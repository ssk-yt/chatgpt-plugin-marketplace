# Math authoring and verification

Use these rules for every formula in `content.md`. The renderer accepts a
TeX-like subset and emits self-contained MathML.

## Inline math

Wrap each complete inline expression in `\(...\)` inside its source anchor:

```markdown
{{s3.12|電荷状態 \(q\) の欠陥 \(D^q\)}}
{{s3.13|補正エネルギー \(E_{\mathrm{corr}}\)}}
```

Ordinary parentheses are not math delimiters. Do not write `(D^q)`,
`(\rho_d)` or `(E_{\mathrm{corr}})` when MathML is intended. `$...$` remains
accepted for compatibility, but use `\(...\)` in new content.

Each source anchor must contain complete delimiter pairs. Never open math in
one anchor and close it in another.

## Display equations

A line beginning with `= ` is already a display-math context. Put exactly one
source anchor on that line and write only the TeX body inside it:

```markdown
= {{s5.27|E_{\mathrm{FNV}}=E_{\mathrm{PC}}-q\Delta V}}
```

Do not put `\(...\)` or `$...$` inside the anchor. Do not split one TeX
expression across two anchors. When an equation depends on separated source
locations, write multiple independent display lines, with a complete equation
and one source anchor on each line.

## TeX details

- Preserve the leading backslash in commands such as `\varepsilon`, `\lambda`,
  `\frac`, `\mathrm`, `\mathbf`, and `\boldsymbol`.
- Enclose signed or multi-character scripts in braces: use `L^{-5}`, not
  `L^-5`; use `E_{\mathrm{corr}}`, not `E_\mathrm{corr}`.
- `\mathbf{r}` and `\boldsymbol{\varepsilon}` are supported. Unicode math
  characters such as `𝐫` and `𝛆` are also acceptable.
- Keep each TeX expression wholly inside one explanation link so that the
  converter receives a continuous expression.

Unknown TeX commands are errors rather than silently rendered command names.
If a command is unsupported, rewrite it with supported notation or a Unicode
math character without changing the mathematical meaning.

## Required checks

Run both `pdfx build work/` and `pdfx verify work/ --flagged-only`. Fix every
`MATH` diagnostic. The generated HTML is also scanned for backslashes, script
markers, and likely command names visible outside `<math>` elements; none may
remain in a deliverable.

When visually reviewing the result, confirm that inline formulas are MathML,
display formulas contain no literal delimiters, long equations are not broken
across links, and negative exponents keep the complete exponent raised.
