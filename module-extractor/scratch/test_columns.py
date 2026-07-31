#!/usr/bin/env python3
"""Tests for T0.3 (columns) and T0.2 (tiers). Synthetic pages, no PDF."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bbox import Page, Word  # noqa: E402
from columns import find_gutter, page_lines  # noqa: E402
from tiers import cluster, tier_table, body_tier  # noqa: E402
from columns import Line  # noqa: E402


def word(text, x, y, h=12.0, w=None):
    return Word(x=x, y=y, width=w if w is not None else len(text) * 5.0, height=h, text=text)


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

    def test_line_height_is_the_dominant_word_height(self) -> None:
        words = (word("BIG", 50.0, 100.0, h=30.0, w=40.0),
                 word("heading", 95.0, 100.0, h=14.0, w=60.0),
                 word("words", 160.0, 100.0, h=14.0, w=60.0))
        page = Page(number=1, width=612.0, height=792.0, words=words)
        self.assertEqual(page_lines(page)[0].height, 14.0)


class TierTests(unittest.TestCase):
    def test_near_identical_heights_cluster_together(self) -> None:
        self.assertEqual(cluster([12.2, 12.2, 12.3]), [[12.2, 12.2, 12.3]])

    def test_distinct_sizes_stay_apart(self) -> None:
        self.assertEqual(len(cluster([12.2, 20.8, 56.1])), 3)

    def _lines(self, spec):
        return [Line(page=1, column=0, x=50.0, y=float(i), height=h, text=t)
                for i, (h, t) in enumerate(spec)]

    def test_body_is_the_tier_carrying_the_most_words(self) -> None:
        lines = self._lines([(56.1, "Title")] + [(12.2, "many words of body text here")] * 40)
        tiers = tier_table(lines, floor=0.0)
        self.assertEqual(body_tier(tiers).height, 12.2)

    def test_body_is_not_assumed_to_be_the_smallest(self) -> None:
        """The Lost City sets a heading smaller than its body text."""
        lines = self._lines([(8.6, "SECTION")] * 3 + [(9.1, "running body text here")] * 40)
        self.assertEqual(body_tier(tier_table(lines, floor=0.0)).height, 9.1)

    def test_rare_sizes_are_dropped_as_noise(self) -> None:
        lines = self._lines([(99.0, "stray glyph")] + [(12.2, "body")] * 500)
        self.assertEqual([t.height for t in tier_table(lines)], [12.2])


if __name__ == "__main__":
    unittest.main()
