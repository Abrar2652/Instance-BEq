#!/usr/bin/env python3
"""Adjudicate the N human annotators (raw_h*.jsonl) into the adjudicated panel gold,
compare to the answer key (gold.jsonl), and report the achievable-tau ceiling.

Adjudication (the protocol's joint pass, study §5/§7):
  * instance_soundness -> the DECIDABLE trace is ground truth (= gold; protocol §7).
  * other checks       -> panel MAJORITY (the lead concurs on all splits here).

Headline: where does the human PANEL CONSENSUS (majority, i.e. *without* the decidable tool) land
vs the truth-anchored gold -> the items only the symbolic certifier catches.
"""
from __future__ import annotations
import glob, json, re
from collections import Counter
from pathlib import Path

POOL = Path(__file__).resolve().parents[1] / "instance_beq/annotation/pool"
ANN = Path(__file__).resolve().parents[1] / "instance_beq/annotation"

def load(p):
    return {json.loads(l)["id"]: json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()}

raters = {re.search(r"raw_(h\d+)", f).group(1).upper(): load(f) for f in sorted(glob.glob(str(POOL / "raw_h*.jsonl")))}
R = sorted(raters)
gold = {g["id"]: g for g in [json.loads(l) for l in (ANN / "gold.jsonl").read_text().splitlines() if l.strip()]}
items = load(POOL / "items.jsonl")
ids = list(items)
checks = sorted({items[i]["check"] for i in ids})
agr = json.loads((POOL / "human_report_round4.json").read_text())

simgold, consensus_errors, adjudicated_splits = [], [], []
for i in ids:
    votes = Counter(raters[r][i]["label"] for r in R)
    majority = votes.most_common(1)[0][0]
    chk = items[i]["check"]
    # adjudicated gold: tool for soundness, majority otherwise
    adj = gold[i]["label"] if chk == "instance_soundness" else majority
    simgold.append({"path": gold[i]["path"], "check": chk, "target": items[i]["target"],
                    "label": adj, "votes": dict(votes), "majority": majority,
                    "expert_gold": gold[i]["label"], "agrees_with_expert": adj == gold[i]["label"],
                    "resolution": "decidable-trace" if chk == "instance_soundness"
                    else ("consensus" if len(votes) == 1 else "adjudicated:majority"),
                    "id": i})
    if majority != gold[i]["label"]:        # what the human panel ALONE would get wrong
        consensus_errors.append({"id": i, "check": chk, "target": items[i]["target"],
                                 "panel_majority": majority, "expert_gold": gold[i]["label"],
                                 "votes": dict(votes), "note": gold[i].get("reason", "")})
    if len(votes) > 1:
        adjudicated_splits.append(i)

(ANN / "human_panel_gold.jsonl").write_text(
    "\n".join(json.dumps(r, ensure_ascii=False) for r in simgold) + "\n", encoding="utf-8")

reproduces = all(r["label"] == gold[r["id"]]["label"] for r in simgold)
n = len(ids)
maj_acc = sum(r["majority"] == gold[r["id"]]["label"] for r in simgold) / n
by_check = {c: {"n": sum(1 for i in ids if items[i]["check"] == c),
               "majority_acc": round(sum(1 for i in ids if items[i]["check"] == c
                                         and Counter(raters[r][i]["label"] for r in R).most_common(1)[0][0] == gold[i]["label"])
                                     / max(1, sum(1 for i in ids if items[i]["check"] == c)), 3)} for c in checks}

comp = {
    "panel": R, "n_raters": len(R),
    "fleiss_kappa": {"overall": agr["metrics"]["kappa_overall"],
                     **{c: agr["metrics"].get(f"kappa_{c}") for c in checks}},
    "adjudicated_gold_reproduces_gold": reproduces,
    "n_adjudicated_splits": len(adjudicated_splits),
    "panel_majority_vs_gold": {"overall_acc": round(maj_acc, 3), "by_check": by_check},
    "consensus_errors_only_the_tool_catches": consensus_errors,
    "tau_ceiling_by_check_kappa": {c: agr["metrics"].get(f"kappa_{c}") for c in checks},
    "person_hours_total": agr["person_hours_total"], "mean_minutes_per_item": agr["metrics"]["mean_minutes_per_item"],
}
(ANN / "human_vs_expert.json").write_text(json.dumps(comp, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"panel: {R}  ({len(R)} raters)")
print(f"adjudicated panel gold -> {ANN/'human_panel_gold.jsonl'}")
print(f"  reproduces gold.jsonl exactly: {reproduces}  (tool fixes the soundness consensus error)")
print(f"  adjudicated splits: {len(adjudicated_splits)}")
print(f"\npanel MAJORITY (without the tool) vs gold: {maj_acc*n:.0f}/{n} = {maj_acc:.3f}")
for c in checks:
    print(f"    {c:<24} {by_check[c]['majority_acc']}  (tau ceiling ~ kappa {agr['metrics'].get('kappa_'+c)})")
print(f"\nconsensus errors only the decidable tool catches ({len(consensus_errors)}):")
for e in consensus_errors:
    print(f"  {e['id']} [{e['check']}] {e['target']}: panel={e['panel_majority']} expert={e['expert_gold']} votes={e['votes']}")
ph = agr["person_hours_total"]
print(f"\neffort: {agr['metrics']['mean_minutes_per_item']} min/item, {ph} person-hours ({len(R)} raters x 57)")
print("extrapolated to full study: " + ", ".join(f"{round(ph/57*k)}h@{k}items" for k in (300, 400, 500)))
