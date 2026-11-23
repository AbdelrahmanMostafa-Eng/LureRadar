# How LureRadar works

```mermaid
flowchart LR
  subgraph Sources
    CT[crt.sh CT search]
    OP[OpenPhish]
    UH[URLhaus]
    US[urlscan.io]
    CR[Community reports]
  end
  Sources --> N[Normalise\nregistrable domain, IDNA]
  N --> D[Dedupe + state\nSQLite, 30/90-day retention]
  D --> P[Lexical prefilter\ncampaign relevance]
  P --> E[Enrich\nDNS, RDAP, TLS,\nhardened HTTP]
  E --> S[Score\nnamed signals]
  S --> T[Tier]
  T --> F[Feeds\nhosts, ABP, RPZ, JSON,\nCSV, STIX + signatures]
  T --> W[Dashboard\nGitHub Pages]
  PW[PC Watch\nofficial sources] -.facts.yaml.-> S
```

## 1. Campaign packs

A pack (`packs/<id>/`) describes one launch: keywords lures use, intent terms,
brands that get impersonated (names and official domains, never logos), an
allowlist, and **dated, sourced facts** such as "no PC version announced as of
2026-11-21". Rules read the facts, so when the facts change the rules follow.
See [PACKS.md](PACKS.md).

## 2. Offline engine (`lureradar check`)

1. **Parse.** Defanged input is refanged; URLs, domains and free text are told
   apart; hostnames are IDNA-normalised and split with the offline Public
   Suffix List (so `user.github.io` is its own site).
2. **Allowlist.** Established outlets are hard-cleared. User-content
   platforms are never blocklisted, but the URL on them is still assessed.
3. **Detectors.** Pure functions return named signals with explanations and
   defanged evidence: keyword + intent, unreleased-platform claims, brand
   typosquat/combosquat, homoglyph IDNs, abuse-prone TLDs. See [SIGNALS.md](SIGNALS.md).
4. **Score and tier.** Weights are summed and clamped to 0-100, then mapped to
   CLEAR / SUSPICIOUS / LIKELY / CONFIRMED with explicit overrides.
5. **Explain.** The verdict lists every signal, a fact check where relevant,
   and what to do next.

Offline mode opens no sockets; a test enforces it.

## 3. Live enrichment (`--live` and the pipeline)

The [hardened fetcher](THREAT_MODEL.md#hardened-fetcher) contacts the target
only after SSRF checks on every DNS answer and redirect, pins the vetted IP,
reads at most 1 MB of *text* within 10 seconds, never downloads binaries,
never runs JavaScript and keeps no cookies. RDAP gives registration age, TLS
gives certificate freshness, the page gives lure patterns (only short
snippets and a SHA-256 are kept). Configured reputation services add
external evidence.

## 4. Pipeline (`lureradar scan`, daily in GitHub Actions)

Collect candidates from sources → normalise and merge by registrable domain →
**prefilter** (offline score must show campaign relevance; drops unrelated
phishing and noise before any network work) → enrich (bounded concurrency,
time budget) → score → store in SQLite state → apply retention → re-apply the
allowlist and facts to every active indicator → export and sign feeds.

## 5. Publication

`feed-refresh.yml` publishes feeds as release assets (dated snapshot + rolling
latest); `pages.yml` deploys the dashboard and feeds to GitHub Pages. Nothing
generated is committed to `main`. See [FEEDS.md](FEEDS.md).

## 6. PC Watch

A separate workflow checks official sources every 4 hours for a PC
announcement. It never flips the status itself: a maintainer commit to
`facts.yaml` does, and that commit also switches off PC lure claims. See
[PC_WATCH.md](PC_WATCH.md).

## Why not machine learning or an LLM?

Precision and explainability. A blocklist that cannot say *why* it listed a
domain cannot be disputed or fixed quickly. Named signals make every verdict
auditable, every false positive fixable with one allowlist line, and every
weight change measurable with `make bench`.
