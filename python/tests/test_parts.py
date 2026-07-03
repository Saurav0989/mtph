"""Part-coverage verification (check_parts) — semantic checks the team asked for."""
from mtph.verify import verify

HEAD = '---\nmtph: "0.2"\ntitle: T\nsubject: physics\n---\n\n'


def _parts(body):
    rep = verify(HEAD + body)
    return [f.id for f in next(c for c in rep.checks if c.group == "parts").findings]


def test_missing_part_answer_flagged():
    body = ("Do **(a)** this, **(b)** that, **(c)** the other.\n\n"
            "```answer part=a\nx\n```\n\n```answer part=b\ny\n```\n")
    assert _parts(body) == ["parts.missing_answer"]  # (c) unanswered


def test_stale_part_answer_flagged():
    body = ("Do (a) and (b).\n\n"
            "```answer part=a\nx\n```\n\n```answer part=b\ny\n```\n\n```answer part=d\nz\n```\n")
    assert "parts.stale_answer" in _parts(body)  # (d) answered but not asked


def test_all_parts_answered_is_clean():
    body = "Do (a) and (b).\n\n```answer part=a\nx\n```\n\n```answer part=b\ny\n```\n"
    assert _parts(body) == []


def test_single_part_not_treated_as_multipart():
    # (a) inside inline math must not be read as a part marker
    assert _parts("Find $f(a)$ at the given point.") == []


def test_combined_answer_style_not_flagged():
    # multi-part statement but the author gives one combined answer — respect that choice
    assert _parts("Do (a) and (b).\n\n```answer\nboth x and y\n```") == []


def test_stray_far_letter_not_a_part():
    # only (a) present (no (b)) → not a marked multi-part problem
    assert _parts("Given (a) the setup, find the flux.\n\n```answer part=z\nq\n```") == []
