import json

import pytest

from trading_os.industry_catalog import industry_catalog
from trading_os.research_assets.research_flow import ValidationError


def test_complete_routes_without_inventing_missing_company_industries(tmp_path):
    state = tmp_path / "coverage/cn-a/research_state.jsonl"
    state.parent.mkdir(parents=True)
    content = "\n".join(json.dumps(row, ensure_ascii=False) for row in [
        {"symbol": "CN:000001", "industry": "银行Ⅱ"},
        {"symbol": "CN:000002", "name": "未分类公司", "industry": None},
    ])
    state.write_text(content, encoding="utf-8")
    docs = tmp_path / "research/industries/sectors"
    docs.mkdir(parents=True)
    (docs / "banks.md").write_text("# 银行\n\n适用二级行业：银行Ⅱ\n", encoding="utf-8")
    result = industry_catalog(tmp_path, require_complete=True)
    assert result["routes"] == {"银行Ⅱ": "banks"}
    assert result["unclassified_companies"][0]["symbol"] == "CN:000002"
    assert state.read_text(encoding="utf-8") == content


def test_missing_route_and_duplicate_are_visible(tmp_path):
    state = tmp_path / "coverage/cn-a/research_state.jsonl"
    state.parent.mkdir(parents=True)
    state.write_text('{"symbol":"CN:000001","industry":"银行Ⅱ"}', encoding="utf-8")
    assert industry_catalog(tmp_path)["unmapped_industries"] == ["银行Ⅱ"]
    with pytest.raises(ValidationError, match="without a research framework"):
        industry_catalog(tmp_path, require_complete=True)
    docs = tmp_path / "research/industries/sectors"
    docs.mkdir(parents=True)
    for slug in ("a", "b"):
        (docs / f"{slug}.md").write_text("# 银行\n适用二级行业：银行Ⅱ\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="duplicate"):
        industry_catalog(tmp_path)
