from __future__ import annotations

import argparse
import json
import sys
from typing import TextIO

from .research_assets.alerts import (
    evaluate_price_alerts,
    load_json,
    write_price_alerts,
)
from .research_assets.company import AssetValidationError, validate_company_dir
from .research_assets.coverage_store import (
    CoverageValidationError,
    coverage_status,
    enqueue_research,
    get_symbol,
    list_screening,
    set_screening,
    validate_coverage_root,
)
from .research_assets.index import write_index
from .research_assets.schedule import write_review_schedule


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trading_os",
        description="Trading OS research asset tools",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    company = sub.add_parser("company", help="Validate company research assets")
    company_sub = company.add_subparsers(dest="company_cmd", required=True)
    validate = company_sub.add_parser("validate", help="Validate one company directory")
    validate.add_argument("path")
    validate.set_defaults(func=cmd_company_validate)

    index = sub.add_parser("index", help="Build generated research indexes")
    index_sub = index.add_subparsers(dest="index_cmd", required=True)
    rebuild = index_sub.add_parser("rebuild", help="Rebuild research/index.json")
    rebuild.add_argument("--research-root", default="research")
    rebuild.set_defaults(func=cmd_index_rebuild)

    alerts = sub.add_parser("alerts", help="Build and check price alerts")
    alerts_sub = alerts.add_subparsers(dest="alerts_cmd", required=True)
    alerts_build = alerts_sub.add_parser(
        "build",
        help="Build automation/price_alerts.json",
    )
    alerts_build.add_argument("--research-root", default="research")
    alerts_build.add_argument("--output", default="automation/price_alerts.json")
    alerts_build.set_defaults(func=cmd_alerts_build)
    alerts_check = alerts_sub.add_parser(
        "check",
        help="Check price alerts with a quote JSON file",
    )
    alerts_check.add_argument("--alerts", default="automation/price_alerts.json")
    alerts_check.add_argument("--quotes", required=True)
    alerts_check.set_defaults(func=cmd_alerts_check)

    schedule = sub.add_parser("schedule", help="Build review schedules")
    schedule_sub = schedule.add_subparsers(dest="schedule_cmd", required=True)
    schedule_build = schedule_sub.add_parser(
        "build",
        help="Build automation/review_schedule.json",
    )
    schedule_build.add_argument("--research-root", default="research")
    schedule_build.add_argument("--output", default="automation/review_schedule.json")
    schedule_build.set_defaults(func=cmd_schedule_build)

    coverage = sub.add_parser("coverage", help="Manage coverage screening JSONL files")
    coverage_sub = coverage.add_subparsers(dest="coverage_cmd", required=True)

    coverage_validate = coverage_sub.add_parser("validate", help="Validate coverage JSONL")
    _add_coverage_root(coverage_validate)
    coverage_validate.set_defaults(func=cmd_coverage_validate)

    coverage_status_cmd = coverage_sub.add_parser("status", help="Show coverage counts")
    _add_coverage_root(coverage_status_cmd)
    coverage_status_cmd.set_defaults(func=cmd_coverage_status)

    coverage_get = coverage_sub.add_parser("get", help="Get coverage records for one symbol")
    coverage_get.add_argument("symbol")
    _add_coverage_root(coverage_get)
    coverage_get.set_defaults(func=cmd_coverage_get)

    coverage_list = coverage_sub.add_parser("list", help="List screening records")
    _add_coverage_root(coverage_list)
    coverage_list.add_argument("--decision")
    coverage_list.set_defaults(func=cmd_coverage_list)

    set_cmd = coverage_sub.add_parser("set-screening", help="Upsert one screening result")
    set_cmd.add_argument("symbol")
    _add_coverage_root(set_cmd)
    set_cmd.add_argument("--name", required=True)
    set_cmd.add_argument("--decision", required=True)
    set_cmd.add_argument("--priority", type=int)
    set_cmd.add_argument("--reason", required=True)
    set_cmd.add_argument("--evidence", action="append", required=True)
    set_cmd.add_argument("--next-action", required=True)
    set_cmd.set_defaults(func=cmd_coverage_set_screening)

    enqueue = coverage_sub.add_parser("enqueue", help="Upsert one research queue item")
    enqueue.add_argument("symbol")
    _add_coverage_root(enqueue)
    enqueue.add_argument("--name", required=True)
    enqueue.add_argument("--priority", type=int, required=True)
    enqueue.add_argument("--reason", required=True)
    enqueue.add_argument("--task-type", default="initial_research")
    enqueue.add_argument("--status", default="pending")
    enqueue.add_argument("--target-company-dir")
    enqueue.set_defaults(func=cmd_coverage_enqueue)
    return parser


def cmd_company_validate(ns: argparse.Namespace) -> int:
    meta = validate_company_dir(ns.path)
    print(
        json.dumps({"ok": True, "symbol": meta["symbol"]}, ensure_ascii=False, indent=2)
    )
    return 0


def cmd_index_rebuild(ns: argparse.Namespace) -> int:
    result = write_index(ns.research_root)
    if not result.ok:
        return _write_failure({"ok": False, "errors": result.errors})
    print(json.dumps({"ok": True, "path": str(result.path)}, ensure_ascii=False, indent=2))
    return 0


def cmd_alerts_build(ns: argparse.Namespace) -> int:
    path = write_price_alerts(ns.research_root, ns.output)
    print(json.dumps({"ok": True, "path": str(path)}, ensure_ascii=False, indent=2))
    return 0


def cmd_alerts_check(ns: argparse.Namespace) -> int:
    alerts = load_json(ns.alerts)
    quotes = load_json(ns.quotes)
    if not isinstance(alerts, dict):
        raise RuntimeError("alerts file must be a JSON object")
    if not isinstance(quotes, list):
        raise RuntimeError("quote snapshot must be a JSON list")
    result = evaluate_price_alerts(alerts, quotes)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_schedule_build(ns: argparse.Namespace) -> int:
    path = write_review_schedule(ns.research_root, ns.output)
    print(json.dumps({"ok": True, "path": str(path)}, ensure_ascii=False, indent=2))
    return 0


def cmd_coverage_validate(ns: argparse.Namespace) -> int:
    status = validate_coverage_root(ns.root)
    print(json.dumps({"ok": True, "status": status}, ensure_ascii=False, indent=2))
    return 0


def cmd_coverage_status(ns: argparse.Namespace) -> int:
    print(json.dumps(coverage_status(ns.root), ensure_ascii=False, indent=2))
    return 0


def cmd_coverage_get(ns: argparse.Namespace) -> int:
    print(json.dumps(get_symbol(ns.root, ns.symbol), ensure_ascii=False, indent=2))
    return 0


def cmd_coverage_list(ns: argparse.Namespace) -> int:
    payload = {
        "schema_version": 1,
        "items": list_screening(ns.root, ns.decision),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_coverage_set_screening(ns: argparse.Namespace) -> int:
    path = set_screening(
        ns.root,
        symbol=ns.symbol,
        name=ns.name,
        decision=ns.decision,
        priority=ns.priority,
        reason=ns.reason,
        evidence=ns.evidence,
        next_action=ns.next_action,
    )
    print(json.dumps({"ok": True, "path": str(path)}, ensure_ascii=False, indent=2))
    return 0


def cmd_coverage_enqueue(ns: argparse.Namespace) -> int:
    path = enqueue_research(
        ns.root,
        symbol=ns.symbol,
        name=ns.name,
        priority=ns.priority,
        reason=ns.reason,
        task_type=ns.task_type,
        status=ns.status,
        target_company_dir=ns.target_company_dir,
    )
    print(json.dumps({"ok": True, "path": str(path)}, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv)
    func = getattr(ns, "func", None)
    if not callable(func):
        return 2
    try:
        return int(func(ns))
    except (
        AssetValidationError,
        CoverageValidationError,
        RuntimeError,
        FileNotFoundError,
        json.JSONDecodeError,
    ) as exc:
        return _write_failure({"ok": False, "error": str(exc)})


def _write_failure(payload: dict[str, object], stream: TextIO | None = None) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=stream or sys.stderr)
    return 1


def _add_coverage_root(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", default="coverage/cn-a")


if __name__ == "__main__":
    raise SystemExit(main())
