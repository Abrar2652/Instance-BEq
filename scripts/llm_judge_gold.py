#!/usr/bin/env python3
"""LLM-judge (baseline C) over the full 57-item gold pool, all four checks, with a confidence score.
Feeds: per-check P/R/F1 vs human gold, Kendall-τ vs human, and the 3b calibration/ECE figure.
Source pool: instance_beq/annotation/pool/items.jsonl (blinded); labels: gold.jsonl.
Out: eval_logs/llm_judge_gold_result.json
"""
from __future__ import annotations
import json, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from instance_beq.config import InstanceBEqConfig
from openai import OpenAI

ANN = Path(__file__).resolve().parents[1] / "instance_beq/annotation"
cfg = InstanceBEqConfig(mock=False)
ext = json.loads(Path(cfg.api_config_path).read_text())
client = OpenAI(api_key=ext["api_key"], base_url=ext["base_url"])
MODEL = "qwen2.5-7b-instruct"

ASK = {
 "definitional":
   "Does the Lean `def` named {target} faithfully encode the informal object (same function: norm, "
   "constants, sign, regularization, domain)? A wrong constant/term/sign/norm is UNFAITHFUL.",
 "instance_soundness":
   "Does the Lean `instance` {target} SOUNDLY certify its structure — every condition field a real "
   "proof, none `sorry` (directly or via a lemma whose body is `sorry`)? Any sorry-backed condition "
   "field is UNFAITHFUL (HOLLOW). Data fields are irrelevant.",
 "transfer_validity":
   "Is the theorem {target} a genuine specialization of the abstract theorem below (obtainable by "
   "applying it)? A statement stronger/unrelated to what the abstract result gives is UNFAITHFUL.",
 "statement_faithfulness":
   "Does the theorem {target}'s STATEMENT match the informal claim — same rate (e.g. O(1/k) vs "
   "O(1/k^2)), inequality direction, hypotheses, quantifier (watch the k=0 corner)? A different "
   "rate/direction/dropped-hypothesis is UNFAITHFUL.",
}

def judge(it):
    p = (f"You are auditing a Lean 4 formalization (check: {it['check']}).\n\n"
         f"{ASK[it['check']].format(target=it['target'])}\n\n"
         f"INFORMAL PROBLEM:\n{str(it.get('informal',''))[:1500]}\n\n"
         + (f"ABSTRACT THEOREM:\n{str(it.get('abstract_theorem',''))[:1200]}\n\n"
            if it['check'] in ('transfer_validity','statement_faithfulness') else "")
         + f"LEAN SOURCE:\n```lean\n{str(it.get('lean_source',''))[:6000]}\n```\n\n"
         "Reply on line 1 with exactly FAITHFUL or UNFAITHFUL. Line 2: confidence 1-5 (5=certain).")
    r = client.chat.completions.create(model=MODEL, temperature=0.0, max_tokens=80,
                                        messages=[{"role":"user","content":p}])
    txt = (r.choices[0].message.content or "").strip()
    up = txt.upper()
    verdict = "unfaithful" if "UNFAITHFUL" in up.split("\n")[0] else ("faithful" if "FAITHFUL" in up.split("\n")[0] else "unknown")
    m = re.search(r"[1-5]", txt.split("\n",1)[-1])
    conf = int(m.group()) if m else 3
    return verdict, conf

def main():
    items = {json.loads(l)["id"]: json.loads(l) for l in (ANN/"pool/items.jsonl").read_text().splitlines() if l.strip()}
    gold = {json.loads(l)["id"]: json.loads(l) for l in (ANN/"gold.jsonl").read_text().splitlines() if l.strip()}
    rows, t0 = [], time.time()
    for i, (iid, it) in enumerate(items.items(), 1):
        v, c = judge(it)
        g = gold[iid]["label"]
        rows.append({"id": iid, "check": it["check"], "target": it["target"],
                     "gold": g, "llm_judge": v, "confidence": c, "correct": v == g})
        print(f"  [{i:>2}/57] {iid} {it['check'][:5]:<5} gold={g:<11} judge={v:<11} c={c} {'OK' if v==g else 'X'}", flush=True)
    out = {"model": MODEL, "n": len(rows), "wall_s": round(time.time()-t0,1), "items": rows}
    (Path(__file__).resolve().parents[1]/"eval_logs"/"llm_judge_gold_result.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    acc = sum(r["correct"] for r in rows)/len(rows)
    print(f"\nLLM-judge overall acc vs gold: {acc:.3f}  ({time.time()-t0:.0f}s)")

if __name__ == "__main__":
    main()
