from pathlib import Path


def test_agents_guidance_points_to_research_recipes_not_scheduler_bulk():
    text = Path("AGENTS.md").read_text(encoding="utf-8")

    assert "ResearchStore" in text
    assert "research recipe" in text
    assert "python -m trading_os research run canslim_screen" in text
    assert "fetch-ak-bulk" not in text
    assert "scheduler trigger market_data_bulk_refresh" not in text


def test_daily_skill_no_longer_requires_scheduler_bulk_refresh():
    text = Path("skills/daily-workflow/SKILL.md").read_text(encoding="utf-8")

    assert "python -m trading_os research daily" in text
    assert "bulk refresh" not in text.lower()
    assert "blocked" not in text.lower()
