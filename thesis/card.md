# The hard-problem card

The condensed doctrine of `thesis/phythesis.md` (885 lines → this). Read this to author at the
bar; consult the full thesis for depth on any line below.

## The core principle

**Hardness is not complexity.** A long, technical problem with a predictable solution path is not
hard — it is *laborious*. A hard problem is one whose **solution path must be invented**, not
retrieved. The difficulty lives in the *conception*, not the execution.

> **Design rule (the whole thesis in one sentence):** the problem must be unreachable by transfer
> from any standard training set, human or machine — it must require reasoning from physics as a
> living logical structure, not as a library of patterns.

**Three levels of understanding** — aim above Level 1:
- **L1 Procedural** — knows the equations and standard moves. (Good students; current AI lives here.)
- **L2 Structural** — knows *when* to use which framework; connects domains. (Top students, professors.)
- **L3 Generative** — derives results from first principles; *invents* the frame/variable/invariant.
  (Almost no humans; current AI ≈ zero.) **The hardest problems require L3.**

## The Seven Pillars (a maximum-difficulty problem has several)

1. **False Attractor** — an obvious approach that is subtly *wrong* (right law, wrong regime; valid
   approximation pushed outside its domain). Must look right until after real investment.
   *E.g. energy conservation where dissipation is hidden; lab frame where a rotating frame is needed.*
2. **Necessary Insight** — exactly one non-obvious key (a reframing, symmetry, conserved quantity,
   frame, limiting case) without which it's unsolvable. Hard to *see*, simple in retrospect, *unifies*
   the problem once seen.
3. **Progressive Dependency** — each part needs the previous part's exact result. No skipping; errors
   cascade; AI confidently propagates a wrong step into polished nonsense. Make the dependency
   *implicit* — physically necessary, not stated.
4. **Domain Collision** — sits at the *coupled* intersection of 2–3 separately-taught domains
   (thermo × EM, fluids × stat-mech, mechanics × info). Co-present is not enough — the parts must be
   *inseparable*. Experts have shallow schemas at boundaries; AI has no boundary templates.
5. **Physical Modeling Before Mathematics** — deliberately under-specified. The solver must build the
   model: what's negligible, what dominates, which regime, which approximations. The single most
   reliable AI-killer (no template retrieves judgment). State a real scenario, not a cleaned-up one.
6. **Symmetry Camouflage** — a deep symmetry/invariant makes it trivial, but the surface coordinates
   *hide* it. Right substitution → five lines; "natural" coordinates → intractable integral.
   *E.g. hidden Runge-Lenz, a centre-of-momentum frame, bispherical coordinates.* State it in the
   *worst* natural coordinates.
7. **Limiting-Case Trap** — a parameter sits near a *qualitative transition* (over/underdamped,
   sub/supersonic, strong/weak coupling, classical/quantum kT vs ℏω). Wrong regime → a finite,
   plausible, *wrong* answer. Don't state the regime; make the correct answer a *different form*.

## The Eight Techniques (concrete moves)

- **A — Reference-Frame Disguise:** state it where the algebra is brutal; the right frame collapses it.
- **B — The Conservation Law That Isn't:** hide dissipation so energy/momentum conservation silently fails.
- **C — Coupled-ODE Surprise:** two "independent" DOF are coupled through a boundary/constraint.
- **D — Wrong-Intuition Setup:** the qualitative behaviour is genuinely counter-intuitive.
- **E — Cascading Approximation:** each approximation is valid only given the previous one's conclusion.
- **F — The Missing Equation:** looks under-determined; the missing relation is an unstated physical constraint.
- **G — Dimensional Trap:** the obvious dimensional combination is wrong; a dimensionless group governs it.
- **H — Stability Inversion:** what looks unstable (inverted pendulum, balanced plasma) is stable via a subtle effect.

## Where the depth is (under-exploited → most fertile)

Mined out (hard only via the pillars): classical mechanics, optics, electrostatics, basic circuits.
**Fertile:** plasma physics, soft matter, active matter, non-equilibrium thermodynamics, nonlinear
dynamics. The collision matrix — ★★★ = almost no existing problems:

```
                 Plasma  Soft    Non-eq  Nonlinear  Active
                 Physics Matter  Thermo  Dynamics   Matter
Quantum Mech.  │  ★★★    ★★      ★★★     ★★         ★★
Elasticity     │  ★★     ★★★     ★★      ★★★        ★★★
Fluid Dynamics │  ★★★    ★★★     ★★      ★★★        ★★★
Statistical M. │  ★★     ★★★     ★★★     ★★         ★★★
Electromag.    │  ★★★    ★★      ★★      ★★         ★★
```

## Difficulty rubric (`difficulty: 1..5`)

- **1–2** — L1 procedural: one domain, standard moves, all data given. (Warm-up.)
- **3** — L2 structural: non-standard but a clear path; needs good judgment, no single hidden key.
- **4** — L3-leaning: ≥1 Necessary Insight + ≥2 pillars; a wrong attractor; under-specified.
- **5** — L3: invented solution path, coupled domain collision, regime/symmetry hidden, self-consistent.
  Wrong approaches terminate in intractable calculations.

## The Anti-AI five-part template (a strong default structure)

- **(a) Physical model construction** — incomplete realistic scenario; justify approximations; no unique number.
- **(b) Principle derivation** — don't give the formula; require derivation from something more fundamental.
- **(c) Coupled self-consistent calc** — (b) feeds an implicit/iterative equation; reward seeing the self-consistency.
- **(d) 3D spatial reasoning** — non-trivial geometry; ask for a *direction*, not just magnitude.
- **(e) Regime identification** — change a parameter; ask what *qualitatively* changes (answer differs from (d)).

## The design checklist (the gate)

Architecture: □ one necessary insight unlocks it □ false attractor compelling, not obviously wrong
□ surface hides the correct framing □ genuinely under-specified.
Defeats humans: □ triggers the wrong expert schema □ violates a physical "obvious" □ pushes working
memory □ crosses ≥2 domains. Defeats AI: □ requires model *construction* □ derivation not formula
□ real self-consistency □ 3D orientation reasoning □ a false trail ending in an intractable integral.
Structure: □ progressively dependent parts □ ≥2 coupled domains □ a hidden symmetry/invariant □ a
regime to identify. **Elegance** (the great-problem test): □ stated in ≤2 paragraphs □ correct
solution ≤2 pages □ the insight feels simple & beautiful in hindsight □ an expert recognizes the
solution immediately.

> All architecture/defeat/structure boxes → a hard problem. Plus all four elegance boxes → a great one.
