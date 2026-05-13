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
