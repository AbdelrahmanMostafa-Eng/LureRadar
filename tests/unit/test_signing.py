from __future__ import annotations

import base64

import minisign  # independent implementation (py-minisign), dev dependency
import pytest

from lureradar.errors import SignatureError
from lureradar.export import signing


def test_sign_verify_roundtrip_and_tamper() -> None:
    key = signing.generate()
    pub = signing.load_public(key.public_file())
    sig = signing.sign(b"feed", key, "latest.json", timestamp=1700000000)
    trusted = signing.verify(b"feed", sig, pub)
    assert trusted.startswith("timestamp:1700000000\tfile:latest.json")
    with pytest.raises(SignatureError, match="does not match"):
        signing.verify(b"feeD", sig, pub)
    tampered = sig.replace("file:latest.json", "file:other.json")
    with pytest.raises(SignatureError):
        signing.verify(b"feed", tampered, pub)


def test_independent_minisign_implementation_accepts_our_signatures(tmp_path) -> None:  # type: ignore[no-untyped-def]
    key = signing.generate()
    (tmp_path / "k.pub").write_text(key.public_file())
    data = b'{"indicators": []}\n'
    (tmp_path / "sig").write_text(signing.sign(data, key, "latest.json"))
    pk = minisign.PublicKey.from_file(str(tmp_path / "k.pub"))
    pk.verify(data, minisign.Signature.from_file(str(tmp_path / "sig")))
    with pytest.raises(minisign.VerifyError):
        pk.verify(data + b" ", minisign.Signature.from_file(str(tmp_path / "sig")))


def test_secret_roundtrip_and_env(monkeypatch: pytest.MonkeyPatch) -> None:
    key = signing.generate()
    again = signing.load_secret(key.secret_b64())
    assert again.public_bytes == key.public_bytes and again.key_id == key.key_id
    assert signing.signing_key_from_env() is None
    monkeypatch.setenv(signing.ENV_KEY, key.secret_b64())
    assert signing.signing_key_from_env().key_id == key.key_id  # type: ignore[union-attr]
    assert len(key.key_id_hex) == 16 and key.key_id_hex.isupper()


@pytest.mark.parametrize("bad", ["!!!", base64.b64encode(b"x" * 44).decode(), ""])
def test_bad_secrets(bad: str) -> None:
    with pytest.raises(SignatureError):
        signing.load_secret(bad or "AAAA")


def test_bad_public_and_signature_files() -> None:
    with pytest.raises(SignatureError):
        signing.load_public("untrusted comment: x\n!!!")
    with pytest.raises(SignatureError):
        signing.load_public("untrusted comment: x\n" + base64.b64encode(b"Ed" + b"x" * 10).decode())
    key = signing.generate()
    pub = signing.load_public(key.public_file())
    with pytest.raises(SignatureError, match="malformed"):
        signing.verify(b"x", "only one line", pub)
    other = signing.generate()
    sig = signing.sign(b"x", other, "f")
    with pytest.raises(SignatureError, match="key id"):
        signing.verify(b"x", sig, pub)
    lines = sig.splitlines()
    lines[1] = "@@@"
    with pytest.raises(SignatureError, match="base64"):
        signing.verify(b"x", "\n".join(lines), pub)


def test_sha256sums(tmp_path) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / "a.txt").write_text("a")
    sums = signing.sha256sums([tmp_path / "a.txt"], tmp_path)
    assert signing.check_sha256sums(sums, tmp_path) == []
    (tmp_path / "a.txt").write_text("b")
    assert signing.check_sha256sums(sums, tmp_path) == ["a.txt: checksum mismatch"]
    (tmp_path / "a.txt").unlink()
    assert signing.check_sha256sums(sums + "\n", tmp_path) == ["a.txt: missing"]
