#!/usr/bin/env python3
"""Inter-annotator agreement + calibration for the human-correlation pool (panel of N raters).

Computes (HUMAN_CORRELATION_STUDY.md §7):
  * pairwise Cohen's kappa (overall + per check)
  * multi-rater Fleiss' kappa (overall + per check)
  * each rater's accuracy vs the hidden construction truth (calibration gate, §4)
  * majority-vote consensus per item, and items where the panel SPLITS (-> adjudication)
  * items where the majority disagrees with construction truth (pool/hard-case audit)

Reads raw_a*.jsonl + keymap.json from instance_beq/annotation/pool/. Writes agreement_report.json.
"""
from __future__ import annotations
import json, glob, itertools, re
from collections import Counter, defaultdict
from pathlib import Path

POOL = Path(__file__).resolve().parents[1] / "instance_beq/annotation/pool"

def load(p):
    return {json.loads(l)["id"]: json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()}

raters = {}
ARCHIVE = POOL / "_expert_panel_archive"   # a-panel archived after the 5-human panel became the reported study
for f in sorted(glob.glob(str(ARCHIVE / "raw_a*.jsonl"))):
    name = re.search(r"raw_(a\d+)", f).group(1).upper()
    raters[name] = load(f)
RNAMES = sorted(raters)
key = json.loads((POOL / "keymap.json").read_text(encoding="utf-8"))
ids = sorted(key)
checks = sorted({key[i]["check"] for i in ids})
LAB = ("faithful", "unfaithful")

def cohen_kappa(a, b):
    """Cohen's kappa for two label lists (paired)."""
    n = len(a)
    if n == 0:
        return float("nan")
    po = sum(x == y for x, y in zip(a, b)) / n
    pe = 0.0
    for lab in LAB:
        pe += (a.count(lab) / n) * (b.count(lab) / n)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)

def fleiss_kappa(rows):
    """rows: list of per-item label-count dicts over LAB, with the SAME number of raters per item."""
    rows = [r for r in rows if sum(r.values()) > 1]
    if not rows:
        return float("nan")
    N = len(rows)
    n = sum(rows[0].values())
    if any(sum(r.values()) != n for r in rows):
        # ragged (some raters abstained?) — fall back to per-item n
        pass
    # P_i per item
    Pbar = 0.0
    pj = {lab: 0 for lab in LAB}
    for r in rows:
        ni = sum(r.values())
        Pi = (sum(c * c for c in r.values()) - ni) / (ni * (ni - 1)) if ni > 1 else 0.0
        Pbar += Pi
        for lab in LAB:
            pj[lab] += r.get(lab, 0)
    Pbar /= N
    tot = sum(sum(r.values()) for r in rows)
    Pe = sum((pj[lab] / tot) ** 2 for lab in LAB)
    return 1.0 if Pe == 1 else (Pbar - Pe) / (1 - Pe)

report = {"raters": RNAMES, "n_items": len(ids)}

# ---- pairwise Cohen's kappa (overall + per check) ----
def subset(rnames_pair, check=None):
    a, b = rnames_pair
    sel = [i for i in ids if (check is None or key[i]["check"] == check)]
    la = [raters[a][i]["label"] for i in sel]
    lb = [raters[b][i]["label"] for i in sel]
    return la, lb

pairwise = {"overall": {}, "by_check": defaultdict(dict)}
for pa, pb in itertools.combinations(RNAMES, 2):
    la, lb = subset((pa, pb))
    pairwise["overall"][f"{pa}-{pb}"] = round(cohen_kappa(la, lb), 3)
    for c in checks:
        la, lb = subset((pa, pb), c)
        pairwise["by_check"][c][f"{pa}-{pb}"] = round(cohen_kappa(la, lb), 3)
report["cohen_pairwise"] = {"overall": pairwise["overall"], "by_check": {c: dict(v) for c, v in pairwise["by_check"].items()}}
report["cohen_mean"] = {
    "overall": round(sum(pairwise["overall"].values()) / len(pairwise["overall"]), 3),
    "by_check": {c: round(sum(pairwise["by_check"][c].values()) / len(pairwise["by_check"][c]), 3) for c in checks},
}

# ---- Fleiss' kappa (overall + per check) ----
def count_rows(check=None):
    rows = []
    for i in ids:
        if check is not None and key[i]["check"] != check:
            continue
        c = Counter(raters[r][i]["label"] for r in RNAMES)
        rows.append({lab: c.get(lab, 0) for lab in LAB})
    return rows
report["fleiss"] = {"overall": round(fleiss_kappa(count_rows()), 3),
                    "by_check": {c: round(fleiss_kappa(count_rows(c)), 3) for c in checks}}

# ---- per-rater accuracy vs construction truth (calibration gate) ----
truth_ids = [i for i in ids if key[i]["construction_truth"] in LAB]
cal = {}
for r in RNAMES:
    overall = sum(raters[r][i]["label"] == key[i]["construction_truth"] for i in truth_ids) / len(truth_ids)
    bycheck = {}
    for c in checks:
        sel = [i for i in truth_ids if key[i]["check"] == c]
        bycheck[c] = round(sum(raters[r][i]["label"] == key[i]["construction_truth"] for i in sel) / len(sel), 3) if sel else None
    cal[r] = {"overall": round(overall, 3), "by_check": bycheck}
report["calibration_vs_truth"] = cal
# gate (study §4): definitional & statement accuracy >= 0.8
report["calibration_gate_0.8_def_stmt"] = {
    r: all((cal[r]["by_check"].get(c) is None) or cal[r]["by_check"][c] >= 0.8
           for c in ("definitional", "statement_faithfulness"))
    for r in RNAMES
}

# ---- majority consensus + splits ----
majority, splits, maj_vs_truth = {}, [], []
for i in ids:
    c = Counter(raters[r][i]["label"] for r in RNAMES)
    top, n_top = c.most_common(1)[0]
    majority[i] = {"label": top, "votes": dict(c), "agreement": round(n_top / len(RNAMES), 2),
                   "unanimous": n_top == len(RNAMES)}
    if n_top < len(RNAMES):
        splits.append({"id": i, "check": key[i]["check"], "target": key[i]["target"],
                       "votes": dict(c), "truth": key[i]["construction_truth"]})
    if key[i]["construction_truth"] in LAB and top != key[i]["construction_truth"]:
        maj_vs_truth.append({"id": i, "check": key[i]["check"], "target": key[i]["target"],
                             "majority": top, "truth": key[i]["construction_truth"], "votes": dict(c),
                             "note": key[i].get("note", "")})
report["majority"] = majority
report["n_unanimous"] = sum(1 for i in ids if majority[i]["unanimous"])
report["splits"] = splits
report["majority_disagrees_with_truth"] = maj_vs_truth

(ARCHIVE / "agreement_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

# ---- console summary ----
print(f"Panel: {RNAMES}   items: {len(ids)}   unanimous: {report['n_unanimous']}/{len(ids)}\n")
print("Cohen's kappa (mean over all pairs):")
print(f"  overall: {report['cohen_mean']['overall']}")
for c in checks:
    print(f"    {c:<24}: {report['cohen_mean']['by_check'][c]}")
print(f"\nFleiss' kappa:")
print(f"  overall: {report['fleiss']['overall']}")
for c in checks:
    print(f"    {c:<24}: {report['fleiss']['by_check'][c]}")
print(f"\nAccuracy vs construction truth (n={len(truth_ids)} truth-bearing items):")
for r in RNAMES:
    g = "PASS" if report["calibration_gate_0.8_def_stmt"][r] else "FAIL"
    print(f"  {r}: {cal[r]['overall']:.3f}   def={cal[r]['by_check']['definitional']} "
          f"stmt={cal[r]['by_check']['statement_faithfulness']} "
          f"inst={cal[r]['by_check']['instance_soundness']} trans={cal[r]['by_check']['transfer_validity']}  gate[{g}]")
print(f"\nSplit items (need adjudication): {len(splits)}")
for s in splits:
    print(f"  {s['id']} [{s['check']}] {s['target']}  votes={s['votes']}  truth={s['truth']}")
print(f"\nMajority disagrees with construction truth: {len(maj_vs_truth)}")
for m in maj_vs_truth:
    print(f"  {m['id']} [{m['check']}] {m['target']}  maj={m['majority']} truth={m['truth']} votes={m['votes']}")
print(f"\nwrote {ARCHIVE / 'agreement_report.json'}")
