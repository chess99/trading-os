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


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv)
    func = getattr(ns, "func", None)
    if not callable(func):
        return 2
    try:
        return int(func(ns))
    except (AssetValidationError, RuntimeError, FileNotFoundError, json.JSONDecodeError) as exc:
        return _write_failure({"ok": False, "error": str(exc)})


def _write_failure(payload: dict[str, object], stream: TextIO | None = None) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=stream or sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
