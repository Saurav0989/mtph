import pytest

from mtph.parser import load, parse
from mtph.render.html import render_html
from mtph.render.md import md_to_html

from conftest import example_files

DOC = '''---
mtph: "0.1"
title: Render Test
subject: physics
answer: { type: expression, value: "a=b" }
solution: |
  Because $x=1$.
---

Prose **bold** and $x$.

$$E=mc^2$$

```figure
point P at=(0,0) label="P"
```
'''


def test_render_html_structure():
    html = render_html(parse(DOC), katex="none")
    assert "<main>" in html
    assert "Render Test" in html
    assert "$$ E=mc^2 $$" in html
    assert "<svg" in html  # figure inlined
    assert "Answer" in html


def test_render_no_answer():
    html = render_html(parse(DOC), katex="none", include_answer=False)
    assert "<details" not in html  # the answer/solution aside element is absent


def test_markdown_protects_math():
    out = md_to_html("a *b* and $a*b*c$")
    assert "<em>b</em>" in out
    assert "$a*b*c$" in out  # math span untouched by italics


def test_markdown_escapes_html():
    assert "&lt;script&gt;" in md_to_html("<script>")


def test_multiline_inline_math_is_one_span():
    # inline math that wraps across source lines must stay a single span (not split by <br>)
    out = md_to_html("gives $a +\nb$ here")
    assert "$a +\nb$" in out
    assert "$a +<br>" not in out


def test_ordered_list_preserves_numbering():
    # 1. / blank / 2. arrive as separate blocks; <ol start=N> keeps them 1, 2, 3 (not 1, 1, 1)
    out = md_to_html("1. First.\n\n2. Second.\n\n3. Third.")
    assert '<ol start="2">' in out
    assert '<ol start="3">' in out
    assert out.index("<ol>") < out.index('<ol start="2">')  # first list has no start attr


def test_single_ordered_list_has_no_start_attr():
    out = md_to_html("1. only")
    assert "<ol>" in out and "start=" not in out


@pytest.mark.parametrize("path", example_files(), ids=lambda p: p.stem)
def test_examples_render(path):
    html = render_html(load(path), katex="none")
    assert "<main>" in html and len(html) > 100
