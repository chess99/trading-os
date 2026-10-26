"""福耀玻璃 2026Q3; 单位十亿元、十亿股。所有预测为研究预算，不使用价格。"""
import json, math
from pathlib import Path
SHARES=2.609743532
CASH0=21.487115845+1.009542675-0.689662926
# 其他流动负债整体作为债务性付款上限；含少量待转税项，保守差额<=0.24bn。
DEBT0=sum([9.848754943,3.709805867,5.081237775,1.499759929,.297915057,.041716237,2.083572932])
PARENT0=18.992899061-.689662926
LEGAL0=8.667059178

def pv(cfs,r,terminal=0):
    return sum(c/(1+r)**(i+1) for i,c in enumerate(cfs))+terminal/(1+r)**len(cfs)

def tail(nopat,r,g=.025,roic=.15,growths=(.04,.035,.03,.0275,.025)):
    flows=[]
    for grow in growths:
        nopat*=1+grow
        flows.append(nopat*(1-grow/roic))
    terminal=nopat*(1+g)*(1-g/roic)/(r-g)
    return pv(flows,r,terminal),flows,terminal

def run(case='base',r=.095,margin_shift=0):
    configs={
      'base':dict(rev=[47,50,53,56,58.8],m=[.18]*5,cap=[6.3,6,5.7,5.3,5],da=[3,3.3,3.5,3.7,3.9],wc=.12,up=.75,collect=[1]*5,g=.025,roic=.15,delay=0,advance=1),
      'cycle':dict(rev=[43,45,49,54,58.8],m=[.155,.165,.175,.18,.18],cap=[6,5.4,5.3,5.3,5],da=[3,3.2,3.4,3.6,3.9],wc=.14,up=.65,collect=[.75,.85,1,1,1],g=.025,roic=.15,delay=0,advance=1.5),
      'structural':dict(rev=[45,46,47,48,49],m=[.16,.15,.145,.14,.14],cap=[6.3,5.8,5.5,5.2,5],da=[3,3.3,3.5,3.7,3.9],wc=.16,up=.55,collect=[.75]*5,g=.01,roic=.09,delay=5,advance=2),
      'upside':dict(rev=[49,53,57,61,65],m=[.185,.19,.19,.19,.19],cap=[6.8,6.5,6.1,5.8,5.5],da=[3,3.4,3.8,4.1,4.4],wc=.11,up=.80,collect=[1]*5,g=.03,roic=.18,delay=0,advance=1),
      'remit_delay':dict(rev=[47,50,53,56,58.8],m=[.18]*5,cap=[6.3,6,5.7,5.3,5],da=[3,3.3,3.5,3.7,3.9],wc=.12,up=.75,collect=[0,0,1,1,1],g=.025,roic=.15,delay=1,advance=5)
    }
    c=configs[case]; cash=CASH0; debt=DEBT0; pc=PARENT0; legal=LEGAL0; ar=.073878614
    prior=46.5; rows=[]; fcffs=[]; divs=[]; capital=40.0
    for i,rev in enumerate(c['rev']):
        nopat=rev*(c['m'][i]+margin_shift) # common-owner operating NOPAT budget; minorities excluded from margin
        reserve=.08*rev; oldreserve=.08*prior
        reinvest=c['cap'][i]-c['da'][i]+c['wc']*(rev-prior)+(reserve-oldreserve)
        fcff=nopat-reinvest; fcffs.append(fcff)
        interest=(cash*.02-debt*.03)*.8
        fce=fcff+interest+(reserve-oldreserve) # physical cash includes minimum cash increase
        profit=nopat+interest
        declared=max(0,nopat*c['up'])
        received=declared*c['collect'][i]
        recovery=ar*(.9 if c['collect'][i]==1 else 0)
        ar+=declared-received-recovery
        # parent own legal profit/cash -0.45 includes own operation, capex and finance;
        # these are components of consolidated flows, not added group expenses.
        legal+=declared-.35
        before_pc=pc+received+recovery-.45-c['advance']
        target=profit*.60
        # no debt-funded dividend: cap by operating cash, consolidated reserve and parent liquidity/legal.
        dividend=max(0,min(target,fce,cash+fce-reserve,before_pc-3,legal))
        # funding only for operating shortfall; draw as needed, dilution absent with <2bn line.
        need=max(0,reserve-(cash+fce-dividend),3-(before_pc-dividend))
        assert debt-DEBT0+need<=2.0, 'Funding path infeasible: exceeds research 2bn incremental borrowing ceiling (not committed facility)'
        debt+=need; cash+=fce-dividend+need; pc=before_pc-dividend+need; legal-=dividend
        capital+=reinvest
        assert cash>=reserve-1e-8 and pc>=3-1e-8 and legal>=-1e-8
        # explicit remainder at operating subsidiaries; parent advances are internal transfers.
        childcash=cash-pc
        assert childcash>=-1e-8
        rows.append(dict(year=i+1,revenue=rev,nopat=nopat,net_profit=profit,capex=c['cap'][i],da=c['da'][i],reinvestment=reinvest,fcff=fcff,net_finance_income=interest,free_equity_cash=fce,dividend=dividend,dps=dividend/SHARES,cash=cash,debt=debt,minimum_cash=reserve,parent_cash=pc,parent_declared=declared,parent_received=received,parent_old_receivable_recovery=recovery,parent_dividend_receivable=ar,parent_legal_profit=legal,child_cash=childcash,new_borrowing=need,capital=capital))
        divs.append(dividend); prior=rev
    grows=(.04,.035,.03,.0275,c['g']) if case not in ('structural','upside') else ((.015,.0125,.01,.01,.01) if case=='structural' else (.05,.045,.04,.035,.03))
    ev5,tailflows,tv10=tail(rows[-1]['nopat'],r,c['g'],c['roic'],grows)
    # Structural restriction affects EACH future cash vintage: 75% accessible immediately,
    # 25% payable five years later. This also scales the perpetual tail, not just existing cash.
    future_access_factor=.75+.25/(1+r)**5 if case=='structural' else 1.0
    ev5*=future_access_factor
    tailflows=[v*future_access_factor for v in tailflows]
    tv10*=future_access_factor
    # financial reserve retained at year 5; cash already excludes all five dividends.
    excess=max(0,cash-rows[-1]['minimum_cash'])
    parent_excess=min(excess,max(0,pc-3))
    trapped_excess=excess-parent_excess
    cash_delay_loss=trapped_excess*(1-1/(1+r)**c['delay'])
    eq5=ev5+cash-debt-rows[-1]['minimum_cash']-cash_delay_loss
    dcf=(pv(fcffs,r,ev5)+CASH0-DEBT0-.08*46.5)/SHARES
    holder=pv(divs,r,eq5)/SHARES
    return dict(case=case,rate=r,config=c,rows=rows,tail_fcff=tailflows,terminal_ev_year10=tv10,enterprise_value_year5=ev5,terminal_per_share=eq5/SHARES,current_value=holder,fcff_crosscheck=dcf,holder_pv_check=holder,cash_delay_loss=cash_delay_loss,future_access_factor=future_access_factor,terminal_pv_fraction=(ev5/(1+r)**5)/(pv(fcffs,r,ev5)),initial_cash=CASH0,initial_debt=DEBT0,shares=SHARES)

def tests():
    assert abs(pv([10]*5,0,100)-150)<1e-12
    # real tail function: no growth, NOPAT10,10% cost, five perpetuity coupons ->100
    assert abs(tail(10,.1,0,.15,(0,0,0,0,0))[0]-100)<1e-10
    b=run(); cash=CASH0
    for x in b['rows']:
        assert abs(x['cash']-(cash+x['free_equity_cash']-x['dividend']+x['new_borrowing']))<1e-9
        cash=x['cash']
    assert all(x['new_borrowing']==0 for x in b['rows'])
    assert run(margin_shift=-.01)['current_value']<b['current_value']
    return 'passed: production pv, tail hand cases; yearly cash conservation; constraints; sensitivity'

if __name__=='__main__':
    out={x:run(x) for x in ['base','cycle','structural','upside','remit_delay']}
    out['core_low']=run(r=.10);out['core_high']=run(r=.09)
    out['margin_minus_100bp']=run(margin_shift=-.01)
    # forward normalized NOPAT multiples: 13—15x, not copied from market/history.
    out['secondary_ev_nopat']=[(47*.18*k+CASH0-DEBT0-.08*46.5)/SHARES for k in (13,15)]
    out['tests']=tests()
    Path(__file__).with_name('2026-Q3-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
    print(json.dumps({k:{z:v[z] for z in ['current_value','terminal_per_share','holder_pv_check']} for k,v in out.items() if isinstance(v,dict) and 'current_value'in v},indent=2))
