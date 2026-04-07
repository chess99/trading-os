"""估值计算模块。

所有公式透明、可复现，参数由调用方（AI 或人工）显式传入，不写死。

支持的方法：
- EPV：格林沃尔德盈利能力价值（无成长假设，永续折现）
- DCF：5年期简化 DCF（成长股适用）
- PEG：彼得·林奇 PEG 法

资本成本选择指引（由 AI 根据护城河分析结果决定后传入）：
  低风险（宽护城河，公用事业/消费品）→ 6%~8%，取 7%
  中风险（窄护城河，服务业/轻工制造）→ 8%~10%，取 9%
  高风险（无护城河，周期/代工/大宗）  → 11%~13%，取 12%
"""
from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)


def calculate_valuation(
    symbol_id: str,
    *,
    # ── 由 AI 根据护城河分析结果决定后传入 ──
    cost_of_capital: float,          # 资本成本，如 0.09
    moat: str = "narrow",            # "wide" / "narrow" / "none"
    # ── EPV 参数 ──
    sustainable_profit_years: int = 3,  # 用最近几年均值作为可持续利润
    # ── DCF 参数（成长股）──
    growth_rate: float | None = None,   # 预期增速，如 0.30；None 则跳过 DCF
    growth_years: int = 5,              # 高增速持续年数
    terminal_pe: float = 15.0,          # 终止 PE（成熟期合理估值）
    discount_rate: float | None = None, # DCF 折现率；None 则用 cost_of_capital + 0.03
    # ── PEG 参数 ──
    peg_target: float = 1.0,            # 目标 PEG，默认 1.0
    growth_cagr: float | None = None,   # 用于 PEG 的增速 CAGR；None 则从财务数据推算
) -> dict[str, Any]:
    """计算股票内在价值，返回各方法结果和格式化报告。

    Args:
        symbol_id:              规范化股票代码，如 "SSE:601138"
        cost_of_capital:        资本成本（由 AI 根据护城河判断后传入）
        moat:                   护城河宽度，影响安全边际要求
        sustainable_profit_years: EPV 使用最近 N 年均值利润
        growth_rate:            DCF 增速假设（None = 跳过 DCF）
        growth_years:           高增速持续年数
        terminal_pe:            终止 PE
        discount_rate:          DCF 折现率（None = cost_of_capital + 3%）
        peg_target:             目标 PEG
        growth_cagr:            PEG 使用的增速（None = 从财务数据推算）

    Returns:
        包含各方法估值结果和 summary_text 的字典
    """
    from .fundamental_source import get_financial_summary

    result: dict[str, Any] = {
        "symbol": symbol_id,
        "inputs": {},
        "epv": {},
        "dcf": {},
        "peg": {},
        "current_price": None,
        "summary_text": "",
        "error": None,
    }

    # ── 1. 获取财务数据 ──
    fin = get_financial_summary(symbol_id, years=max(sustainable_profit_years + 1, 5))
    if fin.get("error") and not fin.get("profitability"):
        result["error"] = f"财务数据获取失败: {fin['error']}"
        result["summary_text"] = result["error"]
        return result

    profits = [r["net_profit"] for r in fin.get("profitability", [])
               if r.get("net_profit") and r["period"].endswith("12-31")]
    profits = [p for p in profits if p is not None]

    if len(profits) < 1:
        result["error"] = "年度利润数据不足"
        result["summary_text"] = result["error"]
        return result

    latest_eps = fin["profitability"][0].get("eps_ttm") if fin.get("profitability") else None
    shares = None
    if latest_eps and profits:
        shares = profits[0] / latest_eps  # 总股本（股，profits 单位为元）

    # ── 2. 获取当前股价 ──
    current_price = _get_current_price(symbol_id)
    result["current_price"] = current_price
    market_cap = current_price * shares if (current_price and shares) else None  # 元

    # ── 3. 记录输入参数（让人看到 AI 用了什么假设）──
    result["inputs"] = {
        "cost_of_capital": cost_of_capital,
        "moat": moat,
        "sustainable_profit_years": sustainable_profit_years,
        "growth_rate": growth_rate,
        "growth_years": growth_years,
        "terminal_pe": terminal_pe,
        "discount_rate": discount_rate or cost_of_capital + 0.03,
        "peg_target": peg_target,
        "latest_profit_bn": profits[0] / 1e8 if profits else None,
        "shares_bn": shares / 1e8 if shares else None,   # 转换为亿股显示
        "shares_raw": shares,                             # 原始股数（用于计算）
        "market_cap_bn": market_cap / 1e8 if market_cap else None,
    }

    # ── 4. EPV ──
    n = min(sustainable_profit_years, len(profits))
    avg_profit = sum(profits[:n]) / n
    epv_total = avg_profit / cost_of_capital
    epv_per_share = epv_total / shares if shares else None  # 元/股

    result["epv"] = {
        "avg_profit_bn": avg_profit / 1e8,
        "years_used": n,
        "epv_total_bn": epv_total / 1e8,
        "epv_per_share": epv_per_share,
        "formula": f"{avg_profit/1e8:.1f}亿 / {cost_of_capital:.0%}",
    }

    # ── 5. DCF（仅当提供增速时）──
    if growth_rate is not None and latest_eps and shares:
        dr = discount_rate if discount_rate else cost_of_capital + 0.03
        latest_profit = profits[0]
        profit_terminal = latest_profit * (1 + growth_rate) ** growth_years
        eps_terminal = profit_terminal / shares
        price_terminal = eps_terminal * terminal_pe
        dcf_price = price_terminal / (1 + dr) ** growth_years

        result["dcf"] = {
            "growth_rate": growth_rate,
            "growth_years": growth_years,
            "terminal_pe": terminal_pe,
            "discount_rate": dr,
            "profit_terminal_bn": profit_terminal / 1e8,
            "eps_terminal": eps_terminal,
            "price_terminal": price_terminal,
            "dcf_per_share": dcf_price,
            "formula": (
                f"{latest_profit/1e8:.0f}亿 × (1+{growth_rate:.0%})^{growth_years}"
                f" = {profit_terminal/1e8:.0f}亿"
                f" → EPS {eps_terminal:.2f} × {terminal_pe}x PE = {price_terminal:.1f}元"
                f" → 折现@{dr:.0%} = {dcf_price:.1f}元"
            ),
        }

    # ── 6. PEG ──
    if latest_eps:
        # 推算 CAGR：用最近2年利润增速均值，或外部传入
        if growth_cagr is None and len(profits) >= 2:
            import math
            years_span = min(len(profits) - 1, 3)
            if profits[years_span] > 0:
                growth_cagr = (profits[0] / profits[years_span]) ** (1 / years_span) - 1
        if growth_cagr and growth_cagr > 0:
            fair_pe = growth_cagr * 100 * peg_target
            peg_price = latest_eps * fair_pe
            actual_peg = (current_price / latest_eps / (growth_cagr * 100)) if current_price else None
            result["peg"] = {
                "growth_cagr": growth_cagr,
                "fair_pe": fair_pe,
                "peg_price": peg_price,
                "actual_peg": actual_peg,
                "formula": f"CAGR {growth_cagr:.1%} × 100 × PEG{peg_target} = {fair_pe:.0f}x PE → {latest_eps:.3f} × {fair_pe:.0f} = {peg_price:.1f}元",
            }

    # ── 7. 安全边际要求 ──
    margin_required = {"wide": 0.25, "narrow": 0.40, "none": 0.50}[moat]

    # ── 8. 格式化输出 ──
    result["summary_text"] = _format_summary(result, current_price, margin_required)
    return result


def _get_current_price(symbol_id: str) -> float | None:
    """从本地 DataLake 获取最新收盘价。"""
    try:
        from ..lake import LocalDataLake
        from ..schema import Adjustment, Exchange, Timeframe
        from pathlib import Path
        import sys

        # 找项目根目录（src/trading_os/data/sources → 上4级）
        here = Path(__file__).resolve()
        root = here.parents[4]

        parts = symbol_id.split(":")
        exch = Exchange(parts[0])
        lake = LocalDataLake(root / "data")
        df = lake.query_bars(
            symbols=[symbol_id], exchange=exch,
            timeframe=Timeframe.D1, adjustment=Adjustment.QFQ,
        )
        if not df.empty:
            return float(df.sort_values("ts").iloc[-1]["close"])
    except Exception as e:
        log.warning("获取当前价格失败: %s", e)
    return None


def _format_summary(result: dict, current_price: float | None, margin_required: float) -> str:
    inp = result["inputs"]
    lines = [
        f"【估值计算】{result['symbol']}",
        f"",
        f"▌ 输入参数（由 AI 根据护城河分析决定）",
        f"  资本成本:     {inp['cost_of_capital']:.0%}  ({_moat_label(inp['moat'])})",
        f"  护城河:       {inp['moat']}",
        f"  最新利润:     {inp['latest_profit_bn']:.1f}亿元",
        f"  总股本:       {inp['shares_bn']:.1f}亿股" if inp['shares_bn'] else "  总股本:       未知",
        f"  当前市值:     {inp['market_cap_bn']:.0f}亿元" if inp.get('market_cap_bn') else "",
        f"  当前股价:     {current_price:.2f}元" if current_price else "  当前股价:     未知",
        f"",
    ]

    # EPV
    epv = result.get("epv", {})
    if epv:
        lines += [
            f"▌ EPV（格林沃尔德，无成长假设）",
            f"  公式: {epv['avg_profit_bn']:.1f}亿（近{epv['years_used']}年均值）/ {inp['cost_of_capital']:.0%}",
            f"  EPV = {epv['epv_total_bn']:.0f}亿 = {epv['epv_per_share']:.1f}元/股" if epv.get('epv_per_share') else f"  EPV = {epv['epv_total_bn']:.0f}亿",
            f"  含义: 若利润不再增长，按{inp['cost_of_capital']:.0%}折现的合理价值",
            f"",
        ]

    # DCF
    dcf = result.get("dcf", {})
    if dcf:
        lines += [
            f"▌ DCF（5年成长期）",
            f"  公式: {dcf['formula']}",
            f"  DCF 价值 = {dcf['dcf_per_share']:.1f}元/股",
            f"  假设: {dcf['growth_rate']:.0%}/年增速持续{dcf['growth_years']}年，终止PE {dcf['terminal_pe']}x，折现率{dcf['discount_rate']:.0%}",
            f"",
        ]

    # PEG
    peg = result.get("peg", {})
    if peg:
        lines += [
            f"▌ PEG 法（林奇）",
            f"  公式: {peg['formula']}",
            f"  PEG 合理价 = {peg['peg_price']:.1f}元/股",
            f"  当前实际 PEG = {peg['actual_peg']:.2f}" if peg.get('actual_peg') else "",
            f"",
        ]

    # 安全边际汇总
    if current_price:
        lines.append(f"▌ 安全边际（护城河={inp['moat']}，要求折扣≥{margin_required:.0%}）")
        for method, key, price_key in [
            ("EPV 保守", "epv", "epv_per_share"),
            ("DCF 乐观", "dcf", "dcf_per_share"),
            ("PEG", "peg", "peg_price"),
        ]:
            val = result.get(key, {}).get(price_key)
            if val:
                discount = (val - current_price) / val
                required_buy = val * (1 - margin_required)
                status = "✅ 有安全边际" if current_price <= required_buy else "❌ 无安全边际"
                lines.append(f"  {method}: 合理值{val:.1f}元，买入线{required_buy:.1f}元，当前{current_price:.2f}元 {status}")
        lines.append("")

    # 市场隐含假设反推
    market_cap_bn = inp.get("market_cap_bn")
    if market_cap_bn and inp.get("shares_bn"):
        implied_profit = market_cap_bn * inp["cost_of_capital"]
        latest = inp.get("latest_profit_bn", 1)
        multiple = implied_profit / latest if latest else None
        lines += [
            f"▌ 市场隐含假设（反推）",
            f"  市值{market_cap_bn:.0f}亿 × {inp['cost_of_capital']:.0%} = 隐含稳态利润{implied_profit:.0f}亿",
            f"  = 当前利润{latest:.0f}亿的{multiple:.1f}倍" if multiple else "",
            f"  含义: 市场定价已包含利润继续大幅增长的预期",
        ]

    return "\n".join(l for l in lines if l is not None)


def _moat_label(moat: str) -> str:
    return {"wide": "低风险，宽护城河", "narrow": "中风险，窄护城河", "none": "高风险，无护城河"}.get(moat, moat)
