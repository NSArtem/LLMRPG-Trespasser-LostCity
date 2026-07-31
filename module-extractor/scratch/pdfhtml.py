#!/usr/bin/env python3
"""T0.1 (revised) -- typed text runs from ``pdftohtml -xml``.

**This replaces the ``pdftotext -bbox-layout`` source in bbox.py.** That tool
gives a box per word and nothing else, so the only typographic signal available
was glyph height -- a lossy proxy for point size, with family, weight and colour
discarded entirely. Two of the five sources could not be segmented with it.

``pdftohtml`` is the same Poppler package, already installed, and emits the
signal the segmenter actually needs:

    <fontspec id="0" size="18" family="CIDFont+F10" color="#3333ff"/>
    <text top="504" left="65" width="182" height="22" font="0">24 CRUSH HALLWAY</text>
    <text top="52"  left="93" width="311" height="23" font="1"><b>roleplAyIng the non-</b></text>

What that recovers, per source:

- *Lair of the Lamb* -- keyed areas are size 18 **blue**, subsection headings are
  size 18 **black**. Glyph height cannot tell them apart; colour can, and that is
  what makes absorbing subsections into their keyed area mechanical.
- *Doom of the Savage Kings* -- headings are a distinct family (Duvall) at size
  21 and **bold** against BookAntiqua 14 body. Under glyph height 96.8% of its
  lines looked identical.
- *The Lost City* -- real point sizes 20/18/15/14 rather than overlapping
  rendered heights.

A ``<text>`` element is a **run**: contiguous characters sharing one font. Runs
split mid-line whenever the font changes, and never span a column, so they are a
strictly better input than words. Runs are geometry-compatible with ``bbox.Word``
(``x``, ``y``, ``width``, ``height``, ``text``, ``right``), so the column, tier
and unit layers consume them unchanged.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import html
from pathlib import Path
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bbox import BboxError, SOURCES  # noqa: E402


_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


@dataclass(frozen=True)
class Font:
    font_id: int
    size: float
    family: str
    color: str

    @property
    def is_black(self) -> bool:
        return self.color.lower() in {"#000000", "#010101", "#000"}


@dataclass(frozen=True)
class Run:
    """One contiguous same-font span. Geometry-compatible with bbox.Word."""

    page: int
    x: float
    y: float
    width: float
    height: float
    text: str
    font: Font
    bold: bool
    italic: bool

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def size(self) -> float:
        return self.font.size

    @property
    def color(self) -> str:
        return self.font.color


@dataclass(frozen=True)
class Page:
    number: int
    width: float
    height: float
    words: tuple[Run, ...]  # named `words` so the column layer needs no change

    @property
    def has_text(self) -> bool:
        return any(run.text.strip() for run in self.words)


@dataclass(frozen=True)
class Document:
    pdf: Path
    pages: tuple[Page, ...]
    fonts: dict[int, Font]


def _run_poppler(pdf: Path) -> str:
    if shutil.which("pdftohtml") is None:
        raise BboxError("pdftohtml is not on PATH; install Poppler")
    if not pdf.is_file():
        raise BboxError(f"PDF does not exist: {pdf}")
    result = subprocess.run(
        # -i drops images: we want text geometry, not extracted artwork on disk.
        ["pdftohtml", "-xml", "-i", "-hidden", "-stdout", str(pdf)],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode:
        detail = result.stderr.strip() or "no diagnostic"
        raise BboxError(f"pdftohtml failed on {pdf.name}: {detail}")
    if not result.stdout.strip():
        raise BboxError(f"pdftohtml returned nothing for {pdf.name}")
    return result.stdout


# XML 1.0 forbids the C0 controls except tab, newline and carriage return, and
# Poppler copies them out of the PDF unescaped. Same defect as in bbox.py.
_ILLEGAL_XML = {chr(code) for code in range(0x20)} - {"\t", "\n", "\r"}


def _sanitize(xml_text: str) -> tuple[str, int]:
    removed = sum(xml_text.count(char) for char in _ILLEGAL_XML)
    if not removed:
        return xml_text, 0
    return xml_text.translate({ord(c): None for c in _ILLEGAL_XML}), removed


# Poppler's inline markup is not well-formed. Where a link overlaps a bold run
# it emits `<a href="...">Bandits</b> can </a>` -- a closing tag with no opener
# inside it. Falkrest Abbey has 637 such spans and fails ET outright, even
# though <b> and <i> are globally balanced 564/564 and 92/92.
#
# So the inline markup is flattened textually before ET sees it: emphasis is
# recorded as attributes and every tag inside a <text> element is removed. The
# outer structure -- pages, fontspecs, positions -- is still parsed properly.
_TEXT_ELEMENT = re.compile(r"<text\b([^>]*)>(.*?)</text>", re.DOTALL)
_ANY_TAG = re.compile(r"<[^>]*>")


def _escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _normalize_runs(xml_text: str) -> str:
    def rewrite(match: re.Match[str]) -> str:
        attributes, inner = match.group(1), match.group(2)
        bold = "1" if re.search(r"<b\b", inner, re.IGNORECASE) else "0"
        italic = "1" if re.search(r"<i\b", inner, re.IGNORECASE) else "0"
        plain = html.unescape(_ANY_TAG.sub("", inner))
        return (f"<text{attributes} bold=\"{bold}\" italic=\"{italic}\">"
                f"{_escape(plain)}</text>")

    return _TEXT_ELEMENT.sub(rewrite, xml_text)


def _number(element: ET.Element, name: str, default: float | None = None) -> float:
    raw = element.get(name)
    if raw is None:
        if default is not None:
            return default
        raise BboxError(f"<{element.tag}> is missing {name}")
    try:
        return float(raw)
    except ValueError as exc:
        raise BboxError(f"{name}={raw!r} is not a number") from exc


def extract_document(pdf: Path) -> Document:
    xml_text, _ = _sanitize(_run_poppler(pdf))
    xml_text = _normalize_runs(xml_text)
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise BboxError(f"could not parse pdftohtml output for {pdf.name}: {exc}") from exc

    fonts: dict[int, Font] = {}
    pages: list[Page] = []
    for node in root.iter("page"):
        number = int(_number(node, "number"))
        for spec in node.iter("fontspec"):
            identifier = int(_number(spec, "id"))
            color = spec.get("color", "#000000")
            fonts[identifier] = Font(
                font_id=identifier,
                size=_number(spec, "size"),
                family=spec.get("family", ""),
                color=color if _HEX.match(color) else "#000000",
            )
        runs = []
        for element in node.iter("text"):
            text = element.text or ""
            if not text.strip():
                continue
            bold = element.get("bold") == "1"
            italic = element.get("italic") == "1"
            font = fonts.get(int(_number(element, "font", -1)))
            if font is None:
                font = Font(font_id=-1, size=_number(element, "height", 0.0),
                            family="", color="#000000")
            runs.append(
                Run(
                    page=number,
                    x=_number(element, "left"),
                    y=_number(element, "top"),
                    width=_number(element, "width"),
                    height=_number(element, "height"),
                    text=text,
                    font=font,
                    bold=bold,
                    italic=italic,
                )
            )
        pages.append(
            Page(
                number=number,
                width=_number(node, "width"),
                height=_number(node, "height"),
                words=tuple(runs),
            )
        )
    if not pages:
        raise BboxError(f"no pages found in {pdf.name}")
    return Document(pdf=pdf, pages=tuple(pages), fonts=fonts)


def summarize(pdf: Path) -> dict[str, object]:
    document = extract_document(pdf)
    runs = [run for page in document.pages for run in page.words]
    sizes = sorted({run.size for run in runs})
    colors = sorted({run.color for run in runs})
    return {
        "name": pdf.name,
        "pages": len(document.pages),
        "runs": len(runs),
        "bold": sum(1 for run in runs if run.bold),
        "sizes": sizes,
        "colors": colors,
        "families": sorted({run.font.family.split("+")[-1] for run in runs}),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pdf", nargs="*", type=Path)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--page", type=int)
    args = parser.parse_args(argv)
    targets = list(SOURCES) if args.all else args.pdf
    if not targets:
        parser.error("give at least one PDF, or --all")

    for pdf in targets:
        try:
            if args.page is not None:
                page = extract_document(pdf).pages[args.page - 1]
                print(f"# {pdf.name} p{page.number}")
                for run in page.words:
                    flag = "B" if run.bold else " "
                    print(f"  x={run.x:6.1f} y={run.y:6.1f} sz={run.size:5.1f} "
                          f"{run.color} {flag} {run.text[:64]}")
                continue
            row = summarize(pdf)
            print(f"\n{row['name']}")
            print(f"  pages={row['pages']} runs={row['runs']} bold={row['bold']}")
            print(f"  sizes={row['sizes']}")
            print(f"  colors={row['colors']}")
            print(f"  families={row['families'][:6]}")
        except BboxError as exc:
            print(f"{pdf.name}: ERROR {exc}")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
