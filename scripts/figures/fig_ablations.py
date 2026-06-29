#!/usr/bin/env python3
"""Two check-1 ablations side by side: (A) reference-source -- definitional certification coverage
by where the reference comes from (curated/property vs few-shot vs zero-shot 7B); (B) tactic-
ensemble size -- coverage on equivalent references grows with the ensemble while false
certifications on corruptions stay zero at every size.
Sources: eval_logs/ref_source_ablation_result.json, eval_logs/tactic_size_sweep_result.json (real).
"""
import numpy as np
import figstyle as F
F.setup()
import matplotlib.pyplot as plt

NAVY = F.COLORS["Instance-BEq"]; GREY = "#cdd2d7"; RED = "#9b1d20"
fig, (axA, axB) = plt.subplots(1, 2, figsize=(12.6, 4.4))

# ---- A: reference source -> coverage ------------------------------------------------------
ra = F.load("ref_source_ablation_result.json")["summary"]
arms = [("curated /\nproperty", "curated"), ("LLM\nfew-shot", "fewshot"), ("LLM\nzero-shot", "zeroshot")]
cov = [ra[k]["coverage"] for _, k in arms]
cols = [NAVY, "#6a89a8", GREY]
b = axA.bar(np.arange(3), cov, 0.6, color=cols, edgecolor="black", zorder=3)
for i, v in enumerate(cov):
    axA.text(i, v + 0.025, f"{v:.2f}", ha="center", va="bottom", fontsize=15, fontweight="bold")
axA.set_xticks(np.arange(3)); axA.set_xticklabels([n for n, _ in arms])
axA.set_ylabel("Definitional coverage"); axA.set_ylim(0, 1.0)
axA.set_xlabel("(A)  reference source")
# every arm makes zero false certifications (precision 1 by kernel soundness) -- one clean note
axA.text(0.5, 0.92, "false certifications $= 0$ for every arm\n(precision $1$ by kernel soundness)",
         transform=axA.transAxes, ha="center", va="top", fontsize=11.5, style="italic", color="#444a50")
F.despine(axA)

# ---- B: tactic-ensemble size -> coverage@k --------------------------------------------------
ts = F.load("tactic_size_sweep_result.json")
cov_k = ts["coverage_at_k"]; fc_k = ts["false_cert_at_k"]; ne = ts["n_equiv"]; nc = ts["n_corrupt"]
k = np.arange(1, len(cov_k) + 1)
axB.plot(k, [c / ne for c in cov_k], "-o", color=NAVY, lw=2.8, ms=9, mec="black", zorder=4,
         label=f"equiv. coverage (/{ne})")
axB.plot(k, [f / nc for f in fc_k], "--s", color=RED, lw=2.4, ms=8, mec="black", zorder=4,
         label=f"corrupt. certified (/{nc})")
for ki, c in zip(k, cov_k):
    dy = -0.09 if c / ne > 0.9 else 0.04          # labels below the top points so they don't clip
    va = "top" if c / ne > 0.9 else "bottom"
    axB.text(ki, c / ne + dy, f"{c}/{ne}", ha="center", va=va, fontsize=12, fontweight="bold")
axB.set_xticks(k); axB.set_ylim(-0.05, 1.14)
axB.set_xlabel("(B)  tactic-ensemble size $k$"); axB.set_ylabel("fraction")
axB.legend(loc="upper left", bbox_to_anchor=(0.02, 0.99), fontsize=12.5, handlelength=1.6)
axB.axhline(0, color="black", lw=1.0)
F.despine(axB)

F.save(fig, "ablations")
