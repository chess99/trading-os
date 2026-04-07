#!/usr/bin/env python3
"""Run all tests via pytest (preferred) or unittest fallback."""

import subprocess
import sys

if __name__ == "__main__":
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-v"],
        cwd=str(__import__("pathlib").Path(__file__).parent.parent),
    )
    sys.exit(result.returncode)
