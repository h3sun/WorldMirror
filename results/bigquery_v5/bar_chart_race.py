"""
Bar Chart Race: Global Cross-Coverage Dynamics
================================================
Strategy: source_country acts as the "time axis", ordered by total article output.
Each frame accumulates one more source country's reporting, revealing which
target countries attract the most global media attention over time.
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.animation import FuncAnimation, FFMpegWriter
import matplotlib.colors as mcolors
import matplotlib.font_manager as fm

# Use a CJK-compatible system font
_cjk_fonts = ["PingFang SC", "Hiragino Sans GB", "Heiti TC", "Arial Unicode MS"]
for _f in _cjk_fonts:
    if any(f.name == _f for f in fm.fontManager.ttflist):
        matplotlib.rcParams["font.family"] = _f
        break

# ── 1. Load & Clean ──────────────────────────────────────────────────────────
df = pd.read_csv("/Users/haihaosun/Desktop/GitHub/WorldMirror/results/bigquery_v5/cross_coverage.csv")
df = df.dropna(subset=["source_country", "target_country", "article_count"])
df["article_count"] = pd.to_numeric(df["article_count"], errors="coerce").fillna(0)

# ── 2. Order Sources by Total Output (most active reporters first) ────────────
source_order = (
    df.groupby("source_country")["article_count"]
    .sum()
    .sort_values(ascending=False)
    .index.tolist()
)

# ── 3. Build Cumulative Coverage Matrix ──────────────────────────────────────
# Pivot: rows = source_country (ordered), cols = target_country, values = article_count
pivot = df.pivot_table(
    index="source_country",
    columns="target_country",
    values="article_count",
    aggfunc="sum",
    fill_value=0,
).reindex(source_order)

# Cumulative sum across sources → shape: (n_sources, n_targets)
cumulative = pivot.cumsum()

# ── 4. Animation Parameters ──────────────────────────────────────────────────
TOP_N = 12          # bars to display per frame
N_INTERP = 8        # interpolation steps between keyframes
FPS = 24
DWELL_FRAMES = 3    # extra frames at each keyframe to let viewer read
BAR_ALPHA = 0.88

# ── 5. Build Frame Sequence (keyframe + interpolated) ────────────────────────
keyframes = cumulative.values            # shape (48, n_targets)
targets = cumulative.columns.tolist()    # all target country names

frames = []
sources_shown = []

for i in range(len(source_order)):
    kf_current = keyframes[i]
    kf_prev = keyframes[i - 1] if i > 0 else np.zeros_like(kf_current)

    n_steps = N_INTERP if i > 0 else 1
    for t in range(n_steps):
        alpha = (t + 1) / n_steps
        interp = kf_prev + alpha * (kf_current - kf_prev)
        frames.append(interp)
        sources_shown.append(source_order[i])

    # dwell at keyframe
    for _ in range(DWELL_FRAMES):
        frames.append(kf_current.copy())
        sources_shown.append(source_order[i])

# ── 6. Color Palette ─────────────────────────────────────────────────────────
N_COLORS = len(targets)
cmap = plt.cm.get_cmap("tab20", N_COLORS)
country_color = {c: mcolors.to_hex(cmap(i % N_COLORS)) for i, c in enumerate(targets)}

# ── 7. Figure Setup ──────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(14, 8))
fig.patch.set_facecolor("#0d1117")
ax.set_facecolor("#0d1117")
ax.tick_params(colors="white", labelsize=11)
for spine in ax.spines.values():
    spine.set_visible(False)
ax.xaxis.label.set_color("white")
ax.yaxis.label.set_color("white")

title_text = ax.set_title(
    "全球报道覆盖率动态分布  |  Global Cross-Coverage Race",
    color="white", fontsize=16, fontweight="bold", pad=16
)
subtitle_text = fig.text(
    0.5, 0.92,
    "累计报道量（文章数）· Cumulative Article Count",
    ha="center", color="#aaaaaa", fontsize=11
)
source_label = ax.text(
    0.97, 0.03, "",
    transform=ax.transAxes,
    ha="right", va="bottom", fontsize=12,
    color="#58a6ff", fontweight="bold"
)
counter_label = ax.text(
    0.02, 0.03, "",
    transform=ax.transAxes,
    ha="left", va="bottom", fontsize=10,
    color="#8b949e"
)

def format_count(n):
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    elif n >= 1_000:
        return f"{n/1_000:.0f}K"
    return str(int(n))

# ── 8. Animation Update ──────────────────────────────────────────────────────
def update(frame_idx):
    ax.cla()
    ax.set_facecolor("#0d1117")
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(colors="white", labelsize=11)

    values = frames[frame_idx]
    src = sources_shown[frame_idx]

    # Get top-N countries
    top_idx = np.argsort(values)[-TOP_N:]
    top_countries = [targets[i] for i in top_idx]
    top_values = [values[i] for i in top_idx]
    colors = [country_color[c] for c in top_countries]

    bars = ax.barh(
        range(TOP_N), top_values,
        color=colors, alpha=BAR_ALPHA,
        height=0.75, edgecolor="none"
    )

    # Value labels on bars
    max_val = max(top_values) if max(top_values) > 0 else 1
    for j, (bar, val, country) in enumerate(zip(bars, top_values, top_countries)):
        label_x = val + max_val * 0.01
        ax.text(label_x, j, format_count(val),
                va="center", ha="left", color="white", fontsize=10, fontweight="bold")

    # Country name labels
    ax.set_yticks(range(TOP_N))
    ax.set_yticklabels(top_countries, color="white", fontsize=12)
    ax.tick_params(axis="y", length=0)

    # X-axis formatting
    ax.set_xlim(0, max_val * 1.22)
    ax.xaxis.set_major_formatter(
        matplotlib.ticker.FuncFormatter(lambda x, _: format_count(x))
    )
    ax.tick_params(axis="x", colors="#666666")
    ax.grid(axis="x", color="#222222", linewidth=0.8, linestyle="--", alpha=0.7)

    # Update labels
    src_idx = source_order.index(src) + 1
    source_label.set_text(f"+ {src}")
    counter_label.set_text(
        f"累计纳入报道方  {src_idx} / {len(source_order)}"
    )

    ax.set_title(
        "全球报道覆盖率动态分布  |  Global Cross-Coverage Race",
        color="white", fontsize=16, fontweight="bold", pad=16
    )

print(f"Total frames: {len(frames)}  |  Duration: {len(frames)/FPS:.1f}s")

ani = FuncAnimation(
    fig, update,
    frames=len(frames),
    interval=1000 / FPS,
    blit=False
)

# ── 9. Save ──────────────────────────────────────────────────────────────────
output_path = "/Users/haihaosun/Desktop/GitHub/WorldMirror/results/bigquery_v5/cross_coverage_race.mp4"
writer = FFMpegWriter(fps=FPS, bitrate=3000,
                      extra_args=["-vcodec", "libx264", "-pix_fmt", "yuv420p"])
ani.save(output_path, writer=writer, dpi=150)
print(f"\n✅ Saved: {output_path}")
plt.close(fig)
