from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

ALLOWED_RATINGS = {"buy", "watch", "hold", "avoid", "sell", "research_only"}
ALLOWED_STATUSES = {"active", "inactive", "archived"}
ALLOWED_MARKETS = {"CN", "HK", "US"}
ALLOWED_REVIEW_TRIGGER_TYPES = {"date"}
ALLOWED_PRICE_TRIGGER_TYPES = {"price_below", "price_above"}
SYMBOL_RE = re.compile(r"^(CN|HK|US):[A-Z0-9.]+$")
REPORT_RE = re.compile(r"^reports/(\d{4}-\d{2}-\d{2})-[a-z0-9][a-z0-9-]*\.md$")


class AssetValidationError(ValueError):
    """Raised when a company research asset is invalid."""


def validate_company_dir(company_dir: str | Path) -> dict[str, Any]:
    path = Path(company_dir)
    if not path.exists():
        raise AssetValidationError(f"company directory does not exist: {path}")
    if not path.is_dir():
        raise AssetValidationError(f"company path is not a directory: {path}")
    meta_path = path / "meta.json"
    if not meta_path.exists():
        raise AssetValidationError(f"missing meta.json: {meta_path}")
    meta = _read_json(meta_path)
    _require_string(meta, "symbol")
    _require_string(meta, "market")
    _require_string(meta, "ticker")
    _require_string(meta, "name")
    _require_string(meta, "currency")
    _require_string(meta, "status")
    _require_string(meta, "current_rating")
    _require_string(meta, "current_thesis")
    _require_string(meta, "latest_report")
    _require_string(meta, "updated_at")
    if not SYMBOL_RE.match(meta["symbol"]):
        raise AssetValidationError(f"symbol must match MARKET:TICKER: {meta['symbol']}")
    if meta["market"] not in ALLOWED_MARKETS:
        raise AssetValidationError(f"market must be one of {sorted(ALLOWED_MARKETS)}")
    if not meta["symbol"].startswith(meta["market"] + ":"):
        raise AssetValidationError("symbol market prefix must match market field")
    if meta["status"] not in ALLOWED_STATUSES:
        raise AssetValidationError(f"status must be one of {sorted(ALLOWED_STATUSES)}")
    if meta["current_rating"] not in ALLOWED_RATINGS:
        raise AssetValidationError(
            f"current_rating must be one of {sorted(ALLOWED_RATINGS)}"
        )
    _require_number_range(meta, "fair_value_range")
    _require_number_range(meta, "buy_zone")
    _require_number_range(meta, "sell_or_reduce_zone")
    _require_report(path, meta["latest_report"], "latest_report")
    _require_report_list(path, meta.get("report_history"), "report_history")
    if meta["latest_report"] not in meta["report_history"]:
        raise AssetValidationError("latest_report must appear in report_history")
    _require_position_plan(meta.get("position_plan"))
    _require_review_triggers(meta.get("review_triggers"))
    _require_price_triggers(meta.get("price_triggers"))
    return meta


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AssetValidationError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise AssetValidationError(f"meta.json must contain an object: {path}")
    return data


def _require_string(meta: dict[str, Any], key: str) -> None:
    value = meta.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AssetValidationError(f"{key} must be a non-empty string")


def _require_number_range(meta: dict[str, Any], key: str) -> None:
    value = meta.get(key)
    if not isinstance(value, list) or len(value) != 2:
        raise AssetValidationError(f"{key} must be a two-item number list")
    low, high = value
    if not _is_number(low) or not _is_number(high):
        raise AssetValidationError(f"{key} values must be numbers")
    if low > high:
        raise AssetValidationError(f"{key} lower bound must be <= upper bound")


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _require_report(company_dir: Path, rel_path: str, field: str) -> None:
    normalized = rel_path.replace("\\", "/")
    match = REPORT_RE.match(normalized)
    if not match:
        raise AssetValidationError(
            f"{field} must match reports/YYYY-MM-DD-slug.md"
        )
    try:
        dt.date.fromisoformat(match.group(1))
    except ValueError as exc:
        raise AssetValidationError(
            f"{field} must match reports/YYYY-MM-DD-slug.md"
        ) from exc
    report_path = Path(rel_path)
    if report_path.is_absolute():
        raise AssetValidationError(f"{field} must be a relative path inside company dir")
    company_root = company_dir.resolve()
    target = (company_root / report_path).resolve()
    try:
        target.relative_to(company_root)
    except ValueError as exc:
        raise AssetValidationError(
            f"{field} must be a relative path inside company dir"
        ) from exc
    if not target.exists():
        raise AssetValidationError(f"{field} points to missing report: {rel_path}")
    if not target.is_file():
        raise AssetValidationError(f"{field} must point to a report file")
    if target.suffix.lower() != ".md":
        raise AssetValidationError(f"{field} must point to a Markdown report")


def _require_report_list(company_dir: Path, value: Any, field: str) -> None:
    if not isinstance(value, list) or not value:
        raise AssetValidationError(f"{field} must be a non-empty list")
    for item in value:
        if not isinstance(item, str):
            raise AssetValidationError(f"{field} entries must be strings")
        _require_report(company_dir, item, field)


def _require_position_plan(value: Any) -> None:
    if not isinstance(value, list) or not value:
        raise AssetValidationError("position_plan must be a non-empty list")
    for item in value:
        if not isinstance(item, dict):
            raise AssetValidationError("position_plan entries must be objects")
        condition = item.get("condition")
        max_weight = item.get("max_weight")
        if not isinstance(condition, str) or not condition.strip():
            raise AssetValidationError("position_plan condition must be a non-empty string")
        if not _is_number(max_weight) or max_weight < 0 or max_weight > 1:
            raise AssetValidationError("position_plan max_weight must be between 0 and 1")


def _require_review_triggers(value: Any) -> None:
    if not isinstance(value, list):
        raise AssetValidationError("review_triggers must be a list")
    for item in value:
        if not isinstance(item, dict):
            raise AssetValidationError("review_triggers entries must be objects")
        if item.get("type") not in ALLOWED_REVIEW_TRIGGER_TYPES:
            raise AssetValidationError("review_triggers type must be date")
        date = item.get("date")
        if not isinstance(date, str) or not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
            raise AssetValidationError("review_triggers date must use YYYY-MM-DD")
        try:
            dt.date.fromisoformat(date)
        except ValueError as exc:
            raise AssetValidationError(
                "review_triggers date must be a real YYYY-MM-DD date"
            ) from exc
        if not isinstance(item.get("reason"), str) or not item["reason"].strip():
            raise AssetValidationError("review_triggers reason must be a non-empty string")


def _require_price_triggers(value: Any) -> None:
    if not isinstance(value, list):
        raise AssetValidationError("price_triggers must be a list")
    for item in value:
        if not isinstance(item, dict):
            raise AssetValidationError("price_triggers entries must be objects")
        if item.get("type") not in ALLOWED_PRICE_TRIGGER_TYPES:
            raise AssetValidationError(
                "price_triggers type must be price_below or price_above"
            )
        if not _is_number(item.get("price")):
            raise AssetValidationError("price_triggers price must be numeric")
        if not isinstance(item.get("reason"), str) or not item["reason"].strip():
            raise AssetValidationError("price_triggers reason must be a non-empty string")
