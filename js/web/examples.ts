// A small showcase set, bundled straight from the shared example bank (esbuild inlines the text).
// Each one exercises a different corner: mechanics figure, geometry, a vector-field plot, and a
// multi-panel thermodynamics figure.
import projectile from "../../spec/examples/projectile.mtph";
import freeFall from "../../spec/examples/free-fall.mtph";
import pendulum from "../../spec/examples/pendulum-period.mtph";
import triangle from "../../spec/examples/triangle.mtph";
import saddleFlow from "../../spec/examples/saddle-flow.mtph";
import twoExpansions from "../../spec/examples/two-expansions.mtph";

export interface Example {
  id: string;
  label: string;
  source: string;
}

export const EXAMPLES: Example[] = [
  { id: "projectile", label: "Projectile (figure + plot)", source: projectile },
  { id: "free-fall", label: "Free fall (numeric — try Quiz mode)", source: freeFall },
  { id: "pendulum", label: "Pendulum (animated — it swings)", source: pendulum },
  { id: "triangle", label: "Triangle area (geometry)", source: triangle },
  { id: "saddle-flow", label: "Saddle flow (vector field)", source: saddleFlow },
  { id: "two-expansions", label: "Two expansions (multi-panel)", source: twoExpansions },
];
