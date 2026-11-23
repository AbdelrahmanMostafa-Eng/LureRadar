# example-launch (template)

A **fictional** campaign pack showing every feature in a single `pack.yaml`:
keywords, intents, a brand with aliases and official domains, an allowlist
with an outlet and a user-content platform, and a dated fact that drives an
unreleased platform. All names and domains are invented or reserved.

`template: true` keeps it out of default checks. Try it explicitly:

```bash
lureradar check "nimbus-quest-2-pc-download[.]test" --pack example-launch
```

To start a real pack, prefer `lureradar pack new <id>` (see docs/PACKS.md).
