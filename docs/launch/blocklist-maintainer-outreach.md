# Proposing LureRadar to community blocklist projects

Large aggregated lists (for example the hosts and filter-list collections
that Pi-hole, AdGuard and uBlock Origin users rely on) have strict inclusion
criteria. Approach them only after LureRadar has a track record.

## Prerequisites before reaching out

1. At least 30 days of daily published feeds (`feeds-YYYY-MM-DD` releases).
2. A low dispute rate, with every dispute resolved and documented.
3. Signed feeds with the public key published.
4. Stable URLs, `Expires` headers and a clear licence (CC0).

## What to send

- What the list contains (launch-lure domains, LIKELY+ only), update cadence,
  size, and the precision methodology (docs/SIGNALS.md, docs/BENCHMARKS.md).
- Retention policy (30-day stale, 90-day purge) and the dispute SLA.
- Links to the raw files and the verification steps.

## Template

> Hello <maintainers>,
>
> LureRadar publishes a small, precision-first list of domains used as lures
> around hyped game launches (currently GTA VI: fake PC downloads, key
> generators, account phishing). It has been published daily since <date>,
> currently <N> entries (real number from stats.json), CC0-licensed, signed,
> and every entry links to a dispute form. Our methodology and benchmark are
> public. Would you consider it as a source, or could you tell us what you
> would need to see first?

Never claim a size or accuracy figure that is not in the published
`stats.json` / `docs/BENCHMARKS.md` at the time of sending.
