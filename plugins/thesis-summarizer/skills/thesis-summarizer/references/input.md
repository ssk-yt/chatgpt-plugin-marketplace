# Obtaining an attached PDF

The PDF must be a readable file in the environment that runs `pdfx init`.
An attachment badge, metadata, or a download URL does not prove that its bytes
are present there. Do not infer the execution location or available permissions
from the client device or the plugin's cache path.

1. Check whether the attached PDF already has a readable path in the current
   execution environment. Use it directly when available.
2. Otherwise, check the attachment and Library file tools actually available
   in this session. If an authorized tool can provide the attached file's
   bytes or a local copy, save it to a task-local input directory. Do not
   substitute a web copy of the paper without the user's direction: it may
   be a different version.
3. If the available file tool only supplies a download URL, try its supported
   download method. If networking is denied, request the narrow network
   permission when this environment supports requests, then retry once. If
   permission requests are unavailable or rejected, check the other available
   attachment or Library route before concluding that the PDF cannot be read.
4. Confirm that the resulting file is nonempty, can be opened as a PDF, and
   has at least one page. Only then run `pdfx init` and `pdfx text` on it.

A DNS failure, proxy failure, or `Operation not permitted` applies to the
specific method that failed. Do not turn it into a claim that every file route
is blocked, or that an app or workspace setting is definitely at fault.
Keep attempts bounded: do not repeatedly try the same failed route or change
the user's network, proxy, or security settings. If no authorized route works,
report the routes actually tried and their errors, then ask for an accessible
copy or path. Do not claim to have read or summarized the paper before the PDF
has passed the file check and extraction has succeeded.
