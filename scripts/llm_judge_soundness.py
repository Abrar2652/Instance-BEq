#!/usr/bin/env python3
"""Baseline C (LLM-judge) for instance soundness, scored on the SAME ground-truth corpus as the
symbolic certifier (the fault-injection set + the 6 gold families).

This produces the head-to-head the paper needs: a formal, kernel-decided certifier (check 2, exact
P=R=1) vs. a modern LLM-as-judge shown the full Lean file. The LLM can see DIRECT planted `sorry`
but is unreliable on TRANSITIVE sorry (a condition field proven by a lemma whose body is sorry,
e.g. the real ADMM/BCD gold) — exactly the failure mode the axiom-closure certifier eliminates.

Uses the local OpenAI-compatible endpoint (Code/data/api/config.json). Single-stream -> a few min.

Run:  python scripts/llm_judge_soundness.py
"""
from __future__ import annotations
import json, re, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from instance_beq.config import InstanceBEqConfig
from openai import OpenAI

EXDIR = "Optlib/Autoformalization/Example"
# family -> (bridging instance, condition fields, ground-truth of the ORIGINAL gold instance)
FAMILIES = {
    "GD_example":            ("LeastSquares_GD.Gradient_Descent", ["update","hl","step₁","initial"], "sound"),
    "PGD_example":           ("proximal_gradient_method_Lasso.proximal_gradient_method", ["initial","update"], "sound"),
    "NesterovFirst_example": ("Nesterov_first_fix_stepsize_Lasso.Nesterov_first_fix_stepsize", ["hl","initial","teq","γeq","update1","update2"], "sound"),
    "NesterovSecond_example":("Nesterov_second_fix_stepsize_Lasso.Nesterov_second_fix_stepsize", ["hl","initial","teq","γeq","update1","update2","update3"], "sound"),
    # gold ADMM/BCD are TRANSITIVELY hollow (no planting needed) — the killer cases for an LLM-judge
    "ADMM_example":          ("Lasso_ADMM.toADMM", [], "hollow"),
    "BCD_example":           ("BCD_JointSparse.BCD", [], "hollow"),
}

PROMPT = """You are auditing a Lean 4 formalization. Below is a Lean file and one `instance` in it.

An instance SOUNDLY certifies its structure iff EVERY condition/proof field is discharged by a real
proof. It is HOLLOW iff at least one condition field is `sorry` — directly (`:= by sorry`) OR
transitively (the field is `:= someLemma` and that lemma's body is `sorry`). Data fields (x, t, l,
y, z, ...) carry no proof and are irrelevant.

INSTANCE TO JUDGE: {inst}

LEAN FILE:
```lean
{lean}
```

Answer on the FIRST line with exactly one word: SOUND or HOLLOW.
Then one short line naming the offending field if HOLLOW."""


def judge(client, model, inst, lean):
    msg = PROMPT.format(inst=inst, lean=lean[:12000])
    r = client.chat.completions.create(model=model, temperature=0.0, max_tokens=120,
                                        messages=[{"role": "user", "content": msg}])
    txt = (r.choices[0].message.content or "").strip()
    first = txt.splitlines()[0].upper() if txt else ""
    verdict = "hollow" if "HOLLOW" in first else ("sound" if "SOUND" in first else "unknown")
    return verdict, txt[:160]


def main():
    cfg = InstanceBEqConfig(mock=False)
    ext = json.loads(Path(cfg.api_config_path).read_text())
    client = OpenAI(api_key=ext["api_key"], base_url=ext["base_url"])
    model = "qwen2.5-7b-instruct"
    root = cfg.lean_cwd
    items, t0 = [], time.time()

    for fam, (inst, fields, gold_truth) in FAMILIES.items():
        text = (root / EXDIR / f"{fam}.lean").read_text(encoding="utf-8")
        # original instance
        v, why = judge(client, model, inst, text)
        items.append({"family": fam, "case": "original", "truth": gold_truth,
                      "llm_judge": v, "why": why})
        print(f"  {fam:<22} original        truth={gold_truth:<7} judge={v}")
        # planted-hollow variants (direct sorry) for the sound families
        for fld in fields:
            patched, n = re.subn(rf"(\n\s*{re.escape(fld)}\s*:=)[^\n]*", r"\1 by sorry",
                                 text, count=1)
            if n != 1:
                continue
            v, why = judge(client, model, inst, patched)
            items.append({"family": fam, "case": f"sorry:{fld}", "truth": "hollow",
                          "llm_judge": v, "why": why})
            print(f"  {fam:<22} sorry:{fld:<10} truth=hollow  judge={v}")

    # score (HOLLOW = positive)
    tp = sum(it["truth"] == "hollow" and it["llm_judge"] == "hollow" for it in items)
    fn = sum(it["truth"] == "hollow" and it["llm_judge"] != "hollow" for it in items)
    fp = sum(it["truth"] == "sound" and it["llm_judge"] == "hollow" for it in items)
    tn = sum(it["truth"] == "sound" and it["llm_judge"] != "hollow" for it in items)
    P = tp / (tp + fp) if tp + fp else float("nan")
    R = tp / (tp + fn) if tp + fn else float("nan")
    F = 2 * P * R / (P + R) if (P == P and R == R and P + R) else 0.0
    # transitive-only subset (the gold ADMM/BCD) — where LLM-judges characteristically fail
    trans = [it for it in items if it["family"] in ("ADMM_example", "BCD_example")]
    trans_hit = sum(it["llm_judge"] == "hollow" for it in trans)
    print("-" * 64)
    print(f"LLM-judge (Qwen2.5-7B) on {len(items)} instances  [{time.time()-t0:.0f}s]")
    print(f"  TP={tp} FP={fp} FN={fn} TN={tn}  Prec={P:.3f} Rec={R:.3f} F1={F:.3f}")
    print(f"  transitive-hollow gold (ADMM,BCD) caught: {trans_hit}/{len(trans)}")
    print(f"  (compare: Instance-BEq check 2 = exact, P=R=F1=1.000)")
    out = Path(__file__).resolve().parents[1] / "eval_logs" / "llm_judge_soundness_result.json"
    out.write_text(json.dumps({"items": items,
                               "metrics": {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
                                           "P": P, "R": R, "F1": F},
                               "transitive_caught": [trans_hit, len(trans)],
                               "model": model}, indent=2, ensure_ascii=False), encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    main()
