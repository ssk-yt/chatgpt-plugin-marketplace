"""PDF -> per-page text + cached page images."""
from __future__ import annotations
import json, os
from pathlib import Path

SKELETON = """\
# タイトル

> リード文。原文の書誌情報など。

## 1. 最初の節

ここに解説を書く。原文ID `s1.1` に紐づける語句は {{s1.1|表示される日本語}} と書く。
1つの解説spanには1つの原文IDだけを使い、複数根拠は短い主張へ分割する。

:::note 補足のタイトル
枠の中は HTML をそのまま書ける。<b>強調</b> や <dl>/<ol> も使える。
:::

:::deriv 導出メモのタイトル
= E_CB = [E(G) + 3E(X) + 4E(L)] / 8
"= " で始まる行は数式ブロックになる。
:::
"""


def init(pdf_path: str, workdir: str, dpi: int = 165, force: bool = False) -> dict:
    import pypdfium2 as pdfium

    wd = Path(workdir)
    (wd / "text").mkdir(parents=True, exist_ok=True)
    (wd / "pages").mkdir(parents=True, exist_ok=True)
    (wd / "out").mkdir(parents=True, exist_ok=True)

    pdf = pdfium.PdfDocument(pdf_path)
    n = len(pdf)
    sizes = []
    page_texts = []
    for i in range(n):
        page = pdf[i]
        sizes.append(list(page.get_size()))

        tp = page.get_textpage()
        text = tp.get_text_range()
        page_texts.append(text)
        (wd / "text" / f"p{i+1:02d}.txt").write_text(text, encoding="utf-8")
        tp.close()

        img = wd / "pages" / f"p{i+1:02d}.png"
        if force or not img.exists():
            page.render(scale=dpi / 72).to_pil().save(img)

    meta = {
        "pdf": os.path.abspath(pdf_path),
        "dpi": dpi,
        "pages": n,
        "sizes": sizes,
    }
    (wd / "pdfx.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    from .sources import write_index
    write_index(wd, page_texts)

    content = wd / "content.md"
    if not content.exists():
        content.write_text(SKELETON, encoding="utf-8")
    return meta


def load_meta(workdir: str) -> dict:
    p = Path(workdir) / "pdfx.json"
    if not p.exists():
        raise SystemExit(f"not a pdfx work directory (no pdfx.json): {workdir}\n"
                         f"run:  pdfx init <paper.pdf> -o {workdir}")
    return json.loads(p.read_text(encoding="utf-8"))
