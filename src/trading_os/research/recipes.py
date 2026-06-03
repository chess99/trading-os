from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import pandas as pd

from ..journal.event_log import EventLog
from ..risk.manager import RiskManager
from .datahub import DataHub
from .store import ResearchRun


@dataclass(frozen=True, slots=True)
class RecipeResult:
    recipe: str
    run: ResearchRun
    manifest: dict[str, Any]
    report: str
    candidates: list[dict[str, Any]]
    filtered_out: dict[str, int]


def run_canslim_screen(
    hub: DataHub,
    *,
    as_of: date,
    top_n: int = 30,
    min_turnover: float = 10_000_000.0,
) -> RecipeResult:
    run = hub.store.start_run(
        "canslim_screen",
        inputs={"as_of": as_of.isoformat(), "top_n": top_n, "min_turnover": min_turnover},
    )
    trace = [
        "# canslim_screen trace",
        f"- as_of: `{as_of.isoformat()}`",
        "- load universe snapshot",
    ]
    universe = hub.get_universe(as_of, policy="cache_first")
    quotes = hub.get_quote_snapshot(as_of, policy="cache_first")
    trace.append("- load quote snapshot")

    filtered = {"st_or_inactive": 0, "low_turnover": 0, "insufficient_data": 0, "no_signal": 0}
    if universe.empty or quotes.empty:
        return _finish_result(hub, run, "canslim_screen", trace, [], filtered)

    universe = universe.copy()
    universe["is_st"] = universe.get("is_st", False).astype(bool)
    universe["is_active"] = universe.get("is_active", True).astype(bool)
    allowed = universe[(~universe["is_st"]) & (universe["is_active"])]
    filtered["st_or_inactive"] = len(universe) - len(allowed)

    merged = allowed.merge(quotes, on="symbol", how="inner", suffixes=("", "_quote"))
    amount = pd.to_numeric(merged.get("amount", 0), errors="coerce").fillna(0)
    liquid = merged[amount >= min_turnover].copy()
    filtered["low_turnover"] = len(merged) - len(liquid)
    symbols = liquid["symbol"].astype(str).tolist()

    fundamentals = hub.get_fundamentals(symbols, as_of=as_of, policy="cache_first")
    if fundamentals.empty:
        filtered["insufficient_data"] = len(symbols)
        return _finish_result(hub, run, "canslim_screen", trace, [], filtered)

    fund_by_symbol = (
        fundamentals.sort_values(["as_of", "fetched_at"]).groupby("symbol", as_index=False).tail(1)
    )
    quarter_history_missing = _core_pass_symbols_missing_quarter_history(fund_by_symbol, symbols)
    if quarter_history_missing:
        trace.append(
            "- refresh quarterly fundamentals for "
            f"`{len(quarter_history_missing)}` core-pass symbols"
        )
        refreshed = hub.get_fundamentals(
            quarter_history_missing, as_of=as_of, periods=8, policy="refresh"
        )
        if refreshed is not None and not refreshed.empty:
            fundamentals = hub.get_fundamentals(symbols, as_of=as_of, policy="cache_first")
            fund_by_symbol = (
                fundamentals.sort_values(["as_of", "fetched_at"])
                .groupby("symbol", as_index=False)
                .tail(1)
            )

    missing_fundamentals = set(symbols) - set(fund_by_symbol["symbol"].astype(str))
    filtered["insufficient_data"] += len(missing_fundamentals)

    prelim_symbols: list[str] = []
    prelim_rows: list[dict[str, Any]] = []
    for row in fund_by_symbol.to_dict("records"):
        symbol = str(row["symbol"])
        if symbol not in symbols:
            continue
        eps_growth = _float(row.get("eps_growth_yoy"))
        roe = _float(row.get("roe"))
        if eps_growth is None or roe is None:
            filtered["insufficient_data"] += 1
            continue
        if eps_growth < 0.18 or roe < 0.17:
            filtered["no_signal"] += 1
            continue
        positive_quarters = _int_or_none(row.get("positive_quarters"))
        if positive_quarters is not None and positive_quarters < 4:
            filtered["no_signal"] += 1
            continue
        if positive_quarters is None:
            filtered["insufficient_data"] += 1
        prelim_symbols.append(symbol)
        prelim_rows.append(row)

    if not prelim_symbols:
        trace.append("- skip RS bars: no symbols passed core C/A fundamental filters")
        return _finish_result(
            hub,
            run,
            "canslim_screen",
            trace,
            [],
            filtered,
            limitations=["No symbols passed core EPS-growth and ROE filters."],
        )

    rs_limitations: list[str] = []
    try:
        bars = hub.get_bars(
            prelim_symbols,
            start=as_of - timedelta(days=420),
            end=as_of + timedelta(days=1),
            adjustment="qfq",
            policy="lazy_fill",
        )
        trace.append("- lazy-fill missing bars only for fundamentally qualified symbols")
    except Exception as exc:
        bars = pd.DataFrame()
        message = f"RS bars unavailable: {exc}"
        rs_limitations.append(message)
        trace.append(f"- {message}")
    rs = _relative_strength(prelim_symbols, bars)
    rs_threshold = _percentile_threshold(rs, pct=0.20)

    candidates: list[dict[str, Any]] = []
    for row in prelim_rows:
        symbol = str(row["symbol"])
        eps_growth = _float(row.get("eps_growth_yoy"))
        roe = _float(row.get("roe"))
        positive_quarters = _int_or_none(row.get("positive_quarters"))
        missing_fields = []
        if positive_quarters is None:
            missing_fields.append("positive_quarters")
        rs_value = rs.get(symbol)
        if rs_value is None:
            missing_fields.append("relative_strength")
        rs_ok = rs_value is not None and rs_value >= rs_threshold
        strict = not missing_fields and positive_quarters is not None and rs_ok
        score = 7.0 + (2.0 if rs_ok else 0.0) + (1.0 if eps_growth >= 0.40 else 0.0)
        if missing_fields:
            score -= 1.0
        name = ""
        name_rows = merged[merged["symbol"] == symbol]
        if not name_rows.empty:
            name = str(name_rows.iloc[0].get("name", name_rows.iloc[0].get("name_quote", "")))
        candidates.append(
            {
                "symbol": symbol,
                "name": name,
                "score": round(score, 1),
                "classification": (
                    "strict_canslim_candidate" if strict else "provisional_research_queue"
                ),
                "missing_fields": missing_fields,
                "signals": {
                    "eps_growth_yoy": round(eps_growth, 3),
                    "roe": round(roe, 3),
                    "positive_quarters": positive_quarters,
                    "relative_strength": round(rs_value, 4) if rs_value is not None else None,
                    "relative_strength_top20pct": rs_ok,
                },
                "next_step": "run company_research before any trade decision",
            }
        )
    candidates.sort(key=lambda x: x["score"], reverse=True)
    for idx, candidate in enumerate(candidates[:top_n], 1):
        candidate["rank"] = idx
    limitations = []
    limitations = [*rs_limitations]
    if any(candidate["missing_fields"] for candidate in candidates):
        limitations.append(
            "Some candidates are provisional because quarterly continuity fields are missing."
        )
    return _finish_result(
        hub, run, "canslim_screen", trace, candidates[:top_n], filtered, limitations=limitations
    )


def run_company_research(
    hub: DataHub,
    symbol: str,
    *,
    as_of: date,
    template: str = "quality_growth",
    lookback_months: int = 12,
    valuation_mode: str = "pe_band",
) -> RecipeResult:
    run = hub.store.start_run(
        "company_research",
        inputs={
            "symbol": symbol,
            "as_of": as_of.isoformat(),
            "template": template,
            "lookback_months": lookback_months,
            "valuation_mode": valuation_mode,
        },
    )
    quotes = hub.get_quote_snapshot(as_of, policy="cache_first")
    fundamentals = hub.get_fundamentals([symbol], as_of=as_of, policy="cache_first")
    estimates = hub.get_estimates([symbol], as_of=as_of, policy="cache_first")
    news = hub.get_news(
        [symbol], as_of=as_of, lookback_months=lookback_months, policy="cache_first"
    )
    trace = [
        "# company_research trace",
        f"- symbol: `{symbol}`",
        "- load quote, fundamentals, estimates, and news through DataHub",
        "- write structured report with explicit data limitations",
    ]
    tables = {
        "quotes": quotes[quotes["symbol"] == symbol] if not quotes.empty else quotes,
        "fundamentals": fundamentals,
        "estimates": estimates,
        "news": news,
    }
    report = _company_report(symbol, as_of, template, valuation_mode, tables)
    manifest = {
        "steps": [{"name": "load_company_datasets"}, {"name": "write_report"}],
        "outputs": {"report": str(run.path / "report.md")},
        "limitations": [
            "Missing datasets are reported as unavailable; no synthetic investment data is used."
        ],
    }
    hub.store.write_run_artifacts(
        run, manifest=manifest, trace_lines=trace, report=report, tables=tables
    )
    return RecipeResult("company_research", run, manifest, report, [], {})


def run_factor_research(
    hub: DataHub,
    *,
    as_of: date,
    factor_name: str = "momentum_roe",
) -> RecipeResult:
    run = hub.store.start_run(
        "factor_research", inputs={"as_of": as_of.isoformat(), "factor_name": factor_name}
    )
    quotes = hub.get_quote_snapshot(as_of, policy="cache_first")
    fundamentals = hub.get_fundamentals(
        quotes["symbol"].astype(str).tolist() if not quotes.empty else [], as_of=as_of
    )
    table = _factor_table(quotes, fundamentals)
    manifest = {"steps": [{"name": "compute_factor_cross_section"}], "factor_name": factor_name}
    report = f"# Factor Research: {factor_name}\n\nRows: {len(table)}\n"
    hub.store.write_run_artifacts(
        run,
        manifest=manifest,
        trace_lines=["# factor_research trace", "- compute cross-sectional factor table"],
        report=report,
        tables={"factor_scores": table},
    )
    return RecipeResult("factor_research", run, manifest, report, [], {})


def run_backtest_recipe(
    hub: DataHub,
    *,
    start: date,
    end: date,
    strategy_name: str,
) -> RecipeResult:
    run = hub.store.start_run(
        "backtest",
        inputs={"start": start.isoformat(), "end": end.isoformat(), "strategy_name": strategy_name},
    )
    event_log = EventLog(run.path / "events.db")
    event_log.write("SESSION_START", {"strategy": strategy_name, "start": start, "end": end})
    RiskManager().start_of_day(start, 1_000_000.0)
    event_log.write("SESSION_END", {"strategy": strategy_name})
    manifest = {
        "steps": [{"name": "initialize_risk_and_event_log"}],
        "event_log": str(run.path / "events.db"),
    }
    report = f"# Backtest: {strategy_name}\n\nThis run initialized RiskManager and EventLog.\n"
    hub.store.write_run_artifacts(
        run,
        manifest=manifest,
        trace_lines=["# backtest trace", "- initialize event log", "- initialize hard risk gate"],
        report=report,
        tables={},
    )
    return RecipeResult("backtest", run, manifest, report, [], {})


def run_daily_research(hub: DataHub, *, as_of: date) -> RecipeResult:
    run = hub.store.start_run("daily_research", inputs={"as_of": as_of.isoformat()})
    screen = run_canslim_screen(hub, as_of=as_of, top_n=10)
    manifest = {
        "steps": [{"name": "run_canslim_screen"}],
        "child_runs": [screen.run.run_id],
        "requires_full_market_bar_refresh": False,
    }
    report = (
        "# Daily Research\n\n"
        "No full-market bar refresh gate is required. "
        "Review the CANSLIM child run for candidates.\n"
    )
    hub.store.write_run_artifacts(
        run,
        manifest=manifest,
        trace_lines=[
            "# daily_research trace",
            "- run selected research recipes",
            "- no full-market bar refresh gate",
        ],
        report=report,
        tables={"canslim_candidates": pd.DataFrame(screen.candidates)},
    )
    return RecipeResult(
        "daily_research", run, manifest, report, screen.candidates, screen.filtered_out
    )


def _finish_result(
    hub: DataHub,
    run: ResearchRun,
    recipe: str,
    trace: list[str],
    candidates: list[dict[str, Any]],
    filtered: dict[str, int],
    limitations: list[str] | None = None,
) -> RecipeResult:
    strict_total = sum(
        1 for c in candidates if c.get("classification") == "strict_canslim_candidate"
    )
    provisional_total = sum(
        1 for c in candidates if c.get("classification") == "provisional_research_queue"
    )
    manifest = {
        "steps": [
            {"name": "load_snapshots"},
            {"name": "score_candidates"},
            {"name": "write_artifacts"},
        ],
        "candidates_total": len(candidates),
        "strict_candidates_total": strict_total,
        "provisional_candidates_total": provisional_total,
        "filtered_out": filtered,
        "limitations": limitations or [],
        "outputs": {
            "report": str(run.path / "report.md"),
            "manifest": str(run.path / "manifest.json"),
        },
    }
    report = _canslim_report(candidates, filtered, limitations or [])
    hub.store.write_run_artifacts(
        run,
        manifest=manifest,
        trace_lines=trace + [f"- candidates: `{len(candidates)}`"],
        report=report,
        tables={"candidates": pd.DataFrame(candidates), "filtered_out": pd.DataFrame([filtered])},
    )
    return RecipeResult(recipe, run, manifest, report, candidates, filtered)


def _relative_strength(symbols: list[str], bars: pd.DataFrame) -> dict[str, float]:
    if bars.empty:
        return {}
    result: dict[str, float] = {}
    for symbol in symbols:
        sym_bars = bars[bars["symbol"] == symbol].sort_values("ts")
        if len(sym_bars) < 2:
            continue
        first = float(sym_bars.iloc[0]["close"])
        last = float(sym_bars.iloc[-1]["close"])
        if first > 0:
            result[symbol] = (last - first) / first
    return result


def _percentile_threshold(values: dict[str, float], *, pct: float) -> float:
    if not values:
        return float("inf")
    ordered = sorted(values.values(), reverse=True)
    idx = min(len(ordered) - 1, max(0, int(len(ordered) * pct)))
    return ordered[idx]


def _float(value: Any) -> float | None:
    try:
        if pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def _int_or_none(value: Any) -> int | None:
    try:
        if pd.isna(value):
            return None
        return int(value)
    except Exception:
        return None


def _core_pass_symbols_missing_quarter_history(
    fundamentals: pd.DataFrame, symbols: list[str]
) -> list[str]:
    if fundamentals.empty:
        return []
    result = []
    symbol_set = set(symbols)
    for row in fundamentals.to_dict("records"):
        symbol = str(row["symbol"])
        if symbol not in symbol_set:
            continue
        eps_growth = _float(row.get("eps_growth_yoy"))
        roe = _float(row.get("roe"))
        if eps_growth is None or roe is None:
            continue
        positive_quarters = _int_or_none(row.get("positive_quarters"))
        if eps_growth >= 0.18 and roe >= 0.17 and positive_quarters is None:
            result.append(symbol)
    return result


def _company_report(
    symbol: str, as_of: date, template: str, valuation_mode: str, tables: dict[str, pd.DataFrame]
) -> str:
    quote = tables["quotes"]
    fundamentals = tables["fundamentals"]
    latest_price = "N/A" if quote.empty or "close" not in quote else quote.iloc[0]["close"]
    latest_roe = (
        "N/A" if fundamentals.empty or "roe" not in fundamentals else fundamentals.iloc[0]["roe"]
    )
    return (
        f"# Company Research: {symbol}\n\n"
        f"- as_of: `{as_of.isoformat()}`\n"
        f"- template: `{template}`\n"
        f"- valuation_mode: `{valuation_mode}`\n"
        f"- latest_price: `{latest_price}`\n"
        f"- latest_roe: `{latest_roe}`\n\n"
        "## Data Limitations\n\n"
        "Missing datasets are explicitly left blank; "
        "no synthetic investment data is used.\n"
    )


def _factor_table(quotes: pd.DataFrame, fundamentals: pd.DataFrame) -> pd.DataFrame:
    if quotes.empty:
        return pd.DataFrame(columns=["symbol", "factor_score"])
    if fundamentals.empty:
        out = quotes[["symbol"]].copy()
        out["factor_score"] = 0.0
        return out
    merged = quotes.merge(fundamentals[["symbol", "roe"]], on="symbol", how="left")
    merged["factor_score"] = pd.to_numeric(merged["roe"], errors="coerce").fillna(0.0)
    return merged[["symbol", "factor_score"]].sort_values("factor_score", ascending=False)


def _canslim_report(
    candidates: list[dict[str, Any]], filtered: dict[str, int], limitations: list[str]
) -> str:
    strict_total = sum(
        1 for c in candidates if c.get("classification") == "strict_canslim_candidate"
    )
    provisional_total = sum(
        1 for c in candidates if c.get("classification") == "provisional_research_queue"
    )
    lines = [
        "# CANSLIM Screen",
        "",
        f"Strict CANSLIM Candidates: {strict_total}",
        f"Provisional Research Queue: {provisional_total}",
        f"Displayed Candidates: {len(candidates)}",
        "",
        "## Filtered Out",
    ]
    for key, value in filtered.items():
        lines.append(f"- {key}: {value}")
    if limitations:
        lines.append("")
        lines.append("## Data Limitations")
        for item in limitations:
            lines.append(f"- {item}")
    lines.append("")
    lines.append("## Candidates")
    for candidate in candidates:
        rank = candidate.get("rank", "")
        symbol = candidate["symbol"]
        name = candidate.get("name", "")
        score = candidate["score"]
        classification = candidate.get("classification", "")
        missing = ",".join(candidate.get("missing_fields", [])) or "none"
        lines.append(
            f"- {rank}. {symbol} {name} score={score} "
            f"classification={classification} missing={missing}"
        )
    return "\n".join(lines) + "\n"
