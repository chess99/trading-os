from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from tests.test_manager_screen_allocation_v3 import (
    FROZEN_AT,
    RUN_ID,
    _freeze,
    _manager,
    _repository,
)
from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl

SUSPENDED_AT = FROZEN_AT + dt.timedelta(minutes=10)


def _ready_repository(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    root, _ = _repository(tmp_path, monkeypatch)
    queue_path = root / "research_queue.jsonl"
    queue = read_jsonl(queue_path)
    screens = []
    for row in queue:
        symbol = row["symbol"]
        ticker = symbol.split(":", 1)[1]
        row.update(
            {
                "name": f"测试公司{ticker}",
                "priority": 3,
                "reason": f"保留 {symbol} 的原始研究理由。",
                "target_company_dir": f"research/companies/CN/{ticker}",
                "next_action": "交给研究员回答决定性问题。",
                "decisive_question": f"{symbol} 的决定性问题是什么？",
                "evidence_ids": [f"snapshot:{symbol}"],
                "effort_budget_hours": 1.5,
                "stop_conditions": ["公开证据无法回答决定性问题"],
            }
        )
        screens.append(
            {
                "symbol": symbol,
                "name": row["name"],
                "decision": "quick_profile",
                "priority": None,
                "reason": row["reason"],
                "evidence": list(row["evidence_ids"]),
                "next_action": row["next_action"],
                "manager_screen_run_id": RUN_ID,
                "manager_screen_route": row["manager_screen_route"],
                "manager_screen_result_path": row["manager_screen_result_path"],
                "manager_screen_result_sha256": row["manager_screen_result_sha256"],
                "decisive_question": row["decisive_question"],
                "confidence": "medium",
            }
        )
    write_jsonl(queue_path, queue)
    write_jsonl(root / "screening.jsonl", screens)
    _freeze(root)
    return root


def _suspend(root: Path, **changes):
    from trading_os.research_assets.manager_screen_allocation_v3_suspension import (
        suspend_manager_screen_allocation_v3_revocable_commitments,
    )

    arguments = {
        "root": root,
        "run_id": RUN_ID,
        "manager": _manager(),
        "reason": "Suspend only pristine commitments and compare the complete scope.",
        "suspended_at": SUSPENDED_AT,
    }
    arguments.update(changes)
    return suspend_manager_screen_allocation_v3_revocable_commitments(**arguments)


def _by_symbol(path: Path) -> dict[str, dict]:
    return {row["symbol"]: row for row in read_jsonl(path)}


def test_suspension_seals_all_revocable_rows_then_materializes_candidate_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_os.research_assets.coverage_store import list_screening
    from trading_os.research_assets.manager_screen_allocation_v3_suspension import (
        verify_manager_screen_allocation_v3_suspension,
    )

    root = _ready_repository(tmp_path, monkeypatch)
    queue_before = _by_symbol(root / "research_queue.jsonl")
    screens_before = _by_symbol(root / "screening.jsonl")
    original_route = queue_before["CN:000001"]["manager_screen_route"]
    original_result = queue_before["CN:000001"]["manager_screen_result_path"]
    original_result_sha256 = queue_before["CN:000001"]["manager_screen_result_sha256"]

    result = _suspend(root)
    verified = verify_manager_screen_allocation_v3_suspension(root=root, run_id=RUN_ID)

    assert result["suspended_commitment_count"] == 196
    assert result["idempotent"] is False
    assert result["materialization"]["fully_materialized"] is True
    assert verified["materialization"]["queue_materialized_count"] == 196
    assert verified["materialization"]["screening_materialized_count"] == 196

    queue = _by_symbol(root / "research_queue.jsonl")["CN:000001"]
    assert queue["manager_screen_route"] == original_route
    assert queue["manager_screen_result_path"] == original_result
    assert queue["manager_screen_result_sha256"] == original_result_sha256
    assert queue["task_type"] == "manager_screen"
    assert queue["status"] == "completed"
    assert queue["research_budget_state"] == "candidate_unfunded"
    assert queue["result_path"] == original_result
    assert queue["stage_history"][-1]["stage"] == ("manager_screen_allocation_v3_suspension")
    assert queue["stage_history"][-1]["action"] == "suspend_unclaimed_purchase"
    for removed in (
        "allocation_sha256",
        "effort_budget_hours",
        "preceding_stage",
        "stop_conditions",
    ):
        assert removed not in queue

    screen = _by_symbol(root / "screening.jsonl")["CN:000001"]
    assert screen["decision"] == "candidate_unfunded"
    assert screen["state"] == "candidate_unfunded"
    assert screen["research_budget_state"] == "candidate_unfunded"
    assert screen["reason"] == screens_before["CN:000001"]["reason"]
    assert screen["evidence"] == screens_before["CN:000001"]["evidence"]
    assert screen["manager_screen_route"] == original_route
    assert screen["manager_screen_result_path"] == original_result
    assert list_screening(root, decision="candidate_unfunded")


def test_noncritical_screening_display_changes_do_not_revoke_eligibility(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _ready_repository(tmp_path, monkeypatch)
    screens = _by_symbol(root / "screening.jsonl")
    screens["CN:000001"].update(
        {
            "name": "更新后的展示名称",
            "priority": 5,
            "reason": "更新后的展示理由仍保留。",
            "next_action": "更新后的展示动作。",
            "confidence": "low",
        }
    )
    write_jsonl(root / "screening.jsonl", list(screens.values()))

    _suspend(root)

    materialized = _by_symbol(root / "screening.jsonl")["CN:000001"]
    assert materialized["name"] == "更新后的展示名称"
    assert materialized["reason"] == "更新后的展示理由仍保留。"
    assert materialized["confidence"] == "low"
    assert materialized["decision"] == "candidate_unfunded"


@pytest.mark.parametrize(
    "changes",
    [
        {
            "status": "running",
            "assigned_agent": "/root/claimed",
            "started_at": SUSPENDED_AT.isoformat(),
        },
        {
            "status": "failed",
            "finished_at": SUSPENDED_AT.isoformat(),
            "failure_reason": "prior attempt failed",
        },
        {"assigned_agent": "/root/claimed-but-not-started"},
        {
            "attempt_history": [
                {
                    "agent": "/root/attempted",
                    "started_at": SUSPENDED_AT.isoformat(),
                }
            ]
        },
        {"result_path": "coverage/cn-a/profiles/unsealed-result.json"},
    ],
)
def test_running_failed_or_result_pointer_drift_fails_the_whole_suspension(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    changes: dict[str, object],
) -> None:
    from trading_os.research_assets.manager_screen_allocation_v3_suspension import (
        SUSPENSION_RELATIVE_PATH,
        ManagerScreenAllocationV3SuspensionError,
    )

    root = _ready_repository(tmp_path, monkeypatch)
    queue = _by_symbol(root / "research_queue.jsonl")
    untouched = dict(queue["CN:000006"])
    queue["CN:000001"].update(changes)
    write_jsonl(root / "research_queue.jsonl", list(queue.values()))

    with pytest.raises(ManagerScreenAllocationV3SuspensionError, match="no commitment"):
        _suspend(root)

    assert _by_symbol(root / "research_queue.jsonl")["CN:000006"] == untouched
    suspension_path = root / "manager-screen" / RUN_ID / SUSPENSION_RELATIVE_PATH
    assert not suspension_path.exists()
    assert not suspension_path.with_name(f"{suspension_path.name}.seal.json").exists()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("manager_screen_route", "watch"),
        ("decisive_question", "被改写的问题"),
        ("evidence", ["snapshot:CN:999999"]),
        ("manager_screen_result_sha256", "f" * 64),
    ],
)
def test_critical_screening_binding_drift_fails_before_sealing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
) -> None:
    from trading_os.research_assets.manager_screen_allocation_v3_suspension import (
        SUSPENSION_RELATIVE_PATH,
        ManagerScreenAllocationV3SuspensionError,
    )

    root = _ready_repository(tmp_path, monkeypatch)
    screens = _by_symbol(root / "screening.jsonl")
    screens["CN:000001"][field] = value
    write_jsonl(root / "screening.jsonl", list(screens.values()))

    with pytest.raises(ManagerScreenAllocationV3SuspensionError, match="binding drifted"):
        _suspend(root)

    assert not (root / "manager-screen" / RUN_ID / SUSPENSION_RELATIVE_PATH).exists()


@pytest.mark.parametrize("partial", ["artifact", "manifest"])
def test_partial_suspension_seal_is_rejected_without_overwrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    partial: str,
) -> None:
    from trading_os.research_assets.manager_screen_allocation_v3_suspension import (
        SUSPENSION_RELATIVE_PATH,
        ManagerScreenAllocationV3SuspensionError,
    )

    root = _ready_repository(tmp_path, monkeypatch)
    path = root / "manager-screen" / RUN_ID / SUSPENSION_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    partial_path = path if partial == "artifact" else path.with_name(f"{path.name}.seal.json")
    partial_path.write_text("{}", encoding="utf-8")

    with pytest.raises(ManagerScreenAllocationV3SuspensionError, match="partially sealed"):
        _suspend(root)
    assert partial_path.read_text(encoding="utf-8") == "{}"


def test_contract_or_suspension_tamper_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_os.research_assets.manager_screen_allocation_v3 import (
        CONTRACT_RELATIVE_PATH,
    )
    from trading_os.research_assets.manager_screen_allocation_v3_suspension import (
        SUSPENSION_RELATIVE_PATH,
        ManagerScreenAllocationV3SuspensionError,
        verify_manager_screen_allocation_v3_suspension,
    )

    contract_root = _ready_repository(tmp_path / "contract", monkeypatch)
    contract_path = contract_root / "manager-screen" / RUN_ID / CONTRACT_RELATIVE_PATH
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["reason"] = "tampered"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    with pytest.raises(ManagerScreenAllocationV3SuspensionError, match="contract is invalid"):
        _suspend(contract_root)

    suspension_root = _ready_repository(tmp_path / "suspension", monkeypatch)
    _suspend(suspension_root)
    suspension_path = suspension_root / "manager-screen" / RUN_ID / SUSPENSION_RELATIVE_PATH
    suspension = json.loads(suspension_path.read_text(encoding="utf-8"))
    suspension["reason"] = "tampered"
    suspension_path.write_text(json.dumps(suspension), encoding="utf-8")
    with pytest.raises(ManagerScreenAllocationV3SuspensionError, match="suspension is invalid"):
        verify_manager_screen_allocation_v3_suspension(
            root=suspension_root,
            run_id=RUN_ID,
        )


def test_identical_replay_recovers_crash_between_queue_and_screening_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_os.research_assets.manager_screen_allocation_v3_suspension as suspension

    root = _ready_repository(tmp_path, monkeypatch)
    real_write_jsonl = suspension.write_jsonl
    call_count = 0

    def interrupt_second_write(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise OSError("simulated crash before screening projection")
        return real_write_jsonl(*args, **kwargs)

    monkeypatch.setattr(suspension, "write_jsonl", interrupt_second_write)
    with pytest.raises(OSError, match="simulated crash"):
        _suspend(root)

    queue = _by_symbol(root / "research_queue.jsonl")["CN:000001"]
    screen = _by_symbol(root / "screening.jsonl")["CN:000001"]
    assert queue["research_budget_state"] == "candidate_unfunded"
    assert screen["decision"] == "quick_profile"

    monkeypatch.setattr(suspension, "write_jsonl", real_write_jsonl)
    recovered = _suspend(root)
    replay = _suspend(root)

    assert recovered["idempotent"] is True
    assert recovered["materialization"]["queue_repaired_count"] == 0
    assert recovered["materialization"]["screening_repaired_count"] == 196
    assert replay["idempotent"] is True
    assert replay["materialization"]["queue_repaired_count"] == 0
    assert replay["materialization"]["screening_repaired_count"] == 0


def test_materialized_row_tamper_and_conflicting_replay_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_os.research_assets.manager_screen_allocation_v3_suspension import (
        ManagerScreenAllocationV3SuspensionError,
    )

    root = _ready_repository(tmp_path, monkeypatch)
    _suspend(root)

    with pytest.raises(ManagerScreenAllocationV3SuspensionError, match="conflicts"):
        _suspend(root, reason="A conflicting suspension reason.")

    queue = _by_symbol(root / "research_queue.jsonl")
    queue["CN:000001"]["reason"] = "post-suspension tamper"
    write_jsonl(root / "research_queue.jsonl", list(queue.values()))
    before = _by_symbol(root / "screening.jsonl")["CN:000006"]
    with pytest.raises(ManagerScreenAllocationV3SuspensionError, match="refusing all writes"):
        _suspend(root)
    assert _by_symbol(root / "screening.jsonl")["CN:000006"] == before
