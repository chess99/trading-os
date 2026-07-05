from __future__ import annotations

import argparse
import json
from datetime import date
from typing import Any

from ..journal.event_log import EventLog
from ..paths import repo_root
from .alerts import evaluate_watchlist_alerts
from .datahub import DataHub, provider_diagnostics
from .migration import migrate_legacy_fundamentals
from .notifier import build_notifier, deliver_alerts
from .recipes import (
    run_backtest_recipe,
    run_canslim_screen,
    run_company_research,
    run_daily_canslim_research,
    run_daily_research,
    run_factor_research,
)
from .store import ResearchStore


def build_datahub() -> DataHub:
    return DataHub(ResearchStore(repo_root() / "data" / "research"))


def cmd_data(ns: argparse.Namespace) -> int:
    hub = build_datahub()
    if ns.data_cmd == "status":
        root = hub.store.root
        payload = {
            "research_store": str(root),
            "datasets": sorted(p.name for p in (root / "datasets").glob("*") if p.is_dir())
            if (root / "datasets").exists()
            else [],
            "runs": len(list((root / "runs").glob("*"))) if (root / "runs").exists() else 0,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    if ns.data_cmd == "refresh":
        as_of = date.fromisoformat(ns.as_of)
        if ns.dataset == "universe":
            df = hub.get_universe(as_of, policy="refresh")
        elif ns.dataset == "quotes":
            df = hub.get_quote_snapshot(as_of, policy="refresh")
        elif ns.dataset == "bars":
            symbols = [s.strip() for s in ns.symbols.split(",") if s.strip()]
            df = hub.get_bars(
                symbols,
                start=date.fromisoformat(ns.start),
                end=date.fromisoformat(ns.end),
                adjustment=ns.adjustment,
                policy="refresh",
            )
        else:  # pragma: no cover
            raise RuntimeError(f"unknown dataset: {ns.dataset}")
        print(f"refreshed {ns.dataset}: {len(df)} rows")
        return 0
    if ns.data_cmd == "migrate":
        as_of = date.fromisoformat(ns.as_of)
        if ns.migration != "legacy-fundamentals":
            raise RuntimeError(f"unknown migration: {ns.migration}")
        stats = migrate_legacy_fundamentals(
            repo_root() / ns.source_dir,
            hub.store,
            as_of=as_of,
        )
        print(
            "migrated legacy fundamentals: "
            f"success={stats.success} failed={stats.failed} skipped={stats.skipped}"
        )
        if stats.errors:
            print(json.dumps({"errors": stats.errors}, ensure_ascii=False, indent=2))
        return 0
    if ns.data_cmd == "provider":
        if ns.provider_cmd == "status":
            health = hub.store.get_provider_health()
            print(health.to_json(orient="records", force_ascii=False))
            return 0
        if ns.provider_cmd == "probe":
            provider = hub._provider()
            payload = {
                "providers": [_provider_display_name(provider)],
                "diagnostics": provider_diagnostics(),
            }
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
    raise RuntimeError(f"unknown data command: {ns.data_cmd}")


def cmd_research(ns: argparse.Namespace) -> int:
    hub = build_datahub()
    if ns.research_cmd == "run":
        as_of = date.fromisoformat(ns.as_of)
        if ns.recipe != "canslim_screen":
            raise RuntimeError(f"unknown research recipe: {ns.recipe}")
        result = run_canslim_screen(
            hub,
            as_of=as_of,
            top_n=ns.top,
            min_turnover=ns.min_turnover,
            symbol_limit=ns.symbol_limit,
        )
    elif ns.research_cmd == "company":
        result = run_company_research(
            hub,
            ns.symbol,
            as_of=date.fromisoformat(ns.as_of),
            template=ns.template,
        )
    elif ns.research_cmd == "daily":
        result = run_daily_research(hub, as_of=date.fromisoformat(ns.as_of))
    elif ns.research_cmd == "daily-canslim":
        result = run_daily_canslim_research(
            hub,
            requested_as_of=date.fromisoformat(ns.as_of),
        )
    else:  # pragma: no cover
        raise RuntimeError(f"unknown research command: {ns.research_cmd}")
    print(f"run_id: {result.run.run_id}")
    print(f"manifest: {result.run.path / 'manifest.json'}")
    print(f"report: {result.run.path / 'report.md'}")
    return 0


def cmd_alert(ns: argparse.Namespace) -> int:
    if ns.alert_cmd != "monitor" or ns.mode != "watchlist":  # pragma: no cover
        raise RuntimeError(f"unknown alert command: {ns.alert_cmd}")
    if not ns.once:
        raise RuntimeError(
            "watchlist alert monitor requires --once; scheduler loop is not available"
        )

    hub = build_datahub()
    store = hub.store
    as_of = date.fromisoformat(ns.as_of) if ns.as_of else date.today()
    watchlist = _watchlist_records_for_alerts(store, as_of)
    quotes = _records_from_table(hub.get_quote_snapshot(as_of, policy="cache_first"))
    existing_alerts = _records_from_table(store.get_alerts(as_of=as_of))
    existing_cooldowns = {
        str(record["cooldown_key"])
        for record in existing_alerts
        if record.get("cooldown_key") not in {None, ""}
    }

    alerts = evaluate_watchlist_alerts(
        watchlist,
        quotes,
        as_of=as_of.isoformat(),
        existing_cooldowns=existing_cooldowns,
    )
    store.write_alerts(alerts)

    event_log = EventLog(repo_root() / "artifacts" / "alerts.db")
    for alert in alerts:
        event_log.write("ALERT", alert)
    notifier = build_notifier(
        ns.notify,
        webhook_url=ns.webhook_url,
        telegram_bot_token=ns.telegram_bot_token,
        telegram_chat_id=ns.telegram_chat_id,
    )
    deliveries = deliver_alerts(alerts, notifier, max_attempts=ns.notify_attempts)
    store.write_alert_deliveries(deliveries)
    for delivery in deliveries:
        event_log.write("ALERT_DELIVERY", delivery)

    print(
        json.dumps(
            {
                "as_of": as_of.isoformat(),
                "alerts_count": len(alerts),
                "deliveries_count": len(deliveries),
                "alerts": [
                    {"alert_id": alert.get("alert_id"), "symbol": alert.get("symbol")}
                    for alert in alerts
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_factor(ns: argparse.Namespace) -> int:
    hub = build_datahub()
    result = run_factor_research(
        hub,
        as_of=date.fromisoformat(ns.as_of),
        factor_name=ns.factor_spec,
    )
    print(f"run_id: {result.run.run_id}")
    print(f"manifest: {result.run.path / 'manifest.json'}")
    return 0


def cmd_backtest_recipe(ns: argparse.Namespace) -> int:
    hub = build_datahub()
    result = run_backtest_recipe(
        hub,
        start=date.fromisoformat(ns.start),
        end=date.fromisoformat(ns.end),
        strategy_name=ns.strategy_spec,
    )
    print(f"run_id: {result.run.run_id}")
    print(f"manifest: {result.run.path / 'manifest.json'}")
    return 0


def _watchlist_records_for_alerts(store: ResearchStore, as_of: date) -> list[dict[str, Any]]:
    stored = _latest_symbol_records(_records_from_table(store.get_watchlist_state(as_of=as_of)))
    exported = _read_exported_watchlist_state(as_of)
    if exported is not None:
        return _merge_watchlist_records(exported, stored)
    return stored


def _read_exported_watchlist_state(as_of: date) -> list[dict[str, Any]] | None:
    path = repo_root() / "artifacts" / "watchlist" / "state.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    try:
        payload_as_of = date.fromisoformat(str(payload.get("as_of")))
    except ValueError:
        return None
    if payload_as_of != as_of:
        return None
    records = payload.get("watchlist_state")
    if not isinstance(records, list):
        return None
    return [record for record in records if isinstance(record, dict)]


def _latest_symbol_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for record in sorted(records, key=_event_record_sort_key):
        symbol = str(record.get("symbol") or "").strip()
        if not symbol:
            continue
        latest[symbol] = {**record, "symbol": symbol}
    return sorted(latest.values(), key=lambda row: str(row["symbol"]))


def _merge_watchlist_records(
    exported: list[dict[str, Any]], stored: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_symbol: dict[str, dict[str, Any]] = {}
    for record in [*exported, *stored]:
        symbol = str(record.get("symbol") or "").strip()
        if not symbol:
            continue
        by_symbol[symbol] = {**record, "symbol": symbol}
    return sorted(by_symbol.values(), key=lambda row: str(row["symbol"]))


def _event_record_sort_key(record: dict[str, Any]) -> tuple[str, str]:
    return (_date_key(record.get("as_of")), str(record.get("fetched_at") or ""))


def _date_key(value: Any) -> str:
    try:
        return date.fromisoformat(str(value)).isoformat()
    except (TypeError, ValueError):
        return ""


def register_research_kernel_commands(sub: argparse._SubParsersAction) -> None:
    data = sub.add_parser("data", help="ResearchStore data refresh and status")
    data_sub = data.add_subparsers(dest="data_cmd", required=True)
    data_status = data_sub.add_parser("status", help="Show ResearchStore status")
    data_status.set_defaults(func=cmd_data)
    refresh = data_sub.add_parser("refresh", help="Refresh a ResearchStore dataset")
    refresh.add_argument("dataset", choices=["universe", "quotes", "bars"])
    refresh.add_argument("--as-of", required=True, dest="as_of")
    refresh.add_argument("--symbols", default="")
    refresh.add_argument("--start", default="2020-01-01")
    refresh.add_argument("--end", required=True)
    refresh.add_argument("--adjustment", default="qfq")
    refresh.set_defaults(func=cmd_data)
    migrate = data_sub.add_parser("migrate", help="Migrate legacy local data into ResearchStore")
    migrate.add_argument("migration", choices=["legacy-fundamentals"])
    migrate.add_argument("--as-of", required=True, dest="as_of")
    migrate.add_argument("--source-dir", default="data/fundamental")
    migrate.set_defaults(func=cmd_data)
    provider = data_sub.add_parser("provider", help="Inspect research data providers")
    provider_sub = provider.add_subparsers(dest="provider_cmd", required=True)
    provider_status = provider_sub.add_parser("status", help="Show provider health records")
    provider_status.set_defaults(func=cmd_data)
    provider_probe = provider_sub.add_parser("probe", help="Probe configured provider capabilities")
    provider_probe.set_defaults(func=cmd_data)

    research = sub.add_parser("research", help="Run deterministic research recipes")
    research_sub = research.add_subparsers(dest="research_cmd", required=True)
    run = research_sub.add_parser("run", help="Run a named research recipe")
    run.add_argument("recipe", choices=["canslim_screen"])
    run.add_argument("--as-of", required=True, dest="as_of")
    run.add_argument("--top", type=int, default=30)
    run.add_argument("--min-turnover", type=float, default=10_000_000.0)
    run.add_argument(
        "--symbol-limit",
        type=int,
        default=None,
        help="Diagnostic smoke limit for symbols entering provider-heavy screening stages",
    )
    run.set_defaults(func=cmd_research)
    company = research_sub.add_parser("company", help="Run company research")
    company.add_argument("symbol")
    company.add_argument("--template", default="quality_growth")
    company.add_argument("--as-of", required=True, dest="as_of")
    company.set_defaults(func=cmd_research)
    daily = research_sub.add_parser(
        "daily", help="Run daily research without a full-market bar refresh gate"
    )
    daily.add_argument("--as-of", required=True, dest="as_of")
    daily.set_defaults(func=cmd_research)
    daily_canslim = research_sub.add_parser(
        "daily-canslim",
        help="Run full daily CANSLIM research closure",
        description=(
            "Run full daily CANSLIM research closure: resolve the completed trading day, "
            "screen all A-shares, research every strict candidate, update decisions and "
            "watchlist state, and export the human report."
        ),
    )
    daily_canslim.add_argument("--as-of", required=True, dest="as_of")
    daily_canslim.set_defaults(func=cmd_research)

    alert = sub.add_parser("alert", help="Run watchlist-only alert monitoring")
    alert_sub = alert.add_subparsers(dest="alert_cmd", required=True)
    monitor = alert_sub.add_parser(
        "monitor",
        description=(
            "Run the watchlist-only alert monitor once. It evaluates existing watchlist "
            "entries against the quote snapshot and does not scan the full market."
        ),
    )
    monitor.add_argument("--mode", choices=["watchlist"], required=True)
    monitor.add_argument("--once", action="store_true")
    monitor.add_argument("--as-of", dest="as_of")
    monitor.add_argument(
        "--notify",
        choices=["none", "stdout", "webhook", "feishu", "dingtalk", "telegram", "system"],
        default="none",
    )
    monitor.add_argument("--webhook-url", dest="webhook_url")
    monitor.add_argument("--telegram-bot-token", dest="telegram_bot_token")
    monitor.add_argument("--telegram-chat-id", dest="telegram_chat_id")
    monitor.add_argument("--notify-attempts", dest="notify_attempts", type=int, default=3)
    monitor.set_defaults(func=cmd_alert)

    factor = sub.add_parser("factor", help="Run factor research")
    factor_sub = factor.add_subparsers(dest="factor_cmd", required=True)
    factor_run = factor_sub.add_parser("run")
    factor_run.add_argument("factor_spec")
    factor_run.add_argument("--as-of", required=True, dest="as_of")
    factor_run.set_defaults(func=cmd_factor)

    backtest = sub.add_parser("backtest", help="Run a ResearchStore-backed backtest recipe")
    backtest_sub = backtest.add_subparsers(dest="backtest_cmd", required=True)
    backtest_run = backtest_sub.add_parser("run")
    backtest_run.add_argument("strategy_spec")
    backtest_run.add_argument("--start", required=True)
    backtest_run.add_argument("--end", required=True)
    backtest_run.set_defaults(func=cmd_backtest_recipe)


def _records_from_table(table: Any) -> list[dict[str, Any]]:
    if table is None:
        return []
    if hasattr(table, "empty") and table.empty:
        return []
    if hasattr(table, "to_dict"):
        return table.to_dict("records")
    return list(table)


def _provider_display_name(provider: Any) -> str:
    if hasattr(provider, "providers"):
        names = [
            str(getattr(item, "name", item.__class__.__name__))
            for item in getattr(provider, "providers", [])
        ]
        return "ProviderRouter(" + ",".join(names) + ")"
    return str(getattr(provider, "name", provider.__class__.__name__))
