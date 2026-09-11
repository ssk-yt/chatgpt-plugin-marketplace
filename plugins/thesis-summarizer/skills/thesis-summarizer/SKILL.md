---
name: thesis-summarizer
description: Summarizes a thesis or research-paper PDF into a researcher-facing Japanese HTML explainer with bidirectional links to exact PDF phrases, equations, figures, and tables. Use whenever the user invokes Thesis Summarizer, attaches this plugin with a PDF, or asks for a linked or annotated thesis or paper summary.
---

# Thesis Summarizer

This is already the active capability. Do not search for another Thesis
Summarizer tool or inspect plugin availability. Start the PDF workflow.

Produce one self-contained HTML explainer with detailed Japanese prose, TeX-like
equations, relevant figures and tables, and one-to-one bidirectional links
between short explanation spans and exact PDF source locations. The bundled
`pdfx` CLI performs extraction, coordinate resolution, rendering, and checks;
do not reimplement those mechanics.

## Runtime

```bash
SKILL_DIR=<directory containing this SKILL.md>
PYTHONPATH="$SKILL_DIR/scripts${PYTHONPATH:+:$PYTHONPATH}" python3 -m pdfx --version
```

Use that module form for every command. If `pypdfium2` or Pillow is missing,
install them into a task-local directory and prepend it to `PYTHONPATH`. Ask for
network permission when required; do not install system-wide.

## Workflow

### 1. Extract and read the complete paper

```bash
pdfx init paper.pdf -o work/
pdfx text work/
```

Read every page. `pdfx text` prints the complete text layer as short,
coordinate-addressable units such as `[s3.12]`. Preserve whole-paper coverage;
do not replace it with selective retrieval. Expect OCR noise, damaged ligatures,
and line-break artifacts in older PDFs.

### 2. Use the default explanation profile

Unless the user requests otherwise:

- Write in Japanese for a researcher who can follow graduate-level material.
- Explain the motivation, assumptions, method, results, limitations, and
  significance, not merely the abstract or conclusion.
- Supply the background needed to understand the paper.
- Derive important equations with defined symbols and meaningful intermediate
  steps. Clearly label reconstructed derivations that are not stated verbatim.
- Place relevant figures and tables next to the discussion that uses them.

Do not ask the user to choose language, depth, or coverage. Ask only when the
source is missing, unreadable, or the requirements conflict materially.

### 3. Write `work/content.md`

Read [references/authoring.md](references/authoring.md), then write the complete
explainer. The preferred source link is:

```text
{{s3.12|表示する日本語の短い主張}}
```

Maintain this invariant:

```text
one explanation span <-> one source ID <-> one contiguous PDF location
```

Never attach multiple source IDs to one span or reuse an ID. When a statement
depends on separated evidence, split it into short atomic claims, each with its
own ID. Multiple PDF rectangles are allowed only when one contiguous source
unit wraps across visual lines.

Every lexical part of ordinary prose, leads, notes, derivations, equations, and
captions must be linked. Headings, box titles, punctuation, and layout-only HTML
may remain unlinked.

### 4. Build

```bash
pdfx build work/
```

Source IDs resolve directly from saved PDF character ranges, without phrase
search. Fix every reported `SOURCE` or `UNLINKED` error. If legacy phrase links
or extraction problems require diagnosis, read
[references/troubleshooting.md](references/troubleshooting.md). Never ship with
`--allow-missing`.

### 5. Verify

Read [references/quality.md](references/quality.md), then run:

```bash
pdfx verify work/ --flagged-only
```

Inspect the reported coverage and every generated media crop. Correct the
content and rebuild until all text is linked, every source ID is unique, each
short claim is supported by its highlighted source unit, and each figure/table
crop contains only the media plus its original caption.

### 6. Deliver

Deliver `work/out/explainer.html` under a descriptive filename. It is
self-contained and includes the PDF pages. Do not publish a copyrighted PDF to
a hosted URL. For mobile/remote delivery and final output checks, read
[references/delivery.md](references/delivery.md). Preserve the bundled viewer
unless the user asks to change its design. When modifying viewer behavior, first read
[references/viewer.md](references/viewer.md).
