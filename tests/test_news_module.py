# tests/test_news_module.py
"""Tests for src/trading_os/news/ module."""
from datetime import datetime, timezone

def test_newsitem_defaults():
    from trading_os.news.models import NewsItem
    item = NewsItem(
        symbol="SSE:600000",
        title="测试标题",
        content="测试内容",
        source="eastmoney",
        pub_time=datetime(2026, 5, 13, 9, 0, tzinfo=timezone.utc),
        sentiment="positive",
        importance="high",
    )
    assert item.url == ""
    assert item.symbol == "SSE:600000"
    assert item.sentiment == "positive"
    assert item.fetched_at.tzinfo is not None  # auto-populated, timezone-aware


def test_newsitem_market_sentinel():
    from trading_os.news.models import NewsItem, MARKET_SYMBOL
    assert MARKET_SYMBOL == "__MARKET__"
    item = NewsItem(
        symbol=MARKET_SYMBOL,
        title="市场新闻",
        content="内容",
        source="cls_telegraph",
        pub_time=datetime(2026, 5, 13, 10, 0, tzinfo=timezone.utc),
        sentiment="neutral",
        importance="medium",
    )
    assert item.symbol == MARKET_SYMBOL
