"""Optional symbolic equivalence (plan 14) — the `mtph[cas]` extra.

Multi-point sampling (:mod:`.equiv`) decides most equivalences, but it goes `None` whenever it
can't put numbers in — an undeclared symbol, or a symbol with no `test:` value. This module fills
exactly that gap when the optional `sympy` dependency is installed: it builds a sympy expression
from the *same* conservative tokenizer the numeric evaluator uses (:func:`dimension._tok_latex`),
never `sympy.parsing.latex` (which pulls in antlr4 and accepts far more than we can vouch for), and
asks sympy whether two expressions are the same function of the declared symbols.

**The core never depends on this.** `import mtph` must work without sympy; every entry point here
routes through :func:`_sympy`, which returns ``None`` when the extra is absent (so the caller falls
back to plan-13 behavior). And the verdict stays conservative (P4): only a *provably nonzero*
difference is ``False``; a `simplify` that can't reach zero is ``None`` (couldn't tell), never a
guess. A token-count gate keeps `verify` from ever hanging on a pathological expression.
"""
from __future__ import annotations

import time
from typing import Iterable, List, Optional

from .dimension import _CantTell, _const_from, _tok_latex, normalize_symbol
from .numeric import _bail_on_multidigit

_MAX_TOKENS = 120       # complexity gate: past this, don't even try — return None
_WALL_BUDGET = 2.0      # seconds; a cheap wall check between the two sympy attempts

# The functions we build symbolically — exactly the numeric evaluator's unambiguous set. `\log`
# stays out (ambiguous base), so a `\log` bails to None rather than risking a wrong verdict.
_FUNC_NAMES = {
    "sin", "cos", "tan", "cot", "sec", "csc",
    "sinh", "cosh", "tanh", "arcsin", "arccos", "arctan", "exp", "ln",
}


def _sympy():
    """The sympy module, or ``None`` when the extra isn't installed. The single import point — tests
    monkeypatch this to simulate absence, and every public function bails cleanly on ``None``."""
    try:
        import sympy
        return sympy
    except Exception:  # pragma: no cover - exercised via monkeypatch
        return None


def _func(sp, name):
    m = {
        "sin": sp.sin, "cos": sp.cos, "tan": sp.tan, "cot": sp.cot, "sec": sp.sec, "csc": sp.csc,
        "sinh": sp.sinh, "cosh": sp.cosh, "tanh": sp.tanh,
        "arcsin": sp.asin, "arccos": sp.acos, "arctan": sp.atan,
        "exp": sp.exp, "ln": sp.log,
    }
    return m.get(name)


class _SymBuilder:
    """Recursive descent over `_tok_latex` tokens, mirroring :class:`numeric._NumParser` but
    emitting sympy expressions. Bails (``_CantTell``) on anything outside the supported set — an
    undeclared symbol, `\\log`, an ambiguous unbraced multi-digit operand — so a built expression is
    always one we fully understand."""

    def __init__(self, toks, symbols: set, sp):
        self.toks = toks
        self.syms = symbols
        self.sp = sp
        self.i = 0

    def at_end(self) -> bool:
        return self.i >= len(self.toks)

    def _peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else None

    def parse_expr(self):
        val = self.parse_term()
        while (t := self._peek()) and t[0] == "op" and t[1] in "+-":
            op = t[1]
            self.i += 1
            rhs = self.parse_term()
            val = val + rhs if op == "+" else val - rhs
        return val

    def parse_term(self):
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

    def parse_power(self):
        t = self._peek()
        if t and t[0] == "op" and t[1] in "+-":  # unary sign
            self.i += 1
            v = self.parse_power()
            return -v if t[1] == "-" else v
        base = self.parse_atom()
        if (t := self._peek()) and t[0] == "op" and t[1] == "^":
            self.i += 1
            return base ** self._read_exp()
        return base

    def _read_exp(self):
        t = self._peek()
        if t and t[0] == "lb":
            self.i += 1
            v = self.parse_expr()
            if not (self._peek() and self._peek()[0] == "rb"):
                raise _CantTell
            self.i += 1
            return v
        if t and t[0] == "op" and t[1] == "-":
            self.i += 1
            return -self.parse_atom()
        _bail_on_multidigit(t)
        return self.parse_atom()

    def parse_atom(self):
        sp = self.sp
        t = self._peek()
        if t is None:
            raise _CantTell
        kind = t[0]
        if kind == "num":
            self.i += 1
            return sp.Rational(t[1])  # exact: "2" -> 2, "9.8" -> 49/5, so equivalence stays symbolic
        if kind == "sym":
            self.i += 1
            name = t[1]
            if name in self.syms:
                return sp.Symbol(name, positive=True)  # physics quantities are positive (documented)
            low = name.lower()
            if low == "pi":
                return sp.pi
            if low == "e":
                return sp.E
            if low == "tau":
                return 2 * sp.pi
            raise _CantTell  # an undeclared symbol — can't build
        if kind in ("lp", "lb"):
            close = "rp" if kind == "lp" else "rb"
            self.i += 1
            v = self.parse_expr()
            if not (self._peek() and self._peek()[0] == close):
                raise _CantTell
            self.i += 1
            return v
        if kind == "frac":
            self.i += 1
            num = self._group()
            den = self._group()
            return num / den
        if kind == "sqrt":
            self.i += 1
            root = sp.Integer(2)
            if self._peek() and self._peek()[0] == "lbrack":
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
                root = sp.Rational(r.numerator, r.denominator)
            return self._group() ** (sp.Integer(1) / root)
        if kind == "func":
            self.i += 1
            power = None
            if self._peek() and self._peek() == ("op", "^"):
                self.i += 1
                power = self._read_exp()  # \sin^2 x -> sin(x) squared
            arg = self._group()
            fn = _func(sp, t[1])
            if fn is None:
                raise _CantTell
            r = fn(arg)
            return r ** power if power is not None else r
        raise _CantTell

    def _group(self):
        if self._peek() and self._peek()[0] == "lb":
            self.i += 1
            v = self.parse_expr()
            if not (self._peek() and self._peek()[0] == "rb"):
                raise _CantTell
            self.i += 1
            return v
        _bail_on_multidigit(self._peek())
        return self.parse_power()


def latex_to_sympy(expr: str, symbols: Iterable[str]):
    """Build a sympy expression from ``expr`` over the declared ``symbols`` (an iterable of
    normalized names), or ``None`` when the extra is absent or the expression is outside our
    conservative set. Only the right-hand side of an ``=`` is built (parity with `eval_latex`)."""
    sp = _sympy()
    if sp is None:
        return None
    rhs = expr.rsplit("=", 1)[1] if "=" in expr else expr
    names = {normalize_symbol(str(s)) for s in symbols}
    try:
        b = _SymBuilder(_tok_latex(rhs), names, sp)
        v = b.parse_expr()
        if not b.at_end():
            return None
    except (_CantTell, ValueError, ZeroDivisionError, TypeError, AttributeError):
        return None
    return v


def sym_equivalent(a: str, b: str, symbols: Iterable[str]) -> Optional[bool]:
    """Are ``a`` and ``b`` the same function of the declared ``symbols``, decided symbolically?

    ``True`` when they simplify equal, ``False`` only on a *provably nonzero* difference (a concrete
    nonzero constant), and ``None`` whenever the extra is missing, either side won't build, the pair
    is past the complexity gate, or `simplify` can't reach a verdict (P4 — never a guess)."""
    sp = _sympy()
    if sp is None:
        return None
    try:
        if len(_tok_latex(a)) + len(_tok_latex(b)) > _MAX_TOKENS:
            return None  # complexity gate — never risk a hang
    except Exception:
        return None      # untokenizable (a stray `,`, `\qquad`, …) — can't tell
    ea = latex_to_sympy(a, symbols)
    eb = latex_to_sympy(b, symbols)
    if ea is None or eb is None:
        return None
    start = time.monotonic()
    try:
        if ea.equals(eb) is True:      # numeric-backed and fast; a confident True short-circuits
            return True
        if time.monotonic() - start > _WALL_BUDGET:
            return None
        diff = sp.simplify(ea - eb)
    except Exception:                  # sympy can raise on exotic input — treat as "can't tell"
        return None
    if diff == 0:
        return True
    if diff.is_number and diff != 0:   # a concrete nonzero constant — a real disagreement
        return False
    return None                        # couldn't reduce to a verdict (e.g. `2x - x = x`)
