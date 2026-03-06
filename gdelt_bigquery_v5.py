"""
GDELT BigQuery v5 — Source country via SCImago Media Rankings domain mapping
Most accurate BigQuery approach: 4,656 curated domain→country mappings

Setup:
  pip install google-cloud-bigquery pandas openpyxl
  gcloud auth application-default login

SCImago data: download from https://www.scimagomedia.com/rankings.php
  -> Save as results/scimago_domain_country.csv (columns: domain, country)
"""

from google.cloud import bigquery
import pandas as pd
import os, time, json

GCP_PROJECT = "YOUR_GCP_PROJECT_ID"
DAYS_BACK   = 30
OUT_DIR     = "results/bigquery_v5"
os.makedirs(OUT_DIR, exist_ok=True)

FIPS2_TO_NAME = {
    "US":"United States","CH":"China","RS":"Russia","GM":"Germany",
    "FR":"France","UK":"United Kingdom","JA":"Japan","IN":"India",
    "BR":"Brazil","CA":"Canada","IT":"Italy","KS":"South Korea",
    "AS":"Australia","SP":"Spain","MX":"Mexico","ID":"Indonesia",
    "NL":"Netherlands","TU":"Turkey","SA":"Saudi Arabia","AR":"Argentina",
    "PL":"Poland","IR":"Iran","EG":"Egypt","TH":"Thailand","PK":"Pakistan",
    "NI":"Nigeria","UP":"Ukraine","VM":"Vietnam","MY":"Malaysia","CO":"Colombia",
    "SF":"South Africa","BG":"Bangladesh","RP":"Philippines","IS":"Israel",
    "SW":"Sweden","NO":"Norway","DA":"Denmark","FI":"Finland","PO":"Portugal",
    "GR":"Greece","BE":"Belgium","EZ":"Czech Republic","RO":"Romania","HU":"Hungary",
    "CI":"Chile","PE":"Peru","NZ":"New Zealand","IZ":"Iraq","QA":"Qatar","SN":"Singapore",
}
COUNTRY_NAMES = sorted(set(FIPS2_TO_NAME.values()))


def build_query(scimago_df, days_back=30):
    domain_cases = "\n".join(
        f"    WHEN '{row.domain.replace(chr(39), chr(39)+chr(39))}' THEN '{row.country}'"
        for row in scimago_df.itertuples()
        if row.country in COUNTRY_NAMES
    )
    fips2_cases = "\n".join(
        f"    WHEN '{k}' THEN '{v}'" for k, v in FIPS2_TO_NAME.items()
    )
    country_names_sql = ", ".join(f"'{n}'" for n in COUNTRY_NAMES)

    return f"""
WITH base AS (
  SELECT
    SourceCommonName,
    SAFE_CAST(SPLIT(V2Tone, ',')[SAFE_OFFSET(0)] AS FLOAT64) AS tone_score,
    REGEXP_EXTRACT_ALL(V2Locations, r'[0-9]#[^#]*#([A-Z]{{2}})[^|#]*') AS loc_fips2_list
  FROM `gdelt-bq.gdeltv2.gkg_partitioned`
  WHERE
    DATE(_PARTITIONTIME) >= DATE_SUB(CURRENT_DATE(), INTERVAL {days_back} DAY)
    AND V2Tone IS NOT NULL AND V2Locations IS NOT NULL AND SourceCommonName IS NOT NULL
),
with_source AS (
  SELECT *,
    CASE SourceCommonName
{domain_cases}
      ELSE NULL
    END AS source_country
  FROM base
),
filtered AS (SELECT * FROM with_source WHERE source_country IS NOT NULL),
exploded AS (
  SELECT
    source_country, tone_score,
    CASE loc_fips2
{fips2_cases}
      ELSE NULL
    END AS target_country
  FROM filtered, UNNEST(loc_fips2_list) AS loc_fips2
)
SELECT
  source_country, target_country,
  ROUND(AVG(tone_score), 4)                                AS avg_tone,
  ROUND(COUNTIF(tone_score > 0) / COUNT(*) * 100, 2)      AS positive_ratio,
  COUNT(*)                                                  AS article_count
FROM exploded
WHERE source_country IS NOT NULL AND target_country IN ({country_names_sql})
GROUP BY 1, 2
ORDER BY source_country, avg_tone DESC
"""


def run():
    scimago = pd.read_csv("results/scimago_domain_country.csv")
    print(f"SCImago domains: {len(scimago)}")

    query = build_query(scimago, DAYS_BACK)
    with open(f"{OUT_DIR}/query.sql", "w") as f:
        f.write(query)
    print(f"Query saved ({len(query):,} chars). Running BigQuery...")

    client = bigquery.Client(project=GCP_PROJECT)
    t0 = time.time()
    job = client.query(query, job_config=bigquery.QueryJobConfig(use_query_cache=True))
    print(f"Job: {job.job_id}")
    df = job.to_dataframe()
    print(f"Done in {time.time()-t0:.1f}s — {len(df)} rows")

    df.to_csv(f"{OUT_DIR}/cross_coverage.csv", index=False)
    print(f"Saved: {OUT_DIR}/cross_coverage.csv")

    print("\nSource country article totals:")
    print(df.groupby("source_country")["article_count"].sum()
            .sort_values(ascending=False).head(20).to_string())

    print("\nSelf-coverage (diagonal):")
    self_cov = df[df["source_country"] == df["target_country"]].sort_values("avg_tone", ascending=False)
    print(self_cov[["source_country", "avg_tone", "positive_ratio", "article_count"]].to_string(index=False))

    return df


if __name__ == "__main__":
    run()
