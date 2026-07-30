from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .coverage_store import (
    COMPANIES_FILE,
    RESEARCH_QUEUE_FILE,
    SCREENING_FILE,
    read_jsonl,
    serialized_coverage_write,
    write_jsonl,
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

BATCH_KEYS = {
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
SCOPE_REF_KEYS = {
    "manifest_path",
    "manifest_sha256",
    "baseline_intake_path",
    "baseline_intake_sha256",
}
POLICY_REF_KEYS = {
    "policy_id",
    "version",
    "path",
    "file_sha256",
    "payload_sha256",
    "default_batch_size",
    "minimum_batch_size",
    "maximum_batch_size",
    "quick_profile_effort_budget_hours",
    "quick_profile_stop_conditions",
    "pass_and_watch_require_revisit_trigger",
    "recursive_correction",
    "one_line_reason_max_chars",
    "decisive_question_max_chars",
}
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
    if batch_path.exists() or packet_path.exists():
        verified = _verify_batch_dir(batch_dir, repository_root=repository_root)
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

    _require_frozen_universe_snapshot(base=base, manifest=manifest)

    already_batched: set[str] = set()
    if run_dir.is_dir():
        for other_dir in sorted(path for path in run_dir.iterdir() if path.is_dir()):
            if other_dir.name == batch_name:
                continue
            verified = _verify_batch_dir(other_dir, repository_root=repository_root)
            for member in verified["batch"]["members"]:
                symbol = member["symbol"]
                if symbol in already_batched:
                    raise ManagerScreeningError(
                        f"symbol appears in multiple manager-screen batches: {symbol}"
                    )
                already_batched.add(symbol)

    companies = _unique_by_symbol(read_jsonl(base / COMPANIES_FILE), "companies")
    screening = _unique_by_symbol(read_jsonl(base / SCREENING_FILE), "screening")
    queue = _unique_by_symbol(read_jsonl(base / RESEARCH_QUEUE_FILE), "research queue")
    candidates, _ = _candidate_members(
        intake=intake,
        queue_by_symbol=queue,
        already_batched=already_batched,
    )
    selected = candidates[:requested_size]
    if not selected:
        raise ManagerScreeningError(
            f"no unbatched manager-screen candidates remain for scope {run}"
        )

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
    batch_seal = seal_json(
        batch_path,
        batch,
        artifact_type="manager_screen_batch",
        sealed_at=frozen,
    )

    dossiers = [
        _build_dossier(
            member=member,
            company=companies.get(member["symbol"]),
            screening=screening.get(member["symbol"]),
            queue=queue.get(member["symbol"]),
            repository_root=repository_root,
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
        "batch_sha256": batch_seal.sha256,
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
    _validate_packet(packet, batch=batch, batch_sha256=batch_seal.sha256)
    packet_seal = seal_json(
        packet_path,
        packet,
        artifact_type="manager_screen_packet",
        sealed_at=frozen,
    )
    return {
        "schema_version": 1,
        "run_id": run,
        "batch_id": batch_name,
        "member_count": len(members),
        "batch_path": _relative(batch_path, repository_root),
        "batch_sha256": batch_seal.sha256,
        "packet_path": _relative(packet_path, repository_root),
        "packet_sha256": packet_seal.sha256,
        "information_cutoff": information_cutoff.isoformat(),
        "portfolio_action": None,
    }


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
    manifest_path, _, manifest_seal, intake_path, intake, intake_seal = (
        _load_scope_artifacts(base=base, run_id=run)
    )
    run_dir = base / "manager-screen" / run
    verified_batches = []
    seen: set[str] = set()
    by_route: Counter[str] = Counter()
    completed_symbols: set[str] = set()
    open_symbols: set[str] = set()
    if run_dir.is_dir():
        for candidate in sorted(path for path in run_dir.iterdir() if path.is_dir()):
            verified = _verify_batch_dir(candidate, repository_root=repository_root)
            _require_scope_binding(
                batch=verified["batch"],
                manifest_path=manifest_path,
                manifest_sha256=manifest_seal.sha256,
                intake_path=intake_path,
                intake_sha256=intake_seal.sha256,
                repository_root=repository_root,
            )
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
                for decision in result["decisions"]:
                    completed_symbols.add(decision["symbol"])
                    by_route[decision["route"]] += 1
            verified_batches.append(verified)
    if requested_batch is not None and not any(
        item["batch"]["batch_id"] == requested_batch for item in verified_batches
    ):
        raise ManagerScreeningError(f"manager-screen batch not found: {requested_batch}")

    queue = _unique_by_symbol(read_jsonl(base / RESEARCH_QUEUE_FILE), "research queue")
    remaining, deferred = _candidate_members(
        intake=intake,
        queue_by_symbol=queue,
        already_batched=seen,
    )
    displayed = [
        item
        for item in verified_batches
        if requested_batch is None or item["batch"]["batch_id"] == requested_batch
    ]
    batches = []
    for item in displayed:
        result = item.get("result")
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
                "status": "completed" if result is not None else "awaiting_manager",
                "batch_sha256": item["batch_seal"].sha256,
                "packet_sha256": item["packet_seal"].sha256,
                "result_sha256": (
                    item["result_seal"].sha256 if item.get("result_seal") is not None else None
                ),
                "manager_wall_clock_seconds": wall_clock_seconds,
            }
        )
    screenable_total = sum(
        1
        for member in intake.get("members", [])
        if member.get("materialization_action") == "normalize_queue"
    )
    return {
        "schema_version": 1,
        "run_id": run,
        "batch_filter": requested_batch,
        "screenable_intake_count": screenable_total,
        "batches_total": len(verified_batches),
        "completed_batches": sum(1 for item in verified_batches if item.get("result") is not None),
        "open_batches": sum(1 for item in verified_batches if item.get("result") is None),
        "batched_company_count": len(seen),
        "completed_company_count": len(completed_symbols),
        "open_company_count": len(open_symbols),
        "remaining_unbatched_count": len(remaining),
        "deferred_current_state_count": sum(deferred.values()),
        "deferred_current_state": dict(sorted(deferred.items())),
        "by_route": dict(sorted(by_route.items())),
        "completed_manager_wall_clock_seconds": sum(
            (
                _parse_datetime(item["result"]["recorded_at"], "result recorded_at")
                - _parse_datetime(item["batch"]["frozen_at"], "batch frozen_at")
            ).total_seconds()
            for item in verified_batches
            if item.get("result") is not None
        ),
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
        "quick_profile_effort_budget_hours": effort,
        "quick_profile_stop_conditions": [item.strip() for item in stops],
        "pass_and_watch_require_revisit_trigger": True,
        "recursive_correction": "forbidden",
        "one_line_reason_max_chars": reason_max,
        "decisive_question_max_chars": question_max,
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
) -> None:
    universe_source = manifest.get("universe_source")
    if not isinstance(universe_source, Mapping):
        raise ManagerScreeningError("scope manifest universe source is invalid")
    source_path_value = universe_source.get("path")
    if not isinstance(source_path_value, str) or not source_path_value:
        raise ManagerScreeningError("scope manifest universe source path is invalid")
    source_path = Path(source_path_value)
    if not source_path.is_absolute():
        source_path = base.parent.parent / source_path
    expected_source_path = base / COMPANIES_FILE
    if source_path.resolve() != expected_source_path.resolve():
        raise ManagerScreeningError(
            "scope manifest does not bind the manager-screen company snapshot"
        )
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
    intake: Mapping[str, Any],
    queue_by_symbol: Mapping[str, Mapping[str, Any]],
    already_batched: set[str],
) -> tuple[list[dict[str, Any]], Counter[str]]:
    candidates = []
    deferred: Counter[str] = Counter()
    for member in intake.get("members", []):
        if not isinstance(member, Mapping):
            raise ManagerScreeningError("baseline intake member must be an object")
        symbol = _symbol(member.get("symbol"))
        action = member.get("materialization_action")
        if action != "normalize_queue":
            deferred[str(action)] += 1
            continue
        if symbol in already_batched:
            continue
        queued = queue_by_symbol.get(symbol)
        reason = _queue_defer_reason(queued)
        if reason is not None:
            deferred[reason] += 1
            continue
        candidates.append(dict(member))
    candidates.sort(key=lambda item: _positive_int(item.get("ordinal"), "scope ordinal"))
    return candidates, deferred


def _queue_defer_reason(queued: Mapping[str, Any] | None) -> str | None:
    if queued is None:
        return None
    if queued.get("manager_screen_result_path"):
        return "manager_screen_terminal"
    if queued.get("task_type") in PROTECTED_TASK_TYPES:
        return "analyst_or_deeper_stage"
    if queued.get("status") == "running":
        return "running"
    if queued.get("status") in {"completed", "skipped", "needs_review"}:
        return f"status:{queued.get('status')}"
    return None


def _build_dossier(
    *,
    member: Mapping[str, Any],
    company: Mapping[str, Any] | None,
    screening: Mapping[str, Any] | None,
    queue: Mapping[str, Any] | None,
    repository_root: Path,
) -> dict[str, Any]:
    symbol = _symbol(member.get("symbol"))
    if company is None:
        raise ManagerScreeningError(f"company snapshot is missing: {symbol}")
    if company.get("symbol") != symbol:
        raise ManagerScreeningError(f"company snapshot identity mismatch: {symbol}")
    market_snapshot = {key: company.get(key) for key in MARKET_FIELDS}
    prior_screening = (
        {key: screening.get(key) for key in SCREEN_FIELDS} if screening is not None else None
    )
    prior_queue = {key: queue.get(key) for key in QUEUE_FIELDS} if queue is not None else None
    ticker = symbol.split(":", 1)[1]
    meta_path = repository_root / "research" / "companies" / "CN" / ticker / "meta.json"
    timeline = _timeline_summary(meta_path, symbol=symbol)
    evidence_catalog = [
        {
            "evidence_id": f"snapshot:{symbol}",
            "kind": "market_snapshot",
            "path": "coverage/cn-a/companies.jsonl",
            "as_of": company.get("as_of"),
        }
    ]
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
    normalized = []
    for item in value:
        if not isinstance(item, Mapping) or set(item) != DECISION_KEYS:
            raise ManagerScreeningError(
                "decision fields do not match the manager-screen v1 contract"
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
        normalized.append(
            {
                "symbol": symbol,
                "route": route,
                "one_line_reason": reason,
                "decisive_question": question,
                "revisit_triggers": triggers,
                "confidence": confidence,
                "evidence_ids": list(evidence_ids),
            }
        )
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
    }


def _validate_batch(batch: Mapping[str, Any]) -> None:
    if set(batch) != BATCH_KEYS or batch.get("schema_version") != 1:
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
    policy = batch.get("policy")
    if not isinstance(policy, Mapping) or set(policy) != POLICY_REF_KEYS:
        raise ManagerScreeningError("manager-screen policy reference is invalid")
    for key in ("file_sha256", "payload_sha256"):
        _sha256(policy.get(key), f"policy.{key}")
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
