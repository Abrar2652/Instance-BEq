#!/usr/bin/env python3
"""NOVEL FIG — precision/recall trade-off with F1 iso-contours.
Rationale: reframes the comparison as a Pareto picture — Instance-BEq sits exactly at the (1,1)
corner (no trade-off), the LLM-judge gives up precision for no gain, and type-check-only collapses
to zero recall. F1 contours are analytic (not data). Points are real:
eval_logs/soundness_methods_result.json. Supports §B and objections R2/R5.
"""
import numpy as np
import figstyle as F
F.setup()
import matplotlib.pyplot as plt

d = F.load("soundness_methods_result.json")["methods"]

fig, ax = plt.subplots(figsize=(5.8, 5.4))
# F1 iso-contours (analytic): F1 = 2PR/(P+R)
rr = np.linspace(0.001, 1, 300); pp = np.linspace(0.001, 1, 300)
RR, PP = np.meshgrid(rr, pp)
F1 = 2 * PP * RR / (PP + RR)
cs = ax.contour(RR, PP, F1, levels=[0.25, 0.5, 0.75, 0.9], colors=F.GRID,
                linewidths=1.1, linestyles="dashed")
# label only the two low contours (clear, lower-left area); leave 0.75/0.9 unlabeled near the points
ax.clabel(cs, levels=[0.25, 0.5], fmt=lambda v: f"F1={v:.2f}", fontsize=10, inline=True)
ax.text(0.97, 0.10, "dashed: F1 contours", ha="right", va="bottom", fontsize=11.5, color="#7a7f85")

# real points (Recall on x, Precision on y). Ours (1,1) and LLM-judge (1,0.913) are near-
# coincident, so use leader lines to well-separated label boxes.
def pt(m): return d[m]["R"], d[m]["P"]
arrow = dict(arrowstyle="-", color="black", lw=1.3)
ax.scatter(*pt("Instance-BEq"), s=420, marker="*", color=F.COLORS["Instance-BEq"],
           edgecolor="black", zorder=6)
ax.annotate("Instance-BEq\n(exact: P=R=1)", pt("Instance-BEq"), xytext=(0.40, 0.86),
            ha="left", va="center", fontsize=14, fontweight="bold",
            color=F.COLORS["Instance-BEq"], arrowprops=arrow)
rj, pj = pt("LLM-judge")
ax.scatter(rj, pj, s=210, marker="o", color=F.COLORS["LLM-judge"], edgecolor="black", zorder=6)
ax.annotate(f"LLM-judge\n(P={pj:.2f}: gives\nup precision)", (rj, pj), xytext=(0.40, 0.60),
            ha="left", va="center", fontsize=14, fontweight="bold", color="#b5660c",
            arrowprops=arrow)
# type-check-only: recall 0, precision undefined -> mark at the no-detection corner
ax.scatter(0, 0, s=180, marker="s", facecolor="white",
           edgecolor="#6b7177", linewidth=2.6, zorder=6)
ax.annotate("type-check-only\nR=0 (predicts nothing;\nP undefined)", (0, 0), xytext=(0.07, 0.30),
            ha="left", va="center", fontsize=13, fontweight="bold", color="#5d646b",
            arrowprops=arrow)

ax.set_xlabel("recall"); ax.set_ylabel("precision")
ax.set_xlim(-0.03, 1.16); ax.set_ylim(-0.03, 1.10)
ax.set_xticks([0, 0.5, 1]); ax.set_yticks([0, 0.5, 1])
F.despine(ax)
F.save(fig, "pr_tradeoff")
