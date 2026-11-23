# Good first issues (to be opened by a maintainer)

Each item is scoped for a first contribution. Paste the title and body into a
new issue and add the `good first issue` label.

1. **Add 20 legitimate gaming sites to the benchmark benign corpus.** Add
   long-established domains to `bench/corpora/benign_domains.txt` with a
   category comment; run `make bench`.
2. **Hard negatives in other languages.** Add synthetic `.test` fan-site names
   in Spanish/Portuguese to `bench/corpora/benign_hard_negatives.txt`.
3. **German and French text-lure patterns.** Extend `textlure/patterns.py`
   for "kostenlos", "gratuit"... with tests in `tests/fixtures/text/messages.yaml`.
4. **`lureradar check --file urls.txt`.** Batch mode with one verdict per line
   and a summary; reuse `Engine`.
5. **Dark/light preview for the report card.** Add a `--light` option to
   `lureradar report` using the light-theme tokens.
6. **Unbound docs: verify signatures in a cron script.** Extend
   `examples/unbound-rpz.md` with a minisign-verifying fetch script.
7. **More shared hosts.** Add site builders missing from the PSL to
   `src/lureradar/data/shared_hosts.yaml` with a test.
8. **Explain mode for text verdicts.** Show which words matched each text
   signal in `--explain`.
9. **`feed diff` Markdown output.** Add `--markdown` for release notes.
10. **Pack lint: overlapping keywords.** Warn when a keyword is a substring of
    an allowlisted outlet's label (`packs/validator.py`).
