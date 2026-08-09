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


def _ignored_after_research(symbol: str) -> ResearchResult:
    return ResearchResult(
        symbol=symbol,
        name="示例公司",
        outcome="ignore",
        information_cutoff=AT,
        summary="完成研究后，业务质量与估值仍不值得持续监控。",
        key_logic=("增长依赖持续融资",),
        risks=("普通股持续稀释",),
        value_range=None,
        valuation_note="无法建立不依赖外部融资的普通股价值。",
        event_triggers=("下一份年报显示自由现金流持续转正",),
        source_urls=("https://example.com/annual-report",),
        report_markdown="# 示例公司研究\n\n研究后不纳入持续覆盖。",
    )


def _complete(flow: ResearchFlow, result: ResearchResult, *, at: str = AT) -> dict:
    update = flow.apply_screening(
        [
            ScreenDecision(
                result.symbol,
                "research_now",
                "主 Agent 已决定完成统一标准研究",
                name=result.name,
            )
        ],
        screen_id=f"test-{next(_TRIGGER_IDS)}",
        mode="event",
        at=at,
    )
    assert len(update.enqueued_tasks) == 1
    task = update.enqueued_tasks[0]
    running = flow.dispatch_tasks(limit=1, at=at)
    assert [item.task_id for item in running] == [task.task_id]
    return flow.apply_result(result, task_id=task.task_id, at=at)


def test_screening_only_creates_ignore_or_candidate(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    flow.register_universe(
        [CompanyRef("CN:000001", "甲公司"), CompanyRef("CN:000002", "乙公司")],
        at=AT,
    )

    update = flow.apply_screening(
        [
            ScreenDecision("CN:000001", "ignore", "当前不值得正式研究"),
            ScreenDecision("CN:000002", "research_now", "现金流问题值得正式研究"),
        ],
        screen_id="baseline-2026-08-08",
        at=AT,
    )

    assert (update.total, update.ignored, update.candidates) == (2, 1, 1)
    assert {row["symbol"]: row["status"] for row in flow.read_states()} == {
        "CN:000001": "ignore",
        "CN:000002": "candidate",
    }
    assert flow.read_watchlist() == ()
    assert [task.symbol for task in flow.list_tasks()] == ["CN:000002"]


def test_dispatch_can_select_tasks_from_queue_end(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    symbols = ["CN:000001", "CN:000002", "CN:000003"]
    flow.register_universe([CompanyRef(symbol, symbol) for symbol in symbols], at=AT)
    flow.apply_screening(
        [
            ScreenDecision(symbol, "research_now", "值得正式研究")
            for symbol in symbols
        ],
        screen_id="reverse-dispatch",
        mode="event",
        at=AT,
    )

    queue_tail = {task.task_id for task in flow.list_tasks()[-2:]}
    running = flow.dispatch_tasks(limit=2, at=AT, from_end=True)

    assert {task.task_id for task in running} == queue_tail


def test_baseline_only_accepts_unseen_companies(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    flow.register_universe([CompanyRef("CN:000001"), CompanyRef("CN:000002")], at=AT)
    flow.apply_screening(
        [ScreenDecision("CN:000001", "ignore", "当前不值得研究")],
        screen_id="baseline-1",
        at=AT,
    )
    before = flow.read_states()

    with pytest.raises(ValidationError, match="only accepts unseen companies: CN:000001"):
        flow.apply_screening(
            [
                ScreenDecision("CN:000002", "research_now", "首次判断"),
                ScreenDecision("CN:000001", "research_now", "重复覆盖"),
            ],
            screen_id="baseline-2",
            at=AT,
        )

    assert flow.read_states() == before
    assert flow.list_tasks() == ()


def test_universe_sync_preserves_history_and_controls_tasks_and_monitoring(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    _complete(flow, _covered("CN:000001"))
    candidate = flow.apply_screening(
        [ScreenDecision("CN:000002", "research_now", "值得正式研究")],
        screen_id="candidate-before-universe-sync",
        mode="event",
        at=AT,
    ).enqueued_tasks[0]

    reduced = flow.sync_universe(
        [CompanyRef("CN:000001", "更新后的公司名")],
        at="2026-08-09T17:00:00+08:00",
    )

    assert (reduced.total, reduced.inactivated, reduced.renamed) == (1, 1, 1)
    assert candidate.task_id not in {task.task_id for task in flow.list_tasks()}
    states = {row["symbol"]: row for row in flow.read_states()}
    assert states["CN:000001"]["status"] == "covered"
    assert states["CN:000001"]["name"] == "更新后的公司名"
    assert states["CN:000002"]["universe_status"] == "inactive"
    assert [row["symbol"] for row in flow.read_watchlist()] == ["CN:000001"]

    switched = flow.sync_universe(
        [CompanyRef("CN:000002"), CompanyRef("CN:000003", "新增公司")],
        at="2026-08-10T17:00:00+08:00",
    )

    assert (switched.added, switched.reactivated, switched.inactivated) == (1, 1, 1)
    assert [task.symbol for task in switched.enqueued_tasks] == ["CN:000002"]
    assert flow.read_watchlist() == ()
    assert (tmp_path / "research/companies/CN/000001/reports/2026-08-08.md").is_file()
    flow.validate()


def test_candidate_task_is_deduplicated_under_concurrency(tmp_path: Path):
    flow = ResearchFlow(tmp_path)

    def screen():
        return flow.apply_screening(
            [ScreenDecision("CN:600000", "research_now", "半年报可能显示变化")],
            screen_id="2026-h1-results",
            mode="event",
            at=AT,
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        returned = list(executor.map(lambda _: screen(), range(16)))

    assert sum(len(update.enqueued_tasks) for update in returned) == 1
    assert sum(update.deduplicated for update in returned) == 15
    assert flow.read_states()[0]["status"] == "candidate"


def test_covered_result_writes_report_and_monitoring_projection(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    state = _complete(flow, _covered("CN:601138"))

    assert state["status"] == "covered"
    assert state["information_cutoff"] == AT
    assert state["value_range"] == {"low": 58.0, "high": 82.0, "currency": "CNY"}
    assert state["report_path"] == "research/companies/CN/601138/reports/2026-08-08.md"
    assert (tmp_path / state["report_path"]).is_file()
    assert flow.list_tasks() == ()
    watch = flow.read_watchlist()[0]
    assert watch["symbol"] == "CN:601138"
    assert watch["status"] == "covered"
    assert watch["information_cutoff"] == AT


def test_researched_ignore_keeps_report_without_price_monitor(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    state = _complete(flow, _ignored_after_research("CN:000333"))

    assert state["status"] == "ignore"
    assert state["report_path"] == "research/companies/CN/000333/reports/2026-08-08.md"
    assert (tmp_path / state["report_path"]).is_file()
    assert state["price_levels"] == []
    assert state["price_monitor"] is None
    assert flow.read_watchlist() == ()
    flow.validate()


def test_same_day_refresh_appends_report_and_current_pointer_uses_latest(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    first = _complete(flow, _covered("CN:601138"))
    update = flow.apply_screening(
        [ScreenDecision("CN:601138", "research_now", "新公告改变估值")],
        screen_id="same-day-refresh",
        mode="event",
        at=AT,
    )
    flow.dispatch_tasks(limit=1, at=AT)
    second = flow.apply_result(
        _covered("CN:601138"),
        task_id=update.enqueued_tasks[0].task_id,
        at=AT,
    )

    assert first["report_path"].endswith("/2026-08-08.md")
    assert second["report_path"].endswith("/2026-08-08-02.md")
    assert (tmp_path / first["report_path"]).is_file()
    assert (tmp_path / second["report_path"]).is_file()
    flow.validate()


def test_dispatch_and_requeue_use_separate_task_state(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    created = flow.apply_screening(
        [
            ScreenDecision("CN:000001", "research_now", "需要研究"),
            ScreenDecision("CN:000002", "research_now", "需要研究"),
            ScreenDecision("CN:000003", "research_now", "需要研究"),
        ],
        screen_id="event-a",
        mode="event",
        at=AT,
    )
    assert len(created.enqueued_tasks) == 3

    first = flow.dispatch_tasks(limit=2, at=AT)
    second = flow.dispatch_tasks(limit=2, at=AT)
    assert len(first) == 2
    assert len(second) == 1
    assert all(task.status is TaskStatus.RUNNING for task in first + second)
    restored = flow.requeue_task(first[0].task_id)
    assert restored.status is TaskStatus.QUEUED
    assert restored.started_at is None


def test_daily_close_only_scans_covered_and_rearms(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    _complete(flow, _covered("CN:601138"))

    assert flow.scan_daily_close({"CN:601138": 60}, trading_date=date(2026, 8, 10), at=AT) == ()
    first = flow.scan_daily_close({"CN:601138": 54}, trading_date="2026-08-11", at=AT)
    assert len(first) == 1
    assert flow.scan_daily_close({"CN:601138": 52}, trading_date="2026-08-12", at=AT) == ()
    assert flow.scan_daily_close({"CN:601138": 58}, trading_date="2026-08-13", at=AT) == ()
    assert len(flow.scan_daily_close({"CN:601138": 55}, trading_date="2026-08-14", at=AT)) == 1
    assert flow.list_tasks() == ()


def test_each_price_level_has_independent_runtime_state(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    result = replace(
        _covered("CN:601138"),
        buy_below=None,
        rearm_above=None,
        price_levels=(
            PriceLevel("attention", "关注价", 55, 57),
            PriceLevel("high-attraction", "高吸引力价", 50, 52),
        ),
    )
    _complete(flow, result)
    first = flow.scan_daily_close({"CN:601138": 54}, trading_date="2026-08-11", at=AT)
    second = flow.scan_daily_close({"CN:601138": 49}, trading_date="2026-08-12", at=AT)
    assert [hit.level_id for hit in first] == ["attention"]
    assert [hit.level_id for hit in second] == ["high-attraction"]


def test_material_event_marks_covered_report_stale_and_suppresses_price(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    covered = _complete(flow, _covered("CN:601138"))
    report = tmp_path / covered["report_path"]

    update = flow.apply_screening(
        [ScreenDecision("CN:601138", "research_now", "新财报改变现金流和估值")],
        screen_id="2026-h1-refresh",
        mode="event",
        at="2026-08-09T17:00:00+08:00",
    )
    state = flow.read_states()[0]
    assert state["status"] == "stale"
    assert state["invalidation"]["reason"] == "新财报改变现金流和估值"
    assert state["price_monitor"] is None
    assert state["report_path"] == covered["report_path"]
    assert report.is_file()
    assert flow.read_watchlist() == ()
    assert len(update.enqueued_tasks) == 1
    flow.validate()


def test_decisive_event_can_ignore_without_deleting_report_history_or_task(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    covered = _complete(flow, _covered("CN:601138"))
    report = tmp_path / covered["report_path"]
    update = flow.apply_screening(
        [ScreenDecision("CN:601138", "research_now", "需要更新")],
        screen_id="refresh",
        mode="event",
        at=AT,
    )
    running = flow.dispatch_tasks(limit=1, at=AT)[0]
    assert running.task_id == update.enqueued_tasks[0].task_id

    flow.apply_screening(
        [ScreenDecision("CN:601138", "ignore", "关键业务已经终止")],
        screen_id="decisive-failure",
        mode="event",
        at=AT,
    )
    state = flow.read_states()[0]
    assert state["status"] == "ignore"
    assert state["report_path"] is None
    assert report.exists()
    assert flow.list_tasks() == ()


def test_v1_migration_splits_watch_and_covered_then_rebaseline(tmp_path: Path):
    state_path = tmp_path / "coverage/cn-a/research_state.jsonl"
    state_path.parent.mkdir(parents=True)
    report = tmp_path / "research/companies/CN/000002/current.md"
    report.parent.mkdir(parents=True)
    report.write_text("# 已有正式研究\n", encoding="utf-8")
    legacy_rows = [
        {
            "schema_version": 1,
            "symbol": "CN:000001",
            "name": "候选公司",
            "status": "watch",
            "updated_at": AT,
            "summary": "旧观察",
            "key_logic": [],
            "risks": [],
            "value_range": None,
            "price_levels": [{"id": "buy", "label": "旧价格", "threshold": 10, "rearm_above": 11}],
            "event_triggers": ["下一期财报"],
            "source_urls": [],
            "last_screening": {"screen_id": "old", "mode": "baseline"},
            "last_research_at": None,
            "report_path": None,
            "processed_triggers": [],
            "price_monitor": {"levels": {}},
        },
        {
            "schema_version": 1,
            "symbol": "CN:000002",
            "name": "覆盖公司",
            "status": "researched",
            "updated_at": AT,
            "summary": "已有研究",
            "key_logic": ["逻辑"],
            "risks": ["风险"],
            "value_range": {"low": 10.0, "high": 20.0, "currency": "CNY"},
            "price_levels": [],
            "event_triggers": ["下一期财报"],
            "source_urls": ["https://example.com/report"],
            "last_screening": {"screen_id": "old", "mode": "baseline"},
            "last_research_at": AT,
            "report_path": "research/companies/CN/000002/current.md",
            "processed_triggers": [],
            "price_monitor": None,
        },
    ]
    state_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in legacy_rows) + "\n",
        encoding="utf-8",
    )
    flow = ResearchFlow(tmp_path)
    assert flow.migrate_state_v2(at=AT) == 2
    states = {row["symbol"]: row for row in flow.read_states()}
    assert states["CN:000001"]["status"] == "candidate"
    assert states["CN:000001"]["price_levels"] == []
    assert states["CN:000002"]["status"] == "covered"
    assert states["CN:000002"]["report_path"] == (
        "research/companies/CN/000002/reports/2026-08-08.md"
    )
    assert not report.exists()
    assert (tmp_path / states["CN:000002"]["report_path"]).is_file()
    flow.validate()

    assert flow.prepare_rebaseline(at=AT) == 1
    states = {row["symbol"]: row for row in flow.read_states()}
    assert states["CN:000001"]["status"] == "unseen"
    assert states["CN:000002"]["status"] == "covered"


def test_validation_checks_queue_and_watchlist_projection(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    _complete(flow, _covered("CN:601138"))
    flow.apply_screening(
        [ScreenDecision("CN:000001", "research_now", "年报复核")],
        screen_id="annual-report",
        mode="event",
        at=AT,
    )
    status = flow.validate()
    assert (status.companies, status.covered, status.candidates) == (2, 1, 1)
    assert (status.watchlist, status.queued, status.running) == (1, 1, 0)

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
            replace(_covered("CN:000001"), risks=()),
            "at least one risk",
        ),
        (
            replace(_covered("CN:000001"), value_range=None, valuation_note=None),
            "value_range or valuation_note",
        ),
        (
            replace(_covered("CN:000001"), source_urls=("not-a-url",)),
            "absolute http",
        ),
        (
            replace(_ignored_after_research("CN:000001"), buy_below=10),
            "must not activate price",
        ),
    ],
)
def test_invalid_results_fail_before_state_write(
    tmp_path: Path, result: ResearchResult, match: str
):
    flow = ResearchFlow(tmp_path)
    with pytest.raises(ValidationError, match=match):
        flow.apply_result(result, task_id="missing-task", at=AT)
    assert not flow.state_path.exists()


def test_corrupt_or_duplicate_state_fails_closed(tmp_path: Path):
    flow = ResearchFlow(tmp_path)
    flow.state_path.parent.mkdir(parents=True)
    row = {
        "schema_version": 2,
        "symbol": "CN:000001",
        "universe_status": "active",
        "status": "ignore",
    }
    flow.state_path.write_text(
        json.dumps(row) + "\n" + json.dumps(row) + "\n",
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
