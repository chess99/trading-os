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


class FailingBarsProvider(RecipeProvider):
    def fetch_bars(self, symbols, start, end, adjustment):
        self.bars_calls.append(list(symbols))
        raise RuntimeError("bars source unavailable")


class EnrichingFundamentalsProvider(RecipeProvider):
    def __init__(self) -> None:
        super().__init__()
        self.fundamental_calls: list[list[str]] = []

    def fetch_fundamentals(self, symbols, as_of, periods):
        self.fundamental_calls.append(list(symbols))
        return pd.DataFrame(
            [
                {
                    "symbol": "SSE:600000",
                    "period": "2026Q1",
                    "eps_growth_yoy": 0.35,
                    "roe": 0.22,
                    "positive_quarters": 8,
                }
            ]
        )


class ManyCandidatesProvider(RecipeProvider):
    def fetch_universe(self, as_of: date):
        return pd.DataFrame(
            [
                {
                    "symbol": f"SSE:60000{i}",
                    "name": f"Candidate {i}",
                    "exchange": "SSE",
                    "is_st": False,
                    "is_active": True,
                }
                for i in range(5)
            ]
        )

    def fetch_quote_snapshot(self, as_of: date):
        return pd.DataFrame(
            [
                {
                    "symbol": f"SSE:60000{i}",
                    "close": 10.0 + i,
                    "volume": 2_000_000.0,
                    "amount": 40_000_000.0,
                }
                for i in range(5)
            ]
        )

    def fetch_bars(self, symbols, start, end, adjustment):
        self.bars_calls.append(list(symbols))
        rows = []
        for idx, sym in enumerate(symbols):
            for i, ts in enumerate(pd.date_range("2025-05-01", periods=260, freq="B")):
                base = 10 + i * (0.01 + idx * 0.01)
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


def test_canslim_screen_marks_missing_quarter_history_as_provisional(tmp_path):
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

    assert [candidate["symbol"] for candidate in result.candidates] == ["SSE:600000"]
    assert result.candidates[0]["classification"] == "provisional_research_queue"
    assert result.candidates[0]["signals"]["positive_quarters"] is None
    assert "positive_quarters" in result.candidates[0]["missing_fields"]
    assert result.filtered_out["insufficient_data"] == 2
    assert result.filtered_out["no_signal"] == 0
    assert provider.bars_calls == [["SSE:600000"]]
    assert result.manifest["strict_candidates_total"] == 0
    assert result.manifest["provisional_candidates_total"] == 1
    report = (result.run.path / "report.md").read_text(encoding="utf-8")
    assert "Strict CANSLIM Candidates: 0" in report
    assert "Provisional Research Queue: 1" in report


def test_canslim_screen_enriches_missing_quarter_history_when_provider_supports_it(tmp_path):
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
    )
    provider = EnrichingFundamentalsProvider()
    hub = DataHub(store, provider=provider)

    result = run_canslim_screen(hub, as_of=date(2026, 5, 30), top_n=10, min_turnover=1)

    assert provider.fundamental_calls == [["SSE:600000"]]
    assert [candidate["symbol"] for candidate in result.candidates] == ["SSE:600000"]
    assert result.candidates[0]["classification"] == "strict_canslim_candidate"
    assert result.candidates[0]["signals"]["positive_quarters"] == 8
    assert result.manifest["strict_candidates_total"] == 1
    assert result.manifest["provisional_candidates_total"] == 0


def test_canslim_screen_top_n_only_limits_displayed_candidates(tmp_path):
    from trading_os.research.datahub import DataHub
    from trading_os.research.recipes import run_canslim_screen
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_fundamentals(
        pd.DataFrame(
            [
                {
                    "symbol": f"SSE:60000{i}",
                    "period": "2026Q1",
                    "eps_growth_yoy": 0.35 + i * 0.01,
                    "roe": 0.22,
                    "positive_quarters": 8,
                }
                for i in range(5)
            ]
        ),
        as_of=date(2026, 5, 30),
        source="fixture",
    )
    provider = ManyCandidatesProvider()
    hub = DataHub(store, provider=provider)

    result = run_canslim_screen(hub, as_of=date(2026, 5, 30), top_n=2, min_turnover=1)

    assert len(result.candidates) == 2
    assert result.manifest["candidates_total"] == 5
    assert result.manifest["displayed_candidates_total"] == 2
    all_candidates = pd.read_csv(result.run.path / "tables" / "all_candidates.csv")
    displayed_candidates = pd.read_csv(result.run.path / "tables" / "candidates.csv")
    assert len(all_candidates) == 5
    assert len(displayed_candidates) == 2
    report = (result.run.path / "report.md").read_text(encoding="utf-8")
    assert "Total Qualified Candidates: 5" in report
    assert "Displayed Candidates: 2" in report


def test_canslim_screen_skips_bars_for_core_fundamental_failures(tmp_path):
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
                    "eps_growth_yoy": 0.10,
                    "roe": 0.22,
                    "positive_quarters": 8,
                }
            ]
        ),
        as_of=date(2026, 5, 30),
        source="fixture",
    )
    provider = RecipeProvider()
    hub = DataHub(store, provider=provider)

    result = run_canslim_screen(hub, as_of=date(2026, 5, 30), top_n=10, min_turnover=1)

    assert result.candidates == []
    assert result.filtered_out["no_signal"] == 1
    assert result.filtered_out["insufficient_data"] == 1
    assert provider.bars_calls == []


def test_canslim_screen_does_not_abort_when_rs_bars_are_unavailable(tmp_path):
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
                    "positive_quarters": 8,
                }
            ]
        ),
        as_of=date(2026, 5, 30),
        source="fixture",
    )
    provider = FailingBarsProvider()
    hub = DataHub(store, provider=provider)

    result = run_canslim_screen(hub, as_of=date(2026, 5, 30), top_n=10, min_turnover=1)

    assert [candidate["symbol"] for candidate in result.candidates] == ["SSE:600000"]
    assert result.candidates[0]["classification"] == "provisional_research_queue"
    assert "relative_strength" in result.candidates[0]["missing_fields"]
    assert result.manifest["strict_candidates_total"] == 0
    assert result.manifest["provisional_candidates_total"] == 1
    assert "RS bars unavailable" in result.manifest["limitations"][0]


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
