"""Multi-point sampling & expression equivalence (plan 12).

The numeric layer (:mod:`.numeric`) can evaluate an answer at *one* set of test values. That is
enough to catch a dropped factor, but not enough to tell two genuinely different functions apart
when they happen to agree at that one point — ``\\sin\\theta`` and ``\\tan\\theta`` are nearly
equal for small ``\\theta`` yet are not the same function. This module lifts the evaluator from
one point to ``K`` sampled points and exposes the primitive every later checker rests on:

    equivalent(a, b, symbols) -> Optional[bool]

*are two LaTeX expressions the same function of the declared symbols?* — ``True`` when every
evaluable sample agrees to a tight relative tolerance, ``False`` on any real disagreement, and
``None`` (principle P4) whenever it can't fully evaluate both sides. A ``False`` is therefore
always a genuine disagreement, never a guess.

Determinism (a hard requirement — ``mtph verify`` output must not vary run to run): sampling uses
``random.Random(_SEED)`` with a fixed module seed, re-seeded per call.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union

from .dimension import normalize_symbol
from .numeric import eval_latex

_SEED = 20260704
_K_DEFAULT = 5
_ATTEMPT_CAP = 20      # total sampling attempts before giving up (domain-guard resampling)
_REL_TOL = 1e-6        # per-point relative tolerance for "the same expression"

# A parsed per-symbol test: a pinned value, or a (lo, hi) sampling range.
Test = Union[float, Tuple[float, float]]


def _read_test(spec) -> Optional[Test]:
    """Read a ``symbols:`` value → a pinned ``float``, a ``(lo, hi)`` range, or ``None``.

    The value is a string (dimension only, no test) or an object ``{dim?, test?}`` whose ``test``
    is a number (pinned) or ``{from, to}`` (a sampling range). Anything else → ``None``."""
    if isinstance(spec, (int, float)) and not isinstance(spec, bool):
        return float(spec)
    if isinstance(spec, dict):
        t = spec.get("test")
        if isinstance(t, (int, float)) and not isinstance(t, bool):
            return float(t)
        if isinstance(t, dict):
            lo, hi = t.get("from"), t.get("to")
            if (isinstance(lo, (int, float)) and not isinstance(lo, bool)
                    and isinstance(hi, (int, float)) and not isinstance(hi, bool)):
                return (float(lo), float(hi))
    return None


def _symbol_tests(symbols) -> Dict[str, Test]:
    """Normalized symbol name → its test (pinned or ranged), for every test-bearing symbol."""
    out: Dict[str, Test] = {}
    if isinstance(symbols, dict):
        for name, spec in symbols.items():
            t = _read_test(spec)
            if t is not None:
                out[normalize_symbol(str(name))] = t
    return out


def _draw(tests: Dict[str, Test], rng: random.Random) -> Dict[str, float]:
    """One sample point: pinned symbols at their value, ranged symbols drawn uniformly."""
    pt: Dict[str, float] = {}
    for name, t in tests.items():
        pt[name] = t if isinstance(t, float) else rng.uniform(t[0], t[1])
    return pt


def sample_values(symbols: dict, k: int = _K_DEFAULT, seed: int = _SEED) -> List[Dict[str, float]]:
    """Return ``k`` sample points over the declared symbols' test values.

    Each point maps a normalized symbol name → a number. Pinned symbols hold the same value at
    every point; ranged symbols are drawn uniformly from ``[from, to]``. Deterministic in ``seed``.
    Symbols with no test value are simply absent (the evaluator will bail on them)."""
    tests = _symbol_tests(symbols)
    rng = random.Random(seed)
    return [_draw(tests, rng) for _ in range(k)]


@dataclass
class EquivDetail:
    """The outcome of an equivalence comparison, with the evidence plan 13's findings quote."""

    verdict: Optional[bool]   # True agree / False disagree / None can't tell (P4)
    points_used: int          # how many sample points actually evaluated on both sides
    max_rel_err: float        # the largest per-point relative error seen


def _rel_err(a: float, b: float) -> float:
    denom = max(abs(a), abs(b))
    return 0.0 if denom == 0.0 else abs(a - b) / denom


def equivalent_detail(a: str, b: str, symbols: dict, k: int = _K_DEFAULT) -> EquivDetail:
    """Sample the declared symbols and compare ``a`` and ``b`` numerically at each usable point.

    ``True`` iff every evaluable point agrees within :data:`_REL_TOL`; ``False`` on any point that
    disagrees (a real disagreement is reported even from a single point); ``None`` when no usable
    point is found, or — with ranged symbols — fewer than two survive the domain guard."""
    tests = _symbol_tests(symbols)
    has_range = any(not isinstance(t, float) for t in tests.values())
    rng = random.Random(_SEED)

    if not has_range:
        # All symbols pinned (or none): one deterministic point; resampling can't help.
        pt = _draw(tests, rng)
        va, vb = eval_latex(a, pt), eval_latex(b, pt)
        if va is None or vb is None:
            return EquivDetail(None, 0, 0.0)
        rel = _rel_err(va, vb)
        return EquivDetail(rel <= _REL_TOL, 1, rel)

    used = 0
    max_rel = 0.0
    disagreed = False
    attempts = 0
    while used < k and attempts < _ATTEMPT_CAP:
        attempts += 1
        pt = _draw(tests, rng)
        va, vb = eval_latex(a, pt), eval_latex(b, pt)
        if va is None or vb is None:
            continue  # a bad-domain draw — resample
        used += 1
        rel = _rel_err(va, vb)
        max_rel = max(max_rel, rel)
        if rel > _REL_TOL:
            disagreed = True
    if disagreed:
        return EquivDetail(False, used, max_rel)   # a real disagreement is never masked
    if used < 2:
        return EquivDetail(None, used, max_rel)    # not enough usable points to trust "equal"
    return EquivDetail(True, used, max_rel)


def equivalent(a: str, b: str, symbols: dict, k: int = _K_DEFAULT) -> Optional[bool]:
    """Thin wrapper over :func:`equivalent_detail` returning just the verdict."""
    return equivalent_detail(a, b, symbols, k).verdict
