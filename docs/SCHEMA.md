# Output schemas

LureRadar's machine-readable outputs are versioned contracts. JSON Schemas
are generated from the pydantic models (`make schemas`) and committed in
[`src/lureradar/schemas/`](../src/lureradar/schemas/); a test fails if they
drift from the code.

| Output | Schema | Version field |
|---|---|---|
| `lureradar check --json` | [`verdict.schema.json`](../src/lureradar/schemas/verdict.schema.json) | `schema_version` (currently `1.0`) |
| `feeds/latest.json`, `feeds/all.json` | [`feed.schema.json`](../src/lureradar/schemas/feed.schema.json) | `schema_version` (currently `1.0`) |
| `packs/<id>/pack.yaml` (resolved) | [`pack.schema.json`](../src/lureradar/schemas/pack.schema.json) | pack `version` |
| `feeds/pc-watch.json` | `PcWatchState` in `src/lureradar/pcwatch/status.py` | `schema_version` (currently `1.0`) |

**Compatibility policy.** Within a major schema version, fields are only
added, never removed or renamed, and enum values are only added. Breaking
changes bump the major version and are announced in the CHANGELOG one release
in advance.

## Verdict (`check --json`)

```json
{
  "schema_version": "1.0",
  "target": "hxxps://rockstar-gta6-pc-download[.]test/free-key",
  "kind": "url",
  "host": "rockstar-gta6-pc-download[.]test",
  "registrable_domain": "rockstar-gta6-pc-download[.]test",
  "score": 75,
  "tier": "likely",
  "signals": [
    {"id": "claims_unreleased_platform", "weight": 30, "category": "platform", "live": false,
     "explanation": "Promises \"download\" of GTA VI for PC: no official PC release exists (fact pc_release, as of 2026-11-21)",
     "evidence": ["rockstar-gta6-pc-download[.]test"]}
  ],
  "corroborated": false,
  "allowlisted": false,
  "mode": "offline",
  "packs": ["gta6"],
  "next_steps": ["..."],
  "urls": [],
  "generated_at": "2026-11-21T12:00:00Z"
}
```

- Every indicator string (`target`, `host`, `registrable_domain`, `evidence`)
  is **defanged**.
- `kind` is `url`, `domain` or `text`. For `text`, `urls` holds one verdict per
  link found in the message.
- `mode` is `live` when `--live` enrichment ran.
- Exit codes: `0` clear, `10` suspicious, `20` likely, `30` confirmed, `1` error.

## Feed document (`latest.json`)

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-11-21T12:00:00Z",
  "generator": "LureRadar/0.1.0",
  "base_url": "https://abdelrahmanmostafa-eng.github.io/LureRadar/",
  "license": "CC0-1.0",
  "min_tier": "likely",
  "count": 1,
  "notice": "Detections are automated and may contain false positives...",
  "indicators": [
    {"domain": "rockstar-gta6-pc-download.test", "url": "https://rockstar-gta6-pc-download.test/",
     "tier": "confirmed", "score": 100, "status": "active",
     "first_seen": "2026-11-21T06:00:00Z", "last_seen": "2026-11-21T06:00:00Z",
     "sources": ["crtsh"], "packs": ["gta6"], "signals": [{"id": "...", "weight": 30, "...": "..."}],
     "dispute_url": "https://github.com/AbdelrahmanMostafa-Eng/LureRadar/issues/new?template=false-positive-review.yml&title=..."}
  ]
}
```

`domain` in feeds is the registrable domain in **raw** form, because feeds are
consumed by machines (DNS blockers). Everything rendered for humans (CLI,
dashboard, issues) is defanged. `count` always equals `len(indicators)`.

## PC Watch state (`pc-watch.json`)

Key fields: `status` (`NOT_ANNOUNCED`, `ANNOUNCED_UNDATED`, `ANNOUNCED_DATED`,
`RELEASED`, `UNKNOWN`), `answer` (the one-sentence honest answer),
`confirmed_status` and `confirmed_as_of` (from `facts.yaml`), `last_checked`,
`last_success`, `last_changed`, `stale`, `review_pending`, `suggested_status`,
`sources[]` (per-source check results), `timeline[]` (verified official
statements), `disclaimer`. See [PC_WATCH.md](PC_WATCH.md).
