#!/usr/bin/env python3
"""BEq+ baseline (statement-level symbolic equivalence, Liu et al.) evaluated on our gold.

BEq+ checks whether a generated *statement* is symbolically equivalent to a reference (back-
translated) statement; it has NO notion of `instance` soundness and NO structural transfer
(apply-validity) check. We implement it faithfully as:
  * definitional   -> symbolic equality (curated-reference certifier verdict; LLM-judge fallback
                       when symbolic equality is not proved) -- this is the def-level analogue.
  * statement      -> the LLM/symbolic statement-equivalence verdict (= our 3b bridge / LLM-judge).
  * instance_sound -> BLIND: BEq+ never inspects instance condition fields, so a hollow instance
                       that type-checks is accepted -> predicts faithful.
  * transfer_valid -> BLIND: BEq+ has no apply-specialization check -> predicts faithful.

So BEq+ matches us on the statement-level checks but has recall 0 on instance soundness and on
transfer validity -- exactly the def/instance/transfer granularity gap Instance-BEq fills. This
baseline is a pure recombination of already-computed per-item verdicts (no new model calls).
Out: eval_logs/baseline_beqplus_result.json
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANN = ROOT/"instance_beq/annotation"
LOG = ROOT/"eval_logs"


def main():
    gold = {json.loads(l)["id"]: json.loads(l) for l in (ANN/"gold.jsonl").read_text().splitlines() if l.strip()}
    judge = {r["id"]: r for r in json.loads((LOG/"llm_judge_gold_result.json").read_text())["items"]}
    abl = json.loads((LOG/"ref_source_ablation_result.json").read_text()) if (LOG/"ref_source_ablation_result.json").exists() else {"items": []}
    curated = {r["id"]: r for r in abl["items"]}

    rows = []
    for iid, g in gold.items():
        chk = g["check"]
        if chk == "instance_soundness" or chk == "transfer_validity":
            v = "faithful"                       # BLIND — accepts anything that type-checks
        elif chk == "definitional":
            cr = curated.get(iid, {}).get("curated")
            if cr and cr.get("verdict") == "faithful":
                v = "faithful"                   # symbolic equality proved
            else:
                v = judge.get(iid, {}).get("llm_judge", "unknown")  # LLM-equivalence fallback
        else:  # statement_faithfulness
            v = judge.get(iid, {}).get("llm_judge", "unknown")
        rows.append({"id": iid, "check": chk, "gold": g["label"], "beqplus": v,
                     "blind": chk in ("instance_soundness", "transfer_validity")})

    (LOG/"baseline_beqplus_result.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")

    import collections
    by = collections.defaultdict(collections.Counter)
    for r in rows:
        by[r["check"]][(r["gold"], r["beqplus"])] += 1
    print("BEq+ baseline vs gold (recall on unfaithful per check):")
    for chk, c in by.items():
        tp = c[("unfaithful", "unfaithful")]; fn = sum(v for (gg, p), v in c.items() if gg == "unfaithful" and p != "unfaithful")
        R = tp/(tp+fn) if (tp+fn) else None
        print(f"  {chk:<22} recall_unfaithful={tp}/{tp+fn}" + (f" = {R:.2f}" if R is not None else "") +
              ("   [BLIND]" if any(r['check'] == chk and r['blind'] for r in rows) else ""))
    print("wrote", LOG/"baseline_beqplus_result.json")


if __name__ == "__main__":
    main()
