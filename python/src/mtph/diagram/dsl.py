"""Parse figure-DSL source into a list of :class:`Statement` objects.

Each non-empty, non-comment line is one statement::

    command [positional ...] key=value key=value ...

Values may be coordinates ``(x, y)`` (which contain spaces) or quoted strings, so we use a
small depth-aware tokenizer rather than ``str.split``. Interpretation of values (float vs
anchor vs string vs list) is left to the compiler.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


class DiagramSyntaxError(ValueError):
    """A malformed figure DSL statement, with a 1-based line number."""

    def __init__(self, lineno: int, message: str):
        self.lineno = lineno
        super().__init__(f"figure line {lineno}: {message}")


@dataclass
class Statement:
    command: str
    positionals: List[str] = field(default_factory=list)
    args: Dict[str, str] = field(default_factory=dict)
    lineno: int = 0


def _tokenize(line: str, lineno: int) -> List[str]:
    tokens: List[str] = []
    buf = ""
    depth = 0  # parenthesis depth
    in_quote = False
    for ch in line:
        if in_quote:
            buf += ch
            if ch == '"':
                in_quote = False
            continue
        if ch == '"':
            in_quote = True
            buf += ch
        elif ch == "(":
            depth += 1
            buf += ch
        elif ch == ")":
            depth -= 1
            if depth < 0:
                raise DiagramSyntaxError(lineno, "unbalanced ')'")
            buf += ch
        elif ch.isspace() and depth == 0:
            if buf:
                tokens.append(buf)
                buf = ""
        else:
            buf += ch
    if in_quote:
        raise DiagramSyntaxError(lineno, "unterminated string (missing closing '\"')")
    if depth != 0:
        raise DiagramSyntaxError(lineno, "unbalanced '(' in coordinate")
    if buf:
        tokens.append(buf)
    return tokens


def parse_dsl(source: str) -> List[Statement]:
    statements: List[Statement] = []
    for idx, raw in enumerate(source.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        tokens = _tokenize(line, idx)
        if not tokens:
            continue
        command = tokens[0]
        stmt = Statement(command=command, lineno=idx)
        for tok in tokens[1:]:
            # key=value, but not a coordinate like (1, 2) and not a quoted string
            eq = tok.find("=")
            if eq > 0 and not tok.startswith("(") and not tok.startswith('"'):
                key = tok[:eq]
                val = tok[eq + 1 :]
                stmt.args[key] = val
            else:
                stmt.positionals.append(tok)
        statements.append(stmt)
    return statements
