# News Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `src/trading_os/news/` — a SQLite-cached news fetcher that injects A-share news context into elder-screen, canslim-position-monitor, value-position-monitor, and daily-workflow skills.

**Architecture:** Five-file module: `models.py` (NewsItem dataclass), `fetcher.py` (AKShare + CLS telegraph), `cache.py` (SQLite 24h TTL), `service.py` (public API), `__init__.py` (re-exports). Skills call `get_stock_news(symbol)` or `get_market_news()` — cache and fetch are transparent.

**Tech Stack:** Python stdlib `sqlite3`, `requests`, `akshare`, `dataclasses`, `threading` (per-symbol lock)

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `src/trading_os/news/__init__.py` | Create | Re-export public API |
| `src/trading_os/news/models.py` | Create | `NewsItem` dataclass |
| `src/trading_os/news/fetcher.py` | Create | `fetch_stock_news`, `fetch_cls_telegraph` |
| `src/trading_os/news/cache.py` | Create | SQLite read/write, 24h TTL, per-symbol lock |
| `src/trading_os/news/service.py` | Create | `get_stock_news`, `get_market_news`, `format_news_for_prompt` |
| `tests/test_news_module.py` | Create | All required tests from spec |
| `.gitignore` | Modify | Add `data/news_cache.db` (already has `/data/` — verify) |
| `.claude/skills/elder-screen/SKILL.md` | Modify | Add news context injection instructions |
| `.claude/skills/canslim-position-monitor/SKILL.md` | Modify | Add news context injection instructions |
| `.claude/skills/value-position-monitor/SKILL.md` | Modify | Add news context injection instructions |
| `.claude/skills/daily-workflow/SKILL.md` | Modify | Add market news section to daily report |

---

## Task 1: `models.py` — NewsItem dataclass

**Files:**
- Create: `src/trading_os/news/models.py`

- [ ] **Step 1: Write the failing test**

```python
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
    assert item.symbol == "__MARKET__"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /path/to/trading-os
pytest tests/test_news_module.py::test_newsitem_defaults tests/test_news_module.py::test_newsitem_market_sentinel -v
```

Expected: `ImportError: No module named 'trading_os.news'`

- [ ] **Step 3: Write `models.py`**

```python
# src/trading_os/news/models.py
"""NewsItem dataclass — shared across fetcher, cache, and service."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

MARKET_SYMBOL = "__MARKET__"
"""Sentinel used in the cache to identify market-level news (e.g. CLS telegraph).

Must NOT be None — SQLite UNIQUE indexes treat every NULL as distinct,
which breaks INSERT OR REPLACE deduplication.
"""


@dataclass
class NewsItem:
    symbol: str
    """Stock symbol (e.g. 'SSE:600000') or MARKET_SYMBOL for market-wide news."""
    title: str
    content: str
    source: str
    """'eastmoney' | 'cls_telegraph'"""
    pub_time: datetime
    sentiment: str
    """'positive' | 'negative' | 'neutral' — keyword-scored at fetch time."""
    importance: str
    """'high' | 'medium' | 'low' — keyword-scored at fetch time."""
    url: str = ""
    fetched_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 4: Create `src/trading_os/news/__init__.py` (empty for now)**

```python
# src/trading_os/news/__init__.py
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_news_module.py::test_newsitem_defaults tests/test_news_module.py::test_newsitem_market_sentinel -v
```

Expected: `2 passed`

- [ ] **Step 6: Commit**

```bash
git add src/trading_os/news/__init__.py src/trading_os/news/models.py tests/test_news_module.py
git commit -m "feat(news): add NewsItem dataclass and MARKET_SYMBOL sentinel"
```

---

## Task 2: `cache.py` — SQLite read/write with 24h TTL

**Files:**
- Create: `src/trading_os/news/cache.py`
- Modify: `tests/test_news_module.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_news_module.py`:

```python
import sqlite3
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
import re


def _make_item(symbol: str, title: str, fetched_at: datetime | None = None) -> "NewsItem":
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
    assert row[0] == "__MARKET__"
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_news_module.py -k "test_ttl or test_market" -v
```

Expected: `ImportError: cannot import name 'NewsCache'`

- [ ] **Step 3: Write `cache.py`**

```python
# src/trading_os/news/cache.py
"""SQLite-backed news cache with 24h TTL.

Schema notes:
- symbol is NOT NULL — use MARKET_SYMBOL sentinel for market-wide news.
  SQLite UNIQUE treats every NULL as distinct, breaking INSERT OR REPLACE dedup.
- fetched_at stored as UTC ISO8601 with +00:00 suffix for consistent TEXT comparison.
- Per-symbol threading lock prevents redundant concurrent fetches.
"""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path

from .models import NewsItem

_TTL_HOURS = 24

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS news_cache (
    id          INTEGER PRIMARY KEY,
    symbol      TEXT    NOT NULL,
    title       TEXT    NOT NULL,
    content     TEXT,
    source      TEXT,
    pub_time    TEXT,
    sentiment   TEXT,
    importance  TEXT,
    url         TEXT,
    fetched_at  TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_symbol_fetched ON news_cache(symbol, fetched_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_dedup ON news_cache(symbol, title);
"""

# Per-symbol locks prevent concurrent cold-cache stampedes.
_SYMBOL_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_LOCK = threading.Lock()


def _get_symbol_lock(symbol: str) -> threading.Lock:
    with _LOCKS_LOCK:
        if symbol not in _SYMBOL_LOCKS:
            _SYMBOL_LOCKS[symbol] = threading.Lock()
        return _SYMBOL_LOCKS[symbol]


class NewsCache:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.executescript(_CREATE_SQL)

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.path))
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=NORMAL")
        return con

    def get_fresh(self, symbol: str) -> list[NewsItem]:
        """Return cached items for symbol if fetched within the last 24h, else []."""
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=_TTL_HOURS)).isoformat()
        with self._connect() as con:
            rows = con.execute(
                "SELECT symbol, title, content, source, pub_time, sentiment, importance, url, fetched_at "
                "FROM news_cache WHERE symbol = ? AND fetched_at >= ?",
                (symbol, cutoff),
            ).fetchall()
        return [_row_to_item(r) for r in rows]

    def save(self, items: list[NewsItem]) -> None:
        """Upsert news items. Duplicate (symbol, title) rows are replaced."""
        if not items:
            return
        rows = [_item_to_row(item) for item in items]
        with self._connect() as con:
            con.executemany(
                "INSERT OR REPLACE INTO news_cache "
                "(symbol, title, content, source, pub_time, sentiment, importance, url, fetched_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )

    def lock(self, symbol: str) -> threading.Lock:
        """Per-symbol lock to serialize cold-cache fetches."""
        return _get_symbol_lock(symbol)


def _item_to_row(item: NewsItem) -> tuple:
    return (
        item.symbol,
        item.title,
        item.content,
        item.source,
        item.pub_time.isoformat() if item.pub_time else None,
        item.sentiment,
        item.importance,
        item.url,
        item.fetched_at.astimezone(timezone.utc).isoformat(),
    )


def _row_to_item(row: tuple) -> NewsItem:
    symbol, title, content, source, pub_time, sentiment, importance, url, fetched_at = row
    return NewsItem(
        symbol=symbol,
        title=title or "",
        content=content or "",
        source=source or "",
        pub_time=datetime.fromisoformat(pub_time) if pub_time else datetime.now(timezone.utc),
        sentiment=sentiment or "neutral",
        importance=importance or "medium",
        url=url or "",
        fetched_at=datetime.fromisoformat(fetched_at),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_news_module.py -k "test_ttl or test_market or test_fetched_at" -v
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add src/trading_os/news/cache.py tests/test_news_module.py
git commit -m "feat(news): add NewsCache with SQLite 24h TTL and sentinel symbol"
```

---

## Task 3: `fetcher.py` — AKShare + CLS telegraph

**Files:**
- Create: `src/trading_os/news/fetcher.py`
- Modify: `tests/test_news_module.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_news_module.py`:

```python
from unittest.mock import patch, MagicMock
import pandas as pd


def _make_em_df() -> pd.DataFrame:
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_news_module.py -k "test_symbol_strip or test_fetch" -v
```

Expected: `ImportError: cannot import name 'fetch_stock_news'`

- [ ] **Step 3: Write `fetcher.py`**

```python
# src/trading_os/news/fetcher.py
"""News fetchers for stock-level (EastMoney) and market-level (CLS telegraph) news.

Key constraints:
- ak.stock_news_em requires a bare 6-digit ticker, not 'SSE:600000'.
- ak.stock_news_em has hardcoded pageSize=10; limit > 10 is silently truncated.
- CLS telegraph returns ~20 most-recent items; no date filtering, no pagination.
- Both fetchers return [] on any exception — news is advisory, not critical path.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import requests

log = logging.getLogger(__name__)

try:
    import akshare as ak
except ImportError:
    ak = None  # type: ignore[assignment]

from .models import NewsItem, MARKET_SYMBOL

_CLS_URL = "https://www.cls.cn/nodeapi/telegraphList"
_CLS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.cls.cn/",
}
_CLS_TIMEOUT = 30

# Sentiment keyword dicts (simplified; extend as needed).
_POSITIVE_WORDS = {"涨", "涨停", "突破", "新高", "盈利", "增长", "利好", "超预期", "大涨", "上涨"}
_NEGATIVE_WORDS = {"跌", "跌停", "亏损", "下滑", "减少", "利空", "低于预期", "大跌", "下跌", "风险"}
_HIGH_IMPORTANCE = {"涨停", "跌停", "重大", "利好", "利空", "公告", "停牌", "重组", "并购", "退市"}
_MEDIUM_IMPORTANCE = {"涨", "跌", "业绩", "季报", "年报", "分红", "增持", "减持"}


def _strip_exchange(symbol: str) -> str:
    """'SSE:600000' -> '600000', 'SZSE:000001' -> '000001'."""
    return symbol.split(":")[-1]


def _score_sentiment(text: str) -> str:
    pos = sum(1 for w in _POSITIVE_WORDS if w in text)
    neg = sum(1 for w in _NEGATIVE_WORDS if w in text)
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


def _score_importance(text: str) -> str:
    if any(w in text for w in _HIGH_IMPORTANCE):
        return "high"
    if any(w in text for w in _MEDIUM_IMPORTANCE):
        return "medium"
    return "low"


def _cls_level_to_importance(level: str) -> str:
    """CLS level 'A'/'B' = high/medium, 'C' = low."""
    return {"A": "high", "B": "medium"}.get(level, "low")


def fetch_stock_news(symbol: str, limit: int = 10) -> list[NewsItem]:
    """Fetch recent news for a stock from EastMoney via akshare.

    symbol: 'SSE:600000' or 'SZSE:000001' format.
    Returns at most 10 items (akshare hardcodes pageSize=10).
    Returns [] silently on any error.
    """
    if ak is None:
        log.warning("akshare not installed; returning empty news")
        return []
    ticker = _strip_exchange(symbol)
    try:
        df = ak.stock_news_em(symbol=ticker)
    except Exception as exc:
        log.debug("fetch_stock_news failed for %s: %s", symbol, exc)
        return []

    if df is None or df.empty:
        return []

    items: list[NewsItem] = []
    for _, row in df.head(limit).iterrows():
        title = str(row.get("新闻标题", "") or "")
        content = str(row.get("新闻内容", "") or row.get("新闻摘要", "") or "")
        text = title + content
        pub_str = str(row.get("发布时间", "") or "")
        try:
            pub_time = datetime.fromisoformat(pub_str).astimezone(timezone.utc)
        except (ValueError, TypeError):
            pub_time = datetime.now(timezone.utc)

        items.append(NewsItem(
            symbol=symbol,
            title=title,
            content=content,
            source="eastmoney",
            pub_time=pub_time,
            sentiment=_score_sentiment(text),
            importance=_score_importance(text),
            url=str(row.get("新闻链接", "") or ""),
        ))
    return items


def fetch_cls_telegraph(limit: int = 20) -> list[NewsItem]:
    """Fetch recent CLS telegraph items (市场级新闻, not stock-specific).

    Returns at most `limit` most-recent items.
    Returns [] silently on any error — no fallback to news_cctv
    (CCTV returns TV transcripts, not financial news).
    """
    try:
        resp = requests.get(_CLS_URL, headers=_CLS_HEADERS, timeout=_CLS_TIMEOUT)
    except Exception as exc:
        log.debug("fetch_cls_telegraph request failed: %s", exc)
        return []

    if not resp.ok:
        log.debug("fetch_cls_telegraph HTTP %s", resp.status_code)
        return []

    try:
        data = resp.json()
        roll_data = data.get("data", {}).get("roll_data", [])
    except Exception as exc:
        log.debug("fetch_cls_telegraph parse failed: %s", exc)
        return []

    items: list[NewsItem] = []
    for entry in roll_data[:limit]:
        title = str(entry.get("title", "") or "")
        content = str(entry.get("content", "") or "")
        if not title and not content:
            continue
        ctime = entry.get("ctime", 0)
        try:
            pub_time = datetime.fromtimestamp(int(ctime), tz=timezone.utc)
        except (ValueError, TypeError):
            pub_time = datetime.now(timezone.utc)

        level = str(entry.get("level", "C"))
        text = title + content
        items.append(NewsItem(
            symbol=MARKET_SYMBOL,
            title=title or content[:40],
            content=content,
            source="cls_telegraph",
            pub_time=pub_time,
            sentiment=_score_sentiment(text),
            importance=_cls_level_to_importance(level),
            url=str(entry.get("shareurl", "") or ""),
        ))
    return items
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_news_module.py -k "test_symbol_strip or test_fetch" -v
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add src/trading_os/news/fetcher.py tests/test_news_module.py
git commit -m "feat(news): add fetcher for EastMoney stock news and CLS telegraph"
```

---

## Task 4: `service.py` — public API wiring cache + fetcher

**Files:**
- Create: `src/trading_os/news/service.py`
- Modify: `src/trading_os/news/__init__.py`
- Modify: `tests/test_news_module.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_news_module.py`:

```python
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
    from trading_os.news.cache import NewsCache
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
    items = [
        _make_item("SSE:600000", f"标题{i}", )
        for i in range(10)
    ]
    # Give each item long content
    for item in items:
        item.content = "内容" * 200
    result = svc.format_news_for_prompt(items)
    assert len(result) < 4000
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_news_module.py -k "test_get_stock_news or test_format" -v
```

Expected: `ImportError: cannot import name 'NewsService'`

- [ ] **Step 3: Write `service.py`**

```python
# src/trading_os/news/service.py
"""Public API for news retrieval.

Usage:
    from trading_os.news import get_stock_news, get_market_news, format_news_for_prompt

    items = get_stock_news("SSE:600000")
    market = get_market_news()
    prompt_text = format_news_for_prompt(items)
"""
from __future__ import annotations

from pathlib import Path

from .cache import NewsCache
from .fetcher import fetch_stock_news, fetch_cls_telegraph
from .models import NewsItem, MARKET_SYMBOL

_CONTENT_PREVIEW_CHARS = 200
_MAX_PROMPT_CHARS = 3500


def _default_cache_path() -> Path:
    """Resolve data/news_cache.db relative to repo root (mirrors paths.py pattern)."""
    here = Path(__file__).resolve()
    for p in here.parents:
        if (p / "pyproject.toml").exists():
            return p / "data" / "news_cache.db"
    return Path("data/news_cache.db")


class NewsService:
    """Wires cache + fetcher. Use the module-level functions for normal usage."""

    def __init__(self, cache_path: Path | None = None) -> None:
        self._cache = NewsCache(cache_path or _default_cache_path())

    def get_stock_news(self, symbol: str, limit: int = 10) -> list[NewsItem]:
        """Return recent news for symbol (up to 10 items, akshare limit).

        Cache hit (fetched within 24h): returns cached rows.
        Cache miss: calls EastMoney via akshare, writes to cache, returns results.
        Returns [] on any fetch failure — news is advisory.
        """
        with self._cache.lock(symbol):
            cached = self._cache.get_fresh(symbol)
            if cached:
                return cached[:limit]
            items = fetch_stock_news(symbol, limit=limit)
            if items:
                self._cache.save(items)
            return items

    def get_market_news(self, limit: int = 20) -> list[NewsItem]:
        """Return recent CLS telegraph items (market-wide, not stock-specific).

        Cache hit (fetched within 24h): returns cached rows.
        Cache miss: calls CLS telegraph, writes to cache, returns results.
        Returns [] on any fetch failure.
        """
        with self._cache.lock(MARKET_SYMBOL):
            cached = self._cache.get_fresh(MARKET_SYMBOL)
            if cached:
                return cached[:limit]
            items = fetch_cls_telegraph(limit=limit)
            if items:
                self._cache.save(items)
            return items

    def format_news_for_prompt(self, items: list[NewsItem]) -> str:
        """Format news items as a Markdown snippet for LLM prompt injection.

        Truncates content to keep total output under 3500 chars.
        Returns '' for empty input.
        """
        if not items:
            return ""

        lines: list[str] = ["### 📰 近期新闻\n"]
        total = len(lines[0])
        for item in items:
            content_preview = item.content[:_CONTENT_PREVIEW_CHARS].replace("\n", " ")
            sentiment_icon = {"positive": "🟢", "negative": "🔴", "neutral": "⚪"}.get(
                item.sentiment, "⚪"
            )
            importance_tag = {"high": "[重要]", "medium": "", "low": ""}.get(
                item.importance, ""
            )
            pub = item.pub_time.strftime("%m-%d %H:%M") if item.pub_time else ""
            line = (
                f"- {sentiment_icon}{importance_tag} **{item.title}** ({pub})\n"
                f"  {content_preview}\n"
            )
            if total + len(line) > _MAX_PROMPT_CHARS:
                lines.append("  *(更多新闻已截断)*\n")
                break
            lines.append(line)
            total += len(line)

        return "".join(lines)


# Module-level singleton using default cache path.
_default_service: NewsService | None = None


def _get_service() -> NewsService:
    global _default_service
    if _default_service is None:
        _default_service = NewsService()
    return _default_service


def get_stock_news(symbol: str, limit: int = 10) -> list[NewsItem]:
    """Return recent stock news. Cached for 24h."""
    return _get_service().get_stock_news(symbol, limit=limit)


def get_market_news(limit: int = 20) -> list[NewsItem]:
    """Return recent CLS telegraph market news. Cached for 24h."""
    return _get_service().get_market_news(limit=limit)


def format_news_for_prompt(items: list[NewsItem]) -> str:
    """Format news items as Markdown for LLM context injection."""
    return _get_service().format_news_for_prompt(items)
```

- [ ] **Step 4: Update `__init__.py` to re-export public API**

```python
# src/trading_os/news/__init__.py
"""News fetching and caching for trading_os skills.

Usage:
    from trading_os.news import get_stock_news, get_market_news, format_news_for_prompt
"""
from .service import get_stock_news, get_market_news, format_news_for_prompt
from .models import NewsItem, MARKET_SYMBOL

__all__ = [
    "get_stock_news",
    "get_market_news",
    "format_news_for_prompt",
    "NewsItem",
    "MARKET_SYMBOL",
]
```

- [ ] **Step 5: Run all tests**

```bash
pytest tests/test_news_module.py -v
```

Expected: all tests pass (14+ passing)

- [ ] **Step 6: Commit**

```bash
git add src/trading_os/news/service.py src/trading_os/news/__init__.py tests/test_news_module.py
git commit -m "feat(news): add NewsService public API with cache+fetch wiring"
```

---

## Task 5: Verify `.gitignore` and smoke test

**Files:**
- Verify: `.gitignore`

- [ ] **Step 1: Verify `data/news_cache.db` is already gitignored**

```bash
git check-ignore -v data/news_cache.db
```

Expected output: `.gitignore:N:/data/` (the existing `/data/` rule covers it)

If NOT ignored, append to `.gitignore`:
```
data/news_cache.db
```

- [ ] **Step 2: Smoke test the full module imports cleanly**

```bash
python -c "from trading_os.news import get_stock_news, get_market_news, format_news_for_prompt; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Run full test suite to catch regressions**

```bash
pytest tests/test_news_module.py tests/test_akshare_source.py -v
```

Expected: all pass

- [ ] **Step 4: Commit (if .gitignore was modified)**

```bash
git add .gitignore
git commit -m "chore: ensure data/news_cache.db is gitignored"
```

---

## Task 6: Integrate into `elder-screen` skill

**Files:**
- Modify: `.claude/skills/elder-screen/SKILL.md`

Read the current skill file first:
```bash
cat .claude/skills/elder-screen/SKILL.md
```

Find the section where abnormal volume/price (量价异动) is analyzed (look for "量" or "异动" or "MACD" or the second filter / daily analysis section).

- [ ] **Step 1: Add news context instructions after the volume/price analysis section**

Find the end of the "第二滤网" or daily analysis section. After that section's conclusion, add:

```markdown
### 📰 新闻背景（量价异动辅助判断）

调用 `get_stock_news("{symbol}")` 获取近期新闻，附在量价分析结论之后：

```python
from trading_os.news import get_stock_news, format_news_for_prompt
items = get_stock_news("{symbol}")  # symbol from analysis context
news_section = format_news_for_prompt(items)
```

如果 `news_section` 非空，在分析报告中追加：

> **近期新闻**：{news_section}

新闻是背景参考，不改变技术信号判断。若技术面已给出明确信号（如 MACD 背离确认），新闻只用于解释"为什么"，不用于推翻信号。
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/elder-screen/SKILL.md
git commit -m "feat(skills): inject stock news context into elder-screen analysis"
```

---

## Task 7: Integrate into `canslim-position-monitor` skill

**Files:**
- Modify: `.claude/skills/canslim-position-monitor/SKILL.md`

Read the current skill file:
```bash
cat .claude/skills/canslim-position-monitor/SKILL.md
```

Find the "核心假设验证" or hypothesis verification step (where the skill checks if the original buy thesis still holds).

- [ ] **Step 1: Add news check to the hypothesis verification step**

Locate the hypothesis verification section. Add after it:

```markdown
#### 📰 新闻核查（核心假设是否被新公告否定）

```python
from trading_os.news import get_stock_news, format_news_for_prompt
items = get_stock_news("{symbol}")
news_section = format_news_for_prompt(items)
```

将 `news_section` 注入到假设验证分析中。重点关注：
- 是否有业绩预警、盈利下修公告
- 是否有监管/政策负面消息
- 是否有管理层变动、大股东减持公告

如无重要新闻，填写"无重要近期新闻"并继续持有判断。
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/canslim-position-monitor/SKILL.md
git commit -m "feat(skills): inject stock news into canslim hypothesis verification"
```

---

## Task 8: Integrate into `value-position-monitor` skill

**Files:**
- Modify: `.claude/skills/value-position-monitor/SKILL.md`

Read the current skill file:
```bash
cat .claude/skills/value-position-monitor/SKILL.md
```

Find the "逻辑止损" or moat/thesis monitoring section.

- [ ] **Step 1: Add news scan to the logical stop-loss check**

Locate the moat/thesis monitoring step. Add after it:

```markdown
#### 📰 新闻扫描（护城河是否受损）

```python
from trading_os.news import get_stock_news, format_news_for_prompt
items = get_stock_news("{symbol}")
news_section = format_news_for_prompt(items)
```

将 `news_section` 注入逻辑止损判断。护城河相关的危险信号包括：
- 核心业务被监管限制或打压
- 主要客户流失或合同终止公告
- 管理层重大变动（创始人离职/被查）
- 竞争对手获得颠覆性优势的公告

新闻是"早期预警"，出现上述信号时标记为"需要深度复查"，不自动触发卖出。
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/value-position-monitor/SKILL.md
git commit -m "feat(skills): inject stock news into value-position-monitor moat check"
```

---

## Task 9: Integrate into `daily-workflow` skill

**Files:**
- Modify: `.claude/skills/daily-workflow/SKILL.md`

Read the current skill file:
```bash
cat .claude/skills/daily-workflow/SKILL.md
```

Find the daily report generation step (Step 5 or the "生成日报" section).

- [ ] **Step 1: Add market news section to daily report**

Locate the daily report output format. Before the final "建议下一步行动" section (or at the end of the report template), add:

```markdown
## 📰 近期市场动态

```python
from trading_os.news import get_market_news, format_news_for_prompt
items = get_market_news(limit=15)
news_section = format_news_for_prompt(items)
```

在日报末尾追加此栏（如 `news_section` 非空）：

---
{news_section}
---

此栏为背景参考，不影响个股分析结论。
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/daily-workflow/SKILL.md
git commit -m "feat(skills): add market news section to daily-workflow report"
```

---

## Task 10: Final integration check

- [ ] **Step 1: Run complete test suite**

```bash
pytest tests/ -v --tb=short
```

Expected: all existing tests pass, all new news tests pass

- [ ] **Step 2: Verify module is importable from project root**

```bash
python -c "
from trading_os.news import get_stock_news, get_market_news, format_news_for_prompt, NewsItem, MARKET_SYMBOL
print('All exports OK')
print('MARKET_SYMBOL:', MARKET_SYMBOL)
"
```

Expected:
```
All exports OK
MARKET_SYMBOL: __MARKET__
```

- [ ] **Step 3: Verify news_cache.db is not tracked by git**

```bash
python -c "from trading_os.news import get_market_news; get_market_news()" 2>/dev/null || true
git status data/
```

Expected: `data/news_cache.db` either doesn't appear or appears as ignored

- [ ] **Step 4: Final commit**

```bash
git add -p  # review any remaining unstaged changes
git commit -m "feat: complete news module Phase A — fetch, cache, skill integration"
```

---

## GSTACK REVIEW REPORT

| Run | Status | Findings |
|-----|--------|----------|
| NO REVIEWS YET — run `/autoplan` | — | — |
