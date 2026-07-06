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
