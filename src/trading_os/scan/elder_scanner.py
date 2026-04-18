"""Elder 技术交易体系批量筛选。

筛选逻辑：
1. 成交额过滤（由 common.filter_by_turnover 处理）
2. 周线 EMA(26) 方向（上升/下降，排除走平）
3. 周线 MACD 柱季节（spring/summer/autumn/winter）
4. 日线随机指标（做多 < 30，做空 > 70）
5. 日线 2 日强力指数（做多为负，做空为正）

评分公式（满分 10）：
- 通过条件 2-5 各 +2 分（基础满分 8）
- MACD 季节为 spring/autumn（最佳）额外 +1
- 随机指标 + 强力指数同时确认额外 +1
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

log = logging.getLogger(__name__)

# 最少需要 52 周日线数据才运行（保证 EMA(26) 稳定）
MIN_WEEKS = 52


def _macd_season(macd_hist: "pd.Series") -> str:
    """判断 MACD 柱季节。

    spring:  0 值以下，斜率向上（最佳做多时机）
    summer:  0 值以上，斜率向上
    autumn:  0 值以上，斜率向下（最佳做空时机）
    winter:  0 值以下，斜率向下
    """
    if len(macd_hist) < 2:
        return "unknown"
    last = macd_hist.iloc[-1]
    prev = macd_hist.iloc[-2]
    rising = last > prev
    above_zero = last > 0
    if not above_zero and rising:
        return "spring"
    if above_zero and rising:
        return "summer"
    if above_zero and not rising:
        return "autumn"
    return "winter"


def _ema_direction(ema: "pd.Series") -> str:
    """判断 EMA 方向：up / down / flat。"""
    if len(ema) < 3:
        return "flat"
    last = ema.iloc[-1]
    prev = ema.iloc[-3]
    if last is None or prev is None:
        return "flat"
    import math
    if math.isnan(last) or math.isnan(prev):
        return "flat"
    diff = (last - prev) / prev if prev != 0 else 0
    if diff > 0.001:
        return "up"
    if diff < -0.001:
        return "down"
    return "flat"


def scan_elder(
    symbols: list[str],
    bars_df: "pd.DataFrame",
    *,
    scan_date: date,
    top_n: int = 30,
) -> dict[str, Any]:
    """对给定符号列表运行 Elder 技术指标筛选。

    Args:
        symbols: 已经过成交额过滤的候选符号
        bars_df: 所有符号的日线数据 DataFrame
        scan_date: 扫描日期
        top_n: 输出前 N 只

    Returns:
        符合 scan output 格式的 dict（不含 filtered_out，由调用方合并）
    """
    try:
        import pandas as pd
        import pandas_ta as ta
    except ImportError as exc:
        raise RuntimeError(
            "pandas_ta 未安装。请运行：pip install 'trading-os[data_ashare]'"
        ) from exc

    candidates = []
    insufficient_data = 0
    no_signal = 0

    for sym in symbols:
        sym_bars = bars_df[bars_df["symbol"] == sym].copy()
        if sym_bars.empty:
            insufficient_data += 1
            continue

        # 设置时间索引（用于 resample）
        sym_bars = sym_bars.sort_values("ts")
        sym_bars = sym_bars.set_index("ts")
        sym_bars.index = pd.to_datetime(sym_bars.index, utc=True)

        # 检查最小数据量（52 周 ≈ 365 天）
        if len(sym_bars) < MIN_WEEKS * 5:  # 约 260 个交易日
            insufficient_data += 1
            continue

        # 周线 resample
        weekly = sym_bars[["open", "high", "low", "close", "volume"]].resample("W-FRI").agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }).dropna()

        if len(weekly) < MIN_WEEKS:
            insufficient_data += 1
            continue

        # ── 第一滤网：周线 EMA(26) + MACD ──
        weekly_ema = ta.ema(weekly["close"], length=26)
        if weekly_ema is None or weekly_ema.isna().all():
            insufficient_data += 1
            continue

        ema_dir = _ema_direction(weekly_ema)
        if ema_dir == "flat":
            no_signal += 1
            continue  # 走平不参与

        weekly_macd = ta.macd(weekly["close"], fast=12, slow=26, signal=9)
        if weekly_macd is None or weekly_macd.empty:
            insufficient_data += 1
            continue

        macd_hist_col = [c for c in weekly_macd.columns if "h" in c.lower()]
        if not macd_hist_col:
            insufficient_data += 1
            continue
        macd_hist = weekly_macd[macd_hist_col[0]].dropna()
        if len(macd_hist) < 2:
            insufficient_data += 1
            continue

        season = _macd_season(macd_hist)

        # ── 第二滤网：日线随机指标 + 强力指数 ──
        daily = sym_bars.copy()
        stoch = ta.stoch(daily["high"], daily["low"], daily["close"], k=5, d=3)
        stoch_k = None
        if stoch is not None and not stoch.empty:
            k_col = [c for c in stoch.columns if "k" in c.lower()]
            if k_col:
                stoch_k = stoch[k_col[0]].dropna().iloc[-1] if not stoch[k_col[0]].dropna().empty else None

        # 强力指数 = 成交量 × (今收 - 昨收)，取 2 日 EMA
        daily["force"] = daily["volume"] * daily["close"].diff()
        force_ema = ta.ema(daily["force"].dropna(), length=2)
        force_val = force_ema.iloc[-1] if force_ema is not None and not force_ema.empty else None

        # ── 判断做多/做空方向 ──
        direction = "long" if ema_dir == "up" else "short"

        stoch_ok = False
        force_ok = False
        if stoch_k is not None:
            stoch_ok = (direction == "long" and stoch_k < 30) or (direction == "short" and stoch_k > 70)
        if force_val is not None:
            import math
            if not math.isnan(force_val):
                force_ok = (direction == "long" and force_val < 0) or (direction == "short" and force_val > 0)

        # 至少需要一个第二滤网信号
        if not stoch_ok and not force_ok:
            no_signal += 1
            continue

        # ── 评分 ──
        score = 0.0
        score += 2  # 条件2: EMA 方向明确
        score += 2  # 条件3: MACD 季节（有值就算通过）
        if stoch_ok:
            score += 2  # 条件4
        if force_ok:
            score += 2  # 条件5
        if season in ("spring", "autumn"):
            score += 1  # 最佳季节加分
        if stoch_ok and force_ok:
            score += 1  # 双重确认加分

        candidates.append({
            "symbol": sym,
            "rank": 0,  # 后续排序后填入
            "score": round(score, 1),
            "direction": direction,
            "signals": {
                "weekly_ema_direction": ema_dir,
                "macd_season": season,
                "daily_stoch": round(float(stoch_k), 1) if stoch_k is not None else None,
                "force_index_2d": round(float(force_val), 0) if force_val is not None else None,
            },
            "next_step": f"运行 elder-screen 做三重滤网深度分析（方向：{direction}）",
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
