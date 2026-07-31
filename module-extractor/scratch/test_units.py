#!/usr/bin/env python3
"""Tests for T0.4. Synthetic lines, no PDF."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from columns import Line  # noqa: E402
from units import (assemble, furniture, is_heading_text,  # noqa: E402
                   key_root, slug)


BODY = ("running body text that goes on for a while here", 12.0, "Body", False, "#000000")
AREA = (18.0, "Display", False, "#3333ff")   # Lair keyed areas and subsections
PART = (30.0, "Display", False, "#000000")   # senior: part titles

RANKS = {PART: 0, AREA: 1}


def line(text, style, page=1, y=0.0):
    size, family, bold, color = style
    return Line(page=page, column=0, x=50.0, y=y, height=size, text=text,
                size=size, family=family, bold=bold, color=color)


def body(page=1, y=0.0):
    return line(BODY[0], (BODY[1], BODY[2], BODY[3], BODY[4]), page, y)


class TextTests(unittest.TestCase):
    def test_page_numbers_and_glyphs_are_not_headings(self) -> None:
        for value in ("12", "— 12 —", "•"):
            self.assertFalse(is_heading_text(value), value)

    def test_a_keyed_area_is_a_heading(self) -> None:
        self.assertTrue(is_heading_text("24 CRUSH HALLWAY"))

    def test_key_root_reads_the_leading_number(self) -> None:
        self.assertEqual(key_root("24 CRUSH HALLWAY"), "24")
        self.assertEqual(key_root("24C"), "24")
        self.assertEqual(key_root("1A FIRST INTERSECTION"), "1")
        self.assertIsNone(key_root("Crossing the Hallway"))

    def test_slug_is_id_safe_and_never_empty(self) -> None:
        self.assertEqual(slug("24 CRUSH HALLWAY"), "24-crush-hallway")
        self.assertEqual(slug("•••"), "unit")

    def test_slug_keeps_cyrillic(self) -> None:
        """An ASCII-only class erased it, collapsing 527 unit IDs to one."""
        self.assertEqual(slug("АВТОРЫ"), "авторы")
        self.assertEqual(slug("КАРТЫ И ГРАФИКА"), "карты-и-графика")

    def test_cyrillic_headings_get_distinct_slugs(self) -> None:
        self.assertNotEqual(slug("АВТОРЫ"), slug("РЕДАКТОРЫ"))


class FurnitureTests(unittest.TestCase):
    def test_text_repeated_across_pages_is_furniture(self) -> None:
        """A watermark stamped on every page produced 49 spurious units."""
        lines = [line("nsartem@pm.me #9013", AREA, page=p) for p in (1, 2, 3, 4)]
        self.assertIn("nsartem@pm.me #9013", furniture(lines))

    def test_two_appearances_are_not_furniture(self) -> None:
        """Lair keys 25F CRYPT twice and both are real."""
        lines = [line("25F CRYPT", AREA, page=p) for p in (30, 31)]
        self.assertNotIn("25F CRYPT", furniture(lines))

    def test_furniture_does_not_open_a_unit(self) -> None:
        lines = [line("1 BOWLS", AREA, page=1), body(page=1),
                 line("RUNNING HEAD", AREA, page=2), body(page=2)]
        units = assemble(lines, RANKS, repeated={"RUNNING HEAD"})
        self.assertEqual([u.heading for u in units], ["1 BOWLS"])


class AbsorptionTests(unittest.TestCase):
    """Decision 1: subsections fold into their keyed area, and only there."""

    def test_sub_areas_are_absorbed_into_their_parent(self) -> None:
        lines = [line("24 CRUSH HALLWAY", AREA), body(),
                 line("24A", AREA, y=1), body(y=2),
                 line("24C", AREA, y=3), body(y=4)]
        units = assemble(lines, RANKS)
        self.assertEqual([u.heading for u in units], ["24 CRUSH HALLWAY"])
        self.assertIn("24A", units[0].text)
        self.assertIn("24C", units[0].text)

    def test_an_unkeyed_subsection_is_absorbed(self) -> None:
        lines = [line("24 CRUSH HALLWAY", AREA), body(),
                 line("Crossing the Hallway", AREA, y=1), body(y=2)]
        units = assemble(lines, RANKS)
        self.assertEqual(len(units), 1)
        self.assertIn("Crossing the Hallway", units[0].text)

    def test_a_new_root_key_opens_a_new_unit(self) -> None:
        lines = [line("24 CRUSH HALLWAY", AREA), body(),
                 line("25F CRYPT", AREA, y=1), body(y=2)]
        self.assertEqual(len(assemble(lines, RANKS)), 2)

    def test_a_senior_heading_always_opens_a_new_unit(self) -> None:
        lines = [line("24 CRUSH HALLWAY", AREA), body(),
                 line("Part 2", PART, y=1), body(y=2)]
        self.assertEqual(len(assemble(lines, RANKS)), 2)

    def test_outside_a_keyed_area_nothing_is_absorbed(self) -> None:
        """The bug that left Lair with 16 units and no keys."""
        lines = [line("Part 1", PART), body(),
                 line("Exploration", AREA, y=1), body(y=2),
                 line("Combat", AREA, y=3), body(y=4)]
        self.assertEqual([u.heading for u in assemble(lines, RANKS)],
                         ["Part 1", "Exploration", "Combat"])

    def test_a_keyed_area_under_a_part_title_still_opens_a_unit(self) -> None:
        lines = [line("Part 1", PART), body(), line("1 BOWLS", AREA, y=1)]
        self.assertEqual(len(assemble(lines, RANKS)), 2)


class AssemblyTests(unittest.TestCase):
    def test_a_unit_spanning_a_page_break_cites_both_pages(self) -> None:
        lines = [line("4 CHESTS", AREA, page=21), body(page=21), body(page=22, y=1)]
        self.assertEqual(assemble(lines, RANKS)[0].pages, [21, 22])

    def test_content_before_the_first_heading_is_dropped(self) -> None:
        units = assemble([body(), line("1 BOWLS", AREA, y=1)], RANKS)
        self.assertEqual([u.heading for u in units], ["1 BOWLS"])

    def test_repeated_headings_get_distinct_ids(self) -> None:
        lines = [line("25F CRYPT", AREA, page=30), body(page=30),
                 line("26 X", AREA, page=30, y=1),
                 line("25F CRYPT", AREA, page=30, y=2)]
        ids = [u.unit_id for u in assemble(lines, RANKS)]
        self.assertEqual(len(set(ids)), len(ids), ids)

    def test_a_page_number_at_heading_style_does_not_split(self) -> None:
        lines = [line("1 BOWLS", AREA), body(), line("31", AREA, y=1)]
        self.assertEqual(len(assemble(lines, RANKS)), 1)

    def test_contract_a_shape(self) -> None:
        unit = assemble([line("1 BOWLS", AREA, page=21), body(page=21)], RANKS)[0]
        payload = unit.to_contract_a()
        self.assertEqual(
            sorted(payload),
            ["column", "heading", "keyed_area", "labels", "pages", "style",
             "text", "text_bytes", "unit_id"],
        )
        self.assertEqual(payload["keyed_area"], "1")
        self.assertEqual(payload["text_bytes"], len(payload["text"].encode("utf-8")))


if __name__ == "__main__":
    unittest.main()
