from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

RUN_ID = "manager-run"
SEALED_AT = dt.datetime.fromisoformat("2026-07-31T10:00:00+08:00")


def _mock_allocation_v3_contract(
    repository_root: Path,
    *,
    monkeypatch: pytest.MonkeyPatch,
    classifications: list[dict],
) -> tuple[Path, dict]:
    from trading_os.research_assets import manager_screen_allocation_v3
    from trading_os.research_assets.sealing import seal_json

    contract_path = (
        repository_root
        / "coverage"
        / "cn-a"
        / "manager-screen"
        / RUN_ID
        / "governance"
        / "allocation-v3"
        / "contract.json"
    )
    payload = {
        "run_id": RUN_ID,
        "commitment_classification": classifications,
    }
    seal_json(
        contract_path,
        payload,
        artifact_type="manager_screen_allocation_v3_contract",
        sealed_at=SEALED_AT,
    )
    monkeypatch.setattr(
        manager_screen_allocation_v3,
        "verify_manager_screen_allocation_v3_contract",
        lambda **_: payload,
    )
    return contract_path, payload


def _classification(
    symbol: str,
    *stages: str,
    commitment_class: str = "irreversible",
) -> dict:
    return {
        "symbol": symbol,
        "commitment_class": commitment_class,
        "sealed_progress": [{"research_stage": stage} for stage in stages],
    }


def test_inherited_stage_evidence_uses_conservative_high_watermarks() -> None:
    from trading_os.research_assets.profile_workflow import (
        _sealed_stage_evidence_proves,
    )

    assert _sealed_stage_evidence_proves({"targeted_followup"}, stage="targeted_followup")
    assert not _sealed_stage_evidence_proves(
        {"scoped_research", "deep_research"}, stage="targeted_followup"
    )
    assert _sealed_stage_evidence_proves({"scoped_research"}, stage="scoped_research")
    assert _sealed_stage_evidence_proves({"deep_research"}, stage="scoped_research")
    assert _sealed_stage_evidence_proves({"deep_research"}, stage="deep_research")
    assert not _sealed_stage_evidence_proves({"scoped_research"}, stage="deep_research")


def test_ledgers_merge_modern_and_migration_evidence_without_double_counting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_os.research_assets.profile_workflow as workflow
    from tests.test_profile_workflow import (
        RECORDED_AT,
        _manager_bound_followup_candidate,
        _policy,
        _seal_run_bound_stage_selection,
    )
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl

    coverage_root = _manager_bound_followup_candidate(tmp_path)
    approved = workflow.approve_targeted_followup(
        root=coverage_root,
        symbol="CN:600519",
        manager="/root/original-manager",
        reason="Explicitly purchase one decisive evidence follow-up.",
        policy=_policy(),
        approved_at=RECORDED_AT + dt.timedelta(seconds=30),
    )
    selection_path = _seal_run_bound_stage_selection(
        tmp_path,
        cycle_id="modern-cycle",
        manager_screen_run_id=RUN_ID,
        evaluated_stage="quick_profile",
        next_stage="scoped_research",
        symbol="CN:600519",
    )

    queue_path = coverage_root / "research_queue.jsonl"
    queue = read_jsonl(queue_path)
    queue.append(
        {
            "symbol": "CN:009999",
            "task_type": "deep_research",
            "status": "completed",
            "manager_screen_run_id": RUN_ID,
        }
    )
    write_jsonl(queue_path, queue)

    _mock_allocation_v3_contract(
        tmp_path,
        monkeypatch=monkeypatch,
        classifications=[
            _classification("CN:600519", "targeted_followup", "scoped_research"),
            _classification("CN:000002", "deep_research"),
            _classification("CN:000003", "targeted_followup", "targeted_followup"),
            _classification("CN:002839", commitment_class="revocable"),
        ],
    )

    targeted = workflow._targeted_followup_approval_ledger(
        base=coverage_root,
        repository_root=tmp_path,
        manager_screen_run_id=RUN_ID,
    )
    scoped = workflow._sealed_stage_commitment_ledger(
        base=coverage_root,
        repository_root=tmp_path,
        manager_screen_run_id=RUN_ID,
        next_stage="scoped_research",
    )
    deep = workflow._sealed_stage_commitment_ledger(
        base=coverage_root,
        repository_root=tmp_path,
        manager_screen_run_id=RUN_ID,
        next_stage="deep_research",
    )

    assert set(targeted) == {"CN:600519", "CN:000003"}
    assert targeted["CN:600519"] == {
        "path": (tmp_path / approved["approval_path"]).resolve(),
        "sha256": approved["approval_sha256"],
    }
    assert set(scoped) == {"CN:600519", "CN:000002"}
    assert scoped["CN:600519"]["selection_path"] == (
        selection_path.relative_to(tmp_path).as_posix()
    )
    assert set(deep) == {"CN:000002"}
    assert "CN:002839" not in targeted | scoped | deep
    assert "CN:009999" not in targeted | scoped | deep


def test_recorded_legacy_transition_conserves_exact_and_high_watermark_stages(
    tmp_path: Path,
) -> None:
    import trading_os.research_assets.profile_workflow as workflow
    from tests.test_legacy_transition import (
        FROZEN_AT,
        RECORDED_AT,
        _profile_pair,
        _submission,
        _transition_fixture,
    )
    from tests.test_legacy_transition import (
        RUN_ID as LEGACY_RUN_ID,
    )
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.legacy_transition import (
        freeze_legacy_transition,
        record_legacy_transition,
    )

    fixture = _transition_fixture(tmp_path)
    targeted_pair = _profile_pair(
        fixture["repository_root"],
        symbol=fixture["symbols"]["direct"],
        cycle="targeted-cycle",
        stamp="direct-targeted",
        stage="targeted_followup",
    )
    queue_path = fixture["coverage_root"] / "research_queue.jsonl"
    queue = read_jsonl(queue_path)
    direct = next(item for item in queue if item["symbol"] == fixture["symbols"]["direct"])
    direct.update(
        {
            "task_type": "targeted_followup",
            "status": "completed",
            "profile_cycle_id": "targeted-cycle",
            "result_path": targeted_pair[2],
        }
    )
    direct["stage_history"].append(
        {
            "stage": "targeted_followup",
            "status": "completed",
            "result_path": targeted_pair[0],
            "evaluation_path": targeted_pair[2],
            "finished_at": "2026-07-31T07:50:00+08:00",
        }
    )
    write_jsonl(queue_path, queue)

    freeze_legacy_transition(
        root=fixture["coverage_root"],
        run_id=LEGACY_RUN_ID,
        classification=fixture["classification"],
        frozen_at=FROZEN_AT,
    )
    record_legacy_transition(
        root=fixture["coverage_root"],
        run_id=LEGACY_RUN_ID,
        submission=_submission(fixture["symbols"]),
        recorded_at=RECORDED_AT,
    )
    write_jsonl(queue_path, [])

    targeted = workflow._targeted_followup_approval_ledger(
        base=fixture["coverage_root"],
        repository_root=fixture["repository_root"],
        manager_screen_run_id=LEGACY_RUN_ID,
    )
    scoped = workflow._sealed_stage_commitment_ledger(
        base=fixture["coverage_root"],
        repository_root=fixture["repository_root"],
        manager_screen_run_id=LEGACY_RUN_ID,
        next_stage="scoped_research",
    )
    deep = workflow._sealed_stage_commitment_ledger(
        base=fixture["coverage_root"],
        repository_root=fixture["repository_root"],
        manager_screen_run_id=LEGACY_RUN_ID,
        next_stage="deep_research",
    )

    assert set(targeted) == {fixture["symbols"]["direct"]}
    assert set(scoped) == {
        fixture["symbols"]["direct"],
        fixture["symbols"]["bridge"],
    }
    assert set(deep) == {fixture["symbols"]["bridge"]}


def test_inherited_ledger_rejects_tampered_legacy_result(tmp_path: Path) -> None:
    import trading_os.research_assets.profile_workflow as workflow
    from tests.test_legacy_transition import (
        FROZEN_AT,
        RECORDED_AT,
        _submission,
        _transition_fixture,
    )
    from tests.test_legacy_transition import (
        RUN_ID as LEGACY_RUN_ID,
    )
    from trading_os.research_assets.legacy_transition import (
        freeze_legacy_transition,
        record_legacy_transition,
    )
    from trading_os.research_assets.research_allocation import ResearchAllocationError

    fixture = _transition_fixture(tmp_path)
    freeze_legacy_transition(
        root=fixture["coverage_root"],
        run_id=LEGACY_RUN_ID,
        classification=fixture["classification"],
        frozen_at=FROZEN_AT,
    )
    record_legacy_transition(
        root=fixture["coverage_root"],
        run_id=LEGACY_RUN_ID,
        submission=_submission(fixture["symbols"]),
        recorded_at=RECORDED_AT,
    )
    result_path = (
        fixture["coverage_root"]
        / "manager-screen"
        / LEGACY_RUN_ID
        / "legacy-transition-001"
        / "result.json"
    )
    result_path.write_text(
        result_path.read_text(encoding="utf-8") + " ",
        encoding="utf-8",
    )

    with pytest.raises(ResearchAllocationError, match="invalid legacy transition"):
        workflow._sealed_stage_commitment_ledger(
            base=fixture["coverage_root"],
            repository_root=fixture["repository_root"],
            manager_screen_run_id=LEGACY_RUN_ID,
            next_stage="scoped_research",
        )


def test_inherited_ledger_rejects_tampered_allocation_v3_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_os.research_assets.profile_workflow as workflow
    from trading_os.research_assets.research_allocation import ResearchAllocationError

    contract_path, _ = _mock_allocation_v3_contract(
        tmp_path,
        monkeypatch=monkeypatch,
        classifications=[_classification("CN:000001", "scoped_research")],
    )
    payload = json.loads(contract_path.read_text(encoding="utf-8"))
    payload["commitment_classification"][0]["symbol"] = "CN:000002"
    contract_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ResearchAllocationError, match="invalid allocation-v3 contract"):
        workflow._sealed_stage_commitment_ledger(
            base=tmp_path / "coverage" / "cn-a",
            repository_root=tmp_path,
            manager_screen_run_id=RUN_ID,
            next_stage="scoped_research",
        )
