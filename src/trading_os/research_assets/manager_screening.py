from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .coverage_store import (
    RESEARCH_QUEUE_FILE,
    SCREENING_FILE,
    read_jsonl,
    serialized_coverage_write,
    write_jsonl,
)
from .manager_screen_control import (
    ManagerScreenControlError,
    manager_screen_control_status,
    require_manager_screen_first_record_allowed,
    require_manager_screen_freeze_allowed,
)
from .manager_screen_decision_quality import (
    ManagerScreenDecisionQualityError,
    build_decision_support,
    validate_canonical_reason,
    validate_decision_support,
    validate_risk_acknowledgements,
)
from .manager_screen_governance import (
    ManagerScreenGovernanceError,
    load_manager_screen_supersession,
)
from .models import PolicyKind, load_policy
from .sealing import SealingError, canonical_json_bytes, seal_json, verify_sealed

ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SYMBOL_RE = re.compile(r"^CN:[0-9]{6}$")
EVIDENCE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._/-]{0,199}$")

ROUTES = {"pass", "watch", "send_to_analyst"}
CONFIDENCES = {"low", "medium", "high"}
TRIGGER_TYPES = {"filing", "price", "date", "ttl", "event", "thesis"}
EXTERNAL_SOURCE_TYPES = {"filing", "exchange", "market_data", "company", "other"}
PROTECTED_TASK_TYPES = {
    "quick_profile",
    "targeted_followup",
    "scoped_research",
    "deep_research",
}

LEGACY_BATCH_KEYS = {
    "schema_version",
    "run_id",
    "batch_id",
    "frozen_at",
    "information_cutoff",
    "scope",
    "policy",
    "selection_basis",
    "requested_batch_size",
    "member_count",
    "members",
    "portfolio_action",
}
BATCH_KEYS = LEGACY_BATCH_KEYS | {"quote_amendment"}
FREEZE_JOURNAL_KEYS = {
    "schema_version",
    "run_id",
    "batch_id",
    "created_at",
    "batch",
    "batch_sha256",
    "packet",
    "packet_sha256",
    "portfolio_action",
}
QUOTE_AMENDMENT_REF_KEYS = {
    "amendment_id",
    "path",
    "sha256",
    "effective_at",
    "base_snapshot_sha256",
}
SCOPE_REF_KEYS = {
    "manifest_path",
    "manifest_sha256",
    "baseline_intake_path",
    "baseline_intake_sha256",
}
LEGACY_POLICY_REF_KEYS = {
    "policy_id",
    "version",
    "path",
    "file_sha256",
    "payload_sha256",
    "default_batch_size",
    "minimum_batch_size",
    "maximum_batch_size",
    "fact_snapshot_required",
    "minimum_annual_periods",
    "quick_profile_effort_budget_hours",
    "quick_profile_stop_conditions",
    "pass_and_watch_require_revisit_trigger",
    "recursive_correction",
    "one_line_reason_max_chars",
    "decisive_question_max_chars",
}
CALIBRATION_POLICY_REF_KEYS = {
    "programmatic_validation_rate",
    "calibration_sample_rate",
    "calibration_minimum_per_batch",
    "calibration_material_error_types",
    "route_disagreement_is_material_error",
}
PRE_CAPACITY_POLICY_REF_KEYS = LEGACY_POLICY_REF_KEYS | CALIBRATION_POLICY_REF_KEYS
ANALYST_CAPACITY_POLICY_REF_KEYS = {"send_to_analyst_capacity_per_run"}
POLICY_REF_KEYS = PRE_CAPACITY_POLICY_REF_KEYS | ANALYST_CAPACITY_POLICY_REF_KEYS
DECISION_V2_POLICY_REF_KEYS = {
    "decision_contract_version",
    "mandatory_risk_acknowledgement",
    "canonical_fact_line_required",
    "high_liability_to_assets_pct",
}
POLICY_V2_REF_KEYS = POLICY_REF_KEYS | DECISION_V2_POLICY_REF_KEYS
RUN_CONTROL_POLICY_REF_KEYS = {"run_control_required"}
PRE_CAPACITY_CONTROL_POLICY_REF_KEYS = (
    PRE_CAPACITY_POLICY_REF_KEYS | RUN_CONTROL_POLICY_REF_KEYS
)
CONTROL_POLICY_REF_KEYS = POLICY_REF_KEYS | RUN_CONTROL_POLICY_REF_KEYS
POLICY_V2_CONTROL_REF_KEYS = POLICY_V2_REF_KEYS | RUN_CONTROL_POLICY_REF_KEYS
CALIBRATION_ERROR_TYPES = {
    "security_identity_error",
    "verifiable_factual_error",
    "material_risk_omission",
    "decision_contract_violation",
}
CALIBRATION_PACKET_KEYS = {
    "schema_version",
    "run_id",
    "batch_id",
    "calibration_id",
    "prepared_at",
    "batch_path",
    "batch_sha256",
    "manager_result_path",
    "manager_result_sha256",
    "policy",
    "plan",
    "reviewer_contract",
    "samples",
    "non_blocking",
    "portfolio_action",
}
CALIBRATION_SAMPLE_KEYS = {
    "symbol",
    "decision",
    "dossier",
    "evidence_ids",
}
CALIBRATION_RESULT_KEYS = {
    "schema_version",
    "run_id",
    "batch_id",
    "calibration_id",
    "recorded_at",
    "packet_path",
    "packet_sha256",
    "batch_sha256",
    "manager_result_sha256",
    "policy_payload_sha256",
    "plan",
    "reviewer",
    "additional_evidence",
    "reviews",
    "summary",
    "non_blocking",
    "recursive_correction",
    "portfolio_action",
}
CALIBRATION_SUBMISSION_KEYS = {
    "schema_version",
    "reviewer",
    "additional_evidence",
    "reviews",
}
CALIBRATION_REVIEW_KEYS = {
    "symbol",
    "material_errors",
    "route_disagreement",
    "adjudication",
}
CALIBRATION_ERROR_KEYS = {"type", "finding", "evidence_ids"}
ROUTE_DISAGREEMENT_KEYS = {"present", "finding", "evidence_ids"}
CALIBRATION_ADJUDICATION_KEYS = {
    "performed",
    "outcome",
    "finding",
    "evidence_ids",
}
ADJUDICATION_OUTCOMES = {
    "not_needed",
    "manager_upheld",
    "material_error_confirmed",
}
CALIBRATION_ADJUDICATION_TRIGGER = "material_error_only"
MEMBER_KEYS = {
    "batch_ordinal",
    "scope_ordinal",
    "symbol",
    "name",
    "prior_task_type",
    "prior_status",
}
PACKET_KEYS = {
    "schema_version",
    "run_id",
    "batch_id",
    "created_at",
    "information_cutoff",
    "batch_path",
    "batch_sha256",
    "instructions",
    "dossiers",
    "portfolio_action",
}
DOSSIER_KEYS = {
    "batch_ordinal",
    "scope_ordinal",
    "symbol",
    "name",
    "market_snapshot",
    "prior_screening",
    "prior_queue",
    "timeline",
    "evidence_catalog",
}
RESULT_KEYS = {
    "schema_version",
    "run_id",
    "batch_id",
    "recorded_at",
    "information_cutoff",
    "batch_path",
    "batch_sha256",
    "packet_path",
    "packet_sha256",
    "manager",
    "additional_evidence",
    "decisions",
    "quality_state",
    "portfolio_action",
}
SUBMISSION_KEYS = {"schema_version", "manager", "additional_evidence", "decisions"}
MANAGER_KEYS = {"agent", "model", "tools"}
EXTERNAL_EVIDENCE_KEYS = {
    "evidence_id",
    "symbol",
    "source_type",
    "title",
    "url",
    "accessed_at",
}
DECISION_KEYS = {
    "symbol",
    "route",
    "one_line_reason",
    "decisive_question",
    "revisit_triggers",
    "confidence",
    "evidence_ids",
}
DECISION_V2_KEYS = DECISION_KEYS | {"risk_acknowledgements"}
TRIGGER_KEYS = {"type", "condition", "reason"}

MARKET_FIELDS = (
    "as_of",
    "exchange",
    "listing_status",
    "security_type",
    "industry",
    "price",
    "currency",
    "market_cap_cny",
    "float_market_cap_cny",
    "pe_ttm",
    "pb",
    "roe",
    "revenue_growth_pct",
    "profit_growth_pct",
    "debt_to_asset_pct",
    "dividend_yield_pct",
    "turnover_cny",
    "turnover_rate_pct",
    "manager_screen_facts",
    "source",
    "fetched_at",
)
SCREEN_FIELDS = ("decision", "reason", "evidence", "next_action")
QUEUE_FIELDS = (
    "task_type",
    "status",
    "reason",
    "result_path",
    "triage_disposition",
    "manager_screen_route",
    "manager_screen_result_path",
)


class ManagerScreeningError(ValueError):
    """Raised when a manager-screen batch is malformed or cannot advance."""


@serialized_coverage_write
def freeze_manager_screen_batch(
    *,
    root: str | Path,
    run_id: str,
    batch_id: str,
    frozen_at: dt.datetime,
    batch_size: int | None = None,
    policy_path: str | Path = "policies/manager-screening.json",
) -> dict[str, Any]:
    """Freeze one administrative batch and its compact manager dossier."""

    base = Path(root)
    repository_root = base.parent.parent
    run = _identifier(run_id, "run_id")
    batch_name = _identifier(batch_id, "batch_id")
    frozen = _aware(frozen_at, "frozen_at")
    policy = _load_policy_contract(
        policy_path=policy_path,
        repository_root=repository_root,
    )
    requested_size = policy["default_batch_size"] if batch_size is None else batch_size
    if isinstance(requested_size, bool) or not isinstance(requested_size, int):
        raise ManagerScreeningError("batch_size must be an integer")
    if not policy["minimum_batch_size"] <= requested_size <= policy["maximum_batch_size"]:
        raise ManagerScreeningError(
            "batch_size must be between "
            f"{policy['minimum_batch_size']} and {policy['maximum_batch_size']}"
        )

    manifest_path, manifest, manifest_seal, intake_path, intake, intake_seal = (
        _load_scope_artifacts(base=base, run_id=run)
    )
    information_cutoff = _parse_datetime(
        manifest.get("scope_cutoff"),
        "scope manifest information cutoff",
    )
    if frozen < information_cutoff:
        raise ManagerScreeningError("frozen_at cannot be before the scope cutoff")

    run_dir = base / "manager-screen" / run
    batch_dir = run_dir / batch_name
    batch_path = batch_dir / "batch.json"
    packet_path = batch_dir / "packet.json"
    journal_path = batch_dir / "freeze-journal.json"
    artifact_exists = any(
        path.exists()
        for path in (
            batch_path,
            batch_path.with_name(f"{batch_path.name}.seal.json"),
            packet_path,
            packet_path.with_name(f"{packet_path.name}.seal.json"),
        )
    )
    artifacts_complete = all(
        path.is_file()
        for path in (
            batch_path,
            batch_path.with_name(f"{batch_path.name}.seal.json"),
            packet_path,
            packet_path.with_name(f"{packet_path.name}.seal.json"),
        )
    )
    journal_exists = journal_path.exists() or journal_path.with_name(
        f"{journal_path.name}.seal.json"
    ).exists()
    if artifact_exists or journal_exists:
        if artifacts_complete:
            verified = _verify_batch_dir(batch_dir, repository_root=repository_root)
            _discard_freeze_journal(batch_dir)
        elif journal_exists:
            verified = _repair_manager_screen_freeze(
                batch_dir,
                repository_root=repository_root,
            )
        else:
            verified = _verify_batch_dir(batch_dir, repository_root=repository_root)
        if verified["supersession"] is not None:
            raise ManagerScreeningError(
                f"superseded manager-screen batch id cannot be reused: {batch_name}"
            )
        _require_scope_binding(
            batch=verified["batch"],
            manifest_path=manifest_path,
            manifest_sha256=manifest_seal.sha256,
            intake_path=intake_path,
            intake_sha256=intake_seal.sha256,
            repository_root=repository_root,
        )
        existing = verified["batch"]
        if (
            existing["requested_batch_size"] != requested_size
            or existing["policy"]["file_sha256"] != policy["file_sha256"]
            or existing["scope"]["manifest_sha256"] != manifest_seal.sha256
            or existing["scope"]["baseline_intake_sha256"] != intake_seal.sha256
        ):
            raise ManagerScreeningError(
                f"sealed manager-screen batch conflicts with freeze request: {batch_name}"
            )
        return _freeze_summary(verified, repository_root=repository_root)

    _enforce_run_capacity_policy_monotonic(
        run_dir=run_dir,
        requested_policy=policy,
        repository_root=repository_root,
    )

    company_snapshot_path = _require_frozen_universe_snapshot(
        base=base,
        manifest=manifest,
    )
    quote_amendment, quote_amendment_payload = _latest_quote_amendment(
        base=base,
        run_id=run,
        base_snapshot_path=company_snapshot_path,
        frozen_at=frozen,
        repository_root=repository_root,
    )

    already_batched: set[str] = set()
    if run_dir.is_dir():
        for other_dir in _manager_batch_dirs(run_dir):
            if other_dir.name == batch_name:
                continue
            verified = _verify_batch_reservation(
                other_dir,
                repository_root=repository_root,
            )
            if verified["supersession"] is not None:
                continue
            for member in verified["batch"]["members"]:
                symbol = member["symbol"]
                if symbol in already_batched:
                    raise ManagerScreeningError(
                        f"symbol appears in multiple manager-screen batches: {symbol}"
                    )
                already_batched.add(symbol)

    company_rows = read_jsonl(company_snapshot_path)
    if quote_amendment_payload is not None:
        company_rows = _apply_quote_amendment(
            company_rows,
            amendment=quote_amendment_payload,
        )
    companies = _unique_by_symbol(company_rows, "companies")
    screening = _unique_by_symbol(read_jsonl(base / SCREENING_FILE), "screening")
    queue = _unique_by_symbol(read_jsonl(base / RESEARCH_QUEUE_FILE), "research queue")
    candidates, _, _ = _candidate_members(
        base=base,
        manifest=manifest,
        manifest_sha256=manifest_seal.sha256,
        intake=intake,
        intake_sha256=intake_seal.sha256,
        queue_by_symbol=queue,
        already_batched=already_batched,
        scope_cutoff=information_cutoff,
    )
    selected = candidates[:requested_size]
    if not selected:
        raise ManagerScreeningError(
            f"no unbatched manager-screen candidates remain for scope {run}"
        )
    try:
        require_manager_screen_freeze_allowed(
            root=base,
            run_id=run,
            requested_company_count=len(selected),
            control_required=policy.get("run_control_required") is True,
        )
    except ManagerScreenControlError as exc:
        raise ManagerScreeningError(str(exc)) from exc

    members = []
    for member in selected:
        symbol = _symbol(member.get("symbol"))
        members.append(
            {
                "batch_ordinal": len(members) + 1,
                "scope_ordinal": _positive_int(member.get("ordinal"), "scope ordinal"),
                "symbol": symbol,
                "name": _text(member.get("name"), f"{symbol}.name"),
                "prior_task_type": (queue.get(symbol) or {}).get("task_type"),
                "prior_status": (queue.get(symbol) or {}).get("status"),
            }
        )

    batch = {
        "schema_version": 1,
        "run_id": run,
        "batch_id": batch_name,
        "frozen_at": frozen.isoformat(),
        "information_cutoff": information_cutoff.isoformat(),
        "scope": {
            "manifest_path": _relative(manifest_path, repository_root),
            "manifest_sha256": manifest_seal.sha256,
            "baseline_intake_path": _relative(intake_path, repository_root),
            "baseline_intake_sha256": intake_seal.sha256,
        },
        "quote_amendment": quote_amendment,
        "policy": policy,
        "selection_basis": (
            "sealed baseline-intake ordinal after excluding already frozen, completed, "
            "identity-blocked, running, or deeper-stage companies; no valuation, factor, "
            "market-cap, liquidity, profitability, industry, score, or completion rank was used"
        ),
        "requested_batch_size": requested_size,
        "member_count": len(members),
        "members": members,
        "portfolio_action": None,
    }
    _validate_batch(batch)
    batch_sha256 = hashlib.sha256(canonical_json_bytes(batch)).hexdigest()

    dossiers = [
        _build_dossier(
            member=member,
            company=companies.get(member["symbol"]),
            screening=screening.get(member["symbol"]),
            queue=queue.get(member["symbol"]),
            company_snapshot_path=company_snapshot_path,
            require_fact_snapshot=policy["fact_snapshot_required"],
            minimum_annual_periods=policy["minimum_annual_periods"],
            frozen_at=frozen,
            quote_amendment=quote_amendment,
            repository_root=repository_root,
            decision_contract_version=policy.get("decision_contract_version", 1),
            high_liability_to_assets_pct=policy.get(
                "high_liability_to_assets_pct"
            ),
        )
        for member in members
    ]
    packet = {
        "schema_version": 1,
        "run_id": run,
        "batch_id": batch_name,
        "created_at": frozen.isoformat(),
        "information_cutoff": information_cutoff.isoformat(),
        "batch_path": _relative(batch_path, repository_root),
        "batch_sha256": batch_sha256,
        "instructions": {
            "role": "同一名投资经理 Agent 在一份 packet 内统一浏览整批公司。",
            "routes": {
                "pass": "当前不值得继续购买研究时间；记录可执行重启条件。",
                "watch": "业务可能可投，但需等待价格、财报、事件或关键证据。",
                "send_to_analyst": "下一小时深入研究很可能改变判断；只把少数候选交给研究员。",
            },
            "rubric": [
                "业务是否看得懂，普通股股东如何获得现金。",
                "生存、治理、资本结构或会计质量是否存在明显阻断。",
                "正常化盈利和现金转化是否有可验证路径。",
                "当前价格已经隐含什么，赔率是否值得继续花研究时间。",
                "下一小时最决定性的研究问题是什么。",
            ],
            "forbidden": [
                "不得输出 rank、score、priority、portfolio_action、buy_now 或仓位。",
                "不得因市值小、流动性低、亏损或行业冷门而静默跳过。",
                "不得为初筛启动一家公司一个 Agent；整批由同一投资经理判断。",
            ],
            "external_evidence": (
                "若 packet 不足，可查少量一手来源，并在提交的 additional_evidence "
                "中一次记录 provenance。"
            ),
        },
        "dossiers": dossiers,
        "portfolio_action": None,
    }
    if policy.get("decision_contract_version") == 2:
        packet["instructions"]["decision_contract"] = {
            "version": 2,
            "canonical_fact_line": (
                "one_line_reason 必须逐字使用 dossier decision_support 中的 "
                "canonical_fact_line.text 作为前缀；后缀只写定性判断，不得手抄数字"
            ),
            "mandatory_risk_flags": (
                "每个 mandatory_risk_flag 都必须在 risk_acknowledgements 中明确判断 "
                "material 或 not_material；风险候选不自动决定 route"
            ),
            "material_acknowledgement": (
                "assessment=material 的 reason 必须原样进入 one_line_reason "
                "定性后缀或 decisive_question"
            ),
        }
    _validate_packet(packet, batch=batch, batch_sha256=batch_sha256)
    journal = {
        "schema_version": 1,
        "run_id": run,
        "batch_id": batch_name,
        "created_at": frozen.isoformat(),
        "batch": batch,
        "batch_sha256": batch_sha256,
        "packet": packet,
        "packet_sha256": hashlib.sha256(canonical_json_bytes(packet)).hexdigest(),
        "portfolio_action": None,
    }
    _validate_freeze_journal(journal, batch_dir=batch_dir, repository_root=repository_root)
    seal_json(
        journal_path,
        journal,
        artifact_type="manager_screen_freeze_journal",
        sealed_at=frozen,
    )
    verified = _repair_manager_screen_freeze(
        batch_dir,
        repository_root=repository_root,
    )
    return _freeze_summary(verified, repository_root=repository_root)


@serialized_coverage_write
def record_manager_screen_decisions(
    *,
    root: str | Path,
    run_id: str,
    batch_id: str,
    submission: Mapping[str, Any],
    recorded_at: dt.datetime,
) -> dict[str, Any]:
    """Validate and seal one whole-batch manager decision, then materialize coverage."""

    base = Path(root)
    repository_root = base.parent.parent
    run = _identifier(run_id, "run_id")
    batch_name = _identifier(batch_id, "batch_id")
    recorded = _aware(recorded_at, "recorded_at")
    batch_dir = base / "manager-screen" / run / batch_name
    verified = _verify_batch_dir(
        batch_dir,
        repository_root=repository_root,
        require_result=False,
    )
    batch = verified["batch"]
    packet = verified["packet"]
    if verified["supersession"] is not None:
        raise ManagerScreeningError(
            f"superseded manager-screen batch cannot be recorded: {batch_name}"
        )
    manifest_path, _, manifest_seal, intake_path, _, intake_seal = (
        _load_scope_artifacts(base=base, run_id=run)
    )
    _require_scope_binding(
        batch=batch,
        manifest_path=manifest_path,
        manifest_sha256=manifest_seal.sha256,
        intake_path=intake_path,
        intake_sha256=intake_seal.sha256,
        repository_root=repository_root,
    )
    if batch["run_id"] != run or batch["batch_id"] != batch_name:
        raise ManagerScreeningError("manager-screen path does not match batch identity")
    if recorded < _parse_datetime(batch["frozen_at"], "batch frozen_at"):
        raise ManagerScreeningError("recorded_at cannot be before batch frozen_at")

    normalized = _normalize_submission(
        submission,
        batch=batch,
        packet=packet,
        recorded_at=recorded,
    )
    result_path = batch_dir / "result.json"
    if result_path.exists():
        complete = _verify_batch_dir(
            batch_dir,
            repository_root=repository_root,
            require_result=True,
        )
        existing = complete["result"]
        replay_keys = ("manager", "additional_evidence", "decisions")
        if any(existing[key] != normalized[key] for key in replay_keys):
            raise ManagerScreeningError(
                f"sealed manager-screen result is immutable: {batch_name}"
            )
        result_seal = complete["result_seal"]
        _materialize_decisions(
            base=base,
            repository_root=repository_root,
            batch=batch,
            result=existing,
            result_path=result_path,
            result_sha256=result_seal.sha256,
        )
        return _record_summary(
            existing,
            result_path=result_path,
            result_sha256=result_seal.sha256,
            repository_root=repository_root,
        )

    try:
        require_manager_screen_first_record_allowed(
            root=base,
            run_id=run,
            batch_id=batch_name,
            batch_sha256=verified["batch_seal"].sha256,
            member_count=batch["member_count"],
            control_required=batch["policy"].get("run_control_required") is True,
        )
    except ManagerScreenControlError as exc:
        raise ManagerScreeningError(str(exc)) from exc

    _enforce_send_to_analyst_capacity(
        run_dir=batch_dir.parent,
        current_batch_dir=batch_dir,
        decisions=normalized["decisions"],
        repository_root=repository_root,
    )
    result = {
        "schema_version": 1,
        "run_id": run,
        "batch_id": batch_name,
        "recorded_at": recorded.isoformat(),
        "information_cutoff": batch["information_cutoff"],
        "batch_path": _relative(verified["batch_path"], repository_root),
        "batch_sha256": verified["batch_seal"].sha256,
        "packet_path": _relative(verified["packet_path"], repository_root),
        "packet_sha256": verified["packet_seal"].sha256,
        "manager": normalized["manager"],
        "additional_evidence": normalized["additional_evidence"],
        "decisions": normalized["decisions"],
        "quality_state": {
            "contract_validation": "passed",
            "fact_review": "deferred_to_analyst_discovery",
            "route_disagreement_is_material_error": False,
            "recursive_correction": "forbidden",
            **(
                {"calibration": _calibration_plan(batch)}
                if _has_calibration_policy(batch["policy"])
                else {}
            ),
        },
        "portfolio_action": None,
    }
    _validate_result(
        result,
        batch=batch,
        packet=packet,
        batch_sha256=verified["batch_seal"].sha256,
        packet_sha256=verified["packet_seal"].sha256,
    )
    result_seal = seal_json(
        result_path,
        result,
        artifact_type="manager_screen_result",
        sealed_at=recorded,
    )
    _materialize_decisions(
        base=base,
        repository_root=repository_root,
        batch=batch,
        result=result,
        result_path=result_path,
        result_sha256=result_seal.sha256,
    )
    return _record_summary(
        result,
        result_path=result_path,
        result_sha256=result_seal.sha256,
        repository_root=repository_root,
    )


def _enforce_send_to_analyst_capacity(
    *,
    run_dir: Path,
    current_batch_dir: Path,
    decisions: list[dict[str, Any]],
    repository_root: Path,
) -> None:
    capacity = _effective_run_send_capacity(
        run_dir=run_dir,
        repository_root=repository_root,
    )
    if capacity is None:
        return
    coverage_root = run_dir.parent.parent
    queue_rows = read_jsonl(coverage_root / RESEARCH_QUEUE_FILE)
    queue_by_symbol = {
        row.get("symbol"): row
        for row in queue_rows
        if isinstance(row, Mapping) and isinstance(row.get("symbol"), str)
    }
    if len(queue_by_symbol) != len(queue_rows):
        raise ManagerScreeningError(
            "research queue symbols are missing or duplicated during capacity accounting"
        )
    run_id = run_dir.name
    queue_routes = {
        symbol: row.get("manager_screen_route")
        for symbol, row in queue_by_symbol.items()
        if row.get("manager_screen_run_id") == run_id
    }
    if any(route not in ROUTES for route in queue_routes.values()):
        raise ManagerScreeningError(
            "research queue has an invalid manager-screen route during capacity accounting"
        )

    from .manager_screen_quote_impact import (
        ManagerScreenQuoteImpactError,
        load_manager_screen_quote_impact_overlay,
    )

    if run_dir.is_dir():
        for batch_dir in _manager_batch_dirs(run_dir):
            if batch_dir.resolve() == current_batch_dir.resolve():
                continue
            result_path = batch_dir / "result.json"
            result_seal_path = result_path.with_name("result.json.seal.json")
            if not result_path.exists() and not result_seal_path.exists():
                continue
            verified = _verify_batch_dir(
                batch_dir,
                repository_root=repository_root,
                require_result=True,
            )
            effective_decisions = {
                decision["symbol"]: decision
                for decision in verified["result"]["decisions"]
            }
            try:
                overlay = load_manager_screen_quote_impact_overlay(
                    root=coverage_root,
                    run_id=run_id,
                    batch_id=verified["batch"]["batch_id"],
                )
            except ManagerScreenQuoteImpactError as exc:
                raise ManagerScreeningError(
                    "manager-screen quote-impact review is invalid during capacity "
                    f"accounting: {verified['batch']['batch_id']}"
                ) from exc
            if overlay["state"] == "recorded":
                for review in overlay["reviews"]:
                    effective_decisions[review["symbol"]] = review[
                        "effective_decision"
                    ]
            for symbol, decision in effective_decisions.items():
                queue = queue_by_symbol.get(symbol)
                if (
                    queue is None
                    or queue.get("manager_screen_run_id") != run_id
                    or queue.get("manager_screen_batch_id")
                    != verified["batch"]["batch_id"]
                    or queue.get("manager_screen_route") != decision["route"]
                ):
                    raise ManagerScreeningError(
                        "research queue does not match the effective sealed "
                        f"manager-screen route during capacity accounting: {symbol}"
                    )
    from .legacy_transition import (
        TRANSITION_ID,
        LegacyTransitionError,
        legacy_transition_status,
    )

    transition_dir = run_dir / TRANSITION_ID
    canonical_transition_result_path = _relative(
        transition_dir / "result.json",
        repository_root,
    )
    legacy_binding_fields = (
        "legacy_transition_action",
        "legacy_transition_id",
        "legacy_transition_run_id",
        "legacy_transition_result_path",
        "legacy_transition_result_sha256",
    )
    queue_references_transition = any(
        row.get("legacy_transition_run_id") == run_id
        or (
            row.get("manager_screen_run_id") == run_id
            and (
                row.get("manager_screen_batch_id") == TRANSITION_ID
                or any(row.get(field) is not None for field in legacy_binding_fields)
            )
        )
        or row.get("legacy_transition_result_path")
        == canonical_transition_result_path
        or row.get("manager_screen_result_path")
        == canonical_transition_result_path
        for row in queue_by_symbol.values()
    )
    if transition_dir.exists() or queue_references_transition:
        if not transition_dir.is_dir():
            raise ManagerScreeningError(
                "research queue references a missing sealed legacy transition "
                "during capacity accounting"
            )
        try:
            transition = legacy_transition_status(
                root=coverage_root,
                run_id=run_id,
            )
        except LegacyTransitionError as exc:
            raise ManagerScreeningError(
                "legacy transition is invalid during capacity accounting"
            ) from exc
        if transition["state"] == "recorded":
            expected_adoptions = transition["classification"]["adoption"]
            if transition["materialized"]["adoption"] != expected_adoptions:
                raise ManagerScreeningError(
                    "legacy transition adoption is not fully materialized during "
                    "capacity accounting"
                )
            transition_result_path = repository_root / transition["result_path"]
            transition_result = _read_object(transition_result_path)
            for decision in transition_result["decisions"]:
                symbol = decision["symbol"]
                queue = queue_by_symbol.get(symbol)
                if (
                    queue is None
                    or queue.get("legacy_transition_run_id") != run_id
                    or queue.get("legacy_transition_id") != TRANSITION_ID
                    or queue.get("legacy_transition_action") != "adoption"
                    or queue.get("legacy_transition_result_path")
                    != transition["result_path"]
                    or queue.get("legacy_transition_result_sha256")
                    != transition["result_sha256"]
                    or queue.get("manager_screen_run_id") != run_id
                    or queue.get("manager_screen_batch_id") != TRANSITION_ID
                    or queue.get("manager_screen_result_path")
                    != transition["result_path"]
                    or queue.get("manager_screen_result_sha256")
                    != transition["result_sha256"]
                    or queue.get("manager_screen_route") != decision["route"]
                ):
                    raise ManagerScreeningError(
                        "research queue does not match the sealed legacy adoption "
                        f"during capacity accounting: {symbol}"
                    )
    sealed_send_count = sum(
        route == "send_to_analyst" for route in queue_routes.values()
    )
    requested_send_count = sum(
        decision["route"] == "send_to_analyst"
        for decision in decisions
    )
    if sealed_send_count + requested_send_count > capacity:
        raise ManagerScreeningError(
            "manager-screen send_to_analyst run capacity would be exceeded: "
            f"{sealed_send_count} sealed + {requested_send_count} requested "
            f"> {capacity}; the whole batch was rejected"
        )


def _enforce_run_capacity_policy_monotonic(
    *,
    run_dir: Path,
    requested_policy: Mapping[str, Any],
    repository_root: Path,
) -> None:
    """Let a legacy run adopt a cap once, then only keep or tighten it."""

    existing_policies = _active_run_bounded_policies(
        run_dir=run_dir,
        repository_root=repository_root,
    )
    if not existing_policies:
        return
    requested = requested_policy.get("send_to_analyst_capacity_per_run")
    effective = min(
        int(policy["send_to_analyst_capacity_per_run"])
        for policy in existing_policies
    )
    if requested is None:
        raise ManagerScreeningError(
            "manager-screen run capacity policy cannot remove an established cap: "
            f"effective capacity is {effective}"
        )
    if requested > effective:
        raise ManagerScreeningError(
            "manager-screen run capacity policy cannot expand within a run: "
            f"requested {requested} > established {effective}"
        )
    established_paths = {str(policy["path"]) for policy in existing_policies}
    if requested_policy.get("path") not in established_paths:
        raise ManagerScreeningError(
            "manager-screen run policy path cannot change after capacity is bound"
        )
    established_effort = min(
        float(policy["quick_profile_effort_budget_hours"])
        for policy in existing_policies
    )
    requested_effort = float(requested_policy["quick_profile_effort_budget_hours"])
    if requested_effort > established_effort:
        raise ManagerScreeningError(
            "manager-screen quick-profile effort budget cannot expand within a run: "
            f"requested {requested_effort} > established {established_effort}"
        )
    established_v2 = [
        policy
        for policy in existing_policies
        if policy.get("decision_contract_version") == 2
    ]
    if established_v2:
        if requested_policy.get("decision_contract_version") != 2:
            raise ManagerScreeningError(
                "manager-screen decision contract v2 cannot be removed within a run"
            )
        established_liability_threshold = min(
            float(policy["high_liability_to_assets_pct"])
            for policy in established_v2
        )
        requested_liability_threshold = float(
            requested_policy["high_liability_to_assets_pct"]
        )
        if requested_liability_threshold > established_liability_threshold:
            raise ManagerScreeningError(
                "manager-screen high-liability risk gate cannot be loosened within "
                f"a run: requested {requested_liability_threshold} > established "
                f"{established_liability_threshold}"
            )
    if any(policy.get("run_control_required") is True for policy in existing_policies):
        if requested_policy.get("run_control_required") is not True:
            raise ManagerScreeningError(
                "manager-screen run control requirement cannot be removed within a run"
            )


def _effective_run_send_capacity(
    *,
    run_dir: Path,
    repository_root: Path,
) -> int | None:
    policies = _active_run_bounded_policies(
        run_dir=run_dir,
        repository_root=repository_root,
    )
    capacities = [
        int(policy["send_to_analyst_capacity_per_run"])
        for policy in policies
    ]
    return min(capacities) if capacities else None


def _active_run_bounded_policies(
    *,
    run_dir: Path,
    repository_root: Path,
) -> list[dict[str, Any]]:
    policies: list[dict[str, Any]] = []
    if not run_dir.is_dir():
        return policies
    for batch_dir in _manager_batch_dirs(run_dir):
        verified = _verify_batch_reservation(
            batch_dir,
            repository_root=repository_root,
        )
        if verified["supersession"] is not None:
            continue
        capacity = verified["batch"]["policy"].get(
            "send_to_analyst_capacity_per_run"
        )
        if capacity is not None:
            policies.append(dict(verified["batch"]["policy"]))
    return policies


@serialized_coverage_write
def prepare_manager_screen_calibration(
    *,
    root: str | Path,
    run_id: str,
    batch_id: str,
    calibration_id: str,
    prepared_at: dt.datetime,
    policy_path: str | Path = "policies/manager-screening.json",
) -> dict[str, Any]:
    """Seal one non-blocking factual-calibration packet for a completed batch."""

    base = Path(root)
    repository_root = base.parent.parent
    run = _identifier(run_id, "run_id")
    batch_name = _identifier(batch_id, "batch_id")
    calibration_name = _identifier(calibration_id, "calibration_id")
    prepared = _aware(prepared_at, "prepared_at")
    batch_dir = base / "manager-screen" / run / batch_name
    verified = _verify_batch_dir(
        batch_dir,
        repository_root=repository_root,
        require_result=True,
    )
    batch = verified["batch"]
    manager_result = verified["result"]
    manifest_path, _, manifest_seal, intake_path, _, intake_seal = (
        _load_scope_artifacts(base=base, run_id=run)
    )
    _require_scope_binding(
        batch=batch,
        manifest_path=manifest_path,
        manifest_sha256=manifest_seal.sha256,
        intake_path=intake_path,
        intake_sha256=intake_seal.sha256,
        repository_root=repository_root,
    )
    if prepared < _parse_datetime(
        manager_result["recorded_at"],
        "manager result recorded_at",
    ):
        raise ManagerScreeningError(
            "calibration prepared_at cannot predate the manager result"
        )
    calibration_root = batch_dir / "calibration"
    existing_ids = sorted(
        path.name
        for path in calibration_root.iterdir()
        if path.is_dir()
    ) if calibration_root.is_dir() else []
    if existing_ids and existing_ids != [calibration_name]:
        raise ManagerScreeningError(
            "manager-screen calibration is single-shot; a calibration already exists "
            f"for {batch_name}: {', '.join(existing_ids)}"
        )
    policy = (
        dict(batch["policy"])
        if _has_calibration_policy(batch["policy"])
        else _load_policy_contract(
            policy_path=policy_path,
            repository_root=repository_root,
        )
    )
    plan = _calibration_plan(batch, policy=policy)
    calibration_dir = calibration_root / calibration_name
    packet_path = calibration_dir / "packet.json"
    result_path = calibration_dir / "result.json"
    if result_path.exists():
        raise ManagerScreeningError(
            f"manager-screen calibration is already complete: {calibration_name}"
        )
    if packet_path.exists():
        calibration = _verify_calibration_dir(
            calibration_dir,
            verified_batch=verified,
            repository_root=repository_root,
            require_result=False,
        )
        existing = calibration["packet"]
        if (
            existing["policy"]["payload_sha256"] != policy["payload_sha256"]
            or existing["plan"] != plan
        ):
            raise ManagerScreeningError(
                f"sealed calibration packet conflicts with request: {calibration_name}"
            )
        return _calibration_prepare_summary(
            calibration,
            repository_root=repository_root,
        )
    dossier_by_symbol = {
        item["symbol"]: item
        for item in verified["packet"]["dossiers"]
    }
    decision_by_symbol = {
        item["symbol"]: item
        for item in manager_result["decisions"]
    }
    samples = []
    for symbol in plan["sample_symbols"]:
        dossier = dossier_by_symbol[symbol]
        samples.append(
            {
                "symbol": symbol,
                "decision": decision_by_symbol[symbol],
                "dossier": dossier,
                "evidence_ids": [
                    item["evidence_id"]
                    for item in dossier["evidence_catalog"]
                ],
            }
        )
    packet = {
        "schema_version": 1,
        "run_id": run,
        "batch_id": batch_name,
        "calibration_id": calibration_name,
        "prepared_at": prepared.isoformat(),
        "batch_path": _relative(verified["batch_path"], repository_root),
        "batch_sha256": verified["batch_seal"].sha256,
        "manager_result_path": _relative(
            verified["result_path"],
            repository_root,
        ),
        "manager_result_sha256": verified["result_seal"].sha256,
        "policy": policy,
        "plan": plan,
        "reviewer_contract": _calibration_reviewer_contract(),
        "samples": samples,
        "non_blocking": True,
        "portfolio_action": None,
    }
    _validate_calibration_packet(
        packet,
        verified_batch=verified,
        repository_root=repository_root,
    )
    packet_seal = seal_json(
        packet_path,
        packet,
        artifact_type="manager_screen_calibration_packet",
        sealed_at=prepared,
    )
    return {
        "schema_version": 1,
        "run_id": run,
        "batch_id": batch_name,
        "calibration_id": calibration_name,
        "planned_sample_count": plan["planned_sample_count"],
        "sample_symbols": plan["sample_symbols"],
        "packet_path": _relative(packet_path, repository_root),
        "packet_sha256": packet_seal.sha256,
        "status": "missing",
        "non_blocking": True,
        "portfolio_action": None,
    }


@serialized_coverage_write
def record_manager_screen_calibration(
    *,
    root: str | Path,
    run_id: str,
    batch_id: str,
    calibration_id: str,
    submission: Mapping[str, Any],
    recorded_at: dt.datetime,
) -> dict[str, Any]:
    """Seal one complete independent calibration review without changing routes."""

    base = Path(root)
    repository_root = base.parent.parent
    run = _identifier(run_id, "run_id")
    batch_name = _identifier(batch_id, "batch_id")
    calibration_name = _identifier(calibration_id, "calibration_id")
    recorded = _aware(recorded_at, "recorded_at")
    batch_dir = base / "manager-screen" / run / batch_name
    verified_batch = _verify_batch_dir(
        batch_dir,
        repository_root=repository_root,
        require_result=True,
    )
    calibration_dir = batch_dir / "calibration" / calibration_name
    calibration = _verify_calibration_dir(
        calibration_dir,
        verified_batch=verified_batch,
        repository_root=repository_root,
        require_result=False,
    )
    packet = calibration["packet"]
    if recorded < _parse_datetime(packet["prepared_at"], "calibration prepared_at"):
        raise ManagerScreeningError(
            "calibration recorded_at cannot predate packet preparation"
        )
    result_path = calibration_dir / "result.json"
    if result_path.exists():
        complete = _verify_calibration_dir(
            calibration_dir,
            verified_batch=verified_batch,
            repository_root=repository_root,
            require_result=True,
        )
        existing = complete["result"]
        normalized = _normalize_calibration_submission(
            submission,
            packet=packet,
            batch=verified_batch["batch"],
            manager_result=verified_batch["result"],
            recorded_at=recorded,
            legacy_contract=_is_legacy_calibration_packet(packet),
        )
        if any(
            existing[key] != normalized[key]
            for key in ("reviewer", "additional_evidence", "reviews")
        ):
            raise ManagerScreeningError(
                f"sealed calibration result is immutable: {calibration_name}"
            )
        return _calibration_record_summary(
            complete,
            repository_root=repository_root,
        )
    normalized = _normalize_calibration_submission(
        submission,
        packet=packet,
        batch=verified_batch["batch"],
        manager_result=verified_batch["result"],
        recorded_at=recorded,
        legacy_contract=False,
    )
    material_error_count = sum(
        len(review["material_errors"])
        for review in normalized["reviews"]
    )
    material_error_symbols = [
        review["symbol"]
        for review in normalized["reviews"]
        if review["material_errors"]
    ]
    route_disagreement_symbols = [
        review["symbol"]
        for review in normalized["reviews"]
        if review["route_disagreement"]["present"]
    ]
    adjudicated_symbols = [
        review["symbol"]
        for review in normalized["reviews"]
        if review["adjudication"]["performed"]
    ]
    result = {
        "schema_version": 1,
        "run_id": run,
        "batch_id": batch_name,
        "calibration_id": calibration_name,
        "recorded_at": recorded.isoformat(),
        "packet_path": _relative(calibration["packet_path"], repository_root),
        "packet_sha256": calibration["packet_seal"].sha256,
        "batch_sha256": verified_batch["batch_seal"].sha256,
        "manager_result_sha256": verified_batch["result_seal"].sha256,
        "policy_payload_sha256": packet["policy"]["payload_sha256"],
        "plan": packet["plan"],
        "reviewer": normalized["reviewer"],
        "additional_evidence": normalized["additional_evidence"],
        "reviews": normalized["reviews"],
        "summary": {
            "status": "material_error" if material_error_count else "complete",
            "planned_sample_count": packet["plan"]["planned_sample_count"],
            "reviewed_sample_count": len(normalized["reviews"]),
            "missing_sample_count": 0,
            "material_error_count": material_error_count,
            "material_error_symbols": material_error_symbols,
            "route_disagreement_count": len(route_disagreement_symbols),
            "route_disagreement_symbols": route_disagreement_symbols,
            "route_disagreement_is_material_error": False,
            "adjudication_count": len(adjudicated_symbols),
            "adjudicated_symbols": adjudicated_symbols,
        },
        "non_blocking": True,
        "recursive_correction": "forbidden",
        "portfolio_action": None,
    }
    _validate_calibration_result(
        result,
        packet=packet,
        packet_sha256=calibration["packet_seal"].sha256,
        verified_batch=verified_batch,
    )
    result_seal = seal_json(
        result_path,
        result,
        artifact_type="manager_screen_calibration_result",
        sealed_at=recorded,
    )
    completed = {
        **calibration,
        "result_path": result_path,
        "result": result,
        "result_seal": result_seal,
    }
    return _calibration_record_summary(
        completed,
        repository_root=repository_root,
    )


def manager_screen_calibration_status(
    *,
    root: str | Path,
    run_id: str,
    batch_id: str | None = None,
) -> dict[str, Any]:
    """Return the calibration-only projection from manager-screen status."""

    status = manager_screen_status(
        root=root,
        run_id=run_id,
        batch_id=batch_id,
    )
    return {
        "schema_version": 1,
        "run_id": status["run_id"],
        "batch_filter": status["batch_filter"],
        "calibration": status["calibration"],
        "batches": [
            {
                "batch_id": item["batch_id"],
                "manager_status": item["status"],
                "calibration": item["calibration"],
            }
            for item in status["batches"]
        ],
        "ok": True,
        "portfolio_action": None,
    }


def manager_screen_status(
    *,
    root: str | Path,
    run_id: str,
    batch_id: str | None = None,
) -> dict[str, Any]:
    """Verify sealed manager-screen artifacts and report whole-scope progress."""

    base = Path(root)
    repository_root = base.parent.parent
    run = _identifier(run_id, "run_id")
    requested_batch = _identifier(batch_id, "batch_id") if batch_id is not None else None
    manifest_path, manifest, manifest_seal, intake_path, intake, intake_seal = (
        _load_scope_artifacts(base=base, run_id=run)
    )
    run_dir = base / "manager-screen" / run
    verified_batches = []
    seen: set[str] = set()
    by_route: Counter[str] = Counter()
    completed_symbols: set[str] = set()
    open_symbols: set[str] = set()
    purchased_analyst_budget: dict[str, float] = {}
    current_effective_send_budget: dict[str, float] = {}
    effective_queue_bindings: dict[str, dict[str, Any]] = {}
    from .manager_screen_quote_impact import (
        ManagerScreenQuoteImpactError,
        load_manager_screen_quote_impact_overlay,
    )

    if run_dir.is_dir():
        for candidate in _manager_batch_dirs(run_dir):
            verified = _verify_batch_dir(candidate, repository_root=repository_root)
            _require_scope_binding(
                batch=verified["batch"],
                manifest_path=manifest_path,
                manifest_sha256=manifest_seal.sha256,
                intake_path=intake_path,
                intake_sha256=intake_seal.sha256,
                repository_root=repository_root,
            )
            try:
                quote_impact = load_manager_screen_quote_impact_overlay(
                    root=base,
                    run_id=run,
                    batch_id=verified["batch"]["batch_id"],
                )
            except ManagerScreenQuoteImpactError as exc:
                raise ManagerScreeningError(
                    "manager-screen quote-impact review is invalid: "
                    f"{verified['batch']['batch_id']}"
                ) from exc
            verified["quote_impact_review"] = quote_impact
            if verified["supersession"] is not None:
                verified_batches.append(verified)
                continue
            for member in verified["batch"]["members"]:
                symbol = member["symbol"]
                if symbol in seen:
                    raise ManagerScreeningError(
                        f"symbol appears in multiple manager-screen batches: {symbol}"
                    )
                seen.add(symbol)
            result = verified.get("result")
            if result is None:
                open_symbols.update(member["symbol"] for member in verified["batch"]["members"])
            else:
                original_decisions = {
                    decision["symbol"]: decision for decision in result["decisions"]
                }
                effective_decisions = dict(original_decisions)
                result_relative = _relative(
                    verified["result_path"],
                    repository_root,
                )
                effective_predecessors = {
                    symbol: (result_relative, verified["result_seal"].sha256)
                    for symbol in original_decisions
                }
                if quote_impact["state"] == "recorded":
                    for review in quote_impact["reviews"]:
                        symbol = review["symbol"]
                        effective_decisions[symbol] = review["effective_decision"]
                        if review["action"] == "replacement":
                            effective_predecessors[symbol] = (
                                quote_impact["result_path"],
                                quote_impact["result_sha256"],
                            )
                original_effort = float(
                    verified["batch"]["policy"][
                        "quick_profile_effort_budget_hours"
                    ]
                )
                for decision in original_decisions.values():
                    if decision["route"] == "send_to_analyst":
                        purchased_analyst_budget[decision["symbol"]] = original_effort
                if quote_impact["state"] == "recorded":
                    quote_effort = float(
                        quote_impact["quick_profile_effort_budget_hours"]
                    )
                    for review in quote_impact["reviews"]:
                        if (
                            review["action"] == "replacement"
                            and review["old_route"] != "send_to_analyst"
                            and review["effective_decision"]["route"]
                            == "send_to_analyst"
                        ):
                            purchased_analyst_budget[review["symbol"]] = quote_effort
                for decision in effective_decisions.values():
                    completed_symbols.add(decision["symbol"])
                    by_route[decision["route"]] += 1
                    if decision["route"] == "send_to_analyst":
                        current_effective_send_budget[decision["symbol"]] = (
                            purchased_analyst_budget[decision["symbol"]]
                        )
                for symbol in purchased_analyst_budget.keys() & effective_decisions.keys():
                    predecessor_path, predecessor_sha256 = effective_predecessors[symbol]
                    effective_queue_bindings[symbol] = {
                        "run_id": run,
                        "batch_id": verified["batch"]["batch_id"],
                        "decision": effective_decisions[symbol],
                        "result_path": predecessor_path,
                        "result_sha256": predecessor_sha256,
                    }
            verified_batches.append(verified)
    if requested_batch is not None and not any(
        item["batch"]["batch_id"] == requested_batch for item in verified_batches
    ):
        raise ManagerScreeningError(f"manager-screen batch not found: {requested_batch}")

    queue = _unique_by_symbol(read_jsonl(base / RESEARCH_QUEUE_FILE), "research queue")
    analyst_backlog_symbols = []
    analyst_state: Counter[str] = Counter()
    analyst_missing_queue_state = 0
    analyst_backlog_hours = 0.0
    for symbol, purchased_hours in sorted(purchased_analyst_budget.items()):
        queued = queue.get(symbol)
        if queued is None:
            analyst_missing_queue_state += 1
            analyst_state["missing"] += 1
            continue
        binding = effective_queue_bindings[symbol]
        decision = binding["decision"]
        if (
            queued.get("manager_screen_run_id") != binding["run_id"]
            or queued.get("manager_screen_batch_id") != binding["batch_id"]
            or queued.get("manager_screen_route") != decision["route"]
            or queued.get("manager_screen_result_path") != binding["result_path"]
            or queued.get("manager_screen_result_sha256") != binding["result_sha256"]
            or queued.get("decisive_question") != decision["decisive_question"]
            or list(queued.get("evidence_ids") or []) != list(decision["evidence_ids"])
        ):
            raise ManagerScreeningError(
                "research queue does not match the effective sealed "
                f"manager-screen decision: {symbol}"
            )
        task_type = str(queued.get("task_type") or "unknown")
        status = str(queued.get("status") or "unknown")
        analyst_state[f"{task_type}:{status}"] += 1
        if (
            symbol in current_effective_send_budget
            and task_type in PROTECTED_TASK_TYPES
            and status in {"pending", "running"}
        ):
            analyst_backlog_symbols.append(symbol)
            current_budget = queued.get("effort_budget_hours")
            analyst_backlog_hours += (
                float(current_budget)
                if (
                    not isinstance(current_budget, bool)
                    and isinstance(current_budget, (int, float))
                    and math.isfinite(float(current_budget))
                    and current_budget > 0
                )
                else purchased_hours
            )
    remaining, deferred, transition = _candidate_members(
        base=base,
        manifest=manifest,
        manifest_sha256=manifest_seal.sha256,
        intake=intake,
        intake_sha256=intake_seal.sha256,
        queue_by_symbol=queue,
        already_batched=seen,
        scope_cutoff=_parse_datetime(
            intake.get("scope_cutoff"),
            "baseline intake scope cutoff",
        ),
    )
    displayed = [
        item
        for item in verified_batches
        if requested_batch is None or item["batch"]["batch_id"] == requested_batch
    ]
    batches = []
    calibration_rows = []
    for item in displayed:
        result = item.get("result")
        supersession = item["supersession"]
        calibration = (
            _superseded_calibration_status()
            if supersession is not None
            else _batch_calibration_status(
                item,
                repository_root=repository_root,
            )
        )
        calibration_rows.append(calibration)
        wall_clock_seconds = (
            (
                _parse_datetime(result["recorded_at"], "result recorded_at")
                - _parse_datetime(item["batch"]["frozen_at"], "batch frozen_at")
            ).total_seconds()
            if result is not None
            else None
        )
        batches.append(
            {
                "batch_id": item["batch"]["batch_id"],
                "member_count": item["batch"]["member_count"],
                "status": (
                    "superseded"
                    if supersession is not None
                    else ("completed" if result is not None else "awaiting_manager")
                ),
                "batch_sha256": item["batch_seal"].sha256,
                "packet_sha256": item["packet_seal"].sha256,
                "result_sha256": (
                    item["result_seal"].sha256 if item.get("result_seal") is not None else None
                ),
                "manager_wall_clock_seconds": wall_clock_seconds,
                "quote_amendment": item["batch"].get("quote_amendment"),
                "quote_impact_review": {
                    key: item["quote_impact_review"][key]
                    for key in (
                        "state",
                        "review_id",
                        "candidate_count",
                        "keep_count",
                        "replacement_count",
                        "new_send_to_analyst_count",
                        "plan_path",
                        "plan_sha256",
                        "packet_path",
                        "packet_sha256",
                        "result_path",
                        "result_sha256",
                        "effective_route_delta",
                    )
                },
                "supersession": supersession,
                "calibration": calibration,
            }
        )
    baseline_intake_total = len(intake.get("members", []))
    screenable_total = baseline_intake_total + transition["release_count"]
    screenable_accounted = len(seen) + len(remaining) + sum(deferred.values())
    if screenable_accounted != screenable_total:
        raise ManagerScreeningError(
            "manager-screen status does not conserve the frozen screenable intake: "
            f"{screenable_accounted} != {screenable_total}"
        )
    calibration_planned = sum(item["planned_sample_count"] for item in calibration_rows)
    calibration_reviewed = sum(item["reviewed_sample_count"] for item in calibration_rows)
    calibration_missing = sum(item["missing_sample_count"] for item in calibration_rows)
    calibration_unconfigured = sum(
        1 for item in calibration_rows if item["status"] == "not_configured"
    )
    calibration_not_applicable = sum(
        1 for item in calibration_rows if item["status"] == "not_applicable"
    )
    calibration_material_errors = sum(
        item.get("material_error_count", 0)
        for item in calibration_rows
    )
    calibration_route_disagreements = sum(
        item.get("route_disagreement_count", 0)
        for item in calibration_rows
    )
    calibration_adjudications = sum(
        item.get("adjudication_count", 0)
        for item in calibration_rows
    )
    calibration_planned_batches = sum(
        1 for item in calibration_rows if item["status"] == "planned"
    )
    try:
        control = manager_screen_control_status(
            root=base,
            run_id=run,
            completed_company_count=len(completed_symbols),
            open_company_count=len(open_symbols),
        )
    except ManagerScreenControlError as exc:
        raise ManagerScreeningError(
            "manager-screen run control is invalid"
        ) from exc
    return {
        "schema_version": 1,
        "run_id": run,
        "batch_filter": requested_batch,
        "baseline_intake_count": baseline_intake_total,
        "screenable_intake_count": screenable_total,
        "legacy_transition": transition,
        "batches_total": len(verified_batches),
        "active_batches": sum(
            1 for item in verified_batches if item["supersession"] is None
        ),
        "completed_batches": sum(
            1
            for item in verified_batches
            if item["supersession"] is None and item.get("result") is not None
        ),
        "open_batches": sum(
            1
            for item in verified_batches
            if item["supersession"] is None and item.get("result") is None
        ),
        "superseded_batches": sum(
            1 for item in verified_batches if item["supersession"] is not None
        ),
        "superseded_company_count": sum(
            item["batch"]["member_count"]
            for item in verified_batches
            if item["supersession"] is not None
        ),
        "batched_company_count": len(seen),
        "completed_company_count": len(completed_symbols),
        "open_company_count": len(open_symbols),
        "control": control,
        "remaining_unbatched_count": len(remaining),
        "deferred_current_state_count": sum(deferred.values()),
        "deferred_current_state": dict(sorted(deferred.items())),
        "screenable_conservation_satisfied": True,
        "by_route": dict(sorted(by_route.items())),
        "analyst_budget": {
            "purchased_company_count": len(purchased_analyst_budget),
            "purchased_effort_budget_hours": sum(
                purchased_analyst_budget.values()
            ),
            "historical_purchased_company_count": len(
                purchased_analyst_budget
            ),
            "historical_purchased_effort_budget_hours": sum(
                purchased_analyst_budget.values()
            ),
            "current_effective_send_company_count": len(
                current_effective_send_budget
            ),
            "current_effective_send_effort_budget_hours": sum(
                current_effective_send_budget.values()
            ),
            "current_backlog_company_count": len(analyst_backlog_symbols),
            "current_backlog_effort_budget_hours": analyst_backlog_hours,
            "current_state": dict(sorted(analyst_state.items())),
            "missing_queue_state_count": analyst_missing_queue_state,
            "capacity_accounting_only": True,
            "machine_route_decision": False,
        },
        "completed_manager_wall_clock_seconds": sum(
            (
                _parse_datetime(item["result"]["recorded_at"], "result recorded_at")
                - _parse_datetime(item["batch"]["frozen_at"], "batch frozen_at")
            ).total_seconds()
            for item in verified_batches
            if item.get("result") is not None
        ),
        "calibration": {
            "non_blocking": True,
            "scope": (
                "security identity, verifiable facts, material risk omissions, "
                "and decision-contract compliance"
            ),
            "route_disagreement_is_material_error": False,
            "planned_sample_count": calibration_planned,
            "reviewed_sample_count": calibration_reviewed,
            "missing_sample_count": calibration_missing,
            "material_error_count": calibration_material_errors,
            "route_disagreement_count": calibration_route_disagreements,
            "adjudication_count": calibration_adjudications,
            "coverage_rate": (
                calibration_reviewed / calibration_planned
                if calibration_planned
                else None
            ),
            "batches_without_calibration_policy": calibration_unconfigured,
            "superseded_batches_not_applicable": calibration_not_applicable,
            "status": (
                "material_error"
                if calibration_material_errors
                else (
                    "missing"
                    if calibration_missing
                    else (
                        "planned"
                        if calibration_planned_batches
                        else (
                            "not_configured"
                            if calibration_unconfigured
                            else (
                                "not_applicable"
                                if calibration_rows
                                and calibration_not_applicable
                                == len(calibration_rows)
                                else "complete"
                            )
                        )
                    )
                )
            ),
        },
        "batches": batches,
        "ok": True,
        "portfolio_action": None,
    }


def verify_manager_screen_terminal(
    *,
    root: str | Path,
    queued: Mapping[str, Any] | None,
    symbol: str,
    scope_cutoff: dt.datetime,
) -> tuple[str, str] | None:
    """Return a verified manager-screen terminal for future scope freezes."""

    if queued is None:
        return None
    candidate = queued.get("manager_screen_result_path")
    if not isinstance(candidate, str) or not candidate:
        if queued.get("task_type") == "manager_screen" and queued.get("status") == "completed":
            candidate = queued.get("result_path")
    if not isinstance(candidate, str) or not candidate:
        return None
    expected_sha256 = queued.get("manager_screen_result_sha256")
    expected_route = queued.get("manager_screen_route")
    expected_run_id = queued.get("manager_screen_run_id")
    expected_batch_id = queued.get("manager_screen_batch_id")
    if (
        not isinstance(expected_sha256, str)
        or not isinstance(expected_route, str)
        or not isinstance(expected_run_id, str)
        or not isinstance(expected_batch_id, str)
    ):
        return None
    base = Path(root)
    repository_root = base.parent.parent
    path = Path(candidate)
    if not path.is_absolute():
        path = repository_root / path
    try:
        verified = _verify_batch_dir(
            path.parent,
            repository_root=repository_root,
            require_result=True,
        )
        result = verified["result"]
        cutoff = _parse_datetime(result["information_cutoff"], "result information_cutoff")
        manifest_path, _, manifest_seal, intake_path, _, intake_seal = (
            _load_scope_artifacts(base=base, run_id=result["run_id"])
        )
        _require_scope_binding(
            batch=verified["batch"],
            manifest_path=manifest_path,
            manifest_sha256=manifest_seal.sha256,
            intake_path=intake_path,
            intake_sha256=intake_seal.sha256,
            repository_root=repository_root,
        )
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    if (
        path.resolve() != verified["result_path"].resolve()
        or cutoff > scope_cutoff
        or verified["result_seal"].sha256 != expected_sha256
        or result["run_id"] != expected_run_id
        or result["batch_id"] != expected_batch_id
    ):
        return None
    decision = next(
        (item for item in result["decisions"] if item["symbol"] == symbol),
        None,
    )
    if decision is None or decision["route"] != expected_route:
        return None
    return _relative(path, repository_root), verified["result_seal"].sha256


def _has_calibration_policy(policy: Mapping[str, Any]) -> bool:
    return CALIBRATION_POLICY_REF_KEYS.issubset(policy)


def _calibration_reviewer_contract() -> dict[str, Any]:
    return {
        "complete_sample_required": True,
        "material_error_types": sorted(CALIBRATION_ERROR_TYPES),
        "route_disagreement_is_material_error": False,
        "independent_reviewer_required": True,
        "adjudication_limit_per_company": 1,
        "adjudication_trigger": CALIBRATION_ADJUDICATION_TRIGGER,
        "recursive_correction": "forbidden",
        "coverage_write": "forbidden",
    }


def _is_legacy_calibration_packet(packet: Mapping[str, Any]) -> bool:
    reviewer_contract = packet.get("reviewer_contract")
    return (
        isinstance(reviewer_contract, Mapping)
        and "adjudication_trigger" not in reviewer_contract
    )


def _calibration_plan(
    batch: Mapping[str, Any],
    *,
    policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    policy = batch["policy"] if policy is None else policy
    if not _has_calibration_policy(policy):
        raise ManagerScreeningError("manager-screen calibration policy is missing")
    members = batch["members"]
    required = min(
        len(members),
        max(
            int(policy["calibration_minimum_per_batch"]),
            math.ceil(len(members) * float(policy["calibration_sample_rate"])),
        ),
    )
    sample_symbols = [
        member["symbol"]
        for member in sorted(
            members,
            key=lambda item: hashlib.sha256(
                (
                    f"{batch['run_id']}\0{batch['batch_id']}\0{item['symbol']}"
                ).encode("utf-8")
            ).hexdigest(),
        )[:required]
    ]
    return {
        "schema_version": 1,
        "status": "planned_non_blocking",
        "non_blocking": True,
        "selection_basis": (
            "deterministic sha256 sample over the sealed batch identity and symbols; "
            "selection does not inspect or change routes"
        ),
        "sample_rate": float(policy["calibration_sample_rate"]),
        "minimum_per_batch": int(policy["calibration_minimum_per_batch"]),
        "planned_sample_count": required,
        "sample_symbols": sample_symbols,
        "material_error_types": list(policy["calibration_material_error_types"]),
        "route_disagreement_is_material_error": False,
        "reviewed_symbol_count": 0,
        "reviewed_symbols": [],
        "missing_sample_count": required,
    }


def _normalize_calibration_submission(
    submission: Mapping[str, Any],
    *,
    packet: Mapping[str, Any],
    batch: Mapping[str, Any],
    manager_result: Mapping[str, Any],
    recorded_at: dt.datetime,
    legacy_contract: bool,
) -> dict[str, Any]:
    if (
        not isinstance(submission, Mapping)
        or set(submission) != CALIBRATION_SUBMISSION_KEYS
        or submission.get("schema_version") != 1
    ):
        raise ManagerScreeningError(
            "calibration submission fields do not match the v1 contract"
        )
    reviewer = _validate_manager(submission.get("reviewer"))
    if reviewer["agent"] == manager_result["manager"]["agent"]:
        raise ManagerScreeningError(
            "calibration reviewer must be independent from the batch manager"
        )
    additional = _validate_additional_evidence(
        submission.get("additional_evidence"),
        batch=batch,
        recorded_at=recorded_at,
    )
    sample_symbols = packet["plan"]["sample_symbols"]
    sample_set = set(sample_symbols)
    if any(item["symbol"] not in sample_set for item in additional):
        raise ManagerScreeningError(
            "calibration additional evidence must belong to the sampled companies"
        )
    reviews = submission.get("reviews")
    if not isinstance(reviews, list):
        raise ManagerScreeningError("calibration reviews must be an array")
    received = [
        item.get("symbol")
        for item in reviews
        if isinstance(item, Mapping)
    ]
    if received != sample_symbols or len(reviews) != len(sample_symbols):
        raise ManagerScreeningError(
            "calibration reviews must cover the deterministic sample exactly once "
            "and in sample order"
        )
    sample_by_symbol = {
        item["symbol"]: item
        for item in packet["samples"]
    }
    external_by_symbol: dict[str, set[str]] = {}
    for item in additional:
        external_by_symbol.setdefault(item["symbol"], set()).add(
            item["evidence_id"]
        )
    normalized_reviews = []
    for review in reviews:
        if (
            not isinstance(review, Mapping)
            or set(review) != CALIBRATION_REVIEW_KEYS
        ):
            raise ManagerScreeningError(
                "calibration review fields do not match the v1 contract"
            )
        symbol = _symbol(review.get("symbol"))
        allowed_evidence = set(sample_by_symbol[symbol]["evidence_ids"])
        allowed_evidence.update(external_by_symbol.get(symbol, set()))
        material_errors = _validate_calibration_errors(
            review.get("material_errors"),
            symbol=symbol,
            allowed_evidence=allowed_evidence,
        )
        route_disagreement = _validate_route_disagreement(
            review.get("route_disagreement"),
            symbol=symbol,
            allowed_evidence=allowed_evidence,
        )
        adjudication = _validate_calibration_adjudication(
            review.get("adjudication"),
            symbol=symbol,
            allowed_evidence=allowed_evidence,
            has_material_error=bool(material_errors),
            has_route_disagreement=route_disagreement["present"],
            legacy_contract=legacy_contract,
        )
        normalized_reviews.append(
            {
                "symbol": symbol,
                "material_errors": material_errors,
                "route_disagreement": route_disagreement,
                "adjudication": adjudication,
            }
        )
    return {
        "reviewer": reviewer,
        "additional_evidence": additional,
        "reviews": normalized_reviews,
    }


def _validate_calibration_errors(
    value: Any,
    *,
    symbol: str,
    allowed_evidence: set[str],
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ManagerScreeningError(
            f"calibration material_errors must be an array: {symbol}"
        )
    seen_types: set[str] = set()
    normalized = []
    for item in value:
        if not isinstance(item, Mapping) or set(item) != CALIBRATION_ERROR_KEYS:
            raise ManagerScreeningError(
                f"calibration material error fields are invalid: {symbol}"
            )
        error_type = item.get("type")
        if error_type not in CALIBRATION_ERROR_TYPES:
            raise ManagerScreeningError(
                f"invalid calibration material error type: {error_type}"
            )
        if error_type in seen_types:
            raise ManagerScreeningError(
                f"duplicate calibration material error type for {symbol}: {error_type}"
            )
        seen_types.add(error_type)
        evidence_ids = _calibration_evidence_ids(
            item.get("evidence_ids"),
            allowed=allowed_evidence,
            label=f"{symbol}.{error_type}.evidence_ids",
            required=True,
        )
        normalized.append(
            {
                "type": error_type,
                "finding": _text(
                    item.get("finding"),
                    f"{symbol}.{error_type}.finding",
                ),
                "evidence_ids": evidence_ids,
            }
        )
    return normalized


def _validate_route_disagreement(
    value: Any,
    *,
    symbol: str,
    allowed_evidence: set[str],
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != ROUTE_DISAGREEMENT_KEYS:
        raise ManagerScreeningError(
            f"route disagreement fields are invalid: {symbol}"
        )
    present = value.get("present")
    if not isinstance(present, bool):
        raise ManagerScreeningError(
            f"route disagreement present must be boolean: {symbol}"
        )
    finding = value.get("finding")
    evidence_ids = _calibration_evidence_ids(
        value.get("evidence_ids"),
        allowed=allowed_evidence,
        label=f"{symbol}.route_disagreement.evidence_ids",
        required=present,
    )
    if present:
        normalized_finding = _text(
            finding,
            f"{symbol}.route_disagreement.finding",
        )
    else:
        if finding is not None or evidence_ids:
            raise ManagerScreeningError(
                f"absent route disagreement cannot contain a finding: {symbol}"
            )
        normalized_finding = None
    return {
        "present": present,
        "finding": normalized_finding,
        "evidence_ids": evidence_ids,
    }


def _validate_calibration_adjudication(
    value: Any,
    *,
    symbol: str,
    allowed_evidence: set[str],
    has_material_error: bool,
    has_route_disagreement: bool,
    legacy_contract: bool,
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != CALIBRATION_ADJUDICATION_KEYS:
        raise ManagerScreeningError(
            f"calibration adjudication fields are invalid: {symbol}"
        )
    performed = value.get("performed")
    if not isinstance(performed, bool):
        raise ManagerScreeningError(
            f"calibration adjudication performed must be boolean: {symbol}"
        )
    outcome = value.get("outcome")
    if outcome not in ADJUDICATION_OUTCOMES:
        raise ManagerScreeningError(
            f"invalid calibration adjudication outcome: {outcome}"
        )
    evidence_ids = _calibration_evidence_ids(
        value.get("evidence_ids"),
        allowed=allowed_evidence,
        label=f"{symbol}.adjudication.evidence_ids",
        required=performed,
    )
    finding = value.get("finding")
    if legacy_contract and performed:
        if not has_material_error and not has_route_disagreement:
            raise ManagerScreeningError(
                f"adjudication requires a recorded disagreement or error: {symbol}"
            )
        if outcome == "material_error_confirmed" and not has_material_error:
            raise ManagerScreeningError(
                f"material-error adjudication lacks a material error: {symbol}"
            )
    elif not legacy_contract and performed != has_material_error:
        if has_material_error:
            raise ManagerScreeningError(
                f"calibration material errors require adjudication: {symbol}"
            )
        raise ManagerScreeningError(
            f"calibration adjudication is allowed only for material errors: {symbol}"
        )
    if not performed:
        if outcome != "not_needed" or finding is not None or evidence_ids:
            raise ManagerScreeningError(
                f"unperformed adjudication must be not_needed: {symbol}"
            )
        normalized_finding = None
    else:
        if outcome == "not_needed":
            raise ManagerScreeningError(
                f"performed adjudication requires an outcome: {symbol}"
            )
        normalized_finding = _text(
            finding,
            f"{symbol}.adjudication.finding",
        )
    return {
        "performed": performed,
        "outcome": outcome,
        "finding": normalized_finding,
        "evidence_ids": evidence_ids,
    }


def _calibration_evidence_ids(
    value: Any,
    *,
    allowed: set[str],
    label: str,
    required: bool,
) -> list[str]:
    if (
        not isinstance(value, list)
        or (required and not value)
        or any(
            not isinstance(item, str)
            or not item
            or item not in allowed
            for item in value
        )
        or len(value) != len(set(value))
    ):
        raise ManagerScreeningError(f"{label} contains invalid evidence references")
    return list(value)


def _validate_calibration_packet(
    packet: Mapping[str, Any],
    *,
    verified_batch: Mapping[str, Any],
    repository_root: Path,
) -> None:
    if (
        set(packet) != CALIBRATION_PACKET_KEYS
        or packet.get("schema_version") != 1
    ):
        raise ManagerScreeningError(
            "manager-screen calibration packet fields are invalid"
        )
    batch = verified_batch["batch"]
    manager_result = verified_batch["result"]
    if (
        packet.get("run_id") != batch["run_id"]
        or packet.get("batch_id") != batch["batch_id"]
        or packet.get("batch_path")
        != _relative(verified_batch["batch_path"], repository_root)
        or packet.get("batch_sha256") != verified_batch["batch_seal"].sha256
        or packet.get("manager_result_path")
        != _relative(verified_batch["result_path"], repository_root)
        or packet.get("manager_result_sha256")
        != verified_batch["result_seal"].sha256
    ):
        raise ManagerScreeningError(
            "manager-screen calibration packet does not bind its batch/result"
        )
    _identifier(packet.get("calibration_id"), "calibration_id")
    prepared = _parse_datetime(packet.get("prepared_at"), "calibration prepared_at")
    if prepared < _parse_datetime(
        manager_result["recorded_at"],
        "manager result recorded_at",
    ):
        raise ManagerScreeningError(
            "manager-screen calibration packet predates manager result"
        )
    policy = packet.get("policy")
    if (
        not isinstance(policy, Mapping)
        or set(policy)
        not in (
            PRE_CAPACITY_POLICY_REF_KEYS,
            PRE_CAPACITY_CONTROL_POLICY_REF_KEYS,
            POLICY_REF_KEYS,
            CONTROL_POLICY_REF_KEYS,
            POLICY_V2_REF_KEYS,
            POLICY_V2_CONTROL_REF_KEYS,
        )
        or not _has_calibration_policy(policy)
    ):
        raise ManagerScreeningError(
            "manager-screen calibration packet policy is invalid"
        )
    for key in ("file_sha256", "payload_sha256"):
        _sha256(policy.get(key), f"calibration policy.{key}")
    expected_plan = _calibration_plan(batch, policy=policy)
    if packet.get("plan") != expected_plan:
        raise ManagerScreeningError(
            "manager-screen calibration packet sample does not match policy"
        )
    samples = packet.get("samples")
    if not isinstance(samples, list) or len(samples) != expected_plan[
        "planned_sample_count"
    ]:
        raise ManagerScreeningError(
            "manager-screen calibration packet sample count is invalid"
        )
    dossier_by_symbol = {
        item["symbol"]: item
        for item in verified_batch["packet"]["dossiers"]
    }
    decision_by_symbol = {
        item["symbol"]: item
        for item in manager_result["decisions"]
    }
    for expected_symbol, sample in zip(
        expected_plan["sample_symbols"],
        samples,
        strict=True,
    ):
        if (
            not isinstance(sample, Mapping)
            or set(sample) != CALIBRATION_SAMPLE_KEYS
            or sample.get("symbol") != expected_symbol
            or sample.get("decision") != decision_by_symbol[expected_symbol]
            or sample.get("dossier") != dossier_by_symbol[expected_symbol]
            or sample.get("evidence_ids")
            != [
                item["evidence_id"]
                for item in dossier_by_symbol[expected_symbol]["evidence_catalog"]
            ]
        ):
            raise ManagerScreeningError(
                "manager-screen calibration sample is not bound to packet facts"
            )
    expected_contract = _calibration_reviewer_contract()
    legacy_contract = dict(expected_contract)
    legacy_contract.pop("adjudication_trigger", None)
    if packet.get("reviewer_contract") not in (expected_contract, legacy_contract):
        raise ManagerScreeningError(
            "manager-screen calibration reviewer contract is invalid"
        )
    if packet.get("non_blocking") is not True or packet.get("portfolio_action") is not None:
        raise ManagerScreeningError(
            "manager-screen calibration packet must be non-blocking"
        )


def _validate_calibration_result(
    result: Mapping[str, Any],
    *,
    packet: Mapping[str, Any],
    packet_sha256: str,
    verified_batch: Mapping[str, Any],
) -> None:
    if (
        set(result) != CALIBRATION_RESULT_KEYS
        or result.get("schema_version") != 1
    ):
        raise ManagerScreeningError(
            "manager-screen calibration result fields are invalid"
        )
    if (
        result.get("run_id") != packet["run_id"]
        or result.get("batch_id") != packet["batch_id"]
        or result.get("calibration_id") != packet["calibration_id"]
        or result.get("packet_sha256") != packet_sha256
        or result.get("batch_sha256") != verified_batch["batch_seal"].sha256
        or result.get("manager_result_sha256")
        != verified_batch["result_seal"].sha256
        or result.get("policy_payload_sha256")
        != packet["policy"]["payload_sha256"]
        or result.get("plan") != packet["plan"]
    ):
        raise ManagerScreeningError(
            "manager-screen calibration result does not bind its inputs"
        )
    recorded = _parse_datetime(result.get("recorded_at"), "calibration recorded_at")
    if recorded < _parse_datetime(packet["prepared_at"], "calibration prepared_at"):
        raise ManagerScreeningError("manager-screen calibration result predates packet")
    normalized = _normalize_calibration_submission(
        {
            "schema_version": 1,
            "reviewer": result.get("reviewer"),
            "additional_evidence": result.get("additional_evidence"),
            "reviews": result.get("reviews"),
        },
        packet=packet,
        batch=verified_batch["batch"],
        manager_result=verified_batch["result"],
        recorded_at=recorded,
        legacy_contract=_is_legacy_calibration_packet(packet),
    )
    if any(result[key] != normalized[key] for key in normalized):
        raise ManagerScreeningError(
            "manager-screen calibration result is not normalized"
        )
    material_error_count = sum(
        len(review["material_errors"])
        for review in normalized["reviews"]
    )
    material_error_symbols = [
        review["symbol"]
        for review in normalized["reviews"]
        if review["material_errors"]
    ]
    route_disagreement_symbols = [
        review["symbol"]
        for review in normalized["reviews"]
        if review["route_disagreement"]["present"]
    ]
    adjudicated_symbols = [
        review["symbol"]
        for review in normalized["reviews"]
        if review["adjudication"]["performed"]
    ]
    expected_summary = {
        "status": "material_error" if material_error_count else "complete",
        "planned_sample_count": packet["plan"]["planned_sample_count"],
        "reviewed_sample_count": len(normalized["reviews"]),
        "missing_sample_count": 0,
        "material_error_count": material_error_count,
        "material_error_symbols": material_error_symbols,
        "route_disagreement_count": len(route_disagreement_symbols),
        "route_disagreement_symbols": route_disagreement_symbols,
        "route_disagreement_is_material_error": False,
        "adjudication_count": len(adjudicated_symbols),
        "adjudicated_symbols": adjudicated_symbols,
    }
    if result.get("summary") != expected_summary:
        raise ManagerScreeningError(
            "manager-screen calibration result summary is invalid"
        )
    if (
        result.get("non_blocking") is not True
        or result.get("recursive_correction") != "forbidden"
        or result.get("portfolio_action") is not None
    ):
        raise ManagerScreeningError(
            "manager-screen calibration result violates the non-blocking contract"
        )


def _verify_calibration_dir(
    calibration_dir: Path,
    *,
    verified_batch: Mapping[str, Any],
    repository_root: Path,
    require_result: bool,
) -> dict[str, Any]:
    packet_path = calibration_dir / "packet.json"
    result_path = calibration_dir / "result.json"
    try:
        packet_seal = verify_sealed(packet_path)
        packet = _read_object(packet_path)
    except (OSError, SealingError, json.JSONDecodeError) as exc:
        raise ManagerScreeningError(
            f"manager-screen calibration packet is invalid: {calibration_dir}"
        ) from exc
    if packet_seal.artifact_type != "manager_screen_calibration_packet":
        raise ManagerScreeningError(
            "manager-screen calibration packet has unexpected artifact type"
        )
    _validate_calibration_packet(
        packet,
        verified_batch=verified_batch,
        repository_root=repository_root,
    )
    if (
        calibration_dir.name != packet["calibration_id"]
        or calibration_dir.parent.parent.name != packet["batch_id"]
        or calibration_dir.parent.parent.parent.name != packet["run_id"]
    ):
        raise ManagerScreeningError(
            "manager-screen calibration directory identity is invalid"
        )
    expected_packet_path = _relative(packet_path, repository_root)
    result = None
    result_seal = None
    if result_path.exists():
        try:
            result_seal = verify_sealed(result_path)
            result = _read_object(result_path)
        except (OSError, SealingError, json.JSONDecodeError) as exc:
            raise ManagerScreeningError(
                f"manager-screen calibration result is invalid: {calibration_dir}"
            ) from exc
        if result_seal.artifact_type != "manager_screen_calibration_result":
            raise ManagerScreeningError(
                "manager-screen calibration result has unexpected artifact type"
            )
        if result.get("packet_path") != expected_packet_path:
            raise ManagerScreeningError(
                "manager-screen calibration result path binding is invalid"
            )
        _validate_calibration_result(
            result,
            packet=packet,
            packet_sha256=packet_seal.sha256,
            verified_batch=verified_batch,
        )
    elif require_result:
        raise ManagerScreeningError(
            f"manager-screen calibration result is missing: {calibration_dir}"
        )
    return {
        "packet_path": packet_path,
        "packet": packet,
        "packet_seal": packet_seal,
        "result_path": result_path,
        "result": result,
        "result_seal": result_seal,
    }


def _calibration_prepare_summary(
    calibration: Mapping[str, Any],
    *,
    repository_root: Path,
) -> dict[str, Any]:
    packet = calibration["packet"]
    return {
        "schema_version": 1,
        "run_id": packet["run_id"],
        "batch_id": packet["batch_id"],
        "calibration_id": packet["calibration_id"],
        "planned_sample_count": packet["plan"]["planned_sample_count"],
        "sample_symbols": packet["plan"]["sample_symbols"],
        "packet_path": _relative(calibration["packet_path"], repository_root),
        "packet_sha256": calibration["packet_seal"].sha256,
        "status": "missing",
        "non_blocking": True,
        "portfolio_action": None,
    }


def _calibration_record_summary(
    calibration: Mapping[str, Any],
    *,
    repository_root: Path,
) -> dict[str, Any]:
    result = calibration["result"]
    return {
        "schema_version": 1,
        "run_id": result["run_id"],
        "batch_id": result["batch_id"],
        "calibration_id": result["calibration_id"],
        "status": result["summary"]["status"],
        "reviewed_sample_count": result["summary"]["reviewed_sample_count"],
        "material_error_count": result["summary"]["material_error_count"],
        "route_disagreement_count": result["summary"][
            "route_disagreement_count"
        ],
        "packet_path": _relative(calibration["packet_path"], repository_root),
        "packet_sha256": calibration["packet_seal"].sha256,
        "result_path": _relative(calibration["result_path"], repository_root),
        "result_sha256": calibration["result_seal"].sha256,
        "non_blocking": True,
        "portfolio_action": None,
    }


def _batch_calibration_status(
    verified: Mapping[str, Any],
    *,
    repository_root: Path,
) -> dict[str, Any]:
    batch = verified["batch"]
    calibration_root = verified["batch_path"].parent / "calibration"
    calibration_dirs = (
        sorted(path for path in calibration_root.iterdir() if path.is_dir())
        if calibration_root.is_dir()
        else []
    )
    if len(calibration_dirs) > 1:
        raise ManagerScreeningError(
            f"manager-screen calibration correction chain is forbidden: "
            f"{batch['batch_id']}"
        )
    if calibration_dirs:
        if verified.get("result") is None:
            raise ManagerScreeningError(
                "manager-screen calibration cannot exist before manager result"
            )
        calibration = _verify_calibration_dir(
            calibration_dirs[0],
            verified_batch=verified,
            repository_root=repository_root,
            require_result=False,
        )
        packet = calibration["packet"]
        result = calibration.get("result")
        if result is None:
            return {
                "status": "missing",
                "calibration_id": packet["calibration_id"],
                "planned_sample_count": packet["plan"]["planned_sample_count"],
                "reviewed_sample_count": 0,
                "missing_sample_count": packet["plan"]["planned_sample_count"],
                "material_error_count": 0,
                "route_disagreement_count": 0,
                "adjudication_count": 0,
                "sample_symbols": packet["plan"]["sample_symbols"],
                "packet_sha256": calibration["packet_seal"].sha256,
                "result_sha256": None,
            }
        summary = result["summary"]
        return {
            "status": summary["status"],
            "calibration_id": packet["calibration_id"],
            "planned_sample_count": summary["planned_sample_count"],
            "reviewed_sample_count": summary["reviewed_sample_count"],
            "missing_sample_count": summary["missing_sample_count"],
            "material_error_count": summary["material_error_count"],
            "route_disagreement_count": summary["route_disagreement_count"],
            "adjudication_count": summary["adjudication_count"],
            "sample_symbols": packet["plan"]["sample_symbols"],
            "packet_sha256": calibration["packet_seal"].sha256,
            "result_sha256": calibration["result_seal"].sha256,
        }
    if not _has_calibration_policy(batch["policy"]):
        return {
            "status": "not_configured",
            "planned_sample_count": 0,
            "reviewed_sample_count": 0,
            "missing_sample_count": 0,
            "sample_symbols": [],
        }
    expected = _calibration_plan(batch)
    result = verified.get("result")
    if result is None:
        return {
            "status": "planned",
            "planned_sample_count": expected["planned_sample_count"],
            "reviewed_sample_count": 0,
            "missing_sample_count": 0,
            "material_error_count": 0,
            "route_disagreement_count": 0,
            "adjudication_count": 0,
            "sample_symbols": expected["sample_symbols"],
        }
    observed = result["quality_state"].get("calibration")
    if observed != expected:
        raise ManagerScreeningError(
            f"manager-screen calibration plan is invalid: {batch['batch_id']}"
        )
    return {
        "status": "missing" if expected["missing_sample_count"] else "complete",
        "planned_sample_count": expected["planned_sample_count"],
        "reviewed_sample_count": expected["reviewed_symbol_count"],
        "missing_sample_count": expected["missing_sample_count"],
        "material_error_count": 0,
        "route_disagreement_count": 0,
        "adjudication_count": 0,
        "sample_symbols": expected["sample_symbols"],
    }


def _superseded_calibration_status() -> dict[str, Any]:
    return {
        "status": "not_applicable",
        "planned_sample_count": 0,
        "reviewed_sample_count": 0,
        "missing_sample_count": 0,
        "material_error_count": 0,
        "route_disagreement_count": 0,
        "adjudication_count": 0,
        "sample_symbols": [],
    }


def _load_policy_contract(
    *,
    policy_path: str | Path,
    repository_root: Path,
) -> dict[str, Any]:
    path = Path(policy_path)
    if not path.is_absolute():
        path = repository_root / path
    if not path.is_file():
        raise ManagerScreeningError(f"manager-screen policy is missing: {path}")
    policy = load_policy(path)
    if policy.kind != PolicyKind.MANAGER_SCREENING:
        raise ManagerScreeningError("manager-screen policy kind must be manager_screening")
    payload = dict(policy.payload)
    default_size = _positive_int(payload.get("default_batch_size"), "default_batch_size")
    minimum_size = _positive_int(payload.get("minimum_batch_size"), "minimum_batch_size")
    maximum_size = _positive_int(payload.get("maximum_batch_size"), "maximum_batch_size")
    if not minimum_size <= default_size <= maximum_size:
        raise ManagerScreeningError("manager-screen batch-size policy is inconsistent")
    if set(payload.get("routes") or []) != ROUTES:
        raise ManagerScreeningError("manager-screen policy routes do not match the contract")
    effort = payload.get("quick_profile_effort_budget_hours")
    if isinstance(effort, bool) or not isinstance(effort, (int, float)) or effort <= 0:
        raise ManagerScreeningError(
            "quick_profile_effort_budget_hours must be positive"
        )
    stops = payload.get("quick_profile_stop_conditions")
    if (
        not isinstance(stops, list)
        or not stops
        or not all(isinstance(item, str) and item.strip() for item in stops)
    ):
        raise ManagerScreeningError(
            "quick_profile_stop_conditions must be a non-empty string array"
        )
    if payload.get("pass_and_watch_require_revisit_trigger") is not True:
        raise ManagerScreeningError(
            "manager-screen policy must require pass/watch revisit triggers"
        )
    if payload.get("recursive_correction") != "forbidden":
        raise ManagerScreeningError("manager-screen policy must forbid recursive correction")
    reason_max = _positive_int(
        payload.get("one_line_reason_max_chars"),
        "one_line_reason_max_chars",
    )
    question_max = _positive_int(
        payload.get("decisive_question_max_chars"),
        "decisive_question_max_chars",
    )
    if not isinstance(payload.get("fact_snapshot_required"), bool):
        raise ManagerScreeningError("fact_snapshot_required must be boolean")
    minimum_annual_periods = _positive_int(
        payload.get("minimum_annual_periods"),
        "minimum_annual_periods",
    )
    quality = payload.get("quality")
    if not isinstance(quality, Mapping):
        raise ManagerScreeningError("manager-screen quality policy must be an object")
    validation_rate = quality.get("programmatic_validation_rate")
    if (
        isinstance(validation_rate, bool)
        or not isinstance(validation_rate, (int, float))
        or float(validation_rate) != 1.0
    ):
        raise ManagerScreeningError("programmatic_validation_rate must be 1.0")
    sample_rate = quality.get("calibration_sample_rate")
    if (
        isinstance(sample_rate, bool)
        or not isinstance(sample_rate, (int, float))
        or not 0 < float(sample_rate) <= 1
    ):
        raise ManagerScreeningError(
            "calibration_sample_rate must be greater than 0 and at most 1"
        )
    calibration_minimum = _positive_int(
        quality.get("calibration_minimum_per_batch"),
        "calibration_minimum_per_batch",
    )
    error_types = quality.get("material_error_types")
    if (
        not isinstance(error_types, list)
        or set(error_types) != CALIBRATION_ERROR_TYPES
        or len(error_types) != len(CALIBRATION_ERROR_TYPES)
    ):
        raise ManagerScreeningError(
            "manager-screen calibration material_error_types do not match the contract"
        )
    if quality.get("route_disagreement_is_material_error") is not False:
        raise ManagerScreeningError(
            "route disagreement must not be a manager-screen material error"
        )
    capacity = None
    if "send_to_analyst_capacity_per_run" in payload:
        capacity = _positive_int(
            payload.get("send_to_analyst_capacity_per_run"),
            "send_to_analyst_capacity_per_run",
        )
    decision_contract_version = payload.get("decision_contract_version")
    decision_v2: dict[str, Any] = {}
    if decision_contract_version is not None:
        if decision_contract_version != 2:
            raise ManagerScreeningError(
                "manager-screen decision_contract_version must be 2 when configured"
            )
        if payload.get("mandatory_risk_acknowledgement") is not True:
            raise ManagerScreeningError(
                "decision contract v2 must require mandatory risk acknowledgement"
            )
        if payload.get("canonical_fact_line_required") is not True:
            raise ManagerScreeningError(
                "decision contract v2 must require the canonical fact line"
            )
        liability_threshold = payload.get("high_liability_to_assets_pct")
        if (
            isinstance(liability_threshold, bool)
            or not isinstance(liability_threshold, (int, float))
            or not math.isfinite(float(liability_threshold))
            or not 0 < float(liability_threshold) <= 100
        ):
            raise ManagerScreeningError(
                "high_liability_to_assets_pct must be greater than 0 and at most 100"
            )
        decision_v2 = {
            "decision_contract_version": 2,
            "mandatory_risk_acknowledgement": True,
            "canonical_fact_line_required": True,
            "high_liability_to_assets_pct": float(liability_threshold),
        }
    run_control: dict[str, Any] = {}
    if "run_control_required" in payload:
        if payload.get("run_control_required") is not True:
            raise ManagerScreeningError(
                "manager-screen run_control_required must be true when configured"
            )
        run_control = {"run_control_required": True}
    raw = path.read_bytes()
    return {
        "policy_id": policy.policy_id,
        "version": policy.version,
        "path": _relative_or_absolute(path, repository_root),
        "file_sha256": hashlib.sha256(raw).hexdigest(),
        "payload_sha256": hashlib.sha256(canonical_json_bytes(payload)).hexdigest(),
        "default_batch_size": default_size,
        "minimum_batch_size": minimum_size,
        "maximum_batch_size": maximum_size,
        "fact_snapshot_required": payload["fact_snapshot_required"],
        "minimum_annual_periods": minimum_annual_periods,
        "quick_profile_effort_budget_hours": effort,
        "quick_profile_stop_conditions": [item.strip() for item in stops],
        "pass_and_watch_require_revisit_trigger": True,
        "recursive_correction": "forbidden",
        "one_line_reason_max_chars": reason_max,
        "decisive_question_max_chars": question_max,
        "programmatic_validation_rate": 1.0,
        "calibration_sample_rate": float(sample_rate),
        "calibration_minimum_per_batch": calibration_minimum,
        "calibration_material_error_types": sorted(CALIBRATION_ERROR_TYPES),
        "route_disagreement_is_material_error": False,
        **(
            {"send_to_analyst_capacity_per_run": capacity}
            if capacity is not None
            else {}
        ),
        **decision_v2,
        **run_control,
    }


def _load_scope_artifacts(*, base: Path, run_id: str):
    scope_dir = base / "scopes" / run_id
    manifest_path = scope_dir / "manifest.json"
    intake_path = scope_dir / "baseline-intake.json"
    try:
        manifest_seal = verify_sealed(manifest_path)
        intake_seal = verify_sealed(intake_path)
    except (OSError, SealingError) as exc:
        raise ManagerScreeningError(
            f"scope artifacts are not validly sealed: {run_id}"
        ) from exc
    if manifest_seal.artifact_type != "all_a_scope_manifest":
        raise ManagerScreeningError("scope manifest has an unexpected artifact type")
    if intake_seal.artifact_type != "all_a_baseline_intake":
        raise ManagerScreeningError("baseline intake has an unexpected artifact type")
    manifest = _read_object(manifest_path)
    intake = _read_object(intake_path)
    if manifest.get("run_id") != run_id or intake.get("run_id") != run_id:
        raise ManagerScreeningError("scope artifacts do not match run_id")
    if intake.get("scope_manifest_sha256") != manifest_seal.sha256:
        raise ManagerScreeningError("baseline intake does not bind scope manifest")
    members = intake.get("members")
    if not isinstance(members, list):
        raise ManagerScreeningError("baseline intake members must be an array")
    return manifest_path, manifest, manifest_seal, intake_path, intake, intake_seal


def _require_frozen_universe_snapshot(
    *,
    base: Path,
    manifest: Mapping[str, Any],
) -> Path:
    universe_source = manifest.get("universe_source")
    if not isinstance(universe_source, Mapping):
        raise ManagerScreeningError("scope manifest universe source is invalid")
    source_path_value = universe_source.get("path")
    if not isinstance(source_path_value, str) or not source_path_value:
        raise ManagerScreeningError("scope manifest universe source path is invalid")
    source_path = Path(source_path_value)
    if not source_path.is_absolute():
        source_path = base.parent.parent / source_path
    source_path = source_path.resolve()
    repository_root = base.parent.parent.resolve()
    try:
        source_path.relative_to(repository_root)
    except ValueError as exc:
        raise ManagerScreeningError(
            "scope universe snapshot must be stored inside the repository"
        ) from exc
    try:
        source_sha256 = hashlib.sha256(source_path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ManagerScreeningError(
            "frozen manager-screen company snapshot is unavailable"
        ) from exc
    if source_sha256 != universe_source.get("sha256"):
        raise ManagerScreeningError(
            "company snapshot changed after scope freeze; create a new scope"
        )
    return source_path


def _latest_quote_amendment(
    *,
    base: Path,
    run_id: str,
    base_snapshot_path: Path,
    frozen_at: dt.datetime,
    repository_root: Path,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    amendment_dir = base / "snapshots" / run_id / "quote-amendments"
    if not amendment_dir.is_dir():
        return None, None
    base_sha256 = hashlib.sha256(base_snapshot_path.read_bytes()).hexdigest()
    base_symbols = {
        _symbol(item.get("symbol"))
        for item in read_jsonl(base_snapshot_path)
    }
    eligible = []
    for path in sorted(amendment_dir.glob("*.json")):
        if path.name.endswith(".seal.json"):
            continue
        try:
            seal = verify_sealed(path)
            payload = _read_object(path)
        except (OSError, SealingError, json.JSONDecodeError) as exc:
            raise ManagerScreeningError(
                f"manager-screen quote amendment is not validly sealed: {path}"
            ) from exc
        if seal.artifact_type != "manager_screen_quote_amendment":
            raise ManagerScreeningError(
                f"manager-screen quote amendment has unexpected type: {path}"
            )
        _validate_quote_amendment_payload(
            payload,
            run_id=run_id,
            base_snapshot_path=base_snapshot_path,
            base_snapshot_sha256=base_sha256,
            base_symbols=base_symbols,
            repository_root=repository_root,
        )
        effective = _parse_datetime(
            payload["effective_at"],
            "quote amendment effective_at",
        )
        if effective <= frozen_at:
            eligible.append((effective, payload["amendment_id"], path, seal, payload))
    if not eligible:
        return None, None
    effective, amendment_id, path, seal, payload = max(
        eligible,
        key=lambda item: (item[0], item[1]),
    )
    return (
        {
            "amendment_id": amendment_id,
            "path": _relative(path, repository_root),
            "sha256": seal.sha256,
            "effective_at": effective.isoformat(),
            "base_snapshot_sha256": base_sha256,
        },
        payload,
    )


def _validate_quote_amendment_payload(
    payload: Mapping[str, Any],
    *,
    run_id: str,
    base_snapshot_path: Path,
    base_snapshot_sha256: str,
    base_symbols: set[str],
    repository_root: Path,
) -> None:
    expected_keys = {
        "schema_version",
        "run_id",
        "amendment_id",
        "effective_at",
        "base_snapshot_path",
        "base_snapshot_sha256",
        "quote_freshness_policy",
        "quote_count",
        "quotes",
        "portfolio_action",
    }
    if set(payload) != expected_keys or payload.get("schema_version") != 1:
        raise ManagerScreeningError("manager-screen quote amendment fields are invalid")
    if payload.get("run_id") != run_id:
        raise ManagerScreeningError("manager-screen quote amendment run_id is invalid")
    _identifier(payload.get("amendment_id"), "quote amendment id")
    effective_at = _parse_datetime(
        payload.get("effective_at"),
        "quote amendment effective_at",
    )
    if (
        payload.get("base_snapshot_path")
        != _relative(base_snapshot_path, repository_root)
        or payload.get("base_snapshot_sha256") != base_snapshot_sha256
    ):
        raise ManagerScreeningError(
            "manager-screen quote amendment does not bind the frozen companies snapshot"
        )
    _sha256(payload.get("base_snapshot_sha256"), "quote amendment base snapshot sha256")
    freshness_policy = payload.get("quote_freshness_policy")
    if not isinstance(freshness_policy, Mapping):
        raise ManagerScreeningError("quote amendment freshness policy is missing")
    max_age = _positive_int(
        freshness_policy.get("max_age_seconds"),
        "quote amendment max_age_seconds",
    )
    future_tolerance = _positive_int(
        freshness_policy.get("future_tolerance_seconds"),
        "quote amendment future_tolerance_seconds",
    )
    quotes = payload.get("quotes")
    if not isinstance(quotes, list) or payload.get("quote_count") != len(quotes):
        raise ManagerScreeningError("quote amendment quote count is invalid")
    symbols = []
    for quote in quotes:
        if not isinstance(quote, Mapping):
            raise ManagerScreeningError("quote amendment row must be an object")
        symbol = _symbol(quote.get("symbol"))
        symbols.append(symbol)
        freshness = quote.get("quote_freshness")
        if (
            not isinstance(freshness, Mapping)
            or freshness.get("schema_version") != 1
            or freshness.get("status") != "fresh"
            or freshness.get("max_age_seconds")
            != freshness_policy.get("max_age_seconds")
            or freshness.get("future_tolerance_seconds")
            != freshness_policy.get("future_tolerance_seconds")
        ):
            raise ManagerScreeningError(
                f"quote amendment freshness row is invalid: {symbol}"
            )
        quote_as_of = _parse_datetime(
            freshness.get("quote_as_of"),
            f"{symbol}.quote amendment as_of",
        )
        if (
            _parse_datetime(quote.get("as_of"), f"{symbol}.quote as_of")
            != quote_as_of
            or freshness.get("evaluated_at") != effective_at.isoformat()
        ):
            raise ManagerScreeningError(
                f"quote amendment freshness timestamps are inconsistent: {symbol}"
            )
        age = effective_at - quote_as_of
        if age > dt.timedelta(seconds=max_age):
            raise ManagerScreeningError(
                f"quote amendment claims a stale quote is fresh: {symbol}"
            )
        if -age > dt.timedelta(seconds=future_tolerance):
            raise ManagerScreeningError(
                f"quote amendment quote is after effective_at: {symbol}"
            )
        source = quote.get("source")
        if (
            not isinstance(source, str)
            or not source.strip()
            or freshness.get("source") != source.strip()
        ):
            raise ManagerScreeningError(
                f"quote amendment source is missing or inconsistent: {symbol}"
            )
        fetched_at = _parse_datetime(
            quote.get("fetched_at"),
            f"{symbol}.quote fetched_at",
        )
        if fetched_at - effective_at > dt.timedelta(seconds=future_tolerance):
            raise ManagerScreeningError(
                f"quote amendment fetched_at is after effective_at: {symbol}"
            )
        if quote_as_of - fetched_at > dt.timedelta(seconds=future_tolerance):
            raise ManagerScreeningError(
                f"quote amendment fetched_at predates quote_as_of: {symbol}"
            )
        price = quote.get("price")
        if (
            isinstance(price, bool)
            or not isinstance(price, (int, float))
            or not math.isfinite(float(price))
            or price <= 0
        ):
            raise ManagerScreeningError(
                f"quote amendment price is invalid: {symbol}"
            )
    if len(symbols) != len(set(symbols)) or set(symbols) != base_symbols:
        raise ManagerScreeningError(
            "quote amendment must cover the frozen company universe exactly once"
        )
    if payload.get("portfolio_action") is not None:
        raise ManagerScreeningError(
            "quote amendment cannot contain a portfolio action"
        )


def _apply_quote_amendment(
    companies: list[dict[str, Any]],
    *,
    amendment: Mapping[str, Any],
) -> list[dict[str, Any]]:
    quotes = {
        _symbol(item.get("symbol")): item
        for item in amendment["quotes"]
    }
    updated = []
    for company in companies:
        row = dict(company)
        symbol = _symbol(row.get("symbol"))
        quote = quotes[symbol]
        for field in MARKET_FIELDS:
            if field != "manager_screen_facts" and field in quote:
                row[field] = quote.get(field)
        facts = (
            dict(row["manager_screen_facts"])
            if isinstance(row.get("manager_screen_facts"), Mapping)
            else {}
        )
        facts["quote_freshness"] = dict(quote["quote_freshness"])
        row["manager_screen_facts"] = facts
        updated.append(row)
    return updated


def _require_scope_binding(
    *,
    batch: Mapping[str, Any],
    manifest_path: Path,
    manifest_sha256: str,
    intake_path: Path,
    intake_sha256: str,
    repository_root: Path,
) -> None:
    expected = {
        "manifest_path": _relative(manifest_path, repository_root),
        "manifest_sha256": manifest_sha256,
        "baseline_intake_path": _relative(intake_path, repository_root),
        "baseline_intake_sha256": intake_sha256,
    }
    if batch.get("scope") != expected:
        raise ManagerScreeningError(
            "manager-screen batch does not bind the frozen scope artifacts"
        )


def _candidate_members(
    *,
    base: Path,
    manifest: Mapping[str, Any],
    manifest_sha256: str,
    intake: Mapping[str, Any],
    intake_sha256: str,
    queue_by_symbol: Mapping[str, Mapping[str, Any]],
    already_batched: set[str],
    scope_cutoff: dt.datetime,
) -> tuple[list[dict[str, Any]], Counter[str], dict[str, Any]]:
    candidates = []
    deferred: Counter[str] = Counter()
    transition = _manager_screen_transition_overlay(
        base=base,
        manifest=manifest,
        manifest_sha256=manifest_sha256,
        intake=intake,
        intake_sha256=intake_sha256,
        queue_by_symbol=queue_by_symbol,
    )
    transition_actions = transition.pop("actions")
    release_members = transition.pop("release_members")
    intake_symbols: set[str] = set()
    for member in intake.get("members", []):
        if not isinstance(member, Mapping):
            raise ManagerScreeningError("baseline intake member must be an object")
        symbol = _symbol(member.get("symbol"))
        if symbol in intake_symbols:
            raise ManagerScreeningError(
                f"duplicate baseline intake member: {symbol}"
            )
        intake_symbols.add(symbol)
        action = member.get("materialization_action")
        if action != "normalize_queue":
            transition_action = transition_actions.get(symbol)
            deferred[
                (
                    f"legacy_transition_{transition_action}"
                    if transition_action in {"adoption", "defer_active"}
                    else str(action)
                )
            ] += 1
            continue
        if symbol in transition_actions:
            raise ManagerScreeningError(
                f"legacy transition overlaps normalized baseline intake: {symbol}"
            )
        if symbol in already_batched:
            continue
        queued = queue_by_symbol.get(symbol)
        reason = _queue_defer_reason(
            base=base,
            queued=queued,
            symbol=symbol,
            scope_cutoff=scope_cutoff,
        )
        if reason is not None:
            deferred[reason] += 1
            continue
        candidates.append(dict(member))
    for member in release_members:
        symbol = _symbol(member.get("symbol"))
        if symbol in intake_symbols:
            raise ManagerScreeningError(
                f"legacy transition release duplicates baseline intake: {symbol}"
            )
        if symbol in already_batched:
            continue
        queued = queue_by_symbol.get(symbol)
        reason = _queue_defer_reason(
            base=base,
            queued=queued,
            symbol=symbol,
            scope_cutoff=scope_cutoff,
        )
        if reason is not None:
            deferred[reason] += 1
            continue
        candidates.append(dict(member))
    candidates.sort(key=lambda item: _positive_int(item.get("ordinal"), "scope ordinal"))
    return candidates, deferred, transition


def _manager_screen_transition_overlay(
    *,
    base: Path,
    manifest: Mapping[str, Any],
    manifest_sha256: str,
    intake: Mapping[str, Any],
    intake_sha256: str,
    queue_by_symbol: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    run_id = _identifier(intake.get("run_id"), "baseline intake run_id")
    transition_dir = (
        base / "manager-screen" / run_id / "legacy-transition-001"
    )
    absent = {
        "state": "absent",
        "release_count": 0,
        "adoption_count": 0,
        "defer_active_count": 0,
        "result_path": None,
        "result_sha256": None,
        "actions": {},
        "release_members": [],
    }
    if not transition_dir.exists():
        return absent
    if not transition_dir.is_dir():
        raise ManagerScreeningError(
            "legacy transition path is not a directory"
        )

    from .legacy_transition import (
        LegacyTransitionError,
        legacy_transition_status,
    )

    try:
        status = legacy_transition_status(root=base, run_id=run_id)
    except LegacyTransitionError as exc:
        raise ManagerScreeningError(
            f"legacy transition is invalid: {exc}"
        ) from exc
    if status["state"] != "recorded":
        return {
            **absent,
            "state": "frozen",
            "plan_path": status["plan_path"],
            "plan_sha256": status["plan_sha256"],
        }
    classification = status["classification"]
    materialized = status["materialized"]
    for action in ("adoption", "rescreen", "defer_active"):
        if materialized.get(action) != classification.get(action):
            raise ManagerScreeningError(
                "legacy transition is not fully materialized: "
                f"{action}={materialized.get(action)}/"
                f"{classification.get(action)}"
            )

    repository_root = base.parent.parent.resolve()
    plan_path = _bound_repository_artifact(
        repository_root,
        status["plan_path"],
        expected_sha256=status["plan_sha256"],
        expected_type="manager_screen_legacy_transition_plan",
        label="legacy transition plan",
    )
    result_path = _bound_repository_artifact(
        repository_root,
        status["result_path"],
        expected_sha256=status["result_sha256"],
        expected_type="manager_screen_legacy_transition_result",
        label="legacy transition result",
    )
    plan = _read_object(plan_path)
    result = _read_object(result_path)
    expected_scope = {
        "manifest_path": _relative(
            base / "scopes" / run_id / "manifest.json",
            repository_root,
        ),
        "manifest_sha256": manifest_sha256,
        "baseline_intake_path": _relative(
            base / "scopes" / run_id / "baseline-intake.json",
            repository_root,
        ),
        "baseline_intake_sha256": intake_sha256,
    }
    if plan.get("scope") != expected_scope:
        raise ManagerScreeningError(
            "legacy transition does not bind the current manager-screen scope"
        )

    actions: dict[str, str] = {}
    for item in plan.get("members", []):
        if not isinstance(item, Mapping):
            raise ManagerScreeningError(
                "legacy transition plan member is invalid"
            )
        symbol = _symbol(item.get("symbol"))
        if symbol in actions:
            raise ManagerScreeningError(
                f"duplicate legacy transition member: {symbol}"
            )
        actions[symbol] = str(item.get("action"))

    release_symbols = result.get("releases")
    if not isinstance(release_symbols, list):
        raise ManagerScreeningError(
            "legacy transition releases must be an array"
        )
    if len(release_symbols) != len(set(release_symbols)):
        raise ManagerScreeningError(
            "legacy transition releases contain duplicates"
        )
    manifest_by_symbol: dict[str, dict[str, Any]] = {}
    for member in manifest.get("members", []):
        if not isinstance(member, Mapping):
            raise ManagerScreeningError(
                "scope manifest member must be an object"
            )
        symbol = _symbol(member.get("symbol"))
        if symbol in manifest_by_symbol:
            raise ManagerScreeningError(
                f"duplicate scope manifest member: {symbol}"
            )
        _positive_int(member.get("ordinal"), "scope ordinal")
        manifest_by_symbol[symbol] = dict(member)

    release_members = []
    for value in release_symbols:
        symbol = _symbol(value)
        if actions.get(symbol) != "rescreen":
            raise ManagerScreeningError(
                f"legacy transition release action is invalid: {symbol}"
            )
        member = manifest_by_symbol.get(symbol)
        if member is None:
            raise ManagerScreeningError(
                f"legacy transition release is outside scope: {symbol}"
            )
        queued = queue_by_symbol.get(symbol) or {}
        if (
            queued.get("legacy_transition_result_sha256")
            != status["result_sha256"]
            or queued.get("legacy_transition_action") != "rescreen"
        ):
            raise ManagerScreeningError(
                f"legacy transition release is not materialized: {symbol}"
            )
        release_members.append(member)
    release_members.sort(
        key=lambda item: _positive_int(item.get("ordinal"), "scope ordinal")
    )
    if len(release_members) != classification["rescreen"]:
        raise ManagerScreeningError(
            "legacy transition release count does not match classification"
        )
    return {
        "state": "recorded",
        "release_count": len(release_members),
        "adoption_count": classification["adoption"],
        "defer_active_count": classification["defer_active"],
        "result_path": status["result_path"],
        "result_sha256": status["result_sha256"],
        "actions": actions,
        "release_members": release_members,
    }


def _bound_repository_artifact(
    repository_root: Path,
    value: Any,
    *,
    expected_sha256: Any,
    expected_type: str,
    label: str,
) -> Path:
    relative = _text(value, f"{label} path")
    path = (repository_root / relative).resolve()
    try:
        path.relative_to(repository_root)
    except ValueError as exc:
        raise ManagerScreeningError(
            f"{label} is outside the repository"
        ) from exc
    try:
        sealed = verify_sealed(path)
    except (OSError, SealingError) as exc:
        raise ManagerScreeningError(f"{label} is not validly sealed") from exc
    if sealed.sha256 != _sha256(expected_sha256, f"{label} sha256"):
        raise ManagerScreeningError(f"{label} SHA binding is invalid")
    if sealed.artifact_type != expected_type:
        raise ManagerScreeningError(f"{label} artifact type is invalid")
    return path


def _queue_defer_reason(
    *,
    base: Path,
    queued: Mapping[str, Any] | None,
    symbol: str,
    scope_cutoff: dt.datetime,
) -> str | None:
    if queued is None:
        return None
    if (
        verify_manager_screen_terminal(
            root=base,
            queued=queued,
            symbol=symbol,
            scope_cutoff=scope_cutoff,
        )
        is not None
    ):
        return "manager_screen_terminal"
    if queued.get("task_type") in PROTECTED_TASK_TYPES:
        return "analyst_or_deeper_stage"
    if queued.get("status") == "running":
        return "running"
    if queued.get("task_type") == "rapid_triage" and queued.get("status") == "completed":
        from .scope_workflow import _verified_rapid_triage_terminal

        repository_root = base.parent.parent
        if (
            _verified_rapid_triage_terminal(
                queued,
                repository_root=repository_root,
                symbol=symbol,
                scope_cutoff=scope_cutoff,
            )
            is not None
        ):
            return "legacy_rapid_triage_terminal"
    return None


def _build_dossier(
    *,
    member: Mapping[str, Any],
    company: Mapping[str, Any] | None,
    screening: Mapping[str, Any] | None,
    queue: Mapping[str, Any] | None,
    company_snapshot_path: Path,
    require_fact_snapshot: bool,
    minimum_annual_periods: int,
    frozen_at: dt.datetime,
    quote_amendment: Mapping[str, Any] | None,
    repository_root: Path,
    decision_contract_version: int,
    high_liability_to_assets_pct: Any,
) -> dict[str, Any]:
    symbol = _symbol(member.get("symbol"))
    if company is None:
        raise ManagerScreeningError(f"company snapshot is missing: {symbol}")
    if company.get("symbol") != symbol:
        raise ManagerScreeningError(f"company snapshot identity mismatch: {symbol}")
    facts = company.get("manager_screen_facts")
    _require_fresh_quote_policy(
        facts=facts,
        symbol=symbol,
        frozen_at=frozen_at,
    )
    if require_fact_snapshot:
        if not isinstance(facts, Mapping):
            raise ManagerScreeningError(
                f"manager-screen fact snapshot is missing: {symbol}"
            )
        annuals = facts.get("annuals")
        if not isinstance(annuals, list):
            raise ManagerScreeningError(
                f"manager-screen annual facts are invalid: {symbol}"
            )
        facts = dict(facts)
        facts["annual_history_complete"] = len(annuals) >= minimum_annual_periods
    prior_screening = (
        {key: screening.get(key) for key in SCREEN_FIELDS} if screening is not None else None
    )
    prior_queue = {key: queue.get(key) for key in QUEUE_FIELDS} if queue is not None else None
    ticker = symbol.split(":", 1)[1]
    meta_path = repository_root / "research" / "companies" / "CN" / ticker / "meta.json"
    timeline = _timeline_summary(meta_path, symbol=symbol)
    market_snapshot = {key: company.get(key) for key in MARKET_FIELDS}
    if isinstance(facts, Mapping):
        facts = dict(facts)
        if decision_contract_version == 2:
            facts["decision_support"] = build_decision_support(
                symbol=symbol,
                name=_text(member.get("name"), "member name"),
                market_snapshot=market_snapshot,
                facts=facts,
                prior_screening=prior_screening,
                timeline=timeline,
                high_liability_to_assets_pct=high_liability_to_assets_pct,
            )
        market_snapshot["manager_screen_facts"] = facts
    evidence_catalog = [
        {
            "evidence_id": f"snapshot:{symbol}",
            "kind": "market_snapshot",
            "path": _relative(company_snapshot_path, repository_root),
            "as_of": company.get("as_of"),
        }
    ]
    if quote_amendment is not None:
        evidence_catalog.append(
            {
                "evidence_id": f"quote-amendment:{quote_amendment['amendment_id']}",
                "kind": "market_quote_amendment",
                "path": quote_amendment["path"],
                "as_of": quote_amendment["effective_at"],
            }
        )
    if screening is not None:
        evidence_catalog.append(
            {
                "evidence_id": f"screening:{symbol}",
                "kind": "prior_screening",
                "path": "coverage/cn-a/screening.jsonl",
                "as_of": None,
            }
        )
    if queue is not None:
        evidence_catalog.append(
            {
                "evidence_id": f"queue:{symbol}",
                "kind": "prior_queue",
                "path": "coverage/cn-a/research_queue.jsonl",
                "as_of": None,
            }
        )
    if timeline["available"]:
        evidence_catalog.append(
            {
                "evidence_id": f"timeline:{symbol}",
                "kind": "company_timeline",
                "path": _relative(meta_path, repository_root),
                "as_of": timeline.get("information_cutoff"),
            }
        )
    return {
        "batch_ordinal": member["batch_ordinal"],
        "scope_ordinal": member["scope_ordinal"],
        "symbol": symbol,
        "name": member["name"],
        "market_snapshot": market_snapshot,
        "prior_screening": prior_screening,
        "prior_queue": prior_queue,
        "timeline": timeline,
        "evidence_catalog": evidence_catalog,
    }


def _require_fresh_quote_policy(
    *,
    facts: Any,
    symbol: str,
    frozen_at: dt.datetime,
) -> None:
    if not isinstance(facts, Mapping):
        raise ManagerScreeningError(
            f"manager-screen quote freshness policy is missing: {symbol}"
        )
    freshness = facts.get("quote_freshness")
    if not isinstance(freshness, Mapping):
        raise ManagerScreeningError(
            f"manager-screen quote freshness policy is missing: {symbol}"
        )
    if freshness.get("schema_version") != 1 or freshness.get("status") != "fresh":
        raise ManagerScreeningError(
            f"manager-screen quote freshness state is invalid: {symbol}"
        )
    max_age = _positive_int(
        freshness.get("max_age_seconds"),
        f"{symbol}.quote_freshness.max_age_seconds",
    )
    future_tolerance = _positive_int(
        freshness.get("future_tolerance_seconds"),
        f"{symbol}.quote_freshness.future_tolerance_seconds",
    )
    quote_as_of = _parse_datetime(
        freshness.get("quote_as_of"),
        f"{symbol}.quote_freshness.quote_as_of",
    )
    age = frozen_at - quote_as_of
    if age > dt.timedelta(seconds=max_age):
        raise ManagerScreeningError(
            f"manager-screen quote is stale at batch freeze: {symbol} "
            f"({quote_as_of.isoformat()}, max_age={max_age}s)"
        )
    if -age > dt.timedelta(seconds=future_tolerance):
        raise ManagerScreeningError(
            f"manager-screen quote is after batch freeze: {symbol}"
        )


def _timeline_summary(path: Path, *, symbol: str) -> dict[str, Any]:
    if not path.is_file():
        return {"available": False, "status": "missing"}
    try:
        meta = _read_object(path)
    except (OSError, json.JSONDecodeError, ManagerScreeningError):
        return {"available": False, "status": "invalid"}
    if meta.get("identity", {}).get("symbol") != symbol:
        return {"available": False, "status": "identity_mismatch"}
    research = meta.get("research") if isinstance(meta.get("research"), Mapping) else {}
    reports = meta.get("reports") if isinstance(meta.get("reports"), Mapping) else {}
    return {
        "available": True,
        "status": "ok",
        "updated_at": meta.get("updated_at"),
        "coverage_status": research.get("coverage_status"),
        "information_cutoff": research.get("information_cutoff"),
        "rebaseline_required": research.get("rebaseline_required"),
        "latest_report": reports.get("latest"),
        "latest_by_type": reports.get("latest_by_type"),
        "underwriting": meta.get("underwriting"),
        "valuation": meta.get("valuation"),
        "active_triggers": [
            item
            for item in (meta.get("triggers") or [])
            if isinstance(item, Mapping) and item.get("active") is not False
        ],
    }


def _normalize_submission(
    submission: Mapping[str, Any],
    *,
    batch: Mapping[str, Any],
    packet: Mapping[str, Any],
    recorded_at: dt.datetime,
) -> dict[str, Any]:
    if not isinstance(submission, Mapping) or set(submission) != SUBMISSION_KEYS:
        raise ManagerScreeningError(
            "manager-screen submission fields do not match the v1 contract"
        )
    if submission.get("schema_version") != 1:
        raise ManagerScreeningError("manager-screen submission schema_version must be 1")
    manager = _validate_manager(submission.get("manager"))
    additional = _validate_additional_evidence(
        submission.get("additional_evidence"),
        batch=batch,
        recorded_at=recorded_at,
    )
    decisions = _validate_decisions(
        submission.get("decisions"),
        batch=batch,
        packet=packet,
        additional_evidence=additional,
    )
    return {
        "manager": manager,
        "additional_evidence": additional,
        "decisions": decisions,
    }


def _validate_manager(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != MANAGER_KEYS:
        raise ManagerScreeningError("manager provenance fields do not match the contract")
    tools = value.get("tools")
    if (
        not isinstance(tools, list)
        or not tools
        or not all(isinstance(item, str) and item.strip() for item in tools)
    ):
        raise ManagerScreeningError("manager.tools must be a non-empty string array")
    return {
        "agent": _text(value.get("agent"), "manager.agent"),
        "model": _text(value.get("model"), "manager.model"),
        "tools": [item.strip() for item in tools],
    }


def _validate_additional_evidence(
    value: Any,
    *,
    batch: Mapping[str, Any],
    recorded_at: dt.datetime,
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ManagerScreeningError("additional_evidence must be an array")
    symbols = {member["symbol"] for member in batch["members"]}
    seen: set[str] = set()
    result = []
    for item in value:
        if not isinstance(item, Mapping) or set(item) != EXTERNAL_EVIDENCE_KEYS:
            raise ManagerScreeningError(
                "additional evidence fields do not match the v1 contract"
            )
        evidence_id = _text(item.get("evidence_id"), "additional evidence id")
        if not evidence_id.startswith("external:") or not EVIDENCE_ID_RE.fullmatch(evidence_id):
            raise ManagerScreeningError(
                "additional evidence id must use the external: prefix"
            )
        if evidence_id in seen:
            raise ManagerScreeningError(f"duplicate additional evidence id: {evidence_id}")
        seen.add(evidence_id)
        symbol = _symbol(item.get("symbol"))
        if symbol not in symbols:
            raise ManagerScreeningError(
                f"additional evidence symbol is outside batch: {symbol}"
            )
        source_type = item.get("source_type")
        if source_type not in EXTERNAL_SOURCE_TYPES:
            raise ManagerScreeningError(
                f"invalid additional evidence source_type: {source_type}"
            )
        accessed = _parse_datetime(item.get("accessed_at"), "evidence accessed_at")
        if accessed > recorded_at:
            raise ManagerScreeningError("evidence accessed_at cannot be in the future")
        result.append(
            {
                "evidence_id": evidence_id,
                "symbol": symbol,
                "source_type": source_type,
                "title": _text(item.get("title"), "additional evidence title"),
                "url": _text(item.get("url"), "additional evidence url"),
                "accessed_at": accessed.isoformat(),
            }
        )
    return result


def _validate_decisions(
    value: Any,
    *,
    batch: Mapping[str, Any],
    packet: Mapping[str, Any],
    additional_evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ManagerScreeningError("decisions must be an array")
    expected = [member["symbol"] for member in batch["members"]]
    received = [item.get("symbol") for item in value if isinstance(item, Mapping)]
    if received != expected or len(value) != len(expected):
        raise ManagerScreeningError(
            "decisions must cover the complete batch exactly once and in batch order"
        )
    dossier_by_symbol = {item["symbol"]: item for item in packet["dossiers"]}
    external_by_symbol: dict[str, set[str]] = {}
    for item in additional_evidence:
        external_by_symbol.setdefault(item["symbol"], set()).add(item["evidence_id"])
    reason_max = batch["policy"]["one_line_reason_max_chars"]
    question_max = batch["policy"]["decisive_question_max_chars"]
    decision_v2 = batch["policy"].get("decision_contract_version") == 2
    decision_keys = DECISION_V2_KEYS if decision_v2 else DECISION_KEYS
    normalized = []
    for item in value:
        if not isinstance(item, Mapping) or set(item) != decision_keys:
            raise ManagerScreeningError(
                "decision fields do not match the sealed manager-screen contract"
            )
        symbol = _symbol(item.get("symbol"))
        route = item.get("route")
        if route not in ROUTES:
            raise ManagerScreeningError(f"invalid manager-screen route: {route}")
        reason = _text(item.get("one_line_reason"), f"{symbol}.one_line_reason")
        if "\n" in reason or "\r" in reason or len(reason) > reason_max:
            raise ManagerScreeningError(
                f"{symbol}.one_line_reason must be one line and at most {reason_max} chars"
            )
        question = _text(item.get("decisive_question"), f"{symbol}.decisive_question")
        if len(question) > question_max:
            raise ManagerScreeningError(
                f"{symbol}.decisive_question exceeds {question_max} chars"
            )
        triggers = _validate_triggers(item.get("revisit_triggers"), symbol=symbol)
        if route in {"pass", "watch"} and not triggers:
            raise ManagerScreeningError(
                f"{route} decision requires at least one revisit trigger: {symbol}"
            )
        confidence = item.get("confidence")
        if confidence not in CONFIDENCES:
            raise ManagerScreeningError(f"invalid confidence for {symbol}: {confidence}")
        evidence_ids = item.get("evidence_ids")
        if (
            not isinstance(evidence_ids, list)
            or not evidence_ids
            or not all(isinstance(entry, str) and entry for entry in evidence_ids)
            or len(evidence_ids) != len(set(evidence_ids))
        ):
            raise ManagerScreeningError(
                f"{symbol}.evidence_ids must be a non-empty unique string array"
            )
        local_ids = {
            evidence["evidence_id"]
            for evidence in dossier_by_symbol[symbol]["evidence_catalog"]
        }
        allowed = local_ids | external_by_symbol.get(symbol, set())
        unknown = sorted(set(evidence_ids) - allowed)
        if unknown:
            raise ManagerScreeningError(
                f"{symbol} cites evidence outside its dossier: {unknown}"
            )
        normalized_decision = {
            "symbol": symbol,
            "route": route,
            "one_line_reason": reason,
            "decisive_question": question,
            "revisit_triggers": triggers,
            "confidence": confidence,
            "evidence_ids": list(evidence_ids),
        }
        if decision_v2:
            facts = dossier_by_symbol[symbol]["market_snapshot"].get(
                "manager_screen_facts"
            )
            support = facts.get("decision_support") if isinstance(facts, Mapping) else None
            try:
                validate_canonical_reason(reason, support)
                normalized_decision["risk_acknowledgements"] = (
                    validate_risk_acknowledgements(
                        item.get("risk_acknowledgements"),
                        support=support,
                        decision_evidence_ids=evidence_ids,
                        one_line_reason=reason,
                        decisive_question=question,
                    )
                )
            except ManagerScreenDecisionQualityError as exc:
                raise ManagerScreeningError(
                    f"manager-screen decision v2 is invalid: {symbol}: {exc}"
                ) from exc
        normalized.append(normalized_decision)
    return normalized


def _validate_triggers(value: Any, *, symbol: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ManagerScreeningError(f"{symbol}.revisit_triggers must be an array")
    result = []
    for item in value:
        if not isinstance(item, Mapping) or set(item) != TRIGGER_KEYS:
            raise ManagerScreeningError(
                f"{symbol} revisit trigger fields do not match the contract"
            )
        trigger_type = item.get("type")
        if trigger_type not in TRIGGER_TYPES:
            raise ManagerScreeningError(
                f"invalid revisit trigger type for {symbol}: {trigger_type}"
            )
        condition = item.get("condition")
        if isinstance(condition, str):
            condition = _text(condition, f"{symbol}.trigger.condition")
        elif isinstance(condition, Mapping):
            condition = dict(condition)
            if not condition:
                raise ManagerScreeningError(
                    f"{symbol}.trigger.condition must not be empty"
                )
        else:
            raise ManagerScreeningError(
                f"{symbol}.trigger.condition must be a string or object"
            )
        result.append(
            {
                "type": trigger_type,
                "condition": condition,
                "reason": _text(item.get("reason"), f"{symbol}.trigger.reason"),
            }
        )
    return result


def _materialize_decisions(
    *,
    base: Path,
    repository_root: Path,
    batch: Mapping[str, Any],
    result: Mapping[str, Any],
    result_path: Path,
    result_sha256: str,
) -> None:
    queue_path = base / RESEARCH_QUEUE_FILE
    screening_path = base / SCREENING_FILE
    queue = _unique_by_symbol(read_jsonl(queue_path), "research queue")
    screening = _unique_by_symbol(read_jsonl(screening_path), "screening")
    members = {member["symbol"]: member for member in batch["members"]}
    result_relative = _relative(result_path, repository_root)
    queue_changed = False
    screening_changed = False
    decision_map = {
        "pass": ("catalog", "等待重启条件，不购买新的单公司研究时间。"),
        "watch": ("watch_only", "按价格、财报、事件或关键证据触发器重新评估。"),
        "send_to_analyst": ("quick_profile", "交给一名研究员解决决定性问题。"),
    }
    for decision in result["decisions"]:
        symbol = decision["symbol"]
        current = queue.get(symbol)
        already_materialized = (
            current is not None
            and current.get("manager_screen_result_path") == result_relative
            and current.get("manager_screen_result_sha256") == result_sha256
            and current.get("manager_screen_route") == decision["route"]
        )
        later_progress = bool(
            already_materialized
            and current is not None
            and current.get("task_type") in PROTECTED_TASK_TYPES
            and not (
                current.get("task_type") == "quick_profile"
                and current.get("status") == "pending"
                and current.get("assigned_agent") is None
            )
        )
        if not already_materialized and current is not None and (
            current.get("status") == "running"
            or current.get("task_type") in PROTECTED_TASK_TYPES
        ):
            raise ManagerScreeningError(
                f"coverage advanced after batch freeze; refusing to overwrite {symbol}"
            )
        if not already_materialized:
            updated = dict(current or {})
            history = list(updated.get("stage_history") or [])
            event = {
                "stage": "manager_screen",
                "status": "completed",
                "finished_at": result["recorded_at"],
                "run_id": batch["run_id"],
                "batch_id": batch["batch_id"],
                "route": decision["route"],
                "result_path": result_relative,
                "result_sha256": result_sha256,
            }
            if not any(
                isinstance(item, Mapping)
                and item.get("stage") == "manager_screen"
                and item.get("result_sha256") == result_sha256
                for item in history
            ):
                history.append(event)
            updated.update(
                {
                    "symbol": symbol,
                    "name": members[symbol]["name"],
                    "priority": 3,
                    "reason": decision["one_line_reason"],
                    "target_company_dir": (
                        f"research/companies/CN/{symbol.split(':', 1)[1]}"
                    ),
                    "assigned_agent": None,
                    "started_at": None,
                    "finished_at": (
                        None
                        if decision["route"] == "send_to_analyst"
                        else result["recorded_at"]
                    ),
                    "failure_reason": None,
                    "manager_screen_run_id": batch["run_id"],
                    "manager_screen_batch_id": batch["batch_id"],
                    "manager_screen_route": decision["route"],
                    "manager_screen_result_path": result_relative,
                    "manager_screen_result_sha256": result_sha256,
                    "decisive_question": decision["decisive_question"],
                    "revisit_triggers": decision["revisit_triggers"],
                    "evidence_ids": decision["evidence_ids"],
                    "stage_history": history,
                }
            )
            if decision["route"] == "send_to_analyst":
                updated.update(
                    {
                        "task_type": "quick_profile",
                        "status": "pending",
                        "result_path": None,
                        "next_action": (
                            "由一名研究员只解决 manager-screen 的决定性问题；"
                            "深研后再购买独立承保。"
                        ),
                        "effort_budget_hours": batch["policy"][
                            "quick_profile_effort_budget_hours"
                        ],
                        "preceding_stage": "manager_screen",
                        "stop_conditions": list(
                            batch["policy"]["quick_profile_stop_conditions"]
                        ),
                    }
                )
            else:
                updated.update(
                    {
                        "task_type": "manager_screen",
                        "status": "completed",
                        "result_path": result_relative,
                        "next_action": decision_map[decision["route"]][1],
                    }
                )
                for stale in (
                    "effort_budget_hours",
                    "preceding_stage",
                    "stop_conditions",
                ):
                    updated.pop(stale, None)
            for stale in (
                "allocation_sha256",
                "selected_by",
                "profile_cycle_id",
                "profile_evaluation_path",
                "profile_recorded_at",
                "profile_quick_selection_path",
                "profile_scoped_selection_path",
                "profile_priority_score",
                "triage_priority_score",
                "triage_allocation_decision",
                "triage_selection_reason",
                "triage_review_mode",
                "triage_cycle_id",
                "triage_disposition",
                "triage_selection_path",
                "triage_selection_sha256",
                "cohort_path",
                "cohort_sha256",
                "cohort_ordinal",
            ):
                updated.pop(stale, None)
            queue[symbol] = updated
            queue_changed = True

        existing_screen = screening.get(symbol)
        if not later_progress and (
            existing_screen is None
            or existing_screen.get("manager_screen_result_path")
            in {None, result_relative}
        ):
            screen = {
                "symbol": symbol,
                "name": members[symbol]["name"],
                "decision": decision_map[decision["route"]][0],
                "priority": None,
                "reason": decision["one_line_reason"],
                "evidence": decision["evidence_ids"],
                "next_action": decision_map[decision["route"]][1],
                "manager_screen_run_id": batch["run_id"],
                "manager_screen_batch_id": batch["batch_id"],
                "manager_screen_route": decision["route"],
                "manager_screen_result_path": result_relative,
                "manager_screen_result_sha256": result_sha256,
                "decisive_question": decision["decisive_question"],
                "confidence": decision["confidence"],
                "revisit_triggers": decision["revisit_triggers"],
            }
            if screen != existing_screen:
                screening[symbol] = screen
                screening_changed = True
    if queue_changed:
        write_jsonl(queue_path, list(queue.values()))
    if screening_changed:
        write_jsonl(screening_path, list(screening.values()))


def _manager_batch_dirs(run_dir: Path) -> list[Path]:
    """Return only ordinary manager-screen batch directories.

    The run directory may also contain one-time transition or governance
    assets. Those have their own validators and must not be parsed as batches.
    """

    return sorted(
        path
        for path in run_dir.iterdir()
        if path.is_dir()
        and (
            (path / "batch.json").exists()
            or (path / "batch.json.seal.json").exists()
            or (path / "freeze-journal.json").exists()
            or (path / "freeze-journal.json.seal.json").exists()
        )
    )


def _verify_batch_reservation(
    batch_dir: Path,
    *,
    repository_root: Path,
) -> dict[str, Any]:
    """Read either a committed batch or its sealed crash-recovery reservation."""

    batch_path = batch_dir / "batch.json"
    packet_path = batch_dir / "packet.json"
    complete = all(
        path.is_file()
        for path in (
            batch_path,
            batch_path.with_name(f"{batch_path.name}.seal.json"),
            packet_path,
            packet_path.with_name(f"{packet_path.name}.seal.json"),
        )
    )
    if complete:
        return _verify_batch_dir(batch_dir, repository_root=repository_root)
    journal, _ = _load_freeze_journal(
        batch_dir,
        repository_root=repository_root,
    )
    return {
        "batch": journal["batch"],
        "packet": journal["packet"],
        "result": None,
        "result_seal": None,
        "supersession": None,
        "freeze_incomplete": True,
    }


def _load_freeze_journal(
    batch_dir: Path,
    *,
    repository_root: Path,
) -> tuple[dict[str, Any], Any]:
    journal_path = batch_dir / "freeze-journal.json"
    try:
        sealed = verify_sealed(journal_path)
        journal = _read_object(journal_path)
    except (OSError, SealingError, json.JSONDecodeError) as exc:
        raise ManagerScreeningError(
            f"manager-screen freeze journal is not validly sealed: {batch_dir}"
        ) from exc
    if sealed.artifact_type != "manager_screen_freeze_journal":
        raise ManagerScreeningError(
            "manager-screen freeze journal has an unexpected artifact type"
        )
    _validate_freeze_journal(
        journal,
        batch_dir=batch_dir,
        repository_root=repository_root,
    )
    return journal, sealed


def _validate_freeze_journal(
    journal: Mapping[str, Any],
    *,
    batch_dir: Path,
    repository_root: Path,
) -> None:
    if (
        not isinstance(journal, Mapping)
        or set(journal) != FREEZE_JOURNAL_KEYS
        or journal.get("schema_version") != 1
        or journal.get("portfolio_action") is not None
    ):
        raise ManagerScreeningError(
            "manager-screen freeze journal fields do not match v1"
        )
    batch = journal.get("batch")
    packet = journal.get("packet")
    if not isinstance(batch, Mapping) or not isinstance(packet, Mapping):
        raise ManagerScreeningError("manager-screen freeze journal payload is invalid")
    _validate_batch(batch)
    batch_sha256 = hashlib.sha256(canonical_json_bytes(batch)).hexdigest()
    packet_sha256 = hashlib.sha256(canonical_json_bytes(packet)).hexdigest()
    if (
        journal.get("run_id") != batch.get("run_id")
        or journal.get("batch_id") != batch.get("batch_id")
        or batch_dir.parent.name != batch.get("run_id")
        or batch_dir.name != batch.get("batch_id")
        or journal.get("created_at") != batch.get("frozen_at")
        or journal.get("batch_sha256") != batch_sha256
        or journal.get("packet_sha256") != packet_sha256
        or packet.get("batch_path")
        != _relative(batch_dir / "batch.json", repository_root)
    ):
        raise ManagerScreeningError(
            "manager-screen freeze journal identity or SHA binding is invalid"
        )
    _validate_packet(packet, batch=batch, batch_sha256=batch_sha256)


def _repair_manager_screen_freeze(
    batch_dir: Path,
    *,
    repository_root: Path,
) -> dict[str, Any]:
    journal, _ = _load_freeze_journal(
        batch_dir,
        repository_root=repository_root,
    )
    frozen_at = _parse_datetime(journal["created_at"], "freeze journal created_at")
    batch_seal = seal_json(
        batch_dir / "batch.json",
        journal["batch"],
        artifact_type="manager_screen_batch",
        sealed_at=frozen_at,
    )
    if batch_seal.sha256 != journal["batch_sha256"]:
        raise ManagerScreeningError(
            "repaired manager-screen batch diverges from freeze journal"
        )
    packet_seal = seal_json(
        batch_dir / "packet.json",
        journal["packet"],
        artifact_type="manager_screen_packet",
        sealed_at=frozen_at,
    )
    if packet_seal.sha256 != journal["packet_sha256"]:
        raise ManagerScreeningError(
            "repaired manager-screen packet diverges from freeze journal"
        )
    verified = _verify_batch_dir(batch_dir, repository_root=repository_root)
    _discard_freeze_journal(batch_dir)
    return verified


def _discard_freeze_journal(batch_dir: Path) -> None:
    journal_path = batch_dir / "freeze-journal.json"
    journal_seal_path = journal_path.with_name(f"{journal_path.name}.seal.json")
    journal_seal_path.unlink(missing_ok=True)
    journal_path.unlink(missing_ok=True)


def _verify_batch_dir(
    batch_dir: Path,
    *,
    repository_root: Path,
    require_result: bool = False,
) -> dict[str, Any]:
    batch_path = batch_dir / "batch.json"
    packet_path = batch_dir / "packet.json"
    result_path = batch_dir / "result.json"
    try:
        batch_seal = verify_sealed(batch_path)
        packet_seal = verify_sealed(packet_path)
    except (OSError, SealingError) as exc:
        raise ManagerScreeningError(
            f"manager-screen batch or packet is not validly sealed: {batch_dir}"
        ) from exc
    if batch_seal.artifact_type != "manager_screen_batch":
        raise ManagerScreeningError("manager-screen batch has an unexpected artifact type")
    if packet_seal.artifact_type != "manager_screen_packet":
        raise ManagerScreeningError("manager-screen packet has an unexpected artifact type")
    batch = _read_object(batch_path)
    packet = _read_object(packet_path)
    _validate_batch(batch)
    _verify_bound_quote_amendment(
        batch=batch,
        repository_root=repository_root,
    )
    _validate_packet(packet, batch=batch, batch_sha256=batch_seal.sha256)
    if batch_dir.name != batch["batch_id"] or batch_dir.parent.name != batch["run_id"]:
        raise ManagerScreeningError(
            "manager-screen directory does not match sealed run and batch identity"
        )
    expected_batch_path = _relative(batch_path, repository_root)
    expected_packet_path = _relative(packet_path, repository_root)
    if packet.get("batch_path") != expected_batch_path:
        raise ManagerScreeningError(
            "manager-screen packet path does not bind the sealed batch file"
        )
    result = None
    result_seal = None
    if result_path.exists():
        try:
            result_seal = verify_sealed(result_path)
        except (OSError, SealingError) as exc:
            raise ManagerScreeningError(
                f"manager-screen result is not validly sealed: {result_path}"
            ) from exc
        if result_seal.artifact_type != "manager_screen_result":
            raise ManagerScreeningError(
                "manager-screen result has an unexpected artifact type"
            )
        result = _read_object(result_path)
        _validate_result(
            result,
            batch=batch,
            packet=packet,
            batch_sha256=batch_seal.sha256,
            packet_sha256=packet_seal.sha256,
        )
        if (
            result.get("batch_path") != expected_batch_path
            or result.get("packet_path") != expected_packet_path
        ):
            raise ManagerScreeningError(
                "manager-screen result paths do not bind the sealed input files"
            )
    elif require_result:
        raise ManagerScreeningError(f"manager-screen result is missing: {result_path}")
    try:
        supersession = load_manager_screen_supersession(
            batch_dir=batch_dir,
            repository_root=repository_root,
        )
    except ManagerScreenGovernanceError as exc:
        raise ManagerScreeningError(
            f"manager-screen supersession is invalid: {batch_dir}"
        ) from exc
    if supersession is not None and result is not None:
        raise ManagerScreeningError(
            "manager-screen batch cannot have both a result and a supersession"
        )
    return {
        "batch_path": batch_path,
        "batch": batch,
        "batch_seal": batch_seal,
        "packet_path": packet_path,
        "packet": packet,
        "packet_seal": packet_seal,
        "result_path": result_path,
        "result": result,
        "result_seal": result_seal,
        "supersession": supersession,
    }


def _verify_bound_quote_amendment(
    *,
    batch: Mapping[str, Any],
    repository_root: Path,
) -> None:
    reference = batch.get("quote_amendment")
    if reference is None:
        return
    path = (repository_root / reference["path"]).resolve()
    try:
        path.relative_to(repository_root.resolve())
    except ValueError as exc:
        raise ManagerScreeningError(
            "bound manager-screen quote amendment is outside the repository"
        ) from exc
    try:
        seal = verify_sealed(path)
        payload = _read_object(path)
    except (OSError, SealingError, json.JSONDecodeError) as exc:
        raise ManagerScreeningError(
            f"bound manager-screen quote amendment is invalid: {path}"
        ) from exc
    if (
        seal.artifact_type != "manager_screen_quote_amendment"
        or seal.sha256 != reference["sha256"]
        or payload.get("run_id") != batch["run_id"]
        or payload.get("amendment_id") != reference["amendment_id"]
        or payload.get("effective_at") != reference["effective_at"]
        or payload.get("base_snapshot_sha256")
        != reference["base_snapshot_sha256"]
    ):
        raise ManagerScreeningError(
            "manager-screen batch quote amendment binding is invalid"
        )
    base_path = (repository_root / payload["base_snapshot_path"]).resolve()
    try:
        base_path.relative_to(repository_root.resolve())
    except ValueError as exc:
        raise ManagerScreeningError(
            "quote amendment base snapshot is outside the repository"
        ) from exc
    base_symbols = {
        _symbol(item.get("symbol"))
        for item in read_jsonl(base_path)
    }
    _validate_quote_amendment_payload(
        payload,
        run_id=batch["run_id"],
        base_snapshot_path=base_path,
        base_snapshot_sha256=hashlib.sha256(base_path.read_bytes()).hexdigest(),
        base_symbols=base_symbols,
        repository_root=repository_root,
    )


def _validate_batch(batch: Mapping[str, Any]) -> None:
    if (
        set(batch) not in (LEGACY_BATCH_KEYS, BATCH_KEYS)
        or batch.get("schema_version") != 1
    ):
        raise ManagerScreeningError("manager-screen batch fields do not match v1")
    _identifier(batch.get("run_id"), "run_id")
    _identifier(batch.get("batch_id"), "batch_id")
    frozen = _parse_datetime(batch.get("frozen_at"), "batch frozen_at")
    cutoff = _parse_datetime(batch.get("information_cutoff"), "batch cutoff")
    if frozen < cutoff:
        raise ManagerScreeningError("batch frozen_at cannot be before cutoff")
    if batch.get("portfolio_action") is not None:
        raise ManagerScreeningError("manager-screen batch cannot contain portfolio action")
    scope = batch.get("scope")
    if not isinstance(scope, Mapping) or set(scope) != SCOPE_REF_KEYS:
        raise ManagerScreeningError("manager-screen scope reference is invalid")
    for key in ("manifest_sha256", "baseline_intake_sha256"):
        _sha256(scope.get(key), f"scope.{key}")
    quote_amendment = batch.get("quote_amendment")
    if quote_amendment is not None:
        if (
            not isinstance(quote_amendment, Mapping)
            or set(quote_amendment) != QUOTE_AMENDMENT_REF_KEYS
        ):
            raise ManagerScreeningError(
                "manager-screen quote amendment reference is invalid"
            )
        _identifier(
            quote_amendment.get("amendment_id"),
            "quote amendment id",
        )
        amendment_path = _text(
            quote_amendment.get("path"),
            "quote amendment path",
        )
        if Path(amendment_path).is_absolute():
            raise ManagerScreeningError(
                "quote amendment path must be repository-relative"
            )
        _sha256(quote_amendment.get("sha256"), "quote amendment sha256")
        _sha256(
            quote_amendment.get("base_snapshot_sha256"),
            "quote amendment base snapshot sha256",
        )
        effective = _parse_datetime(
            quote_amendment.get("effective_at"),
            "quote amendment effective_at",
        )
        if effective > frozen:
            raise ManagerScreeningError(
                "quote amendment cannot become effective after batch freeze"
            )
    policy = batch.get("policy")
    if (
        not isinstance(policy, Mapping)
        or set(policy)
        not in (
            LEGACY_POLICY_REF_KEYS,
            PRE_CAPACITY_POLICY_REF_KEYS,
            PRE_CAPACITY_CONTROL_POLICY_REF_KEYS,
            POLICY_REF_KEYS,
            CONTROL_POLICY_REF_KEYS,
            POLICY_V2_REF_KEYS,
            POLICY_V2_CONTROL_REF_KEYS,
        )
    ):
        raise ManagerScreeningError("manager-screen policy reference is invalid")
    for key in ("file_sha256", "payload_sha256"):
        _sha256(policy.get(key), f"policy.{key}")
    if _has_calibration_policy(policy):
        validation_rate = policy.get("programmatic_validation_rate")
        sample_rate = policy.get("calibration_sample_rate")
        if validation_rate != 1.0:
            raise ManagerScreeningError(
                "sealed manager-screen programmatic validation rate is invalid"
            )
        if (
            isinstance(sample_rate, bool)
            or not isinstance(sample_rate, (int, float))
            or not 0 < float(sample_rate) <= 1
        ):
            raise ManagerScreeningError(
                "sealed manager-screen calibration sample rate is invalid"
            )
        _positive_int(
            policy.get("calibration_minimum_per_batch"),
            "policy.calibration_minimum_per_batch",
        )
        if (
            set(policy.get("calibration_material_error_types") or [])
            != CALIBRATION_ERROR_TYPES
            or policy.get("route_disagreement_is_material_error") is not False
        ):
            raise ManagerScreeningError(
                "sealed manager-screen calibration contract is invalid"
            )
    if "send_to_analyst_capacity_per_run" in policy:
        _positive_int(
            policy.get("send_to_analyst_capacity_per_run"),
            "policy.send_to_analyst_capacity_per_run",
        )
    if "run_control_required" in policy and policy.get("run_control_required") is not True:
        raise ManagerScreeningError(
            "sealed manager-screen run-control requirement is invalid"
        )
    if DECISION_V2_POLICY_REF_KEYS.intersection(policy):
        if (
            not DECISION_V2_POLICY_REF_KEYS.issubset(policy)
            or policy.get("decision_contract_version") != 2
            or policy.get("mandatory_risk_acknowledgement") is not True
            or policy.get("canonical_fact_line_required") is not True
        ):
            raise ManagerScreeningError(
                "sealed manager-screen decision v2 contract is invalid"
            )
        liability_threshold = policy.get("high_liability_to_assets_pct")
        if (
            isinstance(liability_threshold, bool)
            or not isinstance(liability_threshold, (int, float))
            or not math.isfinite(float(liability_threshold))
            or not 0 < float(liability_threshold) <= 100
        ):
            raise ManagerScreeningError(
                "sealed manager-screen high-liability threshold is invalid"
            )
    requested = _positive_int(batch.get("requested_batch_size"), "requested_batch_size")
    if not policy["minimum_batch_size"] <= requested <= policy["maximum_batch_size"]:
        raise ManagerScreeningError("requested batch size violates sealed policy")
    members = batch.get("members")
    if not isinstance(members, list) or not members:
        raise ManagerScreeningError("manager-screen batch members must not be empty")
    if batch.get("member_count") != len(members) or len(members) > requested:
        raise ManagerScreeningError("manager-screen member count is invalid")
    symbols = []
    scope_ordinals = []
    for ordinal, member in enumerate(members, 1):
        if (
            not isinstance(member, Mapping)
            or set(member) != MEMBER_KEYS
            or member.get("batch_ordinal") != ordinal
        ):
            raise ManagerScreeningError("manager-screen member fields or ordinal are invalid")
        symbols.append(_symbol(member.get("symbol")))
        scope_ordinals.append(_positive_int(member.get("scope_ordinal"), "scope ordinal"))
        _text(member.get("name"), "member name")
    if len(symbols) != len(set(symbols)) or scope_ordinals != sorted(scope_ordinals):
        raise ManagerScreeningError(
            "manager-screen members must be unique and scope-ordinal sorted"
        )


def _validate_packet(
    packet: Mapping[str, Any],
    *,
    batch: Mapping[str, Any],
    batch_sha256: str,
) -> None:
    if set(packet) != PACKET_KEYS or packet.get("schema_version") != 1:
        raise ManagerScreeningError("manager-screen packet fields do not match v1")
    if (
        packet.get("run_id") != batch.get("run_id")
        or packet.get("batch_id") != batch.get("batch_id")
        or packet.get("information_cutoff") != batch.get("information_cutoff")
        or packet.get("batch_sha256") != batch_sha256
    ):
        raise ManagerScreeningError("manager-screen packet does not bind its batch")
    if packet.get("portfolio_action") is not None:
        raise ManagerScreeningError("manager-screen packet cannot contain portfolio action")
    _parse_datetime(packet.get("created_at"), "packet created_at")
    if not isinstance(packet.get("instructions"), Mapping):
        raise ManagerScreeningError("manager-screen packet instructions are invalid")
    dossiers = packet.get("dossiers")
    if not isinstance(dossiers, list) or len(dossiers) != batch["member_count"]:
        raise ManagerScreeningError("manager-screen dossier count is invalid")
    expected = [member["symbol"] for member in batch["members"]]
    received = []
    for ordinal, dossier in enumerate(dossiers, 1):
        if (
            not isinstance(dossier, Mapping)
            or set(dossier) != DOSSIER_KEYS
            or dossier.get("batch_ordinal") != ordinal
        ):
            raise ManagerScreeningError("manager-screen dossier fields are invalid")
        received.append(_symbol(dossier.get("symbol")))
        catalog = dossier.get("evidence_catalog")
        if not isinstance(catalog, list) or not catalog:
            raise ManagerScreeningError("manager-screen evidence catalog must not be empty")
        evidence_ids = [item.get("evidence_id") for item in catalog if isinstance(item, Mapping)]
        if len(evidence_ids) != len(catalog) or len(evidence_ids) != len(set(evidence_ids)):
            raise ManagerScreeningError("manager-screen evidence ids must be unique")
        if batch["policy"].get("decision_contract_version") == 2:
            market_snapshot = dossier.get("market_snapshot")
            facts = (
                market_snapshot.get("manager_screen_facts")
                if isinstance(market_snapshot, Mapping)
                else None
            )
            if not isinstance(market_snapshot, Mapping) or not isinstance(facts, Mapping):
                raise ManagerScreeningError(
                    "manager-screen decision v2 support facts are missing"
                )
            try:
                validate_decision_support(
                    facts.get("decision_support"),
                    symbol=dossier["symbol"],
                    name=_text(dossier.get("name"), "dossier name"),
                    market_snapshot=market_snapshot,
                    facts=facts,
                    prior_screening=dossier.get("prior_screening"),
                    timeline=dossier.get("timeline"),
                    high_liability_to_assets_pct=batch["policy"][
                        "high_liability_to_assets_pct"
                    ],
                )
            except ManagerScreenDecisionQualityError as exc:
                raise ManagerScreeningError(
                    f"manager-screen decision v2 support is invalid: {dossier['symbol']}: "
                    f"{exc}"
                ) from exc
    if received != expected:
        raise ManagerScreeningError("manager-screen dossier order does not match batch")


def _validate_result(
    result: Mapping[str, Any],
    *,
    batch: Mapping[str, Any],
    packet: Mapping[str, Any],
    batch_sha256: str,
    packet_sha256: str,
) -> None:
    if set(result) != RESULT_KEYS or result.get("schema_version") != 1:
        raise ManagerScreeningError("manager-screen result fields do not match v1")
    if (
        result.get("run_id") != batch.get("run_id")
        or result.get("batch_id") != batch.get("batch_id")
        or result.get("information_cutoff") != batch.get("information_cutoff")
        or result.get("batch_sha256") != batch_sha256
        or result.get("packet_sha256") != packet_sha256
    ):
        raise ManagerScreeningError("manager-screen result does not bind its inputs")
    if result.get("portfolio_action") is not None:
        raise ManagerScreeningError("manager-screen result cannot contain portfolio action")
    recorded = _parse_datetime(result.get("recorded_at"), "result recorded_at")
    if recorded < _parse_datetime(batch.get("frozen_at"), "batch frozen_at"):
        raise ManagerScreeningError("manager-screen result predates batch")
    manager = _validate_manager(result.get("manager"))
    additional = _validate_additional_evidence(
        result.get("additional_evidence"),
        batch=batch,
        recorded_at=recorded,
    )
    decisions = _validate_decisions(
        result.get("decisions"),
        batch=batch,
        packet=packet,
        additional_evidence=additional,
    )
    if manager != result.get("manager") or additional != result.get("additional_evidence"):
        raise ManagerScreeningError("manager-screen result is not normalized")
    if decisions != result.get("decisions"):
        raise ManagerScreeningError("manager-screen decisions are not normalized")
    quality = result.get("quality_state")
    if (
        not isinstance(quality, Mapping)
        or quality.get("contract_validation") != "passed"
        or quality.get("route_disagreement_is_material_error") is not False
        or quality.get("recursive_correction") != "forbidden"
    ):
        raise ManagerScreeningError("manager-screen quality state is invalid")
    calibration = quality.get("calibration")
    if _has_calibration_policy(batch["policy"]):
        if calibration != _calibration_plan(batch):
            raise ManagerScreeningError(
                "manager-screen calibration plan does not match sealed policy"
            )
    elif calibration is not None:
        raise ManagerScreeningError(
            "legacy manager-screen result cannot add an unbound calibration plan"
        )


def _freeze_summary(
    verified: Mapping[str, Any],
    *,
    repository_root: Path,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "run_id": verified["batch"]["run_id"],
        "batch_id": verified["batch"]["batch_id"],
        "member_count": verified["batch"]["member_count"],
        "batch_path": _relative(verified["batch_path"], repository_root),
        "batch_sha256": verified["batch_seal"].sha256,
        "packet_path": _relative(verified["packet_path"], repository_root),
        "packet_sha256": verified["packet_seal"].sha256,
        "information_cutoff": verified["batch"]["information_cutoff"],
        "portfolio_action": None,
    }


def _record_summary(
    result: Mapping[str, Any],
    *,
    result_path: Path,
    result_sha256: str,
    repository_root: Path,
) -> dict[str, Any]:
    counts = Counter(decision["route"] for decision in result["decisions"])
    return {
        "schema_version": 1,
        "run_id": result["run_id"],
        "batch_id": result["batch_id"],
        "decision_count": len(result["decisions"]),
        "by_route": dict(sorted(counts.items())),
        "result_path": _relative(result_path, repository_root),
        "result_sha256": result_sha256,
        "portfolio_action": None,
    }


def _unique_by_symbol(
    rows: list[dict[str, Any]],
    label: str,
) -> dict[str, dict[str, Any]]:
    result = {}
    for row in rows:
        symbol = row.get("symbol")
        if not isinstance(symbol, str):
            continue
        if symbol in result:
            raise ManagerScreeningError(f"duplicate symbol in {label}: {symbol}")
        result[symbol] = row
    return result


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ManagerScreeningError(f"invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise ManagerScreeningError(f"JSON artifact must be an object: {path}")
    return value


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise ManagerScreeningError(f"{label} is invalid")
    return value


def _symbol(value: Any) -> str:
    if not isinstance(value, str) or not SYMBOL_RE.fullmatch(value):
        raise ManagerScreeningError(f"invalid CN symbol: {value}")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ManagerScreeningError(f"{label} must be a non-empty string")
    return value.strip()


def _positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ManagerScreeningError(f"{label} must be a positive integer")
    return value


def _sha256(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise ManagerScreeningError(f"{label} must be a lowercase SHA-256")
    return value


def _aware(value: dt.datetime, label: str) -> dt.datetime:
    if not isinstance(value, dt.datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ManagerScreeningError(f"{label} must include timezone information")
    return value


def _parse_datetime(value: Any, label: str) -> dt.datetime:
    if not isinstance(value, str):
        raise ManagerScreeningError(f"{label} must be an ISO datetime")
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise ManagerScreeningError(f"{label} must be an ISO datetime") from exc
    return _aware(parsed, label)


def _relative(path: Path, repository_root: Path) -> str:
    try:
        return path.resolve().relative_to(repository_root.resolve()).as_posix()
    except ValueError as exc:
        raise ManagerScreeningError(f"path is outside repository: {path}") from exc


def _relative_or_absolute(path: Path, repository_root: Path) -> str:
    try:
        return path.resolve().relative_to(repository_root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())
