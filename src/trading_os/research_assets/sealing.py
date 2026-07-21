from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class SealingError(ValueError):
    """Raised when an immutable artifact cannot be sealed or verified."""


@dataclass(frozen=True, slots=True)
class SealedArtifact:
    path: Path
    manifest_path: Path
    artifact_type: str
    sha256: str
    size: int
    sealed_at: dt.datetime


_MANIFEST_KEYS = {
    "schema_version",
    "artifact",
    "artifact_type",
    "sha256",
    "size",
    "sealed_at",
}


def canonical_json_bytes(value: Any) -> bytes:
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise SealingError(f"value cannot be represented as canonical JSON: {exc}") from exc
    return text.encode("utf-8")


def atomic_write_bytes(path: str | Path, data: bytes) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, target)
        temp_path = None
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
    return target


def seal_json(
    path: str | Path,
    payload: Any,
    *,
    artifact_type: str,
    sealed_at: dt.datetime,
) -> SealedArtifact:
    target = Path(path)
    if not isinstance(artifact_type, str) or not artifact_type.strip():
        raise SealingError("artifact_type must be a non-empty string")
    _require_aware_datetime(sealed_at, "sealed_at")
    artifact_type = artifact_type.strip()
    content = canonical_json_bytes(payload)
    digest = hashlib.sha256(content).hexdigest()
    manifest_path = _manifest_path(target)

    if manifest_path.exists():
        existing = verify_sealed(target)
        if existing.sha256 != digest or existing.artifact_type != artifact_type:
            raise SealingError(f"sealed artifact is immutable: {target}")
        return existing

    if target.exists():
        if not target.is_file():
            raise SealingError(f"artifact path is not a file: {target}")
        if target.read_bytes() != content:
            raise SealingError(f"refusing to overwrite unsealed artifact: {target}")
    else:
        atomic_write_bytes(target, content)

    manifest = {
        "schema_version": 2,
        "artifact": target.name,
        "artifact_type": artifact_type,
        "sha256": digest,
        "size": len(content),
        "sealed_at": sealed_at.isoformat(),
    }
    atomic_write_bytes(manifest_path, canonical_json_bytes(manifest))
    return verify_sealed(target)


def verify_sealed(path: str | Path) -> SealedArtifact:
    target = Path(path)
    manifest_path = _manifest_path(target)
    if not target.is_file():
        raise SealingError(f"sealed artifact is missing: {target}")
    if not manifest_path.is_file():
        raise SealingError(f"seal manifest is missing: {manifest_path}")
    manifest_bytes = manifest_path.read_bytes()
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SealingError(f"invalid seal manifest: {manifest_path}") from exc
    if not isinstance(manifest, dict):
        raise SealingError("seal manifest must be an object")
    if set(manifest) != _MANIFEST_KEYS:
        raise SealingError("seal manifest fields do not match the v2 contract")
    if canonical_json_bytes(manifest) != manifest_bytes:
        raise SealingError("seal manifest is not canonical or has been modified")
    if manifest.get("schema_version") != 2:
        raise SealingError("seal manifest schema_version must be 2")
    if manifest.get("artifact") != target.name:
        raise SealingError("seal manifest artifact name does not match")
    artifact_type = manifest.get("artifact_type")
    if not isinstance(artifact_type, str) or not artifact_type.strip():
        raise SealingError("seal manifest artifact_type is invalid")
    expected_hash = manifest.get("sha256")
    if (
        not isinstance(expected_hash, str)
        or len(expected_hash) != 64
        or any(char not in "0123456789abcdef" for char in expected_hash)
    ):
        raise SealingError("seal manifest sha256 is invalid")
    expected_size = manifest.get("size")
    if isinstance(expected_size, bool) or not isinstance(expected_size, int):
        raise SealingError("seal manifest size must be an integer")
    sealed_text = manifest.get("sealed_at")
    if not isinstance(sealed_text, str):
        raise SealingError("seal manifest sealed_at is invalid")
    try:
        sealed_at = dt.datetime.fromisoformat(sealed_text)
    except ValueError as exc:
        raise SealingError("seal manifest sealed_at is invalid") from exc
    _require_aware_datetime(sealed_at, "seal manifest sealed_at")

    content = target.read_bytes()
    actual_hash = hashlib.sha256(content).hexdigest()
    if actual_hash != expected_hash:
        raise SealingError(f"sealed artifact sha256 mismatch: {target}")
    if len(content) != expected_size:
        raise SealingError(f"sealed artifact size mismatch: {target}")
    try:
        parsed_content = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SealingError(f"sealed artifact is not valid JSON: {target}") from exc
    if canonical_json_bytes(parsed_content) != content:
        raise SealingError(f"sealed artifact is not canonical JSON: {target}")

    return SealedArtifact(
        path=target,
        manifest_path=manifest_path,
        artifact_type=artifact_type,
        sha256=expected_hash,
        size=expected_size,
        sealed_at=sealed_at,
    )


def _manifest_path(path: Path) -> Path:
    return path.with_name(path.name + ".seal.json")


def _require_aware_datetime(value: dt.datetime, label: str) -> None:
    if not isinstance(value, dt.datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise SealingError(f"{label} must include timezone information")
