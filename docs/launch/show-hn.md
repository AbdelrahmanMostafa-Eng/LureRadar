# Show HN draft

> Post after v0.1.0 is tagged, the site is live and the first scheduled feed
> run has published real feeds. Replace nothing with invented numbers: every
> figure below comes from `make bench` (docs/BENCHMARKS.md).

## Title options

1. Show HN: LureRadar – explainable detection of fake "GTA 6 PC download" sites
2. Show HN: An open blocklist and checker for launch-day game scams
3. Show HN: LureRadar – see the lure before you bite (Pi-hole/uBlock lists, offline CLI)

## URL

https://github.com/AbdelrahmanMostafa-Eng/LureRadar

## First comment

Hi HN. GTA VI launched on 19 November on PS5 and Xbox Series X|S only. As of
the date in our facts file, Rockstar has not announced a PC version, yet
"GTA 6 PC download", "free beta key" and "Steam key generator" lures are
everywhere: search ads, YouTube comments, Discord DMs.

LureRadar is a small, defensive, open-source project that:

- checks a link, domain or message offline in one command
  (`uvx lureradar check "hxxps://rockstar-gta6-pc-download[.]test/free-key"`)
  and explains every point of the score;
- runs a daily pipeline on GitHub Actions (Certificate Transparency + public
  feeds → enrichment → scoring) and publishes free blocklists for Pi-hole,
  AdGuard, uBlock Origin, RPZ, plus STIX/CSV/JSON, all signed;
- tracks "Is GTA 6 coming to PC?" from official sources only, with a
  maintainer in the loop before the status can change.

Design choices you may want to poke at:

- No ML or LLM in the scoring path. Every verdict is a sum of named signals
  with evidence, so every false positive is debuggable and fixable with one
  allowlist line.
- Precision first: keyword matches alone never score. On 522 hand-curated
  real benign domains the benchmark has 0 false positives at LIKELY+ (also
  with allowlists switched off). Offline recall on our synthetic lures is
  deliberately low (6.9% LIKELY+, 48.6% SUSPICIOUS+); live signals do the
  rest. The benchmark is reproducible with `make bench`, and it documents its
  blind spots.
- The hardened fetcher pins vetted IPs (DNS-rebinding safe), re-checks every
  redirect, caps at 1 MB of text and refuses binaries before reading a byte.

Feedback I would love: false positives you can trigger, blind spots, and
blocklist maintainers' requirements for inclusion.
