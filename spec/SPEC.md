# The `.mtph` format — specification v0.2

`.mtph` ("math/physics") is a plain-text container for a single math or physics problem. It
is designed so that **a language model can write it** and **a human (or a renderer) can read
it crisply**, with two first-class kinds of content:

1. **Symbolic notation** authored in **LaTeX** and rendered to real glyphs.
2. **Figures authored as code** in a small declarative DSL, compiled to **SVG**.

This document defines the on-disk syntax, the canonical JSON DOM that a parser produces, and
the contract a conformant renderer follows. The companion file [`schema.json`](schema.json)
validates the DOM and is the normative source of truth for the data model.

---

## 1. File identity

- Encoding: **UTF-8**, LF newlines recommended.
- Extension: **`.mtph`**.
- A file is **YAML front-matter** followed by a **Markdown-style body**.
- Every file declares a format version via the `mtph` front-matter key (current: `"0.2"`). A
  renderer supports a file if it shares the same MAJOR version, so `0.1` files still validate and
  render (0.2 is a backward-compatible superset).

---

## 2. Document structure

```
---
mtph: "0.2"
<meta fields>
---
<body>
```

The region between the first two `---` lines is parsed as YAML and becomes `meta`. Everything
after the closing `---` is the **body**, split into ordered **blocks**.

### 2.1 Front-matter (`meta`)

| Key          | Type                  | Required | Notes                                            |
|--------------|-----------------------|----------|--------------------------------------------------|
| `mtph`       | string `"MAJOR.MINOR"`| yes      | Lives at the top level, not inside `meta`.        |
| `id`         | string                | no       | `[A-Za-z0-9._-]+`. Stable identifier.             |
| `title`      | string                | **yes**  | Human title.                                      |
| `subject`    | `physics` \| `math`   | **yes**  |                                                   |
| `topic`      | string                | no       | Free-form, e.g. `mechanics/dynamics`.             |
| `difficulty` | integer 1–5           | no       |                                                   |
| `tags`       | string[]              | no       |                                                   |
| `notation`   | `irodov`\|`american`\|`jee` | no | Convention pack; `verify` checks drift (see §6.2). |
| `source`     | string                | no       | Attribution.                                      |
| `answer`     | object                | no       | See §2.2.                                         |
| `solution`   | string (Markdown)     | no       | Worked solution; may contain `$...$` math.        |
| `grading`    | object[]              | no       | Marking rubric: items `{part?, points, criteria}`. Rendered as a points table in the aside. |
| `symbols`    | object                | no       | Map symbol → physical dimension (`a: acceleration`) or `{ dim, test }`. Enables `verify`'s dimensional analysis and numeric spot-check (§6.3). |
| `params`     | object                | no       | Explorable parameters, referenced as `{{name}}` in figures/plots; renderers substitute the default, viewers show a slider (§6.4). |

### 2.2 Answer types

```yaml
answer: { type: numeric,    value: 9.8, unit: "m/s^2", tolerance: 0.1 }
answer: { type: expression, value: "a = g\\sin\\theta" }     # LaTeX; optional `check:` num (§6.3.1)
answer: { type: choice,     options: ["A","B","C"], correct: 1 }   # 0-based; array for multi
answer: { type: freeform,   value: "Any proof showing ..." }       # proofs / explanations
```

---

## 3. Body blocks

The body is a sequence of blocks. Block boundaries:

- A **fenced block** ` ```math `, ` ```figure `, or ` ```plot ` runs until the closing ` ``` `.
- A **display-math** block `$$ ... $$` (on its own, possibly multi-line).
- Everything else is collected into **prose** blocks (Markdown), split on blank lines between
  fences. Prose may contain inline math `$...$`.

| Block    | DOM type   | Authoring syntax                | Rendered via            |
|----------|------------|---------------------------------|-------------------------|
| Prose    | `prose`    | plain Markdown + inline `$...$` | Markdown + KaTeX        |
| Math     | `math`     | `$$...$$` or ` ```math `         | LaTeX → KaTeX (glyphs)  |
| Figure   | `figure`   | ` ```figure ` … DSL …            | DSL → SVG (§4)          |
| Plot     | `plot`     | ` ```plot ` … plot spec …        | spec → SVG (§5)         |

A fenced figure/plot may carry a caption with an attribute line right after the opener:
` ```figure caption="Free-body diagram" `.

---

## 4. Figure DSL

A figure is a sequence of **statements**, one per line. Syntax:

```
command [positional] key=value key=value ...
# lines starting with # are comments; blank lines are ignored
```

- **Coordinates** use logical units with **y pointing up** (math convention). The compiler
  auto-fits a `viewBox` with padding; you never set pixel sizes.
- **Anchors** (used wherever a point is expected) are one of:
  - a literal `(x,y)` — e.g. `(1,2.5)`, `(-3,0)`
  - a **name** defined by an earlier statement — e.g. `m`
  - a **named part** `name.part` — e.g. `incline.mid`
- **Strings** are double-quoted and may contain LaTeX: `label="\\theta"`, `label="v_0"`.
  - **Figure labels are rendered by a Unicode mapper, not KaTeX** (so figures stay self-contained
    SVG with no browser). It handles: Greek and common symbols (`\alpha … \omega`, `\partial`,
    `\nabla`, `\infty`, `\pm`, `\leq`, …), sub/superscripts (`_`, `^`, with `{…}` groups), and the
    accents `\vec \hat \bar \dot \ddot \tilde \overline`.
  - It does **not** typeset argument-taking or unknown commands — `\frac{a}{b}`, `\sqrt{x}`,
    `\text{…}`, `\mathbf/\mathrm/\mathcal{…}`, environments — which render as *literal text*. Keep
    labels short (`v_0`, `\omega`, `E_k`); for anything richer, put a `math` block near the figure.
    `mtph verify` flags an unsupported label command (`figure.label_unsupported`).
- **Palette is black-and-white**: `fill` and `stroke` accept `none|black|white|gray|lightgray`.
- Common style keys: `style=solid|dashed|dotted`, `width=<number>`, `stroke=<color>`,
  `fill=<color>`.
- **Fill patterns** (v0.2): `fill=hatch | crosshatch | dots` render a pattern instead of a flat
  colour (cross-sections, materials, shaded regions). Emitted as reusable SVG `<pattern>` defs.

### 4.1 Primitives

| Command   | Key args                                                       | Meaning                              |
|-----------|----------------------------------------------------------------|--------------------------------------|
| `point`   | `at=ANCHOR` `label=` `dot=true\|false`                          | A named point. Defines its name.     |
| `line`    | `from=ANCHOR` `to=ANCHOR` (`segment` is an alias)               | A straight segment.                  |
| `vector`  | `from=ANCHOR` `to=ANCHOR` `label=` (`arrow` is an alias)        | Arrow with a head at `to`.           |
| `circle`  | `at=ANCHOR` `r=` `fill=`                                        | Circle (center `at`).                |
| `rect`    | `at=ANCHOR` `w=` `h=` `angle=` `fill=`                          | Rectangle centered at `at`.          |
| `polygon` | `points=(x,y);(x,y);...` `fill=` `closed=true`                 | Polyline / polygon.                  |
| `arc`     | `at=ANCHOR` `r=` `from=DEG` `to=DEG`                            | Circular arc.                        |
| `spiral`  | `at=ANCHOR` `r0=` `dr=` `turns=` `a0=DEG` `label=` (alias `coil`/`helix`) | Archimedean spiral; `dr` = radius gain per turn. |
| `label`   | `text=` `at=ANCHOR` `anchor=center\|left\|right\|above\|below` `dx=` `dy=` | Text (`text` is an alias). |
| `angle`   | `at=ANCHOR` (`from=DEG to=DEG` \| `between=A,B,C`) `value=` `r=`| Angle arc with a label.              |

`point name at=(x,y)` defines `name`; the bare first token after `point`/`mass`/`block` is the
name, e.g. `point P at=(1,2)` or `mass m at=incline.mid`.

### 4.2 Physics & geometry helpers (expand to primitives)

| Command    | Key args                                                              | Defines / draws                                       |
|------------|-----------------------------------------------------------------------|-------------------------------------------------------|
| `incline`  | `angle=DEG` `length=N` `at=(x,y)`                                      | Ramp. Anchors: `.base .foot .top .mid`. Ground hatch. |
| `mass`     | `<name>` `at=ANCHOR` `size=N` `label=` `angle=DEG`                     | Square block; name = its center. Aligns to incline.   |
| `block`    | alias of `mass`                                                       |                                                       |
| `force`    | `from=ANCHOR` `dir=down\|up\|left\|right\|perp-out\|perp-in\|along\|DEG` `label=` `mag=N` | A labelled force arrow.        |
| `spring`   | `from=ANCHOR` `to=ANCHOR` `coils=N` `label=`                          | Zig-zag spring.                                       |
| `zigzag`   | `from=ANCHOR` `to=ANCHOR` `periods=N` `amplitude=` `label=`            | Zigzag line (cutaway / boundary indicator).          |
| `pulley`   | `at=ANCHOR` `r=N`                                                      | Pulley wheel + axle.                                  |
| `ground`   | `at=(x,y)` `width=N`                                                   | Hatched ground line.                                  |
| `wall`     | `at=(x,y)` `height=N` `side=left\|right`                               | Vertical hatched wall.                                |
| `dim`      | `from=ANCHOR` `to=ANCHOR` `off=N` `label=`                            | Dimension line (offset, double arrow + label).        |
| `axis`     | `x=a..b` `y=c..d` `origin=(x,y)` `labels=true`                        | Coordinate axes with ticks.                          |
| `resistor` | `from=ANCHOR` `to=ANCHOR` `label=`                                     | Circuit resistor (zig-zag).                          |
| `battery`  | `from=ANCHOR` `to=ANCHOR` `label=`                                     | Circuit cell.                                        |
| `wire`     | `from=ANCHOR` `to=ANCHOR`                                              | Plain connector.                                     |
| `lens`     | `at=ANCHOR` `type=convex\|concave` `height=N`                          | Optical lens on the optical axis.                    |
| `ray`      | `from=ANCHOR` `to=ANCHOR` `arrow=true`                                 | Light ray.                                           |

A renderer MUST raise a clear, located error for an unknown command, a bad anchor, or a
missing required argument.

### 4.2a Freeform path — draw *anything* (v0.2)

The `path` command draws an arbitrary shape from an SVG-like list of segments in logical
coordinates. This is the "draw anything" primitive — any curve, blob, freehand form, or
custom symbol.

```
path d="M(0,0) L(2,0) C(3,1)(3,3)(2,4) Q(0,4)(0,2) Z" fill=lightgray arrow=false
```

Segment commands inside `d="..."`: `M(x,y)` move, `L(x,y)` line, `C(c1)(c2)(end)` cubic
Bézier, `Q(c)(end)` quadratic Bézier, `Z` close. `fill=`, `stroke=`, `style=`, `width=` apply;
`arrow=true` puts an arrowhead at the final endpoint.

### 4.2b Fields, charges & E&M (v0.2)

| Command        | Key args                                                       | Draws                                  |
|----------------|----------------------------------------------------------------|----------------------------------------|
| `charge`       | `<name>` `at=ANCHOR` `sign=+\|-` `r=N` `label=`                  | Charge: circle with +/−.               |
| `dipole`       | `at=(x,y)` `sep=N` `angle=DEG` `moment=true` `label=`           | + and − pair (optional moment arrow).  |
| `bfield`       | `at=(x,y)` `width=N` `height=N` `dir=in\|out` `n=N` `label=`     | Grid of ⊗ (in) / ⊙ (out).              |
| `fieldline`    | `from=ANCHOR` `to=ANCHOR` `bend=N` `arrow=true` (alias `streamline`) | Curved field/flow line.           |
| `vectorfield`  | `at=(x,y)` `width=N` `height=N` `dir=DEG\|in\|out` `n=N`         | Grid of arrows (uniform/radial).       |
| `equipotential`| `at=ANCHOR` `r=N`                                                | Dashed equipotential circle.           |
| `gaussian`     | `at=ANCHOR` `r=N` `label=`                                       | Dashed Gaussian surface.               |
| `current`      | `from=ANCHOR` `to=ANCHOR` `label=` (defaults to `I`)            | Labelled current arrow (distinct from `vector`). |

### 4.2c Mechanics, 3D & frames (v0.2)

| Command   | Key args                                                       | Draws                                       |
|-----------|----------------------------------------------------------------|---------------------------------------------|
| `pendulum`| `<name>` `at=ANCHOR` `length=N` `angle=DEG` `bob=N` `label=` `value=` | Pivot+rod+bob, vertical ref, angle arc. name=bob anchor. |
| `rod`     | `from=ANCHOR` `to=ANCHOR` `width=N` `label=`                    | A rigid bar (thick line).                   |
| `pivot`   | `at=ANCHOR` `size=N` `label=` (alias `hinge`)                   | Pivot support (triangle + hatch).           |
| `rope`    | `from=ANCHOR` `to=ANCHOR` (alias `string`)                     | Rope/string (line).                         |
| `axes3d`  | `at=(x,y)` `size=N` `labels=true`                              | Oblique 3-D axes x/y/z.                     |
| `sphere`  | `at=ANCHOR` `r=N` `label=`                                      | Sphere (circle + equator ellipse).          |
| `omega`   | `at=(x,y)` `r=N` `dir=cw\|ccw` `label=`                          | Rotation indicator (curved arrow + ω).      |

### 4.2d Thermo, fluids & waves (v0.2)

| Command     | Key args                                                     | Draws                                       |
|-------------|--------------------------------------------------------------|---------------------------------------------|
| `container` | `at=(x,y)` `width=N` `height=N` `fill=` `level=N` `label=`    | Open vessel; optional liquid fill to level. |
| `piston`    | `at=(x,y)` `width=N` `thickness=N` `rod=N` `label=`           | Piston plate + rod.                         |
| `gas`       | `at=(x,y)` `width=N` `height=N` `n=N` `seed=N`                | Scattered gas molecules (dots).             |
| `heat`      | `at=(x,y)` `width=N` `n=N` `height=N`                         | Wavy heat arrows (upward).                  |
| `flame`     | `at=ANCHOR` `size=N`                                          | Flame outline.                              |
| `wavefront` | `at=ANCHOR` `n=N` `r0=N` `dr=N` `from=DEG` `to=DEG`           | Concentric wavefronts (rings or arcs).      |

### 4.3 Example

```figure
incline angle=30 length=6
mass m at=incline.mid size=0.9 label="m"
force from=m dir=down     label="mg"
force from=m dir=perp-out label="N"
angle at=incline.base from=0 to=30 value="\\theta"
```

### 4.3a Multi-panel figures (v0.2)

A single `figure` can hold several independent sub-scenes — *before/after*, *two cases*, insets.
A leading `layout` directive and/or `---` separators between sub-scenes turn the block multi-panel;
each panel **auto-fits on its own** and is placed as a nested viewport. A leading `#` line in a
panel captions it.

```figure
layout row                 # row (default) | column | grid cols=N  (also: horizontal/vertical)
# Before
incline angle=20 length=5
mass m at=incline.mid label="m"
---
# After
incline angle=40 length=5
mass m at=incline.mid label="m"
force from=m dir=down label="mg"
```

The `layout` line, if present, must be the **first** non-blank line. With no `layout` line, bare
`---` separators default to `row`. A figure with neither is an ordinary single-panel figure.

### 4.3b Micro-animation (v0.2)

Any figure command may carry an `anim=` attribute; the primitives that command draws are wrapped
in a `<g>` that animates via SMIL. Three verbs only (physics moves, but this is deliberately not a
general animation system):

| `anim=`      | Extra attributes                                              | Effect                                                        |
|--------------|---------------------------------------------------------------|---------------------------------------------------------------|
| `spin`       | `anim-period=` (s), `anim-about=(x,y)`, `anim-cw=true`, `anim-swing=DEG` | Rotate about a centre (default: the group's centre). With `anim-swing`, oscillate ±DEG/2 instead of a full turn — a pendulum. |
| `oscillate`  | `anim-amp=` (units), `anim-dir=` (deg), `anim-period=`         | Simple-harmonic translation along a direction (default +x).   |
| `along`      | `anim-path="(x0,y0);(x1,y1);…"`, `anim-period=`               | Follow a displacement polyline (offset from where it's drawn).|

```figure
pendulum at=(0,3) length=2.6 angle=22 anim=spin anim-about=(0,3) anim-swing=44 anim-period=2
```

The default (`anim-cw` absent) spin is counter-clockwise (physics-positive). Animation is
**decoration**: a static SVG/PNG renderer (e.g. cairosvg for `--format png`) ignores SMIL and shows
the first, at-rest frame, and `verify`/`inspect` analyse the drawn geometry unchanged. The viewBox
auto-expands to the swept region so motion never clips. To animate a **multi-part rigid body** (say
a wheel and its spoke), either use one helper command that draws it as a unit (like `pendulum`), or
put the same `anim=spin anim-about=(centre)` on each part so they turn in lock-step.

---

## 5. Plot spec

A plot is a line-oriented spec for one or more functions of `x`:

```
x: -3..3                 # domain (required)
y: -1..9                 # optional explicit range (else auto)
f(x) = x^2               # one or more functions; each is a curve
g(x) = sin(x) + 1
mark: (1, 1) label="P"   # optional marked point(s)
vline: 0                 # optional vertical reference line / asymptote
hline: 0                 # optional horizontal reference line
samples: 200             # optional sampling resolution (default 200)
grid: true               # optional background grid
xlabel: "x"
ylabel: "y"
```

Expression grammar for the right-hand side of `name(x) = ...`:
- numbers, the variable `x`, and `+ - * / ^` (with `^` = power), unary minus, parentheses;
- functions `sin cos tan asin acos atan sinh cosh tanh exp log ln sqrt abs sign floor ceil`;
- constants `pi`, `e`.

Evaluation is performed by a small safe parser (no Python `eval`). Points where a function is
undefined (e.g. division by zero) create a gap in the curve. A `mark:` may carry `color=...`
(`mark: (1,1) label="P" color=red`).

### 5.1 Modes (v0.2)

A leading `mode:` line selects a non-function plot; ranges accept constant expressions (`0..2*pi`).
All are rendered equal-aspect so shapes aren't distorted, and use the same safe evaluator.

| `mode:` | declare | over | draws |
|---------|---------|------|-------|
| `parametric` | `x(t)=…` and `y(t)=…` | `t: a..b` | a traced curve |
| `polar` | `r(theta)=…` | `theta: a..b` | a polar curve |
| `vectorfield` | `u(x,y)=…` and `v(x,y)=…` | `x:`, `y:` | a grid of arrows |
| `implicit` | `F(x,y)=…` | `x:`, `y:` | the curve `F=0` (marching squares) |

```
mode: vectorfield
x: -2..2
y: -2..2
u(x,y) = -y
v(x,y) = x
```

---

## 6. Math / LaTeX

Math is authored in a KaTeX-compatible LaTeX subset. Inline math uses `$...$` inside prose;
display math uses `$$...$$` or a ` ```math ` fence. The renderer produces real glyphs (true
fraction bars, integrals, Greek, vectors, bra-ket, etc.) — never ASCII fallbacks. Use standard
commands: `\frac`, `\int`, `\sum`, `\sqrt`, `\vec`, `\hat`, `\theta`, `\partial`, `\langle … \rangle`, …

### 6.1 Equation numbering & cross-references (v0.2)

Tag a display equation with `\label{key}` to give it a number; reference it from prose with
`\ref{key}`, which renders as a clickable `(n)`. **Only labelled equations are numbered**, so
every visible number is one the author chose to reference. (`\label`/`\ref` are resolved by mtph;
KaTeX never sees them.)

```math
\vec F_{net} = m\vec a \label{eq:n2}
```
> Integrating and using `\ref{eq:n2}` gives the work–energy theorem.

`verify` flags a `\ref` with no matching `\label` (`ref.undefined`) and a label defined more than
once (`ref.duplicate_label`). Put `\ref` in prose text, not inside `$…$`.

### 6.2 Notation packs (v0.2)

Declare a convention with `notation: irodov | american | jee` in front-matter. **This adds no new
syntax** — you still write plain LaTeX. The pack is used two ways:

- **`verify` checks drift** — e.g. `notation.mixed_vectors`: using `\mathbf` under a `\vec`
  tradition (`irodov`/`jee`), or mixing both under `american`. All warnings with a fix. No
  `notation:` declared → the `notation` group reports `unknown`, never a false `ok`.
- **`mtph prompt --notation <id>`** prints a compact style card (vector command, frame labels,
  canonical symbols, gravity) so an AI writes consistent LaTeX the first time.

| id | tradition | vectors | frames | gravity |
|----|-----------|---------|--------|---------|
| `irodov`   | Soviet / Irodov–Landau | `\vec` | `K`, `K'` | 9.8 |
| `american` | US textbook | `\mathbf` (or `\vec`) | `S`, `S'` | 9.8 / 9.81 |
| `jee`      | JEE Advanced | `\vec` | `S`, `S'` | 10 |

### 6.3 Symbols & dimensional analysis (v0.2)

Declare the physical dimension of each symbol used in the answer with an optional `symbols:`
table, and `verify` will dimension-check the answer expressions — the classic AI-author failure
mode (a dropped factor, a stray `g`), caught mechanically.

```yaml
symbols:
  a: acceleration           # a named quantity …
  g: acceleration
  theta: angle              # (angle / dimensionless)
  k: force/length           # … or a formula over named quantities …
  E: M L^2 T^-2             # … or base symbols M L T K I (mass, length, time, temperature, current)
answer: { type: expression, value: 'a = g\sin\theta' }
```

The `dimension` check reports:

- **`dimension.inconsistent`** (error) — a `+`/`-` combines unlike dimensions, or the argument of
  a transcendental function (`\sin`, `\exp`, `\ln`, …) isn't dimensionless.
- **`dimension.mismatch`** (error) — the expression's dimension differs from its declared target:
  the left-hand symbol of `a = …`, or a numeric answer's `unit`.
- **`dimension.bad_symbol`** (warning) — a `symbols:` value that names no known quantity.

Named quantities include `mass, length, time, velocity, acceleration, force, energy, power,
momentum, pressure, charge, voltage, frequency, …`. The analyzer is **conservative**: any symbol
it can't resolve or construct it can't parse makes the answer *un-analysed* (the group reports
`unknown`) rather than a false error — so a reported error is always real. No `symbols:` → the
`dimension` group is `unknown`.

#### 6.3.1 Numeric spot-check (v0.2)

A dimension check is blind to a numeric slip: `\tfrac12 mv^2` and `2mv^2` share a dimension. To
also catch a **dropped factor or a flipped sign**, give symbols a numeric **`test`** value and the
answer an expected **`check`** value — a symbol's value may be an object `{ dim, test }` instead of
a bare dimension string:

```yaml
symbols:
  T: time                          # a bare dimension string, as before
  L: { dim: length, test: 1 }      # … or an object carrying dim and/or a test value
  g: { dim: acceleration, test: 9.8 }
answer:
  type: expression
  value: 'T = 2\pi\sqrt{L/g}'
  check: 2.007                     # expected value of the RHS at L=1, g=9.8
```

`verify`'s `numeric` group evaluates the answer's right-hand side (after `=`) at the `test` values
and compares to `check` (relative tolerance 1%, so a `check` rounded to ~2 significant figures is
fine — this is a gross-error spot-check, not a precision test):

- **`numeric.mismatch`** (error) — the expression evaluates to a value that disagrees with `check`.
- **`numeric.unverifiable`** (warning) — a `check` is declared but the expression couldn't be
  evaluated at the test values (a symbol has no `test`, or the expression uses something the
  evaluator won't guess at).

The evaluator knows `+ - * / ^`, `\frac`, `\sqrt[n]`, the constants `\pi \e \tau`, and the
unambiguous functions `\sin \cos \tan \cot \sec \csc`, their hyperbolic and inverse forms, `\exp`,
and `\ln`. Like the dimension analyzer it is **conservative** — it bails (leaving the answer
un-checked, never a false mismatch) on `\log` (ambiguous base), an undeclared symbol, or ambiguous
shorthand such as `\frac12` (write `\frac{1}{2}`). No answer declares `check:` → the `numeric`
group is `unknown`.

A `test` value may also be a **sampling range** `{ from, to }` instead of a pinned number
(v0.3). A range doesn't answer "what number?" for a `check:` — it drives *multi-point
equivalence* checks (the `solution` group, §6.3.2), which compare two expressions at several
sampled points and so tell genuinely different functions apart even when they agree at one point
(`\sin\theta` vs `\tan\theta` near `\theta=0`). Sampling is deterministic (a fixed seed), so
`verify` output never varies run to run.

```yaml
symbols:
  g: { dim: acceleration, test: 9.8 }         # pinned — a single value
  theta: { dim: angle, test: { from: 0.2, to: 1.2 } }   # a range — sampled uniformly
```

A `check:` needs one specific substitution, so every symbol its answer references must be
**pinned**. If one is range-only, `verify` reports **`numeric.unpinned_symbol`** (warning): pin a
`test:` value for it, or drop `check:` (ranges are for equivalence checks, not `check:`).

### 6.4 Explorable parameters (v0.2)

Declare `params:` in front-matter and reference them as `{{name}}` inside figure/plot sources. A
`.mtph` becomes an *explorable*: drag a slider and watch the diagram change.

```yaml
params:
  theta: { min: 15, max: 75, default: 40, unit: "deg" }
  v0:    { min: 8,  max: 25, default: 20, step: 0.5, unit: "m/s" }
```
```figure
force from=(0,0) dir={{theta}} mag=2.4 label="v_0"
```
```plot
f(x) = x*tan({{theta}}*pi/180) - 9.8*x^2/(2*{{v0}}^2*cos({{theta}}*pi/180)^2)
```

Each param needs `min`, `max`, `default` (optional `step`, `unit`, `label`). **The default is
authoritative for static output**: `mtph render`/PNG and the reference DOM substitute the *default*,
so file output stays deterministic and the format stays honest — the DOM stores the template plus
the declared defaults, never a baked-in number. An interactive viewer (the playground, a future
web component) renders a slider per param and re-renders on drag. `verify` flags a `{{name}}` with
no declaration (`param.undefined`) and a bad range or out-of-range default (`param.bad_range`).

### 6.5 Self-quiz rendering (v0.2)

A renderer may present the answer as an interactive self-test instead of a static reveal
(`mtph render --quiz`, or a viewer toggle):

- a **`numeric`** answer → an input box, graded against `value` within a relative `tolerance`
  (default 1%);
- a **`choice`** answer (`options` + `correct`) → clickable options, graded by index;
- any answer type → a **reveal** of the full answer & solution.

Grading is a self-contained inline script — no dependencies — so the quiz works in an exported
file or a Claude Artifact, not only a live viewer. This is a **rendering mode**, not a format
change: the `.mtph` and its DOM are unchanged, so the same file renders statically or as a quiz.

---

## 7. Canonical JSON DOM

A parser converts the file to this structure (validated by `schema.json`):

```json
{
  "mtph": "0.2",
  "meta": {
    "id": "incline-01",
    "title": "Block on a frictionless incline",
    "subject": "physics",
    "topic": "mechanics/dynamics",
    "difficulty": 2,
    "tags": ["newton", "incline"],
    "answer": { "type": "expression", "value": "a = g\\sin\\theta" }
  },
  "blocks": [
    { "type": "prose",  "text": "A block of mass $m$ ..." },
    { "type": "math",   "latex": "\\sum F_\\parallel = m a" },
    { "type": "figure", "source": "incline angle=30 length=6\nmass m at=incline.mid ..." },
    { "type": "plot",   "source": "x: -3..3\nf(x) = x^2" }
  ]
}
```

Figure/plot **bodies are kept as raw `source` strings** in the DOM; their internal grammar is
validated by the figure/plot compiler at render time, not by `schema.json`. This keeps the
document schema small and lets the DSL evolve without schema churn.

---

## 8. Rendering contract

A conformant renderer:

1. Parses the file into the DOM and validates it against `schema.json`.
2. Renders blocks **in order**.
3. Math → real glyphs (KaTeX). Figures/plots → SVG with an auto-fitted `viewBox`, monochrome.
4. Produces **self-contained** output (no network needed at view time) for the HTML target.
5. Reports parse/validation/DSL errors with a 1-based line reference where possible.

Output targets in the reference implementation: `html` (default, self-contained),
`svg`, and `png` (the latter two via an optional headless-browser export).

---

## 9. Versioning

- `mtph` is `MAJOR.MINOR`. Additive, backward-compatible changes bump MINOR. Breaking changes
  bump MAJOR.
- Renderers should accept any file whose MAJOR they support and ignore unknown **MINOR-level**
  additions where reasonable (but `schema.json` for a given version is exact).
