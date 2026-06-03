from __future__ import annotations

from datetime import date

import pytest

pd = pytest.importorskip("pandas")


class RecipeProvider:
    def __init__(self) -> None:
        self.bars_calls: list[list[str]] = []

    def fetch_universe(self, as_of: date):
        return pd.DataFrame(
            [
                {
                    "symbol": "SSE:600000",
                    "name": "A",
                    "exchange": "SSE",
                    "is_st": False,
                    "is_active": True,
                },
                {
                    "symbol": "SSE:600001",
                    "name": "B",
                    "exchange": "SSE",
                    "is_st": False,
                    "is_active": True,
                },
                {
                    "symbol": "SSE:600002",
                    "name": "ST C",
                    "exchange": "SSE",
                    "is_st": True,
                    "is_active": True,
                },
            ]
        )

    def fetch_quote_snapshot(self, as_of: date):
        return pd.DataFrame(
            [
                {
                    "symbol": "SSE:600000",
                    "close": 20.0,
                    "volume": 2_000_000.0,
                    "amount": 40_000_000.0,
                },
                {
                    "symbol": "SSE:600001",
                    "close": 10.0,
                    "volume": 2_000_000.0,
                    "amount": 20_000_000.0,
                },
                {
                    "symbol": "SSE:600002",
                    "close": 10.0,
                    "volume": 2_000_000.0,
                    "amount": 20_000_000.0,
                },
            ]
        )

    def fetch_bars(self, symbols, start, end, adjustment):
        self.bars_calls.append(list(symbols))
        rows = []
        for sym in symbols:
            for i, ts in enumerate(pd.date_range("2025-05-01", periods=260, freq="B")):
                base = 10 + i * (0.05 if sym == "SSE:600000" else 0.01)
                rows.append(
                    {
                        "symbol": sym,
                        "ts": ts,
                        "open": base,
                        "high": base,
                        "low": base,
                        "close": base,
                        "volume": 1_000_000.0,
                    }
                )
        return pd.DataFrame(rows)


def _fundamentals():
    return pd.DataFrame(
        [
            {
                "symbol": "SSE:600000",
                "period": "2026Q1",
                "eps_growth_yoy": 0.35,
                "roe": 0.22,
                "positive_quarters": 10,
            },
            {
                "symbol": "SSE:600001",
                "period": "2026Q1",
                "eps_growth_yoy": 0.05,
                "roe": 0.25,
                "positive_quarters": 10,
            },
        ]
    )


def test_canslim_screen_uses_snapshots_and_lazy_bars_without_bulk_refresh(tmp_path):
    from trading_os.research.datahub import DataHub
    from trading_os.research.recipes import run_canslim_screen
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_fundamentals(
        _fundamentals(),
        as_of=date(2026, 5, 30),
        source="fixture",
        provenance={"fixture": "fundamentals"},
    )
    provider = RecipeProvider()
    hub = DataHub(store, provider=provider)

    result = run_canslim_screen(hub, as_of=date(2026, 5, 30), top_n=10, min_turnover=1)

    assert [c["symbol"] for c in result.candidates] == ["SSE:600000"]
    assert result.filtered_out["st_or_inactive"] == 1
    assert result.filtered_out["no_signal"] == 1
    assert provider.bars_calls == [["SSE:600000"]]
    assert (result.run.path / "manifest.json").exists()
    assert (result.run.path / "report.md").exists()


def test_canslim_screen_skips_bars_when_fundamental_filters_fail(tmp_path):
    from trading_os.research.datahub import DataHub
    from trading_os.research.recipes import run_canslim_screen
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_fundamentals(
        pd.DataFrame(
            [
                {
                    "symbol": "SSE:600000",
                    "period": "2026Q1",
                    "eps_growth_yoy": 0.35,
                    "roe": 0.22,
                }
            ]
        ),
        as_of=date(2026, 5, 30),
        source="fixture",
        provenance={"fixture": "fundamentals_missing_positive_quarters"},
    )
    provider = RecipeProvider()
    hub = DataHub(store, provider=provider)

    result = run_canslim_screen(hub, as_of=date(2026, 5, 30), top_n=10, min_turnover=1)

    assert result.candidates == []
    assert result.filtered_out["no_signal"] == 1
    assert provider.bars_calls == []
    assert "skip RS bars" in (result.run.path / "trace.md").read_text(encoding="utf-8")


def test_company_factor_backtest_and_daily_recipes_write_run_artifacts(tmp_path):
    from trading_os.research.datahub import DataHub
    from trading_os.research.recipes import (
        run_backtest_recipe,
        run_company_research,
        run_daily_research,
        run_factor_research,
    )
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_universe(
        pd.DataFrame(
            [
                {
                    "symbol": "SSE:600000",
                    "name": "福耀玻璃",
                    "exchange": "SSE",
                    "is_st": False,
                    "is_active": True,
                }
            ]
        ),
        as_of=date(2026, 5, 30),
        source="fixture",
    )
    store.write_quote_snapshot(
        pd.DataFrame(
            [{"symbol": "SSE:600000", "close": 55.0, "volume": 1_000_000.0, "amount": 55_000_000.0}]
        ),
        as_of=date(2026, 5, 30),
        source="fixture",
    )
    store.write_fundamentals(
        pd.DataFrame(
            [
                {
                    "symbol": "SSE:600000",
                    "period": "2026Q1",
                    "eps_growth_yoy": 0.3,
                    "roe": 0.2,
                    "positive_quarters": 8,
                }
            ]
        ),
        as_of=date(2026, 5, 30),
        source="fixture",
    )
    hub = DataHub(store, provider=RecipeProvider())

    company = run_company_research(
        hub, "SSE:600000", as_of=date(2026, 5, 30), template="quality_growth"
    )
    factor = run_factor_research(hub, as_of=date(2026, 5, 30), factor_name="momentum_roe")
    backtest = run_backtest_recipe(
        hub, start=date(2026, 5, 1), end=date(2026, 5, 30), strategy_name="smoke"
    )
    daily = run_daily_research(hub, as_of=date(2026, 5, 30))

    for result in [company, factor, backtest, daily]:
        assert (result.run.path / "manifest.json").exists()
        assert (result.run.path / "trace.md").exists()
        assert (result.run.path / "report.md").exists()
