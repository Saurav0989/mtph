"""LaTeX helpers.

Two jobs:

* ``label_runs`` / ``latex_to_unicode`` — turn a short LaTeX label (as used inside figure
  DSL labels) into Unicode + sub/superscript *runs* for crisp SVG ``<text>`` rendering. This
  keeps figures self-contained SVG with no browser needed.
* the KaTeX-backed rendering of full math blocks lives in :mod:`mtph.render.html`, which
  passes LaTeX through to KaTeX in the browser for true typesetting.
"""
from __future__ import annotations

import re
from typing import List, Tuple

# A pragmatic Greek + symbol table covering what shows up in physics/math figure labels.
_SYMBOLS = {
    r"\alpha": "α", r"\beta": "β", r"\gamma": "γ", r"\delta": "δ",
    r"\epsilon": "ε", r"\varepsilon": "ε", r"\zeta": "ζ", r"\eta": "η",
    r"\theta": "θ", r"\vartheta": "ϑ", r"\iota": "ι", r"\kappa": "κ",
    r"\lambda": "λ", r"\mu": "μ", r"\nu": "ν", r"\xi": "ξ", r"\pi": "π",
    r"\rho": "ρ", r"\sigma": "σ", r"\tau": "τ", r"\upsilon": "υ",
    r"\phi": "φ", r"\varphi": "φ", r"\chi": "χ", r"\psi": "ψ", r"\omega": "ω",
    r"\Gamma": "Γ", r"\Delta": "Δ", r"\Theta": "Θ", r"\Lambda": "Λ",
    r"\Xi": "Ξ", r"\Pi": "Π", r"\Sigma": "Σ", r"\Phi": "Φ", r"\Psi": "Ψ",
    r"\Omega": "Ω",
    r"\infty": "∞", r"\partial": "∂", r"\nabla": "∇", r"\times": "×",
    r"\cdot": "·", r"\pm": "±", r"\mp": "∓", r"\leq": "≤", r"\geq": "≥",
    r"\neq": "≠", r"\approx": "≈", r"\propto": "∝", r"\sum": "∑",
    r"\int": "∫", r"\sqrt": "√", r"\angle": "∠", r"\circ": "∘",
    r"\hbar": "ℏ", r"\ell": "ℓ", r"\prime": "′", r"\degree": "°",
    r"\rightarrow": "→", r"\to": "→", r"\Rightarrow": "⇒",
    r"\leftarrow": "←", r"\parallel": "∥", r"\perp": "⊥",
}
# Longest command first so \varepsilon matches before \epsilon, etc.
_SYM_RE = re.compile("|".join(re.escape(k) for k in sorted(_SYMBOLS, key=len, reverse=True)))
_COMBINING_ARROW = "⃗"  # combining right arrow above (for \vec)
_COMBINING_HAT = "̂"  # combining circumflex (for \hat)
_COMBINING_BAR = "̄"  # combining macron (for \bar)
_COMBINING_OVERLINE = "̅"
_COMBINING_DOT = "̇"
_COMBINING_DDOT = "̈"
_COMBINING_TILDE = "̃"


def latex_to_unicode(s: str) -> str:
    """Best-effort: replace LaTeX Greek/symbol commands with Unicode (no sub/superscripts)."""
    s = s.strip()
    if s.startswith("$") and s.endswith("$"):
        s = s[1:-1]

    # \hat{X}, \bar{X}, ... -> X + combining mark. \vec{X} -> X: the combining arrow glyph
    # (U+20D7) is missing from common serif fonts and shows as a tofu box, and an over-arrow
    # is redundant on a figure label that already sits on an arrow.
    def _accent(mark: str):
        def repl(m: re.Match) -> str:
            return m.group(1) + mark
        return repl

    s = re.sub(r"\\vec\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\vec\s+(\w)", r"\1", s)
    for cmd, mark in (
        ("hat", _COMBINING_HAT),
        ("bar", _COMBINING_BAR),
        ("overline", _COMBINING_OVERLINE),
        ("dot", _COMBINING_DOT),
        ("ddot", _COMBINING_DDOT),
        ("tilde", _COMBINING_TILDE),
    ):
        s = re.sub(rf"\\{cmd}\{{([^}}]*)\}}", _accent(mark), s)
        s = re.sub(rf"\\{cmd}\s+(\w)", _accent(mark), s)

    s = _SYM_RE.sub(lambda m: _SYMBOLS[m.group(0)], s)
    s = s.replace(r"\,", " ").replace(r"\;", " ").replace(r"\!", "")
    s = s.replace(r"\{", "{").replace(r"\}", "}")
    return s


def _esc_xml(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def sub_sup_spans(runs: List[Tuple[str, str]], size: float) -> str:
    """Render ``label_runs`` output to SVG ``<tspan>``s using **absolute font-size + `dy`**.

    We deliberately avoid ``baseline-shift`` and percentage font-sizes: browsers honour them, but
    cairosvg (our PNG path) ignores baseline-shift and mis-scales ``font-size="72%"`` into a giant
    glyph. ``dy`` and absolute sizes render correctly in *both*. ``dy`` is tracked as an absolute
    offset from the baseline so normal runs after a sub/superscript return to it.
    """
    out: List[str] = []
    shift = 0.0
    sub_dy, sup_dy, sub_size = size * 0.30, -size * 0.42, size * 0.72
    for txt, kind in runs:
        target = sub_dy if kind == "sub" else sup_dy if kind == "sup" else 0.0
        fs = f' font-size="{sub_size:.1f}"' if kind != "n" else ""
        out.append(f'<tspan dy="{target - shift:.2f}"{fs}>{_esc_xml(txt)}</tspan>')
        shift = target
    return "".join(out)


def label_runs(s: str) -> List[Tuple[str, str]]:
    """Split a label into runs of ``(text, kind)`` where kind is ``'n'``, ``'sub'`` or ``'sup'``.

    Handles ``_x``, ``_{net}``, ``^2``, ``^{-1}`` on top of Unicode substitution, so an SVG
    text emitter can render real subscripts/superscripts via ``<tspan>``.
    """
    s = latex_to_unicode(s)
    runs: List[Tuple[str, str]] = []
    buf = ""
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c in "_^" and i + 1 < n:
            if buf:
                runs.append((buf, "n"))
                buf = ""
            kind = "sub" if c == "_" else "sup"
            i += 1
            if s[i] == "{":
                j = s.find("}", i)
                if j == -1:
                    j = n
                runs.append((s[i + 1 : j], kind))
                i = j + 1
            else:
                runs.append((s[i], kind))
                i += 1
        else:
            buf += c
            i += 1
    if buf:
        runs.append((buf, "n"))
    return runs
