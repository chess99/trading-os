from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .company import validate_company_dir
from .index import _company_dirs


def build_price_alerts(research_root: str | Path) -> dict[str, Any]:
    root = Path(research_root)
    items: list[dict[str, Any]] = []
    companies_root = root / "companies"
    if companies_root.exists():
        for company_dir in _company_dirs(companies_root):
            meta = validate_company_dir(company_dir)
            rel_company = company_dir.relative_to(root)
            for trigger in meta.get("price_triggers", []):
                items.append(
                    {
                        "symbol": meta["symbol"],
                        "name": meta["name"],
                        "type": trigger["type"],
                        "price": trigger["price"],
                        "reason": trigger["reason"],
                        "latest_report": (
                            rel_company / meta["latest_report"]
                        ).as_posix(),
                    }
                )
    items.sort(key=lambda item: (item["symbol"], item["type"], float(item["price"])))
    return {"schema_version": 1, "item_count": len(items), "items": items}


def write_price_alerts(research_root: str | Path, output_path: str | Path) -> Path:
    payload = build_price_alerts(research_root)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return target


def evaluate_price_alerts(
    alerts: dict[str, Any], quotes: list[dict[str, Any]]
) -> dict[str, Any]:
    quote_by_symbol = {str(item["symbol"]): item for item in quotes if "symbol" in item}
    triggered: list[dict[str, Any]] = []
    for alert in alerts.get("items", []):
        quote = quote_by_symbol.get(str(alert.get("symbol")))
        if not quote:
            continue
        observed = _price_from_quote(quote)
        if observed is None:
            continue
        target = float(alert["price"])
        kind = alert["type"]
        if kind == "price_below" and observed <= target:
            triggered.append(_triggered(alert, quote, observed))
        elif kind == "price_above" and observed >= target:
            triggered.append(_triggered(alert, quote, observed))
    return {"schema_version": 1, "triggered_count": len(triggered), "triggered": triggered}


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _price_from_quote(quote: dict[str, Any]) -> float | None:
    for key in ("price", "close", "last"):
        value = quote.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _triggered(
    alert: dict[str, Any], quote: dict[str, Any], observed: float
) -> dict[str, Any]:
    return {
        "symbol": alert["symbol"],
        "name": alert["name"],
        "type": alert["type"],
        "trigger_price": alert["price"],
        "observed_price": observed,
        "reason": alert["reason"],
        "latest_report": alert["latest_report"],
        "quote_as_of": quote.get("as_of"),
    }
