"""Data model for ``mtph verify`` — findings, per-check results, and the rolled-up report.

The whole point of this model is to be **machine-parseable and stable** (see
``plans/02-verification-engine.md`` and principle P3): an AI or CI step branches on
``report["status"]`` and on each ``finding["id"]``/``severity``/``fix``. A human view is a
presentation layer on top, never the only output.

Severity vs. status vocabulary (kept deliberately distinct):

* a *finding* has a ``severity`` in ``{info, warning, error}``;
* a *check group* has a ``status`` in ``{ok, info, warning, error, unknown}``
  (``unknown`` = "I could not check this; a human must" — a first-class result, principle P4);
* the *report* has a top-level ``status`` in ``{ok, warnings, error}`` for pass/fail.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# finding severities, ordered worst-last
_SEVERITY_RANK = {"ok": 0, "info": 1, "warning": 2, "error": 3}


@dataclass
class Finding:
    """One concrete, actionable problem the tool detected."""

    id: str  # stable, namespaced, e.g. "latex.backslash"
    severity: str  # info | warning | error
    message: str  # human-readable description of what is wrong
    fix: str = ""  # how to fix it (AI acts on this — principle / DD§17)
    line: Optional[int] = None  # 1-based line in the source file, best-effort
    context: Optional[str] = None  # where it is, e.g. "math block", "answer.value"
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"id": self.id, "severity": self.severity, "message": self.message}
        if self.fix:
            d["fix"] = self.fix
        if self.line is not None:
            d["line"] = self.line
        if self.context:
            d["context"] = self.context
        d.update(self.extra)
        return d


@dataclass
class CheckResult:
    """The outcome of one check group (e.g. ``latex``, ``figure``)."""

    group: str
    findings: List[Finding] = field(default_factory=list)
    # an explicit status the check declares regardless of findings — used for "unknown"
    # (e.g. content correctness, or a check we can't run in this environment).
    declared: Optional[str] = None
    message: str = ""  # for unknown/empty groups, why
    # structured group-level counts (e.g. the `solution` group's step tallies) — machine-readable
    # evidence for what was and wasn't checked. Emitted in ``to_dict`` only when non-empty.
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def status(self) -> str:
        if self.declared is not None:
            return self.declared
        worst = "ok"
        for f in self.findings:
            if _SEVERITY_RANK.get(f.severity, 0) > _SEVERITY_RANK[worst]:
                worst = f.severity
        return worst

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"status": self.status}
        if self.message:
            d["message"] = self.message
        if self.extra:
            d["extra"] = self.extra
        if self.findings:
            d["findings"] = [f.to_dict() for f in self.findings]
        return d


@dataclass
class Report:
    """The full verification report for one file."""

    file: Optional[str]
    mtph_version: str
    checks: List[CheckResult] = field(default_factory=list)

    @property
    def status(self) -> str:
        """Top-level pass/fail. ``unknown`` groups never fail the run (principle P4)."""
        has_warning = False
        for c in self.checks:
            for f in c.findings:
                if f.severity == "error":
                    return "error"
                if f.severity == "warning":
                    has_warning = True
        return "warnings" if has_warning else "ok"

    @property
    def exit_code(self) -> int:
        return 1 if self.status == "error" else 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "file": self.file,
            "mtph_version": self.mtph_version,
            "checks": {c.group: c.to_dict() for c in self.checks},
        }
