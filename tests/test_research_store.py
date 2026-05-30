from __future__ import annotations

from datetime import date

import pytest

pd = pytest.importorskip("pandas")


def test_research_store_queries_latest_snapshot_at_or_before_as_of(tmp_path):
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_universe(
        pd.DataFrame(
            [
                {
                    "symbol": "SSE:600000",
                    "name": "Old",
                    "exchange": "SSE",
                    "is_st": False,
                    "is_active": True,
                },
            ]
        ),
        as_of=date(2026, 5, 28),
        source="fixture",
        provenance={"fixture": "old"},
    )
    store.write_universe(
        pd.DataFrame(
            [
                {
                    "symbol": "SSE:600000",
                    "name": "New",
                    "exchange": "SSE",
                    "is_st": False,
                    "is_active": True,
                },
                {
                    "symbol": "SZSE:000001",
                    "name": "PingAn",
                    "exchange": "SZSE",
                    "is_st": False,
                    "is_active": True,
                },
            ]
        ),
        as_of=date(2026, 5, 30),
        source="fixture",
        provenance={"fixture": "new"},
    )

    before = store.get_universe(as_of=date(2026, 5, 29))
    current = store.get_universe(as_of=date(2026, 5, 30))

    assert before["symbol"].tolist() == ["SSE:600000"]
    assert before.iloc[0]["name"] == "Old"
    assert sorted(current["symbol"].tolist()) == ["SSE:600000", "SZSE:000001"]
    assert current[current["symbol"] == "SSE:600000"].iloc[0]["name"] == "New"


def test_research_store_bars_are_strictly_before_trading_date(tmp_path):
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_bars(
        pd.DataFrame(
            [
                {
                    "symbol": "SSE:600000",
                    "ts": "2026-05-27",
                    "open": 10,
                    "high": 11,
                    "low": 9,
                    "close": 10,
                    "volume": 1000,
                },
                {
                    "symbol": "SSE:600000",
                    "ts": "2026-05-28",
                    "open": 11,
                    "high": 12,
                    "low": 10,
                    "close": 11,
                    "volume": 1000,
                },
            ]
        ),
        source="fixture",
        provenance={"fixture": "bars"},
    )

    bars = store.get_bars(["SSE:600000"], start=date(2026, 5, 1), end=date(2026, 5, 28))

    assert bars["ts"].dt.date.tolist() == [date(2026, 5, 27)]


def test_research_store_writes_run_artifacts(tmp_path):
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    run = store.start_run("canslim_screen", inputs={"as_of": "2026-05-30"})
    store.write_run_artifacts(
        run,
        manifest={"recipe": "canslim_screen", "steps": [{"name": "load"}]},
        trace_lines=["loaded fixture data"],
        report="# Report\n",
        tables={"candidates": pd.DataFrame([{"symbol": "SSE:600000"}])},
    )

    assert (run.path / "manifest.json").exists()
    assert (run.path / "trace.md").read_text(encoding="utf-8") == "loaded fixture data\n"
    assert (run.path / "report.md").read_text(encoding="utf-8") == "# Report\n"
    assert (run.path / "tables" / "candidates.csv").exists()
