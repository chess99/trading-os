from __future__ import annotations

import datetime as dt
import json
import urllib.parse
from pathlib import Path
from typing import Any

import pytest


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _write_frozen_quote_universe(
    root: Path,
    run_id: str,
    symbols: list[str],
    *,
    price: float = 20.0,
    market_cap_cny: int = 2_000,
    float_market_cap_cny: int = 1_000,
    pe_ttm: float = 30.0,
    pb: float = 4.0,
) -> None:
    _write_jsonl(
        root / "snapshots" / run_id / "companies.jsonl",
        [
            {
                "symbol": symbol,
                "ticker": symbol.split(":", 1)[1],
                "name": f"Company {symbol}",
                "exchange": (
                    "SSE"
                    if symbol[3:].startswith("6")
                    else "BSE"
                    if symbol[3:].startswith(("4", "8", "9"))
                    else "SZSE"
                ),
                "price": price,
                "market_cap_cny": market_cap_cny,
                "float_market_cap_cny": float_market_cap_cny,
                "pe_ttm": pe_ttm,
                "pb": pb,
            }
            for symbol in symbols
        ],
    )


def _eastmoney_row(
    ticker: str,
    *,
    updated_at: dt.datetime,
    previous_close: Any = 10.0,
    current_price: Any = 12.0,
    market_cap_cny: Any = 1_200,
    float_market_cap_cny: Any = 600,
    pe_ttm: Any = 24.0,
    pb: Any = 3.0,
) -> dict[str, Any]:
    return {
        "f2": current_price,
        "f9": pe_ttm,
        "f12": ticker,
        "f14": f"Company CN:{ticker}",
        "f18": previous_close,
        "f20": market_cap_cny,
        "f21": float_market_cap_cny,
        "f23": pb,
        "f124": int(updated_at.timestamp()),
    }


def _tencent_line(
    code: str,
    *,
    updated_at: str = "20260731075500",
    previous_close: str = "10",
    current_price: str = "12",
    market_cap_yi: str = "1200",
    float_market_cap_yi: str = "600",
    pe_ttm: str = "24",
    pb: str = "3",
    ticker: str | None = None,
) -> str:
    fields = [""] * 54
    fields[0] = "1"
    fields[1] = "测试公司"
    fields[2] = ticker or code[2:]
    fields[3] = current_price
    fields[4] = previous_close
    fields[30] = updated_at
    fields[44] = float_market_cap_yi
    fields[45] = market_cap_yi
    fields[46] = pb
    fields[53] = pe_ttm
    return f'v_{code}="{"~".join(fields)}";'


def test_prepare_manager_screen_snapshot_compacts_facts_and_is_idempotent(
    tmp_path: Path,
):
    from trading_os.research_assets.manager_screen_snapshot import (
        prepare_manager_screen_snapshot,
    )

    cutoff = dt.datetime.fromisoformat("2026-07-31T08:00:00+08:00")
    root = tmp_path / "coverage" / "cn-a"
    _write_jsonl(
        root / "companies.jsonl",
        [
            {
                "symbol": "CN:000001",
                "ticker": "000001",
                "name": "甲公司",
                "exchange": "SZSE",
                "security_type": "common_stock",
                "listing_status": "listed",
                "as_of": "2026-07-30",
                "price": 10.0,
                "source": "fixture quote",
            }
        ],
    )
    calls = []

    def fetch_records(**kwargs):
        calls.append((kwargs["report_name"], kwargs["report_date"]))
        if kwargs["report_name"] == "RPT_F10_BASIC_ORGINFO":
            return [
                {
                    "SECUCODE": "000001.SZ",
                    "SECURITY_CODE": "000001",
                    "ORG_TYPE": "通用",
                    "INDUSTRYCSRC1": "制造业",
                    "BOARD_NAME_LEVEL": "机械-专用设备",
                    "MAIN_BUSINESS": "  制造   核心设备并提供服务。 ",
                    "ACTUAL_HOLDER": "甲集团",
                    "ACCOUNTFIRM_NAME": "甲会计师事务所",
                    "LISTING_DATE": "2000-01-01 00:00:00",
                }
            ]
        report_date = kwargs["report_date"]
        base = {
            "SECUCODE": "000001.SZ",
            "SECURITY_CODE": "000001",
            "ORG_TYPE": "通用",
            "REPORT_DATE": f"{report_date} 00:00:00",
            "REPORT_TYPE": "年报" if report_date.endswith("-12-31") else "中报",
            "NOTICE_DATE": "2026-03-20 00:00:00",
            "UPDATE_DATE": "2026-03-20 00:00:00",
            "OPINION_TYPE": "标准无保留意见",
        }
        if kwargs["report_name"] == "RPT_F10_FINANCE_GINCOME":
            return [
                {
                    **base,
                    "TOTAL_OPERATE_INCOME": 100,
                    "OPERATE_PROFIT": 20,
                    "PARENT_NETPROFIT": 15,
                    "DEDUCT_PARENT_NETPROFIT": 12,
                }
            ]
        if kwargs["report_name"] == "RPT_F10_FINANCE_GBALANCE":
            return [
                {
                    **base,
                    "MONETARYFUNDS": 30,
                    "SHORT_LOAN": 5,
                    "LONG_LOAN": 7,
                    "TOTAL_ASSETS": 200,
                    "TOTAL_LIABILITIES": 80,
                    "TOTAL_PARENT_EQUITY": 110,
                    "GOODWILL": 3,
                    "ACCOUNTS_RECE": 10,
                    "INVENTORY": 8,
                }
            ]
        return [
            {
                **base,
                "NETCASH_OPERATE": 18,
                "CONSTRUCT_LONG_ASSET": 4,
                "ASSIGN_DIVIDEND_PORFIT": 6,
            }
        ]

    result = prepare_manager_screen_snapshot(
        root=root,
        run_id="2026-07-31-manager-001",
        information_cutoff=cutoff,
        fetched_at=cutoff + dt.timedelta(minutes=1),
        fetch_records=fetch_records,
    )
    assert result["record_count"] == 1
    assert len(calls) == 16
    output = tmp_path / result["path"]
    row = json.loads(output.read_text(encoding="utf-8").splitlines()[0])
    facts = row["manager_screen_facts"]
    assert facts["quote_freshness"]["quote_as_of"] == "2026-07-30T15:00:00+08:00"
    assert facts["business"]["main_business"] == "制造 核心设备并提供服务。"
    assert len(facts["annuals"]) == 3
    assert facts["latest_interim"]["report_date"] == "2026-06-30"
    assert facts["annuals"][-1]["operating_cash_flow_cny"] == 18
    assert facts["annuals"][-1]["balance_sheet"]["interest_bearing_debt_cny"] == 12
    assert facts["data_gaps"] == []

    replay = prepare_manager_screen_snapshot(
        root=root,
        run_id="2026-07-31-manager-001",
        information_cutoff=cutoff,
        fetched_at=cutoff + dt.timedelta(hours=1),
        fetch_records=lambda **_: (_ for _ in ()).throw(AssertionError("must not fetch")),
    )
    assert replay["sha256"] == result["sha256"]


def test_unknown_exchange_is_preserved_as_an_identity_data_gap(tmp_path: Path):
    from trading_os.research_assets.manager_screen_snapshot import (
        prepare_manager_screen_snapshot,
    )

    cutoff = dt.datetime.fromisoformat("2026-07-31T08:00:00+08:00")
    root = tmp_path / "coverage" / "cn-a"
    _write_jsonl(
        root / "companies.jsonl",
        [
            {
                "symbol": "CN:302132",
                "ticker": "302132",
                "name": "待核验证券",
                "exchange": "UNKNOWN",
                "security_type": "unknown",
                "listing_status": "unknown",
                "as_of": "2026-07-30",
                "price": 1.0,
                "source": "fixture quote",
            }
        ],
    )

    result = prepare_manager_screen_snapshot(
        root=root,
        run_id="2026-07-31-manager-unknown",
        information_cutoff=cutoff,
        fetched_at=cutoff + dt.timedelta(minutes=1),
        fetch_records=lambda **_: [],
    )
    row = json.loads((tmp_path / result["path"]).read_text(encoding="utf-8").splitlines()[0])
    assert "unsupported_exchange_identity" in row["manager_screen_facts"]["data_gaps"]


def test_snapshot_rejects_stale_quotes_and_accepts_explicit_full_refresh(
    tmp_path: Path,
):
    from trading_os.research_assets.manager_screen_snapshot import (
        ManagerScreenSnapshotError,
        prepare_manager_screen_snapshot,
    )

    cutoff = dt.datetime.fromisoformat("2026-07-31T08:00:00+08:00")
    root = tmp_path / "coverage" / "cn-a"
    _write_jsonl(
        root / "companies.jsonl",
        [
            {
                "symbol": "CN:000001",
                "ticker": "000001",
                "name": "甲公司",
                "exchange": "SZSE",
                "security_type": "common_stock",
                "listing_status": "listed",
                "as_of": "2026-07-01",
                "price": 9.0,
                "source": "stale fixture quote",
            }
        ],
    )

    with pytest.raises(ManagerScreenSnapshotError, match="stale quote"):
        prepare_manager_screen_snapshot(
            root=root,
            run_id="2026-07-31-stale",
            information_cutoff=cutoff,
            fetched_at=cutoff + dt.timedelta(minutes=1),
            fetch_records=lambda **_: [],
        )

    result = prepare_manager_screen_snapshot(
        root=root,
        run_id="2026-07-31-refreshed",
        information_cutoff=cutoff,
        fetched_at=cutoff + dt.timedelta(minutes=1),
        fetch_records=lambda **_: [],
        quote_snapshot=[
            {
                "symbol": "CN:000001",
                "price": 10.5,
                "as_of": "2026-07-31T07:59:00+08:00",
                "source": "explicit quote fixture",
            }
        ],
        quote_max_age=dt.timedelta(hours=1),
    )
    row = json.loads((tmp_path / result["path"]).read_text(encoding="utf-8").splitlines()[0])
    assert row["price"] == 10.5
    freshness = row["manager_screen_facts"]["quote_freshness"]
    assert freshness["status"] == "fresh"
    assert freshness["max_age_seconds"] == 3600
    assert freshness["source"] == "explicit quote fixture"


def test_manager_screen_quote_amendment_cli_seals_overlay(
    tmp_path: Path,
    capsys,
):
    from trading_os.cli import main

    root = tmp_path / "coverage" / "cn-a"
    run_id = "2026-07-31-existing-run"
    _write_jsonl(
        root / "snapshots" / run_id / "companies.jsonl",
        [
            {
                "symbol": "CN:000001",
                "ticker": "000001",
                "name": "甲公司",
                "as_of": "2026-07-22",
                "price": 9.0,
                "source": "old quote",
            }
        ],
    )
    quotes_path = tmp_path / "quotes.json"
    quotes_path.write_text(
        json.dumps(
            [
                {
                    "symbol": "CN:000001",
                    "price": 10.5,
                    "as_of": "2026-07-31T15:00:00+08:00",
                    "source": "closing quote fixture",
                    "fetched_at": "2026-07-31T15:55:00+08:00",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    assert (
        main(
            [
                "coverage",
                "manager-screen-quote-amend",
                run_id,
                "close-2026-07-31",
                "--root",
                str(root),
                "--quotes",
                str(quotes_path),
                "--quote-max-age-hours",
                "2",
                "--at",
                "2026-07-31T16:00:00+08:00",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["quote_count"] == 1
    assert payload["quote_freshness_policy"]["max_age_seconds"] == 7200
    assert (tmp_path / payload["path"]).is_file()


def test_manager_screen_quote_amendment_cli_fetches_tencent_exact_universe(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    from trading_os import cli
    from trading_os.research_assets import manager_screen_snapshot
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl

    root = tmp_path / "coverage" / "cn-a"
    run_id = "2026-07-31-tencent-cli"
    _write_frozen_quote_universe(
        root,
        run_id,
        ["CN:302132", "CN:600000"],
    )
    snapshot_path = root / "snapshots" / run_id / "companies.jsonl"
    rows = read_jsonl(snapshot_path)
    next(item for item in rows if item["symbol"] == "CN:302132")[
        "exchange"
    ] = "UNKNOWN"
    write_jsonl(snapshot_path, rows)
    requested_urls: list[str] = []

    def fetch_text(url: str) -> bytes:
        requested_urls.append(url)
        codes = url.rsplit("=", 1)[1].split(",")
        return "\n".join(
            _tencent_line(code) for code in codes
        ).encode("gb18030")

    monkeypatch.setattr(
        manager_screen_snapshot,
        "_fetch_tencent_quote_text",
        fetch_text,
    )
    assert (
        cli.main(
            [
                "coverage",
                "manager-screen-quote-amend",
                run_id,
                "tencent-close-2026-07-30",
                "--root",
                str(root),
                "--tencent-previous-close-date",
                "2026-07-30",
                "--tencent-quote-endpoint",
                "https://fixture.invalid/q=",
                "--quote-max-age-hours",
                "24",
                "--at",
                "2026-07-31T08:00:00+08:00",
            ]
        )
        == 0
    )

    summary = json.loads(capsys.readouterr().out)
    assert requested_urls == [
        "https://fixture.invalid/q=sh600000,sz302132"
    ]
    assert summary["quote_count"] == 2
    amendment = json.loads(
        (tmp_path / summary["path"]).read_text(encoding="utf-8")
    )
    assert [item["symbol"] for item in amendment["quotes"]] == [
        "CN:302132",
        "CN:600000",
    ]
    assert {
        item["as_of"] for item in amendment["quotes"]
    } == {"2026-07-30T15:00:00+08:00"}
    assert all(
        "Tencent qt.gtimg.cn" in item["source"]
        and "explicit close date 2026-07-30" in item["source"]
        and item["quote_freshness"]["status"] == "fresh"
        for item in amendment["quotes"]
    )


def test_tencent_quote_amendment_cli_fails_closed_on_incomplete_universe(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    from trading_os import cli
    from trading_os.research_assets import manager_screen_snapshot

    root = tmp_path / "coverage" / "cn-a"
    run_id = "2026-07-31-tencent-cli-incomplete"
    _write_frozen_quote_universe(
        root,
        run_id,
        ["CN:000001", "CN:000002"],
    )
    monkeypatch.setattr(
        manager_screen_snapshot,
        "_fetch_tencent_quote_text",
        lambda _: _tencent_line("sz000001"),
    )

    code = cli.main(
        [
            "coverage",
            "manager-screen-quote-amend",
            run_id,
            "incomplete",
            "--root",
            str(root),
            "--tencent-previous-close-date",
            "2026-07-30",
            "--at",
            "2026-07-31T08:00:00+08:00",
        ]
    )

    assert code == 1
    error = json.loads(capsys.readouterr().err)
    assert error["error_code"] == "manager_screen_snapshot_error"
    assert "count does not match" in error["error"]
    assert not (
        root
        / "snapshots"
        / run_id
        / "quote-amendments"
        / "incomplete.json"
    ).exists()


def test_tencent_quote_amendment_cli_does_not_relax_freshness(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    from trading_os import cli
    from trading_os.research_assets import manager_screen_snapshot

    root = tmp_path / "coverage" / "cn-a"
    run_id = "2026-07-31-tencent-cli-stale"
    _write_frozen_quote_universe(root, run_id, ["CN:000001"])
    monkeypatch.setattr(
        manager_screen_snapshot,
        "_fetch_tencent_quote_text",
        lambda _: _tencent_line("sz000001"),
    )

    code = cli.main(
        [
            "coverage",
            "manager-screen-quote-amend",
            run_id,
            "stale",
            "--root",
            str(root),
            "--tencent-previous-close-date",
            "2026-07-30",
            "--quote-max-age-hours",
            "1",
            "--at",
            "2026-07-31T08:00:00+08:00",
        ]
    )

    assert code == 1
    error = json.loads(capsys.readouterr().err)
    assert error["error_code"] == "manager_screen_snapshot_error"
    assert "stale quote" in error["error"]
    assert not (
        root
        / "snapshots"
        / run_id
        / "quote-amendments"
        / "stale.json"
    ).exists()


def test_quote_amendment_sources_are_mutually_exclusive() -> None:
    from trading_os.cli import build_parser

    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "coverage",
                "manager-screen-quote-amend",
                "run-id",
                "amendment-id",
                "--quotes",
                "quotes.json",
                "--tencent-previous-close-date",
                "2026-07-30",
            ]
        )


def test_fetch_previous_close_quotes_chunks_and_recomputes_valuation(
    tmp_path: Path,
):
    from trading_os.research_assets.manager_screen_snapshot import (
        fetch_eastmoney_previous_close_quotes,
    )

    root = tmp_path / "coverage" / "cn-a"
    run_id = "2026-07-31-previous-close"
    symbols = [
        "CN:000001",
        "CN:000002",
        "CN:300001",
        "CN:600000",
        "CN:600001",
    ]
    _write_frozen_quote_universe(root, run_id, symbols)
    fetched_at = dt.datetime.fromisoformat("2026-07-31T08:00:00+08:00")
    updated_at = dt.datetime.fromisoformat("2026-07-31T07:55:00+08:00")
    requested_chunks: list[list[str]] = []

    def fetch_payload(url: str) -> dict[str, Any]:
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        secids = query["secids"][0].split(",")
        requested_chunks.append(secids)
        return {
            "rc": 0,
            "data": {
                "total": len(secids),
                "diff": [
                    _eastmoney_row(
                        secid.split(".", 1)[1],
                        updated_at=updated_at,
                    )
                    for secid in secids
                ],
            },
        }

    quotes = fetch_eastmoney_previous_close_quotes(
        root=root,
        run_id=run_id,
        quote_date=dt.date(2026, 7, 30),
        fetched_at=fetched_at,
        chunk_size=2,
        fetch_payload=fetch_payload,
    )

    assert requested_chunks == [
        ["0.000001", "0.000002"],
        ["0.300001", "1.600000"],
        ["1.600001"],
    ]
    assert [quote["symbol"] for quote in quotes] == sorted(symbols)
    for quote in quotes:
        assert quote["price"] == 10.0
        assert quote["as_of"] == "2026-07-30"
        assert quote["market_cap_cny"] == 1_000
        assert quote["float_market_cap_cny"] == 500
        assert quote["pe_ttm"] == 20.0
        assert quote["pb"] == 2.5


def test_fetch_previous_close_quotes_recomputes_from_frozen_fallback(
    tmp_path: Path,
):
    from trading_os.research_assets.manager_screen_snapshot import (
        fetch_eastmoney_previous_close_quotes,
    )

    root = tmp_path / "coverage" / "cn-a"
    run_id = "2026-07-31-previous-close-fallback"
    _write_frozen_quote_universe(root, run_id, ["CN:000001"])
    fetched_at = dt.datetime.fromisoformat("2026-07-31T08:00:00+08:00")
    updated_at = dt.datetime.fromisoformat("2026-07-30T15:00:00+08:00")

    quotes = fetch_eastmoney_previous_close_quotes(
        root=root,
        run_id=run_id,
        quote_date=dt.date(2026, 7, 30),
        fetched_at=fetched_at,
        fetch_payload=lambda _: {
            "rc": 0,
            "data": {
                "total": 1,
                "diff": [
                    _eastmoney_row(
                        "000001",
                        updated_at=updated_at,
                        current_price=None,
                        market_cap_cny=None,
                        float_market_cap_cny=None,
                        pe_ttm=None,
                        pb=None,
                    )
                ],
            },
        },
    )

    assert quotes[0]["market_cap_cny"] == 1_000
    assert quotes[0]["float_market_cap_cny"] == 500
    assert quotes[0]["pe_ttm"] == 15.0
    assert quotes[0]["pb"] == 2.0


def test_fetch_previous_close_quotes_rejects_in_universe_symbol_from_wrong_chunk(
    tmp_path: Path,
):
    from trading_os.research_assets.manager_screen_snapshot import (
        ManagerScreenSnapshotError,
        fetch_eastmoney_previous_close_quotes,
    )

    root = tmp_path / "coverage" / "cn-a"
    run_id = "2026-07-31-wrong-chunk"
    _write_frozen_quote_universe(
        root,
        run_id,
        ["CN:000001", "CN:000002", "CN:300001"],
    )
    fetched_at = dt.datetime.fromisoformat("2026-07-31T08:00:00+08:00")
    updated_at = dt.datetime.fromisoformat("2026-07-30T15:00:00+08:00")

    with pytest.raises(ManagerScreenSnapshotError, match="requested quote chunk"):
        fetch_eastmoney_previous_close_quotes(
            root=root,
            run_id=run_id,
            quote_date=dt.date(2026, 7, 30),
            fetched_at=fetched_at,
            chunk_size=2,
            fetch_payload=lambda _: {
                "rc": 0,
                "data": {
                    "total": 2,
                    "diff": [
                        _eastmoney_row("000001", updated_at=updated_at),
                        _eastmoney_row("300001", updated_at=updated_at),
                    ],
                },
            },
        )


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("non_object", "response must be an object"),
        ("failed_rc", "returned failure"),
        ("invalid_total", "data.total must be an integer"),
        ("count_mismatch", "count does not match"),
        ("missing", "count does not match"),
        ("duplicate", "duplicate quote"),
        ("outside", "outside the frozen universe"),
        ("malformed_row", "row must be an object"),
        ("invalid_close", "must be a positive number"),
    ],
)
def test_fetch_previous_close_quotes_fails_closed_on_response_contract(
    tmp_path: Path,
    case: str,
    message: str,
):
    from trading_os.research_assets.manager_screen_snapshot import (
        ManagerScreenSnapshotError,
        fetch_eastmoney_previous_close_quotes,
    )

    root = tmp_path / "coverage" / "cn-a"
    run_id = f"2026-07-31-contract-{case}"
    _write_frozen_quote_universe(root, run_id, ["CN:000001", "CN:000002"])
    fetched_at = dt.datetime.fromisoformat("2026-07-31T08:00:00+08:00")
    updated_at = dt.datetime.fromisoformat("2026-07-30T15:00:00+08:00")
    rows: list[Any] = [
        _eastmoney_row("000001", updated_at=updated_at),
        _eastmoney_row("000002", updated_at=updated_at),
    ]
    payload: Any = {"rc": 0, "data": {"total": 2, "diff": rows}}
    if case == "non_object":
        payload = []
    elif case == "failed_rc":
        payload["rc"] = 1
    elif case == "invalid_total":
        payload["data"]["total"] = "2"
    elif case == "count_mismatch":
        payload["data"]["total"] = 1
    elif case == "missing":
        payload["data"]["diff"] = rows[:1]
    elif case == "duplicate":
        payload["data"]["diff"] = [rows[0], rows[0]]
    elif case == "outside":
        payload["data"]["diff"] = [
            rows[0],
            _eastmoney_row("999999", updated_at=updated_at),
        ]
    elif case == "malformed_row":
        payload["data"]["diff"] = [rows[0], "not an object"]
    elif case == "invalid_close":
        rows[0]["f18"] = 0

    with pytest.raises(ManagerScreenSnapshotError, match=message):
        fetch_eastmoney_previous_close_quotes(
            root=root,
            run_id=run_id,
            quote_date=dt.date(2026, 7, 30),
            fetched_at=fetched_at,
            chunk_size=2,
            fetch_payload=lambda _: payload,
        )


@pytest.mark.parametrize(
    ("updated_at", "message"),
    [
        (None, "timestamp is invalid"),
        ("2026-07-29T15:00:00+08:00", "predates"),
        ("2026-07-31T08:06:00+08:00", "after fetched_at"),
    ],
)
def test_fetch_previous_close_quotes_validates_response_update_time(
    tmp_path: Path,
    updated_at: str | None,
    message: str,
):
    from trading_os.research_assets.manager_screen_snapshot import (
        ManagerScreenSnapshotError,
        fetch_eastmoney_previous_close_quotes,
    )

    root = tmp_path / "coverage" / "cn-a"
    run_id = f"2026-07-31-time-{message.replace(' ', '-')}"
    _write_frozen_quote_universe(root, run_id, ["CN:000001"])
    fetched_at = dt.datetime.fromisoformat("2026-07-31T08:00:00+08:00")
    timestamp = (
        None if updated_at is None else int(dt.datetime.fromisoformat(updated_at).timestamp())
    )

    with pytest.raises(ManagerScreenSnapshotError, match=message):
        fetch_eastmoney_previous_close_quotes(
            root=root,
            run_id=run_id,
            quote_date=dt.date(2026, 7, 30),
            fetched_at=fetched_at,
            fetch_payload=lambda _: {
                "rc": 0,
                "data": {
                    "total": 1,
                    "diff": [
                        {
                            **_eastmoney_row(
                                "000001",
                                updated_at=fetched_at,
                            ),
                            "f124": timestamp,
                        }
                    ],
                },
            },
        )


def test_fetch_previous_close_quotes_requires_an_earlier_quote_date(
    tmp_path: Path,
):
    from trading_os.research_assets.manager_screen_snapshot import (
        ManagerScreenSnapshotError,
        fetch_eastmoney_previous_close_quotes,
    )

    root = tmp_path / "coverage" / "cn-a"
    run_id = "2026-07-31-non-previous-date"
    _write_frozen_quote_universe(root, run_id, ["CN:000001"])

    with pytest.raises(ManagerScreenSnapshotError, match="must precede"):
        fetch_eastmoney_previous_close_quotes(
            root=root,
            run_id=run_id,
            quote_date=dt.date(2026, 7, 31),
            fetched_at=dt.datetime.fromisoformat("2026-07-31T08:00:00+08:00"),
            fetch_payload=lambda _: pytest.fail("must reject before fetching"),
        )


def test_fetch_tencent_previous_close_quotes_chunks_decodes_gb18030_and_supports_bse(
    tmp_path: Path,
):
    from trading_os.research_assets.manager_screen_snapshot import (
        fetch_tencent_previous_close_quotes,
    )

    root = tmp_path / "coverage" / "cn-a"
    run_id = "2026-07-31-tencent-chunks"
    symbols = ["CN:000001", "CN:600000", "CN:920001"]
    _write_frozen_quote_universe(root, run_id, symbols)
    requested_chunks: list[list[str]] = []

    def fetch_text(url: str) -> bytes:
        codes = url.rsplit("=", 1)[1].split(",")
        requested_chunks.append(codes)
        return "\n".join(_tencent_line(code) for code in codes).encode("gb18030")

    quotes = fetch_tencent_previous_close_quotes(
        root=root,
        run_id=run_id,
        quote_date=dt.date(2026, 7, 30),
        fetched_at=dt.datetime.fromisoformat("2026-07-31T08:00:00+08:00"),
        chunk_size=2,
        fetch_text=fetch_text,
    )

    assert requested_chunks == [
        ["bj920001", "sh600000"],
        ["sz000001"],
    ]
    assert [quote["symbol"] for quote in quotes] == sorted(symbols)
    for quote in quotes:
        assert quote["price"] == 10.0
        assert quote["as_of"] == "2026-07-30"
        assert quote["market_cap_cny"] == 100_000_000_000
        assert quote["float_market_cap_cny"] == 50_000_000_000
        assert quote["pe_ttm"] == 20.0
        assert quote["pb"] == 2.5
        assert quote["turnover_cny"] is None
        assert quote["turnover_rate_pct"] is None


def test_fetch_tencent_previous_close_quotes_accepts_unambiguous_unknown_szse_identity(
    tmp_path: Path,
):
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.manager_screen_snapshot import (
        fetch_tencent_previous_close_quotes,
    )

    root = tmp_path / "coverage" / "cn-a"
    run_id = "2026-07-31-tencent-unknown-szse"
    _write_frozen_quote_universe(root, run_id, ["CN:302132"])
    snapshot = root / "snapshots" / run_id / "companies.jsonl"
    rows = read_jsonl(snapshot)
    rows[0]["exchange"] = "UNKNOWN"
    write_jsonl(snapshot, rows)

    requested: list[str] = []

    def fetch_text(url: str) -> str:
        code = url.rsplit("=", 1)[1]
        requested.append(code)
        return _tencent_line(code)

    quotes = fetch_tencent_previous_close_quotes(
        root=root,
        run_id=run_id,
        quote_date=dt.date(2026, 7, 30),
        fetched_at=dt.datetime.fromisoformat("2026-07-31T08:00:00+08:00"),
        fetch_text=fetch_text,
    )

    assert requested == ["sz302132"]
    assert quotes[0]["symbol"] == "CN:302132"


def test_fetch_tencent_previous_close_quotes_recomputes_from_frozen_fallback(
    tmp_path: Path,
):
    from trading_os.research_assets.manager_screen_snapshot import (
        fetch_tencent_previous_close_quotes,
    )

    root = tmp_path / "coverage" / "cn-a"
    run_id = "2026-07-31-tencent-fallback"
    _write_frozen_quote_universe(root, run_id, ["CN:000001"])

    quotes = fetch_tencent_previous_close_quotes(
        root=root,
        run_id=run_id,
        quote_date=dt.date(2026, 7, 30),
        fetched_at=dt.datetime.fromisoformat("2026-07-31T08:00:00+08:00"),
        fetch_text=lambda _: _tencent_line(
            "sz000001",
            current_price="",
            market_cap_yi="",
            float_market_cap_yi="",
            pe_ttm="",
            pb="",
        ),
    )

    assert quotes[0]["market_cap_cny"] == 1_000
    assert quotes[0]["float_market_cap_cny"] == 500
    assert quotes[0]["pe_ttm"] == 15.0
    assert quotes[0]["pb"] == 2.0


def test_fetch_tencent_previous_close_quotes_uses_default_80_symbol_chunks(
    tmp_path: Path,
):
    from trading_os.research_assets.manager_screen_snapshot import (
        fetch_tencent_previous_close_quotes,
    )

    root = tmp_path / "coverage" / "cn-a"
    run_id = "2026-07-31-tencent-default-chunks"
    symbols = [f"CN:{ticker:06d}" for ticker in range(1, 82)]
    _write_frozen_quote_universe(root, run_id, symbols)
    chunk_sizes: list[int] = []

    def fetch_text(url: str) -> str:
        codes = url.rsplit("=", 1)[1].split(",")
        chunk_sizes.append(len(codes))
        return "\n".join(_tencent_line(code) for code in codes)

    quotes = fetch_tencent_previous_close_quotes(
        root=root,
        run_id=run_id,
        quote_date=dt.date(2026, 7, 30),
        fetched_at=dt.datetime.fromisoformat("2026-07-31T08:00:00+08:00"),
        fetch_text=fetch_text,
    )

    assert chunk_sizes == [80, 1]
    assert len(quotes) == 81


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("invalid_encoding", "not valid GB18030"),
        ("invalid_type", "must be GB18030 bytes or text"),
        ("missing", "count does not match"),
        ("duplicate", "duplicate quote"),
        ("outside", "outside the frozen universe"),
        ("malformed", "row is malformed"),
        ("short", "required fields"),
        ("ticker_mismatch", "ticker does not match"),
        ("invalid_close", "must be a positive number"),
    ],
)
def test_fetch_tencent_previous_close_quotes_fails_closed_on_response_contract(
    tmp_path: Path,
    case: str,
    message: str,
):
    from trading_os.research_assets.manager_screen_snapshot import (
        ManagerScreenSnapshotError,
        fetch_tencent_previous_close_quotes,
    )

    root = tmp_path / "coverage" / "cn-a"
    run_id = f"2026-07-31-tencent-contract-{case}"
    _write_frozen_quote_universe(root, run_id, ["CN:000001", "CN:000002"])
    lines = [_tencent_line("sz000001"), _tencent_line("sz000002")]
    response: Any = "\n".join(lines).encode("gb18030")
    if case == "invalid_encoding":
        response = b"\x81"
    elif case == "invalid_type":
        response = []
    elif case == "missing":
        response = lines[0]
    elif case == "duplicate":
        response = "\n".join([lines[0], lines[0]])
    elif case == "outside":
        response = "\n".join([lines[0], _tencent_line("sz999999")])
    elif case == "malformed":
        response = "\n".join([lines[0], "not a quote row"])
    elif case == "short":
        response = "\n".join([lines[0], 'v_sz000002="1~name~000002";'])
    elif case == "ticker_mismatch":
        response = "\n".join([lines[0], _tencent_line("sz000002", ticker="000003")])
    elif case == "invalid_close":
        response = "\n".join([lines[0], _tencent_line("sz000002", previous_close="0")])

    with pytest.raises(ManagerScreenSnapshotError, match=message):
        fetch_tencent_previous_close_quotes(
            root=root,
            run_id=run_id,
            quote_date=dt.date(2026, 7, 30),
            fetched_at=dt.datetime.fromisoformat("2026-07-31T08:00:00+08:00"),
            chunk_size=2,
            fetch_text=lambda _: response,
        )


def test_fetch_tencent_previous_close_quotes_rejects_in_universe_wrong_chunk(
    tmp_path: Path,
):
    from trading_os.research_assets.manager_screen_snapshot import (
        ManagerScreenSnapshotError,
        fetch_tencent_previous_close_quotes,
    )

    root = tmp_path / "coverage" / "cn-a"
    run_id = "2026-07-31-tencent-wrong-chunk"
    _write_frozen_quote_universe(
        root,
        run_id,
        ["CN:000001", "CN:600000", "CN:920001"],
    )

    with pytest.raises(ManagerScreenSnapshotError, match="requested quote chunk"):
        fetch_tencent_previous_close_quotes(
            root=root,
            run_id=run_id,
            quote_date=dt.date(2026, 7, 30),
            fetched_at=dt.datetime.fromisoformat("2026-07-31T08:00:00+08:00"),
            chunk_size=2,
            fetch_text=lambda _: "\n".join(
                [
                    _tencent_line("bj920001"),
                    _tencent_line("sz000001"),
                ]
            ),
        )


@pytest.mark.parametrize(
    ("updated_at", "message"),
    [
        ("not-a-time", "timestamp is invalid"),
        ("20260729150000", "predates"),
        ("20260731080600", "after fetched_at"),
    ],
)
def test_fetch_tencent_previous_close_quotes_validates_update_time(
    tmp_path: Path,
    updated_at: str,
    message: str,
):
    from trading_os.research_assets.manager_screen_snapshot import (
        ManagerScreenSnapshotError,
        fetch_tencent_previous_close_quotes,
    )

    root = tmp_path / "coverage" / "cn-a"
    run_id = f"2026-07-31-tencent-time-{message.replace(' ', '-')}"
    _write_frozen_quote_universe(root, run_id, ["CN:000001"])

    with pytest.raises(ManagerScreenSnapshotError, match=message):
        fetch_tencent_previous_close_quotes(
            root=root,
            run_id=run_id,
            quote_date=dt.date(2026, 7, 30),
            fetched_at=dt.datetime.fromisoformat("2026-07-31T08:00:00+08:00"),
            fetch_text=lambda _: _tencent_line(
                "sz000001",
                updated_at=updated_at,
            ),
        )
