"""CAS extra (plan 14): symbolic equivalence that upgrades `unverifiable` to a real verdict.

Two audiences here: the **always-on guard** (`test_cas_absent_*`) proves that without sympi the
engine is byte-identical to plan 13 (method `"none"` on a bail); the rest are `skipif`-guarded and
exercise the sympy-backed builder and `sym_equivalent`.
"""
import pytest

from mtph.mathr.equiv import equivalent_detail

try:
    import sympy  # noqa: F401
    HAS_SYMPY = True
except Exception:  # pragma: no cover - environment without the extra
    HAS_SYMPY = False

needs_sympy = pytest.mark.skipif(not HAS_SYMPY, reason="sympy not installed (mtph[cas])")


# --------------------------------------------------------------------------- always-on guard
def test_cas_absent_behaves_like_plan13(monkeypatch):
    """With the extra unavailable, `\\ln(ab)` vs `\\ln a + \\ln b` (no test values) can't be sampled
    and there is no CAS to fall back on → `None`, method `"none"` — exactly plan-13 behavior."""
    import mtph.mathr.cas as cas
    monkeypatch.setattr(cas, "_sympy", lambda: None)
    symbols = {"a": {"dim": "length"}, "b": {"dim": "length"}}
    d = equivalent_detail(r"\ln(a b)", r"\ln a + \ln b", symbols)
    assert d.verdict is None
    assert d.method == "none"


def test_sampling_still_wins_and_is_labelled(monkeypatch):
    """A verdict sampling can reach is still `"sampled"` (CAS never consulted)."""
    import mtph.mathr.cas as cas
    monkeypatch.setattr(cas, "_sympy", lambda: (_ for _ in ()).throw(AssertionError("CAS called")))
    symbols = {"g": {"dim": "acceleration", "test": 9.8}}
    d = equivalent_detail("2 g", "g + g", symbols)
    assert d.verdict is True
    assert d.method == "sampled"


# --------------------------------------------------------------------------- builder (sympy on)
@needs_sympy
def test_builder_round_trips():
    import sympy as sp
    from mtph.mathr.cas import latex_to_sympy
    e = latex_to_sympy(r"\frac{v^2}{2g}", ["v", "g"])
    assert e is not None
    v, g = sp.symbols("v g", positive=True)
    assert sp.simplify(e - v**2 / (2 * g)) == 0


@needs_sympy
def test_builder_bails_on_log_and_undeclared():
    from mtph.mathr.cas import latex_to_sympy
    assert latex_to_sympy(r"\log x", ["x"]) is None          # ambiguous base — excluded like numeric
    assert latex_to_sympy("x + y", ["x"]) is None            # y is not a declared symbol


# --------------------------------------------------------------------------- sym_equivalent
@needs_sympy
def test_sym_equivalent_trig_identity():
    from mtph.mathr.cas import sym_equivalent
    assert sym_equivalent(r"\sin^2\theta + \cos^2\theta", "1", ["theta"]) is True


@needs_sympy
def test_sym_equivalent_log_law_no_test_values():
    """The case sampling *cannot* reach: no test values, yet symbolically provable."""
    from mtph.mathr.cas import sym_equivalent
    assert sym_equivalent(r"\ln(a b)", r"\ln a + \ln b", ["a", "b"]) is True


@needs_sympy
def test_sym_equivalent_provable_mismatch_is_false():
    from mtph.mathr.cas import sym_equivalent
    assert sym_equivalent(r"\sin^2\theta + \cos^2\theta", "2", ["theta"]) is False


@needs_sympy
def test_sym_equivalent_none_on_unbuildable():
    from mtph.mathr.cas import sym_equivalent
    assert sym_equivalent(r"\log x", "x", ["x"]) is None      # can't build → can't tell


@needs_sympy
def test_over_budget_returns_none():
    """The complexity gate keeps verify from hanging: an oversized pair is `None`, not simplified."""
    from mtph.mathr.cas import sym_equivalent
    big = " + ".join(["x"] * 200)
    assert sym_equivalent(big, big, ["x"]) is None


@needs_sympy
def test_equivalent_detail_uses_cas_fallback():
    """Integration: `\\ln(ab)` with declared-but-untested a,b upgrades to a verdict via CAS."""
    symbols = {"a": {"dim": "length"}, "b": {"dim": "length"}}
    d = equivalent_detail(r"\ln(a b)", r"\ln a + \ln b", symbols)
    assert d.verdict is True
    assert d.method == "cas"


@needs_sympy
def test_equivalent_detail_cas_deterministic():
    symbols = {"theta": {"dim": "angle"}}
    a, b = r"\sin^2\theta + \cos^2\theta", "1"
    first = equivalent_detail(a, b, symbols)
    assert all(equivalent_detail(a, b, symbols).verdict is first.verdict for _ in range(3))


_CAS_DOC = """---
mtph: "0.2"
id: cas-solution-demo
title: A log-law step with no test values
subject: math
symbols:
  p: dimensionless
  q: dimensionless
---
Show the log of a product splits.

````solution
$$\\ln(p q) = \\ln p + \\ln q.$$
````
"""


@needs_sympy
def test_solution_step_checked_via_cas():
    """End-to-end: a solution step provable only symbolically (no `test:` values) is *checked*,
    not tallied unverifiable — the `solution` group reaches `steps_checked >= 1` via the extra."""
    from mtph.verify import verify
    rep = verify(_CAS_DOC, path="cas-solution-demo.mtph")
    sol = [c for c in rep.checks if c.group == "solution"][0]
    assert sol.extra["steps_checked"] >= 1
    assert not any(f.severity == "error" for f in sol.findings)
