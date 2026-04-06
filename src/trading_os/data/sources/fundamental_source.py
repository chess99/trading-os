"""基本面财务数据源。

提供 A 股财务数据，用于 fundamental-research skill 的深度分析。

数据来源优先级：
1. BaoStock（季度财务指标，免费，国内直连）
2. AKShare（完整财报，免费，需代理）

覆盖数据：
- 盈利能力：ROE、净利率、毛利率、净利润、EPS
- 成长能力：净利润同比增长、EPS增长、净资产增长
- 偿债能力：资产负债率、流动比率
- 运营能力：资产周转率
- 股票基本信息：上市日期、股本
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

log = logging.getLogger(__name__)

# BaoStock 交易所前缀
_BS_PREFIX = {"SSE": "sh", "SZSE": "sz"}


def _to_bs_code(symbol_id: str) -> str:
    """SSE:600000 → sh.600000"""
    parts = symbol_id.split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid symbol: {symbol_id}")
    exch, ticker = parts
    prefix = _BS_PREFIX.get(exch.upper())
    if not prefix:
        raise ValueError(f"Unsupported exchange: {exch}")
    return f"{prefix}.{ticker}"


def get_financial_summary(symbol_id: str, years: int = 5) -> dict[str, Any]:
    """获取股票的财务摘要，用于 fundamental-research 分析。

    返回格式化的财务数据字典，直接可以注入到 LLM prompt 中。

    Args:
        symbol_id:  规范化股票代码，如 "SSE:600519"
        years:      获取最近几年的数据（默认5年）

    Returns:
        包含以下键的字典：
        - symbol: 股票代码
        - name: 股票名称
        - ipo_date: 上市日期
        - profitability: 盈利能力（ROE、净利率等）历史数据
        - growth: 成长能力（净利润增速等）历史数据
        - solvency: 偿债能力（资产负债率等）
        - per_share: 每股指标（EPS等）
        - summary_text: 格式化的文字摘要，可直接插入 prompt
    """
    try:
        import baostock as bs
        import pandas as pd
    except ImportError as e:
        raise RuntimeError("baostock required: pip install baostock") from e

    bs_code = _to_bs_code(symbol_id)
    result: dict[str, Any] = {
        "symbol": symbol_id,
        "name": "",
        "ipo_date": "",
        "profitability": [],
        "growth": [],
        "solvency": [],
        "per_share": [],
        "error": None,
    }

    lg = bs.login()
    if lg.error_code != "0":
        result["error"] = f"BaoStock 登录失败: {lg.error_msg}"
        return result

    try:
        # 1. 股票基本信息
        rs = bs.query_stock_basic(code=bs_code)
        if rs.error_code == "0" and rs.next():
            row = rs.get_row_data()
            result["name"] = row[1] if len(row) > 1 else ""
            result["ipo_date"] = row[2] if len(row) > 2 else ""

        # 2. 获取最近 N 年的季度财务数据
        current_year = datetime.now().year
        profit_rows, growth_rows, solvency_rows = [], [], []

        for year in range(current_year - years + 1, current_year + 1):
            for quarter in [4, 3, 2, 1]:
                # 盈利能力
                rs = bs.query_profit_data(code=bs_code, year=year, quarter=quarter)
                if rs.error_code == "0":
                    while rs.next():
                        r = rs.get_row_data()
                        profit_rows.append({
                            "period": r[2],          # statDate
                            "pub_date": r[1],         # pubDate
                            "roe": _safe_float(r[3]),        # roeAvg
                            "net_margin": _safe_float(r[4]),  # npMargin
                            "gross_margin": _safe_float(r[5]),# gpMargin
                            "net_profit": _safe_float(r[6]),  # netProfit（元）
                            "eps_ttm": _safe_float(r[7]),     # epsTTM
                        })

                # 成长能力
                rs = bs.query_growth_data(code=bs_code, year=year, quarter=quarter)
                if rs.error_code == "0":
                    while rs.next():
                        r = rs.get_row_data()
                        growth_rows.append({
                            "period": r[2],
                            "yoy_equity": _safe_float(r[3]),   # 净资产同比增长
                            "yoy_asset": _safe_float(r[4]),    # 总资产同比增长
                            "yoy_net_income": _safe_float(r[5]),# 净利润同比增长
                            "yoy_eps": _safe_float(r[6]),      # EPS同比增长
                        })

                # 偿债能力
                rs = bs.query_balance_data(code=bs_code, year=year, quarter=quarter)
                if rs.error_code == "0":
                    while rs.next():
                        r = rs.get_row_data()
                        solvency_rows.append({
                            "period": r[2],
                            "current_ratio": _safe_float(r[3]),
                            "quick_ratio": _safe_float(r[4]),
                            "liability_to_asset": _safe_float(r[6]),  # 资产负债率
                            "asset_to_equity": _safe_float(r[7]),     # 权益乘数
                        })

        # 去重并排序（按期间降序，最新在前）
        result["profitability"] = _dedup_by_period(profit_rows)[:years * 4]
        result["growth"] = _dedup_by_period(growth_rows)[:years * 4]
        result["solvency"] = _dedup_by_period(solvency_rows)[:years * 4]

        # 3. 生成文字摘要
        result["summary_text"] = _format_summary(result)

    except Exception as e:
        log.error("财务数据获取失败 %s: %s", symbol_id, e)
        result["error"] = str(e)
    finally:
        bs.logout()

    return result


def _safe_float(v: str) -> float | None:
    """安全转换字符串为 float，空字符串返回 None。"""
    if not v or v.strip() == "":
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _dedup_by_period(rows: list[dict]) -> list[dict]:
    """按 period 去重，保留最新数据，并按 period 降序排序。"""
    seen = {}
    for row in rows:
        p = row.get("period", "")
        if p and p not in seen:
            seen[p] = row
    return sorted(seen.values(), key=lambda x: x.get("period", ""), reverse=True)


def _fmt(v: float | None, fmt: str = ".2%", suffix: str = "") -> str:
    if v is None:
        return "N/A"
    try:
        return format(v, fmt) + suffix
    except (ValueError, TypeError):
        return "N/A"


def _format_summary(data: dict) -> str:
    """格式化财务摘要，供 LLM prompt 直接使用。"""
    lines = []
    name = data.get("name", "")
    symbol = data.get("symbol", "")
    ipo = data.get("ipo_date", "")

    lines.append(f"【财务数据摘要】{symbol} {name}")
    if ipo:
        lines.append(f"上市日期：{ipo}")
    lines.append("")

    # 盈利能力（最近8个季度）
    profit = data.get("profitability", [])[:8]
    if profit:
        lines.append("▌ 盈利能力（季度，最新在前）")
        lines.append(f"{'期间':<12} {'ROE':>8} {'净利率':>8} {'毛利率':>8} {'净利润(亿)':>12} {'EPS(TTM)':>10}")
        lines.append("-" * 60)
        for r in profit:
            net_profit_yi = (r["net_profit"] / 1e8) if r["net_profit"] is not None else None
            lines.append(
                f"{r['period']:<12} "
                f"{_fmt(r['roe'], '.2%'):>8} "
                f"{_fmt(r['net_margin'], '.2%'):>8} "
                f"{_fmt(r['gross_margin'], '.2%'):>8} "
                f"{_fmt(net_profit_yi, '.2f', '亿'):>12} "
                f"{_fmt(r['eps_ttm'], '.3f'):>10}"
            )
        lines.append("")

    # 成长能力（最近4个季度）
    growth = data.get("growth", [])[:4]
    if growth:
        lines.append("▌ 成长能力（同比增长率）")
        lines.append(f"{'期间':<12} {'净利润增速':>12} {'EPS增速':>10} {'净资产增速':>12}")
        lines.append("-" * 50)
        for r in growth:
            lines.append(
                f"{r['period']:<12} "
                f"{_fmt(r['yoy_net_income'], '.2%'):>12} "
                f"{_fmt(r['yoy_eps'], '.2%'):>10} "
                f"{_fmt(r['yoy_equity'], '.2%'):>12}"
            )
        lines.append("")

    # 偿债能力（最近4个季度）
    solvency = data.get("solvency", [])[:4]
    if solvency:
        lines.append("▌ 偿债能力")
        lines.append(f"{'期间':<12} {'资产负债率':>12} {'流动比率':>10} {'权益乘数':>10}")
        lines.append("-" * 48)
        for r in solvency:
            lines.append(
                f"{r['period']:<12} "
                f"{_fmt(r['liability_to_asset'], '.2%'):>12} "
                f"{_fmt(r['current_ratio'], '.2f'):>10} "
                f"{_fmt(r['asset_to_equity'], '.2f'):>10}"
            )

    if data.get("error"):
        lines.append(f"\n⚠️  数据获取部分失败: {data['error']}")

    return "\n".join(lines)
