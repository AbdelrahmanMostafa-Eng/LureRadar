# Threat model

LureRadar handles hostile input by design: lure URLs, scam pages, and data
from third-party feeds. This document lists what we protect, from whom, and
how.

## Assets

1. **Users' safety and privacy**: running `check` must never put a user at
   risk or leak what they check.
2. **Infrastructure that runs LureRadar**: CI runners and self-hosted
   `watch` deployments must not be turned against internal networks.
3. **Feed integrity**: consumers load our blocklists into DNS resolvers and
   browsers.
4. **Trust in verdicts and PC Watch**: false positives harm legitimate sites;
   a false "PC announced" would push users toward scams.
5. **The supply chain**: releases, workflows and secrets.

## Adversaries

- Lure operators who control target pages, DNS and redirects and want to
  attack the scanner, poison results, or get a legitimate site blocklisted.
- People submitting false reports or fake "official" pages.
- Supply-chain attackers targeting dependencies, actions or release artifacts.

## Hardened fetcher

`src/lureradar/enrich/http_fetch.py` and `src/lureradar/util/ssrf.py`
(tests: `tests/unit/test_http_fetch.py`, `tests/unit/test_ssrf.py`,
`tests/integration/test_live_local_server.py`):

| Threat | Mitigation |
|---|---|
| SSRF to internal services or cloud metadata | Only `http`/`https`, ports 80/443/8080/8443, no credentials; every DNS answer must be globally routable (private, loopback, link-local incl. 169.254.169.254, CGNAT, multicast, reserved, documentation, 6to4, Teredo, IPv4-mapped forms refused); numeric `inet_aton` hosts refused; internal suffixes refused. |
| DNS rebinding | If *any* answer is non-public the host is refused; the connection is pinned to the vetted IP (SNI and certificate checks keep the hostname). |
| Redirect tricks | Every hop re-validated and re-resolved; at most 5 redirects. |
| Slowloris, huge pages, decompression bombs | One 10-second deadline per fetch; 1 MB cap applied after decompression; absurd `Content-Length` refused. |
| Malware delivery | Only text content types are read; binaries and attachments are refused before a single body byte is read. Nothing is executed; JavaScript never runs. |
| Tracking and fingerprinting | No cookies kept, no proxy environment, honest User-Agent pointing to the `/bot/` page. |
| Hostile HTML | Parsed with selectolax (lexbor), no script execution; only short snippets and a SHA-256 are kept. |
| Hostile XML (PC Watch feeds) | Documents declaring a DTD or entities are refused before parsing. |

## Feed integrity

- Exporters accept only strictly valid hostnames, so a crafted indicator can
  never inject syntax into hosts files, filter lists or RPZ zones (property
  tests parse every format back).
- Every file has a SHA-256 in `SHA256SUMS` and a detached minisign signature;
  the key lives only in an Actions secret. `feed pull` refuses to save a
  snapshot whose signature fails.

## Abuse of the verdicts

| Threat | Mitigation |
|---|---|
| Getting a legitimate site blocklisted | Precision-first weights; keywords alone never score; blocklists publish LIKELY+ only; benchmark gate on 522 real domains; dispute form on every entry; allowlist PRs remove a listing on the next run. |
| Poisoned community reports | Reports only add candidates; they never bypass scoring; a maintainer reviews every PR; the bot validates and defangs input that is passed through environment variables, never shell. |
| Fake "PC announced" | PC Watch reads official domains only; automation can only open an issue; a maintainer commit is required to change the status; failures degrade to UNKNOWN, never to a confident answer. |

## Supply chain

Locked dependencies (`uv.lock`, `package-lock.json`) with Dependabot; Actions
pinned by commit SHA with least-privilege `permissions`; CodeQL, OpenSSF
Scorecard and dependency review; PyPI Trusted Publishing (no long-lived
tokens); build-provenance attestations, Sigstore signatures and a CycloneDX
SBOM on releases; `pull_request_target` workflows never check out PR code.

## Out of scope / residual risks

- A determined lure operator can avoid our keywords. Packs and the benchmark
  document known blind spots ([BENCHMARKS.md](BENCHMARKS.md#known-blind-spots)).
- `--live` reveals the scanner's IP address to the target. Use it from a
  network you are comfortable exposing, or stay offline.
- Third-party sources can be wrong; corroboration rules limit the impact.
