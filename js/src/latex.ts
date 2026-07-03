// Figure-label LaTeX → Unicode runs. Port of python/src/mtph/mathr/latex.py (the label side).

// Greek + symbol table covering physics/math figure labels (keys are the LaTeX commands).
export const SYMBOLS: Record<string, string> = {
  "\\alpha": "α", "\\beta": "β", "\\gamma": "γ", "\\delta": "δ",
  "\\epsilon": "ε", "\\varepsilon": "ε", "\\zeta": "ζ", "\\eta": "η",
  "\\theta": "θ", "\\vartheta": "ϑ", "\\iota": "ι", "\\kappa": "κ",
  "\\lambda": "λ", "\\mu": "μ", "\\nu": "ν", "\\xi": "ξ", "\\pi": "π",
  "\\rho": "ρ", "\\sigma": "σ", "\\tau": "τ", "\\upsilon": "υ",
  "\\phi": "φ", "\\varphi": "φ", "\\chi": "χ", "\\psi": "ψ", "\\omega": "ω",
  "\\Gamma": "Γ", "\\Delta": "Δ", "\\Theta": "Θ", "\\Lambda": "Λ",
  "\\Xi": "Ξ", "\\Pi": "Π", "\\Sigma": "Σ", "\\Phi": "Φ", "\\Psi": "Ψ",
  "\\Omega": "Ω",
  "\\infty": "∞", "\\partial": "∂", "\\nabla": "∇", "\\times": "×",
  "\\cdot": "·", "\\pm": "±", "\\mp": "∓", "\\leq": "≤", "\\geq": "≥",
  "\\neq": "≠", "\\approx": "≈", "\\propto": "∝", "\\sum": "∑",
  "\\int": "∫", "\\sqrt": "√", "\\angle": "∠", "\\circ": "∘",
  "\\hbar": "ℏ", "\\ell": "ℓ", "\\prime": "′", "\\degree": "°",
  "\\rightarrow": "→", "\\to": "→", "\\Rightarrow": "⇒",
  "\\leftarrow": "←", "\\parallel": "∥", "\\perp": "⊥",
};

const reEsc = (s: string): string => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
// longest command first so \varepsilon matches before \epsilon
const SYM_RE = new RegExp(
  Object.keys(SYMBOLS).sort((a, b) => b.length - a.length).map(reEsc).join("|"),
  "g",
);

const HAT = "̂", BAR = "̄", OVERLINE = "̅", DOT = "̇",
  DDOT = "̈", TILDE = "̃";

export function latexToUnicode(input: string): string {
  let s = input.trim();
  if (s.startsWith("$") && s.endsWith("$")) s = s.slice(1, -1);

  // \vec{X} -> X (the over-arrow glyph is missing from common serif fonts)
  s = s.replace(/\\vec\{([^}]*)\}/g, "$1").replace(/\\vec\s+(\w)/g, "$1");
  for (const [cmd, mark] of [
    ["hat", HAT], ["bar", BAR], ["overline", OVERLINE],
    ["dot", DOT], ["ddot", DDOT], ["tilde", TILDE],
  ] as const) {
    s = s.replace(new RegExp(`\\\\${cmd}\\{([^}]*)\\}`, "g"), (_m, g1) => g1 + mark);
    s = s.replace(new RegExp(`\\\\${cmd}\\s+(\\w)`, "g"), (_m, g1) => g1 + mark);
  }
  s = s.replace(SYM_RE, (m) => SYMBOLS[m]);
  s = s.replace(/\\,/g, " ").replace(/\\;/g, " ").replace(/\\!/g, "");
  s = s.replace(/\\\{/g, "{").replace(/\\\}/g, "}");
  return s;
}

export type Run = [string, "n" | "sub" | "sup"];

/** Split a label into (text, kind) runs, handling `_x`, `_{net}`, `^2`, `^{-1}`. */
export function labelRuns(input: string): Run[] {
  const s = latexToUnicode(input);
  const runs: Run[] = [];
  let buf = "";
  let i = 0;
  const n = s.length;
  while (i < n) {
    const c = s[i];
    if ((c === "_" || c === "^") && i + 1 < n) {
      if (buf) {
        runs.push([buf, "n"]);
        buf = "";
      }
      const kind = c === "_" ? "sub" : "sup";
      i += 1;
      if (s[i] === "{") {
        let j = s.indexOf("}", i);
        if (j === -1) j = n;
        runs.push([s.slice(i + 1, j), kind]);
        i = j + 1;
      } else {
        runs.push([s[i], kind]);
        i += 1;
      }
    } else {
      buf += c;
      i += 1;
    }
  }
  if (buf) runs.push([buf, "n"]);
  return runs;
}

const escXml = (s: string): string =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

/** Render runs to SVG <tspan>s with absolute font-size + dy (robust in cairosvg AND browsers). */
export function subSupSpans(runs: Run[], size: number): string {
  const out: string[] = [];
  let shift = 0;
  const subDy = size * 0.3, supDy = -size * 0.42, subSize = size * 0.72;
  for (const [txt, kind] of runs) {
    const target = kind === "sub" ? subDy : kind === "sup" ? supDy : 0;
    const fs = kind !== "n" ? ` font-size="${subSize.toFixed(1)}"` : "";
    out.push(`<tspan dy="${(target - shift).toFixed(2)}"${fs}>${escXml(txt)}</tspan>`);
    shift = target;
  }
  return out.join("");
}
