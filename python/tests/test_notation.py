"""Notation packs (plan 06): declarative convention + consistency checks (no new syntax)."""
from mtph.notation import PACKS, card, pack
from mtph.verify import verify

HEAD = '---\nmtph: "0.2"\ntitle: T\nsubject: physics\n{decl}---\n\n'


def _notation_check(decl, body):
    rep = verify(HEAD.format(decl=decl) + body)
    return next(c for c in rep.checks if c.group == "notation")


# -- the checks --------------------------------------------------------------
def test_irodov_flags_mathbf():
    c = _notation_check("notation: irodov\n", r"Force $\mathbf{F} = m\mathbf{a}$.")
    assert "notation.mixed_vectors" in [f.id for f in c.findings]


def test_irodov_clean_with_vec():
    c = _notation_check("notation: irodov\n", r"Force $\vec{F} = m\vec{a}$.")
    assert c.findings == []
    assert c.declared is None  # checked → not 'unknown'


def test_american_allows_either_but_flags_mixing():
    mixed = _notation_check("notation: american\n", r"$\vec{F}$ then $\mathbf{p}$.")
    assert "notation.mixed_vectors" in [f.id for f in mixed.findings]
    clean = _notation_check("notation: american\n", r"Only $\mathbf{F}$ here.")
    assert clean.findings == []


def test_jee_flags_mathbf():
    c = _notation_check("notation: jee\n", r"$\mathbf{F}$.")
    assert "notation.mixed_vectors" in [f.id for f in c.findings]


def test_no_declaration_is_unknown_never_ok():
    c = _notation_check("", r"Force $\mathbf{F}$ with no pack.")
    assert c.declared == "unknown"
    assert c.findings == []


def test_figure_labels_do_not_trigger_vector_check():
    # \vec/\mathbf in figure labels are not the math-notation choice; don't flag them
    body = 'x\n\n```figure\nvector from=(0,0) to=(1,1) label="\\mathbf{v}"\n```\n'
    c = _notation_check("notation: irodov\n", body)
    assert c.findings == []


# -- packs + card ------------------------------------------------------------
def test_packs_have_required_fields():
    for pid, p in PACKS.items():
        assert {"tradition", "vector", "vector_strict", "frames", "gravity"} <= set(p)
    assert pack("nope") is None


def test_card_states_the_vector_rule():
    text = card("irodov")
    assert "irodov" in text and r"\vec" in text
    assert "plain LaTeX" in text  # always reminds: no new syntax
