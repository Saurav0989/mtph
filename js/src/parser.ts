// Parse `.mtph` source text into the DOM. A faithful port of python/src/mtph/parser.py —
// verified against the Python-generated conformance corpus (spec/conformance).
import { parse as yamlParse } from "yaml";
import {
  answer,
  BlockDom,
  documentToDom,
  Dom,
  figure,
  math,
  plot,
  prose,
  solution,
} from "./model.js";

export class MtphSyntaxError extends Error {}

const FENCE_OPEN = /^(`{3,})(.*)$/;
const FENCE_KIND = /^(\w+)?(.*)$/;
const ATTR_RE = /(\w+)\s*=\s*(?:"([^"]*)"|(\S+))/g;
const FENCE_KINDS = new Set(["math", "figure", "plot", "answer", "solution"]);

// Python `str.strip("\n")`: trim only leading/trailing newlines (not spaces).
const stripNL = (s: string): string => s.replace(/^\n+/, "").replace(/\n+$/, "");

function splitFrontmatter(text: string): [string, string] {
  const lines = text.split("\n");
  if (lines.length === 0 || lines[0].trim() !== "---") {
    throw new MtphSyntaxError(
      "file must begin with a YAML front-matter block opened by '---' on line 1",
    );
  }
  for (let i = 1; i < lines.length; i++) {
    if (lines[i].trim() === "---") {
      return [lines.slice(1, i).join("\n"), lines.slice(i + 1).join("\n")];
    }
  }
  throw new MtphSyntaxError("unterminated front-matter: missing closing '---'");
}

function parseAttrs(s: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const m of (s || "").matchAll(ATTR_RE)) {
    out[m[1]] = m[2] !== undefined ? m[2] : m[3];
  }
  return out;
}

function makeFencedBlock(kind: string, src: string, attrs: Record<string, string>): BlockDom {
  if (kind === "math") return math(src.trim());
  if (kind === "figure") return figure(src, attrs.caption);
  if (kind === "plot") return plot(src, attrs.caption);
  if (kind === "answer") return answer(src.trim(), attrs.part, attrs.type ?? "expression");
  return solution(parseBody(src)); // solution: parsed recursively
}

function parseBody(body: string): BlockDom[] {
  const lines = body.split("\n");
  const n = lines.length;
  const blocks: BlockDom[] = [];
  let proseBuf: string[] = [];

  const flushProse = () => {
    const text = stripNL(proseBuf.join("\n"));
    if (text.trim()) blocks.push(prose(text));
    proseBuf = [];
  };

  let i = 0;
  while (i < n) {
    const line = lines[i];
    const stripped = line.trim();

    // fenced block ------------------------------------------------------------
    const fence = FENCE_OPEN.exec(stripped);
    if (fence) {
      const ticks = fence[1];
      const km = FENCE_KIND.exec(fence[2])!;
      const kind = km[1];
      if (kind && FENCE_KINDS.has(kind)) {
        flushProse();
        const attrs = parseAttrs(km[2]);
        const close = new RegExp("^`{" + ticks.length + ",}\\s*$");
        let j = i + 1;
        const content: string[] = [];
        while (j < n && !close.test(lines[j].trim())) {
          content.push(lines[j]);
          j++;
        }
        if (j >= n) {
          throw new MtphSyntaxError(`unterminated \`\`\`${kind} block opened on line ${i + 1}`);
        }
        blocks.push(makeFencedBlock(kind, stripNL(content.join("\n")), attrs));
        i = j + 1;
        continue;
      }
    }

    // display math $$ ... $$ --------------------------------------------------
    if (stripped.startsWith("$$")) {
      flushProse();
      if (stripped.endsWith("$$") && stripped.length > 3) {
        blocks.push(math(stripped.slice(2, -2).trim()));
        i += 1;
        continue;
      }
      const content: string[] = [];
      const first = stripped.slice(2);
      if (first.trim()) content.push(first);
      let j = i + 1;
      while (j < n && !lines[j].includes("$$")) {
        content.push(lines[j]);
        j++;
      }
      if (j >= n) {
        throw new MtphSyntaxError(`unterminated $$ display-math block opened on line ${i + 1}`);
      }
      const before = lines[j].slice(0, lines[j].indexOf("$$"));
      if (before.trim()) content.push(before);
      blocks.push(math(content.join("\n").trim()));
      i = j + 1;
      continue;
    }

    // prose -------------------------------------------------------------------
    proseBuf.push(line);
    i += 1;
  }
  flushProse();
  return blocks;
}

export function parse(text: string): Dom {
  const [fm, body] = splitFrontmatter(text);
  // parse `fm + "\n"` so block scalars chomp identically to the Python reference (see parser.py)
  const data = fm.trim() ? yamlParse(fm + "\n") : {};
  if (data === null || typeof data !== "object" || Array.isArray(data)) {
    throw new MtphSyntaxError("front-matter must be a YAML mapping (key: value pairs)");
  }
  const meta = data as Record<string, unknown>;
  if (!("mtph" in meta)) {
    throw new MtphSyntaxError("front-matter is missing the required 'mtph' version key");
  }
  const mtph = String(meta.mtph);
  delete meta.mtph;
  return documentToDom(mtph, meta, parseBody(body));
}
