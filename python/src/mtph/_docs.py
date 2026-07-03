"""Locate the bundled authoring docs (AGENTS.md, thesis/card.md) at runtime.

They are force-included into the wheel under ``mtph/docs/`` (see ``pyproject.toml``) so
``mtph prompt`` works for installed users, and fall back to the repo checkout in development —
the same strategy ``validate.py`` uses for ``schema.json``.
"""
from __future__ import annotations

from pathlib import Path


def _find(pkg_rel: str, repo_rel: str) -> str:
    candidates = []
    try:  # installed wheel
        from importlib.resources import files

        candidates.append(Path(str(files("mtph").joinpath(pkg_rel))))
    except Exception:  # pragma: no cover - importlib edge cases
        pass
    here = Path(__file__).resolve()
    candidates.append(here.parents[3] / repo_rel)  # repo dev checkout
    candidates.append(Path.cwd() / repo_rel)
    for c in candidates:
        try:
            return c.read_text(encoding="utf-8")
        except (FileNotFoundError, OSError):
            continue
    raise FileNotFoundError(f"could not locate bundled doc {repo_rel!r}")


def agents_md() -> str:
    return _find("docs/AGENTS.md", "AGENTS.md")


def card_md() -> str:
    return _find("docs/card.md", "thesis/card.md")
