"""Shared style for all Instance-BEq paper figures (AAAI/NeurIPS visual standard).

Principles: restrained categorical palette (ONE accent per method), NO titles/subtitles,
black edges with bold linewidth, large fonts, direct labels over legends, tight margins,
grayscale-safe (dark/mid/light + hatches), vector PDF output.
"""
from __future__ import annotations
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
LOG = ROOT / "eval_logs"
FIGDIR = ROOT / "paper" / "figures"
FIGDIR.mkdir(parents=True, exist_ok=True)

# One accent per method. Dark -> mid -> light so they separate in grayscale print.
COLORS = {
    "Instance-BEq":    "#16324f",   # deep navy  (ours, darkest = boldest)
    "majority-vote":   "#b35806",   # dark amber (baseline B)
    "LLM-judge":       "#e08214",   # amber      (mid grayscale)
    "BEq+":            "#4d8076",   # muted teal (statement-level baseline)
    "type-check-only": "#cdd2d7",   # light gray (palest = "blind")
}
HATCH = {  # redundant encoding for grayscale / colorblind safety
    "Instance-BEq": "", "majority-vote": "xx", "LLM-judge": "..",
    "BEq+": "\\\\", "type-check-only": "////",
}
# verdict-correctness colors for the instance x method matrix
CORRECT = "#dfe7ee"   # pale  (got it right)
MISS    = "#9b1d20"   # deep red (missed a true hollow — the dangerous error)
FALSE   = "#e08214"   # amber  (false alarm on a sound instance)

ACCENT = "#16324f"
GRID = "#b8bdc2"


def setup():
    plt.rcParams.update({
        "pdf.fonttype": 42, "ps.fonttype": 42,        # editable/embedded text
        "font.family": "serif",
        "font.size": 17,
        "axes.labelsize": 20, "axes.titlesize": 1,    # titles suppressed by design
        "xtick.labelsize": 17, "ytick.labelsize": 17,
        "legend.fontsize": 16, "legend.frameon": False,
        "axes.linewidth": 1.5, "lines.linewidth": 2.6,
        "patch.linewidth": 1.6, "patch.force_edgecolor": True,
        "hatch.linewidth": 1.1,
        "savefig.bbox": "tight", "savefig.pad_inches": 0.02,
    })


def despine(ax, keep=("left", "bottom")):
    for s in ("top", "right", "left", "bottom"):
        ax.spines[s].set_visible(s in keep)


def load(name):
    return json.loads((LOG / name).read_text(encoding="utf-8"))


def save(fig, name):
    out = FIGDIR / f"{name}.pdf"
    fig.savefig(out)
    plt.close(fig)
    print("wrote", out)
    return out
