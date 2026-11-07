"""川投能源2026Q3：人民币十亿元；普通股每股为元。标准库、无行情依赖。
真实法人仅雅砻江及川投；其他业务是经济上划预算，不设虚构法定池。
预测起点余额不是2026Q3个别报表。尾期逐年现金/利润/债务/本金，最终零增长持续经营。
"""
import json
from dataclasses import dataclass, asdict
from pathlib import Path
SHARES=4.874606828
VOL=[88,89,91,94,95,97,102,106,108,112]
PRICE=[.28,.279,.278,.277,.276,.275,.275,.275,.275,.275]
OTHER=[1.4,1.7,2.1,2.4,2.8,3.1,3.2,3.3,3.8,4.2]
COST=[5.1,5.2,5.3,5.4,5.5,5.6,5.8,6,6.2,6.4]
DA=[6.3,6.35,6.4,6.5,6.6,6.8,7.1,7.4,7.7,8.1]
CAPEX=[15,16,16,15,14,13,12,11,10,9]
INJ=[1.5,1.4,1.2,1,.8,.6,.5,.4,.3,.2]
UP=[3.8,4,4.2,4.5,4.8,5.2,5.8,6.5,7,7.5]
DPS=[.52,.54,.57,.60,.63,.70,.78,.86,.95,1.04]
ASSOC=[.45,.48,.51,.55,.6,.65,.7,.75,.8,.85]
CONTROL=[.22,.23,.25,.28,.3,.33,.36,.38,.4,.42]
HC=[.40,.41,.42,.43,.44,.46,.48,.50,.52,.54]
DIRECT=[.4,.4,.4,.5,.7,.7,.7,.7,.7,.7]
BORROW=[1,.6,.4,.1,0,0,0,0,0,0]
@dataclass
class Account:
    registered:float
    paid:float
    statutory:float
    discretionary:float
    retained:float

def allocate(a, profit, requested, available_cash, voluntary_stat=0., voluntary_other=0., legacy=False):
    """Same function used for both real entities; prior loss first, registered not paid.
    statutory is an explicit opening budget/lower bound, not a claimed exact fact.
    optional policy may continue beyond 50%. Mandatory increment capped at threshold.
    """
    eligible=max(0.,profit+min(0.,a.retained))
    compulsory=min(.1*eligible,max(0.,.5*a.registered-a.statutory))
    s=max(compulsory,voluntary_stat*eligible)
    o=voluntary_other*eligible
    if legacy:s=.1*max(0.,profit);o=0
    capacity=max(0.,a.retained+profit-s-o)
    dividend=min(max(0.,requested),max(0.,available_cash),capacity)
    a.statutory+=s;a.discretionary+=o;a.retained+=profit-s-o-dividend
    return dict(profit=profit,stat_add=s,discretionary_add=o,capacity=capacity,dividend=dividend,retained=a.retained,statutory=a.statutory,discretionary=a.discretionary)

def capital_return(a,cash,amount,owner_fraction=1.,fee_rate=.01,investment_basis=1e9,old_units=None):
    """Proportional upstream capital reduction: ALL holders cancelled pro rata.
    Registration/paid/basis decrease; principal is not income; fraction unchanged.
    Requires decision, creditor protection and no harm to necessary operating funding.
    """
    gross=min(amount,max(0.,cash),a.paid,a.registered,investment_basis)
    old=a.registered
    a.registered-=gross;a.paid-=gross
    fee=gross*fee_rate
    return dict(gross=gross,fee=fee,net=gross-fee,owner_net=(gross-fee)*owner_fraction,
                accounting_profit=-fee,principal=gross,investment_basis_end=investment_basis-gross,
                holder_units_after=None if old_units is None else old_units*(1-gross/old),fraction_after=owner_fraction)

def parent_profit(yl_equity_income,other_equity_income,cost_dividend,financial_income,cost,old_receivable_collection=0):
    return yl_equity_income+other_equity_income+cost_dividend+financial_income-cost

def run(scenario='base',rate=.07,horizon=160,price_shift=0.,profit_conversion=1.,
        policy_years=10,release_year=15,yl_open_retained=15.,yl_open_stat=8.87038517457,
        recap_year=40,legacy=False,initial_cash=1.5,extra_equity=0.,upstream_delay=0.,opening_receivable=1.104546825,yl_debt_share=.25,parent_debt_share=.20):
    # 2026-04 official pre-increase registered/paid 50.7; future contributions
    # assume registration completed same year; delay tested separately via frozen lower base.
    ya=Account(50.7,50.7,yl_open_stat,2.59936422983,yl_open_retained)
    # Exact parent reserve split absent. Known 2024+2025 additions establish LOWER BOUNDS.
    # Total reserve 11.79903900231 is tracked separately; no invented statutory opening.
    pa=Account(SHARES,SHARES,.44062641704+.47171605772,.66093962556+.70757408659,18.09076086388)
    parent_total_reserve=11.79903900231
    yd=90.;yc=0.;pd=14.185261;pc=initial_cash;ybasis=37.72766664451
    parent_receivable=0.;rows=[]; financial=2.787239843; common_book=46.70917936221
    for t in range(1,horizon+1):
        i=min(t-1,9);v=VOL[i];p=PRICE[i]+price_shift;other=OTHER[i];c=COST[i];da=DA[i]
        cap=CAPEX[i] if t<=10 else da
        inj=INJ[i] if t<=10 else 0.;direct=DIRECT[i] if t<=10 else 0.
        nci=[.04,.045,.05,.055,.06,.07,.08,.09,.10,.11][i]
        rr=.026;tax=.2 if t<5 else .25
        if scenario=='cycle' and t<=2:v*=.8
        if scenario=='optimistic':v*=1.05;other*=1.1;cap*=1.05 if t<=10 else 1.;inj*=1.05
        if scenario=='structural':
            v=[84,84,85,86,87,88,90,92,94,96][i];p=[.26,.258,.256,.254,.252,.25,.25,.25,.25,.25][i]+price_shift
            other=[1.3,1.4,1.5,1.6,1.7,1.8,2,2.2,2.4,2.5][i]
            c=[5.2,5.3,5.4,5.5,5.6,5.7,5.8,5.9,6,6.1][i]
            da=[6.3,6.35,6.4,6.5,6.6,6.7,6.9,7.1,7.3,7.4][i]
            cap=[13,13,12,11,10,9,8,7,7,7][i] if t<=10 else da
            inj=[.9,.8,.6,.5,.4,.3,.2,.1,0,0][i] if t<=10 else 0
            direct=[.3,.3,.2,.2,.1,0,0,0,0,0][i] if t<=10 else 0;rr=.03;tax=.25;nci=.04+.006*i
        conversion=profit_conversion if t<=10 else 1+(profit_conversion-1)*max(0,(20-t)/10)
        old_payable=opening_receivable/.48 if t==1 else 0.
        ebit=v*p+other-c-da
        # Same average-debt calculation as published first decade. NCI cash paid before equity CF.
        # Initial requested upstream isn't a legal fact; constrained by economic legal-profit proxy.
        def solve(div):
            if t<=10:
                b=(cap+div-inj/.48-(ebit-rr*yd)*(1-tax)-da+.2+nci)/(1-rr*(1-tax)/2)
                b=max(-yd,b)
            else:
                # full NI-DA replacement produces equity cash; 25% common NI for debt reduction.
                b=-min(yd,yl_debt_share*max(0.,((ebit-rr*yd)*(1-tax)-nci))/(1-yl_debt_share*rr*(1-tax)/2))
            interest=rr*(yd+b/2);ni=(ebit-interest)*(1-tax)-nci
            return b,interest,ni
        requested=UP[i]/.48 if t<=10 else 1e6
        if scenario=='structural' and t<=10:requested=.6*solve(0)[2]
        if scenario=='cycle' and t<=2:requested*=.8
        if scenario=='optimistic' and t<=10:requested*=1.05
        # iterate cap including profit effect of reduced borrowing
        for _ in range(100):
            b,interest,ni=solve(requested)
            proxy=ni*conversion
            eligible=max(0.,proxy+min(0.,ya.retained))
            required=.1*eligible if legacy and t<=10 else min(.1*eligible,max(0.,.5*(ya.registered+inj/.48)-ya.statutory))
            legal=max(0.,ya.retained+proxy-required)
            free=ni+da-cap-(.2 if t<=10 else 0.)+inj/.48+b+yc
            limit=min(requested,legal+old_payable,max(0.,free))
            if abs(limit-requested)<1e-11:break
            requested=limit
        b,interest,ni=solve(requested)
        if yd+b>180:raise ValueError('YL debt budget exhausted; no unlimited borrowing')
        yc0=yc; yd+=b;ya.registered+=inj/.48;ya.paid+=inj/.48
        yc+=ni+da-cap-(.2 if t<=10 else 0.)+inj/.48+b
        a=allocate(ya,ni*conversion,max(0.,requested-old_payable),yc-old_payable,legacy=legacy and t<=10)
        ydiv=a['dividend'];yc-=ydiv+old_payable
        recap=dict(gross=0.,fee=0.,net=0.,owner_net=0.,accounting_profit=0.)
        if t>=recap_year and yd<1e-8 and yc>1e-8:
            # Excess accumulated because reserve ceiling binds; necessary maintenance funded already.
            # Only documented paid capital return, not reserve relabelled as earnings.
            recap=capital_return(ya,yc,yc,owner_fraction=.48,investment_basis=ybasis/.48)
            yc-=recap['gross'];ya.retained+=recap['accounting_profit']
        assert yc>=-1e-8 and yd>=-1e-8
        assoc=ASSOC[i] if scenario!='structural' else .20
        control=CONTROL[i] if scenario!='structural' else .11
        # Economic other-source budget only; reinvestment reflected in limited cash, not synthetic legal pool.
        other_cash=.24 if t<=10 else (assoc+control)*(.8 if t<=20 else 1.)
        if scenario=='structural':other_cash=.19 if t<=10 else assoc+control
        if scenario=='optimistic':assoc*=1.05;control*=1.05;other_cash*=1.05
        costdiv=min(control,.05+.005*i) if t<=10 else control*(.8 if t<=20 else 1.)
        # Nonoperating asset sold in year 12, earnings cease thereafter; proceeds net explicit fees/tax.
        fin_income=.06 if financial>0 else 0.
        sale=0.;sale_friction=0.;sale_profit=0.
        if t==12:
            sale=financial; sale_friction=.147239843; financial=0.
            sale_profit=-sale_friction # conservative profit capacity; actual FVOCI classification may differ
        # Borrowing all first-decade financing explicitly priced; base HC split to recover old cost.
        pb=BORROW[i] if t<=10 else 0
        if scenario=='structural':pb=[.8,.6,.4,.2,0,0,0,0,0,0][i] if t<=10 else 0
        old_pd=pd;pd+=pb
        hcost=HC[i]+(.03-.026)*(old_pd+pb/2) if scenario=='structural' else HC[i]
        if t>10:
            admin=.54-.026*(14.185261+2.1)
            # Cash after upstream service applied to reduce parent debt, with full annual opening interest.
            hcost=admin+rr*pd
        new_decl=ydiv*.48
        collected=new_decl
        old_collect=opening_receivable if t==1 else 0.
        if t==1 and upstream_delay:
            delayed=min(new_decl,upstream_delay);collected-=delayed;parent_receivable+=delayed
        if t==2 and parent_receivable:old_collect=parent_receivable;parent_receivable=0.
        eqprofit=(ni-recap['fee'])*.48
        profit=parent_profit(eqprofit,assoc,costdiv,fin_income,hcost,old_collect)+sale_profit
        if legacy and t<=10:profit=collected+old_collect+other_cash+fin_income-hcost+sale_profit
        upstream=collected+old_collect+other_cash+fin_income+recap['owner_net']
        invest=inj+direct+(extra_equity if t<=5 else 0.)
        cash0=pc
        pc+=upstream-hcost-invest+pb+sale-sale_friction
        if pc<1-1e-8:raise ValueError(f'parent funding fails even at zero dividend in year {t}')
        repay=0.
        if t>10:
            repay=min(pd,max(0.,(upstream-hcost)*parent_debt_share),max(0.,pc-1))
            pd-=repay;pc-=repay
        target=DPS[i]*SHARES if t<=10 else max(0.,upstream-hcost-repay)
        if scenario=='cycle' and t<=2:target*=.8
        if scenario=='optimistic' and t<=10:target*=1.05
        if scenario=='structural' and t<=10:target=.5*max(0.,eqprofit+assoc+control+fin_income-hcost)
        if t>=release_year:target=max(target,pc-1) # ordinary special dividend; no fictional capital return
        q=allocate(pa,profit,target,pc-1,voluntary_stat=.1 if t<=policy_years else 0,
                   voluntary_other=.15 if t<=policy_years else 0,legacy=legacy and t<=10)
        div=q['dividend'];pc-=div;parent_total_reserve+=q['stat_add']+q['discretionary_add']
        common_profit=eqprofit+assoc+control+fin_income-hcost+sale_profit
        common_book+=common_profit-div
        ybasis+=eqprofit+inj-new_decl-recap['gross']*.48
        assert abs(pc-(cash0+upstream-hcost-invest+pb+sale-sale_friction-repay-div))<1e-8
        assert abs(yc-(yc0+ni+da-cap-(.2 if t<=10 else 0)+inj/.48+b-ydiv-old_payable-recap['gross']))<1e-8
        rows.append(dict(year=t,hydro_kwh=v,price=p,revenue=v*p+other,ebit=ebit,yl_common_profit=ni,
            yl_proxy_profit=ni*conversion,yl_interest=interest,yl_capex=cap,yl_equity_injection=inj/.48,
            yl_distribution=ydiv,yl_old_payable_paid=old_payable,yl_cash_distribution=ydiv+old_payable,yl_net_borrowing=b,yl_debt=yd,yl_cash=yc,yl_account=asdict(ya),yl_allocation=a,
            yl_capital_return=recap,yl_investment_book=ybasis,other_equity_income=assoc,controlled_common_profit=control,
            controlled_cost_dividend=costdiv,other_upstream_cash=other_cash,financial_income=fin_income,
            financial_sale_gross=sale,financial_sale_friction=sale_friction,financial_asset_end=financial,
            parent_equity_method_income=eqprofit,parent_profit=profit,parent_upstream=upstream,
            old_receivable_collection=old_collect,parent_receivable=parent_receivable,parent_holding_cost=hcost,
            parent_equity_outflow=invest,parent_net_borrowing=pb-repay,parent_debt=pd,parent_cash=pc,
            parent_account=asdict(pa),parent_total_reserve=parent_total_reserve,parent_allocation=q,
            common_profit=common_profit,common_book=common_book,dividend=div,dps=div/SHARES))
    # Terminal is last constant distribution; all cash/financing/property constraints already run.
    # No cash/book add-on: financial proceeds, excess cash and legal capital returns paid explicitly.
    if max(abs(rows[-1]['dps']-r['dps']) for r in rows[-10:])>1e-7:
        raise ValueError('Horizon not steady; extend explicit tail')
    terminal=rows[-1]['dps']/rate
    pv=sum(r['dps']/(1+rate)**r['year'] for r in rows)+terminal/(1+rate)**horizon
    tv5=sum(r['dps']/(1+rate)**(r['year']-5) for r in rows[5:])+terminal/(1+rate)**(horizon-5)
    tv10=sum(r['dps']/(1+rate)**(r['year']-10) for r in rows[10:])+terminal/(1+rate)**(horizon-10)
    return dict(value=pv,terminal_year5=tv5,terminal_year10=tv10,terminal_pv_share=tv10/(1+rate)**10/pv,
                distributions_per_share=[r['dps'] for r in rows[:5]],rows=rows,
                remaining_yl_cash=yc,remaining_parent_cash=pc,remaining_financial_assets=financial,
                params=dict(scenario=scenario,rate=rate,horizon=horizon,price_shift=price_shift,
                profit_conversion=profit_conversion,policy_years=policy_years,release_year=release_year,
                recap_year=recap_year,legacy=legacy,yl_open_retained=yl_open_retained,yl_open_stat=yl_open_stat))

def tests():
    a=Account(20,10,5,0,0);assert allocate(a,10,99,99)['stat_add']==1
    a=Account(20,10,5,0,-6);x=allocate(a,10,99,99);assert abs(x['dividend']-3.6)<1e-10
    a=Account(20,10,10,0,0);assert allocate(a,10,99,99)['stat_add']==0
    a=Account(20,10,10,0,0);assert allocate(a,10,99,99,voluntary_stat=.1)['stat_add']==1
    a.registered=40;assert allocate(a,10,99,99)['stat_add']==1
    assert abs(parent_profit(3,1,.2,.1,.4,100)-3.9)<1e-12
    a=Account(20,20,10,0,0);assert allocate(a,0,10,10)['dividend']==0
    x=capital_return(a,10,10,.48,.02,20,20);assert abs(x['owner_net']-4.704)<1e-12 and x['accounting_profit']==-.2 and x['holder_units_after']==10
    assert a.registered==10 and a.retained==0
    a=Account(20,20,10,0,0);assert abs(capital_return(a,10,10,.2,.02,20)['owner_net']-1.96)<1e-12
    try:run(initial_cash=-100)
    except ValueError:pass
    else:raise AssertionError('unfinanced deficit hidden')
    base=run();assert abs(base['value']-sum(x/(1.07)**(i+1) for i,x in enumerate(base['distributions_per_share']))-base['terminal_year5']/1.07**5)<1e-9
    return 'passed: registered/paid, prior loss, cap optional, capital change, old receivable, capital return fees/ownership/units, no fabricated financing, D/TV'

def output():
    out={'core_low':run(rate=.075),'core_mid':run(),'core_high':run(rate=.065),
         'cyclical_weak':run('cycle'),'structural_weak':run('structural',rate=.08),
         'optimistic':run('optimistic',rate=.065),'price_minus_001':run(price_shift=-.01),
         'parent_policy_20years':run(policy_years=20),'parent_policy_30years':run(policy_years=30),
         'yl_profit_95pct':run(profit_conversion=.95),'yl_profit_85pct':run(profit_conversion=.85),'yl_profit_105pct':run(profit_conversion=1.05),
         'yl_open_retained_10':run(yl_open_retained=10),'yl_open_stat_11':run(yl_open_stat=11),'receivable_attribution_zero':run(opening_receivable=0),
         'cash_release_year25':run(release_year=25),'capital_return_delay60':run(recap_year=60),
         'faster_debt_repayment':run(yl_debt_share=.4,parent_debt_share=.3),'capital_cost_8pct':run(rate=.08),'capital_cost_9pct':run(rate=.09),
         'upstream_delay_08':run(upstream_delay=.8),'extra_equity_05':run(extra_equity=.5),
         'old_mechanics_same_economics':run(legacy=True),
         'auxiliary':[((5.1-.06)*pe+2.64)/SHARES for pe in [14,16]],'tests':tests(), 'account_status':{'yl':'registered/paid forecast conditioned on registration, retained and statutory are source-anchored budgets not Q3 audited facts','parent':'statutory and discretionary opening are proven cumulative addition lower bounds, not claimed exact parent split; total actual reserve separate','other_business':'economic upstream budget, not a legal entity or reserve pool','capital_return':'pro rata ownership unchanged, paid/registered/investment cost reduced; no triggered capital return in core scenarios'}}
    out['convergence']={str(n):run(horizon=n)['value'] for n in [100,160,240,400]}
    return out
if __name__=='__main__':
    result=output();p=Path(__file__).with_name('2026-Q3-output.json');p.write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps({k:({'value':v['value'],'TV5':v['terminal_year5'],'D':v['distributions_per_share']} if isinstance(v,dict) and 'value'in v else v) for k,v in result.items()},ensure_ascii=False,indent=2))
