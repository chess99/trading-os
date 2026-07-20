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


def test_repository_company_assets_validate():
    from trading_os.research_assets.company import validate_company_dir

    root = Path(__file__).resolve().parents[1]
    company_dirs = sorted(
        path
        for path in (root / "research" / "companies").glob("*/*")
        if (path / "meta.json").exists()
    )

    assert company_dirs
    symbols = [validate_company_dir(path)["symbol"] for path in company_dirs]
    assert symbols == sorted(symbols)
    assert {"CN:600519", "HK:9660", "US:SPCX"} <= set(symbols)


def test_seeded_repository_reports_are_chinese():
    root = Path(__file__).resolve().parents[1]
    report_paths = sorted((root / "research" / "companies").glob("*/*/reports/*.md"))

    assert report_paths
    for path in report_paths:
        text = path.read_text(encoding="utf-8-sig")
        assert any(line.startswith("# ") for line in text.splitlines())
        assert any("\u4e00" <= char <= "\u9fff" for char in text[:1000])


def test_generated_files_match_repository_assets():
    from trading_os.research_assets.alerts import build_price_alerts
    from trading_os.research_assets.index import build_index
    from trading_os.research_assets.schedule import build_review_schedule

    root = Path(__file__).resolve().parents[1]

    index_payload = json.loads(
        (root / "research" / "index.json").read_text(encoding="utf-8")
    )

    assert index_payload == build_index(root / "research")
    assert json.loads(
        (root / "automation" / "review_schedule.json").read_text(encoding="utf-8")
    ) == build_review_schedule(root / "research")
    assert json.loads(
        (root / "automation" / "price_alerts.json").read_text(encoding="utf-8")
    ) == build_price_alerts(root / "research")
