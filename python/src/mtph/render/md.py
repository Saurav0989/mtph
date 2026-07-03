"""A tiny, math-safe Markdown -> HTML converter.

Just enough Markdown for problem prose (headings, lists, paragraphs, bold/italic/code) while
**never touching math**: ``$...$`` / ``$$...$$`` spans (and inline code) are pulled out before
any formatting runs and restored afterwards, so KaTeX delimiters survive intact for the
browser-side auto-render pass.
"""
from __future__ import annotations

import html
import re
from typing import List, Tuple

_MATH_BLOCK = re.compile(r"\$\$.*?\$\$", re.S)
# Inline math may wrap across source lines, so allow newlines inside (re.S via [^$]).
_MATH_INLINE = re.compile(r"\$[^$]+?\$")
_CODE = re.compile(r"`[^`]+?`")
_PLACEHOLDER = re.compile("\x00(\\d+)\x00")


def _protect(text: str) -> Tuple[str, List[str]]:
    store: List[str] = []

    def stash(m: re.Match) -> str:
        store.append(m.group(0))
        return f"\x00{len(store) - 1}\x00"

    text = _MATH_BLOCK.sub(stash, text)
    text = _MATH_INLINE.sub(stash, text)
    text = _CODE.sub(stash, text)
    return text, store


def _restore(s: str, store: List[str]) -> str:
    def rep(m: re.Match) -> str:
        frag = store[int(m.group(1))]
        if frag.startswith("`"):
            return "<code>" + html.escape(frag[1:-1]) + "</code>"
        return html.escape(frag)  # math: keep $ delimiters, escape < > & inside

    return _PLACEHOLDER.sub(rep, s)


def _inline(s: str) -> str:
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", s)
    return s


def _fmt(text: str) -> str:
    return _inline(html.escape(text))


def md_to_html(text: str) -> str:
    text, store = _protect(text)
    out: List[str] = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [ln for ln in block.split("\n") if ln.strip()]
        if not lines:
            continue
        heading = re.match(r"(#{1,6})\s+(.*)", lines[0])
        if heading and len(lines) == 1:
            level = len(heading.group(1))
            out.append(f"<h{level}>{_fmt(heading.group(2).strip())}</h{level}>")
        elif all(re.match(r"[-*]\s+", ln) for ln in lines):
            items = "".join(f"<li>{_fmt(ln[2:].strip())}</li>" for ln in lines)
            out.append(f"<ul>{items}</ul>")
        elif all(re.match(r"\d+\.\s+", ln) for ln in lines):
            # Preserve the author's starting number. Markdown splits blank-line-separated
            # items into separate blocks, so "1." then "2." arrive as two single-item lists;
            # emitting <ol start="N"> keeps them numbered 1, 2, … instead of resetting to 1.
            start = int(re.match(r"(\d+)\.", lines[0]).group(1))
            stripped = [re.sub(r"^\d+\.\s+", "", ln).strip() for ln in lines]
            items = "".join(f"<li>{_fmt(s)}</li>" for s in stripped)
            start_attr = f' start="{start}"' if start != 1 else ""
            out.append(f"<ol{start_attr}>{items}</ol>")
        else:
            para = _fmt(block.strip()).replace("\n", "<br>\n")
            out.append(f"<p>{para}</p>")
    return _restore("\n".join(out), store)
