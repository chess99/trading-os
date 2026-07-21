from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path

import pytest

SEALED_AT = dt.datetime(2026, 7, 21, 8, 0, tzinfo=dt.timezone.utc)


def test_canonical_json_is_stable_across_mapping_order():
    from trading_os.research_assets.sealing import canonical_json_bytes

    left = {"中文": [3, 2, 1], "a": {"y": 2, "x": 1}}
    right = {"a": {"x": 1, "y": 2}, "中文": [3, 2, 1]}

    assert canonical_json_bytes(left) == canonical_json_bytes(right)
    assert canonical_json_bytes(left).decode("utf-8") == (
        '{"a":{"x":1,"y":2},"中文":[3,2,1]}'
    )


def test_canonical_json_rejects_non_finite_numbers():
    from trading_os.research_assets.sealing import SealingError, canonical_json_bytes

    with pytest.raises(SealingError, match="canonical JSON"):
        canonical_json_bytes({"value": float("nan")})


def test_seal_json_writes_artifact_and_verifiable_manifest(tmp_path: Path):
    from trading_os.research_assets.sealing import seal_json, verify_sealed

    path = tmp_path / "blind_assessment.json"
    sealed = seal_json(
        path,
        {"schema_version": 2, "result": "independent"},
        artifact_type="blind_assessment",
        sealed_at=SEALED_AT,
    )

    expected = path.read_bytes()
    assert sealed.path == path
    assert sealed.sha256 == hashlib.sha256(expected).hexdigest()
    assert sealed.size == len(expected)
    assert sealed.artifact_type == "blind_assessment"
    assert sealed.sealed_at == SEALED_AT
    assert sealed.manifest_path == path.with_name(path.name + ".seal.json")
    assert verify_sealed(path) == sealed


def test_sealing_the_same_content_is_idempotent(tmp_path: Path):
    from trading_os.research_assets.sealing import seal_json

    path = tmp_path / "claim_packet.json"
    first = seal_json(
        path,
        {"schema_version": 2, "claims": ["C1"]},
        artifact_type="claim_packet",
        sealed_at=SEALED_AT,
    )
    first_manifest = first.manifest_path.read_bytes()

    second = seal_json(
        path,
        {"claims": ["C1"], "schema_version": 2},
        artifact_type="claim_packet",
        sealed_at=SEALED_AT + dt.timedelta(hours=1),
    )

    assert second == first
    assert second.manifest_path.read_bytes() == first_manifest


def test_sealing_different_content_over_existing_artifact_fails(tmp_path: Path):
    from trading_os.research_assets.sealing import SealingError, seal_json

    path = tmp_path / "blind_assessment.json"
    seal_json(
        path,
        {"result": "first"},
        artifact_type="blind_assessment",
        sealed_at=SEALED_AT,
    )

    with pytest.raises(SealingError, match="immutable"):
        seal_json(
            path,
            {"result": "changed after reveal"},
            artifact_type="blind_assessment",
            sealed_at=SEALED_AT,
        )


@pytest.mark.parametrize("tamper_target", ["artifact", "manifest"])
def test_verify_sealed_detects_any_tampering(tmp_path: Path, tamper_target: str):
    from trading_os.research_assets.sealing import SealingError, seal_json, verify_sealed

    path = tmp_path / "blind_assessment.json"
    sealed = seal_json(
        path,
        {"result": "original"},
        artifact_type="blind_assessment",
        sealed_at=SEALED_AT,
    )
    target = path if tamper_target == "artifact" else sealed.manifest_path
    target.write_bytes(target.read_bytes() + b" ")

    with pytest.raises(SealingError):
        verify_sealed(path)


def test_resume_can_finish_manifest_after_artifact_only_crash(tmp_path: Path):
    from trading_os.research_assets.sealing import canonical_json_bytes, seal_json

    path = tmp_path / "blind_assessment.json"
    path.write_bytes(canonical_json_bytes({"result": "already-written"}))

    sealed = seal_json(
        path,
        {"result": "already-written"},
        artifact_type="blind_assessment",
        sealed_at=SEALED_AT,
    )

    assert sealed.manifest_path.is_file()


def test_existing_unsealed_different_artifact_is_not_overwritten(tmp_path: Path):
    from trading_os.research_assets.sealing import SealingError, seal_json

    path = tmp_path / "blind_assessment.json"
    path.write_text('{"result":"unknown-origin"}', encoding="utf-8")

    with pytest.raises(SealingError, match="unsealed artifact"):
        seal_json(
            path,
            {"result": "new"},
            artifact_type="blind_assessment",
            sealed_at=SEALED_AT,
        )


def test_atomic_write_does_not_leave_target_or_temp_file_when_replace_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from trading_os.research_assets.sealing import atomic_write_bytes

    path = tmp_path / "state.json"

    def fail_replace(_source: str | os.PathLike[str], _target: str | os.PathLike[str]):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(os, "replace", fail_replace)

    with pytest.raises(OSError, match="simulated"):
        atomic_write_bytes(path, b'{"state":"new"}')

    assert not path.exists()
    assert list(tmp_path.iterdir()) == []


def test_sealed_at_requires_timezone(tmp_path: Path):
    from trading_os.research_assets.sealing import SealingError, seal_json

    with pytest.raises(SealingError, match="timezone"):
        seal_json(
            tmp_path / "artifact.json",
            {"ok": True},
            artifact_type="test",
            sealed_at=dt.datetime(2026, 7, 21, 8, 0),
        )


def test_manifest_has_only_auditable_fields(tmp_path: Path):
    from trading_os.research_assets.sealing import seal_json

    sealed = seal_json(
        tmp_path / "artifact.json",
        {"ok": True},
        artifact_type="test",
        sealed_at=SEALED_AT,
    )
    manifest = json.loads(sealed.manifest_path.read_text(encoding="utf-8"))

    assert set(manifest) == {
        "schema_version",
        "artifact",
        "artifact_type",
        "sha256",
        "size",
        "sealed_at",
    }
