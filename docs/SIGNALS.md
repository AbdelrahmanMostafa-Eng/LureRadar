# Signals

Every LureRadar score is the sum of the **named signals** below, clamped to
0-100. Each signal carries an explanation and defanged evidence, and the
verdict card shows them. There is no machine-learned model and no LLM in the
scoring path. Weights are frozen in
[`src/lureradar/scoring/weights.py`](../src/lureradar/scoring/weights.py) and
measured by [`make bench`](BENCHMARKS.md).

## Tiers

| Tier | Score | Published in blocklists? |
|---|---|---|
| CLEAR | < 40 | no |
| SUSPICIOUS | 40-69 | no (dashboard and `all.json` only; opt in with `--min-tier suspicious`) |
| LIKELY | 70-89 | yes |
| CONFIRMED | >= 90, **or** corroborated external reputation | yes |

Overrides, in order: an allowlisted outlet is always CLEAR (hard clear);
corroborated external reputation floors the tier at CONFIRMED; a listing in
the local feed snapshot floors the tier at the listed tier; a user-content
platform URL is capped at SUSPICIOUS unless corroborated.

**Precision guarantees** (enforced by property tests):

- a campaign keyword alone never scores;
- keyword plus intent alone never reaches LIKELY;
- adding a malicious signal never lowers a score or tier.

## Domain and URL signals

| Signal | Weight | Mode | Fires when |
|---|---|---|---|
| `claims_unreleased_platform` | +30 hostname, +15 path | offline | The name offers a download, key or crack ("acquisition" intent, or a self-acquiring term like `apk`) for a platform that the pack's dated facts mark as unreleased, e.g. `gta6-pc-download`. Reads `facts.yaml`: once PC Watch's `pc_release` fact is announced or released, PC claims stop firing. |
| `keyword_intent_combo` | +20 hostname, +10 path | offline | A campaign keyword ("gta 6", "gtavi", separator-insensitive) together with an intent term (download, free, key, crack, beta...). Short intents (`pc`, `key`, `ios`) only count inside fully segmented tokens, so `npc` and `studios` do not match. A brand token is not counted again as an intent. |
| `brand_impersonation` | +25 | offline | Typosquat (OSA edit distance 1-2 scaled by length, or ASCII look-alikes such as `rn`→`m`, `0`→`o`; the first letter must match), combosquat (brand token plus other known words, or a 7+ character brand inside the name), exact brand label on a non-official domain, or the same via Unicode confusables. Official domains never match. |
| `homoglyph_idn` | +20 | offline | An internationalised domain whose Unicode skeleton (TR39-style confusables, NFKC/NFKD) reads as a brand or campaign keyword, e.g. a Cyrillic `о` in `rоckstargames`. |
| `abused_tld` | +8 | offline | The TLD is on the shipped abuse-prone list (`src/lureradar/data/abused_tlds.yaml`, with sources). Never decisive alone. |
| `domain_age` | +20 / +15 / +8 | live | RDAP registration less than 3 / 14 / 30 days ago. |
| `fresh_cert` | +5 | live | First Certificate Transparency sighting, or certificate `notBefore`, less than 48 hours ago. |
| `content_lure_patterns` | up to +25 | live | Page patterns (sum, capped): fake download call to action (+5), survey or "human verification" gate (+10), key-generator UI (+10), scarcity or countdown (+5), installer links such as `.exe`/`.apk` (+10), fake social proof (+5), "disable your antivirus" (+10), unreleased-platform claim in the page text (+10). CTA, scarcity, installers and social proof only count when the page mentions the campaign. |
| `redirect_chain` | +10 | live | More than 2 redirects, or cross-domain hops through a URL shortener. |
| `hosting_reputation` | +8 | live | The hosting ASN is on a *sourced* reputation list. The list ships **empty** in v0.1.0: no entry could be verified. |
| `external_reputation` | +40 | live / pipeline | Flagged by Safe Browsing, URLhaus, OpenPhish or urlscan. **Corroborated** (two sources, or one plus a strong own signal of weight 20+) floors the tier at CONFIRMED. |
| `feed_listed` | 0 (floors tier) | offline | Present in the local feed snapshot (`lureradar feed pull`). |
| `allowlisted` | -40 (hard clear) | offline | The registrable domain is an allowlisted outlet: publisher, store, wiki or official site. |
| `user_content_platform` | 0 (caps at SUSPICIOUS) | offline | YouTube, Reddit, file hosts and similar: the domain is never listed, but the specific URL is still assessed. |
| `established_domain` | -15 | live | Registered more than a year ago and no strong (20+) signal fired. |

"Mode" says what is needed: *offline* signals work with zero network;
*live* signals need `lureradar check --live` or the pipeline.

## Message (text) signals

`lureradar check "<message>"` analyses comments, DMs and ads, and scores every
URL inside the message too. The verdict tier is the higher of the message
score and the worst link.

| Signal | Weight | Fires when |
|---|---|---|
| `text_unreleased_platform` | +30 | The message offers the game on a platform with no release (pack facts), e.g. "GTA 6 PC beta key". |
| `text_free_key_offer` | +20 | Free, early, beta, leaked or giveaway keys, codes, downloads or copies (campaign context required). |
| `text_off_platform_contact` | +15 | Telegram, WhatsApp, Discord invites, "DM me", "link in bio". |
| `text_payment_red_flag` | +20 | Gift cards, crypto, Cash App/Venmo/Zelle, "pay via". |
| `text_urgency_scarcity` | +10 | "Only 20 keys left", "expires tonight", "first 100 people". |
| `text_disable_security` | +25 | "Disable Windows Defender", "it's a false positive", "run as administrator". |
| `text_executable_lure` | +15 | `.exe`/`.apk`/`.msi`/`.dmg` mentions, or password-protected archives. |
| `text_link_shortener` | +10 | A link shortener hides the destination. |
| `text_too_good_to_be_true` | +15 | "100% working", "no survey", "unlimited money", "cracked", "no virus", implausibly low prices for a new release. |
| `text_survey_gate` | +20 | "Complete a survey/offer", "human verification" before access. |
| `text_impersonation_claim` | +15 | "I work at Rockstar", "official Steam giveaway", "Rockstar support", "your Steam account was...". |
| `text_account_threat` | +20 | "Your account is suspended", "verify your login", "unusual activity". |
| `text_risky_link` | +15 | The message links to a URL that itself scores 20 or more. |
| `text_warning_context` | -25 | The message reads as a warning or question ("PSA", "is this real?", "it's a scam", "there is no PC version"). Reassurances such as "no virus" or "not a scam" do **not** count as warnings. |

## Changing a weight

1. Change `weights.py` (and this table).
2. Run `make bench`: it fails if any real benign domain, hard negative or
   benign message reaches LIKELY.
3. Commit the regenerated `docs/BENCHMARKS.md` in the same PR and explain the
   trade-off in the PR description.
