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


def _model(as_of: str = AT) -> ReturnModel:
    return ReturnModel(
        schema_version=1,
        method="annual_common_equity_irr_v1",
        currency="CNY",
        model_as_of=as_of,
        base_case_distributions_per_share=(1, 1.1, 1.2, 1.3, 1.4),
        base_case_terminal_equity_value_range_per_share={
            "year_5": {"low": 72, "high": 92}
        },
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
    assert flow.list_tasks() == ()
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
        report_markdown=_result("CN:000001", at=AT).report_markdown.replace(
            "58—82", "62—88"
        ),
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
        ResearchFlow._normalized_result(
            _result("CN:000001", "2026-Q3", at=AT)
        )


def test_validation_rejects_retired_event_fields(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    flow.state_path.parent.mkdir(parents=True)
    row = {
        "schema_version": 5,
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
