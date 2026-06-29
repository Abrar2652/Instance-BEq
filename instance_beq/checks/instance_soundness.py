"""Check 2 — Instance soundness (the headline check).

An `instance I : S ... where ...` type-checks regardless of whether its condition fields are
proven for real or discharged by `sorry`. SITA *claims* its instances "certify that the necessary
structural conditions are satisfied"; step-6 harmless-fixing can leave a field sorry-tainted. Such
an instance compiles and looks like a certificate but certifies nothing — a HOLLOW instance.

This check: for each instance, append a `#faithful_axioms` query for the instance (and for each
named proof term its fields reference) and ask the oracle whether the axiom closure is sorry-free
and within the allowed-axiom set.

Verdict:
- "faithful"   : every condition field's proof closure is sorry-free and axiom-clean
- "unfaithful" : at least one field is sorry-tainted (or uses a disallowed axiom)
- "unknown"    : the oracle could not resolve (compile error unrelated to soundness)
"""
from __future__ import annotations

import re
import time

from instance_beq.artifacts import ParsedArtifact, Decl
from instance_beq.config import InstanceBEqConfig, DEFAULT, SORRY_TOKENS
from instance_beq.harness.lean_oracle import LeanOracle, OracleResult
from instance_beq.checks.types import CheckResult


# Field names that are raw DATA (not proof obligations) and so are exempt from the sorry check.
# Heuristic over the structures we see (x, t, l are data; update/hl/step are proof obligations).
_DATA_FIELDS = {"x", "t", "l", "x0", "x₀", "initial", "y", "z"}


def _axiom_query(decl_name: str, art: ParsedArtifact) -> str:
    """Build a snippet that imports the artifact's module and prints the axiom closure.

    In real mode the artifact file is already a module under Optlib; we import it by path-derived
    module name. For robustness in this scaffold we instead *re-include* the artifact text plus the
    query, relying on the oracle's scratch compile.
    """
    return f"#faithful_axioms {decl_name}\n"


def _field_proof_targets(inst: Decl) -> list[str]:
    """Return the proof terms a where-block's condition fields reference (e.g. `self.update_cor`).

    For `update := self.update_cor` we want to trace `update_cor`. For inline proofs we trace the
    instance itself.
    """
    targets: list[str] = []
    for line in inst.body.splitlines():
        s = line.strip()
        m = re.match(r"([A-Za-z_][A-Za-z0-9_'!?]*)\s*:=\s*(.+)$", s)
        if not m:
            continue
        fname, rhs = m.group(1), m.group(2).strip()
        if fname in _DATA_FIELDS:
            continue
        # extract a referenced identifier of the form `xxx.yyy` or `yyy`
        ref = re.search(r"([A-Za-z_][A-Za-z0-9_'.]*)", rhs)
        if ref:
            targets.append(ref.group(1).split(".")[-1])
    return targets


def check_instance_soundness(
    art: ParsedArtifact,
    oracle: LeanOracle,
    cfg: InstanceBEqConfig = DEFAULT,
) -> list[CheckResult]:
    results: list[CheckResult] = []
    for inst in art.instances:
        t0 = time.time()
        lean_calls = 0
        tainted: dict[str, list[str]] = {}

        # Query the instance's own axiom closure first (catches inline sorry too).
        targets = _field_proof_targets(inst)
        query = "\n".join(
            [f"-- @mock:soundness_{inst.name}"] +
            [art_module_header(art)] +
            [_axiom_query(inst.name, art)] +
            [_axiom_query(tgt, art) for tgt in targets]
        )
        res: OracleResult = oracle.check_snippet(query, imports=art.imports)
        lean_calls += 1

        # Examine axiom sets gathered by the oracle. A field is tainted if its closure contains a
        # sorry token or any axiom outside the allowed set.
        for decl, axs in res.axioms.items():
            bad = [a for a in axs
                   if any(tok in a for tok in SORRY_TOKENS) or a not in cfg.allowed_axioms]
            if bad:
                tainted[decl] = bad

        if res.uses_sorry or tainted:
            verdict = "unfaithful"
        elif not res.ok and not res.axioms:
            verdict = "unknown"
        else:
            verdict = "faithful"

        results.append(CheckResult(
            check="instance_soundness",
            target=inst.name,
            verdict=verdict,
            confidence=None,  # purely symbolic
            evidence={"tainted": tainted, "uses_sorry": res.uses_sorry,
                      "axioms": res.axioms, "oracle_ok": res.ok},
            cost={"lean_calls": lean_calls, "llm_calls": 0, "wall_s": time.time() - t0},
        ))
    return results


def art_module_header(art: ParsedArtifact) -> str:
    """In real mode the artifact is its own module; importing it makes its decls queryable.

    The eval driver passes the artifact's module import; in this scaffold we keep a hook so the
    real implementation can `import <ModulePath>` instead of re-including the file text.
    """
    return ""  # eval/run_certifier injects the proper import; mock fixtures embed @mock tags
