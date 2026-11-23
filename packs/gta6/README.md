# GTA VI campaign pack

Lures around the Grand Theft Auto VI console launch (2026-11-19, PlayStation 5
and Xbox Series X|S): fake PC/mobile/last-gen downloads, "beta key" and key
generator offers, Steam/Epic/Rockstar impersonation and account phishing.

| File | Contents |
|---|---|
| `pack.yaml` | Pack metadata and file references |
| `keywords.yaml` | Campaign keywords (`gta 6`, `gtavi`, ...), separator-insensitive |
| `intents.yaml` | What lures promise (download, free, key, crack, beta...) |
| `brands.yaml` | Impersonation targets: names and official domains only |
| `allowlist.yaml` | Legitimate outlets (hard clear) and user-content platforms |
| `facts.yaml` | Dated, sourced facts; `platforms` drive `claims_unreleased_platform` |
| `pc_watch.yaml` | PC Watch sources, rules and the verified evidence timeline |

## Keeping it true

- Facts are re-verified before every release; `lureradar pack validate` warns
  when they are older than 120 days.
- The `pc_release` fact is only changed by a maintainer after verifying an
  official announcement (see [docs/PC_WATCH.md](../../docs/PC_WATCH.md)). Doing so
  switches off PC lure claims and allowlists the official PC storefronts.
- Mentions of third-party names are nominative only ([TRADEMARKS.md](../../TRADEMARKS.md)).

```bash
lureradar pack validate packs/gta6
lureradar check "gta6-pc-download[.]example" --pack gta6 --explain
```
