"""Resolve a verbatim phrase to bounding boxes on a PDF page.

Coordinates are returned as (x%, y%, w%, h%) of the page, origin top-left,
so the HTML can position highlights over a scaled page image.
"""
from __future__ import annotations
import difflib, re
from pathlib import Path

from .extract import load_meta
from .sources import load_index


class Doc:
    def __init__(self, workdir: str):
        import pypdfium2 as pdfium

        self.workdir = Path(workdir)
        self.meta = load_meta(workdir)
        self.pdf = pdfium.PdfDocument(self.meta["pdf"])
        self.n_pages = self.meta["pages"]
        self.sizes = self.meta["sizes"]
        self.source_index = load_index(workdir)
        self.source_units = {unit["id"]: unit for unit in self.source_index.get("units", [])}

    # ---------- text ----------
    def text(self, page0: int) -> str:
        return (self.workdir / "text" / f"p{page0+1:02d}.txt").read_text(encoding="utf-8")

    # ---------- search ----------
    def search(self, page0: int, phrase: str, occ: int = 0, limit: int = 12):
        """Return (rects, n_occurrences). rects is None when not found at `occ`.

        PDFium normalises whitespace, so a phrase that straddles a line break
        in the source is matched with a plain space.
        """
        page = self.pdf[page0]
        w, h = self.sizes[page0]
        tp = page.get_textpage()
        s = tp.search(phrase, match_case=False, match_whole_word=False)
        hits = []
        while len(hits) < limit:
            m = s.get_next()
            if not m:
                break
            idx, cnt = m
            rects = []
            for i in range(tp.count_rects(idx, cnt)):
                left, bottom, right, top = tp.get_rect(i)
                rects.append((
                    round(left / w * 100, 2),
                    round((h - top) / h * 100, 2),
                    round((right - left) / w * 100, 2),
                    round((top - bottom) / h * 100, 2),
                ))
            hits.append(rects)
        tp.close()
        if occ >= len(hits):
            return None, len(hits)
        return hits[occ], len(hits)

    def resolve(self, page0: int, phrases: list[str], occ: int = 0):
        """Union of every phrase's rects, merged per line. Returns (rects, misses)."""
        all_rects, misses = [], []
        for ph in phrases:
            r, cnt = self.search(page0, ph, occ)
            if r:
                all_rects.extend(r)
            else:
                misses.append(ph)
        return merge_line_rects(all_rects), misses

    def resolve_source_id(self, source_id: str):
        """Resolve a saved source unit directly from its PDF character range."""
        unit = self.source_units.get(source_id)
        if unit is None:
            return None, f"unknown source ID {source_id!r}; rerun pdfx text and use a listed ID"
        page0 = unit["page"]
        page = self.pdf[page0]
        width, height = self.sizes[page0]
        textpage = page.get_textpage()
        actual = textpage.get_text_range(unit["start"], unit["count"])
        if actual != unit["text"]:
            textpage.close()
            return None, f"stale source ID {source_id!r}; rerun pdfx init"
        rects = []
        for index in range(textpage.count_rects(unit["start"], unit["count"])):
            left, bottom, right, top = textpage.get_rect(index)
            rects.append((
                round(left / width * 100, 2),
                round((height - top) / height * 100, 2),
                round((right - left) / width * 100, 2),
                round((top - bottom) / height * 100, 2),
            ))
        textpage.close()
        return merge_line_rects(rects), None


    def highlighted_text(self, page0: int, rects) -> str:
        """The text actually inside the highlight boxes.

        This — not the search phrase — is what the reader sees covered, so it
        is what a span's claim has to be measured against.
        """
        if not rects:
            return ""
        page = self.pdf[page0]
        w, h = self.sizes[page0]
        tp = page.get_textpage()
        out = []
        for x, y, rw, rh in rects:
            left = x / 100 * w
            right = (x + rw) / 100 * w
            top = h - (y / 100 * h)
            bottom = h - ((y + rh) / 100 * h)
            try:
                out.append(tp.get_text_bounded(left=left, bottom=bottom,
                                               right=right, top=top))
            except Exception:
                pass
        tp.close()
        return " ".join(t.strip() for t in out if t and t.strip())

    # ---------- diagnostics ----------
    def suggest(self, page0: int, phrase: str, n: int = 3) -> list[str]:
        """Closest verbatim windows in the page's real text layer.

        Extraction noise (ligatures, soft hyphens, OCR artefacts) is the usual
        reason a phrase misses, so show what the page actually contains.
        """
        flat = re.sub(r"\s+", " ", self.text(page0))
        L = max(8, len(phrase))
        step = max(1, L // 8)
        best = []
        sm = difflib.SequenceMatcher(autojunk=False)
        sm.set_seq2(phrase.lower())
        for i in range(0, max(1, len(flat) - L), step):
            win = flat[i:i + L]
            sm.set_seq1(win.lower())
            if sm.quick_ratio() < 0.55:
                continue
            best.append((sm.ratio(), i, win))
        best.sort(reverse=True)
        out, taken = [], []
        for score, i, win in best:
            if any(abs(i - j) < L for j in taken):
                continue
            taken.append(i)
            out.append(f"{score:.2f}  …{flat[max(0,i-25):i+L+25]}…")
            if len(out) >= n:
                break
        return out


def merge_line_rects(rects, y_tol: float = 0.15):
    """Merge fragments PDFium reports as separate runs on the same text line."""
    if not rects:
        return []
    rects = sorted(rects, key=lambda r: (round(r[1] / y_tol), r[0]))
    merged = [list(rects[0])]
    for r in rects[1:]:
        cur = merged[-1]
        if abs(r[1] - cur[1]) < y_tol * 3:
            x0, x1 = min(cur[0], r[0]), max(cur[0] + cur[2], r[0] + r[2])
            y0, y1 = min(cur[1], r[1]), max(cur[1] + cur[3], r[1] + r[3])
            merged[-1] = [x0, y0, x1 - x0, y1 - y0]
        else:
            merged.append(list(r))
    return [tuple(round(v, 2) for v in m) for m in merged]
