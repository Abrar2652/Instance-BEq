#!/usr/bin/env python3
"""FIG: check 1 (definitional faithfulness) controlled benchmark.
Equivalent references are PROVED (recall 1.0; the closing tactic is shown); corrupted references
are REJECTED (0 false certifications; kernel-soundness => precision 1 by construction).
Source: eval_logs/check1_defeq_result.json (real). Supports §B/§D and objection R5/R7.
NOTE: this shows the tactic that closed each equivalence (a partial view of the tactic ensemble);
a full ensemble-SIZE ablation (§D item 1) is not yet run.
"""
import figstyle as F
F.setup()
import matplotlib.pyplot as plt

d = F.load("check1_defeq_result.json")
rows = d["rows"]
# order: equivalents (proved) on top, corruptions (rejected) below
eq = [r for r in rows if r["truth"] == "faithful"]
co = [r for r in rows if r["truth"] == "unfaithful"]
order = eq + co
labels = [r["label"] for r in order]

fig, ax = plt.subplots(figsize=(7.4, 4.3))
for i, r in enumerate(order):
    proved = (r["verdict"] == "faithful")
    color = F.COLORS["Instance-BEq"] if proved else F.COLORS["type-check-only"]
    ax.barh(i, 1.0, color=color, edgecolor="black", zorder=3)   # solid: dark vs light reads in B/W
    if proved:
        tac = (r["winning_tactic"] or "").replace("LeastSquares_problem.f", "f")
        ax.text(0.035, i, f"proved   {tac}", va="center", ha="left",
                color="white", fontsize=13.5, fontweight="bold")
    else:
        ax.text(0.035, i, "rejected (not provably equal)", va="center", ha="left",
                color="#23272b", fontsize=13.5, fontweight="bold")
ax.set_yticks(range(len(order))); ax.set_yticklabels(labels)
ax.set_xlim(0, 1.0); ax.set_xticks([])
F.despine(ax, keep=("left",))
# group brackets
n_eq = len(eq)
ax.text(1.02, (n_eq - 1) / 2, "equivalent\n(should prove)", va="center", ha="left",
        fontsize=13.5, color=F.COLORS["Instance-BEq"], fontweight="bold")
ax.text(1.02, n_eq + (len(co) - 1) / 2, "corrupted\n(should reject)", va="center", ha="left",
        fontsize=13.5, color=F.MISS, fontweight="bold")
ax.axhline(n_eq - 0.5, color="black", lw=1.0, ls=(0, (4, 3)))
F.save(fig, "check1_defeq")
