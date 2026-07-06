from __future__ import annotations

import json
from pathlib import Path

DECISIONS = {
    "deep_research",
    "watch_only",
    "skip_risk",
    "skip_too_small",
    "skip_not_in_scope",
    "needs_manual_review",
}

QUEUE_STATUSES = {
    "pending",
    "running",
    "completed",
    "failed",
    "skipped",
    "needs_review",
}


def test_coverage_examples_are_valid_json():
    root = Path(__file__).resolve().parents[1]

    for path in (root / "coverage" / "cn-a").glob("*.example.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["schema_version"] == 1
        assert payload["market"] == "CN"


def test_screening_example_uses_fixed_decision_protocol():
    root = Path(__file__).resolve().parents[1]
    payload = json.loads(
        (root / "coverage" / "cn-a" / "screening.example.json").read_text(
            encoding="utf-8"
        )
    )

    decisions = {item["decision"] for item in payload["results"]}
    assert decisions <= DECISIONS
    assert {"deep_research", "skip_not_in_scope"} <= decisions
    for item in payload["results"]:
        assert item["reason"].strip()
        assert item["evidence"]
        assert item["next_action"].strip()


def test_research_queue_example_is_resumable():
    root = Path(__file__).resolve().parents[1]
    payload = json.loads(
        (root / "coverage" / "cn-a" / "research-queue.example.json").read_text(
            encoding="utf-8"
        )
    )

    for item in payload["items"]:
        assert item["status"] in QUEUE_STATUSES
        assert item["target_company_dir"].startswith("research/companies/CN/")
        assert item["next_action"].strip()


def test_docs_route_full_market_work_through_coverage():
    root = Path(__file__).resolve().parents[1]
    agents = (root / "AGENTS.md").read_text(encoding="utf-8")
    readme = (root / "README.md").read_text(encoding="utf-8")
    claude = (root / "CLAUDE.md").read_text(encoding="utf-8")
    screening = (root / "playbooks" / "screening.md").read_text(encoding="utf-8")

    assert "coverage/" in agents
    assert "playbooks/screening.md" in agents
    assert "coverage/" in readme
    assert "AGENTS.md" in claude
    assert "coverage/" in claude
    assert "deep_research" in screening
    assert "skip_not_in_scope" in screening
