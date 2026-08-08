from __future__ import annotations

import html
import json
import math
import os
import re
import tempfile
import unicodedata
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urljoin, urlsplit

TENCENT_QUOTE_ENDPOINT = "https://qt.gtimg.cn/q="
CNINFO_ANNOUNCEMENT_ENDPOINT = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_STOCK_DIRECTORY_ENDPOINT = "https://www.cninfo.com.cn/new/data/szse_stock.json"
CNINFO_STATIC_BASE = "https://static.cninfo.com.cn/"
DEFAULT_EVENT_SCAN_STATE_PATH = Path("coverage/cn-a/event_scan_state.json")
DEFAULT_RECENT_ANNOUNCEMENT_LIMIT = 10_000
DEFAULT_CNINFO_COMPANY_CHUNK_SIZE = 50
CNINFO_MAX_QUERY_PAGES = 100

MARKET_TIMEZONE = timezone(timedelta(hours=8), "Asia/Shanghai")
_CLOSE_TIME = time(15, 0)
_FUTURE_TOLERANCE = timedelta(minutes=5)
_MAX_CNINFO_COMPANIES_PER_QUERY = 100
_SYMBOL_RE = re.compile(r"^CN:([0-9]{6})$")
_TENCENT_ROW_RE = re.compile(r'v_((?:sh|sz|bj)[0-9]{6})="([^"\r\n]*)";')
_CNINFO_ID_RE = re.compile(r"^[0-9]+$")
_CNINFO_PDF_RE = re.compile(r"^/finalpage/[0-9]{4}-[0-9]{2}-[0-9]{2}/([0-9]+)\.pdf$", re.I)
_CNINFO_ORG_ID_RE = re.compile(r"^[A-Za-z0-9]+$")

QuoteFetcher = Callable[[str], bytes | str]
AnnouncementFetcher = Callable[[str, Mapping[str, str]], object]
StockDirectoryFetcher = Callable[[str], object]


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


@dataclass(frozen=True)
class EventScanState:
    """Small mutable checkpoint for the full-market announcement scan.

    ``last_successful_at`` is the exclusive end of the last fully judged scan.
    ``recent_announcement_ids`` supports safe overlap between adjacent fetch
    windows without creating a permanent event ledger.
    """

    last_successful_at: str | None = None
    recent_announcement_ids: tuple[str, ...] = ()


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
            if expected_name is not None and not _quote_name_matches(
                expected_name, returned_name
            ):
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
    stock_filter: Mapping[str, str] | None = None,
    max_pages: int | None = None,
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
    if max_pages is not None:
        if isinstance(max_pages, bool) or not isinstance(max_pages, int):
            raise MarketDataError("max_pages must be an integer between 1 and 100")
        if not 1 <= max_pages <= CNINFO_MAX_QUERY_PAGES:
            raise MarketDataError("max_pages must be an integer between 1 and 100")
    stock_query, expected_stock_symbols = _cninfo_stock_query(stock_filter)

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
            "stock": stock_query,
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
            if max_pages is not None and expected_pages > max_pages:
                raise MarketDataError(
                    f"CNInfo filtered query exceeds the {max_pages}-page safety limit: "
                    f"pages={expected_pages}"
                )
        elif total_records != expected_total:
            raise MarketDataError("CNInfo total record count changed during pagination")
        assert expected_pages is not None

        # CNInfo's field is not a conventional page count.  In live responses
        # it is ``floor(totalRecordNum / pageSize)``: 1,329 rows at 30 rows per
        # request advertise ``totalpages=44`` while pageNum 45 contains the
        # final nine rows.  Keep deriving the number of requests ourselves,
        # but validate the provider's actual contract so incomplete payloads
        # still fail closed.
        advertised_pages = expected_total // page_size
        if total_pages_value != advertised_pages:
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
                if expected_stock_symbols is not None:
                    raise MarketDataError(
                        "CNInfo filtered query returned an invalid or unexpected security"
                    )
                continue
            if (
                expected_stock_symbols is not None
                and announcement.symbol not in expected_stock_symbols
            ):
                raise MarketDataError(
                    "CNInfo filtered query returned an unexpected security: "
                    f"{announcement.symbol}"
                )
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


def discover_cninfo_announcements_for_companies(
    companies: Iterable[str] | Mapping[str, object],
    start: str | datetime,
    end: str | datetime,
    *,
    directory_fetcher: StockDirectoryFetcher | None = None,
    fetcher: AnnouncementFetcher | None = None,
    company_chunk_size: int = DEFAULT_CNINFO_COMPANY_CHUNK_SIZE,
    page_size: int = 30,
) -> tuple[Announcement, ...]:
    """Discover announcements for an exact A-share company set without truncation.

    CNInfo caps a single result set at 100 pages. This entry point resolves
    every requested ticker against the provider's current security directory,
    then queries small company chunks one natural market day at a time. Any
    unresolved company, over-limit chunk, unexpected security, or conflicting
    duplicate rejects the complete result.
    """

    window_start = _datetime(start, "start").astimezone(MARKET_TIMEZONE)
    window_end = _datetime(end, "end").astimezone(MARKET_TIMEZONE)
    if window_end <= window_start:
        raise MarketDataError("end must be later than start")
    if isinstance(company_chunk_size, bool) or not isinstance(company_chunk_size, int):
        raise MarketDataError("company_chunk_size must be an integer between 1 and 100")
    if not 1 <= company_chunk_size <= _MAX_CNINFO_COMPANIES_PER_QUERY:
        raise MarketDataError("company_chunk_size must be an integer between 1 and 100")
    if isinstance(page_size, bool) or not isinstance(page_size, int):
        raise MarketDataError("page_size must be an integer between 1 and 30")
    if not 1 <= page_size <= 30:
        raise MarketDataError("page_size must be an integer between 1 and 30")

    requested_symbols = _requested_company_symbols(companies)
    if not requested_symbols:
        return ()

    fetch_directory = directory_fetcher or _fetch_cninfo_stock_directory
    try:
        raw_directory = fetch_directory(CNINFO_STOCK_DIRECTORY_ENDPOINT)
    except MarketDataError:
        raise
    except Exception as exc:
        raise MarketDataError(f"CNInfo stock directory request failed: {exc}") from exc
    directory = _cninfo_stock_directory(raw_directory)
    requested_tickers = {symbol: _symbol(symbol)[1] for symbol in requested_symbols}
    missing = sorted(
        symbol for symbol, ticker in requested_tickers.items() if ticker not in directory
    )
    if missing:
        raise MarketDataError(
            "CNInfo stock directory does not resolve every requested security: "
            + ", ".join(missing)
        )

    ordered_symbols = tuple(sorted(requested_symbols))
    chunks = tuple(
        ordered_symbols[offset : offset + company_chunk_size]
        for offset in range(0, len(ordered_symbols), company_chunk_size)
    )
    selected: dict[str, Announcement] = {}
    requested_set = set(ordered_symbols)
    for day_start, day_end in _market_day_windows(window_start, window_end):
        for chunk in chunks:
            filtered_stocks = {
                requested_tickers[symbol]: directory[requested_tickers[symbol]]
                for symbol in chunk
            }
            announcements = discover_cninfo_announcements(
                day_start,
                day_end,
                fetcher=fetcher,
                page_size=page_size,
                stock_filter=filtered_stocks,
                max_pages=CNINFO_MAX_QUERY_PAGES,
            )
            for announcement in announcements:
                if announcement.symbol not in requested_set:
                    raise MarketDataError(
                        "CNInfo company scan returned an unrequested security: "
                        f"{announcement.symbol}"
                    )
                previous = selected.get(announcement.announcement_id)
                if previous is not None and previous != announcement:
                    raise MarketDataError(
                        "CNInfo company scan returned a conflicting global duplicate: "
                        f"{announcement.announcement_id}"
                    )
                selected[announcement.announcement_id] = announcement

    return tuple(
        sorted(
            selected.values(),
            key=lambda item: (item.published_at, item.symbol, item.announcement_id),
        )
    )


def parse_event_scan_state(value: object) -> EventScanState:
    """Parse the compact checkpoint strictly so corrupt state fails closed."""

    if not isinstance(value, Mapping):
        raise MarketDataError("event scan state must be a JSON object")
    expected_fields = {"last_successful_at", "recent_announcement_ids"}
    actual_fields = set(value)
    if actual_fields != expected_fields:
        missing = sorted(expected_fields - actual_fields)
        unexpected = sorted(str(item) for item in actual_fields - expected_fields)
        raise MarketDataError(
            "event scan state fields do not match the contract: "
            f"missing={missing}, unexpected={unexpected}"
        )

    raw_successful_at = value.get("last_successful_at")
    if raw_successful_at is None:
        successful_at = None
    else:
        successful_at = _datetime(
            raw_successful_at, "event scan last_successful_at"
        ).astimezone(MARKET_TIMEZONE).isoformat()

    raw_ids = value.get("recent_announcement_ids")
    if not isinstance(raw_ids, list):
        raise MarketDataError("event scan recent_announcement_ids must be a JSON list")
    if len(raw_ids) > DEFAULT_RECENT_ANNOUNCEMENT_LIMIT:
        raise MarketDataError(
            "event scan recent_announcement_ids exceeds the compact state limit"
        )
    recent_ids = tuple(
        _announcement_id(item, "event scan recent announcement ID") for item in raw_ids
    )
    if len(set(recent_ids)) != len(recent_ids):
        raise MarketDataError("event scan recent_announcement_ids contains duplicates")
    return EventScanState(
        last_successful_at=successful_at,
        recent_announcement_ids=recent_ids,
    )


def event_scan_state_payload(state: EventScanState) -> dict[str, object]:
    """Return the canonical two-field JSON representation of a checkpoint."""

    normalized = _event_scan_state(state)
    return {
        "last_successful_at": normalized.last_successful_at,
        "recent_announcement_ids": list(normalized.recent_announcement_ids),
    }


def read_event_scan_state(
    path: str | Path = DEFAULT_EVENT_SCAN_STATE_PATH,
) -> EventScanState:
    """Read a checkpoint; a missing file means that no successful scan exists."""

    state_path = Path(path)
    try:
        raw = state_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return EventScanState()
    except OSError as exc:
        raise MarketDataError(f"failed to read event scan state: {exc}") from exc
    return parse_event_scan_state(_json_object(raw, "event scan state"))


def write_event_scan_state(
    state: EventScanState,
    path: str | Path = DEFAULT_EVENT_SCAN_STATE_PATH,
) -> Path:
    """Atomically replace the mutable checkpoint after a successful transition."""

    payload = event_scan_state_payload(state)
    state_path = Path(path)
    temporary_path: Path | None = None
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, raw_temporary_path = tempfile.mkstemp(
            dir=state_path.parent,
            prefix=f".{state_path.name}.",
            suffix=".tmp",
            text=True,
        )
        temporary_path = Path(raw_temporary_path)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, state_path)
        temporary_path = None
    except OSError as exc:
        raise MarketDataError(f"failed to write event scan state atomically: {exc}") from exc
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
    return state_path


def unseen_event_announcements(
    state: EventScanState,
    announcements: Iterable[Announcement],
) -> tuple[Announcement, ...]:
    """Filter overlap-window results using the recent stable provider IDs."""

    normalized_state = _event_scan_state(state)
    discovered = _event_announcements(announcements)
    seen = set(normalized_state.recent_announcement_ids)
    return tuple(item for item in discovered if item.announcement_id not in seen)


def advance_event_scan_state(
    state: EventScanState,
    *,
    scanned_through: str | datetime,
    announcements: Iterable[Announcement],
    successfully_judged_ids: Iterable[str],
    recent_limit: int = DEFAULT_RECENT_ANNOUNCEMENT_LIMIT,
) -> EventScanState:
    """Build the next checkpoint only after every new announcement was judged.

    ``announcements`` may include already-seen rows from an overlapping fetch
    window. Those rows do not need to be judged again. The successful ID set
    must match all and only the unseen rows. Any missing, failed, duplicate, or
    unexpected result rejects the whole transition, leaving callers with the
    prior checkpoint to retry.
    """

    previous = _event_scan_state(state)
    if isinstance(recent_limit, bool) or not isinstance(recent_limit, int):
        raise MarketDataError("recent_limit must be an integer between 1 and 10000")
    if not 1 <= recent_limit <= DEFAULT_RECENT_ANNOUNCEMENT_LIMIT:
        raise MarketDataError("recent_limit must be an integer between 1 and 10000")

    endpoint = _datetime(scanned_through, "scanned_through").astimezone(MARKET_TIMEZONE)
    if previous.last_successful_at is not None:
        previous_endpoint = _datetime(
            previous.last_successful_at, "event scan last_successful_at"
        )
        if endpoint < previous_endpoint:
            raise MarketDataError("event scan checkpoint must not move backwards")

    discovered = _event_announcements(announcements)
    for announcement in discovered:
        published_at = _datetime(
            announcement.published_at,
            f"announcement {announcement.announcement_id} published_at",
        )
        if published_at >= endpoint:
            raise MarketDataError(
                "event scan contains an announcement outside its half-open end: "
                f"{announcement.announcement_id}"
            )

    new_announcements = unseen_event_announcements(previous, discovered)
    expected_ids = tuple(item.announcement_id for item in new_announcements)
    judged_ids = _judged_announcement_ids(successfully_judged_ids)
    missing = sorted(set(expected_ids) - set(judged_ids))
    unexpected = sorted(set(judged_ids) - set(expected_ids))
    if missing or unexpected or len(judged_ids) != len(expected_ids):
        raise MarketDataError(
            "event scan cannot advance before all new announcements are successfully judged: "
            f"missing={missing}, unexpected={unexpected}"
        )

    discovered_ids = tuple(item.announcement_id for item in discovered)
    refreshed_ids = set(discovered_ids)
    combined = [
        item for item in previous.recent_announcement_ids if item not in refreshed_ids
    ]
    combined.extend(discovered_ids)
    return EventScanState(
        last_successful_at=endpoint.isoformat(),
        recent_announcement_ids=tuple(combined[-recent_limit:]),
    )


def _requested_company_symbols(
    companies: Iterable[str] | Mapping[str, object],
) -> tuple[str, ...]:
    if isinstance(companies, Mapping):
        values = tuple(companies)
    elif isinstance(companies, (str, bytes)):
        raise MarketDataError("companies must be an iterable of CN symbols")
    else:
        try:
            values = tuple(companies)
        except TypeError as exc:
            raise MarketDataError("companies must be an iterable of CN symbols") from exc

    symbols: list[str] = []
    observed: set[str] = set()
    for value in values:
        symbol, ticker = _symbol(value)
        _tencent_code(ticker)
        if symbol in observed:
            raise MarketDataError(f"duplicate requested symbol: {symbol}")
        observed.add(symbol)
        symbols.append(symbol)
    return tuple(symbols)


def _cninfo_stock_directory(value: object) -> dict[str, str]:
    payload = _json_object(value, "CNInfo stock directory")
    rows = payload.get("stockList")
    if not isinstance(rows, list):
        raise MarketDataError("CNInfo stock directory stockList must be a list")
    directory: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise MarketDataError("each CNInfo stock directory row must be an object")
        code = row.get("code")
        if not isinstance(code, str) or re.fullmatch(r"[0-9]{6}", code) is None:
            raise MarketDataError("CNInfo stock directory code must contain six digits")
        org_id = row.get("orgId")
        if not isinstance(org_id, str) or _CNINFO_ORG_ID_RE.fullmatch(org_id) is None:
            raise MarketDataError(
                f"CNInfo stock directory orgId is invalid for code {code}"
            )
        if code in directory:
            raise MarketDataError(f"CNInfo stock directory contains duplicate code: {code}")
        directory[code] = org_id
    if not directory:
        raise MarketDataError("CNInfo stock directory is empty")
    return directory


def _cninfo_stock_query(
    stock_filter: Mapping[str, str] | None,
) -> tuple[str, frozenset[str] | None]:
    if stock_filter is None:
        return "", None
    if not isinstance(stock_filter, Mapping) or not stock_filter:
        raise MarketDataError("stock_filter must map at least one A-share code to orgId")
    if len(stock_filter) > _MAX_CNINFO_COMPANIES_PER_QUERY:
        raise MarketDataError("stock_filter cannot contain more than 100 companies")

    entries: list[tuple[str, str, str]] = []
    for raw_code, raw_org_id in stock_filter.items():
        symbol = _a_share_symbol(raw_code)
        if symbol is None:
            raise MarketDataError("stock_filter keys must be six-digit A-share codes")
        if (
            not isinstance(raw_org_id, str)
            or _CNINFO_ORG_ID_RE.fullmatch(raw_org_id) is None
        ):
            raise MarketDataError(f"stock_filter orgId is invalid for code {raw_code}")
        entries.append((raw_code, raw_org_id, symbol))
    entries.sort()
    query = ";".join(f"{code},{org_id}" for code, org_id, _ in entries)
    return query, frozenset(symbol for _, _, symbol in entries)


def _market_day_windows(
    start: datetime,
    end: datetime,
) -> tuple[tuple[datetime, datetime], ...]:
    cursor = start.astimezone(MARKET_TIMEZONE)
    endpoint = end.astimezone(MARKET_TIMEZONE)
    windows: list[tuple[datetime, datetime]] = []
    while cursor < endpoint:
        next_date = cursor.date() + timedelta(days=1)
        next_midnight = datetime.combine(next_date, time.min).replace(
            tzinfo=MARKET_TIMEZONE
        )
        boundary = min(endpoint, next_midnight)
        windows.append((cursor, boundary))
        cursor = boundary
    return tuple(windows)


def _announcement_id(value: object, label: str) -> str:
    if not isinstance(value, str) or _CNINFO_ID_RE.fullmatch(value) is None:
        raise MarketDataError(f"{label} must be a stable numeric CNInfo ID")
    return value


def _event_scan_state(state: EventScanState) -> EventScanState:
    if not isinstance(state, EventScanState):
        raise MarketDataError("event scan state must be an EventScanState")
    raw_ids = state.recent_announcement_ids
    if not isinstance(raw_ids, tuple):
        raise MarketDataError("event scan recent_announcement_ids must be a tuple")
    payload = {
        "last_successful_at": state.last_successful_at,
        "recent_announcement_ids": list(raw_ids),
    }
    return parse_event_scan_state(payload)


def _event_announcements(values: Iterable[Announcement]) -> tuple[Announcement, ...]:
    if isinstance(values, (str, bytes, Mapping)):
        raise MarketDataError("announcements must be an iterable of Announcement values")
    try:
        announcements = tuple(values)
    except TypeError as exc:
        raise MarketDataError(
            "announcements must be an iterable of Announcement values"
        ) from exc
    observed_ids: set[str] = set()
    for item in announcements:
        if not isinstance(item, Announcement):
            raise MarketDataError("announcements must contain only Announcement values")
        announcement_id = _announcement_id(item.announcement_id, "announcement ID")
        if announcement_id in observed_ids:
            raise MarketDataError(
                f"event scan contains duplicate stable announcement ID: {announcement_id}"
            )
        observed_ids.add(announcement_id)
        _symbol(item.symbol)
        _name(item.title, f"announcement {announcement_id} title")
        _datetime(item.published_at, f"announcement {announcement_id} published_at")
        parsed_url = urlsplit(item.url)
        if (
            parsed_url.scheme != "https"
            or parsed_url.hostname != "static.cninfo.com.cn"
            or _CNINFO_PDF_RE.fullmatch(parsed_url.path) is None
        ):
            raise MarketDataError(
                f"announcement {announcement_id} does not use an official CNInfo URL"
            )
        path_match = _CNINFO_PDF_RE.fullmatch(parsed_url.path)
        assert path_match is not None
        if path_match.group(1) != announcement_id:
            raise MarketDataError(
                f"announcement {announcement_id} URL does not match its stable ID"
            )
    return announcements


def _judged_announcement_ids(values: Iterable[str]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes, Mapping)):
        raise MarketDataError("successfully_judged_ids must be an iterable of IDs")
    try:
        ids = tuple(
            _announcement_id(item, "successfully judged announcement ID") for item in values
        )
    except TypeError as exc:
        raise MarketDataError(
            "successfully_judged_ids must be an iterable of IDs"
        ) from exc
    if len(set(ids)) != len(ids):
        raise MarketDataError("successfully_judged_ids contains duplicates")
    return ids


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


def _quote_name_matches(expected: str, returned: str) -> bool:
    expected_key = _name_key(expected)
    returned_key = _name_key(returned)
    if returned_key == expected_key:
        return True
    for marker in ("XD", "XR", "DR"):
        if returned_key.startswith(marker):
            quoted_core = returned_key[len(marker) :]
            return len(quoted_core) >= 2 and expected_key.startswith(quoted_core)
    return False


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


def _fetch_cninfo_stock_directory(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Referer": "https://www.cninfo.com.cn/",
            "User-Agent": "Trading-OS announcement collector/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read()
    except (OSError, TimeoutError, urllib.error.URLError) as exc:
        raise MarketDataError(f"failed to fetch CNInfo stock directory: {exc}") from exc


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
    "CNINFO_MAX_QUERY_PAGES",
    "CNINFO_STOCK_DIRECTORY_ENDPOINT",
    "DEFAULT_CNINFO_COMPANY_CHUNK_SIZE",
    "DEFAULT_EVENT_SCAN_STATE_PATH",
    "DEFAULT_RECENT_ANNOUNCEMENT_LIMIT",
    "DailyClose",
    "EventScanState",
    "MARKET_TIMEZONE",
    "MarketDataError",
    "TENCENT_QUOTE_ENDPOINT",
    "advance_event_scan_state",
    "discover_cninfo_announcements",
    "discover_cninfo_announcements_for_companies",
    "event_scan_state_payload",
    "fetch_tencent_daily_closes",
    "parse_event_scan_state",
    "read_event_scan_state",
    "unseen_event_announcements",
    "write_event_scan_state",
]
