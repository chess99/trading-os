from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

import pytest

REPORT_SECTIONS = {
    "initial_research": [
        "结论版",
        "业务理解",
        "行业与竞争格局",
        "公司质量",
        "财务质量",
        "结构化主张",
        "估值",
        "市场隐含预期",
        "情景与赔率",
        "关键假设",
        "跟踪触发器",
        "风险",
        "来源",
    ],
    "monitoring_update": [
        "上一轮判断复盘",
        "新信息",
        "判断变化",
        "证据更新",
        "跟踪触发器",
        "风险",
        "来源",
    ],
    "underwriting_review": [
        "承保结论",
        "证据账本",
        "盈利质量桥",
        "现金流桥",
        "正常化盈利",
        "估值与敏感性",
        "市场隐含预期",
        "反方证据",
        "旧主张差异审计",
        "自动阻断检查",
        "失效条件",
        "来源",
    ],
    "challenger_review": [
        "独立挑战结论",
        "证据账本",
        "盈利质量桥",
        "现金流桥",
        "正常化盈利",
        "估值与敏感性",
        "反方证据",
        "争议点",
        "失效条件",
        "来源",
    ],
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_report(
    company_dir: Path,
    *,
    report_type: str = "initial_research",
    date: str = "2026-07-21",
    report_id: str | None = None,
    missing_section: str | None = None,
    metadata_overrides: dict[str, object] | None = None,
) -> tuple[Path, dict[str, object]]:
    report_id = report_id or f"CN-600519-{date}-{report_type}"
    slug = report_type.replace("_", "-")
    report_path = company_dir / "reports" / f"{date}-{slug}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    source_manifest = company_dir / "evidence" / f"{report_id}-sources.json"
    source_manifest.parent.mkdir(parents=True, exist_ok=True)
    source_manifest.write_text(
        json.dumps({"schema_version": 2, "sources": []}) + "\n",
        encoding="utf-8",
    )
    metadata: dict[str, object] = {
        "schema_version": 2,
        "report_id": report_id,
        "report_type": report_type,
        "symbol": "CN:600519",
        "as_of": date,
        "information_cutoff": f"{date}T15:00:00+08:00",
        "price_snapshot_id": None,
        "policy_versions": {"underwriting": "1.0.0"},
        "agent_id": "codex-test-fixture",
        "predecessor_reports": [],
        "sealed_artifacts": [],
        "source_manifest": source_manifest.relative_to(company_dir).as_posix(),
    }
    metadata.update(metadata_overrides or {})
    sections = [
        heading
        for heading in REPORT_SECTIONS.get(report_type, REPORT_SECTIONS["initial_research"])
        if heading != missing_section
    ]
    body = "\n".join(f"## {heading}\n\n测试内容。\n" for heading in sections)
    report_path.write_text(
        "<!-- trading-os-report-meta\n"
        + json.dumps(metadata, ensure_ascii=False, indent=2)
        + "\n-->\n"
        + "# 公司研究：贵州茅台（CN:600519）\n\n"
        + body,
        encoding="utf-8",
    )
    return report_path, metadata


def write_company(
    root: Path,
    *,
    report_type: str = "initial_research",
    date: str = "2026-07-21",
) -> Path:
    company_dir = root / "research" / "companies" / "CN" / "600519"
    report_path, report_meta = _write_report(
        company_dir,
        report_type=report_type,
        date=date,
    )
    report_rel = report_path.relative_to(company_dir).as_posix()
    meta = {
        "schema_version": 2,
        "identity": {
            "symbol": "CN:600519",
            "market": "CN",
            "ticker": "600519",
            "name": "贵州茅台",
            "currency": "CNY",
            "security_status": "active",
        },
        "research": {
            "coverage_status": "covered",
            "rebaseline_required": False,
            "information_cutoff": f"{date}T15:00:00+08:00",
        },
        "reports": {
            "latest": report_rel,
            "latest_by_type": {report_type: report_rel},
            "history": [
                {
                    "report_id": report_meta["report_id"],
                    "path": report_rel,
                    "report_type": report_type,
                    "as_of": date,
                    "sha256": _sha256(report_path),
                }
            ],
            "historical_artifacts": [],
        },
        "underwriting": {
            "status": None,
            "review_id": None,
            "confidence": None,
            "evidence_valid_until": None,
            "reason_codes": [],
        },
        "valuation": {
            "currency": None,
            "price_as_of": None,
            "bear_value": None,
            "fair_value_range": None,
            "buy_zone": None,
            "reduce_zone": None,
        },
        "triggers": [
            {
                "trigger_id": "next-filing",
                "type": "filing",
                "condition": {"filing_type": "interim_report"},
                "reason": "半年报披露后重新核验证据。",
                "active": True,
            }
        ],
        "updated_at": f"{date}T15:00:00+08:00",
    }
    (company_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return company_dir


def write_strict_company(root: Path) -> Path:
    return write_company(root)


def _load_meta(company_dir: Path) -> dict[str, object]:
    return json.loads((company_dir / "meta.json").read_text(encoding="utf-8"))


def _write_meta(company_dir: Path, meta: dict[str, object]) -> None:
    (company_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def test_valid_v2_company_asset_loads(tmp_path: Path):
    from trading_os.research_assets.company import validate_company_dir

    company_dir = write_company(tmp_path)

    meta = validate_company_dir(company_dir)

    assert meta["schema_version"] == 2
    assert meta["identity"]["symbol"] == "CN:600519"


def test_v1_company_asset_is_rejected_with_migration_message(tmp_path: Path):
    from trading_os.research_assets.company import AssetValidationError, validate_company_dir

    company_dir = write_company(tmp_path)
    meta = _load_meta(company_dir)
    meta["schema_version"] = 1
    _write_meta(company_dir, meta)

    with pytest.raises(AssetValidationError, match="migrate"):
        validate_company_dir(company_dir)


@pytest.mark.parametrize("field", ["current_rating", "position_plan", "buy_zone"])
def test_portfolio_decision_fields_are_forbidden_in_company_meta(
    tmp_path: Path, field: str
):
    from trading_os.research_assets.company import AssetValidationError, validate_company_dir

    company_dir = write_company(tmp_path)
    meta = _load_meta(company_dir)
    meta[field] = "forbidden"
    _write_meta(company_dir, meta)

    with pytest.raises(AssetValidationError, match="unknown meta fields"):
        validate_company_dir(company_dir)


def test_symbol_must_match_market_ticker_and_directory(tmp_path: Path):
    from trading_os.research_assets.company import AssetValidationError, validate_company_dir

    company_dir = write_company(tmp_path)
    meta = _load_meta(company_dir)
    meta["identity"]["symbol"] = "CN:000001"
    _write_meta(company_dir, meta)

    with pytest.raises(AssetValidationError, match="symbol"):
        validate_company_dir(company_dir)


def test_report_hash_mismatch_is_rejected(tmp_path: Path):
    from trading_os.research_assets.company import AssetValidationError, validate_company_dir

    company_dir = write_company(tmp_path)
    report = next((company_dir / "reports").glob("*.md"))
    report.write_text(report.read_text(encoding="utf-8") + "\n篡改。\n", encoding="utf-8")

    with pytest.raises(AssetValidationError, match="sha256"):
        validate_company_dir(company_dir)


def test_latest_report_must_be_in_history(tmp_path: Path):
    from trading_os.research_assets.company import AssetValidationError, validate_company_dir

    company_dir = write_company(tmp_path)
    meta = _load_meta(company_dir)
    meta["reports"]["latest"] = "reports/2026-07-22-monitoring-update.md"
    _write_meta(company_dir, meta)

    with pytest.raises(AssetValidationError, match="latest"):
        validate_company_dir(company_dir)


def test_latest_by_type_must_match_report_record_type(tmp_path: Path):
    from trading_os.research_assets.company import AssetValidationError, validate_company_dir

    company_dir = write_company(tmp_path)
    meta = _load_meta(company_dir)
    path = meta["reports"]["latest"]
    meta["reports"]["latest_by_type"] = {"monitoring_update": path}
    _write_meta(company_dir, meta)

    with pytest.raises(AssetValidationError, match="latest_by_type"):
        validate_company_dir(company_dir)


def test_report_metadata_type_must_match_history(tmp_path: Path):
    from trading_os.research_assets.company import AssetValidationError, validate_company_dir

    company_dir = write_company(tmp_path)
    report = next((company_dir / "reports").glob("*.md"))
    text = report.read_text(encoding="utf-8").replace(
        '"report_type": "initial_research"',
        '"report_type": "monitoring_update"',
    )
    report.write_text(text, encoding="utf-8")
    meta = _load_meta(company_dir)
    meta["reports"]["history"][0]["sha256"] = _sha256(report)
    _write_meta(company_dir, meta)

    with pytest.raises(AssetValidationError, match="report_type"):
        validate_company_dir(company_dir)


def test_report_requires_machine_readable_front_metadata(tmp_path: Path):
    from trading_os.research_assets.company import AssetValidationError, validate_company_dir

    company_dir = write_company(tmp_path)
    report = next((company_dir / "reports").glob("*.md"))
    report.write_text("# 无元数据报告\n", encoding="utf-8")
    meta = _load_meta(company_dir)
    meta["reports"]["history"][0]["sha256"] = _sha256(report)
    _write_meta(company_dir, meta)

    with pytest.raises(AssetValidationError, match="front metadata"):
        validate_company_dir(company_dir)


@pytest.mark.parametrize("report_type", sorted(REPORT_SECTIONS))
def test_each_v2_report_type_accepts_its_required_sections(
    tmp_path: Path, report_type: str
):
    from trading_os.research_assets.company import validate_company_dir

    company_dir = write_company(tmp_path, report_type=report_type)

    assert validate_company_dir(company_dir)["reports"]["history"][0][
        "report_type"
    ] == report_type


@pytest.mark.parametrize("report_type", sorted(REPORT_SECTIONS))
def test_each_v2_report_type_rejects_a_missing_required_section(
    tmp_path: Path, report_type: str
):
    from trading_os.research_assets.company import AssetValidationError, validate_company_dir

    company_dir = write_company(tmp_path, report_type=report_type)
    report = next((company_dir / "reports").glob("*.md"))
    missing = REPORT_SECTIONS[report_type][0]
    report.write_text(
        report.read_text(encoding="utf-8").replace(f"## {missing}\n", ""),
        encoding="utf-8",
    )
    meta = _load_meta(company_dir)
    meta["reports"]["history"][0]["sha256"] = _sha256(report)
    _write_meta(company_dir, meta)

    with pytest.raises(AssetValidationError, match="required section"):
        validate_company_dir(company_dir)


def test_old_report_can_be_preserved_as_unparsed_historical_artifact(tmp_path: Path):
    from trading_os.research_assets.company import validate_company_dir

    company_dir = write_company(tmp_path)
    legacy = company_dir / "reports" / "2025-12-31-initial.md"
    legacy.write_text("旧格式，可以没有新版章节。\n", encoding="utf-8")
    meta = _load_meta(company_dir)
    meta["reports"]["historical_artifacts"].append(
        {
            "path": legacy.relative_to(company_dir).as_posix(),
            "format": "legacy_v1",
            "sha256": _sha256(legacy),
        }
    )
    _write_meta(company_dir, meta)

    validated = validate_company_dir(company_dir)

    assert validated["reports"]["historical_artifacts"][0]["format"] == "legacy_v1"


def test_report_path_cannot_escape_company_directory(tmp_path: Path):
    from trading_os.research_assets.company import AssetValidationError, validate_company_dir

    company_dir = write_company(tmp_path)
    meta = _load_meta(company_dir)
    meta["reports"]["history"][0]["path"] = "reports/../../outside.md"
    _write_meta(company_dir, meta)

    with pytest.raises(AssetValidationError, match="report path"):
        validate_company_dir(company_dir)


def test_report_history_must_be_chronological(tmp_path: Path):
    from trading_os.research_assets.company import AssetValidationError, validate_company_dir

    company_dir = write_company(tmp_path, date="2026-07-21")
    report, report_meta = _write_report(
        company_dir,
        report_type="monitoring_update",
        date="2026-07-20",
    )
    meta = _load_meta(company_dir)
    meta["reports"]["history"].append(
        {
            "report_id": report_meta["report_id"],
            "path": report.relative_to(company_dir).as_posix(),
            "report_type": "monitoring_update",
            "as_of": "2026-07-20",
            "sha256": _sha256(report),
        }
    )
    _write_meta(company_dir, meta)

    with pytest.raises(AssetValidationError, match="chronological"):
        validate_company_dir(company_dir)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("fair_value_range", [1450, 1150]),
        ("buy_zone", [True, 1100]),
        ("reduce_zone", [1500]),
    ],
)
def test_valuation_ranges_must_be_ordered_numeric_pairs(
    tmp_path: Path, field: str, value: object
):
    from trading_os.research_assets.company import AssetValidationError, validate_company_dir

    company_dir = write_company(tmp_path)
    meta = _load_meta(company_dir)
    meta["valuation"][field] = value
    _write_meta(company_dir, meta)

    with pytest.raises(AssetValidationError, match=field):
        validate_company_dir(company_dir)


def test_datetime_fields_require_timezone_offsets(tmp_path: Path):
    from trading_os.research_assets.company import AssetValidationError, validate_company_dir

    company_dir = write_company(tmp_path)
    meta = _load_meta(company_dir)
    meta["updated_at"] = dt.datetime(2026, 7, 21, 15, 0).isoformat()
    _write_meta(company_dir, meta)

    with pytest.raises(AssetValidationError, match="UTC offset"):
        validate_company_dir(company_dir)


def test_validate_research_assets_reports_invalid_companies(tmp_path: Path):
    from trading_os.research_assets.company import validate_research_assets

    company_dir = write_company(tmp_path)
    meta = _load_meta(company_dir)
    meta["schema_version"] = 1
    _write_meta(company_dir, meta)

    result = validate_research_assets(tmp_path / "research")

    assert result["schema_version"] == 2
    assert result["company_count"] == 1
    assert result["valid_count"] == 0
    assert result["invalid_count"] == 1
    assert "migrate" in result["errors"][0]["error"]


def test_research_assets_star_import_exports_v2_validation():
    namespace: dict[str, object] = {}

    exec("from trading_os.research_assets import *", namespace)

    assert "AssetValidationError" in namespace
    assert "validate_company_dir" in namespace
    assert "validate_research_assets" in namespace
    assert "audit_research_assets" not in namespace
