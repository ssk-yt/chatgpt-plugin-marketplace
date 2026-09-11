"""pdfx command line."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

from . import __version__


def _c(s, code):
    return f"\033[{code}m{s}\033[0m" if sys.stdout.isatty() else s


def cmd_init(a):
    from .extract import init
    meta = init(a.pdf, a.out, dpi=a.dpi, force=a.force)
    print(f"{meta['pages']} pages @ {a.dpi} dpi -> {a.out}/")
    print(f"  text/    extracted text layer (read this before writing prose)")
    print(f"  pages/   cached page images")
    print(f"  content.md   <- write the explainer here")
    return 0


def cmd_text(a):
    from .extract import load_meta
    from .sources import load_index, units_for_page
    meta = load_meta(a.workdir)
    index = load_index(a.workdir)
    pages = [a.page] if a.page else range(1, meta["pages"] + 1)
    for p in pages:
        t = (Path(a.workdir) / "text" / f"p{p:02d}.txt").read_text(encoding="utf-8")
        print(f"===== page {p} ({len(t)} chars) =====")
        if a.raw:
            print(t)
        else:
            for unit in units_for_page(index, p - 1):
                print(f'[{unit["id"]}] {unit["text"]}')
    return 0


def cmd_find(a):
    from .anchors import Doc
    doc = Doc(a.workdir)
    pages = [a.page] if a.page else range(1, doc.n_pages + 1)
    hit = False
    for p in pages:
        rects, n = doc.search(p - 1, a.phrase)
        if n:
            hit = True
            print(f"p{p}  occurrences={n}  rects={rects}")
    if not hit:
        print(f"not found: {a.phrase!r}")
        for p in pages:
            sug = doc.suggest(p - 1, a.phrase)
            if sug:
                print(f"  nearest on p{p}:")
                for s in sug:
                    print(f"    {s}")
        return 1
    return 0


def _resolve_all(doc, spans):
    anchors, problems = [], []
    for sp in spans:
        if sp.source_id:
            rects, error = doc.resolve_source_id(sp.source_id)
            if error:
                problems.append(("SOURCE", sp, error))
                rects = []
            anchors.append({"id": sp.id, "page": sp.page, "rects": rects})
            continue
        rects, misses = doc.resolve(sp.page, sp.phrases, sp.occ)
        for ph in misses:
            problems.append(("MISS", sp, ph))
        for ph in sp.phrases:
            _, n = doc.search(sp.page, ph, 0)
            if n > 1 and sp.occ == 0:
                problems.append(("AMBIG", sp, f"{ph}  ({n} occurrences; use #n to pick)"))
        anchors.append({"id": sp.id, "page": sp.page, "rects": rects})
    return anchors, problems


def _report_link_gaps(blocks):
    gaps = [(block.line, gap) for block in blocks for gap in block.link_gaps]
    for line, gap in gaps:
        print(_c(f"UNLINKED content.md:{line}", "31"), repr(gap))
    if gaps:
        print(_c(f"\n{len(gaps)} unlinked prose/equation segment(s). "
                 "Wrap every lexical part in source anchors; punctuation may remain outside.", "31"))
    return gaps


def _validate_pages(doc, blocks, spans):
    for sp in spans:
        if sp.page >= doc.n_pages:
            raise SystemExit(f"content.md:{sp.line}: page {sp.page+1} does not exist "
                             f"(document has {doc.n_pages} pages)")
    for block in blocks:
        for item in block.media:
            if item.page >= doc.n_pages:
                raise SystemExit(f"content.md:{item.line}: crop page {item.page+1} does not exist "
                                 f"(document has {doc.n_pages} pages)")


def cmd_build(a):
    from .anchors import Doc
    from .parse import parse
    from . import render

    wd = Path(a.workdir)
    src = (wd / "content.md").read_text(encoding="utf-8")
    blocks, spans = parse(src)
    if _report_link_gaps(blocks):
        return 1
    doc = Doc(a.workdir)

    _validate_pages(doc, blocks, spans)

    anchors, problems = _resolve_all(doc, spans)

    misses = [p for p in problems if p[0] in {"MISS", "SOURCE"}]
    ambig = [p for p in problems if p[0] == "AMBIG"]

    for kind, sp, detail in ambig:
        print(_c(f"AMBIG content.md:{sp.line} [{sp.id}] p{sp.page+1}", "33"), detail)
    for kind, sp, detail in misses:
        label = "SOURCE" if kind == "SOURCE" else "MISS"
        print(_c(f"{label:6s} content.md:{sp.line} [{sp.id}] p{sp.page+1}", "31"),
              repr(detail))
        if kind == "MISS":
            for s in doc.suggest(sp.page, detail):
                print(f"      nearest: {s}")

    if misses and not a.allow_missing:
        print(_c(f"\n{len(misses)} source anchor(s) could not be resolved. "
                 f"Fix them in content.md and rebuild.", "31"))
        print("For source IDs, use an ID printed by pdfx text. For legacy phrases, "
              "quote a shorter exact fragment from pdfx text --raw.")
        return 1

    pages_used = None
    if a.only_used_pages:
        pages_used = {sp.page for sp in spans}
        pages_used.update(item.page for block in blocks for item in block.media)
    out = render.write(a.workdir, blocks, anchors, title=a.title,
                       pages_used=pages_used)
    (wd / "out" / "anchors.json").write_text(
        json.dumps([{**an, "text": sp.text, "source_id": sp.source_id,
                     "phrases": sp.phrases, "line": sp.line}
                    for an, sp in zip(anchors, spans)], ensure_ascii=False, indent=1),
        encoding="utf-8")
    kb = out.stat().st_size / 1024
    print(_c(f"OK  {len(anchors)} anchors resolved, 0 missing -> {out} ({kb:.0f} KB)", "32"))
    return 0


def cmd_verify(a):
    from .anchors import Doc
    from .parse import parse
    from . import verify as V

    wd = Path(a.workdir)
    blocks, spans = parse((wd / "content.md").read_text(encoding="utf-8"))
    if _report_link_gaps(blocks):
        return 1
    doc = Doc(a.workdir)
    _validate_pages(doc, blocks, spans)
    anchors, problems = _resolve_all(doc, spans)
    by_id = {x["id"]: x for x in anchors}
    rows = V.coverage(spans, by_id, doc)
    media_sheet = V.media_contact_sheet(a.workdir, blocks)

    ranked = sorted(rows, key=lambda r: -r["ratio"])
    flagged = [r for r in ranked if r["flag"] == "WIDE"]
    med, cut = rows[0]["median"], rows[0]["cut"]
    print(f"{len(rows)} spans; median claim/coverage ratio {med}, flag above {cut}; "
          f"{len(flagged)} flagged")
    print("(WIDE = the prose claims more than the highlight actually covers)")
    for r in ranked[:a.top]:
        mark = _c(f'{r["flag"] or "ok":6s}', "33" if r["flag"] else "0")
        print(f'  {mark} {r["id"]} content.md:{r["line"]} p{r["page"]} ratio={r["ratio"]}')
        print(f'         claim  : {r["text"][:72]}')
        print(f'         covers : {r["covered"][:72]}')

    target = flagged if (a.flagged_only and flagged) else ranked
    if a.sample and len(target) > a.sample:
        step = max(1, len(target) // a.sample)
        target = target[::step][:a.sample]

    if not a.no_sheets:
        sheets = V.contact_sheets(a.workdir, target, per_sheet=a.per_sheet)
        print(f"\n{len(sheets)} contact sheet(s) covering {len(target)} anchors:")
        for s in sheets:
            print(f"  {s}")
        print("legend (id -> claim):")
        for r in target:
            print(f'  {r["id"]}  {r["text"][:60]}')
    if media_sheet:
        print(f"\nmedia crop review sheet:\n  {media_sheet}")
        print("Confirm that every tile contains only the figure or table and its caption; "
              "body prose, equations, headers, and footers must be absent.")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="pdfx", description=__doc__)
    p.add_argument("--version", action="version", version=f"pdfx {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    q = sub.add_parser("init", help="extract text + cache page images from a PDF")
    q.add_argument("pdf")
    q.add_argument("-o", "--out", required=True, help="work directory to create")
    q.add_argument("--dpi", type=int, default=165)
    q.add_argument("--force", action="store_true", help="re-render cached page images")
    q.set_defaults(fn=cmd_init)

    q = sub.add_parser("text", help="print the extracted text layer")
    q.add_argument("workdir")
    q.add_argument("-p", "--page", type=int)
    q.add_argument("--raw", action="store_true",
                   help="print raw text without coordinate-addressable source IDs")
    q.set_defaults(fn=cmd_text)

    q = sub.add_parser("find", help="probe one phrase against the text layer")
    q.add_argument("workdir")
    q.add_argument("phrase")
    q.add_argument("-p", "--page", type=int)
    q.set_defaults(fn=cmd_find)

    q = sub.add_parser("build", help="content.md -> out/explainer.html")
    q.add_argument("workdir")
    q.add_argument("--title")
    q.add_argument("--allow-missing", action="store_true")
    q.add_argument("--only-used-pages", action="store_true",
                   help="embed only pages an anchor points at (smaller file)")
    q.set_defaults(fn=cmd_build)

    q = sub.add_parser("verify", help="coverage heuristics + contact sheets")
    q.add_argument("workdir")
    q.add_argument("--sample", type=int, default=16,
                   help="max anchors to put on sheets (0 = all)")
    q.add_argument("--top", type=int, default=10,
                   help="how many highest-ratio spans to print")
    q.add_argument("--flagged-only", action="store_true",
                   help="sheet only the anchors the heuristic flagged")
    q.add_argument("--per-sheet", type=int, default=8)
    q.add_argument("--no-sheets", action="store_true")
    q.set_defaults(fn=cmd_verify)

    a = p.parse_args(argv)
    return a.fn(a)
