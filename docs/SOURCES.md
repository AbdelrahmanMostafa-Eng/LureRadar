# Data sources

Every source adapter implements the same `Source` protocol
(`src/lureradar/sources/base.py`): `fetch(since) -> Iterable[Candidate]`,
`health() -> SourceHealth`, and declared `terms_url`, `requires_key` and
`rate_limit`. The pipeline keeps running when a source is down,
rate-limited or missing a key; `lureradar doctor` prints live health from
wherever you run it.

**Status meanings:** `ok` verified live · `degraded` implemented and tested
against recorded fixtures, not yet verified live from a build host ·
`requires_key` needs a credential (skipped without one) · `disabled` off by
default.

## Source table

| Source | Kind | Endpoint | Key | Rate limit / politeness | What we publish | Status (2026-11-21) |
|---|---|---|---|---|---|---|
| [crt.sh](https://crt.sh/) | candidates | `crt.sh/?q=%term%&output=json` | no | one query per campaign term, >= 5 s apart, backoff on 429/5xx | derived domains + our scores | `degraded` |
| [OpenPhish community feed](https://openphish.com/) | candidates + reputation | `openphish.com/feed.txt` | no | feed refreshes ~12 h; fetch at most hourly | **not redistributed**; seeds candidates, corroborates | `degraded` |
| [abuse.ch URLhaus](https://urlhaus.abuse.ch/api/) | candidates + reputation | `urlhaus-api.abuse.ch/v1/` | **Auth-Key** | fair use | not redistributed raw; corroborates | `requires_key` |
| [Google Safe Browsing v4](https://developers.google.com/safe-browsing/v4) | reputation | `safebrowsing.googleapis.com/v4/threatMatches:find` | **API key** | per-key quota; Lookup API is non-commercial | never redistributed | `requires_key` |
| [urlscan.io](https://urlscan.io/docs/api/) | candidates + reputation | `urlscan.io/api/v1/search/` | optional | public search is rate-limited; a key raises quotas | not republished | `degraded` |
| Community reports | candidates | `data/reports/*.yaml` (this repo) | no | local files | CC0, defanged | `ok` when run from the repo |
| CertStream-compatible CT stream | candidates (watch) | configurable websocket (`LURERADAR_CERTSTREAM_URL`) | no | push stream; public endpoints come and go | derived domains | `disabled` (stream-only) |
| IANA RDAP bootstrap + RDAP servers | enrichment | `data.iana.org/rdap/dns.json`, fallback `rdap.org` | no | cached 7 days; one lookup per candidate | registration age only | `degraded` |

Raw third-party data is never republished. Feeds contain LureRadar's own
indicators, scores and signal explanations, dedicated to the public domain
(CC0, see [DATA_LICENSE](../DATA_LICENSE)).

## How each status was established

The v0.1.0 build sandbox only allowed package registries and GitHub. Every
threat-intel host returned HTTP 403 at the sandbox's egress proxy, and a
separate web-fetch attempt failed DNS resolution for all of them. This was
recorded by running `lureradar doctor` (see
[DECISIONS.md](DECISIONS.md#pre-flight-2026-11-21)). Therefore:

- adapters were implemented against **recorded fixtures** with the response
  shapes these services document; fixtures use reserved domains only;
- each adapter's parser, retries, key handling and health probe are unit-tested;
- the `feed-refresh` workflow runs `lureradar doctor --json` on GitHub-hosted
  runners (open egress) at the start of every run and uploads the report, so
  the first scheduled run produces the live verification this table needs.
  Update `last_verified` below from that report.

| Source | last_verified (live) | Verified by |
|---|---|---|
| crt.sh | 2026-11-24: reachable but unreliable (doctor probe timed out; scan queries finished in 131 s with 0 candidates). Partial or total query failures are now reported as `partial` / `failed`, never as an empty `ok`. | `feed-refresh` doctor + scan report |
| OpenPhish | 2026-11-24: OK (HTTP 200; 265 entries, none launch-themed) | `feed-refresh` doctor + scan report |
| URLhaus | not enabled (needs the `LURERADAR_URLHAUS_KEY` secret) | `feed-refresh` doctor report |
| Safe Browsing | not enabled (needs the `LURERADAR_SAFEBROWSING_KEY` secret) | `feed-refresh` doctor report |
| urlscan.io | 2026-11-24: OK (HTTP 200) | `feed-refresh` doctor + scan report |
| RDAP | not exercised yet: no candidate passed the campaign prefilter, so nothing needed enrichment | `feed-refresh` scan report |
| PC Watch: Take-Two press releases, SEC EDGAR, Steam | 2026-11-24: OK (5, 40 and 1 relevant items; 0 PC findings) | `pc-watch` run |

## Terms notes (re-check before enabling in production)

- **OpenPhish**: the community feed is free for non-commercial use and its
  terms restrict redistribution; LureRadar never republishes it.
- **Safe Browsing Lookup API**: Google limits it to non-commercial use;
  commercial deployments should use the Web Risk API.
- **URLhaus**: abuse.ch data is free; API access requires a (free) Auth-Key.
- **urlscan.io**: results are not republished; respect the search quotas.
- **crt.sh**: a free community service; keep request volume low.

## Reference lists shipped with the package

| File | Purpose | Provenance |
|---|---|---|
| `src/lureradar/data/abused_tlds.yaml` | `abused_tld` signal | compiled from Spamhaus / Interisle / APWG public rankings; flagged `needs_live_reverification` |
| `src/lureradar/data/shorteners.yaml` | text and redirect signals | well-known public shorteners |
| `src/lureradar/data/shared_hosts.yaml` | treat site builders as private suffixes | checked against the bundled PSL snapshot |
| `src/lureradar/data/hosting_reputation.yaml` | `hosting_reputation` | **empty**: no source could be verified |
| `src/lureradar/data/allowlist_base.yaml` | global outlets and platforms | maintainers' review; entries we could not vouch for were removed |
