#!/usr/bin/env python3
"""Run `mtph verify` over the mutation corpus and report the confusion table (plan 11).

This is the instrument the whole v0.3 verifier program is tuned against: it measures what fraction
of seeded gross errors the current checkers *catch* and how often they cry wolf on a clean file.
Plans 12-13 are "make these numbers go up"; the published bar (>=80% caught, <5% false positives)
becomes a testable claim rather than marketing.

Definitions (plan 11 Interfaces):
  * *caught*  — verify on a mutated file yields >=1 finding whose id is in the manifest's
                ``expected_ids`` with severity ``error``.
  * *false positive* — verify on a clean annotated example yields any ``error`` in the
                ``dimension`` / ``numeric`` / ``solution`` check groups.

``--assert-bar`` exits non-zero unless ``catch_rate >= 0.80 and fp_rate < 0.05``. It is *off* by
default (at plan-11 time only H1/H2 exist, so the baseline is deliberately red); CI switches it on
at the end of plan 13.

Run:  python python/tools/mutation_report.py [--assert-bar] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "python" / "src"))

from mtph.verify import verify  # noqa: E402

MANIFEST = _ROOT / "spec" / "mutations" / "manifest.json"
EXAMPLES = _ROOT / "spec" / "examples"
CLASSES = ("signflip", "factor", "trig", "power", "unit")
FP_GROUPS = {"dimension", "numeric", "solution"}
BAR_CATCH, BAR_FP = 0.80, 0.05


def _error_ids(path: Path) -> Set[str]:
    """The ids of the ``error``-severity findings verify reports for a file."""
    report = verify(path.read_text(encoding="utf-8"), path=str(path))
    return {f.id for c in report.checks for f in c.findings if f.severity == "error"}


def _has_fp(path: Path) -> bool:
    """Does a clean example raise a spurious dimension/numeric/solution error?"""
    report = verify(path.read_text(encoding="utf-8"), path=str(path))
    return any(c.group in FP_GROUPS and any(f.severity == "error" for f in c.findings)
               for c in report.checks)


def _clean_examples() -> List[Path]:
    """The clean annotated examples (the mutation substrate): every example with a symbols table."""
    from mtph.parser import parse
    out: List[Path] = []
    for p in sorted(EXAMPLES.glob("*.mtph")):
        meta = parse(p.read_text(encoding="utf-8")).meta
        if isinstance(meta.get("symbols"), dict) and meta["symbols"]:
            out.append(p)
    return out


def run(paths: Optional[Iterable[str]] = None) -> Dict:
    """Compute the catch-rate / false-positive metrics over the corpus.

    ``paths`` optionally restricts the mutants considered (by manifest ``file`` path or basename);
    the default is the whole committed corpus. False positives are always measured over every clean
    annotated example."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if paths is not None:
        wanted = {str(p) for p in paths}
        manifest = [e for e in manifest
                    if e["file"] in wanted or Path(e["file"]).name in wanted]

    by_class: Dict[str, Dict[str, int]] = {c: {"caught": 0, "missed": 0} for c in CLASSES}
    caught = missed = 0
    for e in manifest:
        err_ids = _error_ids(_ROOT / e["file"])
        hit = any(eid in err_ids for eid in e["expected_ids"])
        bucket = by_class.setdefault(e["cls"], {"caught": 0, "missed": 0})
        if hit:
            caught += 1
            bucket["caught"] += 1
        else:
            missed += 1
            bucket["missed"] += 1

    clean = _clean_examples()
    false_pos = sum(1 for p in clean if _has_fp(p))

    total = caught + missed
    return {
        "caught": caught,
        "missed": missed,
        "false_pos": false_pos,
        "clean": len(clean),
        "catch_rate": (caught / total) if total else 0.0,
        "fp_rate": (false_pos / len(clean)) if clean else 0.0,
        "by_class": {c: {**v, "catch_rate": (v["caught"] / (v["caught"] + v["missed"]))
                         if (v["caught"] + v["missed"]) else 0.0}
                     for c, v in by_class.items()},
    }


def _format(metrics: Dict) -> str:
    lines = ["", "mutation corpus — verify confusion table", "=" * 46,
             f"{'class':<10}{'caught':>8}{'missed':>8}{'catch rate':>13}"]
    for c in CLASSES:
        b = metrics["by_class"].get(c, {"caught": 0, "missed": 0, "catch_rate": 0.0})
        total = b["caught"] + b["missed"]
        rate = f"{b['catch_rate'] * 100:5.1f}%" if total else "    — "
        lines.append(f"{c:<10}{b['caught']:>8}{b['missed']:>8}{rate:>13}")
    lines.append("-" * 46)
    lines.append(f"{'TOTAL':<10}{metrics['caught']:>8}{metrics['missed']:>8}"
                 f"{metrics['catch_rate'] * 100:>11.1f}%")
    lines.append("")
    lines.append(f"catch rate      : {metrics['catch_rate'] * 100:5.1f}%  "
                 f"({metrics['caught']}/{metrics['caught'] + metrics['missed']} mutants caught)  "
                 f"[bar >= {BAR_CATCH * 100:.0f}%]")
    lines.append(f"false-positive  : {metrics['fp_rate'] * 100:5.1f}%  "
                 f"({metrics['false_pos']}/{metrics['clean']} clean examples flagged)  "
                 f"[bar < {BAR_FP * 100:.0f}%]")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Report the mutation-corpus catch/false-positive rates.")
    ap.add_argument("--assert-bar", action="store_true",
                    help="exit non-zero unless catch_rate >= 0.80 and fp_rate < 0.05")
    ap.add_argument("--json", action="store_true", help="print the metrics dict as JSON")
    args = ap.parse_args(argv)

    metrics = run()
    print(json.dumps(metrics, indent=2, sort_keys=True) if args.json else _format(metrics))

    if args.assert_bar:
        if metrics["catch_rate"] >= BAR_CATCH and metrics["fp_rate"] < BAR_FP:
            return 0
        print(f"\nBAR NOT MET: catch_rate={metrics['catch_rate']:.2%} (need >= {BAR_CATCH:.0%}), "
              f"fp_rate={metrics['fp_rate']:.2%} (need < {BAR_FP:.0%})", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
