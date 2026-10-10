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

    {{s3.12|表示テキスト}}                    preferred: one saved source unit
    {{p3|phrase|表示テキスト}}                legacy: one source phrase
    {{p3#2|phrase|表示テキスト}}              legacy: second occurrence

Anchor ids are generated automatically (a001, a002, …) so there is no id
bookkeeping to get wrong.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field

from .mathml import MathSyntaxError, render_inline_math

ID_SELECTOR_RE = re.compile(r"s(\d+)\.(\d+)")
LEGACY_SELECTOR_RE = re.compile(r"p(\d+)(?:#(\d+))?")
PHRASE_SEP = ";;"
NUMBER = r"(?:\d+(?:\.\d+)?|\.\d+)"
MAX_MEDIA_CROP_HEIGHT = 92.0
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
    source_id: str | None = None


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


@dataclass
class SourceToken:
    start: int
    end: int
    raw: str
    selector: str
    page: int
    occ: int
    phrases: list[str]
    visible: str
    source_id: str | None


def _top_level_fields(value: str) -> list[str]:
    fields: list[str] = []
    start = depth = 0
    for index, char in enumerate(value):
        escaped = index > 0 and value[index - 1] == "\\"
        if char == "{" and not escaped:
            depth += 1
        elif char == "}" and not escaped and depth:
            depth -= 1
        elif char == "|" and depth == 0:
            fields.append(value[start:index])
            start = index + 1
    fields.append(value[start:])
    return fields


def _source_tokens(text: str, line: int) -> list[SourceToken]:
    """Scan source anchors without mistaking TeX group braces for `}}`."""
    tokens: list[SourceToken] = []
    cursor = 0
    while True:
        start = text.find("{{", cursor)
        if start < 0:
            break
        index, depth, end = start + 2, 0, None
        while index < len(text):
            if text.startswith("}}", index) and depth == 0:
                end = index + 2
                break
            char = text[index]
            escaped = index > start + 2 and text[index - 1] == "\\"
            if char == "{" and not escaped:
                depth += 1
            elif char == "}" and not escaped:
                if depth == 0:
                    raise ParseError(f"content.md:{line}: unmatched '}}' in source anchor")
                depth -= 1
            index += 1
        if end is None:
            raise ParseError(f"content.md:{line}: unclosed source anchor")

        raw = text[start:end]
        fields = _top_level_fields(raw[2:-2].strip())
        selector = fields[0].strip() if fields else ""
        id_match = ID_SELECTOR_RE.fullmatch(selector)
        legacy_match = LEGACY_SELECTOR_RE.fullmatch(selector)
        if id_match and len(fields) == 2:
            source_id = selector
            page = int(id_match.group(1)) - 1
            occ = 0
            phrases: list[str] = []
            visible = fields[1].strip()
        elif legacy_match and len(fields) == 3:
            source_id = None
            page = int(legacy_match.group(1)) - 1
            occ = int(legacy_match.group(2) or 1) - 1
            phrases = [part.strip() for part in fields[1].split(PHRASE_SEP)
                       if part.strip()]
            visible = fields[2].strip()
        else:
            raise ParseError(f"content.md:{line}: invalid source anchor {raw[:80]}")
        if page < 0:
            raise ParseError(f"content.md:{line}: page numbers are 1-based")
        if source_id is None and not phrases:
            raise ParseError(f"content.md:{line}: empty source phrase in {raw[:80]}")
        tokens.append(SourceToken(start, end, raw, selector, page, occ,
                                  phrases, visible, source_id))
        cursor = end
    return tokens


def parse(src: str) -> tuple[list[Block], list[Span]]:
    counter = [0]
    all_spans: list[Span] = []

    def expand(text: str, line: int) -> tuple[str, list[Span]]:
        def render_checked(value: str, at: int) -> str:
            try:
                return render_inline_math(value)
            except MathSyntaxError as error:
                raise ParseError(f"content.md:{at}: {error}") from error

        spans: list[Span] = []
        out: list[str] = []
        position = 0
        for token in _source_tokens(text, line):
            source_line = line + text[:token.start].count("\n")
            out.append(render_checked(text[position:token.start], source_line))
            counter[0] += 1
            aid = f"a{counter[0]:03d}"
            sp = Span(aid, token.page, token.occ, token.phrases, token.visible,
                      source_line, token.source_id)
            spans.append(sp)
            all_spans.append(sp)
            # Real anchors keep the bidirectional link usable in HTML previews
            # that deliberately disable JavaScript (including some mobile apps).
            out.append(f'<a class="a" id="prose-{aid}" href="#source-{aid}-1" '
                       f'data-anchor="{aid}">{render_checked(token.visible, source_line)}</a>')
            position = token.end
        tail_line = line + text[:position].count("\n")
        out.append(render_checked(text[position:], tail_line))
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
        prepared = _eq_lines(raw, para_line)
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
            inner = _eq_lines("\n".join(body), body_line)
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
    seen_source_ids = set()
    for span in all_spans:
        if span.source_id is None:
            continue
        if span.source_id in seen_source_ids:
            raise ParseError(
                f"content.md:{span.line}: source ID {span.source_id!r} is reused; "
                "one source ID must map to exactly one explanation span"
            )
        seen_source_ids.add(span.source_id)
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
            if height > MAX_MEDIA_CROP_HEIGHT:
                raise ParseError(
                    f"content.md:{line}: crop height {height:g}% looks like a page capture; "
                    "crop tightly to the figure or table plus its caption, excluding body text"
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


def _eq_lines(text: str, start_line: int = 1) -> str:
    out = []
    for offset, ln in enumerate(text.split("\n")):
        if ln.strip().startswith("= "):
            line = start_line + offset
            expression = ln.strip()[2:].strip()
            tokens = _source_tokens(expression, line)
            if len(tokens) > 1:
                raise ParseError(
                    f"content.md:{line}: one display equation cannot cross source links; "
                    "write each source-linked equation as a complete '= {{source|TeX}}' line"
                )
            if tokens and (tokens[0].start != 0 or tokens[0].end != len(expression)):
                raise ParseError(
                    f"content.md:{line}: a display equation line must contain exactly one "
                    "complete source anchor"
                )
            if tokens and tokens[0].source_id:
                token = tokens[0]
                visible = token.visible
                if not visible:
                    raise ParseError(f"content.md:{line}: display equation has no TeX source")
                _reject_display_delimiters(visible, line)
                expression = f"{{{{{token.source_id}|\\({visible}\\)}}}}"
            elif tokens:
                token = tokens[0]
                visible = token.visible
                if not visible:
                    raise ParseError(f"content.md:{line}: display equation has no TeX source")
                _reject_display_delimiters(visible, line)
                expression = (f"{{{{{token.selector}|{PHRASE_SEP.join(token.phrases)}|"
                              f"\\({visible}\\)}}}}")
            else:
                _reject_display_delimiters(expression, line)
                expression = f"\\({expression}\\)"
            out.append(f'<div class="eq">{expression}</div>')
        else:
            out.append(ln)
    return "\n".join(out)


def _reject_display_delimiters(expression: str, line: int) -> None:
    if re.search(r"\\[()]|(?<!\\)\$", expression):
        raise ParseError(
            f"content.md:{line}: '= ' already creates display math; remove inline "
            "delimiters \\( \\) or $ from inside the source anchor"
        )


def _find_link_gaps(text: str) -> list[str]:
    """Return lexical prose/equations left outside source-link spans."""
    parts, position = [], 0
    for token in _source_tokens(text, 1):
        parts.append(text[position:token.start])
        parts.append(" ")
        position = token.end
    parts.append(text[position:])
    unlinked = "".join(parts)

    gaps: list[str] = []
    for line in unlinked.splitlines():
        remainder = line
        remainder = re.sub(r"<[^>]+>", " ", remainder)
        remainder = remainder.replace("\\(", " ").replace("\\)", " ")
        remainder = re.sub(r"&(?:[A-Za-z]+|#\d+|#x[0-9A-Fa-f]+);", " ", remainder)
        remainder = re.sub(r"[\s\W_]+", " ", remainder, flags=re.UNICODE).strip()
        if re.search(r"[0-9A-Za-z\u3040-\u30ff\u3400-\u9fff]", remainder):
            gaps.append(remainder[:100])
    return gaps
