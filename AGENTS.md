# AGENTS.md — Authoring `.mtph` physics problems

You are an AI about to **create a physics problem** as a `.mtph` file. This document is your
operating manual. Follow it exactly.

---

## 0. Prime directive — read before you write a single line

1. **Read [`thesis/card.md`](thesis/card.md) first** — the condensed doctrine (~100 lines) of
   what makes a physics problem *hard*. (`mtph prompt --full` prints it together with this
   manual.) Consult the full [`thesis/phythesis.md`](thesis/phythesis.md) only for depth on a
   specific pillar or technique. The card tells you **what** to build; this manual tells you
   **how** to express it as `.mtph`.
2. Your output is **one `.mtph` file** that is simultaneously:
   - a genuinely hard problem by the thesis's standard (not merely long/tedious), and
   - **rendered crisply** — real math glyphs (LaTeX) and a precise figure (the DSL).
3. **Verify before you finish.** Run `mtph verify` (fix every `error`), `mtph inspect` your
   figures, then `mtph render` and *look at the output*. A problem you have not verified and
   visually checked is not done.

> The `.mtph` file is plain UTF-8 text. It is the *semantic source* — readable directly by you,
> a human, and `git`. Never think in terms of images/PDF; think in terms of LaTeX + the DSL.

---

## 1. The bar (the thesis, distilled into rules)

**Target quadrant:** high conceptual depth + *deceptively simple* setup. The statement fits in
~2 short paragraphs; the solution fits on ~1–2 pages; the gap between reading it and writing
the first correct line should cost hours. **Hard ≠ complex.** Never reach for difficulty by
piling on quantities or steps.

**Defeat BOTH solvers.** Aim at the middle column — properties that break humans *and* AI:

| Attacks humans                  | Attacks both (AIM HERE)        | Attacks AI                         |
|---------------------------------|--------------------------------|------------------------------------|
| Einstellung (wrong schema)      | Non-obvious framing required   | Template hallucination             |
| Working-memory overflow         | Two principles inseparably coupled | No self-verification           |
| Anchoring on first framing      | False surface similarity       | Compositional breakdown            |
| P-prim (deep intuition is wrong)| Under-specification (model first) | 3D/vector blindness             |
| Algebra slips under pressure    | Symmetry hidden in wrong frame | Over-thinking / principle-first blindness |

**Deploy at least 3 of the 7 Pillars** (full definitions + examples in
[`thesis/card.md`](thesis/card.md)): ① False Attractor ② Necessary Insight ③ Progressive
Dependency ④ Domain Collision ⑤ Physical Modeling First ⑥ Symmetry Camouflage ⑦ Limiting-Case
Trap.

**Useful techniques** (pick what fits): reference-frame disguise; conservation-law-that-isn't;
coupled-ODE surprise; wrong-intuition setup; cascading approximation; missing-equation; the
dimensional trap; stability inversion. *(Definitions in the card / Part V of the thesis.)*

**Prefer under-exploited domains** (outside training distributions, little prior art):
non-equilibrium thermodynamics, soft matter, plasma physics, nonlinear dynamics/chaos,
elasticity beyond statics, active/biological matter — and their **collisions** (Part VII).

---

## 2. The authoring workflow (run every time)

1. **Read the thesis.** Internalise the target and the pillars.
2. **Choose a domain / collision** — favour the under-exploited list.
3. **Design the kernel:** pick the *one* Necessary Insight and the *one* False Attractor that
   points away from it. If you can't name both in a sentence each, the problem isn't hard yet.
4. **Draft parts (a)–(e)** with genuine **progressive dependency**; make the dependency
   *implicit* (physically necessary), not "use your answer from (b)".
5. **Decide the under-specification** — what you deliberately leave for the solver to model.
6. **Write the `.mtph`** — front-matter + body blocks (§3).
7. **Draw the figure** with the DSL (§4–5). If no helper fits, **draw it with `path`** — you
   are never limited to the named shapes.
8. **Validate, render, and LOOK** (§8). Fix overlaps, check every glyph and arrow direction.
9. **Self-audit** against the checklist (§7) and iterate; do not finalise until it passes.

---

## 3. The `.mtph` format (essentials)

A file is **YAML front-matter** + a **Markdown-style body**. Full spec:
[`spec/SPEC.md`](spec/SPEC.md); validation schema: [`spec/schema.json`](spec/schema.json).

````markdown
---
mtph: "0.2"
id: my-problem-id
title: Short, evocative title
subject: physics
topic: electromagnetism/plasma        # free text; use the real sub-domain
difficulty: 5                          # 1..5 — be honest; reserve 5 for thesis-grade
tags: [debye, screening, domain-collision]
---

Problem statement here. Inline math like $\lambda_D$ renders as real glyphs.

$$\nabla^2 \phi = \frac{\phi}{\lambda_D^2}$$

```figure caption="Optional caption with $math$."
# diagram DSL — see §4
```

```answer type=expression
\lambda_D = \sqrt{\dfrac{\varepsilon_0 k_B T}{n_0 e^2}}
```

`````solution
Full worked solution. Inline math $...$ and display $$...$$ both work; you may embed
```figure```/```plot``` blocks here too. Annotate the Necessary Insight explicitly.
`````
````

**Block types:** prose (Markdown + inline `$...$`), `math` (`$$...$$` or ```` ```math ````),
`figure` (DSL → SVG), `plot` (`f(x)=…` → SVG), `answer`, `solution`.

**Answers & solutions live in the body (preferred).** Write ```` ```answer ```` and
```` ```solution ```` blocks in the body, *not* in the front-matter. This keeps all LaTeX in one
single-backslash world (no YAML escaping) and lets a solution contain figures/plots/math.
- Multi-part: one ```` ```answer part=a ```` block per part; `type=` is `expression` (default),
  `numeric`, `freeform`, or `choice`.
- A ```` ```solution ```` that contains inner ```` ``` ```` blocks must use a **longer fence**
  (4+ backticks) than the blocks inside it — e.g. open with ````` ````solution `````.
- Front-matter `answer:`/`solution:` still work (back-compat), but prefer body blocks.
- Optional **`grading:`** in front-matter — a list of `{part, points, criteria}` renders as a
  marking rubric with a total. (It's YAML, so single-quote any criteria containing LaTeX.)
- Optional **`symbols:`** — map each answer symbol to its dimension (`a: acceleration`,
  `k: force/length`, `E: M L^2 T^-2`); `mtph verify` dimension-checks the answer (`dimension.mismatch`).
  Add a symbol `test:` value (`L: {dim: length, test: 1}`, or a `{from, to}` range for stronger
  multi-point checks) + an answer **`check:`** number → it spot-checks the arithmetic (`numeric.mismatch`). (SPEC §6.3.)
- Optional **`params:`** in front-matter — declare `{ min, max, default, unit? }` and reference it
  as `{{name}}` in a figure/plot to make the problem *explorable* (a slider in the viewer). Static
  output uses the `default`, so it stays deterministic. Great for "how does the trajectory change
  with the launch angle?" (SPEC §6.4.)
- **Self-quiz.** A `numeric` answer (with a `tolerance`) or a `choice` answer (`options` +
  `correct`) is auto-checkable: `mtph render --quiz` (and the viewer's Quiz toggle) render an input
  or clickable options that grade the reader, with a reveal. Prefer these answer types when you
  want the problem to test the reader, not just show the answer.

**Backslash rule (now simple):** inside **any** block — fences, `$$…$$`, ```` ```answer ````,
```` ```solution ```` — write a **single** backslash (`\theta`, `\frac`, `\vec`), exactly as in a
`.tex` file. Because answers/solutions are body blocks, you no longer put LaTeX in YAML at all.
(`mtph verify` flags a doubled `\\command` if one slips in.)

**Math = LaTeX = unlimited symbols.** Any glyph a problem needs is available:
`\frac \int \oint \nabla \partial \hbar \langle\psi| \otimes \nabla\times \vec{B}
\hat{n} \dot{x} \ddot{x} \mathbf{T} \varepsilon_0 \mu_0 \zeta(3)` … Don't invent notation; use LaTeX.

**Numbered equations.** Add `\label{eq:key}` to a display equation to number it, and cite it from
prose with `\ref{eq:key}` (renders as a clickable `(n)`). Only labelled equations get numbers.
Keep `\ref` in prose, not inside `$…$`. `verify` flags a `\ref` with no matching `\label`.

---

## 4. Figure DSL — the "draw anything" reference

- **Coordinates:** logical units, **y points up**. The canvas auto-fits; never set pixels.
- **Anchors** (anywhere a point is expected): `(x,y)` literal · a `name` defined earlier ·
  `name.part` (e.g. `incline.mid`).
- **Strings** are double-quoted and may contain LaTeX: `label="\theta"`, `label="v_0"`.
  - **Figure labels are Unicode-mapped, not KaTeX.** Greek/symbols, `_`/`^`, and `\vec \hat \bar
    \dot \ddot \tilde` work. `\frac`, `\sqrt{x}`, `\text`, `\mathbf`, environments **don't** — they
    show as literal text. Keep labels short; put rich math in a `math` block. (`mtph verify` flags
    `figure.label_unsupported`.)
- **Palette is black-and-white:** `fill`/`stroke` ∈ `none|black|white|gray|lightgray`.
  Styles: `style=solid|dashed|dotted`, `width=N`.

### 4.1 Freeform path — your universal tool

**If no named helper fits the figure you imagine, draw it directly.** This is the "stubborn
child with a pencil" primitive — any curve, surface, blob, or custom symbol:

```
path d="M(0,0) L(2,0) C(3,1)(3,3)(2,4) Q(0,4)(0,2) Z" fill=lightgray
path d="M(0,0) C(1,1.4)(2,1.4)(3,0) C(4,-1.4)(5,-1.4)(6,0)" arrow=true   # a wave
```
`M` move · `L` line · `C(c1)(c2)(end)` cubic · `Q(c)(end)` quadratic · `Z` close.
`arrow=true` adds a head at the end. (For a circular arc, use the standalone `arc at= r= from= to=`
command rather than `path`.)

**Fills:** any shape that takes `fill=` accepts a colour (`black gray lightgray white none`) **or a
pattern**: `fill=hatch`, `fill=crosshatch`, `fill=dots` — for cross-sections, materials, shaded regions.

### 4.2 Primitives
`point` · `line`/`segment` · `vector`/`arrow` · `circle` · `rect` · `polygon` · `arc` ·
`spiral`/`coil` · `label`/`text` · `angle` · `path`.

### 4.3 Physics helpers (use these; compose freely)
- **Mechanics:** `incline` `mass`/`block` `force` `spring` `pulley` `ground` `wall` `dim`
  `pendulum` `rod` `pivot`/`hinge` `rope`/`string` `axis`.
- **3D & frames:** `axes3d` `sphere` `omega` (rotation indicator).
- **Fields, charges & E&M:** `charge` (+/−) `dipole` `bfield` (⊗ in / ⊙ out) `fieldline`
  `vectorfield` `equipotential` `gaussian`.
- **Circuits & optics:** `resistor` `battery` `wire` `current` (labelled I-arrow) `lens` `ray`.
- **Thermo, fluids & waves:** `container` `piston` `gas` `heat` `flame` `wavefront`
  `streamline`.

Exact arguments for each command are tabulated in **`spec/SPEC.md` §4**. Unknown commands, bad
anchors, or missing required args raise a clear, line-numbered error — read it and fix.

**Multi-panel** (before/after, two cases, insets): start the figure with `layout row` (or
`column`, or `grid cols=N`) and separate sub-scenes with a line of `---`; a leading `#` line
captions each panel. Each panel auto-fits independently.
```
layout row
# Before
incline angle=20 length=5
---
# After
incline angle=40 length=5
force from=m dir=down label="mg"
```

**Animate (optional, SPEC §4.3b)** — add `anim=` to any command for a *live* figure in the reader,
playground and Claude Artifacts (static PNG shows the first frame). Three verbs: `anim=spin`
(`anim-about=`, `anim-swing=DEG` for a pendulum, `anim-cw=true`), `anim=oscillate` (`anim-amp=`,
`anim-dir=`), `anim=along` (`anim-path="(x,y);…"`), each with `anim-period=`. Use it only when
motion *teaches* (a pendulum swinging, a rotor spinning); a static diagram is usually clearer.
```
pendulum at=(0,3) length=2.6 angle=22 anim=spin anim-about=(0,3) anim-swing=44 anim-period=2
```

### 4.4 Plot spec
```
x: -6.28..6.28
f(x) = sin(x)
g(x) = exp(-x/3)*cos(x)
mark: (0, 1) label="A"
vline: 0 ; hline: 0 ; grid: true ; xlabel: "t" ; ylabel: "x(t)"
```
Expressions: `+ - * / ^`, unary `-`, `( )`, and `sin cos tan asin acos atan sinh cosh tanh
exp ln log sqrt abs sign floor ceil`, constants `pi e`. (Safe parser — no `eval`.)

**Parametric mode** (trajectories, orbits, phase portraits, Lissajous) — add `mode: parametric`
and give `x(t)` and `y(t)` over a parameter range. Equal-aspect by default, so a circle looks
circular:
```
mode: parametric
t: 0..6.2832
x(t) = (1 + 0.3*cos(2.1*t)) * cos(t)
y(t) = (1 + 0.3*cos(2.1*t)) * sin(t)
samples: 500 ; grid: true
```
**Polar mode** (orbits, cardioids, rose curves) — `mode: polar`, then `r(theta)` over an angle
range. Range endpoints accept `pi` (e.g. `theta: 0..2*pi`):
```
mode: polar
theta: 0..2*pi
r(theta) = 1 + cos(theta)
samples: 240 ; grid: true
```
**Vector-field mode** (flows, E/B fields, phase portraits) — `mode: vectorfield`, then `u(x,y)` and
`v(x,y)` over `x:`/`y:` ranges → a grid of arrows. **Implicit mode** (conics, level sets) —
`mode: implicit`, then `F(x,y) = …` for the curve `F = 0`. Both render equal-aspect. Marks may carry
`color=` (`mark: (1,1) label="P" color=red`).

---

## 5. Diagram cookbook (copy, then adapt)

**Free-body on an incline**
```figure
incline angle=30 length=6
mass m at=incline.mid size=0.9 label="m"
force from=m dir=down label="mg"
force from=m dir=perp-out label="N"
angle at=incline.base from=0 to=30 value="\theta"
```

**Charge in a field into the page (cyclotron)**
```figure
bfield at=(0,0) width=5 height=4 dir=in n=5
circle at=(2.5,2.2) r=1.5 style=dashed
charge at=(2.5,0.7) sign=+ label="+q"
vector from=(2.5,0.7) to=(3.9,0.7) label="v"
vector from=(2.5,0.7) to=(2.5,1.7) label="F"
```

**Dipole field lines + Gaussian surface**
```figure
charge a at=(0,0) sign=+ label="+q"
charge b at=(3,0) sign=- label="-q"
fieldline from=a to=b bend=0.4
fieldline from=a to=b bend=-0.4
gaussian at=(0,0) r=0.8 label="S"
```

**Piston + gas + heat (thermo)**
```figure
container at=(0,0) width=2 height=3
gas at=(0,0) width=2 height=1.6 n=16
piston at=(1,1.75) width=2 rod=1.0 label="F"
heat at=(0.25,-0.95) width=1.5 n=3
```

**Anything else** → reach for `path` (a spiral, meniscus, shock front, potential well, odd
conductor): build it from `M/L/C/Q/Z`.

**Legibility:** labels carry a white halo (readable over grids/hatching), but still keep them off
arrow tails and dense regions; nudge with `dx`/`dy` or `anchor=`.

---

## 6. Notation: Soviet (Irodov / Landau) vs American

Match the convention the request asks for. Both render via LaTeX; the difference is symbols,
phrasing, and presentation.

| Aspect          | Soviet / Irodov–Landau                              | American textbook                         |
|-----------------|-----------------------------------------------------|-------------------------------------------|
| Voice           | Terse, imperative: "A rod of mass $m$… Find…"       | Fuller prose, scenario framing            |
| Data            | Symbolic; numbers given as a compact list           | Often numeric with explicit SI units      |
| Vectors         | Arrow: $\vec r$, $\vec p$                            | Bold $\mathbf{F}$ or arrow $\vec F$        |
| Frames          | $K$ and $K'$                                         | $S$ and $S'$ (or "lab"/"primed")          |
| Efficiency      | $\eta$                                               | $e$ or $\eta$                             |
| Common letters  | $\varkappa$ (susceptibility), $j$ (current density), $\rho$ (density/resistivity), $\nu$ (frequency) | $\chi$, $J$, $\rho$, $f$ |
| Decimals        | comma in the original (write `1.5` in LaTeX)         | point `1.5`                               |
| Gravity         | $g = 9.8\ \mathrm{m/s^2}$ typical                   | $9.8$ or $9.81$                           |

Default to **symbolic, Irodov-terse** phrasing unless asked otherwise — it suits thesis-grade
problems (under-specification, "find … in terms of …"). When asked for "American style," add
scenario prose and concrete numbers with units.

**Declare it.** Put `notation: irodov | american | jee` in front-matter and keep to that pack's
conventions. You still write **plain LaTeX** — the pack adds no syntax; `mtph verify` flags drift
(e.g. `\mathbf` under `irodov`), and `mtph prompt --notation <id>` prints the pack's style card.

---

## 7. Self-audit checklist — the gate (do not finalise until it passes)

From the thesis Appendix A. A finalised problem MUST satisfy **all Conceptual**, **at least
one full column of Human- or AI-defeating**, **all Structural**, and the **Elegance** tests.

**Conceptual** — [ ] one Necessary Insight unlocks it · [ ] compelling False Attractor ·
[ ] surface hides the correct framing · [ ] meaningfully under-specified.
**Human-defeating** — [ ] triggers wrong schema · [ ] violates a p-prim · [ ] pushes working
memory · [ ] spans ≥2 mental ecologies.
**AI-defeating** — [ ] requires model construction · [ ] requires principle *derivation* (not
formula recall) · [ ] has a self-consistency requirement · [ ] needs 3-D/vector reasoning ·
[ ] includes a false trail to an intractable calculation.
**Structural** — [ ] parts progressively dependent · [ ] ≥2 coupled domains · [ ] hidden
symmetry/conservation · [ ] a regime that must be identified.
**Elegance** — [ ] statement ≤ 2 paragraphs · [ ] solution ≤ 2 pages · [ ] insight feels
simple once seen · [ ] an expert would call the solution correct *and beautiful*.

Also verify mechanically: **answer present and correct**, **solution states the insight**,
**figure `mtph inspect`-ed (anchors in-extent, no label overlap)**, **`mtph verify` clean (no
errors)**.

---

## 8. Verify, inspect, render, view

**Verify first — it is built for you.** `mtph verify` is graduated and machine-parseable: it
catches the silent failures `validate` cannot (doubled backslashes, undefined figure anchors,
plot domain gaps, bare subscripts, overlapping labels). Branch on the JSON.

```bash
mtph verify  path/to/problem.mtph                # JSON when piped; fix every `error`, review `warning`s
mtph inspect path/to/problem.mtph                # a figure's resolved scene as DATA — see §8.1
mtph validate path/to/problem.mtph               # fast schema-only gate
mtph render  path/to/problem.mtph -o out.html    # self-contained HTML
mtph render  path/to/problem.mtph --grid -o out.html   # …with a coordinate grid over figures
mtph figure  path/to/problem.mtph --grid         # render only the figure(s) to SVG (fast loop)
mtph view    path/to/problem.mtph                # live reader (Reveal-answer, Source)
mtph dev     path/to/problem.mtph                # live reader + continuous verify as you edit
```

Read `verify`'s output: top-level `status` is `ok | warnings | error`; each finding has a stable
`id`, a `severity`, and a `fix` you can act on. `unknown` (e.g. `content`, `notation`) means *a
human must check this* — never assume it is fine. **Do not finalise on an `error`.**

### 8.1 Inspect — placing figures without eyes
You cannot see a rendered figure, so do not guess coordinates blindly. `mtph inspect` returns, as
JSON: the logical `extent` (the coordinate window), every resolved `anchor` (where `incline.mid`,
your masses, your points actually landed), each element's `bounds`/`length`/`angle_deg`, and any
`label_overlap` diagnostics. Loop: write the figure → `inspect` → check anchors sit inside the
extent and vectors have the angles you intended → adjust `at=`/coordinates → `inspect` again. Use
`--grid` when you do render, to confirm orientation.

**Then render and look** (or have the human look). Confirm: every symbol typeset, every arrow
points the right way, no label collisions, the figure matches the words.

---

## 9. Worked references

Study these in `spec/examples/` — each is annotated by domain/difficulty in its front-matter:
- `loop-the-loop.mtph` — Pillars 1/2/3/7 (energy + friction + circular motion), the classic
  `N = 6mg`, with a leaving-angle regime question.
- `cyclotron.mtph` — Domain collision (magnetic force × velocity selector), field diagram with
  `bfield` + `charge` + force/velocity vectors.
- `incline.mtph`, `projectile.mtph`, `triangle.mtph`, `integral.mtph`, `circuit.mtph` — the
  block-type and figure basics.

When you author a new problem, place it in `spec/examples/` (or a problem-bank folder), fill in
honest `difficulty`/`tags`, and make the `solution` name its Necessary Insight explicitly.

---

*Math is first (this file); a `subject: math` companion will later share this format, DSL, and discipline.*
