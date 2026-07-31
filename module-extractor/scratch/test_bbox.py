#!/usr/bin/env python3
"""Tests for T0.1. No PDF required -- Poppler output is synthesised."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bbox import BboxError, Word, _sanitize, extract_document  # noqa: E402
import bbox  # noqa: E402


def poppler_xml(*pages: str) -> str:
    body = "".join(pages)
    return (
        '<html xmlns="http://www.w3.org/1999/xhtml"><body><doc>'
        f"{body}"
        "</doc></body></html>"
    )


def page(words: str, width: str = "612", height: str = "792") -> str:
    return f'<page width="{width}" height="{height}"><flow><block>{words}</block></flow></page>'


def word(text: str, x=10.0, y=20.0, w=30.0, h=12.0) -> str:
    return (
        f'<line xMin="{x}" yMin="{y}" xMax="{x + w}" yMax="{y + h}">'
        f'<word xMin="{x}" yMin="{y}" xMax="{x + w}" yMax="{y + h}">{text}</word>'
        "</line>"
    )


class SanitizeTests(unittest.TestCase):
    def test_removes_xml_illegal_controls_and_counts_them(self) -> None:
        cleaned, removed = _sanitize("Introduction\x083\x0b")
        self.assertEqual(cleaned, "Introduction3")
        self.assertEqual(removed, 2)

    def test_keeps_tab_newline_and_carriage_return(self) -> None:
        cleaned, removed = _sanitize("a\tb\nc\rd")
        self.assertEqual(cleaned, "a\tb\nc\rd")
        self.assertEqual(removed, 0)

    def test_clean_input_is_returned_unchanged(self) -> None:
        text = poppler_xml(page(word("Hirelings")))
        self.assertEqual(_sanitize(text), (text, 0))


class ExtractionTests(unittest.TestCase):
    def _document(self, xml: str):
        self.addCleanup(setattr, bbox, "_run_poppler", bbox._run_poppler)
        bbox._run_poppler = lambda pdf: xml
        return extract_document(Path("synthetic.pdf"))

    def test_word_geometry_is_derived_from_the_bounding_box(self) -> None:
        doc = self._document(poppler_xml(page(word("Crush", x=43.0, y=100.0, w=52.5, h=14.5))))
        self.assertEqual(len(doc.pages), 1)
        self.assertEqual(
            doc.pages[0].words,
            (Word(x=43.0, y=100.0, width=52.5, height=14.5, text="Crush"),),
        )

    def test_pages_are_numbered_from_one_in_document_order(self) -> None:
        doc = self._document(poppler_xml(page(word("a")), page(word("b"))))
        self.assertEqual([p.number for p in doc.pages], [1, 2])
        self.assertEqual([p.words[0].text for p in doc.pages], ["a", "b"])

    def test_blank_words_are_dropped_so_empty_pages_are_detectable(self) -> None:
        doc = self._document(poppler_xml(page(word("   "))))
        self.assertEqual(doc.pages[0].words, ())
        self.assertFalse(doc.pages[0].has_text)

    def test_control_characters_survive_as_a_reported_count(self) -> None:
        doc = self._document(poppler_xml(page(word("Introduction\x083"))))
        self.assertEqual(doc.control_chars_removed, 1)
        self.assertEqual(doc.pages[0].words[0].text, "Introduction3")

    def test_a_document_with_no_pages_fails_loudly(self) -> None:
        with self.assertRaises(BboxError):
            self._document(poppler_xml())

    def test_unparseable_output_fails_loudly(self) -> None:
        with self.assertRaises(BboxError):
            self._document("<html><page>")

    def test_a_missing_coordinate_fails_loudly(self) -> None:
        broken = poppler_xml(page('<line><word xMin="1" yMin="2" yMax="3">x</word></line>'))
        with self.assertRaises(BboxError):
            self._document(broken)


if __name__ == "__main__":
    unittest.main()
