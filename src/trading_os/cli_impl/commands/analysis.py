from __future__ import annotations

import argparse
import sys


def _cmd_fundamental(ns: argparse.Namespace) -> int:
    from ...data.sources.fundamental_source import get_financial_summary

    symbols = [s.strip() for s in ns.symbols.split(",")]
    years = int(ns.years)
    for sym in symbols:
        data = get_financial_summary(sym, years=years)
        if data.get("error") and not data.get("profitability"):
            print(f"获取失败 {sym}: {data['error']}", file=sys.stderr)
            continue
        print(data["summary_text"])
        print()
    return 0


def _cmd_valuation(ns: argparse.Namespace) -> int:
    from ...data.sources.valuation_source import calculate_valuation

    symbols = [s.strip() for s in ns.symbols.split(",")]
    for sym in symbols:
        result = calculate_valuation(
            sym,
            cost_of_capital=float(ns.cost_of_capital),
            moat=ns.moat,
            sustainable_profit_years=int(ns.epv_years),
            growth_rate=float(ns.growth_rate) if ns.growth_rate else None,
            growth_years=int(ns.growth_years),
            terminal_pe=float(ns.terminal_pe),
            discount_rate=float(ns.discount_rate) if ns.discount_rate else None,
            peg_target=float(ns.peg_target),
            growth_cagr=float(ns.growth_cagr) if ns.growth_cagr else None,
        )
        if result.get("error"):
            print(f"估值失败 {sym}: {result['error']}", file=sys.stderr)
            continue
        print(result["summary_text"])
        print()
    return 0


def _cmd_valuation_sensitivity(ns: argparse.Namespace) -> int:
    from ...data.sources.valuation_source import calculate_sensitivity

    growth_rates = [float(x) for x in ns.growth_rates.split(",")] if ns.growth_rates else None
    terminal_pes = [float(x) for x in ns.terminal_pes.split(",")] if ns.terminal_pes else None
    costs = [float(x) for x in ns.costs_of_capital.split(",")] if ns.costs_of_capital else None
    profits = [float(x) for x in ns.sustainable_profits.split(",")] if ns.sustainable_profits else None

    result = calculate_sensitivity(
        ns.symbol,
        method=ns.method,
        base_profit_bn=float(ns.base_profit),
        growth_rates=growth_rates,
        terminal_pes=terminal_pes,
        growth_years=int(ns.growth_years),
        discount_rate=float(ns.discount_rate),
        sustainable_profits_bn=profits,
        costs_of_capital=costs,
    )
    print(result["summary_text"])
    return 0


def _cmd_valuation_sotp(ns: argparse.Namespace) -> int:
    import json
    from ...data.sources.valuation_source import calculate_sotp

    try:
        with open(ns.segments_file) as f:
            segments = json.load(f)
    except Exception as e:
        print(f"读取分部参数失败: {e}", file=sys.stderr)
        print("segments_file 应为 JSON 数组，每项包含 name/profit_bn/method/multiple/note 等字段", file=sys.stderr)
        return 1

    result = calculate_sotp(ns.symbol, segments)
    print(result["summary_text"])
    return 0


def _cmd_52week(ns: argparse.Namespace) -> int:
    from ...data.sources.fundamental_source import get_52week_stats

    symbols = [s.strip() for s in ns.symbols.split(",")]
    for sym in symbols:
        result = get_52week_stats(sym)
        print(result["summary_text"])
        print()
    return 0


def _cmd_market_breadth(ns: argparse.Namespace) -> int:
    from ...data.sources.fundamental_source import get_market_breadth

    result = get_market_breadth(ns.index, lookback_days=int(ns.days))
    print(result["summary_text"])
    return 0
