---
name: thesis-summarizer
description: Summarizes a thesis or research-paper PDF into a researcher-facing Japanese HTML explainer with bidirectional links to exact PDF phrases, equations, figures, and tables. Use whenever the user invokes Thesis Summarizer, attaches this plugin with a PDF, or asks for a linked or annotated thesis or paper summary.
---

# Thesis Summarizer

When this skill is loaded, it is already the active capability for the task.
Do not inspect plugin availability, search for a separate Thesis Summarizer
tool, or invoke plugin-management. Start the PDF workflow immediately. This is
a skill-driven workflow; the bundled `pdfx` CLI is its execution mechanism.

Produces one self-contained `.html` file (page images embedded as base64, opens
in any browser) with:

- **Left**: your explanation, in the target language, broken into small
  clickable spans.
- **Right**: the original PDF rendered page by page, stacked and scrollable.
- **Bidirectional click**: explanation highlights scroll the PDF to the exact
  source phrase, and PDF highlights scroll back to the corresponding prose.
- **Reading UI**: both panes scroll independently, their divider is draggable,
  and trackpad pinch zoom affects only the PDF pane without reflowing the page
  image or changing highlight coordinates.

The mechanics live in the bundled `pdfx` CLI (`scripts/`). **Do not
reimplement them inline** — writing throwaway extraction and probe scripts is
what makes this task slow. Your only job is to write `content.md`.

## Runtime setup

```bash
SKILL_DIR=<directory containing this SKILL.md>
PYTHONPATH="$SKILL_DIR/scripts${PYTHONPATH:+:$PYTHONPATH}" python3 -m pdfx --version
```

Use the module command above for every `pdfx` invocation; do not write a
wrapper into `/usr/local/bin`. If it reports a missing module, install into a
task-local dependency directory and prepend that directory to `PYTHONPATH`:

```bash
python3 -m pip install --target work/.pdfx-deps pypdfium2 pillow
PYTHONPATH="work/.pdfx-deps:$SKILL_DIR/scripts${PYTHONPATH:+:$PYTHONPATH}" python3 -m pdfx --version
```

Ask for network permission if the environment requires it. Never assume a
system-wide package install is available.
If `scripts/pdfx/` is not present at all, say so and fall back to writing the
pipeline by hand — but say it, don't silently do the slow thing.

## Workflow

### 1. Extract

```bash
pdfx init paper.pdf -o work/
pdfx text work/          # read every page — this is what you quote from
```

Read the whole text layer now. Old or scanned PDFs extract with ligature
damage, soft hyphens across line breaks (`Sub­stitution`) and OCR noise.
**Anchor phrases must match this noisy text, not the clean text a human reads
off the page image.**

### 2. Apply the default reading profile

Do not ask the user to choose language, audience, depth, background coverage,
or derivation coverage unless they explicitly request different settings. Use
this profile by default:

- Write the explanation in **Japanese**.
- Write at a **researcher-facing, technically detailed** level. Assume the
  reader can follow graduate-level mathematics and field terminology, while
  still defining paper-specific notation and uncommon concepts.
- Include the **background knowledge** needed to understand why the problem,
  assumptions, method, and result matter. Connect the paper to the relevant
  physical or mathematical framework rather than only paraphrasing paragraphs.
- Include **derivations of important equations**: define every symbol, state
  assumptions and approximations, show the meaningful intermediate steps, and
  explain the physical or mathematical interpretation of the result.
- Clearly distinguish derivations stated in the paper from supplementary
  derivations reconstructed for the reader. Never invent missing premises;
  label reasonable reconstruction as such.
- Bring the source PDF's relevant **figures and tables** into the explanation
  next to the passages that interpret them. Include the items and numbering
  the user requests; when no list is given, select the media needed to explain
  the paper's main argument and results. Put directly comparable tables in one
  comparison block. Do not collect media in a detached gallery at the end.

Proceed immediately with these defaults. Ask a question only when the source
file is missing or unreadable, or when the user has given mutually incompatible
requirements that materially affect the output.

### 3. Write `work/content.md` in one pass

```
# タイトル
> リード文（書誌情報など）

## 1. 節の見出し

本文中で原文に紐づけたい語句は {{p1|verbatim source phrase|表示テキスト}} と書く。
複数フレーズを一つのハイライトに: {{p1|phrase A ;; phrase B|表示テキスト}}
同一ページに同じフレーズが複数あるとき: {{p2#2|phrase|表示テキスト}}

:::note 補足のタイトル
枠内は HTML をそのまま書ける（<dl>, <ol>, <b> など）。
:::

:::deriv 導出メモのタイトル
{{p2|The conduction-band energy is obtained from|伝導帯エネルギーは次式で得られる}}。
= {{p2|E_CB = [E(G) + 3E(X) + 4E(L)] / 8|E_{CB} = \frac{E(G)+3E(X)+4E(L)}{8}}}
`= ` で始まる行は中央配置の数式ブロックになる。
:::

:::media figure
@crop p3 10 18 80 34
{{p3|FIG. A. Original caption text|図A　日本語の説明付きキャプション}}
:::

:::media table
@crop p7 18 24 64 58
{{p7|TABLE A. Original caption text|表A　日本語の説明付きキャプション}}
:::

:::media compare
@crop p9 8 20 84 34
{{p9|TABLE B. Original caption text|表B　比較対象}}
@crop p10 8 18 84 38
{{p10|TABLE C. Original caption text|表C　比較対象}}
:::
```

Page numbers are 1-based. Anchor ids are generated automatically, so there is
no id bookkeeping and no cross-reference check to get wrong.

Write equations with TeX-like notation. `\frac{a}{b}`, `\sqrt{x}`, subscripts,
superscripts, Greek commands such as `\lambda`, and common relation/operator
commands are rendered as semantic MathML, without a CDN. Inline math may be
written as `\(E_0 = \frac{1}{2}kQ_R^2\)` or `$E_0$` inside visible anchor text.

Every lexical part of the lead, ordinary paragraphs, note/derivation bodies,
and equation lines must be inside a `{{p...|source|visible text}}` anchor.
Headings, box titles, punctuation, and layout-only HTML may remain unanchored.
`pdfx build` and `pdfx verify` fail with `UNLINKED` if words, numbers, or
equations remain outside anchors. This is intentional: the entire explanation,
not only selected phrases, must be clickable back to its PDF evidence.

Media crop coordinates are `page x y width height`, all in page-relative
percentages. A crop must contain **only the complete figure or table and its
original caption**. Exclude surrounding body prose, equations, running headers,
footers, page numbers, and neighboring media. Find the whitespace boundary
immediately before and after the media, then leave only a small visual margin;
do not use a broad page crop as a shortcut. Crops taller than 92% of a page are
rejected as probable page captures. The caption must be fully wrapped in one
or more source anchors so selecting it opens the exact original caption on the
PDF page. Place each media block immediately after the explanation that first
needs it. Use `figure` for any ordinary figure, `table` for any standalone
table, and a two-item `compare` block for any pair that benefits from direct
visual comparison. The syntax is independent of document numbering.

On desktop, ordinary figures are centered at 80% of the explanation width and
tall table images at 60%. A comparison block places its two items side by side.
At 900 px and narrower, media expands to the available width and the comparison
stacks vertically for legibility. These are fixed viewer defaults; do not
override them with inline sizing.

**Write it straight through. Do not probe phrases one at a time first** —
`pdfx build` resolves every phrase and reports the failures with the
surrounding real text, which is faster and catches the same problems.

### The one hard rule

**One span = one short claim = one short, unique, verbatim source phrase
(roughly 5–15 words).** Do not wrap a sentence that paraphrases *several*
source clauses around a single clause's anchor — the highlight will visibly
under-cover what the span claims, and a careful reader notices.

```
BAD — one span, four source facts, anchored to one of them
{{p1|new structural models|第一原理計算に基づく新しい構造モデルを提案し、DX 形成の
エネルギー論と電子構造を調べ、結果を AlGaAs 合金に拡張した}}

GOOD — one span per clause, each with its own phrase
{{p1|propose new structural models|第一原理計算に基づく新しい構造モデルを提案し}}、
{{p1|energetics of DX formation|DX 形成のエネルギー論と電子構造を調べ}}、
{{p1|extended to the Al|結果を単純なモデルで AlGaAs 合金に拡張した}}。
```

### 4. Build

```bash
pdfx build work/
```

Every unmatched phrase is reported with the nearest real text on that page:

```
MISS  content.md:156 [a149] p3 'Substitution of Eqs. (4) and (5) in Eq. (13)'
      nearest: 0.98  …associated with DX. Sub­stitution of Eqs. (4) and (5) in Eq. (13) gives…
```

The fix is in the diagnostic — here, a soft hyphen inside `Substitution`, so
quote `of Eqs. (4) and (5) in Eq. (13)` instead. Shorter fragments survive
extraction noise far better than long ones. `AMBIG` means the phrase occurs
more than once on the page: extend it with adjacent context, or select the
occurrence with `#n`. Never ship with `--allow-missing`.

`UNLINKED` is a separate authoring error. Wrap the reported prose or equation
segment in an anchor (splitting it into short claims when necessary) before
resolving any `MISS` diagnostics.

Useful when you want to check one phrase before committing to it:

```bash
pdfx find work/ "some candidate phrase"
```

### 5. Verify — always, and cheaply

```bash
pdfx verify work/ --flagged-only
```

Verification also writes `work/out/media_crops.png`. Open that sheet and inspect
every tile at readable size. If any tile contains body text or an equation from
outside the figure/table, tighten its `@crop` coordinates, rebuild, and verify
again. Delivery is not complete until every media tile contains only the
figure/table and its caption.

This compares what each span *claims* against the text its highlight actually
*covers*, calibrated against the document's own median, and tiles the
suspicious ones into a couple of contact sheets:

```
180 spans; median claim/coverage ratio 1.08, flag above 2.38; 6 flagged
  WIDE   a129 content.md:144 p3 ratio=2.72
         claim  : このモードは非常に非調和的で、計算で使った 0.1 Å より小さい…
         covers : The mode is found to be very anharmonic
```

Read the sheets — **one image read per 8 anchors**, not one per anchor. Then:

- A span that claims a second clause the highlight does not cover → split it
  per the hard rule above. Widening the *search phrase* only helps if the
  longer text is literally contiguous in the source; it does not fix a
  semantic mismatch.
- Some flags are fine: explanatory prose carries grammatical framing the
  source does not. Judge from the `covers` line, not the ratio alone.

**Look at the page images for anything numeric you assert.** Superscripts,
exponents and charge states are routinely lost by text extraction — a claim
like "10^18 cm^-3" or "DX^-" read from `pdfx text` alone can be wrong. Crop
and read the region:

```bash
python3 -c "
import pypdfium2 as p; im=p.PdfDocument('paper.pdf')[2].render(scale=10).to_pil()
W,H=im.size; im.crop((int(.74*W),int(.65*H),int(.88*W),int(.67*H))).save('/tmp/z.png')"
```

### 6. Deliver

`work/out/explainer.html` is self-contained. Its default viewer intentionally
uses a compact sans-serif explanation, warm neutral colors, subtle persistent
highlights without underlines, and no document header or PDF toolbar. Preserve
this reading UI unless the user asks for another design. The responsive
contract is fixed: at **901 px and wider**, preserve the complete Codex desktop
reader as a two-column view with independently scrolling panes, a draggable
divider, and PDF-only zoom; at **900 px and narrower**, switch to the app-like
**解説 / 原文** tab view backed by native horizontal scroll snapping. A swipe,
tab selection, or bidirectional source link must animate the horizontal pane
change; source links must simultaneously scroll the destination pane to the
exact vertical target. Do not replace or simplify the desktop CSS merely
because the same plugin is also delivered through ChatGPT. Selecting an
explanation highlight opens the PDF tab, and selecting a PDF highlight returns
to the matching explanation. Explanation links have no fill at rest, an 8%
yellow fill on hover, and a 16% fill when pinned by clicking the matching PDF
region. PDF regions remain visible at 8% and the hovered or related region is
emphasized at 32%. Hovering prose previews only its PDF
region. Clicking a PDF region pins or replaces the corresponding prose
highlight, clicking the same region again releases it, and clicking ordinary
content or whitespace clears it. While the PDF is zoomed, its horizontal pan
takes priority over switching panes. Render
the tabs, explanation links, and PDF highlight overlays as real fragment links
in the HTML so these core actions still work when an app preview disables
JavaScript. JavaScript should only enhance them with inertial scrolling, zoom,
and swipe behavior. Copy it to the outputs directory
under a descriptive name and send it. If the PDF is a copyrighted article, the
file embeds its full pages — deliver it as a file, do not publish it to a
hosted URL.

Before delivery, inspect the **actual generated HTML file**, not only the
viewer templates. It must contain all four of these invariants:

- a mobile source-tab link with `href="#pdf-pane"`;
- explanation links rendered as `<a class="a" ... href="#source-...">`;
- pre-rendered PDF links rendered as `<a class="hl" ... href="#prose-...">`.
- each requested figure/table rendered as a base64 image inside
  `<figure class="media-card ...">`, followed by a linked `<figcaption>`.

If the output instead contains `<span class="a">`, lacks the mobile switch,
or creates all PDF highlights only at runtime, it is a legacy non-interactive
file: do not deliver or reuse it. Rebuild it with the current bundled scripts.
Updating or reinstalling the skill does not retroactively modify HTML files
that were generated earlier.

### Mobile and remote delivery

When the request comes from ChatGPT mobile or Remote, attach the generated
`.html` as a downloadable conversation artifact. A local absolute path or
`file://` link is not a valid delivery because the phone cannot reach the
computer's filesystem. Keep the HTML self-contained so the downloaded file can
be opened in a browser without a server. Do not host an embedded copyrighted
PDF merely to make a clickable URL; offer hosting only for user-owned or
publication-authorized material.

The standalone Codex skill and the plugin must ship the same `parse.py`,
`render.py`, `mathml.py`, `assets/explainer.css`, and `assets/explainer.js`.
When changing viewer behavior, update both copies and verify file parity before
delivery so the PC design does not drift from the ChatGPT plugin.

## Pitfalls

- **Search phrases use plain spaces, never `\n`.** PDFium normalises
  whitespace, so a phrase spanning a line break is found with a plain space.
- **Ligatures and hyphenation.** Quote the fragment before or after a line-end
  hyphen rather than the whole word.
- **Multi-column layouts** need no special handling; per-character coordinates
  are already correct. But note that `pdfx text` prints the *reading order*
  pdfium infers, which interleaves columns — never assume adjacency in that
  dump means adjacency on the page.
- **Anchors spanning two pages**: split into two spans, one per page.
- **Very long documents**: `pdfx build --only-used-pages` embeds only the pages
  an anchor points at; `pdfx init --dpi 120` shrinks the payload further.
