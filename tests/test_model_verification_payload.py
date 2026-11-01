"""Closed sidecar and isolated-copy regressions, never financial model replay."""

import copy
import hashlib
import inspect
import json
import os
from pathlib import Path

import pytest

from trading_os import model_verification_payload as codec

PERIOD = "2026-Q3"
NAME = PERIOD + "-verification-part-000.bin"
MANIFEST = PERIOD + "-verification-payload.json"
RAW = b"complete opaque ZIP contract fixture\x00\xff"
SHA = hashlib.sha256(RAW).hexdigest()
BASE = {
    "schema": "trading_os_verification_payload_v1",
    "period": PERIOD,
    "payload_bytes": len(RAW),
    "payload_sha256": SHA,
    "parts": [{"file": NAME, "bytes": len(RAW), "sha256": SHA}],
}


def encoded(value):
    return (json.dumps(value, separators=(",", ":")) + "\n").encode()


def fixture(directory):
    directory.mkdir()
    (directory / MANIFEST).write_bytes(encoded(BASE))
    (directory / NAME).write_bytes(RAW)
    return directory


def test_whole_payload_and_validated_manifest(tmp_path):
    root = fixture(tmp_path / "source")
    assert codec.verification_manifest(encoded(BASE), PERIOD) == BASE
    assert codec.verification_payload(root, PERIOD, len(RAW), SHA) == RAW


@pytest.mark.parametrize(
    "kind",
    [
        "missing",
        "tamper",
        "order",
        "duplicate",
        "path",
        "whole",
        "size",
        "total",
        "extra",
        "period",
        "duplicate-key",
        "symlink",
        "hardlink",
        "hash-type",
    ],
)
def test_rejects_closed_contract_failures(tmp_path, kind):
    root = fixture(tmp_path / "source")
    manifest = copy.deepcopy(BASE)
    if kind == "missing":
        (root / NAME).unlink()
    elif kind == "tamper":
        (root / NAME).write_bytes(b"x" * len(RAW))
    elif kind == "order":
        manifest["parts"][0]["file"] = PERIOD + "-verification-part-001.bin"
    elif kind == "duplicate":
        manifest["parts"].append(manifest["parts"][0].copy())
    elif kind == "path":
        manifest["parts"][0]["file"] = "../outside.bin"
    elif kind == "whole":
        manifest["payload_sha256"] = "0" * 64
    elif kind == "size":
        manifest["parts"][0]["bytes"] = True
    elif kind == "total":
        manifest["payload_bytes"] = codec.MAX_PAYLOAD_BYTES + 1
    elif kind == "extra":
        manifest["url"] = "https://example.invalid/"
    elif kind == "period":
        manifest["period"] = "2025-FY"
    elif kind in {"symlink", "hardlink"}:
        (root / NAME).rename(root / "original.bin")
        if kind == "symlink":
            (root / NAME).symlink_to("original.bin")
        else:
            os.link(root / "original.bin", root / NAME)
    elif kind == "hash-type":
        manifest["parts"][0]["sha256"] = [SHA]
    raw = encoded(manifest)
    if kind == "duplicate-key":
        raw = raw.rstrip()[:-1] + b',"period":"2026-Q3"}\n'
    (root / MANIFEST).write_bytes(raw)
    with pytest.raises((ValueError, OSError)):
        codec.verification_payload(root, PERIOD, len(RAW), SHA)


def test_isolated_copy_uses_same_validated_bytes_after_source_swap(tmp_path, monkeypatch):
    # The previous two-read pattern could validate version B while copying A.
    # This regression changes the source after its first safe read; no second
    # source-manifest read may supply copy names, and the isolated bytes are A.
    from test_q3_model_reproduction import (
        test_published_q3_model_reproduces_in_isolated_directory as reproduce,
    )

    root = fixture(tmp_path / "source")
    (root / "2026-Q3.py").write_text("print('{\"fixture\":1}')\n")
    (root / "2026-Q3-output.json").write_text('{"fixture":1}\n')
    checker = inspect.getsource(codec) + (
        f"\nassert verification_payload(Path(__file__).resolve().parent, {PERIOD!r}, "
        f"{len(RAW)}, {SHA!r}) == {RAW!r}\n"
    )
    (root / "2026-Q3-independent-recompute.py").write_text(checker)
    original = codec._read_regular
    reads = []

    def swap_after_read(path, *args, **kwargs):
        result = original(path, *args, **kwargs)
        if Path(path) == root / MANIFEST:
            reads.append(str(path))
            bad = copy.deepcopy(BASE)
            bad["parts"][0]["file"] = "../outside.bin"
            (root / MANIFEST).write_bytes(encoded(bad))
        return result

    monkeypatch.setattr(codec, "_read_regular", swap_after_read)
    isolated = tmp_path / "isolated"
    isolated.mkdir()
    reproduce(root / "2026-Q3.py", isolated)
    assert len(reads) == 1
    assert (isolated / MANIFEST).read_bytes() == encoded(BASE)
    assert (isolated / NAME).read_bytes() == RAW
    assert not (tmp_path / "outside.bin").exists()
