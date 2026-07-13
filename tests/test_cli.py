from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.test_company_assets import write_company, write_strict_company


def test_cli_company_validate_success(tmp_path: Path, capsys):
    from trading_os.cli import main

    company_dir = write_company(tmp_path)

    code = main(["company", "validate", str(company_dir)])

    assert code == 0
    assert "CN:600519" in capsys.readouterr().out


def test_cli_company_validate_strict_success(tmp_path: Path, capsys):
    from trading_os.cli import main

    company_dir = write_strict_company(tmp_path)

    code = main(["company", "validate", str(company_dir), "--strict"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"ok": True, "symbol": "CN:600519"}


def test_cli_company_validate_strict_failure_writes_json_error(
    tmp_path: Path, capsys
):
    from trading_os.cli import main

    company_dir = write_company(tmp_path)

    code = main(["company", "validate", str(company_dir), "--strict"])

    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    payload = json.loads(captured.err)
    assert payload["ok"] is False
    assert "report date" in payload["error"]


def test_cli_company_audit_summarizes_report_and_meta_drift(tmp_path: Path, capsys):
    from trading_os.cli import main

    strict_dir = write_strict_company(tmp_path)
    legacy_dir = tmp_path / "research" / "companies" / "CN" / "000001"
    (legacy_dir / "reports").mkdir(parents=True)
    (legacy_dir / "reports" / "2026-07-06-initial.md").write_text(
        "# 公司研究：平安银行（CN:000001）\n"
        "日期：2026-07-06\n"
        "研究类型：initial\n"
        "分析师：agent\n\n"
        "## 结论版\n\n"
        "缺少大量标准章节。\n",
        encoding="utf-8",
    )
    legacy_meta = json.loads((strict_dir / "meta.json").read_text(encoding="utf-8"))
    legacy_meta.update(
        {
            "symbol": "CN:000001",
            "ticker": "000001",
            "name": "平安银行",
            "latest_report": "reports/2026-07-06-initial.md",
            "report_history": ["reports/2026-07-06-initial.md"],
            "current_price": 10.5,
        }
    )
    (legacy_dir / "meta.json").write_text(
        json.dumps(legacy_meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    code = main(["company", "audit", "--research-root", str(tmp_path / "research")])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["company_count"] == 2
    assert payload["analyst_counts"]["codex"] == 1
    assert payload["analyst_counts"]["generic_or_unknown"] == 1
    assert payload["extra_meta_keys"][0] == {"key": "current_price", "count": 1}
    assert payload["price_like_meta_keys"][0] == {"key": "current_price", "count": 1}
    assert payload["strict_issue_count"] > 0
    assert payload["warning_count"] > 0
    assert any("extra meta" in item["error"] for item in payload["warnings"])


def test_cli_help_lists_coverage_command(capsys):
    from trading_os.cli import main

    with pytest.raises(SystemExit) as exc:
        main(["--help"])

    assert exc.value.code == 0
    assert "coverage" in capsys.readouterr().out


def test_cli_index_rebuild_writes_index(tmp_path: Path):
    from trading_os.cli import main

    write_company(tmp_path)

    code = main(["index", "rebuild", "--research-root", str(tmp_path / "research")])

    assert code == 0
    payload = json.loads((tmp_path / "research" / "index.json").read_text(encoding="utf-8"))
    assert payload["company_count"] == 1


def test_cli_alerts_check_uses_quote_snapshot(tmp_path: Path, capsys):
    from trading_os.cli import main

    alerts_path = tmp_path / "alerts.json"
    quotes_path = tmp_path / "quotes.json"
    alerts_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "items": [
                    {
                        "symbol": "CN:600519",
                        "name": "贵州茅台",
                        "type": "price_below",
                        "price": 1100,
                        "reason": "Enter buy zone.",
                        "latest_report": "companies/CN/600519/reports/2026-07-06-initial.md",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    quotes_path.write_text(
        json.dumps([{"symbol": "CN:600519", "price": 1090}], ensure_ascii=False),
        encoding="utf-8",
    )

    code = main(["alerts", "check", "--alerts", str(alerts_path), "--quotes", str(quotes_path)])

    assert code == 0
    assert "triggered_count" in capsys.readouterr().out


def test_cli_alerts_check_accepts_utf8_bom_json(tmp_path: Path, capsys):
    from trading_os.cli import main

    alerts_path = tmp_path / "alerts.json"
    quotes_path = tmp_path / "quotes.json"
    alerts_path.write_text(
        "\ufeff"
        + json.dumps(
            {
                "schema_version": 1,
                "items": [
                    {
                        "symbol": "CN:600519",
                        "name": "璐靛窞鑼呭彴",
                        "type": "price_below",
                        "price": 1100,
                        "reason": "Enter buy zone.",
                        "latest_report": "companies/CN/600519/reports/2026-07-06-initial.md",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    quotes_path.write_text(
        "\ufeff" + json.dumps([{"symbol": "CN:600519", "price": 1090}], ensure_ascii=False),
        encoding="utf-8",
    )

    code = main(["alerts", "check", "--alerts", str(alerts_path), "--quotes", str(quotes_path)])

    assert code == 0
    assert '"triggered_count": 1' in capsys.readouterr().out


def test_cli_alerts_check_rejects_non_object_alerts(tmp_path: Path, capsys):
    from trading_os.cli import main

    alerts_path = tmp_path / "alerts.json"
    quotes_path = tmp_path / "quotes.json"
    alerts_path.write_text(json.dumps([], ensure_ascii=False), encoding="utf-8")
    quotes_path.write_text(
        json.dumps([{"symbol": "CN:600519", "price": 1090}], ensure_ascii=False),
        encoding="utf-8",
    )

    code = main(["alerts", "check", "--alerts", str(alerts_path), "--quotes", str(quotes_path)])

    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    payload = json.loads(captured.err)
    assert payload["ok"] is False
    assert "alert" in payload["error"]
    assert "Traceback" not in captured.err


def test_cli_company_validate_missing_dir_writes_json_error_to_stderr(
    tmp_path: Path, capsys
):
    from trading_os.cli import main

    code = main(["company", "validate", str(tmp_path / "missing-company")])

    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    payload = json.loads(captured.err)
    assert payload["ok"] is False
    assert "company directory does not exist" in payload["error"]


def test_cli_index_rebuild_invalid_metadata_writes_json_error_to_stderr(
    tmp_path: Path, capsys
):
    from trading_os.cli import main

    company_dir = write_company(tmp_path)
    meta_path = company_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["latest_report"] = "reports/missing.md"
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    code = main(["index", "rebuild", "--research-root", str(tmp_path / "research")])

    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    payload = json.loads(captured.err)
    assert payload["ok"] is False
    assert any("latest_report" in error for error in payload["errors"])


def test_cli_coverage_set_screening_get_list_and_status(tmp_path: Path, capsys):
    from trading_os.cli import main

    root = tmp_path / "coverage" / "cn-a"

    code = main(
        [
            "coverage",
            "set-screening",
            "CN:300750",
            "--root",
            str(root),
            "--name",
            "宁德时代",
            "--decision",
            "deep_research",
            "--priority",
            "1",
            "--reason",
            "动力电池龙头，值得完整研究。",
            "--evidence",
            "行业龙头",
            "--next-action",
            "加入研究队列。",
        ]
    )
    assert code == 0

    code = main(["coverage", "get", "CN:300750", "--root", str(root)])
    assert code == 0
    assert "宁德时代" in capsys.readouterr().out

    code = main(["coverage", "list", "--root", str(root), "--decision", "deep_research"])
    assert code == 0
    assert "CN:300750" in capsys.readouterr().out

    code = main(["coverage", "status", "--root", str(root)])
    assert code == 0
    assert '"deep_research": 1' in capsys.readouterr().out


def test_cli_coverage_enqueue_and_validate(tmp_path: Path, capsys):
    from trading_os.cli import main

    root = tmp_path / "coverage" / "cn-a"

    code = main(
        [
            "coverage",
            "enqueue",
            "CN:300750",
            "--root",
            str(root),
            "--name",
            "宁德时代",
            "--priority",
            "1",
            "--reason",
            "筛选结果为 deep_research。",
        ]
    )
    assert code == 0

    code = main(["coverage", "validate", "--root", str(root)])
    assert code == 0
    assert '"ok": true' in capsys.readouterr().out


def _write_reconcile_queue(tmp_path: Path) -> tuple[Path, Path]:
    from trading_os.research_assets.coverage_store import write_jsonl

    company_dir = write_company(tmp_path)
    root = tmp_path / "coverage" / "cn-a"
    write_jsonl(
        root / "research_queue.jsonl",
        [
            {
                "symbol": "CN:600519",
                "name": "贵州茅台",
                "task_type": "initial_research",
                "priority": 1,
                "status": "pending",
                "reason": "进入研究队列。",
                "target_company_dir": str(company_dir),
                "assigned_agent": None,
                "started_at": None,
                "finished_at": None,
                "result_path": None,
                "failure_reason": None,
                "next_action": "完成初始研究。",
            }
        ],
    )
    return root, tmp_path / "research"


def test_cli_coverage_reconcile_check_reports_drift_without_writing(
    tmp_path: Path, capsys
):
    from trading_os.cli import main
    from trading_os.research_assets.coverage_store import read_jsonl

    root, research_root = _write_reconcile_queue(tmp_path)

    code = main(
        [
            "coverage",
            "reconcile",
            "--check",
            "--root",
            str(root),
            "--research-root",
            str(research_root),
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert payload["change_count"] == 1
    assert payload["applied"] is False
    assert read_jsonl(root / "research_queue.jsonl")[0]["status"] == "pending"


def test_cli_coverage_reconcile_apply_updates_queue(tmp_path: Path, capsys):
    from trading_os.cli import main
    from trading_os.research_assets.coverage_store import read_jsonl

    root, research_root = _write_reconcile_queue(tmp_path)

    code = main(
        [
            "coverage",
            "reconcile",
            "--apply",
            "--root",
            str(root),
            "--research-root",
            str(research_root),
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["change_count"] == 1
    assert payload["applied"] is True
    assert read_jsonl(root / "research_queue.jsonl")[0]["status"] == "completed"


@pytest.mark.parametrize("modes", [[], ["--check", "--apply"]])
def test_cli_coverage_reconcile_requires_exactly_one_mode(
    tmp_path: Path, modes: list[str]
):
    from trading_os.cli import main

    root, research_root = _write_reconcile_queue(tmp_path)

    with pytest.raises(SystemExit) as exc:
        main(
            [
                "coverage",
                "reconcile",
                *modes,
                "--root",
                str(root),
                "--research-root",
                str(research_root),
            ]
        )

    assert exc.value.code == 2
