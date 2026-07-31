from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import TextIO

from .research_assets.alerts import (
    PriceAlertError,
    evaluate_price_alert_observations,
    evaluate_price_alerts,
    load_json,
    write_price_alerts,
)
from .research_assets.asset_gc import (
    AssetGcError,
    build_asset_gc_plan,
    gc_plan_summary,
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
from .research_assets.lane_arbitration import (
    LaneArbitrationError,
    freeze_lane_arbitration,
    verify_lane_arbitration,
)
from .research_assets.legacy_transition import (
    LegacyTransitionError,
    freeze_legacy_transition,
    legacy_transition_status,
    record_legacy_transition,
)
from .research_assets.manager_screen_allocation_v3 import (
    ManagerScreenAllocationV3Error,
    freeze_manager_screen_allocation_v3_contract,
    manager_screen_allocation_v3_activation_drift_status,
)
from .research_assets.manager_screen_allocation_v3_suspension import (
    ManagerScreenAllocationV3SuspensionError,
    suspend_manager_screen_allocation_v3_revocable_commitments,
    verify_manager_screen_allocation_v3_suspension,
)
from .research_assets.manager_screen_control import (
    ManagerScreenControlError,
    manager_screen_control_status,
    record_manager_screen_control,
)
from .research_assets.manager_screen_governance import (
    ManagerScreenGovernanceError,
    supersede_manager_screen_batch,
)
from .research_assets.manager_screen_quote_impact import (
    ManagerScreenQuoteImpactError,
    manager_screen_quote_impact_status,
    prepare_manager_screen_quote_impact,
    record_manager_screen_quote_impact,
)
from .research_assets.manager_screen_snapshot import (
    DEFAULT_QUOTE_ENDPOINT,
    DEFAULT_TENCENT_QUOTE_ENDPOINT,
    ManagerScreenSnapshotError,
    fetch_eastmoney_previous_close_quotes,
    fetch_tencent_previous_close_quotes,
    prepare_manager_screen_quote_amendment,
    prepare_manager_screen_snapshot,
)
from .research_assets.manager_screening import (
    ManagerScreeningError,
    freeze_manager_screen_batch,
    manager_screen_calibration_status,
    manager_screen_status,
    prepare_manager_screen_calibration,
    record_manager_screen_calibration,
    record_manager_screen_decisions,
)
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
    approve_targeted_followup,
    build_profile_comparison_packet,
    claim_profile_task,
    decline_targeted_followup,
    finalize_profile_stage,
    finalize_profile_stage_with_agent_decisions,
    profile_cycle_status,
    record_profile_package,
    release_profile_task,
)
from .research_assets.quality_audit import (
    QualityAuditError,
    seal_cycle_quality_audit_result,
    seal_scope_identity_audit_result,
)
from .research_assets.quality_workflow import (
    QualityWorkflowError,
    cycle_quality_gate_status,
    cycle_quality_status,
    load_quality_policy_snapshot,
    materialize_cycle_quality_reopens,
    prepare_cycle_quality_audit,
    prepare_cycle_quality_audit_continuation,
    prepare_cycle_quality_correction,
    prepare_scope_identity_quality_audit,
    record_cycle_quality_audit_continuation,
    record_cycle_quality_correction_resolution,
    scope_quality_status,
)
from .research_assets.research_allocation import (
    ResearchAllocationError,
    allocate_research_capacity,
    apply_research_allocation,
    evaluate_quick_profile,
    write_research_allocation,
)
from .research_assets.review_store import ReviewStoreError
from .research_assets.review_workflow import (
    ReviewWorkflowError,
    create_review,
    create_review_from_underwriting_approval,
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
from .research_assets.scope_workflow import (
    ScopeWorkflowError,
    all_a_scope_status,
    freeze_all_a_scope,
)
from .research_assets.sealing import SealingError
from .research_assets.triage_cohort import (
    freeze_rapid_triage_cohort,
    read_symbol_file,
)
from .research_assets.triage_workflow import (
    build_rapid_triage_comparison_packet,
    claim_rapid_triage_task,
    finalize_rapid_triage_cycle,
    rapid_triage_cycle_status,
    record_rapid_triage_package,
    release_rapid_triage_task,
)
from .research_assets.trigger_hits import (
    TriggerHitError,
    create_trigger_hit_checkpoint,
    observe_fact_hit,
    observe_price_condition,
    observe_schedule_hit,
    rebuild_trigger_hit_state,
    verify_trigger_hit_ledger,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trading_os",
        description="Trading OS research asset tools",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    assets = sub.add_parser("assets", help="Validate v2 research assets")
    assets_sub = assets.add_subparsers(dest="assets_cmd", required=True)
    assets_validate = assets_sub.add_parser("validate", help="Validate every v2 company asset")
    assets_validate.add_argument("--research-root", default="research")
    assets_validate.set_defaults(func=cmd_assets_validate)
    assets_gc = assets_sub.add_parser(
        "gc",
        help="Build a conservative reachability plan for research assets",
    )
    assets_gc.add_argument(
        "--plan",
        action="store_true",
        help="Plan only; no files are deleted or moved",
    )
    assets_gc.add_argument("--repository-root", default=".")
    assets_gc.add_argument("--output")
    assets_gc.add_argument(
        "--no-content-hashes",
        action="store_true",
        help="Skip SHA-only reachability (faster but less conservative)",
    )
    _add_timestamp(assets_gc)
    assets_gc.set_defaults(func=cmd_assets_gc)
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
    review_create.add_argument("--coverage-root", default="coverage/cn-a")
    _add_review_roots(review_create, policies=True)
    _add_timestamp(review_create)
    review_create.set_defaults(func=cmd_review_create)

    review_create_approved = review_sub.add_parser(
        "create-from-underwriting-approval",
        help="Create a manager-bound review from a sealed underwriting approval",
    )
    review_create_approved.add_argument("run_id")
    review_create_approved.add_argument("--scope-type", required=True)
    review_create_approved.add_argument("--market", required=True)
    review_create_approved.add_argument("--description", required=True)
    review_create_approved.add_argument("--approval-path", required=True)
    review_create_approved.add_argument("--approval-sha256", required=True)
    review_create_approved.add_argument("--parent-run-id")
    review_create_approved.add_argument(
        "--coverage-root",
        default="coverage/cn-a",
    )
    _add_review_roots(review_create_approved, policies=True)
    _add_timestamp(review_create_approved)
    review_create_approved.set_defaults(func=cmd_review_create_from_underwriting_approval)

    review_prepare = review_sub.add_parser("prepare", help="Build and seal blind claim packets")
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
    alerts_check.add_argument(
        "--record-hits",
        action="store_true",
        help="Append true edges and false rearms to the canonical trigger ledger",
    )
    alerts_check.add_argument("--coverage-root", default="coverage/cn-a")
    alerts_check.add_argument("--actor", default="price-alert-observer")
    _add_timestamp(alerts_check)
    alerts_check.set_defaults(func=cmd_alerts_check)

    schedule = sub.add_parser("schedule", help="Build review schedules")
    schedule_sub = schedule.add_subparsers(dest="schedule_cmd", required=True)
    schedule_build = schedule_sub.add_parser(
        "build",
        help="Build automation/review_schedule.json",
    )
    schedule_build.add_argument("--research-root", default="research")
    schedule_build.add_argument("--output", default="automation/review_schedule.json")
    schedule_build.add_argument(
        "--as-of",
        help="ISO datetime used to mark date and evidence-expiry items due",
    )
    schedule_build.add_argument(
        "--record-hits",
        action="store_true",
        help="Record due date/TTL rows in the canonical trigger ledger",
    )
    schedule_build.add_argument("--coverage-root", default="coverage/cn-a")
    schedule_build.add_argument("--actor", default="schedule-observer")
    _add_timestamp(schedule_build)
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

    scope_freeze = coverage_sub.add_parser(
        "scope-freeze",
        help="Freeze a conserved all-A scope and materialize its baseline intake",
    )
    _add_coverage_root(scope_freeze)
    scope_freeze.add_argument("run_id")
    scope_freeze.add_argument("--mode", choices=["auto", "baseline", "incremental"], default="auto")
    scope_freeze.add_argument(
        "--scope-cutoff",
        required=True,
        help="Frozen information cutoff as an ISO 8601 timestamp with UTC offset",
    )
    scope_freeze.add_argument("--universe-file")
    scope_freeze.add_argument(
        "--no-apply-intake",
        action="store_true",
        help="Seal scope and intake without materializing coverage queue rows",
    )
    _add_timestamp(scope_freeze)
    scope_freeze.set_defaults(func=cmd_coverage_scope_freeze)

    scope_status = coverage_sub.add_parser(
        "scope-status",
        help="Verify a frozen all-A scope, baseline intake, and queue materialization",
    )
    _add_coverage_root(scope_status)
    scope_status.add_argument("run_id")
    scope_status.set_defaults(func=cmd_coverage_scope_status)

    manager_screen_snapshot = coverage_sub.add_parser(
        "manager-screen-snapshot",
        help="Build one compact fact-only company snapshot for manager screening",
    )
    _add_coverage_root(manager_screen_snapshot)
    manager_screen_snapshot.add_argument("run_id")
    manager_screen_snapshot.add_argument(
        "--information-cutoff",
        required=True,
        help="Information cutoff as an ISO 8601 timestamp with UTC offset",
    )
    manager_screen_snapshot.add_argument("--output")
    manager_screen_snapshot.add_argument(
        "--quotes",
        help="Full-universe quote JSON array to inject into a newly created snapshot",
    )
    manager_screen_snapshot.add_argument(
        "--quote-max-age-hours",
        type=float,
        default=72.0,
        help="Maximum quote age at the information cutoff (default: 72 hours)",
    )
    manager_screen_snapshot.add_argument(
        "--endpoint",
        default="https://datacenter.eastmoney.com/securities/api/data/v1/get",
    )
    manager_screen_snapshot.add_argument("--page-size", type=int, default=500)
    _add_timestamp(manager_screen_snapshot)
    manager_screen_snapshot.set_defaults(func=cmd_coverage_manager_screen_snapshot)

    manager_screen_quote_amend = coverage_sub.add_parser(
        "manager-screen-quote-amend",
        help="Seal a full-universe quote overlay without changing the frozen fact snapshot",
    )
    _add_coverage_root(manager_screen_quote_amend)
    manager_screen_quote_amend.add_argument("run_id")
    manager_screen_quote_amend.add_argument("amendment_id")
    quote_amend_source = manager_screen_quote_amend.add_mutually_exclusive_group(required=True)
    quote_amend_source.add_argument("--quotes")
    quote_amend_source.add_argument(
        "--eastmoney-previous-close-date",
        help="Fetch Eastmoney f18 and bind it to this explicit YYYY-MM-DD close",
    )
    quote_amend_source.add_argument(
        "--tencent-previous-close-date",
        help=("Fetch Tencent field 4 and bind it to this explicit YYYY-MM-DD close"),
    )
    manager_screen_quote_amend.add_argument("--output")
    manager_screen_quote_amend.add_argument(
        "--quote-endpoint",
        default=DEFAULT_QUOTE_ENDPOINT,
    )
    manager_screen_quote_amend.add_argument(
        "--tencent-quote-endpoint",
        default=DEFAULT_TENCENT_QUOTE_ENDPOINT,
    )
    manager_screen_quote_amend.add_argument(
        "--quote-chunk-size",
        type=int,
        default=80,
    )
    manager_screen_quote_amend.add_argument(
        "--quote-max-age-hours",
        type=float,
        default=72.0,
        help="Maximum quote age at amendment effective time (default: 72 hours)",
    )
    _add_timestamp(manager_screen_quote_amend)
    manager_screen_quote_amend.set_defaults(func=cmd_coverage_manager_screen_quote_amend)

    manager_screen_freeze = coverage_sub.add_parser(
        "manager-screen-freeze",
        help="Freeze one 100-200 company packet for a single investment-manager Agent",
    )
    _add_coverage_root(manager_screen_freeze)
    manager_screen_freeze.add_argument("run_id")
    manager_screen_freeze.add_argument("batch_id")
    manager_screen_freeze.add_argument("--batch-size", type=int)
    manager_screen_freeze.add_argument(
        "--policy",
        default="policies/manager-screening.json",
    )
    _add_timestamp(manager_screen_freeze)
    manager_screen_freeze.set_defaults(func=cmd_coverage_manager_screen_freeze)

    manager_screen_record = coverage_sub.add_parser(
        "manager-screen-record",
        help="Seal one complete manager decision and route only selected analyst work",
    )
    _add_coverage_root(manager_screen_record)
    manager_screen_record.add_argument("run_id")
    manager_screen_record.add_argument("batch_id")
    manager_screen_record.add_argument("--input", required=True)
    _add_timestamp(manager_screen_record)
    manager_screen_record.set_defaults(func=cmd_coverage_manager_screen_record)

    manager_screen_status_cmd = coverage_sub.add_parser(
        "manager-screen-status",
        help="Verify manager-screen batches and report scope progress",
    )
    _add_coverage_root(manager_screen_status_cmd)
    manager_screen_status_cmd.add_argument("run_id")
    manager_screen_status_cmd.add_argument("--batch-id")
    manager_screen_status_cmd.set_defaults(func=cmd_coverage_manager_screen_status)

    manager_screen_control_record = coverage_sub.add_parser(
        "manager-screen-control-record",
        help="Append a sealed run-control event for manager-screen production",
    )
    _add_coverage_root(manager_screen_control_record)
    manager_screen_control_record.add_argument("run_id")
    manager_screen_control_record.add_argument("event_id")
    manager_screen_control_record.add_argument(
        "--state",
        required=True,
        choices=("paused", "controlled", "active"),
    )
    manager_screen_control_record.add_argument("--manager-agent", required=True)
    manager_screen_control_record.add_argument("--manager-model", required=True)
    manager_screen_control_record.add_argument(
        "--manager-tool",
        action="append",
        required=True,
    )
    manager_screen_control_record.add_argument("--reason", required=True)
    manager_screen_control_record.add_argument("--company-limit", type=int)
    _add_timestamp(manager_screen_control_record)
    manager_screen_control_record.set_defaults(func=cmd_coverage_manager_screen_control_record)

    manager_screen_control_status_cmd = coverage_sub.add_parser(
        "manager-screen-control-status",
        help="Verify and report the effective manager-screen run control",
    )
    _add_coverage_root(manager_screen_control_status_cmd)
    manager_screen_control_status_cmd.add_argument("run_id")
    manager_screen_control_status_cmd.set_defaults(func=cmd_coverage_manager_screen_control_status)

    manager_screen_allocation_v3_freeze = coverage_sub.add_parser(
        "manager-screen-allocation-v3-freeze",
        help="Seal the run-level v3 research-allocation contract",
    )
    _add_coverage_root(manager_screen_allocation_v3_freeze)
    manager_screen_allocation_v3_freeze.add_argument("run_id")
    manager_screen_allocation_v3_freeze.add_argument(
        "--prior-policy",
        default="policies/manager-screening.json",
    )
    manager_screen_allocation_v3_freeze.add_argument(
        "--future-policy",
        default="policies/manager-screening-allocation-v3.json",
    )
    manager_screen_allocation_v3_freeze.add_argument(
        "--manager-agent",
        required=True,
    )
    manager_screen_allocation_v3_freeze.add_argument(
        "--manager-model",
        required=True,
    )
    manager_screen_allocation_v3_freeze.add_argument(
        "--manager-tool",
        action="append",
        required=True,
    )
    manager_screen_allocation_v3_freeze.add_argument("--reason", required=True)
    _add_timestamp(manager_screen_allocation_v3_freeze)
    manager_screen_allocation_v3_freeze.set_defaults(
        func=cmd_coverage_manager_screen_allocation_v3_freeze
    )

    manager_screen_allocation_v3_status_cmd = coverage_sub.add_parser(
        "manager-screen-allocation-v3-status",
        help="Verify the v3 allocation contract and report activation-queue drift",
    )
    _add_coverage_root(manager_screen_allocation_v3_status_cmd)
    manager_screen_allocation_v3_status_cmd.add_argument("run_id")
    manager_screen_allocation_v3_status_cmd.set_defaults(
        func=cmd_coverage_manager_screen_allocation_v3_status
    )

    manager_screen_allocation_v3_suspend = coverage_sub.add_parser(
        "manager-screen-allocation-v3-suspend",
        help="Seal and materialize suspension of pristine inherited commitments",
    )
    _add_coverage_root(manager_screen_allocation_v3_suspend)
    manager_screen_allocation_v3_suspend.add_argument("run_id")
    manager_screen_allocation_v3_suspend.add_argument(
        "--manager-agent",
        required=True,
    )
    manager_screen_allocation_v3_suspend.add_argument(
        "--manager-model",
        required=True,
    )
    manager_screen_allocation_v3_suspend.add_argument(
        "--manager-tool",
        action="append",
        required=True,
    )
    manager_screen_allocation_v3_suspend.add_argument("--reason", required=True)
    _add_timestamp(manager_screen_allocation_v3_suspend)
    manager_screen_allocation_v3_suspend.set_defaults(
        func=cmd_coverage_manager_screen_allocation_v3_suspend
    )

    manager_screen_allocation_v3_suspension_status = coverage_sub.add_parser(
        "manager-screen-allocation-v3-suspension-status",
        help="Verify the sealed v3 suspension and its coverage projection",
    )
    _add_coverage_root(manager_screen_allocation_v3_suspension_status)
    manager_screen_allocation_v3_suspension_status.add_argument("run_id")
    manager_screen_allocation_v3_suspension_status.set_defaults(
        func=cmd_coverage_manager_screen_allocation_v3_suspension_status
    )

    manager_screen_quote_impact_prepare = coverage_sub.add_parser(
        "manager-screen-quote-impact-prepare",
        help="Seal administrative review candidates from a quote amendment",
    )
    _add_coverage_root(manager_screen_quote_impact_prepare)
    manager_screen_quote_impact_prepare.add_argument("run_id")
    manager_screen_quote_impact_prepare.add_argument("batch_id")
    manager_screen_quote_impact_prepare.add_argument("review_id")
    manager_screen_quote_impact_prepare.add_argument(
        "--quote-amendment",
        required=True,
    )
    manager_screen_quote_impact_prepare.add_argument(
        "--policy",
        default="policies/manager-screening.json",
    )
    _add_timestamp(manager_screen_quote_impact_prepare)
    manager_screen_quote_impact_prepare.set_defaults(
        func=cmd_coverage_manager_screen_quote_impact_prepare
    )

    manager_screen_quote_impact_record = coverage_sub.add_parser(
        "manager-screen-quote-impact-record",
        help="Seal original-manager keep or replacement decisions",
    )
    _add_coverage_root(manager_screen_quote_impact_record)
    manager_screen_quote_impact_record.add_argument("run_id")
    manager_screen_quote_impact_record.add_argument("batch_id")
    manager_screen_quote_impact_record.add_argument("review_id")
    manager_screen_quote_impact_record.add_argument("--input", required=True)
    _add_timestamp(manager_screen_quote_impact_record)
    manager_screen_quote_impact_record.set_defaults(
        func=cmd_coverage_manager_screen_quote_impact_record
    )

    manager_screen_quote_impact_status_cmd = coverage_sub.add_parser(
        "manager-screen-quote-impact-status",
        help="Verify a sealed quote-impact review and materialization",
    )
    _add_coverage_root(manager_screen_quote_impact_status_cmd)
    manager_screen_quote_impact_status_cmd.add_argument("run_id")
    manager_screen_quote_impact_status_cmd.add_argument("batch_id")
    manager_screen_quote_impact_status_cmd.add_argument("review_id")
    manager_screen_quote_impact_status_cmd.set_defaults(
        func=cmd_coverage_manager_screen_quote_impact_status
    )

    manager_screen_supersede = coverage_sub.add_parser(
        "manager-screen-supersede",
        help="Seal the supersession of an unrecorded batch and release its members",
    )
    _add_coverage_root(manager_screen_supersede)
    manager_screen_supersede.add_argument("run_id")
    manager_screen_supersede.add_argument("batch_id")
    manager_screen_supersede.add_argument("--input", required=True)
    _add_timestamp(manager_screen_supersede)
    manager_screen_supersede.set_defaults(func=cmd_coverage_manager_screen_supersede)

    manager_screen_calibration_prepare = coverage_sub.add_parser(
        "manager-screen-calibration-prepare",
        help="Seal one independent factual-calibration packet",
    )
    _add_coverage_root(manager_screen_calibration_prepare)
    manager_screen_calibration_prepare.add_argument("run_id")
    manager_screen_calibration_prepare.add_argument("batch_id")
    manager_screen_calibration_prepare.add_argument("calibration_id")
    manager_screen_calibration_prepare.add_argument(
        "--policy",
        default="policies/manager-screening.json",
    )
    _add_timestamp(manager_screen_calibration_prepare)
    manager_screen_calibration_prepare.set_defaults(
        func=cmd_coverage_manager_screen_calibration_prepare
    )

    manager_screen_calibration_record = coverage_sub.add_parser(
        "manager-screen-calibration-record",
        help="Seal one complete independent factual-calibration result",
    )
    _add_coverage_root(manager_screen_calibration_record)
    manager_screen_calibration_record.add_argument("run_id")
    manager_screen_calibration_record.add_argument("batch_id")
    manager_screen_calibration_record.add_argument("calibration_id")
    manager_screen_calibration_record.add_argument("--input", required=True)
    _add_timestamp(manager_screen_calibration_record)
    manager_screen_calibration_record.set_defaults(
        func=cmd_coverage_manager_screen_calibration_record
    )

    manager_screen_calibration_status_cmd = coverage_sub.add_parser(
        "manager-screen-calibration-status",
        help="Verify factual-calibration coverage and results",
    )
    _add_coverage_root(manager_screen_calibration_status_cmd)
    manager_screen_calibration_status_cmd.add_argument("run_id")
    manager_screen_calibration_status_cmd.add_argument("--batch-id")
    manager_screen_calibration_status_cmd.set_defaults(
        func=cmd_coverage_manager_screen_calibration_status
    )

    manager_screen_transition_freeze = coverage_sub.add_parser(
        "manager-screen-transition-freeze",
        help="Freeze the one-time legacy adoption/rescreen transition",
    )
    _add_coverage_root(manager_screen_transition_freeze)
    manager_screen_transition_freeze.add_argument("run_id")
    manager_screen_transition_freeze.add_argument("--input", required=True)
    _add_timestamp(manager_screen_transition_freeze)
    manager_screen_transition_freeze.set_defaults(
        func=cmd_coverage_manager_screen_transition_freeze
    )

    manager_screen_transition_record = coverage_sub.add_parser(
        "manager-screen-transition-record",
        help="Seal manager decisions for the one-time legacy transition",
    )
    _add_coverage_root(manager_screen_transition_record)
    manager_screen_transition_record.add_argument("run_id")
    manager_screen_transition_record.add_argument("--input", required=True)
    _add_timestamp(manager_screen_transition_record)
    manager_screen_transition_record.set_defaults(
        func=cmd_coverage_manager_screen_transition_record
    )

    manager_screen_transition_status_cmd = coverage_sub.add_parser(
        "manager-screen-transition-status",
        help="Verify the one-time legacy transition and materialization",
    )
    _add_coverage_root(manager_screen_transition_status_cmd)
    manager_screen_transition_status_cmd.add_argument("run_id")
    manager_screen_transition_status_cmd.set_defaults(
        func=cmd_coverage_manager_screen_transition_status
    )

    trigger_observe = coverage_sub.add_parser(
        "trigger-observe",
        help="Record one evidenced filing, event, thesis, date, or TTL occurrence",
    )
    _add_coverage_root(trigger_observe)
    trigger_observe.add_argument("--input", required=True)
    _add_timestamp(trigger_observe)
    trigger_observe.set_defaults(func=cmd_coverage_trigger_observe)

    trigger_status = coverage_sub.add_parser(
        "trigger-status", help="Verify the canonical trigger-hit hash chain and projection"
    )
    _add_coverage_root(trigger_status)
    trigger_status.set_defaults(func=cmd_coverage_trigger_status)

    trigger_rebuild = coverage_sub.add_parser(
        "trigger-rebuild", help="Rebuild the trigger-hit projection from the canonical ledger"
    )
    _add_coverage_root(trigger_rebuild)
    trigger_rebuild.set_defaults(func=cmd_coverage_trigger_rebuild)

    trigger_checkpoint = coverage_sub.add_parser(
        "trigger-checkpoint", help="Seal the trigger-ledger prefix visible to one frozen run"
    )
    _add_coverage_root(trigger_checkpoint)
    trigger_checkpoint.add_argument("run_id")
    trigger_checkpoint.add_argument("--scope-manifest")
    _add_timestamp(trigger_checkpoint)
    trigger_checkpoint.set_defaults(func=cmd_coverage_trigger_checkpoint)

    lane_freeze = coverage_sub.add_parser(
        "lane-freeze", help="Seal incremental intake and baseline/incremental arbitration"
    )
    _add_coverage_root(lane_freeze)
    lane_freeze.add_argument("run_id")
    lane_freeze.add_argument("--baseline-minimum-slots", type=int, default=1)
    lane_freeze.add_argument("--no-apply", action="store_true")
    _add_timestamp(lane_freeze)
    lane_freeze.set_defaults(func=cmd_coverage_lane_freeze)

    lane_status = coverage_sub.add_parser(
        "lane-status", help="Verify sealed lane inputs, decisions, and queue bindings"
    )
    _add_coverage_root(lane_status)
    lane_status.add_argument("run_id")
    lane_status.set_defaults(func=cmd_coverage_lane_status)

    quality_scope_prepare = coverage_sub.add_parser(
        "quality-scope-prepare",
        help="Seal the policy snapshot and 100%% hard-exclusion identity audit plan",
    )
    _add_coverage_root(quality_scope_prepare)
    quality_scope_prepare.add_argument("run_id")
    quality_scope_prepare.add_argument("--policy", default="policies/triage-quality-audit.json")
    _add_timestamp(quality_scope_prepare)
    quality_scope_prepare.set_defaults(func=cmd_coverage_quality_scope_prepare)

    quality_scope_record = coverage_sub.add_parser(
        "quality-scope-record", help="Seal independent hard-exclusion identity reviews"
    )
    _add_coverage_root(quality_scope_record)
    quality_scope_record.add_argument("run_id")
    quality_scope_record.add_argument("--reviews", required=True)
    _add_timestamp(quality_scope_record)
    quality_scope_record.set_defaults(func=cmd_coverage_quality_scope_record)

    quality_scope_status_cmd = coverage_sub.add_parser(
        "quality-scope-status", help="Verify scope quality bindings and result status"
    )
    _add_coverage_root(quality_scope_status_cmd)
    quality_scope_status_cmd.add_argument("run_id")
    quality_scope_status_cmd.set_defaults(func=cmd_coverage_quality_scope_status)

    quality_triage_prepare = coverage_sub.add_parser(
        "quality-triage-prepare",
        help="Seal a deterministic half-blind false-negative audit plan",
    )
    _add_coverage_root(quality_triage_prepare)
    quality_triage_prepare.add_argument("cycle_id")
    quality_triage_prepare.add_argument("--policy", default="policies/triage-quality-audit.json")
    _add_timestamp(quality_triage_prepare)
    quality_triage_prepare.set_defaults(func=cmd_coverage_quality_triage_prepare)

    quality_triage_record = coverage_sub.add_parser(
        "quality-triage-record", help="Seal independent triage quality reviews"
    )
    _add_coverage_root(quality_triage_record)
    quality_triage_record.add_argument("cycle_id")
    quality_triage_record.add_argument("--reviews", required=True)
    _add_timestamp(quality_triage_record)
    quality_triage_record.set_defaults(func=cmd_coverage_quality_triage_record)

    quality_triage_continue = coverage_sub.add_parser(
        "quality-triage-continue",
        help="Seal the next deterministic expansion or full-census redo round",
    )
    _add_coverage_root(quality_triage_continue)
    quality_triage_continue.add_argument("cycle_id")
    _add_timestamp(quality_triage_continue)
    quality_triage_continue.set_defaults(func=cmd_coverage_quality_triage_continue)

    quality_triage_record_continuation = coverage_sub.add_parser(
        "quality-triage-record-continuation",
        help="Seal independent reviews for the latest quality continuation round",
    )
    _add_coverage_root(quality_triage_record_continuation)
    quality_triage_record_continuation.add_argument("cycle_id")
    quality_triage_record_continuation.add_argument("--reviews", required=True)
    _add_timestamp(quality_triage_record_continuation)
    quality_triage_record_continuation.set_defaults(
        func=cmd_coverage_quality_triage_record_continuation
    )

    quality_triage_correction_prepare = coverage_sub.add_parser(
        "quality-triage-correction-prepare",
        help="Freeze a correction cohort bound to unresolved quality reopens",
    )
    _add_coverage_root(quality_triage_correction_prepare)
    quality_triage_correction_prepare.add_argument("cycle_id")
    quality_triage_correction_prepare.add_argument("correction_cycle_id")
    _add_timestamp(quality_triage_correction_prepare)
    quality_triage_correction_prepare.set_defaults(
        func=cmd_coverage_quality_triage_correction_prepare
    )

    quality_triage_correction_resolve = coverage_sub.add_parser(
        "quality-triage-correction-resolve",
        help="Seal corrected packages after the correction quality gate passes",
    )
    _add_coverage_root(quality_triage_correction_resolve)
    quality_triage_correction_resolve.add_argument("cycle_id")
    quality_triage_correction_resolve.add_argument("correction_cycle_id")
    _add_timestamp(quality_triage_correction_resolve)
    quality_triage_correction_resolve.set_defaults(
        func=cmd_coverage_quality_triage_correction_resolve
    )

    quality_triage_status_cmd = coverage_sub.add_parser(
        "quality-triage-status", help="Verify cycle quality bindings and result status"
    )
    _add_coverage_root(quality_triage_status_cmd)
    quality_triage_status_cmd.add_argument("cycle_id")
    quality_triage_status_cmd.set_defaults(func=cmd_coverage_quality_triage_status)

    allocate_research = coverage_sub.add_parser(
        "allocate-research",
        help="Allocate finite research capacity across an explicit frozen input",
    )
    allocate_research.add_argument(
        "--ranking",
        required=True,
        help="Existing frozen research-priority input",
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
        required=True,
        help="Frozen input used to produce the allocation",
    )
    apply_allocation.add_argument(
        "--allocation",
        default="automation/research_allocation.json",
    )
    _add_timestamp(apply_allocation)
    apply_allocation.set_defaults(func=cmd_coverage_apply_allocation)

    triage_freeze = coverage_sub.add_parser(
        "triage-freeze",
        help="Freeze an administrative rapid-triage cohort without investment ranking",
    )
    _add_coverage_root(triage_freeze)
    triage_freeze.add_argument("cycle_id")
    triage_freeze.add_argument(
        "--queue-status",
        default="requires_rebaseline",
        help="Queue status used for administrative intake",
    )
    freeze_source = triage_freeze.add_mutually_exclusive_group(required=True)
    freeze_source.add_argument("--limit", type=int)
    freeze_source.add_argument("--symbols-file")
    triage_freeze.add_argument("--after-symbol")
    triage_freeze.add_argument(
        "--scope-run-id",
        help="Bind the cohort to a sealed all-A scope and baseline intake",
    )
    triage_freeze.add_argument(
        "--quality-policy-snapshot",
        help="Canonical passed scope identity audit policy snapshot for schema-v3 production",
    )
    triage_freeze.add_argument(
        "--scope-identity-result",
        help="Canonical passed 100%% hard-exclusion identity audit result",
    )
    _add_timestamp(triage_freeze)
    triage_freeze.set_defaults(func=cmd_coverage_triage_freeze)

    triage_claim = coverage_sub.add_parser(
        "triage-claim",
        help="Claim one 15-minute rapid-triage task for exactly one agent",
    )
    _add_coverage_root(triage_claim)
    triage_claim.add_argument("cycle_id", nargs="?")
    triage_claim.add_argument("--agent", required=True)
    triage_claim.add_argument("--symbol")
    triage_claim.add_argument("--lens")
    _add_timestamp(triage_claim)
    triage_claim.set_defaults(func=cmd_coverage_triage_claim)

    triage_release = coverage_sub.add_parser(
        "triage-release",
        help="Release one failed rapid-triage claim and preserve its attempt audit",
    )
    _add_coverage_root(triage_release)
    triage_release.add_argument("--agent", required=True)
    triage_release.add_argument("--symbol", required=True)
    triage_release.add_argument("--failure-reason", required=True)
    _add_timestamp(triage_release)
    triage_release.set_defaults(func=cmd_coverage_triage_release)

    triage_record = coverage_sub.add_parser(
        "triage-record",
        help="Seal one rapid-triage result without completion-order promotion",
    )
    _add_coverage_root(triage_record)
    triage_record.add_argument("--input", required=True)
    _add_timestamp(triage_record)
    triage_record.set_defaults(func=cmd_coverage_triage_record)

    triage_status = coverage_sub.add_parser(
        "triage-status",
        help="Verify one rapid-triage cohort and its sealed artifacts",
    )
    _add_coverage_root(triage_status)
    triage_status.add_argument("cycle_id")
    triage_status.set_defaults(func=cmd_coverage_triage_status)

    triage_compare = coverage_sub.add_parser(
        "triage-compare",
        help="Seal a score-free comparison packet for an independent Agent",
    )
    _add_coverage_root(triage_compare)
    triage_compare.add_argument("cycle_id")
    _add_timestamp(triage_compare)
    triage_compare.set_defaults(func=cmd_coverage_triage_compare)

    triage_finalize = coverage_sub.add_parser(
        "triage-finalize",
        help="Compare a complete rapid-triage cohort and grant formal-profile budget",
    )
    _add_coverage_root(triage_finalize)
    triage_finalize.add_argument("cycle_id")
    triage_finalize.add_argument(
        "--decisions",
        required=True,
        help="Independent Agent decision package bound to comparison_sha256",
    )
    triage_finalize.add_argument(
        "--policy",
        default="policies/research-allocation.json",
    )
    _add_timestamp(triage_finalize)
    triage_finalize.set_defaults(func=cmd_coverage_triage_finalize)

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
    profile_claim.add_argument(
        "--run-id",
        help=(
            "Manager-screen run to claim from. Symbol-less claims otherwise use "
            "the lexicographically latest eligible manager-bound run."
        ),
    )
    profile_claim.add_argument(
        "--stage",
        choices=[
            "quick_profile",
            "targeted_followup",
            "scoped_research",
            "deep_research",
        ],
        help="Task stage to claim; defaults to quick_profile when symbol is omitted.",
    )
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

    profile_followup_approve = coverage_sub.add_parser(
        "profile-followup-approve",
        help="Explicitly approve one analyst-recommended targeted followup",
    )
    _add_coverage_root(profile_followup_approve)
    profile_followup_approve.add_argument("--symbol", required=True)
    profile_followup_approve.add_argument("--manager", required=True)
    profile_followup_approve.add_argument("--reason", required=True)
    profile_followup_approve.add_argument(
        "--policy",
        default="policies/research-allocation.json",
    )
    _add_timestamp(profile_followup_approve)
    profile_followup_approve.set_defaults(func=cmd_coverage_profile_followup_approve)

    profile_followup_decline = coverage_sub.add_parser(
        "profile-followup-decline",
        help="Seal the original manager's decision not to buy targeted followup",
    )
    _add_coverage_root(profile_followup_decline)
    profile_followup_decline.add_argument("--symbol", required=True)
    profile_followup_decline.add_argument("--manager", required=True)
    profile_followup_decline.add_argument(
        "--outcome",
        required=True,
        choices=["price_watch", "watch_only", "conditional_stop"],
    )
    profile_followup_decline.add_argument("--reason", required=True)
    profile_followup_decline.add_argument(
        "--triggers",
        required=True,
        help="JSON array of executable restart triggers",
    )
    _add_timestamp(profile_followup_decline)
    profile_followup_decline.set_defaults(func=cmd_coverage_profile_followup_decline)

    profile_compare = coverage_sub.add_parser(
        "profile-compare",
        help="Seal a score-free L2/L3 packet for an independent Agent",
    )
    _add_coverage_root(profile_compare)
    profile_compare.add_argument("cycle_id")
    profile_compare.add_argument(
        "--stage",
        required=True,
        choices=["quick_profile", "scoped_research"],
    )
    _add_timestamp(profile_compare)
    profile_compare.set_defaults(func=cmd_coverage_profile_compare)

    profile_select = coverage_sub.add_parser(
        "profile-select",
        help="Apply an independent Agent's full L2/L3 allocation decisions",
    )
    _add_coverage_root(profile_select)
    profile_select.add_argument("cycle_id")
    profile_select.add_argument(
        "--stage",
        required=True,
        choices=["quick_profile", "scoped_research"],
    )
    profile_select.add_argument(
        "--decisions",
        required=True,
        help="Independent Agent decision package bound to comparison_sha256",
    )
    profile_select.add_argument(
        "--policy",
        default="policies/research-allocation.json",
    )
    _add_timestamp(profile_select)
    profile_select.set_defaults(func=cmd_coverage_profile_select)

    profile_finalize = coverage_sub.add_parser(
        "profile-finalize",
        help="Legacy score-based profile allocation; do not use for new Goals",
    )
    _add_coverage_root(profile_finalize)
    profile_finalize.add_argument("cycle_id")
    profile_finalize.add_argument(
        "--stage",
        required=True,
        choices=["quick_profile", "scoped_research"],
    )
    profile_finalize.add_argument(
        "--policy",
        default="policies/research-allocation.json",
    )
    _add_timestamp(profile_finalize)
    profile_finalize.set_defaults(func=cmd_coverage_profile_finalize)

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


def cmd_assets_gc(ns: argparse.Namespace) -> int:
    if not ns.plan:
        raise AssetGcError("assets gc is read-only and requires --plan")
    plan = build_asset_gc_plan(
        repository_root=ns.repository_root,
        planned_at=_timestamp(ns.at),
        hash_candidate_content=not ns.no_content_hashes,
        output_path=ns.output,
    )
    _write_success({"ok": True, **gc_plan_summary(plan)})
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
        raise MigrationError("--output, --migration-id, and --at are dry-run options")
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
        coverage_root=ns.coverage_root,
    )
    _write_success({"ok": True, "run": state})
    return 0


def cmd_review_create_from_underwriting_approval(ns: argparse.Namespace) -> int:
    state = create_review_from_underwriting_approval(
        runs_root=ns.runs_root,
        coverage_root=ns.coverage_root,
        run_id=ns.run_id,
        scope_type=ns.scope_type,
        market=ns.market,
        description=ns.description,
        approval_path=ns.approval_path,
        approval_sha256=ns.approval_sha256,
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
    result = evaluate_price_alerts(
        alerts,
        quotes,
        evaluated_at=_timestamp(ns.at),
    )
    if ns.record_hits:
        evaluated_at = _timestamp(ns.at)
        alerts_sha = hashlib.sha256(Path(ns.alerts).read_bytes()).hexdigest()
        quotes_sha = hashlib.sha256(Path(ns.quotes).read_bytes()).hexdigest()
        ledger_results = []
        for observation in evaluate_price_alert_observations(
            alerts, quotes, evaluated_at=evaluated_at
        ):
            alert = observation["alert"]
            quote = observation["quote"]
            observed_price = next(
                (
                    float(quote[key])
                    for key in ("price", "close", "last")
                    if isinstance(quote.get(key), (int, float))
                    and not isinstance(quote.get(key), bool)
                ),
                None,
            )
            ledger_results.append(
                observe_price_condition(
                    root=ns.coverage_root,
                    trigger={
                        "trigger_id": alert["alert_id"],
                        "type": "price",
                        "source_kind": str(alert.get("type") or "price_alert"),
                        "definition_ref": str(ns.alerts),
                        "definition_source_sha256": alerts_sha,
                        "definition": {
                            "condition": alert["condition"],
                            "reason": alert.get("reason"),
                            "source_ref": alert.get("source_ref"),
                        },
                    },
                    quote_evidence={
                        "symbol": alert["symbol"],
                        "quote_as_of": quote["as_of"],
                        "observed_price": observed_price,
                        "source_ref": str(ns.quotes),
                        "source_sha256": quotes_sha,
                    },
                    condition_met=observation["condition_met"],
                    actor=ns.actor,
                    recorded_at=evaluated_at,
                    workflow_target=(
                        "portfolio_refresh"
                        if str(alert.get("type", "")).startswith("portfolio_")
                        else "company_research"
                    ),
                )
            )
        result["trigger_ledger_observations"] = ledger_results
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_schedule_build(ns: argparse.Namespace) -> int:
    requested_as_of = (
        _timestamp(ns.as_of) if ns.as_of else _timestamp(ns.at) if ns.record_hits else None
    )
    path = write_review_schedule(
        ns.research_root,
        ns.output,
        as_of=requested_as_of,
    )
    result: dict[str, object] = {"ok": True, "path": str(path)}
    if ns.record_hits:
        payload = load_json(path)
        schedule_sha = hashlib.sha256(path.read_bytes()).hexdigest()
        schedule_as_of = dt.datetime.fromisoformat(payload["as_of"])
        recorded_at = _timestamp(ns.at)
        ledger_results = []
        for item in payload.get("items", []):
            if (
                isinstance(item, dict)
                and item.get("state") == "due"
                and item.get("type") in {"date", "ttl"}
                and item.get("trigger_id") != "research-rebaseline"
            ):
                ledger_results.append(
                    observe_schedule_hit(
                        root=ns.coverage_root,
                        item=item,
                        schedule_as_of=schedule_as_of,
                        schedule_ref=str(path),
                        schedule_sha256=schedule_sha,
                        actor=ns.actor,
                        recorded_at=recorded_at,
                    )
                )
        result["trigger_ledger_observations"] = ledger_results
    print(json.dumps(result, ensure_ascii=False, indent=2))
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


def cmd_coverage_scope_freeze(ns: argparse.Namespace) -> int:
    payload = freeze_all_a_scope(
        root=ns.root,
        run_id=ns.run_id,
        scope_cutoff=_timestamp(ns.scope_cutoff),
        frozen_at=_timestamp(ns.at),
        mode=ns.mode,
        universe_path=ns.universe_file,
        apply_intake=not ns.no_apply_intake,
    )
    _write_success({"ok": True, **payload})
    return 0


def cmd_coverage_scope_status(ns: argparse.Namespace) -> int:
    payload = all_a_scope_status(root=ns.root, run_id=ns.run_id)
    _write_success(payload)
    return 0


def cmd_coverage_manager_screen_snapshot(ns: argparse.Namespace) -> int:
    quote_snapshot = _load_json_array(ns.quotes, "quote snapshot") if ns.quotes else None
    payload = prepare_manager_screen_snapshot(
        root=ns.root,
        run_id=ns.run_id,
        information_cutoff=_timestamp(ns.information_cutoff),
        fetched_at=_timestamp(ns.at),
        output_path=ns.output,
        endpoint=ns.endpoint,
        page_size=ns.page_size,
        quote_snapshot=quote_snapshot,
        quote_max_age=_positive_hours(
            ns.quote_max_age_hours,
            "quote_max_age_hours",
        ),
    )
    _write_success({"ok": True, **payload})
    return 0


def cmd_coverage_manager_screen_quote_amend(ns: argparse.Namespace) -> int:
    effective_at = _timestamp(ns.at)
    if ns.quotes:
        quotes = _load_json_array(ns.quotes, "quote snapshot")
    elif ns.eastmoney_previous_close_date:
        try:
            quote_date = dt.date.fromisoformat(ns.eastmoney_previous_close_date)
        except ValueError as exc:
            raise ManagerScreenSnapshotError(
                "--eastmoney-previous-close-date must be YYYY-MM-DD"
            ) from exc
        quotes = fetch_eastmoney_previous_close_quotes(
            root=ns.root,
            run_id=ns.run_id,
            quote_date=quote_date,
            fetched_at=effective_at,
            endpoint=ns.quote_endpoint,
            chunk_size=ns.quote_chunk_size,
        )
    else:
        try:
            quote_date = dt.date.fromisoformat(ns.tencent_previous_close_date)
        except ValueError as exc:
            raise ManagerScreenSnapshotError(
                "--tencent-previous-close-date must be YYYY-MM-DD"
            ) from exc
        quotes = fetch_tencent_previous_close_quotes(
            root=ns.root,
            run_id=ns.run_id,
            quote_date=quote_date,
            fetched_at=effective_at,
            endpoint=ns.tencent_quote_endpoint,
            chunk_size=ns.quote_chunk_size,
        )
    payload = prepare_manager_screen_quote_amendment(
        root=ns.root,
        run_id=ns.run_id,
        amendment_id=ns.amendment_id,
        effective_at=effective_at,
        quote_snapshot=quotes,
        quote_max_age=_positive_hours(
            ns.quote_max_age_hours,
            "quote_max_age_hours",
        ),
        output_path=ns.output,
    )
    _write_success({"ok": True, **payload})
    return 0


def cmd_coverage_manager_screen_freeze(ns: argparse.Namespace) -> int:
    payload = freeze_manager_screen_batch(
        root=ns.root,
        run_id=ns.run_id,
        batch_id=ns.batch_id,
        frozen_at=_timestamp(ns.at),
        batch_size=ns.batch_size,
        policy_path=ns.policy,
    )
    _write_success({"ok": True, **payload})
    return 0


def cmd_coverage_manager_screen_record(ns: argparse.Namespace) -> int:
    submission = json.loads(Path(ns.input).read_text(encoding="utf-8"))
    payload = record_manager_screen_decisions(
        root=ns.root,
        run_id=ns.run_id,
        batch_id=ns.batch_id,
        submission=submission,
        recorded_at=_timestamp(ns.at),
    )
    _write_success({"ok": True, **payload})
    return 0


def cmd_coverage_manager_screen_status(ns: argparse.Namespace) -> int:
    payload = manager_screen_status(
        root=ns.root,
        run_id=ns.run_id,
        batch_id=ns.batch_id,
    )
    _write_success(payload)
    return 0


def cmd_coverage_manager_screen_control_record(ns: argparse.Namespace) -> int:
    payload = record_manager_screen_control(
        root=ns.root,
        run_id=ns.run_id,
        event_id=ns.event_id,
        state=ns.state,
        manager={
            "agent": ns.manager_agent,
            "model": ns.manager_model,
            "tools": ns.manager_tool,
        },
        reason=ns.reason,
        recorded_at=_timestamp(ns.at),
        company_limit=ns.company_limit,
    )
    _write_success({"ok": True, **payload})
    return 0


def cmd_coverage_manager_screen_control_status(ns: argparse.Namespace) -> int:
    _write_success(
        {
            "ok": True,
            **manager_screen_control_status(root=ns.root, run_id=ns.run_id),
        }
    )
    return 0


def cmd_coverage_manager_screen_allocation_v3_freeze(
    ns: argparse.Namespace,
) -> int:
    payload = freeze_manager_screen_allocation_v3_contract(
        root=ns.root,
        run_id=ns.run_id,
        manager={
            "agent": ns.manager_agent,
            "model": ns.manager_model,
            "tools": ns.manager_tool,
        },
        reason=ns.reason,
        frozen_at=_timestamp(ns.at),
        prior_policy_path=ns.prior_policy,
        future_policy_path=ns.future_policy,
    )
    _write_success({"ok": True, **payload})
    return 0


def cmd_coverage_manager_screen_allocation_v3_status(
    ns: argparse.Namespace,
) -> int:
    payload = manager_screen_allocation_v3_activation_drift_status(
        root=ns.root,
        run_id=ns.run_id,
    )
    _write_success({"ok": True, **payload})
    return 0


def cmd_coverage_manager_screen_allocation_v3_suspend(
    ns: argparse.Namespace,
) -> int:
    payload = suspend_manager_screen_allocation_v3_revocable_commitments(
        root=ns.root,
        run_id=ns.run_id,
        manager={
            "agent": ns.manager_agent,
            "model": ns.manager_model,
            "tools": ns.manager_tool,
        },
        reason=ns.reason,
        suspended_at=_timestamp(ns.at),
    )
    _write_success({"ok": True, **payload})
    return 0


def cmd_coverage_manager_screen_allocation_v3_suspension_status(
    ns: argparse.Namespace,
) -> int:
    payload = verify_manager_screen_allocation_v3_suspension(
        root=ns.root,
        run_id=ns.run_id,
    )
    _write_success({"ok": True, **payload})
    return 0


def cmd_coverage_manager_screen_quote_impact_prepare(
    ns: argparse.Namespace,
) -> int:
    payload = prepare_manager_screen_quote_impact(
        root=ns.root,
        run_id=ns.run_id,
        batch_id=ns.batch_id,
        review_id=ns.review_id,
        quote_amendment_path=ns.quote_amendment,
        prepared_at=_timestamp(ns.at),
        policy_path=ns.policy,
    )
    _write_success({"ok": True, **payload})
    return 0


def cmd_coverage_manager_screen_quote_impact_record(
    ns: argparse.Namespace,
) -> int:
    payload = record_manager_screen_quote_impact(
        root=ns.root,
        run_id=ns.run_id,
        batch_id=ns.batch_id,
        review_id=ns.review_id,
        submission=_load_json_object(ns.input, "manager-screen quote impact"),
        recorded_at=_timestamp(ns.at),
    )
    _write_success({"ok": True, **payload})
    return 0


def cmd_coverage_manager_screen_quote_impact_status(
    ns: argparse.Namespace,
) -> int:
    _write_success(
        manager_screen_quote_impact_status(
            root=ns.root,
            run_id=ns.run_id,
            batch_id=ns.batch_id,
            review_id=ns.review_id,
        )
    )
    return 0


def cmd_coverage_manager_screen_supersede(ns: argparse.Namespace) -> int:
    submission = _load_json_object(ns.input, "manager-screen supersession")
    payload = supersede_manager_screen_batch(
        root=ns.root,
        run_id=ns.run_id,
        batch_id=ns.batch_id,
        manager=submission.get("manager"),
        reason=submission.get("reason"),
        superseded_at=_timestamp(ns.at),
    )
    _write_success({"ok": True, **payload})
    return 0


def cmd_coverage_manager_screen_calibration_prepare(
    ns: argparse.Namespace,
) -> int:
    payload = prepare_manager_screen_calibration(
        root=ns.root,
        run_id=ns.run_id,
        batch_id=ns.batch_id,
        calibration_id=ns.calibration_id,
        prepared_at=_timestamp(ns.at),
        policy_path=ns.policy,
    )
    _write_success({"ok": True, **payload})
    return 0


def cmd_coverage_manager_screen_calibration_record(
    ns: argparse.Namespace,
) -> int:
    payload = record_manager_screen_calibration(
        root=ns.root,
        run_id=ns.run_id,
        batch_id=ns.batch_id,
        calibration_id=ns.calibration_id,
        submission=_load_json_object(ns.input, "manager-screen calibration"),
        recorded_at=_timestamp(ns.at),
    )
    _write_success({"ok": True, **payload})
    return 0


def cmd_coverage_manager_screen_calibration_status(
    ns: argparse.Namespace,
) -> int:
    payload = manager_screen_calibration_status(
        root=ns.root,
        run_id=ns.run_id,
        batch_id=ns.batch_id,
    )
    _write_success(payload)
    return 0


def cmd_coverage_manager_screen_transition_freeze(
    ns: argparse.Namespace,
) -> int:
    payload = freeze_legacy_transition(
        root=ns.root,
        run_id=ns.run_id,
        classification=_load_json_object(ns.input, "legacy transition classification"),
        frozen_at=_timestamp(ns.at),
    )
    _write_success({"ok": True, **payload})
    return 0


def cmd_coverage_manager_screen_transition_record(
    ns: argparse.Namespace,
) -> int:
    payload = record_legacy_transition(
        root=ns.root,
        run_id=ns.run_id,
        submission=_load_json_object(ns.input, "legacy transition submission"),
        recorded_at=_timestamp(ns.at),
    )
    _write_success({"ok": True, **payload})
    return 0


def cmd_coverage_manager_screen_transition_status(
    ns: argparse.Namespace,
) -> int:
    _write_success(
        legacy_transition_status(
            root=ns.root,
            run_id=ns.run_id,
        )
    )
    return 0


def cmd_coverage_trigger_observe(ns: argparse.Namespace) -> int:
    observation = load_json(ns.input)
    if not isinstance(observation, dict):
        raise TriggerHitError("trigger observation input must be an object")
    _write_success(
        {
            "ok": True,
            **observe_fact_hit(
                root=ns.root,
                observation=observation,
                recorded_at=_timestamp(ns.at),
            ),
        }
    )
    return 0


def cmd_coverage_trigger_status(ns: argparse.Namespace) -> int:
    _write_success(verify_trigger_hit_ledger(root=ns.root))
    return 0


def cmd_coverage_trigger_rebuild(ns: argparse.Namespace) -> int:
    _write_success({"ok": True, **rebuild_trigger_hit_state(root=ns.root)})
    return 0


def cmd_coverage_trigger_checkpoint(ns: argparse.Namespace) -> int:
    manifest = ns.scope_manifest or str(Path(ns.root) / "scopes" / ns.run_id / "manifest.json")
    _write_success(
        {
            "ok": True,
            **create_trigger_hit_checkpoint(
                root=ns.root,
                run_id=ns.run_id,
                scope_manifest_path=manifest,
                checkpointed_at=_timestamp(ns.at),
            ),
        }
    )
    return 0


def cmd_coverage_lane_freeze(ns: argparse.Namespace) -> int:
    _write_success(
        {
            "ok": True,
            **freeze_lane_arbitration(
                root=ns.root,
                run_id=ns.run_id,
                frozen_at=_timestamp(ns.at),
                baseline_minimum_slots=ns.baseline_minimum_slots,
                apply_coverage=not ns.no_apply,
            ),
        }
    )
    return 0


def cmd_coverage_lane_status(ns: argparse.Namespace) -> int:
    _write_success(verify_lane_arbitration(root=ns.root, run_id=ns.run_id))
    return 0


def cmd_coverage_quality_scope_prepare(ns: argparse.Namespace) -> int:
    _write_success(
        {
            "ok": True,
            **prepare_scope_identity_quality_audit(
                root=ns.root,
                run_id=ns.run_id,
                policy_path=ns.policy,
                created_at=_timestamp(ns.at),
            ),
        }
    )
    return 0


def cmd_coverage_quality_scope_record(ns: argparse.Namespace) -> int:
    status = scope_quality_status(root=ns.root, run_id=ns.run_id)
    if status["status"] != "pending_reviews":
        _write_success({"ok": status["status"] == "passed", **status})
        return 0
    seal_scope_identity_audit_result(
        plan_path=status["canonical_paths"]["plan"],
        reviews=_load_review_rows(ns.reviews),
        completed_at=_timestamp(ns.at),
    )
    status = scope_quality_status(root=ns.root, run_id=ns.run_id)
    _write_success({"ok": status["status"] == "passed", **status})
    return 0


def cmd_coverage_quality_scope_status(ns: argparse.Namespace) -> int:
    status = scope_quality_status(root=ns.root, run_id=ns.run_id)
    _write_success({"ok": status["status"] == "passed", **status})
    return 0


def cmd_coverage_quality_triage_prepare(ns: argparse.Namespace) -> int:
    _write_success(
        {
            "ok": True,
            **prepare_cycle_quality_audit(
                root=ns.root,
                cycle_id=ns.cycle_id,
                policy_path=ns.policy,
                created_at=_timestamp(ns.at),
            ),
        }
    )
    return 0


def cmd_coverage_quality_triage_record(ns: argparse.Namespace) -> int:
    status = cycle_quality_status(root=ns.root, cycle_id=ns.cycle_id)
    if status["status"] != "pending_reviews":
        materialization = materialize_cycle_quality_reopens(root=ns.root, cycle_id=ns.cycle_id)
        _write_success(
            {
                "ok": status["status"] == "passed",
                **status,
                "reopen_materialization": materialization,
            }
        )
        return 0
    snapshot = load_quality_policy_snapshot(
        snapshot_path=status["canonical_paths"]["policy_snapshot"],
        expected_subject_kind="triage_false_negative",
        expected_subject_id=ns.cycle_id,
    )
    seal_cycle_quality_audit_result(
        plan_path=status["canonical_paths"]["plan"],
        reviews=_load_review_rows(ns.reviews),
        policy=snapshot["policy"],
        completed_at=_timestamp(ns.at),
    )
    status = cycle_quality_status(root=ns.root, cycle_id=ns.cycle_id)
    materialization = materialize_cycle_quality_reopens(root=ns.root, cycle_id=ns.cycle_id)
    _write_success(
        {
            "ok": status["status"] == "passed",
            **status,
            "reopen_materialization": materialization,
        }
    )
    return 0


def cmd_coverage_quality_triage_continue(ns: argparse.Namespace) -> int:
    status = prepare_cycle_quality_audit_continuation(
        root=ns.root,
        cycle_id=ns.cycle_id,
        created_at=_timestamp(ns.at),
    )
    _write_success({"ok": True, **status})
    return 0


def cmd_coverage_quality_triage_record_continuation(ns: argparse.Namespace) -> int:
    status = record_cycle_quality_audit_continuation(
        root=ns.root,
        cycle_id=ns.cycle_id,
        reviews=_load_review_rows(ns.reviews),
        completed_at=_timestamp(ns.at),
    )
    materialization = materialize_cycle_quality_reopens(root=ns.root, cycle_id=ns.cycle_id)
    _write_success(
        {
            "ok": status["status"] == "passed" and materialization["reopen_count"] == 0,
            **status,
            "reopen_materialization": materialization,
        }
    )
    return 0


def cmd_coverage_quality_triage_correction_prepare(ns: argparse.Namespace) -> int:
    result = prepare_cycle_quality_correction(
        root=ns.root,
        cycle_id=ns.cycle_id,
        correction_cycle_id=ns.correction_cycle_id,
        created_at=_timestamp(ns.at),
    )
    _write_success({"ok": True, **result})
    return 0


def cmd_coverage_quality_triage_correction_resolve(ns: argparse.Namespace) -> int:
    result = record_cycle_quality_correction_resolution(
        root=ns.root,
        cycle_id=ns.cycle_id,
        correction_cycle_id=ns.correction_cycle_id,
        completed_at=_timestamp(ns.at),
    )
    _write_success({"ok": result["status"] == "passed", **result})
    return 0


def cmd_coverage_quality_triage_status(ns: argparse.Namespace) -> int:
    status = cycle_quality_gate_status(root=ns.root, cycle_id=ns.cycle_id)
    _write_success({"ok": status["status"] == "passed", **status})
    return 0


def _load_review_rows(path: str | Path) -> list[dict[str, object]]:
    payload = load_json(path)
    if isinstance(payload, dict):
        payload = payload.get("reviews")
    if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
        raise QualityWorkflowError("quality reviews must be a list or {reviews: [...]} object")
    return payload


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


def cmd_coverage_triage_freeze(ns: argparse.Namespace) -> int:
    symbols = read_symbol_file(ns.symbols_file) if ns.symbols_file else None
    payload = freeze_rapid_triage_cohort(
        root=ns.root,
        cycle_id=ns.cycle_id,
        frozen_at=_timestamp(ns.at),
        queue_status=ns.queue_status,
        limit=ns.limit,
        after_symbol=ns.after_symbol,
        symbols=symbols,
        scope_run_id=ns.scope_run_id,
        quality_policy_snapshot_path=ns.quality_policy_snapshot,
        scope_identity_audit_result_path=ns.scope_identity_result,
    )
    _write_success({"ok": True, **payload})
    return 0


def cmd_coverage_triage_claim(ns: argparse.Namespace) -> int:
    payload = claim_rapid_triage_task(
        root=ns.root,
        agent=ns.agent,
        claimed_at=_timestamp(ns.at),
        symbol=ns.symbol,
        lens=ns.lens,
        cycle_id=ns.cycle_id,
    )
    _write_success({"ok": True, **payload})
    return 0


def cmd_coverage_triage_release(ns: argparse.Namespace) -> int:
    payload = release_rapid_triage_task(
        root=ns.root,
        agent=ns.agent,
        symbol=ns.symbol,
        failure_reason=ns.failure_reason,
        released_at=_timestamp(ns.at),
    )
    _write_success({"ok": True, **payload})
    return 0


def cmd_coverage_triage_record(ns: argparse.Namespace) -> int:
    package = json.loads(Path(ns.input).read_text(encoding="utf-8"))
    payload = record_rapid_triage_package(
        package,
        root=ns.root,
        recorded_at=_timestamp(ns.at),
    )
    _write_success({"ok": True, **payload})
    return 0


def cmd_coverage_triage_status(ns: argparse.Namespace) -> int:
    payload = rapid_triage_cycle_status(root=ns.root, cycle_id=ns.cycle_id)
    _write_success({"ok": payload["invalid_artifact_count"] == 0, **payload})
    return 0


def cmd_coverage_triage_compare(ns: argparse.Namespace) -> int:
    payload = build_rapid_triage_comparison_packet(
        root=ns.root,
        cycle_id=ns.cycle_id,
        created_at=_timestamp(ns.at),
    )
    _write_success({"ok": True, **payload})
    return 0


def cmd_coverage_triage_finalize(ns: argparse.Namespace) -> int:
    policy = load_policy(ns.policy)
    decisions = json.loads(Path(ns.decisions).read_text(encoding="utf-8"))
    payload = finalize_rapid_triage_cycle(
        root=ns.root,
        cycle_id=ns.cycle_id,
        policy=policy.payload,
        decisions=decisions,
        finalized_at=_timestamp(ns.at),
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
        run_id=ns.run_id,
        stage=ns.stage,
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


def cmd_coverage_profile_followup_approve(ns: argparse.Namespace) -> int:
    policy = load_policy(ns.policy)
    payload = approve_targeted_followup(
        root=ns.root,
        symbol=ns.symbol,
        manager=ns.manager,
        reason=ns.reason,
        policy=policy.payload,
        approved_at=_timestamp(ns.at),
        policy_path=ns.policy,
    )
    _write_success({"ok": True, **payload})
    return 0


def cmd_coverage_profile_followup_decline(ns: argparse.Namespace) -> int:
    payload = decline_targeted_followup(
        root=ns.root,
        symbol=ns.symbol,
        manager=ns.manager,
        outcome=ns.outcome,
        reason=ns.reason,
        restart_triggers=_load_json_array(
            ns.triggers,
            "targeted-followup restart triggers",
        ),
        declined_at=_timestamp(ns.at),
    )
    _write_success({"ok": True, **payload})
    return 0


def cmd_coverage_profile_compare(ns: argparse.Namespace) -> int:
    payload = build_profile_comparison_packet(
        root=ns.root,
        cycle_id=ns.cycle_id,
        stage=ns.stage,
        created_at=_timestamp(ns.at),
    )
    _write_success({"ok": True, **payload})
    return 0


def cmd_coverage_profile_select(ns: argparse.Namespace) -> int:
    policy = load_policy(ns.policy)
    decisions = json.loads(Path(ns.decisions).read_text(encoding="utf-8"))
    payload = finalize_profile_stage_with_agent_decisions(
        root=ns.root,
        cycle_id=ns.cycle_id,
        stage=ns.stage,
        policy=policy.payload,
        decisions=decisions,
        finalized_at=_timestamp(ns.at),
        policy_path=ns.policy,
    )
    _write_success({"ok": True, **payload})
    return 0


def cmd_coverage_profile_finalize(ns: argparse.Namespace) -> int:
    policy = load_policy(ns.policy)
    payload = finalize_profile_stage(
        root=ns.root,
        cycle_id=ns.cycle_id,
        stage=ns.stage,
        policy=policy.payload,
        finalized_at=_timestamp(ns.at),
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
        return _write_failure({"ok": False, "error_code": error_code, "error": str(exc)})


def _write_failure(payload: dict[str, object], stream: TextIO | None = None) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=stream or sys.stderr)
    return 1


def _write_success(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _error_code(exc: Exception) -> str | None:
    for error_type, code in (
        (AssetValidationError, "asset_validation_failed"),
        (AssetGcError, "asset_gc_error"),
        (PriceAlertError, "price_alert_error"),
        (CoverageValidationError, "coverage_validation_failed"),
        (ScopeWorkflowError, "scope_workflow_error"),
        (TriggerHitError, "trigger_hit_error"),
        (LaneArbitrationError, "lane_arbitration_error"),
        (LegacyTransitionError, "legacy_transition_error"),
        (ManagerScreenControlError, "manager_screen_control_error"),
        (ManagerScreenAllocationV3Error, "manager_screen_allocation_v3_error"),
        (
            ManagerScreenAllocationV3SuspensionError,
            "manager_screen_allocation_v3_suspension_error",
        ),
        (ManagerScreenGovernanceError, "manager_screen_governance_error"),
        (ManagerScreenQuoteImpactError, "manager_screen_quote_impact_error"),
        (ManagerScreeningError, "manager_screening_error"),
        (ManagerScreenSnapshotError, "manager_screen_snapshot_error"),
        (QualityAuditError, "quality_audit_error"),
        (QualityWorkflowError, "quality_workflow_error"),
        (ReviewStoreError, "review_state_error"),
        (ReviewWorkflowError, "review_workflow_error"),
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


def _load_json_array(path: str, label: str) -> list[dict[str, object]]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManagerScreenSnapshotError(f"{label} is not valid JSON: {path}") from exc
    if not isinstance(payload, list):
        raise ManagerScreenSnapshotError(f"{label} must be a JSON array")
    return payload


def _load_json_object(path: str, label: str) -> dict[str, object]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"{label} is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{label} must be a JSON object")
    return payload


def _positive_hours(value: float, field: str) -> dt.timedelta:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or value <= 0
    ):
        raise ManagerScreenSnapshotError(f"{field} must be positive")
    return dt.timedelta(hours=float(value))


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
