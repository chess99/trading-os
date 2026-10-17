from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence, TextIO

from .industry_catalog import industry_catalog
from .research_assets.research_flow import (
    MANUAL_REWRITE_TRIGGER,
    PERIODIC_TRIGGER,
    CompanyRef,
    ResearchFlow,
    ResearchFlowError,
    ResearchRequest,
    ResearchResult,
    ReturnModel,
    ValueRange,
)
from .screening_pool import TIERS, QualityPoolStore


def _add_input(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input", required=True, help="JSON/JSONL 文件；用 - 读取标准输入")


def _add_at(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--at", help="带时区的 ISO 时间；省略时使用当前时间")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trading_os",
        description="按动态重点池和财报周期维护的 A 股研究工作流",
    )
    parser.add_argument("--root", default=".", help="仓库根目录（默认当前目录）")
    commands = parser.add_subparsers(dest="command", required=True)

    status = commands.add_parser("status", help="查看研究状态和当前任务计数")
    status.set_defaults(handler=_status)
    validate = commands.add_parser("validate", help="只读校验状态、周期队列和报告")
    validate.set_defaults(handler=_validate)

    industry = commands.add_parser("industry", help="查阅产业框架和检查细分行业覆盖")
    industry_commands = industry.add_subparsers(dest="industry_command", required=True)
    industry_commands.add_parser("list", help="列出产业专题及未分类公司").set_defaults(
        handler=_industry_list
    )
    industry_commands.add_parser("validate", help="校验现有细分行业的框架路由").set_defaults(
        handler=_industry_validate
    )

    quality_pool = commands.add_parser(
        "quality-pool", help="维护财报周期排期所使用的动态重点跟踪池"
    )
    quality_pool_commands = quality_pool.add_subparsers(
        dest="quality_pool_command", required=True
    )
    quality_pool_status = quality_pool_commands.add_parser("status", help="查看当前池计数")
    quality_pool_status.set_defaults(handler=_quality_pool_status)
    quality_pool_validate = quality_pool_commands.add_parser(
        "validate", help="只读校验当前池和可读投影"
    )
    quality_pool_validate.set_defaults(handler=_quality_pool_validate)
    quality_pool_replace = quality_pool_commands.add_parser(
        "replace", help="用完整快照原子替换当前池"
    )
    _add_input(quality_pool_replace)
    quality_pool_replace.set_defaults(handler=_quality_pool_replace)
    quality_pool_rebuild = quality_pool_commands.add_parser(
        "rebuild", help="只从已保存名单重建可读投影"
    )
    quality_pool_rebuild.set_defaults(handler=_quality_pool_rebuild)
    quality_pool_list = quality_pool_commands.add_parser("list", help="列出当前池")
    quality_pool_list.add_argument("--tier", choices=TIERS)
    quality_pool_list.set_defaults(handler=_quality_pool_list)

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

    research = commands.add_parser("research", help="管理单公司端到端研究任务")
    research_commands = research.add_subparsers(dest="research_command", required=True)
    enqueue_period = research_commands.add_parser(
        "enqueue-period", help="为动态重点跟踪池创建一个财报周期的研究任务"
    )
    enqueue_period.add_argument("--period", required=True, help="YYYY-FY/Q1/H1/Q3")
    _add_at(enqueue_period)
    enqueue_period.set_defaults(handler=_research_enqueue_period)
    enqueue_rewrite = research_commands.add_parser(
        "enqueue-rewrite", help="显式创建最新财报周期的人工重写任务"
    )
    _add_input(enqueue_rewrite)
    enqueue_rewrite.add_argument("--period", required=True, help="要重写的最新财报周期")
    enqueue_rewrite.add_argument("--batch-id", required=True, help="本次人工重写批次")
    _add_at(enqueue_rewrite)
    enqueue_rewrite.set_defaults(handler=_research_enqueue_rewrite)
    next_tasks = research_commands.add_parser("next", help="取下一批公司，数量由调用者决定")
    next_tasks.add_argument("--limit", required=True, type=int)
    next_tasks.add_argument(
        "--trigger-kind",
        choices=(PERIODIC_TRIGGER, MANUAL_REWRITE_TRIGGER),
        help="只领取财报周期或人工重写任务",
    )
    next_tasks.add_argument(
        "--from-end",
        action="store_true",
        help="从队列尾部领取，便于与从队首运行的其他协调器避让",
    )
    _add_at(next_tasks)
    next_tasks.set_defaults(handler=_research_next)
    start = research_commands.add_parser("start", help="按任务 ID 精确领取一个排队任务")
    start.add_argument("task_id")
    _add_at(start)
    start.set_defaults(handler=_research_start)
    requeue = research_commands.add_parser("requeue", help="显式恢复被中断的任务")
    requeue.add_argument("task_id")
    requeue.set_defaults(handler=_research_requeue)
    complete = research_commands.add_parser("complete", help="写入 worker 的一次最终结果")
    _add_input(complete)
    complete.add_argument("--task-id", help="覆盖输入文件中由 research next 返回的 task_id")
    _add_at(complete)
    complete.set_defaults(handler=_research_complete)

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


_RETIRED_PRICE_FIELDS = frozenset({"price_levels", "price_monitor", "buy_below", "rearm_above"})
_RETIRED_DYNAMIC_RETURN_FIELDS = frozenset(
    {
        "expected_annual_return",
        "expected_irr",
        "current_irr",
        "irr",
        "year_3_irr",
        "year_5_irr",
    }
)


def _reject_retired_price_fields(payload: Mapping[str, Any]) -> None:
    present = sorted(_RETIRED_PRICE_FIELDS.intersection(payload))
    if present:
        raise ValueError("证券价格不再是研究触发器；请删除已退役字段：" + ", ".join(present))


def _reject_retired_dynamic_return_fields(payload: Mapping[str, Any]) -> None:
    present = sorted(_RETIRED_DYNAMIC_RETURN_FIELDS.intersection(payload))
    if present:
        raise ValueError(
            "动态回报只能由展示层使用实时价格现场计算；请删除字段：" + ", ".join(present)
        )


def _research_result(payload: Mapping[str, Any]) -> ResearchResult:
    _reject_retired_price_fields(payload)
    _reject_retired_dynamic_return_fields(payload)
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
    raw_return_model = payload.get("return_model")
    return_model = None
    if raw_return_model is not None:
        if not isinstance(raw_return_model, dict):
            raise ValueError("return_model 必须是对象或 null")
        expected_fields = {
            "schema_version",
            "method",
            "currency",
            "model_as_of",
            "base_case_distributions_per_share",
            "base_case_terminal_equity_value_range_per_share",
        }
        if set(raw_return_model) != expected_fields:
            raise ValueError("return_model 字段不符合 version 1 合同")
        return_model = ReturnModel(
            schema_version=raw_return_model["schema_version"],
            method=raw_return_model["method"],
            currency=raw_return_model["currency"],
            model_as_of=raw_return_model["model_as_of"],
            base_case_distributions_per_share=(
                raw_return_model["base_case_distributions_per_share"]
            ),
            base_case_terminal_equity_value_range_per_share=(
                raw_return_model["base_case_terminal_equity_value_range_per_share"]
            ),
        )
    return ResearchResult(
        symbol=payload["symbol"],
        name=payload.get("name"),
        outcome=payload["outcome"],
        summary=payload["summary"],
        key_logic=payload.get("key_logic") or (),
        risks=payload.get("risks") or (),
        value_range=value_range,
        source_urls=payload.get("source_urls") or (),
        information_cutoff=payload["information_cutoff"],
        report_period=payload["report_period"],
        report_markdown=payload.get("report_markdown"),
        valuation_note=payload.get("valuation_note"),
        return_model=return_model,
        return_model_note=payload.get("return_model_note"),
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


def _industry_list(args: argparse.Namespace, stdin: TextIO) -> dict[str, Any]:
    del stdin
    return industry_catalog(Path(args.root))


def _industry_validate(args: argparse.Namespace, stdin: TextIO) -> dict[str, Any]:
    del stdin
    return {"ok": True, **industry_catalog(Path(args.root), require_complete=True)}


def _quality_pool(args: argparse.Namespace) -> QualityPoolStore:
    return QualityPoolStore(Path(args.root))


def _quality_pool_status(args: argparse.Namespace, stdin: TextIO) -> dict[str, Any]:
    del stdin
    store = _quality_pool(args)
    pool = store.read()
    return {**pool.status(), "projection_current": store.projection_current(pool)}


def _quality_pool_validate(args: argparse.Namespace, stdin: TextIO) -> dict[str, Any]:
    del stdin
    return {"ok": True, "status": {
        **_quality_pool(args).validate().status(), "projection_current": True,
    }}


def _quality_pool_replace(args: argparse.Namespace, stdin: TextIO) -> dict[str, Any]:
    payload, _ = _load(args.input, stdin)
    store = _quality_pool(args)
    result = store.replace(payload)
    return {
        "pool_path": store.pool_path.relative_to(store.root).as_posix(),
        "current_path": store.current_path.relative_to(store.root).as_posix(),
        **result.pool.status(),
        "committed": True,
        "projection_current": result.projection_current,
        "warning": result.warning,
    }


def _quality_pool_list(args: argparse.Namespace, stdin: TextIO) -> dict[str, Any]:
    del stdin
    store = _quality_pool(args)
    pool = store.read()
    companies = [
        company for company in pool.companies if args.tier is None or company.tier == args.tier
    ]
    return {"count": len(companies), "companies": companies,
            "projection_current": store.projection_current(pool)}


def _quality_pool_rebuild(args: argparse.Namespace, stdin: TextIO) -> dict[str, Any]:
    del stdin
    return {"ok": True, **_quality_pool(args).rebuild().status(), "projection_current": True}


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


def _research_next(args: argparse.Namespace, stdin: TextIO) -> dict[str, Any]:
    del stdin
    tasks = _flow(args).dispatch_tasks(
        limit=args.limit,
        at=args.at,
        from_end=args.from_end,
        trigger_kind=args.trigger_kind,
    )
    return {"count": len(tasks), "tasks": tasks}


def _research_enqueue_period(args: argparse.Namespace, stdin: TextIO) -> dict[str, Any]:
    del stdin
    pool = _quality_pool(args).read()
    flow = _flow(args)
    flow.register_universe(
        [CompanyRef(symbol=company.symbol, name=company.name) for company in pool.companies],
        at=args.at,
    )
    update = flow.enqueue_research(
        [
            ResearchRequest(
                symbol=company.symbol,
                name=company.name,
                reason=f"完成 {args.period} 财报周期完整研究",
            )
            for company in pool.companies
        ],
        report_period=args.period,
        trigger_kind=PERIODIC_TRIGGER,
        at=args.at,
    )
    return {
        "total": update.total,
        "enqueued": update.enqueued_tasks,
        "deduplicated": update.deduplicated,
    }


def _research_enqueue_rewrite(args: argparse.Namespace, stdin: TextIO) -> dict[str, Any]:
    payload, _ = _load(args.input, stdin)
    metadata = payload if isinstance(payload, dict) else {}
    common_reason = metadata.get("reason")
    requests = []
    for item in _records(payload, "companies"):
        reason = item.get("reason") or common_reason
        if not reason:
            raise ValueError(f"{item.get('symbol', '<unknown>')} 缺少人工重写原因")
        requests.append(ResearchRequest(
            symbol=item["symbol"], name=item.get("name"), reason=reason,
        ))
    update = _flow(args).enqueue_research(
        requests,
        report_period=args.period,
        trigger_kind=MANUAL_REWRITE_TRIGGER,
        batch_id=args.batch_id,
        at=args.at or metadata.get("at"),
    )
    return {
        "total": update.total,
        "enqueued": update.enqueued_tasks,
        "deduplicated": update.deduplicated,
    }


def _research_requeue(args: argparse.Namespace, stdin: TextIO) -> dict[str, Any]:
    del stdin
    return {"task": _flow(args).requeue_task(args.task_id)}


def _research_start(args: argparse.Namespace, stdin: TextIO) -> dict[str, Any]:
    del stdin
    return {"task": _flow(args).start_task(args.task_id, at=args.at)}


def _research_complete(args: argparse.Namespace, stdin: TextIO) -> dict[str, Any]:
    payload, _ = _load(args.input, stdin)
    if not isinstance(payload, dict):
        raise ValueError("研究结果必须是 JSON 对象")
    _reject_retired_dynamic_return_fields(payload)
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
        "value_range": state["value_range"],
        "return_model": state["return_model"],
        "return_model_note": state["return_model_note"],
        "report_period": state["report_period"],
        "basis_report_path": state["basis_report_path"],
        "standard_id": state["standard_id"],
        "spec_revision": state["spec_revision"],
        "accepted_at": state["accepted_at"],
    }


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
