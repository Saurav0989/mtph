"""Browserless SVG → PNG rasterization for figure/plot output (optional ``[raster]`` extra).

Figures and plots are already pure SVG, so turning them into PNG needs only a vector
rasterizer — not a 300 MB headless browser. This uses `cairosvg`. Full-*page* PNG (math +
prose laid out by KaTeX's HTML/CSS) still needs the browser path in :mod:`mtph.render.export`,
because faithfully rasterizing arbitrary HTML/CSS requires a browser engine.
"""
from __future__ import annotations

from pathlib import Path


def _require_cairosvg():
    # cairosvg raises ImportError when not installed, and OSError at import time when its
    # native cairo library is missing — surface both as one friendly, actionable message.
    try:
        import cairosvg  # noqa: F401
    except (ImportError, OSError) as e:  # pragma: no cover - exercised via the CLI message
        raise RuntimeError(
            "SVG→PNG needs cairosvg and its native cairo library. Install with:\n"
            '    pip install "mtph[raster]"\n'
            "    # plus the cairo system library, e.g. `brew install cairo` (macOS) or\n"
            "    # `apt-get install libcairo2` (Debian/Ubuntu)\n"
            "(figure/plot PNG only — full-page PNG still uses the [export] browser path)."
        ) from e

    return cairosvg


def svg_to_png(svg: str, out_path: str | Path, *, scale: float = 2.0,
               background: str = "white") -> Path:
    """Rasterize an SVG string to a PNG file at ``scale``× the SVG's pixel size.

    ``background`` defaults to white: figures draw their ink with ``currentColor``, which a
    raster with no CSS context resolves to black, so a white background gives the expected
    black-on-white diagram. Pass ``None`` for a transparent background.
    """
    cairosvg = _require_cairosvg()
    out_path = Path(out_path)
    cairosvg.svg2png(
        bytestring=svg.encode("utf-8"),
        write_to=str(out_path),
        scale=scale,
        background_color=background,
    )
    return out_path
