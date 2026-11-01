"""Versioned actual-output transport regression; no financial model executed."""

import copy
import hashlib
import json
import lzma
import os
from pathlib import Path

import pytest

from trading_os.model_output_parts import (
    EIGHT_NAMES,
    LARGE_EXACT,
    PART_BYTES,
    decode_output,
    output_manifest,
    reassemble_encoded_output,
    verify_outputs,
)

PERIOD = "2026-Q3"
PRODUCER = "1" * 64


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return (json.dumps(value, separators=(",", ":"), ensure_ascii=True) + "\n").encode()


def fixture(root, documents=None, symbol="300661", encoded=None):
    root.mkdir()
    names = EIGHT_NAMES if symbol == "300015" else ("main",)
    documents = documents or [canonical({"complete": [1, 2, 3], "name": n}) for n in names]
    outputs = []
    for name, raw in zip(names, documents, strict=True):
        data = encoded if encoded is not None else lzma.compress(raw, preset=0)
        parts = []
        for index, start in enumerate(range(0, len(data), PART_BYTES)):
            block = data[start : start + PART_BYTES]
            file = f"{PERIOD}-output-{name}-part-{index:03d}.xzpart"
            (root / file).write_bytes(block)
            parts.append({"file": file, "bytes": len(block), "sha256": sha(block)})
        outputs.append(
            {
                "name": name,
                "compression": "xz",
                "compressed_bytes": len(data),
                "compressed_sha256": sha(data),
                "expanded_bytes": len(raw),
                "expanded_sha256": sha(raw),
                "expanded_media_type": "application/json",
                "parts": parts,
            }
        )
    m = {
        "schema": "trading_os_lossless_json_xz_parts_v1",
        "artifact_kind": "transport_manifest_not_model_result",
        "period": PERIOD,
        "symbol": symbol,
        "producer_sha256": PRODUCER,
        "layout": "cn300015_complete_eight_json" if symbol == "300015" else "single_complete_json",
        "outputs": outputs,
    }
    return m, documents


def verify(root, m):
    return verify_outputs(root, canonical(m), PERIOD, m["symbol"], PRODUCER)


def test_single_complete_json_and_byte_inverse(tmp_path):
    m, documents = fixture(tmp_path / "parts")
    actual = verify(tmp_path / "parts", m)
    p = decode_output(tmp_path / "parts", actual, actual["outputs"][0], tmp_path / "decoded")
    assert p.read_bytes() == documents[0]
    encoded = reassemble_encoded_output(
        tmp_path / "parts", actual, actual["outputs"][0], tmp_path / "original.xz"
    )
    assert sha(encoded.read_bytes()) == actual["outputs"][0]["compressed_sha256"]
    assert lzma.decompress(encoded.read_bytes()) == documents[0]
    with pytest.raises(FileExistsError):
        reassemble_encoded_output(tmp_path / "parts", actual, actual["outputs"][0], encoded)
    with pytest.raises(FileExistsError):
        decode_output(tmp_path / "parts", actual, actual["outputs"][0], p)


def test_eight_documents_cannot_drop_merge_reorder_or_rename(tmp_path):
    root = tmp_path / "parts"
    m, documents = fixture(root, symbol="300015")
    checked = verify(root, m)
    assert [e["name"] for e in checked["outputs"]] == list(EIGHT_NAMES)
    for index, entry in enumerate(checked["outputs"]):
        assert (
            decode_output(root, checked, entry, tmp_path / str(index)).read_bytes()
            == documents[index]
        )
    for mutate in (
        lambda x: x["outputs"].pop(),
        lambda x: x["outputs"].reverse(),
        lambda x: x.update(layout="single_complete_json", outputs=x["outputs"][:1]),
        lambda x: x["outputs"][0].update(name="summary"),
    ):
        bad = copy.deepcopy(m)
        mutate(bad)
        with pytest.raises(ValueError):
            output_manifest(canonical(bad), PERIOD, "300015", PRODUCER)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda m: m.update(extra=True),
        lambda m: m.update(artifact_kind="model_result"),
        lambda m: m.update(producer_sha256="2" * 64),
        lambda m: m.update(symbol="600298"),
        lambda m: m["outputs"][0].update(compressed_bytes=True),
        lambda m: m["outputs"][0].update(expanded_bytes=513 * 1024**2),
        lambda m: m["outputs"][0].update(expanded_sha256="wrong"),
        lambda m: m["outputs"][0]["parts"][0].update(file="../secret"),
        lambda m: m["outputs"][0]["parts"][0].update(file="2026-Q3-output-main-part-001.xzpart"),
        lambda m: m["outputs"][0]["parts"][0].update(bytes=True),
        lambda m: m["outputs"][0]["parts"].append(m["outputs"][0]["parts"][0]),
    ],
)
def test_closed_manifest_rejections(tmp_path, mutation):
    m, _ = fixture(tmp_path / "parts")
    mutation(m)
    with pytest.raises(ValueError):
        output_manifest(canonical(m), PERIOD, "300661", PRODUCER)


def test_duplicate_fields_noncanonical_and_exact_large_exception(tmp_path):
    m, _ = fixture(tmp_path / "parts")
    raw = canonical(m)
    with pytest.raises(ValueError):
        output_manifest(
            raw.replace(b'"schema":', b'"schema":"duplicate","schema":', 1),
            PERIOD,
            "300661",
            PRODUCER,
        )
    with pytest.raises(ValueError):
        output_manifest(json.dumps(m, indent=2).encode(), PERIOD, "300661", PRODUCER)
    m.update(symbol=LARGE_EXACT[0], producer_sha256=LARGE_EXACT[1])
    m["outputs"][0].update(expanded_bytes=LARGE_EXACT[2], expanded_sha256=LARGE_EXACT[3])
    output_manifest(canonical(m), PERIOD, LARGE_EXACT[0], LARGE_EXACT[1])
    m["outputs"][0]["expanded_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        output_manifest(canonical(m), PERIOD, LARGE_EXACT[0], LARGE_EXACT[1])


@pytest.mark.parametrize(
    "case",
    [
        "missing",
        "symlink",
        "directory",
        "hardlink",
        "bytes",
        "part_hash",
        "whole_hash",
        "expanded_hash",
        "expanded_short",
        "expanded_long",
    ],
)
def test_actual_file_identity_and_all_digest_rejections(tmp_path, case):
    root = tmp_path / "parts"
    m, _ = fixture(root)
    entry = m["outputs"][0]
    path = root / entry["parts"][0]["file"]
    if case == "missing":
        path.unlink()
    elif case == "symlink":
        target = tmp_path / "outside"
        path.replace(target)
        path.symlink_to(target)
    elif case == "directory":
        path.unlink()
        path.mkdir()
    elif case == "hardlink":
        os.link(path, tmp_path / "alias")
    elif case == "bytes":
        path.write_bytes(b"0" * path.stat().st_size)
    elif case == "part_hash":
        entry["parts"][0]["sha256"] = "0" * 64
    elif case == "whole_hash":
        entry["compressed_sha256"] = "0" * 64
    elif case == "expanded_hash":
        entry["expanded_sha256"] = "0" * 64
    elif case == "expanded_short":
        entry["expanded_bytes"] -= 1
    elif case == "expanded_long":
        entry["expanded_bytes"] += 1
    with pytest.raises((ValueError, OSError, lzma.LZMAError)):
        verify(root, m)


@pytest.mark.parametrize("kind", ["truncated", "trailing", "concatenated", "invalid_json"])
def test_full_stream_and_json_not_only_exit_or_hash(tmp_path, kind):
    raw = b'{"all":true}\n' if kind != "invalid_json" else b'{"unfinished":'
    encoded = lzma.compress(raw, preset=0)
    if kind == "truncated":
        encoded = encoded[:-1]
    elif kind == "trailing":
        encoded += b"extra"
    elif kind == "concatenated":
        encoded += encoded
    root = tmp_path / "parts"
    m, _ = fixture(root, [raw], encoded=encoded)
    with pytest.raises((ValueError, lzma.LZMAError)):
        verify(root, m)


def test_real_stream_crosses_part_boundary_and_order_is_fixed(tmp_path):
    raw = canonical({"all": os.urandom(7 * 1024**2).hex()})
    root = tmp_path / "parts"
    m, _ = fixture(root, [raw])
    assert len(m["outputs"][0]["parts"]) == 2
    verify(root, m)
    bad = copy.deepcopy(m)
    bad["outputs"][0]["parts"].reverse()
    with pytest.raises(ValueError):
        output_manifest(canonical(bad), PERIOD, "300661", PRODUCER)


def test_indirect_directory_rejected(tmp_path):
    root = tmp_path / "parts"
    m, _ = fixture(root)
    link = tmp_path / "linked"
    link.symlink_to(root, target_is_directory=True)
    with pytest.raises(ValueError):
        verify(link, m)


@pytest.mark.parametrize("mode", ["single", "eight", "missing", "different"])
def test_actual_isolated_harness_covers_each_required_document(tmp_path, mode):
    import importlib.util

    code = "300661" if mode == "single" else "300015"
    names = ("main",) if mode == "single" else EIGHT_NAMES
    root = tmp_path / code / "models"
    root.parent.mkdir()
    documents = [canonical({"all_years": [1, 2, 3], "name": n}) for n in names]
    m, _ = fixture(root, documents, symbol=code)
    source = "from pathlib import Path\nimport sys\nroot=Path(__file__).parent\n"
    for index, (name, raw) in enumerate(zip(names, documents, strict=True)):
        if mode == "missing" and index == len(names) - 1:
            continue
        file = "2026-Q3-output.json" if mode == "single" else f"2026-Q3-output-{name}.json"
        if mode == "different" and index == len(names) - 1:
            raw = canonical({"wrong": True})
        source += f"(root/{file!r}).write_bytes({raw!r})\n"
    source += "print('all complete outputs are separate files')\n"
    model = root / "2026-Q3.py"
    model.write_text(source)
    m["producer_sha256"] = sha(model.read_bytes())
    (root / "2026-Q3-output.json").write_bytes(canonical(m))
    test_path = Path(__file__).with_name("test_q3_model_reproduction.py")
    spec = importlib.util.spec_from_file_location("actual_q3_harness_fixture", test_path)
    harness = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(harness)
    isolated = tmp_path / "isolated"
    isolated.mkdir()
    if mode in {"missing", "different"}:
        with pytest.raises(AssertionError):
            harness.test_published_q3_model_reproduces_in_isolated_directory(model, isolated)
    else:
        harness.test_published_q3_model_reproduces_in_isolated_directory(model, isolated)
