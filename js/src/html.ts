// Render a parsed .mtph DOM to self-contained HTML. A faithful port of the CDN paths of
// python/src/mtph/render/html.py.
//
// Math is left as $…$ / $$…$$ and typeset in the browser by KaTeX (loaded from a CDN); figures
// and plots are compiled to inline SVG; prose runs through the math-safe Markdown shim. The
// "inline" (vendored, font-embedding) mode is Python-only — a browser/artifact loads KaTeX from
// a CDN, which is exactly the deterministic path this port reproduces byte-for-byte.

import type { BlockDom, Dom } from "./model.js";
import { compileFigure } from "./compileSvg.js";
import { compilePlot } from "./plot.js";
import { mdToHtml, htmlEscape } from "./md.js";
import { paramDefaults, substituteParams } from "./params.js";
import {
  collectLabels, labelOf, stripLabel, subRefsMath, subRefsHtml,
} from "./equations.js";
import type { Labels } from "./equations.js";
import { g } from "./pyfmt.js";

const DEFAULT_VERSION = "0.16.11";
const CDN = `https://cdn.jsdelivr.net/npm/katex@${DEFAULT_VERSION}/dist`;
// cdnjs is the ONLY external host allowed inside a Claude Artifact's sandbox CSP.
const CDNJS = `https://cdnjs.cloudflare.com/ajax/libs/KaTeX/${DEFAULT_VERSION}`;
const INIT =
  '<script>document.addEventListener("DOMContentLoaded",function(){' +
  "renderMathInElement(document.body,{delimiters:[" +
  '{left:"$$",right:"$$",display:true},{left:"$",right:"$",display:false}],' +
  'throwOnError:false,errorColor:"#cc0000"});});</script>';

const PAGE_CSS = `
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
`;

// The self-quiz checker — byte-identical to Python's _QUIZ_JS. The `\\u2713` here is a literal
// backslash-escape in the emitted script (the browser turns it into ✓ at runtime), matching the
// Python output which likewise emits the literal `✓`.
const QUIZ_JS =
  "<script>(function(){" +
  "document.querySelectorAll('.mtph-quiz .q').forEach(function(q){" +
  "var t=q.getAttribute('data-type');var fb=q.querySelector('.q-fb');" +
  "if(t==='numeric'){" +
  "var c=parseFloat(q.getAttribute('data-correct'));" +
  "var tol=parseFloat(q.getAttribute('data-tol'))||0.01;" +
  "var inp=q.querySelector('.q-in');" +
  "var go=function(){var v=parseFloat((inp.value||'').replace(',','.'));" +
  "if(isNaN(v)){fb.textContent='enter a number';fb.className='q-fb';return;}" +
  "var ok=Math.abs(v-c)<=tol*Math.max(Math.abs(c),1e-12);" +
  "fb.textContent=ok?'\\u2713 correct':'\\u2717 try again';fb.className='q-fb '+(ok?'ok':'no');};" +
  "q.querySelector('.q-check').addEventListener('click',go);" +
  "inp.addEventListener('keydown',function(e){if(e.key==='Enter'){e.preventDefault();go();}});" +
  "}else if(t==='choice'){" +
  "var ci=parseInt(q.getAttribute('data-correct'),10);" +
  "q.querySelectorAll('.q-opt').forEach(function(b){b.addEventListener('click',function(){" +
  "q.querySelectorAll('.q-opt').forEach(function(x){x.classList.remove('sel');});" +
  "b.classList.add('sel');var ok=parseInt(b.getAttribute('data-i'),10)===ci;" +
  "fb.textContent=ok?'\\u2713 correct':'\\u2717 not that one';fb.className='q-fb '+(ok?'ok':'no');" +
  "});});}});})();</script>";

const NUM_RE = /^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$/;

type Meta = Record<string, unknown>;

function katexHead(mode: string): string {
  if (mode === "cdn" || mode === "cdnjs") {
    const base = mode === "cdnjs" ? CDNJS : CDN;
    return (
      `<link rel="stylesheet" href="${base}/katex.min.css">\n` +
      `<script defer src="${base}/katex.min.js"></script>\n` +
      `<script defer src="${base}/contrib/auto-render.min.js"></script>\n${INIT}`
    );
  }
  return ""; // mode === "none"
}

// -- block + meta rendering ---------------------------------------------------
function renderMath(b: BlockDom, labels: Labels): string {
  const key = labelOf(String(b.latex));
  const latex = subRefsMath(stripLabel(String(b.latex)), labels);
  const body = `$$ ${htmlEscape(latex)} $$`;
  if (key && labels.has(key)) {
    const [num, anchor] = labels.get(key)!;
    return (
      `<div class="mtph-math numbered" id="${anchor}">` +
      `<span class="eqn">${body}</span>` +
      `<span class="eqno">(${num})</span></div>`
    );
  }
  return `<div class="mtph-math">${body}</div>`;
}

function figure(svg: string, caption: unknown): string {
  const cap = caption ? `<figcaption>${htmlEscape(String(caption))}</figcaption>` : "";
  return `<figure class="mtph-figure">${svg}${cap}</figure>`;
}

function renderOne(b: BlockDom, grid: boolean, labels: Labels, params: Record<string, number | string>): string {
  if (b.type === "prose") {
    return `<div class="mtph-prose">${subRefsHtml(mdToHtml(String(b.text)), labels)}</div>`;
  }
  if (b.type === "math") return renderMath(b, labels);
  if (b.type === "figure") {
    return figure(compileFigure(substituteParams(String(b.source), params), null, grid), b.caption);
  }
  if (b.type === "plot") {
    return figure(compilePlot(substituteParams(String(b.source), params)), b.caption);
  }
  return "";
}

function renderBlocks(blocks: BlockDom[], grid: boolean, labels: Labels, params: Record<string, number | string>): string {
  return blocks.map((b) => renderOne(b, grid, labels, params)).filter((s) => s).join("\n");
}

function renderHeader(meta: Meta): string {
  const title = htmlEscape("title" in meta ? String(meta.title) : "Untitled");
  const chips: string[] = [];
  for (const key of ["subject", "topic"]) {
    if (meta[key]) chips.push(`<span class="chip">${htmlEscape(String(meta[key]))}</span>`);
  }
  if (meta.difficulty) {
    chips.push(`<span class="chip">difficulty ${Math.trunc(Number(meta.difficulty))}/5</span>`);
  }
  for (const tag of (meta.tags as unknown[]) ?? []) {
    chips.push(`<span class="tag">#${htmlEscape(String(tag))}</span>`);
  }
  return `<h1>${title}</h1>\n<div class="meta">${chips.join("")}</div>`;
}

function renderAnswerMeta(ans: Record<string, unknown>): string {
  const t = ans.type;
  if (t === "expression") return `<p>$ ${htmlEscape(String(ans.value ?? ""))} $</p>`;
  if (t === "numeric") {
    const unit = ans.unit ? ` ${htmlEscape(String(ans.unit))}` : "";
    return `<p>$ ${htmlEscape(String(ans.value))}${unit} $</p>`;
  }
  if (t === "choice") {
    const opts = (ans.options as unknown[]) ?? [];
    const rawCorrect = ans.correct;
    const correct = Array.isArray(rawCorrect) ? rawCorrect : [rawCorrect];
    const items = opts.map((o, i) => {
      const cls = correct.includes(i) ? ' class="correct"' : "";
      return `<li${cls}>${htmlEscape(String(o))}</li>`;
    });
    return `<ol class='choices'>${items.join("")}</ol>`;
  }
  if (t === "freeform") return mdToHtml(String(ans.value ?? ""));
  return "";
}

function answerValueHtml(value: string, answerType: string, part: unknown): string {
  const tag = part ? `<strong>(${htmlEscape(String(part))})</strong> ` : "";
  if (answerType === "freeform") return `<div>${tag}${mdToHtml(value)}</div>`;
  return `<p>${tag}$ ${htmlEscape(value)} $</p>`;
}

function renderAnswerBlocks(answers: BlockDom[]): string {
  return answers
    .map((b) => answerValueHtml(String(b.value), String(b.answer_type ?? "expression"), b.part))
    .join("");
}

function renderMetaAnswers(answers: Record<string, unknown>[]): string {
  return answers
    .map((a) => answerValueHtml(String(a.value ?? ""), String(a.type ?? "expression"), a.part))
    .join("");
}

function renderGrading(grading: Record<string, unknown>[]): string {
  const items: string[] = [];
  let total = 0.0;
  for (const gr of grading) {
    const pts = gr.points ?? 0;
    if (typeof pts === "number") total += pts;
    const part = gr.part ? `<strong>(${htmlEscape(String(gr.part))})</strong> ` : "";
    items.push(
      `<li><span class="pts">${g(Number(pts))} pts</span> ${part}` +
      `${htmlEscape(String(gr.criteria ?? ""))}</li>`,
    );
  }
  return (
    `<div class="grading"><h3>Grading</h3><ul class="rubric">${items.join("")}</ul>` +
    `<p class="total">Total: ${g(total)} pts</p></div>`
  );
}

function answerSolutionParts(dom: Dom, grid: boolean, labels: Labels): string[] {
  const blocks = dom.blocks;
  const params = paramDefaults(dom.meta);
  const answers = blocks.filter((b) => b.type === "answer");
  const solutions = blocks.filter((b) => b.type === "solution");
  const meta = dom.meta;
  const parts: string[] = [];
  if (answers.length || solutions.length) {
    if (answers.length) {
      parts.push(`<div class="answer"><h3>Answer</h3>${renderAnswerBlocks(answers)}</div>`);
    }
    for (const sol of solutions) {
      const inner = renderBlocks((sol.blocks as BlockDom[]) ?? [], grid, labels, params);
      parts.push(`<div class="solution"><h3>Solution</h3>${inner}</div>`);
    }
  } else {
    if (meta.answer) {
      parts.push(`<div class="answer"><h3>Answer</h3>${renderAnswerMeta(meta.answer as Record<string, unknown>)}</div>`);
    } else if (meta.answers) {
      parts.push(`<div class="answer"><h3>Answer</h3>${renderMetaAnswers(meta.answers as Record<string, unknown>[])}</div>`);
    }
    if (meta.solution) {
      const solHtml = subRefsHtml(mdToHtml(String(meta.solution)), labels);
      parts.push(`<div class="solution"><h3>Solution</h3>${solHtml}</div>`);
    }
  }
  if (meta.grading) parts.push(renderGrading(meta.grading as Record<string, unknown>[]));
  return parts;
}

function renderAside(dom: Dom, grid: boolean, labels: Labels): string {
  const parts = answerSolutionParts(dom, grid, labels);
  if (parts.length === 0) return "";
  return (
    '<details class="mtph-aside"><summary>Answer &amp; solution</summary>' +
    parts.join("\n") +
    "</details>"
  );
}

interface QuizItem {
  type: string;
  value: unknown;
  part: unknown;
  unit: unknown;
  options: unknown;
  correct: unknown;
  tolerance: unknown;
}

function correctStr(v: unknown): string {
  return String(v); // String() is canonical for numbers (2.0 → "2"), matching Python _correct_str
}

function quizItems(dom: Dom): QuizItem[] {
  const body = dom.blocks.filter((b) => b.type === "answer");
  if (body.length) {
    return body.map((b) => ({
      type: String(b.answer_type ?? "expression"), value: b.value, part: b.part,
      unit: b.unit, options: null, correct: null, tolerance: b.tolerance,
    }));
  }
  const items: QuizItem[] = [];
  const meta = dom.meta;
  const metaAnswers: [Record<string, unknown>, unknown][] = [];
  if (meta.answer && typeof meta.answer === "object") metaAnswers.push([meta.answer as Record<string, unknown>, null]);
  for (const x of (meta.answers as Record<string, unknown>[]) ?? []) {
    if (x && typeof x === "object") metaAnswers.push([x, x.part]);
  }
  for (const [a, part] of metaAnswers) {
    items.push({
      type: String(a.type ?? "expression"), value: a.value ?? "", part, unit: a.unit,
      options: a.options, correct: a.correct, tolerance: a.tolerance,
    });
  }
  return items;
}

function quizRow(it: QuizItem): string {
  const part = it.part ? `<strong>(${htmlEscape(String(it.part))})</strong> ` : "";
  if (it.type === "numeric") {
    const correct = correctStr(it.value);
    if (NUM_RE.test(correct.trim())) {
      const tol = it.tolerance !== undefined && it.tolerance !== null ? String(it.tolerance) : "0.01";
      const unit = it.unit ? `<span class="q-unit">${htmlEscape(String(it.unit))}</span>` : "";
      return (
        `<div class="q" data-type="numeric" data-correct="${htmlEscape(correct.trim())}" ` +
        `data-tol="${tol}"><div class="q-row">${part}<input class="q-in" type="text" ` +
        `inputmode="decimal" placeholder="your answer" aria-label="your answer">${unit}` +
        `<button class="q-check" type="button">Check</button>` +
        `<span class="q-fb"></span></div></div>`
      );
    }
  }
  if (it.type === "choice" && Array.isArray(it.options)) {
    const ci = Array.isArray(it.correct) ? it.correct[0] : it.correct;
    const opts = (it.options as unknown[])
      .map((o, i) => `<li><button class="q-opt" type="button" data-i="${i}">${htmlEscape(String(o))}</button></li>`)
      .join("");
    return (
      `<div class="q" data-type="choice" data-correct="${htmlEscape(String(ci))}">${part}` +
      `<ol class="q-choices">${opts}</ol><span class="q-fb"></span></div>`
    );
  }
  return "";
}

function renderQuiz(dom: Dom, grid: boolean, labels: Labels): string {
  const rows = quizItems(dom).map((it) => quizRow(it)).filter((r) => r).join("");
  const reveal = answerSolutionParts(dom, grid, labels);
  if (!rows && reveal.length === 0) return "";
  let out = '<div class="mtph-quiz"><h3>Check your answer</h3>' + rows;
  if (reveal.length) {
    out += '<details class="q-reveal"><summary>Show answer &amp; solution</summary>' +
      reveal.join("\n") + "</details>";
  }
  return out + "</div>";
}

export interface RenderOptions {
  katex?: "cdnjs" | "cdn" | "none";
  includeAnswer?: boolean;
  standalone?: boolean;
  grid?: boolean;
  quiz?: boolean;
}

export function renderHtml(dom: Dom, opts: RenderOptions = {}): string {
  const { katex = "cdnjs", includeAnswer = true, standalone = true, grid = false, quiz = false } = opts;
  const labels = collectLabels(dom.blocks);
  const params = paramDefaults(dom.meta);
  let aside = "";
  if (includeAnswer) aside = quiz ? renderQuiz(dom, grid, labels) : renderAside(dom, grid, labels);
  const body =
    renderHeader(dom.meta) +
    "\n" +
    renderBlocks(dom.blocks, grid, labels, params) +
    (includeAnswer ? "\n" + aside : "");
  let content = `<main>${body}</main>`;
  if (quiz && aside) content += "\n" + QUIZ_JS;
  if (!standalone) return content;
  const title = htmlEscape("title" in dom.meta ? String(dom.meta.title) : "Untitled");
  return (
    "<!doctype html>\n<html lang='en'>\n<head>\n<meta charset='utf-8'>\n" +
    "<meta name='viewport' content='width=device-width, initial-scale=1'>\n" +
    `<title>${title}</title>\n` +
    `<style>${PAGE_CSS}</style>\n${katexHead(katex)}\n</head>\n` +
    `<body>\n${content}\n</body>\n</html>\n`
  );
}
