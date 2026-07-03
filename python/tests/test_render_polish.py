"""Rendering polish (plan 05): dark mode, font subsetting, --cdn, currentColor, raster PNG."""
import pytest

from mtph.diagram.compile_svg import compile_figure
from mtph.parser import parse
from mtph.render.html import _font_drop_set, _inline_css, render_html

HEAD = '---\nmtph: "0.2"\ntitle: T\nsubject: math\n---\n\n'


# -- dark mode ---------------------------------------------------------------
def test_dark_mode_css_present():
    html = render_html(parse(HEAD + "x"), katex="none")
    assert "prefers-color-scheme: dark" in html
    assert "color:var(--ink)" in html  # figures follow the page ink


def test_figures_use_currentcolor_so_they_can_invert():
    svg = compile_figure('vector from=(0,0) to=(1,1) label="v"')
    assert "currentColor" in svg
    assert "#111111" not in svg  # no baked-in black that would vanish in dark mode


def test_label_halo_is_a_separate_underlay_not_paint_order():
    # paint-order is ignored by cairosvg and many SVG tools (it erases the glyphs); the halo
    # must be a separate underlay so labels read in every renderer.
    svg = compile_figure('label text="x" at=(0,0)')
    assert "paint-order" not in svg
    assert svg.count("<text") == 2          # halo underlay + ink overlay
    assert 'class="mtph-lbl"' in svg


# -- font subsetting ---------------------------------------------------------
def test_unused_style_fonts_dropped():
    drop = _font_drop_set(parse(HEAD + "Just $x + y = z$ here."))
    assert drop == frozenset(
        {"KaTeX_Caligraphic", "KaTeX_Fraktur", "KaTeX_SansSerif",
         "KaTeX_Script", "KaTeX_Typewriter"}
    )


def test_used_style_font_is_kept():
    drop = _font_drop_set(parse(HEAD + r"Let $\mathfrak{g}$ act and $\mathtt{code}$."))
    assert "KaTeX_Fraktur" not in drop
    assert "KaTeX_Typewriter" not in drop
    assert "KaTeX_Script" in drop  # still unused


def test_subset_css_omits_dropped_font_faces():
    pytest.importorskip("mtph.tools.fetch_katex")
    from mtph.tools.fetch_katex import is_vendored

    if not is_vendored():
        pytest.skip("KaTeX not vendored in this environment")
    drop = frozenset({"KaTeX_Fraktur"})
    full = _inline_css(frozenset())
    sub = _inline_css(drop)
    assert "@font-face" in full and "KaTeX_Fraktur" in full
    # the Fraktur @font-face (and its embedded woff2) is gone from the subset
    assert "KaTeX_Fraktur-Regular" not in sub
    assert len(sub) < len(full)


def test_subset_default_smaller_than_full_when_unused():
    pytest.importorskip("mtph.tools.fetch_katex")
    from mtph.tools.fetch_katex import is_vendored

    if not is_vendored():
        pytest.skip("KaTeX not vendored in this environment")
    doc = parse(HEAD + "Just $x+y$.")
    full = render_html(doc, katex="inline", subset=False)
    sub = render_html(doc, katex="inline", subset=True)
    assert len(sub.encode()) < len(full.encode())


# -- --cdn -------------------------------------------------------------------
def test_cdn_mode_links_not_inlines():
    html = render_html(parse(HEAD + "$x$"), katex="cdn")
    assert "cdn.jsdelivr.net" in html
    assert "data:font/woff2" not in html  # nothing inlined


# -- raster PNG (cairosvg) ---------------------------------------------------
def test_svg_to_png_or_friendly_error(tmp_path):
    """Either rasterize to a real PNG (cairo present) or raise a friendly RuntimeError —
    never leak a raw ImportError/OSError traceback."""
    from mtph.render.raster import svg_to_png

    svg = compile_figure("circle at=(0,0) r=1")
    out = tmp_path / "fig.png"
    try:
        svg_to_png(svg, out)
    except RuntimeError as e:
        assert "cairosvg" in str(e)
        return
    assert out.exists()
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_document_export_browser_failure_is_friendly(monkeypatch, tmp_path):
    from mtph.render import export

    class Chromium:
        def launch(self):
            raise Exception("raw browser crash")

    class Playwright:
        chromium = Chromium()

    class Manager:
        def __enter__(self):
            return Playwright()

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(export, "_require_playwright", lambda: Manager)
    doc = parse(HEAD + "$x$")
    with pytest.raises(RuntimeError) as exc:
        export.export_document(doc, tmp_path / "out.png", "png")
    assert "PNG/SVG export failed" in str(exc.value)
    assert "playwright install chromium" in str(exc.value)


def test_artifact_mode_uses_only_cdnjs():
    # Claude artifacts allow external scripts ONLY from cdnjs.cloudflare.com (jsdelivr is blocked)
    html = render_html(parse(HEAD + "$x$"), katex="cdnjs")
    assert "cdnjs.cloudflare.com/ajax/libs/KaTeX" in html
    assert "jsdelivr" not in html
    assert "data:font/woff2" not in html  # not inlined — the light path
