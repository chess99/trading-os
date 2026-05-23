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


from unittest.mock import patch, MagicMock
import pandas as pd


def _make_em_df():
    """Minimal DataFrame matching ak.stock_news_em output columns."""
    return pd.DataFrame({
        "新闻标题": ["标题A", "标题B"],
        "新闻内容": ["内容A", "内容B"],
        "新闻摘要": ["摘要A", "摘要B"],
        "新闻链接": ["http://a.com", "http://b.com"],
        "发布时间": ["2026-05-13 09:00:00", "2026-05-13 10:00:00"],
    })


def test_symbol_strip_sse():
    """fetch_stock_news('SSE:600000') must call ak.stock_news_em with '600000'."""
    from trading_os.news.fetcher import fetch_stock_news
    with patch("trading_os.news.fetcher.ak") as mock_ak:
        mock_ak.stock_news_em.return_value = _make_em_df()
        result = fetch_stock_news("SSE:600000")
        mock_ak.stock_news_em.assert_called_once_with(symbol="600000")
    assert len(result) == 2
    assert result[0].source == "eastmoney"
    assert result[0].symbol == "SSE:600000"


def test_symbol_strip_szse():
    """fetch_stock_news('SZSE:000001') must call ak.stock_news_em with '000001'."""
    from trading_os.news.fetcher import fetch_stock_news
    with patch("trading_os.news.fetcher.ak") as mock_ak:
        mock_ak.stock_news_em.return_value = _make_em_df()
        fetch_stock_news("SZSE:000001")
        mock_ak.stock_news_em.assert_called_once_with(symbol="000001")


def test_fetch_stock_news_returns_empty_on_exception():
    """fetch_stock_news must return [] silently on any exception."""
    from trading_os.news.fetcher import fetch_stock_news
    with patch("trading_os.news.fetcher.ak") as mock_ak:
        mock_ak.stock_news_em.side_effect = Exception("rate limited")
        result = fetch_stock_news("SSE:600000")
    assert result == []


def test_fetch_cls_returns_empty_on_exception():
    """fetch_cls_telegraph must return [] silently on network failure."""
    from trading_os.news.fetcher import fetch_cls_telegraph
    with patch("trading_os.news.fetcher.requests") as mock_req:
        mock_req.get.side_effect = Exception("connection refused")
        result = fetch_cls_telegraph()
    assert result == []


def test_fetch_cls_parses_items():
    """fetch_cls_telegraph must parse CLS JSON response into NewsItems."""
    from trading_os.news.fetcher import fetch_cls_telegraph
    from trading_os.news.models import MARKET_SYMBOL
    fake_response = MagicMock()
    fake_response.ok = True
    fake_response.json.return_value = {
        "error": 0,
        "data": {
            "roll_data": [
                {
                    "title": "央行降息",
                    "content": "央行宣布降息25bp",
                    "shareurl": "http://cls.cn/1",
                    "ctime": 1715574000,
                    "level": "A",
                    "subjects": [],
                },
                {
                    "title": "",
                    "content": "无标题电报内容",
                    "shareurl": "http://cls.cn/2",
                    "ctime": 1715574060,
                    "level": "C",
                    "subjects": [],
                },
            ]
        },
    }
    with patch("trading_os.news.fetcher.requests") as mock_req:
        mock_req.get.return_value = fake_response
        result = fetch_cls_telegraph()
    assert len(result) == 2
    assert result[0].symbol == MARKET_SYMBOL
    assert result[0].title == "央行降息"
    assert result[0].importance == "high"   # level A
    assert result[1].importance == "low"    # level C
    assert result[0].source == "cls_telegraph"


def test_get_stock_news_uses_cache_on_second_call(tmp_path):
    """Second call within 24h must return cached data without calling fetcher."""
    from trading_os.news.service import NewsService
    svc = NewsService(cache_path=tmp_path / "news.db")

    fake_items = [_make_item("SSE:600000", "缓存新闻")]
    with patch("trading_os.news.service.fetch_stock_news", return_value=fake_items) as mock_fetch:
        svc.get_stock_news("SSE:600000")
        svc.get_stock_news("SSE:600000")
        assert mock_fetch.call_count == 1  # fetcher called only once


def test_get_stock_news_refetches_when_stale(tmp_path):
    """After cache expires, fetcher must be called again."""
    from trading_os.news.service import NewsService
    svc = NewsService(cache_path=tmp_path / "news.db")

    # Pre-populate with stale item
    stale_time = datetime.now(timezone.utc) - timedelta(hours=25)
    stale = _make_item("SSE:600000", "旧新闻", fetched_at=stale_time)
    svc._cache.save([stale])

    fresh_items = [_make_item("SSE:600000", "新新闻")]
    with patch("trading_os.news.service.fetch_stock_news", return_value=fresh_items) as mock_fetch:
        result = svc.get_stock_news("SSE:600000")
        assert mock_fetch.call_count == 1
    assert result[0].title == "新新闻"


def test_format_news_for_prompt_empty():
    """format_news_for_prompt([]) must return '' without raising."""
    from trading_os.news.service import NewsService
    svc = NewsService()
    result = svc.format_news_for_prompt([])
    assert result == ""


def test_format_news_for_prompt_truncation():
    """10 items with long content must produce output under 4000 chars."""
    from trading_os.news.service import NewsService
    svc = NewsService()
    items = [_make_item("SSE:600000", f"标题{i}") for i in range(10)]
    for item in items:
        item.content = "内容" * 200
    result = svc.format_news_for_prompt(items)
    assert len(result) < 4000
