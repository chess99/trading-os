from __future__ import annotations

import datetime as dt
import json
from collections import Counter
from pathlib import Path

import pytest

from trading_os.research_assets.sealing import seal_json

RUN_ID = "2026-07-31-all-a-continuous-001"
CUTOFF = dt.datetime(2026, 7, 31, 4, 31, 33, tzinfo=dt.timezone(dt.timedelta(hours=8)))
RESULT_AT = CUTOFF + dt.timedelta(hours=1)
OVERLAY_AT = RESULT_AT + dt.timedelta(minutes=10)
PROFILE_AT = OVERLAY_AT + dt.timedelta(minutes=10)
PAUSED_AT = PROFILE_AT + dt.timedelta(minutes=10)
FROZEN_AT = PAUSED_AT + dt.timedelta(minutes=10)


def _manager() -> dict[str, object]:
    return {
        "agent": "/root",
        "model": "gpt-test",
        "tools": ["sealed manager results", "bound queue snapshot"],
    }


def _relative(path: Path, repository_root: Path) -> str:
    return path.relative_to(repository_root).as_posix()


def _write_policy(repository_root: Path) -> Path:
    path = repository_root / "policies" / "manager-screening.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "policy_id": "manager-screening.default",
                "version": "1.2.0",
                "effective_at": (CUTOFF - dt.timedelta(minutes=1)).isoformat(),
                "kind": "manager_screening",
                "payload": {
                    "decision_contract_version": 2,
                    "send_to_analyst_capacity_per_run": 200,
                    "quick_profile_effort_budget_hours": 1.5,
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _write_future_policy(repository_root: Path) -> Path:
    path = repository_root / "policies" / "manager-screening-allocation-v3.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "policy_id": "manager-screening.allocation-v3",
                "version": "3.0.0",
                "effective_at": FROZEN_AT.isoformat(),
                "kind": "manager_screening",
                "payload": {
                    "decision_contract_version": 3,
                    "routes": ["pass", "watch", "research_candidate"],
                    "research_candidate_requires_allocation": True,
                    "send_to_analyst_capacity_per_run": 200,
                    "quick_profile_effort_budget_hours": 1.5,
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _scope(root: Path, repository_root: Path) -> None:
    scope_dir = root / "scopes" / RUN_ID
    manifest_path = scope_dir / "manifest.json"
    manifest_seal = seal_json(
        manifest_path,
        {
            "schema_version": 1,
            "run_id": RUN_ID,
            "scope_cutoff": CUTOFF.isoformat(),
            "members": [],
        },
        artifact_type="all_a_scope_manifest",
        sealed_at=CUTOFF,
    )
    seal_json(
        scope_dir / "baseline-intake.json",
        {
            "schema_version": 1,
            "run_id": RUN_ID,
            "scope_cutoff": CUTOFF.isoformat(),
            "scope_manifest_path": _relative(manifest_path, repository_root),
            "scope_manifest_sha256": manifest_seal.sha256,
            "members": [],
        },
        artifact_type="all_a_baseline_intake",
        sealed_at=CUTOFF,
    )


def _control(root: Path, repository_root: Path) -> tuple[str, str]:
    path = root / "manager-screen" / RUN_ID / "control" / "pause-v3.json"
    sealed = seal_json(
        path,
        {
            "schema_version": 1,
            "run_id": RUN_ID,
            "event_id": "pause-v3",
            "state": "paused",
            "recorded_at": PAUSED_AT.isoformat(),
            "manager": _manager(),
            "reason": "Freeze an auditable activation snapshot.",
            "previous_event_sha256": None,
            "baseline_completed_company_count": None,
            "company_limit": None,
            "portfolio_action": None,
        },
        artifact_type="manager_screen_run_control_event",
        sealed_at=PAUSED_AT,
    )
    return _relative(path, repository_root), sealed.sha256


def _batch(
    root: Path,
    repository_root: Path,
    *,
    batch_id: str,
    symbols: list[str],
    send_symbols: set[str],
    decision_contract_version: int,
) -> dict[str, object]:
    batch_dir = root / "manager-screen" / RUN_ID / batch_id
    batch_path = batch_dir / "batch.json"
    policy: dict[str, object] = {"quick_profile_effort_budget_hours": 1.5}
    if decision_contract_version == 2:
        policy["decision_contract_version"] = 2
    batch = {
        "schema_version": 1,
        "run_id": RUN_ID,
        "batch_id": batch_id,
        "policy": policy,
        "members": [{"symbol": symbol} for symbol in symbols],
    }
    batch_seal = seal_json(
        batch_path,
        batch,
        artifact_type="manager_screen_batch",
        sealed_at=RESULT_AT - dt.timedelta(minutes=2),
    )
    packet_path = batch_dir / "packet.json"
    packet_seal = seal_json(
        packet_path,
        {
            "schema_version": 1,
            "run_id": RUN_ID,
            "batch_id": batch_id,
            "batch_sha256": batch_seal.sha256,
        },
        artifact_type="manager_screen_packet",
        sealed_at=RESULT_AT - dt.timedelta(minutes=1),
    )
    result_path = batch_dir / "result.json"
    result = {
        "schema_version": 1,
        "run_id": RUN_ID,
        "batch_id": batch_id,
        "recorded_at": RESULT_AT.isoformat(),
        "batch_path": _relative(batch_path, repository_root),
        "batch_sha256": batch_seal.sha256,
        "packet_path": _relative(packet_path, repository_root),
        "packet_sha256": packet_seal.sha256,
        "decisions": [
            {
                "symbol": symbol,
                "route": "send_to_analyst" if symbol in send_symbols else "watch",
            }
            for symbol in symbols
        ],
    }
    result_seal = seal_json(
        result_path,
        result,
        artifact_type="manager_screen_result",
        sealed_at=RESULT_AT,
    )
    return {
        "batch_dir": batch_dir,
        "result_path": result_path,
        "result_sha256": result_seal.sha256,
    }


def _quote_overlay(
    repository_root: Path,
    *,
    batch: dict[str, object],
    symbols: list[str],
) -> None:
    batch_dir = batch["batch_dir"]
    assert isinstance(batch_dir, Path)
    review_id = "quote-review-001"
    review_dir = batch_dir / "quote-impact-reviews" / review_id
    plan_path = review_dir / "plan.json"
    plan_seal = seal_json(
        plan_path,
        {
            "schema_version": 1,
            "run_id": RUN_ID,
            "batch_id": batch_dir.name,
            "review_id": review_id,
            "original_result_path": _relative(batch["result_path"], repository_root),
            "original_result_sha256": batch["result_sha256"],
            "policy": {"quick_profile_effort_budget_hours": 1.5},
        },
        artifact_type="manager_screen_quote_impact_plan",
        sealed_at=OVERLAY_AT - dt.timedelta(minutes=2),
    )
    packet_path = review_dir / "packet.json"
    packet_seal = seal_json(
        packet_path,
        {
            "schema_version": 1,
            "run_id": RUN_ID,
            "batch_id": batch_dir.name,
            "review_id": review_id,
            "plan_path": _relative(plan_path, repository_root),
            "plan_sha256": plan_seal.sha256,
        },
        artifact_type="manager_screen_quote_impact_packet",
        sealed_at=OVERLAY_AT - dt.timedelta(minutes=1),
    )
    reviews = [
        {
            "symbol": symbol,
            "action": "replacement",
            "old_route": "watch",
            "effective_decision": {
                "symbol": symbol,
                "route": "send_to_analyst",
            },
        }
        for symbol in symbols
    ]
    seal_json(
        review_dir / "result.json",
        {
            "schema_version": 1,
            "run_id": RUN_ID,
            "batch_id": batch_dir.name,
            "review_id": review_id,
            "recorded_at": OVERLAY_AT.isoformat(),
            "original_result_path": _relative(batch["result_path"], repository_root),
            "original_result_sha256": batch["result_sha256"],
            "plan_path": _relative(plan_path, repository_root),
            "plan_sha256": plan_seal.sha256,
            "packet_path": _relative(packet_path, repository_root),
            "packet_sha256": packet_seal.sha256,
            "reviews": reviews,
            "summary": {"new_send_to_analyst_count": len(reviews)},
        },
        artifact_type="manager_screen_quote_impact_result",
        sealed_at=OVERLAY_AT,
    )


def _legacy_adoption(root: Path, repository_root: Path, *, symbol: str) -> None:
    transition_dir = root / "manager-screen" / RUN_ID / "legacy-transition-001"
    plan_path = transition_dir / "plan.json"
    plan_seal = seal_json(
        plan_path,
        {
            "schema_version": 1,
            "run_id": RUN_ID,
            "transition_id": "legacy-transition-001",
            "members": [{"symbol": symbol, "action": "adoption"}],
        },
        artifact_type="manager_screen_legacy_transition_plan",
        sealed_at=OVERLAY_AT - dt.timedelta(minutes=2),
    )
    packet_path = transition_dir / "packet.json"
    packet_seal = seal_json(
        packet_path,
        {
            "schema_version": 1,
            "run_id": RUN_ID,
            "transition_id": "legacy-transition-001",
            "plan_path": _relative(plan_path, repository_root),
            "plan_sha256": plan_seal.sha256,
        },
        artifact_type="manager_screen_legacy_transition_packet",
        sealed_at=OVERLAY_AT - dt.timedelta(minutes=1),
    )
    seal_json(
        transition_dir / "result.json",
        {
            "schema_version": 1,
            "run_id": RUN_ID,
            "transition_id": "legacy-transition-001",
            "recorded_at": OVERLAY_AT.isoformat(),
            "plan_path": _relative(plan_path, repository_root),
            "plan_sha256": plan_seal.sha256,
            "packet_path": _relative(packet_path, repository_root),
            "packet_sha256": packet_seal.sha256,
            "decisions": [{"symbol": symbol, "route": "send_to_analyst"}],
        },
        artifact_type="manager_screen_legacy_transition_result",
        sealed_at=OVERLAY_AT,
    )


def _sealed_profile(root: Path, *, symbol: str) -> str:
    ticker = symbol.split(":", 1)[1]
    path = root / "profiles" / "activation-cycle" / ticker / "profile.profile.json"
    seal_json(
        path,
        {
            "schema_version": 1,
            "profile": {
                "symbol": symbol,
                "research_stage": "quick_profile",
            },
        },
        artifact_type="quick_profile_package",
        sealed_at=PROFILE_AT,
    )
    return path.relative_to(root.parent.parent).as_posix()


def _queue(
    root: Path,
    ledger: list[dict[str, object]],
    *,
    completed_without_profile: bool = False,
) -> None:
    rows = []
    profile_symbol = "CN:000005"
    profile_path = (
        None
        if completed_without_profile
        else _sealed_profile(
            root,
            symbol=profile_symbol,
        )
    )
    for item in ledger:
        symbol = item["symbol"]
        state: dict[str, object] = {
            "symbol": symbol,
            "manager_screen_run_id": RUN_ID,
            "manager_screen_route": "send_to_analyst",
            "manager_screen_result_path": item["source_path"],
            "manager_screen_result_sha256": item["source_sha256"],
            "task_type": "quick_profile",
            "status": "pending",
            "assigned_agent": None,
            "started_at": None,
            "finished_at": None,
            "failure_reason": None,
            "result_path": None,
            "preceding_stage": "manager_screen",
            "attempt_history": [],
            "stage_history": [],
        }
        if symbol == "CN:000002":
            state["assigned_agent"] = "/root/claimed-but-not-started"
        elif symbol == "CN:000003":
            state["attempt_history"] = [
                {"agent": "/root/attempted", "started_at": PROFILE_AT.isoformat()}
            ]
        elif symbol == "CN:000004":
            state.update(
                {
                    "status": "running",
                    "assigned_agent": "/root/running",
                    "started_at": PROFILE_AT.isoformat(),
                }
            )
        elif symbol == profile_symbol:
            state.update(
                {
                    "status": "completed",
                    "assigned_agent": "/root/completed",
                    "started_at": OVERLAY_AT.isoformat(),
                    "finished_at": PROFILE_AT.isoformat(),
                    "result_path": profile_path,
                    "stage_history": [
                        {
                            "stage": "quick_profile",
                            "status": "completed",
                            "finished_at": PROFILE_AT.isoformat(),
                            "result_path": profile_path,
                        }
                    ],
                }
            )
        rows.append(state)
    (root / "research_queue.jsonl").write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def _status(
    *,
    control_path: str,
    control_sha256: str,
    purchase_count: int = 200,
    hours: float = 300.0,
    state: str = "paused",
    completed: int = 3000,
    remaining: int = 2445,
    open_batches: int = 0,
    open_companies: int = 0,
) -> dict[str, object]:
    return {
        "completed_company_count": completed,
        "remaining_unbatched_count": remaining,
        "open_batches": open_batches,
        "open_company_count": open_companies,
        "control": {
            "state": state,
            "latest_event_path": control_path,
            "latest_event_sha256": control_sha256,
        },
        "analyst_budget": {
            "purchased_company_count": purchase_count,
            "purchased_effort_budget_hours": hours,
        },
    }


def _repository(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    include_legacy: bool = True,
    completed_without_profile: bool = False,
    status_changes: dict[str, object] | None = None,
) -> tuple[Path, dict[str, object]]:
    import trading_os.research_assets.manager_screen_allocation_v3 as allocation_v3

    repository_root = tmp_path
    root = repository_root / "coverage" / "cn-a"
    _write_policy(repository_root)
    _write_future_policy(repository_root)
    _scope(root, repository_root)
    control_path, control_sha256 = _control(root, repository_root)
    v1_symbols = [f"CN:{ordinal:06d}" for ordinal in range(1, 101)]
    v2_symbols = [f"CN:{ordinal:06d}" for ordinal in range(101, 200)]
    v1 = _batch(
        root,
        repository_root,
        batch_id="batch-v1",
        symbols=v1_symbols,
        send_symbols=set(v1_symbols),
        decision_contract_version=1,
    )
    del v1
    quote_symbols = {"CN:000198", "CN:000199"}
    v2 = _batch(
        root,
        repository_root,
        batch_id="batch-v2",
        symbols=v2_symbols,
        send_symbols=set(v2_symbols) - quote_symbols,
        decision_contract_version=2,
    )
    _quote_overlay(repository_root, batch=v2, symbols=sorted(quote_symbols))
    if include_legacy:
        _legacy_adoption(root, repository_root, symbol="CN:000200")
    ledger_state = allocation_v3.rebuild_manager_screen_inherited_purchase_ledger(
        root=root,
        run_id=RUN_ID,
        cutoff=FROZEN_AT,
    )
    _queue(
        root,
        ledger_state["ledger"],
        completed_without_profile=completed_without_profile,
    )
    status = _status(
        control_path=control_path,
        control_sha256=control_sha256,
        purchase_count=ledger_state["purchase_count"],
        hours=ledger_state["effort_budget_hours"],
        **(status_changes or {}),
    )
    monkeypatch.setattr(allocation_v3, "manager_screen_status", lambda **_: status)
    return root, ledger_state


def _freeze(root: Path, **changes):
    from trading_os.research_assets.manager_screen_allocation_v3 import (
        freeze_manager_screen_allocation_v3_contract,
    )

    arguments = {
        "root": root,
        "run_id": RUN_ID,
        "manager": _manager(),
        "reason": "Pause early commitments and compare the complete market fairly.",
        "frozen_at": FROZEN_AT,
    }
    arguments.update(changes)
    return freeze_manager_screen_allocation_v3_contract(**arguments)


def test_contract_rebuilds_v1_v2_quote_and_legacy_without_expanding_cap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_os.research_assets.manager_screen_allocation_v3 import (
        verify_manager_screen_allocation_v3_contract,
    )

    root, ledger = _repository(tmp_path, monkeypatch)
    assert ledger["source_counts"] == {
        "manager_screen_result": 197,
        "manager_screen_quote_impact_result": 2,
        "manager_screen_legacy_transition_result": 1,
    }

    frozen = _freeze(root)
    payload = verify_manager_screen_allocation_v3_contract(
        root=root,
        run_id=RUN_ID,
    )

    assert frozen["historical_purchase_count"] == 200
    assert frozen["historical_effort_budget_hours"] == 300.0
    assert payload["capacity"] == {
        "historical_purchase_count": 200,
        "historical_effort_budget_hours": 300.0,
        "absolute_funded_company_limit": 200,
        "absolute_funded_effort_budget_hours": 300.0,
        "irreversible_commitment_count": 4,
        "irreversible_effort_budget_hours": 6.0,
        "revocable_commitment_count": 196,
        "revocable_effort_budget_hours": 294.0,
        "post_scope_selection_capacity": 196,
        "purchase_effort_budget_hours": 1.5,
    }
    assert payload["rules"]["direct_send_to_analyst"] is False
    assert payload["rules"]["full_scope_before_allocation"] is True
    assert payload["rules"]["historical_routes_immutable"] is True
    assert "incremental_purchase_count_limit" not in payload["capacity"]
    source_kinds = Counter(item["source_kind"] for item in payload["inherited_ledger"])
    assert source_kinds == {
        "manager_screen_result": 197,
        "manager_screen_quote_impact_result": 2,
        "manager_screen_legacy_transition_result": 1,
    }


def test_only_pending_never_claimed_without_attempt_or_sealed_progress_is_revocable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_os.research_assets.manager_screen_allocation_v3 import (
        verify_manager_screen_allocation_v3_contract,
    )

    root, _ = _repository(tmp_path, monkeypatch)
    _freeze(root)
    payload = verify_manager_screen_allocation_v3_contract(root=root, run_id=RUN_ID)
    by_symbol = {item["symbol"]: item for item in payload["commitment_classification"]}

    assert by_symbol["CN:000001"]["commitment_class"] == "revocable"
    assert by_symbol["CN:000001"]["reason_codes"] == [
        "pending_never_claimed_without_sealed_progress"
    ]
    assert by_symbol["CN:000002"]["commitment_class"] == "irreversible"
    assert "claim_identity_present" in by_symbol["CN:000002"]["reason_codes"]
    assert by_symbol["CN:000003"]["commitment_class"] == "irreversible"
    assert "attempt_history_present" in by_symbol["CN:000003"]["reason_codes"]
    assert by_symbol["CN:000004"]["commitment_class"] == "irreversible"
    assert "queue_running" in by_symbol["CN:000004"]["reason_codes"]
    assert by_symbol["CN:000005"]["commitment_class"] == "irreversible"
    assert by_symbol["CN:000005"]["sealed_progress"]


def test_pending_with_failure_result_or_non_manager_predecessor_is_irreversible(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_os.research_assets.manager_screen_allocation_v3 import (
        verify_manager_screen_allocation_v3_contract,
    )

    root, _ = _repository(tmp_path, monkeypatch)
    queue_path = root / "research_queue.jsonl"
    rows = [
        json.loads(line)
        for line in queue_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    by_symbol = {row["symbol"]: row for row in rows}
    by_symbol["CN:000001"]["failure_reason"] = "prior claim crashed"
    by_symbol["CN:000006"]["result_path"] = "coverage/cn-a/profiles/partial.json"
    by_symbol["CN:000007"]["preceding_stage"] = "targeted_followup"
    queue_path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )
    _freeze(root)
    payload = verify_manager_screen_allocation_v3_contract(root=root, run_id=RUN_ID)
    classified = {item["symbol"]: item for item in payload["commitment_classification"]}

    assert "failure_trace_present" in classified["CN:000001"]["reason_codes"]
    assert "result_pointer_present" in classified["CN:000006"]["reason_codes"]
    assert "preceding_stage_not_manager_screen" in classified["CN:000007"]["reason_codes"]
    assert all(
        classified[symbol]["commitment_class"] == "irreversible"
        for symbol in ("CN:000001", "CN:000006", "CN:000007")
    )


def test_contract_is_idempotent_and_conflicting_replay_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_os.research_assets.manager_screen_allocation_v3 import (
        ManagerScreenAllocationV3Error,
    )

    root, _ = _repository(tmp_path, monkeypatch)
    first = _freeze(root)
    replay = _freeze(root)
    assert first["contract_sha256"] == replay["contract_sha256"]
    assert first["idempotent"] is False
    assert replay["idempotent"] is True

    with pytest.raises(ManagerScreenAllocationV3Error, match="conflicts"):
        _freeze(root, reason="A different allocation rationale.")


def test_contract_fails_closed_on_queue_or_sealed_result_tamper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_os.research_assets.manager_screen_allocation_v3 import (
        ManagerScreenAllocationV3Error,
        manager_screen_allocation_v3_activation_drift_status,
        verify_manager_screen_allocation_v3_contract,
    )

    root, _ = _repository(tmp_path, monkeypatch)
    _freeze(root)
    queue_path = root / "research_queue.jsonl"
    queue_path.write_text(
        queue_path.read_text(encoding="utf-8") + json.dumps({"symbol": "CN:999999"}) + "\n",
        encoding="utf-8",
    )
    assert verify_manager_screen_allocation_v3_contract(root=root, run_id=RUN_ID)
    assert (
        manager_screen_allocation_v3_activation_drift_status(
            root=root,
            run_id=RUN_ID,
        )["drifted"]
        is True
    )

    other_root, _ = _repository(tmp_path / "result-tamper", monkeypatch)
    _freeze(other_root)
    result_path = (
        tmp_path
        / "result-tamper"
        / "coverage"
        / "cn-a"
        / "manager-screen"
        / RUN_ID
        / "batch-v1"
        / "result.json"
    )
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    payload["decisions"][0]["route"] = "watch"
    result_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ManagerScreenAllocationV3Error, match="sealed allocation input"):
        verify_manager_screen_allocation_v3_contract(root=other_root, run_id=RUN_ID)


def test_contract_rejects_tampered_formal_progress_after_activation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_os.research_assets.manager_screen_allocation_v3 import (
        ManagerScreenAllocationV3Error,
        verify_manager_screen_allocation_v3_contract,
    )

    root, _ = _repository(tmp_path, monkeypatch)
    _freeze(root)
    profile_path = root / "profiles" / "activation-cycle" / "000005" / "profile.profile.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    profile["profile"]["post_activation_rewrite"] = True
    profile_path.write_text(
        json.dumps(profile, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ManagerScreenAllocationV3Error,
        match="sealed allocation input is invalid",
    ):
        verify_manager_screen_allocation_v3_contract(root=root, run_id=RUN_ID)


@pytest.mark.parametrize(
    ("status_changes", "message"),
    [
        ({"state": "active"}, "only be frozen while the run is paused"),
        ({"open_batches": 1, "open_companies": 1}, "zero open batches"),
        ({"completed": 2999}, "completed-company count is stale"),
        ({"remaining": 2444}, "remaining-company count is stale"),
    ],
)
def test_activation_gate_rejects_wrong_state_or_counts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    status_changes: dict[str, object],
    message: str,
) -> None:
    from trading_os.research_assets.manager_screen_allocation_v3 import (
        ManagerScreenAllocationV3Error,
    )

    root, _ = _repository(
        tmp_path,
        monkeypatch,
        status_changes=status_changes,
    )
    with pytest.raises(ManagerScreenAllocationV3Error, match=message):
        _freeze(root)


def test_wrong_inherited_purchase_count_and_unsealed_completed_state_fail(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_os.research_assets.manager_screen_allocation_v3 import (
        ManagerScreenAllocationV3Error,
    )

    root, _ = _repository(tmp_path / "wrong-count", monkeypatch, include_legacy=False)
    with pytest.raises(ManagerScreenAllocationV3Error, match="exactly 200 inherited"):
        _freeze(root)

    completed_root, _ = _repository(
        tmp_path / "unsealed-completed",
        monkeypatch,
        completed_without_profile=True,
    )
    with pytest.raises(
        ManagerScreenAllocationV3Error,
        match="completed queue state lacks sealed formal progress",
    ):
        _freeze(completed_root)


def test_partial_contract_is_rejected_before_any_overwrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_os.research_assets.manager_screen_allocation_v3 import (
        ManagerScreenAllocationV3Error,
    )

    root, _ = _repository(tmp_path, monkeypatch)
    contract_path = (
        root / "manager-screen" / RUN_ID / "governance" / "allocation-v3" / "contract.json"
    )
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    contract_path.write_text("{}", encoding="utf-8")
    with pytest.raises(ManagerScreenAllocationV3Error, match="partially sealed"):
        _freeze(root)
    assert contract_path.read_text(encoding="utf-8") == "{}"


def test_sealed_contract_authorizes_only_its_one_v2_to_v3_policy_path_migration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_os.research_assets.manager_screening as screening
    from trading_os.research_assets.manager_screen_allocation_v3 import (
        verify_manager_screen_allocation_v3_contract,
    )

    root, _ = _repository(tmp_path, monkeypatch)
    _freeze(root)
    contract = verify_manager_screen_allocation_v3_contract(root=root, run_id=RUN_ID)
    existing = {
        **contract["prior_policy"],
        "high_liability_to_assets_pct": 90.0,
    }
    requested = {
        **contract["future_policy"],
        "high_liability_to_assets_pct": 90.0,
    }
    run_dir = root / "manager-screen" / RUN_ID
    monkeypatch.setattr(
        screening,
        "_active_run_bounded_policies",
        lambda **_: [existing],
    )

    screening._enforce_run_capacity_policy_monotonic(
        run_dir=run_dir,
        requested_policy=requested,
        repository_root=tmp_path,
    )
    monkeypatch.setattr(
        screening,
        "_active_run_bounded_policies",
        lambda **_: [existing, requested],
    )
    screening._enforce_run_capacity_policy_monotonic(
        run_dir=run_dir,
        requested_policy=requested,
        repository_root=tmp_path,
    )
    with pytest.raises(screening.ManagerScreeningError, match="exact future-policy"):
        screening._enforce_run_capacity_policy_monotonic(
            run_dir=run_dir,
            requested_policy={
                **requested,
                "path": "policies/unbound-v3.json",
            },
            repository_root=tmp_path,
        )
    with pytest.raises(
        screening.ManagerScreeningError,
        match="subsequent batches must use",
    ):
        screening._enforce_run_capacity_policy_monotonic(
            run_dir=run_dir,
            requested_policy=existing,
            repository_root=tmp_path,
        )
