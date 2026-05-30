from __future__ import annotations


def test_cli_registers_research_kernel_commands_without_scheduler_or_bulk():
    from trading_os.cli_internal.app import build_parser

    parser = build_parser()
    help_text = parser.format_help()

    assert "research" in help_text
    assert "factor" in help_text
    assert "scheduler" not in help_text
    assert "daily" not in help_text
    assert "fetch-ak-bulk" not in help_text
