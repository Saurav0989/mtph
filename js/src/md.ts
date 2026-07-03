// A tiny, math-safe Markdown → HTML converter. A faithful port of
// python/src/mtph/render/md.py.
//
// Just enough Markdown for problem prose (headings, lists, paragraphs, bold/italic/code) while
// never touching math: `$...$` / `$$...$$` spans (and inline code) are pulled out before any
// formatting runs and restored afterwards, so KaTeX delimiters survive intact.

// Python html.escape(s, quote=True): &, <, >, " → &quot;, ' → &#x27;. Order matters (& first).
export function htmlEscape(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#x27;");
}

const MATH_BLOCK = /\$\$[\s\S]*?\$\$/g;
const MATH_INLINE = /\$[^$]+?\$/g;
const CODE = /`[^`]+?`/g;
const PLACEHOLDER = /\x00(\d+)\x00/g;

function protect(text: string): [string, string[]] {
  const store: string[] = [];
  const stash = (m: string): string => {
    store.push(m);
    return `\x00${store.length - 1}\x00`;
  };
  let t = text.replace(MATH_BLOCK, stash);
  t = t.replace(MATH_INLINE, stash);
  t = t.replace(CODE, stash);
  return [t, store];
}

function restore(s: string, store: string[]): string {
  return s.replace(PLACEHOLDER, (_m, n) => {
    const frag = store[parseInt(n, 10)];
    if (frag.startsWith("`")) return "<code>" + htmlEscape(frag.slice(1, -1)) + "</code>";
    return htmlEscape(frag); // math: keep $ delimiters, escape < > & inside
  });
}

function inline(s: string): string {
  s = s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, "<em>$1</em>");
  return s;
}

function fmt(text: string): string {
  return inline(htmlEscape(text));
}

export function mdToHtml(text: string): string {
  const [protectedText, store] = protect(text);
  const out: string[] = [];
  for (const block of protectedText.trim().split(/\n\s*\n/)) {
    const lines = block.split("\n").filter((ln) => ln.trim());
    if (lines.length === 0) continue;
    const heading = /^(#{1,6})\s+(.*)/.exec(lines[0]);
    if (heading && lines.length === 1) {
      const level = heading[1].length;
      out.push(`<h${level}>${fmt(heading[2].trim())}</h${level}>`);
    } else if (lines.every((ln) => /^[-*]\s+/.test(ln))) {
      const items = lines.map((ln) => `<li>${fmt(ln.slice(2).trim())}</li>`).join("");
      out.push(`<ul>${items}</ul>`);
    } else if (lines.every((ln) => /^\d+\.\s+/.test(ln))) {
      // Preserve the author's starting number (Markdown splits blank-line-separated items into
      // separate single-item lists; <ol start="N"> keeps 1, 2, … instead of resetting).
      const start = parseInt(/^(\d+)\./.exec(lines[0])![1], 10);
      const stripped = lines.map((ln) => ln.replace(/^\d+\.\s+/, "").trim());
      const items = stripped.map((s) => `<li>${fmt(s)}</li>`).join("");
      const startAttr = start !== 1 ? ` start="${start}"` : "";
      out.push(`<ol${startAttr}>${items}</ol>`);
    } else {
      const para = fmt(block.trim()).replace(/\n/g, "<br>\n");
      out.push(`<p>${para}</p>`);
    }
  }
  return restore(out.join("\n"), store);
}
