from __future__ import annotations

from datetime import date

import pytest

pd = pytest.importorskip("pandas")


def test_research_store_writes_and_reads_decisions(tmp_path):
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")

    path = store.write_decisions(
        [
            {
                "symbol": "SSE:600000",
                "as_of": date(2026, 6, 12),
                "decision": "watch",
                "reason": "strict_canslim_candidate",
            }
        ]
    )
    decisions = store.get_decisions()

    assert path.exists()
    assert decisions["symbol"].tolist() == ["SSE:600000"]
    assert decisions["decision"].tolist() == ["watch"]
    assert "fetched_at" in decisions.columns


def test_research_store_filters_decisions_at_or_before_as_of(tmp_path):
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_decisions(
        [
            {"symbol": "SSE:600000", "as_of": date(2026, 6, 12), "decision": "watch"},
            {"symbol": "SZSE:000001", "as_of": date(2026, 6, 15), "decision": "reject"},
        ]
    )

    decisions = store.get_decisions(as_of=date(2026, 6, 12))

    assert decisions["symbol"].tolist() == ["SSE:600000"]


def test_research_store_writes_and_reads_watchlist_state(tmp_path):
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")

    path = store.write_watchlist_state(
        [
            {
                "symbol": "SSE:600000",
                "as_of": date(2026, 6, 12),
                "state": "active",
                "entry_source": "daily_canslim",
            }
        ]
    )
    watchlist = store.get_watchlist_state()

    assert path.exists()
    assert watchlist["symbol"].tolist() == ["SSE:600000"]
    assert watchlist["state"].tolist() == ["active"]
    assert "fetched_at" in watchlist.columns


def test_research_store_filters_watchlist_state_at_or_before_as_of(tmp_path):
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_watchlist_state(
        [
            {"symbol": "SSE:600000", "as_of": date(2026, 6, 12), "state": "active"},
            {"symbol": "SZSE:000001", "as_of": date(2026, 6, 15), "state": "active"},
        ]
    )

    watchlist = store.get_watchlist_state(as_of=date(2026, 6, 12))

    assert watchlist["symbol"].tolist() == ["SSE:600000"]


def test_research_store_writes_and_reads_alerts(tmp_path):
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")

    path = store.write_alerts(
        [
            {
                "symbol": "SSE:600000",
                "as_of": date(2026, 6, 12),
                "alert_type": "breakout_volume",
                "severity": "high",
            }
        ]
    )
    alerts = store.get_alerts()

    assert path.exists()
    assert alerts["symbol"].tolist() == ["SSE:600000"]
    assert alerts["alert_type"].tolist() == ["breakout_volume"]
    assert "fetched_at" in alerts.columns


def test_research_store_filters_alerts_at_or_before_as_of(tmp_path):
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_alerts(
        [
            {"symbol": "SSE:600000", "as_of": date(2026, 6, 12), "alert_type": "buy_zone"},
            {
                "symbol": "SZSE:000001",
                "as_of": date(2026, 6, 15),
                "alert_type": "breakout_volume",
            },
        ]
    )

    alerts = store.get_alerts(as_of=date(2026, 6, 12))

    assert alerts["symbol"].tolist() == ["SSE:600000"]


def test_research_store_writes_and_reads_technical_setups(tmp_path):
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")

    path = store.write_technical_setups(
        [
            {
                "symbol": "SSE:600000",
                "as_of": date(2026, 6, 12),
                "setup": "cup_with_handle",
                "pivot": 18.5,
            }
        ]
    )
    setups = store.get_technical_setups()

    assert path.exists()
    assert setups["symbol"].tolist() == ["SSE:600000"]
    assert setups["setup"].tolist() == ["cup_with_handle"]
    assert "fetched_at" in setups.columns


def test_research_store_filters_technical_setups_at_or_before_as_of(tmp_path):
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_technical_setups(
        [
            {"symbol": "SSE:600000", "as_of": date(2026, 6, 12), "setup": "flat_base"},
            {"symbol": "SZSE:000001", "as_of": date(2026, 6, 15), "setup": "breakout"},
        ]
    )

    setups = store.get_technical_setups(as_of=date(2026, 6, 12))

    assert setups["symbol"].tolist() == ["SSE:600000"]


def test_research_store_event_reads_are_ordered_by_fetched_at(tmp_path):
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    dataset_path = tmp_path / "research" / "datasets" / "watchlist_state"
    dataset_path.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "symbol": "SSE:600000",
                "as_of": "2026-06-12",
                "state": "newer",
                "fetched_at": "2026-06-12T10:00:01+00:00",
            }
        ]
    ).to_parquet(dataset_path / "a-newer.parquet", index=False)
    pd.DataFrame(
        [
            {
                "symbol": "SZSE:000001",
                "as_of": "2026-06-12",
                "state": "older",
                "fetched_at": "2026-06-12T10:00:00+00:00",
            }
        ]
    ).to_parquet(dataset_path / "b-older.parquet", index=False)

    watchlist = store.get_watchlist_state()

    assert watchlist["state"].tolist() == ["older", "newer"]


def test_research_store_event_empty_input_returns_unwritten_path(tmp_path):
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")

    path = store.write_decisions([])

    assert path == tmp_path / "research" / "datasets" / "decisions" / "empty.parquet"
    assert not path.exists()
    assert store.get_decisions().empty
