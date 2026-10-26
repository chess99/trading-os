# Historical full-trace comparisons retain exact canonical equality via frozen
# SHA256 references for all 24 endpoint/horizon runs and the default run.
# This replaces only loading duplicate historical model/output artifacts;
# all production economic, full-path and independent-literal assertions remain.
"""Portable full-path audit; all artifacts relative to this file, no repository writes."""
import json,importlib.util,hashlib,subprocess,sys,tempfile,shutil,copy
from pathlib import Path
D=Path(__file__).resolve().parent
def module(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
m=module(D/'2026-Q3.py','production')
reference=json.loads((D/'historical-reference.json').read_text())
def canonical(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'))
def trace_digest(x):return hashlib.sha256(canonical(x).encode()).hexdigest()
o=m.expand_traces(json.loads((D/'2026-Q3-output.json').read_text()))
def paths(x):
 z={f'{k}@{i}':a for k,v in x['scenarios'].items() for i,a in enumerate(v)}
 z.update({k:v for k,v in x['sensitivity'].items() if 'annual_trace' in v});return z
impact={};differences=[]
for k,n in paths(o).items():
 for z in n['annual_trace']:
  assert abs(z['group_cash_conservation_error'])<1e-7
  assert abs(z['dps']-(z['P']['distribution']+z['P']['capital_payment'])/z['pre_cancel_shares']*z['pre_cancel_holder_factor'])<1e-10
  assert z['P']['debt']<=100+1e-8 and z['P']['cash']>=z['P']['minimum']-1e-7
  assert z['shares']>=100-1e-7
  if z['P']['capital_payment']>1e-8:
   assert z['P']['cash']>=z['P']['creditor_cash_protection_for_capital_action']-1e-7
   assert z['P']['capital_reduction_fee']>0
   assert abs(z['holder_share_factor']/z['pre_cancel_holder_factor']-z['shares']/z['pre_cancel_shares'])<1e-12
  if z['L']['continuing_parent_rights_after_exit_budget']==0:assert z['L']['cash']==0 and z['L']['debt']==0
# Actual production function, source sums independently typed, not merely reading output.
net=sum([16.46805266,11.13009779,6.42775631,14.85441390-.35618504,2.82887070,105.02844406,20.59768442,24.84393786])-sum([54.12300168,57.38578862,56.43644598,.91897749,5.31752236])
assert abs(net-m.OPENING_NOA)<1e-12
assert abs(m.initial()['P']['wc']-(-1488.547204+net))<1e-10
# Same future budget, same financial bridge, isolates only opening funding.
assert canonical(m.BRIDGE)==canonical(reference['BRIDGE']) and canonical(m.SCENARIOS)==canonical(reference['SCENARIOS']) and canonical(m.TOTAL)==canonical(reference['TOTAL'])
assert trace_digest(m.run(opening_noa=m.NORMALIZED_OPENING_NOA))==reference['default_trace_sha256']
mid=o['base_annual_trace'];oldmid=reference['base_annual_trace_first5'];fund=m.NORMALIZED_OPENING_NOA-net
assert abs(mid[0]['P']['delta_wc']-oldmid[0]['P']['delta_wc']-fund)<1e-10
assert mid[0]['dps']==oldmid[0]['dps']
assert all(n['dps']<a['dps'] for n,a in zip(mid[1:5],oldmid[1:5]))
# All8 endpoints at 80/120/160, every opening bound, every year and finite residual.
long=[]
for name,ends in o['scenarios'].items():
 for ix,p in enumerate(ends):
  for label,start in [('matched',net),('frozen',m.NORMALIZED_OPENING_NOA),('legacy_credit',net+11.20442737),('receivables_excluded',net-14.49822886)]:
   for horizon in (80,120,160):
    rr=m.run(name,stable=p['g'],max_year=horizon,opening_noa=start)
    assert max(abs(z['group_cash_conservation_error']) for z in rr)<1e-7
    if label=='frozen': assert trace_digest(rr)==reference['traces'][f'{name}@{ix}:{horizon}']
    z=rr[-1]
    assert z['S']['cash']<=20+1e-8
    long.append({'path':f'{name}@{ix}','opening':label,'horizon':horizon,'PV':m.pv(rr,p['r'],p['g'])['value'],'TV5':m.pv(rr,p['r'],p['g'],5)['value'],'last_P_cash':z['P']['cash'],'last_P_creditor_floor':z['P']['creditor_cash_protection_for_capital_action'],'last_S_cash':z['S']['cash'],'last_L_cash':z['L']['cash'],'annual_trace':rr})
# Store all state evidence without deleting fields; SHA verifies both codecs and full payload.
full={'impact':impact,'annual_differences':differences,'all_endpoints_opening_bounds_convergence':long}
packed=m.pack_traces(full);raw=json.dumps(full,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode();packed['_lossless_manifest']={'schema':'complete audit payload; annual_trace gzip only','canonical_full_sha256':hashlib.sha256(raw).hexdigest(),'canonical_bytes':len(raw)}
assert m.expand_traces(packed)==dict(full,_lossless_manifest=packed['_lossless_manifest'])
(D/'opening-impact.json').write_text(json.dumps(packed,ensure_ascii=False,indent=2)+'\n')
with tempfile.TemporaryDirectory() as td:
 t=Path(td);shutil.copy2(D/'2026-Q3.py',t/'2026-Q3.py');subprocess.run([sys.executable,str(t/'2026-Q3.py')],check=True,stdout=subprocess.DEVNULL)
 assert (t/'2026-Q3-output.json').read_bytes()==(D/'2026-Q3-output.json').read_bytes()
 expanded=json.loads(subprocess.run([sys.executable,str(t/'2026-Q3.py'),'--expand'],check=True,capture_output=True).stdout)
 assert expanded==o
check={'fresh_generation_bytes_equal':True,'full_payload_hash_verified':True,'all_existing_paths_checked':len(paths(o)),'opening_endpoint_convergence_paths':len(long),'scope':'candidate only; all six roots checked; coordinator acceptance pending','frozen_sha256':reference['baseline_output_sha256'],'new_sha256':hashlib.sha256((D/'2026-Q3-output.json').read_bytes()).hexdigest(),'funding':fund,'core_old':reference['core_old'],'core_new':[(v['current'],v['year5'])for v in o['scenarios']['base']],'D5_old':[z['dps']for z in oldmid[:5]],'D5_new':[z['dps']for z in mid[:5]],'mid_PV_old':reference['mid_PV_old'],'mid_PV_new':m.pv(mid,.1,.025)['value']}
(D/'validation.json').write_text(json.dumps(check,indent=2)+'\n');print(json.dumps(check,indent=2))
