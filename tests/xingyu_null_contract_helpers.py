"""Explicit null-current metadata and retained historical transport contracts.
The separate historical financial node is not executed by a sparse metadata qualification.
"""
import hashlib,json,math,shutil,stat,struct,subprocess,sys
from pathlib import Path
CODE='601799'
BASE='research/companies/CN/601799/models/'
HIST=BASE+'2026-Q3-evidence/historical/'
EXPECTED={'research/companies/CN/601799/models/2026-Q3-evidence/CONSUMER-DISPOSITIONS.json': {'bytes': 121364, 'sha256': '2189fa56473198440dfa04778308d2a213da24c1cf17e7f86c7e8910f2c8c268', 'mode': 420}, 'research/companies/CN/601799/models/2026-Q3-evidence/FUNDING-EVENTS.json': {'bytes': 71910, 'sha256': '13a4e9837f698f2d8e53a0545315b1bddf9d7883c6b10039136476468a6202cf', 'mode': 420}, 'research/companies/CN/601799/models/2026-Q3-evidence/OFFICIAL-SOURCES.json': {'bytes': 2562, 'sha256': '1e3ae440709e1d77c70f0b5d54e7609a08b3bbcd71161a14f63ca1c26951b349', 'mode': 420}, 'research/companies/CN/601799/models/2026-Q3-evidence/ORIGINAL-ARTIFACT-IDENTITIES.json': {'bytes': 67833, 'sha256': 'a3db27d3a73fd22185de53a4bae58fb30c334b955c985cd5236626e9ebe90271', 'mode': 420}, 'research/companies/CN/601799/models/2026-Q3-evidence/PUBLIC-MANIFEST.json': {'bytes': 2812, 'sha256': 'c99a5ca2e50922e05c7e526368d5c3953117cde98edb4b87b3f44e75da28d5f0', 'mode': 420}, 'research/companies/CN/601799/models/2026-Q3-evidence/README.md': {'bytes': 4226, 'sha256': 'f8524943a4ebbad4db563ec93d404b57ef4802443a95ff2e5d6d90519d292674', 'mode': 420}, 'research/companies/CN/601799/models/2026-Q3-evidence/historical/2026-Q3-independent-recompute.py': {'bytes': 18251, 'sha256': 'b7306dd18fc7d5cfaa45f79a617b58b29ebc951d84129786d22937febc34aaf7', 'mode': 420}, 'research/companies/CN/601799/models/2026-Q3-evidence/historical/2026-Q3-output.json': {'bytes': 453, 'sha256': 'd413fe4ba0df143652801750aa611d1638661db55ca31ce4f9f59c88244d28b3', 'mode': 420}, 'research/companies/CN/601799/models/2026-Q3-evidence/historical/2026-Q3.py': {'bytes': 26276, 'sha256': '24280c79fbde8ba4e7824dba25a403acb79467498d0ee3daf3f7189083fa2d9f', 'mode': 420}, 'research/companies/CN/601799/models/2026-Q3-evidence/historical/previous-2026-Q3.md': {'bytes': 29447, 'sha256': 'd4a9455669678833a8c5579e1f94122c11cb7444968eaeeb90b6fe33b2302c1d', 'mode': 420}, 'research/companies/CN/601799/models/2026-Q3-evidence/sources/1225651659.PDF': {'bytes': 88560, 'sha256': 'cfebfb177eb86e046919f422cc44ea59177ca4cb3b731af79052fef87834e062', 'mode': 420}, 'research/companies/CN/601799/models/2026-Q3-evidence/sources/1225651659.txt': {'bytes': 4436, 'sha256': 'dc6761581d95d52e2ef7dbab8f0bc2693ea9dc44c4b3f0bc447a6e31ca7c64f6', 'mode': 420}, 'research/companies/CN/601799/models/2026-Q3-independent-recompute.py': {'bytes': 1113, 'sha256': 'c95c815917ea51fcd42c7aa24ec4bc0f4425ac20525f5161d026f3b59cecf60b', 'mode': 420}, 'research/companies/CN/601799/models/2026-Q3-output.json': {'bytes': 2586, 'sha256': 'f5285414e49567ac70514db875f5be0dd7ea903011cee667679163dfdace641b', 'mode': 420}, 'research/companies/CN/601799/models/2026-Q3.py': {'bytes': 1075, 'sha256': 'cb286389e62a9960bf98870ff84518c542ae28d0f31f267e1e707d807dd62593', 'mode': 420}, 'research/companies/CN/601799/reports/2026-Q3.md': {'bytes': 32325, 'sha256': '1797181852738b4c4445350144962d146b1d527095cf815706968c527bb784eb', 'mode': 420}, 'research/companies/CN/601799/models/2026-Q3-evidence/historical/2026-Q3-output.json.xz': {'bytes': 8879516, 'sha256': 'd5c3a03ce0dcf0aaa2c8b38523e877461a6556d0a41be5da907565209f1b9208', 'mode': 420}}
CURRENT_OUTPUT_SHA='f5285414e49567ac70514db875f5be0dd7ea903011cee667679163dfdace641b'
def digest(p):
    h=hashlib.sha256()
    with Path(p).open('rb')as f:
        while b:=f.read(1048576):h.update(b)
    return h.hexdigest()
def exact(a,b):
    assert type(a)is type(b)
    if isinstance(a,dict):
        assert set(a)==set(b)
        for k in a:exact(a[k],b[k])
    elif isinstance(a,list):
        assert len(a)==len(b)
        for x,y in zip(a,b):exact(x,y)
    elif isinstance(a,float):assert math.isfinite(a)and math.isfinite(b)and struct.pack('!d',a)==struct.pack('!d',b)
    else:assert a==b

def regular(p,row):
    st=Path(p).lstat();assert stat.S_ISREG(st.st_mode)and not Path(p).is_symlink()and st.st_nlink==1
    assert(st.st_size,digest(p),stat.S_IMODE(st.st_mode))==(row['bytes'],row['sha256'],row['mode'])
def invoke(script,args,expected):
    run=subprocess.run([sys.executable,'-B',str(script),*map(str,args)],cwd=script.parent,capture_output=True,check=False)
    assert run.returncode==expected,run.stderr
    return run

def assert_null_current(root,tmp):
    models=Path(root)/BASE;expected=json.loads((models/'2026-Q3-output.json').read_text())
    assert digest(models/'2026-Q3-output.json')==CURRENT_OUTPUT_SHA
    assert expected['value_range']is None and expected['return_model']is None
    assert expected['valuation_note'].strip()and expected['return_model_note'].strip()
    assert expected['numeric_model_pass']is False and expected['economic_adoption']is False and expected['fallback_to_previous_or_own']is False
    assert type(expected['original_completed_saved_review_exit'])is int and expected['original_completed_saved_review_exit']==2
    for name in ('2026-Q3.py','2026-Q3-independent-recompute.py'):
        isolated=tmp/name.replace('.py','');isolated.mkdir();copied=isolated/name;shutil.copyfile(models/name,copied);copied.chmod(0o644)
        # Copy current entry plus its status JSON only; never historical finance.
        shutil.copyfile(models/'2026-Q3-output.json',isolated/'2026-Q3-output.json')
        actual=invoke(copied,[],2)
        assert not actual.stderr
        exact(json.loads(actual.stdout),expected)
        assert set(p.name for p in isolated.iterdir())=={name, '2026-Q3-output.json'}
    evidence=Path(root)
    # All current scientific evidence retains the original identity. Reports and
    # README layout guidance changed, and historical objects live in immutable Git.
    for rel,row in EXPECTED.items():
        if '/historical/' not in rel and not rel.endswith('.md'):
            regular(evidence/rel,row)
    # A genuine invalid-metadata fixture uses unchanged original tiny route, not finance.
    original=evidence/(BASE+'2026-Q3.py');regular(original,EXPECTED[BASE+'2026-Q3.py'])
    bad=tmp/'bad-metadata';bad.mkdir();shutil.copyfile(original,bad/'2026-Q3.py')
    invalid=dict(expected);invalid['value_range']={'low':0,'high':0,'currency':'CNY'}
    (bad/'2026-Q3-output.json').write_text(json.dumps(invalid,ensure_ascii=False))
    rejected=invoke(bad/'2026-Q3.py',[],1)
    assert not rejected.stdout and json.loads(rejected.stderr)['status']=='TECHNICAL_METADATA_ERROR'
    return {'metadata_expected_exit':2,'model_numeric_pass':False,'historical_financial_executions':0}

def historical_root(root,tmp):
    from compact_null_history import restore_history
    target = restore_history(root, tmp, '601799')
    for path in target.iterdir():
        regular(path, EXPECTED[HIST + path.name])
    descriptor=json.loads((target/'2026-Q3-output.json').read_text());assert descriptor['file']=='2026-Q3-output.json.xz'
    assert descriptor['compressed_bytes']==EXPECTED[HIST+descriptor['file']]['bytes'] and descriptor['compressed_sha256']==EXPECTED[HIST+descriptor['file']]['sha256']
    return target
