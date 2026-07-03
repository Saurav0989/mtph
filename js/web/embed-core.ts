// Pure, DOM-free helpers behind the <mtph-doc> web component. They live apart from the element
// (mtph-doc.ts) so they can be unit-tested in Node with no jsdom: the element just wires these
// into the browser. Nothing here touches `window`, `document`, or any DOM type.
import { parse } from "../src/parser.js";
import { validate } from "../src/validate.js";
import { renderHtml } from "../src/html.js";
import type { RenderOptions } from "../src/html.js";
import type { Dom } from "../src/model.js";

/**
 * Choose the document source from the ways an author can supply one, by priority:
 *   1. an explicit `src=` fetch result,
 *   2. a raw-text `<script>` child (safe for `<`, `$`, backticks the parser would otherwise mangle),
 *   3. the element's own text content (fine for simple problems).
 * Returns "" when none is usable.
 */
export function pickSource(opts: {
  fetched?: string | null;
  scriptText?: string | null;
  text?: string | null;
}): string {
  // Trim: inline <script>/text-content sources carry the leading newline + indentation of the
  // host HTML, but the .mtph parser requires `---` on line 1 (the playground trims its seed too).
  const { fetched, scriptText, text } = opts;
  if (fetched && fetched.trim()) return fetched.trim();
  if (scriptText && scriptText.trim()) return scriptText.trim();
  if (text && text.trim()) return text.trim();
  return "";
}

// A tiny script injected into the rendered page so the (sandboxed, script-only) iframe reports
// its content height to the host. The host matches messages by event.source, so no id is needed.
// It fires on load, on any resize (KaTeX typesets asynchronously and reflows), and on a couple of
// delayed ticks to catch the late KaTeX layout — then the iframe can size to fit with no scrollbar.
export const HEIGHT_REPORTER =
  '<script>(function(){var d=document,post=function(){' +
  "var b=d.body,e=d.documentElement;" +
  "var h=Math.max(e.scrollHeight,b?b.scrollHeight:0,e.offsetHeight,b?b.offsetHeight:0);" +
  'parent.postMessage({mtph:"height",h:h},"*");};' +
  'addEventListener("load",post);' +
  "if(window.ResizeObserver){new ResizeObserver(post).observe(d.documentElement);}" +
  "setTimeout(post,150);setTimeout(post,600);post();})();<\/script>";

/** Insert the height reporter just before </body> (falling back to append). */
export function injectHeightReporter(html: string): string {
  const i = html.lastIndexOf("</body>");
  if (i === -1) return html + HEIGHT_REPORTER;
  return html.slice(0, i) + HEIGHT_REPORTER + html.slice(i);
}

export interface EmbedOptions {
  quiz?: boolean;
  hideAnswers?: boolean;
  /** Live overrides for declared `params:`, keyed by name (the explorable-slider values). */
  params?: Record<string, number>;
}

export interface EmbedResult {
  html: string;
  dom: Dom;
  warnings: string[];
}

type ParamSpec = { default?: number };

/**
 * Parse `source` and render the full self-contained page (with the height reporter appended) that
 * feeds the iframe's srcdoc. Live param values override each declared default before rendering —
 * exactly the playground's trick, which keeps the *format* honest (the stored default is
 * authoritative; only the rendered view moves). Throws MtphSyntaxError on a bad parse.
 */
export function buildSrcdoc(source: string, opts: EmbedOptions = {}): EmbedResult {
  const dom = parse(source);
  const live = opts.params;
  if (live) {
    const meta = dom.meta as Record<string, unknown> | undefined;
    const specs = meta && typeof meta === "object" ? (meta.params as Record<string, ParamSpec> | undefined) : undefined;
    if (specs && typeof specs === "object") {
      for (const [name, v] of Object.entries(live)) {
        const spec = specs[name];
        if (spec && typeof spec === "object") spec.default = v;
      }
    }
  }
  const warnings = validate(dom);
  const ropts: RenderOptions = { quiz: !!opts.quiz, includeAnswer: !opts.hideAnswers };
  const html = injectHeightReporter(renderHtml(dom, ropts));
  return { html, dom, warnings };
}

/** Read the declared `params:` spec table off a parsed DOM (empty object when there are none). */
export function paramSpecs(dom: Dom): Record<string, { min: number; max: number; default: number; step?: number; unit?: string; label?: string }> {
  const meta = dom.meta as Record<string, unknown> | undefined;
  const p = meta && typeof meta === "object" ? meta.params : undefined;
  return p && typeof p === "object" ? (p as Record<string, { min: number; max: number; default: number; step?: number; unit?: string; label?: string }>) : {};
}
