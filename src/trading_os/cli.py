from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, is_dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence, TextIO

from .research_assets.legacy_salvage import LegacyReportSalvager
from .research_assets.market_data import (
    DEFAULT_EVENT_SCAN_STATE_PATH,
    MARKET_TIMEZONE,
    Announcement,
    MarketDataError,
    advance_event_scan_state,
    discover_cninfo_announcements_for_companies,
    event_scan_state_payload,
    fetch_tencent_daily_closes,
    read_event_scan_state,
    unseen_event_announcements,
    write_event_scan_state,
)
from .research_assets.research_flow import (
    CompanyRef,
    PriceLevel,
    ResearchFlow,
    ResearchFlowError,
    ResearchResult,
    ScreenDecision,
    ValueRange,
)


def _add_input(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input", required=True, help="JSON/JSONL 文件；用 - 读取标准输入")


def _add_at(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--at", help="带时区的 ISO 时间；省略时使用当前时间")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trading_os",
        description="精简的全市场初筛、单公司研究和每日收盘监控",
    )
    parser.add_argument("--root", default=".", help="仓库根目录（默认当前目录）")
    commands = parser.add_subparsers(dest="command", required=True)

    status = commands.add_parser("status", help="查看研究状态和当前任务计数")
    status.set_defaults(handler=_status)
    validate = commands.add_parser("validate", help="只读校验状态、队列、观察池和当前报告")
    validate.set_defaults(handler=_validate)

    state = commands.add_parser("state", help="维护公司状态模型和全市场基线")
    state_commands = state.add_subparsers(dest="state_command", required=True)
    migrate_v2 = state_commands.add_parser("migrate-v2", help="迁移到候选/覆盖/失效状态模型")
    _add_at(migrate_v2)
    migrate_v2.set_defaults(handler=_state_migrate_v2)
    rebaseline = state_commands.add_parser(
        "prepare-rebaseline", help="保留有效覆盖，重置其余公司供全市场重筛"
    )
    _add_at(rebaseline)
    rebaseline.set_defaults(handler=_state_prepare_rebaseline)

    reports = commands.add_parser("reports", help="维护本机日期化正式研报时间线")
    report_commands = reports.add_subparsers(dest="reports_command", required=True)
    migrate_current = report_commands.add_parser(
        "migrate-current", help="把旧 current.md 一次性迁入 reports/日期.md"
    )
    migrate_current.set_defaults(handler=_reports_migrate_current)

    universe = commands.add_parser("universe", help="维护全市场证券清单")
    universe_commands = universe.add_subparsers(dest="universe_command", required=True)
    register = universe_commands.add_parser("register", help="登记证券，已有判断不会被覆盖")
    _add_input(register)
    _add_at(register)
    register.set_defaults(handler=_universe_register)
    sync = universe_commands.add_parser(
        "sync", help="用完整证券快照同步 active/inactive，保留已有研究历史"
    )
    _add_input(sync)
    _add_at(sync)
    sync.set_defaults(handler=_universe_sync)

    screen = commands.add_parser("screen", help="记录主 Agent 的批量初筛")
    screen_commands = screen.add_subparsers(dest="screen_command", required=True)
    record = screen_commands.add_parser("record", help="记录 ignore/research_now")
    _add_input(record)
    record.add_argument("--screen-id", help="覆盖输入文件中的 screen_id")
    record.add_argument("--mode", choices=("baseline", "event"), help="覆盖输入中的筛选模式")
    _add_at(record)
    record.set_defaults(handler=_screen_record)

    research = commands.add_parser("research", help="管理单公司端到端研究任务")
    research_commands = research.add_subparsers(dest="research_command", required=True)
    next_tasks = research_commands.add_parser("next", help="取下一批公司，数量由调用者决定")
    next_tasks.add_argument("--limit", required=True, type=int)
    next_tasks.add_argument(
        "--from-end",
        action="store_true",
        help="从队列尾部领取，便于与从队首运行的其他协调器避让",
    )
    _add_at(next_tasks)
    next_tasks.set_defaults(handler=_research_next)
    requeue = research_commands.add_parser("requeue", help="显式恢复被中断的任务")
    requeue.add_argument("task_id")
    requeue.set_defaults(handler=_research_requeue)
    complete = research_commands.add_parser("complete", help="写入 worker 的一次最终结果")
    _add_input(complete)
    complete.add_argument("--task-id", help="覆盖输入文件中由 research next 返回的 task_id")
    _add_at(complete)
    complete.set_defaults(handler=_research_complete)

    watchlist = commands.add_parser("watchlist", help="查看观察池并执行每日收盘扫描")
    watchlist_commands = watchlist.add_subparsers(dest="watchlist_command", required=True)
    build = watchlist_commands.add_parser("build", help="从研究状态重建观察池")
    build.set_defaults(handler=_watchlist_build)
    list_command = watchlist_commands.add_parser("list", help="列出观察池")
    list_command.set_defaults(handler=_watchlist_list)
    scan = watchlist_commands.add_parser("scan-close", help="扫描一个交易日的收盘价")
    _add_input(scan)
    scan.add_argument("--date", help="覆盖输入文件中的 trading_date")
    _add_at(scan)
    scan.set_defaults(handler=_watchlist_scan_close)
    fetch_close = watchlist_commands.add_parser(
        "fetch-close", help="严格获取全部受监控公司的当日不复权收盘价"
    )
    fetch_close.add_argument("--date", required=True, help="交易日 YYYY-MM-DD")
    _add_at(fetch_close)
    fetch_close.set_defaults(handler=_watchlist_fetch_close)
    run_close = watchlist_commands.add_parser(
        "run-close", help="完整取价后原子执行一次每日收盘触发扫描"
    )
    run_close.add_argument("--date", required=True, help="交易日 YYYY-MM-DD")
    _add_at(run_close)
    run_close.set_defaults(handler=_watchlist_run_close)

    events = commands.add_parser("events", help="获取全市场公告并维护成功检查点")
    event_commands = events.add_subparsers(dest="events_command", required=True)
    event_status = event_commands.add_parser("status", help="查看当前公告扫描检查点")
    event_status.set_defaults(handler=_events_status)
    event_fetch = event_commands.add_parser(
        "fetch", help="获取检查点之后的公告；首次运行必须显式提供起点"
    )
    event_fetch.add_argument("--since", help="首次扫描起点（带时区 ISO 时间）")
    event_fetch.add_argument("--until", help="半开窗口终点（默认当前上海时间）")
    event_fetch.add_argument("--output", help="将完整待判断 packet 写入仓库内临时 JSON")
    event_fetch.set_defaults(handler=_events_fetch)
    event_complete = event_commands.add_parser("complete", help="全部公告判断成功后推进检查点")
    event_complete.add_argument("--packet", required=True, help="events fetch 的原始 JSON")
    _add_input(event_complete)
    event_complete.set_defaults(handler=_events_complete)

    salvage = commands.add_parser("legacy-salvage", help="从固定恢复标签筛选并打捞旧研报")
    salvage_commands = salvage.add_subparsers(dest="salvage_command", required=True)
    candidates = salvage_commands.add_parser(
        "candidates", help="只读列出旧报告候选；不会改变当前状态"
    )
    candidates.add_argument("--limit", type=int, default=200)
    candidates.add_argument("--min-score", type=int, default=0)
    candidates.set_defaults(handler=_legacy_salvage_candidates)
    archive_salvage = salvage_commands.add_parser(
        "archive-best", help="每家公司选一份最佳旧报告写入隔离档案"
    )
    archive_salvage.set_defaults(handler=_legacy_salvage_archive_best)
    return parser


def _load(path: str, stdin: TextIO) -> tuple[Any, Path | None]:
    if path == "-":
        text = stdin.read()
        source = None
    else:
        source = Path(path)
        text = source.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError("输入文件为空")
    try:
        return json.loads(text), source
    except json.JSONDecodeError as object_error:
        rows: list[Any] = []
        try:
            for line in text.splitlines():
                if line.strip():
                    rows.append(json.loads(line))
        except json.JSONDecodeError:
            raise object_error from None
        return rows, source


def _records(payload: Any, key: str) -> list[Mapping[str, Any]]:
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict) and key in payload:
        records = payload[key]
    else:
        raise ValueError(f"输入应为数组或包含 {key!r} 数组的对象")
    if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
        raise ValueError(f"{key} 必须是对象数组")
    return records


def _levels(payload: Mapping[str, Any]) -> tuple[PriceLevel, ...]:
    raw = payload.get("price_levels") or []
    if not isinstance(raw, list):
        raise ValueError("price_levels 必须是数组")
    return tuple(
        PriceLevel(
            id=item["id"],
            label=item["label"],
            threshold=item["threshold"],
            rearm_above=item.get("rearm_above"),
        )
        for item in raw
    )


def _screen_decision(payload: Mapping[str, Any]) -> ScreenDecision:
    return ScreenDecision(
        symbol=payload["symbol"],
        name=payload.get("name"),
        route=payload["route"],
        reason=payload["reason"],
        event_triggers=payload.get("event_triggers") or (),
        source_urls=payload.get("source_urls") or (),
    )


def _research_result(payload: Mapping[str, Any]) -> ResearchResult:
    raw_range = payload.get("value_range")
    value_range = None
    if raw_range is not None:
        if not isinstance(raw_range, dict):
            raise ValueError("value_range 必须是包含 low/high/currency 的对象")
        value_range = ValueRange(
            low=raw_range["low"],
            high=raw_range["high"],
            currency=raw_range.get("currency", "CNY"),
        )
    return ResearchResult(
        symbol=payload["symbol"],
        name=payload.get("name"),
        outcome=payload["outcome"],
        summary=payload["summary"],
        key_logic=payload.get("key_logic") or (),
        risks=payload.get("risks") or (),
        value_range=value_range,
        price_levels=_levels(payload),
        buy_below=payload.get("buy_below"),
        rearm_above=payload.get("rearm_above"),
        event_triggers=payload.get("event_triggers") or (),
        source_urls=payload.get("source_urls") or (),
        information_cutoff=payload["information_cutoff"],
        report_markdown=payload.get("report_markdown"),
        valuation_note=payload.get("valuation_note"),
    )


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _emit(payload: Any, stream: TextIO) -> None:
    stream.write(json.dumps(_jsonable(payload), ensure_ascii=False, sort_keys=True) + "\n")


def _flow(args: argparse.Namespace) -> ResearchFlow:
    return ResearchFlow(Path(args.root))


def _status(args: argparse.Namespace, stdin: TextIO) -> dict[str, Any]:
    del stdin
    return asdict(_flow(args).status())


def _validate(args: argparse.Namespace, stdin: TextIO) -> dict[str, Any]:
    del stdin
    return {"ok": True, "status": asdict(_flow(args).validate())}


def _state_migrate_v2(args: argparse.Namespace, stdin: TextIO) -> dict[str, Any]:
    del stdin
    flow = _flow(args)
    migrated = flow.migrate_state_v2(at=args.at)
    return {"migrated": migrated, "status": asdict(flow.validate())}


def _state_prepare_rebaseline(args: argparse.Namespace, stdin: TextIO) -> dict[str, Any]:
    del stdin
    flow = _flow(args)
    reset = flow.prepare_rebaseline(at=args.at)
    return {"reset": reset, "status": asdict(flow.validate())}


def _reports_migrate_current(args: argparse.Namespace, stdin: TextIO) -> dict[str, Any]:
    del stdin
    flow = _flow(args)
    migrated = flow.migrate_current_reports()
    return {"migrated": migrated, "status": asdict(flow.validate())}


def _universe_register(args: argparse.Namespace, stdin: TextIO) -> dict[str, Any]:
    payload, _ = _load(args.input, stdin)
    companies = [
        CompanyRef(symbol=item["symbol"], name=item.get("name"))
        for item in _records(payload, "companies")
    ]
    flow = _flow(args)
    added = flow.register_universe(companies, at=args.at)
    return {"added": added, "companies": flow.status().companies}


def _universe_sync(args: argparse.Namespace, stdin: TextIO) -> dict[str, Any]:
    payload, _ = _load(args.input, stdin)
    companies = [
        CompanyRef(symbol=item["symbol"], name=item.get("name"))
        for item in _records(payload, "companies")
    ]
    return _jsonable(_flow(args).sync_universe(companies, at=args.at))


def _screen_record(args: argparse.Namespace, stdin: TextIO) -> dict[str, Any]:
    payload, _ = _load(args.input, stdin)
    decisions = [_screen_decision(item) for item in _records(payload, "decisions")]
    metadata = payload if isinstance(payload, dict) else {}
    screen_id = args.screen_id or metadata.get("screen_id")
    if not screen_id:
        raise ValueError("screen_id 必须由输入文件或 --screen-id 提供")
    update = _flow(args).apply_screening(
        decisions,
        screen_id=screen_id,
        mode=args.mode or metadata.get("mode", "baseline"),
        at=args.at or metadata.get("at"),
    )
    return {
        "total": update.total,
        "ignore": update.ignored,
        "research_now": update.candidates,
        "enqueued": [_jsonable(task) for task in update.enqueued_tasks],
        "deduplicated": update.deduplicated,
    }


def _research_next(args: argparse.Namespace, stdin: TextIO) -> dict[str, Any]:
    del stdin
    tasks = _flow(args).dispatch_tasks(
        limit=args.limit,
        at=args.at,
        from_end=args.from_end,
    )
    return {"count": len(tasks), "tasks": tasks}


def _research_requeue(args: argparse.Namespace, stdin: TextIO) -> dict[str, Any]:
    del stdin
    return {"task": _flow(args).requeue_task(args.task_id)}


def _research_complete(args: argparse.Namespace, stdin: TextIO) -> dict[str, Any]:
    payload, _ = _load(args.input, stdin)
    if not isinstance(payload, dict):
        raise ValueError("研究结果必须是 JSON 对象")
    result_payload = payload.get("result", payload)
    if not isinstance(result_payload, dict):
        raise ValueError("result 必须是对象")
    task_id = args.task_id or payload.get("task_id")
    if not task_id:
        raise ValueError("研究结果必须绑定 research next 返回的 task_id")
    state = _flow(args).apply_result(
        _research_result(result_payload),
        task_id=task_id,
        at=args.at or payload.get("at"),
    )
    return {
        "symbol": state["symbol"],
        "status": state["status"],
        "price_levels": state["price_levels"],
        "report_path": state["report_path"],
    }


def _watchlist_build(args: argparse.Namespace, stdin: TextIO) -> dict[str, Any]:
    del stdin
    flow = _flow(args)
    path = flow.rebuild_watchlist()
    return {"path": path.relative_to(flow.root).as_posix(), "count": len(flow.read_watchlist())}


def _watchlist_list(args: argparse.Namespace, stdin: TextIO) -> dict[str, Any]:
    del stdin
    rows = _flow(args).read_watchlist()
    return {"count": len(rows), "companies": rows}


def _watchlist_scan_close(args: argparse.Namespace, stdin: TextIO) -> dict[str, Any]:
    payload, _ = _load(args.input, stdin)
    if not isinstance(payload, dict):
        raise ValueError("收盘价输入必须是 JSON 对象")
    if isinstance(payload.get("closes"), dict):
        closes = payload["closes"]
    else:
        quotes = payload.get("quotes")
        if not isinstance(quotes, list):
            raise ValueError("输入需包含 closes 对象或 quotes 数组")
        closes = {item["symbol"]: item["close"] for item in quotes}
        if len(closes) != len(quotes):
            raise ValueError("quotes 中存在重复 symbol")
    trading_date = args.date or payload.get("trading_date")
    if not trading_date:
        raise ValueError("trading_date 必须由输入文件或 --date 提供")
    hits = _flow(args).scan_daily_close(
        closes,
        trading_date=trading_date,
        at=args.at or payload.get("at"),
    )
    return {"trading_date": trading_date, "hit_count": len(hits), "hits": hits}


def _monitored_companies(flow: ResearchFlow) -> dict[str, str | None]:
    # 证券代码（含交易所映射）是行情身份的稳定键。状态中的 name 可能是
    # 法定全称、旧简称或带 XD/C 等临时前缀，不应让名称展示变化阻断
    # 全市场收盘扫描；行情层仍严格验证代码、交易所、完整覆盖和收盘时间。
    return {
        row["symbol"]: None for row in flow.read_watchlist() if row.get("price_levels")
    }


def _watchlist_fetch_close(args: argparse.Namespace, stdin: TextIO) -> dict[str, Any]:
    del stdin
    flow = _flow(args)
    companies = _monitored_companies(flow)
    quotes = fetch_tencent_daily_closes(
        companies,
        trading_date=args.date,
        fetched_at=args.at,
    )
    return {
        "trading_date": args.date,
        "quote_count": len(quotes),
        "quotes": quotes,
    }


def _watchlist_run_close(args: argparse.Namespace, stdin: TextIO) -> dict[str, Any]:
    del stdin
    flow = _flow(args)
    companies = _monitored_companies(flow)
    quotes = fetch_tencent_daily_closes(
        companies,
        trading_date=args.date,
        fetched_at=args.at,
    )
    closes = {quote.symbol: quote.close for quote in quotes}
    hits = flow.scan_daily_close(closes, trading_date=args.date, at=args.at)
    return {
        "trading_date": args.date,
        "quote_count": len(quotes),
        "hit_count": len(hits),
        "hits": hits,
    }


def _aware_iso(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} 必须是带时区的 ISO 时间")
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError(f"{label} 必须是带时区的 ISO 时间") from exc
    if parsed.utcoffset() is None:
        raise ValueError(f"{label} 必须包含 UTC offset")
    return parsed.astimezone(MARKET_TIMEZONE).isoformat()


def _event_state_path(flow: ResearchFlow) -> Path:
    return flow.root / DEFAULT_EVENT_SCAN_STATE_PATH


def _events_status(args: argparse.Namespace, stdin: TextIO) -> dict[str, Any]:
    del stdin
    flow = _flow(args)
    state = read_event_scan_state(_event_state_path(flow))
    return event_scan_state_payload(state)


def _events_fetch(args: argparse.Namespace, stdin: TextIO) -> dict[str, Any]:
    del stdin
    flow = _flow(args)
    state = read_event_scan_state(_event_state_path(flow))
    if state.last_successful_at is None:
        if args.since is None:
            raise ValueError("首次公告扫描必须用 --since 显式设置起点")
        scan_start = _aware_iso(args.since, "since")
        fetch_start = scan_start
    else:
        if args.since is not None:
            supplied = _aware_iso(args.since, "since")
            if supplied != state.last_successful_at:
                raise ValueError("--since 必须与当前 last_successful_at 完全一致")
        scan_start = state.last_successful_at
        previous_time = datetime.fromisoformat(scan_start).astimezone(MARKET_TIMEZONE)
        fetch_start = (
            (previous_time - timedelta(days=1))
            .replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
            .isoformat()
        )
    scan_end = (
        _aware_iso(args.until, "until")
        if args.until is not None
        else datetime.now(MARKET_TIMEZONE).isoformat()
    )
    companies = tuple(row["symbol"] for row in flow.read_states())
    discovered = discover_cninfo_announcements_for_companies(
        companies,
        fetch_start,
        scan_end,
    )
    pending = unseen_event_announcements(state, discovered)
    packet = {
        "schema_version": 1,
        "scan_start": scan_start,
        "fetch_start": fetch_start,
        "scan_end": scan_end,
        "universe_count": len(companies),
        "announcement_count": len(pending),
        "already_seen_count": len(discovered) - len(pending),
        "announcements": pending,
    }
    if args.output is None:
        return packet
    root = flow.root.resolve()
    output = Path(args.output)
    output = (flow.root / output).resolve() if not output.is_absolute() else output.resolve()
    try:
        output.relative_to(root)
    except ValueError as exc:
        raise ValueError("events fetch --output 必须位于仓库根目录内") from exc
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(_jsonable(packet), ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "packet_path": output.relative_to(root).as_posix(),
        "scan_start": scan_start,
        "fetch_start": fetch_start,
        "scan_end": scan_end,
        "universe_count": len(companies),
        "announcement_count": len(pending),
        "already_seen_count": len(discovered) - len(pending),
    }


def _announcement_from_payload(value: object) -> Announcement:
    if not isinstance(value, Mapping):
        raise ValueError("announcements 必须只包含对象")
    return Announcement(
        announcement_id=value["announcement_id"],
        symbol=value["symbol"],
        title=value["title"],
        published_at=value["published_at"],
        url=value["url"],
    )


def _events_complete(args: argparse.Namespace, stdin: TextIO) -> dict[str, Any]:
    packet, _ = _load(args.packet, stdin)
    judgments, _ = _load(args.input, stdin)
    if not isinstance(packet, dict):
        raise ValueError("events fetch packet 必须是 JSON 对象")
    if not isinstance(judgments, dict):
        raise ValueError("公告判断结果必须是 JSON 对象")
    if packet.get("schema_version") != 1:
        raise ValueError("不支持的 events fetch packet 版本")
    raw_announcements = packet.get("announcements")
    if not isinstance(raw_announcements, list):
        raise ValueError("packet announcements 必须是数组")
    if packet.get("announcement_count") != len(raw_announcements):
        raise ValueError("packet announcement_count 与 announcements 不一致")
    judged_ids = judgments.get("successfully_judged_ids")
    if not isinstance(judged_ids, list):
        raise ValueError("successfully_judged_ids 必须是数组")

    flow = _flow(args)
    path = _event_state_path(flow)
    previous = read_event_scan_state(path)
    scan_start = _aware_iso(packet.get("scan_start"), "packet scan_start")
    fetch_start = _aware_iso(packet.get("fetch_start"), "packet fetch_start")
    scan_end = _aware_iso(packet.get("scan_end"), "packet scan_end")
    if datetime.fromisoformat(fetch_start) > datetime.fromisoformat(scan_start):
        raise ValueError("packet fetch_start 不得晚于 scan_start")
    if datetime.fromisoformat(scan_end) <= datetime.fromisoformat(scan_start):
        raise ValueError("packet scan_end 必须晚于 scan_start")
    if previous.last_successful_at is not None and scan_start != previous.last_successful_at:
        raise ValueError("packet scan_start 已落后于当前公告检查点")
    announcements = tuple(_announcement_from_payload(item) for item in raw_announcements)
    start_time = datetime.fromisoformat(fetch_start)
    for announcement in announcements:
        published_at = datetime.fromisoformat(
            _aware_iso(
                announcement.published_at,
                f"公告 {announcement.announcement_id} published_at",
            )
        )
        if published_at < start_time:
            raise ValueError(f"公告 {announcement.announcement_id} 早于 packet scan_start")
    next_state = advance_event_scan_state(
        previous,
        scanned_through=scan_end,
        announcements=announcements,
        successfully_judged_ids=judged_ids,
    )
    write_event_scan_state(next_state, path)
    return {
        "advanced": True,
        "judged_count": len(judged_ids),
        **event_scan_state_payload(next_state),
    }


def _legacy_salvage_candidates(args: argparse.Namespace, stdin: TextIO) -> Any:
    del stdin
    return LegacyReportSalvager(Path(args.root)).list_candidates(
        limit=args.limit,
        min_score=args.min_score,
    )


def _legacy_salvage_archive_best(args: argparse.Namespace, stdin: TextIO) -> Any:
    del stdin
    return LegacyReportSalvager(Path(args.root)).archive_best()


def main(
    argv: Sequence[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    input_stream = stdin or sys.stdin
    output_stream = stdout or sys.stdout
    error_stream = stderr or sys.stderr
    args = build_parser().parse_args(argv)
    try:
        result = args.handler(args, input_stream)
    except (
        MarketDataError,
        ResearchFlowError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
    ) as exc:
        _emit({"ok": False, "error": str(exc)}, error_stream)
        return 1
    _emit(result, output_stream)
    return 0


__all__ = ["build_parser", "main"]
