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
    assert (
        index["companies"][0]["latest_report"]
        == "companies/CN/600519/reports/2026-07-06-initial.md"
    )


def test_write_index_does_not_replace_existing_file_when_invalid(tmp_path: Path):
    from trading_os.research_assets.index import write_index

    company_dir = write_company(tmp_path)
    research_root = tmp_path / "research"
    index_path = research_root / "index.json"
    index_path.write_text(
        '{"schema_version": 1, "company_count": 0, "companies": []}\n',
        encoding="utf-8",
    )
    meta_path = company_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["latest_report"] = "reports/missing.md"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    result = write_index(research_root)

    assert result.ok is False
    assert json.loads(index_path.read_text(encoding="utf-8"))["company_count"] == 0
    assert "latest_report" in result.errors[0]
