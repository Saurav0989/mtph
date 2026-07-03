import { describe, it, expect } from "vitest";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { parse } from "../src/parser.js";
import { validate } from "../src/validate.js";
import { compileFigure } from "../src/compileSvg.js";
import { compilePlot } from "../src/plot.js";
import { renderHtml } from "../src/html.js";
import type { BlockDom } from "../src/model.js";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const corpus = join(root, "spec", "conformance", "corpus");
const domDir = join(root, "spec", "conformance", "expected", "dom");
const svgDir = join(root, "spec", "conformance", "expected", "svg");
const htmlDir = join(root, "spec", "conformance", "expected", "html");
const stems = readdirSync(corpus).filter((f) => f.endsWith(".mtph")).map((f) => f.slice(0, -5));

describe("conformance: JS parser matches the Python reference DOM", () => {
  for (const stem of stems) {
    const src = readFileSync(join(corpus, `${stem}.mtph`), "utf8");
    it(`${stem}: DOM parity`, () => {
      const expected = JSON.parse(readFileSync(join(domDir, `${stem}.json`), "utf8"));
      expect(parse(src)).toEqual(expected);
    });
    it(`${stem}: validates against schema.json`, () => {
      expect(validate(parse(src))).toEqual([]);
    });
  }
});

describe("conformance: JS figure renderer matches the Python reference SVG", () => {
  for (const stem of stems) {
    const src = readFileSync(join(corpus, `${stem}.mtph`), "utf8");
    // Templated (`{{param}}`) sources aren't compiled per-block (covered by the HTML gold) — skip
    // them so indices line up with the generator.
    const figures = (parse(src).blocks as BlockDom[])
      .filter((b) => b.type === "figure" && !String(b.source).includes("{{"));
    figures.forEach((block, k) => {
      const goldPath = join(svgDir, `${stem}.fig.${k}.svg`);
      if (!existsSync(goldPath)) return; // no gold => nothing to check
      it(`${stem} figure #${k}: SVG parity`, () => {
        const gold = readFileSync(goldPath, "utf8");
        expect(compileFigure(block.source as string) + "\n").toBe(gold);
      });
    });
  }
});

describe("conformance: JS plot renderer matches the Python reference SVG", () => {
  for (const stem of stems) {
    const src = readFileSync(join(corpus, `${stem}.mtph`), "utf8");
    const plots = (parse(src).blocks as BlockDom[])
      .filter((b) => b.type === "plot" && !String(b.source).includes("{{"));
    plots.forEach((block, k) => {
      const goldPath = join(svgDir, `${stem}.plot.${k}.svg`);
      if (!existsSync(goldPath)) return; // no gold => nothing to check
      it(`${stem} plot #${k}: SVG parity`, () => {
        const gold = readFileSync(goldPath, "utf8");
        expect(compilePlot(block.source as string) + "\n").toBe(gold);
      });
    });
  }
});

describe("conformance: JS HTML renderer matches the Python reference (cdnjs KaTeX)", () => {
  for (const stem of stems) {
    const goldPath = join(htmlDir, `${stem}.html`);
    if (!existsSync(goldPath)) continue;
    it(`${stem}: HTML parity`, () => {
      const src = readFileSync(join(corpus, `${stem}.mtph`), "utf8");
      const gold = readFileSync(goldPath, "utf8");
      expect(renderHtml(parse(src), { katex: "cdnjs" })).toBe(gold);
    });
    const quizGold = join(htmlDir, `${stem}.quiz.html`);
    if (!existsSync(quizGold)) continue;
    it(`${stem}: quiz HTML parity`, () => {
      const src = readFileSync(join(corpus, `${stem}.mtph`), "utf8");
      const gold = readFileSync(quizGold, "utf8");
      expect(renderHtml(parse(src), { katex: "cdnjs", quiz: true })).toBe(gold);
    });
  }
});
