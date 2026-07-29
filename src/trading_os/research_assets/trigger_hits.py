from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .coverage_store import serialized_coverage_write
from .sealing import (
    SealingError,
    atomic_write_bytes,
    canonical_json_bytes,
    seal_json,
    verify_sealed,
)

SCHEMA_VERSION = 1
ZERO_HASH = "0" * 64
SYMBOL_RE = re.compile(r"^CN:[0-9]{6}$")
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
FACT_TRIGGER_TYPES = {"filing", "event", "thesis"}
SCHEDULE_TRIGGER_TYPES = {"date", "ttl"}
WORKFLOW_TARGETS = {"company_research", "portfolio_refresh"}
EVENT_TYPES = {"hit_observed", "condition_rearmed", "hit_consumed"}

LEDGER_RELATIVE_PATH = Path("trigger-hits/events.jsonl")
STATE_RELATIVE_PATH = Path("trigger-hits/state.json")


class TriggerHitError(ValueError):
    """Raised when trigger observations or the canonical ledger are invalid."""


@serialized_coverage_write
def observe_fact_hit(
    *,
    root: str | Path,
    observation: Mapping[str, Any],
    recorded_at: dt.datetime,
) -> dict[str, Any]:
    """Record one externally observed filing, event, or thesis occurrence."""

    return _observe_fact_locked(
        root=Path(root),
        observation=observation,
        recorded_at=_aware(recorded_at, "recorded_at"),
        allowed_types=FACT_TRIGGER_TYPES,
    )


@serialized_coverage_write
def observe_price_condition(
    *,
    root: str | Path,
    trigger: Mapping[str, Any],
    quote_evidence: Mapping[str, Any],
    condition_met: bool,
    actor: str,
    recorded_at: dt.datetime,
    workflow_target: str = "company_research",
) -> dict[str, Any]:
    """Observe one price condition using edge-triggered episodes.

    A true observation creates at most one hit until a later false observation
    rearms the same trigger definition.
    """

    base = Path(root)
    recorded = _aware(recorded_at, "recorded_at")
    if not isinstance(condition_met, bool):
        raise TriggerHitError("condition_met must be a boolean")
    normalized_trigger = _normalize_trigger_ref(trigger, allowed_types={"price"})
    symbol = _symbol(quote_evidence.get("symbol"))
    target = _workflow_target(workflow_target)
    actor_name = _text(actor, "actor")
    quote_as_of = _parse_datetime(quote_evidence.get("quote_as_of"), "quote_as_of")
    if quote_as_of > recorded:
        raise TriggerHitError("quote_as_of cannot be after recorded_at")
    observed_price = quote_evidence.get("observed_price")
    if (
        isinstance(observed_price, bool)
        or not isinstance(observed_price, (int, float))
        or float(observed_price) <= 0
    ):
        raise TriggerHitError("observed_price must be a positive number")
    source_sha256 = _sha256(quote_evidence.get("source_sha256"), "source_sha256")
    source_ref = _text(quote_evidence.get("source_ref"), "source_ref")
    monitor_key = _digest(
        {
            "symbol": symbol,
            "workflow_target": target,
            "trigger_id": normalized_trigger["trigger_id"],
            "definition_sha256": normalized_trigger["definition_sha256"],
        }
    )
    events, projection = _load_verified(base)
    monitor = next(
        (
            item
            for item in projection["price_monitors"]
            if item["monitor_key"] == monitor_key
        ),
        None,
    )
    armed = monitor is None or bool(monitor["armed"])
    episode = int(monitor["episode"]) if monitor is not None else 0

    if not condition_met:
        if armed:
            return {
                "schema_version": SCHEMA_VERSION,
                "action": "already_armed",
                "monitor_key": monitor_key,
                "hit_id": None,
                "ledger_line_count": len(events),
            }
        payload = {
            "monitor_key": monitor_key,
            "symbol": symbol,
            "workflow_target": target,
            "trigger_ref": normalized_trigger,
            "episode": episode,
            "observed_at": quote_as_of.isoformat(),
            "quote_evidence": {
                "source_ref": source_ref,
                "source_sha256": source_sha256,
                "quote_as_of": quote_as_of.isoformat(),
                "observed_price": float(observed_price),
                "condition_met": False,
            },
            "actor": actor_name,
        }
        event, appended = _append_logical_event(
            base,
            events,
            event_type="condition_rearmed",
            idempotency_key=f"price-rearm:{monitor_key}:{episode}",
            payload=payload,
            recorded_at=recorded,
        )
        projection = _project(events + ([event] if appended else []))
        _write_projection(base, projection)
        return {
            "schema_version": SCHEMA_VERSION,
            "action": "rearmed" if appended else "already_rearmed",
            "monitor_key": monitor_key,
            "hit_id": None,
            "ledger_line_count": projection["ledger_line_count"],
        }

    if not armed:
        return {
            "schema_version": SCHEMA_VERSION,
            "action": "condition_still_true",
            "monitor_key": monitor_key,
            "hit_id": monitor.get("active_hit_id") if monitor else None,
            "ledger_line_count": len(events),
        }

    episode += 1
    occurrence_key = f"price-episode:{episode}"
    occurrence_evidence = {
        "kind": "price",
        "occurrence_key": occurrence_key,
        "source_id": source_ref,
        "source_ref": source_ref,
        "source_sha256": source_sha256,
        "published_at": quote_as_of.isoformat(),
        "observed_price": float(observed_price),
        "condition_met": True,
    }
    result = _observe_normalized(
        base=base,
        events=events,
        symbol=symbol,
        workflow_target=target,
        trigger_ref=normalized_trigger,
        effective_at=quote_as_of,
        observed_at=quote_as_of,
        occurrence_evidence=occurrence_evidence,
        actor=actor_name,
        idempotency_key=f"price-hit:{monitor_key}:{episode}",
        recorded_at=recorded,
        monitor={"monitor_key": monitor_key, "episode": episode},
    )
    return result


@serialized_coverage_write
def observe_schedule_hit(
    *,
    root: str | Path,
    item: Mapping[str, Any],
    schedule_as_of: dt.datetime,
    schedule_ref: str,
    schedule_sha256: str,
    actor: str,
    recorded_at: dt.datetime,
    workflow_target: str = "company_research",
) -> dict[str, Any]:
    """Record a due date/TTL schedule item; watching definitions are not hits."""

    base = Path(root)
    cutoff = _aware(schedule_as_of, "schedule_as_of")
    recorded = _aware(recorded_at, "recorded_at")
    if item.get("state") != "due":
        raise TriggerHitError("only a due schedule item can become a trigger hit")
    if item.get("trigger_id") == "research-rebaseline" or item.get("type") == "rebaseline":
        raise TriggerHitError("research-rebaseline is baseline intake, not a trigger hit")
    if item.get("type") not in SCHEDULE_TRIGGER_TYPES:
        raise TriggerHitError("only date or ttl schedule items can become trigger hits")
    source_kind = _text(item.get("source"), "schedule item source")
    semantic_type = (
        "ttl"
        if source_kind in {"research_refresh_due", "evidence_expiry"}
        else "date"
    )
    condition = item.get("condition")
    if not isinstance(condition, Mapping):
        raise TriggerHitError("schedule item condition must be an object")
    effective_at = _schedule_effective_at(condition, cutoff)
    if effective_at > cutoff:
        raise TriggerHitError("schedule item is not due at schedule_as_of")
    definition = {
        "type": semantic_type,
        "condition": dict(condition),
        "reason": _text(item.get("reason"), "schedule item reason"),
        "source": source_kind,
    }
    trigger_ref = _normalize_trigger_ref(
        {
            "trigger_id": item.get("trigger_id"),
            "type": semantic_type,
            "source_kind": source_kind,
            "definition_ref": schedule_ref,
            "definition_source_sha256": schedule_sha256,
            "definition": definition,
        },
        allowed_types=SCHEDULE_TRIGGER_TYPES,
    )
    observation = {
        "schema_version": SCHEMA_VERSION,
        "symbol": item.get("symbol"),
        "workflow_target": workflow_target,
        "trigger_ref": trigger_ref,
        "effective_at": effective_at.isoformat(),
        "observed_at": cutoff.isoformat(),
        "occurrence_evidence": {
            "kind": semantic_type,
            "occurrence_key": f"due:{effective_at.isoformat()}",
            "source_id": _text(item.get("trigger_id"), "trigger_id"),
            "source_ref": _text(schedule_ref, "schedule_ref"),
            "source_sha256": _sha256(schedule_sha256, "schedule_sha256"),
            "published_at": cutoff.isoformat(),
        },
        "actor": actor,
        "idempotency_key": (
            f"schedule:{item.get('symbol')}:{item.get('trigger_id')}:"
            f"{effective_at.isoformat()}:{schedule_sha256}"
        ),
    }
    return _observe_fact_locked(
        root=base,
        observation=observation,
        recorded_at=recorded,
        allowed_types=SCHEDULE_TRIGGER_TYPES,
    )


def verify_trigger_hit_ledger(*, root: str | Path) -> dict[str, Any]:
    """Verify the hash chain and compare the materialized projection."""

    base = Path(root)
    events = _read_and_verify_events(_events_path(base))
    projection = _project(events)
    state_path = _state_path(base)
    state_matches = False
    if state_path.is_file():
        try:
            raw_state = json.loads(state_path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TriggerHitError("trigger-hit state projection is invalid JSON") from exc
        state_matches = raw_state == projection and state_path.read_bytes() == canonical_json_bytes(
            projection
        )
    elif not events:
        state_matches = True
    if not state_matches:
        raise TriggerHitError("trigger-hit state projection does not match ledger replay")
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": True,
        "ledger_line_count": len(events),
        "ledger_head_sha256": events[-1]["event_sha256"] if events else ZERO_HASH,
        "open_hit_count": sum(item["state"] == "open" for item in projection["hits"]),
        "consumed_hit_count": sum(
            item["state"] == "consumed" for item in projection["hits"]
        ),
        "price_monitor_count": len(projection["price_monitors"]),
    }


@serialized_coverage_write
def rebuild_trigger_hit_state(*, root: str | Path) -> dict[str, Any]:
    """Rebuild the disposable state projection from a valid canonical ledger."""

    base = Path(root)
    events = _read_and_verify_events(_events_path(base))
    projection = _project(events)
    _write_projection(base, projection)
    return {
        "schema_version": SCHEMA_VERSION,
        "ledger_line_count": len(events),
        "ledger_head_sha256": projection["ledger_head_sha256"],
        "hit_count": len(projection["hits"]),
        "price_monitor_count": len(projection["price_monitors"]),
    }


def verify_trigger_hit_checkpoint(
    *, root: str | Path, checkpoint_path: str | Path
) -> dict[str, Any]:
    """Verify a checkpoint seal and its immutable prefix of the live ledger."""

    base = Path(root)
    repository_root = base.parent.parent
    path = _resolve_repository_path(checkpoint_path, repository_root)
    try:
        sealed = verify_sealed(path)
    except (OSError, SealingError) as exc:
        raise TriggerHitError("trigger-hit checkpoint is not validly sealed") from exc
    if sealed.artifact_type != "trigger_hit_checkpoint":
        raise TriggerHitError("checkpoint has an unexpected artifact type")
    payload = _read_object(path, "trigger-hit checkpoint")
    run = _run_id(payload.get("run_id"))
    scope_path = _resolve_repository_path(
        _text(payload.get("scope_manifest_path"), "scope_manifest_path"),
        repository_root,
    )
    try:
        scope_seal = verify_sealed(scope_path)
    except (OSError, SealingError) as exc:
        raise TriggerHitError("checkpoint scope manifest is not validly sealed") from exc
    _validate_checkpoint_binding(payload, run, scope_seal.sha256)
    scope = _read_object(scope_path, "scope manifest")
    if scope.get("run_id") != run or scope.get("scope_cutoff") != payload.get(
        "scope_cutoff"
    ):
        raise TriggerHitError("checkpoint cutoff does not bind its scope manifest")

    events_path = _events_path(base)
    events = _read_and_verify_events(events_path)
    line_count = payload.get("ledger_line_count")
    if isinstance(line_count, bool) or not isinstance(line_count, int) or line_count < 0:
        raise TriggerHitError("checkpoint ledger_line_count is invalid")
    if len(events) < line_count:
        raise TriggerHitError("live ledger is shorter than the sealed checkpoint")
    prefix = events[:line_count]
    prefix_bytes = b"".join(canonical_json_bytes(item) + b"\n" for item in prefix)
    head = prefix[-1]["event_sha256"] if prefix else ZERO_HASH
    projection = _project(prefix)
    if (
        payload.get("ledger_head_sha256") != head
        or payload.get("ledger_sha256") != hashlib.sha256(prefix_bytes).hexdigest()
        or payload.get("state_projection_sha256")
        != hashlib.sha256(canonical_json_bytes(projection)).hexdigest()
    ):
        raise TriggerHitError("checkpoint does not match the canonical ledger prefix")
    return _checkpoint_result(path, sealed.sha256, payload, repository_root)


@serialized_coverage_write
def create_trigger_hit_checkpoint(
    *,
    root: str | Path,
    run_id: str,
    scope_manifest_path: str | Path,
    checkpointed_at: dt.datetime,
) -> dict[str, Any]:
    """Seal the open-hit view bound to one frozen scope and cutoff."""

    base = Path(root)
    repository_root = base.parent.parent
    run = _run_id(run_id)
    checkpoint_time = _aware(checkpointed_at, "checkpointed_at")
    scope_path = _resolve_repository_path(scope_manifest_path, repository_root)
    try:
        scope_seal = verify_sealed(scope_path)
    except (OSError, SealingError) as exc:
        raise TriggerHitError("scope manifest is not validly sealed") from exc
    if scope_seal.artifact_type != "all_a_scope_manifest":
        raise TriggerHitError("scope manifest has an unexpected artifact type")
    scope = _read_object(scope_path, "scope manifest")
    if scope.get("run_id") != run:
        raise TriggerHitError("scope manifest run_id does not match checkpoint")
    cutoff = _parse_datetime(scope.get("scope_cutoff"), "scope_cutoff")
    frozen_at = _parse_datetime(scope.get("frozen_at"), "frozen_at")
    if checkpoint_time < frozen_at:
        raise TriggerHitError("checkpointed_at cannot be before scope frozen_at")
    members = scope.get("members")
    if not isinstance(members, list):
        raise TriggerHitError("scope manifest members must be an array")
    in_scope = {
        _symbol(item.get("symbol"))
        for item in members
        if isinstance(item, Mapping) and item.get("partition") != "hard_excluded"
    }

    checkpoint_path = scope_path.parent / "trigger-hit-checkpoint.json"
    if checkpoint_path.exists():
        return verify_trigger_hit_checkpoint(root=base, checkpoint_path=checkpoint_path)

    events = _read_and_verify_events(_events_path(base))
    projection = _project(events)
    _write_projection(base, projection)
    eligible = []
    after_cutoff = 0
    outside_scope = 0
    for hit in projection["hits"]:
        if hit["state"] != "open":
            continue
        if hit["symbol"] not in in_scope:
            outside_scope += 1
            continue
        effective_at = _parse_datetime(hit["effective_at"], "hit effective_at")
        if effective_at > cutoff:
            after_cutoff += 1
            continue
        eligible.append(_checkpoint_hit(hit))
    eligible.sort(key=lambda item: (item["symbol"], item["effective_at"], item["hit_id"]))

    ledger_path = _events_path(base)
    ledger_bytes = ledger_path.read_bytes() if ledger_path.is_file() else b""
    state_bytes = canonical_json_bytes(projection)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run,
        "scope_cutoff": cutoff.isoformat(),
        "checkpointed_at": checkpoint_time.isoformat(),
        "scope_manifest_path": _relative(scope_path, repository_root),
        "scope_manifest_sha256": scope_seal.sha256,
        "ledger_path": _relative(ledger_path, repository_root),
        "ledger_line_count": len(events),
        "ledger_head_sha256": events[-1]["event_sha256"] if events else ZERO_HASH,
        "ledger_sha256": hashlib.sha256(ledger_bytes).hexdigest(),
        "state_projection_sha256": hashlib.sha256(state_bytes).hexdigest(),
        "counts": {
            "open_at_checkpoint": sum(
                item["state"] == "open" for item in projection["hits"]
            ),
            "eligible_current_run": len(eligible),
            "after_scope_cutoff": after_cutoff,
            "outside_scope": outside_scope,
        },
        "hits": eligible,
        "portfolio_action": None,
    }
    sealed = seal_json(
        checkpoint_path,
        payload,
        artifact_type="trigger_hit_checkpoint",
        sealed_at=checkpoint_time,
    )
    return _checkpoint_result(checkpoint_path, sealed.sha256, payload, repository_root)


@serialized_coverage_write
def consume_trigger_hits(
    *,
    root: str | Path,
    package_path: str | Path,
    handled_hit_ids: Sequence[str],
    timeline_evidence: Mapping[str, Any],
    consumed_at: dt.datetime,
    actor: str,
) -> dict[str, Any]:
    """Internal integration API: consume hits only after timeline publication."""

    base = Path(root)
    repository_root = base.parent.parent
    consumed = _aware(consumed_at, "consumed_at")
    actor_name = _text(actor, "actor")
    package = _resolve_repository_path(package_path, repository_root)
    try:
        package_seal = verify_sealed(package)
    except (OSError, SealingError) as exc:
        raise TriggerHitError("handled package is not validly sealed") from exc
    if package_seal.artifact_type != "rapid_triage_package":
        raise TriggerHitError("handled package must be a rapid_triage_package")
    package_payload = _read_object(package, "rapid-triage package")
    symbol = _symbol(package_payload.get("symbol"))
    requested = [_sha256(value, "handled_hit_id") for value in handled_hit_ids]
    if not requested or len(requested) != len(set(requested)):
        raise TriggerHitError("handled_hit_ids must be a non-empty unique array")
    if package_payload.get("handled_hit_ids") != requested:
        raise TriggerHitError("handled_hit_ids do not match the sealed package")
    if package_payload.get("review_mode") not in {"triggered_update", "baseline_recheck"}:
        raise TriggerHitError("handled package review_mode cannot consume trigger hits")

    meta_path = _resolve_repository_path(
        _text(timeline_evidence.get("meta_path"), "timeline meta_path"),
        repository_root,
    )
    meta = _read_object(meta_path, "company meta")
    latest = meta.get("research", {}).get("latest_rapid_triage")
    if not isinstance(latest, Mapping):
        raise TriggerHitError("timeline has no published latest_rapid_triage")
    package_relative = _relative(package, repository_root)
    if (
        meta.get("identity", {}).get("symbol") != symbol
        or latest.get("source_package_path") != package_relative
        or latest.get("source_package_sha256") != package_seal.sha256
    ):
        raise TriggerHitError("timeline does not bind the sealed handled package")
    report_relative = latest.get("report_path")
    if not isinstance(report_relative, str):
        raise TriggerHitError("timeline published report_path is missing")
    report_path = meta_path.parent / report_relative
    if not report_path.is_file():
        raise TriggerHitError("timeline published report is missing")
    if meta.get("reports", {}).get("latest_by_type", {}).get("rapid_triage") != report_relative:
        raise TriggerHitError("timeline latest_by_type does not publish the handled package")

    events, projection = _load_verified(base)
    hit_by_id = {item["hit_id"]: item for item in projection["hits"]}
    for hit_id in requested:
        hit = hit_by_id.get(hit_id)
        if hit is None or hit["symbol"] != symbol:
            raise TriggerHitError(f"handled hit is missing or belongs to another symbol: {hit_id}")
        if hit["state"] == "consumed":
            prior = hit.get("consumed_by") or {}
            if prior.get("package_sha256") != package_seal.sha256:
                raise TriggerHitError(f"hit was consumed by a different package: {hit_id}")

    appended_count = 0
    for hit_id in requested:
        hit = hit_by_id[hit_id]
        if hit["state"] == "consumed":
            continue
        payload = {
            "hit_id": hit_id,
            "symbol": symbol,
            "package_path": package_relative,
            "package_sha256": package_seal.sha256,
            "meta_path": _relative(meta_path, repository_root),
            "report_path": _relative(report_path, repository_root),
            "report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
            "consumed_at": consumed.isoformat(),
            "actor": actor_name,
        }
        event, appended = _append_logical_event(
            base,
            events,
            event_type="hit_consumed",
            idempotency_key=f"consume:{hit_id}:{package_seal.sha256}",
            payload=payload,
            recorded_at=consumed,
        )
        if appended:
            events.append(event)
            appended_count += 1
    projection = _project(events)
    _write_projection(base, projection)
    return {
        "schema_version": SCHEMA_VERSION,
        "symbol": symbol,
        "handled_hit_count": len(requested),
        "newly_consumed_count": appended_count,
        "idempotent": appended_count == 0,
        "package_sha256": package_seal.sha256,
        "ledger_line_count": len(events),
    }


def _observe_fact_locked(
    *,
    root: Path,
    observation: Mapping[str, Any],
    recorded_at: dt.datetime,
    allowed_types: set[str],
) -> dict[str, Any]:
    if not isinstance(observation, Mapping) or observation.get("schema_version") != 1:
        raise TriggerHitError("observation must follow schema_version 1")
    trigger_ref = _normalize_trigger_ref(
        _mapping(observation.get("trigger_ref"), "trigger_ref"),
        allowed_types=allowed_types,
    )
    effective_at = _parse_datetime(observation.get("effective_at"), "effective_at")
    observed_at = _parse_datetime(observation.get("observed_at"), "observed_at")
    if effective_at > observed_at or observed_at > recorded_at:
        raise TriggerHitError("effective_at <= observed_at <= recorded_at is required")
    evidence = _normalize_occurrence_evidence(
        _mapping(observation.get("occurrence_evidence"), "occurrence_evidence"),
        trigger_type=trigger_ref["type"],
    )
    if allowed_types == FACT_TRIGGER_TYPES and _parse_datetime(
        evidence["published_at"], "evidence published_at"
    ) != effective_at:
        raise TriggerHitError(
            "fact effective_at must match occurrence evidence published_at"
        )
    events, _ = _load_verified(root)
    return _observe_normalized(
        base=root,
        events=events,
        symbol=_symbol(observation.get("symbol")),
        workflow_target=_workflow_target(observation.get("workflow_target")),
        trigger_ref=trigger_ref,
        effective_at=effective_at,
        observed_at=observed_at,
        occurrence_evidence=evidence,
        actor=_text(observation.get("actor"), "actor"),
        idempotency_key=_text(observation.get("idempotency_key"), "idempotency_key"),
        recorded_at=recorded_at,
        monitor=None,
    )


def _observe_normalized(
    *,
    base: Path,
    events: list[dict[str, Any]],
    symbol: str,
    workflow_target: str,
    trigger_ref: dict[str, Any],
    effective_at: dt.datetime,
    observed_at: dt.datetime,
    occurrence_evidence: dict[str, Any],
    actor: str,
    idempotency_key: str,
    recorded_at: dt.datetime,
    monitor: dict[str, Any] | None,
) -> dict[str, Any]:
    dedupe_key = _digest(
        {
            "symbol": symbol,
            "workflow_target": workflow_target,
            "trigger_id": trigger_ref["trigger_id"],
            "definition_sha256": trigger_ref["definition_sha256"],
            "occurrence_key": occurrence_evidence["occurrence_key"],
        }
    )
    hit_id = _digest({"kind": "trigger_hit", "dedupe_key": dedupe_key})
    projection = _project(events)
    existing_hit = next(
        (item for item in projection["hits"] if item["dedupe_key"] == dedupe_key), None
    )
    logical_payload = {
        "hit_id": hit_id,
        "dedupe_key": dedupe_key,
        "symbol": symbol,
        "workflow_target": workflow_target,
        "trigger_ref": trigger_ref,
        "effective_at": effective_at.isoformat(),
        "observed_at": observed_at.isoformat(),
        "occurrence_evidence": occurrence_evidence,
        "actor": actor,
    }
    if monitor is not None:
        logical_payload["price_monitor"] = dict(monitor)
    event_id = _logical_event_id("hit_observed", idempotency_key, logical_payload)
    same_key = next(
        (item for item in events if item["idempotency_key"] == idempotency_key), None
    )
    if same_key is not None:
        if same_key["event_id"] != event_id:
            raise TriggerHitError(
                f"idempotency key conflicts with existing event: {idempotency_key}"
            )
        return _observe_result(same_key["payload"]["hit_id"], same_key, True, False)
    if existing_hit is not None:
        return {
            "schema_version": SCHEMA_VERSION,
            "hit_id": existing_hit["hit_id"],
            "state": existing_hit["state"],
            "event_id": existing_hit["observed_event_id"],
            "idempotent": False,
            "deduplicated": True,
            "ledger_line_count": len(events),
        }
    event, appended = _append_logical_event(
        base,
        events,
        event_type="hit_observed",
        idempotency_key=idempotency_key,
        payload=logical_payload,
        recorded_at=recorded_at,
    )
    all_events = events + ([event] if appended else [])
    _write_projection(base, _project(all_events))
    return _observe_result(hit_id, event, not appended, False)


def _append_logical_event(
    base: Path,
    events: list[dict[str, Any]],
    *,
    event_type: str,
    idempotency_key: str,
    payload: Mapping[str, Any],
    recorded_at: dt.datetime,
) -> tuple[dict[str, Any], bool]:
    if event_type not in EVENT_TYPES:
        raise TriggerHitError(f"unsupported trigger-hit event type: {event_type}")
    identity = _logical_event_id(event_type, idempotency_key, payload)
    existing = next(
        (item for item in events if item["idempotency_key"] == idempotency_key), None
    )
    if existing is not None:
        if existing["event_id"] != identity:
            raise TriggerHitError(
                f"idempotency key conflicts with existing event: {idempotency_key}"
            )
        return existing, False
    event = {
        "schema_version": SCHEMA_VERSION,
        "sequence": len(events) + 1,
        "event_id": identity,
        "idempotency_key": idempotency_key,
        "event_type": event_type,
        "recorded_at": recorded_at.isoformat(),
        "prev_event_sha256": events[-1]["event_sha256"] if events else ZERO_HASH,
        "payload": dict(payload),
    }
    event["event_sha256"] = _digest(event)
    events_path = _events_path(base)
    previous = events_path.read_bytes() if events_path.is_file() else b""
    atomic_write_bytes(events_path, previous + canonical_json_bytes(event) + b"\n")
    return event, True


def _read_and_verify_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    raw = path.read_bytes()
    if raw and not raw.endswith(b"\n"):
        raise TriggerHitError("trigger-hit ledger must end with a newline")
    events = []
    expected_prev = ZERO_HASH
    idempotency_keys: set[str] = set()
    event_ids: set[str] = set()
    for line_no, line in enumerate(raw.splitlines(), 1):
        if not line:
            raise TriggerHitError(f"trigger-hit ledger has a blank line at {line_no}")
        try:
            event = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TriggerHitError(f"invalid trigger-hit ledger JSON at line {line_no}") from exc
        if not isinstance(event, dict) or canonical_json_bytes(event) != line:
            raise TriggerHitError(f"trigger-hit ledger line {line_no} is not canonical JSON")
        if event.get("schema_version") != SCHEMA_VERSION or event.get("sequence") != line_no:
            raise TriggerHitError(f"trigger-hit ledger sequence is invalid at line {line_no}")
        if event.get("event_type") not in EVENT_TYPES:
            raise TriggerHitError(f"trigger-hit event type is invalid at line {line_no}")
        if event.get("prev_event_sha256") != expected_prev:
            raise TriggerHitError(f"trigger-hit hash chain is broken at line {line_no}")
        event_hash = event.get("event_sha256")
        unsigned = dict(event)
        unsigned.pop("event_sha256", None)
        if event_hash != _digest(unsigned):
            raise TriggerHitError(f"trigger-hit event hash mismatch at line {line_no}")
        event_id = event.get("event_id")
        key = event.get("idempotency_key")
        if not isinstance(key, str) or not key or key in idempotency_keys:
            raise TriggerHitError(f"trigger-hit idempotency key is invalid at line {line_no}")
        payload = event.get("payload")
        if not isinstance(payload, Mapping):
            raise TriggerHitError(f"trigger-hit payload is invalid at line {line_no}")
        expected_event_id = _logical_event_id(event["event_type"], key, payload)
        if event_id != expected_event_id or event_id in event_ids:
            raise TriggerHitError(f"trigger-hit event id is invalid at line {line_no}")
        _parse_datetime(event.get("recorded_at"), f"event[{line_no}].recorded_at")
        idempotency_keys.add(key)
        event_ids.add(event_id)
        expected_prev = event_hash
        events.append(event)
    return events


def _project(events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    hits: dict[str, dict[str, Any]] = {}
    monitors: dict[str, dict[str, Any]] = {}
    for event in events:
        event_type = event["event_type"]
        payload = event["payload"]
        if event_type == "hit_observed":
            hit_id = payload["hit_id"]
            if hit_id in hits:
                raise TriggerHitError(f"duplicate hit_id in ledger: {hit_id}")
            hits[hit_id] = {
                "hit_id": hit_id,
                "dedupe_key": payload["dedupe_key"],
                "symbol": payload["symbol"],
                "workflow_target": payload["workflow_target"],
                "trigger_ref": payload["trigger_ref"],
                "effective_at": payload["effective_at"],
                "observed_at": payload["observed_at"],
                "occurrence_evidence": payload["occurrence_evidence"],
                "state": "open",
                "observed_event_id": event["event_id"],
                "consumed_by": None,
            }
            price_monitor = payload.get("price_monitor")
            if isinstance(price_monitor, Mapping):
                monitor_key = price_monitor["monitor_key"]
                monitors[monitor_key] = {
                    "monitor_key": monitor_key,
                    "symbol": payload["symbol"],
                    "trigger_id": payload["trigger_ref"]["trigger_id"],
                    "definition_sha256": payload["trigger_ref"]["definition_sha256"],
                    "armed": False,
                    "episode": price_monitor["episode"],
                    "active_hit_id": hit_id,
                }
        elif event_type == "condition_rearmed":
            monitor_key = payload["monitor_key"]
            existing = monitors.get(monitor_key)
            if existing is None or existing["armed"]:
                raise TriggerHitError("price monitor cannot be rearmed from current state")
            existing["armed"] = True
            existing["active_hit_id"] = None
        elif event_type == "hit_consumed":
            hit_id = payload["hit_id"]
            hit = hits.get(hit_id)
            if hit is None:
                raise TriggerHitError(f"consumed hit is missing: {hit_id}")
            if hit["state"] == "consumed":
                raise TriggerHitError(f"hit is consumed more than once: {hit_id}")
            hit["state"] = "consumed"
            hit["consumed_by"] = {
                "event_id": event["event_id"],
                "package_path": payload["package_path"],
                "package_sha256": payload["package_sha256"],
                "meta_path": payload["meta_path"],
                "report_path": payload["report_path"],
                "report_sha256": payload["report_sha256"],
                "consumed_at": payload["consumed_at"],
            }
    return {
        "schema_version": SCHEMA_VERSION,
        "ledger_line_count": len(events),
        "ledger_head_sha256": events[-1]["event_sha256"] if events else ZERO_HASH,
        "hits": sorted(hits.values(), key=lambda item: (item["symbol"], item["hit_id"])),
        "price_monitors": sorted(monitors.values(), key=lambda item: item["monitor_key"]),
    }


def _load_verified(base: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    events = _read_and_verify_events(_events_path(base))
    projection = _project(events)
    state_path = _state_path(base)
    if state_path.is_file():
        try:
            existing = json.loads(state_path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TriggerHitError("trigger-hit state projection is invalid JSON") from exc
        if existing != projection or state_path.read_bytes() != canonical_json_bytes(projection):
            raise TriggerHitError("trigger-hit state projection does not match ledger replay")
    elif events:
        raise TriggerHitError("trigger-hit state projection is missing")
    return events, projection


def _write_projection(base: Path, projection: Mapping[str, Any]) -> None:
    atomic_write_bytes(_state_path(base), canonical_json_bytes(projection))


def _normalize_trigger_ref(
    value: Mapping[str, Any], *, allowed_types: set[str]
) -> dict[str, Any]:
    trigger_id = _text(value.get("trigger_id"), "trigger_id")
    trigger_type = _text(value.get("type"), "trigger type")
    if trigger_type not in allowed_types:
        raise TriggerHitError(f"trigger type is not allowed here: {trigger_type}")
    definition = _mapping(value.get("definition"), "trigger definition")
    definition_sha256 = _digest(definition)
    supplied_hash = value.get("definition_sha256")
    if supplied_hash is not None and supplied_hash != definition_sha256:
        raise TriggerHitError("trigger definition_sha256 does not match definition")
    return {
        "trigger_id": trigger_id,
        "type": trigger_type,
        "source_kind": _text(value.get("source_kind"), "trigger source_kind"),
        "definition_ref": _text(value.get("definition_ref"), "trigger definition_ref"),
        "definition_source_sha256": _sha256(
            value.get("definition_source_sha256"), "definition_source_sha256"
        ),
        "definition": dict(definition),
        "definition_sha256": definition_sha256,
    }


def _normalize_occurrence_evidence(
    value: Mapping[str, Any], *, trigger_type: str
) -> dict[str, Any]:
    kind = _text(value.get("kind"), "occurrence evidence kind")
    if kind != trigger_type:
        raise TriggerHitError("occurrence evidence kind must match trigger type")
    published_at = _parse_datetime(value.get("published_at"), "evidence published_at")
    normalized = {
        "kind": kind,
        "occurrence_key": _text(value.get("occurrence_key"), "occurrence_key"),
        "source_id": _text(value.get("source_id"), "occurrence source_id"),
        "source_ref": _text(value.get("source_ref"), "occurrence source_ref"),
        "source_sha256": _sha256(value.get("source_sha256"), "occurrence source_sha256"),
        "published_at": published_at.isoformat(),
    }
    for key in ("observed_price", "condition_met"):
        if key in value:
            normalized[key] = value[key]
    return normalized


def _schedule_effective_at(condition: Mapping[str, Any], as_of: dt.datetime) -> dt.datetime:
    due_at = condition.get("due_at")
    if isinstance(due_at, str):
        return _parse_datetime(due_at, "schedule due_at")
    date_text = condition.get("date")
    if not isinstance(date_text, str):
        raise TriggerHitError("schedule condition needs due_at or date")
    try:
        due_date = dt.date.fromisoformat(date_text)
    except ValueError as exc:
        raise TriggerHitError("schedule date must be ISO 8601") from exc
    return dt.datetime.combine(due_date, dt.time.min, tzinfo=as_of.tzinfo)


def _checkpoint_hit(hit: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "hit_id": hit["hit_id"],
        "dedupe_key": hit["dedupe_key"],
        "symbol": hit["symbol"],
        "workflow_target": hit["workflow_target"],
        "trigger_id": hit["trigger_ref"]["trigger_id"],
        "trigger_type": hit["trigger_ref"]["type"],
        "definition_sha256": hit["trigger_ref"]["definition_sha256"],
        "effective_at": hit["effective_at"],
        "observed_at": hit["observed_at"],
        "occurrence_key": hit["occurrence_evidence"]["occurrence_key"],
        "observed_event_id": hit["observed_event_id"],
    }


def _validate_checkpoint_binding(payload: Mapping[str, Any], run_id: str, scope_sha: str) -> None:
    if (
        payload.get("schema_version") != SCHEMA_VERSION
        or payload.get("run_id") != run_id
        or payload.get("scope_manifest_sha256") != scope_sha
    ):
        raise TriggerHitError("sealed checkpoint does not bind the requested frozen scope")


def _checkpoint_result(
    path: Path, sha256: str, payload: Mapping[str, Any], repository_root: Path
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": payload["run_id"],
        "checkpoint_path": _relative(path, repository_root),
        "checkpoint_sha256": sha256,
        "scope_cutoff": payload["scope_cutoff"],
        "ledger_line_count": payload["ledger_line_count"],
        "eligible_hit_count": payload["counts"]["eligible_current_run"],
        "counts": payload["counts"],
        "portfolio_action": None,
    }


def _observe_result(
    hit_id: str, event: Mapping[str, Any], idempotent: bool, deduplicated: bool
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "hit_id": hit_id,
        "state": "open",
        "event_id": event["event_id"],
        "idempotent": idempotent,
        "deduplicated": deduplicated,
        "ledger_line_count": event["sequence"],
    }


def _logical_event_id(
    event_type: str, idempotency_key: str, payload: Mapping[str, Any]
) -> str:
    return _digest(
        {
            "event_type": event_type,
            "idempotency_key": idempotency_key,
            "payload": dict(payload),
        }
    )


def _events_path(root: Path) -> Path:
    return root / LEDGER_RELATIVE_PATH


def _state_path(root: Path) -> Path:
    return root / STATE_RELATIVE_PATH


def _resolve_repository_path(path: str | Path, repository_root: Path) -> Path:
    value = Path(path)
    return value.resolve() if value.is_absolute() else (repository_root / value).resolve()


def _relative(path: Path, repository_root: Path) -> str:
    try:
        return path.resolve().relative_to(repository_root.resolve()).as_posix()
    except ValueError as exc:
        raise TriggerHitError(f"path must stay inside repository: {path}") from exc


def _read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TriggerHitError(f"{label} is not valid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise TriggerHitError(f"{label} must be an object")
    return value


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TriggerHitError(f"{label} must be an object")
    return value


def _symbol(value: Any) -> str:
    if not isinstance(value, str) or not SYMBOL_RE.fullmatch(value):
        raise TriggerHitError(f"symbol is invalid: {value}")
    return value


def _run_id(value: Any) -> str:
    if not isinstance(value, str) or not RUN_ID_RE.fullmatch(value):
        raise TriggerHitError("run_id is invalid")
    return value


def _workflow_target(value: Any) -> str:
    if value not in WORKFLOW_TARGETS:
        raise TriggerHitError(f"workflow_target is invalid: {value}")
    return str(value)


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TriggerHitError(f"{label} must be a non-empty string")
    return value.strip()


def _sha256(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise TriggerHitError(f"{label} must be a lowercase SHA-256")
    return value


def _aware(value: dt.datetime, label: str) -> dt.datetime:
    if not isinstance(value, dt.datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise TriggerHitError(f"{label} must include timezone information")
    return value


def _parse_datetime(value: Any, label: str) -> dt.datetime:
    if not isinstance(value, str):
        raise TriggerHitError(f"{label} must be an ISO timestamp")
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise TriggerHitError(f"{label} must be an ISO timestamp") from exc
    return _aware(parsed, label)


def _digest(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()
