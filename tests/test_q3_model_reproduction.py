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
    # Amoy's published reader artifact is the documented expanded interface;
    # its default CLI emits an envelope. Generate the exact published form.
    args = ["--expand"] if model.parent.parent.name == "300685" else []
    result = subprocess.run(
        [sys.executable, str(copied), *args], cwd=tmp_path.parent,
        capture_output=True, text=True, timeout=240, check=False,
    )
    assert result.returncode == 0, result.stderr
    output = "2026-Q3-output.json"
    expected = json.loads((model.parent / output).read_text())
    # Earlier single-file models emit their complete JSON to stdout; newer ones
    # save beside __file__. Both are supported reproducible public interfaces.
    generated = tmp_path / output
    actual = json.loads(generated.read_text() if generated.exists() else result.stdout)
    assert actual == expected

    # Every published sibling case is part of the public transport contract.
    # In particular 300033 has 54 case JSON files, not merely its small index.
    cases = sorted(model.parent.glob("2026-Q3-case-*.json"))
    if model.parent.parent.name == "300033":
        assert len(cases) == 54
    for case in cases:
        assert (tmp_path / case.name).is_file(), case.name
        assert (tmp_path / case.name).read_bytes() == case.read_bytes(), case.name
    # Corrected single-file producers promise exact deterministic main bytes.
    migrated = json.loads((ROOT / "tests/q3-final-test-migration.json").read_text())
    if model.parent.parent.name in {entry["code"] for entry in migrated["companies"]}:
        assert generated.read_bytes() == (model.parent / output).read_bytes()
