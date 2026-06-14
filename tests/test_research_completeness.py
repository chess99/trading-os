from __future__ import annotations


def test_company_research_completeness_complete_with_core_data_and_missing_enrichment():
    from trading_os.research.completeness import evaluate_company_research_completeness

    result = evaluate_company_research_completeness(
        {
            "quotes": True,
            "fundamentals": True,
            "bars": True,
            "estimates": False,
            "news": False,
        }
    )

    assert result.complete is True
    assert result.status == "complete"
    assert result.core_missing == []
    assert result.enrichment_missing == ["estimates", "news"]
    assert result.score == 0.75


def test_company_research_completeness_incomplete_when_core_data_missing():
    from trading_os.research.completeness import evaluate_company_research_completeness

    result = evaluate_company_research_completeness(
        {
            "quotes": True,
            "fundamentals": False,
            "bars": True,
            "estimates": True,
            "news": True,
        }
    )

    assert result.complete is False
    assert result.status == "incomplete"
    assert result.core_missing == ["fundamentals"]
    assert result.enrichment_missing == []
    assert result.score == 0.75


def test_status_from_company_manifest_uses_completeness_payload():
    from trading_os.research.completeness import status_from_company_manifest

    status = status_from_company_manifest(
        {
            "completeness": {
                "status": "incomplete",
                "core_missing": ["bars"],
                "enrichment_missing": ["news"],
            }
        }
    )

    assert status == {
        "status": "incomplete",
        "missing_core_datasets": ["bars"],
        "missing_enrichment_datasets": ["news"],
    }
