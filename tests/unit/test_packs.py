from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml

from lureradar.errors import PackError
from lureradar.packs import base_allowlist, list_pack_dirs, load_pack, load_packs, packs_root
from lureradar.packs.loader import clear_caches
from lureradar.packs.scaffold import new_pack
from lureradar.packs.schema import Pack
from lureradar.packs.validator import lint_pack, validate_pack_dir


def test_gta6_pack_loads_and_is_dated() -> None:
    (pack,) = load_packs(["gta6"])
    assert pack.id == "gta6"
    assert "gta 6" in pack.keywords
    assert pack.facts is not None
    pc = pack.facts.platforms["pc"]
    assert pc.status == "unreleased"
    fact = pack.facts.fact(pc.fact or "")
    assert fact is not None and fact.sources and fact.as_of >= date(2026, 11, 21)
    assert pack.platform_label("pc") == "PC"
    assert pack.brand("rockstargames") is not None
    assert pack.brand("rockstargames").label == "Rockstar Games"  # type: ignore[union-attr]


def test_every_shipped_pack_validates_without_errors() -> None:
    for d in list_pack_dirs():
        report = validate_pack_dir(d, today=date(2026, 11, 21))
        assert report.ok, report.errors
        assert report.warnings == []


def test_unknown_pack() -> None:
    with pytest.raises(PackError, match="unknown pack"):
        load_packs(["nope"])


def test_base_allowlist_is_disjoint_and_valid() -> None:
    allow = base_allowlist()
    assert "youtube.com" in allow.platforms
    assert not set(allow.outlets) & set(allow.platforms)


def _write(tmp: Path, name: str, body: dict[str, object]) -> Path:
    d = tmp / name
    d.mkdir()
    (d / "pack.yaml").write_text(yaml.safe_dump(body), encoding="utf-8")
    return d


MINIMAL = {
    "id": "demo",
    "name": "Demo launch",
    "version": 1,
    "as_of": "2026-11-21",
    "keywords": ["demo game"],
    "intents": ["download", "free"],
}


def test_inline_pack(tmp_path: Path) -> None:
    pack = load_pack(_write(tmp_path, "demo", MINIMAL))
    assert pack.keywords == ["demo game"] and pack.facts is None
    assert any("facts" in w for w in lint_pack(pack, today=date(2026, 11, 21)))


@pytest.mark.parametrize(
    ("patch", "message"),
    [
        ({"keywords": ["ab"]}, "too generic"),
        ({"keywords": ["demo game", "Demo  Game"]}, "duplicate keyword"),
        ({"id": "Bad Id"}, "pack id"),
        ({"brands": [{"name": "x y", "official": ["example.com"]}]}, "brand name"),
        ({"brands": [{"name": "brand", "official": ["not a domain"]}]}, "valid registrable"),
        ({"allowlist": {"outlets": ["example.com"], "platforms": ["example.com"]}}, "both"),
        ({"unexpected": 1}, "Extra inputs"),
    ],
)
def test_invalid_packs_give_clear_errors(
    tmp_path: Path, patch: dict[str, object], message: str
) -> None:
    body = {**MINIMAL, **patch}
    d = _write(tmp_path, str(body["id"]).replace(" ", "_"), body)
    report = validate_pack_dir(d)
    assert not report.ok
    assert message in report.errors[0]


def test_folder_name_must_match_id(tmp_path: Path) -> None:
    d = _write(tmp_path, "other", MINIMAL)
    with pytest.raises(PackError, match="must match its folder"):
        load_pack(d)


def test_file_references_cannot_escape_pack(tmp_path: Path) -> None:
    (tmp_path / "evil.yaml").write_text("keywords: [stolen]", encoding="utf-8")
    d = _write(tmp_path, "demo", {**MINIMAL, "keywords": "../evil.yaml"})
    with pytest.raises(PackError, match=r"must reference a \.yaml file in the pack folder"):
        load_pack(d)


def test_bad_yaml(tmp_path: Path) -> None:
    d = tmp_path / "demo"
    d.mkdir()
    (d / "pack.yaml").write_text("id: [unterminated", encoding="utf-8")
    with pytest.raises(PackError, match="invalid YAML"):
        load_pack(d)
    (d / "pack.yaml").write_text("- a list", encoding="utf-8")
    with pytest.raises(PackError, match="mapping"):
        load_pack(d)


def test_facts_reference_validation(tmp_path: Path) -> None:
    facts = {
        "as_of": "2026-11-21",
        "facts": [],
        "platforms": {"pc": {"status": "unreleased", "fact": "missing", "terms": ["pc"]}},
    }
    d = _write(tmp_path, "demo", {**MINIMAL, "facts": facts})
    with pytest.raises(PackError, match="unknown fact"):
        load_pack(d)


def test_stale_facts_warn(tmp_path: Path) -> None:
    src = {
        "url": "https://example.com/s",
        "title": "t",
        "accessed": "2025-01-01",
    }
    facts = {
        "as_of": "2025-01-01",
        "facts": [
            {
                "id": "f",
                "claim": "c",
                "status": "confirmed",
                "as_of": "2025-01-01",
                "sources": [src],
            }
        ],
        "platforms": {"pc": {"status": "unreleased", "terms": ["pc"]}},
    }
    pack = load_pack(_write(tmp_path, "demo", {**MINIMAL, "facts": facts}))
    warnings = lint_pack(pack, today=date(2026, 11, 21))
    assert any("older than" in w for w in warnings)
    assert any("stale" in w for w in warnings)
    assert any("without a backing fact" in w for w in warnings)


def test_scaffold_creates_valid_pack(tmp_path: Path) -> None:
    path = new_pack("console-x", tmp_path, "Console X")
    report = validate_pack_dir(path)
    assert report.ok, report.errors
    assert len((path / "pack.yaml").read_text().splitlines()) <= 30
    with pytest.raises(PackError, match="already exists"):
        new_pack("console-x", tmp_path)
    with pytest.raises(PackError):
        new_pack("Bad!", tmp_path)
    with pytest.raises(PackError, match="4 letters"):
        new_pack("ab-c", tmp_path)


def test_packs_root_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LURERADAR_PACKS_DIR", str(tmp_path))
    clear_caches()
    assert packs_root() == tmp_path
    assert list_pack_dirs() == []
    monkeypatch.delenv("LURERADAR_PACKS_DIR")
    clear_caches()
    assert (packs_root() / "gta6" / "pack.yaml").is_file()


def test_pack_model_roundtrip() -> None:
    (pack,) = load_packs(["gta6"])
    again = Pack.model_validate(pack.model_dump())
    assert again == pack
