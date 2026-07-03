"""``mtph audit`` — verification plus *advisory* structural nudges toward the thesis bar.

`verify` answers "is this well-formed?"; `audit` adds soft, honest suggestions about a problem's
*shape* (does it ship a solution? a figure? a difficulty?). It can never judge the things that
actually make a problem hard — the necessary insight, the false attractor, the domain collision —
so those stay a **checklist for the human** (principle P4: don't claim to check what you can't).
"""
from __future__ import annotations

import re
from typing import List

from .model import Document
from .verify.model import Finding


def _has(doc: Document, btype: str) -> bool:
    return any(getattr(b, "type", None) == btype for b in doc.blocks)


def _iter(doc: Document):
    for b in doc.blocks:
        yield b
        if getattr(b, "type", None) == "solution":
            yield from b.children


def _solution_text(doc: Document) -> str:
    """All prose inside solution blocks + a front-matter solution, concatenated."""
    parts = []
    for b in doc.blocks:
        if getattr(b, "type", None) == "solution":
            parts += [c.text for c in b.children if getattr(c, "type", None) == "prose"]
    sol = doc.meta.get("solution")
    if isinstance(sol, str):
        parts.append(sol)
    return "\n".join(parts)


def _join(items: List[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


# Language a thesis-grade solution uses when it names *why* the problem is hard.
_INSIGHT_RE = re.compile(
    r"\b(insight|necessary|key idea|the key|reframe|realise|realize|the trick|the crux|"
    r"invariant|hidden|false attractor|conserved|the observation)\b", re.I)


def mentor(doc: Document) -> List[str]:
    """Holistic, difficulty-aware notes — the kind a mentor gives, combining signals rather than
    listing fields. Advisory only; a human still judges the physics."""
    meta = doc.meta
    diff = meta.get("difficulty")
    notes: List[str] = []

    gaps = []
    if not (_has(doc, "figure") or _has(doc, "plot")):
        gaps.append("no figure")
    if not (_has(doc, "solution") or meta.get("solution")):
        gaps.append("no worked solution")
    if not (_has(doc, "answer") or meta.get("answer") or meta.get("answers")):
        gaps.append("no stated answer")

    if isinstance(diff, int) and diff >= 4 and gaps:
        notes.append(
            f"This claims difficulty {diff} but has {_join(gaps)} — thesis-grade problems (4–5) "
            f"usually carry all three. Add them, or lower the difficulty to match.")

    if isinstance(diff, int) and diff >= 4:
        sol = _solution_text(doc)
        if sol and not _INSIGHT_RE.search(sol):
            notes.append(
                "The solution doesn't name the necessary insight (Pillar 2) — state the single "
                "idea that unlocks it, so a reader sees *why* it's hard, not just how to grind it.")

    return notes


def advisories(doc: Document) -> List[Finding]:
    """Soft, structural ``info`` suggestions — never errors, never block anything."""
    out: List[Finding] = []
    meta = doc.meta

    if meta.get("subject") == "physics" and not (_has(doc, "figure") or _has(doc, "plot")):
        out.append(Finding(
            id="audit.no_figure", severity="info",
            message="no figure or plot — spatial/visual reasoning is a strong AI-defeating axis.",
            fix="Add a `figure` (or `plot`) if the problem has any geometry.", context="audit"))

    if not (_has(doc, "answer") or meta.get("answer") or meta.get("answers")):
        out.append(Finding(
            id="audit.no_answer", severity="info",
            message="no answer block — give the intended result so it can be checked.",
            fix="Add a ```answer block (or `answer:` in front-matter).", context="audit"))

    if not (_has(doc, "solution") or meta.get("solution")):
        out.append(Finding(
            id="audit.no_solution", severity="info",
            message="no worked solution — a hard problem should ship one (answer↔solution check).",
            fix="Add a ````solution block.", context="audit"))

    if not meta.get("difficulty"):
        out.append(Finding(
            id="audit.no_difficulty", severity="info",
            message="no difficulty declared.",
            fix="Add `difficulty: 1..5` (see the rubric in thesis/card.md).", context="audit"))

    return out


# The genuinely-hard properties a tool can't assess — surfaced for the human to judge.
CHECKLIST = [
    "Is there a single necessary insight that unlocks it (Pillar 2)?",
    "Is there a compelling false attractor — an obvious-but-wrong approach (Pillar 1)?",
    "Do two domains couple inseparably (Pillar 4)?",
    "Is a regime/limiting case hidden, where the wrong choice gives a plausible-but-wrong answer (Pillar 7)?",
    "Is it under-specified so the solver must build the model (Pillar 5)?",
    "Stated in ≤2 paragraphs, solvable in ≤2 pages, insight simple in hindsight (elegance)?",
]
