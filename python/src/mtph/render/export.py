"""Static PNG/SVG export of a whole document via a headless browser (optional extra).

Requires the ``export`` extra::

    pip install "mtph[export]"
    playwright install chromium

PNG is a full-page raster of the rendered card. SVG wraps the *already-typeset* document
(KaTeX has run in the browser) in an ``<foreignObject>`` with inlined CSS, giving a single
self-contained vector file. Note: ``<foreignObject>`` is rendered by browsers but not by every
SVG tool — use PNG where you need universal raster output.
"""
from __future__ import annotations

from pathlib import Path

from ..model import Document
from .html import _PAGE_CSS, _inline_css, render_html

_WAIT_MS = 600


def _require_playwright():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "PNG/SVG export needs Playwright. Install with:\n"
            '    pip install "mtph[export]"\n'
            "    playwright install chromium"
        ) from e
    return sync_playwright


def export_document(doc: Document, out_path: str | Path, fmt: str, *, scale: int = 2) -> Path:
    fmt = fmt.lower()
    if fmt not in ("png", "svg"):
        raise ValueError(f"unsupported export format {fmt!r} (use 'png' or 'svg')")
    out_path = Path(out_path)
    html = render_html(doc, katex="inline")
    sync_playwright = _require_playwright()

    browser = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(
                viewport={"width": 920, "height": 1200}, device_scale_factor=scale
            )
            page.set_content(html, wait_until="load")
            try:
                page.wait_for_function("document.querySelector('.katex') !== null", timeout=2000)
            except Exception:
                pass
            page.wait_for_timeout(_WAIT_MS)

            if fmt == "png":
                page.locator("main").screenshot(path=str(out_path))
            else:
                out_path.write_text(_to_svg(page), encoding="utf-8")
    except Exception as e:
        raise RuntimeError(
            "PNG/SVG export failed while running headless Chromium. "
            "If Chromium is missing, run `playwright install chromium`; if this is a sandboxed "
            "environment, allow browser launch or render HTML instead."
        ) from e
    finally:
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
    return out_path


def _to_svg(page) -> str:
    box = page.locator("main").bounding_box()
    w, h = box["width"], box["height"]
    xhtml = page.evaluate(
        "() => new XMLSerializer().serializeToString(document.querySelector('main'))"
    )
    css = _PAGE_CSS + _inline_css()
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}" '
        f'viewBox="0 0 {w:.0f} {h:.0f}">\n'
        f'<foreignObject x="0" y="0" width="{w:.0f}" height="{h:.0f}">\n'
        f'<div xmlns="http://www.w3.org/1999/xhtml"><style>{css}</style>{xhtml}</div>\n'
        f"</foreignObject>\n</svg>\n"
    )
