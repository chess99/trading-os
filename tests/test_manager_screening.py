from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

CUTOFF = dt.datetime.fromisoformat("2026-07-31T08:00:00+08:00")
RUN_ID = "2026-07-31-manager-screen-001"


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _policy(path: Path) -> Path:
    payload = {
        "schema_version": 2,
        "policy_id": "manager-screening.test",
        "version": "1.0.0",
        "effective_at": CUTOFF.isoformat(),
        "kind": "manager_screening",
        "payload": {
            "default_batch_size": 2,
            "minimum_batch_size": 1,
            "maximum_batch_size": 3,
            "routes": ["pass", "watch", "send_to_analyst"],
            "quick_profile_effort_budget_hours": 1.5,
            "quick_profile_stop_conditions": [
                "无法建立普通股股东现金路径",
                "正常化收益不支持继续研究",
            ],
            "pass_and_watch_require_revisit_trigger": True,
            "one_line_reason_max_chars": 240,
            "decisive_question_max_chars": 600,
            "quality": {
                "route_disagreement_is_material_error": False,
            },
            "recursive_correction": "forbidden",
            "principles": {
                "same_manager_per_batch": True,
            },
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def _root(tmp_path: Path) -> tuple[Path, Path]:
    from trading_os.research_assets.scope_workflow import freeze_all_a_scope

    root = tmp_path / "coverage" / "cn-a"
    companies = []
    screening = []
    for ticker, name, industry, pe in (
        ("000001", "甲公司", "银行", 5.0),
        ("000002", "乙公司", "制造", 12.0),
        ("000003", "丙公司", "消费", 20.0),
        ("000004", "丁公司", "资源", 8.0),
    ):
        symbol = f"CN:{ticker}"
        companies.append(
            {
                "symbol": symbol,
                "ticker": ticker,
                "name": name,
                "market": "CN",
                "exchange": "SZSE",
                "security_type": "common_stock",
                "listing_status": "listed",
                "as_of": "2026-07-30",
                "industry": industry,
                "price": 10.0,
                "market_cap_cny": 10_000_000_000,
                "pe_ttm": pe,
                "pb": 1.0,
                "roe": 10.0,
                "source": "fixture snapshot",
                "fetched_at": CUTOFF.isoformat(),
            }
        )
        screening.append(
            {
                "symbol": symbol,
                "name": name,
                "decision": "catalog",
                "priority": None,
                "reason": "旧目录记录。",
                "evidence": ["fixture"],
                "next_action": "等待新机制初筛。",
            }
        )
    _write_jsonl(root / "companies.jsonl", companies)
    _write_jsonl(root / "screening.jsonl", screening)
    _write_jsonl(root / "research_queue.jsonl", [])
    _write_jsonl(root / "runs.jsonl", [])
    policy_path = _policy(tmp_path / "policies" / "manager-screening.json")
    freeze_all_a_scope(
        root=root,
        run_id=RUN_ID,
        scope_cutoff=CUTOFF,
        frozen_at=CUTOFF,
    )
    return root, policy_path


def _submission(symbols: list[str]) -> dict:
    decisions = []
    for index, symbol in enumerate(symbols):
        route = "pass" if index == 0 else "send_to_analyst"
        decisions.append(
            {
                "symbol": symbol,
                "route": route,
                "one_line_reason": (
                    "现有快照没有显示继续购买研究时间的高价值。"
                    if route == "pass"
                    else "下一小时核验现金转换很可能改变判断。"
                ),
                "decisive_question": "正常化所有者收益能否持续覆盖当前估值？",
                "revisit_triggers": (
                    [
                        {
                            "type": "filing",
                            "condition": "下一份半年报披露",
                            "reason": "重新核验盈利和现金转换。",
                        }
                    ]
                    if route == "pass"
                    else []
                ),
                "confidence": "medium",
                "evidence_ids": [f"snapshot:{symbol}"],
            }
        )
    return {
        "schema_version": 1,
        "manager": {
            "agent": "/root",
            "model": "gpt-test",
            "tools": ["packet_read"],
        },
        "additional_evidence": [],
        "decisions": decisions,
    }


def test_manager_freeze_uses_stable_scope_order_and_only_four_files(tmp_path: Path):
    from trading_os.research_assets.manager_screening import (
        freeze_manager_screen_batch,
    )
    from trading_os.research_assets.sealing import verify_sealed

    root, policy_path = _root(tmp_path)
    frozen = freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        frozen_at=CUTOFF + dt.timedelta(minutes=1),
        policy_path=policy_path,
    )
    batch_dir = tmp_path / "coverage" / "cn-a" / "manager-screen" / RUN_ID / "batch-001"
    assert sorted(path.name for path in batch_dir.iterdir()) == [
        "batch.json",
        "batch.json.seal.json",
        "packet.json",
        "packet.json.seal.json",
    ]
    batch = json.loads((batch_dir / "batch.json").read_text(encoding="utf-8"))
    packet = json.loads((batch_dir / "packet.json").read_text(encoding="utf-8"))
    assert [item["symbol"] for item in batch["members"]] == [
        "CN:000001",
        "CN:000002",
    ]
    assert [item["symbol"] for item in packet["dossiers"]] == [
        "CN:000001",
        "CN:000002",
    ]
    assert packet["dossiers"][0]["market_snapshot"]["pe_ttm"] == 5.0
    assert verify_sealed(batch_dir / "batch.json").sha256 == frozen["batch_sha256"]
    assert (
        freeze_manager_screen_batch(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-001",
            frozen_at=CUTOFF + dt.timedelta(hours=1),
            policy_path=policy_path,
        )["packet_sha256"]
        == frozen["packet_sha256"]
    )


def test_manager_freeze_rejects_company_snapshot_changed_after_scope(tmp_path: Path):
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.manager_screening import (
        ManagerScreeningError,
        freeze_manager_screen_batch,
    )

    root, policy_path = _root(tmp_path)
    companies_path = root / "companies.jsonl"
    companies = read_jsonl(companies_path)
    companies[0]["price"] = 10.5
    write_jsonl(companies_path, companies)

    with pytest.raises(ManagerScreeningError, match="changed after scope freeze"):
        freeze_manager_screen_batch(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-001",
            frozen_at=CUTOFF + dt.timedelta(minutes=1),
            policy_path=policy_path,
        )


def test_record_routes_only_selected_companies_to_analyst_and_status(tmp_path: Path):
    from trading_os.research_assets.coverage_store import read_jsonl
    from trading_os.research_assets.manager_screening import (
        freeze_manager_screen_batch,
        manager_screen_status,
        record_manager_screen_decisions,
    )

    root, policy_path = _root(tmp_path)
    freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        frozen_at=CUTOFF + dt.timedelta(minutes=1),
        policy_path=policy_path,
    )
    recorded = record_manager_screen_decisions(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        submission=_submission(["CN:000001", "CN:000002"]),
        recorded_at=CUTOFF + dt.timedelta(minutes=2),
    )
    assert recorded["by_route"] == {"pass": 1, "send_to_analyst": 1}
    queue = {item["symbol"]: item for item in read_jsonl(root / "research_queue.jsonl")}
    assert queue["CN:000001"]["task_type"] == "manager_screen"
    assert queue["CN:000001"]["status"] == "completed"
    assert queue["CN:000002"]["task_type"] == "quick_profile"
    assert queue["CN:000002"]["status"] == "pending"
    assert queue["CN:000002"]["effort_budget_hours"] == 1.5
    assert queue["CN:000002"]["preceding_stage"] == "manager_screen"
    screening = {item["symbol"]: item for item in read_jsonl(root / "screening.jsonl")}
    assert screening["CN:000001"]["decision"] == "catalog"
    assert screening["CN:000002"]["decision"] == "quick_profile"
    assert not list((tmp_path / "research").glob("companies/*/*/reports/*"))

    status = manager_screen_status(root=root, run_id=RUN_ID)
    assert status["completed_company_count"] == 2
    assert status["remaining_unbatched_count"] == 2
    assert status["by_route"] == {"pass": 1, "send_to_analyst": 1}
    assert status["completed_manager_wall_clock_seconds"] == 60.0
    assert status["batches"][0]["manager_wall_clock_seconds"] == 60.0

    second = freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-002",
        batch_size=2,
        frozen_at=CUTOFF + dt.timedelta(minutes=3),
        policy_path=policy_path,
    )
    batch = json.loads((tmp_path / second["batch_path"]).read_text(encoding="utf-8"))
    assert [item["symbol"] for item in batch["members"]] == [
        "CN:000003",
        "CN:000004",
    ]


def test_watch_materializes_as_general_watch_only(tmp_path: Path):
    from trading_os.research_assets.coverage_store import read_jsonl
    from trading_os.research_assets.manager_screening import (
        freeze_manager_screen_batch,
        record_manager_screen_decisions,
    )

    root, policy_path = _root(tmp_path)
    freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        frozen_at=CUTOFF + dt.timedelta(minutes=1),
        policy_path=policy_path,
    )
    submission = _submission(["CN:000001", "CN:000002"])
    submission["decisions"][0]["route"] = "watch"
    record_manager_screen_decisions(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        submission=submission,
        recorded_at=CUTOFF + dt.timedelta(minutes=2),
    )

    screening = {item["symbol"]: item for item in read_jsonl(root / "screening.jsonl")}
    assert screening["CN:000001"]["decision"] == "watch_only"
    assert "价格、财报、事件或关键证据" in screening["CN:000001"]["next_action"]


def test_result_replay_preserves_later_queue_and_screening_progress(tmp_path: Path):
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.manager_screening import (
        freeze_manager_screen_batch,
        record_manager_screen_decisions,
    )

    root, policy_path = _root(tmp_path)
    freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        frozen_at=CUTOFF + dt.timedelta(minutes=1),
        policy_path=policy_path,
    )
    submission = _submission(["CN:000001", "CN:000002"])
    record_manager_screen_decisions(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        submission=submission,
        recorded_at=CUTOFF + dt.timedelta(minutes=2),
    )

    queue_path = root / "research_queue.jsonl"
    queue = read_jsonl(queue_path)
    analyst_row = next(item for item in queue if item["symbol"] == "CN:000002")
    analyst_row.update(
        {
            "task_type": "deep_research",
            "status": "running",
            "assigned_agent": "/root/analyst-000002",
            "started_at": (CUTOFF + dt.timedelta(minutes=3)).isoformat(),
        }
    )
    write_jsonl(queue_path, queue)

    screening_path = root / "screening.jsonl"
    screening = read_jsonl(screening_path)
    screen_row = next(item for item in screening if item["symbol"] == "CN:000002")
    screen_row.update(
        {
            "decision": "deep_research",
            "reason": "后续研究已经推进到深研。",
            "next_action": "完成当前深研。",
        }
    )
    write_jsonl(screening_path, screening)
    queue_before = read_jsonl(queue_path)
    screening_before = read_jsonl(screening_path)

    record_manager_screen_decisions(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        submission=submission,
        recorded_at=CUTOFF + dt.timedelta(minutes=4),
    )

    assert read_jsonl(queue_path) == queue_before
    assert read_jsonl(screening_path) == screening_before


def test_manager_record_rejects_incomplete_order_score_and_unknown_evidence(
    tmp_path: Path,
):
    from trading_os.research_assets.manager_screening import (
        ManagerScreeningError,
        freeze_manager_screen_batch,
        record_manager_screen_decisions,
    )

    root, policy_path = _root(tmp_path)
    freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        frozen_at=CUTOFF + dt.timedelta(minutes=1),
        policy_path=policy_path,
    )
    submission = _submission(["CN:000001", "CN:000002"])
    submission["decisions"].reverse()
    with pytest.raises(ManagerScreeningError, match="complete batch exactly once"):
        record_manager_screen_decisions(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-001",
            submission=submission,
            recorded_at=CUTOFF + dt.timedelta(minutes=2),
        )

    submission = _submission(["CN:000001", "CN:000002"])
    submission["decisions"][0]["score"] = 99
    with pytest.raises(ManagerScreeningError, match="decision fields"):
        record_manager_screen_decisions(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-001",
            submission=submission,
            recorded_at=CUTOFF + dt.timedelta(minutes=2),
        )

    submission = _submission(["CN:000001", "CN:000002"])
    submission["decisions"][0]["evidence_ids"] = ["external:missing"]
    with pytest.raises(ManagerScreeningError, match="outside its dossier"):
        record_manager_screen_decisions(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-001",
            submission=submission,
            recorded_at=CUTOFF + dt.timedelta(minutes=2),
        )


def test_future_scope_accepts_manager_result_as_current_terminal(tmp_path: Path):
    from trading_os.research_assets.manager_screening import (
        freeze_manager_screen_batch,
        record_manager_screen_decisions,
    )
    from trading_os.research_assets.scope_workflow import freeze_all_a_scope

    root, policy_path = _root(tmp_path)
    freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        frozen_at=CUTOFF + dt.timedelta(minutes=1),
        policy_path=policy_path,
    )
    record_manager_screen_decisions(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        submission=_submission(["CN:000001", "CN:000002"]),
        recorded_at=CUTOFF + dt.timedelta(minutes=2),
    )
    next_scope = freeze_all_a_scope(
        root=root,
        run_id="2026-08-01-manager-screen-002",
        scope_cutoff=CUTOFF + dt.timedelta(days=1),
        frozen_at=CUTOFF + dt.timedelta(days=1),
        apply_intake=False,
    )
    assert next_scope["counts"]["current_protocol_terminal"] == 2
    assert next_scope["counts"]["baseline_backlog"] == 2


def test_future_scope_rejects_queue_sha_that_does_not_bind_result(tmp_path: Path):
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.manager_screening import (
        freeze_manager_screen_batch,
        record_manager_screen_decisions,
    )
    from trading_os.research_assets.scope_workflow import freeze_all_a_scope

    root, policy_path = _root(tmp_path)
    freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        frozen_at=CUTOFF + dt.timedelta(minutes=1),
        policy_path=policy_path,
    )
    record_manager_screen_decisions(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        submission=_submission(["CN:000001", "CN:000002"]),
        recorded_at=CUTOFF + dt.timedelta(minutes=2),
    )
    queue_path = root / "research_queue.jsonl"
    queue = read_jsonl(queue_path)
    next(item for item in queue if item["symbol"] == "CN:000001")[
        "manager_screen_result_sha256"
    ] = "0" * 64
    write_jsonl(queue_path, queue)

    next_scope = freeze_all_a_scope(
        root=root,
        run_id="2026-08-02-manager-screen-003",
        scope_cutoff=CUTOFF + dt.timedelta(days=2),
        frozen_at=CUTOFF + dt.timedelta(days=2),
        apply_intake=False,
    )
    assert next_scope["counts"]["current_protocol_terminal"] == 1
    assert next_scope["counts"]["baseline_backlog"] == 3


def test_status_rejects_batch_moved_outside_its_sealed_identity(tmp_path: Path):
    from trading_os.research_assets.manager_screening import (
        ManagerScreeningError,
        freeze_manager_screen_batch,
        manager_screen_status,
    )

    root, policy_path = _root(tmp_path)
    freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        frozen_at=CUTOFF + dt.timedelta(minutes=1),
        policy_path=policy_path,
    )
    run_dir = root / "manager-screen" / RUN_ID
    (run_dir / "batch-001").rename(run_dir / "batch-moved")

    with pytest.raises(ManagerScreeningError, match="sealed run and batch identity"):
        manager_screen_status(root=root, run_id=RUN_ID)


def test_manager_screen_cli_round_trip(tmp_path: Path, capsys):
    from trading_os.cli import main

    root, policy_path = _root(tmp_path)
    assert (
        main(
            [
                "coverage",
                "manager-screen-freeze",
                RUN_ID,
                "batch-001",
                "--root",
                str(root),
                "--policy",
                str(policy_path),
                "--batch-size",
                "2",
                "--at",
                (CUTOFF + dt.timedelta(minutes=1)).isoformat(),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["member_count"] == 2
    submission_path = tmp_path / "submission.json"
    submission_path.write_text(
        json.dumps(
            _submission(["CN:000001", "CN:000002"]),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    assert (
        main(
            [
                "coverage",
                "manager-screen-record",
                RUN_ID,
                "batch-001",
                "--root",
                str(root),
                "--input",
                str(submission_path),
                "--at",
                (CUTOFF + dt.timedelta(minutes=2)).isoformat(),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["by_route"]["send_to_analyst"] == 1
    assert (
        main(
            [
                "coverage",
                "manager-screen-status",
                RUN_ID,
                "--root",
                str(root),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["ok"] is True
