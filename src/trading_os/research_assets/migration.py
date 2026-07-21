from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from .company import AssetValidationError, validate_company_dir
from .sealing import (
    SealingError,
    atomic_write_bytes,
    canonical_json_bytes,
    seal_json,
    verify_sealed,
)


class MigrationError(ValueError):
    """Raised when a migration plan is malformed, stale, or unsafe to apply."""


PLAN_KEYS = {
    "schema_version",
    "migration_id",
    "created_at",
    "research_root",
    "company_count",
    "migrate_count",
    "already_v2_count",
    "error_count",
    "companies",
    "plan_sha256",
}
PLAN_COMPANY_KEYS = {
    "company_dir",
    "action",
    "source_fingerprint",
    "identity",
    "updated_at",
    "historical_artifacts",
    "triggers",
    "reason_codes",
    "error",
}
MIGRATION_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]+$")


def build_migration_plan(
    research_root: str | Path,
    *,
    migration_id: str,
    created_at: dt.datetime,
) -> dict[str, Any]:
    _validate_migration_id(migration_id)
    _require_aware(created_at, "created_at")
    root = Path(research_root).resolve()
    companies: list[dict[str, Any]] = []
    for company_dir in _company_dirs(root / "companies"):
        companies.append(_scan_company(root, company_dir, created_at=created_at))
    payload: dict[str, Any] = {
        "schema_version": 2,
        "migration_id": migration_id,
        "created_at": created_at.isoformat(),
        "research_root": root.as_posix(),
        "company_count": len(companies),
        "migrate_count": sum(item["action"] == "migrate" for item in companies),
        "already_v2_count": sum(
            item["action"] == "already_v2" for item in companies
        ),
        "error_count": sum(item["action"] == "error" for item in companies),
        "companies": companies,
    }
    payload["plan_sha256"] = _plan_hash(payload)
    return payload


def write_migration_plan(path: str | Path, plan: Mapping[str, Any]) -> Path:
    validated = validate_migration_plan(plan)
    content = (
        json.dumps(validated, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    return atomic_write_bytes(path, content)


def load_migration_plan(path: str | Path) -> dict[str, Any]:
    plan_path = Path(path)
    try:
        value = json.loads(plan_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise MigrationError(f"invalid migration plan JSON: {plan_path}") from exc
    if not isinstance(value, dict):
        raise MigrationError("migration plan must be a JSON object")
    return validate_migration_plan(value)


def validate_migration_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(plan, Mapping) or set(plan) != PLAN_KEYS:
        raise MigrationError("migration plan fields do not match the v2 contract")
    normalized = dict(plan)
    if normalized.get("schema_version") != 2:
        raise MigrationError("migration plan schema_version must be 2")
    migration_id = normalized.get("migration_id")
    if not isinstance(migration_id, str):
        raise MigrationError("migration_id must be a string")
    _validate_migration_id(migration_id)
    _parse_aware(normalized.get("created_at"), "created_at")
    root = normalized.get("research_root")
    if not isinstance(root, str) or not root:
        raise MigrationError("research_root must be a non-empty string")
    companies = normalized.get("companies")
    if not isinstance(companies, list):
        raise MigrationError("migration companies must be an array")
    for index, item in enumerate(companies):
        if not isinstance(item, dict) or set(item) != PLAN_COMPANY_KEYS:
            raise MigrationError(f"migration company {index} fields are invalid")
        if item.get("action") not in {"migrate", "already_v2", "error"}:
            raise MigrationError(f"migration company {index} action is invalid")
    expected_counts = {
        "company_count": len(companies),
        "migrate_count": sum(item["action"] == "migrate" for item in companies),
        "already_v2_count": sum(
            item["action"] == "already_v2" for item in companies
        ),
        "error_count": sum(item["action"] == "error" for item in companies),
    }
    for field, expected in expected_counts.items():
        if normalized.get(field) != expected:
            raise MigrationError(f"migration plan {field} is inconsistent")
    if normalized.get("plan_sha256") != _plan_hash(normalized):
        raise MigrationError("migration plan sha256 mismatch")
    return normalized


def apply_migration_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    validated_plan = validate_migration_plan(plan)
    root = Path(validated_plan["research_root"])
    migration_id = str(validated_plan["migration_id"])
    applied_at = _parse_aware(validated_plan["created_at"], "created_at")
    results: list[dict[str, str]] = []
    for item in validated_plan["companies"]:
        company_rel = str(item["company_dir"])
        if item["action"] == "error":
            results.append(
                {
                    "company_dir": company_rel,
                    "status": "blocked",
                    "reason": str(item["error"]),
                }
            )
            continue
        company_dir = root / company_rel
        try:
            if item["action"] == "already_v2":
                validate_company_dir(company_dir)
                results.append(
                    {
                        "company_dir": company_rel,
                        "status": "already_v2",
                        "reason": "company was v2 before this migration",
                    }
                )
                continue
            status = _apply_company(
                root,
                company_dir,
                item,
                migration_id=migration_id,
                applied_at=applied_at,
            )
            results.append(
                {"company_dir": company_rel, "status": status, "reason": ""}
            )
        except (MigrationError, AssetValidationError, SealingError, OSError) as exc:
            results.append(
                {"company_dir": company_rel, "status": "failed", "reason": str(exc)}
            )
    result = {
        "schema_version": 2,
        "migration_id": migration_id,
        "plan_sha256": validated_plan["plan_sha256"],
        "company_count": len(results),
        "applied_count": sum(item["status"] == "migrated" for item in results),
        "already_applied_count": sum(
            item["status"] in {"already_applied", "already_v2"} for item in results
        ),
        "blocked_count": sum(item["status"] == "blocked" for item in results),
        "failed_count": sum(item["status"] == "failed" for item in results),
        "results": results,
    }
    state_path = root / "migrations" / migration_id / "state.json"
    atomic_write_bytes(
        state_path,
        (json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
            "utf-8"
        ),
    )
    return result


def _apply_company(
    root: Path,
    company_dir: Path,
    item: Mapping[str, Any],
    *,
    migration_id: str,
    applied_at: dt.datetime,
) -> str:
    snapshot_path = _snapshot_path(root, company_dir, migration_id)
    meta_path = company_dir / "meta.json"
    current = _read_json_object(meta_path)
    if current.get("schema_version") == 2:
        validate_company_dir(company_dir)
        sealed = verify_sealed(snapshot_path)
        if sealed.artifact_type != "legacy_company_meta":
            raise MigrationError("existing migration snapshot has the wrong type")
        _validate_migrated_identity(current, item)
        return "already_applied"

    scanned = _scan_company(root, company_dir, created_at=applied_at)
    if scanned["action"] != "migrate":
        raise MigrationError(
            f"company is no longer migratable: {scanned.get('error') or scanned['action']}"
        )
    if scanned["source_fingerprint"] != item["source_fingerprint"]:
        raise MigrationError("source fingerprint changed after dry-run")
    if scanned["identity"] != item["identity"]:
        raise MigrationError("company identity changed after dry-run")
    if scanned["historical_artifacts"] != item["historical_artifacts"]:
        raise MigrationError("historical report set changed after dry-run")

    seal_json(
        snapshot_path,
        current,
        artifact_type="legacy_company_meta",
        sealed_at=applied_at,
    )
    target = _target_meta(item, applied_at=applied_at)
    atomic_write_bytes(
        meta_path,
        (json.dumps(target, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
            "utf-8"
        ),
    )
    validate_company_dir(company_dir)
    return "migrated"


def _scan_company(
    root: Path, company_dir: Path, *, created_at: dt.datetime
) -> dict[str, Any]:
    rel = company_dir.relative_to(root).as_posix()
    base = {
        "company_dir": rel,
        "action": "error",
        "source_fingerprint": None,
        "identity": None,
        "updated_at": created_at.isoformat(),
        "historical_artifacts": [],
        "triggers": [],
        "reason_codes": [],
        "error": None,
    }
    meta_path = company_dir / "meta.json"
    try:
        raw_bytes = meta_path.read_bytes()
        raw = json.loads(raw_bytes.decode("utf-8-sig"))
        if not isinstance(raw, dict):
            raise MigrationError("legacy meta.json must contain an object")
        if raw.get("schema_version") == 2:
            validate_company_dir(company_dir)
            return {
                **base,
                "action": "already_v2",
                "source_fingerprint": hashlib.sha256(raw_bytes).hexdigest(),
                "identity": dict(raw["identity"]),
                "error": None,
            }
        identity = _legacy_identity(company_dir, raw)
        historical = _historical_artifacts(company_dir)
        fingerprint = _source_fingerprint(raw_bytes, historical)
        return {
            **base,
            "action": "migrate",
            "source_fingerprint": fingerprint,
            "identity": identity,
            "updated_at": _legacy_updated_at(raw, created_at),
            "historical_artifacts": historical,
            "triggers": _legacy_triggers(raw),
            "reason_codes": ["legacy_reports_require_structured_rebaseline"],
            "error": None,
        }
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        MigrationError,
        AssetValidationError,
    ) as exc:
        return {**base, "reason_codes": ["migration_scan_failed"], "error": str(exc)}


def _target_meta(item: Mapping[str, Any], *, applied_at: dt.datetime) -> dict[str, Any]:
    identity = dict(item["identity"])
    return {
        "schema_version": 2,
        "identity": identity,
        "research": {
            "coverage_status": "requires_rebaseline",
            "rebaseline_required": True,
            "information_cutoff": None,
        },
        "reports": {
            "latest": None,
            "latest_by_type": {},
            "history": [],
            "historical_artifacts": list(item["historical_artifacts"]),
        },
        "underwriting": {
            "status": None,
            "review_id": None,
            "confidence": None,
            "evidence_valid_until": None,
            "reason_codes": list(item["reason_codes"]),
        },
        "valuation": {
            "currency": None,
            "price_as_of": None,
            "bear_value": None,
            "fair_value_range": None,
            "buy_zone": None,
            "reduce_zone": None,
        },
        "triggers": list(item["triggers"]),
        "updated_at": applied_at.isoformat(),
    }


def _legacy_identity(company_dir: Path, raw: Mapping[str, Any]) -> dict[str, str]:
    market = _text(raw.get("market")) or company_dir.parent.name
    ticker = _text(raw.get("ticker")) or company_dir.name
    symbol = _text(raw.get("symbol")) or f"{market}:{ticker}"
    name = _text(raw.get("name")) or _text(raw.get("company_name"))
    if not name:
        raise MigrationError("legacy company name is missing")
    if symbol != f"{market}:{ticker}":
        raise MigrationError("legacy symbol, market, and ticker do not match")
    status = _text(raw.get("status"))
    security_status = status if status in {"active", "inactive", "archived"} else "active"
    currency = _text(raw.get("currency")) or _text(raw.get("base_currency"))
    if not currency:
        currency = {"CN": "CNY", "HK": "HKD", "US": "USD"}.get(market, "")
    if not currency:
        raise MigrationError("legacy currency is missing")
    return {
        "symbol": symbol,
        "market": market,
        "ticker": ticker,
        "name": name,
        "currency": currency,
        "security_status": security_status,
    }


def _historical_artifacts(company_dir: Path) -> list[dict[str, str]]:
    reports_dir = company_dir / "reports"
    reports = sorted(reports_dir.glob("*.md")) if reports_dir.is_dir() else []
    return [
        {
            "path": path.relative_to(company_dir).as_posix(),
            "format": "legacy_v1",
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in reports
    ]


def _source_fingerprint(raw_meta: bytes, historical: list[dict[str, str]]) -> str:
    source = {
        "meta_sha256": hashlib.sha256(raw_meta).hexdigest(),
        "historical_artifacts": historical,
    }
    return hashlib.sha256(canonical_json_bytes(source)).hexdigest()


def _legacy_updated_at(raw: Mapping[str, Any], fallback: dt.datetime) -> str:
    value = raw.get("updated_at")
    try:
        return _parse_aware(value, "legacy updated_at").isoformat()
    except MigrationError:
        return fallback.isoformat()


def _legacy_triggers(raw: Mapping[str, Any]) -> list[dict[str, Any]]:
    triggers: list[dict[str, Any]] = []
    for index, item in enumerate(raw.get("review_triggers", [])):
        if not isinstance(item, Mapping):
            continue
        reason = _text(item.get("reason")) or "迁移自旧复核触发器。"
        date = _text(item.get("date"))
        triggers.append(
            {
                "trigger_id": f"legacy-review-{index + 1}",
                "type": "date" if date else "event",
                "condition": {"date": date} if date else {"legacy": True},
                "reason": reason,
                "active": True,
            }
        )
    for index, item in enumerate(raw.get("price_triggers", [])):
        if not isinstance(item, Mapping):
            continue
        price = item.get("price")
        if isinstance(price, bool) or not isinstance(price, (int, float)):
            continue
        legacy_type = _text(item.get("type"))
        operator = "price_lte" if legacy_type == "price_below" else "price_gte"
        triggers.append(
            {
                "trigger_id": f"legacy-price-{index + 1}",
                "type": "price",
                "condition": {"operator": operator, "threshold": float(price)},
                "reason": _text(item.get("reason")) or "迁移自旧价格触发器。",
                "active": True,
            }
        )
    return triggers


def _snapshot_path(root: Path, company_dir: Path, migration_id: str) -> Path:
    relative = company_dir.relative_to(root / "companies")
    return root / "migrations" / migration_id / "companies" / relative / "legacy-meta.json"


def _validate_migrated_identity(meta: Mapping[str, Any], item: Mapping[str, Any]) -> None:
    if meta.get("identity") != item.get("identity"):
        raise MigrationError("already migrated company identity does not match the plan")


def _plan_hash(plan: Mapping[str, Any]) -> str:
    unsigned = {key: value for key, value in plan.items() if key != "plan_sha256"}
    return hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest()


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise MigrationError(f"invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise MigrationError(f"JSON file must contain an object: {path}")
    return value


def _company_dirs(companies_root: Path) -> list[Path]:
    if not companies_root.is_dir():
        return []
    return sorted(
        company_dir
        for market_dir in companies_root.iterdir()
        if market_dir.is_dir()
        for company_dir in market_dir.iterdir()
        if company_dir.is_dir() and (company_dir / "meta.json").is_file()
    )


def _validate_migration_id(value: str) -> None:
    if not MIGRATION_ID_RE.fullmatch(value):
        raise MigrationError("migration_id must contain lowercase letters, digits, or hyphens")


def _parse_aware(value: Any, label: str) -> dt.datetime:
    if not isinstance(value, str):
        raise MigrationError(f"{label} must be an ISO 8601 datetime")
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise MigrationError(f"{label} must be an ISO 8601 datetime") from exc
    _require_aware(parsed, label)
    return parsed


def _require_aware(value: dt.datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise MigrationError(f"{label} must include a UTC offset")


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None
