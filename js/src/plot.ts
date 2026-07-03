// Compile a plot spec into an SVG function plot. A faithful port of
// python/src/mtph/diagram/plot.py.
//
// Independent x/y scaling (unlike the equal-aspect figure Scene), axes through the origin with
// "nice" ticks, optional grid, marked points and reference lines. Expressions are evaluated by a
// small safe shunting-yard parser — never eval.

import { labelRuns, subSupSpans } from "./latex.js";
import { fixed, g as pyG } from "./pyfmt.js";

// -- safe expression evaluator ------------------------------------------------
type Fn1 = (x: number) => number | null;
type Fn2 = (x: number, y: number) => number | null;

const FUNCS: Record<string, (v: number) => number> = {
  sin: Math.sin, cos: Math.cos, tan: Math.tan,
  asin: Math.asin, acos: Math.acos, atan: Math.atan,
  sinh: Math.sinh, cosh: Math.cosh, tanh: Math.tanh,
  exp: Math.exp, sqrt: Math.sqrt, floor: Math.floor, ceil: Math.ceil,
  ln: Math.log, log: Math.log10, abs: Math.abs,
  sign: (v) => (v > 0 ? 1 : 0) - (v < 0 ? 1 : 0),
};
const CONSTS: Record<string, number> = { pi: Math.PI, e: Math.E };
const TOKEN = /\d+\.?\d*(?:[eE][+-]?\d+)?|[A-Za-z_]\w*|[-+*/^(),]|\S/g;
// Unary minus sits between * and ^ so that "-x^2" parses as -(x^2), the usual convention.
const PREC: Record<string, number> = { "+": 2, "-": 2, "*": 3, "/": 3, "u-": 3.5, "^": 4 };
const RIGHT = new Set(["^", "u-"]);

export class PlotError extends Error {}

function toRpn(expr: string, varr: string | string[] = "x"): string[] {
  const variables = typeof varr === "string" ? [varr] : varr;
  const tokens = expr.match(TOKEN) ?? [];
  const out: string[] = [];
  const ops: string[] = [];
  let prev: string | null = null;
  for (const tok of tokens) {
    if (/^\d/.test(tok) || tok in CONSTS || variables.includes(tok)) {
      out.push(tok);
    } else if (tok in FUNCS) {
      ops.push(tok);
    } else if (tok === ",") {
      while (ops.length && ops[ops.length - 1] !== "(") out.push(ops.pop()!);
    } else if ("+-*/^".includes(tok) && tok.length === 1) {
      const op = tok === "-" && (prev === null || ["(", ",", "+", "-", "*", "/", "^"].includes(prev))
        ? "u-" : tok;
      while (ops.length && ops[ops.length - 1] !== "(" && (
        (PREC[ops[ops.length - 1]] ?? 0) > PREC[op] ||
        ((PREC[ops[ops.length - 1]] ?? 0) === PREC[op] && !RIGHT.has(op))
      )) {
        out.push(ops.pop()!);
      }
      ops.push(op);
    } else if (tok === "(") {
      ops.push(tok);
    } else if (tok === ")") {
      while (ops.length && ops[ops.length - 1] !== "(") out.push(ops.pop()!);
      if (ops.length === 0) throw new PlotError(`unbalanced ')' in ${pyRepr(expr)}`);
      ops.pop();
      if (ops.length && ops[ops.length - 1] in FUNCS) out.push(ops.pop()!);
    } else {
      throw new PlotError(`unexpected token ${pyRepr(tok)} in ${pyRepr(expr)}`);
    }
    prev = tok;
  }
  while (ops.length) {
    const top = ops[ops.length - 1];
    if (top === "(" || top === ")") throw new PlotError(`unbalanced parenthesis in ${pyRepr(expr)}`);
    out.push(ops.pop()!);
  }
  return out;
}

function evalRpn(rpn: string[], env: Record<string, number>): number | null {
  const stack: number[] = [];
  try {
    for (const tok of rpn) {
      if (tok in env) {
        stack.push(env[tok]);
      } else if (tok in CONSTS) {
        stack.push(CONSTS[tok]);
      } else if (/^\d/.test(tok)) {
        stack.push(Number(tok));
      } else if (tok === "u-") {
        stack.push(-stack.pop()!);
      } else if (tok in FUNCS) {
        stack.push(FUNCS[tok](stack.pop()!));
      } else {
        const b = stack.pop()!;
        const a = stack.pop()!;
        stack.push(
          tok === "+" ? a + b : tok === "-" ? a - b
          : tok === "*" ? a * b : tok === "/" ? a / b
          : a ** b,
        );
      }
    }
    const v = stack.pop()!;
    return Number.isFinite(v) ? v : null;
  } catch {
    return null;
  }
}

export function makeFunc(expr: string, varr = "x"): Fn1 {
  const rpn = toRpn(expr, varr);
  return (x: number) => evalRpn(rpn, { [varr]: x });
}

export function makeFunc2(expr: string, vx = "x", vy = "y"): Fn2 {
  const rpn = toRpn(expr, [vx, vy]);
  return (x: number, y: number) => evalRpn(rpn, { [vx]: x, [vy]: y });
}

// -- spec model ---------------------------------------------------------------
type Mark = [number, number, string, string]; // x, y, label, color

class PlotSpec {
  mode = "function";
  xr: [number, number] = [-5.0, 5.0];
  xrSet = false;
  yr: [number, number] | null = null;
  funcs: string[] = [];
  marks: Mark[] = [];
  vlines: number[] = [];
  hlines: number[] = [];
  samples = 240;
  grid = false;
  xlabel = "x";
  ylabel = "y";
  paramVar = "t";
  xexpr: string | null = null;
  yexpr: string | null = null;
  rexpr: string | null = null;
  tr: [number, number] = [0.0, 1.0];
  fieldVars: [string, string] = ["x", "y"];
  uexpr: string | null = null;
  vexpr: string | null = null;
  fexpr: string | null = null;
}

const FUNC_RE = /^\w+\s*\(\s*x\s*\)\s*=\s*(.+)$/;
const PARAM_RE = /^([xy])\s*\(\s*([A-Za-z]\w*)\s*\)\s*=\s*(.+)$/;
const POLAR_RE = /^r\s*\(\s*([A-Za-z]\w*)\s*\)\s*=\s*(.+)$/;
const FIELD_RE = /^([uv])\s*\(\s*([A-Za-z]\w*)\s*,\s*([A-Za-z]\w*)\s*\)\s*=\s*(.+)$/;
const IMPLICIT_RE = /^[A-Za-z]\w*\s*\(\s*([A-Za-z]\w*)\s*,\s*([A-Za-z]\w*)\s*\)\s*=\s*(.+)$/;
const MODES = ["function", "parametric", "polar", "vectorfield", "implicit"];

export function parsePlot(source: string): PlotSpec {
  const spec = new PlotSpec();
  // a first pass to pick up `mode:` regardless of line order (last wins, as in Python)
  for (const raw of splitlines(source)) {
    const s = raw.trim();
    if (s.toLowerCase().startsWith("mode:")) spec.mode = s.slice(s.indexOf(":") + 1).trim().toLowerCase();
  }
  if (!MODES.includes(spec.mode)) {
    throw new PlotError(`unknown plot mode ${pyRepr(spec.mode)} (use one of ${MODES.join(", ")})`);
  }
  if (spec.mode === "polar") spec.paramVar = "theta";

  const parser: Record<string, (spec: PlotSpec, line: string) => void> = {
    parametric: parseParametric, polar: parsePolar,
    vectorfield: parseVectorfield, implicit: parseImplicit,
  };
  const parse = parser[spec.mode] ?? parseFunction;
  for (const raw of splitlines(source)) {
    const line = raw.trim();
    if (!line || line.startsWith("#") || line.toLowerCase().startsWith("mode:")) continue;
    parse(spec, line);
  }

  if (spec.mode === "parametric") {
    if (!(spec.xexpr && spec.yexpr)) {
      throw new PlotError("parametric plot needs both 'x(t) = ...' and 'y(t) = ...'");
    }
  } else if (spec.mode === "polar") {
    if (!spec.rexpr) throw new PlotError("polar plot needs 'r(theta) = ...'");
  } else if (spec.mode === "vectorfield") {
    if (!(spec.uexpr && spec.vexpr)) {
      throw new PlotError("vectorfield plot needs both 'u(x,y) = ...' and 'v(x,y) = ...'");
    }
  } else if (spec.mode === "implicit") {
    if (!spec.fexpr) throw new PlotError("implicit plot needs 'F(x,y) = ...' (the curve F = 0)");
  } else if (spec.funcs.length === 0 && spec.marks.length === 0) {
    throw new PlotError("plot needs at least one 'name(x) = ...' or a 'mark:'");
  }
  return spec;
}

function partition(line: string, sep: string): [string, string] {
  const i = line.indexOf(sep);
  if (i < 0) return [line.trim(), ""];
  return [line.slice(0, i).trim(), line.slice(i + sep.length).trim()];
}

function parseCommon(spec: PlotSpec, key: string, val: string): boolean {
  if (key === "mark") spec.marks.push(mark(val));
  else if (key === "vline") spec.vlines.push(numExpr(val));
  else if (key === "hline") spec.hlines.push(numExpr(val));
  else if (key === "samples") spec.samples = Math.max(8, Math.trunc(numExpr(val)));
  else if (key === "grid") spec.grid = ["true", "1", "yes"].includes(val.toLowerCase());
  else if (key === "xlabel") spec.xlabel = unquote(val);
  else if (key === "ylabel") spec.ylabel = unquote(val);
  else return false;
  return true;
}

function parseFunction(spec: PlotSpec, line: string): void {
  const m = FUNC_RE.exec(line);
  if (m) { spec.funcs.push(m[1].trim()); return; }
  const [key, val] = partition(line, ":");
  if (key === "x") { spec.xr = range(val); spec.xrSet = true; }
  else if (key === "y") spec.yr = range(val);
  else if (!parseCommon(spec, key, val)) throw new PlotError(`unknown plot directive ${pyRepr(key)}`);
}

function parseParametric(spec: PlotSpec, line: string): void {
  const m = PARAM_RE.exec(line);
  if (m) {
    const axis = m[1], varr = m[2], expr = m[3].trim();
    spec.paramVar = varr;
    if (axis === "x") spec.xexpr = expr;
    else spec.yexpr = expr;
    return;
  }
  const [key, val] = partition(line, ":");
  if (key === "x") { spec.xr = range(val); spec.xrSet = true; }
  else if (key === "y") spec.yr = range(val);
  else if (parseCommon(spec, key, val)) return;
  else if (val.includes("..")) { spec.paramVar = key; spec.tr = range(val); }
  else throw new PlotError(`unknown plot directive ${pyRepr(key)}`);
}

function parsePolar(spec: PlotSpec, line: string): void {
  const m = POLAR_RE.exec(line);
  if (m) { spec.paramVar = m[1]; spec.rexpr = m[2].trim(); return; }
  const [key, val] = partition(line, ":");
  if (key === "x") { spec.xr = range(val); spec.xrSet = true; }
  else if (key === "y") spec.yr = range(val);
  else if (parseCommon(spec, key, val)) return;
  else if (val.includes("..")) { spec.paramVar = key; spec.tr = range(val); }
  else throw new PlotError(`unknown plot directive ${pyRepr(key)}`);
}

function parseXyOrCommon(spec: PlotSpec, line: string): void {
  const [key, val] = partition(line, ":");
  if (key === "x") { spec.xr = range(val); spec.xrSet = true; }
  else if (key === "y") spec.yr = range(val);
  else if (!parseCommon(spec, key, val)) throw new PlotError(`unknown plot directive ${pyRepr(key)}`);
}

function parseVectorfield(spec: PlotSpec, line: string): void {
  const m = FIELD_RE.exec(line);
  if (m) {
    const comp = m[1], vx = m[2], vy = m[3], expr = m[4].trim();
    spec.fieldVars = [vx, vy];
    if (comp === "u") spec.uexpr = expr;
    else spec.vexpr = expr;
    return;
  }
  parseXyOrCommon(spec, line);
}

function parseImplicit(spec: PlotSpec, line: string): void {
  const m = IMPLICIT_RE.exec(line);
  if (m) { spec.fieldVars = [m[1], m[2]]; spec.fexpr = m[3].trim(); return; }
  parseXyOrCommon(spec, line);
}

function numExpr(s: string): number {
  const v = makeFunc(s.trim())(0.0); // no variable; uses the safe evaluator (pi, e, arithmetic)
  if (v === null) throw new PlotError(`bad number/expression ${pyRepr(s)} in range`);
  return v;
}

function range(s: string): [number, number] {
  if (!s.includes("..")) throw new PlotError(`expected range 'a..b', got ${pyRepr(s)}`);
  const i = s.indexOf("..");
  return [numExpr(s.slice(0, i)), numExpr(s.slice(i + 2))];
}

function unquote(s: string): string {
  const t = s.trim();
  return t.length >= 2 && t[0] === '"' && t[t.length - 1] === '"' ? t.slice(1, -1) : t;
}

function mark(val: string): Mark {
  const m = /\(\s*([-\d.eE]+)\s*,\s*([-\d.eE]+)\s*\)(.*)/.exec(val);
  if (!m) throw new PlotError(`bad mark ${pyRepr(val)}; expected '(x, y) [label="..."] [color=...]'`);
  const rest = m[3];
  const lm = /label\s*=\s*"([^"]*)"/.exec(rest);
  const cm = /color\s*=\s*"?([A-Za-z#][\w#]*)"?/.exec(rest);
  return [Number(m[1]), Number(m[2]), lm ? lm[1] : "", cm ? cm[1] : ""];
}

// -- rendering ----------------------------------------------------------------
const W = 560.0, H = 380.0;
const ML = 44.0, MR = 22.0, MT = 18.0, MB = 36.0;
const DASH: (string | null)[] = [null, "7 5", "2 4", "10 4 2 4"];

const esc = (s: string): string =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

const f0 = (x: number): string => fixed(x, 0);
const f2 = (x: number): string => fixed(x, 2);

function pct(sortedVals: number[], p: number): number {
  const k = (sortedVals.length - 1) * p;
  const f = Math.floor(k);
  const c = Math.ceil(k);
  if (f === c) return sortedVals[Math.trunc(k)];
  return sortedVals[f] * (c - k) + sortedVals[c] * (k - f);
}

function nice(x: number): number {
  if (x <= 0) return 1.0;
  const exp = Math.floor(Math.log10(x));
  const f = x / 10 ** exp;
  const nf = f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10;
  return nf * 10 ** exp;
}

function ticks(lo: number, hi: number): number[] {
  const step = nice((hi - lo) / 6);
  const start = Math.ceil(lo / step) * step;
  const vals: number[] = [];
  let v = start;
  while (v <= hi + step * 1e-6) {
    vals.push(round10(v));
    v += step;
  }
  return vals;
}

// Python round(v, 10): round to 10 decimals; -0 normalised to 0. The value only ever reaches
// output through %g (6 sig figs) or .2f pixels, so this needs only to match to that resolution.
function round10(v: number): number {
  const r = parseFloat(v.toFixed(10));
  return r === 0 ? 0 : r;
}

function text(
  x: number, y: number, runsSrc: string,
  opts: { anchor?: string; baseline?: string; size?: number; italic?: boolean } = {},
): string {
  const { anchor = "middle", baseline = "central", size = 14, italic = false } = opts;
  const inner = subSupSpans(labelRuns(runsSrc), size);
  const style = italic ? ' font-style="italic"' : "";
  return (
    `<text x="${f2(x)}" y="${f2(y)}" text-anchor="${anchor}" dominant-baseline="${baseline}" ` +
    `font-size="${size}"${style}>${inner}</text>`
  );
}

export function compilePlot(source: string): string {
  const spec = parsePlot(source);
  const compilers: Record<string, (spec: PlotSpec) => string> = {
    parametric: compileParametric, polar: compilePolar,
    vectorfield: compileVectorfield, implicit: compileImplicit,
  };
  return (compilers[spec.mode] ?? compileFunction)(spec);
}

type Sx = (x: number) => number;

interface Frame {
  out: string[];
  sx: Sx;
  sy: Sx;
  axX: number;
  axY: number;
}

function renderFrame(spec: PlotSpec, x0: number, x1: number, y0: number, y1: number): Frame {
  const pw = W - ML - MR, ph = H - MT - MB;
  const sx: Sx = (x) => ML + (x - x0) / (x1 - x0) * pw;
  const sy: Sx = (y) => MT + (y1 - y) / (y1 - y0) * ph;

  const out: string[] = [
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${f0(W)} ${f0(H)}" ` +
      `width="${f0(W)}" height="${f0(H)}" fill="currentColor" ` +
      `font-family="Georgia, 'Times New Roman', serif">`,
  ];
  const xt = ticks(x0, x1);
  const yt = ticks(y0, y1);
  if (spec.grid) {
    for (const xv of xt) {
      out.push(`<line x1="${f2(sx(xv))}" y1="${f2(MT)}" x2="${f2(sx(xv))}" y2="${f2(MT + ph)}" stroke="#e6e6e6" stroke-width="1"/>`);
    }
    for (const yv of yt) {
      out.push(`<line x1="${f2(ML)}" y1="${f2(sy(yv))}" x2="${f2(ML + pw)}" y2="${f2(sy(yv))}" stroke="#e6e6e6" stroke-width="1"/>`);
    }
  }

  const axY = y0 <= 0 && 0 <= y1 ? sy(0.0) : (y0 > 0 ? MT + ph : MT);
  const axX = x0 <= 0 && 0 <= x1 ? sx(0.0) : (x0 > 0 ? ML : ML + pw);
  out.push(`<line x1="${f2(ML)}" y1="${f2(axY)}" x2="${f2(ML + pw)}" y2="${f2(axY)}" stroke="currentColor" stroke-width="1.4"/>`);
  out.push(`<line x1="${f2(axX)}" y1="${f2(MT)}" x2="${f2(axX)}" y2="${f2(MT + ph)}" stroke="currentColor" stroke-width="1.4"/>`);

  for (const xv of xt) {
    if (Math.abs(xv) < 1e-9) continue;
    const px = sx(xv);
    out.push(`<line x1="${f2(px)}" y1="${f2(axY - 3)}" x2="${f2(px)}" y2="${f2(axY + 3)}" stroke="currentColor" stroke-width="1.2"/>`);
    out.push(text(px, axY + 13, pyG(xv), { size: 12 }));
  }
  for (const yv of yt) {
    if (Math.abs(yv) < 1e-9) continue;
    const py = sy(yv);
    out.push(`<line x1="${f2(axX - 3)}" y1="${f2(py)}" x2="${f2(axX + 3)}" y2="${f2(py)}" stroke="currentColor" stroke-width="1.2"/>`);
    out.push(text(axX - 8, py, pyG(yv), { anchor: "end", size: 12 }));
  }

  for (const xv of spec.vlines) {
    out.push(`<line x1="${f2(sx(xv))}" y1="${f2(MT)}" x2="${f2(sx(xv))}" y2="${f2(MT + ph)}" stroke="#888" stroke-width="1" stroke-dasharray="5 4"/>`);
  }
  for (const yv of spec.hlines) {
    out.push(`<line x1="${f2(ML)}" y1="${f2(sy(yv))}" x2="${f2(ML + pw)}" y2="${f2(sy(yv))}" stroke="#888" stroke-width="1" stroke-dasharray="5 4"/>`);
  }

  return { out, sx, sy, axX, axY };
}

function closeFrame(fr: Frame, spec: PlotSpec): string {
  const pw = W - ML - MR, ph = H - MT - MB;
  const { out, sx, sy, axX, axY } = fr;
  for (const [mx, my, label, colr] of spec.marks) {
    out.push(`<circle cx="${f2(sx(mx))}" cy="${f2(sy(my))}" r="3.4" fill="${colr || "currentColor"}"/>`);
    if (label) out.push(text(sx(mx) + 8, sy(my) - 8, label, { anchor: "start", size: 14, italic: true }));
  }
  out.push(text(ML + pw, axY - 10, spec.xlabel, { anchor: "end", size: 15, italic: true }));
  out.push(text(axX + 12, MT + 2, spec.ylabel, { anchor: "start", size: 15, italic: true }));
  out.push("</svg>");
  return out.join("\n");
}

function compileFunction(spec: PlotSpec): string {
  const funcs = spec.funcs.map((e) => makeFunc(e));
  const [x0, x1] = spec.xr;
  if (x1 <= x0) throw new PlotError("x domain must have a < b");

  const n = spec.samples;
  const xs: number[] = [];
  for (let i = 0; i <= n; i++) xs.push(x0 + (x1 - x0) * i / n);
  const sampled: (number | null)[][] = funcs.map((f) => xs.map((x) => f(x)));

  let y0: number, y1: number;
  if (spec.yr) {
    [y0, y1] = spec.yr;
  } else {
    const finite = sampled.flat().filter((v): v is number => v !== null).sort((a, b) => a - b);
    if (finite.length) {
      const loF = finite[0], hiF = finite[finite.length - 1];
      const loR = pct(finite, 0.02), hiR = pct(finite, 0.98);
      if (hiR > loR && (hiF - loF) > 4 * (hiR - loR)) {
        y0 = loR; y1 = hiR;
      } else {
        y0 = loF; y1 = hiF;
      }
      for (const [, my] of spec.marks) { y0 = Math.min(y0, my); y1 = Math.max(y1, my); }
      const pad = (y1 - y0) * 0.08 || 1.0;
      y0 -= pad; y1 += pad;
    } else {
      y0 = -1.0; y1 = 1.0;
    }
  }
  if (y1 <= y0) y1 = y0 + 1.0;

  const fr = renderFrame(spec, x0, x1, y0, y1);
  const { out, sx, sy } = fr;

  sampled.forEach((col, idx) => {
    const dash = DASH[idx % DASH.length];
    const dattr = dash ? ` stroke-dasharray="${dash}"` : "";
    let seg: string[] = [];
    let prevY: number | null = null;
    for (let i = 0; i < xs.length; i++) {
      const x = xs[i], y = col[i];
      const broken = y === null || (prevY !== null && Math.abs(y - prevY) > (y1 - y0) * 4);
      if (broken) { flushPoly(out, seg, dattr); seg = []; }
      if (y !== null && y0 - (y1 - y0) * 2 <= y && y <= y1 + (y1 - y0) * 2) {
        seg.push(`${f2(sx(x))},${f2(sy(Math.max(Math.min(y, y1 + (y1 - y0)), y0 - (y1 - y0))))}`);
      }
      prevY = y;
    }
    flushPoly(out, seg, dattr);
  });

  return closeFrame(fr, spec);
}

function equalAspect(x0: number, x1: number, y0: number, y1: number): [number, number, number, number] {
  const pw = W - ML - MR, ph = H - MT - MB;
  const scale = Math.max((x1 - x0) / pw, (y1 - y0) / ph);
  const tw = scale * pw, th = scale * ph;
  const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
  return [cx - tw / 2, cx + tw / 2, cy - th / 2, cy + th / 2];
}

function sampleParam(spec: PlotSpec): ([number, number] | null)[] {
  const [t0, t1] = spec.tr;
  if (t1 <= t0) throw new PlotError("parameter range must have a < b (e.g. 't: 0..10')");
  const n = spec.samples;
  if (spec.mode === "polar") {
    const fr = makeFunc(spec.rexpr!, spec.paramVar);
    const pts: ([number, number] | null)[] = [];
    for (let i = 0; i <= n; i++) {
      const th = t0 + (t1 - t0) * i / n;
      const r = fr(th);
      pts.push(r !== null ? [r * Math.cos(th), r * Math.sin(th)] : null);
    }
    return pts;
  }
  const fx = makeFunc(spec.xexpr!, spec.paramVar);
  const fy = makeFunc(spec.yexpr!, spec.paramVar);
  const pts: ([number, number] | null)[] = [];
  for (let i = 0; i <= n; i++) {
    const t = t0 + (t1 - t0) * i / n;
    const xv = fx(t), yv = fy(t);
    pts.push(xv !== null && yv !== null ? [xv, yv] : null);
  }
  return pts;
}

function renderTrajectory(spec: PlotSpec, pts: ([number, number] | null)[], what: string): string {
  const finite = pts.filter((p): p is [number, number] => p !== null);
  if (!finite.length) {
    throw new PlotError(`${what} produced no finite points; check the expression(s) and the range`);
  }

  const explicit = spec.xrSet || spec.yr !== null;
  let x0: number, x1: number, y0: number, y1: number;
  if (spec.xrSet) {
    [x0, x1] = spec.xr;
  } else {
    const xv = finite.map((p) => p[0]);
    x0 = Math.min(...xv); x1 = Math.max(...xv);
  }
  if (spec.yr !== null) {
    [y0, y1] = spec.yr;
  } else {
    const yv = finite.map((p) => p[1]);
    y0 = Math.min(...yv); y1 = Math.max(...yv);
  }
  for (const [mx, my] of spec.marks) {
    x0 = Math.min(x0, mx); x1 = Math.max(x1, mx); y0 = Math.min(y0, my); y1 = Math.max(y1, my);
  }
  if (x1 <= x0) { x0 -= 1; x1 += 1; }
  if (y1 <= y0) { y0 -= 1; y1 += 1; }
  if (!explicit) {
    [x0, x1, y0, y1] = equalAspect(x0, x1, y0, y1);
    const padx = (x1 - x0) * 0.06, pady = (y1 - y0) * 0.06;
    x0 -= padx; x1 += padx; y0 -= pady; y1 += pady;
  }

  const fr = renderFrame(spec, x0, x1, y0, y1);
  const { out, sx, sy } = fr;
  let seg: string[] = [];
  for (const p of pts) {
    if (p === null) { flushPoly(out, seg, ""); seg = []; }
    else seg.push(`${f2(sx(p[0]))},${f2(sy(p[1]))}`);
  }
  flushPoly(out, seg, "");
  return closeFrame(fr, spec);
}

function compileParametric(spec: PlotSpec): string {
  return renderTrajectory(spec, sampleParam(spec), "parametric plot");
}

function compilePolar(spec: PlotSpec): string {
  return renderTrajectory(spec, sampleParam(spec), "polar plot");
}

function flushPoly(out: string[], seg: string[], dattr: string): void {
  if (seg.length >= 2) {
    out.push(
      `<polyline points="${seg.join(" ")}" fill="none" stroke="currentColor" ` +
      `stroke-width="2" stroke-linejoin="round" stroke-linecap="round"${dattr}/>`,
    );
  }
}

function arrowSvg(p1: [number, number], p2: [number, number], colr = "currentColor", w = 1.2, head = 5.0): string {
  const dx = p2[0] - p1[0], dy = p2[1] - p1[1];
  const n = Math.hypot(dx, dy);
  if (n < 1e-6) return "";
  const ux = dx / n, uy = dy / n;
  const px = -uy, py = ux;
  const bx = p2[0] - ux * head, by = p2[1] - uy * head;
  const lx = bx + px * head * 0.5, ly = by + py * head * 0.5;
  const rx = bx - px * head * 0.5, ry = by - py * head * 0.5;
  return (
    `<line x1="${f2(p1[0])}" y1="${f2(p1[1])}" x2="${f2(p2[0])}" y2="${f2(p2[1])}" ` +
    `stroke="${colr}" stroke-width="${w}"/>` +
    `<polygon points="${f2(p2[0])},${f2(p2[1])} ${f2(lx)},${f2(ly)} ${f2(rx)},${f2(ry)}" fill="${colr}"/>`
  );
}

function xyDomain(spec: PlotSpec): [number, number, number, number] {
  const [x0, x1] = spec.xr;
  const [y0, y1] = spec.yr !== null ? spec.yr : spec.xr; // default to a square domain
  if (x1 <= x0 || y1 <= y0) throw new PlotError("x and y domains must each have a < b (e.g. 'x: -2..2')");
  return [x0, x1, y0, y1];
}

function compileVectorfield(spec: PlotSpec): string {
  const [vx, vy] = spec.fieldVars;
  const fu = makeFunc2(spec.uexpr!, vx, vy), fv = makeFunc2(spec.vexpr!, vx, vy);
  const [x0, x1, y0, y1] = equalAspect(...xyDomain(spec));
  const fr = renderFrame(spec, x0, x1, y0, y1);
  const { out, sx, sy } = fr;

  const n = 11; // arrows per axis
  const cellx = (x1 - x0) / (n - 1), celly = (y1 - y0) / (n - 1);
  const samples: [number, number, number, number, number][] = [];
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) {
      const x = x0 + cellx * i, y = y0 + celly * j;
      const u = fu(x, y), v = fv(x, y);
      if (u === null || v === null) continue;
      samples.push([x, y, u, v, Math.hypot(u, v)]);
    }
  }

  const mags = samples.map((s) => s[4]).filter((m) => m > 0).sort((a, b) => a - b);
  const scale = mags.length ? mags[Math.floor(mags.length / 2)] : 1.0;
  const L = 0.9 * Math.min(cellx, celly);
  for (const [x, y, u, v, mag] of samples) {
    if (mag < 1e-12) continue;
    const f = L * mag / (mag + scale) / mag;
    const ex = x + u * f, ey = y + v * f;
    out.push(arrowSvg([sx(x), sy(y)], [sx(ex), sy(ey)]));
  }
  return closeFrame(fr, spec);
}

function compileImplicit(spec: PlotSpec): string {
  const [vx, vy] = spec.fieldVars;
  const F = makeFunc2(spec.fexpr!, vx, vy);
  const [x0, x1, y0, y1] = equalAspect(...xyDomain(spec));
  const fr = renderFrame(spec, x0, x1, y0, y1);
  const { out, sx, sy } = fr;

  const n = Math.max(20, Math.min(Math.trunc((spec.samples || 240) / 4), 120));
  const xs: number[] = [], ys: number[] = [];
  for (let i = 0; i <= n; i++) xs.push(x0 + (x1 - x0) * i / n);
  for (let j = 0; j <= n; j++) ys.push(y0 + (y1 - y0) * j / n);
  const vals = xs.map((x) => ys.map((y) => F(x, y)));

  const cross = (
    pa: [number, number], pb: [number, number], fa: number, fb: number,
  ): [number, number] => {
    const t = fa / (fa - fb);
    return [pa[0] + (pb[0] - pa[0]) * t, pa[1] + (pb[1] - pa[1]) * t];
  };

  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) {
      const corners: [[number, number], number | null][] = [
        [[xs[i], ys[j]], vals[i][j]],
        [[xs[i + 1], ys[j]], vals[i + 1][j]],
        [[xs[i + 1], ys[j + 1]], vals[i + 1][j + 1]],
        [[xs[i], ys[j + 1]], vals[i][j + 1]],
      ];
      if (corners.some(([, val]) => val === null)) continue;
      const hits: [number, number][] = [];
      for (let k = 0; k < 4; k++) {
        const [pa, fa] = corners[k] as [[number, number], number];
        const [pb, fb] = corners[(k + 1) % 4] as [[number, number], number];
        if ((fa <= 0) !== (fb <= 0) && fa !== fb) hits.push(cross(pa, pb, fa, fb));
      }
      let pairs: [[number, number], [number, number]][] = [];
      if (hits.length === 2) pairs = [[hits[0], hits[1]]];
      else if (hits.length === 4) pairs = [[hits[0], hits[1]], [hits[2], hits[3]]];
      for (const [a, b] of pairs) {
        out.push(
          `<line x1="${f2(sx(a[0]))}" y1="${f2(sy(a[1]))}" ` +
          `x2="${f2(sx(b[0]))}" y2="${f2(sy(b[1]))}" stroke="currentColor" ` +
          `stroke-width="2" stroke-linecap="round"/>`,
        );
      }
    }
  }
  return closeFrame(fr, spec);
}

function splitlines(s: string): string[] {
  if (s === "") return [];
  const parts = s.split(/\r\n|\r|\n/);
  if (parts.length && parts[parts.length - 1] === "") parts.pop();
  return parts;
}

// Python repr() for the strings used in error messages.
function pyRepr(s: string): string {
  if (s.includes("'") && !s.includes('"')) return `"${s}"`;
  return `'${s.replace(/\\/g, "\\\\").replace(/'/g, "\\'")}'`;
}
