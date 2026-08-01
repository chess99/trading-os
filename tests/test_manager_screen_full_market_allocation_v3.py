from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from tests.test_manager_screen_allocation_v3 import (
    FROZEN_AT,
    PROFILE_AT,
    RUN_ID,
    _manager,
)
from tests.test_manager_screen_allocation_v3_suspension import (
    SUSPENDED_AT,
    _ready_repository,
    _suspend,
)
from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
from trading_os.research_assets.sealing import seal_json, verify_sealed

PREPARED_AT = SUSPENDED_AT + dt.timedelta(minutes=30)
RECORDED_AT = PREPARED_AT + dt.timedelta(minutes=5)
V3_SYMBOL = "CN:000201"


def _relative(path: Path, repository_root: Path) -> str:
    return path.resolve().relative_to(repository_root.resolve()).as_posix()


def _add_v3_candidate(root: Path) -> None:
    repository_root = root.parent.parent.resolve()
    batch_dir = root / "manager-screen" / RUN_ID / "batch-v3"
    batch_path = batch_dir / "batch.json"
    batch_seal = seal_json(
        batch_path,
        {
            "schema_version": 1,
            "run_id": RUN_ID,
            "batch_id": "batch-v3",
            "policy": {
                "decision_contract_version": 3,
                "quick_profile_effort_budget_hours": 1.5,
            },
            "members": [
                {
                    "symbol": V3_SYMBOL,
                    "name": "全市场候选公司",
                    "scope_ordinal": 201,
                }
            ],
        },
        artifact_type="manager_screen_batch",
        sealed_at=FROZEN_AT + dt.timedelta(minutes=1),
    )
    packet_path = batch_dir / "packet.json"
    packet_seal = seal_json(
        packet_path,
        {
            "schema_version": 1,
            "run_id": RUN_ID,
            "batch_id": "batch-v3",
            "batch_sha256": batch_seal.sha256,
        },
        artifact_type="manager_screen_packet",
        sealed_at=FROZEN_AT + dt.timedelta(minutes=2),
    )
    result_path = batch_dir / "result.json"
    decision = {
        "symbol": V3_SYMBOL,
        "route": "research_candidate",
        "one_line_reason": "完整市场比较后再决定是否购买快速画像预算。",
        "decisive_question": "可持续所有者收益是否足以覆盖估值与治理风险？",
        "evidence_ids": [f"snapshot:{V3_SYMBOL}"],
        "revisit_triggers": [],
        "confidence": "medium",
        "risk_acknowledgements": [],
    }
    result_seal = seal_json(
        result_path,
        {
            "schema_version": 1,
            "run_id": RUN_ID,
            "batch_id": "batch-v3",
            "recorded_at": (FROZEN_AT + dt.timedelta(minutes=3)).isoformat(),
            "batch_path": _relative(batch_path, repository_root),
            "batch_sha256": batch_seal.sha256,
            "packet_path": _relative(packet_path, repository_root),
            "packet_sha256": packet_seal.sha256,
            "manager": _manager(),
            "decisions": [decision],
        },
        artifact_type="manager_screen_result",
        sealed_at=FROZEN_AT + dt.timedelta(minutes=3),
    )
    queue = read_jsonl(root / "research_queue.jsonl")
    queue.append(
        {
            "symbol": V3_SYMBOL,
            "name": "全市场候选公司",
            "priority": 3,
            "reason": decision["one_line_reason"],
            "target_company_dir": "research/companies/CN/000201",
            "task_type": "manager_screen",
            "status": "completed",
            "assigned_agent": None,
            "started_at": None,
            "finished_at": (FROZEN_AT + dt.timedelta(minutes=3)).isoformat(),
            "failure_reason": None,
            "result_path": _relative(result_path, repository_root),
            "next_action": "等待全市场统一配置研究资本。",
            "manager_screen_run_id": RUN_ID,
            "manager_screen_batch_id": "batch-v3",
            "manager_screen_route": "research_candidate",
            "manager_screen_result_path": _relative(result_path, repository_root),
            "manager_screen_result_sha256": result_seal.sha256,
            "decisive_question": decision["decisive_question"],
            "evidence_ids": decision["evidence_ids"],
            "revisit_triggers": [],
            "research_budget_state": "candidate_unfunded",
            "stage_history": [],
        }
    )
    write_jsonl(root / "research_queue.jsonl", queue)
    screens = read_jsonl(root / "screening.jsonl")
    screens.append(
        {
            "symbol": V3_SYMBOL,
            "name": "全市场候选公司",
            "decision": "candidate_unfunded",
            "priority": None,
            "reason": decision["one_line_reason"],
            "evidence": decision["evidence_ids"],
            "next_action": "等待全市场统一配置研究资本。",
            "manager_screen_run_id": RUN_ID,
            "manager_screen_batch_id": "batch-v3",
            "manager_screen_route": "research_candidate",
            "manager_screen_result_path": _relative(result_path, repository_root),
            "manager_screen_result_sha256": result_seal.sha256,
            "decisive_question": decision["decisive_question"],
            "confidence": "medium",
            "revisit_triggers": [],
            "research_budget_state": "candidate_unfunded",
        }
    )
    write_jsonl(root / "screening.jsonl", screens)


def _add_terminal_decision_batch(
    root: Path,
    *,
    batch_id: str,
    decisions: list[tuple[str, str, int]],
) -> None:
    repository_root = root.parent.parent.resolve()
    batch_dir = root / "manager-screen" / RUN_ID / batch_id
    batch_path = batch_dir / "batch.json"
    members = [
        {
            "symbol": symbol,
            "name": f"Calibration candidate {symbol}",
            "scope_ordinal": scope_ordinal,
        }
        for symbol, _, scope_ordinal in decisions
    ]
    batch_seal = seal_json(
        batch_path,
        {
            "schema_version": 1,
            "run_id": RUN_ID,
            "batch_id": batch_id,
            "policy": {
                "decision_contract_version": 3,
                "quick_profile_effort_budget_hours": 1.5,
            },
            "members": members,
        },
        artifact_type="manager_screen_batch",
        sealed_at=FROZEN_AT + dt.timedelta(minutes=1),
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
        sealed_at=FROZEN_AT + dt.timedelta(minutes=2),
    )
    result_path = batch_dir / "result.json"
    result_decisions = [
        {
            "symbol": symbol,
            "route": route,
            "one_line_reason": f"Keep the original {route} route immutable.",
            "decisive_question": f"What evidence would change the {route} route for {symbol}?",
            "evidence_ids": [f"snapshot:{symbol}"],
            "revisit_triggers": [
                {
                    "type": "filing",
                    "condition": "A new audited filing becomes available.",
                    "reason": "New primary evidence can change the original route.",
                }
            ],
            "confidence": "medium",
            "risk_acknowledgements": [],
        }
        for symbol, route, _ in decisions
    ]
    result_seal = seal_json(
        result_path,
        {
            "schema_version": 1,
            "run_id": RUN_ID,
            "batch_id": batch_id,
            "recorded_at": (FROZEN_AT + dt.timedelta(minutes=3)).isoformat(),
            "batch_path": _relative(batch_path, repository_root),
            "batch_sha256": batch_seal.sha256,
            "packet_path": _relative(packet_path, repository_root),
            "packet_sha256": packet_seal.sha256,
            "manager": _manager(),
            "decisions": result_decisions,
        },
        artifact_type="manager_screen_result",
        sealed_at=FROZEN_AT + dt.timedelta(minutes=3),
    )
    queue = read_jsonl(root / "research_queue.jsonl")
    screens = read_jsonl(root / "screening.jsonl")
    for member, decision in zip(members, result_decisions, strict=True):
        symbol = member["symbol"]
        result_relative = _relative(result_path, repository_root)
        queue.append(
            {
                "symbol": symbol,
                "name": member["name"],
                "priority": 3,
                "reason": decision["one_line_reason"],
                "target_company_dir": f"research/companies/CN/{symbol.split(':')[1]}",
                "task_type": "manager_screen",
                "status": "completed",
                "assigned_agent": None,
                "started_at": None,
                "finished_at": (FROZEN_AT + dt.timedelta(minutes=3)).isoformat(),
                "failure_reason": None,
                "result_path": result_relative,
                "next_action": "Wait for a sealed full-market allocation decision.",
                "manager_screen_run_id": RUN_ID,
                "manager_screen_batch_id": batch_id,
                "manager_screen_route": decision["route"],
                "manager_screen_result_path": result_relative,
                "manager_screen_result_sha256": result_seal.sha256,
                "decisive_question": decision["decisive_question"],
                "evidence_ids": decision["evidence_ids"],
                "revisit_triggers": decision["revisit_triggers"],
                "stage_history": [],
            }
        )
        screens.append(
            {
                "symbol": symbol,
                "name": member["name"],
                "decision": decision["route"],
                "priority": None,
                "reason": decision["one_line_reason"],
                "evidence": decision["evidence_ids"],
                "next_action": "Wait for a sealed full-market allocation decision.",
                "manager_screen_run_id": RUN_ID,
                "manager_screen_batch_id": batch_id,
                "manager_screen_route": decision["route"],
                "manager_screen_result_path": result_relative,
                "manager_screen_result_sha256": result_seal.sha256,
                "decisive_question": decision["decisive_question"],
                "confidence": "medium",
                "revisit_triggers": decision["revisit_triggers"],
            }
        )
    write_jsonl(root / "research_queue.jsonl", queue)
    write_jsonl(root / "screening.jsonl", screens)


def _calibration_review(
    symbol: str,
    *,
    outcome: str = "material_error_confirmed",
    material_error_count: int = 1,
) -> dict:
    error_types = [
        "verifiable_factual_error",
        "material_risk_omission",
        "security_identity_error",
        "decision_contract_violation",
    ]
    evidence_id = f"calibration:{symbol}:primary"
    adjudication = {
        "performed": True,
        "outcome": outcome,
        "finding": f"One terminal adjudication was recorded for {symbol}.",
        "evidence_ids": [evidence_id],
    }
    return {
        "symbol": symbol,
        "material_errors": [
            {
                "type": error_type,
                "finding": f"Confirmed calibration finding {index + 1} for {symbol}.",
                "evidence_ids": [evidence_id],
            }
            for index, error_type in enumerate(error_types[:material_error_count])
        ],
        "route_disagreement": {
            "present": False,
            "finding": None,
            "evidence_ids": [],
        },
        "adjudication": adjudication,
    }


def _add_calibration_result(
    root: Path,
    *,
    batch_id: str,
    reviews: list[dict],
    sealed_at: dt.datetime | None = None,
) -> None:
    repository_root = root.parent.parent.resolve()
    batch_dir = root / "manager-screen" / RUN_ID / batch_id
    manager_result_path = batch_dir / "result.json"
    manager_result_seal = verify_sealed(manager_result_path)
    calibration_id = "calibration-material-error"
    result_path = batch_dir / "calibration" / calibration_id / "result.json"
    material_error_symbols = [
        review["symbol"] for review in reviews if review["material_errors"]
    ]
    adjudicated_symbols = [
        review["symbol"]
        for review in reviews
        if review["adjudication"]["performed"] is True
    ]
    calibration_at = sealed_at or FROZEN_AT + dt.timedelta(minutes=4)
    seal_json(
        result_path,
        {
            "schema_version": 1,
            "run_id": RUN_ID,
            "batch_id": batch_id,
            "calibration_id": calibration_id,
            "recorded_at": calibration_at.isoformat(),
            "manager_result_path": _relative(manager_result_path, repository_root),
            "manager_result_sha256": manager_result_seal.sha256,
            "reviews": reviews,
            "summary": {
                "status": "material_error",
                "reviewed_sample_count": len(reviews),
                "material_error_count": sum(
                    len(review["material_errors"]) for review in reviews
                ),
                "material_error_symbols": material_error_symbols,
                "route_disagreement_count": 0,
                "adjudication_count": len(adjudicated_symbols),
                "adjudicated_symbols": adjudicated_symbols,
                "route_disagreement_is_material_error": False,
                "non_blocking": True,
            },
        },
        artifact_type="manager_screen_calibration_result",
        sealed_at=calibration_at,
    )


def _extend_mock_scope(
    root: Path,
    *,
    decisions: list[tuple[str, str, int]],
    batch_id: str,
) -> None:
    import trading_os.research_assets.manager_screen_full_market_allocation_v3 as full

    scope = full._scope_members(base=root, run_id=RUN_ID)
    for symbol, _, scope_ordinal in decisions:
        scope[symbol] = {
            "scope_ordinal": scope_ordinal,
            "name": f"Calibration candidate {symbol}",
            "batch_id": batch_id,
        }


def _materialize_quote_impact_replacement(
    root: Path,
    *,
    symbol: str,
    sealed: bool,
) -> dict:
    import trading_os.research_assets.manager_screen_full_market_allocation_v3 as full

    repository_root = root.parent.parent.resolve()
    suspension_path = (
        root
        / "manager-screen"
        / RUN_ID
        / "governance"
        / "allocation-v3"
        / "suspension.json"
    )
    suspension = json.loads(suspension_path.read_text(encoding="utf-8"))
    suspension_seal = verify_sealed(suspension_path)
    member = next(item for item in suspension["members"] if item["symbol"] == symbol)
    original_path = member["manager_screen_result_path"]
    original_sha256 = member["manager_screen_result_sha256"]
    original = json.loads((repository_root / original_path).read_text(encoding="utf-8"))
    batch_id = original["batch_id"]
    full._scope_members(base=root, run_id=RUN_ID)[symbol]["batch_id"] = batch_id
    original_decision = next(
        decision for decision in original["decisions"] if decision["symbol"] == symbol
    )
    replacement = {
        "symbol": symbol,
        "route": "watch",
        "one_line_reason": "Sealed quote evidence changed the effective manager route.",
        "decisive_question": f"Does the amended quote preserve the thesis for {symbol}?",
        "evidence_ids": [f"quote-amendment:{symbol}"],
        "revisit_triggers": [
            {
                "type": "price",
                "condition": "The next sealed quote moves another 20 percent.",
                "reason": "A further price move can change the research priority.",
            }
        ],
        "confidence": "high",
        "risk_acknowledgements": [],
    }
    recorded_at = (SUSPENDED_AT + dt.timedelta(minutes=10)).isoformat()
    result_payload = {
        "schema_version": 1,
        "run_id": RUN_ID,
        "batch_id": batch_id,
        "review_id": "post-suspension-quote-impact",
        "recorded_at": recorded_at,
        "original_result_path": original_path,
        "original_result_sha256": original_sha256,
        "reviews": [
            {
                "symbol": symbol,
                "action": "replacement",
                "old_route": original_decision["route"],
                "effective_decision": replacement,
            }
        ],
    }
    result_path = (
        root
        / "manager-screen"
        / RUN_ID
        / "governance"
        / "quote-impact-evolution"
        / f"{symbol.replace(':', '-')}.json"
    )
    if sealed:
        result_seal = seal_json(
            result_path,
            result_payload,
            artifact_type="manager_screen_quote_impact_result",
            sealed_at=SUSPENDED_AT + dt.timedelta(minutes=10),
        )
        result_sha256 = result_seal.sha256
    else:
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(
            json.dumps(
                result_payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
        result_sha256 = full._payload_sha256(result_payload)
    result_relative = _relative(result_path, repository_root)
    queue_path = root / "research_queue.jsonl"
    screening_path = root / "screening.jsonl"
    queue = _by_symbol(queue_path)
    screens = _by_symbol(screening_path)
    queue_row = queue[symbol]
    queue_row.update(
        {
            "manager_screen_batch_id": batch_id,
            "manager_screen_route": replacement["route"],
            "manager_screen_result_path": result_relative,
            "manager_screen_result_sha256": result_sha256,
            "decisive_question": replacement["decisive_question"],
            "evidence_ids": replacement["evidence_ids"],
            "revisit_triggers": replacement["revisit_triggers"],
            "reason": replacement["one_line_reason"],
            "finished_at": recorded_at,
            "result_path": result_relative,
        }
    )
    queue_row["stage_history"] = list(queue_row["stage_history"]) + [
        {
            "stage": "manager_screen_quote_impact",
            "status": "completed",
            "finished_at": recorded_at,
            "run_id": RUN_ID,
            "batch_id": batch_id,
            "review_id": result_payload["review_id"],
            "old_route": original_decision["route"],
            "route": replacement["route"],
            "result_path": result_relative,
            "result_sha256": result_sha256,
        }
    ]
    screen = screens[symbol]
    screen.update(
        {
            "manager_screen_batch_id": batch_id,
            "manager_screen_route": replacement["route"],
            "manager_screen_result_path": result_relative,
            "manager_screen_result_sha256": result_sha256,
            "decisive_question": replacement["decisive_question"],
            "evidence": replacement["evidence_ids"],
            "revisit_triggers": replacement["revisit_triggers"],
            "reason": replacement["one_line_reason"],
            "confidence": replacement["confidence"],
        }
    )
    assert queue_row["research_budget_suspension_path"] == _relative(
        suspension_path,
        repository_root,
    )
    assert queue_row["research_budget_suspension_sha256"] == suspension_seal.sha256
    write_jsonl(queue_path, list(queue.values()))
    write_jsonl(screening_path, list(screens.values()))
    return {
        "result_path": result_relative,
        "result_sha256": result_sha256,
        "replacement": replacement,
    }


def _ready_full_market(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    import trading_os.research_assets.manager_screen_full_market_allocation_v3 as full

    root = _ready_repository(tmp_path, monkeypatch)
    _suspend(root)
    _add_v3_candidate(root)
    queue_rows = read_jsonl(root / "research_queue.jsonl")
    symbols = sorted(row["symbol"] for row in queue_rows)
    batch_by_symbol = {
        row["symbol"]: row.get("manager_screen_batch_id") for row in queue_rows
    }
    scope = {
        symbol: {
            "scope_ordinal": ordinal,
            "name": f"范围公司{symbol.split(':')[1]}",
            "batch_id": batch_by_symbol[symbol],
        }
        for ordinal, symbol in enumerate(symbols, 1)
    }
    scope[V3_SYMBOL]["name"] = "全市场候选公司"
    monkeypatch.setattr(full, "_scope_members", lambda **_: scope)
    monkeypatch.setattr(
        full,
        "manager_screen_status",
        lambda **_: {
            "screenable_intake_count": len(symbols),
            "completed_company_count": len(symbols),
            "deferred_current_state_count": 0,
            "remaining_unbatched_count": 0,
            "open_batches": 0,
            "open_company_count": 0,
            "control": {"state": "paused"},
            "legacy_transition": {"state": "recorded"},
            "calibration": {"status": "complete"},
            "batches": [],
        },
    )
    monkeypatch.setattr(
        full,
        "_fresh_quote_binding",
        lambda **_: {
            "amendment_id": "quotes-final",
            "path": "coverage/cn-a/snapshots/final-quotes.json",
            "sha256": "a" * 64,
            "effective_at": PREPARED_AT.isoformat(),
            "quote_count": len(symbols),
            "oldest_quote_as_of": (PREPARED_AT - dt.timedelta(days=1)).isoformat(),
            "newest_quote_as_of": (PREPARED_AT - dt.timedelta(days=1)).isoformat(),
            "max_age_seconds": 259200,
            "future_tolerance_seconds": 300,
        },
    )
    monkeypatch.setattr(
        full,
        "_allocation_policy",
        lambda **_: {
            "path": "policies/manager-screening-allocation-v3.json",
            "file_sha256": "b" * 64,
            "payload_sha256": "c" * 64,
            "quick_profile_effort_budget_hours": 1.5,
            "quick_profile_stop_conditions": ["决定性问题在预算内无法解决时停止"],
        },
    )
    return root


def _prepare(root: Path) -> dict:
    from trading_os.research_assets.manager_screen_full_market_allocation_v3 import (
        prepare_manager_screen_full_market_allocation_v3,
    )

    return prepare_manager_screen_full_market_allocation_v3(
        root=root,
        run_id=RUN_ID,
        prepared_at=PREPARED_AT,
    )


def _packet(root: Path) -> dict:
    return json.loads(_packet_path(root).read_text(encoding="utf-8"))


def _packet_path(root: Path) -> Path:
    return (
        root
        / "manager-screen"
        / RUN_ID
        / "governance"
        / "allocation-v3"
        / "full-market"
        / "packet.json"
    )


def _result_path(root: Path) -> Path:
    return _packet_path(root).with_name("result.json")


def _seal_terminal_manifest_dependency(
    root: Path,
    relative: str,
    *,
    sealed_at: dt.datetime = PREPARED_AT - dt.timedelta(minutes=1),
    marker: str = "original",
) -> Path:
    path = root / "manager-screen" / RUN_ID / relative
    seal_json(
        path,
        {"schema_version": 1, "marker": marker},
        artifact_type="test_terminal_governance_dependency",
        sealed_at=sealed_at,
    )
    return path


def _scope_status(*, calibration: dict, batches: list[dict]) -> dict:
    return {
        "screenable_intake_count": 1,
        "completed_company_count": 1,
        "deferred_current_state_count": 0,
        "remaining_unbatched_count": 0,
        "open_batches": 0,
        "open_company_count": 0,
        "control": {"state": "paused"},
        "legacy_transition": {"state": "recorded"},
        "calibration": calibration,
        "batches": batches,
    }


def test_full_scope_accepts_multiple_errors_with_one_adjudication_per_symbol(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_os.research_assets.manager_screen_full_market_allocation_v3 as full

    historical_error_batches = [
        {
            "batch_id": "batch-001",
            "calibration": {
                "status": "material_error",
                "planned_sample_count": 4,
                "reviewed_sample_count": 4,
                "missing_sample_count": 0,
                "material_error_count": 3,
                "material_error_symbols": ["CN:000001"],
                "adjudication_count": 1,
                "adjudicated_symbols": ["CN:000001"],
                "result_sha256": "a" * 64,
            },
        },
        {
            "batch_id": "batch-002",
            "calibration": {
                "status": "material_error",
                "planned_sample_count": 5,
                "reviewed_sample_count": 5,
                "missing_sample_count": 0,
                "material_error_count": 5,
                "material_error_symbols": [
                    "CN:000101",
                    "CN:000102",
                    "CN:000103",
                ],
                "adjudication_count": 3,
                "adjudicated_symbols": [
                    "CN:000101",
                    "CN:000102",
                    "CN:000103",
                ],
                "result_sha256": "b" * 64,
            },
        },
        {
            "batch_id": "batch-003",
            "calibration": {
                "status": "complete",
                "planned_sample_count": 3,
                "reviewed_sample_count": 3,
                "missing_sample_count": 0,
                "material_error_count": 0,
                "material_error_symbols": [],
                "adjudication_count": 0,
                "adjudicated_symbols": [],
                "result_sha256": "c" * 64,
            },
        },
    ]
    status = _scope_status(
        calibration={
            "status": "material_error",
            "planned_sample_count": 12,
            "reviewed_sample_count": 12,
            "missing_sample_count": 0,
            "material_error_count": 8,
            "material_error_symbols": [
                "CN:000001",
                "CN:000101",
                "CN:000102",
                "CN:000103",
            ],
            "adjudication_count": 4,
            "adjudicated_symbols": [
                "CN:000001",
                "CN:000101",
                "CN:000102",
                "CN:000103",
            ],
        },
        batches=historical_error_batches,
    )
    monkeypatch.setattr(full, "manager_screen_status", lambda **_: status)

    assert full._require_full_scope_ready(base=tmp_path, run_id=RUN_ID) is status


@pytest.mark.parametrize(
    ("aggregate_status", "batch_calibration", "message"),
    [
        (
            "missing",
            {
                "status": "missing",
                "planned_sample_count": 3,
                "reviewed_sample_count": 0,
                "missing_sample_count": 3,
                "material_error_count": 0,
                "material_error_symbols": [],
                "adjudication_count": 0,
                "adjudicated_symbols": [],
            },
            "calibration/QA must be complete",
        ),
        (
            "material_error",
            {
                "status": "material_error",
                "planned_sample_count": 3,
                "reviewed_sample_count": 2,
                "missing_sample_count": 1,
                "material_error_count": 1,
                "material_error_symbols": ["CN:000001"],
                "adjudication_count": 1,
                "adjudicated_symbols": ["CN:000001"],
            },
            "calibration coverage must be complete",
        ),
        (
            "material_error",
            {
                "status": "material_error",
                "planned_sample_count": 3,
                "reviewed_sample_count": 3,
                "missing_sample_count": 0,
                "material_error_count": 2,
                "material_error_symbols": ["CN:000001", "CN:000002"],
                "adjudication_count": 1,
                "adjudicated_symbols": ["CN:000001"],
            },
            "each manager-screen material-error company requires one terminal adjudication",
        ),
    ],
)
def test_full_scope_rejects_unfinished_calibration_work(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    aggregate_status: str,
    batch_calibration: dict,
    message: str,
) -> None:
    import trading_os.research_assets.manager_screen_full_market_allocation_v3 as full

    status = _scope_status(
        calibration={"status": aggregate_status},
        batches=[{"batch_id": "batch-001", "calibration": batch_calibration}],
    )
    monkeypatch.setattr(full, "manager_screen_status", lambda **_: status)

    with pytest.raises(full.ManagerScreenFullMarketAllocationV3Error, match=message):
        full._require_full_scope_ready(base=tmp_path, run_id=RUN_ID)


def test_latest_quote_gate_allows_a_batch_frozen_on_the_latest_amendment_without_overlay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_os.research_assets.manager_screen_full_market_allocation_v3 as full

    latest = {"path": "coverage/cn-a/quotes/latest.json", "sha256": "a" * 64}
    status = {
        "batches": [
            {
                "batch_id": "batch-latest",
                "status": "completed",
                "quote_amendment": dict(latest),
            }
        ]
    }
    monkeypatch.setattr(
        full,
        "load_manager_screen_quote_impact_overlay",
        lambda **_: {"state": "absent"},
    )

    full._require_latest_quote_impact_reviews(
        base=tmp_path,
        run_id=RUN_ID,
        status=status,
        latest_quote=latest,
    )


def test_latest_quote_gate_accepts_a_sealed_zero_candidate_terminal_overlay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_os.research_assets.manager_screen_full_market_allocation_v3 as full

    latest = {"path": "coverage/cn-a/quotes/latest.json", "sha256": "a" * 64}
    status = {
        "batches": [
            {
                "batch_id": "batch-stale",
                "status": "completed",
                "quote_amendment": {
                    "path": "coverage/cn-a/quotes/old.json",
                    "sha256": "b" * 64,
                },
            }
        ]
    }
    monkeypatch.setattr(
        full,
        "load_manager_screen_quote_impact_overlay",
        lambda **_: {
            "state": "recorded",
            "candidate_count": 0,
            "automatic_noop": True,
            "quote_amendment_path": latest["path"],
            "quote_amendment_sha256": latest["sha256"],
            "result_path": "coverage/cn-a/reviews/noop/result.json",
            "result_sha256": "c" * 64,
        },
    )

    full._require_latest_quote_impact_reviews(
        base=tmp_path,
        run_id=RUN_ID,
        status=status,
        latest_quote=latest,
    )


@pytest.mark.parametrize(
    "overlay",
    [
        {"state": "absent"},
        {"state": "prepared"},
        {
            "state": "recorded",
            "quote_amendment_path": "coverage/cn-a/quotes/old.json",
            "quote_amendment_sha256": "a" * 64,
            "result_path": "coverage/cn-a/reviews/old/result.json",
            "result_sha256": "c" * 64,
        },
        {
            "state": "recorded",
            "quote_amendment_path": "coverage/cn-a/quotes/latest.json",
            "quote_amendment_sha256": "b" * 64,
            "result_path": "coverage/cn-a/reviews/wrong-sha/result.json",
            "result_sha256": "c" * 64,
        },
    ],
)
def test_latest_quote_gate_rejects_missing_unfinished_or_wrongly_bound_overlay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    overlay: dict,
) -> None:
    import trading_os.research_assets.manager_screen_full_market_allocation_v3 as full

    latest = {"path": "coverage/cn-a/quotes/latest.json", "sha256": "a" * 64}
    status = {
        "batches": [
            {
                "batch_id": "batch-stale",
                "status": "completed",
                "quote_amendment": {
                    "path": "coverage/cn-a/quotes/old.json",
                    "sha256": "d" * 64,
                },
            }
        ]
    }
    monkeypatch.setattr(
        full,
        "load_manager_screen_quote_impact_overlay",
        lambda **_: overlay,
    )

    with pytest.raises(full.ManagerScreenFullMarketAllocationV3Error):
        full._require_latest_quote_impact_reviews(
            base=tmp_path,
            run_id=RUN_ID,
            status=status,
            latest_quote=latest,
        )


def test_confirmed_pass_and_watch_material_errors_enter_candidate_pool(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _ready_full_market(tmp_path, monkeypatch)
    batch_id = "batch-calibration-routes"
    decisions = [
        ("CN:900001", "pass", 9001),
        ("CN:900002", "watch", 9002),
    ]
    _add_terminal_decision_batch(root, batch_id=batch_id, decisions=decisions)
    _add_calibration_result(
        root,
        batch_id=batch_id,
        reviews=[_calibration_review(symbol) for symbol, _, _ in decisions],
    )
    _extend_mock_scope(root, decisions=decisions, batch_id=batch_id)

    _prepare(root)
    candidates = _packet(root)["candidates"]
    by_symbol = {candidate["symbol"]: candidate for candidate in candidates}

    assert len(candidates) == 199
    for symbol, route, _ in decisions:
        candidate = by_symbol[symbol]
        context = candidate["calibration_material_error"]
        assert candidate["origin"] == "calibration_material_error"
        assert candidate["original_route"] == route
        assert context["review"]["symbol"] == symbol
        assert context["adjudication"]["outcome"] == "material_error_confirmed"
        assert context["calibration_result_path"].endswith(
            f"/{batch_id}/calibration/calibration-material-error/result.json"
        )


def test_confirmed_error_context_merges_into_existing_candidates_without_duplicates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _ready_full_market(tmp_path, monkeypatch)
    suspended_symbol = "CN:000006"
    _add_calibration_result(
        root,
        batch_id="batch-v1",
        reviews=[_calibration_review(suspended_symbol, material_error_count=2)],
    )
    _add_calibration_result(
        root,
        batch_id="batch-v3",
        reviews=[_calibration_review(V3_SYMBOL)],
    )

    _prepare(root)
    candidates = _packet(root)["candidates"]
    symbols = [candidate["symbol"] for candidate in candidates]
    by_symbol = {candidate["symbol"]: candidate for candidate in candidates}

    assert len(candidates) == 197
    assert symbols.count(suspended_symbol) == 1
    assert symbols.count(V3_SYMBOL) == 1
    assert by_symbol[suspended_symbol]["origin"] == "suspended_v2"
    assert by_symbol[V3_SYMBOL]["origin"] == "v3_research_candidate"
    assert len(
        by_symbol[suspended_symbol]["calibration_material_error"]["review"][
            "material_errors"
        ]
    ) == 2
    assert by_symbol[V3_SYMBOL]["calibration_material_error"] is not None


def test_confirmed_error_on_irreversible_commitment_becomes_separate_locked_case(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _ready_full_market(tmp_path, monkeypatch)
    symbol = "CN:000004"
    _add_calibration_result(
        root,
        batch_id="batch-v1",
        reviews=[_calibration_review(symbol, material_error_count=2)],
    )

    summary = _prepare(root)
    packet = _packet(root)
    cases = packet["locked_calibration_cases"]

    assert summary["locked_calibration_case_count"] == 1
    assert packet["candidate_count"] == 197
    assert packet["capacity"]["selection_capacity"] == 196
    assert symbol not in {candidate["symbol"] for candidate in packet["candidates"]}
    assert len(cases) == 1
    case = cases[0]
    assert case["symbol"] == symbol
    assert case["commitment_classification"]["commitment_class"] == "irreversible"
    assert case["prepared_queue_row"]["status"] == "running"
    calibration = case["calibration_material_error"]
    assert calibration["review"]["symbol"] == symbol
    assert calibration["adjudication"]["outcome"] == "material_error_confirmed"
    assert calibration["calibration_result_sha256"]
    assert calibration["review_sha256"]
    assert calibration["adjudication_sha256"]


def test_locked_calibration_defer_record_and_replay_preserve_live_queue_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_os.research_assets.manager_screen_full_market_allocation_v3 import (
        apply_manager_screen_full_market_allocation_v3,
        manager_screen_full_market_allocation_v3_final_status,
    )

    root = _ready_full_market(tmp_path, monkeypatch)
    symbol = "CN:000004"
    _add_calibration_result(
        root,
        batch_id="batch-v1",
        reviews=[_calibration_review(symbol)],
    )
    _prepare(root)
    queue_before = dict(_by_symbol(root / "research_queue.jsonl")[symbol])
    screen_before = dict(_by_symbol(root / "screening.jsonl")[symbol])

    recorded = _record(root, set())
    queue_after = _by_symbol(root / "research_queue.jsonl")[symbol]
    screen_after = _by_symbol(root / "screening.jsonl")[symbol]
    binding = queue_after["manager_screen_locked_calibration_remediation"]

    assert recorded["summary"]["locked_calibration_deferred_count"] == 1
    assert binding["remediation"] == "defer_remediation"
    assert binding == screen_after["manager_screen_locked_calibration_remediation"]
    for field in (
        "task_type",
        "status",
        "assigned_agent",
        "started_at",
        "finished_at",
        "result_path",
        "effort_budget_hours",
        "preceding_stage",
    ):
        assert queue_after.get(field) == queue_before.get(field)
    for field, value in screen_before.items():
        assert screen_after[field] == value
    assert queue_after["stage_history"][:-1] == queue_before["stage_history"]
    assert queue_after["stage_history"][-1]["stage"] == (
        "manager_screen_locked_calibration_remediation"
    )

    screening = _by_symbol(root / "screening.jsonl")
    screening[symbol].pop("manager_screen_locked_calibration_remediation")
    write_jsonl(root / "screening.jsonl", list(screening.values()))
    repaired = apply_manager_screen_full_market_allocation_v3(root=root, run_id=RUN_ID)
    replayed = apply_manager_screen_full_market_allocation_v3(root=root, run_id=RUN_ID)
    status = manager_screen_full_market_allocation_v3_final_status(
        root=root,
        run_id=RUN_ID,
    )

    assert repaired["materialization"]["screening_repaired_count"] == 1
    assert replayed["materialization"]["queue_repaired_count"] == 0
    assert replayed["materialization"]["screening_repaired_count"] == 0
    assert status["finalized"] is True


def test_locked_calibration_remediation_cannot_omit_error_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_os.research_assets.manager_screen_full_market_allocation_v3 import (
        ManagerScreenFullMarketAllocationV3Error,
        record_manager_screen_full_market_allocation_v3,
    )

    root = _ready_full_market(tmp_path, monkeypatch)
    symbol = "CN:000004"
    _add_calibration_result(
        root,
        batch_id="batch-v1",
        reviews=[_calibration_review(symbol)],
    )
    _prepare(root)
    submission = _submission(_packet(root), funded=set())
    remediation = submission["locked_calibration_remediations"][0]
    remediation["evidence_ids"] = [
        item
        for item in remediation["evidence_ids"]
        if not item.startswith("calibration:")
    ]

    with pytest.raises(
        ManagerScreenFullMarketAllocationV3Error,
        match="locked remediation omits confirmed calibration-error evidence",
    ):
        record_manager_screen_full_market_allocation_v3(
            root=root,
            run_id=RUN_ID,
            submission=submission,
            recorded_at=RECORDED_AT,
        )
    assert not _result_path(root).exists()


def test_resolved_locked_calibration_binds_post_error_sealed_work(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _ready_full_market(tmp_path, monkeypatch)
    symbol = "CN:000005"
    _add_calibration_result(
        root,
        batch_id="batch-v1",
        reviews=[_calibration_review(symbol)],
        sealed_at=PROFILE_AT - dt.timedelta(minutes=1),
    )
    _prepare(root)
    packet = _packet(root)
    case = packet["locked_calibration_cases"][0]
    sealed_work = case["commitment_classification"]["sealed_progress"][0]
    submission = _submission(packet, funded=set())
    remediation = submission["locked_calibration_remediations"][0]
    remediation.update(
        {
            "remediation": "resolved_by_existing_sealed_work",
            "resolved_work_sha256": sealed_work["sha256"],
            "decisive_question": None,
            "revisit_triggers": [],
        }
    )

    before = dict(_by_symbol(root / "research_queue.jsonl")[symbol])
    from trading_os.research_assets.manager_screen_full_market_allocation_v3 import (
        record_manager_screen_full_market_allocation_v3,
    )

    recorded = record_manager_screen_full_market_allocation_v3(
        root=root,
        run_id=RUN_ID,
        submission=submission,
        recorded_at=RECORDED_AT,
    )
    after = _by_symbol(root / "research_queue.jsonl")[symbol]
    binding = after["manager_screen_locked_calibration_remediation"]

    assert recorded["summary"]["locked_calibration_resolved_count"] == 1
    assert binding["resolved_work_sha256"] == sealed_work["sha256"]
    assert binding["evidence_ids"] == remediation["evidence_ids"]
    assert after["task_type"] == before["task_type"] == "quick_profile"
    assert after["status"] == before["status"] == "completed"
    assert after["result_path"] == before["result_path"]


def test_resolved_locked_calibration_rejects_work_that_predates_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_os.research_assets.manager_screen_full_market_allocation_v3 import (
        ManagerScreenFullMarketAllocationV3Error,
        record_manager_screen_full_market_allocation_v3,
    )

    root = _ready_full_market(tmp_path, monkeypatch)
    symbol = "CN:000005"
    _add_calibration_result(
        root,
        batch_id="batch-v1",
        reviews=[_calibration_review(symbol)],
    )
    _prepare(root)
    packet = _packet(root)
    case = packet["locked_calibration_cases"][0]
    sealed_work = case["commitment_classification"]["sealed_progress"][0]
    submission = _submission(packet, funded=set())
    submission["locked_calibration_remediations"][0].update(
        {
            "remediation": "resolved_by_existing_sealed_work",
            "resolved_work_sha256": sealed_work["sha256"],
            "decisive_question": None,
            "revisit_triggers": [],
        }
    )

    with pytest.raises(
        ManagerScreenFullMarketAllocationV3Error,
        match="resolved work must postdate the confirmed calibration error",
    ):
        record_manager_screen_full_market_allocation_v3(
            root=root,
            run_id=RUN_ID,
            submission=submission,
            recorded_at=RECORDED_AT,
        )


def test_targeted_locked_calibration_is_only_a_manager_approval_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_os.research_assets.profile_workflow import approve_targeted_followup

    root = _ready_full_market(tmp_path, monkeypatch)
    symbol = "CN:000005"
    queue = _by_symbol(root / "research_queue.jsonl")
    screens = _by_symbol(root / "screening.jsonl")
    queue[symbol]["profile_cycle_id"] = "activation-cycle"
    screens[symbol]["decision"] = "targeted_followup_candidate"
    write_jsonl(root / "research_queue.jsonl", list(queue.values()))
    write_jsonl(root / "screening.jsonl", list(screens.values()))
    _add_calibration_result(
        root,
        batch_id="batch-v1",
        reviews=[_calibration_review(symbol)],
        sealed_at=PROFILE_AT - dt.timedelta(minutes=1),
    )
    _prepare(root)
    packet = _packet(root)
    case = packet["locked_calibration_cases"][0]
    submission = _submission(packet, funded=set())
    remediation = submission["locked_calibration_remediations"][0]
    remediation.update(
        {
            "remediation": "targeted_remediation_candidate",
            "revisit_triggers": [],
        }
    )

    from trading_os.research_assets.manager_screen_full_market_allocation_v3 import (
        record_manager_screen_full_market_allocation_v3,
    )

    record_manager_screen_full_market_allocation_v3(
        root=root,
        run_id=RUN_ID,
        submission=submission,
        recorded_at=RECORDED_AT,
    )
    candidate_queue = _by_symbol(root / "research_queue.jsonl")[symbol]
    assert candidate_queue["task_type"] == "quick_profile"
    assert candidate_queue["status"] == "completed"
    assert "targeted_followup_approval_sha256" not in candidate_queue

    repository_root = root.parent.parent
    policy_path = repository_root / "policies" / "research-allocation.json"
    source_policy = Path(__file__).resolve().parents[1] / "policies" / "research-allocation.json"
    policy_path.write_bytes(source_policy.read_bytes())
    policy = json.loads(policy_path.read_text(encoding="utf-8"))["payload"]
    approved = approve_targeted_followup(
        root=root,
        symbol=symbol,
        manager="/root",
        reason="Explicitly approve only the calibration-bound targeted remediation.",
        policy=policy,
        approved_at=RECORDED_AT + dt.timedelta(minutes=1),
    )

    approved_queue = _by_symbol(root / "research_queue.jsonl")[symbol]
    assert approved["task_type"] == "targeted_followup"
    assert approved_queue["task_type"] == "targeted_followup"
    assert approved_queue["status"] == "pending"
    assert approved_queue["decisive_question"] == remediation["decisive_question"]
    assert approved_queue["evidence_ids"] == remediation["evidence_ids"]
    approved_screen = _by_symbol(root / "screening.jsonl")[symbol]
    assert approved_screen["decisive_question"] == remediation["decisive_question"]
    assert approved_screen["evidence"][: len(remediation["evidence_ids"])] == (
        remediation["evidence_ids"]
    )
    assert approved_queue["manager_screen_locked_calibration_remediation"][
        "locked_calibration_case_sha256"
    ] == case["locked_calibration_case_sha256"]

    from trading_os.research_assets import profile_workflow
    from trading_os.research_assets.profile_workflow import claim_profile_task
    from trading_os.research_assets.research_allocation import ResearchAllocationError

    agent = "/root/locked-remediation-researcher"
    claim_profile_task(
        root=root,
        agent=agent,
        claimed_at=RECORDED_AT + dt.timedelta(minutes=2),
        symbol=symbol,
        run_id=RUN_ID,
    )
    running = _by_symbol(root / "research_queue.jsonl")[symbol]
    package = {
        "manager_screen_binding": {
            "result_path": case["effective_decision_source_path"],
            "result_sha256": case["effective_decision_source_sha256"],
            "decisive_question": case["original_decisive_question"],
            "evidence_ids": case["original_evidence_ids"],
        },
        "decisive_answer": {},
        "provenance": {"agent": agent},
    }
    with pytest.raises(
        ResearchAllocationError,
        match="locked calibration brief",
    ):
        profile_workflow._validate_manager_bound_submission(
            package,
            queue_record=running,
            base=root,
            repository_root=repository_root,
            symbol=symbol,
        )
    locked_binding = running["manager_screen_locked_calibration_remediation"]
    package["manager_screen_binding"] = {
        "result_path": locked_binding["allocation_result_path"],
        "result_sha256": locked_binding["allocation_result_sha256"],
        "decisive_question": locked_binding["decisive_question"],
        "evidence_ids": locked_binding["evidence_ids"],
    }
    profile_workflow._validate_manager_bound_submission(
        package,
        queue_record=running,
        base=root,
        repository_root=repository_root,
        symbol=symbol,
    )


def test_manager_upheld_material_error_does_not_add_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _ready_full_market(tmp_path, monkeypatch)
    batch_id = "batch-calibration-upheld"
    decisions = [("CN:900003", "watch", 9003)]
    _add_terminal_decision_batch(root, batch_id=batch_id, decisions=decisions)
    _add_calibration_result(
        root,
        batch_id=batch_id,
        reviews=[
            _calibration_review("CN:900003", outcome="manager_upheld")
        ],
    )
    _extend_mock_scope(root, decisions=decisions, batch_id=batch_id)

    _prepare(root)
    candidates = _packet(root)["candidates"]

    assert len(candidates) == 197
    assert "CN:900003" not in {candidate["symbol"] for candidate in candidates}


@pytest.mark.parametrize(
    "forgery",
    [
        "calibration_result_sha256",
        "review_sha256",
        "review_content",
        "adjudication_sha256",
        "adjudication_content",
    ],
)
def test_resealed_packet_rejects_tampered_calibration_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    forgery: str,
) -> None:
    import trading_os.research_assets.manager_screen_full_market_allocation_v3 as full

    root = _ready_full_market(tmp_path, monkeypatch)
    batch_id = "batch-calibration-tamper"
    symbol = "CN:900004"
    decisions = [(symbol, "pass", 9004)]
    _add_terminal_decision_batch(root, batch_id=batch_id, decisions=decisions)
    _add_calibration_result(
        root,
        batch_id=batch_id,
        reviews=[_calibration_review(symbol)],
    )
    _extend_mock_scope(root, decisions=decisions, batch_id=batch_id)
    _prepare(root)
    packet = _packet(root)
    candidate = next(item for item in packet["candidates"] if item["symbol"] == symbol)
    context = candidate["calibration_material_error"]

    if forgery == "calibration_result_sha256":
        context["calibration_result_sha256"] = "f" * 64
    elif forgery == "review_sha256":
        context["review_sha256"] = "f" * 64
    elif forgery == "review_content":
        context["review"]["material_errors"] = []
        context["review_sha256"] = full._payload_sha256(context["review"])
    elif forgery == "adjudication_sha256":
        context["adjudication_sha256"] = "f" * 64
    else:
        context["adjudication"]["outcome"] = "manager_upheld"
        context["review"]["adjudication"] = dict(context["adjudication"])
        context["adjudication_sha256"] = full._payload_sha256(
            context["adjudication"]
        )
        context["review_sha256"] = full._payload_sha256(context["review"])

    candidate_core = {
        key: value for key, value in candidate.items() if key != "candidate_sha256"
    }
    candidate["candidate_sha256"] = full._payload_sha256(candidate_core)
    packet["candidates_sha256"] = full._payload_sha256(packet["candidates"])
    path = _packet_path(root)
    path.unlink()
    path.with_name(f"{path.name}.seal.json").unlink()
    seal_json(
        path,
        packet,
        artifact_type=full.PACKET_ARTIFACT_TYPE,
        sealed_at=PREPARED_AT,
    )

    with pytest.raises(full.ManagerScreenFullMarketAllocationV3Error):
        _prepare(root)


def _allocation_evidence_ids(candidate: dict) -> list[str]:
    evidence_ids = list(candidate["evidence_ids"])
    calibration = candidate.get("calibration_material_error")
    if isinstance(calibration, dict):
        review = calibration["review"]
        for error in review["material_errors"]:
            evidence_ids.extend(error["evidence_ids"])
        evidence_ids.extend(calibration["adjudication"]["evidence_ids"])
    return list(dict.fromkeys(evidence_ids))


def _locked_calibration_evidence_ids(case: dict) -> list[str]:
    evidence_ids = list(case["original_evidence_ids"])
    calibration = case["calibration_material_error"]
    for error in calibration["review"]["material_errors"]:
        evidence_ids.extend(error["evidence_ids"])
    evidence_ids.extend(calibration["adjudication"]["evidence_ids"])
    return list(dict.fromkeys(evidence_ids))


def _locked_remediation(case: dict, *, remediation: str = "defer_remediation") -> dict:
    return {
        "symbol": case["symbol"],
        "locked_calibration_case_sha256": case[
            "locked_calibration_case_sha256"
        ],
        "remediation": remediation,
        "reason": "The locked purchase is preserved; remediation remains manager-controlled.",
        "resolved_work_sha256": None,
        "decisive_question": (
            f"Revised remediation question for {case['symbol']} after calibration?"
        ),
        "evidence_ids": _locked_calibration_evidence_ids(case),
        "revisit_triggers": [
            {
                "type": "event",
                "condition": "The locked work reaches a manager-reviewable terminal state.",
                "reason": "Only then can the manager safely revisit remediation budget.",
            }
        ],
    }


def _submission(packet: dict, *, funded: set[str]) -> dict:
    return {
        "schema_version": 1,
        "manager": _manager(),
        "decisions": [
            {
                "symbol": candidate["symbol"],
                "candidate_sha256": candidate["candidate_sha256"],
                "decision": (
                    "fund_quick_profile"
                    if candidate["symbol"] in funded
                    else "defer_full_market"
                ),
                "reason": (
                    "相对全市场候选仍值得购买一次快速画像。"
                    if candidate["symbol"] in funded
                    else "相对完整候选池的边际研究价值不足，本轮不再购买预算。"
                ),
                "decisive_question": (
                    f"全市场分配后的研究问题：{candidate['decisive_question']}"
                ),
                "evidence_ids": _allocation_evidence_ids(candidate),
                "revisit_triggers": (
                    []
                    if candidate["symbol"] in funded
                    else [
                        {
                            "type": "filing",
                            "condition": "下一份正式定期报告披露",
                            "reason": "新证据可改变本轮相对研究价值。",
                        }
                    ]
                ),
            }
            for candidate in packet["candidates"]
        ],
        "locked_calibration_remediations": [
            _locked_remediation(case)
            for case in packet["locked_calibration_cases"]
        ],
    }


def _record(root: Path, funded: set[str]) -> dict:
    from trading_os.research_assets.manager_screen_full_market_allocation_v3 import (
        record_manager_screen_full_market_allocation_v3,
    )

    return record_manager_screen_full_market_allocation_v3(
        root=root,
        run_id=RUN_ID,
        submission=_submission(_packet(root), funded=funded),
        recorded_at=RECORDED_AT,
    )


def _by_symbol(path: Path) -> dict[str, dict]:
    return {row["symbol"]: row for row in read_jsonl(path)}


def test_queue_binding_loader_verifies_final_briefs_without_recursive_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_os.research_assets.manager_screen_full_market_allocation_v3 as full

    root = _ready_full_market(tmp_path, monkeypatch)
    _prepare(root)
    recorded = _record(root, {"CN:000001"})

    def fail_if_status_is_reentered(**_: object) -> dict:
        raise AssertionError("queue binding verification must not re-enter live status")

    monkeypatch.setattr(full, "manager_screen_status", fail_if_status_is_reentered)
    bindings = full.load_manager_screen_full_market_allocation_v3_queue_bindings(
        root=root,
        run_id=RUN_ID,
    )
    result = json.loads(_result_path(root).read_text(encoding="utf-8"))
    decision = next(
        item for item in result["decisions"] if item["symbol"] == "CN:000001"
    )
    binding = bindings["CN:000001"]

    assert binding == {
        "result_path": recorded["result_path"],
        "result_sha256": recorded["result_sha256"],
        "candidate_sha256": decision["candidate_sha256"],
        "decision": decision["decision"],
        "decisive_question": decision["decisive_question"],
        "evidence_ids": decision["evidence_ids"],
    }


def test_final_status_restores_the_sealed_full_scope_postcondition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_os.research_assets.manager_screen_full_market_allocation_v3 as full

    root = _ready_full_market(tmp_path, monkeypatch)
    _prepare(root)
    _record(root, {"CN:000001"})
    symbol_count = len(read_jsonl(root / "research_queue.jsonl"))
    monkeypatch.setattr(
        full,
        "manager_screen_status",
        lambda **_: {
            "screenable_intake_count": symbol_count,
            "completed_company_count": symbol_count - 1,
            "deferred_current_state_count": 1,
            "remaining_unbatched_count": 0,
            "open_batches": 0,
            "open_company_count": 0,
            "control": {"state": "paused"},
            "legacy_transition": {"state": "recorded"},
            "calibration": {"status": "complete"},
            "batches": [],
        },
    )

    with pytest.raises(
        full.ManagerScreenFullMarketAllocationV3Error,
        match="packet governance binding is invalid",
    ):
        full.manager_screen_full_market_allocation_v3_final_status(
            root=root,
            run_id=RUN_ID,
        )


def test_calibration_funded_and_deferred_projection_uses_result_research_brief(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _ready_full_market(tmp_path, monkeypatch)
    batch_id = "batch-calibration-projection"
    decisions = [
        ("CN:900005", "pass", 9005),
        ("CN:900006", "watch", 9006),
    ]
    _add_terminal_decision_batch(root, batch_id=batch_id, decisions=decisions)
    _add_calibration_result(
        root,
        batch_id=batch_id,
        reviews=[_calibration_review(symbol) for symbol, _, _ in decisions],
    )
    _extend_mock_scope(root, decisions=decisions, batch_id=batch_id)
    _prepare(root)
    packet = _packet(root)
    packet_by_symbol = {
        candidate["symbol"]: candidate for candidate in packet["candidates"]
    }

    funded_symbol = "CN:900005"
    recorded = _record(root, {funded_symbol})
    result = json.loads(_result_path(root).read_text(encoding="utf-8"))
    result_by_symbol = {
        decision["symbol"]: decision for decision in result["decisions"]
    }
    queue = _by_symbol(root / "research_queue.jsonl")
    screens = _by_symbol(root / "screening.jsonl")

    assert recorded["summary"]["selected_company_count"] == 1
    for symbol, _, _ in decisions:
        candidate = packet_by_symbol[symbol]
        allocation = result_by_symbol[symbol]
        calibration = candidate["calibration_material_error"]
        assert allocation["decisive_question"] != candidate["decisive_question"]
        assert f"calibration:{symbol}:primary" in allocation["evidence_ids"]
        assert queue[symbol]["decisive_question"] == allocation["decisive_question"]
        assert queue[symbol]["evidence_ids"] == allocation["evidence_ids"]
        assert screens[symbol]["decisive_question"] == allocation["decisive_question"]
        assert screens[symbol]["evidence"] == allocation["evidence_ids"]
        expected_bindings = {
            "manager_screen_calibration_result_path": calibration[
                "calibration_result_path"
            ],
            "manager_screen_calibration_result_sha256": calibration[
                "calibration_result_sha256"
            ],
            "manager_screen_calibration_review_sha256": calibration["review_sha256"],
            "manager_screen_calibration_adjudication_sha256": calibration[
                "adjudication_sha256"
            ],
        }
        for field, value in expected_bindings.items():
            assert queue[symbol][field] == value
            assert screens[symbol][field] == value

    assert queue[funded_symbol]["research_budget_state"] == "funded_quick_profile"
    assert queue["CN:900006"]["research_budget_state"] == "deferred_full_market"


def test_calibration_research_brief_cannot_omit_confirmed_error_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_os.research_assets.manager_screen_full_market_allocation_v3 import (
        ManagerScreenFullMarketAllocationV3Error,
        record_manager_screen_full_market_allocation_v3,
    )

    root = _ready_full_market(tmp_path, monkeypatch)
    batch_id = "batch-calibration-evidence"
    symbol = "CN:900007"
    decisions = [(symbol, "pass", 9007)]
    _add_terminal_decision_batch(root, batch_id=batch_id, decisions=decisions)
    _add_calibration_result(
        root,
        batch_id=batch_id,
        reviews=[_calibration_review(symbol)],
    )
    _extend_mock_scope(root, decisions=decisions, batch_id=batch_id)
    _prepare(root)
    packet = _packet(root)
    submission = _submission(packet, funded={symbol})
    target = next(
        decision for decision in submission["decisions"] if decision["symbol"] == symbol
    )
    target["evidence_ids"] = [
        evidence_id
        for evidence_id in target["evidence_ids"]
        if not evidence_id.startswith("calibration:")
    ]

    with pytest.raises(
        ManagerScreenFullMarketAllocationV3Error,
        match="research brief omits confirmed calibration-error evidence",
    ):
        record_manager_screen_full_market_allocation_v3(
            root=root,
            run_id=RUN_ID,
            submission=submission,
            recorded_at=RECORDED_AT,
        )
    assert not _result_path(root).exists()


def test_calibration_research_brief_cannot_resubmit_original_decisive_question(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_os.research_assets.manager_screen_full_market_allocation_v3 import (
        ManagerScreenFullMarketAllocationV3Error,
        record_manager_screen_full_market_allocation_v3,
    )

    root = _ready_full_market(tmp_path, monkeypatch)
    batch_id = "batch-calibration-question"
    symbol = "CN:900008"
    decisions = [(symbol, "watch", 9008)]
    _add_terminal_decision_batch(root, batch_id=batch_id, decisions=decisions)
    _add_calibration_result(
        root,
        batch_id=batch_id,
        reviews=[_calibration_review(symbol)],
    )
    _extend_mock_scope(root, decisions=decisions, batch_id=batch_id)
    _prepare(root)
    packet = _packet(root)
    candidate = next(item for item in packet["candidates"] if item["symbol"] == symbol)
    submission = _submission(packet, funded={symbol})
    target = next(
        decision for decision in submission["decisions"] if decision["symbol"] == symbol
    )
    assert f"calibration:{symbol}:primary" in target["evidence_ids"]
    target["decisive_question"] = f"  {candidate['decisive_question']}  "

    with pytest.raises(
        ManagerScreenFullMarketAllocationV3Error,
        match="confirmed calibration error requires a revised decisive question",
    ):
        record_manager_screen_full_market_allocation_v3(
            root=root,
            run_id=RUN_ID,
            submission=submission,
            recorded_at=RECORDED_AT,
        )
    assert not _result_path(root).exists()


def test_prepare_rebuilds_suspended_and_v3_candidates_in_scope_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _ready_full_market(tmp_path, monkeypatch)

    summary = _prepare(root)
    packet = _packet(root)

    assert summary["candidate_count"] == 197
    assert summary["selection_capacity"] == 196
    assert summary["locked_company_count"] == 4
    assert packet["candidates_sha256"]
    assert [row["scope_ordinal"] for row in packet["candidates"]] == sorted(
        row["scope_ordinal"] for row in packet["candidates"]
    )
    origins = {row["origin"] for row in packet["candidates"]}
    assert origins == {"suspended_v2", "v3_research_candidate"}
    assert packet["candidates"][-1]["symbol"] == V3_SYMBOL
    assert _prepare(root)["idempotent"] is True


def test_terminal_governance_manifest_binds_non_candidate_calibration_and_quote_noop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_os.research_assets.manager_screen_full_market_allocation_v3 import (
        ManagerScreenFullMarketAllocationV3Error,
    )

    root = _ready_full_market(tmp_path, monkeypatch)
    dependencies = [
        "batch-pass-watch/result.json",
        "batch-no-error/calibration/calibration-001/packet.json",
        "batch-no-error/calibration/calibration-001/result.json",
        "batch-quote-noop/quote-impact-reviews/noop-001/plan.json",
        "batch-quote-noop/quote-impact-reviews/noop-001/packet.json",
        "batch-quote-noop/quote-impact-reviews/noop-001/result.json",
    ]
    paths = [
        _seal_terminal_manifest_dependency(root, relative)
        for relative in dependencies
    ]
    _prepare(root)
    repository_root = root.parent.parent.resolve()
    manifested = {
        row["path"] for row in _packet(root)["terminal_governance_manifest"]
    }
    assert {
        _relative(path, repository_root) for path in paths
    }.issubset(manifested)

    for index, path in enumerate(paths):
        seal_path = path.with_name(f"{path.name}.seal.json")
        original_artifact = path.read_bytes()
        original_seal = seal_path.read_bytes()
        path.unlink()
        seal_path.unlink()
        seal_json(
            path,
            {"schema_version": 1, "marker": f"replacement-{index}"},
            artifact_type="test_terminal_governance_dependency",
            sealed_at=PREPARED_AT - dt.timedelta(minutes=1),
        )
        with pytest.raises(
            ManagerScreenFullMarketAllocationV3Error,
            match="terminal governance manifest drifted",
        ):
            _prepare(root)
        path.write_bytes(original_artifact)
        seal_path.write_bytes(original_seal)


def test_terminal_governance_manifest_rejects_new_upstream_artifact_after_packet(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_os.research_assets.manager_screen_full_market_allocation_v3 import (
        ManagerScreenFullMarketAllocationV3Error,
    )

    root = _ready_full_market(tmp_path, monkeypatch)
    _prepare(root)
    _seal_terminal_manifest_dependency(
        root,
        "batch-added/result.json",
        sealed_at=PREPARED_AT + dt.timedelta(minutes=1),
    )

    with pytest.raises(
        ManagerScreenFullMarketAllocationV3Error,
        match="must be sealed strictly before prepared_at",
    ):
        _prepare(root)


@pytest.mark.parametrize("offset_minutes", [0, 1])
def test_prepare_requires_every_terminal_dependency_to_predate_packet(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    offset_minutes: int,
) -> None:
    from trading_os.research_assets.manager_screen_full_market_allocation_v3 import (
        ManagerScreenFullMarketAllocationV3Error,
    )

    root = _ready_full_market(tmp_path, monkeypatch)
    _seal_terminal_manifest_dependency(
        root,
        "control/last-terminal-event.json",
        sealed_at=PREPARED_AT + dt.timedelta(minutes=offset_minutes),
    )

    with pytest.raises(
        ManagerScreenFullMarketAllocationV3Error,
        match="must be sealed strictly before prepared_at",
    ):
        _prepare(root)
    assert not _packet_path(root).exists()


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("unsealed", "artifact is not sealed"),
        ("orphan_seal", "seal has no artifact"),
        ("unknown", "unknown terminal governance JSON"),
    ],
)
def test_prepare_rejects_incomplete_or_unknown_run_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    message: str,
) -> None:
    from trading_os.research_assets.manager_screen_full_market_allocation_v3 import (
        ManagerScreenFullMarketAllocationV3Error,
    )

    root = _ready_full_market(tmp_path, monkeypatch)
    if case == "unknown":
        path = root / "manager-screen" / RUN_ID / "mystery.json"
        path.write_text("{}", encoding="utf-8")
    else:
        path = (
            root
            / "manager-screen"
            / RUN_ID
            / "control"
            / f"{case}.json"
        )
        if case == "unsealed":
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}", encoding="utf-8")
        else:
            _seal_terminal_manifest_dependency(
                root,
                f"control/{case}.json",
            )
            path.unlink()

    with pytest.raises(ManagerScreenFullMarketAllocationV3Error, match=message):
        _prepare(root)
    assert not _packet_path(root).exists()


def test_record_time_must_be_strictly_later_than_prepared_at_and_packet_seal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_os.research_assets.manager_screen_full_market_allocation_v3 import (
        ManagerScreenFullMarketAllocationV3Error,
        record_manager_screen_full_market_allocation_v3,
    )
    from trading_os.research_assets.sealing import canonical_json_bytes

    root = _ready_full_market(tmp_path, monkeypatch)
    _prepare(root)
    packet = _packet(root)
    submission = _submission(packet, funded=set())
    with pytest.raises(
        ManagerScreenFullMarketAllocationV3Error,
        match="strictly later",
    ):
        record_manager_screen_full_market_allocation_v3(
            root=root,
            run_id=RUN_ID,
            submission=submission,
            recorded_at=PREPARED_AT,
        )

    seal_path = _packet_path(root).with_name("packet.json.seal.json")
    manifest = json.loads(seal_path.read_text(encoding="utf-8"))
    later_packet_seal = PREPARED_AT + dt.timedelta(minutes=1)
    manifest["sealed_at"] = later_packet_seal.isoformat()
    seal_path.write_bytes(canonical_json_bytes(manifest))
    with pytest.raises(
        ManagerScreenFullMarketAllocationV3Error,
        match="strictly later",
    ):
        record_manager_screen_full_market_allocation_v3(
            root=root,
            run_id=RUN_ID,
            submission=submission,
            recorded_at=later_packet_seal,
        )

    recorded = record_manager_screen_full_market_allocation_v3(
        root=root,
        run_id=RUN_ID,
        submission=submission,
        recorded_at=later_packet_seal + dt.timedelta(minutes=1),
    )
    assert recorded["recorded_at"] == (
        later_packet_seal + dt.timedelta(minutes=1)
    ).isoformat()


def test_allocation_suspension_and_full_market_preserve_legacy_adoption_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _ready_full_market(tmp_path, monkeypatch)

    _prepare(root)
    legacy = next(
        candidate
        for candidate in _packet(root)["candidates"]
        if candidate["symbol"] == "CN:000200"
    )

    assert legacy["origin"] == "suspended_v2"
    assert legacy["effective_decision_source_type"] == (
        "manager_screen_legacy_transition_result"
    )
    assert legacy["effective_decision_source_path"].endswith(
        "/legacy-transition-001/result.json"
    )


def test_zero_selection_capacity_can_seal_an_all_defer_partition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_os.research_assets.manager_screen_full_market_allocation_v3 as full

    root = _ready_full_market(tmp_path, monkeypatch)
    zero_capacity = {
        "absolute_funded_company_limit": 200,
        "absolute_funded_effort_budget_hours": 300.0,
        "locked_company_count": 200,
        "locked_effort_budget_hours": 300.0,
        "locked_symbols": [f"CN:{ordinal:06d}" for ordinal in range(1, 201)],
        "selection_capacity": 0,
        "purchase_effort_budget_hours": 1.5,
    }
    monkeypatch.setattr(full, "_packet_capacity", lambda **_: zero_capacity)

    _prepare(root)
    recorded = _record(root, set())

    assert recorded["summary"]["selected_company_count"] == 0
    assert recorded["summary"]["effective_funded_company_count"] == 200
    assert recorded["summary"]["unused_company_capacity"] == 0
    assert all(
        decision["decision"] == "defer_full_market"
        for decision in json.loads(_result_path(root).read_text(encoding="utf-8"))[
            "decisions"
        ]
    )


def test_prepare_uses_sealed_quote_replacements_from_two_batches_after_suspension(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_os.research_assets import manager_screen_quote_impact as quote_impact

    root = _ready_full_market(tmp_path, monkeypatch)
    symbols = ["CN:000006", "CN:000106"]
    replacements = {}
    for symbol in symbols:
        replacements[symbol] = _materialize_quote_impact_replacement(
            root,
            symbol=symbol,
            sealed=True,
        )
        binding = quote_impact._require_post_contract_quote_suspension(
            base=root,
            run_id=RUN_ID,
            require_fully_materialized=True,
        )
        assert binding is not None
        assert binding["materialization"]["fully_materialized"] is False

    _prepare(root)
    candidates = {
        item["symbol"]: item
        for item in _packet(root)["candidates"]
        if item["symbol"] in symbols
    }

    assert set(candidates) == set(symbols)
    for symbol in symbols:
        candidate = candidates[symbol]
        replacement = replacements[symbol]
        assert candidate["origin"] == "suspended_v2"
        assert candidate["effective_decision_source_path"] == replacement["result_path"]
        assert (
            candidate["effective_decision_source_sha256"]
            == replacement["result_sha256"]
        )
        assert candidate["effective_decision_source_type"] == (
            "manager_screen_quote_impact_result"
        )
        assert candidate["original_route"] == replacement["replacement"]["route"]
        assert candidate["decisive_question"] == replacement["replacement"][
            "decisive_question"
        ]
        assert candidate["evidence_ids"] == replacement["replacement"]["evidence_ids"]


def test_prepare_rejects_unsealed_quote_replacement_drift_after_suspension(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_os.research_assets import manager_screen_quote_impact as quote_impact
    from trading_os.research_assets.manager_screen_full_market_allocation_v3 import (
        ManagerScreenFullMarketAllocationV3Error,
    )

    root = _ready_full_market(tmp_path, monkeypatch)
    _materialize_quote_impact_replacement(
        root,
        symbol="CN:000006",
        sealed=True,
    )
    assert (
        quote_impact._require_post_contract_quote_suspension(
            base=root,
            run_id=RUN_ID,
            require_fully_materialized=True,
        )
        is not None
    )
    _materialize_quote_impact_replacement(
        root,
        symbol="CN:000106",
        sealed=False,
    )

    with pytest.raises(
        quote_impact.ManagerScreenQuoteImpactError,
        match="drift outside sealed quote-impact evolution",
    ):
        quote_impact._require_post_contract_quote_suspension(
            base=root,
            run_id=RUN_ID,
            require_fully_materialized=True,
        )

    with pytest.raises(
        ManagerScreenFullMarketAllocationV3Error,
        match="candidate decision source is invalid",
    ):
        _prepare(root)
    assert not _packet_path(root).exists()


def test_candidate_order_allows_duplicate_frozen_batch_ordinals(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_os.research_assets.manager_screen_full_market_allocation_v3 as full

    root = _ready_full_market(tmp_path, monkeypatch)
    scope = full._scope_members(base=root, run_id=RUN_ID)
    duplicate_symbols = sorted(
        row["symbol"]
        for row in read_jsonl(root / "research_queue.jsonl")
        if row.get("research_budget_state") == "candidate_unfunded"
        and row["symbol"] != V3_SYMBOL
    )[:2]
    scope[duplicate_symbols[1]]["scope_ordinal"] = scope[duplicate_symbols[0]][
        "scope_ordinal"
    ]

    _prepare(root)
    candidates = _packet(root)["candidates"]
    keys = [(row["scope_ordinal"], row["symbol"]) for row in candidates]
    assert keys == sorted(keys)
    assert len({ordinal for ordinal, _ in keys}) < len(keys)


def test_scope_ordinals_come_from_sealed_active_batch_members(tmp_path: Path) -> None:
    import trading_os.research_assets.manager_screen_full_market_allocation_v3 as full

    root = tmp_path / "coverage" / "cn-a"
    run_dir = root / "manager-screen" / RUN_ID
    for batch_id, symbol in (("batch-001", "CN:000001"), ("batch-002", "CN:000002")):
        seal_json(
            run_dir / batch_id / "batch.json",
            {
                "schema_version": 1,
                "run_id": RUN_ID,
                "batch_id": batch_id,
                "members": [
                    {
                        "symbol": symbol,
                        "name": f"冻结成员{symbol}",
                        "scope_ordinal": 7,
                    }
                ],
            },
            artifact_type="manager_screen_batch",
            sealed_at=PREPARED_AT,
        )

    members = full._scope_members(base=root, run_id=RUN_ID)
    assert members == {
        "CN:000001": {"scope_ordinal": 7, "name": "冻结成员CN:000001", "batch_id": "batch-001"},
        "CN:000002": {"scope_ordinal": 7, "name": "冻结成员CN:000002", "batch_id": "batch-002"},
    }


def test_scope_appends_sealed_legacy_adoptions_after_active_batch_ordinals(
    tmp_path: Path,
) -> None:
    import trading_os.research_assets.manager_screen_full_market_allocation_v3 as full

    repository_root = tmp_path
    root = repository_root / "coverage" / "cn-a"
    run_dir = root / "manager-screen" / RUN_ID
    seal_json(
        run_dir / "batch-001" / "batch.json",
        {
            "schema_version": 1,
            "run_id": RUN_ID,
            "batch_id": "batch-001",
            "members": [
                {
                    "symbol": "CN:000001",
                    "name": "Active member",
                    "scope_ordinal": 7,
                }
            ],
        },
        artifact_type="manager_screen_batch",
        sealed_at=PREPARED_AT,
    )
    transition_dir = run_dir / "legacy-transition-001"
    plan_path = transition_dir / "plan.json"
    plan_seal = seal_json(
        plan_path,
        {
            "schema_version": 1,
            "run_id": RUN_ID,
            "transition_id": "legacy-transition-001",
            "members": [
                {
                    "ordinal": 1,
                    "symbol": "CN:000003",
                    "name": "First adoption",
                    "action": "adoption",
                },
                {
                    "ordinal": 2,
                    "symbol": "CN:000004",
                    "name": "Rescreen member",
                    "action": "rescreen",
                },
                {
                    "ordinal": 3,
                    "symbol": "CN:000005",
                    "name": "Second adoption",
                    "action": "adoption",
                },
            ],
        },
        artifact_type="manager_screen_legacy_transition_plan",
        sealed_at=PREPARED_AT,
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
        sealed_at=PREPARED_AT,
    )
    result_path = transition_dir / "result.json"
    result_seal = seal_json(
        result_path,
        {
            "schema_version": 1,
            "run_id": RUN_ID,
            "transition_id": "legacy-transition-001",
            "plan_path": _relative(plan_path, repository_root),
            "plan_sha256": plan_seal.sha256,
            "packet_path": _relative(packet_path, repository_root),
            "packet_sha256": packet_seal.sha256,
            "decisions": [
                {"symbol": "CN:000003", "route": "send_to_analyst"},
                {"symbol": "CN:000005", "route": "watch"},
            ],
        },
        artifact_type="manager_screen_legacy_transition_result",
        sealed_at=PREPARED_AT,
    )

    members = full._scope_members(base=root, run_id=RUN_ID)

    assert members["CN:000003"] == {
        "scope_ordinal": 8,
        "name": "First adoption",
        "batch_id": "legacy-transition-001",
        "manager_screen_result_path": _relative(result_path, repository_root),
        "manager_screen_result_sha256": result_seal.sha256,
    }
    assert members["CN:000005"]["scope_ordinal"] == 10
    assert "CN:000004" not in members


def test_record_rebuilds_exact_live_candidate_pool_after_prepare(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_os.research_assets.manager_screen_full_market_allocation_v3 import (
        ManagerScreenFullMarketAllocationV3Error,
    )

    root = _ready_full_market(tmp_path, monkeypatch)
    _prepare(root)
    packet = _packet(root)
    queue_path = root / "research_queue.jsonl"
    queue = _by_symbol(queue_path)
    queue[packet["candidates"][0]["symbol"]]["next_action"] = "prepare 后发生了候选投影漂移"
    write_jsonl(queue_path, list(queue.values()))

    with pytest.raises(ManagerScreenFullMarketAllocationV3Error, match="candidate pool drifted"):
        _record(root, {packet["candidates"][0]["symbol"]})
    assert not (
        root
        / "manager-screen"
        / RUN_ID
        / "governance"
        / "allocation-v3"
        / "full-market"
        / "result.json"
    ).exists()


def test_record_rejects_newer_quote_amendment_injected_after_packet(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_os.research_assets.manager_screen_full_market_allocation_v3 as full

    root = _ready_full_market(tmp_path, monkeypatch)
    _prepare(root)
    packet_quote = dict(_packet(root)["quote"])
    injected_quote = {
        **packet_quote,
        "amendment_id": "quotes-injected-after-packet",
        "path": "coverage/cn-a/snapshots/injected-after-packet.json",
        "sha256": "d" * 64,
        "effective_at": (PREPARED_AT + dt.timedelta(minutes=2)).isoformat(),
    }
    observed_at = []

    def latest_quote(*, prepared_at: dt.datetime, **_: object) -> dict:
        observed_at.append(prepared_at)
        return injected_quote if prepared_at >= RECORDED_AT else packet_quote

    monkeypatch.setattr(full, "_fresh_quote_binding", latest_quote)

    with pytest.raises(
        full.ManagerScreenFullMarketAllocationV3Error,
        match="not bound to the latest quote amendment at recorded_at",
    ):
        _record(root, set())

    assert observed_at == [PREPARED_AT, RECORDED_AT]
    assert not _result_path(root).exists()


@pytest.mark.parametrize(
    "forgery",
    ["capacity", "policy", "quote", "full_scope_state", "instructions"],
)
def test_resealed_packet_cannot_forge_semantic_dependencies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    forgery: str,
) -> None:
    import trading_os.research_assets.manager_screen_full_market_allocation_v3 as full

    root = _ready_full_market(tmp_path, monkeypatch)
    _prepare(root)
    packet = _packet(root)
    if forgery == "capacity":
        packet["capacity"]["selection_capacity"] += 1
    elif forgery == "policy":
        packet["policy"]["quick_profile_effort_budget_hours"] = 0.5
    elif forgery == "quote":
        packet["quote"]["quote_count"] += 1
    elif forgery == "full_scope_state":
        packet["full_scope_state"]["completed_company_count"] -= 1
    else:
        packet["instructions"]["ranking_or_score_forbidden"] = False
    path = _packet_path(root)
    path.unlink()
    path.with_name(f"{path.name}.seal.json").unlink()
    seal_json(
        path,
        packet,
        artifact_type=full.PACKET_ARTIFACT_TYPE,
        sealed_at=PREPARED_AT,
    )

    with pytest.raises(
        full.ManagerScreenFullMarketAllocationV3Error,
        match="governance binding is invalid",
    ):
        _prepare(root)


@pytest.mark.parametrize(
    ("forgery", "message"),
    [
        ("effort", "result effort or hard capacity is invalid"),
        ("cycle", "result profile cycle is not canonical"),
        ("stale_quote", "quotes became stale before record"),
        ("blank_trigger", "revisit trigger condition is invalid"),
    ],
)
def test_resealed_result_cannot_forge_policy_effort_or_cycle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    forgery: str,
    message: str,
) -> None:
    import trading_os.research_assets.manager_screen_full_market_allocation_v3 as full

    root = _ready_full_market(tmp_path, monkeypatch)
    _prepare(root)
    first_symbol = _packet(root)["candidates"][0]["symbol"]
    _record(root, {first_symbol})
    path = _result_path(root)
    result = json.loads(path.read_text(encoding="utf-8"))
    if forgery == "effort":
        result["purchase_effort_budget_hours"] = 0.5
    elif forgery == "cycle":
        result["profile_cycle_id"] = f"{RUN_ID}-forged-cycle"
    elif forgery == "stale_quote":
        result["recorded_at"] = (PREPARED_AT + dt.timedelta(days=4)).isoformat()
    else:
        deferred = next(
            decision
            for decision in result["decisions"]
            if decision["decision"] == "defer_full_market"
        )
        deferred["revisit_triggers"][0]["condition"] = "   "
    path.unlink()
    path.with_name(f"{path.name}.seal.json").unlink()
    seal_json(
        path,
        result,
        artifact_type=full.RESULT_ARTIFACT_TYPE,
        sealed_at=RECORDED_AT,
    )

    with pytest.raises(full.ManagerScreenFullMarketAllocationV3Error, match=message):
        full.verify_manager_screen_full_market_allocation_v3_result(
            root=root,
            run_id=RUN_ID,
        )


def test_record_enforces_absolute_cap_and_complete_explicit_partition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_os.research_assets.manager_screen_full_market_allocation_v3 import (
        ManagerScreenFullMarketAllocationV3Error,
        record_manager_screen_full_market_allocation_v3,
    )

    root = _ready_full_market(tmp_path, monkeypatch)
    _prepare(root)
    packet = _packet(root)
    all_funded = {row["symbol"] for row in packet["candidates"]}

    with pytest.raises(ManagerScreenFullMarketAllocationV3Error, match="exceeds"):
        _record(root, all_funded)
    result_path = (
        root
        / "manager-screen"
        / RUN_ID
        / "governance"
        / "allocation-v3"
        / "full-market"
        / "result.json"
    )
    assert not result_path.exists()

    incomplete = _submission(packet, funded=set())
    incomplete["decisions"].pop()
    with pytest.raises(ManagerScreenFullMarketAllocationV3Error, match="partition"):
        record_manager_screen_full_market_allocation_v3(
            root=root,
            run_id=RUN_ID,
            submission=incomplete,
            recorded_at=RECORDED_AT,
        )
    assert not result_path.exists()


def test_record_projects_selected_and_deferred_without_rewriting_original_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_os.research_assets.manager_screen_full_market_allocation_v3 import (
        manager_screen_full_market_allocation_v3_final_status,
    )
    from trading_os.research_assets.profile_workflow import profile_cycle_status

    root = _ready_full_market(tmp_path, monkeypatch)
    _prepare(root)
    funded = {"CN:000001", V3_SYMBOL}
    recorded = _record(root, funded)

    assert recorded["summary"]["selected_company_count"] == 2
    assert recorded["summary"]["locked_company_count"] == 4
    assert recorded["summary"]["effective_funded_company_count"] == 6
    assert recorded["summary"]["effective_funded_effort_budget_hours"] == 9.0
    assert recorded["summary"]["unused_company_capacity"] == 194
    queue = _by_symbol(root / "research_queue.jsonl")
    screens = _by_symbol(root / "screening.jsonl")
    old = queue["CN:000001"]
    v3 = queue[V3_SYMBOL]
    deferred = queue["CN:000006"]
    assert old["manager_screen_route"] == "send_to_analyst"
    assert v3["manager_screen_route"] == "research_candidate"
    for row in (old, v3):
        assert row["task_type"] == "quick_profile"
        assert row["status"] == "pending"
        assert row["preceding_stage"] == "manager_screen_allocation_v3"
        assert row["research_budget_state"] == "funded_quick_profile"
        assert row["profile_cycle_id"] == recorded["profile_cycle_id"]
        assert row["allocation_sha256"] == recorded["result_sha256"]
    assert deferred["task_type"] == "manager_screen"
    assert deferred["research_budget_state"] == "deferred_full_market"
    assert "effort_budget_hours" not in deferred
    assert screens[V3_SYMBOL]["decision"] == "quick_profile"
    assert screens["CN:000006"]["decision"] == "deferred_full_market"
    final = manager_screen_full_market_allocation_v3_final_status(root=root, run_id=RUN_ID)
    assert final["finalized"] is True
    status = profile_cycle_status(root=root, cycle_id=recorded["profile_cycle_id"])
    assert status["cohort_count"] == 2
    assert status["recorded_count"] == 0
    assert status["remaining_count"] == 2
    assert status["invalid_artifact_count"] == 0


def test_profile_status_uses_sealed_full_market_authority_after_projection_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_os.research_assets import profile_workflow

    root = _ready_full_market(tmp_path, monkeypatch)
    _prepare(root)
    recorded = _record(root, {"CN:000001", V3_SYMBOL})
    queue_path = root / "research_queue.jsonl"
    queue = _by_symbol(queue_path)
    drifted = queue["CN:000001"]
    for field in (
        "profile_cycle_id",
        "manager_screen_run_id",
        "preceding_stage",
        "manager_screen_allocation_result_path",
        "manager_screen_allocation_result_sha256",
        "manager_screen_allocation_candidate_sha256",
        "manager_screen_allocation_decision",
        "allocation_sha256",
    ):
        drifted.pop(field, None)
    drifted["stage_history"] = [
        event
        for event in drifted.get("stage_history") or []
        if not str(event.get("stage", "")).startswith("manager_screen")
    ]
    write_jsonl(queue_path, list(queue.values()))
    screening_path = root / "screening.jsonl"
    screens = _by_symbol(screening_path)
    for field in (
        "profile_cycle_id",
        "manager_screen_allocation_result_path",
        "manager_screen_allocation_result_sha256",
        "manager_screen_allocation_candidate_sha256",
        "manager_screen_allocation_decision",
    ):
        screens["CN:000001"].pop(field, None)
    write_jsonl(screening_path, list(screens.values()))

    assert profile_workflow._record_has_full_market_v3_profile_authority(drifted) is False
    assert (
        profile_workflow._record_has_canonical_full_market_v3_profile_authority(
            drifted,
            base=root,
            cycle=recorded["profile_cycle_id"],
        )
        is True
    )
    status = profile_workflow.profile_cycle_status(
        root=root,
        cycle_id=recorded["profile_cycle_id"],
    )

    assert status["cohort_count"] == 2
    assert status["recorded_count"] == 0
    assert status["remaining_count"] == 2
    assert status["invalid_artifact_count"] == 1
    assert status["invalid_artifacts"][0]["symbol"] == "CN:000001"
    assert status["invalid_artifacts"][0]["error"].startswith(
        "full_market_v3_authority_drift:"
    )
    assert "screening.profile_cycle_id" in status["invalid_artifacts"][0]["error"]


def test_profile_status_fails_closed_when_canonical_full_market_singleton_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_os.research_assets.profile_workflow import profile_cycle_status
    from trading_os.research_assets.research_allocation import ResearchAllocationError

    root = _ready_full_market(tmp_path, monkeypatch)
    _prepare(root)
    recorded = _record(root, {"CN:000001", V3_SYMBOL})
    result_path = (
        root
        / "manager-screen"
        / RUN_ID
        / "governance"
        / "allocation-v3"
        / "full-market"
        / "result.json"
    )
    result_path.unlink()
    result_path.with_name(f"{result_path.name}.seal.json").unlink()

    with pytest.raises(ResearchAllocationError, match="authority singleton is missing"):
        profile_cycle_status(root=root, cycle_id=recorded["profile_cycle_id"])


def test_profile_status_accepts_a_sealed_full_market_cycle_with_no_new_funding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_os.research_assets.profile_workflow import profile_cycle_status

    root = _ready_full_market(tmp_path, monkeypatch)
    _prepare(root)
    recorded = _record(root, set())

    status = profile_cycle_status(root=root, cycle_id=recorded["profile_cycle_id"])

    assert status["cohort_count"] == 0
    assert status["recorded_count"] == 0
    assert status["remaining_count"] == 0
    assert status["comparison_ready"] is True
    assert status["invalid_artifact_count"] == 0


def test_apply_repairs_prior_projection_but_rejects_unrecognized_drift_atomically(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_os.research_assets.manager_screen_full_market_allocation_v3 import (
        ManagerScreenFullMarketAllocationV3Error,
        apply_manager_screen_full_market_allocation_v3,
    )

    root = _ready_full_market(tmp_path, monkeypatch)
    _prepare(root)
    packet = _packet(root)
    _record(root, {"CN:000001", V3_SYMBOL})
    queue_path = root / "research_queue.jsonl"
    queue = _by_symbol(queue_path)
    first = packet["candidates"][0]
    queue[first["symbol"]] = dict(first["prior_queue_row"])
    write_jsonl(queue_path, list(queue.values()))

    repaired = apply_manager_screen_full_market_allocation_v3(root=root, run_id=RUN_ID)
    assert repaired["materialization"]["queue_repaired_count"] == 1

    queue = _by_symbol(queue_path)
    queue[first["symbol"]]["reason"] = "无法归属于 prior 或 expected 的漂移"
    write_jsonl(queue_path, list(queue.values()))
    before_screening = (root / "screening.jsonl").read_bytes()
    with pytest.raises(ManagerScreenFullMarketAllocationV3Error, match="refusing all writes"):
        apply_manager_screen_full_market_allocation_v3(root=root, run_id=RUN_ID)
    assert (root / "screening.jsonl").read_bytes() == before_screening


def test_post_seal_projection_crash_recovers_through_apply_and_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_os.research_assets.manager_screen_full_market_allocation_v3 as full

    root = _ready_full_market(tmp_path, monkeypatch)
    _prepare(root)
    submission = _submission(_packet(root), funded={"CN:000001", V3_SYMBOL})
    original_materialize = full._materialize

    def fail_after_result_seal(**_: object) -> dict:
        raise OSError("simulated post-seal projection crash")

    monkeypatch.setattr(full, "_materialize", fail_after_result_seal)
    with pytest.raises(OSError, match="post-seal projection crash"):
        full.record_manager_screen_full_market_allocation_v3(
            root=root,
            run_id=RUN_ID,
            submission=submission,
            recorded_at=RECORDED_AT,
        )
    monkeypatch.setattr(full, "_materialize", original_materialize)

    assert _result_path(root).exists()
    assert full.manager_screen_full_market_allocation_v3_final_status(
        root=root,
        run_id=RUN_ID,
    )["finalized"] is False
    applied = full.apply_manager_screen_full_market_allocation_v3(
        root=root,
        run_id=RUN_ID,
    )
    assert applied["materialization"]["fully_materialized"] is True
    assert full.manager_screen_full_market_allocation_v3_final_status(
        root=root,
        run_id=RUN_ID,
    )["finalized"] is True
    replayed = full.record_manager_screen_full_market_allocation_v3(
        root=root,
        run_id=RUN_ID,
        submission=submission,
        recorded_at=RECORDED_AT,
    )
    assert replayed["idempotent"] is True


def test_claim_and_cohort_use_common_full_market_predecessor_across_batches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_os.research_assets import profile_workflow
    from trading_os.research_assets.profile_workflow import claim_profile_task
    from trading_os.research_assets.research_allocation import ResearchAllocationError

    root = _ready_full_market(tmp_path, monkeypatch)
    _prepare(root)
    recorded = _record(root, {"CN:000001", V3_SYMBOL})

    first = claim_profile_task(
        root=root,
        agent="/root/analyst-one",
        claimed_at=RECORDED_AT + dt.timedelta(minutes=1),
        symbol="CN:000001",
        run_id=RUN_ID,
    )
    second = claim_profile_task(
        root=root,
        agent="/root/analyst-two",
        claimed_at=RECORDED_AT + dt.timedelta(minutes=1),
        symbol=V3_SYMBOL,
        run_id=RUN_ID,
    )
    assert first["profile_cycle_id"] == recorded["profile_cycle_id"]
    assert second["profile_cycle_id"] == recorded["profile_cycle_id"]
    assert first["manager_screen_allocation_result_sha256"] == recorded["result_sha256"]
    assert second["manager_screen_allocation_result_sha256"] == recorded["result_sha256"]

    queue_path = root / "research_queue.jsonl"
    queue = _by_symbol(queue_path)
    for symbol in ("CN:000001", V3_SYMBOL):
        row = queue[symbol]
        row["status"] = "completed"
        row["finished_at"] = (RECORDED_AT + dt.timedelta(minutes=2)).isoformat()
        row["stage_history"] = list(row.get("stage_history") or []) + [
            {
                "stage": "quick_profile",
                "status": "completed",
                "finished_at": row["finished_at"],
                "result_path": f"coverage/cn-a/profiles/{symbol}.profile.json",
                "evaluation_path": f"coverage/cn-a/profiles/{symbol}.evaluation.json",
            }
        ]
    write_jsonl(queue_path, list(queue.values()))
    queue_rows = read_jsonl(queue_path)
    monkeypatch.setattr(
        profile_workflow,
        "_latest_cycle_stage_completion_with_legacy_decline_migration",
        lambda record, *, base, stage, cycle, canonical_full_market_v3=None: next(
            (
                event
                for event in reversed(record.get("stage_history") or [])
                if event.get("stage") == stage and event.get("status") == "completed"
            ),
            None,
        ),
    )
    binding_field, binding, binding_sha, cohort = profile_workflow._complete_profile_cohort(
        queue_rows,
        base=root,
        repository_root=root.parent.parent.resolve(),
        cycle=recorded["profile_cycle_id"],
        stage="quick_profile",
    )
    assert binding_field == "manager_screen_allocation_result_path"
    assert binding_sha == recorded["result_sha256"]
    assert [row["symbol"] for row in cohort] == ["CN:000001", V3_SYMBOL]
    assert profile_workflow._investment_manager_for_cohort(
        cohort,
        repository_root=root.parent.parent.resolve(),
    ) == _manager()["agent"]
    assert binding.endswith("/full-market/result.json")

    missing_run = json.loads(json.dumps(queue_rows))
    for row in missing_run:
        row.pop("manager_screen_run_id", None)
    with pytest.raises(ResearchAllocationError, match="cannot drop"):
        profile_workflow._complete_profile_cohort(
            missing_run,
            base=root,
            repository_root=root.parent.parent.resolve(),
            cycle=recorded["profile_cycle_id"],
            stage="quick_profile",
        )

    queue_rows[0].pop("manager_screen_allocation_result_sha256")
    with pytest.raises(ResearchAllocationError, match="predecessor SHA binding"):
        profile_workflow._complete_profile_cohort(
            queue_rows,
            base=root,
            repository_root=root.parent.parent.resolve(),
            cycle=recorded["profile_cycle_id"],
            stage="quick_profile",
        )


def test_first_full_market_claim_requires_globally_finalized_projection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_os.research_assets.profile_workflow import claim_profile_task
    from trading_os.research_assets.research_allocation import ResearchAllocationError

    root = _ready_full_market(tmp_path, monkeypatch)
    _prepare(root)
    recorded = _record(root, {"CN:000001", V3_SYMBOL})
    screening_path = root / "screening.jsonl"
    screens = _by_symbol(screening_path)
    screens["CN:000006"]["reason"] = "unrecognized drift before profile activation"
    write_jsonl(screening_path, list(screens.values()))

    with pytest.raises(ResearchAllocationError, match="must be finalized"):
        claim_profile_task(
            root=root,
            agent="/root/blocked-before-finalized",
            claimed_at=RECORDED_AT + dt.timedelta(minutes=1),
            symbol="CN:000001",
            run_id=RUN_ID,
        )
    gate_path = (
        root
        / "profiles"
        / recorded["profile_cycle_id"]
        / "full-market-claim-activation"
        / "gate.json"
    )
    assert not gate_path.exists()


def test_full_market_claim_gate_canonicalizes_locked_remediation_projection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_os.research_assets import profile_workflow
    from trading_os.research_assets.manager_screen_full_market_allocation_v3 import (
        manager_screen_full_market_allocation_v3_final_status,
        verify_manager_screen_full_market_allocation_v3_result,
    )
    from trading_os.research_assets.profile_workflow import claim_profile_task

    root = _ready_full_market(tmp_path, monkeypatch)
    _add_calibration_result(
        root,
        batch_id="batch-v1",
        reviews=[_calibration_review("CN:000004")],
    )
    _prepare(root)
    recorded = _record(root, {"CN:000001", V3_SYMBOL})
    status = manager_screen_full_market_allocation_v3_final_status(
        root=root,
        run_id=RUN_ID,
    )
    result = verify_manager_screen_full_market_allocation_v3_result(
        root=root,
        run_id=RUN_ID,
    )
    expected_digest = profile_workflow._canonical_full_market_final_status_sha256(
        status=status,
        result=result,
    )

    claim_profile_task(
        root=root,
        agent="/root/first-with-locked-remediation",
        claimed_at=RECORDED_AT + dt.timedelta(minutes=1),
        symbol="CN:000001",
        run_id=RUN_ID,
    )
    gate_path = (
        root
        / "profiles"
        / recorded["profile_cycle_id"]
        / "full-market-claim-activation"
        / "gate.json"
    )
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    assert gate["final_status_sha256"] == expected_digest
    assert status["materialization"][
        "locked_remediation_queue_materialized_count"
    ] == 1

    second = claim_profile_task(
        root=root,
        agent="/root/second-verifies-locked-gate",
        claimed_at=RECORDED_AT + dt.timedelta(minutes=2),
        symbol=V3_SYMBOL,
        run_id=RUN_ID,
    )
    assert second["task_type"] == "quick_profile"


@pytest.mark.parametrize(
    ("drift_symbol", "message"),
    [
        ("CN:000006", "not an activated quick-profile claim"),
        (V3_SYMBOL, "lacks a sealed claim activation receipt"),
    ],
)
def test_full_market_claim_gate_rejects_unactivated_other_symbol_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    drift_symbol: str,
    message: str,
) -> None:
    from trading_os.research_assets.profile_workflow import claim_profile_task
    from trading_os.research_assets.research_allocation import ResearchAllocationError

    root = _ready_full_market(tmp_path, monkeypatch)
    _prepare(root)
    _record(root, {"CN:000001", V3_SYMBOL})
    claim_profile_task(
        root=root,
        agent="/root/first-activated",
        claimed_at=RECORDED_AT + dt.timedelta(minutes=1),
        symbol="CN:000001",
        run_id=RUN_ID,
    )
    screening_path = root / "screening.jsonl"
    screens = _by_symbol(screening_path)
    screens[drift_symbol]["reason"] = "drift in a never-activated symbol"
    write_jsonl(screening_path, list(screens.values()))

    with pytest.raises(ResearchAllocationError, match=message):
        claim_profile_task(
            root=root,
            agent="/root/second-blocked",
            claimed_at=RECORDED_AT + dt.timedelta(minutes=2),
            symbol=V3_SYMBOL,
            run_id=RUN_ID,
        )


@pytest.mark.parametrize("receipt_state", ["missing", "forged"])
def test_later_full_market_claim_rejects_missing_or_forged_prior_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    receipt_state: str,
) -> None:
    from trading_os.research_assets.profile_workflow import claim_profile_task
    from trading_os.research_assets.research_allocation import ResearchAllocationError
    from trading_os.research_assets.sealing import seal_json

    root = _ready_full_market(tmp_path, monkeypatch)
    _prepare(root)
    recorded = _record(root, {"CN:000001", V3_SYMBOL})
    claim_profile_task(
        root=root,
        agent="/root/first-activated",
        claimed_at=RECORDED_AT + dt.timedelta(minutes=1),
        symbol="CN:000001",
        run_id=RUN_ID,
    )
    receipt_path = (
        root
        / "profiles"
        / recorded["profile_cycle_id"]
        / "full-market-claim-activation"
        / "receipts"
        / "CN-000001.json"
    )
    seal_path = receipt_path.with_name(f"{receipt_path.name}.seal.json")
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt_path.unlink()
    seal_path.unlink()
    if receipt_state == "forged":
        payload["allocation_result_sha256"] = "f" * 64
        seal_json(
            receipt_path,
            payload,
            artifact_type="full_market_profile_claim_activation_receipt",
            sealed_at=RECORDED_AT + dt.timedelta(minutes=1),
        )

    with pytest.raises(
        ResearchAllocationError,
        match=("lacks a sealed" if receipt_state == "missing" else "does not match"),
    ):
        claim_profile_task(
            root=root,
            agent="/root/second-blocked",
            claimed_at=RECORDED_AT + dt.timedelta(minutes=2),
            symbol=V3_SYMBOL,
            run_id=RUN_ID,
        )


def test_full_market_claim_rejects_resealed_gate_with_forged_final_status_digest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_os.research_assets.profile_workflow import claim_profile_task
    from trading_os.research_assets.research_allocation import ResearchAllocationError

    root = _ready_full_market(tmp_path, monkeypatch)
    _prepare(root)
    recorded = _record(root, {"CN:000001", V3_SYMBOL})
    activated_at = RECORDED_AT + dt.timedelta(minutes=1)
    claim_profile_task(
        root=root,
        agent="/root/first-activated",
        claimed_at=activated_at,
        symbol="CN:000001",
        run_id=RUN_ID,
    )
    activation_dir = (
        root
        / "profiles"
        / recorded["profile_cycle_id"]
        / "full-market-claim-activation"
    )
    gate_path = activation_dir / "gate.json"
    receipt_path = activation_dir / "receipts" / "CN-000001.json"
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    for path in (gate_path, receipt_path):
        path.unlink()
        path.with_name(f"{path.name}.seal.json").unlink()
    gate["final_status_sha256"] = "f" * 64
    resealed_gate = seal_json(
        gate_path,
        gate,
        artifact_type="full_market_profile_claim_activation_gate",
        sealed_at=activated_at,
    )
    receipt["activation_gate_sha256"] = resealed_gate.sha256
    seal_json(
        receipt_path,
        receipt,
        artifact_type="full_market_profile_claim_activation_receipt",
        sealed_at=activated_at,
    )

    with pytest.raises(ResearchAllocationError, match="does not match its allocation"):
        claim_profile_task(
            root=root,
            agent="/root/second-blocked",
            claimed_at=RECORDED_AT + dt.timedelta(minutes=2),
            symbol=V3_SYMBOL,
            run_id=RUN_ID,
        )


@pytest.mark.parametrize("projection", ["research_queue", "screening"])
def test_full_market_claim_allows_non_authorization_drift_after_activation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    projection: str,
) -> None:
    from trading_os.research_assets.profile_workflow import claim_profile_task
    root = _ready_full_market(tmp_path, monkeypatch)
    _prepare(root)
    _record(root, {"CN:000001", V3_SYMBOL})
    claim_profile_task(
        root=root,
        agent="/root/first-activated",
        claimed_at=RECORDED_AT + dt.timedelta(minutes=1),
        symbol="CN:000001",
        run_id=RUN_ID,
    )
    path = root / f"{projection}.jsonl"
    rows = _by_symbol(path)
    rows["CN:000001"]["reason"] = "arbitrary mutable projection drift"
    write_jsonl(path, list(rows.values()))

    claimed = claim_profile_task(
        root=root,
        agent="/root/second-allowed",
        claimed_at=RECORDED_AT + dt.timedelta(minutes=2),
        symbol=V3_SYMBOL,
        run_id=RUN_ID,
    )
    assert claimed["symbol"] == V3_SYMBOL


@pytest.mark.parametrize(
    ("projection", "field"),
    [
        ("research_queue", "manager_screen_run_id"),
        ("research_queue", "manager_screen_allocation_candidate_sha256"),
        ("research_queue", "allocation_sha256"),
        ("screening", "manager_screen_result_sha256"),
        ("screening", "manager_screen_allocation_result_sha256"),
        ("screening", "profile_cycle_id"),
    ],
)
def test_full_market_claim_rejects_activated_immutable_binding_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    projection: str,
    field: str,
) -> None:
    from trading_os.research_assets.profile_workflow import claim_profile_task
    from trading_os.research_assets.research_allocation import ResearchAllocationError

    root = _ready_full_market(tmp_path, monkeypatch)
    _prepare(root)
    _record(root, {"CN:000001", V3_SYMBOL})
    claim_profile_task(
        root=root,
        agent="/root/first-activated",
        claimed_at=RECORDED_AT + dt.timedelta(minutes=1),
        symbol="CN:000001",
        run_id=RUN_ID,
    )
    path = root / f"{projection}.jsonl"
    rows = _by_symbol(path)
    rows["CN:000001"][field] = "f" * 64
    write_jsonl(path, list(rows.values()))

    with pytest.raises(
        ResearchAllocationError,
        match=(
            "immutable allocation binding drifted|"
            "sealed active stage claim has unrecognized queue drift"
        ),
    ):
        claim_profile_task(
            root=root,
            agent="/root/second-blocked",
            claimed_at=RECORDED_AT + dt.timedelta(minutes=2),
            symbol=V3_SYMBOL,
            run_id=RUN_ID,
        )


def test_later_full_market_claim_accepts_sealed_quick_profile_completion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.test_profile_workflow import _manager_bound_package, _policy
    from trading_os.research_assets.profile_workflow import (
        claim_profile_task,
        record_profile_package,
    )

    symbol = "CN:000001"
    root = _ready_full_market(tmp_path, monkeypatch)
    _prepare(root)
    recorded = _record(root, {symbol, V3_SYMBOL})
    claim_profile_task(
        root=root,
        agent="/root/first-activated",
        claimed_at=RECORDED_AT + dt.timedelta(minutes=1),
        symbol=symbol,
        run_id=RUN_ID,
    )
    queue = _by_symbol(root / "research_queue.jsonl")[symbol]
    package = _manager_bound_package(queue)
    package["cycle_id"] = recorded["profile_cycle_id"]
    package["company_name"] = queue["name"]
    package["profile"]["symbol"] = symbol
    package["profile"]["as_of"] = RECORDED_AT.date().isoformat()
    package["profile"]["information_cutoff"] = (
        RECORDED_AT + dt.timedelta(minutes=1)
    ).isoformat()
    package["price_as_of"] = (RECORDED_AT - dt.timedelta(days=1)).isoformat()
    package["provenance"]["agent"] = "/root/first-activated"
    package["provenance"]["generated_at"] = (
        RECORDED_AT + dt.timedelta(minutes=1)
    ).isoformat()
    package["manager_screen_binding"] = {
        "result_path": queue["manager_screen_allocation_result_path"],
        "result_sha256": queue["manager_screen_allocation_result_sha256"],
        "decisive_question": queue["decisive_question"],
        "evidence_ids": list(queue["evidence_ids"]),
    }
    record_profile_package(
        package,
        root=root,
        policy=_policy(),
        policy_reference="research-allocation.default@1.0.0",
        recorded_at=RECORDED_AT + dt.timedelta(minutes=2),
    )

    claimed = claim_profile_task(
        root=root,
        agent="/root/second-activated",
        claimed_at=RECORDED_AT + dt.timedelta(minutes=3),
        symbol=V3_SYMBOL,
        run_id=RUN_ID,
    )
    assert claimed["symbol"] == V3_SYMBOL


def test_full_market_quick_profile_release_retry_does_not_block_other_claims(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_os.research_assets.profile_workflow import (
        claim_profile_task,
        release_profile_task,
    )

    symbol = "CN:000001"
    root = _ready_full_market(tmp_path, monkeypatch)
    _prepare(root)
    _record(root, {symbol, V3_SYMBOL})
    claim_profile_task(
        root=root,
        agent="/root/first-attempt",
        claimed_at=RECORDED_AT + dt.timedelta(minutes=1),
        symbol=symbol,
        run_id=RUN_ID,
    )
    release_profile_task(
        root=root,
        agent="/root/first-attempt",
        symbol=symbol,
        failure_reason="temporary source extraction failure",
        released_at=RECORDED_AT + dt.timedelta(minutes=2),
    )
    retry_at = RECORDED_AT + dt.timedelta(minutes=3)
    retried = claim_profile_task(
        root=root,
        agent="/root/retry-attempt",
        claimed_at=retry_at,
        symbol=symbol,
        run_id=RUN_ID,
    )
    assert retried["started_at"] == retry_at.isoformat()
    assert _by_symbol(root / "research_queue.jsonl")[symbol]["attempt_history"]

    other = claim_profile_task(
        root=root,
        agent="/root/other-company",
        claimed_at=RECORDED_AT + dt.timedelta(minutes=4),
        symbol=V3_SYMBOL,
        run_id=RUN_ID,
    )
    assert other["symbol"] == V3_SYMBOL


def test_full_market_receipt_only_crash_replays_for_original_agent_and_time(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_os.research_assets import profile_workflow
    from trading_os.research_assets.research_allocation import ResearchAllocationError

    symbol = "CN:000001"
    root = _ready_full_market(tmp_path, monkeypatch)
    _prepare(root)
    recorded = _record(root, {symbol})
    original_write_jsonl = profile_workflow.write_jsonl

    def fail_queue_projection(*args: object, **kwargs: object) -> None:
        raise OSError("simulated queue projection crash")

    monkeypatch.setattr(profile_workflow, "write_jsonl", fail_queue_projection)
    activation_at = RECORDED_AT + dt.timedelta(minutes=1)
    with pytest.raises(OSError, match="simulated queue projection crash"):
        profile_workflow.claim_profile_task(
            root=root,
            agent="/root/crashed-claim",
            claimed_at=activation_at,
            symbol=symbol,
            run_id=RUN_ID,
        )
    monkeypatch.setattr(profile_workflow, "write_jsonl", original_write_jsonl)

    receipt_path = (
        root
        / "profiles"
        / recorded["profile_cycle_id"]
        / "full-market-claim-activation"
        / "receipts"
        / "CN-000001.json"
    )
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["activated_at"] == activation_at.isoformat()
    assert _by_symbol(root / "research_queue.jsonl")[symbol]["status"] == "pending"

    retry_at = RECORDED_AT + dt.timedelta(minutes=2)
    with pytest.raises(ResearchAllocationError, match="no eligible profile task"):
        profile_workflow.claim_profile_task(
            root=root,
            agent="/root/different-claim",
            claimed_at=retry_at,
            symbol=symbol,
            run_id=RUN_ID,
        )
    recovered = profile_workflow.claim_profile_task(
        root=root,
        agent="/root/crashed-claim",
        claimed_at=retry_at,
        symbol=symbol,
        run_id=RUN_ID,
    )
    assert recovered["started_at"] == activation_at.isoformat()
    assert json.loads(receipt_path.read_text(encoding="utf-8"))["activated_at"] == (
        activation_at.isoformat()
    )


def test_sealed_targeted_approval_does_not_block_another_full_market_claim(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.test_profile_workflow import ROOT as PROJECT_ROOT
    from tests.test_profile_workflow import _manager_bound_package, _policy
    from trading_os.research_assets.profile_workflow import (
        approve_targeted_followup,
        claim_profile_task,
        profile_cycle_status,
        record_profile_package,
    )

    symbol = "CN:000001"
    root = _ready_full_market(tmp_path, monkeypatch)
    policy_path = tmp_path / "policies" / "research-allocation.json"
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_bytes((PROJECT_ROOT / "policies" / "research-allocation.json").read_bytes())
    _prepare(root)
    recorded = _record(root, {symbol, V3_SYMBOL})
    claim_profile_task(
        root=root,
        agent="/root/targeted-candidate-researcher",
        claimed_at=RECORDED_AT + dt.timedelta(minutes=1),
        symbol=symbol,
        run_id=RUN_ID,
    )
    queue = _by_symbol(root / "research_queue.jsonl")[symbol]
    package = _manager_bound_package(queue)
    package["cycle_id"] = recorded["profile_cycle_id"]
    package["company_name"] = queue["name"]
    package["profile"].update(
        {
            "symbol": symbol,
            "as_of": RECORDED_AT.date().isoformat(),
            "information_cutoff": (
                RECORDED_AT + dt.timedelta(minutes=1)
            ).isoformat(),
            "governance_status": "uncertain",
            "normalized_earnings_status": "uncertain",
        }
    )
    package["profile"]["valuation"]["base_expected_annual_return"] = 0.06
    package["profile"]["valuation"]["bull_expected_annual_return"] = 0.12
    package["price_as_of"] = (RECORDED_AT - dt.timedelta(days=1)).isoformat()
    package["provenance"]["agent"] = "/root/targeted-candidate-researcher"
    package["provenance"]["generated_at"] = (
        RECORDED_AT + dt.timedelta(minutes=1)
    ).isoformat()
    package["manager_screen_binding"] = {
        "result_path": queue["manager_screen_allocation_result_path"],
        "result_sha256": queue["manager_screen_allocation_result_sha256"],
        "decisive_question": queue["decisive_question"],
        "evidence_ids": list(queue["evidence_ids"]),
    }
    recorded_profile = record_profile_package(
        package,
        root=root,
        policy=_policy(),
        policy_reference="research-allocation.default@1.0.0",
        recorded_at=RECORDED_AT + dt.timedelta(minutes=2),
    )
    assert recorded_profile["next_stage"] == "targeted_followup_candidate"
    profile_status = profile_cycle_status(
        root=root,
        cycle_id=recorded["profile_cycle_id"],
    )
    assert profile_status["recorded_count"] == 1
    assert profile_status["remaining_count"] == 1
    assert profile_status["invalid_artifact_count"] == 0
    approved = approve_targeted_followup(
        root=root,
        symbol=symbol,
        manager=_manager()["agent"],
        reason="Approve one bounded evidence follow-up from the sealed candidate.",
        policy=_policy(),
        approved_at=RECORDED_AT + dt.timedelta(minutes=3),
    )
    assert approved["task_type"] == "targeted_followup"

    other = claim_profile_task(
        root=root,
        agent="/root/other-after-targeted",
        claimed_at=RECORDED_AT + dt.timedelta(minutes=4),
        symbol=V3_SYMBOL,
        run_id=RUN_ID,
    )
    assert other["symbol"] == V3_SYMBOL


def test_research_candidate_followup_binding_requires_semantic_full_market_grant(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_os.research_assets import profile_workflow
    from trading_os.research_assets.research_allocation import ResearchAllocationError

    root = _ready_full_market(tmp_path, monkeypatch)
    _prepare(root)
    _record(root, {V3_SYMBOL})
    queue = _by_symbol(root / "research_queue.jsonl")[V3_SYMBOL]
    screen = _by_symbol(root / "screening.jsonl")[V3_SYMBOL]
    repository_root = root.parent.parent.resolve()

    binding = profile_workflow._targeted_followup_manager_binding(
        queue,
        screen=screen,
        symbol=V3_SYMBOL,
        manager=_manager()["agent"],
        root=root,
        repository_root=repository_root,
    )
    assert binding["route"] == "research_candidate"

    tampered_rows = []
    wrong_candidate = dict(queue)
    wrong_candidate["manager_screen_allocation_candidate_sha256"] = "f" * 64
    tampered_rows.append((wrong_candidate, screen))
    wrong_cycle = dict(queue)
    wrong_cycle["profile_cycle_id"] = "wrong-cycle"
    tampered_rows.append((wrong_cycle, screen))
    wrong_run = dict(queue)
    wrong_run["manager_screen_run_id"] = "wrong-run"
    tampered_rows.append((wrong_run, screen))
    wrong_projection = dict(screen)
    wrong_projection["manager_screen_allocation_result_sha256"] = "f" * 64
    tampered_rows.append((queue, wrong_projection))

    for tampered_queue, tampered_screen in tampered_rows:
        with pytest.raises(ResearchAllocationError):
            profile_workflow._targeted_followup_manager_binding(
                tampered_queue,
                screen=tampered_screen,
                symbol=V3_SYMBOL,
                manager=_manager()["agent"],
                root=root,
                repository_root=repository_root,
            )


def test_targeted_followup_approval_rechecks_funded_full_market_symbol(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_os.research_assets.profile_workflow import approve_targeted_followup
    from trading_os.research_assets.research_allocation import ResearchAllocationError

    root = _ready_full_market(tmp_path, monkeypatch)
    _prepare(root)
    _record(root, {V3_SYMBOL})
    queue_path = root / "research_queue.jsonl"
    screening_path = root / "screening.jsonl"
    queue = _by_symbol(queue_path)
    screens = _by_symbol(screening_path)
    queue[V3_SYMBOL].update(
        {
            "task_type": "quick_profile",
            "status": "completed",
            "assigned_agent": "/root/researcher",
        }
    )
    saved_run_id = queue[V3_SYMBOL].pop("manager_screen_run_id")
    screens[V3_SYMBOL]["decision"] = "targeted_followup_candidate"
    write_jsonl(queue_path, list(queue.values()))
    write_jsonl(screening_path, list(screens.values()))
    with pytest.raises(ResearchAllocationError, match="cannot drop"):
        approve_targeted_followup(
            root=root,
            symbol=V3_SYMBOL,
            manager=_manager()["agent"],
            reason="Explicit manager approval must retain the sealed run binding.",
            policy={},
            approved_at=RECORDED_AT + dt.timedelta(minutes=5),
        )
    queue[V3_SYMBOL]["manager_screen_run_id"] = saved_run_id
    queue[V3_SYMBOL].pop("manager_screen_allocation_result_path")
    write_jsonl(queue_path, list(queue.values()))
    write_jsonl(screening_path, list(screens.values()))

    with pytest.raises(
        ResearchAllocationError,
        match="targeted-followup approval is not backed by a funded full-market allocation",
    ):
        approve_targeted_followup(
            root=root,
            symbol=V3_SYMBOL,
            manager=_manager()["agent"],
            reason="批准补齐决定性问题所需的有限证据。",
            policy={},
            approved_at=RECORDED_AT + dt.timedelta(minutes=5),
        )


def test_profile_record_cannot_fall_back_when_full_market_path_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.test_profile_workflow import _manager_bound_package, _policy
    from trading_os.research_assets.profile_workflow import (
        claim_profile_task,
        record_profile_package,
    )
    from trading_os.research_assets.research_allocation import ResearchAllocationError

    symbol = "CN:000001"
    root = _ready_full_market(tmp_path, monkeypatch)
    _prepare(root)
    recorded = _record(root, {symbol})
    claim_profile_task(
        root=root,
        agent="/root/full-market-researcher",
        claimed_at=RECORDED_AT + dt.timedelta(minutes=1),
        symbol=symbol,
        run_id=RUN_ID,
    )
    queue_path = root / "research_queue.jsonl"
    queue = _by_symbol(queue_path)
    package = _manager_bound_package(queue[symbol])
    package["cycle_id"] = recorded["profile_cycle_id"]
    package["company_name"] = queue[symbol]["name"]
    package["profile"]["symbol"] = symbol
    package["profile"]["as_of"] = RECORDED_AT.date().isoformat()
    package["profile"]["information_cutoff"] = (
        RECORDED_AT + dt.timedelta(minutes=1)
    ).isoformat()
    package["price_as_of"] = (RECORDED_AT - dt.timedelta(days=1)).isoformat()
    package["provenance"]["agent"] = "/root/full-market-researcher"
    package["provenance"]["generated_at"] = (
        RECORDED_AT + dt.timedelta(minutes=1)
    ).isoformat()
    queue[symbol].pop("manager_screen_allocation_result_path")
    write_jsonl(queue_path, list(queue.values()))

    with pytest.raises(
        ResearchAllocationError,
        match="profile record is not backed by a funded full-market allocation",
    ):
        record_profile_package(
            package,
            root=root,
            policy=_policy(),
            policy_reference="research-allocation.default@1.0.0",
            recorded_at=RECORDED_AT + dt.timedelta(minutes=2),
        )


def test_profile_record_binds_final_full_market_research_brief(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.test_profile_workflow import _manager_bound_package, _policy
    from trading_os.research_assets.profile_workflow import (
        claim_profile_task,
        record_profile_package,
    )
    from trading_os.research_assets.research_allocation import ResearchAllocationError

    symbol = "CN:000001"
    root = _ready_full_market(tmp_path, monkeypatch)
    _prepare(root)
    recorded = _record(root, {symbol})
    claim_profile_task(
        root=root,
        agent="/root/full-market-researcher",
        claimed_at=RECORDED_AT + dt.timedelta(minutes=1),
        symbol=symbol,
        run_id=RUN_ID,
    )
    queue = _by_symbol(root / "research_queue.jsonl")[symbol]
    package = _manager_bound_package(queue)
    package["cycle_id"] = recorded["profile_cycle_id"]
    package["company_name"] = queue["name"]
    package["profile"]["symbol"] = symbol
    package["profile"]["as_of"] = RECORDED_AT.date().isoformat()
    package["profile"]["information_cutoff"] = (
        RECORDED_AT + dt.timedelta(minutes=1)
    ).isoformat()
    package["price_as_of"] = (RECORDED_AT - dt.timedelta(days=1)).isoformat()
    package["provenance"]["agent"] = "/root/full-market-researcher"
    package["provenance"]["generated_at"] = (
        RECORDED_AT + dt.timedelta(minutes=1)
    ).isoformat()

    with pytest.raises(ResearchAllocationError, match="manager_screen_binding"):
        record_profile_package(
            package,
            root=root,
            policy=_policy(),
            policy_reference="research-allocation.default@1.0.0",
            recorded_at=RECORDED_AT + dt.timedelta(minutes=2),
        )
    package["manager_screen_binding"] = {
        "result_path": queue["manager_screen_allocation_result_path"],
        "result_sha256": queue["manager_screen_allocation_result_sha256"],
        "decisive_question": queue["decisive_question"],
        "evidence_ids": list(queue["evidence_ids"]),
    }
    wrong_question = json.loads(json.dumps(package))
    wrong_question["manager_screen_binding"]["decisive_question"] = "forged question"
    with pytest.raises(ResearchAllocationError, match="manager_screen_binding"):
        record_profile_package(
            wrong_question,
            root=root,
            policy=_policy(),
            policy_reference="research-allocation.default@1.0.0",
            recorded_at=RECORDED_AT + dt.timedelta(minutes=2),
        )

    result = record_profile_package(
        package,
        root=root,
        policy=_policy(),
        policy_reference="research-allocation.default@1.0.0",
        recorded_at=RECORDED_AT + dt.timedelta(minutes=2),
    )
    stored = json.loads((tmp_path / result["profile_path"]).read_text(encoding="utf-8"))
    assert stored["manager_screen_binding"] == package["manager_screen_binding"]


def test_claim_rejects_research_brief_and_calibration_projection_tampering(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_os.research_assets.profile_workflow import claim_profile_task
    from trading_os.research_assets.research_allocation import ResearchAllocationError

    symbol = "CN:900009"
    root = _ready_full_market(tmp_path, monkeypatch)
    batch_id = "batch-calibration-profile-claim"
    decisions = [(symbol, "pass", 9009)]
    _add_terminal_decision_batch(root, batch_id=batch_id, decisions=decisions)
    _add_calibration_result(
        root,
        batch_id=batch_id,
        reviews=[_calibration_review(symbol)],
    )
    _extend_mock_scope(root, decisions=decisions, batch_id=batch_id)
    _prepare(root)
    _record(root, {symbol})
    queue_path = root / "research_queue.jsonl"
    screening_path = root / "screening.jsonl"
    expected_queue = _by_symbol(queue_path)
    expected_screen = _by_symbol(screening_path)
    calibration_fields = [
        "manager_screen_calibration_result_path",
        "manager_screen_calibration_result_sha256",
        "manager_screen_calibration_review_sha256",
        "manager_screen_calibration_adjudication_sha256",
    ]
    tamper_cases = [
        ("queue", "decisive_question", "forged queue question"),
        ("queue", "evidence_ids", ["forged:queue"]),
        ("screen", "decisive_question", "forged screen question"),
        ("screen", "evidence", ["forged:screen"]),
        *[("queue", field, "f" * 64) for field in calibration_fields],
        *[("screen", field, "f" * 64) for field in calibration_fields],
    ]
    for target, field, value in tamper_cases:
        queue = json.loads(json.dumps(expected_queue))
        screens = json.loads(json.dumps(expected_screen))
        (queue if target == "queue" else screens)[symbol][field] = value
        write_jsonl(queue_path, list(queue.values()))
        write_jsonl(screening_path, list(screens.values()))
        with pytest.raises(ResearchAllocationError, match="not authorized"):
            claim_profile_task(
                root=root,
                agent="/root/calibration-tamper",
                claimed_at=RECORDED_AT + dt.timedelta(minutes=1),
                symbol=symbol,
                run_id=RUN_ID,
            )

    queue = json.loads(json.dumps(expected_queue))
    queue[symbol].pop("manager_screen_run_id")
    write_jsonl(queue_path, list(queue.values()))
    write_jsonl(screening_path, list(expected_screen.values()))
    with pytest.raises(ResearchAllocationError, match="cannot drop"):
        claim_profile_task(
            root=root,
            agent="/root/calibration-missing-run",
            claimed_at=RECORDED_AT + dt.timedelta(minutes=1),
            symbol=symbol,
            run_id=RUN_ID,
        )

    write_jsonl(queue_path, list(expected_queue.values()))
    write_jsonl(screening_path, list(expected_screen.values()))
    claimed = claim_profile_task(
        root=root,
        agent="/root/calibration-valid",
        claimed_at=RECORDED_AT + dt.timedelta(minutes=1),
        symbol=symbol,
        run_id=RUN_ID,
    )
    assert claimed["manager_screen_allocation_decision"] == "fund_quick_profile"
    for field in calibration_fields:
        assert claimed[field] == expected_queue[symbol][field]
