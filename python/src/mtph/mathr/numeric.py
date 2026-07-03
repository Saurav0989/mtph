"""Numeric spot-check of answer expressions (H2).

The opt-in companion to dimensional analysis: when a problem's ``symbols:`` table carries *test
values* and an answer declares an expected number via ``check:``, ``mtph verify`` evaluates the
answer expression at those values and confirms it matches. This catches the classic AI-author slip
of a dropped factor of 2 or a flipped sign — errors a dimension check is blind to (``\\tfrac12
mv^2`` and ``2mv^2`` have the same dimension).

It reuses the conservative LaTeX tokenizer from :mod:`.dimension`; like that analyzer, the evaluator
**bails to ``None``** on any construct or symbol it can't fully resolve, so a reported mismatch is
always real (principle P4 — never guess).
"""
from __future__ import annotations

import math
from typing import Dict, Optional

from .dimension import _tok_latex, _CantTell, _const_from

_CONST_VALUES = {"pi": math.pi, "e": math.e, "tau": math.tau}


def _bail_on_multidigit(t) -> None:
    """LaTeX binds a *single token* to ``\\frac`` / ``\\sqrt`` / ``^`` when the operand is
    unbraced: ``\\frac12`` means ``\\frac{1}{2}`` and ``x^12`` means ``x^1 \\cdot 2``. Our
    tokenizer merges ``12`` into one number, so an unbraced multi-digit operand is ambiguous to
    us — bail (P4) rather than silently compute the wrong value. Single-digit forms (``\\sqrt2``,
    ``x^2``) and braced forms (``\\frac{12}{5}``) are unaffected."""
    if t and t[0] == "num" and len(t[1].replace(".", "")) > 1:
        raise _CantTell

# Only unambiguous functions are evaluated. ``\log`` is deliberately absent — its base (10 vs e)
# is ambiguous, so we bail rather than risk a false mismatch. Others fall through to _CantTell too.
_FUNC_IMPL = {
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "cot": lambda x: 1.0 / math.tan(x), "sec": lambda x: 1.0 / math.cos(x),
    "csc": lambda x: 1.0 / math.sin(x),
    "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
    "arcsin": math.asin, "arccos": math.acos, "arctan": math.atan,
    "exp": math.exp, "ln": math.log,
}


def eval_latex(expr: str, values: Dict[str, float]) -> Optional[float]:
    """Numerically evaluate the right-hand side of a LaTeX answer expression at ``values`` (a map
    of normalized symbol name → number). Returns ``None`` when it can't be fully evaluated."""
    rhs = expr
    if "=" in rhs:
        rhs = rhs.rsplit("=", 1)[1]
    try:
        toks = _tok_latex(rhs)
        p = _NumParser(toks, values)
        v = p.parse_expr()
        if not p.at_end():
            return None
    except (_CantTell, ValueError, ZeroDivisionError, OverflowError, TypeError):
        return None
    if isinstance(v, complex) or not math.isfinite(v):
        return None
    return float(v)


class _NumParser:
    """Recursive-descent evaluator, mirroring dimension._Parser but computing numbers."""

    def __init__(self, toks, values):
        self.toks = toks
        self.values = values
        self.i = 0

    def at_end(self) -> bool:
        return self.i >= len(self.toks)

    def _peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else None

    def parse_expr(self) -> float:
        val = self.parse_term()
        while (t := self._peek()) and t[0] == "op" and t[1] in "+-":
            op = t[1]
            self.i += 1
            rhs = self.parse_term()
            val = val + rhs if op == "+" else val - rhs
        return val

    def parse_term(self) -> float:
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

    def parse_power(self) -> float:
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

    def _read_exp(self) -> float:
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
        _bail_on_multidigit(t)  # `x^12` is x^1·2 in LaTeX — ambiguous, so bail rather than guess
        return self.parse_atom()

    def parse_atom(self) -> float:
        t = self._peek()
        if t is None:
            raise _CantTell
        kind = t[0]
        if kind == "num":
            self.i += 1
            return float(t[1])
        if kind == "sym":
            self.i += 1
            name = t[1]
            if name in self.values:
                return float(self.values[name])
            if name.lower() in _CONST_VALUES:
                return _CONST_VALUES[name.lower()]
            raise _CantTell  # an undeclared symbol → can't evaluate
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
            root = 2.0
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
                root = float(r)
            return self._group() ** (1.0 / root)
        if kind == "func":
            self.i += 1
            power: Optional[float] = None
            if self._peek() and self._peek() == ("op", "^"):
                self.i += 1
                power = self._read_exp()  # \sin^2 x → sin(x) squared
            arg = self._group()
            fn = _FUNC_IMPL.get(t[1])
            if fn is None:
                raise _CantTell
            r = fn(arg)
            return r ** power if power is not None else r
        raise _CantTell

    def _group(self) -> float:
        """The operand after \\frac / \\sqrt / a function: a ``{…}`` group or a single power."""
        if self._peek() and self._peek()[0] == "lb":
            self.i += 1
            v = self.parse_expr()
            if not (self._peek() and self._peek()[0] == "rb"):
                raise _CantTell
            self.i += 1
            return v
        _bail_on_multidigit(self._peek())  # `\frac12` is `\frac{1}{2}` in LaTeX — bail, don't guess
        return self.parse_power()
