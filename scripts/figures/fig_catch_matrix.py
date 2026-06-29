#!/usr/bin/env python3
"""NOVEL FIG — "what each method catches vs misses", per instance.
Rationale: a P/R table hides WHERE methods fail; this strip makes the type-check blind spot
visceral (a solid band of missed hollow instances) and shows the LLM-judge's scattered false
alarms, while Instance-BEq is uniformly correct. Source (real): eval_logs/soundness_methods_result.json.
Supports §B and objection R1 (the type-check blind spot) and R2 (LLM unreliability).
"""
import numpy as np
import figstyle as F
F.setup()
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch

d = F.load("soundness_methods_result.json")
items = d["items"]
# order columns: sound instances first, then hollow
items = sorted(items, key=lambda it: (it["truth"] != "sound",))
n_sound = sum(it["truth"] == "sound" for it in items)
methods = ["Instance-BEq", "LLM-judge", "type-check-only"]

# code: 0 correct, 1 miss (true hollow not caught), 2 false alarm (sound flagged hollow)
def code(truth, pred):
    if truth == pred:
        return 0
    return 1 if truth == "hollow" else 2

M = np.array([[code(it["truth"], it[{"Instance-BEq": "certifier", "LLM-judge": "llm_judge",
                                      "type-check-only": "typecheck"}[m]]) for it in items]
              for m in methods])
cmap = ListedColormap([F.CORRECT, F.MISS, F.FALSE])

fig, ax = plt.subplots(figsize=(8.0, 2.6))
ax.imshow(M, cmap=cmap, vmin=0, vmax=2, aspect="auto")
# crisp cell borders
ax.set_xticks(np.arange(-.5, len(items), 1), minor=True)
ax.set_yticks(np.arange(-.5, len(methods), 1), minor=True)
ax.grid(which="minor", color="black", linewidth=1.0)
ax.tick_params(which="minor", length=0)
ax.set_yticks(range(len(methods))); ax.set_yticklabels(methods)
ax.set_xticks([])
# divider sound|hollow + group labels (placed BELOW the strip to avoid the top legend)
ax.axvline(n_sound - 0.5, color="black", lw=2.6)
yb = len(methods) - 0.5 + 0.34
ax.text((n_sound - 1) / 2, yb, f"sound ({n_sound})", ha="center", va="top", fontsize=14)
ax.text(n_sound + (len(items) - n_sound - 1) / 2, yb,
        f"hollow ({len(items) - n_sound})", ha="center", va="top", fontsize=14)
# per-row error tallies, direct
for r, m in enumerate(methods):
    miss = int((M[r] == 1).sum()); false = int((M[r] == 2).sum())
    note = "all correct" if miss == 0 and false == 0 else \
        (f"{miss} missed" if false == 0 else f"{false} false alarms")
    ax.text(len(items) - 0.3, r, note, va="center", ha="left", fontsize=13, fontweight="bold")
ax.set_xlim(-0.5, len(items) + 5.5)
ax.set_ylim(len(methods) - 0.5 + 1.0, -1.4)   # headroom for legend (top), labels (bottom)
for s in ("top", "right", "left", "bottom"):
    ax.spines[s].set_visible(False)
leg = [Patch(facecolor=F.CORRECT, edgecolor="black", label="correct"),
       Patch(facecolor=F.MISS, edgecolor="black", label="missed hollow"),
       Patch(facecolor=F.FALSE, edgecolor="black", label="false alarm")]
ax.legend(handles=leg, loc="lower center", ncol=3, bbox_to_anchor=(0.45, 1.02),
          handlelength=1.1, columnspacing=1.0)
F.save(fig, "catch_matrix")
