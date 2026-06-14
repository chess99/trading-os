from __future__ import annotations

from datetime import date

import pytest

pd = pytest.importorskip("pandas")


class FakeProvider:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def fetch_universe(self, as_of: date):
        self.calls.append(f"universe:{as_of.isoformat()}")
        return pd.DataFrame(
            [
                {
                    "symbol": "SSE:600000",
                    "name": "浦发银行",
                    "exchange": "SSE",
                    "is_st": False,
                    "is_active": True,
                }
            ]
        )

    def fetch_quote_snapshot(self, as_of: date):
        self.calls.append(f"quotes:{as_of.isoformat()}")
        return pd.DataFrame(
            [{"symbol": "SSE:600000", "close": 10.0, "volume": 2_000_000.0, "amount": 20_000_000.0}]
        )

    def fetch_bars(self, symbols, start, end, adjustment):
        self.calls.append(f"bars:{','.join(symbols)}:{start.isoformat()}:{end.isoformat()}")
        return pd.DataFrame(
            [
                {
                    "symbol": symbol,
                    "ts": ts,
                    "open": 10.0,
                    "high": 10.0,
                    "low": 10.0,
                    "close": 10.0,
                    "volume": 1_000_000.0,
                }
                for symbol in symbols
                for ts in pd.bdate_range(start=start, end=end, inclusive="left")
            ]
        )


class EmptyQuoteProvider(FakeProvider):
    def fetch_quote_snapshot(self, as_of: date):
        self.calls.append(f"quotes:{as_of.isoformat()}")
        return pd.DataFrame()


class EmptyBarsProvider(FakeProvider):
    def fetch_bars(self, symbols, start, end, adjustment):
        self.calls.append(f"bars:{','.join(symbols)}:{start.isoformat()}:{end.isoformat()}")
        return pd.DataFrame()


class IncompleteBarsProvider(FakeProvider):
    def fetch_bars(self, symbols, start, end, adjustment):
        self.calls.append(f"bars:{','.join(symbols)}:{start.isoformat()}:{end.isoformat()}")
        return pd.DataFrame(
            [
                {
                    "symbol": symbol,
                    "ts": "2026-05-04",
                    "open": 10.0,
                    "high": 10.0,
                    "low": 10.0,
                    "close": 10.0,
                    "volume": 1_000_000.0,
                }
                for symbol in symbols
            ]
        )


class FundamentalsProvider:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def fetch_fundamentals(self, symbols, as_of, periods):
        self.calls.append(list(symbols))
        return pd.DataFrame(
            [
                {
                    "symbol": symbol,
                    "roe": 0.20,
                    "revenue_growth_yoy": 0.30,
                }
                for symbol in symbols
            ]
        )


class PartialFundamentalsProvider:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def fetch_fundamentals(self, symbols, as_of, periods):
        self.calls.append(list(symbols))
        return pd.DataFrame(
            [
                {
                    "symbol": "SSE:600000",
                    "roe": 0.25,
                    "revenue_growth_yoy": 0.35,
                }
            ]
        )


class EmptyRouterProvider:
    name = "empty"
    capabilities = {"universe", "bars_daily", "fundamentals"}

    def fetch_universe(self, as_of: date):
        return pd.DataFrame()

    def fetch_bars(self, symbols, start, end, adjustment):
        return pd.DataFrame()

    def fetch_fundamentals(self, symbols, as_of, periods):
        return pd.DataFrame()


class WorkingRouterProvider:
    name = "working"
    capabilities = {"universe", "bars_daily", "fundamentals"}

    def fetch_universe(self, as_of: date):
        return pd.DataFrame(
            [
                {
                    "symbol": "SSE:600000",
                    "name": "浦发银行",
                    "exchange": "SSE",
                    "is_st": False,
                    "is_active": True,
                }
            ]
        )

    def fetch_bars(self, symbols, start, end, adjustment):
        return pd.DataFrame(
            [
                {
                    "symbol": symbol,
                    "ts": ts,
                    "open": 10.0,
                    "high": 10.0,
                    "low": 10.0,
                    "close": 10.0,
                    "volume": 1_000_000.0,
                }
                for symbol in symbols
                for ts in pd.bdate_range(start=start, end=end, inclusive="left")
            ]
        )

    def fetch_fundamentals(self, symbols, as_of, periods):
        return pd.DataFrame(
            [
                {
                    "symbol": symbol,
                    "revenue_growth_yoy": 0.25,
                    "net_profit_growth_yoy": 0.30,
                    "roe": 0.18,
                }
                for symbol in symbols
            ]
        )


class EnrichmentProvider(FakeProvider):
    def fetch_estimates(self, symbols, as_of):
        self.calls.append(f"estimates:{','.join(symbols)}:{as_of.isoformat()}")
        return pd.DataFrame(
            [
                {"symbol": symbol, "eps_estimate": 1.23, "target_price": 15.0}
                for symbol in symbols
            ]
        )

    def fetch_news(self, symbols, as_of, lookback_months):
        self.calls.append(f"news:{','.join(symbols)}:{as_of.isoformat()}:{lookback_months}")
        return pd.DataFrame(
            [
                {
                    "symbol": symbol,
                    "title": "订单增长",
                    "published_at": "2026-06-01T09:00:00+08:00",
                    "source_url": "https://example.test/news/1",
                }
                for symbol in symbols
            ]
        )

    def fetch_segments(self, symbols, as_of):
        self.calls.append(f"segments:{','.join(symbols)}:{as_of.isoformat()}")
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
        self.calls.append(f"institutional:{','.join(symbols)}:{as_of.isoformat()}")
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
        self.calls.append(f"peers:{','.join(symbols)}:{as_of.isoformat()}")
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
        self.calls.append(f"guidance:{','.join(symbols)}:{as_of.isoformat()}:{lookback_months}")
        return pd.DataFrame(
            [
                {
                    "symbol": symbol,
                    "published_at": "2026-05-01T09:00:00+08:00",
                    "guidance_type": "capacity",
                    "summary": "产能释放",
                }
                for symbol in symbols
            ]
        )


class EmptyEnrichmentProvider(EnrichmentProvider):
    def fetch_estimates(self, symbols, as_of):
        self.calls.append(f"estimates:{','.join(symbols)}:{as_of.isoformat()}")
        return pd.DataFrame()

    def fetch_news(self, symbols, as_of, lookback_months):
        self.calls.append(f"news:{','.join(symbols)}:{as_of.isoformat()}:{lookback_months}")
        return pd.DataFrame()

    def fetch_segments(self, symbols, as_of):
        self.calls.append(f"segments:{','.join(symbols)}:{as_of.isoformat()}")
        return pd.DataFrame()


class PartialEnrichmentProvider(EnrichmentProvider):
    def fetch_estimates(self, symbols, as_of):
        self.calls.append(f"estimates:{','.join(symbols)}:{as_of.isoformat()}")
        return pd.DataFrame(
            [{"symbol": symbols[0], "eps_estimate": 1.23, "target_price": 15.0}]
        )

    def fetch_news(self, symbols, as_of, lookback_months):
        self.calls.append(f"news:{','.join(symbols)}:{as_of.isoformat()}:{lookback_months}")
        return pd.DataFrame(
            [
                {
                    "symbol": symbols[0],
                    "title": "订单增长",
                    "published_at": "2026-06-01T09:00:00+08:00",
                    "source_url": "https://example.test/news/1",
                }
            ]
        )


class EmptyEnrichmentRouterProvider:
    name = "empty_enrichment"
    capabilities = {"estimates", "news"}

    def fetch_estimates(self, symbols, as_of):
        return pd.DataFrame()

    def fetch_news(self, symbols, as_of, lookback_months):
        return pd.DataFrame()


class WorkingEnrichmentRouterProvider:
    name = "working_enrichment"
    capabilities = {"estimates", "news"}

    def fetch_estimates(self, symbols, as_of):
        return pd.DataFrame(
            [{"symbol": symbols[0], "eps_estimate": 1.45, "target_price": 18.0}]
        )

    def fetch_news(self, symbols, as_of, lookback_months):
        return pd.DataFrame(
            [
                {
                    "symbol": symbols[0],
                    "title": f"{lookback_months}个月订单跟踪",
                    "published_at": "2026-06-02T09:00:00+08:00",
                    "source_url": "https://example.test/news/router",
                }
            ]
        )


class FailingQuoteRouterProvider:
    name = "quote_failing"
    capabilities = {"quote_snapshot_eod"}

    def fetch_quote_snapshot(self, as_of: date):
        raise RuntimeError("quote down")


def test_datahub_cache_first_does_not_refetch_fresh_universe(tmp_path):
    from trading_os.research.datahub import DataHub
    from trading_os.research.store import ResearchStore

    provider = FakeProvider()
    hub = DataHub(ResearchStore(tmp_path / "research"), provider=provider)

    first = hub.get_universe(date(2026, 5, 30), policy="cache_first")
    second = hub.get_universe(date(2026, 5, 30), policy="cache_first")

    assert first.equals(second)
    assert provider.calls == ["universe:2026-05-30"]


def test_datahub_cache_first_refetches_stale_daily_snapshot(tmp_path):
    from trading_os.research.datahub import DataHub
    from trading_os.research.store import ResearchStore

    provider = FakeProvider()
    hub = DataHub(ResearchStore(tmp_path / "research"), provider=provider)

    hub.get_quote_snapshot(date(2026, 5, 30), policy="cache_first")
    second = hub.get_quote_snapshot(date(2026, 5, 31), policy="cache_first")

    assert provider.calls == ["quotes:2026-05-30", "quotes:2026-05-31"]
    assert second["as_of"].unique().tolist() == ["2026-05-31"]


def test_datahub_direct_quote_refresh_rejects_empty_provider_without_returning_stale_cache(
    tmp_path,
):
    from trading_os.research.datahub import DataHub, MissingDataError
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_quote_snapshot(
        pd.DataFrame([{"symbol": "SSE:600000", "close": 9.0, "amount": 1_000_000.0}]),
        as_of=date(2026, 5, 30),
        source="fixture",
    )
    provider = EmptyQuoteProvider()
    hub = DataHub(store, provider=provider)

    with pytest.raises(MissingDataError):
        hub.get_quote_snapshot(date(2026, 5, 31), policy="refresh")

    assert provider.calls == ["quotes:2026-05-31"]
    stale = store.get_quote_snapshot(as_of=date(2026, 5, 31))
    assert stale["as_of"].unique().tolist() == ["2026-05-30"]
    assert stale["source"].unique().tolist() == ["fixture"]


def test_datahub_lazy_fill_refetches_bars_when_date_coverage_is_stale(tmp_path):
    from trading_os.research.datahub import DataHub
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_bars(
        pd.DataFrame(
            [
                {
                    "symbol": "SSE:600000",
                    "ts": "2026-05-20",
                    "open": 9.0,
                    "high": 9.0,
                    "low": 9.0,
                    "close": 9.0,
                    "volume": 1_000_000.0,
                }
            ]
        ),
        source="fixture",
    )
    provider = FakeProvider()
    hub = DataHub(store, provider=provider)

    bars = hub.get_bars(
        ["SSE:600000"],
        start=date(2026, 5, 1),
        end=date(2026, 5, 31),
        policy="lazy_fill",
    )

    assert provider.calls == ["bars:SSE:600000:2026-05-01:2026-05-31"]
    assert pd.to_datetime(bars["ts"], utc=True).max().date().isoformat() == "2026-05-29"


def test_datahub_direct_bars_lazy_fill_rejects_empty_provider_instead_of_partial_cache(
    tmp_path,
):
    from trading_os.research.datahub import DataHub, MissingDataError
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_bars(
        pd.DataFrame(
            [
                {
                    "symbol": "SSE:600000",
                    "ts": "2026-05-04",
                    "open": 9.0,
                    "high": 9.0,
                    "low": 9.0,
                    "close": 9.0,
                    "volume": 1_000_000.0,
                }
            ]
        ),
        source="fixture",
    )
    provider = EmptyBarsProvider()
    hub = DataHub(store, provider=provider)

    with pytest.raises(MissingDataError):
        hub.get_bars(
            ["SSE:600000"],
            start=date(2026, 5, 4),
            end=date(2026, 5, 8),
            policy="lazy_fill",
        )

    assert provider.calls == ["bars:SSE:600000:2026-05-04:2026-05-08"]


def test_datahub_direct_bars_lazy_fill_rejects_incomplete_provider_data(tmp_path):
    from trading_os.research.datahub import DataHub, MissingDataError
    from trading_os.research.store import ResearchStore

    provider = IncompleteBarsProvider()
    hub = DataHub(ResearchStore(tmp_path / "research"), provider=provider)

    with pytest.raises(MissingDataError):
        hub.get_bars(
            ["SSE:600000"],
            start=date(2026, 5, 4),
            end=date(2026, 5, 8),
            policy="lazy_fill",
        )

    assert provider.calls == ["bars:SSE:600000:2026-05-04:2026-05-08"]


def test_datahub_lazy_fill_refetches_bars_when_cache_does_not_cover_start(tmp_path):
    from trading_os.research.datahub import DataHub
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_bars(
        pd.DataFrame(
            [
                {
                    "symbol": "SSE:600000",
                    "ts": "2026-05-29",
                    "open": 9.0,
                    "high": 9.0,
                    "low": 9.0,
                    "close": 9.0,
                    "volume": 1_000_000.0,
                }
            ]
        ),
        source="fixture",
    )
    provider = FakeProvider()
    hub = DataHub(store, provider=provider)

    hub.get_bars(
        ["SSE:600000"],
        start=date(2026, 5, 1),
        end=date(2026, 5, 31),
        policy="lazy_fill",
    )

    assert provider.calls == ["bars:SSE:600000:2026-05-01:2026-05-31"]


def test_datahub_lazy_fill_refetches_bars_when_cache_misses_middle_business_dates(tmp_path):
    from trading_os.research.datahub import DataHub
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_bars(
        pd.DataFrame(
            [
                {
                    "symbol": "SSE:600000",
                    "ts": "2026-05-04",
                    "open": 9.0,
                    "high": 9.0,
                    "low": 9.0,
                    "close": 9.0,
                    "volume": 1_000_000.0,
                },
                {
                    "symbol": "SSE:600000",
                    "ts": "2026-05-07",
                    "open": 9.0,
                    "high": 9.0,
                    "low": 9.0,
                    "close": 9.0,
                    "volume": 1_000_000.0,
                },
            ]
        ),
        source="fixture",
    )
    provider = FakeProvider()
    hub = DataHub(store, provider=provider)

    hub.get_bars(
        ["SSE:600000"],
        start=date(2026, 5, 4),
        end=date(2026, 5, 8),
        policy="lazy_fill",
    )

    assert provider.calls == ["bars:SSE:600000:2026-05-04:2026-05-08"]


def test_datahub_refresh_refetches_bars_when_date_coverage_is_complete(tmp_path):
    from trading_os.research.datahub import DataHub
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_bars(
        pd.DataFrame(
            [
                {
                    "symbol": "SSE:600000",
                    "ts": "2026-05-29",
                    "open": 9.0,
                    "high": 9.0,
                    "low": 9.0,
                    "close": 9.0,
                    "volume": 1_000_000.0,
                }
            ]
        ),
        source="fixture",
    )
    provider = FakeProvider()
    hub = DataHub(store, provider=provider)

    bars = hub.get_bars(
        ["SSE:600000"],
        start=date(2026, 5, 1),
        end=date(2026, 5, 31),
        policy="refresh",
    )

    assert provider.calls == ["bars:SSE:600000:2026-05-01:2026-05-31"]
    assert bars[["symbol", "ts"]].duplicated().sum() == 0
    assert bars["source"].unique().tolist() == ["FakeProvider"]
    assert bars["close"].unique().tolist() == [10.0]


def test_datahub_with_provider_router_fetches_universe_through_fallback(tmp_path):
    from trading_os.research.datahub import DataHub
    from trading_os.research.providers import ProviderRouter
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    hub = DataHub(store, provider=ProviderRouter([EmptyRouterProvider(), WorkingRouterProvider()]))

    universe = hub.get_universe(date(2026, 5, 30), policy="refresh")
    health = store.get_provider_health()

    assert universe["symbol"].tolist() == ["SSE:600000"]
    assert universe["source"].unique().tolist() == ["working"]
    assert health["provider"].tolist() == ["empty"]


def test_datahub_with_provider_router_lazy_fills_bars_through_fallback(tmp_path):
    from trading_os.research.datahub import DataHub
    from trading_os.research.providers import ProviderRouter
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    hub = DataHub(store, provider=ProviderRouter([EmptyRouterProvider(), WorkingRouterProvider()]))

    bars = hub.get_bars(
        ["SSE:600000"],
        start=date(2026, 5, 1),
        end=date(2026, 5, 31),
        policy="lazy_fill",
    )
    health = store.get_provider_health()

    assert bars["symbol"].unique().tolist() == ["SSE:600000"]
    assert bars["source"].unique().tolist() == ["working"]
    assert health["capability"].tolist() == ["bars_daily"]


def test_datahub_with_provider_router_refreshes_fundamentals_through_fallback(tmp_path):
    from trading_os.research.datahub import DataHub
    from trading_os.research.providers import ProviderRouter
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_fundamentals(
        pd.DataFrame([{"symbol": "SSE:600000", "roe": 0.10}]),
        as_of=date(2026, 5, 29),
        source="fixture",
    )
    hub = DataHub(store, provider=ProviderRouter([EmptyRouterProvider(), WorkingRouterProvider()]))

    fundamentals = hub.get_fundamentals(
        ["SSE:600000"],
        as_of=date(2026, 5, 30),
        policy="refresh",
    )
    health = store.get_provider_health()

    assert fundamentals["source"].unique().tolist() == ["working"]
    assert fundamentals.iloc[0]["roe"] == 0.18
    assert health["capability"].tolist() == ["fundamentals"]


def test_datahub_fetches_estimates_when_provider_supports_it(tmp_path):
    from trading_os.research.datahub import DataHub
    from trading_os.research.store import ResearchStore

    provider = EnrichmentProvider()
    hub = DataHub(ResearchStore(tmp_path / "research"), provider=provider)

    estimates = hub.get_estimates(["SSE:600000"], as_of=date(2026, 6, 12))

    assert provider.calls == ["estimates:SSE:600000:2026-06-12"]
    assert estimates.iloc[0]["target_price"] == 15.0
    assert estimates.iloc[0]["source"] == "EnrichmentProvider"


def test_datahub_fetches_news_when_provider_supports_it(tmp_path):
    from trading_os.research.datahub import DataHub
    from trading_os.research.store import ResearchStore

    provider = EnrichmentProvider()
    hub = DataHub(ResearchStore(tmp_path / "research"), provider=provider)

    news = hub.get_news(["SSE:600000"], as_of=date(2026, 6, 12), lookback_months=12)

    assert provider.calls == ["news:SSE:600000:2026-06-12:12"]
    assert news.iloc[0]["title"] == "订单增长"
    assert news.iloc[0]["source"] == "EnrichmentProvider"


def test_datahub_cache_first_estimates_does_not_refetch_cached_data(tmp_path):
    from trading_os.research.datahub import DataHub
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_estimates(
        pd.DataFrame([{"symbol": "SSE:600000", "target_price": 12.0}]),
        as_of=date(2026, 6, 12),
        source="fixture",
    )
    provider = EnrichmentProvider()
    hub = DataHub(store, provider=provider)

    estimates = hub.get_estimates(["SSE:600000"], as_of=date(2026, 6, 12))

    assert provider.calls == []
    assert estimates.iloc[0]["target_price"] == 12.0
    assert estimates.iloc[0]["source"] == "fixture"


def test_datahub_cache_first_estimates_fetches_missing_symbols_only(tmp_path):
    from trading_os.research.datahub import DataHub
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_estimates(
        pd.DataFrame([{"symbol": "SSE:600000", "target_price": 12.0}]),
        as_of=date(2026, 6, 11),
        source="fixture",
    )
    provider = EnrichmentProvider()
    hub = DataHub(store, provider=provider)

    estimates = hub.get_estimates(
        ["SSE:600000", "SZSE:000001"],
        as_of=date(2026, 6, 12),
        policy="cache_first",
    )

    assert provider.calls == ["estimates:SZSE:000001:2026-06-12"]
    cached = estimates[estimates["symbol"] == "SSE:600000"].iloc[0]
    fetched = estimates[estimates["symbol"] == "SZSE:000001"].iloc[0]
    assert cached["target_price"] == 12.0
    assert cached["source"] == "fixture"
    assert cached["as_of"] == "2026-06-11"
    assert fetched["target_price"] == 15.0
    assert fetched["source"] == "EnrichmentProvider"
    assert fetched["as_of"] == "2026-06-12"


def test_datahub_cache_first_news_returns_cached_data_when_provider_is_unsupported(tmp_path):
    from trading_os.research.datahub import DataHub
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_news(
        pd.DataFrame([{"symbol": "SSE:600000", "title": "cached", "lookback_months": 12}]),
        as_of=date(2026, 6, 12),
        source="fixture",
    )
    provider = FakeProvider()
    hub = DataHub(store, provider=provider)

    news = hub.get_news(["SSE:600000"], as_of=date(2026, 6, 12))

    assert provider.calls == []
    assert news.iloc[0]["title"] == "cached"


def test_datahub_cache_first_news_fetches_missing_symbols_only(tmp_path):
    from trading_os.research.datahub import DataHub
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_news(
        pd.DataFrame([{"symbol": "SSE:600000", "title": "cached", "lookback_months": 12}]),
        as_of=date(2026, 6, 12),
        source="fixture",
    )
    provider = EnrichmentProvider()
    hub = DataHub(store, provider=provider)

    news = hub.get_news(
        ["SSE:600000", "SZSE:000001"],
        as_of=date(2026, 6, 12),
        lookback_months=12,
        policy="cache_first",
    )

    assert provider.calls == ["news:SZSE:000001:2026-06-12:12"]
    cached = news[news["symbol"] == "SSE:600000"].iloc[0]
    fetched = news[news["symbol"] == "SZSE:000001"].iloc[0]
    assert cached["title"] == "cached"
    assert cached["source"] == "fixture"
    assert cached["as_of"] == "2026-06-12"
    assert fetched["title"] == "订单增长"
    assert fetched["source"] == "EnrichmentProvider"
    assert fetched["lookback_months"] == 12


def test_datahub_cache_first_news_refetches_when_cached_lookback_is_too_short(tmp_path):
    from trading_os.research.datahub import DataHub
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_news(
        pd.DataFrame([{"symbol": "SSE:600000", "title": "three month", "lookback_months": 3}]),
        as_of=date(2026, 6, 12),
        source="fixture",
    )
    provider = EnrichmentProvider()
    hub = DataHub(store, provider=provider)

    news = hub.get_news(
        ["SSE:600000"],
        as_of=date(2026, 6, 12),
        lookback_months=12,
        policy="cache_first",
    )

    assert provider.calls == ["news:SSE:600000:2026-06-12:12"]
    latest = news[news["symbol"] == "SSE:600000"].iloc[0]
    assert latest["title"] == "订单增长"
    assert latest["source"] == "EnrichmentProvider"
    assert latest["lookback_months"] == 12


def test_datahub_refresh_estimates_rejects_empty_provider_without_returning_stale_cache(tmp_path):
    from trading_os.research.datahub import DataHub, MissingDataError
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_estimates(
        pd.DataFrame([{"symbol": "SSE:600000", "target_price": 12.0}]),
        as_of=date(2026, 6, 11),
        source="fixture",
    )
    provider = EmptyEnrichmentProvider()
    hub = DataHub(store, provider=provider)

    with pytest.raises(MissingDataError):
        hub.get_estimates(["SSE:600000"], as_of=date(2026, 6, 12), policy="refresh")

    assert provider.calls == ["estimates:SSE:600000:2026-06-12"]
    stale = store.get_estimates(["SSE:600000"], as_of=date(2026, 6, 12))
    assert stale.iloc[0]["as_of"] == "2026-06-11"
    assert stale.iloc[0]["source"] == "fixture"


def test_datahub_refresh_news_rejects_empty_provider_without_returning_stale_cache(tmp_path):
    from trading_os.research.datahub import DataHub, MissingDataError
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_news(
        pd.DataFrame([{"symbol": "SSE:600000", "title": "cached"}]),
        as_of=date(2026, 6, 11),
        source="fixture",
    )
    provider = EmptyEnrichmentProvider()
    hub = DataHub(store, provider=provider)

    with pytest.raises(MissingDataError):
        hub.get_news(["SSE:600000"], as_of=date(2026, 6, 12), policy="refresh")

    assert provider.calls == ["news:SSE:600000:2026-06-12:12"]
    stale = store.get_news(["SSE:600000"], as_of=date(2026, 6, 12))
    assert stale.iloc[0]["as_of"] == "2026-06-11"
    assert stale.iloc[0]["source"] == "fixture"


def test_datahub_refresh_estimates_rejects_partial_provider_without_returning_stale_cache(
    tmp_path,
):
    from trading_os.research.datahub import DataHub, MissingDataError
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_estimates(
        pd.DataFrame(
            [
                {"symbol": "SSE:600000", "target_price": 12.0},
                {"symbol": "SZSE:000001", "target_price": 13.0},
            ]
        ),
        as_of=date(2026, 6, 12),
        source="fixture",
    )
    provider = PartialEnrichmentProvider()
    hub = DataHub(store, provider=provider)

    with pytest.raises(MissingDataError):
        hub.get_estimates(
            ["SSE:600000", "SZSE:000001"],
            as_of=date(2026, 6, 12),
            policy="refresh",
        )

    assert provider.calls == ["estimates:SSE:600000,SZSE:000001:2026-06-12"]


def test_datahub_refresh_news_rejects_partial_provider_without_returning_stale_cache(
    tmp_path,
):
    from trading_os.research.datahub import DataHub, MissingDataError
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_news(
        pd.DataFrame(
            [
                {"symbol": "SSE:600000", "title": "cached one", "lookback_months": 12},
                {"symbol": "SZSE:000001", "title": "cached two", "lookback_months": 12},
            ]
        ),
        as_of=date(2026, 6, 12),
        source="fixture",
    )
    provider = PartialEnrichmentProvider()
    hub = DataHub(store, provider=provider)

    with pytest.raises(MissingDataError):
        hub.get_news(
            ["SSE:600000", "SZSE:000001"],
            as_of=date(2026, 6, 12),
            lookback_months=12,
            policy="refresh",
        )

    assert provider.calls == ["news:SSE:600000,SZSE:000001:2026-06-12:12"]


def test_datahub_with_provider_router_fetches_news_through_fallback(tmp_path):
    from trading_os.research.datahub import DataHub
    from trading_os.research.providers import ProviderRouter
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    hub = DataHub(
        store,
        provider=ProviderRouter(
            [EmptyEnrichmentRouterProvider(), WorkingEnrichmentRouterProvider()]
        ),
    )

    news = hub.get_news(["SSE:600000"], as_of=date(2026, 6, 12), policy="refresh")
    health = store.get_provider_health()

    assert news.iloc[0]["title"] == "12个月订单跟踪"
    assert news["source"].unique().tolist() == ["working_enrichment"]
    assert health["provider"].tolist() == ["empty_enrichment"]
    assert health["capability"].tolist() == ["news"]


def test_datahub_fetches_structured_company_enrichment_when_provider_supports_it(tmp_path):
    from trading_os.research.datahub import DataHub
    from trading_os.research.store import ResearchStore

    provider = EnrichmentProvider()
    hub = DataHub(ResearchStore(tmp_path / "research"), provider=provider)

    segments = hub.get_segments(["SSE:600000"], as_of=date(2026, 6, 12))
    institutional = hub.get_institutional(["SSE:600000"], as_of=date(2026, 6, 12))
    peers = hub.get_peers(["SSE:600000"], as_of=date(2026, 6, 12))
    guidance = hub.get_guidance(
        ["SSE:600000"],
        as_of=date(2026, 6, 12),
        lookback_months=12,
    )

    assert provider.calls[-4:] == [
        "segments:SSE:600000:2026-06-12",
        "institutional:SSE:600000:2026-06-12",
        "peers:SSE:600000:2026-06-12",
        "guidance:SSE:600000:2026-06-12:12",
    ]
    assert segments.iloc[0]["segment_name"] == "汽车玻璃"
    assert institutional.iloc[0]["holder_name"] == "机构A"
    assert peers.iloc[0]["peer_symbol"] == "SSE:600001"
    assert guidance.iloc[0]["summary"] == "产能释放"
    assert guidance.iloc[0]["lookback_months"] == 12


def test_datahub_cache_first_structured_company_enrichment_fetches_missing_symbols_only(
    tmp_path,
):
    from trading_os.research.datahub import DataHub
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_segments(
        pd.DataFrame([{"symbol": "SSE:600000", "segment_name": "cached"}]),
        as_of=date(2026, 6, 12),
        source="fixture",
    )
    provider = EnrichmentProvider()
    hub = DataHub(store, provider=provider)

    segments = hub.get_segments(
        ["SSE:600000", "SZSE:000001"],
        as_of=date(2026, 6, 12),
        policy="cache_first",
    )

    assert provider.calls == ["segments:SZSE:000001:2026-06-12"]
    cached = segments[segments["symbol"] == "SSE:600000"].iloc[0]
    fetched = segments[segments["symbol"] == "SZSE:000001"].iloc[0]
    assert cached["segment_name"] == "cached"
    assert cached["source"] == "fixture"
    assert fetched["segment_name"] == "汽车玻璃"
    assert fetched["source"] == "EnrichmentProvider"


def test_datahub_refresh_structured_company_enrichment_requires_provider(tmp_path):
    from trading_os.research.datahub import DataHub, MissingDataError
    from trading_os.research.store import ResearchStore

    hub = DataHub(ResearchStore(tmp_path / "research"), provider=FakeProvider())

    with pytest.raises(MissingDataError, match="segments provider is not available"):
        hub.get_segments(["SSE:600000"], as_of=date(2026, 6, 12), policy="refresh")


def test_datahub_cache_first_fetches_missing_fundamental_symbols_only(tmp_path):
    from trading_os.research.datahub import DataHub
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_fundamentals(
        pd.DataFrame([{"symbol": "SSE:600000", "roe": 0.10}]),
        as_of=date(2026, 5, 30),
        source="fixture",
    )
    provider = FundamentalsProvider()
    hub = DataHub(store, provider=provider)

    fundamentals = hub.get_fundamentals(
        ["SSE:600000", "SZSE:000001"],
        as_of=date(2026, 5, 30),
        policy="cache_first",
    )

    assert provider.calls == [["SZSE:000001"]]
    assert sorted(fundamentals["symbol"].tolist()) == ["SSE:600000", "SZSE:000001"]
    assert fundamentals[fundamentals["symbol"] == "SSE:600000"].iloc[0]["roe"] == 0.10
    assert fundamentals[fundamentals["symbol"] == "SZSE:000001"].iloc[0]["roe"] == 0.20


def test_datahub_cache_first_fundamentals_does_not_promote_stale_cached_symbols(tmp_path):
    from trading_os.research.datahub import DataHub
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_fundamentals(
        pd.DataFrame([{"symbol": "SSE:600000", "roe": 0.10}]),
        as_of=date(2026, 5, 29),
        source="fixture",
    )
    provider = FundamentalsProvider()
    hub = DataHub(store, provider=provider)

    fundamentals = hub.get_fundamentals(
        ["SSE:600000", "SZSE:000001"],
        as_of=date(2026, 5, 30),
        policy="cache_first",
    )

    cached = fundamentals[fundamentals["symbol"] == "SSE:600000"].iloc[0]
    fetched = fundamentals[fundamentals["symbol"] == "SZSE:000001"].iloc[0]

    assert provider.calls == [["SZSE:000001"]]
    assert cached["as_of"] == "2026-05-29"
    assert cached["source"] == "fixture"
    assert cached["roe"] == 0.10
    assert fetched["as_of"] == "2026-05-30"
    assert fetched["source"] == "FundamentalsProvider"
    assert fetched["roe"] == 0.20


def test_datahub_refresh_fundamentals_does_not_promote_stale_missing_symbols(tmp_path):
    from trading_os.research.datahub import DataHub
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_fundamentals(
        pd.DataFrame(
            [
                {"symbol": "SSE:600000", "roe": 0.10},
                {"symbol": "SZSE:000001", "roe": 0.11},
            ]
        ),
        as_of=date(2026, 5, 29),
        source="fixture",
    )
    provider = PartialFundamentalsProvider()
    hub = DataHub(store, provider=provider)

    fundamentals = hub.get_fundamentals(
        ["SSE:600000", "SZSE:000001"],
        as_of=date(2026, 5, 30),
        policy="refresh",
    )

    refreshed = fundamentals[fundamentals["symbol"] == "SSE:600000"].iloc[0]
    stale = fundamentals[fundamentals["symbol"] == "SZSE:000001"].iloc[0]

    assert provider.calls == [["SSE:600000", "SZSE:000001"]]
    assert refreshed["as_of"] == "2026-05-30"
    assert refreshed["source"] == "PartialFundamentalsProvider"
    assert refreshed["roe"] == 0.25
    assert stale["as_of"] == "2026-05-29"
    assert stale["source"] == "fixture"
    assert stale["roe"] == 0.11


def test_datahub_offline_raises_when_fundamental_cache_is_partial(tmp_path):
    from trading_os.research.datahub import DataHub, MissingDataError
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_fundamentals(
        pd.DataFrame([{"symbol": "SSE:600000", "roe": 0.10}]),
        as_of=date(2026, 5, 30),
        source="fixture",
    )
    hub = DataHub(store, provider=FundamentalsProvider())

    with pytest.raises(MissingDataError):
        hub.get_fundamentals(
            ["SSE:600000", "SZSE:000001"],
            as_of=date(2026, 5, 30),
            policy="offline",
        )


def test_datahub_persists_provider_health_when_all_router_quote_providers_fail(tmp_path):
    from trading_os.research.datahub import DataHub
    from trading_os.research.providers import ProviderFetchError, ProviderRouter
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    hub = DataHub(store, provider=ProviderRouter([FailingQuoteRouterProvider()]))

    with pytest.raises(ProviderFetchError):
        hub.get_quote_snapshot(date(2026, 5, 30), policy="refresh")

    health = store.get_provider_health()

    assert health["provider"].tolist() == ["quote_failing"]
    assert health["capability"].tolist() == ["quote_snapshot_eod"]
    assert health["error_type"].tolist() == ["RuntimeError"]
    assert health["recorded_at"].notna().all()


def test_datahub_offline_raises_when_cache_missing(tmp_path):
    from trading_os.research.datahub import DataHub, MissingDataError
    from trading_os.research.store import ResearchStore

    hub = DataHub(ResearchStore(tmp_path / "research"), provider=FakeProvider())

    with pytest.raises(MissingDataError):
        hub.get_quote_snapshot(date(2026, 5, 30), policy="offline")
