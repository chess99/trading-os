from __future__ import annotations

import pytest


def test_watchlist_state_created_from_wait_for_breakout_decision():
    from trading_os.research.watchlist import update_watchlist_from_decisions

    current = []
    decisions = [
        {
            "symbol": "SSE:600000",
            "as_of": "2026-06-12",
            "decision": "wait_for_breakout",
            "pivot_price": 12.0,
            "buy_zone_high": 12.6,
            "stop_loss": 11.04,
            "source_run_id": "run-1",
        }
    ]

    state = update_watchlist_from_decisions(current, decisions)

    assert state[0]["symbol"] == "SSE:600000"
    assert state[0]["status"] == "watching"
    assert state[0]["pivot_price"] == 12.0
    assert state[0]["source_run_id"] == "run-1"
    assert state[0]["last_decision"] == "wait_for_breakout"


def test_reject_decision_invalidates_existing_watchlist_entry():
    from trading_os.research.watchlist import update_watchlist_from_decisions

    current = [
        {
            "symbol": "SSE:600000",
            "status": "watching",
            "pivot_price": 12.0,
            "buy_zone_high": 12.6,
            "stop_loss": 11.04,
        }
    ]
    decisions = [{"symbol": "SSE:600000", "decision": "reject", "source_run_id": "run-2"}]

    state = update_watchlist_from_decisions(current, decisions)

    assert state[0]["status"] == "invalidated"
    assert state[0]["source_run_id"] == "run-2"
    assert state[0]["last_decision"] == "reject"
    assert "pivot_price" not in state[0]
    assert "buy_zone_high" not in state[0]
    assert "stop_loss" not in state[0]


def test_actionable_watch_updates_existing_row_and_preserves_unwritten_fields():
    from trading_os.research.watchlist import update_watchlist_from_decisions

    current = [
        {
            "symbol": "SSE:600000",
            "status": "watching",
            "pivot_price": 11.5,
            "notes": "keep this",
        }
    ]
    decisions = [
        {
            "symbol": "SSE:600000",
            "decision": "actionable_watch",
            "pivot_price": 12.0,
            "buy_zone_high": 12.6,
            "stop_loss": 11.04,
            "source_run_id": "run-3",
        }
    ]

    state = update_watchlist_from_decisions(current, decisions)

    assert state == [
        {
            "symbol": "SSE:600000",
            "status": "actionable",
            "pivot_price": 12.0,
            "notes": "keep this",
            "buy_zone_high": 12.6,
            "stop_loss": 11.04,
            "source_run_id": "run-3",
            "last_decision": "actionable_watch",
        }
    ]


def test_research_only_creates_candidate_without_technical_levels():
    from trading_os.research.watchlist import update_watchlist_from_decisions

    decisions = [
        {
            "symbol": "SZSE:000001",
            "decision": "research_only",
            "pivot_price": 20.0,
            "buy_zone_high": 21.0,
            "stop_loss": 18.4,
            "source_run_id": "run-4",
        }
    ]

    state = update_watchlist_from_decisions([], decisions)

    assert state == [
        {
            "symbol": "SZSE:000001",
            "status": "candidate",
            "source_run_id": "run-4",
            "last_decision": "research_only",
        }
    ]


def test_research_only_clears_stale_technical_levels():
    from trading_os.research.watchlist import update_watchlist_from_decisions

    current = [
        {
            "symbol": "SSE:600000",
            "status": "actionable",
            "pivot_price": 12.0,
            "buy_zone_high": 12.6,
            "stop_loss": 11.04,
            "notes": "preserve",
        }
    ]
    decisions = [
        {
            "symbol": "SSE:600000",
            "decision": "research_only",
            "source_run_id": "run-5",
        }
    ]

    state = update_watchlist_from_decisions(current, decisions)

    assert state == [
        {
            "symbol": "SSE:600000",
            "status": "candidate",
            "notes": "preserve",
            "source_run_id": "run-5",
            "last_decision": "research_only",
        }
    ]


def test_malformed_missing_or_blank_symbols_are_skipped():
    from trading_os.research.watchlist import update_watchlist_from_decisions

    current = [
        {"status": "watching", "notes": "missing symbol"},
        {"symbol": "   ", "status": "watching"},
        {"symbol": "SSE:600000", "status": "watching"},
    ]
    decisions = [
        {"decision": "reject", "source_run_id": "run-5"},
        {"symbol": "", "decision": "wait_for_breakout", "source_run_id": "run-5"},
        {"symbol": "   ", "decision": "research_only", "source_run_id": "run-5"},
        {"symbol": "SZSE:000001", "decision": "research_only", "source_run_id": "run-5"},
    ]

    state = update_watchlist_from_decisions(current, decisions)

    assert [row["symbol"] for row in state] == ["SSE:600000", "SZSE:000001"]
    assert state[1]["status"] == "candidate"


def test_duplicate_decisions_last_decision_wins_deterministically():
    from trading_os.research.watchlist import update_watchlist_from_decisions

    current = [{"symbol": "SZSE:000001", "status": "watching"}]
    decisions = [
        {
            "symbol": "SZSE:000001",
            "decision": "wait_for_breakout",
            "pivot_price": 10.0,
            "buy_zone_high": 10.5,
            "stop_loss": 9.2,
            "source_run_id": "run-1",
        },
        {
            "symbol": "SSE:600000",
            "decision": "research_only",
            "source_run_id": "run-2",
        },
        {
            "symbol": "SZSE:000001",
            "decision": "reject",
            "source_run_id": "run-3",
        },
    ]

    state = update_watchlist_from_decisions(current, decisions)

    assert [row["symbol"] for row in state] == ["SSE:600000", "SZSE:000001"]
    assert state[1]["status"] == "invalidated"
    assert state[1]["source_run_id"] == "run-3"
    assert state[1]["last_decision"] == "reject"
    assert "pivot_price" not in state[1]
    assert "buy_zone_high" not in state[1]
    assert "stop_loss" not in state[1]


@pytest.mark.parametrize(
    "decision",
    [
        {
            "symbol": "SSE:600000",
            "decision": "wait_for_breakout",
            "buy_zone_high": 12.6,
            "stop_loss": 11.04,
        },
        {
            "symbol": "SSE:600000",
            "decision": "actionable_watch",
            "pivot_price": "bad",
            "buy_zone_high": 12.6,
            "stop_loss": 11.04,
        },
        {
            "symbol": "SSE:600000",
            "decision": "wait_for_breakout",
            "pivot_price": float("nan"),
            "buy_zone_high": 12.6,
            "stop_loss": 11.04,
        },
        {
            "symbol": "SSE:600000",
            "decision": "actionable_watch",
            "pivot_price": 0.0,
            "buy_zone_high": 12.6,
            "stop_loss": 11.04,
        },
        {
            "symbol": "SSE:600000",
            "decision": "wait_for_breakout",
            "pivot_price": 12.0,
            "buy_zone_high": -12.6,
            "stop_loss": 11.04,
        },
        {
            "symbol": "SSE:600000",
            "decision": "actionable_watch",
            "pivot_price": 12.0,
            "buy_zone_high": 12.6,
            "stop_loss": None,
        },
    ],
)
def test_invalid_actionable_decisions_downgrade_and_clear_levels(decision):
    from trading_os.research.watchlist import update_watchlist_from_decisions

    current = [
        {
            "symbol": "SSE:600000",
            "status": "watching",
            "pivot_price": 11.5,
            "buy_zone_high": 12.075,
            "stop_loss": 10.58,
            "notes": "keep",
        }
    ]
    decision["source_run_id"] = "run-invalid"

    state = update_watchlist_from_decisions(current, [decision])

    assert state == [
        {
            "symbol": "SSE:600000",
            "status": "candidate",
            "notes": "keep",
            "source_run_id": "run-invalid",
            "last_decision": decision["decision"],
        }
    ]


def test_alert_monitor_only_alerts_watchlist_breakouts():
    from trading_os.research.alerts import evaluate_watchlist_alerts

    watchlist = [
        {
            "symbol": "SSE:600000",
            "status": "watching",
            "pivot_price": 12.0,
            "buy_zone_high": 12.6,
            "stop_loss": 11.04,
        }
    ]
    quotes = [
        {"symbol": "SSE:600000", "close": 12.2, "volume": 2_000_000.0},
        {"symbol": "SSE:600001", "close": 30.0, "volume": 9_000_000.0},
    ]

    alerts = evaluate_watchlist_alerts(
        watchlist, quotes, as_of="2026-06-12T10:30:00+08:00", existing_cooldowns=set()
    )

    assert len(alerts) == 1
    alert = alerts[0]
    assert set(alert) == {
        "alert_id",
        "symbol",
        "as_of",
        "trigger_type",
        "trigger_value",
        "pivot_price",
        "status",
        "cooldown_key",
    }
    assert alert["alert_id"].startswith("alert-")
    assert alert["symbol"] == "SSE:600000"
    assert alert["as_of"] == "2026-06-12T10:30:00+08:00"
    assert alert["trigger_type"] == "breakout_confirmed"
    assert alert["trigger_value"] == 12.2
    assert alert["pivot_price"] == 12.0
    assert alert["status"] == "pending"
    assert alert["cooldown_key"] == "SSE:600000:breakout_confirmed:2026-06-12"


def test_alert_monitor_alerts_actionable_status_at_pivot():
    from trading_os.research.alerts import evaluate_watchlist_alerts

    watchlist = [{"symbol": "SSE:600000", "status": "actionable", "pivot_price": 12.0}]
    quotes = [{"symbol": "SSE:600000", "close": 12.0}]

    alerts = evaluate_watchlist_alerts(
        watchlist, quotes, as_of="2026-06-12T10:30:00+08:00", existing_cooldowns=set()
    )

    assert len(alerts) == 1
    assert alerts[0]["trigger_value"] == 12.0


def test_alert_monitor_deduplicates_by_cooldown_key():
    from trading_os.research.alerts import evaluate_watchlist_alerts

    watchlist = [{"symbol": "SSE:600000", "status": "watching", "pivot_price": 12.0}]
    quotes = [{"symbol": "SSE:600000", "close": 12.2}]

    alerts = evaluate_watchlist_alerts(
        watchlist,
        quotes,
        as_of="2026-06-12T10:30:00+08:00",
        existing_cooldowns={"SSE:600000:breakout_confirmed:2026-06-12"},
    )

    assert alerts == []


def test_alert_monitor_deduplicates_duplicate_watchlist_rows_in_same_evaluation():
    from trading_os.research.alerts import evaluate_watchlist_alerts

    watchlist = [
        {"symbol": "SSE:600000", "status": "watching", "pivot_price": 12.0},
        {"symbol": "SSE:600000", "status": "watching", "pivot_price": 12.0},
    ]
    quotes = [{"symbol": "SSE:600000", "close": 12.2}]

    alerts = evaluate_watchlist_alerts(
        watchlist, quotes, as_of="2026-06-12T10:30:00+08:00", existing_cooldowns=set()
    )

    assert len(alerts) == 1


def test_alert_monitor_uses_valid_buy_zone_high_as_upper_bound():
    from trading_os.research.alerts import evaluate_watchlist_alerts

    watchlist = [
        {
            "symbol": "SSE:600000",
            "status": "watching",
            "pivot_price": 12.0,
            "buy_zone_high": 12.6,
        }
    ]
    quotes = [{"symbol": "SSE:600000", "close": 12.7}]

    alerts = evaluate_watchlist_alerts(
        watchlist, quotes, as_of="2026-06-12T10:30:00+08:00", existing_cooldowns=set()
    )

    assert alerts == []


@pytest.mark.parametrize("buy_zone_high", [None, "bad", float("nan"), 0.0])
def test_alert_monitor_falls_back_to_pivot_when_buy_zone_high_missing_or_invalid(buy_zone_high):
    from trading_os.research.alerts import evaluate_watchlist_alerts

    watchlist = [
        {
            "symbol": "SSE:600000",
            "status": "watching",
            "pivot_price": 12.0,
            "buy_zone_high": buy_zone_high,
        }
    ]
    quotes = [{"symbol": "SSE:600000", "close": 12.7}]

    alerts = evaluate_watchlist_alerts(
        watchlist, quotes, as_of="2026-06-12T10:30:00+08:00", existing_cooldowns=set()
    )

    assert len(alerts) == 1


def test_alert_monitor_cooldown_date_uses_china_trading_date_for_aware_datetime():
    from trading_os.research.alerts import evaluate_watchlist_alerts

    watchlist = [{"symbol": "SSE:600000", "status": "watching", "pivot_price": 12.0}]
    quotes = [{"symbol": "SSE:600000", "close": 12.2}]

    alerts = evaluate_watchlist_alerts(
        watchlist, quotes, as_of="2026-06-11T16:30:00+00:00", existing_cooldowns=set()
    )

    assert alerts[0]["cooldown_key"] == "SSE:600000:breakout_confirmed:2026-06-12"


def test_alert_monitor_cooldown_date_normalizes_space_separated_aware_datetime():
    from trading_os.research.alerts import evaluate_watchlist_alerts

    watchlist = [{"symbol": "SSE:600000", "status": "watching", "pivot_price": 12.0}]
    quotes = [{"symbol": "SSE:600000", "close": 12.2}]

    alerts = evaluate_watchlist_alerts(
        watchlist, quotes, as_of="2026-06-11 16:30:00+00:00", existing_cooldowns=set()
    )

    assert alerts[0]["cooldown_key"] == "SSE:600000:breakout_confirmed:2026-06-12"


def test_alert_monitor_ignores_non_watchlist_quotes():
    from trading_os.research.alerts import evaluate_watchlist_alerts

    alerts = evaluate_watchlist_alerts(
        watchlist=[],
        quotes=[{"symbol": "SSE:600000", "close": 12.2}],
        as_of="2026-06-12T10:30:00+08:00",
        existing_cooldowns=set(),
    )

    assert alerts == []


@pytest.mark.parametrize("status", ["candidate", "invalidated", "rejected", None])
def test_alert_monitor_ignores_non_watch_statuses(status):
    from trading_os.research.alerts import evaluate_watchlist_alerts

    watchlist = [{"symbol": "SSE:600000", "status": status, "pivot_price": 12.0}]
    quotes = [{"symbol": "SSE:600000", "close": 12.2}]

    alerts = evaluate_watchlist_alerts(
        watchlist, quotes, as_of="2026-06-12T10:30:00+08:00", existing_cooldowns=set()
    )

    assert alerts == []


@pytest.mark.parametrize(
    ("watchlist_row", "quote_row"),
    [
        ({"status": "watching", "pivot_price": 12.0}, {"symbol": "SSE:600000", "close": 12.2}),
        ({"symbol": "", "status": "watching", "pivot_price": 12.0}, {"symbol": "", "close": 12.2}),
        (
            {"symbol": "SSE:600000", "status": "watching"},
            {"symbol": "SSE:600000", "close": 12.2},
        ),
        (
            {"symbol": "SSE:600000", "status": "watching", "pivot_price": "bad"},
            {"symbol": "SSE:600000", "close": 12.2},
        ),
        (
            {"symbol": "SSE:600000", "status": "watching", "pivot_price": float("nan")},
            {"symbol": "SSE:600000", "close": 12.2},
        ),
        (
            {"symbol": "SSE:600000", "status": "watching", "pivot_price": 0.0},
            {"symbol": "SSE:600000", "close": 12.2},
        ),
        (
            {"symbol": "SSE:600000", "status": "watching", "pivot_price": 12.0},
            {"symbol": "SSE:600000"},
        ),
        (
            {"symbol": "SSE:600000", "status": "watching", "pivot_price": 12.0},
            {"symbol": "SSE:600000", "close": "bad"},
        ),
        (
            {"symbol": "SSE:600000", "status": "watching", "pivot_price": 12.0},
            {"symbol": "SSE:600000", "close": float("inf")},
        ),
        (
            {"symbol": "SSE:600000", "status": "watching", "pivot_price": 12.0},
            {"symbol": "SSE:600000", "close": 0.0},
        ),
    ],
)
def test_alert_monitor_ignores_missing_or_bad_values(watchlist_row, quote_row):
    from trading_os.research.alerts import evaluate_watchlist_alerts

    alerts = evaluate_watchlist_alerts(
        [watchlist_row],
        [quote_row],
        as_of="2026-06-12T10:30:00+08:00",
        existing_cooldowns=set(),
    )

    assert alerts == []
