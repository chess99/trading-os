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


def test_datahub_cache_first_does_not_refetch_fresh_universe(tmp_path):
    from trading_os.research.datahub import DataHub
    from trading_os.research.store import ResearchStore

    provider = FakeProvider()
    hub = DataHub(ResearchStore(tmp_path / "research"), provider=provider)

    first = hub.get_universe(date(2026, 5, 30), policy="cache_first")
    second = hub.get_universe(date(2026, 5, 30), policy="cache_first")

    assert first.equals(second)
    assert provider.calls == ["universe:2026-05-30"]


def test_datahub_offline_raises_when_cache_missing(tmp_path):
    from trading_os.research.datahub import DataHub, MissingDataError
    from trading_os.research.store import ResearchStore

    hub = DataHub(ResearchStore(tmp_path / "research"), provider=FakeProvider())

    with pytest.raises(MissingDataError):
        hub.get_quote_snapshot(date(2026, 5, 30), policy="offline")
