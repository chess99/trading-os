from __future__ import annotations

from datetime import date

import pytest

pd = pytest.importorskip("pandas")


class FakeTushareClient:
    def stock_basic(self, **kwargs):
        return pd.DataFrame(
            [
                {
                    "ts_code": "600000.SH",
                    "symbol": "600000",
                    "name": "浦发银行",
                    "area": "上海",
                    "industry": "银行",
                    "market": "主板",
                    "list_date": "19991110",
                    "list_status": "L",
                },
                {
                    "ts_code": "000001.SZ",
                    "symbol": "000001",
                    "name": "平安银行",
                    "area": "深圳",
                    "industry": "银行",
                    "market": "主板",
                    "list_date": "19910403",
                    "list_status": "L",
                },
            ]
        )

    def daily(self, **kwargs):
        if kwargs.get("trade_date"):
            return pd.DataFrame(
                [
                    {
                        "ts_code": "600000.SH",
                        "trade_date": "20260612",
                        "open": 10.0,
                        "high": 10.5,
                        "low": 9.8,
                        "close": 10.2,
                        "pre_close": 10.0,
                        "pct_chg": 2.0,
                        "vol": 1000.0,
                        "amount": 5000.0,
                    }
                ]
            )
        return pd.DataFrame(
            [
                {
                    "ts_code": kwargs["ts_code"],
                    "trade_date": "20260611",
                    "open": 10.0,
                    "high": 11.0,
                    "low": 9.5,
                    "close": 10.5,
                    "pre_close": 10.0,
                    "pct_chg": 5.0,
                    "vol": 1000.0,
                    "amount": 5000.0,
                },
                {
                    "ts_code": kwargs["ts_code"],
                    "trade_date": "20260612",
                    "open": 20.0,
                    "high": 22.0,
                    "low": 19.0,
                    "close": 21.0,
                    "pre_close": 20.0,
                    "pct_chg": 5.0,
                    "vol": 2000.0,
                    "amount": 8000.0,
                },
            ]
        )

    def daily_basic(self, **kwargs):
        return pd.DataFrame(
            [
                {
                    "ts_code": "600000.SH",
                    "total_mv": 1000.0,
                    "circ_mv": 900.0,
                    "pe_ttm": 8.5,
                    "pb": 0.7,
                    "turnover_rate": 1.2,
                    "volume_ratio": 1.5,
                }
            ]
        )

    def adj_factor(self, **kwargs):
        return pd.DataFrame(
            [
                {"ts_code": kwargs["ts_code"], "trade_date": "20260611", "adj_factor": 1.0},
                {"ts_code": kwargs["ts_code"], "trade_date": "20260612", "adj_factor": 2.0},
            ]
        )

    def fina_indicator(self, **kwargs):
        return pd.DataFrame(
            [
                {
                    "ts_code": kwargs["ts_code"],
                    "end_date": "20260331",
                    "ann_date": "20260420",
                    "q_netprofit_yoy": 35.0,
                    "tr_yoy": 28.0,
                    "roe": 22.0,
                    "grossprofit_margin": 40.0,
                    "netprofit_margin": 18.0,
                    "debt_to_assets": 45.0,
                    "q_netprofit": 10_000.0,
                },
                {
                    "ts_code": kwargs["ts_code"],
                    "end_date": "20251231",
                    "ann_date": "20260320",
                    "q_netprofit_yoy": 20.0,
                    "tr_yoy": 18.0,
                    "roe": 18.0,
                    "q_netprofit": 8_000.0,
                },
            ]
        )

    def fina_mainbz(self, **kwargs):
        return pd.DataFrame(
            [
                {
                    "ts_code": kwargs["ts_code"],
                    "end_date": "20251231",
                    "bz_item": "汽车玻璃",
                    "bz_sales": 1000.0,
                    "bz_profit": 300.0,
                    "bz_cost": 700.0,
                    "curr_type": "CNY",
                }
            ]
        )

    def top10_holders(self, **kwargs):
        return pd.DataFrame(
            [
                {
                    "ts_code": kwargs["ts_code"],
                    "ann_date": "20260420",
                    "end_date": "20260331",
                    "holder_name": "机构A",
                    "hold_amount": 100.0,
                    "hold_ratio": 5.0,
                }
            ]
        )

    def index_member_all(self, **kwargs):
        return pd.DataFrame(
            [
                {
                    "ts_code": kwargs["ts_code"],
                    "index_code": "881123.TI",
                    "index_name": "汽车零部件",
                }
            ]
        )

    def bak_basic(self, **kwargs):
        return pd.DataFrame(
            [
                {
                    "ts_code": "600001.SH",
                    "name": "同业公司",
                    "industry": "汽车零部件",
                    "total_mv": 500.0,
                    "pe": 20.0,
                }
            ]
        )

    def news(self, **kwargs):
        return pd.DataFrame(
            [
                {
                    "datetime": "2026-05-01 09:00:00",
                    "title": "公司新增订单增长",
                    "content": "公司披露订单增长和产能释放。",
                    "url": "https://example.test/news",
                    "src": "测试新闻",
                }
            ]
        )

    def anns_d(self, **kwargs):
        return pd.DataFrame(
            [
                {
                    "ts_code": kwargs["ts_code"],
                    "ann_date": "20260420",
                    "title": "关于新产品周期的公告",
                    "url": "https://example.test/ann",
                }
            ]
        )


def test_tushare_provider_normalizes_universe():
    from trading_os.research.tushare_provider import TushareResearchProvider

    provider = TushareResearchProvider(pro_client=FakeTushareClient())

    universe = provider.fetch_universe(date(2026, 6, 12))

    assert universe["symbol"].tolist() == ["SSE:600000", "SZSE:000001"]
    assert universe["is_active"].tolist() == [True, True]
    assert universe["is_st"].tolist() == [False, False]


def test_tushare_provider_normalizes_quote_snapshot():
    from trading_os.research.tushare_provider import TushareResearchProvider

    provider = TushareResearchProvider(pro_client=FakeTushareClient())

    quotes = provider.fetch_quote_snapshot(date(2026, 6, 12))

    assert quotes.iloc[0]["symbol"] == "SSE:600000"
    assert quotes.iloc[0]["close"] == 10.2
    assert quotes.iloc[0]["volume"] == 100_000.0
    assert quotes.iloc[0]["amount"] == 5_000_000.0
    assert quotes.iloc[0]["market_cap"] == 10_000_000.0
    assert quotes.iloc[0]["pe_ttm"] == 8.5


def test_tushare_provider_fetches_forward_adjusted_daily_bars():
    from trading_os.research.tushare_provider import TushareResearchProvider

    provider = TushareResearchProvider(pro_client=FakeTushareClient())

    bars = provider.fetch_bars(
        ["SSE:600000"],
        start=date(2026, 6, 11),
        end=date(2026, 6, 12),
        adjustment="qfq",
    )

    assert bars["symbol"].tolist() == ["SSE:600000", "SSE:600000"]
    assert bars["close"].round(2).tolist() == [5.25, 21.0]
    assert bars["volume"].tolist() == [100_000.0, 200_000.0]


def test_tushare_provider_normalizes_fundamentals():
    from trading_os.research.tushare_provider import TushareResearchProvider

    provider = TushareResearchProvider(pro_client=FakeTushareClient())

    fundamentals = provider.fetch_fundamentals(
        ["SSE:600000"],
        as_of=date(2026, 6, 12),
        periods=8,
    )

    row = fundamentals.iloc[0]
    assert row["symbol"] == "SSE:600000"
    assert row["period"] == "2026-03-31"
    assert row["pub_date"] == "2026-04-20"
    assert row["eps_growth_yoy"] == 0.35
    assert row["revenue_growth_yoy"] == 0.28
    assert row["roe"] == 0.22
    assert row["positive_quarters"] == 2


def test_tushare_provider_normalizes_segments_institutional_and_peers():
    from trading_os.research.tushare_provider import TushareResearchProvider

    provider = TushareResearchProvider(pro_client=FakeTushareClient())

    segments = provider.fetch_segments(["SSE:600000"], as_of=date(2026, 6, 12))
    institutional = provider.fetch_institutional(["SSE:600000"], as_of=date(2026, 6, 12))
    peers = provider.fetch_peers(["SSE:600000"], as_of=date(2026, 6, 12))

    assert segments.iloc[0]["segment_name"] == "汽车玻璃"
    assert segments.iloc[0]["revenue"] == 1000.0
    assert institutional.iloc[0]["holder_name"] == "机构A"
    assert institutional.iloc[0]["holding_ratio"] == 0.05
    assert peers.iloc[0]["peer_symbol"] == "SSE:600001"
    assert peers.iloc[0]["peer_name"] == "同业公司"


def test_tushare_provider_normalizes_news_and_guidance():
    from trading_os.research.tushare_provider import TushareResearchProvider

    provider = TushareResearchProvider(pro_client=FakeTushareClient())

    news = provider.fetch_news(["SSE:600000"], as_of=date(2026, 6, 12), lookback_months=12)
    guidance = provider.fetch_guidance(
        ["SSE:600000"],
        as_of=date(2026, 6, 12),
        lookback_months=12,
    )

    assert news["symbol"].tolist() == ["SSE:600000", "SSE:600000"]
    assert set(news["event_type"].tolist()) == {"news", "announcement"}
    assert "新增订单增长" in news.iloc[0]["title"]
    assert guidance.iloc[0]["guidance_type"] in {"orders", "capacity", "product_cycle"}
    assert "订单" in guidance.iloc[0]["summary"]
