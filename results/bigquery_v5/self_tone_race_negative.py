"""
Bar Chart Race: 各国自我报道情感极性竞速 — 最负面版（含国旗）
- 数据：source_country == target_country
- 指标：avg_tone（越低越负面），排行榜展示最负面的国家
- 国旗：PIL + Apple Color Emoji 预渲染 → AnnotationBbox 贴图
- 颜色：每国固定颜色，全程不变
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
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from matplotlib.transforms import blended_transform_factory
from PIL import Image, ImageDraw, ImageFont

# ── CJK 字体 ──────────────────────────────────────────────────────────────────
for _f in ["PingFang SC", "Hiragino Sans GB", "Heiti TC", "Arial Unicode MS"]:
    if any(f.name == _f for f in fm.fontManager.ttflist):
        matplotlib.rcParams["font.family"] = _f
        break

# ── 国旗 emoji 映射 ────────────────────────────────────────────────────────────
FLAGS = {
    "Argentina":      "🇦🇷", "Australia":      "🇦🇺", "Bangladesh":     "🇧🇩",
    "Belgium":        "🇧🇪", "Brazil":         "🇧🇷", "Canada":         "🇨🇦",
    "Chile":          "🇨🇱", "China":          "🇨🇳", "Colombia":       "🇨🇴",
    "Czech Republic": "🇨🇿", "Denmark":        "🇩🇰", "Egypt":          "🇪🇬",
    "Finland":        "🇫🇮", "France":         "🇫🇷", "Germany":        "🇩🇪",
    "Greece":         "🇬🇷", "Hungary":        "🇭🇺", "India":          "🇮🇳",
    "Indonesia":      "🇮🇩", "Iran":           "🇮🇷", "Iraq":           "🇮🇶",
    "Israel":         "🇮🇱", "Italy":          "🇮🇹", "Japan":          "🇯🇵",
    "Malaysia":       "🇲🇾", "Mexico":         "🇲🇽", "Netherlands":    "🇳🇱",
    "New Zealand":    "🇳🇿", "Nigeria":        "🇳🇬", "Norway":         "🇳🇴",
    "Pakistan":       "🇵🇰", "Peru":           "🇵🇪", "Philippines":    "🇵🇭",
    "Poland":         "🇵🇱", "Portugal":       "🇵🇹", "Qatar":          "🇶🇦",
    "Romania":        "🇷🇴", "Russia":         "🇷🇺", "Saudi Arabia":   "🇸🇦",
    "Singapore":      "🇸🇬", "South Africa":   "🇿🇦", "South Korea":   "🇰🇷",
    "Spain":          "🇪🇸", "Sweden":         "🇸🇪", "Thailand":       "🇹🇭",
    "Turkey":         "🇹🇷", "Ukraine":        "🇺🇦", "United Kingdom": "🇬🇧",
    "United States":  "🇺🇸", "Vietnam":        "🇻🇳",
}

# ── 中文国家名 ─────────────────────────────────────────────────────────────────
CN = {
    "Argentina":"阿根廷","Australia":"澳大利亚","Bangladesh":"孟加拉国",
    "Belgium":"比利时","Brazil":"巴西","Canada":"加拿大","Chile":"智利",
    "China":"中国","Colombia":"哥伦比亚","Czech Republic":"捷克",
    "Denmark":"丹麦","Egypt":"埃及","Finland":"芬兰","France":"法国",
    "Germany":"德国","Greece":"希腊","Hungary":"匈牙利","India":"印度",
    "Indonesia":"印度尼西亚","Iran":"伊朗","Iraq":"伊拉克","Israel":"以色列",
    "Italy":"意大利","Japan":"日本","Malaysia":"马来西亚","Mexico":"墨西哥",
    "Netherlands":"荷兰","New Zealand":"新西兰","Nigeria":"尼日利亚",
    "Norway":"挪威","Pakistan":"巴基斯坦","Peru":"秘鲁","Philippines":"菲律宾",
    "Poland":"波兰","Portugal":"葡萄牙","Qatar":"卡塔尔","Romania":"罗马尼亚",
    "Russia":"俄罗斯","Saudi Arabia":"沙特阿拉伯","Singapore":"新加坡",
    "South Africa":"南非","South Korea":"韩国","Spain":"西班牙",
    "Sweden":"瑞典","Thailand":"泰国","Turkey":"土耳其","Ukraine":"乌克兰",
    "United Kingdom":"英国","United States":"美国","Vietnam":"越南",
}
def cn(name): return CN.get(name, name)

# ── PIL 渲染 emoji → numpy RGBA ────────────────────────────────────────────────
EMOJI_FONT = "/System/Library/Fonts/Apple Color Emoji.ttc"
# Apple Color Emoji 只支持特定 bitmap 字号（8 的倍数）
_VALID_SIZES = [16, 20, 32, 40, 48, 64, 96, 160]

def _best_size(target: int) -> int:
    """找到 >= target 的最小合法字号"""
    for s in _VALID_SIZES:
        if s >= target:
            return s
    return _VALID_SIZES[-1]

def render_emoji(text: str, target_size: int = 32) -> np.ndarray:
    """用 Apple Color Emoji 把 emoji 渲染成 RGBA numpy 数组"""
    size = _best_size(target_size)
    font = ImageFont.truetype(EMOJI_FONT, size=size, index=0)
    canvas = size + 8
    img  = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.text((3, 2), text, font=font, embedded_color=True)
    if size != target_size:
        img = img.resize((target_size + 8, target_size + 8), Image.LANCZOS)
    return np.array(img)

print("预渲染国旗 emoji …")
flag_imgs = {c: render_emoji(FLAGS[c], target_size=32) for c in FLAGS}
medal_img  = render_emoji("📉", target_size=40)
print("完成。")

# ── 1. 数据加载 ────────────────────────────────────────────────────────────────
df = pd.read_csv(
    "/Users/haihaosun/Desktop/GitHub/WorldMirror/results/bigquery_v5/cross_coverage.csv"
)
df = df.dropna(subset=["source_country","target_country","avg_tone","article_count"])
df["article_count"] = pd.to_numeric(df["article_count"], errors="coerce").fillna(0)
df["avg_tone"]      = pd.to_numeric(df["avg_tone"], errors="coerce")

self_df = df[
    df["source_country"] == df["target_country"]
].copy()

tones = dict(zip(self_df["source_country"], self_df["avg_tone"]))

# ── 2. 固定颜色（每国唯一） ────────────────────────────────────────────────────
all_countries = sorted(tones.keys())
cmap = matplotlib.colormaps.get_cmap("tab20")
country_color = {c: mcolors.to_hex(cmap(i % 20)) for i, c in enumerate(all_countries)}

# ── 3. 登场顺序（随机，最大化追赶感） ─────────────────────────────────────────
rng = np.random.default_rng(seed=7)
entry_order = list(tones.keys())
rng.shuffle(entry_order)

# ── 4. 参数 ────────────────────────────────────────────────────────────────────
TOP_N          = 10
N_ENTER        = 8    # 新国家滑入 + 重排帧数
N_EVICT_LINGER = 6    # 被淘汰者在榜底高亮停留帧数（让观众看清）
N_EVICT_EXIT   = 6    # 被淘汰者慢慢消失帧数
N_DWELL        = 3    # 最终稳定停顿帧数
FPS            = 24

# ── 5. 逐帧预计算 ──────────────────────────────────────────────────────────────
all_specs    = []
all_newcomer = []
all_active   = []

active = {}

def sorted_ranking(pool):
    return sorted(pool.items(), key=lambda x: x[1])   # 升序：最负面排第一

for newcomer in entry_order:
    tone_new   = tones[newcomer]
    old_sorted = sorted_ranking(active)
    old_rank   = {c: i for i, (c, _) in enumerate(old_sorted)}

    active[newcomer] = tone_new
    new_sorted = sorted_ranking(active)
    new_rank   = {c: i for i, (c, _) in enumerate(new_sorted)}

    evicted = None
    if len(active) > TOP_N:
        evicted = new_sorted[TOP_N][0]

    # ── 阶段1：新国家滑入 + 所有留守国重排（evicted 同步下沉到榜底）
    evicted_y_bottom = -0.5   # 榜底位置（超出 TOP_N 区域但还可见）
    for step in range(N_ENTER):
        t    = (step + 1) / N_ENTER
        spec = {}
        for c, tone in active.items():
            if c == newcomer:
                val   = tone * t
                y_new = TOP_N - 1 - new_rank[c]
                y     = -1.5 + t * (y_new + 1.5)
                alpha = t * 0.9
            elif c == evicted:
                # 下沉到榜底但保持可见，让观众看见"谁被挤出了"
                val   = tone
                y_old = TOP_N - 1 - old_rank.get(c, TOP_N - 1)
                y     = y_old + t * (evicted_y_bottom - y_old)
                alpha = 0.9
            else:
                val   = tone
                r_old = old_rank.get(c, new_rank[c])
                r_new = new_rank[c]
                y     = (TOP_N - 1 - r_old) + t * ((TOP_N - 1 - r_new) - (TOP_N - 1 - r_old))
                alpha = 0.9
            spec[c] = {"value": val, "y": y, "alpha": alpha, "evicted": c == evicted}
        all_specs.append(spec)
        all_newcomer.append(newcomer)
        all_active.append(list(active.keys()))

    # ── 阶段2：淘汰者高亮停留在榜底（闪烁边框提示观众）
    if evicted:
        final_in_rank = sorted_ranking({c: t for c, t in active.items() if c != evicted})
        for linger_step in range(N_EVICT_LINGER):
            spec = {
                c: {"value": t, "y": float(TOP_N - 1 - i), "alpha": 0.9, "evicted": False}
                for i, (c, t) in enumerate(final_in_rank)
            }
            # 被淘汰者停在榜底，透明度轻微脉动（sin 产生闪烁感）
            pulse = 0.55 + 0.35 * abs(np.sin(linger_step * np.pi / N_EVICT_LINGER * 2))
            spec[evicted] = {
                "value": tones[evicted],
                "y": evicted_y_bottom,
                "alpha": pulse,
                "evicted": True,
            }
            all_specs.append(spec)
            all_newcomer.append(newcomer)
            all_active.append(list(active.keys()))

        # ── 阶段3：淘汰者慢慢淡出下沉
        for exit_step in range(N_EVICT_EXIT):
            t = (exit_step + 1) / N_EVICT_EXIT
            spec = {
                c: {"value": tone, "y": float(TOP_N - 1 - i), "alpha": 0.9, "evicted": False}
                for i, (c, tone) in enumerate(final_in_rank)
            }
            spec[evicted] = {
                "value": tones[evicted],
                "y": evicted_y_bottom - t * 1.2,
                "alpha": 0.9 * (1 - t),
                "evicted": True,
            }
            all_specs.append(spec)
            all_newcomer.append(newcomer)
            all_active.append(list(active.keys()))

    if evicted:
        del active[evicted]

    final_sorted = sorted_ranking(active)
    for _ in range(N_DWELL):
        spec = {
            c: {"value": tone, "y": float(TOP_N - 1 - i), "alpha": 0.9, "evicted": False}
            for i, (c, tone) in enumerate(final_sorted)
        }
        all_specs.append(spec)
        all_newcomer.append(newcomer)
        all_active.append(list(active.keys()))

total_frames = len(all_specs)
print(f"总帧数：{total_frames}  |  时长：{total_frames/FPS:.1f}s")

# ── 6. 图形设置 ────────────────────────────────────────────────────────────────
BG = "#0d1117"
fig, ax = plt.subplots(figsize=(14, 8))
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)
for spine in ax.spines.values():
    spine.set_visible(False)
ax.tick_params(colors="white", labelsize=11)

# 标题区：金牌图标 + 文字
medal_ax = fig.add_axes([0.02, 0.905, 0.04, 0.07])  # [left, bottom, w, h]
medal_ax.imshow(medal_img)
medal_ax.axis("off")

fig.text(0.065, 0.945, "自我报道最负面的国家排行榜",
         color="white", fontsize=15, fontweight="bold", va="center")

badge_country = fig.text(0.98, 0.02, "", color="#58a6ff",
                          fontsize=11, fontweight="bold", ha="right")
badge_count   = fig.text(0.98, 0.055, "", color="#8b949e",
                          fontsize=9, ha="right")
fig.text(0.02, 0.005,
         "指标：avg_tone（媒体报道自国的情感倾向，右正左负）  ·  含全部 48 国",
         color="#555555", fontsize=8.5)

# ── 7. 每帧更新 ────────────────────────────────────────────────────────────────
# 用混合坐标系：X 用 axes fraction（固定），Y 用 data（跟随条形）
def get_trans():
    return blended_transform_factory(ax.transAxes, ax.transData)

FLAG_X  = 0.01   # 国旗 axes-x（距左边 1%）
LABEL_X = 0.17   # 国家名右对齐点 axes-x

def update(fi):
    ax.cla()
    ax.set_facecolor(BG)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(colors="white", labelsize=10)

    spec     = all_specs[fi]
    newcomer = all_newcomer[fi]
    n_active = len(all_active[fi])

    if not spec:
        return

    values = [d["value"] for d in spec.values()]
    x_max  = max((v for v in values if np.isfinite(v)), default=1.0)
    x_min  = min((v for v in values if np.isfinite(v)), default=-1.0)
    span   = max(abs(x_max - x_min), 0.3)

    trans = get_trans()

    for country, d in spec.items():
        val   = d["value"]
        y     = d["y"]
        alpha = d["alpha"]
        color = country_color[country]

        # ── 条形：从 0 出发，负数自然向左，正数向右
        ax.barh(y, val, color=color, alpha=alpha,
                height=0.72, edgecolor="none")

        # ── 国旗（PIL 图像，axes-x 固定，data-y 跟随）
        if country in flag_imgs:
            flag_arr = flag_imgs[country].copy().astype(float)
            flag_arr[:, :, 3] = flag_arr[:, :, 3] * alpha
            flag_arr = flag_arr.astype(np.uint8)
            imagebox = OffsetImage(flag_arr, zoom=0.52)
            ab = AnnotationBbox(
                imagebox,
                xy=(FLAG_X, y),
                xycoords=trans,
                frameon=False,
                box_alignment=(0, 0.5),
            )
            ax.add_artist(ab)

        # ── 国家名（axes-x 固定，data-y 跟随）
        ax.text(
            LABEL_X, y, cn(country),
            transform=trans,
            va="center", ha="right",
            color="white", fontsize=11, fontweight="bold",
            alpha=alpha,
        )

        # ── 数值标签：正数贴右端，负数贴左端
        if val >= 0:
            ax.text(val + span * 0.02, y, f"{val:+.3f}",
                    va="center", ha="left", color="white", fontsize=9, alpha=alpha)
        else:
            ax.text(val - span * 0.02, y, f"{val:+.3f}",
                    va="center", ha="right", color="white", fontsize=9, alpha=alpha)

        # ── 登场高亮边框（新入场）
        if country == newcomer and alpha < 0.88:
            ax.barh(y, val, color="none",
                    alpha=min(alpha * 1.8, 1.0),
                    height=0.74, edgecolor=color, linewidth=2.2)

        # ── 淘汰高亮边框（红色虚线 + 文字提示）
        if d.get("evicted"):
            ax.barh(y, val, color="none",
                    alpha=min(alpha * 1.2, 0.9),
                    height=0.74, edgecolor="#ff4444", linewidth=2.0,
                    linestyle="--")
            ax.text(0.5, y - 0.52,
                    f"▼ {cn(country)} 被淘汰出榜",
                    transform=blended_transform_factory(ax.transAxes, ax.transData),
                    ha="center", va="top", color="#ff6666",
                    fontsize=8.5, alpha=alpha)

    # ── 坐标轴（留足左侧标签空间）
    ax.set_xlim(x_min - span * 0.48, x_max + span * 0.20)
    ax.set_ylim(-2, TOP_N)
    ax.set_yticks([])
    ax.xaxis.set_major_formatter(ticker.FormatStrFormatter("%.1f"))
    ax.tick_params(axis="x", colors="#555555", labelsize=9)
    ax.grid(axis="x", color="#1a2233", linewidth=0.8, linestyle="--", alpha=0.8)
    # 零轴线：始终显示，清楚区分正负
    ax.axvline(0, color="#4a5568", linewidth=1.8, zorder=2)

    ax.set_xlabel("情感倾向指数（avg_tone）", color="#777777",
                  fontsize=10, labelpad=8)

    # ── 右下徽章
    badge_country.set_text(f"登场：{cn(newcomer)}")
    badge_count.set_text(f"已登场 {n_active} / {len(tones)} 国")

# ── 8. 渲染 ────────────────────────────────────────────────────────────────────
ani = FuncAnimation(fig, update,
                    frames=total_frames,
                    interval=1000 / FPS,
                    blit=False)

out = ("/Users/haihaosun/Desktop/GitHub/WorldMirror/results/"
       "bigquery_v5/self_tone_race_negative.mp4")
writer = FFMpegWriter(
    fps=FPS, bitrate=6000,
    extra_args=["-vcodec", "libx264", "-pix_fmt", "yuv420p", "-crf", "15"]
)
print("渲染中…")
ani.save(out, writer=writer, dpi=150)
print(f"\n✅  已保存 → {out}")
plt.close(fig)
