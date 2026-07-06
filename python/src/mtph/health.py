"""Environment health for ``mtph doctor`` / ``mtph init``.

One diagnostic that replaces "why doesn't X work": Python + mtph versions, whether KaTeX is
vendored (needed for offline math), and which optional extras are installed — each missing one
paired with the exact command to install it.
"""
from __future__ import annotations

import platform
from typing import Any, Dict

from . import __version__
from .tools.fetch_katex import DEFAULT_VERSION, is_vendored, vendor_dir

# extra name -> (import module, what it unlocks, install command)
_EXTRAS = {
    "export": ("playwright", "full-page PNG/SVG export",
               'pip install "mtph[export]" && playwright install chromium'),
    "raster": ("cairosvg", "browserless figure/plot PNG (mtph figure -o out.png)",
               'pip install "mtph[raster]"  (plus the native cairo lib, e.g. `brew install cairo`)'),
    "app": ("webview", "native desktop reader window (mtph view --app)",
            'pip install "mtph[app]"'),
    "cas": ("sympy", "symbolic equivalence in verify (upgrades unverifiable solution steps)",
            'pip install "mtph[cas]"'),
}


def _probe(module: str) -> bool:
    """True if the module imports. Catches OSError too (e.g. cairosvg with no native cairo)."""
    try:
        __import__(module)
        return True
    except Exception:
        return False


def health_report() -> Dict[str, Any]:
    vendored = is_vendored()
    extras = {
        name: {
            "installed": _probe(mod),
            "module": mod,
            "feature": feature,
            "install": install,
        }
        for name, (mod, feature, install) in _EXTRAS.items()
    }
    return {
        "python": platform.python_version(),
        "mtph": __version__,
        "katex": {
            "vendored": vendored,
            "version": DEFAULT_VERSION if vendored else None,
            "dir": str(vendor_dir()),
        },
        "extras": extras,
        "ok": vendored,  # the core needs vendored KaTeX to render math offline
    }
