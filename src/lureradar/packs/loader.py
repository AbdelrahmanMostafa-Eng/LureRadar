"""Locate, load and resolve campaign packs."""

from __future__ import annotations

import os
from collections.abc import Iterable
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from lureradar.errors import PackError
from lureradar.packs.schema import Allowlist, Brand, Facts, Pack, PackFile

PACK_FILENAME = "pack.yaml"


def packs_root() -> Path:
    """Directory holding pack folders.

    Resolution order: ``$LURERADAR_PACKS_DIR``; the copy bundled in the wheel
    (``lureradar/_packs``); the repository's ``packs/`` (editable installs).
    """
    env = os.environ.get("LURERADAR_PACKS_DIR")
    if env:
        return Path(env)
    bundled = Path(str(resources.files("lureradar"))) / "_packs"
    if bundled.is_dir():
        return bundled
    repo = Path(__file__).resolve().parents[3] / "packs"
    if repo.is_dir():
        return repo
    raise PackError("no packs directory found; set LURERADAR_PACKS_DIR")


def list_pack_dirs(root: Path | None = None) -> list[Path]:
    base = root or packs_root()
    return sorted(p.parent for p in base.glob(f"*/{PACK_FILENAME}"))


def _read_yaml(path: Path) -> Any:
    try:
        with path.open(encoding="utf-8") as fh:
            return yaml.safe_load(fh)
    except FileNotFoundError as exc:
        raise PackError(f"{path}: file not found") from exc
    except yaml.YAMLError as exc:
        raise PackError(f"{path}: invalid YAML: {exc}") from exc


def _resolve_ref(pack_dir: Path, ref: str, key: str) -> Any:
    """Load a sibling file referenced from pack.yaml, refusing path traversal."""
    candidate = (pack_dir / ref).resolve()
    if candidate.parent != pack_dir.resolve() or candidate.suffix not in (".yaml", ".yml"):
        raise PackError(f"{pack_dir.name}: {key} must reference a .yaml file in the pack folder")
    data = _read_yaml(candidate)
    # Allow both `keywords: [...]` files and bare lists.
    if isinstance(data, dict) and key in data and len(data) <= 2:
        inner = data[key]
        if key in ("keywords", "intents", "brands"):
            return inner
    return data


def format_validation_error(exc: ValidationError, where: str) -> str:
    lines = [f"{where}: {exc.error_count()} problem(s)"]
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"]) or "(root)"
        lines.append(f"  - {loc}: {err['msg']}")
    return "\n".join(lines)


def load_pack(pack_dir: Path) -> Pack:
    """Load and fully resolve one pack folder."""
    pack_dir = Path(pack_dir)
    raw = _read_yaml(pack_dir / PACK_FILENAME)
    if not isinstance(raw, dict):
        raise PackError(f"{pack_dir / PACK_FILENAME}: expected a mapping at the top level")
    try:
        spec = PackFile.model_validate(raw)
    except ValidationError as exc:
        raise PackError(format_validation_error(exc, str(pack_dir / PACK_FILENAME))) from exc

    resolved: dict[str, Any] = spec.model_dump(exclude={"keywords", "intents", "brands"})
    for key in ("keywords", "intents", "brands"):
        value = getattr(spec, key)
        resolved[key] = _resolve_ref(pack_dir, value, key) if isinstance(value, str) else value
        if key == "brands" and not isinstance(value, str):
            resolved[key] = [b.model_dump() if isinstance(b, Brand) else b for b in value]
    for key, model in (("allowlist", Allowlist), ("facts", Facts)):
        value = getattr(spec, key)
        if isinstance(value, str):
            resolved[key] = _resolve_ref(pack_dir, value, key)
        elif value is None:
            resolved[key] = None if key == "facts" else {}
        else:
            resolved[key] = value.model_dump() if isinstance(value, model) else value

    resolved["pc_watch"] = (
        _resolve_ref(pack_dir, spec.pc_watch, "pc_watch") if spec.pc_watch else None
    )
    if spec.id != pack_dir.name:
        raise PackError(f"{pack_dir}: pack id {spec.id!r} must match its folder name")
    try:
        return Pack.model_validate(resolved)
    except ValidationError as exc:
        raise PackError(format_validation_error(exc, str(pack_dir))) from exc


def load_packs(ids: Iterable[str] | None = None, root: Path | None = None) -> list[Pack]:
    """Load the requested packs (all packs when ``ids`` is None)."""
    base = root or packs_root()
    available = {d.name: d for d in list_pack_dirs(base)}
    wanted = list(ids) if ids else sorted(available)
    missing = [i for i in wanted if i not in available]
    if missing:
        raise PackError(
            f"unknown pack(s): {', '.join(missing)} (available: {', '.join(sorted(available))})"
        )
    packs = [_load_cached(str(available[i])) for i in wanted]
    if ids:
        return packs
    # template packs (e.g. example-launch) are only used when requested explicitly
    return [p for p in packs if not p.template]


@lru_cache(maxsize=64)
def _load_cached(path: str) -> Pack:
    return load_pack(Path(path))


@lru_cache(maxsize=1)
def base_allowlist() -> Allowlist:
    """Global allowlist shipped with the package (pack-independent platforms/outlets)."""
    text = resources.files("lureradar.data").joinpath("allowlist_base.yaml").read_text("utf-8")
    data = yaml.safe_load(text) or {}
    try:
        return Allowlist.model_validate(data)
    except ValidationError as exc:  # pragma: no cover - guarded by tests
        raise PackError(format_validation_error(exc, "allowlist_base.yaml")) from exc


def clear_caches() -> None:
    _load_cached.cache_clear()
    base_allowlist.cache_clear()
