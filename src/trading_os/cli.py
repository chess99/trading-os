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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="trading_os", description="Trading OS CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_paths = sub.add_parser("paths", help="Print key repo paths")
    p_paths.set_defaults(func=_cmd_paths)

    p_lake = sub.add_parser("lake-init", help="Initialize local DuckDB/Parquet data lake")
    p_lake.set_defaults(func=_cmd_lake_init)

    p_yf = sub.add_parser("fetch-yf", help="Fetch daily bars from yfinance into the lake")
    p_yf.add_argument("--exchange", required=True, help="Exchange code, e.g. NASDAQ/NYSE")
    p_yf.add_argument("--ticker", required=True, help="Yahoo ticker, e.g. AAPL")
    p_yf.add_argument("--start", default=None, help="Start date (YYYY-MM-DD)")
    p_yf.add_argument("--end", default=None, help="End date (YYYY-MM-DD)")
    p_yf.set_defaults(func=_cmd_fetch_yf)

    p_seed = sub.add_parser("seed", help="Seed synthetic daily bars into the lake (offline)")
    p_seed.add_argument("--exchange", required=True, help="Exchange code, e.g. NASDAQ")
    p_seed.add_argument("--ticker", required=True, help="Ticker, e.g. TEST")
    p_seed.add_argument("--days", type=int, default=60, help="Number of days to generate")
    p_seed.set_defaults(func=_cmd_seed)

    p_q = sub.add_parser("query-bars", help="Query bars from the local lake")
    p_q.add_argument("--exchange", default=None, help="Exchange code filter (optional)")
    p_q.add_argument("--symbols", default=None, help="Comma-separated symbol ids (EXCHANGE:TICKER)")
    p_q.add_argument("--timeframe", default="1d", help="Timeframe (default: 1d)")
    p_q.add_argument("--adjustment", default="none", help="Adjustment (default: none)")
    p_q.add_argument("--start", default=None, help="Start (ISO date/timestamp)")
    p_q.add_argument("--end", default=None, help="End (ISO date/timestamp)")
    p_q.add_argument("--limit", type=int, default=20, help="Max rows to print")
    p_q.set_defaults(func=_cmd_query_bars)

    p_bt = sub.add_parser("backtest-sma", help="Run SMA crossover backtest for a symbol")
    p_bt.add_argument("--symbol", required=True, help="Symbol id (EXCHANGE:TICKER)")
    p_bt.add_argument("--fast", type=int, default=10, help="Fast SMA window")
    p_bt.add_argument("--slow", type=int, default=30, help="Slow SMA window")
    p_bt.add_argument("--timeframe", default="1d", help="Timeframe (default: 1d)")
    p_bt.add_argument("--adjustment", default="none", help="Adjustment (default: none)")
    p_bt.add_argument("--start", default=None, help="Start (ISO date/timestamp)")
    p_bt.add_argument("--end", default=None, help="End (ISO date/timestamp)")
    p_bt.add_argument("--initial-cash", type=float, default=100_000.0)
    p_bt.add_argument("--fee-bps", type=float, default=1.0)
    p_bt.add_argument("--slippage-bps", type=float, default=2.0)
    p_bt.set_defaults(func=_cmd_backtest_sma)

    p_bh = sub.add_parser("backtest-bh", help="Run buy & hold backtest for a symbol")
    p_bh.add_argument("--symbol", required=True, help="Symbol id (EXCHANGE:TICKER)")
    p_bh.add_argument("--timeframe", default="1d", help="Timeframe (default: 1d)")
    p_bh.add_argument("--adjustment", default="none", help="Adjustment (default: none)")
    p_bh.add_argument("--start", default=None, help="Start (ISO date/timestamp)")
    p_bh.add_argument("--end", default=None, help="End (ISO date/timestamp)")
    p_bh.add_argument("--initial-cash", type=float, default=100_000.0)
    p_bh.add_argument("--fee-bps", type=float, default=1.0)
    p_bh.add_argument("--slippage-bps", type=float, default=2.0)
    p_bh.set_defaults(func=_cmd_backtest_bh)

    p_paper = sub.add_parser("paper-run-sma", help="Paper trade SMA crossover and write event log")
    p_paper.add_argument("--symbol", required=True, help="Symbol id (EXCHANGE:TICKER)")
    p_paper.add_argument("--fast", type=int, default=10, help="Fast SMA window")
    p_paper.add_argument("--slow", type=int, default=30, help="Slow SMA window")
    p_paper.add_argument("--timeframe", default="1d", help="Timeframe (default: 1d)")
    p_paper.add_argument("--adjustment", default="none", help="Adjustment (default: none)")
    p_paper.add_argument("--start", default=None, help="Start (ISO date/timestamp)")
    p_paper.add_argument("--end", default=None, help="End (ISO date/timestamp)")
    p_paper.add_argument("--initial-cash", type=float, default=100_000.0)
    p_paper.add_argument("--fee-bps", type=float, default=1.0)
    p_paper.add_argument("--slippage-bps", type=float, default=2.0)
    p_paper.add_argument("--max-gross", type=float, default=1.0, help="Max gross exposure pct")
    p_paper.add_argument("--max-pos", type=float, default=1.0, help="Max single position pct")
    p_paper.add_argument("--cooldown", type=int, default=0, help="Cooldown bars after a trade")
    p_paper.add_argument("--stop-loss", type=float, default=None, help="Stop loss pct (e.g. 0.1)")
    p_paper.add_argument("--max-daily-loss", type=float, default=None, help="Max daily loss pct (e.g. 0.03)")
    p_paper.add_argument("--circuit-breaker", type=float, default=None, help="Peak-to-valley drawdown halt pct (e.g. 0.1)")
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
    from pathlib import Path

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

    log_path = Path(root / "artifacts" / "paper" / f"events_{ns.symbol.replace(':', '_')}.jsonl")
    elog = EventLog(log_path)

    # record the "decision" (strategy run configuration) up-front for traceability
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
                    "max_daily_loss": float(ns.max_daily_loss) if ns.max_daily_loss is not None else None,
                    "circuit_breaker": float(ns.circuit_breaker) if ns.circuit_breaker is not None else None,
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
            circuit_breaker_drawdown_pct=float(ns.circuit_breaker)
            if ns.circuit_breaker is not None
            else None,
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

