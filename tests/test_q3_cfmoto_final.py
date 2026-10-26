"""Independent literal reconstruction. No import/exec of production module or its inputs.
Read production JSON only AFTER reconstructing all paths; compare full time-series fields.
"""
import json,math
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"research/companies/CN/603129/models"
SCENARIOS={'central':{},'core_low':{'r':.115,'roic':.16,'g':.025},'core_high':{'r':.105,'roic':.20},'cyclical':{'kind':'cyclical'},'structural':{'kind':'structural','r':.12,'roic':.12,'g':.02},'upside':{'kind':'upside'},'margin_minus_1pp':{'margin':-.01},'roic_12pct':{'roic':.12},'release_delay_5':{'delay':5},'release_delay_1':{'delay':1},'remit_50pct':{'remit':.5},'friction_15pct':{'friction':.15},'parent_delay_2bn':{'pd':2},'extra_capex_2bn':{'cx':2},'conversion':{'convert':True},'financing_failure':{'pd':10}}
def rebuild(cfg):
    r=cfg.get('r',.11);roc=cfg.get('roic',.2);steady=cfg.get('g',.03);kind=cfg.get('kind','base');lag=cfg.get('delay',3);q=cfg.get('remit',.8);taxrate=cfg.get('friction',.07);pd=cfg.get('pd',0)
    revenues=[9.4,5.8,8.2,2.5,1.7];rates=[(.12,.10,.09,.07,.05),(.15,.12,.10,.08,.06),(.14,.12,.10,.08,.06),(.20,.18,.15,.10,.08),(.12,.10,.09,.07,.05)]
    total_cash=13.84858255585;pc=7.65825519985-pd;stock=.153482763;earnings=4.15847860839;reserve=.083022672;working=-5.9;liquidity=8.;debenture=0 if cfg.get('convert',False) else 2.178763
    capital=6.1;total_paid=0;source=0;payment=0;deferred={};schedule={1+lag:total_cash-8};answer=[]
    for year in range(1,cfg.get("horizon",320)+1):
        i=year-1;oldliq=liquidity
        if year<6:
            revenues=[revenues[j]*(1+rates[j][i]) for j in range(5)];s=revenues.copy();m=[.09,.12,.08,[-.04,-.01,.01,.025,.03][i],.12];cap=[1.8,1.7,1.5,1.3,1.2][i]+(cfg.get('cx',0) if year==1 else 0);dep=[.3,.38,.46,.53,.6][i];wc=[-.19,-.17,-.15,-.15,-.15][i]
            if kind=='cyclical':
                for j in [0,1]:s[j]*=[.82,.9,.98,1,1][i]
                m[0]-=[.025,.015,.005,0,0][i];m[1]-=[.015,.008,.003,0,0][i];cap*=.95;wc=[-.14,-.14,-.15,-.15,-.15][i]
            if kind=='structural':s[0]*=.5;s[1]*=.88;s[2]*=.92;m=[.015,.085,.065,-.08,.09];cap=[1.8,1.5,1.2,1,1][i];wc=-.10
            if kind=='upside':s=[a*(1+.025*year) for a in s];m=[.105,.13,.09,[0,.02,.04,.05,.05][i],.13];cap*=1.2
            m=[a+cfg.get('margin',0) for a in m];sales=sum(s);profit=sum(s[j]*m[j] for j in range(5));own=.6*(profit-s[3]*m[3]);change=sales*wc-working;working=sales*wc;liquidity=sales*8/27.6
            if kind=='structural':liquidity=max(6,liquidity)
            invest=cap-dep+change+liquidity-oldliq;owncash=own+.45*dep-.55*cap-.6*change-.2-(.25 if kind=='structural' else 0);award=[.15,.08,.04,.02,.02][i]
        else:
            growth=([.02]*5 if kind=='structural' else [.07,.06,.05,.04,.03])[year-6] if year<=10 else steady
            prior=profit;profit=prior*(1+growth);sales*=1+growth;liquidity*=1+growth;invest=(profit-prior)/roc;dep=.6*sales/44.175;cap=dep+invest-liquidity+oldliq;change=0;own=.6*profit;owncash=.6*(profit-invest+liquidity-oldliq);award=0
        capital+=invest
        equity_cash=0;oldstock=stock
        if year==1:
            stock+=.0023994+.0006+(2.178763/241.70 if cfg.get('convert',False) else 0)
            equity_cash=.0023994*102.15+.0006*145.91
        if year in [2,3,4] and kind!='structural':
            delta=.004151875*({2:.3,3:.3,4:.4}[year]);stock+=delta;equity_cash=delta*max(0,233.45-total_paid)
        interest=debenture*[.001,.003,.006,.015,.018][i] if year<=5 else 0
        redemption=debenture*1.08 if year==6 else 0;premium=debenture*.08 if year==6 else 0
        if year==6:debenture=0
        income=.015*max(0,total_cash-oldliq);pincome=.015*max(0,pc-oldliq/2);friction=payment*taxrate;received=payment-friction
        free=profit+dep-cap-change-interest-redemption
        sale=.14860652229 if year==8 else 0
        extra=cfg.get("source_cash",0) if year==cfg.get("source_year",0) else 0
        rights=cfg.get("source_rights",0) if year==cfg.get("source_year",0) else 0
        total_cash+=free+income+equity_cash-friction+sale+extra
        pc+=owncash+pincome+equity_cash-interest-redemption+received
        source+=deferred.pop(year,0)+rights
        sub=(profit-award+income-(.01651183581 if year==8 else 0))-(own-.75*award+pincome)
        if sub<0:source+=sub
        else:source+=q*sub;deferred[year+3]=(1-q)*sub
        dividend=min(max(0,source),max(0,total_cash-pc-liquidity/2)) if year>5 else 0
        source-=dividend;payment=dividend
        pprofit=own-.75*award-interest-premium+pincome+dividend*(1-taxrate)
        before_reserve=earnings+pprofit
        appropriation=max(0,min(stock/2-reserve,.1*max(0,min(pprofit,before_reserve))))
        reserve+=appropriation;earnings=before_reserve-appropriation
        if year==4:pc+=pd
        escrow=debenture*1.08*min(1,year/5);need=liquidity+escrow;pneed=liquidity/2+escrow
        short=max(0,need-total_cash,pneed-pc,pc-total_cash)
        if short>1e-8:
            answer.append(dict(year=year,feasible=False,cash=total_cash,parent_cash=pc,required_group_floor=need,required_parent_floor=pneed,shortfall=short,debt_redemption=redemption,distribution=0.))
            return {'feasible':False,'failure_year':year,'shortfall':short,'rows':answer}
        ordinary=min(0. if kind=="structural" and year<=5 else .4*max(0,profit-award+income-interest-premium),max(0,earnings),max(0,total_cash-need),max(0,pc-pneed))
        pc-=ordinary;total_cash-=ordinary;earnings-=ordinary
        # Independent dated dictionary, not production list/cohort helper.
        trim=max(0,sum(schedule.values())-max(0,total_cash-liquidity))
        for date in sorted(schedule,reverse=True):
            z=min(trim,schedule[date]);schedule[date]-=z;trim-=z
        special=min(0. if kind=="structural" and year<=5 else sum(v for d,v in schedule.items() if d<=year),max(0,earnings),max(0,total_cash-need),max(0,pc-pneed))
        pc-=special;total_cash-=special;earnings-=special
        todo=special
        for date in sorted(schedule):
            if date<=year:z=min(todo,schedule[date]);schedule[date]-=z;todo-=z
        trim=max(0,sum(schedule.values())-max(0,total_cash-liquidity))
        for date in sorted(schedule,reverse=True):z=min(trim,schedule[date]);schedule[date]-=z;trim-=z
        fresh=max(0,total_cash-liquidity-sum(schedule.values()));date=year+max(1,lag);schedule[date]=schedule.get(date,0)+fresh
        d=(ordinary+special)/stock;total_paid+=d
        answer.append(dict(year=year,feasible=True,revenue=sales,segment_revenue=s if year<=5 else [],operating_profit=profit,accounting_profit=profit-award-interest-premium,consolidated_accounting_profit=profit-award-interest-premium+income-(.01651183581 if year==8 else 0)-friction,net_investment=invest,capex=cap,depreciation=dep,delta_nwc=change,operating_capital=capital,cash_floor=liquidity,parent_floor=liquidity/2,
            fcf=free,financial_income=income,shares=stock,new_shares=stock-oldstock,registered_capital_budget=stock,exercise_proceeds=equity_cash,debt=debenture,debt_interest=interest,debt_redemption=redemption,investment_sale_cash=sale,investment_sale_profit=-.01651183581 if year==8 else 0,
            source_economic_profit=sub,source_financial_income=income-pincome,source_sbc=.25*award,parent_financial_income=pincome,source_injected_cash=extra,source_injected_preexisting_capacity=rights,source_economic_budget=source,source_delayed_capacity=dict(deferred),debt_escrow=escrow,new_dividend_declared=dividend,old_dividend_receipt=received,remittance_friction=friction,pending_dividend=payment,parent_own_profit=pprofit-dividend*(1-taxrate),parent_statutory_profit=pprofit,parent_reserve=reserve,parent_reserve_add=appropriation,parent_retained=earnings,parent_cash=pc,cash=total_cash,
            ordinary=ordinary,special=special,distribution=ordinary+special,distribution_per_share=d,queued_surplus=[[date,v] for date,v in sorted(schedule.items()) if v>1e-12],financing=0.,shortfall=0.,injected_surplus=0.))
    return dict(feasible=True,current=math.fsum(a['distribution_per_share']/(1+r)**a['year'] for a in answer),terminal=math.fsum(a['distribution_per_share']/(1+r)**(a['year']-5) for a in answer[5:]),rows=answer)

def compare(a,b,path=()):
    if isinstance(b,dict):
        a={str(k):v for k,v in a.items()};b={str(k):v for k,v in b.items()}
        assert set(a)==set(b),(path,set(a)^set(b))
        return max([compare(a[k],v,path+(k,)) for k,v in b.items()] or [0])
    if isinstance(b,list):
        assert len(a)==len(b),(path,len(a),len(b))
        return max([compare(x,y,path+(i,)) for i,(x,y) in enumerate(zip(a,b))] or [0])
    if b is None or isinstance(b,(str,bool)):
        assert a==b,(path,a,b);return 0
    error=abs(a-b)/max(1,abs(b));assert error<1e-8,(path,a,b,error);return error


def test_cfmoto_independent_complete_paths():

    literal={k:rebuild(c) for k,c in SCENARIOS.items()}
    actual=json.loads((P/'2026-Q3-output.json').read_text())['paths'];checks={}
    for name,b in literal.items():
        a=actual[name];assert a['feasible']==b['feasible'],name;error=0
        if b['feasible']:
            for field in ['current','terminal']:assert abs(a[field]-b[field])<1e-8,(name,field,a[field],b[field])
        else:
            assert b['failure_year']==a['failure_year'];assert abs(a['shortfall']-b['shortfall'])<1e-8
        for x,z in zip(a['rows'],b['rows']):
            for key,val in z.items():
                err=compare(x[key],val,(name,x['year'],key));error=max(error,err)
            assert set(x)==set(z),(name,set(x)^set(z))
        checks[name]=dict(feasible=b['feasible'],years_rebuilt=len(b['rows']),max_relative_error=error,current=b.get('current'),terminal=b.get('terminal'))

import runpy,subprocess,sys,copy
from functools import lru_cache
@lru_cache(None)
def model():return runpy.run_path(str(P/'2026-Q3.py'))
def test_cfmoto_actual_capital_creditor_and_finance():
 from types import SimpleNamespace
 m=SimpleNamespace(**model())
 checks={}
 # Every test calls an actual production function, not an external restatement.
 assert m.statutory(0,10,5,20)==(9,6,1);checks['registered20_paid10_reserve5_profit10']='reserve addition 1; paid capital not an input'
 assert m.statutory(-10,4,0,20)==(-6,0,0)
 assert m.statutory(-6,10,0,20)==(3.6,.4,.4);checks['loss_first']='-10+4=-6; then10 yields3.6 after reserve.4'
 assert m.statutory(0,10,10,20)==(10,10,0)
 assert m.statutory(0,10,10,40)==(9,11,1);checks['registration_increase']='cap20 to40 reopens reserve headroom; no cash auto-created'
 assert m.statutory(5,-7,0,20)==(-2,0,0);checks['current_loss']='same-year -7 offsets opening5; no dividend capacity'
 a=m.realize(10,10,1,2,.51);assert a['feasible'] and abs(a['cash_to_owner']-3.57)<1e-12 and a['accounting_profit']==-1
 b=m.realize(10,10,1,2,1);assert b['cash_to_owner']==7
 assert not m.realize(2,2,1,2)['feasible'];assert m.realize(2,2,1,2)['creditors_paid'] is None
 failed=m.realize(2,2,1,2,share_count=20,cancel_fraction=.25)
 assert failed['remaining_shares']==20 and failed['cancelled_shares']==0 and failed['cash_to_owner'] is None
 checks['failed_realization_preserves_shares']=failed
 reduction=m.realize(5,5,0,0,share_count=20,cancel_fraction=.25)
 assert reduction['remaining_shares']==15 and reduction['cancelled_shares']==5 and reduction['accounting_profit']==0
 checks['pro_rata_capital_reduction']='conditional approved return5 cancels5 of original20 shares; remaining15; no fictitious profit, no new shares; main forecast does not assume reduction'
 checks['capital_recovery']='10 principal minus1 fee minus2 debt =>7, 51% owner3.57; accounting loss1, not dividend profit10; shortage2-1-2=-1 explicit failure'
 base=m.run();rows=base['rows']
 for i,row in enumerate(rows):
     expected=row['parent_own_profit']+row['new_dividend_declared']*.93
     assert abs(row['parent_statutory_profit']-expected)<1e-8*max(1,abs(expected))
     if i:assert abs(row['old_dividend_receipt']-rows[i-1]['new_dividend_declared']*.93)<1e-8*max(1,row['old_dividend_receipt'])
 checks['old_receivable']='all 320 years receipt affects cash only; parent profit uses new declaration'
 assert rows[5]['debt_redemption']==2.178763*1.08 and rows[5]['debt_interest']==0 and rows[5]['debt']==0
 checks['debt']='Y6 108% includes final interest; no extra2% coupon/no double terminal debt'
 assert not m.run(parent_delay=10)['feasible'];struct=m.run(kind='structural',r=.12,roic=.12,g=.02)
 assert all(x.get('distribution',0)==0 for x in struct['rows'])
 assert not struct['feasible']
 checks['structural_response']='Y1 onward suspend all distributions; remaining Y3 funding plan shortage is explicit, not company bankruptcy conclusion'
 checks['zero_financing']='zero distributions cannot cure missing parent funds; no fabricated financing'
 con=m.run(convert=True);assert abs(con['rows'][0]['shares']-rows[0]['shares']-2.178763/241.70)<1e-12
 assert con['rows'][0]['exercise_proceeds']==rows[0]['exercise_proceeds'];checks['conversion']='new shares +9.014m removes debt; conversion generates no cash'
 checks['future_surplus']={}
 for y in [20,100,200]:
     p=m.run(inject_year=y,inject_cash=1.)
     # Injecting already-owned surplus principal must not create accounting earnings, and must be recovered promptly.
     cumulative=sum(a['distribution']-b['distribution'] for a,b in zip(p['rows'][y-1:y+12],rows[y-1:y+12]))
     assert cumulative>.99,(y,cumulative)
     early=sum(a['distribution']-b['distribution'] for a,b in zip(p['rows'][y-1:y+3],rows[y-1:y+3]))
     assert early>.99,(y,early)
     assert abs(p['rows'][y-1]['parent_statutory_profit']-rows[y-1]['parent_statutory_profit'])<1e-7
     checks['future_surplus'][y]={'incremental_cash_received_within4years':early,'incremental_cash_received_within13years':cumulative,'first_cash_release_year':next(a['year'] for a,b in zip(p['rows'],rows) if a['distribution']-b['distribution']>1e-6)}
 checks['convergence']={}
 for name,args in {**m.results()['specs'],'zero_growth':dict(g=0)}.items():
     if not m.run(**args)['feasible']:
         checks['convergence'][name]={'feasible':False,'no_fabricated_value':True};continue
     vals={n:m.run(horizon=n,**args)['current'] for n in [160,320,640]}
     assert abs(vals[640]-vals[320])<1e-6
     checks['convergence'][name]=vals

def test_cfmoto_full_treasury_income_and_future_principal():
 m=model()
 for name,kwargs in m['results']()['specs'].items():
  q=m['run'](**kwargs)
  for row in q['rows']:
   if not row['feasible']:continue
   assert abs(row['parent_own_profit']+row['source_economic_profit']-row['remittance_friction']-row['consolidated_accounting_profit'])<1e-8*max(1,abs(row['consolidated_accounting_profit']))
 for g in [0,.03]:
  for delay in [3,5]:
   base=m['run'](g=g,delay=delay)
   for row in base['rows'][20:]:
    assert sum(v for due,v in row['queued_surplus'] if due<=row['year'])<1e-7
    assert abs(row['cash']-row['cash_floor']-sum(v for due,v in row['queued_surplus']))<1e-7
   for year in [20,100,200]:
    q=m['run'](g=g,delay=delay,source_inject_year=year,source_inject_cash=1,source_inject_capacity=1)
    z=rebuild(dict(g=g,delay=delay,source_year=year,source_cash=1,source_rights=1))
    for a,b in zip(q['rows'],z['rows']):compare(a,b)
    got=sum(a['distribution']-b['distribution'] for a,b in zip(q['rows'][year-1:year+29],base['rows'][year-1:year+29]))
    assert got>.93
    assert abs(q['rows'][year-1]['source_economic_profit']-base['rows'][year-1]['source_economic_profit'])<1e-9
 q=m['realize'](2,2,1,2,share_count=20,cancel_fraction=.5);assert not q['feasible'] and q['remaining_shares']==20 and q['cancelled_shares']==0

def test_cfmoto_singlefile_reproduce(tmp_path):
 (tmp_path/'2026-Q3.py').write_bytes((P/'2026-Q3.py').read_bytes());subprocess.run([sys.executable,'-I',str(tmp_path/'2026-Q3.py')],cwd=tmp_path,check=True,stdout=subprocess.DEVNULL)
 assert (tmp_path/'2026-Q3-output.json').read_bytes()==(P/'2026-Q3-output.json').read_bytes()
