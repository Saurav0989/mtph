#!/usr/bin/env python3
"""Run ``mtph verify`` on the given ``.mtph`` files and emit a Markdown report.

Used by the ``verify-mtph`` GitHub Action: it verifies only the changed problem files, writes a
findings table to the job summary (and ``verify-report.md`` for the PR comment), and exits
non-zero if any file has an ``error`` — so a regression that ``validate`` would miss (a doubled
backslash, a dangling ``\\ref``, an undefined figure anchor) blocks the merge.

Runs standalone too: ``python .github/scripts/verify_changed.py path/to/a.mtph b.mtph``.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from mtph.verify import verify

_RANK = {"ok": 0, "warnings": 1, "error": 2}
_BADGE = {"ok": "✅ ok", "warnings": "⚠️ warnings", "error": "🛑 error"}
_SEV = {"error": "🛑", "warning": "⚠️", "info": "ℹ️"}


def build_report(files):
    """Return ``(markdown, worst_status)`` for the given files."""
    files = [f for f in files if f.endswith(".mtph")]
    if not files:
        return "No changed `.mtph` files to verify.\n", "ok"

    head = ["## mtph verify", "", "| File | Status | Findings |", "|---|---|---|"]
    details = []
    worst = 0
    for f in sorted(files):
        try:
            text = Path(f).read_text(encoding="utf-8")
        except OSError as e:  # deleted/renamed away — skip, don't fail the run
            head.append(f"| `{f}` | — | skipped ({e.__class__.__name__}) |")
            continue
        rep = verify(text, path=f)
        worst = max(worst, _RANK.get(rep.status, 0))
        findings = [fd for c in rep.checks for fd in c.findings]
        head.append(f"| `{f}` | {_BADGE.get(rep.status, rep.status)} | {len(findings)} |")
        if findings:
            details.append(f"\n<details><summary><code>{f}</code> — "
                           f"{len(findings)} finding(s)</summary>\n")
            for fd in findings:
                loc = f" (line {fd.line})" if fd.line else ""
                details.append(f"- {_SEV.get(fd.severity, '')} **{fd.id}**{loc}: {fd.message}")
                if fd.fix:
                    details.append(f"  - _fix:_ {fd.fix}")
            details.append("</details>")

    worst_status = next(k for k, v in _RANK.items() if v == worst)
    return "\n".join(head + details) + "\n", worst_status


def main(argv):
    report, worst = build_report(argv)
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(report)
    Path("verify-report.md").write_text(report, encoding="utf-8")
    return 1 if _RANK[worst] >= _RANK["error"] else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
