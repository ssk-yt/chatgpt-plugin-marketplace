"""Parse content.md into blocks + spans.

Authoring syntax
    # H1                     title
    ## H2 / ### H3           section headings
    > text                   lead paragraph (boxed intro)
    :::note Title ... :::    grey supplement box (raw HTML allowed inside)
    :::deriv Title ... :::    green derivation box (raw HTML allowed inside)
    :::media figure ... :::  one cropped figure + linked caption
    :::media table ... :::   one cropped table + linked caption
    :::media compare ... ::: two cropped tables side by side
    = {{p3|source equation|TeX-like expression}}
                             linked equation block
    blank line               paragraph break

    {{p3|phrase|表示テキスト}}                one span, one source phrase
    {{p3|phrase A ;; phrase B|表示テキスト}}   one span, union of two phrases
    {{p3#2|phrase|表示テキスト}}              second occurrence on that page

Anchor ids are generated automatically (a001, a002, …) so there is no id
bookkeeping to get wrong.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field

from .mathml import render_inline_math

SPAN_RE = re.compile(r"\{\{\s*p(\d+)(?:#(\d+))?\s*\|(.+?)\|(.+?)\}\}", re.S)
PHRASE_SEP = ";;"
NUMBER = r"(?:\d+(?:\.\d+)?|\.\d+)"
CROP_RE = re.compile(
    rf"^@crop\s+p(\d+)\s+({NUMBER})\s+({NUMBER})\s+({NUMBER})\s+({NUMBER})\s*$"
)


@dataclass
class Span:
    id: str
    page: int          # 0-based
    occ: int           # 0-based occurrence index
    phrases: list[str]
    text: str          # visible (usually Japanese) text
    line: int          # source line in content.md, for error messages


@dataclass
class MediaItem:
    page: int          # 0-based source page containing the figure/table
    crop: tuple[float, float, float, float]  # x, y, width, height in percent
    html: str          # linked caption HTML
    spans: list[Span]
    line: int


@dataclass
class Block:
    kind: str          # h1 h2 h3 lead p note deriv media
    title: str = ""
    html: str = ""
    spans: list[Span] = field(default_factory=list)
    line: int = 0
    link_gaps: list[str] = field(default_factory=list)
    media: list[MediaItem] = field(default_factory=list)


class ParseError(SystemExit):
    pass


def parse(src: str) -> tuple[list[Block], list[Span]]:
    counter = [0]
    all_spans: list[Span] = []

    def expand(text: str, line: int) -> tuple[str, list[Span]]:
        spans: list[Span] = []
        out: list[str] = []
        position = 0
        for m in SPAN_RE.finditer(text):
            out.append(render_inline_math(text[position:m.start()]))
            counter[0] += 1
            aid = f"a{counter[0]:03d}"
            page = int(m.group(1)) - 1
            occ = int(m.group(2) or 1) - 1
            phrases = [p.strip() for p in m.group(3).split(PHRASE_SEP) if p.strip()]
            visible = m.group(4).strip()
            if page < 0:
                raise ParseError(f"content.md:{line}: page numbers are 1-based")
            if not phrases:
                raise ParseError(f"content.md:{line}: empty source phrase in {m.group(0)[:60]}")
            sp = Span(aid, page, occ, phrases, visible, line)
            spans.append(sp)
            all_spans.append(sp)
            # Real anchors keep the bidirectional link usable in HTML previews
            # that deliberately disable JavaScript (including some mobile apps).
            out.append(f'<a class="a" id="prose-{aid}" href="#source-{aid}-1" '
                       f'data-anchor="{aid}">{render_inline_math(visible)}</a>')
            position = m.end()
        out.append(render_inline_math(text[position:]))
        return "".join(out), spans

    blocks: list[Block] = []
    lines = src.splitlines()
    i, para, para_line = 0, [], 0

    def flush():
        nonlocal para
        if not para:
            return
        raw = "\n".join(para).strip()
        para = []
        if not raw:
            return
        prepared = _eq_lines(raw)
        html, spans = expand(prepared, para_line)
        blocks.append(Block("p", html=html, spans=spans, line=para_line,
                            link_gaps=_find_link_gaps(prepared)))

    while i < len(lines):
        ln = lines[i]
        s = ln.strip()

        if s.startswith(":::"):
            head = s[3:].strip()
            kind, _, title = head.partition(" ")
            kind = kind or "note"
            if kind not in ("note", "deriv", "media"):
                raise ParseError(f"content.md:{i+1}: unknown box type ':::{kind}' "
                                 f"(use ':::note', ':::deriv', or ':::media')")
            flush()
            body_line = i + 2
            body, i = [], i + 1
            while i < len(lines) and lines[i].strip() != ":::":
                body.append(lines[i])
                i += 1
            if i >= len(lines):
                raise ParseError(f"content.md: unclosed ':::{kind}' block "
                                 f"(missing a ':::' line)")
            i += 1
            if kind == "media":
                layout = title.strip().lower()
                blocks.append(_media_block(body, body_line, layout, expand))
                continue
            inner = _eq_lines("\n".join(body))
            html, spans = expand(inner, body_line)
            blocks.append(Block(kind, title=title.strip(), html=html, spans=spans,
                                line=body_line, link_gaps=_find_link_gaps(inner)))
            continue

        if s.startswith("#"):
            flush()
            level = len(s) - len(s.lstrip("#"))
            text = s[level:].strip()
            html, spans = expand(text, i + 1)
            blocks.append(Block(f"h{min(level,3)}", html=html, spans=spans, line=i + 1))
            i += 1
            continue

        if s.startswith(">"):
            flush()
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip()[1:].strip())
                i += 1
            lead_text = " ".join(buf)
            html, spans = expand(lead_text, i)
            blocks.append(Block("lead", html=html, spans=spans, line=i,
                                link_gaps=_find_link_gaps(lead_text)))
            continue

        if not s:
            flush()
            i += 1
            continue

        if not para:
            para_line = i + 1
        para.append(ln)
        i += 1

    flush()
    return blocks, all_spans


def _media_block(lines: list[str], body_line: int, layout: str, expand) -> Block:
    if layout not in {"figure", "table", "compare"}:
        raise ParseError(
            f"content.md:{body_line-1}: media type must be figure, table, or compare"
        )

    items: list[MediaItem] = []
    gaps: list[str] = []
    current: tuple[int, tuple[float, float, float, float], int] | None = None
    caption: list[str] = []

    def flush_item() -> None:
        nonlocal caption, current
        if current is None:
            if any(line.strip() for line in caption):
                raise ParseError(f"content.md:{body_line}: caption appears before @crop")
            caption = []
            return
        page, crop, line = current
        raw = "\n".join(caption).strip()
        if not raw:
            raise ParseError(f"content.md:{line}: every @crop needs a linked caption")
        html, spans = expand(raw, line + 1)
        if not spans:
            raise ParseError(f"content.md:{line+1}: media caption must contain a source anchor")
        if any(span.page != page for span in spans):
            raise ParseError(
                f"content.md:{line+1}: caption anchors must point to the cropped page p{page+1}"
            )
        gaps.extend(_find_link_gaps(raw))
        items.append(MediaItem(page, crop, html, spans, line))
        caption = []
        current = None

    for offset, raw_line in enumerate(lines):
        match = CROP_RE.fullmatch(raw_line.strip())
        if match:
            flush_item()
            page = int(match.group(1)) - 1
            crop = tuple(float(match.group(i)) for i in range(2, 6))
            x, y, width, height = crop
            line = body_line + offset
            if page < 0:
                raise ParseError(f"content.md:{line}: page numbers are 1-based")
            if (min(x, y) < 0 or width <= 0 or height <= 0
                    or x + width > 100 or y + height > 100):
                raise ParseError(
                    f"content.md:{line}: crop must be x y width height percentages inside the page"
                )
            current = (page, crop, line)
        else:
            caption.append(raw_line)
    flush_item()

    expected = 2 if layout == "compare" else 1
    if len(items) != expected:
        raise ParseError(
            f"content.md:{body_line-1}: :::media {layout} requires {expected} @crop item(s)"
        )
    return Block("media", title=layout, line=body_line, link_gaps=gaps, media=items)


def _eq_lines(text: str) -> str:
    out = []
    for ln in text.split("\n"):
        if ln.strip().startswith("= "):
            expression = ln.strip()[2:].strip()
            match = SPAN_RE.fullmatch(expression)
            if match:
                selector = f"p{match.group(1)}" + (f"#{match.group(2)}" if match.group(2) else "")
                expression = (f"{{{{{selector}|{match.group(3)}|"
                              f"\\({match.group(4).strip()}\\)}}}}")
            else:
                expression = f"\\({expression}\\)"
            out.append(f'<div class="eq">{expression}</div>')
        else:
            out.append(ln)
    return "\n".join(out)


def _find_link_gaps(text: str) -> list[str]:
    """Return lexical prose/equations left outside source-link spans."""
    gaps: list[str] = []
    for line in text.splitlines():
        remainder = SPAN_RE.sub(" ", line)
        remainder = re.sub(r"<[^>]+>", " ", remainder)
        remainder = remainder.replace("\\(", " ").replace("\\)", " ")
        remainder = re.sub(r"&(?:[A-Za-z]+|#\d+|#x[0-9A-Fa-f]+);", " ", remainder)
        remainder = re.sub(r"[\s\W_]+", " ", remainder, flags=re.UNICODE).strip()
        if re.search(r"[0-9A-Za-z\u3040-\u30ff\u3400-\u9fff]", remainder):
            gaps.append(remainder[:100])
    return gaps
