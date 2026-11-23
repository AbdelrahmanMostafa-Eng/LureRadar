# Privacy

LureRadar collects nothing about you. There is no telemetry anywhere: not in
the CLI, the website, the feeds or the browser extension.

## CLI

- `lureradar check` is **offline by default**: it opens no network
  connection (enforced by a test that fails if a socket is opened).
- `lureradar check --live` contacts, and says so before it starts:
  - your DNS resolver, to look up the target;
  - the target itself (one TLS handshake and one bounded HTTP fetch);
  - the RDAP service for the target's TLD (via the IANA bootstrap or rdap.org);
  - **only** the reputation services you configured with a key (Safe Browsing,
    URLhaus, urlscan.io). Those services receive the URL or host you check.
  The verdict lists every service contacted.
- `lureradar feed pull` downloads the public feed from the project site.
- `lureradar doctor` probes each data source's public endpoint.

## Website

Static pages on GitHub Pages. No cookies, no analytics, no trackers, no
third-party requests (fonts are self-hosted). The **link checker runs entirely
in your browser** and sends nothing anywhere. GitHub Pages itself may keep
standard server logs ([GitHub's privacy statement](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement)).

## Browser extension

The extension downloads the public blocklist and checks the sites you visit
**locally**. No browsing data leaves your device. See `extension/README.md`.

## Feeds and reports

- Feeds contain domains and LureRadar's own scores, never personal data.
- Community reports are public GitHub issues. Do not include personal data;
  the issue form asks you to confirm this.
- PC Watch has no accounts and no email list. Subscribe with RSS/Atom or your
  own webhook ([example](../examples/pc-watch-webhook.md)).

## Crawling

The pipeline identifies itself as `LureRadar/<version> (+<site>/bot/)`. The
`/bot/` page explains how to request exclusion.
