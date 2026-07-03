"""Compile figure-DSL source into an SVG string.

The :class:`Compiler` interprets each statement, maintains a registry of named points and
objects (so ``incline.mid`` / ``m`` resolve to coordinates), and emits primitives into a
:class:`~mtph.diagram.shapes.Scene`.
"""
from __future__ import annotations

import math
import random
import re
from typing import Dict, List, Optional, Tuple

from . import shapes as S
from .dsl import DiagramSyntaxError, Statement, parse_dsl
from .shapes import Pt, Scene

_DEF_FORCE_MAG = 1.15
_GROUND_LEVEL = 0.0
_PATTERN_FILLS = {"hatch", "crosshatch", "dots"}


class Compiler:
    def __init__(self) -> None:
        self.scene = Scene()
        self.points: Dict[str, Pt] = {}
        self.objects: Dict[str, dict] = {}
        self.current_incline: Optional[dict] = None

    # -- value interpreters ---------------------------------------------------
    @staticmethod
    def _coord(tok: str, lineno: int) -> Pt:
        t = tok.strip()
        if not (t.startswith("(") and t.endswith(")")):
            raise DiagramSyntaxError(lineno, f"expected coordinate '(x, y)', got {tok!r}")
        parts = t[1:-1].split(",")
        if len(parts) != 2:
            raise DiagramSyntaxError(lineno, f"coordinate needs exactly two numbers: {tok!r}")
        try:
            return (float(parts[0]), float(parts[1]))
        except ValueError:
            raise DiagramSyntaxError(lineno, f"non-numeric coordinate {tok!r}")

    def resolve(self, tok: str, lineno: int) -> Pt:
        t = tok.strip()
        if t.startswith("("):
            return self._coord(t, lineno)
        if "." in t:
            name, part = t.split(".", 1)
            obj = self.objects.get(name)
            if not obj or part not in obj["anchors"]:
                raise DiagramSyntaxError(lineno, f"unknown anchor {tok!r}")
            return obj["anchors"][part]
        if t in self.points:
            return self.points[t]
        if t in self.objects and "center" in self.objects[t]["anchors"]:
            return self.objects[t]["anchors"]["center"]
        raise DiagramSyntaxError(lineno, f"unknown point/anchor {tok!r}")

    @staticmethod
    def _float(stmt: Statement, key: str, default: Optional[float] = None) -> float:
        if key not in stmt.args:
            if default is not None:
                return default
            raise DiagramSyntaxError(stmt.lineno, f"'{stmt.command}' needs '{key}='")
        try:
            return float(stmt.args[key])
        except ValueError:
            raise DiagramSyntaxError(stmt.lineno, f"'{key}=' must be a number")

    @staticmethod
    def _str(v: str) -> str:
        v = v.strip()
        if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
            return v[1:-1]
        return v

    def _require(self, stmt: Statement, key: str) -> str:
        if key not in stmt.args:
            raise DiagramSyntaxError(stmt.lineno, f"'{stmt.command}' needs '{key}='")
        return stmt.args[key]

    @staticmethod
    def _fill(stmt: Statement, default: str = "none") -> str:
        """Resolve a ``fill=`` value: a colour name, or a pattern (hatch/crosshatch/dots)."""
        v = stmt.args.get("fill", default)
        if v in _PATTERN_FILLS:
            return f"url(#mtph-{v})"
        return S.color(v)

    @staticmethod
    def _style(stmt: Statement) -> dict:
        kw: dict = {}
        # `style=` is canonical; `dash=` is accepted as an alias (it's the internal name and a
        # natural guess — silently ignoring it would render the wrong line style).
        dash = stmt.args.get("style", stmt.args.get("dash"))
        if dash is not None:
            kw["dash"] = dash if dash != "solid" else None
        if "width" in stmt.args:
            kw["width"] = float(stmt.args["width"])
        if "stroke" in stmt.args:
            kw["stroke"] = S.color(stmt.args["stroke"])
        return kw

    # -- compile loop ---------------------------------------------------------
    def execute(self, source: str) -> None:
        """Run the statements, populating the scene/points/objects (no SVG emitted)."""
        for stmt in parse_dsl(source):
            handler = getattr(self, f"_cmd_{_ALIASES.get(stmt.command, stmt.command)}", None)
            if handler is None:
                raise DiagramSyntaxError(stmt.lineno, f"unknown command {stmt.command!r}")
            start = len(self.scene.prims)
            handler(stmt)
            if "anim" in stmt.args:
                self._register_anim(stmt, start, len(self.scene.prims))

    # -- micro-animation (W5) -------------------------------------------------
    _ANIM_KINDS = ("spin", "oscillate", "along")

    def _register_anim(self, stmt: Statement, start: int, end: int) -> None:
        """Attach an ``anim=`` on a command to the primitives it just drew (``prims[start:end]``)."""
        kind = stmt.args["anim"]
        if kind not in self._ANIM_KINDS:
            raise DiagramSyntaxError(
                stmt.lineno, f"unknown anim {kind!r} (spin|oscillate|along)")
        if end <= start:
            return  # the command drew nothing to animate
        period = self._float(stmt, "anim-period", 2.0 if kind == "oscillate" else 3.0)
        if period <= 0:
            raise DiagramSyntaxError(stmt.lineno, "'anim-period=' must be positive")
        anim = S.Anim(kind=kind, start=start, end=end, period=period)
        if kind == "spin":
            if "anim-about" in stmt.args:
                anim.center = self.resolve(stmt.args["anim-about"], stmt.lineno)
            anim.cw = stmt.args.get("anim-cw", "false") != "false"
            anim.swing = self._float(stmt, "anim-swing", 0.0)
        elif kind == "oscillate":
            anim.amp = self._float(stmt, "anim-amp", 0.5)
            anim.direction = self._float(stmt, "anim-dir", 0.0)
        elif kind == "along":
            raw = self._str(self._require(stmt, "anim-path"))
            anim.path = [self._coord(p, stmt.lineno) for p in raw.split(";") if p.strip()]
            if len(anim.path) < 2:
                raise DiagramSyntaxError(stmt.lineno, "'anim-path=' needs at least two points")
        self.scene.animate(anim)

    def run(self, source: str) -> str:
        self.execute(source)
        return self.scene.to_svg()

    # -- primitive commands ---------------------------------------------------
    def _cmd_point(self, stmt: Statement) -> None:
        if not stmt.positionals:
            raise DiagramSyntaxError(stmt.lineno, "point needs a name, e.g. 'point P at=(1,2)'")
        name = stmt.positionals[0]
        at = self.resolve(self._require(stmt, "at"), stmt.lineno)
        self.points[name] = at
        if stmt.args.get("dot", "true") != "false":
            self.scene.circle(at, 0.055, fill=S.INK, stroke=S.INK, width=1)
        if "label" in stmt.args:
            self.scene.text(at, self._str(stmt.args["label"]), anchor="start", ox=9, oy=-9)

    def _cmd_line(self, stmt: Statement) -> None:
        a = self.resolve(self._require(stmt, "from"), stmt.lineno)
        b = self.resolve(self._require(stmt, "to"), stmt.lineno)
        self.scene.line(a, b, **self._style(stmt))
        if "label" in stmt.args:
            m = S.midpoint(a, b)
            self.scene.text(m, self._str(stmt.args["label"]), oy=-12)

    def _cmd_vector(self, stmt: Statement) -> None:
        a = self.resolve(self._require(stmt, "from"), stmt.lineno)
        b = self.resolve(self._require(stmt, "to"), stmt.lineno)
        kw = self._style(stmt)
        kw.setdefault("width", S.W_NORMAL)
        self.scene.line(a, b, arrow=True, **kw)
        if "label" in stmt.args:
            self._arrow_label(b, S.unit(S.sub(b, a)), self._str(stmt.args["label"]))

    def _cmd_current(self, stmt: Statement) -> None:
        """A labelled current arrow (distinct from a generic vector; defaults its label to I)."""
        a = self.resolve(self._require(stmt, "from"), stmt.lineno)
        b = self.resolve(self._require(stmt, "to"), stmt.lineno)
        kw = self._style(stmt)
        kw.setdefault("width", S.W_NORMAL)
        self.scene.line(a, b, arrow=True, **kw)
        label = self._str(stmt.args.get("label", "I"))
        self._arrow_label(b, S.unit(S.sub(b, a)), label)

    def _cmd_spiral(self, stmt: Statement) -> None:
        """Archimedean spiral: at=(x,y) r0= (start radius) dr= (radius gain per turn) turns= a0=deg."""
        c = self.resolve(self._require(stmt, "at"), stmt.lineno)
        r0 = self._float(stmt, "r0", 0.0)
        dr = self._float(stmt, "dr", 0.3)
        turns = self._float(stmt, "turns", 3.0)
        a0 = math.radians(self._float(stmt, "a0", 0.0))
        steps = max(16, int(abs(turns) * 48))
        pts: List[Pt] = []
        for i in range(steps + 1):
            frac = i / steps
            th = a0 + turns * 2 * math.pi * frac
            r = r0 + dr * turns * frac
            pts.append((c[0] + r * math.cos(th), c[1] + r * math.sin(th)))
        self.scene.path(pts, **self._style(stmt))
        if "label" in stmt.args:
            self.scene.text(pts[-1], self._str(stmt.args["label"]), anchor="start", ox=8)

    def _cmd_circle(self, stmt: Statement) -> None:
        c = self.resolve(self._require(stmt, "at"), stmt.lineno)
        r = self._float(stmt, "r")
        fill = self._fill(stmt)
        self.scene.circle(c, r, fill=fill, **self._style(stmt))
        if "label" in stmt.args:
            self.scene.text(c, self._str(stmt.args["label"]))

    def _cmd_rect(self, stmt: Statement) -> None:
        c = self.resolve(self._require(stmt, "at"), stmt.lineno)
        w = self._float(stmt, "w")
        h = self._float(stmt, "h")
        ang = self._float(stmt, "angle", 0.0)
        fill = self._fill(stmt)
        self.scene.path(self._rect_pts(c, w, h, ang), closed=True, fill=fill, **self._style(stmt))
        if "label" in stmt.args:
            self.scene.text(c, self._str(stmt.args["label"]))

    @staticmethod
    def _rect_pts(c: Pt, w: float, h: float, ang: float) -> List[Pt]:
        hw, hh = w / 2, h / 2
        local = [(-hw, hh), (hw, hh), (hw, -hh), (-hw, -hh)]
        return [S.add(c, S.rot(p, ang)) for p in local]

    def _cmd_polygon(self, stmt: Statement) -> None:
        raw = self._require(stmt, "points")
        pts = [self._coord(p, stmt.lineno) for p in raw.split(";") if p.strip()]
        closed = stmt.args.get("closed", "true") != "false"
        fill = self._fill(stmt)
        self.scene.path(pts, closed=closed, fill=fill, **self._style(stmt))

    def _cmd_path(self, stmt: Statement) -> None:
        """General freeform path: d="M(x,y) L(x,y) C(c1)(c2)(end) Q(c)(end) Z" — draw anything."""
        d = self._str(self._require(stmt, "d"))
        tokens = re.findall(r"[MLCQZ]|\([^)]*\)", d)
        need = {"M": 1, "L": 1, "C": 3, "Q": 2, "Z": 0}
        segments: List[Tuple[str, List[Pt]]] = []
        i = 0
        while i < len(tokens):
            cmd = tokens[i]
            if cmd not in need:
                raise DiagramSyntaxError(stmt.lineno, f"unexpected token {cmd!r} in path d=")
            n = need[cmd]
            pts: List[Pt] = []
            for j in range(n):
                if i + 1 + j >= len(tokens):
                    raise DiagramSyntaxError(stmt.lineno, f"path '{cmd}' needs {n} coordinate(s)")
                pts.append(self._coord(tokens[i + 1 + j], stmt.lineno))
            segments.append((cmd, pts))
            i += 1 + n
        if not segments:
            raise DiagramSyntaxError(stmt.lineno, 'path needs d="M(..) L(..) ..."')
        fill = self._fill(stmt)
        arrow = stmt.args.get("arrow", "false") == "true"
        self.scene.bezier(segments, fill=fill, arrow=arrow, **self._style(stmt))

    def _cmd_arc(self, stmt: Statement) -> None:
        c = self.resolve(self._require(stmt, "at"), stmt.lineno)
        r = self._float(stmt, "r")
        a0 = self._float(stmt, "from")
        a1 = self._float(stmt, "to")
        self.scene.arc(c, r, a0, a1, **{k: v for k, v in self._style(stmt).items() if k != "dash"})

    def _cmd_label(self, stmt: Statement) -> None:
        at = self.resolve(self._require(stmt, "at"), stmt.lineno)
        text = self._str(self._require(stmt, "text"))
        anchor, baseline, ox, oy = _anchor_kw(stmt.args.get("anchor", "center"))
        dx = float(stmt.args.get("dx", 0.0))
        dy = float(stmt.args.get("dy", 0.0))
        self.scene.text((at[0] + dx, at[1] + dy), text, anchor=anchor, baseline=baseline, ox=ox, oy=oy)

    def _cmd_angle(self, stmt: Statement) -> None:
        if "between" in stmt.args:
            names = [s.strip() for s in stmt.args["between"].split(",")]
            if len(names) != 3:
                raise DiagramSyntaxError(stmt.lineno, "angle between= needs three anchors A,B,C")
            a = self.resolve(names[0], stmt.lineno)
            v = self.resolve(names[1], stmt.lineno)
            c = self.resolve(names[2], stmt.lineno)
            a0 = math.degrees(math.atan2(a[1] - v[1], a[0] - v[0]))
            a1 = math.degrees(math.atan2(c[1] - v[1], c[0] - v[0]))
            vertex = v
        else:
            vertex = self.resolve(self._require(stmt, "at"), stmt.lineno)
            a0 = self._float(stmt, "from")
            a1 = self._float(stmt, "to")
        r = self._float(stmt, "r", 0.7)
        self.scene.arc(vertex, r, a0, a1, width=S.W_THIN)
        if "value" in stmt.args:
            mid = math.radians((a0 + a1) / 2)
            lp = (vertex[0] + (r + 0.28) * math.cos(mid), vertex[1] + (r + 0.28) * math.sin(mid))
            self.scene.text(lp, self._str(stmt.args["value"]))

    # -- fields, charges & E&M -----------------------------------------------
    def _draw_charge(self, at: Pt, sign: str, r: float) -> None:
        self.scene.circle(at, r, fill=S.PAPER, width=S.W_NORMAL)
        glyph = "+" if sign.startswith("+") or sign in ("plus", "pos", "positive") else "−"
        self.scene.text(at, glyph, size=S.FONT + 3)

    def _cmd_charge(self, stmt: Statement) -> None:
        at = self.resolve(self._require(stmt, "at"), stmt.lineno)
        r = self._float(stmt, "r", 0.26)
        self._draw_charge(at, stmt.args.get("sign", "+"), r)
        if stmt.positionals:
            self.points[stmt.positionals[0]] = at
        if "label" in stmt.args:
            # clear the sign glyph (which extends beyond r) so the label doesn't self-overlap it
            self.scene.text(at, self._str(stmt.args["label"]), oy=-(r * S.SCALE + 26))

    def _cmd_dipole(self, stmt: Statement) -> None:
        at = self.resolve(stmt.args["at"], stmt.lineno) if "at" in stmt.args else (0.0, 0.0)
        sep = self._float(stmt, "sep", 1.2)
        ang = self._float(stmt, "angle", 0.0)
        r = self._float(stmt, "r", 0.24)
        d = S.rot((1.0, 0.0), ang)
        pos = S.add(at, S.mul(d, sep / 2))
        neg = S.sub(at, S.mul(d, sep / 2))
        if stmt.args.get("moment", "false") == "true":
            self.scene.line(neg, pos, arrow=True, width=S.W_THIN)
        self._draw_charge(neg, "-", r)
        self._draw_charge(pos, "+", r)
        if "label" in stmt.args:
            self.scene.text(at, self._str(stmt.args["label"]), oy=-(sep / 2 * S.SCALE + 16))

    def _cmd_bfield(self, stmt: Statement) -> None:
        at = self.resolve(stmt.args["at"], stmt.lineno) if "at" in stmt.args else (0.0, 0.0)
        w = self._float(stmt, "width", 2.0)
        h = self._float(stmt, "height", 2.0)
        n = max(2, int(self._float(stmt, "n", 4)))
        out = stmt.args.get("dir", "out").startswith("o")
        for i in range(n):
            for j in range(n):
                x = at[0] + (i + 0.5) * w / n
                y = at[1] + (j + 0.5) * h / n
                self.scene.circle((x, y), 0.085, width=S.W_THIN)
                if out:
                    self.scene.circle((x, y), 0.022, fill=S.INK, width=S.W_THIN)
                else:
                    dd = 0.06
                    self.scene.line((x - dd, y - dd), (x + dd, y + dd), width=S.W_THIN)
                    self.scene.line((x - dd, y + dd), (x + dd, y - dd), width=S.W_THIN)
        if "label" in stmt.args:
            self.scene.text((at[0] + w / 2, at[1] + h), self._str(stmt.args["label"]), oy=-10)

    def _cmd_fieldline(self, stmt: Statement) -> None:
        a = self.resolve(self._require(stmt, "from"), stmt.lineno)
        b = self.resolve(self._require(stmt, "to"), stmt.lineno)
        bend = self._float(stmt, "bend", 0.0)
        d = S.unit(S.sub(b, a))
        p = (-d[1], d[0])
        ctrl = S.add(S.midpoint(a, b), S.mul(p, bend * S.length(S.sub(b, a))))
        arrow = stmt.args.get("arrow", "true") != "false"
        self.scene.bezier([("M", [a]), ("Q", [ctrl, b])], arrow=arrow, **self._style(stmt))

    def _cmd_vectorfield(self, stmt: Statement) -> None:
        at = self.resolve(stmt.args["at"], stmt.lineno) if "at" in stmt.args else (0.0, 0.0)
        w = self._float(stmt, "width", 3.0)
        h = self._float(stmt, "height", 3.0)
        n = max(2, int(self._float(stmt, "n", 5)))
        direction = stmt.args.get("dir", "0")
        L = min(w, h) / n * 0.62
        cx, cy = at[0] + w / 2, at[1] + h / 2
        for i in range(n):
            for j in range(n):
                x = at[0] + (i + 0.5) * w / n
                y = at[1] + (j + 0.5) * h / n
                if direction in ("out", "radial"):
                    dvec = S.unit((x - cx, y - cy))
                elif direction == "in":
                    dvec = S.unit((cx - x, cy - y))
                else:
                    dvec = S.rot((1.0, 0.0), float(direction))
                if dvec == (0.0, 0.0):
                    continue
                self.scene.line((x, y), S.add((x, y), S.mul(dvec, L)),
                                arrow=True, width=S.W_THIN)

    def _cmd_equipotential(self, stmt: Statement) -> None:
        c = self.resolve(self._require(stmt, "at"), stmt.lineno)
        r = self._float(stmt, "r")
        self.scene.circle(c, r, dash="dashed", width=S.W_THIN, stroke="#888888")

    def _cmd_gaussian(self, stmt: Statement) -> None:
        c = self.resolve(self._require(stmt, "at"), stmt.lineno)
        r = self._float(stmt, "r")
        self.scene.circle(c, r, dash="dashed", width=S.W_THIN)
        if "label" in stmt.args:
            self.scene.text(c, self._str(stmt.args["label"]), oy=-(r * S.SCALE + 10))

    # -- physics / geometry helpers ------------------------------------------
    def _cmd_incline(self, stmt: Statement) -> None:
        ang = self._float(stmt, "angle")
        L = self._float(stmt, "length")
        base = self.resolve(stmt.args["at"], stmt.lineno) if "at" in stmt.args else (0.0, 0.0)
        rad = math.radians(ang)
        foot = (base[0] + L * math.cos(rad), base[1])
        top = (foot[0], base[1] + L * math.sin(rad))
        u = S.unit(S.sub(top, base))           # up the ramp
        n = S.rot(u, 90)                        # outward normal
        self.scene.path([base, foot, top], closed=True, width=S.W_NORMAL)
        self._ground((base[0] - 0.5, base[1]), foot[0] + 0.4)
        obj = {
            "anchors": {"base": base, "foot": foot, "top": top, "mid": S.midpoint(base, top)},
            "u": u, "n": n, "angle": ang,
        }
        self.objects["incline"] = obj
        self.current_incline = obj

    def _cmd_mass(self, stmt: Statement) -> None:
        if not stmt.positionals:
            raise DiagramSyntaxError(stmt.lineno, "mass needs a name, e.g. 'mass m at=...'")
        name = stmt.positionals[0]
        at_tok = self._require(stmt, "at")
        base_pt = self.resolve(at_tok, stmt.lineno)
        size = self._float(stmt, "size", 0.8)
        on_incline = at_tok.startswith("incline") and self.current_incline is not None
        if on_incline:
            inc = self.current_incline
            u, n = inc["u"], inc["n"]
            ang = inc["angle"]
            center = S.add(base_pt, S.mul(n, size / 2))
        else:
            u, n = (1.0, 0.0), (0.0, 1.0)
            ang = self._float(stmt, "angle", 0.0)
            center = base_pt
        self.scene.path(self._rect_pts(center, size, size, ang), closed=True, fill=S.PAPER)
        self.points[name] = center
        self.objects[name] = {"anchors": {"center": center}, "u": u, "n": n}
        if "label" in stmt.args:
            # Nudge the label toward a corner (up-slope) so it clears force arrows that
            # originate from the block's centre.
            self.scene.text(center, self._str(stmt.args["label"]), ox=u[0] * 14, oy=-u[1] * 14)

    def _frame_for(self, anchor_tok: str) -> Tuple[Pt, Pt]:
        name = anchor_tok.split(".")[0]
        obj = self.objects.get(name)
        if obj and "u" in obj:
            return obj["u"], obj["n"]
        if self.current_incline:
            return self.current_incline["u"], self.current_incline["n"]
        return (1.0, 0.0), (0.0, 1.0)

    def _cmd_force(self, stmt: Statement) -> None:
        from_tok = self._require(stmt, "from")
        base = self.resolve(from_tok, stmt.lineno)
        u, n = self._frame_for(from_tok)
        d = self._require(stmt, "dir")
        mag = self._float(stmt, "mag", _DEF_FORCE_MAG)
        dirs = {
            "down": (0.0, -1.0), "up": (0.0, 1.0), "left": (-1.0, 0.0), "right": (1.0, 0.0),
            "perp-out": n, "perp-in": S.mul(n, -1), "along": u, "along-up": u,
            "along-down": S.mul(u, -1),
        }
        if d in dirs:
            dvec = dirs[d]
        else:
            try:
                dvec = S.rot((1.0, 0.0), float(d))
            except ValueError:
                raise DiagramSyntaxError(stmt.lineno, f"bad force dir {d!r}")
        tip = S.add(base, S.mul(S.unit(dvec), mag))
        self.scene.line(base, tip, arrow=True, width=S.W_THICK)
        if "label" in stmt.args:
            self._arrow_label(tip, S.unit(dvec), self._str(stmt.args["label"]))

    def _cmd_spring(self, stmt: Statement) -> None:
        a = self.resolve(self._require(stmt, "from"), stmt.lineno)
        b = self.resolve(self._require(stmt, "to"), stmt.lineno)
        coils = int(self._float(stmt, "coils", 6))
        self.scene.path(_zigzag(a, b, coils, amp=0.13), width=S.W_THIN)
        if "label" in stmt.args:
            self.scene.text(S.midpoint(a, b), self._str(stmt.args["label"]), oy=-14)

    def _cmd_zigzag(self, stmt: Statement) -> None:
        """A zigzag line (cutaway / boundary / sawtooth indicator). `amplitude=` sets the tooth
        height, `periods=` the number of teeth — distinct from `spring` (which is a coil)."""
        a = self.resolve(self._require(stmt, "from"), stmt.lineno)
        b = self.resolve(self._require(stmt, "to"), stmt.lineno)
        amp = self._float(stmt, "amplitude", 0.18)
        periods = max(1, int(self._float(stmt, "periods", 6)))
        self.scene.path(_zigzag(a, b, periods, amp=amp), **self._style(stmt))
        if "label" in stmt.args:
            self.scene.text(S.midpoint(a, b), self._str(stmt.args["label"]), oy=-14)

    def _cmd_pulley(self, stmt: Statement) -> None:
        c = self.resolve(self._require(stmt, "at"), stmt.lineno)
        r = self._float(stmt, "r", 0.35)
        self.scene.circle(c, r)
        self.scene.circle(c, 0.04, fill=S.INK)

    def _cmd_ground(self, stmt: Statement) -> None:
        at = self.resolve(self._require(stmt, "at"), stmt.lineno)
        width = self._float(stmt, "width", 3.0)
        self._ground(at, at[0] + width)

    def _ground(self, left: Pt, right_x: float) -> None:
        y = left[1]
        self.scene.line((left[0], y), (right_x, y), width=S.W_NORMAL)
        x = left[0]
        step = 0.32
        while x < right_x:
            self.scene.line((x, y), (x - 0.22, y - 0.22), width=S.W_THIN)
            x += step

    def _cmd_wall(self, stmt: Statement) -> None:
        at = self.resolve(stmt.args["at"], stmt.lineno) if "at" in stmt.args else (0.0, 0.0)
        h = self._float(stmt, "height", 3.0)
        sgn = -1.0 if stmt.args.get("side", "left") == "left" else 1.0
        self.scene.line(at, (at[0], at[1] + h), width=S.W_NORMAL)
        y = at[1]
        while y < at[1] + h:
            self.scene.line((at[0], y), (at[0] + sgn * 0.22, y + 0.22), width=S.W_THIN)
            y += 0.32

    def _cmd_dim(self, stmt: Statement) -> None:
        """Dimension line between two anchors, offset perpendicular, with a centred label."""
        a = self.resolve(self._require(stmt, "from"), stmt.lineno)
        b = self.resolve(self._require(stmt, "to"), stmt.lineno)
        off = self._float(stmt, "off", -0.6)
        d = S.unit(S.sub(b, a))
        p = (-d[1], d[0])
        a2 = S.add(a, S.mul(p, off))
        b2 = S.add(b, S.mul(p, off))
        self.scene.line(a, a2, width=S.W_THIN, stroke="#888888")
        self.scene.line(b, b2, width=S.W_THIN, stroke="#888888")
        self.scene.line(a2, b2, width=S.W_THIN, arrow=True, arrow_start=True)
        if "label" in stmt.args:
            sign = -1.0 if off < 0 else 1.0
            self.scene.text(
                S.midpoint(a2, b2), self._str(stmt.args["label"]),
                ox=p[0] * 14 * sign, oy=-p[1] * 14 * sign,
            )

    def _cmd_axis(self, stmt: Statement) -> None:
        origin = self.resolve(stmt.args["origin"], stmt.lineno) if "origin" in stmt.args else (0.0, 0.0)
        xr = _range(stmt.args.get("x", "-3..3"), stmt.lineno)
        yr = _range(stmt.args.get("y", "-3..3"), stmt.lineno)
        self.scene.line((origin[0] + xr[0], origin[1]), (origin[0] + xr[1], origin[1]),
                        width=S.W_THIN, arrow=True, arrow_start=True)
        self.scene.line((origin[0], origin[1] + yr[0]), (origin[0], origin[1] + yr[1]),
                        width=S.W_THIN, arrow=True, arrow_start=True)
        if stmt.args.get("labels", "true") != "false":
            self.scene.text((origin[0] + xr[1], origin[1]), "x", anchor="start", ox=10, oy=12)
            self.scene.text((origin[0], origin[1] + yr[1]), "y", anchor="start", ox=10, oy=-6)

    # -- mechanics, 3D & frames ----------------------------------------------
    def _cmd_pendulum(self, stmt: Statement) -> None:
        pivot = self.resolve(self._require(stmt, "at"), stmt.lineno)
        L = self._float(stmt, "length", 2.0)
        ang = self._float(stmt, "angle", 20.0)  # from the downward vertical, + tilts toward +x
        bob = self._float(stmt, "bob", 0.3)
        rad = math.radians(ang)
        bobc = (pivot[0] + L * math.sin(rad), pivot[1] - L * math.cos(rad))
        self.scene.line(pivot, (pivot[0], pivot[1] - L), dash="dashed", width=S.W_THIN, stroke="#888888")
        self.scene.line(pivot, bobc, width=S.W_NORMAL)
        self.scene.circle(pivot, 0.05, fill=S.INK)
        self.scene.circle(bobc, bob, fill=S.PAPER)
        if abs(ang) > 0.5:
            a_rod = math.degrees(math.atan2(bobc[1] - pivot[1], bobc[0] - pivot[0]))
            self.scene.arc(pivot, L * 0.32, min(-90.0, a_rod), max(-90.0, a_rod), width=S.W_THIN)
            if "value" in stmt.args:
                mid = math.radians((-90.0 + a_rod) / 2)
                lp = (pivot[0] + (L * 0.32 + 0.25) * math.cos(mid),
                      pivot[1] + (L * 0.32 + 0.25) * math.sin(mid))
                self.scene.text(lp, self._str(stmt.args["value"]))
        if stmt.positionals:
            self.points[stmt.positionals[0]] = bobc
            self.objects[stmt.positionals[0]] = {"anchors": {"center": bobc}, "u": (1.0, 0.0), "n": (0.0, 1.0)}
        if "label" in stmt.args:
            self.scene.text(bobc, self._str(stmt.args["label"]))

    def _cmd_rod(self, stmt: Statement) -> None:
        a = self.resolve(self._require(stmt, "from"), stmt.lineno)
        b = self.resolve(self._require(stmt, "to"), stmt.lineno)
        self.scene.line(a, b, width=float(stmt.args.get("width", S.W_THICK)))
        if "label" in stmt.args:
            self.scene.text(S.midpoint(a, b), self._str(stmt.args["label"]), oy=-12)

    def _cmd_pivot(self, stmt: Statement) -> None:
        c = self.resolve(self._require(stmt, "at"), stmt.lineno)
        s = self._float(stmt, "size", 0.3)
        self.scene.path([(c[0] - s, c[1] - s), c, (c[0] + s, c[1] - s)], closed=True, fill=S.PAPER)
        self._ground((c[0] - s - 0.15, c[1] - s), c[0] + s + 0.15)
        self.scene.circle(c, 0.05, fill=S.INK)
        if "label" in stmt.args:
            self.scene.text(c, self._str(stmt.args["label"]), anchor="start", ox=10)

    def _cmd_axes3d(self, stmt: Statement) -> None:
        o = self.resolve(stmt.args["at"], stmt.lineno) if "at" in stmt.args else (0.0, 0.0)
        s = self._float(stmt, "size", 2.4)
        zdir = S.unit((-0.7, -0.5))
        self.scene.line(o, (o[0] + s, o[1]), arrow=True, width=S.W_THIN)
        self.scene.line(o, (o[0], o[1] + s), arrow=True, width=S.W_THIN)
        self.scene.line(o, S.add(o, S.mul(zdir, s * 0.75)), arrow=True, width=S.W_THIN)
        if stmt.args.get("labels", "true") != "false":
            self.scene.text((o[0] + s, o[1]), "x", anchor="start", ox=8, oy=10)
            self.scene.text((o[0], o[1] + s), "y", anchor="start", ox=8, oy=-6)
            zt = S.add(o, S.mul(zdir, s * 0.75))
            self.scene.text(zt, "z", anchor="end", ox=-8, oy=6)

    def _cmd_sphere(self, stmt: Statement) -> None:
        c = self.resolve(self._require(stmt, "at"), stmt.lineno)
        r = self._float(stmt, "r", 1.0)
        self.scene.circle(c, r)
        self.scene.ellipse(c, r, r * 0.32, width=S.W_THIN)  # equator for a 3D feel
        if "label" in stmt.args:
            self.scene.text(c, self._str(stmt.args["label"]), oy=-(r * S.SCALE + 10))

    def _cmd_omega(self, stmt: Statement) -> None:
        c = self.resolve(stmt.args["at"], stmt.lineno) if "at" in stmt.args else (0.0, 0.0)
        r = self._float(stmt, "r", 0.6)
        ccw = stmt.args.get("dir", "ccw") != "cw"
        a0, a1 = (35.0, 320.0) if ccw else (320.0, 35.0)
        steps = 26
        pts = [(c[0] + r * math.cos(math.radians(a0 + (a1 - a0) * k / steps)),
                c[1] + r * math.sin(math.radians(a0 + (a1 - a0) * k / steps))) for k in range(steps + 1)]
        self.scene.path(pts, width=S.W_NORMAL)
        self.scene.line(pts[-2], pts[-1], arrow=True, width=S.W_NORMAL)
        label = self._str(stmt.args["label"]) if "label" in stmt.args else "\\omega"
        self.scene.text(c, label)

    # -- circuit --------------------------------------------------------------
    def _cmd_wire(self, stmt: Statement) -> None:
        a = self.resolve(self._require(stmt, "from"), stmt.lineno)
        b = self.resolve(self._require(stmt, "to"), stmt.lineno)
        self.scene.line(a, b, width=S.W_NORMAL)

    def _cmd_resistor(self, stmt: Statement) -> None:
        a = self.resolve(self._require(stmt, "from"), stmt.lineno)
        b = self.resolve(self._require(stmt, "to"), stmt.lineno)
        d = S.unit(S.sub(b, a))
        lead = 0.22
        a2 = S.add(a, S.mul(d, lead))
        b2 = S.sub(b, S.mul(d, lead))
        self.scene.line(a, a2, width=S.W_NORMAL)
        self.scene.line(b2, b, width=S.W_NORMAL)
        self.scene.path(_zigzag(a2, b2, 6, amp=0.16), width=S.W_NORMAL)
        if "label" in stmt.args:
            self._component_label(a, b, self._str(stmt.args["label"]))

    def _cmd_battery(self, stmt: Statement) -> None:
        a = self.resolve(self._require(stmt, "from"), stmt.lineno)
        b = self.resolve(self._require(stmt, "to"), stmt.lineno)
        d = S.unit(S.sub(b, a))
        p = (-d[1], d[0])
        mid = S.midpoint(a, b)
        long_p, short_p = mid, S.add(mid, S.mul(d, 0.16))
        self.scene.line(a, S.sub(long_p, S.mul(d, 0.0)), width=S.W_NORMAL)
        self.scene.line(short_p, b, width=S.W_NORMAL)
        self.scene.line(S.add(long_p, S.mul(p, 0.32)), S.sub(long_p, S.mul(p, 0.32)), width=S.W_NORMAL)
        self.scene.line(S.add(short_p, S.mul(p, 0.18)), S.sub(short_p, S.mul(p, 0.18)), width=S.W_THICK)
        if "label" in stmt.args:
            self._component_label(a, b, self._str(stmt.args["label"]))

    # -- optics (light) -------------------------------------------------------
    def _cmd_lens(self, stmt: Statement) -> None:
        c = self.resolve(self._require(stmt, "at"), stmt.lineno)
        h = self._float(stmt, "height", 2.0)
        kind = stmt.args.get("type", "convex")
        top, bot = (c[0], c[1] + h / 2), (c[0], c[1] - h / 2)
        self.scene.line(top, bot, width=S.W_NORMAL)
        out = 1 if kind == "convex" else -1
        for end in (top, bot):
            sgn = 1 if end is top else -1
            tip = (end[0], end[1] + sgn * 0.18 * out)
            self.scene.line((end[0], end[1] - sgn * 0.18 * out), tip, arrow=True, width=S.W_THIN)

    def _cmd_ray(self, stmt: Statement) -> None:
        a = self.resolve(self._require(stmt, "from"), stmt.lineno)
        b = self.resolve(self._require(stmt, "to"), stmt.lineno)
        arrow = stmt.args.get("arrow", "true") != "false"
        self.scene.line(a, b, arrow=arrow, width=S.W_THIN)

    # -- thermo, fluids & waves ----------------------------------------------
    def _cmd_container(self, stmt: Statement) -> None:
        at = self.resolve(self._require(stmt, "at"), stmt.lineno)  # bottom-left
        w = self._float(stmt, "width", 2.0)
        h = self._float(stmt, "height", 2.0)
        if stmt.args.get("fill", "none") != "none":
            level = self._float(stmt, "level", h * 0.6)
            self.scene.path(
                [at, (at[0] + w, at[1]), (at[0] + w, at[1] + level), (at[0], at[1] + level)],
                closed=True, fill=S.color(stmt.args["fill"]),
            )
        self.scene.path(
            [(at[0], at[1] + h), at, (at[0] + w, at[1]), (at[0] + w, at[1] + h)],
            width=S.W_NORMAL,
        )
        if "label" in stmt.args:
            self.scene.text((at[0] + w / 2, at[1] + h / 2), self._str(stmt.args["label"]))

    def _cmd_piston(self, stmt: Statement) -> None:
        at = self.resolve(self._require(stmt, "at"), stmt.lineno)  # centre of plate
        w = self._float(stmt, "width", 1.8)
        th = self._float(stmt, "thickness", 0.22)
        rod = self._float(stmt, "rod", 1.0)
        self.scene.path(self._rect_pts(at, w, th, 0.0), closed=True, fill="#cccccc")
        self.scene.line((at[0], at[1] + th / 2), (at[0], at[1] + th / 2 + rod), width=S.W_THICK)
        if "label" in stmt.args:
            self.scene.text((at[0], at[1] + th / 2 + rod), self._str(stmt.args["label"]), oy=-12)

    def _cmd_gas(self, stmt: Statement) -> None:
        at = self.resolve(self._require(stmt, "at"), stmt.lineno)  # bottom-left
        w = self._float(stmt, "width", 2.0)
        h = self._float(stmt, "height", 2.0)
        n = max(1, int(self._float(stmt, "n", 14)))
        rng = random.Random(int(self._float(stmt, "seed", 0)))
        m = 0.12
        for _ in range(n):
            x = at[0] + m + rng.random() * (w - 2 * m)
            y = at[1] + m + rng.random() * (h - 2 * m)
            self.scene.circle((x, y), 0.06, fill=S.INK, width=S.W_THIN)

    def _cmd_heat(self, stmt: Statement) -> None:
        at = self.resolve(self._require(stmt, "at"), stmt.lineno)  # baseline left
        w = self._float(stmt, "width", 2.0)
        n = max(1, int(self._float(stmt, "n", 3)))
        H = self._float(stmt, "height", 0.9)
        a = 0.12
        for k in range(n):
            x = at[0] + (k + 0.5) * w / n
            y = at[1]
            seg = [
                ("M", [(x, y)]),
                ("C", [(x + a, y + H * 0.33), (x - a, y + H * 0.5), (x, y + H * 0.66)]),
                ("Q", [(x + a, y + H * 0.86), (x, y + H)]),
            ]
            self.scene.bezier(seg, arrow=True, width=S.W_THIN)

    def _cmd_flame(self, stmt: Statement) -> None:
        at = self.resolve(self._require(stmt, "at"), stmt.lineno)
        s = self._float(stmt, "size", 0.6)
        x, y = at
        seg = [
            ("M", [(x, y + s * 1.7)]),
            ("C", [(x + s * 0.75, y + s * 0.9), (x + s * 0.55, y), (x, y)]),
            ("C", [(x - s * 0.55, y), (x - s * 0.75, y + s * 0.9), (x, y + s * 1.7)]),
            ("Z", []),
        ]
        self.scene.bezier(seg, width=S.W_NORMAL)

    def _cmd_wavefront(self, stmt: Statement) -> None:
        c = self.resolve(self._require(stmt, "at"), stmt.lineno)
        n = max(1, int(self._float(stmt, "n", 4)))
        r0 = self._float(stmt, "r0", 0.5)
        dr = self._float(stmt, "dr", 0.5)
        if "from" in stmt.args and "to" in stmt.args:
            f, t = self._float(stmt, "from"), self._float(stmt, "to")
            for k in range(n):
                self.scene.arc(c, r0 + k * dr, f, t, width=S.W_THIN)
        else:
            for k in range(n):
                self.scene.circle(c, r0 + k * dr, width=S.W_THIN)
        self.scene.circle(c, 0.05, fill=S.INK)

    # -- shared label placement ----------------------------------------------
    def _arrow_label(self, tip: Pt, d: Pt, text: str) -> None:
        ox = d[0] * 16
        oy = -d[1] * 16
        anchor = "start" if d[0] > 0.3 else "end" if d[0] < -0.3 else "middle"
        self.scene.text(tip, text, anchor=anchor, ox=ox, oy=oy)

    def _component_label(self, a: Pt, b: Pt, text: str) -> None:
        """Place a label beside a 2-terminal component, offset perpendicular to it."""
        d = S.unit(S.sub(b, a))
        p = (-d[1], d[0])
        if p[1] < 0:  # prefer the upper / left side
            p = (-p[0], -p[1])
        ox, oy = p[0] * 20, -p[1] * 20
        anchor = "start" if p[0] > 0.4 else "end" if p[0] < -0.4 else "middle"
        self.scene.text(S.midpoint(a, b), text, anchor=anchor, ox=ox, oy=oy)


_ALIASES = {
    "segment": "line", "arrow": "vector", "block": "mass", "text": "label",
    "hinge": "pivot", "rope": "line", "string": "line", "streamline": "fieldline",
    "coil": "spiral", "helix": "spiral",
}


def _anchor_kw(kw: str):
    return {
        "center": ("middle", "central", 0, 0),
        "left": ("end", "central", -8, 0),
        "right": ("start", "central", 8, 0),
        "above": ("middle", "auto", 0, -10),
        "below": ("middle", "hanging", 0, 10),
    }.get(kw, ("middle", "central", 0, 0))


def _range(s: str, lineno: int) -> Tuple[float, float]:
    if ".." not in s:
        raise DiagramSyntaxError(lineno, f"expected range 'a..b', got {s!r}")
    a, b = s.split("..", 1)
    return (float(a), float(b))


def _zigzag(a: Pt, b: Pt, teeth: int, amp: float) -> List[Pt]:
    d = S.unit(S.sub(b, a))
    p = (-d[1], d[0])
    total = S.length(S.sub(b, a))
    lead = total * 0.16
    start = S.add(a, S.mul(d, lead))
    end = S.sub(b, S.mul(d, lead))
    span = S.length(S.sub(end, start))
    pts = [a, start]
    for i in range(1, 2 * teeth):
        t = i / (2 * teeth)
        base = S.add(start, S.mul(d, span * t))
        sign = 1 if i % 2 == 1 else -1
        pts.append(S.add(base, S.mul(p, amp * sign)))
    pts += [end, b]
    return pts


def _compile_single(source: str, title: str | None = None, grid: bool = False,
                    nudge: bool = False) -> str:
    compiler = Compiler()
    compiler.execute(source)
    if nudge:
        compiler.scene.nudge_labels()
    return compiler.scene.to_svg(title=title, grid=grid)


# -- multi-panel figures ------------------------------------------------------
# A figure may hold several independent sub-scenes ("before/after", "two cases", insets),
# separated by a line of `---` and arranged by a leading `layout` directive. Each panel
# auto-fits on its own; the panels are placed as nested <svg> viewports in one outer SVG.
_PANEL_SEP = re.compile(r"^\s*-{3,}\s*$")
_LAYOUT_RE = re.compile(r"^\s*layout\s*[:=]?\s*(row|horizontal|column|col|vertical|grid)\b(.*)$", re.I)
_COLS_RE = re.compile(r"\bcols\s*[:=]?\s*(\d+)")
_LAYOUT_ALIASES = {"horizontal": "row", "row": "row",
                   "col": "column", "vertical": "column", "column": "column", "grid": "grid"}
_PANEL_GAP = 20.0
_PANEL_TITLE_H = 26.0


def _xesc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _panelize(source: str):
    """Detect a multi-panel figure. Returns ``(layout, cols, [(title, src), ...])`` or ``None``
    for an ordinary single-panel figure (no layout directive and no ``---`` separators)."""
    lines = source.splitlines()
    layout: Optional[str] = None
    cols: Optional[int] = None
    rest = lines
    for i, raw in enumerate(lines):
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        m = _LAYOUT_RE.match(s)
        if m:
            layout = m.group(1).lower()
            cm = _COLS_RE.search(m.group(2))
            if cm:
                cols = int(cm.group(1))
            rest = lines[i + 1:]
        break  # only the first meaningful line may be the layout directive

    if layout is None and not any(_PANEL_SEP.match(l) for l in rest):
        return None
    layout = _LAYOUT_ALIASES.get(layout or "row", "row")

    panels: List[List[str]] = [[]]
    for l in rest:
        if _PANEL_SEP.match(l):
            panels.append([])
        else:
            panels[-1].append(l)

    out: List[Tuple[Optional[str], str]] = []
    for p in panels:
        title = None
        body = list(p)
        for j, l in enumerate(body):
            if not l.strip():
                continue
            if l.strip().startswith("#"):  # a leading comment becomes the panel caption
                title = l.strip().lstrip("#").strip() or None
                body = body[:j] + body[j + 1:]
            break
        src = "\n".join(body).strip()
        if src:
            out.append((title, src))
    return layout, cols, out


def _svg_size(svg: str) -> Tuple[float, float]:
    w = float(re.search(r'\bwidth="([\d.]+)"', svg).group(1))
    h = float(re.search(r'\bheight="([\d.]+)"', svg).group(1))
    return w, h


def _compile_multipanel(layout, cols, panels, title, grid, nudge=False) -> str:
    rendered = [(t, _compile_single(src, grid=grid, nudge=nudge)) for t, src in panels]
    sizes = [_svg_size(svg) for _t, svg in rendered]
    n = len(rendered)
    ncols = n if layout == "row" else 1 if layout == "column" else max(1, cols or 2)
    nrows = math.ceil(n / ncols)
    cell_w = max(w for w, _h in sizes)
    cell_h = max(h for _w, h in sizes)
    th = _PANEL_TITLE_H if any(t for t, _ in rendered) else 0.0
    total_w = ncols * cell_w + (ncols - 1) * _PANEL_GAP
    total_h = nrows * (cell_h + th) + (nrows - 1) * _PANEL_GAP

    out: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total_w:.1f} {total_h:.1f}" '
        f'width="{total_w:.0f}" height="{total_h:.0f}" '
        f'font-family="Georgia, \'Times New Roman\', serif">'
    ]
    if title:
        out.append(f"<title>{_xesc(title)}</title>")
    for i, ((ptitle, svg), (w, h)) in enumerate(zip(rendered, sizes)):
        r, c = divmod(i, ncols)
        cell_x = c * (cell_w + _PANEL_GAP)
        cell_y = r * (cell_h + th + _PANEL_GAP)
        if ptitle:
            out.append(
                f'<text x="{cell_x + cell_w / 2:.1f}" y="{cell_y + th * 0.62:.1f}" '
                f'text-anchor="middle" dominant-baseline="middle" font-size="14" '
                f'fill="currentColor">{_xesc(ptitle)}</text>'
            )
        px = cell_x + (cell_w - w) / 2
        py = cell_y + th + (cell_h - h) / 2
        out.append(svg.replace("<svg ", f'<svg x="{px:.1f}" y="{py:.1f}" ', 1))
    out.append("</svg>")
    return "\n".join(out)


def compile_figure(source: str, title: str | None = None, grid: bool = False,
                   nudge: bool = False) -> str:
    """Compile figure DSL ``source`` into an SVG string.

    ``grid=True`` overlays a light logical-coordinate grid (for authoring orientation).
    ``nudge=True`` pushes overlapping labels apart in the rendered output (opt-in; the source
    file is never changed).

    A multi-panel figure (a leading ``layout row|column|grid [cols=N]`` directive and/or
    ``---`` separators between sub-scenes) is laid out as nested viewports; a leading ``#``
    line in a panel captions it.
    """
    panels = _panelize(source)
    if panels is not None:
        return _compile_multipanel(*panels, title=title, grid=grid, nudge=nudge)
    return _compile_single(source, title=title, grid=grid, nudge=nudge)
