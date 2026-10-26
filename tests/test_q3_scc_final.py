"""Literal reconstruction: never imports formal model or reads its input parameters.
Compare only after reconstructing annual accounting, registered/paid timing and DCF.
"""
import json,pathlib,copy
D=pathlib.Path(__file__).resolve().parents[1]/"research/companies/CN/002916/models"
SPEC={
 'base':{},'registration_lag_3years':{'lag':3},'voluntary_reserve_10pct':{'voluntary':.1},
 'tax25_from_year1':{'expiry':1},'tax25_from_year4':{'expiry':4},'portfolio_accessibility_minus5pct':{'haircut':.05},
 'cyclical':{'sales':[34,37,44,51,56],'margins':[.14,.15,.17,.18,.18],'capex':[7,4.5,4.8,4.8,4.8],'wc':.37},
 'structural':{'sales':[34,35,37,39,41],'margins':[.12,.115,.11,.105,.10],'capex':[7,4,3.5,3.2,3.2],'wc':.38,'tm':.1,'g':.01,'growth':[.02]*5,'fixed':.8},
 'upside':{'sales':[43,53,62,70,77],'margins':[.21,.21,.205,.2,.195],'capex':[9,7,6.5,6.2,6],'tm':.16},
 'margin_minus_2pp_from_year1':{'margins':[.18,.175,.17,.165,.16],'tm':.13},
 'wc_plus_5pp_from_year1':{'wc':.37},'borrowing_plus_2pp_from_year1':{'interest':.06},
 'guangzhou_loss_2bn':{'gloss':-2},'upstream_delay_one_year_parent_pays_1bn':{'delay':1,'settlement':1},
 'financial_release_delayed_to_year11':{'policy_end':10},'debt_cap_11bn':{'limit':11},
 'cash_capex_plus_20pct_first5':{'capex':[9.6,7.2,6,5.76,5.76]},
 'incentive_refund_cancel':{'equity':-1.624123968,'shares':-.0144258},
 'equity_4_30bn_newshares_0.03':{'equity':4.3,'shares':.03},'equity_4_30bn_newshares_0.06':{'equity':4.3,'shares':.06}}

def reconstruct(over,n=40):
    q=dict(sales=[40,47,53,58,62],margins=[.20,.195,.19,.185,.18],capex=[8,6,5,4.8,4.8],wc=.32,tm=.15,g=.02,growth=[.07,.06,.05,.04,.03],fixed=.65,interest=.04,gloss=-.5,delay=0,settlement=0,policy_end=5,limit=18,equity=0,shares=0,lag=1,voluntary=0,expiry=1000,haircut=0)
    q.update(over)
    cash=[.4,.22,.17,.15,.16111696734];debt=[1.8,3,1.6,1,2.09499814993]
    retained=[3.87016577999,0,0,0,q['gloss']];stat=[.3333703975,0,0,0,0];vol=[0.]*5
    reg=[.681166595,.78,.78,.101,1.5];paid=[0.]*5;pending=[[] for _ in range(5)]
    basis=[0,.86021610502,1.59249193372,2.07829177915,4.37173421137]
    wp=[.18,.32,.18,.22,.1];wk=[.08,.40,.22,.12,.18];ww=[.2,.3,.2,.18,.12]
    rev=32.66683675642;wc=10.564;shares=.681166595;outputs=[];fixed=23.859
    def profit(i,amount):
        surplus=max(0,amount+min(0,retained[i]));reserve=min(max(0,reg[i]/2-stat[i]),surplus/10)
        voluntary=min(max(0,reg[i]/2-vol[i]),max(0,surplus-reserve)*q['voluntary'])
        retained[i]+=amount-reserve-voluntary;stat[i]+=reserve;vol[i]+=voluntary
    for year in range(1,n+2):
        for i in range(5):
            reg[i]+=sum(a for y,a in pending[i] if y<=year);pending[i]=[(y,a) for y,a in pending[i] if y>year]
        if year==1:cash[0]+=q['equity'];shares+=q['shares'];reg[0]+=q['shares']
        old=rev
        if year<6:rev=q['sales'][year-1];m=q['margins'][year-1];capex=q['capex'][year-1]
        else:
            rev*=1+(q['growth'][year-6] if year<11 else q['g']);m=q['margins'][-1]+(q['tm']-q['margins'][-1])*min(1,(year-5)/5)
            capex=rev*.055+max(0,rev-old)*q['fixed']
        dwc=rev*q['wc']-wc;wc=rev*q['wc'];floor=[rev*.035*w for w in ww];income=0;taxes=[]
        for i in range(5):
            pretax=rev*m*wp[i]-q['interest']*debt[i]+cash[i]*.015
            tax=max(0,pretax)*(.25 if year>=q['expiry'] else .17);taxes.append(tax)
            net=pretax-tax;net-=max(0,net)*q['haircut'];net-=max(0,rev*m*(1-(.25 if year>=q['expiry'] else .17)))*.0013 if i==0 else 0
            income+=net;cash[i]+=net+(rev*.055-capex)*wk[i]-dwc*ww[i];profit(i,net)
        if year==3:
            gain=.08418882463-.0304783237;cash[0]+=.08418882463-.25*gain;retained[0]+=gain*.75
        if year==1:cash[0]-=q['settlement'];cash[4]+=q['settlement']
        for i in range(5):
            repay=min(debt[i],max(0,cash[i]-floor[i])*(.25 if year<6 else 1));cash[i]-=repay;debt[i]-=repay
        for i,target in [(3,4),(1,0),(2,0),(4,0)]:
            remit=min(max(0,retained[i]),max(0,cash[i]-floor[i])) if year>q['delay'] else 0
            retained[i]-=remit;cash[i]-=remit;cash[target]+=remit;profit(target,remit)
            excess=max(0,cash[i]-floor[i])
            if year>=10 and excess>1e-9 and paid[i]>0:
                avail=cash[i]-floor[i]-debt[i]
                if avail>=-1e-10:
                    ret=min(excess,max(0,avail),max(0,paid[i]-sum(a for _,a in pending[i])),reg[i]);fee=ret*.02
                    cash[i]-=ret;cash[target]+=ret-fee;reg[i]-=ret;paid[i]-=ret;basis[i]-=ret;profit(target,-fee)
        for i in [1,2,3,4]:
            injection=max(0,floor[i]-cash[i]);cash[0]-=injection;cash[i]+=injection
            if injection:
                paid[i]+=injection;basis[i]+=injection;pending[i].append((year+q['lag'],injection))
                if i==3:paid[4]+=injection;basis[4]+=injection;pending[4].append((year+q['lag'],injection))
        target=max(0,income)*.30 if year<=q['policy_end'] else max(0,cash[0]-floor[0])
        credit=min(max(0,q['limit']-sum(debt)),max(0,floor[0]+min(target,max(0,retained[0]))-cash[0]));debt[0]+=credit;cash[0]+=credit
        feasible=cash[0]+1e-8>=floor[0]
        requested=max(0,income)*.30 if year<=q['policy_end'] else max(0,cash[0]-floor[0])
        payout=min(requested,max(0,retained[0]),max(0,cash[0]-floor[0])) if feasible else 0
        cash[0]-=payout;retained[0]-=payout;fixed+=capex-([2,1.5,0,0,0][year-1] if year<=5 else 0)-rev*.055
        outputs.append(dict(year=year,revenue=rev,net_profit=income,total_cash=sum(cash),total_debt=sum(debt),distribution_per_share=payout/shares,fixed_assets=fixed,feasible=feasible,entity_cash=cash[:],entity_debt=debt[:],entity_retained=retained[:],entity_reserve=stat[:],entity_registered=reg[:],entity_paid_new=paid[:],entity_investment_cost=basis[:],entity_voluntary=vol[:],entity_tax=taxes))
        if not feasible:break
    values={}
    for label,rate in [('low',.105),('high',.09)]:
        if not outputs[-1]['feasible']:values[label]={'value_per_share':None,'terminal_year5_per_share':None};continue
        d=[x['distribution_per_share'] for x in outputs];terminal=d[n]/(rate-q['g'])
        pv=sum(d[t-1]/(1+rate)**t for t in range(1,n+1))+terminal/(1+rate)**n
        tv=sum(d[t-1]/(1+rate)**(t-5) for t in range(6,n+1))+terminal/(1+rate)**(n-5)
        values[label]={'value_per_share':pv,'terminal_year5_per_share':tv}
    return {'years':outputs,'values':values}


import runpy,subprocess,sys
from functools import lru_cache
@lru_cache(None)
def model():return runpy.run_path(str(D/'2026-Q3.py'))
@lru_cache(None)
def output():return json.loads((D/'2026-Q3-output.json').read_text())
def test_scc_all_literal_annual_paths():
 reference=output()
 for name,over in SPEC.items():
  calc=reconstruct(over);rr=reference['scenarios'][name]['years'];assert len(rr)==len(calc['years'])
  for a,b in zip(calc['years'],rr):
   assert a['feasible']==b['feasible']
   for k in ['revenue','net_profit','total_cash','total_debt','distribution_per_share','fixed_assets']:assert abs(a[k]-b[k])<1e-8
   for i in range(5):
    for x,y in [('entity_cash','closing_cash'),('entity_debt','closing_debt'),('entity_retained','closing_legal_retained'),('entity_reserve','closing_reserve'),('entity_registered','registered_capital'),('entity_paid_new','new_paid_capital_budget'),('entity_investment_cost','investment_cost_budget'),('entity_voluntary','discretionary_reserve_budget'),('entity_tax','tax')]:assert abs(a[x][i]-b['entities'][i][y])<1e-8
  for e in ['low','high']:
   for k in ['value_per_share','terminal_year5_per_share']:
    x,y=calc['values'][e][k],reference['valuations'][name][e][k];assert (x is None and y is None)or abs(x-y)<1e-8

def test_scc_actual_registered_loss_return_failures():
 m=model();m['hand_tests']();m['root_tests']()
 e=dict(re=0.,reserve=5.,capital=20.,paid_verified=10.);assert m['accrue'](e,10)==1
 e=dict(re=-5.,reserve=0.,capital=20.);assert m['accrue'](e,3)==0 and e['re']==-2
 for debt,cost in [(5,0),(0,5)]:
  q=m['capital_realisation'](4,0,debt,cost,10,10,10,exit_all=True,equity_units=7)
  assert not q['feasible'] and q['equity_units_after']==7 and q['owner_cash']==0
 q=m['capital_realisation'](100,0,0,0,100,100,40,ownership=.6,fee_rate=0,equity_units=10)
 assert q['equity_units_after']==6 and q['owner_cash']==24 and q['minority_cash']==16

def test_scc_full_tail_cash_maintenance_and_same_path():
 m=model()
 for name,path in output()['scenarios'].items():
  if not path['feasible']:assert output()['valuations'][name]['low']['value_per_share'] is None;continue
  p=copy.deepcopy(path['inputs']);p['tail_year']=120
  long=m['run'](p,name,path['equity_budget'],path['new_share_budget'])
  for edge,rate in [('low',.105),('high',.09)]:assert abs(m['value'](long,rate)['value_per_share']-output()['valuations'][name][edge]['value_per_share'])<1e-7
  for row in long['years']:
   if row['year']>=11:assert abs(row['total_cash']-row['revenue']*p['cash_floor_ratio'])<1e-7
   assert abs(row['cash_conservation_error'])<1e-8
   if row['year']>10:assert row['cash_capex']>=row['depreciation']

def test_scc_singlefile_fresh(tmp_path):
 (tmp_path/'2026-Q3.py').write_bytes((D/'2026-Q3.py').read_bytes());subprocess.run([sys.executable,'-I',str(tmp_path/'2026-Q3.py')],cwd=tmp_path,check=True,stdout=subprocess.DEVNULL)
 assert (tmp_path/'2026-Q3-output.json').read_bytes()==(D/'2026-Q3-output.json').read_bytes()
