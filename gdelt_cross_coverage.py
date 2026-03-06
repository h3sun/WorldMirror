"""
GDELT Cross-Coverage Tone Scraper
For every (source_country A, target_country B) pair among 50 countries:
  query = "{B_name} sourcecountry:{A_fips}"  →  how A covers B
Saves incrementally to cache; resumes automatically on restart.
Total: 50x50 = 2500 pairs
Rate limit: enforced with exponential backoff on 429
"""

import requests, time, json, os, csv, sys
from datetime import datetime

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

GDELT_API    = "https://api.gdeltproject.org/api/v2/doc/doc"
TIMESPAN     = "1M"
CACHE_FILE   = "results/cross_coverage/cache.json"
RESULTS_FILE = "results/cross_coverage/matrix.csv"
LOG_FILE     = "results/cross_coverage/progress.log"

BASE_SLEEP   = 6   # seconds between successful requests
MAX_RETRIES  = 3


# ── helpers ────────────────────────────────────────────────────────────────

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            return json.load(f)
    return {}

def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)

def cache_key(src_fips, tgt_fips):
    return f"{src_fips}->{tgt_fips}"

def calc_stats(tonechart):
    if not tonechart:
        return None, None, 0
    total = sum(i["count"] for i in tonechart)
    if total == 0:
        return None, None, 0
    wavg  = sum(i["bin"] * i["count"] for i in tonechart) / total
    pos   = sum(i["count"] for i in tonechart if i["bin"] > 0) / total * 100
    return round(wavg, 4), round(pos, 2), total

def fetch_tone(target_kw, source_fips, retries=MAX_RETRIES):
    query  = f"{target_kw} sourcecountry:{source_fips}"
    params = {"format": "json", "timespan": TIMESPAN,
              "query": query, "mode": "tonechart"}
    sleep  = BASE_SLEEP
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(GDELT_API, params=params, timeout=30)
            if r.status_code == 200:
                text = r.text.strip()
                if text.startswith("Please limit"):
                    wait = sleep * attempt
                    print(f" [rate-limit] sleeping {wait}s", flush=True)
                    time.sleep(wait)
                    continue
                try:
                    data = r.json()
                except Exception:
                    # Invalid escape or malformed JSON — treat as empty
                    return []
                return data.get("tonechart", [])
            elif r.status_code == 429:
                wait = sleep * attempt
                print(f" [429] sleeping {wait}s", flush=True)
                time.sleep(wait)
            else:
                print(f" [HTTP {r.status_code}] attempt {attempt}", flush=True)
                time.sleep(sleep)
        except Exception as e:
            print(f" [err:{e}] attempt {attempt}", flush=True)
            time.sleep(sleep * attempt)
    return None   # all retries exhausted → will be retried next run

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


# ── main ───────────────────────────────────────────────────────────────────

def run():
    os.makedirs("results/cross_coverage", exist_ok=True)
    cache = load_cache()

    # Build all pairs
    pairs = [(s, t) for s in COUNTRIES for t in COUNTRIES]
    total = len(pairs)

    done    = sum(1 for s, t in pairs if cache_key(s[1], t[1]) in cache)
    failed  = [k for k, v in cache.items() if v is None]

    log(f"Total pairs: {total}  |  Cached: {done}  |  Previously failed: {len(failed)}")
    log(f"Remaining: {total - done}")

    fetched_this_run = 0
    for idx, (src, tgt) in enumerate(pairs, 1):
        src_kw, src_fips, src_name = src
        tgt_kw, tgt_fips, tgt_name = tgt
        key = cache_key(src_fips, tgt_fips)

        # Skip if already successfully cached
        if key in cache and cache[key] is not None:
            continue

        label = f"[{idx:4d}/{total}] {src_name:20s} → {tgt_name:20s}"
        print(label, end=" ", flush=True)

        chart = fetch_tone(tgt_kw, src_fips)

        if chart is None:
            # Fetch failed — store None so we know it was attempted
            cache[key] = None
            print("FAILED (will retry next run)")
        else:
            cache[key] = chart
            avg, pos, n = calc_stats(chart)
            print(f"tone={avg:+.2f}  pos%={pos}  n={n:,}" if avg is not None else "NO DATA")

        save_cache(cache)
        fetched_this_run += 1
        time.sleep(BASE_SLEEP)

    # ── Re-try all None entries ────────────────────────────────────────────
    failed_keys = [k for k, v in cache.items() if v is None]
    if failed_keys:
        log(f"\nRetrying {len(failed_keys)} failed pairs...")
        for key in list(failed_keys):
            src_fips, tgt_fips = key.split("->")
            src = next(c for c in COUNTRIES if c[1] == src_fips)
            tgt = next(c for c in COUNTRIES if c[1] == tgt_fips)
            print(f"  RETRY {src[2]:20s} → {tgt[2]:20s}", end=" ", flush=True)
            chart = fetch_tone(tgt[0], src_fips)
            if chart is not None:
                cache[key] = chart
                avg, pos, n = calc_stats(chart)
                print(f"tone={avg:+.2f}" if avg is not None else "NO DATA")
            else:
                print("STILL FAILED")
            save_cache(cache)
            time.sleep(BASE_SLEEP)

    # ── Write CSV matrix ───────────────────────────────────────────────────
    write_csv(cache)
    log("Done!")


def write_csv(cache):
    rows = []
    for src in COUNTRIES:
        for tgt in COUNTRIES:
            key = cache_key(src[1], tgt[1])
            chart = cache.get(key)
            avg, pos, n = calc_stats(chart) if chart else (None, None, 0)
            rows.append({
                "source_country":  src[2],
                "source_fips":     src[1],
                "target_country":  tgt[2],
                "target_fips":     tgt[1],
                "avg_tone":        avg,
                "positive_ratio":  pos,
                "article_count":   n,
            })

    rows.sort(key=lambda r: (r["source_country"], r["target_country"]))
    with open(RESULTS_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    # Summary stats
    valid = [r for r in rows if r["avg_tone"] is not None]
    success_rate = len(valid) / len(rows) * 100
    missing = len(rows) - len(valid)
    log(f"CSV saved: {RESULTS_FILE}  ({len(valid)}/{len(rows)} pairs, {success_rate:.1f}%  missing={missing})")


if __name__ == "__main__":
    # Keep looping until all pairs are filled
    while True:
        cache = load_cache()
        pairs = [(s, t) for s in COUNTRIES for t in COUNTRIES]
        missing = [
            (s, t) for s, t in pairs
            if cache.get(cache_key(s[1], t[1])) is None
        ]
        if not missing:
            log("All pairs complete!")
            write_csv(cache)
            break

        log(f"Starting run — {len(missing)} pairs still needed")
        run()

        # Check again
        cache = load_cache()
        still_missing = [
            (s, t) for s, t in pairs
            if cache.get(cache_key(s[1], t[1])) is None
        ]
        if not still_missing:
            log("All pairs complete!")
            write_csv(cache)
            break

        log(f"{len(still_missing)} pairs still missing — waiting 30s then retrying...")
        time.sleep(30)
