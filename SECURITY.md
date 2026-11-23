# Security policy

LureRadar is a defensive security project, so we hold ourselves to the
standard we ask of others.

## Reporting a vulnerability

**Please do not open a public issue for security problems.**

Use GitHub's private vulnerability reporting:
[Report a vulnerability](https://github.com/AbdelrahmanMostafa-Eng/LureRadar/security/advisories/new)
(Security tab → "Report a vulnerability").

Please include: affected version/commit, a description, reproduction steps or
a proof of concept, and the impact you expect. Defang any URLs (`hxxps://`,
`[.]`).

### What we consider in scope

- Bypasses of the hardened fetcher (SSRF, redirect handling, size/time limits,
  binary download prevention) in `src/lureradar/enrich/` and `src/lureradar/util/ssrf.py`.
- Anything that makes `lureradar check` (offline mode) contact the network.
- Feed integrity issues: signature verification bypass, checksum mismatches,
  injection into hosts/ABP/RPZ outputs that could break or subvert a consumer's
  resolver or blocker.
- Cross-site scripting or third-party requests on the website or in the
  browser extension; anything that leaks a user's browsing data.
- Supply-chain issues in our workflows (unpinned actions, excessive
  permissions, secret exposure).

### Out of scope

- False positives or false negatives in detections: please use the
  [false-positive review](https://github.com/AbdelrahmanMostafa-Eng/LureRadar/issues/new?template=false-positive-review.yml)
  or [report a lure](https://github.com/AbdelrahmanMostafa-Eng/LureRadar/issues/new?template=report-a-lure.yml)
  forms instead.
- Reports about third-party sites listed in our feeds (contact their registrar
  or host; `lureradar report --abuse <domain>` drafts the message for you).

## Response targets

| Stage | Target |
|---|---|
| Acknowledgement | 3 business days |
| Initial assessment | 7 days |
| Fix for high/critical issues | 30 days |
| Public advisory | after a fix is released, with credit if you want it |

These are targets for a volunteer project, not contractual guarantees.

## Verifying what you download

- **Releases** are built in GitHub Actions with build-provenance attestations
  and Sigstore signatures. Verify with `scripts/verify_release.sh` (see
  [docs/QUICKSTART.md](docs/QUICKSTART.md#verify-a-release)).
- **Feeds** are signed with an Ed25519 key in minisign format; the public key
  is committed at `keys/lureradar-feed.pub`. Verify with
  `lureradar feed verify` or `minisign -Vm latest.json -p keys/lureradar-feed.pub`
  (see [docs/FEEDS.md](docs/FEEDS.md)).

We do not use PGP. Sigstore (keyless, tied to this repository's workflows)
and minisign cover releases and feeds respectively.

## Supported versions

Only the latest minor release receives security fixes during the 0.x series.
