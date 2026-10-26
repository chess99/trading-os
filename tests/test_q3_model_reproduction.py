"""隔离重跑正式Q3模型；公司模型内的手算特例随正式计算链执行。"""
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODELS = sorted((ROOT / "research/companies/CN").glob("*/models/2026-Q3.py"))


@pytest.mark.parametrize("model", MODELS, ids=lambda path: path.parent.parent.name)
def test_published_q3_model_reproduces_in_isolated_directory(model, tmp_path):
    # No original artifacts are modified, and no repository working directory is assumed.
    copied = tmp_path / model.name
    shutil.copyfile(model, copied)
    result = subprocess.run(
        [sys.executable, str(copied)], cwd=tmp_path.parent,
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stderr
    output = "2026-Q3-output.json"
    expected = json.loads((model.parent / output).read_text())
    # Earlier single-file models emit their complete JSON to stdout; newer ones
    # save beside __file__. Both are supported reproducible public interfaces.
    generated = tmp_path / output
    actual = json.loads(generated.read_text() if generated.exists() else result.stdout)
    assert actual == expected
