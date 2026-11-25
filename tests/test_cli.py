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
STANDARD_ID = "owner-value-1.0"
SPEC_REVISION = "9ca1bb179c3aa0ce5005ffaf3c57b6324e9c5462"


def _write_registry(root: Path) -> None:
    path = root / "research/standards/registry.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "active_standard": STANDARD_ID,
                "standards": [
                    {"id": STANDARD_ID, "status": "released", "spec_revision": SPEC_REVISION}
                ],
            }
        ),
        encoding="utf-8",
    )


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
    _write_registry(tmp_path)
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
    assert completed["standard_id"] == STANDARD_ID
    assert completed["spec_revision"] == SPEC_REVISION
    assert completed["accepted_at"] == AT

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


def test_latest_disclosure_preview_respects_fiscal_end_without_writing_tasks(tmp_path, capsys):
    from test_screening_pool import _pool_payload, _prepare_methodology

    from trading_os.screening_pool import QualityPoolStore

    _prepare_methodology(tmp_path)
    payload = _pool_payload()
    c = payload["companies"][0]
    c["symbol"] = "US:MSFT"
    payload["companies"] = [c]
    payload["universe"]["securities"] = {"US:MSFT": c["name"]}
    payload["review"]["reviewed_symbols"] = ["US:MSFT"]
    QualityPoolStore(tmp_path, "us").replace(payload)
    source = tmp_path / "disclosures.json"
    source.write_text(
        json.dumps(
            {
                "disclosures": [
                    {
                        "symbol": "US:MSFT",
                        "report_period": period,
                        "financial_basis": {
                            "period_end": end,
                            "published_on": published,
                            "source_url": "https://example.com/results",
                        },
                    }
                    for period, end, published in [
                        ("2026-H1", "2025-12-31", "2026-01-28"),
                        ("2026-FY", "2026-06-30", "2026-07-29"),
                    ]
                ]
            }
        )
    )
    args = (
        "research",
        "--market",
        "us",
        "enqueue-latest",
        "--input",
        str(source),
        "--at",
        "2026-10-24T09:00:00+08:00",
    )
    preview = _call(tmp_path, capsys, *args)
    assert preview["plan"][0]["report_period"] == "2026-FY"
    assert preview["selection_period"] == "2026-Q3"
    assert not (tmp_path / "screening/us/value-quality/periods").exists()
    assert not (tmp_path / "coverage/us/research_queue.jsonl").exists()
    applied = _call(tmp_path, capsys, *args, "--apply")
    assert len(applied["enqueued"]) == 1
    assert applied["enqueued"][0]["financial_basis"]["period_end"] == "2026-06-30"
    repeated = _call(tmp_path, capsys, *args, "--apply")
    assert repeated["skipped"] == ["US:MSFT"]


def test_period_membership_survives_pool_changes_and_independent_study(tmp_path, capsys):
    from test_screening_pool import _pool_payload, _prepare_methodology

    from trading_os.screening_pool import QualityPoolStore

    _prepare_methodology(tmp_path)
    _write_registry(tmp_path)
    store = QualityPoolStore(tmp_path)
    payload = _pool_payload()
    store.replace(payload)
    _call(tmp_path, capsys, "quality-pool", "freeze-period", "--period", "2026-H1")
    payload["companies"].pop()
    store.replace(payload)
    batch = _call(tmp_path, capsys, "research", "enqueue-period", "--period", "2026-H1")
    assert {task["symbol"] for task in batch["enqueued"]} == {"CN:600519", "CN:600900"}

    flow = ResearchFlow(tmp_path)
    flow.register_universe([CompanyRef("CN:000001", "示例公司")], at=AT)
    source = tmp_path / "company.json"
    source.write_text(json.dumps({"companies": [{"symbol": "CN:000001"}]}))
    command = ("research", "enqueue-company", "--period", "2026-H1", "--input", str(source))
    task = _call(tmp_path, capsys, *command)["enqueued"][0]
    _call(tmp_path, capsys, "research", "start", task["task_id"])
    result = tmp_path / "result.json"
    result.write_text(json.dumps(_result("CN:000001", task["task_id"])))
    completed = _call(tmp_path, capsys, "research", "complete", "--input", str(result))
    assert (tmp_path / completed["basis_report_path"]).is_file()
    assert _call(tmp_path, capsys, *command)["deduplicated"] == 1
    historic = _call(tmp_path, capsys, "quality-pool", "list", "--period", "2026-H1")
    assert {c["symbol"] for c in historic["companies"]} == {"CN:600519", "CN:600900"}
    assert [c.symbol for c in store.read().companies] == ["CN:600519"]


@pytest.mark.parametrize("use_disclosures", [False, True])
def test_rescreen_targets_new_members_in_same_financial_period(tmp_path, capsys, use_disclosures):
    from test_screening_pool import _pool_payload, _prepare_methodology

    from trading_os.screening_pool import QualityPoolStore

    _prepare_methodology(tmp_path)
    store = QualityPoolStore(tmp_path)
    pool = _pool_payload()
    store.replace(pool)
    original = store.freeze_selection("2026-Q3")
    pool["companies"].pop()
    store.replace(pool)
    label = "2026-Q3@2026-11-25"
    _call(tmp_path, capsys, "quality-pool", "freeze-period", "--period", label)
    args = ["research", "enqueue-period", "--period", "2026-Q3", "--selection-period", label]
    if use_disclosures:
        path = tmp_path / "disclosures.json"
        path.write_text(json.dumps([{
            "symbol": "CN:600519", "report_period": "2026-Q3",
            "financial_basis": {"period_end": "2026-09-30", "published_on": "2026-10-30",
                                "source_url": "https://example.com/quarterly"},
        }]))
        args.extend(["--disclosures", str(path)])
    result = _call(tmp_path, capsys, *args, "--at", "2026-11-25T16:00:00+08:00")
    assert [(t["symbol"], t["report_period"]) for t in result["enqueued"]] == [
        ("CN:600519", "2026-Q3")
    ]
    assert store.read_selection("2026-Q3") == original


@pytest.mark.parametrize("with_disclosures", [False, True])
@pytest.mark.parametrize(
    ("tier", "expected"),
    [
        (None, {"CN:600519", "CN:600900"}),
        ("core_moat", {"CN:600519"}),
        ("quality_research", {"CN:600900"}),
    ],
)
def test_period_schedule_filters_current_pool_tier(
    tmp_path, capsys, with_disclosures, tier, expected
):
    from test_screening_pool import _pool_payload, _prepare_methodology

    from trading_os.screening_pool import QualityPoolStore

    _prepare_methodology(tmp_path)
    store = QualityPoolStore(tmp_path)
    store.replace(_pool_payload())
    pool_before = (tmp_path / "screening/cn-a/value-quality/pool.json").read_bytes()
    args = ["research", "enqueue-period", "--period", "2026-Q3"]
    if tier:
        args.extend(["--tier", tier])
    if with_disclosures:
        source = tmp_path / "disclosures.json"
        source.write_text(json.dumps({
            "disclosures": [
                {
                    "symbol": symbol,
                    "report_period": "2026-Q3",
                    "financial_basis": {
                        "period_end": "2026-09-30",
                        "published_on": "2026-10-30",
                        "source_url": "https://example.com/quarterly",
                    },
                }
                for symbol in ["CN:600519", "CN:600900"]
            ],
        }))
        args.extend(["--disclosures", str(source)])
    args.extend(["--at", "2026-11-12T20:00:00+08:00"])
    result = _call(tmp_path, capsys, *args)
    assert {task["symbol"] for task in result["enqueued"]} == expected
    if with_disclosures:
        assert result["missing_disclosures"] == []
    assert (tmp_path / "screening/cn-a/value-quality/pool.json").read_bytes() == pool_before
    if with_disclosures:
        repeated = _call(tmp_path, capsys, *args)
        assert repeated["enqueued"] == []
    else:
        assert main(["--root", str(tmp_path), *args]) == 1
        assert "active task" in capsys.readouterr().err
    assert ResearchFlow(tmp_path).status().queued == len(expected)
