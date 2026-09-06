from __future__ import annotations

import json
from pathlib import Path

import pytest

from trading_os.cli import main


def _write(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _call(tmp_path: Path, capsys: pytest.CaptureFixture[str], *args: str) -> dict:
    code = main(["--root", str(tmp_path), *args])
    captured = capsys.readouterr()
    assert code == 0, captured.err
    assert captured.err == ""
    return json.loads(captured.out)


def _pool_payload() -> dict:
    return {
        "schema_version": 1,
        "as_of": "2026-08-31",
        "universe_count": 5552,
        "methodology": "prompts/screening/cn-a-value-quality.md",
        "philosophy": "商业质量与价格分开判断。",
        "companies": [
            {
                "symbol": "CN:600519",
                "name": "贵州茅台",
                "industry": "白酒Ⅱ",
                "tier": "core_moat",
                "group": "consumer_brand_network",
                "note": "品牌、渠道和供给约束构成长期壁垒。",
            },
            {
                "symbol": "CN:600900",
                "name": "长江电力",
                "industry": "电力",
                "tier": "quality_research",
                "group": "infrastructure_finance_resource",
            },
        ],
    }


def _prepare_methodology(tmp_path: Path) -> None:
    path = tmp_path / "prompts/screening/cn-a-value-quality.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# 筛选规范\n", encoding="utf-8")


def test_quality_pool_replace_validate_status_and_list(tmp_path: Path, capsys):
    _prepare_methodology(tmp_path)
    source = _write(tmp_path / "input.json", _pool_payload())

    replaced = _call(tmp_path, capsys, "quality-pool", "replace", "--input", str(source))
    validated = _call(tmp_path, capsys, "quality-pool", "validate")
    status = _call(tmp_path, capsys, "quality-pool", "status")
    core = _call(tmp_path, capsys, "quality-pool", "list", "--tier", "core_moat")

    assert replaced["pool_count"] == 2
    assert replaced["tier_counts"] == {"core_moat": 1, "quality_research": 1}
    assert validated == {"ok": True, "status": status}
    assert core["count"] == 1
    assert core["companies"][0]["symbol"] == "CN:600519"
    assert (tmp_path / replaced["pool_path"]).is_file()
    current = (tmp_path / replaced["current_path"]).read_text(encoding="utf-8")
    assert "本池只表达商业质量" in current
    assert "贵州茅台" in current and "长江电力" in current
    assert not (tmp_path / "coverage/cn-a/research_state.jsonl").exists()
    assert not (tmp_path / "coverage/cn-a/research_queue.jsonl").exists()
    assert not (tmp_path / "research/watchlist.jsonl").exists()


def test_quality_pool_rejects_research_and_market_coupling_fields(tmp_path: Path, capsys):
    _prepare_methodology(tmp_path)
    payload = _pool_payload()
    payload["companies"][0]["report_path"] = "research/companies/CN/600519/report.md"
    source = _write(tmp_path / "coupled.json", payload)

    code = main(
        ["--root", str(tmp_path), "quality-pool", "replace", "--input", str(source)]
    )
    error = json.loads(capsys.readouterr().err)

    assert code == 1
    assert "不得耦合" in error["error"]
    assert "report_path" in error["error"]
    assert not (tmp_path / "screening/cn-a/value-quality/pool.json").exists()


def test_quality_pool_requires_unique_companies_and_tier_order(tmp_path: Path, capsys):
    _prepare_methodology(tmp_path)
    duplicate = _pool_payload()
    duplicate["companies"][1]["symbol"] = "CN:600519"
    source = _write(tmp_path / "duplicate.json", duplicate)

    code = main(
        ["--root", str(tmp_path), "quality-pool", "replace", "--input", str(source)]
    )
    assert code == 1
    assert "重复证券" in json.loads(capsys.readouterr().err)["error"]

    wrong_order = _pool_payload()
    wrong_order["companies"].reverse()
    source = _write(tmp_path / "wrong-order.json", wrong_order)
    code = main(
        ["--root", str(tmp_path), "quality-pool", "replace", "--input", str(source)]
    )
    assert code == 1
    assert "core_moat 必须整体排在" in json.loads(capsys.readouterr().err)["error"]


def test_research_and_quality_pool_validation_are_independent(tmp_path: Path, capsys):
    _prepare_methodology(tmp_path)
    source = _write(tmp_path / "input.json", _pool_payload())
    _call(tmp_path, capsys, "quality-pool", "replace", "--input", str(source))
    current = tmp_path / "screening/cn-a/value-quality/current.md"
    current.write_text("被手工改坏\n", encoding="utf-8")

    research_validation = _call(tmp_path, capsys, "validate")
    assert research_validation["ok"] is True

    code = main(["--root", str(tmp_path), "quality-pool", "validate"])
    error = json.loads(capsys.readouterr().err)
    assert code == 1
    assert "确定性投影" in error["error"]
