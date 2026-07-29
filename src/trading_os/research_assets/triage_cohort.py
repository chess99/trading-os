from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from .coverage_store import (
    QUEUE_STATUSES,
    RESEARCH_QUEUE_FILE,
    SCREENING_FILE,
    read_jsonl,
    serialized_coverage_write,
    write_jsonl,
)
from .research_allocation import ResearchAllocationError
from .sealing import seal_json, verify_sealed

COHORT_KEYS = {
    "schema_version",
    "cycle_id",
    "frozen_at",
    "selection_basis",
    "request",
    "cohort_count",
    "members",
    "portfolio_action",
}
COHORT_V2_KEYS = COHORT_KEYS | {"parent_scope"}
PARENT_SCOPE_KEYS = {
    "run_id",
    "scope_cutoff",
    "manifest_path",
    "manifest_sha256",
    "baseline_intake_path",
    "baseline_intake_sha256",
}
REQUEST_KEYS = {
    "mode",
    "queue_status",
    "limit",
    "after_symbol",
    "symbols",
}
MEMBER_KEYS = {
    "ordinal",
    "symbol",
    "name",
    "intake_reason_codes",
    "prior_task_type",
    "prior_status",
    "prior_reason",
    "prior_result_path",
}
SYMBOL_RE = re.compile(r"^CN:[0-9]{6}$")
CYCLE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
TRIAGE_EFFORT_HOURS = 0.25
RETRIABLE_TERMINAL_STATUSES = {"completed", "needs_review"}
RAPID_TRIAGE_INTAKE_STATUSES = {
    "pending",
    "requires_rebaseline",
    "failed",
    "skipped",
    "needs_review",
}
RAPID_TRIAGE_INTAKE_TASK_TYPES = {"initial_research", "rapid_triage"}


@serialized_coverage_write
def freeze_rapid_triage_cohort(
    *,
    root: str | Path,
    cycle_id: str,
    frozen_at: dt.datetime,
    queue_status: str = "requires_rebaseline",
    limit: int | None = None,
    after_symbol: str | None = None,
    symbols: Sequence[str] | None = None,
    scope_run_id: str | None = None,
) -> dict[str, Any]:
    """Freeze an administrative rapid-triage cohort without investment ranking.

    Selection is either a stable symbol-order slice of one queue status or an
    explicit symbol set.  The sealed cohort is the immutable source of truth;
    queue and screening rows are merely its resumable materialization.
    """

    _aware(frozen_at, "frozen_at")
    cycle = _cycle(cycle_id)
    explicit = symbols is not None
    _validate_freeze_queue_status(queue_status, explicit=explicit)
    if explicit:
        if limit is not None or after_symbol is not None:
            raise ResearchAllocationError(
                "explicit symbols cannot be combined with limit or after_symbol"
            )
        selected_symbols = _symbol_list(symbols)
        request = {
            "mode": "explicit_symbols",
            "queue_status": queue_status,
            "limit": None,
            "after_symbol": None,
            "symbols": selected_symbols,
        }
    else:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise ResearchAllocationError(
                "limit must be a positive integer when symbols are not explicit"
            )
        cursor = _symbol(after_symbol) if after_symbol is not None else None
        selected_symbols = None
        request = {
            "mode": "queue_status",
            "queue_status": queue_status,
            "limit": limit,
            "after_symbol": cursor,
            "symbols": None,
        }

    base = Path(root)
    repository_root = base.parent.parent
    parent_scope = (
        _load_parent_scope(base, repository_root, _cycle(scope_run_id))
        if scope_run_id is not None
        else None
    )
    parent_scope_symbols: set[str] = set()
    if parent_scope is not None:
        parent_scope_symbols = parent_scope.pop("_symbols")
    cohort_path = base / "triage" / cycle / "cohort.json"
    relative_path = cohort_path.relative_to(repository_root).as_posix()
    queue_path = base / RESEARCH_QUEUE_FILE
    screening_path = base / SCREENING_FILE
    queue = read_jsonl(queue_path)
    screening = read_jsonl(screening_path)

    if cohort_path.exists():
        sealed = verify_sealed(cohort_path)
        if sealed.artifact_type != "rapid_triage_cohort":
            raise ResearchAllocationError(
                f"unexpected sealed artifact type for cohort: {sealed.artifact_type}"
            )
        payload = _load_and_validate_cohort(cohort_path)
        if (
            payload["cycle_id"] != cycle
            or payload["request"] != request
            or payload.get("parent_scope") != parent_scope
        ):
            raise ResearchAllocationError(
                f"sealed rapid-triage cohort conflicts with freeze request: {cycle}"
            )
        materialized = _materialize_cohort(
            payload,
            cohort_sha256=sealed.sha256,
            cohort_path=relative_path,
            queue=queue,
            screening=screening,
            queue_path=queue_path,
            screening_path=screening_path,
        )
        return _freeze_result(
            payload,
            cohort_path=relative_path,
            cohort_sha256=sealed.sha256,
            idempotent=True,
            materialized_count=materialized,
        )

    queue_by_symbol = _unique_by_symbol(queue, "research queue")
    screening_by_symbol = _unique_by_symbol(screening, "screening")
    if explicit:
        candidates = []
        for symbol in selected_symbols or []:
            record = queue_by_symbol.get(symbol)
            if record is None:
                raise ResearchAllocationError(f"symbol is absent from research queue: {symbol}")
            if record.get("status") != queue_status:
                raise ResearchAllocationError(
                    f"symbol queue status is not {queue_status}: {symbol}"
                )
            _validate_intake_record(
                record,
                symbol=symbol,
                requested_status=queue_status,
                allow_terminal_refresh=True,
            )
            candidates.append(record)
    else:
        candidates = sorted(
            (
                item
                for item in queue
                if item.get("status") == queue_status
                and _is_intake_record(item, requested_status=queue_status)
                and (
                    request["after_symbol"] is None
                    or item.get("symbol") > request["after_symbol"]
                )
            ),
            key=lambda item: str(item.get("symbol")),
        )[: int(request["limit"])]

    if not candidates:
        raise ResearchAllocationError(
            f"no queue records are available for rapid-triage freeze: {queue_status}"
        )
    candidate_symbols = [str(item.get("symbol")) for item in candidates]
    if candidate_symbols != sorted(candidate_symbols):
        candidates.sort(key=lambda item: str(item.get("symbol")))
    for record in candidates:
        symbol = _symbol(record.get("symbol"))
        _text(record.get("name"), f"{symbol}.name")
        _validate_intake_record(
            record,
            symbol=symbol,
            requested_status=queue_status,
            allow_terminal_refresh=explicit,
        )
        if symbol not in screening_by_symbol:
            raise ResearchAllocationError(f"symbol is absent from screening: {symbol}")
        existing_cycle = record.get("triage_cycle_id")
        existing_sha = record.get("cohort_sha256")
        if existing_cycle is not None or existing_sha is not None:
            if existing_cycle == cycle and existing_sha is None:
                raise ResearchAllocationError(
                    f"queue record has an incomplete cohort binding: {symbol}"
                )
            _verify_terminal_cycle_can_be_rebound(
                repository_root,
                record,
                symbol=symbol,
            )
    if parent_scope is not None:
        missing = sorted(set(candidate_symbols) - parent_scope_symbols)
        if missing:
            raise ResearchAllocationError(
                "rapid-triage cohort contains symbols outside the sealed baseline intake: "
                + ", ".join(missing)
            )

    reason_code = _queue_status_reason_code(queue_status)
    members = [
        {
            "ordinal": index,
            "symbol": item["symbol"],
            "name": item["name"],
            "intake_reason_codes": [reason_code],
            "prior_task_type": item.get("task_type"),
            "prior_status": item.get("status"),
            "prior_reason": item.get("reason"),
            "prior_result_path": item.get("result_path"),
        }
        for index, item in enumerate(candidates, 1)
    ]
    payload = {
        "schema_version": 2 if parent_scope is not None else 1,
        "cycle_id": cycle,
        "frozen_at": frozen_at.isoformat(),
        "selection_basis": (
            "administrative coverage intake in stable symbol order; no investment "
            "score, factor rank, style lens, or valuation rank was used"
        ),
        "request": request,
        "cohort_count": len(members),
        "members": members,
        "portfolio_action": None,
    }
    if parent_scope is not None:
        payload["parent_scope"] = parent_scope
    sealed = seal_json(
        cohort_path,
        payload,
        artifact_type="rapid_triage_cohort",
        sealed_at=frozen_at,
    )
    materialized = _materialize_cohort(
        payload,
        cohort_sha256=sealed.sha256,
        cohort_path=relative_path,
        queue=queue,
        screening=screening,
        queue_path=queue_path,
        screening_path=screening_path,
    )
    return _freeze_result(
        payload,
        cohort_path=relative_path,
        cohort_sha256=sealed.sha256,
        idempotent=False,
        materialized_count=materialized,
    )


def load_rapid_triage_cohort(
    *, root: str | Path, cycle_id: str
) -> tuple[dict[str, Any], str, str]:
    """Load and verify one administrative cohort.

    Returns ``(payload, sha256, repository_relative_path)``.
    """

    base = Path(root)
    cycle = _cycle(cycle_id)
    path = base / "triage" / cycle / "cohort.json"
    sealed = verify_sealed(path)
    if sealed.artifact_type != "rapid_triage_cohort":
        raise ResearchAllocationError(
            f"unexpected sealed artifact type for cohort: {sealed.artifact_type}"
        )
    payload = _load_and_validate_cohort(path)
    if payload["cycle_id"] != cycle:
        raise ResearchAllocationError("cohort cycle_id does not match path")
    relative = path.relative_to(base.parent.parent).as_posix()
    return payload, sealed.sha256, relative


def read_symbol_file(path: str | Path) -> list[str]:
    """Read a JSON symbol list/object or a newline-delimited symbol file."""

    source = Path(path)
    text = source.read_text(encoding="utf-8-sig")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        values = [
            line.strip()
            for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        return _symbol_list(values)
    if isinstance(parsed, Mapping):
        parsed = parsed.get("symbols")
    if not isinstance(parsed, list):
        raise ResearchAllocationError(
            "symbols file must be a JSON array, a {symbols: [...]} object, or one symbol per line"
        )
    return _symbol_list(parsed)


def _materialize_cohort(
    payload: Mapping[str, Any],
    *,
    cohort_sha256: str,
    cohort_path: str,
    queue: list[dict[str, Any]],
    screening: list[dict[str, Any]],
    queue_path: Path,
    screening_path: Path,
) -> int:
    queue_by_symbol = _unique_by_symbol(queue, "research queue")
    screening_by_symbol = _unique_by_symbol(screening, "screening")
    changed_symbols: set[str] = set()
    frozen_at = str(payload["frozen_at"])
    cycle = str(payload["cycle_id"])

    for member in payload["members"]:
        symbol = member["symbol"]
        queued = queue_by_symbol.get(symbol)
        screened = screening_by_symbol.get(symbol)
        if queued is None or screened is None:
            raise ResearchAllocationError(
                f"cohort member is absent from coverage materialization: {symbol}"
            )
        existing_sha = queued.get("cohort_sha256")
        existing_cycle = queued.get("triage_cycle_id")
        if existing_sha is not None or existing_cycle is not None:
            if existing_sha == cohort_sha256 and existing_cycle == cycle:
                if queued.get("cohort_path") != cohort_path:
                    raise ResearchAllocationError(
                        f"cohort member path binding is inconsistent: {symbol}"
                    )
                continue
            _validate_intake_record(
                queued,
                symbol=symbol,
                requested_status=str(member["prior_status"]),
                allow_terminal_refresh=payload["request"]["mode"] == "explicit_symbols",
            )
            _verify_terminal_cycle_can_be_rebound(
                queue_path.parent.parent.parent,
                queued,
                symbol=symbol,
            )
        else:
            _validate_intake_record(
                queued,
                symbol=symbol,
                requested_status=str(member["prior_status"]),
                allow_terminal_refresh=payload["request"]["mode"] == "explicit_symbols",
            )
        if (
            queued.get("status") != member["prior_status"]
            or queued.get("task_type") != member["prior_task_type"]
        ):
            raise ResearchAllocationError(
                f"cannot repair cohort materialization after queue state changed: {symbol}"
            )

        updated = dict(queued)
        prior_cycle = updated.get("triage_cycle_id")
        prior_selection_path = updated.get("triage_selection_path")
        for stale_field in (
            "allocation_sha256",
            "selected_by",
            "matched_lenses",
            "economic_risk_cluster",
            "triage_priority_score",
            "triage_selection_path",
            "triage_selection_sha256",
            "triage_allocation_decision",
            "triage_selection_reason",
            "triage_review_mode",
            "company_timeline_report_path",
            "profile_cycle_id",
            "profile_evaluation_path",
            "profile_recorded_at",
            "profile_quick_selection_path",
            "profile_scoped_selection_path",
        ):
            updated.pop(stale_field, None)
        history = list(updated.get("stage_history") or [])
        refresh_event = {
            "stage": "coverage_refresh",
            "status": "frozen_for_rapid_triage",
            "finished_at": frozen_at,
            "cohort_path": cohort_path,
            "cohort_sha256": cohort_sha256,
        }
        if isinstance(prior_cycle, str) and prior_cycle != cycle:
            refresh_event["replaces_cycle_id"] = prior_cycle
        if isinstance(prior_selection_path, str):
            refresh_event["replaces_selection_path"] = prior_selection_path
        history.append(refresh_event)
        updated.update(
            {
                "task_type": "rapid_triage",
                "priority": 3,
                "status": "pending",
                "reason": (
                    f"Administrative intake from queue status {member['prior_status']}; "
                    "no investment ranking was applied."
                ),
                "assigned_agent": None,
                "started_at": None,
                "finished_at": None,
                "result_path": None,
                "failure_reason": None,
                "next_action": (
                    "Complete an auditable rapid triage, then wait for the sealed "
                    "cohort comparison and an independent Agent decision."
                ),
                "effort_budget_hours": TRIAGE_EFFORT_HOURS,
                "preceding_stage": "coverage_refresh",
                "stop_conditions": [
                    "current research value is low and a concrete revisit trigger is recorded",
                    "survival, governance, or evidence reliability prevents further work now",
                    "the business is outside the assigned Agent's competence "
                    "and must be reassigned",
                ],
                "cohort_sha256": cohort_sha256,
                "cohort_path": cohort_path,
                "cohort_ordinal": member["ordinal"],
                "triage_cycle_id": cycle,
                "intake_reason_codes": list(member["intake_reason_codes"]),
                "triage_disposition": None,
                "revisit_triggers": [],
                "stage_history": history,
            }
        )
        queue_by_symbol[symbol] = updated

        screen = dict(screened)
        evidence = [
            value
            for value in list(screen.get("evidence") or [])
            if not str(value).startswith(("triage_cohort:", "triage_cohort_sha256:"))
        ]
        evidence.extend(
            [
                f"triage_cohort:{cohort_path}",
                f"triage_cohort_sha256:{cohort_sha256}",
                f"intake_reason_codes:{','.join(member['intake_reason_codes'])}",
            ]
        )
        screen.update(
            {
                "decision": "rapid_triage",
                "priority": None,
                "reason": (
                    "Frozen for administrative coverage refresh before any "
                    "cross-company research-budget decision."
                ),
                "evidence": evidence,
                "next_action": "Complete and seal the rapid-triage package.",
                "triage_cycle_id": cycle,
            }
        )
        screening_by_symbol[symbol] = screen
        changed_symbols.add(symbol)

    if changed_symbols:
        write_jsonl(screening_path, list(screening_by_symbol.values()))
        write_jsonl(queue_path, list(queue_by_symbol.values()))
    return len(changed_symbols)


def _load_and_validate_cohort(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or (
        set(payload) != COHORT_KEYS and set(payload) != COHORT_V2_KEYS
    ):
        raise ResearchAllocationError("rapid-triage cohort fields do not match contract")
    schema_version = payload.get("schema_version")
    if schema_version not in {1, 2}:
        raise ResearchAllocationError("rapid-triage cohort schema_version must be 1 or 2")
    if schema_version == 1 and set(payload) != COHORT_KEYS:
        raise ResearchAllocationError("v1 rapid-triage cohort cannot bind a parent scope")
    if schema_version == 2:
        parent_scope = payload.get("parent_scope")
        if not isinstance(parent_scope, dict) or set(parent_scope) != PARENT_SCOPE_KEYS:
            raise ResearchAllocationError("rapid-triage cohort parent scope is invalid")
        _cycle(parent_scope.get("run_id"))
        _datetime(parent_scope.get("scope_cutoff"), "parent_scope.scope_cutoff")
        for field in ("manifest_path", "baseline_intake_path"):
            _text(parent_scope.get(field), f"parent_scope.{field}")
        for field in ("manifest_sha256", "baseline_intake_sha256"):
            value = parent_scope.get(field)
            if (
                not isinstance(value, str)
                or len(value) != 64
                or any(char not in "0123456789abcdef" for char in value)
            ):
                raise ResearchAllocationError(f"parent_scope.{field} is invalid")
    _cycle(payload.get("cycle_id"))
    _datetime(payload.get("frozen_at"), "frozen_at")
    _text(payload.get("selection_basis"), "selection_basis")
    if payload.get("portfolio_action") is not None:
        raise ResearchAllocationError("rapid-triage cohort cannot contain portfolio action")
    request = payload.get("request")
    if not isinstance(request, dict) or set(request) != REQUEST_KEYS:
        raise ResearchAllocationError("rapid-triage cohort request is invalid")
    if request.get("mode") not in {"queue_status", "explicit_symbols"}:
        raise ResearchAllocationError("rapid-triage cohort request mode is invalid")
    queue_status = request.get("queue_status")
    if not isinstance(queue_status, str):
        raise ResearchAllocationError("rapid-triage cohort queue_status is invalid")
    _validate_freeze_queue_status(
        queue_status,
        explicit=request["mode"] == "explicit_symbols",
    )
    members = payload.get("members")
    if not isinstance(members, list) or not members:
        raise ResearchAllocationError("rapid-triage cohort members must not be empty")
    if payload.get("cohort_count") != len(members):
        raise ResearchAllocationError("rapid-triage cohort count does not match members")
    symbols: list[str] = []
    for expected_ordinal, member in enumerate(members, 1):
        if not isinstance(member, dict) or set(member) != MEMBER_KEYS:
            raise ResearchAllocationError("rapid-triage cohort member is invalid")
        if member.get("ordinal") != expected_ordinal:
            raise ResearchAllocationError("rapid-triage cohort ordinal is invalid")
        symbols.append(_symbol(member.get("symbol")))
        _text(member.get("name"), "member.name")
        reasons = member.get("intake_reason_codes")
        if not isinstance(reasons, list) or not reasons or not all(
            isinstance(value, str) and value.strip() for value in reasons
        ):
            raise ResearchAllocationError("member intake_reason_codes are invalid")
        if member.get("prior_status") != queue_status:
            raise ResearchAllocationError(
                "cohort member prior_status does not match request queue_status"
            )
        if member.get("prior_task_type") not in RAPID_TRIAGE_INTAKE_TASK_TYPES:
            raise ResearchAllocationError(
                "cohort member prior_task_type is not eligible for rapid-triage intake"
            )
        if queue_status == "completed" and member.get("prior_task_type") != "rapid_triage":
            raise ResearchAllocationError(
                "completed cohort members must come from finalized rapid triage"
            )
    if symbols != sorted(symbols) or len(symbols) != len(set(symbols)):
        raise ResearchAllocationError(
            "rapid-triage cohort members must be unique and in stable symbol order"
        )
    expected_symbols = request.get("symbols")
    if request["mode"] == "explicit_symbols" and expected_symbols != symbols:
        raise ResearchAllocationError("explicit cohort symbols do not match members")
    return payload


def _load_parent_scope(
    base: Path,
    repository_root: Path,
    run_id: str,
) -> dict[str, Any]:
    scope_dir = base / "scopes" / run_id
    manifest_path = scope_dir / "manifest.json"
    intake_path = scope_dir / "baseline-intake.json"
    try:
        manifest_seal = verify_sealed(manifest_path)
        intake_seal = verify_sealed(intake_path)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        intake = json.loads(intake_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise ResearchAllocationError(
            f"parent all-A scope is not validly sealed: {run_id}"
        ) from exc
    if (
        manifest_seal.artifact_type != "all_a_scope_manifest"
        or intake_seal.artifact_type != "all_a_baseline_intake"
        or manifest.get("run_id") != run_id
        or intake.get("run_id") != run_id
        or intake.get("scope_manifest_sha256") != manifest_seal.sha256
    ):
        raise ResearchAllocationError(f"parent all-A scope binding is invalid: {run_id}")
    intake_members = intake.get("members")
    if not isinstance(intake_members, list):
        raise ResearchAllocationError("parent baseline intake members are invalid")
    allowed_symbols = {
        item.get("symbol")
        for item in intake_members
        if isinstance(item, Mapping) and item.get("materialization_action") == "normalize_queue"
    }
    return {
        "run_id": run_id,
        "scope_cutoff": manifest["scope_cutoff"],
        "manifest_path": manifest_path.relative_to(repository_root).as_posix(),
        "manifest_sha256": manifest_seal.sha256,
        "baseline_intake_path": intake_path.relative_to(repository_root).as_posix(),
        "baseline_intake_sha256": intake_seal.sha256,
        "_symbols": allowed_symbols,
    }


def _verify_terminal_cycle_can_be_rebound(
    repository_root: Path,
    record: Mapping[str, Any],
    *,
    symbol: str,
) -> None:
    """Allow a new trigger cycle only after the prior cycle was fully finalized."""

    if record.get("status") not in RETRIABLE_TERMINAL_STATUSES:
        raise ResearchAllocationError(
            f"queue record is already bound to an active rapid-triage cohort: {symbol}"
        )
    prior_cycle = record.get("triage_cycle_id")
    prior_cohort_sha = record.get("cohort_sha256")
    selection_path_text = record.get("triage_selection_path")
    selection_sha = record.get("triage_selection_sha256")
    if not all(
        isinstance(value, str) and value
        for value in (
            prior_cycle,
            prior_cohort_sha,
            selection_path_text,
            selection_sha,
        )
    ):
        raise ResearchAllocationError(
            f"prior rapid-triage cycle is not fully finalized: {symbol}"
        )
    selection_path = repository_root / str(selection_path_text)
    try:
        sealed = verify_sealed(selection_path)
    except (OSError, ValueError) as exc:
        raise ResearchAllocationError(
            f"prior rapid-triage selection is not validly sealed: {symbol}"
        ) from exc
    if (
        sealed.artifact_type != "rapid_triage_cross_company_selection"
        or sealed.sha256 != selection_sha
    ):
        raise ResearchAllocationError(
            f"prior rapid-triage selection binding is invalid: {symbol}"
        )
    try:
        selection = json.loads(selection_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResearchAllocationError(
            f"prior rapid-triage selection cannot be read: {symbol}"
        ) from exc
    if (
        not isinstance(selection, Mapping)
        or selection.get("cycle_id") != prior_cycle
        or selection.get("binding_sha256") != prior_cohort_sha
    ):
        raise ResearchAllocationError(
            f"prior rapid-triage selection does not match queue history: {symbol}"
        )


def _freeze_result(
    payload: Mapping[str, Any],
    *,
    cohort_path: str,
    cohort_sha256: str,
    idempotent: bool,
    materialized_count: int,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "cycle_id": payload["cycle_id"],
        "cohort_count": payload["cohort_count"],
        "symbols": [item["symbol"] for item in payload["members"]],
        "cohort_path": cohort_path,
        "cohort_sha256": cohort_sha256,
        "materialized_count": materialized_count,
        "idempotent": idempotent,
        "portfolio_action": None,
    }


def _unique_by_symbol(
    records: list[dict[str, Any]], label: str
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for record in records:
        symbol = _symbol(record.get("symbol"))
        if symbol in result:
            raise ResearchAllocationError(f"duplicate symbol in {label}: {symbol}")
        result[symbol] = record
    return result


def _symbol_list(values: Sequence[Any]) -> list[str]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise ResearchAllocationError("symbols must be a sequence")
    symbols = [_symbol(value) for value in values]
    if not symbols:
        raise ResearchAllocationError("symbols must not be empty")
    if len(symbols) != len(set(symbols)):
        raise ResearchAllocationError("symbols must not contain duplicates")
    return sorted(symbols)


def _queue_status_reason_code(queue_status: str) -> str:
    return {
        "requires_rebaseline": "requires_rebaseline",
        "pending": "pending_coverage_task",
        "completed": "scheduled_coverage_refresh",
        "failed": "retry_after_failed_research",
        "skipped": "scheduled_skip_recheck",
        "needs_review": "needs_manual_review",
    }[queue_status]


def _validate_freeze_queue_status(queue_status: str, *, explicit: bool) -> None:
    if queue_status not in QUEUE_STATUSES:
        raise ResearchAllocationError(f"unsupported queue_status: {queue_status}")
    if queue_status in RAPID_TRIAGE_INTAKE_STATUSES:
        return
    if explicit and queue_status == "completed":
        return
    if queue_status == "completed":
        raise ResearchAllocationError(
            "completed rapid-triage refresh requires explicit symbols"
        )
    raise ResearchAllocationError(
        f"queue_status is not eligible for rapid-triage intake: {queue_status}"
    )


def _is_intake_record(record: Mapping[str, Any], *, requested_status: str) -> bool:
    try:
        _validate_intake_record(
            record,
            symbol=str(record.get("symbol")),
            requested_status=requested_status,
            allow_terminal_refresh=False,
        )
    except ResearchAllocationError:
        return False
    return True


def _validate_intake_record(
    record: Mapping[str, Any],
    *,
    symbol: str,
    requested_status: str,
    allow_terminal_refresh: bool,
) -> None:
    status = record.get("status")
    if status != requested_status:
        raise ResearchAllocationError(
            f"queue record status changed before rapid-triage freeze: {symbol}"
        )
    task_type = record.get("task_type")
    if task_type not in RAPID_TRIAGE_INTAKE_TASK_TYPES:
        raise ResearchAllocationError(
            "queue record is already at a protected research stage and cannot be "
            f"downgraded to rapid triage: {symbol} ({task_type})"
        )
    if status == "completed":
        if not allow_terminal_refresh or task_type != "rapid_triage":
            raise ResearchAllocationError(
                f"completed queue record is not eligible for rapid-triage intake: {symbol}"
            )
        if not record.get("triage_cycle_id") or not record.get("cohort_sha256"):
            raise ResearchAllocationError(
                f"completed rapid-triage record is not fully cohort-bound: {symbol}"
            )
        return
    if status not in RAPID_TRIAGE_INTAKE_STATUSES:
        raise ResearchAllocationError(
            f"queue record is not in an intake state: {symbol} ({status})"
        )
    if status in {"pending", "requires_rebaseline"} and (
        record.get("assigned_agent") is not None or record.get("started_at") is not None
    ):
        raise ResearchAllocationError(
            f"queue record has active assignment metadata and cannot be frozen: {symbol}"
        )


def _cycle(value: Any) -> str:
    result = _text(value, "cycle_id")
    if not CYCLE_RE.fullmatch(result):
        raise ResearchAllocationError("cycle_id is invalid")
    return result


def _symbol(value: Any) -> str:
    result = _text(value, "symbol")
    if not SYMBOL_RE.fullmatch(result):
        raise ResearchAllocationError("symbol must match CN:000000")
    return result


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ResearchAllocationError(f"{label} must be a non-empty string")
    return value.strip()


def _datetime(value: Any, label: str) -> dt.datetime:
    text = _text(value, label)
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError as exc:
        raise ResearchAllocationError(f"{label} must be an ISO datetime") from exc
    _aware(parsed, label)
    return parsed


def _aware(value: dt.datetime, label: str) -> None:
    if (
        not isinstance(value, dt.datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ResearchAllocationError(f"{label} must include timezone information")
