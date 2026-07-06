from __future__ import annotations

import json
from pathlib import Path

from tests.test_company_assets import write_company


def test_company_report_template_contains_required_sections():
    root = Path(__file__).resolve().parents[1]
    text = (root / "templates" / "company-report.md").read_text(encoding="utf-8")

    for heading in [
        "## One-line Conclusion",
        "## Decision",
        "## Business Understanding",
        "## Industry and Competitive Context",
        "## Company Quality",
        "## Financial Quality",
        "## Valuation",
        "## Price and Position Plan",
        "## Key Assumptions",
        "## Follow-up Triggers",
        "## Risks",
        "## Previous Thesis Review",
        "## Sources",
    ]:
        assert heading in text


def test_playbooks_state_immutable_report_rule():
    root = Path(__file__).resolve().parents[1]
    company = (root / "playbooks" / "company-research.md").read_text(encoding="utf-8")
    followup = (root / "playbooks" / "followup-review.md").read_text(encoding="utf-8")

    assert "Do not overwrite existing reports" in company
    assert "Read the previous latest_report" in followup
    assert "Previous Thesis Review" in followup


def test_meta_schema_is_valid_json_and_has_validator_aligned_constraints():
    root = Path(__file__).resolve().parents[1]
    schema = json.loads(
        (root / "templates" / "meta.schema.json").read_text(encoding="utf-8")
    )
    properties = schema["properties"]

    for field in [
        "symbol",
        "market",
        "ticker",
        "name",
        "currency",
        "status",
        "current_rating",
        "current_thesis",
        "latest_report",
        "updated_at",
    ]:
        assert field in schema["required"]
        assert properties[field]["minLength"] == 1

    assert properties["position_plan"]["minItems"] == 1
    assert properties["position_plan"]["items"]["properties"]["condition"][
        "minLength"
    ] == 1
    assert properties["report_history"]["minItems"] == 1
    assert properties["report_history"]["items"]["minLength"] == 1

    review_trigger = properties["review_triggers"]["items"]["properties"]
    assert review_trigger["type"]["minLength"] == 1
    assert review_trigger["date"]["minLength"] == 1
    assert review_trigger["reason"]["minLength"] == 1

    price_trigger = properties["price_triggers"]["items"]["properties"]
    assert price_trigger["type"]["minLength"] == 1
    assert price_trigger["reason"]["minLength"] == 1

    for field in ["fair_value_range", "buy_zone", "sell_or_reduce_zone"]:
        description = properties[field]["description"]
        assert "lower bound" in description
        assert "<= upper bound" in description


def test_company_fixture_matches_schema_required_fields_and_validator(tmp_path: Path):
    from trading_os.research_assets.company import validate_company_dir

    root = Path(__file__).resolve().parents[1]
    schema = json.loads(
        (root / "templates" / "meta.schema.json").read_text(encoding="utf-8")
    )
    company_dir = write_company(tmp_path)
    meta = json.loads((company_dir / "meta.json").read_text(encoding="utf-8"))

    for field in schema["required"]:
        assert field in meta

    validated = validate_company_dir(company_dir)
    assert validated["symbol"] == "CN:600519"
