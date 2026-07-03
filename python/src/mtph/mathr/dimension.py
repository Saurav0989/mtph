"""Dimensional analysis for answer expressions.

Opt-in: a problem declares a ``symbols:`` table in front-matter (``m: mass``, ``g: acceleration``,
``k: force/length`` …). Then ``mtph verify`` can parse each answer *expression* and check two
things purely mechanically:

* **consistency** — a ``+``/``-`` never adds unlike dimensions, and the argument of a
  transcendental function (``\\sin``, ``\\exp``, ``\\ln`` …) is dimensionless;
* **match** — when a target dimension is known (the left side ``a =`` is a declared symbol, or a
  numeric answer carries a ``unit``), the expression's dimension equals it.

Design rule (principle P4 — "unknown is first-class"): the analyzer is **conservative**. If it
meets any construct it doesn't fully understand, or a symbol not in the table, it reports
*"can't determine"* and stays silent — it never guesses, so a reported error is always real.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction
from typing import Dict, List, Optional, Tuple

# Base dimensions: mass, length, time, temperature, electric current.
_BASES = ("M", "L", "T", "K", "I")


@dataclass(frozen=True)
class Dim:
    powers: Tuple[Fraction, Fraction, Fraction, Fraction, Fraction]

    def __mul__(self, o: "Dim") -> "Dim":
        return Dim(tuple(a + b for a, b in zip(self.powers, o.powers)))

    def __truediv__(self, o: "Dim") -> "Dim":
        return Dim(tuple(a - b for a, b in zip(self.powers, o.powers)))

    def __pow__(self, n: Fraction) -> "Dim":
        return Dim(tuple(a * n for a in self.powers))

    @property
    def dimensionless(self) -> bool:
        return all(p == 0 for p in self.powers)

    def __str__(self) -> str:
        if self.dimensionless:
            return "dimensionless"
        parts = []
        for base, p in zip(_BASES, self.powers):
            if p == 0:
                continue
            parts.append(base if p == 1 else f"{base}^{_fmt_pow(p)}")
        return " ".join(parts)


def _fmt_pow(p: Fraction) -> str:
    return str(p.numerator) if p.denominator == 1 else f"{p.numerator}/{p.denominator}"


def _dim(**kw: int) -> Dim:
    idx = {b: i for i, b in enumerate(_BASES)}
    powers = [Fraction(0)] * 5
    for k, v in kw.items():
        powers[idx[k]] = Fraction(v)
    return Dim(tuple(powers))


DIMLESS = _dim()
_M, _L, _T, _K, _I = _dim(M=1), _dim(L=1), _dim(T=1), _dim(K=1), _dim(I=1)

# Named physical quantities → their dimension. Base letters (M/L/T/K/I) are accepted too.
NAMED: Dict[str, Dim] = {
    "dimensionless": DIMLESS, "1": DIMLESS, "number": DIMLESS, "scalar": DIMLESS,
    "angle": DIMLESS, "radian": DIMLESS, "rad": DIMLESS, "count": DIMLESS,
    "m": _M, "mass": _M,
    "l": _L, "length": _L, "distance": _L, "displacement": _L, "position": _L,
    "height": _L, "width": _L, "radius": _L, "wavelength": _L, "amplitude": _L,
    "t": _T, "time": _T, "duration": _T, "period": _T,
    "k": _K, "temperature": _K,
    "i": _I, "current": _I,
    "area": _dim(L=2), "volume": _dim(L=3),
    "velocity": _dim(L=1, T=-1), "speed": _dim(L=1, T=-1),
    "acceleration": _dim(L=1, T=-2), "gravity": _dim(L=1, T=-2),
    "frequency": _dim(T=-1), "angularvelocity": _dim(T=-1), "angular_velocity": _dim(T=-1),
    "angularfrequency": _dim(T=-1), "rate": _dim(T=-1),
    "angularacceleration": _dim(T=-2), "angular_acceleration": _dim(T=-2),
    "force": _dim(M=1, L=1, T=-2), "weight": _dim(M=1, L=1, T=-2),
    "tension": _dim(M=1, L=1, T=-2),
    "momentum": _dim(M=1, L=1, T=-1), "impulse": _dim(M=1, L=1, T=-1),
    "energy": _dim(M=1, L=2, T=-2), "work": _dim(M=1, L=2, T=-2),
    "heat": _dim(M=1, L=2, T=-2), "torque": _dim(M=1, L=2, T=-2),
    "power": _dim(M=1, L=2, T=-3),
    "pressure": _dim(M=1, L=-1, T=-2), "stress": _dim(M=1, L=-1, T=-2),
    "density": _dim(M=1, L=-3),
    "momentofinertia": _dim(M=1, L=2), "moment_of_inertia": _dim(M=1, L=2),
    "angularmomentum": _dim(M=1, L=2, T=-1), "angular_momentum": _dim(M=1, L=2, T=-1),
    "stiffness": _dim(M=1, T=-2), "springconstant": _dim(M=1, T=-2),
    "spring_constant": _dim(M=1, T=-2),
    "charge": _dim(I=1, T=1),
    "voltage": _dim(M=1, L=2, T=-3, I=-1), "potential": _dim(M=1, L=2, T=-3, I=-1),
    "emf": _dim(M=1, L=2, T=-3, I=-1),
    "resistance": _dim(M=1, L=2, T=-3, I=-2),
    "capacitance": _dim(M=-1, L=-2, T=4, I=2),
    "inductance": _dim(M=1, L=2, T=-2, I=-2),
    "magneticfield": _dim(M=1, T=-2, I=-1), "magnetic_field": _dim(M=1, T=-2, I=-1),
    "electricfield": _dim(M=1, L=1, T=-3, I=-1), "electric_field": _dim(M=1, L=1, T=-3, I=-1),
    "entropy": _dim(M=1, L=2, T=-2, K=-1), "heatcapacity": _dim(M=1, L=2, T=-2, K=-1),
    "heat_capacity": _dim(M=1, L=2, T=-2, K=-1),
}

# Units (for a numeric answer's `unit`) → dimension. SI base + the common derived units.
_UNITS: Dict[str, Dim] = {
    "1": DIMLESS, "rad": DIMLESS, "sr": DIMLESS, "deg": DIMLESS, "%": DIMLESS,
    "kg": _M, "g": _M,
    "m": _L, "cm": _L, "mm": _L, "km": _L, "nm": _L,
    "s": _T, "ms": _T, "min": _T, "h": _T, "hr": _T,
    "K": _K, "A": _I,
    "N": _dim(M=1, L=1, T=-2), "J": _dim(M=1, L=2, T=-2), "W": _dim(M=1, L=2, T=-3),
    "Pa": _dim(M=1, L=-1, T=-2), "Hz": _dim(T=-1),
    "C": _dim(I=1, T=1), "V": _dim(M=1, L=2, T=-3, I=-1),
    "ohm": _dim(M=1, L=2, T=-3, I=-2), "F": _dim(M=-1, L=-2, T=4, I=2),
    "T": _dim(M=1, T=-2, I=-1), "Wb": _dim(M=1, L=2, T=-2, I=-1),
}

# transcendental functions: argument must be dimensionless, result is dimensionless
_FUNCS = {
    "sin", "cos", "tan", "cot", "sec", "csc", "sinh", "cosh", "tanh", "coth",
    "arcsin", "arccos", "arctan", "exp", "ln", "log",
}
# dimensionless mathematical constants (unless the author declares a symbol of the same name)
_CONSTS = {"pi", "e", "tau"}


class _CantTell(Exception):
    """Raised when the analyzer meets something it can't understand — bail, don't guess."""


def normalize_symbol(name: str) -> str:
    """Table key / token normalizer: drop a leading ``\\``, ``$``, spaces; keep subscripts."""
    s = name.strip().strip("$").strip()
    if s.startswith("\\"):
        s = s[1:]
    return s


def parse_dim_spec(spec: str) -> Optional[Dim]:
    """Parse a ``symbols:`` value (``"acceleration"``, ``"force/length"``, ``"M L^2 T^-2"``) into a
    :class:`Dim`. Returns ``None`` if it names an unknown quantity or doesn't parse."""
    toks = _tok_spec(spec)
    if not toks:
        return None
    try:
        pos = [0]
        val = _spec_expr(toks, pos)
        if pos[0] != len(toks):
            return None
        return val
    except _CantTell:
        return None


_SPEC_TOKEN = re.compile(r"[A-Za-z_]+|\d+|\^|-|\*|/|\(|\)|\s+")


def _tok_spec(spec: str) -> List[str]:
    out: List[str] = []
    for m in _SPEC_TOKEN.finditer(spec.strip()):
        t = m.group(0)
        if not t.isspace():
            out.append(t)
    # implicit multiplication: "M L^2" — insert * between adjacent operands
    merged: List[str] = []
    for t in out:
        if merged and _is_operand_start(t) and _is_operand_end(merged[-1]):
            merged.append("*")
        merged.append(t)
    return merged


def _is_operand_start(t: str) -> bool:
    return bool(re.match(r"[A-Za-z_]", t)) or t.isdigit() or t == "("


def _is_operand_end(t: str) -> bool:
    return bool(re.match(r"[A-Za-z_]", t)) or t.isdigit() or t == ")"


def _spec_expr(toks: List[str], pos: List[int]) -> Dim:
    val = _spec_term(toks, pos)
    while pos[0] < len(toks) and toks[pos[0]] in ("*", "/"):
        op = toks[pos[0]]
        pos[0] += 1
        rhs = _spec_term(toks, pos)
        val = val * rhs if op == "*" else val / rhs
    return val


def _spec_term(toks: List[str], pos: List[int]) -> Dim:
    val = _spec_atom(toks, pos)
    if pos[0] < len(toks) and toks[pos[0]] == "^":
        pos[0] += 1
        val = val ** _spec_exp(toks, pos)
    return val


def _spec_exp(toks: List[str], pos: List[int]) -> Fraction:
    sign = 1
    if pos[0] < len(toks) and toks[pos[0]] == "-":
        sign = -1
        pos[0] += 1
    if pos[0] >= len(toks) or not toks[pos[0]].isdigit():
        raise _CantTell
    n = int(toks[pos[0]])
    pos[0] += 1
    return Fraction(sign * n)


def _spec_atom(toks: List[str], pos: List[int]) -> Dim:
    if pos[0] >= len(toks):
        raise _CantTell
    t = toks[pos[0]]
    if t == "(":
        pos[0] += 1
        val = _spec_expr(toks, pos)
        if pos[0] >= len(toks) or toks[pos[0]] != ")":
            raise _CantTell
        pos[0] += 1
        return val
    if t.isdigit():
        pos[0] += 1
        return DIMLESS  # a bare number is dimensionless
    key = t.lower()
    if key in NAMED:
        pos[0] += 1
        return NAMED[key]
    raise _CantTell


def parse_unit(unit: str) -> Optional[Dim]:
    """Parse a numeric answer's ``unit`` (``"m/s^2"``, ``"N"``, ``"kg m/s"``) into a dimension."""
    u = unit.replace("·", "*").replace("Ω", "ohm").strip()
    toks = _tok_unit(u)
    if not toks:
        return None
    try:
        pos = [0]
        val = _unit_expr(toks, pos)
        if pos[0] != len(toks):
            return None
        return val
    except _CantTell:
        return None


_UNIT_TOKEN = re.compile(r"[A-Za-z%]+|\d+|\^|-|\*|/|\(|\)|\s+")


def _tok_unit(u: str) -> List[str]:
    out: List[str] = []
    for m in _UNIT_TOKEN.finditer(u):
        t = m.group(0)
        if not t.isspace():
            out.append(t)
    merged: List[str] = []
    for t in out:
        if merged and _is_operand_start(t) and _is_operand_end(merged[-1]):
            merged.append("*")
        merged.append(t)
    return merged


def _unit_expr(toks: List[str], pos: List[int]) -> Dim:
    val = _unit_term(toks, pos)
    while pos[0] < len(toks) and toks[pos[0]] in ("*", "/"):
        op = toks[pos[0]]
        pos[0] += 1
        rhs = _unit_term(toks, pos)
        val = val * rhs if op == "*" else val / rhs
    return val


def _unit_term(toks: List[str], pos: List[int]) -> Dim:
    val = _unit_atom(toks, pos)
    if pos[0] < len(toks) and toks[pos[0]] == "^":
        pos[0] += 1
        val = val ** _spec_exp(toks, pos)
    return val


def _unit_atom(toks: List[str], pos: List[int]) -> Dim:
    if pos[0] >= len(toks):
        raise _CantTell
    t = toks[pos[0]]
    if t == "(":
        pos[0] += 1
        val = _unit_expr(toks, pos)
        if pos[0] >= len(toks) or toks[pos[0]] != ")":
            raise _CantTell
        pos[0] += 1
        return val
    if t.isdigit():
        pos[0] += 1
        return DIMLESS
    if t in _UNITS:
        pos[0] += 1
        return _UNITS[t]
    raise _CantTell


# --------------------------------------------------------------------------- LaTeX expression
@dataclass
class DimResult:
    determined: bool          # did we fully understand the expression?
    dim: Optional[Dim]        # its dimension, if determined
    uses_symbol: bool         # did it reference at least one declared symbol?
    issues: List[str]         # consistency problems found (only when determined)


def dim_of_latex(expr: str, symbols: Dict[str, Dim]) -> DimResult:
    """Compute the dimension of the *right-hand side* of a LaTeX answer expression.

    ``symbols`` maps normalized symbol names to dimensions. Returns a :class:`DimResult`; when
    ``determined`` is False the caller must treat the answer as un-analysable (stay silent)."""
    rhs = expr
    if "=" in rhs:
        rhs = rhs.rsplit("=", 1)[1]
    issues: List[str] = []
    used = {"any": False}
    try:
        toks = _tok_latex(rhs)
        p = _Parser(toks, symbols, issues, used)
        dim = p.parse_expr()
        if not p.at_end():
            raise _CantTell
    except _CantTell:
        return DimResult(False, None, used["any"], [])
    return DimResult(True, dim, used["any"], issues)


def target_dim_of_lhs(expr: str, symbols: Dict[str, Dim]) -> Optional[Dim]:
    """If the answer is ``<symbol> = …`` and ``<symbol>`` is declared, return its dimension."""
    if "=" not in expr:
        return None
    lhs = expr.split("=", 1)[0]
    toks = _tok_latex(lhs)
    if len(toks) == 1 and toks[0][0] == "sym":
        return symbols.get(toks[0][1])
    return None


# Token kinds: ("num", str) ("sym", name) ("op", ch) ("func", name) ("frac",) ("sqrt",)
#   ("lp",)("rp",)("lb",)("rb",)("lbrack",)("rbrack",)
_LATEX_CMD = re.compile(r"\\([A-Za-z]+)")


def _tok_latex(s: str) -> List[Tuple[str, str]]:
    s = s.strip()
    if s.startswith("$") and s.endswith("$"):
        s = s[1:-1]
    toks: List[Tuple[str, str]] = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c.isspace():
            i += 1
        elif c == "\\":
            m = _LATEX_CMD.match(s, i)
            if not m:
                # \, \; \! \{ \} \( \) — spacing or literal; skip the pair
                i += 2
                continue
            cmd = m.group(1)
            i = m.end()
            if cmd in ("cdot", "times", "ast"):
                toks.append(("op", "*"))
            elif cmd in ("div",):
                toks.append(("op", "/"))
            elif cmd in ("frac", "dfrac", "tfrac"):
                toks.append(("frac", ""))
            elif cmd == "sqrt":
                toks.append(("sqrt", ""))
            elif cmd in ("left", "right", "bigl", "bigr", "Bigl", "Bigr", "displaystyle"):
                pass  # sizing/spacing — ignore
            elif cmd in ("quad", "qquad", "text", "mathrm", "mathbf", "vec", "hat", "bar",
                         "dot", "ddot", "tilde", "operatorname"):
                # \text{..}/\vec{..} etc. wrap a symbol; fold the braced content into a name below
                i = _fold_wrapped(s, i, cmd, toks)
            elif cmd in _FUNCS:
                i = _maybe_subscript(s, i, ("func", cmd), toks)
            else:
                i = _maybe_subscript(s, i, ("sym", cmd), toks)
        elif c.isdigit() or c == ".":
            j = i
            while j < n and (s[j].isdigit() or s[j] == "."):
                j += 1
            toks.append(("num", s[i:j]))
            i = j
        elif c.isalpha():
            i = _maybe_subscript(s, i + 1, ("sym", c), toks)
        elif c in "+-*/^(){}[]":
            kind = {"(": "lp", ")": "rp", "{": "lb", "}": "rb", "[": "lbrack", "]": "rbrack"}.get(c)
            toks.append((kind, "") if kind else ("op", c))
            i += 1
        else:
            raise _CantTell  # an unrecognized character — bail conservatively
    return toks


def _fold_wrapped(s: str, i: int, cmd: str, toks: List[Tuple[str, str]]) -> int:
    """``\\vec{v}`` / ``\\text{net}`` → treat the braced body as (part of) a symbol name."""
    if i < len(s) and s[i] == "{":
        depth, j = 0, i
        while j < len(s):
            if s[j] == "{":
                depth += 1
            elif s[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        inner = s[i + 1:j]
        name = normalize_symbol(re.sub(r"[\\{}]|text|mathrm", "", inner))
        return _maybe_subscript(s, j + 1, ("sym", name), toks)
    return i


def _maybe_subscript(s: str, i: int, tok: Tuple[str, str], toks: List[Tuple[str, str]]) -> int:
    """Attach a trailing ``_x`` / ``_{net}`` subscript to a symbol token's name."""
    if tok[0] == "sym" and i < len(s) and s[i] == "_":
        i += 1
        if i < len(s) and s[i] == "{":
            depth, j = 0, i
            while j < len(s):
                if s[j] == "{":
                    depth += 1
                elif s[j] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            sub = s[i + 1:j]
            i = j + 1
        else:
            sub = s[i]
            i += 1
        sub = normalize_symbol(re.sub(r"[\\{}]|text|mathrm", "", sub))
        toks.append(("sym", f"{normalize_symbol(tok[1])}_{sub}"))
        return i
    if tok[0] == "sym":
        toks.append(("sym", normalize_symbol(tok[1])))
        return i
    toks.append(tok)
    return i


class _Parser:
    def __init__(self, toks, symbols, issues, used):
        self.toks = toks
        self.symbols = symbols
        self.issues = issues
        self.used = used
        self.i = 0

    def at_end(self) -> bool:
        return self.i >= len(self.toks)

    def _peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else None

    def parse_expr(self) -> Dim:
        val = self.parse_term()
        while (t := self._peek()) and t[0] == "op" and t[1] in "+-":
            self.i += 1
            rhs = self.parse_term()
            if val != rhs:
                self.issues.append(
                    f"adds {val} to {rhs} (a `+`/`-` between unlike dimensions)"
                )
        return val

    def parse_term(self) -> Dim:
        val = self.parse_power()
        while True:
            t = self._peek()
            if t and t[0] == "op" and t[1] in "*/":
                op = t[1]
                self.i += 1
                rhs = self.parse_power()
                val = val * rhs if op == "*" else val / rhs
            elif t and t[0] in ("num", "sym", "lp", "lb", "frac", "sqrt", "func"):
                val = val * self.parse_power()  # implicit multiplication (juxtaposition)
            else:
                break
        return val

    def parse_power(self) -> Dim:
        base = self.parse_atom()
        if (t := self._peek()) and t[0] == "op" and t[1] == "^":
            self.i += 1
            exp = self._read_exponent()
            if exp is not None:
                return base ** exp
            # non-constant exponent: only dimensionless bases stay determinable
            if base.dimensionless:
                return DIMLESS
            raise _CantTell
        return base

    def _read_exponent(self) -> Optional[Fraction]:
        """A constant exponent (``2``, ``{-1}``, ``{1/2}``); None if it isn't a plain number."""
        t = self._peek()
        if t and t[0] == "lb":
            depth, j = 0, self.i
            while j < len(self.toks):
                if self.toks[j][0] == "lb":
                    depth += 1
                elif self.toks[j][0] == "rb":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            inner = self.toks[self.i + 1:j]
            self.i = j + 1
            return _const_from(inner)
        if t and t[0] == "op" and t[1] == "-":
            self.i += 1
            nxt = self._peek()
            if nxt and nxt[0] == "num":
                self.i += 1
                return -Fraction(nxt[1])
            raise _CantTell
        if t and t[0] == "num":
            self.i += 1
            return Fraction(t[1])
        # a symbol/expression exponent — parse & discard (handled by caller)
        self.parse_atom()
        return None

    def parse_atom(self) -> Dim:
        t = self._peek()
        if t is None:
            raise _CantTell
        kind = t[0]
        if kind == "num":
            self.i += 1
            return DIMLESS
        if kind == "sym":
            self.i += 1
            name = t[1]
            if name in self.symbols:
                self.used["any"] = True
                return self.symbols[name]
            if name.lower() in _CONSTS:
                return DIMLESS
            raise _CantTell  # an undeclared symbol → can't determine
        if kind in ("lp", "lb"):
            close = "rp" if kind == "lp" else "rb"
            self.i += 1
            val = self.parse_expr()
            if not (self._peek() and self._peek()[0] == close):
                raise _CantTell
            self.i += 1
            return val
        if kind == "frac":
            self.i += 1
            num = self._group()
            den = self._group()
            return num / den
        if kind == "sqrt":
            self.i += 1
            root = Fraction(2)
            if self._peek() and self._peek()[0] == "lbrack":
                # \sqrt[n]{...}
                self.i += 1
                inner = []
                while self._peek() and self._peek()[0] != "rbrack":
                    inner.append(self.toks[self.i])
                    self.i += 1
                if not self._peek():
                    raise _CantTell
                self.i += 1
                r = _const_from(inner)
                if r is None or r == 0:
                    raise _CantTell
                root = r
            return self._group() ** (Fraction(1) / root)
        if kind == "func":
            self.i += 1
            if self._peek() and self._peek() == ("op", "^"):
                self.i += 1  # \sin^2 x — the power sits on the (dimensionless) result
                self._read_exponent()
            arg = self._group()
            if not arg.dimensionless:
                self.issues.append(
                    f"the argument of `\\{t[1]}` has dimension {arg} (it must be dimensionless)"
                )
            return DIMLESS
        raise _CantTell

    def _group(self) -> Dim:
        """The operand after ``\\frac``/``\\sqrt``/a function: a ``{…}`` group or a single atom."""
        if self._peek() and self._peek()[0] == "lb":
            self.i += 1
            val = self.parse_expr()
            if not (self._peek() and self._peek()[0] == "rb"):
                raise _CantTell
            self.i += 1
            return val
        return self.parse_power()


def _const_from(toks: List[Tuple[str, str]]) -> Optional[Fraction]:
    """Evaluate a tiny token list as a rational constant (``-1``, ``1/2``, ``3``)."""
    sign = Fraction(1)
    k = 0
    if k < len(toks) and toks[k] == ("op", "-"):
        sign = Fraction(-1)
        k += 1
    if k >= len(toks) or toks[k][0] != "num":
        return None
    val = Fraction(toks[k][1])
    k += 1
    if k < len(toks) and toks[k] == ("op", "/") and k + 1 < len(toks) and toks[k + 1][0] == "num":
        val = val / Fraction(toks[k + 1][1])
        k += 2
    if k != len(toks):
        return None
    return sign * val
