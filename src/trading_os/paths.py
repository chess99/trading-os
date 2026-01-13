from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    """Resolve repository root by searching for `pyproject.toml` upward.

    This works both when running from source and when installed in editable mode.
    """
    here = Path(__file__).resolve()
    for p in [here, *here.parents]:
        if (p / "pyproject.toml").exists():
            return p
    # Fallback: assume src layout: repo/src/trading_os/paths.py
    return here.parents[2]

