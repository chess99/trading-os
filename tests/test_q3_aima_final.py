"""Independent literal-input reconstruction. Does not import/run production model or read its inputs.
Production JSON is read only after the independent paths and valuations are calculated.
"""
import json,pathlib,copy
D=pathlib.Path(__file__).resolve().parents[1]/"research/companies/CN/603529/models"
DEFAULT={'revs':[24000,26000,27500,28600,29700],'m':[.055,.061,.065,.066,.066],
 'invest':[2000,1500,1200,1100,1150],'da':[850,900,950,1000,1050],
 'shock':[300,0,0,0,0],'arrive':1.,'lag':3,'fee':.02,'realize':1.,'voluntary':0.,
 'r':.10,'g':.015,'roic':.12,'tm':.066,'limit':1500.,'repayment':[0,0,2200,0,970],
 'cash0':9286.,'pc0':1800.,'debt0':2970.,'eb0':5000.,'shares':863.320284,'registration':863.320284}
VARIANTS={
 'core_low':{},'core_high':{'r':.095,'g':.02,'roic':.15},
 'scenarios/cyclical':{'revs':[21500,22500,25500,28000,29700],'m':[.04,.045,.06,.065,.066],'shock':[1000,300,-300,-300,0],'invest':[2000,1400,1200,1100,1150],'arrive':.75,'lag':5},
 'scenarios/structural':{'revs':[22000,21500,21000,21000,21000],'m':[.035,.025,.025,.025,.025],'shock':[2000,1000,0,0,0],'invest':[2000,1200,950,950,950],'arrive':.65,'tm':.025,'g':0.,'roic':.08,'r':.11,'lag':5,'fee':.05},
 'scenarios/upside':{'revs':[25000,28000,30500,32500,34000],'m':[.06,.067,.07,.07,.07],'invest':[2200,1700,1500,1350,1350],'tm':.07,'g':.02,'roic':.15,'r':.095},
 'scenarios/liquidity_extreme':{'revs':[18000]*5,'m':[-.02]*5,'shock':[6500,1000,0,0,0],'arrive':.2,'limit':500.},
 'sensitivities/margin_minus_1pp':{'m':[.045,.051,.055,.056,.056],'tm':.056},
 'sensitivities/arrival_50pct':{'arrive':.5},
 'sensitivities/capex_plus_300':{'invest':[2300,1800,1500,1400,1450]},
 'sensitivities/tax_25pct':{'m':[.055*.75/.8,.061*.75/.8,.065*.75/.8,.066*.75/.8,.066*.75/.8],'tm':.066*.75/.8,'roic':.12*.75/.8},
 'sensitivities/release_lag_5':{'lag':5},'sensitivities/release_lag_1':{'lag':1},
 'sensitivities/realizability_80pct':{'realize':.8,'lag':5,'fee':.05},
 'sensitivities/voluntary_parent_10pct':{'voluntary':.1},
 'sensitivities/parent_cash_and_receipt':{'pc0':800.,'arrive':.5},
 'sensitivities/additional_restricted_500':{'cash0':8786.},
 'sensitivities/zero_source_opening_earnings_budget':{'eb0':0.}}
VARIANTS['scenarios/upside_full_conversion']=dict(VARIANTS['scenarios/upside'],repayment=[0,0,0,0,970],debt0=970.,shares=863.320284+1999.497/36.70,registration=863.320284+1999.497/36.70)
def rebuild(over):
 z=dict(DEFAULT);z.update(over)
 P=z['pc0'];B=z['cash0']-P;debt=z['debt0'];E=z['eb0'];L=1838.;R=433.946478;A=0.;used=0.;previous=22500.;need_old=2000.;K=7000.;pledge=5000.;disc=0.;timeline={};rows=[]
 for y in range(1,121):
  i=y-1;before=P+B
  if y<6:
   sales=z['revs'][i];op=sales*z['m'][i];deprec=z['da'][i];cap=z['invest'][i];wc=.03*(sales-previous)+z['shock'][i];need=2000.;cost=300.;pay=z['repayment'][i]
  else:
   sales=previous*(1+z['g']);op=sales*z['tm'];deprec=1050*(1+z['g'])**(y-5);need=2000*sales/z['revs'][4];cost=300*sales/z['revs'][4];pay=0.;wc=.03*(sales-previous);cap=deprec+op*z['g']/z['roic']-wc-need+need_old
  premium=200. if pay>=2200 else 0.;principal=min(debt,max(pay-premium,0.))
  cb=min(debt,2000.) if y<4 and z['repayment'][2]>=2200 else 0.
  coupon=30. if cb and y==1 else 36. if cb and y==2 else 0.
  fin=.015*before-.035*(debt-cb)-coupon;income=op+fin-premium
  E+=income+cost;free=income+deprec-cap-wc;B+=free+cost;P-=cost+principal;debt-=principal
  due=timeline.get(y-z['lag'],0.) if y>5 else 0.
  normal=min(max(0.,(income+cost)*.8),max(E,0.)*z['realize'],max(B-.8*need-A,0.))
  special_source=min(due,max(B-.8*need,0.),max(E-normal,0.)*z['realize']/(1+z['fee']),max(B-.8*need-A-normal,0.)/(1+z['fee']))
  expense=special_source*z['fee'];B-=expense;income-=expense;free-=expense;E-=expense
  announce=normal+special_source;E-=announce;A+=announce;transfer=A*z['arrive'];A-=transfer;B-=transfer;P+=transfer
  pprofit=announce-cost;eligible=max(0.,pprofit+min(L,0.));rs=min(eligible*.1,max(z['registration']/2-R,0.));ds=eligible*z['voluntary'] if y<=5 else 0.;R+=rs;disc+=ds;L+=pprofit-rs-ds
  shortP=max(.2*need-P,0.);shortB=max(.8*need-B,0.);borrow=min(shortP+shortB,max(z['limit']-used,0.));used+=borrow;debt+=borrow;allocate=min(borrow,shortP);P+=allocate;B+=borrow-allocate
  feasible=P>=.2*need-1e-7 and B>=.8*need-1e-7
  dividend=min(max(.5*income,0.),max(L,0.),max(P-.2*need,0.),max(P+B-need-debt,0.)) if feasible else 0.
  P-=dividend;L-=dividend
  extra=min(due,max(L,0.),max(P-.2*need,0.),max(P+B-need-debt,0.)) if feasible else 0.
  P-=extra;L-=extra;K+=cap-deprec+wc+need-need_old;pledge+=(sales-previous)*.22
  timeline[y]=max(P+B-need-debt,0.) if y>=5 else 0.
  rows.append(dict(year=y,revenue=sales,operating_common_profit=op,finance=fin,net_income=income,
   capex=cap,depreciation=deprec,working_capital_increase=wc,minimum_cash=need,
   restricted_collateral=pledge,fcf=free,source_earnings_budget=E,declared_normal=normal,
   declared_special=special_source,realization_fee=expense,declared=announce,received=transfer,
   upstream_receivable=A,parent_legal_retained=L,parent_statutory=R,parent_statutory_add=rs,
   parent_discretionary=disc,parent_cash=P,source_cash_budget=B,cash=P+B,debt=debt,new_debt=borrow,
   ordinary_dividend=dividend,special_dividend=extra,dividend=dividend+extra,
   dps=(dividend+extra)/z['shares'],capital=K,due_surplus_budget=due,post_distribution_surplus=timeline[y]))
  if not feasible:return {'feasible':False,'rows':rows,'value':None,'tv5':None}
  previous=sales;need_old=need
 r=z['r'];g=z['g'];end=rows[-1];res=sales*(1+g)*z['tm']*(1-g/z['roic'])/(r-g)+P+B-need-debt
 present=sum(row['dividend']/(1+r)**row['year'] for row in rows)+res/(1+r)**120
 future=sum(row['dividend']/(1+r)**(row['year']-5) for row in rows[5:])+res/(1+r)**115
 return dict(feasible=True,rows=rows,value=present/z['shares'],tv5=future/z['shares'])

def test_aima_independent_complete_paths():
 ind={k:rebuild(v) for k,v in VARIANTS.items()}
 production=json.loads((D/'2026-Q3-output.json').read_text());checks=[]
 for key,reconstruction in ind.items():
  prod=production
  for part in key.split('/'):prod=prod[part]
  assert reconstruction['feasible']==prod['path']['feasible']
  assert len(reconstruction['rows'])==len(prod['path']['rows'])
  largest=0.;count=0
  for expected,actual in zip(reconstruction['rows'],prod['path']['rows']):
   for k,v in expected.items():
    delta=abs(v-actual[k]);largest=max(largest,delta);count+=1
    assert delta<1e-6,(key,k,expected['year'],v,actual[k])
  if reconstruction['value'] is not None:
   assert abs(reconstruction['value']-prod['valuation']['value_per_share'])<1e-8
   assert abs(reconstruction['tv5']-prod['valuation']['terminal_year5_per_share'])<1e-8
  checks.append(dict(case=key,compared_fields=count,max_abs_difference=largest,value=reconstruction['value'],tv5=reconstruction['tv5'],feasible=reconstruction['feasible']))

import runpy,subprocess,sys
from functools import lru_cache
@lru_cache(None)
def model():return runpy.run_path(str(D/'2026-Q3.py'))
def test_aima_actual_functions():
 m=model()
 assert m['legal_close'](0,5,20,10)['statutory_add']==1
 assert m['legal_close'](-6,0,20,10)['statutory_add']==.4
 assert m['legal_close'](5,10,20,-8)['retained']==-3
 for args in [(10,20,40,1,20),(0,10,0,11,10)]:
  a=m['dispose'](*args);assert not a['feasible'] and a['distributable'] is None and a['unpaid_claims']>0
 q=m['capital_reduction'](20,10,20,100,20,external_debt=5,cost=1);assert q['cash']==9 and q['profit']==-1 and q['shares']==50
 q=m['capital_reduction'](10,10,20,100,20,external_debt=5,cost=1);assert not q['feasible'] and q['shares']==100
 q=m['capital_reduction'](10,0,0,100,0);assert not q['feasible']

def test_aima_full_future_economic_principal():
 m=model()
 cases={'base':({},None,m['S']),'core_high':({'r':.095,'g':.02,'roic':.15},None,m['S']),'zero_growth':({'g':0},None,m['S'])}
 for k,v in (m['SCENARIOS']|m['SENSITIVITIES']).items():cases[k]=(v,None,m['S'])
 cases['full_conversion']=(dict(m['SCENARIOS']['upside'],repay=[0,0,0,0,970]),dict(m['I'],debt=970,parent_registered=m['S']+1999.497/36.7),m['S']+1999.497/36.7)
 cases['parent_cash_and_receipt']=({'arrival':.5},dict(m['I'],parent_cash=800),m['S'])
 cases['additional_restricted_500']=({},dict(m['I'],cash=8786),m['S'])
 cases['zero_source_opening_earnings_budget']=({},dict(m['I'],source_earnings_budget=0),m['S'])
 output=[]
 for name,(cfg,init,shares) in cases.items():
  for fy in [.015,0]:
   p=dict(cfg,financial_yield=fy);a=m['case'](p,init,shares,years=320)
   if not a['path']['feasible']:output.append(dict(name=name,financial_yield=fy,feasible=False,failure_year=a['path']['failure_year']));continue
   ar=a['path']['rows'];r=a['inputs']['r']
   for y in [12,78,200]:
    for amount in [1,100,1000]:
     b=m['case'](dict(p,cash_pulse_year=y,cash_pulse=amount),init,shares,years=320);br=b['path']['rows']
     if not b['path']['feasible']: output.append(dict(name=name,financial_yield=fy,y=y,amount=amount,feasible=False));continue
     delta=lambda key,t:sum(v[key]-u[key] for u,v in zip(ar[y-1:t],br[y-1:t]))
     at=lambda key,t:br[t-1][key]-ar[t-1][key]
     pv=sum((v['dividend']-u['dividend'])/(1+r)**(u['year']-y) for u,v in zip(ar,br))
     rec=dict(name=name,financial_yield=fy,y=y,amount=amount,pv_at_pulse=pv,base_value=a['valuation']['value_per_share'],base_final_cash=ar[-1]['cash'],base_final_minimum=ar[-1]['minimum_cash'],base_final_surplus=ar[-1]['post_distribution_surplus'])
     rec['horizons']={str(t):dict(D=delta('dividend',t),finance=delta('finance',t),fee=delta('realization_fee',t),cash=at('cash',t),debt=at('debt',t),ar=at('upstream_receivable',t),balance=amount+delta('finance',t)-delta('realization_fee',t)-delta('dividend',t)+at('debt',t)-at('cash',t)) for t in [y+29,y+60,320]}
     rec['cash_delta_minmax']=[min(v['cash']-u['cash'] for u,v in zip(ar[y-1:],br[y-1:])),max(v['cash']-u['cash'] for u,v in zip(ar[y-1:],br[y-1:]))]
     output.append(rec)
 
 valid=[x for x in output if 'pv_at_pulse' in x]
 assert len(valid)==324
 for x in valid:
  assert x['pv_at_pulse']>0
  assert max(abs(v['balance']) for v in x['horizons'].values())<1e-6
 for name in cases:
  for fy in [.015,0]:
   for y in [12,78,200]:
    z=sorted([x for x in valid if x['name']==name and x['financial_yield']==fy and x['y']==y],key=lambda x:x['amount'])
    assert all(b['pv_at_pulse']>a['pv_at_pulse'] for a,b in zip(z,z[1:]))
 for name,net in [('zero_growth',100/1.02),('structural',100/1.05)]:
  x=next(x for x in valid if x['name']==name and x['financial_yield']==0 and x['y']==12 and x['amount']==100)
  assert abs(x['horizons']['320']['cash'])<1e-7
  assert abs(x['horizons']['320']['D']-net)<1e-6

def test_aima_standalone_byte_equal(tmp_path):
 (tmp_path/'2026-Q3.py').write_bytes((D/'2026-Q3.py').read_bytes())
 subprocess.run([sys.executable,'-I',str(tmp_path/'2026-Q3.py')],cwd=tmp_path,check=True,stdout=subprocess.DEVNULL)
 assert (tmp_path/'2026-Q3-output.json').read_bytes()==(D/'2026-Q3-output.json').read_bytes()
