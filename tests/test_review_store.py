from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

T0 = dt.datetime(2026, 7, 21, 0, 0, tzinfo=dt.timezone.utc)


def _store(tmp_path: Path):
    from trading_os.research_assets.review_store import ReviewRunStore

    return ReviewRunStore(tmp_path / "automation" / "runs")


def _create(store, run_id: str = "memory-2026-07-21") -> dict[str, object]:
    return store.create_run(
        run_id,
        scope={"type": "industry", "market": "CN", "description": "存储产业链"},
        policy_versions={
            "underwriting.default": "1.0.0",
            "portfolio.default-model": "1.0.0",
        },
        policy_snapshot_sha256="f" * 64,
        created_at=T0,
    )


def _candidates() -> list[dict[str, str]]:
    return [
        {
            "symbol": "CN:000100",
            "name": "TCL科技",
            "target_company_dir": "research/companies/CN/000100",
        },
        {
            "symbol": "CN:000021",
            "name": "深科技",
            "target_company_dir": "research/companies/CN/000021",
        },
    ]


def test_create_run_writes_v2_state_and_initial_event(tmp_path: Path):
    store = _store(tmp_path)

    state = _create(store)

    assert state["schema_version"] == 2
    assert state["status"] == "created"
    assert state["candidate_set"] == {
        "frozen": False,
        "frozen_at": None,
        "sha256": None,
        "count": 0,
        "source_binding": None,
    }
    assert store.load_run("memory-2026-07-21") == state
    events = store.read_events("memory-2026-07-21")
    assert events == [
        {
            "sequence": 1,
            "event": "run_created",
            "from_status": None,
            "to_status": "created",
            "actor": "system",
            "at": T0.isoformat(),
            "reason": None,
        }
    ]


def test_create_run_rejects_null_policy_snapshot_hash(tmp_path: Path):
    from trading_os.research_assets.review_store import ReviewStoreError

    with pytest.raises(ReviewStoreError, match="policy_snapshot_sha256"):
        _store(tmp_path).create_run(
            "null-policy-snapshot",
            scope={"type": "custom", "market": "CN", "description": "invalid"},
            policy_versions={"underwriting.default": "2.0.0"},
            policy_snapshot_sha256=None,
            created_at=T0,
        )


def test_create_run_is_idempotent_only_for_identical_manifest(tmp_path: Path):
    from trading_os.research_assets.review_store import ReviewStoreError

    store = _store(tmp_path)
    first = _create(store)

    assert _create(store) == first
    with pytest.raises(ReviewStoreError, match="different manifest"):
        store.create_run(
            "memory-2026-07-21",
            scope={"type": "theme", "market": "CN", "description": "changed"},
            policy_versions={"underwriting.default": "1.0.0"},
            policy_snapshot_sha256="f" * 64,
            created_at=T0,
        )


@pytest.mark.parametrize(
    (
        "failpoint",
        "state_exists",
        "events_exists",
        "transaction_exists",
    ),
    [
        ("create_directory_ready", False, False, False),
        ("create_tasks_ready", False, False, False),
        ("transaction_prepared", False, False, True),
        ("state_written", True, False, True),
        ("events_written", True, True, True),
        ("transaction_cleared", True, True, False),
    ],
)
def test_create_run_repairs_every_crash_boundary_on_identical_replay(
    tmp_path: Path,
    monkeypatch,
    failpoint: str,
    state_exists: bool,
    events_exists: bool,
    transaction_exists: bool,
) -> None:
    from trading_os.research_assets import review_store

    store = _store(tmp_path)

    def crash(name: str) -> None:
        if name == failpoint:
            raise RuntimeError(f"simulated crash at {name}")

    monkeypatch.setattr(review_store, "_crash_failpoint", crash)
    with pytest.raises(RuntimeError, match="simulated crash"):
        _create(store)

    run_dir = (
        tmp_path / "automation" / "runs" / "memory-2026-07-21"
    )
    assert (run_dir / "state.json").exists() is state_exists
    assert (run_dir / "events.jsonl").exists() is events_exists
    assert (
        run_dir / review_store.STATE_TRANSACTION_FILE
    ).exists() is transaction_exists

    monkeypatch.setattr(review_store, "_crash_failpoint", lambda _: None)
    recovered = _create(store)

    assert recovered["status"] == "created"
    assert store.load_run("memory-2026-07-21") == recovered
    assert [event["event"] for event in store.read_events("memory-2026-07-21")] == [
        "run_created"
    ]
    assert (run_dir / "agent_tasks").is_dir()
    assert not (run_dir / review_store.STATE_TRANSACTION_FILE).exists()


def test_freeze_candidates_sorts_and_hashes_immutable_snapshot(tmp_path: Path):
    store = _store(tmp_path)
    _create(store)

    state = store.freeze_candidates(
        "memory-2026-07-21",
        list(reversed(_candidates())),
        actor="coordinator",
        at=T0 + dt.timedelta(minutes=1),
    )

    assert state["status"] == "candidates_frozen"
    assert state["candidate_set"]["frozen"] is True
    assert state["candidate_set"]["count"] == 2
    assert len(state["candidate_set"]["sha256"]) == 64
    snapshot = store.read_candidates("memory-2026-07-21")
    assert [item["symbol"] for item in snapshot] == ["CN:000021", "CN:000100"]


@pytest.mark.parametrize(
    (
        "failpoint",
        "raw_status",
        "event_count",
        "transaction_exists",
    ),
    [
        ("transaction_prepared", "candidates_frozen", 2, True),
        ("state_written", "packets_ready", 2, True),
        ("events_written", "packets_ready", 3, True),
        ("transaction_cleared", "packets_ready", 3, False),
    ],
)
def test_transition_repairs_every_two_phase_crash_boundary(
    tmp_path: Path,
    monkeypatch,
    failpoint: str,
    raw_status: str,
    event_count: int,
    transaction_exists: bool,
) -> None:
    from trading_os.research_assets import review_store

    store = _store(tmp_path)
    _create(store)
    store.freeze_candidates(
        "memory-2026-07-21",
        _candidates(),
        actor="coordinator",
        at=T0 + dt.timedelta(minutes=1),
    )

    def crash(name: str) -> None:
        if name == failpoint:
            raise RuntimeError(f"simulated crash at {name}")

    monkeypatch.setattr(review_store, "_crash_failpoint", crash)
    transition_at = T0 + dt.timedelta(minutes=2)
    with pytest.raises(RuntimeError, match="simulated crash"):
        store.transition(
            "memory-2026-07-21",
            "packets_ready",
            actor="coordinator",
            at=transition_at,
        )

    run_dir = (
        tmp_path / "automation" / "runs" / "memory-2026-07-21"
    )
    raw_state = json.loads(
        (run_dir / "state.json").read_text(encoding="utf-8")
    )
    raw_events = [
        json.loads(line)
        for line in (run_dir / "events.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
    ]
    assert raw_state["status"] == raw_status
    assert len(raw_events) == event_count
    assert (
        run_dir / review_store.STATE_TRANSACTION_FILE
    ).exists() is transaction_exists

    monkeypatch.setattr(review_store, "_crash_failpoint", lambda _: None)
    recovered = store.transition(
        "memory-2026-07-21",
        "packets_ready",
        actor="coordinator",
        at=transition_at,
    )

    assert recovered["status"] == "packets_ready"
    events = store.read_events("memory-2026-07-21")
    assert len(events) == 3
    assert events[-1] == {
        "sequence": 3,
        "event": "state_transition",
        "from_status": "candidates_frozen",
        "to_status": "packets_ready",
        "actor": "coordinator",
        "at": transition_at.isoformat(),
        "reason": None,
    }
    assert not (run_dir / review_store.STATE_TRANSACTION_FILE).exists()


def test_pending_transaction_recovery_fails_closed_on_conflicting_state(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from trading_os.research_assets import review_store
    from trading_os.research_assets.review_store import ReviewStoreError

    store = _store(tmp_path)
    _create(store)
    store.freeze_candidates(
        "memory-2026-07-21",
        _candidates(),
        actor="coordinator",
        at=T0 + dt.timedelta(minutes=1),
    )

    def crash(name: str) -> None:
        if name == "transaction_prepared":
            raise RuntimeError("simulated crash")

    monkeypatch.setattr(review_store, "_crash_failpoint", crash)
    with pytest.raises(RuntimeError, match="simulated crash"):
        store.transition(
            "memory-2026-07-21",
            "packets_ready",
            actor="coordinator",
            at=T0 + dt.timedelta(minutes=2),
        )

    state_path = (
        tmp_path
        / "automation"
        / "runs"
        / "memory-2026-07-21"
        / "state.json"
    )
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["status"] = "completed"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    monkeypatch.setattr(review_store, "_crash_failpoint", lambda _: None)

    with pytest.raises(ReviewStoreError, match="conflicts with pending"):
        store.load_run("memory-2026-07-21")


def test_frozen_candidates_are_idempotent_but_cannot_change(tmp_path: Path):
    from trading_os.research_assets.review_store import ReviewStoreError

    store = _store(tmp_path)
    _create(store)
    first = store.freeze_candidates(
        "memory-2026-07-21",
        _candidates(),
        actor="coordinator",
        at=T0 + dt.timedelta(minutes=1),
    )

    assert (
        store.freeze_candidates(
            "memory-2026-07-21",
            list(reversed(_candidates())),
            actor="coordinator",
            at=T0 + dt.timedelta(minutes=2),
        )
        == first
    )
    changed = _candidates() + [
        {
            "symbol": "CN:300750",
            "name": "宁德时代",
            "target_company_dir": "research/companies/CN/300750",
        }
    ]
    with pytest.raises(ReviewStoreError, match="frozen"):
        store.freeze_candidates(
            "memory-2026-07-21",
            changed,
            actor="coordinator",
            at=T0 + dt.timedelta(minutes=2),
        )


@pytest.mark.parametrize(
    "statuses",
    [
        [
            "packets_ready",
            "blind_reviewing",
            "blind_sealed",
            "revealing",
            "company_reviews_complete",
            "synthesizing",
            "completed",
        ],
        [
            "packets_ready",
            "blind_reviewing",
            "blind_sealed",
            "revealing",
            "challenging",
            "company_reviews_complete",
            "synthesizing",
            "completed",
        ],
    ],
)
def test_legal_review_paths_reach_completed(tmp_path: Path, statuses: list[str]):
    store = _store(tmp_path)
    _create(store)
    store.freeze_candidates(
        "memory-2026-07-21",
        _candidates(),
        actor="coordinator",
        at=T0 + dt.timedelta(minutes=1),
    )

    for offset, status in enumerate(statuses, start=2):
        state = store.transition(
            "memory-2026-07-21",
            status,
            actor="coordinator",
            at=T0 + dt.timedelta(minutes=offset),
        )

    assert state["status"] == "completed"
    events = store.read_events("memory-2026-07-21")
    assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [
        ("created", "packets_ready"),
        ("candidates_frozen", "blind_reviewing"),
        ("packets_ready", "revealing"),
        ("blind_reviewing", "revealing"),
        ("blind_sealed", "completed"),
        ("completed", "synthesizing"),
    ],
)
def test_illegal_state_transitions_are_rejected(
    tmp_path: Path, from_status: str, to_status: str
):
    from trading_os.research_assets.review_store import ReviewStoreError

    store = _store(tmp_path)
    _create(store)
    if from_status != "created":
        store.freeze_candidates(
            "memory-2026-07-21",
            _candidates(),
            actor="coordinator",
            at=T0 + dt.timedelta(minutes=1),
        )
        path = {
            "candidates_frozen": [],
            "packets_ready": ["packets_ready"],
            "blind_reviewing": ["packets_ready", "blind_reviewing"],
            "blind_sealed": ["packets_ready", "blind_reviewing", "blind_sealed"],
            "completed": [
                "packets_ready",
                "blind_reviewing",
                "blind_sealed",
                "revealing",
                "company_reviews_complete",
                "synthesizing",
                "completed",
            ],
        }[from_status]
        for offset, status in enumerate(path, start=2):
            store.transition(
                "memory-2026-07-21",
                status,
                actor="coordinator",
                at=T0 + dt.timedelta(minutes=offset),
            )

    with pytest.raises(ReviewStoreError, match="illegal review state transition"):
        store.transition(
            "memory-2026-07-21",
            to_status,
            actor="coordinator",
            at=T0 + dt.timedelta(hours=1),
        )


def test_failure_and_cancel_states_are_terminal_until_explicit_resume(tmp_path: Path):
    from trading_os.research_assets.review_store import ReviewStoreError

    store = _store(tmp_path)
    _create(store)
    store.freeze_candidates(
        "memory-2026-07-21",
        _candidates(),
        actor="coordinator",
        at=T0 + dt.timedelta(minutes=1),
    )
    failed = store.transition(
        "memory-2026-07-21",
        "failed_validation",
        actor="validator",
        at=T0 + dt.timedelta(minutes=2),
        reason="claim packet leaked a target price",
    )
    assert failed["status"] == "failed_validation"

    with pytest.raises(ReviewStoreError):
        store.transition(
            "memory-2026-07-21",
            "packets_ready",
            actor="coordinator",
            at=T0 + dt.timedelta(minutes=3),
        )

    resumed = store.resume(
        "memory-2026-07-21",
        actor="coordinator",
        at=T0 + dt.timedelta(minutes=4),
    )
    assert resumed["status"] == "candidates_frozen"
    assert store.read_events("memory-2026-07-21")[-1]["event"] == "run_resumed"


def test_resume_rejects_nonfailure_state(tmp_path: Path):
    from trading_os.research_assets.review_store import ReviewStoreError

    store = _store(tmp_path)
    _create(store)

    with pytest.raises(ReviewStoreError, match="only a failed"):
        store.resume("memory-2026-07-21", actor="test", at=T0)


def test_task_lease_is_exclusive_and_same_owner_is_idempotent(tmp_path: Path):
    from trading_os.research_assets.review_store import ReviewStoreError

    store = _store(tmp_path)
    _create(store)
    first = store.acquire_lease(
        "memory-2026-07-21",
        "CN-000021-blind",
        owner="agent-a",
        now=T0,
        ttl_seconds=600,
    )
    second = store.acquire_lease(
        "memory-2026-07-21",
        "CN-000021-blind",
        owner="agent-a",
        now=T0 + dt.timedelta(seconds=30),
        ttl_seconds=600,
    )

    assert second == first
    with pytest.raises(ReviewStoreError, match="leased"):
        store.acquire_lease(
            "memory-2026-07-21",
            "CN-000021-blind",
            owner="agent-b",
            now=T0 + dt.timedelta(seconds=30),
            ttl_seconds=600,
        )


def test_expired_task_lease_can_be_reclaimed(tmp_path: Path):
    store = _store(tmp_path)
    _create(store)
    store.acquire_lease(
        "memory-2026-07-21",
        "CN-000021-blind",
        owner="agent-a",
        now=T0,
        ttl_seconds=60,
    )

    reclaimed = store.acquire_lease(
        "memory-2026-07-21",
        "CN-000021-blind",
        owner="agent-b",
        now=T0 + dt.timedelta(seconds=61),
        ttl_seconds=120,
    )

    assert reclaimed.owner == "agent-b"
    assert reclaimed.attempt == 2


def test_only_lease_owner_can_complete_and_completion_is_idempotent(tmp_path: Path):
    from trading_os.research_assets.review_store import ReviewStoreError

    store = _store(tmp_path)
    _create(store)
    store.acquire_lease(
        "memory-2026-07-21",
        "CN-000021-blind",
        owner="agent-a",
        now=T0,
        ttl_seconds=600,
    )

    with pytest.raises(ReviewStoreError, match="owner"):
        store.complete_lease(
            "memory-2026-07-21",
            "CN-000021-blind",
            owner="agent-b",
            completed_at=T0 + dt.timedelta(minutes=1),
            result_path="research/companies/CN/000021/underwriting/review/blind.json",
        )

    completed = store.complete_lease(
        "memory-2026-07-21",
        "CN-000021-blind",
        owner="agent-a",
        completed_at=T0 + dt.timedelta(minutes=1),
        result_path="research/companies/CN/000021/underwriting/review/blind.json",
    )
    repeated = store.complete_lease(
        "memory-2026-07-21",
        "CN-000021-blind",
        owner="agent-a",
        completed_at=T0 + dt.timedelta(minutes=1),
        result_path="research/companies/CN/000021/underwriting/review/blind.json",
    )

    assert completed == repeated
    assert completed.status == "completed"


def test_event_log_rejects_manual_sequence_corruption(tmp_path: Path):
    from trading_os.research_assets.review_store import ReviewStoreError

    store = _store(tmp_path)
    _create(store)
    event_path = (
        tmp_path
        / "automation"
        / "runs"
        / "memory-2026-07-21"
        / "events.jsonl"
    )
    with event_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"sequence": 99}) + "\n")

    with pytest.raises(ReviewStoreError, match="event sequence"):
        store.read_events("memory-2026-07-21")
