"""
Geolocate top 500 GDELT domains using:
  Layer 1: Wikidata exact match
  Layer 2: ipinfo.io IP geolocation
  Layer 3: TLD fallback
"""

import pandas as pd
import requests
import socket
import time
import json
import os
from collections import Counter

OUT_DIR = "results/domain_mapping"
os.makedirs(OUT_DIR, exist_ok=True)

# Our 50 countries
COUNTRIES = {
    "United States","China","Russia","Germany","France","United Kingdom",
    "Japan","India","Brazil","Canada","Italy","South Korea","Australia",
    "Spain","Mexico","Indonesia","Netherlands","Turkey","Saudi Arabia",
    "Argentina","Poland","Iran","Egypt","Thailand","Pakistan","Nigeria",
    "Ukraine","Vietnam","Malaysia","Colombia","South Africa","Bangladesh",
    "Philippines","Israel","Sweden","Norway","Denmark","Finland","Portugal",
    "Greece","Belgium","Czech Republic","Romania","Hungary","Chile","Peru",
    "New Zealand","Iraq","Qatar","Singapore",
}

# ipinfo.io country code → our country name
ISO2_TO_NAME = {
    "US":"United States","CN":"China","RU":"Russia","DE":"Germany",
    "FR":"France","GB":"United Kingdom","JP":"Japan","IN":"India",
    "BR":"Brazil","CA":"Canada","IT":"Italy","KR":"South Korea",
    "AU":"Australia","ES":"Spain","MX":"Mexico","ID":"Indonesia",
    "NL":"Netherlands","TR":"Turkey","SA":"Saudi Arabia","AR":"Argentina",
    "PL":"Poland","IR":"Iran","EG":"Egypt","TH":"Thailand","PK":"Pakistan",
    "NG":"Nigeria","UA":"Ukraine","VN":"Vietnam","MY":"Malaysia",
    "CO":"Colombia","ZA":"South Africa","BD":"Bangladesh","PH":"Philippines",
    "IL":"Israel","SE":"Sweden","NO":"Norway","DK":"Denmark","FI":"Finland",
    "PT":"Portugal","GR":"Greece","BE":"Belgium","CZ":"Czech Republic",
    "RO":"Romania","HU":"Hungary","CL":"Chile","PE":"Peru","NZ":"New Zealand",
    "IQ":"Iraq","QA":"Qatar","SG":"Singapore",
}

TLD_MAP = [
    (".com.cn","China"),(".cn","China"),(".ru","Russia"),(".de","Germany"),
    (".fr","France"),(".co.uk","United Kingdom"),(".uk","United Kingdom"),
    (".jp","Japan"),(".co.jp","Japan"),(".in","India"),(".com.br","Brazil"),
    (".br","Brazil"),(".ca","Canada"),(".it","Italy"),(".co.kr","South Korea"),
    (".kr","South Korea"),(".com.au","Australia"),(".au","Australia"),
    (".es","Spain"),(".com.mx","Mexico"),(".mx","Mexico"),
    (".co.id","Indonesia"),(".id","Indonesia"),(".nl","Netherlands"),
    (".com.tr","Turkey"),(".tr","Turkey"),(".com.sa","Saudi Arabia"),
    (".sa","Saudi Arabia"),(".com.ar","Argentina"),(".ar","Argentina"),
    (".pl","Poland"),(".ir","Iran"),(".eg","Egypt"),(".th","Thailand"),
    (".co.th","Thailand"),(".pk","Pakistan"),(".com.pk","Pakistan"),
    (".ng","Nigeria"),(".com.ng","Nigeria"),(".ua","Ukraine"),
    (".vn","Vietnam"),(".com.my","Malaysia"),(".my","Malaysia"),
    (".co","Colombia"),(".com.co","Colombia"),(".co.za","South Africa"),
    (".za","South Africa"),(".bd","Bangladesh"),(".com.bd","Bangladesh"),
    (".ph","Philippines"),(".com.ph","Philippines"),(".il","Israel"),
    (".co.il","Israel"),(".se","Sweden"),(".no","Norway"),(".dk","Denmark"),
    (".fi","Finland"),(".pt","Portugal"),(".gr","Greece"),(".be","Belgium"),
    (".cz","Czech Republic"),(".ro","Romania"),(".hu","Hungary"),
    (".cl","Chile"),(".pe","Peru"),(".co.nz","New Zealand"),(".nz","New Zealand"),
    (".iq","Iraq"),(".qa","Qatar"),(".com.sg","Singapore"),(".sg","Singapore"),
]

def tld_lookup(domain):
    for tld, country in TLD_MAP:
        if domain.endswith(tld):
            return country
    return None

def ipinfo_lookup(domain, cache):
    if domain in cache:
        return cache[domain]
    try:
        ip = socket.gethostbyname(domain)
        r = requests.get(f"https://ipinfo.io/{ip}/json", timeout=5)
        if r.status_code == 200:
            data = r.json()
            cc = data.get("country", "")
            country = ISO2_TO_NAME.get(cc)
            cache[domain] = country
            return country
    except:
        pass
    cache[domain] = None
    return None

def run():
    # Load top 500 domains
    df = pd.read_csv(f"{OUT_DIR}/top500_domains.csv")
    domains = df["SourceCommonName"].tolist()
    print(f"Top 500 domains loaded, total articles: {df['cnt'].sum():,}")

    # Layer 1: Wikidata
    wikidata = pd.read_csv("results/wikidata_domain_country.csv")
    wikidata_map = dict(zip(wikidata["domain"], wikidata["country"]))

    # IP cache
    ip_cache_file = f"{OUT_DIR}/ip_cache.json"
    ip_cache = json.load(open(ip_cache_file)) if os.path.exists(ip_cache_file) else {}

    results = []
    layer_counts = Counter()

    for i, domain in enumerate(domains, 1):
        article_count = df[df["SourceCommonName"]==domain]["cnt"].values[0]

        # Layer 1: Wikidata
        if domain in wikidata_map and wikidata_map[domain] in COUNTRIES:
            country = wikidata_map[domain]
            layer = "wikidata"

        # Layer 2: TLD
        elif tld_lookup(domain):
            country = tld_lookup(domain)
            layer = "tld"

        # Layer 3: ipinfo.io
        else:
            country = ipinfo_lookup(domain, ip_cache)
            layer = "ipinfo" if country else "unknown"
            if i % 10 == 0:
                with open(ip_cache_file, "w") as f:
                    json.dump(ip_cache, f)
            time.sleep(0.15)  # ~6 req/sec, well within free tier

        layer_counts[layer] += 1
        results.append({
            "domain": domain,
            "country": country,
            "layer": layer,
            "article_count": article_count
        })

        status = f"{country or '?':20s} [{layer}]"
        print(f"[{i:3d}/500] {domain:35s} {status}")

    # Save IP cache
    with open(ip_cache_file, "w") as f:
        json.dump(ip_cache, f)

    # Save results
    res_df = pd.DataFrame(results)
    res_df.to_csv(f"{OUT_DIR}/top500_mapped.csv", index=False)

    # Summary
    print(f"\n{'='*50}")
    print(f"Layer breakdown: {dict(layer_counts)}")
    covered = res_df[res_df["country"].notna()]
    covered_pct = covered["article_count"].sum() / res_df["article_count"].sum() * 100
    print(f"Coverage: {len(covered)}/500 domains = {covered_pct:.1f}% of articles")
    print(f"\nCountry distribution:")
    for country, cnt in res_df[res_df["country"].notna()].groupby("country")["article_count"].sum().sort_values(ascending=False).head(20).items():
        print(f"  {country:25s} {cnt:>10,}")

if __name__ == "__main__":
    run()
