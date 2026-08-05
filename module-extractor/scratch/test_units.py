#!/usr/bin/env python3
"""Tests for T0.4. Synthetic lines, no PDF."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from columns import Line  # noqa: E402
from units import (assemble, attach_paths, furniture,  # noqa: E402
                   is_heading_text, join_wrapped_headings, key_root,
                   merge_table_runs, rejoin_run_ins, slug)


BODY = ("running body text that goes on for a while here", 12.0, "Body", False, "#000000")
AREA = (18.0, "Display", False, "#3333ff")   # Lair keyed areas and subsections
PART = (30.0, "Display", False, "#000000")   # senior: part titles

RANKS = {PART: 0, AREA: 1}


def line(text, style, page=1, y=0.0, run_in=False):
    size, family, bold, color = style
    return Line(page=page, column=0, x=50.0, y=y, height=size, text=text,
                size=size, family=family, bold=bold, color=color, run_in=run_in)


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

    def test_key_root_reads_lettered_keys(self) -> None:
        """Doom keys its village as Area A-1 .. Area A-11."""
        self.assertEqual(key_root("Area A-4 - Chapel of Justicia:"), "A-4")
        self.assertEqual(key_root("Area A - Village of Hirot:"), "A")

    def test_lettered_siblings_are_distinct_keys(self) -> None:
        """A-1 and A-4 must not share a root, or they merge into one unit."""
        self.assertNotEqual(key_root("Area A-1 - South Gates:"),
                            key_root("Area A-4 - Chapel:"))


class TableRunTests(unittest.TestCase):
    """Table rows are content. They become one unit, not none and not many."""

    def _unit(self, heading, body_lines=0):
        lines = [line(heading, AREA)] + [body() for _ in range(body_lines)]
        return assemble(lines, RANKS)[0]

    def test_a_run_of_tiny_headings_folds_into_the_unit_above(self) -> None:
        units = [self._unit("Wandering Monsters", body_lines=3)]
        units += [self._unit(f"{n} Goblin") for n in range(1, 7)]
        merged = merge_table_runs(units)
        self.assertEqual([u.heading for u in merged], ["Wandering Monsters"])

    def test_no_content_is_lost_when_rows_are_folded(self) -> None:
        units = [self._unit("Wandering Monsters", body_lines=3)]
        units += [self._unit(f"{n} Goblin") for n in range(1, 7)]
        merged = merge_table_runs(units)
        for n in range(1, 7):
            self.assertIn(f"{n} Goblin", merged[0].text)

    def test_a_single_small_unit_is_not_a_table(self) -> None:
        units = [self._unit("1 BOWLS", body_lines=3), self._unit("24C")]
        self.assertEqual(len(merge_table_runs(units)), 2)

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

    def test_an_unkeyed_all_caps_sibling_is_not_absorbed(self) -> None:
        """FIGHTING THE LAMB is the climax, not part of 44A WALL."""
        lines = [line("44A WALL", AREA), body(),
                 line("FIGHTING THE LAMB", AREA, y=1), body(y=2)]
        self.assertEqual([u.heading for u in assemble(lines, RANKS)],
                         ["44A WALL", "FIGHTING THE LAMB"])

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
            ["column", "heading", "heading_path", "keyed_area", "labels",
             "pages", "style", "text", "text_bytes", "unit_id"],
        )
        self.assertEqual(payload["keyed_area"], "1")
        self.assertEqual(payload["text_bytes"], len(payload["text"].encode("utf-8")))


class RunInTests(unittest.TestCase):
    """A run-in prefix earns a unit boundary only by opening a key."""

    def test_an_unkeyed_prefix_is_folded_back_into_its_row(self) -> None:
        lines = rejoin_run_ins([
            line("Lvl", AREA, run_in=True),
            line("4 Def leather Slam 1d6", (12.0, "Body", False, "#000000")),
        ])
        self.assertEqual([item.text for item in lines],
                         ["Lvl 4 Def leather Slam 1d6"])

    def test_a_keyed_prefix_survives_as_its_own_line(self) -> None:
        """Doom sets every keyed area this way; splitting them is the point."""
        lines = rejoin_run_ins([
            line("Area A-4 - Chapel of Justicia:", AREA, run_in=True),
            line("The chapel is a low, vaulted hall", (12.0, "Body", False, "#000000")),
        ])
        self.assertEqual(len(lines), 2)

    def test_a_prefix_on_a_different_row_is_left_alone(self) -> None:
        lines = rejoin_run_ins([
            line("Stonemeld -", AREA, run_in=True),
            line("body", (12.0, "Body", False, "#000000"), page=2),
        ])
        self.assertEqual(len(lines), 2)

    def test_the_folded_line_takes_the_longer_runs_style(self) -> None:
        """So it can never be read as a heading afterwards."""
        lines = rejoin_run_ins([
            line("Lvl", AREA, run_in=True),
            line("4 Def leather Slam 1d6 and more besides",
                 (12.0, "Body", False, "#000000")),
        ])
        self.assertEqual(lines[0].size, 12.0)


class WrappedHeadingTests(unittest.TestCase):
    def test_a_heading_wrapping_onto_three_lines_is_one_heading(self) -> None:
        lines = join_wrapped_headings(
            [line("Part 2", PART, y=0.0),
             line("Gallery of", PART, y=40.0),
             line("the Ghouls", PART, y=80.0)],
            RANKS,
        )
        self.assertEqual([item.text for item in lines],
                         ["Part 2 Gallery of the Ghouls"])

    def test_keyed_table_rows_are_never_joined(self) -> None:
        """Lair keys its character tables by die number, in the heading style."""
        rows = [line("1 Athletic", AREA, y=0.0), line("2 Beautiful", AREA, y=20.0),
                line("3 Boney", AREA, y=40.0)]
        self.assertEqual(len(join_wrapped_headings(rows, RANKS)), 3)

    def test_a_finished_sentence_does_not_wrap(self) -> None:
        lines = join_wrapped_headings(
            [line("Immunity - Acid.", PART, y=0.0),
             line("Immunity - Fire.", PART, y=20.0)],
            RANKS,
        )
        self.assertEqual(len(lines), 2)

    def test_a_paragraph_gap_is_not_a_wrap(self) -> None:
        lines = join_wrapped_headings(
            [line("Overview", PART, y=0.0), line("Secrets", PART, y=400.0)],
            RANKS,
        )
        self.assertEqual(len(lines), 2)

    def test_body_style_lines_are_never_joined(self) -> None:
        lines = join_wrapped_headings([body(y=0.0), body(y=14.0)], RANKS)
        self.assertEqual(len(lines), 2)


class HeadingPathTests(unittest.TestCase):
    SECTION = AREA  # rank 1 in RANKS

    def _units(self, lines):
        return attach_paths(assemble(lines, RANKS))

    def test_a_bodyless_title_reaches_its_children(self) -> None:
        """Lair prints two encounter tables side by side in one style."""
        units = self._units([
            line("Encounter Table (Lamb Dead)", self.SECTION, page=18, y=0.0),
            line("Active Encounters", self.SECTION, page=18, y=20.0),
            body(page=18, y=40.0),
        ])
        self.assertEqual(units[1].heading, "Active Encounters")
        self.assertEqual(units[1].path, ("Encounter Table (Lamb Dead)",))

    def test_a_same_rank_title_does_not_survive_a_page_turn(self) -> None:
        """The regression: it leaked onto every keyed room for three pages."""
        units = self._units([
            line("Encounter Table (Lamb Dead)", self.SECTION, page=18, y=0.0),
            line("Active Encounters", self.SECTION, page=18, y=20.0),
            body(page=18, y=40.0),
            line("Dungeon Features", self.SECTION, page=19, y=0.0),
            body(page=19, y=20.0),
        ])
        self.assertEqual(units[-1].heading, "Dungeon Features")
        self.assertEqual(units[-1].path, ())

    def test_a_senior_divider_keeps_its_scope_across_pages(self) -> None:
        units = self._units([
            line("Part 2 Gallery of the Ghouls", PART, page=27, y=0.0),
            line("Lantern Worm", self.SECTION, page=28, y=0.0),
            body(page=28, y=20.0),
        ])
        self.assertEqual(units[-1].path, ("Part 2 Gallery of the Ghouls",))

    def test_a_title_with_a_body_is_not_an_ancestor(self) -> None:
        units = self._units([
            line("Overview", self.SECTION, page=19, y=0.0), body(page=19, y=20.0),
            line("Starting the Game", self.SECTION, page=19, y=40.0),
            body(page=19, y=60.0),
        ])
        self.assertEqual(units[-1].path, ())


class FurnitureTests(unittest.TestCase):
    def test_a_running_head_is_furniture(self) -> None:
        lines = [line("Lair of the Lamb", PART, page=p, y=10.0) for p in (1, 2, 3)]
        self.assertIn("Lair of the Lamb", furniture(lines))

    def test_a_repeated_title_that_moves_is_not_furniture(self) -> None:
        """Lair heads three pages 'Encounter Table (Lamb Alive)'.

        Counting pages alone deleted it while leaving its twin, printed twice,
        standing -- so two tables of the same kind looked like different kinds.
        """
        lines = [line("Encounter Table (Lamb Alive)", PART, page=p, y=y)
                 for p, y in ((17, 493.0), (18, 120.0), (19, 700.0))]
        self.assertNotIn("Encounter Table (Lamb Alive)", furniture(lines))


if __name__ == "__main__":
    unittest.main()
