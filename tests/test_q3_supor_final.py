"""Independent literal annual reconstruction; no production imports/constants.
Run: python independent_literal.py. All formulas/data below are literal research inputs.
"""
import json
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"research/companies/CN/002032/models"
def independent(case,k,g,extra=0,years_to_release=5,delay=0,capital=0,transfer_fee=0,margin=0,legacy_fee=0,remit_tax=0,oldcapacity=None):
    if case=='base': d=[16*1.025**i for i in range(5)];e=[7*1.02**i for i in range(5)];dm=[.095+margin]*5;em=[.047]*5;cx=.24;wc=[.06]*5;u=.9;receipt=.9;settles=[.15]*5;opts=True;roic=.25
    elif case=='structural': d=[14.5*.99**i for i in range(5)];e=[5.8*.97**i for i in range(5)];dm=[.07]*5;em=[.025]*5;cx=.28;wc=[.2,.15,.1,.1,.1];u=.65;receipt=.6;settles=[.6,.3,.3,.3,.3];opts=False;roic=.15
    elif case=='cycle': d=[14.8,15.5]+[16*1.025**i for i in range(2,5)];e=[6.2,6.5]+[7*1.02**i for i in range(2,5)];dm=[.088,.092,.095,.095,.095];em=[.035,.04,.047,.047,.047];cx=.24;wc=[.3,.15,-.15,.06,.06];u=.9;receipt=.65;settles=[.4,.15,.15,.15,.15];opts=True;roic=.25
    else: d=[16.2*1.04**i for i in range(5)];e=[7.3*1.04**i for i in range(5)];dm=[.1]*5;em=[.06]*5;cx=.30;wc=[.1]*5;u=.9;receipt=.95;settles=[.15]*5;opts=True;roic=.25
    p=.5;s=1.60142209873-.01786188461+.0004462727-.5+extra
    earnings=0;legal=1.093300754;reserve=.330789524;inter=2.451173958;owed=0
    shares=.796964626;reg=.799518446;paid=.796964626
    inc=[.00102317,.0010115,.0010345,.0005215,0]
    proceeds=[.000480780*36.49+.000542390*37.89,.000498500*37.89+.000513000*38.82,.000513000*38.82+.000521500*31.21,.000521500*31.21,0]
    rows=[];old_ability=(s+inter if oldcapacity is None else oldcapacity)-capital;deferred=[];helds=heldp=0
    for y in range(1,321):
        if y==6:
            helds=s-owed;heldp=p;earnings+=old_ability
        opening=p+s
        op=d[y-1]*dm[y-1]+e[y-1]*em[y-1] if y<=5 else (d[-1]*dm[-1]+e[-1]*em[-1])*(1+g)**(y-5)
        reinvest=cx-.16+wc[y-1] if y<=5 else op*g/roic
        begin=6+delay;finish=begin+years_to_release-1
        sf=helds/years_to_release*legacy_fee if begin<=y<=finish else 0
        pf=heldp/years_to_release*legacy_fee if begin<=y<=finish else 0
        profit=op+.02*opening-sf-pf;direct=op*.022+p*.02-pf;sourceprofit=profit-direct
        earnings+=sum(amount for due,amount in deferred if due==y)
        allocation=max(0,min(sourceprofit,earnings+sourceprofit))*(.1 if y<=10 else 0)
        deferred.append((y+10,allocation))
        earnings+=sourceprofit-allocation
        own_cf=direct-reinvest*.022;source_cf=profit-reinvest-own_cf
        shares+=inc[y-1] if y<=5 and opts else 0;paid+=inc[y-1] if y<=5 and opts else 0
        if y==1:reg=.796964626
        reg+=inc[y-1] if y<=5 and opts else 0
        issue=proceeds[y-1] if y<=5 and opts else 0
        repayment=min(inter,settles[y-1] if y<=5 else .15);inter-=repayment
        begin=6+delay;finish=begin+years_to_release-1
        fraction=1 if y<begin else max(0,(finish-y)/years_to_release)
        sfloor=helds*fraction if y>=6 else 0;pfloor=heldp*fraction if y>=6 else 0
        gross=capital if y==8 else 0
        capfee=gross*.02;captax=max(0,gross-.15)*.25
        bookout=.65416348354*gross/.610
        authority=max(0,s+source_cf+repayment-owed-gross-sfloor)
        if y<=5:declaration=max(0,min(u*max(0,sourceprofit-allocation),earnings,authority));fee=0
        else:declaration=max(0,min(earnings/(1+transfer_fee),authority/(1+transfer_fee)));fee=declaration*transfer_fee
        earnings-=declaration+fee
        tax=declaration*remit_tax if y>5 else 0;declaration-=tax
        cash=owed+receipt*declaration;owed=(1-receipt)*declaration
        p+=own_cf+cash+issue-repayment+gross-capfee-captax;s+=source_cf-cash+repayment-gross-fee-tax
        motherprofit=direct+declaration+gross-bookout-capfee-captax
        statutory=min(.1*max(0,min(motherprofit,legal+motherprofit)),max(0,reg*.5-reserve))
        reserve+=statutory;legal+=motherprofit-statutory
        dividend=max(0,min(.85*profit if y<=5 else p-pfloor,legal,p-pfloor,p+s))
        p-=dividend;legal-=dividend
        assert min(p,s)>=-1e-10
        assert abs(p+s-(opening+profit-reinvest+issue-dividend-capfee-captax-fee-tax))<1e-7
        rows.append(dict(year=y,parent_cash=p,subs_cash=s,source_earnings_budget=earnings,parent_ur=legal,parent_reserve=reserve,dividend=dividend,dps=dividend/shares,subs_declaration=declaration,upstream_receipt=cash,dividend_receivable=owed,intercompany_payable=inter,shares=shares,registered_capital=reg,paid_capital=paid))
    pv=sum(r['dps']/(1+k)**r['year'] for r in rows[:240]);tv=sum(r['dps']/(1+k)**(r['year']-5) for r in rows[5:240])
    return dict(pv=pv,tv=tv,rows=rows,convergence=sum(r['dps']/(1+k)**r['year'] for r in rows[240:]))


def test_supor_independent_full_paths():
 
 literal={}
 for case in ['base','cycle','structural','upside']:
  for i,(k,g) in enumerate([(.105,0),(.095,.005)] if case=='structural' else [(.095,.015),(.085,.02)]):literal[f'{case}/{i}']=independent(case,k,g)
 for name,args in [('governance_delay_3years',dict(delay=3)),('realization_8years',dict(years_to_release=8)),('conditional_shaoxing_capital_return',dict(capital=.2)),('tail_transfer_friction_2pct',dict(transfer_fee=.02)),('domestic_margin_minus_1pp',dict(margin=-.01)),('old_surplus_realization_friction_5pct',dict(legacy_fee=.05)),('old_surplus_realization_friction_15pct',dict(legacy_fee=.15)),('source_remittance_effective_tax_2pct',dict(remit_tax=.02)),('ordinary_old_capacity_3bn_delay3',dict(oldcapacity=3,delay=3)),('ordinary_old_capacity_2bn_delay3_release8',dict(oldcapacity=2,delay=3,years_to_release=8))]:
  for i,(k,g) in enumerate([(.095,.015),(.085,.02)]):literal[f'{name}/{i}']=independent('base',k,g,**args)
 import base64,gzip,hashlib
 transport=json.loads((P/'2026-Q3-output.json').read_text())
 if transport.get('wrapper_schema')=='trading-os-full-json-gzip-base64-v1':
  compressed=base64.b64decode(transport['full_payload_gzip_base64'],validate=True)
  assert hashlib.sha256(compressed).hexdigest()==transport['compressed_sha256']
  raw=gzip.decompress(compressed)
  assert len(raw)==transport['uncompressed_bytes'] and hashlib.sha256(raw).hexdigest()==transport['uncompressed_sha256']
  target=json.loads(raw)
 else:target=transport
 errors={};summary={}
 for key,v in literal.items():
  name,idx=key.split('/');idx=int(idx)
  t=(target['cases'][name] if name in target['cases'] else target['sensitivities'][name])['valuations'][idx]
  err=max(abs(v['pv']-t['current_per_share']),abs(v['tv']-t['terminal_per_share']))
  for a,b in zip(v['rows'],t['explicit_rows']+t['tail_rows']):err=max(err,*(abs(a[k]-b[k]) for k in a))
  assert err<1e-8,(key,err)
  errors[key]=err;summary[key]={k:v[k] for k in ['pv','tv','convergence']}

import runpy,subprocess,sys,copy,gzip,base64,hashlib
from functools import lru_cache
@lru_cache(None)
def model():return runpy.run_path(str(P/'2026-Q3.py'))
def test_supor_actual_function_boundaries():
 m=model();m['tests']()
 q=copy.deepcopy(m['BASE']);q['source_legacy_capacity']=0
 r=m['evaluate'](q,[(.095,.015),(.085,.02)]);assert r['status']!='feasible' and not r['valuations']
 cap=m['capital_return'](.2,.610,.65416348354,.15,.02,.25)
 assert abs(cap['parent_legal_gain']-(-.03097983066885246))<1e-8
 # Zero/legalcapacity is distinct from declaring the financial assets worthless.
 q=copy.deepcopy(m['BASE']);q['source_legacy_capacity']=2;q['realization_delay']=3;q['realization_years']=8
 r=m['evaluate'](q,[(.095,.015),(.085,.02)]);assert r['status']=='feasible'

def test_supor_all_future_principal_and_capacity():
 m=model();x=m['all_birth_years']();assert x['all_passed'] and not x['failures'];assert sum(v['tests'] for v in x['paths'].values())==3840
 for name,a in m['scenario_assumptions']().items():
  g=0 if name=='structural' else .015
  rows=m['forecast'](a,320,g,a['terminal_roic'])
  assert max(z['true_extra_cash'] for z in rows[10:])<1e-7
  assert all(z['normal_settlement_cash']>=0 for z in rows)

def test_supor_singlefile_full_expand(tmp_path):
 (tmp_path/'2026-Q3.py').write_bytes((P/'2026-Q3.py').read_bytes());subprocess.run([sys.executable,'-I',str(tmp_path/'2026-Q3.py')],cwd=tmp_path,check=True,stdout=subprocess.DEVNULL)
 assert (tmp_path/'2026-Q3-output.json').read_bytes()==(P/'2026-Q3-output.json').read_bytes()
 subprocess.run([sys.executable,'-I',str(tmp_path/'2026-Q3.py'),'--expand',str(tmp_path/'expanded.json')],cwd=tmp_path,check=True,stdout=subprocess.DEVNULL)
 assert hashlib.sha256((tmp_path/'expanded.json').read_bytes()).hexdigest()=='5f982d5046c6f89134bb347705794f909916c4b1860445f9b5e1d91e1bb828e9'
