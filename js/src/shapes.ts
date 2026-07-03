// Geometry primitives + the SVG scene. A faithful port of python/src/mtph/diagram/shapes.py.
//
// Everything is built in logical coordinates with y pointing up (math convention). The Scene
// computes a bounding box, then maps logical units to pixels (flipping y) and emits a
// self-contained <svg> with a fitted viewBox. Stroke widths and font sizes are in pixels so
// weights stay consistent regardless of the figure's logical size.

import { labelRuns, subSupSpans } from "./latex.js";
import { fixed } from "./pyfmt.js";

export type Pt = [number, number];

export const SCALE = 62.0; // pixels per logical unit
export const PAD = 26.0; // pixel padding around content
export const W_NORMAL = 2.0;
export const W_THIN = 1.3;
export const W_THICK = 3.0;
export const FONT = 18.0; // label font size (px)

// Default "ink" is currentColor so figures inherit the page's text colour. PAPER is the opaque
// "knock-out" fill (lens bodies, bobs, label halos): white standalone, themed on a dark page.
export const INK = "currentColor";
export const PAPER = "#ffffff";

const _COLORS: Record<string, string> = {
  none: "none", black: "#111111", white: PAPER,
  gray: "#888888", grey: "#888888", lightgray: "#cccccc",
  lightgrey: "#cccccc",
};

export function color(name: string | null | undefined, def: string = INK): string {
  if (name === null || name === undefined) return def;
  return name in _COLORS ? _COLORS[name] : name;
}

// -- small vector helpers -----------------------------------------------------
export const add = (a: Pt, b: Pt): Pt => [a[0] + b[0], a[1] + b[1]];
export const sub = (a: Pt, b: Pt): Pt => [a[0] - b[0], a[1] - b[1]];
export const mul = (a: Pt, s: number): Pt => [a[0] * s, a[1] * s];
export const length = (a: Pt): number => Math.hypot(a[0], a[1]);
export const unit = (a: Pt): Pt => {
  const n = length(a);
  return n === 0 ? [0.0, 0.0] : [a[0] / n, a[1] / n];
};
export const rot = (a: Pt, deg: number): Pt => {
  const r = (deg * Math.PI) / 180;
  const c = Math.cos(r), s = Math.sin(r);
  return [a[0] * c - a[1] * s, a[0] * s + a[1] * c];
};
export const midpoint = (a: Pt, b: Pt): Pt => [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];

const esc = (s: string): string =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

// Canonical number string (integer-valued → no decimals), so Python and JS emit identical SVG.
// JS String() already collapses 2.0 → "2" while keeping 1.3 → "1.3", matching Python's _num().
const numStr = (x: number): string => String(x);

// Fixed-decimal formatters matching Python f-string specifiers (round half-to-even).
const f0 = (x: number): string => fixed(x, 0);
const f1 = (x: number): string => fixed(x, 1);
const f2 = (x: number): string => fixed(x, 2);
// Like f2 but normalises "-0.00" → "0.00", for animation coordinates where negation and zero
// components can produce a signed zero (matches Python's _f2 — keeps the emitted SVG identical).
const f2n = (x: number): string => { const s = fixed(x, 2); return s === "-0.00" ? "0.00" : s; };

// Reusable fill patterns (hatch / crosshatch / dots), emitted only when referenced.
const PATTERN_DEFS =
  "<defs>" +
  '<pattern id="mtph-hatch" patternUnits="userSpaceOnUse" width="6" height="6">' +
  '<path d="M0,6 L6,0" stroke="currentColor" stroke-width="0.7"/></pattern>' +
  '<pattern id="mtph-crosshatch" patternUnits="userSpaceOnUse" width="6" height="6">' +
  '<path d="M0,0 L6,6 M0,6 L6,0" stroke="currentColor" stroke-width="0.6" fill="none"/></pattern>' +
  '<pattern id="mtph-dots" patternUnits="userSpaceOnUse" width="6" height="6">' +
  '<circle cx="3" cy="3" r="1" fill="currentColor"/></pattern>' +
  "</defs>";

// -- primitives ---------------------------------------------------------------
export class Line {
  p1: Pt; p2: Pt;
  width: number; stroke: string; dash: string | null;
  arrow: boolean; arrow_start: boolean;
  constructor(p1: Pt, p2: Pt, opts: Partial<Omit<Line, "p1" | "p2">> = {}) {
    this.p1 = p1; this.p2 = p2;
    this.width = opts.width ?? W_NORMAL;
    this.stroke = opts.stroke ?? INK;
    this.dash = opts.dash ?? null;
    this.arrow = opts.arrow ?? false;
    this.arrow_start = opts.arrow_start ?? false;
  }
}

export class Path {
  points: Pt[];
  closed: boolean; width: number; stroke: string; fill: string; dash: string | null;
  constructor(points: Pt[], opts: Partial<Omit<Path, "points">> = {}) {
    this.points = points;
    this.closed = opts.closed ?? false;
    this.width = opts.width ?? W_NORMAL;
    this.stroke = opts.stroke ?? INK;
    this.fill = opts.fill ?? "none";
    this.dash = opts.dash ?? null;
  }
}

export class Circle {
  c: Pt; r: number;
  width: number; stroke: string; fill: string; dash: string | null;
  constructor(c: Pt, r: number, opts: Partial<Omit<Circle, "c" | "r">> = {}) {
    this.c = c; this.r = r;
    this.width = opts.width ?? W_NORMAL;
    this.stroke = opts.stroke ?? INK;
    this.fill = opts.fill ?? "none";
    this.dash = opts.dash ?? null;
  }
}

export class Ellipse {
  c: Pt; rx: number; ry: number;
  angle: number; width: number; stroke: string; fill: string; dash: string | null;
  constructor(c: Pt, rx: number, ry: number, opts: Partial<Omit<Ellipse, "c" | "rx" | "ry">> = {}) {
    this.c = c; this.rx = rx; this.ry = ry;
    this.angle = opts.angle ?? 0.0;
    this.width = opts.width ?? W_NORMAL;
    this.stroke = opts.stroke ?? INK;
    this.fill = opts.fill ?? "none";
    this.dash = opts.dash ?? null;
  }
}

// A general path: segments of ('M'|'L', [pt]), ('C', [c1,c2,end]), ('Q', [c,end]), ('Z', []).
export type BezSeg = [string, Pt[]];

export class BezPath {
  segments: BezSeg[];
  width: number; stroke: string; fill: string; dash: string | null; arrow: boolean;
  constructor(segments: BezSeg[], opts: Partial<Omit<BezPath, "segments">> = {}) {
    this.segments = segments;
    this.width = opts.width ?? W_NORMAL;
    this.stroke = opts.stroke ?? INK;
    this.fill = opts.fill ?? "none";
    this.dash = opts.dash ?? null;
    this.arrow = opts.arrow ?? false;
  }
}

export class Text {
  pos: Pt; raw: string;
  anchor: string; baseline: string; ox: number; oy: number; size: number; fill: string;
  constructor(pos: Pt, raw: string, opts: Partial<Omit<Text, "pos" | "raw">> = {}) {
    this.pos = pos; this.raw = raw;
    this.anchor = opts.anchor ?? "middle";
    this.baseline = opts.baseline ?? "middle";
    this.ox = opts.ox ?? 0.0;
    this.oy = opts.oy ?? 0.0;
    this.size = opts.size ?? FONT;
    this.fill = opts.fill ?? INK;
  }
}

/** A micro-animation over a contiguous run of primitives (one command's output), emitted as SMIL
 *  wrapping that run in a <g>. Mirrors Python's Anim. Three verbs: spin / oscillate / along. */
export class Anim {
  kind: string;
  start: number;
  end: number;
  period: number;
  center: Pt | null = null;
  cw = false;
  swing = 0.0;
  amp = 0.5;
  direction = 0.0;
  path: Pt[] | null = null;
  constructor(kind: string, start: number, end: number, period = 3.0) {
    this.kind = kind; this.start = start; this.end = end; this.period = period;
  }
}

export type Prim = Line | Path | Circle | Ellipse | BezPath | Text;
export type BBox = [number, number, number, number];

/** Logical bounding box (minx, miny, maxx, maxy) of a single primitive (null if empty). */
export function primBbox(pr: Prim): BBox | null {
  const xs: number[] = [];
  const ys: number[] = [];
  const inc = (p: Pt) => { xs.push(p[0]); ys.push(p[1]); };

  if (pr instanceof Line) {
    inc(pr.p1); inc(pr.p2);
  } else if (pr instanceof Path) {
    for (const p of pr.points) inc(p);
  } else if (pr instanceof Circle) {
    inc([pr.c[0] - pr.r, pr.c[1] - pr.r]);
    inc([pr.c[0] + pr.r, pr.c[1] + pr.r]);
  } else if (pr instanceof Ellipse) {
    const rr = Math.max(pr.rx, pr.ry);
    inc([pr.c[0] - rr, pr.c[1] - rr]);
    inc([pr.c[0] + rr, pr.c[1] + rr]);
  } else if (pr instanceof BezPath) {
    for (const [, pts] of pr.segments) for (const p of pts) inc(p);
  } else if (pr instanceof Text) {
    const sizeL = pr.size / SCALE;
    const plain = labelRuns(pr.raw).reduce((acc, [t]) => acc + t.length, 0) || 1;
    const half = 0.32 * sizeL * plain;
    const cx = pr.pos[0] + pr.ox / SCALE;
    const cy = pr.pos[1] - pr.oy / SCALE;
    if (pr.anchor === "start") {
      xs.push(cx, cx + 2 * half);
    } else if (pr.anchor === "end") {
      xs.push(cx - 2 * half, cx);
    } else {
      xs.push(cx - half, cx + half);
    }
    ys.push(cy - sizeL, cy + sizeL);
  }
  if (xs.length === 0) return null;
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
}

type Tx = (x: number) => number;

export class Scene {
  prims: Prim[] = [];
  anims: Anim[] = [];

  // add helpers -------------------------------------------------------------
  line(p1: Pt, p2: Pt, opts: Partial<Omit<Line, "p1" | "p2">> = {}): void {
    this.prims.push(new Line(p1, p2, opts));
  }
  path(points: Pt[], opts: Partial<Omit<Path, "points">> = {}): void {
    this.prims.push(new Path([...points], opts));
  }
  circle(c: Pt, r: number, opts: Partial<Omit<Circle, "c" | "r">> = {}): void {
    this.prims.push(new Circle(c, r, opts));
  }
  ellipse(c: Pt, rx: number, ry: number, opts: Partial<Omit<Ellipse, "c" | "rx" | "ry">> = {}): void {
    this.prims.push(new Ellipse(c, rx, ry, opts));
  }
  bezier(segments: BezSeg[], opts: Partial<Omit<BezPath, "segments">> = {}): void {
    this.prims.push(new BezPath([...segments], opts));
  }

  /** Circular arc from angle a0 to a1 (degrees, ccw), sampled as a polyline. */
  arc(c: Pt, r: number, a0: number, a1: number, opts: { width?: number; stroke?: string } = {}): void {
    const width = opts.width ?? W_NORMAL;
    const stroke = opts.stroke ?? INK;
    const steps = Math.max(8, Math.trunc(Math.abs(a1 - a0) / 6));
    const pts: Pt[] = [];
    for (let i = 0; i <= steps; i++) {
      const ang = ((a0 + ((a1 - a0) * i) / steps) * Math.PI) / 180;
      pts.push([c[0] + r * Math.cos(ang), c[1] + r * Math.sin(ang)]);
    }
    this.prims.push(new Path(pts, { width, stroke, fill: "none" }));
  }

  text(pos: Pt, raw: string, opts: Partial<Omit<Text, "pos" | "raw">> = {}): void {
    this.prims.push(new Text(pos, raw, opts));
  }

  animate(anim: Anim): void {
    this.anims.push(anim);
  }

  /** Logical bbox of the primitive run prims[start:end] (null if it drew nothing). */
  groupBbox(start: number, end: number): BBox | null {
    const xs: number[] = [];
    const ys: number[] = [];
    for (const pr of this.prims.slice(start, end)) {
      const bb = primBbox(pr);
      if (bb) { xs.push(bb[0], bb[2]); ys.push(bb[1], bb[3]); }
    }
    if (xs.length === 0) return null;
    return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
  }

  /** The logical region an animation can sweep into, so the viewBox never clips it. */
  private animBbox(a: Anim): BBox | null {
    const base = this.groupBbox(a.start, a.end);
    if (!base) return null;
    const [minx, miny, maxx, maxy] = base;
    if (a.kind === "spin") {
      const [cx, cy] = a.center ?? [(minx + maxx) / 2, (miny + maxy) / 2];
      const corners: Pt[] = [[minx, miny], [minx, maxy], [maxx, miny], [maxx, maxy]];
      if (a.swing > 0) { // a swing sweeps only ±swing/2 — bound it by the two extremes
        const hs = a.swing / 2;
        const xs: number[] = [];
        const ys: number[] = [];
        for (const deg of [-hs, 0.0, hs]) {
          for (const [x, y] of corners) {
            const [rx, ry] = rot([x - cx, y - cy], deg);
            xs.push(cx + rx); ys.push(cy + ry);
          }
        }
        return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
      }
      const r = Math.max(...corners.map(([x, y]) => Math.hypot(x - cx, y - cy)));
      return [cx - r, cy - r, cx + r, cy + r];
    }
    if (a.kind === "oscillate") {
      const dx = a.amp * Math.abs(Math.cos((a.direction * Math.PI) / 180));
      const dy = a.amp * Math.abs(Math.sin((a.direction * Math.PI) / 180));
      return [minx - dx, miny - dy, maxx + dx, maxy + dy];
    }
    if (a.kind === "along" && a.path) {
      const [x0, y0] = a.path[0];
      const offs = a.path.map(([x, y]): Pt => [x - x0, y - y0]);
      const loX = Math.min(...offs.map((o) => o[0]));
      const hiX = Math.max(...offs.map((o) => o[0]));
      const loY = Math.min(...offs.map((o) => o[1]));
      const hiY = Math.max(...offs.map((o) => o[1]));
      return [minx + loX, miny + loY, maxx + hiX, maxy + hiY];
    }
    return base;
  }

  /** Push overlapping text labels apart (opt-in). Mutates label positions only. Returns moved count. */
  nudgeLabels(iters = 25, margin = 0.05): number {
    const texts = this.prims.filter((pr): pr is Text => pr instanceof Text);
    const moved = new Set<Text>();
    for (let it = 0; it < iters; it++) {
      let anyMove = false;
      for (let i = 0; i < texts.length; i++) {
        for (let j = i + 1; j < texts.length; j++) {
          const a = texts[i], b = texts[j];
          const ba = primBbox(a), bb = primBbox(b);
          if (!ba || !bb) continue;
          const ix = Math.min(ba[2], bb[2]) - Math.max(ba[0], bb[0]);
          const iy = Math.min(ba[3], bb[3]) - Math.max(ba[1], bb[1]);
          if (ix <= margin || iy <= margin) continue; // not overlapping
          const ca: Pt = [(ba[0] + ba[2]) / 2, (ba[1] + ba[3]) / 2];
          const cb: Pt = [(bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2];
          const d = sub(cb, ca);
          const n = length(d);
          const push = Math.min(ix, iy) / 2 + margin;
          const u: Pt = n > 1e-6 ? [d[0] / n, d[1] / n] : [1.0, 0.0];
          a.pos = [a.pos[0] - u[0] * push, a.pos[1] - u[1] * push];
          b.pos = [b.pos[0] + u[0] * push, b.pos[1] + u[1] * push];
          moved.add(a);
          moved.add(b);
          anyMove = true;
        }
      }
      if (!anyMove) break;
    }
    return moved.size;
  }

  // bbox --------------------------------------------------------------------
  private bbox(): BBox {
    const xs: number[] = [];
    const ys: number[] = [];
    for (const pr of this.prims) {
      const bb = primBbox(pr);
      if (bb) {
        xs.push(bb[0], bb[2]);
        ys.push(bb[1], bb[3]);
      }
    }
    for (const a of this.anims) { // include the region each animation sweeps, so it never clips
      const ab = this.animBbox(a);
      if (ab) { xs.push(ab[0], ab[2]); ys.push(ab[1], ab[3]); }
    }
    if (xs.length === 0) return [0.0, 0.0, 1.0, 1.0];
    return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
  }

  // emit --------------------------------------------------------------------
  toSvg(title: string | null = null, grid = false): string {
    const [minx, miny, maxx, maxy] = this.bbox();
    let w = (maxx - minx) * SCALE + 2 * PAD;
    let h = (maxy - miny) * SCALE + 2 * PAD;
    w = Math.max(w, 2 * PAD + 1);
    h = Math.max(h, 2 * PAD + 1);

    const tx: Tx = (x) => PAD + (x - minx) * SCALE;
    const ty: Tx = (y) => PAD + (maxy - y) * SCALE;

    const out: string[] = [
      `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${f1(w)} ${f1(h)}" ` +
        `width="${f0(w)}" height="${f0(h)}" font-family="Georgia, 'Times New Roman', serif">`,
    ];
    if (title) out.push(`<title>${esc(title)}</title>`);
    if (this.prims.some(
      (pr) => typeof (pr as { fill?: unknown }).fill === "string" &&
        ((pr as { fill: string }).fill).startsWith("url("),
    )) {
      out.push(PATTERN_DEFS);
    }
    if (grid) out.push(Scene.emitGrid(minx, miny, maxx, maxy, tx, ty));

    // Emit primitives in order; an animated run is wrapped in a <g> that carries its SMIL.
    const animAt = new Map<number, Anim>();
    for (const a of this.anims) if (a.end > a.start) animAt.set(a.start, a);
    let i = 0;
    const n = this.prims.length;
    while (i < n) {
      const a = animAt.get(i);
      if (a) {
        out.push("<g>");
        for (let j = a.start; j < a.end; j++) out.push(this.emitPrim(this.prims[j], tx, ty));
        out.push(this.emitAnim(a, tx, ty));
        out.push("</g>");
        i = a.end;
      } else {
        out.push(this.emitPrim(this.prims[i], tx, ty));
        i += 1;
      }
    }
    out.push("</svg>");
    return out.join("\n");
  }

  private emitPrim(pr: Prim, tx: Tx, ty: Tx): string {
    if (pr instanceof Line) return this.emitLine(pr, tx, ty);
    if (pr instanceof Path) return this.emitPath(pr, tx, ty);
    if (pr instanceof Circle) return this.emitCircle(pr, tx, ty);
    if (pr instanceof Ellipse) return this.emitEllipse(pr, tx, ty);
    if (pr instanceof BezPath) return this.emitBezpath(pr, tx, ty);
    if (pr instanceof Text) return this.emitText(pr, tx, ty);
    return "";
  }

  /** The SMIL element for one animation (a child of the wrapping <g>). Mirrors Python _emit_anim. */
  private emitAnim(a: Anim, tx: Tx, ty: Tx): string {
    if (a.kind === "spin") {
      const base = this.groupBbox(a.start, a.end);
      let cx: number, cy: number;
      if (a.center) { [cx, cy] = a.center; }
      else if (base) { cx = (base[0] + base[2]) / 2; cy = (base[1] + base[3]) / 2; }
      else { cx = 0.0; cy = 0.0; }
      const px = tx(cx), py = ty(cy);
      if (a.swing > 0) {
        const hs = a.swing / 2;
        const c = `${f2n(px)} ${f2n(py)}`;
        const vals =
          `0 ${c};${numStr(-hs)} ${c};0 ${c};${numStr(hs)} ${c};0 ${c}`;
        const ks = "0.42 0 0.58 1;0.42 0 0.58 1;0.42 0 0.58 1;0.42 0 0.58 1";
        return (
          `<animateTransform attributeName="transform" attributeType="XML" type="rotate" ` +
          `values="${vals}" keyTimes="0;0.25;0.5;0.75;1" calcMode="spline" ` +
          `keySplines="${ks}" dur="${numStr(a.period)}s" repeatCount="indefinite"/>`
        );
      }
      const deg = a.cw ? 360 : -360; // SVG +angle is clockwise (y flipped), so ccw = -360
      return (
        `<animateTransform attributeName="transform" attributeType="XML" type="rotate" ` +
        `from="0 ${f2n(px)} ${f2n(py)}" to="${deg} ${f2n(px)} ${f2n(py)}" ` +
        `dur="${numStr(a.period)}s" repeatCount="indefinite"/>`
      );
    }
    if (a.kind === "oscillate") {
      const rad = (a.direction * Math.PI) / 180;
      const ex = a.amp * SCALE * Math.cos(rad);
      const ey = -a.amp * SCALE * Math.sin(rad);
      const vals = `0 0;${f2n(ex)} ${f2n(ey)};0 0;${f2n(-ex)} ${f2n(-ey)};0 0`;
      const ks = "0.42 0 0.58 1;0.42 0 0.58 1;0.42 0 0.58 1;0.42 0 0.58 1";
      return (
        `<animateTransform attributeName="transform" attributeType="XML" type="translate" ` +
        `values="${vals}" keyTimes="0;0.25;0.5;0.75;1" calcMode="spline" ` +
        `keySplines="${ks}" dur="${numStr(a.period)}s" repeatCount="indefinite"/>`
      );
    }
    if (a.kind === "along" && a.path) {
      const [x0, y0] = a.path[0];
      const d = a.path
        .map(([x, y], k) => (k === 0 ? "M 0 0" : `L ${f2n((x - x0) * SCALE)} ${f2n(-(y - y0) * SCALE)}`))
        .join(" ");
      return `<animateMotion path="${d}" dur="${numStr(a.period)}s" repeatCount="indefinite"/>`;
    }
    return "";
  }

  private static emitGrid(
    minx: number, miny: number, maxx: number, maxy: number, tx: Tx, ty: Tx,
  ): string {
    const parts: string[] = ['<g class="mtph-grid">'];
    const xLo = Math.floor(minx), xHi = Math.ceil(maxx);
    const yLo = Math.floor(miny), yHi = Math.ceil(maxy);
    for (let gx = xLo; gx <= xHi; gx++) {
      const x = tx(gx);
      const stroke = gx === 0 ? "#d4d4d4" : "#ededed";
      parts.push(
        `<line x1="${f1(x)}" y1="${f1(ty(maxy))}" x2="${f1(x)}" ` +
          `y2="${f1(ty(miny))}" stroke="${stroke}" stroke-width="1"/>`,
      );
      parts.push(
        `<text x="${f1(x)}" y="${f1(ty(miny) + 11)}" text-anchor="middle" ` +
          `font-size="9" fill="#b0b0b0">${gx}</text>`,
      );
    }
    for (let gy = yLo; gy <= yHi; gy++) {
      const y = ty(gy);
      const stroke = gy === 0 ? "#d4d4d4" : "#ededed";
      parts.push(
        `<line x1="${f1(tx(minx))}" y1="${f1(y)}" x2="${f1(tx(maxx))}" ` +
          `y2="${f1(y)}" stroke="${stroke}" stroke-width="1"/>`,
      );
      parts.push(
        `<text x="${f1(tx(minx) - 4)}" y="${f1(y + 3)}" text-anchor="end" ` +
          `font-size="9" fill="#b0b0b0">${gy}</text>`,
      );
    }
    parts.push("</g>");
    return parts.join("");
  }

  // -- per-primitive emitters ----------------------------------------------
  private static dash(dash: string | null): string {
    if (dash === "dashed") return ' stroke-dasharray="7 5"';
    if (dash === "dotted") return ' stroke-dasharray="1.5 4"';
    return "";
  }

  private static paper(fill: string): string {
    return fill === PAPER ? ' class="mtph-pp"' : "";
  }

  private emitLine(pr: Line, tx: Tx, ty: Tx): string {
    const a: Pt = [tx(pr.p1[0]), ty(pr.p1[1])];
    const b: Pt = [tx(pr.p2[0]), ty(pr.p2[1])];
    const frag =
      `<line x1="${f2(a[0])}" y1="${f2(a[1])}" x2="${f2(b[0])}" y2="${f2(b[1])}" ` +
      `stroke="${pr.stroke}" stroke-width="${numStr(pr.width)}" stroke-linecap="round"` +
      `${Scene.dash(pr.dash)}/>`;
    let heads = "";
    if (pr.arrow) heads += Scene.arrowhead(a, b, pr.stroke);
    if (pr.arrow_start) heads += Scene.arrowhead(b, a, pr.stroke);
    return frag + heads;
  }

  private static arrowhead(a: Pt, b: Pt, stroke: string, size = 10.0): string {
    const d = unit([b[0] - a[0], b[1] - a[1]]);
    if (d[0] === 0.0 && d[1] === 0.0) return "";
    const perp: Pt = [-d[1], d[0]];
    const base: Pt = [b[0] - d[0] * size, b[1] - d[1] * size];
    const l: Pt = [base[0] + perp[0] * size * 0.42, base[1] + perp[1] * size * 0.42];
    const r: Pt = [base[0] - perp[0] * size * 0.42, base[1] - perp[1] * size * 0.42];
    return (
      `<polygon points="${f2(b[0])},${f2(b[1])} ${f2(l[0])},${f2(l[1])} ` +
      `${f2(r[0])},${f2(r[1])}" fill="${stroke}"/>`
    );
  }

  private emitPath(pr: Path, tx: Tx, ty: Tx): string {
    if (pr.points.length === 0) return "";
    const pts = pr.points.map(([x, y]) => `${f2(tx(x))},${f2(ty(y))}`).join(" ");
    if (pr.closed) {
      return (
        `<polygon points="${pts}" fill="${pr.fill}"${Scene.paper(pr.fill)} ` +
        `stroke="${pr.stroke}" stroke-width="${numStr(pr.width)}" ` +
        `stroke-linejoin="round"${Scene.dash(pr.dash)}/>`
      );
    }
    return (
      `<polyline points="${pts}" fill="${pr.fill}"${Scene.paper(pr.fill)} ` +
      `stroke="${pr.stroke}" stroke-width="${numStr(pr.width)}" stroke-linejoin="round" ` +
      `stroke-linecap="round"${Scene.dash(pr.dash)}/>`
    );
  }

  private emitCircle(pr: Circle, tx: Tx, ty: Tx): string {
    return (
      `<circle cx="${f2(tx(pr.c[0]))}" cy="${f2(ty(pr.c[1]))}" r="${f2(pr.r * SCALE)}" ` +
      `fill="${pr.fill}"${Scene.paper(pr.fill)} stroke="${pr.stroke}" ` +
      `stroke-width="${numStr(pr.width)}"${Scene.dash(pr.dash)}/>`
    );
  }

  private emitEllipse(pr: Ellipse, tx: Tx, ty: Tx): string {
    const cx = tx(pr.c[0]), cy = ty(pr.c[1]);
    // y is flipped on screen, so a ccw logical rotation is cw in SVG.
    const rotAttr = pr.angle ? ` transform="rotate(${f2(-pr.angle)} ${f2(cx)} ${f2(cy)})"` : "";
    return (
      `<ellipse cx="${f2(cx)}" cy="${f2(cy)}" rx="${f2(pr.rx * SCALE)}" ` +
      `ry="${f2(pr.ry * SCALE)}" fill="${pr.fill}"${Scene.paper(pr.fill)} ` +
      `stroke="${pr.stroke}" stroke-width="${numStr(pr.width)}"${Scene.dash(pr.dash)}${rotAttr}/>`
    );
  }

  private emitBezpath(pr: BezPath, tx: Tx, ty: Tx): string {
    if (pr.segments.length === 0) return "";
    const parts: string[] = [];
    let pen: Pt | null = null; // current on-curve point (logical)
    let ref: Pt | null = null; // point just before the end, for arrow direction
    for (const [cmd, pts] of pr.segments) {
      const scr = pts.map(([x, y]): Pt => [tx(x), ty(y)]);
      if (cmd === "M" || cmd === "L") {
        parts.push(`${cmd} ${f2(scr[0][0])} ${f2(scr[0][1])}`);
        ref = pen; pen = pts[0];
      } else if (cmd === "C") {
        parts.push(
          `C ${f2(scr[0][0])} ${f2(scr[0][1])} ${f2(scr[1][0])} ${f2(scr[1][1])} ` +
            `${f2(scr[2][0])} ${f2(scr[2][1])}`,
        );
        ref = pts[1]; pen = pts[2];
      } else if (cmd === "Q") {
        parts.push(`Q ${f2(scr[0][0])} ${f2(scr[0][1])} ${f2(scr[1][0])} ${f2(scr[1][1])}`);
        ref = pts[0]; pen = pts[1];
      } else if (cmd === "Z") {
        parts.push("Z");
      }
    }
    let frag =
      `<path d="${parts.join(" ")}" fill="${pr.fill}"${Scene.paper(pr.fill)} ` +
      `stroke="${pr.stroke}" stroke-width="${numStr(pr.width)}" stroke-linejoin="round" ` +
      `stroke-linecap="round"${Scene.dash(pr.dash)}/>`;
    if (pr.arrow && pen !== null && ref !== null) {
      frag += Scene.arrowhead([tx(ref[0]), ty(ref[1])], [tx(pen[0]), ty(pen[1])], pr.stroke);
    }
    return frag;
  }

  private emitText(pr: Text, tx: Tx, ty: Tx): string {
    const x = tx(pr.pos[0]) + pr.ox;
    const y = ty(pr.pos[1]) + pr.oy;
    const inner = subSupSpans(labelRuns(pr.raw), pr.size);
    const baseMap: Record<string, string> = { middle: "central", hanging: "hanging", auto: "auto" };
    const baseline = baseMap[pr.baseline] ?? "central";
    const common =
      `x="${f2(x)}" y="${f2(y)}" text-anchor="${pr.anchor}" ` +
      `dominant-baseline="${baseline}" font-size="${numStr(pr.size)}" font-style="italic"`;
    // A paper-coloured halo (drawn as a separate underlay, not paint-order) keeps labels
    // readable over busy backgrounds and renders correctly in cairosvg AND browsers.
    const halo =
      `<text class="mtph-lbl" ${common} fill="${PAPER}" stroke="${PAPER}" ` +
      `stroke-width="3.2" stroke-linejoin="round">${inner}</text>`;
    const ink = `<text ${common} fill="${pr.fill}">${inner}</text>`;
    return halo + ink;
  }
}
