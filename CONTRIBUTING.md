# Contributing to LureRadar

Thanks for helping protect players. Most contributions take minutes and need
no deep knowledge of the code.

## Ways to help (no code needed)

- **Report a lure**: use the [Report a lure](https://github.com/AbdelrahmanMostafa-Eng/LureRadar/issues/new?template=report-a-lure.yml)
  form. A bot validates and defangs it and opens a pull request.
- **Dispute a listing**: [false-positive review](https://github.com/AbdelrahmanMostafa-Eng/LureRadar/issues/new?template=false-positive-review.yml).
- **Improve a pack**: keywords lures use, brands they impersonate, allowlist
  entries, dated facts ([docs/PACKS.md](docs/PACKS.md)).

## Your first pull request in 10 minutes

```bash
git clone https://github.com/AbdelrahmanMostafa-Eng/LureRadar && cd LureRadar
make install
```

```bash
make check
```

`make install` uses [uv](https://docs.astral.sh/uv/) to create `.venv` from
`uv.lock`. `make check` runs everything CI runs: ruff, mypy `--strict`, the
test suite with coverage gates, pack validation, secret scan, the fixture
domain guard, the docs link check and the hostname guard.

A good first change: add an allowlist entry for a legitimate gaming site.

1. Add the registrable domain to `packs/gta6/allowlist.yaml` under `outlets`.
2. Run `make check` and `make bench`.
3. Open a PR explaining why the site is legitimate (who runs it, how long it
   has existed).

More starter ideas live in [docs/launch/good-first-issues.md](docs/launch/good-first-issues.md).

## Ground rules

- **Defensive only.** Read [docs/ETHICS_AND_ABUSE.md](docs/ETHICS_AND_ABUSE.md).
- **No real malicious content in the repo.** Fixtures use reserved names
  (`*.test`, `*.example`, `example.com`); CI fails otherwise.
- **Defang** every URL humans will read (`hxxps://`, `[.]`).
- **Date and source every claim** about a launch (`facts.yaml`).
- **Precision first.** Detection changes must keep `make bench` green (no
  benign domain at LIKELY) and update [docs/SIGNALS.md](docs/SIGNALS.md).
- Conventional Commits (`feat:`, `fix:`, `docs:`, `data(reports):` ...).
- Be kind: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Project layout

| Path | What |
|---|---|
| `src/lureradar/detectors/` | Pure functions returning named signals |
| `src/lureradar/scoring/` | Weights, tiers, explanations, engine |
| `src/lureradar/textlure/` | Message analyzer |
| `src/lureradar/enrich/` | Hardened fetcher, DNS, RDAP, TLS |
| `src/lureradar/sources/` | Source adapters (fixtures-aware) |
| `src/lureradar/pipeline/`, `export/` | Pipeline, state, feeds, signatures |
| `src/lureradar/pcwatch/` | PC Watch |
| `packs/` | Campaign packs |
| `bench/` | Benchmark corpora and harness |
| `web/` | Astro dashboard |
| `tests/` | unit, property, integration, e2e, fixtures |

## Releases

Maintainers tag `vX.Y.Z` on `main`; `release.yml` builds, signs, attests and
publishes. See [GOVERNANCE.md](GOVERNANCE.md).
