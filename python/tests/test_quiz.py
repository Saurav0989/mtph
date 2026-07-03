"""Self-quiz render mode (render_html(quiz=True))."""
from mtph.parser import parse
from mtph.render.html import render_html

_NUMERIC = """---
mtph: "0.2"
id: q-num
title: Q
subject: physics
topic: mechanics
difficulty: 1
answer:
  type: numeric
  value: 4.6
  unit: "m/s^2"
  tolerance: 0.05
---
A block slides down a 28° frictionless incline. Find its acceleration.
"""

_CHOICE = """---
mtph: "0.2"
id: q-choice
title: Q
subject: physics
topic: mechanics
difficulty: 1
answer:
  type: choice
  options: ["$g\\\\sin\\\\theta$", "$g\\\\cos\\\\theta$", "$g\\\\tan\\\\theta$"]
  correct: 0
---
Which is the acceleration down a frictionless incline?
"""

_EXPRESSION = """---
mtph: "0.2"
id: q-expr
title: Q
subject: physics
topic: mechanics
difficulty: 1
answer:
  type: expression
  value: 'a = g\\sin\\theta'
solution: |
  Along the incline, $ma = mg\\sin\\theta$.
---
Find the acceleration.
"""


def test_numeric_quiz_has_input_and_tolerance():
    h = render_html(parse(_NUMERIC), katex="cdnjs", quiz=True)
    assert 'data-type="numeric" data-correct="4.6" data-tol="0.05"' in h
    assert 'class="q-in"' in h and ">Check<" in h
    assert "m/s^2" in h                       # unit shown
    assert "mtph-quiz .q" in h                # checker script emitted
    assert 'data-type="numeric"' in h and "\\u2713" in h  # ✓ escape in the emitted script


def test_choice_quiz_has_clickable_options():
    h = render_html(parse(_CHOICE), katex="cdnjs", quiz=True)
    assert 'data-type="choice" data-correct="0"' in h
    assert h.count('class="q-opt"') == 3


def test_expression_quiz_reveals_without_input():
    h = render_html(parse(_EXPRESSION), katex="cdnjs", quiz=True)
    # no auto-check input for an expression, but the reveal is present
    assert 'data-type="numeric"' not in h and 'data-type="choice"' not in h
    assert "Show answer &amp; solution" in h
    # the checker script is only emitted when there's a quiz section (there is: the reveal)
    assert 'class="mtph-quiz"' in h


def test_default_render_is_unchanged_without_quiz():
    h = render_html(parse(_NUMERIC), katex="cdnjs")
    # the quiz *section* and checker script are absent (the CSS carries .mtph-quiz rules always)
    assert 'class="mtph-quiz"' not in h and "q.getAttribute('data-type')" not in h
    assert 'class="mtph-aside"' in h


def test_numeric_value_canonical_matches_no_trailing_zero():
    doc = parse(_NUMERIC.replace("value: 4.6", "value: 40.0"))
    h = render_html(doc, katex="cdnjs", quiz=True)
    assert 'data-correct="40"' in h            # 40.0 → "40" (matches JS String)
