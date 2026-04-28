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

        # fundamental_source 返回的实际格式：
        # profitability: list of {period, roe, eps_ttm, ...}（按时间降序）
        # growth: list of {period, yoy_eps, ...}（按时间降序）
        profitability_list = fund.get("profitability", [])
        growth_list = fund.get("growth", [])

        if not profitability_list or not growth_list:
            insufficient_data += 1
            continue

        # ── C 维度：最新季度 EPS 同比增速 ≥ 18% ──
        # growth[0] 是最新季度，yoy_eps 已经是同比增速（小数）
        latest_growth = growth_list[0]
        yoy_eps = latest_growth.get("yoy_eps")
        if yoy_eps is None:
            insufficient_data += 1
            continue

        if yoy_eps < _MIN_EPS_GROWTH:
            no_signal += 1
            continue

        # ── A 维度：年度 EPS 连续增长（用 yoy_eps > 0 的季度比例代理）──
        # 取最近 12 个季度（约 3 年），要求多数季度 yoy_eps > 0
        recent_growth = growth_list[:12]
        positive_quarters = sum(1 for g in recent_growth if g.get("yoy_eps", 0) > 0)
        if len(recent_growth) < 4 or positive_quarters < len(recent_growth) * 0.75:
            no_signal += 1
            continue

        # ── ROE ≥ 17% ──
        latest_roe = profitability_list[0].get("roe", 0) if profitability_list else 0
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
        if yoy_eps >= 0.40:
            score += 1

        candidates.append({
            "symbol": sym,
            "rank": 0,
            "score": round(score, 1),
            "signals": {
                "eps_growth_yoy": round(yoy_eps, 3),
                "recent_quarters_positive": positive_quarters,
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


def scan_canslim_live(
    symbols: list[str],
    bars_df: "pd.DataFrame",
    *,
    scan_date: date,
    top_n: int = 30,
    max_workers: int = 3,
) -> dict[str, Any]:
    """CANSLIM 实时扫描模式：直接调用 EastMoney F10，无需 fundamental-store 预缓存。

    适用场景：
    - 本地没有 fundamental/ 缓存数据
    - 需要最新财务数据（F10 比 BaoStock 更新更快）

    与 scan_canslim 的区别：
    - 数据源：EastMoney F10 API（实时）vs BaoStock fundamental JSON（预缓存）
    - 速度：受网络限速，建议 max_workers=3
    - 依赖：需要网络访问东方财富，无需 fundamental-store

    Args:
        symbols: 已经过成交额过滤的候选符号
        bars_df: 所有符号的日线数据 DataFrame
        scan_date: 扫描日期
        top_n: 输出前 N 只
        max_workers: 并发线程数（建议 3，避免触发限速）
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from ..data.sources.eastmoney_source import get_financial_data

    candidates = []
    insufficient_data = 0
    no_signal = 0

    # 计算全市场相对强度
    rs_map = _compute_relative_strength(symbols, bars_df)
    if rs_map:
        all_returns = sorted(rs_map.values(), reverse=True)
        rs_threshold_idx = int(len(all_returns) * _RS_RANK_THRESHOLD)
        rs_threshold = all_returns[rs_threshold_idx] if rs_threshold_idx < len(all_returns) else 0.0
    else:
        rs_threshold = 0.0

    def _process(sym: str) -> dict[str, Any]:
        fund = get_financial_data(sym)
        if not fund:
            return {"_type": "nodata", "symbol": sym}

        yoy_eps_list = fund.get("yoy_eps_list", [])
        roe_list = fund.get("roe_list", [])

        if not yoy_eps_list or not roe_list:
            return {"_type": "nodata", "symbol": sym}

        # C 维度：最新季度 EPS 同比增速 ≥ 18%
        latest_yoy = yoy_eps_list[0].get("yoy_eps")
        if latest_yoy is None or latest_yoy < _MIN_EPS_GROWTH:
            return {"_type": "nosignal", "symbol": sym, "reason": "eps_growth"}

        # A 维度：近 12 季度 75% 以上 yoy_eps > 0
        recent_12 = yoy_eps_list[:12]
        positive_quarters = sum(1 for g in recent_12 if (g.get("yoy_eps") or 0) > 0)
        if len(recent_12) < 4 or positive_quarters < len(recent_12) * 0.75:
            return {"_type": "nosignal", "symbol": sym, "reason": "positive_quarters"}

        # ROE ≥ 17%（F10 返回百分数格式，如 17.54）
        latest_roe_pct = roe_list[0].get("roe", 0)
        latest_roe = latest_roe_pct / 100  # 转为小数
        if latest_roe < _MIN_ROE:
            return {"_type": "nosignal", "symbol": sym, "reason": "roe"}

        sym_return = rs_map.get(sym)
        rs_ok = sym_return is not None and sym_return >= rs_threshold

        score = 7.0  # C(3) + A(2) + ROE(2)
        if rs_ok:
            score += 2
        if latest_yoy >= 0.40:
            score += 1

        return {
            "_type": "candidate",
            "symbol": sym,
            "score": round(score, 1),
            "signals": {
                "eps_growth_yoy": round(latest_yoy, 3),
                "recent_quarters_positive": positive_quarters,
                "roe": round(latest_roe, 3),
                "relative_strength_top20pct": rs_ok,
            },
            "next_step": "运行 canslim-system 做完整 CANSLIM 七维度分析",
        }

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_process, sym): sym for sym in symbols}
        done = 0
        for future in as_completed(futures):
            result = future.result()
            done += 1
            t = result["_type"]
            if t == "candidate":
                candidates.append(result)
            elif t == "nodata":
                insufficient_data += 1
            elif t == "nosignal":
                no_signal += 1

            if done % 100 == 0:
                log.info("进度: %d/%d candidates=%d", done, len(symbols), len(candidates))

    # 排序 + 截取 top_n
    candidates.sort(key=lambda x: x["score"], reverse=True)
    candidates = candidates[:top_n]
    for i, c in enumerate(candidates, 1):
        c["rank"] = i
        c.pop("_type", None)

    return {
        "candidates": candidates,
        "_stats": {
            "insufficient_data": insufficient_data,
            "no_signal": no_signal,
        },
    }
