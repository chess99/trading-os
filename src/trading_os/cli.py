from __future__ import annotations

import argparse
from datetime import datetime, timezone
import sys

from .paths import repo_root


def _cmd_paths(_: argparse.Namespace) -> int:
    root = repo_root()
    print(f"repo_root: {root}")
    print(f"docs:      {root / 'docs'}")
    print(f"journal:   {root / 'journal'}")
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


def _cmd_fetch_yf(ns: argparse.Namespace) -> int:
    from .data.lake import LocalDataLake
    from .data.schema import Adjustment, Exchange, Timeframe
    from .data.sources.yfinance_source import fetch_daily_bars

    root = repo_root()
    lake = LocalDataLake(root / "data")

    exch = Exchange(ns.exchange)
    tf = Timeframe.D1
    adj = Adjustment.NONE

    df = fetch_daily_bars(ns.ticker, exchange=exch, start=ns.start, end=ns.end)
    if df.empty:
        print("No data fetched.")
        return 1

    lake.write_bars_parquet(
        df,
        exchange=exch,
        timeframe=tf,
        adjustment=adj,
        source="yfinance",
        partition_hint=datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
    )
    lake.init()
    print(f"Wrote {len(df)} rows for {exch.value}:{ns.ticker}")
    return 0


def _cmd_fetch_ak(ns: argparse.Namespace) -> int:
    from .data.lake import LocalDataLake
    from .data.schema import Adjustment, Exchange, Timeframe
    from .data.sources.akshare_source import fetch_daily_bars

    root = repo_root()
    lake = LocalDataLake(root / "data")

    exch = Exchange(ns.exchange)
    tf = Timeframe.D1

    if ns.adjustment == "qfq":
        adj = Adjustment.QFQ
    elif ns.adjustment == "hfq":
        adj = Adjustment.HFQ
    else:
        adj = Adjustment.NONE

    try:
        print(f"获取A股数据: {exch.value}:{ns.ticker} (复权: {adj.value})")
        df = fetch_daily_bars(
            ns.ticker,
            exchange=exch,
            start=ns.start,
            end=ns.end,
            adjustment=adj,
        )
        if df.empty:
            print("未获取到数据")
            return 1
        lake.write_bars_parquet(
            df,
            exchange=exch,
            timeframe=tf,
            adjustment=adj,
            source="akshare",
            partition_hint=datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
        )
        lake.init()
        print(f"写入 {len(df)} 条: {exch.value}:{ns.ticker}")
        print(f"数据范围: {df['ts'].min().date()} 至 {df['ts'].max().date()}")
        return 0
    except Exception as e:
        print(f"获取A股数据失败: {e}")
        return 1


def _cmd_seed(ns: argparse.Namespace) -> int:
    from .data.lake import LocalDataLake
    from .data.schema import Adjustment, Exchange, Timeframe
    from .data.sources.synthetic_source import make_daily_bars

    root = repo_root()
    lake = LocalDataLake(root / "data")

    exch = Exchange(ns.exchange)
    tf = Timeframe.D1
    adj = Adjustment.NONE

    df = make_daily_bars(ns.ticker, exchange=exch)
    df = df.head(int(ns.days))
    lake.write_bars_parquet(
        df,
        exchange=exch,
        timeframe=tf,
        adjustment=adj,
        source="synthetic",
        partition_hint=datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
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
    tf = Timeframe(ns.timeframe)
    adj = Adjustment(ns.adjustment)

    symbols = None
    if ns.symbols:
        symbols = [s.strip() for s in ns.symbols.split(",") if s.strip()]

    df = lake.query_bars(
        symbols=symbols,
        exchange=exch,
        timeframe=tf,
        adjustment=adj,
        start=ns.start,
        end=ns.end,
        limit=ns.limit,
    )
    print(df)
    return 0


def _cmd_backtest_sma(ns: argparse.Namespace) -> int:
    from .backtest.engine import BacktestConfig, run_backtest
    from .backtest.metrics import compute_performance_metrics
    from .backtest.strategies import sma_crossover_signals
    from .data.lake import LocalDataLake
    from .data.schema import Adjustment, Timeframe

    root = repo_root()
    lake = LocalDataLake(root / "data")

    bars = lake.query_bars(
        symbols=[ns.symbol],
        timeframe=Timeframe(ns.timeframe),
        adjustment=Adjustment(ns.adjustment),
        start=ns.start,
        end=ns.end,
        limit=None,
    )
    if bars.empty:
        raise RuntimeError("No bars found for requested query.")

    cfg = BacktestConfig(
        initial_cash=float(ns.initial_cash),
        fee_bps=float(ns.fee_bps),
        slippage_bps=float(ns.slippage_bps),
    )
    res = run_backtest(
        bars,
        signals_fn=lambda b: sma_crossover_signals(b, fast=int(ns.fast), slow=int(ns.slow)),
        config=cfg,
    )
    m = compute_performance_metrics(res.equity_curve)

    print(f"symbol: {res.symbol}")
    print(f"total_return: {m.total_return:.4f}")
    print(f"max_drawdown: {m.max_drawdown:.4f}")
    if m.sharpe is not None:
        print(f"sharpe: {m.sharpe:.3f}")
    if m.cagr is not None:
        print(f"cagr: {m.cagr:.4f}")
    print(f"trades: {len(res.trades)}")
    print(res.equity_curve.tail(5))
    return 0


def _cmd_backtest_bh(ns: argparse.Namespace) -> int:
    from .backtest.engine import BacktestConfig, run_backtest
    from .backtest.metrics import compute_performance_metrics
    from .backtest.strategies import buy_and_hold_signals
    from .data.lake import LocalDataLake
    from .data.schema import Adjustment, Timeframe

    root = repo_root()
    lake = LocalDataLake(root / "data")

    bars = lake.query_bars(
        symbols=[ns.symbol],
        timeframe=Timeframe(ns.timeframe),
        adjustment=Adjustment(ns.adjustment),
        start=ns.start,
        end=ns.end,
        limit=None,
    )
    if bars.empty:
        raise RuntimeError("No bars found for requested query.")

    cfg = BacktestConfig(
        initial_cash=float(ns.initial_cash),
        fee_bps=float(ns.fee_bps),
        slippage_bps=float(ns.slippage_bps),
    )
    res = run_backtest(bars, signals_fn=buy_and_hold_signals, config=cfg)
    m = compute_performance_metrics(res.equity_curve)
    print(f"symbol: {res.symbol}")
    print(f"total_return: {m.total_return:.4f}")
    print(f"max_drawdown: {m.max_drawdown:.4f}")
    if m.sharpe is not None:
        print(f"sharpe: {m.sharpe:.3f}")
    if m.cagr is not None:
        print(f"cagr: {m.cagr:.4f}")
    print(f"trades: {len(res.trades)}")
    print(res.equity_curve.tail(5))
    return 0


def _cmd_paper_run_sma(ns: argparse.Namespace) -> int:
    from .backtest.strategies import sma_crossover_signals
    from .data.lake import LocalDataLake
    from .data.schema import Adjustment, Timeframe
    from .execution.engine import PaperEngineConfig, PaperTradingEngine
    from .journal.event_log import EventLog
    from .risk.manager import RiskConfig, RiskManager

    root = repo_root()
    lake = LocalDataLake(root / "data")
    bars = lake.query_bars(
        symbols=[ns.symbol],
        timeframe=Timeframe(ns.timeframe),
        adjustment=Adjustment(ns.adjustment),
        start=ns.start,
        end=ns.end,
        limit=None,
    )
    if bars.empty:
        raise RuntimeError("No bars found for requested query.")

    log_path = root / "artifacts" / "paper" / f"events_{ns.symbol.replace(':', '_')}.jsonl"
    elog = EventLog(log_path)

    elog.write(
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "kind": "decision",
            "payload": {
                "engine": "paper-run-sma",
                "symbol": ns.symbol,
                "strategy": {"name": "sma_crossover", "fast": int(ns.fast), "slow": int(ns.slow)},
                "bars": {"timeframe": ns.timeframe, "adjustment": ns.adjustment},
                "costs": {"fee_bps": float(ns.fee_bps), "slippage_bps": float(ns.slippage_bps)},
                "risk": {
                    "max_gross": float(ns.max_gross),
                    "max_pos": float(ns.max_pos),
                    "cooldown": int(ns.cooldown),
                    "stop_loss": float(ns.stop_loss) if ns.stop_loss is not None else None,
                    "max_daily_loss": float(ns.max_daily_loss) if ns.max_daily_loss is not None else None,  # noqa: E501
                    "circuit_breaker": float(ns.circuit_breaker) if ns.circuit_breaker is not None else None,  # noqa: E501
                },
            },
        }
    )

    risk = RiskManager(
        RiskConfig(
            max_gross_exposure_pct=float(ns.max_gross),
            max_position_pct=float(ns.max_pos),
            cooldown_bars=int(ns.cooldown),
            stop_loss_pct=float(ns.stop_loss) if ns.stop_loss is not None else None,
            max_daily_loss_pct=float(ns.max_daily_loss) if ns.max_daily_loss is not None else None,
            circuit_breaker_drawdown_pct=float(ns.circuit_breaker) if ns.circuit_breaker is not None else None,  # noqa: E501
        )
    )
    engine = PaperTradingEngine(
        config=PaperEngineConfig(
            initial_cash=float(ns.initial_cash),
            fee_bps=float(ns.fee_bps),
            slippage_bps=float(ns.slippage_bps),
        ),
        risk=risk,
        event_log=elog,
    )
    curve = engine.run_single_symbol(
        bars,
        signals_fn=lambda b: sma_crossover_signals(b, fast=int(ns.fast), slow=int(ns.slow)),
    )
    print(f"wrote_events: {log_path}")
    print(curve.tail(5))
    return 0


def _cmd_backtest(ns: argparse.Namespace) -> int:
    """New event-driven backtest using unified Strategy interface."""
    from datetime import date as date_type

    from .backtest.runner import BacktestConfig, BacktestRunner
    from .data.lake import LocalDataLake
    from .data.pipeline import DataPipeline

    root = repo_root()
    lake = LocalDataLake(root / "data")
    pipeline = DataPipeline(lake)

    # Parse strategy
    strategy_name = ns.strategy.lower()
    if strategy_name == "ma" or strategy_name == "macross":
        from .strategy.builtin import MACrossStrategy
        strategy = MACrossStrategy(fast=int(ns.fast), slow=int(ns.slow))
    elif strategy_name == "bh" or strategy_name == "buyandhold":
        from .strategy.builtin import BuyAndHoldStrategy
        strategy = BuyAndHoldStrategy()
    elif strategy_name == "rsi":
        from .strategy.builtin import RSIStrategy
        strategy = RSIStrategy()
    else:
        print(f"Unknown strategy: {ns.strategy}. Use: ma, bh, rsi", file=sys.stderr)
        return 1

    # Parse symbols
    symbols = [s.strip() for s in ns.symbols.split(",")]

    # Parse dates
    def _parse_date(s: str | None) -> date_type | None:
        if s is None:
            return None
        return date_type.fromisoformat(s)

    start = _parse_date(ns.start) or date_type(2022, 1, 1)
    end = _parse_date(ns.end) or date_type.today()

    config = BacktestConfig(
        initial_cash=float(ns.initial_cash),
    )

    runner = BacktestRunner(strategy=strategy, pipeline=pipeline, config=config)

    print(f"Running backtest: {strategy_name} | {symbols} | {start} → {end}")
    result = runner.run(symbols=symbols, start=start, end=end)
    summary = result.summary()

    print(f"\n{'='*50}")
    print(f"  Total Return:      {summary.get('total_return', 0):.2f}%")
    print(f"  Annualized Return: {summary.get('annualized_return', 0):.2f}%")
    print(f"  Sharpe Ratio:      {summary.get('sharpe_ratio', 0):.3f}")
    print(f"  Max Drawdown:      {summary.get('max_drawdown', 0):.2f}%")
    print(f"  Final NAV:         {summary.get('final_nav', 0):,.2f} CNY")
    print(f"  Trades:            {summary.get('trades', 0)}")
    print(f"{'='*50}")

    if not result.equity_curve.empty:
        print("\nEquity curve (last 5 rows):")
        print(result.equity_curve.tail(5).to_string(index=False))

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="trading_os", description="Trading OS CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_paths = sub.add_parser("paths", help="Print key repo paths")
    p_paths.set_defaults(func=_cmd_paths)

    p_lake = sub.add_parser("lake-init", help="Initialize local DuckDB/Parquet data lake")
    p_lake.set_defaults(func=_cmd_lake_init)

    p_yf = sub.add_parser("fetch-yf", help="Fetch daily bars from yfinance")
    p_yf.add_argument("--exchange", required=True)
    p_yf.add_argument("--ticker", required=True)
    p_yf.add_argument("--start", default=None)
    p_yf.add_argument("--end", default=None)
    p_yf.set_defaults(func=_cmd_fetch_yf)

    p_ak = sub.add_parser("fetch-ak", help="从akshare获取A股数据")
    p_ak.add_argument("--exchange", required=True, choices=["SSE", "SZSE"])
    p_ak.add_argument("--ticker", required=True)
    p_ak.add_argument("--start", default=None)
    p_ak.add_argument("--end", default=None)
    p_ak.add_argument("--adjustment", choices=["none", "qfq", "hfq"], default="none")
    p_ak.set_defaults(func=_cmd_fetch_ak)

    p_seed = sub.add_parser("seed", help="Seed synthetic daily bars (offline)")
    p_seed.add_argument("--exchange", required=True)
    p_seed.add_argument("--ticker", required=True)
    p_seed.add_argument("--days", type=int, default=60)
    p_seed.set_defaults(func=_cmd_seed)

    p_q = sub.add_parser("query-bars", help="Query bars from the local lake")
    p_q.add_argument("--exchange", default=None)
    p_q.add_argument("--symbols", default=None)
    p_q.add_argument("--timeframe", default="1d")
    p_q.add_argument("--adjustment", default="none")
    p_q.add_argument("--start", default=None)
    p_q.add_argument("--end", default=None)
    p_q.add_argument("--limit", type=int, default=20)
    p_q.set_defaults(func=_cmd_query_bars)

    p_bt = sub.add_parser("backtest-sma", help="Run SMA crossover backtest")
    p_bt.add_argument("--symbol", required=True)
    p_bt.add_argument("--fast", type=int, default=10)
    p_bt.add_argument("--slow", type=int, default=30)
    p_bt.add_argument("--timeframe", default="1d")
    p_bt.add_argument("--adjustment", default="none")
    p_bt.add_argument("--start", default=None)
    p_bt.add_argument("--end", default=None)
    p_bt.add_argument("--initial-cash", type=float, default=100_000.0)
    p_bt.add_argument("--fee-bps", type=float, default=1.0)
    p_bt.add_argument("--slippage-bps", type=float, default=2.0)
    p_bt.set_defaults(func=_cmd_backtest_sma)

    p_bh = sub.add_parser("backtest-bh", help="Run buy & hold backtest")
    p_bh.add_argument("--symbol", required=True)
    p_bh.add_argument("--timeframe", default="1d")
    p_bh.add_argument("--adjustment", default="none")
    p_bh.add_argument("--start", default=None)
    p_bh.add_argument("--end", default=None)
    p_bh.add_argument("--initial-cash", type=float, default=100_000.0)
    p_bh.add_argument("--fee-bps", type=float, default=1.0)
    p_bh.add_argument("--slippage-bps", type=float, default=2.0)
    p_bh.set_defaults(func=_cmd_backtest_bh)

    # New unified backtest command
    p_bt2 = sub.add_parser("backtest", help="Run backtest with unified Strategy interface (A-share rules)")
    p_bt2.add_argument("--symbols", required=True, help="Comma-separated symbol ids, e.g. SSE:600000,SZSE:000001")
    p_bt2.add_argument("--strategy", default="ma", help="Strategy: ma, bh, rsi (default: ma)")
    p_bt2.add_argument("--fast", type=int, default=5, help="Fast MA period (for ma strategy)")
    p_bt2.add_argument("--slow", type=int, default=20, help="Slow MA period (for ma strategy)")
    p_bt2.add_argument("--start", default=None, help="Start date YYYY-MM-DD")
    p_bt2.add_argument("--end", default=None, help="End date YYYY-MM-DD")
    p_bt2.add_argument("--initial-cash", type=float, default=1_000_000.0)
    p_bt2.set_defaults(func=_cmd_backtest)

    p_paper = sub.add_parser("paper-run-sma", help="Paper trade SMA crossover")
    p_paper.add_argument("--symbol", required=True)
    p_paper.add_argument("--fast", type=int, default=10)
    p_paper.add_argument("--slow", type=int, default=30)
    p_paper.add_argument("--timeframe", default="1d")
    p_paper.add_argument("--adjustment", default="none")
    p_paper.add_argument("--start", default=None)
    p_paper.add_argument("--end", default=None)
    p_paper.add_argument("--initial-cash", type=float, default=100_000.0)
    p_paper.add_argument("--fee-bps", type=float, default=1.0)
    p_paper.add_argument("--slippage-bps", type=float, default=2.0)
    p_paper.add_argument("--max-gross", type=float, default=1.0)
    p_paper.add_argument("--max-pos", type=float, default=1.0)
    p_paper.add_argument("--cooldown", type=int, default=0)
    p_paper.add_argument("--stop-loss", type=float, default=None)
    p_paper.add_argument("--max-daily-loss", type=float, default=None)
    p_paper.add_argument("--circuit-breaker", type=float, default=None)
    p_paper.set_defaults(func=_cmd_paper_run_sma)

    ns = parser.parse_args(argv)
    func = getattr(ns, "func", None)
    if not callable(func):
        return 2
    try:
        return int(func(ns))
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1
