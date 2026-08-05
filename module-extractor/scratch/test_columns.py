#!/usr/bin/env python3
"""Tests for T0.3 (columns) and T0.2 (tiers). Synthetic pages, no PDF."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pdfhtml import Font, Page, Run  # noqa: E402
from columns import (Line, _split_run_in_heading, body_run_style,  # noqa: E402
                     find_gutter, page_lines, region_lines, run_style)
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

    def test_a_ragged_margin_is_not_mistaken_for_the_gutter(self) -> None:
        """Lair p21: the widest quiet band is short lines, not the gutter.

        The left column ends at 250 but one wide line reaches 295, so the
        emptiest *and widest* band is 250-295 while the real gutter is the
        narrow 300-350. Taking the widest put the boundary mid-sentence and
        ``Each bowl contains 4`` was filed as a full-width line.
        """
        words = [word("shortleft", 50.0, 100.0 + i * 14, w=200.0) for i in range(14)]
        words.append(word("a long justified line reaching further", 50.0, 300.0,
                          w=245.0))
        words += [word("rightcolumntext", 350.0, 100.0 + i * 14, w=200.0)
                  for i in range(14)]
        page = Page(number=1, width=612.0, height=792.0, words=tuple(words))
        gutter = find_gutter(page)
        self.assertIsNotNone(gutter)
        self.assertGreater(gutter, 295.0, "boundary cut the long left line")

    def test_a_two_point_gutter_is_still_a_gutter(self) -> None:
        """Шпиль Кетцаль sets a 2pt gutter on a 722pt page.

        Any absolute minimum width that admits it would admit word spacing on
        *Lair of the Lamb*, which is 918pt wide with a 10pt gutter. Width can
        only ever be a tie-break.
        """
        words = []
        for i in range(20):
            y = 100.0 + i * 12
            words.append(word("left", 40.0, y, w=328.0))
            words.append(word("right", 371.0, y, w=310.0))
        page = Page(number=1, width=722.0, height=1020.0, words=tuple(words))
        gutter = find_gutter(page)
        self.assertIsNotNone(gutter)
        self.assertTrue(368.0 <= gutter <= 371.0, gutter)


def stacked_page(table_rows=25):
    """Two columns of prose above a full-width table -- Шпиль Кетцаль p65.

    The table crosses the middle on most rows, so no gutter holds for the whole
    page and ``find_gutter`` correctly declines.
    """
    words = []
    for i in range(10):
        y = 100.0 + i * 14
        words.append(word("leftcolumntext", 50.0, y, w=200.0))
        words.append(word("rightcolumntext", 350.0, y, w=200.0))
    for i in range(table_rows):
        words.append(word("a full width table row crossing the middle",
                          60.0, 260.0 + i * 14, w=480.0))
    return Page(number=1, width=612.0, height=792.0, words=tuple(words))


class RegionColumnTests(unittest.TestCase):
    """T0.5's fourth defect: a page may hold more than one layout."""

    def test_a_page_with_two_layouts_has_no_page_wide_gutter(self) -> None:
        """Why the fallback exists at all. Detection is right to decline here."""
        self.assertIsNone(find_gutter(stacked_page()))

    def test_columns_above_a_full_width_table_are_not_braided(self) -> None:
        for line in page_lines(stacked_page()):
            self.assertFalse(
                "leftcolumntext" in line.text and "rightcolumntext" in line.text,
                f"columns braided: {line.text!r}",
            )

    def test_the_full_width_table_still_reads_as_full_width(self) -> None:
        table = [line for line in page_lines(stacked_page())
                 if "table row" in line.text]
        self.assertEqual(len(table), 25)
        self.assertTrue(all(line.column == -1 for line in table))

    def test_a_line_reaching_the_boundary_does_not_break_the_run(self) -> None:
        """Doom p4, with the ragged left column that caused it.

        Averaging the cluster put the boundary at 448.6 while one justified line
        reached 449.0, so that line counted as crossing, broke the run of
        agreeing rows, and left every row above it braided. The boundary has to
        lie in the *intersection* of the holes, where no supporting row can
        reach it.
        """
        def row(index, left_right):
            y = 100.0 + index * 14
            return [word("leftcolumntext", 50.0, y, w=left_right - 50.0),
                    word("rightcolumntext", 461.0, y, w=140.0)]

        words = row(0, 420.0) + row(1, 420.0)
        words.append(word("a justified line reaching further", 50.0, 128.0,
                          w=399.0))                                  # right=449
        for index in range(3, 9):
            words += row(index, 420.0)
        for index in range(9, 13):
            words += row(index, 447.0)
        # A full-width table below, so no page-wide gutter holds and the
        # regional path is the one under test.
        for index in range(25):
            words.append(word("a full width table row crossing the middle",
                              60.0, 320.0 + index * 14, w=780.0))
        page = Page(number=1, width=904.0, height=792.0, words=tuple(words))
        self.assertIsNone(find_gutter(page), "page-wide gutter short-circuits")
        for line in page_lines(page):
            self.assertFalse(
                "leftcolumntext" in line.text and "rightcolumntext" in line.text,
                f"columns braided: {line.text!r}",
            )

    def test_three_columns_in_one_region_are_all_separated(self) -> None:
        """A single gutter cannot express Doom's three-column rumour table."""
        words = []
        for i in range(12):
            y = 100.0 + i * 14
            words.append(word("colonetext", 50.0, y, w=150.0))
            words.append(word("coltwotext", 250.0, y, w=150.0))
            words.append(word("colthreetext", 450.0, y, w=150.0))
        page = Page(number=1, width=712.0, height=792.0, words=tuple(words))
        lines = region_lines(page, body=None)
        self.assertEqual(sorted({line.column for line in lines}), [0, 1, 2])
        for line in lines:
            self.assertEqual(len(line.text.split()), 1, f"fused: {line.text!r}")

    def test_a_single_column_page_yields_no_regional_boundary(self) -> None:
        words = tuple(word("bodytext", 50.0, 100.0 + i * 14, w=500.0)
                      for i in range(30))
        page = Page(number=1, width=612.0, height=792.0, words=words)
        self.assertEqual(region_lines(page, body=None), [])


class FolioTests(unittest.TestCase):
    def test_a_page_number_in_the_footer_is_dropped(self) -> None:
        words = [word("bodytext", 50.0, 100.0 + i * 14, w=500.0) for i in range(24)]
        words.append(word("27", 300.0, 760.0))
        page = Page(number=27, width=612.0, height=792.0, words=tuple(words))
        self.assertNotIn("27", [line.text for line in page_lines(page)])

    def test_a_die_number_in_the_body_is_kept(self) -> None:
        """Both conditions are required: digits alone would eat a table row."""
        words = [word("bodytext", 50.0, 100.0 + i * 14, w=500.0) for i in range(24)]
        words.append(word("5", 50.0, 500.0))
        page = Page(number=27, width=612.0, height=792.0, words=tuple(words))
        self.assertIn("5", [line.text for line in page_lines(page)])


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

    def test_a_spanning_heading_divides_the_page_rather_than_preceding_it(self) -> None:
        """Winter's Daughter p13 sets two centred keyed headings on one page.

        Emitting every spanning line before every column put both headings ahead
        of all the prose, so `3. Tomb Entrance` came out with an empty body and
        its granite slab was filed under `4. Worm Hole`.
        """
        words = [word("3. Tomb Entrance", 230.0, 30.0, w=150.0)]
        for i in range(8):
            y = 80.0 + i * 14
            words.append(word("firstroomtext", 50.0, y, w=200.0))
            words.append(word("firstroomright", 350.0, y, w=200.0))
        words.append(word("4. Worm Hole", 230.0, 310.0, w=150.0))
        for i in range(8):
            y = 350.0 + i * 14
            words.append(word("secondroomtext", 50.0, y, w=200.0))
            words.append(word("secondroomright", 350.0, y, w=200.0))
        page = Page(number=13, width=612.0, height=792.0, words=tuple(words))

        texts = [line.text for line in page_lines(page)]
        first, second = texts.index("3. Tomb Entrance"), texts.index("4. Worm Hole")
        self.assertLess(first, second)
        for index, text in enumerate(texts):
            if "firstroom" in text:
                self.assertTrue(first < index < second, f"{text!r} left its heading")
            if "secondroom" in text:
                self.assertGreater(index, second, f"{text!r} preceded its heading")

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

    def test_a_run_in_heading_splits_from_a_tail_that_is_not_body(self) -> None:
        """Doom sets read-aloud text after a keyed heading in bold italic.

        Requiring the tail to match body exactly left C-7, C-10 and D-1 glued
        to their prose and rejected as over-long headings.
        """
        italic = Run(page=1, x=175.0, y=100.0, width=200.0, height=12.0,
                     text="Tall slabs of stone", font=BODY_FONT,
                     bold=True, italic=True)
        row = [self._row()[0], italic]
        parts = _split_run_in_heading(row, run_style(self._row()[1]))
        self.assertEqual(len(parts), 2)
        self.assertIn("Chapel of Justicia", parts[0][0].text)

    def test_a_style_change_alone_does_not_split_a_stat_line(self) -> None:
        """Шпиль Кетцаль sets whole stat lines in non-body styles.

        Cutting on the style change alone promoted fifteen attribute lines to
        units. Only a prefix closing like a heading earns the cut.
        """
        other = Font(font_id=4, size=12.0, family="Caps", color="#000000")
        row = [word("Телосложение 3, ловкость 2", 50.0, 100.0, font=other),
               word("НАВЫКИ: скрытность 2", 175.0, 100.0, font=self.HEAD)]
        self.assertEqual(len(_split_run_in_heading(row, run_style(word("x", 0, 0)))), 1)

    def test_body_style_is_the_most_characters_not_the_most_runs(self) -> None:
        words = [word("H", 50.0, float(i), font=self.HEAD) for i in range(9)]
        words.append(word("a" * 200, 50.0, 100.0, w=300.0))
        page = Page(number=1, width=612.0, height=792.0, words=tuple(words))
        self.assertEqual(body_run_style([page]), run_style(words[-1]))


class DropCapTests(unittest.TestCase):
    """A 72pt initial describes one glyph, never the row it opens."""

    DISPLAY = Font(font_id=5, size=21.0, family="Duvall", color="#000000")
    INITIAL = Font(font_id=6, size=72.0, family="RomantiqueInitials", color="#000000")

    def _page(self):
        # Doom page 3: heading, then an initial 85pt tall across three body
        # lines. Letting the initial set the row tolerance fused all three.
        words = [word("IntroductIon", 152.0, 52.0, h=23.0, font=self.DISPLAY, bold=True),
                 word("R", 53.0, 78.0, h=85.0, w=63.0, font=self.INITIAL),
                 word("emember the good old days", 116.0, 89.0, w=331.0),
                 word("underground, NPCs were there", 116.0, 106.0, w=331.0)]
        return Page(number=3, width=904.0, height=1174.0, words=tuple(words))

    def test_the_heading_above_an_initial_stays_its_own_line(self) -> None:
        lines = page_lines(self._page(), body=run_style(word("x", 0.0, 0.0)))
        self.assertIn("IntroductIon", [item.text for item in lines])

    def test_the_heading_keeps_its_own_style(self) -> None:
        """Fused into the body row it took body's style and stopped ranking."""
        lines = page_lines(self._page(), body=run_style(word("x", 0.0, 0.0)))
        heading = next(item for item in lines if item.text == "IntroductIon")
        self.assertEqual(heading.family, "Duvall")
        self.assertEqual(heading.size, 21.0)

    def test_an_initial_still_joins_the_paragraph_it_opens(self) -> None:
        lines = page_lines(self._page(), body=run_style(word("x", 0.0, 0.0)))
        self.assertTrue(any(item.text.startswith("R emember") for item in lines),
                        [item.text for item in lines])

    def test_an_initial_claims_one_line_and_not_the_paragraph(self) -> None:
        """Once the row has ordinary text, the initial's height is spent.

        Left in the measure it kept reaching down the column, taking the second
        and third body lines into the same row.
        """
        lines = page_lines(self._page(), body=run_style(word("x", 0.0, 0.0)))
        self.assertIn("underground, NPCs were there", [item.text for item in lines])


class ItalicStyleTests(unittest.TestCase):
    def test_italic_distinguishes_two_otherwise_identical_styles(self) -> None:
        """Doom's read-aloud text is bold italic where its act titles are bold.

        Blind to italic, every boxed paragraph after a keyed heading became a
        heading of its own.
        """
        upright = Run(page=1, x=0.0, y=0.0, width=10.0, height=12.0, text="a",
                      font=BODY_FONT, bold=True, italic=False)
        slanted = Run(page=1, x=0.0, y=0.0, width=10.0, height=12.0, text="a",
                      font=BODY_FONT, bold=True, italic=True)
        self.assertNotEqual(run_style(upright), run_style(slanted))


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
