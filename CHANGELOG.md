# Changelog

All notable changes to mtph are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com); this project uses [SemVer](https://semver.org).

## [Unreleased]

Toward v0.2 — making the format *honest* and giving it *feedback*.

### Added
- **Verifier QA harness — a committed mutation corpus + catch-rate report.** Before writing new
  checkers, mtph now *measures* the ones it has. `python/tools/gen_mutations.py` applies five small,
  realistic mutation operators (`signflip`, `factor`, `trig`, `power`, `unit`) to the annotated
  examples and writes a committed, diffable corpus (`spec/mutations/*.mtph` + `manifest.json`);
  `python/tools/mutation_report.py` runs `mtph verify` over it and prints a per-class **confusion
  table** — catch rate and false-positive rate, with `--assert-bar` for the published target
  (≥80% of seeded gross errors caught, <5% false positives). Each mutant is one textual slip that
  still parses and validates, tagged with the finding id that *should* catch it, so a *missed*
  mutant is counted honestly rather than hidden (P4). The corpus regenerates deterministically and
  is CI-gated exactly like the conformance gold. Curated examples (`incline`, `projectile-range`,
  `loop-the-loop`, `rotating-hoop`, …) gain `symbols:`/`test:`/`check:` annotations so the dimension
  and numeric checks have something to bite on. Dev tooling only — the format, `schema.json`, and
  both renderers are untouched, and every example still verifies `ok`.
- **Numeric spot-check of answers (`check:` + `test:`).** Dimensional analysis is blind to a
  numeric slip — `\tfrac12 mv^2` and `2mv^2` share a dimension. Now give an answer's symbols a
  numeric `test` value (a `symbols:` entry may be `{ dim, test }` instead of a bare dimension
  string) and the answer an expected `check` number, and `verify`'s new **`numeric` group**
  evaluates the answer's right-hand side at those values and confirms it matches (`numeric.mismatch`
  on a disagreement, `numeric.unverifiable` when a symbol lacks a `test`). This catches the classic
  dropped-factor-of-2 or flipped-sign an AI author leaves behind. The evaluator (`mathr.numeric`)
  reuses the conservative LaTeX tokenizer and, like the dimension analyzer, **bails rather than
  guess** — on `\log` (ambiguous base), an undeclared symbol, a complex/non-finite result, or
  shorthand like `\frac12` — so a reported mismatch is always real (P4). 1% tolerance (a gross-error
  check, not a precision test). Verify-only and Python-side; the JS renderer is untouched and
  conformance stays byte-identical. `spec/examples/pendulum-period.mtph` now declares `check: 2.007`;
  SPEC §6.3.1, AGENTS §3.
- **JavaScript port — the complete renderer (M1–M4).** The `js/` TypeScript package now reproduces
  the *entire* Python pipeline **byte-for-byte**: `parse` + `validate` (M1), `compileFigure`
  (M2 — all 46 DSL commands + aliases + multi-panel, incl. a faithful port of CPython's Mersenne
  Twister so seeded `gas` matches), `compilePlot` (M3 — all 5 modes + the safe evaluator + a
  Python-compatible `%.2f`), and `renderHtml` (M4 — the self-contained cdnjs-KaTeX document, the
  Claude-Artifact path). **76/76 conformance tests** cover parser DOM, every figure, every plot, and
  the full HTML render; CI asserts Python↔JS parity on every push. A `.mtph` now renders to a
  self-contained page entirely in the browser, no server.
- **Figure micro-animation (`anim=`).** Any figure command can carry `anim=spin` / `oscillate` /
  `along` (with `anim-period`, `anim-about`, `anim-swing`, `anim-amp`, `anim-dir`, `anim-path`,
  `anim-cw`) to animate the primitives it draws via SMIL — a spinning rotor, an oscillating
  spring-mass, a swinging pendulum (`anim=spin anim-swing=44`), a particle tracing a path. Three
  verbs by design, not a general animation system. It's **decoration**: a static SVG/PNG renderer
  ignores SMIL and shows the at-rest first frame, `verify`/`inspect` see the drawn geometry
  unchanged, and the viewBox auto-expands so motion never clips. Byte-identical across the Python
  and JS renderers (the SHM/swing use spline keyframes rather than per-sample trig, and a signed-zero
  normaliser keeps the emitted SVG identical). New example `spec/examples/pendulum-period.mtph`;
  SPEC §4.3b, AGENTS §4.3.
- **`<mtph-doc>` web component** — a one-tag embed of a live `.mtph` problem for any web page, LMS
  or blog. `<script src="mtph-doc.js">` registers the custom element; give it a problem via a
  `<script type="text/plain">` child (raw-text-safe), the element's text content, or a `src="…"`
  URL. It renders inside a sandboxed iframe fed the exact self-contained artifact HTML — so its
  CSS, KaTeX and quiz script never leak into (or out of) the host page — and the frame reports its
  height back (postMessage) so it grows to fit with no inner scrollbar. Attributes: `quiz`
  (self-check mode), `hide-answers` (statement only). A document with `params:` renders sliders and
  re-renders live on drag — an explorable, embeddable anywhere. Pure logic lives in
  `js/web/embed-core.ts` (unit-tested in Node); build with `npm run build:webcomponent`; see
  `playground/mtph-doc.html` for a live gallery. Thin wrapper over the parity-tested `renderHtml`,
  so it inherits byte-identical output.
- **The playground** (`playground/`, deploys to GitHub Pages) — a zero-server single-page editor:
  type `.mtph`, see it render live (figures, plots, LaTeX), and "Copy share link" packs the source
  into the URL fragment (lz-string) so every shared link carries its own document. Built from the JS
  port via esbuild (`npm run build:web`) and published by `.github/workflows/pages.yml`.
- **Self-quiz render mode (`render_html(quiz=True)` / `mtph render --quiz`).** Turns any rendered
  `.mtph` into a self-test: a **numeric** answer becomes an input box graded against the correct
  value within a (relative) `tolerance`, a **choice** answer becomes clickable options graded by
  index, and the full answer & solution sit behind a reveal. The grader is a self-contained inline
  script (no deps), so it works in an exported file or a Claude Artifact — not just the playground
  (which gets a "Quiz mode" toggle). Byte-identical across the Python and JS renderers. Combined
  with explorable params, a `.mtph` is now a complete study object: explore, then test yourself.
- **Explorable parameters (`params:`).** Declare `{ min, max, default, unit? }` parameters and
  reference them as `{{name}}` in figure/plot sources; the playground renders a **slider per param
  and re-renders on drag** — drag the launch angle, watch the trajectory reshape. Static output
  (`mtph render`/PNG, the reference DOM) substitutes the *default*, so it stays deterministic and the
  DOM keeps the template, never a baked-in number. `verify` gains a `params` group
  (`param.undefined`, `param.bad_range`). No static format — PDF, Markdown, even Jupyter without a
  kernel — can do this, and an AI authors it in three lines. New example `projectile-range`. (SPEC §6.4.)
- **Dimensional analysis (`verify`'s `dimension` group).** Declare a `symbols:` table
  (`a: acceleration`, `k: force/length`, `E: M L^2 T^-2`) and `verify` dimension-checks the answer
  expressions: `dimension.inconsistent` (a `+`/`-` of unlike dimensions, or a transcendental of a
  dimensional argument), `dimension.mismatch` (result ≠ the left-hand symbol or a numeric `unit`),
  and `dimension.bad_symbol`. Catches the classic AI-author slip (a dropped or stray factor)
  mechanically. Conservative by design — anything it can't fully resolve is reported `unknown`, never
  a false error. The biggest step from *verify the form* toward *verify the physics*. (SPEC §6.3.)
- **`mtph render --artifact`** — emit HTML tuned for a Claude Artifact: KaTeX from `cdnjs` (the only
  host the artifact sandbox's CSP allows), ~57 KB instead of ~560 KB inline. mtph's self-contained
  HTML renders as a claude.ai HTML artifact **today** (verified).
- **A curated example bank** — new thesis-grade problems spanning domains and features:
  `rotating-hoop` (bifurcation + multi-curve plot), `saddle-flow` (vector field), `earnshaw-trap`
  (vector field + implicit equipotential, Earnshaw's theorem), `two-expansions` (multi-panel figure,
  the entropy paradox). Each deploys a false attractor and verifies clean.
- **Part-coverage verification** — `verify` now checks that a multi-part statement (`(a)`, `(b)`, …)
  is answered: when the author uses per-part answers, it flags a part with no answer
  (`parts.missing_answer`) and an answer whose part isn't asked (`parts.stale_answer`). Ignores
  `(a)` inside math and respects the single-combined-answer style.
- **`figure.label_unsupported`** — figure labels are Unicode-mapped (not KaTeX); `verify` now warns
  when a label uses a command the mapper can't typeset (`\frac`, `\text`, `\mathbf`, …) so it no
  longer renders as literal text silently. The label renderer's supported/unsupported set is now
  documented sharply in SPEC §4 and AGENTS.
- **`mtph audit` mentor mode** — holistic, difficulty-aware notes that combine signals ("claims
  difficulty 5 but has no figure, no worked solution, and doesn't name its insight") instead of
  just listing missing fields.
- **`grading:` rubric** — optional front-matter marking scheme: a list of `{part, points,
  criteria}` rendered as a points table (with a total) in the answer/solution aside. Criteria may
  contain `$…$` math (use YAML-safe quoting in front-matter).
- **`vectorfield` & `implicit` plot modes** — `mode: vectorfield` (`u(x,y)`/`v(x,y)` → a grid of
  arrows) and `mode: implicit` (`F(x,y)=…` → the curve `F=0` via marching squares), both
  equal-aspect. A new two-variable safe evaluator backs them (still no `eval`). Plot marks now take
  `color=` (`mark: (1,1) label="P" color=red`).
- **`zigzag` figure command** — a zigzag line (cutaway / boundary indicator), distinct from `spring`.
- **`mtph figure --nudge`** — push overlapping labels apart in the rendered output (opt-in; never
  edits the source file — the diff is untouched).
- **`mtph audit`** — `verify` plus advisory structural nudges (no figure/answer/solution/difficulty)
  and the hard-problem checklist printed for human judgment. Advisories are `info`; only a `verify`
  error sets a non-zero exit.
- **`mtph doctor` / `mtph init`** — `doctor` reports environment health (Python, mtph, KaTeX vendor
  status, and which optional extras are installed, each missing one paired with its install command;
  `--format json`). `init` is the one-shot setup: ensure KaTeX is vendored, then self-test a render.
- **`mtph prompt`** — print the authoring card (`AGENTS.md`, plus `thesis/card.md` with `--full`) to
  stdout, so a tool-using AI can load its instructions locally without filesystem spelunking.
- **`mtph new --template <id>`** — scaffold a structurally-complete, *verifiable* skeleton for a
  common problem shape (`charged-oscillator`, `thermal-process`, `coupled-pendulum`) with content
  slots to fill. `--template list` lists them.
- **`mtph install-viewer --refresh-backend`** — reinstall the current source into the native
  viewer's isolated backend venv (`~/.mtph/venv`) in one step, so new DSL commands / block types
  render in the double-click viewer instead of erroring as "unknown command".
- **Notation packs** — declare `notation: irodov | american | jee` in front-matter (no new
  syntax; still plain LaTeX). `verify` checks convention drift (`notation.mixed_vectors`: `\mathbf`
  under a `\vec` tradition, or mixing both); no declaration → the `notation` group reports
  `unknown`, never a false `ok`. `mtph prompt --notation <id>` prints the pack's compact style card.
- **`thesis/card.md`** — the 885-line doctrine condensed to ~100 lines (7 pillars, 8 techniques,
  domain-collision matrix, difficulty rubric, anti-AI template, design checklist). `AGENTS.md` §0
  now points at the card instead of "read the whole thesis every time"; the required read dropped
  from ~2,100 lines to ~475.
- **`verify-mtph` GitHub Action** — on PRs/pushes that touch `*.mtph`, verify the changed problem
  files, post a findings table to the run summary and a sticky PR comment, and fail the job on any
  error. Catches silent regressions (`\\frac`, dangling `\ref`, undefined anchors, plot gaps) in CI.
- **Body `answer` / `solution` blocks** — author answers and worked solutions as ` ```answer `
  (with `part=` / `type=`) and ` ```solution ` blocks in the body, instead of YAML front-matter.
  This removes the front-matter backslash-escaping trap entirely, supports multi-part answers,
  and lets a solution embed figures/plots/math (via longer ` ````solution ` fences). Front-matter
  `answer:`/`solution:` still work; body blocks take precedence. `mtph new` now scaffolds this style.
- **`mtph verify`** — graduated, machine-parseable verification (JSON or human). Catches silent
  failures `validate` can't: doubled backslashes (`\\frac`) that render as literal text, undefined
  figure anchors, plot domain gaps/empties, bare subscripts in prose, and overlapping figure
  labels. Every finding has a stable `id`, a `severity`, and a `fix`; top-level status is
  `ok | warnings | error`, with `unknown` reserved for things only a human can judge.
- **`mtph inspect`** — a figure's resolved scene as data (JSON/human): logical extent, every
  resolved anchor, per-element bounds/length/angle, and label-overlap diagnostics. Lets an AI
  place figure elements correctly without rendering an image.
- **`mtph figure`** — render only the figure(s) to SVG, for a fast figure-authoring loop.
- **`mtph dev`** — a watch loop: the live-reload reader plus continuous `verify` feedback in the
  terminal, so findings (with fixes) update as you edit. One command instead of edit/render/look.
- **`--grid`** on `mtph render` and `mtph figure` — overlay a logical coordinate grid.
- **More figure DSL** — `current` (labelled I-arrow for circuits), `spiral`/`coil`/`helix`
  (Archimedean), and **fill patterns** `fill=hatch | crosshatch | dots` on any shape
  (cross-sections, materials, shaded regions).
- **Multi-panel figures** — one `figure` block can hold several independent sub-scenes for
  before/after, two cases, or insets: a leading `layout row | column | grid cols=N` directive
  and/or `---` separators, with a leading `#` line captioning each panel. Each panel auto-fits on
  its own and is placed as a nested viewport; `verify` and `inspect` understand panels too
  (`inspect` returns a `panels` list, overlaps detected per panel).
- **Numbered equations & cross-references** — tag a display equation with `\label{eq:key}` to
  number it, and cite it from prose with `\ref{eq:key}` (renders as a clickable `(n)`). Only
  labelled equations are numbered. `\label`/`\ref` are resolved by mtph and stripped before KaTeX.
  `verify` adds `ref.undefined` (a `\ref` with no matching label) and `ref.duplicate_label`.
- **Parametric & polar plots** — ` ```plot ` with `mode: parametric` (`x(t)`/`y(t)`) or
  `mode: polar` (`r(theta)`), rendered equal-aspect so trajectories, orbits, Lissajous, and rose
  curves aren't distorted. The expression evaluator now binds any variable name, not just `x`
  (still no `eval`), and range endpoints accept constant expressions like `0..2*pi`.
- **Dark mode** — rendered HTML now follows `prefers-color-scheme`. Figures and plots draw their
  default ink with `currentColor`, so black-on-white diagrams invert to light-on-dark legibly
  instead of vanishing; label halos and knock-out fills re-theme to the dark paper. Standalone
  SVG and raster output stay black-on-white (no CSS context → `currentColor` is black).
- **Font subsetting** — self-contained HTML now inlines only the KaTeX font families a document
  actually uses, dropping Fraktur / Script / Typewriter / SansSerif / Caligraphic when unused
  (a typical problem sheds ~120 KB). Safe and on by default; `render_html(subset=False)` opts out.
- **`mtph render --cdn`** — link KaTeX from a CDN instead of inlining it: ~8 KB HTML that needs
  the network at view time. Self-contained inlining stays the default.
- **`mtph figure -o out.png`** — figure/plot SVG → PNG without a headless browser, via the
  lightweight `cairosvg` rasterizer (new optional `[raster]` extra). Full-*page* PNG still uses
  the browser-based `[export]` path, since rasterizing KaTeX's HTML/CSS faithfully needs a browser.

### Fixed
- **Sub/superscript labels rendered as giant glyphs in PNG** — `font-size="72%"` + `baseline-shift`
  (which cairosvg ignores/mis-scales) are replaced by absolute font-size + `dy`, so subscripts and
  superscripts render correctly in cairosvg *and* browsers.
- **Vector fields with singularities** (Coulomb/gravity 1/r²) no longer collapse to nubs — arrow
  length now uses a soft saturating scale `L·mag/(mag+median)` instead of normalizing by the max,
  so a near-charge spike saturates instead of shrinking every other arrow.
- **A labelled `charge` no longer self-overlaps its own sign glyph** (spurious `label_overlap`);
  the label offset now clears the `+`/`−` sign.
- **`dash=` is accepted as an alias for `style=`** on figure statements — it was a natural guess
  that was silently ignored, rendering a solid line.
- Format-version consistency: the current format is **0.2** everywhere (all examples, SPEC title +
  identity, DOM example, README, `SCHEMA_VERSION`, schema `$id`). `0.1` files still validate (0.2 is
  a backward-compatible superset); the package release version (`__version__`) is tracked separately.
- A bad LaTeX command now renders **visibly wrong** (its source, in red) rather than silently —
  the KaTeX init sets `throwOnError:false, errorColor:"#cc0000"` explicitly (principle P1).
- Ordered lists keep the author's numbering (`<ol start="N">`), so `1.` / blank / `2.` renders
  `1.`, `2.` instead of resetting to `1.`, `1.`.
- Figure labels no longer rely on SVG `paint-order` for their halo (browsers honour it, but
  cairosvg and many SVG tools ignore it and paint the halo *over* the glyphs, erasing them). The
  halo is now a separate underlay, so labels read correctly in every renderer, not just browsers.

## [0.1.0] — initial alpha

The first public release: the `.mtph` format + a Python reference implementation.

### Format
- `.mtph` = YAML front-matter + a Markdown-style body with `prose`, `math` (LaTeX),
  `figure` (diagram DSL), and `plot` (function plots) blocks.
- Canonical JSON Schema (`spec/schema.json`) as the source of truth; full spec in
  `spec/SPEC.md`.

### Rendering
- Math via **KaTeX**, bundled and inlined for fully **offline** rendering (real glyphs).
- Figure DSL → SVG, including a freeform Bézier **`path`** ("draw anything") plus helpers for
  mechanics, **fields & charges** (`charge`, `dipole`, `bfield`, `fieldline`, `gaussian`),
  **3-D & frames** (`axes3d`, `sphere`, `omega`), **thermo/fluids/waves** (`container`,
  `piston`, `gas`, `heat`, `wavefront`), circuits and optics. Labels carry a white halo for
  legibility over busy backgrounds.
- Function plots with a safe expression evaluator (no `eval`).
- Output targets: self-contained **HTML**, plus **PNG/SVG** via the optional `[export]` extra.

### Tooling
- CLI: `mtph validate | render | view | open | new | install-viewer | vendor-katex`.
- `mtph view` — a live reader (Reveal-answer, Source panel, live-reload, folder gallery).
- `mtph install-viewer` (macOS) — a native Swift/WKWebView app that opens `.mtph` in its own
  window on double-click.
- Robustness: the renderer never crashes to empty output; any error shows a readable page.

### For AI authors
- `AGENTS.md` — operating manual that turns `thesis/phythesis.md` (the hard-problem doctrine)
  into an authoring workflow, with the full DSL reference, Soviet/American notation guidance,
  a diagram cookbook, and a self-audit checklist.

### Packaging
- Published to **PyPI**: `pip install mtph` (also installable from `git+https://…` or a clone),
  with KaTeX + schema bundled so a fresh machine works offline with no extra steps.

[Unreleased]: https://github.com/Saurav0989/mtph/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Saurav0989/mtph/releases/tag/v0.1.0
