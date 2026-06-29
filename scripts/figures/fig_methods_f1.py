#!/usr/bin/env python3
"""Centerpiece comparison: (A) per-check faithfulness-detection F1 for all five methods, and
(B) the safety story -- false certifications (truly-unfaithful artifacts positively accepted).
Source: eval_logs/methods_vs_gold_result.json (real unified scorer). No invented numbers.
Message: Instance-BEq is the only method exact on the two structural checks (soundness, transfer)
and makes the fewest false certifications, where the blind baselines accept dozens of unfaithful
artifacts. Its definitional bar is shown as a certify marker (it certifies, not detects; Tab. refabl).
"""
import numpy as np
import figstyle as F
F.setup()
import matplotlib.pyplot as plt

d = F.load("methods_vs_gold_result.json")
CHECKS = [("definitional", "Defin."), ("instance_soundness", "Sound."),
          ("transfer_validity", "Transf."), ("statement_faithfulness", "Stmt.")]
METHODS = ["type-check-only", "BEq+", "LLM-judge", "majority-vote", "Instance-BEq"]

fig, (axA, axB) = plt.subplots(1, 2, figsize=(14.0, 4.7), gridspec_kw={"width_ratios": [2.4, 1]})
plt.subplots_adjust(wspace=0.32)

# ---- Panel A: grouped F1 bars per check ---------------------------------------------------
x = np.arange(len(CHECKS)); w = 0.16
for j, m in enumerate(METHODS):
    vals, marks = [], []
    for c, _ in CHECKS:
        s = d["by_check"][c][m]
        f1 = s["F1"]
        vals.append(f1 if f1 is not None else 0.0)
        marks.append(f1 is None and s["coverage"] is not None and s["coverage"] < 1)
    off = (j - (len(METHODS) - 1) / 2) * w
    bars = axA.bar(x + off, vals, w, color=F.COLORS[m], edgecolor="black",
                   hatch=F.HATCH[m], label=m, zorder=3)
    # certify-only marker for the certifier's definitional cell (F1 undefined -> it certifies)
    for xi, mk in zip(x, marks):
        if mk:
            axA.scatter(xi + off, 0.045, marker=r"$\checkmark$", s=130,
                        color=F.COLORS[m], zorder=6)
            axA.text(xi + off, 0.10, "cert", rotation=90, ha="center", va="bottom",
                     fontsize=11, color=F.COLORS[m], fontweight="bold")
axA.set_xticks(x); axA.set_xticklabels([n for _, n in CHECKS])
axA.set_ylabel("Detection F1"); axA.set_ylim(0, 1.08)
axA.axhline(0, color="black", lw=1.0)
axA.legend(loc="upper center", ncol=3, bbox_to_anchor=(0.5, 1.20), handlelength=1.4,
           columnspacing=1.1, fontsize=13.5)
F.despine(axA)

# ---- Panel B: false certifications (overall) ----------------------------------------------
ov = d["by_check"]["overall"]
order = sorted(METHODS, key=lambda m: ov[m]["false_cert"], reverse=True)
y = np.arange(len(order))
fc = [ov[m]["false_cert"] for m in order]
axB.barh(y, fc, color=[F.COLORS[m] for m in order], edgecolor="black",
         hatch=[F.HATCH[m] for m in order], zorder=3)
for yi, m in zip(y, order):
    axB.text(ov[m]["false_cert"] + 0.4, yi, str(ov[m]["false_cert"]), va="center",
             fontsize=14, fontweight="bold")
axB.set_yticks(y); axB.set_yticklabels(order, fontsize=13)
axB.set_xlabel("False certifications", fontsize=16)
axB.set_xlim(0, max(fc) + 3.5)
axB.set_xticks([0, 10, 20])
axB.invert_yaxis()
F.despine(axB)

F.save(fig, "methods_f1")
