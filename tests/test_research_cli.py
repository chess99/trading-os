from __future__ import annotations

import json

import pytest


def test_cli_registers_only_research_kernel_commands():
    from trading_os.cli_internal.app import build_parser

    parser = build_parser()
    help_text = parser.format_help()

    for command in ["data", "research", "factor", "backtest", "alert", "pool"]:
        assert command in help_text
    assert "research" in help_text
    assert "factor" in help_text
    for retired in [
        "scheduler",
        "daily",
        "scan-elder",
        "scan-canslim",
        "scan-value",
        "fetch-ak-bulk",
        "fundamental-store",
        "lake-init",
        "valuation-sotp",
        "valuation-sensitivity",
        "market-breadth",
    ]:
        assert retired not in help_text


def test_pool_cli_does_not_offer_scan_sync(capsys):
    from trading_os.cli_internal.app import build_parser

    parser = build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["pool", "--help"])

    assert exc.value.code == 0
    assert "sync-from-scan" not in capsys.readouterr().out


def test_cli_parses_legacy_fundamental_migration_command():
    from trading_os.cli_internal.app import build_parser

    parser = build_parser()
    ns = parser.parse_args(
        ["data", "migrate", "legacy-fundamentals", "--as-of", "2026-06-01"]
    )

    assert ns.data_cmd == "migrate"
    assert ns.migration == "legacy-fundamentals"
    assert ns.as_of == "2026-06-01"
    assert ns.source_dir == "data/fundamental"


def test_research_cli_parses_daily_canslim_command():
    from trading_os.cli_internal.app import build_parser

    parser = build_parser()
    ns = parser.parse_args(["research", "daily-canslim", "--as-of", "2026-06-12"])

    assert ns.research_cmd == "daily-canslim"
    assert ns.as_of == "2026-06-12"


def test_research_daily_canslim_help_describes_closure(capsys):
    from trading_os.cli_internal.app import build_parser

    parser = build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["research", "daily-canslim", "--help"])

    assert exc.value.code == 0
    help_text = capsys.readouterr().out
    assert "daily CANSLIM research closure" in help_text
    assert "--as-of" in help_text


def test_data_provider_status_command_parses():
    from trading_os.cli_internal.app import build_parser

    parser = build_parser()
    ns = parser.parse_args(["data", "provider", "status"])

    assert ns.data_cmd == "provider"
    assert ns.provider_cmd == "status"


def test_data_provider_probe_command_parses():
    from trading_os.cli_internal.app import build_parser

    parser = build_parser()
    ns = parser.parse_args(["data", "provider", "probe"])

    assert ns.data_cmd == "provider"
    assert ns.provider_cmd == "probe"


def test_alert_monitor_parser_accepts_watchlist_once_as_of():
    from trading_os.cli_internal.app import build_parser

    parser = build_parser()
    ns = parser.parse_args(
        [
            "alert",
            "monitor",
            "--mode",
            "watchlist",
            "--once",
            "--as-of",
            "2026-06-12",
            "--notify",
            "stdout",
        ]
    )

    assert ns.cmd == "alert"
    assert ns.alert_cmd == "monitor"
    assert ns.mode == "watchlist"
    assert ns.once is True
    assert ns.as_of == "2026-06-12"


def test_alert_monitor_parser_accepts_notify_attempts():
    from trading_os.cli_internal.app import build_parser

    parser = build_parser()
    ns = parser.parse_args(
        [
            "alert",
            "monitor",
            "--mode",
            "watchlist",
            "--once",
            "--notify",
            "webhook",
            "--webhook-url",
            "https://example.invalid/hook",
            "--notify-attempts",
            "3",
        ]
    )

    assert ns.notify == "webhook"
    assert ns.webhook_url == "https://example.invalid/hook"
    assert ns.notify_attempts == 3


def test_alert_monitor_help_describes_watchlist_mode(capsys):
    from trading_os.cli_internal.app import build_parser

    parser = build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["alert", "monitor", "--help"])

    assert exc.value.code == 0
    help_text = capsys.readouterr().out
    assert "watchlist-only alert monitor" in help_text
    assert "--mode {watchlist}" in help_text


def test_alert_monitor_without_once_fails_fast():
    from trading_os.cli_internal.app import build_parser

    parser = build_parser()
    ns = parser.parse_args(["alert", "monitor", "--mode", "watchlist"])

    with pytest.raises(RuntimeError, match="requires --once"):
        ns.func(ns)


def test_alert_monitor_once_writes_alerts_and_event_log(tmp_path, monkeypatch, capsys):
    from trading_os.cli_internal.app import build_parser
    from trading_os.journal.event_log import EventLog
    from trading_os.research import cli as research_cli
    from trading_os.research.datahub import DataHub
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_watchlist_state(
        [
            {
                "symbol": "SSE:600660",
                "as_of": "2026-06-12",
                "status": "watching",
                "pivot_price": 100.0,
                "buy_zone_high": 105.0,
            }
        ]
    )
    store.write_quote_snapshot(
        [{"symbol": "SSE:600660", "close": 102.0}],
        as_of=research_cli.date.fromisoformat("2026-06-12"),
        source="fixture",
    )
    hub = DataHub(store)

    monkeypatch.setattr(research_cli, "build_datahub", lambda: hub)
    monkeypatch.setattr(research_cli, "repo_root", lambda: tmp_path)

    parser = build_parser()
    ns = parser.parse_args(
        [
            "alert",
            "monitor",
            "--mode",
            "watchlist",
            "--once",
            "--as-of",
            "2026-06-12",
            "--notify",
            "stdout",
        ]
    )

    assert ns.func(ns) == 0

    out = capsys.readouterr().out
    assert '"alerts_count": 1' in out
    assert '"deliveries_count": 1' in out
    assert "SSE:600660" in out

    alerts = store.get_alerts(as_of=research_cli.date.fromisoformat("2026-06-12"))
    assert len(alerts) == 1
    assert alerts.iloc[0]["symbol"] == "SSE:600660"
    deliveries = store.get_alert_deliveries(
        as_of=research_cli.date.fromisoformat("2026-06-12")
    )
    assert len(deliveries) == 1
    assert deliveries.iloc[0]["destination"] == "stdout"
    assert bool(deliveries.iloc[0]["success"]) is True

    events = EventLog(tmp_path / "artifacts" / "alerts.db").query(event_type="ALERT")
    assert len(events) == 1
    assert events[0]["payload"]["symbol"] == "SSE:600660"
    delivery_events = EventLog(tmp_path / "artifacts" / "alerts.db").query(
        event_type="ALERT_DELIVERY"
    )
    assert len(delivery_events) == 1
    assert delivery_events[0]["payload"]["destination"] == "stdout"


def test_alert_monitor_uses_latest_watchlist_status_when_json_is_absent(
    tmp_path, monkeypatch, capsys
):
    from trading_os.cli_internal.app import build_parser
    from trading_os.journal.event_log import EventLog
    from trading_os.research import cli as research_cli
    from trading_os.research.datahub import DataHub
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_watchlist_state(
        [
            {
                "symbol": "SSE:600660",
                "as_of": "2026-06-12",
                "status": "invalidated",
            }
        ]
    )
    store.write_watchlist_state(
        [
            {
                "symbol": "SSE:600660",
                "as_of": "2026-06-11",
                "status": "watching",
                "pivot_price": 100.0,
                "buy_zone_high": 105.0,
            }
        ]
    )
    store.write_quote_snapshot(
        [{"symbol": "SSE:600660", "close": 102.0}],
        as_of=research_cli.date.fromisoformat("2026-06-12"),
        source="fixture",
    )
    hub = DataHub(store)

    monkeypatch.setattr(research_cli, "build_datahub", lambda: hub)
    monkeypatch.setattr(research_cli, "repo_root", lambda: tmp_path)

    parser = build_parser()
    ns = parser.parse_args(
        ["alert", "monitor", "--mode", "watchlist", "--once", "--as-of", "2026-06-12"]
    )

    assert ns.func(ns) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["alerts_count"] == 0
    assert store.get_alerts(as_of=research_cli.date.fromisoformat("2026-06-12")).empty
    assert EventLog(tmp_path / "artifacts" / "alerts.db").query(event_type="ALERT") == []


def test_alert_monitor_ignores_stale_exported_watchlist_json(
    tmp_path, monkeypatch, capsys
):
    from trading_os.cli_internal.app import build_parser
    from trading_os.journal.event_log import EventLog
    from trading_os.research import cli as research_cli
    from trading_os.research.datahub import DataHub
    from trading_os.research.store import ResearchStore

    state_path = tmp_path / "artifacts" / "watchlist" / "state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        json.dumps(
            {
                "as_of": "2026-06-13",
                "watchlist_state": [
                    {
                        "symbol": "SSE:600660",
                        "status": "watching",
                        "pivot_price": 100.0,
                        "buy_zone_high": 105.0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    store = ResearchStore(tmp_path / "research")
    store.write_watchlist_state(
        [
            {
                "symbol": "SSE:600660",
                "as_of": "2026-06-13",
                "status": "invalidated",
            }
        ]
    )
    store.write_quote_snapshot(
        [{"symbol": "SSE:600660", "close": 102.0}],
        as_of=research_cli.date.fromisoformat("2026-06-13"),
        source="fixture",
    )
    hub = DataHub(store)

    monkeypatch.setattr(research_cli, "build_datahub", lambda: hub)
    monkeypatch.setattr(research_cli, "repo_root", lambda: tmp_path)

    parser = build_parser()
    ns = parser.parse_args(
        ["alert", "monitor", "--mode", "watchlist", "--once", "--as-of", "2026-06-13"]
    )

    assert ns.func(ns) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["alerts_count"] == 0
    assert store.get_alerts(as_of=research_cli.date.fromisoformat("2026-06-13")).empty
    assert EventLog(tmp_path / "artifacts" / "alerts.db").query(event_type="ALERT") == []
