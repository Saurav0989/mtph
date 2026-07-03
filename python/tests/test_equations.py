"""Equation numbering + cross-references (\\label / \\ref) — plan 03B."""
from mtph.parser import parse
from mtph.render.equations import collect_labels
from mtph.render.html import render_html
from mtph.verify import verify

HEAD = '---\nmtph: "0.2"\ntitle: T\nsubject: physics\n---\n\n'


def _doc(body):
    return parse(HEAD + body)


def test_collect_labels_numbers_unique_in_order():
    doc = _doc("```math\na=1 \\label{eq:a}\n```\n\n```math\nb=2 \\label{eq:b}\n```\n")
    labels = collect_labels(doc)
    assert labels["eq:a"] == (1, "eq-a")
    assert labels["eq:b"] == (2, "eq-b")


def test_labeled_equation_is_numbered_and_anchored():
    html = render_html(_doc("```math\nF=ma \\label{eq:n2}\n```\n"), katex="none")
    assert 'class="mtph-math numbered" id="eq-n2"' in html
    assert '<span class="eqno">(1)</span>' in html


def test_unlabeled_equation_is_not_numbered():
    html = render_html(_doc("```math\nF=ma\n```\n"), katex="none")
    assert 'class="mtph-math numbered"' not in html  # the class is only in the CSS, not used
    assert '<span class="eqno">' not in html


def test_label_is_stripped_before_katex():
    html = render_html(_doc("```math\nF=ma \\label{eq:n2}\n```\n"), katex="none")
    assert "\\label" not in html  # KaTeX would choke on it


def test_ref_in_prose_becomes_a_link():
    html = render_html(_doc("By \\ref{eq:n2} we win.\n\n```math\nF=ma \\label{eq:n2}\n```\n"),
                       katex="none")
    assert '<a class="eqref" href="#eq-n2">(1)</a>' in html


def test_unknown_ref_renders_placeholder():
    html = render_html(_doc("See \\ref{eq:ghost}."), katex="none")
    assert "(?)" in html


def test_ref_inside_inline_math_is_left_intact():
    # a \ref inside $...$ must not be turned into an <a> (would corrupt the KaTeX source)
    html = render_html(_doc("Value $x = \\ref{eq:n2}$ here.\n\n```math\nF=ma \\label{eq:n2}\n```\n"),
                       katex="none")
    assert "$x = \\ref{eq:n2}$" in html
    assert '<a class="eqref"' not in html  # the only ref was inside math


def test_verify_flags_dangling_ref_and_duplicate_label():
    body = ("See \\ref{eq:ghost}.\n\n```math\nx=1 \\label{eq:a}\n```\n\n"
            "```math\ny=2 \\label{eq:a}\n```\n")
    refs = [c for c in verify(HEAD + body).checks if c.group == "refs"][0]
    ids = [f.id for f in refs.findings]
    assert "ref.undefined" in ids
    assert "ref.duplicate_label" in ids


def test_verify_clean_when_refs_resolve():
    body = "By \\ref{eq:a}.\n\n```math\nx=1 \\label{eq:a}\n```\n"
    assert verify(HEAD + body).status == "ok"


def test_doc_without_labels_unchanged():
    # back-compat: ordinary docs render with no numbering machinery
    html = render_html(_doc("```math\nE=mc^2\n```\n"), katex="none")
    assert "$$ E=mc^2 $$" in html
    assert 'class="mtph-math numbered"' not in html
