from __future__ import annotations

import json
from pathlib import Path

import pytest

from trading_os.cli import main
from trading_os.research_assets.research_flow import (
    PERIODIC_TRIGGER,
    CompanyRef,
    ResearchFlow,
    ResearchRequest,
)

AT = "2026-08-08T17:00:00+08:00"


def _call(tmp_path: Path, capsys: pytest.CaptureFixture[str], *args: str) -> dict:
    code = main(["--root", str(tmp_path), *args])
    captured = capsys.readouterr()
    assert code == 0, captured.err
    return json.loads(captured.out)


def _result(symbol: str, task_id: str) -> dict:
    return {
        "task_id": task_id,
        "at": AT,
        "result": {
            "symbol": symbol,
            "name": "示例公司",
            "outcome": "covered",
            "report_period": "2026-H1",
            "information_cutoff": AT,
            "summary": "需求成立，现金流仍需验证。",
            "key_logic": ["需求增长"],
            "risks": ["资本开支回报不及预期"],
            "value_range": {"low": 58, "high": 82, "currency": "CNY"},
            "valuation_note": "正常化盈利为主。",
            "return_model": None,
            "return_model_note": "暂不可靠构造五年持有人模型。",
            "source_urls": ["https://example.com/report"],
            "report_markdown": (
                "# 示例公司\n\n信息截止：2026-08-08\n\n"
                "## 一句话结论\n\n需求成立。\n\n"
                "## 财务质量\n\n现金流仍需验证。\n\n"
                "## 估值\n\n方法一为正常化PE，方法二为DCF；以前者为核心。\n\n"
                "核心合理价值区间：58—82 元。\n\n"
                "## 基准持有人回报模型输入\n\n当前无法可靠建模。\n\n"
                "## 风险\n\n资本开支回报不足。\n\n"
                "## 来源\n\nhttps://example.com/report"
            ),
        },
    }


def test_help_exposes_only_periodic_research_workflow(capsys):
    with pytest.raises(SystemExit):
        main(["--help"])
    output = capsys.readouterr().out
    for command in ("quality-pool", "universe", "research", "validate"):
        assert command in output
    for removed in ("events", "updates", "watchlist", "screen"):
        assert removed not in output

    with pytest.raises(SystemExit):
        main(["research", "--help"])
    research = capsys.readouterr().out
    assert "enqueue-period" in research and "enqueue-rewrite" in research
    assert "enqueue-standard" not in research


def test_empty_status_and_validate(tmp_path: Path, capsys):
    assert _call(tmp_path, capsys, "status") == {
        "active": 0,
        "companies": 0,
        "covered": 0,
        "ignored": 0,
        "inactive": 0,
        "queued": 0,
        "running": 0,
        "unseen": 0,
    }
    assert _call(tmp_path, capsys, "validate")["ok"] is True


def test_cli_completes_a_period_task(tmp_path: Path, capsys):
    flow = ResearchFlow(tmp_path)
    flow.register_universe([CompanyRef("CN:000001", "示例公司")], at=AT)
    batch = flow.enqueue_research(
        [ResearchRequest("CN:000001", "完成中报研究")],
        report_period="2026-H1",
        trigger_kind=PERIODIC_TRIGGER,
        at=AT,
    )
    task = flow.start_task(batch.enqueued_tasks[0].task_id, at=AT)
    source = tmp_path / "result.json"
    source.write_text(
        json.dumps(_result(task.symbol, task.task_id), ensure_ascii=False),
        encoding="utf-8",
    )
    completed = _call(tmp_path, capsys, "research", "complete", "--input", str(source))
    assert completed["report_period"] == "2026-H1"
    assert completed["basis_report_path"].endswith("/2026-H1.md")

    rewrite = tmp_path / "rewrite.json"
    rewrite.write_text(
        json.dumps(
            {
                "reason": "用户要求完整重写",
                "companies": [{"symbol": "CN:000001"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    queued = _call(
        tmp_path,
        capsys,
        "research",
        "enqueue-rewrite",
        "--period",
        "2026-H1",
        "--batch-id",
        "manual-001",
        "--input",
        str(rewrite),
    )
    assert queued["enqueued"][0]["trigger_kind"] == "manual_rewrite"
    assert queued["enqueued"][0]["report_period"] == "2026-H1"
