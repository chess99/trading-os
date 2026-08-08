from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence, TextIO

from .research_assets.legacy_salvage import LegacyReportSalvager
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

    universe = commands.add_parser("universe", help="维护全市场证券清单")
    universe_commands = universe.add_subparsers(dest="universe_command", required=True)
    register = universe_commands.add_parser("register", help="登记证券，已有判断不会被覆盖")
    _add_input(register)
    _add_at(register)
    register.set_defaults(handler=_universe_register)

    screen = commands.add_parser("screen", help="记录主 Agent 的批量初筛")
    screen_commands = screen.add_subparsers(dest="screen_command", required=True)
    record = screen_commands.add_parser("record", help="记录 ignore/watch/research_now")
    _add_input(record)
    record.add_argument("--screen-id", help="覆盖输入文件中的 screen_id")
    record.add_argument("--mode", choices=("baseline", "event"), help="覆盖输入中的筛选模式")
    _add_at(record)
    record.set_defaults(handler=_screen_record)

    research = commands.add_parser("research", help="管理单公司端到端研究任务")
    research_commands = research.add_subparsers(dest="research_command", required=True)
    next_tasks = research_commands.add_parser("next", help="取下一批公司，数量由调用者决定")
    next_tasks.add_argument("--limit", required=True, type=int)
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

    salvage = commands.add_parser("legacy-salvage", help="从固定恢复标签筛选并打捞旧研报")
    salvage_commands = salvage.add_subparsers(dest="salvage_command", required=True)
    candidates = salvage_commands.add_parser(
        "candidates", help="批量列出高信号候选；不会创建单公司任务"
    )
    candidates.add_argument("--limit", type=int, default=200)
    candidates.add_argument("--min-score", type=int, default=40)
    candidates.set_defaults(handler=_legacy_salvage_candidates)
    apply_salvage = salvage_commands.add_parser(
        "apply", help="按显式决策写入重新核验、压缩后的 current.md"
    )
    _add_input(apply_salvage)
    _add_at(apply_salvage)
    apply_salvage.set_defaults(handler=_legacy_salvage_apply)
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
        price_levels=_levels(payload),
        buy_below=payload.get("buy_below"),
        rearm_above=payload.get("rearm_above"),
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
        report_markdown=payload.get("report_markdown"),
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


def _universe_register(args: argparse.Namespace, stdin: TextIO) -> dict[str, Any]:
    payload, _ = _load(args.input, stdin)
    companies = [
        CompanyRef(symbol=item["symbol"], name=item.get("name"))
        for item in _records(payload, "companies")
    ]
    flow = _flow(args)
    added = flow.register_universe(companies, at=args.at)
    return {"added": added, "companies": flow.status().companies}


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
        "watch": update.watched,
        "research_now": update.research_now,
        "enqueued": [_jsonable(task) for task in update.enqueued_tasks],
        "deduplicated": update.deduplicated,
    }


def _research_next(args: argparse.Namespace, stdin: TextIO) -> dict[str, Any]:
    del stdin
    tasks = _flow(args).dispatch_tasks(limit=args.limit, at=args.at)
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


def _legacy_salvage_candidates(args: argparse.Namespace, stdin: TextIO) -> Any:
    del stdin
    return LegacyReportSalvager(Path(args.root)).list_candidates(
        limit=args.limit,
        min_score=args.min_score,
    )


def _legacy_salvage_apply(args: argparse.Namespace, stdin: TextIO) -> Any:
    payload, _ = _load(args.input, stdin)
    if not isinstance(payload, dict):
        raise ValueError("旧研报打捞决策必须是 JSON 对象")
    return LegacyReportSalvager(Path(args.root)).apply_decisions(payload, at=args.at)


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
    except (ResearchFlowError, OSError, ValueError, KeyError, TypeError) as exc:
        _emit({"ok": False, "error": str(exc)}, error_stream)
        return 1
    _emit(result, output_stream)
    return 0


__all__ = ["build_parser", "main"]
