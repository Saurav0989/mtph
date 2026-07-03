// <mtph-doc> — a one-tag embed of a live .mtph problem for any web page, LMS, or blog.
//
//   <script src="mtph-doc.js"></script>
//
//   <mtph-doc>
//     <script type="text/plain">
//     ---
//     mtph: "0.2"
//     title: A block on an incline
//     ---
//     A block of mass $m$ rests on a frictionless incline of angle $\theta$ ...
//     </script>
//   </mtph-doc>
//
// Or point it at a file:  <mtph-doc src="problems/incline.mtph"></mtph-doc>
//
// The problem renders inside a sandboxed iframe fed the exact self-contained page the CLI/artifact
// produces, so its CSS, KaTeX and quiz script are fully isolated from the host page. The iframe
// reports its content height back (postMessage) so it grows to fit with no inner scrollbar. If the
// document declares `params:`, sliders appear above it and it re-renders live on drag — the same
// "explorable" mode as the playground.
//
// Attributes:
//   src="…"        fetch the .mtph source from a URL (else read a <script> child / text content)
//   quiz           render the answer section as a self-check (input + tolerance / choice buttons)
//   hide-answers   drop the answer & solution entirely (a bare problem statement)

import { buildSrcdoc, pickSource, paramSpecs } from "./embed-core.js";

interface ParamSpec { min: number; max: number; default: number; step?: number; unit?: string; label?: string; }

const SHADOW_CSS = `
:host { display:block; margin:1.2rem 0; }
.params { display:flex; flex-wrap:wrap; gap:12px 22px; align-items:center;
  padding:10px 14px; margin-bottom:8px; border:1px solid #e2e2e2; border-radius:10px;
  background:#fafafa; color:#333; font:14px -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; }
.params.hide { display:none; }
.params label { display:flex; align-items:center; gap:8px; }
.params .name { color:#445; }
.params input[type=range] { width:130px; accent-color:#3a6ea5; }
.params .val { font-variant-numeric:tabular-nums; color:#666; min-width:3.2em; }
.frame { width:100%; border:0; display:block; overflow:hidden; }
.err { border:1px solid #e0b4b4; background:#fdf2f2; color:#a2382c; border-radius:10px;
  padding:12px 15px; font:14px ui-monospace,Menlo,Consolas,monospace; white-space:pre-wrap; }
@media (prefers-color-scheme: dark) {
  .params { background:#1d1e22; border-color:#33343a; color:#c3cbe0; }
  .params .name { color:#c3cbe0; }
  .params .val { color:#9a9aa2; }
  .err { background:#2a1c1c; border-color:#5a3232; color:#e8776b; }
}`;

class MtphDoc extends HTMLElement {
  private root: ShadowRoot;
  private frame: HTMLIFrameElement;
  private slidersEl: HTMLDivElement;
  private errEl: HTMLDivElement;
  private values: Record<string, number> = {};
  private paramSig = "";
  private source = "";
  private timer = 0;
  private readonly onMessage = (e: MessageEvent): void => this.handleMessage(e);

  constructor() {
    super();
    this.root = this.attachShadow({ mode: "open" });
    const style = document.createElement("style");
    style.textContent = SHADOW_CSS;
    this.slidersEl = document.createElement("div");
    this.slidersEl.className = "params hide";
    this.errEl = document.createElement("div");
    this.errEl.className = "err";
    this.errEl.style.display = "none";
    this.frame = document.createElement("iframe");
    this.frame.className = "frame";
    this.frame.setAttribute("sandbox", "allow-scripts");
    this.frame.setAttribute("title", "mtph problem");
    this.frame.style.height = "120px"; // provisional; the reporter corrects it after load
    this.root.append(style, this.slidersEl, this.errEl, this.frame);
  }

  static get observedAttributes(): string[] { return ["src", "quiz", "hide-answers"]; }

  connectedCallback(): void {
    window.addEventListener("message", this.onMessage);
    // Children may not be fully parsed yet if this element is upgraded mid-parse; wait for the
    // document to finish before reading a <script>/text-content source.
    if (!this.getAttribute("src") && document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", () => this.load(), { once: true });
    } else {
      this.load();
    }
  }

  disconnectedCallback(): void {
    window.removeEventListener("message", this.onMessage);
  }

  attributeChangedCallback(): void {
    if (this.isConnected) this.load();
  }

  private async load(): Promise<void> {
    const src = this.getAttribute("src");
    let fetched: string | null = null;
    if (src) {
      try {
        const res = await fetch(src);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        fetched = await res.text();
      } catch (e) {
        this.showError(`Could not load ${src}\n${e instanceof Error ? e.message : String(e)}`);
        return;
      }
    }
    const scriptEl = this.querySelector<HTMLScriptElement>(
      'script[type="text/plain"], script[type="application/mtph"], script[type="text/mtph"]',
    );
    const scriptText = scriptEl ? scriptEl.textContent : null;
    const text = scriptEl ? null : this.textContent;
    this.source = pickSource({ fetched, scriptText, text });
    if (!this.source) {
      this.showError("No .mtph source: add a <script type=\"text/plain\"> child or a src= attribute.");
      return;
    }
    this.renderNow();
  }

  private renderNow(): void {
    let result;
    try {
      result = buildSrcdoc(this.source, {
        quiz: this.hasAttribute("quiz"),
        hideAnswers: this.hasAttribute("hide-answers"),
        params: this.values,
      });
    } catch (e) {
      this.showError(e instanceof Error ? e.message : String(e));
      return;
    }
    if (result.warnings.length) {
      // Non-fatal: the renderer still produced output. Surface for authors, don't block readers.
      console.warn(`[mtph-doc] ${result.warnings.length} schema issue(s):\n` + result.warnings.join("\n"));
    }
    this.errEl.style.display = "none";
    this.frame.style.display = "";
    this.frame.srcdoc = result.html;
    this.syncSliders(paramSpecs(result.dom));
  }

  /** Build the slider row when the declared param set changes; keep drag values across edits. */
  private syncSliders(specs: Record<string, ParamSpec>): void {
    const names = Object.keys(specs);
    for (const k of Object.keys(this.values)) if (!(k in specs)) delete this.values[k];
    for (const n of names) if (!(n in this.values)) this.values[n] = specs[n].default;

    this.slidersEl.classList.toggle("hide", names.length === 0);
    const sig = names.map((n) => `${n}:${specs[n].min},${specs[n].max},${specs[n].step ?? ""}`).join("|");
    if (sig === this.paramSig) return; // structure unchanged — keep the live inputs (and focus)
    this.paramSig = sig;

    this.slidersEl.replaceChildren();
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
      input.value = String(this.values[name]);
      const val = document.createElement("span");
      val.className = "val";
      const unit = s.unit ? ` ${s.unit}` : "";
      val.textContent = `${this.values[name]}${unit}`;
      input.addEventListener("input", () => {
        this.values[name] = Number(input.value);
        val.textContent = `${input.value}${unit}`;
        this.schedule();
      });
      label.append(tag, input, val);
      this.slidersEl.append(label);
    }
  }

  private schedule(): void {
    clearTimeout(this.timer);
    this.timer = window.setTimeout(() => this.renderNow(), 90);
  }

  private handleMessage(e: MessageEvent): void {
    if (e.source !== this.frame.contentWindow) return; // only our own iframe
    const d = e.data as { mtph?: string; h?: number } | null;
    if (d && d.mtph === "height" && typeof d.h === "number" && d.h > 0) {
      this.frame.style.height = `${Math.ceil(d.h)}px`;
    }
  }

  private showError(msg: string): void {
    this.frame.style.display = "none";
    this.slidersEl.classList.add("hide");
    this.errEl.textContent = `mtph: ${msg}`;
    this.errEl.style.display = "";
  }
}

if (typeof customElements !== "undefined" && !customElements.get("mtph-doc")) {
  customElements.define("mtph-doc", MtphDoc);
}

export { MtphDoc };
