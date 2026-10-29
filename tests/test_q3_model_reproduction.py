"""隔离重跑正式Q3模型；公司模型内的手算特例随正式计算链执行。"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

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
    # Serial measured consumer runtimes: 248.480s and 525.087s respectively.
    # Bounded transport budgets retain every numerical and byte assertion.
    timeout = {"002847": 600, "600309": 1200}.get(model.parent.parent.name, 240)
    result = subprocess.run(
        [sys.executable, str(copied), *args],
        cwd=tmp_path.parent,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    output = "2026-Q3-output.json"
    expected = json.loads((model.parent / output).read_text())
    # Earlier single-file models emit their complete JSON to stdout; newer ones
    # save beside __file__. Both are supported reproducible public interfaces.
    generated = tmp_path / output
    if not generated.exists():
        generated.write_text(result.stdout)
    actual = json.loads(generated.read_text())
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
    restored_codes = {
        "600276",
        "603298",
        "688111",
        "000729",
        "000858",
        "000895",
        "002027",
        "301498",
        "603816",
        "300529",
        "300832",
        "688578",
        "002001",
        "002463",
        "300596",
        "301696",
        "603197",
        "688300",
        "600377",
        "600926",
        "601985",
        "603568",
    }
    newly_disclosed_codes = {
        "300487",
        "600761",
        "688271",
        "688581",
        "601009",
        "300573",
        "002595",
        "003816",
        "600585",
        "601799",
        "600809",
        "601601",
        "601318",
        "300408",
        "603855",
        "002050",
        "600600",
        "603501",
        "601091",
        "603345",
        "002422",
        "300705",
        "300394",
        "300896",
        "603606",
        "688617",
        "603871",
        "601838",
        "600886",
        "600406",
    }
    migrated_codes = {entry["code"] for entry in migrated["companies"]}
    if model.parent.parent.name in migrated_codes | restored_codes | newly_disclosed_codes:
        assert generated.read_bytes() == (model.parent / output).read_bytes()

    # Checkers consume only files recreated in the isolated consumer directory.
    verifications = set(model.parent.glob("2026-Q3*verification.py"))
    verifications.update(model.parent.glob("2026-Q3-independent-recompute.py"))
    for verification in sorted(verifications):
        check_copy = tmp_path / verification.name
        shutil.copyfile(verification, check_copy)
        checked = subprocess.run(
            [sys.executable, str(check_copy)],
            cwd=tmp_path.parent,
            capture_output=True,
            text=True,
            timeout=240,
            check=False,
        )
        assert checked.returncode == 0, checked.stderr
