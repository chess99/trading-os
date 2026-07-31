from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

RUN_ID = "2026-07-31-test-transition"
FROZEN_AT = dt.datetime(2026, 7, 31, 8, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))
RECORDED_AT = dt.datetime(2026, 7, 31, 9, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )


def _seal(
    path: Path,
    payload: Any,
    artifact_type: str,
    *,
    sealed_at: dt.datetime = FROZEN_AT,
):
    from trading_os.research_assets.sealing import seal_json

    return seal_json(
        path,
        payload,
        artifact_type=artifact_type,
        sealed_at=sealed_at,
    )


def _profile_pair(
    repository_root: Path,
    *,
    symbol: str,
    cycle: str,
    stamp: str,
    stage: str,
) -> tuple[str, str, str, str]:
    ticker = symbol.split(":", 1)[1]
    profile_path = (
        repository_root
        / "coverage"
        / "cn-a"
        / "profiles"
        / cycle
        / ticker
        / f"{stamp}.profile.json"
    )
    evaluation_path = profile_path.with_name(f"{stamp}.evaluation.json")
    profile_seal = _seal(
        profile_path,
        {
            "schema_version": 2,
            "symbol": symbol,
            "stage": stage,
            "profile": {
                "research_stage": stage,
                "information_cutoff": "2026-07-31T07:25:00+08:00",
            },
            "claims": [],
        },
        "quick_profile_package",
    )
    evaluation_seal = _seal(
        evaluation_path,
        {
            "schema_version": 1,
            "symbol": symbol,
            "stage": stage,
            "next_stage": "price_watch",
        },
        "quick_profile_evaluation",
    )
    return (
        profile_path.relative_to(repository_root).as_posix(),
        profile_seal.sha256,
        evaluation_path.relative_to(repository_root).as_posix(),
        evaluation_seal.sha256,
    )


def _transition_fixture(tmp_path: Path) -> dict[str, Any]:
    from trading_os.research_assets.coverage_store import write_jsonl

    repository_root = tmp_path / "repo"
    coverage_root = repository_root / "coverage" / "cn-a"
    scope_dir = coverage_root / "scopes" / RUN_ID
    symbols = {
        "direct": "CN:000001",
        "bridge": "CN:000002",
        "rescreen": "CN:000003",
        "defer": "CN:000004",
    }

    direct_current = _profile_pair(
        repository_root,
        symbol=symbols["direct"],
        cycle="current-cycle",
        stamp="direct-current",
        stage="quick_profile",
    )
    direct_high = _profile_pair(
        repository_root,
        symbol=symbols["direct"],
        cycle="older-cycle",
        stamp="direct-scoped",
        stage="scoped_research",
    )
    bridge_scoped = _profile_pair(
        repository_root,
        symbol=symbols["bridge"],
        cycle="bridge-cycle",
        stamp="bridge-scoped",
        stage="scoped_research",
    )

    terminal_members = []
    for key in ("rescreen", "defer"):
        symbol = symbols[key]
        ticker = symbol.split(":", 1)[1]
        terminal_path = coverage_root / "triage" / "legacy-cycle" / ticker / "terminal.triage.json"
        terminal_seal = _seal(
            terminal_path,
            {
                "schema_version": 1,
                "symbol": symbol,
                "disposition": "price_watch",
            },
            "rapid_triage_package",
        )
        terminal_members.append(
            {
                "symbol": symbol,
                "name": f"Company {ticker}",
                "current_protocol_terminal": True,
                "terminal_path": terminal_path.relative_to(repository_root).as_posix(),
                "terminal_sha256": terminal_seal.sha256,
            }
        )

    manifest_path = scope_dir / "manifest.json"
    manifest = {
        "schema_version": 1,
        "run_id": RUN_ID,
        "scope_cutoff": "2026-07-31T07:00:00+08:00",
        "members": [
            {
                "symbol": symbols["direct"],
                "name": "Direct",
                "current_protocol_terminal": False,
            },
            {
                "symbol": symbols["bridge"],
                "name": "Bridge",
                "current_protocol_terminal": False,
            },
            *terminal_members,
        ],
    }
    manifest_seal = _seal(
        manifest_path,
        manifest,
        "all_a_scope_manifest",
    )
    intake_path = scope_dir / "baseline-intake.json"
    intake = {
        "schema_version": 1,
        "run_id": RUN_ID,
        "scope_cutoff": manifest["scope_cutoff"],
        "scope_manifest_path": manifest_path.relative_to(repository_root).as_posix(),
        "scope_manifest_sha256": manifest_seal.sha256,
        "members": [
            {
                "symbol": symbols["direct"],
                "name": "Direct",
                "materialization_action": "defer_active_or_deeper_stage",
            },
            {
                "symbol": symbols["bridge"],
                "name": "Bridge",
                "materialization_action": "defer_active_or_deeper_stage",
            },
        ],
    }
    _seal(intake_path, intake, "all_a_baseline_intake")

    bridge_company_dir = repository_root / "research" / "companies" / "CN" / "000002"
    bridge_report_path = bridge_company_dir / "reports" / "legacy-deep.md"
    bridge_report_path.parent.mkdir(parents=True, exist_ok=True)
    bridge_report_path.write_text("# Legacy deep report\n", encoding="utf-8")
    bridge_report_sha256 = hashlib.sha256(bridge_report_path.read_bytes()).hexdigest()
    bridge_meta_path = bridge_company_dir / "meta.json"
    _write_json(
        bridge_meta_path,
        {
            "schema_version": 2,
            "identity": {"symbol": symbols["bridge"], "name": "Bridge"},
            "research": {
                "coverage_status": "covered",
                "rebaseline_required": False,
                "information_cutoff": "2026-07-31T07:40:00+08:00",
            },
            "reports": {
                "latest": "reports/legacy-deep.md",
                "history": [
                    {
                        "report_id": "CN-000002-legacy-deep",
                        "path": "reports/legacy-deep.md",
                        "sha256": bridge_report_sha256,
                    }
                ],
            },
        },
    )

    direct_queue = {
        "symbol": symbols["direct"],
        "name": "Direct",
        "task_type": "quick_profile",
        "status": "completed",
        "priority": 3,
        "reason": "current formal evidence",
        "target_company_dir": "research/companies/CN/000001",
        "result_path": direct_current[2],
        "finished_at": "2026-07-31T07:30:00+08:00",
        "allocation_sha256": "a" * 64,
        "selected_by": ["legacy_manager"],
        "profile_cycle_id": "current-cycle",
        "triage_cycle_id": "legacy-cycle",
        "triage_disposition": "triage_candidate",
        "stage_history": [
            {
                "stage": "scoped_research",
                "status": "completed",
                "result_path": direct_high[0],
                "evaluation_path": direct_high[2],
                "finished_at": "2026-07-30T06:00:00+08:00",
            },
            {
                "stage": "quick_profile",
                "status": "completed",
                "result_path": direct_current[0],
                "evaluation_path": direct_current[2],
                "finished_at": "2026-07-31T07:30:00+08:00",
            },
        ],
    }
    bridge_queue = {
        "symbol": symbols["bridge"],
        "name": "Bridge",
        "task_type": "deep_research",
        "status": "completed",
        "priority": 3,
        "reason": "legacy deep report",
        "target_company_dir": "research/companies/CN/000002",
        "result_path": "reports/legacy-deep.md",
        "finished_at": "2026-07-31T07:40:00+08:00",
        "allocation_sha256": "b" * 64,
        "selected_by": ["legacy_manager"],
        "profile_cycle_id": "bridge-cycle",
        "stage_history": [
            {
                "stage": "scoped_research",
                "status": "completed",
                "result_path": bridge_scoped[0],
                "evaluation_path": bridge_scoped[2],
                "finished_at": "2026-07-31T07:20:00+08:00",
            }
        ],
    }
    rescreen_queue = {
        "symbol": symbols["rescreen"],
        "name": "Rescreen",
        "task_type": "rapid_triage",
        "status": "completed",
        "priority": 3,
        "reason": "legacy terminal only",
        "target_company_dir": "research/companies/CN/000003",
        "result_path": terminal_members[0]["terminal_path"],
        "finished_at": "2026-07-31T07:10:00+08:00",
        "triage_cycle_id": "legacy-cycle",
        "triage_disposition": "price_watch",
        "triage_selection_path": "coverage/cn-a/triage/legacy-cycle/selection.json",
        "triage_selection_sha256": "c" * 64,
        "cohort_path": "coverage/cn-a/triage/legacy-cycle/cohort.json",
        "cohort_sha256": "d" * 64,
        "cohort_ordinal": 1,
        "stage_history": [
            {
                "stage": "rapid_triage",
                "status": "completed",
                "result_path": terminal_members[0]["terminal_path"],
            }
        ],
    }
    defer_queue = {
        "symbol": symbols["defer"],
        "name": "Defer",
        "task_type": "quick_profile",
        "status": "pending",
        "priority": 3,
        "reason": "active formal task",
        "target_company_dir": "research/companies/CN/000004",
        "result_path": terminal_members[1]["terminal_path"],
        "triage_cycle_id": "legacy-cycle",
        "triage_disposition": "triage_candidate",
        "stage_history": [
            {
                "stage": "rapid_triage",
                "status": "completed",
                "result_path": terminal_members[1]["terminal_path"],
            }
        ],
    }
    for ticker in ("000001", "000003", "000004"):
        (repository_root / "research" / "companies" / "CN" / ticker).mkdir(
            parents=True,
            exist_ok=True,
        )
    direct_meta_path = repository_root / "research" / "companies" / "CN" / "000001" / "meta.json"
    _write_json(
        direct_meta_path,
        {
            "schema_version": 2,
            "identity": {
                "symbol": symbols["direct"],
                "market": "CN",
                "ticker": "000001",
                "name": "Direct",
                "currency": "CNY",
                "security_status": "active",
            },
            "research": {
                "coverage_status": "requires_rebaseline",
                "rebaseline_required": True,
                "information_cutoff": None,
            },
            "reports": {
                "latest": None,
                "latest_by_type": {},
                "history": [],
                "historical_artifacts": [],
            },
            "underwriting": {
                "status": None,
                "review_id": None,
                "confidence": None,
                "evidence_valid_until": None,
                "reason_codes": ["legacy_reports_require_structured_rebaseline"],
            },
            "valuation": {
                "currency": None,
                "price_as_of": None,
                "bear_value": None,
                "fair_value_range": None,
                "buy_zone": None,
                "reduce_zone": None,
            },
            "triggers": [],
            "updated_at": "2026-07-21T21:15:00+08:00",
        },
    )
    queue = [direct_queue, bridge_queue, rescreen_queue, defer_queue]
    write_jsonl(coverage_root / "research_queue.jsonl", queue)
    write_jsonl(coverage_root / "screening.jsonl", [])

    classification = {
        "schema_version": 1,
        "adoption": [symbols["direct"], symbols["bridge"]],
        "rescreen": [symbols["rescreen"]],
        "defer_active": [symbols["defer"]],
        "legacy_bridges": [
            {
                "symbol": symbols["bridge"],
                "report_path": bridge_report_path.relative_to(repository_root).as_posix(),
                "report_sha256": bridge_report_sha256,
                "meta_path": bridge_meta_path.relative_to(repository_root).as_posix(),
                "scoped_profile_path": bridge_scoped[0],
                "scoped_profile_sha256": bridge_scoped[1],
                "scoped_evaluation_path": bridge_scoped[2],
                "scoped_evaluation_sha256": bridge_scoped[3],
            }
        ],
    }
    return {
        "repository_root": repository_root,
        "coverage_root": coverage_root,
        "symbols": symbols,
        "classification": classification,
        "queue": {item["symbol"]: item for item in queue},
        "direct_current": direct_current,
        "bridge_report_path": bridge_report_path,
    }


def _submission(symbols: dict[str, str]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manager": {
            "agent": "/root/manager",
            "model": "gpt-test",
            "tools": ["sealed transition packet"],
        },
        "decisions": [
            {
                "symbol": symbols["direct"],
                "route": "watch",
                "one_line_reason": "Formal evidence is useful but the trigger is not ready.",
                "decisive_question": "Does the next filing confirm normalized cash flow?",
                "revisit_triggers": [
                    {
                        "type": "filing",
                        "condition": {"description": "next interim report"},
                        "reason": "Refresh normalized cash flow.",
                    }
                ],
                "confidence": "medium",
                "evidence_ids": [
                    f"transition:formal:{symbols['direct']}",
                ],
            },
            {
                "symbol": symbols["bridge"],
                "route": "send_to_analyst",
                "one_line_reason": "The bridged report leaves one decisive question.",
                "decisive_question": "Can the legacy thesis be verified from current filings?",
                "revisit_triggers": [],
                "confidence": "low",
                "evidence_ids": [
                    f"transition:formal:{symbols['bridge']}",
                    f"transition:legacy-report:{symbols['bridge']}",
                ],
            },
        ],
    }


def test_transition_freeze_record_status_preserves_formal_high_watermark_and_history(
    tmp_path: Path,
):
    from trading_os.research_assets.coverage_store import read_jsonl
    from trading_os.research_assets.legacy_transition import (
        freeze_legacy_transition,
        legacy_transition_status,
        record_legacy_transition,
    )
    from trading_os.research_assets.sealing import verify_sealed

    fixture = _transition_fixture(tmp_path)
    root = fixture["coverage_root"]
    frozen = freeze_legacy_transition(
        root=root,
        run_id=RUN_ID,
        classification=fixture["classification"],
        frozen_at=FROZEN_AT,
    )
    replay = freeze_legacy_transition(
        root=root,
        run_id=RUN_ID,
        classification=fixture["classification"],
        frozen_at=FROZEN_AT,
    )
    assert replay == frozen
    assert frozen["classification"] == {
        "adoption": 2,
        "rescreen": 1,
        "defer_active": 1,
        "total": 4,
    }
    transition_dir = root / "manager-screen" / RUN_ID / "legacy-transition-001"
    verify_sealed(transition_dir / "plan.json")
    verify_sealed(transition_dir / "packet.json")
    assert not (fixture["bridge_report_path"].with_name("legacy-deep.md.seal.json")).exists()

    recorded = record_legacy_transition(
        root=root,
        run_id=RUN_ID,
        submission=_submission(fixture["symbols"]),
        recorded_at=RECORDED_AT,
    )
    replay_record = record_legacy_transition(
        root=root,
        run_id=RUN_ID,
        submission=_submission(fixture["symbols"]),
        recorded_at=RECORDED_AT,
    )
    assert replay_record == recorded
    assert (
        freeze_legacy_transition(
            root=root,
            run_id=RUN_ID,
            classification=fixture["classification"],
            frozen_at=FROZEN_AT,
        )
        == frozen
    )
    verify_sealed(transition_dir / "result.json")

    queue = {item["symbol"]: item for item in read_jsonl(root / "research_queue.jsonl")}
    direct = queue[fixture["symbols"]["direct"]]
    assert direct["task_type"] == "quick_profile"
    assert direct["status"] == "completed"
    assert direct["result_path"] == fixture["direct_current"][2]
    assert direct["research_stage_high_watermark"] == "scoped_research"
    assert direct["manager_screen_route"] == "watch"
    assert "allocation_sha256" not in direct
    assert "profile_cycle_id" not in direct
    assert "triage_cycle_id" not in direct
    assert direct["stage_history"][-2]["stage"] == "legacy_transition_source_snapshot"
    assert direct["stage_history"][-2]["live_fields"]["allocation_sha256"] == "a" * 64
    assert direct["stage_history"][-1]["stage"] == "manager_screen"
    assert direct["stage_history"][-1]["adopted_formal_source"]["kind"] == ("sealed_formal")

    bridge = queue[fixture["symbols"]["bridge"]]
    assert bridge["task_type"] == "deep_research"
    assert bridge["status"] == "completed"
    assert "preceding_stage" not in bridge
    assert "effort_budget_hours" not in bridge
    assert bridge["result_path"] == "reports/legacy-deep.md"
    assert bridge["evidence_ids"] == [
        f"transition:formal:{fixture['symbols']['bridge']}",
        f"transition:legacy-report:{fixture['symbols']['bridge']}",
    ]
    assert bridge["research_stage_high_watermark"] == "deep_research"
    assert bridge["stage_history"][-1]["adopted_formal_source"]["kind"] == ("legacy_report_bridge")

    rescreen = queue[fixture["symbols"]["rescreen"]]
    assert rescreen["task_type"] == "manager_screen"
    assert rescreen["status"] == "pending"
    assert rescreen["result_path"] is None
    assert "triage_cycle_id" not in rescreen
    assert rescreen["stage_history"][-2]["live_fields"]["cohort_ordinal"] == 1
    assert rescreen["stage_history"][-1]["action"] == "rescreen"

    assert queue[fixture["symbols"]["defer"]] == fixture["queue"][fixture["symbols"]["defer"]]
    direct_meta_path = (
        fixture["repository_root"]
        / "research"
        / "companies"
        / "CN"
        / "000001"
        / "meta.json"
    )
    direct_meta_text = direct_meta_path.read_text(encoding="utf-8")
    direct_meta = json.loads(direct_meta_text)
    assert direct_meta_text.endswith("\n")
    assert "\n  \"identity\"" in direct_meta_text
    assert direct_meta["research"] == {
        "coverage_status": "covered",
        "rebaseline_required": False,
        "information_cutoff": "2026-07-31T07:25:00+08:00",
    }
    assert direct_meta["reports"] == {
        "latest": None,
        "latest_by_type": {},
        "history": [],
        "historical_artifacts": [],
    }
    status = legacy_transition_status(root=root, run_id=RUN_ID)
    assert status["state"] == "recorded"
    assert status["materialized"] == {
        "adoption": 2,
        "rescreen": 1,
        "defer_active": 1,
    }
    assert status["company_meta_sync"] == {"planned": 1, "completed": 1}


def test_transition_rejects_overlap_and_population_loss(tmp_path: Path):
    from trading_os.research_assets.legacy_transition import (
        LegacyTransitionError,
        freeze_legacy_transition,
    )

    fixture = _transition_fixture(tmp_path)
    overlap = dict(fixture["classification"])
    overlap["rescreen"] = [
        fixture["symbols"]["rescreen"],
        fixture["symbols"]["direct"],
    ]
    with pytest.raises(LegacyTransitionError, match="overlap"):
        freeze_legacy_transition(
            root=fixture["coverage_root"],
            run_id=RUN_ID,
            classification=overlap,
            frozen_at=FROZEN_AT,
        )

    missing = dict(fixture["classification"])
    missing["defer_active"] = []
    with pytest.raises(LegacyTransitionError, match="does not conserve"):
        freeze_legacy_transition(
            root=fixture["coverage_root"],
            run_id=RUN_ID,
            classification=missing,
            frozen_at=FROZEN_AT,
        )


def test_transition_action_states_conserve_real_53_terminal_plus_56_formal_shape():
    from trading_os.research_assets.legacy_transition import (
        _validate_transition_action_state,
    )

    cases: list[tuple[str, dict[str, str], bool]] = []
    cases.extend(
        ("adoption", {"task_type": "quick_profile", "status": "completed"}, False)
        for _ in range(56)
    )
    cases.extend(
        ("adoption", {"task_type": "quick_profile", "status": "completed"}, True) for _ in range(8)
    )
    cases.extend(
        (
            "adoption",
            {"task_type": "targeted_followup", "status": "completed"},
            True,
        )
        for _ in range(2)
    )
    cases.extend(
        ("rescreen", {"task_type": "rapid_triage", "status": "completed"}, True) for _ in range(33)
    )
    cases.extend(
        ("defer_active", {"task_type": "quick_profile", "status": "pending"}, True)
        for _ in range(10)
    )

    for ordinal, (action, queue_record, is_terminal) in enumerate(cases, 1):
        _validate_transition_action_state(
            action=action,
            symbol=f"CN:{ordinal:06d}",
            queue_record=queue_record,
            is_legacy_terminal=is_terminal,
        )

    assert len(cases) == 109
    assert sum(is_terminal for _, _, is_terminal in cases) == 53
    assert sum(not is_terminal for _, _, is_terminal in cases) == 56


def test_transition_rejects_missing_formal_seal(tmp_path: Path):
    from trading_os.research_assets.legacy_transition import (
        LegacyTransitionError,
        freeze_legacy_transition,
    )

    fixture = _transition_fixture(tmp_path)
    evaluation_path = fixture["repository_root"] / fixture["direct_current"][2]
    evaluation_path.with_name(evaluation_path.name + ".seal.json").unlink()
    with pytest.raises(LegacyTransitionError, match="not validly sealed"):
        freeze_legacy_transition(
            root=fixture["coverage_root"],
            run_id=RUN_ID,
            classification=fixture["classification"],
            frozen_at=FROZEN_AT,
        )


def test_transition_status_rejects_tampered_legacy_bridge_report(tmp_path: Path):
    from trading_os.research_assets.legacy_transition import (
        LegacyTransitionError,
        freeze_legacy_transition,
        legacy_transition_status,
    )

    fixture = _transition_fixture(tmp_path)
    freeze_legacy_transition(
        root=fixture["coverage_root"],
        run_id=RUN_ID,
        classification=fixture["classification"],
        frozen_at=FROZEN_AT,
    )
    fixture["bridge_report_path"].write_text(
        "# Tampered legacy deep report\n",
        encoding="utf-8",
    )
    with pytest.raises(LegacyTransitionError, match="legacy bridge report binding"):
        legacy_transition_status(
            root=fixture["coverage_root"],
            run_id=RUN_ID,
        )


def test_transition_send_to_analyst_only_materializes_a_budget_candidate(
    tmp_path: Path,
):
    from trading_os.research_assets.coverage_store import read_jsonl
    from trading_os.research_assets.legacy_transition import (
        freeze_legacy_transition,
        record_legacy_transition,
    )

    fixture = _transition_fixture(tmp_path)
    root = fixture["coverage_root"]
    freeze_legacy_transition(
        root=root,
        run_id=RUN_ID,
        classification=fixture["classification"],
        frozen_at=FROZEN_AT,
    )
    submission = _submission(fixture["symbols"])
    direct_decision = next(
        item for item in submission["decisions"] if item["symbol"] == fixture["symbols"]["direct"]
    )
    direct_decision.update(
        {
            "route": "send_to_analyst",
            "revisit_triggers": [],
        }
    )
    bridge_decision = next(
        item for item in submission["decisions"] if item["symbol"] == fixture["symbols"]["bridge"]
    )
    bridge_decision.update(
        {
            "route": "watch",
            "revisit_triggers": [
                {
                    "type": "filing",
                    "condition": {"description": "next filing"},
                    "reason": "Refresh the bridged thesis.",
                }
            ],
        }
    )
    record_legacy_transition(
        root=root,
        run_id=RUN_ID,
        submission=submission,
        recorded_at=RECORDED_AT,
    )
    queue = {item["symbol"]: item for item in read_jsonl(root / "research_queue.jsonl")}
    direct = queue[fixture["symbols"]["direct"]]
    assert direct["task_type"] == "quick_profile"
    assert direct["status"] == "completed"
    assert "effort_budget_hours" not in direct
    assert "preceding_stage" not in direct
    assert direct["research_stage_high_watermark"] == "scoped_research"
    assert direct["result_path"] == fixture["direct_current"][2]
    assert direct["evidence_ids"] == [f"transition:formal:{fixture['symbols']['direct']}"]
    assert "Await explicit manager approval" in direct["next_action"]
    direct_meta_path = (
        fixture["repository_root"] / "research" / "companies" / "CN" / "000001" / "meta.json"
    )
    direct_meta = json.loads(direct_meta_path.read_text(encoding="utf-8"))
    assert direct_meta["research"]["coverage_status"] == "covered"
    assert direct_meta["research"]["rebaseline_required"] is False
    screening = {item["symbol"]: item for item in read_jsonl(root / "screening.jsonl")}
    assert screening[fixture["symbols"]["direct"]]["decision"] == ("profile_candidate")
    assert (
        "Await explicit manager approval" in screening[fixture["symbols"]["direct"]]["next_action"]
    )


def test_transition_rejects_queue_race_before_sealing_result(tmp_path: Path):
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.legacy_transition import (
        LegacyTransitionError,
        freeze_legacy_transition,
        record_legacy_transition,
    )

    fixture = _transition_fixture(tmp_path)
    root = fixture["coverage_root"]
    freeze_legacy_transition(
        root=root,
        run_id=RUN_ID,
        classification=fixture["classification"],
        frozen_at=FROZEN_AT,
    )
    rows = read_jsonl(root / "research_queue.jsonl")
    raced = [dict(item) for item in rows]
    for item in raced:
        if item["symbol"] == fixture["symbols"]["direct"]:
            item["reason"] = "changed after freeze"
    write_jsonl(root / "research_queue.jsonl", raced)

    with pytest.raises(LegacyTransitionError, match="queue changed"):
        record_legacy_transition(
            root=root,
            run_id=RUN_ID,
            submission=_submission(fixture["symbols"]),
            recorded_at=RECORDED_AT,
        )
    result_path = root / "manager-screen" / RUN_ID / "legacy-transition-001" / "result.json"
    assert not result_path.exists()

    write_jsonl(root / "research_queue.jsonl", rows)
    recorded = record_legacy_transition(
        root=root,
        run_id=RUN_ID,
        submission=_submission(fixture["symbols"]),
        recorded_at=RECORDED_AT,
    )
    assert recorded["adoption_count"] == 2


def test_transition_result_replay_repairs_partial_coverage_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from trading_os.research_assets import legacy_transition
    from trading_os.research_assets.coverage_store import read_jsonl
    from trading_os.research_assets.legacy_transition import (
        freeze_legacy_transition,
        record_legacy_transition,
    )
    from trading_os.research_assets.sealing import verify_sealed

    fixture = _transition_fixture(tmp_path)
    root = fixture["coverage_root"]
    freeze_legacy_transition(
        root=root,
        run_id=RUN_ID,
        classification=fixture["classification"],
        frozen_at=FROZEN_AT,
    )
    real_write = legacy_transition.write_jsonl
    calls = 0

    def fail_screening_write(path: Path, records: list[dict[str, Any]], sort_key="symbol"):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated screening write failure")
        return real_write(path, records, sort_key)

    monkeypatch.setattr(legacy_transition, "write_jsonl", fail_screening_write)
    with pytest.raises(OSError, match="simulated screening"):
        record_legacy_transition(
            root=root,
            run_id=RUN_ID,
            submission=_submission(fixture["symbols"]),
            recorded_at=RECORDED_AT,
        )
    result_path = root / "manager-screen" / RUN_ID / "legacy-transition-001" / "result.json"
    verify_sealed(result_path)
    assert read_jsonl(root / "screening.jsonl") == []

    monkeypatch.setattr(legacy_transition, "write_jsonl", real_write)
    repaired = record_legacy_transition(
        root=root,
        run_id=RUN_ID,
        submission=_submission(fixture["symbols"]),
        recorded_at=RECORDED_AT,
    )
    assert repaired["adoption_count"] == 2
    screening = {item["symbol"]: item for item in read_jsonl(root / "screening.jsonl")}
    assert screening[fixture["symbols"]["direct"]]["manager_screen_route"] == "watch"
    assert screening[fixture["symbols"]["bridge"]]["manager_screen_route"] == "send_to_analyst"


def test_transition_result_replay_repairs_company_meta_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from trading_os.research_assets import legacy_transition
    from trading_os.research_assets.legacy_transition import (
        freeze_legacy_transition,
        record_legacy_transition,
    )

    fixture = _transition_fixture(tmp_path)
    root = fixture["coverage_root"]
    freeze_legacy_transition(
        root=root,
        run_id=RUN_ID,
        classification=fixture["classification"],
        frozen_at=FROZEN_AT,
    )
    real_atomic_write = legacy_transition.atomic_write_bytes
    failed = False

    def fail_meta_once(path: Path, data: bytes):
        nonlocal failed
        if path.name == "meta.json" and not failed:
            failed = True
            raise OSError("simulated company meta write failure")
        return real_atomic_write(path, data)

    monkeypatch.setattr(legacy_transition, "atomic_write_bytes", fail_meta_once)
    with pytest.raises(OSError, match="simulated company meta"):
        record_legacy_transition(
            root=root,
            run_id=RUN_ID,
            submission=_submission(fixture["symbols"]),
            recorded_at=RECORDED_AT,
        )
    meta_path = (
        fixture["repository_root"] / "research" / "companies" / "CN" / "000001" / "meta.json"
    )
    before_repair = json.loads(meta_path.read_text(encoding="utf-8"))
    assert before_repair["research"]["rebaseline_required"] is True

    monkeypatch.setattr(legacy_transition, "atomic_write_bytes", real_atomic_write)
    record_legacy_transition(
        root=root,
        run_id=RUN_ID,
        submission=_submission(fixture["symbols"]),
        recorded_at=RECORDED_AT,
    )
    repaired = json.loads(meta_path.read_text(encoding="utf-8"))
    assert repaired["research"]["coverage_status"] == "covered"
    assert repaired["research"]["rebaseline_required"] is False
    assert repaired["reports"] == before_repair["reports"]


def test_transition_uses_shared_coverage_write_lock(tmp_path: Path):
    from trading_os.research_assets.coverage_store import (
        CoverageValidationError,
        coverage_write_lock,
    )
    from trading_os.research_assets.legacy_transition import freeze_legacy_transition

    fixture = _transition_fixture(tmp_path)
    with coverage_write_lock(fixture["coverage_root"]):
        with pytest.raises(CoverageValidationError, match="coverage state is busy"):
            freeze_legacy_transition(
                root=fixture["coverage_root"],
                run_id=RUN_ID,
                classification=fixture["classification"],
                frozen_at=FROZEN_AT,
            )
