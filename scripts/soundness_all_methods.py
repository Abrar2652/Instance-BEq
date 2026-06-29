#!/usr/bin/env python3
"""Assemble a single-corpus, multi-method soundness comparison from EXISTING real result files.

No re-running, no invented numbers: every per-item verdict is read from a logged real run.
  * certifier (check 2)  : fault_injection_result.json (4 sound originals + 19 plants)
                           + certify_gold_result.json   (ADMM/BCD originals, transitively hollow)
  * type-check-only (A)  : "faithful" for every item — all 25 compile with 0 errors
                           (measured: baselineA_typechecks=True for the 23; ADMM/BCD built rc=0).
  * LLM-judge (C)        : llm_judge_soundness_result.json (per-item verdicts).
Corpus = the 25 instances of the LLM-judge run (6 gold originals + 19 planted-hollow variants).

Out: eval_logs/soundness_methods_result.json  (per-item table + per-method P/R/F1, HOLLOW=positive).
"""
from __future__ import annotations
import json
from pathlib import Path

LOG = Path(__file__).resolve().parents[1] / "eval_logs"


def load(n):
    return json.loads((LOG / n).read_text(encoding="utf-8"))


def prf(items, pred_key):
    tp = sum(it["truth"] == "hollow" and it[pred_key] == "hollow" for it in items)
    fn = sum(it["truth"] == "hollow" and it[pred_key] != "hollow" for it in items)
    fp = sum(it["truth"] == "sound" and it[pred_key] == "hollow" for it in items)
    tn = sum(it["truth"] == "sound" and it[pred_key] != "hollow" for it in items)
    P = tp / (tp + fp) if tp + fp else None      # None = undefined (no positives predicted)
    R = tp / (tp + fn) if tp + fn else None
    F = (2 * P * R / (P + R)) if (P and R) else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "P": P, "R": R, "F1": F}


def main():
    judge = load("llm_judge_soundness_result.json")["items"]          # canonical 25-item corpus
    fault = {(it["family"], it["case"]): it for it in load("fault_injection_result.json")["items"]}
    gold = {r["family"]: r["gold"]["verdict"] for r in load("certify_gold_result.json")}
    # map gold verdict words -> sound/hollow
    g2 = {"faithful": "sound", "unfaithful": "hollow"}

    items = []
    for it in judge:
        fam, case = it["family"], it["case"]
        # certifier verdict (exact), sourced from the real runs
        if (fam, case) in fault:
            cert = fault[(fam, case)]["certifier"]            # 'sound' | 'hollow'
        elif case == "original":
            cert = g2[gold[fam]]                              # ADMM/BCD originals
        else:
            cert = None
        items.append({
            "family": fam, "case": case, "truth": it["truth"],
            "certifier": cert,
            "typecheck": "sound",        # baseline A never flags: every file compiles (0 errors)
            "llm_judge": it["llm_judge"],
        })

    # integrity: certifier must equal ground truth on every item (it is exact)
    bad = [it for it in items if it["certifier"] != it["truth"]]
    assert not bad, f"certifier disagreed with truth (should be impossible): {bad}"

    out = {
        "corpus_size": len(items),
        "n_sound": sum(it["truth"] == "sound" for it in items),
        "n_hollow": sum(it["truth"] == "hollow" for it in items),
        "items": items,
        "methods": {
            "Instance-BEq": prf(items, "certifier"),
            "type-check-only": prf(items, "typecheck"),
            "LLM-judge": prf(items, "llm_judge"),
        },
    }
    (LOG / "soundness_methods_result.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"corpus={out['corpus_size']} (sound={out['n_sound']}, hollow={out['n_hollow']})")
    for m, s in out["methods"].items():
        P = "undef" if s["P"] is None else f"{s['P']:.3f}"
        print(f"  {m:<16} TP{s['tp']:>3} FP{s['fp']:>3} FN{s['fn']:>3} TN{s['tn']:>3}  "
              f"P={P} R={s['R'] if s['R'] is None else round(s['R'],3)} F1={s['F1']:.3f}")
    print("wrote", LOG / "soundness_methods_result.json")


if __name__ == "__main__":
    main()
