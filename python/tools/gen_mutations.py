#!/usr/bin/env python3
"""Generate the mutation corpus & manifest from the clean annotated examples (plan 11).

A verifier is only as trustworthy as the errors it catches, so before writing new checkers we
build the thing that *measures* checkers: a committed corpus of deliberately-broken problems
plus a manifest mapping each file to its mutation class and the verify finding id(s) that
*should* catch it. `mutation_report.py` runs `mtph verify` over the corpus and prints the catch
rate / false-positive rate.

Design (see plans/11-mutation-corpus.md):
  * Mutations are generated, committed, diffable files — never hand-edited. Regenerate in CI and
    `git diff --exit-code`, exactly like `spec/conformance/`.
  * Each operator edits *text* (not the DOM) so a mutant looks like the one small slip a real
    author makes; the file still parses and validates.
  * `expected_ids` records what *should* catch a mutant by its nature (the class table below),
    never merely what today's verifier happens to emit — otherwise the catch rate is meaningless.

Run:  python python/tools/gen_mutations.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "python" / "src"))

# --------------------------------------------------------------------------- LaTeX operators
# Each takes an answer/solution LaTeX fragment and returns the fragment with exactly one targeted
# change, or None when the fragment has no site for that operator.


def op_signflip(s: str) -> Optional[str]:
    """Flip the first *binary* ``+``/``-`` (a leading unary sign, a sign inside an exponent like
    ``x^{-1}``, or a hyphen inside a word like ``charge-free`` is not a site)."""
    for i, ch in enumerate(s):
        if ch not in "+-":
            continue
        j = i - 1
        while j >= 0 and s[j] == " ":
            j -= 1
        if j < 0:
            continue  # leading unary sign — nothing to its left
        if not (s[j] in "})]" or s[j].isalnum()):
            continue  # follows an operator / `(` / `^` / `_` / `=` — a unary sign, not binary
        right = s[i + 1] if i + 1 < len(s) else ""
        if s[i - 1].isalpha() and right.isalpha():
            continue  # a word hyphen (`charge-free`), not a math operator
        return s[:i] + ("-" if ch == "+" else "+") + s[i + 1:]
    return None


_TRIG_RE = re.compile(r"\\(sin|cos)(?![a-zA-Z])")


def op_trig(s: str) -> Optional[str]:
    """Swap the first ``\\sin`` <-> ``\\cos`` (a whole command only, so ``\\sinh`` is skipped)."""
    m = _TRIG_RE.search(s)
    if not m:
        return None
    swap = "cos" if m.group(1) == "sin" else "sin"
    return s[: m.start()] + "\\" + swap + s[m.end():]


_POW_RE = re.compile(r"\^(\{2\}|2(?![0-9]))")


def op_power(s: str) -> Optional[str]:
    """Bump the first bare ``^2`` (or ``^{2}``) to ``^3`` (multi-digit exponents are left alone)."""
    m = _POW_RE.search(s)
    if not m:
        return None
    rep = "{3}" if m.group(1) == "{2}" else "3"
    return s[: m.start()] + "^" + rep + s[m.end():]


_HALF_RE = re.compile(r"\\[dt]?frac(?:\{1\}\{2\}|12)")


def op_factor(s: str) -> Optional[str]:
    """Drop a leading one-half (``\\tfrac12`` / ``\\frac{1}{2}`` / ``\\dfrac{1}{2}`` …); failing
    that, knock the first coefficient ``2`` down to ``1``. Both are the classic dropped-factor
    slip that a dimension check is blind to (``\\tfrac12 mv^2`` and ``mv^2`` share a dimension)."""
    m = _HALF_RE.search(s)
    if m:
        end = m.end()
        if end < len(s) and s[end] == " ":
            end += 1  # also swallow one following space so `\tfrac12 mv^2` -> `mv^2`
        return s[: m.start()] + s[end:]
    i = _find_coeff_two(s)
    if i is not None:
        return s[:i] + "1" + s[i + 1:]
    return None


def _find_coeff_two(s: str) -> Optional[int]:
    """Index of the first standalone coefficient ``2`` — not a subscript/exponent, not part of a
    multi-digit number, not the ``2`` in ``^{2}``."""
    for i, ch in enumerate(s):
        if ch != "2":
            continue
        prev = s[i - 1] if i > 0 else ""
        nxt = s[i + 1] if i + 1 < len(s) else ""
        if nxt.isdigit():
            continue  # part of a multi-digit number
        if prev.isalnum() or prev in ("_", "^"):
            continue  # a subscript/exponent digit, or a variable like `x2`
        if prev == "{":
            before = s[i - 2] if i >= 2 else ""
            if before == "^" or nxt == "}":
                continue  # `^{2}` (an exponent) or a lone `{2}`
        return i
    return None


# swap a numeric answer's unit for a DIMENSION-CHANGING one — `m -> cm` would preserve the
# dimension and could never be a dimensional error, so it would name the wrong checker.
_UNIT_SWAP = {
    "m/s": "W", "m/s^2": "W", "m": "J", "J": "W", "W": "J", "N": "J", "s": "m", "kg": "s",
}


def op_unit_swap(unit: Optional[str]) -> Optional[str]:
    """Swap a unit for one of a different dimension; None when there is no unit to swap."""
    if not unit:
        return None
    return _UNIT_SWAP.get(unit, "J" if unit == "W" else "W")


LATEX_OPERATORS: Dict[str, Callable[[str], Optional[str]]] = {
    "signflip": op_signflip,
    "factor": op_factor,
    "trig": op_trig,
    "power": op_power,
}


# --------------------------------------------------------------------------- generator

from mtph.parser import parse  # noqa: E402
from mtph.validate import validate  # noqa: E402

EXAMPLES = _ROOT / "spec" / "examples"
MUTATIONS = _ROOT / "spec" / "mutations"

# What SHOULD catch each mutant, by its nature — not what today's verifier happens to emit. A
# mutation of an answer expression is a dimension/numeric error; a mutation buried in a solution
# step is `solution.step_mismatch` (plan 13) and so is honestly *missed* until that checker lands.
EXPECTED: Dict[str, Dict[str, List[str]]] = {
    "signflip": {"answer": ["numeric.mismatch"], "solution": ["solution.step_mismatch"]},
    "factor":   {"answer": ["numeric.mismatch"], "solution": ["solution.step_mismatch"]},
    "trig":     {"answer": ["numeric.mismatch"], "solution": ["solution.step_mismatch"]},
    "power":    {"answer": ["dimension.mismatch", "numeric.mismatch"],
                 "solution": ["solution.step_mismatch"]},
}
UNIT_EXPECTED = ["dimension.mismatch"]


def _regions(doc) -> List[Tuple[str, str]]:
    """The mutable LaTeX regions of a document as ``(kind, content)`` pairs, in document order.
    ``kind`` is ``answer`` (an answer expression a checker could bite on) or ``solution`` (a
    solution step). Freeform answers and prose are not targeted."""
    out: List[Tuple[str, str]] = []
    meta = doc.meta
    ans = meta.get("answer")
    if isinstance(ans, dict) and ans.get("type") == "expression" and isinstance(ans.get("value"), str):
        out.append(("answer", ans["value"]))
    for a in meta.get("answers", []) or []:
        if isinstance(a, dict) and a.get("type") == "expression" and isinstance(a.get("value"), str):
            out.append(("answer", a["value"]))
    for b in doc.blocks:
        if getattr(b, "type", None) == "answer" and getattr(b, "answer_type", None) == "expression" \
                and isinstance(getattr(b, "value", None), str):
            out.append(("answer", b.value))
    sol = meta.get("solution")
    if isinstance(sol, str):
        out.append(("solution", sol))
    for b in doc.blocks:
        if getattr(b, "type", None) == "solution":
            for c in getattr(b, "children", []) or []:
                if isinstance(getattr(c, "text", None), str):
                    out.append(("solution", c.text))
    return out


def _numeric_unit(doc) -> Optional[str]:
    ans = doc.meta.get("answer")
    if isinstance(ans, dict) and ans.get("type") == "numeric" and isinstance(ans.get("unit"), str):
        return ans["unit"]
    return None


def _mutate_region(raw: str, content: str, op: Callable[[str], Optional[str]]) -> Optional[str]:
    """Apply ``op`` to the first line of ``content`` that has a site and splice the one-line change
    into ``raw``."""
    for line in content.split("\n"):
        mutated = op(line)
        if mutated is None or mutated == line:
            continue
        spliced = _splice_line(raw, line, mutated)
        if spliced is not None:
            return spliced
    return None


def _splice_line(raw: str, line: str, mutated: str) -> Optional[str]:
    """Replace ``line`` with ``mutated`` in ``raw``, preferring a *whole-line* match (a fenced-block
    line or an indented front-matter scalar line). Matching the full line excludes substring hits —
    a ``grading: criteria:`` line, or a ` ```math ` line that merely *contains* the answer text with
    a trailing ``\\label`` — that a bare ``replace`` would wrongly land on."""
    m = re.search(r"(?<=\n)([ \t]*)" + re.escape(line) + r"(?=\n)", raw)
    if m:
        return raw[: m.start()] + m.group(1) + mutated + raw[m.end():]
    if line in raw:  # a front-matter answer value living inside `value: '…'`
        return raw.replace(line, mutated, 1)
    return None


def _swap_unit(raw: str, unit: str, new_unit: str) -> Optional[str]:
    new = re.sub(r'(unit:\s*["\']?)' + re.escape(unit) + r'(["\']?)',
                 lambda m: m.group(1) + new_unit + m.group(2), raw, count=1)
    return new if new != raw else None


def _valid(text: str) -> bool:
    try:
        return validate(parse(text)) == []
    except Exception:
        return False


def main() -> int:
    MUTATIONS.mkdir(parents=True, exist_ok=True)
    for old in MUTATIONS.glob("*.mtph"):  # regenerated wholesale, like the conformance gold
        old.unlink()

    manifest: List[dict] = []
    for src in sorted(EXAMPLES.glob("*.mtph")):
        raw = src.read_text(encoding="utf-8")
        doc = parse(raw)
        if not isinstance(doc.meta.get("symbols"), dict) or not doc.meta["symbols"]:
            continue  # only annotated (verifiable) examples are mutation substrate
        stem = src.stem
        regions = _regions(doc)

        for cls in ("signflip", "factor", "trig", "power"):
            op = LATEX_OPERATORS[cls]
            n = 0
            for kind in ("answer", "solution"):
                for rkind, content in regions:
                    if rkind != kind:
                        continue
                    mutated = _mutate_region(raw, content, op)
                    if mutated is None or not _valid(mutated):
                        continue
                    n += 1
                    fname = f"{stem}__{cls}{n}.mtph"
                    (MUTATIONS / fname).write_text(mutated, encoding="utf-8")
                    manifest.append({
                        "file": f"spec/mutations/{fname}",
                        "source": f"spec/examples/{stem}.mtph",
                        "cls": cls,
                        "expected_ids": EXPECTED[cls][kind],
                    })
                    break  # one mutant per (class, region-kind)

        unit = _numeric_unit(doc)
        if unit is not None:
            new_unit = op_unit_swap(unit)
            if new_unit:
                mutated = _swap_unit(raw, unit, new_unit)
                if mutated is not None and _valid(mutated):
                    fname = f"{stem}__unit1.mtph"
                    (MUTATIONS / fname).write_text(mutated, encoding="utf-8")
                    manifest.append({
                        "file": f"spec/mutations/{fname}",
                        "source": f"spec/examples/{stem}.mtph",
                        "cls": "unit",
                        "expected_ids": UNIT_EXPECTED,
                    })

    manifest.sort(key=lambda e: e["file"])
    (MUTATIONS / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    by_class: Dict[str, int] = {}
    for e in manifest:
        by_class[e["cls"]] = by_class.get(e["cls"], 0) + 1
    print(f"mutations: wrote {len(manifest)} mutants to spec/mutations/ "
          f"({', '.join(f'{k}={v}' for k, v in sorted(by_class.items()))})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
