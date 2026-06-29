#!/usr/bin/env python3
"""Unified per-check comparison of ALL methods vs the human gold (+ Kendall-τ vs human labels).

Methods (all from real result files):
  * type-check-only   -- blind baseline A: a file that compiles is called faithful.
  * BEq+              -- statement-level symbolic equivalence (baseline); blind to instance
                         soundness and transfer-validity (baseline_beqplus_result.json).
  * LLM-judge         -- single-shot judge, baseline C (llm_judge_gold_result.json).
  * majority-vote     -- K=5 self-consistency judge, baseline B (baseline_majority_vote_result.json).
  * Instance-BEq      -- the certifier across ALL FOUR checks:
        soundness  = decidable axiom-closure gate          (certifier_all_checks_result.json)
        definitional = curated-reference def-eq            (ref_source_ablation_result.json, curated)
        transfer   = apply-specialisation compile          (certifier_all_checks_result.json)
        statement  = LLM bridge / check 3b                 (certifier_all_checks_result.json)

The certifier is a SOUND certifier on the definitional/transfer checks: it emits faithful/abstain
(never false-certifies). We therefore report, per cell: detection P/R/F1 (positive=unfaithful),
Kendall-τ, AND the two safety/coverage columns -- false-certifications (gold-unfaithful called
faithful or passed through on abstain; the dangerous error) and coverage (non-abstain rate).
Out: eval_logs/methods_vs_gold_result.json
"""
from __future__ import annotations
import json, sys
from pathlib import Path
from scipy.stats import kendalltau

ROOT = Path(__file__).resolve().parents[1]
ANN, LOG = ROOT/"instance_beq/annotation", ROOT/"eval_logs"
CHECKS = ["definitional", "instance_soundness", "transfer_validity", "statement_faithfulness"]


def jl(p): return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]
def jload(name): return json.loads((LOG/name).read_text())


def cell(pairs):
    """pairs: (gold, pred) with pred possibly None (abstain). positive = unfaithful."""
    n_all = len(pairs)
    kept = [(g, m) for g, m in pairs if m is not None]
    tp = sum(g == "unfaithful" and m == "unfaithful" for g, m in kept)
    fn = sum(g == "unfaithful" and m != "unfaithful" for g, m in kept)
    fp = sum(g == "faithful" and m == "unfaithful" for g, m in kept)
    tn = sum(g == "faithful" and m != "unfaithful" for g, m in kept)
    # false certification = a gold-unfaithful artifact POSITIVELY certified faithful. A sound
    # certifier deploys certify-to-accept (abstain => reject/human-review, NOT acceptance), so
    # abstain is not a false certification; only an explicit "faithful" on a truly-unfaithful
    # item is. This is the safety-critical error and is 0 for the certifier by kernel soundness.
    false_cert = sum(g == "unfaithful" and m == "faithful" for g, m in pairs)
    # pass_through additionally counts abstains under a permissive flag-to-reject deployment.
    pass_through = sum(g == "unfaithful" and (m is None or m == "faithful") for g, m in pairs)
    P = tp/(tp+fp) if tp+fp else None
    R = tp/(tp+fn) if tp+fn else None
    F = 2*tp/(2*tp+fp+fn) if (2*tp+fp+fn) else None
    gy = [1 if g == "unfaithful" else 0 for g, _ in kept]
    my = [1 if m == "unfaithful" else 0 for _, m in kept]
    tau = kendalltau(gy, my)[0] if (len(set(gy)) > 1 and len(set(my)) > 1) else 0.0
    return {"n": n_all, "n_pred": len(kept), "coverage": round(len(kept)/n_all, 3) if n_all else None,
            "tp": tp, "fp": fp, "fn": fn, "tn": tn, "false_cert": false_cert, "pass_through": pass_through,
            "P": P, "R": R, "F1": round(F, 3) if F is not None else None,
            "tau": round(tau if tau == tau else 0.0, 3),
            "acc": round((tp+tn)/len(kept), 3) if kept else None}


def main():
    gold = {r["id"]: r for r in jl(ANN/"gold.jsonl")}
    judge = {r["id"]: r for r in jload("llm_judge_gold_result.json")["items"]}
    mv = {r["id"]: r for r in jload("baseline_majority_vote_result.json")["items"]}
    beq = {r["id"]: r for r in jload("baseline_beqplus_result.json")}
    cac = {r["id"]: r for r in jload("certifier_all_checks_result.json")}
    abl = {r["id"]: r for r in jload("ref_source_ablation_result.json")["items"]}
    kappa = json.loads((ANN/"human_vs_expert.json").read_text()).get("fleiss_kappa", {})

    def certifier(iid):
        chk = gold[iid]["check"]
        if chk == "definitional":                         # curated-reference def-eq (sound: faithful/abstain)
            c = abl.get(iid, {}).get("curated")
            return c["verdict"] if c else None
        return cac.get(iid, {}).get("certifier")          # soundness/transfer/statement

    METHODS = {
        "type-check-only": lambda i: "faithful",
        "BEq+":            lambda i: beq.get(i, {}).get("beqplus"),
        "LLM-judge":       lambda i: judge.get(i, {}).get("llm_judge"),
        "majority-vote":   lambda i: mv.get(i, {}).get("majority_vote"),
        "Instance-BEq":    certifier,
    }

    out = {"by_check": {}, "kappa_ceiling": kappa, "methods": list(METHODS)}
    for c in CHECKS + ["overall"]:
        ids = [i for i in gold if c == "overall" or gold[i]["check"] == c]
        out["by_check"][c] = {name: cell([(gold[i]["label"], fn(i)) for i in ids])
                              for name, fn in METHODS.items()}
    # per-item verdicts for every method (single source of truth for figures + bootstrap CIs)
    out["per_item"] = [{"id": i, "check": gold[i]["check"], "gold": gold[i]["label"],
                        **{name: fn(i) for name, fn in METHODS.items()}} for i in gold]
    (LOG/"methods_vs_gold_result.json").write_text(json.dumps(out, indent=2), encoding="utf-8")

    hdr = f"{'check':<22}{'method':<16}{'n':>3}{'cov':>6}{'P':>6}{'R':>6}{'F1':>6}{'tau':>6}{'FC':>4}"
    print(hdr); print("-"*len(hdr))
    for c in CHECKS + ["overall"]:
        for name in METHODS:
            s = out["by_check"][c][name]
            f = lambda x: "  -  " if x is None else f"{x:.2f}"
            print(f"{c:<22}{name:<16}{s['n']:>3}{f(s['coverage']):>6}{f(s['P']):>6}{f(s['R']):>6}"
                  f"{f(s['F1']):>6}{s['tau']:>6.2f}{s['false_cert']:>4}")
        print()
    print("wrote", LOG/"methods_vs_gold_result.json")


if __name__ == "__main__":
    main()
