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


def test_cli_alerts_check_accepts_utf8_bom_json(tmp_path: Path, capsys):
    from trading_os.cli import main

    alerts_path = tmp_path / "alerts.json"
    quotes_path = tmp_path / "quotes.json"
    alerts_path.write_text(
        "\ufeff"
        + json.dumps(
            {
                "schema_version": 1,
                "items": [
                    {
                        "symbol": "CN:600519",
                        "name": "璐靛窞鑼呭彴",
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
        "\ufeff" + json.dumps([{"symbol": "CN:600519", "price": 1090}], ensure_ascii=False),
        encoding="utf-8",
    )

    code = main(["alerts", "check", "--alerts", str(alerts_path), "--quotes", str(quotes_path)])

    assert code == 0
    assert '"triggered_count": 1' in capsys.readouterr().out


def test_cli_alerts_check_rejects_non_object_alerts(tmp_path: Path, capsys):
    from trading_os.cli import main

    alerts_path = tmp_path / "alerts.json"
    quotes_path = tmp_path / "quotes.json"
    alerts_path.write_text(json.dumps([], ensure_ascii=False), encoding="utf-8")
    quotes_path.write_text(
        json.dumps([{"symbol": "CN:600519", "price": 1090}], ensure_ascii=False),
        encoding="utf-8",
    )

    code = main(["alerts", "check", "--alerts", str(alerts_path), "--quotes", str(quotes_path)])

    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    payload = json.loads(captured.err)
    assert payload["ok"] is False
    assert "alert" in payload["error"]
    assert "Traceback" not in captured.err


def test_cli_company_validate_missing_dir_writes_json_error_to_stderr(
    tmp_path: Path, capsys
):
    from trading_os.cli import main

    code = main(["company", "validate", str(tmp_path / "missing-company")])

    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    payload = json.loads(captured.err)
    assert payload["ok"] is False
    assert "company directory does not exist" in payload["error"]


def test_cli_index_rebuild_invalid_metadata_writes_json_error_to_stderr(
    tmp_path: Path, capsys
):
    from trading_os.cli import main

    company_dir = write_company(tmp_path)
    meta_path = company_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["latest_report"] = "reports/missing.md"
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    code = main(["index", "rebuild", "--research-root", str(tmp_path / "research")])

    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    payload = json.loads(captured.err)
    assert payload["ok"] is False
    assert any("latest_report" in error for error in payload["errors"])
