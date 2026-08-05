"""Prepare one repository-local module workspace from a PDF."""

from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any

from .errors import ExtractorError
from .routing import routing_pack_readme, routing_prompt, routing_template
from .util import (
    SAFE_SLUG,
    atomic_publish,
    canonical_json_bytes,
    deterministic_zip,
    sha256_file,
    write_json,
)


POPLER_TOOLS = ("pdfinfo", "pdftotext", "pdftoppm", "pdftohtml")

# Segmentation needs the typesetter's own choices -- point size, family, weight,
# colour -- and `pdftotext -bbox-layout` exposes only a box per word. Glyph
# height is a lossy proxy for size and discards the rest, and two of the five
# in-scope sources could not be segmented from it at all. `pdftohtml -xml` ships
# in the same Poppler package and emits all four.
#
# `-i` drops images: this is text geometry, not artwork. `-hidden` keeps text
# that sits under a covering element. `-stdout` avoids a temporary tree.
PDFTOHTML_ARGUMENTS = ("-xml", "-i", "-hidden", "-stdout")

_FONTSPEC = re.compile(r"<fontspec\b[^>]*>")
_TEXT_RUN = re.compile(r"<text\b")
_XML_ATTRIBUTE = re.compile(r'(\w+)="([^"]*)"')
# PDF embeds subsetted fonts under an arbitrary six-letter tag, so one face is
# "DHWVTZ+BookAntiqua" on one page and "CZMPFB+BookAntiqua" on the next. The tag
# is packaging, not typography, and counting it would inflate the style count on
# a perfectly ordinary document.
_SUBSET_TAG = re.compile(r"^[A-Z]{6}\+")

# Below this many runs a document is too small for the ratio to mean anything,
# and the empty-text check is the operative one.
TEXT_LAYER_MIN_RUNS = 200
# Measured across every in-scope source: 145 (Lair), 122 (Winter's Daughter),
# 103 (Falkrest), 115 (Doom), 190 (Шпиль Кетцаль), 190 (The Lost City) runs per
# distinct style. Curse of Strahd, an EPSON Scan carrying 32,020 runs under
# 11,964 synthetic styles, gives 2.7. The threshold sits a factor of five below
# the worst typeset source and a factor of seven above the scan.
TEXT_LAYER_MIN_RUNS_PER_STYLE = 20.0


def inferred_slug(pdf: Path) -> str:
    """Return the safe ASCII slug implied by a PDF filename."""
    return re.sub(r"[^a-z0-9]+", "-", pdf.stem.lower()).strip("-")


def readable_stem(pdf: Path) -> str:
    """Turn a filename stem into a useful fallback title."""
    return re.sub(r"[_-]+", " ", pdf.stem).strip()


def _run(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            arguments,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        raise ExtractorError(f"could not run {arguments[0]}: {exc}") from exc
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "no diagnostic"
        raise ExtractorError(f"{arguments[0]} failed: {detail}")
    return result


def _pdf_info(path: Path) -> dict[str, Any]:
    result = _run(["pdfinfo", str(path)])
    fields = {}
    for line in result.stdout.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    try:
        pages = int(fields["Pages"])
    except (KeyError, ValueError) as exc:
        raise ExtractorError("pdfinfo did not return a valid Pages field") from exc
    if pages < 1:
        raise ExtractorError("PDF contains no physical pages")
    return {"pdf_pages": pages, "pdf_title": fields.get("Title", "")}


def _split_pages(text: str, expected: int) -> list[str]:
    pages = text.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    if len(pages) != expected:
        raise ExtractorError(
            f"pdftotext page count mismatch: expected {expected}, got {len(pages)}"
        )
    return pages


def style_keys(runs_xml: str) -> set[tuple[str, str, str]]:
    """The distinct (size, family, colour) triples a document declares.

    Read with a regular expression rather than an XML parser on purpose. Poppler
    emits markup that is not well-formed -- unescaped ampersands inside font
    names, unbalanced inline tags inside runs -- and repairing that belongs to
    the segmenter that consumes the runs, not to the stage that counts them.
    """
    keys = set()
    for spec in _FONTSPEC.findall(runs_xml):
        attributes = dict(_XML_ATTRIBUTE.findall(spec))
        keys.add((
            attributes.get("size", ""),
            _SUBSET_TAG.sub("", attributes.get("family", "")),
            attributes.get("color", ""),
        ))
    return keys


def check_text_layer(page_text: str, runs_xml: str) -> None:
    """Fail a PDF whose text layer cannot carry the pipeline.

    Stage 1 requires a source without a usable text layer to fail explicitly
    rather than proceed with empty pages. **Empty is not the only unusable.**
    Curse of Strahd carries 779 KB of OCR text across 258 pages and segments to
    nothing, because its OCR engine declared one synthetic face per recognised
    fragment: 12,151 fonts named ``Times New Roman-271``, ``-272``, and a
    slightly different near-black per fragment. Every style then falls below the
    noise floor, none is accepted as a heading, and the run ends with zero units
    and exit 0. Silence is the actual defect.

    The ratio of runs to distinct styles measures that directly. Style-based
    segmentation assumes a typesetter chose a small number of styles
    deliberately; an OCR engine chooses one per fragment, accidentally.

    **This does not catch a damaged text layer.** The Lost City scores 190 runs
    per style -- a clean font table -- while its prose arrives as
    ``C e ntip e d e , G ia nt``. That is a different defect with a different
    measure, and it is still deferred.
    """
    if not page_text.strip():
        raise ExtractorError(
            "PDF has no text layer: pdftotext returned no characters. "
            "A scanned source needs OCR or the image path, not this pipeline."
        )
    runs = len(_TEXT_RUN.findall(runs_xml))
    styles = len(style_keys(runs_xml))
    if runs < TEXT_LAYER_MIN_RUNS or not styles:
        return
    ratio = runs / styles
    if ratio < TEXT_LAYER_MIN_RUNS_PER_STYLE:
        raise ExtractorError(
            "PDF text layer is unusable: "
            f"{runs} text runs declare {styles} distinct styles "
            f"({ratio:.1f} runs per style, minimum "
            f"{TEXT_LAYER_MIN_RUNS_PER_STYLE:.0f}). "
            "A font table this fragmented is OCR noise rather than typography, "
            "and segmentation would silently yield nothing. "
            "This source needs OCR or the image path."
        )


def _check_replaceable_input(input_dir: Path, slug: str) -> None:
    if not input_dir.exists():
        return
    if not input_dir.is_dir():
        raise ExtractorError(
            f"module input path is not a directory: {input_dir}"
        )
    if not any(input_dir.iterdir()):
        return
    source_path = input_dir / "source.json"
    if not source_path.is_file():
        raise ExtractorError(
            f"refusing to replace unrecognized module input directory: {input_dir}"
        )
    from .util import load_json

    existing = load_json(source_path)
    if not isinstance(existing, dict) or existing.get("slug") != slug:
        found = existing.get("slug") if isinstance(existing, dict) else None
        raise ExtractorError(
            f"module-input belongs to slug {found!r}, not {slug!r}"
        )


def prepare(
    pdf: Path,
    *,
    slug: str,
    title: str | None,
    input_dir: Path,
    exchange_dir: Path,
    cache_dir: Path,
) -> Path:
    """Replace the active workspace for ``slug`` after successful preparation."""
    if not SAFE_SLUG.fullmatch(slug):
        raise ExtractorError("slug must contain lowercase letters, digits, and hyphens")
    pdf = pdf.resolve()
    if not pdf.is_file():
        raise ExtractorError(f"PDF does not exist: {pdf}")
    missing = [tool for tool in POPLER_TOOLS if shutil.which(tool) is None]
    if missing:
        raise ExtractorError("missing required Poppler tools: " + ", ".join(missing))

    input_dir = input_dir.resolve()
    exchange_dir = exchange_dir.resolve()
    cache_dir = cache_dir.resolve()
    _check_replaceable_input(input_dir, slug)

    digest = sha256_file(pdf)
    info = _pdf_info(pdf)
    resolved_title = (
        title.strip()
        if isinstance(title, str) and title.strip()
        else info["pdf_title"].strip() or readable_stem(pdf)
    )
    if not resolved_title:
        raise ExtractorError(
            "could not infer a title from the PDF; provide --title"
        )
    source = {
        "slug": slug,
        "filename": pdf.name,
        "title": resolved_title,
        "pdf_title": info["pdf_title"],
        "pdf_pages": info["pdf_pages"],
        "sha256": digest,
    }

    staging_parent = cache_dir.parent
    staging_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".module-extractor-prepare-", dir=staging_parent
    ) as temporary:
        stage = Path(temporary)
        cache_stage = stage / "cache"
        input_stage = stage / "input"
        exchange_stage = stage / "exchange"
        cache_stage.mkdir()
        input_stage.mkdir()
        exchange_stage.mkdir()

        shutil.copyfile(pdf, cache_stage / "source.pdf")
        text_dir = cache_stage / "text"
        pages_dir = text_dir / "pages"
        pages_dir.mkdir(parents=True)
        layout = text_dir / "layout.txt"
        _run(["pdftotext", "-layout", str(pdf), str(layout)])
        layout_text = layout.read_text(encoding="utf-8", errors="replace")
        page_texts = _split_pages(layout_text, info["pdf_pages"])
        for page, page_text in enumerate(page_texts, 1):
            (pages_dir / f"page-{page:04d}.txt").write_text(
                page_text, encoding="utf-8", newline="\n"
            )

        # Written verbatim, for the whole document rather than per page. The
        # output is not well-formed XML -- Poppler leaves bare ampersands in
        # font names and unbalanced inline tags inside runs -- so splitting it
        # would need the very repairs that belong to the segmenter. The cache
        # should hold what Poppler said, not a partial reading of it.
        runs_xml = _run(
            ["pdftohtml", *PDFTOHTML_ARGUMENTS, str(pdf)]
        ).stdout
        (text_dir / "runs.xml").write_text(
            runs_xml, encoding="utf-8", newline="\n"
        )
        # Before the page renders, so an unusable source fails in seconds.
        check_text_layer(layout_text, runs_xml)

        thumbnails = cache_stage / "thumbnails"
        thumbnails.mkdir()
        _run(
            [
                "pdftoppm",
                "-png",
                "-r",
                "45",
                "-f",
                "1",
                "-l",
                str(info["pdf_pages"]),
                str(pdf),
                str(thumbnails / "page"),
            ]
        )
        rendered = sorted(thumbnails.glob("page-*.png"))
        if len(rendered) != info["pdf_pages"]:
            raise ExtractorError("pdftoppm did not render every physical page")
        for page, path in enumerate(rendered, 1):
            path.rename(thumbnails / f"page-{page:04d}.png")

        routing_entries: dict[str, bytes | Path] = {
            "README.md": routing_pack_readme(source).encode("utf-8"),
            "source.json": canonical_json_bytes(source),
            "prompt.md": routing_prompt(source).encode("utf-8"),
            "response-template.json": canonical_json_bytes(
                routing_template(source)
            ),
        }
        for thumbnail in sorted(thumbnails.glob("page-*.png")):
            routing_entries[f"thumbnails/{thumbnail.name}"] = thumbnail
        routing_archive = exchange_stage / "routing.zip"
        deterministic_zip(routing_archive, routing_entries)

        prepared = {
            "schema": "module-preparation/v1",
            "source": source,
            "asset_root": ".",
            "routing_pack": "routing.zip",
            "routing_pack_sha256": sha256_file(routing_archive),
        }
        write_json(cache_stage / "prepared.json", prepared)
        write_json(cache_stage / "source.json", source)
        write_json(input_stage / "source.json", source)
        write_json(
            exchange_stage / ".module-extractor.json",
            {
                "schema": "module-exchange/v1",
                "slug": slug,
                "source_sha256": digest,
            },
        )

        atomic_publish(cache_stage, cache_dir, replace=cache_dir.exists())
        atomic_publish(input_stage, input_dir, replace=input_dir.exists())
        atomic_publish(
            exchange_stage, exchange_dir, replace=exchange_dir.exists()
        )
    return exchange_dir
