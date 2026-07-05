"""Numeric spot-check (H2): the evaluator (mathr.numeric) and the verify `numeric` group."""
import math

from mtph.mathr.numeric import eval_latex
from mtph.verify import verify


# --------------------------------------------------------------------------- the evaluator
def test_eval_basic_arithmetic():
    assert eval_latex(r"2 + 3*4", {}) == 14.0
    assert eval_latex(r"2^{10}", {}) == 1024.0
    assert eval_latex(r"-3 + 5", {}) == 2.0


def test_eval_takes_rhs_of_equation():
    # only the right-hand side is evaluated
    assert eval_latex(r"T = 3 + 4", {}) == 7.0
    assert eval_latex(r"E = \frac{1}{2} m v^2", {"m": 2, "v": 3}) == 9.0


def test_eval_frac_and_sqrt():
    assert eval_latex(r"\frac{L}{g}", {"L": 6, "g": 2}) == 3.0
    assert math.isclose(eval_latex(r"\sqrt{2}", {}), math.sqrt(2))
    assert math.isclose(eval_latex(r"\sqrt[3]{27}", {}), 3.0)


def test_eval_constants_without_declaration():
    assert math.isclose(eval_latex(r"2\pi", {}), 2 * math.pi)
    assert math.isclose(eval_latex(r"e", {}), math.e)
    assert math.isclose(eval_latex(r"\tau", {}), math.tau)


def test_eval_functions():
    assert math.isclose(eval_latex(r"\sin(0)", {}), 0.0)
    assert math.isclose(eval_latex(r"\cos(0)", {}), 1.0)
    assert math.isclose(eval_latex(r"\sin^2 x + \cos^2 x", {"x": 0.7}), 1.0)
    assert math.isclose(eval_latex(r"\ln(e)", {}), 1.0)


def test_eval_pendulum_period():
    got = eval_latex(r"T = 2\pi\sqrt{L/g}", {"L": 1, "g": 9.8})
    assert math.isclose(got, 2 * math.pi * math.sqrt(1 / 9.8))


def test_eval_symbol_with_subscript():
    # the tokenizer normalizes `v_0` → sym "v_0", which must resolve against the values map
    assert eval_latex(r"v_0^2", {"v_0": 4}) == 16.0


# --- conservative bails: anything ambiguous returns None, never a wrong number (P4) ---
def test_eval_bails_on_undeclared_symbol():
    assert eval_latex(r"q + 1", {}) is None


def test_eval_bails_on_log_ambiguous_base():
    assert eval_latex(r"\log(100)", {}) is None


def test_eval_bails_on_complex_result():
    assert eval_latex(r"\sqrt{-1}", {}) is None


def test_eval_bails_on_non_finite():
    assert eval_latex(r"1/0", {}) is None


def test_eval_bails_on_unbraced_multidigit_shorthand():
    # `\frac12` means `\frac{1}{2}` in LaTeX, and `x^12` means `x^1·2` — our tokenizer merges the
    # digits, so we bail rather than compute a wrong value. Braced/single-digit forms still work.
    assert eval_latex(r"\tfrac12 m v^2", {"m": 2, "v": 3}) is None
    assert eval_latex(r"x^12", {"x": 2}) is None
    assert eval_latex(r"\frac{1}{2} m v^2", {"m": 2, "v": 3}) == 9.0
    assert math.isclose(eval_latex(r"\sqrt2", {}), math.sqrt(2))  # single digit is fine
    assert eval_latex(r"x^{12}", {"x": 2}) == 4096.0              # braced is fine


# --------------------------------------------------------------------------- the verify check
_DOC = """---
mtph: "0.2"
id: num-test
title: Numeric test
subject: physics
topic: mechanics
difficulty: 2
symbols:
  T: time
  L: { dim: length, test: 1 }
  g: { dim: acceleration, test: 9.8 }
answer:
  type: expression
  value: '{VAL}'
  check: {CHECK}
---
A pendulum of length $L$.
"""


def _num_group(val, check):
    rep = verify(_DOC.replace("{VAL}", val).replace("{CHECK}", str(check)))
    return next(c for c in rep.checks if c.group == "numeric")


def test_check_ok_when_value_matches():
    c = _num_group(r"T = 2\pi\sqrt{L/g}", "2.007")
    assert c.status == "ok" and not c.findings


def test_check_reports_mismatch():
    c = _num_group(r"T = 2\pi\sqrt{L/g}", "4.0")
    assert c.status == "error"
    assert any(f.id == "numeric.mismatch" for f in c.findings)


def test_check_catches_dropped_factor():
    # a dimension check can't see this; the spot-check can
    c = _num_group(r"T = \pi\sqrt{L/g}", "2.007")   # missing the factor of 2
    assert c.status == "error"
    assert any(f.id == "numeric.mismatch" for f in c.findings)


def test_check_rounded_check_within_tolerance():
    c = _num_group(r"T = 2\pi\sqrt{L/g}", "2.01")   # true 2.00709, rounded to 3 sig figs (<1%)
    assert c.status == "ok"


def test_check_unverifiable_when_symbol_lacks_test():
    # references `m`, which has no test value → couldn't evaluate → warning, not a false pass
    c = _num_group(r"E = \frac{1}{2} m g L", "5.0")
    assert c.status == "warning"
    assert any(f.id == "numeric.unverifiable" for f in c.findings)


def test_check_unknown_without_any_check():
    text = _DOC.replace("{VAL}", r"T = 2\pi\sqrt{L/g}")
    # drop the check line entirely
    text = "\n".join(l for l in text.splitlines() if "{CHECK}" not in l)
    rep = verify(text)
    c = next(cc for cc in rep.checks if cc.group == "numeric")
    assert c.status == "unknown"


def test_check_unpinned_range_symbol_warns():
    """Plan 12 decision 5: a `check:` needs a single substitution, so a symbol the answer uses
    that carries a `test:` range (not a pinned number) can't satisfy it — a precise warning
    naming the symbol, not a silent bail or a false mismatch."""
    doc = _DOC.replace("test: 9.8", "test: { from: 9.0, to: 10.0 }")  # g becomes range-only
    rep = verify(doc.replace("{VAL}", r"T = 2\pi\sqrt{L/g}").replace("{CHECK}", "2.007"))
    grp = next(cc for cc in rep.checks if cc.group == "numeric")
    assert grp.status == "warning"
    ids = {f.id for f in grp.findings}
    assert ids == {"numeric.unpinned_symbol"}
    f = grp.findings[0]
    assert "g" in f.message and "range" in f.message
    assert "drop `check:`" in f.fix
