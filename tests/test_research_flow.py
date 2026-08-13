from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from itertools import count
from pathlib import Path

import pytest

from trading_os.research_assets.research_flow import (
    CompanyRef,
    ResearchFlow,
    ResearchResult,
    ResearchUpdate,
    ScreenDecision,
    StateCorruptionError,
    TaskStatus,
    ValidationError,
    ValueRange,
)

AT = "2026-08-08T17:00:00+08:00"
LATER = "2026-08-09T17:00:00+08:00"
_TRIGGER_IDS = count()


def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _covered(symbol: str) -> ResearchResult:
    return ResearchResult(
        symbol=symbol,
        name="示例公司",
        outcome="covered",
        information_cutoff=AT,
        summary="需求增长成立，但现金流转化仍需后续财报验证。",
        key_logic=("核心产品需求增长", "现金流转化决定估值上限"),
        risks=("客户集中", "资本开支回报不及预期"),
        value_range=ValueRange(low=58, high=82),
        event_triggers=("下一期财报发布", "大客户订单显著变化"),
        source_urls=("https://example.com/annual-report",),
        report_markdown=(
            "# 示例公司完整研究\n\n"
            "## 商业与竞争\n\n核心产品需求增长，竞争位置取决于客户验证。\n\n"
            "## 财务与估值\n\n现金流转化决定估值上限。\n\n"
            "## 风险\n\n客户集中，且资本开支回报仍待验证。"
        ),
    )


def _ignored(symbol: str) -> ResearchResult:
    return ResearchResult(
        symbol=symbol,
        name="示例公司",
        outcome="ignore",
        information_cutoff=AT,
        summary="正式研究后仍不值得持续覆盖。",
        key_logic=("增长依赖持续融资",),
        risks=("普通股持续稀释",),
        value_range=None,
        valuation_note="无法建立不依赖外部融资的普通股价值。",
        event_triggers=("下一份年报显示自由现金流持续转正",),
        source_urls=("https://example.com/annual-report",),
        report_markdown="# 示例公司完整研究\n\n业务、财务、治理、估值和风险均已独立说明。",
    )


def _complete(flow: ResearchFlow, result: ResearchResult, *, at: str = AT) -> dict:
    update = flow.apply_screening(
        [ScreenDecision(result.symbol, "research_now", "完成统一标准研究", name=result.name)],
        screen_id=f"test-{next(_TRIGGER_IDS)}",
        mode="event",
        at=at,
    )
    task = update.enqueued_tasks[0]
    assert flow.dispatch_tasks(limit=1, at=at)[0].task_id == task.task_id
    return flow.apply_result(result, task_id=task.task_id, at=at)


def _update(symbol: str, impact: str = "reaffirmed") -> ResearchUpdate:
    return ResearchUpdate(
        symbol=symbol,
        title="重大合同公告核对",
        impact=impact,
        reviewed_at=LATER,
        information_cutoff=LATER,
        summary="公司披露一项合同，规模仍在原报告情景内。",
        analysis="事件没有改变正常化利润、价值区间、核心逻辑或风险排序。",
        conclusion="当前正式报告继续有效。",
        source_urls=("https://example.com/announcement",),
        event_ids=("event-001",),
        invalidation_reason=("新事实越过原报告边界" if impact == "invalidated" else None),
    )


def test_screening_creates_only_ignore_or_candidate_and_deduplicates(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    flow.register_universe(
        [CompanyRef("CN:000001", "甲公司"), CompanyRef("CN:000002", "乙公司")], at=AT
    )
    update = flow.apply_screening(
        [
            ScreenDecision("CN:000001", "ignore", "当前不值得正式研究"),
            ScreenDecision("CN:000002", "research_now", "现金流问题值得正式研究"),
        ],
        screen_id="baseline",
        at=AT,
    )
    assert (update.ignored, update.candidates) == (1, 1)
    assert [task.symbol for task in flow.list_tasks()] == ["CN:000002"]

    def repeat():
        return flow.apply_screening(
            [ScreenDecision("CN:600000", "research_now", "半年报可能显示变化")],
            screen_id="event-one",
            mode="event",
            at=AT,
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        returned = list(executor.map(lambda _: repeat(), range(12)))
    assert sum(len(item.enqueued_tasks) for item in returned) == 1


def test_dispatch_from_end_and_requeue_are_explicit(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    symbols = ["CN:000001", "CN:000002", "CN:000003"]
    flow.apply_screening(
        [ScreenDecision(symbol, "research_now", "值得研究") for symbol in symbols],
        screen_id="three",
        mode="event",
        at=AT,
    )
    tail = {task.task_id for task in flow.list_tasks()[-2:]}
    running = flow.dispatch_tasks(limit=2, at=AT, from_end=True)
    assert {task.task_id for task in running} == tail
    restored = flow.requeue_task(running[0].task_id)
    assert restored.status is TaskStatus.QUEUED and restored.started_at is None


def test_formal_result_is_self_contained_and_watchlist_has_no_price_state(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    state = _complete(flow, _covered("CN:601138"))
    assert state["status"] == "covered"
    assert state["value_range"] == {"low": 58.0, "high": 82.0, "currency": "CNY"}
    assert "price_levels" not in state and "price_monitor" not in state
    assert (tmp_path / state["report_path"]).is_file()
    watch = flow.read_watchlist()[0]
    assert watch["report_path"] == state["report_path"]
    assert "price_levels" not in watch and "price_monitor" not in watch
    flow.validate()


def test_formal_report_cannot_defer_analysis_to_history(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    bad = replace(
        _covered("CN:601138"),
        report_markdown=(
            "# 裁决版\n\n本次裁决不重复发明第三套商业事实。"
            "完整业务分析可沿时间线回看两份前序报告。"
        ),
    )
    with pytest.raises(ValidationError, match="self-contained"):
        flow.apply_result(bad, task_id="missing", at=AT)
    assert not flow.state_path.exists()


def test_new_formal_report_cannot_restore_a_price_review_line(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    bad = replace(
        _covered("CN:601138"),
        report_markdown="# 完整研究\n\n核心合理价值区间 58—82 元，关注价格 55 元。",
    )
    with pytest.raises(ValidationError, match="security-price trigger"):
        flow.apply_result(bad, task_id="missing", at=AT)
    assert not flow.state_path.exists()


@pytest.mark.parametrize(
    "trigger",
    ["收盘价跌至 50 元", "股价回到合理区间下沿", "关注价触发后重新武装"],
)
def test_security_price_is_not_a_research_trigger(tmp_path: Path, trigger: str):
    flow = ResearchFlow(tmp_path)
    with pytest.raises(ValidationError, match="security-price"):
        flow.apply_screening(
            [ScreenDecision("CN:000001", "research_now", "研究", event_triggers=(trigger,))],
            screen_id="price-trigger",
            mode="event",
            at=AT,
        )
    assert not flow.state_path.exists()


def test_business_and_industry_prices_remain_valid_triggers(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    update = flow.apply_screening(
        [
            ScreenDecision(
                "CN:000001",
                "research_now",
                "经营变量变化",
                event_triggers=("铜价持续高于每吨 10 万元", "产品售价显著下调"),
            )
        ],
        screen_id="operating-price",
        mode="event",
        at=AT,
    )
    assert len(update.enqueued_tasks) == 1


def test_reaffirmed_update_writes_log_without_changing_formal_state(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    before = _complete(flow, _covered("CN:601138"))
    record = flow.record_update(_update("CN:601138"))
    after = flow.read_states()[0]
    assert record.impact.value == "reaffirmed"
    assert record.status.value == "covered" and record.enqueued_task is None
    assert after["report_path"] == before["report_path"]
    assert after["information_cutoff"] == before["information_cutoff"]
    assert after["value_range"] == before["value_range"]
    text = (tmp_path / record.update_path).read_text(encoding="utf-8")
    assert "确认原报告" in text and before["report_path"] in text
    flow.validate()


def test_monitor_update_also_leaves_current_conclusion_untouched(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    before = _complete(flow, _covered("CN:601138"))
    record = flow.record_update(_update("CN:601138", "monitor"))
    after = flow.read_states()[0]
    assert record.impact.value == "monitor"
    assert after == before
    assert flow.list_tasks() == ()


def test_update_event_ids_are_idempotent(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    _complete(flow, _covered("CN:601138"))
    flow.record_update(_update("CN:601138"))
    with pytest.raises(ValidationError, match="already recorded"):
        flow.record_update(_update("CN:601138", "monitor"))
    assert len(list((tmp_path / "research/companies/CN/601138/updates").iterdir())) == 1


def test_invalidated_update_marks_stale_and_enqueues_one_full_research(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    before = _complete(flow, _covered("CN:601138"))
    record = flow.record_update(_update("CN:601138", "invalidated"))
    state = flow.read_states()[0]
    assert record.status.value == "stale"
    assert state["report_path"] == before["report_path"]
    assert state["invalidation"]["update_path"] == record.update_path
    assert record.enqueued_task is not None
    assert record.enqueued_task.trigger_kind == "update"
    assert len(flow.list_tasks()) == 1
    assert flow.read_watchlist() == ()
    flow.validate()


def test_stale_cannot_be_reaffirmed_and_update_cannot_predate_report(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    _complete(flow, _covered("CN:601138"))
    flow.record_update(_update("CN:601138", "invalidated"))
    with pytest.raises(ValidationError, match="stale company"):
        flow.record_update(replace(_update("CN:601138"), event_ids=("event-002",)))

    other = ResearchFlow(tmp_path / "other")
    _complete(other, _covered("CN:601138"))
    with pytest.raises(ValidationError, match="predates"):
        other.record_update(
            replace(
                _update("CN:601138"),
                reviewed_at="2026-08-08T18:00:00+08:00",
                information_cutoff="2026-08-07T17:00:00+08:00",
            )
        )


def test_same_day_full_refresh_appends_complete_report(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    first = _complete(flow, _covered("CN:601138"))
    refresh = flow.apply_screening(
        [ScreenDecision("CN:601138", "research_now", "财报改变估值")],
        screen_id="same-day-refresh",
        mode="event",
        at=AT,
    )
    flow.dispatch_tasks(limit=1, at=AT)
    second = flow.apply_result(
        replace(_covered("CN:601138"), value_range=ValueRange(62, 88)),
        task_id=refresh.enqueued_tasks[0].task_id,
        at=AT,
    )
    assert first["report_path"].endswith("2026-08-08.md")
    assert second["report_path"].endswith("2026-08-08-02.md")
    assert second["value_range"]["low"] == 62
    flow.validate()


def test_screening_cannot_change_a_formal_outcome_to_ignore(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    before = _complete(flow, _covered("CN:601138"))
    with pytest.raises(ValidationError, match="full research task"):
        flow.apply_screening(
            [ScreenDecision("CN:601138", "ignore", "事件看起来负面")],
            screen_id="direct-ignore",
            mode="event",
            at=LATER,
        )
    assert flow.read_states()[0] == before


def test_ignore_keeps_formal_report_outside_watchlist(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    state = _complete(flow, _ignored("CN:000333"))
    assert state["status"] == "ignore"
    assert (tmp_path / state["report_path"]).is_file()
    assert flow.read_watchlist() == ()
    flow.validate()


def test_v2_to_v3_migration_removes_price_state_and_only_security_price_triggers(
    tmp_path: Path,
):
    state_path = tmp_path / "coverage/cn-a/research_state.jsonl"
    state_path.parent.mkdir(parents=True)
    report_path = tmp_path / "research/companies/CN/000001/reports/2026-08-08.md"
    report_path.parent.mkdir(parents=True)
    report_path.write_text(
        "# 完整研究\n\n独立说明业务、财务、治理、估值和风险。\n",
        encoding="utf-8",
    )
    row = {
        "schema_version": 2,
        "symbol": "CN:000001",
        "name": "示例公司",
        "universe_status": "active",
        "status": "covered",
        "updated_at": AT,
        "summary": "已有研究",
        "key_logic": ["逻辑"],
        "risks": ["风险"],
        "value_range": {"low": 10.0, "high": 20.0, "currency": "CNY"},
        "valuation_note": None,
        "price_levels": [{"id": "attention", "threshold": 10}],
        "price_monitor": {"levels": {}},
        "event_triggers": ["收盘价跌至 10 元", "铜价持续上涨", "下一期财报"],
        "source_urls": ["https://example.com/report"],
        "last_screening": {
            "event_triggers": ["股价回到低位", "产品售价下调"],
            "price_levels": [{"id": "attention", "threshold": 10}],
        },
        "last_research_at": AT,
        "information_cutoff": AT,
        "report_path": "research/companies/CN/000001/reports/2026-08-08.md",
        "candidate_since": None,
        "invalidation": None,
        "processed_triggers": [],
    }
    state_path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    flow = ResearchFlow(tmp_path)
    assert flow.migrate_state_v3(at=LATER) == 1
    state = flow.read_states()[0]
    assert state["schema_version"] == 3
    assert "price_levels" not in state and "price_monitor" not in state
    assert state["event_triggers"] == ["铜价持续上涨", "下一期财报"]
    assert state["last_screening"]["event_triggers"] == ["产品售价下调"]
    assert "price_levels" not in state["last_screening"]
    flow.validate()


def test_validation_detects_corrupt_projection_and_duplicate_tasks(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    _complete(flow, _covered("CN:601138"))
    flow.watchlist_path.write_text("", encoding="utf-8")
    with pytest.raises(StateCorruptionError, match="watchlist is not"):
        flow.validate()

    other = ResearchFlow(tmp_path / "other")
    other.apply_screening(
        [ScreenDecision("CN:000001", "research_now", "第一次研究")],
        screen_id="first",
        mode="event",
        at=AT,
    )
    rows = _rows(other.queue_path)
    trigger_key = "screen:second"
    duplicate = {
        **rows[0],
        "task_id": hashlib.sha256(f"CN:000001\0{trigger_key}".encode()).hexdigest()[:24],
        "trigger_id": "second",
    }
    other.queue_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in [*rows, duplicate]) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(StateCorruptionError, match="more than one current task"):
        other.validate()


@pytest.mark.parametrize(
    "result, match",
    [
        (replace(_covered("CN:000001"), risks=()), "at least one risk"),
        (
            replace(_covered("CN:000001"), value_range=None, valuation_note=None),
            "value_range or valuation_note",
        ),
        (replace(_covered("CN:000001"), source_urls=("not-a-url",)), "absolute http"),
    ],
)
def test_invalid_results_fail_before_state_write(
    tmp_path: Path, result: ResearchResult, match: str
):
    flow = ResearchFlow(tmp_path)
    with pytest.raises(ValidationError, match=match):
        flow.apply_result(result, task_id="missing", at=AT)
    assert not flow.state_path.exists()


def test_duplicate_state_fails_closed(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    flow.state_path.parent.mkdir(parents=True)
    row = {
        "schema_version": 3,
        "symbol": "CN:000001",
        "universe_status": "active",
        "status": "ignore",
    }
    flow.state_path.write_text(json.dumps(row) + "\n" + json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(StateCorruptionError, match="duplicate state"):
        flow.read_states()
