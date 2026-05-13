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
