# mtph

[![PyPI](https://img.shields.io/pypi/v/mtph.svg)](https://pypi.org/project/mtph/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Status](https://img.shields.io/badge/status-alpha-orange)

**An AI-native file format for math & physics problems.**

One plain-text file an AI can write and a human can read: real symbolic notation
(true fraction bars, `∫`, Greek, vectors, tensors — not ASCII like `/`) **and** diagrams-as-code
(free-body diagrams, fields, circuits, 3-D, thermodynamics, function plots — or *any* freeform
shape), rendered crisply. **No PDF, no OCR, no images** — the `.mtph` file *is* the semantic
source, equally readable by an AI, a human, and `git`.

```
.mtph  ──parse──▶  validated DOM  ──render──▶  crisp HTML · PNG · SVG · a native reader
 │ LaTeX for math (→ real glyphs via KaTeX)
 │ a small diagram DSL for figures (→ SVG)
 └ a function-plot mini-language (→ SVG)
```

**▶ Try it in your browser — no install:** the [**playground**](https://saurav0989.github.io/mtph/)
is a live editor that renders `.mtph` client-side (figures, plots, LaTeX) and turns any problem
into a share link that carries its own source. (Powered by the JavaScript port in [`js/`](js/),
which reproduces the Python renderer byte-for-byte; served from [`playground/`](playground/) on
GitHub Pages — zero server.)

**▶ Embed a problem anywhere:** the [`<mtph-doc>`](playground/mtph-doc.html) web component renders a
live `.mtph` — figures, LaTeX, self-check quizzes, even `params:` sliders — from one `<script>` tag,
with nothing to install on the host page:

```html
<script src="mtph-doc.js"></script>
<mtph-doc><script type="text/plain">
---
mtph: "0.2"
title: My problem
---
A block of mass $m$ on an incline of angle $\theta$ …
</script></mtph-doc>
```

---

## Install

Everything (including the math fonts) is bundled — it works **offline, with zero setup**.
Requires Python 3.9+.

```bash
pip install mtph
```

Optional extras:

```bash
pip install "mtph[raster]"   # figure/plot PNG, browserless (cairosvg)
pip install "mtph[export]"   # full-page PNG/SVG export   (also: playwright install chromium)
pip install "mtph[app]"      # native desktop reader window (pywebview)
pip install "mtph[cas]"      # symbolic equivalence in verify (sympy) — deeper solution checks
```

> **PNG, honestly.** A figure or plot is pure SVG, so turning *it* into PNG needs only a vector
> rasterizer — `mtph figure problem.mtph -o fig.png` works with the light `[raster]` extra, no
> 300 MB browser. A *full page* (math + prose laid out by KaTeX's HTML/CSS) can only be
> rasterized faithfully by a browser engine, so `mtph render … -o page.png` still uses `[export]`.

> **Bleeding edge:** to run ahead of the latest release, install from source —
> `pip install git+https://github.com/Saurav0989/mtph` (or clone and `pip install .`).

---

## Try it in 30 seconds

```bash
mtph init                        # one-shot setup + self-test (after pip install)
mtph new problem.mtph            # scaffold a starter problem (--template for a known shape)
mtph view problem.mtph           # open a live reader (auto-refreshes as you edit)
mtph render problem.mtph -o problem.html    # self-contained HTML (dark-mode aware)
mtph render problem.mtph --cdn -o page.html # tiny HTML, KaTeX from a CDN
mtph figure problem.mtph -o fig.png         # just the figure → PNG (needs mtph[raster])
mtph verify problem.mtph         # graduated checks (silent errors + fixes, as JSON)
mtph audit problem.mtph          # verify + structural nudges + the hard-problem checklist
mtph inspect problem.mtph        # a figure's resolved scene as data (coords, overlaps)
mtph validate problem.mtph       # fast schema-only gate
mtph render problem.mtph --badge -o problem.html  # HTML + an honest "solution checked ✓" line
mtph render spec/examples/(problem path) -o (problem).html #create the html file reg .mtph file.
```

On macOS, make `.mtph` open in a **native window by double-clicking** (like a PDF):

```bash
mtph install-viewer
```

---

## Use it with your AI ✨

mtph is built so an AI can **author hard problems end-to-end**. Point your assistant at two
files and let it work:

1. **[`AGENTS.md`](AGENTS.md)** — the operating manual: how to write `.mtph`, the full diagram
   DSL, notation conventions, and a quality checklist.
2. **[`thesis/card.md`](thesis/card.md)** — the doctrine of what makes a physics problem genuinely
   *hard*, condensed to ~100 lines (7 pillars, 8 techniques, the design checklist). The full
   [`thesis/phythesis.md`](thesis/phythesis.md) is there for depth.

Or just run **`mtph prompt --full`** — it prints both to stdout, so an AI can load its instructions
locally with no filesystem spelunking.

A typical prompt:

> *Read `AGENTS.md` and `thesis/phythesis.md`, then create a hard rotational-dynamics problem
> as a `.mtph` file with a free-body diagram. Validate and render it.*

The AI writes plain text; `mtph render` turns it into crisp math + figures. You read it.

**Render it as a Claude Artifact.** mtph's HTML is fully self-contained, so it drops straight into a
[claude.ai](https://claude.ai) **HTML artifact** and renders in the side panel — math, figures,
plots, and all:

```bash
mtph render spec/examples/earnshaw-trap.mtph --artifact -o problem.html
# then paste problem.html's contents into a claude.ai HTML artifact
```

`--artifact` loads KaTeX from cdnjs (the host the artifact sandbox allows) for a ~57 KB file; plain
`mtph render` inlines everything (~560 KB, zero network).

**Keep a problem bank honest in CI.** The bundled [`verify-mtph`](.github/workflows/verify.yml)
GitHub Action runs `mtph verify` on every changed `.mtph` in a PR, comments the findings, and
fails on any error — so a doubled backslash, a dangling `\ref`, or an undefined figure anchor
never lands silently.

**Content that proves itself.** Give the symbols `test:` values and `verify` doesn't just lint —
it *reads the math*: it evaluates the answer, and walks the equation chain inside the `solution`
step by step, flagging any step that doesn't hold and any result that disagrees with the declared
answer ([SPEC §6.3.2](spec/SPEC.md)). On a committed corpus of deliberately-broken problems the
checkers catch **82%** of seeded gross errors at **0%** false positives (bar: ≥80% / <5%, enforced
in CI); the honest misses are documented, not hidden. `mtph render --badge` then stamps a
*“solution checked ✓”* line — a claim about exactly what was verified, nothing more.

---

## What a `.mtph` file looks like

````markdown
---
mtph: "0.2"
title: Block on a frictionless incline
subject: physics
---

A block of mass $m$ rests on a **frictionless** incline of angle $\theta$.

$$\sum F_\parallel = mg\sin\theta = ma$$

```figure
incline angle=30 length=6
mass m at=incline.mid size=0.9 label="m"
force from=m dir=down     label="mg"
force from=m dir=perp-out label="N"
angle at=incline.base from=0 to=30 value="\theta"
```

```answer
a = g\sin\theta
```
````

## What you can express

- **Math** — full LaTeX (rendered to real glyphs by KaTeX, bundled offline). Any symbol:
  `\frac \int \oint \nabla \hbar \langle\psi| \vec B \otimes \zeta(3)` …
- **Diagrams** — a compact DSL compiled to SVG: mechanics (`incline`, `mass`, `force`,
  `pendulum`, `pulley`, `spring`…), fields & charges (`charge`, `dipole`, `bfield`,
  `fieldline`, `gaussian`), 3-D & frames (`axes3d`, `sphere`, `omega`), thermo/fluids/waves
  (`container`, `piston`, `gas`, `heat`, `wavefront`), circuits, optics — and **`path`**, a
  freeform Bézier primitive to draw *anything*.
- **Plots** — `f(x) = …` function plots with axes, grids, marks.

Full reference: **[`spec/SPEC.md`](spec/SPEC.md)**. Validation schema: **[`spec/schema.json`](spec/schema.json)**.

## The reader

`mtph view` is a dedicated reader (not a PDF, not a raw browser tab): a **Reveal-answer**
toggle so you can solve first, a **Source** panel showing the raw `.mtph`, live-reload on save,
and a searchable **gallery** when you point it at a folder (`mtph view ./problems/`).

---

## Project layout

```
spec/        the format — SPEC.md, schema.json, examples/*.mtph
thesis/      the doctrine of hard-problem design (phythesis.md)
AGENTS.md    the AI authoring manual
python/      the reference implementation (the `mtph` package + tests)
```

## Docs

| File | What |
|------|------|
| [`AGENTS.md`](AGENTS.md) | How an AI should author `.mtph` problems |
| [`spec/SPEC.md`](spec/SPEC.md) | The `.mtph` format + full diagram DSL |
| [`thesis/phythesis.md`](thesis/phythesis.md) | What makes a physics problem hard |
| [`spec/examples/`](spec/examples) | Worked example problems |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Dev setup & how to contribute |
| [`CHANGELOG.md`](CHANGELOG.md) | Release notes |

## Status & roadmap

**Format v0.2 (current), Python reference implementation:** the format + renderer
(validate/**verify**/**audit**/**inspect**/render/**figure**/**dev**/view/open), the full diagram
DSL, five plot modes (function, parametric, polar, vector field, implicit), multi-panel figures,
numbered equations (`\label`/`\ref`), body answer/solution blocks, grading rubrics, notation packs,
dark mode, a CI verify Action, and the AI authoring layer (`thesis/card.md`, `mtph prompt`). `0.1`
files still validate and render. The macOS native viewer opens `.mtph` on double-click.

Next: the **npm/browser** implementation (sharing the same `schema.json`) — the gateway to a live
web viewer, a hosted validator, and shareable links. See [`js/`](js/) for the port in progress.

## Contributing

Issues and PRs welcome — see [`CONTRIBUTING.md`](CONTRIBUTING.md). The golden rule:
`spec/schema.json` is the source of truth, and any new DSL/format feature ships with a spec
entry, a renderer, and a test.

## License

MIT — see [LICENSE](LICENSE). Bundles [KaTeX](https://katex.org) (MIT) for offline math rendering.
