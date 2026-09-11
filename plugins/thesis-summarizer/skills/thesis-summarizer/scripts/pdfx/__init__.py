"""pdfx — build a two-column HTML explainer whose prose links to exact PDF phrases.

Layout of a work directory:
    pdfx.json      metadata (source pdf, dpi, page sizes)
    text/pNN.txt   extracted text layer, one file per page
    pages/pNN.png  rendered page images (cache; reused across builds)
    content.md     the authoring file YOU write
    out/           explainer.html, contact sheets
"""
__version__ = "0.3.0"
