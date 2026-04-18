"""CANSLIM 成长股体系批量筛选。

筛选逻辑（全部用 Python 计算，无 AI）：
1. 当季 EPS 增速（同比）≥ 18%（C 维度）
   - 去年同期 EPS ≤ 0 → 跳过（insufficient_data）
2. 年度 EPS 连续增长（过去 3 年无亏损年，A 维度）
3. ROE ≥ 17%
4. 相对强度排名：过去 52 周涨幅相对全市场排名前 20%（L 维度代理指标）
5. 大盘状态：如果沪深 300 周线 EMA 下降，输出警告（不阻止扫描）
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_MIN_EPS_GROWTH = 0.18   # C 维度：当季 EPS 同比增速最低阈值
_MIN_ROE = 0.17           # ROE 最低阈值
_RS_RANK_THRESHOLD = 0.20  # 相对强度排名：前 20%


def _eps_yoy_growth(current_eps: float, prior_eps: float) -> float | None:
    """计算 EPS 同比增速（YoY）。

    去年同期 EPS ≤ 0 时返回 None（无法计算有意义的增速）。
    """
    if prior_eps <= 0:
        return None
    return (current_eps - prior_eps) / abs(prior_eps)


def _annual_eps_continuous_growth(annual_eps: list[float], years: int = 3) -> bool:
    """检查过去 N 年 EPS 是否连续增长（无亏损年）。

    annual_eps: 按时间升序排列（最早在前）
    """
    if len(annual_eps) < years:
        return False
    recent = annual_eps[-years:]
    # 每年均为正值
    if any(e <= 0 for e in recent):
        return False
    # 逐年增长
    return all(recent[i] < recent[i + 1] for i in range(len(recent) - 1))


def _compute_relative_strength(
    symbols: list[str],
    bars_df: "pd.DataFrame",
    *,
    lookback_days: int = 252,
) -> dict[str, float]:
    """计算每只股票过去 52 周的涨幅，返回 {symbol: return_pct}。"""
    import pandas as pd

    result = {}
    for sym in symbols:
        sym_bars = bars_df[bars_df["symbol"] == sym].sort_values("ts")
        if len(sym_bars) < lookback_days // 2:
            continue
        start_price = sym_bars["close"].iloc[0]
        end_price = sym_bars["close"].iloc[-1]
        if start_price > 0:
            result[sym] = (end_price - start_price) / start_price
    return result


def scan_canslim(
    symbols: list[str],
    bars_df: "pd.DataFrame",
    *,
    scan_date: date,
    data_root: Path,
    top_n: int = 30,
) -> dict[str, Any]:
    """对给定符号列表运行 CANSLIM 基本面筛选。

    Args:
        symbols: 已经过成交额过滤的候选符号
        bars_df: 所有符号的日线数据 DataFrame
        scan_date: 扫描日期
        data_root: 项目数据根目录（用于读取 fundamental JSON）
        top_n: 输出前 N 只

    Returns:
        符合 scan output 格式的 dict（不含 filtered_out，由调用方合并）
    """
    from .common import load_fundamental

    candidates = []
    insufficient_data = 0
    no_signal = 0

    # 计算全市场相对强度（用于 L 维度排名）
    rs_map = _compute_relative_strength(symbols, bars_df)
    if rs_map:
        all_returns = sorted(rs_map.values(), reverse=True)
        rs_threshold_idx = int(len(all_returns) * _RS_RANK_THRESHOLD)
        rs_threshold = all_returns[rs_threshold_idx] if rs_threshold_idx < len(all_returns) else 0.0
    else:
        rs_threshold = 0.0

    for sym in symbols:
        fund = load_fundamental(data_root, sym)
        if fund is None:
            insufficient_data += 1
            continue

        # ── C 维度：当季 EPS 同比增速 ≥ 18% ──
        per_share = fund.get("per_share", {})
        quarterly_eps = per_share.get("quarterly_eps", [])
        if len(quarterly_eps) < 5:  # 需要至少 5 个季度（当季 + 去年同期）
            insufficient_data += 1
            continue

        # quarterly_eps 按时间升序，最后一个是最新季度
        current_eps = quarterly_eps[-1].get("eps", 0)
        prior_year_eps = quarterly_eps[-5].get("eps", 0)  # 去年同期（4个季度前）

        growth = _eps_yoy_growth(current_eps, prior_year_eps)
        if growth is None:
            # 去年同期 EPS ≤ 0，无法计算
            insufficient_data += 1
            continue

        if growth < _MIN_EPS_GROWTH:
            no_signal += 1
            continue

        # ── A 维度：年度 EPS 连续增长 ──
        annual_eps_list = [
            item.get("eps", 0)
            for item in per_share.get("annual_eps", [])
        ]
        if not _annual_eps_continuous_growth(annual_eps_list, years=3):
            no_signal += 1
            continue

        # ── ROE ≥ 17% ──
        profitability = fund.get("profitability", {})
        roe_history = profitability.get("roe", [])
        latest_roe = roe_history[-1].get("value", 0) if roe_history else 0
        if latest_roe < _MIN_ROE:
            no_signal += 1
            continue

        # ── L 维度：相对强度前 20% ──
        sym_return = rs_map.get(sym)
        rs_ok = sym_return is not None and sym_return >= rs_threshold

        # 评分：通过的条件越多分越高
        score = 0.0
        score += 3  # C 维度（最重要）
        score += 2  # A 维度
        score += 2  # ROE
        if rs_ok:
            score += 2  # L 维度
        # EPS 增速越高加分
        if growth >= 0.40:
            score += 1

        candidates.append({
            "symbol": sym,
            "rank": 0,
            "score": round(score, 1),
            "signals": {
                "eps_growth_yoy": round(growth, 3),
                "annual_eps_continuous": True,
                "roe": round(latest_roe, 3),
                "relative_strength_top20pct": rs_ok,
            },
            "next_step": "运行 canslim-system 做完整 CANSLIM 七维度分析",
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
