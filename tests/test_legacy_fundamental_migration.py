from __future__ import annotations

import json
from datetime import date


def test_legacy_fundamentals_migrate_into_research_store(tmp_path):
    from trading_os.research.migration import migrate_legacy_fundamentals
    from trading_os.research.store import ResearchStore

    source_dir = tmp_path / "fundamental"
    source_dir.mkdir()
    (source_dir / "SSE_600000.json").write_text(
        json.dumps(
            {
                "symbol": "SSE:600000",
                "name": "浦发银行",
                "ipo_date": "1999-11-10",
                "summary_text": "财务摘要",
                "profitability": [
                    {
                        "period": "2025-12-31",
                        "pub_date": "2026-03-31",
                        "roe": 0.064403,
                        "net_margin": 0.289744,
                        "gross_margin": None,
                        "net_profit": 50_405_000_000.0,
                        "eps_ttm": 1.501749,
                    }
                ],
                "growth": [
                    {
                        "period": "2025-12-31",
                        "yoy_equity": 0.109442,
                        "yoy_asset": 0.065512,
                        "yoy_net_income": 0.099705,
                        "yoy_eps": 0.117647,
                    }
                ],
                "solvency": [
                    {
                        "period": "2025-12-31",
                        "current_ratio": None,
                        "quick_ratio": None,
                        "liability_to_asset": 0.061972,
                        "asset_to_equity": 0.009182,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    store = ResearchStore(tmp_path / "research")

    stats = migrate_legacy_fundamentals(source_dir, store, as_of=date(2026, 6, 1))

    migrated = store.get_fundamentals(["SSE:600000"], as_of=date(2026, 6, 1))
    assert stats.success == 1
    assert stats.failed == 0
    assert stats.skipped == 0
    assert migrated.shape[0] == 1
    row = migrated.iloc[0]
    assert row["symbol"] == "SSE:600000"
    assert row["name"] == "浦发银行"
    assert row["period"] == "2025-12-31"
    assert row["roe"] == 0.064403
    assert row["eps_growth_yoy"] == 0.117647
    assert row["liability_to_asset"] == 0.061972
    assert row["summary_text"] == "财务摘要"
    assert row["source_file"] == "SSE_600000.json"
    assert row["source"] == "legacy_fundamental_json"
    assert (tmp_path / "research" / "datasets" / "fundamentals" / "2026-06-01.parquet").exists()


def test_legacy_fundamentals_migration_records_bad_and_unusable_files(tmp_path):
    from trading_os.research.migration import migrate_legacy_fundamentals
    from trading_os.research.store import ResearchStore

    source_dir = tmp_path / "fundamental"
    source_dir.mkdir()
    (source_dir / "missing_symbol.json").write_text(
        json.dumps({"name": "No Symbol"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (source_dir / "empty_metrics.json").write_text(
        json.dumps({"symbol": "SSE:600001", "name": "Empty"}, ensure_ascii=False),
        encoding="utf-8",
    )
    store = ResearchStore(tmp_path / "research")

    stats = migrate_legacy_fundamentals(source_dir, store, as_of=date(2026, 6, 1))

    assert stats.success == 0
    assert stats.failed == 1
    assert stats.skipped == 1
    assert [error["file"] for error in stats.errors] == ["missing_symbol.json"]
    assert store.get_fundamentals(as_of=date(2026, 6, 1)).empty
