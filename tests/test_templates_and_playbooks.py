from __future__ import annotations

from pathlib import Path


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
