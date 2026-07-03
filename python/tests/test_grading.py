"""Grading rubric (plan 01) + the visible-KaTeX-error guarantee (plan 05 §1)."""
import pytest

from mtph.parser import parse
from mtph.render.html import render_html
from mtph.validate import validate

GRADED = '''---
mtph: "0.2"
title: Graded
subject: physics
grading:
  - part: a
    points: 3
    criteria: Correct free-body diagram.
  - part: b
    points: 5
    criteria: 'Derive $a = g\\sin\\theta$.'
---

A block on an incline.

```answer
a = g\\sin\\theta
```
'''


def test_grading_validates():
    assert validate(parse(GRADED)) == []


def test_grading_renders_with_total():
    html = render_html(parse(GRADED), katex="none")
    assert '<div class="grading">' in html
    assert "3 pts" in html and "5 pts" in html
    assert "Total: 8 pts" in html


def test_grading_criteria_keeps_math():
    html = render_html(parse(GRADED), katex="none")
    assert r"$a = g\sin\theta$" in html  # left intact for KaTeX


def test_grading_requires_points_and_criteria():
    bad = '---\nmtph: "0.2"\ntitle: T\nsubject: math\ngrading:\n  - part: a\n---\n\n$x$\n'
    assert validate(parse(bad)) != []  # missing points + criteria


def test_no_grading_no_section():
    html = render_html(parse('---\nmtph: "0.2"\ntitle: T\nsubject: math\n---\n\n$x$\n'), katex="none")
    assert '<div class="grading">' not in html


def test_visible_katex_error_config_present():
    # P1: a bad command must render visibly wrong, not silently — KaTeX shows source in red
    head = render_html(parse('---\nmtph: "0.2"\ntitle: T\nsubject: math\n---\n\n$x$\n'), katex="cdn")
    assert "throwOnError:false" in head
    assert 'errorColor:"#cc0000"' in head
