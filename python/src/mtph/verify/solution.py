"""Solution step checking (plan 13) — the headline check.

`mtph verify` reads the equation chain already inside a `solution` and checks it numerically:
split display math into rows and top-level ``=`` chains, then run plan 12's
:func:`mathr.equiv.equivalent_detail` on each adjacent pair, and on the final result versus the
declared answer. A step that doesn't hold is :data:`solution.step_mismatch` (error); one that
can't be evaluated is tallied *unverifiable* (P4 — never a silent pass or a guessed fail). There
is **zero format change**: the equations were always there; verify finally reads them.

The heavy lifting lives here (not in ``checks.py``) so the check registry stays legible. The pure
splitters — :func:`split_rows`, :func:`split_chain` — are unit-tested in isolation.
"""
from __future__ import annotations

import re
from typing import List, Optional

from ..mathr.equiv import equivalent_detail
from ..render.equations import strip_label

# Relations that make a row *not* a checkable equality (an approximation, an inequality, an
# implication, a ± ambiguity …). A row containing any of these is skipped, never a verdict.
# Longer command names come first so the negative lookahead lands correctly (``\leq`` before
# ``\le``); the lookahead keeps ``\left`` / ``\nearrow`` from matching ``\le`` / ``\ne``.
_VOID_RE = re.compile(
    r"\\(?:leqslant|geqslant|lesssim|gtrsim|longrightarrow|Rightarrow|rightarrow|implies"
    r"|approx|propto|simeq|cong|neq|leq|geq|ne|le|ge|to|pm|mp|sim|ll|gg)(?![a-zA-Z])"
    r"|[<>]"
)
_ENV_RE = re.compile(r"\\(?:begin|end)\s*\{[^}]*\}")
_BOXED_RE = re.compile(r"\\boxed\s*\{")
_DISPLAY_RE = re.compile(r"\$\$(.+?)\$\$", re.S)


def _iter_top_level(src: str):
    """Yield ``(index, char, brace_depth)`` scanning ``src``, skipping escaped chars (so ``\\{``
    and a command's letters don't disturb the brace count) and treating ``\\\\`` as one token."""
    i, depth, n = 0, 0, len(src)
    while i < n:
        c = src[i]
        if c == "\\":
            if i + 1 < n and src[i + 1] == "\\":
                yield i, "\\\\", depth  # a row break token
                i += 2
                continue
            i += 2  # a command or escaped char — skip the backslash and the next char
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth = max(0, depth - 1)
        yield i, c, depth
        i += 1


def split_rows(src: str) -> List[str]:
    """Split display-math ``src`` into rows on top-level ``\\\\`` (brace depth 0), stripping any
    ``\\begin{…}`` / ``\\end{…}`` environment markers so an ``aligned`` body splits into its rows."""
    src = _ENV_RE.sub(" ", src)
    rows: List[str] = []
    start = 0
    for i, tok, depth in _iter_top_level(src):
        if tok == "\\\\" and depth == 0:
            rows.append(src[start:i])
            start = i + 2
    rows.append(src[start:])
    return [r.strip() for r in rows if r.strip()]


def _unwrap_boxed(row: str) -> str:
    """Replace ``\\boxed{X}`` with its content ``X`` (one level; brace-matched)."""
    m = _BOXED_RE.search(row)
    if not m:
        return row
    depth, j = 0, m.end() - 1
    for k in range(m.end() - 1, len(row)):
        if row[k] == "{":
            depth += 1
        elif row[k] == "}":
            depth -= 1
            if depth == 0:
                j = k
                break
    return row[: m.start()] + row[m.end():j] + row[j + 1:]


def split_chain(row: str) -> List[str]:
    """Split one row into the segments of its top-level ``=`` chain, or ``[]`` if the row is not a
    checkable equality. ``\\label`` and ``\\boxed`` are unwrapped, ``&`` alignment markers dropped,
    and any ``=`` nested inside ``{}`` (e.g. inside ``\\frac{a=b}{c}``) is *not* a chain boundary."""
    row = strip_label(_unwrap_boxed(row)).replace("&", "").strip().rstrip(".,;")
    if not row or _VOID_RE.search(row):
        return []
    segs: List[str] = []
    start = 0
    for i, tok, depth in _iter_top_level(row):
        if tok == "=" and depth == 0:
            segs.append(row[start:i])
            start = i + 1
    segs.append(row[start:])
    segs = [s.strip() for s in segs if s.strip()]
    return segs if len(segs) >= 2 else []


# --------------------------------------------------------------------------- the walk
def _display_sources(text: str) -> List[str]:
    """Every ``$$…$$`` display-math body inside a chunk of prose/solution text."""
    return [m.group(1) for m in _DISPLAY_RE.finditer(text)]


def _solution_sources(doc) -> List[str]:
    """All display-math sources associated with the solution: the front-matter ``solution:``
    string, plus each ``solution`` block's math children and the ``$$…$$`` in its prose."""
    out: List[str] = []
    sol = doc.meta.get("solution")
    if isinstance(sol, str):
        out += _display_sources(sol)
    for b in doc.blocks:
        if getattr(b, "type", None) != "solution":
            continue
        for c in getattr(b, "children", []) or []:
            if getattr(c, "type", None) == "math":
                out.append(c.latex)
            elif getattr(c, "type", None) == "prose":
                out += _display_sources(c.text)
    return out


def _trim(s: str, n: int = 60) -> str:
    s = s.strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def check_solution(doc, text, answer_specs, symbols, find_line):
    """Walk the solution's equation chains and check them numerically.

    Injected dependencies keep this module free of a ``checks.py`` import cycle:
    ``answer_specs`` is an iterable of ``(label, value, unit)`` (only expression answers matter
    here); ``symbols`` is the raw front-matter symbols table; ``find_line(needle)`` maps a source
    substring to a 1-based line. Returns a :class:`CheckResult`-shaped tuple of
    ``(findings, extra, unknown_message)`` — the caller in ``checks.py`` wraps it."""
    from .model import Finding  # local import: model is a sibling, no cycle

    findings: List[Finding] = []
    steps_checked = steps_skipped = steps_unverifiable = 0
    points = 0
    last_evaluable: Optional[str] = None

    for src in _solution_sources(doc):
        for row in split_rows(src):
            segs = split_chain(row)
            if not segs:
                steps_skipped += 1
                continue
            for a, b in zip(segs, segs[1:]):
                d = equivalent_detail(a, b, symbols)
                if d.verdict is None:
                    steps_unverifiable += 1
                    continue
                steps_checked += 1
                points = max(points, d.points_used)
                if d.verdict is False:
                    findings.append(Finding(
                        id="solution.step_mismatch", severity="error",
                        message=(f"the step `{_trim(a)} = {_trim(b)}` doesn't hold: the two sides "
                                 f"disagree (max relative error {d.max_rel_err:.2g} over "
                                 f"{d.points_used} sample point(s))."),
                        fix="A step that fails numerically is usually an algebra slip — re-derive "
                            "it, or fix the symbols' `test:` values if the step is actually right.",
                        line=find_line(row), context="solution"))
            # the last segment of this chain that actually evaluates — the answer comparison anchor
            for seg in reversed(segs):
                if equivalent_detail(seg, seg, symbols).verdict is not None:
                    last_evaluable = seg
                    break

    # Answer agreement: the solution's final evaluable result vs each declared answer expression.
    if last_evaluable is not None:
        for label, value, _unit in answer_specs:
            d = equivalent_detail(last_evaluable, value, symbols)
            if d.verdict is False:
                findings.append(Finding(
                    id="solution.answer_mismatch", severity="error",
                    message=(f"the solution's final result `{_trim(last_evaluable)}` disagrees with "
                             f"the declared {label} `{_trim(value)}` (max relative error "
                             f"{d.max_rel_err:.2g} over {d.points_used} sample point(s))."),
                    fix="The solution and the answer must agree — re-derive one, or correct the "
                        "declared answer.",
                    line=find_line(value), context="solution"))

    extra = {
        "steps_checked": steps_checked,
        "steps_skipped": steps_skipped,
        "steps_unverifiable": steps_unverifiable,
        "points": points,
    }
    if steps_checked == 0 and not findings:
        return findings, extra, "solution has no checkable equalities (no symbols, or only prose/approximate steps)."
    # An honest note when we could evaluate some steps but not others (and nothing was wrong).
    if steps_unverifiable and not any(f.severity == "error" for f in findings):
        findings.append(Finding(
            id="solution.step_unverifiable", severity="info",
            message=(f"{steps_unverifiable} solution step(s) couldn't be checked numerically "
                     f"(a symbol lacks a `test:` value, or the step uses something the evaluator "
                     f"won't guess at)."),
            fix="Give every symbol used in the solution a `test:` value (pin it, or a `{from,to}` "
                "range) so the step can be sampled.",
            context="solution"))
    return findings, extra, None
