"""Detached feed signatures in minisign format (Ed25519, BLAKE2b-prehashed).

Anyone can verify with the stock tool:

    minisign -Vm latest.json -p keys/lureradar-feed.pub

or with ``lureradar feed verify``. The signing key lives only in the
``LURERADAR_SIGNING_KEY`` GitHub Actions secret (base64, our own compact
format); the public key is committed at ``keys/lureradar-feed.pub``.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import os
import time
from dataclasses import dataclass
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from lureradar import __version__
from lureradar.errors import SignatureError

_SECRET_MAGIC = b"LRSK"
ENV_KEY = "LURERADAR_SIGNING_KEY"


@dataclass(frozen=True)
class SigningKey:
    key_id: bytes  # 8 bytes, as stored in minisign blobs
    private: Ed25519PrivateKey

    @property
    def public_bytes(self) -> bytes:
        return self.private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)

    @property
    def key_id_hex(self) -> str:
        return key_id_hex(self.key_id)

    def secret_b64(self) -> str:
        from cryptography.hazmat.primitives.serialization import NoEncryption, PrivateFormat

        seed = self.private.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
        return base64.b64encode(_SECRET_MAGIC + self.key_id + seed).decode()

    def public_file(self) -> str:
        blob = base64.b64encode(b"Ed" + self.key_id + self.public_bytes).decode()
        return f"untrusted comment: minisign public key {self.key_id_hex}\n{blob}\n"


def key_id_hex(key_id: bytes) -> str:
    """minisign displays the little-endian key id as uppercase hex."""
    return key_id[::-1].hex().upper()


def generate() -> SigningKey:
    return SigningKey(key_id=os.urandom(8), private=Ed25519PrivateKey.generate())


def load_secret(value: str) -> SigningKey:
    try:
        raw = base64.b64decode(value.strip(), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise SignatureError("signing key is not valid base64") from exc
    if len(raw) != 44 or not raw.startswith(_SECRET_MAGIC):
        raise SignatureError("signing key has the wrong format (expected LureRadar secret key)")
    return SigningKey(key_id=raw[4:12], private=Ed25519PrivateKey.from_private_bytes(raw[12:]))


def signing_key_from_env() -> SigningKey | None:
    value = os.environ.get(ENV_KEY)
    return load_secret(value) if value else None


@dataclass(frozen=True)
class PublicKey:
    key_id: bytes
    key: Ed25519PublicKey

    @property
    def key_id_hex(self) -> str:
        return key_id_hex(self.key_id)


def load_public(text: str) -> PublicKey:
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    blob_line = lines[-1] if lines else ""
    try:
        blob = base64.b64decode(blob_line, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise SignatureError("public key is not valid base64") from exc
    if len(blob) != 42 or blob[:2] != b"Ed":
        raise SignatureError("not a minisign Ed25519 public key")
    return PublicKey(key_id=blob[2:10], key=Ed25519PublicKey.from_public_bytes(blob[10:]))


def sign(data: bytes, key: SigningKey, filename: str, timestamp: int | None = None) -> str:
    """Return the text of a ``.minisig`` file for ``data``."""
    digest = hashlib.blake2b(data, digest_size=64).digest()
    signature = key.private.sign(digest)
    ts = int(time.time()) if timestamp is None else timestamp
    trusted = f"timestamp:{ts}\tfile:{filename}\tgenerator:LureRadar/{__version__}"
    global_sig = key.private.sign(signature + trusted.encode())
    return (
        "untrusted comment: signature from LureRadar feed key\n"
        f"{base64.b64encode(b'ED' + key.key_id + signature).decode()}\n"
        f"trusted comment: {trusted}\n"
        f"{base64.b64encode(global_sig).decode()}\n"
    )


def verify(data: bytes, signature_text: str, public: PublicKey) -> str:
    """Verify a minisign signature; return the trusted comment. Raises SignatureError."""
    lines = signature_text.splitlines()
    if len(lines) < 4 or not lines[2].startswith("trusted comment: "):
        raise SignatureError("malformed signature file")
    try:
        blob = base64.b64decode(lines[1].strip(), validate=True)
        global_sig = base64.b64decode(lines[3].strip(), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise SignatureError("signature is not valid base64") from exc
    if len(blob) != 74 or blob[:2] not in (b"ED", b"Ed"):
        raise SignatureError("unsupported signature algorithm")
    if blob[2:10] != public.key_id:
        raise SignatureError(
            f"signature key id {key_id_hex(blob[2:10])} != public key {public.key_id_hex}"
        )
    signature = blob[10:]
    message = hashlib.blake2b(data, digest_size=64).digest() if blob[:2] == b"ED" else data
    trusted = lines[2][len("trusted comment: ") :]
    try:
        public.key.verify(signature, message)
        public.key.verify(global_sig, signature + trusted.encode())
    except InvalidSignature as exc:
        raise SignatureError("signature does not match the data") from exc
    return trusted


def sha256sums(paths: list[Path], root: Path) -> str:
    lines = []
    for path in sorted(paths):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.relative_to(root).as_posix()}")
    return "\n".join(lines) + "\n"


def check_sha256sums(text: str, root: Path) -> list[str]:
    """Return a list of problems (empty when every checksum matches)."""
    problems = []
    for line in text.splitlines():
        if not line.strip():
            continue
        digest, _, name = line.partition("  ")
        path = root / name
        if not path.is_file():
            problems.append(f"{name}: missing")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            problems.append(f"{name}: checksum mismatch")
    return problems
