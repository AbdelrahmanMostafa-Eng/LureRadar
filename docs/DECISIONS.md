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

## ADR-013: Feed signatures use the minisign format

Of the two options (Sigstore or minisign), feeds use **minisign-format
Ed25519 signatures** (BLAKE2b-prehashed), produced in pure Python with
`cryptography`. Reasons: users verify with a tiny standard tool or
`lureradar feed verify`, fully offline, and the test suite can exercise
signing end to end. Interoperability is verified against an independent
implementation (`py-minisign`) in `tests/unit/test_signing.py`. The secret
lives only in the `LURERADAR_SIGNING_KEY` Actions secret (our compact base64
format; `lureradar feed keygen` prints it once and never writes it to disk).
Release artifacts (wheels, SBOM) are signed separately with Sigstore keyless
signing in `release.yml`.

## ADR-014: Feed unit, publication and retention

Feeds list **registrable domains** (eTLD+1, PSL private suffixes included, so
`user.github.io` is the unit, never `github.io`). Feeds are never committed to
`main`: `feed-refresh.yml` attaches them to a dated `feeds-YYYY-MM-DD` release
(the permanent daily snapshot) and to the rolling `feeds-latest` release;
`pages.yml` is the single Pages deployer and pulls both. Pipeline state is a
SQLite file in the Actions cache. Indicators go `stale` after 30 days without
a re-sighting and are purged after 90. Each run re-applies the allowlist and
offline rules to every active indicator, so an allowlist PR or a facts change
takes effect within one run.

## ADR-015: PC Watch is facts-driven, with a human in the loop

The published PC status is the `pc_release` fact in `facts.yaml`, which only
a maintainer commit can change. Automation (every 4 hours) can open a review
issue with official evidence, and downgrade the status to UNKNOWN when the
last fully successful check (all required sources OK) is older than 36 hours.
A source yielding fewer game items than `expect_min_items` counts as failed,
so a page redesign cannot masquerade as "not announced". New fact statuses
(`announced_undated`, `announced_dated`, `released`) make the backing platform
count as released: `claims_unreleased_platform` drops to 0 for PC and the
official PC storefronts in `pc_watch.yaml` join the allowlist.

## ADR-016: Calibration keeps the brief's weights; the benchmark fixed bugs instead

`make bench` measures the frozen weights on 522 real benign domains, 50 hard
negatives, 30 benign article URLs, 1,298 synthetic lures (11 pattern
families) and 600 synthetic messages. Result: 0 benign false positives at
LIKELY+ *and* SUSPICIOUS+, with or without allowlists, and a 45-point margin
under the LIKELY threshold. We deliberately did **not** raise weights to
improve offline recall: the synthetic lures come from our own generators, so
fitting to them would overfit and erode the precision margin that protects
real users. Instead the benchmark surfaced two real bugs (multi-word platform
terms like "Switch 2" never matched; a brand token counted again as an
intent), both fixed with regression tests. Offline recall at LIKELY+ is
therefore low by design and reported as such; the newly-registered
simulation shows how live signals lift it. The benchmark exits non-zero if a
benign domain, hard negative or benign message reaches LIKELY.

## ADR-017: Demo GIF without vhs

`vhs` (and its `ttyd`/`ffmpeg` dependencies) is not installable in the build
sandbox. `make demo` runs `vhs assets/demo.tape` when vhs is present and
otherwise falls back to `scripts/render_demo.py`: the real verdict card is
rendered by Rich, exported to SVG with a terminal theme built from the design
tokens, rasterised with resvg and assembled into a GIF with Pillow (about
6 s, about 65 KiB). The GIF shows the exact offline README command.

## ADR-018: Release and container details

Releases build once and publish the same artifacts to GitHub Releases
(with SHA256SUMS, CycloneDX SBOM, Sigstore bundles and provenance
attestations) and to PyPI through Trusted Publishing. The container image is
`ghcr.io/abdelrahmanmostafa-eng/lureradar` (GHCR requires lowercase names),
runs as UID 10001, keeps its cache in `/tmp` so `--read-only` works, and is
attested. Base images are tracked by Dependabot rather than pinned by digest,
because the build sandbox could not query a registry to resolve digests.

## ADR-019: Community reports go through a PR, never straight to feeds

The "Report a lure" form triggers `community-report.yml`, which passes the
untrusted issue body to `scripts/community_report.py` through an environment
variable (never shell interpolation), validates and defangs it, writes
`data/reports/<date>-issue<N>.yaml` and opens a pull request with the offline
verdict. A maintainer merges; the pipeline then scores it like any other
candidate, so a report cannot list a domain by itself.

## ADR-020: Static Astro site with a parity-tested client checker

The dashboard is Astro 7 (static output, exact pinned versions, telemetry
off) with hand-written CSS variables from `web/src/styles/tokens.css`,
self-hosted Inter and JetBrains Mono, and no third-party requests. The
in-browser checker (`web/src/lib/checker.ts`) is a TypeScript port of the
offline engine fed by `rules.json` exported from the Python packs (including
the full Public Suffix List and a Unicode skeleton map). `npm test` asserts
it matches the Python engine on 132 cases (score, tier and signal ids), so the
two cannot drift silently. Data under `web/src/data/generated/` is rebuilt by
`scripts/build_site_data.py` on every build; without published feeds the site
shows clearly labelled demo data from the fixture pipeline. Audit (local
preview, Lighthouse 13.6 / axe-core 4.14): 100 in all four categories on
Home, Radar, Check and PC Watch; 0 axe violations on 16 pages in both themes
(`web/audit-results.json`). A clean-checkout build exposed that the Python
`.gitignore` template's `lib/` rule hid `web/src/lib/`; it is now anchored to
the repository root.

## ADR-021: Fresh-eyes review before release

A final review as a skeptical maintainer and a hostile reviewer, run from a
fresh clone (`make install check bench demo smoke-wheel site` all green, the
tree unchanged afterwards, so the GIF and benchmark report are reproducible
byte for byte), found and fixed:

- the template `lib/` ignore rule hid `web/src/lib/` (anchored to the root);
- PC Watch review issues embedded fetched titles/snippets verbatim, so an
  `@handle` or `#123` on a fetched page could ping people or link issues;
  mentions and references are now neutralised (test added);
- PC Watch's UNKNOWN sentence repeated itself (reworded).

Accepted residual items, tracked in the release checklist: workflows assume
the `lure-report`, `false-positive`, `pc-watch` and `reports` labels exist;
signed feeds need the maintainer-generated key; live source verification
happens on the first scheduled CI run.

## ADR-022: Vercel deployment as a single static `web` service

The repository was proposed for Vercel "services" with a Python `app` service
at the root receiving all traffic. The code has no Python HTTP application
(the package is a Typer CLI and library), and the site is a fully static Astro
build whose only runtime requests are same-origin files, so that layout would
route every request to a service with nothing to serve. `vercel.json`
therefore declares one public service, `web`, with a catch-all rewrite and no
bindings (bindings only resolve inside functions, and nothing calls another
service). The Vercel build derives `LURERADAR_BASE_URL` from Vercel's system
variables, because the default base URL is the GitHub Pages sub-path. GitHub
Pages stays the canonical deployment unless maintainers decide otherwise.
