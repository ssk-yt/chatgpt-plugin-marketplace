"""Post-build checks: coverage heuristics + contact sheets for visual review.

The failure mode this catches is the one a human notices instantly and a
build cannot: a span whose prose claims several source facts while its
anchor quotes only one of them, so the highlight visibly under-covers the
claim. Comparing the weight of the visible text against the length of the
quoted phrase flags those cheaply; only the flagged ones need eyeballing.
"""
from __future__ import annotations
import re
from pathlib import Path

CJK = re.compile(r"[　-ヿ㐀-鿿＀-￯]")
TAG = re.compile(r"<[^>]+>")

REL = 2.2      # flag a span whose ratio exceeds this multiple of the document median
ABS = 1.8      # ...but never flag anything below this absolute ratio
NARROW = 0.35  # highlight much larger than the claim -> maybe over-broad


def text_weight(visible: str) -> float:
    """Rough source-character equivalent of the visible explanatory text."""
    plain = TAG.sub("", visible)
    cjk = len(CJK.findall(plain))
    other = len(plain) - cjk
    return cjk * 2.3 + other


def coverage(spans, anchors_by_id: dict, doc=None) -> list[dict]:
    """Score every span by how much it claims versus how much it highlights.

    The ratio is calibrated against the document's own median, so it adapts to
    the language pair and writing density instead of relying on a fixed number.
    """
    rows = []
    for sp in spans:
        rects = anchors_by_id.get(sp.id, {}).get("rects", [])
        covered = doc.highlighted_text(sp.page, rects) if doc else ""
        src = len(covered) or sum(len(p) for p in sp.phrases)
        w = text_weight(sp.text)
        rows.append({
            "id": sp.id, "page": sp.page + 1, "line": sp.line,
            "ratio": round(w / src, 2) if src else 99.0, "flag": "",
            "text": TAG.sub("", sp.text), "phrases": sp.phrases,
            "covered": covered, "rects": rects,
        })

    ratios = sorted(r["ratio"] for r in rows)
    med = ratios[len(ratios) // 2] if ratios else 1.0
    cut = max(ABS, REL * med)
    for r in rows:
        if r["ratio"] > cut:
            r["flag"] = "WIDE"
        elif r["ratio"] < NARROW:
            r["flag"] = "NARROW"
    for r in rows:
        r["median"] = med
        r["cut"] = round(cut, 2)
    return rows


def contact_sheets(workdir: str, rows: list[dict], per_sheet: int = 8,
                   cols: int = 2, ctx: float = 3.2) -> list[Path]:
    """Crop each highlight with surrounding lines, tile into a few PNGs.

    Reviewing one tiled sheet costs a single look instead of one per anchor,
    which is what makes visual verification cheap enough to always do.
    """
    from PIL import Image, ImageDraw

    wd = Path(workdir)
    imgs = {i: wd / "pages" / f"p{i+1:02d}.png"
            for i in range(len(list((wd / "pages").glob("p*.png"))))}
    cache: dict[int, "Image.Image"] = {}
    tiles = []

    for r in rows:
        if not r["rects"]:
            continue
        p0 = r["page"] - 1
        if p0 not in cache:
            cache[p0] = Image.open(imgs[p0]).convert("RGB")
        im = cache[p0]
        W, H = im.size
        xs = [q[0] for q in r["rects"]]
        ys = [q[1] for q in r["rects"]]
        xe = [q[0] + q[2] for q in r["rects"]]
        ye = [q[1] + q[3] for q in r["rects"]]
        x0, y0, x1, y1 = min(xs), min(ys), max(xe), max(ye)

        cx0 = max(0, int((x0 - 6) / 100 * W))
        cx1 = min(W, int((x1 + 6) / 100 * W))
        cy0 = max(0, int((y0 - ctx) / 100 * H))
        cy1 = min(H, int((y1 + ctx) / 100 * H))
        if cx1 - cx0 < 60 or cy1 - cy0 < 30:
            continue
        crop = im.crop((cx0, cy0, cx1, cy1)).copy()
        d = ImageDraw.Draw(crop)
        for q in r["rects"]:
            d.rectangle([q[0] / 100 * W - cx0, q[1] / 100 * H - cy0,
                         (q[0] + q[2]) / 100 * W - cx0, (q[1] + q[3]) / 100 * H - cy0],
                        outline=(210, 20, 20), width=3)
        label = f'{r["id"]} p{r["page"]} r={r["ratio"]}{" " + r["flag"] if r["flag"] else ""}'
        tiles.append((label, crop))

    if not tiles:
        return []

    tw = max(t[1].width for t in tiles)
    th = max(t[1].height for t in tiles)
    tw, th = min(tw, 1100), min(th, 340)
    pad, hdr = 10, 20
    rows_n = (per_sheet + cols - 1) // cols
    out = []
    for s in range(0, len(tiles), per_sheet):
        chunk = tiles[s:s + per_sheet]
        sheet = Image.new("RGB",
                          (cols * (tw + pad) + pad,
                           rows_n * (th + hdr + pad) + pad),
                          (250, 250, 248))
        d = ImageDraw.Draw(sheet)
        for k, (label, crop) in enumerate(chunk):
            c, rr = k % cols, k // cols
            x = pad + c * (tw + pad)
            y = pad + rr * (th + hdr + pad)
            d.text((x, y + 4), label, fill=(30, 30, 30))
            if crop.width > tw or crop.height > th:
                crop = crop.copy()
                crop.thumbnail((tw, th))
            sheet.paste(crop, (x, y + hdr))
        p = Path(workdir) / "out" / f"sheet_{s // per_sheet + 1:02d}.png"
        sheet.save(p)
        out.append(p)
    return out
