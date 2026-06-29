"""Check 1 — Definitional faithfulness.

Does the generated `def D_gen` actually encode the informal object? We obtain a reference
definition `D_ref` (independently of D_gen) and discharge `D_gen = D_ref` (or extensional
equality) via a tactic ensemble. First tactic that closes the goal wins.

Reference-def source is configurable (cfg.refdef_source):
- "retrieval": pull a canonical characterization from the Optlib theorem DB and instantiate it.
- "llm":       ask the LLM to formalize ONLY the objective from the informal spec (no sight of
               D_gen), maximizing independence.
- "property":  assert known properties instead of a reference def (secondary signal).

This module ships a working control flow that runs in mock mode. The retrieval/LLM reference-def
generation and the Lean equality discharge call the harness, which mock mode intercepts. the implementation
Code fleshes out `build_reference_def` option (a) against the real theorem DB on the cluster.
"""
from __future__ import annotations

import time
from typing import Optional

from instance_beq.artifacts import ParsedArtifact, Decl
from instance_beq.config import InstanceBEqConfig, DEFAULT
from instance_beq.harness.lean_oracle import LeanOracle
from instance_beq.harness.llm import LLMClient
from instance_beq.checks.types import CheckResult


def build_reference_def(
    target: Decl,
    art: ParsedArtifact,
    cfg: InstanceBEqConfig,
    llm: LLMClient,
) -> Optional[str]:
    """Return Lean source for a reference def `D_ref` of the same object, or None if unavailable.

    Mock mode: the LLM/oracle fixtures supply the reference; here we construct the prompt/snippet
    deterministically so the mock key is stable.
    """
    if cfg.refdef_source == "llm":
        informal = (art.informal or {}).get("problem_statement", "")
        prompt = (
            "@mock:refdef_" + target.name + "\n"
            "Formalize ONLY the following objective as a single Lean 4 `def` named "
            f"`{target.name}_ref`, matching the style of Optlib. Do not prove anything.\n"
            f"Objective (informal): {informal}\n"
        )
        return LLMClient.extract_lean(llm.complete(prompt))
    if cfg.refdef_source == "retrieval":
        # the implementation: instantiate the canonical Optlib characterization here. For the scaffold we
        # signal "retrieval not yet wired" by returning None unless a mock fixture provides it.
        return None
    if cfg.refdef_source == "property":
        return None  # property-based path handled by check_definitional directly
    return None


def _equality_snippet(gen: Decl, ref_src: str, art: ParsedArtifact, tactic: str) -> str:
    lhs, rhs = gen.name, gen.name + "_ref"
    tac = tactic.format(lhs=lhs, rhs=rhs)
    return (
        f"-- @mock:defeq_{gen.name}_{_tac_id(tactic)}\n"
        f"{ref_src}\n"
        f"example : (@{lhs}) = (@{rhs}) := by {tac}\n"
    )


def _tac_id(t: str) -> str:
    """Stable, collision-free short id for a tactic string.

    We index by the tactic's position-independent content. Truncating an alnum-squash collides
    (`unfold ...; ring` vs `unfold ...; ext x; ring_nf; simp` both -> 'unfoldlhsrhs'), so we append
    a short hash of the full tactic to guarantee uniqueness while staying readable.
    """
    import hashlib
    base = "".join(c for c in t if c.isalnum())[:10]
    h = hashlib.sha1(t.encode("utf-8")).hexdigest()[:6]
    return f"{base}_{h}"


def check_definitional(
    art: ParsedArtifact,
    oracle: LeanOracle,
    llm: LLMClient,
    cfg: InstanceBEqConfig = DEFAULT,
    only: Optional[list[str]] = None,
) -> list[CheckResult]:
    results: list[CheckResult] = []
    for d in art.defs:
        if only and d.name not in only:
            continue
        t0 = time.time()
        lean_calls = llm_calls = 0

        ref_src = build_reference_def(d, art, cfg, llm)
        llm_calls += 1 if cfg.refdef_source == "llm" else 0
        if ref_src is None:
            results.append(CheckResult(
                check="definitional", target=d.name, verdict="unknown",
                confidence=None,
                evidence={"reason": f"no reference def (source={cfg.refdef_source})"},
                cost={"lean_calls": lean_calls, "llm_calls": llm_calls,
                      "wall_s": time.time() - t0},
            ))
            continue

        verdict = "unknown"
        winning_tactic = None
        for tactic in cfg.tactic_ensemble:
            snip = _equality_snippet(d, ref_src, art, tactic)
            res = oracle.check_snippet(snip, imports=art.imports)
            lean_calls += 1
            if res.ok and not res.uses_sorry:
                verdict = "faithful"
                winning_tactic = tactic
                break
        else:
            # ensemble exhausted without closing the goal
            verdict = "unfaithful" if not cfg.allow_unknown else "unknown"

        results.append(CheckResult(
            check="definitional", target=d.name, verdict=verdict, confidence=None,
            evidence={"reference_source": cfg.refdef_source, "winning_tactic": winning_tactic},
            cost={"lean_calls": lean_calls, "llm_calls": llm_calls, "wall_s": time.time() - t0},
        ))
    return results
