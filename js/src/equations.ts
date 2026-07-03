// Equation numbering and cross-references (\label / \ref). A faithful port of
// python/src/mtph/render/equations.py.
//
// A display-math block carrying \label{key} gets a number; \ref{key} in prose becomes a
// clickable (n). Only labelled equations are numbered. KaTeX never sees \label/\ref: \label is
// stripped before the LaTeX reaches the browser, and \ref is resolved to a link or bare number.

import type { BlockDom } from "./model.js";

const LABEL_RE = /\\label\{([^}]*)\}/g;
const REF_RE = /\\ref\{([^}]*)\}/g;

export type Labels = Map<string, [number, string]>; // key -> (number, html anchor id)

function slug(key: string): string {
  const s = key.trim().replace(/[^A-Za-z0-9]+/g, "-").replace(/^-+|-+$/g, "").toLowerCase();
  return s.startsWith("eq") ? s : `eq-${s}`;
}

function* iterMath(blocks: BlockDom[]): Generator<BlockDom> {
  for (const b of blocks) {
    if (b.type === "math") yield b;
    else if (b.type === "solution") yield* iterMath((b.blocks as BlockDom[]) ?? []);
  }
}

export function collectLabels(blocks: BlockDom[]): Labels {
  const labels: Labels = new Map();
  for (const b of iterMath(blocks)) {
    for (const m of String(b.latex).matchAll(LABEL_RE)) {
      const key = m[1].trim();
      if (key && !labels.has(key)) labels.set(key, [labels.size + 1, slug(key)]);
    }
  }
  return labels;
}

export function labelOf(latex: string): string | null {
  const m = /\\label\{([^}]*)\}/.exec(latex);
  return m ? m[1].trim() : null;
}

export function stripLabel(latex: string): string {
  return latex.replace(LABEL_RE, "").trim();
}

/** Inside math, a \ref becomes the bare number (KaTeX renders it); unknown → "?". */
export function subRefsMath(latex: string, labels: Labels): string {
  return latex.replace(REF_RE, (_m, k) => {
    const entry = labels.get(String(k).trim());
    return entry ? String(entry[0]) : "?";
  });
}

/** In already-rendered prose HTML, turn \ref{key} into a link — but never inside a $…$ / $$…$$
 *  span (protect math first). */
export function subRefsHtml(rendered: string, labels: Labels): string {
  const store: string[] = [];
  const stash = (m: string): string => {
    store.push(m);
    return `\x00R${store.length - 1}\x00`;
  };
  let s = rendered.replace(/\$\$[\s\S]*?\$\$/g, stash);
  s = s.replace(/\$[^$]+?\$/g, stash);
  s = s.replace(REF_RE, (_m, k) => {
    const key = String(k).trim();
    const entry = labels.get(key);
    if (entry) return `<a class="eqref" href="#${entry[1]}">(${entry[0]})</a>`;
    return "(?)";
  });
  return s.replace(/\x00R(\d+)\x00/g, (_m, n) => store[parseInt(n, 10)]);
}
