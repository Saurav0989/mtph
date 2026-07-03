import pytest

from mtph.diagram.compile_svg import compile_figure
from mtph.diagram.dsl import DiagramSyntaxError, parse_dsl
from mtph.mathr.latex import label_runs, latex_to_unicode


def test_tokenizer_keeps_coords_and_strings_together():
    stmts = parse_dsl('mass m at=(1, 2) label="a b"')
    s = stmts[0]
    assert s.command == "mass"
    assert s.positionals == ["m"]
    assert s.args["at"] == "(1, 2)"
    assert s.args["label"] == '"a b"'


def test_incline_compiles_to_svg():
    svg = compile_figure(
        "incline angle=30 length=6\n"
        "mass m at=incline.mid size=0.9 label=\"m\"\n"
        "force from=m dir=perp-out label=\"N\""
    )
    assert svg.startswith("<svg")
    assert "viewBox" in svg
    assert "polygon" in svg  # incline triangle + block


def test_wall_and_dim_compile():
    svg = compile_figure(
        "wall at=(0,0) height=2 side=left\n"
        'dim from=(0,0) to=(3,0) off=-0.5 label="L"'
    )
    assert svg.startswith("<svg")
    assert "<line" in svg
    assert "L" in svg  # the dimension label


V2_COMMANDS = [
    'path d="M(0,0) C(1,1)(2,1)(3,0) Z" fill=gray arrow=false',
    'path d="M(0,0) Q(1,2)(3,0)" arrow=true',
    'charge at=(0,0) sign=+ label="q"',
    'charge at=(0,0) sign=-',
    "dipole at=(0,0) sep=1 angle=20 moment=true",
    "bfield at=(0,0) width=2 height=2 dir=in n=3",
    "bfield at=(0,0) width=2 height=2 dir=out n=3",
    "fieldline from=(0,0) to=(2,0) bend=0.3",
    "vectorfield at=(0,0) width=2 height=2 dir=out n=4",
    "equipotential at=(0,0) r=1",
    'gaussian at=(0,0) r=1 label="S"',
    'pendulum at=(0,3) length=2 angle=20 label="m" value="\\theta"',
    'rod from=(0,0) to=(2,1) label="L"',
    'pivot at=(0,0) label="O"',
    "axes3d at=(0,0) size=2",
    'sphere at=(0,0) r=1 label="R"',
    "omega at=(0,0) r=0.6 dir=ccw",
    'container at=(0,0) width=2 height=2 fill=lightgray level=1',
    'piston at=(0,1) width=1.8 label="F"',
    "gas at=(0,0) width=2 height=2 n=8",
    "heat at=(0,0) width=2 n=3",
    "flame at=(0,0) size=0.6",
    "wavefront at=(0,0) n=3 r0=0.4 dr=0.4",
    "wavefront at=(0,0) n=3 from=-40 to=40",
    'current from=(0,0) to=(3,0) label="I"',
    "current from=(0,0) to=(3,0)",
    "spiral at=(0,0) r0=0.1 dr=0.3 turns=3",
    'coil at=(0,0) dr=0.2 turns=2 label="L"',
    "rect at=(0,0) w=2 h=1 fill=hatch",
    "circle at=(0,0) r=1 fill=crosshatch",
    "polygon points=(0,0);(2,0);(1,2) fill=dots",
]


def test_current_defaults_label_to_I():
    svg = compile_figure("current from=(0,0) to=(3,0)")
    assert "polygon" in svg  # arrowhead present
    assert ">I<" in svg or "I</text>" in svg


def test_hatch_emits_pattern_def_only_when_used():
    assert "mtph-hatch" in compile_figure("rect at=(0,0) w=2 h=1 fill=hatch")
    assert "mtph-hatch" not in compile_figure("rect at=(0,0) w=2 h=1 fill=gray")


def test_spiral_grows_outward():
    # last point should be farther from centre than the first (radius increases)
    from mtph.diagram.inspect import inspect_figure
    info = inspect_figure("spiral at=(0,0) r0=0.0 dr=0.5 turns=2")
    path = [e for e in info["elements"] if e["type"] == "path"][0]
    assert path["points"] > 10  # sampled into many points


@pytest.mark.parametrize("src", V2_COMMANDS, ids=lambda s: s.split()[0])
def test_v2_commands_compile(src):
    svg = compile_figure(src)
    assert svg.startswith("<svg") and "</svg>" in svg


def test_path_has_bezier():
    svg = compile_figure('path d="M(0,0) C(1,1)(2,1)(3,0)"')
    assert "<path" in svg and "C " in svg


def test_path_bad_token_raises():
    with pytest.raises(DiagramSyntaxError):
        compile_figure('path d="M(0,0) X(1,1)"')


def test_unknown_command_raises():
    with pytest.raises(DiagramSyntaxError):
        compile_figure("frobnicate x=1")


def test_unknown_anchor_raises():
    with pytest.raises(DiagramSyntaxError):
        compile_figure("force from=ghost dir=down")


def test_label_runs_subscript():
    assert label_runs("R_1") == [("R", "n"), ("1", "sub")]


def test_label_runs_superscript_group():
    assert label_runs("x^{-1}") == [("x", "n"), ("-1", "sup")]


def test_latex_to_unicode_greek():
    assert latex_to_unicode(r"\theta") == "θ"
    assert latex_to_unicode(r"\omega_0").startswith("ω")


def test_latex_to_unicode_common_accents():
    assert latex_to_unicode(r"\bar q_x").startswith("q̄")
    assert label_runs(r"\bar q_x") == [("q̄", "n"), ("x", "sub")]
    assert label_runs(r"\bar{q}_\parallel") == [("q̄", "n"), ("∥", "sub")]


# -- multi-panel figures (plan 03B) -------------------------------------------
from mtph.diagram.compile_svg import _panelize  # noqa: E402


def test_single_panel_is_not_panelized():
    # no layout directive and no --- separator → ordinary single-panel figure
    assert _panelize("mass m at=(0,0)\n# a comment\ncircle at=(0,0) r=1") is None


def test_panelize_reads_layout_and_titles():
    layout, cols, panels = _panelize(
        "layout grid cols=2\n# A\ncircle at=(0,0) r=1\n---\n# B\nrect at=(0,0) w=1 h=1"
    )
    assert layout == "grid" and cols == 2
    assert [t for t, _ in panels] == ["A", "B"]


def test_bare_separator_defaults_to_row():
    layout, cols, panels = _panelize("circle at=(0,0) r=1\n---\nrect at=(0,0) w=1 h=1")
    assert layout == "row" and cols is None and len(panels) == 2


@pytest.mark.parametrize("layout", ["row", "column", "horizontal", "vertical", "grid cols=2"])
def test_multipanel_renders_nested_svgs(layout):
    src = f"layout {layout}\ncircle at=(0,0) r=1\n---\nrect at=(0,0) w=2 h=1"
    svg = compile_figure(src)
    assert svg.count("<svg") == 3            # one outer + two inner panel viewports
    assert svg.strip().endswith("</svg>")


def test_multipanel_titles_appear_in_output():
    svg = compile_figure("layout row\n# Before\ncircle at=(0,0) r=1\n---\n# After\nrect at=(0,0) w=1 h=1")
    assert "Before" in svg and "After" in svg


def test_layout_directive_must_be_first_meaningful_line():
    # a stray `layout` further down is just an unknown command (not a layout directive)
    with pytest.raises(DiagramSyntaxError):
        compile_figure("circle at=(0,0) r=1\nlayout row")


# -- zigzag helper + label nudge (plan 03) ------------------------------------
from mtph.diagram.compile_svg import Compiler  # noqa: E402
from mtph.diagram.inspect import label_overlaps  # noqa: E402
from mtph.diagram.shapes import Text, prim_bbox  # noqa: E402


def test_zigzag_renders():
    svg = compile_figure('zigzag from=(0,0) to=(5,0) periods=8 amplitude=0.3 label="cut"')
    assert "points=" in svg and "cut" in svg


def _overlaps(scene):
    labs = [(p.raw, prim_bbox(p)) for p in scene.prims if isinstance(p, Text)]
    return label_overlaps(labs)


def test_nudge_separates_coincident_labels():
    c = Compiler()
    c.execute('label text="forceforce" at=(0,0)\nlabel text="fieldfield" at=(0,0)')
    assert len(_overlaps(c.scene)) == 1
    c.scene.nudge_labels()
    assert _overlaps(c.scene) == []


def test_nudge_flag_changes_output_but_not_source():
    src = 'label text="aaaa" at=(0,0)\nlabel text="bbbb" at=(0,0)'
    plain = compile_figure(src)
    nudged = compile_figure(src, nudge=True)
    assert plain != nudged  # labels moved in the rendered output
    assert compile_figure(src) == plain  # source-derived render is unchanged (no mutation)


# -- regression: bugs found while authoring the example bank -------------------
def test_dash_alias_accepted():
    # `dash=` is accepted alongside canonical `style=` (was silently ignored)
    svg = compile_figure("circle at=(0,0) r=1 dash=dashed\nline from=(0,1) to=(0,-1) style=dotted")
    assert 'stroke-dasharray="7 5"' in svg and 'stroke-dasharray="1.5 4"' in svg


def test_labels_use_dy_not_percentage_fontsize():
    # sub/superscripts must not use font-size="72%"/baseline-shift (cairosvg mis-renders them)
    svg = compile_figure('label text="v_0" at=(0,0)')
    assert "72%" not in svg and "baseline-shift" not in svg
    assert 'dy=' in svg and 'font-size="' in svg


def test_charge_label_does_not_self_overlap():
    from mtph.diagram.inspect import inspect_figure
    for sign, lbl in (("+", "+q"), ("-", "-q")):
        info = inspect_figure(f'charge at=(0,0) sign={sign} label="{lbl}"')
        assert info["diagnostics"] == [], (sign, lbl)


# -- micro-animation (W5) -----------------------------------------------------
def test_spin_wraps_group_with_rotate():
    svg = compile_figure("circle at=(0,0) r=1 anim=spin anim-period=2")
    assert "<g>" in svg and "</g>" in svg
    assert 'type="rotate"' in svg and 'to="-360' in svg  # ccw default
    assert 'dur="2s"' in svg and 'repeatCount="indefinite"' in svg


def test_spin_clockwise():
    svg = compile_figure("rect at=(0,0) w=1 h=1 anim=spin anim-cw=true")
    assert 'to="360 ' in svg


def test_spin_swing_is_rotational_oscillation():
    svg = compile_figure("pendulum at=(0,3) length=2 angle=20 anim=spin anim-about=(0,3) anim-swing=40")
    assert 'type="rotate"' in svg and 'values="0 ' in svg
    assert 'keySplines=' in svg and 'calcMode="spline"' in svg
    assert "-20 " in svg and "20 " in svg  # ±swing/2


def test_oscillate_translate_has_no_signed_zero():
    svg = compile_figure('mass m at=(0,0) size=0.5 anim=oscillate anim-amp=1 anim-dir=0')
    assert 'type="translate"' in svg
    assert "-0.00" not in svg  # signed-zero normalised for JS parity


def test_along_emits_animatemotion():
    svg = compile_figure('circle at=(0,0) r=0.2 anim=along anim-path="(0,0);(2,1)" anim-period=3')
    assert "<animateMotion" in svg and 'path="M 0 0 L' in svg


def test_unknown_anim_kind_raises():
    with pytest.raises(DiagramSyntaxError):
        compile_figure("circle at=(0,0) r=1 anim=wobble")


def test_along_needs_two_points():
    with pytest.raises(DiagramSyntaxError):
        compile_figure('circle at=(0,0) r=1 anim=along anim-path="(0,0)"')


def test_bad_anim_period_raises():
    with pytest.raises(DiagramSyntaxError):
        compile_figure("circle at=(0,0) r=1 anim=spin anim-period=0")


def test_anim_expands_viewbox_so_motion_is_not_clipped():
    # an oscillation reaches beyond the drawn circle → the viewBox must grow to fit it
    plain = compile_figure("circle at=(0,0) r=0.5")
    moving = compile_figure("circle at=(0,0) r=0.5 anim=oscillate anim-amp=2 anim-dir=0")
    import re
    wp = float(re.search(r'width="(\d+)"', plain).group(1))
    wm = float(re.search(r'width="(\d+)"', moving).group(1))
    assert wm > wp


def test_anim_on_empty_command_is_ignored():
    # `point ... dot=false` with no label draws nothing; an anim on it must be a no-op, not a crash
    svg = compile_figure("point P at=(0,0) dot=false anim=spin")
    assert "animateTransform" not in svg
