"""Tests for the graduated verification engine (plan 02).

One positive + negative per check id, plus the status rollup, exit codes, and JSON shape.
"""
import pytest

from mtph.verify import verify
from mtph.verify.model import CheckResult, Finding, Report

from conftest import example_files

HEAD = '---\nmtph: "0.1"\ntitle: T\nsubject: physics\n---\n'


def _ids(report, group):
    checks = {c.group: c for c in report.checks}
    return [f.id for f in checks[group].findings]


def _status(report, group):
    return {c.group: c.status for c in report.checks}[group]


# --------------------------------------------------------------------------- top-level
def test_clean_document_is_ok():
    r = verify(HEAD + "A mass $v_0$ moves.\n\n$$\\frac{a}{b}$$\n")
    assert r.status == "ok"
    assert r.exit_code == 0


def test_content_and_notation_are_unknown_not_ok():
    # never falsely report ok for things only a human can judge (principle P4)
    r = verify(HEAD + "body\n")
    assert _status(r, "content") == "unknown"
    assert _status(r, "notation") == "unknown"


def test_parse_error_short_circuits():
    r = verify("no front matter here")
    assert r.status == "error"
    assert _ids(r, "parse") == ["parse.error"]


# --------------------------------------------------------------------------- latex.backslash
def test_backslash_doubled_command_flagged():
    r = verify(HEAD + "x\n\n```math\n\\\\frac{a}{b}\n```\n")
    assert "latex.backslash" in _ids(r, "latex")
    assert r.status == "error"


def test_backslash_single_command_clean():
    r = verify(HEAD + "x\n\n```math\n\\frac{a}{b}\n```\n")
    assert _ids(r, "latex") == []


def test_backslash_rowbreak_in_environment_not_flagged():
    # legitimate matrix/cases row break must NOT be mistaken for the escaping bug
    r = verify(HEAD + "x\n\n$$\\begin{cases} a \\\\ b \\end{cases}$$\n")
    assert _ids(r, "latex") == []


def test_backslash_flagged_in_answer_value():
    src = ('---\nmtph: "0.1"\ntitle: T\nsubject: physics\n'
           "answer:\n  type: expression\n  value: '\\\\frac{1}{2}'\n---\nbody\n")
    r = verify(src)
    assert "latex.backslash" in _ids(r, "latex")


# --------------------------------------------------------------------------- figure
def test_figure_undefined_anchor():
    r = verify(HEAD + "x\n\n```figure\nforce from=ghost dir=down\n```\n")
    assert "figure.undefined_anchor" in _ids(r, "figure")
    assert r.exit_code == 1


def test_figure_valid_clean():
    r = verify(HEAD + "x\n\n```figure\nincline angle=30 length=6\n```\n")
    assert _ids(r, "figure") == []


# --------------------------------------------------------------------------- plot
def test_plot_domain_gap_is_warning():
    r = verify(HEAD + "x\n\n```plot\nx: 0..2\nf(x) = 1/(x-1)\n```\n")
    assert "plot.domain" in _ids(r, "plot")
    assert r.status == "warnings"  # a gap is a warning, not an error
    assert r.exit_code == 0


def test_plot_empty_is_error():
    r = verify(HEAD + "x\n\n```plot\nx: 0..2\nf(x) = sqrt(-1-x^2)\n```\n")
    assert "plot.empty" in _ids(r, "plot")
    assert r.exit_code == 1


def test_plot_clean():
    r = verify(HEAD + "x\n\n```plot\nx: -3..3\nf(x) = x^2\n```\n")
    assert _ids(r, "plot") == []


# --------------------------------------------------------------------------- prose
def test_bare_subscript_warned():
    r = verify(HEAD + "The speed v_0 is constant.\n")
    assert "prose.bare_subscript" in _ids(r, "prose")


def test_subscript_in_math_not_warned():
    r = verify(HEAD + "The speed $v_0$ is constant.\n")
    assert _ids(r, "prose") == []


def test_snake_case_not_warned():
    r = verify(HEAD + "the data_set variable\n")
    assert _ids(r, "prose") == []


# --------------------------------------------------------------------------- filtering / shape
def test_checks_filter():
    r = verify(HEAD + "v_0 here\n", checks=["schema"])
    groups = {c.group for c in r.checks}
    assert groups == {"schema"}


def test_report_json_shape():
    r = verify(HEAD + "x\n\n```math\n\\\\vec{B}\n```\n", path="p.mtph")
    d = r.to_dict()
    assert d["status"] == "error"
    assert d["file"] == "p.mtph"
    assert d["mtph_version"] == "0.1"
    assert d["checks"]["latex"]["findings"][0]["id"] == "latex.backslash"
    assert "fix" in d["checks"]["latex"]["findings"][0]


def test_rollup_logic():
    rep = Report(file=None, mtph_version="0.1", checks=[
        CheckResult("a", [Finding("x", "warning", "w")]),
        CheckResult("b", [Finding("y", "error", "e")]),
    ])
    assert rep.status == "error"
    rep.checks = [CheckResult("a", [Finding("x", "warning", "w")])]
    assert rep.status == "warnings"
    rep.checks = [CheckResult("a", declared="unknown")]
    assert rep.status == "ok"  # unknown never fails the run


@pytest.mark.parametrize("path", example_files(), ids=lambda p: p.stem)
def test_examples_verify_without_errors(path):
    r = verify(path.read_text(encoding="utf-8"), path=str(path))
    assert r.status in ("ok", "warnings"), [
        f.to_dict() for c in r.checks for f in c.findings if f.severity == "error"
    ]


# -- figure.label_unsupported (label renderer is Unicode, not KaTeX) ----------
def _figure_ids(src):
    rep = verify(HEAD + "\nx\n\n```figure\n" + src + "\n```\n")
    return [f.id for f in next(c for c in rep.checks if c.group == "figure").findings]


def test_label_unsupported_flags_argument_commands():
    assert "figure.label_unsupported" in _figure_ids('point P at=(0,0) label="\\frac{a}{b}"')
    assert "figure.label_unsupported" in _figure_ids('point P at=(0,0) label="\\mathbf{F}"')


def test_label_supported_greek_and_accents_clean():
    ids = _figure_ids('vector from=(0,0) to=(1,1) label="\\vec{v}_0"\nlabel text="\\theta" at=(0.5,0.5)')
    assert "figure.label_unsupported" not in ids


def test_label_unsupported_in_angle_value():
    assert "figure.label_unsupported" in _figure_ids('angle at=(0,0) from=0 to=45 value="\\frac{\\pi}{4}"')
