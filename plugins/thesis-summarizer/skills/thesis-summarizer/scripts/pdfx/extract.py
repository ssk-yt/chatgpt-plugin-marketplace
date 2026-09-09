"""PDF -> per-page text + cached page images."""
from __future__ import annotations
import json, os
from pathlib import Path

SKELETON = """\
# タイトル

> リード文。原文の書誌情報など。

## 1. 最初の節

ここに解説を書く。原文に紐づけたい語句は {{p1|verbatim source phrase|表示される日本語}} と書く。
複数フレーズを一つのハイライトにまとめるときは {{p1|phrase A ;; phrase B|日本語}}。
同じフレーズが同一ページに複数あるときは {{p2#2|phrase|日本語}} のように出現番号を指定する。

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
    for i in range(n):
        page = pdf[i]
        sizes.append(list(page.get_size()))

        tp = page.get_textpage()
        (wd / "text" / f"p{i+1:02d}.txt").write_text(tp.get_text_range(), encoding="utf-8")
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
