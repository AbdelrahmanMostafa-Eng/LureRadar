from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from lureradar import __version__
from lureradar.cli import app
from lureradar.schemas import load

runner = CliRunner()


def test_demo_command_exit_code_and_card() -> None:
    result = runner.invoke(app, ["check", "https://rockstar-gta6-pc-download[.]test/free-key"])
    assert result.exit_code == 20, result.output
    out = result.output
    assert "LIKELY LURE" in out
    assert "hxxps://rockstar-gta6-pc-download[.]test/free-key" in out
    assert "claims_unreleased_platform" in out
    assert "WHAT TO DO NEXT" in out


@pytest.mark.parametrize(
    ("target", "code"),
    [
        ("www.ign.com", 0),
        ("gta6-pc-download-free.xyz", 10),
        ("rockstar-gta6-pc-download.test", 20),
    ],
)
def test_exit_codes(target: str, code: int) -> None:
    assert runner.invoke(app, ["check", target]).exit_code == code


def test_json_output_matches_schema() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    result = runner.invoke(app, ["check", "--json", "gta6-pc-download.test"])
    data = json.loads(result.output)
    assert data["schema_version"] == "1.0"
    assert data["tier"] in ("suspicious", "likely")
    jsonschema.validate(data, load("verdict"))


def test_json_output_basic_shape() -> None:
    result = runner.invoke(app, ["check", "--json", "free gta 6 pc keys, dm me on telegram"])
    data = json.loads(result.output)
    assert data["kind"] == "text"
    assert {s["id"] for s in data["signals"]} >= {"text_unreleased_platform"}


def test_stdin_and_explain() -> None:
    result = runner.invoke(app, ["check", "-", "--explain"], input="gta6-pc-download.test\n")
    assert result.exit_code in (10, 20)
    assert "evidence:" in result.output


def test_invalid_target_is_error() -> None:
    result = runner.invoke(app, ["check", "javascript://x.test"])
    assert result.exit_code == 1


def test_unknown_pack_is_error() -> None:
    result = runner.invoke(app, ["check", "a.test", "--pack", "nope"])
    assert result.exit_code == 1
    assert "unknown pack" in result.output


def test_pack_commands(tmp_path: Path) -> None:
    listed = runner.invoke(app, ["pack", "list"])
    assert listed.exit_code == 0 and "gta6" in listed.output
    as_json = json.loads(runner.invoke(app, ["pack", "list", "--json"]).output)
    assert as_json[0]["id"] == "gta6"
    assert runner.invoke(app, ["pack", "validate"]).exit_code == 0
    created = runner.invoke(app, ["pack", "new", "console-x", "--root", str(tmp_path)])
    assert created.exit_code == 0
    assert runner.invoke(app, ["pack", "validate", str(tmp_path / "console-x")]).exit_code == 0
    dup = runner.invoke(app, ["pack", "new", "console-x", "--root", str(tmp_path)])
    assert dup.exit_code == 1
    (tmp_path / "broken").mkdir()
    (tmp_path / "broken" / "pack.yaml").write_text("id: broken\n", encoding="utf-8")
    assert runner.invoke(app, ["pack", "validate", str(tmp_path / "broken")]).exit_code == 1


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert __version__ in result.output
    data = json.loads(runner.invoke(app, ["version", "--json"]).output)
    assert data["version"] == __version__ and data["base_url"].endswith("/")


def test_offline_check_never_touches_the_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Privacy guarantee: `check` without --live opens no sockets and resolves no names."""
    import socket

    def boom(*_a: object, **_k: object) -> None:
        raise AssertionError("network access attempted in offline mode")

    monkeypatch.setattr(socket.socket, "connect", boom)
    monkeypatch.setattr(socket, "create_connection", boom)
    monkeypatch.setattr(socket, "getaddrinfo", boom)
    for target in (
        "https://rockstar-gta6-pc-download[.]test/free-key",
        "free gta 6 pc keys at gta6-keys.test, dm me on telegram",
        "xn--rckstargames-4fk.com",
    ):
        result = runner.invoke(app, ["check", target])
        assert result.exit_code in (0, 10, 20, 30), result.output


def test_doctor_offline_and_fixture_modes() -> None:
    result = runner.invoke(app, ["doctor", "--offline"])
    assert result.exit_code == 0 and "Environment" in result.output and "skipped" in result.output
    fixtures = Path(__file__).parents[1] / "fixtures" / "sources"
    data = json.loads(
        runner.invoke(app, ["doctor", "--json", "--offline", "--fixtures", str(fixtures)]).output
    )
    statuses = {row["name"]: row["status"] for row in data["sources"]}
    assert statuses["crtsh"] == "degraded" and statuses["urlhaus"] == "degraded"
    env = {row["name"]: row["status"] for row in data["environment"]}
    assert env["packs"] == "ok" and env["dns"] == "skipped"
