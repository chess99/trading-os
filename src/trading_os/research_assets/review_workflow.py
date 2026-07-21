from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from .claims import build_claim_packet
from .company import validate_company_dir, validate_research_assets
from .models import ReviewRunStatus, load_policy
from .portfolio import POLICY_KEYS, build_model_portfolio
from .review_store import ReviewRunStore
from .sealing import (
    atomic_write_bytes,
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
    root = Path(policy_root)
    if not root.is_dir():
        raise ReviewWorkflowError(f"policy directory does not exist: {root}")
    versions: dict[str, str] = {}
    for path in sorted(root.rglob("*.json")):
        policy = load_policy(path)
        if policy.policy_id in versions:
            raise ReviewWorkflowError(f"duplicate policy_id: {policy.policy_id}")
        versions[policy.policy_id] = policy.version
    if not versions:
        raise ReviewWorkflowError(f"no policies found under: {root}")
    return versions


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
) -> dict[str, Any]:
    store = ReviewRunStore(runs_root)
    policy_versions = load_policy_versions(policy_root)
    store.create_run(
        run_id,
        scope={"type": scope_type, "market": market, "description": description},
        policy_versions=policy_versions,
        created_at=created_at,
        parent_run_id=parent_run_id,
    )
    return store.freeze_candidates(
        run_id,
        list(candidates),
        actor="cli",
        at=created_at,
    )


def prepare_review(
    *, runs_root: str | Path, run_id: str, prepared_at: dt.datetime
) -> dict[str, Any]:
    store = ReviewRunStore(runs_root)
    state = store.load_run(run_id)
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


def validate_review(
    *, runs_root: str | Path, run_id: str, strict: bool
) -> dict[str, Any]:
    store = ReviewRunStore(runs_root)
    state = store.load_run(run_id)
    candidates = store.read_candidates(run_id)
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
    if state["status"] != ReviewRunStatus.COMPANY_REVIEWS_COMPLETE.value:
        raise ReviewWorkflowError(
            "review synthesize requires company_reviews_complete, "
            f"got {state['status']}"
        )
    validate_review(runs_root=runs_root, run_id=run_id, strict=True)
    quotes_raw = _read_json(Path(quotes_path), "quote snapshot")
    if not isinstance(quotes_raw, list):
        raise ReviewWorkflowError("quote snapshot must be a JSON array")
    quotes: dict[str, float] = {}
    for item in quotes_raw:
        if not isinstance(item, dict) or set(item) < {"symbol", "price"}:
            raise ReviewWorkflowError("each quote must contain symbol and price")
        symbol = str(item["symbol"])
        price = item["price"]
        if isinstance(price, bool) or not isinstance(price, (int, float)) or price <= 0:
            raise ReviewWorkflowError(f"invalid quote price for {symbol}")
        if symbol in quotes:
            raise ReviewWorkflowError(f"duplicate quote symbol: {symbol}")
        quotes[symbol] = float(price)

    candidates: list[dict[str, Any]] = []
    for item in store.read_candidates(run_id):
        symbol = item["symbol"]
        if symbol not in quotes:
            raise ReviewWorkflowError(f"quote snapshot is missing candidate: {symbol}")
        candidate_path = (
            Path(item["target_company_dir"])
            / "underwriting"
            / run_id
            / "portfolio-candidate.json"
        )
        sealed = verify_sealed(candidate_path)
        if sealed.artifact_type != "portfolio_candidate":
            raise ReviewWorkflowError(f"invalid portfolio candidate type: {symbol}")
        candidate = _read_json_object(candidate_path, "portfolio candidate")
        if candidate.get("symbol") != symbol:
            raise ReviewWorkflowError(f"portfolio candidate symbol mismatch: {symbol}")
        candidate["current_price"] = quotes[symbol]
        candidates.append(candidate)

    portfolio_policy = load_policy(Path(policy_root) / "portfolio.json")
    policy = {
        key: portfolio_policy.payload[key]
        for key in POLICY_KEYS
    }
    result = build_model_portfolio(candidates, policy=policy)
    batch_dir = Path(research_root) / "batches" / run_id
    quote_artifact = seal_json(
        batch_dir / "quotes.json",
        quotes_raw,
        artifact_type="quote_snapshot",
        sealed_at=synthesized_at,
    )
    portfolio = {
        "schema_version": 2,
        "portfolio_id": f"model-{run_id}",
        "run_id": run_id,
        "as_of": synthesized_at.isoformat(),
        "quote_snapshot_sha256": quote_artifact.sha256,
        "policy_versions": state["policy_versions"],
        "positions": [_decision_payload(item) for item in result.decisions],
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
        return {
            "schema_version": 2,
            "run_id": run_id,
            "status": "completed",
            "path": path.as_posix(),
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
    lines = [
        f"# 独立承保复核综合：{run_id}",
        "",
        f"生成时间：{reported_at.isoformat()}",
        "",
        "| 公司 | 操作 | 现价 | 合理价值 | 买入区 | 目标仓位 | 理由代码 |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for item in portfolio["positions"]:
        lines.append(
            (
                "| {symbol} | {action} | {price:g} | {fair} | {buy} | "
                "{weight:.2%} | {reasons} |"
            ).format(
                symbol=item["symbol"],
                action=item["action"],
                price=item["current_price"],
                fair="–".join(f"{value:g}" for value in item["fair_value_range"]),
                buy="–".join(f"{value:g}" for value in item["buy_zone"]),
                weight=item["target_weight"],
                reasons=", ".join(item["reason_codes"]),
            )
        )
    lines.extend(["", f"现金权重：{portfolio['cash_weight']:.2%}", ""])
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
    return {
        "schema_version": 2,
        "run_id": run_id,
        "status": ReviewRunStatus.COMPLETED.value,
        "path": path.as_posix(),
        "sha256": digest,
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
        "action": item.action,
        "current_price": item.current_price,
        "fair_value_range": list(item.fair_value_range),
        "buy_zone": list(item.buy_zone),
        "target_weight": item.target_weight,
        "industry": item.industry,
        "economic_risk_clusters": list(item.economic_risk_clusters),
        "reason_codes": list(item.reason_codes),
    }


def _next_action(status: str) -> str:
    return {
        ReviewRunStatus.PACKETS_READY.value: "dispatch_blind_reviews",
        ReviewRunStatus.BLIND_REVIEWING.value: "wait_for_blind_reviews",
        ReviewRunStatus.BLIND_SEALED.value: "dispatch_reveal_reviews",
        ReviewRunStatus.REVEALING.value: "complete_reveal_or_dispatch_challenger",
        ReviewRunStatus.CHALLENGING.value: "complete_challenger_and_arbitration",
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
