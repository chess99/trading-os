from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from ..journal.event_log import EventLog
from ..paths import repo_root
from ..risk.manager import RiskManager
from .calendar import TradingCalendar
from .completeness import evaluate_company_research_completeness, status_from_company_manifest
from .datahub import DataHub
from .decisions import build_canslim_decisions
from .store import ResearchRun
from .technical import detect_technical_setup
from .watchlist import update_watchlist_from_decisions


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
    data_coverage = {
        "universe_snapshot": _snapshot_coverage(universe),
        "quote_snapshot": _snapshot_coverage(quotes),
    }
    trace.append("- load quote snapshot")

    filtered = {"st_or_inactive": 0, "low_turnover": 0, "insufficient_data": 0, "no_signal": 0}
    if universe.empty or quotes.empty:
        return _finish_result(
            hub,
            run,
            "canslim_screen",
            trace,
            [],
            filtered,
            data_coverage=data_coverage,
        )

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

    fundamentals = hub.store.get_fundamentals(symbols, as_of=as_of)
    if fundamentals.empty:
        fundamentals = hub.get_fundamentals(symbols, as_of=as_of, policy="cache_first")
    data_coverage["fundamentals"] = _snapshot_coverage(fundamentals)
    if fundamentals.empty:
        filtered["insufficient_data"] = len(symbols)
        return _finish_result(
            hub,
            run,
            "canslim_screen",
            trace,
            [],
            filtered,
            data_coverage=data_coverage,
        )

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
            fundamentals = hub.store.get_fundamentals(symbols, as_of=as_of)
            data_coverage["fundamentals"] = _snapshot_coverage(fundamentals)
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
            data_coverage=data_coverage,
        )

    rs_limitations: list[str] = []
    try:
        bars = _get_bars_with_partial_fallback(
            hub,
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
    data_coverage["bars"] = _bars_coverage(bars)
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
    for idx, candidate in enumerate(candidates, 1):
        candidate["rank"] = idx
    displayed_candidates = candidates[:top_n]
    limitations = []
    limitations = [*rs_limitations]
    if any(candidate["missing_fields"] for candidate in candidates):
        limitations.append(
            "Some candidates are provisional because quarterly continuity fields are missing."
        )
    return _finish_result(
        hub,
        run,
        "canslim_screen",
        trace,
        displayed_candidates,
        filtered,
        limitations=limitations,
        all_candidates=candidates,
        data_coverage=data_coverage,
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
    bars = _get_bars_with_partial_fallback(
        hub,
        [symbol],
        start=as_of - timedelta(days=420),
        end=as_of + timedelta(days=1),
        adjustment="qfq",
        policy="lazy_fill",
    )
    trace = [
        "# company_research trace",
        f"- symbol: `{symbol}`",
        "- load quote, fundamentals, bars, estimates, and news through DataHub",
        "- write structured report with explicit data limitations",
    ]
    tables = {
        "quotes": quotes[quotes["symbol"] == symbol] if not quotes.empty else quotes,
        "fundamentals": fundamentals,
        "bars": bars,
        "estimates": estimates,
        "news": news,
    }
    report = _company_report(symbol, as_of, template, valuation_mode, tables)
    datasets = {
        "quotes": not tables["quotes"].empty,
        "fundamentals": not fundamentals.empty,
        "bars": not bars.empty,
        "estimates": not estimates.empty,
        "news": not news.empty,
    }
    completeness = evaluate_company_research_completeness(datasets)
    manifest = {
        "steps": [{"name": "load_company_datasets"}, {"name": "write_report"}],
        "template": template,
        "datasets": datasets,
        "completeness": completeness.to_manifest(),
        "complete": completeness.complete,
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


def run_daily_canslim_research(hub: DataHub, *, requested_as_of: date) -> RecipeResult:
    calendar = TradingCalendar()
    effective_as_of = calendar.resolve_effective_as_of(requested_as_of)
    run = hub.store.start_run(
        "daily_canslim_research",
        inputs={
            "requested_as_of": requested_as_of.isoformat(),
            "effective_as_of": effective_as_of.isoformat(),
        },
    )
    trace = [
        "# daily_canslim_research trace",
        f"- requested_as_of: `{requested_as_of.isoformat()}`",
        f"- effective_as_of: `{effective_as_of.isoformat()}`",
        "- run CANSLIM screen with top_n=30 display limit",
    ]

    screen = run_canslim_screen(hub, as_of=effective_as_of, top_n=30)
    all_candidates = _read_screen_all_candidates(screen)
    strict_candidates = [
        row
        for row in all_candidates
        if str(row.get("classification")) == "strict_canslim_candidate"
    ]
    strict_symbols = _ordered_unique_candidate_symbols(strict_candidates)
    current_watchlist = _current_watchlist_records(hub, effective_as_of)
    watched_symbols = _watchlist_symbols_for_daily(current_watchlist)
    evaluation_symbols = _ordered_unique_values([*strict_symbols, *watched_symbols])
    trace.append(f"- strict candidates loaded from all_candidates.csv: `{len(strict_candidates)}`")
    trace.append(f"- active watchlist symbols loaded: `{len(watched_symbols)}`")

    bars = _get_bars_with_partial_fallback(
        hub,
        evaluation_symbols,
        start=effective_as_of - timedelta(days=420),
        end=effective_as_of + timedelta(days=1),
        adjustment="qfq",
        policy="lazy_fill",
    )
    trace.append("- lazy-fill bars for strict CANSLIM symbols and active watchlist symbols")

    setups = {
        symbol: {
            **detect_technical_setup(symbol, bars),
            "as_of": effective_as_of.isoformat(),
            "source_run_id": run.run_id,
            "screen_run_id": screen.run.run_id,
        }
        for symbol in evaluation_symbols
    }
    technical_setups = list(setups.values())
    hub.store.write_technical_setups(technical_setups)

    deep_research_runs = []
    for symbol in strict_symbols:
        try:
            company = run_company_research(
                hub,
                symbol,
                as_of=effective_as_of,
                template="canslim",
            )
        except Exception as exc:
            deep_research_runs.append(
                {
                    "symbol": symbol,
                    "template": "canslim",
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
            continue
        deep_research_runs.append(
            {
                "symbol": symbol,
                "run_id": company.run.run_id,
                "template": "canslim",
                **_deep_research_status(company),
                "report": str(company.run.path / "report.md"),
                "manifest": str(company.run.path / "manifest.json"),
            }
        )
    trace.append(f"- deep research runs written: `{len(deep_research_runs)}`")

    strict_decisions = build_canslim_decisions(
        strict_candidates,
        setups,
        as_of=effective_as_of.isoformat(),
        source_run_id=screen.run.run_id,
    )
    strict_decisions = _downgrade_failed_deep_research_decisions(
        strict_decisions,
        deep_research_runs,
    )
    watchlist_refresh_decisions = _build_watchlist_refresh_decisions(
        current_watchlist,
        strict_symbols=set(strict_symbols),
        setups=setups,
        as_of=effective_as_of.isoformat(),
        source_run_id=run.run_id,
    )
    decisions = [*strict_decisions, *watchlist_refresh_decisions]
    hub.store.write_decisions(decisions)
    trace.append(f"- decisions written: `{len(decisions)}`")

    watchlist_state = update_watchlist_from_decisions(current_watchlist, decisions)
    watchlist_state = [
        {**row, "as_of": effective_as_of.isoformat(), "source_run_id": row.get("source_run_id")}
        for row in watchlist_state
    ]
    hub.store.write_watchlist_state(watchlist_state)
    trace.append(f"- watchlist rows written: `{len(watchlist_state)}`")
    watchlist_state_path = _write_watchlist_state_json(
        as_of=effective_as_of,
        generated_from_run_id=run.run_id,
        watchlist_state=watchlist_state,
    )
    trace.append(f"- watchlist state json: `{watchlist_state_path}`")

    report = _daily_canslim_report(
        requested_as_of=requested_as_of,
        effective_as_of=effective_as_of,
        screen=screen,
        strict_candidates=strict_candidates,
        deep_research_runs=deep_research_runs,
        decisions=decisions,
        watchlist_state=watchlist_state,
    )
    human_report_path = (
        repo_root()
        / "artifacts"
        / "research"
        / f"daily-canslim-{effective_as_of:%Y%m%d}.md"
    )
    human_report_path.parent.mkdir(parents=True, exist_ok=True)
    human_report_path.write_text(report, encoding="utf-8")

    manifest = {
        "requested_as_of": requested_as_of.isoformat(),
        "effective_as_of": effective_as_of.isoformat(),
        "child_runs": [
            screen.run.run_id,
            *[item["run_id"] for item in deep_research_runs if item.get("run_id")],
        ],
        "deep_research_runs": deep_research_runs,
        "strict_candidates_processed": len(strict_candidates),
        "active_watchlist_symbols_processed": len(watched_symbols),
        "decisions_total": len(decisions),
        "human_report": str(human_report_path),
        "watchlist_state_json": str(watchlist_state_path),
        "outputs": {
            "report": str(run.path / "report.md"),
            "manifest": str(run.path / "manifest.json"),
            "watchlist_state_json": str(watchlist_state_path),
        },
    }
    hub.store.write_run_artifacts(
        run,
        manifest=manifest,
        trace_lines=trace,
        report=report,
        tables={
            "decisions": pd.DataFrame(decisions),
            "watchlist_state": pd.DataFrame(watchlist_state),
            "technical_setups": pd.DataFrame(technical_setups),
        },
    )
    return RecipeResult(
        "daily_canslim_research",
        run,
        manifest,
        report,
        decisions,
        screen.filtered_out,
    )


def _write_watchlist_state_json(
    *,
    as_of: date,
    generated_from_run_id: str,
    watchlist_state: list[dict[str, Any]],
) -> Path:
    path = repo_root() / "artifacts" / "watchlist" / "state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "as_of": as_of.isoformat(),
        "generated_from_run_id": generated_from_run_id,
        "watchlist_state": watchlist_state,
    }
    path.write_text(json.dumps(_jsonable(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _finish_result(
    hub: DataHub,
    run: ResearchRun,
    recipe: str,
    trace: list[str],
    candidates: list[dict[str, Any]],
    filtered: dict[str, int],
    limitations: list[str] | None = None,
    all_candidates: list[dict[str, Any]] | None = None,
    data_coverage: dict[str, Any] | None = None,
) -> RecipeResult:
    all_candidates = all_candidates if all_candidates is not None else candidates
    strict_total = sum(
        1 for c in all_candidates if c.get("classification") == "strict_canslim_candidate"
    )
    provisional_total = sum(
        1 for c in all_candidates if c.get("classification") == "provisional_research_queue"
    )
    manifest = {
        "steps": [
            {"name": "load_snapshots"},
            {"name": "score_candidates"},
            {"name": "write_artifacts"},
        ],
        "candidates_total": len(all_candidates),
        "displayed_candidates_total": len(candidates),
        "strict_candidates_total": strict_total,
        "provisional_candidates_total": provisional_total,
        "filtered_out": filtered,
        "limitations": limitations or [],
        "data_coverage": data_coverage or {},
        "outputs": {
            "report": str(run.path / "report.md"),
            "manifest": str(run.path / "manifest.json"),
        },
    }
    report = _canslim_report(candidates, filtered, limitations or [], all_candidates)
    hub.store.write_run_artifacts(
        run,
        manifest=manifest,
        trace_lines=trace
        + [
            f"- total candidates: `{len(all_candidates)}`",
            f"- displayed candidates: `{len(candidates)}`",
        ],
        report=report,
        tables={
            "candidates": pd.DataFrame(candidates),
            "all_candidates": pd.DataFrame(all_candidates),
            "filtered_out": pd.DataFrame([filtered]),
        },
    )
    return RecipeResult(recipe, run, manifest, report, candidates, filtered)


def _read_screen_all_candidates(screen: RecipeResult) -> list[dict[str, Any]]:
    path = screen.run.path / "tables" / "all_candidates.csv"
    if not path.exists():
        return []
    try:
        df = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return []
    if df.empty:
        return []
    return df.to_dict("records")


def _ordered_unique_candidate_symbols(candidates: list[dict[str, Any]]) -> list[str]:
    return _ordered_unique_values(row.get("symbol") for row in candidates)


def _ordered_unique_values(values: Any) -> list[str]:
    seen = set()
    symbols = []
    for raw in values:
        symbol = _clean_symbol(raw)
        if symbol is None or symbol in seen:
            continue
        seen.add(symbol)
        symbols.append(symbol)
    return symbols


def _current_watchlist_records(hub: DataHub, as_of: date) -> list[dict[str, Any]]:
    try:
        current = hub.store.get_watchlist_state(as_of=as_of)
    except TypeError:
        current = hub.store.get_watchlist_state()
    records = current.to_dict("records") if current is not None and not current.empty else []
    return _latest_rows_by_symbol(records)


def _latest_rows_by_symbol(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_symbol: dict[str, dict[str, Any]] = {}
    for record in sorted(records, key=_event_record_sort_key):
        symbol = _clean_symbol(record.get("symbol"))
        if symbol is None:
            continue
        row = dict(record)
        row["symbol"] = symbol
        by_symbol[symbol] = row
    return sorted(by_symbol.values(), key=lambda row: str(row["symbol"]))


def _watchlist_symbols_for_daily(records: list[dict[str, Any]]) -> list[str]:
    return _ordered_unique_values(
        row.get("symbol")
        for row in records
        if row.get("status") in {"watching", "actionable"}
    )


def _build_watchlist_refresh_decisions(
    watchlist: list[dict[str, Any]],
    *,
    strict_symbols: set[str],
    setups: dict[str, dict[str, Any]],
    as_of: str,
    source_run_id: str,
) -> list[dict[str, Any]]:
    decisions = []
    for item in watchlist:
        symbol = _clean_symbol(item.get("symbol"))
        if symbol is None or symbol in strict_symbols:
            continue
        status = item.get("status")
        if status == "candidate":
            reason = "existing candidate requires fresh strict screen and complete deep research"
            decisions.append(
                {
                    "symbol": symbol,
                    "as_of": as_of,
                    "decision": "research_only",
                    "confidence": 0.35,
                    "reason": reason,
                    "score": item.get("score"),
                    "pivot_price": None,
                    "buy_zone_high": None,
                    "stop_loss": None,
                    "source_run_id": source_run_id,
                }
            )
            continue
        if status not in {"watching", "actionable"}:
            continue
        setup = setups.get(symbol, {})
        pivot = setup.get("pivot_price")
        stop_loss = setup.get("stop_loss")
        if _is_positive_number(pivot) and _is_positive_number(stop_loss):
            decision = setup.get("status") or "wait_for_breakout"
            confidence = 0.55
            reason = "existing watchlist symbol refreshed with defined technical setup"
        else:
            decision = "research_only"
            confidence = 0.35
            reason = "existing watchlist symbol refreshed but technical setup is incomplete"
        decisions.append(
            {
                "symbol": symbol,
                "as_of": as_of,
                "decision": decision,
                "confidence": confidence,
                "reason": reason,
                "score": item.get("score"),
                "pivot_price": pivot,
                "buy_zone_high": setup.get("buy_zone_high"),
                "stop_loss": stop_loss,
                "source_run_id": source_run_id,
            }
        )
    return decisions


def _downgrade_failed_deep_research_decisions(
    decisions: list[dict[str, Any]], deep_research_runs: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    unsafe = {
        str(item.get("symbol")): str(item.get("status"))
        for item in deep_research_runs
        if item.get("status") != "ok" and item.get("symbol") is not None
    }
    if not unsafe:
        return decisions
    downgraded = []
    for decision in decisions:
        row = dict(decision)
        symbol = str(row.get("symbol"))
        if symbol in unsafe:
            row["decision"] = "research_only"
            row["confidence"] = min(float(row.get("confidence") or 0.0), 0.35)
            row["reason"] = f"strict CANSLIM evidence but deep research {unsafe[symbol]}"
        downgraded.append(row)
    return downgraded


def _deep_research_status(company: RecipeResult) -> dict[str, Any]:
    status = status_from_company_manifest(company.manifest or {})
    report_path = company.run.path / "report.md"
    manifest_path = company.run.path / "manifest.json"
    if not report_path.exists() or not manifest_path.exists():
        return {
            "status": "incomplete",
            "reason": "company research artifacts missing",
        }
    if status["status"] == "complete":
        return {"status": "ok"}
    if status["status"] == "ok":
        return status
    return status


def _clean_symbol(value: Any) -> str | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        return None
    symbol = str(value).strip()
    return symbol or None


def _is_positive_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    try:
        number = float(value)
    except Exception:
        return False
    return not pd.isna(number) and number > 0


def _event_record_sort_key(record: dict[str, Any]) -> tuple[str, str]:
    return (_date_key(record.get("as_of")), str(record.get("fetched_at") or ""))


def _date_key(value: Any) -> str:
    try:
        return date.fromisoformat(str(value)).isoformat()
    except (TypeError, ValueError):
        return ""


def _get_bars_with_partial_fallback(
    hub: DataHub,
    symbols: list[str],
    *,
    start: date,
    end: date,
    adjustment: str,
    policy: str,
) -> pd.DataFrame:
    if not symbols:
        return pd.DataFrame()
    try:
        return hub.get_bars(
            symbols,
            start=start,
            end=end,
            adjustment=adjustment,
            policy=policy,
        )
    except Exception:
        cached = hub.store.get_bars(symbols, start=start, end=end)
        if cached is not None and not cached.empty:
            return cached
        raise


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


def _snapshot_coverage(df: pd.DataFrame) -> dict[str, Any]:
    if df is None or df.empty:
        return {"rows": 0}
    result: dict[str, Any] = {"rows": len(df)}
    for column in ["as_of", "source", "freshness_policy"]:
        if column in df.columns:
            values = sorted(str(v) for v in df[column].dropna().unique())
            result[column] = values
    if "fetched_at" in df.columns:
        fetched = df["fetched_at"].dropna().astype(str)
        if not fetched.empty:
            result["fetched_at_min"] = fetched.min()
            result["fetched_at_max"] = fetched.max()
    return result


def _bars_coverage(df: pd.DataFrame) -> dict[str, Any]:
    if df is None or df.empty:
        return {"rows": 0, "symbols": 0}
    ts = pd.to_datetime(df["ts"], utc=True, errors="coerce") if "ts" in df.columns else None
    result: dict[str, Any] = {
        "rows": len(df),
        "symbols": int(df["symbol"].nunique()) if "symbol" in df.columns else 0,
    }
    if ts is not None and not ts.dropna().empty:
        result["ts_min"] = ts.min().date().isoformat()
        result["ts_max"] = ts.max().date().isoformat()
    for column in ["source", "freshness_policy"]:
        if column in df.columns:
            result[column] = sorted(str(v) for v in df[column].dropna().unique())
    return result


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


def _jsonable(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if pd.isna(value):
        return None
    return value


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
    bars = tables.get("bars", pd.DataFrame())
    estimates = tables.get("estimates", pd.DataFrame())
    news = tables.get("news", pd.DataFrame())
    latest_price = "N/A" if quote.empty or "close" not in quote else quote.iloc[0]["close"]
    latest_roe = (
        "N/A" if fundamentals.empty or "roe" not in fundamentals else fundamentals.iloc[0]["roe"]
    )
    if template == "canslim":
        return _canslim_company_report(
            symbol, as_of, valuation_mode, quote, fundamentals, bars, estimates, news
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


def _canslim_company_report(
    symbol: str,
    as_of: date,
    valuation_mode: str,
    quote: pd.DataFrame,
    fundamentals: pd.DataFrame,
    bars: pd.DataFrame,
    estimates: pd.DataFrame,
    news: pd.DataFrame,
) -> str:
    latest_quote = quote.iloc[0].to_dict() if not quote.empty else {}
    latest_fund = fundamentals.iloc[0].to_dict() if not fundamentals.empty else {}
    rs_values = _relative_strength([symbol], bars)
    rs_value = rs_values.get(symbol)
    close = _float(latest_quote.get("close"))
    amount = _float(latest_quote.get("amount"))
    eps_growth = _float(latest_fund.get("eps_growth_yoy"))
    roe = _float(latest_fund.get("roe"))
    positive_quarters = _int_or_none(latest_fund.get("positive_quarters"))
    gross_margin = _float(latest_fund.get("gross_margin"))
    net_margin = _float(latest_fund.get("net_margin"))

    missing = []
    for name, value in [
        ("quote.close", close),
        ("quote.amount", amount),
        ("fundamentals.eps_growth_yoy", eps_growth),
        ("fundamentals.roe", roe),
        ("fundamentals.positive_quarters", positive_quarters),
        ("bars.relative_strength", rs_value),
    ]:
        if value is None:
            missing.append(name)

    c_ok = eps_growth is not None and eps_growth >= 0.18
    a_ok = roe is not None and roe >= 0.17 and (
        positive_quarters is not None and positive_quarters >= 4
    )
    l_ok = rs_value is not None and rs_value > 0

    lines = [
        f"# CANSLIM Company Research: {symbol}",
        "",
        f"- as_of: `{as_of.isoformat()}`",
        f"- valuation_mode: `{valuation_mode}`",
        f"- latest_price: `{_fmt(close)}`",
        f"- latest_turnover_amount: `{_fmt(amount)}`",
        "",
        "## CANSLIM Evidence",
        "",
        f"- C current earnings: eps_growth_yoy=`{_fmt_pct(eps_growth)}` pass=`{c_ok}`",
        (
            "- A annual/quality proxy: "
            f"roe=`{_fmt_pct(roe)}`, positive_quarters=`{_fmt(positive_quarters)}` "
            f"pass=`{a_ok}`"
        ),
        f"- L leadership proxy: relative_strength=`{_fmt_pct(rs_value)}` pass=`{l_ok}`",
        f"- S liquidity proxy: turnover_amount=`{_fmt(amount)}`",
        f"- profitability context: gross_margin=`{_fmt_pct(gross_margin)}`, "
        f"net_margin=`{_fmt_pct(net_margin)}`",
        "",
        "## Interpretation",
        "",
        "- This report verifies the deterministic CANSLIM screening evidence available locally.",
        "- It is not a trade instruction; technical base/pivot confirmation is still required.",
        "",
        "## News and Announcements",
        "",
    ]
    if news.empty:
        lines.append("- No cached news or announcements are available for this symbol.")
    else:
        symbol_news = _filter_symbol_rows(news, symbol)
        ordered_news = _sort_by_recency(
            symbol_news,
            recency_columns=["published_at"],
            tie_columns=["title", "source_url"],
        )
        if ordered_news.empty:
            lines.append("- No cached news or announcements are available for this symbol.")
        else:
            for record in ordered_news.head(10).to_dict("records"):
                published_at = _fmt(record.get("published_at"))
                title = _fmt(record.get("title"))
                source_url = _fmt(record.get("source_url"))
                lines.append(
                    f"- published_at=`{published_at}` title=`{title}` source_url=`{source_url}`"
                )
    lines.extend(
        [
            "",
            "## Estimates and Valuation Context",
            "",
        ]
    )
    if estimates.empty:
        lines.append("- No cached estimates are available for this symbol.")
    else:
        symbol_estimates = _filter_symbol_rows(estimates, symbol)
        ordered_estimates = _sort_by_recency(
            symbol_estimates,
            recency_columns=["as_of", "fetched_at", "estimate_date", "report_date", "published_at"],
        )
        if ordered_estimates.empty:
            lines.append("- No cached estimates are available for this symbol.")
        else:
            latest_estimate = ordered_estimates.iloc[0].to_dict()
            for key, value in latest_estimate.items():
                if key == "symbol":
                    continue
                lines.append(f"- {key}: `{_fmt(value)}`")
    lines.extend(
        [
            "",
            "## Institutional Sponsorship and Peer Context",
            "",
            "- Institutional sponsorship, peer positioning, ownership trend, and industry "
            "crowding require provider coverage that is not guaranteed in cached datasets.",
            "- Missing sponsorship or peer fields reduce confidence and block automatic trade "
            "status until provider-backed evidence is available.",
            "",
        ]
    )
    lines.extend(
        [
            "## Data Limitations",
            "",
        ]
    )
    if missing:
        for item in missing:
            lines.append(f"- Missing `{item}`.")
    else:
        lines.append("- Required local CANSLIM screening fields are present.")
    lines.extend(
        [
            "- News, management guidance, institutional sponsorship, and peer comparison are "
            "not yet fully populated unless separate datasets exist.",
            "",
            "## Next Actions",
            "",
            "- Run CANSLIM technical confirmation before adding to watchlist.",
            "- Investigate one-off profit, cyclicality, and industry crowding.",
            "- Link any final conclusion back to this run manifest and technical confirmation.",
        ]
    )
    return "\n".join(lines) + "\n"


def _filter_symbol_rows(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if df.empty or "symbol" not in df.columns:
        return df
    return df[df["symbol"].astype(str) == symbol].reset_index(drop=True)


def _sort_by_recency(
    df: pd.DataFrame, *, recency_columns: list[str], tie_columns: list[str] | None = None
) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()
    sort_columns = []
    ascending = []
    for column in recency_columns:
        if column not in out.columns:
            continue
        parsed_column = f"__parsed_{column}"
        out[parsed_column] = pd.to_datetime(out[column], errors="coerce", utc=True)
        sort_columns.append(parsed_column)
        ascending.append(False)

    for column in tie_columns or []:
        if column in out.columns:
            sort_columns.append(column)
            ascending.append(True)

    if not sort_columns:
        return out

    return (
        out.sort_values(
            sort_columns,
            ascending=ascending,
            na_position="last",
            kind="mergesort",
        )
        .drop(columns=[column for column in sort_columns if column.startswith("__parsed_")])
        .reset_index(drop=True)
    )


def _fmt(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.2%}"


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
    candidates: list[dict[str, Any]],
    filtered: dict[str, int],
    limitations: list[str],
    all_candidates: list[dict[str, Any]] | None = None,
) -> str:
    all_candidates = all_candidates if all_candidates is not None else candidates
    strict_total = sum(
        1 for c in all_candidates if c.get("classification") == "strict_canslim_candidate"
    )
    provisional_total = sum(
        1 for c in all_candidates if c.get("classification") == "provisional_research_queue"
    )
    lines = [
        "# CANSLIM Screen",
        "",
        f"Total Qualified Candidates: {len(all_candidates)}",
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


def _daily_canslim_report(
    *,
    requested_as_of: date,
    effective_as_of: date,
    screen: RecipeResult,
    strict_candidates: list[dict[str, Any]],
    deep_research_runs: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    watchlist_state: list[dict[str, Any]],
) -> str:
    lines = [
        "# Daily CANSLIM Research",
        "",
        f"- requested_as_of: `{requested_as_of.isoformat()}`",
        f"- effective_as_of: `{effective_as_of.isoformat()}`",
        f"- screen_run: `{screen.run.run_id}`",
        f"- full_candidates: `{screen.manifest.get('candidates_total')}`",
        f"- displayed_candidates: `{screen.manifest.get('displayed_candidates_total')}`",
        f"- strict_candidates_processed: `{len(strict_candidates)}`",
        f"- decisions_total: `{len(decisions)}`",
        "",
        "## Strict Candidates",
    ]
    if strict_candidates:
        for row in strict_candidates:
            lines.append(f"- {row.get('symbol')} score={row.get('score')}")
    else:
        lines.append("- No strict CANSLIM candidates.")

    lines.extend(["", "## Deep Research Runs"])
    if deep_research_runs:
        for row in deep_research_runs:
            if row["status"] == "ok":
                lines.append(f"- {row['symbol']} status=ok report={row['report']}")
            else:
                lines.append(_format_deep_research_issue(row))
    else:
        lines.append("- No strict candidate deep research runs.")

    lines.extend(["", "## Decisions"])
    if decisions:
        for row in decisions:
            lines.append(
                f"- {row['symbol']} decision={row['decision']} "
                f"pivot={row.get('pivot_price')} stop={row.get('stop_loss')}"
            )
    else:
        lines.append("- No decisions generated.")

    lines.extend(["", "## Watchlist State"])
    if watchlist_state:
        for row in watchlist_state:
            lines.append(
                f"- {row['symbol']} status={row.get('status')} "
                f"pivot={row.get('pivot_price')}"
            )
    else:
        lines.append("- Watchlist is empty.")

    lines.extend(
        [
            "",
            "## Data Lineage",
            "",
            f"- screen_manifest: `{screen.run.path / 'manifest.json'}`",
            f"- screen_report: `{screen.run.path / 'report.md'}`",
        ]
    )
    return "\n".join(lines) + "\n"


def _format_deep_research_issue(row: dict[str, Any]) -> str:
    parts = [f"- {row.get('symbol')} status={row.get('status')}"]
    if row.get("error_type"):
        parts.append(f"error_type={row['error_type']}")
    if row.get("error"):
        parts.append(f"error={row['error']}")
    if row.get("reason"):
        parts.append(f"reason={row['reason']}")
    if row.get("missing_core_datasets"):
        parts.append(f"missing_core_datasets={row['missing_core_datasets']}")
    if row.get("missing_enrichment_datasets"):
        parts.append(f"missing_enrichment_datasets={row['missing_enrichment_datasets']}")
    return " ".join(parts)
