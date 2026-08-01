from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

import pytest

from tests.test_company_assets import _write_report, write_company
from tests.test_profile_workflow import _coverage, _seal_run_bound_stage_selection

RUN_ID = "2026-07-20-deep-completion-test"
CYCLE_ID = "2026-07-20-deep-cycle"
SYMBOL = "CN:600519"
RESEARCH_AGENT = "/root/deep-researcher"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SELECTION_AT = dt.datetime.fromisoformat("2026-07-20T09:00:00+08:00")
STARTED_AT = dt.datetime.fromisoformat("2026-07-20T10:00:00+08:00")
CLAIMS_AT = dt.datetime.fromisoformat("2026-07-20T11:00:00+08:00")
COMPLETED_AT = dt.datetime.fromisoformat("2026-07-20T12:00:00+08:00")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _environment(
    tmp_path: Path,
    *,
    claims_at: dt.datetime = CLAIMS_AT,
    information_cutoff: str = "2026-07-20T11:30:00+08:00",
    report_agent: str = RESEARCH_AGENT,
    bind_predecessor: bool = True,
    underwriting_capacity: int = 3,
    claim_task: bool = True,
) -> dict[str, object]:
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.profile_workflow import claim_profile_task
    from trading_os.research_assets.sealing import seal_json, verify_sealed

    _coverage(tmp_path)
    coverage_root = tmp_path / "coverage" / "cn-a"
    policy_path = tmp_path / "policies" / "research-allocation.json"
    policy_document = json.loads(policy_path.read_text(encoding="utf-8"))
    policy_document["payload"]["stage_capacity_per_run"]["underwriting"] = underwriting_capacity
    policy_path.write_text(
        json.dumps(policy_document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    manager_path = coverage_root / "manager-screen" / RUN_ID / "batch-001" / "result.json"
    decisive_question = "Can normalized owner earnings support a full underwriting case?"
    evidence_ids = ["snapshot:CN:600519"]
    manager_seal = seal_json(
        manager_path,
        {
            "schema_version": 1,
            "run_id": RUN_ID,
            "batch_id": "batch-001",
            "manager": {
                "agent": "/root/investment-manager",
                "model": "test-manager",
                "tools": ["sealed manager-screen result"],
            },
            "decisions": [
                {
                    "symbol": SYMBOL,
                    "route": "send_to_analyst",
                    "decisive_question": decisive_question,
                    "evidence_ids": evidence_ids,
                }
            ],
            "portfolio_action": None,
        },
        artifact_type="manager_screen_result",
        sealed_at=SELECTION_AT - dt.timedelta(hours=1),
    )
    selection_path = _seal_run_bound_stage_selection(
        tmp_path,
        cycle_id=CYCLE_ID,
        manager_screen_run_id=RUN_ID,
        evaluated_stage="scoped_research",
        next_stage="deep_research",
        symbol=SYMBOL,
        policy=policy_document["payload"],
        sealed_at=SELECTION_AT,
    )
    selection_seal = verify_sealed(selection_path)
    selection_relative = selection_path.relative_to(tmp_path).as_posix()

    company_dir = write_company(tmp_path, date="2026-07-19")
    meta_path = company_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    prior = dict(meta["reports"]["history"][-1])
    report_id = "CN-600519-2026-07-20-initial-research"
    claims_path = company_dir / "evidence" / "deep-research-claims.json"
    claims_seal = seal_json(
        claims_path,
        {
            "schema_version": 2,
            "report_id": report_id,
            "symbol": SYMBOL,
            "claims": [
                {
                    "claim_id": "claim-business-quality",
                    "category": "business",
                    "claim": "Normalized owner earnings are supported by filings.",
                    "verification_metrics": ["cash conversion"],
                    "falsifiers": ["persistent cash conversion collapse"],
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
                "conclusion": "Wait for a sufficient margin of safety.",
            },
        },
        artifact_type="research_claims",
        sealed_at=claims_at,
    )
    report_path, report_front = _write_report(
        company_dir,
        date="2026-07-20",
        report_id=report_id,
        metadata_overrides={
            "information_cutoff": information_cutoff,
            "agent_id": report_agent,
            "predecessor_reports": [prior["report_id"]] if bind_predecessor else [],
            "sealed_artifacts": [claims_path.relative_to(company_dir).as_posix()],
        },
    )
    report_relative_company = report_path.relative_to(company_dir).as_posix()
    meta["reports"]["history"].append(
        {
            "report_id": report_id,
            "path": report_relative_company,
            "report_type": "initial_research",
            "as_of": "2026-07-20",
            "sha256": _sha256(report_path),
        }
    )
    meta["reports"]["latest"] = report_relative_company
    meta["reports"]["latest_by_type"]["initial_research"] = report_relative_company
    meta["research"]["information_cutoff"] = information_cutoff
    meta["updated_at"] = COMPLETED_AT.isoformat()
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    queue = read_jsonl(coverage_root / "research_queue.jsonl")
    queue[0].update(
        {
            "task_type": "deep_research",
            "status": "pending",
            "reason": "sealed scoped selection funded deep research",
            "assigned_agent": None,
            "started_at": None,
            "finished_at": None,
            "result_path": (
                "coverage/cn-a/profiles/2026-07-20-deep-cycle/"
                "scoped-research-evaluation-600519.json"
            ),
            "failure_reason": None,
            "next_action": "complete formal company research",
            "effort_budget_hours": 24.0,
            "preceding_stage": "scoped_research",
            "stop_conditions": ["thesis disproven"],
            "manager_screen_run_id": RUN_ID,
            "manager_screen_batch_id": "batch-001",
            "manager_screen_route": "send_to_analyst",
            "manager_screen_result_path": manager_path.relative_to(tmp_path).as_posix(),
            "manager_screen_result_sha256": manager_seal.sha256,
            "decisive_question": decisive_question,
            "evidence_ids": evidence_ids,
            "profile_cycle_id": CYCLE_ID,
            "profile_scoped_selection_path": selection_relative,
            "profile_scoped_selection_sha256": selection_seal.sha256,
            "stage_history": [
                {
                    "stage": "scoped_research",
                    "status": "completed",
                    "started_at": "2026-07-20T08:00:00+08:00",
                    "finished_at": "2026-07-20T08:30:00+08:00",
                    "agent": "/root/scoped-researcher",
                    "result_path": (
                        "coverage/cn-a/profiles/2026-07-20-deep-cycle/"
                        "scoped-research-profile-600519.json"
                    ),
                    "evaluation_path": (
                        "coverage/cn-a/profiles/2026-07-20-deep-cycle/"
                        "scoped-research-evaluation-600519.json"
                    ),
                    "next_stage": "deep_candidate",
                }
            ],
        }
    )
    write_jsonl(coverage_root / "research_queue.jsonl", queue)
    screening = read_jsonl(coverage_root / "screening.jsonl")
    screening[0].update(
        {
            "decision": "deep_research",
            "reason": "sealed scoped selection funded deep research",
            "evidence": [
                f"stage_selection:{selection_relative}",
                f"stage_selection_sha256:{selection_seal.sha256}",
            ],
            "next_action": "complete formal company research",
            "manager_screen_run_id": RUN_ID,
            "manager_screen_batch_id": "batch-001",
            "manager_screen_route": "send_to_analyst",
            "manager_screen_result_path": manager_path.relative_to(tmp_path).as_posix(),
            "manager_screen_result_sha256": manager_seal.sha256,
            "decisive_question": decisive_question,
            "evidence_ids": evidence_ids,
            "profile_cycle_id": CYCLE_ID,
        }
    )
    write_jsonl(coverage_root / "screening.jsonl", screening)
    if claim_task:
        claim_profile_task(
            root=coverage_root,
            agent=RESEARCH_AGENT,
            symbol=SYMBOL,
            stage="deep_research",
            claimed_at=STARTED_AT,
        )
    report_relative = report_path.relative_to(tmp_path).as_posix()
    claims_relative = claims_path.relative_to(tmp_path).as_posix()
    submission = {
        "schema_version": 1,
        "symbol": SYMBOL,
        "research_agent": RESEARCH_AGENT,
        "profile_cycle_id": CYCLE_ID,
        "manager_screen_run_id": RUN_ID,
        "scoped_selection_path": selection_relative,
        "scoped_selection_sha256": selection_seal.sha256,
        "report_path": report_relative,
        "report_sha256": _sha256(report_path),
        "claims_path": claims_relative,
        "claims_sha256": claims_seal.sha256,
    }
    return {
        "repository": tmp_path,
        "coverage_root": coverage_root,
        "company_dir": company_dir,
        "report_path": report_path,
        "claims_path": claims_path,
        "selection_path": selection_path,
        "submission": submission,
        "report_front": report_front,
    }


def _full_market_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, object]:
    from tests.test_manager_screen_full_market_allocation_v3 import (
        RECORDED_AT as FULL_MARKET_RECORDED_AT,
    )
    from tests.test_manager_screen_full_market_allocation_v3 import (
        RUN_ID as FULL_MARKET_RUN_ID,
    )
    from tests.test_manager_screen_full_market_allocation_v3 import (
        _prepare as prepare_full_market,
    )
    from tests.test_manager_screen_full_market_allocation_v3 import (
        _ready_full_market,
    )
    from tests.test_manager_screen_full_market_allocation_v3 import (
        _record as record_full_market,
    )
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.profile_workflow import claim_profile_task
    from trading_os.research_assets.sealing import seal_json, verify_sealed

    symbol = "CN:000001"
    ticker = symbol.split(":", 1)[1]
    coverage_root = _ready_full_market(tmp_path, monkeypatch)
    prepare_full_market(coverage_root)
    allocation = record_full_market(coverage_root, {symbol})
    repository = coverage_root.parent.parent.resolve()
    policy_path = repository / "policies" / "research-allocation.json"
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_bytes((PROJECT_ROOT / "policies" / "research-allocation.json").read_bytes())
    cycle_id = str(allocation["profile_cycle_id"])
    selection_at = FULL_MARKET_RECORDED_AT + dt.timedelta(minutes=10)
    started_at = selection_at + dt.timedelta(minutes=10)
    claims_at = started_at + dt.timedelta(minutes=10)
    completed_at = started_at + dt.timedelta(minutes=30)
    selection_path = _seal_run_bound_stage_selection(
        repository,
        cycle_id=cycle_id,
        manager_screen_run_id=FULL_MARKET_RUN_ID,
        evaluated_stage="scoped_research",
        next_stage="deep_research",
        symbol=symbol,
        sealed_at=selection_at,
    )
    selection_seal = verify_sealed(selection_path)
    selection_relative = selection_path.relative_to(repository).as_posix()

    original_company = write_company(repository, date="2026-07-30")
    company_dir = repository / "research" / "companies" / "CN" / ticker
    original_company.rename(company_dir)
    meta_path = company_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["identity"]["symbol"] = symbol
    meta["identity"]["ticker"] = ticker
    prior = dict(meta["reports"]["history"][-1])
    prior_path = company_dir / prior["path"]
    prior_path.write_text(
        prior_path.read_text(encoding="utf-8").replace("CN:600519", symbol),
        encoding="utf-8",
    )
    prior["sha256"] = _sha256(prior_path)
    meta["reports"]["history"][-1] = prior

    report_id = f"CN-{ticker}-2026-07-31-initial-research"
    claims_path = company_dir / "evidence" / "deep-research-claims.json"
    claims_seal = seal_json(
        claims_path,
        {
            "schema_version": 2,
            "report_id": report_id,
            "symbol": symbol,
            "claims": [
                {
                    "claim_id": "claim-full-market-owner-earnings",
                    "category": "business",
                    "claim": "Normalized owner earnings are supported by filings.",
                    "verification_metrics": ["cash conversion"],
                    "falsifiers": ["persistent cash conversion collapse"],
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
                "conclusion": "Wait for a sufficient margin of safety.",
            },
        },
        artifact_type="research_claims",
        sealed_at=claims_at,
    )
    report_path, _ = _write_report(
        company_dir,
        date="2026-07-31",
        report_id=report_id,
        metadata_overrides={
            "information_cutoff": (completed_at - dt.timedelta(minutes=5)).isoformat(),
            "agent_id": RESEARCH_AGENT,
            "predecessor_reports": [prior["report_id"]],
            "sealed_artifacts": [claims_path.relative_to(company_dir).as_posix()],
        },
    )
    report_path.write_text(
        report_path.read_text(encoding="utf-8").replace("CN:600519", symbol),
        encoding="utf-8",
    )
    report_relative_company = report_path.relative_to(company_dir).as_posix()
    meta["reports"]["history"].append(
        {
            "report_id": report_id,
            "path": report_relative_company,
            "report_type": "initial_research",
            "as_of": "2026-07-31",
            "sha256": _sha256(report_path),
        }
    )
    meta["reports"]["latest"] = report_relative_company
    meta["reports"]["latest_by_type"]["initial_research"] = report_relative_company
    meta["research"]["information_cutoff"] = (completed_at - dt.timedelta(minutes=5)).isoformat()
    meta["updated_at"] = completed_at.isoformat()
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    queue_path = coverage_root / "research_queue.jsonl"
    queue = read_jsonl(queue_path)
    queued = next(row for row in queue if row["symbol"] == symbol)
    queued.update(
        {
            "task_type": "deep_research",
            "status": "pending",
            "reason": "sealed scoped selection funded deep research",
            "assigned_agent": None,
            "started_at": None,
            "finished_at": None,
            "result_path": f"coverage/cn-a/profiles/{cycle_id}/scoped-evaluation.json",
            "failure_reason": None,
            "next_action": "complete formal company research",
            "effort_budget_hours": 24.0,
            "preceding_stage": "scoped_research",
            "stop_conditions": ["thesis disproven"],
            "profile_cycle_id": cycle_id,
            "profile_scoped_selection_path": selection_relative,
            "profile_scoped_selection_sha256": selection_seal.sha256,
            "stage_history": list(queued.get("stage_history") or [])
            + [
                {
                    "stage": "scoped_research",
                    "status": "completed",
                    "started_at": (selection_at - dt.timedelta(minutes=5)).isoformat(),
                    "finished_at": selection_at.isoformat(),
                    "agent": "/root/scoped-researcher",
                    "result_path": f"coverage/cn-a/profiles/{cycle_id}/scoped-profile.json",
                    "evaluation_path": (
                        f"coverage/cn-a/profiles/{cycle_id}/scoped-evaluation.json"
                    ),
                    "next_stage": "deep_candidate",
                }
            ],
        }
    )
    write_jsonl(queue_path, queue)
    screening_path = coverage_root / "screening.jsonl"
    screening = read_jsonl(screening_path)
    screen = next(row for row in screening if row["symbol"] == symbol)
    screen.update(
        {
            "decision": "deep_research",
            "reason": "sealed scoped selection funded deep research",
            "evidence": list(screen.get("evidence") or [])
            + [
                f"stage_selection:{selection_relative}",
                f"stage_selection_sha256:{selection_seal.sha256}",
            ],
            "next_action": "complete formal company research",
        }
    )
    write_jsonl(screening_path, screening)
    claim_profile_task(
        root=coverage_root,
        agent=RESEARCH_AGENT,
        symbol=symbol,
        stage="deep_research",
        claimed_at=started_at,
    )
    submission = {
        "schema_version": 1,
        "symbol": symbol,
        "research_agent": RESEARCH_AGENT,
        "profile_cycle_id": cycle_id,
        "manager_screen_run_id": FULL_MARKET_RUN_ID,
        "scoped_selection_path": selection_relative,
        "scoped_selection_sha256": selection_seal.sha256,
        "report_path": report_path.relative_to(repository).as_posix(),
        "report_sha256": _sha256(report_path),
        "claims_path": claims_path.relative_to(repository).as_posix(),
        "claims_sha256": claims_seal.sha256,
    }
    return {
        "repository": repository,
        "coverage_root": coverage_root,
        "symbol": symbol,
        "submission": submission,
        "completed_at": completed_at,
        "allocation": allocation,
    }


def _record(env: dict[str, object]) -> dict[str, object]:
    from trading_os.research_assets.deep_research_completion import (
        record_deep_research_completion,
    )

    return record_deep_research_completion(
        root=env["coverage_root"],
        symbol=SYMBOL,
        submission=env["submission"],
        completed_at=COMPLETED_AT,
    )


def test_records_sealed_deep_completion_and_waits_for_underwriting(tmp_path: Path):
    from trading_os.research_assets.coverage_store import read_jsonl
    from trading_os.research_assets.deep_research_completion import (
        deep_research_completion_status,
    )
    from trading_os.research_assets.sealing import verify_sealed

    env = _environment(tmp_path)

    result = _record(env)

    assert result["finalized"] is True
    assert result["underwriting_budget_purchased"] is False
    receipt_path = tmp_path / str(result["receipt_path"])
    assert verify_sealed(receipt_path).artifact_type == "deep_research_completion"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["schema_version"] == 2
    assert receipt["claim_attempt"]["agent"] == RESEARCH_AGENT
    assert receipt["claim_attempt"]["attempt_number"] == 1
    assert receipt["effective_manager_authority"]["agent"] == ("/root/investment-manager")
    queue = read_jsonl(Path(env["coverage_root"]) / "research_queue.jsonl")[0]
    assert queue["status"] == "completed"
    assert queue["result_path"] == result["report_path"]
    completed = [
        row
        for row in queue["stage_history"]
        if row.get("stage") == "deep_research" and row.get("status") == "completed"
    ]
    assert len(completed) == 1
    assert completed[0]["completion_sha256"] == result["receipt_sha256"]
    assert completed[0]["claims_sha256"] == result["claims_sha256"]
    status = deep_research_completion_status(
        root=env["coverage_root"],
        symbol=SYMBOL,
    )
    assert status["finalized"] is True


def test_forged_minimal_deep_completion_history_cannot_release_agent_capacity(
    tmp_path: Path,
):
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.profile_stage_claims import (
        ProfileStageClaimError,
        assert_agent_profile_stage_claim_capacity,
        verify_active_profile_stage_claim,
    )
    from trading_os.research_assets.sealing import seal_json

    env = _environment(tmp_path)
    root = Path(env["coverage_root"])
    queue_path = root / "research_queue.jsonl"
    running = read_jsonl(queue_path)[0]
    claim = verify_active_profile_stage_claim(
        root=root,
        queue_record=running,
        stage="deep_research",
    )
    receipt_path = (
        root
        / "profiles"
        / CYCLE_ID
        / "deep-research-completions"
        / "600519.json"
    )
    forged = {
        "schema_version": 2,
        "symbol": SYMBOL,
        "research_agent": RESEARCH_AGENT,
        "profile_cycle_id": CYCLE_ID,
        "manager_screen_run_id": RUN_ID,
        "completed_at": COMPLETED_AT.isoformat(),
        "claim_attempt": claim,
    }
    sealed = seal_json(
        receipt_path,
        forged,
        artifact_type="deep_research_completion",
        sealed_at=COMPLETED_AT,
    )
    repository = root.parent.parent
    receipt_relative = receipt_path.relative_to(repository).as_posix()
    running.update(
        {
            "status": "completed",
            "finished_at": COMPLETED_AT.isoformat(),
            "stage_history": list(running.get("stage_history") or [])
            + [
                {
                    "stage": "deep_research",
                    "status": "completed",
                    "agent": RESEARCH_AGENT,
                    "started_at": STARTED_AT.isoformat(),
                    "finished_at": COMPLETED_AT.isoformat(),
                    "claim_path": claim["path"],
                    "claim_sha256": claim["sha256"],
                    "claim_attempt_number": claim["attempt_number"],
                    "completion_path": receipt_relative,
                    "completion_sha256": sealed.sha256,
                }
            ],
        }
    )
    write_jsonl(queue_path, [running])

    with pytest.raises(ProfileStageClaimError, match="unrecognized queue drift"):
        assert_agent_profile_stage_claim_capacity(
            root=root,
            queue_records=[running],
            agent=RESEARCH_AGENT,
            requested_symbol=None,
        )


def test_identical_record_is_idempotent(tmp_path: Path):
    env = _environment(tmp_path)
    first = _record(env)

    second = _record(env)

    assert second["idempotent"] is True
    assert second["receipt_sha256"] == first["receipt_sha256"]


def test_cli_records_and_revalidates_deep_completion(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    from trading_os.cli import main

    env = _environment(tmp_path)
    submission_path = tmp_path / "deep-completion-submission.json"
    submission_path.write_text(
        json.dumps(env["submission"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    assert (
        main(
            [
                "coverage",
                "deep-research-complete",
                SYMBOL,
                "--root",
                str(env["coverage_root"]),
                "--input",
                str(submission_path),
                "--at",
                COMPLETED_AT.isoformat(),
            ]
        )
        == 0
    )
    recorded = json.loads(capsys.readouterr().out)
    assert recorded["ok"] is True
    assert recorded["finalized"] is True
    assert (
        main(
            [
                "coverage",
                "deep-research-completion-status",
                SYMBOL,
                "--root",
                str(env["coverage_root"]),
            ]
        )
        == 0
    )
    status = json.loads(capsys.readouterr().out)
    assert status["ok"] is True
    assert status["finalized"] is True


def test_full_market_funded_grant_completes_without_legacy_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from trading_os.research_assets.deep_research_completion import (
        record_deep_research_completion,
    )

    env = _full_market_environment(tmp_path, monkeypatch)

    result = record_deep_research_completion(
        root=env["coverage_root"],
        symbol=env["symbol"],
        submission=env["submission"],
        completed_at=env["completed_at"],
    )

    receipt = json.loads(
        (Path(env["repository"]) / result["receipt_path"]).read_text(encoding="utf-8")
    )
    assert receipt["manager_predecessor"]["kind"] == (
        "manager_screen_full_market_allocation_v3_result"
    )
    assert receipt["manager_predecessor"]["decision"] == "fund_quick_profile"
    assert receipt["manager_predecessor"]["sha256"] == env["allocation"]["result_sha256"]
    assert receipt["effective_manager_authority"]["source_type"] == (
        "manager_screen_full_market_allocation_v3_result"
    )
    assert (
        receipt["effective_manager_authority"]["source_sha256"]
        == env["allocation"]["result_sha256"]
    )
    assert receipt["effective_manager_authority"]["agent"] != ("/root/early-batch-manager")


def test_full_market_grant_cannot_downgrade_when_queue_bindings_are_deleted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.deep_research_completion import (
        DeepResearchCompletionError,
        record_deep_research_completion,
    )

    env = _full_market_environment(tmp_path, monkeypatch)
    queue_path = Path(env["coverage_root"]) / "research_queue.jsonl"
    queue = read_jsonl(queue_path)
    queued = next(row for row in queue if row["symbol"] == env["symbol"])
    for field in (
        "manager_screen_allocation_result_path",
        "manager_screen_allocation_result_sha256",
        "manager_screen_allocation_candidate_sha256",
        "manager_screen_allocation_decision",
    ):
        queued.pop(field, None)
    write_jsonl(queue_path, queue)

    with pytest.raises(DeepResearchCompletionError, match="active sealed claim"):
        record_deep_research_completion(
            root=env["coverage_root"],
            symbol=env["symbol"],
            submission=env["submission"],
            completed_at=env["completed_at"],
        )


def test_full_market_candidate_sha_mismatch_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.deep_research_completion import (
        DeepResearchCompletionError,
        record_deep_research_completion,
    )

    env = _full_market_environment(tmp_path, monkeypatch)
    queue_path = Path(env["coverage_root"]) / "research_queue.jsonl"
    queue = read_jsonl(queue_path)
    queued = next(row for row in queue if row["symbol"] == env["symbol"])
    queued["manager_screen_allocation_candidate_sha256"] = "f" * 64
    write_jsonl(queue_path, queue)

    with pytest.raises(DeepResearchCompletionError, match="active sealed claim"):
        record_deep_research_completion(
            root=env["coverage_root"],
            symbol=env["symbol"],
            submission=env["submission"],
            completed_at=env["completed_at"],
        )


def test_replay_repairs_projection_after_second_jsonl_write_crashes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import trading_os.research_assets.deep_research_completion as workflow

    env = _environment(tmp_path)
    real_write = workflow.write_jsonl
    calls = 0

    def fail_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated crash")
        return real_write(*args, **kwargs)

    monkeypatch.setattr(workflow, "write_jsonl", fail_second)
    with pytest.raises(OSError, match="simulated crash"):
        _record(env)
    monkeypatch.setattr(workflow, "write_jsonl", real_write)

    partial = workflow.deep_research_completion_status(
        root=env["coverage_root"],
        symbol=SYMBOL,
    )
    assert partial["queue_projected"] is True
    assert partial["screening_projected"] is False
    assert partial["finalized"] is False

    repaired = _record(env)

    assert repaired["finalized"] is True
    assert repaired["idempotent"] is False


def test_cli_replay_uses_sealed_completion_time_after_projection_crash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    import trading_os.cli as cli
    import trading_os.research_assets.deep_research_completion as workflow

    env = _environment(tmp_path)
    real_write = workflow.write_jsonl
    calls = 0

    def fail_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated crash")
        return real_write(*args, **kwargs)

    monkeypatch.setattr(workflow, "write_jsonl", fail_second)
    with pytest.raises(OSError, match="simulated crash"):
        _record(env)
    monkeypatch.setattr(workflow, "write_jsonl", real_write)

    submission_path = tmp_path / "deep-completion-replay-submission.json"
    submission_path.write_text(
        json.dumps(env["submission"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    real_timestamp = cli._timestamp

    def later_default(value: str | None) -> dt.datetime:
        if value is None:
            return COMPLETED_AT + dt.timedelta(days=1)
        return real_timestamp(value)

    monkeypatch.setattr(cli, "_timestamp", later_default)
    assert (
        cli.main(
            [
                "coverage",
                "deep-research-complete",
                SYMBOL,
                "--root",
                str(env["coverage_root"]),
                "--input",
                str(submission_path),
            ]
        )
        == 0
    )
    replayed = json.loads(capsys.readouterr().out)
    assert replayed["finalized"] is True
    assert replayed["idempotent"] is False
    assert replayed["completed_at"] == COMPLETED_AT.isoformat()


def test_replay_rejects_unrecognized_queue_drift(tmp_path: Path):
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.deep_research_completion import (
        DeepResearchCompletionError,
    )

    env = _environment(tmp_path)
    _record(env)
    queue_path = Path(env["coverage_root"]) / "research_queue.jsonl"
    queue = read_jsonl(queue_path)
    queue[0]["reason"] = "unrecognized mutation"
    write_jsonl(queue_path, queue)

    with pytest.raises(DeepResearchCompletionError, match="unrecognized drift"):
        _record(env)


@pytest.mark.parametrize(
    ("environment_changes", "message"),
    [
        ({"claims_at": SELECTION_AT - dt.timedelta(minutes=1)}, "claims"),
        ({"information_cutoff": "2026-07-20T08:59:00+08:00"}, "report predates"),
        ({"report_agent": "/root/other-agent"}, "metadata"),
        ({"bind_predecessor": False}, "prior latest report"),
    ],
)
def test_rejects_non_new_or_unbound_formal_report(
    tmp_path: Path,
    environment_changes: dict[str, object],
    message: str,
):
    from trading_os.research_assets.deep_research_completion import (
        DeepResearchCompletionError,
    )

    env = _environment(tmp_path, **environment_changes)

    with pytest.raises(DeepResearchCompletionError, match=message):
        _record(env)


def test_rejects_wrong_selection_sha_before_sealing_receipt(tmp_path: Path):
    from trading_os.research_assets.deep_research_completion import (
        DeepResearchCompletionError,
    )

    env = _environment(tmp_path)
    submission = dict(env["submission"])
    submission["scoped_selection_sha256"] = "f" * 64
    env["submission"] = submission

    with pytest.raises(DeepResearchCompletionError, match="running claim"):
        _record(env)
    receipt = (
        Path(env["coverage_root"])
        / "profiles"
        / CYCLE_ID
        / "deep-research-completions"
        / "600519.json"
    )
    assert not receipt.exists()


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("status", "pending", "running claim"),
        ("assigned_agent", "/root/other-agent", "running claim"),
        ("started_at", "2026-07-20T12:01:00+08:00", "later than its claim"),
        ("profile_cycle_id", "different-cycle", "running claim"),
    ],
)
def test_rejects_queue_claim_drift(
    tmp_path: Path,
    field: str,
    value: object,
    message: str,
):
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.deep_research_completion import (
        DeepResearchCompletionError,
    )

    env = _environment(tmp_path)
    queue_path = Path(env["coverage_root"]) / "research_queue.jsonl"
    queue = read_jsonl(queue_path)
    queue[0][field] = value
    write_jsonl(queue_path, queue)

    with pytest.raises(DeepResearchCompletionError, match=message):
        _record(env)


def test_rejects_synchronized_queue_submission_and_report_agent_forgery(
    tmp_path: Path,
) -> None:
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.deep_research_completion import (
        DeepResearchCompletionError,
    )

    env = _environment(tmp_path)
    forged_agent = "/root/forged-researcher"
    queue_path = Path(env["coverage_root"]) / "research_queue.jsonl"
    queue = read_jsonl(queue_path)
    queue[0]["assigned_agent"] = forged_agent
    write_jsonl(queue_path, queue)

    report_path = Path(env["report_path"])
    report_path.write_text(
        report_path.read_text(encoding="utf-8").replace(
            RESEARCH_AGENT,
            forged_agent,
        ),
        encoding="utf-8",
    )
    company_dir = Path(env["company_dir"])
    meta_path = company_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["reports"]["history"][-1]["sha256"] = _sha256(report_path)
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    submission = dict(env["submission"])
    submission["research_agent"] = forged_agent
    submission["report_sha256"] = _sha256(report_path)
    env["submission"] = submission

    with pytest.raises(DeepResearchCompletionError, match="active sealed claim"):
        _record(env)


def test_release_closes_old_attempt_and_retry_attempt_can_complete(tmp_path: Path) -> None:
    from trading_os.research_assets.deep_research_completion import (
        DeepResearchCompletionError,
    )
    from trading_os.research_assets.profile_workflow import (
        claim_profile_task,
        release_profile_task,
    )

    env = _environment(tmp_path)
    released_at = STARTED_AT + dt.timedelta(minutes=10)
    release_profile_task(
        root=env["coverage_root"],
        agent=RESEARCH_AGENT,
        symbol=SYMBOL,
        failure_reason="transient source failure",
        released_at=released_at,
    )

    with pytest.raises(DeepResearchCompletionError, match="running claim"):
        _record(env)

    claim_profile_task(
        root=env["coverage_root"],
        agent=RESEARCH_AGENT,
        symbol=SYMBOL,
        stage="deep_research",
        claimed_at=released_at + dt.timedelta(minutes=5),
    )
    result = _record(env)
    receipt = json.loads((tmp_path / str(result["receipt_path"])).read_text(encoding="utf-8"))
    assert receipt["claim_attempt"]["attempt_number"] == 2


def test_claim_receipt_only_crash_is_replayed_without_second_attempt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_os.research_assets.profile_workflow as workflow

    env = _environment(tmp_path, claim_task=False)
    real_write = workflow.write_jsonl

    def fail_projection(*args, **kwargs):
        raise OSError("simulated claim projection crash")

    monkeypatch.setattr(workflow, "write_jsonl", fail_projection)
    with pytest.raises(OSError, match="claim projection crash"):
        workflow.claim_profile_task(
            root=env["coverage_root"],
            agent=RESEARCH_AGENT,
            symbol=SYMBOL,
            stage="deep_research",
            claimed_at=STARTED_AT,
        )
    monkeypatch.setattr(workflow, "write_jsonl", real_write)

    repaired = workflow.claim_profile_task(
        root=env["coverage_root"],
        agent=RESEARCH_AGENT,
        symbol=SYMBOL,
        stage="deep_research",
        claimed_at=STARTED_AT,
    )
    attempts = (
        Path(env["coverage_root"])
        / "profiles"
        / CYCLE_ID
        / "stage-claim-attempts"
        / "deep_research"
        / "600519"
    )
    assert repaired["assigned_agent"] == RESEARCH_AGENT
    assert [path.name for path in attempts.iterdir()] == ["attempt-000001"]


def test_release_receipt_only_crash_is_replayed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_os.research_assets.profile_workflow as workflow

    env = _environment(tmp_path)
    real_write = workflow.write_jsonl
    released_at = STARTED_AT + dt.timedelta(minutes=10)

    def fail_projection(*args, **kwargs):
        raise OSError("simulated release projection crash")

    monkeypatch.setattr(workflow, "write_jsonl", fail_projection)
    with pytest.raises(OSError, match="release projection crash"):
        workflow.release_profile_task(
            root=env["coverage_root"],
            agent=RESEARCH_AGENT,
            symbol=SYMBOL,
            failure_reason="transient source failure",
            released_at=released_at,
        )
    monkeypatch.setattr(workflow, "write_jsonl", real_write)

    repaired = workflow.release_profile_task(
        root=env["coverage_root"],
        agent=RESEARCH_AGENT,
        symbol=SYMBOL,
        failure_reason="transient source failure",
        released_at=released_at + dt.timedelta(minutes=5),
    )
    assert repaired["status"] == "pending"
    assert repaired["profile_stage_claim_release_path"].endswith("release.json")
    assert repaired["attempt_history"][-1]["finished_at"] == released_at.isoformat()


@pytest.mark.parametrize(
    ("tamper", "message"),
    [
        ("delete", "lost its research queue row"),
        ("assigned_agent", "unrecognized queue drift"),
    ],
)
def test_sealed_active_claim_blocks_second_company_after_queue_tampering(
    tmp_path: Path,
    tamper: str,
    message: str,
) -> None:
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.profile_workflow import (
        ResearchAllocationError,
        claim_profile_task,
    )

    env = _environment(tmp_path)
    queue_path = Path(env["coverage_root"]) / "research_queue.jsonl"
    queue = read_jsonl(queue_path)
    second = dict(queue[0])
    second.update(
        {
            "symbol": "CN:600520",
            "status": "pending",
            "assigned_agent": None,
            "started_at": None,
            "finished_at": None,
            "failure_reason": None,
        }
    )
    second.pop("profile_stage_claim_attempt_path", None)
    second.pop("profile_stage_claim_attempt_sha256", None)
    if tamper == "delete":
        queue = [second]
    else:
        queue[0]["assigned_agent"] = "/root/forged-researcher"
        queue.append(second)
    write_jsonl(queue_path, queue)

    with pytest.raises(ResearchAllocationError, match=message):
        claim_profile_task(
            root=env["coverage_root"],
            agent=RESEARCH_AGENT,
            symbol="CN:600520",
            stage="deep_research",
            claimed_at=STARTED_AT + dt.timedelta(minutes=5),
        )


def test_sealed_run_policy_snapshot_survives_live_policy_drift(tmp_path: Path):
    env = _environment(tmp_path)
    policy_path = tmp_path / "policies" / "research-allocation.json"
    policy_path.write_text(
        policy_path.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )

    recorded = _record(env)
    assert recorded["symbol"] == SYMBOL


def test_status_revalidates_claims_seal(tmp_path: Path):
    from trading_os.research_assets.deep_research_completion import (
        DeepResearchCompletionError,
        deep_research_completion_status,
    )

    env = _environment(tmp_path)
    _record(env)
    claims_path = Path(env["claims_path"])
    claims_path.write_bytes(claims_path.read_bytes() + b"\n")

    with pytest.raises(DeepResearchCompletionError, match="artifact"):
        deep_research_completion_status(
            root=env["coverage_root"],
            symbol=SYMBOL,
        )


def test_generic_reconcile_blocks_manager_bound_deep_research(tmp_path: Path):
    from trading_os.research_assets.coverage_store import (
        read_jsonl,
        reconcile_research_queue,
        write_jsonl,
    )

    company_dir = write_company(tmp_path, date="2026-07-20")
    coverage_root = tmp_path / "coverage" / "cn-a"
    write_jsonl(
        coverage_root / "research_queue.jsonl",
        [
            {
                "symbol": SYMBOL,
                "name": "贵州茅台",
                "task_type": "deep_research",
                "priority": 1,
                "status": "running",
                "reason": "manager-bound deep work",
                "target_company_dir": company_dir.relative_to(tmp_path).as_posix(),
                "assigned_agent": RESEARCH_AGENT,
                "started_at": STARTED_AT.isoformat(),
                "finished_at": None,
                "result_path": None,
                "failure_reason": None,
                "next_action": "formal completion",
                "effort_budget_hours": 24.0,
                "preceding_stage": "scoped_research",
                "stop_conditions": ["thesis disproven"],
                "manager_screen_run_id": RUN_ID,
                "profile_scoped_selection_path": "coverage/cn-a/profiles/x/selection.json",
            }
        ],
    )

    result = reconcile_research_queue(
        coverage_root,
        tmp_path / "research",
        apply=True,
    )

    assert result["change_count"] == 0
    assert result["blocked_count"] == 1
    assert "formal sealed" in result["blocked"][0]["error"]
    assert read_jsonl(coverage_root / "research_queue.jsonl")[0]["status"] == "running"


def test_generic_reconcile_cannot_downgrade_after_manager_bindings_are_deleted(
    tmp_path: Path,
):
    from trading_os.research_assets.coverage_store import (
        read_jsonl,
        reconcile_research_queue,
        write_jsonl,
    )

    company_dir = write_company(tmp_path, date="2026-07-20")
    coverage_root = tmp_path / "coverage" / "cn-a"
    write_jsonl(
        coverage_root / "research_queue.jsonl",
        [
            {
                "symbol": SYMBOL,
                "name": "贵州茅台",
                "task_type": "deep_research",
                "priority": 1,
                "status": "running",
                "reason": "all mutable manager bindings were deleted",
                "target_company_dir": company_dir.relative_to(tmp_path).as_posix(),
                "assigned_agent": RESEARCH_AGENT,
                "started_at": STARTED_AT.isoformat(),
                "finished_at": None,
                "result_path": None,
                "failure_reason": None,
                "next_action": "formal completion",
                "effort_budget_hours": 24.0,
                "preceding_stage": "scoped_research",
                "stop_conditions": ["thesis disproven"],
            }
        ],
    )

    result = reconcile_research_queue(
        coverage_root,
        tmp_path / "research",
        apply=True,
    )

    assert result["change_count"] == 0
    assert result["blocked_count"] == 1
    assert read_jsonl(coverage_root / "research_queue.jsonl")[0]["status"] == "running"


def test_generic_reconcile_fails_closed_when_provenance_is_rewritten_as_legacy(
    tmp_path: Path,
):
    from trading_os.research_assets.coverage_store import (
        read_jsonl,
        reconcile_research_queue,
        write_jsonl,
    )

    company_dir = write_company(tmp_path, date="2026-07-20")
    coverage_root = tmp_path / "coverage" / "cn-a"
    write_jsonl(
        coverage_root / "research_queue.jsonl",
        [
            {
                "symbol": SYMBOL,
                "name": "贵州茅台",
                "task_type": "deep_research",
                "priority": 1,
                "status": "pending",
                "reason": "modern deep work with all provenance removed",
                "target_company_dir": company_dir.relative_to(tmp_path).as_posix(),
                "assigned_agent": None,
                "started_at": None,
                "finished_at": None,
                "result_path": None,
                "failure_reason": None,
                "next_action": "legacy reconcile",
                "effort_budget_hours": 24.0,
                "preceding_stage": "legacy",
                "stop_conditions": ["thesis disproven"],
            }
        ],
    )

    result = reconcile_research_queue(
        coverage_root,
        tmp_path / "research",
        apply=True,
    )

    assert result["change_count"] == 0
    assert result["blocked_count"] == 1
    assert "formal sealed" in result["blocked"][0]["error"]
    assert read_jsonl(coverage_root / "research_queue.jsonl")[0]["status"] == "pending"
