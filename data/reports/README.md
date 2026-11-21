# Community lure reports

Each file here is one **validated, defanged** lure report, added by a pull
request that the `community-report` workflow opens from the
[Report a lure](https://github.com/AbdelrahmanMostafa-Eng/LureRadar/issues/new?template=report-a-lure.yml)
issue form. A maintainer reviews and merges it; the next pipeline run scores
the indicator like any other candidate.

**A report never bypasses scoring.** It only adds a candidate. Whether it is
published depends on LureRadar's signals and tiers (LIKELY+ by default).

Format (`data/reports/<yyyy-mm-dd>-<short-id>.yaml`), validated by
`src/lureradar/sources/community_reports.py`:

```yaml
indicator: "hxxps://gta6-pc-download[.]example/free-key"   # must be defanged
reported: 2026-11-21
pack: gta6
where_seen: "YouTube comment"        # optional, <= 200 chars
notes: "Promised a PC beta key"      # optional, <= 500 chars
```

Reports are dedicated to the public domain (CC0), as stated in the issue form.
Never include personal data about victims or reporters.
