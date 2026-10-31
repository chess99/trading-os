"""隔离重跑正式Q3模型；公司模型内的手算特例随正式计算链执行。"""

import hashlib
import json
import lzma
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODELS = sorted((ROOT / "research/companies/CN").glob("*/models/2026-Q3.py"))


@pytest.mark.parametrize("model", MODELS, ids=lambda path: path.parent.parent.name)
def test_published_q3_model_reproduces_in_isolated_directory(model, tmp_path):
    # No original artifacts are modified, and no repository working directory is assumed.
    copied = tmp_path / model.name
    shutil.copyfile(model, copied)
    # Amoy's published reader artifact is the documented expanded interface;
    # its default CLI emits an envelope. Generate the exact published form.
    args = ["--expand"] if model.parent.parent.name == "300685" else []
    # Serial measured consumer runtimes: 248.480s and 525.087s respectively.
    # Bounded transport budgets retain every numerical and byte assertion.
    timeout = {"002847": 600, "600309": 1200}.get(model.parent.parent.name, 240)
    # Keep complete stdout on disk, not in the pytest parent's heap while a
    # separate checker also loads a large complete annual output.
    stdout_path = tmp_path / ".producer-stdout"
    with stdout_path.open("wb") as stdout:
        result = subprocess.run(
            [sys.executable, str(copied), *args],
            cwd=tmp_path.parent,
            stdout=stdout,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    assert result.returncode == 0, result.stderr
    output = "2026-Q3-output.json"
    expected_path = model.parent / output
    # Transport descriptors are small and have a closed publication schema;
    # ordinary full JSON is parsed in the isolated semantic comparator below.
    transport = (
        json.loads(expected_path.read_bytes())
        if expected_path.stat().st_size <= 4096
        else None
    )
    if isinstance(transport, dict) and transport.get("schema") == "trading_os_lossless_json_xz_v1":
        assert transport["artifact_kind"] == "transport_manifest_not_model_result"
        assert transport["file"] == "2026-Q3-output.json.xz"
        assert 0 < transport["compressed_bytes"] <= 100 * 1024**2
        assert 0 < transport["expanded_bytes"] <= 512 * 1024**2
        compressed_path = model.parent / transport["file"]
        assert compressed_path.is_file() and not compressed_path.is_symlink()
        expected_path = tmp_path / ".expected-full-json"
        encoded_hash, decoded_hash = hashlib.sha256(), hashlib.sha256()
        encoded_size = decoded_size = 0
        decoder = lzma.LZMADecompressor(format=lzma.FORMAT_XZ, memlimit=256 * 1024**2)
        with compressed_path.open("rb") as encoded, expected_path.open("wb") as decoded:
            while chunk := encoded.read(64 * 1024):
                assert not decoder.eof
                encoded_size += len(chunk)
                assert encoded_size <= transport["compressed_bytes"]
                encoded_hash.update(chunk)
                data = chunk
                while True:
                    part = decoder.decompress(data, max_length=1024 * 1024)
                    data = b""
                    decoded_size += len(part)
                    assert decoded_size <= transport["expanded_bytes"]
                    decoded_hash.update(part)
                    decoded.write(part)
                    if decoder.needs_input or decoder.eof:
                        break
                assert not decoder.unused_data
        assert decoder.eof and not decoder.unused_data
        assert encoded_size == transport["compressed_bytes"]
        assert encoded_hash.hexdigest() == transport["compressed_sha256"]
        assert decoded_size == transport["expanded_bytes"]
        assert decoded_hash.hexdigest() == transport["expanded_sha256"]
        del decoder
    # Both public producer interfaces retain exact binary stdout/file bytes.
    generated = tmp_path / output
    if not generated.exists():
        stdout_path.replace(generated)
    else:
        stdout_path.unlink()
    # Preserve the complete JSON semantic equality assertion, in a child which
    # exits before any independent checker starts. No annual data are omitted.
    semantic = subprocess.run(
        [sys.executable, "-I", "-S", "-c",
         "import json,sys; "
         "a=json.load(open(sys.argv[1],encoding='utf-8')); "
         "b=json.load(open(sys.argv[2],encoding='utf-8')); assert a==b",
         str(generated), str(expected_path)],
        cwd=tmp_path.parent,
        capture_output=True,
        timeout=240,
        check=False,
    )
    assert semantic.returncode == 0, semantic.stderr

    # Every published sibling case is part of the public transport contract.
    # In particular 300033 has 54 case JSON files, not merely its small index.
    cases = sorted(model.parent.glob("2026-Q3-case-*.json"))
    if model.parent.parent.name == "300033":
        assert len(cases) == 54
    for case in cases:
        assert (tmp_path / case.name).is_file(), case.name
        assert (tmp_path / case.name).read_bytes() == case.read_bytes(), case.name
    # Corrected single-file producers promise exact deterministic main bytes.
    migrated = json.loads((ROOT / "tests/q3-final-test-migration.json").read_text())
    restored_codes = {
        "600276",
        "603298",
        "688111",
        "000729",
        "000858",
        "000895",
        "002027",
        "301498",
        "603816",
        "300529",
        "300832",
        "688578",
        "002001",
        "002463",
        "300596",
        "301696",
        "603197",
        "688300",
        "600377",
        "600926",
        "601985",
        "603568",
    }
    newly_disclosed_codes = {
        "603939",
        "688188",
        "001965",
        "000596",
        "000538",
        "002142",
        "000568",
        "920982",
        "300979",
        "300487",
        "600761",
        "688271",
        "688581",
        "601009",
        "300573",
        "002595",
        "003816",
        "600585",
        "601799",
        "600809",
        "601601",
        "601318",
        "300408",
        "603855",
        "002050",
        "600600",
        "603501",
        "601091",
        "603345",
        "002422",
        "300705",
        "300394",
        "300896",
        "603606",
        "688617",
        "603871",
        "601838",
        "600886",
        "600406",
    }
    migrated_codes = {entry["code"] for entry in migrated["companies"]}
    if model.parent.parent.name in migrated_codes | restored_codes | newly_disclosed_codes:
        assert generated.stat().st_size == expected_path.stat().st_size
        with generated.open("rb") as actual, expected_path.open("rb") as expected:
            while block := actual.read(1024 * 1024):
                assert block == expected.read(len(block))
            assert expected.read(1) == b""
    # The full expected file is no longer needed after semantic/byte checks.
    if expected_path.parent == tmp_path:
        expected_path.unlink()

    # Checkers consume only files recreated in the isolated consumer directory.
    verifications = set(model.parent.glob("2026-Q3*verification.py"))
    verifications.update(model.parent.glob("2026-Q3-independent-recompute.py"))
    for verification in sorted(verifications):
        check_copy = tmp_path / verification.name
        shutil.copyfile(verification, check_copy)
        # Complete author/audit/600-1200-year consumer measured 242.270s.
        checker_timeout = 600 if model.parent.parent.name == "000538" else 240
        checked = subprocess.run(
            [sys.executable, str(check_copy)],
            cwd=tmp_path.parent,
            capture_output=True,
            text=True,
            timeout=checker_timeout,
            check=False,
        )
        assert checked.returncode == 0, checked.stderr
