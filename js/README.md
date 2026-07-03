# mtph — JavaScript / TypeScript

The browser/npm implementation of the `.mtph` format, sharing the **same `spec/schema.json`** as the
Python reference. Built validator-first; it is the gateway to a live browser viewer, a web
validator, and rendering `.mtph` as a Claude Artifact.

## Status

- **M0 — conformance harness** ✓ — `python/tools/gen_conformance.py` freezes the Python reference's
  DOM into `spec/conformance/`; this package must reproduce it.
- **M1 — validator** ✓ — `parse` (`.mtph` → DOM) + `validate` (ajv, Draft 2020-12).
- **M2 — figure renderer** ✓ — `compileFigure` (DSL → SVG): all 46 commands + 10 aliases,
  multi-panel layout, LaTeX label runs, and a faithful port of CPython's Mersenne Twister
  (so seeded `gas` scatters match).
- **M3 — plot renderer** ✓ — `compilePlot` (spec → SVG): all 5 modes (function, parametric,
  polar, vectorfield, implicit), the safe shunting-yard evaluator, "nice" ticks, and a
  Python-compatible `%.2f` (round half-to-even).
- **M4 — document renderer** ✓ — `renderHtml` (DOM → self-contained HTML) via the cdnjs KaTeX
  path (the one that renders inside a Claude Artifact): math-safe Markdown, equation
  `\label`/`\ref`, answers (expression/numeric/choice/freeform), solutions and grading, dark
  mode. **76/76 conformance tests pass** — parser DOM, every figure, every plot, *and* the full
  HTML document render are all *byte-identical* to the Python reference.

The port is feature-complete: a `.mtph` string goes to a self-contained HTML page — the same
bytes the Python `mtph render --artifact` produces — entirely in the browser, no server.

- **`<mtph-doc>` web component** ✓ — a one-tag embed built on the renderer (`web/mtph-doc.ts`,
  pure core in `web/embed-core.ts`). It renders a problem inside a sandboxed iframe (fed the exact
  artifact HTML, isolated), auto-sizes via a postMessage height reporter, and turns `params:` into
  live sliders. Attributes: `src`, `quiz`, `hide-answers`. Build: `npm run build:webcomponent`;
  gallery: `playground/mtph-doc.html`.

## Use

```ts
import { parse, validate, renderHtml, compileFigure, compilePlot } from "mtph";

const dom = parse(source);        // .mtph text → canonical DOM (same shape as the Python impl)
const errors = validate(dom);     // [] when valid, else human-readable messages

// render a whole document to a self-contained HTML page (KaTeX from cdnjs — the Artifact path)
const page = renderHtml(dom);

// or render a single figure / plot block's source straight to an SVG string
const svg = compileFigure(dom.blocks.find((b) => b.type === "figure")!.source as string);
```

## Develop

```bash
npm install
npm test        # conformance parity against the Python-generated corpus
npm run typecheck
```

**Parity is the contract.** Never edit `spec/conformance/expected/` by hand — regenerate it from the
Python reference (`python python/tools/gen_conformance.py`) and make the JS match. CI runs both and
fails on drift.
