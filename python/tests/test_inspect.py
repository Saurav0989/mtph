"""Tests for `mtph inspect` — the figure scene-as-data engine (plan 03)."""
import pytest

from mtph.diagram.dsl import DiagramSyntaxError
from mtph.diagram.inspect import inspect_figure, label_overlaps
from mtph.verify import verify

from conftest import example_files

HEAD = '---\nmtph: "0.1"\ntitle: T\nsubject: physics\n---\n'


def test_inspect_reports_extent_and_anchors():
    info = inspect_figure("incline angle=30 length=6\nmass m at=incline.mid size=0.9 label=\"m\"")
    assert set(info["extent"]) == {"minx", "miny", "maxx", "maxy"}
    assert "m" in info["anchors"]
    assert "incline.mid" in info["anchors"]
    # the mass anchor sits inside the reported extent
    e, (mx, my) = info["extent"], info["anchors"]["m"]
    assert e["minx"] <= mx <= e["maxx"]
    assert e["miny"] <= my <= e["maxy"]


def test_inspect_elements_have_bounds_and_geometry():
    info = inspect_figure("vector from=(0,0) to=(3,4) label=\"v\"")
    arrows = [el for el in info["elements"] if el["type"] == "arrow"]
    assert arrows, info["elements"]
    a = arrows[0]
    assert a["length"] == pytest.approx(5.0, abs=0.01)
    assert a["angle_deg"] == pytest.approx(53.13, abs=0.1)
    assert "bounds" in a


def test_inspect_raises_on_bad_anchor():
    with pytest.raises(DiagramSyntaxError):
        inspect_figure("force from=ghost dir=down")


def test_label_overlap_detected():
    info = inspect_figure('label text="forceforce" at=(0,0)\nlabel text="fieldfield" at=(0,0)')
    assert any(d["type"] == "label_overlap" for d in info["diagnostics"])


def test_distant_labels_do_not_overlap():
    info = inspect_figure('label text="a" at=(0,0)\nlabel text="b" at=(5,5)')
    assert info["diagnostics"] == []


def test_label_overlaps_helper_threshold():
    # tiny touch is below the epsilon, big overlap is reported
    assert label_overlaps([("a", (0, 0, 1, 1)), ("b", (0.999, 0.999, 2, 2))]) == []
    assert label_overlaps([("a", (0, 0, 1, 1)), ("b", (0.2, 0.2, 1.2, 1.2))])


def test_verify_surfaces_label_overlap():
    src = HEAD + 'x\n\n```figure\nlabel text="forceforce" at=(0,0)\nlabel text="fieldfield" at=(0,0)\n```\n'
    r = verify(src)
    fig = {c.group: c for c in r.checks}["figure"]
    assert "figure.label_overlap" in [f.id for f in fig.findings]
    assert r.status == "warnings"


def test_grid_overlay_present_only_when_requested():
    from mtph.diagram.compile_svg import compile_figure
    src = "incline angle=30 length=6"
    assert "mtph-grid" not in compile_figure(src)
    gridded = compile_figure(src, grid=True)
    assert "mtph-grid" in gridded
    # the SVG is otherwise unchanged in structure (grid is additive)
    assert gridded.count("<svg") == 1


def test_grid_does_not_change_bbox():
    from mtph.diagram.compile_svg import compile_figure
    import re
    src = "incline angle=30 length=6\nmass m at=incline.mid size=0.9 label=\"m\""
    vb = lambda s: re.search(r'viewBox="([^"]+)"', s).group(1)
    assert vb(compile_figure(src)) == vb(compile_figure(src, grid=True))


@pytest.mark.parametrize("path", example_files(), ids=lambda p: p.stem)
def test_inspect_examples(path):
    from mtph.params import resolve as resolve_params
    from mtph.parser import load
    doc = load(path)
    for b in doc.blocks:
        if b.type == "figure":
            # resolve {{param}} defaults first (as the CLI/renderers do) before compiling
            info = inspect_figure(resolve_params(b.source, doc.meta))
            assert "elements" in info
            # single-panel figures report a top-level extent; multi-panel report per-panel extents
            if "panels" in info:
                assert all("extent" in p for p in info["panels"])
            else:
                assert "extent" in info


# -- multi-panel figures (plan 03B) -------------------------------------------
def test_inspect_multipanel_shape():
    info = inspect_figure("layout row\n# A\ncircle at=(0,0) r=1\n---\n# B\nrect at=(0,0) w=2 h=1")
    assert info["layout"] == "row"
    assert [p["title"] for p in info["panels"]] == ["A", "B"]
    # each panel keeps its own extent/anchors/elements
    assert all("extent" in p and "elements" in p for p in info["panels"])


def test_inspect_multipanel_combines_diagnostics_per_panel():
    info = inspect_figure(
        'layout row\nlabel text="forceforce" at=(0,0)\nlabel text="fieldfield" at=(0,0)'
        "\n---\ncircle at=(0,0) r=1"
    )
    assert any(d["type"] == "label_overlap" for d in info["diagnostics"])


def test_verify_passes_good_multipanel_figure():
    src = HEAD + "x\n\n```figure\nlayout row\nincline angle=20 length=4\n---\nincline angle=40 length=4\n```\n"
    assert verify(src).status == "ok"


def test_verify_flags_bad_command_inside_a_panel():
    src = HEAD + "x\n\n```figure\nlayout row\ncircle at=(0,0) r=1\n---\nboguscmd foo=1\n```\n"
    fig = [c for c in verify(src).checks if c.group == "figure"][0]
    assert "figure.syntax" in [f.id for f in fig.findings]
