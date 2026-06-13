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


class EmptyProvider:
    name = "empty"
    capabilities = {"quote_snapshot_eod"}

    def fetch_quote_snapshot(self, as_of: date):
        return pd.DataFrame()


class NoneProvider:
    name = "none"
    capabilities = {"quote_snapshot_eod"}

    def fetch_quote_snapshot(self, as_of: date):
        return None


def test_provider_router_falls_back_and_records_failure():
    from trading_os.research.providers import ProviderRouter

    router = ProviderRouter([FailingProvider(), WorkingProvider()])

    result = router.fetch("quote_snapshot_eod", "fetch_quote_snapshot", date(2026, 6, 12))

    assert result.provider_name == "working"
    assert len(result.failures) == 1
    assert result.failures[0]["provider"] == "failing"
    assert result.failures[0]["error_type"] == "RuntimeError"
    assert not result.data.empty


def test_provider_router_falls_back_when_provider_returns_none():
    from trading_os.research.providers import ProviderRouter

    router = ProviderRouter([NoneProvider(), WorkingProvider()])

    result = router.fetch("quote_snapshot_eod", "fetch_quote_snapshot", date(2026, 6, 12))

    assert result.provider_name == "working"
    assert len(result.failures) == 1
    assert result.failures[0]["provider"] == "none"
    assert result.failures[0]["error_type"] == "EmptyDataError"
    assert result.failures[0]["message"] == "provider returned no data"
    assert not result.data.empty


def test_provider_router_falls_back_when_provider_returns_empty_frame():
    from trading_os.research.providers import ProviderRouter

    router = ProviderRouter([EmptyProvider(), WorkingProvider()])

    result = router.fetch("quote_snapshot_eod", "fetch_quote_snapshot", date(2026, 6, 12))

    assert result.provider_name == "working"
    assert len(result.failures) == 1
    assert result.failures[0]["provider"] == "empty"
    assert result.failures[0]["error_type"] == "EmptyDataError"
    assert result.failures[0]["message"] == "provider returned empty data"
    assert not result.data.empty


def test_provider_router_raises_fetch_error_with_failures_when_all_providers_fail():
    from trading_os.research.providers import ProviderFetchError, ProviderRouter

    router = ProviderRouter([FailingProvider(), EmptyProvider(), NoneProvider()])

    with pytest.raises(ProviderFetchError) as exc_info:
        router.fetch("quote_snapshot_eod", "fetch_quote_snapshot", date(2026, 6, 12))

    assert exc_info.value.capability == "quote_snapshot_eod"
    assert [failure["provider"] for failure in exc_info.value.failures] == [
        "failing",
        "empty",
        "none",
    ]
    assert [failure["error_type"] for failure in exc_info.value.failures] == [
        "RuntimeError",
        "EmptyDataError",
        "EmptyDataError",
    ]


def test_provider_router_fails_when_no_provider_has_capability():
    from trading_os.research.providers import MissingCapabilityError, ProviderRouter

    router = ProviderRouter([])

    with pytest.raises(MissingCapabilityError):
        router.fetch("quote_snapshot_eod", "fetch_quote_snapshot", date(2026, 6, 12))


def test_provider_health_rows_include_recorded_at(tmp_path):
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")

    store.write_provider_health(
        [
            {
                "provider": "failing",
                "capability": "quote_snapshot_eod",
                "method": "fetch_quote_snapshot",
                "error_type": "RuntimeError",
                "error": "primary down",
            }
        ]
    )

    health = store.get_provider_health()

    assert "recorded_at" in health.columns
    assert health.iloc[0]["recorded_at"]
