"""Value Investing 体系批量筛选。

筛选逻辑（全部用 Python 计算，无 AI）：
1. 当前 PE 相对该股过去 3 年价格序列的分位 < 30%（价格代理法，MVP）
   - 数据不足 1 年 → 跳过
   - 数据 1-3 年 → 标注"数据有限"
2. PB < 3（排除高溢价）
3. ROE ≥ 15%（排除低质量低估值陷阱）
4. 市值 > 50 亿（排除微盘股）

注意：PE/PB 数据来自 AKShare 实时快照（stock_zh_a_spot_em），
      不是 scan_date 的历史数据。在输出中标注 pe_pb_source: realtime_snapshot。
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_MAX_PB = 3.0
_MIN_ROE = 0.15
_MIN_MARKET_CAP = 50e8   # 50 亿
_PE_PERCENTILE_THRESHOLD = 0.30  # 当前 PE 低于历史 70% 的时间
_MIN_YEARS_FOR_PERCENTILE = 1.0   # 至少 1 年数据才计算分位
_FULL_YEARS_FOR_PERCENTILE = 3.0  # 3 年以上为"完整数据"


def _price_percentile(
    close_series: "pd.Series",
    current_price: float,
) -> tuple[float, bool]:
    """计算当前价格在历史价格序列中的分位。

    Returns:
        (percentile, is_limited_data)
        percentile: 0.0-1.0，越低表示当前价格越低
        is_limited_data: True 表示数据不足 3 年
    """
    if close_series.empty:
        return 1.0, True
    percentile = (close_series < current_price).mean()
    years_of_data = len(close_series) / 252  # 约估
    is_limited = years_of_data < _FULL_YEARS_FOR_PERCENTILE
    return float(percentile), is_limited


def scan_value(
    symbols: list[str],
    bars_df: "pd.DataFrame",
    *,
    scan_date: date,
    data_root: Path,
    top_n: int = 30,
) -> dict[str, Any]:
    """对给定符号列表运行 Value Investing 估值筛选。

    Args:
        symbols: 已经过成交额过滤的候选符号
        bars_df: 所有符号的日线数据 DataFrame
        scan_date: 扫描日期
        data_root: 项目数据根目录（用于读取 fundamental JSON）
        top_n: 输出前 N 只

    Returns:
        符合 scan output 格式的 dict（不含 filtered_out，由调用方合并）
    """
    import pandas as pd
    from .common import load_fundamental

    # 获取全市场实时 PE/PB/市值快照
    try:
        from trading_os.data.sources.akshare_factors import AkshareFactorSource
        akshare = AkshareFactorSource()
        snapshot_df = akshare.get_stock_basic_info()
    except Exception as exc:
        raise RuntimeError(
            f"AKShare 不可用，无法获取 PE/PB 数据，请检查网络连接。错误：{exc}"
        ) from exc

    # 建立 symbol → snapshot 行的映射
    # snapshot_df 的 symbol 列格式为 6 位代码，需要匹配规范格式
    snapshot_map: dict[str, Any] = {}
    if snapshot_df is not None and not snapshot_df.empty:
        for _, row in snapshot_df.iterrows():
            # 尝试从 symbol 列推断规范格式
            raw_sym = str(row.get("symbol", ""))
            if raw_sym.startswith("6"):
                canonical = f"SSE:{raw_sym}"
            else:
                canonical = f"SZSE:{raw_sym}"
            snapshot_map[canonical] = row

    candidates = []
    insufficient_data = 0
    no_signal = 0

    for sym in symbols:
        snap = snapshot_map.get(sym)
        if snap is None:
            insufficient_data += 1
            continue

        # ── 市值过滤 ──
        market_cap = snap.get("total_mv", 0)
        try:
            market_cap = float(market_cap) * 1e4  # AKShare 单位为万元
        except (TypeError, ValueError):
            market_cap = 0
        if market_cap < _MIN_MARKET_CAP:
            no_signal += 1
            continue

        # ── PB 过滤 ──
        pb = snap.get("pb", None)
        try:
            pb = float(pb) if pb is not None else None
        except (TypeError, ValueError):
            pb = None
        if pb is None or pb >= _MAX_PB or pb <= 0:
            no_signal += 1
            continue

        # ── PE 历史分位（价格代理法）──
        sym_bars = bars_df[bars_df["symbol"] == sym].sort_values("ts")
        if sym_bars.empty:
            insufficient_data += 1
            continue

        years_of_data = len(sym_bars) / 252
        if years_of_data < _MIN_YEARS_FOR_PERCENTILE:
            insufficient_data += 1
            continue

        current_price = sym_bars["close"].iloc[-1]
        percentile, is_limited_data = _price_percentile(sym_bars["close"], current_price)

        if percentile >= _PE_PERCENTILE_THRESHOLD:
            no_signal += 1
            continue

        # ── ROE 过滤（来自 fundamental JSON）──
        fund = load_fundamental(data_root, sym)
        roe_ok = False
        latest_roe = None
        if fund is not None:
            profitability = fund.get("profitability", {})
            roe_history = profitability.get("roe", [])
            if roe_history:
                latest_roe = roe_history[-1].get("value", 0)
                roe_ok = latest_roe >= _MIN_ROE
        # 无 fundamental 数据时跳过 ROE 过滤（不崩溃）

        if fund is not None and not roe_ok:
            no_signal += 1
            continue

        # ── 评分 ──
        score = 0.0
        score += 3  # PE 分位通过（最重要）
        score += 2  # PB 通过
        score += 1  # 市值通过
        if roe_ok:
            score += 2  # ROE 通过
        # PE 分位越低加分
        if percentile < 0.10:
            score += 2
        elif percentile < 0.20:
            score += 1

        candidates.append({
            "symbol": sym,
            "rank": 0,
            "score": round(score, 1),
            "signals": {
                "price_percentile_3yr": round(percentile, 3),
                "price_percentile_method": "price_proxy",
                "data_limited": is_limited_data,
                "pb": round(pb, 2),
                "roe": round(latest_roe, 3) if latest_roe is not None else None,
                "market_cap_billion": round(market_cap / 1e8, 1),
            },
            "pe_pb_source": "realtime_snapshot",
            "next_step": "运行 value-system 做深度基本面研究和估值分析",
        })

    # 排序 + 截取 top_n
    candidates.sort(key=lambda x: x["score"], reverse=True)
    candidates = candidates[:top_n]
    for i, c in enumerate(candidates, 1):
        c["rank"] = i

    return {
        "candidates": candidates,
        "_stats": {
            "insufficient_data": insufficient_data,
            "no_signal": no_signal,
        },
    }
