from __future__ import annotations

import argparse

from .commands.analysis import (
    _cmd_52week,
    _cmd_fundamental,
    _cmd_market_breadth,
    _cmd_valuation,
    _cmd_valuation_sensitivity,
    _cmd_valuation_sotp,
)
from .commands.data import (
    _cmd_fetch_ak_bulk,
    _cmd_fetch_bars,
    _cmd_fetch_yf,
    _cmd_lake_compact,
    _cmd_lake_fix_index,
    _cmd_lake_init,
    _cmd_paths,
    _cmd_query_bars,
    _cmd_seed,
)
from .commands.pool import _cmd_pool
from .commands.scan import (
    _cmd_fundamental_store,
    _cmd_scan_canslim,
    _cmd_scan_elder,
    _cmd_scan_value,
)
from .commands.strategy import _cmd_agent, _cmd_backtest, _cmd_paper

STRATEGY_HELP = (
    "Strategy: ma (MA crossover), bh (buy-and-hold), rsi (RSI), "
    "agent (Claude AI), elder (Elder Triple Screen)"
)
EXCHANGE_CHOICES = ["SSE", "SZSE"]
POOL_SYSTEM_CHOICES = ["canslim", "elder", "value"]
POOL_TIER_CHOICES = ["candidates", "watchlist", "ready"]


def _add_scan_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--date", default=None, help="扫描日期 YYYY-MM-DD（默认昨日）")
    parser.add_argument("--top", type=int, default=30, help="输出前 N 只（默认30）")
    parser.add_argument("--min-turnover", type=float, default=1e7, help="最低日均成交额 CNY（默认1000万）")
    parser.add_argument("--exchange", default=None, choices=EXCHANGE_CHOICES, help="只扫描指定交易所")
    parser.add_argument("--output", default=None, help="输出 JSON 路径")


def _add_strategy_common_args(
    parser: argparse.ArgumentParser,
    *,
    symbols_help: str = "Comma-separated symbol ids",
    fast_help: str | None = None,
    slow_help: str | None = None,
    start_help: str | None = None,
    end_help: str | None = None,
) -> None:
    parser.add_argument("--symbols", required=True, help=symbols_help)
    parser.add_argument("--strategy", default="ma", help=STRATEGY_HELP)
    parser.add_argument("--fast", type=int, default=5, help=fast_help)
    parser.add_argument("--slow", type=int, default=20, help=slow_help)
    parser.add_argument("--start", default=None, help=start_help)
    parser.add_argument("--end", default=None, help=end_help)
    parser.add_argument("--initial-cash", type=float, default=1_000_000.0)


def register_data_commands(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("paths", help="Print key repo paths")
    p.set_defaults(func=_cmd_paths)

    p = sub.add_parser("lake-init", help="Initialize DuckDB/Parquet data lake")
    p.set_defaults(func=_cmd_lake_init)

    p = sub.add_parser("lake-compact", help="合并去重 Parquet 文件（自动在文件数>20时触发，也可手动执行）")
    p.set_defaults(func=_cmd_lake_compact)

    p = sub.add_parser("lake-fix-index", help="清洗被股票 API 污染的指数数据并重新拉取正确数据（幂等）")
    p.add_argument("--symbol", required=True, help="要修复的指数 symbol，如 SSE:000001")
    p.set_defaults(func=_cmd_lake_fix_index)

    p = sub.add_parser("fundamental", help="获取股票财务摘要（BaoStock，无需代理）")
    p.add_argument("--symbols", required=True, help="逗号分隔的股票代码，如 SSE:600519,SSE:600000")
    p.add_argument("--years", type=int, default=5, help="获取最近几年数据（默认5年）")
    p.set_defaults(func=_cmd_fundamental)

    p = sub.add_parser("valuation", help="计算股票内在价值（EPV/DCF/PEG），参数由AI根据分析结果传入")
    p.add_argument("--symbols", required=True, help="逗号分隔的股票代码，如 SSE:601138")
    p.add_argument("--cost-of-capital", default="0.09", help="资本成本：宽护城河取0.07，窄护城河取0.09，无护城河取0.12")
    p.add_argument("--moat", choices=["wide", "narrow", "none"], default="narrow", help="护城河宽度，影响安全边际要求")
    p.add_argument("--epv-years", type=int, default=3, help="EPV 使用最近几年均值利润（默认3年）")
    p.add_argument("--growth-rate", default=None, help="DCF 增速假设，如0.30（不传则跳过DCF）")
    p.add_argument("--growth-years", type=int, default=5, help="高增速持续年数（默认5年）")
    p.add_argument("--terminal-pe", type=float, default=15.0, help="终止PE，成熟代工企业约12-15x，消费品约18-20x")
    p.add_argument("--discount-rate", default=None, help="DCF折现率（不传则用资本成本+3%）")
    p.add_argument("--peg-target", type=float, default=1.0, help="目标PEG（默认1.0）")
    p.add_argument("--growth-cagr", default=None, help="PEG使用的增速CAGR（不传则从财务数据自动推算）")
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
    p.add_argument("--exchange", required=True, choices=EXCHANGE_CHOICES)
    p.add_argument("--ticker", required=True, help="股票代码，如 600000")
    p.add_argument("--start", default=None, help="开始日期 YYYY-MM-DD")
    p.add_argument("--end", default=None, help="结束日期 YYYY-MM-DD")
    p.add_argument("--adjustment", choices=["none", "qfq", "hfq"], default="qfq", help="复权方式")
    p.add_argument("--asset-type", choices=["equity", "index", "etf"], default="equity", dest="asset_type", help="资产类型 (默认: equity)。指数请用 index，如: --asset-type index")
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


def register_strategy_commands(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("backtest", help="Run backtest with A-share rules")
    _add_strategy_common_args(
        p,
        symbols_help="Comma-separated symbol ids, e.g. SSE:600000",
        fast_help="Fast MA period",
        slow_help="Slow MA period",
        start_help="Start date YYYY-MM-DD",
        end_help="End date YYYY-MM-DD",
    )
    p.set_defaults(func=_cmd_backtest)

    p = sub.add_parser("paper", help="Paper trading with A-share rules")
    _add_strategy_common_args(p)
    p.add_argument("--bypass-confirm", action="store_true", help="Auto-execute without confirmation")
    p.set_defaults(func=_cmd_paper)

    p = sub.add_parser("agent", help="One-shot Claude agent analysis")
    p.add_argument("--symbols", required=True, help="Comma-separated symbol ids")
    p.add_argument("--date", default=None, help="Analysis date YYYY-MM-DD (default: today)")
    p.add_argument("--bypass-confirm", action="store_true")
    p.set_defaults(func=_cmd_agent)


def register_scan_commands(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("scan-elder", help="批量扫描全 A 股技术信号（Elder 三重滤网体系）")
    _add_scan_common_args(p)
    p._actions[-1].help = "输出 JSON 路径（默认 artifacts/scan/elder-YYYYMMDD.json）"  # type: ignore[attr-defined]
    p.set_defaults(func=_cmd_scan_elder)

    p = sub.add_parser("fundamental-store", help="持久化 BaoStock 基本面数据到 data/fundamental/")
    p.add_argument("--symbols", default=None, help="逗号分隔的股票代码（不传则处理全 A 股）")
    p.add_argument("--years", type=int, default=5, help="获取最近几年数据（默认5年）")
    p.add_argument("--skip-existing", action="store_true", help="跳过已有数据的股票（增量更新）")
    p.set_defaults(func=_cmd_fundamental_store)

    p = sub.add_parser("scan-canslim", help="批量扫描全 A 股基本面信号（CANSLIM 成长股体系）")
    _add_scan_common_args(p)
    p.add_argument("--live", action="store_true", help="实时模式：直接调用 EastMoney F10 API，无需 fundamental-store 预缓存")
    p.add_argument("--workers", type=int, default=3, help="--live 模式并发线程数（默认3，避免触发限速）")
    p.set_defaults(func=_cmd_scan_canslim)

    p = sub.add_parser("scan-value", help="批量扫描全 A 股估值信号（Value Investing 体系）")
    _add_scan_common_args(p)
    p.add_argument("--mode", default="live", choices=["live", "historical"], help="live=实时估值快照；historical=读取 data/valuation_snapshots/YYYY-MM-DD.json")
    p.set_defaults(func=_cmd_scan_value)


def register_pool_commands(sub: argparse._SubParsersAction) -> None:
    pool_p = sub.add_parser("pool", help="自选池管理（查看/添加/移出/升层/更新）")
    pool_sub = pool_p.add_subparsers(dest="pool_cmd", required=True)
    pool_p.set_defaults(func=_cmd_pool)

    p = pool_sub.add_parser("list", help="列出池中标的")
    p.add_argument("--system", choices=POOL_SYSTEM_CHOICES, default=None)
    p.add_argument("--tier", choices=POOL_TIER_CHOICES, default=None)
    p.add_argument("-v", "--verbose", action="store_true", help="显示备注")

    p = pool_sub.add_parser("status", help="生成池状态摘要报告")
    p.add_argument("--output", default=None, help="输出 Markdown 路径（默认 stdout）")

    p = pool_sub.add_parser("add", help="添加标的到池")
    p.add_argument("--symbol", required=True, help="如 SZSE:300750")
    p.add_argument("--system", required=True, choices=POOL_SYSTEM_CHOICES)
    p.add_argument("--tier", choices=POOL_TIER_CHOICES, default="candidates")
    p.add_argument("--name", default=None)
    p.add_argument("--reason", default="")
    p.add_argument("--trigger", type=float, default=None, help="触发入场价")
    p.add_argument("--stop-loss", type=float, default=None, dest="stop_loss")
    p.add_argument("--position-pct", type=float, default=None, dest="position_pct")
    p.add_argument("--research", default=None, help="研究报告路径")
    p.add_argument("--score", type=float, default=None)
    p.add_argument("--notes", default="")

    p = pool_sub.add_parser("remove", help="移出标的（记录原因）")
    p.add_argument("--symbol", required=True)
    p.add_argument("--system", choices=POOL_SYSTEM_CHOICES, default=None)
    p.add_argument("--reason", default="")

    p = pool_sub.add_parser("promote", help="升层（candidates→watchlist→ready）")
    p.add_argument("--symbol", required=True)
    p.add_argument("--system", required=True, choices=POOL_SYSTEM_CHOICES)
    p.add_argument("--to", required=True, choices=["watchlist", "ready"], dest="to")
    p.add_argument("--research", default=None)

    p = pool_sub.add_parser("update", help="更新标的状态/触发价/备注")
    p.add_argument("--symbol", required=True)
    p.add_argument("--system", choices=POOL_SYSTEM_CHOICES, default=None)
    p.add_argument("--status", default=None, choices=["waiting_market", "waiting_catalyst", "ready", "entered"])
    p.add_argument("--trigger", type=float, default=None)
    p.add_argument("--stop-loss", type=float, default=None, dest="stop_loss")
    p.add_argument("--notes", default=None)

    p = pool_sub.add_parser("sync-from-scan", help="比对扫描结果与现有池，输出进出池建议（不修改池）")
    p.add_argument("--scan", required=True, help="扫描 JSON 路径，如 artifacts/scan/canslim-20260506.json")
    p.add_argument("--system", required=True, choices=POOL_SYSTEM_CHOICES)


def register_scheduler_commands(sub: argparse._SubParsersAction) -> None:
    from trading_os.scheduler import cmd_scheduler

    p = sub.add_parser("scheduler", help="后台任务编排服务控制面")
    scheduler_sub = p.add_subparsers(dest="scheduler_cmd", required=True)
    p.set_defaults(func=cmd_scheduler)

    p_run = scheduler_sub.add_parser("run", help="启动后台调度服务")
    p_run.set_defaults(func=cmd_scheduler)

    p_status = scheduler_sub.add_parser("status", help="显示当前任务状态")
    p_status.set_defaults(func=cmd_scheduler)

    p_jobs = scheduler_sub.add_parser("jobs", help="列出最近任务")
    p_jobs.add_argument("--limit", type=int, default=50)
    p_jobs.set_defaults(func=cmd_scheduler)

    p_trigger = scheduler_sub.add_parser("trigger", help="手动触发任务")
    p_trigger.add_argument(
        "job_name",
        choices=["market_data_probe", "market_data_bulk_refresh", "full_scan_and_daily"],
    )
    p_trigger.add_argument("--effective-date", default=None, help="YYYY-MM-DD")
    p_trigger.add_argument("--force", action="store_true", help="对扫描任务允许重复运行")
    p_trigger.set_defaults(func=cmd_scheduler)


def register_daily_commands(sub: argparse._SubParsersAction) -> None:
    from trading_os.scheduler import cmd_daily

    p = sub.add_parser("daily", help="读取 scheduler 状态生成日报或阻塞报告")
    p.add_argument("--effective-date", default=None, help="YYYY-MM-DD；默认今日")
    p.add_argument("--allow-historical", action="store_true", help="允许生成历史复盘报告")
    p.set_defaults(func=cmd_daily)
