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


def test_meta_json_with_utf8_bom_loads(tmp_path: Path):
    from trading_os.research_assets.company import validate_company_dir

    company_dir = write_company(tmp_path)
    meta_path = company_dir / "meta.json"
    text = meta_path.read_text(encoding="utf-8")
    meta_path.write_text("\ufeff" + text, encoding="utf-8")

    meta = validate_company_dir(company_dir)

    assert meta["symbol"] == "CN:600519"


def test_invalid_rating_is_rejected(tmp_path: Path):
    from trading_os.research_assets.company import AssetValidationError, validate_company_dir

    company_dir = write_company(tmp_path, rating="strong_buy")

    with pytest.raises(AssetValidationError, match="current_rating"):
        validate_company_dir(company_dir)


def test_symbol_must_match_market_and_ticker_fields(tmp_path: Path):
    from trading_os.research_assets.company import AssetValidationError, validate_company_dir

    company_dir = write_company(tmp_path)
    meta_path = company_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["symbol"] = "CN:000001"
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(AssetValidationError, match="symbol"):
        validate_company_dir(company_dir)


def test_company_directory_must_match_market_and_ticker(tmp_path: Path):
    from trading_os.research_assets.company import AssetValidationError, validate_company_dir

    company_dir = write_company(tmp_path)
    wrong_dir = tmp_path / "research" / "companies" / "CN" / "000001"
    wrong_dir.parent.mkdir(parents=True, exist_ok=True)
    company_dir.rename(wrong_dir)

    with pytest.raises(AssetValidationError, match="company directory"):
        validate_company_dir(wrong_dir)


def test_missing_latest_report_is_rejected(tmp_path: Path):
    from trading_os.research_assets.company import AssetValidationError, validate_company_dir

    company_dir = write_company(tmp_path)
    (company_dir / "reports" / "2026-07-06-initial.md").unlink()

    with pytest.raises(AssetValidationError, match="latest_report"):
        validate_company_dir(company_dir)


def test_latest_report_missing_from_report_history_is_rejected(tmp_path: Path):
    from trading_os.research_assets.company import AssetValidationError, validate_company_dir

    company_dir = write_company(tmp_path)
    second_report = company_dir / "reports" / "2026-08-31-h1-review.md"
    second_report.write_text("# H1 Review\n", encoding="utf-8")
    meta_path = company_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["latest_report"] = "reports/2026-08-31-h1-review.md"
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(AssetValidationError, match="latest_report"):
        validate_company_dir(company_dir)


def test_latest_report_absolute_path_outside_company_dir_is_rejected(tmp_path: Path):
    from trading_os.research_assets.company import AssetValidationError, validate_company_dir

    company_dir = write_company(tmp_path)
    outside_report = tmp_path / "outside.md"
    outside_report.write_text("# Outside\n", encoding="utf-8")
    meta_path = company_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["latest_report"] = str(outside_report)
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(AssetValidationError, match="latest_report"):
        validate_company_dir(company_dir)


def test_latest_report_outside_reports_is_rejected(tmp_path: Path):
    from trading_os.research_assets.company import AssetValidationError, validate_company_dir

    company_dir = write_company(tmp_path)
    sources = company_dir / "sources"
    sources.mkdir()
    (sources / "note.md").write_text("# Note\n", encoding="utf-8")
    meta_path = company_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["latest_report"] = "sources/note.md"
    meta["report_history"] = ["sources/note.md"]
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(AssetValidationError, match="latest_report"):
        validate_company_dir(company_dir)


def test_latest_report_without_report_date_is_rejected(tmp_path: Path):
    from trading_os.research_assets.company import AssetValidationError, validate_company_dir

    company_dir = write_company(tmp_path)
    (company_dir / "reports" / "not-a-date.md").write_text("# Bad\n", encoding="utf-8")
    meta_path = company_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["latest_report"] = "reports/not-a-date.md"
    meta["report_history"] = ["reports/not-a-date.md"]
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(AssetValidationError, match="latest_report"):
        validate_company_dir(company_dir)


def test_latest_report_directory_named_markdown_is_rejected(tmp_path: Path):
    from trading_os.research_assets.company import AssetValidationError, validate_company_dir

    company_dir = write_company(tmp_path)
    (company_dir / "reports" / "2026-07-06-dir.md").mkdir()
    meta_path = company_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["latest_report"] = "reports/2026-07-06-dir.md"
    meta["report_history"] = ["reports/2026-07-06-dir.md"]
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(AssetValidationError, match="report file"):
        validate_company_dir(company_dir)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("fair_value_range", [True, 1450], "fair_value_range"),
        ("position_plan", [{"condition": "price <= 1150", "max_weight": True}], "max_weight"),
        (
            "price_triggers",
            [{"type": "price_below", "price": True, "reason": "Enter buy zone."}],
            "price",
        ),
    ],
)
def test_boolean_numeric_values_are_rejected(
    tmp_path: Path, field: str, value: object, message: str
):
    from trading_os.research_assets.company import AssetValidationError, validate_company_dir

    company_dir = write_company(tmp_path)
    meta_path = company_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta[field] = value
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(AssetValidationError, match=message):
        validate_company_dir(company_dir)


def test_impossible_review_trigger_date_is_rejected(tmp_path: Path):
    from trading_os.research_assets.company import AssetValidationError, validate_company_dir

    company_dir = write_company(tmp_path)
    meta_path = company_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["review_triggers"] = [
        {"type": "date", "date": "2026-99-99", "reason": "Impossible date."}
    ]
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(AssetValidationError, match="review_triggers date"):
        validate_company_dir(company_dir)


def test_research_assets_star_import_succeeds():
    namespace: dict[str, object] = {}

    exec("from trading_os.research_assets import *", namespace)

    assert "AssetValidationError" in namespace
    assert "validate_company_dir" in namespace
