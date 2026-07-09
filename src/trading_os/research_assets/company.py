from __future__ import annotations

import datetime as dt
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ALLOWED_RATINGS = {"buy", "watch", "hold", "avoid", "sell", "research_only"}
ALLOWED_STATUSES = {"active", "inactive", "archived"}
ALLOWED_MARKETS = {"CN", "HK", "US"}
ALLOWED_REVIEW_TRIGGER_TYPES = {"date"}
ALLOWED_PRICE_TRIGGER_TYPES = {"price_below", "price_above"}
SYMBOL_RE = re.compile(r"^(CN|HK|US):[A-Z0-9.]+$")
REPORT_RE = re.compile(r"^reports/(\d{4}-\d{2}-\d{2})-[a-z0-9][a-z0-9-]*\.md$")
STANDARD_META_KEYS = {
    "symbol",
    "market",
    "ticker",
    "name",
    "currency",
    "status",
    "current_rating",
    "current_thesis",
    "fair_value_range",
    "buy_zone",
    "sell_or_reduce_zone",
    "position_plan",
    "latest_report",
    "report_history",
    "review_triggers",
    "price_triggers",
    "updated_at",
}
REQUIRED_REPORT_SECTIONS = [
    "结论版",
    "业务理解",
    "行业与竞争格局",
    "公司质量",
    "财务质量",
    "估值",
    "市场隐含预期",
    "情景与赔率",
    "价格与仓位计划",
    "关键假设",
    "跟踪触发器",
    "风险",
    "上一轮判断复盘",
    "来源",
]
REPORT_TYPE_RE = re.compile(r"^研究类型：(?P<kind>[a-z_]+)$")
ANALYST_RE = re.compile(r"^(?:- )?(?:分析师|Analyst)\s*[:：]\s*(?P<value>.+)$", re.I)


class AssetValidationError(ValueError):
    """Raised when a company research asset is invalid."""


def validate_company_dir(company_dir: str | Path, *, strict: bool = False) -> dict[str, Any]:
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
    if meta["symbol"] != f"{meta['market']}:{meta['ticker']}":
        raise AssetValidationError("symbol must match market and ticker fields")
    _require_company_dir_layout(path, meta)
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
    if strict:
        _require_strict_company_asset(path, meta)
    return meta


def audit_research_assets(research_root: str | Path) -> dict[str, Any]:
    root = Path(research_root)
    companies_root = root / "companies"
    company_dirs = _company_dirs(companies_root) if companies_root.exists() else []
    analyst_counts: Counter[str] = Counter()
    extra_meta_keys: Counter[str] = Counter()
    price_like_meta_keys: Counter[str] = Counter()
    strict_issues: list[dict[str, str]] = []
    validation_errors: list[dict[str, str]] = []

    for company_dir in company_dirs:
        meta_path = company_dir / "meta.json"
        try:
            meta = _read_json(meta_path)
        except AssetValidationError as exc:
            validation_errors.append({"company_dir": str(company_dir), "error": str(exc)})
            continue

        extras = sorted(set(meta) - STANDARD_META_KEYS)
        extra_meta_keys.update(extras)
        price_like_meta_keys.update(key for key in extras if _is_price_like_key(key))

        latest_report = meta.get("latest_report")
        report_path = company_dir / latest_report if isinstance(latest_report, str) else None
        analyst_counts[_classify_report_analyst(report_path)] += 1

        try:
            validate_company_dir(company_dir)
        except AssetValidationError as exc:
            validation_errors.append({"company_dir": str(company_dir), "error": str(exc)})
            continue

        for issue in _strict_company_issues(company_dir, meta):
            strict_issues.append({"company_dir": str(company_dir), "error": issue})

    return {
        "schema_version": 1,
        "company_count": len(company_dirs),
        "analyst_counts": dict(sorted(analyst_counts.items())),
        "extra_meta_keys": _counter_items(extra_meta_keys),
        "price_like_meta_keys": _counter_items(price_like_meta_keys),
        "strict_issue_count": len(strict_issues),
        "strict_issues": strict_issues,
        "validation_errors": validation_errors,
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise AssetValidationError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise AssetValidationError(f"meta.json must contain an object: {path}")
    return data


def _company_dirs(companies_root: Path) -> list[Path]:
    paths: list[Path] = []
    for market_dir in sorted(path for path in companies_root.iterdir() if path.is_dir()):
        for company_dir in sorted(path for path in market_dir.iterdir() if path.is_dir()):
            if (company_dir / "meta.json").exists():
                paths.append(company_dir)
    return paths


def _require_strict_company_asset(company_dir: Path, meta: dict[str, Any]) -> None:
    issues = _strict_company_issues(company_dir, meta)
    if issues:
        raise AssetValidationError(issues[0])


def _strict_company_issues(company_dir: Path, meta: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    extra_keys = sorted(set(meta) - STANDARD_META_KEYS)
    if extra_keys:
        issues.append(f"extra meta keys are not allowed in strict mode: {extra_keys}")

    report_path = company_dir / meta["latest_report"]
    try:
        text = report_path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        return [f"latest report could not be read: {exc}"]

    lines = [line.strip() for line in text.splitlines()]
    first_non_empty = next((line for line in lines if line), "")
    if first_non_empty != f"# 公司研究：{meta['name']}（{meta['symbol']}）":
        issues.append(
            "report title must be '# 公司研究：{name}（MARKET:TICKER）' "
            f"for {meta['symbol']}"
        )

    date_line = _find_prefixed_line(lines[:10], "日期：")
    if date_line is None:
        issues.append("report date line must be '日期：YYYY-MM-DD'")
    else:
        date_text = date_line.removeprefix("日期：")
        try:
            dt.date.fromisoformat(date_text)
        except ValueError:
            issues.append("report date line must contain a real YYYY-MM-DD date")

    report_type_line = _find_prefixed_line(lines[:10], "研究类型：")
    if report_type_line is None or REPORT_TYPE_RE.match(report_type_line) is None:
        issues.append("report research type line must be '研究类型：initial|followup|...'")

    analyst_line = _find_analyst_line(lines[:20])
    if analyst_line is None:
        issues.append("report analyst line must be '分析师：具体工具 + 模型'")
    else:
        analyst = ANALYST_RE.match(analyst_line)
        analyst_value = analyst.group("value").strip() if analyst else ""
        analyst_problem = _analyst_problem(analyst_value)
        if analyst_problem:
            issues.append(analyst_problem)

    headings = {
        line.removeprefix("## ").strip()
        for line in lines
        if line.startswith("## ")
    }
    missing_sections = [
        section for section in REQUIRED_REPORT_SECTIONS if section not in headings
    ]
    if missing_sections:
        issues.append(f"report section missing: {missing_sections[0]}")

    return issues


def _find_prefixed_line(lines: list[str], prefix: str) -> str | None:
    return next((line for line in lines if line.startswith(prefix)), None)


def _find_analyst_line(lines: list[str]) -> str | None:
    return next((line for line in lines if ANALYST_RE.match(line)), None)


def _analyst_problem(value: str) -> str | None:
    normalized = value.strip().lower()
    if not normalized:
        return "report analyst line must name the actual tool and model"
    if normalized == "agent" or normalized.startswith("agent "):
        return "report analyst line must not use generic analyst label 'agent'"
    if normalized.startswith("codex-subagent"):
        return "report analyst line must not use opaque codex-subagent labels"
    if "unknown" in normalized:
        return "report analyst line must not use unknown model labels in strict mode"
    if "+" not in value:
        return "report analyst line must include actual tool + model"
    return None


def _classify_report_analyst(report_path: Path | None) -> str:
    if report_path is None or not report_path.exists():
        return "missing"
    try:
        text = report_path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return "missing"
    analyst_line = _find_analyst_line([line.strip() for line in text.splitlines()[:40]])
    if analyst_line is None:
        return "missing"
    match = ANALYST_RE.match(analyst_line)
    value = match.group("value").strip().lower() if match else ""
    if "codex" in value:
        return "codex"
    if "claude" in value:
        return "claude"
    if value == "agent" or "unknown" in value:
        return "generic_or_unknown"
    return "other"


def _is_price_like_key(key: str) -> bool:
    lowered = key.lower()
    return "price" in lowered or "现价" in key or "价格" in key


def _counter_items(counter: Counter[str]) -> list[dict[str, int | str]]:
    return [
        {"key": key, "count": count}
        for key, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    ]


def _require_string(meta: dict[str, Any], key: str) -> None:
    value = meta.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AssetValidationError(f"{key} must be a non-empty string")


def _require_company_dir_layout(company_dir: Path, meta: dict[str, Any]) -> None:
    if company_dir.parent.name != meta["market"] or company_dir.name != meta["ticker"]:
        raise AssetValidationError(
            "company directory must match research/companies/{MARKET}/{TICKER}"
        )


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
