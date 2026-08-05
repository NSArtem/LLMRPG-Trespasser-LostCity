"""Stage 1: typed-run extraction and the unusable-text-layer gate (T2.1, T2.2)."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from module_extractor.errors import ExtractorError  # noqa: E402
from module_extractor.preparation import (  # noqa: E402
    POPLER_TOOLS,
    TEXT_LAYER_MIN_RUNS,
    TEXT_LAYER_MIN_RUNS_PER_STYLE,
    check_text_layer,
    prepare,
    style_keys,
)


def runs_xml(runs: int, styles: int, family: str = "F") -> str:
    """A pdftohtml -xml document with a stated number of runs and styles."""
    specs = "".join(
        f'<fontspec id="{index}" size="{10 + index}" '
        f'family="{family}{index}" color="#000000"/>'
        for index in range(styles)
    )
    texts = "".join(
        f'<text top="{index}" left="0" width="10" height="10" '
        f'font="{index % styles if styles else 0}">word{index}</text>'
        for index in range(runs)
    )
    return (
        '<pdf2xml><page number="1" width="612" height="792">'
        f"{specs}{texts}</page></pdf2xml>"
    )


class StyleKeyTests(unittest.TestCase):
    def test_size_family_and_colour_are_all_distinguishing(self) -> None:
        xml = (
            '<fontspec id="0" size="12" family="Body" color="#000000"/>'
            '<fontspec id="1" size="18" family="Body" color="#000000"/>'
            '<fontspec id="2" size="12" family="Display" color="#000000"/>'
            '<fontspec id="3" size="12" family="Body" color="#3333ff"/>'
            '<fontspec id="4" size="12" family="Body" color="#000000"/>'
        )
        self.assertEqual(len(style_keys(xml)), 4)

    def test_a_font_subset_tag_is_not_a_style(self) -> None:
        """One face is DHWVTZ+BookAntiqua on one page and CZMPFB+ on the next.

        Counting the tag would inflate an ordinary document's style count and
        could fail it as OCR noise.
        """
        xml = (
            '<fontspec id="0" size="14" family="DHWVTZ+BookAntiqua" color="#000000"/>'
            '<fontspec id="1" size="14" family="CZMPFB+BookAntiqua" color="#000000"/>'
        )
        self.assertEqual(len(style_keys(xml)), 1)

    def test_malformed_markup_does_not_stop_the_count(self) -> None:
        """Poppler leaves bare ampersands in font names; ET would refuse this."""
        xml = '<fontspec id="0" size="11" family="TURLCX+Brokgauz&Efron" color="#181716"/>'
        self.assertEqual(len(style_keys(xml)), 1)


class TextLayerTests(unittest.TestCase):
    def test_a_pdf_with_no_text_layer_fails_and_says_so(self) -> None:
        with self.assertRaises(ExtractorError) as caught:
            check_text_layer("   \n\f  ", runs_xml(0, 0))
        self.assertIn("no text layer", str(caught.exception))

    def test_ocr_noise_fails_and_names_the_ratio(self) -> None:
        """Curse of Strahd: 32,020 runs under 11,964 synthetic styles."""
        with self.assertRaises(ExtractorError) as caught:
            check_text_layer("plenty of text", runs_xml(3000, 1500))
        message = str(caught.exception)
        self.assertIn("unusable", message)
        self.assertIn("3000 text runs", message)
        self.assertIn("1500 distinct styles", message)

    def test_a_typeset_source_passes(self) -> None:
        """The worst in-scope source is Falkrest at 103 runs per style."""
        check_text_layer("plenty of text", runs_xml(3000, 30))

    def test_the_ratio_is_not_applied_to_a_short_document(self) -> None:
        """Too few runs for the ratio to mean anything; emptiness still rules."""
        runs = TEXT_LAYER_MIN_RUNS - 1
        check_text_layer("plenty of text", runs_xml(runs, runs))

    def test_the_threshold_is_where_it_says_it_is(self) -> None:
        runs = TEXT_LAYER_MIN_RUNS * 4
        just_under = int(runs / TEXT_LAYER_MIN_RUNS_PER_STYLE) + 1
        with self.assertRaises(ExtractorError):
            check_text_layer("text", runs_xml(runs, just_under))
        check_text_layer("text", runs_xml(runs, int(runs / 40)))

    def test_a_damaged_text_layer_is_not_this_check(self) -> None:
        """The Lost City scores 190 runs per style and reads

            C e ntip e d e , G ia nt. G ia n t c en tip ed es

        A clean font table over damaged glyphs is a different defect with a
        different measure, and it is still deferred. This check must not claim
        it, because a false pass here is honest and a false failure is not.
        """
        check_text_layer("C e ntip e d e , G ia nt", runs_xml(3800, 20))


class PrepareTests(unittest.TestCase):
    """End to end through ``prepare`` with Poppler mocked."""

    def _prepare(self, root: Path, xml: str, page_text: str = "Visible text\f"):
        pdf = root / "source.pdf"
        pdf.write_bytes(b"synthetic pdf")
        called: list[str] = []

        def fake_poppler(arguments: list[str]) -> mock.Mock:
            called.append(arguments[0])
            if arguments[0] == "pdftotext":
                Path(arguments[-1]).write_text(page_text, encoding="utf-8")
            elif arguments[0] == "pdftoppm":
                prefix = Path(arguments[-1])
                (prefix.parent / f"{prefix.name}-1.png").write_bytes(b"png")
            elif arguments[0] == "pdftohtml":
                return mock.Mock(returncode=0, stdout=xml, stderr="")
            return mock.Mock(returncode=0, stdout="", stderr="")

        with (
            mock.patch("module_extractor.preparation.shutil.which",
                       return_value="/usr/bin/tool"),
            mock.patch("module_extractor.preparation._pdf_info",
                       return_value={"pdf_pages": 1, "pdf_title": ""}),
            mock.patch("module_extractor.preparation._run",
                       side_effect=fake_poppler),
        ):
            try:
                prepare(
                    pdf,
                    slug="example",
                    title="Example",
                    input_dir=root / "module-input",
                    exchange_dir=root / "_exchange",
                    cache_dir=root / ".cache",
                )
            finally:
                self.called = called

    def test_the_typed_runs_are_cached_verbatim(self) -> None:
        xml = runs_xml(300, 10)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._prepare(root, xml)
            cached = (root / ".cache/text/runs.xml").read_text(encoding="utf-8")
        self.assertEqual(cached, xml)

    def test_pdftohtml_is_a_required_tool(self) -> None:
        self.assertIn("pdftohtml", POPLER_TOOLS)

    def test_an_ocr_noise_source_stops_preparation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(ExtractorError) as caught:
                self._prepare(root, runs_xml(3000, 1500))
        self.assertIn("OCR noise", str(caught.exception))

    def test_an_empty_text_layer_stops_preparation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(ExtractorError) as caught:
                self._prepare(root, runs_xml(300, 10), page_text="\f")
        self.assertIn("no text layer", str(caught.exception))

    def test_an_unusable_source_fails_before_the_page_renders(self) -> None:
        """258 pages of thumbnails is a long wait for a decidable failure."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(ExtractorError):
                self._prepare(root, runs_xml(3000, 1500))
        self.assertNotIn("pdftoppm", self.called)

    def test_nothing_is_published_when_the_check_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(ExtractorError):
                self._prepare(root, runs_xml(3000, 1500))
            self.assertFalse((root / ".cache").exists())
            self.assertFalse((root / "module-input").exists())


if __name__ == "__main__":
    unittest.main()
