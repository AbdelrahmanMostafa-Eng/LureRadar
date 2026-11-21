# Data sources

Every source adapter implements the same `Source` protocol (see
`src/lureradar/sources/base.py`) and declares its terms URL, whether it needs
a key, and its rate limit. The pipeline keeps running when a source is down,
rate-limited or missing a key.

**Status meanings:** `ok` verified live; `degraded` implemented and tested
against recorded fixtures but not verified live from the build environment;
`requires_key` needs a credential (pipeline skips it without one); `disabled`
off by default.

`lureradar doctor` prints the live status from wherever you run it.

## Build-environment verification (2026-11-21)

The v0.1.0 build sandbox only allowed package registries and GitHub; every
threat-intel host below returned HTTP 403 at the sandbox's egress proxy. The
adapters were therefore built against fixtures that use reserved domains and
**must be verified live** from GitHub Actions (open egress) by running
`lureradar doctor` in the `feed-refresh` workflow. See
[DECISIONS.md](DECISIONS.md#pre-flight-2026-11-21).

The full per-source table (terms, limits, what we redistribute) is maintained
below as adapters land.
