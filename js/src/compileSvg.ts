// Compile figure-DSL source into an SVG string. A faithful port of
// python/src/mtph/diagram/compile_svg.py.
//
// The Compiler interprets each statement, maintains a registry of named points and objects (so
// `incline.mid` / `m` resolve to coordinates), and emits primitives into a Scene.

import {
  Scene, Anim, INK, PAPER, SCALE, FONT, W_NORMAL, W_THIN, W_THICK,
  add, sub, mul, rot, unit, length, midpoint, color,
} from "./shapes.js";
import type { Pt, BezSeg } from "./shapes.js";
import { DiagramSyntaxError, parseDsl } from "./dsl.js";
import type { Statement } from "./dsl.js";
import { MersenneTwister } from "./random.js";
import { fixed } from "./pyfmt.js";

const DEF_FORCE_MAG = 1.15;
const PATTERN_FILLS = new Set(["hatch", "crosshatch", "dots"]);

// Python's float(): parse a numeric string, throwing on malformed input so callers can convert
// to a DiagramSyntaxError exactly where Python catches ValueError.
class PyValueError extends Error {}

function pyFloat(s: string): number {
  const t = s.trim();
  if (t === "" || !/^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$|^[+-]?(inf|infinity|nan)$/i.test(t)) {
    throw new PyValueError(`could not convert to float: ${JSON.stringify(s)}`);
  }
  return Number(t.replace(/inf(inity)?/i, "Infinity"));
}

const rad = (deg: number): number => (deg * Math.PI) / 180;
const deg = (r: number): number => (r * 180) / Math.PI;

interface SceneObject {
  anchors: Record<string, Pt>;
  u?: Pt;
  n?: Pt;
  angle?: number;
}

type StyleKw = { dash?: string | null; width?: number; stroke?: string };

export class Compiler {
  scene = new Scene();
  points: Record<string, Pt> = {};
  objects: Record<string, SceneObject> = {};
  currentIncline: SceneObject | null = null;

  // -- value interpreters ---------------------------------------------------
  private static coord(tok: string, lineno: number): Pt {
    const t = tok.trim();
    if (!(t.startsWith("(") && t.endsWith(")"))) {
      throw new DiagramSyntaxError(lineno, `expected coordinate '(x, y)', got ${pyRepr(tok)}`);
    }
    const parts = t.slice(1, -1).split(",");
    if (parts.length !== 2) {
      throw new DiagramSyntaxError(lineno, `coordinate needs exactly two numbers: ${pyRepr(tok)}`);
    }
    try {
      return [pyFloat(parts[0]), pyFloat(parts[1])];
    } catch {
      throw new DiagramSyntaxError(lineno, `non-numeric coordinate ${pyRepr(tok)}`);
    }
  }

  resolve(tok: string, lineno: number): Pt {
    const t = tok.trim();
    if (t.startsWith("(")) return Compiler.coord(t, lineno);
    if (t.includes(".")) {
      const idx = t.indexOf(".");
      const name = t.slice(0, idx);
      const part = t.slice(idx + 1);
      const obj = this.objects[name];
      if (!obj || !(part in obj.anchors)) {
        throw new DiagramSyntaxError(lineno, `unknown anchor ${pyRepr(tok)}`);
      }
      return obj.anchors[part];
    }
    if (t in this.points) return this.points[t];
    if (t in this.objects && "center" in this.objects[t].anchors) {
      return this.objects[t].anchors.center;
    }
    throw new DiagramSyntaxError(lineno, `unknown point/anchor ${pyRepr(tok)}`);
  }

  private static float(stmt: Statement, key: string, def?: number): number {
    if (!(key in stmt.args)) {
      if (def !== undefined) return def;
      throw new DiagramSyntaxError(stmt.lineno, `'${stmt.command}' needs '${key}='`);
    }
    try {
      return pyFloat(stmt.args[key]);
    } catch {
      throw new DiagramSyntaxError(stmt.lineno, `'${key}=' must be a number`);
    }
  }

  private static str(v: string): string {
    const s = v.trim();
    if (s.length >= 2 && s[0] === '"' && s[s.length - 1] === '"') return s.slice(1, -1);
    return s;
  }

  private require(stmt: Statement, key: string): string {
    if (!(key in stmt.args)) {
      throw new DiagramSyntaxError(stmt.lineno, `'${stmt.command}' needs '${key}='`);
    }
    return stmt.args[key];
  }

  private static fill(stmt: Statement, def = "none"): string {
    const v = stmt.args.fill ?? def;
    if (PATTERN_FILLS.has(v)) return `url(#mtph-${v})`;
    return color(v);
  }

  private static style(stmt: Statement): StyleKw {
    const kw: StyleKw = {};
    // `style=` is canonical; `dash=` is an accepted alias.
    const dash = "style" in stmt.args ? stmt.args.style : stmt.args.dash;
    if (dash !== undefined) kw.dash = dash !== "solid" ? dash : null;
    if ("width" in stmt.args) kw.width = pyFloat(stmt.args.width);
    if ("stroke" in stmt.args) kw.stroke = color(stmt.args.stroke);
    return kw;
  }

  // -- compile loop ---------------------------------------------------------
  execute(source: string): void {
    for (const stmt of parseDsl(source)) {
      const canonical = ALIASES[stmt.command] ?? stmt.command;
      const handler = HANDLERS[canonical];
      if (handler === undefined) {
        throw new DiagramSyntaxError(stmt.lineno, `unknown command ${pyRepr(stmt.command)}`);
      }
      const start = this.scene.prims.length;
      handler.call(this, stmt);
      if ("anim" in stmt.args) this.registerAnim(stmt, start, this.scene.prims.length);
    }
  }

  // -- micro-animation (W5) -------------------------------------------------
  private static readonly ANIM_KINDS = new Set(["spin", "oscillate", "along"]);

  /** Attach an `anim=` on a command to the primitives it just drew (prims[start:end]). */
  private registerAnim(stmt: Statement, start: number, end: number): void {
    const kind = stmt.args.anim;
    if (!Compiler.ANIM_KINDS.has(kind)) {
      throw new DiagramSyntaxError(stmt.lineno, `unknown anim ${pyRepr(kind)} (spin|oscillate|along)`);
    }
    if (end <= start) return; // the command drew nothing to animate
    const period = Compiler.float(stmt, "anim-period", kind === "oscillate" ? 2.0 : 3.0);
    if (period <= 0) throw new DiagramSyntaxError(stmt.lineno, "'anim-period=' must be positive");
    const anim = new Anim(kind, start, end, period);
    if (kind === "spin") {
      if ("anim-about" in stmt.args) anim.center = this.resolve(stmt.args["anim-about"], stmt.lineno);
      anim.cw = (stmt.args["anim-cw"] ?? "false") !== "false";
      anim.swing = Compiler.float(stmt, "anim-swing", 0.0);
    } else if (kind === "oscillate") {
      anim.amp = Compiler.float(stmt, "anim-amp", 0.5);
      anim.direction = Compiler.float(stmt, "anim-dir", 0.0);
    } else if (kind === "along") {
      const raw = Compiler.str(this.require(stmt, "anim-path"));
      anim.path = raw.split(";").filter((p) => p.trim()).map((p) => Compiler.coord(p, stmt.lineno));
      if (anim.path.length < 2) {
        throw new DiagramSyntaxError(stmt.lineno, "'anim-path=' needs at least two points");
      }
    }
    this.scene.animate(anim);
  }

  run(source: string): string {
    this.execute(source);
    return this.scene.toSvg();
  }

  // -- primitive commands ---------------------------------------------------
  cmd_point(stmt: Statement): void {
    if (stmt.positionals.length === 0) {
      throw new DiagramSyntaxError(stmt.lineno, "point needs a name, e.g. 'point P at=(1,2)'");
    }
    const name = stmt.positionals[0];
    const at = this.resolve(this.require(stmt, "at"), stmt.lineno);
    this.points[name] = at;
    if ((stmt.args.dot ?? "true") !== "false") {
      this.scene.circle(at, 0.055, { fill: INK, stroke: INK, width: 1 });
    }
    if ("label" in stmt.args) {
      this.scene.text(at, Compiler.str(stmt.args.label), { anchor: "start", ox: 9, oy: -9 });
    }
  }

  cmd_line(stmt: Statement): void {
    const a = this.resolve(this.require(stmt, "from"), stmt.lineno);
    const b = this.resolve(this.require(stmt, "to"), stmt.lineno);
    this.scene.line(a, b, Compiler.style(stmt));
    if ("label" in stmt.args) {
      const m = midpoint(a, b);
      this.scene.text(m, Compiler.str(stmt.args.label), { oy: -12 });
    }
  }

  cmd_vector(stmt: Statement): void {
    const a = this.resolve(this.require(stmt, "from"), stmt.lineno);
    const b = this.resolve(this.require(stmt, "to"), stmt.lineno);
    const kw = Compiler.style(stmt);
    if (kw.width === undefined) kw.width = W_NORMAL;
    this.scene.line(a, b, { ...kw, arrow: true });
    if ("label" in stmt.args) {
      this.arrowLabel(b, unit(sub(b, a)), Compiler.str(stmt.args.label));
    }
  }

  cmd_current(stmt: Statement): void {
    const a = this.resolve(this.require(stmt, "from"), stmt.lineno);
    const b = this.resolve(this.require(stmt, "to"), stmt.lineno);
    const kw = Compiler.style(stmt);
    if (kw.width === undefined) kw.width = W_NORMAL;
    this.scene.line(a, b, { ...kw, arrow: true });
    const label = Compiler.str(stmt.args.label ?? "I");
    this.arrowLabel(b, unit(sub(b, a)), label);
  }

  cmd_spiral(stmt: Statement): void {
    const c = this.resolve(this.require(stmt, "at"), stmt.lineno);
    const r0 = Compiler.float(stmt, "r0", 0.0);
    const dr = Compiler.float(stmt, "dr", 0.3);
    const turns = Compiler.float(stmt, "turns", 3.0);
    const a0 = rad(Compiler.float(stmt, "a0", 0.0));
    const steps = Math.max(16, Math.trunc(Math.abs(turns) * 48));
    const pts: Pt[] = [];
    for (let i = 0; i <= steps; i++) {
      const frac = i / steps;
      const th = a0 + turns * 2 * Math.PI * frac;
      const r = r0 + dr * turns * frac;
      pts.push([c[0] + r * Math.cos(th), c[1] + r * Math.sin(th)]);
    }
    this.scene.path(pts, Compiler.style(stmt));
    if ("label" in stmt.args) {
      this.scene.text(pts[pts.length - 1], Compiler.str(stmt.args.label), { anchor: "start", ox: 8 });
    }
  }

  cmd_circle(stmt: Statement): void {
    const c = this.resolve(this.require(stmt, "at"), stmt.lineno);
    const r = Compiler.float(stmt, "r");
    const fill = Compiler.fill(stmt);
    this.scene.circle(c, r, { fill, ...Compiler.style(stmt) });
    if ("label" in stmt.args) this.scene.text(c, Compiler.str(stmt.args.label));
  }

  cmd_rect(stmt: Statement): void {
    const c = this.resolve(this.require(stmt, "at"), stmt.lineno);
    const w = Compiler.float(stmt, "w");
    const h = Compiler.float(stmt, "h");
    const ang = Compiler.float(stmt, "angle", 0.0);
    const fill = Compiler.fill(stmt);
    this.scene.path(Compiler.rectPts(c, w, h, ang), { closed: true, fill, ...Compiler.style(stmt) });
    if ("label" in stmt.args) this.scene.text(c, Compiler.str(stmt.args.label));
  }

  private static rectPts(c: Pt, w: number, h: number, ang: number): Pt[] {
    const hw = w / 2, hh = h / 2;
    const local: Pt[] = [[-hw, hh], [hw, hh], [hw, -hh], [-hw, -hh]];
    return local.map((p) => add(c, rot(p, ang)));
  }

  cmd_polygon(stmt: Statement): void {
    const raw = this.require(stmt, "points");
    const pts = raw.split(";").filter((p) => p.trim()).map((p) => Compiler.coord(p, stmt.lineno));
    const closed = (stmt.args.closed ?? "true") !== "false";
    const fill = Compiler.fill(stmt);
    this.scene.path(pts, { closed, fill, ...Compiler.style(stmt) });
  }

  cmd_path(stmt: Statement): void {
    const d = Compiler.str(this.require(stmt, "d"));
    const tokens = d.match(/[MLCQZ]|\([^)]*\)/g) ?? [];
    const need: Record<string, number> = { M: 1, L: 1, C: 3, Q: 2, Z: 0 };
    const segments: BezSeg[] = [];
    let i = 0;
    while (i < tokens.length) {
      const cmd = tokens[i];
      if (!(cmd in need)) {
        throw new DiagramSyntaxError(stmt.lineno, `unexpected token ${pyRepr(cmd)} in path d=`);
      }
      const n = need[cmd];
      const pts: Pt[] = [];
      for (let j = 0; j < n; j++) {
        if (i + 1 + j >= tokens.length) {
          throw new DiagramSyntaxError(stmt.lineno, `path '${cmd}' needs ${n} coordinate(s)`);
        }
        pts.push(Compiler.coord(tokens[i + 1 + j], stmt.lineno));
      }
      segments.push([cmd, pts]);
      i += 1 + n;
    }
    if (segments.length === 0) {
      throw new DiagramSyntaxError(stmt.lineno, 'path needs d="M(..) L(..) ..."');
    }
    const fill = Compiler.fill(stmt);
    const arrow = stmt.args.arrow === "true";
    this.scene.bezier(segments, { fill, arrow, ...Compiler.style(stmt) });
  }

  cmd_arc(stmt: Statement): void {
    const c = this.resolve(this.require(stmt, "at"), stmt.lineno);
    const r = Compiler.float(stmt, "r");
    const a0 = Compiler.float(stmt, "from");
    const a1 = Compiler.float(stmt, "to");
    const { dash: _dash, ...rest } = Compiler.style(stmt);
    this.scene.arc(c, r, a0, a1, rest);
  }

  cmd_label(stmt: Statement): void {
    const at = this.resolve(this.require(stmt, "at"), stmt.lineno);
    const text = Compiler.str(this.require(stmt, "text"));
    const [anchor, baseline, ox, oy] = anchorKw(stmt.args.anchor ?? "center");
    const dx = pyFloat(stmt.args.dx ?? "0.0");
    const dy = pyFloat(stmt.args.dy ?? "0.0");
    this.scene.text([at[0] + dx, at[1] + dy], text, { anchor, baseline, ox, oy });
  }

  cmd_angle(stmt: Statement): void {
    let vertex: Pt;
    let a0: number;
    let a1: number;
    if ("between" in stmt.args) {
      const names = stmt.args.between.split(",").map((s) => s.trim());
      if (names.length !== 3) {
        throw new DiagramSyntaxError(stmt.lineno, "angle between= needs three anchors A,B,C");
      }
      const a = this.resolve(names[0], stmt.lineno);
      const v = this.resolve(names[1], stmt.lineno);
      const c = this.resolve(names[2], stmt.lineno);
      a0 = deg(Math.atan2(a[1] - v[1], a[0] - v[0]));
      a1 = deg(Math.atan2(c[1] - v[1], c[0] - v[0]));
      vertex = v;
    } else {
      vertex = this.resolve(this.require(stmt, "at"), stmt.lineno);
      a0 = Compiler.float(stmt, "from");
      a1 = Compiler.float(stmt, "to");
    }
    const r = Compiler.float(stmt, "r", 0.7);
    this.scene.arc(vertex, r, a0, a1, { width: W_THIN });
    if ("value" in stmt.args) {
      const mid = rad((a0 + a1) / 2);
      const lp: Pt = [vertex[0] + (r + 0.28) * Math.cos(mid), vertex[1] + (r + 0.28) * Math.sin(mid)];
      this.scene.text(lp, Compiler.str(stmt.args.value));
    }
  }

  // -- fields, charges & E&M ------------------------------------------------
  private drawCharge(at: Pt, sign: string, r: number): void {
    this.scene.circle(at, r, { fill: PAPER, width: W_NORMAL });
    const glyph = sign.startsWith("+") || ["plus", "pos", "positive"].includes(sign) ? "+" : "−";
    this.scene.text(at, glyph, { size: FONT + 3 });
  }

  cmd_charge(stmt: Statement): void {
    const at = this.resolve(this.require(stmt, "at"), stmt.lineno);
    const r = Compiler.float(stmt, "r", 0.26);
    this.drawCharge(at, stmt.args.sign ?? "+", r);
    if (stmt.positionals.length) this.points[stmt.positionals[0]] = at;
    if ("label" in stmt.args) {
      this.scene.text(at, Compiler.str(stmt.args.label), { oy: -(r * SCALE + 26) });
    }
  }

  cmd_dipole(stmt: Statement): void {
    const at = "at" in stmt.args ? this.resolve(stmt.args.at, stmt.lineno) : [0.0, 0.0] as Pt;
    const sep = Compiler.float(stmt, "sep", 1.2);
    const ang = Compiler.float(stmt, "angle", 0.0);
    const r = Compiler.float(stmt, "r", 0.24);
    const d = rot([1.0, 0.0], ang);
    const pos = add(at, mul(d, sep / 2));
    const neg = sub(at, mul(d, sep / 2));
    if (stmt.args.moment === "true") this.scene.line(neg, pos, { arrow: true, width: W_THIN });
    this.drawCharge(neg, "-", r);
    this.drawCharge(pos, "+", r);
    if ("label" in stmt.args) {
      this.scene.text(at, Compiler.str(stmt.args.label), { oy: -(sep / 2 * SCALE + 16) });
    }
  }

  cmd_bfield(stmt: Statement): void {
    const at = "at" in stmt.args ? this.resolve(stmt.args.at, stmt.lineno) : [0.0, 0.0] as Pt;
    const w = Compiler.float(stmt, "width", 2.0);
    const h = Compiler.float(stmt, "height", 2.0);
    const n = Math.max(2, Math.trunc(Compiler.float(stmt, "n", 4)));
    const out = (stmt.args.dir ?? "out").startsWith("o");
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        const x = at[0] + (i + 0.5) * w / n;
        const y = at[1] + (j + 0.5) * h / n;
        this.scene.circle([x, y], 0.085, { width: W_THIN });
        if (out) {
          this.scene.circle([x, y], 0.022, { fill: INK, width: W_THIN });
        } else {
          const dd = 0.06;
          this.scene.line([x - dd, y - dd], [x + dd, y + dd], { width: W_THIN });
          this.scene.line([x - dd, y + dd], [x + dd, y - dd], { width: W_THIN });
        }
      }
    }
    if ("label" in stmt.args) {
      this.scene.text([at[0] + w / 2, at[1] + h], Compiler.str(stmt.args.label), { oy: -10 });
    }
  }

  cmd_fieldline(stmt: Statement): void {
    const a = this.resolve(this.require(stmt, "from"), stmt.lineno);
    const b = this.resolve(this.require(stmt, "to"), stmt.lineno);
    const bend = Compiler.float(stmt, "bend", 0.0);
    const d = unit(sub(b, a));
    const p: Pt = [-d[1], d[0]];
    const ctrl = add(midpoint(a, b), mul(p, bend * length(sub(b, a))));
    const arrow = (stmt.args.arrow ?? "true") !== "false";
    this.scene.bezier([["M", [a]], ["Q", [ctrl, b]]], { arrow, ...Compiler.style(stmt) });
  }

  cmd_vectorfield(stmt: Statement): void {
    const at = "at" in stmt.args ? this.resolve(stmt.args.at, stmt.lineno) : [0.0, 0.0] as Pt;
    const w = Compiler.float(stmt, "width", 3.0);
    const h = Compiler.float(stmt, "height", 3.0);
    const n = Math.max(2, Math.trunc(Compiler.float(stmt, "n", 5)));
    const direction = stmt.args.dir ?? "0";
    const L = Math.min(w, h) / n * 0.62;
    const cx = at[0] + w / 2, cy = at[1] + h / 2;
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        const x = at[0] + (i + 0.5) * w / n;
        const y = at[1] + (j + 0.5) * h / n;
        let dvec: Pt;
        if (direction === "out" || direction === "radial") {
          dvec = unit([x - cx, y - cy]);
        } else if (direction === "in") {
          dvec = unit([cx - x, cy - y]);
        } else {
          dvec = rot([1.0, 0.0], pyFloat(direction));
        }
        if (dvec[0] === 0.0 && dvec[1] === 0.0) continue;
        this.scene.line([x, y], add([x, y], mul(dvec, L)), { arrow: true, width: W_THIN });
      }
    }
  }

  cmd_equipotential(stmt: Statement): void {
    const c = this.resolve(this.require(stmt, "at"), stmt.lineno);
    const r = Compiler.float(stmt, "r");
    this.scene.circle(c, r, { dash: "dashed", width: W_THIN, stroke: "#888888" });
  }

  cmd_gaussian(stmt: Statement): void {
    const c = this.resolve(this.require(stmt, "at"), stmt.lineno);
    const r = Compiler.float(stmt, "r");
    this.scene.circle(c, r, { dash: "dashed", width: W_THIN });
    if ("label" in stmt.args) {
      this.scene.text(c, Compiler.str(stmt.args.label), { oy: -(r * SCALE + 10) });
    }
  }

  // -- physics / geometry helpers -------------------------------------------
  cmd_incline(stmt: Statement): void {
    const ang = Compiler.float(stmt, "angle");
    const L = Compiler.float(stmt, "length");
    const base = "at" in stmt.args ? this.resolve(stmt.args.at, stmt.lineno) : [0.0, 0.0] as Pt;
    const r = rad(ang);
    const foot: Pt = [base[0] + L * Math.cos(r), base[1]];
    const top: Pt = [foot[0], base[1] + L * Math.sin(r)];
    const u = unit(sub(top, base)); // up the ramp
    const n = rot(u, 90); // outward normal
    this.scene.path([base, foot, top], { closed: true, width: W_NORMAL });
    this.ground([base[0] - 0.5, base[1]], foot[0] + 0.4);
    const obj: SceneObject = {
      anchors: { base, foot, top, mid: midpoint(base, top) },
      u, n, angle: ang,
    };
    this.objects.incline = obj;
    this.currentIncline = obj;
  }

  cmd_mass(stmt: Statement): void {
    if (stmt.positionals.length === 0) {
      throw new DiagramSyntaxError(stmt.lineno, "mass needs a name, e.g. 'mass m at=...'");
    }
    const name = stmt.positionals[0];
    const atTok = this.require(stmt, "at");
    const basePt = this.resolve(atTok, stmt.lineno);
    const size = Compiler.float(stmt, "size", 0.8);
    const onIncline = atTok.startsWith("incline") && this.currentIncline !== null;
    let u: Pt, n: Pt, ang: number, center: Pt;
    if (onIncline) {
      const inc = this.currentIncline!;
      u = inc.u!; n = inc.n!;
      ang = inc.angle!;
      center = add(basePt, mul(n, size / 2));
    } else {
      u = [1.0, 0.0]; n = [0.0, 1.0];
      ang = Compiler.float(stmt, "angle", 0.0);
      center = basePt;
    }
    this.scene.path(Compiler.rectPts(center, size, size, ang), { closed: true, fill: PAPER });
    this.points[name] = center;
    this.objects[name] = { anchors: { center }, u, n };
    if ("label" in stmt.args) {
      this.scene.text(center, Compiler.str(stmt.args.label), { ox: u[0] * 14, oy: -u[1] * 14 });
    }
  }

  private frameFor(anchorTok: string): [Pt, Pt] {
    const name = anchorTok.split(".")[0];
    const obj = this.objects[name];
    if (obj && obj.u) return [obj.u, obj.n!];
    if (this.currentIncline) return [this.currentIncline.u!, this.currentIncline.n!];
    return [[1.0, 0.0], [0.0, 1.0]];
  }

  cmd_force(stmt: Statement): void {
    const fromTok = this.require(stmt, "from");
    const base = this.resolve(fromTok, stmt.lineno);
    const [u, n] = this.frameFor(fromTok);
    const d = this.require(stmt, "dir");
    const mag = Compiler.float(stmt, "mag", DEF_FORCE_MAG);
    const dirs: Record<string, Pt> = {
      down: [0.0, -1.0], up: [0.0, 1.0], left: [-1.0, 0.0], right: [1.0, 0.0],
      "perp-out": n, "perp-in": mul(n, -1), along: u, "along-up": u,
      "along-down": mul(u, -1),
    };
    let dvec: Pt;
    if (d in dirs) {
      dvec = dirs[d];
    } else {
      try {
        dvec = rot([1.0, 0.0], pyFloat(d));
      } catch {
        throw new DiagramSyntaxError(stmt.lineno, `bad force dir ${pyRepr(d)}`);
      }
    }
    const tip = add(base, mul(unit(dvec), mag));
    this.scene.line(base, tip, { arrow: true, width: W_THICK });
    if ("label" in stmt.args) {
      this.arrowLabel(tip, unit(dvec), Compiler.str(stmt.args.label));
    }
  }

  cmd_spring(stmt: Statement): void {
    const a = this.resolve(this.require(stmt, "from"), stmt.lineno);
    const b = this.resolve(this.require(stmt, "to"), stmt.lineno);
    const coils = Math.trunc(Compiler.float(stmt, "coils", 6));
    this.scene.path(zigzag(a, b, coils, 0.13), { width: W_THIN });
    if ("label" in stmt.args) {
      this.scene.text(midpoint(a, b), Compiler.str(stmt.args.label), { oy: -14 });
    }
  }

  cmd_zigzag(stmt: Statement): void {
    const a = this.resolve(this.require(stmt, "from"), stmt.lineno);
    const b = this.resolve(this.require(stmt, "to"), stmt.lineno);
    const amp = Compiler.float(stmt, "amplitude", 0.18);
    const periods = Math.max(1, Math.trunc(Compiler.float(stmt, "periods", 6)));
    this.scene.path(zigzag(a, b, periods, amp), Compiler.style(stmt));
    if ("label" in stmt.args) {
      this.scene.text(midpoint(a, b), Compiler.str(stmt.args.label), { oy: -14 });
    }
  }

  cmd_pulley(stmt: Statement): void {
    const c = this.resolve(this.require(stmt, "at"), stmt.lineno);
    const r = Compiler.float(stmt, "r", 0.35);
    this.scene.circle(c, r);
    this.scene.circle(c, 0.04, { fill: INK });
  }

  cmd_ground(stmt: Statement): void {
    const at = this.resolve(this.require(stmt, "at"), stmt.lineno);
    const width = Compiler.float(stmt, "width", 3.0);
    this.ground(at, at[0] + width);
  }

  private ground(left: Pt, rightX: number): void {
    const y = left[1];
    this.scene.line([left[0], y], [rightX, y], { width: W_NORMAL });
    let x = left[0];
    const step = 0.32;
    while (x < rightX) {
      this.scene.line([x, y], [x - 0.22, y - 0.22], { width: W_THIN });
      x += step;
    }
  }

  cmd_wall(stmt: Statement): void {
    const at = "at" in stmt.args ? this.resolve(stmt.args.at, stmt.lineno) : [0.0, 0.0] as Pt;
    const h = Compiler.float(stmt, "height", 3.0);
    const sgn = (stmt.args.side ?? "left") === "left" ? -1.0 : 1.0;
    this.scene.line(at, [at[0], at[1] + h], { width: W_NORMAL });
    let y = at[1];
    while (y < at[1] + h) {
      this.scene.line([at[0], y], [at[0] + sgn * 0.22, y + 0.22], { width: W_THIN });
      y += 0.32;
    }
  }

  cmd_dim(stmt: Statement): void {
    const a = this.resolve(this.require(stmt, "from"), stmt.lineno);
    const b = this.resolve(this.require(stmt, "to"), stmt.lineno);
    const off = Compiler.float(stmt, "off", -0.6);
    const d = unit(sub(b, a));
    const p: Pt = [-d[1], d[0]];
    const a2 = add(a, mul(p, off));
    const b2 = add(b, mul(p, off));
    this.scene.line(a, a2, { width: W_THIN, stroke: "#888888" });
    this.scene.line(b, b2, { width: W_THIN, stroke: "#888888" });
    this.scene.line(a2, b2, { width: W_THIN, arrow: true, arrow_start: true });
    if ("label" in stmt.args) {
      const sign = off < 0 ? -1.0 : 1.0;
      this.scene.text(midpoint(a2, b2), Compiler.str(stmt.args.label),
        { ox: p[0] * 14 * sign, oy: -p[1] * 14 * sign });
    }
  }

  cmd_axis(stmt: Statement): void {
    const origin = "origin" in stmt.args ? this.resolve(stmt.args.origin, stmt.lineno) : [0.0, 0.0] as Pt;
    const xr = rangePair(stmt.args.x ?? "-3..3", stmt.lineno);
    const yr = rangePair(stmt.args.y ?? "-3..3", stmt.lineno);
    this.scene.line([origin[0] + xr[0], origin[1]], [origin[0] + xr[1], origin[1]],
      { width: W_THIN, arrow: true, arrow_start: true });
    this.scene.line([origin[0], origin[1] + yr[0]], [origin[0], origin[1] + yr[1]],
      { width: W_THIN, arrow: true, arrow_start: true });
    if ((stmt.args.labels ?? "true") !== "false") {
      this.scene.text([origin[0] + xr[1], origin[1]], "x", { anchor: "start", ox: 10, oy: 12 });
      this.scene.text([origin[0], origin[1] + yr[1]], "y", { anchor: "start", ox: 10, oy: -6 });
    }
  }

  // -- mechanics, 3D & frames -----------------------------------------------
  cmd_pendulum(stmt: Statement): void {
    const pivot = this.resolve(this.require(stmt, "at"), stmt.lineno);
    const L = Compiler.float(stmt, "length", 2.0);
    const ang = Compiler.float(stmt, "angle", 20.0);
    const bob = Compiler.float(stmt, "bob", 0.3);
    const r = rad(ang);
    const bobc: Pt = [pivot[0] + L * Math.sin(r), pivot[1] - L * Math.cos(r)];
    this.scene.line(pivot, [pivot[0], pivot[1] - L], { dash: "dashed", width: W_THIN, stroke: "#888888" });
    this.scene.line(pivot, bobc, { width: W_NORMAL });
    this.scene.circle(pivot, 0.05, { fill: INK });
    this.scene.circle(bobc, bob, { fill: PAPER });
    if (Math.abs(ang) > 0.5) {
      const aRod = deg(Math.atan2(bobc[1] - pivot[1], bobc[0] - pivot[0]));
      this.scene.arc(pivot, L * 0.32, Math.min(-90.0, aRod), Math.max(-90.0, aRod), { width: W_THIN });
      if ("value" in stmt.args) {
        const mid = rad((-90.0 + aRod) / 2);
        const lp: Pt = [pivot[0] + (L * 0.32 + 0.25) * Math.cos(mid),
          pivot[1] + (L * 0.32 + 0.25) * Math.sin(mid)];
        this.scene.text(lp, Compiler.str(stmt.args.value));
      }
    }
    if (stmt.positionals.length) {
      this.points[stmt.positionals[0]] = bobc;
      this.objects[stmt.positionals[0]] = { anchors: { center: bobc }, u: [1.0, 0.0], n: [0.0, 1.0] };
    }
    if ("label" in stmt.args) this.scene.text(bobc, Compiler.str(stmt.args.label));
  }

  cmd_rod(stmt: Statement): void {
    const a = this.resolve(this.require(stmt, "from"), stmt.lineno);
    const b = this.resolve(this.require(stmt, "to"), stmt.lineno);
    this.scene.line(a, b, { width: pyFloat(stmt.args.width ?? String(W_THICK)) });
    if ("label" in stmt.args) {
      this.scene.text(midpoint(a, b), Compiler.str(stmt.args.label), { oy: -12 });
    }
  }

  cmd_pivot(stmt: Statement): void {
    const c = this.resolve(this.require(stmt, "at"), stmt.lineno);
    const s = Compiler.float(stmt, "size", 0.3);
    this.scene.path([[c[0] - s, c[1] - s], c, [c[0] + s, c[1] - s]], { closed: true, fill: PAPER });
    this.ground([c[0] - s - 0.15, c[1] - s], c[0] + s + 0.15);
    this.scene.circle(c, 0.05, { fill: INK });
    if ("label" in stmt.args) {
      this.scene.text(c, Compiler.str(stmt.args.label), { anchor: "start", ox: 10 });
    }
  }

  cmd_axes3d(stmt: Statement): void {
    const o = "at" in stmt.args ? this.resolve(stmt.args.at, stmt.lineno) : [0.0, 0.0] as Pt;
    const s = Compiler.float(stmt, "size", 2.4);
    const zdir = unit([-0.7, -0.5]);
    this.scene.line(o, [o[0] + s, o[1]], { arrow: true, width: W_THIN });
    this.scene.line(o, [o[0], o[1] + s], { arrow: true, width: W_THIN });
    this.scene.line(o, add(o, mul(zdir, s * 0.75)), { arrow: true, width: W_THIN });
    if ((stmt.args.labels ?? "true") !== "false") {
      this.scene.text([o[0] + s, o[1]], "x", { anchor: "start", ox: 8, oy: 10 });
      this.scene.text([o[0], o[1] + s], "y", { anchor: "start", ox: 8, oy: -6 });
      const zt = add(o, mul(zdir, s * 0.75));
      this.scene.text(zt, "z", { anchor: "end", ox: -8, oy: 6 });
    }
  }

  cmd_sphere(stmt: Statement): void {
    const c = this.resolve(this.require(stmt, "at"), stmt.lineno);
    const r = Compiler.float(stmt, "r", 1.0);
    this.scene.circle(c, r);
    this.scene.ellipse(c, r, r * 0.32, { width: W_THIN });
    if ("label" in stmt.args) {
      this.scene.text(c, Compiler.str(stmt.args.label), { oy: -(r * SCALE + 10) });
    }
  }

  cmd_omega(stmt: Statement): void {
    const c = "at" in stmt.args ? this.resolve(stmt.args.at, stmt.lineno) : [0.0, 0.0] as Pt;
    const r = Compiler.float(stmt, "r", 0.6);
    const ccw = (stmt.args.dir ?? "ccw") !== "cw";
    const [a0, a1] = ccw ? [35.0, 320.0] : [320.0, 35.0];
    const steps = 26;
    const pts: Pt[] = [];
    for (let k = 0; k <= steps; k++) {
      pts.push([c[0] + r * Math.cos(rad(a0 + (a1 - a0) * k / steps)),
        c[1] + r * Math.sin(rad(a0 + (a1 - a0) * k / steps))]);
    }
    this.scene.path(pts, { width: W_NORMAL });
    this.scene.line(pts[pts.length - 2], pts[pts.length - 1], { arrow: true, width: W_NORMAL });
    const label = "label" in stmt.args ? Compiler.str(stmt.args.label) : "\\omega";
    this.scene.text(c, label);
  }

  // -- circuit --------------------------------------------------------------
  cmd_wire(stmt: Statement): void {
    const a = this.resolve(this.require(stmt, "from"), stmt.lineno);
    const b = this.resolve(this.require(stmt, "to"), stmt.lineno);
    this.scene.line(a, b, { width: W_NORMAL });
  }

  cmd_resistor(stmt: Statement): void {
    const a = this.resolve(this.require(stmt, "from"), stmt.lineno);
    const b = this.resolve(this.require(stmt, "to"), stmt.lineno);
    const d = unit(sub(b, a));
    const lead = 0.22;
    const a2 = add(a, mul(d, lead));
    const b2 = sub(b, mul(d, lead));
    this.scene.line(a, a2, { width: W_NORMAL });
    this.scene.line(b2, b, { width: W_NORMAL });
    this.scene.path(zigzag(a2, b2, 6, 0.16), { width: W_NORMAL });
    if ("label" in stmt.args) this.componentLabel(a, b, Compiler.str(stmt.args.label));
  }

  cmd_battery(stmt: Statement): void {
    const a = this.resolve(this.require(stmt, "from"), stmt.lineno);
    const b = this.resolve(this.require(stmt, "to"), stmt.lineno);
    const d = unit(sub(b, a));
    const p: Pt = [-d[1], d[0]];
    const mid = midpoint(a, b);
    const longP = mid, shortP = add(mid, mul(d, 0.16));
    this.scene.line(a, sub(longP, mul(d, 0.0)), { width: W_NORMAL });
    this.scene.line(shortP, b, { width: W_NORMAL });
    this.scene.line(add(longP, mul(p, 0.32)), sub(longP, mul(p, 0.32)), { width: W_NORMAL });
    this.scene.line(add(shortP, mul(p, 0.18)), sub(shortP, mul(p, 0.18)), { width: W_THICK });
    if ("label" in stmt.args) this.componentLabel(a, b, Compiler.str(stmt.args.label));
  }

  // -- optics (light) -------------------------------------------------------
  cmd_lens(stmt: Statement): void {
    const c = this.resolve(this.require(stmt, "at"), stmt.lineno);
    const h = Compiler.float(stmt, "height", 2.0);
    const kind = stmt.args.type ?? "convex";
    const top: Pt = [c[0], c[1] + h / 2], bot: Pt = [c[0], c[1] - h / 2];
    this.scene.line(top, bot, { width: W_NORMAL });
    const out = kind === "convex" ? 1 : -1;
    for (const end of [top, bot]) {
      const sgn = end === top ? 1 : -1;
      const tip: Pt = [end[0], end[1] + sgn * 0.18 * out];
      this.scene.line([end[0], end[1] - sgn * 0.18 * out], tip, { arrow: true, width: W_THIN });
    }
  }

  cmd_ray(stmt: Statement): void {
    const a = this.resolve(this.require(stmt, "from"), stmt.lineno);
    const b = this.resolve(this.require(stmt, "to"), stmt.lineno);
    const arrow = (stmt.args.arrow ?? "true") !== "false";
    this.scene.line(a, b, { arrow, width: W_THIN });
  }

  // -- thermo, fluids & waves -----------------------------------------------
  cmd_container(stmt: Statement): void {
    const at = this.resolve(this.require(stmt, "at"), stmt.lineno); // bottom-left
    const w = Compiler.float(stmt, "width", 2.0);
    const h = Compiler.float(stmt, "height", 2.0);
    if ((stmt.args.fill ?? "none") !== "none") {
      const level = Compiler.float(stmt, "level", h * 0.6);
      this.scene.path(
        [at, [at[0] + w, at[1]], [at[0] + w, at[1] + level], [at[0], at[1] + level]],
        { closed: true, fill: color(stmt.args.fill) },
      );
    }
    this.scene.path(
      [[at[0], at[1] + h], at, [at[0] + w, at[1]], [at[0] + w, at[1] + h]],
      { width: W_NORMAL },
    );
    if ("label" in stmt.args) {
      this.scene.text([at[0] + w / 2, at[1] + h / 2], Compiler.str(stmt.args.label));
    }
  }

  cmd_piston(stmt: Statement): void {
    const at = this.resolve(this.require(stmt, "at"), stmt.lineno); // centre of plate
    const w = Compiler.float(stmt, "width", 1.8);
    const th = Compiler.float(stmt, "thickness", 0.22);
    const rodLen = Compiler.float(stmt, "rod", 1.0);
    this.scene.path(Compiler.rectPts(at, w, th, 0.0), { closed: true, fill: "#cccccc" });
    this.scene.line([at[0], at[1] + th / 2], [at[0], at[1] + th / 2 + rodLen], { width: W_THICK });
    if ("label" in stmt.args) {
      this.scene.text([at[0], at[1] + th / 2 + rodLen], Compiler.str(stmt.args.label), { oy: -12 });
    }
  }

  cmd_gas(stmt: Statement): void {
    const at = this.resolve(this.require(stmt, "at"), stmt.lineno); // bottom-left
    const w = Compiler.float(stmt, "width", 2.0);
    const h = Compiler.float(stmt, "height", 2.0);
    const n = Math.max(1, Math.trunc(Compiler.float(stmt, "n", 14)));
    const rng = new MersenneTwister(Math.trunc(Compiler.float(stmt, "seed", 0)));
    const m = 0.12;
    for (let k = 0; k < n; k++) {
      const x = at[0] + m + rng.random() * (w - 2 * m);
      const y = at[1] + m + rng.random() * (h - 2 * m);
      this.scene.circle([x, y], 0.06, { fill: INK, width: W_THIN });
    }
  }

  cmd_heat(stmt: Statement): void {
    const at = this.resolve(this.require(stmt, "at"), stmt.lineno); // baseline left
    const w = Compiler.float(stmt, "width", 2.0);
    const n = Math.max(1, Math.trunc(Compiler.float(stmt, "n", 3)));
    const H = Compiler.float(stmt, "height", 0.9);
    const a = 0.12;
    for (let k = 0; k < n; k++) {
      const x = at[0] + (k + 0.5) * w / n;
      const y = at[1];
      const seg: BezSeg[] = [
        ["M", [[x, y]]],
        ["C", [[x + a, y + H * 0.33], [x - a, y + H * 0.5], [x, y + H * 0.66]]],
        ["Q", [[x + a, y + H * 0.86], [x, y + H]]],
      ];
      this.scene.bezier(seg, { arrow: true, width: W_THIN });
    }
  }

  cmd_flame(stmt: Statement): void {
    const at = this.resolve(this.require(stmt, "at"), stmt.lineno);
    const s = Compiler.float(stmt, "size", 0.6);
    const [x, y] = at;
    const seg: BezSeg[] = [
      ["M", [[x, y + s * 1.7]]],
      ["C", [[x + s * 0.75, y + s * 0.9], [x + s * 0.55, y], [x, y]]],
      ["C", [[x - s * 0.55, y], [x - s * 0.75, y + s * 0.9], [x, y + s * 1.7]]],
      ["Z", []],
    ];
    this.scene.bezier(seg, { width: W_NORMAL });
  }

  cmd_wavefront(stmt: Statement): void {
    const c = this.resolve(this.require(stmt, "at"), stmt.lineno);
    const n = Math.max(1, Math.trunc(Compiler.float(stmt, "n", 4)));
    const r0 = Compiler.float(stmt, "r0", 0.5);
    const dr = Compiler.float(stmt, "dr", 0.5);
    if ("from" in stmt.args && "to" in stmt.args) {
      const f = Compiler.float(stmt, "from"), t = Compiler.float(stmt, "to");
      for (let k = 0; k < n; k++) this.scene.arc(c, r0 + k * dr, f, t, { width: W_THIN });
    } else {
      for (let k = 0; k < n; k++) this.scene.circle(c, r0 + k * dr, { width: W_THIN });
    }
    this.scene.circle(c, 0.05, { fill: INK });
  }

  // -- shared label placement -----------------------------------------------
  private arrowLabel(tip: Pt, d: Pt, text: string): void {
    const ox = d[0] * 16;
    const oy = -d[1] * 16;
    const anchor = d[0] > 0.3 ? "start" : d[0] < -0.3 ? "end" : "middle";
    this.scene.text(tip, text, { anchor, ox, oy });
  }

  private componentLabel(a: Pt, b: Pt, text: string): void {
    const d = unit(sub(b, a));
    let p: Pt = [-d[1], d[0]];
    if (p[1] < 0) p = [-p[0], -p[1]]; // prefer the upper / left side
    const ox = p[0] * 20, oy = -p[1] * 20;
    const anchor = p[0] > 0.4 ? "start" : p[0] < -0.4 ? "end" : "middle";
    this.scene.text(midpoint(a, b), text, { anchor, ox, oy });
  }
}

type Handler = (this: Compiler, stmt: Statement) => void;

const HANDLERS: Record<string, Handler> = {
  point: Compiler.prototype.cmd_point,
  line: Compiler.prototype.cmd_line,
  vector: Compiler.prototype.cmd_vector,
  current: Compiler.prototype.cmd_current,
  spiral: Compiler.prototype.cmd_spiral,
  circle: Compiler.prototype.cmd_circle,
  rect: Compiler.prototype.cmd_rect,
  polygon: Compiler.prototype.cmd_polygon,
  path: Compiler.prototype.cmd_path,
  arc: Compiler.prototype.cmd_arc,
  label: Compiler.prototype.cmd_label,
  angle: Compiler.prototype.cmd_angle,
  charge: Compiler.prototype.cmd_charge,
  dipole: Compiler.prototype.cmd_dipole,
  bfield: Compiler.prototype.cmd_bfield,
  fieldline: Compiler.prototype.cmd_fieldline,
  vectorfield: Compiler.prototype.cmd_vectorfield,
  equipotential: Compiler.prototype.cmd_equipotential,
  gaussian: Compiler.prototype.cmd_gaussian,
  incline: Compiler.prototype.cmd_incline,
  mass: Compiler.prototype.cmd_mass,
  force: Compiler.prototype.cmd_force,
  spring: Compiler.prototype.cmd_spring,
  zigzag: Compiler.prototype.cmd_zigzag,
  pulley: Compiler.prototype.cmd_pulley,
  ground: Compiler.prototype.cmd_ground,
  wall: Compiler.prototype.cmd_wall,
  dim: Compiler.prototype.cmd_dim,
  axis: Compiler.prototype.cmd_axis,
  pendulum: Compiler.prototype.cmd_pendulum,
  rod: Compiler.prototype.cmd_rod,
  pivot: Compiler.prototype.cmd_pivot,
  axes3d: Compiler.prototype.cmd_axes3d,
  sphere: Compiler.prototype.cmd_sphere,
  omega: Compiler.prototype.cmd_omega,
  wire: Compiler.prototype.cmd_wire,
  resistor: Compiler.prototype.cmd_resistor,
  battery: Compiler.prototype.cmd_battery,
  lens: Compiler.prototype.cmd_lens,
  ray: Compiler.prototype.cmd_ray,
  container: Compiler.prototype.cmd_container,
  piston: Compiler.prototype.cmd_piston,
  gas: Compiler.prototype.cmd_gas,
  heat: Compiler.prototype.cmd_heat,
  flame: Compiler.prototype.cmd_flame,
  wavefront: Compiler.prototype.cmd_wavefront,
};

const ALIASES: Record<string, string> = {
  segment: "line", arrow: "vector", block: "mass", text: "label",
  hinge: "pivot", rope: "line", string: "line", streamline: "fieldline",
  coil: "spiral", helix: "spiral",
};

// Python's repr() for the strings used in error messages: single-quoted, with ' escaped.
function pyRepr(s: string): string {
  if (s.includes("'") && !s.includes('"')) return `"${s}"`;
  return `'${s.replace(/\\/g, "\\\\").replace(/'/g, "\\'")}'`;
}

function anchorKw(kw: string): [string, string, number, number] {
  const map: Record<string, [string, string, number, number]> = {
    center: ["middle", "central", 0, 0],
    left: ["end", "central", -8, 0],
    right: ["start", "central", 8, 0],
    above: ["middle", "auto", 0, -10],
    below: ["middle", "hanging", 0, 10],
  };
  return map[kw] ?? ["middle", "central", 0, 0];
}

function rangePair(s: string, lineno: number): [number, number] {
  if (!s.includes("..")) {
    throw new DiagramSyntaxError(lineno, `expected range 'a..b', got ${pyRepr(s)}`);
  }
  const idx = s.indexOf("..");
  return [pyFloat(s.slice(0, idx)), pyFloat(s.slice(idx + 2))];
}

function zigzag(a: Pt, b: Pt, teeth: number, amp: number): Pt[] {
  const d = unit(sub(b, a));
  const p: Pt = [-d[1], d[0]];
  const total = length(sub(b, a));
  const lead = total * 0.16;
  const start = add(a, mul(d, lead));
  const end = sub(b, mul(d, lead));
  const span = length(sub(end, start));
  const pts: Pt[] = [a, start];
  for (let i = 1; i < 2 * teeth; i++) {
    const t = i / (2 * teeth);
    const base = add(start, mul(d, span * t));
    const sign = i % 2 === 1 ? 1 : -1;
    pts.push(add(base, mul(p, amp * sign)));
  }
  pts.push(end, b);
  return pts;
}

// -- multi-panel figures ------------------------------------------------------
const PANEL_SEP = /^\s*-{3,}\s*$/;
const LAYOUT_RE = /^\s*layout\s*[:=]?\s*(row|horizontal|column|col|vertical|grid)\b(.*)$/i;
const COLS_RE = /\bcols\s*[:=]?\s*(\d+)/;
const LAYOUT_ALIASES: Record<string, string> = {
  horizontal: "row", row: "row",
  col: "column", vertical: "column", column: "column", grid: "grid",
};
const PANEL_GAP = 20.0;
const PANEL_TITLE_H = 26.0;

const f0 = (x: number): string => fixed(x, 0);
const f1 = (x: number): string => fixed(x, 1);

const xesc = (s: string): string =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

function splitlines(s: string): string[] {
  if (s === "") return [];
  const parts = s.split(/\r\n|\r|\n/);
  if (parts.length && parts[parts.length - 1] === "") parts.pop();
  return parts;
}

type Panelized = { layout: string; cols: number | null; panels: [string | null, string][] };

function panelize(source: string): Panelized | null {
  const lines = splitlines(source);
  let layout: string | null = null;
  let cols: number | null = null;
  let rest = lines;
  for (let i = 0; i < lines.length; i++) {
    const s = lines[i].trim();
    if (!s || s.startsWith("#")) continue;
    const m = LAYOUT_RE.exec(s);
    if (m) {
      layout = m[1].toLowerCase();
      const cm = COLS_RE.exec(m[2]);
      if (cm) cols = parseInt(cm[1], 10);
      rest = lines.slice(i + 1);
    }
    break; // only the first meaningful line may be the layout directive
  }

  if (layout === null && !rest.some((l) => PANEL_SEP.test(l))) return null;
  layout = LAYOUT_ALIASES[layout ?? "row"] ?? "row";

  const rawPanels: string[][] = [[]];
  for (const l of rest) {
    if (PANEL_SEP.test(l)) rawPanels.push([]);
    else rawPanels[rawPanels.length - 1].push(l);
  }

  const out: [string | null, string][] = [];
  for (const p of rawPanels) {
    let title: string | null = null;
    let body = [...p];
    for (let j = 0; j < body.length; j++) {
      const l = body[j];
      if (!l.trim()) continue;
      if (l.trim().startsWith("#")) {
        title = l.trim().replace(/^#+/, "").trim() || null;
        body = body.slice(0, j).concat(body.slice(j + 1));
      }
      break;
    }
    const src = body.join("\n").trim();
    if (src) out.push([title, src]);
  }
  return { layout, cols, panels: out };
}

function svgSize(svg: string): [number, number] {
  const w = parseFloat(/\bwidth="([\d.]+)"/.exec(svg)![1]);
  const h = parseFloat(/\bheight="([\d.]+)"/.exec(svg)![1]);
  return [w, h];
}

function compileSingle(source: string, title: string | null = null, grid = false, nudge = false): string {
  const compiler = new Compiler();
  compiler.execute(source);
  if (nudge) compiler.scene.nudgeLabels();
  return compiler.scene.toSvg(title, grid);
}

function compileMultipanel(
  p: Panelized, title: string | null, grid: boolean, nudge: boolean,
): string {
  const rendered: [string | null, string][] = p.panels.map(
    ([t, src]) => [t, compileSingle(src, null, grid, nudge)],
  );
  const sizes = rendered.map(([, svg]) => svgSize(svg));
  const n = rendered.length;
  const ncols = p.layout === "row" ? n : p.layout === "column" ? 1 : Math.max(1, p.cols ?? 2);
  const nrows = Math.ceil(n / ncols);
  const cellW = Math.max(...sizes.map(([w]) => w));
  const cellH = Math.max(...sizes.map(([, h]) => h));
  const th = rendered.some(([t]) => t) ? PANEL_TITLE_H : 0.0;
  const totalW = ncols * cellW + (ncols - 1) * PANEL_GAP;
  const totalH = nrows * (cellH + th) + (nrows - 1) * PANEL_GAP;

  const out: string[] = [
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${f1(totalW)} ${f1(totalH)}" ` +
      `width="${f0(totalW)}" height="${f0(totalH)}" ` +
      `font-family="Georgia, 'Times New Roman', serif">`,
  ];
  if (title) out.push(`<title>${xesc(title)}</title>`);
  for (let i = 0; i < rendered.length; i++) {
    const [ptitle, svg] = rendered[i];
    const [w, h] = sizes[i];
    const rowIdx = Math.floor(i / ncols);
    const colIdx = i % ncols;
    const cellX = colIdx * (cellW + PANEL_GAP);
    const cellY = rowIdx * (cellH + th + PANEL_GAP);
    if (ptitle) {
      out.push(
        `<text x="${f1(cellX + cellW / 2)}" y="${f1(cellY + th * 0.62)}" ` +
          `text-anchor="middle" dominant-baseline="middle" font-size="14" ` +
          `fill="currentColor">${xesc(ptitle)}</text>`,
      );
    }
    const px = cellX + (cellW - w) / 2;
    const py = cellY + th + (cellH - h) / 2;
    out.push(svg.replace("<svg ", `<svg x="${f1(px)}" y="${f1(py)}" `));
  }
  out.push("</svg>");
  return out.join("\n");
}

export function compileFigure(
  source: string, title: string | null = null, grid = false, nudge = false,
): string {
  const p = panelize(source);
  if (p !== null) return compileMultipanel(p, title, grid, nudge);
  return compileSingle(source, title, grid, nudge);
}
