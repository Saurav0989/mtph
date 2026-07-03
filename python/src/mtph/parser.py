"""Parse `.mtph` source text into the :class:`~mtph.model.Document` DOM, and back.

The source is YAML front-matter (between ``---`` fences) followed by a Markdown-style body.
The body is split into ordered blocks:

* fenced ` ```math `, ` ```figure `, ` ```plot ` blocks,
* display math delimited by ``$$``,
* everything else collected into ``prose`` blocks (inline ``$...$`` left intact).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Tuple

import yaml

from .model import (
    AnswerBlock,
    Block,
    Document,
    FigureBlock,
    MathBlock,
    PlotBlock,
    ProseBlock,
    SolutionBlock,
)


class MtphSyntaxError(ValueError):
    """Raised for malformed .mtph source (front-matter or body structure)."""


# A fence opens with a run of 3+ backticks; it closes on a line of >= that many backticks.
# (Variable-length fences let a ````solution block contain inner ```figure / ```math blocks.)
_FENCE_OPEN = re.compile(r"^(`{3,})(.*)$")
_FENCE_KIND = re.compile(r"^(\w+)?(.*)$")
# attribute values may be quoted ("a b") or bare (part=b, type=expression)
_ATTR_RE = re.compile(r'(\w+)\s*=\s*(?:"([^"]*)"|(\S+))')
_FENCE_KINDS = {"math", "figure", "plot", "answer", "solution"}


def _split_frontmatter(text: str) -> Tuple[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise MtphSyntaxError(
            "file must begin with a YAML front-matter block opened by '---' on line 1"
        )
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1 :])
    raise MtphSyntaxError("unterminated front-matter: missing closing '---'")


def _parse_attrs(s: str) -> Dict[str, str]:
    return {m.group(1): (m.group(2) if m.group(2) is not None else m.group(3))
            for m in _ATTR_RE.finditer(s or "")}


def _make_fenced_block(kind: str, src: str, attrs: Dict[str, str]) -> Block:
    if kind == "math":
        return MathBlock(latex=src.strip())
    if kind == "figure":
        return FigureBlock(source=src, caption=attrs.get("caption"))
    if kind == "plot":
        return PlotBlock(source=src, caption=attrs.get("caption"))
    if kind == "answer":
        return AnswerBlock(value=src.strip(), part=attrs.get("part"),
                           answer_type=attrs.get("type", "expression"))
    # solution: its body is parsed recursively so it can hold figures/math/prose
    return SolutionBlock(children=_parse_body(src))


def _parse_body(body: str) -> List[Block]:
    lines = body.split("\n")
    n = len(lines)
    blocks: List[Block] = []
    prose_buf: List[str] = []

    def flush_prose() -> None:
        nonlocal prose_buf
        text = "\n".join(prose_buf).strip("\n")
        if text.strip():
            blocks.append(ProseBlock(text=text))
        prose_buf = []

    i = 0
    while i < n:
        line = lines[i]
        stripped = line.strip()

        # --- fenced block: ```math / figure / plot / answer / solution -------
        fence = _FENCE_OPEN.match(stripped)
        if fence:
            ticks = fence.group(1)
            km = _FENCE_KIND.match(fence.group(2))
            kind = km.group(1)
            if kind in _FENCE_KINDS:
                flush_prose()
                attrs = _parse_attrs(km.group(2))
                close = re.compile(r"^`{" + str(len(ticks)) + r",}\s*$")
                j = i + 1
                content: List[str] = []
                while j < n and not close.match(lines[j].strip()):
                    content.append(lines[j])
                    j += 1
                if j >= n:
                    raise MtphSyntaxError(
                        f"unterminated ```{kind} block opened on line {i + 1}"
                    )
                src = "\n".join(content).strip("\n")
                blocks.append(_make_fenced_block(kind, src, attrs))
                i = j + 1
                continue

        # --- display math: $$ ... $$ -----------------------------------------
        if stripped.startswith("$$"):
            flush_prose()
            if stripped.endswith("$$") and len(stripped) > 3:
                blocks.append(MathBlock(latex=stripped[2:-2].strip()))
                i += 1
                continue
            content = []
            first = stripped[2:]
            if first.strip():
                content.append(first)
            j = i + 1
            while j < n and "$$" not in lines[j]:
                content.append(lines[j])
                j += 1
            if j >= n:
                raise MtphSyntaxError(
                    f"unterminated $$ display-math block opened on line {i + 1}"
                )
            before = lines[j][: lines[j].index("$$")]
            if before.strip():
                content.append(before)
            blocks.append(MathBlock(latex="\n".join(content).strip()))
            i = j + 1
            continue

        # --- prose -----------------------------------------------------------
        prose_buf.append(line)
        i += 1

    flush_prose()
    return blocks


def parse(text: str) -> Document:
    """Parse `.mtph` source text into a :class:`Document`."""
    fm, body = _split_frontmatter(text)
    # Parse `fm + "\n"` so a trailing block scalar (`solution: |`) chomps deterministically — with
    # a final line break present, clip chomping keeps exactly one newline, which the JS `yaml`
    # parser matches (without it, pyyaml and yaml-js disagree on the trailing newline). See plan 09.
    data = yaml.safe_load(fm + "\n") if fm.strip() else {}
    if not isinstance(data, dict):
        raise MtphSyntaxError("front-matter must be a YAML mapping (key: value pairs)")
    if "mtph" not in data:
        raise MtphSyntaxError("front-matter is missing the required 'mtph' version key")
    mtph_ver = str(data.pop("mtph"))
    return Document(mtph=mtph_ver, meta=data, blocks=_parse_body(body))


def load(path: str | Path) -> Document:
    """Read and parse a `.mtph` file."""
    return parse(Path(path).read_text(encoding="utf-8"))


def serialize(doc: Document) -> str:
    """Serialise a :class:`Document` back to canonical `.mtph` source (round-trips the DOM)."""
    fm = {"mtph": doc.mtph, **doc.meta}
    fm_yaml = yaml.safe_dump(
        fm, sort_keys=False, allow_unicode=True, default_flow_style=False
    ).rstrip()

    body = "\n\n".join(_serialize_block(b) for b in doc.blocks)
    return f"---\n{fm_yaml}\n---\n\n" + body + "\n"


def _serialize_block(b: Block) -> str:
    if isinstance(b, ProseBlock):
        return b.text
    if isinstance(b, MathBlock):
        return f"$$\n{b.latex}\n$$"
    if isinstance(b, FigureBlock):
        cap = f' caption="{b.caption}"' if b.caption else ""
        return f"```figure{cap}\n{b.source}\n```"
    if isinstance(b, PlotBlock):
        cap = f' caption="{b.caption}"' if b.caption else ""
        return f"```plot{cap}\n{b.source}\n```"
    if isinstance(b, AnswerBlock):
        attrs = ""
        if b.part:
            attrs += f" part={b.part}"
        if b.answer_type and b.answer_type != "expression":
            attrs += f" type={b.answer_type}"
        return f"```answer{attrs}\n{b.value}\n```"
    if isinstance(b, SolutionBlock):
        # 4-tick fence so inner 3-tick figure/math/plot blocks round-trip cleanly
        inner = "\n\n".join(_serialize_block(c) for c in b.children)
        return f"````solution\n{inner}\n````"
    return ""
