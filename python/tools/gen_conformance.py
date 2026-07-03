#!/usr/bin/env python3
"""Generate the shared conformance corpus from the Python reference (plan 09 M0).

The Python impl is the source of truth. This freezes its behaviour as data the JS port must
reproduce, so the two implementations can't silently drift:

    spec/conformance/
      corpus/        .mtph inputs (the examples + targeted edge cases)
      expected/dom/  <id>.json — the canonical DOM (parser output) for each input
      expected/svg/  <id>.<k>.svg — the rendered SVG of the k-th figure block in each input

Run it in CI: regenerate and `git diff --exit-code` — a diff means Python changed and the gold
must be updated intentionally. Run:  python python/tools/gen_conformance.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "python" / "src"))

from mtph.diagram.compile_svg import compile_figure  # noqa: E402
from mtph.diagram.plot import compile_plot  # noqa: E402
from mtph.parser import parse  # noqa: E402
from mtph.render.html import render_html  # noqa: E402

CORPUS = _ROOT / "spec" / "conformance" / "corpus"
DOM_OUT = _ROOT / "spec" / "conformance" / "expected" / "dom"
SVG_OUT = _ROOT / "spec" / "conformance" / "expected" / "svg"
HTML_OUT = _ROOT / "spec" / "conformance" / "expected" / "html"


def main() -> int:
    CORPUS.mkdir(parents=True, exist_ok=True)
    DOM_OUT.mkdir(parents=True, exist_ok=True)
    SVG_OUT.mkdir(parents=True, exist_ok=True)
    HTML_OUT.mkdir(parents=True, exist_ok=True)
    # SVG/HTML gold is regenerated wholesale; clear stale renders so a removed block can't linger.
    for old in SVG_OUT.glob("*.svg"):
        old.unlink()
    for old in HTML_OUT.glob("*.html"):
        old.unlink()

    # The corpus is the example bank (broad feature coverage) plus any files dropped into corpus/.
    sources = sorted((_ROOT / "spec" / "examples").glob("*.mtph"))
    sources += [p for p in sorted(CORPUS.glob("*.mtph"))]

    seen = set()
    n = 0
    figs = 0
    plots = 0
    for src in sources:
        stem = src.stem
        if stem in seen:
            continue
        seen.add(stem)
        text = src.read_text(encoding="utf-8")
        # keep a copy of every input in corpus/ so JS reads one directory
        (CORPUS / f"{stem}.mtph").write_text(text, encoding="utf-8")
        doc = parse(text)
        dom = doc.to_dom()
        (DOM_OUT / f"{stem}.json").write_text(
            json.dumps(dom, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        # Freeze the full HTML document render via the deterministic cdnjs KaTeX path (no vendored
        # fonts embedded), so the JS renderer must reproduce it byte-for-byte — both the normal
        # render and the self-quiz mode.
        (HTML_OUT / f"{stem}.html").write_text(
            render_html(doc, katex="cdnjs"), encoding="utf-8",
        )
        (HTML_OUT / f"{stem}.quiz.html").write_text(
            render_html(doc, katex="cdnjs", quiz=True), encoding="utf-8",
        )
        # Freeze each figure/plot block's rendered SVG (default options: no title/grid/nudge), so
        # the JS renderer must reproduce it byte-for-byte. Figures and plots share the .<k>.svg
        # namespace, indexed by their position among renderable blocks of the same kind.
        # A source with `{{param}}` placeholders isn't directly compilable — it's a template
        # resolved at render time. Those are covered by the HTML gold (which substitutes defaults);
        # skip them here so the per-block SVG gold stays "raw source → SVG".
        fk = 0
        pk = 0
        for block in dom["blocks"]:
            if block["type"] == "figure" and "{{" not in block["source"]:
                svg = compile_figure(block["source"])
                (SVG_OUT / f"{stem}.fig.{fk}.svg").write_text(svg + "\n", encoding="utf-8")
                fk += 1
                figs += 1
            elif block["type"] == "plot" and "{{" not in block["source"]:
                svg = compile_plot(block["source"])
                (SVG_OUT / f"{stem}.plot.{pk}.svg").write_text(svg + "\n", encoding="utf-8")
                pk += 1
                plots += 1
        n += 1
    print(f"conformance: wrote {n} inputs + DOM + {figs} figure + {plots} plot SVGs + {n} HTML "
          "docs to spec/conformance/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
