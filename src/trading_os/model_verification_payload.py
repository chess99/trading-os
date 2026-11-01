"""Closed opaque verification-ZIP transport. No extraction or code execution.
This function is copied verbatim into published checkers; numeric body unchanged.
"""

import hashlib
import json
import os
import re
import stat
from pathlib import Path

PART_BYTES = 6 * 1024**2
MAX_PARTS = 32
MAX_PAYLOAD_BYTES = PART_BYTES * MAX_PARTS
MAX_MANIFEST_BYTES = 64 * 1024


def _read_regular(path, expected_size=None, limit=MAX_PAYLOAD_BYTES):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise ValueError("payload member must be one regular file")
        if before.st_size > limit or (
            expected_size is not None and before.st_size != expected_size
        ):
            raise ValueError("payload member size mismatch")
        with os.fdopen(os.dup(fd), "rb") as stream:
            data = stream.read(limit + 1)
        after, named = os.fstat(fd), path.lstat()
        if len(data) != before.st_size or len(data) > limit:
            raise ValueError("payload member read size mismatch")
        if (before.st_dev, before.st_ino) != (named.st_dev, named.st_ino):
            raise ValueError("payload member identity changed")
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns, before.st_nlink) != (
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
            after.st_nlink,
        ):
            raise ValueError("payload member changed while reading")
        return data
    finally:
        os.close(fd)


def _unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate manifest key")
        obj[key] = value
    return obj


def verification_manifest(raw, period):
    """Validate one immutable canonical byte string and return its closed object."""
    if not isinstance(period, str) or not re.fullmatch(r"20\d{2}-(FY|Q1|H1|Q3)", period):
        raise ValueError("invalid payload period")
    if not isinstance(raw, bytes) or len(raw) > MAX_MANIFEST_BYTES:
        raise ValueError("invalid manifest bytes")
    manifest = json.loads(raw, object_pairs_hook=_unique_object)
    if raw != (json.dumps(manifest, separators=(",", ":"), ensure_ascii=True) + "\n").encode(
        "ascii"
    ):
        raise ValueError("canonical manifest bytes required")
    if not isinstance(manifest, dict) or set(manifest) != {
        "schema",
        "period",
        "payload_bytes",
        "payload_sha256",
        "parts",
    }:
        raise ValueError("closed manifest fields required")
    if manifest["schema"] != "trading_os_verification_payload_v1" or manifest["period"] != period:
        raise ValueError("manifest schema or period mismatch")
    total = manifest["payload_bytes"]
    if type(total) is not int or not 0 < total <= MAX_PAYLOAD_BYTES:
        raise ValueError("invalid payload size")
    if not isinstance(manifest["payload_sha256"], str) or not re.fullmatch(
        "[a-f0-9]{64}", manifest["payload_sha256"]
    ):
        raise ValueError("invalid whole payload hash")
    parts = manifest["parts"]
    count = (total + PART_BYTES - 1) // PART_BYTES
    if not isinstance(parts, list) or len(parts) != count or not 1 <= count <= MAX_PARTS:
        raise ValueError("invalid part count")
    for index, entry in enumerate(parts):
        name = f"{period}-verification-part-{index:03d}.bin"
        size = min(PART_BYTES, total - index * PART_BYTES)
        if not isinstance(entry, dict) or set(entry) != {"file", "bytes", "sha256"}:
            raise ValueError("closed part fields required")
        if entry["file"] != name or type(entry["bytes"]) is not int or entry["bytes"] != size:
            raise ValueError("part order, filename or size mismatch")
        if not isinstance(entry["sha256"], str) or not re.fullmatch(
            "[a-f0-9]{64}", entry["sha256"]
        ):
            raise ValueError("invalid part hash")
    return manifest


def verification_payload(
    directory, period, expected_bytes, expected_sha256, *, manifest_bytes=None
):
    root = Path(directory)
    if root.resolve() != root.absolute() or not root.is_dir():
        raise ValueError("payload directory must be direct and absolute")
    if type(expected_bytes) is not int or not 0 < expected_bytes <= MAX_PAYLOAD_BYTES:
        raise ValueError("invalid expected payload size")
    if not isinstance(expected_sha256, str) or not re.fullmatch("[a-f0-9]{64}", expected_sha256):
        raise ValueError("invalid expected payload hash")
    raw = manifest_bytes
    if raw is None:
        if not isinstance(period, str) or not re.fullmatch(r"20\d{2}-(FY|Q1|H1|Q3)", period):
            raise ValueError("invalid payload period")
        raw = _read_regular(
            root / (period + "-verification-payload.json"), limit=MAX_MANIFEST_BYTES
        )
    manifest = verification_manifest(raw, period)
    if manifest["payload_bytes"] != expected_bytes or manifest["payload_sha256"] != expected_sha256:
        raise ValueError("manifest does not match checker-pinned ZIP")
    payload = bytearray()
    for entry in manifest["parts"]:
        data = _read_regular(root / entry["file"], entry["bytes"], PART_BYTES)
        if hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise ValueError("part hash mismatch")
        payload.extend(data)
    if len(payload) != expected_bytes or hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise ValueError("whole original ZIP mismatch")
    return bytes(payload)
