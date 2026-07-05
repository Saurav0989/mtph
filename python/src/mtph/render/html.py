"""Render a :class:`~mtph.model.Document` to self-contained HTML.

Math is left as ``$...$`` / ``$$...$$`` and typeset in the browser by KaTeX (vendored and
inlined, so the output file works fully offline). Figures and plots are compiled to inline
SVG. Prose is converted with the math-safe Markdown shim.
"""
from __future__ import annotations

import base64
import functools
import html
import re
from typing import Any, Dict, Optional

from ..diagram.compile_svg import compile_figure
from ..diagram.plot import compile_plot
from ..model import Document
from ..params import defaults as _param_defaults
from ..params import format_value as _fmt_value
from ..params import substitute as _param_substitute
from ..tools.fetch_katex import DEFAULT_VERSION, is_vendored, vendor_dir
from .equations import (
    Labels,
    collect_labels,
    label_of,
    strip_label,
    sub_refs_html,
    sub_refs_math,
)
from .md import md_to_html

_CDN = f"https://cdn.jsdelivr.net/npm/katex@{DEFAULT_VERSION}/dist"
# cdnjs is the ONLY external host allowed inside a Claude Artifact's sandbox CSP, so the artifact
# path loads KaTeX from here instead of jsdelivr (which is blocked). See plans/10.
_CDNJS = f"https://cdnjs.cloudflare.com/ajax/libs/KaTeX/{DEFAULT_VERSION}"
_INIT = (
    '<script>document.addEventListener("DOMContentLoaded",function(){'
    'renderMathInElement(document.body,{delimiters:['
    '{left:"$$",right:"$$",display:true},{left:"$",right:"$",display:false}],'
    # P1: never typeset garbage silently — a bad command renders its source in red, visibly wrong.
    'throwOnError:false,errorColor:"#cc0000"});});</script>'
)


# KaTeX font families that are reachable *only* through an explicit command, so when the
# command never appears in a document, its font is dead weight we can drop. Structural families
# (Main/Math/Size1-4) and the symbol family (AMS, used by many operators that are hard to detect)
# are always kept. Dropping the five below cuts most of the ~677 KB base64 woff2 payload for a
# typical problem that uses none of them.
_DROPPABLE_FONTS = {
    "KaTeX_Caligraphic": ("\\mathcal",),
    "KaTeX_Fraktur": ("\\mathfrak",),
    "KaTeX_SansSerif": ("\\mathsf", "\\textsf"),
    "KaTeX_Script": ("\\mathscr",),
    "KaTeX_Typewriter": ("\\mathtt", "\\texttt"),
}


@functools.lru_cache(maxsize=8)
def _inline_css(drop: frozenset = frozenset()) -> str:
    """Inline the KaTeX stylesheet with woff2 fonts base64-embedded. ``drop`` is a set of
    ``@font-face`` family names to omit entirely (font subsetting; see :func:`_font_drop_set`)."""
    d = vendor_dir()
    css = (d / "katex.min.css").read_text(encoding="utf-8")
    if drop:
        css = re.sub(
            r"@font-face\{[^}]*\}",
            lambda m: "" if any(fam in m.group(0) for fam in drop) else m.group(0),
            css,
        )
    css = re.sub(r',url\(fonts/[^)]*\.woff\) format\("woff"\)', "", css)
    css = re.sub(r',url\(fonts/[^)]*\.ttf\) format\("truetype"\)', "", css)

    def embed(m: re.Match) -> str:
        data = (d / "fonts" / m.group(1)).read_bytes()
        return f"url(data:font/woff2;base64,{base64.b64encode(data).decode()})"

    return re.sub(r"url\(fonts/([^)]*\.woff2)\)", embed, css)


def _collect_latex(blocks, acc: list) -> None:
    """Gather every string where LaTeX commands could appear (for font detection)."""
    for b in blocks:
        for attr in ("text", "latex", "value"):
            v = getattr(b, attr, None)
            if isinstance(v, str):
                acc.append(v)
        if getattr(b, "type", None) == "solution":
            _collect_latex(b.children, acc)


def _font_drop_set(doc: Document) -> frozenset:
    """Which droppable KaTeX font families this document never uses. Over-keeping a font is
    safe; under-keeping breaks glyphs — so detection scans broadly and keeps on any match."""
    acc = [str(doc.meta)]
    _collect_latex(doc.blocks, acc)
    text = "\n".join(acc)
    return frozenset(
        fam for fam, cmds in _DROPPABLE_FONTS.items() if not any(c in text for c in cmds)
    )


@functools.lru_cache(maxsize=1)
def _inline_js() -> str:
    d = vendor_dir()
    katex = (d / "katex.min.js").read_text(encoding="utf-8")
    auto = (d / "contrib" / "auto-render.min.js").read_text(encoding="utf-8")
    return f"<script>{katex}</script>\n<script>{auto}</script>"


def _katex_head(mode: str, drop: frozenset = frozenset()) -> str:
    if mode == "inline":
        return f"<style>{_inline_css(drop)}</style>\n{_inline_js()}\n{_INIT}"
    if mode in ("cdn", "cdnjs"):
        base = _CDNJS if mode == "cdnjs" else _CDN
        return (
            f'<link rel="stylesheet" href="{base}/katex.min.css">\n'
            f'<script defer src="{base}/katex.min.js"></script>\n'
            f'<script defer src="{base}/contrib/auto-render.min.js"></script>\n{_INIT}'
        )
    return ""  # mode == "none"


def _resolve_mode(katex: str) -> str:
    if katex == "auto":
        return "inline" if is_vendored() else "cdn"
    return katex


# -- block + meta rendering ---------------------------------------------------
def _render_math(b, labels: Labels) -> str:
    """Render a display-math block. A ``\\label{key}`` block is numbered and anchored; ``\\ref``
    inside math resolves to the bare number. KaTeX never sees ``\\label``/``\\ref``."""
    key = label_of(b.latex)
    latex = sub_refs_math(strip_label(b.latex), labels)
    body = f"$$ {html.escape(latex)} $$"
    if key and key in labels:
        num, anchor = labels[key]
        return (
            f'<div class="mtph-math numbered" id="{anchor}">'
            f'<span class="eqn">{body}</span>'
            f'<span class="eqno">({num})</span></div>'
        )
    return f'<div class="mtph-math">{body}</div>'


def _render_one(b, grid: bool = False, labels: Optional[Labels] = None,
                params: Optional[dict] = None) -> str:
    """Render a single content block. Answer/solution blocks return "" (shown in the aside).

    ``params`` is the ``name -> default`` map; ``{{name}}`` references in a figure/plot source are
    resolved to these before compiling (a static render is deterministic)."""
    labels = labels or {}
    params = params or {}
    if b.type == "prose":
        return f'<div class="mtph-prose">{sub_refs_html(md_to_html(b.text), labels)}</div>'
    if b.type == "math":
        return _render_math(b, labels)
    if b.type == "figure":
        return _figure(compile_figure(_param_substitute(b.source, params), grid=grid), b.caption)
    if b.type == "plot":
        return _figure(compile_plot(_param_substitute(b.source, params)), b.caption)
    return ""


def _render_blocks(doc: Document, grid: bool = False, labels: Optional[Labels] = None,
                   params: Optional[dict] = None) -> str:
    labels = labels if labels is not None else collect_labels(doc)
    params = _param_defaults(doc.meta) if params is None else params
    return "\n".join(s for b in doc.blocks if (s := _render_one(b, grid, labels, params)))


def _figure(svg: str, caption: str | None) -> str:
    cap = f"<figcaption>{html.escape(caption)}</figcaption>" if caption else ""
    return f'<figure class="mtph-figure">{svg}{cap}</figure>'


def _render_header(meta: Dict[str, Any]) -> str:
    title = html.escape(meta.get("title", "Untitled"))
    chips = []
    for key in ("subject", "topic"):
        if meta.get(key):
            chips.append(f'<span class="chip">{html.escape(str(meta[key]))}</span>')
    if meta.get("difficulty"):
        chips.append(f'<span class="chip">difficulty {int(meta["difficulty"])}/5</span>')
    for tag in meta.get("tags", []) or []:
        chips.append(f'<span class="tag">#{html.escape(str(tag))}</span>')
    return f'<h1>{title}</h1>\n<div class="meta">{"".join(chips)}</div>'


def _render_answer(ans: Dict[str, Any]) -> str:
    t = ans.get("type")
    if t == "expression":
        return f'<p>$ {html.escape(str(ans.get("value", "")))} $</p>'
    if t == "numeric":
        unit = f' {html.escape(str(ans["unit"]))}' if ans.get("unit") else ""
        return f'<p>$ {html.escape(str(ans.get("value")))}{unit} $</p>'
    if t == "choice":
        opts = ans.get("options", [])
        correct = ans.get("correct")
        correct = correct if isinstance(correct, list) else [correct]
        items = []
        for i, o in enumerate(opts):
            cls = ' class="correct"' if i in correct else ""
            items.append(f"<li{cls}>{html.escape(str(o))}</li>")
        return f"<ol class='choices'>{''.join(items)}</ol>"
    if t == "freeform":
        return md_to_html(str(ans.get("value", "")))
    return ""


def _answer_value_html(value: str, answer_type: str, part: Optional[str]) -> str:
    tag = f"<strong>({html.escape(part)})</strong> " if part else ""
    if answer_type == "freeform":
        return f"<div>{tag}{md_to_html(value)}</div>"
    return f"<p>{tag}$ {html.escape(value)} $</p>"


def _render_answer_blocks(answers) -> str:
    return "".join(_answer_value_html(b.value, b.answer_type, b.part) for b in answers)


def _render_meta_answers(answers) -> str:
    out = []
    for a in answers:
        out.append(_answer_value_html(str(a.get("value", "")),
                                      a.get("type", "expression"), a.get("part")))
    return "".join(out)


def _render_grading(grading) -> str:
    """A marking rubric: per-criterion points and a total. Criteria may contain `$…$` math."""
    items, total = [], 0.0
    for g in grading:
        pts = g.get("points", 0)
        if isinstance(pts, (int, float)):
            total += pts
        part = f'<strong>({html.escape(str(g["part"]))})</strong> ' if g.get("part") else ""
        items.append(f'<li><span class="pts">{pts:g} pts</span> {part}'
                     f'{html.escape(str(g.get("criteria", "")))}</li>')
    return (f'<div class="grading"><h3>Grading</h3><ul class="rubric">{"".join(items)}</ul>'
            f'<p class="total">Total: {total:g} pts</p></div>')


def answer_solution_parts(doc: Document, grid: bool = False,
                          labels: Optional[Labels] = None) -> list:
    """The inner answer/solution HTML fragments. Body ```answer/```solution blocks take
    precedence over front-matter; falls back to meta for back-compat. Shared by the static
    aside and the reader's reveal panel."""
    labels = labels if labels is not None else collect_labels(doc)
    params = _param_defaults(doc.meta)
    answers = [b for b in doc.blocks if b.type == "answer"]
    solutions = [b for b in doc.blocks if b.type == "solution"]
    meta = doc.meta
    parts: list = []
    if answers or solutions:
        if answers:
            parts.append(f'<div class="answer"><h3>Answer</h3>{_render_answer_blocks(answers)}</div>')
        for sol in solutions:
            inner = "\n".join(s for c in sol.children if (s := _render_one(c, grid, labels, params)))
            parts.append(f'<div class="solution"><h3>Solution</h3>{inner}</div>')
    else:
        if meta.get("answer"):
            parts.append(f'<div class="answer"><h3>Answer</h3>{_render_answer(meta["answer"])}</div>')
        elif meta.get("answers"):
            parts.append(f'<div class="answer"><h3>Answer</h3>{_render_meta_answers(meta["answers"])}</div>')
        if meta.get("solution"):
            sol_html = sub_refs_html(md_to_html(str(meta["solution"])), labels)
            parts.append(f'<div class="solution"><h3>Solution</h3>{sol_html}</div>')
    if meta.get("grading"):
        parts.append(_render_grading(meta["grading"]))
    return parts


def _render_aside(doc: Document, grid: bool = False, labels: Optional[Labels] = None) -> str:
    parts = answer_solution_parts(doc, grid, labels)
    if not parts:
        return ""
    return (
        '<details class="mtph-aside"><summary>Answer &amp; solution</summary>'
        + "\n".join(parts)
        + "</details>"
    )


_PAGE_CSS = """
:root { --ink:#1a1a1a; --muted:#666; --line:#e2e2e2; --paper:#fff; --bg:#f7f7f8;
  --chip-bg:#eef0f3; --chip-ink:#445; --code-bg:#f0f0f2; --summary:#334; --ok:#2a7; }
@media (prefers-color-scheme: dark) {
  :root { --ink:#e7e7e4; --muted:#9a9aa2; --line:#33343a; --paper:#1d1e22; --bg:#141519;
    --chip-bg:#2a2c33; --chip-ink:#c3cbe0; --code-bg:#26282e; --summary:#c3cbe0; --ok:#4cd6a0; }
}
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--ink);
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,serif; }
main { max-width:760px; margin:40px auto; background:var(--paper); padding:40px 48px;
  border:1px solid var(--line); border-radius:10px; line-height:1.6; }
h1 { font-size:1.6rem; margin:0 0 .4rem; }
.meta { margin-bottom:1.6rem; }
.chip { display:inline-block; font-size:.74rem; background:var(--chip-bg); color:var(--chip-ink);
  padding:2px 9px; border-radius:20px; margin-right:6px; }
.tag { font-size:.74rem; color:var(--muted); margin-right:6px; }
.mtph-prose { margin:1rem 0; }
.mtph-math { margin:1.3rem 0; text-align:center; overflow-x:auto; }
.mtph-math.numbered { position:relative; padding-right:2.5rem; }
.mtph-math.numbered .eqno { position:absolute; right:0; top:50%; transform:translateY(-50%);
  color:var(--muted); font-variant-numeric:tabular-nums; }
.eqref { text-decoration:none; color:inherit; border-bottom:1px dotted var(--muted); }
.mtph-figure { margin:1.6rem 0; text-align:center; }
/* Diagrams/plots draw their default ink with currentColor, so they follow the page theme;
   the white knock-out fills and label halos are re-themed to the paper colour here. */
.mtph-figure svg { max-width:100%; height:auto; color:var(--ink); }
.mtph-figure svg .mtph-pp { fill:var(--paper); }
.mtph-figure svg .mtph-lbl { fill:var(--paper); stroke:var(--paper); }
figcaption { font-size:.85rem; color:var(--muted); margin-top:.4rem; }
.mtph-aside { margin-top:2rem; border-top:1px solid var(--line); padding-top:1rem; }
.mtph-aside summary { cursor:pointer; font-weight:600; color:var(--summary); }
.answer, .solution { margin-top:1rem; }
.answer h3, .solution h3 { font-size:.95rem; text-transform:uppercase; letter-spacing:.04em;
  color:var(--muted); margin:.6rem 0 .3rem; }
.choices li.correct { font-weight:700; }
.choices li.correct::after { content:" ✓"; color:var(--ok); }
.grading .rubric { list-style:none; padding-left:0; }
.grading .rubric li { margin:.25rem 0; }
.grading .pts { display:inline-block; min-width:3.6em; font-variant-numeric:tabular-nums;
  font-weight:600; color:var(--muted); }
.grading .total { font-weight:600; margin-top:.4rem; }
code { background:var(--code-bg); padding:1px 5px; border-radius:4px; font-size:.92em; }
.mtph-quiz { margin-top:2rem; border-top:1px solid var(--line); padding-top:1rem; }
.mtph-quiz h3 { font-size:.95rem; text-transform:uppercase; letter-spacing:.04em;
  color:var(--muted); margin:.4rem 0 .7rem; }
.mtph-quiz .q { margin:.55rem 0; }
.mtph-quiz .q-row { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.mtph-quiz .q-in { font:inherit; padding:4px 8px; border:1px solid var(--line); border-radius:6px;
  background:var(--paper); color:var(--ink); width:8em; }
.mtph-quiz .q-unit { color:var(--muted); }
.mtph-quiz button { font:inherit; font-size:.85rem; padding:4px 12px; border:1px solid var(--line);
  border-radius:6px; background:var(--bg); color:var(--ink); cursor:pointer; }
.mtph-quiz button:hover { border-color:var(--summary); }
.mtph-quiz .q-choices { list-style:none; padding-left:0; display:flex; flex-direction:column;
  gap:6px; margin:.3rem 0; }
.mtph-quiz .q-opt { text-align:left; width:100%; }
.mtph-quiz .q-opt.sel { border-color:var(--summary); font-weight:600; }
.mtph-quiz .q-fb { font-weight:600; }
.mtph-quiz .q-fb.ok { color:var(--ok); }
.mtph-quiz .q-fb.no { color:#cc4b37; }
.mtph-quiz .q-reveal { margin-top:1rem; border-top:1px solid var(--line); padding-top:.8rem; }
.mtph-quiz .q-reveal summary { cursor:pointer; font-weight:600; color:var(--summary); }
"""

# The self-quiz checker — a self-contained script (no deps), emitted once in `quiz` mode. It reads
# the correct answer from each `.q` element's data-attributes and grades client-side: numeric with
# a relative tolerance, choice by index. Kept as a byte-identical constant in the JS port.
_QUIZ_JS = (
    "<script>(function(){"
    "document.querySelectorAll('.mtph-quiz .q').forEach(function(q){"
    "var t=q.getAttribute('data-type');var fb=q.querySelector('.q-fb');"
    "if(t==='numeric'){"
    "var c=parseFloat(q.getAttribute('data-correct'));"
    "var tol=parseFloat(q.getAttribute('data-tol'))||0.01;"
    "var inp=q.querySelector('.q-in');"
    "var go=function(){var v=parseFloat((inp.value||'').replace(',','.'));"
    "if(isNaN(v)){fb.textContent='enter a number';fb.className='q-fb';return;}"
    "var ok=Math.abs(v-c)<=tol*Math.max(Math.abs(c),1e-12);"
    "fb.textContent=ok?'\\u2713 correct':'\\u2717 try again';fb.className='q-fb '+(ok?'ok':'no');};"
    "q.querySelector('.q-check').addEventListener('click',go);"
    "inp.addEventListener('keydown',function(e){if(e.key==='Enter'){e.preventDefault();go();}});"
    "}else if(t==='choice'){"
    "var ci=parseInt(q.getAttribute('data-correct'),10);"
    "q.querySelectorAll('.q-opt').forEach(function(b){b.addEventListener('click',function(){"
    "q.querySelectorAll('.q-opt').forEach(function(x){x.classList.remove('sel');});"
    "b.classList.add('sel');var ok=parseInt(b.getAttribute('data-i'),10)===ci;"
    "fb.textContent=ok?'\\u2713 correct':'\\u2717 not that one';fb.className='q-fb '+(ok?'ok':'no');"
    "});});}});})();</script>"
)

# A strict number literal (same in the JS port), so both implementations decide identically which
# numeric answers are auto-checkable.
_NUM_RE = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")


def _correct_str(v) -> str:
    """The correct answer as a data-attribute string (canonical for numbers, matching JS)."""
    return _fmt_value(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else str(v)


def _quiz_items(doc: Document) -> list:
    """The answer data needed to build interactive quiz inputs (body blocks win over meta)."""
    body = [b for b in doc.blocks if b.type == "answer"]
    if body:
        return [{"type": getattr(b, "answer_type", "expression"), "value": b.value,
                 "part": getattr(b, "part", None), "unit": getattr(b, "unit", None),
                 "options": None, "correct": None, "tolerance": getattr(b, "tolerance", None)}
                for b in body]
    items = []
    meta = doc.meta
    for a, part in ([(meta["answer"], None)] if isinstance(meta.get("answer"), dict) else []) + \
            [(x, x.get("part")) for x in (meta.get("answers") or []) if isinstance(x, dict)]:
        items.append({"type": a.get("type", "expression"), "value": a.get("value", ""),
                      "part": part, "unit": a.get("unit"), "options": a.get("options"),
                      "correct": a.get("correct"), "tolerance": a.get("tolerance")})
    return items


def _quiz_row(it: dict) -> str:
    """One interactive quiz control for a numeric or choice answer ("" for other types)."""
    part = f'<strong>({html.escape(str(it["part"]))})</strong> ' if it.get("part") else ""
    t = it["type"]
    if t == "numeric":
        correct = _correct_str(it["value"])
        if _NUM_RE.match(correct.strip()):
            tol = _fmt_value(it["tolerance"]) if it.get("tolerance") is not None else "0.01"
            unit = f'<span class="q-unit">{html.escape(str(it["unit"]))}</span>' if it.get("unit") else ""
            return (
                f'<div class="q" data-type="numeric" data-correct="{html.escape(correct.strip())}" '
                f'data-tol="{tol}"><div class="q-row">{part}<input class="q-in" type="text" '
                f'inputmode="decimal" placeholder="your answer" aria-label="your answer">{unit}'
                f'<button class="q-check" type="button">Check</button>'
                f'<span class="q-fb"></span></div></div>'
            )
    if t == "choice" and isinstance(it.get("options"), list):
        correct = it["correct"]
        ci = correct[0] if isinstance(correct, list) else correct
        opts = "".join(
            f'<li><button class="q-opt" type="button" data-i="{i}">{html.escape(str(o))}</button></li>'
            for i, o in enumerate(it["options"])
        )
        return (
            f'<div class="q" data-type="choice" data-correct="{html.escape(str(ci))}">{part}'
            f'<ol class="q-choices">{opts}</ol><span class="q-fb"></span></div>'
        )
    return ""


def _render_quiz(doc: Document, grid: bool = False, labels: Optional[Labels] = None) -> str:
    """Self-quiz section: interactive inputs for numeric/choice answers, plus a reveal of the full
    answer & solution. Returns "" when there's nothing to test."""
    labels = labels if labels is not None else collect_labels(doc)
    rows = "".join(r for it in _quiz_items(doc) if (r := _quiz_row(it)))
    reveal = answer_solution_parts(doc, grid, labels)
    if not rows and not reveal:
        return ""
    out = '<div class="mtph-quiz"><h3>Check your answer</h3>' + rows
    if reveal:
        out += ('<details class="q-reveal"><summary>Show answer &amp; solution</summary>'
                + "\n".join(reveal) + "</details>")
    return out + "</div>"


def render_html(
    doc: Document,
    *,
    katex: str = "auto",
    include_answer: bool = True,
    standalone: bool = True,
    grid: bool = False,
    subset: bool = True,
    quiz: bool = False,
    badge: Optional[str] = None,
) -> str:
    """Render ``doc`` to an HTML string.

    katex: ``"auto"`` (inline vendored if present, else CDN), ``"inline"``, ``"cdn"``, ``"none"``.
    grid: overlay a logical-coordinate grid on figures (authoring aid).
    subset: when inlining KaTeX, embed only the font families the document actually uses
        (drops Fraktur/Script/Typewriter/SansSerif/Caligraphic when unused). Safe; on by default.
    quiz: render the answer section as a self-quiz (input + tolerance check / clickable choices,
        with a reveal) instead of the plain answer aside.
    badge: an optional honest verification line rendered under the title (a `<p class=
        "mtph-verified">`). Composed only by the CLI (`mtph render --badge`), never by the
        renderer on its own, so default output — and the JS port — stay untouched.
    """
    mode = _resolve_mode(katex)
    drop = _font_drop_set(doc) if (mode == "inline" and subset) else frozenset()
    labels = collect_labels(doc)
    aside = ""
    if include_answer:
        aside = _render_quiz(doc, grid, labels) if quiz else _render_aside(doc, grid=grid, labels=labels)
    body = (
        _render_header(doc.meta)
        + (f'\n<p class="mtph-verified" style="color:var(--muted);font-size:.8rem;'
           f'margin:.2rem 0 1rem">{html.escape(badge)}</p>' if badge else "")
        + "\n"
        + _render_blocks(doc, grid=grid, labels=labels)
        + (("\n" + aside) if include_answer else "")
    )
    content = f"<main>{body}</main>"
    if quiz and aside:
        content += "\n" + _QUIZ_JS
    if not standalone:
        return content
    return (
        "<!doctype html>\n<html lang='en'>\n<head>\n<meta charset='utf-8'>\n"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>\n"
        f"<title>{html.escape(doc.title)}</title>\n"
        f"<style>{_PAGE_CSS}</style>\n{_katex_head(mode, drop)}\n</head>\n"
        f"<body>\n{content}\n</body>\n</html>\n"
    )
