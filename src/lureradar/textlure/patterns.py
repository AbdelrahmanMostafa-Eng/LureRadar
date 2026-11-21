"""Lure-language patterns shared by the text analyzer and the page-content detector.

All patterns are case-insensitive and deliberately conservative. Each match is
returned as a short snippet so verdicts can show *why* something matched.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_F = re.IGNORECASE


def _rx(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, _F)


FREE_OFFER = _rx(
    r"\b(?:free|early|beta|exclusive|giveaway|unlocked|leaked)\W+(?:[\w'-]+\W+){0,4}?"
    r"(?:keys?|codes?|access|downloads?|cop(?:y|ies)|invites?|accounts?|version|builds?|money|cash"
    r"|shark\s?cards?|games?|apk|ipa)\b"
    r"|\b(?:keys?|codes?|downloads?|cop(?:y|ies))\W+(?:\w+\W+){0,2}?(?:for\s+)?free\b"
)
OFF_PLATFORM = _rx(
    r"\b(?:telegram|whats\s?app|signal\s+app|kik|snapchat|wechat|viber)\b"
    r"|\bt\.me/|\bdiscord\.gg/|\bwa\.me/"
    r"|\b(?:dm|pm|message|inbox|text|whisper)\s+me\b|\bdm\s+(?:for|to)\b|\bhmu\b"
    r"|\badd\s+me\s+(?:on|at)\s+(?:telegram|whats\s?app|discord|snap(?:chat)?|kik|insta(?:gram)?|signal)\b"
    r"|\bcontact\s+me\b|\blink\s+in\s+(?:my\s+)?bio\b|\bcheck\s+(?:my\s+)?(?:bio|profile)\b"
    r"|\bjoin\s+(?:my|our)\s+(?:telegram|discord|channel|server|group)\b"
)
PAYMENT = _rx(
    r"\bgift\s?cards?\b|\b(?:steam|google\s+play|itunes|apple|amazon|psn|xbox)\s+(?:gift\s+)?cards?\b"
    r"|\b(?:bitcoin|btc|crypto|usdt|tether|ethereum|litecoin|monero|xmr)\b"
    r"|\b(?:cash\s?app|venmo|zelle|western\s+union|moneygram)\b"
    r"|\bpaypal\s+(?:friends|f&f)\b|\bpay(?:ment)?\s+(?:via|with|in)\s+(?:crypto|gift|btc|usdt)\b"
)
URGENCY = _rx(
    r"\b(?:hurry(?:\s+up)?|act\s+(?:fast|now|quick(?:ly)?)|limited\s+(?:time|offer|slots|spots|keys|codes)"
    r"|only\s+\d+\s+(?:keys?|codes?|slots?|spots?|copies|left|remaining)"
    r"|(?:keys?|slots?|spots?|codes?|copies)\s+(?:left|remaining)"
    r"|expires?\s+(?:today|tonight|soon|in\s+\d+)|last\s+chance|before\s+(?:it'?s|they'?re)\s+gone"
    r"|first\s+\d+\s+(?:people|users|players)|ends\s+(?:today|tonight|soon)|while\s+(?:stocks?|supplies)\s+last"
    r"|before\s+(?:midnight|tonight|they\s+run\s+out)|grab\s+it\s+(?:now|before|while)"
    r"|\d+\s+(?:[\w-]+\s+){0,5}?(?:invites?|keys?|codes?|slots?|spots?|copies)\s+left)\b"
)
DISABLE_SECURITY = _rx(
    r"\b(?:disable|turn\s+off|deactivate|pause|uninstall|switch\s+off)\s+(?:your\s+|the\s+)?"
    r"(?:anti-?virus|av|windows\s+defender|defender|smart\s?screen|firewall|real-?time\s+protection|security)\b"
    r"|\b(?:it'?s\s+a\s+)?false\s+positive\b|\bwhitelist\s+(?:the|this)\s+(?:file|exe|app)\b"
    r"|\brun\s+(?:it\s+|the\s+\w+\s+)?as\s+admin(?:istrator)?\b|\bignore\s+(?:the\s+)?(?:warning|virus|defender)\b"
)
EXECUTABLE = _rx(r"\b[\w.-]+\.(?:exe|msi|scr|bat|cmd|apk|ipa|dmg|pkg|jar|vbs|ps1|lnk|iso)\b")
ARCHIVE_PASSWORD = _rx(
    r"\b(?:zip|rar|7z|archive)\b.{0,40}\bpass(?:word)?\s*[:=]?\s*\S+"
    r"|\bpass(?:word)?\s+(?:for|of|to)\s+(?:the\s+)?(?:zip|rar|7z|archive|file)\b"
)
TOO_GOOD = _rx(
    r"\b(?:100%\s+(?:working|free|legit|safe|real)|no\s+survey|no\s+(?:human\s+)?verification"
    r"|unlimited\s+(?:money|cash|gems|coins)|money\s+(?:glitch|generator|hack)|mod\s?menu"
    r"|free\s+(?:money|cash|shark\s?cards?)|undetected|instant(?:ly)?\s+(?:download|delivery|access)"
    r"|full\s+(?:game|version)\s+(?:for\s+)?free|cracked|no\s+virus|virus[-\s]free|not\s+a\s+scam"
    r"|totally\s+legit|works\s+on\s+(?:pc|android|ios|iphone|all\s+(?:phones|devices))"
    r"|no\s+(?:jailbreak|root)(?:\s+needed|\s+required)?|(?:key|code|money)\s+generator"
    r"|works?\s+100\s?%|free\s+(?:[\w-]+\s+){0,7}?full\s+(?:game|version))(?!\w)"
)
CHEAP_PRICE = _rx(
    r"(?:\$|usd\s?|€|£)\s?[0-9](?:[.,]\d{1,2})?(?!\d)|\b[0-9](?:[.,]\d{1,2})?\s?(?:\$|usd|dollars?|€|eur|£)"
)
SURVEY = _rx(
    r"\b(?:complete|finish|fill(?:\s+out)?)\s+(?:a\s+|one\s+|the\s+|two\s+|\d\s+)?(?:short\s+|quick\s+)?"
    r"(?:surveys?|offers?|tasks?)\b|\bhuman\s+verification\b"
    r"|\bverify\s+(?:that\s+)?(?:you'?re|you\s+are)\s+(?:a\s+)?(?:human|not\s+a\s+(?:robot|bot))\b"
    r"|\bcontent\s+locker\b|\bunlock\s+(?:the\s+)?download\b"
)
ACCOUNT_THREAT = _rx(
    r"\baccount\s+(?:has\s+been\s+|is\s+|will\s+be\s+)?(?:suspended|locked|banned|disabled|terminated|flagged)\b"
    r"|\bverify\s+your\s+(?:account|identity|login)\b|\bunusual\s+(?:sign-?in|login|activity)\b"
    r"|\blog\s?in\s+(?:to|now\s+to)\s+(?:confirm|avoid|keep|restore)\b"
)
KEYGEN_UI = _rx(
    r"\bgenerate\s+(?:your\s+)?(?:key|code|serial)s?\b|\bkey\s?-?gen(?:erator)?\b"
    r"|\b(?:activation|serial|cd)\s+(?:key|code)\s+generator\b|\bcode\s+generator\b"
)
DOWNLOAD_CTA = _rx(
    r"\b(?:download\s+(?:now|free|here|for\s+free|the\s+(?:game|setup|installer))|instant\s+download"
    r"|get\s+(?:it|the\s+game|your\s+(?:key|copy|code))\s+now|claim\s+(?:your\s+)?(?:key|code|copy)"
    r"|start\s+download|download\s+(?:gta|game))\b"
)
SOCIAL_PROOF = _rx(
    r"\b\d[\d,.]*k?\+?\s+(?:downloads?|users|players|people|gamers)\s+(?:today|online|downloaded|"
    r"already|this\s+week|joined)\b|\b(?:users|people|players)\s+(?:are\s+)?online\s+now\b"
    r"|\brated\s+\d(?:\.\d)?\s*/\s*5\s+by\b|\b\d[\d,]*\s+(?:keys|codes)\s+(?:claimed|generated|redeemed)\b"
)
COUNTDOWN = re.compile(r"\b\d{1,2}:\d{2}:\d{2}\b")
WARNING = _rx(
    r"\b(?:scams?|fakes?|phishing|malware|viruse?s?|trojan|beware|warning|psa|stolen\s+accounts?"
    r"|don'?t\s+(?:click|download|fall\s+for|trust|buy)|do\s+not\s+(?:click|download|trust|buy)"
    r"|is\s+(?:it|this|that)\s+(?:real|legit|safe)|not\s+real|doesn'?t\s+exist|does\s+not\s+exist"
    r"|hasn'?t\s+been\s+(?:announced|released)|has\s+not\s+been\s+(?:announced|released)"
    r"|no\s+pc\s+(?:version|release|port)|reported?\s+(?:it|this|them|the\s+account)|lying|liars?)\b"
)
# Words around a WARNING match that turn it into reassurance ("not a scam", "no virus").
_REASSURANCE_BEFORE = re.compile(r"(?:\bno|\bnot(?:\s+a)?|\bzero|\banti|\b0)[\s-]+$", _F)
_REASSURANCE_AFTER = re.compile(r"^[\s-]*(?:free|clean|safe)\b", _F)


@dataclass(frozen=True)
class Match:
    snippet: str
    start: int
    end: int


def _snippet(text: str, start: int, end: int, pad: int = 0) -> str:
    s = text[max(0, start - pad) : min(len(text), end + pad)]
    s = " ".join(s.split())
    return s[:80] + ("..." if len(s) > 80 else "")


def find_all(pattern: re.Pattern[str], text: str, limit: int = 5) -> list[Match]:
    out: list[Match] = []
    for m in pattern.finditer(text):
        out.append(Match(_snippet(text, m.start(), m.end()), m.start(), m.end()))
        if len(out) >= limit:
            break
    return out


def find_warnings(text: str, limit: int = 5) -> list[Match]:
    """WARNING matches that are not reassurances like "no virus" / "not a scam"."""
    out: list[Match] = []
    for m in WARNING.finditer(text):
        before = text[max(0, m.start() - 12) : m.start()]
        after = text[m.end() : m.end() + 8]
        if _REASSURANCE_BEFORE.search(before) or _REASSURANCE_AFTER.search(after):
            continue
        out.append(Match(_snippet(text, m.start(), m.end()), m.start(), m.end()))
        if len(out) >= limit:
            break
    return out
