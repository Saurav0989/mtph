"""Multi-point sampling & expression equivalence (plan 12).

`mathr.equiv` wraps the conservative numeric evaluator (`mathr.numeric.eval_latex`) with
deterministic sampling over per-symbol test values — a pinned number or a `{from,to}` range.
`equivalent(a, b, symbols)` answers "are these two LaTeX expressions the same function of the
declared symbols?": True when every evaluable sample agrees (rel 1e-6), False on any real
disagreement, None when it can't fully evaluate both sides (principle P4 — a False is never a
guess). This is the primitive plan 13's solution-step checker rests on.
"""
from __future__ import annotations

from mtph.mathr.equiv import (
    EquivDetail,
    equivalent,
    equivalent_detail,
    sample_values,
)


def test_sample_values_deterministic():
    """A fixed seed makes sampling reproducible run-to-run (verify must be deterministic)."""
    symbols = {"x": {"test": {"from": 0.0, "to": 1.0}}, "g": {"dim": "acceleration", "test": 9.8}}
    a = sample_values(symbols)
    b = sample_values(symbols)
    assert a == b
    assert len(a) == 5  # K default


def test_sample_values_pinned_vs_ranged():
    """Pinned symbols are constant across every sample point; ranged symbols vary."""
    symbols = {
        "g": {"dim": "acceleration", "test": 9.8},   # pinned
        "theta": {"test": {"from": 0.2, "to": 1.2}}, # ranged
    }
    pts = sample_values(symbols)
    assert all(p["g"] == 9.8 for p in pts)             # pinned: constant
    assert 0.2 <= min(p["theta"] for p in pts)          # ranged: within bounds
    assert max(p["theta"] for p in pts) <= 1.2
    assert len({p["theta"] for p in pts}) > 1           # ranged: actually varies

    # A symbol with no test value (dimension-only or a bare string) is not sampled.
    assert sample_values({"m": "mass"}) == [{}] * len(sample_values({"m": "mass"}))
    assert all(p == {} for p in sample_values({"m": "mass"}))


def test_equivalent_distinguishes_sin_tan():
    """The headline: sin θ and tan θ agree near θ=0 but are different functions — one test point
    could be fooled; sampling a *range* is not (this is the whole reason for multi-point)."""
    symbols = {"theta": {"test": {"from": 0.01, "to": 0.15}}}
    assert equivalent(r"\sin\theta", r"\tan\theta", symbols) is False
    assert equivalent(r"\sin\theta", r"\sin\theta", symbols) is True


def test_equivalent_algebraic_identity():
    """Two spellings of ½mv² are the same function — True at every sampled point."""
    symbols = {"m": {"test": {"from": 1.0, "to": 3.0}}, "v": {"test": {"from": 1.0, "to": 4.0}}}
    assert equivalent(r"\frac{1}{2} m v^2", r"\frac{m v^2}{2}", symbols) is True


def test_equivalent_bails_to_none_not_false():
    """P4: when the evaluator can't resolve a side (e.g. `\\log`, ambiguous base), the verdict is
    None — never a guessed True or a false-alarm False."""
    symbols = {"x": {"test": {"from": 1.0, "to": 2.0}}}
    assert equivalent(r"\log x", r"\log x", symbols) is None
    # An undeclared symbol also bails to None (no value to sample).
    assert equivalent(r"a + b", r"b + a", {"a": {"test": 1.0}}) is None


def test_equivalent_resamples_across_a_bad_domain():
    """A range that crosses `\\sqrt`'s domain edge: points where the arg is negative evaluate to
    None and are resampled; enough good points remain to still return a verdict."""
    symbols = {"x": {"test": {"from": -1.0, "to": 1.0}}}
    d = equivalent_detail(r"\sqrt{x}", r"\sqrt{x}", symbols)
    assert d.verdict is True
    assert d.points_used >= 2  # resampling recovered usable points from the positive half

    # A range entirely in the bad domain yields no usable sample points: the *sampling* layer can't
    # tell (None, never a false False). (With the optional CAS extra the public `equivalent`
    # upgrades identical expressions to a provable True — not a guess; see test_cas.)
    from mtph.mathr.equiv import _sampled_detail
    bad = {"x": {"test": {"from": -2.0, "to": -1.0}}}
    assert _sampled_detail(r"\sqrt{x}", r"\sqrt{x}", bad, 5).verdict is None


def test_equivalent_detail_reports_points_and_error():
    """`equivalent_detail` exposes what plan 13's findings quote: verdict, points_used, max_rel_err.
    A single pinned point is honest about being one point."""
    pinned = {"g": {"dim": "acceleration", "test": 9.8}, "L": {"test": 3.0}}
    d = equivalent_detail(r"\sqrt{g/L}", r"\sqrt{g/L}", pinned)
    assert isinstance(d, EquivDetail)
    assert d.verdict is True
    assert d.points_used == 1          # all symbols pinned → one distinct point
    assert d.max_rel_err <= 1e-6

    diff = equivalent_detail(r"g L", r"2 g L", {"g": {"test": {"from": 1.0, "to": 2.0}}, "L": {"test": {"from": 1.0, "to": 2.0}}})
    assert diff.verdict is False
    assert diff.max_rel_err > 0.4      # differs by a factor of 2 everywhere
