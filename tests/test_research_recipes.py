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


class CompanyEnrichmentProvider(EnrichingFundamentalsProvider):
    def fetch_estimates(self, symbols, as_of):
        return pd.DataFrame(
            [
                {"symbol": symbol, "target_price": 30.0, "estimate_date": "2026-06-01"}
                for symbol in symbols
            ]
        )

    def fetch_news(self, symbols, as_of, lookback_months):
        return pd.DataFrame(
            [
                {
                    "symbol": symbol,
                    "title": "公告订单增长",
                    "published_at": "2026-06-01T09:00:00+08:00",
                    "source_url": "https://example.test/news",
                }
                for symbol in symbols
            ]
        )

    def fetch_segments(self, symbols, as_of):
        return pd.DataFrame(
            [
                {
                    "symbol": symbol,
                    "period": "2025-12-31",
                    "segment_name": "汽车玻璃",
                    "revenue": 100.0,
                }
                for symbol in symbols
            ]
        )

    def fetch_institutional(self, symbols, as_of):
        return pd.DataFrame(
            [
                {
                    "symbol": symbol,
                    "holder_name": "机构A",
                    "holding_ratio": 0.05,
                    "period": "2026-03-31",
                }
                for symbol in symbols
            ]
        )

    def fetch_peers(self, symbols, as_of):
        return pd.DataFrame(
            [
                {
                    "symbol": symbol,
                    "peer_symbol": "SSE:600001",
                    "peer_name": "同业公司",
                    "industry": "汽车零部件",
                }
                for symbol in symbols
            ]
        )

    def fetch_guidance(self, symbols, as_of, lookback_months):
        return pd.DataFrame(
            [
                {
                    "symbol": symbol,
                    "guidance_type": "capacity",
                    "summary": "产能释放",
                    "published_at": "2026-05-01T09:00:00+08:00",
                }
                for symbol in symbols
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
    assert result.manifest["data_coverage"]["quote_snapshot"]["as_of"] == ["2026-05-30"]
    assert result.manifest["data_coverage"]["bars"]["symbols"] == 1
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


def test_canslim_screen_prefilter_limit_bounds_fundamental_fetch_scope(tmp_path):
    from trading_os.research.datahub import DataHub
    from trading_os.research.recipes import run_canslim_screen
    from trading_os.research.store import ResearchStore

    class TrackingProvider(ManyCandidatesProvider):
        def __init__(self) -> None:
            super().__init__()
            self.fundamental_calls: list[list[str]] = []

        def fetch_fundamentals(self, symbols, as_of, periods):
            self.fundamental_calls.append(list(symbols))
            return pd.DataFrame(
                [
                    {
                        "symbol": symbol,
                        "period": "2026Q1",
                        "eps_growth_yoy": 0.35,
                        "roe": 0.22,
                        "positive_quarters": 8,
                    }
                    for symbol in symbols
                ]
            )

        def fetch_quote_snapshot(self, as_of: date):
            quotes = super().fetch_quote_snapshot(as_of)
            quotes["amount"] = [
                10_000_000.0,
                50_000_000.0,
                20_000_000.0,
                70_000_000.0,
                30_000_000.0,
            ]
            return quotes

    provider = TrackingProvider()
    hub = DataHub(ResearchStore(tmp_path / "research"), provider=provider)

    result = run_canslim_screen(
        hub,
        as_of=date(2026, 5, 30),
        top_n=10,
        min_turnover=1,
        prefilter_limit=2,
    )

    assert provider.fundamental_calls == [["SSE:600003", "SSE:600001"]]
    assert result.manifest["prefilter"] == {
        "mode": "liquidity",
        "input_total": 5,
        "output_total": 2,
        "limit": 2,
    }
    assert result.manifest["candidates_total"] == 2


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


def test_company_research_canslim_report_contains_real_screening_sections(tmp_path):
    from trading_os.research.datahub import DataHub
    from trading_os.research.recipes import run_company_research
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_quote_snapshot(
        pd.DataFrame(
            [
                {
                    "symbol": "SSE:600000",
                    "name": "A",
                    "close": 20.0,
                    "volume": 2_000_000.0,
                    "amount": 40_000_000.0,
                }
            ]
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
                    "eps_growth_yoy": 0.35,
                    "roe": 0.22,
                    "positive_quarters": 8,
                    "net_margin": 0.18,
                    "gross_margin": 0.42,
                }
            ]
        ),
        as_of=date(2026, 5, 30),
        source="fixture",
    )
    bars = RecipeProvider().fetch_bars(["SSE:600000"], date(2025, 5, 1), date(2026, 5, 31), "qfq")
    store.write_bars(bars, source="fixture")
    hub = DataHub(store, provider=RecipeProvider())

    result = run_company_research(
        hub, "SSE:600000", as_of=date(2026, 5, 30), template="canslim"
    )

    report = result.report
    assert "## CANSLIM Evidence" in report
    assert "eps_growth_yoy" in report
    assert "positive_quarters" in report
    assert "relative_strength" in report
    assert "## Data Limitations" in report
    assert "## Next Actions" in report
    assert result.manifest["template"] == "canslim"
    assert "bars" in result.manifest["datasets"]


def test_company_research_canslim_report_includes_enrichment_sections(tmp_path):
    from trading_os.research.datahub import DataHub
    from trading_os.research.recipes import run_company_research
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_quote_snapshot(
        pd.DataFrame([{"symbol": "SSE:600000", "close": 20.0, "amount": 40_000_000.0}]),
        as_of=date(2026, 6, 12),
        source="fixture",
    )
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
        as_of=date(2026, 6, 12),
        source="fixture",
    )
    store.write_news(
        pd.DataFrame(
            [
                {
                    "symbol": "SSE:600000",
                    "title": "公司公告订单增长",
                    "published_at": "2026-06-01T09:00:00+08:00",
                    "source_url": "https://example.test/news/1",
                    "lookback_months": 12,
                }
            ]
        ),
        as_of=date(2026, 6, 12),
        source="fixture",
    )
    store.write_estimates(
        pd.DataFrame([{"symbol": "SSE:600000", "eps_estimate": 1.23, "target_price": 15.0}]),
        as_of=date(2026, 6, 12),
        source="fixture",
    )
    hub = DataHub(store, provider=RecipeProvider())

    result = run_company_research(
        hub,
        "SSE:600000",
        as_of=date(2026, 6, 12),
        template="canslim",
    )

    assert "## News and Announcements" in result.report
    assert "公司公告订单增长" in result.report
    assert "## Estimates and Valuation Context" in result.report
    assert "target_price" in result.report
    assert "## Institutional Sponsorship and Peer Context" in result.report


def test_company_research_manifest_and_report_include_structured_enrichment(tmp_path):
    from trading_os.research.datahub import DataHub
    from trading_os.research.recipes import run_company_research
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_quote_snapshot(
        pd.DataFrame([{"symbol": "SSE:600000", "close": 20.0, "amount": 40_000_000.0}]),
        as_of=date(2026, 6, 12),
        source="fixture",
    )
    hub = DataHub(store, provider=CompanyEnrichmentProvider())

    result = run_company_research(
        hub,
        "SSE:600000",
        as_of=date(2026, 6, 12),
        template="canslim",
    )

    for dataset in ["segments", "institutional", "peers", "guidance"]:
        assert result.manifest["datasets"][dataset] is True
        assert (result.run.path / "tables" / f"{dataset}.csv").exists()
    assert "## Business Segments" in result.report
    assert "汽车玻璃" in result.report
    assert "机构A" in result.report
    assert "同业公司" in result.report
    assert "## Management Guidance and Catalysts" in result.report
    assert "产能释放" in result.report


def test_company_research_canslim_report_sorts_news_latest_first_and_filters_symbol():
    from trading_os.research.recipes import _company_report

    report = _company_report(
        "SSE:600000",
        date(2026, 6, 12),
        "canslim",
        "pe_band",
        {
            "quotes": pd.DataFrame(
                [{"symbol": "SSE:600000", "close": 20.0, "amount": 40_000_000.0}]
            ),
            "fundamentals": pd.DataFrame(
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
            "bars": pd.DataFrame(),
            "estimates": pd.DataFrame(),
            "news": pd.DataFrame(
                [
                    {
                        "symbol": "SSE:600000",
                        "title": "较早公告",
                        "published_at": "2026-05-01T09:00:00+08:00",
                        "source_url": "https://example.test/news/old",
                    },
                    {
                        "symbol": "SZSE:000001",
                        "title": "其他公司公告",
                        "published_at": "2026-06-10T09:00:00+08:00",
                        "source_url": "https://example.test/news/other",
                    },
                    {
                        "symbol": "SSE:600000",
                        "title": "最新公告",
                        "published_at": "2026-06-01T09:00:00+08:00",
                        "source_url": "https://example.test/news/new",
                    },
                ]
            ),
        },
    )

    assert report.index("最新公告") < report.index("较早公告")
    assert "其他公司公告" not in report


def test_company_research_canslim_report_selects_freshest_estimate():
    from trading_os.research.recipes import _company_report

    report = _company_report(
        "SSE:600000",
        date(2026, 6, 12),
        "canslim",
        "pe_band",
        {
            "quotes": pd.DataFrame(
                [{"symbol": "SSE:600000", "close": 20.0, "amount": 40_000_000.0}]
            ),
            "fundamentals": pd.DataFrame(
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
            "bars": pd.DataFrame(),
            "news": pd.DataFrame(),
            "estimates": pd.DataFrame(
                [
                    {
                        "symbol": "SSE:600000",
                        "target_price": 10.0,
                        "estimate_date": "2026-05-01",
                        "analyst": "stale",
                    },
                    {
                        "symbol": "SSE:600000",
                        "target_price": 15.0,
                        "estimate_date": "2026-06-01",
                        "analyst": "fresh",
                    },
                ]
            ),
        },
    )

    assert "target_price: `15`" in report
    assert "analyst: `fresh`" in report
    assert "target_price: `10`" not in report
    assert "analyst: `stale`" not in report


def test_company_research_canslim_report_uses_freshest_cached_estimate_real_path(tmp_path):
    from trading_os.research.datahub import DataHub
    from trading_os.research.recipes import run_company_research
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_quote_snapshot(
        pd.DataFrame([{"symbol": "SSE:600000", "close": 20.0, "amount": 40_000_000.0}]),
        as_of=date(2026, 6, 12),
        source="fixture",
    )
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
        as_of=date(2026, 6, 12),
        source="fixture",
    )
    store.write_estimates(
        pd.DataFrame(
            [
                {
                    "symbol": "SSE:600000",
                    "target_price": 15.0,
                    "estimate_date": "2026-06-01",
                    "analyst": "fresh",
                },
                {
                    "symbol": "SSE:600000",
                    "target_price": 10.0,
                    "estimate_date": "2026-05-01",
                    "analyst": "stale",
                },
            ]
        ),
        as_of=date(2026, 6, 12),
        source="fixture",
    )
    hub = DataHub(store, provider=RecipeProvider())

    result = run_company_research(
        hub,
        "SSE:600000",
        as_of=date(2026, 6, 12),
        template="canslim",
    )

    assert "target_price: `15`" in result.report
    assert "analyst: `fresh`" in result.report
    assert "target_price: `10`" not in result.report
    assert "analyst: `stale`" not in result.report
