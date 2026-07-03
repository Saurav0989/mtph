import pytest

from mtph.parser import MtphSyntaxError, parse, serialize

DOC = '''---
mtph: "0.1"
title: Test
subject: physics
---

Some prose with $x$ inline.

$$E = mc^2$$

```figure
point P at=(0,0)
```

```plot
x: -1..1
f(x) = x
```
'''


def test_parse_block_types():
    doc = parse(DOC)
    assert doc.mtph == "0.1"
    assert doc.meta["title"] == "Test"
    assert [b.type for b in doc.blocks] == ["prose", "math", "figure", "plot"]


def test_math_block_extracts_latex():
    doc = parse(DOC)
    math = [b for b in doc.blocks if b.type == "math"][0]
    assert math.latex == "E = mc^2"


def test_single_line_display_math():
    doc = parse('---\nmtph: "0.1"\ntitle: T\nsubject: math\n---\n$$a+b$$\n')
    assert doc.blocks[0].type == "math"
    assert doc.blocks[0].latex == "a+b"


def test_roundtrip_preserves_dom():
    doc = parse(DOC)
    doc2 = parse(serialize(doc))
    assert doc.to_dom() == doc2.to_dom()


def test_missing_frontmatter_raises():
    with pytest.raises(MtphSyntaxError):
        parse("no front matter here")


def test_missing_version_raises():
    with pytest.raises(MtphSyntaxError):
        parse("---\ntitle: T\nsubject: math\n---\nbody\n")


def test_unterminated_fence_raises():
    bad = '---\nmtph: "0.1"\ntitle: T\nsubject: math\n---\n```figure\npoint P at=(0,0)\n'
    with pytest.raises(MtphSyntaxError):
        parse(bad)


def test_figure_caption_attribute():
    src = '---\nmtph: "0.1"\ntitle: T\nsubject: math\n---\n```figure caption="hi"\npoint P at=(0,0)\n```\n'
    doc = parse(src)
    assert doc.blocks[0].caption == "hi"
