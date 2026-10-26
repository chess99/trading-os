"""Transport-only regressions; expanded economics match the previously accepted bytes."""
import base64
import hashlib
import json
import lzma
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from q3_final_fixture import staged_company
D=staged_company("000786")
RAW_SHA='f9c0264b2926e7d40f22f0903ac4dbb8e4f96ccc5d64477c7a713d49081bd270'
RAW_BYTES=97501197

@pytest.fixture(scope='module')
def packed():
    w=json.loads((D/'2026-Q3-output.json').read_text())
    z=base64.b64decode(w['payload_xz_base64'],validate=True)
    raw=lzma.decompress(z)
    return w,z,raw

def test_lossless_canonical_identity_and_actual_transport_budget(packed):
    w,z,raw=packed
    assert w['schema']=='deterministic-xz-json-envelope-v1'
    assert w['compression']['preset']==6
    assert len(raw)==w['uncompressed_bytes']==RAW_BYTES
    assert hashlib.sha256(raw).hexdigest()==w['payload_sha256']==RAW_SHA
    assert len(z)==w['compressed_bytes']
    assert hashlib.sha256(z).hexdigest()==w['compressed_sha256']
    assert (D/'2026-Q3-output.json').stat().st_size<15_000_000
    request=json.dumps({'path':'research/companies/CN/000786/models/2026-Q3-output.json','content':(D/'2026-Q3-output.json').read_text()},ensure_ascii=True).encode()
    assert len(request)<15_000_000
    full=json.loads(raw)
    assert w['value_range']==full['value_range']
    assert w['return_model']==full['return_model']
    assert w['tests']==full['tests']
    assert json.loads((D/'summary.json').read_text())=={k:v for k,v in w.items() if k!='payload_xz_base64'}

def test_exact_unchanged_economic_code():
    source=(D/'2026-Q3.py').read_text()
    prefix=source.split('def main():')[0]
    calculation=source[source.index("    output={'schema'"):source.index('    raw=json.dumps(output')]
    assert len(prefix.encode())==40778
    assert hashlib.sha256(prefix.encode()).hexdigest()=='5b570aac6201dcd9f84bb90c05400cec53f56fc1e0cb01323773720170d00b6b'
    assert len(calculation.encode())==2464
    assert hashlib.sha256(calculation.encode()).hexdigest()=='04147a46fb1ee49358188b54adec5699ad49777817af378e3edceaec257ad8e6'

def test_expansion_exact_bytes_explicit_target_and_protected_inputs(tmp_path,packed):
    for name in ['2026-Q3.py','2026-Q3-output.json']:shutil.copy2(D/name,tmp_path/name)
    target=tmp_path/'chosen.json'
    subprocess.run([sys.executable,str(tmp_path/'2026-Q3.py'),'--expand',str(target)],check=True,capture_output=True)
    assert target.read_bytes()==packed[2]
    for name in ['2026-Q3.py','2026-Q3-output.json']:
        p=tmp_path/name;before=p.read_bytes()
        r=subprocess.run([sys.executable,str(tmp_path/'2026-Q3.py'),'--expand',str(p)],capture_output=True)
        assert r.returncode!=0 and p.read_bytes()==before

def test_tampered_hash_rejected_before_write(tmp_path,packed):
    shutil.copy2(D/'2026-Q3.py',tmp_path/'2026-Q3.py')
    w=dict(packed[0]);w['payload_sha256']='0'*64
    (tmp_path/'2026-Q3-output.json').write_text(json.dumps(w))
    r=subprocess.run([sys.executable,str(tmp_path/'2026-Q3.py'),'--expand'],capture_output=True)
    assert r.returncode!=0
    assert not (tmp_path/'expanded-output.json').exists()

def test_reader_result_candidate_transport_instructions():
    report=(D/'report.md').read_text()
    r=json.loads((D/'result.json').read_text())
    assert r==json.loads((D/'candidate.json').read_text())['result']
    assert r['report_markdown']==report
    for text in ['deterministic-xz-json-envelope-v1','payload_xz_base64','lzma.decompress','python 2026-Q3.py --expand','../models/2026-Q3.py','../models/2026-Q3-output.json']:
        assert text in report
