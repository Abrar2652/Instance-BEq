#!/usr/bin/env python3
"""Human-correlation study: Kendall-τ of each method with the HUMAN gold, per check, against the
inter-annotator κ ceiling (dashed caps). Source: eval_logs/methods_vs_gold_result.json (real:
human gold + every method's verdicts + human κ). Supports the human-correlation claim.
Message: the formal certifier tracks the human gold up to the inter-annotator ceiling on the two
structural checks (soundness, transfer) where every LLM-based method's τ collapses; on the
definitional check it abstains (τ reported 0, but it never false-certifies -- see Fig. methods_f1).
"""
import numpy as np
import figstyle as F
F.setup()
import matplotlib.pyplot as plt

d = F.load("methods_vs_gold_result.json")
CHECKS = [("definitional", "Definitional"), ("instance_soundness", "Soundness"),
          ("transfer_validity", "Transfer"), ("statement_faithfulness", "Statement")]
METHODS = ["BEq+", "LLM-judge", "majority-vote", "Instance-BEq"]
x = np.arange(len(CHECKS)); w = 0.19

fig, ax = plt.subplots(figsize=(9.2, 4.6))

# human κ ceiling per check (dashed grey caps spanning each group)
for xi, (c, _) in zip(x, CHECKS):
    k = d["kappa_ceiling"].get(c)
    if k is not None:
        ax.plot([xi - 0.44, xi + 0.44], [k, k], color="#444a50", lw=2.4, ls=(0, (5, 3)), zorder=7)
ax.plot([], [], color="#444a50", lw=2.4, ls=(0, (5, 3)), label="human $\\kappa$ ceiling")

for j, m in enumerate(METHODS):
    vals = [d["by_check"][c][m]["tau"] for c, _ in CHECKS]
    off = (j - (len(METHODS) - 1) / 2) * w
    ax.bar(x + off, vals, w, color=F.COLORS[m], edgecolor="black", hatch=F.HATCH[m],
           label=m, zorder=3)
    if m == "Instance-BEq":            # label only ours to avoid 4-bar clutter
        for xi, v in zip(x, vals):
            if v >= 0.03:
                ax.text(xi + off, v + 0.015, f"{v:.2f}", ha="center", va="bottom",
                        fontsize=11.5, fontweight="bold", color=F.COLORS[m])

ax.set_xticks(x); ax.set_xticklabels([n for _, n in CHECKS])
ax.set_ylabel("Kendall $\\tau$ with human gold"); ax.set_ylim(0, 1.14)
ax.axhline(0, color="black", lw=1.0)
ax.legend(loc="upper center", ncol=3, bbox_to_anchor=(0.5, 1.17), handlelength=1.4,
          columnspacing=1.0, fontsize=12.5)
F.despine(ax)
F.save(fig, "tau_human")
