from __future__ import annotations

import argparse
import os
import sys
from datetime import date as date_type

from ...paths import repo_root


def _build_strategy(ns: argparse.Namespace):
    name = ns.strategy.lower()
    if name in ("ma", "macross"):
        from ...strategy.builtin import MACrossStrategy
        return MACrossStrategy(fast=int(getattr(ns, "fast", 5)), slow=int(getattr(ns, "slow", 20)))
    if name in ("bh", "buyandhold"):
        from ...strategy.builtin import BuyAndHoldStrategy
        return BuyAndHoldStrategy()
    if name == "rsi":
        from ...strategy.builtin import RSIStrategy
        return RSIStrategy()
    if name == "agent":
        from ...strategy.agent import AgentConfig, AgentStrategy

        confirm = "auto" if getattr(ns, "bypass_confirm", False) else "confirm"
        model = os.environ.get("LLM_MODEL", "claude-opus-4-6")
        base_url = os.environ.get("LLM_BASE_URL") or None
        api_key = os.environ.get("LLM_API_KEY") or None
        return AgentStrategy(AgentConfig(
            model=model,
            api_base_url=base_url,
            api_key=api_key,
            confirm_mode=confirm,
            cache_dir=str(repo_root() / "artifacts" / "agent_cache"),
        ))
    if name in ("elder", "elder_triple_screen"):
        from ...strategy.elder import ElderStrategy
        return ElderStrategy()
    raise ValueError(f"Unknown strategy: {name!r}. Available: ma, bh, rsi, agent, elder")


def _parse_date(s: str | None) -> date_type | None:
    return date_type.fromisoformat(s) if s else None


def _cmd_backtest(ns: argparse.Namespace) -> int:
    from ...backtest.runner import BacktestConfig, BacktestRunner
    from ...data.lake import LocalDataLake
    from ...data.pipeline import DataPipeline

    root = repo_root()
    pipeline = DataPipeline(LocalDataLake(root / "data"))
    try:
        strategy = _build_strategy(ns)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1

    if ns.symbols.strip().lower() == "all":
        symbols = pipeline.available_symbols()
        if not symbols:
            print("本地没有任何股票数据，请先运行 fetch-ak-bulk", file=sys.stderr)
            return 1
        print(f"--symbols all: 使用本地全部 {len(symbols)} 只股票")
    else:
        symbols = [s.strip() for s in ns.symbols.split(",")]
    start = _parse_date(ns.start) or date_type(2022, 1, 1)
    end = _parse_date(ns.end) or date_type.today()

    runner = BacktestRunner(
        strategy=strategy,
        pipeline=pipeline,
        config=BacktestConfig(initial_cash=float(ns.initial_cash)),
    )
    print(f"Backtest: {ns.strategy} | {symbols} | {start} → {end}")
    result = runner.run(symbols=symbols, start=start, end=end)
    s = result.summary()
    print(f"\n{'='*52}")
    print(f"  Total Return:      {s.get('total_return', 0):>8.2f}%")
    print(f"  Annualized Return: {s.get('annualized_return', 0):>8.2f}%")
    print(f"  Sharpe Ratio:      {s.get('sharpe_ratio', 0):>8.3f}")
    print(f"  Max Drawdown:      {s.get('max_drawdown', 0):>8.2f}%")
    print(f"  Final NAV:         {s.get('final_nav', 0):>14,.2f} CNY")
    print(f"  Trades:            {s.get('trades', 0):>8}")
    print(f"{'='*52}")
    if not result.equity_curve.empty:
        print("\nEquity curve (last 5 rows):")
        print(result.equity_curve.tail(5).to_string(index=False))
    return 0


def _cmd_paper(ns: argparse.Namespace) -> int:
    from ...backtest.runner import BacktestConfig
    from ...data.lake import LocalDataLake
    from ...data.pipeline import DataPipeline
    from ...journal.event_log import EventLog
    from ...paper.runner import PaperConfig, PaperRunner
    from ...risk.manager import RiskConfig

    root = repo_root()
    pipeline = DataPipeline(LocalDataLake(root / "data"))
    try:
        strategy = _build_strategy(ns)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1

    symbols = [s.strip() for s in ns.symbols.split(",")]
    start = _parse_date(ns.start) or date_type(2024, 1, 1)
    end = _parse_date(ns.end) or date_type.today()
    confirm = "auto" if getattr(ns, "bypass_confirm", False) else "confirm"

    config = PaperConfig(
        initial_cash=float(ns.initial_cash),
        confirm_mode=confirm,
        broker=BacktestConfig(),
        risk=RiskConfig(),
    )
    event_log = EventLog.from_repo_root(root, name=f"paper_{start}_{end}")
    runner = PaperRunner(strategy=strategy, pipeline=pipeline, config=config, event_log=event_log)
    print(f"Paper: {ns.strategy} | {symbols} | {start} → {end} | mode={confirm}")
    session = runner.run(symbols=symbols, start=start, end=end)
    s = session.summary()
    print(f"\n{'='*52}")
    print(f"  Total Return:  {s['total_return']:>10}")
    print(f"  Final NAV:     {s['final_nav']:>14,.2f} CNY")
    print(f"  Fills:         {s['fills']:>8}")
    print(f"  Rejects:       {s['rejects']:>8}")
    print(f"  Log:           {s['log']}")
    print(f"{'='*52}")
    return 0


def _cmd_agent(ns: argparse.Namespace) -> int:
    from ...data.lake import LocalDataLake
    from ...data.pipeline import DataPipeline
    from ...strategy.agent import AgentConfig, AgentStrategy

    root = repo_root()
    pipeline = DataPipeline(LocalDataLake(root / "data"))
    symbols = [s.strip() for s in ns.symbols.split(",")]
    trading_date = _parse_date(ns.date) or date_type.today()
    confirm = "auto" if getattr(ns, "bypass_confirm", False) else "confirm"
    model = os.environ.get("LLM_MODEL", "claude-opus-4-6")
    base_url = os.environ.get("LLM_BASE_URL") or None
    api_key = os.environ.get("LLM_API_KEY") or None
    strategy = AgentStrategy(AgentConfig(
        model=model,
        api_base_url=base_url,
        api_key=api_key,
        confirm_mode=confirm,
        cache_dir=str(root / "artifacts" / "agent_cache"),
    ))

    bars = pipeline.get_bars(symbols=symbols, trading_date=trading_date)
    if bars is None or bars.empty:
        print("No bars found. Fetch data first: trading-os fetch-bars ...", file=sys.stderr)
        return 1
    print(f"Analyzing {symbols} for {trading_date}...")
    signals = strategy.generate_signals(bars, trading_date)
    print(f"\n{'='*60}")
    print(f"  Agent Signals — {trading_date}")
    print(f"{'='*60}")
    for sym, sig in sorted(signals.items()):
        marker = "→" if sig.action != "HOLD" else " "
        print(f"  {marker} {sig.action:4s}  {sym:20s}  size={sig.size:.1%}  conf={sig.confidence:.0%}")
        if sig.reason:
            print(f"       {sig.reason}")
    print(f"{'='*60}")
    return 0
