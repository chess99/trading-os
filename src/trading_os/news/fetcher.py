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
