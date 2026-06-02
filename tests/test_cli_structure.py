"""CLI public boundary regression tests."""

import importlib.util

import pytest


def test_cli_exposes_only_main():
    from trading_os import cli

    assert callable(cli.main)


def test_cli_does_not_export_internal_parser():
    with pytest.raises(ImportError):
        from trading_os.cli import build_parser  # noqa: F401


def test_retired_modules_are_not_importable():
    retired = [
        "trading_os.scheduler",
        "trading_os.scan",
        "trading_os.data.lake",
        "trading_os.data.pipeline",
        "trading_os.cli_internal.commands.data",
        "trading_os.cli_internal.commands.scan",
        "trading_os.cli_internal.commands.analysis",
        "trading_os.cli_internal.commands.strategy",
    ]

    for module_name in retired:
        assert importlib.util.find_spec(module_name) is None, module_name
