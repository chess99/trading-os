"""Trading OS program entrypoint.

This module intentionally exposes only the public CLI entrypoint. Internal
parser builders and command helpers live under ``trading_os.cli_internal`` and
are not part of the supported import surface.
"""

from __future__ import annotations

from .cli_internal.app import main

__all__ = ["main"]
