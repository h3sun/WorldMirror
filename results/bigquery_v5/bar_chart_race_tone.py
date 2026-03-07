"""
Bar Chart Race: Most Positive Coverage Tone  (smooth version)
=============================================================
Fix: interpolate BOTH bar value (X) AND rank position (Y) between keyframes,
so bars slide smoothly up/down instead of jumping.
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.animation import FuncAnimation, FFMpegWriter
import matplotlib.font_manager as fm
import matplotlib.colors as mcolors

# CJK font
for _f in ["PingFang SC", "Hiragino Sans GB", "Heiti TC", "Arial Unicode MS"]:
    if any(f.name == _f for f in fm.fontManager.ttflist):
        matplotlib.rcParams["font.family"] = _f
        break

# ── 1. Load & Filter ──────────────────────────────────────────────────────────
df = pd.read_csv(
    "/Users/haihaosun/Desktop/GitHub/WorldMirror/results/bigquery_v5/cross_coverage.csv"
)
df = df.dropna(subset=["source_country", "target_country", "avg_tone", "article_count"])
df["article_count"] = pd.to_numeric(df["article_count"], errors="coerce").fillna(0)
df["avg_tone"]      = pd.to_numeric(df["avg_tone"],      errors="coerce")
df = df[df["article_count"] >= 500].copy()
df["pair"] = df["source_country"] + " → " + df["target_country"]

# ── 2. Source order (alphabetical) ────────────────────────────────────────────
source_order = sorted(df["source_country"].unique())
N_SOURCES = len(source_order)

# ── 3. Animation params ───────────────────────────────────────────────────────
TOP_N     = 12     # bars shown
POOL      = 16     # track extra bars for smooth entry/exit
FPS       = 24
N_INTERP  = 14     # steps between keyframes (more = smoother)
DWELL     = 2      # hold frames at each keyframe

# ── 4. Build keyframe snapshots ───────────────────────────────────────────────
# Each keyframe: pd.Series {pair: avg_tone} for all revealed pairs so far
keyframes = []
revealed  = {}
for src in source_order:
    batch = df[df["source_country"] == src].set_index("pair")["avg_tone"]
    revealed.update(batch.to_dict())
    keyframes.append(pd.Series(revealed, dtype=float))

# ── 5. Pre-compute smooth frame specs ────────────────────────────────────────
# Each frame spec: list of dicts {pair, value, y_pos, alpha}
# y_pos is a FLOAT — interpolated rank — so bars slide smoothly.

def get_ranking(series: pd.Series, pool: int) -> pd.DataFrame:
    """Return top `pool` pairs with their rank (0=top) and value."""
    top = series.nlargest(pool)
    return pd.DataFrame({
        "value": top.values,
        "rank":  np.arange(len(top), dtype=float),
    }, index=top.index)

all_frame_specs    = []   # [{pair: {value, y, alpha}}, ...]
all_frame_sources  = []
all_revealed_count = []

for ki, src in enumerate(source_order):
    curr_rank = get_ranking(keyframes[ki], POOL)
    prev_rank = get_ranking(keyframes[ki - 1], POOL) if ki > 0 else curr_rank.copy()

    n_steps = N_INTERP if ki > 0 else 1
    for step in range(n_steps):
        alpha = (step + 1) / n_steps

        frame_spec = {}
        # All pairs visible in either prev or curr top-POOL
        all_visible = curr_rank.index.union(prev_rank.index)

        for pair in all_visible:
            in_curr = pair in curr_rank.index
            in_prev = pair in prev_rank.index

            # Value interpolation
            val_curr = curr_rank.loc[pair, "value"] if in_curr else None
            val_prev = prev_rank.loc[pair, "value"] if in_prev else None

            if in_curr and in_prev:
                val = val_prev + alpha * (val_curr - val_prev)
            elif in_curr:
                val = val_curr * alpha          # grow in from 0
            else:
                val = val_prev * (1 - alpha)    # shrink out to 0

            # Rank/Y interpolation
            r_curr = curr_rank.loc[pair, "rank"] if in_curr else float(POOL)
            r_prev = prev_rank.loc[pair, "rank"] if in_prev else float(POOL)
            rank_f = r_prev + alpha * (r_curr - r_prev)

            # Alpha (opacity) for entering/leaving bars
            if in_curr and in_prev:
                bar_alpha = 0.88
            elif in_curr:
                bar_alpha = 0.88 * alpha        # fade in
            else:
                bar_alpha = 0.88 * (1 - alpha)  # fade out

            frame_spec[pair] = {"value": val, "rank": rank_f, "alpha": bar_alpha}

        all_frame_specs.append(frame_spec)
        all_frame_sources.append(src)
        all_revealed_count.append(len(keyframes[ki]))

    # Dwell frames
    dwell_spec = {p: {"value": curr_rank.loc[p, "value"],
                      "rank":  curr_rank.loc[p, "rank"],
                      "alpha": 0.88}
                  for p in curr_rank.index}
    for _ in range(DWELL):
        all_frame_specs.append(dwell_spec)
        all_frame_sources.append(src)
        all_revealed_count.append(len(keyframes[ki]))

print(f"Total frames: {len(all_frame_specs)}  |  "
      f"Duration: {len(all_frame_specs)/FPS:.1f}s")

# ── 6. Colors by source country ───────────────────────────────────────────────
src_list   = sorted(df["source_country"].unique())
cmap       = matplotlib.colormaps.get_cmap("tab20")
src_colors = {s: mcolors.to_hex(cmap(i % 20)) for i, s in enumerate(src_list)}

def pair_color(pair_name):
    return src_colors.get(pair_name.split(" → ")[0], "#888888")

# ── 7. Figure ─────────────────────────────────────────────────────────────────
BG = "#0d1117"
fig, ax = plt.subplots(figsize=(15, 8.5))
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)

fig.text(
    0.13, 0.005,
    "颜色 = 报道方 (source country)   ·   过滤：文章数 ≥ 500",
    color="#555555", fontsize=8.5, ha="left"
)
src_badge   = fig.text(0.98, 0.015, "", color="#58a6ff",  fontsize=11,
                        fontweight="bold", ha="right")
count_badge = fig.text(0.98, 0.052, "", color="#8b949e",  fontsize=9,
                        ha="right")

# ── 8. Update ─────────────────────────────────────────────────────────────────
Y_TOP    = TOP_N - 1   # y=0 is bottom bar, y=TOP_N-1 is top bar

def update(fi):
    ax.cla()
    ax.set_facecolor(BG)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(colors="white", labelsize=10.5)

    spec = all_frame_specs[fi]
    src  = all_frame_sources[fi]

    # Sort by rank (ascending = higher rank closer to POOL, but we flip Y)
    items = sorted(spec.items(), key=lambda x: x[1]["rank"])

    # Only draw pairs that are within visible rank range (rank < TOP_N + 1.5)
    visible = [(p, d) for p, d in items if d["rank"] < TOP_N + 1.0]

    if not visible:
        return

    values = [d["value"]         for _, d in visible]
    ypos   = [Y_TOP - d["rank"]  for _, d in visible]   # flip: rank 0 → top
    alphas = [d["alpha"]         for _, d in visible]
    colors = [pair_color(p)      for p, _ in visible]
    labels = [p                  for p, _ in visible]

    x_vals  = np.array(values)
    x_max   = np.nanmax(x_vals) if len(x_vals) else 1
    x_min   = np.nanmin(x_vals) if len(x_vals) else -1
    span    = max(x_max - x_min, 0.5)

    for j, (val, yp, al, col, lbl) in enumerate(
            zip(values, ypos, alphas, colors, labels)):
        ax.barh(yp, val, color=col, alpha=al,
                height=0.72, edgecolor="none")
        # Value label
        ax.text(val + span * 0.012, yp, f"{val:+.3f}",
                va="center", ha="left", color="white",
                fontsize=9, fontweight="bold", alpha=al)
        # Pair label (left side)
        ax.text(x_min - span * 0.015, yp, lbl,
                va="center", ha="right", color="white",
                fontsize=10.5, alpha=al)

    # Axes
    ax.set_xlim(x_min - span * 0.35, x_max + span * 0.22)
    ax.set_ylim(-1.5, TOP_N)
    ax.set_yticks([])
    ax.xaxis.set_major_formatter(ticker.FormatStrFormatter("%.1f"))
    ax.tick_params(axis="x", colors="#555555", labelsize=9)
    ax.grid(axis="x", color="#1a2233", linewidth=0.8,
            linestyle="--", alpha=0.9)
    if x_min < 0 < x_max:
        ax.axvline(0, color="#333d4d", linewidth=1.2)

    ax.set_title(
        "报道情感极性竞速  |  Most Positive Coverage Tone Race",
        color="white", fontsize=14.5, fontweight="bold", pad=12, loc="left"
    )
    ax.set_xlabel("avg_tone  (越高 = 报道越正面)", color="#777777",
                  fontsize=10, labelpad=8)

    src_idx = source_order.index(src) + 1
    src_badge.set_text(f"+ {src}  [{src_idx} / {N_SOURCES}]")
    count_badge.set_text(f"竞争对数：{all_revealed_count[fi]}")

# ── 9. Render ─────────────────────────────────────────────────────────────────
ani = FuncAnimation(fig, update,
                    frames=len(all_frame_specs),
                    interval=1000 / FPS, blit=False)

out = ("/Users/haihaosun/Desktop/GitHub/WorldMirror/results/"
       "bigquery_v5/tone_race.mp4")
writer = FFMpegWriter(
    fps=FPS, bitrate=5000,
    extra_args=["-vcodec", "libx264", "-pix_fmt", "yuv420p", "-crf", "16"]
)
print("Rendering …")
ani.save(out, writer=writer, dpi=150)
print(f"\n✅  Saved → {out}")
plt.close(fig)
