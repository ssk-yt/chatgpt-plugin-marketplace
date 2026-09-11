# Delivery and output checks

## Mobile and remote sessions

Attach the self-contained `.html` artifact to the response. A local filesystem
path or `file://` URL from the execution environment is not usable on another
device. Do not publicly host the artifact when it embeds a copyrighted or
private source PDF.

## Final integrity check

Before delivery, confirm that the generated HTML contains:

- mobile navigation to `#pdf-pane`;
- explanation links using `a.a`;
- PDF overlays using `a.hl`;
- the expected figure and table media.

If an expected element is absent, rebuild with the current bundled scripts.
Previously generated HTML files are not updated when the plugin is upgraded.
