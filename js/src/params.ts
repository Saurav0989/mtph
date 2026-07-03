// Explorable parameters — the JS side of python/src/mtph/params.py. A figure/plot source may
// reference declared params as `{{name}}`; renderers substitute the default (deterministic), or
// a live value from the playground's sliders. Kept byte-identical to the Python substitution so
// the HTML conformance holds.

export const PARAM_REF = /\{\{\s*(\w+)\s*\}\}/g;

type ParamValues = Record<string, number | string>;

/** The `name -> default` map declared by `params:` in meta (empty if none). */
export function paramDefaults(meta: Record<string, unknown>): ParamValues {
  const out: ParamValues = {};
  const params = meta.params;
  if (params && typeof params === "object") {
    for (const [name, spec] of Object.entries(params as Record<string, unknown>)) {
      if (spec && typeof spec === "object" && "default" in spec) {
        out[name] = (spec as { default: number | string }).default;
      }
    }
  }
  return out;
}

/** Replace each `{{name}}` for which `name` is in `values`; leave unknown references. */
export function substituteParams(source: string, values: ParamValues): string {
  if (!source.includes("{{")) return source;
  return source.replace(PARAM_REF, (m, name) => (name in values ? String(values[name]) : m));
}

/** Substitute a document's declared parameter *defaults* into a figure/plot source. */
export function resolveParams(source: string, meta: Record<string, unknown>): string {
  return substituteParams(source, paramDefaults(meta));
}
