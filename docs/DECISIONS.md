# Decisions (ADR log)

Short architecture decision records. Newest decisions are appended at the end.
Each entry: context, decision, consequences. Status is *accepted* unless noted.

## Pre-flight (2026-11-21)

Recorded before any design work, in the build sandbox used for v0.1.0.

| Check | Result |
|---|---|
| Python | 3.13.18 default; 3.11 and 3.12 also present |
| uv | 0.11.32 |
| Node / npm | 22.23.5 / 10.9.9 |
| git | 2.43.0 |
| gh | present (GitHub access scoped to this repository only) |
| docker | binary present (not used for builds here) |
| vhs, ttyd, ffmpeg, minisign, cosign | **not installed** (no global installs allowed) |
| Chromium + Playwright | pre-installed (used for Lighthouse/axe and screenshots) |
| PyPI, npm registry | reachable |
| github.com (git over HTTPS) | reachable read-only through the sandbox git proxy |
| crt.sh, OpenPhish, URLhaus, urlscan.io, rdap.org, data.iana.org, publicsuffix.org, certstream.calidog.io, dns.google | **blocked** by the sandbox egress policy (HTTP 403 at the proxy) |
| Google Safe Browsing API host | reachable, but needs an API key (none available) |
| Direct DNS resolution | **unavailable** (no resolver; all traffic goes through an HTTPS proxy) |

Consequences: every external source adapter is implemented against recorded
fixtures (reserved domains only) and marked `degraded` in
[SOURCES.md](SOURCES.md) until it is verified live from GitHub Actions, which
has open egress. `lureradar doctor` reports the real health wherever it runs.

## ADR-001: Generic engine, GTA VI as the first campaign pack

LureRadar is a launch-lure engine; campaign-specific knowledge (keywords,
intents, brands, allowlist, dated facts) lives in YAML packs under `packs/`.
No trademark appears in package, repo or domain names. Mentions in pack data
are nominative only (see [TRADEMARKS.md](../TRADEMARKS.md)).

## ADR-002: Repository, site URL and single BASE_URL

Per the maintainer's setup, the repository is `AbdelrahmanMostafa-Eng/LureRadar`
and the site is the GitHub Pages project site
`https://abdelrahmanmostafa-eng.github.io/LureRadar/` (sub-path deployment).
The base URL is defined once in `src/lureradar/config.py` (`DEFAULT_BASE_URL`,
overridable with `LURERADAR_BASE_URL`) and once in `web/astro.config.mjs`
(`site` + `base`); a test asserts they match and `scripts/check_hostnames.py`
fails CI if the hostname is hardcoded anywhere else in code. Generated files
(JSON Schemas, extension config) and `pyproject.toml` metadata are explicit,
documented exceptions. Prose (README, docs) may link to the site.

## ADR-003: Facts drive rules, and prose cites facts

Claims such as "no PC version has been announced" are stored in
`packs/gta6/facts.yaml` with `as_of` dates and sources, re-verified by web
search on 2026-11-21 (console release scheduled 2026-11-19 on PS5 and Xbox
Series X|S; no official PC announcement; an October 2026 press report of an
early-2027 PC window is tracked as a rumour). The `claims_unreleased_platform`
rule reads `platforms.<name>.status`; flipping `pc` to `released` disables it
for PC. The README and site always cite the fact and its date. The primary
source (Rockstar's site) could not be fetched from the sandbox; secondary
sources are cited and the facts carry a re-verification note.

## ADR-004: Offline PSL, implicit `*` rule, extra shared-host suffixes

`tldextract` runs with `suffix_list_urls=()` so it never downloads the Public
Suffix List; the snapshot bundled with the library is used. Private suffixes
are included (`foo.github.io` is its own site). Unknown TLDs (`.test`,
`.invalid`, internal names) follow the PSL's implicit `*` rule as browsers do.
A short list of shared hosts missing from the PSL (`weebly.com`,
`000webhostapp.com`...) is treated as private suffixes
(`src/lureradar/data/shared_hosts.yaml`).

## ADR-005: Two kinds of allowlist entries

`outlets` (publishers, stores, wikis, official sites) are hard-cleared.
`platforms` (YouTube, Reddit, file hosts...) are never blocklisted at domain
level, but URLs on them are still assessed and capped at SUSPICIOUS unless
external reputation corroborates. Otherwise a `mediafire.com/.../GTA6_PC_Setup.exe`
link would be silently cleared. Allowlist entries require evidence of
legitimacy; entries we could not vouch for were removed rather than guessed.

## ADR-006: Precision by construction

Keywords alone never score. Path-only matches count at half weight. Short
vocabulary words ("pc", "key", "ios") only count inside fully segmented tokens,
so `npc` or `studios` do not match. Short brands ("steam", "xbox") are matched
only through look-alike substitutions, never plain edits (avoids "stream").
Typosquats must keep the first character. The benchmark (Phase 4) is the
final arbiter; weights are frozen in `src/lureradar/scoring/weights.py`.

## ADR-007: selectolax lexbor backend

selectolax 1.0 removed the Modest backend; we use `selectolax.lexbor`. No
JavaScript is ever executed and only short snippets/hashes are retained.

## ADR-008: STIX 2.1 without a runtime dependency on `stix2`

The `stix2` library pulls in `requests`, `simplejson` and ANTLR. We emit STIX
2.1 JSON directly (deterministic UUIDv5 ids) and validate it in tests with
`stix2` as a dev dependency. Smaller install, same guarantees.

## ADR-009: GitHub Actions pinned by commit SHA

Workflow actions are pinned to the commit of their latest release (resolved
with `git ls-remote` on 2026-11-21) with the version in a trailing comment.
Dependabot (`github-actions` ecosystem) keeps them current. All workflows set
least-privilege `permissions:`.

## ADR-010: Verification when the build host has no egress

Direct fetches from the build sandbox, and a web-fetch agent used as a
second path, both failed for every threat-intel and publisher host. Stuck
protocol applied: no retries. Facts and official statements (PC Watch
timeline) were verified through **live search-index lookups** of the
official domains (rockstargames.com, take2games.com), with that method
recorded next to each entry. Source adapters were built against fixtures;
`feed-refresh.yml` runs `lureradar doctor` on GitHub runners to produce the
live verification.

## ADR-011: SSRF policy details

Besides private/loopback/link-local/CGNAT/multicast/reserved ranges, the
guard refuses 6to4 and Teredo addresses outright, unwraps IPv4-mapped and
NAT64 forms, refuses `inet_aton`-style numeric hosts (`0x7f000001`,
`127.1`), internal suffixes (`.local`, `.internal`, `.home.arpa`,
`localhost`), credentials in URLs, and ports other than 80/443/8080/8443.
If *any* DNS answer is non-public the host is refused, and the connection is
pinned to a vetted IP with SNI preserved. The fetcher ignores proxy
environment variables (`trust_env=False`) so the vetted address is the one
actually contacted; live mode therefore needs direct egress.

## ADR-012: `--live` only contacts keyed reputation services

`check --live` contacts the target (DNS, TLS, one bounded HTTP fetch), RDAP,
and only the reputation services the user configured with a key. It never
downloads third-party feeds on the user's behalf. The verdict lists every
service contacted (`Enrichment.contacted`).
