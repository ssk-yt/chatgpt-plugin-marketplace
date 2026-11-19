# Quality verification

The explanation must cover the complete paper while keeping every linked span
small enough that its highlighted source visibly supports what it claims.

Run `pdfx verify work/ --flagged-only`. Review flags by comparing `claim` and
`covers`; split any span that asserts more than the highlighted unit supports.
Some grammatical framing is acceptable, but additional scientific claims are
not. Check numeric statements against the rendered page because superscripts,
exponents, and charge states may be lost in extraction.

With the PDFium fallback backend, verification writes `work/out/media_crops.png`.
Open it at readable size and
inspect every tile. Each tile must contain only the complete figure or table
and its original caption. Exclude surrounding prose, equations, headers,
footers, page numbers, and neighboring media. Tighten `@crop` coordinates and
repeat build and verification when any contamination remains. Crops taller
than 92% of a page are rejected as probable page captures.

With the PDF.js backend, inspect each crop in the generated HTML instead;
the crop is drawn in browser JavaScript and no static contact sheet is created.

Ordinary figures render centered at 80% of the explanation width; tall tables
at 60%. Comparison items are side by side on desktop and stacked on mobile.
Do not override these defaults in authored content.
