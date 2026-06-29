#!/usr/bin/env python3
"""Majority-voting baseline (B) — SITA's own self-consistency principle applied to faithfulness.
SITA selects among type-checking candidates by majority vote; it carries no faithfulness check
beyond type-checking. The strongest voting-based faithfulness DETECTOR is self-consistency over
the judge: sample K independent faithfulness judgments (temperature>0) and take the majority.
This tests whether voting closes the LLM-judge gap to the formal certifier (it does not, on the
soundness check, because the model cannot trace `sorry` through the axiom closure).
Out: eval_logs/baseline_majority_vote_result.json
"""
from __future__ import annotations
import json, re, sys, time, collections
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from instance_beq.config import InstanceBEqConfig
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
ANN = ROOT/"instance_beq/annotation"
LOG = ROOT/"eval_logs"
cfg = InstanceBEqConfig(mock=False)
ext = json.loads(Path(cfg.api_config_path).read_text())
client = OpenAI(api_key=ext["api_key"], base_url=ext["base_url"])
MODEL = "qwen2.5-7b-instruct"
K = 5

# reuse the exact judge prompts so B is the K-vote version of baseline C (apples-to-apples)
from importlib import import_module
ljg = import_module("scripts.llm_judge_gold") if (ROOT/"scripts/__init__.py").exists() else None
if ljg is None:
    import importlib.util
    spec = importlib.util.spec_from_file_location("ljg", ROOT/"scripts/llm_judge_gold.py")
    ljg = importlib.util.module_from_spec(spec); spec.loader.exec_module(ljg)
ASK = ljg.ASK


def vote_once(it, temp):
    p = (f"You are auditing a Lean 4 formalization (check: {it['check']}).\n\n"
         f"{ASK[it['check']].format(target=it['target'])}\n\n"
         f"INFORMAL PROBLEM:\n{str(it.get('informal',''))[:1500]}\n\n"
         + (f"ABSTRACT THEOREM:\n{str(it.get('abstract_theorem',''))[:1200]}\n\n"
            if it['check'] in ('transfer_validity', 'statement_faithfulness') else "")
         + f"LEAN SOURCE:\n```lean\n{str(it.get('lean_source',''))[:6000]}\n```\n\n"
         "Reply on line 1 with exactly FAITHFUL or UNFAITHFUL.")
    r = client.chat.completions.create(model=MODEL, temperature=temp, max_tokens=40,
                                       messages=[{"role": "user", "content": p}])
    up = (r.choices[0].message.content or "").strip().upper().split("\n")[0]
    return "unfaithful" if "UNFAITHFUL" in up else ("faithful" if "FAITHFUL" in up else "unknown")


def main():
    items = {json.loads(l)["id"]: json.loads(l) for l in (ANN/"pool/items.jsonl").read_text().splitlines() if l.strip()}
    gold = {json.loads(l)["id"]: json.loads(l) for l in (ANN/"gold.jsonl").read_text().splitlines() if l.strip()}
    rows, t0 = [], time.time()
    for i, (iid, it) in enumerate(items.items(), 1):
        votes = [vote_once(it, 0.7) for _ in range(K)]
        tally = collections.Counter(v for v in votes if v != "unknown")
        v = tally.most_common(1)[0][0] if tally else "unknown"
        agree = tally.most_common(1)[0][1]/K if tally else 0.0
        g = gold[iid]["label"]
        rows.append({"id": iid, "check": it["check"], "gold": g, "majority_vote": v,
                     "votes": votes, "agreement": round(agree, 2), "correct": v == g})
        print(f"  [{i:>2}/57] {iid} {it['check'][:5]:<5} gold={g:<11} vote={v:<11} {votes} {'OK' if v==g else 'X'}", flush=True)
    out = {"model": MODEL, "K": K, "n": len(rows), "wall_s": round(time.time()-t0, 1), "items": rows}
    (LOG/"baseline_majority_vote_result.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    acc = sum(r["correct"] for r in rows)/len(rows)
    print(f"\nmajority-vote (K={K}) overall acc vs gold: {acc:.3f}  ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
