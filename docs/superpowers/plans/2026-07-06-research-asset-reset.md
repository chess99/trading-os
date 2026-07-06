# Research Asset Reset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reset Trading OS into a Markdown-first research asset repository with immutable company research reports, mutable company metadata, generated indexes, and lightweight trigger automation.

**Architecture:** Replace the old recipe/DataHub/backtest-centered code with a small standard-library Python package under `trading_os.research_assets`. Company reports are immutable Markdown files; `meta.json` is the only mutable company state; generated index, schedule, and alert files are derived from metadata and never hand-authored.

**Tech Stack:** Python 3.10+, standard-library JSON/pathlib/argparse/datetime, pytest, ruff, Git-tracked Markdown and JSON assets.

---

## Scope

This plan performs the reset on branch `codex/research-asset-reset`. It intentionally deletes old workflow code, old skills, old scripts, old tests, and old artifacts from the working tree. Historical material remains available through git history.

The first implementation does not seed company research reports unless the user asks for that in a later iteration. It builds the asset model, validation, generated indexes, trigger builders, templates, playbooks, docs, and a minimal CLI.

## File Structure

Create or replace these files:

- Replace: `README.md`
  - Describe the new research-asset repository model and commands.
- Replace: `AGENTS.md`
  - Make the new asset model the agent source of truth.
- Replace: `pyproject.toml`
  - Remove old data-provider dependencies and keep a minimal package.
- Keep: `src/trading_os/__main__.py`
  - Retain the `.env` loader and call `trading_os.cli.main`.
- Replace: `src/trading_os/__init__.py`
  - Describe the reset package.
- Replace: `src/trading_os/cli.py`
  - Own the public CLI directly; remove the `cli_internal` dependency.
- Create: `src/trading_os/research_assets/__init__.py`
  - Export validation and index helpers.
- Create: `src/trading_os/research_assets/company.py`
  - Validate company asset directories and `meta.json`.
- Create: `src/trading_os/research_assets/index.py`
  - Build and write `research/index.json`.
- Create: `src/trading_os/research_assets/schedule.py`
  - Build and write `automation/review_schedule.json`.
- Create: `src/trading_os/research_assets/alerts.py`
  - Build price alert definitions and evaluate quote snapshots.
- Create: `templates/company-report.md`
  - Required report skeleton.
- Create: `templates/meta.schema.json`
  - Machine-readable metadata schema for agents and editors.
- Create: `playbooks/company-research.md`
  - Single-company research operating procedure.
- Create: `playbooks/followup-review.md`
  - Follow-up research operating procedure.
- Create: `playbooks/batch-dispatch.md`
  - Batch subagent operating procedure.
- Create: `playbooks/price-alert.md`
  - Price trigger operating procedure.
- Create: `research/companies/.gitkeep`
  - Keep the empty company asset root in git.
- Create: `research/index.json`
  - Generated empty index.
- Create: `automation/review_schedule.json`
  - Generated empty schedule.
- Create: `automation/price_alerts.json`
  - Generated empty price alert list.
- Create tests:
  - `tests/test_company_assets.py`
  - `tests/test_asset_index.py`
  - `tests/test_schedule_and_alerts.py`
  - `tests/test_cli.py`
  - `tests/test_templates_and_playbooks.py`

Delete these legacy paths:

- `artifacts/`
- `data/`
- `docs/research/`
- `docs/plans/`
- `scripts/`
- `skills/`
- `src/trading_os/backtest/`
- `src/trading_os/cli_internal/`
- `src/trading_os/data/`
- `src/trading_os/journal/`
- `src/trading_os/news/`
- `src/trading_os/paper/`
- `src/trading_os/research/`
- `src/trading_os/risk/`
- `src/trading_os/strategy/`
- Existing legacy tests under `tests/`

Keep these paths:

- `.gitignore`
- `.env.example`
- `CLAUDE.md` if it continues to point at `AGENTS.md`
- `cspell.json`
- `docs/superpowers/specs/`
- `docs/superpowers/plans/`
- `src/trading_os/__main__.py`

## Task 1: Reset Tests and Metadata Fixtures

**Files:**
- Delete: existing `tests/*.py`
- Create: `tests/test_company_assets.py`
- Create: `tests/test_asset_index.py`
- Create: `tests/test_schedule_and_alerts.py`
- Create: `tests/test_cli.py`
- Create: `tests/test_templates_and_playbooks.py`

- [ ] **Step 1: Delete legacy tests**

Run:

```powershell
git rm -r tests
New-Item -ItemType Directory -Path tests | Out-Null
```

Expected: legacy tests are removed from git, and an empty `tests/` directory exists.

- [ ] **Step 2: Write company asset validation tests**

Create `tests/test_company_assets.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest


def write_company(root: Path, *, rating: str = "watch") -> Path:
    company_dir = root / "research" / "companies" / "CN" / "600519"
    reports = company_dir / "reports"
    reports.mkdir(parents=True)
    report_path = reports / "2026-07-06-initial.md"
    report_path.write_text(
        "# Company Research: 贵州茅台 (CN:600519)\n\n"
        "Date: 2026-07-06\n"
        "Research Type: initial\n"
        "Analyst: agent\n\n"
        "## One-line Conclusion\n\n"
        "High-quality cash compounder with valuation discipline required.\n\n"
        "## Decision\n\n"
        "Watch.\n\n"
        "## Business Understanding\n\n"
        "Premium baijiu producer.\n\n"
        "## Industry and Competitive Context\n\n"
        "High-end baijiu remains concentrated.\n\n"
        "## Company Quality\n\n"
        "Wide moat.\n\n"
        "## Financial Quality\n\n"
        "High margins and strong cash flow.\n\n"
        "## Valuation\n\n"
        "Fair value range is 1150-1450 CNY.\n\n"
        "## Price and Position Plan\n\n"
        "Initial buy zone is 1000-1100 CNY.\n\n"
        "## Key Assumptions\n\n"
        "- Premium demand remains resilient.\n\n"
        "## Follow-up Triggers\n\n"
        "- Review after semiannual report.\n\n"
        "## Risks\n\n"
        "- Demand weakness.\n\n"
        "## Previous Thesis Review\n\n"
        "No previous report exists.\n\n"
        "## Sources\n\n"
        "- Company filings.\n",
        encoding="utf-8",
    )
    meta = {
        "symbol": "CN:600519",
        "market": "CN",
        "ticker": "600519",
        "name": "贵州茅台",
        "currency": "CNY",
        "status": "active",
        "current_rating": rating,
        "current_thesis": "High-quality cash compounder.",
        "fair_value_range": [1150, 1450],
        "buy_zone": [1000, 1100],
        "sell_or_reduce_zone": [1500, 1800],
        "position_plan": [
            {"condition": "price <= 1150", "max_weight": 0.05},
            {"condition": "price <= 1000", "max_weight": 0.12},
        ],
        "latest_report": "reports/2026-07-06-initial.md",
        "report_history": ["reports/2026-07-06-initial.md"],
        "review_triggers": [
            {"type": "date", "date": "2026-08-31", "reason": "Semiannual review."}
        ],
        "price_triggers": [
            {"type": "price_below", "price": 1100, "reason": "Enter buy zone."}
        ],
        "updated_at": "2026-07-06T00:00:00+08:00",
    }
    (company_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return company_dir


def test_valid_company_asset_loads(tmp_path: Path):
    from trading_os.research_assets.company import validate_company_dir

    company_dir = write_company(tmp_path)

    meta = validate_company_dir(company_dir)

    assert meta["symbol"] == "CN:600519"
    assert meta["latest_report"] == "reports/2026-07-06-initial.md"


def test_invalid_rating_is_rejected(tmp_path: Path):
    from trading_os.research_assets.company import AssetValidationError, validate_company_dir

    company_dir = write_company(tmp_path, rating="strong_buy")

    with pytest.raises(AssetValidationError, match="current_rating"):
        validate_company_dir(company_dir)


def test_missing_latest_report_is_rejected(tmp_path: Path):
    from trading_os.research_assets.company import AssetValidationError, validate_company_dir

    company_dir = write_company(tmp_path)
    (company_dir / "reports" / "2026-07-06-initial.md").unlink()

    with pytest.raises(AssetValidationError, match="latest_report"):
        validate_company_dir(company_dir)
```

- [ ] **Step 3: Write index tests**

Create `tests/test_asset_index.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from tests.test_company_assets import write_company


def test_build_index_from_company_metadata(tmp_path: Path):
    from trading_os.research_assets.index import build_index

    write_company(tmp_path)

    index = build_index(tmp_path / "research")

    assert index["schema_version"] == 1
    assert index["company_count"] == 1
    assert index["companies"][0]["symbol"] == "CN:600519"
    assert index["companies"][0]["latest_report"] == "companies/CN/600519/reports/2026-07-06-initial.md"


def test_write_index_does_not_replace_existing_file_when_invalid(tmp_path: Path):
    from trading_os.research_assets.index import write_index

    company_dir = write_company(tmp_path)
    research_root = tmp_path / "research"
    index_path = research_root / "index.json"
    index_path.write_text('{"schema_version": 1, "company_count": 0, "companies": []}\n', encoding="utf-8")
    meta_path = company_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["latest_report"] = "reports/missing.md"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    result = write_index(research_root)

    assert result.ok is False
    assert json.loads(index_path.read_text(encoding="utf-8"))["company_count"] == 0
    assert "latest_report" in result.errors[0]
```

- [ ] **Step 4: Write schedule and alert tests**

Create `tests/test_schedule_and_alerts.py`:

```python
from __future__ import annotations

from pathlib import Path

from tests.test_company_assets import write_company


def test_build_review_schedule_from_date_triggers(tmp_path: Path):
    from trading_os.research_assets.schedule import build_review_schedule

    write_company(tmp_path)

    schedule = build_review_schedule(tmp_path / "research")

    assert schedule["schema_version"] == 1
    assert schedule["items"][0]["symbol"] == "CN:600519"
    assert schedule["items"][0]["date"] == "2026-08-31"


def test_build_price_alerts_from_price_triggers(tmp_path: Path):
    from trading_os.research_assets.alerts import build_price_alerts

    write_company(tmp_path)

    alerts = build_price_alerts(tmp_path / "research")

    assert alerts["schema_version"] == 1
    assert alerts["items"][0]["symbol"] == "CN:600519"
    assert alerts["items"][0]["price"] == 1100


def test_evaluate_price_alerts_detects_triggered_snapshot():
    from trading_os.research_assets.alerts import evaluate_price_alerts

    alerts = {
        "schema_version": 1,
        "items": [
            {
                "symbol": "CN:600519",
                "name": "贵州茅台",
                "type": "price_below",
                "price": 1100,
                "reason": "Enter buy zone.",
                "latest_report": "companies/CN/600519/reports/2026-07-06-initial.md",
            }
        ],
    }
    quotes = [{"symbol": "CN:600519", "price": 1099.5, "as_of": "2026-07-06T10:30:00+08:00"}]

    triggered = evaluate_price_alerts(alerts, quotes)

    assert triggered["triggered_count"] == 1
    assert triggered["triggered"][0]["symbol"] == "CN:600519"
    assert triggered["triggered"][0]["observed_price"] == 1099.5
```

- [ ] **Step 5: Write CLI tests**

Create `tests/test_cli.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from tests.test_company_assets import write_company


def test_cli_company_validate_success(tmp_path: Path, capsys):
    from trading_os.cli import main

    company_dir = write_company(tmp_path)

    code = main(["company", "validate", str(company_dir)])

    assert code == 0
    assert "CN:600519" in capsys.readouterr().out


def test_cli_index_rebuild_writes_index(tmp_path: Path):
    from trading_os.cli import main

    write_company(tmp_path)

    code = main(["index", "rebuild", "--research-root", str(tmp_path / "research")])

    assert code == 0
    payload = json.loads((tmp_path / "research" / "index.json").read_text(encoding="utf-8"))
    assert payload["company_count"] == 1


def test_cli_alerts_check_uses_quote_snapshot(tmp_path: Path, capsys):
    from trading_os.cli import main

    alerts_path = tmp_path / "alerts.json"
    quotes_path = tmp_path / "quotes.json"
    alerts_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "items": [
                    {
                        "symbol": "CN:600519",
                        "name": "贵州茅台",
                        "type": "price_below",
                        "price": 1100,
                        "reason": "Enter buy zone.",
                        "latest_report": "companies/CN/600519/reports/2026-07-06-initial.md",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    quotes_path.write_text(
        json.dumps([{"symbol": "CN:600519", "price": 1090}], ensure_ascii=False),
        encoding="utf-8",
    )

    code = main(["alerts", "check", "--alerts", str(alerts_path), "--quotes", str(quotes_path)])

    assert code == 0
    assert "triggered_count" in capsys.readouterr().out
```

- [ ] **Step 6: Write template and playbook tests**

Create `tests/test_templates_and_playbooks.py`:

```python
from __future__ import annotations

from pathlib import Path


def test_company_report_template_contains_required_sections():
    root = Path(__file__).resolve().parents[1]
    text = (root / "templates" / "company-report.md").read_text(encoding="utf-8")

    for heading in [
        "## One-line Conclusion",
        "## Decision",
        "## Business Understanding",
        "## Industry and Competitive Context",
        "## Company Quality",
        "## Financial Quality",
        "## Valuation",
        "## Price and Position Plan",
        "## Key Assumptions",
        "## Follow-up Triggers",
        "## Risks",
        "## Previous Thesis Review",
        "## Sources",
    ]:
        assert heading in text


def test_playbooks_state_immutable_report_rule():
    root = Path(__file__).resolve().parents[1]
    company = (root / "playbooks" / "company-research.md").read_text(encoding="utf-8")
    followup = (root / "playbooks" / "followup-review.md").read_text(encoding="utf-8")

    assert "Do not overwrite existing reports" in company
    assert "Read the previous latest_report" in followup
    assert "Previous Thesis Review" in followup
```

- [ ] **Step 7: Run tests to verify they fail against old code**

Run:

```powershell
pytest -q
```

Expected: tests fail with missing `trading_os.research_assets`, missing templates, or missing playbooks.

- [ ] **Step 8: Commit test reset**

Run:

```powershell
git add tests
git commit -m "test: define research asset reset behavior"
```

Expected: one commit containing only the new test suite and legacy test deletions.

## Task 2: Add Company Asset Validation

**Files:**
- Create: `src/trading_os/research_assets/__init__.py`
- Create: `src/trading_os/research_assets/company.py`
- Replace: `src/trading_os/__init__.py`
- Test: `tests/test_company_assets.py`

- [ ] **Step 1: Create package export**

Create `src/trading_os/research_assets/__init__.py`:

```python
from __future__ import annotations

from .company import AssetValidationError, validate_company_dir
from .index import build_index, write_index

__all__ = [
    "AssetValidationError",
    "build_index",
    "validate_company_dir",
    "write_index",
]
```

- [ ] **Step 2: Implement company validation**

Create `src/trading_os/research_assets/company.py`:

```python
from __future__ import annotations

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
    if not isinstance(low, (int, float)) or not isinstance(high, (int, float)):
        raise AssetValidationError(f"{key} values must be numbers")
    if low > high:
        raise AssetValidationError(f"{key} lower bound must be <= upper bound")


def _require_report(company_dir: Path, rel_path: str, field: str) -> None:
    if rel_path.startswith("/") or ".." in Path(rel_path).parts:
        raise AssetValidationError(f"{field} must be a relative path inside company dir")
    target = company_dir / rel_path
    if not target.exists():
        raise AssetValidationError(f"{field} points to missing report: {rel_path}")
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
        if not isinstance(max_weight, (int, float)) or max_weight < 0 or max_weight > 1:
            raise AssetValidationError("position_plan max_weight must be between 0 and 1")


def _require_review_triggers(value: Any) -> None:
    if not isinstance(value, list):
        raise AssetValidationError("review_triggers must be a list")
    for item in value:
        if not isinstance(item, dict):
            raise AssetValidationError("review_triggers entries must be objects")
        if item.get("type") not in ALLOWED_REVIEW_TRIGGER_TYPES:
            raise AssetValidationError("review_triggers type must be date")
        if not isinstance(item.get("date"), str) or not re.match(r"^\d{4}-\d{2}-\d{2}$", item["date"]):
            raise AssetValidationError("review_triggers date must use YYYY-MM-DD")
        if not isinstance(item.get("reason"), str) or not item["reason"].strip():
            raise AssetValidationError("review_triggers reason must be a non-empty string")


def _require_price_triggers(value: Any) -> None:
    if not isinstance(value, list):
        raise AssetValidationError("price_triggers must be a list")
    for item in value:
        if not isinstance(item, dict):
            raise AssetValidationError("price_triggers entries must be objects")
        if item.get("type") not in ALLOWED_PRICE_TRIGGER_TYPES:
            raise AssetValidationError("price_triggers type must be price_below or price_above")
        if not isinstance(item.get("price"), (int, float)):
            raise AssetValidationError("price_triggers price must be numeric")
        if not isinstance(item.get("reason"), str) or not item["reason"].strip():
            raise AssetValidationError("price_triggers reason must be a non-empty string")
```

- [ ] **Step 3: Replace package metadata**

Replace `src/trading_os/__init__.py` with:

```python
"""Trading OS research asset repository tools."""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
```

- [ ] **Step 4: Run company asset tests**

Run:

```powershell
pytest tests/test_company_assets.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit validation package**

Run:

```powershell
git add src/trading_os/__init__.py src/trading_os/research_assets tests/test_company_assets.py
git commit -m "feat: validate company research assets"
```

Expected: one commit containing the validation implementation.

## Task 3: Build Generated Index

**Files:**
- Create: `src/trading_os/research_assets/index.py`
- Test: `tests/test_asset_index.py`

- [ ] **Step 1: Implement index builder**

Create `src/trading_os/research_assets/index.py`:

```python
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
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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
        if isinstance(item, dict) and item.get("type") == "date" and isinstance(item.get("date"), str)
    ]
    return min(dates) if dates else None


def _posix(path: Path) -> str:
    return path.as_posix()
```

- [ ] **Step 2: Run index tests**

Run:

```powershell
pytest tests/test_asset_index.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Commit index builder**

Run:

```powershell
git add src/trading_os/research_assets/index.py src/trading_os/research_assets/__init__.py tests/test_asset_index.py
git commit -m "feat: build research asset index"
```

Expected: one commit containing index generation.

## Task 4: Build Review Schedule and Price Alerts

**Files:**
- Create: `src/trading_os/research_assets/schedule.py`
- Create: `src/trading_os/research_assets/alerts.py`
- Test: `tests/test_schedule_and_alerts.py`

- [ ] **Step 1: Implement review schedule builder**

Create `src/trading_os/research_assets/schedule.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .company import validate_company_dir
from .index import _company_dirs


def build_review_schedule(research_root: str | Path) -> dict[str, Any]:
    root = Path(research_root)
    items: list[dict[str, Any]] = []
    companies_root = root / "companies"
    if companies_root.exists():
        for company_dir in _company_dirs(companies_root):
            meta = validate_company_dir(company_dir)
            rel_company = company_dir.relative_to(root)
            for trigger in meta.get("review_triggers", []):
                if trigger.get("type") != "date":
                    continue
                items.append(
                    {
                        "date": trigger["date"],
                        "symbol": meta["symbol"],
                        "name": meta["name"],
                        "reason": trigger["reason"],
                        "latest_report": (rel_company / meta["latest_report"]).as_posix(),
                    }
                )
    items.sort(key=lambda item: (item["date"], item["symbol"]))
    return {"schema_version": 1, "item_count": len(items), "items": items}


def write_review_schedule(research_root: str | Path, output_path: str | Path) -> Path:
    payload = build_review_schedule(research_root)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target
```

- [ ] **Step 2: Implement price alert builder and evaluator**

Create `src/trading_os/research_assets/alerts.py`:

```python
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
                        "latest_report": (rel_company / meta["latest_report"]).as_posix(),
                    }
                )
    items.sort(key=lambda item: (item["symbol"], item["type"], float(item["price"])))
    return {"schema_version": 1, "item_count": len(items), "items": items}


def write_price_alerts(research_root: str | Path, output_path: str | Path) -> Path:
    payload = build_price_alerts(research_root)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def evaluate_price_alerts(alerts: dict[str, Any], quotes: list[dict[str, Any]]) -> dict[str, Any]:
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


def _triggered(alert: dict[str, Any], quote: dict[str, Any], observed: float) -> dict[str, Any]:
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
```

- [ ] **Step 3: Run schedule and alert tests**

Run:

```powershell
pytest tests/test_schedule_and_alerts.py -q
```

Expected: all tests pass.

- [ ] **Step 4: Commit automation builders**

Run:

```powershell
git add src/trading_os/research_assets/schedule.py src/trading_os/research_assets/alerts.py tests/test_schedule_and_alerts.py
git commit -m "feat: build research schedules and price alerts"
```

Expected: one commit containing schedule and alert generation.

## Task 5: Replace CLI

**Files:**
- Replace: `src/trading_os/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Replace public CLI**

Replace `src/trading_os/cli.py` with:

```python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .research_assets.alerts import evaluate_price_alerts, load_json, write_price_alerts
from .research_assets.company import AssetValidationError, validate_company_dir
from .research_assets.index import write_index
from .research_assets.schedule import write_review_schedule


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trading_os",
        description="Trading OS research asset tools",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    company = sub.add_parser("company", help="Validate company research assets")
    company_sub = company.add_subparsers(dest="company_cmd", required=True)
    validate = company_sub.add_parser("validate", help="Validate one company directory")
    validate.add_argument("path")
    validate.set_defaults(func=cmd_company_validate)

    index = sub.add_parser("index", help="Build generated research indexes")
    index_sub = index.add_subparsers(dest="index_cmd", required=True)
    rebuild = index_sub.add_parser("rebuild", help="Rebuild research/index.json")
    rebuild.add_argument("--research-root", default="research")
    rebuild.set_defaults(func=cmd_index_rebuild)

    alerts = sub.add_parser("alerts", help="Build and check price alerts")
    alerts_sub = alerts.add_subparsers(dest="alerts_cmd", required=True)
    alerts_build = alerts_sub.add_parser("build", help="Build automation/price_alerts.json")
    alerts_build.add_argument("--research-root", default="research")
    alerts_build.add_argument("--output", default="automation/price_alerts.json")
    alerts_build.set_defaults(func=cmd_alerts_build)
    alerts_check = alerts_sub.add_parser("check", help="Check price alerts with a quote JSON file")
    alerts_check.add_argument("--alerts", default="automation/price_alerts.json")
    alerts_check.add_argument("--quotes", required=True)
    alerts_check.set_defaults(func=cmd_alerts_check)

    schedule = sub.add_parser("schedule", help="Build review schedules")
    schedule_sub = schedule.add_subparsers(dest="schedule_cmd", required=True)
    schedule_build = schedule_sub.add_parser("build", help="Build automation/review_schedule.json")
    schedule_build.add_argument("--research-root", default="research")
    schedule_build.add_argument("--output", default="automation/review_schedule.json")
    schedule_build.set_defaults(func=cmd_schedule_build)
    return parser


def cmd_company_validate(ns: argparse.Namespace) -> int:
    meta = validate_company_dir(ns.path)
    print(json.dumps({"ok": True, "symbol": meta["symbol"]}, ensure_ascii=False, indent=2))
    return 0


def cmd_index_rebuild(ns: argparse.Namespace) -> int:
    result = write_index(ns.research_root)
    if not result.ok:
        print(json.dumps({"ok": False, "errors": result.errors}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({"ok": True, "path": str(result.path)}, ensure_ascii=False, indent=2))
    return 0


def cmd_alerts_build(ns: argparse.Namespace) -> int:
    path = write_price_alerts(ns.research_root, ns.output)
    print(json.dumps({"ok": True, "path": str(path)}, ensure_ascii=False, indent=2))
    return 0


def cmd_alerts_check(ns: argparse.Namespace) -> int:
    alerts = load_json(ns.alerts)
    quotes = load_json(ns.quotes)
    if not isinstance(quotes, list):
        raise RuntimeError("quote snapshot must be a JSON list")
    result = evaluate_price_alerts(alerts, quotes)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_schedule_build(ns: argparse.Namespace) -> int:
    path = write_review_schedule(ns.research_root, ns.output)
    print(json.dumps({"ok": True, "path": str(path)}, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv)
    func = getattr(ns, "func", None)
    if not callable(func):
        return 2
    try:
        return int(func(ns))
    except (AssetValidationError, RuntimeError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run CLI tests**

Run:

```powershell
pytest tests/test_cli.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Verify module CLI manually**

Run:

```powershell
python -m trading_os --help
```

Expected: help includes `company`, `index`, `alerts`, and `schedule`.

- [ ] **Step 4: Commit CLI replacement**

Run:

```powershell
git add src/trading_os/cli.py tests/test_cli.py
git commit -m "feat: add research asset CLI"
```

Expected: one commit containing the new CLI.

## Task 6: Add Templates and Playbooks

**Files:**
- Create: `templates/company-report.md`
- Create: `templates/meta.schema.json`
- Create: `playbooks/company-research.md`
- Create: `playbooks/followup-review.md`
- Create: `playbooks/batch-dispatch.md`
- Create: `playbooks/price-alert.md`
- Test: `tests/test_templates_and_playbooks.py`

- [ ] **Step 1: Create company report template**

Create `templates/company-report.md`:

```markdown
# Company Research: {Name} ({Symbol})

Date: YYYY-MM-DD
Research Type: initial | followup | earnings_review | price_trigger_review
Analyst: agent

## One-line Conclusion

State the current investment judgment in one sentence.

## Decision

State the current action class: buy, watch, hold, avoid, sell, or research_only.

## Business Understanding

Explain what the company sells, who pays, why customers choose it, and how durable the business model is.

## Industry and Competitive Context

Explain the industry structure, growth drivers, cycle position, competitors, substitutes, and bargaining power.

## Company Quality

Assess moat, management, capital allocation, product quality, customer stickiness, and governance.

## Financial Quality

Assess revenue growth, margins, cash conversion, capital intensity, leverage, dilution, and accounting quality.

## Valuation

Give a fair value range, valuation method, key assumptions, and sensitivity to the most important variables.

## Price and Position Plan

Give buy zone, reduce zone, maximum position size, add rules, and conditions that must be checked before acting.

## Key Assumptions

List the explicit assumptions the thesis depends on.

## Follow-up Triggers

List dates, filings, earnings releases, product milestones, price levels, or industry events that require review.

## Risks

List the risks that can impair intrinsic value or invalidate the thesis.

## Previous Thesis Review

For an initial report, state that no previous report exists. For later reports, review the prior `latest_report` and classify each prior assumption as confirmed, weakened, or disproven.

## Sources

List primary filings, company materials, exchange disclosures, credible industry reports, and market data sources used.
```

- [ ] **Step 2: Create metadata schema**

Create `templates/meta.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Trading OS Company Research Metadata",
  "type": "object",
  "required": [
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
    "updated_at"
  ],
  "properties": {
    "symbol": {"type": "string", "pattern": "^(CN|HK|US):[A-Z0-9.]+$"},
    "market": {"type": "string", "enum": ["CN", "HK", "US"]},
    "ticker": {"type": "string"},
    "name": {"type": "string"},
    "currency": {"type": "string"},
    "status": {"type": "string", "enum": ["active", "inactive", "archived"]},
    "current_rating": {
      "type": "string",
      "enum": ["buy", "watch", "hold", "avoid", "sell", "research_only"]
    },
    "current_thesis": {"type": "string"},
    "fair_value_range": {
      "type": "array",
      "minItems": 2,
      "maxItems": 2,
      "items": {"type": "number"}
    },
    "buy_zone": {
      "type": "array",
      "minItems": 2,
      "maxItems": 2,
      "items": {"type": "number"}
    },
    "sell_or_reduce_zone": {
      "type": "array",
      "minItems": 2,
      "maxItems": 2,
      "items": {"type": "number"}
    },
    "position_plan": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["condition", "max_weight"],
        "properties": {
          "condition": {"type": "string"},
          "max_weight": {"type": "number", "minimum": 0, "maximum": 1}
        }
      }
    },
    "latest_report": {"type": "string"},
    "report_history": {"type": "array", "items": {"type": "string"}},
    "review_triggers": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["type", "date", "reason"],
        "properties": {
          "type": {"type": "string", "enum": ["date"]},
          "date": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
          "reason": {"type": "string"}
        }
      }
    },
    "price_triggers": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["type", "price", "reason"],
        "properties": {
          "type": {"type": "string", "enum": ["price_below", "price_above"]},
          "price": {"type": "number"},
          "reason": {"type": "string"}
        }
      }
    },
    "updated_at": {"type": "string"}
  },
  "additionalProperties": true
}
```

- [ ] **Step 3: Create company research playbook**

Create `playbooks/company-research.md`:

```markdown
# Company Research Playbook

Use this playbook when researching one company from scratch.

## Boundary

Research exactly one company. Do not edit another company directory. Do not overwrite existing reports.

## Inputs

- Company identifier in `MARKET:TICKER` format.
- Company directory under `research/companies/{MARKET}/{TICKER}/`.
- Optional user question or focus area.

## Process

1. Confirm whether the security is a listed common stock, private company exposure, fund, receipt, or synthetic exposure.
2. Gather primary sources first: exchange filings, annual reports, interim reports, company investor materials, official announcements, and prospectuses.
3. Gather credible secondary sources: industry reports, regulator data, reputable financial media, and analyst summaries.
4. Understand the business before valuation: products, customers, pricing, margins, sales channels, suppliers, and capital intensity.
5. Evaluate industry structure: market size, growth, concentration, substitution, regulation, and cycle position.
6. Evaluate company quality: moat, management, governance, capital allocation, competitive advantage, and failure modes.
7. Evaluate financial quality: growth, margin durability, cash conversion, leverage, dilution, and accounting quality.
8. Build a valuation range with explicit assumptions.
9. Define buy zone, reduce zone, maximum position size, and price-to-position rules.
10. Define follow-up triggers: earnings dates, filing dates, product milestones, regulatory events, price levels, and thesis validation points.
11. Write a new report under `reports/YYYY-MM-DD-slug.md`.
12. Update `meta.json` so `latest_report` points to the new report and `report_history` includes it.

## Output Rules

- Reports are immutable research snapshots.
- Do not overwrite existing reports.
- Do not edit a historical report to change the judgment.
- If a prior report was wrong, write a new report explaining the error.
- Keep `meta.json` concise and machine-readable.
- Keep the full reasoning in Markdown.
```

- [ ] **Step 4: Create follow-up review playbook**

Create `playbooks/followup-review.md`:

```markdown
# Follow-up Review Playbook

Use this playbook when a company has already been researched and a trigger asks for a new review.

## Boundary

Review exactly one company. Read the previous latest_report before doing new research.

## Process

1. Read `meta.json`.
2. Read the previous `latest_report`.
3. Extract the prior key assumptions, valuation range, buy zone, position plan, and follow-up triggers.
4. Gather new filings, announcements, earnings, industry data, price movement, and relevant news since the prior report.
5. Classify each prior key assumption as confirmed, weakened, disproven, or still untested.
6. Decide whether the rating, valuation range, buy zone, position plan, or triggers should change.
7. Write a new timestamped report under `reports/`.
8. Include a `Previous Thesis Review` section.
9. Update `meta.json` with the latest state and new report pointer.
10. Rebuild the repository index and automation files.

## Output Rules

- Never replace the previous report.
- The new report must explicitly name the previous latest_report.
- The new report must explain what changed.
- If nothing material changed, write that conclusion plainly and keep the metadata stable.
```

- [ ] **Step 5: Create batch dispatch playbook**

Create `playbooks/batch-dispatch.md`:

```markdown
# Batch Dispatch Playbook

Use this playbook when a main agent assigns many companies to subagents.

## Operating Model

- One subagent researches exactly one company.
- A subagent writes only inside that company's directory.
- The main agent owns assignment, review, index rebuild, and commits.
- Failed runs should leave no partial report unless the failure analysis is itself useful.

## Main Agent Steps

1. Prepare a company list with market, ticker, name, and research reason.
2. Dispatch one company per subagent.
3. Require each subagent to follow `playbooks/company-research.md` or `playbooks/followup-review.md`.
4. Review every generated report for sourcing, valuation, position plan, and trigger quality.
5. Reject reports that read like data dumps or lack a decision.
6. Run `python -m trading_os company validate <company-dir>` for each company.
7. Run `python -m trading_os index rebuild`.
8. Run `python -m trading_os schedule build`.
9. Run `python -m trading_os alerts build`.
10. Commit only reviewed company assets and generated indexes.
```

- [ ] **Step 6: Create price alert playbook**

Create `playbooks/price-alert.md`:

```markdown
# Price Alert Playbook

Use this playbook when price reaches a level defined in company metadata.

## Rule

Price alerts are review triggers, not trade instructions.

## Process

1. Read the triggered alert.
2. Read the company's `meta.json`.
3. Read the previous `latest_report`.
4. Verify the current price from a reliable market source.
5. Check whether the business thesis changed since the prior report.
6. Write a new price-trigger review report when the trigger is material.
7. Update `meta.json` only after the new research judgment is complete.

## Output

The output is a new research report and updated metadata. It is not an automatic order.
```

- [ ] **Step 7: Run template and playbook tests**

Run:

```powershell
pytest tests/test_templates_and_playbooks.py -q
```

Expected: all tests pass.

- [ ] **Step 8: Commit templates and playbooks**

Run:

```powershell
git add templates playbooks tests/test_templates_and_playbooks.py
git commit -m "docs: add research asset playbooks"
```

Expected: one commit containing templates and playbooks.

## Task 7: Reset Repository Assets and Generated Files

**Files:**
- Create: `research/companies/.gitkeep`
- Create: `research/index.json`
- Create: `automation/review_schedule.json`
- Create: `automation/price_alerts.json`
- Replace: `.gitignore`

- [ ] **Step 1: Remove legacy data and artifact directories**

Run:

```powershell
git rm -r artifacts data scripts skills docs/research docs/plans
```

Expected: legacy artifacts, scripts, skills, and non-superpowers research docs are staged for deletion.

- [ ] **Step 2: Remove legacy source packages**

Run:

```powershell
git rm -r src/trading_os/backtest src/trading_os/cli_internal src/trading_os/data src/trading_os/journal src/trading_os/news src/trading_os/paper src/trading_os/research src/trading_os/risk src/trading_os/strategy
```

Expected: old deterministic workflow packages are staged for deletion.

- [ ] **Step 3: Create new asset roots**

Run:

```powershell
New-Item -ItemType Directory -Force -Path research/companies | Out-Null
New-Item -ItemType Directory -Force -Path automation | Out-Null
Set-Content -Path research/companies/.gitkeep -Value "" -Encoding UTF8
Set-Content -Path research/index.json -Value "{`n  `"schema_version`": 1,`n  `"company_count`": 0,`n  `"companies`": []`n}" -Encoding UTF8
Set-Content -Path automation/review_schedule.json -Value "{`n  `"schema_version`": 1,`n  `"item_count`": 0,`n  `"items`": []`n}" -Encoding UTF8
Set-Content -Path automation/price_alerts.json -Value "{`n  `"schema_version`": 1,`n  `"item_count`": 0,`n  `"items`": []`n}" -Encoding UTF8
```

Expected: empty generated baseline files exist.

- [ ] **Step 4: Replace `.gitignore`**

Replace `.gitignore` with:

```gitignore
# Python
.venv/
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
.mypy_cache/
*.egg-info/

# OS / IDE
.DS_Store
.idea/
.vscode/

# Notebooks
.ipynb_checkpoints/

# Secrets
.env

# Temporary local files
/temp/

# Local quote snapshots and ad-hoc inputs
/quotes/

# Claude Code local settings
.claude/settings.local.json
.claude/*.local.*
vendor/
```

- [ ] **Step 5: Run tests after deletion**

Run:

```powershell
pytest -q
```

Expected: all current tests pass.

- [ ] **Step 6: Commit reset assets and deletions**

Run:

```powershell
git add .gitignore research automation
git status --short
git commit -m "chore: reset repository to research assets"
```

Expected: one commit containing old path deletions plus new empty asset roots.

## Task 8: Replace Project Docs and Packaging

**Files:**
- Replace: `README.md`
- Replace: `AGENTS.md`
- Replace: `pyproject.toml`
- Test: `tests/test_templates_and_playbooks.py`

- [ ] **Step 1: Replace README**

Replace `README.md` with:

```markdown
# Trading OS

Trading OS is a research asset repository.

The primary asset is the company research timeline under `research/companies/`.
Each research run creates a new immutable Markdown report. Each company also has one
mutable `meta.json` file for current rating, valuation range, buy zone, position plan,
follow-up triggers, and price alerts.

## Structure

```text
research/
  companies/
    CN/600519/
      meta.json
      reports/
  index.json

playbooks/
templates/
automation/
src/trading_os/research_assets/
```

## Rules

- Do not overwrite historical reports.
- Update `meta.json` after each accepted research report.
- Rebuild `research/index.json` from metadata.
- Use price alerts as review triggers, not automatic trades.
- Old recipe workflows, provider pipelines, backtests, and artifacts are not part of this reset.

## Commands

```bash
python -m trading_os company validate research/companies/CN/600519
python -m trading_os index rebuild
python -m trading_os schedule build
python -m trading_os alerts build
python -m trading_os alerts check --quotes quotes/latest.json
```

## Research Workflow

For a new company, follow `playbooks/company-research.md`.

For a follow-up review, follow `playbooks/followup-review.md`.

For batch research, follow `playbooks/batch-dispatch.md`.
```

- [ ] **Step 2: Replace AGENTS**

Replace `AGENTS.md` with:

```markdown
# Trading OS Agent Guide

This repository is a research asset repository. The source of truth is the company
research timeline under `research/companies/`.

## Core Model

- Every research run creates a new immutable Markdown report.
- Existing reports must not be overwritten to change a past judgment.
- `meta.json` is the only mutable company state file.
- `research/index.json`, `automation/review_schedule.json`, and `automation/price_alerts.json`
  are generated files.

## Company Directory

```text
research/companies/{MARKET}/{TICKER}/
  meta.json
  reports/
    YYYY-MM-DD-slug.md
  sources/
```

## Agent Rules

- Research one company per agent unless the user explicitly asks for synthesis.
- Read the previous `latest_report` before writing a follow-up.
- Write a new report for every new research run.
- Update `meta.json` only after the report is complete.
- Run validation and rebuild generated files before committing.
- Do not revive old recipe, DataHub, CANSLIM, Elder, Value, backtest, or paper-trading workflows.

## Commands

```bash
python -m trading_os company validate research/companies/CN/600519
python -m trading_os index rebuild
python -m trading_os schedule build
python -m trading_os alerts build
python -m trading_os alerts check --quotes quotes/latest.json
```
```

- [ ] **Step 3: Replace pyproject**

Replace `pyproject.toml` with:

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "trading-os"
version = "0.1.0"
description = "Markdown-first research asset repository tools."
readme = "README.md"
license = { text = "MIT" }
authors = [{ name = "zcs" }]
requires-python = ">=3.10,<3.15"
dependencies = []

[project.optional-dependencies]
dev = [
  "pytest>=8",
  "ruff>=0.4",
]

[tool.setuptools]
package-dir = {"" = "src"}

[tool.setuptools.packages.find]
where = ["src"]

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "I", "B"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 4: Run docs-sensitive tests**

Run:

```powershell
pytest tests/test_templates_and_playbooks.py -q
```

Expected: tests pass.

- [ ] **Step 5: Commit docs and packaging**

Run:

```powershell
git add README.md AGENTS.md pyproject.toml
git commit -m "docs: describe research asset repository"
```

Expected: one commit containing top-level docs and package metadata.

## Task 9: Verification Sweep

**Files:**
- No source edits expected unless verification exposes a concrete failure.

- [ ] **Step 1: Run full test suite**

Run:

```powershell
pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Run ruff**

Run:

```powershell
ruff check src tests
```

Expected: no lint violations.

- [ ] **Step 3: Run CLI smoke tests**

Run:

```powershell
python -m trading_os --help
python -m trading_os index rebuild
python -m trading_os schedule build
python -m trading_os alerts build
```

Expected:

- `--help` lists `company`, `index`, `alerts`, and `schedule`.
- `index rebuild` writes `research/index.json`.
- `schedule build` writes `automation/review_schedule.json`.
- `alerts build` writes `automation/price_alerts.json`.

- [ ] **Step 4: Confirm generated baseline files**

Run:

```powershell
Get-Content research/index.json
Get-Content automation/review_schedule.json
Get-Content automation/price_alerts.json
```

Expected:

- `research/index.json` has `"company_count": 0`.
- `automation/review_schedule.json` has `"item_count": 0`.
- `automation/price_alerts.json` has `"item_count": 0`.

- [ ] **Step 5: Inspect git status and staged changes**

Run:

```powershell
git status --short
git diff --stat
```

Expected: no unstaged changes unless verification produced intentional generated-file rewrites.

- [ ] **Step 6: Commit verification fixes if needed**

If verification required fixes, run:

```powershell
git add src/trading_os tests README.md AGENTS.md pyproject.toml templates playbooks research automation .gitignore
git diff --staged --stat
git commit -m "test: verify research asset reset"
```

Expected: a narrow commit containing only verification fixes.

If verification produced no changes, do not create an empty commit.

## Execution Notes

- Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` before executing this plan.
- Keep one commit per task.
- Do not seed company research assets unless the user explicitly requests it.
- Do not migrate old artifacts into the new `research/` tree.
- Do not reintroduce old DataHub, recipe, skill, backtest, or paper trading modules.
- Treat generated index, schedule, and alert files as derived artifacts committed for repository readability.

## Self-Review

Spec coverage:

- Markdown plus metadata architecture: Tasks 2, 3, 6, 7.
- Immutable timestamped reports: Tasks 1, 6, 8.
- Mutable `meta.json`: Tasks 1 and 2.
- Generated `research/index.json`: Task 3 and Task 7.
- Review triggers: Task 4.
- Price triggers: Task 4.
- Lightweight CLI: Task 5.
- Old workflow deletion: Task 7.
- Docs and agent rules: Task 8.
- Verification: Task 9.

Placeholder scan:

- The plan uses concrete file paths, exact code, exact commands, and expected results.
- The plan does not leave unspecified implementation areas.

Type consistency:

- `validate_company_dir` returns `dict[str, Any]`.
- `build_index`, `build_review_schedule`, and `build_price_alerts` all accept `str | Path`.
- CLI commands call the same function names defined in the implementation tasks.
