"""Explorable parameters: substitution (mathr-free) + the verify `params` check + render."""
from mtph.params import defaults, format_value, resolve, substitute
from mtph.render.html import render_html
from mtph.parser import parse
from mtph.verify import verify


def test_format_value_matches_js_string():
    assert format_value(30) == "30"
    assert format_value(2.0) == "2"      # integer-valued float loses .0 (JS String(2) == "2")
    assert format_value(2.5) == "2.5"
    assert format_value(0.5) == "0.5"


def test_substitute_and_defaults():
    meta = {"params": {"theta": {"min": 0, "max": 90, "default": 30}}}
    assert defaults(meta) == {"theta": 30}
    assert substitute("angle={{theta}} x=1", {"theta": 30}) == "angle=30 x=1"
    assert substitute("angle={{ theta }}", {"theta": 45}) == "angle=45"
    # an unknown reference is left untouched
    assert substitute("a={{missing}}", {"theta": 30}) == "a={{missing}}"
    # no placeholders → identity (fast path)
    assert substitute("angle=30", {"theta": 30}) == "angle=30"
    assert resolve("angle={{theta}}", meta) == "angle=30"


_DOC = """---
mtph: "0.2"
id: p
title: P
subject: physics
topic: mechanics
difficulty: 1
params:
  theta: { min: 0, max: 90, default: 30, unit: "deg" }
---
Body.

```figure
incline angle={{theta}} length=5
```
"""


def test_param_figure_verifies_and_renders_with_default():
    text = _DOC
    rep = verify(text)
    groups = {c.group: c for c in rep.checks}
    assert groups["figure"].status == "ok"      # {{theta}} resolved to 30 before compiling
    assert groups["params"].status == "ok"
    html = render_html(parse(text), katex="cdnjs")
    # 30° incline rendered; the template is gone from the output
    assert "{{theta}}" not in html and "<svg" in html


def test_param_undefined_reference_flagged():
    text = _DOC.replace("angle={{theta}}", "angle={{phi}}")
    rep = verify(text)
    params = next(c for c in rep.checks if c.group == "params")
    assert any(f.id == "param.undefined" for f in params.findings)


def test_param_bad_range_flagged():
    text = _DOC.replace("min: 0, max: 90, default: 30", "min: 90, max: 0, default: 30")
    rep = verify(text)
    params = next(c for c in rep.checks if c.group == "params")
    assert params.status == "error" and any(f.id == "param.bad_range" for f in params.findings)


def test_param_default_out_of_range_flagged():
    text = _DOC.replace("min: 0, max: 90, default: 30", "min: 0, max: 90, default: 200")
    rep = verify(text)
    params = next(c for c in rep.checks if c.group == "params")
    assert any(f.id == "param.bad_range" for f in params.findings)
