#!/usr/bin/env python3
"""Bootstrap 95% confidence intervals for every P/R/F1/accuracy/Kendall-tau reported, so the small
per-check n's (4-24) come with honest uncertainty. Resamples per-item (gold,pred) pairs.
Reads per-item results that already exist; writes eval_logs/ci_result.json.
"""
from __future__ import annotations
import json, sys, random
from pathlib import Path
from scipy.stats import kendalltau

LOG = Path(__file__).resolve().parents[1] / "eval_logs"
random.seed(20260628)
B = 2000


def metrics(pairs):
    tp = sum(g == "unfaithful" and p == "unfaithful" for g, p in pairs)
    fn = sum(g == "unfaithful" and p != "unfaithful" for g, p in pairs)
    fp = sum(g == "faithful" and p == "unfaithful" for g, p in pairs)
    tn = sum(g == "faithful" and p != "unfaithful" for g, p in pairs)
    P = tp/(tp+fp) if tp+fp else None
    R = tp/(tp+fn) if tp+fn else None
    # F1 = 2tp/(2tp+fp+fn): always defined when any positive exists (gold or predicted);
    # a blind baseline that predicts all-faithful gets F1=0 here (it recalls no unfaithful).
    F = (2*tp/(2*tp+fp+fn)) if (2*tp+fp+fn) > 0 else None
    acc = (tp+tn)/len(pairs) if pairs else None
    gy = [1 if g == "unfaithful" else 0 for g, _ in pairs]
    py = [1 if p == "unfaithful" else 0 for _, p in pairs]
    tau = kendalltau(gy, py)[0] if (len(set(gy)) > 1 and len(set(py)) > 1) else 0.0
    return {"P": P, "R": R, "F1": F, "acc": acc, "tau": (0.0 if tau != tau else tau)}


def ci(pairs, keys=("P", "R", "F1", "acc", "tau")):
    pairs = [(g, p) for g, p in pairs if p is not None]
    if not pairs:
        return None
    pt = metrics(pairs)
    boots = {k: [] for k in keys}
    n = len(pairs)
    for _ in range(B):
        sample = [pairs[random.randrange(n)] for _ in range(n)]
        m = metrics(sample)
        for k in keys:
            if m[k] is not None:
                boots[k].append(m[k])
    out = {"n": n}
    for k in keys:
        v = pt[k]
        if v is None or not boots[k]:
            out[k] = {"point": None}
        else:
            bs = sorted(boots[k])
            lo = bs[int(0.025*len(bs))]; hi = bs[min(len(bs)-1, int(0.975*len(bs)))]
            out[k] = {"point": round(v, 3), "lo": round(lo, 3), "hi": round(hi, 3)}
    return out


def main():
    # single source of truth: the unified per-item verdicts emitted by score_methods_vs_gold.py
    per = json.loads((LOG/"methods_vs_gold_result.json").read_text())["per_item"]
    METHODS = ["Instance-BEq", "majority-vote", "LLM-judge", "BEq+", "type-check-only"]
    CH = ["definitional", "instance_soundness", "transfer_validity", "statement_faithfulness", "overall"]
    res = {}
    for c in CH:
        rows = [r for r in per if c == "overall" or r["check"] == c]
        res[c] = {m: ci([(r["gold"], r.get(m)) for r in rows]) for m in METHODS}
    (LOG/"ci_result.json").write_text(json.dumps(res, indent=2), encoding="utf-8")

    def fmt(d, k):
        if not d or d[k]["point"] is None:
            return "  --  "
        x = d[k]
        return f"{x['point']:.2f} [{x['lo']:.2f},{x['hi']:.2f}]"
    print(f"{'check':<22}{'method':<17}{'F1 [95% CI]':<22}{'tau [95% CI]'}")
    for c in CH:
        for m in METHODS:
            d = res[c].get(m)
            if d is None:
                continue
            print(f"{c:<22}{m:<17}{fmt(d,'F1'):<22}{fmt(d,'tau')}")
        print()
    print("wrote", LOG/"ci_result.json")


if __name__ == "__main__":
    main()
