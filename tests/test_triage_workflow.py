from __future__ import annotations

import copy
import datetime as dt
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CYCLE = "2026-07-27-triage-test"
RECORDED_AT = dt.datetime.fromisoformat("2026-07-27T10:00:00+08:00")
SYMBOLS = [
    ("CN:000001", "公司一"),
    ("CN:000002", "公司二"),
    ("CN:000003", "公司三"),
]


def _policy() -> dict:
    return json.loads((ROOT / "policies" / "research-allocation.json").read_text(encoding="utf-8"))[
        "payload"
    ]


def _package(
    symbol: str,
    name: str,
    agent: str,
    *,
    cycle_id: str = CYCLE,
    research_value: str = "medium",
    valuation_signal: str = "possible",
    triggers: list[dict] | None = None,
) -> dict:
    revisit_triggers = triggers
    if revisit_triggers is None:
        revisit_triggers = [
            {
                "trigger_id": "routine-refresh",
                "type": "ttl",
                "condition": {"days": 90},
                "reason": "即使无重大事件，也应在九十天后重新快速复核。",
            }
        ]
    return {
        "schema_version": 2,
        "cycle_id": cycle_id,
        "symbol": symbol,
        "company_name": name,
        "as_of": "2026-07-27",
        "information_cutoff": "2026-07-27T09:30:00+08:00",
        "price_as_of": "2026-07-27T09:25:00+08:00",
        "price_source_id": "quote",
        "current_price": 10.0,
        "review_mode": "baseline_recheck",
        "prior_research_path": None,
        "trigger_context": "全覆盖基线复核批次。",
        "business_summary": "主营业务、客户和盈利来源已做快速核对。",
        "change_summary": "相对旧目录未发现足以跳过本次复核的重大变化。",
        "normalized_earnings_view": "剔除一次性项目后盈利大致可辨认。",
        "expectations_view": "当前价格隐含温和增长，仍需下一层研究验证。",
        "counterevidence": ["利润可能受周期高点影响", "现金流仍需核验"],
        "business_legibility": "clear",
        "survival_status": "pass",
        "governance_status": "acceptable",
        "earnings_legibility": "plausible",
        "valuation_signal": valuation_signal,
        "research_value": research_value,
        "decisive_question": "正常化所有者收益能否持续？",
        "reason_codes": ["latest_filing_and_price_checked"],
        "revisit_triggers": revisit_triggers,
        "sources": [
            {
                "source_id": "filing",
                "tier": "S1",
                "title": "最新定期报告",
                "accessed_at": "2026-07-27T09:00:00+08:00",
                "url": "https://example.com/filing",
                "local_path": None,
                "supports": ["business", "earnings", "governance"],
            },
            {
                "source_id": "quote",
                "tier": "S2",
                "title": "最新行情",
                "accessed_at": "2026-07-27T09:25:00+08:00",
                "url": "https://example.com/quote",
                "local_path": None,
                "supports": ["current_price"],
            },
        ],
        "provenance": {
            "agent": agent,
            "model": "test-model",
            "tools": ["repository", "browser"],
            "generated_at": "2026-07-27T09:45:00+08:00",
        },
    }


def _company(root: Path, symbol: str, name: str) -> None:
    ticker = symbol.split(":", 1)[1]
    company_dir = root / "research" / "companies" / "CN" / ticker
    company_dir.mkdir(parents=True)
    meta = {
        "schema_version": 2,
        "identity": {
            "symbol": symbol,
            "market": "CN",
            "ticker": ticker,
            "name": name,
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
            "reason_codes": [],
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
        "updated_at": "2026-07-20T10:00:00+08:00",
    }
    (company_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _coverage(root: Path, *, legacy_allocation: bool = False) -> Path:
    from trading_os.research_assets.coverage_store import write_jsonl

    coverage_root = root / "coverage" / "cn-a"
    write_jsonl(
        coverage_root / "companies.jsonl",
        [{"symbol": symbol, "name": name} for symbol, name in SYMBOLS],
    )
    write_jsonl(
        coverage_root / "screening.jsonl",
        [
            {
                "symbol": symbol,
                "name": name,
                "decision": "rapid_triage" if legacy_allocation else "needs_manual_review",
                "priority": 1 + index,
                "reason": "测试覆盖队列",
                "evidence": ["fixture:test"],
                "next_action": "等待快速甄别",
            }
            for index, (symbol, name) in enumerate(SYMBOLS)
        ],
    )
    queue = []
    for index, (symbol, name) in enumerate(SYMBOLS):
        record = {
            "symbol": symbol,
            "name": name,
            "task_type": "rapid_triage" if legacy_allocation else "initial_research",
            "priority": 1 + index,
            "status": "pending" if legacy_allocation else "requires_rebaseline",
            "reason": "测试覆盖队列",
            "target_company_dir": f"research/companies/CN/{symbol[-6:]}",
            "assigned_agent": None,
            "started_at": None,
            "finished_at": None,
            "result_path": None,
            "failure_reason": None,
            "next_action": "等待快速甄别",
        }
        if legacy_allocation:
            record.update(
                {
                    "effort_budget_hours": 0.25,
                    "preceding_stage": "machine_triage",
                    "stop_conditions": ["没有继续研究价值"],
                    "allocation_sha256": "a" * 64,
                    "selected_by": ["balanced"],
                }
            )
        queue.append(record)
        _company(root, symbol, name)
    write_jsonl(coverage_root / "research_queue.jsonl", queue)
    write_jsonl(coverage_root / "runs.jsonl", [], sort_key="run_id")
    return coverage_root


def _freeze(root: Path, *, symbols: list[str] | None = None) -> dict:
    from trading_os.research_assets.triage_cohort import freeze_rapid_triage_cohort

    return freeze_rapid_triage_cohort(
        root=root,
        cycle_id=CYCLE,
        frozen_at=RECORDED_AT,
        symbols=symbols,
        limit=None if symbols is not None else 3,
    )


def _decision_package(
    comparison_sha256: str,
    symbols: list[str],
    *,
    selected_symbols: list[str] | None = None,
) -> dict:
    selected = set(selected_symbols or [])
    return {
        "schema_version": 1,
        "cycle_id": CYCLE,
        "comparison_sha256": comparison_sha256,
        "decisions": [
            {
                "symbol": symbol,
                "decision": "select_quick_profile" if symbol in selected else "defer",
                "reason": f"独立复核后对 {symbol} 分配研究预算。",
                "decisive_question": "下一小时研究能否显著改变投资判断？",
                "counterevidence_considered": ["周期风险", "现金流反证"],
            }
            for symbol in symbols
        ],
        "provenance": {
            "agent": "/root/allocation-agent",
            "model": "test-model",
            "tools": ["repository"],
            "generated_at": "2026-07-27T10:08:00+08:00",
        },
    }


def test_triage_mutations_share_one_coverage_write_lock(tmp_path: Path):
    from trading_os.research_assets.coverage_store import (
        CoverageValidationError,
        coverage_write_lock,
        read_jsonl,
    )
    from trading_os.research_assets.triage_workflow import (
        claim_rapid_triage_task,
        finalize_rapid_triage_cycle,
        record_rapid_triage_package,
        release_rapid_triage_task,
    )

    root = _coverage(tmp_path)
    queue_before = read_jsonl(root / "research_queue.jsonl")
    with coverage_write_lock(root):
        with pytest.raises(CoverageValidationError, match="coverage state is busy"):
            _freeze(root)
    assert read_jsonl(root / "research_queue.jsonl") == queue_before

    _freeze(root)
    with coverage_write_lock(root):
        calls = [
            lambda: claim_rapid_triage_task(
                root=root,
                agent="/root/company-1",
                claimed_at=RECORDED_AT,
                cycle_id=CYCLE,
            ),
            lambda: release_rapid_triage_task(
                root=root,
                agent="/root/company-1",
                symbol="CN:000001",
                failure_reason="simulated",
                released_at=RECORDED_AT,
            ),
            lambda: record_rapid_triage_package(
                {},
                root=root,
                recorded_at=RECORDED_AT,
            ),
            lambda: finalize_rapid_triage_cycle(
                root=root,
                cycle_id=CYCLE,
                policy=_policy(),
                decisions={},
                finalized_at=RECORDED_AT,
            ),
        ]
        for call in calls:
            with pytest.raises(CoverageValidationError, match="coverage state is busy"):
                call()

    claimed = claim_rapid_triage_task(
        root=root,
        agent="/root/company-1",
        claimed_at=RECORDED_AT,
        cycle_id=CYCLE,
    )
    assert claimed["symbol"] == "CN:000001"


def _selection_inputs(
    root: Path,
    *,
    symbols: list[str] | None = None,
    selected_symbols: list[str] | None = None,
) -> tuple[dict, dict]:
    from trading_os.research_assets.triage_workflow import (
        build_rapid_triage_comparison_packet,
        record_rapid_triage_package,
    )

    selected = symbols or ["CN:000001"]
    names = dict(SYMBOLS)
    _freeze(root, symbols=selected)
    for index, symbol in enumerate(selected):
        record_rapid_triage_package(
            _package(symbol, names[symbol], f"/root/company-{symbol[-1]}"),
            root=root,
            recorded_at=RECORDED_AT + dt.timedelta(minutes=index),
        )
    comparison = build_rapid_triage_comparison_packet(
        root=root,
        cycle_id=CYCLE,
        created_at=RECORDED_AT + dt.timedelta(minutes=5),
    )
    return (
        _policy(),
        _decision_package(
            comparison["comparison_sha256"],
            selected,
            selected_symbols=selected_symbols,
        ),
    )


def test_freeze_is_stable_sealed_idempotent_and_conflicts_fail(tmp_path: Path):
    from trading_os.research_assets.coverage_store import read_jsonl
    from trading_os.research_assets.research_allocation import ResearchAllocationError
    from trading_os.research_assets.sealing import verify_sealed
    from trading_os.research_assets.triage_cohort import freeze_rapid_triage_cohort
    from trading_os.research_assets.triage_workflow import rapid_triage_cycle_status

    root = _coverage(tmp_path)
    first = freeze_rapid_triage_cohort(
        root=root,
        cycle_id=CYCLE,
        frozen_at=RECORDED_AT,
        queue_status="requires_rebaseline",
        limit=2,
        after_symbol="CN:000001",
    )
    assert first["symbols"] == ["CN:000002", "CN:000003"]
    assert first["idempotent"] is False
    assert verify_sealed(tmp_path / first["cohort_path"]).sha256 == first["cohort_sha256"]
    queue = {item["symbol"]: item for item in read_jsonl(root / "research_queue.jsonl")}
    assert queue["CN:000001"]["status"] == "requires_rebaseline"
    assert queue["CN:000002"]["preceding_stage"] == "coverage_refresh"
    assert "selected_by" not in queue["CN:000002"]
    assert queue["CN:000002"]["priority"] == queue["CN:000003"]["priority"] == 3
    status = rapid_triage_cycle_status(root=root, cycle_id=CYCLE)
    assert status["cohort_count"] == 2
    assert status["recorded_count"] == 0
    assert status["remaining_count"] == 2

    repeated = freeze_rapid_triage_cohort(
        root=root,
        cycle_id=CYCLE,
        frozen_at=RECORDED_AT + dt.timedelta(minutes=1),
        queue_status="requires_rebaseline",
        limit=2,
        after_symbol="CN:000001",
    )
    assert repeated["idempotent"] is True
    assert repeated["materialized_count"] == 0
    with pytest.raises(ResearchAllocationError, match="conflicts"):
        freeze_rapid_triage_cohort(
            root=root,
            cycle_id=CYCLE,
            frozen_at=RECORDED_AT,
            queue_status="requires_rebaseline",
            symbols=["CN:000002"],
        )


def test_claim_uses_cycle_and_does_not_require_selected_by(tmp_path: Path):
    from trading_os.research_assets.research_allocation import ResearchAllocationError
    from trading_os.research_assets.triage_workflow import (
        claim_rapid_triage_task,
        release_rapid_triage_task,
    )

    root = _coverage(tmp_path)
    _freeze(root, symbols=["CN:000001"])
    with pytest.raises(ResearchAllocationError, match="no eligible"):
        claim_rapid_triage_task(
            root=root,
            agent="/root/company-1",
            cycle_id="wrong-cycle",
            claimed_at=RECORDED_AT,
        )
    claimed = claim_rapid_triage_task(
        root=root,
        agent="/root/company-1",
        cycle_id=CYCLE,
        claimed_at=RECORDED_AT,
    )
    assert claimed["symbol"] == "CN:000001"
    assert claimed["selected_by"] == []
    assert claimed["cohort_sha256"]
    assert (
        claim_rapid_triage_task(
            root=root,
            agent="/root/company-1",
            cycle_id=CYCLE,
            claimed_at=RECORDED_AT,
        )["idempotent"]
        is True
    )
    assert (
        release_rapid_triage_task(
            root=root,
            agent="/root/company-1",
            symbol="CN:000001",
            failure_reason="temporary tool failure",
            released_at=RECORDED_AT + dt.timedelta(minutes=1),
        )["attempt_count"]
        == 1
    )


def test_v2_contract_and_wrong_cycle_are_rejected_before_completion(tmp_path: Path):
    from trading_os.research_assets.coverage_store import read_jsonl
    from trading_os.research_assets.research_allocation import ResearchAllocationError
    from trading_os.research_assets.triage_workflow import record_rapid_triage_package

    root = _coverage(tmp_path)
    _freeze(root, symbols=["CN:000001"])
    wrong = _package("CN:000001", "公司一", "/root/company-1", cycle_id="wrong-cycle")
    with pytest.raises(ResearchAllocationError, match="another cycle"):
        record_rapid_triage_package(wrong, root=root, recorded_at=RECORDED_AT)
    invalid = _package("CN:000001", "公司一", "/root/company-1")
    invalid["sources"][1]["supports"] = ["quote"]
    with pytest.raises(ResearchAllocationError, match="current_price"):
        record_rapid_triage_package(invalid, root=root, recorded_at=RECORDED_AT)
    queue = {item["symbol"]: item for item in read_jsonl(root / "research_queue.jsonl")}
    assert queue["CN:000001"]["status"] == "pending"


def test_record_replay_is_read_only_idempotent_and_conflicts_fail(tmp_path: Path):
    from trading_os.research_assets.company import validate_company_dir
    from trading_os.research_assets.coverage_store import read_jsonl
    from trading_os.research_assets.research_allocation import ResearchAllocationError
    from trading_os.research_assets.triage_workflow import record_rapid_triage_package

    root = _coverage(tmp_path)
    _freeze(root, symbols=["CN:000001"])
    package = _package("CN:000001", "公司一", "/root/company-1")
    first = record_rapid_triage_package(
        package,
        root=root,
        recorded_at=RECORDED_AT,
    )
    assert first["idempotent"] is False

    queue_before = read_jsonl(root / "research_queue.jsonl")
    screening_before = read_jsonl(root / "screening.jsonl")
    meta_before = validate_company_dir(tmp_path / "research" / "companies" / "CN" / "000001")
    triage_history_before = [
        item for item in queue_before[0]["stage_history"] if item.get("stage") == "rapid_triage"
    ]
    report_history_before = list(meta_before["reports"]["history"])

    repeated = record_rapid_triage_package(
        package,
        root=root,
        recorded_at=RECORDED_AT,
    )
    assert repeated["idempotent"] is True
    assert repeated["triage_path"] == first["triage_path"]
    assert repeated["company_timeline_report_path"] == first["company_timeline_report_path"]

    queue_after = read_jsonl(root / "research_queue.jsonl")
    screening_after = read_jsonl(root / "screening.jsonl")
    meta_after = validate_company_dir(tmp_path / "research" / "companies" / "CN" / "000001")
    assert queue_after == queue_before
    assert screening_after == screening_before
    assert meta_after == meta_before
    assert [
        item for item in queue_after[0]["stage_history"] if item.get("stage") == "rapid_triage"
    ] == triage_history_before
    assert meta_after["reports"]["history"] == report_history_before

    conflicting = copy.deepcopy(package)
    conflicting["change_summary"] += "但重放内容被修改。"
    with pytest.raises(ResearchAllocationError, match="conflicts with the sealed package"):
        record_rapid_triage_package(
            conflicting,
            root=root,
            recorded_at=RECORDED_AT,
        )


@pytest.mark.parametrize("seal_damage", ["missing", "corrupt"])
def test_record_replay_rejects_missing_or_corrupt_package_seal(tmp_path: Path, seal_damage: str):
    from trading_os.research_assets.coverage_store import read_jsonl
    from trading_os.research_assets.research_allocation import ResearchAllocationError
    from trading_os.research_assets.triage_workflow import record_rapid_triage_package

    root = _coverage(tmp_path)
    _freeze(root, symbols=["CN:000001"])
    package = _package("CN:000001", "公司一", "/root/company-1")
    first = record_rapid_triage_package(package, root=root, recorded_at=RECORDED_AT)
    queue_before = read_jsonl(root / "research_queue.jsonl")
    artifact_path = tmp_path / first["triage_path"]
    seal_path = artifact_path.with_name(artifact_path.name + ".seal.json")
    if seal_damage == "missing":
        seal_path.unlink()
    else:
        seal_path.write_text("{}", encoding="utf-8")

    with pytest.raises(ResearchAllocationError, match="not validly sealed"):
        record_rapid_triage_package(package, root=root, recorded_at=RECORDED_AT)
    assert read_jsonl(root / "research_queue.jsonl") == queue_before


def test_record_replay_rejects_unproven_coverage_regression(tmp_path: Path):
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.research_allocation import ResearchAllocationError
    from trading_os.research_assets.triage_workflow import record_rapid_triage_package

    root = _coverage(tmp_path)
    symbol, name = SYMBOLS[0]
    _freeze(root, symbols=[symbol])
    package = _package(symbol, name, "/root/company-1")
    record_rapid_triage_package(package, root=root, recorded_at=RECORDED_AT)
    queue = read_jsonl(root / "research_queue.jsonl")
    queue[0].update(
        {
            "task_type": "initial_research",
            "status": "requires_rebaseline",
            "assigned_agent": None,
            "started_at": None,
        }
    )
    write_jsonl(root / "research_queue.jsonl", queue)

    with pytest.raises(ResearchAllocationError, match="unexpected coverage state"):
        record_rapid_triage_package(package, root=root, recorded_at=RECORDED_AT)


def test_record_replay_after_profile_promotion_preserves_queue_state(tmp_path: Path):
    from trading_os.research_assets.company import validate_company_dir
    from trading_os.research_assets.coverage_store import read_jsonl
    from trading_os.research_assets.triage_workflow import (
        build_rapid_triage_comparison_packet,
        finalize_rapid_triage_cycle,
        record_rapid_triage_package,
    )

    root = _coverage(tmp_path)
    _freeze(root, symbols=["CN:000001"])
    package = _package("CN:000001", "公司一", "/root/company-1")
    record_rapid_triage_package(package, root=root, recorded_at=RECORDED_AT)
    comparison = build_rapid_triage_comparison_packet(
        root=root,
        cycle_id=CYCLE,
        created_at=RECORDED_AT + dt.timedelta(minutes=5),
    )
    finalize_rapid_triage_cycle(
        root=root,
        cycle_id=CYCLE,
        policy=_policy(),
        decisions=_decision_package(
            comparison["comparison_sha256"],
            ["CN:000001"],
            selected_symbols=["CN:000001"],
        ),
        finalized_at=RECORDED_AT + dt.timedelta(minutes=10),
    )
    queue_before = read_jsonl(root / "research_queue.jsonl")
    screening_before = read_jsonl(root / "screening.jsonl")
    meta_before = validate_company_dir(tmp_path / "research" / "companies" / "CN" / "000001")
    assert queue_before[0]["task_type"] == "quick_profile"
    assert queue_before[0]["status"] == "pending"

    repeated = record_rapid_triage_package(package, root=root, recorded_at=RECORDED_AT)
    assert repeated["idempotent"] is True
    assert repeated["awaiting_cohort_comparison"] is False
    assert read_jsonl(root / "research_queue.jsonl") == queue_before
    assert read_jsonl(root / "screening.jsonl") == screening_before
    assert (
        validate_company_dir(tmp_path / "research" / "companies" / "CN" / "000001") == meta_before
    )


def test_incomplete_cohort_cannot_compare_or_finalize(tmp_path: Path):
    from trading_os.research_assets.research_allocation import ResearchAllocationError
    from trading_os.research_assets.triage_workflow import (
        build_rapid_triage_comparison_packet,
        finalize_rapid_triage_cycle,
        record_rapid_triage_package,
    )

    root = _coverage(tmp_path)
    _freeze(root)
    record_rapid_triage_package(
        _package("CN:000001", "公司一", "/root/company-1"),
        root=root,
        recorded_at=RECORDED_AT,
    )
    with pytest.raises(ResearchAllocationError, match="cohort is incomplete"):
        build_rapid_triage_comparison_packet(
            root=root, cycle_id=CYCLE, created_at=RECORDED_AT + dt.timedelta(minutes=1)
        )
    with pytest.raises(ResearchAllocationError, match="cohort is incomplete"):
        finalize_rapid_triage_cycle(
            root=root,
            cycle_id=CYCLE,
            policy=_policy(),
            decisions={},
            finalized_at=RECORDED_AT + dt.timedelta(minutes=1),
        )


def test_agent_decisions_not_mechanical_scores_control_profile_budget(tmp_path: Path):
    from trading_os.research_assets.company import validate_company_dir
    from trading_os.research_assets.coverage_store import (
        read_jsonl,
        validate_coverage_root,
    )
    from trading_os.research_assets.research_allocation import ResearchAllocationError
    from trading_os.research_assets.triage_workflow import (
        build_rapid_triage_comparison_packet,
        finalize_rapid_triage_cycle,
        rapid_triage_cycle_status,
        record_rapid_triage_package,
    )

    root = _coverage(tmp_path)
    _freeze(root)
    packages = [
        _package("CN:000001", "公司一", "/root/company-1"),
        _package(
            "CN:000002",
            "公司二",
            "/root/company-2",
            research_value="high",
            valuation_signal="attractive",
        ),
        _package(
            "CN:000003",
            "公司三",
            "/root/company-3",
            valuation_signal="unattractive",
            triggers=[
                {
                    "trigger_id": "price-reset",
                    "type": "price",
                    "condition": {"operator": "price_lte", "threshold": 8.0},
                    "reason": "价格下降后重新获得研究赔率。",
                }
            ],
        ),
    ]
    for index, package in enumerate(packages):
        result = record_rapid_triage_package(
            package,
            root=root,
            recorded_at=RECORDED_AT + dt.timedelta(minutes=index),
        )
        assert result["company_timeline_report_path"].endswith(".md")

    company_meta = validate_company_dir(tmp_path / "research" / "companies" / "CN" / "000001")
    assert company_meta["research"]["rebaseline_required"] is False
    comparison = build_rapid_triage_comparison_packet(
        root=root,
        cycle_id=CYCLE,
        created_at=RECORDED_AT + dt.timedelta(minutes=5),
    )
    packet = json.loads((tmp_path / comparison["comparison_path"]).read_text(encoding="utf-8"))
    assert [row["symbol"] for row in packet["rows"]] == [item[0] for item in SYMBOLS]
    assert all("comparison_score" not in row and "rank" not in row for row in packet["rows"])
    comparison_symbols = [row["symbol"] for row in packet["rows"]]
    eligible = [row["symbol"] for row in packet["rows"] if row["eligible_for_quick_profile"]]
    assert eligible == ["CN:000001", "CN:000002"]
    decisions = _decision_package(
        comparison["comparison_sha256"],
        comparison_symbols,
        selected_symbols=["CN:000003"],
    )
    missing = copy.deepcopy(decisions)
    missing["decisions"].pop()
    with pytest.raises(ResearchAllocationError, match="cover every comparison row"):
        finalize_rapid_triage_cycle(
            root=root,
            cycle_id=CYCLE,
            policy=_policy(),
            decisions=missing,
            finalized_at=RECORDED_AT + dt.timedelta(minutes=10),
        )

    missing_reason = copy.deepcopy(decisions)
    missing_reason["decisions"][0]["reason"] = " "
    with pytest.raises(ResearchAllocationError, match="decision.reason"):
        finalize_rapid_triage_cycle(
            root=root,
            cycle_id=CYCLE,
            policy=_policy(),
            decisions=missing_reason,
            finalized_at=RECORDED_AT + dt.timedelta(minutes=10),
        )

    policy = copy.deepcopy(_policy())
    policy["quick_profile_capacity_per_cycle"] = 1
    over_capacity = _decision_package(
        comparison["comparison_sha256"],
        comparison_symbols,
        selected_symbols=["CN:000001", "CN:000003"],
    )
    with pytest.raises(ResearchAllocationError, match="exceed quick-profile capacity"):
        finalize_rapid_triage_cycle(
            root=root,
            cycle_id=CYCLE,
            policy=policy,
            decisions=over_capacity,
            finalized_at=RECORDED_AT + dt.timedelta(minutes=10),
        )
    cluster_limited_policy = copy.deepcopy(_policy())
    cluster_limited_policy["risk_cluster_caps"]["quick_profile"] = 1
    with pytest.raises(ResearchAllocationError, match="unclassified risk-cluster cap"):
        finalize_rapid_triage_cycle(
            root=root,
            cycle_id=CYCLE,
            policy=cluster_limited_policy,
            decisions=over_capacity,
            finalized_at=RECORDED_AT + dt.timedelta(minutes=10),
        )
    result = finalize_rapid_triage_cycle(
        root=root,
        cycle_id=CYCLE,
        policy=policy,
        decisions=decisions,
        finalized_at=RECORDED_AT + dt.timedelta(minutes=10),
    )
    assert result["selected_symbols"] == ["CN:000003"]
    assert result["reviewed_count"] == 3
    selection = json.loads((tmp_path / result["selection_path"]).read_text(encoding="utf-8"))
    assert selection["reviewed_count"] == 3
    assert selection["risk_cluster_mode"] == "conservative_unclassified"
    assert selection["quick_profile_risk_cluster_cap"] == 10
    assert [row["symbol"] for row in selection["decisions"]] == comparison_symbols
    queue = {item["symbol"]: item for item in read_jsonl(root / "research_queue.jsonl")}
    assert queue["CN:000001"]["task_type"] == "rapid_triage"
    assert queue["CN:000001"]["triage_allocation_decision"] == "defer"
    assert queue["CN:000002"]["task_type"] == "rapid_triage"
    assert queue["CN:000002"]["triage_allocation_decision"] == "defer"
    assert queue["CN:000003"]["task_type"] == "quick_profile"
    assert queue["CN:000003"]["triage_allocation_decision"] == "select_quick_profile"
    repeated = finalize_rapid_triage_cycle(
        root=root,
        cycle_id=CYCLE,
        policy=policy,
        decisions=decisions,
        finalized_at=RECORDED_AT + dt.timedelta(minutes=11),
    )
    assert repeated["idempotent"] is True
    conflicting = copy.deepcopy(decisions)
    conflicting["decisions"][-1]["decision"] = "defer"
    with pytest.raises(ResearchAllocationError, match="conflicts"):
        finalize_rapid_triage_cycle(
            root=root,
            cycle_id=CYCLE,
            policy=policy,
            decisions=conflicting,
            finalized_at=RECORDED_AT + dt.timedelta(minutes=11),
        )
    status = rapid_triage_cycle_status(root=root, cycle_id=CYCLE)
    assert status["recorded_count"] == 3
    assert status["remaining_count"] == 0
    assert status["comparison_ready"] is True
    assert status["selection_finalized"] is True
    assert status["audit_status"] == "completed_full_cross_company_review"
    validate_coverage_root(root)


def test_finalize_recovers_when_selection_sealed_before_coverage_writes(
    tmp_path: Path, monkeypatch
):
    import trading_os.research_assets.triage_workflow as workflow
    from trading_os.research_assets.coverage_store import read_jsonl
    from trading_os.research_assets.sealing import verify_sealed

    root = _coverage(tmp_path)
    policy, decisions = _selection_inputs(
        root,
        selected_symbols=["CN:000001"],
    )
    screening_before = read_jsonl(root / "screening.jsonl")
    queue_before = read_jsonl(root / "research_queue.jsonl")
    original_write = workflow.write_jsonl

    def crash_before_write(*args, **kwargs):
        raise RuntimeError("simulated crash before coverage materialization")

    monkeypatch.setattr(workflow, "write_jsonl", crash_before_write)
    with pytest.raises(RuntimeError, match="simulated crash"):
        workflow.finalize_rapid_triage_cycle(
            root=root,
            cycle_id=CYCLE,
            policy=policy,
            decisions=decisions,
            finalized_at=RECORDED_AT + dt.timedelta(minutes=10),
        )

    selection_path = root / "triage" / CYCLE / "selection.json"
    assert verify_sealed(selection_path).artifact_type == ("rapid_triage_cross_company_selection")
    assert read_jsonl(root / "screening.jsonl") == screening_before
    assert read_jsonl(root / "research_queue.jsonl") == queue_before

    monkeypatch.setattr(workflow, "write_jsonl", original_write)
    recovered = workflow.finalize_rapid_triage_cycle(
        root=root,
        cycle_id=CYCLE,
        policy=policy,
        decisions=decisions,
        finalized_at=RECORDED_AT + dt.timedelta(minutes=11),
    )
    assert recovered["idempotent"] is True
    screening = read_jsonl(root / "screening.jsonl")[0]
    queue = read_jsonl(root / "research_queue.jsonl")[0]
    assert screening["decision"] == "quick_profile"
    assert queue["task_type"] == "quick_profile"
    assert queue["status"] == "pending"
    assert queue["triage_selection_path"] == recovered["selection_path"]


def test_finalize_recovers_when_only_screening_was_materialized(tmp_path: Path, monkeypatch):
    import trading_os.research_assets.triage_workflow as workflow
    from trading_os.research_assets.coverage_store import read_jsonl

    root = _coverage(tmp_path)
    policy, decisions = _selection_inputs(
        root,
        selected_symbols=["CN:000001"],
    )
    queue_before = read_jsonl(root / "research_queue.jsonl")
    original_write = workflow.write_jsonl
    write_count = 0

    def crash_before_queue(path, records, sort_key="symbol"):
        nonlocal write_count
        write_count += 1
        if write_count == 2:
            raise RuntimeError("simulated crash before queue materialization")
        return original_write(path, records, sort_key)

    monkeypatch.setattr(workflow, "write_jsonl", crash_before_queue)
    with pytest.raises(RuntimeError, match="simulated crash"):
        workflow.finalize_rapid_triage_cycle(
            root=root,
            cycle_id=CYCLE,
            policy=policy,
            decisions=decisions,
            finalized_at=RECORDED_AT + dt.timedelta(minutes=10),
        )

    screening_after_crash = read_jsonl(root / "screening.jsonl")
    assert screening_after_crash[0]["decision"] == "quick_profile"
    assert read_jsonl(root / "research_queue.jsonl") == queue_before

    monkeypatch.setattr(workflow, "write_jsonl", original_write)
    recovered = workflow.finalize_rapid_triage_cycle(
        root=root,
        cycle_id=CYCLE,
        policy=policy,
        decisions=decisions,
        finalized_at=RECORDED_AT + dt.timedelta(minutes=11),
    )
    assert recovered["idempotent"] is True
    assert read_jsonl(root / "screening.jsonl") == screening_after_crash
    queue = read_jsonl(root / "research_queue.jsonl")[0]
    assert queue["task_type"] == "quick_profile"
    assert queue["status"] == "pending"
    assert queue["triage_allocation_decision"] == "select_quick_profile"


def test_finalize_replay_never_regresses_valid_quick_profile_progress(tmp_path: Path):
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.triage_workflow import finalize_rapid_triage_cycle

    root = _coverage(tmp_path)
    policy, decisions = _selection_inputs(
        root,
        selected_symbols=["CN:000001"],
    )
    finalize_rapid_triage_cycle(
        root=root,
        cycle_id=CYCLE,
        policy=policy,
        decisions=decisions,
        finalized_at=RECORDED_AT + dt.timedelta(minutes=10),
    )

    queue = read_jsonl(root / "research_queue.jsonl")
    queue[0].update(
        {
            "status": "running",
            "assigned_agent": "/root/profile-agent",
            "started_at": (RECORDED_AT + dt.timedelta(minutes=11)).isoformat(),
        }
    )
    write_jsonl(root / "research_queue.jsonl", queue)
    running_queue = read_jsonl(root / "research_queue.jsonl")
    running_screening = read_jsonl(root / "screening.jsonl")
    assert (
        finalize_rapid_triage_cycle(
            root=root,
            cycle_id=CYCLE,
            policy=policy,
            decisions=decisions,
            finalized_at=RECORDED_AT + dt.timedelta(minutes=12),
        )["idempotent"]
        is True
    )
    assert read_jsonl(root / "research_queue.jsonl") == running_queue
    assert read_jsonl(root / "screening.jsonl") == running_screening

    queue = read_jsonl(root / "research_queue.jsonl")
    queue[0].update(
        {
            "status": "completed",
            "finished_at": (RECORDED_AT + dt.timedelta(minutes=13)).isoformat(),
            "result_path": "coverage/cn-a/profiles/test/profile.evaluation.json",
        }
    )
    queue[0]["stage_history"].append(
        {
            "stage": "quick_profile",
            "status": "completed",
            "finished_at": queue[0]["finished_at"],
            "agent": "/root/profile-agent",
            "result_path": "coverage/cn-a/profiles/test/profile.json",
            "evaluation_path": queue[0]["result_path"],
            "next_stage": "profile_candidate",
        }
    )
    screening = read_jsonl(root / "screening.jsonl")
    screening[0].update(
        {
            "decision": "profile_candidate",
            "reason": "快速画像已完成，等待横向比较。",
            "evidence": ["profile:coverage/cn-a/profiles/test/profile.json"],
            "next_action": "等待画像批次比较。",
        }
    )
    write_jsonl(root / "screening.jsonl", screening)
    write_jsonl(root / "research_queue.jsonl", queue)
    completed_queue = read_jsonl(root / "research_queue.jsonl")
    completed_screening = read_jsonl(root / "screening.jsonl")
    finalize_rapid_triage_cycle(
        root=root,
        cycle_id=CYCLE,
        policy=policy,
        decisions=decisions,
        finalized_at=RECORDED_AT + dt.timedelta(minutes=14),
    )
    assert read_jsonl(root / "research_queue.jsonl") == completed_queue
    assert read_jsonl(root / "screening.jsonl") == completed_screening

    queue = read_jsonl(root / "research_queue.jsonl")
    queue[0].update(
        {
            "task_type": "scoped_research",
            "status": "running",
            "assigned_agent": "/root/scoped-agent",
            "started_at": (RECORDED_AT + dt.timedelta(minutes=15)).isoformat(),
            "finished_at": None,
            "preceding_stage": "quick_profile",
        }
    )
    screening = read_jsonl(root / "screening.jsonl")
    screening[0].update(
        {
            "decision": "scoped_research",
            "reason": "已获得下一层研究预算。",
            "next_action": "完成范围研究。",
        }
    )
    write_jsonl(root / "screening.jsonl", screening)
    write_jsonl(root / "research_queue.jsonl", queue)
    deeper_queue = read_jsonl(root / "research_queue.jsonl")
    deeper_screening = read_jsonl(root / "screening.jsonl")
    finalize_rapid_triage_cycle(
        root=root,
        cycle_id=CYCLE,
        policy=policy,
        decisions=decisions,
        finalized_at=RECORDED_AT + dt.timedelta(minutes=16),
    )
    assert read_jsonl(root / "research_queue.jsonl") == deeper_queue
    assert read_jsonl(root / "screening.jsonl") == deeper_screening


def test_finalized_terminal_company_can_enter_a_new_trigger_cycle(tmp_path: Path):
    from trading_os.research_assets.coverage_store import read_jsonl
    from trading_os.research_assets.triage_cohort import freeze_rapid_triage_cohort
    from trading_os.research_assets.triage_workflow import (
        build_rapid_triage_comparison_packet,
        finalize_rapid_triage_cycle,
        rapid_triage_cycle_status,
        record_rapid_triage_package,
    )

    root = _coverage(tmp_path)
    _freeze(root, symbols=["CN:000001"])
    record_rapid_triage_package(
        _package(
            "CN:000001",
            "公司一",
            "/root/company-1",
            valuation_signal="unattractive",
        ),
        root=root,
        recorded_at=RECORDED_AT,
    )
    comparison = build_rapid_triage_comparison_packet(
        root=root,
        cycle_id=CYCLE,
        created_at=RECORDED_AT + dt.timedelta(minutes=5),
    )
    finalize_rapid_triage_cycle(
        root=root,
        cycle_id=CYCLE,
        policy=_policy(),
        decisions=_decision_package(
            comparison["comparison_sha256"], ["CN:000001"], selected_symbols=[]
        ),
        finalized_at=RECORDED_AT + dt.timedelta(minutes=10),
    )

    second_cycle = "2026-08-27-trigger-test"
    freeze_rapid_triage_cohort(
        root=root,
        cycle_id=second_cycle,
        frozen_at=RECORDED_AT + dt.timedelta(days=31),
        queue_status="completed",
        symbols=["CN:000001"],
    )

    queue = {item["symbol"]: item for item in read_jsonl(root / "research_queue.jsonl")}
    current = queue["CN:000001"]
    assert current["status"] == "pending"
    assert current["triage_cycle_id"] == second_cycle
    assert "triage_selection_path" not in current
    assert any(
        item.get("replaces_cycle_id") == CYCLE
        for item in current["stage_history"]
        if item.get("stage") == "coverage_refresh"
    )
    old_status = rapid_triage_cycle_status(root=root, cycle_id=CYCLE)
    assert old_status["recorded_count"] == 1
    assert old_status["remaining_count"] == 0
    new_status = rapid_triage_cycle_status(root=root, cycle_id=second_cycle)
    assert new_status["recorded_count"] == 0
    assert new_status["remaining_count"] == 1


def test_record_replay_of_older_package_survives_a_later_triage_cycle(
    tmp_path: Path,
):
    from trading_os.research_assets.coverage_store import read_jsonl
    from trading_os.research_assets.triage_cohort import freeze_rapid_triage_cohort
    from trading_os.research_assets.triage_workflow import (
        build_rapid_triage_comparison_packet,
        finalize_rapid_triage_cycle,
        record_rapid_triage_package,
    )

    root = _coverage(tmp_path)
    symbol, name = SYMBOLS[0]
    _freeze(root, symbols=[symbol])
    first_package = _package(
        symbol,
        name,
        "/root/company-1",
        valuation_signal="unattractive",
    )
    first_result = record_rapid_triage_package(
        first_package,
        root=root,
        recorded_at=RECORDED_AT,
    )
    comparison = build_rapid_triage_comparison_packet(
        root=root,
        cycle_id=CYCLE,
        created_at=RECORDED_AT + dt.timedelta(minutes=5),
    )
    finalize_rapid_triage_cycle(
        root=root,
        cycle_id=CYCLE,
        policy=_policy(),
        decisions=_decision_package(
            comparison["comparison_sha256"], [symbol], selected_symbols=[]
        ),
        finalized_at=RECORDED_AT + dt.timedelta(minutes=10),
    )

    second_cycle = "2026-08-27-replay-test"
    freeze_rapid_triage_cohort(
        root=root,
        cycle_id=second_cycle,
        frozen_at=RECORDED_AT + dt.timedelta(days=31),
        queue_status="completed",
        symbols=[symbol],
    )
    second_package = _package(
        symbol,
        name,
        "/root/company-2",
        cycle_id=second_cycle,
        research_value="high",
    )
    second_package.update(
        {
            "as_of": "2026-08-27",
            "information_cutoff": "2026-08-27T09:30:00+08:00",
            "price_as_of": "2026-08-27T09:25:00+08:00",
        }
    )
    second_package["provenance"]["generated_at"] = "2026-08-27T09:45:00+08:00"
    second_result = record_rapid_triage_package(
        second_package,
        root=root,
        recorded_at=RECORDED_AT + dt.timedelta(days=31, minutes=1),
    )
    queue_before_replay = read_jsonl(root / "research_queue.jsonl")
    screening_before_replay = read_jsonl(root / "screening.jsonl")
    meta_path = tmp_path / "research" / "companies" / "CN" / symbol[-6:] / "meta.json"
    meta_before_replay = meta_path.read_bytes()

    repeated_first = record_rapid_triage_package(
        first_package,
        root=root,
        recorded_at=RECORDED_AT,
    )

    assert repeated_first["idempotent"] is True
    assert repeated_first["company_timeline_report_path"] == first_result[
        "company_timeline_report_path"
    ]
    assert repeated_first["awaiting_cohort_comparison"] is False
    assert second_result["company_timeline_report_path"] != first_result[
        "company_timeline_report_path"
    ]
    assert read_jsonl(root / "research_queue.jsonl") == queue_before_replay
    assert read_jsonl(root / "screening.jsonl") == screening_before_replay
    assert meta_path.read_bytes() == meta_before_replay


def test_legacy_allocation_binding_remains_usable_with_v2_results(tmp_path: Path):
    from trading_os.research_assets.coverage_store import read_jsonl
    from trading_os.research_assets.triage_workflow import (
        build_rapid_triage_comparison_packet,
        finalize_rapid_triage_cycle,
        record_rapid_triage_package,
    )

    root = _coverage(tmp_path, legacy_allocation=True)
    packages = {}
    recorded_results = {}
    for index, (symbol, name) in enumerate(SYMBOLS):
        package = _package(symbol, name, f"/root/legacy-{index}")
        packages[symbol] = package
        recorded_results[symbol] = record_rapid_triage_package(
            package,
            root=root,
            recorded_at=RECORDED_AT + dt.timedelta(minutes=index),
        )
    comparison = build_rapid_triage_comparison_packet(
        root=root,
        cycle_id=CYCLE,
        created_at=RECORDED_AT + dt.timedelta(minutes=5),
    )
    packet = json.loads(
        (tmp_path / comparison["comparison_path"]).read_text(encoding="utf-8")
    )
    assert packet["binding_type"] == "legacy_allocation"
    assert packet["cohort_count"] == 3

    selected_symbol = SYMBOLS[0][0]
    finalize_rapid_triage_cycle(
        root=root,
        cycle_id=CYCLE,
        policy=_policy(),
        decisions=_decision_package(
            comparison["comparison_sha256"],
            [symbol for symbol, _ in SYMBOLS],
            selected_symbols=[selected_symbol],
        ),
        finalized_at=RECORDED_AT + dt.timedelta(minutes=10),
    )
    selected_queue = {
        item["symbol"]: item for item in read_jsonl(root / "research_queue.jsonl")
    }[selected_symbol]
    assert selected_queue["task_type"] == "quick_profile"
    assert selected_queue["status"] == "pending"

    queue_before_replay = (root / "research_queue.jsonl").read_bytes()
    screening_before_replay = (root / "screening.jsonl").read_bytes()
    meta_path = (
        tmp_path / "research" / "companies" / "CN" / selected_symbol[-6:] / "meta.json"
    )
    meta_before_replay = meta_path.read_bytes()

    replayed = record_rapid_triage_package(
        packages[selected_symbol],
        root=root,
        recorded_at=RECORDED_AT,
    )

    assert replayed["idempotent"] is True
    assert replayed["company_timeline_report_path"] == recorded_results[selected_symbol][
        "company_timeline_report_path"
    ]
    assert (root / "research_queue.jsonl").read_bytes() == queue_before_replay
    assert (root / "screening.jsonl").read_bytes() == screening_before_replay
    assert meta_path.read_bytes() == meta_before_replay


def test_cli_freezes_explicit_symbol_file(tmp_path: Path, capsys):
    from trading_os.cli import main

    root = _coverage(tmp_path)
    symbols_path = tmp_path / "symbols.json"
    symbols_path.write_text(json.dumps({"symbols": ["CN:000003", "CN:000001"]}), encoding="utf-8")
    assert (
        main(
            [
                "coverage",
                "triage-freeze",
                CYCLE,
                "--root",
                str(root),
                "--symbols-file",
                str(symbols_path),
                "--at",
                RECORDED_AT.isoformat(),
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["symbols"] == ["CN:000001", "CN:000003"]
    assert payload["cohort_count"] == 2


def test_record_replay_repairs_trigger_consumption_after_publish_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from trading_os.research_assets import triage_workflow
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.trigger_hits import (
        observe_fact_hit,
        verify_trigger_hit_ledger,
    )

    root = _coverage(tmp_path)
    _freeze(root, symbols=["CN:000001"])
    source_sha = "a" * 64
    occurrence_sha = "b" * 64
    observed = observe_fact_hit(
        root=root,
        observation={
            "schema_version": 1,
            "symbol": "CN:000001",
            "workflow_target": "company_research",
            "trigger_ref": {
                "trigger_id": "filing-update",
                "type": "filing",
                "source_kind": "company_trigger",
                "definition_ref": "research/companies/CN/000001/meta.json",
                "definition_source_sha256": source_sha,
                "definition": {"condition": {"filing": "annual_report"}},
            },
            "effective_at": "2026-07-27T07:00:00+08:00",
            "observed_at": "2026-07-27T08:00:00+08:00",
            "occurrence_evidence": {
                "kind": "filing",
                "occurrence_key": "annual-report-2026",
                "source_id": "annual-report-2026",
                "source_ref": "https://example.test/annual-report",
                "source_sha256": occurrence_sha,
                "published_at": "2026-07-27T07:00:00+08:00",
            },
            "actor": "filing-observer",
            "idempotency_key": "filing:annual-report-2026",
        },
        recorded_at=RECORDED_AT,
    )
    queue = read_jsonl(root / "research_queue.jsonl")
    queue[0]["bound_trigger_hit_ids"] = [observed["hit_id"]]
    write_jsonl(root / "research_queue.jsonl", queue)
    package = _package("CN:000001", "公司一", "/root/company-1")
    package["review_mode"] = "triggered_update"
    package["handled_hit_ids"] = [observed["hit_id"]]

    real_consume = triage_workflow.consume_trigger_hits

    def fail_after_publish(**kwargs):
        raise RuntimeError("injected ledger append failure")

    monkeypatch.setattr(triage_workflow, "consume_trigger_hits", fail_after_publish)
    with pytest.raises(RuntimeError, match="injected ledger append"):
        triage_workflow.record_rapid_triage_package(
            package, root=root, recorded_at=RECORDED_AT
        )
    assert verify_trigger_hit_ledger(root=root)["open_hit_count"] == 1

    monkeypatch.setattr(triage_workflow, "consume_trigger_hits", real_consume)
    repaired = triage_workflow.record_rapid_triage_package(
        package, root=root, recorded_at=RECORDED_AT
    )
    assert repaired["idempotent"] is True
    assert repaired["trigger_consumption"]["newly_consumed_count"] == 1
    assert verify_trigger_hit_ledger(root=root)["open_hit_count"] == 0
