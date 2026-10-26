"""Regenerate every figure in the proposal from numbers reported in the
Oct 4 2026 progress report (no trace access needed).

Run:  python scripts/make_figures.py      (writes figures/*.pdf)
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

OUT = Path(__file__).resolve().parent.parent / "figures"
OUT.mkdir(exist_ok=True)

# Reference categorical palette (fixed order) + neutral ink.
BLUE, ORANGE, AQUA, YELLOW, VIOLET = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#6250d6"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 9,
    "axes.edgecolor": INK2,
    "axes.labelcolor": INK,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.6,
    "xtick.color": INK2,
    "ytick.color": INK2,
    "legend.frameon": False,
    "savefig.bbox": "tight",
})


def save(fig, name):
    fig.savefig(OUT / f"{name}.pdf")
    plt.close(fig)


# 1. Model A risk/reclaim trade-off on unseen clusters --------------------------
def fig_tradeoff():
    fig, ax = plt.subplots(figsize=(4.6, 3.0))
    pts = {
        "A1 history rule": (0.7, 11.0, BLUE),
        "A2 linear QR": (1.4, 12.9, ORANGE),
        "A3 XGBoost QR": (2.0, 14.3, AQUA),
    }
    for name, (u, r, c) in pts.items():
        ax.scatter(u, r, s=55, color=c, edgecolor="white", linewidth=1.5, zorder=3, label=name)
    # Matched-risk operating point (U = 5%).
    ax.scatter(5, 20.8, s=55, marker="s", color=BLUE, edgecolor="white", linewidth=1.5, zorder=3)
    ax.scatter(5, 21.9, s=55, marker="s", color=AQUA, edgecolor="white", linewidth=1.5, zorder=3)
    ax.plot([0.7, 5], [11.0, 20.8], color=BLUE, lw=1.2, ls="--")
    ax.plot([2.0, 5], [14.3, 21.9], color=AQUA, lw=1.2, ls="--")
    ax.axvline(5, color=INK2, lw=0.8, ls=":")
    ax.annotate("5% safety budget", (5, 9.6), xytext=(3.15, 9.6), color=INK2, fontsize=8)
    ax.annotate("A3 21.9%", (5, 21.9), xytext=(5.2, 22.4), fontsize=8, color=INK)
    ax.annotate("A1 20.8%", (5, 20.8), xytext=(5.2, 19.9), fontsize=8, color=INK)
    ax.set_xlim(0, 6.6)
    ax.set_ylim(8, 24)
    ax.set_xlabel("Under-provisioned pods, U (%)")
    ax.set_ylabel("Reserved GPU-hours reclaimed, R (%)")
    ax.legend(loc="upper left", fontsize=8)
    save(fig, "fig_tradeoff")


# 2. Where savings come from -------------------------------------------------
def fig_segments():
    groups = ["Rec,\nwith history", "Rec,\nno history", "GenAI,\nwith history", "GenAI,\nno history"]
    a1 = [33.3, 0.0, 8.3, 0.0]
    a3 = [42.6, 8.1, 8.1, 0.0]
    x = np.arange(len(groups))
    w = 0.36
    fig, ax = plt.subplots(figsize=(4.8, 2.8))
    b1 = ax.bar(x - w / 2 - 0.01, a1, w, color=BLUE, label="A1 history rule")
    b3 = ax.bar(x + w / 2 + 0.01, a3, w, color=AQUA, label="A3 XGBoost QR")
    for bars in (b1, b3):
        for b in bars:
            h = b.get_height()
            ax.text(b.get_x() + b.get_width() / 2, h + 0.8, f"{h:.1f}", ha="center", fontsize=7.5, color=INK)
    ax.set_xticks(x, groups)
    ax.set_ylabel("Reserved GPU-hours reclaimed (%)")
    ax.set_ylim(0, 50)
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper right", fontsize=8)
    save(fig, "fig_segments")


# 3. Model B transfer gap ----------------------------------------------------
def fig_modelb():
    models = ["B1 logistic", "B2 random forest", "B3 LightGBM"]
    seen = [0.640, 0.754, 0.754]
    unseen = [0.575, 0.671, 0.651]
    ece_seen = [0.067, 0.044, 0.053]
    ece_unseen = [0.123, 0.112, 0.121]
    fig, axes = plt.subplots(1, 2, figsize=(6.2, 2.4))
    y = np.arange(len(models))[::-1]
    for ax, a, b, lab, lim in (
        (axes[0], seen, unseen, "ROC-AUC (higher is better)", (0.5, 0.8)),
        (axes[1], ece_seen, ece_unseen, "ECE (lower is better)", (0.0, 0.14)),
    ):
        for yi, s, u in zip(y, a, b):
            ax.plot([s, u], [yi, yi], color=GRID, lw=3, zorder=1)
        ax.scatter(a, y, color=BLUE, s=40, zorder=3, label="Seen clusters")
        ax.scatter(b, y, color=ORANGE, s=40, zorder=3, label="Unseen clusters")
        ax.set_yticks(y, models)
        ax.set_xlim(*lim)
        ax.set_xlabel(lab)
        ax.grid(axis="y", visible=False)
    axes[1].set_yticklabels([])
    axes[0].legend(loc="lower left", bbox_to_anchor=(0.0, 1.02), ncol=2, fontsize=7.5)
    fig.tight_layout()
    save(fig, "fig_modelb")


# 4. A+B composition: reclaim vs support --------------------------------------
def fig_composition():
    caps = ["None", "+10 pts", "+5 pts", "+2 pts"]
    reclaimed = [11.4, 7.3, 5.3, 3.4]
    support = [12.0, 8.1, 5.5, 3.6]
    shrunk = [27.5, 20.3, 15.2, 10.5]
    x = np.arange(len(caps))
    fig, ax = plt.subplots(figsize=(4.8, 2.8))
    ax.plot(x, shrunk, marker="o", color=VIOLET, lw=2, label="Pods shrunk")
    ax.plot(x, reclaimed, marker="o", color=AQUA, lw=2, label="GPU-hours reclaimed")
    ax.plot(x, support, marker="o", color=ORANGE, lw=2, label="Shrunk sizes seen in training")
    for xi, v in zip(x, reclaimed):
        ax.text(xi, v - 2.2, f"{v}", ha="center", fontsize=7.5, color=INK)
    ax.set_xticks(x, caps)
    ax.set_xlabel("Per-pod cap on increase in predicted failure risk")
    ax.set_ylabel("Share (%)")
    ax.set_ylim(0, 31)
    ax.legend(loc="upper right", fontsize=7.5)
    save(fig, "fig_composition")


# 5. Slice-grid quantisation: why GenAI keeps whole GPUs ------------------------
def fig_quantisation():
    # Illustrative grid: only the top of the 27-size grid matters here, and
    # the report states the jumps 0.5 -> 0.7 -> 1.0.
    grid = np.array([0.1, 0.2, 0.25, 0.3, 0.4, 0.5, 0.7, 1.0])
    need = np.linspace(0.01, 1.0, 400)
    alloc = np.array([grid[np.searchsorted(grid, n)] for n in need])
    fig, ax = plt.subplots(figsize=(4.6, 2.8))
    ax.fill_between(need, need, alloc, step=None, color=YELLOW, alpha=0.25, lw=0, label="Stranded by slice rounding")
    ax.plot(need, alloc, color=BLUE, lw=2, label="Allocated slice")
    ax.plot(need, need, color=INK2, lw=1, ls="--", label="Predicted need + margin")
    ax.axvline(0.231, color=AQUA, lw=1.2)
    ax.axvline(0.983, color=ORANGE, lw=1.2)
    ax.text(0.245, 0.9, "rec median\nneed 0.231", fontsize=7.5, color=INK)
    ax.text(0.70, 0.18, "GenAI median\nneed 0.983", fontsize=7.5, color=INK)
    ax.set_xlabel("GPU fraction needed (P90 of busy hours)")
    ax.set_ylabel("GPU fraction allocated")
    ax.set_xlim(0, 1.02)
    ax.set_ylim(0, 1.05)
    ax.legend(loc="upper left", fontsize=7.5, bbox_to_anchor=(0.0, 0.83))
    save(fig, "fig_quantisation")


# 6. Business value sensitivity ---------------------------------------------
def fig_value():
    # Annual $ freed per 1,000 reserved inference GPUs, by price and savings rate.
    price = np.linspace(1.0, 6.0, 100)  # $/GPU-hour
    hours = 8760
    fig, ax = plt.subplots(figsize=(4.8, 2.9))
    tiers = (
        (0.25, AQUA, "25% opportunity (upper)"),
        (0.21, BLUE, "21% opportunity (U = 5%)"),
        (0.114, ORANGE, "11.4% A+B, no risk cap"),
        (0.034, VIOLET, "3.4% A+B, +2 pt risk cap"),
    )
    for rate, c, lab in tiers:
        ax.plot(price, 1000 * hours * price * rate / 1e6, color=c, lw=2, label=lab)
    for p, lab in ((1.0, "A10-class\n~$1"), (3.43, "A100\n$3.43"), (3.90, "H100\n$3.90")):
        ax.axvline(p, color=GRID, lw=1, zorder=0)
        ax.text(p + 0.05, 12.6, lab, fontsize=6.5, color=INK2, va="top")
    ax.set_xlabel("Effective cost per GPU-hour (USD)")
    ax.set_ylabel("Annual cost freed per\n1,000 reserved GPUs ($M)")
    ax.set_xlim(1, 6)
    ax.set_ylim(0, 14)
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), fontsize=7.5)
    save(fig, "fig_value")


# 7. Utilisation -> servers saved (doc 1 equation) ------------------------------
def fig_util():
    r1 = np.array([0.28])
    r2 = np.linspace(0.28, 0.70, 200)
    fig, ax = plt.subplots(figsize=(4.4, 2.6))
    ax.plot(r2 * 100, (r2 - r1) / r2 * 100, color=BLUE, lw=2)
    ax.scatter([40], [30], color=ORANGE, s=40, zorder=3)
    ax.annotate("28% -> 40%: 30% of\nservers freeable", (40, 30), xytext=(45, 18), fontsize=7.5,
                arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8))
    ax.set_xlabel("Target utilisation R2 (%), from R1 = 28%")
    ax.set_ylabel("Fleet freed, X/N (%)")
    save(fig, "fig_util")


if __name__ == "__main__":
    for f in (fig_tradeoff, fig_segments, fig_modelb, fig_composition, fig_quantisation, fig_value, fig_util):
        f()
    print("wrote", sorted(p.name for p in OUT.glob("*.pdf")))
