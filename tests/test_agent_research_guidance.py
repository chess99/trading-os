from pathlib import Path

RETIRED_WORKFLOW_TERMS = [
    "scheduler status",
    "python -m trading_os daily",
    "scan-canslim",
    "fetch-ak-bulk",
    "sync-from-scan",
    "query-bars",
    "market-breadth",
    "python -m trading_os valuation",
    "python -m trading_os fundamental",
    "python -m trading_os 52week",
    "python -m trading_os backtest --",
    "valuation-sotp",
    "valuation-sensitivity",
]


def test_agents_guidance_points_to_research_recipes_not_scheduler_bulk():
    text = Path("AGENTS.md").read_text(encoding="utf-8")

    assert "ResearchStore" in text
    assert "research recipe" in text
    assert "python -m trading_os research run canslim_screen" in text
    for term in RETIRED_WORKFLOW_TERMS:
        assert term not in text
    assert "scheduler trigger market_data_bulk_refresh" not in text


def test_daily_skill_no_longer_requires_scheduler_bulk_refresh():
    text = Path("skills/daily-workflow/SKILL.md").read_text(encoding="utf-8")

    assert "python -m trading_os research daily" in text
    assert "bulk refresh" not in text.lower()
    assert "blocked" not in text.lower()


def test_readme_and_core_skills_do_not_reference_retired_workflows():
    paths = [
        Path("README.md"),
        Path("AGENTS.md"),
        Path("skills/elder-signal-scanner/SKILL.md"),
        Path("skills/value-fundamental-research/SKILL.md"),
        Path("skills/canslim-fundamental-research/SKILL.md"),
    ]

    for path in paths:
        text = path.read_text(encoding="utf-8")
        for term in RETIRED_WORKFLOW_TERMS:
            assert term not in text, f"{path} still references {term}"


def test_gitignore_tracks_new_artifact_boundaries_not_retired_scan_daily():
    text = Path(".gitignore").read_text(encoding="utf-8")

    assert "!artifacts/research/" in text
    assert "!artifacts/watchlist/" in text
    assert "!artifacts/runs/" in text
    assert "!artifacts/daily/" not in text
    assert "!artifacts/scan/" not in text
