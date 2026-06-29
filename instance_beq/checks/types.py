"""Shared result types for checks and baselines."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

Verdict = Literal["faithful", "unfaithful", "unknown"]
CheckName = Literal[
    "definitional",
    "instance_soundness",
    "transfer_validity",
    "statement_faithfulness",
]


@dataclass
class CheckResult:
    check: CheckName
    target: str
    verdict: Verdict
    confidence: Optional[float] = None       # None for purely-symbolic checks
    evidence: dict = field(default_factory=dict)
    cost: dict = field(default_factory=lambda: {"lean_calls": 0, "llm_calls": 0, "wall_s": 0.0})

    @property
    def passed(self) -> bool:
        return self.verdict == "faithful"

    def to_dict(self) -> dict:
        return {
            "check": self.check,
            "target": self.target,
            "verdict": self.verdict,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "cost": self.cost,
        }


@dataclass
class Certificate:
    """Per-artifact aggregate. The FORMAL certificate is checks 1 ∧ 2 ∧ 3a only (3b is the
    informal bridge, reported separately)."""
    path: str
    results: list[CheckResult] = field(default_factory=list)

    def by_check(self, name: CheckName) -> list[CheckResult]:
        return [r for r in self.results if r.check == name]

    @property
    def formal_faithful(self) -> Verdict:
        formal = [r for r in self.results
                  if r.check in ("definitional", "instance_soundness", "transfer_validity")]
        if not formal:
            return "unknown"
        if any(r.verdict == "unfaithful" for r in formal):
            return "unfaithful"
        if all(r.verdict == "faithful" for r in formal):
            return "faithful"
        return "unknown"

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "formal_faithful": self.formal_faithful,
            "results": [r.to_dict() for r in self.results],
        }
