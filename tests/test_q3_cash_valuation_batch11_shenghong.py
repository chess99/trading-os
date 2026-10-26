"""Independent ledger rebuild from original parameters; never consumes official traces as input.
No simulate/annual_business/value/legal_add/payment call from the valuation module.
"""
import copy,json
from pathlib import Path
root=Path(__file__).resolve().parents[1]/'research/companies/CN/300693/models'
# Independently re-entered literal research assumptions and statement anchors.
# No reads/imports of the valuation source or its parameter object occur here.
# Statement anchors: Q3 cash/debt/book, H1 term deposits and internal balances;
# forecasts: report.md operating/capital/legal budget, reproduced explicitly below.
params = {
 'revenue0': [1050.0, 1040.0, 1670.0, 270.0, 90.0],
 'growth5': [
  [0.22, 0.20, 0.12, 0.06, 0.05],
  [0.18, 0.17, 0.10, 0.06, 0.04],
  [0.15, 0.14, 0.09, 0.05, 0.04],
  [0.12, 0.12, 0.08, 0.05, 0.03],
  [0.10, 0.10, 0.07, 0.04, 0.03]],
 'gross5': [
  [0.59, 0.34, 0.30, 0.31, 0.30],
  [0.58, 0.335, 0.295, 0.31, 0.30],
  [0.57, 0.33, 0.29, 0.31, 0.30],
  [0.56, 0.325, 0.285, 0.31, 0.30],
  [0.55, 0.32, 0.28, 0.31, 0.30]],
 'gross_mature': [0.50, 0.27, 0.25, 0.28, 0.28],
 'opex5': [0.245, 0.241, 0.238, 0.235, 0.232], 'opex_mature': 0.225,
 'tax': 0.15,'rates':[.15,.25,.25,.25,.25,.25,.25],'tax_loss_years':5,'mother_preferential_until':None, 'wc_ratio': 0.14, 'wc0': 400.0, 'fixed0': 820.0,
 'depreciation_ratio': 0.025, 'capex_ratio': 0.035,
 'committed_capex': [80.0, 40.0, 0.0, 0.0, 0.0],
 'long_g': 0.02, 'fade_end': 15, 'capital_allocation_fade_end': 15,
 'cash0': [422.50624451, 25.0, 20.0, 15.0, 10.0, 10.0, 12.0],
 'term0': [610.0, 0.0, 0.0, 0.0, 0.0, 28.88201449, 0.0], 'maturity_year': 3,
 'debt0': [100.06944556, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], 'lease0': 12.34619662,
 'legal0': [1600.0, 3.0, -21.6641, -23.2001, -1.2582, 0.0, -36.0],
 'reserve0': [210.59477448, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0],
 'capital0': [312.795823, 5.0, 180.0, 50.0, 5.0, 60.0, 50.0],
 'loan0': [142.00445104, 158.00074483, 0.0, 31.83073359, 111.0, 0.0],
 'cash_floor_weights': [0.72, 0.05, 0.06, 0.045, 0.025, 0.075, 0.025],
 'cash_floor_ratio': 0.10, 'reinvest_weights': [0.60, 0.05, 0.10, 0.08, 0.02, 0.14, 0.01],
 'subs_profit5': [
  [0.005, -0.003, -0.025, 0.015, -0.010, -0.002],
  [0.008, 0.002, -0.012, 0.018, -0.005, 0.0],
  [0.012, 0.010, 0.0, 0.020, 0.005, 0.003],
  [0.016, 0.018, 0.020, 0.023, 0.020, 0.006],
  [0.020, 0.025, 0.040, 0.025, 0.030, 0.010]],
 'subs_profit_mature': [0.02, 0.025, 0.04, 0.025, 0.03, 0.01],
 'ownership': [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.5],
 'deposit_yield': 0.018, 'debt_rate': 0.04, 'loan_rate': 0.03,
 'loan_limit_additional': 500.0, 'external_limit': 320.0, 'equity_support_limit': 250.0,
 'payout5': 0.45, 'special_start': 3,
 'new_shares': [0.84864, 0.84864, 1.13152, 0.0, 0.0], 'initial_shares': 312.042673,
 'sbc_path': [25.0, 14.0, 5.76330317, 0.0, 0.0], 'grant_price': 31.06,
 'book0': 2290.14471334, 'margin_shock': 0.0, 'shock_start': 1,
 'cash_parent_shift': 0.0, 'maturity_haircut': 0.0
}
def rebuild(p,N=240):
 c=p['cash0'][:];td=p['term0'][:];d=p['debt0'][:];re=p['legal0'][:];sr=p['reserve0'][:];cap=p['capital0'][:];lo=p['loan0'][:]
 rev=p['revenue0'][:];wc=p['wc0'];fa=p['fixed0'];sh=p['initial_shares'];book=p['book0'];pending=[0.]*6;cashraised=0.;equity=0.;dps_cum=0.;out=[];fa_ratio=.2
 taxloss=[[] for _ in range(7)];foreign=51.91445336;investbasis={5:53.43073375,6:16.10284915}
 c[0]-=p['cash_parent_shift'];c[1]+=p['cash_parent_shift']
 def add(i,income):
  old=re[i];re[i]+=income
  v=max(re[i]-max(old,0),0)*.1 if i==0 and t<=15 else min(max(re[i]-max(old,0),0)*.1,max(cap[i]*.5-sr[i],0));re[i]-=v;sr[i]+=v
 for t in range(1,N+1):
  if t<=5: gg=p['growth5'][t-1];gm=p['gross5'][t-1];ox=p['opex5'][t-1]
  else:
   f=min((t-5)/(p['fade_end']-5),1)
   gg=[(1-f)*g+f*p['long_g'] for g in p['growth5'][4]]
   gm=[(1-f)*g+f*h for g,h in zip(p['gross5'][4],p['gross_mature'])]
   ox=(1-f)*p['opex5'][4]+f*p['opex_mature']
  oldsales=sum(rev);rev=[x*(1+g) for x,g in zip(rev,gg)];sales=sum(rev)
  before_sbc=sum(x*(m+(p['margin_shock'] if t>=p['shock_start'] else 0)) for x,m in zip(rev,gm))-sales*ox
  sbc=p['sbc_path'][t-1] if t<=5 else 0.
  np=(before_sbc*(1-p['tax']) if before_sbc>0 else before_sbc)-sbc
  nextwc=sales*p['wc_ratio'];dep=sales*p['depreciation_ratio'];cp=sales*p['capex_ratio']+p['committed_capex'][t-1] if t<=5 else dep+max(sales-oldsales,0)*fa_ratio
  ri=cp-dep+nextwc-wc;wc=nextwc;fa+=cp-dep
  if t==5:fa_ratio=fa/sales
  fxtax=fxfee=0.
  mother_rate=.25 if p.get('mother_preferential_until') is not None and t>p['mother_preferential_until'] else .15
  if foreign>0:
   if t>=p.get('foreign_release_year',3):fxfee=foreign*.01;foreign=0.
   else:fxtax=foreign*.018*(.25-mother_rate);foreign*=1.0135
  fl=[sales*p['cash_floor_ratio']*w for w in p['cash_floor_weights']];fl[0]+=foreign
  if t==p.get('conversion_year',0):
   remaining=p.get('conversion_limit',0)
   for i in [5,2,3,1,4]:
    cv=min(remaining,lo[i-1]);lo[i-1]-=cv;cap[i]+=cv;remaining-=cv
    if i in investbasis:investbasis[i]+=cv
  li=[x*p['loan_rate'] for x in lo]
  weights=p['subs_profit5'][t-1] if t<=5 else p['subs_profit_mature'];weights=[1-sum(weights)]+weights
  rates=p['rates'][:]
  if p.get('mother_preferential_until') is not None and t>p['mother_preferential_until']:rates[0]=.25
  nps=[];interest=[];cost=[];parenttax=0.;shield=[];taxes=[];taxloss_used=[]
  for i in range(7):
   taxloss[i]=[z for z in taxloss[i] if z[0]>=t];available=sum(z[1] for z in taxloss[i])
   operating=before_sbc*weights[i];deposit=(c[i]+td[i])*p['deposit_yield'];debtcost=d[i]*p['debt_rate']
   ownbase=operating+deposit-debtcost;finalbase=ownbase+(sum(li) if i==0 else -li[i-1])
   t0=max(operating-available,0)*rates[i];t1=max(operating+deposit-available,0)*rates[i];t2=max(ownbase-available,0)*rates[i];t3=max(finalbase-available,0)*rates[i]
   nps.append(operating-t0-(sbc if i==0 else 0));interest.append(deposit-t1+t0);cost.append(debtcost-t1+t2)
   if i==0:parenttax=t3-t2
   else:shield.append(t2-t3)
   taxes.append(t3);used=min(max(finalbase,0),available);taxloss_used.append(used)
   for bucket in taxloss[i]:
    take=min(used,bucket[1]);bucket[1]-=take;used-=take
   taxloss[i]=[z for z in taxloss[i] if z[1]>1e-10]
   if finalbase<0 and p['tax_loss_years']>0:taxloss[i].append([t+p['tax_loss_years'],-finalbase])
  interest[0]-=fxtax
  np=sum(nps)
  assetcash=[0.]*7;assetincome=[0.]*7
  if t==10:
   for i,bv,tb,dtl in [(0,22.0744,20.26747658,.27103851)]:
    proceeds=bv*.8*.97;tax=max(proceeds-tb,0)*rates[i]
    assetcash[i]=proceeds-tax;assetincome[i]=proceeds-tax-bv+dtl
  own=[a+b-c for a,b,c in zip(nps,interest,cost)];own[0]+=sum(li)-parenttax-fxfee
  for i in range(1,7):own[i]-=li[i-1]-shield[i-1]
  for i in range(7):own[i]+=assetincome[i]
  f=min(max((t-5)/(p['capital_allocation_fade_end']-5),0),1);wfuture=[1-sum(p['subs_profit_mature'])]+p['subs_profit_mature'];wi=[a*(1-f)+b*f for a,b in zip(p['reinvest_weights'],wfuture)]
  for i in range(7):c[i]+=nps[i]-ri*wi[i]+interest[i]-cost[i]
  c[0]+=sbc-parenttax-fxfee
  for i in range(1,7):c[i]+=shield[i-1]
  for i in range(7):c[i]+=assetcash[i]
  for i in range(1,7):c[i]-=pending[i-1];c[0]+=pending[i-1]
  pending=[0.]*6;mature=0.
  if t==p['maturity_year']:
   for i in range(7):c[i]+=td[i]*(1-p['maturity_haircut']);own[i]-=td[i]*p['maturity_haircut'];mature+=td[i]*(1-p['maturity_haircut']);td[i]=0
  repay=d[:] if t in (1,3) else [0.]*7
  if t==1:c[0]-=p['lease0']
  test=576 if t==1 else out[-1]['profit']+out[-1]['sbc']
  targets=[561.62,673.94,808.73];minimum=[514.82,566.30,622.93]
  fraction=(1 if test>=targets[t-1] else .6 if test>=minimum[t-1] else 0) if t<=3 else 0
  new=p['new_shares'][t-1]*fraction if t<=5 else 0;amount=new*max(p['grant_price']-dps_cum,0);sh+=new;cap[0]+=new;c[0]+=amount
  for i in range(1,7):
   need=max(fl[i]+repay[i]+li[i-1]-c[i],0)
   draw=min(max(need+fl[0]+repay[0]-c[0],0),max(p['external_limit']-cashraised,0));c[0]+=draw;d[0]+=draw;cashraised+=draw
   lend=min(need,max(min(sum(p['loan0'])+p['loan_limit_additional']-sum(lo),c[0]-fl[0]-repay[0]),0));c[0]-=lend;c[i]+=lend;lo[i-1]+=lend
   more=max(fl[i]+repay[i]+li[i-1]-c[i],0)
   eq=min(more,max(p['equity_support_limit']-equity,0),max(c[0]-fl[0]-repay[0],0)) if p['ownership'][i]==1 else 0
   c[0]-=eq;c[i]+=eq;cap[i]+=eq;equity+=eq
   if i in investbasis:investbasis[i]+=eq
   assert c[i]>=fl[i]+repay[i]+li[i-1]-1e-6
   c[i]-=li[i-1];c[0]+=li[i-1]
  for i in range(7):
   draw=min(max(fl[i]+repay[i]-c[i],0),max(p['external_limit']-cashraised,0) if i==0 else 0);c[i]+=draw;d[i]+=draw;cashraised+=draw
   assert c[i]>=fl[i]+repay[i]-1e-6;c[i]-=repay[i];d[i]-=repay[i]
  for i in range(1,7):
   pay=min(max(c[i]-fl[i],0),lo[i-1]);c[i]-=pay;c[0]+=pay;lo[i-1]-=pay
  if p.get('finite_sub_capital_enabled',False) and t>=20:
   for i in [5,6]:
    if lo[i-1]>1e-8:continue
    post=re[i]+own[i];prov=min(max(post-max(re[i],0),0)*.1,max(cap[i]*.5-sr[i],0));available=max(c[i]-fl[i]-max(post-prov,0),0)
    nav=cap[i]+sr[i]+re[i]+own[i];gross=min(available/1.01,max(nav,0)*.25,10.)
    if gross<.01 or nav<=0 or cap[i]<=.01:continue
    frac=gross/nav;face=cap[i]*frac;fee=gross*.01;receipt=gross*p['ownership'][i];costbasis=investbasis[i]*frac;cash_tax=receipt*rates[0]
    c[i]-=gross+fee;c[0]+=receipt-cash_tax;cap[i]-=face;re[i]-=gross-face;own[i]-=fee;own[0]-=cash_tax
    add(0,receipt-costbasis);investbasis[i]-=costbasis
  for i in range(7):add(i,own[i])
  for i in range(1,7):
   div=min(max(re[i],0),max(c[i]-fl[i],0))*(.45 if t<=5 else 1)
   pending[i-1]=div*p['ownership'][i];c[i]-=div-pending[i-1];re[i]-=div
  add(0,sum(pending));profit=sum(own)-own[-1]*.5
  ordinary=min(max(profit,0)*(p['payout5'] if t<=5 else 1),max(re[0],0),max(c[0]-fl[0],0));c[0]-=ordinary;re[0]-=ordinary
  extra=min(mature if t<=5 else max(c[0]-fl[0],0),max(re[0],0),max(c[0]-fl[0],0)) if t>=p['special_start'] else 0;c[0]-=extra;re[0]-=extra
  div=ordinary+extra;per=div/sh;dps_cum+=per;book+=profit+sbc+amount-div
  out.append({'year':t,'taxes':taxes,'taxloss_used':taxloss_used,'profit':profit,'sbc':sbc,'cash':c[:],'legal':re[:],'loans':lo[:],'shares':sh,'dps':per,'book':book,'revenue':rev[:],'vesting_fraction':fraction,'operating_profit':nps[:],'reinvestment':ri,'investment_weights':wi[:],'floors':fl[:],'nopat':np})
 return out

import runpy
from functools import lru_cache
@lru_cache(None)
def model():
 return runpy.run_path(str(root/'2026-Q3.py'))

def test_shenghong_literal_eight_full_paths_and_auxiliary():
    res={}
    official=model()['expand_output'](json.loads((root/'2026-Q3-output.json').read_text()))
    for name,change in [('base',{}),('margin_minus_2pp',{'margin_shock':-.02,'shock_start':2}),('wc_plus_5pp',{'wc_ratio':.19}),('mother_tax25_from_Y1',{'mother_preferential_until':0}),('mother_tax25_from_Y4',{'mother_preferential_until':3}),('no_generated_tax_loss_credit',{'tax_loss_years':0})]+[(name,{'wc_ratio':.20,'foreign_release_year':1,'opex_mature':.235,'conversion_year':3,'conversion_limit':250.,'growth5':[[.08,.02,.02,-.05,.02],[.06,.02,.02,0.,.02],[.05,.02,.02,.02,.02],[.04,.02,.02,.02,.02],[.03,.02,.02,.02,.02]],'gross5':[[.51,.25,.23,.27,.28]]*5,'gross_mature':[.47,.23,.22,.26,.27],'opex5':[.245,.242,.24,.238,.235],'capex_ratio':.03,'long_g':g,'finite_sub_capital_enabled':g==0}) for name,g in [('structural_adverse',.02),('structural_zero_growth',0.)]]:
     p=copy.deepcopy(params);p.update(change)
     for iteration in range(6):
      interim=rebuild(p,5);vf=[a['vesting_fraction'] for a in interim[:3]]
      remaining=60.43504953*sum(a*b for a,b in zip([.3,.3,.4],vf))-15.67174636
      shape=[25.,14.,5.76330317];new=[remaining*w/sum(shape) for w in shape]+[0.,0.]
      if max(abs(a-b) for a,b in zip(new,p['sbc_path']))<1e-10:break
      p['sbc_path']=new
     rows=rebuild(p)
     maxerr=0
     for a,b in zip(rows,official['scenarios'][name]['rows']):
      for x,y in zip(a['cash']+a['legal']+a['loans']+a['taxes']+[a['dps'],a['shares']],b['cash']+b['legal']+b['internal_loans']+b['entity_tax_details']['entity_cash_taxes']+[b['distribution_per_share'],b['shares']]):maxerr=max(maxerr,abs(x-y))
     assert maxerr<1e-6
     res[name]={'annual_rows_compared':len(rows),'max_ledger_abs_difference':maxerr,'endpoints':{}}
     for label,r in [('low',.11),('high',.10)]:
      v=sum(a['dps']/(1+r)**a['year'] for a in rows);tv=sum(a['dps']/(1+r)**(a['year']-5) for a in rows if a['year']>5)
      expected=official['scenarios'][name][label];assert abs(v-expected['per_share'])<1e-9 and abs(tv-expected['year5_terminal_per_share'])<1e-9
      res[name]['endpoints'][label]={'value':v,'tv5':tv,'value_difference':v-expected['per_share'],'tv5_difference':tv-expected['year5_terminal_per_share']}
    p=copy.deepcopy(params)
    for iteration in range(6):
     interim=rebuild(p,5);vf=[a['vesting_fraction'] for a in interim[:3]]
     rem=60.43504953*sum(a*b for a,b in zip([.3,.3,.4],vf))-15.67174636
     shape=[25.,14.,5.76330317];new=[rem*w/sum(shape) for w in shape]+[0.,0.]
     if max(abs(a-b) for a,b in zip(new,p['sbc_path']))<1e-10:break
     p['sbc_path']=new
    p.update(fade_end=6,capital_allocation_fade_end=6,gross_mature=[.52,.29,.26,.29,.29],opex_mature=.23)
    rows=rebuild(p);a,z=rows[4:6]
    cap=sum((z['operating_profit'][i]-z['reinvestment']*z['investment_weights'][i]-(z['floors'][i]-a['floors'][i])+a['floors'][i]*.018*(1-[.15,.25,.25,.25,.25,.25,.25][i]))*p['ownership'][i] for i in range(7))/z['shares']
    res['independent_earnings_power']={}
    for label,r in [('low',.11),('high',.10)]:
     op=cap/(r-.02);bridge=sum((q['dps']-cap*1.02**(q['year']-6))/(1+r)**(q['year']-5) for q in rows[5:]);near=sum(q['dps']/(1+r)**q['year'] for q in rows[:5]);v=near+(op+bridge)/(1+r)**5
     assert abs(v-official['earnings_power_crosscheck']['method_results'][label]['per_share'])<1e-9
     res['independent_earnings_power'][label]={'per_share':v,'tv5':op+bridge,'operating':op,'legal_financial_bridge':bridge,'value_difference':v-official['earnings_power_crosscheck']['method_results'][label]['per_share']}

def test_shenghong_production_function_handcases():
 m=model();m['self_tests']();p=copy.deepcopy(m['P']);z=[0.]*7
 q=m['entity_tax_bridge']([0,100,-10,0,0,0,0],0,z,z,z,[100,0,0,0,0,0],p,1,[[] for _ in range(7)])
 assert abs(q['entity_cash_taxes'][0]-.45)<1e-12
 assert abs(q['entity_cash_taxes'][1]-24.25)<1e-12
 assert q['operating_profits'][2]==-10 and q['entity_cash_taxes'][2]==0
 loss=[[] for _ in range(7)];loss[2]=[[6,10.]]
 q=m['entity_tax_bridge']([0,8,8,0,0,0,0],0,z,z,z,[0.]*6,p,2,loss)
 assert q['entity_cash_taxes'][1]==2 and q['entity_cash_taxes'][2]==0
 q=m['entity_tax_bridge']([0,0,10,0,0,0,0],0,z,z,z,[0.]*6,p,7,loss)
 assert q['entity_cash_taxes'][2]==2.5
 p['mother_preferential_until']=0
 q=m['entity_tax_bridge']([0,100,-10,0,0,0,0],0,z,z,z,[100,0,0,0,0,0],p,1,[[] for _ in range(7)])
 assert abs(q['internal_parent_tax']-.75)<1e-12

def test_shenghong_actual_finite_capital_and_minority():
 m=model();a=m['finite_capital_budget'](30,10,0,5,20,0,.5,8,.15,10,.01)
 for k,v in {'gross':6.25,'face':5.,'parent':3.125,'minority':3.125,'basis':2.,'tax':.46875,'fee':.0625,'mother_gain':1.125,'sub_capital_premium_charge':1.25}.items():assert abs(a[k]-v)<1e-10
 assert m['finite_capital_budget'](10,10,0,5,20,0,.5,8,.15,10,.01) is None
 for change in [{},{'finite_sub_capital_from':30,'finite_sub_capital_fee':.03}]:
  p=m['configs']()['structural_zero_growth'];p.update(change);r=m['simulate'](m['prepare_award_budget'](p));assert r['feasible']
  for row in r['rows'][15:]:assert abs(row['capex']-row['da'])<1e-8 and row['da']>0
  for row in [r['rows'][79],r['rows'][-1]]:
   for i in [5,6]:assert row['cash'][i]-row['liquidity_floors'][i]-row['parent_dividend_receivable'][i-1]<1
  for row in r['rows']:
   for e in row['finite_capital_events']:
    assert abs(e['parent']+e['minority']-e['gross'])<1e-9
    assert abs(e['mother_gain']-(e['parent']-e['basis']))<1e-9
    assert e['units_after']>0 and e['registered_after']>0 and e['parent_basis_after']>=0

def test_shenghong_fresh_all_output_and_interface():
 m=model();out=m['make']();packed=json.loads((root/'2026-Q3-output.json').read_text())
 assert m['expand_output'](packed)==out
 assert m['canonical_bytes'](m['pack_output'](out))==(root/'2026-Q3-output.json').read_bytes()
 assert len(out['scenarios'])==34
 assert out['return_model']['base_case_distributions_per_share']==[a['distribution_per_share'] for a in out['scenarios']['base']['rows'][:5]]
 for name,run in out['scenarios'].items():
  if not run['feasible']:continue
  for row in run['rows']:
   assert abs(row['cash_identity_error'])<1e-5
   assert min(row['entity_tax_details']['entity_cash_taxes'])>=0
  if name!='voluntary_continue_None':
   for row in [run['rows'][79],run['rows'][-1]]:
    for i in range(7):assert row['cash'][i]-row['liquidity_floors'][i]-(row['parent_dividend_receivable'][i-1] if i else 0)<1
 assert not out['scenarios']['funding_failure']['feasible']
 assert not out['scenarios']['structural_foreign_not_accelerated']['feasible']
