# Newsletter pitch (tl;dr sec, Risky Business, Hacker Newsletter style)

**Subject:** Open-source, explainable detection of launch-day game scams (GTA 6)

Hi <name>,

LureRadar is a new MIT-licensed project that detects the scam wave around
hyped launches, starting with GTA 6 (console-only at launch, so every
"PC download" is a lure). Why it may interest your readers:

- **Explainable by construction**: no ML/LLM; every score is a sum of named
  signals with evidence (unreleased-platform claims driven by dated facts,
  brand typosquat/combosquat, Unicode confusables, RDAP age, page patterns).
- **Engineering details**: an SSRF-hardened fetcher (IP pinning against DNS
  rebinding, redirect re-validation, 1 MB/10 s caps, text-only), feeds
  signed in minisign format and verified against an independent
  implementation, SHA-pinned workflows and Sigstore/provenance on releases.
- **Honest benchmark**: 0 false positives on 522 real benign domains at the
  blocklist threshold, with offline recall reported as it is (low by
  design) and blind spots listed. `make bench` reproduces it.
- **PC Watch**: an official-sources-only "Is GTA 6 coming to PC?" tracker
  with a human in the loop, a good pattern for any fact a detector depends on.

Repo: https://github.com/AbdelrahmanMostafa-Eng/LureRadar
One-liner: Open threat radar for hyped-launch scams: fake downloads, key-gen
traps and phishing, starting with GTA 6.

Thanks!
