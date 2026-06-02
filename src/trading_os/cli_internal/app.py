from __future__ import annotations

import argparse
import sys

from ..research.cli import register_research_kernel_commands
from .commands.pool import register_pool_commands


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trading_os",
        description="Trading OS — agent-native research and quantitative analysis",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    register_research_kernel_commands(sub)
    register_pool_commands(sub)
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
