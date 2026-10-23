from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from trading_os.research_assets.research_flow import (
    MANUAL_REWRITE_TRIGGER,
    PERIODIC_TRIGGER,
    CompanyRef,
    ResearchFlow,
    ResearchRequest,
    ResearchResult,
    ReturnModel,
    StateCorruptionError,
    ValidationError,
    ValueRange,
)

AT = "2026-08-08T17:00:00+08:00"
LATER = "2026-09-01T17:00:00+08:00"
STANDARD_ID = "owner-value-1.0"
SPEC_REVISION = "320545a7e5878afab2eb781fbb9ee4a91deff304"


def _write_registry(root: Path) -> None:
    path = root / "research/standards/registry.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "active_standard": STANDARD_ID,
                "standards": [
                    {
                        "id": STANDARD_ID,
                        "status": "released",
                        "spec_revision": SPEC_REVISION,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _model(as_of: str = AT) -> ReturnModel:
    return ReturnModel(
        schema_version=1,
        method="annual_common_equity_irr_v1",
        currency="CNY",
        model_as_of=as_of,
        base_case_distributions_per_share=(1, 1.1, 1.2, 1.3, 1.4),
        base_case_terminal_equity_value_range_per_share={"year_5": {"low": 72, "high": 92}},
    )


def _result(symbol: str, period: str = "2026-H1", *, at: str = AT) -> ResearchResult:
    return ResearchResult(
        symbol=symbol,
        name="示例公司",
        outcome="covered",
        report_period=period,
        information_cutoff=at,
        summary="需求成立，但现金流仍需验证。",
        key_logic=("核心产品需求增长",),
        risks=("资本开支回报不及预期",),
        value_range=ValueRange(58, 82),
        valuation_note="正常化盈利为主、现金流折现为辅。",
        return_model=_model(at),
        return_model_note="按完全稀释普通股构造五年分配与独立第五年终值。",
        source_urls=("https://example.com/report",),
        report_markdown=(
            "# 示例公司完整研究\n\n"
            f"信息截止：{at[:10]}\n\n"
            "## 一句话结论\n\n需求成立，但现金流仍需验证。\n\n"
            "## 财务质量\n\n现金流转化决定估值上限。\n\n"
            "| 前次假设 | 本期实际 | 判断变化 | 估值影响 |\n"
            "|---|---|---|---|\n| 需求增长 | 需求增长 | 不变 | 区间不变 |\n\n"
            "## 估值\n\n方法一为正常化PE，方法二为现金流折现；以正常化PE为核心。\n\n"
            "核心合理价值区间：58—82 元。\n\n"
            "### 基准持有人回报模型输入\n\n五年分配及独立终值已核。\n\n"
            "## 风险\n\n资本开支回报不及预期。\n\n"
            "## 来源\n\n- https://example.com/report"
        ),
    )


def _enqueue(
    flow: ResearchFlow,
    symbol: str,
    period: str,
    *,
    kind: str = PERIODIC_TRIGGER,
    at: str = AT,
) -> str:
    _write_registry(flow.root)
    flow.register_universe([CompanyRef(symbol, "示例公司")], at=at)
    batch = flow.enqueue_research(
        [ResearchRequest(symbol, "完成财报周期完整研究")],
        report_period=period,
        trigger_kind=kind,
        batch_id="manual-001" if kind == MANUAL_REWRITE_TRIGGER else None,
        at=at,
    )
    task = batch.enqueued_tasks[0]
    return flow.start_task(task.task_id, at=at).task_id


def test_periodic_research_creates_one_period_slot(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    task_id = _enqueue(flow, "CN:000001", "2026-H1")
    state = flow.apply_result(_result("CN:000001"), task_id=task_id, at=AT)
    assert state["basis_report_path"].endswith("/reports/2026-H1.md")
    assert state["report_period"] == "2026-H1"
    assert state["standard_id"] == STANDARD_ID
    assert state["spec_revision"] == SPEC_REVISION
    assert state["accepted_at"] == AT
    assert flow.list_tasks() == ()
    flow.validate()


@pytest.mark.parametrize(
    "field,leak",
    [
        ("report_markdown", "按照你的要求，本报告扩大长期研究。"),
        ("report_markdown", "持有人模型保持仓库统一的五年接口。"),
        ("summary", "本轮对话形成了最新判断。"),
        ("key_logic", "回应您的问题，公司值得拥有。"),
        ("risks", "协调器验收后继续观察。"),
        ("return_model_note", "task_id: internal-123"),
    ],
)
def test_process_notes_are_rejected_before_any_research_write(tmp_path, field, leak):
    flow = ResearchFlow(tmp_path)
    task_id = _enqueue(flow, "CN:000001", "2026-H1")
    original = _result("CN:000001")
    value = getattr(original, field)
    replacement = (*value, leak) if isinstance(value, tuple) else value + "\n" + leak
    candidate = replace(original, **{field: replacement})
    before_state = (tmp_path / "coverage/cn-a/research_state.jsonl").read_bytes()
    before_queue = (tmp_path / "coverage/cn-a/research_queue.jsonl").read_bytes()
    with pytest.raises(ValidationError, match="user conversation or workflow notes"):
        flow.apply_result(candidate, task_id=task_id, at=AT)
    assert (tmp_path / "coverage/cn-a/research_state.jsonl").read_bytes() == before_state
    assert (tmp_path / "coverage/cn-a/research_queue.jsonl").read_bytes() == before_queue
    assert not (tmp_path / "research/companies/CN/000001/reports/2026-H1.md").exists()


def test_customer_analysis_and_necessary_accounting_contrasts_are_allowed(tmp_path):
    flow = ResearchFlow(tmp_path)
    task_id = _enqueue(flow, "CN:000001", "2026-H1")
    original = _result("CN:000001")
    candidate = replace(
        original,
        report_markdown=original.report_markdown
        + (
            "\n用户反馈显示续费率提高。模型不把会计利润当作现金分配。"
            "这不是新增收益，而是已确认应收股利到账。\n"
        ),
    )
    flow.apply_result(candidate, task_id=task_id, at=AT)
    flow.validate()


def test_completion_requires_a_released_active_standard(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    task_id = _enqueue(flow, "CN:000001", "2026-H1")
    (tmp_path / "research/standards/registry.json").unlink()
    with pytest.raises(ValidationError, match="registry is missing"):
        flow.apply_result(_result("CN:000001"), task_id=task_id, at=AT)

    _write_registry(tmp_path)
    registry_path = tmp_path / "research/standards/registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["standards"][0]["status"] = "draft"
    registry_path.write_text(json.dumps(registry), encoding="utf-8")
    with pytest.raises(ValidationError, match="must be released"):
        flow.apply_result(_result("CN:000001"), task_id=task_id, at=AT)


def test_validation_rejects_an_incomplete_standard_stamp(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    task_id = _enqueue(flow, "CN:000001", "2026-H1")
    flow.apply_result(_result("CN:000001"), task_id=task_id, at=AT)
    row = json.loads(flow.state_path.read_text(encoding="utf-8"))
    row["accepted_at"] = None
    flow.state_path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    with pytest.raises(StateCorruptionError, match="standard stamp is incomplete"):
        flow.validate()


def test_next_period_adds_a_slot_and_same_period_manual_rewrite_overwrites(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    first = _enqueue(flow, "CN:000001", "2026-H1")
    flow.apply_result(_result("CN:000001"), task_id=first, at=AT)

    rewrite = _enqueue(
        flow,
        "CN:000001",
        "2026-H1",
        kind=MANUAL_REWRITE_TRIGGER,
        at=LATER,
    )
    revised = replace(
        _result("CN:000001", at=AT),
        value_range=ValueRange(62, 88),
        report_markdown=_result("CN:000001", at=AT).report_markdown.replace("58—82", "62—88"),
    )
    state = flow.apply_result(revised, task_id=rewrite, at=LATER)
    assert state["basis_report_path"].endswith("2026-H1.md")
    assert len(list((tmp_path / "research/companies/CN/000001/reports").glob("*.md"))) == 1

    q3 = _enqueue(flow, "CN:000001", "2026-Q3", at="2026-10-31T17:00:00+08:00")
    q3_result = _result("CN:000001", "2026-Q3", at="2026-10-31T17:00:00+08:00")
    state = flow.apply_result(q3_result, task_id=q3, at="2026-10-31T17:00:00+08:00")
    assert state["basis_report_path"].endswith("2026-Q3.md")
    assert len(list((tmp_path / "research/companies/CN/000001/reports").glob("*.md"))) == 2
    flow.validate()


def test_periodic_enqueue_deduplicates_an_existing_slot(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    task_id = _enqueue(flow, "CN:000001", "2026-H1")
    flow.apply_result(_result("CN:000001"), task_id=task_id, at=AT)
    batch = flow.enqueue_research(
        [ResearchRequest("CN:000001", "重复周期")],
        report_period="2026-H1",
        trigger_kind=PERIODIC_TRIGGER,
        at=LATER,
    )
    assert batch.deduplicated == 1 and batch.enqueued_tasks == ()


def test_manual_rewrite_requires_an_existing_period(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    flow.register_universe([CompanyRef("CN:000001", "示例公司")], at=AT)
    with pytest.raises(ValidationError, match="no matching period slot"):
        flow.enqueue_research(
            [ResearchRequest("CN:000001", "人工改写")],
            report_period="2026-H1",
            trigger_kind=MANUAL_REWRITE_TRIGGER,
            batch_id="manual-001",
            at=AT,
        )


def test_result_must_match_task_period(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    task_id = _enqueue(flow, "CN:000001", "2026-H1")
    with pytest.raises(ValidationError, match="period does not match"):
        flow.apply_result(
            _result("CN:000001", "2026-Q3", at="2026-10-31T17:00:00+08:00"),
            task_id=task_id,
            at="2026-10-31T17:00:00+08:00",
        )


def test_period_cannot_end_after_information_cutoff(tmp_path: Path):
    del tmp_path
    with pytest.raises(ValidationError, match="ends after"):
        ResearchFlow._normalized_result(_result("CN:000001", "2026-Q3", at=AT))


def test_validation_rejects_retired_event_fields(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    flow.state_path.parent.mkdir(parents=True)
    row = {
        "schema_version": 6,
        "symbol": "CN:000001",
        "name": "示例公司",
        "universe_status": "active",
        "status": "ignore",
        "updated_at": AT,
        "summary": "不在重点跟踪池",
        "key_logic": [],
        "risks": [],
        "value_range": None,
        "source_urls": [],
        "last_research_at": None,
        "information_cutoff": None,
        "report_period": None,
        "basis_report_path": None,
        "valuation_note": None,
        "return_model": None,
        "return_model_note": None,
        "standard_id": None,
        "spec_revision": None,
        "accepted_at": None,
        "last_update": {"impact": "monitor"},
    }
    flow.state_path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    with pytest.raises(StateCorruptionError, match="retired event fields"):
        flow.validate()


def test_universe_sync_keeps_reports_and_cancels_tasks_for_inactive_security(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    _enqueue(flow, "CN:000001", "2026-H1")
    update = flow.sync_universe([], at=LATER)
    assert update.inactivated == 1
    assert flow.list_tasks() == ()
    assert flow.read_states()[0]["universe_status"] == "inactive"


def _foreign_result(
    symbol, period, basis, *, at="2026-10-24T09:00:00+08:00", unit="ordinary_share"
):
    currency = "HKD" if symbol.startswith("HK:") else "USD"
    result = _result(symbol, period, at=at)
    return replace(
        result,
        financial_basis=basis,
        security_basis={
            "currency": currency,
            "unit": unit,
            "ordinary_shares_per_unit": 5 if unit == "ADS" else 1,
            "source_url": "https://example.com/share-rights",
        },
        value_range=ValueRange(58, 82, currency),
        return_model=replace(result.return_model, currency=currency),
        report_markdown=result.report_markdown
        + f"\n财务期末：{basis['period_end']}\n财报披露：{basis['published_on']}\n",
    )


@pytest.mark.parametrize(
    "market,symbol,period,end",
    [
        ("hk", "HK:00700", "2026-H1", "2026-06-30"),
        ("us", "US:MSFT", "2026-FY", "2026-06-30"),
        ("us", "US:TSM", "2026-Q3", "2026-09-30"),
    ],
)
def test_foreign_full_lifecycle_with_actual_fiscal_end(tmp_path, market, symbol, period, end):
    _write_registry(tmp_path)
    flow = ResearchFlow(tmp_path, market=market)
    at = "2026-10-24T09:00:00+08:00"
    basis = {
        "period_end": end,
        "published_on": "2026-10-20",
        "source_url": "https://example.com/filing",
    }
    flow.register_universe([CompanyRef(symbol, "海外公司")], at=at)
    task = flow.enqueue_research(
        [ResearchRequest(symbol, "财报研究", financial_basis=basis)],
        report_period=period,
        trigger_kind=PERIODIC_TRIGGER,
        at=at,
    ).enqueued_tasks[0]
    started = flow.dispatch_tasks(limit=1, at=at)[0]
    assert started.financial_basis == basis
    result = _foreign_result(
        symbol, period, basis, unit="ADS" if symbol.endswith("TSM") else "ordinary_share"
    )
    state = flow.apply_result(result, task_id=task.task_id, at=at)
    assert (
        state["basis_report_path"]
        == f"research/companies/{symbol[:2]}/{symbol[3:]}/reports/{period}.md"
    )
    assert state["financial_basis"] == basis
    assert flow.validate().covered == 1
    assert not (tmp_path / "coverage/cn-a/research_state.jsonl").exists()
    rewrite = flow.enqueue_research(
        [ResearchRequest(symbol, "重新检验")],
        report_period=period,
        trigger_kind=MANUAL_REWRITE_TRIGGER,
        batch_id="rewrite",
        at=at,
    ).enqueued_tasks[0]
    assert rewrite.financial_basis == basis


def test_foreign_dates_currency_and_security_units_fail_closed(tmp_path):
    flow = ResearchFlow(tmp_path, market="us")
    with pytest.raises(ValidationError, match="another research market"):
        flow.register_universe([CompanyRef("HK:00700")])
    basis = {
        "period_end": "2026-06-30",
        "published_on": "2026-07-29",
        "source_url": "https://example.com/fy",
    }
    result = _foreign_result("US:MSFT", "2026-FY", basis)
    for broken in [
        replace(result, financial_basis=None),
        replace(result, security_basis=None),
        replace(result, value_range=ValueRange(58, 82, "CNY")),
        replace(result, financial_basis={**basis, "published_on": "2026-12-01"}),
    ]:
        with pytest.raises(ValidationError):
            flow._normalized_result(broken)


def test_foreign_next_slot_preserves_prior_report_and_requires_comparison(tmp_path):
    _write_registry(tmp_path)
    flow = ResearchFlow(tmp_path, market="us")
    symbol = "US:MSFT"
    at = "2026-10-30T09:00:00+08:00"
    flow.register_universe([CompanyRef(symbol)], at=at)
    bases = [("2026-FY", "2026-06-30", "2026-07-29"), ("2027-Q1", "2026-09-30", "2026-10-29")]
    for period, end, publication in bases:
        basis = {
            "period_end": end,
            "published_on": publication,
            "source_url": "https://example.com/results",
        }
        task = flow.enqueue_research(
            [ResearchRequest(symbol, "周期研究", financial_basis=basis)],
            report_period=period,
            trigger_kind=PERIODIC_TRIGGER,
            at=at,
        ).enqueued_tasks[0]
        flow.dispatch_tasks(limit=1, at=at)
        flow.apply_result(
            _foreign_result(symbol, period, basis, at=at), task_id=task.task_id, at=at
        )
    assert len(list((tmp_path / "research/companies/US/MSFT/reports").glob("*.md"))) == 2
    assert flow.validate().covered == 1


def test_same_issuer_cannot_run_in_two_market_queues(tmp_path):
    for market, symbol in [("cn-a", "CN:600036"), ("hk", "HK:03968")]:
        path = tmp_path / f"screening/{market}/value-quality/pool.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"companies": [{"symbol": symbol, "issuer": "CN:600036"}]}))
    cn = ResearchFlow(tmp_path)
    cn.register_universe([CompanyRef("CN:600036")], at=AT)
    cn.enqueue_research(
        [ResearchRequest("CN:600036", "周期")],
        report_period="2026-H1",
        trigger_kind=PERIODIC_TRIGGER,
        at=AT,
    )
    hk = ResearchFlow(tmp_path, market="hk")
    hk.register_universe([CompanyRef("HK:03968")], at=AT)
    basis = {
        "period_end": "2026-06-30",
        "published_on": "2026-08-01",
        "source_url": "https://example.com/h1",
    }
    with pytest.raises(ValidationError, match="issuer"):
        hk.enqueue_research(
            [ResearchRequest("HK:03968", "周期", financial_basis=basis)],
            report_period="2026-H1",
            trigger_kind=PERIODIC_TRIGGER,
            at=AT,
        )
