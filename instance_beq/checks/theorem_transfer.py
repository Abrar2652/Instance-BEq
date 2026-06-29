"""Check 3 — Theorem transfer.

3a. Transfer validity (symbolic, high precision): the instance theorem T_inst is a genuine
    specialization of the abstract theorem T_abs. We synthesize the canonical transfer proof
    (`apply T_abs (alg := <bridge>) <discharge>`) and compile it. If it closes, transfer is valid.

3b. Statement faithfulness (LLM-assisted + symbolic): T_inst's STATEMENT matches the informal
    claim (rate, hypotheses, inequality direction). Back-translate T_inst, structure both claims,
    symbolic-compare when possible, else calibrated LLM-judge. Reported separately from the formal
    certificate (it is the bridge to the informal world).

The transfer-proof SYNTHESIS for 3a needs the abstract theorem's name + hypothesis list, parsed
from the Template file. The scaffold provides the control flow and the template-parsing hook;
the implementation completes `synthesize_transfer_proof` against real templates on the cluster.
"""
from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Optional

from instance_beq.artifacts import ParsedArtifact, Decl, parse_lean_file
from instance_beq.config import InstanceBEqConfig, DEFAULT
from instance_beq.harness.lean_oracle import LeanOracle
from instance_beq.harness.llm import LLMClient
from instance_beq.checks.types import CheckResult


def _find_abstract_theorem(template_path: Optional[str]) -> Optional[Decl]:
    """Parse the Template file and return its main abstract convergence theorem/lemma."""
    if not template_path or not Path(template_path).exists():
        return None
    tart = parse_lean_file(template_path)
    # heuristic: the last lemma/theorem in the template is the headline convergence result
    th = tart.theorems
    return th[-1] if th else None


def synthesize_transfer_proof(
    t_inst: Decl, abstract: Optional[Decl], bridge_instance: Optional[Decl], art: ParsedArtifact
) -> str:
    """Build `example : <T_inst sig> := by apply <abstract> (alg := <bridge>) ...`.

    the implementation: replace the hypothesis-discharge `<...>` with the instance's proof lemmas parsed
    from the artifact (e.g. alg.diff, alg.smooth, alg.convex, step₂). The mock fixtures supply the
    expected verdict so the control flow is testable now.
    """
    abs_name = abstract.name if abstract else "ABSTRACT_THEOREM"
    bridge = bridge_instance.name if bridge_instance else "BRIDGE_INSTANCE"
    return (
        f"-- @mock:transfer_{t_inst.name}\n"
        f"example : {t_inst.signature} := by\n"
        f"  apply {abs_name}\n"
    )


def check_transfer_validity(
    art: ParsedArtifact,
    oracle: LeanOracle,
    cfg: InstanceBEqConfig = DEFAULT,
) -> list[CheckResult]:
    abstract = _find_abstract_theorem(art.abstract_structure)
    # the bridge instance is the one whose target type is the abstract algorithm class
    bridge = art.instances[-1] if art.instances else None
    results: list[CheckResult] = []
    for th in art.theorems:
        t0 = time.time()
        snip = synthesize_transfer_proof(th, abstract, bridge, art)
        res = oracle.check_snippet(snip, imports=art.imports)
        if res.ok and not res.uses_sorry:
            verdict = "faithful"
        elif not res.ok:
            verdict = "unfaithful"
        else:
            verdict = "unknown"
        results.append(CheckResult(
            check="transfer_validity", target=th.name, verdict=verdict, confidence=None,
            evidence={"abstract": abstract.name if abstract else None,
                      "bridge": bridge.name if bridge else None, "oracle_ok": res.ok},
            cost={"lean_calls": 1, "llm_calls": 0, "wall_s": time.time() - t0},
        ))
    return results


def check_statement_faithfulness(
    art: ParsedArtifact,
    llm: LLMClient,
    oracle: LeanOracle,
    cfg: InstanceBEqConfig = DEFAULT,
) -> list[CheckResult]:
    informal = (art.informal or {}).get("problem_statement", "")
    results: list[CheckResult] = []
    for th in art.theorems:
        t0 = time.time()
        prompt = (
            "@mock:stmtfaith_" + th.name + "\n"
            "Back-translate this Lean theorem to a structured claim "
            "(LHS, relation, RHS-rate, hypotheses), then judge whether it faithfully matches the "
            "informal target. Answer strictly as JSON "
            '{"faithful": true|false, "confidence": 0-1, "reason": "..."}.\n'
            f"Informal target: {informal}\n"
            f"Lean theorem: {th.signature}\n"
        )
        raw = llm.complete(prompt)
        faithful, conf, reason = _parse_judge_json(raw)
        verdict = "faithful" if faithful else "unfaithful"
        results.append(CheckResult(
            check="statement_faithfulness", target=th.name, verdict=verdict,
            confidence=conf,
            evidence={"reason": reason, "raw": raw[:500]},
            cost={"lean_calls": 0, "llm_calls": 1, "wall_s": time.time() - t0},
        ))
    return results


def _parse_judge_json(raw: str) -> tuple[bool, Optional[float], str]:
    import json
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return False, None, "unparseable judge output"
    try:
        d = json.loads(m.group(0))
        return bool(d.get("faithful", False)), d.get("confidence"), str(d.get("reason", ""))
    except Exception:
        return False, None, "invalid judge JSON"
