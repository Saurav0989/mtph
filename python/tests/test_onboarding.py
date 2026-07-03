"""Onboarding & templates (plan 07): doctor, init, prompt, the card, and new --template."""
import json
from pathlib import Path

from typer.testing import CliRunner

from mtph._docs import agents_md, card_md
from mtph.cli import app
from mtph.health import health_report
from mtph.templates import TEMPLATES, template_ids
from mtph.verify import verify

runner = CliRunner()


# -- the card + the required read --------------------------------------------
def test_card_is_condensed_doctrine():
    text = card_md()
    assert "Seven Pillars" in text
    assert len(text.splitlines()) <= 220  # condensed, not the 885-line thesis


def test_agents_points_at_card_and_keeps_backslash_box():
    text = agents_md()
    assert "card.md" in text  # §0 now points at the card, not "read the whole thesis"
    assert "Backslash rule" in text


def test_required_read_stays_bounded():
    # AGENTS.md + card.md is the whole required read; guard against bloat back toward ~2,100 lines
    total = len(agents_md().splitlines()) + len(card_md().splitlines())
    assert total <= 500


# -- doctor / health ---------------------------------------------------------
def test_health_report_shape():
    r = health_report()
    assert {"python", "mtph", "katex", "extras", "ok"} <= set(r)
    assert {"raster", "export", "app"} <= set(r["extras"])
    assert "install" in r["extras"]["raster"]  # every extra names its install command


def test_doctor_json_is_valid():
    res = runner.invoke(app, ["doctor", "--format", "json"])
    data = json.loads(res.stdout)
    assert data["mtph"] and "katex" in data


# -- prompt ------------------------------------------------------------------
def test_prompt_emits_the_card():
    res = runner.invoke(app, ["prompt"])
    assert res.exit_code == 0
    assert "Authoring `.mtph`" in res.stdout


def test_prompt_full_appends_doctrine():
    res = runner.invoke(app, ["prompt", "--full"])
    assert "Seven Pillars" in res.stdout  # the card is appended


# -- templates ---------------------------------------------------------------
def test_all_templates_verify_ok():
    for tid, content in TEMPLATES.items():
        assert verify(content).status == "ok", tid


def test_new_template_scaffolds_a_verifiable_file(tmp_path):
    out = tmp_path / "p.mtph"
    res = runner.invoke(app, ["new", str(out), "--template", "coupled-pendulum"])
    assert res.exit_code == 0 and out.exists()
    assert verify(out.read_text(encoding="utf-8")).status == "ok"


def test_new_template_list():
    res = runner.invoke(app, ["new", "--template", "list"])
    for tid in template_ids():
        assert tid in res.stdout


# -- viewer backend refresh --------------------------------------------------
def test_refresh_backend_errors_cleanly_without_a_backend(monkeypatch, tmp_path):
    # HOME with no ~/.mtph/venv → a clear, non-crashing error (exit 1), never a traceback
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    res = runner.invoke(app, ["install-viewer", "--refresh-backend"])
    assert res.exit_code == 1
    assert "backend venv" in res.output or "source tree" in res.output
