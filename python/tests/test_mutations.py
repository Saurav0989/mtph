"""Tests for the mutation corpus & verifier QA harness (plan 11).

The generator (`python/tools/gen_mutations.py`) applies small, realistic mutation operators
to clean annotated examples and writes mutated `.mtph` files + a manifest. These tests pin the
operator contract (each operator makes exactly one targeted textual change and the result still
parses + validates) and the manifest's integrity.
"""
from __future__ import annotations

import difflib
import json
import sys
from pathlib import Path

from mtph.parser import parse
from mtph.validate import validate

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "python" / "tools"))

import gen_mutations as gm  # noqa: E402

MUTATIONS_DIR = _ROOT / "spec" / "mutations"
MANIFEST = MUTATIONS_DIR / "manifest.json"


def _changed_lines(a: str, b: str) -> int:
    """Number of source lines the mutation touched (replaced/added/removed)."""
    sm = difflib.SequenceMatcher(None, a.splitlines(), b.splitlines())
    return sum(max(i2 - i1, j2 - j1) for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != "equal")


def _doc(answer_value: str) -> str:
    """A minimal, valid `.mtph` document whose expression answer is `answer_value`."""
    return (
        "---\n"
        'mtph: "0.2"\n'
        "id: t\n"
        "title: T\n"
        "subject: physics\n"
        "answer:\n"
        "  type: expression\n"
        f"  value: '{answer_value}'\n"
        "---\n\n"
        "Body.\n"
    )


def test_operators():
    """Each operator makes exactly one targeted change (or reports no site), and the mutated
    LaTeX still parses and validates when spliced back into a document."""

    # --- signflip: flip the first *binary* +/- (leading unary sign is left alone) ---
    assert gm.op_signflip(r"2\mu L + 5R") == r"2\mu L - 5R"
    assert gm.op_signflip("a - b") == "a + b"
    assert gm.op_signflip(r"-mgR\cos\theta - x") == r"-mgR\cos\theta + x"
    assert gm.op_signflip(r"x^{-1} + y") == r"x^{-1} - y"  # exponent sign is not a site
    assert gm.op_signflip("in charge-free space") is None  # a word hyphen is not a math sign
    assert gm.op_signflip("the quasi-static route") is None
    assert gm.op_signflip("abc") is None

    # --- trig: swap the first \sin <-> \cos (whole command only, not \sinh) ---
    assert gm.op_trig(r"g\sin\theta") == r"g\cos\theta"
    assert gm.op_trig(r"\cos(2\theta)") == r"\sin(2\theta)"
    assert gm.op_trig(r"a\sin b\cos c") == r"a\cos b\cos c"  # first occurrence only
    assert gm.op_trig(r"\sinh x") is None
    assert gm.op_trig("x + y") is None

    # --- power: first bare ^2 -> ^3 (brace-aware; multi-digit exponents are left alone) ---
    assert gm.op_power("v_0^2") == "v_0^3"
    assert gm.op_power(r"mR^{2}\omega^2") == r"mR^{3}\omega^2"
    assert gm.op_power("x^2 + y^2") == "x^3 + y^2"
    assert gm.op_power("x^{12}") is None
    assert gm.op_power("abc") is None

    # --- factor: drop a leading 1/2, else knock a coefficient 2 down to 1 ---
    assert gm.op_factor(r"\tfrac12 mv^2") == "mv^2"
    assert gm.op_factor(r"\tfrac{1}{2}mR^2") == "mR^2"
    assert gm.op_factor(r"\frac{1}{2} k x^2") == "k x^2"
    assert gm.op_factor(r"2\pi\sqrt{L/g}") == r"1\pi\sqrt{L/g}"
    assert gm.op_factor(r"\sqrt{2gh}") == r"\sqrt{1gh}"
    assert gm.op_factor("v_0^2") is None  # ^2 is a power, not a coefficient
    assert gm.op_factor("abc") is None

    # --- unit: swap a numeric answer's unit for a dimension-CHANGING one ---
    assert gm.op_unit_swap("m/s") is not None
    assert gm.op_unit_swap("m/s") != "m/s"
    assert gm.op_unit_swap("J") is not None
    assert gm.op_unit_swap(None) is None

    # Every LaTeX operator, applied to a document's answer, keeps it parseable + valid.
    cases = {
        "signflip": r"a = b + c",
        "trig": r"a = g\sin\theta",
        "power": r"R = v_0^2",
        "factor": r"T = 2\pi\sqrt{L/g}",
    }
    for cls, value in cases.items():
        op = gm.LATEX_OPERATORS[cls]
        mutated_value = op(value)
        assert mutated_value is not None and mutated_value != value, cls
        src = _doc(value)
        mutated = src.replace(value, mutated_value, 1)
        assert mutated != src, cls
        assert validate(parse(mutated)) == [], cls  # still schema-valid after the mutation


def test_manifest_integrity():
    """Every manifest entry names real files that parse, validate, and differ from their source
    in a bounded way; the corpus spans all five classes with >=20 mutants (plan 11 acceptance)."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert isinstance(manifest, list)
    assert len(manifest) >= 20, f"expected >=20 mutants, got {len(manifest)}"
    assert {e["cls"] for e in manifest} == {"signflip", "factor", "trig", "power", "unit"}

    seen_files = set()
    for e in manifest:
        assert set(e) == {"file", "source", "cls", "expected_ids"}, e
        assert e["file"] not in seen_files, f"duplicate file {e['file']}"
        seen_files.add(e["file"])
        assert e["expected_ids"], e  # never claim a mutant nothing should catch
        mut = _ROOT / e["file"]
        src = _ROOT / e["source"]
        assert mut.exists(), e["file"]
        assert src.exists(), e["source"]
        mtext = mut.read_text(encoding="utf-8")
        stext = src.read_text(encoding="utf-8")
        assert validate(parse(mtext)) == [], f"{e['file']} does not validate"
        assert mtext != stext, f"{e['file']} is identical to its source"
        n = _changed_lines(stext, mtext)
        assert 1 <= n <= 2, f"{e['file']} changed {n} lines (want <=2)"
        # Regression: a mutation must land on answer/solution content — never a grading
        # `criteria:` line or a ` ```math ` display line (the one carrying a `\label`).
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
                None, stext.splitlines(), mtext.splitlines()).get_opcodes():
            if tag == "equal":
                continue
            for touched in mtext.splitlines()[j1:j2]:
                assert "criteria:" not in touched, f"{e['file']} mutated a grading criteria"
                assert "\\label{" not in touched, f"{e['file']} mutated a labelled display block"
