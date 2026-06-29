#!/usr/bin/env python3
"""Method overview schematic (Figure 1) — icon-driven, conceptual (not from a result file).
Pipeline: informal problem -> SITA -> generated Lean (def/instance/theorem) -> the three checks
-> certificate. The headline check is drawn as a magnifying glass that reveals a hidden `sorry`
inside an instance whose surface type-checks. Designed so no text overflows / overlaps.
"""
import numpy as np
import figstyle as F
F.setup()
import matplotlib.pyplot as plt
plt.rcParams["font.family"] = "DejaVu Sans"
from matplotlib.patches import (FancyBboxPatch, Circle, Polygon, RegularPolygon, Arc)

NAVY = F.COLORS["Instance-BEq"]; GREY = "#c7ccd1"
GREEN, RED = "#2e7d32", "#9b1d20"

# ----------------------------- primitives --------------------------------------------------
def panel(ax, x, y, w, h, fc, ec=NAVY, lw=1.9, r=0.05, ls="-"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0.01,rounding_size={r}",
                                fc=fc, ec=ec, lw=lw, ls=ls, zorder=2, mutation_aspect=0.85))

def arrow(ax, p1, p2, color=NAVY, lw=2.4, ls="-"):
    ax.annotate("", xy=p2, xytext=p1, zorder=1,
                arrowprops=dict(arrowstyle="-|>", color=color, lw=lw, ls=ls,
                                shrinkA=2, shrinkB=2, mutation_scale=20))

def T(ax, x, y, s, fs=11, w="normal", c="black", ha="center", va="center", fam=None, st="normal"):
    ax.text(x, y, s, fontsize=fs, fontweight=w, color=c, ha=ha, va=va, zorder=6,
            family=fam, fontstyle=st, linespacing=1.2)

# ----------------------------- icons -------------------------------------------------------
def doc(ax, x, y, s=1.0, fc="white", ec="#444", lines=(GREEN, RED, NAVY)):
    w, h, f = 0.62*s, 0.84*s, 0.2*s
    x0, y0 = x-w/2, y-h/2
    ax.add_patch(Polygon([(x0,y0),(x0,y0+h),(x0+w-f,y0+h),(x0+w,y0+h-f),(x0+w,y0)],
                         closed=True, fc=fc, ec=ec, lw=1.7, zorder=3))
    ax.add_patch(Polygon([(x0+w-f,y0+h),(x0+w-f,y0+h-f),(x0+w,y0+h-f)], fc="#e6e6e6", ec=ec, lw=1.2, zorder=4))
    for i, col in enumerate(lines):
        yy = y0 + h - (0.30 + 0.205*i)*s
        ax.plot([x0+0.12*s, x0+w-0.12*s], [yy, yy], color=col, lw=3.0*s, solid_capstyle="round", zorder=4)

def gear(ax, x, y, s=1.0, color=NAVY):
    R = 0.30*s
    for a in np.linspace(0, 2*np.pi, 9, endpoint=False):
        ax.plot([x+R*np.cos(a), x+(R+0.13*s)*np.cos(a)], [y+R*np.sin(a), y+(R+0.13*s)*np.sin(a)],
                color=color, lw=3.4*s, solid_capstyle="round", zorder=3)
    ax.add_patch(Circle((x, y), R, fc="white", ec=color, lw=2.8*s, zorder=4))
    ax.add_patch(Circle((x, y), 0.10*s, fc=color, zorder=5))

def scale(ax, x, y, s=1.0, color=NAVY):
    bw = 0.46*s
    ax.plot([x-bw, x+bw], [y+0.22*s, y+0.22*s], color=color, lw=3.2*s, solid_capstyle="round", zorder=4)
    ax.plot([x, x], [y+0.22*s, y-0.22*s], color=color, lw=3.2*s, zorder=4)
    ax.add_patch(Polygon([(x-0.17*s, y-0.22*s), (x+0.17*s, y-0.22*s), (x, y-0.02*s)], fc=color, zorder=3))
    for sg in (-1, 1):
        px = x+sg*bw
        ax.plot([px, px], [y+0.22*s, y+0.05*s], color=color, lw=1.6*s, zorder=4)
        ax.add_patch(Arc((px, y+0.03*s), 0.26*s, 0.16*s, theta1=180, theta2=360, color=color, lw=2.6*s, zorder=4))

def magnifier(ax, x, y, s=1.0, ring=NAVY):
    R = 0.34*s
    ax.add_patch(Circle((x, y), R, fc="white", ec=ring, lw=3.2*s, zorder=7))
    ax.plot([x+R*0.7, x+R*1.32], [y-R*0.7, y-R*1.32], color=ring, lw=5.2*s, solid_capstyle="round", zorder=6)
    return R

def nested(ax, x, y, s=1.0, outer=GREY, inner=NAVY):
    panel(ax, x-0.5*s, y-0.42*s, 1.0*s, 0.84*s, "white", outer, lw=2.2, r=0.06)
    panel(ax, x-0.02*s, y-0.38*s, 0.46*s, 0.46*s, "#eef0f6", inner, lw=2.0, r=0.05)
    T(ax, x+0.21*s, y-0.15*s, "inst", 7.5, "bold", inner)
    T(ax, x-0.43*s, y+0.23*s, "abstract", 7.5, "bold", "#5d646b", ha="left")

def seal(ax, x, y, s=1.0, color=GREEN):
    ax.add_patch(RegularPolygon((x, y), 16, radius=0.40*s, orientation=np.pi/16, fc=color, ec="white", lw=1.2, zorder=4))
    ax.add_patch(Circle((x, y), 0.30*s, fc="white", ec=color, lw=2.6*s, zorder=5))
    T(ax, x, y+0.02*s, "✓", 20*s, "bold", color)
    for sg in (-1, 1):
        ax.add_patch(Polygon([(x+sg*0.10*s, y-0.30*s), (x+sg*0.10*s, y-0.66*s),
                              (x+sg*0.26*s, y-0.54*s), (x+sg*0.22*s, y-0.36*s)], fc=color, zorder=3))

def chip(ax, x, y, w, h, color, label):
    ax.add_patch(FancyBboxPatch((x-w/2, y-h/2), w, h, boxstyle="round,pad=0.01,rounding_size=0.08",
                                fc=color, ec="black", lw=1.4, zorder=4))
    T(ax, x, y, label, 10, "bold", "white")

# ----------------------------- layout ------------------------------------------------------
fig, ax = plt.subplots(figsize=(14.8, 7.4))
ax.set_xlim(0, 14.8); ax.set_ylim(0, 7.4); ax.axis("off")

# Stage A — input (far left, stacked)
doc(ax, 1.15, 6.35, 1.25)
T(ax, 1.15, 5.55, "Informal problem", 11.5, "bold")
T(ax, 1.15, 5.18, "min ½‖Ax−b‖²", 10.5, fam="monospace")
arrow(ax, (1.15, 4.85), (1.15, 4.30), "black")
gear(ax, 1.15, 3.75, 1.2)
T(ax, 1.15, 2.95, "SITA", 12, "bold", NAVY)
T(ax, 1.15, 2.62, "autoformalizer", 10)
arrow(ax, (1.95, 3.75), (2.55, 3.75), "black")

# Stage B — generated Lean file (three labelled artifact chips)
panel(ax, 2.6, 1.7, 2.5, 4.25, "#fbfbf9")
T(ax, 3.85, 5.6, "Generated Lean file", 11, "bold", NAVY)
chip(ax, 3.85, 4.82, 1.95, 0.52, GREEN, "def  f")
chip(ax, 3.85, 4.10, 1.95, 0.52, RED, "instance  ⚠")
chip(ax, 3.85, 3.38, 1.95, 0.52, NAVY, "theorem")
T(ax, 3.85, 2.72, "✓ type-checks (0 errors)", 10, "bold", GREEN)
T(ax, 3.85, 2.36, "sorry is only a warning", 9, "normal", RED, st="italic")
# split to the three checks (colour-matched to the artifact each check targets)
arrow(ax, (4.83, 4.82), (5.58, 5.95), GREEN, lw=2.2)
arrow(ax, (4.83, 4.10), (5.58, 4.10), RED, lw=2.5)     # horizontal into box 2
arrow(ax, (4.83, 3.38), (5.58, 1.45), NAVY, lw=2.2)

# Stage C — three checks (icon at left of each panel, short text at right)
cx, cw = 5.6, 5.05
# (1) Definitional — balance scale
panel(ax, cx, 5.29, cw, 1.55, "#f4f7fb")
scale(ax, cx+0.78, 6.04, 1.0)
T(ax, cx+1.55, 6.57, "① Definitional faithfulness", 11.5, "bold", NAVY, ha="left")
T(ax, cx+1.55, 6.07, "prove  def  =  reference", 10.5, ha="left")
T(ax, cx+1.55, 5.69, "(tactic ensemble)  →  ", 10, ha="left")
T(ax, cx+3.55, 5.69, "✓ exact", 10.5, "bold", GREEN, ha="left")
# (2) Instance soundness — magnifier reveals a hidden sorry  [HEADLINE]
panel(ax, cx, 2.68, cw, 2.28, "#fbf4ef", lw=2.6)
T(ax, cx+0.18, 4.68, "② Instance soundness   ★", 12, "bold", NAVY, ha="left")
# a mini instance card the surface of which looks fine
panel(ax, cx+0.2, 3.11, 1.72, 1.34, "white", "#888", lw=1.5)
T(ax, cx+0.42, 4.18, "instance", 8.5, "bold", "#444", ha="left")
T(ax, cx+0.42, 3.84, "hl := pos_l", 8.5, fam="monospace", c="#444", ha="left")
T(ax, cx+0.42, 3.50, "update :=", 8.5, fam="monospace", c="#444", ha="left")
magnifier(ax, cx+1.53, 3.48, 0.88)
ax.text(cx+1.53, 3.49, "sorry", fontsize=8.5, fontweight="bold", color=RED,
        ha="center", va="center", zorder=9)            # revealed in the lens
arrow(ax, (cx+2.1, 3.76), (cx+2.62, 3.76), RED, lw=2.4)
T(ax, cx+2.72, 4.18, "#print axioms", 9.3, "bold", NAVY, ha="left", fam="monospace")
T(ax, cx+2.72, 3.72, "clean → SOUND", 10.0, "bold", GREEN, ha="left")
T(ax, cx+2.72, 3.34, "sorryAx → HOLLOW", 10.0, "bold", RED, ha="left")
T(ax, cx+0.22, 2.88, "decidable & exact — type-checking is blind", 9.2, "normal", RED, ha="left", st="italic")
# (3) Theorem transfer — nested specialization
panel(ax, cx, 0.5, cw, 1.85, "#f4f7fb")
nested(ax, cx+0.84, 1.3, 1.2)
T(ax, cx+1.65, 2.02, "③ Theorem transfer", 11.5, "bold", NAVY, ha="left")
T(ax, cx+1.65, 1.55, "3a  apply abstract thm → valid", 10.2, ha="left")
T(ax, cx+1.65, 1.15, "3b  back-translate ⇄ informal", 10.2, ha="left")
T(ax, cx+1.65, 0.82, "(LLM, calibrated)", 9, "normal", "#5d646b", ha="left", st="italic")

# arrows checks -> certificate (box 2 exits horizontally)
arrow(ax, (cx+cw, 5.95), (11.1, 3.82), NAVY, lw=1.8)
arrow(ax, (cx+cw, 3.6), (11.1, 3.6), NAVY, lw=1.8)
arrow(ax, (cx+cw, 1.45), (11.1, 3.38), NAVY, lw=1.8)

# Stage D — certificate seal
panel(ax, 11.1, 2.35, 3.35, 2.5, "#e9eef6", lw=2.6)
seal(ax, 12.78, 4.2, 1.05)
T(ax, 12.78, 3.08, "Faithfulness certificate", 11.5, "bold", NAVY)
T(ax, 12.78, 2.74, "①  ∧  ②  ∧  ③a", 12.5, "bold", "#16213a")
T(ax, 12.78, 2.48, "(formal) + ③b (LLM bridge)", 9, "normal", "#5d646b", st="italic")

F.save(fig, "overview")
