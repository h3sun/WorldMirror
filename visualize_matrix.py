"""
Country-to-Country Tone Heatmap
Source country (rows) → Target country (cols) → avg_tone
"""

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np

df = pd.read_csv("results/bigquery/bq_cross_coverage.csv")

# Build pivot: rows=source, cols=target
matrix = df.pivot_table(
    index="source_country",
    columns="target_country",
    values="avg_tone"
)

# Order countries by their self-coverage tone (diagonal)
countries_with_self = [c for c in matrix.index if c in matrix.columns]
self_tone = pd.Series(
    {c: matrix.loc[c, c] for c in countries_with_self if not np.isnan(matrix.loc[c, c])},
)
order = self_tone.sort_values(ascending=False).index.tolist()

# Add countries missing from diagonal at end
all_countries = sorted(set(matrix.index) | set(matrix.columns))
order += [c for c in all_countries if c not in order]

matrix = matrix.reindex(index=order, columns=order)

# ── Plot ───────────────────────────────────────────────────────────────────
n = len(matrix)
fig, ax = plt.subplots(figsize=(26, 22))
fig.patch.set_facecolor("#0e1117")
ax.set_facecolor("#0e1117")

cmap = plt.cm.RdYlGn
vmin, vmax = -5, 5

im = ax.imshow(matrix.values, cmap=cmap, vmin=vmin, vmax=vmax,
               aspect="auto", interpolation="nearest")

# Colorbar
cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.01)
cbar.set_label("Average Tone Score", color="white", fontsize=11)
cbar.ax.yaxis.set_tick_params(color="white")
plt.setp(cbar.ax.yaxis.get_ticklabels(), color="white")

# Axis labels
ax.set_xticks(range(n))
ax.set_yticks(range(n))
ax.set_xticklabels(matrix.columns, rotation=45, ha="right",
                   fontsize=7.5, color="white")
ax.set_yticklabels(matrix.index, fontsize=7.5, color="white")

ax.set_xlabel("Target Country (被报道国)", color="white", fontsize=12, labelpad=10)
ax.set_ylabel("Source Country (报道国)", color="white", fontsize=12, labelpad=10)

# Highlight diagonal (self-coverage)
for i, country in enumerate(matrix.index):
    if country in matrix.columns:
        j = list(matrix.columns).index(country)
        ax.add_patch(plt.Rectangle(
            (j - 0.5, i - 0.5), 1, 1,
            fill=False, edgecolor="gold", linewidth=1.5
        ))

# Title
ax.set_title(
    "国家对国家的新闻报道情绪矩阵\nCountry-to-Country Media Tone  ·  GDELT BigQuery  ·  Last 30 Days\n"
    "行 = 报道来源国  ·  列 = 被报道国  ·  颜色 = 平均情绪分  ·  金框 = 自我报道",
    color="white", fontsize=13, fontweight="bold", pad=15
)

# Spine colors
for spine in ax.spines.values():
    spine.set_edgecolor("#444")

plt.tight_layout()
out = "results/bigquery/country_tone_matrix.png"
plt.savefig(out, dpi=150, bbox_inches="tight", facecolor="#0e1117")
print(f"Saved: {out}")

# ── Also print top findings ────────────────────────────────────────────────
print("\n=== 最喜欢正面报道其他国家的国家 (avg across all targets) ===")
src_mean = df.groupby("source_country")["avg_tone"].mean().sort_values(ascending=False)
print(src_mean.head(10).to_string())

print("\n=== 被报道最正面的国家 (avg across all sources) ===")
tgt_mean = df.groupby("target_country")["avg_tone"].mean().sort_values(ascending=False)
print(tgt_mean.head(10).to_string())

print("\n=== 最敌对的国家对 (最低tone) ===")
hostile = df.nsmallest(10, "avg_tone")[["source_country","target_country","avg_tone","article_count"]]
print(hostile.to_string(index=False))

print("\n=== 最友好的国家对 (最高tone, 文章数>100) ===")
friendly = df[df["article_count"] > 100].nlargest(10, "avg_tone")[["source_country","target_country","avg_tone","article_count"]]
print(friendly.to_string(index=False))
