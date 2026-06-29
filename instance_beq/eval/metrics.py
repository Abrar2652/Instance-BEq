"""Metrics: precision/recall/F1 per check + overall, and Kendall tau vs human gold.

Gold format (annotation/gold.jsonl), one JSON per line:
  {"path": "...", "check": "instance_soundness"|"definitional"|"transfer_validity"|
   "statement_faithfulness"|"overall", "target": "<decl-or-file>", "label": "faithful"|"unfaithful"}

This refuses to emit a final table from a mock run unless --allow-mock-table is passed.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Iterable


def load_jsonl(path: str) -> list[dict]:
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


def prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f, 4),
            "tp": tp, "fp": fp, "fn": fn}


def score_predictions(pred: dict, gold: dict) -> dict:
    """pred/gold: {(path,check,target): "faithful"|"unfaithful"|"unknown"}.

    We score "unfaithful" detection as the positive class (we want to CATCH unfaithful ones).
    "unknown" predictions are counted as abstentions (excluded from P/R, reported as coverage).
    """
    by_check = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0, "abstain": 0, "n": 0})
    for key, g in gold.items():
        check = key[1]
        p = pred.get(key, "unknown")
        slot = by_check[check]
        slot["n"] += 1
        if p == "unknown":
            slot["abstain"] += 1
            # an abstention on a truly-unfaithful item is a missed detection (fn) for recall-honesty
            if g == "unfaithful":
                slot["fn"] += 1
            continue
        pred_pos = (p == "unfaithful")
        gold_pos = (g == "unfaithful")
        if pred_pos and gold_pos:
            slot["tp"] += 1
        elif pred_pos and not gold_pos:
            slot["fp"] += 1
        elif (not pred_pos) and gold_pos:
            slot["fn"] += 1
    out = {}
    for check, s in by_check.items():
        m = prf(s["tp"], s["fp"], s["fn"])
        m["coverage"] = round((s["n"] - s["abstain"]) / s["n"], 4) if s["n"] else 0.0
        m["n"] = s["n"]
        out[check] = m
    return out


def kendall_tau(pred_scores: list[float], gold_scores: list[float]) -> float | None:
    try:
        from scipy.stats import kendalltau
    except Exception:
        return None
    if len(pred_scores) < 2:
        return None
    tau, _ = kendalltau(pred_scores, gold_scores)
    return None if tau != tau else round(float(tau), 4)  # nan guard


def predictions_from_summary(summary_path: str) -> dict:
    s = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    pred = {}
    for cert in s.get("certificates", []):
        path = cert["path"]
        for r in cert["results"]:
            pred[(path, r["check"], r["target"])] = r["verdict"]
        pred[(path, "overall", path)] = cert["formal_faithful"]
    return pred, s.get("mock", False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", required=True)
    ap.add_argument("--summary", required=True, help="run_certifier output JSON")
    ap.add_argument("--allow-mock-table", action="store_true")
    ap.add_argument("--out", default="instance_beq/eval/results/metrics.json")
    args = ap.parse_args()

    pred, is_mock = predictions_from_summary(args.summary)
    if is_mock and not args.allow_mock_table:
        raise SystemExit("Refusing to emit a metrics table from a MOCK run. Use real outputs, or "
                         "--allow-mock-table for pipeline debugging only.")
    gold_rows = load_jsonl(args.gold)
    gold = {(g["path"], g["check"], g["target"]): g["label"] for g in gold_rows}
    metrics = score_predictions(pred, gold)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
