# A Thesis on Designing the Hardest Physics Problems on the Planet
### A Complete Philosophy for Defeating Both Human and Machine

---

> "A problem that is merely difficult has many solutions. A problem that is truly hard has exactly one — and finding it requires you to become a different kind of thinker."

---

## Table of Contents

1. [Part I — The Fundamental Mistake Everyone Makes About "Hard"](#part-i)
2. [Part II — How the Human Brain Actually Solves Physics Problems](#part-ii)
3. [Part III — How AI Solves Physics Problems (And Where It Breaks)](#part-iii)
4. [Part IV — The Seven Pillars of a Maximum-Difficulty Problem](#part-iv)
5. [Part V — The Specific Techniques, Ready to Use](#part-v)
6. [Part VI — The Meta-Philosophy: What You Are Really Testing](#part-vi)
7. [Part VII — The Unexploited Frontiers: Which Physics Domains Have the Most Depth](#part-vii)
8. [Part VIII — Worked Examples Built From Scratch](#part-viii)
9. [Part IX — The Anti-AI Problem: Construction Guide](#part-ix)
10. [Part X — The Final Hierarchy: Grading Problem Hardness](#part-x)

---

## Part I — The Fundamental Mistake Everyone Makes About "Hard" {#part-i}

Most people think hard means *long*, *complex*, or *computationally brutal*. This is wrong. These are properties of **tedious** problems, not hard ones.

The confusion runs deep because the two things often correlate in exam settings. A six-hour IPhO problem *is* long. But its length is not the source of its difficulty. Strip away the computation and there is always a single conceptual kernel — a reframing, a conserved quantity, a symmetry — that is the actual problem. The rest is implementation.

### The Four Quadrant Map of Problem Types

```
                    HIGH CONCEPTUAL DEPTH
                            |
          TRULY HARD        |        TEDIOUS
          (Target)          |        (Mistaken for hard)
          - Simple setup    |        - Many steps
          - Non-obvious key |        - Brute-force math
          - Insight-gated   |        - Defeated by patience
                            |
SIMPLE ——————————————————————————————————————— COMPLEX
                            |
          TRIVIAL           |        DECEPTIVE
          - Simple setup    |        - Long calculation
          - Obvious path    |        - Shallow idea
          - Textbook drill  |        - Looks impressive
                            |
                    LOW CONCEPTUAL DEPTH
```

**The target is always top-left.** High conceptual depth, deceptively simple setup. The hardest physics problem ever written should fit in two sentences. Its solution should fit on one page. But the gap between reading the problem and writing the first correct line should cost most people hours — or forever.

### The Core Principle

A problem becomes truly hard not when it demands more work, but when it demands a *different kind of thinking* that the solver's trained system cannot automatically produce.

The deepest formulation:

> **A hard problem is one where the correct framing is itself the solution.**

Once you see it the right way, the math is almost trivial. The difficulty lives entirely in the re-framing. This is why Fermi problems and Putnam problems and Landau's physics minimum problems are so devastating — they are short, they are clean, and they require you to *invent* the approach rather than *select* it from a library.

### Hardness is Not Complexity — A Precise Distinction

| Property       | Complex Problem                  | Hard Problem                         |
|----------------|----------------------------------|--------------------------------------|
| Setup          | Many given quantities            | Minimal, possibly under-specified    |
| Solution path  | Long but findable                | Short once you see the key           |
| What blocks you| Amount of work                   | Inability to find the right frame    |
| Defeated by    | Patience and stamina             | Insight alone                        |
| What it tests  | Procedural fluency               | Conceptual understanding             |
| Example        | 6-body numerical integration     | "Why does a gyroscope precess?"      |

The distinction matters enormously for problem design. If you want to create maximum difficulty, you are not trying to increase complexity. You are trying to *hide the key* in a way that makes every trained instinct point the wrong direction.

---

## Part II — How the Human Brain Actually Solves Physics Problems {#part-ii}

To defeat a solver, you must understand the solver's architecture. The cognitive science of physics problem solving is well-researched and reveals a surprisingly precise picture.

### 2.1 The Schema System

Long-term memory (LTM) stores physics knowledge not as raw equations but as **schemas** — richly connected chunks that bundle together:

- A recognizable problem *situation* (inclined plane, two-body collision, LC circuit)
- The relevant physical *law* (Newton's second law, momentum conservation, Kirchhoff's laws)
- The applicable *equations* in their most useful form
- Typical *solution moves* (choose coordinates along the slope, go to centre-of-mass frame, use superposition)
- Known *pitfalls* and edge cases

When an expert sees a problem, they do not re-derive physics. A schema *fires*. The entire solution architecture arrives pre-packaged. This is phenomenally efficient for standard problems and phenomenally dangerous for non-standard ones.

The researcher Jill Larkin showed in 1980 that experts and novices solve physics problems through completely different cognitive processes. Novices search forward from given quantities using equations as transformations. Experts work backward from desired quantities using schemas as shortcuts. The expert is faster and more accurate on schema-matchable problems — and *more* vulnerable on schema-trapping ones.

### 2.2 The Working Memory Bottleneck

Working memory — the conscious reasoning workspace — holds only **5 to 9 independent "slots"** at any given time, regardless of the solver's IQ or expertise. This is a hard architectural constraint of the human brain, established by Miller's famous 1956 paper and refined by Cowan's 2001 analysis (who put the real limit closer to 4 chunks).

This limit is the master constraint of all human problem solving. Everything else is downstream of it.

An expert conserves slots by *chunking*: an entire sub-problem that a novice must track as five separate variables gets compressed into a single schema-unit and occupies one slot. A novice burns four slots on what an expert handles in one. This is why expertise matters — not because experts know more laws, but because they have automated more structure into single retrievable units.

The design implication:

> **To overload an expert, you must force them to simultaneously track more independent constraints than their chunking system can handle — and the constraints must be genuinely independent, not reducible by any standard trick.**

```
Working Memory Slots (Expert vs Novice on same problem)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Expert:  [Schema A] [Schema B] [Constraint] [Result]  . . . . .   (4/9 used)
Novice:  [F=ma] [θ] [cosθ] [sinθ] [N] [friction] [g component] . (7/9 used, near collapse)

A hard problem forces EVEN THE EXPERT to approach 9/9.
```

### 2.3 The Dual-Process Architecture (System 1 / System 2)

Kahneman's dual-process theory maps cleanly onto physics problem solving:

**System 1 (Fast, Automatic, Intuitive)**
- Fires immediately on pattern recognition
- Uses schemas from LTM
- Costs almost no working memory
- Generates the expert's first instinct
- Can be *wrong* — and when wrong, actively suppresses System 2

**System 2 (Slow, Deliberate, Analytical)**
- Engages when System 1 fails or is deliberately overridden
- Expensive in working memory
- Capable of first-principles reasoning
- Can be exhausted by cognitive load (ego depletion effect)
- Is the only system that can *catch* System 1 errors

The expert's System 1 is powerful but specific. It is tuned to the distribution of problems the expert has seen. A problem that *looks like* something familiar but *isn't* will trigger System 1 confidently and incorrectly — and because System 1 is suppressing System 2, the expert may not even realize they are wrong.

This is called the **Einstellung effect** — one of the most robust and devastating phenomena in cognitive psychology. The word is German for "set" or "attitude." The effect: your experience with similar problems creates a mental set that *prevents you from seeing the better solution*. Experts are *more* vulnerable to Einstellung than novices on carefully designed problems, because their System 1 is stronger and more suppressive.

### 2.4 The Mental Ecology

Redish introduced the concept of **mental ecology** — the meta-schema that tells you which schema to apply. This is knowledge about knowledge. Novices have poor mental ecologies: they pick equations by surface features (problem mentions velocity → use kinematics). Experts have rich mental ecologies: they categorize by underlying structure (this is a constraint problem → use Lagrangian).

But even the expert's mental ecology has boundaries. At the edges of their training — domain crossings, unusual geometries, non-standard boundary conditions — the mental ecology produces no reliable output. The solver must reason from scratch, which is enormously expensive in working memory and requires conscious System 2 engagement.

> **The hardest problems are located precisely at the edges of expert mental ecologies** — recognizable enough to trigger schemas, unfamiliar enough that those schemas fail.

### 2.5 The P-Prim Layer (Phenomenological Primitives)

Beneath schemas lies an even more fundamental layer: **p-prims**, short for phenomenological primitives. These are sub-conceptual intuitions built from embodied experience with the physical world:

- *More push → more motion* (leads to Aristotelian thinking, resists Newton's first law)
- *Objects "want" to return to rest* (violates inertia)
- *Heavier things fall faster* (wrong, but deeply encoded)
- *Forces are "used up"* (leads to systematic errors in multi-body problems)
- *Equilibrium means nothing is happening* (misses dynamic equilibrium)

P-prims are pre-conceptual and extraordinarily persistent. They survive years of physics education. They resurface under time pressure. They are what cause expert physicists to make "stupid" errors on deceptively simple problems.

A master problem designer knows the p-prim landscape and constructs scenarios where the correct answer *requires* violating a deeply encoded p-prim. The solver must consciously override intuitions that feel physically obvious.

---

## Part III — How AI Solves Physics Problems (And Where It Breaks) {#part-iii}

AI language models and humans fail at almost completely *different things*. This means a problem that defeats both requires attacking both failure modes simultaneously. Understanding the AI failure taxonomy is essential.

### 3.1 What AI Actually Does When It Solves Physics

A large language model like GPT-4, Claude, or Gemini does not "know physics" in any sense analogous to human understanding. It has learned, through training on vast text corpora, statistical associations between *problem descriptions* and *solution structures*. When it sees a physics problem, it is pattern-matching the problem text against its training distribution and generating the most probable continuation.

This works remarkably well for standard problems — because the training set contains millions of similar problems and their solutions. It fails in systematic, predictable ways when a problem departs from the training distribution.

### 3.2 The AI Failure Taxonomy

**Failure Mode 1: Template Hallucination**
AI matches the *surface features* of a problem to a known template and applies that template even when the physics is fundamentally different. A problem about a rotating frame gets treated as a standard inertial frame problem because the rotating frame machinery isn't triggered by the surface language. This is the AI analogue of Einstellung.

The key difference from human Einstellung: the AI has no metacognitive awareness that it has matched the wrong template. A human expert will eventually feel the cognitive dissonance between their approach and the problem's behavior. AI will confidently produce a well-formatted wrong answer with no indication of uncertainty.

**Failure Mode 2: No Self-Verification Loop**
Humans can sanity-check intermediate results: *Does this velocity seem physically reasonable? Is this energy positive? Does this force point the right direction?* AI generates a reasoning chain and follows it verbatim. It has no external ground-truth check on intermediate steps. A single wrong assumption early in the solution cascades into confident nonsense at the end. The verbal fluency of the wrong answer makes it *more* convincing, not less.

Research showed that OpenAI's o3-mini fails specifically because it "follows the verbal reasoning it generates, without any way to evaluate its intermediate steps by other means (such as physics simulation)."

**Failure Mode 3: Under-Specification Collapse**
When a problem lacks complete numerical specification — when the solver must decide what quantities to estimate, what regime applies, what simplifications are valid — AI collapses. Studies showed ChatGPT solved only 2 of 24 under-specified physics problems. AI needs the scaffolding of given quantities to anchor its solution. It cannot independently construct the physical model.

This is deeply significant. It means that the act of *physical modeling* — translating a real-world scenario into a solvable mathematical structure — is almost entirely absent from AI capability. AI can solve the mathematical structure once it exists. It cannot create it.

**Failure Mode 4: Compositional Reasoning Breakdown**
AI can apply principle A and principle B separately but breaks down when A and B must be *simultaneously* applied in a non-separable, coupled way. This is not about knowing two things. It is about holding the tension between two frameworks active at the same time while working out their mutual constraints. AI's sequential token generation makes this particularly difficult — it tends to "finish" one framework before starting the other, missing the coupling.

**Failure Mode 5: 3D Spatial and Vector Blindness**
Direction errors cluster heavily in AI physics failures: wrong signs on torques, incorrect orientation of normal forces in 3D, right-hand rule failures, incorrect identification of which way a magnetic force acts. These require spatial simulation that language models fundamentally cannot perform. The AI can recite the right-hand rule but cannot *apply* it to a novel geometry.

**Failure Mode 6: The Over-Thinking Trap**
Counterintuitively, more reasoning is not always better for AI. The PhySense benchmark found that LLMs with longer reasoning chains ("thinking models") do not necessarily perform better and sometimes worse. They generate elaborate incorrect reasoning paths and get trapped in self-consistent but physically wrong logic trees. More tokens of wrong reasoning do not converge to right reasoning.

**Failure Mode 7: Principle-First Blindness**
The hardest test: start from a fundamental symmetry or conservation principle and derive the result from scratch, without using any memorized formula. PhySense (2025) showed that LLMs consistently fail to reason this way. They reach for formulas. A problem that *requires* deriving the formula from scratch — where the formula is what the problem is asking you to prove — cannot be solved by template retrieval.

### 3.3 The Human-AI Failure Comparison

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HUMANS FAIL AT:                    BOTH FAIL AT:           AI FAILS AT:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Einstellung effect                 Non-obvious             Template
(wrong schema blocks right)        framing required        hallucination

Working memory overflow            Principle coupling      No self-
(too many simultaneous             (two laws inseparably   verification
constraints)                       intertwined)

Anchoring bias                     False surface           Compositional
(first framing becomes             similarity              breakdown
prison)                            (looks like X,
                                   is actually Y)
P-prim violations                  Under-specification     3D/vector
(deep intuition is wrong)          (solver must model      blindness
                                   physics first)

Calculation errors                 Symmetry hidden         Over-thinking
(algebra slips under               in wrong frame          trap
pressure)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**The middle column is the design target.** Problems built around those properties defeat both systems because they attack the fundamental architecture of pattern-based reasoning, human or machine.

---

## Part IV — The Seven Pillars of a Maximum-Difficulty Problem {#part-iv}

These are not tricks. They are structural principles derived from cognitive science, AI research, and the history of the hardest known physics problems. The hardest problems ever designed use several of them at once.

### Pillar 1 — The False Attractor

The problem must contain an *obvious-seeming approach that is subtly wrong*. Not wrong because of a calculation error, but wrong because it uses the right law in the wrong regime, or ignores a hidden constraint, or applies a valid approximation outside its domain of validity.

The false attractor must be compelling enough that:
- An expert human triggers the wrong schema via System 1
- An AI matches the wrong template

And it must be wrong in a way that only becomes apparent *after significant investment* in the wrong approach — not immediately at the start.

The solver must discover the error themselves by reaching a contradiction, and must have the metacognitive strength to abandon their first framing entirely and start fresh. This is extremely hard. Einstellung is not a mild bias. It is a genuine cognitive block. Studies have shown that even after being explicitly told their first approach is wrong, many experts struggle to disengage from it.

**Design rule:** The false attractor should use a law or technique that is *slightly more general* than what the problem actually requires — it appears to cover the case but has a hidden inapplicability. The most powerful false attractors are energy conservation (which breaks when there is dissipation hidden in the setup) and Newton's laws in the lab frame (which hide when a rotating frame would simplify everything).

### Pillar 2 — The Necessary Insight

There must be exactly one non-obvious key — a reframing, a symmetry, a conserved quantity, a reference frame choice, a limiting case — without which the problem is essentially unsolvable. Not hard to *execute*, but hard to *see*.

This is the "aha" structure. The insight should be *simple in retrospect*. Once you see it, you wonder why you didn't see it immediately. The best insights feel almost obvious after the fact — which is exactly what makes them so devastating before the fact.

Properties of a good Necessary Insight:
- It is a *single step* — not a sequence of insights, which would make the problem merely long
- It *unifies* the problem — once seen, every part of the solution follows naturally
- It is *visually or linguistically hidden* by the problem's surface presentation
- It is *elegant* — a beautiful idea, not an ad-hoc trick

The Necessary Insight is what gives the problem its identity. Years later, people remember the problem by its insight: "that's the one where you had to go to the rotating frame" or "the one where you had to realize momentum wasn't conserved but the Runge-Lenz vector was."

### Pillar 3 — Progressive Dependency

Structure the problem so that each part depends critically on the result of the previous one. Part (b) requires the exact expression from (a). Part (c) requires a specific intermediate result from (b). Part (d) only makes physical sense if the model was constructed correctly in (c).

This is the IPhO design philosophy, and it is devastating for several reasons:

1. **Error cascades.** A mistake in part (a) propagates through every subsequent part, creating consistent but wrong answers. The solver cannot patch errors downstream.

2. **No skipping.** Unlike independent sub-questions, progressive problems cannot be attacked out of order. The solver must commit to the correct path from the beginning.

3. **Working memory load.** Tracking multiple coupled intermediate results simultaneously pushes expert working memory toward its limit.

4. **AI self-consistency trap.** AI cannot verify its own intermediate outputs. A wrong step in part (b) will cascade confidently through parts (c) and (d), producing polished, well-formatted, internally consistent nonsense. The AI will not notice.

5. **Psychological pressure.** Human solvers who invest hours in an approach find it psychologically very difficult to abandon it. The sunk cost fallacy compounds Einstellung.

**Design rule:** Make the dependency *implicit*, not explicit. Don't say "use your result from (b)." Make it physically necessary that the result flows in that direction. The solver should *discover* the dependency, not be told about it.

### Pillar 4 — Domain Collision

The problem sits at the *intersection* of two or three physics domains that are taught and mentally stored separately. Thermodynamics and electrostatics. Quantum mechanics and elasticity theory. Fluid dynamics and statistical mechanics. Classical mechanics and information theory.

Experts have deep schemas *within* each domain but shallow schemas at the *boundaries*. Their mental ecology has clear domain labels and routes problems to the correct domain quickly — but fails when a problem genuinely belongs to two domains simultaneously.

The critical design requirement: the domains must be **coupled**, not merely co-present. It is not enough to have a problem that uses thermodynamics in part (a) and electrostatics in part (b). The coupling must be such that the thermodynamic and electromagnetic aspects are *inseparable* — you cannot solve the thermal part without knowing the electromagnetic part, and vice versa.

**Examples of high-value domain collisions:**
- Thermodynamics × Quantum mechanics (black body radiation, phonon heat capacity)
- Fluid dynamics × Electrostatics (electrowetting, electroosmosis)
- Statistical mechanics × Information theory (Maxwell's demon, Landauer's principle)
- Classical mechanics × Optics (optical tweezers, radiation pressure dynamics)
- Elasticity × Electromagnetism (piezoelectricity, magnetostriction)
- Non-equilibrium thermodynamics × Biology (molecular motors, ion pumps)

The more *unexpected* the collision, the more devastating it is to both human schema systems and AI template libraries.

### Pillar 5 — Physical Modeling Before Mathematics

Leave the problem under-specified in a physically meaningful way. Do not give all the numbers. Force the solver to *construct the physical model* first — decide what is negligible, what is dominant, what regime applies, what approximations are valid.

This is the single most reliable differentiator between genuine physics understanding and trained pattern recognition. It is also the most reliable AI killer.

Physical modeling requires:
- Identifying the relevant physical processes in a complex scenario
- Estimating the order of magnitude of each process
- Determining which can be neglected (and *justifying* the neglect)
- Choosing the appropriate level of description
- Recognizing which regime (linear vs nonlinear, classical vs quantum, laminar vs turbulent) applies

None of these steps can be done by template retrieval. They require genuine physical judgment — the ability to think about what physics *is doing* in the situation before writing a single equation.

**Design rule:** State the problem as a real physical scenario — not a cleaned-up textbook version. Give some quantities but not others. Let the solver determine what they need. Reward the solver who correctly identifies that a particular effect is negligible with a simpler calculation; punish the solver who carries every term by making the calculation impossible to complete in the time available.

### Pillar 6 — Symmetry Camouflage

The problem secretly contains a deep symmetry, conservation law, or invariant that renders it trivial — but the surface presentation actively *obscures* it. The problem is stated in coordinates, variables, or a reference frame that makes the symmetry invisible.

The solver who *finds* the right frame, variable substitution, or invariant gets a five-line solution. The solver who brute-forces it in the "natural" coordinates gets an unsolvable integral or a coupled ODE system with no closed form.

This pillar is specifically devastating to AI because:
1. AI tends to work in whatever coordinate system the problem is stated in
2. AI cannot recognize that a substitution will simplify the problem unless it has seen that exact substitution in training
3. AI's sequential generation makes it hard to "backtrack" and try a fundamentally different approach

**Examples of high-value hidden symmetries:**
- A mechanical problem with a hidden Runge-Lenz symmetry (orbit problem in disguise)
- A thermal problem with a hidden time-reversal symmetry
- An electromagnetic problem that simplifies in bispherical coordinates
- A quantum problem that has SU(2) symmetry in disguise
- A fluid problem with a hidden hodograph transformation
- A collision problem where the centre-of-momentum frame makes it trivial

**Design rule:** State the problem in the *worst* natural coordinates. Design the correct substitution so it is motivated physically but not obvious mathematically. The solver should only discover the substitution by noticing that the "natural" approach leads to an intractable expression.

### Pillar 7 — The Limiting Case Trap

The problem has a parameter — a mass ratio, a charge density, a temperature, a frequency, a friction coefficient — that takes a value placing the system near a *qualitative transition in behavior*. The regime matters more than the calculation.

Solvers who do not identify the correct regime get an answer that is:
- Formally algebraically self-consistent
- Gives plausible-looking numbers
- Is physically completely wrong

This tests *physical judgment* — the ability to reason about what physics is doing without computing it — which is the rarest skill in physics and the one most absent in both highly trained students and AI systems.

The transitions that work best:
- **Overdamped vs underdamped oscillator** (qualitatively different dynamics)
- **Supersonic vs subsonic flow** (different governing equations)
- **Strong vs weak coupling** (different effective theories apply)
- **Classical vs quantum regime** (kT vs ℏω comparison, often missed)
- **Continuum vs discrete** (when does the fluid description break down?)
- **Near-field vs far-field** (which terms dominate?)

**Design rule:** Do not state which regime the system is in. Let the solver discover it. Make the wrong-regime calculation produce a finite, reasonable-looking answer. Make the correct answer *impossible to obtain* without identifying the regime first — for example, the correct answer has a qualitatively different form (oscillatory vs exponential decay, or finite vs divergent) depending on the regime.

---

## Part V — The Specific Techniques, Ready to Use {#part-v}

The seven pillars are structural principles. Here are the concrete implementation techniques — specific moves you can make when building a problem.

### Technique A: The Reference-Frame Disguise

**What it does:** State the problem in the lab frame or a natural-seeming coordinate system where the algebra is brutal or intractable. The correct solution requires moving to a non-obvious frame where everything simplifies to something beautiful.

**How to build it:**
1. Start with a problem that is *elegant* in some frame (rotating frame, centre-of-mass frame, accelerating frame, conformal frame in 2D electrostatics)
2. Transform back to the lab frame — this is your problem statement
3. Ensure the brute-force lab-frame calculation either has no closed form or requires genuinely heroic algebra
4. Design the correct frame choice to be motivated by a physical argument (not just "it simplifies things") — the solver should feel that the frame choice *reveals* something

**Examples:**
- A two-body gravitational problem stated in the lab frame where the correct move is the reduced mass / COM separation
- A rotating charged ring problem where the correct frame is the co-rotating frame
- A fluid mechanics problem stated in Eulerian coordinates where the Lagrangian description is trivial

**Why it defeats AI:** AI commits to the stated coordinate system and cannot recognize that a frame change is available. It will attempt the intractable calculation and either fail or produce an approximate answer.

### Technique B: The Conservation Law That Isn't

**What it does:** Include a dissipative element — friction, radiation, viscosity, inelastic collision, ohmic heating — that seems minor or is embedded in the problem language in a non-obvious way, breaking the conservation law the solver most naturally wants to use.

**How to build it:**
1. Choose a scenario where energy conservation is the obvious first move
2. Hide a dissipation mechanism that is *physically motivated* but not immediately apparent (e.g., radiation from an accelerating charge in an otherwise classical mechanics problem, or viscous dissipation in a flow that looks inviscid)
3. Make the dissipation small enough that energy-conservation gives a *plausible-looking* wrong answer
4. Make the problem ask for a quantity that is *sensitive* to the dissipation — not the main motion but a correction to it, or the heat generated

**Why it defeats humans:** Energy conservation is the dominant schema for dynamics problems. The Einstellung effect makes it very hard to abandon even when subtly inapplicable.

**Why it defeats AI:** AI applies energy conservation whenever kinematic quantities are involved. It cannot recognize the regime where radiation reaction or viscous dissipation must be included.

### Technique C: The Coupled ODE Surprise

**What it does:** A system that appears to give two independent equations — two separate degrees of freedom — turns out to be coupled through a boundary condition, a constraint, or a shared field that only becomes apparent mid-solution.

**How to build it:**
1. Write down the two governing equations in their natural form — they look decoupled
2. Hide the coupling in a boundary condition, an integral constraint, or a shared quantity that appears in both equations
3. Let the solver proceed far into the solution (burning working memory and cognitive investment) before the coupling becomes apparent
4. Design the coupling to force a backtrack — not just a simple addition but a fundamental reformulation

**Timing is everything:** The coupling should become apparent at maximum cognitive investment, not at the start. This is the moment of maximum Einstellung — the solver has committed to an approach, built up a mental model, and must now discard it entirely.

### Technique D: The Wrong Intuition Setup

**What it does:** Describe a physical scenario where the qualitative behaviour is deeply counter-intuitive — where every physical instinct points the wrong direction. Then ask for a quantitative derivation.

**The best counter-intuitive physical phenomena for this:**
- A spinning gyroscope precessing sideways instead of falling (counter-intuitive torque direction)
- A plasma shielding in the opposite direction from a regular conductor
- A quantum system with higher energy having *shorter* wavelength (confused students expect the opposite)
- A flexible rod buckling *before* the classical Euler load under dynamic loading
- A thermodynamic process that runs *backward* when you expect it to run forward (Maxwell's demon setups)
- Light slowing down in a medium and the phase velocity exceeding c (group vs phase velocity confusion)
- A ball rolling on a turntable moving in a non-intuitive curved path due to Coriolis

**Why this is so powerful:** Both humans and AI will produce the *intuitive* answer before completing the derivation, and will be biased toward confirming it. The human will unconsciously check their algebra in a way that confirms the expected answer. The AI will interpolate toward the expected answer. The only way to get it right is to trust the mathematics *over* the intuition — which requires both mathematical skill and metacognitive awareness.

### Technique E: The Cascading Approximation

**What it does:** Requires a sequence of approximations where each approximation is valid *only given the conclusions of the previous one*, and where the final result is only obtainable by getting the entire sequence right.

**How to build it:**
1. Identify a problem with multiple length scales, time scales, or energy scales
2. The correct solution requires: first identifying the dominant scale, then identifying the next-order correction, then recognizing that the correction changes the effective problem for the third-order term
3. At each stage the approximation must be *justified by dimensional analysis or physical argument*, not just assumed
4. Make any individual approximation look reasonable in isolation — the problem is in the chain

**Why this is hard:** It requires holding the *entire approximation chain* in working memory simultaneously while executing the calculation at each step. It also requires the physical judgment to know *which* terms to keep at each order.

**Why it defeats AI:** AI makes approximations that "look right" locally but are inconsistent globally. It cannot maintain a coherent approximation scheme across multiple steps.

### Technique F: The Missing Equation

**What it does:** The system appears under-determined — there are fewer equations than unknowns. The "missing" equation is a physical constraint that is not written down but follows from the physics that the problem description only implies.

**Sources of hidden constraints:**
- Geometric constraints (the sum of angles in a polygon, the volume being constant)
- Thermodynamic constraints (quasi-static process, adiabatic condition implied by context)
- Electromagnetic constraints (charge conservation on an isolated conductor, gauge conditions)
- Mechanical constraints (no slipping, no penetration, inextensibility)
- Symmetry constraints (the solution must be symmetric under a transformation the problem has)
- Self-consistency constraints (the field must be consistent with the charge distribution it produces)

**Why this is the deepest test:** It requires understanding *why* physics works — not which equations apply, but why the system is constrained in a particular way. It tests the conceptual foundation, not the computational superstructure.

### Technique G: The Dimensional Trap

**What it does:** The problem has a natural-looking set of dimensional quantities that the solver will try to combine into an answer. But the only dimensionally consistent combination that satisfies all the constraints gives a *surprising* result — perhaps zero, or infinity, or a universal constant.

**How to build it:**
1. Choose a problem where dimensional analysis gives a misleadingly simple-looking answer
2. Add a constraint that eliminates the "obvious" dimensionally consistent combination
3. The actual answer requires recognizing a *less obvious* dimensionally consistent combination, or recognizing that the answer is actually dimensionless (a pure number)

**The extreme version:** A problem where dimensional analysis tells you the answer *must* have a certain form, but then the coefficient turns out to involve a pure mathematical constant (π, e, ζ(3)) that cannot be obtained by dimensional analysis alone — requiring a genuine calculation to obtain the prefactor.

### Technique H: The Stability Inversion

**What it does:** A configuration that *looks* unstable — a ball balanced on top of a hill, an inverted pendulum, a plasma — is actually stable when a subtle restoring mechanism is included. Conversely, a configuration that looks stable is actually unstable on the relevant timescale.

**Examples:**
- The inverted pendulum stabilized by rapid vertical oscillation (Kapitza pendulum)
- A plasma that appears magnetically confined but has a slow drift instability
- A colloidal suspension that appears stable but aggregates via van der Waals forces over long timescales
- A seemingly rigid structure that buckles at a load below the Euler critical load due to imperfections

**Why this works:** Stability analysis triggers strong p-prim responses. Solvers *feel* whether something is stable or not. When the physics contradicts this feeling, the cognitive dissonance is intense — and the temptation to trust the feeling over the mathematics is very hard to resist.

---

## Part VI — The Meta-Philosophy: What You Are Really Testing {#part-vi}

All of the above serves a single, deeper principle.

### The Central Claim

> **The hardest physics problem is not a test of knowledge. It is a test of the solver's relationship with knowledge.**

A solver who has *memorized* physics — whether a human who crammed schemas, or an AI trained on solution patterns — will be defeated by a problem that requires them to *generate* physics. To temporarily forget every template they know. To reason from first principles in an unfamiliar configuration.

The cognitive science literature calls this *transfer* — the ability to apply knowledge in genuinely novel situations. Transfer is what separates Feynman from a good textbook student. It is what IPhO gold medalists have that silver medalists don't. It is what current AI systems cannot reliably do.

AI systems are, at their core, **transfer-minimizing machines**. They succeed *because* most problems resemble training data. The same property that makes them powerful on standard problems makes them fragile on genuinely novel ones.

### The Three Levels of Physics Understanding

```
LEVEL 3 — GENERATIVE
Can derive new results from first principles.
Knows WHY the laws take their form.
Can reconstruct all of Level 1 and 2 from scratch.
Invents the frame, the variable, the invariant.
[Almost no humans. Current AI: essentially zero.]

LEVEL 2 — STRUCTURAL
Understands deep connections between domains.
Knows when to use which framework.
Can solve non-standard problems by reasoning.
Has rich mental ecology.
[Top physics students, professors in their domain.]

LEVEL 1 — PROCEDURAL
Knows the equations and standard solution moves.
Can solve textbook problems reliably.
Good mental ecology within learned domains.
[Good physics students. Current AI: Level 1-2 range.]
```

The hardest problem on the planet is one that *requires Level 3 understanding*. It cannot be solved by pattern-matching. It cannot be solved by having a large library of schemas. It requires the solver to, in effect, *do a small original physics derivation* — derive something that has never been derived in exactly that form before.

### Why Most "Hard" Problems Fail This Standard

Most problems that are considered "hard" — including most IPhO problems — are actually Level 2 problems in disguise. They require:
- Deep knowledge of non-standard material
- Strong mathematical technique
- Good time management under pressure
- Careful calculation

These are genuinely demanding. But they are not Level 3. A solver with sufficient domain knowledge and mathematical training can find the solution by systematic schema application. The problem has a *predictable* solution path — it's just long and technical.

A true Level 3 problem has no predictable solution path. The solver must *create* the path. The difficulty is not in the execution but in the *conception*.

### The Design Consequence

The deepest design rule is:

> **Your problem must be unreachable by transfer from any standard training set, human or machine.**

It must require reasoning from physics as a living logical structure — not physics as a library of patterns. The solver must encounter the problem as genuinely *new* — not as a variation of something they have seen, but as something that requires them to ask "what *is* actually happening here?" from the beginning.

This is extraordinarily difficult to achieve because the space of physics problems is not infinite. Every new problem built from classical mechanics, thermodynamics, electrodynamics, quantum mechanics, and statistical mechanics has some resemblance to previously solved problems. The art is in designing the *combination* and *framing* such that no standard approach reaches it.

---

## Part VII — The Unexploited Frontiers: Which Physics Domains Have the Most Depth {#part-vii}

Not all physics domains are equally fertile for hard problem design. Some areas have been so thoroughly mined — classical mechanics, optics, electrostatics — that essentially every combination of their elements has been explored in olympiad and textbook problems. Other areas are vastly under-exploited.

### 7.1 Highly Exploited (Diminishing Returns)

**Classical Mechanics (point particles)**
Springs, pendulums, inclined planes, circular motion, conservation laws, collisions. Almost every combination has been explored. Problems here can be made hard by using Pillars 1-7, but the underlying physics is fully familiar.

**Geometric Optics**
Ray tracing, mirrors, lenses, prisms. Exhausted as a source of novel problems. Any new problem in geometric optics is basically a variation on known problems.

**Elementary Electrostatics**
Coulomb's law, Gauss's law, capacitors, basic circuits. Well-mined. The techniques (method of images, Legendre expansion) are all known and taught.

### 7.2 Moderately Exploited (Some Remaining Depth)

**Rigid Body Dynamics**
Moments of inertia, precession, Euler angles. Harder than point mechanics because the geometry is richer. Still, the standard tools (Euler equations, Lagrangian formulation) are well-established. Remaining hard problems require unusual geometries or non-obvious constraints.

**Waves and Oscillations**
Normal modes, dispersion relations, standing waves, interference. Well-studied but with some remaining depth in driven systems, nonlinear oscillations, and wave phenomena in unusual media.

**Thermodynamics and Statistical Mechanics**
Heat engines, entropy, partition functions, phase transitions. The conceptual subtlety here is high (thermodynamics has more counter-intuitive results than almost any other domain), but the technical tools are well-known.

### 7.3 Under-Exploited (High Remaining Depth)

**Non-Equilibrium Thermodynamics and Irreversible Processes**
The physics of systems *away* from equilibrium: entropy production, Onsager relations, fluctuation theorems, time-reversal asymmetry. This is a frontier of physics research where even professional physicists lack strong intuition. The overlap with information theory (Landauer's principle, Maxwell's demon) creates fertile domain-collision opportunities. Extremely under-exploited in competition problems.

**Soft Matter and Complex Fluids**
Polymer physics, liquid crystals, gels, foams, emulsions, biological membranes. Governed by a combination of entropy, elasticity, and surface tension in ways that are deeply counter-intuitive. The relevant length scales and energy scales are unfamiliar to most physics students. Problems in this domain have no standard templates.

**Plasma Physics**
Magnetohydrodynamics, Debye shielding, plasma waves, instabilities. The correct physics is frequently counter-intuitive (plasma behaves like a fluid in some regimes and like individual particles in others). The presence of long-range electromagnetic forces creates qualitatively new effects that have no analogues in ordinary matter. Almost entirely absent from olympiad problem sets.

**Elasticity and Continuum Mechanics Beyond Statics**
Dynamic elasticity, elastic waves, fracture mechanics, buckling under dynamic loading. The coupling between geometry and mechanics in deformable solids creates enormous complexity. The Euler buckling problem is taught; almost nothing beyond it is.

**Nonlinear Dynamics and Chaos**
Bifurcations, limit cycles, strange attractors, sensitive dependence on initial conditions. Formally simple systems (the logistic map, the double pendulum) with astonishing complexity. Problems can be constructed with simple equations but non-trivial qualitative questions.

**Wave-Chaos and Quantum Billiards**
The intersection of quantum mechanics and classical chaos. How does wave physics behave in classically chaotic systems? This involves random matrix theory, semiclassical methods, and deep connections between classical and quantum mechanics. Almost zero penetration into competition physics.

**Gravitational Wave Physics**
Post-Newtonian dynamics, inspiral calculations, gravitational wave strain. Involves a sophisticated mixture of general relativity, mechanics, and wave physics. Now practically relevant (LIGO). The techniques are non-trivial but the physics is beautiful.

**Active Matter and Biological Physics**
Systems that consume energy internally and produce motion: bacteria, molecular motors, cytoskeletal networks. The combination of thermodynamics, fluid mechanics, and nonequilibrium statistical mechanics creates phenomena with no analogues in passive systems.

### 7.4 The Domain Collision Matrix

The most fertile ground for new hard problems is the *intersection* of under-exploited domains:

```
                    Plasma    Soft     Non-eq.  Nonlinear  Active
                    Physics   Matter   Thermo   Dynamics   Matter
                    ────────────────────────────────────────────
Quantum Mech.    │   ★★★      ★★       ★★★       ★★        ★★
Elasticity       │   ★★       ★★★      ★★        ★★★       ★★★
Fluid Dynamics   │   ★★★      ★★★      ★★        ★★★       ★★★
Statistical Mech │   ★★       ★★★      ★★★       ★★        ★★★
Electromagnetism │   ★★★      ★★       ★★        ★★        ★★
```

★★★ = extremely fertile, almost no existing problems
★★  = moderately fertile, some existing problems
★   = well-mined

---

## Part VIII — Worked Examples Built From Scratch {#part-viii}

The following are original problem constructions using the principles above, with explicit annotation of which pillars and techniques are deployed.

### Example Problem 1: "The Warm Wire"

**Problem Statement:**

A long, thin conducting wire of resistivity ρ, radius a, and thermal conductivity κ carries a steady current I in vacuum. The wire loses heat only by radiation (emissivity ε = 1, Stefan-Boltzmann constant σ). The ambient temperature is T₀.

*(a)* Without solving any differential equation, determine how the steady-state temperature of the wire scales with I, a, ρ, κ, σ, and T₀.

*(b)* Now assume the current is suddenly doubled. Without computing the full time-dependent solution, determine the characteristic timescale for the wire to reach its new equilibrium, in terms of the relevant material properties.

*(c)* If the wire is instead cooled by natural convection (h is the convective heat transfer coefficient), qualitatively explain — without calculation — whether you expect the new steady-state temperature to be higher or lower than the radiation-cooled case at the same current, and why this depends on the wire radius a in a non-trivial way.

---

**Pillar analysis:**
- **Pillar 2 (Necessary Insight):** Part (a) requires dimensional analysis and physical reasoning, not a differential equation. The insight is that you can extract the scaling without solving the heat equation.
- **Pillar 5 (Physical Modeling):** Part (b) is deliberately under-specified. The solver must identify the relevant timescale from the physics (thermal mass per unit length × temperature difference / power per unit length).
- **Pillar 7 (Limiting Case Trap):** Part (c) requires recognizing that the crossover between radiation-dominated and convection-dominated cooling depends on radius in a way that is not obvious (radiation scales as a × T⁴ per unit length; convection scales as a^(3/4) × ΔT^(5/4) per unit length via natural convection scaling).
- **Technique E (Cascading Approximation):** Getting the scaling in (a) right requires correctly identifying which temperature (T - T₀ or T itself) appears in the radiation law, which depends on whether T >> T₀ or T ≈ T₀.

**Why it is hard:**
- The false attractor is to write down the heat equation immediately in part (a). The correct move is to refuse this and use dimensional analysis.
- Part (b) catches solvers who correctly solved (a) by dimensional analysis but then try to solve the full PDE in (b) — missing that the timescale also follows from dimensional analysis.
- Part (c) is qualitative but is arguably the hardest part: it requires physical intuition about the relative scaling of radiation vs convection with radius.

---

### Example Problem 2: "The Angry Plasma"

**Problem Statement:**

A fully ionized hydrogen plasma occupies a long cylinder of radius R. The plasma is in thermal equilibrium at temperature T with electron number density n₀ (the ions are assumed stationary). A small additional charge Q is placed at the centre of the cylinder.

*(a)* Explain why the electron density distribution is not uniform in response to Q, and write down the equation governing the electrostatic potential φ(r) inside the plasma.

*(b)* For r >> λ_D (where λ_D is the Debye length), solve for the potential. For r << λ_D, solve for the potential. Explain the physical content of each limit.

*(c)* A classmate argues that because the plasma is electrically neutral overall, the charge Q is "perfectly screened" and exerts no net force on a test charge placed at large r. Another classmate argues that the screening is only partial, and there is a residual long-range interaction that falls off as 1/r³. Which classmate is correct, and why? Show this from your solution.

*(d)* Now suppose Q is oscillating at frequency ω. For ω >> ω_p (plasma frequency) and ω << ω_p, qualitatively describe the response of the plasma, and explain which case causes the plasma to become *transparent* to electromagnetic radiation and why.

---

**Pillar analysis:**
- **Pillar 4 (Domain Collision):** Electrostatics + statistical mechanics (the Debye-Hückel theory lives at their intersection)
- **Pillar 1 (False Attractor):** The false attractor in (c) is that a neutral plasma should perfectly screen a charge — which is the intuitively obvious answer and is *wrong*. The residual 1/r³ force (from the correlations beyond mean field) is the correct answer.
- **Pillar 7 (Limiting Case Trap):** Part (d) explicitly requires identifying the correct regime and recognizing the qualitative change in behavior.
- **Pillar 6 (Symmetry Camouflage):** The linearized Poisson-Boltzmann equation in (a) has a hidden screened-Coulomb (Yukawa) symmetry that makes it analytically soluble in the right coordinate.
- **Technique D (Wrong Intuition Setup):** The result in (d) — that plasma becomes transparent *above* the plasma frequency, not below it — is deeply counter-intuitive (we usually think of matter blocking radiation, not becoming more transparent at higher frequencies).

---

### Example Problem 3: "The Self-Referential Conductor"

**Problem Statement:**

An isolated conducting spherical shell of radius R and charge Q is surrounded by a uniform dielectric with permittivity ε (ε > ε₀). Inside the dielectric, there is a thin, concentric spherical shell of a different dielectric with permittivity ε₂ and inner radius r₁, outer radius r₂ (r₁ < r₂ < R).

*(a)* Find the electric displacement field D(r) everywhere. [This is the "easy" part — it should take 2 lines.]

*(b)* Find the electric field E(r) everywhere.

*(c)* Find the force per unit area on the inner dielectric shell. You may use any method.

*(d)* The inner dielectric shell is now replaced by a conducting shell with charge q. This inner shell is connected to the outer shell by a thin conducting wire running along the axis. In equilibrium, how is the total charge Q + q distributed between the two shells?

*(e)* The wire is now removed, and the inner shell is given an initial velocity v₀ directed radially outward. It begins to move. Explain why the motion of the inner shell radiates electromagnetic energy even if v₀ << c, and estimate the power radiated.

---

**Pillar analysis:**
- **Pillar 3 (Progressive Dependency):** Each part builds critically on the previous. Part (c) requires the correct E fields from (b). Part (d) requires understanding that the wire enforces equal potential, which changes the charge distribution. Part (e) requires recognizing that accelerating charges radiate.
- **Pillar 1 (False Attractor):** In part (d), the false attractor is that charge distributes uniformly over both shells. The correct answer (all charge on the outer shell) requires recognizing that the interior of a conductor has zero field, making the inner shell charge zero in equilibrium.
- **Technique F (Missing Equation):** In part (d), the "missing equation" is the condition that the two conducting shells are at equal potential when connected — this is not stated but is implied by "conducting wire."
- **Technique B (Conservation Law That Isn't):** In part (e), energy appears to be conserved in the mechanical sense but is actually being lost to radiation — a dissipation mechanism that most mechanics-trained solvers don't expect in what looks like a mechanical problem.

---

## Part IX — The Anti-AI Problem: Construction Guide {#part-ix}

If the goal is specifically to construct problems that AI cannot solve correctly, the design philosophy shifts slightly. We want to exploit the *specific* failure modes of language models.

### 9.1 The Core Anti-AI Properties

**Property 1: Require Physical Model Construction**
State the problem as a real scenario with incomplete specification. The solver must identify the dominant physics, make justified approximations, and set up the model before writing any equation. AI cannot do this. It can only solve models that have already been set up. Example: "A person jumps on a trampoline — estimate the maximum height they can reach if they start jumping from rest and jump optimally for 2 minutes."

**Property 2: Require Self-Consistency**
Design problems where the solution must be self-consistent — where the answer affects the input to the calculation in a non-trivial way. This requires iterative reasoning that AI's sequential generation cannot handle. Example: The charge distribution on a conductor that depends on the field, which depends on the charge distribution (a well-posed electrostatics problem, but one that AI will incorrectly treat as non-self-referential).

**Property 3: Demand Principle Derivation, Not Formula Application**
Ask the solver to *derive* a well-known formula from more fundamental principles. Do not give the formula. The AI's training has the formula and will use it without deriving it. The grader should be able to see whether the solver actually derived it. Example: "Without using the formula E = hν, derive the relationship between the energy and frequency of a photon from the photoelectric effect thought experiment and de Broglie's hypothesis."

**Property 4: Require 3D Spatial Visualization**
Design problems that require genuine spatial reasoning — building a three-dimensional picture and reading off geometric relationships. Use unusual orientations of coordinate axes, rotating frames, and non-standard geometries. AI fails consistently at spatial reasoning that requires building a mental 3D model.

**Property 5: Include Deliberate False Trails**
Write the problem so that a natural-sounding approach leads to a calculation that terminates in an intractable integral or a contradictory result. The solver must recognize this dead end and backtrack. AI typically commits to a calculation path and does not backtrack gracefully — it will either produce an approximate answer, state the integral cannot be evaluated (and stop), or make an algebraic error that "resolves" the intractability.

**Property 6: Require Qualitative Physical Judgment**
Include questions with no unique numerical answer but with a *correct qualitative argument*. AI struggles with open-ended qualitative reasoning that requires physical intuition. Example: "Describe qualitatively how the behavior of this system changes as the temperature is raised from near zero to well above the critical temperature, and explain the physics at each stage."

### 9.2 The Anti-AI Problem Template

```
STRUCTURE OF A MAXIMALLY AI-RESISTANT PROBLEM

Part (a): [Physical model construction]
  - Give an incomplete, realistic scenario
  - Ask the solver to justify their approximations
  - No unique numerical answer (judgment required)

Part (b): [Principle derivation]
  - Do not give the relevant formula
  - Require derivation from something more fundamental
  - Make it clear that just stating the formula receives no credit

Part (c): [Coupled self-consistent calculation]
  - The answer to (b) feeds into a self-consistent equation
  - Require an iterative or implicit solution
  - Reward recognizing the self-consistency condition

Part (d): [3D spatial reasoning]
  - Introduce a 3D geometry non-trivially
  - Ask for a direction (not just magnitude)
  - Include a rotation or unusual orientation

Part (e): [Regime identification + qualitative]
  - Change a parameter
  - Ask what qualitatively changes and why
  - The correct answer is qualitatively different from (d)
```

### 9.3 Why Current Reasoning Models Still Fail

Even the most advanced reasoning models (o3, o1, Claude Sonnet 4.5, Gemini 2.0 Flash Thinking) fail at specifically designed problems because:

1. **The "over-thinking" trap:** These models generate very long reasoning chains. A hard problem that requires a *short but non-obvious insight* is not helped by more reasoning tokens. The model keeps reasoning and talks itself into wrong answers.

2. **No physical simulation:** The model cannot actually simulate the physics. It can only describe what physics would do. When the problem requires the outcome of a real physical process — which requires genuine simulation — the model must guess.

3. **Training distribution boundary:** The problem must be genuinely outside the training distribution. With the enormous training sets of modern LLMs, this is harder to achieve than it sounds. But the under-exploited domains (plasma physics, soft matter, active matter, non-equilibrium thermodynamics) remain largely outside the training distribution of useful *problem-solving* examples.

4. **Self-verification failure:** Given a proposed intermediate result, the model cannot check whether it is physically reasonable except by comparing it to similar results in its training data. If the result is genuinely novel, it has no baseline.

---

## Part X — The Final Hierarchy: Grading Problem Hardness {#part-x}

### The Five-Level Hardness Scale

Not all "hard" problems are equally hard. Here is a rigorous framework for grading problem difficulty.

**Level 1 — Technically Demanding**
Long calculation with multiple steps. Requires mastery of technique. Solvable by systematic schema application. Any expert who knows the relevant material and has sufficient time will solve it.
*Example: A complex circuit with 8 nodes solved by Kirchhoff's laws.*

**Level 2 — Conceptually Rich**
Requires understanding the deep connections between topics. Requires choosing the right framework. Not solvable by mechanical application — requires judgment in approach. Most IPhO problems.
*Example: Finding the normal modes of a coupled oscillator in a non-obvious configuration.*

**Level 3 — Insight-Gated**
Has a single necessary insight that is hidden. Solvable once the insight is found; essentially unsolvable without it. Only the solver who finds the right frame, symmetry, or invariant makes progress.
*Example: A problem where moving to the rotating frame reduces a complicated 3D motion to a 1D problem.*

**Level 4 — Model-Building Required**
Requires the solver to construct the physical model before doing any mathematics. Under-specified by design. Rewards physical judgment and the ability to identify the relevant physics in a complex scenario. Defeats AI reliably.
*Example: "A star of mass M has just exhausted its nuclear fuel. Estimate the timescale over which it collapses and the mechanism by which it is halted."*

**Level 5 — Generative Physics**
Requires the solver to derive a new result — to do original physics in miniature. The problem cannot be solved by any form of pattern recognition because the required reasoning chain does not exist in any training set. Only accessible to Level 3 understanding as defined in Part VI.
*These problems do not yet exist in a systematic form. Creating them is the frontier of problem design.*

### What Level 5 Would Look Like

A Level 5 problem would have all of the following properties:

1. The physical scenario it describes has never been analyzed in the literature
2. The solution requires a technique or invariant that the solver must *invent* during the solution
3. The problem is stated simply enough to fit in a paragraph
4. The correct solution is less than two pages
5. Upon seeing the solution, any expert physicist immediately recognizes it as correct and beautiful
6. No AI system can solve it even with extended thinking time
7. No human can solve it without genuine insight — not even IPhO gold medalists, without significant time

Whether such problems exist in classical physics (rather than frontier research problems) is an open question. The history of physics suggests they do — many of Fermi's back-of-envelope problems, Landau's theoretical minimum problems, and Feynman's notebook problems have this character. They have not been systematically collected or categorized.

**The ultimate goal of this thesis is to provide the tools to create them.**

---

## Appendix A — Quick Reference: The Design Checklist

When designing a maximum-difficulty problem, check these boxes:

**Conceptual Architecture**
- [ ] Is there a single necessary insight that unlocks the problem?
- [ ] Is the false attractor compelling and not immediately obvious as wrong?
- [ ] Does the surface presentation hide the correct framing?
- [ ] Is the problem genuinely under-specified in a physically meaningful way?

**Human-Defeating Properties**
- [ ] Does it trigger the wrong schema in experts? (Einstellung)
- [ ] Does it require violating at least one well-encoded p-prim?
- [ ] Does it push working memory near its limit for even expert solvers?
- [ ] Does it sit at the boundary of at least two distinct mental ecologies?

**AI-Defeating Properties**
- [ ] Does it require physical model construction (not just model solution)?
- [ ] Does it require principle derivation rather than formula application?
- [ ] Does it include a genuine self-consistency requirement?
- [ ] Does it require 3D spatial reasoning with non-obvious orientation?
- [ ] Does it include a false trail that terminates in an intractable calculation?

**Structural Properties**
- [ ] Is each part progressively dependent on the previous part?
- [ ] Does the problem sit at the intersection of at least two domains?
- [ ] Is there a hidden symmetry or conservation law in a disguised form?
- [ ] Is there a parameter whose regime must be identified before solving?

**Elegance Tests**
- [ ] Is the problem stated in two paragraphs or less?
- [ ] Is the correct solution shorter than two pages?
- [ ] Does the insight, once found, feel simple and beautiful?
- [ ] Would an expert physicist recognize the solution as correct immediately?

If all boxes are checked: you have designed a hard problem.
If the last four elegance tests are also satisfied: you may have designed a great one.

---

## Appendix B — A Short Reading List

For the problem designer who wants to go deeper:

**Cognitive Science of Physics**
- Larkin, McDermott, Simon & Simon (1980) — "Expert and novice performance in solving physics problems" — *Science*
- Chi, Feltovich & Glaser (1981) — "Categorization and representation of physics problems by experts and novices" — *Cognitive Science*
- Redish (1994) — "The implications of cognitive studies for teaching physics" — *American Journal of Physics*
- diSessa (1993) — "Toward an epistemology of physics" — *Cognition and Instruction*

**Problem Solving and Insight**
- Kahneman (2011) — *Thinking, Fast and Slow*
- Ohlsson (1992) — "Information processing explanations of insight and related phenomena"
- Knoblich, Ohlsson, Haider & Rhenius (1999) — "Constraint relaxation and chunk decomposition in insight problem solving"

**AI and Physics**
- PhySense Benchmark (2025) — "Principle-Based Physics Reasoning Benchmarking for LLMs"
- OlympiadBench (2024) — "A Challenging Benchmark for Promoting AGI with Olympiad-Level Scientific Problems"
- "AI Reasoning Models for Problem Solving in Physics" — *arxiv 2508.20941* (2025)

**Problem Design Philosophy**
- Irodov, *Problems in General Physics* — the gold standard of elegant problem design
- Jaan Kalda's IPhO handouts — *ioc.ee/~kalda/ipho* — the deepest publicly available problem collection
- Landau & Lifshitz, *Mechanics* — the problems in this book are among the best ever written
- Feynman, *Lectures on Physics* — the problems at the end of each chapter are model examples of insight-gated problems

---

*This document is a living thesis. The frontier of physics problem design is open. The problems in Part IX do not yet exist in systematic form. That is the work remaining.*

---

**End of Thesis**
*Total scope: 10 parts, ~8000 words*
*Covers: cognitive science, AI failure taxonomy, 7 design pillars, 8 techniques, domain analysis, 3 worked examples, anti-AI framework, difficulty hierarchy*
