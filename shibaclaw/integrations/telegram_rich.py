"""Telegram markdown/HTML and rich-message body builders (pure helpers)."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

_RE_MD_BOLD1 = re.compile(r"\*\*(.+?)\*\*")
_RE_MD_BOLD2 = re.compile(r"__(.+?)__")
_RE_MD_STRIKE = re.compile(r"~~(.+?)~~")
_RE_MD_INLINE = re.compile(r"`([^`]+)`")
_RE_MD_BLOCK = re.compile(r"```[\w]*\n?([\s\S]*?)```")
_RE_MD_TABLE = re.compile(r"^\s*\|.+\|")
_RE_MD_TABLE_SEP = re.compile(r"^:?-+:?$")
_RE_MD_HEADER = re.compile(r"^#{1,6}\s+(.+)$", flags=re.MULTILINE)
_RE_MD_BLOCKQUOTE = re.compile(r"^>\s*(.*)$", flags=re.MULTILINE)
_RE_MD_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_RE_MD_BOLD_ITALIC = re.compile(r"\*\*\*(.+?)\*\*\*")
_RE_MD_ITALIC = re.compile(r"(?<![^\W_])_([^_]+)_(?![^\W_])")
_RE_MD_BULLET = re.compile(r"^[-*]\s+", flags=re.MULTILINE)

# Rich Messages auto-blocks heuristics (math / GFM tables / image collages).
_RE_RICH_DISPLAY_MATH = re.compile(r"\$\$(.+?)\$\$", re.DOTALL)
_RE_RICH_MATH_FENCE = re.compile(r"```math\s*\n([\s\S]*?)```", re.IGNORECASE)
_RE_RICH_IMG = re.compile(
    r"!\[([^\]]*)\]\((https?://[^)\s]+)(?:\s+\"([^\"]*)\")?\)"
)
_RE_RICH_TABLE_SEP_LINE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")


def _rich_should_use_blocks(text: str) -> bool:
    """True when content has constructs better sent as explicit rich blocks."""
    if not text:
        return False
    if _RE_RICH_DISPLAY_MATH.search(text) or _RE_RICH_MATH_FENCE.search(text):
        return True
    if "<tg-collage>" in text.lower() or "<tg-slideshow>" in text.lower():
        return True
    imgs = _RE_RICH_IMG.findall(text)
    if len(imgs) >= 2:
        return True
    lines = text.splitlines()
    for i, line in enumerate(lines[:-1]):
        if "|" in line and _RE_RICH_TABLE_SEP_LINE.match(lines[i + 1] or ""):
            return True
    return False


def _rich_parse_table_block(lines: list[str], start: int) -> tuple[dict[str, Any] | None, int]:
    """Parse a GFM pipe-table starting at *start*. Returns (block, next_index)."""
    if start >= len(lines) or "|" not in lines[start]:
        return None, start
    if start + 1 >= len(lines) or not _RE_RICH_TABLE_SEP_LINE.match(lines[start + 1]):
        return None, start
    rows: list[list[str]] = []
    i = start
    while i < len(lines) and "|" in lines[i]:
        if i == start + 1 and _RE_RICH_TABLE_SEP_LINE.match(lines[i]):
            i += 1
            continue
        cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
        rows.append(cells)
        i += 1
        if i < len(lines) and not lines[i].strip():
            break
    if not rows:
        return None, start
    width = max(len(r) for r in rows)
    sep = lines[start + 1]
    aligns: list[str] = []
    for raw in sep.strip().strip("|").split("|"):
        cell = raw.strip()
        if cell.startswith(":") and cell.endswith(":"):
            aligns.append("center")
        elif cell.endswith(":"):
            aligns.append("right")
        else:
            aligns.append("left")
    while len(aligns) < width:
        aligns.append("left")
    cells_out: list[list[dict[str, Any]]] = []
    for r_idx, row in enumerate(rows):
        padded = row + [""] * (width - len(row))
        cells_out.append(
            [
                {
                    "text": cell,
                    "align": aligns[c_idx],
                    "valign": "top",
                    **({"is_header": True} if r_idx == 0 else {}),
                }
                for c_idx, cell in enumerate(padded)
            ]
        )
    return {
        "type": "table",
        "cells": cells_out,
        "is_bordered": True,
    }, i


def _rich_flush_prose(buf: list[str], blocks: list[dict[str, Any]]) -> None:
    """Turn accumulated prose lines into heading/pre/paragraph/divider blocks."""
    chunk = "\n".join(buf).strip("\n")
    buf.clear()
    if not chunk.strip():
        return
    for part in re.split(r"\n{2,}", chunk):
        part = part.strip("\n")
        if not part.strip():
            continue
        lines = part.splitlines()
        if len(lines) == 1 and lines[0].strip() in ("---", "***", "___"):
            blocks.append({"type": "divider"})
            continue
        m = re.match(r"^(#{1,6})\s+(.+)$", lines[0].strip())
        if m and len(lines) == 1:
            blocks.append(
                {
                    "type": "heading",
                    "text": m.group(2).strip(),
                    "size": min(6, len(m.group(1))),
                }
            )
            continue
        if lines[0].startswith("```"):
            lang = lines[0][3:].strip() or None
            body_lines = lines[1:]
            if body_lines and body_lines[-1].strip() == "```":
                body_lines = body_lines[:-1]
            block: dict[str, Any] = {"type": "pre", "text": "\n".join(body_lines)}
            if lang:
                block["language"] = lang
            blocks.append(block)
            continue
        blocks.append({"type": "paragraph", "text": part})


def build_rich_message_body(text: str) -> dict[str, Any]:
    """Build InputRichMessage body: markdown by default, blocks for math/table/collage.

    ponytail: only switch to blocks when heuristics fire; prose stays as paragraph strings.
    """
    src = text or ""
    if not _rich_should_use_blocks(src):
        return {"markdown": src}

    # Normalize math fences to $$ for one scanner.
    normalized = _RE_RICH_MATH_FENCE.sub(lambda m: f"$${m.group(1).strip()}$$", src)

    blocks: list[dict[str, Any]] = []
    prose: list[str] = []
    lines = normalized.splitlines(keepends=False)
    i = 0
    while i < len(lines):
        line = lines[i]

        # Display math on its own or embedded — peel $$...$$ from the line stream.
        if "$$" in line or (line.strip().startswith("$$")):
            # Consume a math block that may span lines.
            joined = "\n".join(lines[i:])
            m = _RE_RICH_DISPLAY_MATH.search(joined)
            if m and m.start() == 0:
                _rich_flush_prose(prose, blocks)
                blocks.append(
                    {
                        "type": "mathematical_expression",
                        "expression": m.group(1).strip(),
                    }
                )
                consumed = m.end()
                # Advance by number of lines covered.
                covered = joined[:consumed].count("\n") + 1
                i += covered
                continue
            # Math not at start of remaining text — fall through to prose with split below.

        table, next_i = _rich_parse_table_block(lines, i)
        if table is not None:
            _rich_flush_prose(prose, blocks)
            blocks.append(table)
            i = next_i
            continue

        # Cluster of consecutive image markdowns → collage (need ≥2).
        imgs: list[tuple[str, str, str]] = []
        j = i
        while j < len(lines):
            im = _RE_RICH_IMG.fullmatch(lines[j].strip())
            if not im:
                break
            imgs.append((im.group(1) or "", im.group(2), im.group(3) or ""))
            j += 1
        if len(imgs) >= 2:
            _rich_flush_prose(prose, blocks)
            photo_blocks: list[dict[str, Any]] = []
            for alt, url, _title in imgs:
                photo: dict[str, Any] = {
                    "type": "photo",
                    "photo": {"type": "photo", "media": url},
                }
                if alt:
                    photo["caption"] = {"text": alt}
                photo_blocks.append(photo)
            blocks.append({"type": "collage", "blocks": photo_blocks})
            i = j
            continue

        # Single image → photo block (only when already in blocks mode).
        im_one = _RE_RICH_IMG.fullmatch(line.strip())
        if im_one:
            _rich_flush_prose(prose, blocks)
            photo = {
                "type": "photo",
                "photo": {"type": "photo", "media": im_one.group(2)},
            }
            if im_one.group(1):
                photo["caption"] = {"text": im_one.group(1)}
            blocks.append(photo)
            i += 1
            continue

        # Inline $$math$$ inside a prose line → split.
        if "$$" in line:
            _rich_flush_prose(prose, blocks)
            pos = 0
            for m in _RE_RICH_DISPLAY_MATH.finditer(line):
                before = line[pos : m.start()]
                if before.strip():
                    blocks.append({"type": "paragraph", "text": before})
                blocks.append(
                    {
                        "type": "mathematical_expression",
                        "expression": m.group(1).strip(),
                    }
                )
                pos = m.end()
            after = line[pos:]
            if after.strip():
                prose.append(after)
            i += 1
            continue

        prose.append(line)
        i += 1

    _rich_flush_prose(prose, blocks)
    if not blocks:
        return {"markdown": src}
    return {"blocks": blocks}


def _strip_md(s: str) -> str:
    """Strip markdown inline formatting from text."""
    s = _RE_MD_BOLD1.sub(r"\1", s)
    s = _RE_MD_BOLD2.sub(r"\1", s)
    s = _RE_MD_STRIKE.sub(r"\1", s)
    s = _RE_MD_INLINE.sub(r"\1", s)
    return s.strip()


def _render_table_box(table_lines: list[str]) -> str:
    """Convert markdown pipe-table to compact aligned text for <pre> display."""

    def dw(s: str) -> int:
        return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in s)

    rows: list[list[str]] = []
    has_sep = False
    for line in table_lines:
        cells = [_strip_md(c) for c in line.strip().strip("|").split("|")]
        if all(_RE_MD_TABLE_SEP.match(c) for c in cells if c):
            has_sep = True
            continue
        rows.append(cells)
    if not rows or not has_sep:
        return "\n".join(table_lines)
    ncols = max(len(r) for r in rows)
    for r in rows:
        r.extend([""] * (ncols - len(r)))
    widths = [max(dw(r[c]) for r in rows) for c in range(ncols)]

    def dr(cells: list[str]) -> str:
        return "  ".join(f"{c}{' ' * (w - dw(c))}" for c, w in zip(cells, widths))

    out = [dr(rows[0])]
    out.append("  ".join("─" * w for w in widths))
    for row in rows[1:]:
        out.append(dr(row))
    return "\n".join(out)


def _markdown_to_telegram_html(text: str) -> str:
    """
    Convert markdown to Telegram-safe HTML.
    """
    if not text:
        return ""
    code_blocks: list[str] = []

    def save_code_block(m: re.Match) -> str:
        code_blocks.append(m.group(1))
        return f"\x00CB{len(code_blocks) - 1}\x00"

    text = _RE_MD_BLOCK.sub(save_code_block, text)
    lines = text.split("\n")
    rebuilt: list[str] = []
    li = 0
    while li < len(lines):
        if _RE_MD_TABLE.match(lines[li]):
            tbl: list[str] = []
            while li < len(lines) and _RE_MD_TABLE.match(lines[li]):
                tbl.append(lines[li])
                li += 1
            box = _render_table_box(tbl)
            if box != "\n".join(tbl):
                code_blocks.append(box)
                rebuilt.append(f"\x00CB{len(code_blocks) - 1}\x00")
            else:
                rebuilt.extend(tbl)
        else:
            rebuilt.append(lines[li])
            li += 1
    text = "\n".join(rebuilt)
    inline_codes: list[str] = []

    def save_inline_code(m: re.Match) -> str:
        inline_codes.append(m.group(1))
        return f"\x00IC{len(inline_codes) - 1}\x00"

    text = _RE_MD_INLINE.sub(save_inline_code, text)
    link_placeholders: list[tuple[str, str]] = []

    def save_link(m: re.Match) -> str:
        link_placeholders.append((m.group(1), m.group(2)))
        return f"\x00LK{len(link_placeholders) - 1}\x00"

    text = _RE_MD_LINK.sub(save_link, text)
    text = _RE_MD_HEADER.sub(r"\1", text)
    text = _RE_MD_BLOCKQUOTE.sub(r"\1", text)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    for i, (link_text, url) in enumerate(link_placeholders):
        escaped_text = link_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        text = text.replace(f"\x00LK{i}\x00", f'<a href="{url}">{escaped_text}</a>')
    text = _RE_MD_BOLD_ITALIC.sub(r"<b><i>\1</i></b>", text)
    text = _RE_MD_BOLD1.sub(r"<b>\1</b>", text)
    text = _RE_MD_BOLD2.sub(r"<b>\1</b>", text)
    text = _RE_MD_ITALIC.sub(r"<i>\1</i>", text)
    text = _RE_MD_STRIKE.sub(r"<s>\1</s>", text)
    text = _RE_MD_BULLET.sub("• ", text)
    for i, code in enumerate(inline_codes):
        escaped = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        text = text.replace(f"\x00IC{i}\x00", f"<code>{escaped}</code>")
    for i, code in enumerate(code_blocks):
        escaped = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        text = text.replace(f"\x00CB{i}\x00", f"<pre><code>{escaped}</code></pre>")
    return text


