from __future__ import annotations

import json
from pathlib import Path

from tests.test_company_assets import write_company


def _load_meta(company_dir: Path) -> dict[str, object]:
    return json.loads((company_dir / "meta.json").read_text(encoding="utf-8"))


def _write_meta(company_dir: Path, meta: dict[str, object]) -> None:
    (company_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _underwrite(meta: dict[str, object]) -> None:
    meta["underwriting"] = {
        "status": "passed",
        "review_id": "review-2026-07-21",
        "confidence": "high",
        "evidence_valid_until": "2026-10-21T15:00:00+08:00",
        "reason_codes": ["underwriting_passed"],
    }
    meta["valuation"] = {
        "currency": "CNY",
        "price_as_of": "2026-07-21T15:00:00+08:00",
        "bear_value": 60.0,
        "fair_value_range": [95.0, 105.0],
        "buy_zone": [70.0, 80.0],
        "reduce_zone": [120.0, 130.0],
    }


def _all_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        keys.update(value)
        for nested in value.values():
            keys.update(_all_keys(nested))
    elif isinstance(value, list):
        for nested in value:
            keys.update(_all_keys(nested))
    return keys


def test_build_v2_index_exposes_research_underwriting_and_valuation(tmp_path: Path):
    from trading_os.research_assets.index import build_index

    company_dir = write_company(tmp_path)
    meta = _load_meta(company_dir)
    _underwrite(meta)
    _write_meta(company_dir, meta)

    index = build_index(tmp_path / "research")

    assert index["schema_version"] == 2
    assert index["company_count"] == 1
    company = index["companies"][0]
    assert company["symbol"] == "CN:600519"
    assert company["coverage_status"] == "covered"
    assert company["underwriting"]["status"] == "passed"
    assert company["underwriting"]["evidence_valid_until"].startswith("2026-10-21")
    assert company["valuation"]["fair_value_range"] == [95.0, 105.0]
    assert company["conclusion_status"] == "valid"
    assert company["latest_report"] == (
        "companies/CN/600519/reports/2026-07-21-initial-research.md"
    )


def test_index_never_publishes_legacy_rating_or_portfolio_fields(tmp_path: Path):
    from trading_os.research_assets.index import build_index

    write_company(tmp_path)

    keys = _all_keys(build_index(tmp_path / "research"))

    assert "current_rating" not in keys
    assert "position_plan" not in keys
    assert "target_weight" not in keys
    assert "current_thesis" not in keys


def test_index_marks_missing_underwriting_and_rebaseline_as_invalid(tmp_path: Path):
    from trading_os.research_assets.index import build_index

    company_dir = write_company(tmp_path)
    first = build_index(tmp_path / "research")["companies"][0]
    assert first["conclusion_status"] == "not_underwritten"

    meta = _load_meta(company_dir)
    meta["research"]["rebaseline_required"] = True
    meta["research"]["coverage_status"] = "requires_rebaseline"
    _write_meta(company_dir, meta)

    second = build_index(tmp_path / "research")["companies"][0]
    assert second["conclusion_status"] == "requires_rebaseline"


def test_write_index_is_atomic_and_does_not_replace_valid_file_on_error(
    tmp_path: Path,
):
    from trading_os.research_assets.index import write_index

    company_dir = write_company(tmp_path)
    research_root = tmp_path / "research"
    index_path = research_root / "index.json"
    sentinel = b'{"schema_version":2,"sentinel":true}\n'
    index_path.write_bytes(sentinel)
    meta = _load_meta(company_dir)
    meta["reports"]["latest"] = "reports/missing.md"
    _write_meta(company_dir, meta)

    result = write_index(research_root)

    assert result.ok is False
    assert index_path.read_bytes() == sentinel
    assert "reports.latest" in result.errors[0]


def test_write_index_is_byte_stable(tmp_path: Path):
    from trading_os.research_assets.index import write_index

    write_company(tmp_path)
    research_root = tmp_path / "research"

    assert write_index(research_root).ok is True
    first = (research_root / "index.json").read_bytes()
    assert write_index(research_root).ok is True

    assert (research_root / "index.json").read_bytes() == first
