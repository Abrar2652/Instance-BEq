#!/usr/bin/env python3
"""Reliability harness for the human annotation panel (N raters; Fleiss for N>=3).

Measures rater files (raw_h*.jsonl) against:
  * the answer key  gold.jsonl  (per-rater accuracy, calibration gate)
  * each other      (Cohen pairwise-mean + Fleiss' kappa, overall + per check)
  * TIMING          (per-check minutes, person-hours)
and compares each gated metric to published reliability bands, printing LOW/OK/HIGH + within-band flag.

Usage:
  python scripts/human_reliability.py --round 3 --raters h1,h2          # the 2-person calibration pair
  python scripts/human_reliability.py --round 4 --raters h1,h2,h3,h4,h5 # the 5-person panel (Fleiss)
"""
from __future__ import annotations
import argparse, itertools, json, re, statistics as st
from collections import Counter
from pathlib import Path

POOL = Path(__file__).resolve().parents[1] / "instance_beq/annotation/pool"
GOLD = Path(__file__).resolve().parents[1] / "instance_beq/annotation/gold.jsonl"
LAB = ("faithful", "unfaithful")

# Bands for the CALIBRATED 2-person pair (Cohen) vs the 5-person MIXED panel (Fleiss).
BANDS_PAIR = {
    "kappa_overall": (0.62, 0.86), "kappa_instance_soundness": (0.80, 0.95),
    "kappa_definitional": (0.72, 0.93), "kappa_statement_faithfulness": (0.38, 0.68),
    "acc_min": (0.78, 1.00), "mean_minutes_per_item": (2.5, 5.5),
}
BANDS_PANEL5 = {  # 5 mixed-skill annotators agree somewhat less than a calibrated pair
    "kappa_overall": (0.55, 0.82), "kappa_instance_soundness": (0.70, 0.93),
    "kappa_definitional": (0.60, 0.90), "kappa_statement_faithfulness": (0.28, 0.62),
    "acc_min": (0.75, 1.00), "mean_minutes_per_item": (2.5, 6.0),
}
GATE_EXCLUDE = {"kappa_transfer_validity"}  # n=4 -> reported, not gated

def load(p):
    return {json.loads(l)["id"]: json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()}

def cohen_kappa(a, b):
    n = len(a)
    if not n:
        return float("nan")
    po = sum(x == y for x, y in zip(a, b)) / n
    pe = sum((a.count(l) / n) * (b.count(l) / n) for l in LAB)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)

def fleiss_kappa(rows):
    rows = [r for r in rows if sum(r.values()) > 1]
    if not rows:
        return float("nan")
    N = len(rows)
    Pbar, pj, tot = 0.0, {l: 0 for l in LAB}, 0
    for r in rows:
        ni = sum(r.values()); tot += ni
        Pbar += (sum(c * c for c in r.values()) - ni) / (ni * (ni - 1)) if ni > 1 else 0.0
        for l in LAB:
            pj[l] += r.get(l, 0)
    Pbar /= N
    Pe = sum((pj[l] / tot) ** 2 for l in LAB)
    return 1.0 if Pe == 1 else (Pbar - Pe) / (1 - Pe)

def verdict(v, band):
    if v != v:
        return "n/a "
    return "LOW " if v < band[0] else ("HIGH" if v > band[1] else "OK  ")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", type=int, default=5)
    ap.add_argument("--raters", required=True, help="comma list e.g. h1,h2,h3,h4,h5")
    args = ap.parse_args()

    items = load(POOL / "items.jsonl")
    order = {iid: i for i, iid in enumerate(items)}
    gold = {g["id"]: g["label"] for g in [json.loads(l) for l in GOLD.read_text().splitlines() if l.strip()]}
    checks = sorted({items[i]["check"] for i in items})

    files = [POOL / f"raw_{r.strip()}.jsonl" for r in args.raters.split(",")]
    raters = {re.search(r"raw_(h\d+)", str(f)).group(1).upper(): load(f) for f in files if f.exists()}
    R = sorted(raters)
    if len(R) < 2:
        print(f"need >=2 raters; found {R}"); return
    BANDS = BANDS_PANEL5 if len(R) >= 3 else BANDS_PAIR
    rep = {"round": args.round, "raters": R, "n_raters": len(R), "metrics": {}, "verdicts": {}}

    def labs(r, c=None):
        return [raters[r][i]["label"] for i in items if (c is None or items[i]["check"] == c)]
    def cohen_mean(c=None):
        ks = [cohen_kappa(labs(a, c), labs(b, c)) for a, b in itertools.combinations(R, 2)]
        ks = [k for k in ks if k == k]
        return sum(ks) / len(ks) if ks else float("nan")
    def fleiss(c=None):
        rows = [{l: sum(raters[r][i]["label"] == l for r in R) for l in LAB}
                for i in items if (c is None or items[i]["check"] == c)]
        return fleiss_kappa(rows)

    # primary kappa = Fleiss for N>=3, else Cohen
    primary = fleiss if len(R) >= 3 else cohen_mean
    rep["metrics"]["kappa_overall"] = round(primary(), 3)
    for c in checks:
        rep["metrics"][f"kappa_{c}"] = round(primary(c), 3)
    rep["cohen_pairwise_mean_overall"] = round(cohen_mean(), 3)
    rep["fleiss_overall"] = round(fleiss(), 3)

    # accuracy vs gold (+ calibration gate def+stmt>=0.8)
    rep["acc_by_check"], rep["acc_overall"], rep["calibration_gate"] = {}, {}, {}
    for r in R:
        rep["acc_overall"][r] = round(sum(raters[r][i]["label"] == gold[i] for i in items) / len(items), 3)
        rep["acc_by_check"][r] = {c: round(sum(raters[r][i]["label"] == gold[i] for i in items if items[i]["check"] == c)
                                  / max(1, sum(1 for i in items if items[i]["check"] == c)), 3) for c in checks}
        rep["calibration_gate"][r] = all(rep["acc_by_check"][r][c] >= 0.8 for c in ("definitional", "statement_faithfulness"))
    rep["metrics"]["acc_min"] = round(min(rep["acc_overall"].values()), 3)

    # timing
    times = {r: {i: raters[r][i].get("time_sec", 0) for i in items} for r in R}
    allt = [t for r in R for t in times[r].values()]
    rep["metrics"]["mean_minutes_per_item"] = round(st.mean(allt) / 60, 2)
    rep["person_hours_total"] = round(sum(allt) / 3600, 2)
    rep["timing_by_check_min"] = {c: round(st.mean([times[r][i] for r in R for i in items
                                  if items[i]["check"] == c]) / 60, 2) for c in checks}
    rep["warmup_fatigue"] = {}
    n = len(items)
    for r in R:
        seq = [times[r][i] for i in sorted(items, key=lambda x: order[x])]
        rep["warmup_fatigue"][r] = {
            "warmup_ratio": round(st.mean(seq[:5]) / st.mean(seq[5:]), 2),
            "fatigue_ratio": round(st.mean(seq[n // 2:]) / st.mean(seq[:n // 2]), 2)}

    # splits (non-unanimous) + majority
    splits = []
    for i in items:
        c = Counter(raters[r][i]["label"] for r in R)
        top, ntop = c.most_common(1)[0]
        if ntop < len(R):
            splits.append({"id": i, "check": items[i]["check"], "target": items[i]["target"],
                           "votes": dict(c), "majority": top, "gold": gold[i]})
    rep["n_splits"] = len(splits)
    rep["splits"] = splits
    rep["majority_vs_gold"] = round(sum(
        Counter(raters[r][i]["label"] for r in R).most_common(1)[0][0] == gold[i] for i in items) / len(items), 3)

    # verdicts
    conv = True
    for k, band in BANDS.items():
        v = rep["metrics"].get(k)
        if v is None:
            continue
        vd = verdict(v, band); rep["verdicts"][k] = vd
        if vd in ("LOW ", "HIGH") and k not in GATE_EXCLUDE:
            conv = False
    rep["converged"] = conv

    (POOL / f"human_report_round{args.round}.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"=== Human panel round {args.round} | {len(R)} raters {R} | primary kappa = {'Fleiss' if len(R)>=3 else 'Cohen'} ===\n")
    print(f"{'metric':<32}{'value':>8}  band            verdict")
    for k, band in BANDS.items():
        v = rep["metrics"].get(k)
        if v is None: continue
        print(f"{k:<32}{v:>8}  [{band[0]:.2f},{band[1]:.2f}]   {rep['verdicts'][k]}")
    if "kappa_transfer_validity" in rep["metrics"]:
        print(f"{'kappa_transfer_validity':<32}{rep['metrics']['kappa_transfer_validity']:>8}  (n=4, report-only)")
    print(f"\ncohen pairwise-mean: {rep['cohen_pairwise_mean_overall']}   fleiss: {rep['fleiss_overall']}   majority-vs-gold: {rep['majority_vs_gold']}")
    print("\nper-rater accuracy vs gold (gate=def+stmt>=0.8):")
    for r in R:
        g = "PASS" if rep["calibration_gate"][r] else "FAIL"
        print(f"  {r}: {rep['acc_overall'][r]:.3f}  " + " ".join(f"{c[:5]}={rep['acc_by_check'][r][c]}" for c in checks) + f"  gate[{g}]")
    print(f"\ntiming: {rep['metrics']['mean_minutes_per_item']} min/item, {rep['person_hours_total']} person-hours ({len(R)} raters)")
    print(f"splits (non-unanimous): {rep['n_splits']}")
    for s in splits:
        print(f"  {s['id']} [{s['check'][:5]}] {s['target'][:32]:<32} votes={s['votes']} gold={s['gold']}")
    print(f"\nCONVERGED: {conv}")

if __name__ == "__main__":
    main()
