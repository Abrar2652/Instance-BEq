#!/usr/bin/env python3
"""Tactic-ensemble SIZE ablation for check 1 (gap #6b). Question: does check-1 coverage actually
need the tactic ensemble, or would a single tactic do? We take one clean gold def
(LeastSquares_problem.f in GD_example) and a LADDER of references that are all MATHEMATICALLY EQUAL
to the true objective but written in forms that need progressively stronger tactics to discharge,
plus the same corruptions used elsewhere (which must stay rejected at every ensemble size).
We grow the ensemble tactic-by-tactic (ordered weakest->strongest) and report coverage@k on the
equivalents and false-certifications@k on the corruptions (must be 0 at every k -- kernel-sound).
Out: eval_logs/tactic_size_sweep_result.json
"""
from __future__ import annotations
import json, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from instance_beq.config import InstanceBEqConfig
from instance_beq.harness.lean_oracle import LeanOracle

cfg = InstanceBEqConfig(mock=False)
oracle = LeanOracle(cfg)
LOG = Path(__file__).resolve().parents[1] / "eval_logs"
ANN = Path(__file__).resolve().parents[1] / "instance_beq/annotation"
T = "LeastSquares_problem.f"

# ordered weakest -> strongest; coverage should be non-decreasing in k
ENSEMBLE = [f"rfl", f"unfold {T}; rfl", f"unfold {T}; simp", f"unfold {T}; ring",
            f"unfold {T}; funext; ring_nf"]

# references EQUAL to ½‖Ax-b‖² in increasingly hard-to-normalise forms
EQUIV = [
    ("identical",  "1 / 2 * ‖A *ᵥ x - b‖₂ ^ 2"),
    ("div-form",   "‖A *ᵥ x - b‖₂ ^ 2 / 2"),
    ("inv-form",   "2⁻¹ * ‖A *ᵥ x - b‖₂ ^ 2"),
    ("factored",   "(‖A *ᵥ x - b‖₂ ^ 2) * (1 / 2)"),
    ("sub-form",   "‖A *ᵥ x - b‖₂ ^ 2 - ‖A *ᵥ x - b‖₂ ^ 2 / 2"),
]
CORRUPT = [
    ("const-1/3",  "1 / 3 * ‖A *ᵥ x - b‖₂ ^ 2"),
    ("missing-½",  "‖A *ᵥ x - b‖₂ ^ 2"),
    ("no-square",  "1 / 2 * ‖A *ᵥ x - b‖₂"),
    ("sign-flip",  "1 / 2 * ‖A *ᵥ x + b‖₂ ^ 2"),
]


def win_index(src, rhs):
    for i, tac in enumerate(ENSEMBLE):
        ex = (f"example (self : LeastSquares_problem A b) (x : EuclideanSpace ℝ (Fin n)) :\n"
              f"    {T} self x = {rhs} := by\n  {tac}")
        anchor = re.search(rf"def\s+{re.escape(T)}\b.*?fun x ↦[^\n]*\n", src, re.DOTALL)
        probe = src[:anchor.end()] + "\n" + ex + "\n" + src[anchor.end():]
        r = oracle.check_snippet(probe)
        if r.ok and not r.errors:
            return i
    return None


def main():
    src = (cfg.lean_cwd / "Optlib/Autoformalization/Example/GD_example.lean").read_text(encoding="utf-8")
    t0 = time.time()
    eq = [{"label": n, "win": win_index(src, r)} for n, r in EQUIV]
    co = [{"label": n, "win": win_index(src, r)} for n, r in CORRUPT]
    K = len(ENSEMBLE)
    cov_at_k = [sum(1 for e in eq if e["win"] is not None and e["win"] <= k) for k in range(K)]
    fc_at_k = [sum(1 for c in co if c["win"] is not None and c["win"] <= k) for k in range(K)]
    res = {"ensemble": ENSEMBLE, "n_equiv": len(EQUIV), "n_corrupt": len(CORRUPT),
           "equiv": eq, "corrupt": co, "coverage_at_k": cov_at_k, "false_cert_at_k": fc_at_k,
           "seconds": round(time.time()-t0)}
    (LOG/"tactic_size_sweep_result.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print("ensemble size k :", list(range(1, K+1)))
    print("coverage@k      :", cov_at_k, f"/ {len(EQUIV)} equivalents")
    print("false-cert@k    :", fc_at_k, "(must be all 0)")
    for e in eq:
        print(f"  equiv {e['label']:<12} first proved by tactic #{(e['win']+1) if e['win'] is not None else '-'}")
    print("wrote", LOG/"tactic_size_sweep_result.json", f"[{res['seconds']}s]")


if __name__ == "__main__":
    main()
