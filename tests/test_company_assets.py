from __future__ import annotations

import json
from pathlib import Path

import pytest


def write_company(root: Path, *, rating: str = "watch") -> Path:
    company_dir = root / "research" / "companies" / "CN" / "600519"
    reports = company_dir / "reports"
    reports.mkdir(parents=True)
    report_path = reports / "2026-07-06-initial.md"
    report_path.write_text(
        "# Company Research: 贵州茅台 (CN:600519)\n\n"
        "Date: 2026-07-06\n"
        "Research Type: initial\n"
        "Analyst: Test Fixture + model unknown\n\n"
        "## One-line Conclusion\n\n"
        "High-quality cash compounder with valuation discipline required.\n\n"
        "## Decision\n\n"
        "Watch.\n\n"
        "## Business Understanding\n\n"
        "Premium baijiu producer.\n\n"
        "## Industry and Competitive Context\n\n"
        "High-end baijiu remains concentrated.\n\n"
        "## Company Quality\n\n"
        "Wide moat.\n\n"
        "## Financial Quality\n\n"
        "High margins and strong cash flow.\n\n"
        "## Valuation\n\n"
        "Fair value range is 1150-1450 CNY.\n\n"
        "## Price and Position Plan\n\n"
        "Initial buy zone is 1000-1100 CNY.\n\n"
        "## Key Assumptions\n\n"
        "- Premium demand remains resilient.\n\n"
        "## Follow-up Triggers\n\n"
        "- Review after semiannual report.\n\n"
        "## Risks\n\n"
        "- Demand weakness.\n\n"
        "## Previous Thesis Review\n\n"
        "No previous report exists.\n\n"
        "## Sources\n\n"
        "- Company filings.\n",
        encoding="utf-8",
    )
    meta = {
        "symbol": "CN:600519",
        "market": "CN",
        "ticker": "600519",
        "name": "贵州茅台",
        "currency": "CNY",
        "status": "active",
        "current_rating": rating,
        "current_thesis": "High-quality cash compounder.",
        "fair_value_range": [1150, 1450],
        "buy_zone": [1000, 1100],
        "sell_or_reduce_zone": [1500, 1800],
        "position_plan": [
            {"condition": "price <= 1150", "max_weight": 0.05},
            {"condition": "price <= 1000", "max_weight": 0.12},
        ],
        "latest_report": "reports/2026-07-06-initial.md",
        "report_history": ["reports/2026-07-06-initial.md"],
        "review_triggers": [
            {"type": "date", "date": "2026-08-31", "reason": "Semiannual review."}
        ],
        "price_triggers": [
            {"type": "price_below", "price": 1100, "reason": "Enter buy zone."}
        ],
        "updated_at": "2026-07-06T00:00:00+08:00",
    }
    (company_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return company_dir


def write_strict_company(root: Path) -> Path:
    company_dir = write_company(root)
    report_path = company_dir / "reports" / "2026-07-06-initial.md"
    report_path.write_text(
        "# 公司研究：贵州茅台（CN:600519）\n"
        "日期：2026-07-06\n"
        "研究类型：initial\n"
        "分析师：Codex + GPT-5\n\n"
        "## 结论版\n\n"
        "### 一句话结论\n\n"
        "贵州茅台是高质量现金流资产，但买入必须等待安全边际。\n\n"
        "## 业务理解\n\n"
        "公司销售高端白酒，核心利润来自飞天茅台。\n\n"
        "## 行业与竞争格局\n\n"
        "高端白酒集中度高，品牌和渠道壁垒明显。\n\n"
        "## 公司质量\n\n"
        "品牌护城河强，现金转换质量高。\n\n"
        "## 财务质量\n\n"
        "利润率和自由现金流质量长期领先。\n\n"
        "## 估值\n\n"
        "合理价值区间为 1150-1450 元。\n\n"
        "## 市场隐含预期\n\n"
        "当前价格隐含稳健增长和利润率维持。\n\n"
        "## 情景与赔率\n\n"
        "基准情景赔率一般，低价区间赔率改善。\n\n"
        "## 价格与仓位计划\n\n"
        "买入区间为 1000-1100 元，减仓区间为 1500-1800 元。\n\n"
        "## 关键假设\n\n"
        "- 高端白酒需求保持韧性。\n\n"
        "## 跟踪触发器\n\n"
        "- 半年报后复盘收入和现金流。\n\n"
        "## 风险\n\n"
        "- 需求走弱或渠道库存恶化。\n\n"
        "## 上一轮判断复盘\n\n"
        "初始报告，无上一轮判断。\n\n"
        "## 来源\n\n"
        "- 公司公告。\n",
        encoding="utf-8",
    )
    meta_path = company_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["name"] = "贵州茅台"
    meta["current_thesis"] = "高质量现金流资产，但需要估值纪律。"
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return company_dir


def test_valid_company_asset_loads(tmp_path: Path):
    from trading_os.research_assets.company import validate_company_dir

    company_dir = write_company(tmp_path)

    meta = validate_company_dir(company_dir)

    assert meta["symbol"] == "CN:600519"
    assert meta["latest_report"] == "reports/2026-07-06-initial.md"


def test_strict_company_asset_accepts_standard_chinese_report(tmp_path: Path):
    from trading_os.research_assets.company import validate_company_dir

    company_dir = write_strict_company(tmp_path)

    meta = validate_company_dir(company_dir, strict=True)

    assert meta["symbol"] == "CN:600519"


def test_strict_company_asset_warns_on_untraceable_analyst(tmp_path: Path):
    from trading_os.research_assets.company import (
        audit_research_assets,
        validate_company_dir,
    )

    company_dir = write_strict_company(tmp_path)
    report_path = company_dir / "reports" / "2026-07-06-initial.md"
    report_path.write_text(
        report_path.read_text(encoding="utf-8").replace(
            "分析师：Codex + GPT-5",
            "分析师：agent",
        ),
        encoding="utf-8",
    )

    assert validate_company_dir(company_dir, strict=True)["symbol"] == "CN:600519"
    audit = audit_research_assets(tmp_path / "research")
    assert any("analyst" in item["error"] for item in audit["warnings"])


def test_strict_company_asset_rejects_missing_report_type(tmp_path: Path):
    from trading_os.research_assets.company import AssetValidationError, validate_company_dir

    company_dir = write_strict_company(tmp_path)
    report_path = company_dir / "reports" / "2026-07-06-initial.md"
    report_path.write_text(
        report_path.read_text(encoding="utf-8").replace("研究类型：initial\n", ""),
        encoding="utf-8",
    )

    with pytest.raises(AssetValidationError, match="research type"):
        validate_company_dir(company_dir, strict=True)


def test_strict_company_asset_rejects_missing_required_section(tmp_path: Path):
    from trading_os.research_assets.company import AssetValidationError, validate_company_dir

    company_dir = write_strict_company(tmp_path)
    report_path = company_dir / "reports" / "2026-07-06-initial.md"
    report_path.write_text(
        report_path.read_text(encoding="utf-8").replace("## 市场隐含预期", "## 市场预期"),
        encoding="utf-8",
    )

    with pytest.raises(AssetValidationError, match="section"):
        validate_company_dir(company_dir, strict=True)


def test_strict_company_asset_warns_on_extra_meta_keys(tmp_path: Path):
    from trading_os.research_assets.company import (
        audit_research_assets,
        validate_company_dir,
    )

    company_dir = write_strict_company(tmp_path)
    meta_path = company_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["current_price"] = 1200
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    assert validate_company_dir(company_dir, strict=True)["symbol"] == "CN:600519"
    audit = audit_research_assets(tmp_path / "research")
    assert any("extra meta" in item["error"] for item in audit["warnings"])


def test_strict_company_asset_warns_on_nonstandard_title(tmp_path: Path):
    from trading_os.research_assets.company import (
        audit_research_assets,
        validate_company_dir,
    )

    company_dir = write_strict_company(tmp_path)
    report_path = company_dir / "reports" / "2026-07-06-initial.md"
    report_path.write_text(
        report_path.read_text(encoding="utf-8").replace(
            "# 公司研究：贵州茅台（CN:600519）",
            "# 贵州茅台初始研究",
        ),
        encoding="utf-8",
    )

    assert validate_company_dir(company_dir, strict=True)["symbol"] == "CN:600519"
    audit = audit_research_assets(tmp_path / "research")
    assert any("report title" in item["error"] for item in audit["warnings"])


def _write_followup_company(tmp_path: Path, *, include_new_information: bool) -> Path:
    company_dir = write_strict_company(tmp_path)
    report_path = company_dir / "reports" / "2026-08-31-followup.md"
    sections = [
        ("上一轮判断复盘", "上一轮维持观察。"),
        ("判断变化", "估值区间保持不变。"),
        ("跟踪触发器", "等待三季报。"),
        ("风险", "需求恢复慢于预期。"),
        ("来源", "公司半年报。"),
    ]
    if include_new_information:
        sections.insert(1, ("新信息", "半年报收入保持增长。"))
    body = "".join(f"## {heading}\n\n{text}\n\n" for heading, text in sections)
    report_path.write_text(
        "# 公司研究：贵州茅台（CN:600519）\n"
        "日期：2026-08-31\n"
        "研究类型：followup\n"
        "分析师：Codex + GPT-5\n\n"
        + body,
        encoding="utf-8",
    )
    meta_path = company_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["latest_report"] = "reports/2026-08-31-followup.md"
    meta["report_history"].append(meta["latest_report"])
    meta["updated_at"] = "2026-08-31T00:00:00+08:00"
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return company_dir


def test_strict_followup_uses_followup_sections(tmp_path: Path):
    from trading_os.research_assets.company import validate_company_dir

    company_dir = _write_followup_company(tmp_path, include_new_information=True)

    assert validate_company_dir(company_dir, strict=True)["symbol"] == "CN:600519"


def test_strict_followup_rejects_missing_followup_section(tmp_path: Path):
    from trading_os.research_assets.company import AssetValidationError, validate_company_dir

    company_dir = _write_followup_company(tmp_path, include_new_information=False)

    with pytest.raises(AssetValidationError, match="section"):
        validate_company_dir(company_dir, strict=True)


def test_meta_json_with_utf8_bom_loads(tmp_path: Path):
    from trading_os.research_assets.company import validate_company_dir

    company_dir = write_company(tmp_path)
    meta_path = company_dir / "meta.json"
    text = meta_path.read_text(encoding="utf-8")
    meta_path.write_text("\ufeff" + text, encoding="utf-8")

    meta = validate_company_dir(company_dir)

    assert meta["symbol"] == "CN:600519"


def test_invalid_rating_is_rejected(tmp_path: Path):
    from trading_os.research_assets.company import AssetValidationError, validate_company_dir

    company_dir = write_company(tmp_path, rating="strong_buy")

    with pytest.raises(AssetValidationError, match="current_rating"):
        validate_company_dir(company_dir)


def test_symbol_must_match_market_and_ticker_fields(tmp_path: Path):
    from trading_os.research_assets.company import AssetValidationError, validate_company_dir

    company_dir = write_company(tmp_path)
    meta_path = company_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["symbol"] = "CN:000001"
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(AssetValidationError, match="symbol"):
        validate_company_dir(company_dir)


def test_company_directory_must_match_market_and_ticker(tmp_path: Path):
    from trading_os.research_assets.company import AssetValidationError, validate_company_dir

    company_dir = write_company(tmp_path)
    wrong_dir = tmp_path / "research" / "companies" / "CN" / "000001"
    wrong_dir.parent.mkdir(parents=True, exist_ok=True)
    company_dir.rename(wrong_dir)

    with pytest.raises(AssetValidationError, match="company directory"):
        validate_company_dir(wrong_dir)


def test_missing_latest_report_is_rejected(tmp_path: Path):
    from trading_os.research_assets.company import AssetValidationError, validate_company_dir

    company_dir = write_company(tmp_path)
    (company_dir / "reports" / "2026-07-06-initial.md").unlink()

    with pytest.raises(AssetValidationError, match="latest_report"):
        validate_company_dir(company_dir)


def test_latest_report_missing_from_report_history_is_rejected(tmp_path: Path):
    from trading_os.research_assets.company import AssetValidationError, validate_company_dir

    company_dir = write_company(tmp_path)
    second_report = company_dir / "reports" / "2026-08-31-h1-review.md"
    second_report.write_text("# H1 Review\n", encoding="utf-8")
    meta_path = company_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["latest_report"] = "reports/2026-08-31-h1-review.md"
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(AssetValidationError, match="latest_report"):
        validate_company_dir(company_dir)


def test_latest_report_absolute_path_outside_company_dir_is_rejected(tmp_path: Path):
    from trading_os.research_assets.company import AssetValidationError, validate_company_dir

    company_dir = write_company(tmp_path)
    outside_report = tmp_path / "outside.md"
    outside_report.write_text("# Outside\n", encoding="utf-8")
    meta_path = company_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["latest_report"] = str(outside_report)
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(AssetValidationError, match="latest_report"):
        validate_company_dir(company_dir)


def test_latest_report_outside_reports_is_rejected(tmp_path: Path):
    from trading_os.research_assets.company import AssetValidationError, validate_company_dir

    company_dir = write_company(tmp_path)
    sources = company_dir / "sources"
    sources.mkdir()
    (sources / "note.md").write_text("# Note\n", encoding="utf-8")
    meta_path = company_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["latest_report"] = "sources/note.md"
    meta["report_history"] = ["sources/note.md"]
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(AssetValidationError, match="latest_report"):
        validate_company_dir(company_dir)


def test_latest_report_without_report_date_is_rejected(tmp_path: Path):
    from trading_os.research_assets.company import AssetValidationError, validate_company_dir

    company_dir = write_company(tmp_path)
    (company_dir / "reports" / "not-a-date.md").write_text("# Bad\n", encoding="utf-8")
    meta_path = company_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["latest_report"] = "reports/not-a-date.md"
    meta["report_history"] = ["reports/not-a-date.md"]
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(AssetValidationError, match="latest_report"):
        validate_company_dir(company_dir)


def test_latest_report_directory_named_markdown_is_rejected(tmp_path: Path):
    from trading_os.research_assets.company import AssetValidationError, validate_company_dir

    company_dir = write_company(tmp_path)
    (company_dir / "reports" / "2026-07-06-dir.md").mkdir()
    meta_path = company_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["latest_report"] = "reports/2026-07-06-dir.md"
    meta["report_history"] = ["reports/2026-07-06-dir.md"]
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(AssetValidationError, match="report file"):
        validate_company_dir(company_dir)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("fair_value_range", [True, 1450], "fair_value_range"),
        ("position_plan", [{"condition": "price <= 1150", "max_weight": True}], "max_weight"),
        (
            "price_triggers",
            [{"type": "price_below", "price": True, "reason": "Enter buy zone."}],
            "price",
        ),
    ],
)
def test_boolean_numeric_values_are_rejected(
    tmp_path: Path, field: str, value: object, message: str
):
    from trading_os.research_assets.company import AssetValidationError, validate_company_dir

    company_dir = write_company(tmp_path)
    meta_path = company_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta[field] = value
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(AssetValidationError, match=message):
        validate_company_dir(company_dir)


def test_impossible_review_trigger_date_is_rejected(tmp_path: Path):
    from trading_os.research_assets.company import AssetValidationError, validate_company_dir

    company_dir = write_company(tmp_path)
    meta_path = company_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["review_triggers"] = [
        {"type": "date", "date": "2026-99-99", "reason": "Impossible date."}
    ]
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(AssetValidationError, match="review_triggers date"):
        validate_company_dir(company_dir)


def test_research_assets_star_import_succeeds():
    namespace: dict[str, object] = {}

    exec("from trading_os.research_assets import *", namespace)

    assert "AssetValidationError" in namespace
    assert "validate_company_dir" in namespace
