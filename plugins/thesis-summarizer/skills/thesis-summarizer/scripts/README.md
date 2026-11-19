# pdfx

Builds a two-column HTML explainer from a PDF: your prose on the left, the
rendered PDF on the right, and clicking any phrase in the prose highlights the
exact source text it came from — using the PDF's real text-layer coordinates,
not an estimate.

    pdfx init paper.pdf -o work/      # PDF.js text and coordinates; Node.js only
    pdfx init paper.pdf -o work-pdfium/ --backend pdfium  # optional raster fallback
    pdfx text work/                   # read all indexed source units
    pdfx build work/                  # content.md -> work/out/explainer.html
    pdfx build work/ --viewer pdfjs   # test PDF.js viewer with PDFium extraction
    pdfx verify work/                 # coverage checks; PDFium adds contact sheets
    pdfx find work/ "some phrase"     # probe one phrase, with near-miss hints

`<PY>` is `python3` on macOS and Linux, `python` or `py -3` on Windows. There is
no `pdfx` executable on `PATH`; run each command through the launcher, which
needs no `PYTHONPATH` and works the same in bash, zsh, PowerShell, and cmd:

    <PY> "<this directory>/run_pdfx.py" init paper.pdf -o work/

`<PY> -m pdfx` also works when `PYTHONPATH` already includes this directory.

## Module map

| file          | responsibility |
|---------------|----------------|
| `run_pdfx.py` | cross-platform entry point; sets `sys.path`, then calls `cli.main` |
| `cli.py`      | argparse subcommands, diagnostics formatting, UTF-8 output |
| `extract.py`  | PDF.js or PDFium extraction → `text/pNN.txt`, `pdfx.json` |
| `assets/pdfjs-extract.mjs` | PDF.js text units and coordinates in Node.js |
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

Inline math uses `\(...\)`. A line beginning with `= ` is already display math,
so its single source anchor contains the TeX body without another delimiter.
Display expressions cannot span anchors. Unknown commands, unbraced signed
scripts such as `^-5`, and visible TeX residue outside MathML stop the build.

PDF page crops use page-relative percentages. The output embeds each page image
once, choosing the smaller of its PNG and a high-quality WebP encoding. Figure
and table crops reuse that image through CSS rather than duplicating its bytes;
the crop and the original page remain visible without JavaScript.
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

The PDF.js backend (`init`, followed by `build`)
extracts text and coordinates with the bundled PDF.js runtime under Node.js
(20.16+ or 22.3+).
It does not require `pypdfium2`, Pillow, or a package download. The HTML
embeds the original PDF and PDF.js modules, then renders pages and figure/table
crops in the browser. This full route needs browser JavaScript, `DecompressionStream`,
and blob module URLs. `verify` checks text/link coverage but cannot make image
contact sheets; inspect the generated crops in the HTML preview. The viewer
creates selectable PDF.js text only for pages near the visible PDF pane and
removes offscreen text layers. Dragging selects source text; a click on a
highlighted source still jumps to the matching explanation.

The separate `build --viewer pdfjs` option on a PDFium-initialized directory
changes only the viewer. It retains small static page previews and embedded
figure/table crops, so it still needs the Python packages during generation.
Use the PDFium raster fallback when the preview host cannot run PDF.js.

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
* **Non-PDF sources** — add an extractor and corresponding `anchors.Doc`
  resolver for source IDs and highlight coverage.
