from __future__ import annotations

import argparse
import sys

from .parser_builders import (
    register_daily_commands,
    register_data_commands,
    register_pool_commands,
    register_scan_commands,
    register_scheduler_commands,
    register_strategy_commands,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trading_os",
        description="Trading OS — A-share quantitative trading",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    register_data_commands(sub)
    register_strategy_commands(sub)
    register_scan_commands(sub)
    register_pool_commands(sub)
    register_scheduler_commands(sub)
    register_daily_commands(sub)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv)
    func = getattr(ns, "func", None)
    if not callable(func):
        return 2
    try:
        return int(func(ns))
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1
