# pdfx

Builds a two-column HTML explainer from a PDF: your prose on the left, the
rendered PDF on the right, and clicking any phrase in the prose highlights the
exact source text it came from — using the PDF's real text-layer coordinates,
not an estimate.

    pip install pypdfium2 pillow      # pypdfium2 is Apache-2.0/BSD; avoid AGPL PyMuPDF

    pdfx init paper.pdf -o work/      # extract text, cache page images
    pdfx text work/                   # read all indexed source units
    pdfx build work/                  # content.md -> work/out/explainer.html
    pdfx verify work/                 # coverage heuristics + contact sheets
    pdfx find work/ "some phrase"     # probe one phrase, with near-miss hints

## Module map

| file          | responsibility |
|---------------|----------------|
| `cli.py`      | argparse subcommands, diagnostics formatting |
| `extract.py`  | PDF → `text/pNN.txt`, `pages/pNN.png`, `pdfx.json` |
| `anchors.py`  | phrase → page rects; `suggest()` for near-misses; `highlighted_text()` |
| `parse.py`    | `content.md` → blocks + spans (`{{p3\|phrase\|表示}}`) |
| `mathml.py`   | inline/block TeX-like notation → semantic MathML |
| `render.py`   | blocks + anchors → one self-contained HTML file |
| `verify.py`   | claim-vs-coverage ratio, contact-sheet tiling |
| `assets/`     | `explainer.css`, `explainer.js` — edit these to restyle output |

## Authoring contract

All lexical explanation text and every equation must be source-linked. Headings,
box titles, punctuation, and layout-only HTML are exempt. Both `build` and
`verify` report `UNLINKED` and stop when words or numbers remain outside an
anchor.

    {{s1.3|リンクされた本文。数式 \(E_0\) も使用できる}}
    = {{s1.4|E_0 = \frac{1}{2}kQ_R^2}}

`pdfx init` writes `sources.json`, and `pdfx text` prints its short source IDs.
Each ID stores one exact PDF character range and resolves directly to its PDF
coordinates without phrase search. One ID may be used by exactly one explanation
span. `pdfx text --raw` and the older `{{p1|phrase|text}}` syntax remain available
as a compatibility fallback.

The TeX-like subset supports fractions, square roots, subscripts, superscripts,
Greek letters, and common operators. It is rendered to MathML locally, so the
generated HTML remains self-contained and does not load a CDN.

PDF page crops use page-relative percentages and are embedded into the output.
Each crop must contain only the figure or table and its caption, without body
prose, equations, headers, footers, or neighboring media:

    :::media figure
    @crop p3 10 18 80 34
    {{p3|FIG. A. Original caption|図A　リンク付きキャプション}}
    :::

Use `:::media table` for a single tall table and `:::media compare` with exactly
two `@crop` items for a side-by-side comparison. Figures default to 80% width,
tall tables to 60%, and both expand responsively on mobile. Every caption must
contain a source anchor.

`pdfx verify` writes `out/media_crops.png`, a contact sheet of all authored
crops. Inspect every tile and tighten `@crop` coordinates until only the media
and caption remain. Nearly full-page crops are rejected.

At mobile widths, the explanation and PDF panes form a native horizontal
scroll-snap carousel. Swiping, selecting a tab, or following a bidirectional
source link animates between panes; source links simultaneously scroll the
destination pane vertically to the matched phrase.

Explanation links are unfilled at rest, use an 8% yellow tint on hover, and
use a 16% tint only when pinned from the PDF. PDF source regions remain marked
at 8%, rising to 32% for the hovered or currently related region. Hovering explanation
text previews its PDF region; clicking a PDF region pins or replaces its prose
selection, clicking it again toggles the pin off, and clicking ordinary page
content clears the selection. Bidirectional navigation remains unchanged.

## Extending

* **Restyle the output** — edit `assets/explainer.css` / `explainer.js`. Nothing
  else needs to change; `render.py` inlines whatever is there.
* **New block type** (e.g. a warning box) — add the marker to `parse.py`'s
  `:::` branch and a rule in `render.py:body_html` + CSS.
* **Different anchor syntax** — `parse.SPAN_RE` is the single source of truth.
* **Other verification rules** — add a function in `verify.py` returning rows
  with `id`/`flag`/`ratio` and wire it into `cli.cmd_verify`.
* **Non-PDF sources** — `extract.py` and `anchors.Doc` are the only pdfium
  users; swapping in another backend means implementing `text()`, `search()`
  and `highlighted_text()`.
