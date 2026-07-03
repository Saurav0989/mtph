"""The individual verification checks.

Each check is a function ``check_x(ctx) -> CheckResult``. They reuse the *real* compilers
(figure, plot) and the schema validator, so ``verify`` and ``render`` can never disagree about
what is and isn't valid (principle P1). Checks must never raise — a check that can't run returns
an ``unknown`` result, honestly (principle P4).

The ordered :data:`CHECKS` registry is what the runner iterates.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, List, Optional

from ..diagram.dsl import DiagramSyntaxError
from ..diagram.inspect import inspect_figure
from ..diagram.plot import PlotError, make_func, make_func2, parse_plot
from ..mathr.dimension import (
    dim_of_latex,
    normalize_symbol,
    parse_dim_spec,
    parse_unit,
    target_dim_of_lhs,
)
from ..mathr.numeric import eval_latex
from ..mathr.latex import _SYMBOLS  # the Greek/symbol command table we already maintain
from ..model import Document
from ..notation import pack as notation_pack
from ..params import PARAM_REF, resolve as _resolve_params
from ..render.equations import _LABEL_RE, _REF_RE, collect_labels
from ..validate import validate
from .model import CheckResult, Finding


@dataclass
class Context:
    text: str  # raw source (for best-effort line numbers)
    doc: Document
    path: Optional[str] = None


# --------------------------------------------------------------------------- helpers
# Inline + display math spans inside prose.
_MATH_SPANS = re.compile(r"\$\$.*?\$\$|\$[^$]+?\$", re.S)


@dataclass
class _Segment:
    context: str
    text: str


def _iter_blocks(blocks):
    """All blocks, descending into ```solution children (so nested figures/math are checked)."""
    for b in blocks:
        yield b
        if b.type == "solution":
            yield from _iter_blocks(b.children)


def _latex_segments(ctx: Context) -> List[_Segment]:
    """Every chunk of the document that is (or contains) LaTeX, with a context label."""
    segs: List[_Segment] = []
    for b in _iter_blocks(ctx.doc.blocks):
        if b.type == "math":
            segs.append(_Segment("math block", b.latex))
        elif b.type == "figure":
            segs.append(_Segment("figure", b.source))
        elif b.type == "plot":
            segs.append(_Segment("plot", b.source))
        elif b.type == "answer":
            segs.append(_Segment("answer block", b.value))
        elif b.type == "prose":
            for m in _MATH_SPANS.finditer(b.text):
                segs.append(_Segment("inline math", m.group(0)))
    meta = ctx.doc.meta
    if isinstance(meta.get("solution"), str):
        segs.append(_Segment("solution", meta["solution"]))
    ans = meta.get("answer")
    if isinstance(ans, dict) and isinstance(ans.get("value"), str):
        segs.append(_Segment("answer.value", ans["value"]))
    answers = meta.get("answers")
    if isinstance(answers, list):
        for i, a in enumerate(answers):
            if isinstance(a, dict) and isinstance(a.get("value"), str):
                segs.append(_Segment(f"answers[{i}].value", a["value"]))
    return segs


def _find_line(text: str, needle: str) -> Optional[int]:
    if not needle:
        return None
    idx = text.find(needle)
    if idx < 0:
        # try the first line of a multi-line needle
        first = needle.splitlines()[0] if needle.splitlines() else needle
        idx = text.find(first)
        if idx < 0:
            return None
    return text.count("\n", 0, idx) + 1


_BEGIN = re.compile(r"\\begin\{")
_END = re.compile(r"\\end\{")


def _env_ranges(text: str) -> List[tuple]:
    """(start, end) spans of ``\\begin{..} … \\end{..}`` where ``\\`` row-breaks legitimately live."""
    begins = [m.start() for m in _BEGIN.finditer(text)]
    ends = [m.end() for m in _END.finditer(text)]
    ranges: List[tuple] = []
    ei = 0
    for b in begins:
        while ei < len(ends) and ends[ei] < b:
            ei += 1
        if ei < len(ends):
            ranges.append((b, ends[ei]))
            ei += 1
    return ranges


# Known LaTeX command names (without the backslash): the Greek/symbol table plus the
# structural commands an author actually types. A double backslash before one of these is
# almost certainly the escaping bug, not a matrix row break (those are followed by space/digit
# or a single variable letter, and live inside \begin..\end which we exempt).
_KNOWN_CMDS = {k.lstrip("\\") for k in _SYMBOLS} | {
    "frac", "dfrac", "tfrac", "binom", "sqrt", "vec", "hat", "bar", "dot", "ddot", "tilde",
    "overline", "underline", "overrightarrow", "sum", "prod", "int", "oint", "iint", "lim",
    "sin", "cos", "tan", "cot", "sec", "csc", "sinh", "cosh", "tanh", "arcsin", "arccos",
    "arctan", "log", "ln", "exp", "min", "max", "det", "deg", "gcd", "mathbf", "mathrm",
    "mathcal", "mathbb", "mathfrak", "mathsf", "mathtt", "boldsymbol", "text", "textbf",
    "textit", "left", "right", "begin", "end", "cdot", "times", "div", "pm", "mp", "leq",
    "geq", "neq", "approx", "equiv", "propto", "partial", "nabla", "infty", "hbar", "langle",
    "rangle", "lambda", "omega", "theta", "alpha", "beta", "gamma", "delta", "phi", "psi",
    "rho", "sigma", "tau", "mu", "nu", "xi", "chi", "eta", "zeta", "kappa", "varphi",
    "varepsilon", "varkappa", "quad", "qquad", "mathring",
}
# two backslashes, then a command word of 2+ letters
_DOUBLE_BS = re.compile(r"\\\\([A-Za-z]{2,})")


# --------------------------------------------------------------------------- checks
def check_schema(ctx: Context) -> CheckResult:
    findings = [
        Finding(id="schema.invalid", severity="error", message=e, context="schema")
        for e in validate(ctx.doc)
    ]
    return CheckResult("schema", findings)


def check_latex(ctx: Context) -> CheckResult:
    """The backslash tax linter: flag ``\\\\command`` that renders as literal ``\\command``."""
    findings: List[Finding] = []
    for seg in _latex_segments(ctx):
        envs = _env_ranges(seg.text)
        for m in _DOUBLE_BS.finditer(seg.text):
            word = m.group(1)
            if word not in _KNOWN_CMDS:
                continue  # be precise: only known commands, to avoid false positives
            if any(a <= m.start() < b for a, b in envs):
                continue  # inside \begin..\end, '\\' is a legitimate row break
            findings.append(
                Finding(
                    id="latex.backslash",
                    severity="error",
                    message=(
                        f"`\\\\{word}` in {seg.context} is a doubled backslash; it renders as the "
                        f"literal text `\\{word}` instead of the command."
                    ),
                    fix=f"Use a single backslash: `\\{word}`.",
                    line=_find_line(ctx.text, m.group(0)),
                    context=seg.context,
                )
            )
    return CheckResult("latex", findings)


def check_figure(ctx: Context) -> CheckResult:
    findings: List[Finding] = []
    for b in _iter_blocks(ctx.doc.blocks):
        if b.type != "figure":
            continue
        try:
            info = inspect_figure(_resolve_params(b.source, ctx.doc.meta))
        except DiagramSyntaxError as e:
            msg = str(e)
            is_anchor = ("anchor" in msg.lower()) or ("point" in msg.lower())
            findings.append(
                Finding(
                    id="figure.undefined_anchor" if is_anchor else "figure.syntax",
                    severity="error",
                    message=msg,
                    fix=(
                        "Define the point first (e.g. `point NAME at=(x,y)`) or reference an "
                        "anchor that exists."
                        if is_anchor
                        else "Fix the figure DSL statement on that line."
                    ),
                    context="figure",
                    extra={"figure_line": getattr(e, "lineno", None)},
                )
            )
            continue
        except Exception as e:  # a renderer bug shouldn't crash verify
            findings.append(
                Finding(id="figure.error", severity="error",
                        message=f"{type(e).__name__}: {e}", context="figure")
            )
            continue
        for d in info["diagnostics"]:
            if d["type"] == "label_overlap":
                a, bb = d["labels"]
                findings.append(
                    Finding(
                        id="figure.label_overlap", severity="warning",
                        message=f"labels {a!r} and {bb!r} overlap (area {d['overlap']}).",
                        fix="Nudge one label apart (set its `at=`) or move the element it sits on.",
                        context="figure", extra={"overlap": d["overlap"]},
                    )
                )
        findings += _label_findings(b.source)
    return CheckResult("figure", findings)


# Figure labels are rendered to SVG via a Unicode mapper (mathr.latex.label_runs), NOT KaTeX. It
# knows Greek/symbols (mathr.latex._SYMBOLS), the accents below, and `_`/`^` sub/superscripts —
# but an argument-taking or unknown command (\frac, \text, \mathbf, \sqrt{x}, …) renders as literal
# text. Surface that instead of shipping a wrong glyph silently (P1).
_LABEL_ACCENTS = {"vec", "hat", "bar", "overline", "dot", "ddot", "tilde"}
_LABEL_OK_CMDS = _LABEL_ACCENTS | {c.lstrip("\\") for c in _SYMBOLS}
_LABEL_ARG_RE = re.compile(r'(?:label|text|value)\s*=\s*"([^"]*)"')
_LABEL_CMD_RE = re.compile(r"(?<!\\)\\([A-Za-z]+)")  # single-backslash command (not \\cmd)


def _label_findings(source: str) -> List[Finding]:
    out: List[Finding] = []
    seen = set()
    for label in _LABEL_ARG_RE.findall(source):
        for cmd in _LABEL_CMD_RE.findall(label):
            if cmd in _LABEL_OK_CMDS or cmd in seen:
                continue
            seen.add(cmd)
            out.append(Finding(
                id="figure.label_unsupported", severity="warning",
                message=(f"figure label {label!r} uses `\\{cmd}`, which the label renderer can't "
                         f"typeset (labels are Unicode, not KaTeX) — it will show as literal text."),
                fix="Use a short plain/Greek label (e.g. `\\theta`, `v_0`), or put the expression "
                    "in a nearby `math` block instead of the figure.",
                context="figure"))
    return out


def _check_expr_domain(findings: List[Finding], label: str, f, lo: float, hi: float,
                       n: int, var: str) -> None:
    bad = [lo + (hi - lo) * i / n for i in range(n + 1)
           if f(lo + (hi - lo) * i / n) is None]
    if len(bad) == n + 1:
        findings.append(
            Finding(id="plot.empty", severity="error",
                    message=f"`{label}` has no finite values on {var}∈[{lo:g}, {hi:g}]; nothing will plot.",
                    fix="Check the expression or restrict the domain.", context="plot")
        )
    elif bad:
        findings.append(
            Finding(id="plot.domain", severity="warning",
                    message=(f"`{label}` is undefined at {len(bad)} sampled point(s) on "
                             f"{var}∈[{lo:g}, {hi:g}] (e.g. {var}={bad[0]:g}); the curve will have gaps."),
                    fix="Restrict the domain or guard the expression (e.g. avoid where it diverges).",
                    context="plot")
        )


def check_plot(ctx: Context) -> CheckResult:
    findings: List[Finding] = []
    for b in _iter_blocks(ctx.doc.blocks):
        if b.type != "plot":
            continue
        try:
            spec = parse_plot(_resolve_params(b.source, ctx.doc.meta))
        except PlotError as e:
            findings.append(
                Finding(id="plot.syntax", severity="error", message=str(e), context="plot",
                        fix="Fix the plot directive or function definition.")
            )
            continue

        if spec.mode in ("parametric", "polar"):
            t0, t1 = spec.tr
            if t1 <= t0:
                findings.append(
                    Finding(id="plot.domain", severity="error",
                            message=f"parameter range must have a < b, got {t0}..{t1}.", context="plot",
                            fix=f"Write it as `{spec.param_var}: a..b` with a < b.")
                )
                continue
            comps = ([("r", spec.rexpr)] if spec.mode == "polar"
                     else [("x", spec.xexpr), ("y", spec.yexpr)])
            for axis, expr in comps:
                try:
                    f = make_func(expr, spec.param_var)
                except PlotError as e:
                    findings.append(
                        Finding(id="plot.syntax", severity="error", message=f"{axis}({spec.param_var}): {e}",
                                context="plot", fix="Fix the expression syntax.")
                    )
                    continue
                _check_expr_domain(findings, f"{axis}({spec.param_var})", f, t0, t1,
                                   spec.samples, spec.param_var)
            continue

        if spec.mode in ("vectorfield", "implicit"):
            vx, vy = spec.field_vars
            comps = ([("u", spec.uexpr), ("v", spec.vexpr)] if spec.mode == "vectorfield"
                     else [("F", spec.fexpr)])
            for name, expr in comps:
                try:
                    make_func2(expr, vx, vy)
                except PlotError as e:
                    findings.append(
                        Finding(id="plot.syntax", severity="error",
                                message=f"{name}({vx},{vy}): {e}", context="plot",
                                fix="Fix the expression syntax.")
                    )
            continue

        x0, x1 = spec.xr
        if x1 <= x0:
            findings.append(
                Finding(id="plot.domain", severity="error",
                        message=f"x domain must have a < b, got {x0}..{x1}.", context="plot",
                        fix="Write the range as a smaller..larger pair, e.g. `x: -3..3`.")
            )
            continue
        for expr in spec.funcs:
            try:
                f = make_func(expr)
            except PlotError as e:
                findings.append(
                    Finding(id="plot.syntax", severity="error", message=f"{expr!r}: {e}",
                            context="plot", fix="Fix the expression syntax.")
                )
                continue
            _check_expr_domain(findings, expr, f, x0, x1, spec.samples, "x")
    return CheckResult("plot", findings)


_BARE_SUB = re.compile(r"(?<!\w)([A-Za-z])_([0-9A-Za-z])(?!\w)")


def check_prose(ctx: Context) -> CheckResult:
    findings: List[Finding] = []
    for b in _iter_blocks(ctx.doc.blocks):
        if b.type != "prose":
            continue
        # blank out math spans so we only inspect non-math prose
        masked = _MATH_SPANS.sub(lambda m: " " * len(m.group(0)), b.text)
        seen = set()
        for m in _BARE_SUB.finditer(masked):
            token = m.group(0)
            if token in seen:
                continue
            seen.add(token)
            findings.append(
                Finding(
                    id="prose.bare_subscript",
                    severity="warning",
                    message=(f"`{token}` looks like a subscript but is outside math mode; "
                             f"Markdown may italicize the `_`."),
                    fix=f"Wrap it in math: `${token}$`.",
                    line=_find_line(ctx.text, token),
                    context="prose",
                )
            )
    return CheckResult("prose", findings)


_PART_RE = re.compile(r"\(([a-h])\)")


def _fmt_parts(letters) -> str:
    return ", ".join(f"({c})" for c in sorted(letters))


def check_parts(ctx: Context) -> CheckResult:
    """Part coverage: if a statement asks parts (a), (b), … and the author uses per-part answers,
    flag parts that have no answer (``parts.missing_answer``) and answers whose part isn't asked
    (``parts.stale_answer``). Only fires for a clearly multi-part problem — never guesses."""
    findings: List[Finding] = []
    prose = " ".join(
        _MATH_SPANS.sub(lambda m: " " * len(m.group(0)), b.text)
        for b in _iter_blocks(ctx.doc.blocks) if b.type == "prose"
    )
    found = set(_PART_RE.findall(prose))
    if not ({"a", "b"} <= found):
        return CheckResult("parts", [])  # not a marked multi-part problem — nothing to check

    asked = set()  # the contiguous run a, b, c, … (a stray far letter isn't treated as a part)
    for i in range(8):
        c = chr(ord("a") + i)
        if c in found:
            asked.add(c)
        else:
            break

    answered = set()
    for b in _iter_blocks(ctx.doc.blocks):
        if b.type == "answer" and getattr(b, "part", None):
            answered.add(str(b.part).strip().lower())
    for a in ctx.doc.meta.get("answers", []) or []:
        if isinstance(a, dict) and a.get("part"):
            answered.add(str(a["part"]).strip().lower())

    if answered:  # the author is using per-part answers → check coverage
        missing = asked - answered
        if missing:
            findings.append(Finding(
                id="parts.missing_answer", severity="warning",
                message=f"statement asks {_fmt_parts(asked)} but has no answer for {_fmt_parts(missing)}.",
                fix="Add a ```answer part=X block for each part (or answer them in the solution).",
                context="parts"))
        stale = answered - asked
        if stale:
            findings.append(Finding(
                id="parts.stale_answer", severity="warning",
                message=f"answer for {_fmt_parts(stale)} but the statement doesn't ask {_fmt_parts(stale)}.",
                fix="Fix the `part=` label, or add the missing part marker to the statement.",
                context="parts"))
    return CheckResult("parts", findings)


def check_refs(ctx: Context) -> CheckResult:
    """Equation cross-references: a ``\\ref{key}`` with no matching ``\\label`` (dangling), and
    a ``\\label`` defined more than once (refs would resolve to the first)."""
    findings: List[Finding] = []
    labels = collect_labels(ctx.doc)  # key -> (number, anchor)

    seen_bad = set()
    for b in _iter_blocks(ctx.doc.blocks):
        text = b.text if b.type == "prose" else b.latex if b.type == "math" else None
        if text is None:
            continue
        for m in _REF_RE.finditer(text):
            key = m.group(1).strip()
            if key in labels or key in seen_bad:
                continue
            seen_bad.add(key)
            findings.append(
                Finding(
                    id="ref.undefined", severity="warning",
                    message=f"`\\ref{{{key}}}` points at an equation label that doesn't exist.",
                    fix=f"Add `\\label{{{key}}}` to the target equation, or fix the key.",
                    line=_find_line(ctx.text, f"\\ref{{{key}}}"), context="refs",
                )
            )

    counts: dict = {}
    for b in _iter_blocks(ctx.doc.blocks):
        if b.type == "math":
            for k in _LABEL_RE.findall(b.latex):
                counts[k.strip()] = counts.get(k.strip(), 0) + 1
    for k, c in counts.items():
        if c > 1:
            findings.append(
                Finding(
                    id="ref.duplicate_label", severity="warning",
                    message=f"`\\label{{{k}}}` is defined {c} times; refs resolve to the first.",
                    fix="Give each equation a unique label.",
                    line=_find_line(ctx.text, f"\\label{{{k}}}"), context="refs",
                )
            )
    return CheckResult("refs", findings)


def check_params(ctx: Context) -> CheckResult:
    """Explorable parameters: a ``{{name}}`` in a figure/plot with no matching ``params:`` entry
    (``param.undefined``), and a malformed declaration — ``min ≥ max`` or a default outside the
    range (``param.bad_range``)."""
    meta = ctx.doc.meta
    params = meta.get("params")
    findings: List[Finding] = []
    declared: dict = {}
    if isinstance(params, dict):
        for name, spec in params.items():
            if not isinstance(spec, dict):
                continue
            declared[str(name)] = spec
            mn, mx, df = spec.get("min"), spec.get("max"), spec.get("default")
            if all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in (mn, mx, df)):
                if mn >= mx:
                    findings.append(Finding(
                        id="param.bad_range", severity="error",
                        message=f"param `{name}` has min {mn} ≥ max {mx}.",
                        fix="Give it min < max.", context="params"))
                elif not (mn <= df <= mx):
                    findings.append(Finding(
                        id="param.bad_range", severity="error",
                        message=f"param `{name}` default {df} is outside [{mn}, {mx}].",
                        fix="Put the default within the declared range.", context="params"))

    seen: set = set()
    for b in _iter_blocks(ctx.doc.blocks):
        src = b.source if b.type in ("figure", "plot") else None
        if src is None:
            continue
        for m in PARAM_REF.finditer(src):
            name = m.group(1)
            if name not in declared and name not in seen:
                seen.add(name)
                findings.append(Finding(
                    id="param.undefined", severity="warning",
                    message=f"`{{{{{name}}}}}` references an undeclared parameter.",
                    fix=f"Declare `{name}` under `params:` in front-matter, or fix the name.",
                    line=_find_line(ctx.text, "{{" + name), context="params"))
    return CheckResult("params", findings)


def _answer_specs(ctx: Context):
    """Yield ``(label, value, unit)`` for every answer *expression* in the document (the
    dimensionally-meaningful kinds: ``expression`` and ``numeric``)."""
    meta = ctx.doc.meta
    ans = meta.get("answer")
    if isinstance(ans, dict) and isinstance(ans.get("value"), str) \
            and ans.get("type") in ("expression", "numeric"):
        yield ("answer.value", ans["value"], ans.get("unit") if ans.get("type") == "numeric" else None)
    for i, a in enumerate(meta.get("answers", []) or []):
        if isinstance(a, dict) and isinstance(a.get("value"), str) \
                and a.get("type") in ("expression", "numeric"):
            yield (f"answers[{i}].value", a["value"],
                   a.get("unit") if a.get("type") == "numeric" else None)
    for b in _iter_blocks(ctx.doc.blocks):
        if b.type == "answer" and isinstance(b.value, str) \
                and getattr(b, "answer_type", "expression") in ("expression", "numeric"):
            yield ("answer block", b.value, getattr(b, "unit", None))


def _symbol_dim_test(spec):
    """Read a ``symbols:`` value in either form → ``(dim_spec_or_None, test_or_None)``.

    The value is a string (the dimension spec) *or* an object ``{dim?, test?}`` carrying the
    dimension and/or a numeric test value. A test-only symbol has no dimension (``dim`` is None)."""
    if isinstance(spec, str):
        return spec, None
    if isinstance(spec, dict):
        dim = spec.get("dim")
        test = spec.get("test")
        dim = dim if isinstance(dim, str) else None
        test = float(test) if isinstance(test, (int, float)) and not isinstance(test, bool) else None
        return dim, test
    return None, None


def check_dimension(ctx: Context) -> CheckResult:
    """Dimensional analysis of the answer expressions, gated on a declared ``symbols:`` table.

    Reports ``dimension.inconsistent`` (a `+`/`-` of unlike dimensions, or a transcendental
    function of a dimensional argument) and ``dimension.mismatch`` (the result's dimension differs
    from the declared left-hand symbol or the numeric ``unit``). The analyzer is conservative: any
    construct or symbol it can't resolve makes the answer un-analysed rather than a false error.
    No ``symbols:`` → ``unknown`` (principle P4)."""
    symbols = ctx.doc.meta.get("symbols")
    if not isinstance(symbols, dict) or not symbols:
        return CheckResult("dimension", declared="unknown",
                           message="no `symbols:` table declared; answer dimensions not checked.")
    findings: List[Finding] = []
    sym_dims: dict = {}
    for name, spec in symbols.items():
        dim_spec, _ = _symbol_dim_test(spec)
        if dim_spec is None:
            continue  # a test-only symbol carries no dimension — nothing to analyse here
        d = parse_dim_spec(dim_spec)
        if d is None:
            findings.append(Finding(
                id="dimension.bad_symbol", severity="warning",
                message=f"can't read the dimension `{dim_spec}` declared for `{name}`.",
                fix="Use a named quantity (mass, length, time, velocity, acceleration, force, "
                    "energy, charge, …) or a formula like `force/length` or `M L^2 T^-2`.",
                line=_find_line(ctx.text, str(name)), context="symbols"))
        else:
            sym_dims[normalize_symbol(str(name))] = d

    checked = False
    for label, value, unit in _answer_specs(ctx):
        res = dim_of_latex(value, sym_dims)
        if not (res.determined and res.uses_symbol):
            continue  # a bare number or an expression we can't fully resolve — stay silent (P4)
        checked = True
        for msg in res.issues:
            findings.append(Finding(
                id="dimension.inconsistent", severity="error",
                message=f"{label}: {msg}.",
                fix="A dimensional inconsistency usually means a dropped, extra, or mistyped factor.",
                line=_find_line(ctx.text, value), context=label))
        target = parse_unit(unit) if unit else target_dim_of_lhs(value, sym_dims)
        if target is not None and res.dim is not None and target != res.dim:
            src = f"the unit `{unit}`" if unit else "the left-hand side"
            findings.append(Finding(
                id="dimension.mismatch", severity="error",
                message=f"{label}: the result has dimension {res.dim}, but {src} is {target}.",
                fix="Re-derive the answer, or correct the declared symbol dimensions if they're wrong.",
                line=_find_line(ctx.text, value), context=label))

    if not checked and not findings:
        return CheckResult("dimension", declared="unknown",
                           message="`symbols:` is declared, but no answer expression referenced it.")
    return CheckResult("dimension", findings)


def _answer_checks(ctx: Context):
    """Yield ``(label, expression, expected)`` for each front-matter answer that declares a numeric
    ``check:`` on an expression value."""
    meta = ctx.doc.meta

    def one(label, a):
        if not isinstance(a, dict):
            return
        chk, val = a.get("check"), a.get("value")
        if isinstance(chk, (int, float)) and not isinstance(chk, bool) and isinstance(val, str):
            yield (label, val, float(chk))

    yield from one("answer.value", meta.get("answer"))
    for i, a in enumerate(meta.get("answers", []) or []):
        yield from one(f"answers[{i}].value", a)


def check_numeric(ctx: Context) -> CheckResult:
    """Numeric spot-check: evaluate an answer expression at the symbols' ``test`` values and confirm
    it equals the declared ``check``. This catches a dropped factor or a flipped sign — errors a
    dimension check is blind to (``\\tfrac12 mv^2`` and ``2mv^2`` share a dimension).

    Gated on an answer carrying ``check:``; with none, ``unknown`` (principle P4). The evaluator
    (:func:`mtph.mathr.numeric.eval_latex`) bails on anything it can't fully resolve, so a
    ``numeric.mismatch`` is always a real disagreement — never a false alarm."""
    checks = list(_answer_checks(ctx))
    if not checks:
        return CheckResult("numeric", declared="unknown",
                           message="no answer declares a `check:` value; numeric spot-check not run.")
    symbols = ctx.doc.meta.get("symbols")
    test_values: dict = {}
    if isinstance(symbols, dict):
        for name, spec in symbols.items():
            _, test = _symbol_dim_test(spec)
            if test is not None:
                test_values[normalize_symbol(str(name))] = test

    findings: List[Finding] = []
    for label, value, expected in checks:
        got = eval_latex(value, test_values)
        if got is None:
            findings.append(Finding(
                id="numeric.unverifiable", severity="warning",
                message=(f"{label}: declares `check: {expected:g}`, but the expression couldn't be "
                         f"evaluated at the test values, so the check didn't run."),
                fix="Give every symbol in the answer a `test:` value under `symbols:` (a bare "
                    "`\\log`, an undeclared symbol, or shorthand like `\\frac12` all make it bail).",
                line=_find_line(ctx.text, value), context=label))
            continue
        # 1% relative: this is a *gross-error* spot-check (dropped factor, sign flip — all ≥50%),
        # so a generous tolerance still catches them while forgiving a check rounded to ~2 sig figs.
        tol = max(1e-9, 1e-2 * abs(expected))
        if abs(got - expected) > tol:
            findings.append(Finding(
                id="numeric.mismatch", severity="error",
                message=(f"{label}: evaluates to {got:.6g} at the test values, but `check:` says "
                         f"{expected:g}."),
                fix="A mismatch here is usually a dropped factor or a flipped sign — re-derive the "
                    "answer, or correct the `check` value if that's the one that's wrong.",
                line=_find_line(ctx.text, value), context=label))
    return CheckResult("numeric", findings)


def check_notation(ctx: Context) -> CheckResult:
    # With a declared `notation:` pack we check convention drift; without one we honestly report
    # `unknown` (principle P4 — never a false `ok`).
    nid = ctx.doc.meta.get("notation")
    if not nid:
        return CheckResult("notation", declared="unknown",
                           message="no `notation:` declared; notation consistency not checked.")
    p = notation_pack(nid)
    if p is None:  # schema already flags an invalid enum; we just can't check it
        return CheckResult("notation", declared="unknown",
                           message=f"unknown notation pack {nid!r}; consistency not checked.")

    # Scan math contexts only (not figure/plot labels) for the vector-notation choice.
    math = "\n".join(s.text for s in _latex_segments(ctx) if s.context not in ("figure", "plot"))
    preferred = p["vector"]
    other = r"\mathbf" if preferred == r"\vec" else r"\vec"
    findings: List[Finding] = []
    if p["vector_strict"] and (other + "{") in math:
        findings.append(Finding(
            id="notation.mixed_vectors", severity="warning",
            message=f"`{other}` used, but the {nid} convention writes vectors as `{preferred}`.",
            fix=f"Replace `{other}{{…}}` with `{preferred}{{…}}`.",
            line=_find_line(ctx.text, other + "{"), context="notation"))
    elif (not p["vector_strict"]) and (other + "{") in math and (preferred + "{") in math:
        findings.append(Finding(
            id="notation.mixed_vectors", severity="warning",
            message=f"both `\\vec` and `\\mathbf` appear; pick one vector style for the {nid} convention.",
            fix=f"Use `{preferred}{{…}}` throughout.",
            line=_find_line(ctx.text, other + "{"), context="notation"))
    return CheckResult("notation", findings)


def check_content(ctx: Context) -> CheckResult:
    # Physical correctness, answer↔solution agreement, difficulty justification: a human must
    # judge these. Never report `ok` here (principle P4).
    return CheckResult("content", declared="unknown",
                       message="answer/solution correctness and physics need human review.")


# Ordered registry — name -> function. Order is leverage order.
CHECKS: List[tuple] = [
    ("schema", check_schema),
    ("latex", check_latex),
    ("figure", check_figure),
    ("plot", check_plot),
    ("prose", check_prose),
    ("parts", check_parts),
    ("refs", check_refs),
    ("params", check_params),
    ("dimension", check_dimension),
    ("numeric", check_numeric),
    ("notation", check_notation),
    ("content", check_content),
]

CHECK_NAMES = [name for name, _ in CHECKS]
