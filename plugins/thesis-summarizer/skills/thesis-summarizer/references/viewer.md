# Viewer contract

At widths of 901px and above, keep the two independently scrolling panes and
draggable divider. Trackpad pinch zoom affects only the PDF pane. At 900px and
below, use the 解説 / 原文 horizontal scroll-snap tabs. Swipes, tab selections,
and source links animate pane navigation and also scroll to the vertical target.

Explanation links are clear at rest, 8% yellow on hover, and 16% when pinned
from the PDF. PDF regions stay visible at 8% and rise to 32% when hovered or
related. PDF clicks pin or replace the corresponding prose highlight; clicking
the same region or ordinary whitespace clears it. Hovering prose emphasizes
only its PDF counterpart.

Keep tabs, prose links, and PDF overlays as real fragment links so core
navigation survives previews that disable JavaScript. JavaScript may enhance
scrolling, zoom, and swipe behavior but must not be the only navigation path.
Page images and figure/table crops share one embedded image per page through
CSS; keep crops visible when JavaScript is disabled.

PDF.js is the default for newly initialized work directories. It uses the
bundled PDF.js 5.4.54 for text rectangles and
browser rendering, without PDFium or Pillow. Figure/table crops are drawn
from the PDF.js page canvas. Selectable text layers are created only near the
visible pages; text selection must not trigger a source link. This route
requires browser JavaScript and has no
static page-image fallback. Check each source highlight and crop in the
intended preview host before delivery, and verify that source text can be
selected while a plain click on highlighted text still returns to the prose.

`pdfx build work/ --viewer pdfjs` on a PDFium-initialized directory changes
only the viewer. It retains low-resolution page previews and static crop
images, and still needs PDFium/Pillow to generate the HTML.
