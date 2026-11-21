"""``lureradar feed verify``: structural validation, checksums and signatures."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import orjson

from lureradar.errors import LureRadarError, SignatureError
from lureradar.export import abp, csvfeed, hosts, jsonfeed, rpz
from lureradar.export.signing import check_sha256sums, load_public, verify

Result = tuple[str, bool, str]


def _check_stix(text: str) -> int:
    data = orjson.loads(text)
    if data.get("type") != "bundle" or not isinstance(data.get("objects"), list):
        raise ValueError("not a STIX bundle")
    return sum(1 for o in data["objects"] if o.get("type") == "indicator")


def verify_feed_dir(
    directory: Path, pubkey: Path | None, require_signature: bool = False
) -> list[Result]:
    results: list[Result] = []
    latest = directory / "latest.json"
    try:
        doc = jsonfeed.load(latest)
        results.append(
            ("latest.json", True, f"schema {doc.schema_version}, {doc.count} indicators")
        )
    except LureRadarError as exc:
        return [("latest.json", False, str(exc))]
    expected = {i.domain for i in doc.indicators}

    parsers: dict[str, Callable[[str], object]] = {
        "hosts.txt": hosts.parse_hosts,
        "domains.txt": hosts.parse_domains,
        "adguard.txt": abp.parse_abp,
        "rpz.zone": rpz.parse_rpz,
        "indicators.csv": lambda t: [r["domain"] for r in csvfeed.parse_csv(t)],
        "stix.json": _check_stix,
    }
    for name, parse in parsers.items():
        path = directory / name
        if not path.is_file():
            results.append((name, False, "missing"))
            continue
        try:
            parsed = parse(path.read_text(encoding="utf-8"))
        except (ValueError, KeyError, orjson.JSONDecodeError) as exc:
            results.append((name, False, f"does not parse: {exc}"))
            continue
        if isinstance(parsed, list):
            got = set(parsed)
            ok = got <= expected and len(got) == len(expected)
            results.append(
                (name, ok, f"{len(got)} entries" + ("" if ok else " (mismatch with latest.json)"))
            )
        else:
            ok = parsed == len(expected)
            results.append((name, ok, f"{parsed} STIX indicators"))

    sums = directory / "SHA256SUMS"
    if sums.is_file():
        problems = check_sha256sums(sums.read_text(encoding="utf-8"), directory)
        results.append(
            ("SHA256SUMS", not problems, "all match" if not problems else "; ".join(problems))
        )
    else:
        results.append(("SHA256SUMS", False, "missing"))

    sigs = sorted(directory.glob("*.minisig"))
    if not sigs:
        results.append(("signatures", not require_signature, "unsigned (no .minisig files)"))
    elif pubkey is None:
        results.append(
            ("signatures", not require_signature, "present but no public key to verify with")
        )
    else:
        key = load_public(pubkey.read_text(encoding="utf-8"))
        for sig in sigs:
            target = sig.with_suffix("")
            try:
                verify(target.read_bytes(), sig.read_text(encoding="utf-8"), key)
                results.append((sig.name, True, f"valid (key {key.key_id_hex})"))
            except (SignatureError, FileNotFoundError) as exc:
                results.append((sig.name, False, str(exc)))
    return results
