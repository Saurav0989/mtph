"""Dimensional analysis: the engine (mathr.dimension) and the verify check (dimension group)."""
from mtph.mathr.dimension import (
    DIMLESS,
    dim_of_latex,
    normalize_symbol,
    parse_dim_spec,
    parse_unit,
    target_dim_of_lhs,
)
from mtph.verify import verify


def _syms(**kw):
    return {normalize_symbol(k): parse_dim_spec(v) for k, v in kw.items()}


# --------------------------------------------------------------------------- spec + unit parsing
def test_parse_dim_spec_named_and_formula():
    assert str(parse_dim_spec("acceleration")) == "L T^-2"
    assert str(parse_dim_spec("force/length")) == "M T^-2"           # a spring constant
    assert str(parse_dim_spec("mass*length/time^2")) == "M L T^-2"   # a force
    assert str(parse_dim_spec("M L^2 T^-2")) == "M L^2 T^-2"         # base symbols + juxtaposition
    assert parse_dim_spec("dimensionless").dimensionless
    assert parse_dim_spec("angle").dimensionless


def test_parse_dim_spec_rejects_unknown():
    assert parse_dim_spec("bogus") is None
    assert parse_dim_spec("mass/") is None
    assert parse_dim_spec("") is None


def test_parse_unit():
    assert str(parse_unit("m/s^2")) == "L T^-2"
    assert str(parse_unit("N")) == "M L T^-2"
    assert str(parse_unit("kg m/s")) == "M L T^-1"
    assert str(parse_unit("J")) == "M L^2 T^-2"
    assert parse_unit("rad").dimensionless
    assert parse_unit("flibberts") is None


# --------------------------------------------------------------------------- expression dimensions
def test_dim_of_latex_basic():
    s = _syms(g="acceleration", theta="angle", a="acceleration")
    r = dim_of_latex(r"a = g\sin\theta", s)
    assert r.determined and r.uses_symbol and not r.issues
    assert str(r.dim) == "L T^-2"


def test_dim_of_latex_sqrt_and_frac():
    s = _syms(g="acceleration", h="length", v="velocity", r="length")
    assert str(dim_of_latex(r"\sqrt{2gh}", s).dim) == "L T^-1"       # → a velocity
    assert str(dim_of_latex(r"\frac{v^2}{r}", s).dim) == "L T^-2"    # centripetal acceleration


def test_dim_of_latex_pendulum_period():
    s = _syms(L="length", g="acceleration")
    assert str(dim_of_latex(r"2\pi\sqrt{\frac{L}{g}}", s).dim) == "T"


def test_dim_of_latex_flags_inconsistency():
    s = _syms(g="acceleration", v="velocity")
    r = dim_of_latex(r"g + v", s)
    assert r.determined and r.issues and "unlike dimensions" in r.issues[0]


def test_dim_of_latex_flags_transcendental_arg():
    s = _syms(m="mass", g="acceleration")
    r = dim_of_latex(r"g\sin(m)", s)
    assert r.determined and any("must be dimensionless" in i for i in r.issues)


def test_dim_of_latex_is_conservative_on_unknown_symbol():
    s = _syms(g="acceleration")           # phi is not declared
    r = dim_of_latex(r"g\sin\phi", s)
    assert not r.determined and r.dim is None


def test_dim_of_latex_bare_number_uses_no_symbol():
    r = dim_of_latex("9.8", _syms(g="acceleration"))
    assert r.determined and not r.uses_symbol and r.dim == DIMLESS


def test_target_dim_of_lhs():
    s = _syms(a="acceleration", g="acceleration")
    assert str(target_dim_of_lhs(r"a = g", s)) == "L T^-2"
    assert target_dim_of_lhs(r"g\sin\theta", s) is None   # no `=` → no target


# --------------------------------------------------------------------------- the verify check
_DOC = """---
mtph: "0.2"
id: dim-test
title: Dim test
subject: physics
topic: mechanics
difficulty: 2
symbols:
  a: acceleration
  g: acceleration
  theta: angle
answer:
  type: expression
  value: '{VAL}'
---
A block on a frictionless incline of angle $\\theta$.
"""


def _dim_group(text):
    rep = verify(text)
    return next(c for c in rep.checks if c.group == "dimension")


def test_check_ok_for_consistent_answer():
    c = _dim_group(_DOC.replace("{VAL}", r"a = g\sin\theta"))
    assert c.status == "ok" and not c.findings


def test_check_reports_mismatch():
    text = _DOC.replace("a: acceleration", "a: force").replace("{VAL}", r"a = g\sin\theta")
    c = _dim_group(text)
    assert c.status == "error"
    assert any(f.id == "dimension.mismatch" for f in c.findings)


def test_check_reports_inconsistency():
    c = _dim_group(_DOC.replace("{VAL}", r"a = g + g^2"))
    assert c.status == "error"
    assert any(f.id == "dimension.inconsistent" for f in c.findings)


def test_check_unknown_without_symbols():
    text = _DOC.replace("symbols:\n  a: acceleration\n  g: acceleration\n  theta: angle\n", "")
    c = _dim_group(text.replace("{VAL}", r"a = g\sin\theta"))
    assert c.status == "unknown"


def test_check_flags_bad_symbol_spec():
    text = _DOC.replace("theta: angle", "theta: wobble").replace("{VAL}", r"a = g\sin\theta")
    c = _dim_group(text)
    assert any(f.id == "dimension.bad_symbol" for f in c.findings)


def test_numeric_answer_unit_match():
    doc = """---
mtph: "0.2"
id: ke
title: KE
subject: physics
topic: mechanics
difficulty: 2
symbols:
  m: mass
  v: velocity
answer:
  type: numeric
  value: '\\tfrac{1}{2} m v^2'
  unit: '{U}'
---
Kinetic energy.
"""
    assert _dim_group(doc.replace("{U}", "J")).status == "ok"
    bad = _dim_group(doc.replace("{U}", "N"))
    assert bad.status == "error" and any(f.id == "dimension.mismatch" for f in bad.findings)
