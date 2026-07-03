// The mtph playground: a zero-server editor + live renderer. Everything runs in the browser via
// the JS port (parse → validate → renderHtml). The document is stored in the URL fragment
// (lz-string compressed), so every shared link carries its own source — no backend, no database.
import { compressToEncodedURIComponent, decompressFromEncodedURIComponent } from "lz-string";
import { parse, validate, renderHtml } from "../src/index.js";
import { EXAMPLES } from "./examples.js";

const $ = <T extends HTMLElement>(id: string): T => document.getElementById(id) as T;

const editor = $<HTMLTextAreaElement>("editor");
const preview = $<HTMLIFrameElement>("preview");
const badge = $<HTMLSpanElement>("badge");
const problems = $<HTMLDivElement>("problems");
const toggleProblems = $<HTMLButtonElement>("toggle-problems");
const shareBtn = $<HTMLButtonElement>("share");
const downloadBtn = $<HTMLButtonElement>("download");
const examplesSel = $<HTMLSelectElement>("examples");
const slidersEl = $<HTMLDivElement>("sliders");
const quizBtn = $<HTMLButtonElement>("quiz");
const seed = ($("seed") as HTMLScriptElement).textContent ?? "";

let lastId = "problem";
let quizMode = false;

// Live parameter values (explorable `params:`), keyed by name. Persist across edits/drags.
interface ParamSpec { min: number; max: number; default: number; step?: number; unit?: string; label?: string; }
let paramSig = "";
const paramValues: Record<string, number> = {};

function setBadge(kind: "ok" | "warn" | "err", text: string): void {
  badge.className = `badge ${kind}`;
  badge.textContent = text;
}

function showProblems(lines: { text: string; warn?: boolean }[]): void {
  if (lines.length === 0) {
    problems.classList.remove("show");
    problems.innerHTML = "";
    toggleProblems.style.display = "none";
    return;
  }
  toggleProblems.style.display = "";
  problems.innerHTML = lines
    .map((l) => `<div class="row${l.warn ? " warn" : ""}">${escapeHtml(l.text)}</div>`)
    .join("");
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function paramSpecs(meta: Record<string, unknown>): Record<string, ParamSpec> {
  const p = meta.params;
  return p && typeof p === "object" ? (p as Record<string, ParamSpec>) : {};
}

/** Build the slider row when the declared param set changes; keep drag values across edits. */
function syncSliders(specs: Record<string, ParamSpec>): void {
  const names = Object.keys(specs);
  const sig = names.map((n) => `${n}:${specs[n].min},${specs[n].max},${specs[n].step ?? ""}`).join("|");
  // prune values for params that vanished; seed new ones from their default
  for (const k of Object.keys(paramValues)) if (!(k in specs)) delete paramValues[k];
  for (const n of names) if (!(n in paramValues)) paramValues[n] = specs[n].default;

  slidersEl.classList.toggle("show", names.length > 0);
  if (sig === paramSig) return; // structure unchanged — keep the live inputs (and focus)
  paramSig = sig;

  slidersEl.replaceChildren();
  for (const name of names) {
    const s = specs[name];
    const label = document.createElement("label");
    const tag = document.createElement("span");
    tag.className = "name";
    tag.textContent = s.label || name;
    const input = document.createElement("input");
    input.type = "range";
    input.min = String(s.min);
    input.max = String(s.max);
    input.step = String(s.step ?? "any");
    input.value = String(paramValues[name]);
    const val = document.createElement("span");
    val.className = "val";
    const unit = s.unit ? ` ${s.unit}` : "";
    val.textContent = `${paramValues[name]}${unit}`;
    input.addEventListener("input", () => {
      paramValues[name] = Number(input.value);
      val.textContent = `${input.value}${unit}`;
      scheduleRender(70);
    });
    label.append(tag, input, val);
    slidersEl.append(label);
  }
}

function render(): void {
  const src = editor.value;
  // Persist to the URL fragment silently (no history spam, no hashchange).
  const encoded = compressToEncodedURIComponent(src);
  history.replaceState(null, "", `#${encoded}`);

  let dom;
  try {
    dom = parse(src);
  } catch (e) {
    setBadge("err", "syntax error");
    showProblems([{ text: e instanceof Error ? e.message : String(e) }]);
    slidersEl.classList.remove("show");
    return; // keep the last good preview on screen
  }

  lastId = typeof dom.meta.id === "string" && dom.meta.id ? dom.meta.id : "problem";
  const specs = paramSpecs(dom.meta);
  syncSliders(specs);
  // Override each param's default with the live slider value; renderHtml substitutes `default`.
  for (const [name, v] of Object.entries(paramValues)) {
    if (specs[name]) specs[name].default = v;
  }

  const errors = validate(dom);
  if (errors.length) {
    setBadge("warn", `${errors.length} schema issue${errors.length > 1 ? "s" : ""}`);
    showProblems(errors.map((text) => ({ text, warn: true })));
  } else {
    setBadge("ok", "ok");
    showProblems([]);
  }

  try {
    preview.srcdoc = renderHtml(dom, { quiz: quizMode });
  } catch (e) {
    setBadge("err", "render error");
    showProblems([{ text: e instanceof Error ? e.message : String(e) }]);
  }
}

let timer = 0;
function scheduleRender(delay = 250): void {
  clearTimeout(timer);
  timer = window.setTimeout(render, delay);
}

function load(source: string): void {
  editor.value = source;
  render();
}

// -- wiring -------------------------------------------------------------------
editor.addEventListener("input", () => scheduleRender());

// Tab inserts two spaces instead of leaving the textarea.
editor.addEventListener("keydown", (e) => {
  if (e.key === "Tab") {
    e.preventDefault();
    const s = editor.selectionStart, end = editor.selectionEnd;
    editor.value = editor.value.slice(0, s) + "  " + editor.value.slice(end);
    editor.selectionStart = editor.selectionEnd = s + 2;
    scheduleRender();
  }
});

toggleProblems.addEventListener("click", () => problems.classList.toggle("show"));

quizBtn.addEventListener("click", () => {
  quizMode = !quizMode;
  quizBtn.setAttribute("aria-pressed", String(quizMode));
  render();
});

shareBtn.addEventListener("click", async () => {
  const url = `${location.origin}${location.pathname}#${compressToEncodedURIComponent(editor.value)}`;
  history.replaceState(null, "", url);
  try {
    await navigator.clipboard.writeText(url);
    const prev = shareBtn.textContent;
    shareBtn.textContent = "Copied ✓";
    setTimeout(() => (shareBtn.textContent = prev), 1400);
  } catch {
    prompt("Copy this share link:", url);
  }
});

downloadBtn.addEventListener("click", () => {
  let html: string;
  try {
    const dom = parse(editor.value);
    const specs = paramSpecs(dom.meta); // bake the current slider values into the download
    for (const [name, v] of Object.entries(paramValues)) if (specs[name]) specs[name].default = v;
    html = renderHtml(dom, { quiz: quizMode });
  } catch {
    return; // nothing to download while the source is broken
  }
  const blob = new Blob([html], { type: "text/html" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${lastId}.html`;
  a.click();
  URL.revokeObjectURL(a.href);
});

for (const ex of EXAMPLES) {
  const opt = document.createElement("option");
  opt.value = ex.id;
  opt.textContent = ex.label;
  examplesSel.append(opt);
}
examplesSel.addEventListener("change", () => {
  const ex = EXAMPLES.find((e) => e.id === examplesSel.value);
  if (ex) load(ex.source);
  examplesSel.value = "";
});

// -- boot ---------------------------------------------------------------------
const hash = location.hash.slice(1);
let initial = seed.trim() + "\n";
if (hash) {
  const decoded = decompressFromEncodedURIComponent(hash);
  if (decoded) initial = decoded;
}
load(initial);
