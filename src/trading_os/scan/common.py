"""共享工具层：全市场扫描的公共函数。

所有 scanner 通过本模块获取数据，不直接调用底层 API。
"""
from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pandas as pd

log = logging.getLogger(__name__)


def get_stock_names(cache_path: Path | None = None, max_age_days: int = 30) -> dict[str, str]:
    """获取全 A 股中文名称映射，返回 {symbol: name}。

    结果缓存到 data/stock_names.json，30 天内直接读缓存，不重复调接口。
    失败时返回空 dict（不影响主流程）。
    """
    import time

    if cache_path is None:
        # 默认缓存路径：相对于调用方的 data/ 目录，由 cli 传入
        # 这里用 None 表示"不缓存"，cli 传入具体路径
        pass

    # 读缓存
    if cache_path is not None and cache_path.exists():
        age_days = (time.time() - cache_path.stat().st_mtime) / 86400
        if age_days < max_age_days:
            try:
                return json.loads(cache_path.read_text(encoding="utf-8"))
            except Exception:
                pass

    # 从 BaoStock 拉取
    try:
        import baostock as bs
        lg = bs.login()
        if lg.error_code != "0":
            return {}
        rs = bs.query_stock_basic(code="", code_name="")
        name_map: dict[str, str] = {}
        while rs.next():
            row = rs.get_row_data()
            code = row[0]      # sh.600000
            name = row[1]      # 浦发银行
            stock_type = row[4]
            if stock_type != "1":
                continue
            prefix, ticker = code.split(".")
            exch = "SSE" if prefix == "sh" else "SZSE"
            name_map[f"{exch}:{ticker}"] = name
        bs.logout()

        # 写缓存
        if cache_path is not None and name_map:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(name_map, ensure_ascii=False), encoding="utf-8")

        return name_map
    except Exception:
        return {}


def to_canonical(exchange: str, ticker: str) -> str:
    """将交易所+代码转换为规范格式。

    Examples:
        to_canonical("SSE", "600000") -> "SSE:600000"
        to_canonical("SZSE", "000001") -> "SZSE:000001"
    """
    return f"{exchange.upper()}:{ticker}"


def fundamental_path(data_root: Path, symbol_id: str) -> Path:
    """返回基本面 JSON 文件路径。

    symbol_id: "SSE:600000" -> data_root/fundamental/SSE_600000.json
    冒号替换为下划线，避免 Windows 文件名非法字符。
    """
    safe_name = symbol_id.replace(":", "_")
    return data_root / "fundamental" / f"{safe_name}.json"


def load_fundamental(data_root: Path, symbol_id: str) -> dict[str, Any] | None:
    """读取基本面 JSON，文件不存在返回 None（不抛异常）。"""
    path = fundamental_path(data_root, symbol_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("Failed to read fundamental data for %s: %s", symbol_id, exc)
        return None


def get_scan_symbols(
    pipeline: Any,
    data_sources: Any,
    *,
    exchange: str | None = None,
) -> tuple[list[str], int]:
    """获取可扫描的股票列表。

    两步过滤：
    1. 从 AKShare 获取全市场列表，过滤 ST/退市
    2. 与本地 DuckDB available_symbols() 取交集

    Returns:
        (symbols, no_data_count) — 可扫描的规范化符号列表，以及无本地数据的数量
    """
    try:
        akshare_df = data_sources.get_a_stock_list()
    except Exception as exc:
        raise RuntimeError(
            f"AKShare 不可用，请检查网络连接。错误：{exc}"
        ) from exc

    if akshare_df is None or akshare_df.empty:
        raise RuntimeError(
            "AKShare 返回空股票列表，请检查网络连接后重试。"
        )

    # 过滤 ST / 退市：名称包含 ST、*ST、退 等
    mask = ~akshare_df["name"].str.contains(r"ST|退市", na=False)
    akshare_df = akshare_df[mask]

    # 转换为规范格式
    akshare_symbols = set(
        to_canonical(row["exchange"], row["symbol"])
        for _, row in akshare_df.iterrows()
    )

    # 与本地数据取交集
    from trading_os.data.schema import Exchange
    exch_enum = Exchange(exchange) if exchange else None
    local_symbols = set(pipeline.available_symbols(exchange=exch_enum))

    scan_symbols = sorted(akshare_symbols & local_symbols)
    no_data_count = len(akshare_symbols - local_symbols)

    log.info(
        "Scan symbols: %d (AKShare: %d, local: %d, no_data: %d)",
        len(scan_symbols), len(akshare_symbols), len(local_symbols), no_data_count,
    )
    return scan_symbols, no_data_count


def filter_by_turnover(
    symbols: list[str],
    bars_df: "pd.DataFrame",
    *,
    min_amount: float,
    lookback_days: int = 20,
) -> tuple[list[str], int]:
    """按过去 N 日均成交额过滤。

    Args:
        symbols: 候选符号列表
        bars_df: 包含所有符号日线数据的 DataFrame（symbol, ts, volume, close 列）
        min_amount: 最低日均成交额（CNY）
        lookback_days: 计算均值的天数

    Returns:
        (passed_symbols, filtered_count)
    """
    import pandas as pd

    if bars_df.empty:
        return [], len(symbols)

    # 计算成交额（CNY）
    # BaoStock 的 volume 单位是手（1手=100股），需要乘以 100
    # AKShare 的 volume 单位是股，不需要乘以 100
    # 两种数据源都用 volume * close 近似，但 BaoStock 需要再乘 100
    # 判断方法：BaoStock 数据的 source 列为 "baostock"
    bars_df = bars_df.copy()
    if "source" in bars_df.columns and (bars_df["source"] == "baostock").any():
        bars_df["turnover"] = bars_df["volume"] * bars_df["close"] * 100
    else:
        bars_df["turnover"] = bars_df["volume"] * bars_df["close"]

    passed = []
    filtered = 0
    for sym in symbols:
        sym_bars = bars_df[bars_df["symbol"] == sym].tail(lookback_days)
        if sym_bars.empty:
            filtered += 1
            continue
        avg_turnover = sym_bars["turnover"].mean()
        if avg_turnover >= min_amount:
            passed.append(sym)
        else:
            filtered += 1

    return passed, filtered


def load_bars_batch(
    pipeline: Any,
    symbols: list[str],
    *,
    scan_date: date,
    lookback_days: int = 504,  # ~2年
) -> "pd.DataFrame":
    """批量加载历史 K 线，继承 DataPipeline 的前瞻偏差防护。

    一次调用返回所有符号的数据，不逐只调用。
    """
    import pandas as pd

    if not symbols:
        return pd.DataFrame()

    try:
        df = pipeline.get_bars(
            symbols,
            trading_date=scan_date,
            lookback_days=lookback_days,
        )
        return df if df is not None else pd.DataFrame()
    except Exception as exc:
        log.warning("Failed to load bars for batch of %d symbols: %s", len(symbols), exc)
        return pd.DataFrame()


class _NumpyEncoder(json.JSONEncoder):
    """处理 numpy 类型的 JSON 序列化。"""
    def default(self, obj: Any) -> Any:
        try:
            import numpy as np
            if isinstance(obj, (np.integer,)):
                return int(obj)
            if isinstance(obj, (np.floating,)):
                return float(obj)
            if isinstance(obj, (np.bool_,)):
                return bool(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
        except ImportError:
            pass
        return super().default(obj)


def write_scan_output(results: dict[str, Any], path: Path) -> None:
    """写入扫描结果 JSON 文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2, cls=_NumpyEncoder),
        encoding="utf-8",
    )
    log.info("Scan output written to %s", path)
