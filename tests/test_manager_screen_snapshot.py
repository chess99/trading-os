from __future__ import annotations

import datetime as dt
import json
from pathlib import Path


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


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
    row = json.loads(
        (tmp_path / result["path"]).read_text(encoding="utf-8").splitlines()[0]
    )
    assert "unsupported_exchange_identity" in row["manager_screen_facts"]["data_gaps"]
