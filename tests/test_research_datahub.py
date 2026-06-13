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
                    "ts": pd.Timestamp(end) - pd.Timedelta(days=1),
                    "open": 10.0,
                    "high": 10.0,
                    "low": 10.0,
                    "close": 10.0,
                    "volume": 1_000_000.0,
                }
                for symbol in symbols
            ]
        )


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
    assert pd.to_datetime(bars["ts"], utc=True).max().date().isoformat() == "2026-05-30"


def test_datahub_offline_raises_when_cache_missing(tmp_path):
    from trading_os.research.datahub import DataHub, MissingDataError
    from trading_os.research.store import ResearchStore

    hub = DataHub(ResearchStore(tmp_path / "research"), provider=FakeProvider())

    with pytest.raises(MissingDataError):
        hub.get_quote_snapshot(date(2026, 5, 30), policy="offline")
