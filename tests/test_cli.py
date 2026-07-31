from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tests.test_company_assets import write_company

T0 = "2026-07-21T09:00:00+08:00"
T1 = "2026-07-21T09:01:00+08:00"


def test_cli_help_renders_literal_percent_signs(capsys):
    from trading_os.cli import main

    with pytest.raises(SystemExit) as exc_info:
        main(["coverage", "--help"])

    assert exc_info.value.code == 0
    assert "100% hard-exclusion" in capsys.readouterr().out


def _candidates_file(tmp_path: Path, company_dir: Path, *, jsonl: bool = False) -> Path:
    item = {
        "symbol": "CN:600519",
        "name": "贵州茅台",
        "target_company_dir": str(company_dir),
    }
    path = tmp_path / ("candidates.jsonl" if jsonl else "candidates.json")
    if jsonl:
        path.write_text(json.dumps(item, ensure_ascii=False) + "\n", encoding="utf-8")
    else:
        path.write_text(json.dumps([item], ensure_ascii=False), encoding="utf-8")
    return path


def _create_args(tmp_path: Path, candidates: Path) -> list[str]:
    return [
        "review",
        "create",
        "memory-2026-07-21",
        "--scope-type",
        "industry",
        "--market",
        "CN",
        "--description",
        "存储产业链",
        "--candidates",
        str(candidates),
        "--runs-root",
        str(tmp_path / "automation" / "runs"),
        "--policy-root",
        str(Path("policies").resolve()),
        "--at",
        T0,
    ]


def _attach_research_claims(
    company_dir: Path,
    *,
    claim_category: str = "business",
) -> None:
    from trading_os.research_assets.sealing import seal_json

    claims_path = company_dir / "evidence" / "research-claims.json"
    claims = {
        "schema_version": 2,
        "report_id": "CN-600519-2026-07-21-initial_research",
        "symbol": "CN:600519",
        "claims": [
            {
                "claim_id": "claim-business-quality",
                "category": claim_category,
                "claim": "公司具有可验证的品牌和渠道优势。",
                "verification_metrics": ["渠道库存", "批价与出厂价关系"],
                "falsifiers": ["渠道库存持续恶化"],
                "source_ids": ["annual-report"],
            }
        ],
        "sources": [
            {
                "source_id": "annual-report",
                "tier": "S1",
                "uri_or_path": "sources/annual-report.pdf",
            }
        ],
        "decision": {
            "rating": "watch",
            "fair_value_range": [100.0, 120.0],
            "buy_zone": [80.0, 90.0],
            "reduce_zone": [130.0, 140.0],
            "conclusion": "等待安全边际。",
        },
    }
    seal_json(
        claims_path,
        claims,
        artifact_type="research_claims",
        sealed_at=__import__("datetime").datetime.fromisoformat(T0),
    )
    report_path = company_dir / "reports" / "2026-07-21-initial-research.md"
    text = report_path.read_text(encoding="utf-8")
    text = text.replace(
        '"sealed_artifacts": []',
        '"sealed_artifacts": [\n    "evidence/research-claims.json"\n  ]',
    )
    report_path.write_text(text, encoding="utf-8")
    meta_path = company_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["reports"]["history"][0]["sha256"] = hashlib.sha256(
        report_path.read_bytes()
    ).hexdigest()
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def test_cli_help_replaces_company_commands_with_assets_and_review(capsys):
    from trading_os.cli import main

    with pytest.raises(SystemExit) as exc:
        main(["--help"])

    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert "assets" in output
    assert "review" in output
    assert "company" not in output


def test_cli_review_help_lists_complete_workflow(capsys):
    from trading_os.cli import main

    with pytest.raises(SystemExit) as exc:
        main(["review", "--help"])

    assert exc.value.code == 0
    output = capsys.readouterr().out
    for command in (
        "create",
        "prepare",
        "status",
        "resume",
        "validate",
        "synthesize",
        "report",
        "finalize",
        "run",
    ):
        assert command in output


def test_cli_assets_validate_success(tmp_path: Path, capsys):
    from trading_os.cli import main

    write_company(tmp_path)

    code = main(["assets", "validate", "--research-root", str(tmp_path / "research")])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["valid_count"] == 1


def test_cli_assets_validate_failure_has_stable_error_code(tmp_path: Path, capsys):
    from trading_os.cli import main

    company_dir = write_company(tmp_path)
    meta_path = company_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["schema_version"] = 1
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    code = main(["assets", "validate", "--research-root", str(tmp_path / "research")])

    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    payload = json.loads(captured.err)
    assert payload["error_code"] == "asset_validation_failed"
    assert payload["invalid_count"] == 1


@pytest.mark.parametrize("jsonl", [False, True])
def test_cli_review_create_freezes_candidates_and_status_is_json(
    tmp_path: Path, capsys, jsonl: bool
):
    from trading_os.cli import main

    company_dir = write_company(tmp_path)
    candidates = _candidates_file(tmp_path, company_dir, jsonl=jsonl)

    assert main(_create_args(tmp_path, candidates)) == 0
    created = json.loads(capsys.readouterr().out)
    assert created["run"]["status"] == "candidates_frozen"
    assert created["run"]["candidate_set"]["count"] == 1

    code = main(
        [
            "review",
            "status",
            "memory-2026-07-21",
            "--runs-root",
            str(tmp_path / "automation" / "runs"),
        ]
    )
    assert code == 0
    status = json.loads(capsys.readouterr().out)
    assert status["run"]["status"] == "candidates_frozen"
    assert status["event_count"] == 2


def test_cli_review_prepare_seals_packets_and_strict_validate(tmp_path: Path, capsys):
    from trading_os.cli import main

    company_dir = write_company(tmp_path)
    _attach_research_claims(company_dir)
    candidates = _candidates_file(tmp_path, company_dir)
    runs_root = tmp_path / "automation" / "runs"
    assert main(_create_args(tmp_path, candidates)) == 0
    capsys.readouterr()

    code = main(
        [
            "review",
            "prepare",
            "memory-2026-07-21",
            "--runs-root",
            str(runs_root),
            "--at",
            T1,
        ]
    )
    assert code == 0
    prepared = json.loads(capsys.readouterr().out)
    assert prepared["run"]["status"] == "packets_ready"
    assert (company_dir / "underwriting" / "memory-2026-07-21" / "claim-packet.json").is_file()

    code = main(
        [
            "review",
            "validate",
            "memory-2026-07-21",
            "--strict",
            "--runs-root",
            str(runs_root),
        ]
    )
    assert code == 0
    validated = json.loads(capsys.readouterr().out)
    assert validated["ok"] is True
    assert validated["strict"] is True


def test_cli_review_prepare_failure_is_json_with_stable_code(tmp_path: Path, capsys):
    from trading_os.cli import main

    company_dir = write_company(tmp_path)
    candidates = _candidates_file(tmp_path, company_dir)
    assert main(_create_args(tmp_path, candidates)) == 0
    capsys.readouterr()

    code = main(
        [
            "review",
            "prepare",
            "memory-2026-07-21",
            "--runs-root",
            str(tmp_path / "automation" / "runs"),
            "--at",
            T1,
        ]
    )

    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    payload = json.loads(captured.err)
    assert payload["error_code"] == "review_workflow_error"
    assert "research_claims" in payload["error"]


def test_cli_review_run_advances_only_safe_executable_stages(tmp_path: Path, capsys):
    from trading_os.cli import main

    company_dir = write_company(tmp_path)
    _attach_research_claims(company_dir)
    candidates = _candidates_file(tmp_path, company_dir)
    assert main(_create_args(tmp_path, candidates)) == 0
    capsys.readouterr()

    code = main(
        [
            "review",
            "run",
            "memory-2026-07-21",
            "--runs-root",
            str(tmp_path / "automation" / "runs"),
            "--research-root",
            str(tmp_path / "research"),
            "--policy-root",
            str(Path("policies").resolve()),
            "--at",
            T1,
        ]
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "packets_ready"
    assert payload["next_action"] == "dispatch_blind_reviews"


def test_cli_review_commands_parse_synthesize_and_report(monkeypatch, capsys):
    import trading_os.cli as cli

    monkeypatch.setattr(cli, "synthesize_review", lambda **_: {"status": "synthesizing"})
    monkeypatch.setattr(cli, "write_review_report", lambda **_: {"status": "completed"})

    code = cli.main(
        [
            "review",
            "synthesize",
            "run-id",
            "--quotes",
            "quotes.json",
            "--at",
            T0,
        ]
    )
    assert code == 0
    assert json.loads(capsys.readouterr().out)["status"] == "synthesizing"

    code = cli.main(["review", "report", "run-id", "--at", T0])
    assert code == 0
    assert json.loads(capsys.readouterr().out)["status"] == "completed"


def test_cli_invalid_timestamp_has_stable_json_error(tmp_path: Path, capsys):
    from trading_os.cli import main

    company_dir = write_company(tmp_path)
    candidates = _candidates_file(tmp_path, company_dir)
    args = _create_args(tmp_path, candidates)
    args[-1] = "not-a-time"

    code = main(args)

    captured = capsys.readouterr()
    assert code == 1
    payload = json.loads(captured.err)
    assert payload["error_code"] == "review_workflow_error"


def test_cli_alerts_check_uses_quote_snapshot(tmp_path: Path, capsys):
    from trading_os.cli import main

    alerts_path = tmp_path / "alerts.json"
    quotes_path = tmp_path / "quotes.json"
    alerts_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "items": [
                    {
                        "alert_id": "CN:600519:buy-zone",
                        "symbol": "CN:600519",
                        "name": "贵州茅台",
                        "type": "underwriting_buy_zone_entry",
                        "condition": {"operator": "price_lte", "threshold": 1100},
                        "reason": "Enter buy zone.",
                        "latest_report": "companies/CN/600519/reports/example.md",
                        "source_ref": "review-1",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    quotes_path.write_text(
        json.dumps(
            [
                {
                    "symbol": "CN:600519",
                    "price": 1090,
                    "as_of": "2026-07-21T15:00:00+08:00",
                }
            ]
        ),
        encoding="utf-8",
    )

    code = main(
        [
            "alerts",
            "check",
            "--alerts",
            str(alerts_path),
            "--quotes",
            str(quotes_path),
            "--at",
            "2026-07-21T15:00:00+08:00",
        ]
    )

    assert code == 0
    assert json.loads(capsys.readouterr().out)["triggered_count"] == 1


def test_cli_alerts_check_rejects_non_object_alerts(tmp_path: Path, capsys):
    from trading_os.cli import main

    alerts_path = tmp_path / "alerts.json"
    quotes_path = tmp_path / "quotes.json"
    alerts_path.write_text("[]", encoding="utf-8")
    quotes_path.write_text("[]", encoding="utf-8")

    code = main(
        ["alerts", "check", "--alerts", str(alerts_path), "--quotes", str(quotes_path)]
    )

    captured = capsys.readouterr()
    assert code == 1
    assert json.loads(captured.err)["error_code"] == "runtime_error"


def test_cli_coverage_set_screening_and_validate(tmp_path: Path, capsys):
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
            "动力电池龙头。",
            "--evidence",
            "行业龙头",
            "--next-action",
            "加入研究队列。",
        ]
    )
    assert code == 0
    capsys.readouterr()

    assert main(["coverage", "validate", "--root", str(root)]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_cli_allocates_research_capacity_and_evaluates_profile(
    tmp_path: Path,
    capsys,
):
    from tests.test_research_allocation import (
        _profile,
        _ranking,
        _small_policy,
    )
    from trading_os.cli import main

    ranking_path = tmp_path / "ranking.json"
    policy_path = tmp_path / "policy.json"
    allocation_path = tmp_path / "allocation.json"
    profile_path = tmp_path / "profile.json"
    policy = json.loads(
        Path("policies/research-allocation.json").read_text(encoding="utf-8")
    )
    policy["payload"] = _small_policy()
    ranking_path.write_text(
        json.dumps(_ranking(), ensure_ascii=False),
        encoding="utf-8",
    )
    policy_path.write_text(
        json.dumps(policy, ensure_ascii=False),
        encoding="utf-8",
    )

    code = main(
        [
            "coverage",
            "allocate-research",
            "--ranking",
            str(ranking_path),
            "--policy",
            str(policy_path),
            "--output",
            str(allocation_path),
        ]
    )

    assert code == 0
    assert json.loads(capsys.readouterr().out)["selected_count"] == 4
    assert json.loads(allocation_path.read_text(encoding="utf-8"))[
        "selected_count"
    ] == 4

    profile_path.write_text(
        json.dumps(_profile(), ensure_ascii=False),
        encoding="utf-8",
    )
    code = main(
        [
            "coverage",
            "evaluate-profile",
            "--input",
            str(profile_path),
            "--policy",
            str(policy_path),
        ]
    )

    assert code == 0
    assert json.loads(capsys.readouterr().out)["next_stage"] == "scoped_research"


def test_cli_quality_triage_continuation_commands(monkeypatch, tmp_path: Path, capsys):
    import trading_os.cli as cli

    reviews_path = tmp_path / "reviews.json"
    reviews_path.write_text('{"reviews": []}', encoding="utf-8")
    monkeypatch.setattr(
        cli,
        "prepare_cycle_quality_audit_continuation",
        lambda **_: {
            "status": "pending_reviews",
            "round_number": 2,
            "idempotent": False,
        },
    )
    monkeypatch.setattr(
        cli,
        "record_cycle_quality_audit_continuation",
        lambda **_: {"status": "passed", "round_number": 2},
    )
    monkeypatch.setattr(
        cli,
        "materialize_cycle_quality_reopens",
        lambda **_: {"reopen_count": 0},
    )
    monkeypatch.setattr(
        cli,
        "prepare_cycle_quality_correction",
        lambda **_: {
            "correction_cycle_id": "correction-cycle",
            "symbol_count": 1,
        },
    )
    monkeypatch.setattr(
        cli,
        "record_cycle_quality_correction_resolution",
        lambda **_: {
            "status": "passed",
            "correction_cycle_id": "correction-cycle",
            "resolved_count": 1,
        },
    )

    code = cli.main(
        [
            "coverage",
            "quality-triage-continue",
            "cycle-id",
            "--root",
            str(tmp_path / "coverage" / "cn-a"),
            "--at",
            T0,
        ]
    )
    assert code == 0
    assert json.loads(capsys.readouterr().out)["round_number"] == 2

    code = cli.main(
        [
            "coverage",
            "quality-triage-record-continuation",
            "cycle-id",
            "--root",
            str(tmp_path / "coverage" / "cn-a"),
            "--reviews",
            str(reviews_path),
            "--at",
            T1,
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["status"] == "passed"

    code = cli.main(
        [
            "coverage",
            "quality-triage-correction-prepare",
            "cycle-id",
            "correction-cycle",
            "--root",
            str(tmp_path / "coverage" / "cn-a"),
            "--at",
            T0,
        ]
    )
    assert code == 0
    assert json.loads(capsys.readouterr().out)["symbol_count"] == 1

    code = cli.main(
        [
            "coverage",
            "quality-triage-correction-resolve",
            "cycle-id",
            "correction-cycle",
            "--root",
            str(tmp_path / "coverage" / "cn-a"),
            "--at",
            T1,
        ]
    )
    assert code == 0
    assert json.loads(capsys.readouterr().out)["resolved_count"] == 1
