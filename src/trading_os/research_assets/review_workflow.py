from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Mapping

from .claims import build_claim_packet
from .company import validate_company_dir, validate_research_assets
from .coverage_store import CoverageValidationError, assert_legacy_unbound_symbols
from .models import PolicyKind, ReviewRunStatus
from .policy_snapshot import (
    PolicySnapshotError,
    ReviewPolicySnapshot,
    build_policy_snapshot,
    load_review_policy_snapshot,
    policy_versions_from_snapshot,
    seal_review_policy_snapshot,
)
from .portfolio import (
    POLICY_KEYS,
    PortfolioValidationError,
    build_model_portfolio,
    portfolio_candidate_core_sha256,
)
from .review_allocation import (
    ReviewAllocationError,
    verify_review_budget_approval,
    verify_underwriting_approval,
)
from .review_store import ReviewRunStore
from .sealing import (
    atomic_write_bytes,
    canonical_json_bytes,
    seal_json,
    verify_sealed,
)


class ReviewWorkflowError(ValueError):
    """Raised when a review command cannot safely advance the workflow."""


_REPORT_META_RE = re.compile(
    r"\A<!-- trading-os-report-meta\r?\n(?P<meta>.*?)\r?\n-->\r?\n",
    re.DOTALL,
)
_TERMINAL_FAILURES = {
    ReviewRunStatus.BLOCKED_MISSING_EVIDENCE.value,
    ReviewRunStatus.FAILED_AGENT.value,
    ReviewRunStatus.FAILED_VALIDATION.value,
    ReviewRunStatus.STALE_QUOTES.value,
    ReviewRunStatus.CANCELLED.value,
}
_PACKET_REQUIRED_STATUSES = {
    ReviewRunStatus.PACKETS_READY.value,
    ReviewRunStatus.BLIND_REVIEWING.value,
    ReviewRunStatus.BLIND_SEALED.value,
    ReviewRunStatus.REVEALING.value,
    ReviewRunStatus.CHALLENGING.value,
    ReviewRunStatus.COMPANY_REVIEWS_COMPLETE.value,
    ReviewRunStatus.PORTFOLIO_CHALLENGING.value,
    ReviewRunStatus.SYNTHESIZING.value,
    ReviewRunStatus.COMPLETED.value,
}


def load_candidates(path: str | Path) -> list[dict[str, Any]]:
    candidate_path = Path(path)
    text = candidate_path.read_text(encoding="utf-8-sig")
    if candidate_path.suffix.lower() == ".jsonl":
        items: list[Any] = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ReviewWorkflowError(
                    f"invalid candidates JSONL at line {line_number}: {exc}"
                ) from exc
    else:
        try:
            items = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ReviewWorkflowError(f"invalid candidates JSON: {exc}") from exc
    if not isinstance(items, list):
        raise ReviewWorkflowError("candidate input must contain an array or JSONL objects")
    if not all(isinstance(item, dict) for item in items):
        raise ReviewWorkflowError("every candidate must be a JSON object")
    return items


def load_policy_versions(policy_root: str | Path) -> dict[str, str]:
    try:
        payload = build_policy_snapshot(policy_root, run_id="policy-version-scan")
        return policy_versions_from_snapshot(payload)
    except PolicySnapshotError as exc:
        raise ReviewWorkflowError(str(exc)) from exc


def create_review(
    *,
    runs_root: str | Path,
    run_id: str,
    scope_type: str,
    market: str,
    description: str,
    candidates: list[Mapping[str, Any]],
    policy_root: str | Path,
    created_at: dt.datetime,
    parent_run_id: str | None = None,
    coverage_root: str | Path = "coverage/cn-a",
) -> dict[str, Any]:
    """Create a legacy review with no manager-run underwriting binding."""

    repository = _repository_root_for_runs(runs_root)
    coverage = _repository_path(repository, coverage_root, "coverage_root")
    canonical_coverage = (repository / "coverage" / "cn-a").resolve()
    if coverage != canonical_coverage:
        raise ReviewWorkflowError(
            "legacy review create requires canonical coverage_root=coverage/cn-a"
        )
    candidate_symbols = []
    for candidate in candidates:
        symbol = candidate.get("symbol")
        if not isinstance(symbol, str):
            raise ReviewWorkflowError("legacy review candidate symbol is invalid")
        candidate_symbols.append(symbol)
    try:
        assert_legacy_unbound_symbols(
            coverage,
            candidate_symbols,
            operation="legacy review create",
        )
    except CoverageValidationError as exc:
        raise ReviewWorkflowError(str(exc)) from exc

    store = ReviewRunStore(runs_root)
    try:
        snapshot_payload = build_policy_snapshot(policy_root, run_id=run_id)
        policy_versions = policy_versions_from_snapshot(snapshot_payload)
    except PolicySnapshotError as exc:
        raise ReviewWorkflowError(str(exc)) from exc
    policy_snapshot_sha256 = hashlib.sha256(
        canonical_json_bytes(snapshot_payload)
    ).hexdigest()
    state = store.create_run(
        run_id,
        scope={"type": scope_type, "market": market, "description": description},
        policy_versions=policy_versions,
        policy_snapshot_sha256=policy_snapshot_sha256,
        created_at=created_at,
        parent_run_id=parent_run_id,
        intake={
            "mode": "legacy_unbound",
            "manager_screen_run_id": None,
            "coverage_root": coverage.relative_to(repository).as_posix(),
            "underwriting_approval_path": None,
            "underwriting_approval_sha256": None,
        },
    )
    try:
        seal_review_policy_snapshot(
            runs_root=runs_root,
            run_id=run_id,
            payload=snapshot_payload,
            sealed_at=created_at,
        )
        load_review_policy_snapshot(
            runs_root=runs_root,
            run_id=run_id,
            state=state,
        )
    except PolicySnapshotError as exc:
        raise ReviewWorkflowError(str(exc)) from exc
    return store.freeze_candidates(
        run_id,
        list(candidates),
        actor="cli",
        at=created_at,
    )


def create_review_from_underwriting_approval(
    *,
    runs_root: str | Path,
    coverage_root: str | Path,
    run_id: str,
    scope_type: str,
    market: str,
    description: str,
    approval_path: str,
    approval_sha256: str,
    policy_root: str | Path,
    created_at: dt.datetime,
    parent_run_id: str | None = None,
) -> dict[str, Any]:
    """Create the only manager-bound review intake from a sealed approval."""

    if (
        not isinstance(created_at, dt.datetime)
        or created_at.tzinfo is None
        or created_at.utcoffset() is None
    ):
        raise ReviewWorkflowError("created_at must include timezone information")
    if market != "CN":
        raise ReviewWorkflowError(
            "manager-bound CN-A underwriting approval requires market=CN"
        )
    repository = _repository_root_for_runs(runs_root)
    coverage = _repository_path(
        repository,
        coverage_root,
        "coverage_root",
    )
    try:
        verified = verify_underwriting_approval(
            root=coverage,
            repository_root=repository,
            approval_path=approval_path,
            approval_sha256=approval_sha256,
        )
    except ReviewAllocationError as exc:
        raise ReviewWorkflowError(str(exc)) from exc
    approval = verified["approval"]
    candidates = _approval_review_candidates(
        approval,
        repository=repository,
    )

    store = ReviewRunStore(runs_root)
    try:
        snapshot_payload = build_policy_snapshot(policy_root, run_id=run_id)
        policy_versions = policy_versions_from_snapshot(snapshot_payload)
    except PolicySnapshotError as exc:
        raise ReviewWorkflowError(str(exc)) from exc
    policy_snapshot_sha256 = hashlib.sha256(
        canonical_json_bytes(snapshot_payload)
    ).hexdigest()
    _verify_approval_policy_in_snapshot(
        approval,
        policies=snapshot_payload["policies"],
        repository=repository,
    )
    intake = {
        "mode": "underwriting_approval",
        "manager_screen_run_id": approval["manager_screen_run_id"],
        "coverage_root": coverage.relative_to(repository).as_posix(),
        "underwriting_approval_path": verified["approval_path"],
        "underwriting_approval_sha256": verified["approval_sha256"],
    }
    scope = {"type": scope_type, "market": market, "description": description}
    state_path = Path(runs_root) / run_id / "state.json"
    if state_path.exists():
        state = store.load_run(run_id)
        expected_manifest = {
            "scope": scope,
            "created_at": created_at.isoformat(),
            "policy_versions": policy_versions,
            "policy_snapshot_sha256": policy_snapshot_sha256,
            "parent_run_id": parent_run_id,
            "intake": intake,
        }
        mismatched = [
            key
            for key, expected in expected_manifest.items()
            if state.get(key) != expected
        ]
        if mismatched:
            raise ReviewWorkflowError(
                "review run conflicts with underwriting approval replay at "
                + ",".join(mismatched)
            )
    else:
        state = store.create_run(
            run_id,
            scope=scope,
            policy_versions=policy_versions,
            policy_snapshot_sha256=policy_snapshot_sha256,
            created_at=created_at,
            parent_run_id=parent_run_id,
            intake=intake,
        )
    try:
        seal_review_policy_snapshot(
            runs_root=runs_root,
            run_id=run_id,
            payload=snapshot_payload,
            sealed_at=created_at,
        )
        load_review_policy_snapshot(
            runs_root=runs_root,
            run_id=run_id,
            state=state,
        )
    except PolicySnapshotError as exc:
        raise ReviewWorkflowError(str(exc)) from exc
    frozen = store.freeze_candidates(
        run_id,
        candidates,
        actor="manager_underwriting_approval",
        at=created_at,
    )
    _verify_review_intake(
        runs_root=runs_root,
        state=frozen,
        candidates=store.read_candidates(run_id),
    )
    return frozen


def prepare_review(
    *, runs_root: str | Path, run_id: str, prepared_at: dt.datetime
) -> dict[str, Any]:
    store = ReviewRunStore(runs_root)
    state = store.load_run(run_id)
    _validated_policy_snapshot(runs_root=runs_root, run_id=run_id, state=state)
    _verify_review_intake(
        runs_root=runs_root,
        state=state,
        candidates=store.read_candidates(run_id),
    )
    if state["status"] in _TERMINAL_FAILURES:
        raise ReviewWorkflowError(f"review run is terminal: {state['status']}")
    if state["status"] in _PACKET_REQUIRED_STATUSES:
        validate_review(runs_root=runs_root, run_id=run_id, strict=False)
        return state
    if state["status"] != ReviewRunStatus.CANDIDATES_FROZEN.value:
        raise ReviewWorkflowError(
            f"review prepare requires candidates_frozen, got {state['status']}"
        )

    prepared: list[dict[str, Any]] = []
    for candidate in store.read_candidates(run_id):
        company_dir = Path(candidate["target_company_dir"])
        meta = validate_company_dir(company_dir)
        if meta["identity"]["symbol"] != candidate["symbol"]:
            raise ReviewWorkflowError(
                f"candidate symbol does not match company asset: {candidate['symbol']}"
            )
        if meta["research"]["rebaseline_required"]:
            raise ReviewWorkflowError(
                f"candidate requires research rebaseline: {candidate['symbol']}"
            )
        claims, report_hash = _load_latest_research_claims(company_dir, meta)
        packet_path = company_dir / "underwriting" / run_id / "claim-packet.json"
        packet = build_claim_packet(
            claims,
            review_id=run_id,
            packet_id=f"{run_id}-{candidate['symbol'].replace(':', '-')}",
            source_report_sha256=report_hash,
            created_at=prepared_at,
        )
        sealed = seal_json(
            packet_path,
            packet,
            artifact_type="claim_packet",
            sealed_at=prepared_at,
        )
        prepared.append(
            {
                "symbol": candidate["symbol"],
                "packet_path": packet_path.as_posix(),
                "sha256": sealed.sha256,
            }
        )

    manifest_path = Path(runs_root) / run_id / "prepared.json"
    seal_json(
        manifest_path,
        {"schema_version": 2, "run_id": run_id, "packets": prepared},
        artifact_type="review_prepared_manifest",
        sealed_at=prepared_at,
    )
    return store.transition(
        run_id,
        ReviewRunStatus.PACKETS_READY.value,
        actor="cli",
        at=prepared_at,
    )


def review_status(*, runs_root: str | Path, run_id: str) -> dict[str, Any]:
    store = ReviewRunStore(runs_root)
    state = store.load_run(run_id)
    run_dir = Path(runs_root) / run_id
    tasks: list[dict[str, Any]] = []
    task_root = run_dir / "agent_tasks"
    if task_root.is_dir():
        for path in sorted(task_root.glob("*.json")):
            raw = _read_json_object(path, "agent task")
            tasks.append(raw)
    return {
        "schema_version": 2,
        "run": state,
        "candidate_count": state["candidate_set"]["count"],
        "tasks": tasks,
        "event_count": len(store.read_events(run_id)),
    }


def request_challenger_budget(
    *,
    runs_root: str | Path,
    run_id: str,
    symbols: list[str],
    trigger: str,
    requested_by: str,
    requested_at: dt.datetime,
) -> dict[str, Any]:
    return _freeze_review_budget_request(
        runs_root=runs_root,
        run_id=run_id,
        budget_stage="challenger",
        symbols=symbols,
        trigger=trigger,
        requested_by=requested_by,
        requested_at=requested_at,
    )


def request_portfolio_synthesis_budget(
    *,
    runs_root: str | Path,
    run_id: str,
    requested_by: str,
    requested_at: dt.datetime,
) -> dict[str, Any]:
    candidates = ReviewRunStore(runs_root).read_candidates(run_id)
    return _freeze_review_budget_request(
        runs_root=runs_root,
        run_id=run_id,
        budget_stage="portfolio_synthesis",
        symbols=[str(item["symbol"]) for item in candidates],
        trigger="company_reviews_complete",
        requested_by=requested_by,
        requested_at=requested_at,
    )


def require_review_budget_approval(
    *,
    runs_root: str | Path,
    run_id: str,
    budget_stage: str,
    trigger: str,
    executor: str,
) -> dict[str, Any]:
    state = ReviewRunStore(runs_root).load_run(run_id)
    if state["intake"]["mode"] == "legacy_unbound":
        verify_review_intake(runs_root=runs_root, run_id=run_id)
        return {"legacy_unbound": True}
    request = _existing_review_budget_request(
        runs_root=runs_root,
        run_id=run_id,
        budget_stage=budget_stage,
        trigger=trigger,
    )
    repository = _repository_root_for_runs(runs_root)
    coverage = _repository_path(
        repository,
        str(state["intake"]["coverage_root"]),
        "review intake coverage_root",
    )
    try:
        return verify_review_budget_approval(
            root=coverage,
            repository_root=repository,
            budget_stage=budget_stage,
            request_path=request["request_path"],
            request_sha256=request["request_sha256"],
            executor=executor,
        )
    except ReviewAllocationError as exc:
        raise ReviewWorkflowError(str(exc)) from exc


def resume_review(
    *, runs_root: str | Path, run_id: str, resumed_at: dt.datetime
) -> dict[str, Any]:
    return ReviewRunStore(runs_root).resume(
        run_id,
        actor="cli",
        at=resumed_at,
    )


def validate_review(
    *, runs_root: str | Path, run_id: str, strict: bool
) -> dict[str, Any]:
    store = ReviewRunStore(runs_root)
    state = store.load_run(run_id)
    policy_snapshot = _validated_policy_snapshot(
        runs_root=runs_root,
        run_id=run_id,
        state=state,
    )
    candidates = store.read_candidates(run_id)
    _verify_review_intake(
        runs_root=runs_root,
        state=state,
        candidates=candidates,
    )
    events = store.read_events(run_id)
    if not events or events[-1]["to_status"] != state["status"]:
        raise ReviewWorkflowError("review event log does not match current state")
    if state["candidate_set"]["count"] != len(candidates):
        raise ReviewWorkflowError("candidate count does not match frozen snapshot")
    if strict:
        for candidate in candidates:
            validate_company_dir(candidate["target_company_dir"])
    if state["status"] in _PACKET_REQUIRED_STATUSES:
        manifest_path = Path(runs_root) / run_id / "prepared.json"
        manifest_seal = verify_sealed(manifest_path)
        if manifest_seal.artifact_type != "review_prepared_manifest":
            raise ReviewWorkflowError("prepared manifest has the wrong artifact type")
        manifest = _read_json_object(manifest_path, "prepared manifest")
        packets = manifest.get("packets")
        if not isinstance(packets, list) or len(packets) != len(candidates):
            raise ReviewWorkflowError("prepared manifest does not cover all candidates")
        expected_symbols = {item["symbol"] for item in candidates}
        actual_symbols: set[str] = set()
        for item in packets:
            if not isinstance(item, dict):
                raise ReviewWorkflowError("prepared packet record must be an object")
            actual_symbols.add(str(item.get("symbol")))
            sealed = verify_sealed(str(item.get("packet_path")))
            if sealed.artifact_type != "claim_packet" or sealed.sha256 != item.get("sha256"):
                raise ReviewWorkflowError("claim packet seal does not match prepared manifest")
        if actual_symbols != expected_symbols:
            raise ReviewWorkflowError("prepared manifest candidate coverage mismatch")
    return {
        "schema_version": 2,
        "ok": True,
        "run_id": run_id,
        "status": state["status"],
        "strict": strict,
        "candidate_count": len(candidates),
        "event_count": len(events),
        "policy_snapshot_sha256": policy_snapshot.sha256,
    }


def synthesize_review(
    *,
    runs_root: str | Path,
    research_root: str | Path,
    policy_root: str | Path,
    run_id: str,
    quotes_path: str | Path,
    synthesized_at: dt.datetime,
) -> dict[str, Any]:
    store = ReviewRunStore(runs_root)
    state = store.load_run(run_id)
    policy_snapshot = _validated_policy_snapshot(
        runs_root=runs_root,
        run_id=run_id,
        state=state,
    )
    if state["status"] != ReviewRunStatus.COMPANY_REVIEWS_COMPLETE.value:
        raise ReviewWorkflowError(
            "review synthesize requires company_reviews_complete, "
            f"got {state['status']}"
        )
    validate_review(runs_root=runs_root, run_id=run_id, strict=True)
    if state["intake"]["mode"] == "underwriting_approval":
        request = request_portfolio_synthesis_budget(
            runs_root=runs_root,
            run_id=run_id,
            requested_by="cli",
            requested_at=synthesized_at,
        )
        try:
            require_review_budget_approval(
                runs_root=runs_root,
                run_id=run_id,
                budget_stage="portfolio_synthesis",
                trigger="company_reviews_complete",
                executor="cli",
            )
        except ReviewWorkflowError as exc:
            if str(exc) != "explicit manager portfolio_synthesis approval is required":
                raise
            return {
                "schema_version": 2,
                "run_id": run_id,
                "status": ReviewRunStatus.COMPANY_REVIEWS_COMPLETE.value,
                "approval_required": True,
                **request,
            }
    quotes_raw = _read_json(Path(quotes_path), "quote snapshot")
    if not isinstance(quotes_raw, list):
        raise ReviewWorkflowError("quote snapshot must be a JSON array")
    quotes: dict[str, float] = {}
    quote_times: dict[str, dt.datetime] = {}
    for item in quotes_raw:
        if not isinstance(item, dict) or set(item) < {"symbol", "price", "as_of"}:
            raise ReviewWorkflowError("each quote must contain symbol, price, and as_of")
        symbol = str(item["symbol"])
        price = item["price"]
        if (
            isinstance(price, bool)
            or not isinstance(price, (int, float))
            or not math.isfinite(float(price))
            or price <= 0
        ):
            raise ReviewWorkflowError(f"invalid quote price for {symbol}")
        if symbol in quotes:
            raise ReviewWorkflowError(f"duplicate quote symbol: {symbol}")
        quotes[symbol] = float(price)
        quote_times[symbol] = _parse_aware_datetime(item["as_of"], f"quote {symbol} as_of")

    stale_symbols = sorted(
        symbol
        for symbol, quote_time in quote_times.items()
        if synthesized_at - quote_time > dt.timedelta(days=3)
        or quote_time - synthesized_at > dt.timedelta(minutes=5)
    )
    if stale_symbols:
        store.transition(
            run_id,
            ReviewRunStatus.STALE_QUOTES.value,
            actor="cli",
            at=synthesized_at,
            reason=f"stale quote snapshot: {','.join(stale_symbols)}",
        )
        raise ReviewWorkflowError(
            f"quote snapshot is stale for: {', '.join(stale_symbols)}"
        )

    try:
        portfolio_policy = policy_snapshot.require_kind(PolicyKind.PORTFOLIO)
    except PolicySnapshotError as exc:
        raise ReviewWorkflowError(str(exc)) from exc
    policy = {
        key: portfolio_policy["payload"][key]
        for key in POLICY_KEYS
    }
    stale_threshold = float(
        portfolio_policy["payload"]["price_change_stale_threshold"]
    )

    candidates: list[dict[str, Any]] = []
    candidate_hashes: dict[str, str] = {}
    for item in store.read_candidates(run_id):
        symbol = item["symbol"]
        if symbol not in quotes:
            raise ReviewWorkflowError(f"quote snapshot is missing candidate: {symbol}")
        candidate_path = _active_portfolio_candidate_path(
            Path(item["target_company_dir"]),
            run_id,
        )
        sealed = verify_sealed(candidate_path)
        if sealed.artifact_type != "portfolio_candidate":
            raise ReviewWorkflowError(f"invalid portfolio candidate type: {symbol}")
        candidate_hashes[symbol] = sealed.sha256
        candidate = _read_json_object(candidate_path, "portfolio candidate")
        if candidate.get("symbol") != symbol:
            raise ReviewWorkflowError(f"portfolio candidate symbol mismatch: {symbol}")
        if candidate.get("policy_snapshot_sha256") != policy_snapshot.sha256:
            raise ReviewWorkflowError(
                f"portfolio candidate policy snapshot mismatch: {symbol}"
            )
        decision_filename = (
            "final-underwriting-decision.json"
            if candidate_path.name == "portfolio-candidate.final.json"
            else "primary-evaluation.json"
        )
        decision_path = candidate_path.with_name(decision_filename)
        decision_seal = verify_sealed(decision_path)
        if (
            decision_seal.artifact_type
            != "machine_underwriting_evaluation"
            or decision_seal.sha256
            != candidate.get("source_machine_decision_sha256")
        ):
            raise ReviewWorkflowError(
                f"portfolio candidate machine decision mismatch: {symbol}"
            )
        machine_decision = _read_json_object(
            decision_path,
            "machine underwriting decision",
        )
        if (
            machine_decision.get("symbol") != symbol
            or machine_decision.get("status")
            != candidate.get("underwriting_status")
            or machine_decision.get("policy_snapshot_sha256")
            != policy_snapshot.sha256
        ):
            raise ReviewWorkflowError(
                f"portfolio candidate decision fields diverge: {symbol}"
            )
        _validate_candidate_binding(
            run_id=run_id,
            candidate_path=candidate_path,
            candidate=candidate,
            machine_decision=machine_decision,
            policy_snapshot_sha256=policy_snapshot.sha256,
        )
        prior_price = candidate["current_price"]
        candidate["_previous_price"] = prior_price
        candidate["current_price"] = quotes[symbol]
        candidate["price_as_of"] = quote_times[symbol].isoformat()
        candidates.append(candidate)

    for candidate in candidates:
        previous = float(candidate.pop("_previous_price", candidate["current_price"]))
        if previous > 0 and abs(candidate["current_price"] / previous - 1) >= stale_threshold:
            candidate["evidence_stale"] = True
            candidate["reason_codes"] = sorted(
                {*candidate["reason_codes"], "price_change_invalidated_conclusion"}
            )
    result = build_model_portfolio(candidates, policy=policy)
    if result.challenger_required_symbols:
        if state["intake"]["mode"] == "underwriting_approval":
            request = request_challenger_budget(
                runs_root=runs_root,
                run_id=run_id,
                symbols=list(result.challenger_required_symbols),
                trigger="portfolio_top_five",
                requested_by="cli",
                requested_at=synthesized_at,
            )
            store.transition(
                run_id,
                ReviewRunStatus.PORTFOLIO_CHALLENGING.value,
                actor="cli",
                at=synthesized_at,
                reason=(
                    "actual top-five allocation requires approved independent "
                    "challenger: "
                    + ",".join(result.challenger_required_symbols)
                ),
            )
            return {
                "schema_version": 2,
                "run_id": run_id,
                "status": ReviewRunStatus.PORTFOLIO_CHALLENGING.value,
                "approval_required": True,
                **request,
            }
        request_payload = {
            "schema_version": 3,
            "run_id": run_id,
            "requested_at": synthesized_at.isoformat(),
            "quote_snapshot_sha256": hashlib.sha256(
                canonical_json_bytes(quotes_raw)
            ).hexdigest(),
            "policy_snapshot_sha256": policy_snapshot.sha256,
            "candidates": [
                {
                    "symbol": symbol,
                    "primary_candidate_sha256": candidate_hashes[symbol],
                }
                for symbol in result.challenger_required_symbols
            ],
        }
        request_id = hashlib.sha256(
            canonical_json_bytes(request_payload)
        ).hexdigest()
        request_artifact = seal_json(
            Path(runs_root)
            / run_id
            / "portfolio_challenger_requests"
            / f"{request_id}.json",
            request_payload,
            artifact_type="portfolio_challenger_request",
            sealed_at=synthesized_at,
        )
        store.transition(
            run_id,
            ReviewRunStatus.PORTFOLIO_CHALLENGING.value,
            actor="cli",
            at=synthesized_at,
            reason=(
                "actual top-five allocation requires independent challenger: "
                + ",".join(result.challenger_required_symbols)
            ),
        )
        return {
            "schema_version": 2,
            "run_id": run_id,
            "status": ReviewRunStatus.PORTFOLIO_CHALLENGING.value,
            "challenger_request_path": request_artifact.path.as_posix(),
            "challenger_request_sha256": request_artifact.sha256,
            "symbols": list(result.challenger_required_symbols),
        }
    batch_dir = Path(research_root) / "batches" / run_id
    quote_artifact = seal_json(
        batch_dir / "quotes.json",
        quotes_raw,
        artifact_type="quote_snapshot",
        sealed_at=synthesized_at,
    )
    portfolio = {
        "schema_version": 3,
        "portfolio_id": f"model-{run_id}",
        "run_id": run_id,
        "as_of": synthesized_at.isoformat(),
        "quote_snapshot_sha256": quote_artifact.sha256,
        "policy_snapshot_sha256": policy_snapshot.sha256,
        "policy_versions": state["policy_versions"],
        "positions": [
            {
                **_decision_payload(item),
                "portfolio_candidate_sha256": candidate_hashes[item.symbol],
            }
            for item in result.decisions
        ],
        "cash_weight": result.cash_weight,
        "exclusions": [
            {
                "symbol": item.symbol,
                "action": item.action,
                "reason_codes": list(item.reason_codes),
            }
            for item in result.exclusions
        ],
    }
    _validate_portfolio_payload(
        portfolio,
        expected_policy_snapshot_sha256=policy_snapshot.sha256,
    )
    sealed_portfolio = seal_json(
        batch_dir / "portfolio.json",
        portfolio,
        artifact_type="model_portfolio",
        sealed_at=synthesized_at,
    )
    store.transition(
        run_id,
        ReviewRunStatus.SYNTHESIZING.value,
        actor="cli",
        at=synthesized_at,
    )
    return {
        "schema_version": 2,
        "run_id": run_id,
        "status": ReviewRunStatus.SYNTHESIZING.value,
        "portfolio_path": sealed_portfolio.path.as_posix(),
        "portfolio_sha256": sealed_portfolio.sha256,
        "position_count": len(result.decisions),
        "cash_weight": result.cash_weight,
    }


def write_review_report(
    *,
    runs_root: str | Path,
    research_root: str | Path,
    run_id: str,
    reported_at: dt.datetime,
) -> dict[str, Any]:
    store = ReviewRunStore(runs_root)
    state = store.load_run(run_id)
    if state["status"] == ReviewRunStatus.COMPLETED.value:
        path = Path(research_root) / "batches" / run_id / "synthesis.md"
        if not path.is_file():
            raise ReviewWorkflowError("completed review is missing synthesis.md")
        finalization = finalize_review_companies(
            runs_root=runs_root,
            research_root=research_root,
            run_id=run_id,
            finalized_at=reported_at,
        )
        return {
            "schema_version": 2,
            "run_id": run_id,
            "status": "completed",
            "path": path.as_posix(),
            "company_finalization": finalization,
        }
    if state["status"] != ReviewRunStatus.SYNTHESIZING.value:
        raise ReviewWorkflowError(
            f"review report requires synthesizing, got {state['status']}"
        )
    batch_dir = Path(research_root) / "batches" / run_id
    portfolio_seal = verify_sealed(batch_dir / "portfolio.json")
    if portfolio_seal.artifact_type != "model_portfolio":
        raise ReviewWorkflowError("portfolio artifact type is invalid")
    portfolio = _read_json_object(batch_dir / "portfolio.json", "portfolio")
    policy_snapshot = _validated_policy_snapshot(
        runs_root=runs_root,
        run_id=run_id,
        state=state,
    )
    _validate_portfolio_payload(
        portfolio,
        expected_policy_snapshot_sha256=policy_snapshot.sha256,
    )
    lines = _portfolio_report_lines(
        portfolio,
        run_id=run_id,
        reported_at=reported_at,
    )
    content = "\n".join(lines).encode("utf-8")
    path = batch_dir / "synthesis.md"
    if path.exists() and path.read_bytes() != content:
        raise ReviewWorkflowError(f"synthesis report is immutable: {path}")
    atomic_write_bytes(path, content)
    digest = hashlib.sha256(content).hexdigest()
    seal_json(
        batch_dir / "synthesis-manifest.json",
        {
            "schema_version": 2,
            "run_id": run_id,
            "path": path.name,
            "sha256": digest,
            "portfolio_sha256": portfolio_seal.sha256,
        },
        artifact_type="portfolio_synthesis_manifest",
        sealed_at=reported_at,
    )
    store.transition(
        run_id,
        ReviewRunStatus.COMPLETED.value,
        actor="cli",
        at=reported_at,
    )
    finalization = finalize_review_companies(
        runs_root=runs_root,
        research_root=research_root,
        run_id=run_id,
        finalized_at=reported_at,
    )
    return {
        "schema_version": 2,
        "run_id": run_id,
        "status": ReviewRunStatus.COMPLETED.value,
        "path": path.as_posix(),
        "sha256": digest,
        "company_finalization": finalization,
    }


def finalize_review_companies(
    *,
    runs_root: str | Path,
    research_root: str | Path,
    run_id: str,
    finalized_at: dt.datetime,
) -> dict[str, Any]:
    """Publish a completed batch's final underwriting state to company metadata.

    The sealed batch remains the decision source of truth.  Company ``meta.json``
    files are mutable projections used by indexes, schedules, and alerts.  A
    sealed finalization receipt makes the projection idempotent and auditable.
    """
    if finalized_at.tzinfo is None or finalized_at.utcoffset() is None:
        raise ReviewWorkflowError("finalized_at must include a UTC offset")

    store = ReviewRunStore(runs_root)
    state = store.load_run(run_id)
    if state["status"] != ReviewRunStatus.COMPLETED.value:
        raise ReviewWorkflowError(
            f"review finalization requires completed, got {state['status']}"
        )

    batch_dir = Path(research_root) / "batches" / run_id
    portfolio_path = batch_dir / "portfolio.json"
    portfolio_seal = verify_sealed(portfolio_path)
    if portfolio_seal.artifact_type != "model_portfolio":
        raise ReviewWorkflowError("portfolio artifact type is invalid")
    portfolio = _read_json_object(portfolio_path, "portfolio")
    if portfolio.get("run_id") != run_id:
        raise ReviewWorkflowError("portfolio run_id does not match review run")
    policy_snapshot = _validated_policy_snapshot(
        runs_root=runs_root,
        run_id=run_id,
        state=state,
    )
    _validate_portfolio_payload(
        portfolio,
        expected_policy_snapshot_sha256=policy_snapshot.sha256,
    )

    receipt_path = batch_dir / "company-finalization.json"
    candidates = store.read_candidates(run_id)
    if receipt_path.exists():
        return _validate_finalization_receipt(
            receipt_path=receipt_path,
            run_id=run_id,
            candidates=candidates,
        )

    quote_path = batch_dir / "quotes.json"
    quote_seal = verify_sealed(quote_path)
    if quote_seal.artifact_type != "quote_snapshot":
        raise ReviewWorkflowError("quote snapshot artifact type is invalid")
    quotes_raw = _read_json(quote_path, "quote snapshot")
    if not isinstance(quotes_raw, list):
        raise ReviewWorkflowError("quote snapshot must be an array")
    quote_times: dict[str, str] = {}
    for item in quotes_raw:
        if not isinstance(item, dict):
            raise ReviewWorkflowError("quote snapshot item must be an object")
        symbol = str(item.get("symbol"))
        if symbol in quote_times:
            raise ReviewWorkflowError(f"duplicate quote symbol: {symbol}")
        quote_time = _parse_aware_datetime(
            item.get("as_of"), f"quote {symbol} as_of"
        )
        quote_times[symbol] = quote_time.isoformat()

    positions_raw = portfolio.get("positions")
    if not isinstance(positions_raw, list):
        raise ReviewWorkflowError("portfolio positions must be an array")
    positions: dict[str, dict[str, Any]] = {}
    for item in positions_raw:
        if not isinstance(item, dict):
            raise ReviewWorkflowError("portfolio position must be an object")
        symbol = str(item.get("symbol"))
        if symbol in positions:
            raise ReviewWorkflowError(f"duplicate portfolio symbol: {symbol}")
        positions[symbol] = item

    candidate_symbols = {str(item["symbol"]) for item in candidates}
    if set(positions) != candidate_symbols:
        raise ReviewWorkflowError("portfolio does not cover the frozen candidate set")
    if set(quote_times) != candidate_symbols:
        raise ReviewWorkflowError("quote snapshot does not cover the frozen candidate set")

    planned: list[tuple[Path, dict[str, Any]]] = []
    portfolio_as_of = _parse_aware_datetime(portfolio.get("as_of"), "portfolio as_of")
    for candidate in candidates:
        symbol = str(candidate["symbol"])
        company_dir = Path(candidate["target_company_dir"])
        meta = validate_company_dir(company_dir)
        if meta["identity"]["symbol"] != symbol:
            raise ReviewWorkflowError(f"company symbol mismatch: {symbol}")

        source_candidate_path = _active_portfolio_candidate_path(
            company_dir,
            run_id,
        )
        source_seal = verify_sealed(source_candidate_path)
        if source_seal.artifact_type != "portfolio_candidate":
            raise ReviewWorkflowError(f"portfolio candidate type is invalid: {symbol}")
        source_candidate = _read_json_object(
            source_candidate_path, "portfolio candidate"
        )
        decision = positions[symbol]
        if source_candidate.get("symbol") != symbol:
            raise ReviewWorkflowError(f"portfolio candidate symbol mismatch: {symbol}")
        if source_candidate.get("underwriting_status") != decision.get(
            "underwriting_status"
        ):
            raise ReviewWorkflowError(
                f"portfolio underwriting status diverges from candidate: {symbol}"
            )
        if source_seal.sha256 != decision.get("portfolio_candidate_sha256"):
            raise ReviewWorkflowError(
                f"portfolio candidate SHA-256 diverges: {symbol}"
            )
        if source_candidate.get("policy_snapshot_sha256") != policy_snapshot.sha256:
            raise ReviewWorkflowError(
                f"portfolio candidate policy snapshot diverges: {symbol}"
            )

        prior_review_id = meta["underwriting"]["review_id"]
        meta_updated_at = _parse_aware_datetime(
            meta.get("updated_at"), f"{symbol} meta.updated_at"
        )
        if (
            prior_review_id not in {None, run_id}
            and meta_updated_at > portfolio_as_of
        ):
            raise ReviewWorkflowError(
                f"refusing to replace newer underwriting state for {symbol}: "
                f"{prior_review_id}"
            )

        underwriting_status = str(decision.get("underwriting_status"))
        reason_codes = [str(value) for value in decision.get("reason_codes", [])]
        if bool(decision.get("evidence_stale", source_candidate["evidence_stale"])):
            if underwriting_status == "passed":
                underwriting_status = "stale"
            reason_codes.append("evidence_stale_at_finalization")

        updated = copy.deepcopy(meta)
        updated["research"].update(
            {"coverage_status": "covered", "rebaseline_required": False}
        )
        updated["underwriting"] = {
            "status": underwriting_status,
            "review_id": run_id,
            "confidence": decision.get("confidence"),
            "evidence_valid_until": None,
            "reason_codes": sorted(set(reason_codes)),
        }
        updated["valuation"] = {
            "currency": meta["identity"]["currency"],
            "price_as_of": quote_times[symbol],
            "bear_value": decision.get("bear_value"),
            "fair_value_range": decision.get("fair_value_range"),
            "buy_zone": decision.get("buy_zone"),
            "reduce_zone": decision.get("reduce_zone", source_candidate["reduce_zone"]),
        }
        updated["updated_at"] = finalized_at.isoformat()
        planned.append((company_dir / "meta.json", updated))

    records: list[dict[str, Any]] = []
    for meta_path, updated in planned:
        content = _pretty_json_bytes(updated)
        atomic_write_bytes(meta_path, content)
        validated = validate_company_dir(meta_path.parent)
        records.append(
            {
                "symbol": validated["identity"]["symbol"],
                "meta_path": meta_path.as_posix(),
                "meta_sha256": hashlib.sha256(content).hexdigest(),
                "underwriting_status": validated["underwriting"]["status"],
            }
        )

    receipt = {
        "schema_version": 2,
        "run_id": run_id,
        "finalized_at": finalized_at.isoformat(),
        "portfolio_sha256": portfolio_seal.sha256,
        "quote_snapshot_sha256": quote_seal.sha256,
        "companies": sorted(records, key=lambda item: item["symbol"]),
    }
    seal_json(
        receipt_path,
        receipt,
        artifact_type="company_finalization",
        sealed_at=finalized_at,
    )
    return {
        "run_id": run_id,
        "synced_count": len(records),
        "already_finalized": False,
        "receipt_path": receipt_path.as_posix(),
    }


def _validate_finalization_receipt(
    *,
    receipt_path: Path,
    run_id: str,
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    receipt_seal = verify_sealed(receipt_path)
    if receipt_seal.artifact_type != "company_finalization":
        raise ReviewWorkflowError("company finalization receipt type is invalid")
    receipt = _read_json_object(receipt_path, "company finalization receipt")
    if receipt.get("run_id") != run_id:
        raise ReviewWorkflowError("company finalization receipt run_id mismatch")
    records = receipt.get("companies")
    if not isinstance(records, list):
        raise ReviewWorkflowError("company finalization companies must be an array")
    expected_paths = {
        str(item["symbol"]): Path(item["target_company_dir"]) / "meta.json"
        for item in candidates
    }
    if {str(item.get("symbol")) for item in records if isinstance(item, dict)} != set(
        expected_paths
    ):
        raise ReviewWorkflowError("company finalization candidate coverage mismatch")
    for item in records:
        if not isinstance(item, dict):
            raise ReviewWorkflowError("company finalization record must be an object")
        symbol = str(item["symbol"])
        meta_path = expected_paths[symbol]
        if not meta_path.is_file():
            raise ReviewWorkflowError(f"finalized company meta is missing: {symbol}")
        actual_hash = hashlib.sha256(meta_path.read_bytes()).hexdigest()
        if actual_hash != item.get("meta_sha256"):
            raise ReviewWorkflowError(f"finalized company meta drifted: {symbol}")
        meta = validate_company_dir(meta_path.parent)
        if meta["underwriting"]["review_id"] != run_id:
            raise ReviewWorkflowError(f"company review_id drifted: {symbol}")
    return {
        "run_id": run_id,
        "synced_count": len(records),
        "already_finalized": True,
        "receipt_path": receipt_path.as_posix(),
    }


def run_review(
    *,
    runs_root: str | Path,
    research_root: str | Path,
    policy_root: str | Path,
    run_id: str,
    quotes_path: str | Path | None,
    now: dt.datetime,
) -> dict[str, Any]:
    store = ReviewRunStore(runs_root)
    state = store.load_run(run_id)
    if state["status"] == ReviewRunStatus.CANDIDATES_FROZEN.value:
        state = prepare_review(runs_root=runs_root, run_id=run_id, prepared_at=now)
    if state["status"] == ReviewRunStatus.COMPANY_REVIEWS_COMPLETE.value:
        if quotes_path is None:
            raise ReviewWorkflowError("--quotes is required once company reviews are complete")
        synthesize_review(
            runs_root=runs_root,
            research_root=research_root,
            policy_root=policy_root,
            run_id=run_id,
            quotes_path=quotes_path,
            synthesized_at=now,
        )
        state = store.load_run(run_id)
    if state["status"] == ReviewRunStatus.SYNTHESIZING.value:
        return write_review_report(
            runs_root=runs_root,
            research_root=research_root,
            run_id=run_id,
            reported_at=now,
        )
    return {
        "schema_version": 2,
        "run_id": run_id,
        "status": state["status"],
        "next_action": _next_action(state["status"]),
    }


def validate_all_assets(research_root: str | Path) -> dict[str, Any]:
    result = validate_research_assets(research_root)
    return {"ok": result["invalid_count"] == 0, **result}


def _verify_review_intake(
    *,
    runs_root: str | Path,
    state: Mapping[str, Any],
    candidates: list[Mapping[str, Any]],
) -> None:
    intake = state.get("intake")
    if not isinstance(intake, Mapping):
        raise ReviewWorkflowError("review intake binding is missing")
    mode = intake.get("mode")
    if mode == "legacy_unbound":
        repository = _repository_root_for_runs(runs_root)
        coverage_root = intake.get("coverage_root") or "coverage/cn-a"
        coverage = _repository_path(
            repository,
            str(coverage_root),
            "review intake coverage_root",
        )
        if coverage != (repository / "coverage" / "cn-a").resolve():
            raise ReviewWorkflowError(
                "legacy review intake must use canonical coverage/cn-a provenance"
            )
        try:
            assert_legacy_unbound_symbols(
                coverage,
                [str(candidate.get("symbol")) for candidate in candidates],
                operation="legacy review",
            )
        except CoverageValidationError as exc:
            raise ReviewWorkflowError(str(exc)) from exc
        return
    if mode != "underwriting_approval":
        raise ReviewWorkflowError(f"unsupported review intake mode: {mode}")
    repository = _repository_root_for_runs(runs_root)
    coverage = _repository_path(
        repository,
        str(intake.get("coverage_root")),
        "review intake coverage_root",
    )
    try:
        verified = verify_underwriting_approval(
            root=coverage,
            repository_root=repository,
            approval_path=str(intake.get("underwriting_approval_path")),
            approval_sha256=str(intake.get("underwriting_approval_sha256")),
        )
    except ReviewAllocationError as exc:
        raise ReviewWorkflowError(str(exc)) from exc
    approval = verified["approval"]
    policy_snapshot = load_review_policy_snapshot(
        runs_root=runs_root,
        run_id=str(state["run_id"]),
        state=state,
    )
    _verify_approval_policy_in_snapshot(
        approval,
        policies=policy_snapshot.policies,
        repository=repository,
    )
    if approval.get("manager_screen_run_id") != intake.get(
        "manager_screen_run_id"
    ):
        raise ReviewWorkflowError(
            "review intake manager_screen_run_id does not match approval"
        )
    expected = _approval_review_candidates(approval, repository=repository)
    if list(candidates) != expected:
        raise ReviewWorkflowError(
            "review candidate snapshot does not match underwriting approval"
        )


def verify_review_intake(
    *,
    runs_root: str | Path,
    run_id: str,
) -> dict[str, Any]:
    """Revalidate review provenance before external dispatch or budget bypass."""

    store = ReviewRunStore(runs_root)
    state = store.load_run(run_id)
    _verify_review_intake(
        runs_root=runs_root,
        state=state,
        candidates=store.read_candidates(run_id),
    )
    return state


def _freeze_review_budget_request(
    *,
    runs_root: str | Path,
    run_id: str,
    budget_stage: str,
    symbols: list[str],
    trigger: str,
    requested_by: str,
    requested_at: dt.datetime,
) -> dict[str, Any]:
    if (
        not isinstance(requested_at, dt.datetime)
        or requested_at.tzinfo is None
        or requested_at.utcoffset() is None
    ):
        raise ReviewWorkflowError("requested_at must include timezone information")
    if budget_stage not in {"challenger", "portfolio_synthesis"}:
        raise ReviewWorkflowError(f"unsupported review budget stage: {budget_stage}")
    if not isinstance(trigger, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", trigger
    ):
        raise ReviewWorkflowError("review budget trigger is invalid")
    if not isinstance(requested_by, str) or not requested_by.strip():
        raise ReviewWorkflowError("review budget requested_by is required")

    store = ReviewRunStore(runs_root)
    state = store.load_run(run_id)
    if state["intake"]["mode"] != "underwriting_approval":
        raise ReviewWorkflowError(
            "explicit review budget requests require manager-bound intake"
        )
    candidates = store.read_candidates(run_id)
    _verify_review_intake(
        runs_root=runs_root,
        state=state,
        candidates=candidates,
    )
    by_symbol = {str(item["symbol"]): item for item in candidates}
    normalized_symbols = sorted(set(symbols))
    if not normalized_symbols or len(normalized_symbols) != len(symbols):
        raise ReviewWorkflowError(
            "review budget request symbols must be non-empty and unique"
        )
    missing = sorted(set(normalized_symbols) - set(by_symbol))
    if missing:
        raise ReviewWorkflowError(
            f"review budget request contains unknown symbols: {missing}"
        )

    repository = _repository_root_for_runs(runs_root)
    items: list[dict[str, Any]] = []
    for symbol in normalized_symbols:
        company_dir = Path(str(by_symbol[symbol]["target_company_dir"]))
        candidate_path = _active_portfolio_candidate_path(company_dir, run_id)
        decision_path = candidate_path.with_name(
            "final-underwriting-decision.json"
            if candidate_path.name == "portfolio-candidate.final.json"
            else "primary-evaluation.json"
        )
        try:
            candidate_seal = verify_sealed(candidate_path)
            decision_seal = verify_sealed(decision_path)
        except Exception as exc:
            raise ReviewWorkflowError(
                f"review budget evidence is not validly sealed: {symbol}"
            ) from exc
        if candidate_seal.artifact_type != "portfolio_candidate":
            raise ReviewWorkflowError(
                f"review budget candidate artifact type is invalid: {symbol}"
            )
        if decision_seal.artifact_type != "machine_underwriting_evaluation":
            raise ReviewWorkflowError(
                f"review budget evaluation artifact type is invalid: {symbol}"
            )
        candidate_payload = _read_json_object(
            candidate_path,
            "review budget portfolio candidate",
        )
        decision_payload = _read_json_object(
            decision_path,
            "review budget machine evaluation",
        )
        if (
            candidate_payload.get("symbol") != symbol
            or decision_payload.get("symbol") != symbol
            or candidate_payload.get("source_machine_decision_sha256")
            != decision_seal.sha256
        ):
            raise ReviewWorkflowError(
                f"review budget candidate/evaluation binding is invalid: {symbol}"
            )
        items.append(
            {
                "symbol": symbol,
                "evaluation": {
                    "path": _relative_repository_path(
                        decision_path,
                        repository=repository,
                    ),
                    "sha256": decision_seal.sha256,
                },
                "candidate": {
                    "path": _relative_repository_path(
                        candidate_path,
                        repository=repository,
                    ),
                    "sha256": candidate_seal.sha256,
                },
            }
        )

    existing = _existing_review_budget_request(
        runs_root=runs_root,
        run_id=run_id,
        budget_stage=budget_stage,
        trigger=trigger,
        required=False,
    )
    intake = state["intake"]
    expected_binding = {
        "path": str(intake["underwriting_approval_path"]),
        "sha256": str(intake["underwriting_approval_sha256"]),
    }
    if existing is not None:
        payload = existing["request"]
        if (
            payload["manager_screen_run_id"]
            != intake["manager_screen_run_id"]
            or payload["underwriting_approval"] != expected_binding
            or payload["items"] != items
        ):
            raise ReviewWorkflowError(
                f"existing {budget_stage} request conflicts with current evidence"
            )
        return {
            key: value
            for key, value in existing.items()
            if key != "request"
        }

    request_core = {
        "manager_screen_run_id": intake["manager_screen_run_id"],
        "review_run_id": run_id,
        "budget_stage": budget_stage,
        "trigger": trigger,
        "underwriting_approval": expected_binding,
        "items": items,
    }
    request_id = hashlib.sha256(canonical_json_bytes(request_core)).hexdigest()[:24]
    payload = {
        "schema_version": 1,
        "request_id": request_id,
        **request_core,
        "requested_by": requested_by.strip(),
        "requested_at": requested_at.isoformat(),
    }
    artifact_type = (
        "manager_run_challenger_request"
        if budget_stage == "challenger"
        else "manager_run_portfolio_synthesis_request"
    )
    target = (
        Path(runs_root)
        / run_id
        / "budget_requests"
        / budget_stage
        / trigger
        / f"{request_id}.json"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    sealed = seal_json(
        target,
        payload,
        artifact_type=artifact_type,
        sealed_at=requested_at,
    )
    return {
        "request_path": _relative_repository_path(
            sealed.path,
            repository=repository,
        ),
        "request_sha256": sealed.sha256,
        "budget_stage": budget_stage,
        "trigger": trigger,
        "symbols": normalized_symbols,
    }


def _existing_review_budget_request(
    *,
    runs_root: str | Path,
    run_id: str,
    budget_stage: str,
    trigger: str,
    required: bool = True,
) -> dict[str, Any] | None:
    request_dir = (
        Path(runs_root)
        / run_id
        / "budget_requests"
        / budget_stage
        / trigger
    )
    paths = (
        sorted(
            path
            for path in request_dir.glob("*.json")
            if not path.name.endswith(".seal.json")
        )
        if request_dir.is_dir()
        else []
    )
    if not paths:
        if required:
            raise ReviewWorkflowError(
                f"{budget_stage} budget request is missing for trigger {trigger}"
            )
        return None
    if len(paths) != 1:
        raise ReviewWorkflowError(
            f"{budget_stage} budget request is ambiguous for trigger {trigger}"
        )
    path = paths[0]
    expected_type = (
        "manager_run_challenger_request"
        if budget_stage == "challenger"
        else "manager_run_portfolio_synthesis_request"
    )
    try:
        sealed = verify_sealed(path)
    except Exception as exc:
        raise ReviewWorkflowError(
            f"{budget_stage} budget request is not validly sealed"
        ) from exc
    if sealed.artifact_type != expected_type:
        raise ReviewWorkflowError(
            f"{budget_stage} budget request artifact type is invalid"
        )
    payload = _read_json_object(path, f"{budget_stage} budget request")
    required_keys = {
        "schema_version",
        "request_id",
        "manager_screen_run_id",
        "review_run_id",
        "budget_stage",
        "trigger",
        "requested_by",
        "requested_at",
        "underwriting_approval",
        "items",
    }
    if (
        set(payload) != required_keys
        or payload.get("schema_version") != 1
        or payload.get("review_run_id") != run_id
        or payload.get("budget_stage") != budget_stage
        or payload.get("trigger") != trigger
        or _parse_aware_datetime(
            payload.get("requested_at"),
            "review budget request requested_at",
        )
        != sealed.sealed_at
    ):
        raise ReviewWorkflowError(
            f"{budget_stage} budget request contract is invalid"
        )
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise ReviewWorkflowError(
            f"{budget_stage} budget request has no items"
        )
    return {
        "request_path": _relative_repository_path(
            path,
            repository=_repository_root_for_runs(runs_root),
        ),
        "request_sha256": sealed.sha256,
        "budget_stage": budget_stage,
        "trigger": trigger,
        "symbols": [str(item.get("symbol")) for item in items],
        "request": payload,
    }


def _relative_repository_path(path: Path, *, repository: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(repository).as_posix()
    except ValueError as exc:
        raise ReviewWorkflowError("review artifact escapes repository root") from exc


def _approval_review_candidates(
    approval: Mapping[str, Any], *, repository: Path
) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for item in approval["candidates"]:
        company_dir = _repository_path(
            repository,
            str(item["company_dir"]),
            f"{item['symbol']} approved company_dir",
        )
        meta = validate_company_dir(company_dir)
        if meta["identity"]["symbol"] != item["symbol"]:
            raise ReviewWorkflowError(
                f"approved company identity mismatch: {item['symbol']}"
            )
        result.append(
            {
                "symbol": str(item["symbol"]),
                "name": str(meta["identity"]["name"]),
                "target_company_dir": str(company_dir),
            }
        )
    return sorted(result, key=lambda item: item["symbol"])


def _verify_approval_policy_in_snapshot(
    approval: Mapping[str, Any],
    *,
    policies: Mapping[str, Mapping[str, Any]],
    repository: Path,
) -> None:
    binding = approval.get("policy_binding")
    if not isinstance(binding, Mapping):
        raise ReviewWorkflowError(
            "underwriting approval policy binding is missing"
        )
    policy_id = str(binding.get("policy_id"))
    snapshot_policy = policies.get(policy_id)
    if not isinstance(snapshot_policy, Mapping):
        raise ReviewWorkflowError(
            "review policy snapshot omits underwriting allocation policy"
        )
    policy_path = _repository_path(
        repository,
        str(binding.get("path")),
        "underwriting allocation policy",
    )
    try:
        bound_policy = json.loads(policy_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReviewWorkflowError(
            "underwriting allocation policy cannot be read"
        ) from exc
    if (
        not isinstance(bound_policy, Mapping)
        or dict(snapshot_policy) != dict(bound_policy)
        or snapshot_policy.get("version") != binding.get("version")
    ):
        raise ReviewWorkflowError(
            "review policy snapshot diverges from underwriting approval"
        )


def _repository_root_for_runs(runs_root: str | Path) -> Path:
    runs = Path(runs_root).resolve()
    if runs.name != "runs" or runs.parent.name != "automation":
        raise ReviewWorkflowError(
            "manager-bound review requires runs_root at <repository>/automation/runs"
        )
    return runs.parent.parent


def _repository_path(repository: Path, value: str | Path, label: str) -> Path:
    candidate = Path(value)
    resolved = (
        candidate if candidate.is_absolute() else repository / candidate
    ).resolve()
    try:
        resolved.relative_to(repository)
    except ValueError as exc:
        raise ReviewWorkflowError(f"{label} escapes repository root") from exc
    return resolved


def _validated_policy_snapshot(
    *,
    runs_root: str | Path,
    run_id: str,
    state: Mapping[str, Any],
) -> ReviewPolicySnapshot:
    try:
        return load_review_policy_snapshot(
            runs_root=runs_root,
            run_id=run_id,
            state=state,
        )
    except PolicySnapshotError as exc:
        raise ReviewWorkflowError(str(exc)) from exc


def _active_portfolio_candidate_path(
    company_dir: Path,
    run_id: str,
) -> Path:
    review_dir = company_dir / "underwriting" / run_id
    final_path = review_dir / "portfolio-candidate.final.json"
    if final_path.is_file():
        return final_path
    primary_path = review_dir / "portfolio-candidate.primary.json"
    if primary_path.is_file():
        return primary_path
    raise ReviewWorkflowError(
        f"portfolio candidate is missing: {company_dir.name}"
    )


def _validate_candidate_binding(
    *,
    run_id: str,
    candidate_path: Path,
    candidate: Mapping[str, Any],
    machine_decision: Mapping[str, Any],
    policy_snapshot_sha256: str,
) -> None:
    symbol = str(candidate.get("symbol"))
    expected_decision_source_stage = (
        "arbitration"
        if candidate_path.name == "portfolio-candidate.final.json"
        else "blind"
    )
    expected_challenger_completed = expected_decision_source_stage == "arbitration"
    if (
        machine_decision.get("review_id") != run_id
        or machine_decision.get("source_stage")
        != expected_decision_source_stage
        or machine_decision.get("challenger_completed")
        is not expected_challenger_completed
        or candidate.get("independent_challenger_completed")
        is not expected_challenger_completed
        or candidate.get("evidence_stale")
        is not (machine_decision.get("status") == "stale")
    ):
        raise ReviewWorkflowError(
            f"portfolio candidate decision state diverges: {symbol}"
        )

    assessment_filenames = {
        "blind": "blind-assessment.json",
        "challenger": "challenger-assessment.json",
        "arbitration": "arbitration.json",
    }
    decision_source_stage = str(machine_decision.get("source_stage"))
    decision_source_path = candidate_path.with_name(
        assessment_filenames[decision_source_stage]
    )
    decision_source_seal = verify_sealed(decision_source_path)
    if (
        decision_source_seal.artifact_type
        != f"{decision_source_stage}_assessment"
        or machine_decision.get("source_assessment_sha256")
        != decision_source_seal.sha256
    ):
        raise ReviewWorkflowError(
            f"machine decision source assessment mismatch: {symbol}"
        )

    candidate_source_stage = machine_decision.get("candidate_source_stage")
    allowed_candidate_sources = (
        {"blind", "challenger"}
        if expected_challenger_completed
        else {"blind"}
    )
    if candidate_source_stage not in allowed_candidate_sources:
        raise ReviewWorkflowError(
            f"portfolio candidate source stage mismatch: {symbol}"
        )
    candidate_source_path = candidate_path.with_name(
        assessment_filenames[str(candidate_source_stage)]
    )
    candidate_source_seal = verify_sealed(candidate_source_path)
    if (
        candidate_source_seal.artifact_type
        != f"{candidate_source_stage}_assessment"
        or machine_decision.get("candidate_source_assessment_sha256")
        != candidate_source_seal.sha256
    ):
        raise ReviewWorkflowError(
            f"portfolio candidate source assessment mismatch: {symbol}"
        )
    candidate_source = _read_json_object(
        candidate_source_path,
        "portfolio candidate source assessment",
    )
    if (
        candidate_source.get("review_id") != run_id
        or candidate_source.get("symbol") != symbol
    ):
        raise ReviewWorkflowError(
            f"portfolio candidate source identity mismatch: {symbol}"
        )

    if (
        machine_decision.get("policy_snapshot_sha256")
        != policy_snapshot_sha256
    ):
        raise ReviewWorkflowError(
            f"portfolio candidate policy decision mismatch: {symbol}"
        )
    try:
        actual_core_sha256 = portfolio_candidate_core_sha256(candidate)
    except (PortfolioValidationError, ValueError) as exc:
        raise ReviewWorkflowError(
            f"portfolio candidate core is invalid: {symbol}"
        ) from exc
    if (
        machine_decision.get("portfolio_candidate_core_sha256")
        != actual_core_sha256
    ):
        raise ReviewWorkflowError(
            f"portfolio candidate core SHA-256 mismatch: {symbol}"
        )


def _load_latest_research_claims(
    company_dir: Path, meta: Mapping[str, Any]
) -> tuple[dict[str, Any], str]:
    latest = meta["reports"]["latest"]
    if not isinstance(latest, str):
        raise ReviewWorkflowError(
            f"company has no latest structured report: {meta['identity']['symbol']}"
        )
    record = next(
        (item for item in meta["reports"]["history"] if item["path"] == latest),
        None,
    )
    if record is None:
        raise ReviewWorkflowError("latest report is absent from report history")
    report_path = company_dir / latest
    match = _REPORT_META_RE.match(report_path.read_text(encoding="utf-8-sig"))
    if not match:
        raise ReviewWorkflowError(f"latest report has no v2 metadata: {report_path}")
    front = json.loads(match.group("meta"))
    candidates: list[Path] = []
    for relative in front["sealed_artifacts"]:
        path = company_dir / relative
        sealed = verify_sealed(path)
        if sealed.artifact_type == "research_claims":
            candidates.append(path)
    if len(candidates) != 1:
        raise ReviewWorkflowError(
            "latest report must reference exactly one sealed research_claims artifact: "
            f"{meta['identity']['symbol']}"
        )
    return _read_json_object(candidates[0], "research claims"), str(record["sha256"])


def _decision_payload(item: Any) -> dict[str, Any]:
    return {
        "symbol": item.symbol,
        "name": item.name,
        "underwriting_status": item.underwriting_status,
        "evidence_stale": item.evidence_stale,
        "confidence": item.confidence,
        "action": item.action,
        "current_price": item.current_price,
        "price_as_of": item.price_as_of,
        "expected_annual_return": item.expected_annual_return,
        "minimum_expected_annual_return": item.minimum_expected_annual_return,
        "expected_return_gap": item.expected_return_gap,
        "minimum_return_activation_price": item.minimum_return_activation_price,
        "near_miss_return_activation_price": item.near_miss_return_activation_price,
        "buy_now_price_ceiling": item.buy_now_price_ceiling,
        "bear_value": item.bear_value,
        "fair_value_range": list(item.fair_value_range),
        "buy_zone": list(item.buy_zone),
        "reduce_zone": list(item.reduce_zone),
        "return_model": {
            "schema_version": 1,
            "method": item.return_model_method,
            "currency": item.return_model_currency,
            "model_as_of": item.return_model_as_of,
            "base_case_distributions_per_share": list(
                item.annual_cash_distributions
            ),
            "base_case_terminal_value_per_share": item.terminal_value,
        },
        "target_weight": item.target_weight,
        "initial_entry_weight": item.initial_entry_weight,
        "industry": item.industry,
        "economic_risk_clusters": list(item.economic_risk_clusters),
        "reason_codes": list(item.reason_codes),
    }


def _portfolio_report_lines(
    portfolio: Mapping[str, Any],
    *,
    run_id: str,
    reported_at: dt.datetime,
) -> list[str]:
    lines = [
        f"# 独立承保复核综合：{run_id}",
        "",
        f"生成时间：{reported_at.isoformat()}",
        "",
        "| 公司 | 承保 | 置信度 | 操作 | 现价 | 预期年化 | 距12%门槛 | "
        "12%激活价 | 实际买入上限 | 合理价值 | 目标仓位 | 理由代码 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for item in portfolio["positions"]:
        lines.append(
            (
                "| {name}（{symbol}） | {underwriting} | {confidence} | {action} | "
                "{price:g} | {expected:.2%} | {gap:+.2%} | {activation:g} | "
                "{ceiling:g} | {fair} | {weight:.2%} | {reasons} |"
            ).format(
                name=item["name"],
                symbol=item["symbol"],
                underwriting=item["underwriting_status"],
                confidence=item["confidence"],
                action=item["action"],
                price=item["current_price"],
                expected=item["expected_annual_return"],
                gap=item["expected_return_gap"],
                activation=item["minimum_return_activation_price"],
                ceiling=item["buy_now_price_ceiling"],
                fair="–".join(f"{value:g}" for value in item["fair_value_range"]),
                weight=item["target_weight"],
                reasons=", ".join(item["reason_codes"]),
            )
        )
    lines.extend(["", f"现金权重：{portfolio['cash_weight']:.2%}", ""])
    return lines


def _validate_portfolio_payload(
    payload: Mapping[str, Any],
    *,
    expected_policy_snapshot_sha256: str,
) -> None:
    top_level = {
        "schema_version",
        "portfolio_id",
        "run_id",
        "as_of",
        "quote_snapshot_sha256",
        "policy_snapshot_sha256",
        "policy_versions",
        "positions",
        "cash_weight",
        "exclusions",
    }
    position_fields = {
        "symbol",
        "name",
        "underwriting_status",
        "evidence_stale",
        "confidence",
        "action",
        "current_price",
        "price_as_of",
        "expected_annual_return",
        "minimum_expected_annual_return",
        "expected_return_gap",
        "minimum_return_activation_price",
        "near_miss_return_activation_price",
        "buy_now_price_ceiling",
        "bear_value",
        "fair_value_range",
        "buy_zone",
        "reduce_zone",
        "return_model",
        "portfolio_candidate_sha256",
        "target_weight",
        "initial_entry_weight",
        "industry",
        "economic_risk_clusters",
        "reason_codes",
    }
    if set(payload) != top_level or payload.get("schema_version") != 3:
        raise ReviewWorkflowError("portfolio payload does not match the v3 contract")
    snapshot_hash = payload.get("policy_snapshot_sha256")
    if (
        not isinstance(snapshot_hash, str)
        or len(snapshot_hash) != 64
        or any(char not in "0123456789abcdef" for char in snapshot_hash)
    ):
        raise ReviewWorkflowError("portfolio policy_snapshot_sha256 is invalid")
    if (
        not isinstance(expected_policy_snapshot_sha256, str)
        or len(expected_policy_snapshot_sha256) != 64
        or any(
            char not in "0123456789abcdef"
            for char in expected_policy_snapshot_sha256
        )
    ):
        raise ReviewWorkflowError(
            "expected policy_snapshot_sha256 is invalid"
        )
    if snapshot_hash != expected_policy_snapshot_sha256:
        raise ReviewWorkflowError(
            "portfolio policy_snapshot_sha256 does not match the review snapshot"
        )
    positions = payload.get("positions")
    if not isinstance(positions, list):
        raise ReviewWorkflowError("portfolio positions must be an array")
    for item in positions:
        if not isinstance(item, Mapping) or set(item) != position_fields:
            raise ReviewWorkflowError(
                "portfolio position does not match the v3 contract"
            )


def _next_action(status: str) -> str:
    return {
        ReviewRunStatus.PACKETS_READY.value: "dispatch_blind_reviews",
        ReviewRunStatus.BLIND_REVIEWING.value: "wait_for_blind_reviews",
        ReviewRunStatus.BLIND_SEALED.value: "dispatch_reveal_reviews",
        ReviewRunStatus.REVEALING.value: "complete_reveal_or_dispatch_challenger",
        ReviewRunStatus.CHALLENGING.value: "complete_challenger_and_arbitration",
        ReviewRunStatus.PORTFOLIO_CHALLENGING.value: (
            "complete_top_five_challenger_and_arbitration"
        ),
        ReviewRunStatus.COMPLETED.value: "none",
    }.get(status, "inspect_status")


def _read_json(path: Path, label: str) -> Any:
    if not path.is_file():
        raise ReviewWorkflowError(f"{label} is missing: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ReviewWorkflowError(f"invalid {label} JSON: {path}") from exc


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    value = _read_json(path, label)
    if not isinstance(value, dict):
        raise ReviewWorkflowError(f"{label} must be a JSON object")
    return value


def _parse_aware_datetime(value: Any, label: str) -> dt.datetime:
    if not isinstance(value, str):
        raise ReviewWorkflowError(f"{label} must be an ISO 8601 datetime")
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise ReviewWorkflowError(f"{label} must be an ISO 8601 datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ReviewWorkflowError(f"{label} must include a UTC offset")
    return parsed


def _pretty_json_bytes(payload: Any) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
