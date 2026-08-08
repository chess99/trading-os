from __future__ import annotations

from datetime import datetime

import pytest

from trading_os.research_assets.market_data import (
    CNINFO_STOCK_DIRECTORY_ENDPOINT,
    MARKET_TIMEZONE,
    Announcement,
    EventScanState,
    MarketDataError,
    advance_event_scan_state,
    discover_cninfo_announcements,
    discover_cninfo_announcements_for_companies,
    event_scan_state_payload,
    fetch_tencent_daily_closes,
    parse_event_scan_state,
    read_event_scan_state,
    unseen_event_announcements,
    write_event_scan_state,
)


def _tencent_row(
    code: str,
    *,
    name: str = "测试公司",
    ticker: str | None = None,
    close: str = "12.34",
    updated_at: str = "20260807150005",
) -> str:
    fields = [""] * 31
    fields[0] = "1"
    fields[1] = name
    fields[2] = ticker or code[2:]
    fields[3] = close
    fields[30] = updated_at
    return f'v_{code}="{"~".join(fields)}";'


def _milliseconds(value: str) -> int:
    parsed = datetime.fromisoformat(value)
    return int(parsed.timestamp() * 1000)


def _announcement(
    announcement_id: str,
    ticker: str,
    published_at: str,
    *,
    title: str = "重大事项公告",
    url: str | None = None,
) -> dict[str, object]:
    published = datetime.fromisoformat(published_at)
    day = published.astimezone(MARKET_TIMEZONE).date().isoformat()
    return {
        "secCode": ticker,
        "secName": "测试公司",
        "announcementId": announcement_id,
        "announcementTitle": title,
        "announcementTime": _milliseconds(published_at),
        "adjunctUrl": url or f"finalpage/{day}/{announcement_id}.PDF",
    }


def _page(
    rows: list[dict[str, object]],
    *,
    total: int,
    has_more: bool,
    page_size: int = 2,
) -> dict:
    pages = total // page_size
    return {
        "totalAnnouncement": total,
        "totalRecordNum": total,
        "announcements": rows,
        "hasMore": has_more,
        "totalpages": pages,
    }


def _stock_directory(*entries: tuple[str, str]) -> dict[str, object]:
    return {
        "stockList": [
            {"code": code, "orgId": org_id, "category": "A股"}
            for code, org_id in entries
        ]
    }


def test_tencent_daily_close_is_exact_batched_unadjusted_and_identity_checked():
    calls: list[str] = []

    def fetch(url: str) -> bytes:
        calls.append(url)
        codes = url.rsplit("=", 1)[1].split(",")
        names = {
            "sz000001": "平安银行",
            "sh601138": "工业富联",
            "bj920001": "北交公司",
        }
        return "\n".join(
            _tencent_row(code, name=names[code], close=str(10 + index))
            for index, code in enumerate(codes)
        ).encode("gb18030")

    closes = fetch_tencent_daily_closes(
        {
            "CN:601138": "工业富联",
            "CN:000001": "平安银行",
            "CN:920001": "北交公司",
        },
        trading_date="2026-08-07",
        fetched_at="2026-08-07T15:10:00+08:00",
        fetcher=fetch,
        chunk_size=2,
    )

    assert [item.symbol for item in closes] == ["CN:000001", "CN:601138", "CN:920001"]
    assert len(calls) == 2
    assert all(item.adjustment == "none" and item.currency == "CNY" for item in closes)
    assert all(item.trading_date == "2026-08-07" for item in closes)
    assert all(item.closed_at == "2026-08-07T15:00:05+08:00" for item in closes)
    assert closes[0].name == "平安银行"
    assert closes[0].source_url in calls


def test_tencent_empty_set_does_not_fetch():
    def unexpected(_: str) -> str:
        raise AssertionError("empty input must not make a network request")

    assert (
        fetch_tencent_daily_closes(
            {},
            trading_date="2026-08-07",
            fetched_at="2026-08-07T15:10:00+08:00",
            fetcher=unexpected,
        )
        == ()
    )


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (_tencent_row("sz000001"), "count does not match"),
        (
            "\n".join(
                [_tencent_row("sz000001"), _tencent_row("sz000001")]
            ),
            "duplicate quote",
        ),
        (
            "\n".join(
                [
                    _tencent_row("sz000001"),
                    _tencent_row("sh601138", ticker="601139"),
                ]
            ),
            "ticker does not match",
        ),
        (
            "\n".join(
                [
                    _tencent_row("sz000001"),
                    _tencent_row("sh601138", name="另一家公司"),
                ]
            ),
            "name does not match",
        ),
        (
            "\n".join(
                [
                    _tencent_row("sz000001"),
                    _tencent_row("sh601138", updated_at="20260806150005"),
                ]
            ),
            "not from requested trading date",
        ),
        (
            "\n".join(
                [
                    _tencent_row("sz000001"),
                    _tencent_row("sh601138", updated_at="20260807145959"),
                ]
            ),
            "before the official close",
        ),
        (
            "\n".join(
                [_tencent_row("sz000001"), _tencent_row("sh601138", close="0")]
            ),
            "positive number",
        ),
    ],
)
def test_tencent_daily_close_fails_closed_on_bad_contract(response: str, message: str):
    with pytest.raises(MarketDataError, match=message):
        fetch_tencent_daily_closes(
            {"CN:000001": "测试公司", "CN:601138": "测试公司"},
            trading_date="2026-08-07",
            fetched_at="2026-08-07T15:10:00+08:00",
            fetcher=lambda _: response,
        )


def test_cninfo_discovers_all_pages_filters_strict_window_and_deduplicates():
    at_start = _announcement(
        "1225000001",
        "000001",
        "2026-08-07T08:00:00+08:00",
        title="<em>2026年</em>半年度报告",
    )
    non_a_share = _announcement(
        "1225000002",
        "159001",
        "2026-08-07T09:00:00+08:00",
    )
    second_company = _announcement(
        "1225000003",
        "601138",
        "2026-08-07T10:00:00+08:00",
    )
    at_end = _announcement(
        "1225000004",
        "920001",
        "2026-08-08T08:00:00+08:00",
    )
    pages = {
        1: _page([at_start, non_a_share], total=6, has_more=True),
        2: _page([second_company, at_start], total=6, has_more=True),
        3: _page([at_end, non_a_share], total=6, has_more=False),
    }
    calls: list[dict[str, str]] = []

    def fetch(_: str, form: dict[str, str]) -> object:
        calls.append(dict(form))
        return pages[int(form["pageNum"])]

    announcements = discover_cninfo_announcements(
        "2026-08-07T08:00:00+08:00",
        "2026-08-08T08:00:00+08:00",
        fetcher=fetch,
        page_size=2,
    )

    assert [item.announcement_id for item in announcements] == [
        "1225000001",
        "1225000003",
    ]
    assert [item.symbol for item in announcements] == ["CN:000001", "CN:601138"]
    assert announcements[0].title == "2026年半年度报告"
    assert announcements[0].url == (
        "https://static.cninfo.com.cn/finalpage/2026-08-07/1225000001.PDF"
    )
    assert [call["pageNum"] for call in calls] == ["1", "2", "3"]
    assert all(call["seDate"] == "2026-08-07~2026-08-08" for call in calls)


def test_cninfo_uses_live_floor_totalpages_contract_with_a_partial_last_page():
    rows = [
        _announcement(
            f"122500000{index}",
            "000001",
            f"2026-08-07T0{index}:00:00+08:00",
        )
        for index in range(1, 6)
    ]
    pages = {
        1: _page(rows[:2], total=5, has_more=True),
        2: _page(rows[2:4], total=5, has_more=True),
        3: _page(rows[4:], total=5, has_more=False),
    }

    announcements = discover_cninfo_announcements(
        "2026-08-07T00:00:00+08:00",
        "2026-08-08T00:00:00+08:00",
        fetcher=lambda _url, form: pages[int(form["pageNum"])],
        page_size=2,
    )

    assert len(announcements) == 5


def test_cninfo_accepts_json_bytes_and_zero_results():
    response = (
        b'{"totalAnnouncement":0,"totalRecordNum":0,"announcements":null,'
        b'"hasMore":false,"totalpages":0}'
    )
    result = discover_cninfo_announcements(
        "2026-08-07T00:00:00+08:00",
        "2026-08-08T00:00:00+08:00",
        fetcher=lambda _url, _form: response,
    )
    assert result == ()


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (
            {
                "totalAnnouncement": 2,
                "totalRecordNum": 2,
                "announcements": [_announcement(
                    "1225000001", "000001", "2026-08-07T08:00:00+08:00"
                )],
                "hasMore": False,
                "totalpages": 1,
            },
            "page size does not match",
        ),
        (
            {
                "totalAnnouncement": 1,
                "totalRecordNum": 2,
                "announcements": [],
                "hasMore": False,
                "totalpages": 0,
            },
            "do not match",
        ),
        (
            {
                "totalAnnouncement": 1,
                "totalRecordNum": 1,
                "announcements": [_announcement(
                    "1225000001",
                    "000001",
                    "2026-08-07T08:00:00+08:00",
                    url="https://example.com/finalpage/2026-08-07/1225000001.PDF",
                )],
                "hasMore": False,
                "totalpages": 0,
            },
            "not official",
        ),
    ],
)
def test_cninfo_fails_closed_on_incomplete_or_unofficial_response(payload, message):
    with pytest.raises(MarketDataError, match=message):
        discover_cninfo_announcements(
            "2026-08-07T00:00:00+08:00",
            "2026-08-08T00:00:00+08:00",
            fetcher=lambda _url, _form: payload,
            page_size=2,
        )


def test_cninfo_rejects_conflicting_duplicates():
    first = _announcement(
        "1225000001", "000001", "2026-08-07T08:00:00+08:00", title="甲公告"
    )
    conflict = {**first, "announcementTitle": "乙公告"}
    payload = {
        "totalAnnouncement": 2,
        "totalRecordNum": 2,
        "announcements": [first, conflict],
        "hasMore": False,
        "totalpages": 1,
    }

    with pytest.raises(MarketDataError, match="conflicting duplicate"):
        discover_cninfo_announcements(
            "2026-08-07T00:00:00+08:00",
            "2026-08-08T00:00:00+08:00",
            fetcher=lambda _url, _form: payload,
            page_size=2,
        )


def test_time_windows_must_be_aware_and_half_open():
    with pytest.raises(MarketDataError, match="UTC offset"):
        discover_cninfo_announcements(
            "2026-08-07T00:00:00",
            "2026-08-08T00:00:00+08:00",
            fetcher=lambda _url, _form: {},
        )
    with pytest.raises(MarketDataError, match="later than start"):
        discover_cninfo_announcements(
            "2026-08-08T00:00:00+08:00",
            "2026-08-08T00:00:00+08:00",
            fetcher=lambda _url, _form: {},
        )


def test_cninfo_company_scan_chunks_exact_universe_across_natural_days():
    directory_calls: list[str] = []
    announcement_calls: list[dict[str, str]] = []
    hours = {"2026-08-07": 13, "2026-08-08": 12, "2026-08-09": 1}

    def fetch_directory(url: str) -> object:
        directory_calls.append(url)
        return _stock_directory(
            ("000001", "org000001"),
            ("002444", "org002444"),
            ("601138", "org601138"),
        )

    def fetch_announcements(_: str, form: dict[str, str]) -> object:
        announcement_calls.append(dict(form))
        day = form["seDate"].split("~", 1)[0]
        rows = []
        for code_and_org in form["stock"].split(";"):
            code = code_and_org.split(",", 1)[0]
            announcement_id = f"9{day.replace('-', '')}{code}"
            rows.append(
                _announcement(
                    announcement_id,
                    code,
                    f"{day}T{hours[day]:02d}:00:00+08:00",
                )
            )
        return _page(rows, total=len(rows), has_more=False, page_size=30)

    announcements = discover_cninfo_announcements_for_companies(
        ["CN:601138", "CN:000001", "CN:002444"],
        "2026-08-07T12:00:00+08:00",
        "2026-08-09T06:00:00+08:00",
        directory_fetcher=fetch_directory,
        fetcher=fetch_announcements,
        company_chunk_size=2,
    )

    assert directory_calls == [CNINFO_STOCK_DIRECTORY_ENDPOINT]
    assert len(announcement_calls) == 6
    assert {call["seDate"] for call in announcement_calls} == {
        "2026-08-07~2026-08-07",
        "2026-08-08~2026-08-08",
        "2026-08-09~2026-08-09",
    }
    assert {call["stock"] for call in announcement_calls} == {
        "000001,org000001;002444,org002444",
        "601138,org601138",
    }
    assert len(announcements) == 9
    assert {item.symbol for item in announcements} == {
        "CN:000001",
        "CN:002444",
        "CN:601138",
    }


def test_cninfo_company_scan_fails_before_query_when_directory_misses_security():
    calls: list[dict[str, str]] = []

    with pytest.raises(MarketDataError, match="does not resolve"):
        discover_cninfo_announcements_for_companies(
            ["CN:000001", "CN:601138"],
            "2026-08-07T00:00:00+08:00",
            "2026-08-08T00:00:00+08:00",
            directory_fetcher=lambda _url: _stock_directory(
                ("000001", "org000001")
            ),
            fetcher=lambda _url, form: calls.append(dict(form)),
        )

    assert calls == []


def test_cninfo_company_scan_fails_closed_above_provider_page_limit():
    calls: list[dict[str, str]] = []
    row = _announcement(
        "1225000001", "000001", "2026-08-07T08:00:00+08:00"
    )

    def fetch(_: str, form: dict[str, str]) -> object:
        calls.append(dict(form))
        return {
            "totalAnnouncement": 101,
            "totalRecordNum": 101,
            "announcements": [row],
            "hasMore": True,
            "totalpages": 101,
        }

    with pytest.raises(MarketDataError, match="100-page safety limit"):
        discover_cninfo_announcements_for_companies(
            ["CN:000001"],
            "2026-08-07T00:00:00+08:00",
            "2026-08-08T00:00:00+08:00",
            directory_fetcher=lambda _url: _stock_directory(
                ("000001", "org000001")
            ),
            fetcher=fetch,
            page_size=1,
        )

    assert len(calls) == 1


def test_cninfo_company_scan_rejects_security_outside_requested_chunk():
    unexpected = _announcement(
        "1225000001", "601138", "2026-08-07T08:00:00+08:00"
    )

    with pytest.raises(MarketDataError, match="unexpected security"):
        discover_cninfo_announcements_for_companies(
            ["CN:000001"],
            "2026-08-07T00:00:00+08:00",
            "2026-08-08T00:00:00+08:00",
            directory_fetcher=lambda _url: _stock_directory(
                ("000001", "org000001")
            ),
            fetcher=lambda _url, _form: _page(
                [unexpected], total=1, has_more=False, page_size=30
            ),
        )


def test_cninfo_company_scan_rejects_conflicting_ids_across_chunks():
    def fetch(_: str, form: dict[str, str]) -> object:
        code = form["stock"].split(",", 1)[0]
        row = _announcement(
            "1225000001", code, "2026-08-07T08:00:00+08:00"
        )
        return _page([row], total=1, has_more=False, page_size=30)

    with pytest.raises(MarketDataError, match="conflicting global duplicate"):
        discover_cninfo_announcements_for_companies(
            ["CN:000001", "CN:601138"],
            "2026-08-07T00:00:00+08:00",
            "2026-08-08T00:00:00+08:00",
            directory_fetcher=lambda _url: _stock_directory(
                ("000001", "org000001"),
                ("601138", "org601138"),
            ),
            fetcher=fetch,
            company_chunk_size=1,
        )


def _event(
    announcement_id: str,
    published_at: str,
    *,
    symbol: str = "CN:000001",
) -> Announcement:
    day = datetime.fromisoformat(published_at).astimezone(MARKET_TIMEZONE).date()
    return Announcement(
        announcement_id=announcement_id,
        symbol=symbol,
        title=f"Announcement {announcement_id}",
        published_at=published_at,
        url=(
            "https://static.cninfo.com.cn/finalpage/"
            f"{day.isoformat()}/{announcement_id}.PDF"
        ),
    )


def test_event_scan_state_round_trips_as_a_compact_atomic_checkpoint(tmp_path):
    path = tmp_path / "coverage" / "cn-a" / "event_scan_state.json"
    assert read_event_scan_state(path) == EventScanState()

    state = EventScanState(
        last_successful_at="2026-08-08T00:00:00+08:00",
        recent_announcement_ids=("1225000001", "1225000002"),
    )
    assert write_event_scan_state(state, path) == path
    assert read_event_scan_state(path) == state
    assert event_scan_state_payload(state) == {
        "last_successful_at": "2026-08-08T00:00:00+08:00",
        "recent_announcement_ids": ["1225000001", "1225000002"],
    }
    assert list(path.parent.glob(f".{path.name}.*.tmp")) == []


def test_event_scan_overlap_filters_seen_ids_and_advances_after_exact_successes():
    previous = EventScanState(
        last_successful_at="2026-08-08T00:00:00+08:00",
        recent_announcement_ids=("1225000001",),
    )
    overlap = _event("1225000001", "2026-08-07T23:00:00+08:00")
    first_new = _event("1225000002", "2026-08-08T08:00:00+08:00")
    second_new = _event(
        "1225000003", "2026-08-08T09:00:00+08:00", symbol="CN:601138"
    )
    discovered = (overlap, first_new, second_new)

    assert unseen_event_announcements(previous, discovered) == (first_new, second_new)
    advanced = advance_event_scan_state(
        previous,
        scanned_through="2026-08-09T00:00:00+08:00",
        announcements=discovered,
        successfully_judged_ids=("1225000002", "1225000003"),
    )

    assert previous.recent_announcement_ids == ("1225000001",)
    assert advanced == EventScanState(
        last_successful_at="2026-08-09T00:00:00+08:00",
        recent_announcement_ids=("1225000001", "1225000002", "1225000003"),
    )


@pytest.mark.parametrize(
    ("successful_ids", "message"),
    [
        (("1225000002",), "missing"),
        (("1225000002", "1225000003", "1225999999"), "unexpected"),
        (("1225000002", "1225000002"), "duplicates"),
    ],
)
def test_event_scan_does_not_advance_on_incomplete_or_ambiguous_judgment(
    tmp_path, successful_ids, message
):
    path = tmp_path / "event_scan_state.json"
    previous = EventScanState(
        last_successful_at="2026-08-08T00:00:00+08:00",
        recent_announcement_ids=("1225000001",),
    )
    write_event_scan_state(previous, path)
    before = path.read_bytes()
    announcements = (
        _event("1225000002", "2026-08-08T08:00:00+08:00"),
        _event("1225000003", "2026-08-08T09:00:00+08:00"),
    )

    with pytest.raises(MarketDataError, match=message):
        next_state = advance_event_scan_state(
            previous,
            scanned_through="2026-08-09T00:00:00+08:00",
            announcements=announcements,
            successfully_judged_ids=successful_ids,
        )
        write_event_scan_state(next_state, path)

    assert path.read_bytes() == before
    assert read_event_scan_state(path) == previous


def test_event_scan_checkpoint_is_bounded_monotonic_and_half_open():
    previous = EventScanState(
        last_successful_at="2026-08-08T00:00:00+08:00",
        recent_announcement_ids=("1225000001", "1225000002"),
    )
    new = _event("1225000003", "2026-08-08T08:00:00+08:00")
    advanced = advance_event_scan_state(
        previous,
        scanned_through="2026-08-09T00:00:00+08:00",
        announcements=(new,),
        successfully_judged_ids=("1225000003",),
        recent_limit=2,
    )
    assert advanced.recent_announcement_ids == ("1225000002", "1225000003")

    with pytest.raises(MarketDataError, match="move backwards"):
        advance_event_scan_state(
            previous,
            scanned_through="2026-08-07T23:59:59+08:00",
            announcements=(),
            successfully_judged_ids=(),
        )
    with pytest.raises(MarketDataError, match="half-open end"):
        advance_event_scan_state(
            previous,
            scanned_through="2026-08-08T08:00:00+08:00",
            announcements=(new,),
            successfully_judged_ids=("1225000003",),
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"last_successful_at": None, "recent_announcement_ids": [], "extra": True},
        {
            "last_successful_at": "2026-08-08T00:00:00",
            "recent_announcement_ids": [],
        },
        {
            "last_successful_at": "2026-08-08T00:00:00+08:00",
            "recent_announcement_ids": ["1225000001", "1225000001"],
        },
    ],
)
def test_event_scan_state_corruption_fails_closed(payload):
    with pytest.raises(MarketDataError):
        parse_event_scan_state(payload)
