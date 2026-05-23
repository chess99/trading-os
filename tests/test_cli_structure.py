"""CLI public boundary regression tests."""

import pytest


def test_cli_exposes_only_main():
    from trading_os import cli

    assert callable(cli.main)


def test_cli_does_not_export_internal_parser():
    with pytest.raises(ImportError):
        from trading_os.cli import build_parser  # noqa: F401
