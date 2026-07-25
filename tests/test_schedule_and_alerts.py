from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from tests.test_company_assets import write_company

NOW = dt.datetime(2026, 7, 21, 15, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))


def _load_meta(company_dir: Path) -> dict[str, object]:
    return json.loads((company_dir / "meta.json").read_text(encoding="utf-8"))


def _write_meta(company_dir: Path, meta: dict[str, object]) -> None:
    (company_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _underwrite(meta: dict[str, object], *, status: str = "passed") -> None:
    meta["underwriting"] = {
        "status": status,
        "review_id": "review-2026-07-21",
        "confidence": "high",
        "evidence_valid_until": "2026-10-21T15:00:00+08:00",
        "reason_codes": [f"underwriting_{status}"],
    }
    meta["valuation"] = {
        "currency": "CNY",
        "price_as_of": "2026-07-21T15:00:00+08:00",
        "bear_value": 60.0,
        "fair_value_range": [95.0, 105.0],
        "buy_zone": [70.0, 80.0],
        "reduce_zone": [120.0, 130.0],
    }


def test_review_schedule_preserves_generic_company_triggers(tmp_path: Path):
    from trading_os.research_assets.schedule import build_review_schedule

    company_dir = write_company(tmp_path)
    meta = _load_meta(company_dir)
    _underwrite(meta)
    meta["triggers"].append(
        {
            "trigger_id": "scheduled-review",
            "type": "date",
            "condition": {"date": "2026-08-31"},
            "reason": "半年报后复核。",
            "active": True,
        }
    )
    _write_meta(company_dir, meta)

    schedule = build_review_schedule(tmp_path / "research")

    assert schedule["schema_version"] == 2
    assert schedule["item_count"] == 2
    assert {item["type"] for item in schedule["items"]} == {"date", "filing"}
    date_item = next(item for item in schedule["items"] if item["type"] == "date")
    assert date_item["condition"] == {"date": "2026-08-31"}
    assert date_item["source"] == "company_trigger"


def test_review_schedule_adds_structured_conclusion_invalidation(tmp_path: Path):
    from trading_os.research_assets.schedule import build_review_schedule

    company_dir = write_company(tmp_path)
    meta = _load_meta(company_dir)
    _underwrite(meta, status="stale")
    _write_meta(company_dir, meta)

    schedule = build_review_schedule(tmp_path / "research")

    invalid = next(
        item for item in schedule["items"] if item["source"] == "conclusion_invalidation"
    )
    assert invalid["condition"] == {"conclusion_status": "stale"}
    assert invalid["type"] == "thesis"


def test_rebaseline_company_has_one_rebuild_task_and_no_legacy_triggers(
    tmp_path: Path,
):
    from trading_os.research_assets.schedule import build_review_schedule

    company_dir = write_company(tmp_path)
    meta = _load_meta(company_dir)
    meta["research"]["rebaseline_required"] = True
    meta["triggers"].append(
        {
            "trigger_id": "legacy-price",
            "type": "price",
            "condition": {"operator": "price_lte", "threshold": 100.0},
            "reason": "旧估值触发器。",
            "active": True,
        }
    )
    _write_meta(company_dir, meta)

    schedule = build_review_schedule(tmp_path / "research")

    assert schedule["item_count"] == 1
    assert schedule["items"][0]["type"] == "rebaseline"
    assert schedule["items"][0]["source"] == "research_rebaseline"


def test_price_alerts_include_buy_zone_and_ten_percent_staleness(tmp_path: Path):
    from trading_os.research_assets.alerts import build_price_alerts

    company_dir = write_company(tmp_path)
    meta = _load_meta(company_dir)
    _underwrite(meta)
    _write_meta(company_dir, meta)

    alerts = build_price_alerts(tmp_path / "research")

    assert alerts["schema_version"] == 2
    assert {item["type"] for item in alerts["items"]} == {
        "underwriting_buy_zone_entry",
        "conclusion_price_move_stale",
    }
    buy = next(
        item for item in alerts["items"] if item["type"] == "underwriting_buy_zone_entry"
    )
    assert buy["condition"] == {"operator": "price_lte", "threshold": 80.0}
    stale = next(
        item for item in alerts["items"] if item["type"] == "conclusion_price_move_stale"
    )
    assert stale["condition"]["threshold"] == 0.10


def test_company_reduce_zone_does_not_create_a_reduce_alert(tmp_path: Path):
    from trading_os.research_assets.alerts import build_price_alerts

    company_dir = write_company(tmp_path)
    meta = _load_meta(company_dir)
    _underwrite(meta)
    _write_meta(company_dir, meta)

    types = {item["type"] for item in build_price_alerts(tmp_path / "research")["items"]}

    assert "portfolio_reduce_observation" not in types
    assert "price_above" not in types


def test_rebaseline_company_suppresses_all_company_price_alerts(tmp_path: Path):
    from trading_os.research_assets.alerts import build_price_alerts

    company_dir = write_company(tmp_path)
    meta = _load_meta(company_dir)
    _underwrite(meta)
    meta["research"]["rebaseline_required"] = True
    meta["triggers"].append(
        {
            "trigger_id": "legacy-price",
            "type": "price",
            "condition": {"operator": "price_lte", "threshold": 100.0},
            "reason": "旧估值触发器。",
            "active": True,
        }
    )
    _write_meta(company_dir, meta)

    alerts = build_price_alerts(tmp_path / "research")

    assert alerts["item_count"] == 0


def test_price_trigger_waits_for_independent_underwriting(tmp_path: Path):
    from trading_os.research_assets.alerts import build_price_alerts

    company_dir = write_company(tmp_path)
    meta = _load_meta(company_dir)
    meta["triggers"].append(
        {
            "trigger_id": "initial-research-price",
            "type": "price",
            "condition": {"operator": "price_lte", "threshold": 100.0},
            "reason": "初研价格线索，尚未经独立承保。",
            "active": True,
        }
    )
    _write_meta(company_dir, meta)

    alerts = build_price_alerts(tmp_path / "research")

    assert alerts["item_count"] == 0


def test_reduce_and_exit_observations_only_come_from_sealed_portfolio(tmp_path: Path):
    from trading_os.research_assets.alerts import build_price_alerts
    from trading_os.research_assets.sealing import seal_json

    research_root = tmp_path / "research"
    portfolio_path = research_root / "batches" / "run-1" / "portfolio.json"
    seal_json(
        portfolio_path,
        {
            "schema_version": 3,
            "run_id": "run-1",
            "as_of": NOW.isoformat(),
            "positions": [
                {"symbol": "CN:000001", "name": "平安银行", "action": "reduce"},
                {"symbol": "CN:000002", "name": "万科A", "action": "exit"},
            ],
        },
        artifact_type="model_portfolio",
        sealed_at=NOW,
    )

    alerts = build_price_alerts(research_root)

    assert {item["type"] for item in alerts["items"]} == {
        "portfolio_reduce_observation",
        "portfolio_exit_observation",
    }
    assert all(item["source_ref"] == "batches/run-1/portfolio.json" for item in alerts["items"])


def test_near_miss_alert_uses_combined_return_and_buy_zone_ceiling(
    tmp_path: Path,
):
    from trading_os.research_assets.alerts import (
        build_price_alerts,
        evaluate_price_alerts,
    )
    from trading_os.research_assets.sealing import seal_json

    research_root = tmp_path / "research"
    seal_json(
        research_root / "batches" / "run-1" / "portfolio.json",
        {
            "schema_version": 3,
            "run_id": "run-1",
            "as_of": NOW.isoformat(),
            "positions": [
                {
                    "symbol": "CN:000001",
                    "name": "测试公司",
                    "underwriting_status": "passed",
                    "evidence_stale": False,
                    "action": "watch",
                    "buy_now_price_ceiling": 71.1780247813411,
                    "reason_codes": [
                        "expected_return_below_minimum",
                        "expected_return_near_miss",
                    ],
                }
            ],
        },
        artifact_type="model_portfolio",
        sealed_at=NOW,
    )

    alerts = build_price_alerts(research_root)
    threshold_alert = next(
        item
        for item in alerts["items"]
        if item["type"] == "portfolio_buy_threshold_entry"
    )
    assert threshold_alert["condition"]["threshold"] == pytest.approx(
        71.1780247813411
    )
    assert (
        evaluate_price_alerts(
            alerts,
            [{"symbol": "CN:000001", "price": 72.0, "as_of": NOW.isoformat()}],
        )["triggered_count"]
        == 0
    )
    triggered = evaluate_price_alerts(
        alerts,
        [{"symbol": "CN:000001", "price": 71.0, "as_of": NOW.isoformat()}],
    )
    assert triggered["triggered_count"] == 1
    assert triggered["triggered"][0]["type"] == "portfolio_buy_threshold_entry"


def test_evaluate_v2_alerts_detects_buy_zone_and_price_staleness():
    from trading_os.research_assets.alerts import evaluate_price_alerts

    alerts = {
        "schema_version": 2,
        "items": [
            {
                "alert_id": "CN:600519:buy",
                "symbol": "CN:600519",
                "name": "贵州茅台",
                "type": "underwriting_buy_zone_entry",
                "condition": {"operator": "price_lte", "threshold": 80.0},
                "reason": "重查后决定。",
                "latest_report": "companies/CN/600519/reports/example.md",
                "source_ref": "review-1",
            },
            {
                "alert_id": "CN:600519:stale",
                "symbol": "CN:600519",
                "name": "贵州茅台",
                "type": "conclusion_price_move_stale",
                "condition": {
                    "operator": "absolute_change_fraction_gte",
                    "threshold": 0.10,
                },
                "reason": "价格结论过期。",
                "latest_report": "companies/CN/600519/reports/example.md",
                "source_ref": "review-1",
            },
        ],
    }
    quotes = [
        {
            "symbol": "CN:600519",
            "price": 79.0,
            "change_since_review": -0.11,
            "as_of": "2026-07-21T15:00:00+08:00",
        }
    ]

    triggered = evaluate_price_alerts(alerts, quotes)

    assert triggered["schema_version"] == 2
    assert triggered["triggered_count"] == 2
    assert {item["type"] for item in triggered["triggered"]} == {
        "underwriting_buy_zone_entry",
        "conclusion_price_move_stale",
    }


def test_evaluate_alerts_ignores_bool_and_non_object_quotes():
    from trading_os.research_assets.alerts import evaluate_price_alerts

    alerts = {
        "schema_version": 2,
        "items": [
            {
                "alert_id": "CN:600519:buy",
                "symbol": "CN:600519",
                "name": "贵州茅台",
                "type": "underwriting_buy_zone_entry",
                "condition": {"operator": "price_lte", "threshold": 80.0},
                "reason": "重查后决定。",
                "latest_report": None,
                "source_ref": "review-1",
            }
        ],
    }

    triggered = evaluate_price_alerts(
        alerts,
        [None, {"symbol": "CN:600519", "price": True}],
    )

    assert triggered["triggered_count"] == 0


def test_schedule_and_alert_writes_are_byte_stable(tmp_path: Path):
    from trading_os.research_assets.alerts import write_price_alerts
    from trading_os.research_assets.schedule import write_review_schedule

    write_company(tmp_path)
    research_root = tmp_path / "research"
    schedule_path = tmp_path / "automation" / "schedule.json"
    alerts_path = tmp_path / "automation" / "alerts.json"

    write_review_schedule(research_root, schedule_path)
    write_price_alerts(research_root, alerts_path)
    first = (schedule_path.read_bytes(), alerts_path.read_bytes())
    write_review_schedule(research_root, schedule_path)
    write_price_alerts(research_root, alerts_path)

    assert (schedule_path.read_bytes(), alerts_path.read_bytes()) == first
