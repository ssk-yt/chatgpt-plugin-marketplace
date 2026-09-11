# Troubleshooting

`SOURCE` means the ID is absent or its saved character range is stale. Copy an
ID exactly from `pdfx text`; if the work directory predates source IDs or the
PDF changed, rerun `pdfx init`.

`UNLINKED` means words, numbers, or equations remain outside source anchors.
Wrap them in source-ID anchors and split broad claims into smaller spans.

The legacy phrase syntax remains available for PDFs whose text layer cannot be
indexed reliably:

```text
{{p3|exact source phrase|表示テキスト}}
{{p3#2|repeated phrase|2番目の出現に対応するテキスト}}
```

Use `pdfx text work/ --raw` to see exact extracted bytes and `pdfx find work/
"phrase"` to test a legacy phrase. Short exact fragments tolerate OCR and
ligature damage better. `MISS` is a legacy phrase that did not match; `AMBIG`
requires more context or an occurrence number. Do not use `--allow-missing` in
deliverables.
