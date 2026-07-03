"""``mtph verify`` — graduated, machine-parseable verification (plan 02).

Unlike :func:`mtph.validate.validate` (a binary schema gate), ``verify`` runs a battery of
checks and returns a :class:`Report` whose top-level ``status`` is one of ``ok | warnings |
error`` and whose every finding carries a stable ``id`` and a ``fix`` string. It is the keystone
that lets an AI author check its own work without a human in the loop.

Usage::

    from mtph.verify import verify
    report = verify(text=source, path="problem.mtph")
    print(report.to_dict())   # JSON-ready
"""
from __future__ import annotations

from typing import List, Optional

from ..parser import MtphSyntaxError, parse
from .checks import CHECK_NAMES, CHECKS, Context
from .model import CheckResult, Finding, Report

__all__ = ["verify", "Report", "Finding", "CheckResult", "CHECK_NAMES"]


def verify(text: str, *, path: Optional[str] = None,
           checks: Optional[List[str]] = None) -> Report:
    """Verify `.mtph` source text and return a :class:`Report`.

    ``checks`` optionally restricts which check groups run (by name, see
    :data:`mtph.verify.checks.CHECK_NAMES`). A parse failure short-circuits to a single
    ``parse`` error finding rather than raising.
    """
    try:
        doc = parse(text)
    except MtphSyntaxError as e:
        return Report(
            file=path,
            mtph_version="?",
            checks=[CheckResult("parse", [Finding(
                id="parse.error", severity="error", message=str(e),
                fix="Fix the YAML front-matter (it must open and close with `---`) or block structure.",
            )])],
        )

    ctx = Context(text=text, doc=doc, path=path)
    selected = set(checks) if checks else None
    results = [fn(ctx) for name, fn in CHECKS if selected is None or name in selected]
    return Report(file=path, mtph_version=doc.mtph, checks=results)
