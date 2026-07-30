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


POPLER_TOOLS = ("pdfinfo", "pdftotext", "pdftoppm")


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
        page_texts = _split_pages(
            layout.read_text(encoding="utf-8", errors="replace"),
            info["pdf_pages"],
        )
        for page, page_text in enumerate(page_texts, 1):
            (pages_dir / f"page-{page:04d}.txt").write_text(
                page_text, encoding="utf-8", newline="\n"
            )

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
