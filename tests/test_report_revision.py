from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest

from trading_os import report_revision
from trading_os.report_revision import revise_current
from trading_os.research_assets.research_flow import (
    ResearchFlow,
    ResearchResult,
    ResearchUpdate,
    ReturnModel,
    ScreenDecision,
    ValidationError,
    ValueRange,
)

AT = "2026-08-28T17:00:00+08:00"
EVENT = "2026-09-01T17:00:00+08:00"
REVIEW = "2026-09-15T17:00:00+08:00"
SYMBOL = "CN:000001"


def _result(symbol: str = SYMBOL) -> ResearchResult:
    return ResearchResult(
        symbol=symbol,
        name="示例公司",
        outcome="covered",
        information_cutoff=AT,
        summary="现金回收尚待核实。",
        key_logic=("认证使替换需要时间",),
        risks=("客户可能要求降低价格",),
        value_range=ValueRange(low=10, high=15),
        return_model=None,
        return_model_note="资本预算未披露，无法可靠约束未来分配及终值。",
        event_triggers=("定期财报披露",),
        source_urls=("https://example.com/interim-report",),
        report_markdown=(
            "# 示例公司\n\n信息截止：2026-08-28\n\n"
            "## 一句话结论\n\n现金回收尚待核实。\n\n"
            "## 商业与竞争\n\n认证使替换需要时间，未能证明长期定价权。\n\n"
            "## 财务质量\n\n2026年半年收入100亿元，但应收增加。\n\n"
            "## 估值\n\n方法一为正常化PE，方法二为现金流折现，以正常化PE为核心。\n\n"
            "核心合理价值区间：10—15元。\n\n"
            "### 基准持有人回报模型输入\n\n"
            "资本预算未披露，无法可靠约束未来分配及终值。\n\n"
            "## 核心风险\n\n客户可能要求降低价格。\n\n"
            "## 来源清单\n\nhttps://example.com/interim-report\n"
        ),
    )


def _complete(flow: ResearchFlow, result: ResearchResult) -> dict:
    task = flow.apply_screening(
        [ScreenDecision(result.symbol, "research_now", "核验现金回收")],
        screen_id=result.symbol,
        mode="event",
        at=AT,
    ).enqueued_tasks[0]
    flow.dispatch_tasks(limit=1, at=AT)
    return flow.apply_result(result, task_id=task.task_id, at=AT)


@pytest.fixture
def case(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    original = _result()
    state = _complete(flow, original)
    report = tmp_path / state["report_path"]
    candidate = replace(
        original,
        summary="低现金回收削弱价值创造。",
        key_logic=("认证壁垒不足以抵消长期应收占用",),
        risks=("收入增长持续消耗股东资本",),
        report_markdown=original.report_markdown.replace(
            "现金回收尚待核实。", "低现金回收削弱价值创造。"
        ),
    )
    return flow, state, report, candidate


def _run(case, **overrides):
    flow, state, report, candidate = case
    kwargs = {
        "allowed_reports": {SYMBOL: state["report_path"]},
        "expected_report": report.read_text(encoding="utf-8"),
        "reviewed_at": REVIEW,
        "rationale": "原有信息下重新核验现金回收与竞争机制。",
    }
    kwargs.update(overrides)
    return revise_current(flow.root, candidate, **kwargs)


def _snapshot(flow, report):
    return {
        path: path.read_bytes() if path.exists() else None
        for path in (report, flow.state_path, flow.watchlist_path, flow.queue_path)
    }


def test_revision_updates_current_state_and_projection_only(case):
    flow, state, report, candidate = case
    other = _complete(flow, _result("CN:000002"))
    historic = report.parent / "2026-08-01.md"
    historic.write_text("历史报告不变", encoding="utf-8")
    queue = flow.queue_path.read_bytes()
    actual = _run(case)
    assert actual["report_path"] == state["report_path"]
    assert actual["information_cutoff"] == AT
    assert actual["last_research_at"] == actual["updated_at"] == REVIEW
    assert actual["last_revision"]["reviewed_at"] == REVIEW
    assert actual["summary"] == candidate.summary
    assert actual["key_logic"] == list(candidate.key_logic)
    assert actual["risks"] == list(candidate.risks)
    assert report.read_text(encoding="utf-8") == candidate.report_markdown
    assert historic.read_text(encoding="utf-8") == "历史报告不变"
    assert flow._states()["CN:000002"] == other
    assert flow.queue_path.read_bytes() == queue
    assert flow.read_watchlist()[0]["summary"] == candidate.summary
    flow.validate()


def test_revision_outcome_changes_watchlist(case):
    flow, state, report, candidate = case
    revised = (flow, state, report, replace(candidate, outcome="ignore"))
    assert _run(revised)["status"] == "ignore"
    assert flow.read_watchlist() == ()
    assert _run(case)["status"] == "covered"
    assert len(flow.read_watchlist()) == 1


def test_revision_updates_valuation_and_model_with_body(case):
    flow, state, report, candidate = case
    note = "按扣除债务后的普通股终值估计，已折算未来完全稀释股数。"
    model = ReturnModel(
        schema_version=1,
        method="annual_common_equity_irr_v1",
        currency="CNY",
        model_as_of=AT,
        base_case_distributions_per_share=(0.1, 0.2, 0.3, 0.4, 0.5),
        base_case_terminal_equity_value_range_per_share={"year_5": {"low": 14, "high": 18}},
    )
    candidate = replace(
        candidate,
        value_range=ValueRange(low=8, high=12),
        return_model=model,
        return_model_note=note,
        valuation_note="按更新的现金回收与资本效率研究假设修订。",
        event_triggers=("客户回款条款变化",),
        source_urls=("https://example.com/interim-report", "https://example.com/contract"),
        report_markdown=candidate.report_markdown.replace("10—15元", "8—12元").replace(
            "资本预算未披露，无法可靠约束未来分配及终值。",
            "未来五年每股分配0.1、0.2、0.3、0.4、0.5元；第五年末终值14—18元。" + note,
        ),
    )
    revised = _run((flow, state, report, candidate))
    projected = flow.read_watchlist()[0]
    assert revised["value_range"]["low"] == 8
    assert revised["return_model"]["base_case_distributions_per_share"] == [0.1, 0.2, 0.3, 0.4, 0.5]
    for key in (
        "value_range",
        "return_model",
        "return_model_note",
        "source_urls",
        "event_triggers",
    ):
        assert projected[key] == revised[key]
    assert "8—12元" in report.read_text(encoding="utf-8")
    flow.validate()


@pytest.mark.parametrize(
    "scope",
    [
        {},
        {SYMBOL: "research/companies/CN/000001/legacy/2026-08-28.md"},
        {SYMBOL: "research/companies/CN/000002/reports/2026-08-28.md"},
        {SYMBOL: "research/companies/CN/000001/reports/../../outside.md"},
        {SYMBOL: "/tmp/2026-08-28.md"},
        {SYMBOL: "C:/outside/2026-08-28.md"},
    ],
)
def test_revision_rejects_unauthorized_or_invalid_path(case, scope):
    flow, _, report, _ = case
    before = _snapshot(flow, report)
    with pytest.raises(ValidationError):
        _run(case, allowed_reports=scope)
    assert _snapshot(flow, report) == before


def test_revision_rejects_old_report_even_if_manifest_allows_it(case):
    flow, _, report, _ = case
    newer = report.parent / "2026-09-01.md"
    newer.write_text("已产生较新报告", encoding="utf-8")
    before = _snapshot(flow, report)
    with pytest.raises(ValidationError, match="older"):
        _run(case)
    assert _snapshot(flow, report) == before


def test_revision_rejects_changed_current_pointer(case):
    flow, state, report, _ = case
    states = flow._states()
    new_path = report.parent / "2026-09-01.md"
    new_path.write_text(report.read_text(encoding="utf-8"), encoding="utf-8")
    states[SYMBOL]["report_path"] = new_path.relative_to(flow.root).as_posix()
    flow._write_states(states)
    before = _snapshot(flow, report)
    with pytest.raises(ValidationError, match="no longer"):
        _run(case, allowed_reports={SYMBOL: state["report_path"]})
    assert _snapshot(flow, report) == before


def test_revision_rejects_changed_text_and_competing_audit(case):
    flow, state, report, candidate = case
    original = report.read_text(encoding="utf-8")

    def run():
        try:
            revise_current(
                flow.root,
                candidate,
                allowed_reports={SYMBOL: state["report_path"]},
                expected_report=original,
                reviewed_at=REVIEW,
                rationale="复核现金",
            )
            return "saved"
        except ValidationError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: run(), range(2)))
    assert results.count("saved") == 1
    assert sum("changed since" in result for result in results) == 1
    flow.validate()


def test_revision_rejects_cutoff_changes(case):
    flow, state, report, candidate = case
    new = replace(
        candidate,
        information_cutoff=EVENT,
        report_markdown=candidate.report_markdown.replace("2026-08-28", "2026-09-01"),
    )
    before = _snapshot(flow, report)
    with pytest.raises(ValidationError, match="original information_cutoff"):
        _run((flow, state, report, new))
    assert _snapshot(flow, report) == before


@pytest.mark.parametrize(
    "overrides",
    [{"reviewed_at": "2026-08-01T00:00:00+08:00"}, {"rationale": " "}, {"expected_report": " "}],
)
def test_revision_requires_current_review_time_and_explicit_reason(case, overrides):
    with pytest.raises(ValidationError):
        _run(case, **overrides)


def test_revision_runs_full_result_validation(case):
    flow, state, report, candidate = case
    before = _snapshot(flow, report)
    invalid = replace(candidate, value_range=ValueRange(low=40, high=60))
    with pytest.raises(ValidationError, match="match value_range"):
        _run((flow, state, report, invalid))
    assert _snapshot(flow, report) == before


def _invalidate(flow):
    flow.record_update(
        ResearchUpdate(
            symbol=SYMBOL,
            title="新事实改变旧判断",
            impact="invalidated",
            reviewed_at=EVENT,
            information_cutoff=EVENT,
            summary="新合同损害现金回收。",
            analysis="新合同越过原报告假设。",
            conclusion="等待完整更新。",
            source_urls=("https://example.com/new-contract",),
            event_ids=("new-contract",),
            invalidation_reason="新合同越过原报告假设。",
        )
    )


@pytest.mark.parametrize("outcome", ["covered", "ignore"])
def test_stale_report_remains_stale_with_unchanged_invalidation_and_queue(case, outcome):
    flow, state, report, candidate = case
    _invalidate(flow)
    previous = flow._states()[SYMBOL]
    queue = flow.queue_path.read_bytes()
    revised = _run((flow, state, report, replace(candidate, outcome=outcome)))
    assert revised["status"] == "stale"
    assert revised["invalidation"] == previous["invalidation"]
    assert revised["last_update"] == previous["last_update"]
    assert revised["processed_triggers"] == previous["processed_triggers"]
    assert flow.queue_path.read_bytes() == queue
    assert not flow.read_watchlist()
    flow.validate()


def test_revision_rejects_running_company(case):
    flow, _, report, _ = case
    _invalidate(flow)
    flow.dispatch_tasks(limit=1, at=EVENT)
    before = _snapshot(flow, report)
    with pytest.raises(ValidationError, match="running"):
        _run(case)
    assert _snapshot(flow, report) == before


@pytest.mark.parametrize("stage", ["report", "state", "watchlist", "validation"])
def test_failed_revision_restores_exact_bytes(case, monkeypatch, stage):
    flow, _, report, _ = case
    # Preserve the original newline representation during rollback as well.
    report.write_bytes(report.read_bytes().replace(b"\n", b"\r\n"))
    before = _snapshot(flow, report)

    if stage == "report":

        def fail_report(path, text):
            path.write_text(text, encoding="utf-8")
            raise OSError("report write failed")

        monkeypatch.setattr(report_revision, "_atomic_write_text", fail_report)
    elif stage in {"state", "watchlist"}:
        original_writer = ResearchFlow._write_states

        def fail_states(self, states):
            if stage == "state":
                self.state_path.write_text("partial state", encoding="utf-8")
            else:
                original_writer(self, states)
                self.watchlist_path.write_text("partial watchlist", encoding="utf-8")
            raise OSError("projection write failed")

        monkeypatch.setattr(ResearchFlow, "_write_states", fail_states)
    else:
        monkeypatch.setattr(
            ResearchFlow,
            "validate",
            lambda self: (_ for _ in ()).throw(ValidationError("validation failed")),
        )
    with pytest.raises((OSError, ValidationError)):
        _run(case)
    assert _snapshot(flow, report) == before


@pytest.mark.parametrize("link_kind", ["report", "parent", "state"])
def test_revision_rejects_symlinks(case, tmp_path, link_kind):
    flow, _, report, _ = case
    original = report.read_text(encoding="utf-8")
    path = {"report": report, "parent": report.parent, "state": flow.state_path}[link_kind]
    external = tmp_path.parent / f"{tmp_path.name}-{link_kind}-original"
    path.rename(external)
    try:
        path.symlink_to(external, target_is_directory=external.is_dir())
    except OSError:
        external.rename(path)
        pytest.skip("symlink creation is unavailable")
    try:
        with pytest.raises(ValidationError, match="symlink|junction"):
            _run(case, expected_report=original)
    finally:
        path.unlink()
        external.rename(path)


def test_revision_preserves_security_identity_and_other_metadata(case):
    flow, state, report, candidate = case
    states = flow._states()
    states[SYMBOL]["universe_status"] = "inactive"
    states[SYMBOL]["industry"] = "原始行业"
    states[SYMBOL]["custom_metadata"] = {"user": "retain"}
    flow._write_states(states)
    revised = _run((flow, state, report, replace(candidate, name="改名不是本轮审核职责")))
    assert revised["name"] == "示例公司"
    assert revised["industry"] == "原始行业"
    assert revised["universe_status"] == "inactive"
    assert revised["custom_metadata"] == {"user": "retain"}
    assert not flow.read_watchlist()
    assert json.loads(flow.state_path.read_text(encoding="utf-8"))["last_revision"]
