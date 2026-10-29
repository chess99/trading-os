#!/usr/bin/env python3
"""600585 economic budget. Stdlib only, all money CNY bn, volume million tonnes.
No network/files/input imports. Annual periods from 2026-10-28; no stock quotes.
Cohorts are budget bounds, not fabricated legal-entity forecasts. Actual named
ownership: Yingde .75, Conch Venture Environmental .2121 (lower tiers .69 budget).
"""
import json, math, copy
SHARES=(5277060044-36879800-17306500)/1e9
CASES={
 'core_low':dict(r=.10,price=215,cost=154,volume=220,other=1.15,release=15,extra=0,finance=75,aux_yield=.100),
 'base':dict(r=.095,price=218,cost=153,volume=225,other=1.35,release=13,extra=0,finance=77,aux_yield=.106),
 'core_high':dict(r=.09,price=221,cost=152,volume=230,other=1.50,release=11,extra=0,finance=79,aux_yield=.112),
 'persistent_demand_loss':dict(r=.105,price=202,cost=159,volume=192,other=.8,release=20,extra=0,finance=75,aux_yield=.054),
 'supply_discipline':dict(r=.09,price=232,cost=151,volume=238,other=1.6,release=11,extra=0,finance=79,aux_yield=.125),
 'cost_plus_5':dict(r=.095,price=218,cost=158,volume=225,other=1.35,release=13,extra=0,finance=77,aux_yield=.096),
 'cash_delay':dict(r=.095,price=218,cost=153,volume=225,other=1.35,release=25,extra=0,finance=77,aux_yield=.106),
 'extra_capital':dict(r=.095,price=218,cost=153,volume=225,other=1.35,release=13,extra=2,finance=77,aux_yield=.106)}
CASES['plan_not_adopted']=dict(CASES['base'],floor_plan=False)
CASES['legal_capacity_stress']=dict(CASES['base'],reserve_cap=26,yingde_up=.5)
CASES['portfolio_delay']=dict(CASES['base'],portfolio_start=16)
CASES['legal_opening']=dict(CASES['base'],legal_opening=20)
CASES['nci_leakage']=dict(CASES['base'],residual_owner=.90)
CASES['cash_location']=dict(CASES['base'],parent_cash=50)
CASES['no_refinancing']=dict(CASES['base'],no_refinancing=True)
CASES['old_dividend_zero']=dict(CASES['base'],old_dividend='zero')
CASES['old_dividend_external']=dict(CASES['base'],old_dividend='external')
CASES['portfolio_recovery_low']=dict(CASES['base'],recovery=.60,portfolio_income=.01)
CASES['portfolio_recovery_high']=dict(CASES['base'],recovery=1.,portfolio_income=.035)
CASES['portfolio_recovery_only_low']=dict(CASES['base'],recovery=.60)
CASES['portfolio_recovery_only_high']=dict(CASES['base'],recovery=1.)
CASES['acquisition_not_completed']=dict(CASES['base'],acquisition=0.)
CASES['environment_all_99pct_bound']=dict(CASES['base'],env_lower=.99)
CASES['new_medical_cash_upper_bound']=dict(CASES['base'],new_medical_upper=True,env_lower=.99)
CASES['conditional_low_after_base5']=dict(CASES['core_low'],conditional=True,finance=77)
CASES['conditional_high_after_base5']=dict(CASES['core_high'],conditional=True,finance=77)
def legal(up,res,cap,profit):
    # Negative UP must first be repaired; never cross-offset separate cohorts.
    after=up+profit
    provision=min(max(0,cap*.5-res),.10*max(0,after-max(0,up)))
    return after-provision,res+provision,provision

def unit(name,cash,debt,up,res,cap,owner,floor):
    return dict(name=name,cash=cash,debt=debt,up=up,res=res,cap=cap,owner=owner,floor=floor)

def cash_step(u,ebit,da,capex,dwc,external_income=0,repay=0,required=False):
    opening=u['cash']; finance=opening*.015
    interest=u['debt']*.026
    pretax=ebit+finance-interest+external_income
    # No group tax consolidation. No unsupported tax-loss asset cash benefit.
    tax=.25*max(0,pretax); profit=pretax-tax
    u['up'],u['res'],reserve=legal(u['up'],u['res'],u['cap'],profit)
    before=opening+profit+da-capex-dwc
    maturity=u['debt']/3
    paid=min(repay,u['debt']) if required else min(repay,u['debt'],max(0,before-u['floor']))
    refinancing=max(0,maturity-paid)
    u['debt']-=paid; u['cash']=before-paid
    assert abs(u['cash']-(opening+profit+da-capex-dwc-paid))<1e-8
    return dict(open_cash=opening,ebit=ebit,da=da,capex=capex,dwc=dwc,financial_income=finance,other_cash_income=external_income,interest=interest,tax=tax,profit=profit,reserve_add=reserve,debt_repaid=paid,scheduled_maturity=maturity,refinancing=refinancing,cash_before_distribution=u['cash'])

def distribute(u,desired):
    d=min(max(0,desired),max(0,u['up']),max(0,u['cash']-u['floor']))
    u['cash']-=d;u['up']-=d
    assert u['cash']>=u['floor']-1e-8 or d==0
    return d

def economics(t,c,method):
    f=min(1,(t-1)/5); vol=235+(c['volume']-235)*f
    price=209+(c['price']-209)*f; cost=157+(c['cost']-157)*f
    # Long-run stable nominal service demand, no indefinite real growth.
    # Replacement investment continues indefinitely; no terminal cash formula.
    dep=8.; capex=(10.5,10,9.5,9,8.5)[t-1] if t<=5 else 8.0
    capex+=c['extra'] if t<=5 else 0
    other=.9+(c['other']-.9)*f
    revenue=vol*price/1000+12
    if method=='unit_economics':
        ebit=vol*(price-cost-16)/1000-(7.7-.5*f)+other
    else:
        # Independent replacement-asset budget, productive capital 126bn;
        # current EBITDA ~9.7bn -> normalized asset cash yields, not PE or RI.
        ebit=(9.7+(126*c['aux_yield']-9.7)*f)-dep
        capex=(10.5,10,9.5,9,8.5)[t-1] if t<=5 else 8.0
        capex+=c['extra'] if t<=5 else 0
    # A continuing underperforming slice remains separate and loss-first.
    loss=-.35*(1-f)-.05*f
    env=-.12*(1-f)+.12*f
    yingde=.04*(1-f)+.12*f
    parent=-.15
    residual=ebit-loss-env-yingde-parent
    return dict(volume=vol,price=price,landed_cash_cost=cost,revenue=revenue,ebit=ebit,da=dep,capex=capex,components=[parent,residual,loss,yingde,env])

def run(name,method='unit_economics',horizon=400):
    scenario=CASES[name];c=CASES['base'] if scenario.get('conditional') else scenario;pc=c.get('parent_cash',60);p=unit('listed_parent',pc,10.6,141.970464865,2.64965129,5.277060044,1,4)
    w=unit('residual_profitable_budget_pool',c['finance']-pc-5.8,10.6,c.get('legal_opening',0),1.5,c.get('reserve_cap',6),c.get('residual_owner',.94),5)
    l=unit('residual_loss_budget_pool',2,0,-1.0,.1,1,.94,.8)
    y=unit('Yingde_75pct',2.5,.2,c.get('yingde_up',3.0),.1,.4,.75,.4)
    e=unit('Environmental_budget_pool',1.3,4.1,-.5,.2,1.2,.2121*c.get('env_lower',.69),.5)
    us=[p,w,l,y,e]; loan=44.088345981;poolpay=17.164153814
    # Gross intercompany principal never creates group earnings or cash.
    portfolio=9.376410426-.03599034*(1-.2121*.69);initial_portfolio=portfolio;fund_calls=1.93;receivable=.041608258;pending=0;pending_by_sub=[0.0]*5
    rows=[]; stopped=None; support_loans=[0.0]*5;acquisition_cost=0.;checkpoint=None
    for t in range(1,horizon+1):
        if t==6 and scenario.get('conditional'): c=scenario  # SAME live accounts; no reinitialization
        op=economics(t,c,method);start_cash=sum(u['cash'] for u in us)
        receipts=pending; p['cash']+=receipts;pending=0
        for i in range(1,5): us[i]['cash']-=pending_by_sub[i]
        pending_by_sub=[0.0]*5
        # Existing receivable collected once, never booked again as profit.
        rc=receivable if t==1 and c.get('old_dividend','internal')!='zero' else 0
        p['cash']+=rc;receivable-=rc
        rc_external=rc if c.get('old_dividend','internal')=='external' else 0
        if rc and not rc_external:w['cash']-=rc  # uncertain debtor: conservative internal transfer
        # Assets held through ordinary portfolio maturity/recycling, not immediate liquidation.
        call=min(fund_calls,.5) if t<=4 else 0
        fund_calls-=call;portfolio+=call;p['cash']-=call
        sale=min(portfolio,(initial_portfolio+1.93)/10) if c.get('portfolio_start',6)<=t<c.get('portfolio_start',6)+10 else 0
        recovery=c.get('recovery',.85)
        portfolio-=sale;p['cash']+=sale*recovery
        # 15% haircut is recognized, coupon scales with outstanding principal.
        income=portfolio*c.get('portfolio_income',.025)
        p['up']-=sale*(1-recovery)
        payable=min(poolpay,17.164153814/5);poolpay-=payable
        p['cash']-=payable;w['cash']+=payable
        st=[];internal_interest=loan*.02
        for i,u in enumerate(us):
            dep=op['da']*[.02,.83,.05,.025,.075][i]
            cap=op['capex']*[.02,.83,.05,.025,.075][i]
            if i==4 and t==1:
                acquisition_cost=c.get('acquisition',.307);cap+=acquisition_cost
            dwc=(.3 if t==1 else -.1 if t<=5 else 0)*[.01,.87,.04,.03,.05][i]
            st.append(cash_step(u,op['components'][i],dep,cap,dwc,income+internal_interest if i==0 else -internal_interest if i==1 else 0,u['debt']/3 if c.get('no_refinancing') else u['debt']/max(1,11-t) if t<=10 else u['debt'],c.get('no_refinancing',False)))
        # Acquisition earnings are excluded from base pending approvals/integration.
        # Wide boundary: 40m pretax incremental project earnings, taxed separately,
        # all environmental ownership raised to .99 (not merely new project).
        # Actual environmental legal reserves/cash/debt gate every distribution.
        medical_cash=.04*.75 if c.get('new_medical_upper') else 0.
        medical_common=medical_cash*.99*.2121
        if medical_cash:
            e['cash']+=medical_cash
            st[4]['cash_before_distribution']+=medical_cash
            e['up'],e['res'],medical_reserve=legal(e['up'],e['res'],e['cap'],medical_cash)
            st[4]['profit']+=medical_cash;st[4]['tax']+=.01
            st[4]['ebit']+=.04;st[4]['reserve_add']+=medical_reserve
            op['ebit']+=.04;op['components'][4]+=.04
        # Lawful loan recovery only out of cash actually available. No netting.
        lr=min(loan,44.088345981/12,max(0,w['cash']-w['floor']))
        w['cash']-=lr;p['cash']+=lr;loan-=lr
        # Finite parent support budget: losses cannot be funded with invented debt.
        support=0
        for i in (1,2,3,4):
            need=max(0,us[i]['floor']-us[i]['cash'])
            if need:
                if p['cash']-p['floor']<need:
                    stopped={'year':t,'reason':'parent liquidity cannot fund operating deficit','cohort':us[i]['name'],'required_cash':need,'available_parent_cash_above_floor':max(0,p['cash']-p['floor']),'operations':op,'accounts_before_failure':[dict(z) for z in us],'year_cash_steps':st};break
                p['cash']-=need;us[i]['cash']+=need;support+=need;support_loans[i]+=need
                if i==2: p['up']-=need  # bad-loss-pool support impaired for parent legal profit only
                # Recoverable principal support; zero cash interest while distressed.
                # No parent expense, no recipient legal profit, no NCI gift.
        if stopped:break
        if any(u['cash']<0 for u in us):
            stopped={'year':t,'reason':'negative cash after required operating cash flows'};break
        support_recovery=0
        for i in (1,2,3,4):
            sr=min(support_loans[i],max(0,us[i]['cash']-us[i]['floor']))
            us[i]['cash']-=sr;p['cash']+=sr;support_loans[i]-=sr;support_recovery+=sr
            if i==2:p['up']+=sr  # reverse allowance only on actual recovery
        d_sub=0;nci=0;declared=0
        for i,u in enumerate(us[1:],1):
            target=max(0,st[i]['profit'])+min(1,max(0,(t-5)/10))*.15*max(0,u['cash']-u['floor'])
            d=distribute(u,target)
            d_sub+=d;owned=d*u['owner'];nci+=d-owned;declared+=owned
            pending_by_sub[i]=.25*owned;u['cash']+=.25*owned
        # Declaration creates parent income; 25% actually received next year.
        paid_now=.75*declared;p['cash']+=paid_now;pending=.25*declared
        p['up'],p['res'],reserve_on_div=legal(p['up'],p['res'],p['cap'],declared)
        st[0]['reserve_add']+=reserve_on_div
        # Common holder payout budget moves 45% to full distributable cash as
        # domestic expansion ends; excess opening liquidity returned gradually.
        ramp=min(1,max(0,(t-5)/(c['release']-5)))
        ownerprofit=st[0]['profit']+declared
        common_profit=st[0]['profit']+sum(st[i]['profit']*us[i]['owner'] for i in range(1,len(us)))
        desired=max(0,common_profit)*(.45+.55*ramp)+ramp*.15*max(0,p['cash']-p['floor'])
        if t<=2 and c.get('floor_plan',True) and common_profit>0: desired=max(desired,.90*SHARES)
        d=distribute(p,desired)
        end_cash=sum(u['cash'] for u in us)
        # Consolidated cash conservation excludes internal payments, preserves
        # dividend transit receivable and actual minority distributions.
        operating=sum(z['profit']+z['da']-z['capex']-z['dwc']-z['debt_repaid'] for z in st)
        expected=start_cash+rc_external+sale*recovery-call+operating-nci-d
        assert abs(end_cash-expected)<1e-7,(t,end_cash,expected)
        row=dict(old_receivable=receivable,old_receivable_collection=rc,old_receivable_external_cash=rc_external,portfolio_cost_sold=sale,portfolio_cash_recovery=sale*recovery,portfolio_cash_income=income,portfolio_disposal_loss=sale*(1-recovery),acquisition_cost=acquisition_cost,new_medical_full_cash=medical_cash,new_medical_attributable_profit_before_payout=medical_common,year=t,method=method,case=name,operations=op,entities={u['name']:dict(**u,**st[i]) for i,u in enumerate(us)},loan=loan,internal_interest=internal_interest,pool_payable=poolpay,portfolio=portfolio,fund_call=call,common_attributable_profit=common_profit,parent_dividend_receivable=pending,declared_to_parent=declared,received_by_parent=paid_now+receipts,loan_recovery=lr,gross_pool_payment=payable,parent_support=support,support_loan_balances=list(support_loans),support_recovery=support_recovery,nci_cash_distribution=nci,common_distribution=d,distribution_per_share=d/SHARES,total_cash=end_cash,total_debt=sum(u['debt'] for u in us),total_reserve=sum(u['res'] for u in us),pv=d/SHARES/(1+scenario['r'])**t)
        rows.append(row)
        if t==5:
            checkpoint=copy.deepcopy(dict(entities=us,loan=loan,poolpay=poolpay,portfolio=portfolio,initial_portfolio=initial_portfolio,fund_calls=fund_calls,old_receivable=receivable,pending=pending,pending_by_sub=pending_by_sub,support_loans=support_loans,acquisition_cost=acquisition_cost))
    pv=sum(r['pv'] for r in rows)
    tv5=sum(r['distribution_per_share']/(1+scenario['r'])**(r['year']-5) for r in rows if r['year']>5)
    return dict(case=name,method=method,year5_state=checkpoint,parameters=scenario,shared_base_first5=bool(scenario.get('conditional')),shares_bn=SHARES,status='infeasible' if stopped else 'feasible',stop=stopped,value=pv if not stopped else None,partial_distributions_pv=pv,terminal_year5=tv5 if not stopped else None,first5=[r['distribution_per_share'] for r in rows[:5]],terminal_pv_fraction=(tv5/(1+scenario['r'])**5/pv if pv and not stopped else None),rows=rows)

def tests():
    assert legal(-5,0,10,3)==(-2,0,0)
    assert all(abs(a-b)<1e-12 for a,b in zip(legal(-5,0,10,8),(2.7,.3,.3)))
    assert legal(2,4.9,10,10)==(11.9,5.0,.09999999999999964)
    u=unit('hand',10,2,-5,0,10,1,1)
    z=cash_step(u,8,1,2,.5,0,2)
    # literal: pretax 8+.15-.052=8.098; tax2.0245; profit6.0735;
    # repair old loss5, reserve.10735, legal room.96615; cash12.5735
    assert abs(z['profit']-6.0735)<1e-10
    assert abs(u['cash']-12.5735)<1e-10
    assert abs(u['up']-.96615)<1e-10
    assert abs(distribute(u,9)-.96615)<1e-10
    assert abs(u['cash']-11.60735)<1e-10
    # Separate loss cohort may not offset profitable cohort tax/legal reserve.
    a=unit('profit',10,0,0,0,10,1,1);b=unit('loss',10,0,-5,0,10,1,1)
    aa=cash_step(a,4,0,0,0);bb=cash_step(b,-4,0,0,0)
    assert abs(aa['tax']-1.0375)<1e-10 and bb['tax']==0
    return 'loss-first, reserve cap, cash/debt, isolated-tax production tests passed'

def main():
    test=tests();out=[];convergence=[]
    for method in ('unit_economics','replacement_asset_budget'):
        for name in CASES:
            full=run(name,method,400);out.append(full)
            a=run(name,method,200);b=run(name,method,300)
            item=dict(case=name,method=method,status=full['status'])
            if full['status']=='feasible':
                item.update(pv200=a['value'],pv300=b['value'],pv400=full['value'],last_cash=full['rows'][-1]['total_cash'],last_debt=full['rows'][-1]['total_debt'],last_reserve=full['rows'][-1]['total_reserve'],last_d=full['rows'][-1]['common_distribution'],cash_delta_300_400=full['rows'][-1]['total_cash']-b['rows'][-1]['total_cash'],reserve_delta_300_400=full['rows'][-1]['total_reserve']-b['rows'][-1]['total_reserve'],D_delta_300_400=full['rows'][-1]['common_distribution']-b['rows'][-1]['common_distribution'])
                assert abs(full['value']-b['value'])<1e-7
                assert abs(item['cash_delta_300_400'])<1e-6
                assert abs(item['reserve_delta_300_400'])<1e-6
                assert abs(item['D_delta_300_400'])<1e-6
            else:item['stop']=full['stop']
            convergence.append(item)
    print(json.dumps(dict(production_tests=test,unit='CNY billion; distributions per share CNY',horizon=400,convergence=convergence,results=out),ensure_ascii=False,sort_keys=True,separators=(',',':')))
if __name__=='__main__':main()
