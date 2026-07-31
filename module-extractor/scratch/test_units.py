#!/usr/bin/env python3
"""Tests for T0.4. Synthetic lines, no PDF."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from columns import Line  # noqa: E402
from tiers import tier_table  # noqa: E402
from units import assemble, heading_heights, is_heading_text, slug  # noqa: E402


def line(text, height, page=1, y=0.0, column=0):
    return Line(page=page, column=column, x=50.0, y=y, height=height, text=text)


def document(*spec):
    """spec: (text, height, page) tuples, in reading order."""
    return [line(t, h, page=p, y=float(i)) for i, (t, h, p) in enumerate(spec)]


BODY = "running body text that goes on for a while here"


class HeadingTextTests(unittest.TestCase):
    def test_a_page_number_is_not_a_heading(self) -> None:
        self.assertFalse(is_heading_text("12"))
        self.assertFalse(is_heading_text("— 12 —"))

    def test_a_bullet_glyph_alone_is_not_a_heading(self) -> None:
        self.assertFalse(is_heading_text("•"))

    def test_a_long_sentence_is_not_a_heading(self) -> None:
        self.assertFalse(is_heading_text(BODY))

    def test_a_keyed_area_is_a_heading(self) -> None:
        self.assertTrue(is_heading_text("24 CRUSH HALLWAY"))


class HeadingTierTests(unittest.TestCase):
    def _heights(self, lines):
        return heading_heights(lines, tier_table(lines, floor=0.0))

    def test_a_tier_just_above_body_is_not_a_heading_tier(self) -> None:
        """Lair sets random-table rows at 12.9 against body at 12.2."""
        lines = document(*[(BODY, 12.2, 1)] * 40,
                         *[("1 Athletic 1 Cautious", 12.9, 1)] * 10)
        self.assertNotIn(12.9, self._heights(lines))

    def test_a_clearly_larger_tier_is_a_heading_tier(self) -> None:
        lines = document(*[(BODY, 12.2, 1)] * 40, *[("24 CRUSH HALLWAY", 14.5, 1)] * 5)
        self.assertIn(14.5, self._heights(lines))

    def test_a_smaller_but_shouting_tier_is_a_heading_tier(self) -> None:
        """The Lost City sets sections below body size."""
        lines = document(*[(BODY, 9.1, 1)] * 40, *[("PLAYERS BACKGROUND", 8.6, 1)] * 5)
        self.assertIn(8.6, self._heights(lines))

    def test_a_smaller_lowercase_tier_is_not_a_heading_tier(self) -> None:
        lines = document(*[(BODY, 12.2, 1)] * 40, *[("• Fighter", 10.5, 1)] * 5)
        self.assertNotIn(10.5, self._heights(lines))


class AssemblyTests(unittest.TestCase):
    def test_a_unit_runs_from_its_heading_to_the_next(self) -> None:
        lines = document(("1 BOWLS", 14.5, 1), (BODY, 12.2, 1),
                         ("2 GOATS", 14.5, 1), (BODY, 12.2, 1))
        units = assemble(lines, {14.5})
        self.assertEqual([u.heading for u in units], ["1 BOWLS", "2 GOATS"])
        self.assertIn(BODY, units[0].text)
        self.assertEqual(units[0].text.count(BODY), 1)

    def test_a_unit_spanning_a_page_break_cites_both_pages(self) -> None:
        lines = document(("4 CHESTS", 14.5, 21), (BODY, 12.2, 21), (BODY, 12.2, 22))
        self.assertEqual(assemble(lines, {14.5})[0].pages, [21, 22])

    def test_content_before_the_first_heading_is_dropped(self) -> None:
        lines = document((BODY, 12.2, 1), ("1 BOWLS", 14.5, 1))
        units = assemble(lines, {14.5})
        self.assertEqual(len(units), 1)
        self.assertEqual(units[0].heading, "1 BOWLS")

    def test_repeated_headings_get_distinct_ids(self) -> None:
        lines = document(("25F CRYPT", 14.5, 30), ("25F CRYPT", 14.5, 30))
        ids = [u.unit_id for u in assemble(lines, {14.5})]
        self.assertEqual(len(set(ids)), 2, ids)

    def test_a_heading_height_carrying_a_page_number_does_not_split(self) -> None:
        lines = document(("1 BOWLS", 14.5, 1), (BODY, 12.2, 1), ("31", 14.5, 1))
        self.assertEqual(len(assemble(lines, {14.5})), 1)

    def test_keyed_area_is_read_off_the_heading(self) -> None:
        units = assemble(document(("24A", 14.5, 31), ("Crossing", 14.5, 31)), {14.5})
        self.assertEqual(units[0].keyed_area, "24A")
        self.assertIsNone(units[1].keyed_area)

    def test_contract_a_shape(self) -> None:
        unit = assemble(document(("1 BOWLS", 14.5, 21), (BODY, 12.2, 21)), {14.5})[0]
        payload = unit.to_contract_a()
        self.assertEqual(
            sorted(payload),
            ["column", "heading", "heading_height", "labels", "pages",
             "text", "text_bytes", "unit_id"],
        )
        self.assertEqual(payload["text_bytes"], len(payload["text"].encode("utf-8")))


class SlugTests(unittest.TestCase):
    def test_slug_is_filesystem_and_id_safe(self) -> None:
        self.assertEqual(slug("24 CRUSH HALLWAY"), "24-crush-hallway")
        self.assertEqual(slug("“ Luck ”"), "luck")

    def test_slug_never_returns_empty(self) -> None:
        self.assertEqual(slug("•••"), "unit")


if __name__ == "__main__":
    unittest.main()
