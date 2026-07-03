"""`mtph audit` — verify + advisory structural nudges (plan 02/07)."""
from mtph.audit import CHECKLIST, advisories
from mtph.parser import parse

HEAD = '---\nmtph: "0.2"\ntitle: T\nsubject: physics\n{extra}---\n\n'

COMPLETE = HEAD.format(extra="difficulty: 4\n") + (
    "A statement with $x$.\n\n"
    "```figure\ncircle at=(0,0) r=1\n```\n\n"
    "```answer\nx=1\n```\n\n"
    "````solution\nBecause.\n````\n"
)


def test_complete_problem_has_no_advisories():
    assert advisories(parse(COMPLETE)) == []


def test_bare_problem_flags_structure():
    ids = [a.id for a in advisories(parse(HEAD.format(extra="") + "Just $x$."))]
    assert set(ids) == {"audit.no_figure", "audit.no_answer", "audit.no_solution",
                        "audit.no_difficulty"}


def test_advisories_are_info_only():
    for a in advisories(parse(HEAD.format(extra="") + "x")):
        assert a.severity == "info"  # never an error — audit can't fail a build


def test_no_figure_only_for_physics():
    math_doc = '---\nmtph: "0.2"\ntitle: T\nsubject: math\ndifficulty: 2\n---\n\n$x$\n\n```answer\n1\n```\n\n````solution\ns\n````\n'
    ids = [a.id for a in advisories(parse(math_doc))]
    assert "audit.no_figure" not in ids  # math problems needn't have a figure


def test_checklist_is_present():
    assert len(CHECKLIST) >= 5
    assert any("insight" in c.lower() for c in CHECKLIST)


# -- mentor mode (holistic, difficulty-aware) ---------------------------------
from mtph.audit import mentor  # noqa: E402


def test_mentor_flags_overclaimed_difficulty():
    doc = parse(HEAD.format(extra="difficulty: 5\n") + "Compute the thing. No support here.")
    notes = mentor(doc)
    assert any("difficulty 5" in n and "no figure" in n for n in notes)


def test_mentor_flags_solution_without_insight():
    doc = parse(HEAD.format(extra="difficulty: 4\n") + (
        "A statement with $x$.\n\n```figure\ncircle at=(0,0) r=1\n```\n\n```answer\nx=1\n```\n\n"
        "````solution\nPlug in and turn the crank: x=1.\n````\n"))
    assert any("necessary insight" in n for n in mentor(doc))


def test_mentor_quiet_when_insight_named():
    doc = parse(HEAD.format(extra="difficulty: 4\n") + (
        "A statement with $x$.\n\n```figure\ncircle at=(0,0) r=1\n```\n\n```answer\nx=1\n```\n\n"
        "````solution\nThe key insight is the hidden symmetry; then x=1 follows.\n````\n"))
    # complete + names the insight → no mentor notes
    assert mentor(doc) == []


def test_mentor_silent_for_easy_problems():
    doc = parse(HEAD.format(extra="difficulty: 2\n") + "A simple warm-up. Find x.")
    assert mentor(doc) == []  # difficulty < 4 → mentor doesn't nag
