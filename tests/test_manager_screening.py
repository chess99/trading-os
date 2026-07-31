from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import shutil
from pathlib import Path

import pytest

CUTOFF = dt.datetime.fromisoformat("2026-07-31T08:00:00+08:00")
RUN_ID = "2026-07-31-manager-screen-001"


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _quote_freshness(
    quote_as_of: dt.datetime = CUTOFF - dt.timedelta(days=1),
    *,
    max_age_seconds: int = 3 * 24 * 60 * 60,
) -> dict:
    return {
        "schema_version": 1,
        "status": "fresh",
        "quote_as_of": quote_as_of.isoformat(),
        "evaluated_at": CUTOFF.isoformat(),
        "age_seconds": (CUTOFF - quote_as_of).total_seconds(),
        "max_age_seconds": max_age_seconds,
        "future_tolerance_seconds": 300,
        "source": "fixture snapshot",
    }


def _manager_facts() -> dict:
    annuals = []
    for year, deducted_profit, operating_cash_flow in (
        (2023, 410_000_000, 530_000_000),
        (2024, 460_000_000, 590_000_000),
        (2025, 500_000_000, 620_000_000),
    ):
        annuals.append(
            {
                "report_date": f"{year}-12-31",
                "notice_date": f"{year + 1}-03-31",
                "report_type": "年报",
                "deducted_parent_net_profit_cny": deducted_profit,
                "operating_cash_flow_cny": operating_cash_flow,
                "audit_opinion": "标准无保留意见",
                "balance_sheet": {
                    "cash_cny": 1_200_000_000,
                    "interest_bearing_debt_cny": 300_000_000,
                    "total_assets_cny": 5_000_000_000,
                    "total_liabilities_cny": 2_000_000_000,
                    "parent_equity_cny": 2_500_000_000,
                },
            }
        )
    return {
        "quote_freshness": _quote_freshness(),
        "annuals": annuals,
        "latest_interim": {
            "report_date": "2026-06-30",
            "notice_date": "2026-07-30",
            "report_type": "中报",
            "deducted_parent_net_profit_cny": 280_000_000,
            "operating_cash_flow_cny": 310_000_000,
            "audit_opinion": None,
            "balance_sheet": {
                "cash_cny": 1_300_000_000,
                "interest_bearing_debt_cny": 320_000_000,
                "total_assets_cny": 5_200_000_000,
                "total_liabilities_cny": 2_100_000_000,
                "parent_equity_cny": 2_600_000_000,
            },
        },
        "business": {},
        "data_gaps": [],
    }


def _policy(path: Path, *, decision_contract_version: int = 1) -> Path:
    payload = {
        "schema_version": 2,
        "policy_id": "manager-screening.test",
        "version": "1.0.0",
        "effective_at": CUTOFF.isoformat(),
        "kind": "manager_screening",
        "payload": {
            "default_batch_size": 2,
            "minimum_batch_size": 1,
            "maximum_batch_size": 3,
            "fact_snapshot_required": False,
            "minimum_annual_periods": 3,
            "routes": ["pass", "watch", "send_to_analyst"],
            "send_to_analyst_capacity_per_run": 2,
            "quick_profile_effort_budget_hours": 1.5,
            "quick_profile_stop_conditions": [
                "无法建立普通股股东现金路径",
                "正常化收益不支持继续研究",
            ],
            "pass_and_watch_require_revisit_trigger": True,
            "one_line_reason_max_chars": 240,
            "decisive_question_max_chars": 600,
            "quality": {
                "programmatic_validation_rate": 1.0,
                "material_error_types": [
                    "security_identity_error",
                    "verifiable_factual_error",
                    "material_risk_omission",
                    "decision_contract_violation",
                ],
                "route_disagreement_is_material_error": False,
                "calibration_sample_rate": 0.05,
                "calibration_minimum_per_batch": 1,
            },
            "recursive_correction": "forbidden",
            "principles": {
                "same_manager_per_batch": True,
            },
        },
    }
    if decision_contract_version in {2, 3}:
        payload["version"] = f"{decision_contract_version}.0.0"
        payload["payload"].update(
            {
                "decision_contract_version": decision_contract_version,
                "mandatory_risk_acknowledgement": True,
                "canonical_fact_line_required": True,
                "high_liability_to_assets_pct": 90.0,
            }
        )
        if decision_contract_version == 3:
            payload["payload"].update(
                {
                    "routes": ["pass", "watch", "research_candidate"],
                    "research_candidate_requires_allocation": True,
                }
            )
    elif decision_contract_version != 1:
        raise ValueError("unsupported decision contract fixture")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def _root(tmp_path: Path) -> tuple[Path, Path]:
    from trading_os.research_assets.scope_workflow import freeze_all_a_scope

    root = tmp_path / "coverage" / "cn-a"
    companies = []
    screening = []
    for ticker, name, industry, pe in (
        ("000001", "甲公司", "银行", 5.0),
        ("000002", "乙公司", "制造", 12.0),
        ("000003", "丙公司", "消费", 20.0),
        ("000004", "丁公司", "资源", 8.0),
    ):
        symbol = f"CN:{ticker}"
        manager_facts = _manager_facts()
        if ticker == "000001":
            manager_facts["annuals"][-1]["balance_sheet"].update(
                {
                    "cash_cny": 100_000_000,
                    "interest_bearing_debt_cny": 1_500_000_000,
                    "total_assets_cny": 5_000_000_000,
                    "total_liabilities_cny": 4_600_000_000,
                    "parent_equity_cny": 200_000_000,
                }
            )
            manager_facts["latest_interim"]["balance_sheet"].update(
                {
                    "cash_cny": 80_000_000,
                    "interest_bearing_debt_cny": 1_600_000_000,
                    "total_assets_cny": 5_100_000_000,
                    "total_liabilities_cny": 4_700_000_000,
                    "parent_equity_cny": 180_000_000,
                }
            )
        companies.append(
            {
                "symbol": symbol,
                "ticker": ticker,
                "name": name,
                "market": "CN",
                "exchange": "SZSE",
                "security_type": "common_stock",
                "listing_status": "listed",
                "as_of": "2026-07-30",
                "industry": industry,
                "price": 10.0,
                "market_cap_cny": 10_000_000_000,
                "pe_ttm": pe,
                "pb": 1.0,
                "roe": 10.0,
                "source": "fixture snapshot",
                "fetched_at": CUTOFF.isoformat(),
                "manager_screen_facts": manager_facts,
            }
        )
        screening.append(
            {
                "symbol": symbol,
                "name": name,
                "decision": "catalog",
                "priority": None,
                "reason": "旧目录记录。",
                "evidence": ["fixture"],
                "next_action": "等待新机制初筛。",
            }
        )
    _write_jsonl(root / "companies.jsonl", companies)
    _write_jsonl(root / "screening.jsonl", screening)
    _write_jsonl(root / "research_queue.jsonl", [])
    _write_jsonl(root / "runs.jsonl", [])
    policy_path = _policy(tmp_path / "policies" / "manager-screening.json")
    freeze_all_a_scope(
        root=root,
        run_id=RUN_ID,
        scope_cutoff=CUTOFF,
        frozen_at=CUTOFF,
    )
    return root, policy_path


def _recorded_transition_root(tmp_path: Path) -> tuple[dict, Path]:
    from tests.test_legacy_transition import (
        RECORDED_AT,
        _transition_fixture,
    )
    from tests.test_legacy_transition import (
        RUN_ID as TRANSITION_RUN_ID,
    )
    from tests.test_legacy_transition import (
        _submission as transition_submission,
    )
    from trading_os.research_assets.legacy_transition import (
        freeze_legacy_transition,
        record_legacy_transition,
    )
    from trading_os.research_assets.sealing import seal_json

    fixture = _transition_fixture(tmp_path)
    repository = Path(fixture["repository_root"])
    root = Path(fixture["coverage_root"])
    scope_dir = root / "scopes" / TRANSITION_RUN_ID
    manifest_path = scope_dir / "manifest.json"
    intake_path = scope_dir / "baseline-intake.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    intake = json.loads(intake_path.read_text(encoding="utf-8"))

    companies = []
    for ordinal, member in enumerate(manifest["members"], 1):
        member["ordinal"] = ordinal
        symbol = member["symbol"]
        ticker = symbol.split(":", 1)[1]
        companies.append(
            {
                "symbol": symbol,
                "ticker": ticker,
                "name": member["name"],
                "market": "CN",
                "exchange": "SZSE",
                "security_type": "common_stock",
                "listing_status": "listed",
                "as_of": "2026-07-31",
                "source": "transition integration fixture",
                "fetched_at": CUTOFF.isoformat(),
                "manager_screen_facts": {
                    "quote_freshness": _quote_freshness(),
                },
            }
        )
    snapshot_path = root / "snapshots" / TRANSITION_RUN_ID / "companies.jsonl"
    _write_jsonl(snapshot_path, companies)
    manifest["universe_source"] = {
        "path": snapshot_path.relative_to(repository).as_posix(),
        "sha256": hashlib.sha256(snapshot_path.read_bytes()).hexdigest(),
    }
    manifest["market"] = "CN"
    for member in intake["members"]:
        member["ordinal"] = next(
            item["ordinal"] for item in manifest["members"] if item["symbol"] == member["symbol"]
        )

    for path in (
        manifest_path,
        manifest_path.with_name(manifest_path.name + ".seal.json"),
        intake_path,
        intake_path.with_name(intake_path.name + ".seal.json"),
    ):
        path.unlink()
    manifest_seal = seal_json(
        manifest_path,
        manifest,
        artifact_type="all_a_scope_manifest",
        sealed_at=CUTOFF,
    )
    intake["scope_manifest_sha256"] = manifest_seal.sha256
    seal_json(
        intake_path,
        intake,
        artifact_type="all_a_baseline_intake",
        sealed_at=CUTOFF,
    )
    policy_path = _policy(repository / "policies" / "manager-screening.json")
    freeze_legacy_transition(
        root=root,
        run_id=TRANSITION_RUN_ID,
        classification=fixture["classification"],
        frozen_at=CUTOFF + dt.timedelta(minutes=1),
    )
    record_legacy_transition(
        root=root,
        run_id=TRANSITION_RUN_ID,
        submission=transition_submission(fixture["symbols"]),
        recorded_at=RECORDED_AT,
    )
    return fixture, policy_path


def _submission(symbols: list[str]) -> dict:
    decisions = []
    for index, symbol in enumerate(symbols):
        route = "pass" if index == 0 else "send_to_analyst"
        decisions.append(
            {
                "symbol": symbol,
                "route": route,
                "one_line_reason": (
                    "现有快照没有显示继续购买研究时间的高价值。"
                    if route == "pass"
                    else "下一小时核验现金转换很可能改变判断。"
                ),
                "decisive_question": "正常化所有者收益能否持续覆盖当前估值？",
                "revisit_triggers": (
                    [
                        {
                            "type": "filing",
                            "condition": "下一份半年报披露",
                            "reason": "重新核验盈利和现金转换。",
                        }
                    ]
                    if route == "pass"
                    else []
                ),
                "confidence": "medium",
                "evidence_ids": [f"snapshot:{symbol}"],
            }
        )
    return {
        "schema_version": 1,
        "manager": {
            "agent": "/root",
            "model": "gpt-test",
            "tools": ["packet_read"],
        },
        "additional_evidence": [],
        "decisions": decisions,
    }


def _send_submission(symbols: list[str]) -> dict:
    submission = _submission(symbols)
    for decision in submission["decisions"]:
        decision["route"] = "send_to_analyst"
        decision["one_line_reason"] = "下一小时核验现金转换很可能改变判断。"
        decision["revisit_triggers"] = []
    return submission


def _v2_submission(packet: dict) -> dict:
    submission = _submission([row["symbol"] for row in packet["dossiers"]])
    dossier_by_symbol = {row["symbol"]: row for row in packet["dossiers"]}
    for decision in submission["decisions"]:
        support = dossier_by_symbol[decision["symbol"]]["market_snapshot"]["manager_screen_facts"][
            "decision_support"
        ]
        acknowledgements = []
        material_reasons = []
        for flag in support["mandatory_risk_flags"]:
            reason = f"{flag['category']}风险会影响普通股剩余索取权"
            acknowledgements.append(
                {
                    "flag_id": flag["flag_id"],
                    "assessment": "material",
                    "reason": reason,
                }
            )
            material_reasons.append(reason)
        decision["one_line_reason"] = (
            support["canonical_fact_line"]["text"]
            + "；"
            + (
                "；".join(material_reasons)
                if material_reasons
                else "现有证据下继续投入研究时间的边际价值有限"
            )
        )
        decision["risk_acknowledgements"] = acknowledgements
        decision["evidence_ids"] = list(
            dict.fromkeys(
                [
                    *decision["evidence_ids"],
                    *(
                        evidence_id
                        for flag in support["mandatory_risk_flags"]
                        for evidence_id in flag["evidence_ids"]
                    ),
                ]
            )
        )
    return submission


def _v3_submission(packet: dict, *, all_candidates: bool = False) -> dict:
    submission = _v2_submission(packet)
    for decision in submission["decisions"]:
        if all_candidates or decision["route"] == "send_to_analyst":
            decision["route"] = "research_candidate"
            decision["revisit_triggers"] = []
    return submission


def _calibration_submission(
    packet: dict,
    *,
    material_error: bool = False,
    route_disagreement: bool = True,
) -> dict:
    reviews = []
    for index, sample in enumerate(packet["samples"]):
        symbol = sample["symbol"]
        evidence_id = sample["evidence_ids"][0]
        has_disagreement = route_disagreement and index == 0
        has_error = material_error and index == 0
        reviews.append(
            {
                "symbol": symbol,
                "material_errors": (
                    [
                        {
                            "type": "verifiable_factual_error",
                            "finding": "封存快照中的可核验事实与一手证据不一致。",
                            "evidence_ids": [evidence_id],
                        }
                    ]
                    if has_error
                    else []
                ),
                "route_disagreement": {
                    "present": has_disagreement,
                    "finding": (
                        "Reviewer 对研究预算路由有不同看法，但不把观点差异算作错误。"
                        if has_disagreement
                        else None
                    ),
                    "evidence_ids": [evidence_id] if has_disagreement else [],
                },
                "adjudication": {
                    "performed": has_error,
                    "outcome": ("material_error_confirmed" if has_error else "not_needed"),
                    "finding": ("一次性裁决已完成，不启动 correction 链。" if has_error else None),
                    "evidence_ids": [evidence_id] if has_error else [],
                },
            }
        )
    return {
        "schema_version": 1,
        "reviewer": {
            "agent": "/independent/calibration-reviewer",
            "model": "gpt-review",
            "tools": ["packet_read", "source_check"],
        },
        "additional_evidence": [],
        "reviews": reviews,
    }


def test_manager_freeze_uses_stable_scope_order_and_only_four_files(tmp_path: Path):
    from trading_os.research_assets.manager_screening import (
        freeze_manager_screen_batch,
    )
    from trading_os.research_assets.sealing import verify_sealed

    root, policy_path = _root(tmp_path)
    frozen = freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        frozen_at=CUTOFF + dt.timedelta(minutes=1),
        policy_path=policy_path,
    )
    batch_dir = tmp_path / "coverage" / "cn-a" / "manager-screen" / RUN_ID / "batch-001"
    assert sorted(path.name for path in batch_dir.iterdir()) == [
        "batch.json",
        "batch.json.seal.json",
        "packet.json",
        "packet.json.seal.json",
    ]
    leftover_journal = batch_dir / "freeze-journal.json"
    leftover_journal.write_text("cleanup interrupted", encoding="utf-8")
    replayed = freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        frozen_at=CUTOFF + dt.timedelta(minutes=4),
        policy_path=policy_path,
    )
    assert replayed["packet_sha256"] == frozen["packet_sha256"]
    assert not leftover_journal.exists()
    batch = json.loads((batch_dir / "batch.json").read_text(encoding="utf-8"))
    packet = json.loads((batch_dir / "packet.json").read_text(encoding="utf-8"))
    assert [item["symbol"] for item in batch["members"]] == [
        "CN:000001",
        "CN:000002",
    ]
    assert [item["symbol"] for item in packet["dossiers"]] == [
        "CN:000001",
        "CN:000002",
    ]
    assert packet["dossiers"][0]["market_snapshot"]["pe_ttm"] == 5.0
    assert verify_sealed(batch_dir / "batch.json").sha256 == frozen["batch_sha256"]
    assert (
        freeze_manager_screen_batch(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-001",
            frozen_at=CUTOFF + dt.timedelta(hours=1),
            policy_path=policy_path,
        )["packet_sha256"]
        == frozen["packet_sha256"]
    )


def test_decision_v2_binds_canonical_facts_and_requires_risk_acknowledgement(
    tmp_path: Path,
):
    from trading_os.research_assets.manager_screening import (
        ManagerScreeningError,
        freeze_manager_screen_batch,
        prepare_manager_screen_calibration,
        record_manager_screen_decisions,
    )

    root, policy_path = _root(tmp_path)
    _policy(policy_path, decision_contract_version=2)
    freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        frozen_at=CUTOFF + dt.timedelta(minutes=1),
        policy_path=policy_path,
    )
    batch_dir = root / "manager-screen" / RUN_ID / "batch-001"
    packet = json.loads((batch_dir / "packet.json").read_text(encoding="utf-8"))
    first_support = packet["dossiers"][0]["market_snapshot"]["manager_screen_facts"][
        "decision_support"
    ]
    assert "中报" in first_support["canonical_fact_line"]["text"]
    assert "一季报" not in first_support["canonical_fact_line"]["text"]
    assert [flag["category"] for flag in first_support["mandatory_risk_flags"]] == [
        "capital_structure"
    ]

    submission = _v2_submission(packet)
    missing_ack = copy.deepcopy(submission)
    missing_ack["decisions"][0]["risk_acknowledgements"] = []
    with pytest.raises(
        ManagerScreeningError,
        match="risk acknowledgement",
    ):
        record_manager_screen_decisions(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-001",
            submission=missing_ack,
            recorded_at=CUTOFF + dt.timedelta(minutes=2),
        )

    tampered_fact = copy.deepcopy(submission)
    tampered_fact["decisions"][0]["one_line_reason"] = tampered_fact["decisions"][0][
        "one_line_reason"
    ].replace("中报", "一季报", 1)
    with pytest.raises(ManagerScreeningError, match="canonical fact line"):
        record_manager_screen_decisions(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-001",
            submission=tampered_fact,
            recorded_at=CUTOFF + dt.timedelta(minutes=2),
        )

    recorded = record_manager_screen_decisions(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        submission=submission,
        recorded_at=CUTOFF + dt.timedelta(minutes=2),
    )
    assert recorded["by_route"] == {
        "pass": 1,
        "send_to_analyst": 1,
    }
    calibration = prepare_manager_screen_calibration(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        calibration_id="calibration-v2",
        prepared_at=CUTOFF + dt.timedelta(minutes=3),
        policy_path=policy_path,
    )
    assert calibration["planned_sample_count"] == 1

    changed_ack = copy.deepcopy(submission)
    changed_ack["decisions"][0]["risk_acknowledgements"][0]["assessment"] = "not_material"
    with pytest.raises(ManagerScreeningError):
        record_manager_screen_decisions(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-001",
            submission=changed_ack,
            recorded_at=CUTOFF + dt.timedelta(minutes=4),
        )


def test_decision_v3_records_unfunded_candidates_without_buying_profile_budget(
    tmp_path: Path,
):
    from trading_os.research_assets.coverage_store import read_jsonl
    from trading_os.research_assets.manager_screening import (
        ManagerScreeningError,
        freeze_manager_screen_batch,
        manager_screen_status,
        record_manager_screen_decisions,
        verify_manager_screen_terminal,
    )

    root, policy_path = _root(tmp_path)
    _policy(policy_path, decision_contract_version=3)
    freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        frozen_at=CUTOFF + dt.timedelta(minutes=1),
        policy_path=policy_path,
    )
    batch_dir = root / "manager-screen" / RUN_ID / "batch-001"
    packet = json.loads((batch_dir / "packet.json").read_text(encoding="utf-8"))
    assert set(packet["instructions"]["routes"]) == {
        "pass",
        "watch",
        "research_candidate",
    }
    assert packet["instructions"]["decision_contract"]["version"] == 3

    invalid = _v3_submission(packet)
    invalid["decisions"][1]["route"] = "send_to_analyst"
    with pytest.raises(ManagerScreeningError, match="invalid manager-screen route"):
        record_manager_screen_decisions(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-001",
            submission=invalid,
            recorded_at=CUTOFF + dt.timedelta(minutes=2),
        )

    recorded = record_manager_screen_decisions(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        submission=_v3_submission(packet),
        recorded_at=CUTOFF + dt.timedelta(minutes=2),
    )
    assert recorded["by_route"] == {"pass": 1, "research_candidate": 1}
    queue = {row["symbol"]: row for row in read_jsonl(root / "research_queue.jsonl")}
    candidate = queue["CN:000002"]
    assert candidate["task_type"] == "manager_screen"
    assert candidate["status"] == "completed"
    assert candidate["manager_screen_route"] == "research_candidate"
    assert candidate["research_budget_state"] == "candidate_unfunded"
    assert "effort_budget_hours" not in candidate
    assert not any(row.get("task_type") == "quick_profile" for row in queue.values())
    screening = {row["symbol"]: row for row in read_jsonl(root / "screening.jsonl")}
    assert screening["CN:000002"]["decision"] == "candidate_unfunded"
    assert screening["CN:000002"]["research_budget_state"] == "candidate_unfunded"
    assert verify_manager_screen_terminal(
        root=root,
        queued=candidate,
        symbol="CN:000002",
        scope_cutoff=CUTOFF + dt.timedelta(minutes=3),
    ) == (recorded["result_path"], recorded["result_sha256"])
    status = manager_screen_status(root=root, run_id=RUN_ID)
    assert status["analyst_budget"]["purchased_company_count"] == 0
    assert status["analyst_budget"]["current_backlog_company_count"] == 0


def test_decision_v3_cannot_bypass_migration_contract_on_the_v2_policy_path(
    tmp_path: Path,
):
    from trading_os.research_assets.manager_screening import (
        ManagerScreeningError,
        freeze_manager_screen_batch,
        record_manager_screen_decisions,
    )

    root, policy_path = _root(tmp_path)
    _policy(policy_path, decision_contract_version=2)
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    policy["payload"]["send_to_analyst_capacity_per_run"] = 1
    policy_path.write_text(
        json.dumps(policy, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        batch_size=1,
        frozen_at=CUTOFF + dt.timedelta(minutes=1),
        policy_path=policy_path,
    )
    packet1 = json.loads(
        (root / "manager-screen" / RUN_ID / "batch-001" / "packet.json").read_text(encoding="utf-8")
    )
    first = _v2_submission(packet1)
    first["decisions"][0]["route"] = "send_to_analyst"
    first["decisions"][0]["revisit_triggers"] = []
    record_manager_screen_decisions(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        submission=first,
        recorded_at=CUTOFF + dt.timedelta(minutes=2),
    )

    _policy(policy_path, decision_contract_version=3)
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    policy["payload"]["send_to_analyst_capacity_per_run"] = 1
    policy_path.write_text(
        json.dumps(policy, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ManagerScreeningError, match="sealed allocation contract"):
        freeze_manager_screen_batch(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-002",
            batch_size=2,
            frozen_at=CUTOFF + dt.timedelta(minutes=3),
            policy_path=policy_path,
        )
    assert not (root / "manager-screen" / RUN_ID / "batch-002").exists()


def test_manager_freeze_replays_batch_packet_crash_from_sealed_journal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    import trading_os.research_assets.manager_screening as manager_screening
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.sealing import verify_sealed

    root, policy_path = _root(tmp_path)
    real_seal_json = manager_screening.seal_json
    failed = False

    def fail_before_packet(path, payload, *, artifact_type, sealed_at):
        nonlocal failed
        if artifact_type == "manager_screen_packet" and not failed:
            failed = True
            raise RuntimeError("simulated batch-packet crash")
        return real_seal_json(
            path,
            payload,
            artifact_type=artifact_type,
            sealed_at=sealed_at,
        )

    monkeypatch.setattr(manager_screening, "seal_json", fail_before_packet)
    with pytest.raises(RuntimeError, match="batch-packet crash"):
        manager_screening.freeze_manager_screen_batch(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-001",
            frozen_at=CUTOFF + dt.timedelta(minutes=1),
            policy_path=policy_path,
        )

    batch_dir = root / "manager-screen" / RUN_ID / "batch-001"
    verify_sealed(batch_dir / "freeze-journal.json")
    verify_sealed(batch_dir / "batch.json")
    assert not (batch_dir / "packet.json.seal.json").exists()

    queue_path = root / "research_queue.jsonl"
    queue = read_jsonl(queue_path)
    queue[0]["reason"] = "mutable state changed after crash"
    write_jsonl(queue_path, queue)

    manager_screening.freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-002",
        frozen_at=CUTOFF + dt.timedelta(minutes=2),
        policy_path=policy_path,
    )
    second_batch = json.loads(
        (root / "manager-screen" / RUN_ID / "batch-002" / "batch.json").read_text(encoding="utf-8")
    )
    assert [row["symbol"] for row in second_batch["members"]] == [
        "CN:000003",
        "CN:000004",
    ]

    monkeypatch.setattr(manager_screening, "seal_json", real_seal_json)
    repaired = manager_screening.freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        frozen_at=CUTOFF + dt.timedelta(minutes=3),
        policy_path=policy_path,
    )
    packet = json.loads((batch_dir / "packet.json").read_text(encoding="utf-8"))
    assert packet["dossiers"][0]["prior_queue"]["reason"] != ("mutable state changed after crash")
    assert verify_sealed(batch_dir / "batch.json").sha256 == repaired["batch_sha256"]
    assert verify_sealed(batch_dir / "packet.json").sha256 == repaired["packet_sha256"]
    assert sorted(path.name for path in batch_dir.iterdir()) == [
        "batch.json",
        "batch.json.seal.json",
        "packet.json",
        "packet.json.seal.json",
    ]


def test_manager_freeze_rejects_company_snapshot_changed_after_scope(tmp_path: Path):
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.manager_screening import (
        ManagerScreeningError,
        freeze_manager_screen_batch,
    )

    root, policy_path = _root(tmp_path)
    companies_path = root / "companies.jsonl"
    companies = read_jsonl(companies_path)
    companies[0]["price"] = 10.5
    write_jsonl(companies_path, companies)

    with pytest.raises(ManagerScreeningError, match="changed after scope freeze"):
        freeze_manager_screen_batch(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-001",
            frozen_at=CUTOFF + dt.timedelta(minutes=1),
            policy_path=policy_path,
        )


def test_manager_freeze_reads_the_scope_bound_custom_company_snapshot(
    tmp_path: Path,
):
    from trading_os.research_assets.coverage_store import read_jsonl
    from trading_os.research_assets.manager_screening import (
        freeze_manager_screen_batch,
    )
    from trading_os.research_assets.scope_workflow import freeze_all_a_scope

    root, policy_path = _root(tmp_path)
    run_id = "2026-07-31-manager-screen-custom"
    custom_path = root / "snapshots" / run_id / "companies.jsonl"
    companies = read_jsonl(root / "companies.jsonl")
    for company in companies:
        company["manager_screen_facts"] = {
            "schema_version": 1,
            "quote_freshness": _quote_freshness(),
            "business": {"main_business": "封存主营业务摘要。"},
            "annuals": [],
            "latest_interim": None,
            "data_gaps": ["three_year_annual_history_incomplete"],
        }
    _write_jsonl(custom_path, companies)
    freeze_all_a_scope(
        root=root,
        run_id=run_id,
        scope_cutoff=CUTOFF,
        frozen_at=CUTOFF,
        universe_path=custom_path,
    )

    freeze_manager_screen_batch(
        root=root,
        run_id=run_id,
        batch_id="batch-001",
        frozen_at=CUTOFF + dt.timedelta(minutes=1),
        policy_path=policy_path,
    )
    packet_path = root / "manager-screen" / run_id / "batch-001" / "packet.json"
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    assert (
        packet["dossiers"][0]["market_snapshot"]["manager_screen_facts"]["business"][
            "main_business"
        ]
        == "封存主营业务摘要。"
    )
    assert (
        packet["dossiers"][0]["evidence_catalog"][0]["path"]
        == f"coverage/cn-a/snapshots/{run_id}/companies.jsonl"
    )


def test_manager_freeze_does_not_trust_unverified_completed_queue_state(
    tmp_path: Path,
):
    from trading_os.research_assets.manager_screening import (
        freeze_manager_screen_batch,
    )

    root, policy_path = _root(tmp_path)
    _write_jsonl(
        root / "research_queue.jsonl",
        [
            {
                "symbol": "CN:000001",
                "name": "甲公司",
                "task_type": "rapid_triage",
                "status": "completed",
                "result_path": "missing/package.json",
                "triage_disposition": "catalog",
            },
            {
                "symbol": "CN:000002",
                "name": "乙公司",
                "task_type": "manager_screen",
                "status": "completed",
                "result_path": "missing/result.json",
                "manager_screen_result_path": "missing/result.json",
                "manager_screen_result_sha256": "0" * 64,
                "manager_screen_route": "pass",
                "manager_screen_run_id": RUN_ID,
                "manager_screen_batch_id": "missing",
            },
        ],
    )

    freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        frozen_at=CUTOFF + dt.timedelta(minutes=1),
        policy_path=policy_path,
    )
    batch_path = root / "manager-screen" / RUN_ID / "batch-001" / "batch.json"
    batch = json.loads(batch_path.read_text(encoding="utf-8"))
    assert [item["symbol"] for item in batch["members"]] == [
        "CN:000001",
        "CN:000002",
    ]


def test_record_routes_only_selected_companies_to_analyst_and_status(tmp_path: Path):
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.manager_screening import (
        freeze_manager_screen_batch,
        manager_screen_status,
        record_manager_screen_decisions,
    )

    root, policy_path = _root(tmp_path)
    freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        frozen_at=CUTOFF + dt.timedelta(minutes=1),
        policy_path=policy_path,
    )
    queue_path = root / "research_queue.jsonl"
    queue_before = read_jsonl(queue_path)
    candidate = next(item for item in queue_before if item["symbol"] == "CN:000002")
    candidate.update(
        {
            "allocation_sha256": "a" * 64,
            "selected_by": ["legacy_lens"],
            "profile_cycle_id": "2026-07-28-legacy-cycle",
            "profile_evaluation_path": "legacy/evaluation.json",
            "profile_quick_selection_path": "legacy/selection.json",
            "triage_priority_score": 99,
        }
    )
    write_jsonl(queue_path, queue_before)
    recorded = record_manager_screen_decisions(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        submission=_submission(["CN:000001", "CN:000002"]),
        recorded_at=CUTOFF + dt.timedelta(minutes=2),
    )
    assert recorded["by_route"] == {"pass": 1, "send_to_analyst": 1}
    result_payload = json.loads(
        (root / "manager-screen" / RUN_ID / "batch-001" / "result.json").read_text(encoding="utf-8")
    )
    calibration_plan = result_payload["quality_state"]["calibration"]
    assert calibration_plan["status"] == "planned_non_blocking"
    assert calibration_plan["planned_sample_count"] == 1
    assert calibration_plan["reviewed_symbol_count"] == 0
    assert calibration_plan["route_disagreement_is_material_error"] is False
    queue = {item["symbol"]: item for item in read_jsonl(root / "research_queue.jsonl")}
    assert queue["CN:000001"]["task_type"] == "manager_screen"
    assert queue["CN:000001"]["status"] == "completed"
    assert queue["CN:000002"]["task_type"] == "quick_profile"
    assert queue["CN:000002"]["status"] == "pending"
    assert queue["CN:000002"]["effort_budget_hours"] == 1.5
    assert queue["CN:000002"]["preceding_stage"] == "manager_screen"
    for stale in (
        "allocation_sha256",
        "selected_by",
        "profile_cycle_id",
        "profile_evaluation_path",
        "profile_quick_selection_path",
        "triage_priority_score",
    ):
        assert stale not in queue["CN:000002"]
    screening = {item["symbol"]: item for item in read_jsonl(root / "screening.jsonl")}
    assert screening["CN:000001"]["decision"] == "catalog"
    assert screening["CN:000002"]["decision"] == "quick_profile"
    assert not list((tmp_path / "research").glob("companies/*/*/reports/*"))

    status = manager_screen_status(root=root, run_id=RUN_ID)
    assert status["completed_company_count"] == 2
    assert status["remaining_unbatched_count"] == 2
    assert status["by_route"] == {"pass": 1, "send_to_analyst": 1}
    assert status["completed_manager_wall_clock_seconds"] == 60.0
    assert status["batches"][0]["manager_wall_clock_seconds"] == 60.0
    assert status["analyst_budget"]["purchased_company_count"] == 1
    assert status["analyst_budget"]["purchased_effort_budget_hours"] == 1.5
    assert status["analyst_budget"]["current_backlog_company_count"] == 1
    assert status["analyst_budget"]["current_backlog_effort_budget_hours"] == 1.5
    assert status["analyst_budget"]["current_state"] == {"quick_profile:pending": 1}
    assert status["analyst_budget"]["machine_route_decision"] is False
    assert status["calibration"]["planned_sample_count"] == 1
    assert status["calibration"]["reviewed_sample_count"] == 0
    assert status["calibration"]["missing_sample_count"] == 1
    assert status["calibration"]["coverage_rate"] == 0.0
    assert status["calibration"]["status"] == "missing"

    second = freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-002",
        batch_size=2,
        frozen_at=CUTOFF + dt.timedelta(minutes=3),
        policy_path=policy_path,
    )
    batch = json.loads((tmp_path / second["batch_path"]).read_text(encoding="utf-8"))
    assert [item["symbol"] for item in batch["members"]] == [
        "CN:000003",
        "CN:000004",
    ]


def test_status_conserves_intake_members_deferred_at_scope_freeze(tmp_path: Path):
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.manager_screening import manager_screen_status
    from trading_os.research_assets.scope_workflow import freeze_all_a_scope

    root, _ = _root(tmp_path)
    queue = read_jsonl(root / "research_queue.jsonl")
    queued = next(item for item in queue if item["symbol"] == "CN:000001")
    queued["task_type"] = "quick_profile"
    queued["status"] = "pending"
    queued["reason"] = "existing analyst work"
    write_jsonl(root / "research_queue.jsonl", queue)
    run_id = "2026-08-01-manager-screen-deferred"
    freeze_all_a_scope(
        root=root,
        run_id=run_id,
        scope_cutoff=CUTOFF + dt.timedelta(days=1),
        frozen_at=CUTOFF + dt.timedelta(days=1),
    )

    status = manager_screen_status(root=root, run_id=run_id)

    assert status["screenable_intake_count"] == 4
    assert status["remaining_unbatched_count"] == 3
    assert status["deferred_current_state_count"] == 1
    assert status["deferred_current_state"] == {"defer_active_or_deeper_stage": 1}
    assert status["screenable_conservation_satisfied"] is True


def test_recorded_transition_releases_join_scope_order_and_status_conservation(
    tmp_path: Path,
) -> None:
    from tests.test_legacy_transition import (
        RECORDED_AT,
    )
    from tests.test_legacy_transition import (
        RUN_ID as TRANSITION_RUN_ID,
    )
    from trading_os.research_assets.manager_screening import (
        freeze_manager_screen_batch,
        manager_screen_status,
    )

    fixture, policy_path = _recorded_transition_root(tmp_path)
    root = Path(fixture["coverage_root"])
    status = manager_screen_status(root=root, run_id=TRANSITION_RUN_ID)

    assert status["baseline_intake_count"] == 2
    assert status["screenable_intake_count"] == 3
    assert status["legacy_transition"]["state"] == "recorded"
    assert status["legacy_transition"]["release_count"] == 1
    assert status["remaining_unbatched_count"] == 1
    assert status["deferred_current_state"] == {"legacy_transition_adoption": 2}
    assert status["screenable_conservation_satisfied"] is True

    frozen = freeze_manager_screen_batch(
        root=root,
        run_id=TRANSITION_RUN_ID,
        batch_id="batch-001",
        frozen_at=RECORDED_AT + dt.timedelta(minutes=1),
        batch_size=1,
        policy_path=policy_path,
    )
    batch = json.loads(
        (Path(fixture["repository_root"]) / frozen["batch_path"]).read_text(encoding="utf-8")
    )
    assert batch["members"] == [
        {
            "batch_ordinal": 1,
            "scope_ordinal": 3,
            "symbol": fixture["symbols"]["rescreen"],
            "name": "Company 000003",
            "prior_task_type": "manager_screen",
            "prior_status": "pending",
        }
    ]
    completed = manager_screen_status(
        root=root,
        run_id=TRANSITION_RUN_ID,
    )
    assert completed["batched_company_count"] == 1
    assert completed["remaining_unbatched_count"] == 0
    assert completed["deferred_current_state_count"] == 2
    assert completed["screenable_conservation_satisfied"] is True


def test_capacity_fails_closed_when_legacy_adoption_route_is_tampered(
    tmp_path: Path,
) -> None:
    from tests.test_legacy_transition import RECORDED_AT
    from tests.test_legacy_transition import RUN_ID as TRANSITION_RUN_ID
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.manager_screening import (
        ManagerScreeningError,
        freeze_manager_screen_batch,
        record_manager_screen_decisions,
    )

    fixture, policy_path = _recorded_transition_root(tmp_path)
    root = Path(fixture["coverage_root"])
    frozen = freeze_manager_screen_batch(
        root=root,
        run_id=TRANSITION_RUN_ID,
        batch_id="batch-001",
        frozen_at=RECORDED_AT + dt.timedelta(minutes=1),
        batch_size=1,
        policy_path=policy_path,
    )
    packet = json.loads(
        (Path(fixture["repository_root"]) / frozen["packet_path"]).read_text(encoding="utf-8")
    )
    queue_path = root / "research_queue.jsonl"
    queue = read_jsonl(queue_path)
    legacy_send = next(
        item
        for item in queue
        if item.get("legacy_transition_action") == "adoption"
        and item.get("manager_screen_route") == "send_to_analyst"
    )
    legacy_send["manager_screen_route"] = "pass"
    write_jsonl(queue_path, queue)
    queue_before = queue_path.read_bytes()
    result_path = root / "manager-screen" / TRANSITION_RUN_ID / "batch-001" / "result.json"

    with pytest.raises(
        ManagerScreeningError,
        match="does not match the sealed legacy adoption",
    ):
        record_manager_screen_decisions(
            root=root,
            run_id=TRANSITION_RUN_ID,
            batch_id="batch-001",
            submission=_send_submission([packet["dossiers"][0]["symbol"]]),
            recorded_at=RECORDED_AT + dt.timedelta(minutes=2),
        )
    assert not result_path.exists()
    assert not result_path.with_name("result.json.seal.json").exists()
    assert queue_path.read_bytes() == queue_before


def test_capacity_fails_closed_when_legacy_adoption_run_binding_is_missing(
    tmp_path: Path,
) -> None:
    from tests.test_legacy_transition import RECORDED_AT
    from tests.test_legacy_transition import RUN_ID as TRANSITION_RUN_ID
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.manager_screening import (
        ManagerScreeningError,
        freeze_manager_screen_batch,
        record_manager_screen_decisions,
    )

    fixture, policy_path = _recorded_transition_root(tmp_path)
    root = Path(fixture["coverage_root"])
    frozen = freeze_manager_screen_batch(
        root=root,
        run_id=TRANSITION_RUN_ID,
        batch_id="batch-001",
        frozen_at=RECORDED_AT + dt.timedelta(minutes=1),
        batch_size=1,
        policy_path=policy_path,
    )
    packet = json.loads(
        (Path(fixture["repository_root"]) / frozen["packet_path"]).read_text(encoding="utf-8")
    )
    queue_path = root / "research_queue.jsonl"
    queue = read_jsonl(queue_path)
    adoption = next(item for item in queue if item.get("legacy_transition_action") == "adoption")
    adoption.pop("legacy_transition_run_id")
    write_jsonl(queue_path, queue)

    with pytest.raises(
        ManagerScreeningError,
        match="does not match the sealed legacy adoption",
    ):
        record_manager_screen_decisions(
            root=root,
            run_id=TRANSITION_RUN_ID,
            batch_id="batch-001",
            submission=_send_submission([packet["dossiers"][0]["symbol"]]),
            recorded_at=RECORDED_AT + dt.timedelta(minutes=2),
        )


def test_capacity_fails_closed_when_referenced_legacy_transition_is_missing(
    tmp_path: Path,
) -> None:
    from tests.test_legacy_transition import RECORDED_AT
    from tests.test_legacy_transition import RUN_ID as TRANSITION_RUN_ID
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.manager_screening import (
        ManagerScreeningError,
        freeze_manager_screen_batch,
        record_manager_screen_decisions,
    )

    fixture, policy_path = _recorded_transition_root(tmp_path)
    root = Path(fixture["coverage_root"])
    frozen = freeze_manager_screen_batch(
        root=root,
        run_id=TRANSITION_RUN_ID,
        batch_id="batch-001",
        frozen_at=RECORDED_AT + dt.timedelta(minutes=1),
        batch_size=1,
        policy_path=policy_path,
    )
    packet = json.loads(
        (Path(fixture["repository_root"]) / frozen["packet_path"]).read_text(encoding="utf-8")
    )
    transition_dir = root / "manager-screen" / TRANSITION_RUN_ID / "legacy-transition-001"
    queue_path = root / "research_queue.jsonl"
    queue = read_jsonl(queue_path)
    for item in queue:
        if item.get("legacy_transition_result_path") is not None:
            item.pop("legacy_transition_run_id", None)
            item.pop("legacy_transition_id", None)
            item.pop("manager_screen_run_id", None)
            item.pop("manager_screen_batch_id", None)
    write_jsonl(queue_path, queue)
    shutil.rmtree(transition_dir)
    queue_before = queue_path.read_bytes()
    result_path = root / "manager-screen" / TRANSITION_RUN_ID / "batch-001" / "result.json"

    with pytest.raises(
        ManagerScreeningError,
        match="references a missing sealed legacy transition",
    ):
        record_manager_screen_decisions(
            root=root,
            run_id=TRANSITION_RUN_ID,
            batch_id="batch-001",
            submission=_send_submission([packet["dossiers"][0]["symbol"]]),
            recorded_at=RECORDED_AT + dt.timedelta(minutes=2),
        )
    assert not result_path.exists()
    assert not result_path.with_name("result.json.seal.json").exists()
    assert queue_path.read_bytes() == queue_before


def test_capacity_ignores_legacy_reference_from_an_unrelated_run(
    tmp_path: Path,
) -> None:
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.manager_screening import (
        freeze_manager_screen_batch,
        record_manager_screen_decisions,
    )

    root, policy_path = _root(tmp_path)
    frozen = freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        frozen_at=CUTOFF + dt.timedelta(minutes=1),
        batch_size=1,
        policy_path=policy_path,
    )
    packet = json.loads((tmp_path / frozen["packet_path"]).read_text(encoding="utf-8"))
    queue_path = root / "research_queue.jsonl"
    queue = read_jsonl(queue_path)
    queue.append(
        {
            "symbol": "CN:999999",
            "legacy_transition_run_id": "prior-unrelated-run",
            "legacy_transition_action": "adoption",
            "legacy_transition_result_path": "missing/prior/result.json",
            "legacy_transition_result_sha256": "f" * 64,
        }
    )
    write_jsonl(queue_path, queue)

    recorded = record_manager_screen_decisions(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        submission=_send_submission([packet["dossiers"][0]["symbol"]]),
        recorded_at=CUTOFF + dt.timedelta(minutes=2),
    )
    assert recorded["decision_count"] == 1


def test_transition_release_fails_closed_when_not_materialized(
    tmp_path: Path,
) -> None:
    from tests.test_legacy_transition import RUN_ID as TRANSITION_RUN_ID
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.manager_screening import (
        ManagerScreeningError,
        manager_screen_status,
    )

    fixture, _ = _recorded_transition_root(tmp_path)
    root = Path(fixture["coverage_root"])
    queue_path = root / "research_queue.jsonl"
    queue = read_jsonl(queue_path)
    release = next(item for item in queue if item["symbol"] == fixture["symbols"]["rescreen"])
    release.pop("legacy_transition_result_sha256")
    write_jsonl(queue_path, queue)

    with pytest.raises(
        ManagerScreeningError,
        match="not fully materialized",
    ):
        manager_screen_status(root=root, run_id=TRANSITION_RUN_ID)


def test_transition_duplicate_release_tamper_fails_closed(
    tmp_path: Path,
) -> None:
    from tests.test_legacy_transition import RUN_ID as TRANSITION_RUN_ID
    from trading_os.research_assets.manager_screening import (
        ManagerScreeningError,
        manager_screen_status,
    )

    fixture, _ = _recorded_transition_root(tmp_path)
    root = Path(fixture["coverage_root"])
    result_path = (
        root / "manager-screen" / TRANSITION_RUN_ID / "legacy-transition-001" / "result.json"
    )
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["releases"].append(result["releases"][0])
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )

    with pytest.raises(
        ManagerScreeningError,
        match="transition.*invalid",
    ):
        manager_screen_status(root=root, run_id=TRANSITION_RUN_ID)


def test_superseded_batch_releases_members_and_cannot_be_recorded(tmp_path: Path):
    from trading_os.research_assets.manager_screen_governance import (
        supersede_manager_screen_batch,
    )
    from trading_os.research_assets.manager_screening import (
        ManagerScreeningError,
        freeze_manager_screen_batch,
        manager_screen_status,
        record_manager_screen_decisions,
    )

    root, policy_path = _root(tmp_path)
    freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        frozen_at=CUTOFF + dt.timedelta(minutes=1),
        policy_path=policy_path,
    )
    supersede_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        manager={
            "agent": "/root",
            "model": "gpt-test",
            "tools": ["packet_read"],
        },
        reason="行情口径需要重冻，释放未决策成员。",
        superseded_at=CUTOFF + dt.timedelta(minutes=2),
    )
    queue_before = (root / "research_queue.jsonl").read_bytes()
    screening_before = (root / "screening.jsonl").read_bytes()
    with pytest.raises(ManagerScreeningError, match="superseded.*cannot be recorded"):
        record_manager_screen_decisions(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-001",
            submission=_submission(["CN:000001", "CN:000002"]),
            recorded_at=CUTOFF + dt.timedelta(minutes=3),
        )
    assert (root / "research_queue.jsonl").read_bytes() == queue_before
    assert (root / "screening.jsonl").read_bytes() == screening_before

    released = manager_screen_status(root=root, run_id=RUN_ID)
    assert released["batches_total"] == 1
    assert released["active_batches"] == 0
    assert released["open_batches"] == 0
    assert released["superseded_batches"] == 1
    assert released["superseded_company_count"] == 2
    assert released["batched_company_count"] == 0
    assert released["remaining_unbatched_count"] == 4
    assert released["batches"][0]["status"] == "superseded"
    assert released["batches"][0]["calibration"]["status"] == "not_applicable"

    frozen = freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-002",
        frozen_at=CUTOFF + dt.timedelta(minutes=4),
        policy_path=policy_path,
    )
    second_batch = json.loads((tmp_path / frozen["batch_path"]).read_text(encoding="utf-8"))
    assert [item["symbol"] for item in second_batch["members"]] == [
        "CN:000001",
        "CN:000002",
    ]
    reused = manager_screen_status(root=root, run_id=RUN_ID)
    assert reused["batches_total"] == 2
    assert reused["active_batches"] == 1
    assert reused["superseded_batches"] == 1
    assert reused["batched_company_count"] == 2
    assert reused["open_company_count"] == 2
    assert reused["remaining_unbatched_count"] == 2
    assert reused["screenable_conservation_satisfied"] is True


def test_send_to_analyst_run_capacity_rejects_whole_batch_before_writes(
    tmp_path: Path,
):
    from trading_os.research_assets.manager_screening import (
        ManagerScreeningError,
        freeze_manager_screen_batch,
        manager_screen_status,
        record_manager_screen_decisions,
    )

    root, policy_path = _root(tmp_path)
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    policy["payload"]["send_to_analyst_capacity_per_run"] = 1
    policy_path.write_text(
        json.dumps(policy, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    first = freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        batch_size=1,
        frozen_at=CUTOFF + dt.timedelta(minutes=1),
        policy_path=policy_path,
    )
    first_batch = json.loads((tmp_path / first["batch_path"]).read_text(encoding="utf-8"))
    assert first_batch["policy"]["send_to_analyst_capacity_per_run"] == 1
    record_manager_screen_decisions(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        submission=_send_submission(["CN:000001"]),
        recorded_at=CUTOFF + dt.timedelta(minutes=2),
    )
    freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-002",
        batch_size=2,
        frozen_at=CUTOFF + dt.timedelta(minutes=3),
        policy_path=policy_path,
    )
    submission = _send_submission(["CN:000002", "CN:000003"])
    submitted_copy = copy.deepcopy(submission)
    queue_before = (root / "research_queue.jsonl").read_bytes()
    screening_before = (root / "screening.jsonl").read_bytes()
    result_path = root / "manager-screen" / RUN_ID / "batch-002" / "result.json"
    with pytest.raises(
        ManagerScreeningError,
        match=r"1 sealed \+ 2 requested > 1.*whole batch was rejected",
    ):
        record_manager_screen_decisions(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-002",
            submission=submission,
            recorded_at=CUTOFF + dt.timedelta(minutes=4),
        )
    assert submission == submitted_copy
    assert not result_path.exists()
    assert not result_path.with_name("result.json.seal.json").exists()
    assert (root / "research_queue.jsonl").read_bytes() == queue_before
    assert (root / "screening.jsonl").read_bytes() == screening_before
    status = manager_screen_status(root=root, run_id=RUN_ID)
    assert status["by_route"] == {"send_to_analyst": 1}
    assert status["completed_batches"] == 1
    assert status["open_batches"] == 1


def test_policy_without_run_capacity_remains_backward_compatible(tmp_path: Path):
    from trading_os.research_assets.manager_screening import (
        freeze_manager_screen_batch,
        manager_screen_status,
        record_manager_screen_decisions,
    )

    root, policy_path = _root(tmp_path)
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    del policy["payload"]["send_to_analyst_capacity_per_run"]
    policy_path.write_text(
        json.dumps(policy, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    for index, symbol in enumerate(("CN:000001", "CN:000002"), 1):
        batch_id = f"batch-{index:03d}"
        frozen = freeze_manager_screen_batch(
            root=root,
            run_id=RUN_ID,
            batch_id=batch_id,
            batch_size=1,
            frozen_at=CUTOFF + dt.timedelta(minutes=index * 2 - 1),
            policy_path=policy_path,
        )
        batch = json.loads((tmp_path / frozen["batch_path"]).read_text(encoding="utf-8"))
        assert "send_to_analyst_capacity_per_run" not in batch["policy"]
        record_manager_screen_decisions(
            root=root,
            run_id=RUN_ID,
            batch_id=batch_id,
            submission=_send_submission([symbol]),
            recorded_at=CUTOFF + dt.timedelta(minutes=index * 2),
        )
    status = manager_screen_status(root=root, run_id=RUN_ID)
    assert status["by_route"] == {"send_to_analyst": 2}


def test_run_capacity_policy_can_tighten_but_cannot_expand_or_be_removed(
    tmp_path: Path,
):
    from trading_os.research_assets.manager_screening import (
        ManagerScreeningError,
        freeze_manager_screen_batch,
        record_manager_screen_decisions,
    )

    root, policy_path = _root(tmp_path)
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    policy["payload"]["send_to_analyst_capacity_per_run"] = 2
    policy_path.write_text(
        json.dumps(policy, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        batch_size=1,
        frozen_at=CUTOFF + dt.timedelta(minutes=1),
        policy_path=policy_path,
    )
    record_manager_screen_decisions(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        submission=_send_submission(["CN:000001"]),
        recorded_at=CUTOFF + dt.timedelta(minutes=2),
    )

    policy["payload"]["send_to_analyst_capacity_per_run"] = 3
    policy_path.write_text(
        json.dumps(policy, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ManagerScreeningError, match="cannot expand within a run"):
        freeze_manager_screen_batch(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-002",
            batch_size=1,
            frozen_at=CUTOFF + dt.timedelta(minutes=3),
            policy_path=policy_path,
        )

    del policy["payload"]["send_to_analyst_capacity_per_run"]
    policy_path.write_text(
        json.dumps(policy, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ManagerScreeningError, match="cannot remove an established cap"):
        freeze_manager_screen_batch(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-002",
            batch_size=1,
            frozen_at=CUTOFF + dt.timedelta(minutes=3),
            policy_path=policy_path,
        )

    policy["payload"]["send_to_analyst_capacity_per_run"] = 1
    policy["payload"]["quick_profile_effort_budget_hours"] += 1
    policy_path.write_text(
        json.dumps(policy, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ManagerScreeningError, match="effort budget cannot expand"):
        freeze_manager_screen_batch(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-002",
            batch_size=1,
            frozen_at=CUTOFF + dt.timedelta(minutes=3),
            policy_path=policy_path,
        )

    policy["payload"]["quick_profile_effort_budget_hours"] -= 1
    policy_path.write_text(
        json.dumps(policy, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-002",
        batch_size=1,
        frozen_at=CUTOFF + dt.timedelta(minutes=3),
        policy_path=policy_path,
    )
    with pytest.raises(
        ManagerScreeningError,
        match=r"1 sealed \+ 1 requested > 1",
    ):
        record_manager_screen_decisions(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-002",
            submission=_send_submission(["CN:000002"]),
            recorded_at=CUTOFF + dt.timedelta(minutes=4),
        )


def test_decision_v2_risk_gate_cannot_be_removed_or_loosened_within_run(
    tmp_path: Path,
):
    from trading_os.research_assets.manager_screening import (
        ManagerScreeningError,
        freeze_manager_screen_batch,
    )

    root, policy_path = _root(tmp_path)
    _policy(policy_path, decision_contract_version=2)
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        batch_size=1,
        frozen_at=CUTOFF + dt.timedelta(minutes=1),
        policy_path=policy_path,
    )

    v2_fields = {
        key: policy["payload"].pop(key)
        for key in (
            "decision_contract_version",
            "mandatory_risk_acknowledgement",
            "canonical_fact_line_required",
            "high_liability_to_assets_pct",
        )
    }
    policy_path.write_text(
        json.dumps(policy, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ManagerScreeningError, match="v2 cannot be removed"):
        freeze_manager_screen_batch(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-002",
            batch_size=1,
            frozen_at=CUTOFF + dt.timedelta(minutes=2),
            policy_path=policy_path,
        )

    policy["payload"].update(v2_fields)
    policy["payload"]["high_liability_to_assets_pct"] = 95.0
    policy_path.write_text(
        json.dumps(policy, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ManagerScreeningError, match="cannot be loosened"):
        freeze_manager_screen_batch(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-002",
            batch_size=1,
            frozen_at=CUTOFF + dt.timedelta(minutes=2),
            policy_path=policy_path,
        )

    policy["payload"]["high_liability_to_assets_pct"] = 85.0
    policy_path.write_text(
        json.dumps(policy, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    frozen = freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-002",
        batch_size=1,
        frozen_at=CUTOFF + dt.timedelta(minutes=2),
        policy_path=policy_path,
    )
    assert frozen["member_count"] == 1


def test_calibration_writes_respect_the_shared_coverage_lock(tmp_path: Path):
    from trading_os.research_assets.coverage_store import (
        CoverageValidationError,
        coverage_write_lock,
    )
    from trading_os.research_assets.manager_screening import (
        prepare_manager_screen_calibration,
        record_manager_screen_calibration,
    )

    root, policy_path = _root(tmp_path)
    with coverage_write_lock(root):
        with pytest.raises(CoverageValidationError, match="coverage state is busy"):
            prepare_manager_screen_calibration(
                root=root,
                run_id=RUN_ID,
                batch_id="batch-001",
                calibration_id="calibration-001",
                prepared_at=CUTOFF + dt.timedelta(minutes=1),
                policy_path=policy_path,
            )
        with pytest.raises(CoverageValidationError, match="coverage state is busy"):
            record_manager_screen_calibration(
                root=root,
                run_id=RUN_ID,
                batch_id="batch-001",
                calibration_id="calibration-001",
                submission={},
                recorded_at=CUTOFF + dt.timedelta(minutes=2),
            )


def test_sealed_quote_amendment_refreshes_immutable_snapshot_and_binds_batch(
    tmp_path: Path,
):
    from trading_os.research_assets.coverage_store import read_jsonl
    from trading_os.research_assets.manager_screen_snapshot import (
        prepare_manager_screen_quote_amendment,
    )
    from trading_os.research_assets.manager_screening import (
        freeze_manager_screen_batch,
    )
    from trading_os.research_assets.scope_workflow import freeze_all_a_scope

    root, policy_path = _root(tmp_path)
    run_id = "2026-07-31-manager-screen-amendment"
    immutable_snapshot = root / "snapshots" / run_id / "companies.jsonl"
    companies = read_jsonl(root / "companies.jsonl")
    for company in companies:
        company["as_of"] = "2026-07-01"
        company["price"] = 9.0
        company["manager_screen_facts"]["quote_freshness"] = _quote_freshness(
            CUTOFF - dt.timedelta(days=30)
        )
    _write_jsonl(immutable_snapshot, companies)
    original_sha256 = hashlib.sha256(immutable_snapshot.read_bytes()).hexdigest()
    freeze_all_a_scope(
        root=root,
        run_id=run_id,
        scope_cutoff=CUTOFF,
        frozen_at=CUTOFF,
        universe_path=immutable_snapshot,
    )

    quotes = [
        {
            "symbol": company["symbol"],
            "price": 10.0 + index,
            "as_of": (CUTOFF + dt.timedelta(minutes=1)).isoformat(),
            "source": "explicit refreshed quote fixture",
        }
        for index, company in enumerate(companies)
    ]
    amendment = prepare_manager_screen_quote_amendment(
        root=root,
        run_id=run_id,
        amendment_id="quotes-001",
        effective_at=CUTOFF + dt.timedelta(minutes=1),
        quote_snapshot=quotes,
        quote_max_age=dt.timedelta(hours=1),
    )
    replay = prepare_manager_screen_quote_amendment(
        root=root,
        run_id=run_id,
        amendment_id="quotes-001",
        effective_at=CUTOFF + dt.timedelta(minutes=1),
        quote_snapshot=quotes,
        quote_max_age=dt.timedelta(hours=1),
    )
    assert replay["sha256"] == amendment["sha256"]
    assert hashlib.sha256(immutable_snapshot.read_bytes()).hexdigest() == original_sha256

    frozen = freeze_manager_screen_batch(
        root=root,
        run_id=run_id,
        batch_id="batch-001",
        frozen_at=CUTOFF + dt.timedelta(minutes=2),
        policy_path=policy_path,
    )
    batch = json.loads((tmp_path / frozen["batch_path"]).read_text(encoding="utf-8"))
    packet = json.loads((tmp_path / frozen["packet_path"]).read_text(encoding="utf-8"))
    assert batch["quote_amendment"]["path"] == amendment["path"]
    assert batch["quote_amendment"]["sha256"] == amendment["sha256"]
    assert packet["dossiers"][0]["market_snapshot"]["price"] == 10.0
    assert any(
        item["kind"] == "market_quote_amendment"
        for item in packet["dossiers"][0]["evidence_catalog"]
    )

    from trading_os.research_assets.manager_screening import ManagerScreeningError
    from trading_os.research_assets.sealing import seal_json

    valid_amendment_path = tmp_path / amendment["path"]
    forged = copy.deepcopy(json.loads(valid_amendment_path.read_text(encoding="utf-8")))
    forged["amendment_id"] = "quotes-forged"
    stale_as_of = (CUTOFF - dt.timedelta(days=30)).isoformat()
    for quote in forged["quotes"]:
        quote["as_of"] = stale_as_of
        quote["quote_freshness"]["quote_as_of"] = stale_as_of
        quote["quote_freshness"]["status"] = "fresh"
    forged_path = valid_amendment_path.parent / "quotes-forged.json"
    seal_json(
        forged_path,
        forged,
        artifact_type="manager_screen_quote_amendment",
        sealed_at=CUTOFF + dt.timedelta(minutes=1),
    )
    with pytest.raises(ManagerScreeningError, match="claims a stale quote is fresh"):
        freeze_manager_screen_batch(
            root=root,
            run_id=run_id,
            batch_id="batch-002",
            frozen_at=CUTOFF + dt.timedelta(minutes=3),
            policy_path=policy_path,
        )


def test_calibration_review_closes_sample_without_changing_coverage(tmp_path: Path):
    from trading_os.research_assets.manager_screening import (
        ManagerScreeningError,
        freeze_manager_screen_batch,
        manager_screen_calibration_status,
        manager_screen_status,
        prepare_manager_screen_calibration,
        record_manager_screen_calibration,
        record_manager_screen_decisions,
    )

    root, policy_path = _root(tmp_path)
    freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        frozen_at=CUTOFF + dt.timedelta(minutes=1),
        policy_path=policy_path,
    )
    record_manager_screen_decisions(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        submission=_submission(["CN:000001", "CN:000002"]),
        recorded_at=CUTOFF + dt.timedelta(minutes=2),
    )
    queue_before = (root / "research_queue.jsonl").read_bytes()
    screening_before = (root / "screening.jsonl").read_bytes()

    prepared = prepare_manager_screen_calibration(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        calibration_id="calibration-001",
        prepared_at=CUTOFF + dt.timedelta(minutes=3),
        policy_path=policy_path,
    )
    packet = json.loads((tmp_path / prepared["packet_path"]).read_text(encoding="utf-8"))
    assert packet["reviewer_contract"]["recursive_correction"] == "forbidden"
    assert packet["reviewer_contract"]["route_disagreement_is_material_error"] is False
    assert packet["reviewer_contract"]["adjudication_trigger"] == "material_error_only"
    assert packet["plan"]["planned_sample_count"] == len(packet["samples"]) == 1

    missing = manager_screen_calibration_status(root=root, run_id=RUN_ID)
    assert missing["calibration"]["status"] == "missing"
    assert missing["calibration"]["missing_sample_count"] == 1

    incomplete = _calibration_submission(packet)
    incomplete["reviews"] = []
    with pytest.raises(ManagerScreeningError, match="cover the deterministic sample"):
        record_manager_screen_calibration(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-001",
            calibration_id="calibration-001",
            submission=incomplete,
            recorded_at=CUTOFF + dt.timedelta(minutes=4),
        )
    same_manager = _calibration_submission(packet)
    same_manager["reviewer"]["agent"] = "/root"
    with pytest.raises(ManagerScreeningError, match="must be independent"):
        record_manager_screen_calibration(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-001",
            calibration_id="calibration-001",
            submission=same_manager,
            recorded_at=CUTOFF + dt.timedelta(minutes=4),
        )

    route_only_adjudication = _calibration_submission(packet)
    route_only_adjudication["reviews"][0]["adjudication"] = {
        "performed": True,
        "outcome": "manager_upheld",
        "finding": "路由观点分歧不应触发裁决。",
        "evidence_ids": [packet["samples"][0]["evidence_ids"][0]],
    }
    with pytest.raises(
        ManagerScreeningError,
        match="adjudication is allowed only for material errors",
    ):
        record_manager_screen_calibration(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-001",
            calibration_id="calibration-001",
            submission=route_only_adjudication,
            recorded_at=CUTOFF + dt.timedelta(minutes=4),
        )

    submission = _calibration_submission(packet)
    recorded = record_manager_screen_calibration(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        calibration_id="calibration-001",
        submission=submission,
        recorded_at=CUTOFF + dt.timedelta(minutes=4),
    )
    assert recorded["status"] == "complete"
    assert recorded["material_error_count"] == 0
    assert recorded["route_disagreement_count"] == 1
    assert (
        record_manager_screen_calibration(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-001",
            calibration_id="calibration-001",
            submission=submission,
            recorded_at=CUTOFF + dt.timedelta(minutes=5),
        )["result_sha256"]
        == recorded["result_sha256"]
    )
    status = manager_screen_status(root=root, run_id=RUN_ID)
    assert status["calibration"]["status"] == "complete"
    assert status["calibration"]["reviewed_sample_count"] == 1
    assert status["calibration"]["missing_sample_count"] == 0
    assert status["calibration"]["route_disagreement_count"] == 1
    assert status["calibration"]["material_error_count"] == 0
    assert status["batches"][0]["calibration"]["adjudication_count"] == 0
    assert (root / "research_queue.jsonl").read_bytes() == queue_before
    assert (root / "screening.jsonl").read_bytes() == screening_before
    with pytest.raises(ManagerScreeningError, match="single-shot"):
        prepare_manager_screen_calibration(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-001",
            calibration_id="calibration-002",
            prepared_at=CUTOFF + dt.timedelta(minutes=6),
            policy_path=policy_path,
        )


def test_legacy_sealed_calibration_route_adjudication_remains_readable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    import trading_os.research_assets.manager_screening as manager_screening
    from trading_os.research_assets.coverage_store import validate_coverage_root

    root, policy_path = _root(tmp_path)
    manager_screening.freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        frozen_at=CUTOFF + dt.timedelta(minutes=1),
        policy_path=policy_path,
    )
    manager_screening.record_manager_screen_decisions(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        submission=_submission(["CN:000001", "CN:000002"]),
        recorded_at=CUTOFF + dt.timedelta(minutes=2),
    )
    reviewer_contract = manager_screening._calibration_reviewer_contract

    def legacy_reviewer_contract():
        contract = reviewer_contract()
        contract.pop("adjudication_trigger")
        return contract

    monkeypatch.setattr(
        manager_screening,
        "_calibration_reviewer_contract",
        legacy_reviewer_contract,
    )
    prepared = manager_screening.prepare_manager_screen_calibration(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        calibration_id="calibration-legacy",
        prepared_at=CUTOFF + dt.timedelta(minutes=3),
        policy_path=policy_path,
    )
    monkeypatch.setattr(
        manager_screening,
        "_calibration_reviewer_contract",
        reviewer_contract,
    )
    packet = json.loads((tmp_path / prepared["packet_path"]).read_text(encoding="utf-8"))
    assert "adjudication_trigger" not in packet["reviewer_contract"]
    legacy_submission = _calibration_submission(packet)
    legacy_submission["reviews"][0]["adjudication"] = {
        "performed": True,
        "outcome": "manager_upheld",
        "finding": "历史 contract 曾允许对纯路由分歧执行一次裁决。",
        "evidence_ids": [packet["samples"][0]["evidence_ids"][0]],
    }

    normalize = manager_screening._normalize_calibration_submission

    def normalize_as_legacy(*args, **kwargs):
        kwargs["legacy_contract"] = True
        return normalize(*args, **kwargs)

    monkeypatch.setattr(
        manager_screening,
        "_normalize_calibration_submission",
        normalize_as_legacy,
    )
    recorded = manager_screening.record_manager_screen_calibration(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        calibration_id="calibration-legacy",
        submission=legacy_submission,
        recorded_at=CUTOFF + dt.timedelta(minutes=4),
    )
    monkeypatch.setattr(
        manager_screening,
        "_normalize_calibration_submission",
        normalize,
    )

    status = manager_screening.manager_screen_status(root=root, run_id=RUN_ID)
    assert status["calibration"]["route_disagreement_count"] == 1
    assert status["calibration"]["material_error_count"] == 0
    assert status["calibration"]["adjudication_count"] == 1
    assert validate_coverage_root(root)["manager_screen_runs"][0]["run_id"] == RUN_ID
    assert (
        manager_screening.record_manager_screen_calibration(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-001",
            calibration_id="calibration-legacy",
            submission=legacy_submission,
            recorded_at=CUTOFF + dt.timedelta(minutes=5),
        )["result_sha256"]
        == recorded["result_sha256"]
    )


def test_calibration_material_error_is_non_blocking_and_not_route_disagreement(
    tmp_path: Path,
):
    from trading_os.research_assets.manager_screening import (
        ManagerScreeningError,
        freeze_manager_screen_batch,
        manager_screen_status,
        prepare_manager_screen_calibration,
        record_manager_screen_calibration,
        record_manager_screen_decisions,
    )

    root, policy_path = _root(tmp_path)
    freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        frozen_at=CUTOFF + dt.timedelta(minutes=1),
        policy_path=policy_path,
    )
    record_manager_screen_decisions(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        submission=_submission(["CN:000001", "CN:000002"]),
        recorded_at=CUTOFF + dt.timedelta(minutes=2),
    )
    prepared = prepare_manager_screen_calibration(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        calibration_id="calibration-error",
        prepared_at=CUTOFF + dt.timedelta(minutes=3),
        policy_path=policy_path,
    )
    packet = json.loads((tmp_path / prepared["packet_path"]).read_text(encoding="utf-8"))
    missing_adjudication = _calibration_submission(
        packet,
        material_error=True,
        route_disagreement=False,
    )
    missing_adjudication["reviews"][0]["adjudication"] = {
        "performed": False,
        "outcome": "not_needed",
        "finding": None,
        "evidence_ids": [],
    }
    with pytest.raises(
        ManagerScreeningError,
        match="material errors require adjudication",
    ):
        record_manager_screen_calibration(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-001",
            calibration_id="calibration-error",
            submission=missing_adjudication,
            recorded_at=CUTOFF + dt.timedelta(minutes=4),
        )
    recorded = record_manager_screen_calibration(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        calibration_id="calibration-error",
        submission=_calibration_submission(
            packet,
            material_error=True,
            route_disagreement=False,
        ),
        recorded_at=CUTOFF + dt.timedelta(minutes=4),
    )
    assert recorded["status"] == "material_error"
    assert recorded["material_error_count"] == 1
    status = manager_screen_status(root=root, run_id=RUN_ID)
    assert status["calibration"]["status"] == "material_error"
    assert status["calibration"]["material_error_count"] == 1
    assert status["calibration"]["route_disagreement_count"] == 0
    assert status["calibration"]["non_blocking"] is True
    assert status["by_route"] == {"pass": 1, "send_to_analyst": 1}


def test_legacy_batch_can_freeze_current_policy_calibration_without_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    import trading_os.research_assets.manager_screening as manager_screening

    root, policy_path = _root(tmp_path)
    repository_root = root.parent.parent
    original_loader = manager_screening._load_policy_contract
    full_policy = original_loader(
        policy_path=policy_path,
        repository_root=repository_root,
    )
    legacy_policy = {
        key: value
        for key, value in full_policy.items()
        if key in manager_screening.LEGACY_POLICY_REF_KEYS
    }
    monkeypatch.setattr(
        manager_screening,
        "_load_policy_contract",
        lambda **_: dict(legacy_policy),
    )
    manager_screening.freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        frozen_at=CUTOFF + dt.timedelta(minutes=1),
        policy_path=policy_path,
    )
    monkeypatch.setattr(
        manager_screening,
        "_load_policy_contract",
        original_loader,
    )
    manager_screening.record_manager_screen_decisions(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        submission=_submission(["CN:000001", "CN:000002"]),
        recorded_at=CUTOFF + dt.timedelta(minutes=2),
    )
    batch_path = root / "manager-screen" / RUN_ID / "batch-001" / "batch.json"
    result_path = root / "manager-screen" / RUN_ID / "batch-001" / "result.json"
    batch_before = batch_path.read_bytes()
    result_before = result_path.read_bytes()
    result_payload = json.loads(result_before)
    assert "calibration" not in result_payload["quality_state"]

    prepared = manager_screening.prepare_manager_screen_calibration(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        calibration_id="legacy-calibration",
        prepared_at=CUTOFF + dt.timedelta(minutes=3),
        policy_path=policy_path,
    )
    packet = json.loads((tmp_path / prepared["packet_path"]).read_text(encoding="utf-8"))
    assert packet["policy"]["payload_sha256"] == full_policy["payload_sha256"]
    assert packet["plan"]["planned_sample_count"] == 1
    assert batch_path.read_bytes() == batch_before
    assert result_path.read_bytes() == result_before
    status = manager_screening.manager_screen_status(root=root, run_id=RUN_ID)
    assert status["batches"][0]["calibration"]["status"] == "missing"


def test_watch_materializes_as_general_watch_only(tmp_path: Path):
    from trading_os.research_assets.coverage_store import read_jsonl
    from trading_os.research_assets.manager_screening import (
        freeze_manager_screen_batch,
        record_manager_screen_decisions,
    )

    root, policy_path = _root(tmp_path)
    freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        frozen_at=CUTOFF + dt.timedelta(minutes=1),
        policy_path=policy_path,
    )
    submission = _submission(["CN:000001", "CN:000002"])
    submission["decisions"][0]["route"] = "watch"
    record_manager_screen_decisions(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        submission=submission,
        recorded_at=CUTOFF + dt.timedelta(minutes=2),
    )

    screening = {item["symbol"]: item for item in read_jsonl(root / "screening.jsonl")}
    assert screening["CN:000001"]["decision"] == "watch_only"
    assert "价格、财报、事件或关键证据" in screening["CN:000001"]["next_action"]


def test_result_replay_preserves_later_queue_and_screening_progress(tmp_path: Path):
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.manager_screening import (
        freeze_manager_screen_batch,
        record_manager_screen_decisions,
    )

    root, policy_path = _root(tmp_path)
    freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        frozen_at=CUTOFF + dt.timedelta(minutes=1),
        policy_path=policy_path,
    )
    submission = _submission(["CN:000001", "CN:000002"])
    record_manager_screen_decisions(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        submission=submission,
        recorded_at=CUTOFF + dt.timedelta(minutes=2),
    )

    queue_path = root / "research_queue.jsonl"
    queue = read_jsonl(queue_path)
    analyst_row = next(item for item in queue if item["symbol"] == "CN:000002")
    analyst_row.update(
        {
            "task_type": "deep_research",
            "status": "running",
            "assigned_agent": "/root/analyst-000002",
            "started_at": (CUTOFF + dt.timedelta(minutes=3)).isoformat(),
        }
    )
    write_jsonl(queue_path, queue)

    screening_path = root / "screening.jsonl"
    screening = read_jsonl(screening_path)
    screen_row = next(item for item in screening if item["symbol"] == "CN:000002")
    screen_row.update(
        {
            "decision": "deep_research",
            "reason": "后续研究已经推进到深研。",
            "next_action": "完成当前深研。",
        }
    )
    write_jsonl(screening_path, screening)
    queue_before = read_jsonl(queue_path)
    screening_before = read_jsonl(screening_path)

    record_manager_screen_decisions(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        submission=submission,
        recorded_at=CUTOFF + dt.timedelta(minutes=4),
    )

    assert read_jsonl(queue_path) == queue_before
    assert read_jsonl(screening_path) == screening_before


def test_manager_record_rejects_incomplete_order_score_and_unknown_evidence(
    tmp_path: Path,
):
    from trading_os.research_assets.manager_screening import (
        ManagerScreeningError,
        freeze_manager_screen_batch,
        record_manager_screen_decisions,
    )

    root, policy_path = _root(tmp_path)
    freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        frozen_at=CUTOFF + dt.timedelta(minutes=1),
        policy_path=policy_path,
    )
    submission = _submission(["CN:000001", "CN:000002"])
    submission["decisions"].reverse()
    with pytest.raises(ManagerScreeningError, match="complete batch exactly once"):
        record_manager_screen_decisions(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-001",
            submission=submission,
            recorded_at=CUTOFF + dt.timedelta(minutes=2),
        )

    submission = _submission(["CN:000001", "CN:000002"])
    submission["decisions"][0]["score"] = 99
    with pytest.raises(ManagerScreeningError, match="decision fields"):
        record_manager_screen_decisions(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-001",
            submission=submission,
            recorded_at=CUTOFF + dt.timedelta(minutes=2),
        )

    submission = _submission(["CN:000001", "CN:000002"])
    submission["decisions"][0]["evidence_ids"] = ["external:missing"]
    with pytest.raises(ManagerScreeningError, match="outside its dossier"):
        record_manager_screen_decisions(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-001",
            submission=submission,
            recorded_at=CUTOFF + dt.timedelta(minutes=2),
        )


def test_future_scope_accepts_manager_result_as_current_terminal(tmp_path: Path):
    from trading_os.research_assets.manager_screening import (
        freeze_manager_screen_batch,
        record_manager_screen_decisions,
    )
    from trading_os.research_assets.scope_workflow import freeze_all_a_scope

    root, policy_path = _root(tmp_path)
    freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        frozen_at=CUTOFF + dt.timedelta(minutes=1),
        policy_path=policy_path,
    )
    record_manager_screen_decisions(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        submission=_submission(["CN:000001", "CN:000002"]),
        recorded_at=CUTOFF + dt.timedelta(minutes=2),
    )
    next_scope = freeze_all_a_scope(
        root=root,
        run_id="2026-08-01-manager-screen-002",
        scope_cutoff=CUTOFF + dt.timedelta(days=1),
        frozen_at=CUTOFF + dt.timedelta(days=1),
        apply_intake=False,
    )
    assert next_scope["counts"]["current_protocol_terminal"] == 2
    assert next_scope["counts"]["baseline_backlog"] == 2


def test_future_scope_rejects_queue_sha_that_does_not_bind_result(tmp_path: Path):
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.manager_screening import (
        freeze_manager_screen_batch,
        record_manager_screen_decisions,
    )
    from trading_os.research_assets.scope_workflow import freeze_all_a_scope

    root, policy_path = _root(tmp_path)
    freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        frozen_at=CUTOFF + dt.timedelta(minutes=1),
        policy_path=policy_path,
    )
    record_manager_screen_decisions(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        submission=_submission(["CN:000001", "CN:000002"]),
        recorded_at=CUTOFF + dt.timedelta(minutes=2),
    )
    queue_path = root / "research_queue.jsonl"
    queue = read_jsonl(queue_path)
    next(item for item in queue if item["symbol"] == "CN:000001")[
        "manager_screen_result_sha256"
    ] = "0" * 64
    write_jsonl(queue_path, queue)

    next_scope = freeze_all_a_scope(
        root=root,
        run_id="2026-08-02-manager-screen-003",
        scope_cutoff=CUTOFF + dt.timedelta(days=2),
        frozen_at=CUTOFF + dt.timedelta(days=2),
        apply_intake=False,
    )
    assert next_scope["counts"]["current_protocol_terminal"] == 1
    assert next_scope["counts"]["baseline_backlog"] == 3


def test_status_rejects_batch_moved_outside_its_sealed_identity(tmp_path: Path):
    from trading_os.research_assets.manager_screening import (
        ManagerScreeningError,
        freeze_manager_screen_batch,
        manager_screen_status,
    )

    root, policy_path = _root(tmp_path)
    freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        frozen_at=CUTOFF + dt.timedelta(minutes=1),
        policy_path=policy_path,
    )
    run_dir = root / "manager-screen" / RUN_ID
    (run_dir / "batch-001").rename(run_dir / "batch-moved")

    with pytest.raises(ManagerScreeningError, match="sealed run and batch identity"):
        manager_screen_status(root=root, run_id=RUN_ID)


def test_manager_screen_cli_round_trip(tmp_path: Path, capsys):
    from trading_os.cli import main

    root, policy_path = _root(tmp_path)
    assert (
        main(
            [
                "coverage",
                "manager-screen-freeze",
                RUN_ID,
                "batch-001",
                "--root",
                str(root),
                "--policy",
                str(policy_path),
                "--batch-size",
                "2",
                "--at",
                (CUTOFF + dt.timedelta(minutes=1)).isoformat(),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["member_count"] == 2
    submission_path = tmp_path / "submission.json"
    submission_path.write_text(
        json.dumps(
            _submission(["CN:000001", "CN:000002"]),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    assert (
        main(
            [
                "coverage",
                "manager-screen-record",
                RUN_ID,
                "batch-001",
                "--root",
                str(root),
                "--input",
                str(submission_path),
                "--at",
                (CUTOFF + dt.timedelta(minutes=2)).isoformat(),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["by_route"]["send_to_analyst"] == 1
    assert (
        main(
            [
                "coverage",
                "manager-screen-status",
                RUN_ID,
                "--root",
                str(root),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_manager_screen_fails_closed_on_unsealed_transition_directory(
    tmp_path: Path,
):
    from trading_os.research_assets.manager_screening import (
        ManagerScreeningError,
        freeze_manager_screen_batch,
        manager_screen_status,
    )

    root, policy_path = _root(tmp_path)
    transition_dir = root / "manager-screen" / RUN_ID / "legacy-transition-001"
    transition_dir.mkdir(parents=True)
    (transition_dir / "plan.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ManagerScreeningError, match="transition.*invalid"):
        manager_screen_status(root=root, run_id=RUN_ID)
    with pytest.raises(ManagerScreeningError, match="transition.*invalid"):
        freeze_manager_screen_batch(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-001",
            frozen_at=CUTOFF + dt.timedelta(minutes=1),
            batch_size=2,
            policy_path=policy_path,
        )
