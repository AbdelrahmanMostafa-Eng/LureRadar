# Feeds

LureRadar publishes static, cacheable feeds from GitHub Pages. Every URL
below is relative to the site's `BASE_URL`
(`https://abdelrahmanmostafa-eng.github.io/LureRadar/` for the canonical
deployment, configured once in `src/lureradar/config.py`).

## Endpoints

| File | Format | Use it for |
|---|---|---|
| `feeds/latest.json` | LureRadar JSON ([schema](../src/lureradar/schemas/feed.schema.json)) | everything below is derived from this |
| `feeds/all.json` | same, including SUSPICIOUS | dashboards, research (not for blocking) |
| `feeds/hosts.txt` | hosts file (`0.0.0.0 domain`) | Pi-hole, `/etc/hosts`, routers |
| `feeds/domains.txt` | one domain per line | Pi-hole, AdGuard Home, NextDNS, scripts |
| `feeds/adguard.txt` | Adblock syntax (`\|\|domain^`) | AdGuard, uBlock Origin |
| `feeds/rpz.zone` | DNS Response Policy Zone | BIND, Unbound, Knot, PowerDNS |
| `feeds/stix.json` | STIX 2.1 bundle | TIPs, SIEMs, MISP/OpenCTI import |
| `feeds/indicators.csv` | CSV (leading `#` metadata line) | spreadsheets, SIEM lookups |
| `feeds/stats.json` | counts, new in 24h/7d, top signals | dashboards, badges |
| `feeds/shields-*.json` | [shields.io endpoint](https://shields.io/badges/endpoint-badge) JSON | README badges |
| `feeds/pc-watch.json`, `feeds/pc-watch.atom` | PC Watch state and Atom feed | see [PC_WATCH.md](PC_WATCH.md) |
| `feeds/SHA256SUMS` | checksums of every file | integrity |
| `feeds/*.minisig` | detached minisign signatures | authenticity |

Every feed file carries `generated_at`, `schema_version` and `count` (in a
header comment for text formats, as fields for JSON, in a `note` object for
STIX). Shields badge files follow shields.io's own schema instead.

**Default blocklists contain LIKELY and CONFIRMED indicators only.**
SUSPICIOUS indicators appear on the dashboard and in `all.json`; self-hosters
can opt in with `lureradar export --format hosts --input all.json --min-tier suspicious`.

## Cadence and freshness

The `feed-refresh` workflow runs daily (05:17 UTC) and on demand. GitHub
Actions cron is **best-effort**: runs can be delayed or skipped under load.
Always check `generated_at` (or the "feed updated" badge). Each run is also
attached to a dated GitHub release (`feeds-YYYY-MM-DD`) as a permanent
snapshot, and to the rolling `feeds-latest` release.

## Retention

- An indicator not re-sighted for **30 days** becomes `stale` and leaves every feed.
- Stale indicators are **purged after 90 days**. Recycled domains are never
  blocklisted forever.
- If a domain is added to an allowlist (`packs/*/allowlist.yaml` or
  `src/lureradar/data/allowlist_base.yaml`), it is removed on the **next run**.

## Verify what you download

Signatures use the minisign format (Ed25519). The public key is committed at
[`keys/lureradar-feed.pub`](../keys/README.md) once the maintainers generate it.

```bash
minisign -Vm latest.json -p keys/lureradar-feed.pub
```

```bash
lureradar feed verify ./feeds --pubkey keys/lureradar-feed.pub --require-signature
```

`feed verify` also re-parses every format (hosts, ABP, RPZ, CSV, STIX), checks
that they list exactly the indicators in `latest.json`, and validates
`SHA256SUMS`. For offline checks, `lureradar feed pull` downloads
`latest.json`, refuses to save it if a signature check fails, and caches it
for `lureradar check`.

## Disputes and removal

Every indicator includes a `dispute_url` that opens the
[false-positive review](https://github.com/AbdelrahmanMostafa-Eng/LureRadar/issues/new?template=false-positive-review.yml)
form with the indicator pre-filled (defanged). Target: triage within 2
business days. A confirmed false positive is fixed by a one-line allowlist PR
and disappears from the feeds on the next pipeline run.

## Licence and attribution

Feed data is CC0-1.0 ([DATA_LICENSE](../DATA_LICENSE)). Feeds contain
LureRadar's own indicators and scores; raw third-party data is never
republished (see [SOURCES.md](SOURCES.md)). Detections are automated and may
contain false positives. No warranty.
