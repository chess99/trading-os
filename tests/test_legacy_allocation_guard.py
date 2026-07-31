from __future__ import annotations

import copy
import datetime as dt
import json
from pathlib import Path

import pytest

from trading_os.research_assets.coverage_store import (
    CoverageValidationError,
    enqueue_research,
    write_jsonl,
)
from trading_os.research_assets.research_allocation import (
    ResearchAllocationError,
    allocate_research_capacity,
    apply_research_allocation,
)

ROOT = Path(__file__).resolve().parents[1]


def _policy() -> dict[str, object]:
    return copy.deepcopy(
        json.loads(
            (ROOT / "policies" / "research-allocation.json").read_text(
                encoding="utf-8"
            )
        )["payload"]
    )


def _ranking_item(index: int) -> dict[str, object]:
    return {
        "symbol": f"CN:{index:06d}",
        "name": f"Company {index}",
        "total_score": 80.0 - index,
        "score_confidence": "high",
        "economic_risk_cluster": "consumer_demand",
        "dimensions": {
            "value_dislocation": 10.0,
            "operating_capital_quality": 10.0,
            "permanent_loss_protection": 10.0,
            "information_update_urgency": 5.0,
            "verifiable_catalyst_odds": 5.0,
            "evidence_availability": 5.0,
        },
        "penalties": [],
        "reason_codes": ["public_prefilter_evidence_available"],
        "public_snapshot": {"dividend_yield_pct": 2.0},
    }


def _allocation() -> tuple[dict[str, object], dict[str, object]]:
    ranking: dict[str, object] = {
        "generated_at": "2026-07-31T08:00:00+08:00",
        "items": [_ranking_item(1)],
        "excluded": [],
    }
    allocation = allocate_research_capacity(
        ranking,
        policy=_policy(),
        policy_version="research-allocation.default@4.0.0",
    )
    return ranking, allocation


def _write_root(
    root: Path,
    *,
    manager_status: str,
    bind_queue: bool,
    bind_screening: bool,
) -> tuple[bytes, bytes]:
    companies = [
        {"symbol": "CN:000001", "name": "Company 1"},
        {"symbol": "CN:000002", "name": "Company 2"},
    ]
    screening = [
        {
            "symbol": "CN:000001",
            "name": "Company 1",
            "decision": "catalog",
            "priority": None,
            "reason": "legacy",
            "evidence": ["legacy"],
            "next_action": "legacy",
        },
        {
            "symbol": "CN:000002",
            "name": "Company 2",
            "decision": "watch_only",
            "priority": None,
            "reason": "manager decision",
            "evidence": ["snapshot:CN:000002"],
            "next_action": "wait",
        },
    ]
    queue = [
        {
            "symbol": "CN:000001",
            "name": "Company 1",
            "task_type": "rapid_triage",
            "priority": 3,
            "status": "requires_rebaseline",
            "reason": "legacy",
            "target_company_dir": "research/companies/CN/000001",
        },
        {
            "symbol": "CN:000002",
            "name": "Company 2",
            "task_type": "manager_screen",
            "priority": 3,
            "status": manager_status,
            "reason": "manager decision",
            "target_company_dir": "research/companies/CN/000002",
        },
    ]
    binding = {
        "manager_screen_run_id": "2026-07-31-all-a-continuous-001",
        "manager_screen_batch_id": "batch-001",
        "manager_screen_route": "watch",
        "manager_screen_result_path": (
            "coverage/cn-a/manager-screen/"
            "2026-07-31-all-a-continuous-001/batch-001/result.json"
        ),
        "manager_screen_result_sha256": "1" * 64,
    }
    if bind_screening:
        screening[1].update(binding)
    if bind_queue:
        queue[1].update(binding)
        queue[1]["stage_history"] = [
            {
                "stage": "manager_screen",
                "status": manager_status,
            }
        ]

    write_jsonl(root / "companies.jsonl", companies)
    write_jsonl(root / "screening.jsonl", screening)
    write_jsonl(root / "research_queue.jsonl", queue)
    write_jsonl(root / "runs.jsonl", [], sort_key="run_id")
    return (
        (root / "screening.jsonl").read_bytes(),
        (root / "research_queue.jsonl").read_bytes(),
    )


def _seal_scope(root: Path, symbol: str) -> Path:
    from trading_os.research_assets.sealing import seal_json

    run_id = "current-manager-screen-run"
    manifest_path = root / "scopes" / run_id / "manifest.json"
    seal_json(
        manifest_path,
        {
            "schema_version": 1,
            "run_id": run_id,
            "market": "CN",
            "members": [{"symbol": symbol}],
        },
        artifact_type="all_a_scope_manifest",
        sealed_at=dt.datetime.fromisoformat("2026-07-31T08:00:00+08:00"),
    )
    return manifest_path


def _enqueue(root: Path, symbol: str = "CN:000001") -> Path:
    return enqueue_research(
        root,
        symbol=symbol,
        name="Company 1",
        priority=3,
        reason="legacy compatibility",
    )


@pytest.mark.parametrize("status", ["pending", "running", "completed"])
def test_legacy_apply_rejects_any_manager_bound_queue_status(
    tmp_path: Path, status: str
) -> None:
    ranking, allocation = _allocation()
    root = tmp_path / "coverage" / "cn-a"
    before_screening, before_queue = _write_root(
        root,
        manager_status=status,
        bind_queue=True,
        bind_screening=False,
    )

    with pytest.raises(
        ResearchAllocationError,
        match="cannot write manager-screen-bound coverage",
    ):
        apply_research_allocation(
            allocation,
            ranking=ranking,
            root=root,
            applied_at=dt.datetime.fromisoformat("2026-07-31T09:00:00+08:00"),
        )

    assert (root / "screening.jsonl").read_bytes() == before_screening
    assert (root / "research_queue.jsonl").read_bytes() == before_queue


def test_legacy_apply_rejects_manager_bound_screening_without_queue_binding(
    tmp_path: Path,
) -> None:
    ranking, allocation = _allocation()
    root = tmp_path / "coverage" / "cn-a"
    before_screening, before_queue = _write_root(
        root,
        manager_status="completed",
        bind_queue=False,
        bind_screening=True,
    )

    with pytest.raises(
        ResearchAllocationError,
        match=r"found 1 bound symbol\(s\): CN:000002",
    ):
        apply_research_allocation(
            allocation,
            ranking=ranking,
            root=root,
            applied_at=dt.datetime.fromisoformat("2026-07-31T09:00:00+08:00"),
        )

    assert (root / "screening.jsonl").read_bytes() == before_screening
    assert (root / "research_queue.jsonl").read_bytes() == before_queue


def test_direct_enqueue_rejects_manager_screen_binding_without_mutation(
    tmp_path: Path,
) -> None:
    root = tmp_path / "coverage" / "cn-a"
    _, before_queue = _write_root(
        root,
        manager_status="completed",
        bind_queue=True,
        bind_screening=False,
    )

    with pytest.raises(
        CoverageValidationError,
        match="cannot write manager-screen/new-protocol",
    ):
        _enqueue(root, "CN:000002")

    assert (root / "research_queue.jsonl").read_bytes() == before_queue


def test_direct_enqueue_rejects_legacy_transition_binding(tmp_path: Path) -> None:
    root = tmp_path / "coverage" / "cn-a"
    _write_root(
        root,
        manager_status="completed",
        bind_queue=False,
        bind_screening=False,
    )
    queue_path = root / "research_queue.jsonl"
    queue = json.loads(queue_path.read_text(encoding="utf-8").splitlines()[0])
    queue["legacy_transition_run_id"] = "legacy-transition-001"
    write_jsonl(queue_path, [queue])
    before = queue_path.read_bytes()

    with pytest.raises(CoverageValidationError, match="CN:000001"):
        _enqueue(root)

    assert queue_path.read_bytes() == before


def test_direct_enqueue_rejects_symbol_owned_only_by_sealed_scope(
    tmp_path: Path,
) -> None:
    root = tmp_path / "coverage" / "cn-a"
    _write_root(
        root,
        manager_status="completed",
        bind_queue=False,
        bind_screening=False,
    )
    _seal_scope(root, "CN:000001")
    before = (root / "research_queue.jsonl").read_bytes()

    with pytest.raises(CoverageValidationError, match="CN:000001"):
        _enqueue(root)

    assert (root / "research_queue.jsonl").read_bytes() == before


def test_direct_enqueue_preserves_determinable_legacy_compatibility(
    tmp_path: Path,
) -> None:
    root = tmp_path / "coverage" / "cn-a"
    _write_root(
        root,
        manager_status="completed",
        bind_queue=False,
        bind_screening=False,
    )

    path = _enqueue(root)

    record = next(
        item
        for item in (
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
        )
        if item["symbol"] == "CN:000001"
    )
    assert record["task_type"] == "initial_research"


def test_direct_enqueue_fails_closed_when_scope_seal_is_corrupt(
    tmp_path: Path,
) -> None:
    root = tmp_path / "coverage" / "cn-a"
    _write_root(
        root,
        manager_status="completed",
        bind_queue=False,
        bind_screening=False,
    )
    manifest_path = _seal_scope(root, "CN:000002")
    manifest_path.write_text("{}", encoding="utf-8")
    before = (root / "research_queue.jsonl").read_bytes()

    with pytest.raises(
        CoverageValidationError,
        match="cannot determine legacy ownership",
    ):
        _enqueue(root)

    assert (root / "research_queue.jsonl").read_bytes() == before
