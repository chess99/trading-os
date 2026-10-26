"""Independent literal budgets and alternate annual derivation. No production import."""
from pathlib import Path
import json,copy
SHARES=.639826824
CASH0=(3670798598.29+3611072057.36)/1e9-.020-.060541-.051-.09563224203
BASE=dict(revenues=[6.9,7.18,7.47,7.77,8.08,8.36,8.61,8.85,9.07,9.25],
 margins=[.295,.295,.297,.297,.297,.295,.293,.291,.289,.287],tax=.16,
 da=[.17,.19,.23,.25,.27,.28,.29,.30,.31,.32],
 maintenance=[.15,.17,.21,.24,.27,.28,.29,.30,.31,.32],
 project=[.60,.60,.17,0,0,0,0,0,0,0],
 other_growth=[.04,.04,.04,.04,.04,.04,.04,.04,.04,.04],
 nwc=[.12,.08,.07,.07,.07,.06,.06,.06,.06,.06],
 minority=[.003,.004,.005,.006,.007,.008,.009,.01,.011,.012],
 payout=.95,yield_net=.013,parent_share=.88,sub_payout=.8,
 parent_cash=CASH0-.4,sub_cash=.4,parent_re=8.0,source_retained_budget=0.,
 source_profit_buffer_rate=.10,tail_source_buffer_rate=0.,source_release_rate=.10,mother_release_rate=.10,parent_registered=.639802980,parent_paid=.639802980,shares=.639802980,capital_action_cash=.00076614393,
 parent_statutory=.46615687134,treasury_shares=.000385869,
 parent_floor=.9,sub_floor=.1,liquidity_revenue_anchor=9.25,review_years=5,realization_fee=.01,internal_repayment=0.,g=.02,roic=.15)

def scenario(name):
    p=copy.deepcopy(BASE)
    if name=='cyclical':
        p.update(revenues=[6.2,6.3,6.8,7.3,7.75,8.1,8.4,8.65,8.85,9.02],
          margins=[.255,.26,.28,.29,.295,.293,.291,.289,.287,.285],
          nwc=[.4,.2,-.12,-.08,.07,.06,.06,.06,.06,.06],payout=.8)
    elif name=='structural':
        p.update(revenues=[6.2,5.9,5.65,5.5,5.4,5.3,5.2,5.1,5.,4.9],
          margins=[.24,.21,.19,.18,.18,.18,.18,.18,.18,.18],tax=.20,
          nwc=[.35,.25,.15,.1,.1,.08,.08,.08,.08,.08],payout=.65,g=0.,roic=.10)
    elif name=='optimistic':
        p.update(revenues=[7.1,7.6,8.15,8.7,9.25,9.7,10.1,10.5,10.85,11.17],
          margins=[.30,.305,.31,.31,.31,.308,.306,.304,.302,.30],
          nwc=[.14,.14,.14,.14,.14,.12,.12,.1,.1,.1],g=.025,roic=.18)
    elif name=='loss_year1':p['margins'][0]=-.10
    elif name=='margin_minus_2pp':p['margins']=[x-.02 for x in p['margins']]
    elif name=='credit_delay':p['nwc'][0]+=.6;p['nwc'][2]-=.6
    elif name=='park_overrun':p['project']=[x*1.3 for x in p['project']]
    elif name=='internal_settlement':p['internal_repayment']=.6
    elif name=='no_upstream':p['sub_payout']=0.
    elif name=='source_buffer_zero':p['source_profit_buffer_rate']=0.
    elif name=='source_buffer_20pct':p['source_profit_buffer_rate']=.20
    elif name=='source_prior_budget_035':p['source_retained_budget']=.35
    elif name=='mother_legal_zero_boundary':p['parent_re']=0.
    elif name=='pending_cancellations_complete':
        p.update(shares=.639417111,treasury_shares=0.,parent_registered=.639417111,parent_paid=.639417111,
            capital_action_cash=.00076614393)
    elif name=='registered_old_charter_timing':p['parent_registered']=.643976824
    elif name=='source_release_slow':p.update(source_release_rate=.05,mother_release_rate=.05)
    elif name=='source_release_fast':p.update(source_release_rate=.20,mother_release_rate=.20)
    elif name=='source_payout_half':p['sub_payout']=.40
    elif name=='horizon_400':p['horizon']=400
    elif name=='tail_source_buffer_10pct':p['tail_source_buffer_rate']=.10
    elif name=='review_3years':p['review_years']=3
    elif name=='review_10years':p['review_years']=10
    elif name=='realization_fee_3pct':p['realization_fee']=.03
    elif name=='realization_fee_zero':p['realization_fee']=0.
    elif name=='liquidity_150pct':p['parent_floor']*=1.5;p['sub_floor']*=1.5
    return p

def literal(p,r=.09,start=0,delay=0):
    n=len(p['revenues']);h=p.get('horizon',320)
    pc=p['parent_cash']-p.get('capital_action_cash',0);sc=p['sub_cash'];pr=p['parent_re'];sr=p['source_retained_budget'];reserve=p['parent_statutory'];shares=p['shares']-p['treasury_shares']
    rows=[];hp=hs=0.;withheld=0.
    for y in range(1,h+1):
        i=y-1
        if y<=n:
            rev=p['revenues'][i];margin=p['margins'][i];mi=p['minority'][i]
            da=p['da'][i];maint=p['maintenance'][i];park=p['project'][i];growth=p['other_growth'][i];nwc=p['nwc'][i]
        else:
            scale=(1+p['g'])**(y-n);rev=p['revenues'][-1]*scale;margin=p['margins'][-1];mi=p['minority'][-1]*scale
            e=p['revenues'][-1]*p['margins'][-1];last=e-max(e,0)*p['tax']-p['minority'][-1]
            da=p['da'][-1]*scale;maint=da;park=0.;growth=last*scale*p['g']/p['roic'];nwc=0.
        ebit=rev*margin;tax=max(ebit,0)*p['tax'];profit=ebit-tax-mi
        if y==n+1:hp=max(pc-p['parent_floor'],0);hs=max(sc-p['sub_floor'],0)
        locked=n<y<=n+delay
        scale=rev/p["liquidity_revenue_anchor"] if y>n else 1.
        pm=p["parent_floor"]*scale;sm=p["sub_floor"]*scale
        review=y>n and not locked and (y-n-delay)%p["review_years"]==0
        pi=pc*p['yield_net'];si=sc*p['yield_net'];own=profit*p['parent_share'];source=profit*(1-p['parent_share'])
        adj=da-maint-growth-nwc;transfer=p['internal_repayment'] if y==1 else 0.
        available=sc+source+adj*(1-p['parent_share'])+si+transfer
        source_income=source+si
        recovered=max(0,min(source_income,sr+source_income))
        buffer=recovered*(p['source_profit_buffer_rate'] if y<=n else p['tail_source_buffer_rate'])
        sr=sr+source_income-buffer;withheld+=buffer
        release=p['source_release_rate']*max(sc-p['sub_floor'],0) if y>n and not locked else 0.
        sent=max(0,min(p['sub_payout']*max(source_income,0)+release,sr,available-sm-(hs if locked else 0)))
        gross=sent;principal=fee=br=0.
        if review:
            gross=max(0.,available-sm)
            earning=min(gross,max(0.,sr));br=min(withheld,gross-earning);withheld-=br
            principal=gross-earning-br;fee=gross*p['realization_fee'];sent=gross-fee
        sr-=gross-principal-br;sc_end=available-gross
        legal=own+pi+sent-principal;recovered=max(0,min(legal,pr+legal));retention=min(.1*recovered,max(0,.5*p['parent_registered']-reserve));reserve+=retention
        pr=pr+legal-retention
        available=pc+own+adj*p['parent_share']-park+pi+sent-transfer
        request=p['payout']*max(0,profit+pi+si)
        if y>n and not locked:request+=p['mother_release_rate']*max(pc-p['parent_floor'],0)
        if review:request=max(0.,available-pm)
        paid=max(0,min(request,pr,available-pm-(hp if locked else 0)))
        pc=available-paid;sc=sc_end;pr-=paid
        rows.append(dict(year=y,revenue=rev,ebit=ebit,cash_tax=tax,old_dividend_receipt=0.,debt_service=0.,operating_profit_common=profit,parent_own_profit=own,subsidiary_profit=source,financial_income=pi+si,parent_legal_profit=legal,subsidiary_upstream=sent,source_gross_realization=gross,source_principal_return=principal,source_buffer_release=br,source_withheld_earnings=withheld,realization_fee=fee,parent_necessary_cash=pm,source_necessary_cash=sm,realization_review=int(review),capex=maint+park+growth,da=da,nwc=nwc,fcf=profit+da-maint-park-growth-nwc,dividend=paid,dps=paid/shares,parent_cash=pc,subsidiary_cash=sc,cash=pc+sc,parent_retained=pr,source_earnings_budget=sr,source_profit_buffer=buffer,parent_reserve_appropriation=retention,parent_statutory_reserve=reserve,parent_registered=p['parent_registered'],parent_paid=p['parent_paid'],bank_debt=0.,new_financing=0.,shares=shares,issued_shares=p['shares'],treasury_shares=p['treasury_shares'],internal_repayment=transfer,capital_action_cash=p['capital_action_cash'] if y==1 else 0.,parent_locked_cash=hp if locked else 0.,source_locked_cash=hs if locked else 0.))
    terminal=sum(x['dividend']/(1+r)**(x['year']-n) for x in rows[n:])
    value=sum(x['dividend']/(1+r)**(x['year']-start) for x in rows[start:])/shares
    return dict(value=value,terminal_equity=terminal,rows=rows)


ROOT=Path(__file__).resolve().parents[1]/"research/companies/CN/000423/models"
def test_donge_independent_full_paths():

    paths={}
    for k,r,start in [('base_low',.095,0),('base_high',.085,0),('year5_low',.095,5),('year5_high',.085,5)]:paths[k]=literal(copy.deepcopy(BASE),r,start)
    names=['cyclical','structural','optimistic','loss_year1','margin_minus_2pp','credit_delay','park_overrun','internal_settlement','no_upstream','source_buffer_zero','source_buffer_20pct','source_prior_budget_035','mother_legal_zero_boundary','pending_cancellations_complete','registered_old_charter_timing','source_release_slow','source_release_fast','source_payout_half','horizon_400','tail_source_buffer_10pct','review_3years','review_10years','realization_fee_3pct','realization_fee_zero','liquidity_150pct']
    for k in names:paths['scenarios/'+k]=literal(scenario(k))
    for d in [3,5]:paths['scenarios/terminal_cash_delay_'+str(d)]=literal(copy.deepcopy(BASE),delay=d)
    for k in ['base','cyclical','structural','optimistic']:
        q=scenario(k);q['tail_source_buffer_rate']=.1;paths['tail_source_buffer_scenarios/'+k]=literal(q)
    # Only now read production outputs, never inputs or production code.
    p=ROOT;actual=json.loads((p/'2026-Q3-output.json').read_text());errors={}
    for key,a in paths.items():
        b=actual
        for part in key.split('/'):b=b[part]
        rows=b['rows']+b['tail_rows'];assert len(rows)==len(a['rows'])
        differences=[abs(a['value']-b['value']),abs(a['terminal_equity']-b['terminal_equity'])]
        for i,row in enumerate(a['rows']):
            assert set(row)==set(rows[i]),(key,set(row)^set(rows[i]))
            differences.extend(abs(v-rows[i][k]) for k,v in row.items())
        errors[key]=max(differences);assert errors[key]<1e-8,(key,errors[key])

import runpy,subprocess,sys
from functools import lru_cache
from types import SimpleNamespace
@lru_cache(None)
def model():return SimpleNamespace(**runpy.run_path(str(ROOT/'2026-Q3.py')))
def test_donge_actual_functions():
 m=model()
 def simple(profits):
  q=copy.deepcopy(m.BASE);n=len(profits)
  q.update(revenues=[1.]*n,margins=profits,tax=0.,da=[0.]*n,maintenance=[0.]*n,project=[0.]*n,other_growth=[0.]*n,nwc=[0.]*n,minority=[0.]*n,payout=1.,yield_net=0.,parent_share=1.,sub_payout=1.,parent_cash=10.,sub_cash=0.,parent_re=0.,source_retained_budget=0.,parent_floor=0.,sub_floor=0.,g=0.,roic=.2,shares=1.,treasury_shares=0.,capital_action_cash=0.,parent_registered=20.,parent_paid=10.,parent_statutory=5.)
  return q
 out={}
 q=simple([10]);z=m.project(q)[0];assert z['parent_reserve_appropriation']==1 and z['dividend']==9;out['registered_not_paid']=z
 q['parent_statutory']=10;z=m.project(q)[0];assert z['parent_reserve_appropriation']==0;out['full_reserve']=z
 q=simple([10]);q['parent_re']=-4;z=m.project(q)[0];assert abs(z['parent_reserve_appropriation']-.6)<1e-12 and abs(z['dividend']-5.4)<1e-12;out['same_year_loss_makeup']=z
 q=simple([-1,2]);q.update(tax=.25,parent_statutory=10);z=m.project(q);assert z[0]['cash_tax']==0 and z[0]['parent_retained']==-1 and z[1]['cash_tax']==.5 and z[1]['dividend']==.5;out['negative_ebit_no_refund']=z
 q=simple([10]);q.update(parent_statutory=10,bank_debt=20,debt_conversion=20,conversion_price=1);z=m.project(q)[0];assert z['shares']==21 and z['parent_registered']==40 and z['bank_debt']==0 and z['parent_reserve_appropriation']==1;out['conversion_registered_shares_debt']=z
 v=m.valuation(q,.1);assert v['feasible'];expected=sum(x['dps']/1.1**x['year'] for x in v['rows']+v['tail_rows']);assert abs(v['value']-expected)<1e-10;out['conversion_valuation_per_share']=v['value']
 q=simple([0]);q.update(parent_cash=0,sub_cash=1,old_dividend_receivable=1,old_dividend_receipts={1:1});z=m.project(q)[0];assert z['parent_cash']==1 and z['parent_legal_profit']==0 and z['dividend']==0;out['old_receipt_cash_only']=z
 q=simple([0]);q.update(parent_cash=0,project=[1]);z=m.valuation(q,.1);assert not z['feasible'] and z['value'] is None and z['failure']['funding_gap']==1 and z['failure']['shares']==1;out['main_capex_shortfall']=z
 q=simple([0]);q.update(parent_cash=.25,bank_debt=1,debt_service={1:1});z=m.valuation(q,.1);assert not z['feasible'] and z['failure']['bank_debt']==1 and z['failure']['shares']==1 and z['failure']['funding_gap']==.75;out['main_creditor_failure_preserves_debt']=z
 q=simple([0]);q.update(parent_cash=0,capital_action_cash=.1,pre_action_shares=2);z=m.valuation(q,.1);assert not z['feasible'] and z['failure']['shares']==2;out['unfunded_cancellation_preserves_shares']=z
 for fraction in [1,.7,.51]:
  z=m.capital_realization(cash=0,proceeds=10,investment_cost=10,exit_cost=1,debt=1,shares=2,fraction=fraction)
  assert z['feasible'] and z['tax_cash']==0 and abs(z['distribution']-(9*fraction-1))<1e-12 and z['shares']==0
  out['principal_with_cost_'+str(fraction)]=z
 for label,kw in [('exit_cost',dict(cash=0,proceeds=1,investment_cost=1,exit_cost=2,debt=0,shares=3)),('debt',dict(cash=0,proceeds=1,investment_cost=1,exit_cost=.1,debt=2,shares=3))]:
  z=m.capital_realization(**kw);assert not z['feasible'] and z['shares']==3 and z['debt']==kw['debt'] and z['distribution']==0 and z['funding_gap']>0;out['disposal_failure_'+label]=z
 z=m.capital_realization(cash=0,proceeds=12,investment_cost=10,exit_cost=1,debt=0,shares=1,tax=.25);assert z['tax_cash']==.25 and z['realized_profit']==.75 and z['distribution']==10.75;out['tax_only_gain_no_principal_income']=z
 q=simple([0]);q.update(bank_debt=1);z=m.valuation(q,.1);assert not z['feasible'] and z['failure']['bank_debt']==1;out['terminal_debt_never_disappears']=z
 q=simple([1]);q.update(shares=10.,treasury_shares=2.,parent_statutory=10.);z=m.project(q)[0];assert z['issued_shares']==10 and z['shares']==8 and z['dps']==.125;out['treasury_excluded_before_cancellation']=z
 q.update(shares=8.,treasury_shares=0.,parent_registered=18.,parent_paid=8.);w=m.project(q)[0];assert w['dps']==z['dps'];out['treasury_cancellation_no_second_benefit']=w
 # Main economic-tail function, not just disposal helper: principal cannot create legal profit.
 q=simple([0]);q.update(parent_cash=0.,sub_cash=1.,parent_re=10.,parent_statutory=10.,_tail_start=0,review_years=1,realization_fee=.01)
 z=m.project(q)[0];assert abs(z['source_principal_return']-1)<1e-12 and abs(z['realization_fee']-.01)<1e-12 and abs(z['parent_legal_profit']+.01)<1e-12 and abs(z['dividend']-.99)<1e-12 and z['shares']==1
 out['main_tail_principal_fee_no_fake_profit']=z
 q['parent_re']=0.;z=m.project(q)[0];assert z['dividend']==0 and abs(z['parent_cash']-.99)<1e-12 and z['parent_retained']<0
 out['main_tail_principal_requires_mother_capacity']=z
 q['realization_fee']=2.
 try:m.project(q);raise AssertionError('fee failure required')
 except m.FundingFailure as ex:assert ex.state['shares']==1 and ex.state['funding_gap']>0;out['main_tail_fee_failure_preserves_shares']=ex.state

def test_donge_all_aggregate_future_cash():
 p=ROOT;m=model()
 a=json.loads((p/'2026-Q3-output.json').read_text());results={}
 paths=[('base',copy.deepcopy(m.BASE),0)]
 for name in a['scenarios']:
  if name.startswith('terminal_cash_delay_'):paths.append((name,copy.deepcopy(m.BASE),int(name[-1])))
  else:paths.append((name,m.scenario(name),0))
 for name in a['tail_source_buffer_scenarios']:
  q=m.scenario(name);q['tail_source_buffer_rate']=.1;paths.append(('tail_buffer/'+name,q,0))
 for name,q,delay in paths:
  rows=m.project(m.extend_forecast(q,480,delay));reviews=[]
  for x in rows:
   excess=x['cash']-x['parent_necessary_cash']-x['source_necessary_cash']
   if x['realization_review']:
    if not (name=='mother_legal_zero_boundary' and x['year']<=20):
     assert abs(excess)<1e-8*max(1.,x['cash']),(name,x['year'],excess)
    reviews.append(dict(year=x['year'],total_cash=x['cash'],necessary=x['parent_necessary_cash']+x['source_necessary_cash'],excess=excess,source_principal=x['source_principal_return'],fees=x['realization_fee']))
  assert max(b['year']-a['year'] for a,b in zip(reviews,reviews[1:]))==q['review_years']
  v={}
  for h in [320,400,480]:
   z=copy.deepcopy(q);z['horizon']=h;v[h]=m.valuation(z,.09,cash_release_delay=delay)['value']
  assert abs(v[480]-v[400])<1e-7,(name,v)
  results[name]=dict(aggregate_surplus_reviews=reviews,max_tail_wait=q['review_years'],value_by_horizon=v)
 # Endogenous principal: retain existing owner cash, no injection, financing or invented income.
 # At each year 11..320 withhold up to .01bn from a real dividend and recompute to 340.
 retentions=[]
 for scenario in ['base','structural']:
  q=m.extend_forecast(m.scenario(scenario),340);base=m.project(q)
  for y in range(11,321):
   for node in ['parent','source']:
    if node=='source' and base[y-1]['realization_review']:continue
    w=copy.deepcopy(q);w['retain_'+node]={y:.01};r=m.project(w)
    review=next(z['year'] for z in base[y:] if z['realization_review'])
    z0,z1=base[review-1],r[review-1]
    assert abs(z1['cash']-z0['cash'])<1e-8,(scenario,node,y,review)
    assert all(z['new_financing']==0 and z['shares']==base[i]['shares'] for i,z in enumerate(r))
    cost=base[y-1]['dividend']-r[y-1]['dividend']
    recovered=sum(r[t]['dividend']-base[t]['dividend'] for t in range(y,review))
    # Source retention can delay mother cash without contemporaneous dividend impact;
    # nevertheless both pools normalize by the next review, with explicit fee/interest.
    retentions.append(dict(scenario=scenario,node=node,year=y,review=review,dividend_deferred=cost,future_distribution_change=recovered,ending_cash_delta=z1['cash']-z0['cash']))

def test_donge_standalone_regenerate(tmp_path):
 (tmp_path/'2026-Q3.py').write_bytes((ROOT/'2026-Q3.py').read_bytes());subprocess.run([sys.executable,'-I',str(tmp_path/'2026-Q3.py')],cwd=tmp_path,check=True,stdout=subprocess.DEVNULL)
 assert (tmp_path/'2026-Q3-output.json').read_bytes()==(ROOT/'2026-Q3-output.json').read_bytes()
