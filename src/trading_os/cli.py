"""Trading OS CLI.

Commands:
    lake-init      Initialize DuckDB/Parquet data lake
    fetch-ak       Fetch A-share daily bars from AKShare
    fetch-yf       Fetch bars from yfinance (US/HK stocks)
    seed           Seed synthetic bars (offline testing)
    query-bars     Query bars from the local lake
    backtest       Run backtest with A-share rules (ma/bh/rsi/agent)
    paper          Paper trading (ma/bh/rsi/agent)
    agent          One-shot Claude agent analysis
    paths          Print key repo paths
"""
from __future__ import annotations

import argparse
import os
from datetime import date as date_type
from datetime import datetime, timezone
import sys

from .paths import repo_root


# ---------------------------------------------------------------------------
# Data commands
# ---------------------------------------------------------------------------

def _cmd_paths(_: argparse.Namespace) -> int:
    root = repo_root()
    print(f"repo_root: {root}")
    print(f"docs:      {root / 'docs'}")
    print(f"data:      {root / 'data'}")
    print(f"artifacts: {root / 'artifacts'}")
    return 0


def _cmd_lake_init(_: argparse.Namespace) -> int:
    from .data.lake import LocalDataLake

    root = repo_root()
    lake = LocalDataLake(root / "data")
    lake.init()
    print(f"Initialized lake at: {lake.paths.duckdb_path}")
    return 0


def _cmd_fetch_ak(ns: argparse.Namespace) -> int:
    from .data.lake import LocalDataLake
    from .data.schema import Adjustment, Exchange, Timeframe
    from .data.sources.akshare_source import fetch_daily_bars

    root = repo_root()
    lake = LocalDataLake(root / "data")
    exch = Exchange(ns.exchange)
    adj = {"qfq": Adjustment.QFQ, "hfq": Adjustment.HFQ}.get(ns.adjustment, Adjustment.NONE)

    try:
        print(f"获取A股数据: {exch.value}:{ns.ticker} (复权: {adj.value})")
        df = fetch_daily_bars(ns.ticker, exchange=exch, start=ns.start, end=ns.end, adjustment=adj)
        if df.empty:
            print("未获取到数据")
            return 1
        lake.write_bars_parquet(
            df, exchange=exch, timeframe=Timeframe.D1, adjustment=adj,
            source="akshare", partition_hint=datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
        )
        lake.init()
        print(f"写入 {len(df)} 条: {exch.value}:{ns.ticker}")
        print(f"数据范围: {df['ts'].min().date()} 至 {df['ts'].max().date()}")
        return 0
    except Exception as e:
        print(f"获取A股数据失败: {e}", file=sys.stderr)
        return 1


def _cmd_fetch_bs(ns: argparse.Namespace) -> int:
    """从 BaoStock 获取 A 股数据（国内直连，无需代理）。"""
    from .data.lake import LocalDataLake
    from .data.schema import Adjustment, Exchange, Timeframe
    from .data.sources.baostock_source import fetch_daily_bars

    root = repo_root()
    lake = LocalDataLake(root / "data")
    exch = Exchange(ns.exchange)
    adj = {"qfq": Adjustment.QFQ, "hfq": Adjustment.HFQ}.get(ns.adjustment, Adjustment.NONE)

    try:
        print(f"获取A股数据(BaoStock): {exch.value}:{ns.ticker} (复权: {adj.value})")
        df = fetch_daily_bars(ns.ticker, exchange=exch, start=ns.start, end=ns.end, adjustment=adj)
        if df.empty:
            print("未获取到数据")
            return 1
        lake.write_bars_parquet(
            df, exchange=exch, timeframe=Timeframe.D1, adjustment=adj,
            source="baostock", partition_hint=datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
        )
        lake.init()
        print(f"写入 {len(df)} 条: {exch.value}:{ns.ticker}")
        print(f"数据范围: {df['ts'].min().date()} 至 {df['ts'].max().date()}")
        return 0
    except Exception as e:
        print(f"获取数据失败: {e}", file=sys.stderr)
        return 1


def _cmd_fetch_yf(ns: argparse.Namespace) -> int:
    from .data.lake import LocalDataLake
    from .data.schema import Adjustment, Exchange, Timeframe
    from .data.sources.yfinance_source import fetch_daily_bars

    root = repo_root()
    lake = LocalDataLake(root / "data")
    exch = Exchange(ns.exchange)
    df = fetch_daily_bars(ns.ticker, exchange=exch, start=ns.start, end=ns.end)
    if df.empty:
        print("No data fetched.")
        return 1
    lake.write_bars_parquet(
        df, exchange=exch, timeframe=Timeframe.D1, adjustment=Adjustment.NONE,
        source="yfinance", partition_hint=datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
    )
    lake.init()
    print(f"Wrote {len(df)} rows for {exch.value}:{ns.ticker}")
    return 0


def _cmd_seed(ns: argparse.Namespace) -> int:
    from .data.lake import LocalDataLake
    from .data.schema import Adjustment, Exchange, Timeframe
    from .data.sources.synthetic_source import make_daily_bars

    root = repo_root()
    lake = LocalDataLake(root / "data")
    exch = Exchange(ns.exchange)
    df = make_daily_bars(ns.ticker, exchange=exch).head(int(ns.days))
    lake.write_bars_parquet(
        df, exchange=exch, timeframe=Timeframe.D1, adjustment=Adjustment.NONE,
        source="synthetic", partition_hint=datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
    )
    lake.init()
    print(f"Seeded {len(df)} rows for {exch.value}:{ns.ticker}")
    return 0


def _cmd_query_bars(ns: argparse.Namespace) -> int:
    from .data.lake import LocalDataLake
    from .data.schema import Adjustment, Exchange, Timeframe

    root = repo_root()
    lake = LocalDataLake(root / "data")
    exch = Exchange(ns.exchange) if ns.exchange else None
    symbols = [s.strip() for s in ns.symbols.split(",")] if ns.symbols else None
    df = lake.query_bars(
        symbols=symbols, exchange=exch,
        timeframe=Timeframe(ns.timeframe), adjustment=Adjustment(ns.adjustment),
        start=ns.start, end=ns.end, limit=ns.limit,
    )
    print(df)
    return 0


# ---------------------------------------------------------------------------
# Strategy builder (shared)
# ---------------------------------------------------------------------------

def _cmd_fundamental(ns: argparse.Namespace) -> int:
    """获取股票财务摘要（BaoStock，免费，无需代理）。"""
    from .data.sources.fundamental_source import get_financial_summary

    symbols = [s.strip() for s in ns.symbols.split(",")]
    years = int(ns.years)

    for sym in symbols:
        data = get_financial_summary(sym, years=years)
        if data.get("error") and not data.get("profitability"):
            print(f"获取失败 {sym}: {data['error']}", file=sys.stderr)
            continue
        print(data["summary_text"])
        print()
    return 0


def _cmd_52week(ns: argparse.Namespace) -> int:
    """计算股票52周高低点统计（从本地K线，无需网络）。"""
    from .data.sources.fundamental_source import get_52week_stats

    symbols = [s.strip() for s in ns.symbols.split(",")]
    for sym in symbols:
        result = get_52week_stats(sym)
        print(result["summary_text"])
        print()
    return 0


def _cmd_market_breadth(ns: argparse.Namespace) -> int:
    """计算大盘换筹日数量，判断市场状态（从本地K线，无需网络）。"""
    from .data.sources.fundamental_source import get_market_breadth

    result = get_market_breadth(ns.index, lookback_days=int(ns.days))
    print(result["summary_text"])
    return 0


def _build_strategy(ns: argparse.Namespace):
    name = ns.strategy.lower()
    if name in ("ma", "macross"):
        from .strategy.builtin import MACrossStrategy
        return MACrossStrategy(fast=int(getattr(ns, "fast", 5)), slow=int(getattr(ns, "slow", 20)))
    elif name in ("bh", "buyandhold"):
        from .strategy.builtin import BuyAndHoldStrategy
        return BuyAndHoldStrategy()
    elif name == "rsi":
        from .strategy.builtin import RSIStrategy
        return RSIStrategy()
    elif name == "agent":
        from .strategy.agent import AgentConfig, AgentStrategy
        confirm = "auto" if getattr(ns, "bypass_confirm", False) else "confirm"
        # 从环境变量读取 LLM 配置（支持 MiniMax/通义千问等 OpenAI 兼容接口）
        # LLM_MODEL=MiniMax-M2.7 LLM_BASE_URL=https://api.minimaxi.com/v1 LLM_API_KEY=sk-...
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
    else:
        raise ValueError(f"Unknown strategy: {name!r}. Available: ma, bh, rsi, agent")


def _parse_date(s: str | None) -> date_type | None:
    return date_type.fromisoformat(s) if s else None


# ---------------------------------------------------------------------------
# Backtest
# ---------------------------------------------------------------------------

def _cmd_backtest(ns: argparse.Namespace) -> int:
    from .backtest.runner import BacktestConfig, BacktestRunner
    from .data.lake import LocalDataLake
    from .data.pipeline import DataPipeline

    root = repo_root()
    pipeline = DataPipeline(LocalDataLake(root / "data"))

    try:
        strategy = _build_strategy(ns)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1

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


# ---------------------------------------------------------------------------
# Paper trading
# ---------------------------------------------------------------------------

def _cmd_paper(ns: argparse.Namespace) -> int:
    from .backtest.runner import BacktestConfig
    from .data.lake import LocalDataLake
    from .data.pipeline import DataPipeline
    from .journal.event_log import EventLog
    from .paper.runner import PaperConfig, PaperRunner
    from .risk.manager import RiskConfig

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


# ---------------------------------------------------------------------------
# Agent one-shot
# ---------------------------------------------------------------------------

def _cmd_agent(ns: argparse.Namespace) -> int:
    from .data.lake import LocalDataLake
    from .data.pipeline import DataPipeline
    from .strategy.agent import AgentConfig, AgentStrategy

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
        print("No bars found. Fetch data first: trading-os fetch-ak ...", file=sys.stderr)
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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="trading_os", description="Trading OS — A-share quantitative trading")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # --- Data ---
    p = sub.add_parser("paths", help="Print key repo paths")
    p.set_defaults(func=_cmd_paths)

    p = sub.add_parser("lake-init", help="Initialize DuckDB/Parquet data lake")
    p.set_defaults(func=_cmd_lake_init)

    p = sub.add_parser("fundamental", help="获取股票财务摘要（BaoStock，无需代理）")
    p.add_argument("--symbols", required=True, help="逗号分隔的股票代码，如 SSE:600519,SSE:600000")
    p.add_argument("--years", type=int, default=5, help="获取最近几年数据（默认5年）")
    p.set_defaults(func=_cmd_fundamental)

    p = sub.add_parser("52week", help="计算股票52周高低点统计（从本地K线）")
    p.add_argument("--symbols", required=True, help="逗号分隔的股票代码，如 SSE:601138")
    p.set_defaults(func=_cmd_52week)

    p = sub.add_parser("market-breadth", help="计算大盘换筹日数量，判断市场状态（从本地K线）")
    p.add_argument("--index", default="SSE:000001", help="指数代码（默认上证综指）")
    p.add_argument("--days", type=int, default=30, help="统计窗口（默认30个交易日）")
    p.set_defaults(func=_cmd_market_breadth)

    p = sub.add_parser("fetch-bs", help="从BaoStock获取A股日线数据（国内直连，无需代理）")
    p.add_argument("--exchange", required=True, choices=["SSE", "SZSE"])
    p.add_argument("--ticker", required=True, help="股票代码，如 600000")
    p.add_argument("--start", default=None, help="开始日期 YYYY-MM-DD")
    p.add_argument("--end", default=None, help="结束日期 YYYY-MM-DD")
    p.add_argument("--adjustment", choices=["none", "qfq", "hfq"], default="qfq")
    p.set_defaults(func=_cmd_fetch_bs)

    p = sub.add_parser("fetch-ak", help="从AKShare获取A股日线数据")
    p.add_argument("--exchange", required=True, choices=["SSE", "SZSE"])
    p.add_argument("--ticker", required=True, help="股票代码，如 600000")
    p.add_argument("--start", default=None, help="开始日期 YYYY-MM-DD")
    p.add_argument("--end", default=None, help="结束日期 YYYY-MM-DD")
    p.add_argument("--adjustment", choices=["none", "qfq", "hfq"], default="qfq", help="复权方式")
    p.set_defaults(func=_cmd_fetch_ak)

    p = sub.add_parser("fetch-yf", help="Fetch bars from yfinance (US/HK stocks)")
    p.add_argument("--exchange", required=True)
    p.add_argument("--ticker", required=True)
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.set_defaults(func=_cmd_fetch_yf)

    p = sub.add_parser("seed", help="Seed synthetic daily bars (offline testing)")
    p.add_argument("--exchange", required=True)
    p.add_argument("--ticker", required=True)
    p.add_argument("--days", type=int, default=252)
    p.set_defaults(func=_cmd_seed)

    p = sub.add_parser("query-bars", help="Query bars from the local lake")
    p.add_argument("--exchange", default=None)
    p.add_argument("--symbols", default=None, help="Comma-separated symbol ids")
    p.add_argument("--timeframe", default="1d")
    p.add_argument("--adjustment", default="qfq")
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=_cmd_query_bars)

    # --- Strategy ---
    _STRATEGY_HELP = "Strategy: ma (MA crossover), bh (buy-and-hold), rsi (RSI), agent (Claude AI)"

    p = sub.add_parser("backtest", help="Run backtest with A-share rules")
    p.add_argument("--symbols", required=True, help="Comma-separated symbol ids, e.g. SSE:600000")
    p.add_argument("--strategy", default="ma", help=_STRATEGY_HELP)
    p.add_argument("--fast", type=int, default=5, help="Fast MA period")
    p.add_argument("--slow", type=int, default=20, help="Slow MA period")
    p.add_argument("--start", default=None, help="Start date YYYY-MM-DD")
    p.add_argument("--end", default=None, help="End date YYYY-MM-DD")
    p.add_argument("--initial-cash", type=float, default=1_000_000.0)
    p.set_defaults(func=_cmd_backtest)

    p = sub.add_parser("paper", help="Paper trading with A-share rules")
    p.add_argument("--symbols", required=True, help="Comma-separated symbol ids")
    p.add_argument("--strategy", default="ma", help=_STRATEGY_HELP)
    p.add_argument("--fast", type=int, default=5)
    p.add_argument("--slow", type=int, default=20)
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--initial-cash", type=float, default=1_000_000.0)
    p.add_argument("--bypass-confirm", action="store_true", help="Auto-execute without confirmation")
    p.set_defaults(func=_cmd_paper)

    p = sub.add_parser("agent", help="One-shot Claude agent analysis")
    p.add_argument("--symbols", required=True, help="Comma-separated symbol ids")
    p.add_argument("--date", default=None, help="Analysis date YYYY-MM-DD (default: today)")
    p.add_argument("--bypass-confirm", action="store_true")
    p.set_defaults(func=_cmd_agent)

    ns = parser.parse_args(argv)
    func = getattr(ns, "func", None)
    if not callable(func):
        return 2
    try:
        return int(func(ns))
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1
