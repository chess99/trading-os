from __future__ import annotations


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

    current = [{"symbol": "SSE:600000", "status": "watching", "pivot_price": 12.0}]
    decisions = [{"symbol": "SSE:600000", "decision": "reject", "source_run_id": "run-2"}]

    state = update_watchlist_from_decisions(current, decisions)

    assert state[0]["status"] == "invalidated"
    assert state[0]["source_run_id"] == "run-2"
    assert state[0]["last_decision"] == "reject"
    assert state[0]["pivot_price"] == 12.0


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
    assert state[1]["pivot_price"] == 10.0
