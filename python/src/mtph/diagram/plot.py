"""Compile a plot spec into an SVG function plot.

Independent x/y scaling (unlike the equal-aspect figure :class:`~mtph.diagram.shapes.Scene`),
axes through the origin with "nice" ticks, optional grid, marked points and reference lines.
Expressions are evaluated by a small safe shunting-yard parser — never Python ``eval``.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

from ..mathr.latex import label_runs, sub_sup_spans

# -- safe expression evaluator ------------------------------------------------
_FUNCS = {
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan,
    "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
    "exp": math.exp, "sqrt": math.sqrt, "floor": math.floor, "ceil": math.ceil,
    "ln": math.log, "log": math.log10, "abs": abs,
    "sign": lambda v: (v > 0) - (v < 0),
}
_CONSTS = {"pi": math.pi, "e": math.e}
_TOKEN = re.compile(r"\d+\.?\d*(?:[eE][+-]?\d+)?|[A-Za-z_]\w*|[-+*/^(),]|\S")
# Unary minus sits between * and ^ so that "-x^2" parses as -(x^2), the usual convention.
# (Write "a^(-b)" for a negative exponent.)
_PREC = {"+": 2, "-": 2, "*": 3, "/": 3, "u-": 3.5, "^": 4}
_RIGHT = {"^", "u-"}


class PlotError(ValueError):
    pass


def _to_rpn(expr: str, var="x") -> List[str]:
    variables = (var,) if isinstance(var, str) else tuple(var)
    tokens = _TOKEN.findall(expr)
    out: List[str] = []
    ops: List[str] = []
    prev: Optional[str] = None
    for tok in tokens:
        if re.match(r"^\d", tok) or tok in _CONSTS or tok in variables:
            out.append(tok)
        elif tok in _FUNCS:
            ops.append(tok)
        elif tok == ",":
            while ops and ops[-1] != "(":
                out.append(ops.pop())
        elif tok in "+-*/^":
            op = "u-" if (tok == "-" and prev in (None, "(", ",", "+", "-", "*", "/", "^")) else tok
            while ops and ops[-1] != "(" and (
                _PREC.get(ops[-1], 0) > _PREC[op]
                or (_PREC.get(ops[-1], 0) == _PREC[op] and op not in _RIGHT)
            ):
                out.append(ops.pop())
            ops.append(op)
        elif tok == "(":
            ops.append(tok)
        elif tok == ")":
            while ops and ops[-1] != "(":
                out.append(ops.pop())
            if not ops:
                raise PlotError(f"unbalanced ')' in {expr!r}")
            ops.pop()
            if ops and ops[-1] in _FUNCS:
                out.append(ops.pop())
        else:
            raise PlotError(f"unexpected token {tok!r} in {expr!r}")
        prev = tok
    while ops:
        if ops[-1] in "()":
            raise PlotError(f"unbalanced parenthesis in {expr!r}")
        out.append(ops.pop())
    return out


def _eval_rpn(rpn: List[str], env: dict) -> Optional[float]:
    """Evaluate compiled RPN with variable values in ``env``; None on any math error/non-finite."""
    stack: List[float] = []
    try:
        for tok in rpn:
            if tok in env:
                stack.append(env[tok])
            elif tok in _CONSTS:
                stack.append(_CONSTS[tok])
            elif re.match(r"^\d", tok):
                stack.append(float(tok))
            elif tok == "u-":
                stack.append(-stack.pop())
            elif tok in _FUNCS:
                stack.append(float(_FUNCS[tok](stack.pop())))
            else:
                b = stack.pop()
                a = stack.pop()
                stack.append(
                    a + b if tok == "+" else a - b if tok == "-"
                    else a * b if tok == "*" else a / b if tok == "/"
                    else a ** b
                )
        v = stack.pop()
        return v if math.isfinite(v) else None
    except (ValueError, ZeroDivisionError, OverflowError, IndexError):
        return None


def make_func(expr: str, var: str = "x") -> Callable[[float], Optional[float]]:
    rpn = _to_rpn(expr, var)
    return lambda x: _eval_rpn(rpn, {var: x})


def make_func2(expr: str, vx: str = "x", vy: str = "y") -> Callable[[float, float], Optional[float]]:
    """A safe evaluator of an expression in two variables — for vector fields and implicit curves."""
    rpn = _to_rpn(expr, (vx, vy))
    return lambda x, y: _eval_rpn(rpn, {vx: x, vy: y})


# -- spec model ---------------------------------------------------------------
@dataclass
class PlotSpec:
    mode: str = "function"  # function | parametric | polar | vectorfield | implicit
    xr: Tuple[float, float] = (-5.0, 5.0)
    xr_set: bool = False  # did the author give an explicit x range?
    yr: Optional[Tuple[float, float]] = None
    funcs: List[str] = field(default_factory=list)
    marks: List[Tuple[float, float, str, str]] = field(default_factory=list)  # x, y, label, color
    vlines: List[float] = field(default_factory=list)
    hlines: List[float] = field(default_factory=list)
    samples: int = 240
    grid: bool = False
    xlabel: str = "x"
    ylabel: str = "y"
    # parametric mode: x(t), y(t) over t in `tr`; polar mode: r(theta) over `tr`
    param_var: str = "t"
    xexpr: Optional[str] = None
    yexpr: Optional[str] = None
    rexpr: Optional[str] = None
    tr: Tuple[float, float] = (0.0, 1.0)
    # vectorfield mode: u(x,y), v(x,y); implicit mode: F(x,y) = 0 — both over (xr, yr)
    field_vars: Tuple[str, str] = ("x", "y")
    uexpr: Optional[str] = None
    vexpr: Optional[str] = None
    fexpr: Optional[str] = None


_FUNC_RE = re.compile(r"^\w+\s*\(\s*x\s*\)\s*=\s*(.+)$")
# parametric component: `x(t) = ...` / `y(t) = ...` (the variable name is captured)
_PARAM_RE = re.compile(r"^([xy])\s*\(\s*([A-Za-z]\w*)\s*\)\s*=\s*(.+)$")
# polar: `r(theta) = ...`
_POLAR_RE = re.compile(r"^r\s*\(\s*([A-Za-z]\w*)\s*\)\s*=\s*(.+)$")
# vectorfield component `u(x,y) = …`; implicit `F(x,y) = …` (name, then two var names, then expr)
_FIELD_RE = re.compile(r"^([uv])\s*\(\s*([A-Za-z]\w*)\s*,\s*([A-Za-z]\w*)\s*\)\s*=\s*(.+)$")
_IMPLICIT_RE = re.compile(r"^[A-Za-z]\w*\s*\(\s*([A-Za-z]\w*)\s*,\s*([A-Za-z]\w*)\s*\)\s*=\s*(.+)$")
_MODES = ("function", "parametric", "polar", "vectorfield", "implicit")


def parse_plot(source: str) -> PlotSpec:
    spec = PlotSpec()
    # a first pass to pick up `mode:` regardless of line order
    for raw in source.splitlines():
        s = raw.strip()
        if s.lower().startswith("mode:"):
            spec.mode = s.split(":", 1)[1].strip().lower()
    if spec.mode not in _MODES:
        raise PlotError(f"unknown plot mode {spec.mode!r} (use one of {', '.join(_MODES)})")
    if spec.mode == "polar":
        spec.param_var = "theta"

    parser = {"parametric": _parse_parametric, "polar": _parse_polar,
              "vectorfield": _parse_vectorfield, "implicit": _parse_implicit,
              }.get(spec.mode, _parse_function)
    for raw in source.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.lower().startswith("mode:"):
            continue
        parser(spec, line)

    if spec.mode == "parametric":
        if not (spec.xexpr and spec.yexpr):
            raise PlotError("parametric plot needs both 'x(t) = ...' and 'y(t) = ...'")
    elif spec.mode == "polar":
        if not spec.rexpr:
            raise PlotError("polar plot needs 'r(theta) = ...'")
    elif spec.mode == "vectorfield":
        if not (spec.uexpr and spec.vexpr):
            raise PlotError("vectorfield plot needs both 'u(x,y) = ...' and 'v(x,y) = ...'")
    elif spec.mode == "implicit":
        if not spec.fexpr:
            raise PlotError("implicit plot needs 'F(x,y) = ...' (the curve F = 0)")
    elif not spec.funcs and not spec.marks:
        raise PlotError("plot needs at least one 'name(x) = ...' or a 'mark:'")
    return spec


def _parse_common(spec: PlotSpec, key: str, val: str) -> bool:
    """Directives shared by all modes. Returns True if handled."""
    if key == "mark":
        spec.marks.append(_mark(val))
    elif key == "vline":
        spec.vlines.append(float(val))
    elif key == "hline":
        spec.hlines.append(float(val))
    elif key == "samples":
        spec.samples = max(8, int(float(val)))
    elif key == "grid":
        spec.grid = val.lower() in ("true", "1", "yes")
    elif key == "xlabel":
        spec.xlabel = _unquote(val)
    elif key == "ylabel":
        spec.ylabel = _unquote(val)
    else:
        return False
    return True


def _parse_function(spec: PlotSpec, line: str) -> None:
    m = _FUNC_RE.match(line)
    if m:
        spec.funcs.append(m.group(1).strip())
        return
    key, _, val = line.partition(":")
    key, val = key.strip(), val.strip()
    if key == "x":
        spec.xr = _range(val)
        spec.xr_set = True
    elif key == "y":
        spec.yr = _range(val)
    elif not _parse_common(spec, key, val):
        raise PlotError(f"unknown plot directive {key!r}")


def _parse_parametric(spec: PlotSpec, line: str) -> None:
    m = _PARAM_RE.match(line)
    if m:
        axis, var, expr = m.group(1), m.group(2), m.group(3).strip()
        spec.param_var = var
        if axis == "x":
            spec.xexpr = expr
        else:
            spec.yexpr = expr
        return
    key, _, val = line.partition(":")
    key, val = key.strip(), val.strip()
    if key == "x":  # optional explicit axis limits
        spec.xr = _range(val)
        spec.xr_set = True
    elif key == "y":
        spec.yr = _range(val)
    elif _parse_common(spec, key, val):
        return
    elif ".." in val:  # the parameter range, e.g. `t: 0..20`
        spec.param_var = key
        spec.tr = _range(val)
    else:
        raise PlotError(f"unknown plot directive {key!r}")


def _parse_polar(spec: PlotSpec, line: str) -> None:
    m = _POLAR_RE.match(line)
    if m:
        spec.param_var = m.group(1)
        spec.rexpr = m.group(2).strip()
        return
    key, _, val = line.partition(":")
    key, val = key.strip(), val.strip()
    if key == "x":
        spec.xr = _range(val)
        spec.xr_set = True
    elif key == "y":
        spec.yr = _range(val)
    elif _parse_common(spec, key, val):
        return
    elif ".." in val:  # the angle range, e.g. `theta: 0..2*pi`
        spec.param_var = key
        spec.tr = _range(val)
    else:
        raise PlotError(f"unknown plot directive {key!r}")


def _parse_xy_or_common(spec: PlotSpec, line: str) -> None:
    """Shared tail for the 2-D modes: `x:`/`y:` ranges or a common directive."""
    key, _, val = line.partition(":")
    key, val = key.strip(), val.strip()
    if key == "x":
        spec.xr = _range(val)
        spec.xr_set = True
    elif key == "y":
        spec.yr = _range(val)
    elif not _parse_common(spec, key, val):
        raise PlotError(f"unknown plot directive {key!r}")


def _parse_vectorfield(spec: PlotSpec, line: str) -> None:
    m = _FIELD_RE.match(line)
    if m:
        comp, vx, vy, expr = m.group(1), m.group(2), m.group(3), m.group(4).strip()
        spec.field_vars = (vx, vy)
        if comp == "u":
            spec.uexpr = expr
        else:
            spec.vexpr = expr
        return
    _parse_xy_or_common(spec, line)


def _parse_implicit(spec: PlotSpec, line: str) -> None:
    m = _IMPLICIT_RE.match(line)
    if m:
        spec.field_vars = (m.group(1), m.group(2))
        spec.fexpr = m.group(3).strip()
        return
    _parse_xy_or_common(spec, line)


def _num(s: str) -> float:
    """Evaluate a range endpoint: a plain number or a constant expression like ``2*pi``."""
    v = make_func(s.strip())(0.0)  # no variable; uses the safe evaluator (pi, e, arithmetic)
    if v is None:
        raise PlotError(f"bad number/expression {s!r} in range")
    return v


def _range(s: str) -> Tuple[float, float]:
    if ".." not in s:
        raise PlotError(f"expected range 'a..b', got {s!r}")
    a, b = s.split("..", 1)
    return (_num(a), _num(b))


def _unquote(s: str) -> str:
    s = s.strip()
    return s[1:-1] if len(s) >= 2 and s[0] == '"' and s[-1] == '"' else s


def _mark(val: str) -> Tuple[float, float, str, str]:
    m = re.match(r"\(\s*([-\d.eE]+)\s*,\s*([-\d.eE]+)\s*\)(.*)", val)
    if not m:
        raise PlotError(f"bad mark {val!r}; expected '(x, y) [label=\"...\"] [color=...]'")
    rest = m.group(3)
    lm = re.search(r'label\s*=\s*"([^"]*)"', rest)
    cm = re.search(r'color\s*=\s*"?([A-Za-z#][\w#]*)"?', rest)
    return (float(m.group(1)), float(m.group(2)),
            lm.group(1) if lm else "", cm.group(1) if cm else "")


# -- rendering ----------------------------------------------------------------
W, H = 560.0, 380.0
ML, MR, MT, MB = 44.0, 22.0, 18.0, 36.0
_DASH = [None, "7 5", "2 4", "10 4 2 4"]


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _pct(sorted_vals: List[float], p: float) -> float:
    k = (len(sorted_vals) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)


def _nice(x: float) -> float:
    if x <= 0:
        return 1.0
    exp = math.floor(math.log10(x))
    f = x / 10 ** exp
    nf = 1 if f < 1.5 else 2 if f < 3 else 5 if f < 7 else 10
    return nf * 10 ** exp


def _ticks(lo: float, hi: float) -> List[float]:
    step = _nice((hi - lo) / 6)
    start = math.ceil(lo / step) * step
    vals = []
    v = start
    while v <= hi + step * 1e-6:
        vals.append(round(v, 10))
        v += step
    return vals


def _text(x, y, runs_src, *, anchor="middle", baseline="central", size=14, italic=False):
    inner = sub_sup_spans(label_runs(runs_src), size)
    style = ' font-style="italic"' if italic else ""
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" text-anchor="{anchor}" dominant-baseline="{baseline}" '
        f'font-size="{size}"{style}>{inner}</text>'
    )


def compile_plot(source: str) -> str:
    spec = parse_plot(source)
    return {
        "parametric": _compile_parametric,
        "polar": _compile_polar,
        "vectorfield": _compile_vectorfield,
        "implicit": _compile_implicit,
    }.get(spec.mode, _compile_function)(spec)


def _render_frame(spec: PlotSpec, x0, x1, y0, y1):
    """Emit the shared plot frame (svg open, grid, axes, ticks, reference lines).

    Returns ``(out, sx, sy, ax_x, ax_y)`` — caller adds curves, then calls :func:`_close_frame`.
    """
    pw, ph = W - ML - MR, H - MT - MB

    def sx(x: float) -> float:
        return ML + (x - x0) / (x1 - x0) * pw

    def sy(y: float) -> float:
        return MT + (y1 - y) / (y1 - y0) * ph

    # fill="currentColor" so axis/tick text inherits the page ink (black standalone, light on a
    # dark page); axes and curves use currentColor strokes for the same reason.
    out: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} {H:.0f}" '
        f'width="{W:.0f}" height="{H:.0f}" fill="currentColor" '
        f'font-family="Georgia, \'Times New Roman\', serif">'
    ]
    xt = _ticks(x0, x1)
    yt = _ticks(y0, y1)
    if spec.grid:
        for xv in xt:
            out.append(f'<line x1="{sx(xv):.2f}" y1="{MT:.2f}" x2="{sx(xv):.2f}" y2="{MT+ph:.2f}" stroke="#e6e6e6" stroke-width="1"/>')
        for yv in yt:
            out.append(f'<line x1="{ML:.2f}" y1="{sy(yv):.2f}" x2="{ML+pw:.2f}" y2="{sy(yv):.2f}" stroke="#e6e6e6" stroke-width="1"/>')

    ax_y = sy(0.0) if y0 <= 0 <= y1 else (MT + ph if y0 > 0 else MT)
    ax_x = sx(0.0) if x0 <= 0 <= x1 else (ML if x0 > 0 else ML + pw)
    out.append(f'<line x1="{ML:.2f}" y1="{ax_y:.2f}" x2="{ML+pw:.2f}" y2="{ax_y:.2f}" stroke="currentColor" stroke-width="1.4"/>')
    out.append(f'<line x1="{ax_x:.2f}" y1="{MT:.2f}" x2="{ax_x:.2f}" y2="{MT+ph:.2f}" stroke="currentColor" stroke-width="1.4"/>')

    for xv in xt:
        if abs(xv) < 1e-9:
            continue
        px = sx(xv)
        out.append(f'<line x1="{px:.2f}" y1="{ax_y-3:.2f}" x2="{px:.2f}" y2="{ax_y+3:.2f}" stroke="currentColor" stroke-width="1.2"/>')
        out.append(_text(px, ax_y + 13, f"{xv:g}", size=12))
    for yv in yt:
        if abs(yv) < 1e-9:
            continue
        py = sy(yv)
        out.append(f'<line x1="{ax_x-3:.2f}" y1="{py:.2f}" x2="{ax_x+3:.2f}" y2="{py:.2f}" stroke="currentColor" stroke-width="1.2"/>')
        out.append(_text(ax_x - 8, py, f"{yv:g}", anchor="end", size=12))

    for xv in spec.vlines:
        out.append(f'<line x1="{sx(xv):.2f}" y1="{MT:.2f}" x2="{sx(xv):.2f}" y2="{MT+ph:.2f}" stroke="#888" stroke-width="1" stroke-dasharray="5 4"/>')
    for yv in spec.hlines:
        out.append(f'<line x1="{ML:.2f}" y1="{sy(yv):.2f}" x2="{ML+pw:.2f}" y2="{sy(yv):.2f}" stroke="#888" stroke-width="1" stroke-dasharray="5 4"/>')

    return out, sx, sy, ax_x, ax_y


def _close_frame(out: List[str], spec: PlotSpec, sx, sy, ax_x, ax_y) -> str:
    pw, ph = W - ML - MR, H - MT - MB
    for mx, my, label, color in spec.marks:
        out.append(f'<circle cx="{sx(mx):.2f}" cy="{sy(my):.2f}" r="3.4" '
                   f'fill="{color or "currentColor"}"/>')
        if label:
            out.append(_text(sx(mx) + 8, sy(my) - 8, label, anchor="start", size=14, italic=True))
    out.append(_text(ML + pw, ax_y - 10, spec.xlabel, anchor="end", size=15, italic=True))
    out.append(_text(ax_x + 12, MT + 2, spec.ylabel, anchor="start", size=15, italic=True))
    out.append("</svg>")
    return "\n".join(out)


def _compile_function(spec: PlotSpec) -> str:
    funcs = [make_func(e) for e in spec.funcs]
    x0, x1 = spec.xr
    if x1 <= x0:
        raise PlotError("x domain must have a < b")

    n = spec.samples
    xs = [x0 + (x1 - x0) * i / n for i in range(n + 1)]
    sampled: List[List[Optional[float]]] = [[f(x) for x in xs] for f in funcs]

    if spec.yr:
        y0, y1 = spec.yr
    else:
        finite = sorted(v for col in sampled for v in col if v is not None)
        if finite:
            lo_f, hi_f = finite[0], finite[-1]
            lo_r, hi_r = _pct(finite, 0.02), _pct(finite, 0.98)
            # Only clip when the spread is pathological (e.g. tan near an asymptote),
            # so ordinary functions keep their exact range.
            if hi_r > lo_r and (hi_f - lo_f) > 4 * (hi_r - lo_r):
                y0, y1 = lo_r, hi_r
            else:
                y0, y1 = lo_f, hi_f
            for _mx, my, _l, _c in spec.marks:
                y0, y1 = min(y0, my), max(y1, my)
            pad = (y1 - y0) * 0.08 or 1.0
            y0, y1 = y0 - pad, y1 + pad
        else:
            y0, y1 = -1.0, 1.0
    if y1 <= y0:
        y1 = y0 + 1.0

    out, sx, sy, ax_x, ax_y = _render_frame(spec, x0, x1, y0, y1)

    # curves (split into segments at gaps / asymptote jumps)
    for idx, col in enumerate(sampled):
        dash = _DASH[idx % len(_DASH)]
        dattr = f' stroke-dasharray="{dash}"' if dash else ""
        seg: List[str] = []
        prev_y: Optional[float] = None
        for x, y in zip(xs, col):
            broken = y is None or (prev_y is not None and abs(y - prev_y) > (y1 - y0) * 4)
            if broken:
                _flush_poly(out, seg, dattr)
                seg = []
            if y is not None and y0 - (y1 - y0) * 2 <= y <= y1 + (y1 - y0) * 2:
                seg.append(f"{sx(x):.2f},{sy(max(min(y, y1 + (y1-y0)), y0 - (y1-y0))):.2f}")
            prev_y = y
        _flush_poly(out, seg, dattr)

    return _close_frame(out, spec, sx, sy, ax_x, ax_y)


def _equal_aspect(x0, x1, y0, y1):
    """Expand ranges so logical units map uniformly to pixels (circles look circular)."""
    pw, ph = W - ML - MR, H - MT - MB
    scale = max((x1 - x0) / pw, (y1 - y0) / ph)
    tw, th = scale * pw, scale * ph
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return cx - tw / 2, cx + tw / 2, cy - th / 2, cy + th / 2


def _sample_param(spec: PlotSpec) -> List[Optional[Tuple[float, float]]]:
    t0, t1 = spec.tr
    if t1 <= t0:
        raise PlotError("parameter range must have a < b (e.g. 't: 0..10')")
    n = spec.samples
    if spec.mode == "polar":
        fr = make_func(spec.rexpr, spec.param_var)
        pts = []
        for i in range(n + 1):
            th = t0 + (t1 - t0) * i / n
            r = fr(th)
            pts.append((r * math.cos(th), r * math.sin(th)) if r is not None else None)
        return pts
    fx = make_func(spec.xexpr, spec.param_var)
    fy = make_func(spec.yexpr, spec.param_var)
    pts = []
    for i in range(n + 1):
        t = t0 + (t1 - t0) * i / n
        xv, yv = fx(t), fy(t)
        pts.append((xv, yv) if (xv is not None and yv is not None) else None)
    return pts


def _render_trajectory(spec: PlotSpec, pts: List[Optional[Tuple[float, float]]], what: str) -> str:
    """Shared rendering for parametric & polar: auto equal-aspect frame + a connected path."""
    finite = [p for p in pts if p is not None]
    if not finite:
        raise PlotError(f"{what} produced no finite points; check the expression(s) and the range")

    explicit = spec.xr_set or (spec.yr is not None)
    if spec.xr_set:
        x0, x1 = spec.xr
    else:
        xv = [p[0] for p in finite]
        x0, x1 = min(xv), max(xv)
    if spec.yr is not None:
        y0, y1 = spec.yr
    else:
        yv = [p[1] for p in finite]
        y0, y1 = min(yv), max(yv)
    for mx, my, _l, _c in spec.marks:
        x0, x1, y0, y1 = min(x0, mx), max(x1, mx), min(y0, my), max(y1, my)
    if x1 <= x0:
        x0, x1 = x0 - 1, x1 + 1
    if y1 <= y0:
        y0, y1 = y0 - 1, y1 + 1
    if not explicit:
        # equal aspect so trajectories/orbits aren't distorted, then a small margin
        x0, x1, y0, y1 = _equal_aspect(x0, x1, y0, y1)
        padx, pady = (x1 - x0) * 0.06, (y1 - y0) * 0.06
        x0, x1, y0, y1 = x0 - padx, x1 + padx, y0 - pady, y1 + pady

    out, sx, sy, ax_x, ax_y = _render_frame(spec, x0, x1, y0, y1)
    seg: List[str] = []
    for p in pts:
        if p is None:
            _flush_poly(out, seg, "")
            seg = []
        else:
            seg.append(f"{sx(p[0]):.2f},{sy(p[1]):.2f}")
    _flush_poly(out, seg, "")
    return _close_frame(out, spec, sx, sy, ax_x, ax_y)


def _compile_parametric(spec: PlotSpec) -> str:
    return _render_trajectory(spec, _sample_param(spec), "parametric plot")


def _compile_polar(spec: PlotSpec) -> str:
    return _render_trajectory(spec, _sample_param(spec), "polar plot")


def _flush_poly(out: List[str], seg: List[str], dattr: str) -> None:
    if len(seg) >= 2:
        out.append(
            f'<polyline points="{" ".join(seg)}" fill="none" stroke="currentColor" '
            f'stroke-width="2" stroke-linejoin="round" stroke-linecap="round"{dattr}/>'
        )


def _arrow_svg(p1, p2, color="currentColor", w=1.2, head=5.0) -> str:
    """A small arrow (line + filled head) in screen pixels, for vector-field glyphs."""
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    n = math.hypot(dx, dy)
    if n < 1e-6:
        return ""
    ux, uy = dx / n, dy / n
    px, py = -uy, ux
    bx, by = p2[0] - ux * head, p2[1] - uy * head
    lx, ly = bx + px * head * 0.5, by + py * head * 0.5
    rx, ry = bx - px * head * 0.5, by - py * head * 0.5
    return (
        f'<line x1="{p1[0]:.2f}" y1="{p1[1]:.2f}" x2="{p2[0]:.2f}" y2="{p2[1]:.2f}" '
        f'stroke="{color}" stroke-width="{w}"/>'
        f'<polygon points="{p2[0]:.2f},{p2[1]:.2f} {lx:.2f},{ly:.2f} {rx:.2f},{ry:.2f}" fill="{color}"/>'
    )


def _xy_domain(spec: PlotSpec) -> Tuple[float, float, float, float]:
    x0, x1 = spec.xr
    y0, y1 = spec.yr if spec.yr is not None else spec.xr  # default to a square domain
    if x1 <= x0 or y1 <= y0:
        raise PlotError("x and y domains must each have a < b (e.g. 'x: -2..2')")
    return x0, x1, y0, y1


def _compile_vectorfield(spec: PlotSpec) -> str:
    vx, vy = spec.field_vars
    fu, fv = make_func2(spec.uexpr, vx, vy), make_func2(spec.vexpr, vx, vy)
    # equal aspect so directions aren't sheared (a 45° vector looks 45°)
    x0, x1, y0, y1 = _equal_aspect(*_xy_domain(spec))
    out, sx, sy, ax_x, ax_y = _render_frame(spec, x0, x1, y0, y1)

    n = 11  # arrows per axis
    cellx, celly = (x1 - x0) / (n - 1), (y1 - y0) / (n - 1)
    samples = []
    for i in range(n):
        for j in range(n):
            x, y = x0 + cellx * i, y0 + celly * j
            u, v = fu(x, y), fv(x, y)
            if u is None or v is None:
                continue
            samples.append((x, y, u, v, math.hypot(u, v)))

    # Soft, saturating scale: length = L·mag/(mag+scale) with `scale` the median magnitude. Unlike
    # normalizing by the max, a singularity (a 1/r² field near a charge) saturates to L instead of
    # shrinking every other arrow to a nub, while a calm region (mag≈0) stays calm and the bulk
    # keeps proportional lengths. Robust across smooth and singular fields.
    mags = sorted(m for *_r, m in samples if m > 0)
    scale = mags[len(mags) // 2] if mags else 1.0
    L = 0.9 * min(cellx, celly)
    for x, y, u, v, mag in samples:
        if mag < 1e-12:
            continue
        f = L * mag / (mag + scale) / mag  # per-unit-vector length factor
        ex, ey = x + u * f, y + v * f
        out.append(_arrow_svg((sx(x), sy(y)), (sx(ex), sy(ey))))
    return _close_frame(out, spec, sx, sy, ax_x, ax_y)


def _compile_implicit(spec: PlotSpec) -> str:
    vx, vy = spec.field_vars
    F = make_func2(spec.fexpr, vx, vy)
    # equal aspect so a circle reads as a circle, not an ellipse
    x0, x1, y0, y1 = _equal_aspect(*_xy_domain(spec))
    out, sx, sy, ax_x, ax_y = _render_frame(spec, x0, x1, y0, y1)

    n = max(20, min((spec.samples or 240) // 4, 120))  # marching-squares grid resolution
    xs = [x0 + (x1 - x0) * i / n for i in range(n + 1)]
    ys = [y0 + (y1 - y0) * j / n for j in range(n + 1)]
    vals = [[F(x, y) for y in ys] for x in xs]

    def cross(pa, pb, fa, fb):
        t = fa / (fa - fb)  # fa, fb have opposite signs → denominator non-zero
        return (pa[0] + (pb[0] - pa[0]) * t, pa[1] + (pb[1] - pa[1]) * t)

    for i in range(n):
        for j in range(n):
            corners = [
                ((xs[i], ys[j]), vals[i][j]),
                ((xs[i + 1], ys[j]), vals[i + 1][j]),
                ((xs[i + 1], ys[j + 1]), vals[i + 1][j + 1]),
                ((xs[i], ys[j + 1]), vals[i][j + 1]),
            ]
            if any(val is None for _p, val in corners):
                continue
            hits = []
            for k in range(4):
                (pa, fa), (pb, fb) = corners[k], corners[(k + 1) % 4]
                if (fa <= 0) != (fb <= 0) and fa != fb:
                    hits.append(cross(pa, pb, fa, fb))
            pairs = []
            if len(hits) == 2:
                pairs = [(hits[0], hits[1])]
            elif len(hits) == 4:  # saddle — connect adjacent crossings
                pairs = [(hits[0], hits[1]), (hits[2], hits[3])]
            for a, b in pairs:
                out.append(f'<line x1="{sx(a[0]):.2f}" y1="{sy(a[1]):.2f}" '
                           f'x2="{sx(b[0]):.2f}" y2="{sy(b[1]):.2f}" stroke="currentColor" '
                           f'stroke-width="2" stroke-linecap="round"/>')
    return _close_frame(out, spec, sx, sy, ax_x, ax_y)
