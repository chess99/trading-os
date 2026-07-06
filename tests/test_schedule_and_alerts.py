from __future__ import annotations

from pathlib import Path

from tests.test_company_assets import write_company


def test_build_review_schedule_from_date_triggers(tmp_path: Path):
    from trading_os.research_assets.schedule import build_review_schedule

    write_company(tmp_path)

    schedule = build_review_schedule(tmp_path / "research")

    assert schedule["schema_version"] == 1
    assert schedule["items"][0]["symbol"] == "CN:600519"
    assert schedule["items"][0]["date"] == "2026-08-31"


def test_build_price_alerts_from_price_triggers(tmp_path: Path):
    from trading_os.research_assets.alerts import build_price_alerts

    write_company(tmp_path)

    alerts = build_price_alerts(tmp_path / "research")

    assert alerts["schema_version"] == 1
    assert alerts["items"][0]["symbol"] == "CN:600519"
    assert alerts["items"][0]["price"] == 1100


def test_evaluate_price_alerts_detects_triggered_snapshot():
    from trading_os.research_assets.alerts import evaluate_price_alerts

    alerts = {
        "schema_version": 1,
        "items": [
            {
                "symbol": "CN:600519",
                "name": "贵州茅台",
                "type": "price_below",
                "price": 1100,
                "reason": "Enter buy zone.",
                "latest_report": "companies/CN/600519/reports/2026-07-06-initial.md",
            }
        ],
    }
    quotes = [{"symbol": "CN:600519", "price": 1099.5, "as_of": "2026-07-06T10:30:00+08:00"}]

    triggered = evaluate_price_alerts(alerts, quotes)

    assert triggered["triggered_count"] == 1
    assert triggered["triggered"][0]["symbol"] == "CN:600519"
    assert triggered["triggered"][0]["observed_price"] == 1099.5
