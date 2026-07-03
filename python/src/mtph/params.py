"""Explorable parameters (v0.2).

A problem may declare ``params:`` in front-matter and reference them as ``{{name}}`` inside
figure/plot sources::

    params:
      theta: { min: 0, max: 90, default: 30, unit: "deg" }
    ```figure
    incline angle={{theta}} length=6
    ```

At **render time** each ``{{name}}`` is replaced by a value — the declared *default* for a static
render (so Python/PNG output stays deterministic and the format stays honest), or the live slider
value in an interactive viewer (the playground). The DOM always stores the *template* source plus
the declared defaults, never a baked-in number — nothing is lost.
"""
from __future__ import annotations

import re
from typing import Any, Dict

# ``{{ name }}`` — a parameter reference inside a figure/plot source.
PARAM_REF = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def format_value(v: Any) -> str:
    """Render a substituted value canonically, matching the JS port's ``String(v)`` (an
    integer-valued float loses its ``.0``), so both implementations emit identical sources."""
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, (int, float)):
        return str(int(v)) if float(v) == int(v) else str(v)
    return str(v)


def defaults(meta: Dict[str, Any]) -> Dict[str, Any]:
    """The ``name -> default`` map declared by ``params:`` (empty if none)."""
    params = meta.get("params")
    out: Dict[str, Any] = {}
    if isinstance(params, dict):
        for name, spec in params.items():
            if isinstance(spec, dict) and "default" in spec:
                out[str(name)] = spec["default"]
    return out


def substitute(source: str, values: Dict[str, Any]) -> str:
    """Replace every ``{{name}}`` in ``source`` for which ``name`` is in ``values``. Unknown
    references are left untouched (``verify`` flags them)."""
    if "{{" not in source:
        return source

    def rep(m: "re.Match[str]") -> str:
        name = m.group(1)
        return format_value(values[name]) if name in values else m.group(0)

    return PARAM_REF.sub(rep, source)


def resolve(source: str, meta: Dict[str, Any]) -> str:
    """Substitute a document's declared parameter *defaults* into a figure/plot source."""
    return substitute(source, defaults(meta))
