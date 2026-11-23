# Campaign packs

LureRadar is a generic launch-lure engine. Everything specific to one launch
lives in a **campaign pack**: a folder under `packs/` with YAML files. The
GTA VI pack ships with v0.1.0; adding a console, a game or a device takes
about 20 lines.

## Add a launch in 20 lines

```bash
lureradar pack new console-x --name "Console X"
```

```yaml
# packs/console-x/pack.yaml
id: console-x
name: "Console X launch lures"
version: 1
as_of: 2026-11-21
keywords: [console-x, "console x", consolex]
intents: [download, free, key, keygen, crack, apk, pc, beta, early-access, generator, giveaway]
brands:
  - {name: examplecorp, display: "Example Corp", official: [example.com]}
allowlist:
  outlets: [example.org]
  platforms: []
facts:
  as_of: 2026-11-21
  facts:
    - id: pc_release
      claim: "No PC version of Console X games has been announced as of 2026-11-21."
      status: not_announced
      as_of: 2026-11-21
      sources: [{url: "https://example.com/announcement", title: "Official FAQ", accessed: 2026-11-21}]
  platforms:
    pc: {status: unreleased, fact: pc_release, terms: [pc, windows, steam]}
```

```bash
lureradar pack validate packs/console-x
lureradar check "console-x-pc-free-download[.]test" --pack console-x
```

## Reference

`pack.yaml` may inline each section or reference a sibling file
(`keywords: keywords.yaml`). The resolved schema is
[`pack.schema.json`](../src/lureradar/schemas/pack.schema.json).

| Field | Purpose | Rules |
|---|---|---|
| `id` | Folder name and pack id | lowercase, digits, hyphens |
| `name`, `subject` | Display names (`subject` is what launches, e.g. "GTA VI") | |
| `version`, `as_of` | Pack version and review date | `as_of` is a date |
| `keywords` | Names lures use | at least 4 letters/digits each; separator-insensitive matching |
| `intents` | What lures promise | download, free, key, crack, beta, ... |
| `brands` | Impersonation targets: `name`, `display`, `aliases`, `official` domains | names only, never logos |
| `allowlist` | `outlets` (hard clear) and `platforms` (user content, capped at SUSPICIOUS) | registrable domains |
| `facts` | Dated, sourced claims and `platforms` they drive | every fact needs `as_of` and at least one source |
| `pc_watch` | Optional PC Watch config ([PC_WATCH.md](PC_WATCH.md)) | |

### Facts drive rules

A platform with `status: unreleased` makes "download for <platform>" a lure
signal. If the platform references a fact (`fact: pc_release`) and that fact's
status becomes `announced_undated`, `announced_dated` or `released`, the
platform is treated as released automatically. `lureradar pack validate`
warns when facts are older than 120 days so they get re-verified.

### Allowlist entries

Add a domain only with evidence that it is legitimate and long-established.
Wrongly listed sites are removed from the feeds on the next pipeline run after
an allowlist PR merges.

## Quality bar for a new pack

- Facts are dated and sourced from official pages.
- Keywords are specific (no generic words that appear in ordinary names).
- `make bench` still passes (no benign domain reaches LIKELY).
- No logos, art or other third-party assets ([TRADEMARKS.md](../TRADEMARKS.md)).
