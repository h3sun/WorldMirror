"""
Regenerate website/index.html with latest data from results/merged_coverage.csv
Run this after updating any data files.
"""

import pandas as pd
import json
import re

df = pd.read_csv("results/merged_coverage.csv")
data = df.to_dict(orient="records")

api_count = sum(1 for r in data if r.get("source") == "api")
bq_count  = sum(1 for r in data if r.get("source") == "bigquery")

with open("website/index.html") as f:
    html = f.read()

# Embed data inline
new_data_js = f"const data = {json.dumps(data)}"
html = re.sub(r"const data = \[.*?\](?=;\s*ALL = data)", new_data_js, html, flags=re.DOTALL)

# Update header stats
html = re.sub(
    r"\d+ API verified</span> \+ <span[^>]*>\d+ BigQuery estimated[^<]*",
    f"{api_count} API verified</span> + <span style=\"color:#666\">{bq_count} BigQuery estimated (SCImago)",
    html
)

with open("website/index.html", "w") as f:
    f.write(html)

print(f"Website updated: {api_count} API + {bq_count} BigQuery pairs ({len(data)} total)")
print(f"HTML size: {len(html):,} bytes")
