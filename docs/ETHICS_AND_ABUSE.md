# Ethics and abuse policy

## Scope: defensive only

LureRadar exists to help people **recognise and block** launch lures: fake
downloads, key generators and phishing around hyped releases. All analysis
is passive. We never execute, install, detonate or interact with lures
beyond one bounded, read-only page fetch in `--live` mode.

## What we refuse

We do not accept features, packs or contributions that:

- help create, test, optimise or disguise lures, phishing pages or scam
  messages (for example "generate lure domains that evade LureRadar");
- evade other security tools or blocklists;
- scan, attack, overload or exploit anyone's systems;
- collect or publish personal data about victims, reporters or site owners;
- scrape sources against their terms or republish restricted third-party data.

The synthetic generators in `bench/` exist only to measure detection. They
run in memory and never register, resolve or contact anything. Proposals to
make them more "realistic" for offensive use will be declined.

## Language and claims

- Verdicts say **detected / likely**, never "scam", unless the tier is
  CONFIRMED and the evidence supports it.
- Every listing is explainable and disputable; every feed says it may
  contain false positives and comes with no warranty.
- Claims about launches (for example "no PC version") are dated, sourced and
  phrased to stay true ("no official PC release has been announced as of
  <date>"). PC Watch never says "will never come to PC".

## Defanging

Indicators are defanged (`hxxps://`, `[.]`) everywhere humans read them: CLI,
dashboard, docs, issues and launch posts. Machine feeds use raw domains
because resolvers need them.

## Takedown help

`lureradar report --abuse <domain>` drafts a report for the registrar or host
(with the RDAP abuse contact when run with `--live`). It is never sent
automatically, and it warns when the verdict is below LIKELY.

## Reporting misuse

If you see LureRadar data or code used to harm people, contact the
maintainers privately through GitHub's private vulnerability reporting.
