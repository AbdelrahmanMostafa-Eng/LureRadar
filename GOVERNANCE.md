# Governance

## Roles

- **Maintainers** merge pull requests, tag releases, approve changes to
  detection weights, packs, facts and allowlists, and hold the feed signing
  key. Current maintainer: [@AbdelrahmanMostafa-Eng](https://github.com/AbdelrahmanMostafa-Eng).
- **Contributors** propose changes through issues and pull requests.

## Decisions

- Day-to-day changes: one maintainer review.
- Detection weights, tier thresholds, PC Watch status (`facts.yaml`) and
  allowlist removals: a maintainer review plus a passing `make bench`; the
  rationale goes in the PR and, for lasting choices, in `docs/DECISIONS.md`.
- Anything touching scope or ethics follows `docs/ETHICS_AND_ABUSE.md`.

## Service targets (best effort)

| Item | Target |
|---|---|
| False-positive disputes | triage within 2 business days |
| Community lure reports | review within 7 days |
| Security reports | see [SECURITY.md](SECURITY.md) |
| PC Watch review issues | within 24 hours when an official announcement is suspected |

## Becoming a maintainer

Sustained, high-quality contributions (especially reviews and disputes
handled carefully) lead to an invitation. Maintainers who are inactive for
six months move to emeritus status.

## Funding

The project accepts no sponsorship yet. If that changes, funding sources will
be listed in the README and never influence what gets listed.
