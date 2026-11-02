"""Actual cold cash-only entry; original mine/service producer is never run."""

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "research/companies/CN/603979/models"
PREFIX = "2026-Q3-capital-20261102"


def test_jchx_capital_cash_complete_cold_entry(tmp_path):
    consumer = tmp_path / "download"
    consumer.mkdir()
    for name in [
        PREFIX + ".py",
        PREFIX + "-output.json",
        PREFIX + "-check.py",
        "2026-Q3-output.json",
    ]:
        source = MODELS / name
        assert source.is_file() and not source.is_symlink()
        shutil.copyfile(source, consumer / name)
        assert (consumer / name).read_bytes() == source.read_bytes()
    generated = consumer / "new-cash.json"

    def run(label, argv, success):
        result = subprocess.run(
            [sys.executable, "-B", "-S", *map(str, argv)],
            cwd=tmp_path,
            capture_output=True,
            timeout=60,
            check=False,
        )
        (tmp_path / (label + ".stdout")).write_bytes(result.stdout)
        (tmp_path / (label + ".stderr")).write_bytes(result.stderr)
        assert (result.returncode == 0) is success, (label, result.returncode, result.stderr)
        return result

    run("current-five-cash-producer", [consumer / (PREFIX + ".py"), "--output", generated], True)
    assert generated.read_bytes() == (consumer / (PREFIX + "-output.json")).read_bytes()
    result = run(
        "independent-cash-invariants",
        [consumer / (PREFIX + "-check.py"), "--output", generated],
        True,
    )
    receipt = json.loads(result.stdout)
    assert (
        receipt["rows_checked"] == 150
        and receipt["historical_diagnostic_scenarios_not_updated"] == 25
    )
    current = json.loads(generated.read_bytes())
    state = next(
        json.loads(line)
        for line in (ROOT / "coverage/cn-a/research_state.jsonl").read_text().splitlines()
        if json.loads(line)["symbol"] == "CN:603979"
    )
    actual_d = current["summary"]["base_D"]
    for old, new in zip(
        state["return_model"]["base_case_distributions_per_share"], actual_d, strict=False
    ):
        assert abs(old - new) <= 1e-11 * max(1.0, abs(old))
    for endpoint in ["low", "high"]:
        assert (
            state["return_model"]["base_case_terminal_equity_value_range_per_share"]["year_5"][
                endpoint
            ]
            == current["conditional_year5"]["core_" + endpoint]["terminal_year5_per_share"]
        )
    assert current["scope"]["shares_unchanged"] and current["scope"]["current_cash_paths"] == 5
    altered = json.loads(generated.read_bytes())
    altered["scenarios"]["core_high"]["years"][1]["ending"]["parent_cash"] += 0.001
    wrong = consumer / "changed-cash.json"
    wrong.write_text(json.dumps(altered))
    run("tampered-cash-negative", [consumer / (PREFIX + "-check.py"), "--output", wrong], False)
    baseline = consumer / "2026-Q3-output.json"
    retained = tmp_path / "baseline-original.json"
    baseline.rename(retained)
    run("missing-baseline-negative", [consumer / (PREFIX + ".py")], False)
    baseline.write_bytes(retained.read_bytes() + b" ")
    run("tampered-baseline-negative", [consumer / (PREFIX + ".py")], False)
    baseline.unlink()
    baseline.symlink_to(retained)
    run("symlink-baseline-negative", [consumer / (PREFIX + ".py")], False)
    baseline.unlink()
    shutil.copyfile(retained, baseline)
    run("no-overwrite-negative", [consumer / (PREFIX + ".py"), "--output", generated], False)
    assert (
        hashlib.sha256(generated.read_bytes()).hexdigest()
        == hashlib.sha256((consumer / (PREFIX + "-output.json")).read_bytes()).hexdigest()
    )
