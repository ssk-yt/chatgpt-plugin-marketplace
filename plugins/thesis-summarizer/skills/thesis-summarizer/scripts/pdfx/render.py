"""Assemble the self-contained explainer HTML."""
from __future__ import annotations
import base64, html, json, re
from io import BytesIO
from pathlib import Path

from PIL import Image

from .extract import load_meta

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
{viewer_assets}
<script>{js}</script>
{viewer_js}
</body></html>
"""

PDFJS_ASSETS = ASSETS / "pdfjs"


def _embedded_pdfjs_assets(pdf_path: Path) -> str:
    """Bundle the PDF and pinned PDF.js runtime into an offline HTML document."""
    resources = (
        ("pdf-source-data", pdf_path),
        ("pdfjs-main-gzip", PDFJS_ASSETS / "pdf.min.mjs.gz"),
        ("pdfjs-worker-gzip", PDFJS_ASSETS / "pdf.worker.min.mjs.gz"),
    )
    return "\n".join(
        f'<script id="{name}" type="application/octet-stream">'
        f'{base64.b64encode(path.read_bytes()).decode("ascii")}</script>'
        for name, path in resources
    )


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


def _fallback_page_image(path: Path) -> str:
    """Small page preview for hosts that do not run the PDF.js module."""
    with Image.open(path) as source:
        source = source.convert("RGB")
        source.thumbnail((612, 792), Image.Resampling.LANCZOS)
        output = BytesIO()
        try:
            source.save(output, format="WEBP", quality=48, method=6)
            mime = "image/webp"
        except (OSError, ValueError):
            output = BytesIO()
            source.save(output, format="JPEG", quality=65, optimize=True)
            mime = "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(output.getvalue()).decode('ascii')}"


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


def _crop_image(workdir: Path, item) -> str:
    path = workdir / "pages" / f"p{item.page + 1:02d}.png"
    left, top, width, height, _, _ = _crop_geometry(workdir, item)
    with Image.open(path) as page:
        crop = page.crop((left, top, left + width, top + height))
        png = BytesIO()
        crop.save(png, format="PNG")
        webp = BytesIO()
        try:
            crop.save(webp, format="WEBP", quality=95, method=6)
        except (OSError, ValueError):
            pass
    if webp.tell() and webp.tell() < png.tell():
        mime, data = "image/webp", webp.getvalue()
    else:
        mime, data = "image/png", png.getvalue()
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def _media_html(block, workdir: Path, viewer: str = "raster") -> str:
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
        if viewer == "pdfjs":
            crop_markup = (
                f'<img class="media-crop" src="{_crop_image(workdir, item)}" '
                f'alt="{html.escape(plain_caption, quote=True)}" '
                f'width="{width}" height="{height}">'
            )
        else:
            crop_markup = (
                f'<div class="media-crop page-image-{item.page}" role="img" '
                f'aria-label="{html.escape(plain_caption, quote=True)}" '
                f'style="{crop_style}"></div>'
            )
        cards.append(
            f'<figure class="media-card media-{card_kind}">'
            f'<a class="media-jump" href="#source-{first.id}-1" data-anchor="{first.id}" '
            f'aria-label="原文の図表キャプションを表示">'
            f'{crop_markup}</a>'
            f'<figcaption>{item.html}</figcaption></figure>'
        )
    layout = "media-compare" if block.title == "compare" else "media-single"
    return f'<div class="media-gallery {layout}">{"".join(cards)}</div>'


def body_html(blocks, workdir: Path, viewer: str = "raster") -> str:
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
            out.append(_media_html(b, workdir, viewer))
    return "\n".join(out)


def write(workdir: str, blocks, anchors: list[dict], *, title: str | None = None,
          lang: str = "ja", hint: str = "左の下線付き語句をクリックすると、原文の該当箇所がハイライトされます。",
          pages_used: set[int] | None = None, viewer: str = "raster") -> Path:
    if viewer not in {"raster", "pdfjs"}:
        raise ValueError(f"unsupported PDF viewer: {viewer}")
    wd = Path(workdir)
    body = body_html(blocks, wd, viewer)

    if title is None:
        m = re.search(r"<h1>(.*?)</h1>", body, re.S)
        title = re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else "Linked explainer"

    meta = load_meta(workdir) if viewer == "pdfjs" else None
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
    page_numbers = range(meta["pages"]) if meta else range(len(imgs))
    for i in page_numbers:
        if pages_used is not None and i not in pages_used:
            continue
        if viewer == "raster":
            src, width, height = _page_image(imgs[i])
            page_css.append(f'.page-image-{i}{{background-image:url("{src}")}}')
            surface = (f'<div class="page-surface page-image-{i}" role="img" '
                       f'aria-label="原文PDF {i+1}ページ" style="aspect-ratio:{width}/{height}"></div>')
        else:
            width, height = meta["sizes"][i]
            preview = _fallback_page_image(imgs[i])
            page_css.append(f'.page-preview-{i}{{background-image:url("{preview}")}}')
            surface = (f'<div class="page-surface pdfjs-surface page-preview-{i}" role="img" '
                       f'aria-label="原文PDF {i+1}ページ" style="aspect-ratio:{width}/{height}"></div>')
        overlays = "".join(overlays_by_page.get(i, []))
        parts.append(f'  <div class="pdfpage" data-page="{i}"><div class="pnum">p.{i+1}</div>'
                     f'{surface}'
                     f'{overlays}</div>')

    viewer_assets = _embedded_pdfjs_assets(Path(meta["pdf"])) if meta else ""
    viewer_js = (f'<script type="module">'
                 f'{(ASSETS / "pdfjs-viewer.mjs").read_text(encoding="utf-8")}'
                 f'</script>') if meta else ""

    html = DOC.format(
        lang=lang, title=title,
        css=(ASSETS / "explainer.css").read_text(encoding="utf-8"),
        page_css="\n".join(page_css),
        js=(ASSETS / "explainer.js").read_text(encoding="utf-8"),
        body=body, hint=hint, pages="\n".join(parts),
        data=json.dumps(anchors, ensure_ascii=False),
        viewer_assets=viewer_assets, viewer_js=viewer_js,
    )
    out = wd / "out" / "explainer.html"
    out.write_text(html, encoding="utf-8")
    return out
