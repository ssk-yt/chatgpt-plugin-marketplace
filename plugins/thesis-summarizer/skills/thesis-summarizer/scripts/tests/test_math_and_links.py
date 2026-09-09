import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from pdfx.mathml import render_inline_math, render_math
from pdfx.parse import ParseError, parse
from pdfx.render import ASSETS, body_html


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


class LinkCoverageTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
