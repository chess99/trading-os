from __future__ import annotations

import pytest


def test_cli_registers_only_research_kernel_commands():
    from trading_os.cli_internal.app import build_parser

    parser = build_parser()
    help_text = parser.format_help()

    for command in ["data", "research", "factor", "backtest", "pool"]:
        assert command in help_text
    assert "research" in help_text
    assert "factor" in help_text
    for retired in [
        "scheduler",
        "daily",
        "scan-elder",
        "scan-canslim",
        "scan-value",
        "fetch-ak-bulk",
        "fundamental-store",
        "lake-init",
        "valuation-sotp",
        "valuation-sensitivity",
        "market-breadth",
    ]:
        assert retired not in help_text


def test_pool_cli_does_not_offer_scan_sync(capsys):
    from trading_os.cli_internal.app import build_parser

    parser = build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["pool", "--help"])

    assert exc.value.code == 0
    assert "sync-from-scan" not in capsys.readouterr().out


def test_cli_parses_legacy_fundamental_migration_command():
    from trading_os.cli_internal.app import build_parser

    parser = build_parser()
    ns = parser.parse_args(
        ["data", "migrate", "legacy-fundamentals", "--as-of", "2026-06-01"]
    )

    assert ns.data_cmd == "migrate"
    assert ns.migration == "legacy-fundamentals"
    assert ns.as_of == "2026-06-01"
    assert ns.source_dir == "data/fundamental"
