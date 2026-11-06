"""Offline immutable-history restoration. Byte retrieval only, never financial execution."""
import hashlib
import json
from pathlib import Path
import subprocess

def restore_history(root, tmp, symbol):
    root = Path(root).resolve()
    refs = json.loads((root / f'research/companies/CN/{symbol}/models/2026-Q3-evidence/HISTORY-REFERENCES.json').read_text())
    target = Path(tmp) / 'history' / f'research/companies/CN/{symbol}/models'
    target.mkdir(parents=True, exist_ok=False)
    selected = [row for row in refs['historical_members_not_duplicated'] if row['baseline_path'] is not None]
    assert selected
    for row in selected:
        commit = row['baseline_commit']
        assert commit == 'ba611a5bef5d0a39022dd01945f0b62f9f01f4c0'
        path = row['baseline_path']
        assert path.startswith(f'research/companies/CN/{symbol}/') and '..' not in Path(path).parts
        result = subprocess.run(['git', '-c', 'remote.origin.promisor=false', 'show', f'{commit}:{path}'], cwd=root, capture_output=True, timeout=30, env={**__import__('os').environ, 'GIT_NO_LAZY_FETCH':'1', 'GIT_TERMINAL_PROMPT':'0'})
        assert result.returncode == 0, 'Required immutable baseline object is unavailable locally; no network fetch is attempted: ' + result.stderr.decode(errors='replace')
        raw = result.stdout
        assert len(raw) == row['bytes'] and hashlib.sha256(raw).hexdigest() == row['sha256']
        destination = target / Path(row['archive_member']).name
        with destination.open('xb') as output:
            output.write(raw)
        destination.chmod(0o644)
    return target
