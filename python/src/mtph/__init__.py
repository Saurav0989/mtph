"""mtph — an AI-native file format for math & physics problems.

Public API:
    parse(text)        -> Document     parse .mtph source into the DOM
    load(path)         -> Document     read + parse a .mtph file
    validate(doc)      -> list[str]    schema-validate a Document/DOM (empty list == valid)
    render_html(doc)   -> str          render a Document to self-contained HTML
"""
from __future__ import annotations

# Package (pip) release version — bumped on tag/release.
__version__ = "0.1.0"
# Format/spec version, i.e. the `mtph:` front-matter key this build targets. The two are
# intentionally independent (a package can implement a given format spec). 0.1 files still
# validate (validate.py accepts any 0.x for back-compat).
SCHEMA_VERSION = "0.2"

# Convenience re-exports. Kept lazy-free but minimal so importing the package is cheap.
from .model import Document  # noqa: E402
from .parser import parse, load  # noqa: E402
from .validate import validate  # noqa: E402
from .render.html import render_html  # noqa: E402

__all__ = [
    "Document", "parse", "load", "validate", "render_html",
    "__version__", "SCHEMA_VERSION",
]
