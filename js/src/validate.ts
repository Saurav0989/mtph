// Schema validation against the *same* spec/schema.json the Python impl uses (Draft 2020-12).
import Ajv2020 from "ajv/dist/2020.js";
import schema from "../../spec/schema.json";

const ajv = new Ajv2020({ allErrors: true, strict: false });
const validateFn = ajv.compile(schema as object);

/** Return human-readable validation errors (empty array == valid), mirroring Python `validate`. */
export function validate(dom: unknown): string[] {
  if (validateFn(dom)) return [];
  return (validateFn.errors ?? []).map(
    (e) => `${e.instancePath || "<root>"}: ${e.message ?? "invalid"}`,
  );
}
