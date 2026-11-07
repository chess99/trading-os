"""福耀玻璃 2026Q3; 单位十亿元、十亿股。所有预测为研究预算，不使用价格。"""
import json, math
from pathlib import Path
SHARES=2.609743532
CASH0=21.487115845+1.009542675-0.689662926
# 其他流动负债整体作为债务性付款上限；含少量待转税项，保守差额<=0.24bn。
DEBT0=sum([9.848754943,3.709805867,5.081237775,1.499759929,.297915057,.041716237,2.083572932])
PARENT0=18.992899061+1.001668493-.689662926
LEGAL0=8.667059178
REGISTERED=2.609743532
STATUTORY0=5.020531741
# Q3 mother p12: only identified loan/bond/lease financing, no intercompany payable.
PARENT_EXTERNAL_DEBT=sum([2.175355766,2.446064485,3.8177,1.499759929,.032579119])

def legal_step(profit, retained, reserve, registered, paid=None, policy=.10):
    # Paid capital deliberately does not enter threshold. Negative retained is prior loss.
    earnings=profit+retained
    eligible=max(0,profit-max(0,-retained))
    minimum=min(eligible*.10,max(0,registered*.50-reserve))
    appropriation=max(minimum,eligible*policy)
    return earnings-appropriation,reserve+appropriation,appropriation

def realize_principal(principal,ownership,delay,friction,r):
    # Economic net realizable value, NOT new accounting profit or immediate dividend.
    return principal*ownership*(1-friction)/(1+r)**delay

def finance_step(cash, operating, dividend, floor, ceiling):
    need=max(0,floor-(cash+operating-dividend))
    if need>ceiling+1e-10: return None
    return cash+operating-dividend+need,need

def owner_cash(nopat,g,roic,maintenance_above_da=0):
    return nopat*(1-g/roic-maintenance_above_da)

def capital_return(cash,shares,amount,cancel_fraction,fee=0):
    assert 0<=cancel_fraction<1 and amount+fee<=cash
    return dict(cash=cash-amount-fee,shares=shares*(1-cancel_fraction),holder_cash=amount,fee=fee)

def pv(cfs,r,terminal=0):
    return sum(c/(1+r)**(i+1) for i,c in enumerate(cfs))+terminal/(1+r)**len(cfs)

def tail(nopat,r,g=.025,roic=.15,growths=(.04,.035,.03,.0275,.025)):
    flows=[]
    for grow in growths:
        nopat*=1+grow
        flows.append(nopat*(1-grow/roic))
    terminal=nopat*(1+g)*(1-g/roic)/(r-g)
    return pv(flows,r,terminal),flows,terminal

def run(case='base',r=.095,margin_shift=0,policy=.10,friction=.01,recovery_lag=3,recovery_cost=.03,mode='corrected',parent_liquid_investments=True):
    configs={
      'base':dict(rev=[47,50,53,56,58.8],m=[.18]*5,cap=[6.3,6,5.7,5.3,5],da=[3,3.3,3.5,3.7,3.9],wc=.12,up=.75,collect=[1]*5,g=.025,roic=.15,delay=0,advance=1),
      'cycle':dict(rev=[43,45,49,54,58.8],m=[.155,.165,.175,.18,.18],cap=[6,5.4,5.3,5.3,5],da=[3,3.2,3.4,3.6,3.9],wc=.14,up=.65,collect=[.75,.85,1,1,1],g=.025,roic=.15,delay=0,advance=1.5),
      'structural':dict(rev=[45,46,47,48,49],m=[.16,.15,.145,.14,.14],cap=[6.3,5.8,5.5,5.2,5],da=[3,3.3,3.5,3.7,3.9],wc=.16,up=.55,collect=[.75]*5,g=.01,roic=.09,delay=5,advance=2),
      'upside':dict(rev=[49,53,57,61,65],m=[.185,.19,.19,.19,.19],cap=[6.8,6.5,6.1,5.8,5.5],da=[3,3.4,3.8,4.1,4.4],wc=.11,up=.80,collect=[1]*5,g=.03,roic=.18,delay=0,advance=1),
      'no_us_remit':dict(rev=[47,50,53,56,58.8],m=[.18]*5,cap=[6.3,6,5.7,5.3,5],da=[3,3.3,3.5,3.7,3.9],wc=.12,up=.65,collect=[1]*5,g=.025,roic=.15,delay=3,advance=1),
      'remit_delay':dict(rev=[47,50,53,56,58.8],m=[.18]*5,cap=[6.3,6,5.7,5.3,5],da=[3,3.3,3.5,3.7,3.9],wc=.12,up=.75,collect=[0,0,1,1,1],g=.025,roic=.15,delay=1,advance=5)
    }
    c=configs[case]; cash=CASH0; debt=DEBT0; pc=PARENT0-(0 if parent_liquid_investments else 1.001668493); legal=LEGAL0; ar=.073878614; statutory=STATUTORY0
    catchup=7.314667124*policy if mode=='corrected' else 0
    legal-=catchup;statutory+=catchup
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
        transfer_cost=declared*friction if mode=='corrected' else 0.0
        # residual cross-border leakage is incremental to operating income tax, not domestic WHT.
        fce-=transfer_cost; profit-=transfer_cost
        received=declared*c['collect'][i]
        recovery=ar*(.9 if c['collect'][i]==1 else 0)
        ar+=declared-received-recovery
        # parent own legal profit/cash -0.45 includes own operation, capex and finance;
        # these are components of consolidated flows, not added group expenses.
        legal,statutory,appropriation=legal_step(declared-.35-transfer_cost,legal,statutory,REGISTERED,policy=policy if mode=='corrected' else 0)
        before_pc=pc+received+recovery-.45-c['advance']-transfer_cost
        target=profit*.60
        # no debt-funded dividend: cap by operating cash, consolidated reserve and parent liquidity/legal.
        dividend=max(0,min(target,fce,cash+fce-reserve,before_pc-3,legal))
        # funding only for operating shortfall; draw as needed, dilution absent with <2bn line.
        gf=finance_step(cash,fce,dividend,reserve,2-(debt-DEBT0))
        pf=finance_step(before_pc,0,dividend,3,2-(debt-DEBT0))
        assert gf is not None and pf is not None, 'No feasible funded path'
        need=max(gf[1],pf[1])
        assert debt-DEBT0+need<=2.0, 'Funding path infeasible: exceeds research 2bn incremental borrowing ceiling (not committed facility)'
        debt+=need; cash+=fce-dividend+need; pc=before_pc-dividend+need; legal-=dividend
        capital+=reinvest
        assert cash>=reserve-1e-8 and pc>=3-1e-8 and legal>=-1e-8
        # explicit remainder at operating subsidiaries; parent advances are internal transfers.
        childcash=cash-pc
        assert childcash>=-1e-8
        rows.append(dict(year=i+1,revenue=rev,nopat=nopat,net_profit=profit,capex=c['cap'][i],da=c['da'][i],reinvestment=reinvest,fcff=fcff,net_finance_income=interest,free_equity_cash=fce,dividend=dividend,dps=dividend/SHARES,cash=cash,debt=debt,minimum_cash=reserve,parent_cash=pc,parent_declared=declared,parent_received=received,parent_old_receivable_recovery=recovery,parent_dividend_receivable=ar,parent_legal_profit=legal,parent_statutory_reserve=statutory,parent_appropriation=appropriation,transfer_cost=transfer_cost,child_cash=childcash,new_borrowing=need,capital=capital))
        divs.append(dividend); prior=rev
    grows=(.04,.035,.03,.0275,c['g']) if case not in ('structural','upside') else ((.015,.0125,.01,.01,.01) if case=='structural' else (.05,.045,.04,.035,.03))
    # Tail economic budgets, not invented legal subsidiaries. Maintenance=DA in normal
    # steady state; structural replacement burden persists ABOVE DA even at g=0.
    extra_maintenance=.01 if case=='structural' else 0
    delayed_fraction=.25 if case=='structural' else .10
    lag=5 if case=='structural' else recovery_lag
    loss=.08 if case=='structural' else recovery_cost
    if mode!='corrected': delayed_fraction=0;friction=0;extra_maintenance=0
    factor=(1-delayed_fraction)+delayed_fraction*(1-loss)/(1+r)**lag
    # Each new annual vintage is realized; not just starting stock FIFO. Operating taxes
    # already in nopat; incremental residual transfer tax/cost separate.
    n=rows[-1]['nopat']; tailrows=[]; ev5=0
    for j,grow in enumerate(grows,6):
        n*=1+grow
        investment=n*grow/c['roic']
        maintenance=n*extra_maintenance
        flow=owner_cash(n,grow,c['roic'],extra_maintenance)
        cost=flow*friction
        realized=(flow-cost)*factor
        ev5+=realized/(1+r)**(j-5)
        tailrows.append(dict(year=j,nopat=n,growth=grow,net_growth_capital=investment,maintenance_above_da=maintenance,economic_owner_cash=flow,residual_transfer_cost=cost,immediate=(flow-cost)*(1-delayed_fraction),deferred_principal=(flow-cost)*delayed_fraction,deferred_recovery_year=j+lag,recovery_fraction=1-loss,valuation_equivalent_at_generation=realized))
    n11=n*(1+c['g'])
    f11=owner_cash(n11,c['g'],c['roic'],extra_maintenance)
    tv10=f11*(1-friction)*factor/(r-c['g'])
    ev5+=tv10/(1+r)**5
    # Gross financial assets and full debt separately; financial income excluded from EV.
    excess=max(0,cash-rows[-1]['minimum_cash'])
    parent_excess=min(excess,max(0,pc-3))
    trapped_excess=excess-parent_excess
    cashlag=max(c['delay'],recovery_lag) if mode=='corrected' else c['delay']
    # Same equity bridge, now demonstrate own-entity debt repayment before ordinary payout.
    # Constant existing financing through Y5 is already a model policy, not a lender promise.
    parent_debt_repaid=min(parent_excess,debt,PARENT_EXTERNAL_DEBT)
    parent_after_own_debt=parent_excess-parent_debt_repaid
    parent_profit_backed_distribution=min(parent_after_own_debt,max(0,legal))
    parent_delayed=parent_after_own_debt-parent_profit_backed_distribution
    financial_value=parent_profit_backed_distribution+realize_principal(trapped_excess+parent_delayed,1,cashlag,recovery_cost if mode=='corrected' else 0,r)-(debt-parent_debt_repaid)
    parent_bridge=dict(documented_mother_financing=PARENT_EXTERNAL_DEBT,debt_repaid=parent_debt_repaid,remaining_group_debt=debt-parent_debt_repaid,parent_extra_after_own_debt=parent_after_own_debt,profit_backed_distribution=parent_profit_backed_distribution,parent_delayed_realization=parent_delayed)
    assert abs((parent_excess-debt)-(parent_after_own_debt-(debt-parent_debt_repaid)))<1e-10
    eq5=ev5+financial_value
    holder=pv(divs,r,eq5)/SHARES
    dcf=(pv(fcffs,r,ev5)+CASH0-DEBT0-.08*46.5)/SHARES
    return dict(case=case,rate=r,mode=mode,config=c,rows=rows,tail_rows=tailrows,tail_growth=c['g'],tail_roic=c['roic'],tail_extra_maintenance=extra_maintenance,delayed_fraction=delayed_fraction,recovery_lag=lag,recovery_cost=loss,tail_access_factor=factor,transfer_friction=friction,terminal_ev_year10=tv10,enterprise_value_year5=ev5,financial_value_year5=financial_value,parent_financial_bridge=parent_bridge,parent_excess_year5=parent_excess,child_excess_year5=trapped_excess,terminal_per_share=eq5/SHARES,current_value=holder,fcff_crosscheck=dcf,terminal_pv_fraction=eq5/(1+r)**5/(holder*SHARES),initial_cash=CASH0,initial_debt=DEBT0,opening_policy_appropriation=catchup,shares=SHARES)

def tests():
    assert legal_step(10,0,5,20,paid=10,policy=0)==(9,6,1)
    assert legal_step(10,-6,0,20,policy=0)==(3.6,.4,.4)
    assert legal_step(10,0,10,20,policy=0)==(10,10,0)
    assert legal_step(10,0,10,40,policy=0)==(9,11,1)
    assert legal_step(10,0,10,20,policy=.1)==(9,11,1)
    # Old receivable collection enters physical cash but not legal_step profits.
    assert legal_step(0,2,10,20,policy=0)[0]==2
    assert finance_step(0,-3,0,0,2) is None
    assert owner_cash(10,0,.15,.1)==9
    assert owner_cash(10,0,.15,0)==10
    z=capital_return(20,10,5,.2,1)
    assert z==dict(cash=14,shares=8,holder_cash=5,fee=1)
    assert abs(realize_principal(20,.75,2,.1,.1)-13.5/1.21)<1e-12
    assert abs(pv([10]*5,0,100)-150)<1e-12
    assert abs(tail(10,.1,0,.15,(0,0,0,0,0))[0]-100)<1e-10
    for c in ['base','cycle','structural','upside','remit_delay','no_us_remit']:
        b=run(c);cash=CASH0
        for x in b['rows']:
            assert abs(x['cash']-(cash+x['free_equity_cash']-x['dividend']+x['new_borrowing']))<1e-9
            cash=x['cash']
            assert x['parent_statutory_reserve']>=STATUTORY0
    assert run(margin_shift=-.01)['current_value']<run()['current_value']
    return 'passed; actual production legal_step, capital_return, finance_step, realize_principal, pv and tail functions invoked'

if __name__=='__main__':
    out={x:run(x) for x in ['base','cycle','structural','upside','remit_delay','no_us_remit']}
    out['core_low']=run(r=.10);out['core_high']=run(r=.09)
    out['margin_minus_100bp']=run(margin_shift=-.01)
    out['legal_minimum_only']=run(policy=0)
    out['slow_recovery']=run(recovery_lag=5,recovery_cost=.10)
    out['high_transfer_cost']=run(friction=.03)
    out['remit_delay_illiquid_parent_investments']=run('remit_delay',parent_liquid_investments=False)
    out['secondary_ev_nopat']=[(47*.18*k+CASH0-DEBT0-.08*46.5)/SHARES for k in (13,15)]
    out['tests']=tests()
    Path(__file__).with_name('2026-Q3-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
    print(json.dumps({k:{z:v[z] for z in ['current_value','terminal_per_share']} for k,v in out.items() if isinstance(v,dict) and 'current_value'in v},indent=2))
