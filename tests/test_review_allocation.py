from __future__ import annotations

import datetime as dt
import hashlib
import json
import shutil
from pathlib import Path

import pytest

APPROVED_AT = dt.datetime.fromisoformat("2026-07-31T18:00:00+08:00")
RUN_ID = "2026-07-20-deep-completion-test"
ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _environment(
    tmp_path: Path,
    *,
    capacity: int = 3,
) -> dict[str, object]:
    from tests.test_deep_research_completion import (
        _environment as _deep_environment,
    )
    from tests.test_deep_research_completion import _record as _record_completion

    deep = _deep_environment(
        tmp_path,
        underwriting_capacity=capacity,
    )
    completion = _record_completion(deep)
    submission = deep["submission"]
    assert isinstance(submission, dict)
    policy_path = tmp_path / "policies" / "research-allocation.json"
    research_policy_bytes = policy_path.read_bytes()
    shutil.copytree(ROOT / "policies", policy_path.parent, dirs_exist_ok=True)
    policy_path.write_bytes(research_policy_bytes)
    selection_path = tmp_path / str(submission["scoped_selection_path"])
    completion_path = tmp_path / str(completion["receipt_path"])
    return {
        "repository": tmp_path,
        "coverage_root": deep["coverage_root"],
        "policy_path": policy_path,
        "selection_path": selection_path,
        "selection_sha256": submission["scoped_selection_sha256"],
        "completion_path": completion_path,
        "candidate": {
            "symbol": "CN:600519",
            "deep_selection_path": submission["scoped_selection_path"],
            "deep_selection_sha256": submission["scoped_selection_sha256"],
            "deep_completion_path": completion["receipt_path"],
            "deep_completion_sha256": completion["receipt_sha256"],
        },
    }


def _full_market_underwriting_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, object]:
    from tests.test_deep_research_completion import _full_market_environment
    from trading_os.research_assets.deep_research_completion import (
        record_deep_research_completion,
    )

    deep = _full_market_environment(tmp_path, monkeypatch)
    completion = record_deep_research_completion(
        root=deep["coverage_root"],
        symbol=str(deep["symbol"]),
        submission=deep["submission"],
        completed_at=deep["completed_at"],
    )
    submission = deep["submission"]
    assert isinstance(submission, dict)
    completed_at = deep["completed_at"]
    assert isinstance(completed_at, dt.datetime)
    receipt_path = tmp_path / str(completion["receipt_path"])
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    policy_path = tmp_path / "policies" / "research-allocation.json"
    return {
        "repository": tmp_path,
        "coverage_root": deep["coverage_root"],
        "policy_path": policy_path,
        "approved_at": completed_at + dt.timedelta(hours=1),
        "manager_screen_run_id": receipt["manager_screen_run_id"],
        "allocator": receipt["effective_manager_authority"]["agent"],
        "authority": receipt["effective_manager_authority"],
        "candidate": {
            "symbol": deep["symbol"],
            "deep_selection_path": submission["scoped_selection_path"],
            "deep_selection_sha256": submission["scoped_selection_sha256"],
            "deep_completion_path": completion["receipt_path"],
            "deep_completion_sha256": completion["receipt_sha256"],
        },
    }


def _freeze(env: dict[str, object], **changes):
    from trading_os.research_assets.review_allocation import (
        freeze_underwriting_approval,
    )

    values = {
        "root": env["coverage_root"],
        "repository_root": env["repository"],
        "approval_id": "uw-approval-001",
        "manager_screen_run_id": RUN_ID,
        "policy_path": Path(env["policy_path"]).relative_to(Path(env["repository"])).as_posix(),
        "policy_sha256": _sha256(Path(env["policy_path"])),
        "approved_by": "/root/investment-manager",
        "reason": "Deep research is complete and underwriting has comparative value.",
        "approved_at": APPROVED_AT,
        "candidates": [env["candidate"]],
    }
    values.update(changes)
    return freeze_underwriting_approval(**values)


def _manager_bound_prepared(
    env: dict[str, object],
    *,
    run_id: str = "underwriting-review-001",
) -> tuple[Path, Path, Path, dict[str, object]]:
    from trading_os.research_assets.review_workflow import (
        create_review_from_underwriting_approval,
        prepare_review,
    )

    approval = _freeze(env)
    repository = Path(env["repository"])
    runs_root = repository / "automation" / "runs"
    policy_root = repository / "policies"
    create_review_from_underwriting_approval(
        runs_root=runs_root,
        coverage_root=env["coverage_root"],
        run_id=run_id,
        scope_type="custom",
        market="CN",
        description="Approved manager-run underwriting cohort",
        approval_path=approval["approval_path"],
        approval_sha256=approval["approval_sha256"],
        policy_root=policy_root,
        created_at=APPROVED_AT + dt.timedelta(minutes=1),
    )
    prepare_review(
        runs_root=runs_root,
        run_id=run_id,
        prepared_at=APPROVED_AT + dt.timedelta(minutes=2),
    )
    company_dir = repository / "research" / "companies" / "CN" / "600519"
    return runs_root, policy_root, company_dir, approval


def _manager_bound_runner(company_dir: Path, run_id: str):
    from automation.scripts.review_dispatch import AgentResult
    from tests.test_review_dispatch import MachineContractRunner

    class CurrentEvidenceRunner(MachineContractRunner):
        def run(self, task):
            result = super().run(task)
            if not result.ok or task.stage not in {"blind", "challenger"}:
                return result
            payload = json.loads(json.dumps(result.payload))
            timestamp = (APPROVED_AT + dt.timedelta(minutes=3)).isoformat()
            payload["information_cutoff"] = timestamp
            for item in payload["evidence"]["ledger"]:
                item["observed_at"] = timestamp
                item["retrieved_at"] = timestamp
            payload["portfolio_inputs"]["price_as_of"] = timestamp
            payload["portfolio_inputs"]["return_model"]["model_as_of"] = timestamp
            return AgentResult(ok=True, payload=payload)

    return CurrentEvidenceRunner(company_dir=company_dir, run_id=run_id)


def test_freeze_underwriting_approval_binds_evidence_and_replays(tmp_path: Path):
    from trading_os.research_assets.review_allocation import (
        APPROVAL_ARTIFACT_TYPE,
        downstream_review_request_contracts,
    )
    from trading_os.research_assets.sealing import verify_sealed

    env = _environment(tmp_path)
    created = _freeze(env)

    assert created["approved_symbols"] == ["CN:600519"]
    assert created["capacity"] == {
        "limit": 3,
        "committed_before": 0,
        "approved_count": 1,
        "committed_after": 1,
        "effort_budget_hours_per_company": 12.0,
    }
    assert created["idempotent"] is False
    approval_path = tmp_path / created["approval_path"]
    sealed = verify_sealed(approval_path)
    assert sealed.artifact_type == APPROVAL_ARTIFACT_TYPE
    payload = json.loads(approval_path.read_text(encoding="utf-8"))
    assert payload["manager_screen_run_id"] == RUN_ID
    snapshot_path = (
        Path(env["coverage_root"]) / "manager-screen" / RUN_ID / "research-policy.snapshot.json"
    )
    assert payload["policy_binding"]["path"] == snapshot_path.relative_to(tmp_path).as_posix()
    assert payload["policy_binding"]["sha256"] == verify_sealed(snapshot_path).sha256
    assert payload["candidates"][0]["deep_selection"]["sha256"] == env["selection_sha256"]
    assert payload["candidates"][0]["deep_completion"]["sha256"] == _sha256(
        Path(env["completion_path"])
    )
    assert payload["candidates"][0]["research_claims"]["source_ids"] == ["annual-report"]

    replayed = _freeze(env)
    assert replayed["idempotent"] is True
    assert replayed["approval_sha256"] == created["approval_sha256"]
    contracts = downstream_review_request_contracts()
    assert contracts["contracts"]["challenger"]["underwriting_approval_grants_budget"] is False
    assert contracts["contracts"]["portfolio"]["underwriting_approval_grants_budget"] is False


def test_policy_upgrade_does_not_invalidate_sealed_approval_or_replay(
    tmp_path: Path,
):
    from trading_os.research_assets.review_allocation import (
        ReviewAllocationError,
        verify_underwriting_approval,
    )

    env = _environment(tmp_path)
    old_policy_sha256 = _sha256(Path(env["policy_path"]))
    created = _freeze(env)
    policy_path = Path(env["policy_path"])
    upgraded = json.loads(policy_path.read_text(encoding="utf-8"))
    upgraded["version"] = "99.0.0"
    upgraded["payload"]["stage_capacity_per_run"]["underwriting"] = 1
    policy_path.write_text(
        json.dumps(upgraded, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    verified = verify_underwriting_approval(
        root=env["coverage_root"],
        repository_root=env["repository"],
        approval_path=created["approval_path"],
        approval_sha256=created["approval_sha256"],
    )
    assert verified["approval"]["capacity"]["limit"] == 3

    replay = _freeze(env, policy_sha256=old_policy_sha256)
    assert replay["idempotent"] is True
    assert replay["approval_sha256"] == created["approval_sha256"]

    with pytest.raises(ReviewAllocationError, match="sealed manager-run contract"):
        _freeze(env)


def test_new_approval_after_live_upgrade_uses_existing_run_contract(
    tmp_path: Path,
):
    from trading_os.research_assets.review_allocation import (
        ReviewAllocationError,
        _ensure_run_policy_contract,
    )

    env = _environment(tmp_path, capacity=3)
    policy_path = Path(env["policy_path"])
    old_policy_sha256 = _sha256(policy_path)
    policy_binding, capacity, _ = _ensure_run_policy_contract(
        base=Path(env["coverage_root"]),
        repository=Path(env["repository"]),
        run_id=RUN_ID,
        policy_path=policy_path.relative_to(tmp_path).as_posix(),
        expected_sha256=old_policy_sha256,
        bound_at=APPROVED_AT - dt.timedelta(minutes=1),
    )
    upgraded = json.loads(policy_path.read_text(encoding="utf-8"))
    upgraded["version"] = "2.0.0"
    upgraded["payload"]["stage_capacity_per_run"]["underwriting"] = 1
    policy_path.write_text(
        json.dumps(upgraded, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    created = _freeze(env, policy_sha256=old_policy_sha256)
    approval = json.loads((tmp_path / created["approval_path"]).read_text(encoding="utf-8"))
    assert capacity == 3
    assert approval["policy_binding"] == policy_binding
    assert approval["capacity"]["limit"] == 3

    with pytest.raises(ReviewAllocationError, match="sealed manager-run contract"):
        _freeze(
            env,
            approval_id="uw-approval-different-policy",
            policy_sha256=_sha256(policy_path),
            approved_at=APPROVED_AT + dt.timedelta(minutes=1),
        )


def test_underwriting_reuses_profile_style_run_policy_contract(
    tmp_path: Path,
):
    from trading_os.research_assets.sealing import verify_sealed

    env = _environment(tmp_path)
    contract_path = Path(env["coverage_root"]) / "manager-screen" / RUN_ID / "research-policy.json"
    contract_sha256 = verify_sealed(contract_path).sha256

    created = _freeze(env)
    snapshot_path = contract_path.with_name("research-policy.snapshot.json")

    assert verify_sealed(contract_path).sha256 == contract_sha256
    assert verify_sealed(snapshot_path).artifact_type == ("manager_screen_research_policy_snapshot")
    assert created["capacity"]["limit"] == 3


def test_underwriting_approval_requires_same_run_and_completed_deep_history(
    tmp_path: Path,
):
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.review_allocation import ReviewAllocationError

    env = _environment(tmp_path)
    queue_path = Path(env["coverage_root"]) / "research_queue.jsonl"
    queue = read_jsonl(queue_path)
    queue[0]["manager_screen_run_id"] = "different-run"
    write_jsonl(queue_path, queue)
    with pytest.raises(ReviewAllocationError, match="different manager run"):
        _freeze(env)

    queue[0]["manager_screen_run_id"] = RUN_ID
    queue[0]["stage_history"] = []
    write_jsonl(queue_path, queue)
    with pytest.raises(ReviewAllocationError, match="completion chain is invalid"):
        _freeze(env)


def test_underwriting_rejects_formal_report_in_place_of_completion_receipt(
    tmp_path: Path,
):
    from trading_os.research_assets.review_allocation import ReviewAllocationError

    env = _environment(tmp_path)
    receipt = json.loads(Path(env["completion_path"]).read_text(encoding="utf-8"))
    report_path = tmp_path / receipt["report"]["path"]
    candidate = dict(env["candidate"])
    candidate["deep_completion_path"] = receipt["report"]["path"]
    candidate["deep_completion_sha256"] = _sha256(report_path)

    with pytest.raises(ReviewAllocationError, match="not validly sealed"):
        _freeze(env, candidates=[candidate])


@pytest.mark.parametrize("tamper", ["candidate_sha", "receipt_bytes"])
def test_underwriting_rejects_completion_receipt_tampering(
    tmp_path: Path,
    tamper: str,
):
    from trading_os.research_assets.review_allocation import ReviewAllocationError

    env = _environment(tmp_path)
    candidate = dict(env["candidate"])
    if tamper == "candidate_sha":
        candidate["deep_completion_sha256"] = "a" * 64
    else:
        receipt_path = Path(env["completion_path"])
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["report"]["sha256"] = "a" * 64
        receipt_path.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    with pytest.raises(ReviewAllocationError, match="SHA-256 mismatch|not validly sealed"):
        _freeze(env, candidates=[candidate])


@pytest.mark.parametrize(
    "field",
    [
        "deep_research_completion_path",
        "deep_research_completion_sha256",
        "deep_research_claims_sha256",
    ],
)
def test_underwriting_rejects_deep_completion_queue_projection_drift(
    tmp_path: Path,
    field: str,
):
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.review_allocation import ReviewAllocationError

    env = _environment(tmp_path)
    queue_path = Path(env["coverage_root"]) / "research_queue.jsonl"
    queue = read_jsonl(queue_path)
    queue[0][field] = "a" * 64 if field.endswith("sha256") else "drifted.json"
    write_jsonl(queue_path, queue)

    with pytest.raises(ReviewAllocationError, match="completion chain is invalid"):
        _freeze(env)


def test_underwriting_requires_terminal_deep_completion_projection(tmp_path: Path):
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.review_allocation import ReviewAllocationError

    env = _environment(tmp_path)
    receipt = json.loads(Path(env["completion_path"]).read_text(encoding="utf-8"))
    queue_path = Path(env["coverage_root"]) / "research_queue.jsonl"
    screening_path = Path(env["coverage_root"]) / "screening.jsonl"
    queue = read_jsonl(queue_path)
    screening = read_jsonl(screening_path)
    queue[0] = receipt["projection_base"]["research_queue"]
    screening[0] = receipt["projection_base"]["screening"]
    write_jsonl(queue_path, queue)
    write_jsonl(screening_path, screening)

    with pytest.raises(ReviewAllocationError, match="terminal projection"):
        _freeze(env)


def test_underwriting_approval_rejects_unsealed_claims(tmp_path: Path):
    from trading_os.research_assets.review_allocation import ReviewAllocationError

    env = _environment(tmp_path)
    claims_manifest = (
        Path(env["repository"])
        / "research"
        / "companies"
        / "CN"
        / "600519"
        / "evidence"
        / "deep-research-claims.json.seal.json"
    )
    claims_manifest.unlink()

    with pytest.raises(ReviewAllocationError, match="not validly sealed"):
        _freeze(env)


def test_underwriting_approval_binds_effective_manager_authority(tmp_path: Path):
    from trading_os.research_assets.review_allocation import ReviewAllocationError

    env = _environment(tmp_path)
    with pytest.raises(
        ReviewAllocationError,
        match="approved_by does not match sealed effective manager authority",
    ):
        _freeze(env, approved_by="/root/not-the-manager")

    manager_result = (
        tmp_path / "coverage" / "cn-a" / "manager-screen" / RUN_ID / "batch-001" / "result.json"
    )
    payload = json.loads(manager_result.read_text(encoding="utf-8"))
    payload["manager"]["agent"] = "/root/tampered-manager"
    manager_result.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(
        ReviewAllocationError,
        match="deep research completion chain is invalid",
    ):
        _freeze(env)


def test_full_market_underwriting_accepts_effective_allocator_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_os.research_assets.review_allocation import (
        freeze_underwriting_approval,
    )

    env = _full_market_underwriting_environment(tmp_path, monkeypatch)
    authority = env["authority"]
    assert isinstance(authority, dict)
    assert authority["source_type"] == (
        "manager_screen_full_market_allocation_v3_result"
    )

    created = freeze_underwriting_approval(
        root=env["coverage_root"],
        repository_root=env["repository"],
        approval_id="uw-full-market-allocator",
        manager_screen_run_id=str(env["manager_screen_run_id"]),
        policy_path=Path(env["policy_path"])
        .relative_to(Path(env["repository"]))
        .as_posix(),
        policy_sha256=_sha256(Path(env["policy_path"])),
        approved_by=str(env["allocator"]),
        reason="The full-market allocator explicitly purchases underwriting.",
        approved_at=env["approved_at"],
        candidates=[env["candidate"]],
    )

    assert created["approved_symbols"] == ["CN:000001"]


def test_full_market_underwriting_rejects_non_allocator_manager(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_os.research_assets.review_allocation import (
        ReviewAllocationError,
        freeze_underwriting_approval,
    )

    env = _full_market_underwriting_environment(tmp_path, monkeypatch)

    with pytest.raises(
        ReviewAllocationError,
        match="approved_by does not match sealed effective manager authority",
    ):
        freeze_underwriting_approval(
            root=env["coverage_root"],
            repository_root=env["repository"],
            approval_id="uw-full-market-non-allocator",
            manager_screen_run_id=str(env["manager_screen_run_id"]),
            policy_path=Path(env["policy_path"])
            .relative_to(Path(env["repository"]))
            .as_posix(),
            policy_sha256=_sha256(Path(env["policy_path"])),
            approved_by="/root/early-batch-manager",
            reason="A non-allocator must not purchase underwriting.",
            approved_at=env["approved_at"],
            candidates=[env["candidate"]],
        )


def test_underwriting_approval_enforces_cross_artifact_run_capacity(
    tmp_path: Path,
):
    from trading_os.research_assets.review_allocation import (
        APPROVAL_ARTIFACT_TYPE,
        ReviewAllocationError,
        _ensure_run_policy_contract,
    )
    from trading_os.research_assets.sealing import seal_json

    env = _environment(tmp_path, capacity=1)
    policy_path = Path(env["policy_path"])
    policy_binding, _, _ = _ensure_run_policy_contract(
        base=Path(env["coverage_root"]),
        repository=tmp_path,
        run_id=RUN_ID,
        policy_path=policy_path.relative_to(tmp_path).as_posix(),
        expected_sha256=_sha256(policy_path),
        bound_at=APPROVED_AT - dt.timedelta(days=1),
    )
    prior_path = Path(env["coverage_root"]) / "review-allocations" / RUN_ID / "prior-approval.json"
    seal_json(
        prior_path,
        {
            "schema_version": 1,
            "approval_id": "prior-approval",
            "manager_screen_run_id": RUN_ID,
            "stage": "underwriting",
            "approved_by": "/root/investment-manager",
            "approved_at": (APPROVED_AT - dt.timedelta(days=1)).isoformat(),
            "reason": "Prior company consumed the run capacity.",
            "policy_binding": policy_binding,
            "capacity": {
                "limit": 1,
                "committed_before": 0,
                "approved_count": 1,
                "committed_after": 1,
                "effort_budget_hours_per_company": 12.0,
            },
            "candidates": [
                {
                    "symbol": "CN:000001",
                    "company_dir": "research/companies/CN/000001",
                    "deep_selection": {
                        "path": "coverage/cn-a/prior-selection.json",
                        "sha256": "a" * 64,
                    },
                    "deep_completion": {
                        "path": "research/companies/CN/000001/reports/deep.md",
                        "sha256": "b" * 64,
                    },
                    "research_claims": {
                        "path": ("research/companies/CN/000001/evidence/claims.json"),
                        "sha256": "c" * 64,
                        "report_id": "prior-deep-report",
                        "source_ids": ["annual-report"],
                    },
                }
            ],
        },
        artifact_type=APPROVAL_ARTIFACT_TYPE,
        sealed_at=APPROVED_AT - dt.timedelta(days=1),
    )

    with pytest.raises(ReviewAllocationError, match="run capacity exceeded"):
        _freeze(env)


def test_underwriting_approval_rejects_cross_artifact_duplicate_symbol(
    tmp_path: Path,
):
    from trading_os.research_assets.review_allocation import ReviewAllocationError

    env = _environment(tmp_path)
    _freeze(env, approval_id="uw-approval-001")
    with pytest.raises(ReviewAllocationError, match="already approved"):
        _freeze(
            env,
            approval_id="uw-approval-002",
            approved_at=APPROVED_AT + dt.timedelta(minutes=1),
        )


def test_manager_bound_review_is_created_only_from_approval_and_replays(
    tmp_path: Path,
):
    from trading_os.research_assets.review_store import ReviewRunStore
    from trading_os.research_assets.review_workflow import (
        create_review_from_underwriting_approval,
        prepare_review,
        review_status,
    )

    env = _environment(tmp_path)
    approval = _freeze(env)
    runs_root = tmp_path / "automation" / "runs"
    arguments = {
        "runs_root": runs_root,
        "coverage_root": env["coverage_root"],
        "run_id": "underwriting-review-001",
        "scope_type": "custom",
        "market": "CN",
        "description": "Approved manager-run underwriting cohort",
        "approval_path": approval["approval_path"],
        "approval_sha256": approval["approval_sha256"],
        "policy_root": tmp_path / "policies",
        "created_at": APPROVED_AT + dt.timedelta(minutes=1),
    }
    state = create_review_from_underwriting_approval(**arguments)

    assert state["intake"] == {
        "mode": "underwriting_approval",
        "manager_screen_run_id": RUN_ID,
        "coverage_root": "coverage/cn-a",
        "underwriting_approval_path": approval["approval_path"],
        "underwriting_approval_sha256": approval["approval_sha256"],
    }
    assert state["candidate_set"]["source_binding"] == {
        "type": "underwriting_approval",
        "path": approval["approval_path"],
        "sha256": approval["approval_sha256"],
    }
    snapshot = ReviewRunStore(runs_root).read_candidates("underwriting-review-001")
    assert snapshot == [
        {
            "symbol": "CN:600519",
            "name": "贵州茅台",
            "target_company_dir": str(tmp_path / "research" / "companies" / "CN" / "600519"),
        }
    ]
    replayed = create_review_from_underwriting_approval(**arguments)
    assert replayed == state

    prepared = prepare_review(
        runs_root=runs_root,
        run_id="underwriting-review-001",
        prepared_at=APPROVED_AT + dt.timedelta(minutes=2),
    )
    assert prepared["status"] == "packets_ready"
    repeated = prepare_review(
        runs_root=runs_root,
        run_id="underwriting-review-001",
        prepared_at=APPROVED_AT + dt.timedelta(minutes=3),
    )
    assert repeated["status"] == "packets_ready"
    assert (
        review_status(
            runs_root=runs_root,
            run_id="underwriting-review-001",
        )["run"]["intake"]["mode"]
        == "underwriting_approval"
    )


def test_cli_creates_review_only_from_valid_underwriting_approval(
    tmp_path: Path,
    capsys,
) -> None:
    from trading_os.cli import main

    env = _environment(tmp_path)
    approval = _freeze(env)
    base_args = [
        "review",
        "create-from-underwriting-approval",
        "cli-underwriting-review-001",
        "--scope-type",
        "custom",
        "--market",
        "CN",
        "--description",
        "Approved manager-run underwriting cohort",
        "--approval-path",
        str(approval["approval_path"]),
        "--approval-sha256",
        str(approval["approval_sha256"]),
        "--coverage-root",
        str(env["coverage_root"]),
        "--runs-root",
        str(tmp_path / "automation" / "runs"),
        "--policy-root",
        str(tmp_path / "policies"),
        "--at",
        (APPROVED_AT + dt.timedelta(minutes=1)).isoformat(),
    ]

    assert main(base_args) == 0
    created = json.loads(capsys.readouterr().out)
    assert created["run"]["intake"]["mode"] == "underwriting_approval"

    invalid_args = list(base_args)
    invalid_args[2] = "cli-underwriting-review-002"
    invalid_args[invalid_args.index("--approval-sha256") + 1] = "0" * 64
    assert main(invalid_args) == 1
    error = json.loads(capsys.readouterr().err)
    assert error["error_code"] == "review_workflow_error"


def test_manager_bound_prepare_revalidates_approval_seal(tmp_path: Path):
    from trading_os.research_assets.review_workflow import (
        ReviewWorkflowError,
        create_review_from_underwriting_approval,
        prepare_review,
    )

    env = _environment(tmp_path)
    approval = _freeze(env)
    runs_root = tmp_path / "automation" / "runs"
    create_review_from_underwriting_approval(
        runs_root=runs_root,
        coverage_root=env["coverage_root"],
        run_id="underwriting-review-001",
        scope_type="custom",
        market="CN",
        description="Approved manager-run underwriting cohort",
        approval_path=approval["approval_path"],
        approval_sha256=approval["approval_sha256"],
        policy_root=tmp_path / "policies",
        created_at=APPROVED_AT + dt.timedelta(minutes=1),
    )
    approval_path = tmp_path / approval["approval_path"]
    payload = json.loads(approval_path.read_text(encoding="utf-8"))
    payload["reason"] = "tampered"
    approval_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ReviewWorkflowError, match="not validly sealed"):
        prepare_review(
            runs_root=runs_root,
            run_id="underwriting-review-001",
            prepared_at=APPROVED_AT + dt.timedelta(minutes=2),
        )


def test_legacy_review_state_is_explicitly_unbound(tmp_path: Path):
    from trading_os.research_assets.review_workflow import (
        ReviewWorkflowError,
        create_review,
    )

    _environment(tmp_path)
    company_dir = tmp_path / "research" / "companies" / "CN" / "600519"
    arguments = {
        "runs_root": tmp_path / "automation" / "runs",
        "run_id": "legacy-review-001",
        "scope_type": "custom",
        "market": "CN",
        "description": "Legacy compatibility review",
        "candidates": [
            {
                "symbol": "CN:000001",
                "name": "Legacy Company",
                "target_company_dir": str(company_dir),
            }
        ],
        "policy_root": tmp_path / "policies",
        "created_at": APPROVED_AT,
    }
    state = create_review(**arguments)

    assert state["intake"] == {
        "mode": "legacy_unbound",
        "manager_screen_run_id": None,
        "coverage_root": "coverage/cn-a",
        "underwriting_approval_path": None,
        "underwriting_approval_sha256": None,
    }

    blocked = dict(arguments)
    blocked["run_id"] = "manager-bound-review-001"
    blocked["candidates"] = [
        {
            "symbol": "CN:600519",
            "name": "贵州茅台",
            "target_company_dir": str(company_dir),
        }
    ]
    with pytest.raises(
        ReviewWorkflowError,
        match="cannot write manager-screen/new-protocol",
    ):
        create_review(**blocked)
    assert not (tmp_path / "automation" / "runs" / "manager-bound-review-001").exists()

    with pytest.raises(
        ReviewWorkflowError,
        match="requires canonical coverage_root",
    ):
        create_review(
            **blocked,
            coverage_root="coverage/empty-bypass",
        )


def test_manager_bound_challenger_waits_for_approval_and_then_dispatches(
    tmp_path: Path,
):
    from automation.scripts.review_dispatch import (
        DispatchError,
        ReviewDispatcher,
    )
    from trading_os.research_assets.review_allocation import (
        ReviewAllocationError,
        freeze_challenger_approval,
    )
    from trading_os.research_assets.review_workflow import (
        request_challenger_budget,
    )

    env = _environment(tmp_path)
    runs_root, policy_root, company_dir, _ = _manager_bound_prepared(env)
    run_id = "underwriting-review-001"
    runner = _manager_bound_runner(company_dir, run_id)
    runner.runs_root = runs_root
    dispatcher = ReviewDispatcher(
        runs_root=runs_root,
        policy_root=policy_root,
        runner=runner,
        timeout_seconds=60,
        lease_seconds=120,
    )
    dispatcher.dispatch(
        run_id,
        now=APPROVED_AT + dt.timedelta(minutes=3),
    )
    reveal = dispatcher.dispatch(
        run_id,
        now=APPROVED_AT + dt.timedelta(minutes=4),
    )
    assert reveal.status == "challenging"
    assert [task.stage for task in runner.tasks] == ["blind", "reveal"]

    request = request_challenger_budget(
        runs_root=runs_root,
        run_id=run_id,
        symbols=["CN:600519"],
        trigger="company_underwriting_trigger",
        requested_by="ignored-on-replay",
        requested_at=APPROVED_AT + dt.timedelta(minutes=10),
    )
    assert request["symbols"] == ["CN:600519"]
    with pytest.raises(
        DispatchError,
        match="explicit manager challenger approval is required",
    ):
        dispatcher.dispatch(
            run_id,
            now=APPROVED_AT + dt.timedelta(minutes=5),
        )
    assert [task.stage for task in runner.tasks] == ["blind", "reveal"]

    approval_args = {
        "root": env["coverage_root"],
        "repository_root": env["repository"],
        "approval_id": "challenger-approval-001",
        "request_path": request["request_path"],
        "request_sha256": request["request_sha256"],
        "approved_by": "/root/investment-manager",
        "executor": "review-dispatch",
        "reason": "Material accounting uncertainty requires challenge.",
        "approved_at": APPROVED_AT + dt.timedelta(minutes=5),
    }
    live_policy_path = Path(env["policy_path"])
    upgraded = json.loads(live_policy_path.read_text(encoding="utf-8"))
    upgraded["version"] = "2.0.0"
    upgraded["payload"]["stage_capacity_per_run"]["underwriting"] = 1
    live_policy_path.write_text(
        json.dumps(upgraded, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    created = freeze_challenger_approval(**approval_args)
    assert created["idempotent"] is False
    assert freeze_challenger_approval(**approval_args)["idempotent"] is True
    with pytest.raises(ReviewAllocationError, match="approver and executor"):
        freeze_challenger_approval(
            **{
                **approval_args,
                "approval_id": "challenger-approval-invalid",
                "executor": "/root/investment-manager",
            }
        )

    completed = dispatcher.dispatch(
        run_id,
        now=APPROVED_AT + dt.timedelta(minutes=6),
    )
    assert completed.status == "company_reviews_complete"
    assert [task.stage for task in runner.tasks] == [
        "blind",
        "reveal",
        "challenger",
        "arbitration",
    ]
    duplicate_request = request_challenger_budget(
        runs_root=runs_root,
        run_id=run_id,
        symbols=["CN:600519"],
        trigger="duplicate_company_trigger",
        requested_by="review-dispatch",
        requested_at=APPROVED_AT + dt.timedelta(minutes=7),
    )
    with pytest.raises(
        ReviewAllocationError,
        match="already approved for one or more symbols",
    ):
        freeze_challenger_approval(
            root=env["coverage_root"],
            repository_root=env["repository"],
            approval_id="challenger-approval-002",
            request_path=duplicate_request["request_path"],
            request_sha256=duplicate_request["request_sha256"],
            approved_by="/root/investment-manager",
            executor="review-dispatch",
            reason="A symbol cannot purchase challenger twice in one manager run.",
            approved_at=APPROVED_AT + dt.timedelta(minutes=8),
        )


def test_manager_bound_portfolio_synthesis_requires_single_approval(
    tmp_path: Path,
):
    from automation.scripts.review_dispatch import ReviewDispatcher
    from trading_os.research_assets.review_allocation import (
        ReviewAllocationError,
        freeze_challenger_approval,
        freeze_portfolio_synthesis_approval,
    )
    from trading_os.research_assets.review_workflow import (
        request_challenger_budget,
        synthesize_review,
    )

    env = _environment(tmp_path)
    runs_root, policy_root, company_dir, _ = _manager_bound_prepared(env)
    run_id = "underwriting-review-001"
    runner = _manager_bound_runner(company_dir, run_id)
    runner.runs_root = runs_root
    dispatcher = ReviewDispatcher(
        runs_root=runs_root,
        policy_root=policy_root,
        runner=runner,
        timeout_seconds=60,
        lease_seconds=120,
    )
    dispatcher.dispatch(
        run_id,
        now=APPROVED_AT + dt.timedelta(minutes=3),
    )
    dispatcher.dispatch(
        run_id,
        now=APPROVED_AT + dt.timedelta(minutes=4),
    )
    challenger_request = request_challenger_budget(
        runs_root=runs_root,
        run_id=run_id,
        symbols=["CN:600519"],
        trigger="company_underwriting_trigger",
        requested_by="review-dispatch",
        requested_at=APPROVED_AT + dt.timedelta(minutes=4),
    )
    freeze_challenger_approval(
        root=env["coverage_root"],
        repository_root=env["repository"],
        approval_id="challenger-approval-001",
        request_path=challenger_request["request_path"],
        request_sha256=challenger_request["request_sha256"],
        approved_by="/root/investment-manager",
        executor="review-dispatch",
        reason="Top-five eligibility requires an independent challenge.",
        approved_at=APPROVED_AT + dt.timedelta(minutes=5),
    )
    dispatcher.dispatch(
        run_id,
        now=APPROVED_AT + dt.timedelta(minutes=6),
    )

    requested = synthesize_review(
        runs_root=runs_root,
        research_root=tmp_path / "research",
        policy_root=policy_root,
        run_id=run_id,
        quotes_path=tmp_path / "missing-quotes.json",
        synthesized_at=APPROVED_AT + dt.timedelta(minutes=7),
    )
    assert requested["approval_required"] is True
    assert requested["status"] == "company_reviews_complete"
    assert not (tmp_path / "research" / "batches" / run_id).exists()

    approval_args = {
        "root": env["coverage_root"],
        "repository_root": env["repository"],
        "approval_id": "portfolio-approval-001",
        "request_path": requested["request_path"],
        "request_sha256": requested["request_sha256"],
        "approved_by": "/root/investment-manager",
        "executor": "cli",
        "reason": "Completed reviews justify portfolio synthesis.",
        "approved_at": APPROVED_AT + dt.timedelta(minutes=8),
    }
    live_policy_path = Path(env["policy_path"])
    upgraded = json.loads(live_policy_path.read_text(encoding="utf-8"))
    upgraded["version"] = "2.0.0"
    upgraded["payload"]["stage_capacity_per_run"]["underwriting"] = 1
    live_policy_path.write_text(
        json.dumps(upgraded, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    approved = freeze_portfolio_synthesis_approval(**approval_args)
    assert approved["capacity"]["limit"] == 1
    assert freeze_portfolio_synthesis_approval(**approval_args)["idempotent"] is True
    with pytest.raises(ReviewAllocationError, match="already approved"):
        freeze_portfolio_synthesis_approval(
            **{
                **approval_args,
                "approval_id": "portfolio-approval-002",
                "approved_at": APPROVED_AT + dt.timedelta(minutes=9),
            }
        )

    quotes_path = tmp_path / "quotes.json"
    quotes_path.write_text(
        json.dumps(
            [
                {
                    "symbol": "CN:600519",
                    "price": 75.0,
                    "as_of": (APPROVED_AT + dt.timedelta(minutes=9)).isoformat(),
                }
            ]
        ),
        encoding="utf-8",
    )
    portfolio = synthesize_review(
        runs_root=runs_root,
        research_root=tmp_path / "research",
        policy_root=policy_root,
        run_id=run_id,
        quotes_path=quotes_path,
        synthesized_at=APPROVED_AT + dt.timedelta(minutes=9),
    )
    assert portfolio["status"] == "synthesizing"
    assert (tmp_path / "research" / "batches" / run_id / "portfolio.json").is_file()


@pytest.mark.parametrize("tamper_target", ["request", "evaluation", "candidate"])
def test_review_budget_approval_revalidates_bound_evidence(
    tmp_path: Path,
    tamper_target: str,
):
    from automation.scripts.review_dispatch import ReviewDispatcher
    from trading_os.research_assets.review_allocation import (
        ReviewAllocationError,
        freeze_challenger_approval,
    )
    from trading_os.research_assets.review_workflow import (
        request_challenger_budget,
    )

    env = _environment(tmp_path)
    runs_root, policy_root, company_dir, _ = _manager_bound_prepared(env)
    run_id = "underwriting-review-001"
    runner = _manager_bound_runner(company_dir, run_id)
    runner.runs_root = runs_root
    dispatcher = ReviewDispatcher(
        runs_root=runs_root,
        policy_root=policy_root,
        runner=runner,
        timeout_seconds=60,
        lease_seconds=120,
    )
    dispatcher.dispatch(
        run_id,
        now=APPROVED_AT + dt.timedelta(minutes=3),
    )
    dispatcher.dispatch(
        run_id,
        now=APPROVED_AT + dt.timedelta(minutes=4),
    )
    request = request_challenger_budget(
        runs_root=runs_root,
        run_id=run_id,
        symbols=["CN:600519"],
        trigger="company_underwriting_trigger",
        requested_by="review-dispatch",
        requested_at=APPROVED_AT + dt.timedelta(minutes=4),
    )
    if tamper_target == "request":
        tamper_path = tmp_path / request["request_path"]
        payload = json.loads(tamper_path.read_text(encoding="utf-8"))
        payload["trigger"] = "tampered"
    elif tamper_target == "evaluation":
        tamper_path = company_dir / "underwriting" / run_id / "primary-evaluation.json"
        payload = json.loads(tamper_path.read_text(encoding="utf-8"))
        payload["status"] = "rejected"
    else:
        tamper_path = company_dir / "underwriting" / run_id / "portfolio-candidate.primary.json"
        payload = json.loads(tamper_path.read_text(encoding="utf-8"))
        payload["underwriting_status"] = "rejected"
    tamper_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(
        ReviewAllocationError,
        match="binding is invalid",
    ):
        freeze_challenger_approval(
            root=env["coverage_root"],
            repository_root=env["repository"],
            approval_id="challenger-approval-001",
            request_path=request["request_path"],
            request_sha256=request["request_sha256"],
            approved_by="/root/investment-manager",
            executor="review-dispatch",
            reason="Tampered evidence must fail revalidation.",
            approved_at=APPROVED_AT + dt.timedelta(minutes=5),
        )
