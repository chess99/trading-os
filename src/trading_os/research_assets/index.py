from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .company import AssetValidationError, validate_company_dir


@dataclass(frozen=True, slots=True)
class WriteResult:
    ok: bool
    path: Path
    errors: list[str]


def build_index(research_root: str | Path) -> dict[str, Any]:
    root = Path(research_root)
    companies_root = root / "companies"
    companies: list[dict[str, Any]] = []
    if companies_root.exists():
        for company_dir in _company_dirs(companies_root):
            meta = validate_company_dir(company_dir)
            rel_company = company_dir.relative_to(root)
            companies.append(
                {
                    "symbol": meta["symbol"],
                    "market": meta["market"],
                    "ticker": meta["ticker"],
                    "name": meta["name"],
                    "currency": meta["currency"],
                    "status": meta["status"],
                    "current_rating": meta["current_rating"],
                    "current_thesis": meta["current_thesis"],
                    "fair_value_range": meta["fair_value_range"],
                    "buy_zone": meta["buy_zone"],
                    "sell_or_reduce_zone": meta["sell_or_reduce_zone"],
                    "latest_report": _posix(rel_company / meta["latest_report"]),
                    "next_review_date": _next_review_date(meta),
                    "active_price_triggers": len(meta.get("price_triggers", [])),
                    "updated_at": meta["updated_at"],
                }
            )
    companies.sort(key=lambda item: item["symbol"])
    return {"schema_version": 1, "company_count": len(companies), "companies": companies}


def write_index(research_root: str | Path) -> WriteResult:
    root = Path(research_root)
    target = root / "index.json"
    try:
        payload = build_index(root)
    except AssetValidationError as exc:
        return WriteResult(ok=False, path=target, errors=[str(exc)])
    root.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(".json.tmp")
    temp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temp.replace(target)
    return WriteResult(ok=True, path=target, errors=[])


def _company_dirs(companies_root: Path) -> list[Path]:
    paths: list[Path] = []
    for market_dir in sorted(path for path in companies_root.iterdir() if path.is_dir()):
        for company_dir in sorted(path for path in market_dir.iterdir() if path.is_dir()):
            if (company_dir / "meta.json").exists():
                paths.append(company_dir)
    return paths


def _next_review_date(meta: dict[str, Any]) -> str | None:
    dates = [
        item["date"]
        for item in meta.get("review_triggers", [])
        if isinstance(item, dict)
        and item.get("type") == "date"
        and isinstance(item.get("date"), str)
    ]
    return min(dates) if dates else None


def _posix(path: Path) -> str:
    return path.as_posix()
