import subprocess
import textwrap
from pathlib import Path

import pytest


WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/research-ingest.yml"


@pytest.mark.parametrize("with_inbox,changed", [(False, True), (True, True), (False, False)])
def test_coordinator_commit_handles_missing_or_consumed_inbox(tmp_path, with_inbox, changed):
    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=tmp_path, check=True, capture_output=True, text=True
        ).stdout.strip()

    git("init", "--quiet")
    git("config", "user.name", "Test")
    git("config", "user.email", "test@example.com")
    state = tmp_path / "coverage/cn-a/research_state.jsonl"
    report = tmp_path / "research/companies/CN/000001/reports/2026-Q3.md"
    for path in (state, report):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("original\n", encoding="utf-8")
    inbox = tmp_path / "research/inbox/result.json"
    if with_inbox:
        inbox.parent.mkdir(parents=True)
        inbox.write_text("{}\n", encoding="utf-8")
    git("add", ".")
    git("commit", "--quiet", "-m", "initial")
    original = git("rev-parse", "HEAD")
    if with_inbox:
        inbox.unlink()
        inbox.parent.rmdir()
    if changed:
        state.write_text("updated\n", encoding="utf-8")
        report.write_text("updated\n", encoding="utf-8")
    (tmp_path / "unrelated.txt").write_text("do not publish\n", encoding="utf-8")

    step = WORKFLOW.read_text(encoding="utf-8").split(
        "      - name: Commit coordinator outputs\n", 1
    )[1]
    script = textwrap.dedent(step.split("        run: |\n", 1)[1])
    # Exercise the real workflow step; keep its pull/push inside this local fixture.
    local_git = """
git() {
  case "$1" in
    pull|push) printf 'REMOTE_%s\\n' "$1" ;;
    *) command git "$@" ;;
  esac
}
"""
    result = subprocess.run(
        ["bash", "-c", local_git + script],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (git("rev-parse", "HEAD") != original) == changed
    assert git("status", "--porcelain") == "?? unrelated.txt"
    assert ("REMOTE_push" in result.stdout) == changed
