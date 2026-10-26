#!/usr/bin/env python3
"""独立全链复算。仅stdlib；原始假设手录，不导入正式脚本。
完成所有预测及端点后才读取正式JSON进行比较；金额亿元。
现金分为可动用cash与宣派后锁定pending，收款不再记法律利润。
"""
from dataclasses import dataclass
from pathlib import Path
import json

NAMES=('L','I','E','H','O','P')
SHARES=33.6864569
D0=17.4622684964+17.890628146-17.236864745+51.2530244+29.303815726+1.9177433628
C0=128.1150078051
RESTRICTED=142.1546221072-C0
# cash,floor,opening retained,remaining reserve room,profit weight,capital weight,debt weight
INPUT={
'L':(70,7,0,28,.70,.65,.48),'I':(0,0,0,22.4,0,0,0),
'E':(20,1.5,0,15.975,.13,.10,.24),'H':(10,1,0,6,.10,.10,.20),
'O':(C0-100-.9016081171,20,0,.522345,.02,0,.02),
'P':(.9016081171,.5,9.0996638532,SHARES/2-9.2269774471,.05,.15,.06)}
EDGES=(('L','I',.8),('L','H',.2),('O','E',1),('I','P',1),('E','P',1),('H','P',1))
BUDGET=list(zip([132,138,148,158,163],[30,32,34,35,36],[28,29,31,33,35],
 [30,31,33,35,37],[26,22,13.29,0,0],[5,6,8,10,12],[4,4,5,5,5],
 [12,10.64941641,0,0,0],[.65,.75,.85,.95,1.05]))
PARAM={'low':(.11,.099,.015,.10),'high':(.10,.092,.02,.12)}
@dataclass
class Account:
    cash:float
    legal:float
    reserve:float
    debt:float
    new_debt:float=0

def accrue(a,amount,room):
    eligible=max(0,amount+min(a.legal,0)) if amount>0 else 0
    held=min(eligible/10,max(0,room-a.reserve))
    a.legal+=amount-held
    a.reserve+=held

def snapshot(accounts):
    return {k:dict(vars(v)) for k,v in accounts.items()}

def forecast(delay=0, kind='base'):
    accounts={k:Account(x[0],x[2],0,D0*x[6]) for k,x in INPUT.items()}
    transfers=[]; events=[]; history=[]; borrowed=0
    scales=[1]*5; caps=[1]*5; extra_wc=[0]*5; rate=.033; extra_rent=0
    projects=[b[4] for b in BUDGET]; ongoing=[b[5] for b in BUDGET]; frozen=False
    if kind=='cyclical': scales=[.78,.80,.90,1,1];caps=[1,1,1.05,1.05,1.05];extra_wc=[8,3,-4,-3,0];delay=1
    if kind.startswith('structural'):
        scales=[.65,.65,.62,.60,.60];caps=[1.1]*5;extra_wc=[8,3,2,2,2];rate=.045;extra_rent=5;delay=1
    if kind=='structural':
        scales=[.65,.65,.60,.58,.58];projects=[15,18,18,10.29,0];ongoing=[0,0,2,3,3];frozen=True
    if kind=='upside':scales=[1.08,1.10,1.12,1.15,1.15];caps=[1.05,1.05,1.1,1.1,1.1];extra_wc=[2]*5
    for year,b in enumerate(BUDGET):
        initial=snapshot(accounts);initial_pending=sum(p['cash'] for p in transfers)
        pre,rent,da,maintenance,_,_,wc,old,target=b
        ebit=pre*scales[year]-rent-extra_rent
        operating={}; profit={}; tax={}; interest={}; settled={k:0 for k in NAMES};sent={k:0 for k in NAMES};loans={k:0 for k in NAMES}
        for k,a in accounts.items():
            _,floor,_,room,pw,cw,_=INPUT[k]
            interest[k]=a.debt*rate
            taxable=ebit*pw+max(a.cash-floor,0)*.01+.5*pw-interest[k]
            tax[k]=max(taxable,0)*(.17 if k=='O' else .15)
            profit[k]=taxable-tax[k]-(.02 if k=='H' else 0)
            operating[k]=profit[k]-.5*pw+da*cw-maintenance*caps[year]*cw-(projects[year]+ongoing[year])*caps[year]*cw-(wc+extra_wc[year])*pw
            a.cash+=operating[k]-old*cw
            accrue(a,profit[k],room)
        for k,a in accounts.items():
            capacity=40-borrowed
            if k=='P':capacity=min(capacity,12-a.new_debt)
            loan=min(max(0,INPUT[k][1]-a.cash),max(0,capacity))
            a.cash+=loan;a.debt+=loan;a.new_debt+=loan;borrowed+=loan;loans[k]=loan
            if a.cash<INPUT[k][1]-1e-8:
                return {'feasible':False,'failed_year':year+1,'failed_entity':k,'shortfall':INPUT[k][1]-a.cash,'rows':history}
        for k in ('L','O','I','E','H','P'):
            received=[p for p in transfers if p['dest']==k and p['due']<=year]
            for p in received:
                before=accounts[k].legal
                accounts[k].cash+=p['cash'];settled[k]+=p['cash'];transfers.remove(p)
                assert accounts[k].legal==before # 收到旧应收不二次确认利润
                events.append({'year':year+1,'type':'receipt','source':p['src'],'destination':k,'cash':p['cash'],'legal_income':0})
            a=accounts[k]
            if k=='P':
                paid=min(0 if frozen else target*SHARES,max(a.legal,0),max(a.cash-INPUT[k][1],0))
                a.cash-=paid;a.legal-=paid
            else:
                ceiling=.55*max(profit[k],0) if k in ('L','O') else max(a.cash-INPUT[k][1],0)
                amount=max(0,min(ceiling,a.legal,a.cash-INPUT[k][1]));a.cash-=amount;a.legal-=amount;sent[k]=amount
                for src,dest,w in EDGES:
                    if src==k and amount>0:
                        value=amount*w;accrue(accounts[dest],value,INPUT[dest][3])
                        transfers.append({'src':src,'dest':dest,'due':year+delay,'cash':value})
                        events.append({'year':year+1,'type':'declaration','source':src,'destination':dest,'cash':value,'legal_income':value})
        for k,a in accounts.items():
            expected=initial[k]['cash']+operating[k]-old*INPUT[k][5]+loans[k]+settled[k]-sent[k]-(paid if k=='P' else 0)
            assert abs(a.cash-expected)<1e-8 and a.cash>=-1e-8
        ending=sum(a.cash for a in accounts.values())+sum(p['cash'] for p in transfers)
        assert abs(ending-(sum(x['cash'] for x in initial.values())+initial_pending+sum(operating.values())-old+sum(loans.values())-paid))<1e-7
        history.append({'year':year+1,'accounts':snapshot(accounts),'pending':list(map(dict,transfers)),'dps':paid/SHARES,'ebit':ebit,'paid':paid,'new_debt':sum(loans.values()),'declared':sent,'net_profit':sum(profit.values()),'cash_generated':sum(operating.values())})
    return {'feasible':True,'rows':history,'events':events}

def unlock(prediction,blocked=0):
    last=prediction['rows'][-1]
    accounts={k:Account(**v) for k,v in last['accounts'].items()}
    pending=[dict(x) for x in last['pending']];security=9.118;rows=[];cumulative=0
    initial=sum(a.cash for a in accounts.values())+sum(p['cash'] for p in pending)+security
    for step in range(1,blocked+4):
        declarations={k:0 for k in NAMES};payments=0;flows=[]
        if step>blocked:
            periods=blocked+4-step
            if periods==1:accounts['E'].cash+=security;security=0
            for k in ('L','O','I','E','H'):
                a=accounts[k];v=min(max(a.cash-INPUT[k][1],0)/periods,max(a.legal,0))
                a.cash-=v;a.legal-=v;declarations[k]=v
                for src,dst,w in EDGES:
                    if src==k:
                        accounts[dst].cash+=v*w;accrue(accounts[dst],v*w,INPUT[dst][3]);flows.append((src,dst,v*w))
            due=[p for p in pending if p['due']<=4+step]
            for p in due:
                oldlegal=accounts[p['dest']].legal
                accounts[p['dest']].cash+=p['cash'];pending.remove(p)
                assert oldlegal==accounts[p['dest']].legal
            parent=accounts['P'];payments=min(max(parent.cash-.5,0),max(parent.legal,0));parent.cash-=payments;parent.legal-=payments
        cumulative+=payments
        assert abs(sum(a.cash for a in accounts.values())+sum(p['cash'] for p in pending)+security+cumulative-initial)<1e-7
        assert all(a.cash>=-1e-8 for a in accounts.values())
        rows.append({'step':step,'paid':payments,'accounts':snapshot(accounts),'declared':declarations,'transfers':flows,'pending':list(map(dict,pending))})
    residual=sum(max(a.cash-INPUT[k][1],0) for k,a in accounts.items())+security+sum(p['cash'] for p in pending)
    return {'rows':rows,'residual':residual}

def price(pred,tail,param,terminal_ebit_delta=0):
    ke,wacc,g,roic=param
    last=pred['rows'][-1]
    # delta仅Y6起永续经营水平冲击，Y1–Y5全部现金/法定利润不变，非经营全链压力情景。
    ev=(last['ebit']+terminal_ebit_delta)*.85*(1+g)*(1-g/roic)/(wacc-g)
    financial=sum(row['paid']/(1+ke)**row['step'] for row in tail['rows'])
    debt=sum(a['debt'] for a in last['accounts'].values())
    tv=(ev-debt+RESTRICTED+23.0780722239-.118577+financial)/SHARES
    current=sum(r['paid']/SHARES/(1+ke)**r['year'] for r in pred['rows'])+tv/(1+ke)**5
    return {'ev_year5':ev,'financial_pv':financial,'terminal_equity_per_share':tv,'value_per_share':current}


import pytest
ROOT=Path(__file__).resolve().parents[1]/'research/companies/CN'
@pytest.mark.parametrize('kind',['base','cyclical','structural_unmitigated','structural','upside'])
@pytest.mark.parametrize('endpoint',['low','high'])
def test_satellite_full_source_entity_chain(kind,endpoint):
 out=json.loads((ROOT/'002648/models/2026-Q3-output.json').read_text())
 pred=forecast(kind=kind);ref=out['scenarios'][kind]
 assert pred['feasible']==ref['feasible']
 if not pred['feasible']:
  assert pred['failed_entity']==ref['failed_entity']
  assert pred['failed_year']==ref['failed_year']
  assert pred['shortfall']==pytest.approx(ref['shortfall'],abs=1e-8)
  return
 for a,b in zip(pred['rows'],ref['rows']):
  for entity,account in a['accounts'].items():
   for own,formal in [('cash','cash_by_entity'),('legal','legal_by_entity'),('reserve','reserves_by_entity'),('debt','debt_by_entity')]:
    assert account[own]==pytest.approx(b[formal][entity],abs=1e-8)
 param=PARAM[endpoint]
 if kind=='structural':param=(param[0],param[1],.005,.08)
 result=price(pred,unlock(pred),param)
 expected=out['valuations'][kind][endpoint]
 for key in ['value_per_share','terminal_equity_per_share']:
  assert result[key]==pytest.approx(expected[key],abs=1e-8)

@pytest.mark.parametrize('endpoint',['low','high'])
def test_satellite_year6_only_ebit_shock(endpoint):
 out=json.loads((ROOT/'002648/models/2026-Q3-output.json').read_text());pred=forecast();result=price(pred,unlock(pred),PARAM[endpoint],-10)
 assert result['value_per_share']==pytest.approx(out['independent_recomputation'][endpoint]['alternate_value'],abs=1e-8)

import math
def independently_rebuild(r,g):
    """Second implementation from literal source/budget inputs; no formal model calls or rows.
    Rebuild P/S/L earnings, accrual/receipt, capital, borrowing, legal profit, dilution, all 80 years.
    This is deliberately verbose and uses scalar accounts to expose cross-entity mistakes.
    """
    pc,sc,lc=500.,4.782733,0.; pd,sd,ld=2100.,160.867732,220.
    pe,se=620.,234.056598; pa=sa=la=0.; debt=1.5
    pre,pres=1300.,203.642853; sre,sres=-650.,0.; s_capital=400.; lre,lres=35.,5.
    shares=413.375586; old_wc=-1488.547204+.045*2134.324686
    outstanding_dividend=0.; accumulated_dps=0.; payments=[]; rebuilt=[]
    for year in range(1,81):
      if year<=5:
        mic=[1990.,2150.,2320.,2490.,2640.][year-1]
        ai=[105.,130.,155.,178.,200.][year-1]
        other=[230.,235.,240.,245.,250.][year-1]
        margin=[.313,.319,.324,.328,.330][year-1]
        prepaid=[.68,.68,.68,.67,.66][year-1]
        subsidiary_profit=[-25.,-18.,-10.,-5.,0.][year-1]
      else:
        growth=g+(.06-g)*max(0.,(10-year)/5)
        mic=mic*(1+growth);ai=ai*(1+growth);other=other*(1+growth)
        subsidiary_profit=4.*(1+g)**(year-5)
      turnover=mic+ai
      issued=(10.329613 if year==1 else 8.156226 if year==2 else 0.)
      subscription=issued*max(0.,20.84-accumulated_dps);shares+=issued
      pm=min(pd,600. if year==1 else 500. if year in (2,3,4) else 0.)
      sm=sd if year==1 else 0.;lm=ld if year==1 else 0.
      p_fin=pc*.018+pd*.018+pe*.025;s_fin=sc*.015+sd*.015;l_fin=lc*.018+ld*.018
      pa+=pd*.018;sa+=sd*.015;la+=ld*.018
      p_coupon=pa*pm/pd if pd else 0.;s_coupon=sa*sm/sd if sd else 0.;l_coupon=la*lm/ld if ld else 0.
      pa-=p_coupon;sa-=s_coupon;la-=l_coupon
      p_fin_cash=pc*.018+pe*.025+p_coupon;s_fin_cash=sc*.015+s_coupon;l_fin_cash=lc*.018+l_coupon
      pp=pe*.90 if year==8 else 0.;pb=pe if year==8 else 0.
      sp=se*.65 if year==10 else 0.;sb=se if year==10 else 0.
      s_tax=max(0.,subsidiary_profit+s_fin)*.20+max(0.,sp-sb)*.25
      s_income=subsidiary_profit+s_fin-s_tax+sp-sb
      s_potential=sc+subsidiary_profit+s_fin_cash-s_tax+sm+sp
      parent_support=max(0.,-subsidiary_profit,20.-s_potential)
      assert parent_support<=60.
      sc=s_potential+parent_support
      s_capital+=parent_support
      s_reserve=min(.1*max(0.,s_income+min(sre,0.)),max(0.,.5*s_capital-sres))
      sre+=s_income-s_reserve;sres+=s_reserve
      # No S upstream; no positive/negative sub income can be pooled into P statutory balance.
      l_tax=l_fin*.25;l_income=l_fin-l_tax
      l_reserve=min(.1*max(0.,l_income+min(lre,0.)),max(0.,100.-lres))
      lre+=l_income-l_reserve;lres+=l_reserve
      l_before=lc+l_fin_cash-l_tax+lm
      ld_cash=min(.8*l_income,max(0.,lre),max(0.,l_before-220.))
      lc=l_before-ld_cash;lre-=ld_cash
      declaration=ld_cash*.9987
      ebit=turnover*margin;debt_interest=debt*.05
      income_tax=max(0.,ebit+p_fin-debt_interest)*.15+max(0.,pp-pb)*.25
      p_income=ebit+p_fin-debt_interest-income_tax+(pp-pb)+declaration-max(0.,-subsidiary_profit)
      p_reserve=min(.1*max(0.,p_income+min(pre,0.)),max(0.,.5*shares-pres))
      pre+=p_income-p_reserve;pres+=p_reserve
      new_wc=(-prepaid+.045)*turnover
      required=(.3*prepaid+.12)*turnover
      available=pc+ebit+p_fin_cash-debt_interest-income_tax+.017*turnover-.018*turnover-new_wc+old_wc+pm+pp+outstanding_dividend+subscription-parent_support
      draw=min(max(0.,required-available),max(0.,100.-debt));available+=draw
      assert available>=required-1e-7
      repaid=min(max(0.,available-required),debt+draw);available-=repaid;debt+=draw-repaid
      normal=.8*max(0.,ebit*.85+p_fin*.85+subsidiary_profit+declaration)
      extra=.2*turnover if year>=6 else 0.
      distribution=max(0.,min(normal+extra,pre,available-required))
      pre-=distribution;pc=available-distribution
      per_share=distribution/shares;payments.append(per_share);accumulated_dps+=per_share
      outstanding_dividend=declaration;old_wc=new_wc
      pd-=pm;sd-=sm;ld-=lm
      if year==8:pe=0.
      if year==10:se=0.
      rebuilt.append(dict(year=year,P_cash=pc,S_cash=sc,L_cash=lc,P_retained=pre,S_retained=sre,S_capital=s_capital,S_reserve=sres,L_retained=lre,shares=shares,dividend=per_share))
    current=sum(payment*math.pow(1+r,-i) for i,payment in enumerate(payments,1))
    current+=payments[-1]*(1+g)/(r-g)*math.pow(1+r,-80)
    future=sum(payments[i-1]*math.pow(1+r,-(i-5)) for i in range(6,81))
    future+=payments[-1]*(1+g)/(r-g)*math.pow(1+r,-75)
    return {'current':current,'TV5':future,'first5':rebuilt[:5],'last':rebuilt[-1],'annual_trace':rebuilt}

@pytest.mark.parametrize('r,g,index',[(.105,.02,0),(.095,.03,1),(.11,.025,2)])
def test_focus_raw_80year_entity_chain(r,g,index):
 out=json.loads((ROOT/'002315/models/2026-Q3-output.json').read_text());v=independently_rebuild(r,g)
 if index<2:
  target=out['scenarios']['base'][index];expected=target['current'];tv=target['year5'];trace=target['annual_trace']
 else:
  target=out['sensitivity']['discount_11pct'];expected=target['value'];trace=target['annual_trace'];tv=sum(x['dps']/(1+r)**(x['year']-5) for x in trace[5:])+trace[-1]['dps']*(1+g)/(r-g)/(1+r)**75
 assert v['current']==pytest.approx(expected,abs=1e-7)
 assert v['TV5']==pytest.approx(tv,abs=1e-7)
 for a,b in zip(v['annual_trace'],trace):
  for k in ['P','S','L']:
   assert a[k+'_cash']==pytest.approx(b[k]['cash'],abs=1e-7)
   assert a[k+'_retained']==pytest.approx(b[k]['retained'],abs=1e-7)
  assert a['S_capital']==pytest.approx(b['states']['S']['capital'],abs=1e-7)
  assert a['S_reserve']==pytest.approx(b['S']['statutory'],abs=1e-7)
