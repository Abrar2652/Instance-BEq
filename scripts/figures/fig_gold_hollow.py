#!/usr/bin/env python3
"""FIG (motivating, EXPERIMENT_PLAN §C): hollow condition fields in the GOLD instances.
Even hand-written gold examples contain hollow (sorry-tainted) structural-condition fields:
2/6 instances, localized per field. Sources (all real):
  eval_logs/certify_gold_result.json  (which families are hollow)
  eval_logs/trace_fields_result.json  (per-field hollow counts for ADMM/BCD)
  eval_logs/fault_injection_result.json (condition-field counts for the sound families = #plants)
Supports the §C motivating measurement and objection R1 ("type-check already means correct").
"""
import figstyle as F
F.setup()
import matplotlib.pyplot as plt
from collections import Counter

gold = {r["family"]: r["gold"]["verdict"] for r in F.load("certify_gold_result.json")}
trace = F.load("trace_fields_result.json")
fault = F.load("fault_injection_result.json")["items"]
# condition-field count per sound family = number of planted fields for it
cond_n = Counter(it["family"] for it in fault if it["case"] != "original")

LABEL = {"GD_example": "Gradient Descent", "PGD_example": "Proximal Gradient",
         "NesterovFirst_example": "Nesterov-I", "NesterovSecond_example": "Nesterov-II",
         "ADMM_example": "ADMM", "BCD_example": "BCD"}

rows = []  # (label, n_fields, n_hollow)
for fam in ["GD_example", "PGD_example", "NesterovFirst_example", "NesterovSecond_example"]:
    rows.append((LABEL[fam], cond_n[fam], 0))
for fam in ["ADMM_example", "BCD_example"]:
    nf = len(trace[fam]["fields"]); nh = len(trace[fam]["tainted_fields"])
    rows.append((LABEL[fam], nf, nh))
rows.sort(key=lambda r: (r[2] == 0, r[1]))   # hollow families first (bottom-up)

fig, ax = plt.subplots(figsize=(7.2, 4.3))
y = range(len(rows))
admm_i = next(i for i, r in enumerate(rows) if r[0] == "ADMM")
for yi, (lab, nf, nh) in zip(y, rows):
    ns = nf - nh
    ax.barh(yi, ns, color=F.COLORS["type-check-only"], edgecolor="black", zorder=3)
    if nh:
        ax.barh(yi, nh, left=ns, color=F.MISS, edgecolor="black", hatch="////", zorder=3)
        ax.text(nf + 0.15, yi, f"{nh}/{nf} hollow", va="center", ha="left",
                fontsize=14, fontweight="bold", color=F.MISS)
    # direct on-bar colour key, placed once on the ADMM bar (both segments visible there)
    if yi == admm_i:
        ax.text(ns / 2, yi, "sound", va="center", ha="center", color="#3a4046",
                fontsize=12.5, fontweight="bold")
        ax.text(ns + nh / 2, yi, "hollow", va="center", ha="center", color="white",
                fontsize=12.5, fontweight="bold")
ax.set_yticks(list(y)); ax.set_yticklabels([r[0] for r in rows])
ax.set_xlabel("structural-condition fields")
ax.set_xlim(0, max(r[1] for r in rows) + 3.0)
ax.set_ylim(-0.7, len(rows) - 1 + 1.4)   # top headroom for the summary annotation
F.despine(ax)
ax.text(0.99, 0.97, "2 of 6 gold instances are hollow", transform=ax.transAxes,
        ha="right", va="top", fontsize=15, fontweight="bold")
F.save(fig, "gold_hollow")
