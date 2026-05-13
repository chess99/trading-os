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


import sqlite3
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
import re


def _make_item(symbol: str, title: str, fetched_at: datetime | None = None):
    from trading_os.news.models import NewsItem
    return NewsItem(
        symbol=symbol,
        title=title,
        content="내용",
        source="eastmoney",
        pub_time=datetime(2026, 5, 13, 9, 0, tzinfo=timezone.utc),
        sentiment="neutral",
        importance="low",
        fetched_at=fetched_at or datetime.now(timezone.utc),
    )


def test_ttl_returns_cached_when_fresh(tmp_path):
    """Second read within 24h must return cached rows without re-fetch."""
    from trading_os.news.cache import NewsCache
    cache = NewsCache(tmp_path / "news.db")
    item = _make_item("SSE:600000", "新闻标题")
    cache.save([item])

    result = cache.get_fresh("SSE:600000")
    assert len(result) == 1
    assert result[0].title == "新闻标题"


def test_ttl_returns_empty_when_stale(tmp_path):
    """Rows older than 24h must not be returned as fresh."""
    from trading_os.news.cache import NewsCache
    cache = NewsCache(tmp_path / "news.db")
    stale_time = datetime.now(timezone.utc) - timedelta(hours=25)
    item = _make_item("SSE:600000", "旧新闻", fetched_at=stale_time)
    cache.save([item])

    result = cache.get_fresh("SSE:600000")
    assert result == []


def test_market_news_no_row_growth(tmp_path):
    """Saving market news twice must not grow the row count."""
    from trading_os.news.cache import NewsCache
    from trading_os.news.models import MARKET_SYMBOL
    cache = NewsCache(tmp_path / "news.db")

    items = [_make_item(MARKET_SYMBOL, f"电报{i}") for i in range(3)]
    cache.save(items)
    cache.save(items)  # second save — same titles

    con = sqlite3.connect(str(tmp_path / "news.db"))
    count = con.execute(
        "SELECT COUNT(*) FROM news_cache WHERE symbol = ?", (MARKET_SYMBOL,)
    ).fetchone()[0]
    con.close()
    assert count == 3


def test_market_sentinel_symbol(tmp_path):
    """Market news rows must use '__MARKET__' sentinel, never NULL."""
    from trading_os.news.cache import NewsCache
    from trading_os.news.models import MARKET_SYMBOL
    cache = NewsCache(tmp_path / "news.db")
    cache.save([_make_item(MARKET_SYMBOL, "电报标题")])

    con = sqlite3.connect(str(tmp_path / "news.db"))
    row = con.execute("SELECT symbol FROM news_cache").fetchone()
    con.close()
    assert row[0] == MARKET_SYMBOL
    assert row[0] is not None


def test_fetched_at_utc_format(tmp_path):
    """fetched_at stored in DB must match UTC ISO8601 +00:00 format."""
    from trading_os.news.cache import NewsCache
    cache = NewsCache(tmp_path / "news.db")
    cache.save([_make_item("SSE:600000", "格式测试")])

    con = sqlite3.connect(str(tmp_path / "news.db"))
    fetched_at = con.execute("SELECT fetched_at FROM news_cache").fetchone()[0]
    con.close()
    pattern = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?\+00:00"
    assert re.match(pattern, fetched_at), f"Bad format: {fetched_at}"
