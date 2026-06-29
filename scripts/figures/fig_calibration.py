#!/usr/bin/env python3
"""SKIPPED-FIG now completed: reliability diagram + ECE for the LLM-judge's stated confidence vs.
its actual correctness (the calibration concern behind baseline C / check 3b). Source (real):
eval_logs/llm_judge_gold_result.json. Supports EXPERIMENT_PLAN §D(6) and objection R2 (LLM-judge
miscalibration). Message: the LLM-judge is systematically over-confident — high stated confidence
does not deliver matching accuracy.
"""
import numpy as np
import figstyle as F
F.setup()
import matplotlib.pyplot as plt

rows = F.load("llm_judge_gold_result.json")["items"]
# bin by stated confidence (1..5 -> normalized c/5); empirical accuracy per bin
levels = sorted(set(r["confidence"] for r in rows))
conf, acc, ns = [], [], []
N = len(rows)
ece = 0.0
for c in levels:
    rs = [r for r in rows if r["confidence"] == c]
    a = sum(r["correct"] for r in rs) / len(rs)
    conf.append(c / 5.0); acc.append(a); ns.append(len(rs))
    ece += (len(rs) / N) * abs(a - c / 5.0)

fig, ax = plt.subplots(figsize=(5.9, 5.4))
ax.plot([0, 1], [0, 1], color="#6b7177", lw=1.8, ls=(0, (5, 3)), zorder=2,
        label="perfect calibration")
# reliability points: position ∝ (confidence, accuracy); marker area ∝ n (modal bin dominates)
for x, a, n in zip(conf, acc, ns):
    ax.plot([x, x], [x, a], color="#b9bfc5", lw=1.6, zorder=2)          # thin gap to the diagonal
    ax.scatter(x, a, s=60 + 26 * n, color=F.COLORS["LLM-judge"], edgecolor="black", zorder=4)
# labels staggered so adjacent points never collide (0.6 left, 0.8 right; modal below)
lab = {0.2: (0.0, 0.06, "center", "bottom"), 0.4: (0.0, -0.08, "center", "top"),
       0.6: (-0.04, 0.05, "right", "bottom"), 0.8: (0.04, 0.05, "left", "bottom"),
       1.0: (-0.05, -0.09, "right", "top")}
for x, a, n in zip(conf, acc, ns):
    dx, dy, ha, va = lab[round(x, 1)]
    ax.text(x + dx, a + dy, f"{a:.2f} (n={n})", ha=ha, va=va, fontsize=12.5, fontweight="bold")

ax.set_xlabel("stated confidence"); ax.set_ylabel("empirical accuracy")
ax.set_xlim(0.05, 1.12); ax.set_ylim(0.05, 1.14)
ax.set_xticks([0.2, 0.4, 0.6, 0.8, 1.0]); ax.set_yticks([0.25, 0.5, 0.75, 1.0])
ax.text(0.08, 0.99, f"ECE = {ece:.3f}", fontsize=18, fontweight="bold", va="top",
        color=F.COLORS["Instance-BEq"])
F.despine(ax)
ax.legend(loc="lower right", handlelength=1.6, borderpad=0.3)
F.save(fig, "calibration")
print("ECE =", round(ece, 3), "| levels:", list(zip(levels, [round(a, 3) for a in acc], ns)))
