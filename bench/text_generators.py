"""Synthetic message generators for the text-lure benchmark (seeded).

These are written for evaluation only and deliberately differ from the
hand-written unit-test corpus in tests/fixtures/text/messages.yaml.
"""

from __future__ import annotations

import random

from bench.generators import Sample

KW = ["GTA 6", "GTA VI", "gta6", "Grand Theft Auto VI", "GTA6"]
UNRELEASED = ["PC", "Windows", "Steam", "Android", "iOS", "iPhone", "PS4", "Switch 2"]
RELEASED = ["PS5", "Xbox Series X", "Xbox Series S"]
OFFER = [
    "free beta key",
    "early access key",
    "free download",
    "cracked copy",
    "free activation code",
    "beta invite",
]
CONTACT = [
    "DM me on Telegram",
    "message me on WhatsApp",
    "add me on discord",
    "link in bio",
    "join our Telegram channel",
]
URGENCY = [
    "only 30 keys left",
    "hurry, offer ends tonight",
    "first 100 people only",
    "limited time",
]
PAY = ["pay with a Steam gift card", "BTC only", "send USDT", "Amazon gift cards accepted"]
EXTRA = ["no survey", "100% working", "no virus", "works on all devices", "undetected"]
URLS = [
    "bit.ly/example-{n}",
    "gta6-{p}-download-{n}.test",
    "tinyurl.com/example-{n}",
    "free-gta6-keys-{n}.test/claim",
]
BENIGN_T = [
    "Just finished the {kw} story on {rp}, what a ride",
    "Is the {kw} {up} download real? No, it's a scam, there is no {up} version yet",
    "Anyone know when {kw} comes to {up}? Rockstar hasn't said anything",
    "PSA: ignore anyone offering {kw} {up} keys, they're fake",
    "{kw} runs great on {rp}, the lighting is unreal",
    "Pre-loaded {kw} on {rp} last night, can't wait",
    "Best {kw} cars so far? I love the new muscle cars",
    "My {kw} photo mode shots from Leonida, thoughts?",
    "Waiting for the {kw} {up} port before I buy, my console is broken",
    "Beware: fake {kw} {up} download sites are spreading malware",
    "Does {kw} support 120Hz on {rp}?",
    "Reviews for {kw} are in, mostly positive",
    "Got {kw} as a gift, playing on {rp} tonight with friends",
    "There's no official {kw} {up} release, report those ads",
    "The {kw} soundtrack is amazing, which station is your favourite?",
]


def messages(n: int = 300, seed: int = 2026) -> list[Sample]:
    rng = random.Random(seed)
    out: list[Sample] = []
    for i in range(n):
        kw, up = rng.choice(KW), rng.choice(UNRELEASED)
        parts = [f"{rng.choice(OFFER).capitalize()} for {kw} {up}"]
        for pool in (CONTACT, URGENCY, PAY, EXTRA):
            if rng.random() < 0.5:
                parts.append(rng.choice(pool))
        if rng.random() < 0.6:
            parts.append(rng.choice(URLS).format(n=i, p=up.lower().replace(" ", "")))
        rng.shuffle(parts[1:])
        out.append(Sample(value=", ".join(parts), label="lure", pattern="text_lure"))
    for i in range(n):
        tpl = rng.choice(BENIGN_T)
        text = tpl.format(kw=rng.choice(KW), up=rng.choice(UNRELEASED), rp=rng.choice(RELEASED))
        out.append(Sample(value=f"{text} #{i}", label="benign", pattern="text_benign"))
    return out
