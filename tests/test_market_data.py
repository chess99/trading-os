from __future__ import annotations

from datetime import datetime

import pytest

from trading_os.research_assets.market_data import (
    MARKET_TIMEZONE,
    MarketDataError,
    discover_cninfo_announcements,
    fetch_tencent_daily_closes,
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


def _page(rows: list[dict[str, object]], *, total: int, has_more: bool) -> dict:
    pages = (total + 1) // 2 if total > 2 else 0
    return {
        "totalAnnouncement": total,
        "totalRecordNum": total,
        "announcements": rows,
        "hasMore": has_more,
        "totalpages": pages,
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
                "totalpages": 0,
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
        "totalpages": 0,
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
