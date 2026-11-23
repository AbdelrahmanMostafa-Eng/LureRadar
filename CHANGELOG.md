# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-11-23

First public release.

### Added

- `lureradar check` for URLs, domains (defanged input accepted) and messages:
  verdict card, versioned `--json`, `--explain`, `--live`, CI-friendly exit codes.
- Explainable detection engine: 15 domain/URL signals and 14 message signals,
  frozen weights, tiers, corroboration rules; no machine learning or LLM.
- GTA VI campaign pack with dated, sourced facts; pack validator and scaffold.
- Hardened fetcher (SSRF guard, redirect re-validation, size and time limits,
  text-only), DNS/RDAP/TLS enrichment, `lureradar doctor`.
- Source adapters: crt.sh, CertStream (watch), OpenPhish, URLhaus, Google Safe
  Browsing, urlscan.io, community reports.
- Pipeline with SQLite state and retention; feeds in JSON, hosts, domains,
  AdGuard/uBlock, RPZ, CSV and STIX 2.1, with SHA256SUMS and minisign-format
  signatures; `feed build|diff|verify|pull|keygen`, `export`.
- PC Watch: official-sources-only tracker with status enum, staleness guard,
  human-in-the-loop review issues, JSON/Atom/badge outputs.
- Benchmark (`make bench`): 522 real benign domains, hard negatives, synthetic
  lures and messages; 0% false positives at LIKELY+ on the benign corpus.
- `lureradar report` daily stats card and abuse-report drafts.
- Static dashboard with a client-side link checker, feeds page and PC Watch page.
- Supply chain: SHA-pinned actions, CodeQL, Scorecard, dependency review,
  Trusted Publishing, provenance attestations, Sigstore, CycloneDX SBOM.

[Unreleased]: https://github.com/AbdelrahmanMostafa-Eng/LureRadar/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/AbdelrahmanMostafa-Eng/LureRadar/releases/tag/v0.1.0
