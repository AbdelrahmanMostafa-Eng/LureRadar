# Reddit drafts

> Read each subreddit's rules before posting; several forbid self-promotion
> except on specific days or require flair. Post from an account with history
> in the community, answer comments, and never post more than one subreddit
> per day. Defang every example link.

## r/netsec (only if it fits the link-post rules; otherwise r/cybersecurity)

**Title:** LureRadar: explainable detection of launch-day game lures (CT + feeds → signed blocklists), open source

Body: link to the repository. First comment: methodology summary (named
signals, no ML), the hardened fetcher's SSRF design, benchmark numbers from
docs/BENCHMARKS.md including blind spots, and a request for adversarial
false-positive tests.

## r/pihole

**Title:** Free blocklist for fake GTA 6 download / key-generator sites (hosts + domains format, daily)

Body:

> GTA 6 is console-only for now (dated facts in the repo), so "GTA 6 PC
> download" sites are lures. LureRadar publishes a daily list of likely and
> confirmed lure domains, precision-first (0 false positives on a 522-domain
> benign benchmark). Add to Adlists:
> `https://abdelrahmanmostafa-eng.github.io/LureRadar/feeds/hosts.txt`
> Every entry has a dispute link; signatures and checksums are published.

## r/uBlockOrigin

**Title:** Filter list for launch-day game scam domains (AdGuard/ABP syntax)

Body: subscribe URL for `feeds/adguard.txt`, the `abp:subscribe` link, what
gets listed (LIKELY+ only), update cadence (daily, best-effort) and the
dispute path.

## r/GTA6 (check the self-promotion rule first; ask mods if unsure)

**Title:** PSA: there is no official GTA 6 PC version yet. Free tool to check any "PC download" link

Body:

> As of the date in our sources file, Rockstar has not announced a PC
> version. Every "GTA 6 PC download", "beta key" or "Steam key" offer is a
> scam. Paste any link or DM into the checker (runs in your browser, sends
> nothing anywhere): <site>/check/. Want to know the moment PC is announced
> officially? PC Watch has an RSS feed: <site>/pc-watch/.

## r/cybersecurity

Short version of the Show HN comment, focused on the threat (seasonal lure
campaigns around hyped launches) and how to consume the STIX/CSV feeds.
