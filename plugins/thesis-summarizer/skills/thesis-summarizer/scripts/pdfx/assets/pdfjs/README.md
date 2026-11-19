# PDF.js runtime

The two gzip files are the unmodified `build/pdf.min.mjs` and
`build/pdf.worker.min.mjs` from Mozilla PDF.js / `pdfjs-dist` version 5.4.54.
They are included in experimental self-contained HTML output. The generated
HTML decompresses the modules in the browser and loads them through blob URLs;
it does not request a CDN or send the PDF over the network.

Source: https://github.com/mozilla/pdf.js
License: Apache License 2.0, reproduced in `LICENSE`.
