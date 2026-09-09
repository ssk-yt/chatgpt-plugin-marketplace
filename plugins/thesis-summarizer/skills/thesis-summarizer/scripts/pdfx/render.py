"""Assemble the self-contained explainer HTML."""
from __future__ import annotations
import base64, html, json, re
from io import BytesIO
from pathlib import Path

from PIL import Image

ASSETS = Path(__file__).parent / "assets"

DOC = """<!DOCTYPE html>
<html lang="{lang}"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{css}</style></head>
<body>
<nav class="mobile-switch" aria-label="表示する内容">
  <a class="active" href="#article-pane" data-mobile-view="article">解説</a>
  <a href="#pdf-pane" data-mobile-view="pdf">原文</a>
</nav>
<div class="layout" data-mobile-pane="article">
<div class="col-left" id="article-pane">
{body}
</div>
<button type="button" class="splitter" role="separator" aria-label="解説とPDFの幅を調整" aria-orientation="vertical"></button>
<div class="col-right" id="pdf-pane">
<div class="pdf-pages">
{pages}
</div>
</div>
</div>
<script id="anchor-data" type="application/json">{data}</script>
<script>{js}</script>
</body></html>
"""


def _media_data_uri(workdir: Path, item) -> str:
    path = workdir / "pages" / f"p{item.page + 1:02d}.png"
    if not path.exists():
        raise SystemExit(f"content.md:{item.line}: rendered page image is missing: {path.name}")
    with Image.open(path) as source:
        x, y, width, height = item.crop
        left = round(source.width * x / 100)
        top = round(source.height * y / 100)
        right = round(source.width * (x + width) / 100)
        bottom = round(source.height * (y + height) / 100)
        cropped = source.crop((left, top, right, bottom))
        output = BytesIO()
        cropped.save(output, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")


def _media_html(block, workdir: Path) -> str:
    cards = []
    card_kind = "table" if block.title in {"table", "compare"} else "figure"
    for item in block.media:
        first = item.spans[0]
        plain_caption = " ".join(span.text for span in item.spans).strip()
        src = _media_data_uri(workdir, item)
        cards.append(
            f'<figure class="media-card media-{card_kind}">'
            f'<a class="media-jump" href="#source-{first.id}-1" data-anchor="{first.id}" '
            f'aria-label="原文の図表キャプションを表示">'
            f'<img src="{src}" alt="{html.escape(plain_caption, quote=True)}"></a>'
            f'<figcaption>{item.html}</figcaption></figure>'
        )
    layout = "media-compare" if block.title == "compare" else "media-single"
    return f'<div class="media-gallery {layout}">{"".join(cards)}</div>'


def body_html(blocks, workdir: Path) -> str:
    out = []
    for b in blocks:
        if b.kind in ("h1", "h2", "h3"):
            out.append(f"<{b.kind}>{b.html}</{b.kind}>")
        elif b.kind == "lead":
            out.append(f'<p class="lead">{b.html}</p>')
        elif b.kind == "p":
            out.append(f"<p>{b.html}</p>")
        elif b.kind in ("note", "deriv"):
            label = b.title or ("補足" if b.kind == "note" else "導出メモ")
            out.append(f'<div class="box {b.kind}"><div class="box-t">{label}</div>{b.html}</div>')
        elif b.kind == "media":
            out.append(_media_html(b, workdir))
    return "\n".join(out)


def write(workdir: str, blocks, anchors: list[dict], *, title: str | None = None,
          lang: str = "ja", hint: str = "左の下線付き語句をクリックすると、原文の該当箇所がハイライトされます。",
          pages_used: set[int] | None = None) -> Path:
    wd = Path(workdir)
    body = body_html(blocks, wd)

    if title is None:
        m = re.search(r"<h1>(.*?)</h1>", body, re.S)
        title = re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else "Linked explainer"

    imgs = sorted((wd / "pages").glob("p*.png"))
    overlays_by_page: dict[int, list[str]] = {}
    for anchor in anchors:
        rects = anchor.get("rects", [])
        for index, rect in enumerate(rects):
            if len(rect) != 4:
                continue
            left, top, width, height = rect
            label_suffix = f" {index + 1}" if len(rects) > 1 else ""
            overlay = (
                f'<a class="hl" id="source-{anchor["id"]}-{index + 1}" '
                f'href="#prose-{anchor["id"]}" data-anchor="{anchor["id"]}" '
                f'aria-label="対応する解説を表示{label_suffix}" '
                f'style="left:{left}%;top:{top}%;width:{width}%;height:{height}%"></a>'
            )
            overlays_by_page.setdefault(anchor["page"], []).append(overlay)
    parts = []
    for i, img in enumerate(imgs):
        if pages_used is not None and i not in pages_used:
            continue
        b64 = base64.b64encode(img.read_bytes()).decode("ascii")
        overlays = "".join(overlays_by_page.get(i, []))
        parts.append(f'  <div class="pdfpage" data-page="{i}"><div class="pnum">p.{i+1}</div>'
                     f'<img alt="page {i+1}" src="data:image/png;base64,{b64}">{overlays}</div>')

    html = DOC.format(
        lang=lang, title=title,
        css=(ASSETS / "explainer.css").read_text(encoding="utf-8"),
        js=(ASSETS / "explainer.js").read_text(encoding="utf-8"),
        body=body, hint=hint, pages="\n".join(parts),
        data=json.dumps(anchors, ensure_ascii=False),
    )
    out = wd / "out" / "explainer.html"
    out.write_text(html, encoding="utf-8")
    return out
