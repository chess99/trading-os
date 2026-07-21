from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

import pytest

NOW = dt.datetime(2026, 7, 21, 12, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))


def _legacy_company(
    tmp_path: Path,
    ticker: str = "600519",
    *,
    name: str = "贵州茅台",
) -> Path:
    company_dir = tmp_path / "research" / "companies" / "CN" / ticker
    reports = company_dir / "reports"
    reports.mkdir(parents=True)
    (reports / "2026-07-01-initial.md").write_text(
        f"# 公司研究：{name}（CN:{ticker}）\n\n旧报告一。\n", encoding="utf-8"
    )
    (reports / "2026-07-15-followup.md").write_text(
        f"# 公司研究：{name}（CN:{ticker}）\n\n旧报告二。\n", encoding="utf-8"
    )
    meta = {
        "symbol": f"CN:{ticker}",
        "market": "CN",
        "ticker": ticker,
        "name": name,
        "currency": "CNY",
        "status": "active",
        "current_rating": "buy",
        "current_thesis": "旧结论",
        "fair_value_range": [100.0, 120.0],
        "buy_zone": [80.0, 90.0],
        "sell_or_reduce_zone": [130.0, 140.0],
        "position_plan": [{"condition": "旧计划", "max_weight": 0.05}],
        "latest_report": "reports/2026-07-15-followup.md",
        "report_history": [
            "reports/2026-07-01-initial.md",
            "reports/2026-07-15-followup.md",
        ],
        "review_triggers": [
            {"type": "date", "date": "2026-08-31", "reason": "半年报复核"}
        ],
        "price_triggers": [
            {"type": "price_below", "price": 90.0, "reason": "旧买入提醒"}
        ],
        "updated_at": "2026-07-15T15:00:00+08:00",
    }
    (company_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return company_dir


def _tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _plan(tmp_path: Path, migration_id: str = "v2-reset"):
    from trading_os.research_assets.migration import build_migration_plan

    return build_migration_plan(
        tmp_path / "research",
        migration_id=migration_id,
        created_at=NOW,
    )


def test_dry_run_scans_legacy_assets_without_writing(tmp_path: Path):
    _legacy_company(tmp_path)
    before = _tree_hashes(tmp_path)

    plan = _plan(tmp_path)

    assert _tree_hashes(tmp_path) == before
    assert plan["company_count"] == 1
    assert plan["migrate_count"] == 1
    assert plan["error_count"] == 0
    assert len(plan["plan_sha256"]) == 64
    company = plan["companies"][0]
    assert company["action"] == "migrate"
    assert company["reason_codes"] == ["legacy_reports_require_structured_rebaseline"]


def test_apply_archives_legacy_meta_and_converts_without_fabricating_judgment(
    tmp_path: Path,
):
    from trading_os.research_assets.company import validate_company_dir
    from trading_os.research_assets.migration import apply_migration_plan
    from trading_os.research_assets.sealing import verify_sealed

    company_dir = _legacy_company(tmp_path)
    original_reports = _tree_hashes(company_dir / "reports")
    plan = _plan(tmp_path)

    result = apply_migration_plan(plan)

    assert result["applied_count"] == 1
    assert result["failed_count"] == 0
    assert _tree_hashes(company_dir / "reports") == original_reports
    meta = validate_company_dir(company_dir)
    assert meta["identity"]["symbol"] == "CN:600519"
    assert meta["research"] == {
        "coverage_status": "requires_rebaseline",
        "rebaseline_required": True,
        "information_cutoff": None,
    }
    assert meta["reports"]["latest"] is None
    assert meta["reports"]["history"] == []
    assert len(meta["reports"]["historical_artifacts"]) == 2
    assert meta["underwriting"]["status"] is None
    assert meta["valuation"]["fair_value_range"] is None
    assert "current_rating" not in meta
    assert "position_plan" not in meta

    snapshot = (
        tmp_path
        / "research"
        / "migrations"
        / "v2-reset"
        / "companies"
        / "CN"
        / "600519"
        / "legacy-meta.json"
    )
    assert verify_sealed(snapshot).artifact_type == "legacy_company_meta"
    legacy = json.loads(snapshot.read_text(encoding="utf-8"))
    assert legacy["current_rating"] == "buy"


def test_apply_rejects_tampered_plan_hash(tmp_path: Path):
    from trading_os.research_assets.migration import MigrationError, apply_migration_plan

    _legacy_company(tmp_path)
    plan = _plan(tmp_path)
    plan["migration_id"] = "tampered"

    with pytest.raises(MigrationError, match="sha256"):
        apply_migration_plan(plan)


def test_apply_rejects_source_changes_after_dry_run(tmp_path: Path):
    from trading_os.research_assets.migration import apply_migration_plan

    company_dir = _legacy_company(tmp_path)
    plan = _plan(tmp_path)
    meta_path = company_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["name"] = "源文件已变化"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")

    result = apply_migration_plan(plan)

    assert result["failed_count"] == 1
    assert "fingerprint changed" in result["results"][0]["reason"]
    assert "schema_version" not in json.loads(meta_path.read_text(encoding="utf-8"))


def test_interrupted_apply_is_resumable_and_idempotent(tmp_path: Path, monkeypatch):
    import trading_os.research_assets.migration as migration

    first = _legacy_company(tmp_path, "600519", name="贵州茅台")
    second = _legacy_company(tmp_path, "000001", name="平安银行")
    plan = _plan(tmp_path)
    real_write = migration.atomic_write_bytes
    failed_once = False

    def fail_one_meta(path, data):
        nonlocal failed_once
        target = Path(path)
        if target == second / "meta.json" and not failed_once:
            failed_once = True
            raise OSError("simulated interruption")
        return real_write(path, data)

    monkeypatch.setattr(migration, "atomic_write_bytes", fail_one_meta)
    first_result = migration.apply_migration_plan(plan)
    assert first_result["applied_count"] == 1
    assert first_result["failed_count"] == 1
    assert json.loads((first / "meta.json").read_text(encoding="utf-8"))["schema_version"] == 2
    assert "schema_version" not in json.loads(
        (second / "meta.json").read_text(encoding="utf-8")
    )

    second_result = migration.apply_migration_plan(plan)
    third_result = migration.apply_migration_plan(plan)

    assert second_result["applied_count"] == 1
    assert second_result["already_applied_count"] == 1
    assert second_result["failed_count"] == 0
    assert third_result["already_applied_count"] == 2
    assert third_result["failed_count"] == 0


def test_scan_records_malformed_company_as_structured_blocker(tmp_path: Path):
    company_dir = tmp_path / "research" / "companies" / "CN" / "000001"
    company_dir.mkdir(parents=True)
    (company_dir / "meta.json").write_text("{broken", encoding="utf-8")

    plan = _plan(tmp_path)

    assert plan["error_count"] == 1
    assert plan["companies"][0]["action"] == "error"
    assert plan["companies"][0]["reason_codes"] == ["migration_scan_failed"]
    assert plan["companies"][0]["error"]


def test_plan_file_round_trip_requires_matching_hash(tmp_path: Path):
    from trading_os.research_assets.migration import (
        load_migration_plan,
        write_migration_plan,
    )

    _legacy_company(tmp_path)
    plan = _plan(tmp_path)
    path = tmp_path / "migration-plan.json"

    write_migration_plan(path, plan)

    assert load_migration_plan(path) == plan


def test_cli_dry_run_and_apply_use_the_same_hashed_plan(tmp_path: Path, capsys):
    from trading_os.cli import main

    _legacy_company(tmp_path)
    plan_path = tmp_path / "migration-plan.json"
    dry_code = main(
        [
            "assets",
            "migrate",
            "--dry-run",
            "--research-root",
            str(tmp_path / "research"),
            "--migration-id",
            "v2-reset",
            "--at",
            NOW.isoformat(),
            "--output",
            str(plan_path),
        ]
    )
    assert dry_code == 0
    dry_payload = json.loads(capsys.readouterr().out)
    assert dry_payload["plan_sha256"]

    apply_code = main(["assets", "migrate", "--apply", "--plan", str(plan_path)])

    assert apply_code == 0
    result = json.loads(capsys.readouterr().out)
    assert result["plan_sha256"] == dry_payload["plan_sha256"]
    assert result["applied_count"] == 1
