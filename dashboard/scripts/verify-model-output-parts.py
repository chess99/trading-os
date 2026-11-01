"""Trusted codec-only entry: closed canonical descriptor on stdin; no research execution."""

import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from trading_os.model_output_parts import MAX_MANIFEST_BYTES, verify_outputs  # noqa: E402

if __name__ == "__main__":
    verify_outputs(sys.argv[1], sys.stdin.buffer.read(MAX_MANIFEST_BYTES + 1), *sys.argv[2:5])
    print("complete output parts / whole XZ / all JSON verified")
