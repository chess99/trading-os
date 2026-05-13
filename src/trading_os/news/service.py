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

        lines: list[str] = ["### 近期新闻\n"]
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
