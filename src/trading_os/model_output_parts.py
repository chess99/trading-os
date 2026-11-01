"""Lossless actual model-output XZ parts, separate from verification evidence.

One JSON document, or the exact eight separate 300015 documents; never a summary
or a silent merge. Decode each complete document and validate its JSON in turn.
"""

import hashlib
import json
import lzma
import os
import re
import stat
import tempfile
from pathlib import Path

PART_BYTES = 6 * 1024**2
MAX_MANIFEST_BYTES = 64 * 1024
MAX_COMPRESSED_BYTES = 192 * 1024**2
EIGHT_NAMES = (
    "production",
    "literal",
    "supplement-a-production",
    "supplement-a-literal",
    "supplement-b-production",
    "supplement-b-literal",
    "supplement-r-production",
    "supplement-r-literal",
)
LARGE_EXACT = (
    "600018",
    "53c9134dc98943c7222b845e6a503e4910e6c1552606fc2bc7a75d1a7d26d1f7",
    670121548,
    "308f5b98103a609927f18b27e06424545ab09d969f502082274cc9f6196a7959",
)


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate output manifest key")
        result[key] = value
    return result


def _fields(value, names):
    if not isinstance(value, dict) or set(value) != set(names):
        raise ValueError("closed output manifest fields required")


def _integer(value, limit):
    if type(value) is not int or not 0 < value <= limit:
        raise ValueError("invalid output transport size")


def _hash(value):
    if not isinstance(value, str) or not re.fullmatch("[a-f0-9]{64}", value):
        raise ValueError("invalid output transport hash")


def output_manifest(raw, period, symbol, producer_sha256):
    """The returned object and all later reads bind this ONE canonical byte string."""
    if not isinstance(raw, bytes) or len(raw) > MAX_MANIFEST_BYTES:
        raise ValueError("invalid output manifest bytes")
    if not re.fullmatch(r"20\d{2}-(FY|Q1|H1|Q3)", period) or not re.fullmatch(r"\d{6}", symbol):
        raise ValueError("invalid company or period")
    _hash(producer_sha256)
    m = json.loads(raw, object_pairs_hook=_unique)
    if raw != (json.dumps(m, separators=(",", ":"), ensure_ascii=True) + "\n").encode("ascii"):
        raise ValueError("canonical output manifest required")
    _fields(
        m, ("schema", "artifact_kind", "period", "symbol", "producer_sha256", "layout", "outputs")
    )
    if (
        m["schema"] != "trading_os_lossless_json_xz_parts_v1"
        or m["artifact_kind"] != "transport_manifest_not_model_result"
        or m["period"] != period
        or m["symbol"] != symbol
        or m["producer_sha256"] != producer_sha256
    ):
        raise ValueError("output manifest identity mismatch")
    if m["layout"] == "single_complete_json" and symbol != "300015":
        names = ("main",)
    elif m["layout"] == "cn300015_complete_eight_json" and symbol == "300015":
        names = EIGHT_NAMES
    else:
        raise ValueError("unsupported complete output layout")
    outputs = m["outputs"]
    if not isinstance(outputs, list) or len(outputs) != len(names):
        raise ValueError("incomplete output document coverage")
    total = 0
    for name, entry in zip(names, outputs, strict=True):
        _fields(
            entry,
            (
                "name",
                "compression",
                "compressed_bytes",
                "compressed_sha256",
                "expanded_bytes",
                "expanded_sha256",
                "expanded_media_type",
                "parts",
            ),
        )
        if (
            entry["name"] != name
            or entry["compression"] != "xz"
            or entry["expanded_media_type"] != "application/json"
        ):
            raise ValueError("output document identity or order mismatch")
        _integer(entry["compressed_bytes"], 100 * 1024**2)
        _hash(entry["compressed_sha256"])
        _hash(entry["expanded_sha256"])
        limit = 512 * 1024**2
        if (
            symbol,
            producer_sha256,
            entry["expanded_bytes"],
            entry["expanded_sha256"],
        ) == LARGE_EXACT and name == "main":
            limit = LARGE_EXACT[2]
        _integer(entry["expanded_bytes"], limit)
        total += entry["compressed_bytes"]
        if total > MAX_COMPRESSED_BYTES:
            raise ValueError("whole output transport too large")
        count = (entry["compressed_bytes"] + PART_BYTES - 1) // PART_BYTES
        if not isinstance(entry["parts"], list) or len(entry["parts"]) != count or count > 32:
            raise ValueError("output part count mismatch")
        for index, part in enumerate(entry["parts"]):
            _fields(part, ("file", "bytes", "sha256"))
            expected = f"{period}-output-{name}-part-{index:03d}.xzpart"
            size = min(PART_BYTES, entry["compressed_bytes"] - index * PART_BYTES)
            if part["file"] != expected or type(part["bytes"]) is not int or part["bytes"] != size:
                raise ValueError("output part order, path or length mismatch")
            _hash(part["sha256"])
    return m


def _part(root, entry):
    path = root / entry["file"]
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_size != entry["bytes"]
        ):
            raise ValueError("output part must be one exact regular file")
        with os.fdopen(os.dup(fd), "rb") as stream:
            data = stream.read(PART_BYTES + 1)
        after, named = os.fstat(fd), path.lstat()

        def identity(s):
            return (
                s.st_dev,
                s.st_ino,
                s.st_size,
                s.st_mtime_ns,
                s.st_ctime_ns,
                s.st_nlink,
            )

        if identity(before) != identity(after) or identity(before) != identity(named):
            raise ValueError("output part identity changed while reading")
        if len(data) != entry["bytes"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise ValueError("output part byte hash mismatch")
        return data
    finally:
        os.close(fd)


def reassemble_encoded_output(directory, manifest, entry, destination):
    """Recreate the exact original encoded XZ for unchanged original consumers."""
    root = Path(directory)
    if root.resolve() != root.absolute() or not root.is_dir():
        raise ValueError("output directory must be direct and absolute")
    if not any(entry is item for item in manifest["outputs"]):
        raise ValueError("entry is not the validated manifest object")
    digest = hashlib.sha256()
    size = 0
    with Path(destination).open("xb") as target:
        for part in entry["parts"]:
            data = _part(root, part)
            target.write(data)
            digest.update(data)
            size += len(data)
    if size != entry["compressed_bytes"] or digest.hexdigest() != entry["compressed_sha256"]:
        raise ValueError("whole original encoded output mismatch")
    return Path(destination)


def decode_output(directory, manifest, entry, destination):
    """Decode only a previously validated entry into a new explicit file."""
    root = Path(directory)
    if root.resolve() != root.absolute() or not root.is_dir():
        raise ValueError("output directory must be direct and absolute")
    if not any(entry is item for item in manifest["outputs"]):
        raise ValueError("entry is not the validated manifest object")
    encoded_hash, expanded_hash = hashlib.sha256(), hashlib.sha256()
    encoded_size = expanded_size = 0
    decoder = lzma.LZMADecompressor(format=lzma.FORMAT_XZ, memlimit=256 * 1024**2)
    with Path(destination).open("xb") as output:
        for part in entry["parts"]:
            data = _part(root, part)
            encoded_hash.update(data)
            encoded_size += len(data)
            if decoder.eof:
                raise ValueError("trailing or concatenated output XZ")
            while True:
                block = decoder.decompress(
                    data, max_length=min(1024 * 1024, entry["expanded_bytes"] - expanded_size + 1)
                )
                data = b""
                expanded_size += len(block)
                if expanded_size > entry["expanded_bytes"]:
                    raise ValueError("expanded output exceeds bound")
                output.write(block)
                expanded_hash.update(block)
                if decoder.eof:
                    if decoder.unused_data:
                        raise ValueError("trailing or concatenated output XZ")
                    break
                if decoder.needs_input:
                    break
    if (
        not decoder.eof
        or encoded_size != entry["compressed_bytes"]
        or encoded_hash.hexdigest() != entry["compressed_sha256"]
        or expanded_size != entry["expanded_bytes"]
        or expanded_hash.hexdigest() != entry["expanded_sha256"]
    ):
        raise ValueError("incomplete output XZ or whole size/hash mismatch")
    return Path(destination)


def verify_outputs(directory, raw, period, symbol, producer_sha256):
    """Codec-only full JSON checks; no model import/execution and no retained writes."""
    manifest = output_manifest(raw, period, symbol, producer_sha256)
    with tempfile.TemporaryDirectory(prefix="trading-os-output-codec-") as temporary:
        for index, entry in enumerate(manifest["outputs"]):
            path = decode_output(directory, manifest, entry, Path(temporary) / str(index))
            with path.open(encoding="utf-8") as stream:
                json.load(
                    stream, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value))
                )
            path.unlink()
    return manifest
