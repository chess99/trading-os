from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import date
from itertools import count
from pathlib import Path

import pytest

from trading_os.research_assets.research_flow import (
    CompanyRef,
    PriceLevel,
    ResearchFlow,
    ResearchResult,
    ScreenDecision,
    StateCorruptionError,
    TaskStatus,
    ValidationError,
    ValueRange,
)

AT = "2026-08-08T17:00:00+08:00"
_TRIGGER_IDS = count()


def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _researched(symbol: str) -> ResearchResult:
    return ResearchResult(
        symbol=symbol,
        name="示例公司",
        outcome="researched",
        summary="需求增长成立，但现金流转化仍需后续财报验证。",
        key_logic=("核心产品需求增长", "现金流转化决定估值上限"),
        risks=("客户集中", "资本开支回报不及预期"),
        value_range=ValueRange(low=58, high=82),
        buy_below=55,
        rearm_above=57,
        event_triggers=("下一期财报发布", "大客户订单显著变化"),
        source_urls=(
            "https://example.com/annual-report",
            "https://example.com/company-announcement",
        ),
        report_markdown=(
            "# 示例公司研究\n\n"
            "核心逻辑是需求增长，估值上限取决于利润向自由现金流的转化。\n\n"
            "## 风险\n\n客户集中，且资本开支回报仍待验证。"
        ),
    )


def _complete(
    flow: ResearchFlow,
    result: ResearchResult,
    *,
    at: str = AT,
) -> dict:
    update = flow.apply_screening(
        [
            ScreenDecision(
                result.symbol,
                "research_now",
                "测试中的主 Agent 已决定派发",
                name=result.name,
            )
        ],
        screen_id=f"test-{next(_TRIGGER_IDS)}",
        mode="event",
        at=at,
    )
    assert len(update.enqueued_tasks) == 1
    task = update.enqueued_tasks[0]
    dispatched = flow.dispatch_tasks(limit=1, at=at)
    assert [item.task_id for item in dispatched] == [task.task_id]
    return flow.apply_result(result, task_id=task.task_id, at=at)


def test_manager_screening_only_queues_research_now_and_derives_watchlist(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    assert (
        flow.register_universe(
            [
                CompanyRef("CN:000001", "甲公司"),
                CompanyRef("CN:000002", "乙公司"),
                CompanyRef("CN:000003", "丙公司"),
            ],
            at=AT,
        )
        == 3
    )

    update = flow.apply_screening(
        [
            ScreenDecision("CN:000001", "ignore", "商业模式暂不值得继续看"),
            ScreenDecision(
                "CN:000002",
                "watch",
                "质量尚可，等待更低价格",
                buy_below=12,
                event_triggers=("利润率显著改善",),
            ),
            ScreenDecision("CN:000003", "research_now", "出现值得核实的行业拐点"),
        ],
        screen_id="close-2026-08-08",
        at=AT,
    )

    assert (update.total, update.ignored, update.watched, update.research_now) == (3, 1, 1, 1)
    assert [task.symbol for task in update.enqueued_tasks] == ["CN:000003"]
    assert [task.symbol for task in flow.list_tasks()] == ["CN:000003"]
    assert {row["symbol"]: row["status"] for row in flow.read_states()} == {
        "CN:000001": "ignore",
        "CN:000002": "watch",
        "CN:000003": "unseen",
    }
    assert [row["symbol"] for row in flow.read_watchlist()] == ["CN:000002"]
    assert (tmp_path / "coverage/cn-a/research_state.jsonl").exists()
    assert (tmp_path / "research/watchlist.jsonl").exists()


def test_baseline_only_accepts_unseen_companies_and_fails_the_whole_batch(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    flow.register_universe(
        [CompanyRef("CN:000001"), CompanyRef("CN:000002")],
        at=AT,
    )
    flow.apply_screening(
        [ScreenDecision("CN:000001", "ignore", "当前不值得继续研究")],
        screen_id="baseline-1",
        at=AT,
    )
    before = flow.read_states()

    with pytest.raises(ValidationError, match="only accepts unseen companies: CN:000001"):
        flow.apply_screening(
            [
                ScreenDecision(
                    "CN:000002",
                    "watch",
                    "等待价格",
                    buy_below=10,
                ),
                ScreenDecision("CN:000001", "research_now", "重复覆盖"),
            ],
            screen_id="baseline-2",
            at="2026-08-09T17:00:00+08:00",
        )

    assert flow.read_states() == before
    assert flow.read_watchlist() == ()
    assert flow.list_tasks() == ()

    event_update = flow.apply_screening(
        [ScreenDecision("CN:000001", "research_now", "重大事件需要重看")],
        screen_id="event-1",
        mode="event",
        at="2026-08-09T18:00:00+08:00",
    )
    assert [task.symbol for task in event_update.enqueued_tasks] == ["CN:000001"]

    flow.apply_screening(
        [ScreenDecision("CN:000002", "research_now", "首次基线判断")],
        screen_id="baseline-3",
        at="2026-08-10T17:00:00+08:00",
    )
    with pytest.raises(ValidationError, match="only accepts unseen companies: CN:000002"):
        flow.apply_screening(
            [ScreenDecision("CN:000002", "research_now", "重复基线判断")],
            screen_id="baseline-4",
            at="2026-08-11T17:00:00+08:00",
        )


def test_symbol_and_trigger_are_deduplicated_under_concurrent_screening(tmp_path: Path):
    flow = ResearchFlow(tmp_path)

    def screen():
        return flow.apply_screening(
            [ScreenDecision("CN:600000", "research_now", "半年报可能显示基本面变化")],
            screen_id="2026-h1-results",
            mode="event",
            at=AT,
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        returned = list(executor.map(lambda _: screen(), range(16)))

    assert sum(len(update.enqueued_tasks) for update in returned) == 1
    assert sum(update.deduplicated for update in returned) == 15
    assert len(flow.list_tasks()) == 1

    repeated_screen = flow.apply_screening(
        [ScreenDecision("CN:600001", "research_now", "需要研究")],
        screen_id="batch-1",
        mode="event",
        at=AT,
    )
    repeated_screen_again = flow.apply_screening(
        [ScreenDecision("CN:600001", "research_now", "需要研究")],
        screen_id="batch-1",
        mode="event",
        at=AT,
    )
    assert len(repeated_screen.enqueued_tasks) == 1
    assert repeated_screen_again.deduplicated == 1


def test_single_worker_result_updates_state_and_removes_current_task(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    update = flow.apply_screening(
        [
            ScreenDecision(
                "CN:601138",
                "research_now",
                "AI服务器现金流值得深入核实",
                name="工业富联",
            )
        ],
        screen_id="manager-2026-08-08",
        at=AT,
    )
    queued = update.enqueued_tasks[0]

    dispatched = flow.dispatch_tasks(limit=1, at="2026-08-08T17:01:00+08:00")
    assert len(dispatched) == 1
    assert dispatched[0].task_id == queued.task_id
    assert dispatched[0].status is TaskStatus.DISPATCHED

    state = flow.apply_result(
        _researched("CN:601138"),
        task_id=dispatched[0].task_id,
        at="2026-08-08T17:25:00+08:00",
    )

    assert state["status"] == "researched"
    assert "detail_level" not in state
    assert state["value_range"] == {"low": 58.0, "high": 82.0, "currency": "CNY"}
    assert state["price_levels"] == [
        {"id": "buy", "label": "买入触发", "threshold": 55.0, "rearm_above": 57.0}
    ]
    assert state["report_path"] == "research/companies/CN/601138/current.md"
    assert (
        (tmp_path / state["report_path"]).read_text(encoding="utf-8").startswith("# 示例公司研究")
    )
    assert state["processed_triggers"] == ["screen:manager-2026-08-08"]
    assert flow.list_tasks() == ()
    watch = flow.read_watchlist()[0]
    assert watch["symbol"] == "CN:601138"
    assert watch["event_triggers"] == ["下一期财报发布", "大客户订单显著变化"]
    assert watch["key_logic"] == ["核心产品需求增长", "现金流转化决定估值上限"]
    assert watch["risks"] == ["客户集中", "资本开支回报不及预期"]
    assert watch["report_path"] == state["report_path"]
    assert "detail_level" not in watch


def test_discard_requires_only_a_nonblank_summary(tmp_path: Path):
    flow = ResearchFlow(tmp_path)

    state = _complete(
        flow,
        ResearchResult(
            symbol="CN:000333",
            outcome="discard",
            summary="商业质量和估值都不值得继续投入。",
            key_logic=(),
            risks=(),
            value_range=None,
            event_triggers=(),
            source_urls=(),
        ),
        at=AT,
    )

    assert state["status"] == "ignore"
    assert state["key_logic"] == []
    assert state["source_urls"] == []
    assert state["event_triggers"] == []
    assert flow.read_watchlist() == ()


def test_dispatch_limit_is_caller_controlled_and_never_creates_one_symbol_twice(
    tmp_path: Path,
):
    flow = ResearchFlow(tmp_path)
    created = flow.apply_screening(
        [
            ScreenDecision("CN:000001", "research_now", "需要复核"),
            ScreenDecision("CN:000002", "research_now", "需要复核"),
            ScreenDecision("CN:000003", "research_now", "需要复核"),
        ],
        screen_id="event-a",
        mode="event",
        at=AT,
    )
    duplicate = flow.apply_screening(
        [ScreenDecision("CN:000001", "research_now", "另一事件仍需复核")],
        screen_id="event-b",
        mode="event",
        at=AT,
    )

    assert len(created.enqueued_tasks) == 3
    assert duplicate.enqueued_tasks == ()
    assert duplicate.deduplicated == 1
    assert len(flow.list_tasks()) == 3

    first = flow.dispatch_tasks(limit=2, at="2026-08-08T17:01:00+08:00")
    second = flow.dispatch_tasks(limit=2, at="2026-08-08T17:02:00+08:00")

    assert len(first) == 2
    assert len(second) == 1
    assert len({task.symbol for task in first + second}) == 3
    restored = flow.requeue_task(first[0].task_id)
    assert restored.status is TaskStatus.QUEUED
    assert restored.dispatched_at is None


def test_daily_close_scan_uses_edge_rearm_and_same_day_dedup(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    _complete(flow, _researched("CN:601138"), at=AT)

    assert (
        flow.scan_daily_close(
            {"CN:601138": 60}, trading_date=date(2026, 8, 10), at=AT
        )
        == ()
    )
    first = flow.scan_daily_close(
        {"CN:601138": 54},
        trading_date="2026-08-11",
        at=AT,
    )
    assert len(first) == 1
    assert first[0].level_id == "buy"
    assert (
        flow.scan_daily_close(
            {"CN:601138": 53}, trading_date="2026-08-11", at=AT
        )
        == ()
    )
    assert (
        flow.scan_daily_close(
            {"CN:601138": 52}, trading_date="2026-08-12", at=AT
        )
        == ()
    )

    # A close above the explicit rearm price creates no hit, but arms the next edge.
    assert (
        flow.scan_daily_close(
            {"CN:601138": 58}, trading_date="2026-08-13", at=AT
        )
        == ()
    )
    second = flow.scan_daily_close(
        {"CN:601138": 55}, trading_date="2026-08-14", at=AT
    )
    assert len(second) == 1
    assert flow.list_tasks() == ()
    watch_level = flow.read_watchlist()[0]["price_levels"][0]
    assert watch_level["last_close"] == 55.0
    assert watch_level["last_hit_date"] == "2026-08-14"


def test_each_price_level_has_an_independent_edge_and_hit(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    result = replace(
        _researched("CN:601138"),
        buy_below=None,
        rearm_above=None,
        price_levels=(
            PriceLevel("attention", "关注区", 55, 57),
            PriceLevel("high-conviction", "高吸引力区", 50, 52),
        ),
    )
    _complete(flow, result, at=AT)

    first = flow.scan_daily_close(
        {"CN:601138": 54}, trading_date="2026-08-11", at=AT
    )
    second = flow.scan_daily_close(
        {"CN:601138": 49}, trading_date="2026-08-12", at=AT
    )

    assert [(hit.level_id, hit.label) for hit in first] == [("attention", "关注区")]
    assert [(hit.level_id, hit.label) for hit in second] == [("high-conviction", "高吸引力区")]
    assert flow.list_tasks() == ()
    levels = flow.read_watchlist()[0]["price_levels"]
    assert [level["id"] for level in levels] == ["attention", "high-conviction"]
    assert levels[0]["last_hit_date"] == "2026-08-11"
    assert levels[1]["last_hit_date"] == "2026-08-12"


def test_daily_close_requires_every_monitored_company_and_fails_atomically(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    _complete(flow, _researched("CN:601138"), at=AT)
    _complete(flow, _researched("CN:000333"), at=AT)
    before = flow.read_watchlist()

    with pytest.raises(
        ValidationError,
        match="daily close input is missing monitored companies: CN:000333",
    ):
        flow.scan_daily_close(
            {"CN:601138": 54},
            trading_date="2026-08-11",
            at=AT,
        )

    assert flow.read_watchlist() == before
    hits = flow.scan_daily_close(
        {"CN:000333": 60, "CN:601138": 54},
        trading_date="2026-08-11",
        at=AT,
    )
    assert [(hit.symbol, hit.level_id) for hit in hits] == [("CN:601138", "buy")]
    assert flow.list_tasks() == ()


def test_event_routes_downgrade_research_and_cancel_stale_company_tasks(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    ignored = _complete(flow, _researched("CN:601138"), at=AT)
    watched = _complete(flow, _researched("CN:000333"), at=AT)
    old_reports = [tmp_path / ignored["report_path"], tmp_path / watched["report_path"]]

    queued = flow.apply_screening(
        [
            ScreenDecision("CN:601138", "research_now", "新事件需要复核"),
            ScreenDecision("CN:000333", "research_now", "新事件需要复核"),
        ],
        screen_id="refresh-before-new-judgment",
        mode="event",
        at="2026-08-09T17:00:00+08:00",
    )
    dispatched = flow.dispatch_tasks(limit=2, at="2026-08-09T17:01:00+08:00")
    assert {task.task_id for task in dispatched} == {
        task.task_id for task in queued.enqueued_tasks
    }

    flow.apply_screening(
        [
            ScreenDecision("CN:601138", "ignore", "基本面已经证伪"),
            ScreenDecision(
                "CN:000333",
                "watch",
                "暂时降为价格观察",
                buy_below=40,
                event_triggers=("下一期财报",),
            ),
        ],
        screen_id="announcement-2026-08-09",
        mode="event",
        at="2026-08-09T18:00:00+08:00",
    )
    states = {state["symbol"]: state for state in flow.read_states()}

    assert states["CN:601138"]["status"] == "ignore"
    assert states["CN:601138"]["summary"] == "基本面已经证伪"
    assert states["CN:601138"]["price_levels"] == []
    assert states["CN:601138"]["event_triggers"] == []
    assert states["CN:601138"]["price_monitor"] is None
    assert states["CN:000333"]["status"] == "watch"
    assert states["CN:000333"]["summary"] == "暂时降为价格观察"
    assert states["CN:000333"]["price_levels"][0]["threshold"] == 40.0
    assert states["CN:000333"]["report_path"] is None
    assert [row["symbol"] for row in flow.read_watchlist()] == ["CN:000333"]
    assert flow.list_tasks() == ()
    assert all(not report.exists() for report in old_reports)

    with pytest.raises(ValidationError, match="task is not current"):
        flow.apply_result(
            _researched("CN:601138"),
            task_id=dispatched[0].task_id,
            at="2026-08-09T18:01:00+08:00",
        )


def test_ignore_keeps_event_rescreen_conditions_but_stays_out_of_watchlist(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    flow.apply_screening(
        [
            ScreenDecision(
                "CN:000001",
                "ignore",
                "当前不值得研究",
                event_triggers=("下一份年报出现主营业务转型",),
            )
        ],
        screen_id="baseline",
        at=AT,
    )

    state = flow.read_states()[0]
    assert state["status"] == "ignore"
    assert state["event_triggers"] == ["下一份年报出现主营业务转型"]
    assert flow.read_watchlist() == ()


def test_result_downgrade_removes_the_former_current_report(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    researched = _complete(flow, _researched("CN:601138"), at=AT)
    report = tmp_path / researched["report_path"]
    assert report.exists()

    downgraded = _complete(
        flow,
        ResearchResult(
            symbol="CN:601138",
            outcome="watch",
            summary="现金流假设被削弱，退回观察。",
            key_logic=("收入增长尚未转化为现金流",),
            risks=("自由现金流持续为负",),
            value_range=None,
            buy_below=None,
            event_triggers=("后续财报现金流转正",),
            source_urls=("https://example.com/latest-results",),
        ),
        at="2026-08-09T18:00:00+08:00",
    )

    assert downgraded["status"] == "watch"
    assert downgraded["report_path"] is None
    assert not report.exists()


def test_read_only_validation_checks_reports_queue_and_watchlist_projection(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    _complete(flow, _researched("CN:601138"), at=AT)
    flow.apply_screening(
        [ScreenDecision("CN:000001", "research_now", "年报复核")],
        screen_id="annual-report",
        mode="event",
        at=AT,
    )

    status = flow.validate()
    assert (status.companies, status.researched, status.unseen) == (2, 1, 1)
    assert (status.watchlist, status.queued, status.dispatched) == (1, 1, 0)

    flow.watchlist_path.write_text("", encoding="utf-8")
    with pytest.raises(StateCorruptionError, match="watchlist is not"):
        flow.validate()


def test_validation_rejects_two_current_tasks_for_one_company(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    flow.apply_screening(
        [ScreenDecision("CN:000001", "research_now", "第一次研究判断")],
        screen_id="first-screen",
        mode="event",
        at=AT,
    )
    rows = _rows(flow.queue_path)
    trigger_key = "screen:second-screen"
    duplicate = {
        **rows[0],
        "task_id": hashlib.sha256(f"CN:000001\0{trigger_key}".encode()).hexdigest()[:24],
        "trigger_id": "second-screen",
    }
    flow.queue_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in [*rows, duplicate]) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(StateCorruptionError, match="more than one current task"):
        flow.validate()


@pytest.mark.parametrize(
    "result, match",
    [
        (
            ResearchResult(
                symbol="CN:000001",
                outcome="researched",
                summary="结论",
                key_logic=("逻辑",),
                risks=(),
                value_range=None,
                buy_below=None,
                event_triggers=(),
                source_urls=("https://example.com/source",),
            ),
            "value_range and price_levels",
        ),
        (
            ResearchResult(
                symbol="CN:000001",
                outcome="discard",
                summary="结论",
                key_logic=("逻辑",),
                risks=(),
                value_range=None,
                buy_below=None,
                event_triggers=(),
                source_urls=("not-a-url",),
            ),
            "absolute http",
        ),
    ],
)
def test_invalid_results_fail_before_any_state_write(
    tmp_path: Path, result: ResearchResult, match: str
):
    flow = ResearchFlow(tmp_path)

    with pytest.raises(ValidationError, match=match):
        flow.apply_result(result, task_id="missing-task", at=AT)

    assert not flow.state_path.exists()


def test_corrupt_or_duplicate_state_fails_closed(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    flow.state_path.parent.mkdir(parents=True)
    flow.state_path.write_text(
        '{"symbol":"CN:000001","status":"watch"}\n{"symbol":"CN:000001","status":"watch"}\n',
        encoding="utf-8",
    )

    with pytest.raises(StateCorruptionError, match="duplicate state"):
        flow.read_states()


def test_invalid_screen_batch_is_all_or_nothing(tmp_path: Path):
    flow = ResearchFlow(tmp_path)

    with pytest.raises(ValidationError, match="duplicate screening"):
        flow.apply_screening(
            [
                ScreenDecision("CN:000001", "ignore", "不看"),
                ScreenDecision("cn:000001", "research_now", "要看"),
            ],
            screen_id="bad-batch",
            at=AT,
        )

    assert not flow.state_path.exists()
    assert not flow.queue_path.exists()

    with pytest.raises(ValidationError, match="watch screening requires"):
        flow.apply_screening(
            [ScreenDecision("CN:000002", "watch", "空观察条件")],
            screen_id="empty-watch",
            at=AT,
        )
