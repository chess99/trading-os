from __future__ import annotations

import json
from pathlib import Path

import pytest


def write_company(root: Path, *, rating: str = "watch") -> Path:
    company_dir = root / "research" / "companies" / "CN" / "600519"
    reports = company_dir / "reports"
    reports.mkdir(parents=True)
    report_path = reports / "2026-07-06-initial.md"
    report_path.write_text(
        "# Company Research: 贵州茅台 (CN:600519)\n\n"
        "Date: 2026-07-06\n"
        "Research Type: initial\n"
        "Analyst: agent\n\n"
        "## One-line Conclusion\n\n"
        "High-quality cash compounder with valuation discipline required.\n\n"
        "## Decision\n\n"
        "Watch.\n\n"
        "## Business Understanding\n\n"
        "Premium baijiu producer.\n\n"
        "## Industry and Competitive Context\n\n"
        "High-end baijiu remains concentrated.\n\n"
        "## Company Quality\n\n"
        "Wide moat.\n\n"
        "## Financial Quality\n\n"
        "High margins and strong cash flow.\n\n"
        "## Valuation\n\n"
        "Fair value range is 1150-1450 CNY.\n\n"
        "## Price and Position Plan\n\n"
        "Initial buy zone is 1000-1100 CNY.\n\n"
        "## Key Assumptions\n\n"
        "- Premium demand remains resilient.\n\n"
        "## Follow-up Triggers\n\n"
        "- Review after semiannual report.\n\n"
        "## Risks\n\n"
        "- Demand weakness.\n\n"
        "## Previous Thesis Review\n\n"
        "No previous report exists.\n\n"
        "## Sources\n\n"
        "- Company filings.\n",
        encoding="utf-8",
    )
    meta = {
        "symbol": "CN:600519",
        "market": "CN",
        "ticker": "600519",
        "name": "贵州茅台",
        "currency": "CNY",
        "status": "active",
        "current_rating": rating,
        "current_thesis": "High-quality cash compounder.",
        "fair_value_range": [1150, 1450],
        "buy_zone": [1000, 1100],
        "sell_or_reduce_zone": [1500, 1800],
        "position_plan": [
            {"condition": "price <= 1150", "max_weight": 0.05},
            {"condition": "price <= 1000", "max_weight": 0.12},
        ],
        "latest_report": "reports/2026-07-06-initial.md",
        "report_history": ["reports/2026-07-06-initial.md"],
        "review_triggers": [
            {"type": "date", "date": "2026-08-31", "reason": "Semiannual review."}
        ],
        "price_triggers": [
            {"type": "price_below", "price": 1100, "reason": "Enter buy zone."}
        ],
        "updated_at": "2026-07-06T00:00:00+08:00",
    }
    (company_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return company_dir


def test_valid_company_asset_loads(tmp_path: Path):
    from trading_os.research_assets.company import validate_company_dir

    company_dir = write_company(tmp_path)

    meta = validate_company_dir(company_dir)

    assert meta["symbol"] == "CN:600519"
    assert meta["latest_report"] == "reports/2026-07-06-initial.md"


def test_invalid_rating_is_rejected(tmp_path: Path):
    from trading_os.research_assets.company import AssetValidationError, validate_company_dir

    company_dir = write_company(tmp_path, rating="strong_buy")

    with pytest.raises(AssetValidationError, match="current_rating"):
        validate_company_dir(company_dir)


def test_missing_latest_report_is_rejected(tmp_path: Path):
    from trading_os.research_assets.company import AssetValidationError, validate_company_dir

    company_dir = write_company(tmp_path)
    (company_dir / "reports" / "2026-07-06-initial.md").unlink()

    with pytest.raises(AssetValidationError, match="latest_report"):
        validate_company_dir(company_dir)
