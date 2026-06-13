from __future__ import annotations

from datetime import date

import pytest

pd = pytest.importorskip("pandas")


class FailingProvider:
    name = "failing"
    capabilities = {"quote_snapshot_eod"}

    def fetch_quote_snapshot(self, as_of: date):
        raise RuntimeError("primary down")


class WorkingProvider:
    name = "working"
    capabilities = {"quote_snapshot_eod"}

    def fetch_quote_snapshot(self, as_of: date):
        return pd.DataFrame([{"symbol": "SSE:600000", "close": 10.0, "amount": 20_000_000.0}])


def test_provider_router_falls_back_and_records_failure():
    from trading_os.research.providers import ProviderRouter

    router = ProviderRouter([FailingProvider(), WorkingProvider()])

    result = router.fetch("quote_snapshot_eod", "fetch_quote_snapshot", date(2026, 6, 12))

    assert result.provider_name == "working"
    assert len(result.failures) == 1
    assert result.failures[0]["provider"] == "failing"
    assert result.failures[0]["error_type"] == "RuntimeError"
    assert not result.data.empty


def test_provider_router_fails_when_no_provider_has_capability():
    from trading_os.research.providers import MissingCapabilityError, ProviderRouter

    router = ProviderRouter([])

    with pytest.raises(MissingCapabilityError):
        router.fetch("quote_snapshot_eod", "fetch_quote_snapshot", date(2026, 6, 12))
