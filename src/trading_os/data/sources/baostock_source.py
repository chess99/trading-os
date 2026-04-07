"""BaoStock 数据源 — 国内直连，无需代理，免费历史数据。

覆盖：沪深 A 股日线/周线/月线，前复权/后复权/不复权。
数据质量：可靠，延迟约 T+1（当日数据次日可取）。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from ..schema import Adjustment, BarColumns, Exchange

log = logging.getLogger(__name__)

# BaoStock 股票代码前缀
_EXCHANGE_PREFIX = {
    Exchange.SSE: "sh",
    Exchange.SZSE: "sz",
}

# BaoStock 复权参数
_ADJUST_FLAG = {
    Adjustment.NONE: "3",    # 不复权
    Adjustment.QFQ: "2",     # 前复权
    Adjustment.HFQ: "1",     # 后复权
}


def fetch_daily_bars(
    ticker: str,
    *,
    exchange: Exchange,
    start: str | None = None,
    end: str | None = None,
    adjustment: Adjustment = Adjustment.QFQ,
):
    """从 BaoStock 获取 A 股日线数据。

    Args:
        ticker:     股票代码（如 "600000"）
        exchange:   交易所（SSE / SZSE）
        start:      开始日期 "YYYY-MM-DD"
        end:        结束日期 "YYYY-MM-DD"
        adjustment: 复权类型（默认前复权）

    Returns:
        标准化的 DataFrame，包含 OHLCV 数据，列名与 BarColumns 一致。
    """
    try:
        import baostock as bs
        import pandas as pd
    except ImportError as e:
        raise RuntimeError(
            "baostock is required. Install with: pip install baostock"
        ) from e

    if exchange not in _EXCHANGE_PREFIX:
        raise ValueError(f"BaoStock 仅支持 SSE/SZSE，得到: {exchange}")

    prefix = _EXCHANGE_PREFIX[exchange]
    bs_symbol = f"{prefix}.{ticker}"
    adjust_flag = _ADJUST_FLAG.get(adjustment, "3")

    if end is None:
        end = datetime.now().strftime("%Y-%m-%d")
    if start is None:
        start = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

    # BaoStock 需要 YYYY-MM-DD 格式
    start = start[:10]
    end = end[:10]

    log.info("BaoStock 获取数据: %s [%s ~ %s] 复权=%s", bs_symbol, start, end, adjustment.value)

    lg = bs.login()
    if lg.error_code != "0":
        raise RuntimeError(f"BaoStock 登录失败: {lg.error_msg}")

    try:
        rs = bs.query_history_k_data_plus(
            bs_symbol,
            "date,open,high,low,close,volume,amount,turn,pctChg",
            start_date=start,
            end_date=end,
            frequency="d",
            adjustflag=adjust_flag,
        )

        if rs.error_code != "0":
            raise RuntimeError(f"BaoStock 查询失败: {rs.error_msg}")

        rows = []
        while rs.next():
            rows.append(rs.get_row_data())

        if not rows:
            log.warning("BaoStock 未返回数据: %s", bs_symbol)
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume", "amount", "turn", "pctChg"])

        # 过滤空行（停牌日）
        df = df[df["open"] != ""].copy()
        if df.empty:
            return pd.DataFrame()

        # 转换类型
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["open", "close"])

        # 标准化为 BarColumns 格式
        symbol_id = f"{exchange.value}:{ticker}"
        df[BarColumns.symbol] = symbol_id
        df[BarColumns.ts] = pd.to_datetime(df["date"], utc=True)
        df[BarColumns.open] = df["open"]
        df[BarColumns.high] = df["high"]
        df[BarColumns.low] = df["low"]
        df[BarColumns.close] = df["close"]
        df[BarColumns.volume] = df["volume"]
        df[BarColumns.source] = "baostock"

        cols = [
            BarColumns.symbol, BarColumns.ts,
            BarColumns.open, BarColumns.high, BarColumns.low,
            BarColumns.close, BarColumns.volume, BarColumns.source,
        ]
        return df[cols].sort_values(BarColumns.ts).reset_index(drop=True)

    finally:
        bs.logout()
