## What and why

<!-- One or two sentences. Link the issue (Fixes #...). -->

## Type

- [ ] Detection / scoring change (ran `make bench`, updated docs/SIGNALS.md if weights changed)
- [ ] Campaign pack / allowlist / facts (sources and dates included)
- [ ] Pipeline, feeds or exporters
- [ ] Website or docs
- [ ] Tooling / CI

## Checklist

- [ ] `make check` passes locally
- [ ] No real malicious URLs, samples or personal data (fixtures use `*.test` / `example.com`)
- [ ] Every URL shown to users is defanged
- [ ] New claims in docs are dated and sourced (facts.yaml for anything about a launch)
