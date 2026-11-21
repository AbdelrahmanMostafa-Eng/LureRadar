"""Synthetic lure generators (seeded, deterministic).

Generated names exist only in memory during a benchmark run; nothing is
resolved or contacted, and none of it is committed. They cover the patterns
seen in launch-lure campaigns: keyword+intent, unreleased-platform claims,
combosquats, typosquats, homoglyph IDNs, keyword stuffing, shared-host
subdomains, and URL-path-only lures, plus two deliberately out-of-scope
"blind spot" families reported separately.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from lureradar.util.domains import to_ascii_host

KEYWORDS = ["gta6", "gta-6", "gtavi", "gta-vi", "grand-theft-auto-6", "grandtheftauto6"]
ACQUISITION = [
    "download", "free", "key", "keys", "crack", "keygen", "torrent", "beta", "leak", "generator",
    "giveaway", "unlock", "claim", "install", "setup", "codes", "early-access", "cd-key",
    "no-survey", "repack", "installer", "activation",
]  # fmt: skip
PLATFORMS = [
    "pc",
    "windows",
    "steam",
    "apk",
    "android",
    "ios",
    "iphone",
    "ps4",
    "xbox-one",
    "switch2",
    "mobile",
]
BRAND_TOKENS = [
    "rockstar",
    "rockstargames",
    "steam",
    "steamcommunity",
    "epicgames",
    "playstation",
    "xbox",
    "take2",
]
LURE_WORDS = [
    "gift",
    "giveaway",
    "support",
    "login",
    "verify",
    "rewards",
    "key",
    "free",
    "promo",
    "claim",
]
OFFICIAL_LABELS = [
    "rockstargames",
    "steampowered",
    "steamcommunity",
    "epicgames",
    "playstation",
    "rockstarnorth",
    "take2games",
]
TLDS = [
    "xyz",
    "top",
    "shop",
    "online",
    "site",
    "com",
    "net",
    "org",
    "io",
    "info",
    "store",
    "live",
    "club",
    "fun",
    "app",
]
SHARED_HOSTS = [
    "github.io",
    "pages.dev",
    "netlify.app",
    "weebly.com",
    "blogspot.com",
    "vercel.app",
    "web.app",
]
NEUTRAL = [
    "files-cdn",
    "dl-mirror",
    "static-host",
    "media-box",
    "cloud-store",
    "fastfiles",
    "getfile",
]
LOOKALIKE = {"o": "0", "l": "1", "e": "3", "a": "4", "s": "5", "m": "rn", "i": "l", "g": "q"}
CYRILLIC = {"a": "а", "e": "е", "o": "о", "p": "р", "c": "с", "y": "у", "x": "х", "i": "і"}


@dataclass(frozen=True)
class Sample:
    value: str
    label: str  # "lure" | "benign"
    pattern: str
    in_scope: bool = True


def _mutate(label: str, rng: random.Random) -> str:
    for _ in range(20):
        op = rng.choice(["sub", "del", "ins", "swap", "look"])
        i = rng.randrange(1, len(label))  # keep the first character
        if op == "sub":
            out = label[:i] + rng.choice("abcdefghijklmnopqrstuvwxyz") + label[i + 1 :]
        elif op == "del":
            out = label[:i] + label[i + 1 :]
        elif op == "ins":
            out = label[:i] + label[i] + label[i:]
        elif op == "swap" and i < len(label) - 1:
            out = label[:i] + label[i + 1] + label[i] + label[i + 2 :]
        else:
            ch = label[i]
            out = label[:i] + LOOKALIKE.get(ch, ch) + label[i + 1 :]
        if out != label:
            return out
    return label + "s"


def _homoglyph(label: str, rng: random.Random) -> str:
    positions = [i for i, ch in enumerate(label) if ch in CYRILLIC]
    chosen = (
        set(rng.sample(positions, k=min(len(positions), rng.choice([1, 2]))))
        if positions
        else set()
    )
    return "".join(CYRILLIC[ch] if i in chosen else ch for i, ch in enumerate(label))


def lure_domains(n_per_pattern: int = 120, seed: int = 2026) -> list[Sample]:
    rng = random.Random(seed)
    out: list[Sample] = []

    def add(value: str, pattern: str, in_scope: bool = True) -> None:
        out.append(Sample(value=value, label="lure", pattern=pattern, in_scope=in_scope))

    for _ in range(n_per_pattern):
        kw, tld = rng.choice(KEYWORDS), rng.choice(TLDS)
        a, b = rng.sample(ACQUISITION, 2)
        shape = rng.choice([f"{kw}-{a}", f"{kw}-{a}-{b}", f"{a}-{kw}-{b}", f"{a}-{kw}"])
        add(f"{shape}.{tld}", "keyword_intent")

        plat, acq = rng.choice(PLATFORMS), rng.choice(ACQUISITION)
        shape = rng.choice([f"{kw}-{plat}-{acq}", f"{acq}-{kw}-{plat}", f"{kw}-{acq}-{plat}"])
        add(f"{shape}.{rng.choice(TLDS)}", "unreleased_platform")

        brand, word = rng.choice(BRAND_TOKENS), rng.choice(LURE_WORDS)
        shape = rng.choice([f"{brand}-{kw}-{word}", f"{brand}-{word}-{kw}", f"{kw}-{brand}-{word}"])
        add(f"{shape}.{rng.choice(TLDS)}", "combosquat_campaign")

        brand, word = rng.choice(BRAND_TOKENS), rng.choice(LURE_WORDS)
        add(f"{brand}-{word}.{rng.choice(TLDS)}", "combosquat_brand_only")

        official = rng.choice(OFFICIAL_LABELS)
        add(
            f"{_mutate(official, rng)}.{rng.choice(['com', 'net', 'org', 'co', 'xyz'])}",
            "typosquat",
        )

        target = rng.choice([*OFFICIAL_LABELS, "gta6-free-download", "gtavi-pc-download"])
        add(
            to_ascii_host(f"{_homoglyph(target, rng)}.{rng.choice(['com', 'net', 'xyz'])}"),
            "homoglyph_idn",
        )

        parts = [
            rng.choice(["free", "get", "best"]),
            kw.replace("-", ""),
            rng.choice(PLATFORMS).replace("-", ""),
            rng.choice(["download", "keygen", "crack", "key", "setup"]),
        ]
        add(f"{''.join(parts)}.{rng.choice(TLDS)}", "keyword_stuffing")

        sub = f"{kw}-{rng.choice(PLATFORMS)}-{rng.choice(ACQUISITION)}"
        add(f"{sub}-{rng.randrange(10, 99)}.{rng.choice(SHARED_HOSTS)}", "shared_host_subdomain")

        host = f"{rng.choice(NEUTRAL)}-{rng.randrange(100, 9999)}.{rng.choice(TLDS)}"
        add(
            f"https://{host}/{kw}/{rng.choice(PLATFORMS)}-{rng.choice(ACQUISITION)}/setup.exe",
            "url_path_only",
        )

        add(f"{rng.choice(['free', 'best', 'top'])}-games-{rng.choice(['download', 'crack', 'keys'])}-{rng.randrange(1, 99)}.{rng.choice(TLDS)}",
            "blind_spot_no_campaign_keyword", in_scope=False)  # fmt: skip
        add(f"{rng.choice(['leonida', 'vice-city', 'lucia-jason'])}-{rng.choice(PLATFORMS)}-{rng.choice(ACQUISITION)}.{rng.choice(TLDS)}",
            "blind_spot_unlisted_keyword", in_scope=False)  # fmt: skip
    # de-duplicate while keeping order
    seen: set[str] = set()
    unique = []
    for s in out:
        if s.value not in seen:
            seen.add(s.value)
            unique.append(s)
    return unique
