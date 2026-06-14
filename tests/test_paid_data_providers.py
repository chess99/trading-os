from __future__ import annotations

from datetime import date

import pytest

pd = pytest.importorskip("pandas")


class FakeRqdataClient:
    def all_instruments(self, type=None, date=None):  # noqa: A002
        return pd.DataFrame(
            [
                {
                    "order_book_id": "600000.XSHG",
                    "symbol": "浦发银行",
                    "exchange": "XSHG",
                    "listed_date": "1999-11-10",
                    "status": "Active",
                }
            ]
        )

    def get_price(self, order_book_ids, start_date, end_date, frequency, adjust_type):
        assert frequency == "1d"
        assert adjust_type == "pre"
        return pd.DataFrame(
            [
                {
                    "order_book_id": order_book_ids[0],
                    "date": "2026-06-12",
                    "open": 10.0,
                    "high": 10.5,
                    "low": 9.8,
                    "close": 10.2,
                    "volume": 1000.0,
                    "total_turnover": 5000.0,
                }
            ]
        )

    def get_fundamentals(self, order_book_ids, as_of, periods):
        return pd.DataFrame(
            [
                {
                    "order_book_id": order_book_ids[0],
                    "period": "2026-03-31",
                    "pub_date": "2026-04-20",
                    "roe": 0.22,
                    "revenue_growth_yoy": 0.28,
                    "eps_growth_yoy": 0.35,
                }
            ]
        )


class FakeJqdataClient:
    def get_all_securities(self, types, date):  # noqa: A002
        return pd.DataFrame(
            [
                {
                    "code": "600000.XSHG",
                    "display_name": "浦发银行",
                    "name": "PFYH",
                    "start_date": "1999-11-10",
                    "end_date": "2200-01-01",
                }
            ]
        )

    def get_price(self, security, start_date, end_date, frequency, fq):
        assert frequency == "daily"
        assert fq == "pre"
        return pd.DataFrame(
            [
                {
                    "code": security[0],
                    "time": "2026-06-12",
                    "open": 10.0,
                    "high": 10.5,
                    "low": 9.8,
                    "close": 10.2,
                    "volume": 1000.0,
                    "money": 5000.0,
                }
            ]
        )

    def get_fundamentals(self, securities, as_of, periods):
        return pd.DataFrame(
            [
                {
                    "code": securities[0],
                    "period": "2026-03-31",
                    "pub_date": "2026-04-20",
                    "roe": 0.22,
                    "revenue_growth_yoy": 0.28,
                    "eps_growth_yoy": 0.35,
                }
            ]
        )


def test_rqdata_provider_normalizes_universe_bars_and_fundamentals():
    from trading_os.research.rqdata_provider import RqdataResearchProvider

    provider = RqdataResearchProvider(client=FakeRqdataClient())

    universe = provider.fetch_universe(date(2026, 6, 12))
    bars = provider.fetch_bars(
        ["SSE:600000"],
        start=date(2026, 6, 1),
        end=date(2026, 6, 12),
        adjustment="qfq",
    )
    fundamentals = provider.fetch_fundamentals(["SSE:600000"], date(2026, 6, 12), 8)

    assert universe.iloc[0]["symbol"] == "SSE:600000"
    assert universe.iloc[0]["is_active"] is True
    assert bars.iloc[0]["symbol"] == "SSE:600000"
    assert bars.iloc[0]["amount"] == 5000.0
    assert fundamentals.iloc[0]["roe"] == 0.22


def test_jqdata_provider_normalizes_universe_bars_and_fundamentals():
    from trading_os.research.jqdata_provider import JqdataResearchProvider

    provider = JqdataResearchProvider(client=FakeJqdataClient())

    universe = provider.fetch_universe(date(2026, 6, 12))
    bars = provider.fetch_bars(
        ["SSE:600000"],
        start=date(2026, 6, 1),
        end=date(2026, 6, 12),
        adjustment="qfq",
    )
    fundamentals = provider.fetch_fundamentals(["SSE:600000"], date(2026, 6, 12), 8)

    assert universe.iloc[0]["symbol"] == "SSE:600000"
    assert universe.iloc[0]["is_active"] is True
    assert bars.iloc[0]["symbol"] == "SSE:600000"
    assert bars.iloc[0]["amount"] == 5000.0
    assert fundamentals.iloc[0]["roe"] == 0.22
