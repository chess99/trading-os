from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from tests.test_company_assets import write_company

SEALED_AT = dt.datetime.fromisoformat("2026-07-27T10:00:00+08:00")
PUBLISHED_AT = dt.datetime.fromisoformat("2026-07-27T10:05:00+08:00")


def _make_rebaseline_company(root: Path) -> Path:
    company_dir = write_company(root)
    meta_path = company_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["research"].update(
        {"coverage_status": "requires_rebaseline", "rebaseline_required": True}
    )
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return company_dir


def _package(*, review_mode: str = "baseline_recheck") -> dict:
    return {
        "schema_version": 2,
        "cycle_id": "2026-07-27-timeline-test",
        "review_mode": review_mode,
        "symbol": "CN:600519",
        "company_name": "贵州茅台",
        "as_of": "2026-07-27",
        "information_cutoff": "2026-07-27T09:30:00+08:00",
        "price_as_of": "2026-07-27T09:25:00+08:00",
        "price_source_id": "quote",
        "current_price": 100.0,
        "business_summary": "公司以高端白酒生产和经销为主。",
        "change_summary": "与上一轮相比没有发现生存或治理层面的重大恶化。",
        "normalized_earnings_view": "正常化盈利可粗略理解，但仍需核验渠道库存。",
        "expectations_view": "当前价格隐含较高的长期增长预期。",
        "counterevidence": ["渠道库存数据仍不完整", "提价后的动销需要验证"],
        "business_legibility": "clear",
        "survival_status": "pass",
        "governance_status": "acceptable",
        "earnings_legibility": "plausible",
        "valuation_signal": "unattractive",
        "research_value": "low",
        "decisive_question": "真实终端动销能否支持当前预期",
        "reason_codes": ["latest_filing_and_price_checked"],
        "revisit_triggers": [
            {
                "trigger_id": "next-filing",
                "type": "filing",
                "condition": {"description": "下一份定期报告正式披露"},
                "reason": "核验收入、现金流和库存。",
            },
            {
                "trigger_id": "research-price",
                "type": "price",
                "condition": {"operator": "price_lte", "threshold": 80.0},
                "reason": "价格回落后重新评估研究赔率。",
            },
            {
                "trigger_id": "calendar-review",
                "type": "date",
                "condition": {"date": "2026-09-30"},
                "reason": "季度例行复核。",
            },
            {
                "trigger_id": "material-event",
                "type": "event",
                "condition": {"description": "重大渠道或治理事件"},
                "reason": "事件可能改变盈利质量。",
            },
            {
                "trigger_id": "thesis-break",
                "type": "thesis",
                "condition": {"description": "渠道库存显著恶化"},
                "reason": "核心经营假设失效。",
            },
            {
                "trigger_id": "evidence-ttl",
                "type": "ttl",
                "condition": {"days": 30},
                "reason": "快速证据超过三十天后刷新。",
            },
        ],
        "sources": [
            {
                "source_id": "filing",
                "tier": "S1",
                "title": "最新定期报告",
                "accessed_at": "2026-07-27T09:00:00+08:00",
                "url": "https://example.com/filing",
                "local_path": None,
                "supports": ["业务", "盈利"],
            },
            {
                "source_id": "quote",
                "tier": "S2",
                "title": "最新行情",
                "accessed_at": "2026-07-27T09:25:00+08:00",
                "url": "https://example.com/quote",
                "local_path": None,
                "supports": ["价格"],
            },
        ],
        "provenance": {
            "agent": "/root/company-600519",
            "model": "test-model",
            "tools": ["browser", "repository"],
            "generated_at": "2026-07-27T09:45:00+08:00",
        },
    }


def _seal_package(
    root: Path,
    package: dict,
    *,
    artifact_name: str = "result.triage.json",
    sealed_at: dt.datetime = SEALED_AT,
) -> Path:
    from trading_os.research_assets.sealing import seal_json

    path = (
        root
        / "coverage"
        / "cn-a"
        / "triage"
        / "2026-07-27-timeline-test"
        / "600519"
        / artifact_name
    )
    seal_json(
        path,
        package,
        artifact_type="rapid_triage_package",
        sealed_at=sealed_at,
    )
    return path


def test_sealed_rapid_triage_appends_company_timeline_and_is_idempotent(
    tmp_path: Path,
):
    from trading_os.research_assets.company import validate_company_dir
    from trading_os.research_assets.company_timeline import (
        publish_rapid_triage_to_company_timeline,
    )
    from trading_os.research_assets.sealing import verify_sealed

    company_dir = _make_rebaseline_company(tmp_path)
    package_path = _seal_package(tmp_path, _package())

    result = publish_rapid_triage_to_company_timeline(
        repository_root=tmp_path,
        package_path=package_path,
        published_at=PUBLISHED_AT,
    )

    assert result["symbol"] == "CN:600519"
    assert result["idempotent"] is False
    assert result["rebaseline_cleared"] is True
    assert result["trigger_count"] == 6
    assert result["company_report_path"].startswith(
        "research/companies/CN/600519/reports/2026-07-27-rapid-triage-"
    )
    meta = validate_company_dir(company_dir)
    assert meta["research"]["coverage_status"] == "covered"
    assert meta["research"]["rebaseline_required"] is False
    assert meta["research"]["information_cutoff"] == (
        "2026-07-27T09:30:00+08:00"
    )
    assert meta["research"]["refresh_due_at"] == (
        "2026-08-26T09:30:00+08:00"
    )
    assert meta["reports"]["latest_by_type"]["rapid_triage"] == (
        meta["reports"]["latest"]
    )
    assert len(meta["reports"]["history"]) == 2
    ttl = next(item for item in meta["triggers"] if item["trigger_id"] == "evidence-ttl")
    assert ttl["type"] == "date"
    assert ttl["condition"] == {
        "due_at": "2026-08-26T09:30:00+08:00",
        "origin": "ttl",
    }
    source_manifest = tmp_path / result["source_manifest_path"]
    assert verify_sealed(source_manifest).artifact_type == (
        "rapid_triage_source_manifest"
    )

    repeated = publish_rapid_triage_to_company_timeline(
        repository_root=tmp_path,
        package_path=package_path,
        published_at=PUBLISHED_AT + dt.timedelta(minutes=5),
    )
    assert repeated["idempotent"] is True
    assert repeated["report_id"] == result["report_id"]
    assert len(validate_company_dir(company_dir)["reports"]["history"]) == 2


def test_historical_rapid_triage_replay_is_idempotent_without_rolling_back_state(
    tmp_path: Path,
):
    from trading_os.research_assets.company import validate_company_dir
    from trading_os.research_assets.company_timeline import (
        publish_rapid_triage_to_company_timeline,
    )

    company_dir = _make_rebaseline_company(tmp_path)
    package_a_path = _seal_package(
        tmp_path,
        _package(),
        artifact_name="result-a.triage.json",
    )
    result_a = publish_rapid_triage_to_company_timeline(
        repository_root=tmp_path,
        package_path=package_a_path,
        published_at=PUBLISHED_AT,
    )

    package_b = _package(review_mode="triggered_update")
    package_b.update(
        {
            "cycle_id": "2026-07-28-timeline-test",
            "as_of": "2026-07-28",
            "information_cutoff": "2026-07-28T09:30:00+08:00",
            "price_as_of": "2026-07-28T09:25:00+08:00",
        }
    )
    package_b_path = _seal_package(
        tmp_path,
        package_b,
        artifact_name="result-b.triage.json",
        sealed_at=SEALED_AT + dt.timedelta(days=1),
    )
    result_b = publish_rapid_triage_to_company_timeline(
        repository_root=tmp_path,
        package_path=package_b_path,
        published_at=PUBLISHED_AT + dt.timedelta(days=1),
    )
    before = {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }

    replayed = publish_rapid_triage_to_company_timeline(
        repository_root=tmp_path,
        package_path=package_a_path,
        published_at=PUBLISHED_AT + dt.timedelta(days=2),
    )

    after = {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    meta = validate_company_dir(company_dir)
    assert replayed["idempotent"] is True
    assert replayed["report_id"] == result_a["report_id"]
    assert replayed["company_report_path"] == result_a["company_report_path"]
    assert replayed["source_manifest_path"] == result_a["source_manifest_path"]
    assert replayed["source_package_sha256"] == result_a["source_package_sha256"]
    assert meta["research"]["latest_rapid_triage"]["report_id"] == result_b["report_id"]
    assert meta["reports"]["latest"] == result_b["company_report_path"].split(
        "research/companies/CN/600519/", 1
    )[1]
    assert len(meta["reports"]["history"]) == 3
    assert after == before


def test_historical_rapid_triage_replay_rejects_damaged_manifest(tmp_path: Path):
    from trading_os.research_assets.company import AssetValidationError
    from trading_os.research_assets.company_timeline import (
        publish_rapid_triage_to_company_timeline,
    )

    _make_rebaseline_company(tmp_path)
    package_a_path = _seal_package(
        tmp_path,
        _package(),
        artifact_name="result-a.triage.json",
    )
    result_a = publish_rapid_triage_to_company_timeline(
        repository_root=tmp_path,
        package_path=package_a_path,
        published_at=PUBLISHED_AT,
    )
    package_b = _package(review_mode="triggered_update")
    package_b.update(
        {
            "cycle_id": "2026-07-28-timeline-test",
            "as_of": "2026-07-28",
            "information_cutoff": "2026-07-28T09:30:00+08:00",
            "price_as_of": "2026-07-28T09:25:00+08:00",
        }
    )
    package_b_path = _seal_package(
        tmp_path,
        package_b,
        artifact_name="result-b.triage.json",
        sealed_at=SEALED_AT + dt.timedelta(days=1),
    )
    publish_rapid_triage_to_company_timeline(
        repository_root=tmp_path,
        package_path=package_b_path,
        published_at=PUBLISHED_AT + dt.timedelta(days=1),
    )
    manifest_path = tmp_path / result_a["source_manifest_path"]
    manifest_path.write_text("{}\n", encoding="utf-8")

    with pytest.raises(AssetValidationError, match="source manifest"):
        publish_rapid_triage_to_company_timeline(
            repository_root=tmp_path,
            package_path=package_a_path,
            published_at=PUBLISHED_AT + dt.timedelta(days=2),
        )


def test_company_validator_detects_broken_rapid_triage_source_link(tmp_path: Path):
    from trading_os.research_assets.company import (
        AssetValidationError,
        validate_company_dir,
    )
    from trading_os.research_assets.company_timeline import (
        publish_rapid_triage_to_company_timeline,
    )

    company_dir = _make_rebaseline_company(tmp_path)
    package_path = _seal_package(tmp_path, _package())
    publish_rapid_triage_to_company_timeline(
        repository_root=tmp_path,
        package_path=package_path,
        published_at=PUBLISHED_AT,
    )
    package_path.write_text("{}", encoding="utf-8")

    with pytest.raises(AssetValidationError, match="source package"):
        validate_company_dir(company_dir)


def test_schedule_and_alerts_consume_rapid_triage_refresh_state(tmp_path: Path):
    from trading_os.research_assets.alerts import (
        build_price_alerts,
        evaluate_price_alerts,
    )
    from trading_os.research_assets.company_timeline import (
        publish_rapid_triage_to_company_timeline,
    )
    from trading_os.research_assets.schedule import build_review_schedule

    _make_rebaseline_company(tmp_path)
    package_path = _seal_package(tmp_path, _package())
    publish_rapid_triage_to_company_timeline(
        repository_root=tmp_path,
        package_path=package_path,
        published_at=PUBLISHED_AT,
    )

    schedule = build_review_schedule(tmp_path / "research")
    assert all(item["type"] != "rebaseline" for item in schedule["items"])
    assert all(item["source"] != "conclusion_invalidation" for item in schedule["items"])
    assert {item["state"] for item in schedule["items"]} == {
        "watching",
        "scheduled",
    }
    assert any(
        item["trigger_id"] == "evidence-ttl"
        and item["condition"]["due_at"] == "2026-08-26T09:30:00+08:00"
        for item in schedule["items"]
    )
    assert not any(
        item["source"] == "research_refresh_due" for item in schedule["items"]
    )

    alerts = build_price_alerts(tmp_path / "research")
    assert alerts["item_count"] == 1
    assert alerts["items"][0]["type"] == "research_price_trigger"
    triggered = evaluate_price_alerts(
        alerts,
        [
            {
                "symbol": "CN:600519",
                "price": 79.0,
                "as_of": "2026-07-27T15:00:00+08:00",
            }
        ],
        evaluated_at=dt.datetime.fromisoformat("2026-07-27T15:00:00+08:00"),
    )
    assert triggered["triggered_count"] == 1
    assert triggered["triggered"][0]["type"] == "research_price_trigger"


def test_v1_package_requires_explicit_review_mode(tmp_path: Path):
    from trading_os.research_assets.company_timeline import (
        CompanyTimelineError,
        publish_rapid_triage_to_company_timeline,
    )

    _make_rebaseline_company(tmp_path)
    package = _package()
    package["schema_version"] = 1
    package.pop("review_mode")
    package["revisit_triggers"] = []
    path = _seal_package(tmp_path, package)

    with pytest.raises(CompanyTimelineError, match="explicit review_mode"):
        publish_rapid_triage_to_company_timeline(
            repository_root=tmp_path,
            package_path=path,
            published_at=PUBLISHED_AT,
        )


def test_triggered_update_does_not_silently_clear_pending_rebaseline(tmp_path: Path):
    from trading_os.research_assets.company import validate_company_dir
    from trading_os.research_assets.company_timeline import (
        publish_rapid_triage_to_company_timeline,
    )

    company_dir = _make_rebaseline_company(tmp_path)
    path = _seal_package(tmp_path, _package(review_mode="triggered_update"))

    result = publish_rapid_triage_to_company_timeline(
        repository_root=tmp_path,
        package_path=path,
        published_at=PUBLISHED_AT,
    )

    meta = validate_company_dir(company_dir)
    assert result["rebaseline_cleared"] is False
    assert meta["research"]["rebaseline_required"] is True
    assert meta["research"]["coverage_status"] == "requires_rebaseline"
