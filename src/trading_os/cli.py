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
    """从akshare获取A股数据"""
    from .data.lake import LocalDataLake
    from .data.schema import Adjustment, Exchange, Timeframe
    from .data.sources.akshare_source import fetch_daily_bars

    root = repo_root()
    lake = LocalDataLake(root / "data")

    exch = Exchange(ns.exchange)
    tf = Timeframe.D1

    # 处理复权类型
    if ns.adjustment == "qfq":
        adj = Adjustment.QFQ
    elif ns.adjustment == "hfq":
        adj = Adjustment.HFQ
    else:
        adj = Adjustment.NONE

    try:
        print(f"📊 获取A股数据: {exch.value}:{ns.ticker} (复权: {adj.value})")

        df = fetch_daily_bars(
            ns.ticker,
            exchange=exch,
            start=ns.start,
            end=ns.end,
            adjustment=adj
        )

        if df.empty:
            print("❌ 未获取到数据")
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

        print(f"✅ 成功写入 {len(df)} 条记录: {exch.value}:{ns.ticker}")
        print(f"📈 数据范围: {df['ts'].min().date()} 至 {df['ts'].max().date()}")

        return 0

    except Exception as e:
        print(f"❌ 获取A股数据失败: {e}")
        return 1


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

    p_ak = sub.add_parser("fetch-ak", help="从akshare获取A股数据")
    p_ak.add_argument("--exchange", required=True, choices=["SSE", "SZSE"], help="交易所 (SSE/SZSE)")
    p_ak.add_argument("--ticker", required=True, help="股票代码 (6位数字)")
    p_ak.add_argument("--start", default=None, help="开始日期 YYYY-MM-DD")
    p_ak.add_argument("--end", default=None, help="结束日期 YYYY-MM-DD")
    p_ak.add_argument("--adjustment", choices=["none", "qfq", "hfq"], default="none", help="复权类型")
    p_ak.set_defaults(func=_cmd_fetch_ak)

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

    p_dr = sub.add_parser(
        "draft-review", help="Generate a review draft from a paper-trading JSONL event log"
    )
    p_dr.add_argument("--events", required=True, help="Path to events_*.jsonl (absolute or repo-relative)")
    p_dr.add_argument("--decision", default=None, help="Decision markdown path to include (optional)")
    p_dr.add_argument(
        "--out",
        default=None,
        help="Output markdown path (default: journal/reviews/<date>_<symbol>_auto.md)",
    )
    p_dr.add_argument("--overwrite", action="store_true", help="Overwrite output file if exists")
    p_dr.set_defaults(func=_cmd_draft_review)

    # Agent system commands
    p_agent = sub.add_parser("agent", help="基金经理AI系统")
    agent_sub = p_agent.add_subparsers(dest="agent_action", required=True)

    p_daily = agent_sub.add_parser("daily", help="运行日常分析")
    p_daily.set_defaults(func=_cmd_agent)

    p_board = agent_sub.add_parser("board-report", help="生成董事会报告")
    p_board.set_defaults(func=_cmd_agent)

    p_recommend = agent_sub.add_parser("recommend", help="获取投资建议")
    p_recommend.set_defaults(func=_cmd_agent)

    p_risk = agent_sub.add_parser("risk", help="评估投资组合风险")
    p_risk.set_defaults(func=_cmd_agent)

    p_status = agent_sub.add_parser("status", help="检查数据湖状态")
    p_status.set_defaults(func=_cmd_agent)

    p_screen = agent_sub.add_parser("screen", help="股票筛选和投资组合分析")
    p_screen.add_argument("--style", choices=["value", "growth", "garp"], default="garp", help="投资风格")
    p_screen.add_argument("--risk", choices=["conservative", "moderate", "aggressive"], default="moderate", help="风险等级")
    p_screen.set_defaults(func=_cmd_agent)

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


def _cmd_draft_review(ns: argparse.Namespace) -> int:
    from pathlib import Path

    from .journal.review_draft import write_review_draft

    root = repo_root()
    events_path = Path(ns.events).expanduser()
    if not events_path.is_absolute():
        events_path = root / events_path

    if ns.out:
        out_path = Path(ns.out).expanduser()
        if not out_path.is_absolute():
            out_path = root / out_path
    else:
        today = datetime.now(timezone.utc).date().isoformat()
        # derive symbol from filename when possible, e.g. events_NASDAQ_TEST.jsonl
        stem = events_path.stem
        safe_symbol = stem.removeprefix("events_") if stem.startswith("events_") else stem
        out_path = root / "journal" / "reviews" / f"{today}_{safe_symbol}_auto.md"

    out = write_review_draft(
        events_path=events_path,
        out_path=out_path,
        decision_path=ns.decision,
        overwrite=bool(ns.overwrite),
    )
    print(f"wrote_review: {out}")
    return 0


def _cmd_agent(ns: argparse.Namespace) -> int:
    """Agent系统命令处理"""
    from .agents.cli_integration import AgentSystemCLI

    root = repo_root()
    agent_cli = AgentSystemCLI(root)

    if ns.agent_action == 'daily':
        result = agent_cli.run_daily_analysis()
        agent_cli.print_analysis_summary(result)
    elif ns.agent_action == 'board-report':
        report = agent_cli.generate_board_report()
        print("\n📊 董事会报告:")
        print(f"报告日期: {report['report_date']}")
        print(f"投资组合: {report['portfolio_summary']}")
        print(f"市场观点: {report['market_assessment']}")
        print(f"风险状况: {report['risk_analysis']}")
        print(f"展望: {report['outlook']}")
    elif ns.agent_action == 'recommend':
        recommendations = agent_cli.get_investment_recommendations()
        print(f"\n💡 投资建议 ({len(recommendations['recommendations'])} 条):")
        for i, rec in enumerate(recommendations['recommendations'], 1):
            print(f"{i}. {rec.symbol}: {rec.action} (目标: {rec.target_allocation:.1%})")
            print(f"   推理: {rec.reasoning}")
            print(f"   信心: {rec.confidence:.1%}, 风险: {rec.risk_level}")
    elif ns.agent_action == 'risk':
        risk_result = agent_cli.assess_portfolio_risk()
        if risk_result['risk_assessment']:
            risk = risk_result['risk_assessment']
            print(f"\n⚠️  风险评估结果:")
            print(f"整体风险: {risk.get('overall_risk_level', '未知')}")
            print(f"风险指标: {risk.get('risk_metrics', {})}")
            alerts = risk.get('risk_alerts', [])
            if alerts:
                print(f"风险警报 ({len(alerts)} 个):")
                for alert in alerts:
                    print(f"  - {alert.description} (严重性: {alert.severity})")
    elif ns.agent_action == 'status':
        from .agents.data_validation import DataIntegrityChecker
        checker = DataIntegrityChecker(root)
        report = checker.generate_data_status_report()
        print(report)
    elif ns.agent_action == 'screen':
        from .research.stock_screener import StockScreener, ScreeningCriteria, InvestmentStyle
        from .research.portfolio_manager import PortfolioManager, RiskLevel

        # 解析参数
        style_map = {
            "value": InvestmentStyle.VALUE,
            "growth": InvestmentStyle.GROWTH,
            "garp": InvestmentStyle.GARP
        }
        risk_map = {
            "conservative": RiskLevel.CONSERVATIVE,
            "moderate": RiskLevel.MODERATE,
            "aggressive": RiskLevel.AGGRESSIVE
        }

        investment_style = style_map.get(ns.style, InvestmentStyle.GARP)
        risk_level = risk_map.get(ns.risk, RiskLevel.MODERATE)

        print(f"🔍 股票筛选分析")
        print(f"投资风格: {investment_style.value}")
        print(f"风险等级: {risk_level.value}")
        print("-" * 50)

        # 初始化筛选器
        screener = StockScreener()
        screener.load_stock_universe()

        # 根据风险等级创建筛选条件
        portfolio_manager = PortfolioManager()
        criteria = portfolio_manager._get_screening_criteria_by_risk(risk_level)
        criteria.investment_style = investment_style

        # 执行筛选
        selected_stocks = screener.screen_stocks(criteria)

        # 显示结果
        print(f"\n📊 筛选结果: {len(selected_stocks)} 只股票")
        print("\n前10只推荐股票:")
        for i, stock in enumerate(selected_stocks[:10], 1):
            print(f"{i:2d}. {stock.symbol} {stock.name}")
            print(f"     行业: {stock.industry.value}, PE: {stock.pe_ratio:.1f}, ROE: {stock.roe:.1%}")

        # 显示行业分布
        report = screener.get_screening_report()
        if report.get("industry_distribution"):
            print(f"\n🏭 行业分布:")
            for industry, count in report["industry_distribution"].items():
                print(f"  {industry}: {count} 只")

    else:
        print("请指定有效的agent操作: daily, board-report, recommend, risk, status, screen")

    return 0

