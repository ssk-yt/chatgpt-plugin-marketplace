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
