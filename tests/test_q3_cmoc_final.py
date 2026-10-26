"""Independent literal rebuild; does NOT import/read production model or its parameters.
Units billion CNY. Equations transcribed from evidence + explicitly adopted budgets.
Only comparison stage reads output. This engine constructs all years from literals.
"""
import json
from pathlib import Path

def rebuild(cost_up=False,fee=.05,delay=0):
    names=['TFM','KFM','BR','BG','IXM','ODIN']
    cash=[14,7,1.5,1.5,8,0]; debt=[.8,.4,.5,.5,34,0]
    own=[.8,.7125,1,1,1,1];floor=[3,2,.7,.7,5,.5];limits=[4,4,2,2,42,0]
    life=[15,15,20,15,30,29];wc=[4,2,1,.6,36.533455,.5];close=[1,.6,.4,.3,0,.6]
    earnings=[0.]*6;inventory=[107718.6,88133.4];pending=[];dead=set()
    parent=10.186334732;mother=4.186334732;borrow=22.159167733;retained=1.36615118;basis=40.25373746363
    capital=30.73797280675;reg=4.2788620352;sh=21.394310176;pool=0.;done=False;rows=[]
    for year in range(1,33):
        growth=1.02**(year-1);profit=0;incoming=0;newdiv=0;caprecv=0;disposal_gain=0;ni_list=[]
        for j in range(6):
            if j in dead:ni_list.append(0);continue
            maintenance=0;depreciation=0;stock=0;settlement=0
            if j<2:
                copper=([560000]*8+[500000,450000,400000,350000,300000,250000,200000] if j==0 else [260000,310000]+[340000]*6+[250000,200000,150000,120000,100000,80000,60000])[year-1]
                ratio=.55 if j==0 else .45
                produced=([80000,70000,60000]+[45000]*7+[35000,25000,15000,10000,0])[year-1]*ratio
                sale=min(([30000,40000,60000]+[70000]*7+[60000,50000,40000,30000,20000])[year-1]*ratio,inventory[j]+produced)
                stock=(produced-sale)*10000*6.9/1e9*growth;inventory[j]+=produced-sale
                sales=(copper*10500*.965+sale*35000*.9)*6.9/1e9*growth
                expenses=(copper*4600*(1.15 if cost_up else 1)+sale*10000)*6.9/1e9*growth+.35*growth+6.563914669/15*growth*ratio
                depreciation=copper*700*6.9/1e9*growth
                maintenance=(copper*650*6.9/1e9+((2 if j==0 else 1) if 7<=year<=10 else 0))*growth
                if j==1 and year==1:maintenance+=2.5
                if j==0 and year<=3:maintenance+=1
                settlement=(.7 if j==0 and year<=2 else 0)+(10.540270406/5 if j==1 and year<=5 else 0)
                tax=.35
            elif j==2:
                sales=7.2*growth;expenses=5.3*growth;depreciation=.5*growth;maintenance=.65*growth;tax=.34
            elif j==3:
                ounces=225000*(1 if year<=7 else max(.35,1-.07*(year-7)))
                sales=ounces*3200*6.9/1e9*growth;expenses=ounces*1900*6.9/1e9*growth;depreciation=.35*growth;maintenance=.55*growth;tax=.2
            elif j==4:
                sales=240*growth;expenses=(240-(1.3/.853+34*.045))*growth;depreciation=.06*growth;maintenance=depreciation;stock=36.533455*.02*growth;tax=.147
            else:
                ounces=0 if year<=3 else (180000 if year==4 else (280000 if year==5 else 371000))
                copper=0 if year<=3 else (10000 if year==4 else 18597)
                sales=(ounces*3200*(1-.044*.82)+copper*10500)*6.9/1e9*growth;expenses=(ounces*1300*6.9/1e9+.15)*growth
                depreciation=.45*growth if ounces else 0;maintenance={1:2.5,2:3,3:2.5,6:2,9:2}.get(year,.5 if ounces else .1)*growth;stock=.5 if year==4 else 0;tax=.3
            ebit=sales-expenses-depreciation
            income=ebit-max(0,ebit)*tax
            if j==1 and year<=5:income-=.05*10.540270406*(1-(year-1)/5)
            flow=income+depreciation-maintenance-stock-settlement
            income-=debt[j]*.045;flow-=debt[j]*.045
            income+=cash[j]*.015;flow+=cash[j]*.015
            ni_list.append(income);profit+=income*own[j];earnings[j]+=income
            repay=min(debt[j],.25) if j!=4 else 0;cash[j]+=flow-repay;debt[j]-=repay
            if j==5 and cash[j]<floor[j]:
                contribution=floor[j]-cash[j];mother-=max(0,contribution-(parent-mother));parent-=contribution;cash[j]+=contribution;basis+=contribution
            draw=max(0,floor[j]-cash[j]);debt[j]+=draw;cash[j]+=draw
            assert debt[j]<=limits[j]+1e-8
            if j==0 and year==1:cash[j]-=1.802341533;incoming+=1.802341533
            if year==life[j]:
                noncash=wc[j]*(growth*1.02 if j==4 else 1)
                if j<2:noncash+=inventory[j]*10000*6.9/1e9*.75
                pot=cash[j]+noncash*.85-debt[j]-close[j]*growth
                assert pot>=0
                pending.append([year+1,pot*own[j]*(1-fee),'capital']);cash[j]=0;debt[j]=0;dead.add(j)
            else:
                budget=(.35 if year<=5 else .85)*max(0,income)+(.05 if year<=5 else .5)*max(0,cash[j]-floor[j])
                declare=min(max(0,earnings[j]),max(0,cash[j]-floor[j]),budget)
                cash[j]-=declare;earnings[j]-=declare;pending.append([year+delay,declare*own[j]*(1-fee),'dividend'])
        for due,amount,kind in pending:
            if due<=year:
                incoming+=amount
                if kind=='dividend':newdiv+=amount
                else:
                    caprecv+=amount;recovered=min(basis,amount);disposal_gain+=amount-recovered;basis-=recovered
        pending=[x for x in pending if x[0]>year]
        if len(dead)==6 and not pending and not done:disposal_gain-=basis;basis=0;done=True
        domestic=(3.2 if year<=8 else max(0,3.2-.64*(year-8)))*growth if year<=13 else 0
        domestic+=(.45 if year<=10 else 0)-(.6 if year<=15 else .2)*growth
        interest=borrow*.045;yield_=parent*.015;profit+=domestic-interest+yield_
        income=domestic+newdiv-interest+yield_+disposal_gain-max(0,disposal_gain)*.25
        retained+=income # verified starting statutory reserve already above registered / 2
        flow=domestic+(.3-.45)*growth*(year<=13)-interest+yield_
        release=5.948578055-.228973 if year==1 else (7.951387165+.228973 if year==10 else 0)
        if year in (16,31):release+=2 if year==16 else .871809985
        parent+=flow+incoming+release-max(0,disposal_gain)*.25;mother+=flow+incoming+release-max(0,disposal_gain)*.25
        repay=min(borrow,8.28 if year==1 else (5 if year<=4 else 1));mother-=max(0,repay-(parent-mother));parent-=repay;borrow-=repay
        draw=max(0,(3 if year<32 else 0)-parent);parent+=draw;borrow+=draw;assert borrow<=36+1e-8
        repaypool=min(pool,max(0,mother-1));mother-=repaypool;pool-=repaypool
        lend=min(max(0,1-mother),max(0,parent-mother),max(0,10-pool));mother+=lend;pool+=lend
        target=.3*max(0,profit) if year<=5 else max(.75*max(0,profit),.9*max(0,parent-15))
        dividend=min(target,max(0,retained),max(0,mother-1),max(0,parent-3));retained-=dividend
        redemption=0
        if 15<=year<32:
            redemption=min(max(0,target-dividend),max(0,parent-15-dividend),max(0,mother-1-dividend),max(0,capital-.5))
            scale=1-redemption/capital;capital-=redemption;reg*=scale;sh*=scale
        if year==32:redemption=parent-borrow-.2*growth-dividend;parent-=borrow+.2*growth;borrow=0
        payment=dividend+redemption;parent-=payment;mother-=min(mother,payment)
        rows.append({'year':year,'d':payment/21.394310176,'cash':parent,'profit':profit,'basis':basis,'legal':retained})
    return rows

def value(rows,rate):
    return sum(row['d']/(1+rate)**row['year'] for row in rows)


import runpy,subprocess,sys,hashlib
from functools import lru_cache
D=Path(__file__).resolve().parents[1]/"research/companies/CN/603993/models"
@lru_cache(None)
def model():return runpy.run_path(str(D/'2026-Q3.py'))
@lru_cache(None)
def output():return json.loads((D/'2026-Q3-output.json').read_text())
def test_cmoc_independent_paths():
 for n,kw in [('base',{}),('cost_plus_15',{'cost_up':True}),('friction_10',{'fee':.1}),('upstream_delay_2',{'delay':2})]:
  own=rebuild(**kw);actual=output()['scenarios'][n]
  assert len(own)==len(actual['annual'])
  for a,b in zip(own,actual['annual']):
   for x,y in [('d','distribution_per_share'),('cash','parent_cash'),('profit','common_profit'),('basis','hk_investment_basis'),('legal','parent_legal_retained')]:assert abs(a[x]-b[y])<1e-8,(n,a['year'],x,a[x],b[y])
  for r,v in zip([.115,.10],actual['valuation']):assert abs(value(own,r)-v['pv'])<1e-9

def test_cmoc_actual_legal_and_creditor_functions():
 m=model();assert all(m['actual_tests']().values())
 assert m['china_profit'](-4,0,3,20)==(-1,0,0)
 assert m['china_profit'](-4,0,10,20)==(5.4,.6000000000000001,.6000000000000001)
 assert m['recover_basis'](3,8,True)==(0.,3,-5)
 assert m['capital_reduce'](40,10,90,100)==(6.,54.,60.)
 for args in [(0,0,1,0,1),(1,0,0,2,1),(3,2,6,0,.8)]:
  try:m['disposal'](*args)
  except ValueError:pass
  else:raise AssertionError('creditor or fee shortage valued')
 try:m['run'](force_need=1000)
 except ValueError:pass
 else:raise AssertionError('unfunded path priced')

def test_cmoc_all_actual_paths_and_capital_recovery():
 m=model()
 for n,s in output()['scenarios'].items():
  assert s['feasible'];rows=m['run'](n,horizon=34 if n=='exit_delay_3' else 32)
  assert rows==s['annual']
  last=rows[-1]
  for k in ['parent_cash','parent_debt','settlement_cash','hk_investment_basis','registered','shares_outstanding']:assert abs(last[k])<1e-7
  assert all(abs(r['cash_conservation_error'])<2e-7 for r in rows)
  assert abs(sum(r['parent_old_receivable_collection'] for r in rows)-1.802341533)<1e-12
  for r in [.115,.10]:
   a=m['valuation'](rows,r)
   for N in [64,128,512]:assert m['valuation'](rows+[{'distribution_per_share':0.}]*(N-len(rows)),r)==a

def test_cmoc_single_file_regeneration(tmp_path):
 code=(D/'2026-Q3.py').read_bytes();(tmp_path/'2026-Q3.py').write_bytes(code)
 subprocess.run([sys.executable,'-I',str(tmp_path/'2026-Q3.py')],cwd=tmp_path,check=True,stdout=subprocess.DEVNULL)
 assert (tmp_path/'2026-Q3-output.json').read_bytes()==(D/'2026-Q3-output.json').read_bytes()
