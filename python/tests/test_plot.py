import math

import pytest

from mtph.diagram.plot import PlotError, compile_plot, make_func


def test_eval_power():
    assert make_func("x^2")(3) == 9


def test_eval_trig_and_constants():
    assert abs(make_func("sin(x)")(0)) < 1e-12
    assert abs(make_func("cos(pi)")(0) + 1) < 1e-12


def test_eval_precedence():
    assert make_func("2 + 3 * x")(4) == 14


def test_unary_minus():
    assert make_func("-x^2")(3) == -9


def test_division_by_zero_is_gap():
    assert make_func("1/x")(0) is None


def test_domain_error_is_gap():
    assert make_func("sqrt(x)")(-1) is None


def test_compile_plot_svg():
    svg = compile_plot("x: -2..2\nf(x) = x^2\ngrid: true")
    assert svg.startswith("<svg")
    assert "polyline" in svg


def test_empty_plot_raises():
    with pytest.raises(PlotError):
        compile_plot("x: -1..1")


def test_bad_token_raises():
    with pytest.raises(PlotError):
        make_func("x @ 2")


# --------------------------------------------------------------------------- parametric mode
def test_make_func_alternate_variable():
    assert make_func("t^2", "t")(3) == 9


def test_parse_parametric():
    from mtph.diagram.plot import parse_plot
    spec = parse_plot("mode: parametric\nt: 0..6.28\nx(t) = cos(t)\ny(t) = sin(t)")
    assert spec.mode == "parametric"
    assert spec.param_var == "t"
    assert spec.xexpr == "cos(t)" and spec.yexpr == "sin(t)"
    assert spec.tr == (0.0, 6.28)


def test_compile_parametric_svg():
    svg = compile_plot("mode: parametric\nt: 0..6.2832\nx(t) = cos(t)\ny(t) = sin(t)\nsamples: 100")
    assert svg.startswith("<svg")
    assert "polyline" in svg


def test_parametric_requires_both_components():
    with pytest.raises(PlotError):
        compile_plot("mode: parametric\nt: 0..1\nx(t) = t")


def test_parametric_bad_param_range():
    with pytest.raises(PlotError):
        compile_plot("mode: parametric\nt: 1..0\nx(t) = t\ny(t) = t")


def test_unknown_mode_raises():
    with pytest.raises(PlotError):
        compile_plot("mode: spiral\nx(t)=t\ny(t)=t")


def test_function_mode_still_default():
    from mtph.diagram.plot import parse_plot
    assert parse_plot("x: -2..2\nf(x) = x^2").mode == "function"


def test_parametric_mark_renders():
    svg = compile_plot('mode: parametric\nt: 0..6.3\nx(t)=cos(t)\ny(t)=sin(t)\nmark: (1,0) label="P"')
    assert "circle" in svg  # the mark dot


# --------------------------------------------------------------------------- polar mode
def test_range_accepts_expressions():
    from mtph.diagram.plot import parse_plot
    spec = parse_plot("mode: polar\ntheta: 0..2*pi\nr(theta) = 1")
    assert spec.tr[1] == pytest.approx(2 * math.pi)


def test_compile_polar_cardioid():
    svg = compile_plot("mode: polar\ntheta: 0..2*pi\nr(theta) = 1 + cos(theta)\nsamples: 200")
    assert svg.startswith("<svg")
    assert "polyline" in svg


def test_polar_requires_r():
    with pytest.raises(PlotError):
        compile_plot("mode: polar\ntheta: 0..6.28\nx(theta)=1")


def test_polar_default_var_is_theta():
    from mtph.diagram.plot import parse_plot
    spec = parse_plot("mode: polar\nr(theta) = theta\ntheta: 0..6.28")
    assert spec.param_var == "theta"


# -- vectorfield / implicit modes + per-mark colour (plan 04) -----------------
from mtph.diagram.plot import compile_plot, make_func2, parse_plot  # noqa: E402


def test_make_func2_two_variables():
    f = make_func2("x^2 + y^2")
    assert f(3, 4) == 25
    assert make_func2("1/(x-y)")(2, 2) is None


def test_vectorfield_renders_arrows():
    svg = compile_plot("mode: vectorfield\nx: -2..2\ny: -2..2\nu(x,y) = -y\nv(x,y) = x")
    assert svg.startswith("<svg") and svg.count("<polygon") > 10  # arrowheads


def test_vectorfield_needs_both_components():
    with pytest.raises(PlotError):
        parse_plot("mode: vectorfield\nu(x,y) = -y")


def test_implicit_circle_has_segments():
    svg = compile_plot("mode: implicit\nx: -1.5..1.5\ny: -1.5..1.5\nF(x,y) = x^2 + y^2 - 1")
    assert svg.count('stroke-width="2"') > 20  # the curve is many short segments


def test_implicit_needs_an_equation():
    with pytest.raises(PlotError):
        parse_plot("mode: implicit\nx: -1..1")


def test_mark_colour_parsed_and_rendered():
    svg = compile_plot('x: -3..3\nf(x) = x^2\nmark: (1, 1) label="P" color=red')
    assert 'fill="red"' in svg


def test_unknown_mode_rejected():
    with pytest.raises(PlotError):
        parse_plot("mode: hologram\nf(x) = x")


def test_vectorfield_singular_field_renders():
    # a 1/r^2 field (Coulomb-like) must not collapse to nubs or crash — soft normalization
    src = ("mode: vectorfield\nx: -2..2\ny: -2..2\n"
           "u(x,y) = x/(x^2+y^2)^1.5\nv(x,y) = y/(x^2+y^2)^1.5")
    svg = compile_plot(src)
    assert svg.count("<polygon") > 10  # arrows present despite the singularity at the origin
