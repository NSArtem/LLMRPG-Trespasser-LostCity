#!/usr/bin/env python3
"""Read-only-compatible v0 command adapter for the proof-of-concept extractor.

New work should use ``module-extractor/cli.py``. This historical surface remains
intact for existing commands and preserved v0 fixtures. It deliberately
performs no model calls, prepares deterministic archives for manual uploads,
validates downloaded JSON responses, and renders the provisional v0 layout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import time
from typing import Any, Mapping, Sequence
import zipfile
import zlib


ROOT = Path(__file__).resolve().parents[2]
EXTRACTOR_ROOT = ROOT / "module-extractor"
WORK_ROOT = EXTRACTOR_ROOT / "work"
TOOLS = ("pdfinfo", "pdftotext", "pdfimages", "pdftoppm")
CLASSIFICATIONS = {"topology_map", "mixed", "illustration", "none", "uncertain"}
MAP_CLASSIFICATIONS = {"topology_map", "mixed", "uncertain"}
CONFIDENCES = {"high", "medium", "low"}
EDGE_TYPES = {"corridor", "door", "secret", "stairs", "water", "other"}
DIRECTIONS = {"both", "from_to", "unknown"}
KNOWLEDGE_KINDS = {"fact", "clue", "claim", "rumor"}
TRUTH_STATUSES = {"confirmed", "false", "uncertain", "disputed"}
SAFE_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SAFE_ID = re.compile(r"^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$")
MAP_KEYWORDS = (
    "map",
    "level",
    "dungeon",
    "corridor",
    "stairs",
    "secret door",
    "entrance",
    "exit",
    "area",
)
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


class PocError(RuntimeError):
    """Expected, user-facing command failure."""


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode(
        "utf-8"
    )


def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise PocError(f"file does not exist: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise PocError(f"cannot read JSON from {path}: {exc}") from exc


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json_bytes(value))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise PocError(f"cannot read {path}: {exc}") from exc
    return digest.hexdigest()


def require_tools() -> None:
    missing = [name for name in TOOLS if shutil.which(name) is None]
    if missing:
        raise PocError("missing required Poppler tools: " + ", ".join(missing))


def run_command(
    args: Sequence[str], timings: list[dict[str, Any]], *, label: str
) -> subprocess.CompletedProcess[str]:
    started = time.monotonic()
    try:
        result = subprocess.run(
            list(args),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        raise PocError(f"could not run {args[0]}: {exc}") from exc
    elapsed = time.monotonic() - started
    timings.append(
        {
            "command": label,
            "seconds": round(elapsed, 6),
            "returncode": result.returncode,
        }
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "no diagnostic output"
        raise PocError(f"{label} failed: {detail}")
    return result


def parse_pdfinfo(text: str) -> dict[str, Any]:
    fields: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()
    try:
        pages = int(fields["Pages"])
    except (KeyError, ValueError) as exc:
        raise PocError("pdfinfo output does not contain a valid Pages field") from exc
    if pages < 1:
        raise PocError("PDF has no physical pages")
    return {"pdf_title": fields.get("Title", ""), "pdf_pages": pages}


def parse_pdfimages_list(text: str) -> list[dict[str, Any]]:
    """Parse the stable leading columns from ``pdfimages -list`` output."""

    images: list[dict[str, Any]] = []
    for line in text.splitlines():
        columns = line.split()
        if len(columns) < 13 or not columns[0].isdigit() or not columns[1].isdigit():
            continue
        try:
            page = int(columns[0])
            number = int(columns[1])
            width = int(columns[3])
            height = int(columns[4])
            components = int(columns[6])
            bits_per_component = int(columns[7])
        except (ValueError, IndexError):
            continue
        images.append(
            {
                "pdf_page": page,
                "image_number": number,
                "type": columns[2],
                "width": width,
                "height": height,
                "color": columns[5],
                "components": components,
                "bits_per_component": bits_per_component,
                "encoding": columns[8],
            }
        )
    return images


def split_physical_pages(text: str, expected_pages: int) -> list[str]:
    pages = text.split("\f")
    if pages and pages[-1] == "":
        pages.pop()
    elif pages and not pages[-1].strip():
        pages.pop()
    if len(pages) != expected_pages:
        raise PocError(
            "pdftotext page count mismatch: "
            f"expected {expected_pages}, extracted {len(pages)}"
        )
    return pages


def parse_ppm(path: Path) -> tuple[int, int, bytes]:
    data = path.read_bytes()
    position = 0

    def token() -> bytes:
        nonlocal position
        while position < len(data):
            if data[position : position + 1] == b"#":
                while position < len(data) and data[position : position + 1] != b"\n":
                    position += 1
            elif data[position : position + 1].isspace():
                position += 1
            else:
                break
        start = position
        while position < len(data) and not data[position : position + 1].isspace():
            position += 1
        return data[start:position]

    if token() != b"P6":
        raise PocError(f"unsupported thumbnail format in {path}; expected binary PPM")
    try:
        width = int(token())
        height = int(token())
        maximum = int(token())
    except ValueError as exc:
        raise PocError(f"invalid PPM header in {path}") from exc
    if position >= len(data) or not data[position : position + 1].isspace():
        raise PocError(f"invalid PPM header separator in {path}")
    if data[position : position + 2] == b"\r\n":
        position += 2
    else:
        position += 1
    pixels = data[position:]
    if maximum != 255 or len(pixels) != width * height * 3:
        raise PocError(f"invalid PPM pixel data in {path}")
    return width, height, pixels


def resize_rgb(
    width: int, height: int, pixels: bytes, max_width: int, max_height: int
) -> tuple[int, int, bytes]:
    scale = min(max_width / width, max_height / height, 1.0)
    out_width = max(1, int(width * scale))
    out_height = max(1, int(height * scale))
    if out_width == width and out_height == height:
        return width, height, pixels
    output = bytearray(out_width * out_height * 3)
    for y in range(out_height):
        source_y = min(height - 1, y * height // out_height)
        for x in range(out_width):
            source_x = min(width - 1, x * width // out_width)
            source = (source_y * width + source_x) * 3
            target = (y * out_width + x) * 3
            output[target : target + 3] = pixels[source : source + 3]
    return out_width, out_height, bytes(output)


def png_bytes(width: int, height: int, pixels: bytes) -> bytes:
    if len(pixels) != width * height * 3:
        raise PocError("internal PNG pixel length mismatch")

    def chunk(kind: bytes, payload: bytes) -> bytes:
        body = kind + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))

    rows = b"".join(
        b"\x00" + pixels[y * width * 3 : (y + 1) * width * 3] for y in range(height)
    )
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows, 9))
        + chunk(b"IEND", b"")
    )


FONT = {
    " ": ("000",) * 5,
    "A": ("010", "101", "111", "101", "101"),
    "E": ("111", "100", "110", "100", "111"),
    "G": ("011", "100", "101", "101", "011"),
    "P": ("110", "101", "110", "100", "100"),
    "0": ("111", "101", "101", "101", "111"),
    "1": ("010", "110", "010", "010", "111"),
    "2": ("110", "001", "010", "100", "111"),
    "3": ("110", "001", "010", "001", "110"),
    "4": ("101", "101", "111", "001", "001"),
    "5": ("111", "100", "110", "001", "110"),
    "6": ("011", "100", "111", "101", "111"),
    "7": ("111", "001", "010", "010", "010"),
    "8": ("111", "101", "111", "101", "111"),
    "9": ("111", "101", "111", "001", "110"),
}


def blit(
    canvas: bytearray,
    canvas_width: int,
    canvas_height: int,
    image_width: int,
    image_height: int,
    pixels: bytes,
    x_offset: int,
    y_offset: int,
) -> None:
    for y in range(image_height):
        if y + y_offset >= canvas_height:
            break
        source = y * image_width * 3
        target = ((y + y_offset) * canvas_width + x_offset) * 3
        canvas[target : target + image_width * 3] = pixels[source : source + image_width * 3]


def draw_label(
    canvas: bytearray, width: int, text: str, x: int, y: int, *, scale: int = 2
) -> None:
    cursor = x
    for character in text:
        glyph = FONT.get(character, FONT[" "])
        for row, pattern in enumerate(glyph):
            for column, bit in enumerate(pattern):
                if bit != "1":
                    continue
                for dy in range(scale):
                    for dx in range(scale):
                        pixel_x = cursor + column * scale + dx
                        pixel_y = y + row * scale + dy
                        offset = (pixel_y * width + pixel_x) * 3
                        canvas[offset : offset + 3] = b"\x00\x00\x00"
        cursor += 4 * scale


def make_contact_sheets(
    thumbnails: Sequence[tuple[int, Path]], destination: Path, *, per_sheet: int = 20
) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    results: list[Path] = []
    columns = 4
    cell_width, cell_height = 252, 348
    for sheet_number, start in enumerate(range(0, len(thumbnails), per_sheet), 1):
        batch = thumbnails[start : start + per_sheet]
        rows = (len(batch) + columns - 1) // columns
        canvas_width, canvas_height = columns * cell_width, rows * cell_height
        canvas = bytearray(b"\xff" * (canvas_width * canvas_height * 3))
        for index, (page, thumbnail) in enumerate(batch):
            width, height, pixels = parse_png_rgb(thumbnail)
            column = index % columns
            row = index // columns
            x = column * cell_width + (cell_width - width) // 2
            y = row * cell_height + 20
            blit(canvas, canvas_width, canvas_height, width, height, pixels, x, y)
            draw_label(
                canvas,
                canvas_width,
                f"PAGE {page}",
                column * cell_width + 8,
                row * cell_height + 5,
            )
        path = destination / f"contact-sheet-{sheet_number:03d}.png"
        path.write_bytes(png_bytes(canvas_width, canvas_height, bytes(canvas)))
        results.append(path)
    return results


def parse_png_rgb(path: Path) -> tuple[int, int, bytes]:
    """Read only the deterministic RGB PNG flavor emitted by this program."""

    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise PocError(f"invalid generated PNG: {path}")
    position = 8
    width = height = 0
    compressed = bytearray()
    while position < len(data):
        length = struct.unpack(">I", data[position : position + 4])[0]
        kind = data[position + 4 : position + 8]
        payload = data[position + 8 : position + 8 + length]
        position += 12 + length
        if kind == b"IHDR":
            width, height, depth, color, _, _, _ = struct.unpack(">IIBBBBB", payload)
            if depth != 8 or color != 2:
                raise PocError(f"unsupported generated PNG format: {path}")
        elif kind == b"IDAT":
            compressed.extend(payload)
        elif kind == b"IEND":
            break
    raw = zlib.decompress(bytes(compressed))
    stride = width * 3
    pixels = bytearray()
    for y in range(height):
        row = raw[y * (stride + 1) : (y + 1) * (stride + 1)]
        if not row or row[0] != 0:
            raise PocError(f"unsupported generated PNG filter: {path}")
        pixels.extend(row[1:])
    return width, height, bytes(pixels)


def deterministic_zip(path: Path, entries: Mapping[str, bytes | Path]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(entries):
            if name.startswith("/") or ".." in Path(name).parts:
                raise PocError(f"unsafe ZIP member name: {name}")
            value = entries[name]
            payload = value.read_bytes() if isinstance(value, Path) else value
            info = zipfile.ZipInfo(name, ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            info.create_system = 3
            archive.writestr(info, payload)


def replace_path(source: Path, destination: Path) -> None:
    if destination.is_dir():
        shutil.rmtree(destination)
    elif destination.exists():
        destination.unlink()
    os.replace(source, destination)


def classification_prompt(identity: Mapping[str, Any]) -> str:
    return f"""Classify every physical PDF page represented in this archive.

Create the result as a downloadable file named classification.json. The file
must contain JSON only, matching response-template.json, with no Markdown code
fence or surrounding prose. Do not paste the JSON into the chat unless file
creation is unavailable. Include every physical page from 1 through
{identity['pdf_pages']} exactly once and in ascending order.

Classifications:
- topology_map: a map or diagram whose visible connections matter spatially
- mixed: meaningful topology and substantial other content share the page
- illustration: visual content without operational topology
- none: no topology-relevant visual content
- uncertain: possibly topology-relevant; use this for recall

Use confidence high, medium, or low. Keep notes short. Prefer false positives
over missed maps. Do not use the network, access a repository, run scripts, or
infer content not visible in the supplied files. Copy source_sha256 exactly:
{identity['sha256']}
"""


def classification_template(identity: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source_sha256": identity["sha256"],
        "pages": [
            {
                "pdf_page": page,
                "classification": "uncertain",
                "confidence": "low",
                "notes": "",
            }
            for page in range(1, identity["pdf_pages"] + 1)
        ],
    }


def prepare(args: argparse.Namespace) -> None:
    require_tools()
    if not SAFE_SLUG.fullmatch(args.slug):
        raise PocError("slug must contain lowercase letters, digits, and single hyphens")
    pdf = Path(args.pdf).expanduser()
    if not pdf.is_file():
        raise PocError(f"PDF does not exist or is not a file: {pdf}")
    work = WORK_ROOT / args.slug
    work.mkdir(parents=True, exist_ok=True)
    (work / "responses").mkdir(exist_ok=True)
    timings: list[dict[str, Any]] = []
    total_started = time.monotonic()

    with tempfile.TemporaryDirectory(prefix=".prepare-", dir=work) as temporary:
        stage = Path(temporary)
        info_result = run_command(("pdfinfo", str(pdf)), timings, label="pdfinfo")
        info = parse_pdfinfo(info_result.stdout)
        identity = {
            "filename": pdf.name,
            "sha256": sha256_file(pdf),
            "title": args.title,
            "pdf_title": info["pdf_title"],
            "pdf_pages": info["pdf_pages"],
        }

        shutil.copyfile(pdf, stage / "source.pdf")
        text_dir = stage / "text"
        text_dir.mkdir()
        layout_path = text_dir / "layout.txt"
        run_command(
            ("pdftotext", "-layout", str(pdf), str(layout_path)),
            timings,
            label="pdftotext",
        )
        layout_text = layout_path.read_text(encoding="utf-8", errors="replace")
        page_texts = split_physical_pages(layout_text, identity["pdf_pages"])
        page_text_dir = text_dir / "pages"
        page_text_dir.mkdir()
        for page, text in enumerate(page_texts, 1):
            (page_text_dir / f"page-{page:04d}.txt").write_text(
                text, encoding="utf-8", newline="\n"
            )

        images_dir = stage / "images"
        files_dir = images_dir / "files"
        files_dir.mkdir(parents=True)
        image_list = run_command(
            ("pdfimages", "-list", str(pdf)), timings, label="pdfimages-list"
        )
        image_rows = parse_pdfimages_list(image_list.stdout)
        run_command(
            ("pdfimages", "-all", str(pdf), str(files_dir / "image")),
            timings,
            label="pdfimages-extract",
        )
        extracted_files = sorted(path for path in files_dir.iterdir() if path.is_file())
        by_number: dict[int, list[str]] = {}
        for path in extracted_files:
            match = re.match(r"image-(\d+)", path.name)
            if match:
                by_number.setdefault(int(match.group(1)), []).append(path.name)
        for row in image_rows:
            row["files"] = sorted(by_number.get(row["image_number"], []))
        image_inventory = {"images": image_rows}
        write_json(images_dir / "inventory.json", image_inventory)

        ppm_dir = stage / "ppm"
        ppm_dir.mkdir()
        run_command(
            (
                "pdftoppm",
                "-r",
                "45",
                "-f",
                "1",
                "-l",
                str(identity["pdf_pages"]),
                str(pdf),
                str(ppm_dir / "page"),
            ),
            timings,
            label="pdftoppm-thumbnails",
        )
        ppm_files = sorted(ppm_dir.glob("page-*.ppm"))
        if len(ppm_files) != identity["pdf_pages"]:
            raise PocError(
                "pdftoppm page count mismatch: "
                f"expected {identity['pdf_pages']}, rendered {len(ppm_files)}"
            )
        thumbnails_dir = stage / "thumbnails"
        thumbnails_dir.mkdir()
        thumbnails: list[tuple[int, Path]] = []
        for page, ppm_path in enumerate(ppm_files, 1):
            width, height, pixels = parse_ppm(ppm_path)
            width, height, pixels = resize_rgb(width, height, pixels, 240, 320)
            thumbnail = thumbnails_dir / f"page-{page:04d}.png"
            thumbnail.write_bytes(png_bytes(width, height, pixels))
            thumbnails.append((page, thumbnail))
        contact_dir = stage / "contact-sheets"
        contact_sheets = make_contact_sheets(thumbnails, contact_dir)

        per_page_images: dict[int, list[dict[str, Any]]] = {}
        for row in image_rows:
            per_page_images.setdefault(row["pdf_page"], []).append(row)
        page_signals: list[dict[str, Any]] = []
        for page, text in enumerate(page_texts, 1):
            lowered = text.lower()
            short_labels = [
                line.strip()
                for line in text.splitlines()
                if 0 < len(line.strip()) <= 32
                and re.search(r"[A-Za-z0-9]", line)
            ]
            images = per_page_images.get(page, [])
            hits = [keyword for keyword in MAP_KEYWORDS if keyword in lowered]
            page_signals.append(
                {
                    "pdf_page": page,
                    "text_length": len(text),
                    "short_label_count": len(short_labels),
                    "image_count": len(images),
                    "image_dimensions": [
                        {"width": item["width"], "height": item["height"]}
                        for item in images
                    ],
                    "map_keyword_hits": hits,
                }
            )
        signals = {"pages": page_signals}
        write_json(stage / "signals.json", signals)
        write_json(stage / "source.json", identity)

        pack_entries: dict[str, bytes | Path] = {
            "source.json": stage / "source.json",
            "signals.json": stage / "signals.json",
            "image-inventory.json": images_dir / "inventory.json",
            "prompt.txt": classification_prompt(identity).encode("utf-8"),
            "response-template.json": json_bytes(classification_template(identity)),
        }
        for _, path in thumbnails:
            pack_entries[f"thumbnails/{path.name}"] = path
        for path in contact_sheets:
            pack_entries[f"contact-sheets/{path.name}"] = path
        deterministic_zip(stage / "classification-pack.zip", pack_entries)

        prepare_manifest = {
            "source": identity,
            "classification_pack": "classification-pack.zip",
            "thumbnail_dpi": 45,
            "contact_sheet_pages": 20,
        }
        write_json(stage / "prepare-manifest.json", prepare_manifest)

        for name in (
            "source.pdf",
            "text",
            "images",
            "thumbnails",
            "contact-sheets",
            "signals.json",
            "source.json",
            "classification-pack.zip",
            "prepare-manifest.json",
        ):
            replace_path(stage / name, work / name)
        for stale in (
            "focused-packs",
            "focused",
            "focus-manifest.json",
            "focus-timings.json",
        ):
            target = work / stale
            if target.exists():
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()

    timings.append(
        {
            "command": "prepare-total",
            "seconds": round(time.monotonic() - total_started, 6),
            "returncode": 0,
        }
    )
    write_json(work / "timings.json", {"commands": timings})
    print(work / "classification-pack.zip")


def validate_classification(
    value: Any, identity: Mapping[str, Any]
) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        raise PocError("classification response must be a JSON object")
    if value.get("source_sha256") != identity["sha256"]:
        raise PocError("classification source_sha256 does not match prepared PDF")
    pages = value.get("pages")
    if not isinstance(pages, list):
        raise PocError("classification pages must be an array")
    expected = set(range(1, identity["pdf_pages"] + 1))
    seen: set[int] = set()
    validated: list[dict[str, Any]] = []
    for index, item in enumerate(pages):
        if not isinstance(item, dict):
            raise PocError(f"classification pages[{index}] must be an object")
        page = item.get("pdf_page")
        if not isinstance(page, int) or isinstance(page, bool) or page not in expected:
            raise PocError(f"classification pages[{index}] has invalid pdf_page")
        if page in seen:
            raise PocError(f"classification contains duplicate physical page {page}")
        seen.add(page)
        if item.get("classification") not in CLASSIFICATIONS:
            raise PocError(f"classification page {page} has invalid classification")
        if item.get("confidence") not in CONFIDENCES:
            raise PocError(f"classification page {page} has invalid confidence")
        if not isinstance(item.get("notes"), str):
            raise PocError(f"classification page {page} notes must be a string")
        validated.append(item)
    missing = sorted(expected - seen)
    if missing:
        raise PocError(f"classification is missing physical pages: {missing}")
    if len(pages) != identity["pdf_pages"]:
        raise PocError("classification must contain exactly one result per physical page")
    return sorted(validated, key=lambda item: item["pdf_page"])


def parse_page_list(value: str, page_count: int) -> list[int]:
    if not value.strip():
        return []
    pages: list[int] = []
    for piece in value.split(","):
        try:
            page = int(piece.strip())
        except ValueError as exc:
            raise PocError(f"invalid physical page in --text-pages: {piece!r}") from exc
        if not 1 <= page <= page_count:
            raise PocError(f"text page {page} is outside PDF range 1..{page_count}")
        if page in pages:
            raise PocError(f"duplicate text page {page}")
        pages.append(page)
    return sorted(pages)


def partition(values: Sequence[int], size: int) -> list[list[int]]:
    return [list(values[start : start + size]) for start in range(0, len(values), size)]


def map_prompt(identity: Mapping[str, Any], pack_id: str, pages: Sequence[int]) -> str:
    return f"""Extract only visibly supported topology evidence from this focused pack.

Create the result as a downloadable file named {pack_id}.json. The file must
contain one JSON object only, matching response-template.json and including its
short numeric summary, with no Markdown code fence or surrounding prose. Do not
paste the JSON into the chat unless file creation is unavailable. Copy
source_sha256 and pack_id exactly. Use predictable node IDs derived from printed
labels (for example area-11 or area-1a). Give every edge a predictable ID from
its lexically ordered endpoint pair, regardless of direction (for example
edge-area-11-area-12). Record visible labels, nodes, and edges. Allowed edge
types are corridor, door, secret, stairs, water, and other. Direction is both,
from_to, or unknown. Confidence is high, medium, or low. Uncertainties may
reference a node ID or an edge ID. Every fact must cite physical source pages
from this pack:
{', '.join(str(page) for page in pages)}.

Do not infer invisible connections. Put ambiguity in uncertainties with the
specific object_id it affects. Do not use the network, access a repository, run
scripts, generate module files, or provide a narrative report.

source_sha256: {identity['sha256']}
pack_id: {pack_id}
"""


def map_template(identity: Mapping[str, Any], pack_id: str) -> dict[str, Any]:
    return {
        "kind": "map-evidence",
        "source_sha256": identity["sha256"],
        "pack_id": pack_id,
        "nodes": [
            {
                "id": "area-11",
                "label": "11",
                "source_pages": [],
                "confidence": "low",
            }
        ],
        "edges": [
            {
                "id": "edge-area-11-area-12",
                "from": "area-11",
                "to": "area-12",
                "type": "corridor",
                "direction": "both",
                "source_pages": [],
                "confidence": "low",
            }
        ],
        "uncertainties": [
            {
                "object_id": "area-11",
                "description": "",
                "source_pages": [],
            }
        ],
        "summary": {"nodes": 1, "edges": 1, "uncertainties": 1},
    }


def text_prompt(identity: Mapping[str, Any], pack_id: str, pages: Sequence[int]) -> str:
    return f"""Extract English operational evidence from the supplied physical pages.

Return one JSON object only, matching response-template.json, including its
short numeric summary. Copy source_sha256 and pack_id exactly. Paraphrase; do
not reproduce long source passages. Create stable safe IDs and cite only these
physical PDF pages: {', '.join(str(page) for page in pages)}.

Places need title, description, occupants, hazards, resources, and exits.
Actors need role, goals, reactions, mechanics, and knowledge. Situations need
trigger, participants, stakes, approaches, consequences, and references.
Procedures need a trigger and ordered steps, with state only when useful.
Knowledge needs kind (fact, clue, claim, or rumor), text, truth_status
(confirmed, false, uncertain, or disputed), and subjects. Attach every
uncertainty to a specific object_id.

Do not use the network, access a repository, run scripts, generate module
files, invent unsupported detail, list pending units, or provide a narrative
report.

source_sha256: {identity['sha256']}
pack_id: {pack_id}
"""


def text_template(identity: Mapping[str, Any], pack_id: str) -> dict[str, Any]:
    return {
        "kind": "text-evidence",
        "source_sha256": identity["sha256"],
        "pack_id": pack_id,
        "places": [
            {
                "id": "place.example",
                "title": "Example place",
                "description": "",
                "occupants": [],
                "hazards": [],
                "resources": [],
                "exits": [],
                "source_pages": [],
            }
        ],
        "actors": [
            {
                "id": "actor.example",
                "title": "Example actor",
                "role": "",
                "goals": [],
                "reactions": [],
                "mechanics": [],
                "knowledge": [],
                "source_pages": [],
            }
        ],
        "situations": [
            {
                "id": "situation.example",
                "title": "Example situation",
                "trigger": "",
                "participants": [],
                "stakes": [],
                "approaches": [],
                "consequences": [],
                "references": [],
                "source_pages": [],
            }
        ],
        "procedures": [
            {
                "id": "procedure.example",
                "title": "Example procedure",
                "trigger": "",
                "steps": [],
                "state": None,
                "source_pages": [],
            }
        ],
        "knowledge": [
            {
                "id": "fact.example",
                "kind": "fact",
                "text": "",
                "truth_status": "uncertain",
                "subjects": [],
                "source_pages": [],
            }
        ],
        "uncertainties": [
            {
                "object_id": "place.example",
                "description": "",
                "source_pages": [],
            }
        ],
        "summary": {
            "places": 1,
            "actors": 1,
            "situations": 1,
            "procedures": 1,
            "knowledge": 1,
            "uncertainties": 1,
        },
    }


def add_common_pack_entries(
    entries: dict[str, bytes | Path],
    identity: Mapping[str, Any],
    pack_id: str,
    kind: str,
    pages: Sequence[int],
) -> None:
    entries["pack.json"] = json_bytes(
        {
            "pack_id": pack_id,
            "kind": kind,
            "source": identity,
            "physical_pages": list(pages),
        }
    )


def focus(args: argparse.Namespace) -> None:
    require_tools()
    if not SAFE_SLUG.fullmatch(args.slug):
        raise PocError("invalid slug")
    work = WORK_ROOT / args.slug
    prepared = load_json(work / "prepare-manifest.json")
    if not isinstance(prepared, dict) or not isinstance(prepared.get("source"), dict):
        raise PocError("invalid prepare-manifest.json")
    identity = prepared["source"]
    classification_path = Path(args.classification)
    classification = validate_classification(load_json(classification_path), identity)
    text_pages = parse_page_list(args.text_pages, identity["pdf_pages"])
    map_pages = [
        item["pdf_page"]
        for item in classification
        if item["classification"] in MAP_CLASSIFICATIONS
    ]
    source_pdf = work / "source.pdf"
    if not source_pdf.is_file() or sha256_file(source_pdf) != identity["sha256"]:
        raise PocError("prepared source.pdf is missing or its SHA-256 has changed")
    timings: list[dict[str, Any]] = []
    total_started = time.monotonic()

    with tempfile.TemporaryDirectory(prefix=".focus-", dir=work) as temporary:
        stage = Path(temporary)
        packs_dir = stage / "focused-packs"
        packs_dir.mkdir()
        rendered_dir = stage / "focused" / "map-renders"
        rendered_dir.mkdir(parents=True)
        for page in map_pages:
            output_prefix = rendered_dir / f"page-{page:04d}"
            run_command(
                (
                    "pdftoppm",
                    "-png",
                    "-r",
                    "200",
                    "-f",
                    str(page),
                    "-l",
                    str(page),
                    "-singlefile",
                    str(source_pdf),
                    str(output_prefix),
                ),
                timings,
                label=f"pdftoppm-map-page-{page}",
            )
            if not output_prefix.with_suffix(".png").is_file():
                raise PocError(f"pdftoppm did not create render for physical page {page}")

        inventory = load_json(work / "images" / "inventory.json")
        image_rows = inventory.get("images", []) if isinstance(inventory, dict) else []
        pack_records: list[dict[str, Any]] = []
        for number, pages in enumerate(partition(map_pages, 10), 1):
            pack_id = f"map-{number:03d}"
            entries: dict[str, bytes | Path] = {
                "prompt.txt": map_prompt(identity, pack_id, pages).encode("utf-8"),
                "response-template.json": json_bytes(map_template(identity, pack_id)),
            }
            add_common_pack_entries(entries, identity, pack_id, "map-evidence", pages)
            for page in pages:
                entries[f"pages/page-{page:04d}.txt"] = (
                    work / "text" / "pages" / f"page-{page:04d}.txt"
                )
                entries[f"renders/page-{page:04d}.png"] = (
                    rendered_dir / f"page-{page:04d}.png"
                )
                for row in image_rows:
                    if row.get("pdf_page") != page:
                        continue
                    for filename in row.get("files", []):
                        source = work / "images" / "files" / filename
                        if source.is_file():
                            entries[f"embedded/page-{page:04d}/{filename}"] = source
            archive = packs_dir / f"{pack_id}.zip"
            deterministic_zip(archive, entries)
            pack_records.append(
                {"pack_id": pack_id, "kind": "map-evidence", "physical_pages": pages}
            )

        for number, pages in enumerate(partition(text_pages, 8), 1):
            pack_id = f"text-{number:03d}"
            entries = {
                "prompt.txt": text_prompt(identity, pack_id, pages).encode("utf-8"),
                "response-template.json": json_bytes(text_template(identity, pack_id)),
            }
            add_common_pack_entries(entries, identity, pack_id, "text-evidence", pages)
            for page in pages:
                entries[f"pages/page-{page:04d}.txt"] = (
                    work / "text" / "pages" / f"page-{page:04d}.txt"
                )
                thumbnail = work / "thumbnails" / f"page-{page:04d}.png"
                if thumbnail.is_file():
                    entries[f"thumbnails/page-{page:04d}.png"] = thumbnail
            archive = packs_dir / f"{pack_id}.zip"
            deterministic_zip(archive, entries)
            pack_records.append(
                {"pack_id": pack_id, "kind": "text-evidence", "physical_pages": pages}
            )

        focus_manifest = {
            "source": identity,
            "classification_response_sha256": sha256_file(classification_path),
            "classified_pages": classification,
            "classified_map_pages": map_pages,
            "selected_text_pages": text_pages,
            "packs": pack_records,
        }
        write_json(stage / "focus-manifest.json", focus_manifest)
        replace_path(stage / "focused-packs", work / "focused-packs")
        replace_path(stage / "focused", work / "focused")
        replace_path(stage / "focus-manifest.json", work / "focus-manifest.json")

    timings.append(
        {
            "command": "focus-total",
            "seconds": round(time.monotonic() - total_started, 6),
            "returncode": 0,
        }
    )
    write_json(work / "focus-timings.json", {"commands": timings})
    for record in pack_records:
        print(work / "focused-packs" / f"{record['pack_id']}.zip")


def expect_dict(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PocError(f"{context} must be an object")
    return value


def expect_string(record: Mapping[str, Any], field: str, context: str) -> str:
    value = record.get(field)
    if not isinstance(value, str):
        raise PocError(f"{context}.{field} must be a string")
    return value


def expect_string_list(record: Mapping[str, Any], field: str, context: str) -> list[str]:
    value = record.get(field)
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise PocError(f"{context}.{field} must be an array of strings")
    return value


def expect_pages(
    record: Mapping[str, Any],
    context: str,
    page_count: int,
    allowed_pages: set[int],
) -> list[int]:
    value = record.get("source_pages")
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, int) or isinstance(item, bool) for item in value)
    ):
        raise PocError(f"{context}.source_pages must be a non-empty integer array")
    if len(set(value)) != len(value):
        raise PocError(f"{context}.source_pages contains duplicates")
    invalid = [page for page in value if page < 1 or page > page_count]
    if invalid:
        raise PocError(f"{context}.source_pages is outside the physical PDF range")
    outside = [page for page in value if page not in allowed_pages]
    if outside:
        raise PocError(f"{context}.source_pages cites pages outside its focused pack")
    return value


def expect_id(record: Mapping[str, Any], context: str) -> str:
    identifier = expect_string(record, "id", context)
    if not SAFE_ID.fullmatch(identifier):
        raise PocError(f"{context}.id is unsafe: {identifier!r}")
    return identifier


def validate_summary(
    response: Mapping[str, Any], arrays: Sequence[str], context: str
) -> None:
    summary = expect_dict(response.get("summary"), f"{context}.summary")
    for name in arrays:
        count = summary.get(name)
        if not isinstance(count, int) or isinstance(count, bool):
            raise PocError(f"{context}.summary.{name} must be an integer")
        if count != len(response.get(name, [])):
            raise PocError(f"{context}.summary.{name} does not match the array count")


def response_array(response: Mapping[str, Any], name: str, context: str) -> list[Any]:
    value = response.get(name)
    if not isinstance(value, list):
        raise PocError(f"{context}.{name} must be an array")
    return value


def validate_uncertainties(
    response: Mapping[str, Any],
    context: str,
    page_count: int,
    pages: set[int],
    known_ids: set[str],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for index, value in enumerate(response_array(response, "uncertainties", context)):
        item_context = f"{context}.uncertainties[{index}]"
        item = expect_dict(value, item_context)
        object_id = expect_string(item, "object_id", item_context)
        if object_id not in known_ids:
            raise PocError(f"{item_context}.object_id references an unknown object")
        expect_string(item, "description", item_context)
        expect_pages(item, item_context, page_count, pages)
        results.append(item)
    return results


def default_edge_id(start: str, end: str) -> str:
    """Return the legacy edge identity used when a saved response has no edge ID."""
    first, second = sorted((start, end))
    return f"edge-{first}-{second}"


def edge_observation_id(pack_id: str, edge_id: str) -> str:
    return f"{pack_id}.edge.{edge_id}"


def node_observation_id(pack_id: str, node_id: str) -> str:
    return f"{pack_id}.node.{node_id}"


def normalized_edge_signature(edge: Mapping[str, Any]) -> tuple[str, str, str, str]:
    """Normalize endpoint order only when the observation has no traversal direction."""
    start = edge["from"]
    end = edge["to"]
    if edge["direction"] in {"both", "unknown"}:
        start, end = sorted((start, end))
    return (start, end, edge["type"], edge["direction"])


def validate_map_response(
    response: Mapping[str, Any],
    pack: Mapping[str, Any],
    identity: Mapping[str, Any],
) -> dict[str, Any]:
    context = f"response {pack['pack_id']}"
    pages = set(pack["physical_pages"])
    nodes: list[dict[str, Any]] = []
    node_ids: set[str] = set()
    for index, value in enumerate(response_array(response, "nodes", context)):
        item_context = f"{context}.nodes[{index}]"
        node = expect_dict(value, item_context)
        identifier = expect_id(node, item_context)
        if identifier in node_ids:
            raise PocError(f"{context} contains duplicate node ID {identifier}")
        node_ids.add(identifier)
        expect_string(node, "label", item_context)
        expect_pages(node, item_context, identity["pdf_pages"], pages)
        if node.get("confidence") not in CONFIDENCES:
            raise PocError(f"{item_context}.confidence is invalid")
        if "title" in node:
            expect_string(node, "title", item_context)
        nodes.append(
            {
                **node,
                "observation_id": node_observation_id(pack["pack_id"], identifier),
                "pack_id": pack["pack_id"],
            }
        )
    edges: list[dict[str, Any]] = []
    edge_keys: set[tuple[str, str, str, str]] = set()
    edge_ids: set[str] = set()
    edge_references: dict[str, list[dict[str, Any]]] = {}
    for index, value in enumerate(response_array(response, "edges", context)):
        item_context = f"{context}.edges[{index}]"
        edge = expect_dict(value, item_context)
        start = expect_string(edge, "from", item_context)
        end = expect_string(edge, "to", item_context)
        if start not in node_ids or end not in node_ids:
            raise PocError(f"{item_context} references a missing node")
        if edge.get("type") not in EDGE_TYPES:
            raise PocError(f"{item_context}.type is invalid")
        if edge.get("direction") not in DIRECTIONS:
            raise PocError(f"{item_context}.direction is invalid")
        if edge.get("confidence") not in CONFIDENCES:
            raise PocError(f"{item_context}.confidence is invalid")
        expect_pages(edge, item_context, identity["pdf_pages"], pages)
        key = normalized_edge_signature(edge)
        if key in edge_keys:
            raise PocError(f"{context} contains a duplicate edge")
        edge_keys.add(key)
        canonical_id = default_edge_id(start, end)
        if "id" in edge:
            source_id = expect_id(edge, item_context)
        else:
            # The completed PoC responses predate edge IDs. Deriving the identity
            # from the unordered endpoint pair preserves those fixtures.
            source_id = canonical_id
        if source_id in edge_ids:
            raise PocError(f"{context} contains duplicate edge ID {source_id}")
        if source_id in node_ids:
            raise PocError(f"{context} uses {source_id} as both a node and edge ID")
        edge_ids.add(source_id)
        validated_edge = {
            **edge,
            "id": canonical_id,
            "source_id": source_id,
            "observation_id": edge_observation_id(pack["pack_id"], source_id),
            "pack_id": pack["pack_id"],
        }
        edges.append(validated_edge)
        aliases = {
            source_id,
            canonical_id,
            f"edge-{start}-{end}",
            f"edge-{end}-{start}",
        }
        for alias in aliases:
            edge_references.setdefault(alias, []).append(validated_edge)

    uncertainties: list[dict[str, Any]] = []
    for index, value in enumerate(response_array(response, "uncertainties", context)):
        item_context = f"{context}.uncertainties[{index}]"
        item = expect_dict(value, item_context)
        object_id = expect_string(item, "object_id", item_context)
        expect_string(item, "description", item_context)
        expect_pages(item, item_context, identity["pdf_pages"], pages)
        if object_id in node_ids:
            target_id = object_id
            object_kind = "node"
            observation_id = node_observation_id(pack["pack_id"], object_id)
        else:
            targets = edge_references.get(object_id, [])
            unique_targets = {
                target["observation_id"]: target for target in targets
            }
            if not unique_targets:
                raise PocError(f"{item_context}.object_id references an unknown object")
            if len(unique_targets) != 1:
                raise PocError(f"{item_context}.object_id is an ambiguous edge reference")
            target = next(iter(unique_targets.values()))
            target_id = target["id"]
            object_kind = "edge"
            observation_id = target["observation_id"]
        uncertainties.append(
            {
                "id": f"{pack['pack_id']}.uncertainty-{index + 1:03d}",
                "pack_id": pack["pack_id"],
                "object_id": target_id,
                "object_kind": object_kind,
                "observation_id": observation_id,
                "source_object_id": object_id,
                "description": item["description"],
                "source_pages": item["source_pages"],
            }
        )
    validate_summary(response, ("nodes", "edges", "uncertainties"), context)
    return {
        "pack_id": pack["pack_id"],
        "nodes": nodes,
        "edges": edges,
        "uncertainties": uncertainties,
    }


TEXT_REQUIRED: dict[str, tuple[str, ...]] = {
    "places": ("title", "description"),
    "actors": ("title", "role"),
    "situations": ("title", "trigger"),
    "procedures": ("title", "trigger"),
    "knowledge": ("text",),
}
TEXT_LIST_FIELDS: dict[str, tuple[str, ...]] = {
    "places": ("occupants", "hazards", "resources", "exits"),
    "actors": ("goals", "reactions", "mechanics", "knowledge"),
    "situations": (
        "participants",
        "stakes",
        "approaches",
        "consequences",
        "references",
    ),
    "procedures": ("steps",),
    "knowledge": ("subjects",),
}


def validate_text_response(
    response: Mapping[str, Any],
    pack: Mapping[str, Any],
    identity: Mapping[str, Any],
) -> dict[str, Any]:
    context = f"response {pack['pack_id']}"
    pages = set(pack["physical_pages"])
    result: dict[str, Any] = {}
    all_ids: set[str] = set()
    for category in TEXT_REQUIRED:
        records: list[dict[str, Any]] = []
        for index, value in enumerate(response_array(response, category, context)):
            item_context = f"{context}.{category}[{index}]"
            record = expect_dict(value, item_context)
            identifier = expect_id(record, item_context)
            if identifier in all_ids:
                raise PocError(f"{context} contains duplicate object ID {identifier}")
            all_ids.add(identifier)
            for field in TEXT_REQUIRED[category]:
                expect_string(record, field, item_context)
            for field in TEXT_LIST_FIELDS[category]:
                expect_string_list(record, field, item_context)
            expect_pages(record, item_context, identity["pdf_pages"], pages)
            if category == "knowledge":
                if record.get("kind") not in KNOWLEDGE_KINDS:
                    raise PocError(f"{item_context}.kind is invalid")
                if record.get("truth_status") not in TRUTH_STATUSES:
                    raise PocError(f"{item_context}.truth_status is invalid")
            if category == "places" and "topology_node" in record:
                topology_node = expect_string(record, "topology_node", item_context)
                if not SAFE_ID.fullmatch(topology_node):
                    raise PocError(f"{item_context}.topology_node is unsafe")
            records.append(record)
        result[category] = records
    result["uncertainties"] = validate_uncertainties(
        response, context, identity["pdf_pages"], pages, all_ids
    )
    validate_summary(
        response,
        ("places", "actors", "situations", "procedures", "knowledge", "uncertainties"),
        context,
    )
    return result


def yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    raise PocError(f"cannot serialize YAML scalar of type {type(value).__name__}")


def yaml_lines(value: Any, indent: int = 0) -> list[str]:
    prefix = " " * indent
    if isinstance(value, dict):
        if not value:
            return [prefix + "{}"]
        lines: list[str] = []
        for key, child in value.items():
            if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", key):
                raise PocError(f"cannot serialize unsafe YAML key {key!r}")
            if isinstance(child, (dict, list)) and child:
                lines.append(f"{prefix}{key}:")
                lines.extend(yaml_lines(child, indent + 2))
            elif isinstance(child, (dict, list)):
                lines.append(f"{prefix}{key}: {'{}' if isinstance(child, dict) else '[]'}")
            else:
                lines.append(f"{prefix}{key}: {yaml_scalar(child)}")
        return lines
    if isinstance(value, list):
        if not value:
            return [prefix + "[]"]
        lines = []
        for child in value:
            if isinstance(child, (dict, list)):
                lines.append(prefix + "-")
                lines.extend(yaml_lines(child, indent + 2))
            else:
                lines.append(prefix + "- " + yaml_scalar(child))
        return lines
    return [prefix + yaml_scalar(value)]


def yaml_text(value: Any) -> str:
    return "\n".join(yaml_lines(value)) + "\n"


def markdown_list(values: Sequence[str]) -> str:
    return "\n".join(f"- {value}" for value in values) if values else "- None."


def render_place(record: Mapping[str, Any]) -> str:
    frontmatter: dict[str, Any] = {
        "id": record["id"],
        "title": record["title"],
        "source_pages": sorted(record["source_pages"]),
    }
    if record.get("topology_node"):
        frontmatter["topology_node"] = record["topology_node"]
    return (
        "---\n"
        + yaml_text(frontmatter)
        + "---\n\n"
        + "## Description\n\n"
        + record["description"].strip()
        + "\n\n## Occupants\n\n"
        + markdown_list(record["occupants"])
        + "\n\n## Hazards\n\n"
        + markdown_list(record["hazards"])
        + "\n\n## Resources\n\n"
        + markdown_list(record["resources"])
        + "\n\n## Exits\n\n"
        + markdown_list(record["exits"])
        + "\n"
    )


def render_actor(record: Mapping[str, Any]) -> str:
    return (
        "---\n"
        + yaml_text(
            {
                "id": record["id"],
                "title": record["title"],
                "source_pages": sorted(record["source_pages"]),
            }
        )
        + "---\n\n## Role\n\n"
        + record["role"].strip()
        + "\n\n## Goals\n\n"
        + markdown_list(record["goals"])
        + "\n\n## Reactions\n\n"
        + markdown_list(record["reactions"])
        + "\n\n## Mechanics\n\n"
        + markdown_list(record["mechanics"])
        + "\n\n## Knowledge\n\n"
        + markdown_list(record["knowledge"])
        + "\n"
    )


def render_situation(record: Mapping[str, Any]) -> str:
    sections = (
        ("Trigger", [record["trigger"]]),
        ("Participants", record["participants"]),
        ("Stakes", record["stakes"]),
        ("Approaches", record["approaches"]),
        ("Consequences", record["consequences"]),
        ("References", record["references"]),
    )
    body = ""
    for title, values in sections:
        body += f"\n## {title}\n\n"
        if title == "Trigger":
            body += values[0].strip() or "None."
        else:
            body += markdown_list(values)
        body += "\n"
    return (
        "---\n"
        + yaml_text(
            {
                "id": record["id"],
                "title": record["title"],
                "source_pages": sorted(record["source_pages"]),
            }
        )
        + "---\n"
        + body
    )


def reconcile_map_observations(
    maps: Sequence[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Consolidate compatible map observations without selecting among conflicts."""
    node_groups: dict[str, list[dict[str, Any]]] = {}
    edge_groups: dict[str, list[dict[str, Any]]] = {}
    for response in maps:
        for node in response["nodes"]:
            node_groups.setdefault(node["id"], []).append(node)
        for edge in response["edges"]:
            edge_groups.setdefault(edge["id"], []).append(edge)

    nodes: list[dict[str, Any]] = []
    for node_id, observations in sorted(node_groups.items()):
        ordered = sorted(observations, key=lambda item: item["observation_id"])
        nodes.append(
            {
                "id": node_id,
                "labels": sorted({item["label"] for item in ordered}),
                "source_pages": sorted(
                    {page for item in ordered for page in item["source_pages"]}
                ),
                "observations": [
                    {
                        key: item[key]
                        for key in (
                            "observation_id",
                            "pack_id",
                            "label",
                            "title",
                            "source_pages",
                            "confidence",
                        )
                        if key in item
                    }
                    for item in ordered
                ],
            }
        )

    edges: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    for edge_id, observations in sorted(edge_groups.items()):
        endpoint_pairs = {
            tuple(sorted((item["from"], item["to"]))) for item in observations
        }
        if len(endpoint_pairs) != 1:
            raise PocError(
                f"topology edge ID {edge_id} refers to different endpoint pairs across packs"
            )
        endpoints = list(next(iter(endpoint_pairs)))
        variants_by_signature: dict[
            tuple[str, str, str, str], list[dict[str, Any]]
        ] = {}
        for observation in observations:
            variants_by_signature.setdefault(
                normalized_edge_signature(observation), []
            ).append(observation)

        variants: list[dict[str, Any]] = []
        for signature, variant_observations in sorted(variants_by_signature.items()):
            start, end, edge_type, direction = signature
            ordered = sorted(
                variant_observations, key=lambda item: item["observation_id"]
            )
            variants.append(
                {
                    "from": start,
                    "to": end,
                    "type": edge_type,
                    "direction": direction,
                    "source_pages": sorted(
                        {page for item in ordered for page in item["source_pages"]}
                    ),
                    "observations": [
                        {
                            key: item[key]
                            for key in (
                                "observation_id",
                                "pack_id",
                                "source_id",
                                "from",
                                "to",
                                "type",
                                "direction",
                                "source_pages",
                                "confidence",
                            )
                        }
                        for item in ordered
                    ],
                }
            )

        types = {variant["type"] for variant in variants}
        directions = {
            (
                variant["direction"],
                variant["from"] if variant["direction"] == "from_to" else "",
                variant["to"] if variant["direction"] == "from_to" else "",
            )
            for variant in variants
        }
        conflict_fields: list[str] = []
        if len(types) > 1:
            conflict_fields.append("type")
        if len(directions) > 1:
            conflict_fields.append("direction")
        edge_record = {
            "id": edge_id,
            "endpoints": endpoints,
            "status": "conflict" if conflict_fields else "consistent",
            "conflict_fields": conflict_fields,
            "source_pages": sorted(
                {page for item in observations for page in item["source_pages"]}
            ),
            "variants": variants,
        }
        edges.append(edge_record)
        if conflict_fields:
            conflicts.append(
                {
                    "edge_id": edge_id,
                    "endpoints": endpoints,
                    "fields": conflict_fields,
                }
            )

    uncertainties = sorted(
        (
            uncertainty
            for response in maps
            for uncertainty in response["uncertainties"]
        ),
        key=lambda item: item["id"],
    )
    return {
        "nodes": nodes,
        "edges": edges,
        "conflicts": conflicts,
        "uncertainties": uncertainties,
    }


def validate_cross_pack_records(
    topology: Mapping[str, Sequence[dict[str, Any]]],
    texts: Sequence[dict[str, Any]],
) -> None:
    node_ids = {node["id"] for node in topology["nodes"]}
    object_ids: set[str] = set()
    for response in texts:
        for category in TEXT_REQUIRED:
            for record in response[category]:
                if record["id"] in object_ids:
                    raise PocError(f"duplicate text object ID across packs: {record['id']}")
                object_ids.add(record["id"])
                topology_node = record.get("topology_node")
                if (
                    category == "places"
                    and topology_node is not None
                    and topology_node not in node_ids
                ):
                    raise PocError(
                        f"place {record['id']} references missing topology node "
                        f"{record['topology_node']}"
                    )


def assemble(args: argparse.Namespace) -> None:
    if not SAFE_SLUG.fullmatch(args.slug):
        raise PocError("invalid slug")
    work = WORK_ROOT / args.slug
    focus_manifest = expect_dict(
        load_json(work / "focus-manifest.json"), "focus-manifest"
    )
    identity = expect_dict(focus_manifest.get("source"), "focus-manifest.source")
    expected_packs: dict[str, dict[str, Any]] = {}
    for index, value in enumerate(focus_manifest.get("packs", [])):
        pack = expect_dict(value, f"focus-manifest.packs[{index}]")
        pack_id = expect_string(pack, "pack_id", f"focus-manifest.packs[{index}]")
        if pack_id in expected_packs:
            raise PocError(f"focus manifest contains duplicate pack ID {pack_id}")
        expected_packs[pack_id] = pack
    if not expected_packs:
        raise PocError("focus manifest contains no evidence packs")

    responses: dict[str, Mapping[str, Any]] = {}
    for argument in args.evidence:
        path = Path(argument)
        response = expect_dict(load_json(path), f"evidence {path}")
        pack_id = response.get("pack_id")
        if not isinstance(pack_id, str) or pack_id not in expected_packs:
            raise PocError(f"{path} has an unknown pack_id: {pack_id!r}")
        if pack_id in responses:
            raise PocError(f"duplicate evidence response for pack ID {pack_id}")
        if response.get("source_sha256") != identity["sha256"]:
            raise PocError(f"{path} source_sha256 does not match prepared PDF")
        pack = expected_packs[pack_id]
        if response.get("kind") != pack["kind"]:
            raise PocError(f"{path} kind does not match focused pack {pack_id}")
        responses[pack_id] = response
    missing = sorted(set(expected_packs) - set(responses))
    if missing:
        raise PocError("missing evidence responses for pack IDs: " + ", ".join(missing))

    validated_maps: list[dict[str, Any]] = []
    validated_texts: list[dict[str, Any]] = []
    for pack_id in sorted(expected_packs):
        pack = expected_packs[pack_id]
        response = responses[pack_id]
        if pack["kind"] == "map-evidence":
            validated_maps.append(validate_map_response(response, pack, identity))
        elif pack["kind"] == "text-evidence":
            validated_texts.append(validate_text_response(response, pack, identity))
        else:
            raise PocError(f"focus manifest has unknown evidence kind {pack['kind']!r}")
    topology = reconcile_map_observations(validated_maps)
    validate_cross_pack_records(topology, validated_texts)

    output = Path(args.output)
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise PocError(f"refusing to overwrite non-empty output: {output}")
    output_parent = output.parent.resolve()
    output_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".module-stage-", dir=output_parent) as temporary:
        stage = Path(temporary)
        for directory in (
            "places",
            "actors",
            "situations",
            "topology",
            "procedures",
            "knowledge",
        ):
            (stage / directory).mkdir()

        places = sorted(
            (record for result in validated_texts for record in result["places"]),
            key=lambda item: item["id"],
        )
        actors = sorted(
            (record for result in validated_texts for record in result["actors"]),
            key=lambda item: item["id"],
        )
        situations = sorted(
            (record for result in validated_texts for record in result["situations"]),
            key=lambda item: item["id"],
        )
        procedures = sorted(
            (record for result in validated_texts for record in result["procedures"]),
            key=lambda item: item["id"],
        )
        knowledge = sorted(
            (record for result in validated_texts for record in result["knowledge"]),
            key=lambda item: item["id"],
        )
        for record in places:
            (stage / "places" / f"{record['id']}.md").write_text(
                render_place(record), encoding="utf-8", newline="\n"
            )
        for record in actors:
            (stage / "actors" / f"{record['id']}.md").write_text(
                render_actor(record), encoding="utf-8", newline="\n"
            )
        for record in situations:
            (stage / "situations" / f"{record['id']}.md").write_text(
                render_situation(record), encoding="utf-8", newline="\n"
            )
        for record in procedures:
            (stage / "procedures" / f"{record['id']}.yaml").write_text(
                yaml_text(record), encoding="utf-8", newline="\n"
            )
        (stage / "knowledge" / "facts.yaml").write_text(
            yaml_text({"knowledge": knowledge}), encoding="utf-8", newline="\n"
        )
        (stage / "topology" / "graph.yaml").write_text(
            yaml_text(topology),
            encoding="utf-8",
            newline="\n",
        )
        manifest = {
            "title": identity["title"],
            "experiment": True,
            "incomplete": True,
            "source": {
                "filename": identity["filename"],
                "sha256": identity["sha256"],
                "pdf_title": identity["pdf_title"],
                "pdf_pages": identity["pdf_pages"],
            },
            "selected_text_pages": focus_manifest["selected_text_pages"],
            "classified_map_pages": focus_manifest["classified_map_pages"],
            "evidence_pack_ids": sorted(expected_packs),
            "topology": {
                "nodes": len(topology["nodes"]),
                "node_observations": sum(
                    len(node["observations"]) for node in topology["nodes"]
                ),
                "edges": len(topology["edges"]),
                "edge_observations": sum(
                    len(variant["observations"])
                    for edge in topology["edges"]
                    for variant in edge["variants"]
                ),
                "conflicts": len(topology["conflicts"]),
            },
        }
        (stage / "manifest.yaml").write_text(
            yaml_text(manifest), encoding="utf-8", newline="\n"
        )

        if output.exists():
            output.rmdir()
        os.replace(stage, output)
    print(output)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare manual ChatGPT packs and assemble a proof-of-concept module."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("pdf", metavar="PDF")
    prepare_parser.add_argument("--slug", required=True)
    prepare_parser.add_argument("--title", required=True)
    prepare_parser.set_defaults(function=prepare)

    focus_parser = subparsers.add_parser("focus")
    focus_parser.add_argument("--slug", required=True)
    focus_parser.add_argument("--classification", required=True)
    focus_parser.add_argument("--text-pages", required=True)
    focus_parser.set_defaults(function=focus)

    assemble_parser = subparsers.add_parser("assemble")
    assemble_parser.add_argument("--slug", required=True)
    assemble_parser.add_argument("--evidence", nargs="+", required=True)
    assemble_parser.add_argument("--output", default="module")
    assemble_parser.set_defaults(function=assemble)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.function(args)
    except PocError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
