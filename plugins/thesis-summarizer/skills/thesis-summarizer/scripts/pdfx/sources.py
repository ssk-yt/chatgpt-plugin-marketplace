"""Stable, coordinate-addressable source units for one extracted PDF."""
from __future__ import annotations

import json
import re
from pathlib import Path

INDEX_NAME = "sources.json"
MAX_UNIT_CHARS = 120
MIN_SPLIT_CHARS = 48


def _trimmed_range(text: str, start: int, end: int) -> tuple[int, int] | None:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return (start, end) if start < end else None


def _split_range(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """Split an unusually long visual line without changing source offsets."""
    out = []
    cursor = start
    while end - cursor > MAX_UNIT_CHARS:
        window_end = cursor + MAX_UNIT_CHARS
        window = text[cursor:window_end]
        candidates = [m.end() for m in re.finditer(r"(?:[.;:!?。！？]\s+|\s+)", window)]
        usable = [offset for offset in candidates if offset >= MIN_SPLIT_CHARS]
        cut = cursor + (usable[-1] if usable else MAX_UNIT_CHARS)
        trimmed = _trimmed_range(text, cursor, cut)
        if trimmed:
            out.append(trimmed)
        cursor = cut
    trimmed = _trimmed_range(text, cursor, end)
    if trimmed:
        out.append(trimmed)
    return out


def page_units(text: str, page0: int) -> list[dict]:
    """Create short units from visual text lines while preserving exact offsets."""
    ranges = []
    offset = 0
    for raw_line in text.splitlines(keepends=True):
        content_end = offset + len(raw_line.rstrip("\r\n"))
        trimmed = _trimmed_range(text, offset, content_end)
        if trimmed:
            ranges.extend(_split_range(text, *trimmed))
        offset += len(raw_line)
    if offset < len(text):
        trimmed = _trimmed_range(text, offset, len(text))
        if trimmed:
            ranges.extend(_split_range(text, *trimmed))

    return [
        {
            "id": f"s{page0 + 1}.{number}",
            "page": page0,
            "start": start,
            "count": end - start,
            "text": text[start:end],
        }
        for number, (start, end) in enumerate(ranges, 1)
    ]


def write_index(workdir: str | Path, page_texts: list[str]) -> dict:
    index = {
        "version": 1,
        "units": [unit for page0, text in enumerate(page_texts)
                  for unit in page_units(text, page0)],
    }
    path = Path(workdir) / INDEX_NAME
    path.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    return index


def load_index(workdir: str | Path) -> dict:
    path = Path(workdir) / INDEX_NAME
    if not path.exists():
        page_paths = sorted((Path(workdir) / "text").glob("p*.txt"))
        return write_index(workdir, [p.read_text(encoding="utf-8") for p in page_paths])
    return json.loads(path.read_text(encoding="utf-8"))


def units_for_page(index: dict, page0: int) -> list[dict]:
    return [unit for unit in index.get("units", []) if unit.get("page") == page0]
