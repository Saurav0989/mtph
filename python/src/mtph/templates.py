"""Fill-in templates for ``mtph new --template <id>`` (plan 07).

Each template is a *structurally complete, verifiable* ``.mtph`` skeleton for a common
domain-collision problem shape, with the format correct (front-matter, block order, a valid
figure, a labelled equation, body answer/solution) so format-level errors are impossible. The
content is marked with ``{{…}}`` slots for the author (an AI) to fill — those are plain prose,
so a freshly scaffolded file passes ``mtph verify`` unchanged.

Kept deliberately small (3, spanning common collisions); grow by real demand, not speculation.
"""
from __future__ import annotations

from typing import List

CHARGED_OSCILLATOR = '''---
mtph: "0.2"
id: charged-oscillator
title: "{{Title — e.g. Charged Mass on a Spring in a Magnetic Field}}"
subject: physics
topic: mechanics/oscillations
difficulty: 4
tags: [oscillations, electromagnetism, domain-collision]
---

A block of mass $m$ carrying charge $q$ is fixed to a spring of constant $k$ and moves in a
uniform field. {{State the scenario in two paragraphs. Leave one quantity unspecified so the
solver must build the model first (Pillar 5), and hide the framing that trivialises it (Pillar 6).}}

```figure
bfield at=(0,0) width=6 height=3.4 dir=out n=5
spring from=(0,1.7) to=(2.2,1.7) coils=8 label="k"
mass m at=(2.7,1.7) size=0.7 label="m, q"
vector from=(2.7,1.7) to=(4.0,1.7) label="v"
```

Set up the equation of motion, then identify the regime that changes its character (Pillar 7).

```math
m\\ddot{x} = -kx + qv\\,B \\label{eq:eom}
```

```answer
\\omega = \\sqrt{k/m}
```

````solution
{{Derive the result from \\ref{eq:eom}. State the necessary insight explicitly (the single
reframing that unlocks it), then the steps. Note where the obvious approach (the false attractor)
breaks.}}
````
'''

THERMAL_PROCESS = '''---
mtph: "0.2"
id: thermal-process
title: "{{Title — e.g. A Gas Through a Coupled Thermal Process}}"
subject: physics
topic: thermodynamics
difficulty: 4
tags: [thermodynamics, modeling, limiting-case]
---

A gas of $n$ moles is enclosed by a movable piston. {{Describe the process. Under-specify a
boundary condition so the solver must decide which idealisation applies (Pillar 5), and put a
parameter near a qualitative transition — e.g. adiabatic vs isothermal (Pillar 7).}}

```figure
container at=(0,0) width=3.2 height=2.4
gas at=(1.6,1.0) n=14
piston at=(0,2.0) width=3.2
vector from=(1.6,3.0) to=(1.6,2.3) label="F"
```

Relate the state variables across the process.

```math
p V^{\\gamma} = \\text{const} \\label{eq:process}
```

```answer
W = \\frac{p_1 V_1 - p_2 V_2}{\\gamma - 1}
```

````solution
{{Identify the regime, justify the idealisation, and derive the work from \\ref{eq:process}.
Show what the wrong regime would have given and why it is physically incorrect.}}
````
'''

COUPLED_PENDULUM = '''---
mtph: "0.2"
id: coupled-pendulum
title: "{{Title — e.g. Two Pendulums, One Hidden Normal Mode}}"
subject: physics
topic: waves/oscillations
difficulty: 4
tags: [oscillations, waves, normal-modes, domain-collision]
---

Two identical pendulums (length $L$, mass $m$) are joined by a light spring of constant $k$.
{{State the scenario. The framing should hide that normal coordinates decouple the system
(Pillar 6); ask something whose answer depends on the mode the system is in (Pillar 2).}}

```figure
pendulum at=(0,3.2) length=2.2 angle=14 label="L"
pendulum at=(2.6,3.2) length=2.2 angle=-14 label="L"
spring from=(0.53,1.06) to=(2.07,1.06) coils=7 label="k"
```

Write the coupled equations of motion, then find the normal modes.

```math
\\ddot{\\theta}_1 = -\\frac{g}{L}\\theta_1 - \\frac{k}{m}(\\theta_1 - \\theta_2) \\label{eq:coupled}
```

```answer
\\omega_\\pm = \\sqrt{\\tfrac{g}{L}},\\ \\sqrt{\\tfrac{g}{L} + \\tfrac{2k}{m}}
```

````solution
{{From \\ref{eq:coupled}, introduce normal coordinates (the necessary insight) and read off the
two mode frequencies. Explain the beating that the in-phase/out-of-phase mix produces.}}
````
'''

TEMPLATES = {
    "charged-oscillator": CHARGED_OSCILLATOR,
    "thermal-process": THERMAL_PROCESS,
    "coupled-pendulum": COUPLED_PENDULUM,
}


def template_ids() -> List[str]:
    return sorted(TEMPLATES)
