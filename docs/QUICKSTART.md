# Quickstart

## Check a link, a domain or a message (no setup, no network)

```bash
uvx lureradar check "https://rockstar-gta6-pc-download[.]test/free-key"
```

`uvx` runs LureRadar in a throwaway environment ([install uv](https://docs.astral.sh/uv/getting-started/installation/)).
Prefer a permanent install:

```bash
pipx install lureradar
```

```bash
docker run --rm --read-only ghcr.io/abdelrahmanmostafa-eng/lureradar check "gta6-pc-download[.]example"
```

Defanged input (`hxxps://`, `[.]`) is accepted everywhere. Paste a whole
message to analyse it:

```bash
lureradar check "Free GTA 6 PC beta key!! DM me on Telegram, only 20 keys left"
```

Useful flags:

| Flag | What it does |
|---|---|
| `--json` | Stable, versioned JSON ([SCHEMA.md](SCHEMA.md)) |
| `--explain` | Show evidence for every signal |
| `--live` | Add DNS, RDAP, TLS and a hardened page fetch (contacts the target; see [PRIVACY.md](PRIVACY.md)) |
| `--pack gta6` | Restrict to one campaign pack |
| `-` as target | Read the target or message from stdin |

Exit codes make it script-friendly: `0` clear, `10` suspicious, `20` likely,
`30` confirmed, `1` error.

```bash
lureradar check "$URL" >/dev/null; [ $? -ge 20 ] && echo "blocked: likely lure"
```

## Use the public feed offline

```bash
lureradar feed pull
```

Downloads and verifies `latest.json`; `check` then also consults it.

## Block lures on your network

See [FEEDS.md](FEEDS.md) and the copy-paste guides for
[Pi-hole](../examples/pihole.md), [AdGuard](../examples/adguard.md),
[uBlock Origin](../examples/ublock.md) and [Unbound RPZ](../examples/unbound-rpz.md).

## Self-host a Certificate Transparency watcher

```bash
docker compose up -d
```

`docker-compose.yml` runs `lureradar watch` (read-only filesystem, non-root,
no capabilities): it consumes a CertStream-compatible stream, prints JSON-line
alerts and re-publishes feeds hourly into a volume. Without Docker:

```bash
pipx install 'lureradar[watch]'
```

```bash
lureradar watch --feeds-out ./feeds --alert-tier likely
```

## Browser extension

Load `extension/` unpacked in Chrome, Edge, Brave or Firefox (see
[extension/README.md](../extension/README.md)). It checks sites locally
against the public feed and warns before a listed site loads.

## Is GTA 6 coming to PC?

```bash
lureradar pcwatch status
```

See [PC_WATCH.md](PC_WATCH.md).

## Run the pipeline yourself

```bash
git clone https://github.com/AbdelrahmanMostafa-Eng/LureRadar && cd LureRadar
make install
make scan-fixtures
```

`make scan-fixtures` runs the full pipeline offline on recorded fixtures
(reserved `.test` domains) and writes every feed format to `build/site/feeds`.
For live sources, drop `--fixtures` and set the optional keys from
`.env.example`.

## Verify a release

Every release is built in GitHub Actions with a build-provenance attestation,
a Sigstore signature and a CycloneDX SBOM.

```bash
gh release download v0.1.0 --repo AbdelrahmanMostafa-Eng/LureRadar
```

```bash
scripts/verify_release.sh lureradar-0.1.0-py3-none-any.whl SHA256SUMS
```

The script checks the GitHub attestation (`gh attestation verify`), the
Sigstore bundle (`python -m sigstore verify github`) and the SHA-256, and
reports any check it could not run. LureRadar never asks you to pipe a script
into a shell.
