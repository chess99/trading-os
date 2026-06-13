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


def test_canslim_guidance_distinguishes_display_limit_from_full_results():
    agents = Path("AGENTS.md").read_text(encoding="utf-8")
    skill = Path("skills/canslim-system/SKILL.md").read_text(encoding="utf-8")

    for text in [agents, skill]:
        assert "--top" in text
        assert "展示上限" in text
        assert "candidates_total" in text
        assert "strict_candidates_total" in text
        assert "tables/all_candidates.csv" in text
        assert "不要任意只取 top 3" in text


def test_canslim_guidance_requires_human_readable_research_summary():
    agents = Path("AGENTS.md").read_text(encoding="utf-8")
    skill = Path("skills/canslim-system/SKILL.md").read_text(encoding="utf-8")

    for text in [agents, skill]:
        assert "artifacts/research/" in text
        assert "人类可读" in text
        assert "不能只" in text
        assert "data/research/runs" in text
        assert "单标的报告路径" in text
        assert "下一步" in text


def test_canslim_guidance_requires_complete_post_screen_review():
    agents = Path("AGENTS.md").read_text(encoding="utf-8")
    skill = Path("skills/canslim-system/SKILL.md").read_text(encoding="utf-8")

    required_terms = [
        "完整复核报告",
        "后续再补",
        "近 12 个月公告/事件",
        "管理层指引/订单/产能/产品线索",
        "机构持仓",
        "同业拥挤度",
        "base/pivot/突破放量技术确认",
        "失败接口",
        "替代口径",
    ]
    for text in [agents, skill]:
        for term in required_terms:
            assert term in text


def test_docs_reference_daily_canslim_closure():
    agents = Path("AGENTS.md").read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "daily-canslim" in agents
    assert "daily-canslim" in readme
    assert "data/research/runs/{run_id}/manifest.json" in agents
    assert "data/research/runs/{run_id}/manifest.json" in readme
    assert "artifacts/runs/{run_id}" not in agents
    assert "artifacts/runs/{run_id}" not in readme
    assert "观察池盘中提醒" in agents


def test_daily_skill_requires_human_report_and_watchlist_state():
    text = Path("skills/daily-workflow/SKILL.md").read_text(encoding="utf-8")

    assert "artifacts/research/daily-canslim-YYYYMMDD.md" in text
    assert "artifacts/watchlist/state.json" in text
    assert "data/research/runs/{run_id}/manifest.json" in text
    assert "artifacts/runs/{run_id}" not in text
    assert "不能只输出 run manifest" in text


def test_canslim_skill_uses_implemented_run_manifest_path():
    text = Path("skills/canslim-system/SKILL.md").read_text(encoding="utf-8")

    assert "data/research/runs/{run_id}/manifest.json" in text
    assert "artifacts/runs/{run_id}" not in text


def test_core_skills_use_implemented_run_artifact_path():
    paths = [
        Path("skills/daily-workflow/SKILL.md"),
        Path("skills/canslim-system/SKILL.md"),
        Path("skills/elder-signal-scanner/SKILL.md"),
        Path("skills/value-valuation/SKILL.md"),
        Path("skills/canslim-fundamental-research/SKILL.md"),
        Path("skills/value-fundamental-research/SKILL.md"),
    ]

    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "artifacts/runs/{run_id}" not in text, f"{path} uses stale run path"


def test_daily_skill_no_longer_requires_scheduler_bulk_refresh():
    text = Path("skills/daily-workflow/SKILL.md").read_text(encoding="utf-8")

    assert "python -m trading_os research daily-canslim" in text
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
