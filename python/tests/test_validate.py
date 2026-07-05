import pytest

from mtph.parser import load, parse
from mtph.validate import validate

from conftest import example_files

VALID = '---\nmtph: "0.1"\ntitle: T\nsubject: physics\n---\nbody\n'


def test_valid_document():
    assert validate(parse(VALID)) == []


def test_bad_subject():
    errors = validate(parse(VALID.replace("subject: physics", "subject: chemistry")))
    assert any("subject" in e for e in errors)


def test_missing_title():
    errors = validate(parse('---\nmtph: "0.1"\nsubject: math\n---\nx\n'))
    assert any("title" in e for e in errors)


def test_unsupported_version():
    errors = validate(parse('---\nmtph: "9.0"\ntitle: T\nsubject: math\n---\nx\n'))
    assert any("version" in e for e in errors)


def test_bad_difficulty_range():
    errors = validate(parse(VALID.replace("subject: physics", "subject: physics\ndifficulty: 9")))
    assert any("difficulty" in e for e in errors)


@pytest.mark.parametrize("path", example_files(), ids=lambda p: p.stem)
def test_examples_validate(path):
    assert validate(load(path)) == []


def test_symbol_test_range_form_validates():
    """Plan 12: a symbol's `test:` may be a pinned number *or* a `{from, to}` sampling range.
    Both forms validate; a range missing an endpoint or with a stray key does not."""
    base = ('---\nmtph: "0.2"\nid: r\ntitle: T\nsubject: physics\n'
            "symbols:\n  {SYM}\n---\n\nbody $x$\n")
    assert validate(parse(base.replace("{SYM}", "theta: { test: { from: 0.1, to: 1.2 } }"))) == []
    assert validate(parse(base.replace("{SYM}", "g: { dim: acceleration, test: 9.8 }"))) == []
    # a range needs both endpoints
    assert validate(parse(base.replace("{SYM}", "theta: { test: { from: 0.1 } }"))) != []
    # no extra keys inside the range object
    assert validate(parse(base.replace("{SYM}", "theta: { test: { from: 0, to: 1, mid: 0.5 } }"))) != []


def test_both_format_versions_validate():
    # 0.2 is a backward-compatible superset; 0.1 files must still validate (same MAJOR).
    from mtph import SCHEMA_VERSION
    assert SCHEMA_VERSION == "0.2"
    for v in ("0.1", "0.2"):
        doc = parse(f'---\nmtph: "{v}"\ntitle: T\nsubject: physics\n---\n\nbody $x$\n')
        assert validate(doc) == [], v
