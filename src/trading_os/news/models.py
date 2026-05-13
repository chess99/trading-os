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
