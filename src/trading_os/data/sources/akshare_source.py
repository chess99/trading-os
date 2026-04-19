"""
A股数据源 - 基于akshare

提供A股市场的实时和历史数据获取功能
"""

from typing import Any
import pandas as pd
import logging
import threading
from datetime import datetime, timedelta

from ..schema import Exchange, Symbol, Timeframe, Adjustment


logger = logging.getLogger(__name__)

# 新浪接口使用 mini_racer（JS 引擎），不是线程安全的。
# 并发调用时必须串行化新浪 fallback，否则 mini_racer 会崩溃。
_SINA_LOCK = threading.Lock()


class AkshareConfig:
    """Akshare数据源配置"""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout


def fetch_daily_bars(
    ticker: str,
    *,
    exchange: Exchange,
    start: str | None = None,
    end: str | None = None,
    adjustment: Adjustment = Adjustment.NONE,
    config: AkshareConfig | None = None,
) -> pd.DataFrame:
    """
    从akshare获取A股日线数据

    Args:
        ticker: 股票代码 (如 "600000", "000001")
        exchange: 交易所 (SSE/SZSE)
        start: 开始日期 "YYYY-MM-DD"
        end: 结束日期 "YYYY-MM-DD"
        adjustment: 复权类型
        config: 配置参数

    Returns:
        标准化的DataFrame，包含OHLCV数据
    """
    try:
        import akshare as ak
    except ImportError as e:
        raise RuntimeError(
            "akshare is required for A-share data. Install with: pip install akshare"
        ) from e

    if config is None:
        config = AkshareConfig()

    # 验证交易所
    if exchange not in [Exchange.SSE, Exchange.SZSE]:
        raise ValueError(f"akshare仅支持SSE和SZSE交易所，得到: {exchange}")

    # 构造akshare股票代码
    symbol_str = _build_akshare_symbol(ticker, exchange)

    try:
        logger.info(f"获取A股数据: {symbol_str}, 复权类型: {adjustment}")

        # 设置默认日期范围
        if end is None:
            end = datetime.now().strftime("%Y%m%d")
        else:
            end = end.replace("-", "")

        if start is None:
            start = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
        else:
            start = start.replace("-", "")

        # 根据复权类型获取数据（优先东财接口，失败自动 fallback 新浪）
        adjust_map = {Adjustment.QFQ: "qfq", Adjustment.HFQ: "hfq", Adjustment.NONE: ""}
        adjust_str = adjust_map.get(adjustment, "")

        df = _fetch_with_fallback(ak, symbol_str, exchange, start, end, adjust_str)

        if df is None or df.empty:
            logger.warning(f"未获取到数据: {symbol_str}")
            return pd.DataFrame()

        # 标准化列名和数据格式
        df = _normalize_akshare_data(df, ticker, exchange, adjustment)

        logger.info(f"成功获取 {len(df)} 条记录: {symbol_str}")
        return df

    except Exception as e:
        logger.error(f"获取A股数据失败 {symbol_str}: {e}")
        raise RuntimeError(f"akshare数据获取失败: {e}") from e


def _fetch_with_fallback(ak, symbol_str: str, exchange: "Exchange", start: str, end: str, adjust: str) -> "pd.DataFrame":
    """先用东财接口，失败自动 fallback 到新浪接口。

    东财（push2his.eastmoney.com）：境外 IP 不可达。
    新浪（finance.sina.com.cn）：无地区限制，本机可用。
    """
    import pandas as pd

    # 主路：东财
    try:
        df = ak.stock_zh_a_hist(
            symbol=symbol_str,
            period="daily",
            start_date=start,
            end_date=end,
            adjust=adjust,
        )
        if df is not None and not df.empty:
            logger.debug(f"东财接口成功: {symbol_str}")
            return df
    except Exception as e:
        logger.warning(f"东财接口失败({symbol_str}): {e}，切换新浪接口")

    # Fallback：新浪（stock_zh_a_daily 需要 "sh600000" / "sz000001" 格式）
    # mini_racer 不是线程安全的，必须加锁串行化
    try:
        prefix = "sh" if exchange.value == "SSE" else "sz"
        sina_symbol = f"{prefix}{symbol_str}"
        adjust_sina = {"qfq": "qfq", "hfq": "hfq", "": None}.get(adjust, None)
        with _SINA_LOCK:
            df = ak.stock_zh_a_daily(symbol=sina_symbol, adjust=adjust_sina)
        if df is None or df.empty:
            return pd.DataFrame()

        # 新浪接口列名不同，统一映射到东财列名
        # 注意：新浪已有 amount 列（成交额），直接映射，不补占位列
        df = df.rename(columns={
            "date": "日期",
            "open": "开盘",
            "high": "最高",
            "low": "最低",
            "close": "收盘",
            "volume": "成交量",
            "amount": "成交额",
        })

        logger.info(f"新浪接口成功: {sina_symbol}，共{len(df)}条")
        return df
    except Exception as e2:
        logger.error(f"新浪接口也失败({sina_symbol}): {e2}")
        return pd.DataFrame()


def _build_akshare_symbol(ticker: str, exchange: Exchange) -> str:
    """构造akshare使用的股票代码"""
    # akshare使用6位数字代码
    if len(ticker) != 6 or not ticker.isdigit():
        raise ValueError(f"A股代码必须是6位数字，得到: {ticker}")

    return ticker


def _normalize_akshare_data(
    df: pd.DataFrame,
    ticker: str,
    exchange: Exchange,
    adjustment: Adjustment
) -> pd.DataFrame:
    """标准化akshare数据格式"""

    # akshare返回的列名映射
    column_mapping = {
        "日期": "ts",
        "开盘": "open",
        "收盘": "close",
        "最高": "high",
        "最低": "low",
        "成交量": "volume",
        "成交额": "amount",
        "振幅": "amplitude",
        "涨跌幅": "pct_change",
        "涨跌额": "change",
        "换手率": "turnover"
    }

    # 重命名列
    df = df.rename(columns=column_mapping)

    # 确保必要的列存在
    required_columns = ["ts", "open", "high", "low", "close", "volume"]
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"缺少必要列: {col}")

    # 处理时间戳
    df["ts"] = pd.to_datetime(df["ts"])

    # 添加标准化字段
    symbol_id = Symbol(exchange=exchange, ticker=ticker)
    df["symbol"] = str(symbol_id)
    df["exchange"] = exchange.value
    df["timeframe"] = Timeframe.D1.value
    df["adjustment"] = adjustment.value
    df["source"] = "akshare"

    # 计算VWAP (成交量加权平均价)
    if "amount" in df.columns and df["amount"].notna().all():
        # 成交额 / 成交量 = VWAP (注意akshare成交额单位)
        df["vwap"] = df["amount"] * 10000 / df["volume"]  # 成交额通常以万元为单位
    else:
        # 如果没有成交额，使用简单平均价
        df["vwap"] = (df["high"] + df["low"] + df["close"]) / 3

    # 交易笔数 (akshare通常不提供，使用估算)
    df["trades"] = (df["volume"] / 100).astype(int)  # 估算：平均每手100股

    # 确保数值类型
    numeric_columns = ["open", "high", "low", "close", "volume", "vwap", "trades"]
    for col in numeric_columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # 按时间排序
    df = df.sort_values("ts").reset_index(drop=True)

    # 选择标准列
    standard_columns = [
        "symbol", "ts", "open", "high", "low", "close",
        "volume", "vwap", "trades", "source"
    ]

    return df[standard_columns]


def get_stock_info(ticker: str, exchange: Exchange) -> dict:
    """获取股票基本信息"""
    try:
        import akshare as ak

        symbol_str = _build_akshare_symbol(ticker, exchange)

        # 获取股票基本信息
        info = ak.stock_individual_info_em(symbol=symbol_str)

        if info is not None and not info.empty:
            return {
                "symbol": Symbol(exchange=exchange, ticker=ticker),
                "name": info.get("股票简称", ""),
                "market_cap": info.get("总市值", 0),
                "pe_ratio": info.get("市盈率", 0),
                "pb_ratio": info.get("市净率", 0),
                "industry": info.get("所属行业", ""),
                "source": "akshare"
            }

        return {}

    except Exception as e:
        logger.warning(f"获取股票信息失败 {ticker}: {e}")
        return {}


def get_market_index(index_code: str = "000001") -> pd.DataFrame:
    """
    获取市场指数数据

    Args:
        index_code: 指数代码，默认"000001"(上证指数)

    Returns:
        指数历史数据
    """
    try:
        import akshare as ak

        # 获取指数数据
        df = ak.stock_zh_index_daily(symbol=f"sh{index_code}")

        if df is None or df.empty:
            return pd.DataFrame()

        # 标准化格式
        df = df.rename(columns={
            "date": "ts",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "volume": "volume"
        })

        df["ts"] = pd.to_datetime(df["ts"])
        df["symbol"] = f"INDEX:{index_code}"
        df["source"] = "akshare"

        return df.sort_values("ts").reset_index(drop=True)

    except Exception as e:
        logger.error(f"获取指数数据失败: {e}")
        return pd.DataFrame()