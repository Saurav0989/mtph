"""Tests for body ```answer / ```solution blocks (plan 01, the locked v0.2 format addition)."""
from mtph.parser import parse, serialize
from mtph.render.html import render_html
from mtph.validate import validate
from mtph.verify import verify

HEAD = '---\nmtph: "0.2"\ntitle: T\nsubject: physics\n---\n'


def _types(doc):
    return [b.type for b in doc.blocks]


def test_parse_answer_block():
    doc = parse(HEAD + "Find it.\n\n```answer part=a type=expression\na = g\\sin\\theta\n```\n")
    answers = [b for b in doc.blocks if b.type == "answer"]
    assert len(answers) == 1
    assert answers[0].part == "a"
    assert answers[0].answer_type == "expression"
    assert answers[0].value == "a = g\\sin\\theta"


def test_multipart_answers():
    doc = parse(HEAD + "Q.\n\n```answer part=a\nx\n```\n\n```answer part=b\ny\n```\n")
    answers = [b for b in doc.blocks if b.type == "answer"]
    assert [a.part for a in answers] == ["a", "b"]


def test_solution_with_nested_figure():
    src = (HEAD + "Q.\n\n````solution\nText with $a$.\n\n```figure\nincline angle=30 length=5\n```\n````\n")
    doc = parse(src)
    sols = [b for b in doc.blocks if b.type == "solution"]
    assert len(sols) == 1
    assert [c.type for c in sols[0].children] == ["prose", "figure"]


def test_validate_accepts_body_blocks():
    doc = parse(HEAD + "Q.\n\n```answer\na=g\n```\n\n````solution\ntext\n````\n")
    assert validate(doc) == []


def test_render_puts_answer_solution_in_aside_not_inline():
    src = HEAD + "STATEMENT.\n\n```answer\na = g\\sin\\theta\n```\n\n````solution\nbecause $F=ma$.\n````\n"
    html = render_html(parse(src))
    assert "<details" in html  # aside present
    assert "Answer" in html and "Solution" in html
    # the answer value lives inside the details aside, after the statement
    assert html.index("STATEMENT") < html.index("a = g")


def test_render_nested_figure_in_solution():
    src = (HEAD + "Q.\n\n````solution\nsee figure.\n\n```figure\nincline angle=30 length=5\n```\n````\n")
    html = render_html(parse(src))
    assert "<svg" in html


def test_no_answer_flag_hides_body_answer():
    src = HEAD + "Q.\n\n```answer\na=g\n```\n"
    assert "a=g" not in render_html(parse(src), include_answer=False)


def test_roundtrip_body_blocks():
    src = (HEAD + "Q with $x$.\n\n```answer part=a type=freeform\nbecause.\n```\n\n"
           "````solution\nstep.\n\n```math\n\\frac{a}{b}\n```\n````\n")
    doc = parse(src)
    doc2 = parse(serialize(doc))
    assert _types(doc) == _types(doc2)
    sol = [b for b in doc.blocks if b.type == "solution"][0]
    sol2 = [b for b in doc2.blocks if b.type == "solution"][0]
    assert [c.type for c in sol.children] == [c.type for c in sol2.children]


def test_verify_checks_nested_solution_figure():
    src = (HEAD + "Q.\n\n````solution\ntext\n\n```figure\nforce from=ghost dir=down\n```\n````\n")
    r = verify(src)
    fig = {c.group: c for c in r.checks}["figure"]
    assert "figure.undefined_anchor" in [f.id for f in fig.findings]


def test_verify_flags_backslash_in_answer_block():
    src = HEAD + "Q.\n\n```answer\n\\\\frac{1}{2}\n```\n"
    r = verify(src)
    assert "latex.backslash" in [f.id for c in r.checks for f in c.findings]


def test_backcompat_frontmatter_answer_still_renders():
    src = ('---\nmtph: "0.1"\ntitle: T\nsubject: physics\n'
           "answer:\n  type: expression\n  value: 'a=g'\nsolution: |\n  because.\n---\nbody\n")
    html = render_html(parse(src))
    assert "Answer" in html and "Solution" in html


def test_body_answer_takes_precedence_over_meta():
    src = ('---\nmtph: "0.2"\ntitle: T\nsubject: physics\n'
           "answer:\n  type: expression\n  value: 'FROM_META'\n---\n"
           "Q.\n\n```answer\nFROM_BODY\n```\n")
    html = render_html(parse(src))
    assert "FROM_BODY" in html and "FROM_META" not in html
