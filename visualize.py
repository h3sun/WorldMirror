"""
GDELT Self-Coverage Tone - Multi-Panel Visualization
"""

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
from matplotlib.colors import LinearSegmentedColormap
import numpy as np

df = pd.read_csv("gdelt_tone_results.csv")
df = df.sort_values("avg_tone", ascending=False).reset_index(drop=True)

# ── Color helpers ──────────────────────────────────────────────────────────
CMAP = LinearSegmentedColormap.from_list(
    "tone", ["#d62728", "#ff7f7f", "#ffffff", "#74c476", "#006d2c"]
)

def tone_color(t, vmin=-4.5, vmax=2.5):
    return CMAP((t - vmin) / (vmax - vmin))

BAR_COLORS  = [tone_color(t) for t in df["avg_tone"]]
EDGE_COLORS = ["#555" for _ in df["avg_tone"]]

# ── Bubble size: proportional to log article count ─────────────────────────
log_n = np.log1p(df["article_count"])
bubble_size = (log_n / log_n.max() * 900) + 50

# ══════════════════════════════════════════════════════════════════════════════
fig = plt.figure(figsize=(22, 28), facecolor="#0e1117")
fig.patch.set_facecolor("#0e1117")

gs = gridspec.GridSpec(
    3, 2,
    figure=fig,
    height_ratios=[2.8, 1, 1],
    hspace=0.45, wspace=0.35,
    left=0.07, right=0.97, top=0.95, bottom=0.04
)

DARK  = "#0e1117"
PANEL = "#1a1f2e"
TEXT  = "#e8eaf0"
GRID  = "#2a2f3e"
ACCENT= "#61dafb"

def style_ax(ax, title=""):
    ax.set_facecolor(PANEL)
    for sp in ax.spines.values():
        sp.set_color(GRID)
    ax.tick_params(colors=TEXT, labelsize=9)
    ax.xaxis.label.set_color(TEXT)
    ax.yaxis.label.set_color(TEXT)
    if title:
        ax.set_title(title, color=ACCENT, fontsize=11, fontweight="bold", pad=8)
    ax.grid(color=GRID, linestyle=":", linewidth=0.6, alpha=0.8)

# ══════════════════════════════════════════════════════════════════════════════
# Panel 1 (top, full width): Horizontal bar chart – all 49 countries
# ══════════════════════════════════════════════════════════════════════════════
ax1 = fig.add_subplot(gs[0, :])
style_ax(ax1)

y = np.arange(len(df))
bars = ax1.barh(y, df["avg_tone"], color=BAR_COLORS,
                edgecolor=EDGE_COLORS, linewidth=0.4, height=0.78)

ax1.set_yticks(y)
ax1.set_yticklabels(df["country"], fontsize=8.5, color=TEXT)
ax1.invert_yaxis()
ax1.axvline(0, color="#aaa", linewidth=0.9, linestyle="--", alpha=0.6)

# Value labels
for bar, tone in zip(bars, df["avg_tone"]):
    xval = bar.get_width()
    offset = 0.06 if xval >= 0 else -0.06
    ax1.text(xval + offset, bar.get_y() + bar.get_height() / 2,
             f"{tone:+.2f}", va="center",
             ha="left" if xval >= 0 else "right",
             fontsize=7.2, color=TEXT, fontweight="bold")

ax1.set_xlabel("Weighted Average Tone Score", color=TEXT, fontsize=10)
ax1.set_title(
    "Which Countries Report Most Positively About Themselves?\n"
    "GDELT Web News · Last 1 Month · Query: '{country} sourcecountry:{FIPS}' | mode=tonechart",
    color=ACCENT, fontsize=12, fontweight="bold", pad=10
)

# Colorbar legend
sm = plt.cm.ScalarMappable(
    cmap=CMAP,
    norm=plt.Normalize(vmin=-4.5, vmax=2.5)
)
sm.set_array([])
cbar = fig.colorbar(sm, ax=ax1, orientation="horizontal",
                    fraction=0.012, pad=0.01, aspect=40)
cbar.ax.tick_params(colors=TEXT, labelsize=8)
cbar.set_label("Tone Score", color=TEXT, fontsize=8)
cbar.outline.set_edgecolor(GRID)

# ══════════════════════════════════════════════════════════════════════════════
# Panel 2 (middle-left): Bubble chart — tone vs positive ratio, size=volume
# ══════════════════════════════════════════════════════════════════════════════
ax2 = fig.add_subplot(gs[1, 0])
style_ax(ax2, "Tone Score vs Positive Article % (bubble = volume)")

sc = ax2.scatter(df["avg_tone"], df["positive_ratio"],
                 s=bubble_size, c=df["avg_tone"],
                 cmap=CMAP, vmin=-4.5, vmax=2.5,
                 edgecolors="#555", linewidths=0.5, alpha=0.88, zorder=3)

# Label notable countries
highlight = ["Saudi Arabia", "Vietnam", "China", "Iran",
             "Ukraine", "Israel", "United States", "Qatar", "Egypt"]
for _, row in df[df["country"].isin(highlight)].iterrows():
    ax2.annotate(
        row["country"],
        (row["avg_tone"], row["positive_ratio"]),
        textcoords="offset points", xytext=(5, 4),
        fontsize=7.5, color=TEXT, fontweight="bold",
        arrowprops=dict(arrowstyle="-", color="#888", lw=0.5)
    )

ax2.set_xlabel("Average Tone Score", color=TEXT)
ax2.set_ylabel("Positive Article %", color=TEXT)
ax2.axvline(0, color="#aaa", lw=0.8, ls="--", alpha=0.5)
ax2.axhline(50, color="#aaa", lw=0.8, ls="--", alpha=0.5)

# ══════════════════════════════════════════════════════════════════════════════
# Panel 3 (middle-right): Article volume top 15 (log scale)
# ══════════════════════════════════════════════════════════════════════════════
ax3 = fig.add_subplot(gs[1, 1])
style_ax(ax3, "Top 15 by Article Volume (log scale)")

top15_vol = df.nlargest(15, "article_count").sort_values("article_count")
bar_cols = [tone_color(t) for t in top15_vol["avg_tone"]]
ax3.barh(top15_vol["country"], top15_vol["article_count"],
         color=bar_cols, edgecolor="#555", linewidth=0.4, height=0.7)
ax3.set_xscale("log")
ax3.set_xlabel("Article Count (log)", color=TEXT)
ax3.tick_params(axis="y", labelsize=8.5, colors=TEXT)
for xv, name, tone in zip(top15_vol["article_count"],
                           top15_vol["country"],
                           top15_vol["avg_tone"]):
    ax3.text(xv * 1.05, name, f"  {tone:+.2f}",
             va="center", fontsize=7.5, color=TEXT)

# ══════════════════════════════════════════════════════════════════════════════
# Panel 4 (bottom-left): Top 10 most positive
# ══════════════════════════════════════════════════════════════════════════════
ax4 = fig.add_subplot(gs[2, 0])
style_ax(ax4, "Top 10 Most Positive Self-Coverage")

top10 = df.head(10).iloc[::-1]
cols4 = [tone_color(t) for t in top10["avg_tone"]]
hb = ax4.barh(top10["country"], top10["avg_tone"],
              color=cols4, edgecolor="#555", linewidth=0.4, height=0.7)
for bar, tone in zip(hb, top10["avg_tone"]):
    ax4.text(bar.get_width() + 0.05, bar.get_y() + bar.get_height() / 2,
             f"{tone:+.3f}", va="center", fontsize=8.5, color="#74c476",
             fontweight="bold")
ax4.set_xlabel("Average Tone Score", color=TEXT)
ax4.tick_params(axis="y", labelsize=9, colors=TEXT)
ax4.set_xlim(0, 2.8)

# ══════════════════════════════════════════════════════════════════════════════
# Panel 5 (bottom-right): Bottom 10 most negative
# ══════════════════════════════════════════════════════════════════════════════
ax5 = fig.add_subplot(gs[2, 1])
style_ax(ax5, "Bottom 10 Most Negative Self-Coverage")

bot10 = df.tail(10)
cols5 = [tone_color(t) for t in bot10["avg_tone"]]
hb5 = ax5.barh(bot10["country"], bot10["avg_tone"],
               color=cols5, edgecolor="#555", linewidth=0.4, height=0.7)
for bar, tone in zip(hb5, bot10["avg_tone"]):
    ax5.text(bar.get_width() - 0.08, bar.get_y() + bar.get_height() / 2,
             f"{tone:+.3f}", va="center", fontsize=8.5, color="#ff7f7f",
             fontweight="bold", ha="right")
ax5.set_xlabel("Average Tone Score", color=TEXT)
ax5.tick_params(axis="y", labelsize=9, colors=TEXT)
ax5.axvline(0, color="#aaa", lw=0.8, ls="--", alpha=0.5)

# ── Footer ─────────────────────────────────────────────────────────────────
fig.text(
    0.5, 0.015,
    "Data: GDELT Project (api.gdeltproject.org) · Web news · 2026-02-06 to 2026-03-06 · "
    "Tone = weighted mean of doc-level tone histogram",
    ha="center", fontsize=8, color="#888"
)

out = "gdelt_self_tone_dashboard.png"
plt.savefig(out, dpi=160, bbox_inches="tight", facecolor=DARK)
print(f"Saved: {out}")
