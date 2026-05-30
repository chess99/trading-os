from __future__ import annotations

import argparse
import json
from datetime import date

from ..paths import repo_root
from .datahub import DataHub
from .recipes import (
    run_backtest_recipe,
    run_canslim_screen,
    run_company_research,
    run_daily_research,
    run_factor_research,
)
from .store import ResearchStore


def build_datahub() -> DataHub:
    return DataHub(ResearchStore(repo_root() / "data" / "research"))


def cmd_data(ns: argparse.Namespace) -> int:
    hub = build_datahub()
    if ns.data_cmd == "status":
        root = hub.store.root
        payload = {
            "research_store": str(root),
            "datasets": sorted(p.name for p in (root / "datasets").glob("*") if p.is_dir())
            if (root / "datasets").exists()
            else [],
            "runs": len(list((root / "runs").glob("*"))) if (root / "runs").exists() else 0,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    if ns.data_cmd == "refresh":
        as_of = date.fromisoformat(ns.as_of)
        if ns.dataset == "universe":
            df = hub.get_universe(as_of, policy="refresh")
        elif ns.dataset == "quotes":
            df = hub.get_quote_snapshot(as_of, policy="refresh")
        elif ns.dataset == "bars":
            symbols = [s.strip() for s in ns.symbols.split(",") if s.strip()]
            df = hub.get_bars(
                symbols,
                start=date.fromisoformat(ns.start),
                end=date.fromisoformat(ns.end),
                adjustment=ns.adjustment,
                policy="refresh",
            )
        else:  # pragma: no cover
            raise RuntimeError(f"unknown dataset: {ns.dataset}")
        print(f"refreshed {ns.dataset}: {len(df)} rows")
        return 0
    raise RuntimeError(f"unknown data command: {ns.data_cmd}")


def cmd_research(ns: argparse.Namespace) -> int:
    hub = build_datahub()
    if ns.research_cmd == "run":
        as_of = date.fromisoformat(ns.as_of)
        if ns.recipe != "canslim_screen":
            raise RuntimeError(f"unknown research recipe: {ns.recipe}")
        result = run_canslim_screen(hub, as_of=as_of, top_n=ns.top, min_turnover=ns.min_turnover)
    elif ns.research_cmd == "company":
        result = run_company_research(
            hub,
            ns.symbol,
            as_of=date.fromisoformat(ns.as_of),
            template=ns.template,
        )
    elif ns.research_cmd == "daily":
        result = run_daily_research(hub, as_of=date.fromisoformat(ns.as_of))
    else:  # pragma: no cover
        raise RuntimeError(f"unknown research command: {ns.research_cmd}")
    print(f"run_id: {result.run.run_id}")
    print(f"manifest: {result.run.path / 'manifest.json'}")
    print(f"report: {result.run.path / 'report.md'}")
    return 0


def cmd_factor(ns: argparse.Namespace) -> int:
    hub = build_datahub()
    result = run_factor_research(
        hub,
        as_of=date.fromisoformat(ns.as_of),
        factor_name=ns.factor_spec,
    )
    print(f"run_id: {result.run.run_id}")
    print(f"manifest: {result.run.path / 'manifest.json'}")
    return 0


def cmd_backtest_recipe(ns: argparse.Namespace) -> int:
    hub = build_datahub()
    result = run_backtest_recipe(
        hub,
        start=date.fromisoformat(ns.start),
        end=date.fromisoformat(ns.end),
        strategy_name=ns.strategy_spec,
    )
    print(f"run_id: {result.run.run_id}")
    print(f"manifest: {result.run.path / 'manifest.json'}")
    return 0


def register_research_kernel_commands(sub: argparse._SubParsersAction) -> None:
    data = sub.add_parser("data", help="ResearchStore data refresh and status")
    data_sub = data.add_subparsers(dest="data_cmd", required=True)
    data_status = data_sub.add_parser("status", help="Show ResearchStore status")
    data_status.set_defaults(func=cmd_data)
    refresh = data_sub.add_parser("refresh", help="Refresh a ResearchStore dataset")
    refresh.add_argument("dataset", choices=["universe", "quotes", "bars"])
    refresh.add_argument("--as-of", required=True, dest="as_of")
    refresh.add_argument("--symbols", default="")
    refresh.add_argument("--start", default="2020-01-01")
    refresh.add_argument("--end", required=True)
    refresh.add_argument("--adjustment", default="qfq")
    refresh.set_defaults(func=cmd_data)

    research = sub.add_parser("research", help="Run deterministic research recipes")
    research_sub = research.add_subparsers(dest="research_cmd", required=True)
    run = research_sub.add_parser("run", help="Run a named research recipe")
    run.add_argument("recipe", choices=["canslim_screen"])
    run.add_argument("--as-of", required=True, dest="as_of")
    run.add_argument("--top", type=int, default=30)
    run.add_argument("--min-turnover", type=float, default=10_000_000.0)
    run.set_defaults(func=cmd_research)
    company = research_sub.add_parser("company", help="Run company research")
    company.add_argument("symbol")
    company.add_argument("--template", default="quality_growth")
    company.add_argument("--as-of", required=True, dest="as_of")
    company.set_defaults(func=cmd_research)
    daily = research_sub.add_parser(
        "daily", help="Run daily research without a full-market bar refresh gate"
    )
    daily.add_argument("--as-of", required=True, dest="as_of")
    daily.set_defaults(func=cmd_research)

    factor = sub.add_parser("factor", help="Run factor research")
    factor_sub = factor.add_subparsers(dest="factor_cmd", required=True)
    factor_run = factor_sub.add_parser("run")
    factor_run.add_argument("factor_spec")
    factor_run.add_argument("--as-of", required=True, dest="as_of")
    factor_run.set_defaults(func=cmd_factor)

    backtest = sub.add_parser("backtest", help="Run a ResearchStore-backed backtest recipe")
    backtest_sub = backtest.add_subparsers(dest="backtest_cmd", required=True)
    backtest_run = backtest_sub.add_parser("run")
    backtest_run.add_argument("strategy_spec")
    backtest_run.add_argument("--start", required=True)
    backtest_run.add_argument("--end", required=True)
    backtest_run.set_defaults(func=cmd_backtest_recipe)
