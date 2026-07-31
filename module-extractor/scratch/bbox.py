#!/usr/bin/env python3
"""T0.1 -- word-level page geometry from ``pdftotext -bbox-layout``.

Stage 2 of the target dataflow segments on typographic signal: heading size,
column structure, stat-block and table layout. ``pdftotext -layout`` discards
all of it -- font, weight and size are gone, and on a two-column source the
columns are interleaved onto shared lines.

``pdftotext -bbox-layout`` keeps the geometry. It emits XHTML with a bounding
box per word, which is enough to recover both signals we need:

- **size**, as ``height`` -- Poppler exposes no font name or weight, and glyph
  height turns out to be sufficient to separate a document's structural tiers;
- **columns**, as ``x`` -- but only at word level. Poppler groups text from
  facing columns into single ``<line>`` elements, so splitting on line geometry
  merges the two columns into nonsense. See ``T0.3``.

Standard library only: Poppler is invoked as a subprocess, exactly as
``module_extractor.preparation`` already does.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET


XHTML = "{http://www.w3.org/1999/xhtml}"

# Stable per architecture-new-implementation.md, "Environment".
SOURCES = (
    Path("/mnt/data/RPG/Module - Lair of the Lamb.pdf"),
    Path("/mnt/data/RPG/Module - Winters Daughter.pdf"),
    Path("/mnt/data/RPG/Module - Falkrest_Abbey_1.1.pdf"),
    Path("/mnt/data/RPG/[M] 66.5 Doom of the Savage Kings.pdf"),
    Path("/mnt/data/RPG/TSR B4 - The Lost City 1982.pdf"),
)


class BboxError(RuntimeError):
    """Extraction failed loudly rather than returning empty pages."""


@dataclass(frozen=True)
class Word:
    """One word and where it sits on the page, in PDF points."""

    x: float
    y: float
    width: float
    height: float
    text: str

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height


@dataclass(frozen=True)
class Page:
    number: int  # 1-based physical page
    width: float
    height: float
    words: tuple[Word, ...]

    @property
    def has_text(self) -> bool:
        return any(word.text.strip() for word in self.words)


@dataclass(frozen=True)
class Document:
    pdf: Path
    pages: tuple[Page, ...]
    control_chars_removed: int


# XML 1.0 forbids the C0 controls except tab, newline and carriage return.
# Poppler copies text straight out of the PDF without escaping them, so a source
# containing e.g. a backspace produces output that is not well-formed XML.
# Winter's Daughter has 29 of them.
_ILLEGAL_XML = {chr(code) for code in range(0x20)} - {"\t", "\n", "\r"}


def _sanitize(xml_text: str) -> tuple[str, int]:
    """Drop XML-illegal control characters, and report how many.

    This is transport cleanup, not content repair: the characters are an
    artefact of Poppler's serialization and carry no textual meaning. The count
    is surfaced rather than swallowed -- a source with a large number of them is
    saying something about itself, and the caller should see it.
    """
    removed = sum(xml_text.count(char) for char in _ILLEGAL_XML)
    if not removed:
        return xml_text, 0
    table = {ord(char): None for char in _ILLEGAL_XML}
    return xml_text.translate(table), removed


def _run_poppler(pdf: Path) -> str:
    if shutil.which("pdftotext") is None:
        raise BboxError("pdftotext is not on PATH; install Poppler")
    if not pdf.is_file():
        raise BboxError(f"PDF does not exist: {pdf}")
    result = subprocess.run(
        ["pdftotext", "-bbox-layout", str(pdf), "-"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode:
        detail = result.stderr.strip() or "no diagnostic"
        raise BboxError(f"pdftotext failed on {pdf.name}: {detail}")
    if not result.stdout.strip():
        raise BboxError(f"pdftotext returned nothing for {pdf.name}")
    return result.stdout


def _float(element: ET.Element, name: str) -> float:
    raw = element.get(name)
    if raw is None:
        raise BboxError(f"<{element.tag}> is missing {name}")
    try:
        return float(raw)
    except ValueError as exc:
        raise BboxError(f"{name}={raw!r} is not a number") from exc


def extract_document(pdf: Path) -> Document:
    """Parse one PDF into pages of positioned words."""
    xml_text, removed = _sanitize(_run_poppler(pdf))
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise BboxError(f"could not parse pdftotext output for {pdf.name}: {exc}") from exc

    pages: list[Page] = []
    for number, node in enumerate(root.iter(f"{XHTML}page"), 1):
        words = []
        for word in node.iter(f"{XHTML}word"):
            text = word.text or ""
            if not text.strip():
                continue
            left, top = _float(word, "xMin"), _float(word, "yMin")
            words.append(
                Word(
                    x=left,
                    y=top,
                    width=_float(word, "xMax") - left,
                    height=_float(word, "yMax") - top,
                    text=text,
                )
            )
        pages.append(
            Page(
                number=number,
                width=_float(node, "width"),
                height=_float(node, "height"),
                words=tuple(words),
            )
        )
    if not pages:
        raise BboxError(f"no pages found in {pdf.name}")
    return Document(pdf=pdf, pages=tuple(pages), control_chars_removed=removed)


def extract_pages(pdf: Path) -> list[Page]:
    """Return one :class:`Page` per physical page, in document order."""
    return list(extract_document(pdf).pages)


def summarize(pdf: Path) -> dict[str, object]:
    """Per-document counts, and which pages carry no text layer at all."""
    document = extract_document(pdf)
    pages = document.pages
    empty = [page.number for page in pages if not page.has_text]
    words = sum(len(page.words) for page in pages)
    return {
        "name": pdf.name,
        "pages": len(pages),
        "words": words,
        "words_per_page": round(words / len(pages), 1),
        "empty_pages": empty,
        "control_chars_removed": document.control_chars_removed,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pdf", nargs="*", type=Path, help="PDFs to inspect")
    parser.add_argument(
        "--all", action="store_true", help="inspect every source in SOURCES"
    )
    parser.add_argument(
        "--page", type=int, help="dump one page's words instead of a summary"
    )
    args = parser.parse_args(argv)

    targets = list(SOURCES) if args.all else args.pdf
    if not targets:
        parser.error("give at least one PDF, or --all")

    if args.page is not None:
        for pdf in targets:
            pages = extract_pages(pdf)
            if not 1 <= args.page <= len(pages):
                raise SystemExit(f"{pdf.name} has no page {args.page}")
            page = pages[args.page - 1]
            print(f"# {pdf.name} page {page.number} "
                  f"({page.width:.0f}x{page.height:.0f}pt, {len(page.words)} words)")
            for word in page.words:
                print(f"{word.x:8.2f} {word.y:8.2f} {word.height:5.2f}  {word.text}")
        return 0

    failures = 0
    header = f"{'source':<40} {'pages':>5} {'words':>7} {'/page':>7} {'ctrl':>5}  empty pages"
    print(header)
    print("-" * len(header))
    for pdf in targets:
        try:
            row = summarize(pdf)
        except BboxError as exc:
            print(f"{pdf.name[:40]:<40} {'ERROR':>5}  {exc}")
            failures += 1
            continue
        empty = row["empty_pages"]
        note = "-" if not empty else f"{len(empty)} {empty[:8]}"
        print(f"{str(row['name'])[:40]:<40} {row['pages']:>5} {row['words']:>7} "
              f"{row['words_per_page']:>7} {row['control_chars_removed']:>5}  {note}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
