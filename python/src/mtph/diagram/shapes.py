"""Geometry primitives + the SVG scene.

Everything is built in **logical coordinates with y pointing up** (math convention). The
``Scene`` computes a bounding box, then maps logical units to pixels (flipping y) and emits a
self-contained ``<svg>`` with a fitted ``viewBox``. Stroke widths and font sizes are in
pixels so weights stay consistent regardless of the figure's logical size.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Sequence, Tuple

from ..mathr.latex import label_runs, sub_sup_spans

Pt = Tuple[float, float]

SCALE = 62.0   # pixels per logical unit
PAD = 26.0     # pixel padding around content
W_NORMAL = 2.0
W_THIN = 1.3
W_THICK = 3.0
FONT = 18.0    # label font size (px)

# Default "ink" is ``currentColor`` so figures inherit the page's text colour: black on a
# light page, light on a dark one (the SVG's ``color`` is themed by the HTML). A standalone
# .svg or a cairosvg raster has no CSS context, where ``currentColor`` resolves to black —
# so figures stay correct on white when used on their own. ``PAPER`` is the opaque "knock-out"
# fill (lens bodies, bobs, label halos): white standalone, themed to the dark page in the HTML.
INK = "currentColor"
PAPER = "#ffffff"

_COLORS = {
    "none": "none", "black": "#111111", "white": PAPER,
    "gray": "#888888", "grey": "#888888", "lightgray": "#cccccc",
    "lightgrey": "#cccccc",
}


def color(name: str | None, default: str = INK) -> str:
    if name is None:
        return default
    return _COLORS.get(name, name)


# -- small vector helpers -----------------------------------------------------
def add(a: Pt, b: Pt) -> Pt:
    return (a[0] + b[0], a[1] + b[1])


def sub(a: Pt, b: Pt) -> Pt:
    return (a[0] - b[0], a[1] - b[1])


def mul(a: Pt, s: float) -> Pt:
    return (a[0] * s, a[1] * s)


def length(a: Pt) -> float:
    return math.hypot(a[0], a[1])


def unit(a: Pt) -> Pt:
    n = length(a)
    return (0.0, 0.0) if n == 0 else (a[0] / n, a[1] / n)


def rot(a: Pt, deg: float) -> Pt:
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return (a[0] * c - a[1] * s, a[0] * s + a[1] * c)


def midpoint(a: Pt, b: Pt) -> Pt:
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


def _esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _num(x: float) -> str:
    """Canonical number string (integer-valued → no decimals), so Python and the JS port emit
    identical SVG: ``2.0`` and ``2`` both render as ``2`` (JS ``String(2.0)`` is ``"2"``)."""
    return str(int(x)) if float(x) == int(x) else str(x)


def _f2(x: float) -> str:
    """Two-decimal pixel string that normalises ``-0.00`` → ``0.00``. Used for the animation
    (SMIL) coordinates, where negation and zero components can produce a signed zero that Python's
    ``%.2f`` prints as ``-0.00`` but the JS port's formatter does not — normalising both sides keeps
    the emitted SVG byte-identical."""
    s = f"{x:.2f}"
    return "0.00" if s == "-0.00" else s


# Reusable fill patterns (hatch / crosshatch / dots), emitted only when referenced. They use
# ``currentColor`` so the pattern strokes invert with the rest of the ink in dark mode.
_PATTERN_DEFS = (
    '<defs>'
    '<pattern id="mtph-hatch" patternUnits="userSpaceOnUse" width="6" height="6">'
    '<path d="M0,6 L6,0" stroke="currentColor" stroke-width="0.7"/></pattern>'
    '<pattern id="mtph-crosshatch" patternUnits="userSpaceOnUse" width="6" height="6">'
    '<path d="M0,0 L6,6 M0,6 L6,0" stroke="currentColor" stroke-width="0.6" fill="none"/></pattern>'
    '<pattern id="mtph-dots" patternUnits="userSpaceOnUse" width="6" height="6">'
    '<circle cx="3" cy="3" r="1" fill="currentColor"/></pattern>'
    '</defs>'
)


# -- primitives ---------------------------------------------------------------
@dataclass
class Line:
    p1: Pt
    p2: Pt
    width: float = W_NORMAL
    stroke: str = INK
    dash: str | None = None
    arrow: bool = False
    arrow_start: bool = False


@dataclass
class Path:
    points: List[Pt]
    closed: bool = False
    width: float = W_NORMAL
    stroke: str = INK
    fill: str = "none"
    dash: str | None = None


@dataclass
class Circle:
    c: Pt
    r: float
    width: float = W_NORMAL
    stroke: str = INK
    fill: str = "none"
    dash: str | None = None


@dataclass
class Ellipse:
    c: Pt
    rx: float
    ry: float
    angle: float = 0.0          # rotation in degrees (logical, ccw)
    width: float = W_NORMAL
    stroke: str = INK
    fill: str = "none"
    dash: str | None = None


@dataclass
class BezPath:
    """A general path: segments of ('M'|'L', [pt]), ('C', [c1,c2,end]), ('Q', [c,end]), ('Z', [])."""
    segments: List[Tuple[str, List[Pt]]]
    width: float = W_NORMAL
    stroke: str = INK
    fill: str = "none"
    dash: str | None = None
    arrow: bool = False          # arrowhead at the path end


@dataclass
class Text:
    pos: Pt
    raw: str
    anchor: str = "middle"     # start | middle | end
    baseline: str = "middle"   # middle | auto | hanging
    ox: float = 0.0            # pixel offset x
    oy: float = 0.0            # pixel offset y
    size: float = FONT
    fill: str = INK


@dataclass
class Anim:
    """A micro-animation over a contiguous run of primitives ``prims[start:end]`` (the output of
    one figure command), emitted as SMIL wrapping that run in a ``<g>``. Three verbs only —
    ``spin`` (rotate about a centre), ``oscillate`` (SHM translate), ``along`` (follow a path).
    A static SVG/PNG renderer (cairosvg) ignores SMIL and shows the first, at-rest frame."""
    kind: str                       # "spin" | "oscillate" | "along"
    start: int                      # prim index, inclusive
    end: int                        # prim index, exclusive
    period: float = 3.0             # seconds per cycle
    center: Pt | None = None        # spin: logical centre (default = group bbox centre)
    cw: bool = False                # spin: clockwise (default counter-clockwise, physics +ve)
    swing: float = 0.0              # spin: if >0, oscillate ±swing/2° about centre (a pendulum)
    amp: float = 0.5                # oscillate: amplitude in logical units
    direction: float = 0.0          # oscillate: direction in degrees (logical, ccw from +x)
    path: List[Pt] | None = None    # along: logical displacement polyline (normalised to start)


def prim_bbox(pr) -> Tuple[float, float, float, float] | None:
    """Logical bounding box ``(minx, miny, maxx, maxy)`` of a single primitive (None if empty).

    Single source of truth for bounds, used by both ``Scene._bbox`` (to fit the viewBox) and
    ``mtph inspect`` / ``verify`` (for per-element bounds, overlap and out-of-bounds checks).
    """
    xs: List[float] = []
    ys: List[float] = []

    def inc(p: Pt):
        xs.append(p[0])
        ys.append(p[1])

    if isinstance(pr, Line):
        inc(pr.p1)
        inc(pr.p2)
    elif isinstance(pr, Path):
        for p in pr.points:
            inc(p)
    elif isinstance(pr, Circle):
        inc((pr.c[0] - pr.r, pr.c[1] - pr.r))
        inc((pr.c[0] + pr.r, pr.c[1] + pr.r))
    elif isinstance(pr, Ellipse):
        rr = max(pr.rx, pr.ry)
        inc((pr.c[0] - rr, pr.c[1] - rr))
        inc((pr.c[0] + rr, pr.c[1] + rr))
    elif isinstance(pr, BezPath):
        for _cmd, pts in pr.segments:
            for p in pts:
                inc(p)
    elif isinstance(pr, Text):
        size_l = pr.size / SCALE
        plain = sum(len(t) for t, _ in label_runs(pr.raw)) or 1
        half = 0.32 * size_l * plain
        cx = pr.pos[0] + pr.ox / SCALE
        cy = pr.pos[1] - pr.oy / SCALE
        if pr.anchor == "start":
            xs += [cx, cx + 2 * half]
        elif pr.anchor == "end":
            xs += [cx - 2 * half, cx]
        else:
            xs += [cx - half, cx + half]
        ys += [cy - size_l, cy + size_l]
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


class Scene:
    def __init__(self) -> None:
        self.prims: list = []
        self.anims: List[Anim] = []

    # add helpers -------------------------------------------------------------
    def line(self, p1, p2, **kw):
        self.prims.append(Line(p1, p2, **kw))

    def path(self, points, **kw):
        self.prims.append(Path(list(points), **kw))

    def circle(self, c, r, **kw):
        self.prims.append(Circle(c, r, **kw))

    def ellipse(self, c, rx, ry, **kw):
        self.prims.append(Ellipse(c, rx, ry, **kw))

    def bezier(self, segments, **kw):
        self.prims.append(BezPath(list(segments), **kw))

    def arc(self, c: Pt, r: float, a0: float, a1: float, *, width=W_NORMAL, stroke=INK):
        """Circular arc from angle a0 to a1 (degrees, ccw), sampled as a polyline."""
        steps = max(8, int(abs(a1 - a0) / 6))
        pts = []
        for i in range(steps + 1):
            ang = math.radians(a0 + (a1 - a0) * i / steps)
            pts.append((c[0] + r * math.cos(ang), c[1] + r * math.sin(ang)))
        self.prims.append(Path(pts, width=width, stroke=stroke, fill="none"))

    def text(self, pos, raw, **kw):
        self.prims.append(Text(pos, raw, **kw))

    def animate(self, anim: Anim) -> None:
        self.anims.append(anim)

    def group_bbox(self, start: int, end: int) -> Tuple[float, float, float, float] | None:
        """Logical bbox of the primitive run ``prims[start:end]`` (None if it drew nothing)."""
        xs: List[float] = []
        ys: List[float] = []
        for pr in self.prims[start:end]:
            bb = prim_bbox(pr)
            if bb:
                xs += [bb[0], bb[2]]
                ys += [bb[1], bb[3]]
        if not xs:
            return None
        return (min(xs), min(ys), max(xs), max(ys))

    def _anim_bbox(self, a: Anim) -> Tuple[float, float, float, float] | None:
        """The logical region an animation can sweep into, so the viewBox never clips it."""
        base = self.group_bbox(a.start, a.end)
        if not base:
            return None
        minx, miny, maxx, maxy = base
        if a.kind == "spin":
            cx, cy = a.center if a.center else ((minx + maxx) / 2, (miny + maxy) / 2)
            corners = [(minx, miny), (minx, maxy), (maxx, miny), (maxx, maxy)]
            if a.swing > 0:  # a swing sweeps only ±swing/2 — bound it by the two extremes
                hs = a.swing / 2
                xs: List[float] = []
                ys: List[float] = []
                for deg in (-hs, 0.0, hs):
                    for x, y in corners:
                        rx, ry = rot((x - cx, y - cy), deg)
                        xs.append(cx + rx)
                        ys.append(cy + ry)
                return (min(xs), min(ys), max(xs), max(ys))
            r = max(math.hypot(x - cx, y - cy) for x, y in corners)
            return (cx - r, cy - r, cx + r, cy + r)
        if a.kind == "oscillate":
            dx = a.amp * abs(math.cos(math.radians(a.direction)))
            dy = a.amp * abs(math.sin(math.radians(a.direction)))
            return (minx - dx, miny - dy, maxx + dx, maxy + dy)
        if a.kind == "along" and a.path:
            x0, y0 = a.path[0]
            offs = [(x - x0, y - y0) for x, y in a.path]
            lo_x = min(o[0] for o in offs)
            hi_x = max(o[0] for o in offs)
            lo_y = min(o[1] for o in offs)
            hi_y = max(o[1] for o in offs)
            return (minx + lo_x, miny + lo_y, maxx + hi_x, maxy + hi_y)
        return base

    def nudge_labels(self, iters: int = 25, margin: float = 0.05) -> int:
        """Push overlapping text labels apart (opt-in via ``mtph figure --nudge``). Mutates label
        positions in this scene only — never the source file. Returns how many labels moved."""
        texts = [pr for pr in self.prims if isinstance(pr, Text)]
        moved: set = set()
        for _ in range(iters):
            any_move = False
            for i in range(len(texts)):
                for j in range(i + 1, len(texts)):
                    a, b = texts[i], texts[j]
                    ba, bb = prim_bbox(a), prim_bbox(b)
                    if not ba or not bb:
                        continue
                    ix = min(ba[2], bb[2]) - max(ba[0], bb[0])
                    iy = min(ba[3], bb[3]) - max(ba[1], bb[1])
                    if ix <= margin or iy <= margin:
                        continue  # not overlapping
                    ca = ((ba[0] + ba[2]) / 2, (ba[1] + ba[3]) / 2)
                    cb = ((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2)
                    d = sub(cb, ca)
                    n = length(d)
                    push = (min(ix, iy) / 2 + margin)
                    # coincident centres give no direction — separate horizontally as a fallback
                    u = (d[0] / n, d[1] / n) if n > 1e-6 else (1.0, 0.0)
                    a.pos = (a.pos[0] - u[0] * push, a.pos[1] - u[1] * push)
                    b.pos = (b.pos[0] + u[0] * push, b.pos[1] + u[1] * push)
                    moved.add(id(a))
                    moved.add(id(b))
                    any_move = True
            if not any_move:
                break
        return len(moved)

    # bbox --------------------------------------------------------------------
    def _bbox(self) -> Tuple[float, float, float, float]:
        xs: List[float] = []
        ys: List[float] = []
        for pr in self.prims:
            bb = prim_bbox(pr)
            if bb:
                xs += [bb[0], bb[2]]
                ys += [bb[1], bb[3]]
        for a in self.anims:  # include the region each animation sweeps, so it never clips
            ab = self._anim_bbox(a)
            if ab:
                xs += [ab[0], ab[2]]
                ys += [ab[1], ab[3]]
        if not xs:
            return (0.0, 0.0, 1.0, 1.0)
        return (min(xs), min(ys), max(xs), max(ys))

    # emit --------------------------------------------------------------------
    def to_svg(self, title: str | None = None, grid: bool = False) -> str:
        minx, miny, maxx, maxy = self._bbox()
        w = (maxx - minx) * SCALE + 2 * PAD
        h = (maxy - miny) * SCALE + 2 * PAD
        w = max(w, 2 * PAD + 1)
        h = max(h, 2 * PAD + 1)

        def tx(x: float) -> float:
            return PAD + (x - minx) * SCALE

        def ty(y: float) -> float:
            return PAD + (maxy - y) * SCALE

        out: List[str] = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.1f} {h:.1f}" '
            f'width="{w:.0f}" height="{h:.0f}" font-family="Georgia, \'Times New Roman\', serif">'
        ]
        if title:
            out.append(f"<title>{_esc(title)}</title>")
        if any(isinstance(getattr(pr, "fill", None), str) and pr.fill.startswith("url(")
               for pr in self.prims):
            out.append(_PATTERN_DEFS)
        if grid:
            out.append(self._emit_grid(minx, miny, maxx, maxy, tx, ty))

        # Emit primitives in order; an animated run is wrapped in a <g> that carries its SMIL.
        anim_at = {a.start: a for a in self.anims if a.end > a.start}
        i = 0
        n = len(self.prims)
        while i < n:
            a = anim_at.get(i)
            if a:
                out.append("<g>")
                for j in range(a.start, a.end):
                    out.append(self._emit_prim(self.prims[j], tx, ty))
                out.append(self._emit_anim(a, tx, ty))
                out.append("</g>")
                i = a.end
            else:
                out.append(self._emit_prim(self.prims[i], tx, ty))
                i += 1
        out.append("</svg>")
        return "\n".join(out)

    def _emit_prim(self, pr, tx, ty) -> str:
        if isinstance(pr, Line):
            return self._emit_line(pr, tx, ty)
        if isinstance(pr, Path):
            return self._emit_path(pr, tx, ty)
        if isinstance(pr, Circle):
            return self._emit_circle(pr, tx, ty)
        if isinstance(pr, Ellipse):
            return self._emit_ellipse(pr, tx, ty)
        if isinstance(pr, BezPath):
            return self._emit_bezpath(pr, tx, ty)
        if isinstance(pr, Text):
            return self._emit_text(pr, tx, ty)
        return ""

    def _emit_anim(self, a: Anim, tx, ty) -> str:
        """The SMIL element for one animation (a child of the wrapping <g>)."""
        if a.kind == "spin":
            base = self.group_bbox(a.start, a.end)
            if a.center:
                cx, cy = a.center
            elif base:
                cx, cy = ((base[0] + base[2]) / 2, (base[1] + base[3]) / 2)
            else:
                cx, cy = (0.0, 0.0)
            px, py = tx(cx), ty(cy)
            if a.swing > 0:
                # Pendulum: oscillate the rotation ±swing/2 about the centre, resting at 0 (drawn
                # position). SVG +angle is clockwise, so a ccw-first swing is the negative extreme.
                hs = a.swing / 2
                vals = (
                    f"0 {_f2(px)} {_f2(py)};{_num(-hs)} {_f2(px)} {_f2(py)};"
                    f"0 {_f2(px)} {_f2(py)};{_num(hs)} {_f2(px)} {_f2(py)};0 {_f2(px)} {_f2(py)}"
                )
                ks = "0.42 0 0.58 1;0.42 0 0.58 1;0.42 0 0.58 1;0.42 0 0.58 1"
                return (
                    f'<animateTransform attributeName="transform" attributeType="XML" type="rotate" '
                    f'values="{vals}" keyTimes="0;0.25;0.5;0.75;1" calcMode="spline" '
                    f'keySplines="{ks}" dur="{_num(a.period)}s" repeatCount="indefinite"/>'
                )
            deg = 360 if a.cw else -360  # SVG +angle is clockwise (y is flipped), so ccw = -360
            return (
                f'<animateTransform attributeName="transform" attributeType="XML" type="rotate" '
                f'from="0 {_f2(px)} {_f2(py)}" to="{deg} {_f2(px)} {_f2(py)}" '
                f'dur="{_num(a.period)}s" repeatCount="indefinite"/>'
            )
        if a.kind == "oscillate":
            rad = math.radians(a.direction)
            ex = a.amp * SCALE * math.cos(rad)     # +x pixels at the extreme
            ey = -a.amp * SCALE * math.sin(rad)    # flip y for screen space
            # SHM as 5 keyframes with an ease-in-out spline (slow at the extremes, fast through
            # centre) — no per-sample trig, so the emitted bytes match the JS port exactly.
            vals = f"0 0;{_f2(ex)} {_f2(ey)};0 0;{_f2(-ex)} {_f2(-ey)};0 0"
            ks = "0.42 0 0.58 1;0.42 0 0.58 1;0.42 0 0.58 1;0.42 0 0.58 1"
            return (
                f'<animateTransform attributeName="transform" attributeType="XML" type="translate" '
                f'values="{vals}" keyTimes="0;0.25;0.5;0.75;1" calcMode="spline" '
                f'keySplines="{ks}" dur="{_num(a.period)}s" repeatCount="indefinite"/>'
            )
        if a.kind == "along" and a.path:
            x0, y0 = a.path[0]
            d = " ".join(
                "M 0 0" if k == 0 else f"L {_f2((x - x0) * SCALE)} {_f2(-(y - y0) * SCALE)}"
                for k, (x, y) in enumerate(a.path)
            )
            return (
                f'<animateMotion path="{d}" dur="{_num(a.period)}s" repeatCount="indefinite"/>'
            )
        return ""

    @staticmethod
    def _emit_grid(minx, miny, maxx, maxy, tx, ty) -> str:
        """A faint integer-coordinate grid with axis emphasis at 0 and edge tick labels."""
        parts = ['<g class="mtph-grid">']
        x_lo, x_hi = int(math.floor(minx)), int(math.ceil(maxx))
        y_lo, y_hi = int(math.floor(miny)), int(math.ceil(maxy))
        for gx in range(x_lo, x_hi + 1):
            x = tx(gx)
            stroke = "#d4d4d4" if gx == 0 else "#ededed"
            parts.append(f'<line x1="{x:.1f}" y1="{ty(maxy):.1f}" x2="{x:.1f}" '
                         f'y2="{ty(miny):.1f}" stroke="{stroke}" stroke-width="1"/>')
            parts.append(f'<text x="{x:.1f}" y="{ty(miny) + 11:.1f}" text-anchor="middle" '
                         f'font-size="9" fill="#b0b0b0">{gx}</text>')
        for gy in range(y_lo, y_hi + 1):
            y = ty(gy)
            stroke = "#d4d4d4" if gy == 0 else "#ededed"
            parts.append(f'<line x1="{tx(minx):.1f}" y1="{y:.1f}" x2="{tx(maxx):.1f}" '
                         f'y2="{y:.1f}" stroke="{stroke}" stroke-width="1"/>')
            parts.append(f'<text x="{tx(minx) - 4:.1f}" y="{y + 3:.1f}" text-anchor="end" '
                         f'font-size="9" fill="#b0b0b0">{gy}</text>')
        parts.append("</g>")
        return "".join(parts)

    # -- per-primitive emitters ----------------------------------------------
    @staticmethod
    def _dash(dash: str | None) -> str:
        if dash == "dashed":
            return ' stroke-dasharray="7 5"'
        if dash == "dotted":
            return ' stroke-dasharray="1.5 4"'
        return ""

    @staticmethod
    def _paper(fill: str) -> str:
        """Tag opaque white knock-out fills so the HTML can re-theme them in dark mode
        (the inline ``fill="#ffffff"`` stays the standalone/raster fallback)."""
        return ' class="mtph-pp"' if fill == PAPER else ""

    def _emit_line(self, pr: Line, tx, ty) -> str:
        a = (tx(pr.p1[0]), ty(pr.p1[1]))
        b = (tx(pr.p2[0]), ty(pr.p2[1]))
        frag = (
            f'<line x1="{a[0]:.2f}" y1="{a[1]:.2f}" x2="{b[0]:.2f}" y2="{b[1]:.2f}" '
            f'stroke="{pr.stroke}" stroke-width="{_num(pr.width)}" stroke-linecap="round"'
            f'{self._dash(pr.dash)}/>'
        )
        heads = ""
        if pr.arrow:
            heads += self._arrowhead(a, b, pr.stroke)
        if pr.arrow_start:
            heads += self._arrowhead(b, a, pr.stroke)
        return frag + heads

    @staticmethod
    def _arrowhead(a: Pt, b: Pt, stroke: str, size: float = 10.0) -> str:
        d = unit((b[0] - a[0], b[1] - a[1]))
        if d == (0.0, 0.0):
            return ""
        perp = (-d[1], d[0])
        base = (b[0] - d[0] * size, b[1] - d[1] * size)
        l = (base[0] + perp[0] * size * 0.42, base[1] + perp[1] * size * 0.42)
        r = (base[0] - perp[0] * size * 0.42, base[1] - perp[1] * size * 0.42)
        return (
            f'<polygon points="{b[0]:.2f},{b[1]:.2f} {l[0]:.2f},{l[1]:.2f} '
            f'{r[0]:.2f},{r[1]:.2f}" fill="{stroke}"/>'
        )

    def _emit_path(self, pr: Path, tx, ty) -> str:
        if not pr.points:
            return ""
        pts = " ".join(f"{tx(x):.2f},{ty(y):.2f}" for x, y in pr.points)
        if pr.closed:
            return (
                f'<polygon points="{pts}" fill="{pr.fill}"{self._paper(pr.fill)} '
                f'stroke="{pr.stroke}" stroke-width="{_num(pr.width)}" '
                f'stroke-linejoin="round"{self._dash(pr.dash)}/>'
            )
        return (
            f'<polyline points="{pts}" fill="{pr.fill}"{self._paper(pr.fill)} '
            f'stroke="{pr.stroke}" stroke-width="{_num(pr.width)}" stroke-linejoin="round" '
            f'stroke-linecap="round"{self._dash(pr.dash)}/>'
        )

    def _emit_circle(self, pr: Circle, tx, ty) -> str:
        return (
            f'<circle cx="{tx(pr.c[0]):.2f}" cy="{ty(pr.c[1]):.2f}" r="{pr.r * SCALE:.2f}" '
            f'fill="{pr.fill}"{self._paper(pr.fill)} stroke="{pr.stroke}" '
            f'stroke-width="{_num(pr.width)}"{self._dash(pr.dash)}/>'
        )

    def _emit_ellipse(self, pr: Ellipse, tx, ty) -> str:
        cx, cy = tx(pr.c[0]), ty(pr.c[1])
        # y is flipped on screen, so a ccw logical rotation is cw in SVG.
        rot = f' transform="rotate({-pr.angle:.2f} {cx:.2f} {cy:.2f})"' if pr.angle else ""
        return (
            f'<ellipse cx="{cx:.2f}" cy="{cy:.2f}" rx="{pr.rx * SCALE:.2f}" '
            f'ry="{pr.ry * SCALE:.2f}" fill="{pr.fill}"{self._paper(pr.fill)} '
            f'stroke="{pr.stroke}" stroke-width="{_num(pr.width)}"{self._dash(pr.dash)}{rot}/>'
        )

    def _emit_bezpath(self, pr: BezPath, tx, ty) -> str:
        if not pr.segments:
            return ""
        parts: List[str] = []
        pen: Pt | None = None       # current on-curve point (logical)
        ref: Pt | None = None       # point just before the end, for arrow direction
        for cmd, pts in pr.segments:
            scr = [(tx(x), ty(y)) for x, y in pts]
            if cmd in ("M", "L"):
                parts.append(f"{cmd} {scr[0][0]:.2f} {scr[0][1]:.2f}")
                ref, pen = pen, pts[0]
            elif cmd == "C":
                parts.append(
                    f"C {scr[0][0]:.2f} {scr[0][1]:.2f} {scr[1][0]:.2f} {scr[1][1]:.2f} "
                    f"{scr[2][0]:.2f} {scr[2][1]:.2f}"
                )
                ref, pen = pts[1], pts[2]
            elif cmd == "Q":
                parts.append(f"Q {scr[0][0]:.2f} {scr[0][1]:.2f} {scr[1][0]:.2f} {scr[1][1]:.2f}")
                ref, pen = pts[0], pts[1]
            elif cmd == "Z":
                parts.append("Z")
        frag = (
            f'<path d="{" ".join(parts)}" fill="{pr.fill}"{self._paper(pr.fill)} '
            f'stroke="{pr.stroke}" stroke-width="{_num(pr.width)}" stroke-linejoin="round" '
            f'stroke-linecap="round"{self._dash(pr.dash)}/>'
        )
        if pr.arrow and pen is not None and ref is not None:
            frag += self._arrowhead((tx(ref[0]), ty(ref[1])), (tx(pen[0]), ty(pen[1])), pr.stroke)
        return frag

    def _emit_text(self, pr: Text, tx, ty) -> str:
        x = tx(pr.pos[0]) + pr.ox
        y = ty(pr.pos[1]) + pr.oy
        inner = sub_sup_spans(label_runs(pr.raw), pr.size)
        baseline = {"middle": "central", "hanging": "hanging", "auto": "auto"}.get(
            pr.baseline, "central"
        )
        common = (
            f'x="{x:.2f}" y="{y:.2f}" text-anchor="{pr.anchor}" '
            f'dominant-baseline="{baseline}" font-size="{_num(pr.size)}" font-style="italic"'
        )
        # A paper-coloured halo keeps labels readable over busy backgrounds (field grids,
        # hatching, curves). Rather than ``paint-order="stroke"`` — which browsers honour but
        # cairosvg and many SVG tools silently ignore, painting the halo *over* the glyphs and
        # erasing them — draw the halo as a separate underlay text first, then the ink text on
        # top. That reads correctly in every renderer. The ``mtph-lbl`` class lets the HTML
        # re-theme the halo to the dark paper; the inline ``PAPER`` is the standalone/raster
        # fallback.
        halo = (
            f'<text class="mtph-lbl" {common} fill="{PAPER}" stroke="{PAPER}" '
            f'stroke-width="3.2" stroke-linejoin="round">{inner}</text>'
        )
        ink = f'<text {common} fill="{pr.fill}">{inner}</text>'
        return halo + ink
