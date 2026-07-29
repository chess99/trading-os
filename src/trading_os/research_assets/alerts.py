from __future__ import annotations

import datetime as dt
import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .company import validate_company_dir
from .index import _company_dirs
from .sealing import atomic_write_bytes, verify_sealed

PRICE_STALE_FRACTION = 0.10
QUOTE_MAX_AGE = dt.timedelta(days=7)
QUOTE_FUTURE_TOLERANCE = dt.timedelta(minutes=5)


class PriceAlertError(ValueError):
    """Raised when an alert or quote snapshot cannot be evaluated safely."""


def build_price_alerts(research_root: str | Path) -> dict[str, Any]:
    root = Path(research_root)
    items: list[dict[str, Any]] = []
    rebaseline_symbols: set[str] = set()
    companies_root = root / "companies"
    if companies_root.exists():
        for company_dir in _company_dirs(companies_root):
            meta = validate_company_dir(company_dir)
            identity = meta["identity"]
            if meta["research"]["rebaseline_required"]:
                rebaseline_symbols.add(identity["symbol"])
                continue
            underwriting = meta["underwriting"]
            valuation = meta["valuation"]
            latest_report = _latest_report(root, company_dir, meta)
            if underwriting["status"] == "passed" and valuation["buy_zone"] is not None:
                items.append(
                    {
                        "alert_id": f"{identity['symbol']}:underwriting-buy-zone",
                        "symbol": identity["symbol"],
                        "name": identity["name"],
                        "type": "underwriting_buy_zone_entry",
                        "condition": {
                            "operator": "price_lte",
                            "threshold": valuation["buy_zone"][1],
                        },
                        "reason": (
                            "价格进入承保买入区；执行前必须重查证据有效性、"
                            "最新预期回报和核心逻辑。"
                        ),
                        "latest_report": latest_report,
                        "source_ref": underwriting["review_id"],
                    }
                )
            reference = _underwriting_reference(company_dir, meta)
            if underwriting["review_id"] is not None and reference is not None:
                items.append(
                    {
                        "alert_id": f"{identity['symbol']}:conclusion-price-stale",
                        "symbol": identity["symbol"],
                        "name": identity["name"],
                        "type": "conclusion_price_move_stale",
                        "condition": {
                            "operator": "absolute_change_fraction_gte",
                            "threshold": PRICE_STALE_FRACTION,
                            "reference_price": reference["price"],
                            "reference_price_as_of": reference["price_as_of"],
                            "reference_source_sha256": reference["sha256"],
                        },
                        "reason": (
                            "相对承保复核价变动达到10%，原价格结论自动过期。"
                        ),
                        "latest_report": latest_report,
                        "source_ref": underwriting["review_id"],
                    }
                )
            for trigger in meta["triggers"]:
                if (
                    (
                        underwriting["status"] == "passed"
                        or _has_research_price_watch(meta)
                    )
                    and trigger["active"]
                    and trigger["type"] == "price"
                ):
                    items.append(
                        {
                            "alert_id": f"{identity['symbol']}:{trigger['trigger_id']}",
                            "symbol": identity["symbol"],
                            "name": identity["name"],
                            "type": (
                                "company_price_trigger"
                                if underwriting["status"] == "passed"
                                else "research_price_trigger"
                            ),
                            "condition": trigger["condition"],
                            "reason": trigger["reason"],
                            "latest_report": latest_report,
                            "source_ref": trigger["trigger_id"],
                        }
                    )
    items.extend(_portfolio_observations(root, excluded_symbols=rebaseline_symbols))
    items.sort(key=lambda item: (item["symbol"], item["type"], item["alert_id"]))
    return {"schema_version": 2, "item_count": len(items), "items": items}


def write_price_alerts(research_root: str | Path, output_path: str | Path) -> Path:
    payload = build_price_alerts(research_root)
    target = Path(output_path)
    content = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    return atomic_write_bytes(target, content)


def evaluate_price_alerts(
    alerts: dict[str, Any],
    quotes: list[Any],
    *,
    evaluated_at: dt.datetime | None = None,
) -> dict[str, Any]:
    cutoff = evaluated_at or dt.datetime.now().astimezone()
    _require_aware_datetime(cutoff, "evaluated_at")
    quote_by_symbol = _validated_quote_snapshot(quotes, evaluated_at=cutoff)
    triggered: list[dict[str, Any]] = []
    for alert in alerts.get("items", []):
        if not isinstance(alert, Mapping):
            continue
        quote = quote_by_symbol.get(str(alert.get("symbol")))
        if quote is None or not _condition_met(alert.get("condition"), quote):
            continue
        triggered.append(_triggered(alert, quote))
    triggered.sort(key=lambda item: (item["symbol"], item["type"], item["alert_id"]))
    return {
        "schema_version": 2,
        "evaluated_at": cutoff.isoformat(),
        "quote_max_age_seconds": int(QUOTE_MAX_AGE.total_seconds()),
        "triggered_count": len(triggered),
        "triggered": triggered,
    }


def evaluate_price_alert_observations(
    alerts: dict[str, Any],
    quotes: list[Any],
    *,
    evaluated_at: dt.datetime,
) -> list[dict[str, Any]]:
    """Return all observable price conditions, including false rearms."""

    _require_aware_datetime(evaluated_at, "evaluated_at")
    quote_by_symbol = _validated_quote_snapshot(quotes, evaluated_at=evaluated_at)
    observations: list[dict[str, Any]] = []
    for alert in alerts.get("items", []):
        if not isinstance(alert, Mapping):
            continue
        symbol = str(alert.get("symbol"))
        quote = quote_by_symbol.get(symbol)
        condition = alert.get("condition")
        if quote is None or not isinstance(condition, Mapping):
            continue
        if condition.get("operator") not in {
            "price_lte",
            "price_gte",
            "absolute_change_fraction_gte",
        }:
            continue
        observations.append(
            {
                "alert": dict(alert),
                "condition_met": _condition_met(condition, quote),
                "quote": dict(quote),
            }
        )
    observations.sort(
        key=lambda item: (
            str(item["alert"].get("symbol")),
            str(item["alert"].get("alert_id")),
        )
    )
    return observations


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _condition_met(condition: Any, quote: Mapping[str, Any]) -> bool:
    if not isinstance(condition, Mapping):
        return False
    operator = condition.get("operator")
    threshold = _number(condition.get("threshold"))
    if operator in {"price_lte", "price_gte"}:
        price = _price_from_quote(quote)
        if price is None or threshold is None:
            return False
        return price <= threshold if operator == "price_lte" else price >= threshold
    if operator == "absolute_change_fraction_gte":
        change = _change_since_reference(condition, quote)
        if change is None:
            return False
        return threshold is not None and abs(change) >= threshold
    if operator == "observe":
        return True
    return False


def _portfolio_observations(
    root: Path, *, excluded_symbols: set[str] | None = None
) -> list[dict[str, Any]]:
    batches_root = root / "batches"
    if not batches_root.is_dir():
        return []
    latest: dict[str, tuple[dt.datetime, str, dict[str, Any]]] = {}
    for portfolio_path in sorted(batches_root.glob("*/portfolio.json")):
        try:
            sealed = verify_sealed(portfolio_path)
        except ValueError:
            continue
        if sealed.artifact_type != "model_portfolio":
            continue
        payload = load_json(portfolio_path)
        if not isinstance(payload, Mapping):
            continue
        try:
            portfolio_as_of = dt.datetime.fromisoformat(str(payload.get("as_of")))
        except ValueError:
            continue
        if portfolio_as_of.tzinfo is None or portfolio_as_of.utcoffset() is None:
            continue
        run_id = str(payload.get("run_id") or portfolio_path.parent.name)
        for position in payload.get("positions", []):
            if not isinstance(position, Mapping):
                continue
            symbol = str(position.get("symbol"))
            if not symbol or symbol in (excluded_symbols or set()):
                continue
            prior = latest.get(symbol)
            if prior is None or portfolio_as_of > prior[0]:
                latest[symbol] = (portfolio_as_of, run_id, dict(position))

    observations: list[dict[str, Any]] = []
    for symbol, (_, run_id, position) in sorted(latest.items()):
        action = str(position.get("action"))
        if action in {"reduce", "exit"}:
            observations.append(
                {
                    "alert_id": f"{symbol}:portfolio-{action}",
                    "symbol": symbol,
                    "name": str(position.get("name") or symbol),
                    "type": f"portfolio_{action}_observation",
                    "condition": {"operator": "observe"},
                    "reason": f"封存模型组合给出 {action}，需要复核持仓处置。",
                    "latest_report": None,
                    "source_ref": f"batches/{run_id}/portfolio.json",
                }
            )
        reasons = {
            str(value) for value in position.get("reason_codes", []) if value
        }
        threshold = _number(position.get("buy_now_price_ceiling"))
        if (
            position.get("underwriting_status") == "passed"
            and not bool(position.get("evidence_stale"))
            and action in {"watch", "buy_on_weakness"}
            and reasons.intersection(
                {"expected_return_below_minimum", "price_above_buy_zone"}
            )
            and threshold is not None
            and threshold > 0
        ):
            observations.append(
                {
                    "alert_id": f"{symbol}:portfolio-buy-threshold",
                    "symbol": symbol,
                    "name": str(position.get("name") or symbol),
                    "type": "portfolio_buy_threshold_entry",
                    "condition": {
                        "operator": "price_lte",
                        "threshold": threshold,
                    },
                    "reason": (
                        "价格进入同时满足安全边际与组合最低回报的区间；"
                        "执行前必须按最新证据重新运行组合决策。"
                    ),
                    "latest_report": None,
                    "source_ref": f"batches/{run_id}/portfolio.json",
                }
            )
    return observations


def _price_from_quote(quote: Mapping[str, Any]) -> float | None:
    for key in ("price", "close", "last"):
        value = _number(quote.get(key))
        if value is not None:
            return value
    return None


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _triggered(alert: Mapping[str, Any], quote: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "alert_id": alert["alert_id"],
        "symbol": alert["symbol"],
        "name": alert["name"],
        "type": alert["type"],
        "condition": alert["condition"],
        "observed_price": _price_from_quote(quote),
        "change_since_review": _change_since_reference(
            alert.get("condition"), quote
        ),
        "reason": alert["reason"],
        "latest_report": alert["latest_report"],
        "source_ref": alert["source_ref"],
        "quote_as_of": quote.get("as_of"),
    }


def _latest_report(root: Path, company_dir: Path, meta: dict[str, Any]) -> str | None:
    latest = meta["reports"]["latest"]
    return (company_dir.relative_to(root) / latest).as_posix() if latest else None


def _has_research_price_watch(meta: Mapping[str, Any]) -> bool:
    research = meta.get("research")
    return bool(
        isinstance(research, Mapping)
        and research.get("coverage_status") == "covered"
        and isinstance(research.get("latest_rapid_triage"), Mapping)
    )


def _validated_quote_snapshot(
    quotes: list[Any], *, evaluated_at: dt.datetime
) -> dict[str, Mapping[str, Any]]:
    quote_by_symbol: dict[str, Mapping[str, Any]] = {}
    for index, item in enumerate(quotes):
        if not isinstance(item, Mapping):
            raise PriceAlertError(f"quote[{index}] must be an object")
        symbol = item.get("symbol")
        if not isinstance(symbol, str) or not symbol.strip():
            raise PriceAlertError(f"quote[{index}].symbol must be a non-empty string")
        symbol = symbol.strip()
        if symbol in quote_by_symbol:
            raise PriceAlertError(f"duplicate quote symbol: {symbol}")
        price = _price_from_quote(item)
        if price is None or price <= 0:
            raise PriceAlertError(f"invalid quote price for {symbol}")
        quote_time = _parse_aware_datetime(
            item.get("as_of"), f"quote {symbol} as_of"
        )
        if evaluated_at - quote_time > QUOTE_MAX_AGE:
            raise PriceAlertError(f"stale quote for {symbol}: {quote_time.isoformat()}")
        if quote_time - evaluated_at > QUOTE_FUTURE_TOLERANCE:
            raise PriceAlertError(
                f"quote is too far in the future for {symbol}: {quote_time.isoformat()}"
            )
        quote_by_symbol[symbol] = item
    return quote_by_symbol


def _underwriting_reference(
    company_dir: Path, meta: Mapping[str, Any]
) -> dict[str, Any] | None:
    underwriting = meta.get("underwriting")
    identity = meta.get("identity")
    valuation = meta.get("valuation")
    if not all(
        isinstance(value, Mapping)
        for value in (underwriting, identity, valuation)
    ):
        return None
    review_id = underwriting.get("review_id")
    symbol = identity.get("symbol")
    if not isinstance(review_id, str) or not review_id.strip():
        return None
    if not isinstance(symbol, str) or not symbol:
        return None

    underwriting_root = (company_dir / "underwriting").resolve()
    review_dir = (underwriting_root / review_id).resolve()
    if review_dir.parent != underwriting_root:
        raise PriceAlertError(
            f"underwriting review path escapes company directory: {review_id}"
        )
    candidate_path = next(
        (
            review_dir / filename
            for filename in (
                "portfolio-candidate.final.json",
                "portfolio-candidate.primary.json",
                "portfolio-candidate.json",
            )
            if (review_dir / filename).is_file()
        ),
        None,
    )
    if candidate_path is None:
        # Legacy metadata without a sealed candidate remains valid, but cannot
        # safely produce a percentage-change invalidation alert.
        return None
    try:
        sealed = verify_sealed(candidate_path)
    except ValueError as exc:
        raise PriceAlertError(
            f"underwriting reference is not validly sealed: {candidate_path}"
        ) from exc
    if sealed.artifact_type != "portfolio_candidate":
        raise PriceAlertError(
            f"underwriting reference has wrong artifact type: {candidate_path}"
        )
    payload = load_json(candidate_path)
    if not isinstance(payload, Mapping):
        raise PriceAlertError(
            f"underwriting reference must be an object: {candidate_path}"
        )
    if payload.get("symbol") != symbol:
        raise PriceAlertError(
            f"underwriting reference symbol mismatch: {candidate_path}"
        )
    price = _number(payload.get("current_price"))
    if price is None or price <= 0:
        raise PriceAlertError(
            f"underwriting reference price is invalid: {candidate_path}"
        )
    price_as_of = payload.get("price_as_of")
    if price_as_of is None:
        price_as_of = valuation.get("price_as_of")
    parsed_as_of = _parse_aware_datetime(
        price_as_of, f"underwriting reference {symbol} price_as_of"
    )
    return {
        "price": price,
        "price_as_of": parsed_as_of.isoformat(),
        "sha256": sealed.sha256,
    }


def _change_since_reference(
    condition: Any, quote: Mapping[str, Any]
) -> float | None:
    if not isinstance(condition, Mapping):
        return None
    if condition.get("operator") != "absolute_change_fraction_gte":
        return None
    price = _price_from_quote(quote)
    reference = _number(condition.get("reference_price"))
    if price is None or reference is None or reference <= 0:
        return None
    return price / reference - 1


def _parse_aware_datetime(value: Any, label: str) -> dt.datetime:
    if not isinstance(value, str):
        raise PriceAlertError(f"{label} must be an ISO 8601 timestamp")
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise PriceAlertError(f"{label} must be an ISO 8601 timestamp") from exc
    _require_aware_datetime(parsed, label)
    return parsed


def _require_aware_datetime(value: dt.datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise PriceAlertError(f"{label} must include timezone information")
