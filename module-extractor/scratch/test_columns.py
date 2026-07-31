#!/usr/bin/env python3
"""Tests for T0.3 (columns) and T0.2 (tiers). Synthetic pages, no PDF."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pdfhtml import Font, Page, Run  # noqa: E402
from columns import (Line, _split_run_in_heading, body_run_style,  # noqa: E402
                     find_gutter, page_lines, run_style)
from tiers import body_style, style_table  # noqa: E402

BODY_FONT = Font(font_id=0, size=12.0, family="Body", color="#000000")


def word(text, x, y, h=12.0, w=None, font=BODY_FONT, bold=False):
    return Run(page=1, x=x, y=y, width=w if w is not None else len(text) * 5.0,
               height=h, text=text, font=font, bold=bold, italic=False)


def two_column_page(rows=14, spanning=0):
    """Left column at x=50, right at x=350, gutter around x=300."""
    words = []
    for i in range(rows):
        y = 100.0 + i * 14
        words.append(word("leftcolumntext", 50.0, y, w=200.0))
        words.append(word("rightcolumntext", 350.0, y, w=200.0))
    for i in range(spanning):
        words.append(word("BANNER HEADING ACROSS", 50.0, 60.0 + i * 20, h=20.0, w=500.0))
    return Page(number=1, width=612.0, height=792.0, words=tuple(words))


class GutterTests(unittest.TestCase):
    def test_finds_the_gutter_between_two_columns(self) -> None:
        gutter = find_gutter(two_column_page())
        self.assertIsNotNone(gutter)
        self.assertTrue(250 < gutter < 350, gutter)

    def test_survives_a_full_width_heading_crossing_the_gutter(self) -> None:
        """The reason detection is density-based rather than emptiness-based."""
        self.assertIsNotNone(find_gutter(two_column_page(spanning=2)))

    def test_single_column_page_has_no_gutter(self) -> None:
        words = tuple(word("bodytext", 50.0, 100.0 + i * 14, w=500.0) for i in range(30))
        page = Page(number=1, width=612.0, height=792.0, words=words)
        self.assertIsNone(find_gutter(page))

    def test_a_nearly_empty_page_is_not_guessed_at(self) -> None:
        page = Page(number=1, width=612.0, height=792.0,
                    words=(word("a", 50.0, 100.0), word("b", 400.0, 100.0)))
        self.assertIsNone(find_gutter(page))


class LineTests(unittest.TestCase):
    def test_columns_are_not_fused_into_one_line(self) -> None:
        """The T0.3 regression: banding by y alone merges facing columns."""
        lines = page_lines(two_column_page())
        for line in lines:
            self.assertNotIn("rightcolumntext leftcolumntext", line.text)
            self.assertFalse(
                "leftcolumntext" in line.text and "rightcolumntext" in line.text,
                f"columns fused: {line.text!r}",
            )

    def test_reading_order_is_spanning_then_left_then_right(self) -> None:
        lines = page_lines(two_column_page(rows=12, spanning=1))
        self.assertEqual([line.column for line in lines], [-1] + [0] * 12 + [1] * 12)

    def test_a_word_crossing_the_gutter_is_marked_spanning(self) -> None:
        lines = page_lines(two_column_page(rows=12, spanning=1))
        self.assertEqual(lines[0].column, -1)
        self.assertIn("BANNER", lines[0].text)

    def test_line_style_is_the_dominant_runs_style(self) -> None:
        """A dropped capital must not redefine the line it opens."""
        drop = Font(font_id=1, size=72.0, family="Initials", color="#000000")
        words = (word("A", 50.0, 100.0, h=72.0, w=40.0, font=drop),
                 word("good portion of the adventure", 95.0, 100.0, w=200.0))
        page = Page(number=1, width=612.0, height=792.0, words=words)
        self.assertEqual(page_lines(page)[0].size, 12.0)


class RunInHeadingTests(unittest.TestCase):
    """Doom and Lost City set headings inline with the body text that follows."""

    HEAD = Font(font_id=2, size=12.0, family="CooperBlack", color="#000000")

    def _row(self):
        return [word("Area A-4 - Chapel of Justicia:", 50.0, 100.0, font=self.HEAD,
                     bold=True, w=120.0),
                word("The chapel is a low, vaulted hall", 175.0, 100.0, w=200.0)]

    def test_a_run_in_heading_is_split_from_its_body(self) -> None:
        parts = _split_run_in_heading(self._row(), run_style(self._row()[1]))
        self.assertEqual(len(parts), 2)
        self.assertIn("Chapel of Justicia", parts[0][0].text)
        self.assertIn("vaulted hall", parts[1][0].text)

    def test_a_row_that_opens_in_body_style_is_not_split(self) -> None:
        row = self._row()[::-1]
        row = [row[0], row[1]]
        self.assertEqual(len(_split_run_in_heading(row, run_style(row[0]))), 1)

    def test_a_wholly_heading_row_is_not_split(self) -> None:
        row = [word("IntroductIon", 50.0, 100.0, font=self.HEAD, bold=True)]
        self.assertEqual(len(_split_run_in_heading(row, run_style(row[0]))), 1)

    def test_splitting_gives_the_heading_part_its_own_style(self) -> None:
        page = Page(number=1, width=612.0, height=792.0, words=tuple(self._row()))
        lines = page_lines(page, body=run_style(self._row()[1]))
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0].family, "CooperBlack")
        self.assertTrue(lines[0].bold)
        self.assertFalse(lines[1].bold)

    def test_a_dropped_capital_is_not_a_run_in_heading(self) -> None:
        """One oversized glyph opening a paragraph matches the shape exactly."""
        drop = Font(font_id=3, size=72.0, family="Initials", color="#000000")
        row = [word("A", 50.0, 100.0, h=72.0, w=40.0, font=drop),
               word("good portion of the adventure", 95.0, 100.0, w=200.0)]
        self.assertEqual(len(_split_run_in_heading(row, run_style(row[1]))), 1)

    def test_body_style_is_the_most_characters_not_the_most_runs(self) -> None:
        words = [word("H", 50.0, float(i), font=self.HEAD) for i in range(9)]
        words.append(word("a" * 200, 50.0, 100.0, w=300.0))
        page = Page(number=1, width=612.0, height=792.0, words=tuple(words))
        self.assertEqual(body_run_style([page]), run_style(words[-1]))


class StyleTests(unittest.TestCase):
    def _lines(self, spec):
        return [Line(page=1, column=0, x=50.0, y=float(i), height=s, text=t,
                     size=s, family=f, bold=b, color=c)
                for i, (s, f, b, c, t) in enumerate(spec)]

    def test_body_is_the_style_carrying_the_most_words(self) -> None:
        lines = self._lines(
            [(56.0, "Display", False, "#000000", "Title")]
            + [(12.0, "Body", False, "#000000", "many words of body text here")] * 40
        )
        self.assertEqual(body_style(style_table(lines, floor=0.0)).size, 12.0)

    def test_body_is_not_assumed_to_be_the_smallest(self) -> None:
        """The Lost City sets headings at or below its body size."""
        lines = self._lines(
            [(14.0, "Times", True, "#000000", "SECTION")] * 3
            + [(14.0, "Times", False, "#000000", "running body text here")] * 40
        )
        body = body_style(style_table(lines, floor=0.0))
        self.assertFalse(body.bold)

    def test_styles_differing_only_in_weight_stay_apart(self) -> None:
        """No tolerance to tune: styles are discrete."""
        lines = self._lines(
            [(14.0, "Times", True, "#000000", "SECTION")] * 5
            + [(14.0, "Times", False, "#000000", "body")] * 5
        )
        self.assertEqual(len(style_table(lines, floor=0.0)), 2)

    def test_rare_styles_are_dropped_as_noise(self) -> None:
        lines = self._lines(
            [(99.0, "Stray", False, "#000000", "stray glyph")]
            + [(12.0, "Body", False, "#000000", "body")] * 900
        )
        self.assertEqual([g.size for g in style_table(lines)], [12.0])


if __name__ == "__main__":
    unittest.main()
