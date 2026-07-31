#!/usr/bin/env python3
"""Tests for the revised T0.1. Synthesised pdftohtml output, no PDF."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bbox import BboxError  # noqa: E402
import pdfhtml  # noqa: E402
from pdfhtml import _normalize_runs, extract_document  # noqa: E402


def doc(*pages: str) -> str:
    return ('<?xml version="1.0" encoding="UTF-8"?><pdf2xml producer="poppler">'
            + "".join(pages) + "</pdf2xml>")


def page(body: str, number: int = 1) -> str:
    return (f'<page number="{number}" height="1174" width="904">'
            '<fontspec id="0" size="16" family="CIDFont+F1" color="#000000"/>'
            '<fontspec id="1" size="18" family="CIDFont+F10" color="#3333ff"/>'
            f"{body}</page>")


def text(content: str, font: int = 0, left: int = 65, top: int = 100) -> str:
    return (f'<text top="{top}" left="{left}" width="182" height="22" '
            f'font="{font}">{content}</text>')


class NormalizeTests(unittest.TestCase):
    def test_mismatched_inline_tags_are_flattened(self) -> None:
        """Falkrest: <a href=...>Bandits</b> can </a> -- 637 such spans."""
        raw = doc(page(text('<a href="x.html#36">Bandits</b> can </a>')))
        normalized = _normalize_runs(raw)
        self.assertNotIn("</b>", normalized)
        self.assertIn("Bandits can", normalized)

    def test_bold_becomes_an_attribute(self) -> None:
        normalized = _normalize_runs(doc(page(text("<b>IntroductIon</b>"))))
        self.assertIn('bold="1"', normalized)
        self.assertIn("IntroductIon", normalized)

    def test_plain_runs_are_marked_not_bold(self) -> None:
        self.assertIn('bold="0"', _normalize_runs(doc(page(text("body text")))))

    def test_entities_survive_one_round_trip(self) -> None:
        normalized = _normalize_runs(doc(page(text("Fish &amp; Chips"))))
        self.assertIn("Fish &amp; Chips", normalized)

    def test_a_bare_ampersand_in_text_is_escaped(self) -> None:
        normalized = _normalize_runs(doc(page(text("<b>Dungeons &amp; Dragons</b>"))))
        self.assertIn("&amp;", normalized)
        self.assertNotIn("& D", normalized)


class ExtractionTests(unittest.TestCase):
    def _document(self, xml: str):
        self.addCleanup(setattr, pdfhtml, "_run_poppler", pdfhtml._run_poppler)
        pdfhtml._run_poppler = lambda pdf: xml
        return extract_document(Path("synthetic.pdf"))

    def test_font_metadata_reaches_the_run(self) -> None:
        """The whole point of the switch: size, family and colour survive."""
        run = self._document(doc(page(text("1 BOWLS", font=1)))).pages[0].words[0]
        self.assertEqual(run.size, 18.0)
        self.assertEqual(run.color, "#3333ff")
        self.assertEqual(run.font.family, "CIDFont+F10")
        self.assertFalse(run.font.is_black)

    def test_keyed_area_and_subsection_are_distinguishable_by_colour(self) -> None:
        """Both are 18pt in Lair; only colour separates them."""
        document = self._document(doc(page(
            text("1 BOWLS", font=1) + text("Crossing the Hallway", font=0, top=200)
        )))
        keyed, subsection = document.pages[0].words
        self.assertNotEqual(keyed.color, subsection.color)

    def test_bold_is_carried_through_normalization(self) -> None:
        run = self._document(doc(page(text("<b>IntroductIon</b>")))).pages[0].words[0]
        self.assertTrue(run.bold)
        self.assertEqual(run.text.strip(), "IntroductIon")

    def test_runs_are_geometry_compatible_with_words(self) -> None:
        run = self._document(doc(page(text("x")))).pages[0].words[0]
        for attribute in ("x", "y", "width", "height", "text", "right"):
            self.assertTrue(hasattr(run, attribute), attribute)
        self.assertEqual(run.right, run.x + run.width)

    def test_blank_runs_are_dropped(self) -> None:
        self.assertEqual(self._document(doc(page(text("   ")))).pages[0].words, ())

    def test_control_characters_do_not_break_the_parse(self) -> None:
        run = self._document(doc(page(text("Introduction\x083")))).pages[0].words[0]
        self.assertEqual(run.text, "Introduction3")

    def test_page_numbers_come_from_the_document(self) -> None:
        document = self._document(doc(page(text("a"), 1), page(text("b"), 7)))
        self.assertEqual([p.number for p in document.pages], [1, 7])

    def test_an_empty_document_fails_loudly(self) -> None:
        with self.assertRaises(BboxError):
            self._document(doc())

    def test_unknown_font_id_falls_back_rather_than_crashing(self) -> None:
        run = self._document(doc(page(text("x", font=99)))).pages[0].words[0]
        self.assertEqual(run.font.font_id, -1)


if __name__ == "__main__":
    unittest.main()
