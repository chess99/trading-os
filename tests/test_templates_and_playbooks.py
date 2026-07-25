from __future__ import annotations

import json
from pathlib import Path

from tests.test_company_assets import REPORT_SECTIONS, write_company

ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_old_company_template_is_removed_and_four_v2_templates_exist():
    assert not (ROOT / "templates" / "company-report.md").exists()
    for name in (
        "initial-research-v2.md",
        "underwriting-review.md",
        "challenger-review.md",
        "portfolio-synthesis.md",
    ):
        assert (ROOT / "templates" / name).is_file()
    assert (ROOT / "templates" / "quick-profile.md").is_file()
    assert (ROOT / "templates" / "quick-profile.schema.json").is_file()


def test_company_report_templates_cover_validator_sections():
    mapping = {
        "initial_research": "initial-research-v2.md",
        "underwriting_review": "underwriting-review.md",
        "challenger_review": "challenger-review.md",
    }
    for report_type, template_name in mapping.items():
        text = _read(f"templates/{template_name}")
        for heading in REPORT_SECTIONS[report_type]:
            assert f"## {heading}" in text


def test_initial_research_produces_structured_claims_without_portfolio_decision():
    text = _read("templates/initial-research-v2.md")

    assert "research-claims.json" in text
    assert "claim_id" in text
    assert "验证指标" in text
    assert "证伪条件" in text
    assert "不得给组合操作或仓位" in text
    assert "最大仓位" not in text
    assert "建仓计划" not in text


def test_underwriting_template_locks_evidence_bridges_scenarios_and_blind_audit():
    text = _read("templates/underwriting-review.md")

    for phrase in (
        "证据账本",
        "盈利质量桥",
        "现金流桥",
        "正常化盈利",
        "悲观/基准/乐观三情景",
        "反方证据",
        "旧主张差异审计",
        "自动阻断检查",
        "盲态结果封存后才揭示",
        "safety_margin_tier",
    ):
        assert phrase in text


def test_portfolio_template_lists_every_required_user_decision_field():
    text = _read("templates/portfolio-synthesis.md")

    for phrase in (
        "当前价",
        "悲观价值",
        "合理价值区间",
        "买入区",
        "承保状态",
        "最终操作",
        "目标仓位",
        "全部落选理由",
    ):
        assert phrase in text


def test_docs_lock_adaptive_funnel_half_blind_sealing_and_two_level_decisions():
    screening = _read("playbooks/screening.md")
    allocation = _read("playbooks/research-capital-allocation.md")
    underwriting = _read("playbooks/underwriting-review.md")
    batch = _read("playbooks/batch-dispatch.md")
    portfolio = _read("playbooks/portfolio-synthesis.md")

    for phrase in ("约 5000 家", "数百家公司", "数十家公司", "少数公司"):
        assert phrase in screening
    assert "半盲两阶段" in underwriting
    assert "SHA-256 封存" in underwriting
    assert "challenger 不能读取此前研究和第一份评估" in underwriting
    assert "一家公司一个独立 agent" in batch
    assert "公司之间并行，公司内阶段串行" in batch
    assert "单公司只能承保通过或不通过" in portfolio
    assert "组合层才能给 `buy_now`" in portfolio
    assert "事件性冲击与危机错杀" in screening
    assert "不得无说明地同时" in underwriting
    assert "高优先级近门槛观察" in portfolio
    assert "研究时间本身也是资本" in allocation
    assert "不能直接把公司晋级为深研" in allocation
    assert "假阴性抽查" in allocation
    assert "L2 只能进入范围研究" in allocation


def test_readme_and_agents_only_document_v2_boundaries_and_commands():
    combined = _read("README.md") + "\n" + _read("AGENTS.md")

    for phrase in (
        "research/companies/",
        "research/batches/",
        "automation/runs/",
        "python -m trading_os assets validate",
        "python -m trading_os review create",
        "python -m trading_os review validate",
        "python -m trading_os coverage reconcile --check",
    ):
        assert phrase in combined
    assert "company validate" not in combined
    assert "company audit" not in combined
    assert "batch_research.py" not in combined
    assert "_worker_prompt.md" not in combined


def test_v2_company_schema_matches_fixture_and_validator(tmp_path: Path):
    from trading_os.research_assets.company import validate_company_dir

    schema = json.loads(_read("templates/company-meta-v2.schema.json"))
    company_dir = write_company(tmp_path)
    meta = json.loads((company_dir / "meta.json").read_text(encoding="utf-8"))

    assert set(schema["required"]) == set(meta)
    validated = validate_company_dir(company_dir)
    assert validated["identity"]["symbol"] == "CN:600519"


def test_miller_value_discipline_survives_v2_research_docs():
    combined = "\n".join(
        _read(path)
        for path in (
            "templates/initial-research-v2.md",
            "templates/underwriting-review.md",
            "playbooks/company-research.md",
            "playbooks/followup-review.md",
        )
    )
    for phrase in (
        "自由现金流",
        "市场隐含预期",
        "资本回报",
        "永久资本损失",
        "三情景",
        "低估值",
    ):
        assert phrase in combined
