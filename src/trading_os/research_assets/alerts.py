from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .company import validate_company_dir
from .index import _company_dirs
from .sealing import atomic_write_bytes, verify_sealed

PRICE_STALE_FRACTION = 0.10


def build_price_alerts(research_root: str | Path) -> dict[str, Any]:
    root = Path(research_root)
    items: list[dict[str, Any]] = []
    companies_root = root / "companies"
    if companies_root.exists():
        for company_dir in _company_dirs(companies_root):
            meta = validate_company_dir(company_dir)
            identity = meta["identity"]
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
                        "reason": "价格进入承保买入区；执行前必须重查证据有效性和核心逻辑。",
                        "latest_report": latest_report,
                        "source_ref": underwriting["review_id"],
                    }
                )
            if underwriting["review_id"] is not None:
                items.append(
                    {
                        "alert_id": f"{identity['symbol']}:conclusion-price-stale",
                        "symbol": identity["symbol"],
                        "name": identity["name"],
                        "type": "conclusion_price_move_stale",
                        "condition": {
                            "operator": "absolute_change_fraction_gte",
                            "threshold": PRICE_STALE_FRACTION,
                            "reference_price_as_of": valuation["price_as_of"],
                        },
                        "reason": "相对承保复核价变动达到 10%，原价格结论自动过期。",
                        "latest_report": latest_report,
                        "source_ref": underwriting["review_id"],
                    }
                )
            for trigger in meta["triggers"]:
                if trigger["active"] and trigger["type"] == "price":
                    items.append(
                        {
                            "alert_id": f"{identity['symbol']}:{trigger['trigger_id']}",
                            "symbol": identity["symbol"],
                            "name": identity["name"],
                            "type": "company_price_trigger",
                            "condition": trigger["condition"],
                            "reason": trigger["reason"],
                            "latest_report": latest_report,
                            "source_ref": trigger["trigger_id"],
                        }
                    )
    items.extend(_portfolio_observations(root))
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
    alerts: dict[str, Any], quotes: list[dict[str, Any]]
) -> dict[str, Any]:
    quote_by_symbol = {
        str(item["symbol"]): item
        for item in quotes
        if isinstance(item, Mapping) and "symbol" in item
    }
    triggered: list[dict[str, Any]] = []
    for alert in alerts.get("items", []):
        if not isinstance(alert, Mapping):
            continue
        quote = quote_by_symbol.get(str(alert.get("symbol")))
        if quote is None or not _condition_met(alert.get("condition"), quote):
            continue
        triggered.append(_triggered(alert, quote))
    triggered.sort(key=lambda item: (item["symbol"], item["type"], item["alert_id"]))
    return {"schema_version": 2, "triggered_count": len(triggered), "triggered": triggered}


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
        change = _number(quote.get("change_since_review"))
        if change is None:
            price = _price_from_quote(quote)
            reference = _number(quote.get("review_price"))
            if price is None or reference is None or reference <= 0:
                return False
            change = price / reference - 1
        return threshold is not None and abs(change) >= threshold
    if operator == "observe":
        return True
    return False


def _portfolio_observations(root: Path) -> list[dict[str, Any]]:
    batches_root = root / "batches"
    if not batches_root.is_dir():
        return []
    latest: dict[str, tuple[str, dict[str, Any]]] = {}
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
        run_id = str(payload.get("run_id") or portfolio_path.parent.name)
        for position in payload.get("positions", []):
            if not isinstance(position, Mapping) or position.get("action") not in {
                "reduce",
                "exit",
            }:
                continue
            symbol = str(position.get("symbol"))
            if not symbol:
                continue
            latest[symbol] = (run_id, dict(position))
    observations: list[dict[str, Any]] = []
    for symbol, (run_id, position) in sorted(latest.items()):
        action = str(position["action"])
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
    return float(value)


def _triggered(alert: Mapping[str, Any], quote: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "alert_id": alert["alert_id"],
        "symbol": alert["symbol"],
        "name": alert["name"],
        "type": alert["type"],
        "condition": alert["condition"],
        "observed_price": _price_from_quote(quote),
        "change_since_review": _number(quote.get("change_since_review")),
        "reason": alert["reason"],
        "latest_report": alert["latest_report"],
        "source_ref": alert["source_ref"],
        "quote_as_of": quote.get("as_of"),
    }


def _latest_report(root: Path, company_dir: Path, meta: dict[str, Any]) -> str | None:
    latest = meta["reports"]["latest"]
    return (company_dir.relative_to(root) / latest).as_posix() if latest else None
