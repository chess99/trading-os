from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import TextIO

from .research_assets.alerts import (
    evaluate_price_alerts,
    load_json,
    write_price_alerts,
)
from .research_assets.claims import ClaimPacketError
from .research_assets.company import AssetValidationError
from .research_assets.coverage_store import (
    CoverageValidationError,
    coverage_status,
    enqueue_research,
    get_symbol,
    list_screening,
    reconcile_research_queue,
    set_screening,
    validate_coverage_root,
)
from .research_assets.index import write_index
from .research_assets.migration import (
    MigrationError,
    apply_migration_plan,
    build_migration_plan,
    load_migration_plan,
    write_migration_plan,
)
from .research_assets.models import PolicyValidationError, load_policy
from .research_assets.portfolio import PortfolioValidationError
from .research_assets.profile_workflow import (
    claim_profile_task,
    profile_cycle_status,
    record_profile_package,
    release_profile_task,
)
from .research_assets.rebaseline_ranking import (
    RebaselineRankingError,
    build_rebaseline_ranking,
    write_rebaseline_ranking,
)
from .research_assets.research_allocation import (
    ResearchAllocationError,
    apply_research_allocation,
    allocate_research_capacity,
    evaluate_quick_profile,
    write_research_allocation,
)
from .research_assets.review_store import ReviewStoreError
from .research_assets.review_workflow import (
    ReviewWorkflowError,
    create_review,
    finalize_review_companies,
    load_candidates,
    prepare_review,
    resume_review,
    review_status,
    run_review,
    synthesize_review,
    validate_all_assets,
    validate_review,
    write_review_report,
)
from .research_assets.schedule import write_review_schedule
from .research_assets.sealing import SealingError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trading_os",
        description="Trading OS research asset tools",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    assets = sub.add_parser("assets", help="Validate v2 research assets")
    assets_sub = assets.add_subparsers(dest="assets_cmd", required=True)
    assets_validate = assets_sub.add_parser(
        "validate", help="Validate every v2 company asset"
    )
    assets_validate.add_argument("--research-root", default="research")
    assets_validate.set_defaults(func=cmd_assets_validate)
    assets_migrate = assets_sub.add_parser(
        "migrate", help="Plan or apply the one-shot v2 asset migration"
    )
    migration_mode = assets_migrate.add_mutually_exclusive_group(required=True)
    migration_mode.add_argument("--dry-run", action="store_true")
    migration_mode.add_argument("--apply", action="store_true")
    assets_migrate.add_argument("--plan", help="Dry-run plan required by --apply")
    assets_migrate.add_argument("--output", help="Optionally write the dry-run plan")
    assets_migrate.add_argument("--migration-id")
    assets_migrate.add_argument("--research-root", default="research")
    _add_timestamp(assets_migrate)
    assets_migrate.set_defaults(func=cmd_assets_migrate)

    review = sub.add_parser("review", help="Run independent underwriting reviews")
    review_sub = review.add_subparsers(dest="review_cmd", required=True)

    review_create = review_sub.add_parser(
        "create", help="Create a review and freeze its candidate set"
    )
    review_create.add_argument("run_id")
    review_create.add_argument("--scope-type", required=True)
    review_create.add_argument("--market", required=True)
    review_create.add_argument("--description", required=True)
    review_create.add_argument("--candidates", required=True)
    review_create.add_argument("--parent-run-id")
    _add_review_roots(review_create, policies=True)
    _add_timestamp(review_create)
    review_create.set_defaults(func=cmd_review_create)

    review_prepare = review_sub.add_parser(
        "prepare", help="Build and seal blind claim packets"
    )
    review_prepare.add_argument("run_id")
    _add_review_roots(review_prepare)
    _add_timestamp(review_prepare)
    review_prepare.set_defaults(func=cmd_review_prepare)

    review_status_cmd = review_sub.add_parser("status", help="Show review run state")
    review_status_cmd.add_argument("run_id")
    _add_review_roots(review_status_cmd)
    review_status_cmd.set_defaults(func=cmd_review_status)

    review_resume = review_sub.add_parser(
        "resume", help="Resume a review from its safe pre-failure state"
    )
    review_resume.add_argument("run_id")
    _add_review_roots(review_resume)
    _add_timestamp(review_resume)
    review_resume.set_defaults(func=cmd_review_resume)

    review_validate = review_sub.add_parser(
        "validate", help="Validate review state and sealed artifacts"
    )
    review_validate.add_argument("run_id")
    review_validate.add_argument("--strict", action="store_true")
    _add_review_roots(review_validate)
    review_validate.set_defaults(func=cmd_review_validate)

    review_synthesize = review_sub.add_parser(
        "synthesize", help="Build a constrained model portfolio"
    )
    review_synthesize.add_argument("run_id")
    review_synthesize.add_argument("--quotes", required=True)
    _add_review_roots(review_synthesize, research=True, policies=True)
    _add_timestamp(review_synthesize)
    review_synthesize.set_defaults(func=cmd_review_synthesize)

    review_report = review_sub.add_parser(
        "report", help="Write the immutable portfolio synthesis report"
    )
    review_report.add_argument("run_id")
    _add_review_roots(review_report, research=True)
    _add_timestamp(review_report)
    review_report.set_defaults(func=cmd_review_report)

    review_finalize = review_sub.add_parser(
        "finalize", help="Sync a completed batch into mutable company metadata"
    )
    review_finalize.add_argument("run_id")
    _add_review_roots(review_finalize, research=True)
    _add_timestamp(review_finalize)
    review_finalize.set_defaults(func=cmd_review_finalize)

    review_run = review_sub.add_parser(
        "run", help="Advance every currently executable review stage"
    )
    review_run.add_argument("run_id")
    review_run.add_argument("--quotes")
    _add_review_roots(review_run, research=True, policies=True)
    _add_timestamp(review_run)
    review_run.set_defaults(func=cmd_review_run)

    index = sub.add_parser("index", help="Build generated research indexes")
    index_sub = index.add_subparsers(dest="index_cmd", required=True)
    rebuild = index_sub.add_parser("rebuild", help="Rebuild research/index.json")
    rebuild.add_argument("--research-root", default="research")
    rebuild.set_defaults(func=cmd_index_rebuild)

    alerts = sub.add_parser("alerts", help="Build and check price alerts")
    alerts_sub = alerts.add_subparsers(dest="alerts_cmd", required=True)
    alerts_build = alerts_sub.add_parser(
        "build",
        help="Build automation/price_alerts.json",
    )
    alerts_build.add_argument("--research-root", default="research")
    alerts_build.add_argument("--output", default="automation/price_alerts.json")
    alerts_build.set_defaults(func=cmd_alerts_build)
    alerts_check = alerts_sub.add_parser(
        "check",
        help="Check price alerts with a quote JSON file",
    )
    alerts_check.add_argument("--alerts", default="automation/price_alerts.json")
    alerts_check.add_argument("--quotes", required=True)
    alerts_check.set_defaults(func=cmd_alerts_check)

    schedule = sub.add_parser("schedule", help="Build review schedules")
    schedule_sub = schedule.add_subparsers(dest="schedule_cmd", required=True)
    schedule_build = schedule_sub.add_parser(
        "build",
        help="Build automation/review_schedule.json",
    )
    schedule_build.add_argument("--research-root", default="research")
    schedule_build.add_argument("--output", default="automation/review_schedule.json")
    schedule_build.set_defaults(func=cmd_schedule_build)

    coverage = sub.add_parser("coverage", help="Manage coverage screening JSONL files")
    coverage_sub = coverage.add_subparsers(dest="coverage_cmd", required=True)

    coverage_validate = coverage_sub.add_parser("validate", help="Validate coverage JSONL")
    _add_coverage_root(coverage_validate)
    coverage_validate.set_defaults(func=cmd_coverage_validate)

    coverage_status_cmd = coverage_sub.add_parser("status", help="Show coverage counts")
    _add_coverage_root(coverage_status_cmd)
    coverage_status_cmd.set_defaults(func=cmd_coverage_status)

    coverage_get = coverage_sub.add_parser("get", help="Get coverage records for one symbol")
    coverage_get.add_argument("symbol")
    _add_coverage_root(coverage_get)
    coverage_get.set_defaults(func=cmd_coverage_get)

    coverage_list = coverage_sub.add_parser("list", help="List screening records")
    _add_coverage_root(coverage_list)
    coverage_list.add_argument("--decision")
    coverage_list.set_defaults(func=cmd_coverage_list)

    rank_rebaseline = coverage_sub.add_parser(
        "rank-rebaseline", help="Rank companies requiring research rebaseline"
    )
    _add_coverage_root(rank_rebaseline)
    rank_rebaseline.add_argument("--companies")
    rank_rebaseline.add_argument("--screening")
    rank_rebaseline.add_argument("--research-root", default="research")
    rank_rebaseline.add_argument("--output", default="automation/rebaseline_ranking.json")
    rank_rebaseline.add_argument("--max-snapshot-age-days", type=int, default=7)
    _add_timestamp(rank_rebaseline)
    rank_rebaseline.set_defaults(func=cmd_coverage_rank_rebaseline)

    allocate_research = coverage_sub.add_parser(
        "allocate-research",
        help="Allocate finite research capacity across a public ranking",
    )
    allocate_research.add_argument(
        "--ranking",
        default="automation/rebaseline_ranking.json",
    )
    allocate_research.add_argument(
        "--policy",
        default="policies/research-allocation.json",
    )
    allocate_research.add_argument(
        "--output",
        default="automation/research_allocation.json",
    )
    allocate_research.set_defaults(func=cmd_coverage_allocate_research)

    apply_allocation = coverage_sub.add_parser(
        "apply-allocation",
        help="Apply a sealed research-capacity decision to coverage queues",
    )
    _add_coverage_root(apply_allocation)
    apply_allocation.add_argument(
        "--ranking",
        default="automation/rebaseline_ranking.json",
    )
    apply_allocation.add_argument(
        "--allocation",
        default="automation/research_allocation.json",
    )
    _add_timestamp(apply_allocation)
    apply_allocation.set_defaults(func=cmd_coverage_apply_allocation)

    evaluate_profile = coverage_sub.add_parser(
        "evaluate-profile",
        help="Evaluate whether a quick or scoped profile deserves more research",
    )
    evaluate_profile.add_argument("--input", required=True)
    evaluate_profile.add_argument(
        "--policy",
        default="policies/research-allocation.json",
    )
    evaluate_profile.add_argument("--output")
    evaluate_profile.set_defaults(func=cmd_coverage_evaluate_profile)

    record_profile = coverage_sub.add_parser(
        "record-profile",
        help="Seal one quick/scoped profile and apply its deterministic next stage",
    )
    _add_coverage_root(record_profile)
    record_profile.add_argument("--input", required=True)
    record_profile.add_argument(
        "--policy",
        default="policies/research-allocation.json",
    )
    _add_timestamp(record_profile)
    record_profile.set_defaults(func=cmd_coverage_record_profile)

    profile_status = coverage_sub.add_parser(
        "profile-status",
        help="Verify progress and sealed artifacts for one profile cycle",
    )
    _add_coverage_root(profile_status)
    profile_status.add_argument("cycle_id")
    profile_status.set_defaults(func=cmd_coverage_profile_status)

    profile_claim = coverage_sub.add_parser(
        "profile-claim",
        help="Claim one pending profile task for exactly one agent",
    )
    _add_coverage_root(profile_claim)
    profile_claim.add_argument("--agent", required=True)
    profile_claim.add_argument("--symbol")
    profile_claim.add_argument("--lens")
    _add_timestamp(profile_claim)
    profile_claim.set_defaults(func=cmd_coverage_profile_claim)

    profile_release = coverage_sub.add_parser(
        "profile-release",
        help="Release one failed profile claim and preserve its attempt audit",
    )
    _add_coverage_root(profile_release)
    profile_release.add_argument("--agent", required=True)
    profile_release.add_argument("--symbol", required=True)
    profile_release.add_argument("--failure-reason", required=True)
    _add_timestamp(profile_release)
    profile_release.set_defaults(func=cmd_coverage_profile_release)

    set_cmd = coverage_sub.add_parser("set-screening", help="Upsert one screening result")
    set_cmd.add_argument("symbol")
    _add_coverage_root(set_cmd)
    set_cmd.add_argument("--name", required=True)
    set_cmd.add_argument("--decision", required=True)
    set_cmd.add_argument("--priority", type=int)
    set_cmd.add_argument("--reason", required=True)
    set_cmd.add_argument("--evidence", action="append", required=True)
    set_cmd.add_argument("--next-action", required=True)
    set_cmd.set_defaults(func=cmd_coverage_set_screening)

    enqueue = coverage_sub.add_parser("enqueue", help="Upsert one research queue item")
    enqueue.add_argument("symbol")
    _add_coverage_root(enqueue)
    enqueue.add_argument("--name", required=True)
    enqueue.add_argument("--priority", type=int, required=True)
    enqueue.add_argument("--reason", required=True)
    enqueue.add_argument("--task-type", default="initial_research")
    enqueue.add_argument("--status", default="pending")
    enqueue.add_argument("--target-company-dir")
    enqueue.add_argument("--effort-budget-hours", type=float)
    enqueue.add_argument("--preceding-stage")
    enqueue.add_argument("--stop-condition", action="append")
    enqueue.set_defaults(func=cmd_coverage_enqueue)

    reconcile = coverage_sub.add_parser(
        "reconcile", help="Reconcile queue state with valid company assets"
    )
    _add_coverage_root(reconcile)
    reconcile.add_argument("--research-root", default="research")
    reconcile_mode = reconcile.add_mutually_exclusive_group(required=True)
    reconcile_mode.add_argument("--check", action="store_true")
    reconcile_mode.add_argument("--apply", action="store_true")
    reconcile.set_defaults(func=cmd_coverage_reconcile)
    return parser


def cmd_assets_validate(ns: argparse.Namespace) -> int:
    payload = validate_all_assets(ns.research_root)
    if not payload["ok"]:
        return _write_failure(
            {
                **payload,
                "error_code": "asset_validation_failed",
                "error": f"{payload['invalid_count']} company asset(s) are invalid",
            }
        )
    _write_success(payload)
    return 0


def cmd_assets_migrate(ns: argparse.Namespace) -> int:
    if ns.dry_run:
        created_at = _timestamp(ns.at)
        migration_id = ns.migration_id or f"v2-reset-{created_at.date().isoformat()}"
        plan = build_migration_plan(
            ns.research_root,
            migration_id=migration_id,
            created_at=created_at,
        )
        if ns.output:
            write_migration_plan(ns.output, plan)
        _write_success(plan)
        return 1 if plan["error_count"] else 0
    if not ns.plan:
        raise MigrationError("--plan is required with --apply")
    if ns.output or ns.migration_id or ns.at:
        raise MigrationError(
            "--output, --migration-id, and --at are dry-run options"
        )
    result = apply_migration_plan(load_migration_plan(ns.plan))
    _write_success(result)
    return 1 if result["failed_count"] or result["blocked_count"] else 0


def cmd_review_create(ns: argparse.Namespace) -> int:
    state = create_review(
        runs_root=ns.runs_root,
        run_id=ns.run_id,
        scope_type=ns.scope_type,
        market=ns.market,
        description=ns.description,
        candidates=load_candidates(ns.candidates),
        policy_root=ns.policy_root,
        created_at=_timestamp(ns.at),
        parent_run_id=ns.parent_run_id,
    )
    _write_success({"ok": True, "run": state})
    return 0


def cmd_review_prepare(ns: argparse.Namespace) -> int:
    state = prepare_review(
        runs_root=ns.runs_root,
        run_id=ns.run_id,
        prepared_at=_timestamp(ns.at),
    )
    _write_success({"ok": True, "run": state})
    return 0


def cmd_review_status(ns: argparse.Namespace) -> int:
    _write_success(review_status(runs_root=ns.runs_root, run_id=ns.run_id))
    return 0


def cmd_review_resume(ns: argparse.Namespace) -> int:
    state = resume_review(
        runs_root=ns.runs_root,
        run_id=ns.run_id,
        resumed_at=_timestamp(ns.at),
    )
    _write_success({"ok": True, "run": state})
    return 0


def cmd_review_validate(ns: argparse.Namespace) -> int:
    _write_success(
        validate_review(
            runs_root=ns.runs_root,
            run_id=ns.run_id,
            strict=bool(ns.strict),
        )
    )
    return 0


def cmd_review_synthesize(ns: argparse.Namespace) -> int:
    _write_success(
        synthesize_review(
            runs_root=ns.runs_root,
            research_root=ns.research_root,
            policy_root=ns.policy_root,
            run_id=ns.run_id,
            quotes_path=ns.quotes,
            synthesized_at=_timestamp(ns.at),
        )
    )
    return 0


def cmd_review_report(ns: argparse.Namespace) -> int:
    _write_success(
        write_review_report(
            runs_root=ns.runs_root,
            research_root=ns.research_root,
            run_id=ns.run_id,
            reported_at=_timestamp(ns.at),
        )
    )
    return 0


def cmd_review_finalize(ns: argparse.Namespace) -> int:
    _write_success(
        finalize_review_companies(
            runs_root=ns.runs_root,
            research_root=ns.research_root,
            run_id=ns.run_id,
            finalized_at=_timestamp(ns.at),
        )
    )
    return 0


def cmd_review_run(ns: argparse.Namespace) -> int:
    _write_success(
        run_review(
            runs_root=ns.runs_root,
            research_root=ns.research_root,
            policy_root=ns.policy_root,
            run_id=ns.run_id,
            quotes_path=ns.quotes,
            now=_timestamp(ns.at),
        )
    )
    return 0


def cmd_index_rebuild(ns: argparse.Namespace) -> int:
    result = write_index(ns.research_root)
    if not result.ok:
        return _write_failure({"ok": False, "errors": result.errors})
    print(json.dumps({"ok": True, "path": str(result.path)}, ensure_ascii=False, indent=2))
    return 0


def cmd_alerts_build(ns: argparse.Namespace) -> int:
    path = write_price_alerts(ns.research_root, ns.output)
    print(json.dumps({"ok": True, "path": str(path)}, ensure_ascii=False, indent=2))
    return 0


def cmd_alerts_check(ns: argparse.Namespace) -> int:
    alerts = load_json(ns.alerts)
    quotes = load_json(ns.quotes)
    if not isinstance(alerts, dict):
        raise RuntimeError("alerts file must be a JSON object")
    if not isinstance(quotes, list):
        raise RuntimeError("quote snapshot must be a JSON list")
    result = evaluate_price_alerts(alerts, quotes)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_schedule_build(ns: argparse.Namespace) -> int:
    path = write_review_schedule(ns.research_root, ns.output)
    print(json.dumps({"ok": True, "path": str(path)}, ensure_ascii=False, indent=2))
    return 0


def cmd_coverage_validate(ns: argparse.Namespace) -> int:
    status = validate_coverage_root(ns.root)
    print(json.dumps({"ok": True, "status": status}, ensure_ascii=False, indent=2))
    return 0


def cmd_coverage_status(ns: argparse.Namespace) -> int:
    print(json.dumps(coverage_status(ns.root), ensure_ascii=False, indent=2))
    return 0


def cmd_coverage_get(ns: argparse.Namespace) -> int:
    print(json.dumps(get_symbol(ns.root, ns.symbol), ensure_ascii=False, indent=2))
    return 0


def cmd_coverage_list(ns: argparse.Namespace) -> int:
    payload = {
        "schema_version": 1,
        "items": list_screening(ns.root, ns.decision),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_coverage_rank_rebaseline(ns: argparse.Namespace) -> int:
    root = Path(ns.root)
    payload = build_rebaseline_ranking(
        companies_path=ns.companies or root / "companies.jsonl",
        queue_path=root / "research_queue.jsonl",
        screening_path=ns.screening or root / "screening.jsonl",
        research_root=ns.research_root,
        generated_at=_timestamp(ns.at),
        max_snapshot_age_days=ns.max_snapshot_age_days,
    )
    path = write_rebaseline_ranking(ns.output, payload)
    _write_success(
        {
            "ok": True,
            "path": str(path),
            "ranked_count": payload["ranked_count"],
            "excluded_count": payload["excluded_count"],
        }
    )
    return 0


def cmd_coverage_allocate_research(ns: argparse.Namespace) -> int:
    ranking = json.loads(Path(ns.ranking).read_text(encoding="utf-8"))
    policy = load_policy(ns.policy)
    payload = allocate_research_capacity(
        ranking,
        policy=policy.payload,
        policy_version=f"{policy.policy_id}@{policy.version}",
    )
    path = write_research_allocation(ns.output, payload)
    _write_success(
        {
            "ok": True,
            "path": str(path),
            "selected_count": payload["selected_count"],
            "deferred_count": payload["deferred_count"],
            "warnings": payload["warnings"],
        }
    )
    return 0


def cmd_coverage_apply_allocation(ns: argparse.Namespace) -> int:
    ranking = json.loads(Path(ns.ranking).read_text(encoding="utf-8"))
    allocation = json.loads(Path(ns.allocation).read_text(encoding="utf-8"))
    payload = apply_research_allocation(
        allocation,
        ranking=ranking,
        root=ns.root,
        applied_at=_timestamp(ns.at),
    )
    _write_success({"ok": True, **payload})
    return 0


def cmd_coverage_evaluate_profile(ns: argparse.Namespace) -> int:
    profile = json.loads(Path(ns.input).read_text(encoding="utf-8"))
    policy = load_policy(ns.policy)
    payload = evaluate_quick_profile(profile, policy=policy.payload)
    if ns.output:
        write_research_allocation(ns.output, payload)
    _write_success(payload)
    return 0


def cmd_coverage_record_profile(ns: argparse.Namespace) -> int:
    package = json.loads(Path(ns.input).read_text(encoding="utf-8"))
    policy = load_policy(ns.policy)
    payload = record_profile_package(
        package,
        root=ns.root,
        policy=policy.payload,
        policy_reference=f"{policy.policy_id}@{policy.version}",
        recorded_at=_timestamp(ns.at),
    )
    _write_success({"ok": True, **payload})
    return 0


def cmd_coverage_profile_status(ns: argparse.Namespace) -> int:
    payload = profile_cycle_status(root=ns.root, cycle_id=ns.cycle_id)
    _write_success({"ok": payload["invalid_artifact_count"] == 0, **payload})
    return 0


def cmd_coverage_profile_claim(ns: argparse.Namespace) -> int:
    payload = claim_profile_task(
        root=ns.root,
        agent=ns.agent,
        claimed_at=_timestamp(ns.at),
        symbol=ns.symbol,
        lens=ns.lens,
    )
    _write_success({"ok": True, **payload})
    return 0


def cmd_coverage_profile_release(ns: argparse.Namespace) -> int:
    payload = release_profile_task(
        root=ns.root,
        agent=ns.agent,
        symbol=ns.symbol,
        failure_reason=ns.failure_reason,
        released_at=_timestamp(ns.at),
    )
    _write_success({"ok": True, **payload})
    return 0


def cmd_coverage_set_screening(ns: argparse.Namespace) -> int:
    path = set_screening(
        ns.root,
        symbol=ns.symbol,
        name=ns.name,
        decision=ns.decision,
        priority=ns.priority,
        reason=ns.reason,
        evidence=ns.evidence,
        next_action=ns.next_action,
    )
    print(json.dumps({"ok": True, "path": str(path)}, ensure_ascii=False, indent=2))
    return 0


def cmd_coverage_enqueue(ns: argparse.Namespace) -> int:
    path = enqueue_research(
        ns.root,
        symbol=ns.symbol,
        name=ns.name,
        priority=ns.priority,
        reason=ns.reason,
        task_type=ns.task_type,
        status=ns.status,
        target_company_dir=ns.target_company_dir,
        effort_budget_hours=ns.effort_budget_hours,
        preceding_stage=ns.preceding_stage,
        stop_conditions=ns.stop_condition,
    )
    print(json.dumps({"ok": True, "path": str(path)}, ensure_ascii=False, indent=2))
    return 0


def cmd_coverage_reconcile(ns: argparse.Namespace) -> int:
    payload = reconcile_research_queue(
        ns.root,
        ns.research_root,
        apply=bool(ns.apply),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if ns.check and (payload["change_count"] or payload["blocked_count"]):
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv)
    func = getattr(ns, "func", None)
    if not callable(func):
        return 2
    try:
        return int(func(ns))
    except Exception as exc:
        error_code = _error_code(exc)
        if error_code is None:
            raise
        return _write_failure(
            {"ok": False, "error_code": error_code, "error": str(exc)}
        )


def _write_failure(payload: dict[str, object], stream: TextIO | None = None) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=stream or sys.stderr)
    return 1


def _write_success(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _error_code(exc: Exception) -> str | None:
    for error_type, code in (
        (AssetValidationError, "asset_validation_failed"),
        (CoverageValidationError, "coverage_validation_failed"),
        (ReviewStoreError, "review_state_error"),
        (ReviewWorkflowError, "review_workflow_error"),
        (RebaselineRankingError, "rebaseline_ranking_error"),
        (ResearchAllocationError, "research_allocation_error"),
        (ClaimPacketError, "claim_packet_error"),
        (SealingError, "sealed_artifact_error"),
        (PortfolioValidationError, "portfolio_validation_error"),
        (PolicyValidationError, "policy_validation_error"),
        (MigrationError, "migration_error"),
        (FileNotFoundError, "file_not_found"),
        (json.JSONDecodeError, "invalid_json"),
        (RuntimeError, "runtime_error"),
    ):
        if isinstance(exc, error_type):
            return code
    return None


def _add_coverage_root(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", default="coverage/cn-a")


def _add_review_roots(
    parser: argparse.ArgumentParser,
    *,
    research: bool = False,
    policies: bool = False,
) -> None:
    parser.add_argument("--runs-root", default="automation/runs")
    if research:
        parser.add_argument("--research-root", default="research")
    if policies:
        parser.add_argument("--policy-root", default="policies")


def _add_timestamp(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--at",
        help="ISO 8601 timestamp with UTC offset; defaults to the current time",
    )


def _timestamp(value: str | None) -> dt.datetime:
    if value is None:
        return dt.datetime.now().astimezone()
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise ReviewWorkflowError("--at must be an ISO 8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ReviewWorkflowError("--at must include a UTC offset")
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
