"""隔离重跑正式Q3模型；公司模型内的手算特例随正式计算链执行。"""

import hashlib
import json
import lzma
import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODELS = sorted((ROOT / "research/companies/CN").glob("*/models/2026-Q3.py"))


def _abort_owned_checker_timeout(error, *, symbol, tmp_path, phase="checker"):
    assert phase in {"producer", "checker"}
    # Keep the checker in the already owned pytest PGID. The outer owner must
    # terminate any surviving nested descendants before admitting more work.
    # Even a record-write failure aborts pytest instead of continuing next node.
    root = Path(os.environ.get("PARTITION_EVIDENCE_DIR", tmp_path))
    prefix = root / (symbol + "-" + phase + "-timeout")
    try:
        for suffix, value in ((".stdout", error.stdout), (".stderr", error.stderr)):
            value = value.encode() if isinstance(value, str) else (value or b"")
            with Path(str(prefix) + suffix).open("xb") as stream:
                stream.write(value)
        with Path(str(prefix) + ".traceback.txt").open("x") as stream:
            stream.write(traceback.format_exc())
        with Path(str(prefix) + ".json").open("x") as stream:
            json.dump({"status": "controlled_" + phase + "_timeout_requires_owner_group_cleanup",
                       "symbol": symbol, "timeout": error.timeout, "argv": error.cmd,
                       "pytest_pid": os.getpid(), "pytest_pgid": os.getpgrp(),
                       "pid_namespace": os.readlink("/proc/self/ns/pid"),
                       "no_next_node_admission": True, "failure_not_success": True}, stream)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        pytest.exit(
            phase.upper() + "_TIMEOUT: owned pytest group cleanup required; " + symbol,
            returncode=2,
        )


def _assert_historical_or_unmigrated_model_reproduction(model, tmp_path):
    # No original artifacts are modified, and no repository working directory is assumed.
    copied = tmp_path / model.name
    shutil.copyfile(model, copied)
    # Amoy's published reader artifact is the documented expanded interface;
    # its default CLI emits an envelope. Generate the exact published form.
    args = ["--expand"] if model.parent.parent.name == "300685" else []
    # Serial measured consumer runtimes: 248.480s and 525.087s respectively.
    # Bounded transport budgets retain every numerical and byte assertion.
    timeout = {"002847": 600, "600309": 1200, "300015": 600}.get(model.parent.parent.name, 240)
    # 300015 eight complete streams: conservative workload budget, not an
    # observed raw-only timeout; no numerical assertion or other budget changes.
    # Keep complete stdout on disk, not in the pytest parent's heap while a
    # separate checker also loads a large complete annual output.
    stdout_path = tmp_path / ".producer-stdout"
    with stdout_path.open("wb") as stdout:
        try:
            result = subprocess.run(
                [sys.executable, str(copied), *args],
                cwd=tmp_path.parent,
                stdout=stdout,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            if model.parent.parent.name != "300015":
                raise
            _abort_owned_checker_timeout(
                error, symbol=model.parent.parent.name, tmp_path=tmp_path, phase="producer"
            )
    assert result.returncode == 0, result.stderr
    output = "2026-Q3-output.json"
    expected_path = model.parent / output
    # Transport descriptors are small and have a closed publication schema;
    # ordinary full JSON is parsed in the isolated semantic comparator below.
    transport = (
        json.loads(expected_path.read_bytes())
        if expected_path.stat().st_size <= 64 * 1024
        else None
    )
    if isinstance(transport, dict) and transport.get("schema") == "trading_os_lossless_json_xz_v1":
        assert transport["artifact_kind"] == "transport_manifest_not_model_result"
        assert transport["file"] == "2026-Q3-output.json.xz"
        assert 0 < transport["compressed_bytes"] <= 100 * 1024**2
        expanded_limit = 512 * 1024**2
        if model.parent.parent.name == "600018":
            # Exact accepted complete output is larger, not a generic limit lift.
            assert hashlib.sha256(model.read_bytes()).hexdigest() == (
                "53c9134dc98943c7222b845e6a503e4910e6c1552606fc2bc7a75d1a7d26d1f7"
            )
            assert transport["expanded_bytes"] == 670121548
            assert transport["expanded_sha256"] == (
                "308f5b98103a609927f18b27e06424545ab09d969f502082274cc9f6196a7959"
            )
            expanded_limit = 670121548
        assert 0 < transport["expanded_bytes"] <= expanded_limit
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
    output_parts = (
        isinstance(transport, dict)
        and transport.get("schema") == "trading_os_lossless_json_xz_parts_v1"
    )
    if output_parts:
        from trading_os.model_output_parts import decode_output, output_manifest
        # Exact same bytes are parsed/validated then used throughout; no second
        # unchecked manifest object controls file paths or document selection.
        manifest_bytes = expected_path.read_bytes()
        manifest = output_manifest(
            manifest_bytes, "2026-Q3", model.parent.parent.name,
            hashlib.sha256(model.read_bytes()).hexdigest(),
        )
        for entry in manifest["outputs"]:
            name = (output if manifest["layout"] == "single_complete_json"
                    else f"2026-Q3-output-{entry['name']}.json")
            actual_path = tmp_path / name
            if manifest["layout"] == "single_complete_json" and not actual_path.exists():
                stdout_path.replace(actual_path)
            assert actual_path.is_file() and not actual_path.is_symlink()
            decoded_path = tmp_path / (".expected-" + entry["name"] + ".json")
            decode_output(model.parent, manifest, entry, decoded_path)
            # One complete JSON parse plus exact whole bytes is stricter than
            # semantic equality, with only one potentially large graph in RAM.
            compared = subprocess.run(
                [sys.executable, "-I", "-S", "-c",
                 "import json,sys,os\n"
                 "json.load(open(sys.argv[2],encoding='utf-8'),"
                 "parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))\n"
                 "assert os.path.getsize(sys.argv[1])==os.path.getsize(sys.argv[2])\n"
                 "with open(sys.argv[1],'rb') as a,open(sys.argv[2],'rb') as b:\n"
                 " while True:\n"
                 "  x=a.read(1024*1024);y=b.read(1024*1024);assert x==y\n"
                 "  if not x:break\n", str(actual_path), str(decoded_path)],
                cwd=tmp_path.parent, capture_output=True, timeout=240, check=False,
            )
            assert compared.returncode == 0, compared.stderr
            decoded_path.unlink()
        # All eight 300015 outputs are separate real JSON documents. The
        # descriptor or stdout progress is not substituted for any of them.
        generated = tmp_path / output
    else:
        # Both public producer interfaces retain exact binary stdout/file bytes.
        generated = tmp_path / output
        if not generated.exists():
            stdout_path.replace(generated)
        else:
            stdout_path.unlink()
        # Preserve the complete JSON semantic equality assertion, in a child which
        # exits before any independent checker starts. No annual data are omitted.
        semantic_script = (
            "import json,sys; "
            "a=json.load(open(sys.argv[1],encoding='utf-8')); "
            "b=json.load(open(sys.argv[2],encoding='utf-8')); assert a==b"
        )
        if model.parent.parent.name == "600018":
            assert isinstance(transport, dict)
            assert transport.get("schema") == "trading_os_lossless_json_xz_v1"
            # Parse the entire expected JSON once, then demand exact full bytes.
            # Valid JSON plus byte identity implies the original semantic equality;
            # no two large object graphs need coexist and no annual state is omitted.
            semantic_script = (
                "import json,sys,os\n"
                "json.load(open(sys.argv[2],encoding='utf-8'))\n"
                "assert os.path.getsize(sys.argv[1]) == os.path.getsize(sys.argv[2])\n"
                "with open(sys.argv[1],'rb') as a, open(sys.argv[2],'rb') as b:\n"
                " while True:\n"
                "  x=a.read(1024*1024); y=b.read(1024*1024)\n"
                "  assert x==y\n"
                "  if not x: break\n"
            )
        semantic = subprocess.run(
            [sys.executable, "-I", "-S", "-c", semantic_script,
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
    if (
        not output_parts
        and model.parent.parent.name in migrated_codes | restored_codes | newly_disclosed_codes
    ):
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
        # Closed verification payload siblings; never arbitrary repository files.
        payload_manifest = model.parent / "2026-Q3-verification-payload.json"
        if verification.name == "2026-Q3-independent-recompute.py" and payload_manifest.exists():
            from trading_os.model_verification_payload import (
                _read_regular,
                verification_manifest,
                verification_payload,
            )
            manifest_bytes = _read_regular(payload_manifest, limit=64 * 1024)
            manifest = verification_manifest(manifest_bytes, "2026-Q3")
            verification_payload(
                model.parent, "2026-Q3", manifest["payload_bytes"], manifest["payload_sha256"],
                manifest_bytes=manifest_bytes,
            )
            with (tmp_path / payload_manifest.name).open("xb") as destination:
                destination.write(manifest_bytes)
            for part in manifest["parts"]:
                with (tmp_path / part["file"]).open("xb") as destination:
                    destination.write(
                        _read_regular(model.parent / part["file"], part["bytes"], 6 * 1024**2)
                    )
            verification_payload(
                tmp_path, "2026-Q3", manifest["payload_bytes"], manifest["payload_sha256"]
            )
        # Complete author/audit/600-1200-year consumer measured 242.270s.
        # Yili complete author + independent consumer measured 295.038s.
        # Runtime budget only; all original economic assertions remain.
        # 300661: conservative complete 10-stage + 4 author-replay wait budget;
        # no historical total-time measurement is claimed.
        # 600298 likewise retains all six full accepted stages and two507MB
        # audit replays;600s is conservative workload budget, not oldtimeout.
        # 600018:11 full stages/670MB producer/485MB independent; conservative
        # 1200s resource wait only, original financial assertions unchanged.
        checker_timeout = (
            1200
            if model.parent.parent.name in {"600018", "300015"}
            else 600
            if model.parent.parent.name
            in {
                "000538", "300760", "600887", "603939", "688188", "688617",
                "600519", "300347", "300661", "600298",
            }
            else 240
        )
        try:
            checked = subprocess.run(
                [sys.executable, str(check_copy)],
                cwd=tmp_path.parent,
                capture_output=True,
                text=True,
                timeout=checker_timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            if model.parent.parent.name not in {
                "603939", "688188", "688617", "600519", "300347",
                "300661", "600298", "600018", "300015",
            }:
                raise
            _abort_owned_checker_timeout(error, symbol=model.parent.parent.name, tmp_path=tmp_path)
        assert checked.returncode == 0, checked.stderr


@pytest.mark.parametrize("model", [path for path in MODELS if path.parent.parent.name != "603605"], ids=lambda path: path.parent.parent.name)
def test_published_q3_model_reproduces_in_isolated_directory(model, tmp_path):
    code = model.parent.parent.name
    if code == "601799":
        from xingyu_null_contract_helpers import assert_null_current
        assert_null_current(ROOT, tmp_path)
    elif code == "002270":
        from huaming_null_contract_helpers import assert_null_current
        assert_null_current(ROOT, tmp_path)
    elif code == "002850":
        from kedali_null_contract_helpers import assert_null_current
        assert_null_current(ROOT, tmp_path)
    else:
        _assert_historical_or_unmigrated_model_reproduction(model, tmp_path)


def test_proya_current_transport_and_metadata(tmp_path):
    from proya_current_contract_helpers import assert_current_transport
    assert_current_transport(ROOT, tmp_path)


def test_proya_current_full_financial_reproduction(tmp_path):
    # Full financial execution is retained separately and was not run for publication.
    from proya_current_contract_helpers import assert_full_financial
    assert_full_financial(ROOT, tmp_path)


def test_xingyu_historical_full_producer_and_checker(tmp_path):
    # Retain the exact original full financial comparison as a distinct history node.
    # This node requires separate full/global execution admission, never sparse metadata qualification.
    from xingyu_null_contract_helpers import historical_root
    historical = historical_root(ROOT, tmp_path)
    run = tmp_path / "historical-financial-run"
    run.mkdir()
    _assert_historical_or_unmigrated_model_reproduction(historical / "2026-Q3.py", run)


def test_huaming_historical_full_producer_and_checker(tmp_path):
    # Separate full historical financial contract; never admitted by current-null qualification.
    from huaming_null_contract_helpers import historical_root
    historical = historical_root(ROOT, tmp_path)
    run = tmp_path / "historical-financial-run"
    run.mkdir()
    _assert_historical_or_unmigrated_model_reproduction(historical / "2026-Q3.py", run)


def test_kedali_historical_full_producer(tmp_path):
    # Full historical production comparison, outside current-null qualification.
    # There was no original independent checker or method file for this company.
    from kedali_null_contract_helpers import historical_root
    historical = historical_root(ROOT, tmp_path)
    run = tmp_path / "historical-financial-run"
    run.mkdir()
    _assert_historical_or_unmigrated_model_reproduction(historical / "2026-Q3.py", run)
