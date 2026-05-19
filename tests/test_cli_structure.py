"""CLI structure regression tests."""


def test_cli_exposes_main_build_parser_and_compat_exports():
    from trading_os import cli

    assert callable(cli.main)
    assert callable(cli.build_parser)
    assert callable(cli._pool_path)
    assert callable(cli._stock_names_path)
    assert callable(cli._append_tracking)
    assert callable(cli._acquire_bulk_lock)
    assert callable(cli._release_bulk_lock)
    assert callable(cli._write_bulk_progress)


def test_build_parser_contains_known_commands():
    from trading_os.cli import build_parser

    parser = build_parser()
    subparsers_action = next(
        action for action in parser._actions
        if getattr(action, "choices", None)
    )
    commands = set(subparsers_action.choices)

    assert "backtest" in commands
    assert "scan-value" in commands
    assert "pool" in commands
