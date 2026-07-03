// Python-compatible fixed-point formatting. CPython's `format(x, '.Nf')` rounds half-to-EVEN on
// the exact IEEE-754 value; JavaScript's `Number.prototype.toFixed` rounds half-UP. They agree
// except when a value is an exact dyadic tie at N digits (e.g. 136.625 → Python "136.62", JS
// "136.63"). Figure/plot pixel coordinates hit those ties, so byte-identical SVG parity needs
// this. `fixed(x, n)` reproduces Python's result exactly.

function incrementDecimalString(s: string): string {
  const arr = s.split("");
  let i = arr.length - 1;
  while (i >= 0) {
    if (arr[i] === "9") { arr[i] = "0"; i--; }
    else { arr[i] = String.fromCharCode(arr[i].charCodeAt(0) + 1); break; }
  }
  if (i < 0) arr.unshift("1");
  return arr.join("");
}

export function fixed(x: number, digits: number): string {
  if (!Number.isFinite(x)) return x.toString();
  const negative = x < 0 || Object.is(x, -0);
  const ax = Math.abs(x);

  // A high-precision expansion — enough to see every significant digit of the double (its exact
  // dyadic expansion is short relative to this for the magnitudes figures/plots produce), so tie
  // detection at `digits` places is exact.
  const extra = Math.min(100, digits + 30);
  const long = ax.toFixed(extra);
  const dot = long.indexOf(".");
  const intPart = dot < 0 ? long : long.slice(0, dot);
  const fracPart = dot < 0 ? "" : long.slice(dot + 1);

  const keep = fracPart.slice(0, digits);
  const rest = fracPart.slice(digits);

  let roundUp = false;
  if (rest.length > 0) {
    const first = rest.charCodeAt(0) - 48;
    if (first > 5) {
      roundUp = true;
    } else if (first === 5) {
      const tail = rest.slice(1).replace(/0+$/, "");
      if (tail.length > 0) {
        roundUp = true; // strictly greater than half
      } else {
        // exact tie → round half to even (look at the last digit we keep)
        const lastKept = digits > 0
          ? keep.charCodeAt(digits - 1) - 48
          : intPart.charCodeAt(intPart.length - 1) - 48;
        roundUp = lastKept % 2 === 1;
      }
    }
  }

  let combined = intPart + keep.padEnd(digits, "0");
  if (roundUp) combined = incrementDecimalString(combined);

  let result: string;
  if (digits > 0) {
    while (combined.length < digits + 1) combined = "0" + combined;
    const ip = combined.slice(0, combined.length - digits);
    const fp = combined.slice(combined.length - digits);
    result = `${ip}.${fp}`;
  } else {
    result = combined;
  }
  return negative ? `-${result}` : result;
}

// Python's format(x, 'g') with default precision 6 (used for tick labels and grading points).
export function g(x: number, precision = 6): string {
  if (x === 0) return Object.is(x, -0) ? "-0" : "0";
  const neg = x < 0;
  const ax = Math.abs(x);
  const [mant, expPart] = ax.toExponential(precision - 1).split("e");
  const X = parseInt(expPart, 10);
  let result: string;
  if (X < -4 || X >= precision) {
    const m = mant.replace(/0+$/, "").replace(/\.$/, "");
    const sign = X < 0 ? "-" : "+";
    result = `${m}e${sign}${Math.abs(X).toString().padStart(2, "0")}`;
  } else {
    let fx = ax.toFixed(Math.max(0, precision - 1 - X));
    if (fx.includes(".")) fx = fx.replace(/0+$/, "").replace(/\.$/, "");
    result = fx;
  }
  return neg ? `-${result}` : result;
}
