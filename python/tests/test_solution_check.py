"""Solution step checking (plan 13).

`mtph verify` finally *reads* the equation chain already inside a solution: it splits display
math into rows and top-level `=` chains, and runs plan 12's `equivalent_detail` on each adjacent
pair (and on the final result vs the declared answer). A step that doesn't hold numerically is
`solution.step_mismatch` (error); a step it can't evaluate is tallied `unverifiable`, never a
silent pass (P4). Zero format change — the equations were always there.
"""
from __future__ import annotations

from mtph.verify import verify
from mtph.verify.solution import split_chain, split_rows


# --------------------------------------------------------------------------- splitters
def test_split_rows_on_double_backslash():
    assert split_rows(r"a = b \\ c = d") == ["a = b", "c = d"]


def test_split_rows_respects_aligned_body():
    # `\\` inside \begin{aligned} are row breaks; the env markers are stripped.
    rows = split_rows(r"\begin{aligned} a &= b \\ &= c \end{aligned}")
    assert rows == ["a &= b", "&= c"]


def test_split_rows_ignores_backslash_inside_braces():
    # a `\\` nested in a group (e.g. \substack) is not a top-level row break.
    assert split_rows(r"\substack{a \\ b} = c") == [r"\substack{a \\ b} = c"]


def test_split_chain_top_level_equals():
    assert split_chain("a = b = c") == ["a", "b", "c"]


def test_split_chain_ignores_equals_inside_frac():
    # the `=` lives inside \frac{}{} (brace depth > 0) — not a chain boundary.
    assert split_chain(r"x = \frac{a=b}{c}") == ["x", r"\frac{a=b}{c}"]


def test_split_chain_handles_alignment_marker():
    assert split_chain(r"a &= b") == ["a", "b"]


def test_split_chain_unwraps_boxed():
    assert split_chain(r"\boxed{a = b}") == ["a", "b"]


def test_split_chain_non_equality_rows_return_empty():
    assert split_chain(r"a \approx b") == []          # approximate, not exact
    assert split_chain(r"mg = ma \implies a = g") == []  # an implication is not a checkable equality
    assert split_chain(r"v^2 \le 5gR") == []          # an inequality
    assert split_chain("x + y") == []                 # not an equation at all


# --------------------------------------------------------------------------- the walk
_HEAD = """---
mtph: "0.2"
id: sol-test
title: Solution test
subject: physics
symbols:
  m: {{ dim: mass, test: 2 }}
  v: {{ dim: velocity, test: 3 }}
  E: {{ dim: energy, test: 9 }}
{answer}solution: |
  {sol}
---

A block of mass $m$ moves at speed $v$.
"""


def _verify_solution(sol: str, answer: str = ""):
    text = _HEAD.format(sol=sol, answer=answer)
    rep = verify(text)
    return next(c for c in rep.checks if c.group == "solution")


def test_correct_chain_is_ok_and_counts_pairs():
    c = _verify_solution(r"$$E = \frac{1}{2} m v^2 = \frac{m v^2}{2}$$")
    assert c.status == "ok"
    assert c.extra["steps_checked"] == 2   # one row, three segments → two adjacent pairs


def test_wrong_middle_step_flags_one_mismatch():
    c = _verify_solution(r"$$E = \frac{1}{2} m v^2 = m v^2$$")  # last equality is wrong (missing ½)
    assert c.status == "error"
    mism = [f for f in c.findings if f.id == "solution.step_mismatch"]
    assert len(mism) == 1
    assert mism[0].line is not None


def test_answer_mismatch_when_solution_disagrees_with_answer():
    # the solution derives ½mv² (=9), but the declared answer says mv² (=18) — a real disagreement.
    answer = "answer:\n  type: expression\n  value: 'E = m v^2'\n"
    c = _verify_solution(r"$$E = \frac{1}{2} m v^2 = \frac{m v^2}{2}$$", answer=answer)
    assert c.status == "error"
    assert any(f.id == "solution.answer_mismatch" for f in c.findings)


def test_no_symbols_is_unknown():
    text = """---
mtph: "0.2"
id: s
title: T
subject: physics
solution: |
  $$E = \\frac{1}{2} m v^2 = m v^2$$
---

Body.
"""
    rep = verify(text)
    c = next(cc for cc in rep.checks if cc.group == "solution")
    assert c.status == "unknown"
    assert c.extra["steps_checked"] == 0


def test_unverifiable_step_is_info_not_error():
    # references undeclared `w` → the chain can't be evaluated → info tally, never a false mismatch.
    c = _verify_solution(r"$$E = \frac{1}{2} m w^2 = \frac{m w^2}{2}$$")
    assert c.status in ("info", "unknown")
    assert not any(f.severity == "error" for f in c.findings)


# --------------------------------------------------------------------------- the badge
def test_render_html_badge_present_iff_given():
    from mtph.parser import parse
    from mtph.render.html import render_html

    doc = parse(_HEAD.format(sol=r"$$E = \frac{1}{2} m v^2 = \frac{m v^2}{2}$$", answer=""))
    assert 'class="mtph-verified"' not in render_html(doc, katex="none")
    out = render_html(doc, katex="none", badge="solution checked ✓ — 2 step(s)")
    assert 'class="mtph-verified"' in out and "solution checked ✓" in out


def test_cli_badge_injects_when_verified(tmp_path):
    from typer.testing import CliRunner

    from mtph.cli import app

    src = tmp_path / "p.mtph"
    src.write_text(_HEAD.format(sol=r"$$E = \frac{1}{2} m v^2 = \frac{m v^2}{2}$$", answer=""))
    out = tmp_path / "p.html"
    res = CliRunner().invoke(app, ["render", str(src), "-o", str(out), "--badge"])
    assert res.exit_code == 0
    assert 'class="mtph-verified"' in out.read_text(encoding="utf-8")


def test_cli_badge_skipped_on_error(tmp_path):
    from typer.testing import CliRunner

    from mtph.cli import app

    src = tmp_path / "bad.mtph"  # wrong last step → verify error → no badge, exit 0, stderr note
    src.write_text(_HEAD.format(sol=r"$$E = \frac{1}{2} m v^2 = m v^2$$", answer=""))
    out = tmp_path / "bad.html"
    res = CliRunner().invoke(app, ["render", str(src), "-o", str(out), "--badge"])
    assert res.exit_code == 0
    assert 'class="mtph-verified"' not in out.read_text(encoding="utf-8")
    assert "skipped" in res.output
