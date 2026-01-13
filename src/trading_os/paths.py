from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    """Resolve repository root by walking up from this file.

    Assumption: this file lives under `src/trading_os/`.
    """

    here = Path(__file__).resolve()
    # trading-os/src/trading_os/paths.py -> trading-os
    return here.parents[3]

