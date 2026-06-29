#!/usr/bin/env python3
"""FIG: headline precision/recall/F1 across methods for instance-soundness (check 2).
Source: eval_logs/soundness_methods_result.json (assembled from real runs by
scripts/soundness_all_methods.py). Supports EXPERIMENT_PLAN §B (core results) and R1/R2.
Majority-vote (baseline B) is intentionally absent: not yet run on real data.
"""
import numpy as np
import figstyle as F
F.setup()
import matplotlib.pyplot as plt

d = F.load("soundness_methods_result.json")["methods"]
methods = ["Instance-BEq", "LLM-judge", "type-check-only"]   # ours first
metrics = [("P", "Precision"), ("R", "Recall"), ("F1", "F1")]

fig, ax = plt.subplots(figsize=(7.4, 4.4))
x = np.arange(len(metrics)); w = 0.26
for i, m in enumerate(methods):
    vals, labels = [], []
    for k, _ in metrics:
        v = d[m][k]
        vals.append(0.0 if v is None else v)
        labels.append("n/a" if v is None else f"{v:.2f}")
    xs = x + (i - 1) * w
    bars = ax.bar(xs, vals, w, color=F.COLORS[m], edgecolor="black",
                  hatch=F.HATCH[m], label=m, zorder=3)
    for xi, v, lab in zip(xs, vals, labels):
        ax.text(xi, v + 0.015 if v > 0 else 0.015, lab, ha="center", va="bottom",
                fontsize=13.5, fontweight="bold")

ax.set_xticks(x); ax.set_xticklabels([n for _, n in metrics])
ax.set_ylabel("score"); ax.set_ylim(0, 1.12)
ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
ax.axhline(0, color="black", lw=1.2)
F.despine(ax)
ax.legend(loc="lower center", ncol=3, bbox_to_anchor=(0.5, 1.0),
          handlelength=1.3, columnspacing=1.1, borderpad=0.2)
F.save(fig, "prf_soundness")
