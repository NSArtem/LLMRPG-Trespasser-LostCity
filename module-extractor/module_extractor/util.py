"""Small standard-library utilities shared by the extractor."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any, Mapping
import zipfile

from .errors import ExtractorError


SAFE_ID = re.compile(r"^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$")
SAFE_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ExtractorError(f"file does not exist: {path}") from exc
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExtractorError(f"cannot read JSON from {path}: {exc}") from exc


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value))


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise ExtractorError(f"cannot read {path}: {exc}") from exc
    return digest.hexdigest()


def require_safe_id(value: Any, context: str) -> str:
    if not isinstance(value, str) or not SAFE_ID.fullmatch(value):
        raise ExtractorError(f"{context} must be a safe stable ID")
    return value


def require_sha256(value: Any, context: str) -> str:
    if not isinstance(value, str) or not SHA256.fullmatch(value):
        raise ExtractorError(f"{context} must be a lowercase SHA-256")
    return value


def deterministic_zip(path: Path, entries: Mapping[str, bytes | Path]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for name in sorted(entries):
            if name.startswith("/") or ".." in Path(name).parts:
                raise ExtractorError(f"unsafe ZIP member name: {name}")
            value = entries[name]
            payload = value.read_bytes() if isinstance(value, Path) else value
            info = zipfile.ZipInfo(name, ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            info.create_system = 3
            archive.writestr(info, payload)


def content_tree_hash(root: Path) -> str:
    """Hash relative names and bytes, independent of filesystem metadata."""
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        payload = path.read_bytes()
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def atomic_publish(stage: Path, destination: Path, *, replace: bool = False) -> None:
    """Publish a staged directory, rolling back a replaced target on failure."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not replace:
        if not destination.is_dir() or any(destination.iterdir()):
            raise ExtractorError(f"refusing to overwrite non-empty output: {destination}")
        destination.rmdir()
    backup: Path | None = None
    if destination.exists():
        backup = Path(
            tempfile.mkdtemp(prefix=f".{destination.name}-backup-", dir=destination.parent)
        )
        backup.rmdir()
        os.replace(destination, backup)
    try:
        os.replace(stage, destination)
    except BaseException:
        if backup is not None and backup.exists() and not destination.exists():
            os.replace(backup, destination)
        raise
    if backup is not None:
        shutil.rmtree(backup)


def resolve_asset_root(run_dir: Path, prepared: Mapping[str, Any]) -> Path:
    value = prepared.get("asset_root")
    if not isinstance(value, str):
        raise ExtractorError("prepared.json.asset_root must be a string")
    root = (run_dir / value).resolve()
    if not root.is_dir():
        raise ExtractorError(f"prepared asset root does not exist: {root}")
    return root
