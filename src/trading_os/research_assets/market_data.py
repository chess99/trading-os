from __future__ import annotations

import html
import json
import math
import re
import unicodedata
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from urllib.parse import urlencode, urljoin, urlsplit

TENCENT_QUOTE_ENDPOINT = "https://qt.gtimg.cn/q="
CNINFO_ANNOUNCEMENT_ENDPOINT = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_STATIC_BASE = "https://static.cninfo.com.cn/"

MARKET_TIMEZONE = timezone(timedelta(hours=8), "Asia/Shanghai")
_CLOSE_TIME = time(15, 0)
_FUTURE_TOLERANCE = timedelta(minutes=5)
_SYMBOL_RE = re.compile(r"^CN:([0-9]{6})$")
_TENCENT_ROW_RE = re.compile(r'v_((?:sh|sz|bj)[0-9]{6})="([^"\r\n]*)";')
_CNINFO_ID_RE = re.compile(r"^[0-9]+$")
_CNINFO_PDF_RE = re.compile(r"^/finalpage/[0-9]{4}-[0-9]{2}-[0-9]{2}/([0-9]+)\.pdf$", re.I)

QuoteFetcher = Callable[[str], bytes | str]
AnnouncementFetcher = Callable[[str, Mapping[str, str]], object]


class MarketDataError(RuntimeError):
    """Raised when an upstream market-data response is incomplete or ambiguous."""


@dataclass(frozen=True)
class DailyClose:
    symbol: str
    name: str
    close: float
    trading_date: str
    closed_at: str
    source_url: str
    currency: str = "CNY"
    adjustment: str = "none"


@dataclass(frozen=True)
class Announcement:
    announcement_id: str
    symbol: str
    title: str
    published_at: str
    url: str


def fetch_tencent_daily_closes(
    companies: Mapping[str, str | None],
    *,
    trading_date: str | date,
    fetched_at: str | datetime | None = None,
    fetcher: QuoteFetcher | None = None,
    chunk_size: int = 80,
) -> tuple[DailyClose, ...]:
    """Fetch an exact set of official, unadjusted A-share closing prices.

    Tencent field 3 is a raw exchange quote. It is accepted as the day's close
    only when field 30 identifies the requested trading day at or after the
    continuous market's official close. Every requested security must appear
    exactly once; callers never receive a partial result.
    """

    target_date = _date(trading_date, "trading_date")
    fetched = _datetime(fetched_at, "fetched_at", default_now=True)
    fetched_market = fetched.astimezone(MARKET_TIMEZONE)
    if fetched_market.date() < target_date:
        raise MarketDataError("fetched_at must not precede trading_date")
    if isinstance(chunk_size, bool) or not isinstance(chunk_size, int):
        raise MarketDataError("chunk_size must be an integer between 1 and 100")
    if not 1 <= chunk_size <= 100:
        raise MarketDataError("chunk_size must be an integer between 1 and 100")
    if not isinstance(companies, Mapping):
        raise MarketDataError("companies must map CN symbols to expected names")

    expected: dict[str, tuple[str, str | None]] = {}
    symbols: set[str] = set()
    for raw_symbol, raw_name in companies.items():
        symbol, ticker = _symbol(raw_symbol)
        if symbol in symbols:
            raise MarketDataError(f"duplicate requested symbol: {symbol}")
        symbols.add(symbol)
        name = _optional_name(raw_name)
        code = _tencent_code(ticker)
        if code in expected:
            raise MarketDataError(f"duplicate Tencent security identity: {code}")
        expected[code] = (symbol, name)

    if not expected:
        return ()

    fetch = fetcher or _fetch_tencent_text
    observed: dict[str, tuple[list[str], str]] = {}
    codes = sorted(expected)
    for offset in range(0, len(codes), chunk_size):
        chunk = codes[offset : offset + chunk_size]
        source_url = f"{TENCENT_QUOTE_ENDPOINT}{','.join(chunk)}"
        try:
            raw_response = fetch(source_url)
        except MarketDataError:
            raise
        except Exception as exc:
            raise MarketDataError(f"Tencent quote request failed: {exc}") from exc
        text_response = _decode_tencent(raw_response)
        matches = list(_TENCENT_ROW_RE.finditer(text_response))
        residue = _TENCENT_ROW_RE.sub("", text_response)
        if residue.strip():
            raise MarketDataError("Tencent quote response contains malformed content")
        if len(matches) != len(chunk):
            raise MarketDataError(
                "Tencent response count does not match requested chunk: "
                f"requested={len(chunk)}, rows={len(matches)}"
            )

        chunk_codes: set[str] = set()
        for match in matches:
            code, value = match.groups()
            if code not in expected:
                raise MarketDataError(f"Tencent returned an unrequested security: {code}")
            if code not in chunk:
                raise MarketDataError(f"Tencent returned a security from another chunk: {code}")
            if code in observed or code in chunk_codes:
                raise MarketDataError(f"Tencent returned a duplicate quote: {code}")
            fields = value.split("~")
            if len(fields) <= 30:
                raise MarketDataError(f"Tencent quote lacks required fields: {code}")
            if fields[2] != code[2:]:
                raise MarketDataError(f"Tencent ticker does not match requested code: {code}")
            returned_name = _name(fields[1], f"Tencent name for {code}")
            expected_name = expected[code][1]
            if expected_name is not None and _name_key(returned_name) != _name_key(expected_name):
                raise MarketDataError(
                    f"Tencent name does not match requested security: {code} "
                    f"expected={expected_name!r}, returned={returned_name!r}"
                )
            _tencent_close_timestamp(
                fields[30],
                code=code,
                trading_date=target_date,
                fetched_at=fetched,
            )
            _positive_number(fields[3], f"Tencent close for {code}")
            observed[code] = (fields, source_url)
            chunk_codes.add(code)

        missing_chunk = sorted(set(chunk) - chunk_codes)
        if missing_chunk:
            raise MarketDataError(
                "Tencent response does not cover the requested chunk: " + ", ".join(missing_chunk)
            )

    missing = sorted(set(expected) - set(observed))
    unexpected = sorted(set(observed) - set(expected))
    if missing or unexpected or len(observed) != len(expected):
        raise MarketDataError(
            f"Tencent response is not exact; missing={missing}, unexpected={unexpected}"
        )

    closes: list[DailyClose] = []
    for code, (symbol, _) in sorted(expected.items(), key=lambda item: item[1][0]):
        fields, source_url = observed[code]
        closed_at = _tencent_close_timestamp(
            fields[30],
            code=code,
            trading_date=target_date,
            fetched_at=fetched,
        )
        closes.append(
            DailyClose(
                symbol=symbol,
                name=_name(fields[1], f"Tencent name for {code}"),
                close=_positive_number(fields[3], f"Tencent close for {code}"),
                trading_date=target_date.isoformat(),
                closed_at=closed_at.isoformat(),
                source_url=source_url,
            )
        )
    return tuple(closes)


def discover_cninfo_announcements(
    start: str | datetime,
    end: str | datetime,
    *,
    fetcher: AnnouncementFetcher | None = None,
    page_size: int = 30,
) -> tuple[Announcement, ...]:
    """Return all A-share announcements in the strict half-open window ``[start, end)``.

    The function exhausts CNInfo's official full-text pagination, validates its
    advertised record count, and then filters non-A-share securities. Identical
    provider rows are de-duplicated; conflicting rows with the same announcement
    and symbol fail closed.
    """

    window_start = _datetime(start, "start")
    window_end = _datetime(end, "end")
    if window_end <= window_start:
        raise MarketDataError("end must be later than start")
    if isinstance(page_size, bool) or not isinstance(page_size, int):
        raise MarketDataError("page_size must be an integer between 1 and 30")
    if not 1 <= page_size <= 30:
        raise MarketDataError("page_size must be an integer between 1 and 30")

    start_market = window_start.astimezone(MARKET_TIMEZONE)
    end_market = window_end.astimezone(MARKET_TIMEZONE)
    inclusive_end = (end_market - timedelta(microseconds=1)).date()
    query_dates = f"{start_market.date().isoformat()}~{inclusive_end.isoformat()}"
    fetch = fetcher or _fetch_cninfo_page

    expected_total: int | None = None
    expected_pages: int | None = None
    raw_count = 0
    page_number = 1
    selected: dict[tuple[str, str], Announcement] = {}
    while True:
        form = {
            "pageNum": str(page_number),
            "pageSize": str(page_size),
            "column": "szse",
            "tabName": "fulltext",
            "plate": "",
            "stock": "",
            "searchkey": "",
            "secid": "",
            "category": "",
            "trade": "",
            "seDate": query_dates,
            "sortName": "",
            "sortType": "",
            "isHLtitle": "true",
        }
        try:
            raw_payload = fetch(CNINFO_ANNOUNCEMENT_ENDPOINT, form)
        except MarketDataError:
            raise
        except Exception as exc:
            raise MarketDataError(f"CNInfo announcement request failed: {exc}") from exc
        payload = _json_object(raw_payload, "CNInfo response")
        total_announcement = _nonnegative_int(
            payload.get("totalAnnouncement"), "CNInfo totalAnnouncement"
        )
        total_records = _nonnegative_int(
            payload.get("totalRecordNum"), "CNInfo totalRecordNum"
        )
        if total_announcement != total_records:
            raise MarketDataError(
                "CNInfo totalAnnouncement and totalRecordNum do not match"
            )
        rows_value = payload.get("announcements")
        if rows_value is None and total_records == 0:
            rows: list[Any] = []
        elif isinstance(rows_value, list):
            rows = rows_value
        else:
            raise MarketDataError("CNInfo announcements must be a list")
        has_more = payload.get("hasMore")
        if not isinstance(has_more, bool):
            raise MarketDataError("CNInfo hasMore must be a boolean")
        total_pages_value = _nonnegative_int(payload.get("totalpages"), "CNInfo totalpages")

        if expected_total is None:
            expected_total = total_records
            expected_pages = max(1, math.ceil(expected_total / page_size))
        elif total_records != expected_total:
            raise MarketDataError("CNInfo total record count changed during pagination")
        assert expected_pages is not None

        if expected_pages == 1:
            if total_pages_value not in {0, 1}:
                raise MarketDataError("CNInfo totalpages is inconsistent with record count")
        elif total_pages_value != expected_pages:
            raise MarketDataError("CNInfo totalpages is inconsistent with record count")

        expected_rows = (
            0
            if expected_total == 0
            else min(page_size, expected_total - (page_number - 1) * page_size)
        )
        if len(rows) != expected_rows:
            raise MarketDataError(
                "CNInfo page size does not match advertised record count: "
                f"page={page_number}, expected={expected_rows}, rows={len(rows)}"
            )
        should_have_more = page_number < expected_pages
        if has_more != should_have_more:
            raise MarketDataError(
                f"CNInfo hasMore is inconsistent on page {page_number}"
            )

        raw_count += len(rows)
        for row in rows:
            announcement = _cninfo_announcement(row)
            if announcement is None:
                continue
            published = datetime.fromisoformat(announcement.published_at)
            if not window_start <= published < window_end:
                continue
            key = (announcement.announcement_id, announcement.symbol)
            previous = selected.get(key)
            if previous is not None and previous != announcement:
                raise MarketDataError(
                    "CNInfo returned conflicting duplicate announcement: "
                    f"{announcement.announcement_id} {announcement.symbol}"
                )
            selected[key] = announcement

        if page_number >= expected_pages:
            break
        page_number += 1

    assert expected_total is not None
    if raw_count != expected_total:
        raise MarketDataError(
            f"CNInfo pagination incomplete: expected={expected_total}, fetched={raw_count}"
        )
    return tuple(
        sorted(
            selected.values(),
            key=lambda item: (item.published_at, item.symbol, item.announcement_id),
        )
    )


def _symbol(value: object) -> tuple[str, str]:
    if not isinstance(value, str):
        raise MarketDataError("symbol must use the CN:000000 form")
    normalized = value.strip().upper()
    match = _SYMBOL_RE.fullmatch(normalized)
    if match is None:
        raise MarketDataError("symbol must use the CN:000000 form")
    return normalized, match.group(1)


def _optional_name(value: object) -> str | None:
    if value is None:
        return None
    return _name(value, "expected company name")


def _name(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise MarketDataError(f"{label} must be a nonblank string")
    result = " ".join(value.split())
    if not result:
        raise MarketDataError(f"{label} must be a nonblank string")
    if any(ord(character) < 32 for character in result):
        raise MarketDataError(f"{label} contains a control character")
    return result


def _name_key(value: str) -> str:
    return "".join(unicodedata.normalize("NFKC", value).split())


def _tencent_code(ticker: str) -> str:
    if ticker.startswith(("600", "601", "603", "605", "688", "689")):
        return f"sh{ticker}"
    if ticker.startswith(("000", "001", "002", "003", "300", "301", "302")):
        return f"sz{ticker}"
    if ticker.startswith(("43", "83", "87", "88", "92")):
        return f"bj{ticker}"
    raise MarketDataError(f"cannot infer an A-share exchange for CN:{ticker}")


def _date(value: str | date, label: str) -> date:
    if isinstance(value, datetime):
        raise MarketDataError(f"{label} must be a date, not a datetime")
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not value.strip():
        raise MarketDataError(f"{label} must be an ISO date")
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise MarketDataError(f"{label} must be an ISO date") from exc


def _datetime(
    value: str | datetime | None,
    label: str,
    *,
    default_now: bool = False,
) -> datetime:
    if value is None:
        if default_now:
            return datetime.now(MARKET_TIMEZONE)
        raise MarketDataError(f"{label} must be an ISO datetime with UTC offset")
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise MarketDataError(f"{label} must be an ISO datetime with UTC offset") from exc
    else:
        raise MarketDataError(f"{label} must be an ISO datetime with UTC offset")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise MarketDataError(f"{label} must include a UTC offset")
    return parsed


def _decode_tencent(value: object) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, bytes):
        raise MarketDataError("Tencent response must be GB18030 bytes or text")
    try:
        return value.decode("gb18030")
    except UnicodeDecodeError as exc:
        raise MarketDataError("Tencent response is not valid GB18030") from exc


def _positive_number(value: object, label: str) -> float:
    if not isinstance(value, str) or not value.strip():
        raise MarketDataError(f"{label} must be a positive number")
    try:
        result = float(value)
    except ValueError as exc:
        raise MarketDataError(f"{label} must be a positive number") from exc
    if not math.isfinite(result) or result <= 0:
        raise MarketDataError(f"{label} must be a positive number")
    return result


def _tencent_close_timestamp(
    value: object,
    *,
    code: str,
    trading_date: date,
    fetched_at: datetime,
) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{14}", value):
        raise MarketDataError(f"Tencent close timestamp is invalid: {code}")
    try:
        closed_at = datetime.strptime(value, "%Y%m%d%H%M%S").replace(
            tzinfo=MARKET_TIMEZONE
        )
    except ValueError as exc:
        raise MarketDataError(f"Tencent close timestamp is invalid: {code}") from exc
    if closed_at.date() != trading_date:
        raise MarketDataError(
            f"Tencent quote is not from requested trading date: {code} "
            f"returned={closed_at.date().isoformat()}"
        )
    if closed_at.time() < _CLOSE_TIME:
        raise MarketDataError(f"Tencent quote was captured before the official close: {code}")
    if closed_at > fetched_at.astimezone(MARKET_TIMEZONE) + _FUTURE_TOLERANCE:
        raise MarketDataError(f"Tencent close timestamp is after fetched_at: {code}")
    return closed_at


def _fetch_tencent_text(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "Accept-Charset": "gb18030",
            "Referer": "https://gu.qq.com/",
            "User-Agent": "Trading-OS daily-close collector/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read()
    except (OSError, TimeoutError, urllib.error.URLError) as exc:
        raise MarketDataError(f"failed to fetch Tencent quotes: {exc}") from exc


def _fetch_cninfo_page(url: str, form: Mapping[str, str]) -> bytes:
    request = urllib.request.Request(
        url,
        data=urlencode(form).encode("utf-8"),
        headers={
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Referer": "https://www.cninfo.com.cn/",
            "User-Agent": "Trading-OS announcement collector/1.0",
            "X-Requested-With": "XMLHttpRequest",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read()
    except (OSError, TimeoutError, urllib.error.URLError) as exc:
        raise MarketDataError(f"failed to fetch CNInfo announcements: {exc}") from exc


def _json_object(value: object, label: str) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if isinstance(value, bytes):
        try:
            text = value.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise MarketDataError(f"{label} is not valid UTF-8") from exc
    elif isinstance(value, str):
        text = value
    else:
        raise MarketDataError(f"{label} must be a JSON object, text, or bytes")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise MarketDataError(f"{label} is not valid JSON: {exc.msg}") from exc
    if not isinstance(payload, Mapping):
        raise MarketDataError(f"{label} must be a JSON object")
    return payload


def _nonnegative_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise MarketDataError(f"{label} must be a non-negative integer")
    return value


def _a_share_symbol(value: object) -> str | None:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{6}", value):
        return None
    try:
        _tencent_code(value)
    except MarketDataError:
        return None
    return f"CN:{value}"


def _clean_title(value: object) -> str:
    if not isinstance(value, str):
        raise MarketDataError("CNInfo announcement title must be a string")
    without_highlight = re.sub(r"</?em>", "", value, flags=re.I)
    if "<" in without_highlight or ">" in without_highlight:
        raise MarketDataError("CNInfo announcement title contains unexpected markup")
    return _name(html.unescape(without_highlight), "CNInfo announcement title")


def _cninfo_announcement(row: object) -> Announcement | None:
    if not isinstance(row, Mapping):
        raise MarketDataError("each CNInfo announcement must be an object")
    symbol = _a_share_symbol(row.get("secCode"))
    if symbol is None:
        return None
    raw_id = row.get("announcementId")
    if not isinstance(raw_id, str) or _CNINFO_ID_RE.fullmatch(raw_id) is None:
        raise MarketDataError(f"CNInfo announcement ID is invalid for {symbol}")
    title = _clean_title(row.get("announcementTitle"))
    timestamp = row.get("announcementTime")
    if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
        raise MarketDataError(f"CNInfo announcement time is invalid: {raw_id}")
    if not math.isfinite(float(timestamp)) or timestamp <= 0 or float(timestamp) % 1:
        raise MarketDataError(f"CNInfo announcement time is invalid: {raw_id}")
    try:
        published = datetime.fromtimestamp(int(timestamp) / 1000, tz=timezone.utc).astimezone(
            MARKET_TIMEZONE
        )
    except (OverflowError, OSError, ValueError) as exc:
        raise MarketDataError(f"CNInfo announcement time is invalid: {raw_id}") from exc

    adjunct = row.get("adjunctUrl")
    if not isinstance(adjunct, str) or not adjunct.strip():
        raise MarketDataError(f"CNInfo announcement URL is missing: {raw_id}")
    url = urljoin(CNINFO_STATIC_BASE, adjunct.strip().lstrip("/"))
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "static.cninfo.com.cn":
        raise MarketDataError(f"CNInfo announcement URL is not official: {raw_id}")
    path_match = _CNINFO_PDF_RE.fullmatch(parsed.path)
    if path_match is None or path_match.group(1) != raw_id:
        raise MarketDataError(f"CNInfo announcement URL does not match its ID: {raw_id}")
    if parsed.username or parsed.password or parsed.fragment:
        raise MarketDataError(f"CNInfo announcement URL is malformed: {raw_id}")
    return Announcement(
        announcement_id=raw_id,
        symbol=symbol,
        title=title,
        published_at=published.isoformat(),
        url=url,
    )


__all__ = [
    "Announcement",
    "CNINFO_ANNOUNCEMENT_ENDPOINT",
    "DailyClose",
    "MARKET_TIMEZONE",
    "MarketDataError",
    "TENCENT_QUOTE_ENDPOINT",
    "discover_cninfo_announcements",
    "fetch_tencent_daily_closes",
]
