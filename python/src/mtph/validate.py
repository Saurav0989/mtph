"""Validate an mtph DOM against the canonical ``schema.json``.

``schema.json`` (under ``spec/``) is the source of truth shared with any future
implementation. We locate it as packaged data when installed, falling back to the repo
checkout during development.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Union

from jsonschema import Draft202012Validator

from .model import Document

SUPPORTED_MAJOR = 0


@lru_cache(maxsize=1)
def _load_schema() -> Dict[str, Any]:
    candidates: List[Path] = []
    try:  # installed wheel: spec/schema.json is force-included as package data
        from importlib.resources import files

        candidates.append(Path(str(files("mtph").joinpath("spec/schema.json"))))
    except Exception:  # pragma: no cover - importlib edge cases
        pass
    here = Path(__file__).resolve()
    candidates.append(here.parents[3] / "spec" / "schema.json")  # repo dev checkout
    candidates.append(Path.cwd() / "spec" / "schema.json")
    for c in candidates:
        try:
            return json.loads(c.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError):
            continue
    raise FileNotFoundError(
        "could not locate mtph schema.json (looked in package data and ./spec/)"
    )


def validate(doc: Union[Document, Dict[str, Any]]) -> List[str]:
    """Return a list of human-readable validation errors (empty list == valid)."""
    dom = doc.to_dom() if isinstance(doc, Document) else doc
    errors: List[str] = []

    version = str(dom.get("mtph", ""))
    try:
        major = int(version.split(".")[0])
    except (ValueError, IndexError):
        major = None
    if major != SUPPORTED_MAJOR:
        errors.append(
            f"unsupported mtph version {version!r}: this build supports {SUPPORTED_MAJOR}.x"
        )

    validator = Draft202012Validator(_load_schema())
    for e in sorted(validator.iter_errors(dom), key=lambda err: list(err.path)):
        loc = "/".join(str(p) for p in e.path) or "<root>"
        errors.append(f"{loc}: {e.message}")
    return errors
