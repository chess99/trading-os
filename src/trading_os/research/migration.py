from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from .store import ResearchStore


@dataclass(slots=True)
class MigrationStats:
    success: int = 0
    failed: int = 0
    skipped: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)


def migrate_legacy_fundamentals(
    source_dir: Path,
    store: ResearchStore,
    *,
    as_of: date,
) -> MigrationStats:
    """Move legacy per-symbol fundamental JSON files into ResearchStore."""
    try:
        import pandas as pd
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise RuntimeError("legacy fundamental migration requires pandas") from exc

    stats = MigrationStats()
    rows: list[dict[str, Any]] = []
    for path in sorted(source_dir.glob("*.json")):
        try:
            row = _legacy_fundamental_row(path)
        except ValueError as exc:
            stats.failed += 1
            stats.errors.append({"file": path.name, "error": str(exc)})
            continue
        if row is None:
            stats.skipped += 1
            continue
        rows.append(row)
        stats.success += 1

    if rows:
        store.write_fundamentals(
            pd.DataFrame(rows),
            as_of=as_of,
            source="legacy_fundamental_json",
            provenance={"source_dir": str(source_dir), "files": len(rows)},
            freshness_policy="quarterly",
        )
    return stats


def _legacy_fundamental_row(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid json: {exc}") from exc

    symbol = payload.get("symbol")
    if not symbol:
        raise ValueError("missing symbol")

    profitability = _latest_dict(payload.get("profitability"))
    growth = _latest_dict(payload.get("growth"))
    solvency = _latest_dict(payload.get("solvency"))
    if not profitability and not growth and not solvency:
        return None

    period = profitability.get("period") or growth.get("period") or solvency.get("period")
    return {
        "symbol": symbol,
        "name": payload.get("name"),
        "ipo_date": payload.get("ipo_date"),
        "summary_text": payload.get("summary_text"),
        "source_file": path.name,
        "period": period,
        "pub_date": profitability.get("pub_date"),
        "roe": profitability.get("roe"),
        "net_margin": profitability.get("net_margin"),
        "gross_margin": profitability.get("gross_margin"),
        "net_profit": profitability.get("net_profit"),
        "eps_ttm": profitability.get("eps_ttm"),
        "yoy_equity": growth.get("yoy_equity"),
        "yoy_asset": growth.get("yoy_asset"),
        "yoy_net_income": growth.get("yoy_net_income"),
        "eps_growth_yoy": growth.get("yoy_eps"),
        "current_ratio": solvency.get("current_ratio"),
        "quick_ratio": solvency.get("quick_ratio"),
        "liability_to_asset": solvency.get("liability_to_asset"),
        "asset_to_equity": solvency.get("asset_to_equity"),
        "legacy_error": payload.get("error"),
    }


def _latest_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                return item
    if isinstance(value, dict):
        return value
    return {}
