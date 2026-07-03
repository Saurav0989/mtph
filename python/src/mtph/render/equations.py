"""Equation numbering and cross-references (`\\label` / `\\ref`).

A display-math block (` ```math ` or a standalone ``$$…$$``) that carries ``\\label{key}`` gets a
number; ``\\ref{key}`` in prose becomes a clickable ``(n)`` pointing at it. Only *labelled*
equations are numbered, so every visible number is something the author chose to reference.

KaTeX doesn't understand ``\\label``/``\\ref``, so we resolve them ourselves: ``\\label`` is
stripped before the LaTeX reaches the browser (the number is rendered as separate HTML), and
``\\ref`` is replaced — with a link in prose, or with the bare number inside math.
"""
from __future__ import annotations

import re
from typing import Dict, Tuple

from ..model import Document

_LABEL_RE = re.compile(r"\\label\{([^}]*)\}")
_REF_RE = re.compile(r"\\ref\{([^}]*)\}")

Labels = Dict[str, Tuple[int, str]]  # key -> (number, html anchor id)


def _slug(key: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", key.strip()).strip("-").lower()
    return s if s.startswith("eq") else f"eq-{s}"


def _iter_math(blocks):
    for b in blocks:
        if getattr(b, "type", None) == "math":
            yield b
        elif getattr(b, "type", None) == "solution":
            yield from _iter_math(b.children)


def collect_labels(doc: Document) -> Labels:
    """Map each unique ``\\label{key}`` to ``(number, anchor)`` in first-appearance order."""
    labels: Labels = {}
    for b in _iter_math(doc.blocks):
        for key in _LABEL_RE.findall(b.latex):
            key = key.strip()
            if key and key not in labels:
                labels[key] = (len(labels) + 1, _slug(key))
    return labels


def label_of(latex: str) -> str | None:
    m = _LABEL_RE.search(latex)
    return m.group(1).strip() if m else None


def strip_label(latex: str) -> str:
    return _LABEL_RE.sub("", latex).strip()


def sub_refs_math(latex: str, labels: Labels) -> str:
    """Inside math, a ``\\ref`` becomes the bare number (KaTeX renders it); unknown → ``?``."""
    return _REF_RE.sub(lambda m: str(labels.get(m.group(1).strip(), ("?",))[0]), latex)


def sub_refs_html(rendered: str, labels: Labels) -> str:
    """In already-rendered prose HTML, turn ``\\ref{key}`` into a link — but never inside a
    ``$…$`` / ``$$…$$`` span (that would corrupt the KaTeX source), so math is protected first."""
    store: list = []

    def stash(m: re.Match) -> str:
        store.append(m.group(0))
        return f"\x00R{len(store) - 1}\x00"

    s = re.sub(r"\$\$.*?\$\$", stash, rendered, flags=re.S)
    s = re.sub(r"\$[^$]+?\$", stash, s)

    def link(m: re.Match) -> str:
        key = m.group(1).strip()
        if key in labels:
            num, anchor = labels[key]
            return f'<a class="eqref" href="#{anchor}">({num})</a>'
        return "(?)"

    s = _REF_RE.sub(link, s)
    return re.sub(r"\x00R(\d+)\x00", lambda m: store[int(m.group(1))], s)
