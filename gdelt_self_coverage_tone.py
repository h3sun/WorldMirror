"""
GDELT Self-Coverage Tone Analyzer
Scrapes GDELT API to measure how positively each country covers itself.
Uses: query="{country_name} sourcecountry:{FIPS_CODE}" mode=tonechart

Rate limit: 1 request per 5 seconds (enforced)
"""

import requests
import time
import json
import csv
import sys
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from datetime import datetime

# GDELT uses FIPS 10-4 country codes in sourcecountry filter
# Format: (search_keyword, FIPS_code, display_name)
COUNTRIES = [
    ("united states",   "US", "United States"),
    ("china",           "CH", "China"),
    ("russia",          "RS", "Russia"),
    ("germany",         "GM", "Germany"),
    ("france",          "FR", "France"),
    ("united kingdom",  "UK", "United Kingdom"),
    ("japan",           "JA", "Japan"),
    ("india",           "IN", "India"),
    ("brazil",          "BR", "Brazil"),
    ("canada",          "CA", "Canada"),
    ("italy",           "IT", "Italy"),
    ("south korea",     "KS", "South Korea"),
    ("australia",       "AS", "Australia"),
    ("spain",           "SP", "Spain"),
    ("mexico",          "MX", "Mexico"),
    ("indonesia",       "ID", "Indonesia"),
    ("netherlands",     "NL", "Netherlands"),
    ("turkey",          "TU", "Turkey"),
    ("saudi arabia",    "SA", "Saudi Arabia"),
    ("argentina",       "AR", "Argentina"),
    ("poland",          "PL", "Poland"),
    ("iran",            "IR", "Iran"),
    ("egypt",           "EG", "Egypt"),
    ("thailand",        "TH", "Thailand"),
    ("pakistan",        "PK", "Pakistan"),
    ("nigeria",         "NI", "Nigeria"),
    ("ukraine",         "UP", "Ukraine"),
    ("vietnam",         "VM", "Vietnam"),
    ("malaysia",        "MY", "Malaysia"),
    ("colombia",        "CO", "Colombia"),
    ("south africa",    "SF", "South Africa"),
    ("bangladesh",      "BG", "Bangladesh"),
    ("philippines",     "RP", "Philippines"),
    ("israel",          "IS", "Israel"),
    ("sweden",          "SW", "Sweden"),
    ("norway",          "NO", "Norway"),
    ("denmark",         "DA", "Denmark"),
    ("finland",         "FI", "Finland"),
    ("portugal",        "PO", "Portugal"),
    ("greece",          "GR", "Greece"),
    ("belgium",         "BE", "Belgium"),
    ("czech republic",  "EZ", "Czech Republic"),
    ("romania",         "RO", "Romania"),
    ("hungary",         "HU", "Hungary"),
    ("chile",           "CI", "Chile"),
    ("peru",            "PE", "Peru"),
    ("new zealand",     "NZ", "New Zealand"),
    ("iraq",            "IZ", "Iraq"),
    ("qatar",           "QA", "Qatar"),
    ("singapore",       "SN", "Singapore"),
]

GDELT_API = "https://api.gdeltproject.org/api/v2/doc/doc"
TIMESPAN = "1M"
RATE_LIMIT_SLEEP = 6   # seconds between requests
MAX_RETRIES = 3

RESULTS_FILE = "gdelt_tone_results.csv"
CACHE_FILE   = "gdelt_tone_cache.json"
CHART_FILE   = "gdelt_self_tone_chart.png"


def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


def fetch_tone(keyword, fips_code):
    """Fetch tonechart JSON for a country covering itself."""
    query = f"{keyword} sourcecountry:{fips_code}"
    params = {
        "format": "json",
        "timespan": TIMESPAN,
        "query": query,
        "mode": "tonechart",
    }
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(GDELT_API, params=params, timeout=30)
            if resp.status_code == 200:
                text = resp.text.strip()
                if text.startswith("Please limit"):
                    print(f"    Rate-limited, sleeping 15s...")
                    time.sleep(15)
                    continue
                data = resp.json()
                return data.get("tonechart", [])
            else:
                print(f"    HTTP {resp.status_code}, attempt {attempt}/{MAX_RETRIES}")
        except Exception as e:
            print(f"    Error: {e}, attempt {attempt}/{MAX_RETRIES}")
        time.sleep(RATE_LIMIT_SLEEP * attempt)
    return None


def calc_weighted_tone(tonechart):
    """Compute weighted mean tone and total article count."""
    if not tonechart:
        return None, 0
    total_count = sum(item["count"] for item in tonechart)
    if total_count == 0:
        return None, 0
    weighted_sum = sum(item["bin"] * item["count"] for item in tonechart)
    avg_tone = weighted_sum / total_count
    return round(avg_tone, 4), total_count


def calc_positive_ratio(tonechart):
    """Fraction of articles with tone > 0."""
    if not tonechart:
        return None
    positive = sum(item["count"] for item in tonechart if item["bin"] > 0)
    total = sum(item["count"] for item in tonechart)
    if total == 0:
        return None
    return round(positive / total * 100, 2)


def run_scrape():
    cache = load_cache()
    results = []

    print(f"\n{'='*60}")
    print(f"GDELT Self-Coverage Tone Scraper")
    print(f"Timespan: Last {TIMESPAN} | Countries: {len(COUNTRIES)}")
    print(f"Estimated time: ~{len(COUNTRIES) * RATE_LIMIT_SLEEP // 60} min")
    print(f"{'='*60}\n")

    for i, (keyword, fips, display) in enumerate(COUNTRIES, 1):
        cache_key = f"{fips}_{TIMESPAN}"

        if cache_key in cache:
            print(f"[{i:2d}/{len(COUNTRIES)}] {display:20s} [CACHED]")
            tonechart = cache[cache_key]
        else:
            print(f"[{i:2d}/{len(COUNTRIES)}] {display:20s} Fetching...", end=" ", flush=True)
            tonechart = fetch_tone(keyword, fips)

            if tonechart is None:
                print("FAILED")
                results.append({
                    "country": display,
                    "fips": fips,
                    "avg_tone": None,
                    "positive_ratio": None,
                    "article_count": 0,
                    "status": "failed"
                })
                time.sleep(RATE_LIMIT_SLEEP)
                continue

            cache[cache_key] = tonechart
            save_cache(cache)

        avg_tone, count = calc_weighted_tone(tonechart)
        pos_ratio = calc_positive_ratio(tonechart)

        if avg_tone is not None:
            print(f"avg_tone={avg_tone:+.2f}  pos%={pos_ratio:.1f}%  n={count:,}")
        else:
            print(f"NO DATA")

        results.append({
            "country": display,
            "fips": fips,
            "avg_tone": avg_tone,
            "positive_ratio": pos_ratio,
            "article_count": count,
            "status": "ok" if avg_tone is not None else "nodata"
        })

        if cache_key not in cache:
            time.sleep(RATE_LIMIT_SLEEP)

    return results


def save_csv(results):
    valid = [r for r in results if r["avg_tone"] is not None]
    valid.sort(key=lambda x: x["avg_tone"], reverse=True)

    with open(RESULTS_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "rank", "country", "fips", "avg_tone",
            "positive_ratio", "article_count", "status"
        ])
        writer.writeheader()
        for rank, row in enumerate(valid, 1):
            writer.writerow({"rank": rank, **row})

    print(f"\nResults saved to {RESULTS_FILE}")
    return valid


def plot_results(ranked):
    """Generate horizontal bar chart colored by tone."""
    if not ranked:
        print("No data to plot.")
        return

    countries = [r["country"] for r in ranked]
    tones = [r["avg_tone"] for r in ranked]

    # Color: red (negative) -> white (0) -> green (positive)
    def tone_color(t):
        if t >= 0:
            intensity = min(t / 5, 1.0)
            return (1 - intensity * 0.7, 1.0, 1 - intensity * 0.7)  # greenish
        else:
            intensity = min(-t / 5, 1.0)
            return (1.0, 1 - intensity * 0.7, 1 - intensity * 0.7)  # reddish

    colors = [tone_color(t) for t in tones]

    fig, ax = plt.subplots(figsize=(14, max(10, len(ranked) * 0.38)))
    y_pos = range(len(countries))

    bars = ax.barh(list(y_pos), tones, color=colors,
                   edgecolor="gray", linewidth=0.5, height=0.75)

    # Value labels
    for bar, tone in zip(bars, tones):
        label = f"{tone:+.2f}"
        x = bar.get_width()
        ax.text(
            x + (0.05 if x >= 0 else -0.05),
            bar.get_y() + bar.get_height() / 2,
            label,
            va="center",
            ha="left" if x >= 0 else "right",
            fontsize=8.5,
            fontweight="bold"
        )

    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(countries, fontsize=9)
    ax.invert_yaxis()
    ax.axvline(0, color="black", linewidth=0.8, linestyle="--", alpha=0.7)
    ax.set_xlabel("Average Tone Score (Weighted Mean)", fontsize=11)
    ax.set_title(
        "Which Countries Report Most Positively About Themselves?\n"
        f"GDELT Web Coverage — Last 1 Month ({datetime.now().strftime('%Y-%m-%d')})\n"
        "Query: '{country name} sourcecountry:{FIPS}' | Mode: tonechart",
        fontsize=12, fontweight="bold", pad=15
    )

    green_patch = mpatches.Patch(color=(0.3, 1.0, 0.3), label="Positive tone")
    red_patch   = mpatches.Patch(color=(1.0, 0.3, 0.3), label="Negative tone")
    ax.legend(handles=[green_patch, red_patch], loc="lower right", fontsize=9)

    ax.grid(axis="x", alpha=0.3, linestyle=":")
    plt.tight_layout()
    plt.savefig(CHART_FILE, dpi=150, bbox_inches="tight")
    print(f"Chart saved to {CHART_FILE}")
    plt.close()


def print_summary(ranked):
    print(f"\n{'='*60}")
    print(f"TOP 10 MOST POSITIVE SELF-COVERAGE:")
    print(f"{'='*60}")
    for i, r in enumerate(ranked[:10], 1):
        print(f"  {i:2d}. {r['country']:20s}  avg_tone={r['avg_tone']:+.3f}  "
              f"pos%={r['positive_ratio']:.1f}%  n={r['article_count']:,}")

    print(f"\n{'='*60}")
    print(f"BOTTOM 10 MOST NEGATIVE SELF-COVERAGE:")
    print(f"{'='*60}")
    for i, r in enumerate(reversed(ranked[-10:]), 1):
        print(f"  {i:2d}. {r['country']:20s}  avg_tone={r['avg_tone']:+.3f}  "
              f"pos%={r['positive_ratio']:.1f}%  n={r['article_count']:,}")


if __name__ == "__main__":
    results = run_scrape()
    ranked  = save_csv(results)
    print_summary(ranked)
    plot_results(ranked)
    print("\nDone!")
