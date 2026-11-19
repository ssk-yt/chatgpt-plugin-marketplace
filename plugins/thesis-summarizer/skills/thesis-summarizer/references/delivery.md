# Delivery and output checks

## Mobile and remote sessions

Attach the self-contained `.html` artifact as a file in the final response,
then confirm that the attachment opens when the available tools allow it. A
local filesystem path or `file://` URL alone is not delivery: it is not usable
on another device and does not establish that the file was saved to ChatGPT
Library. If attachment or opening cannot be verified, state that explicitly
instead of claiming Library delivery. Do not publicly host the artifact when
it embeds a copyrighted or private source PDF.

## Final integrity check

Before delivery, confirm that the generated HTML contains:

- mobile navigation to `#pdf-pane`;
- explanation links using `a.a`;
- PDF overlays using `a.hl`;
- display equations with MathML TeX annotations and the bundled LaTeX copy control;
- the expected figure and table media, with a page image definition for each
  `page-image-N` crop class.

If an expected element is absent, rebuild with the current bundled scripts.
Previously generated HTML files are not updated when the plugin is upgraded.
