import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from pdfx.mathml import MathSyntaxError, output_math_residue, render_inline_math, render_math
from pdfx.parse import ParseError, parse
from pdfx.render import ASSETS, body_html
from pdfx.sources import page_units
from pdfx.verify import media_contact_sheet


class MathRenderingTests(unittest.TestCase):
    def test_tex_fraction_scripts_and_greek_render_to_mathml(self):
        html = render_math(r"E_0 = \frac{1}{2} k Q_R^2 + \lambda")
        self.assertIn("<math", html)
        self.assertIn("<mfrac>", html)
        self.assertIn("<msub>", html)
        self.assertIn("<msubsup>", html)
        self.assertIn("λ", html)

    def test_inline_delimiters_render(self):
        html = render_inline_math(r"energy \(E_0\) and $Q^2$")
        self.assertEqual(html.count('<math class="math-inline"'), 2)

    def test_html_attribute_underscores_are_not_tex_residue(self):
        self.assertEqual(render_inline_math('<span class="math_note">注記</span>'),
                         '<span class="math_note">注記</span>')

    def test_bold_math_commands_render_without_literal_command_names(self):
        html = render_math(r"\mathbf{r}+\boldsymbol{\varepsilon}")
        self.assertIn('mathvariant="bold"', html)
        self.assertIn('mathvariant="bold-italic"', html)
        self.assertNotIn(">mathbf<", html)
        self.assertNotIn(">boldsymbol<", html)

    def test_unknown_tex_command_is_rejected(self):
        with self.assertRaisesRegex(MathSyntaxError, "unsupported TeX command"):
            render_math(r"\notacommand{x}")

    def test_signed_exponent_requires_braces(self):
        with self.assertRaisesRegex(MathSyntaxError, "need braces"):
            render_math(r"O(L^-5)")
        self.assertIn("<msup>", render_math(r"O(L^{-5})"))

    def test_visible_output_scan_ignores_tex_annotation_inside_math(self):
        rendered = render_math(r"E_0=\frac{1}{2}")
        valid = f"<p>{rendered}</p>"
        self.assertEqual(output_math_residue(valid), [])
        self.assertEqual(output_math_residue(r"<p>broken \varepsilon and L^-5</p>"),
                         [r"\varepsilon", "^"])
        self.assertEqual(output_math_residue("<p>broken lambda</p>"), ["lambda"])


class LinkCoverageTests(unittest.TestCase):
    def test_source_id_links_one_span_to_one_page_location(self):
        blocks, spans = parse("{{s3.12|座標付きIDでリンクする}}。")
        self.assertEqual(blocks[0].link_gaps, [])
        self.assertEqual(spans[0].source_id, "s3.12")
        self.assertEqual(spans[0].page, 2)
        self.assertEqual(spans[0].phrases, [])

    def test_source_id_cannot_be_reused(self):
        with self.assertRaisesRegex(ParseError, "source ID 's1.1' is reused"):
            parse("{{s1.1|主張A}}。{{s1.1|主張B}}。")

    def test_fully_linked_prose_has_no_gap(self):
        blocks, _ = parse("{{p1|source phrase|全文をリンクする}}。")
        self.assertEqual(blocks[0].link_gaps, [])

    def test_unlinked_words_are_reported(self):
        blocks, _ = parse("{{p1|source phrase|リンク済み}}だが未リンク。")
        self.assertTrue(blocks[0].link_gaps)

    def test_linked_equation_is_mathml_and_has_no_gap(self):
        blocks, _ = parse(r"= {{p1|source equation|E_0 = \frac{1}{2}kQ^2}}")
        self.assertEqual(blocks[0].link_gaps, [])
        self.assertIn("<mfrac>", blocks[0].html)
        self.assertIn('<a class="a"', blocks[0].html)

    def test_source_id_equation_is_mathml_and_has_no_gap(self):
        blocks, spans = parse(r"= {{s1.2|E_0 = \frac{1}{2}kQ^2}}")
        self.assertEqual(blocks[0].link_gaps, [])
        self.assertEqual(spans[0].source_id, "s1.2")
        self.assertIn("<mfrac>", blocks[0].html)

    def test_tex_group_braces_do_not_close_source_anchor(self):
        blocks, spans = parse(
            r"= {{s1.2|E_{\mathrm{FNV}}=E_{\mathrm{PC}}+O(L^{-5})}}"
        )
        self.assertEqual(len(spans), 1)
        self.assertEqual(spans[0].text,
                         r"\(E_{\mathrm{FNV}}=E_{\mathrm{PC}}+O(L^{-5})\)")
        self.assertEqual(blocks[0].html.count("<math"), 1)

    def test_multiline_source_anchor_remains_supported(self):
        blocks, spans = parse("{{s1.2|一行目\n二行目 \\(E_0\\)}}")
        self.assertEqual(len(spans), 1)
        self.assertEqual(blocks[0].link_gaps, [])
        self.assertEqual(blocks[0].html.count("<math"), 1)

    def test_display_equation_rejects_nested_inline_delimiters(self):
        with self.assertRaisesRegex(ParseError, "already creates display math"):
            parse(r"= {{s1.2|\(E_{\mathrm{FNV}}=E_{\mathrm{PC}}-q\Delta V\)}}")

    def test_display_equation_cannot_cross_source_links(self):
        with self.assertRaisesRegex(ParseError, "cannot cross source links"):
            parse(
                r"= {{s1.2|E_{\mathrm{FNV}}=E_{\mathrm{PC}}-q\Delta V}} "
                r"{{s1.3|=[1-\alpha(r)]E_{\mathrm{PC}}}}"
            )

    def test_inline_tex_requires_inline_delimiters(self):
        with self.assertRaisesRegex(ParseError, "outside math delimiters"):
            parse(r"{{s1.2|欠陥電荷密度 (\rho_d)}}")

    def test_unlinked_equation_is_reported(self):
        blocks, _ = parse(r"= E_0 = \frac{1}{2}kQ^2")
        self.assertTrue(blocks[0].link_gaps)


class MediaTests(unittest.TestCase):
    def test_figure_crop_and_linked_caption(self):
        blocks, spans = parse(
            ":::media figure\n"
            "@crop p1 10 20 80 50\n"
            "{{p1|Figure 1. Structure.|図1　構造図}}\n"
            ":::"
        )
        self.assertEqual(len(spans), 1)
        self.assertEqual(blocks[0].title, "figure")
        self.assertEqual(blocks[0].media[0].crop, (10.0, 20.0, 80.0, 50.0))
        self.assertEqual(blocks[0].link_gaps, [])

    def test_compare_requires_two_crops(self):
        with self.assertRaises(ParseError):
            parse(
                ":::media compare\n"
                "@crop p1 0 0 50 50\n"
                "{{p1|Table 3.|表3}}\n"
                ":::"
            )

    def test_nearly_full_page_crop_is_rejected(self):
        with self.assertRaisesRegex(ParseError, "looks like a page capture"):
            parse(
                ":::media figure\n"
                "@crop p1 2 2 96 95\n"
                "{{p1|Figure 1. Structure.|図1　構造図}}\n"
                ":::"
            )

    def test_caption_must_link_to_cropped_page(self):
        with self.assertRaises(ParseError):
            parse(
                ":::media figure\n"
                "@crop p1 0 0 50 50\n"
                "{{p2|Figure 1.|図1}}\n"
                ":::"
            )

    def test_media_is_embedded_as_data_uri(self):
        blocks, _ = parse(
            ":::media table\n"
            "@crop p1 10 10 60 70\n"
            "{{p1|Table 1. Results.|表1　結果}}\n"
            ":::"
        )
        with TemporaryDirectory() as directory:
            pages = Path(directory) / "pages"
            pages.mkdir()
            Image.new("RGB", (100, 100), "white").save(pages / "p01.png")
            rendered = body_html(blocks, Path(directory))
        self.assertIn('class="media-card media-table"', rendered)
        self.assertIn("data:image/png;base64,", rendered)
        self.assertIn('href="#source-a001-1"', rendered)

    def test_media_review_sheet_is_generated(self):
        blocks, _ = parse(
            ":::media figure\n"
            "@crop p1 10 20 80 50\n"
            "{{p1|Figure 1. Structure.|図1　構造図}}\n"
            ":::"
        )
        with TemporaryDirectory() as directory:
            pages = Path(directory) / "pages"
            pages.mkdir()
            Image.new("RGB", (200, 300), "white").save(pages / "p01.png")
            output = media_contact_sheet(directory, blocks)
            self.assertIsNotNone(output)
            self.assertTrue(output.exists())


class SourceIndexTests(unittest.TestCase):
    def test_units_preserve_exact_text_offsets(self):
        text = "  First source line.\r\nSecond source line.\n\nThird.  "
        units = page_units(text, 1)
        self.assertEqual([unit["id"] for unit in units], ["s2.1", "s2.2", "s2.3"])
        for unit in units:
            self.assertEqual(
                text[unit["start"]:unit["start"] + unit["count"]],
                unit["text"],
            )

    def test_unusually_long_line_is_split_into_short_units(self):
        text = " ".join(["evidence"] * 80)
        units = page_units(text, 0)
        self.assertGreater(len(units), 1)
        self.assertTrue(all(len(unit["text"]) <= 120 for unit in units))


class MobileViewerTests(unittest.TestCase):
    def test_mobile_uses_native_horizontal_scroll_snap(self):
        css = (ASSETS / "explainer.css").read_text(encoding="utf-8")
        self.assertIn("scroll-snap-type:x mandatory", css)
        self.assertIn("scroll-snap-align:start", css)
        self.assertNotIn('data-mobile-pane="article"] .col-right{display:none}', css)

    def test_swipe_and_links_share_animated_pane_navigation(self):
        js = (ASSETS / "explainer.js").read_text(encoding="utf-8")
        self.assertIn("layout.scrollTo", js)
        self.assertIn("layout.addEventListener('scroll'", js)
        self.assertIn("requestAnimationFrame(()=>focusPdf(anchor))", js)
        self.assertNotIn("swipeStart", js)


class HighlightInteractionTests(unittest.TestCase):
    def test_explanation_is_clear_until_hovered_or_pinned(self):
        css = (ASSETS / "explainer.css").read_text(encoding="utf-8")
        self.assertIn(".a{padding:1px 2px;border-radius:3px;background:transparent", css)
        self.assertIn(".a:hover{background:rgba(var(--highlight-rgb),.08)", css)
        self.assertIn(".a.pinned{background:rgba(var(--highlight-rgb),.16)", css)
        self.assertNotIn(".a.active", css)

    def test_pdf_highlights_are_persistent_and_emphasized_at_thirty_two_percent(self):
        css = (ASSETS / "explainer.css").read_text(encoding="utf-8")
        self.assertIn(".hl{position:absolute", css)
        self.assertIn("background:rgba(var(--highlight-rgb),.08)", css)
        self.assertIn(".hl:hover,.hl.emphasis{background:rgba(var(--highlight-rgb),.32)", css)

    def test_pdf_click_toggles_pin_and_background_clears_it(self):
        js = (ASSETS / "explainer.js").read_text(encoding="utf-8")
        self.assertIn("const release=pinnedId===id", js)
        self.assertIn("togglePinnedProse(anchor.id)", js)
        self.assertIn("document.addEventListener('click'", js)
        self.assertIn("clearSelection()", js)

    def test_prose_hover_emphasizes_only_its_pdf_group(self):
        js = (ASSETS / "explainer.js").read_text(encoding="utf-8")
        self.assertIn("const emphasisId=hoveredId||selectedId", js)
        self.assertIn("link.addEventListener('mouseenter'", js)
        self.assertIn("hit.dataset.anchor===emphasisId", js)


class CrossPlatformEntryPointTests(unittest.TestCase):
    """run_pdfx.py must behave the same on Linux, macOS, and Windows."""

    LAUNCHER = Path(__file__).resolve().parents[1] / "run_pdfx.py"

    def _run(self, *args, extra_env=None):
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        env.update(extra_env or {})
        with TemporaryDirectory() as cwd:
            return subprocess.run(
                [sys.executable, str(self.LAUNCHER), *args],
                capture_output=True, cwd=cwd, env=env,
            )

    def test_launcher_runs_without_pythonpath_from_an_unrelated_cwd(self):
        proc = self._run("--version")
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        self.assertIn("pdfx 0.4.2", proc.stdout.decode("utf-8", "replace"))

    def test_unicode_output_survives_a_non_utf8_console(self):
        # A Japanese Windows console reports cp932, which cannot encode U+2080.
        with TemporaryDirectory() as d:
            wd = Path(d)
            (wd / "text").mkdir()
            (wd / "text" / "p01.txt").write_text(
                "The energy E₀ depends on α.\n日本語。\n",
                encoding="utf-8")
            (wd / "pdfx.json").write_text('{"pages": 1}', encoding="utf-8")
            proc = self._run("text", str(wd), extra_env={"PYTHONIOENCODING": "cp932"})
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        out = proc.stdout.decode("utf-8", "replace")
        self.assertIn("E₀", out)
        self.assertIn("日本語", out)


class FramedHostTests(unittest.TestCase):
    """The explainer is read inside the sandboxed iframes of Claude Desktop and
    chatgpt.app, where the document is about:srcdoc: replaceState throws
    SecurityError, and a fragment link that escapes is treated as navigating
    away from the reply rather than moving within the document.
    """
    def setUp(self):
        self.js = (ASSETS / "explainer.js").read_text(encoding="utf-8")
        self.lines = self.js.splitlines()

    def _block_after(self, needle, span):
        start = next(i for i, line in enumerate(self.lines) if needle in line)
        return " ".join(self.lines[start:start + span])

    def test_history_is_only_touched_inside_the_guarded_helper(self):
        self.assertEqual(self.js.count("history.replaceState"), 1)
        helper = self._block_after("function setHash(", 6)
        self.assertIn("history.replaceState", helper)
        self.assertIn("try{", helper)
        self.assertIn("catch(err)", helper)

    def test_every_hash_update_goes_through_the_helper(self):
        self.assertIn("setHash(hit.getAttribute('href'))", self.js)
        self.assertIn("setHash(link.getAttribute('href'))", self.js)
        self.assertNotIn("history.replaceState(null,'',hit", self.js)
        self.assertNotIn("history.replaceState(null,'',link", self.js)

    def test_fragment_links_are_cancelled_in_the_capture_phase(self):
        guard = next(line for line in self.lines if 'a[href^="#"]' in line)
        self.assertIn("preventDefault()", guard)
        self.assertIn("},true);", self.js)

    def test_media_jump_cancels_before_it_can_bail_out(self):
        handler = self.js.split("mediaJumps.forEach(")[1].split("});")[0]
        cancel = handler.index("event.preventDefault()")
        bail = handler.index("if(!anchor)return")
        self.assertLess(cancel, bail, "an unresolved media jump escapes to the host")

    def test_startup_tolerates_a_hash_the_host_left_behind(self):
        line = next(l for l in self.lines if "document.querySelector(location.hash)" in l)
        self.assertIn("try{", line)
        self.assertIn("catch(err)", line)


if __name__ == "__main__":
    unittest.main()
