from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
from pathlib import Path

import pytest

RUN_ID = "2026-07-31-quote-impact-test"
BATCH_ID = "batch-001"
REVIEW_ID = "review-001"
CUTOFF = dt.datetime.fromisoformat("2026-07-31T08:00:00+08:00")
MANAGER = {
    "agent": "/root/investment-manager",
    "model": "gpt-test",
    "tools": ["packet_read"],
}


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _write_policy(
    path: Path,
    *,
    capacity: int = 2,
    decision_contract_version: int = 1,
) -> Path:
    policy = {
        "schema_version": 2,
        "policy_id": "manager-screening.quote-impact-test",
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
            "send_to_analyst_capacity_per_run": capacity,
            "quote_amendment_review_absolute_price_change_pct": 20.0,
            "quick_profile_effort_budget_hours": 1.5,
            "quick_profile_stop_conditions": ["证据不足时停止。"],
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
            "principles": {"same_manager_per_batch": True},
        },
    }
    if decision_contract_version in {2, 3}:
        policy["payload"].update(
            {
                "decision_contract_version": decision_contract_version,
                "mandatory_risk_acknowledgement": True,
                "canonical_fact_line_required": True,
                "high_liability_to_assets_pct": 70.0,
                "one_line_reason_max_chars": 2000,
            }
        )
        if decision_contract_version == 3:
            policy["payload"].update(
                {
                    "routes": ["pass", "watch", "research_candidate"],
                    "research_candidate_requires_allocation": True,
                }
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(policy, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def _company(ticker: str, name: str, *, price: float | None) -> dict:
    return {
        "symbol": f"CN:{ticker}",
        "ticker": ticker,
        "name": name,
        "market": "CN",
        "exchange": "SZSE",
        "security_type": "common_stock",
        "listing_status": "listed",
        "as_of": "2026-07-30",
        "industry": "测试行业",
        "price": price,
        "market_cap_cny": 10_000_000_000,
        "float_market_cap_cny": 8_000_000_000,
        "pe_ttm": 10.0,
        "pb": 1.0,
        "roe": 10.0,
        "source": "fixture snapshot",
        "fetched_at": CUTOFF.isoformat(),
        "manager_screen_facts": {
            "quote_freshness": {
                "schema_version": 1,
                "status": "fresh",
                "quote_as_of": (CUTOFF - dt.timedelta(days=1)).isoformat(),
                "evaluated_at": CUTOFF.isoformat(),
                "age_seconds": 86400,
                "max_age_seconds": 259200,
                "future_tolerance_seconds": 300,
                "source": "fixture snapshot",
            }
        },
    }


def _manager_submission(
    packet: dict,
    *,
    routes: tuple[str, ...] | None = None,
) -> dict:
    decisions = []
    for index, dossier in enumerate(packet["dossiers"]):
        symbol = dossier["symbol"]
        route = (
            routes[index] if routes is not None else ("pass" if index == 0 else "send_to_analyst")
        )
        decision = {
            "symbol": symbol,
            "route": route,
            "one_line_reason": (
                "当前证据不足以购买进一步研究预算。"
                if route in {"pass", "watch"}
                else "决定性问题可在画像预算内解决。"
            ),
            "decisive_question": "正常化股东收益能否覆盖当前估值？",
            "revisit_triggers": (
                [
                    {
                        "type": "price",
                        "condition": "价格较当前下跌20%",
                        "reason": "安全边际可能改善。",
                    }
                ]
                if route in {"pass", "watch"}
                else []
            ),
            "confidence": "medium",
            "evidence_ids": [dossier["evidence_catalog"][0]["evidence_id"]],
        }
        support = (
            dossier.get("market_snapshot", {})
            .get("manager_screen_facts", {})
            .get("decision_support")
        )
        if isinstance(support, dict):
            decision["one_line_reason"] = (
                f"{support['canonical_fact_line']['text']}；当前仍需按决定性问题分配研究预算"
            )
            decision["risk_acknowledgements"] = [
                {
                    "flag_id": flag["flag_id"],
                    "assessment": "not_material",
                    "reason": "已核对该风险，暂不改变研究预算判断",
                }
                for flag in support["mandatory_risk_flags"]
            ]
        decisions.append(decision)
    return {
        "schema_version": 1,
        "manager": copy.deepcopy(MANAGER),
        "additional_evidence": [],
        "decisions": decisions,
    }


def _fixture(
    tmp_path: Path,
    *,
    first_old_price: float | None = 10.0,
    second_change_pct: float = 10.0,
    capacity: int = 2,
    original_routes: tuple[str, str] | None = None,
    decision_contract_version: int = 1,
    first_name: str = "甲公司",
    include_third_company: bool = False,
) -> dict:
    from trading_os.research_assets.manager_screen_snapshot import (
        prepare_manager_screen_quote_amendment,
    )
    from trading_os.research_assets.manager_screening import (
        freeze_manager_screen_batch,
        record_manager_screen_decisions,
    )
    from trading_os.research_assets.scope_workflow import freeze_all_a_scope

    root = tmp_path / "coverage" / "cn-a"
    policy_path = _write_policy(
        tmp_path / "policies" / "manager-screening.json",
        capacity=capacity,
        decision_contract_version=decision_contract_version,
    )
    companies = [
        _company("000001", first_name, price=first_old_price),
        _company("000002", "乙公司", price=20.0),
    ]
    if include_third_company:
        companies.append(_company("000003", "丙公司", price=30.0))
    snapshot_path = root / "snapshots" / RUN_ID / "companies.jsonl"
    _write_jsonl(snapshot_path, companies)
    _write_jsonl(root / "companies.jsonl", companies)
    _write_jsonl(
        root / "screening.jsonl",
        [
            {
                "symbol": row["symbol"],
                "name": row["name"],
                "decision": "catalog",
                "priority": None,
                "reason": "初始目录。",
                "evidence": ["fixture"],
                "next_action": "等待初筛。",
            }
            for row in companies
        ],
    )
    _write_jsonl(root / "research_queue.jsonl", [])
    _write_jsonl(root / "runs.jsonl", [])
    freeze_all_a_scope(
        root=root,
        run_id=RUN_ID,
        scope_cutoff=CUTOFF,
        frozen_at=CUTOFF,
        universe_path=snapshot_path,
    )
    frozen = freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id=BATCH_ID,
        frozen_at=CUTOFF + dt.timedelta(minutes=1),
        batch_size=2,
        policy_path=policy_path,
    )
    packet = json.loads((tmp_path / frozen["packet_path"]).read_text(encoding="utf-8"))
    if original_routes is None and decision_contract_version == 3:
        original_routes = ("pass", "research_candidate")
    recorded = record_manager_screen_decisions(
        root=root,
        run_id=RUN_ID,
        batch_id=BATCH_ID,
        submission=_manager_submission(packet, routes=original_routes),
        recorded_at=CUTOFF + dt.timedelta(minutes=2),
    )
    quote_snapshot = [
        {
            "symbol": "CN:000001",
            "price": 12.5,
            "market_cap_cny": 12_500_000_000,
            "float_market_cap_cny": 10_000_000_000,
            "as_of": (CUTOFF + dt.timedelta(minutes=3)).isoformat(),
            "source": "fixture quote amendment",
        },
        {
            "symbol": "CN:000002",
            "price": 20.0 * (1.0 + second_change_pct / 100.0),
            "market_cap_cny": 10_000_000_000 * (1.0 + second_change_pct / 100.0),
            "float_market_cap_cny": 8_000_000_000 * (1.0 + second_change_pct / 100.0),
            "as_of": (CUTOFF + dt.timedelta(minutes=3)).isoformat(),
            "source": "fixture quote amendment",
        },
    ]
    if include_third_company:
        quote_snapshot.append(
            {
                "symbol": "CN:000003",
                "price": 30.0,
                "market_cap_cny": 10_000_000_000,
                "float_market_cap_cny": 8_000_000_000,
                "as_of": (CUTOFF + dt.timedelta(minutes=3)).isoformat(),
                "source": "fixture quote amendment",
            }
        )
    amendment = prepare_manager_screen_quote_amendment(
        root=root,
        run_id=RUN_ID,
        amendment_id="quotes-002",
        effective_at=CUTOFF + dt.timedelta(minutes=3),
        quote_snapshot=quote_snapshot,
        quote_max_age=dt.timedelta(hours=1),
    )
    return {
        "root": root,
        "policy_path": policy_path,
        "packet": packet,
        "recorded": recorded,
        "amendment": amendment,
    }


def _replace_first_amendment_price(
    tmp_path: Path,
    context: dict,
    value: float | None,
) -> dict:
    from trading_os.research_assets.sealing import seal_json

    source = tmp_path / context["amendment"]["path"]
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["amendment_id"] = "quotes-invalid"
    payload["quotes"][0]["price"] = value
    target = source.with_name("quotes-invalid.json")
    sealed = seal_json(
        target,
        payload,
        artifact_type="manager_screen_quote_amendment",
        sealed_at=CUTOFF + dt.timedelta(minutes=3),
    )
    updated = dict(context)
    updated["amendment"] = {
        **context["amendment"],
        "amendment_id": "quotes-invalid",
        "path": target.relative_to(tmp_path).as_posix(),
        "sha256": sealed.sha256,
    }
    return updated


def _prepare(context: dict, *, review_id: str = REVIEW_ID) -> dict:
    from trading_os.research_assets.manager_screen_quote_impact import (
        prepare_manager_screen_quote_impact,
    )

    return prepare_manager_screen_quote_impact(
        root=context["root"],
        run_id=RUN_ID,
        batch_id=BATCH_ID,
        review_id=review_id,
        quote_amendment_path=context["amendment"]["path"],
        prepared_at=CUTOFF + dt.timedelta(minutes=4),
        policy_path=context["policy_path"],
    )


def _review_submission(packet: dict, *, actions: dict[str, str]) -> dict:
    reviews = []
    for row in packet["rows"]:
        symbol = row["symbol"]
        route = actions[symbol]
        if route == "keep":
            reviews.append(
                {
                    "symbol": symbol,
                    "action": "keep",
                    "replacement": None,
                }
            )
            continue
        replacement = copy.deepcopy(row["old_decision"])
        replacement.update(
            {
                "route": route,
                "one_line_reason": f"价格变化后完整复核，调整为{route}。",
                "decisive_question": "新价格下是否仍值得投入研究预算？",
                "revisit_triggers": (
                    []
                    if route == "send_to_analyst"
                    else [
                        {
                            "type": "price",
                            "condition": "价格再次变化20%",
                            "reason": "估值判断可能改变。",
                        }
                    ]
                ),
                "confidence": "high",
                "evidence_ids": [row["quote"]["evidence_id"]],
            }
        )
        support = row.get("decision_support")
        if isinstance(support, dict):
            replacement["one_line_reason"] = (
                f"{support['canonical_fact_line']['text']}；"
                "价格变化后已完整复核，当前路由仍由决定性问题主导"
            )
            replacement["evidence_ids"] = list(
                dict.fromkeys(
                    [
                        *row["old_decision"]["evidence_ids"],
                        row["quote"]["evidence_id"],
                    ]
                )
            )
        reviews.append(
            {
                "symbol": symbol,
                "action": "replacement",
                "replacement": replacement,
            }
        )
    return {
        "schema_version": 1,
        "manager": copy.deepcopy(MANAGER),
        "reviews": reviews,
    }


def _load_review_packet(tmp_path: Path, review_id: str = REVIEW_ID) -> dict:
    path = (
        tmp_path
        / "coverage"
        / "cn-a"
        / "manager-screen"
        / RUN_ID
        / BATCH_ID
        / "quote-impact-reviews"
        / review_id
        / "packet.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def test_prepare_selects_only_threshold_candidates_and_is_idempotent(
    tmp_path: Path,
):
    from trading_os.research_assets.coverage_store import read_jsonl

    context = _fixture(tmp_path)
    queue_before = read_jsonl(context["root"] / "research_queue.jsonl")
    screening_before = read_jsonl(context["root"] / "screening.jsonl")

    prepared = _prepare(context)
    replay = _prepare(context)
    packet = _load_review_packet(tmp_path)

    assert prepared["candidate_symbols"] == ["CN:000001"]
    assert replay["plan_sha256"] == prepared["plan_sha256"]
    assert replay["packet_sha256"] == prepared["packet_sha256"]
    assert packet["rows"][0]["old_price"] == 10.0
    assert packet["rows"][0]["new_price"] == 12.5
    assert packet["rows"][0]["price_change_pct"] == 25.0
    assert "comparison_status" not in packet["rows"][0]
    assert "candidate_reason" not in packet["rows"][0]
    assert packet["rows"][0]["old_decision"]["route"] == "pass"
    assert packet["rows"][0]["valuation"]["old"]["market_cap_cny"] == 10_000_000_000
    assert packet["rows"][0]["valuation"]["new"]["market_cap_cny"] == 12_500_000_000
    assert read_jsonl(context["root"] / "research_queue.jsonl") == queue_before
    assert read_jsonl(context["root"] / "screening.jsonl") == screening_before


def test_post_contract_v2_quote_prepare_is_frozen(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    import trading_os.research_assets.manager_screen_quote_impact as quote_impact

    context = _fixture(tmp_path, decision_contract_version=2)
    monkeypatch.setattr(
        quote_impact,
        "_allocation_v3_contract_active",
        lambda **_: True,
    )
    with pytest.raises(
        quote_impact.ManagerScreenQuoteImpactError,
        match="read-only",
    ):
        _prepare(context)


def test_post_contract_v2_quote_replay_never_rematerializes_suspended_row(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    import trading_os.research_assets.manager_screen_quote_impact as quote_impact
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl

    context = _fixture(tmp_path, decision_contract_version=2)
    _prepare(context)
    packet = _load_review_packet(tmp_path)
    submission = _review_submission(
        packet,
        actions={"CN:000001": "send_to_analyst"},
    )
    recorded = quote_impact.record_manager_screen_quote_impact(
        root=context["root"],
        run_id=RUN_ID,
        batch_id=BATCH_ID,
        review_id=REVIEW_ID,
        submission=submission,
        recorded_at=CUTOFF + dt.timedelta(minutes=5),
    )
    queue_path = context["root"] / "research_queue.jsonl"
    queue = read_jsonl(queue_path)
    row = next(item for item in queue if item["symbol"] == "CN:000001")
    row.update(
        {
            "task_type": "manager_screen",
            "status": "completed",
            "research_budget_state": "candidate_unfunded",
        }
    )
    write_jsonl(queue_path, queue)
    queue_before = queue_path.read_bytes()
    monkeypatch.setattr(
        quote_impact,
        "_allocation_v3_contract_active",
        lambda **_: True,
    )
    replayed = quote_impact.record_manager_screen_quote_impact(
        root=context["root"],
        run_id=RUN_ID,
        batch_id=BATCH_ID,
        review_id=REVIEW_ID,
        submission=submission,
        recorded_at=CUTOFF + dt.timedelta(minutes=6),
    )
    assert replayed["result_sha256"] == recorded["result_sha256"]
    assert replayed["idempotent"] is True
    assert queue_path.read_bytes() == queue_before


@pytest.mark.parametrize("old_price", [None, 0.0, -1.0])
def test_missing_or_non_positive_old_price_is_mandatory_candidate(
    tmp_path: Path,
    old_price: float | None,
):
    context = _fixture(tmp_path, first_old_price=old_price)

    prepared = _prepare(context)
    packet = _load_review_packet(tmp_path)
    row = packet["rows"][0]

    assert prepared["candidate_symbols"] == ["CN:000001"]
    assert row["old_price"] == old_price
    assert row["new_price"] == 12.5
    assert row["price_change_pct"] is None
    assert row["absolute_price_change_pct"] is None
    assert row["comparison_status"] == "not_comparable"
    assert row["candidate_reason"] == "price_not_comparable"
    assert row["invalid_price_fields"] == ["old_price"]
    assert row["requires_manual_review"] is True


@pytest.mark.parametrize("new_price", [None, 0.0, -1.0])
def test_missing_or_non_positive_new_price_is_mandatory_candidate(
    tmp_path: Path,
    new_price: float | None,
):
    context = _replace_first_amendment_price(
        tmp_path,
        _fixture(tmp_path),
        new_price,
    )

    prepared = _prepare(context)
    packet = _load_review_packet(tmp_path)
    row = packet["rows"][0]

    assert prepared["candidate_symbols"] == ["CN:000001"]
    assert row["old_price"] == 10.0
    assert row["new_price"] == new_price
    assert row["price_change_pct"] is None
    assert row["absolute_price_change_pct"] is None
    assert row["comparison_status"] == "not_comparable"
    assert row["candidate_reason"] == "price_not_comparable"
    assert row["invalid_price_fields"] == ["new_price"]
    assert row["requires_manual_review"] is True


def test_not_comparable_candidate_must_be_recorded_but_does_not_change_route(
    tmp_path: Path,
):
    from trading_os.research_assets.coverage_store import read_jsonl
    from trading_os.research_assets.manager_screen_quote_impact import (
        record_manager_screen_quote_impact,
    )

    context = _fixture(tmp_path, first_old_price=0.0)
    _prepare(context)
    packet = _load_review_packet(tmp_path)
    queue_before = read_jsonl(context["root"] / "research_queue.jsonl")
    submission = _review_submission(
        packet,
        actions={"CN:000001": "keep"},
    )

    result = record_manager_screen_quote_impact(
        root=context["root"],
        run_id=RUN_ID,
        batch_id=BATCH_ID,
        review_id=REVIEW_ID,
        submission=submission,
        recorded_at=CUTOFF + dt.timedelta(minutes=5),
    )

    assert result["keep_count"] == 1
    assert read_jsonl(context["root"] / "research_queue.jsonl") == queue_before


def test_record_keep_requires_exact_original_manager_and_complete_coverage(
    tmp_path: Path,
):
    from trading_os.research_assets.coverage_store import read_jsonl
    from trading_os.research_assets.manager_screen_quote_impact import (
        ManagerScreenQuoteImpactError,
        record_manager_screen_quote_impact,
    )

    context = _fixture(tmp_path)
    _prepare(context)
    packet = _load_review_packet(tmp_path)
    submission = _review_submission(
        packet,
        actions={"CN:000001": "keep"},
    )
    queue_before = read_jsonl(context["root"] / "research_queue.jsonl")
    screening_before = read_jsonl(context["root"] / "screening.jsonl")

    wrong_manager = copy.deepcopy(submission)
    wrong_manager["manager"]["tools"] = ["different_tool"]
    with pytest.raises(ManagerScreenQuoteImpactError, match="original investment manager"):
        record_manager_screen_quote_impact(
            root=context["root"],
            run_id=RUN_ID,
            batch_id=BATCH_ID,
            review_id=REVIEW_ID,
            submission=wrong_manager,
            recorded_at=CUTOFF + dt.timedelta(minutes=5),
        )

    incomplete = copy.deepcopy(submission)
    incomplete["reviews"] = []
    with pytest.raises(ManagerScreenQuoteImpactError, match="every candidate"):
        record_manager_screen_quote_impact(
            root=context["root"],
            run_id=RUN_ID,
            batch_id=BATCH_ID,
            review_id=REVIEW_ID,
            submission=incomplete,
            recorded_at=CUTOFF + dt.timedelta(minutes=5),
        )

    recorded = record_manager_screen_quote_impact(
        root=context["root"],
        run_id=RUN_ID,
        batch_id=BATCH_ID,
        review_id=REVIEW_ID,
        submission=submission,
        recorded_at=CUTOFF + dt.timedelta(minutes=5),
    )
    assert recorded["keep_count"] == 1
    assert read_jsonl(context["root"] / "research_queue.jsonl") == queue_before
    assert read_jsonl(context["root"] / "screening.jsonl") == screening_before


def test_replacement_materializes_and_profile_accepts_new_predecessor(
    tmp_path: Path,
):
    from trading_os.research_assets.coverage_store import read_jsonl
    from trading_os.research_assets.manager_screen_quote_impact import (
        manager_screen_quote_impact_status,
        record_manager_screen_quote_impact,
    )
    from trading_os.research_assets.profile_workflow import (
        _profile_predecessor_order,
        _validate_manager_bound_submission,
    )

    context = _fixture(tmp_path)
    _prepare(context)
    packet = _load_review_packet(tmp_path)
    submission = _review_submission(
        packet,
        actions={"CN:000001": "watch"},
    )
    recorded = record_manager_screen_quote_impact(
        root=context["root"],
        run_id=RUN_ID,
        batch_id=BATCH_ID,
        review_id=REVIEW_ID,
        submission=submission,
        recorded_at=CUTOFF + dt.timedelta(minutes=5),
    )
    replay = record_manager_screen_quote_impact(
        root=context["root"],
        run_id=RUN_ID,
        batch_id=BATCH_ID,
        review_id=REVIEW_ID,
        submission=submission,
        recorded_at=CUTOFF + dt.timedelta(minutes=6),
    )
    queue = {row["symbol"]: row for row in read_jsonl(context["root"] / "research_queue.jsonl")}
    screening = {row["symbol"]: row for row in read_jsonl(context["root"] / "screening.jsonl")}
    result = json.loads((tmp_path / recorded["result_path"]).read_text(encoding="utf-8"))

    assert replay["idempotent"] is True
    assert queue["CN:000001"]["manager_screen_route"] == "watch"
    assert queue["CN:000001"]["task_type"] == "manager_screen"
    assert screening["CN:000001"]["decision"] == "watch_only"
    assert (
        manager_screen_quote_impact_status(
            root=context["root"],
            run_id=RUN_ID,
            batch_id=BATCH_ID,
            review_id=REVIEW_ID,
        )["materialized_replacement_count"]
        == 1
    )
    assert (
        _profile_predecessor_order(
            result,
            artifact_type="manager_screen_quote_impact_result",
            stage="quick_profile",
        )
        == []
    )
    claimed = {
        **queue["CN:000001"],
        "status": "running",
        "assigned_agent": "/root/analyst",
    }
    _validate_manager_bound_submission(
        {
            "manager_screen_binding": {
                "result_path": claimed["manager_screen_result_path"],
                "result_sha256": claimed["manager_screen_result_sha256"],
                "decisive_question": claimed["decisive_question"],
                "evidence_ids": claimed["evidence_ids"],
            },
            "decisive_answer": {},
            "provenance": {"agent": "/root/analyst"},
        },
        queue_record=claimed,
        repository_root=tmp_path,
        symbol="CN:000001",
    )


def test_capacity_does_not_refund_historical_purchase_on_net_route_change(
    tmp_path: Path,
):
    from trading_os.research_assets.manager_screen_quote_impact import (
        ManagerScreenQuoteImpactError,
        record_manager_screen_quote_impact,
    )

    blocked_context = _fixture(tmp_path / "blocked", capacity=1)
    _prepare(blocked_context)
    blocked_packet = _load_review_packet(tmp_path / "blocked")
    blocked_submission = _review_submission(
        blocked_packet,
        actions={"CN:000001": "send_to_analyst"},
    )
    with pytest.raises(ManagerScreenQuoteImpactError, match="capacity"):
        record_manager_screen_quote_impact(
            root=blocked_context["root"],
            run_id=RUN_ID,
            batch_id=BATCH_ID,
            review_id=REVIEW_ID,
            submission=blocked_submission,
            recorded_at=CUTOFF + dt.timedelta(minutes=5),
        )

    net_context = _fixture(
        tmp_path / "net",
        second_change_pct=25.0,
        capacity=1,
    )
    _prepare(net_context)
    net_packet = _load_review_packet(tmp_path / "net")
    net_submission = _review_submission(
        net_packet,
        actions={
            "CN:000001": "send_to_analyst",
            "CN:000002": "pass",
        },
    )
    with pytest.raises(ManagerScreenQuoteImpactError, match="cumulative"):
        record_manager_screen_quote_impact(
            root=net_context["root"],
            run_id=RUN_ID,
            batch_id=BATCH_ID,
            review_id=REVIEW_ID,
            submission=net_submission,
            recorded_at=CUTOFF + dt.timedelta(minutes=5),
        )


def test_new_batch_capacity_counts_recorded_quote_impact_effective_routes(
    tmp_path: Path,
):
    from trading_os.research_assets.coverage_store import read_jsonl
    from trading_os.research_assets.manager_screen_quote_impact import (
        record_manager_screen_quote_impact,
    )
    from trading_os.research_assets.manager_screening import (
        ManagerScreeningError,
        freeze_manager_screen_batch,
        record_manager_screen_decisions,
    )

    context = _fixture(
        tmp_path,
        capacity=2,
        original_routes=("pass", "send_to_analyst"),
        include_third_company=True,
    )
    _prepare(context)
    quote_packet = _load_review_packet(tmp_path)
    record_manager_screen_quote_impact(
        root=context["root"],
        run_id=RUN_ID,
        batch_id=BATCH_ID,
        review_id=REVIEW_ID,
        submission=_review_submission(
            quote_packet,
            actions={"CN:000001": "send_to_analyst"},
        ),
        recorded_at=CUTOFF + dt.timedelta(minutes=5),
    )
    effective_routes = {
        row["symbol"]: row["manager_screen_route"]
        for row in read_jsonl(context["root"] / "research_queue.jsonl")
        if row.get("manager_screen_run_id") == RUN_ID
    }
    assert effective_routes == {
        "CN:000001": "send_to_analyst",
        "CN:000002": "send_to_analyst",
    }

    frozen = freeze_manager_screen_batch(
        root=context["root"],
        run_id=RUN_ID,
        batch_id="batch-002",
        batch_size=1,
        frozen_at=CUTOFF + dt.timedelta(minutes=6),
        policy_path=context["policy_path"],
    )
    packet = json.loads((tmp_path / frozen["packet_path"]).read_text(encoding="utf-8"))
    queue_before = (context["root"] / "research_queue.jsonl").read_bytes()
    result_path = context["root"] / "manager-screen" / RUN_ID / "batch-002" / "result.json"

    with pytest.raises(
        ManagerScreeningError,
        match=r"2 sealed \+ 1 requested > 2.*whole batch was rejected",
    ):
        record_manager_screen_decisions(
            root=context["root"],
            run_id=RUN_ID,
            batch_id="batch-002",
            submission=_manager_submission(
                packet,
                routes=("send_to_analyst",),
            ),
            recorded_at=CUTOFF + dt.timedelta(minutes=7),
        )
    assert not result_path.exists()
    assert not result_path.with_name("result.json.seal.json").exists()
    assert (context["root"] / "research_queue.jsonl").read_bytes() == queue_before


def test_later_progress_capacity_uses_final_materialized_routes(
    tmp_path: Path,
):
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.manager_screen_quote_impact import (
        ManagerScreenQuoteImpactError,
        record_manager_screen_quote_impact,
    )

    context = _fixture(
        tmp_path,
        second_change_pct=25.0,
        capacity=1,
    )
    _prepare(context)
    queue_path = context["root"] / "research_queue.jsonl"
    queue = read_jsonl(queue_path)
    later = next(row for row in queue if row["symbol"] == "CN:000002")
    later.update(
        {
            "task_type": "deep_research",
            "status": "running",
            "assigned_agent": "/analyst/deep",
            "started_at": (CUTOFF + dt.timedelta(minutes=5)).isoformat(),
            "result_path": "research/deep-in-progress.json",
        }
    )
    write_jsonl(queue_path, queue)
    packet = _load_review_packet(tmp_path)
    submission = _review_submission(
        packet,
        actions={
            "CN:000001": "send_to_analyst",
            "CN:000002": "pass",
        },
    )

    queue_before = queue_path.read_bytes()
    with pytest.raises(ManagerScreenQuoteImpactError, match="cumulative"):
        record_manager_screen_quote_impact(
            root=context["root"],
            run_id=RUN_ID,
            batch_id=BATCH_ID,
            review_id=REVIEW_ID,
            submission=submission,
            recorded_at=CUTOFF + dt.timedelta(minutes=6),
        )
    assert queue_path.read_bytes() == queue_before


def test_capacity_and_materialization_conserve_later_progress_routes_directly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    import trading_os.research_assets.manager_screening as screening
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.manager_screen_quote_impact import (
        _enforce_capacity,
        _materialize_replacements,
    )

    root = tmp_path / "coverage" / "cn-a"
    original_path = f"coverage/cn-a/manager-screen/{RUN_ID}/{BATCH_ID}/result.json"
    queue = [
        {
            "symbol": "CN:000001",
            "manager_screen_run_id": RUN_ID,
            "manager_screen_batch_id": BATCH_ID,
            "manager_screen_route": "pass",
            "manager_screen_result_path": original_path,
            "manager_screen_result_sha256": "a" * 64,
            "task_type": "manager_screen",
            "status": "completed",
            "stage_history": [],
        },
        {
            "symbol": "CN:000002",
            "manager_screen_run_id": RUN_ID,
            "manager_screen_batch_id": BATCH_ID,
            "manager_screen_route": "send_to_analyst",
            "manager_screen_result_path": original_path,
            "manager_screen_result_sha256": "a" * 64,
            "task_type": "deep_research",
            "status": "running",
            "assigned_agent": "/analyst/deep",
            "result_path": "research/deep-in-progress.json",
            "stage_history": [],
        },
    ]
    write_jsonl(root / "research_queue.jsonl", queue)
    write_jsonl(
        root / "screening.jsonl",
        [
            {
                "symbol": row["symbol"],
                "decision": "quick_profile",
            }
            for row in queue
        ],
    )

    def decision(symbol: str, route: str) -> dict:
        return {
            "symbol": symbol,
            "route": route,
            "one_line_reason": f"replace with {route}",
            "decisive_question": "Does the new price change research value?",
            "revisit_triggers": (
                []
                if route == "send_to_analyst"
                else [
                    {
                        "type": "price",
                        "condition": "price changes again",
                        "reason": "valuation changed",
                    }
                ]
            ),
            "confidence": "high",
            "evidence_ids": [f"quote:{symbol}"],
        }

    reviews = [
        {
            "symbol": "CN:000001",
            "action": "replacement",
            "old_route": "pass",
            "replacement": decision("CN:000001", "send_to_analyst"),
            "effective_decision": decision(
                "CN:000001",
                "send_to_analyst",
            ),
        },
        {
            "symbol": "CN:000002",
            "action": "replacement",
            "old_route": "send_to_analyst",
            "replacement": decision("CN:000002", "pass"),
            "effective_decision": decision("CN:000002", "pass"),
        },
    ]
    plan = {
        "run_id": RUN_ID,
        "batch_id": BATCH_ID,
        "review_id": REVIEW_ID,
        "original_result_path": original_path,
        "policy": {
            "send_to_analyst_capacity_per_run": 2,
            "quick_profile_effort_budget_hours": 1.5,
            "quick_profile_stop_conditions": ["stop"],
        },
    }
    result = {
        "recorded_at": (CUTOFF + dt.timedelta(minutes=6)).isoformat(),
        "reviews": reviews,
    }
    packet = {
        "rows": [
            {"symbol": "CN:000001", "name": "甲公司"},
            {"symbol": "CN:000002", "name": "乙公司"},
        ]
    }
    result_path = (
        root
        / "manager-screen"
        / RUN_ID
        / BATCH_ID
        / "quote-impact-reviews"
        / REVIEW_ID
        / "result.json"
    )

    monkeypatch.setattr(
        screening,
        "manager_screen_status",
        lambda **_: {"analyst_budget": {"purchased_company_count": 1}},
    )
    _enforce_capacity(
        base=root,
        run_id=RUN_ID,
        plan=plan,
        reviews=reviews,
    )
    _materialize_replacements(
        base=root,
        repository_root=tmp_path,
        plan=plan,
        packet=packet,
        result=result,
        result_path=result_path,
        result_sha256="b" * 64,
    )
    final = {row["symbol"]: row for row in read_jsonl(root / "research_queue.jsonl")}

    assert {symbol: row["manager_screen_route"] for symbol, row in final.items()} == {
        "CN:000001": "send_to_analyst",
        "CN:000002": "pass",
    }
    assert sum(row["manager_screen_route"] == "send_to_analyst" for row in final.values()) == 1
    assert final["CN:000002"]["task_type"] == "deep_research"
    assert final["CN:000002"]["status"] == "running"
    assert final["CN:000002"]["assigned_agent"] == "/analyst/deep"
    assert final["CN:000002"]["result_path"] == "research/deep-in-progress.json"


def test_later_research_keeps_operational_and_screening_state(tmp_path: Path):
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.manager_screen_quote_impact import (
        record_manager_screen_quote_impact,
    )

    context = _fixture(tmp_path)
    _prepare(context)
    queue_path = context["root"] / "research_queue.jsonl"
    screening_path = context["root"] / "screening.jsonl"
    queue = read_jsonl(queue_path)
    target = next(row for row in queue if row["symbol"] == "CN:000001")
    target.update(
        {
            "task_type": "scoped_research",
            "status": "running",
            "assigned_agent": "/analyst/one",
            "started_at": (CUTOFF + dt.timedelta(minutes=5)).isoformat(),
            "result_path": "research/in-progress.json",
            "manager_screen_route": "pass",
        }
    )
    write_jsonl(queue_path, queue)
    screening_before = read_jsonl(screening_path)
    operational_before = {
        key: target.get(key)
        for key in (
            "task_type",
            "status",
            "assigned_agent",
            "started_at",
            "result_path",
            "reason",
        )
    }
    packet = _load_review_packet(tmp_path)
    submission = _review_submission(
        packet,
        actions={"CN:000001": "send_to_analyst"},
    )
    recorded = record_manager_screen_quote_impact(
        root=context["root"],
        run_id=RUN_ID,
        batch_id=BATCH_ID,
        review_id=REVIEW_ID,
        submission=submission,
        recorded_at=CUTOFF + dt.timedelta(minutes=6),
    )
    updated = next(row for row in read_jsonl(queue_path) if row["symbol"] == "CN:000001")

    assert {key: updated.get(key) for key in operational_before} == operational_before
    assert updated["manager_screen_route"] == "send_to_analyst"
    assert updated["decisive_question"] == "新价格下是否仍值得投入研究预算？"
    assert updated["revisit_triggers"] == []
    assert updated["evidence_ids"] == [packet["rows"][0]["quote"]["evidence_id"]]
    assert updated["manager_screen_result_path"] == recorded["result_path"]
    assert updated["stage_history"][-1]["stage"] == "manager_screen_quote_impact"
    assert read_jsonl(screening_path) == screening_before


def test_record_replay_repairs_partial_materialization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    import trading_os.research_assets.manager_screen_quote_impact as module

    context = _fixture(tmp_path)
    _prepare(context)
    packet = _load_review_packet(tmp_path)
    submission = _review_submission(
        packet,
        actions={"CN:000001": "watch"},
    )
    real_write_jsonl = module.write_jsonl

    def fail_screening(path: str | Path, rows: list[dict], *args, **kwargs):
        if Path(path).name == "screening.jsonl":
            raise OSError("simulated screening write failure")
        return real_write_jsonl(path, rows, *args, **kwargs)

    monkeypatch.setattr(module, "write_jsonl", fail_screening)
    with pytest.raises(OSError, match="simulated"):
        module.record_manager_screen_quote_impact(
            root=context["root"],
            run_id=RUN_ID,
            batch_id=BATCH_ID,
            review_id=REVIEW_ID,
            submission=submission,
            recorded_at=CUTOFF + dt.timedelta(minutes=5),
        )
    result_path = (
        context["root"]
        / "manager-screen"
        / RUN_ID
        / BATCH_ID
        / "quote-impact-reviews"
        / REVIEW_ID
        / "result.json"
    )
    assert result_path.exists()

    monkeypatch.setattr(module, "write_jsonl", real_write_jsonl)
    replay = module.record_manager_screen_quote_impact(
        root=context["root"],
        run_id=RUN_ID,
        batch_id=BATCH_ID,
        review_id=REVIEW_ID,
        submission=submission,
        recorded_at=CUTOFF + dt.timedelta(minutes=6),
    )
    assert replay["idempotent"] is True
    assert (
        module.manager_screen_quote_impact_status(
            root=context["root"],
            run_id=RUN_ID,
            batch_id=BATCH_ID,
            review_id=REVIEW_ID,
        )["materialized_replacement_count"]
        == 1
    )


def test_manager_status_reports_prepared_quote_impact_without_overlay(
    tmp_path: Path,
):
    from trading_os.research_assets.manager_screening import manager_screen_status

    context = _fixture(tmp_path)
    _prepare(context)

    status = manager_screen_status(root=context["root"], run_id=RUN_ID)

    assert status["by_route"] == {"pass": 1, "send_to_analyst": 1}
    quote_impact = status["batches"][0]["quote_impact_review"]
    assert quote_impact["state"] == "prepared"
    assert quote_impact["candidate_count"] == 1
    assert quote_impact["result_sha256"] is None


def test_manager_status_overlays_pass_to_send_and_reports_effective_budget(
    tmp_path: Path,
):
    from trading_os.research_assets.manager_screen_quote_impact import (
        record_manager_screen_quote_impact,
    )
    from trading_os.research_assets.manager_screening import manager_screen_status

    context = _fixture(tmp_path)
    _prepare(context)
    packet = _load_review_packet(tmp_path)
    recorded = record_manager_screen_quote_impact(
        root=context["root"],
        run_id=RUN_ID,
        batch_id=BATCH_ID,
        review_id=REVIEW_ID,
        submission=_review_submission(
            packet,
            actions={"CN:000001": "send_to_analyst"},
        ),
        recorded_at=CUTOFF + dt.timedelta(minutes=5),
    )

    status = manager_screen_status(root=context["root"], run_id=RUN_ID)

    assert status["by_route"] == {"send_to_analyst": 2}
    budget = status["analyst_budget"]
    assert budget["purchased_company_count"] == 2
    assert budget["historical_purchased_company_count"] == 2
    assert budget["current_effective_send_company_count"] == 2
    assert budget["current_backlog_company_count"] == 2
    quote_impact = status["batches"][0]["quote_impact_review"]
    assert quote_impact["state"] == "recorded"
    assert quote_impact["result_sha256"] == recorded["result_sha256"]
    assert quote_impact["effective_route_delta"] == {
        "pass": -1,
        "send_to_analyst": 1,
        "watch": 0,
    }
    assert status["batches"][0]["quote_amendment"] is None


def test_manager_status_tracks_watch_to_send_and_send_to_pass_later_progress(
    tmp_path: Path,
):
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.manager_screen_quote_impact import (
        record_manager_screen_quote_impact,
    )
    from trading_os.research_assets.manager_screening import manager_screen_status

    context = _fixture(
        tmp_path,
        second_change_pct=25.0,
        original_routes=("watch", "send_to_analyst"),
    )
    _prepare(context)
    queue_path = context["root"] / "research_queue.jsonl"
    queue = read_jsonl(queue_path)
    later = next(row for row in queue if row["symbol"] == "CN:000002")
    later.update(
        {
            "task_type": "deep_research",
            "status": "running",
            "assigned_agent": "/analyst/deep",
            "started_at": (CUTOFF + dt.timedelta(minutes=5)).isoformat(),
            "result_path": "research/deep-in-progress.json",
        }
    )
    write_jsonl(queue_path, queue)
    packet = _load_review_packet(tmp_path)
    record_manager_screen_quote_impact(
        root=context["root"],
        run_id=RUN_ID,
        batch_id=BATCH_ID,
        review_id=REVIEW_ID,
        submission=_review_submission(
            packet,
            actions={
                "CN:000001": "send_to_analyst",
                "CN:000002": "pass",
            },
        ),
        recorded_at=CUTOFF + dt.timedelta(minutes=6),
    )

    status = manager_screen_status(root=context["root"], run_id=RUN_ID)

    assert status["by_route"] == {"pass": 1, "send_to_analyst": 1}
    budget = status["analyst_budget"]
    assert budget["historical_purchased_company_count"] == 2
    assert budget["historical_purchased_effort_budget_hours"] == 3.0
    assert budget["current_effective_send_company_count"] == 1
    assert budget["current_effective_send_effort_budget_hours"] == 1.5
    assert budget["current_backlog_company_count"] == 1
    assert budget["current_backlog_effort_budget_hours"] == 1.5
    assert budget["current_state"] == {
        "deep_research:running": 1,
        "quick_profile:pending": 1,
    }


def test_manager_status_fails_closed_on_multiple_quote_impact_reviews(
    tmp_path: Path,
):
    from trading_os.research_assets.manager_screening import (
        ManagerScreeningError,
        manager_screen_status,
    )

    context = _fixture(tmp_path)
    _prepare(context)
    extra = (
        context["root"]
        / "manager-screen"
        / RUN_ID
        / BATCH_ID
        / "quote-impact-reviews"
        / "review-002"
    )
    extra.mkdir(parents=True)

    with pytest.raises(ManagerScreeningError, match="quote-impact review is invalid"):
        manager_screen_status(root=context["root"], run_id=RUN_ID)


def test_manager_status_rejects_inconsistent_quote_impact_summary(
    tmp_path: Path,
):
    from trading_os.research_assets.manager_screen_quote_impact import (
        record_manager_screen_quote_impact,
    )
    from trading_os.research_assets.manager_screening import (
        ManagerScreeningError,
        manager_screen_status,
    )
    from trading_os.research_assets.sealing import canonical_json_bytes, seal_json

    context = _fixture(tmp_path)
    _prepare(context)
    packet = _load_review_packet(tmp_path)
    recorded = record_manager_screen_quote_impact(
        root=context["root"],
        run_id=RUN_ID,
        batch_id=BATCH_ID,
        review_id=REVIEW_ID,
        submission=_review_submission(
            packet,
            actions={"CN:000001": "send_to_analyst"},
        ),
        recorded_at=CUTOFF + dt.timedelta(minutes=5),
    )
    result_path = tmp_path / recorded["result_path"]
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["summary"]["replacement_count"] = 0
    result_path.with_name(f"{result_path.name}.seal.json").unlink()
    result_path.write_bytes(canonical_json_bytes(result))
    seal_json(
        result_path,
        result,
        artifact_type="manager_screen_quote_impact_result",
        sealed_at=CUTOFF + dt.timedelta(minutes=5),
    )

    with pytest.raises(ManagerScreeningError, match="quote-impact review is invalid"):
        manager_screen_status(root=context["root"], run_id=RUN_ID)


def test_manager_status_rejects_queue_that_disagrees_with_effective_predecessor(
    tmp_path: Path,
):
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.manager_screen_quote_impact import (
        record_manager_screen_quote_impact,
    )
    from trading_os.research_assets.manager_screening import (
        ManagerScreeningError,
        manager_screen_status,
    )

    context = _fixture(tmp_path)
    _prepare(context)
    packet = _load_review_packet(tmp_path)
    record_manager_screen_quote_impact(
        root=context["root"],
        run_id=RUN_ID,
        batch_id=BATCH_ID,
        review_id=REVIEW_ID,
        submission=_review_submission(
            packet,
            actions={"CN:000001": "send_to_analyst"},
        ),
        recorded_at=CUTOFF + dt.timedelta(minutes=5),
    )
    queue_path = context["root"] / "research_queue.jsonl"
    queue = read_jsonl(queue_path)
    target = next(row for row in queue if row["symbol"] == "CN:000001")
    target["decisive_question"] = "mutable queue tampering"
    write_jsonl(queue_path, queue)

    with pytest.raises(ManagerScreeningError, match="effective sealed"):
        manager_screen_status(root=context["root"], run_id=RUN_ID)


def test_v2_quote_impact_rebuilds_support_and_accepts_complete_replacement(
    tmp_path: Path,
):
    from trading_os.research_assets.manager_screen_quote_impact import (
        manager_screen_quote_impact_status,
        record_manager_screen_quote_impact,
    )

    context = _fixture(
        tmp_path,
        decision_contract_version=2,
        first_name="ST甲公司",
    )
    _prepare(context)
    packet = _load_review_packet(tmp_path)
    row = packet["rows"][0]
    old_support = context["packet"]["dossiers"][0]["market_snapshot"]["manager_screen_facts"][
        "decision_support"
    ]
    support = row["decision_support"]

    assert old_support["canonical_fact_line"]["market_cap_cny"] == 10_000_000_000
    assert support["canonical_fact_line"]["market_cap_cny"] == 12_500_000_000
    assert support["canonical_fact_line"]["sha256"] != old_support["canonical_fact_line"]["sha256"]
    expected_source_evidence_id = f"quote-amendment:quotes-002:{row['symbol']}"
    assert (
        support["canonical_fact_line"]["source_evidence_id"]
        == expected_source_evidence_id
        == row["quote"]["evidence_id"]
    )
    assert expected_source_evidence_id in row["allowed_evidence_ids"]
    assert [flag["flag_id"] for flag in support["mandatory_risk_flags"]] == ["audit_or_listing"]

    submission = _review_submission(
        packet,
        actions={"CN:000001": "watch"},
    )
    recorded = record_manager_screen_quote_impact(
        root=context["root"],
        run_id=RUN_ID,
        batch_id=BATCH_ID,
        review_id=REVIEW_ID,
        submission=submission,
        recorded_at=CUTOFF + dt.timedelta(minutes=5),
    )
    result = json.loads((tmp_path / recorded["result_path"]).read_text(encoding="utf-8"))
    replacement = result["decisions"][0]

    assert replacement["route"] == "watch"
    assert replacement["one_line_reason"].startswith(f"{support['canonical_fact_line']['text']}；")
    assert replacement["risk_acknowledgements"] == row["old_decision"]["risk_acknowledgements"]
    assert (
        manager_screen_quote_impact_status(
            root=context["root"],
            run_id=RUN_ID,
            batch_id=BATCH_ID,
            review_id=REVIEW_ID,
        )["replacement_count"]
        == 1
    )


def test_v3_quote_impact_keeps_candidate_unfunded_after_full_replacement(
    tmp_path: Path,
):
    from trading_os.research_assets.coverage_store import read_jsonl
    from trading_os.research_assets.manager_screen_quote_impact import (
        record_manager_screen_quote_impact,
    )
    from trading_os.research_assets.manager_screening import manager_screen_status

    context = _fixture(
        tmp_path,
        decision_contract_version=3,
        first_name="ST甲公司",
    )
    _prepare(context)
    packet = _load_review_packet(tmp_path)
    recorded = record_manager_screen_quote_impact(
        root=context["root"],
        run_id=RUN_ID,
        batch_id=BATCH_ID,
        review_id=REVIEW_ID,
        submission=_review_submission(
            packet,
            actions={"CN:000001": "research_candidate"},
        ),
        recorded_at=CUTOFF + dt.timedelta(minutes=5),
    )
    result = json.loads((tmp_path / recorded["result_path"]).read_text(encoding="utf-8"))
    assert result["decisions"][0]["route"] == "research_candidate"
    queue = {row["symbol"]: row for row in read_jsonl(context["root"] / "research_queue.jsonl")}
    candidate = queue["CN:000001"]
    assert candidate["task_type"] == "manager_screen"
    assert candidate["status"] == "completed"
    assert candidate["manager_screen_route"] == "research_candidate"
    assert candidate["research_budget_state"] == "candidate_unfunded"
    assert "effort_budget_hours" not in candidate
    screening = {row["symbol"]: row for row in read_jsonl(context["root"] / "screening.jsonl")}
    assert screening["CN:000001"]["decision"] == "candidate_unfunded"
    assert screening["CN:000001"]["research_budget_state"] == "candidate_unfunded"
    status = manager_screen_status(root=context["root"], run_id=RUN_ID)
    assert status["analyst_budget"]["purchased_company_count"] == 0
    assert status["batches"][0]["quote_impact_review"]["effective_route_delta"] == {
        "pass": -1,
        "research_candidate": 1,
        "watch": 0,
    }


def test_v3_quote_impact_clears_stale_candidate_budget_state(tmp_path: Path):
    from trading_os.research_assets.coverage_store import read_jsonl
    from trading_os.research_assets.manager_screen_quote_impact import (
        record_manager_screen_quote_impact,
    )

    context = _fixture(
        tmp_path,
        decision_contract_version=3,
        original_routes=("research_candidate", "pass"),
    )
    _prepare(context)
    packet = _load_review_packet(tmp_path)
    record_manager_screen_quote_impact(
        root=context["root"],
        run_id=RUN_ID,
        batch_id=BATCH_ID,
        review_id=REVIEW_ID,
        submission=_review_submission(
            packet,
            actions={"CN:000001": "pass"},
        ),
        recorded_at=CUTOFF + dt.timedelta(minutes=5),
    )
    queue = {row["symbol"]: row for row in read_jsonl(context["root"] / "research_queue.jsonl")}
    screening = {row["symbol"]: row for row in read_jsonl(context["root"] / "screening.jsonl")}
    assert queue["CN:000001"]["manager_screen_route"] == "pass"
    assert "research_budget_state" not in queue["CN:000001"]
    assert screening["CN:000001"]["decision"] == "catalog"
    assert "research_budget_state" not in screening["CN:000001"]


def test_v2_quote_impact_rejects_keep(tmp_path: Path):
    from trading_os.research_assets.manager_screen_quote_impact import (
        ManagerScreenQuoteImpactError,
        record_manager_screen_quote_impact,
    )

    context = _fixture(
        tmp_path,
        decision_contract_version=2,
        first_name="ST甲公司",
    )
    _prepare(context)
    packet = _load_review_packet(tmp_path)

    with pytest.raises(ManagerScreenQuoteImpactError, match="complete replacement"):
        record_manager_screen_quote_impact(
            root=context["root"],
            run_id=RUN_ID,
            batch_id=BATCH_ID,
            review_id=REVIEW_ID,
            submission=_review_submission(
                packet,
                actions={"CN:000001": "keep"},
            ),
            recorded_at=CUTOFF + dt.timedelta(minutes=5),
        )


def test_v2_quote_impact_rejects_tampered_packet_canonical_support(
    tmp_path: Path,
):
    from trading_os.research_assets.manager_screen_quote_impact import (
        ManagerScreenQuoteImpactError,
        record_manager_screen_quote_impact,
    )
    from trading_os.research_assets.sealing import canonical_json_bytes, seal_json

    context = _fixture(
        tmp_path,
        decision_contract_version=2,
        first_name="ST甲公司",
    )
    prepared = _prepare(context)
    packet_path = tmp_path / prepared["packet_path"]
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    packet["rows"][0]["decision_support"]["canonical_fact_line"]["market_cap_cny"] = 1
    packet_path.with_name(f"{packet_path.name}.seal.json").unlink()
    packet_path.write_bytes(canonical_json_bytes(packet))
    seal_json(
        packet_path,
        packet,
        artifact_type="manager_screen_quote_impact_packet",
        sealed_at=CUTOFF + dt.timedelta(minutes=4),
    )

    with pytest.raises(ManagerScreenQuoteImpactError, match="decision support"):
        record_manager_screen_quote_impact(
            root=context["root"],
            run_id=RUN_ID,
            batch_id=BATCH_ID,
            review_id=REVIEW_ID,
            submission=_review_submission(
                packet,
                actions={"CN:000001": "watch"},
            ),
            recorded_at=CUTOFF + dt.timedelta(minutes=5),
        )


def test_v2_quote_impact_rejects_rehashed_tampered_canonical_source(
    tmp_path: Path,
):
    from trading_os.research_assets.manager_screen_quote_impact import (
        ManagerScreenQuoteImpactError,
        record_manager_screen_quote_impact,
    )
    from trading_os.research_assets.sealing import canonical_json_bytes, seal_json

    context = _fixture(
        tmp_path,
        decision_contract_version=2,
        first_name="ST甲公司",
    )
    prepared = _prepare(context)
    packet_path = tmp_path / prepared["packet_path"]
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    canonical = packet["rows"][0]["decision_support"]["canonical_fact_line"]
    canonical["source_evidence_id"] = f"snapshot:{packet['rows'][0]['symbol']}"
    unsigned = {key: value for key, value in canonical.items() if key != "sha256"}
    canonical["sha256"] = hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest()
    packet_path.with_name(f"{packet_path.name}.seal.json").unlink()
    packet_path.write_bytes(canonical_json_bytes(packet))
    seal_json(
        packet_path,
        packet,
        artifact_type="manager_screen_quote_impact_packet",
        sealed_at=CUTOFF + dt.timedelta(minutes=4),
    )

    with pytest.raises(ManagerScreenQuoteImpactError, match="decision support"):
        record_manager_screen_quote_impact(
            root=context["root"],
            run_id=RUN_ID,
            batch_id=BATCH_ID,
            review_id=REVIEW_ID,
            submission=_review_submission(
                packet,
                actions={"CN:000001": "watch"},
            ),
            recorded_at=CUTOFF + dt.timedelta(minutes=5),
        )


@pytest.mark.parametrize("tampered", ["canonical", "acknowledgement"])
def test_v2_quote_impact_rejects_tampered_decision_quality(
    tmp_path: Path,
    tampered: str,
):
    from trading_os.research_assets.manager_screen_quote_impact import (
        ManagerScreenQuoteImpactError,
        record_manager_screen_quote_impact,
    )

    context = _fixture(
        tmp_path,
        decision_contract_version=2,
        first_name="ST甲公司",
    )
    _prepare(context)
    packet = _load_review_packet(tmp_path)
    submission = _review_submission(
        packet,
        actions={"CN:000001": "watch"},
    )
    replacement = submission["reviews"][0]["replacement"]
    if tampered == "canonical":
        replacement["one_line_reason"] = "篡改后的事实前缀；仍需复核"
        expected = "canonical"
    else:
        replacement["risk_acknowledgements"] = []
        expected = "risk_acknowledgements"

    with pytest.raises(ManagerScreenQuoteImpactError, match=expected):
        record_manager_screen_quote_impact(
            root=context["root"],
            run_id=RUN_ID,
            batch_id=BATCH_ID,
            review_id=REVIEW_ID,
            submission=submission,
            recorded_at=CUTOFF + dt.timedelta(minutes=5),
        )


def test_legacy_quote_impact_plan_is_stable_after_live_policy_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    import trading_os.research_assets.manager_screen_quote_impact as module

    context = _fixture(tmp_path)
    real_loader = module._load_completed_inputs

    def legacy_loader(**kwargs):
        loaded = real_loader(**kwargs)
        loaded["policy_ref"] = dict(loaded["policy_ref"])
        loaded["policy_ref"].pop("payload")
        return loaded

    monkeypatch.setattr(module, "_load_completed_inputs", legacy_loader)
    _prepare(context)
    packet = _load_review_packet(tmp_path)
    assert "decision_support" not in packet["rows"][0]
    _write_policy(
        context["policy_path"],
        capacity=3,
        decision_contract_version=2,
    )

    overlay = module.load_manager_screen_quote_impact_overlay(
        root=context["root"],
        run_id=RUN_ID,
        batch_id=BATCH_ID,
    )

    assert overlay["state"] == "prepared"
    assert overlay["candidate_count"] == 1
    recorded = module.record_manager_screen_quote_impact(
        root=context["root"],
        run_id=RUN_ID,
        batch_id=BATCH_ID,
        review_id=REVIEW_ID,
        submission=_review_submission(
            packet,
            actions={"CN:000001": "keep"},
        ),
        recorded_at=CUTOFF + dt.timedelta(minutes=5),
    )
    assert recorded["keep_count"] == 1


@pytest.mark.parametrize("tampered", ["packet", "original_result", "amendment"])
def test_status_rejects_tampered_sealed_inputs(
    tmp_path: Path,
    tampered: str,
):
    from trading_os.research_assets.manager_screen_quote_impact import (
        ManagerScreenQuoteImpactError,
        manager_screen_quote_impact_status,
    )

    context = _fixture(tmp_path)
    prepared = _prepare(context)
    paths = {
        "packet": tmp_path / prepared["packet_path"],
        "original_result": tmp_path / context["recorded"]["result_path"],
        "amendment": tmp_path / context["amendment"]["path"],
    }
    path = paths[tampered]
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["portfolio_action"] = "tampered"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ManagerScreenQuoteImpactError, match="sealed"):
        manager_screen_quote_impact_status(
            root=context["root"],
            run_id=RUN_ID,
            batch_id=BATCH_ID,
            review_id=REVIEW_ID,
        )


def test_prepare_and_record_honor_coverage_lock(tmp_path: Path):
    from trading_os.research_assets.coverage_store import (
        CoverageValidationError,
        coverage_write_lock,
    )
    from trading_os.research_assets.manager_screen_quote_impact import (
        record_manager_screen_quote_impact,
    )

    context = _fixture(tmp_path)
    with coverage_write_lock(context["root"]):
        with pytest.raises(CoverageValidationError, match="busy"):
            _prepare(context)

    _prepare(context)
    packet = _load_review_packet(tmp_path)
    submission = _review_submission(
        packet,
        actions={"CN:000001": "keep"},
    )
    with coverage_write_lock(context["root"]):
        with pytest.raises(CoverageValidationError, match="busy"):
            record_manager_screen_quote_impact(
                root=context["root"],
                run_id=RUN_ID,
                batch_id=BATCH_ID,
                review_id=REVIEW_ID,
                submission=submission,
                recorded_at=CUTOFF + dt.timedelta(minutes=5),
            )


def test_quote_impact_cli_prepare_record_and_status(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    from trading_os.cli import main

    context = _fixture(tmp_path)
    common = [
        "--root",
        str(context["root"]),
        RUN_ID,
        BATCH_ID,
        REVIEW_ID,
    ]
    assert (
        main(
            [
                "coverage",
                "manager-screen-quote-impact-prepare",
                *common,
                "--quote-amendment",
                str(tmp_path / context["amendment"]["path"]),
                "--policy",
                str(context["policy_path"]),
                "--at",
                (CUTOFF + dt.timedelta(minutes=4)).isoformat(),
            ]
        )
        == 0
    )
    packet = _load_review_packet(tmp_path)
    submission_path = tmp_path / "review-submission.json"
    submission_path.write_text(
        json.dumps(
            _review_submission(
                packet,
                actions={"CN:000001": "keep"},
            ),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    assert (
        main(
            [
                "coverage",
                "manager-screen-quote-impact-record",
                *common,
                "--input",
                str(submission_path),
                "--at",
                (CUTOFF + dt.timedelta(minutes=5)).isoformat(),
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "coverage",
                "manager-screen-quote-impact-status",
                *common,
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert '"state": "recorded"' in output
