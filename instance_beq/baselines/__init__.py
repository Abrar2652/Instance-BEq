"""Baselines (apples-to-apples with the certifier).

A. type-check-only : file compiles with zero errors -> "faithful". Passes hollow instances and
   mis-stated theorems (the point).
B. majority_voting : port of SITA's majorty_voting.py, thresholded to a binary call (skeleton).
C. llm_judge       : ReForm-style (informal, formal) -> faithful? yes/no with rationale.

All emit CheckResult with check="..."-agnostic target="<file>" so eval/metrics scores them like
the certifier's overall verdict.
"""
from __future__ import annotations

import re
import time
from typing import Optional

from instance_beq.artifacts import ParsedArtifact
from instance_beq.config import InstanceBEqConfig, DEFAULT
from instance_beq.harness.lean_oracle import LeanOracle
from instance_beq.harness.llm import LLMClient
from instance_beq.checks.types import CheckResult


def baseline_typecheck_only(art: ParsedArtifact, oracle: LeanOracle) -> CheckResult:
    t0 = time.time()
    res = oracle.check_file(art.path)
    verdict = "faithful" if res.ok else "unfaithful"
    return CheckResult(
        check="instance_soundness",  # reuse slot; metrics treats baseline verdict as overall
        target=art.path, verdict=verdict, confidence=None,
        evidence={"baseline": "typecheck_only", "errors": len(res.errors),
                  "uses_sorry": res.uses_sorry},
        cost={"lean_calls": 1, "llm_calls": 0, "wall_s": time.time() - t0},
    )


def baseline_llm_judge(
    art: ParsedArtifact, llm: LLMClient, cfg: InstanceBEqConfig = DEFAULT
) -> CheckResult:
    t0 = time.time()
    informal = (art.informal or {}).get("problem_statement", "")
    formal = "\n".join(d.raw for d in art.decls)[:6000]
    prompt = (
        "@mock:judge_" + _file_key(art.path) + "\n"
        "You are evaluating whether a Lean 4 formalization faithfully captures an informal "
        "optimization problem (definitions, instances, and theorem statements). Answer strictly "
        'as JSON {"faithful": true|false, "confidence": 0-1, "reason": "..."}.\n'
        f"Informal problem: {informal}\n"
        f"Lean formalization:\n{formal}\n"
    )
    raw = llm.complete(prompt)
    faithful, conf, reason = _parse_judge_json(raw)
    return CheckResult(
        check="instance_soundness", target=art.path,
        verdict="faithful" if faithful else "unfaithful", confidence=conf,
        evidence={"baseline": "llm_judge", "reason": reason},
        cost={"lean_calls": 0, "llm_calls": 1, "wall_s": time.time() - t0},
    )


def baseline_majority_voting(
    art: ParsedArtifact, llm: LLMClient, cfg: InstanceBEqConfig = DEFAULT,
    rounds: int = 16, threshold: float = 60.0,
) -> CheckResult:
    """Skeleton port of SITA majorty_voting.py: average a 0-100 quality score over `rounds`
    votes, threshold to a binary verdict. the implementation: port the exact rubric/prompt from
    Code/src/majorty_voting.py for a faithful baseline."""
    t0 = time.time()
    informal = (art.informal or {}).get("problem_statement", "")
    formal = "\n".join(d.raw for d in art.decls)[:6000]
    scores: list[float] = []
    for i in range(rounds):
        prompt = (
            f"@mock:mv_{_file_key(art.path)}_{i}\n"
            "Rate 0-100 how well this Lean formalization captures the informal problem across "
            "problem formalization, algorithm correctness, update-scheme explicitness, theoretical "
            "analysis, proof completion. Output ONLY the integer.\n"
            f"Informal: {informal}\nFormal:\n{formal}\n"
        )
        raw = llm.complete(prompt)
        m = re.search(r"\d+", raw)
        if m:
            scores.append(float(m.group(0)))
    avg = sum(scores) / len(scores) if scores else 0.0
    return CheckResult(
        check="instance_soundness", target=art.path,
        verdict="faithful" if avg >= threshold else "unfaithful",
        confidence=avg / 100.0,
        evidence={"baseline": "majority_voting", "avg_score": avg, "n": len(scores)},
        cost={"lean_calls": 0, "llm_calls": len(scores), "wall_s": time.time() - t0},
    )


def _file_key(path: str) -> str:
    import os
    return re.sub(r"[^A-Za-z0-9]+", "_", os.path.basename(path)).strip("_")


def _parse_judge_json(raw: str) -> tuple[bool, Optional[float], str]:
    import json
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return False, None, "unparseable"
    try:
        d = json.loads(m.group(0))
        return bool(d.get("faithful", False)), d.get("confidence"), str(d.get("reason", ""))
    except Exception:
        return False, None, "invalid json"
