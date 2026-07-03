// Tokenize figure-DSL source into statements. A faithful port of python/src/mtph/diagram/dsl.py.

export class DiagramSyntaxError extends Error {
  lineno: number;
  constructor(lineno: number, message: string) {
    super(`figure line ${lineno}: ${message}`);
    this.lineno = lineno;
  }
}

export interface Statement {
  command: string;
  positionals: string[];
  args: Record<string, string>;
  lineno: number;
}

const isSpace = (ch: string): boolean => /\s/.test(ch);

function tokenize(line: string, lineno: number): string[] {
  const tokens: string[] = [];
  let buf = "";
  let depth = 0;
  let inQuote = false;
  for (const ch of line) {
    if (inQuote) {
      buf += ch;
      if (ch === '"') inQuote = false;
      continue;
    }
    if (ch === '"') {
      inQuote = true;
      buf += ch;
    } else if (ch === "(") {
      depth++;
      buf += ch;
    } else if (ch === ")") {
      depth--;
      if (depth < 0) throw new DiagramSyntaxError(lineno, "unbalanced ')'");
      buf += ch;
    } else if (isSpace(ch) && depth === 0) {
      if (buf) {
        tokens.push(buf);
        buf = "";
      }
    } else {
      buf += ch;
    }
  }
  if (inQuote) throw new DiagramSyntaxError(lineno, "unterminated string (missing closing '\"')");
  if (depth !== 0) throw new DiagramSyntaxError(lineno, "unbalanced '(' in coordinate");
  if (buf) tokens.push(buf);
  return tokens;
}

export function parseDsl(source: string): Statement[] {
  const statements: Statement[] = [];
  const lines = source.split("\n");
  for (let idx = 0; idx < lines.length; idx++) {
    const line = lines[idx].trim();
    if (!line || line.startsWith("#")) continue;
    const tokens = tokenize(line, idx + 1);
    if (tokens.length === 0) continue;
    const stmt: Statement = { command: tokens[0], positionals: [], args: {}, lineno: idx + 1 };
    for (const tok of tokens.slice(1)) {
      const eq = tok.indexOf("=");
      if (eq > 0 && !tok.startsWith("(") && !tok.startsWith('"')) {
        stmt.args[tok.slice(0, eq)] = tok.slice(eq + 1);
      } else {
        stmt.positionals.push(tok);
      }
    }
    statements.push(stmt);
  }
  return statements;
}
