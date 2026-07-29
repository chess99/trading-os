from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import os
import re
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .company import _read_report_front, validate_company_dir
from .sealing import atomic_write_bytes, seal_json, verify_sealed


class CompanyTimelineError(ValueError):
    """Raised when an immutable rapid-triage result cannot enter a company timeline."""


_SYMBOL_RE = re.compile(r"^(CN|HK|US):[A-Z0-9.]+$")
_REVIEW_MODES = {"baseline_recheck", "triggered_update"}
_TRIGGER_TYPES = {"filing", "price", "date", "event", "thesis", "ttl"}
_PRICE_OPERATORS = {"price_lte", "price_gte"}


def publish_rapid_triage_to_company_timeline(
    *,
    repository_root: str | Path,
    package_path: str | Path,
    published_at: dt.datetime,
    review_mode: str | None = None,
) -> dict[str, Any]:
    """Append one sealed rapid-triage package to its immutable company timeline.

    Version 2 packages carry ``review_mode`` themselves. A legacy version 1 package
    is publishable only when its caller supplies an explicit mode. The operation is
    idempotent by the source package seal hash.
    """

    _aware(published_at, "published_at")
    repo = Path(repository_root).resolve()
    source_path = Path(package_path).resolve()
    source_rel = _relative_to_repository(repo, source_path, "package_path")
    try:
        source_seal = verify_sealed(source_path)
    except ValueError as exc:
        raise CompanyTimelineError(f"rapid-triage package is not validly sealed: {exc}") from exc
    if source_seal.artifact_type != "rapid_triage_package":
        raise CompanyTimelineError("package seal artifact_type must be rapid_triage_package")
    if source_seal.sealed_at > published_at:
        raise CompanyTimelineError("published_at cannot precede the package seal")
    package = _read_object(source_path, "rapid-triage package")
    schema_version = package.get("schema_version")
    if schema_version not in {1, 2}:
        raise CompanyTimelineError("rapid-triage package schema_version must be 1 or 2")
    package_mode = package.get("review_mode") if schema_version == 2 else None
    if schema_version == 2:
        if package_mode not in _REVIEW_MODES:
            raise CompanyTimelineError("v2 rapid-triage package review_mode is invalid")
        if review_mode is not None and review_mode != package_mode:
            raise CompanyTimelineError("review_mode conflicts with the sealed package")
        resolved_mode = str(package_mode)
    else:
        if review_mode not in _REVIEW_MODES:
            raise CompanyTimelineError(
                "legacy rapid-triage packages require an explicit review_mode"
            )
        resolved_mode = str(review_mode)

    symbol = _text(package.get("symbol"), "symbol")
    if not _SYMBOL_RE.fullmatch(symbol):
        raise CompanyTimelineError(f"invalid company symbol: {symbol}")
    market, ticker = symbol.split(":", 1)
    company_dir = repo / "research" / "companies" / market / ticker
    as_of = _date(package.get("as_of"), "as_of")
    cutoff = _datetime(package.get("information_cutoff"), "information_cutoff")
    if as_of > published_at.date() or cutoff > published_at:
        raise CompanyTimelineError("rapid-triage timestamps cannot be after publication")
    triggers, refresh_due_at = _normalize_triggers(
        package.get("revisit_triggers"),
        schema_version=int(schema_version),
        information_cutoff=cutoff,
    )

    digest_prefix = source_seal.sha256[:12]
    report_id = f"{market}-{ticker}-{as_of.isoformat()}-rapid-triage-{digest_prefix}"
    report_rel = f"reports/{as_of.isoformat()}-rapid-triage-{digest_prefix}.md"
    manifest_rel = f"evidence/{report_id}-sources.json"
    report_path = company_dir / report_rel
    manifest_path = company_dir / manifest_rel
    source_seal_rel = _relative_to_repository(
        repo, source_seal.manifest_path.resolve(), "package seal manifest"
    )

    with _exclusive_lock(company_dir / ".timeline.lock"):
        meta = validate_company_dir(company_dir)
        if meta["identity"]["symbol"] != symbol:
            raise CompanyTimelineError("package symbol does not match company identity")
        package_name = package.get("company_name")
        if package_name is not None and str(package_name).strip() != meta["identity"]["name"]:
            raise CompanyTimelineError("package company_name does not match company identity")
        existing_state = meta["research"].get("latest_rapid_triage")
        if (
            isinstance(existing_state, Mapping)
            and existing_state.get("source_package_sha256") == source_seal.sha256
        ):
            validated = validate_company_dir(company_dir)
            return _result(
                repo=repo,
                company_dir=company_dir,
                state=validated["research"]["latest_rapid_triage"],
                trigger_count=len(validated["triggers"]),
                idempotent=True,
                rebaseline_cleared=False,
                source_manifest_path=manifest_rel,
            )
        historical_match = _find_historical_rapid_triage(
            company_dir=company_dir,
            history=meta["reports"]["history"],
            source_package_sha256=source_seal.sha256,
        )
        if historical_match is not None:
            historical_state, historical_manifest_rel = historical_match
            return _result(
                repo=repo,
                company_dir=company_dir,
                state=historical_state,
                trigger_count=len(meta["triggers"]),
                idempotent=True,
                rebaseline_cleared=False,
                source_manifest_path=historical_manifest_rel,
            )
        if meta["identity"]["security_status"] != "active":
            raise CompanyTimelineError("rapid triage can only be published for active securities")
        prior_updated_at = _datetime(meta.get("updated_at"), "meta.updated_at")
        if prior_updated_at > published_at:
            raise CompanyTimelineError("refusing to replace newer company metadata")
        prior_cutoff_raw = meta["research"].get("information_cutoff")
        if prior_cutoff_raw is not None and _datetime(
            prior_cutoff_raw, "research.information_cutoff"
        ) > cutoff:
            raise CompanyTimelineError("rapid triage cannot regress information_cutoff")
        history = meta["reports"]["history"]
        if history and _date(history[-1]["as_of"], "reports.history[-1].as_of") > as_of:
            raise CompanyTimelineError("rapid triage cannot regress report chronology")

        source_manifest = {
            "schema_version": 1,
            "artifact_type": "rapid_triage_source_manifest",
            "report_id": report_id,
            "symbol": symbol,
            "information_cutoff": cutoff.isoformat(),
            "source_package": {
                "repository_path": source_rel,
                "seal_manifest_path": source_seal_rel,
                "artifact_type": source_seal.artifact_type,
                "sha256": source_seal.sha256,
                "sealed_at": source_seal.sealed_at.isoformat(),
            },
            "sources": copy.deepcopy(package.get("sources") or []),
        }
        seal_json(
            manifest_path,
            source_manifest,
            artifact_type="rapid_triage_source_manifest",
            sealed_at=published_at,
        )

        predecessor_reports = (
            [str(history[-1]["report_id"])] if history else []
        )
        front = {
            "schema_version": 2,
            "report_id": report_id,
            "report_type": "rapid_triage",
            "symbol": symbol,
            "as_of": as_of.isoformat(),
            "information_cutoff": cutoff.isoformat(),
            "price_snapshot_id": package.get("price_source_id"),
            "policy_versions": {
                "rapid-triage-contract": f"{schema_version}.0.0"
            },
            "agent_id": _agent_id(package),
            "predecessor_reports": predecessor_reports,
            "sealed_artifacts": [manifest_rel],
            "source_manifest": manifest_rel,
        }
        report_bytes = _report_bytes(
            package,
            identity=meta["identity"],
            front=front,
            review_mode=resolved_mode,
            triggers=triggers,
        )
        _write_immutable(report_path, report_bytes)
        report_sha = hashlib.sha256(report_bytes).hexdigest()

        updated = copy.deepcopy(meta)
        updated_history = list(updated["reports"]["history"])
        updated_history.append(
            {
                "report_id": report_id,
                "path": report_rel,
                "report_type": "rapid_triage",
                "as_of": as_of.isoformat(),
                "sha256": report_sha,
            }
        )
        updated["reports"]["history"] = updated_history
        updated["reports"]["latest"] = report_rel
        updated["reports"]["latest_by_type"]["rapid_triage"] = report_rel
        was_rebaseline = bool(updated["research"]["rebaseline_required"])
        updated["research"].update(
            {
                "coverage_status": (
                    "covered"
                    if resolved_mode == "baseline_recheck" or not was_rebaseline
                    else updated["research"]["coverage_status"]
                ),
                "information_cutoff": cutoff.isoformat(),
                "refresh_due_at": refresh_due_at,
                "latest_rapid_triage": {
                    "report_id": report_id,
                    "report_path": report_rel,
                    "source_package_path": source_rel,
                    "source_package_sha256": source_seal.sha256,
                    "information_cutoff": cutoff.isoformat(),
                    "review_mode": resolved_mode,
                    "published_at": published_at.isoformat(),
                },
            }
        )
        if resolved_mode == "baseline_recheck":
            updated["research"]["rebaseline_required"] = False
        updated["triggers"] = triggers
        updated["updated_at"] = published_at.isoformat()

        meta_path = company_dir / "meta.json"
        previous_meta_bytes = meta_path.read_bytes()
        updated_bytes = _pretty_json_bytes(updated)
        atomic_write_bytes(meta_path, updated_bytes)
        try:
            validated = validate_company_dir(company_dir)
        except Exception:
            atomic_write_bytes(meta_path, previous_meta_bytes)
            raise
        return _result(
            repo=repo,
            company_dir=company_dir,
            state=validated["research"]["latest_rapid_triage"],
            trigger_count=len(validated["triggers"]),
            idempotent=False,
            rebaseline_cleared=(
                was_rebaseline and resolved_mode == "baseline_recheck"
            ),
            source_manifest_path=manifest_rel,
        )


def _find_historical_rapid_triage(
    *,
    company_dir: Path,
    history: list[dict[str, Any]],
    source_package_sha256: str,
) -> tuple[dict[str, Any], str] | None:
    matches: list[tuple[dict[str, Any], str]] = []
    for index, record in enumerate(history):
        if record.get("report_type") != "rapid_triage":
            continue
        report_rel = _text(record.get("path"), f"reports.history[{index}].path")
        front = _read_report_front(company_dir / report_rel)
        manifest_rel = _text(
            front.get("source_manifest"),
            f"rapid-triage report {record.get('report_id')} source_manifest",
        )
        manifest_path = (company_dir / manifest_rel).resolve()
        try:
            manifest_path.relative_to(company_dir.resolve())
        except ValueError as exc:
            raise CompanyTimelineError(
                f"rapid-triage source manifest must stay inside company directory: {manifest_rel}"
            ) from exc
        try:
            manifest_seal = verify_sealed(manifest_path)
        except ValueError as exc:
            raise CompanyTimelineError(
                f"rapid-triage source manifest is not validly sealed: {exc}"
            ) from exc
        if manifest_seal.artifact_type != "rapid_triage_source_manifest":
            raise CompanyTimelineError(
                "rapid-triage source manifest artifact_type is invalid"
            )
        manifest = _read_object(manifest_path, "rapid-triage source manifest")
        package_ref = manifest.get("source_package")
        if not isinstance(package_ref, Mapping):
            raise CompanyTimelineError(
                "rapid-triage source manifest source_package must be an object"
            )
        if package_ref.get("sha256") != source_package_sha256:
            continue
        matches.append(
            (
                {
                    "report_id": record["report_id"],
                    "report_path": report_rel,
                    "source_package_sha256": source_package_sha256,
                },
                manifest_rel,
            )
        )
    if len(matches) > 1:
        report_ids = ", ".join(str(state["report_id"]) for state, _ in matches)
        raise CompanyTimelineError(
            "source package sha256 is referenced by multiple rapid-triage reports: "
            f"{report_ids}"
        )
    return matches[0] if matches else None


def _normalize_triggers(
    raw_triggers: Any,
    *,
    schema_version: int,
    information_cutoff: dt.datetime,
) -> tuple[list[dict[str, Any]], str | None]:
    if not isinstance(raw_triggers, list):
        raise CompanyTimelineError("revisit_triggers must be an array")
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    refresh_dates: list[dt.datetime] = []
    for index, raw in enumerate(raw_triggers):
        if not isinstance(raw, Mapping):
            raise CompanyTimelineError(f"revisit_triggers[{index}] must be an object")
        trigger_type = _text(raw.get("type"), f"revisit_triggers[{index}].type")
        if trigger_type not in _TRIGGER_TYPES:
            raise CompanyTimelineError(f"unsupported revisit trigger type: {trigger_type}")
        reason = _text(raw.get("reason"), f"revisit_triggers[{index}].reason")
        raw_condition = raw.get("condition")
        if schema_version == 1 and isinstance(raw_condition, str):
            raw_condition = _legacy_condition(trigger_type, raw_condition)
        if not isinstance(raw_condition, Mapping):
            raise CompanyTimelineError(
                f"revisit_triggers[{index}].condition must be an object"
            )
        condition = dict(raw_condition)
        trigger_id_raw = raw.get("trigger_id")
        if schema_version == 2:
            trigger_id = _text(
                trigger_id_raw, f"revisit_triggers[{index}].trigger_id"
            )
        elif trigger_id_raw is None:
            seed = json.dumps(
                [trigger_type, condition, reason],
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            trigger_id = f"rapid-triage-{hashlib.sha256(seed).hexdigest()[:12]}"
        else:
            trigger_id = _text(
                trigger_id_raw, f"revisit_triggers[{index}].trigger_id"
            )
        if trigger_id in seen_ids:
            raise CompanyTimelineError(f"duplicate revisit trigger_id: {trigger_id}")
        seen_ids.add(trigger_id)

        meta_type = trigger_type
        if trigger_type == "price":
            if set(condition) != {"operator", "threshold"}:
                raise CompanyTimelineError(
                    "price trigger condition requires only operator and threshold"
                )
            if condition.get("operator") not in _PRICE_OPERATORS:
                raise CompanyTimelineError("price trigger operator is invalid")
            threshold = _positive_number(condition.get("threshold"), "price threshold")
            condition = {
                "operator": str(condition["operator"]),
                "threshold": threshold,
            }
        elif trigger_type == "date":
            if set(condition) != {"date"}:
                raise CompanyTimelineError("date trigger condition requires only date")
            due_date = _date(condition.get("date"), "date trigger date")
            condition = {"date": due_date.isoformat()}
            refresh_dates.append(
                dt.datetime.combine(
                    due_date, dt.time.min, tzinfo=information_cutoff.tzinfo
                )
            )
        elif trigger_type == "ttl":
            if set(condition) == {"days"}:
                days = condition.get("days")
                if isinstance(days, bool) or not isinstance(days, int) or days <= 0:
                    raise CompanyTimelineError("ttl days must be a positive integer")
                due_at = information_cutoff + dt.timedelta(days=days)
            elif set(condition) == {"due_at"}:
                due_at = _datetime(condition.get("due_at"), "ttl due_at")
            else:
                raise CompanyTimelineError("ttl condition requires days xor due_at")
            if due_at <= information_cutoff:
                raise CompanyTimelineError("ttl due_at must follow information_cutoff")
            meta_type = "date"
            condition = {"due_at": due_at.isoformat(), "origin": "ttl"}
            refresh_dates.append(due_at)
        else:
            description = condition.get("description") or condition.get("matcher")
            _text(description, f"{trigger_type} trigger description")
            condition = copy.deepcopy(condition)
        normalized.append(
            {
                "trigger_id": trigger_id,
                "type": meta_type,
                "condition": condition,
                "reason": reason,
                "active": True,
            }
        )
    refresh_due_at = min(refresh_dates).isoformat() if refresh_dates else None
    return normalized, refresh_due_at


def _legacy_condition(trigger_type: str, condition: str) -> dict[str, Any]:
    text = _text(condition, "legacy trigger condition")
    if trigger_type in {"filing", "event", "thesis"}:
        return {"description": text}
    if trigger_type == "date":
        return {"date": text}
    raise CompanyTimelineError(
        f"legacy {trigger_type} trigger is not machine actionable; use a v2 package"
    )


def _report_bytes(
    package: Mapping[str, Any],
    *,
    identity: Mapping[str, Any],
    front: Mapping[str, Any],
    review_mode: str,
    triggers: list[dict[str, Any]],
) -> bytes:
    counterevidence = _as_lines(package.get("counterevidence"))
    sources = package.get("sources") if isinstance(package.get("sources"), list) else []
    trigger_lines = [
        f"- `{item['type']}` / `{item['trigger_id']}`：{item['reason']}；"
        f"条件 `{json.dumps(item['condition'], ensure_ascii=False, sort_keys=True)}`"
        for item in triggers
    ] or ["- 当前包没有定义后续重启触发器。"]
    source_lines: list[str] = []
    for item in sources:
        if not isinstance(item, Mapping):
            continue
        source_id = item.get("source_id") or "未编号来源"
        tier = item.get("tier") or "未分级"
        title = item.get("title") or source_id
        ref = item.get("url") or item.get("local_path") or "无路径"
        source_lines.append(f"- [{tier}] {title}（{source_id}）：{ref}")
    if not source_lines:
        source_lines = ["- 来源详见已封存的 source manifest。"]
    sections = [
        (
            "快速结论",
            f"本次为 `{review_mode}`。研究价值粗判为 "
            f"`{package.get('research_value', 'unknown')}`，估值信号为 "
            f"`{package.get('valuation_signal', 'unknown')}`。本报告只分配后续研究预算，"
            "不构成买入、卖出或仓位结论。",
        ),
        ("业务速览", _display(package.get("business_summary"), "未提供业务速览。")),
        ("变化摘要", _display(package.get("change_summary"), "未提供变化摘要。")),
        (
            "正常化盈利粗判",
            _display(
                package.get("normalized_earnings_view"),
                f"盈利可理解性：{package.get('earnings_legibility', 'unknown')}。",
            ),
        ),
        (
            "市场隐含预期",
            _display(
                package.get("expectations_view"),
                f"当前价格与粗略估值信号：{package.get('current_price', 'unknown')} / "
                f"{package.get('valuation_signal', 'unknown')}。",
            ),
        ),
        ("反方证据", "\n".join(counterevidence) if counterevidence else "- 未单列反方证据。"),
        ("重启触发器", "\n".join(trigger_lines)),
        ("来源", "\n".join(source_lines)),
    ]
    metadata = json.dumps(front, ensure_ascii=False, indent=2)
    body = [
        "<!-- trading-os-report-meta",
        metadata,
        "-->",
        f"# 公司研究：{identity['name']}（{identity['symbol']}）",
        "",
    ]
    for heading, content in sections:
        body.extend([f"## {heading}", "", content, ""])
    return ("\n".join(body).rstrip() + "\n").encode("utf-8")


def _result(
    *,
    repo: Path,
    company_dir: Path,
    state: Mapping[str, Any],
    trigger_count: int,
    idempotent: bool,
    rebaseline_cleared: bool,
    source_manifest_path: str,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "symbol": company_dir.parent.name + ":" + company_dir.name,
        "company_report_path": (
            company_dir / str(state["report_path"])
        ).relative_to(repo).as_posix(),
        "report_id": state["report_id"],
        "idempotent": idempotent,
        "rebaseline_cleared": rebaseline_cleared,
        "trigger_count": trigger_count,
        "source_manifest_path": (
            company_dir / source_manifest_path
        ).relative_to(repo).as_posix(),
        "source_package_sha256": state["source_package_sha256"],
    }


def _agent_id(package: Mapping[str, Any]) -> str:
    provenance = package.get("provenance")
    if not isinstance(provenance, Mapping):
        return "rapid-triage-agent"
    agent = str(provenance.get("agent") or "rapid-triage-agent")
    model = str(provenance.get("model") or "unknown-model")
    tools = provenance.get("tools")
    tool_text = ", ".join(str(value) for value in tools) if isinstance(tools, list) else ""
    return f"{agent}; {model}" + (f"; {tool_text}" if tool_text else "")


def _as_lines(value: Any) -> list[str]:
    if isinstance(value, list):
        return [f"- {str(item).strip()}" for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [f"- {value.strip()}"]
    return []


def _display(value: Any, fallback: str) -> str:
    return value.strip() if isinstance(value, str) and value.strip() else fallback


def _write_immutable(path: Path, content: bytes) -> None:
    if path.exists():
        if not path.is_file() or path.read_bytes() != content:
            raise CompanyTimelineError(f"company timeline artifact is immutable: {path}")
        return
    atomic_write_bytes(path, content)


def _read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CompanyTimelineError(f"invalid {label}: {path}") from exc
    if not isinstance(value, dict):
        raise CompanyTimelineError(f"{label} must be an object")
    return value


def _relative_to_repository(repo: Path, path: Path, label: str) -> str:
    try:
        return path.relative_to(repo).as_posix()
    except ValueError as exc:
        raise CompanyTimelineError(f"{label} must be inside repository_root") from exc


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CompanyTimelineError(f"{label} must be a non-empty string")
    return value.strip()


def _date(value: Any, label: str) -> dt.date:
    if not isinstance(value, str):
        raise CompanyTimelineError(f"{label} must be an ISO date")
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise CompanyTimelineError(f"{label} must be a real ISO date") from exc


def _datetime(value: Any, label: str) -> dt.datetime:
    if not isinstance(value, str):
        raise CompanyTimelineError(f"{label} must be an ISO datetime")
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise CompanyTimelineError(f"{label} must be an ISO datetime") from exc
    _aware(parsed, label)
    return parsed


def _aware(value: dt.datetime, label: str) -> None:
    if not isinstance(value, dt.datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise CompanyTimelineError(f"{label} must include timezone information")


def _positive_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise CompanyTimelineError(f"{label} must be a positive number")
    return float(value)


def _pretty_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


@contextmanager
def _exclusive_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise CompanyTimelineError(f"company timeline is busy: {path}") from exc
    try:
        os.write(descriptor, str(os.getpid()).encode("ascii"))
        os.close(descriptor)
        descriptor = -1
        yield
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        path.unlink(missing_ok=True)
