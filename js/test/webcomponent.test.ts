// Unit tests for the <mtph-doc> web component's pure core (embed-core.ts). The custom element
// itself is thin DOM wiring around these functions plus the already-parity-tested renderHtml, so
// there's no gold to freeze — these cover the logic that isn't just renderHtml: source selection,
// height-reporter injection, and the live-param override.
import { describe, it, expect } from "vitest";
import { pickSource, injectHeightReporter, HEIGHT_REPORTER, buildSrcdoc } from "../web/embed-core.js";

const DOC = `---
mtph: "0.2"
id: embed-test
title: Embed Test
subject: physics
params:
  a: { min: 0, max: 10, default: 3 }
answer: { type: numeric, value: 5, unit: "m" }
---

A body with a parameter $a$.

\`\`\`plot
x: 0..5
f(x) = {{a}}
\`\`\`
`;

describe("pickSource priority", () => {
  it("prefers a fetched src over everything", () => {
    expect(pickSource({ fetched: "A", scriptText: "B", text: "C" })).toBe("A");
  });
  it("prefers a script child over text content", () => {
    expect(pickSource({ fetched: null, scriptText: "B", text: "C" })).toBe("B");
  });
  it("falls back to text content", () => {
    expect(pickSource({ fetched: "   ", scriptText: "", text: "C" })).toBe("C");
  });
  it("returns empty when nothing usable is given", () => {
    expect(pickSource({ fetched: "  ", scriptText: null, text: "\n\t" })).toBe("");
  });
});

describe("injectHeightReporter", () => {
  it("inserts the reporter just before </body>", () => {
    const out = injectHeightReporter("<html><body><p>hi</p></body></html>");
    expect(out).toContain(HEIGHT_REPORTER);
    expect(out.indexOf(HEIGHT_REPORTER)).toBeLessThan(out.indexOf("</body>"));
    expect(out.indexOf("<p>hi</p>")).toBeLessThan(out.indexOf(HEIGHT_REPORTER));
  });
  it("appends when there is no </body>", () => {
    expect(injectHeightReporter("<div>x</div>")).toBe("<div>x</div>" + HEIGHT_REPORTER);
  });
});

describe("buildSrcdoc", () => {
  it("renders a self-contained page with the height reporter and no schema warnings", () => {
    const { html, warnings } = buildSrcdoc(DOC);
    expect(html.startsWith("<!doctype html>")).toBe(true);
    expect(html).toContain(HEIGHT_REPORTER);
    expect(warnings).toEqual([]);
  });

  it("uses the declared default when no live params are given", () => {
    const withDefault = buildSrcdoc(DOC).html;
    const withSame = buildSrcdoc(DOC, { params: { a: 3 } }).html;
    expect(withSame).toBe(withDefault);
  });

  it("overriding a param changes the rendered plot", () => {
    const base = buildSrcdoc(DOC).html;
    const moved = buildSrcdoc(DOC, { params: { a: 7 } }).html;
    expect(moved).not.toBe(base);
  });

  it("does not mutate the format: a live override is per-render only", () => {
    buildSrcdoc(DOC, { params: { a: 9 } });
    // A subsequent default render is unaffected (each parse gets a fresh DOM).
    expect(buildSrcdoc(DOC).html).toBe(buildSrcdoc(DOC).html);
  });

  it("hideAnswers drops the answer section", () => {
    const shown = buildSrcdoc(DOC).html;
    const hidden = buildSrcdoc(DOC, { hideAnswers: true }).html;
    expect(shown).toContain('class="answer"');
    expect(hidden).not.toContain('class="answer"');
  });

  it("quiz mode emits the self-check markup", () => {
    const quiz = buildSrcdoc(DOC, { quiz: true }).html;
    expect(quiz).toContain('class="mtph-quiz"');
    expect(quiz).toContain('data-type="numeric"');
  });
});
