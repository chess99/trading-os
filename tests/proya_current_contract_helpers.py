"""Explicit Proya current transport versus full-financial contracts.
Transport never invokes --output. Full-financial is separately selectable and NOT_RUN
in the cumulative engineering partition. Pins come from independent original503
build/qualification evidence, not from trusting the wrapper's EXPECTED variable.
"""
import ast, copy, datetime, gzip, hashlib, json, os, shutil, stat, subprocess, sys
from pathlib import Path

ENTRY='research/companies/CN/603605/models/2026-Q3.py'
WRAPPER_SHA='f3391ec97998b2eb9f099d7a1314f14da7ae94b24065408682acda8f1dd6c4a6'
INDEX_SHA='61ac1c5ce04ba4f40817253e9303a6611077f422c53d9b2c047516d2d0488fa5'
INNER_SHA='d9117c3cfef0b26b1759bc7041cecfddf79f602a14f5aafdeddac5e1a7b29ae7'

def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()

def typed_exact(a,b):
    assert type(a) is type(b)
    if isinstance(a,dict):
        assert set(a)==set(b)
        for key in a: typed_exact(a[key],b[key])
    elif isinstance(a,list):
        assert len(a)==len(b)
        for x,y in zip(a,b): typed_exact(x,y)
    else:
        assert a==b

def index_for(root):
    path = Path(root)/'tests/proya-current-original503.json'
    assert digest(path) == INDEX_SHA
    result = json.loads(path.read_bytes())
    assert len(result) == 503
    return result

def exact_tree(directory, expected):
    files = set()
    for parent, dirs, names in os.walk(directory, followlinks=False):
        for name in dirs:
            assert not (Path(parent)/name).is_symlink()
        for name in names:
            path = Path(parent)/name
            relative = path.relative_to(directory).as_posix()
            assert relative in expected
            row = expected[relative]; info = path.lstat()
            assert stat.S_ISREG(info.st_mode) and info.st_nlink == 1
            assert (info.st_size, stat.S_IMODE(info.st_mode), digest(path)) == (row['bytes'],row['mode'],row['sha256'])
            files.add(relative)
    assert files == set(expected)

def copied_wrapper(root, tmp):
    source = Path(root)/ENTRY
    assert digest(source) == WRAPPER_SHA
    target = tmp/'2026-Q3.py'
    shutil.copyfile(source, target)
    assert digest(target) == WRAPPER_SHA
    return target

def invoke(wrapper, args, logdir, label):
    assert not sys.flags.optimize
    argv = [sys.executable, '-I', '-B', str(wrapper), *map(str,args)]
    with (logdir/(label+'.stdout')).open('xb') as out, (logdir/(label+'.stderr')).open('xb') as err:
        result = subprocess.run(argv, cwd=wrapper.parent, stdout=out, stderr=err, check=False)
    assert result.returncode == 0, str(logdir/(label+'.stderr'))
    return (logdir/(label+'.stdout')).read_text(), (logdir/(label+'.stderr')).read_text()

def assert_current_transport(root, tmp):
    expected = index_for(root)
    wrapper = copied_wrapper(root,tmp)
    extracted = tmp/'extracted'
    invoke(wrapper,['--extract-only',extracted],tmp,'extract')
    exact_tree(extracted,expected)
    helped = tmp/'help-extracted'
    stdout,stderr = invoke(wrapper,['--engine-help',helped],tmp,'help')
    exact_tree(helped,expected)
    events=[json.loads(line.split(' ',1)[1]) for line in stderr.splitlines() if line.startswith('TRANSPORT_DISPATCH ')]
    ends=[json.loads(line.split(' ',1)[1]) for line in stderr.splitlines() if line.startswith('TRANSPORT_EXIT ')]
    assert len(events)==len(ends)==1 and ends[0]['actual_exit']==0
    assert events[0]['argv']==[sys.executable,'-I','-B',str(helped/ENTRY),'--help']
    assert events[0]['entry_sha256']==INNER_SHA and '--output' in stdout
    publication=Path(root)/Path(ENTRY).parent/'2026-Q3-output.json'
    original=extracted/Path(ENTRY).parent/'2026-Q3-output.json'
    assert publication.read_bytes()==original.read_bytes()
    current=json.loads(publication.read_bytes())
    assert len(current['primary'])==8 and len(current['diagnostics'])==9
    machine=json.loads((extracted/Path(ENTRY).parent/'2026-Q3-current/MACHINE-INPUTS.json').read_bytes())
    typed_exact(current['value_range'],machine['value_range'])
    typed_exact(current['return_model'],machine['return_model'])
    states=[json.loads(line) for line in (Path(root)/'coverage/cn-a/research_state.jsonl').read_text().splitlines()]
    rows=[row for row in states if row['symbol']=='CN:603605']; assert len(rows)==1
    # Only native serialization of this fixed information-version instant differs.
    # Production output, machine input, economic dates and PV origin stay exact.
    native_expected={key:copy.deepcopy(machine[key]) for key in ('value_range','return_model')}
    assert native_expected['return_model']['model_as_of']=='2026-11-03T00:00:00Z'
    native_model_as_of='2026-11-03T00:00:00+00:00'
    assert datetime.datetime.fromisoformat(native_expected['return_model']['model_as_of'])==datetime.datetime.fromisoformat(native_model_as_of)
    native_expected['return_model']['model_as_of']=native_model_as_of
    for key in ('value_range','return_model'):
        typed_exact(rows[0][key],native_expected[key])
    assert not any((extracted/part).exists() for part in ('formal','own','author','comparison'))

def assert_full_financial(root,tmp):
    # This is a real financial execution. Never select in nonfinancial partitions.
    expected=index_for(root)
    wrapper_dir=tmp/'wrapper'
    wrapper_dir.mkdir()
    wrapper=copied_wrapper(root,wrapper_dir)
    output=tmp/'financial-output'
    stdout,stderr=invoke(wrapper,['--output',output],tmp,'full-financial')
    package=Path(str(output)+'.source-package')
    exact_tree(package,expected)
    events=[json.loads(line.split(' ',1)[1]) for line in stderr.splitlines() if line.startswith('TRANSPORT_DISPATCH ')]
    ends=[json.loads(line.split(' ',1)[1]) for line in stderr.splitlines() if line.startswith('TRANSPORT_EXIT ')]
    assert len(events)==len(ends)==1 and ends[0]['actual_exit']==0
    assert events[0]['argv']==[sys.executable,'-I','-B',str(package/ENTRY),'--output',str(output)]
    assert events[0]['entry_sha256']==INNER_SHA
    assert (Path(root)/Path(ENTRY).parent/'2026-Q3-output.json').read_bytes()==(package/Path(ENTRY).parent/'2026-Q3-output.json').read_bytes()
    qualify_complete_financial(output,package/Path(ENTRY).parent)

def qualify_complete_financial(output, public):
    D=Path(output); PUB=Path(public); C=PUB/"2026-Q3-current"; O=Path(output)
    def read(p):return json.loads(Path(p).read_text())
    def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
    def put(p,x):p.open('x').write(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
    def equal(a,b,p=''):
     assert type(a)is type(b),(p,'type',type(a).__name__,type(b).__name__)
     if isinstance(a,dict):
      assert list(a)==list(b),(p,'keys/order')
      for k in a:equal(a[k],b[k],p+'/'+k)
     elif isinstance(a,list):
      assert len(a)==len(b),(p,'length')
      for i,(x,y)in enumerate(zip(a,b)):equal(x,y,p+'/'+str(i))
     else:assert a==b,(p,a,b)
    def load_ref(ref):
     p=Path(ref['path']);assert ref['complete']is True and p.stat().st_size==ref['compressed_bytes']and sha(p)==ref['compressed_sha256'];raw=gzip.decompress(p.read_bytes());assert len(raw)==ref['expanded_bytes']and hashlib.sha256(raw).hexdigest()==ref['expanded_sha256'];return json.loads(raw)
    t=read(O/'ACTUAL-TERMINAL.json');assert t['actual_exit']==0 and t['differences']==0 and t['pairs_completed']==17 and t['direct_saved_consumer_relationships']==194 and t['economic_adoption']is False
    formal=read(O/'formal/GATES-COMPLETE.json');assert formal['actual_exit']==0 and formal['own_fixture_count']==6 and formal['author_fixture_count']==5
    for group,n in [('own-six',6),('author-five',5)]:
     r=read(O/'formal'/group/'RESULTS.json');assert len(r)==n and all(x['status']=='PASS'for x in r);assert read(O/'formal'/group/'ACTUAL-TERMINAL.json')['actual_exit']==0
    storage_counts={}
    for storage_root in (O/'formal/own-six',O/'own'):
     sm=read(storage_root/'STORAGE-MAP.json');assert sm['status']=='COMPLETE'and sm['uncommitted_records']==[]and len(sm['records'])==sm['logical_record_count']
     for ref in sm['records']:
      assert Path(ref['path']).is_relative_to(storage_root)and Path(ref['path']).stat().st_nlink==1;load_ref(ref)
     storage_counts[str(storage_root.relative_to(O))]=sm['logical_record_count']
    refs=read(O/'own/COMPLETE-INDEX.json');cases=read(C/'CURRENT-CASES.json');expected={x['case']for x in cases};assert len(refs)==len(cases)==17 and set(refs)==expected
    saved={r['logical_record']:r for r in read(C/'OWN-SAVED-MANIFEST.json')};rows=[];author={};own={};meta=[]
    base_ref=refs['company-base.raw.json'];base=load_ref(base_ref)
    for case in cases:
     key=case['case'];a=read(O/'author'/key/'RAW.json');e=read(C/case['canonical_saved']);equal(e,a);assert read(O/'author'/key/'CANONICAL-TYPED-EXACT.json')['match']is True
     author[key]=a;o=load_ref(refs[key]);own[key]=o;r=saved['current/'+key+'/RAW.json'];p=C/r['public_file'];raw=gzip.decompress(p.read_bytes());assert(p.stat().st_size,sha(p),len(raw),hashlib.sha256(raw).hexdigest())==(r['public_compressed_bytes'],r['public_compressed_sha256'],r['public_expanded_bytes'],r['public_expanded_sha256']);old=json.loads(raw);projected=copy.deepcopy(o)
     if key in ('company-holder_terminal_low.raw.json','company-holder_terminal_high.raw.json'):
      # Original saved stream ran previous before current; this exclusive default
      # runs current only. Three transport fields change, not cash/date/financial leaves.
      equal(o['same_base_source_raw'],base_ref)
      for field in ('sequence','logical_path','path'):
       oldv=old['same_base_source_raw'][field];newv=projected['same_base_source_raw'][field]
       if field=='logical_path':assert Path(newv)==O/'own/current/company-base.raw.json/RAW.json'and oldv=='current/company-base.raw.json/RAW.json'
       elif field=='path':assert Path(newv)==O/'own/current/company-base.raw.json/RAW.json.gz'and oldv=='current/company-base.raw.json/RAW.json.gz'
       else:assert type(oldv)is type(newv)is int and oldv>0 and newv>0
       meta.append({'case':key,'pointer':'/same_base_source_raw/'+field,'original':oldv,'fresh':newv,'reason':'validated fresh base transport reference only'})
       projected['same_base_source_raw'][field]=oldv
     equal(old,projected)
     assert o['metadata']['model_as_of']=='2026-11-03T00:00:00Z'and o['metadata']['valuation_date']=='2026-11-01'and o['metadata']['year_5_date']=='2031-11-01'
     rows.append({'case':key,'author_complete_typed_exact':True,'own_complete_typed_exact_except_precise_validated_transport':True,'fresh_author':str(O/'author'/key/'RAW.json'),'fresh_own':refs[key],'saved_own':r})
    # Entire adopted output's 17 complete primary/diagnostic raw bind to fresh author.
    whole=read(PUB/'2026-Q3-output.json')
    assert set(whole['primary'])|set(whole['diagnostics'])==expected and len(whole['primary'])==8 and len(whole['diagnostics'])==9
    for k,v in {**whole['primary'],**whole['diagnostics']}.items():equal(v,author[k])
    machine=read(C/'MACHINE-INPUTS.json');equal(machine['value_range'],whole['value_range']);equal(machine['return_model'],whole['return_model']);equal(machine['return_model']['base_case_distributions_per_share'],author['company-base.raw.json']['distributions_per_share'])
    for side in ('low','high'):equal(machine['return_model']['base_case_terminal_equity_value_range_per_share']['year_5'][side],author['company-holder_terminal_'+side+'.raw.json']['year5_terminal_equity_value_per_share']);equal(machine['value_range'][side],author['company-core_'+side+'.raw.json']['current_value_per_share'])
    for x in read(O/'SAME-BASE-COMPLETE.json'):assert all(x['checks'].values())
    assert all(read(O/'SAVED-CONSUMER-CONTROLS.json').values())
    counts=read(C/'SCOPE-COUNTS.json');assert sum(x['mapped_relationships']for x in t['pair_results'])==counts['direct_raw_relationships']+counts['input_policy_relationships']+counts['direct_saved_consumer_relationships']+counts['source_event_relationships']
    result={'status':'ACTUAL_FRESH_17_AUTHOR_17_OWN_FULL_OBJECT_AND_194_CONSUMER_QUALIFIED','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'formal_own':6,'formal_author':5,'all_fresh_storage_records_double_hash_JSON_reopened':storage_counts,'fresh_author':17,'fresh_own':17,'original_own_reference_metadata_projection':meta,'full_raw_rows':rows,'mapped_relationships':sum(x['mapped_relationships']for x in t['pair_results']),'differences_outside_frozen_budget':0,'direct_current_consumers':194,'original_economic_adoption_false_retained':True,'all_unpaired_outputs_retained':True,'same_base_exact':True,'finance_executed_by_this_checker':0,'historical_previous_17_not_fresh':True,'full_global_web_HTTP_cold':'DEFERRED','browser':'OPEN'}
    put(D/'FRESH-QUALIFICATION.json',result);print(json.dumps({k:v for k,v in result.items()if k not in ('full_raw_rows','original_own_reference_metadata_projection')}))
