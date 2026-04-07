from __future__ import annotations

import os
from pathlib import Path


def _load_dotenv() -> None:
    """Load .env file from repo root if it exists.

    Simple parser: supports KEY=VALUE and KEY="VALUE", ignores comments (#).
    Does NOT override existing environment variables (same behavior as dotenv).
    """
    env_path = Path(__file__).parent.parent.parent.parent / ".env"
    if not env_path.exists():
        return
    with env_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


_load_dotenv()

from .cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
