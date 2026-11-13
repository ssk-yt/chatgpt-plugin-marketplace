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
<style>{css}\n{page_css}</style></head>
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


def _page_image(path: Path) -> tuple[str, int, int]:
    """Keep the smaller of the source PNG and a high-quality WebP copy."""
    png = path.read_bytes()
    with Image.open(path) as source:
        width, height = source.size
        try:
            output = BytesIO()
            source.save(output, format="WEBP", quality=95, method=6)
            webp = output.getvalue()
        except (OSError, ValueError):  # WebP support is optional in Pillow builds.
            webp = b""
    if webp and len(webp) < len(png):
        mime, data = "image/webp", webp
    else:
        mime, data = "image/png", png
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}", width, height


def _crop_geometry(workdir: Path, item) -> tuple[int, int, int, int, int, int]:
    path = workdir / "pages" / f"p{item.page + 1:02d}.png"
    if not path.exists():
        raise SystemExit(f"content.md:{item.line}: rendered page image is missing: {path.name}")
    with Image.open(path) as source:
        page_width, page_height = source.size
        x, y, width, height = item.crop
        left = round(page_width * x / 100)
        top = round(page_height * y / 100)
        right = round(page_width * (x + width) / 100)
        bottom = round(page_height * (y + height) / 100)
    return left, top, max(1, right - left), max(1, bottom - top), page_width, page_height


def _media_html(block, workdir: Path) -> str:
    cards = []
    card_kind = "table" if block.title in {"table", "compare"} else "figure"
    for item in block.media:
        first = item.spans[0]
        plain_caption = " ".join(span.text for span in item.spans).strip()
        left, top, width, height, page_width, page_height = _crop_geometry(workdir, item)
        size_x, size_y = page_width / width * 100, page_height / height * 100
        pos_x = left / (page_width - width) * 100 if page_width > width else 0
        pos_y = top / (page_height - height) * 100 if page_height > height else 0
        crop_style = (f'aspect-ratio:{width}/{height};background-size:{size_x:.8g}% '
                      f'{size_y:.8g}%;background-position:{pos_x:.8g}% {pos_y:.8g}%')
        cards.append(
            f'<figure class="media-card media-{card_kind}">'
            f'<a class="media-jump" href="#source-{first.id}-1" data-anchor="{first.id}" '
            f'aria-label="原文の図表キャプションを表示">'
            f'<div class="media-crop page-image-{item.page}" role="img" '
            f'aria-label="{html.escape(plain_caption, quote=True)}" '
            f'style="{crop_style}"></div></a>'
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
    page_css = []
    for i, img in enumerate(imgs):
        if pages_used is not None and i not in pages_used:
            continue
        src, width, height = _page_image(img)
        page_css.append(f'.page-image-{i}{{background-image:url("{src}")}}')
        overlays = "".join(overlays_by_page.get(i, []))
        parts.append(f'  <div class="pdfpage" data-page="{i}"><div class="pnum">p.{i+1}</div>'
                     f'<div class="page-surface page-image-{i}" role="img" '
                     f'aria-label="原文PDF {i+1}ページ" style="aspect-ratio:{width}/{height}"></div>'
                     f'{overlays}</div>')

    html = DOC.format(
        lang=lang, title=title,
        css=(ASSETS / "explainer.css").read_text(encoding="utf-8"),
        page_css="\n".join(page_css),
        js=(ASSETS / "explainer.js").read_text(encoding="utf-8"),
        body=body, hint=hint, pages="\n".join(parts),
        data=json.dumps(anchors, ensure_ascii=False),
    )
    out = wd / "out" / "explainer.html"
    out.write_text(html, encoding="utf-8")
    return out
