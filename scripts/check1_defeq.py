#!/usr/bin/env python3
"""Controlled benchmark for check 1 (definitional faithfulness) on real Lean.

Check 1 discharges `D_gen = D_ref` via a tactic ensemble. Because Lean's kernel is sound, a
PROVED equality is genuinely an equality -> check 1 can never falsely certify (precision = 1 by
construction). The open question is RECALL: does the ensemble prove true (equivalent) references,
and does it correctly reject corrupted ones?

We take a gold def and a set of reference RHS expressions with known ground truth:
  * EQUIVALENT references (mathematically equal, written differently)  -> should PROVE  (faithful)
  * CORRUPTED references (wrong constant / missing term / sign flip)   -> should FAIL   (unfaithful)
and report coverage (recall on equivalents) and rejection (no false certify on corruptions).

Run:  python scripts/check1_defeq.py
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from instance_beq.config import InstanceBEqConfig
from instance_beq.harness.lean_oracle import LeanOracle

PREAMBLE = (
    "import Optlib.Autoformalization.Example.GD_example\n"
    "noncomputable section C1\n"
    "open Set Real Matrix Finset Filter Bornology BigOperators Topology\n"
    'local notation "‖" x "‖₂" => @Norm.norm _ (PiLp.instNorm 2 fun _ ↦ ℝ) x\n'
    "variable {A : Matrix (Fin m) (Fin n) ℝ} {b : Fin m → ℝ}\n"
)
BINDERS = "(self : LeastSquares_problem A b) (x : EuclideanSpace ℝ (Fin n))"
LHS = "LeastSquares_problem.f self x"          # gold: 1/2 * ‖A *ᵥ x - b‖₂ ^ 2
DEFN = "LeastSquares_problem.f"

# (label, reference RHS, ground-truth)
CASES = [
    ("identical",        "1 / 2 * ‖A *ᵥ x - b‖₂ ^ 2",       "faithful"),
    ("div-form",         "‖A *ᵥ x - b‖₂ ^ 2 / 2",            "faithful"),
    ("inv-form",         "2⁻¹ * ‖A *ᵥ x - b‖₂ ^ 2",          "faithful"),
    ("factored",         "(‖A *ᵥ x - b‖₂ ^ 2) * (1/2)",      "faithful"),
    ("wrong-const-1/3",  "1 / 3 * ‖A *ᵥ x - b‖₂ ^ 2",        "unfaithful"),
    ("missing-half",     "‖A *ᵥ x - b‖₂ ^ 2",                "unfaithful"),
    ("no-square",        "1 / 2 * ‖A *ᵥ x - b‖₂",            "unfaithful"),
    ("sign-flip",        "1 / 2 * ‖A *ᵥ x + b‖₂ ^ 2",        "unfaithful"),
]
TACTICS = [
    "rfl",
    f"unfold {DEFN}; ring",
    f"simp only [{DEFN}]; ring",
    f"unfold {DEFN}; ring_nf",
]


def prove(oracle, ref, tactic):
    src = (PREAMBLE +
           f"example {BINDERS} : {LHS} = {ref} := by {tactic}\n" +
           "end C1\n")
    res = oracle.check_snippet(src)
    return res.ok and len(res.errors) == 0


def main():
    cfg = InstanceBEqConfig(mock=False)
    oracle = LeanOracle(cfg)
    rows, t0 = [], time.time()
    for label, ref, truth in CASES:
        proved, win = False, None
        for tac in TACTICS:
            if prove(oracle, ref, tac):
                proved, win = True, tac
                break
        verdict = "faithful" if proved else "unfaithful"   # exhausted ensemble => reject
        ok = (verdict == truth)
        rows.append({"label": label, "ref": ref, "truth": truth, "verdict": verdict,
                     "winning_tactic": win, "correct": ok})
        mark = "✓" if ok else "✗"
        print(f"  {mark} {label:<16} truth={truth:<11} -> {verdict:<11} "
              f"{'['+win+']' if win else ''}")

    faith = [r for r in rows if r["truth"] == "faithful"]
    corr  = [r for r in rows if r["truth"] == "unfaithful"]
    recall = sum(r["verdict"] == "faithful" for r in faith) / max(1, len(faith))
    false_cert = sum(r["verdict"] == "faithful" for r in corr)   # must be 0 (kernel-sound)
    print("-" * 60)
    print(f"equivalent refs proved (RECALL)   : {sum(r['verdict']=='faithful' for r in faith)}/{len(faith)} = {recall:.2f}")
    print(f"corrupted refs falsely certified  : {false_cert}/{len(corr)}  (must be 0 — kernel-sound)")
    print(f"wall: {time.time()-t0:.0f}s")
    out = Path(__file__).resolve().parents[1] / "eval_logs" / "check1_defeq_result.json"
    out.write_text(json.dumps({"rows": rows, "recall_on_equivalents": recall,
                               "false_certifications": false_cert}, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    print("wrote", out)
    sys.exit(0 if false_cert == 0 else 1)


if __name__ == "__main__":
    main()
