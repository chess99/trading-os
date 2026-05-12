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

# BaoStock login/logout 是全局状态，并发调用会互相干扰。
_BAOSTOCK_LOCK = threading.Lock()

# 会话级别数据源可用性缓存：None=未探测, True=可用, False=不可用
# 探测一次后整个进程内复用，避免每只股票都等超时。
_SOURCE_AVAILABILITY: dict[str, bool | None] = {
    "eastmoney": None,
    "sina": None,
    "baostock": None,
}
_SOURCE_PROBE_LOCK = threading.Lock()

# 代理/全局网络故障特征词：匹配后立即将 eastmoney 标记为会话级不可用。
# "443" 太宽泛（可能出现在价格或错误码中），依赖其他关键词已足够覆盖 ProxyError/TLS 场景。
_PROXY_KEYWORDS: tuple[str, ...] = ("proxy", "proxyerror", "max retries", "remotedisconnected")


def probe_and_get_preferred_source(exchange: "Exchange", timeout: int = 10) -> str:
    """探测各数据源可用性，返回首选源名称（'eastmoney'/'sina'/'baostock'/'none'）。

    使用 600000（浦发银行）作为探针股票，结果在进程内缓存。
    每个源最多等 timeout 秒，避免卡在超时上。
    仅在首次调用时实际发起网络请求，后续直接返回缓存结果。
    """
    import akshare as ak
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

    with _SOURCE_PROBE_LOCK:
        # 已探测过，直接返回
        if _SOURCE_AVAILABILITY["eastmoney"] is not None:
            if _SOURCE_AVAILABILITY["eastmoney"]:
                return "eastmoney"
            if _SOURCE_AVAILABILITY["sina"]:
                return "sina"
            if _SOURCE_AVAILABILITY["baostock"]:
                return "baostock"
            return "none"

        probe_ticker = "600000"
        probe_start = "20260101"
        probe_end = "20260401"

        def _try_eastmoney():
            return ak.stock_zh_a_hist(
                symbol=probe_ticker, period="daily",
                start_date=probe_start, end_date=probe_end, adjust="qfq",
            )

        def _try_sina():
            with _SINA_LOCK:
                return ak.stock_zh_a_daily(symbol=f"sh{probe_ticker}", adjust="qfq")

        def _try_baostock():
            from .baostock_source import fetch_daily_bars as bs_fetch
            from ..schema import Adjustment as Adj
            with _BAOSTOCK_LOCK:
                return bs_fetch(probe_ticker, exchange=exchange, start="2026-01-01", end="2026-04-01", adjustment=Adj.QFQ)

        for source_name, probe_fn in [
            ("eastmoney", _try_eastmoney),
            ("sina", _try_sina),
            ("baostock", _try_baostock),
        ]:
            try:
                # cancel_futures=True：超时后不等阻塞线程（避免 executor.__exit__ 挂死）
                executor = ThreadPoolExecutor(max_workers=1)
                future = executor.submit(probe_fn)
                try:
                    df = future.result(timeout=timeout)
                except FuturesTimeout:
                    future.cancel()
                    executor.shutdown(wait=False)
                    _SOURCE_AVAILABILITY[source_name] = False
                    logger.warning(f"源探测：{source_name} 超时（>{timeout}s）")
                    continue
                finally:
                    executor.shutdown(wait=False)
                if df is not None and not df.empty:
                    _SOURCE_AVAILABILITY[source_name] = True
                    logger.info(f"源探测：{source_name} 可用")
                    return source_name
                else:
                    _SOURCE_AVAILABILITY[source_name] = False
                    logger.warning(f"源探测：{source_name} 返回空数据")
            except Exception as e:
                _SOURCE_AVAILABILITY[source_name] = False
                logger.warning(f"源探测：{source_name} 不可用 ({e})")

        return "none"


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
    asset_type: "Any | None" = None,
) -> tuple[pd.DataFrame, str]:
    """
    从akshare获取A股日线数据（自动选择最佳数据源）

    Args:
        ticker: 股票代码 (如 "600000", "000001")
        exchange: 交易所 (SSE/SZSE)
        start: 开始日期 "YYYY-MM-DD"
        end: 结束日期 "YYYY-MM-DD"
        adjustment: 复权类型（对指数无效，会被强制覆盖为 NONE）
        config: 配置参数（仅 EquityHandler 使用）
        asset_type: 资产类型。None 或不传时默认 AssetType.EQUITY（向后兼容）。
                    指数请显式传 AssetType.INDEX。

    Returns:
        (标准化的DataFrame，实际使用的数据源名称)
    """
    from ..schema import AssetType as AT
    from .asset_type_handler import get_handler

    if asset_type is None:
        asset_type = AT.EQUITY

    try:
        import akshare  # noqa: F401 — ensure akshare is installed
    except ImportError as e:
        raise RuntimeError(
            "akshare is required for A-share data. Install with: pip install akshare"
        ) from e

    if exchange not in [Exchange.SSE, Exchange.SZSE]:
        raise ValueError(f"akshare仅支持SSE和SZSE交易所，得到: {exchange}")

    handler = get_handler(asset_type)
    df, source = handler.fetch(ticker, exchange, start=start, end=end, adjustment=adjustment)
    if df is not None and not df.empty:
        handler.validate(df, ticker, exchange)
    return df if df is not None else pd.DataFrame(), source


def _fetch_with_fallback(ak, symbol_str: str, exchange: "Exchange", start: str, end: str, adjust: str) -> "tuple[pd.DataFrame, str]":
    """先用东财接口，失败自动 fallback 到新浪接口，再失败 fallback 到 BaoStock。

    东财（push2his.eastmoney.com）：境外 IP 不可达，ETF 可能失败。
    新浪（finance.sina.com.cn）：ETF 代码解析失败。
    BaoStock：国内直连，支持 A 股及 ETF，无需代理。

    会话级别源可用性缓存：如果探测已确认某源不可用，直接跳过，不等超时。

    Returns:
        (DataFrame, source_name)，source_name 为 "akshare" / "baostock" / "none"
    """
    import pandas as pd

    # 主路：东财（若会话级探测已确认不可用则跳过）
    if _SOURCE_AVAILABILITY["eastmoney"] is not False:
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
                return df, "akshare"
        except Exception as e:
            err_str = str(e).lower()
            if any(kw in err_str for kw in _PROXY_KEYWORDS):
                # 代理/网络全局性故障：标记整个会话内跳过东财，避免每只股票都等超时
                _SOURCE_AVAILABILITY["eastmoney"] = False
                logger.warning(f"东财接口代理错误，本会话内禁用东财接口: {e}")
            else:
                logger.warning(f"东财接口失败({symbol_str}): {e}，切换新浪接口")

    # Fallback 1：新浪（若会话级探测已确认不可用则跳过）
    # mini_racer 不是线程安全的，必须加锁串行化
    sina_symbol = ""
    if _SOURCE_AVAILABILITY["sina"] is not False:
        try:
            prefix = "sh" if exchange.value == "SSE" else "sz"
            sina_symbol = f"{prefix}{symbol_str}"
            adjust_sina = {"qfq": "qfq", "hfq": "hfq", "": None}.get(adjust, None)
            with _SINA_LOCK:
                df = ak.stock_zh_a_daily(symbol=sina_symbol, adjust=adjust_sina)
            if df is not None and not df.empty:
                # 新浪接口列名不同，统一映射到东财列名
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
                return df, "akshare"
            logger.warning(f"新浪接口也失败({sina_symbol}): No value to decode，切换 BaoStock 接口")
        except Exception as e2:
            logger.warning(f"新浪接口也失败({sina_symbol}): {e2}，切换 BaoStock 接口")

    # Fallback 2：BaoStock（若会话级探测已确认不可用则跳过）
    # ETF/LOF 代码新浪失败是预期行为，不走 BaoStock fallback——BaoStock 不通时会超时卡死全量更新进程。
    # SSE ETF 前缀：51xxxx（普通ETF）、56xxxx（LOF）、58xxxx（科创板ETF，如588000科创50ETF）
    # SZSE ETF 前缀：15xxxx、16xxxx
    _is_etf = (
        (exchange.value == "SSE" and (
            symbol_str.startswith("51") or symbol_str.startswith("56") or symbol_str.startswith("58")
        ))
        or (exchange.value == "SZSE" and (symbol_str.startswith("15") or symbol_str.startswith("16")))
    )
    if _is_etf:
        return pd.DataFrame(), "none"
    # BaoStock login/logout 是全局状态，并发时必须串行化
    if _SOURCE_AVAILABILITY["baostock"] is False:
        return pd.DataFrame(), "none"
    try:
        from .baostock_source import fetch_daily_bars as bs_fetch
        from ..schema import Adjustment as Adj
        adjust_map = {"qfq": Adj.QFQ, "hfq": Adj.HFQ, "": Adj.NONE}
        adj = adjust_map.get(adjust, Adj.NONE)
        # BaoStock 日期格式 YYYY-MM-DD，而 start/end 此时是 YYYYMMDD
        start_fmt = f"{start[:4]}-{start[4:6]}-{start[6:8]}"
        end_fmt = f"{end[:4]}-{end[4:6]}-{end[6:8]}"
        with _BAOSTOCK_LOCK:
            bs_df = bs_fetch(symbol_str, exchange=exchange, start=start_fmt, end=end_fmt, adjustment=adj)
        if bs_df is not None and not bs_df.empty:
            # BaoStock 返回的是标准化列名（BarColumns），需映射回东财格式供后续 _normalize_akshare_data 处理
            bs_df = bs_df.rename(columns={
                "ts": "日期",
                "open": "开盘",
                "high": "最高",
                "low": "最低",
                "close": "收盘",
                "volume": "成交量",
            })
            bs_df["成交额"] = 0  # BaoStock 标准输出不含 amount，补占位列
            logger.info(f"BaoStock 接口成功: {symbol_str}，共{len(bs_df)}条")
            return bs_df, "baostock"
    except Exception as e3:
        logger.error(f"BaoStock 接口也失败({symbol_str}): {e3}")

    return pd.DataFrame(), "none"


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

    .. deprecated::
        使用 IndexHandler.fetch() 替代（通过 fetch_daily_bars(..., asset_type=AssetType.INDEX)）。
        此函数写入 source='akshare'（非 'akshare_index'），会被
        _check_price_continuity 拦截，且不走 AssetType 校验。

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

def _make_akshare_df_for_test() -> pd.DataFrame:
    """Test helper: minimal DataFrame in akshare (eastmoney) column format."""
    return pd.DataFrame({
        "日期": pd.date_range("2024-01-01", periods=5, freq="B"),
        "开盘": [10.0, 10.1, 10.2, 10.3, 10.4],
        "最高": [10.5, 10.6, 10.7, 10.8, 10.9],
        "最低": [9.5, 9.6, 9.7, 9.8, 9.9],
        "收盘": [10.2, 10.3, 10.4, 10.5, 10.6],
        "成交量": [1_000_000] * 5,
        "成交额": [10_000_000.0] * 5,
    })
