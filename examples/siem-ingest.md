# SIEM and TIP ingestion

| Format | URL (append to the site base) | Typical consumer |
|---|---|---|
| STIX 2.1 bundle | `feeds/stix.json` | OpenCTI, MISP (STIX import), TIPs |
| CSV | `feeds/indicators.csv` | Splunk lookups, Elastic, Sentinel watchlists |
| JSON | `feeds/latest.json` | anything; richest format (signals, tiers, dispute links) |

Each indicator carries `tier`, `score`, `first_seen`, `last_seen`, `sources`,
the explaining `signals`, and a `dispute_url`. STIX indicators use deterministic
UUIDv5 ids, so re-imports update instead of duplicating, and `confidence` maps
from the tier (LIKELY 75, CONFIRMED 95).

## Splunk lookup (CSV)

The CSV starts with one `#` metadata line; skip it when loading:

```bash
curl -fsS https://abdelrahmanmostafa-eng.github.io/LureRadar/feeds/indicators.csv | grep -v '^#' > lureradar_indicators.csv
```

```text
| inputlookup lureradar_indicators.csv | rename domain AS query | ...
```

## Python

```python
import httpx

feed = httpx.get("https://abdelrahmanmostafa-eng.github.io/LureRadar/feeds/latest.json").json()
bad = {i["domain"] for i in feed["indicators"]}
```

Verify downloads with `lureradar feed verify` before ingesting in production.
Data is CC0: no attribution required, but appreciated.
