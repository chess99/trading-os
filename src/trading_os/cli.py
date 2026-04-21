"""Trading OS CLI.

Commands:
    lake-init           Initialize DuckDB/Parquet data lake
    lake-compact        合并去重 Parquet 文件（自动在文件数>20时触发，也可手动执行）
    fetch-bars          获取A股日线数据（自动选择最佳数据源）
    fetch-yf            Fetch bars from yfinance (US/HK stocks)
    seed                Seed synthetic bars (offline testing)
    query-bars          Query bars from the local lake
    backtest            Run backtest with A-share rules (ma/bh/rsi/agent)
    paper               Paper trading (ma/bh/rsi/agent)
    agent               One-shot Claude agent analysis
    paths               Print key repo paths
    fetch-ak-bulk       批量并发拉取全 A 股历史数据
    scan-elder          批量扫描全 A 股技术信号（Elder 体系）
    fundamental-store   持久化 BaoStock 基本面数据到本地
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


def _cmd_lake_compact(_: argparse.Namespace) -> int:
    """手动触发 Parquet compact（强制，不检查 threshold）。"""
    from .data.lake import LocalDataLake
    root = repo_root()
    lake = LocalDataLake(root / "data")
    n = lake.compact(threshold=0)  # threshold=0 强制触发
    if n == 0:
        print("没有数据需要 compact")
    else:
        print(f"Compact 完成，当前 {n} 个 Parquet 文件")
    return 0


def _cmd_fetch_bars(ns: argparse.Namespace) -> int:
    from .data.lake import LocalDataLake
    from .data.schema import Adjustment, Exchange, Timeframe
    from .data.sources.akshare_source import fetch_daily_bars

    root = repo_root()
    lake = LocalDataLake(root / "data")
    exch = Exchange(ns.exchange)
    adj = {"qfq": Adjustment.QFQ, "hfq": Adjustment.HFQ}.get(ns.adjustment, Adjustment.NONE)

    try:
        print(f"获取A股数据: {exch.value}:{ns.ticker} (复权: {adj.value})")
        df, actual_source = fetch_daily_bars(ns.ticker, exchange=exch, start=ns.start, end=ns.end, adjustment=adj)
        if df.empty:
            print("未获取到数据")
            return 1
        lake.write_bars_parquet(
            df, exchange=exch, timeframe=Timeframe.D1, adjustment=adj,
            source=actual_source, partition_hint=datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
        )
        lake.init()
        source_note = f" (via {actual_source})" if actual_source != "akshare" else ""
        print(f"写入 {len(df)} 条: {exch.value}:{ns.ticker}{source_note}")
        print(f"数据范围: {df['ts'].min().date()} 至 {df['ts'].max().date()}")
        return 0
    except Exception as e:
        print(f"获取A股数据失败: {e}", file=sys.stderr)
        return 1


def _resolve_bulk_pairs(ns) -> list | None:
    """解析 --tickers 参数或从 BaoStock 获取全 A 股列表。返回 (Exchange, ticker) 列表，失败返回 None。"""
    from .data.schema import Exchange
    if ns.tickers:
        pairs = []
        for sym in ns.tickers.split(","):
            sym = sym.strip()
            if ":" in sym:
                exch_str, ticker = sym.split(":", 1)
                pairs.append((Exchange(exch_str.upper()), ticker))
            else:
                print(f"跳过格式不正确的代码: {sym}（需要 SSE:600000 格式）", file=sys.stderr)
        return pairs
    else:
        try:
            import baostock as bs
            lg = bs.login()
            if lg.error_code != "0":
                print(f"BaoStock 登录失败: {lg.error_msg}", file=sys.stderr)
                return None
            # fields: code, code_name, ipoDate, outDate, type, status
            rs = bs.query_stock_basic(code="", code_name="")
            pairs = []
            while rs.next():
                row = rs.get_row_data()
                code = row[0]          # sh.600000 / sz.000001
                stock_type = row[4]    # 1=股票, 2=指数, 3=其他
                status = row[5]        # 1=上市, 0=退市
                if stock_type != "1" or status != "1":
                    continue
                prefix, ticker = code.split(".")
                exch = Exchange.SSE if prefix == "sh" else Exchange.SZSE
                pairs.append((exch, ticker))
            bs.logout()
            return pairs
        except Exception as exc:
            print(f"获取股票列表失败: {exc}", file=sys.stderr)
            return None


def _cmd_fetch_ak_bulk(ns: argparse.Namespace) -> int:
    """批量拉取全 A 股历史数据。

    使用 BaoStock 作为数据源（全球可达，无需代理），串行处理。
    每 BATCH_SIZE 只写入一个 Parquet 文件，最后统一刷新 DuckDB view。

    设计原则：
    - BaoStock 天然串行（login/logout per session），并发无收益
    - 批量写入避免 Parquet 文件碎片化（5000 个小文件 vs 25 个批次文件）
    - lake.init() 只在最后调用一次，不在循环内调用
    - 预计耗时：~33 分钟（2.5 req/s × 5000 只）
    """
    import pandas as pd
    from .data.lake import LocalDataLake
    from .data.schema import Adjustment, Exchange, Timeframe
    from .data.sources.baostock_source import query_bars_with_session

    root = repo_root()
    adj = {"qfq": Adjustment.QFQ, "hfq": Adjustment.HFQ}.get(ns.adjustment, Adjustment.NONE)
    BATCH_SIZE = 200  # 每批写入一个 Parquet 文件

    pairs = _resolve_bulk_pairs(ns)
    if pairs is None:
        return 1
    if not pairs:
        print("没有需要拉取的股票")
        return 0

    # --skip-existing：跳过本地已有数据的股票
    if ns.skip_existing:
        lake_check = LocalDataLake(root / "data")
        lake_check.init()
        from .data.pipeline import DataPipeline
        existing = set(DataPipeline(lake_check).available_symbols())
        before = len(pairs)
        pairs = [(e, t) for e, t in pairs if f"{e.value}:{t}" not in existing]
        print(f"--skip-existing: 跳过 {before - len(pairs)} 只已有数据，剩余 {len(pairs)} 只")

    if not pairs:
        print("没有需要拉取的股票")
        return 0

    start = ns.start or "2022-01-01"
    end = ns.end or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"开始批量拉取 {len(pairs)} 只（BaoStock，串行）")
    print(f"  日期范围: {start} ~ {end}，预计耗时 ~{len(pairs) // 150 + 1} 分钟")

    try:
        import baostock as bs
    except ImportError:
        print("baostock 未安装，请运行: pip install baostock", file=sys.stderr)
        return 1

    def _bs_login() -> bool:
        lg = bs.login()
        if lg.error_code != "0":
            print(f"BaoStock 登录失败: {lg.error_msg}", file=sys.stderr)
            return False
        return True

    if not _bs_login():
        return 1

    lake = LocalDataLake(root / "data")
    success = 0
    failed_list: list[str] = []
    batch: list[pd.DataFrame] = []
    batch_num = 0
    # 每 N 只重连一次，避免长连接断线
    RECONNECT_INTERVAL = 500

    def _flush_batch() -> None:
        nonlocal batch, batch_num
        if not batch:
            return
        combined = pd.concat(batch, ignore_index=True)
        batch_num += 1
        lake.write_bars_parquet(
            combined,
            exchange=Exchange.SSE,
            timeframe=Timeframe.D1,
            adjustment=adj,
            source="baostock",
            partition_hint=f"bulk_{batch_num:05d}",
        )
        batch = []

    import time
    QUERY_INTERVAL = 0.4  # 每次查询间隔 0.4 秒，避免触发 BaoStock 限速
    consecutive_failures = 0
    MAX_CONSECUTIVE_FAILURES = 5  # 连续失败超过 5 次强制重连

    try:
        for i, (exch, ticker) in enumerate(pairs, 1):
            # 定期重连，防止长连接超时断开
            if i > 1 and (i - 1) % RECONNECT_INTERVAL == 0:
                bs.logout()
                time.sleep(2)
                if not _bs_login():
                    print(f"重连失败，已处理 {i-1} 只，中止", file=sys.stderr)
                    break

            sym_id = f"{exch.value}:{ticker}"
            try:
                df = query_bars_with_session(bs, ticker, exchange=exch, start=start, end=end, adjustment=adj)
                if df.empty:
                    failed_list.append(f"{sym_id}: 空数据（停牌或未上市）")
                    consecutive_failures += 1
                else:
                    batch.append(df)
                    success += 1
                    consecutive_failures = 0
                time.sleep(QUERY_INTERVAL)  # 限速：2.5 req/s
            except Exception as exc:
                err = str(exc)[:80]
                failed_list.append(f"{sym_id}: {err}")
                consecutive_failures += 1
                # 连接/超时错误立即重连（含 BaoStock 中文错误信息）
                reconnect_keywords = (
                    "connection", "login", "socket", "timeout", "timed out", "reset",
                    "broken pipe", "网络", "接收错误", "连接失败", "10002",
                )
                need_reconnect = any(k in err.lower() for k in reconnect_keywords)
                if not need_reconnect and consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    need_reconnect = True
                    print(f"  连续失败 {consecutive_failures} 次，强制重连")
                if need_reconnect:
                    print(f"  连接异常，重连 BaoStock ({sym_id}): {err}")
                    try:
                        bs.logout()
                    except Exception:
                        pass
                    time.sleep(3)
                    _bs_login()
                    consecutive_failures = 0

            if len(batch) >= BATCH_SIZE:
                _flush_batch()

            if i % 100 == 0 or i == len(pairs):
                print(f"  {i}/{len(pairs)}  成功={success}  失败={len(failed_list)}")

        _flush_batch()

    finally:
        bs.logout()

    lake.init()  # 一次性刷新 DuckDB view

    print(f"\n完成: 成功={success}, 失败={len(failed_list)}")
    if failed_list and ns.verbose:
        print("失败列表（前 20 条）:")
        for item in failed_list[:20]:
            print(f"  {item}")
        if len(failed_list) > 20:
            print(f"  ... 还有 {len(failed_list) - 20} 条")
    return 0 if not failed_list else 1



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


def _cmd_valuation(ns: argparse.Namespace) -> int:
    """计算股票内在价值（EPV / DCF / PEG），参数由调用方显式传入。"""
    from .data.sources.valuation_source import calculate_valuation

    symbols = [s.strip() for s in ns.symbols.split(",")]
    for sym in symbols:
        result = calculate_valuation(
            sym,
            cost_of_capital=float(ns.cost_of_capital),
            moat=ns.moat,
            sustainable_profit_years=int(ns.epv_years),
            growth_rate=float(ns.growth_rate) if ns.growth_rate else None,
            growth_years=int(ns.growth_years),
            terminal_pe=float(ns.terminal_pe),
            discount_rate=float(ns.discount_rate) if ns.discount_rate else None,
            peg_target=float(ns.peg_target),
            growth_cagr=float(ns.growth_cagr) if ns.growth_cagr else None,
        )
        if result.get("error"):
            print(f"估值失败 {sym}: {result['error']}", file=__import__("sys").stderr)
            continue
        print(result["summary_text"])
        print()
    return 0


def _cmd_valuation_sensitivity(ns: argparse.Namespace) -> int:
    """计算估值敏感性矩阵，展示关键参数变化对估值的影响范围。"""
    from .data.sources.valuation_source import calculate_sensitivity

    growth_rates = [float(x) for x in ns.growth_rates.split(",")] if ns.growth_rates else None
    terminal_pes = [float(x) for x in ns.terminal_pes.split(",")] if ns.terminal_pes else None
    costs = [float(x) for x in ns.costs_of_capital.split(",")] if ns.costs_of_capital else None
    profits = [float(x) for x in ns.sustainable_profits.split(",")] if ns.sustainable_profits else None

    result = calculate_sensitivity(
        ns.symbol,
        method=ns.method,
        base_profit_bn=float(ns.base_profit),
        growth_rates=growth_rates,
        terminal_pes=terminal_pes,
        growth_years=int(ns.growth_years),
        discount_rate=float(ns.discount_rate),
        sustainable_profits_bn=profits,
        costs_of_capital=costs,
    )
    print(result["summary_text"])
    return 0


def _cmd_valuation_sotp(ns: argparse.Namespace) -> int:
    """分部估值（Sum-of-the-Parts）。各板块参数通过 JSON 文件传入。"""
    import json, sys
    from .data.sources.valuation_source import calculate_sotp

    try:
        with open(ns.segments_file) as f:
            segments = json.load(f)
    except Exception as e:
        print(f"读取分部参数失败: {e}", file=sys.stderr)
        print("segments_file 应为 JSON 数组，每项包含 name/profit_bn/method/multiple/note 等字段", file=sys.stderr)
        return 1

    result = calculate_sotp(ns.symbol, segments)
    print(result["summary_text"])
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
    elif name in ("elder", "elder_triple_screen"):
        from .strategy.elder import ElderStrategy
        return ElderStrategy()
    else:
        raise ValueError(f"Unknown strategy: {name!r}. Available: ma, bh, rsi, agent, elder")


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


# ---------------------------------------------------------------------------
# Scan commands
# ---------------------------------------------------------------------------

def _run_scan(
    ns: argparse.Namespace,
    *,
    scanner_fn,
    system_name: str,
    lookback_days: int = 504,
    scanner_kwargs: dict | None = None,
) -> int:
    """三个 scan 命令的公共实现。"""
    from datetime import timedelta
    import pandas as pd
    from .data.lake import LocalDataLake
    from .data.pipeline import DataPipeline
    from .data.sources.akshare_factors import AkshareFactorSource
    from .scan.common import get_scan_symbols, filter_by_turnover, load_bars_batch, write_scan_output, get_stock_names

    root = repo_root()
    scan_date = date_type.fromisoformat(ns.date) if ns.date else date_type.today() - timedelta(days=1)
    output_path = (
        root / ns.output if ns.output
        else root / "artifacts" / "scan" / f"{system_name}-{scan_date.isoformat().replace('-', '')}.json"
    )

    lake = LocalDataLake(root / "data")
    lake.init()
    pipeline = DataPipeline(lake)
    akshare = AkshareFactorSource()

    print(f"Scanning {system_name} signals for {scan_date}...")

    try:
        symbols, no_data = get_scan_symbols(pipeline, akshare, exchange=ns.exchange)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"  Local symbols: {len(symbols)} ({no_data} without local data)")

    # 批量加载数据（每批 500 只）
    batch_size = 500
    all_bars_parts = []
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i + batch_size]
        bars = load_bars_batch(pipeline, batch, scan_date=scan_date, lookback_days=lookback_days)
        if not bars.empty:
            all_bars_parts.append(bars)

    all_bars = pd.concat(all_bars_parts) if all_bars_parts else pd.DataFrame()

    # 成交额过滤
    if not all_bars.empty:
        symbols, low_turnover = filter_by_turnover(
            symbols, all_bars, min_amount=ns.min_turnover
        )
    else:
        low_turnover = len(symbols)
        symbols = []

    kwargs: dict = {"scan_date": scan_date, "top_n": ns.top}
    if scanner_kwargs:
        kwargs.update(scanner_kwargs)

    try:
        result = scanner_fn(symbols, all_bars, **kwargs)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    # 注入股票名称（有 miss 时强制刷新缓存，可能是新股上市）
    print("  获取股票名称...")
    name_cache = root / "data" / "stock_names.json"
    name_map = get_stock_names(cache_path=name_cache)
    missing = [c["symbol"] for c in result["candidates"] if c["symbol"] not in name_map]
    if missing:
        print(f"  发现 {len(missing)} 只未知股票，刷新名称缓存...")
        name_map = get_stock_names(cache_path=name_cache, max_age_days=0)
    for c in result["candidates"]:
        c["name"] = name_map.get(c["symbol"], "")

    output = {
        "scan_date": scan_date.isoformat(),
        "system": system_name,
        "total_scanned": len(symbols) + result["_stats"]["insufficient_data"] + result["_stats"]["no_signal"],
        "candidates": result["candidates"],
        "filtered_out": {
            "no_data": no_data,
            "low_turnover": low_turnover,
            "insufficient_data": result["_stats"]["insufficient_data"],
            "no_signal": result["_stats"]["no_signal"],
        },
    }

    write_scan_output(output, output_path)
    print(f"  Found {len(result['candidates'])} candidates → {output_path}")
    return 0


def _cmd_scan_elder(ns: argparse.Namespace) -> int:
    from .scan.elder_scanner import scan_elder
    return _run_scan(ns, scanner_fn=scan_elder, system_name="elder", lookback_days=504)


def _cmd_fundamental_store(ns: argparse.Namespace) -> int:
    import json
    from .data.sources.fundamental_source import get_financial_summary
    from .scan.common import fundamental_path

    root = repo_root()
    (root / "data" / "fundamental").mkdir(parents=True, exist_ok=True)

    if ns.symbols:
        symbols = [s.strip() for s in ns.symbols.split(",")]
    else:
        # 全 A 股：从 AKShare 获取列表
        try:
            from .data.sources.akshare_factors import AkshareFactorSource
            from .scan.common import to_canonical
            akshare = AkshareFactorSource()
            df = akshare.get_a_stock_list()
            symbols = [
                to_canonical(row["exchange"], row["symbol"])
                for _, row in df.iterrows()
            ]
        except Exception as exc:
            print(f"AKShare 不可用，请检查网络连接。错误：{exc}", file=sys.stderr)
            return 1

    success = 0
    failed = 0
    skipped = 0

    print(f"fundamental-store: processing {len(symbols)} symbols...")

    for i, sym in enumerate(symbols, 1):
        path = fundamental_path(root / "data", sym)

        if ns.skip_existing and path.exists():
            skipped += 1
            continue

        try:
            data = get_financial_summary(sym, years=ns.years)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            success += 1
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("Failed %s: %s", sym, exc)
            failed += 1

        if i % 100 == 0:
            print(f"  Progress: {i}/{len(symbols)} (success={success}, failed={failed}, skipped={skipped})")

    print(f"\nDone: success={success}, failed={failed}, skipped={skipped}")
    return 0


def _cmd_scan_canslim(ns: argparse.Namespace) -> int:
    from .scan.canslim_scanner import scan_canslim
    from pathlib import Path
    root = repo_root()
    return _run_scan(
        ns,
        scanner_fn=scan_canslim,
        system_name="canslim",
        lookback_days=504,
        scanner_kwargs={"data_root": root / "data"},
    )


def _cmd_scan_value(ns: argparse.Namespace) -> int:
    from .scan.value_scanner import scan_value
    root = repo_root()
    return _run_scan(
        ns,
        scanner_fn=scan_value,
        system_name="value",
        lookback_days=756,
        scanner_kwargs={"data_root": root / "data"},
    )


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

    p = sub.add_parser("lake-compact", help="合并去重 Parquet 文件（自动在文件数>20时触发，也可手动执行）")
    p.set_defaults(func=_cmd_lake_compact)

    p = sub.add_parser("fundamental", help="获取股票财务摘要（BaoStock，无需代理）")
    p.add_argument("--symbols", required=True, help="逗号分隔的股票代码，如 SSE:600519,SSE:600000")
    p.add_argument("--years", type=int, default=5, help="获取最近几年数据（默认5年）")
    p.set_defaults(func=_cmd_fundamental)

    p = sub.add_parser("valuation", help="计算股票内在价值（EPV/DCF/PEG），参数由AI根据分析结果传入")
    p.add_argument("--symbols", required=True, help="逗号分隔的股票代码，如 SSE:601138")
    p.add_argument("--cost-of-capital", default="0.09",
                   help="资本成本：宽护城河取0.07，窄护城河取0.09，无护城河取0.12")
    p.add_argument("--moat", choices=["wide", "narrow", "none"], default="narrow",
                   help="护城河宽度，影响安全边际要求")
    p.add_argument("--epv-years", type=int, default=3,
                   help="EPV 使用最近几年均值利润（默认3年）")
    p.add_argument("--growth-rate", default=None,
                   help="DCF 增速假设，如0.30（不传则跳过DCF）")
    p.add_argument("--growth-years", type=int, default=5,
                   help="高增速持续年数（默认5年）")
    p.add_argument("--terminal-pe", type=float, default=15.0,
                   help="终止PE，成熟代工企业约12-15x，消费品约18-20x")
    p.add_argument("--discount-rate", default=None,
                   help="DCF折现率（不传则用资本成本+3%）")
    p.add_argument("--peg-target", type=float, default=1.0,
                   help="目标PEG（默认1.0）")
    p.add_argument("--growth-cagr", default=None,
                   help="PEG使用的增速CAGR（不传则从财务数据自动推算）")
    p.set_defaults(func=_cmd_valuation)

    p = sub.add_parser("valuation-sensitivity", help="估值敏感性矩阵：展示关键参数变化对估值的影响")
    p.add_argument("--symbol", required=True, help="股票代码，如 SSE:601138")
    p.add_argument("--method", choices=["dcf", "epv"], default="dcf")
    p.add_argument("--base-profit", required=True, help="基准利润（亿元），如 353")
    p.add_argument("--growth-rates", default=None, help="DCF增速列表，逗号分隔，如 0.15,0.20,0.25,0.30,0.35")
    p.add_argument("--terminal-pes", default=None, help="DCF终止PE列表，如 10,12,15,18,20")
    p.add_argument("--growth-years", type=int, default=5)
    p.add_argument("--discount-rate", type=float, default=0.12)
    p.add_argument("--sustainable-profits", default=None, help="EPV可持续利润列表（亿），如 250,300,350,400")
    p.add_argument("--costs-of-capital", default=None, help="EPV资本成本列表，如 0.08,0.09,0.10,0.11,0.12")
    p.set_defaults(func=_cmd_valuation_sensitivity)

    p = sub.add_parser("valuation-sotp", help="分部估值（Sum-of-the-Parts），各板块参数通过 JSON 文件传入")
    p.add_argument("--symbol", required=True, help="股票代码，如 SSE:601138")
    p.add_argument("--segments-file", required=True, help="分部参数 JSON 文件路径")
    p.set_defaults(func=_cmd_valuation_sotp)

    p = sub.add_parser("52week", help="计算股票52周高低点统计（从本地K线）")
    p.add_argument("--symbols", required=True, help="逗号分隔的股票代码，如 SSE:601138")
    p.set_defaults(func=_cmd_52week)

    p = sub.add_parser("market-breadth", help="计算大盘换筹日数量，判断市场状态（从本地K线）")
    p.add_argument("--index", default="SSE:000001", help="指数代码（默认上证综指）")
    p.add_argument("--days", type=int, default=30, help="统计窗口（默认30个交易日）")
    p.set_defaults(func=_cmd_market_breadth)

    p = sub.add_parser("fetch-bars", help="获取A股日线数据（自动选择最佳数据源）")
    p.add_argument("--exchange", required=True, choices=["SSE", "SZSE"])
    p.add_argument("--ticker", required=True, help="股票代码，如 600000")
    p.add_argument("--start", default=None, help="开始日期 YYYY-MM-DD")
    p.add_argument("--end", default=None, help="结束日期 YYYY-MM-DD")
    p.add_argument("--adjustment", choices=["none", "qfq", "hfq"], default="qfq", help="复权方式")
    p.set_defaults(func=_cmd_fetch_bars)

    p = sub.add_parser("fetch-ak-bulk", help="批量拉取全A股历史数据（BaoStock，串行，全球可达）")
    p.add_argument("--tickers", default=None, help="逗号分隔的代码，如 SSE:600000,SZSE:000001（不传则全A股）")
    p.add_argument("--start", default="2022-01-01", help="开始日期 YYYY-MM-DD（默认2022-01-01）")
    p.add_argument("--end", default=None, help="结束日期 YYYY-MM-DD（默认今日）")
    p.add_argument("--adjustment", choices=["none", "qfq", "hfq"], default="qfq", help="复权方式")
    p.add_argument("--skip-existing", action="store_true", help="跳过本地已有数据的股票")
    p.add_argument("--verbose", action="store_true", help="显示失败列表详情")
    p.set_defaults(func=_cmd_fetch_ak_bulk)

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
    _STRATEGY_HELP = "Strategy: ma (MA crossover), bh (buy-and-hold), rsi (RSI), agent (Claude AI), elder (Elder Triple Screen)"

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

    # --- Scan ---
    p = sub.add_parser("scan-elder", help="批量扫描全 A 股技术信号（Elder 三重滤网体系）")
    p.add_argument("--date", default=None, help="扫描日期 YYYY-MM-DD（默认昨日）")
    p.add_argument("--top", type=int, default=30, help="输出前 N 只（默认30）")
    p.add_argument("--min-turnover", type=float, default=1e7, help="最低日均成交额 CNY（默认1000万）")
    p.add_argument("--exchange", default=None, choices=["SSE", "SZSE"], help="只扫描指定交易所")
    p.add_argument("--output", default=None, help="输出 JSON 路径（默认 artifacts/scan/elder-YYYYMMDD.json）")
    p.set_defaults(func=_cmd_scan_elder)

    p = sub.add_parser("fundamental-store", help="持久化 BaoStock 基本面数据到 data/fundamental/")
    p.add_argument("--symbols", default=None, help="逗号分隔的股票代码（不传则处理全 A 股）")
    p.add_argument("--years", type=int, default=5, help="获取最近几年数据（默认5年）")
    p.add_argument("--skip-existing", action="store_true", help="跳过已有数据的股票（增量更新）")
    p.set_defaults(func=_cmd_fundamental_store)

    p = sub.add_parser("scan-canslim", help="批量扫描全 A 股基本面信号（CANSLIM 成长股体系）")
    p.add_argument("--date", default=None, help="扫描日期 YYYY-MM-DD（默认昨日）")
    p.add_argument("--top", type=int, default=30, help="输出前 N 只（默认30）")
    p.add_argument("--min-turnover", type=float, default=1e7, help="最低日均成交额 CNY（默认1000万）")
    p.add_argument("--exchange", default=None, choices=["SSE", "SZSE"], help="只扫描指定交易所")
    p.add_argument("--output", default=None, help="输出 JSON 路径")
    p.set_defaults(func=_cmd_scan_canslim)

    p = sub.add_parser("scan-value", help="批量扫描全 A 股估值信号（Value Investing 体系）")
    p.add_argument("--date", default=None, help="扫描日期 YYYY-MM-DD（默认昨日）")
    p.add_argument("--top", type=int, default=30, help="输出前 N 只（默认30）")
    p.add_argument("--min-turnover", type=float, default=1e7, help="最低日均成交额 CNY（默认1000万）")
    p.add_argument("--exchange", default=None, choices=["SSE", "SZSE"], help="只扫描指定交易所")
    p.add_argument("--output", default=None, help="输出 JSON 路径")
    p.set_defaults(func=_cmd_scan_value)

    ns = parser.parse_args(argv)
    func = getattr(ns, "func", None)
    if not callable(func):
        return 2
    try:
        return int(func(ns))
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1
