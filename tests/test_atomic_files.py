import json

import pytest

from trading_os.research_assets import research_flow


@pytest.mark.parametrize("as_json", [False, True])
def test_transient_windows_reader_lock_does_not_expose_a_partial_write(
    tmp_path, monkeypatch, as_json
):
    target = tmp_path / "state.jsonl"
    target.write_bytes(b"original\n")
    replace = research_flow.os.replace
    attempts = []

    def occasionally_busy(source, destination):
        attempts.append(source)
        if len(attempts) < 3:
            assert target.read_bytes() == b"original\n"
            error = PermissionError("reader still holds file")
            error.winerror = 32
            raise error
        replace(source, destination)

    monkeypatch.setattr(research_flow.os, "replace", occasionally_busy)
    monkeypatch.setattr(research_flow.time, "sleep", lambda _: None)
    if as_json:
        research_flow._atomic_write_jsonl(target, [{"symbol": "CN:000001"}])
        assert json.loads(target.read_text(encoding="utf-8")) == {"symbol": "CN:000001"}
    else:
        research_flow._atomic_write_text(target, "complete replacement\n")
        assert target.read_bytes() == b"complete replacement\n"
    assert len(attempts) == 3
    assert list(tmp_path.iterdir()) == [target]


def test_persistent_access_denial_fails_without_destroying_the_original(tmp_path, monkeypatch):
    target = tmp_path / "state.jsonl"
    target.write_bytes(b"original\n")
    attempts = []

    def always_busy(source, destination):
        attempts.append(source)
        error = PermissionError("denied")
        error.winerror = 5
        raise error

    monkeypatch.setattr(research_flow.os, "replace", always_busy)
    monkeypatch.setattr(research_flow.time, "sleep", lambda _: None)
    with pytest.raises(PermissionError):
        research_flow._atomic_write_text(target, "replacement")
    assert 1 < len(attempts) < 10
    assert target.read_bytes() == b"original\n"
    assert list(tmp_path.iterdir()) == [target]
