"""The verify-mtph GitHub Action's aggregation script (plan 08)."""
import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / ".github" / "scripts" / "verify_changed.py"

HEAD = '---\nmtph: "0.2"\ntitle: T\nsubject: {s}\n---\n\n'


def _load():
    spec = importlib.util.spec_from_file_location("verify_changed", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_clean_file_reports_ok(tmp_path):
    f = tmp_path / "good.mtph"
    f.write_text(HEAD.format(s="math") + "Just $x + y$.\n", encoding="utf-8")
    md, worst = _load().build_report([str(f)])
    assert worst == "ok"
    assert "✅ ok" in md


def test_broken_figure_reports_error(tmp_path):
    f = tmp_path / "bad.mtph"
    f.write_text(HEAD.format(s="physics") + "x\n\n```figure\nvector from=O to=(1,1)\n```\n",
                 encoding="utf-8")
    md, worst = _load().build_report([str(f)])
    assert worst == "error"
    assert "figure.undefined_anchor" in md


def test_no_mtph_files_is_ok():
    md, worst = _load().build_report(["README.md", "src/foo.py"])
    assert worst == "ok"
    assert "No changed" in md
