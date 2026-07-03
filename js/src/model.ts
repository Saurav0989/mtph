// The mtph DOM — mirrors python/src/mtph/model.py exactly (same JSON shape).
// Block builders reproduce Python's `to_dom()`, including its conditional fields.

export type BlockDom = { type: string } & Record<string, unknown>;

export interface Dom {
  mtph: string;
  meta: Record<string, unknown>;
  blocks: BlockDom[];
}

export const prose = (text: string): BlockDom => ({ type: "prose", text });

export const math = (latex: string): BlockDom => ({ type: "math", latex });

export const figure = (source: string, caption?: string | null): BlockDom =>
  caption ? { type: "figure", source, caption } : { type: "figure", source };

export const plot = (source: string, caption?: string | null): BlockDom =>
  caption ? { type: "plot", source, caption } : { type: "plot", source };

export const answer = (
  value: string,
  part?: string | null,
  answerType: string = "expression",
): BlockDom => {
  const d: BlockDom = { type: "answer", value };
  if (answerType && answerType !== "expression") d.answer_type = answerType;
  if (part) d.part = part;
  return d;
};

export const solution = (blocks: BlockDom[]): BlockDom => ({ type: "solution", blocks });

export const documentToDom = (
  mtph: string,
  meta: Record<string, unknown>,
  blocks: BlockDom[],
): Dom => ({ mtph, meta, blocks });
