# LureRadar browser extension (Manifest V3)

Warns you **before** a page loads if its domain is in the LureRadar feed of
LIKELY and CONFIRMED launch lures (optionally SUSPICIOUS too).

**Privacy:** the extension downloads the public feed (`feeds/latest.json`)
every 6 hours. The sites you visit are checked **on your device** and never
sent anywhere. No analytics, no remote code.

## Install (developer mode, until store listings exist)

- Chrome / Edge / Brave: `chrome://extensions` → enable *Developer mode* →
  *Load unpacked* → select this `extension/` folder.
- Firefox (121+): `about:debugging#/runtime/this-firefox` → *Load Temporary
  Add-on* → select `manifest.json`.

## How it works

| File | Role |
|---|---|
| `src/background.js` | Fetches the feed, builds a local index, checks top-level navigations |
| `src/match.js` | Pure matching helpers (host and parent-domain lookup, defanging) |
| `src/warning.html` | Block page: defanged URL, tier, reasons, "go back", "continue once", dispute link |
| `src/options.html` | Enable/disable, include SUSPICIOUS, update now |
| `src/config.js` | Generated from `src/lureradar/config.py` by `scripts/sync_extension.py` |

Permissions: `storage` (the local index), `alarms` (refresh), `webNavigation`
(see top-level navigations), and host access to the LureRadar site only (to
download the feed).

## Develop

```bash
cd extension && npm test
```

```bash
uv run python scripts/sync_extension.py
```

Store listings are on the [roadmap](../ROADMAP.md).
