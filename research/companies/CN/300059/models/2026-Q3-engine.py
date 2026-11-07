#!/usr/bin/env python3
"""CNY billion, shares billion. Standalone deterministic shareholder cash model."""
import json, math, gzip, hashlib, base64, zlib
from pathlib import Path
from copy import deepcopy
SHARES=15.822199875
DILUTION=.001906
EXERCISE=23.63
INITIAL={'sec_equity':84.0,'other_equity':18.39849091709,'sec_required':80.,'other_required':13.,'sec_up':31.,'parent_up':15.18415647965,'sec_stat':3.81206356153,'parent_stat':2.24775334314,'parent_cash':3.3,'parent_receivable':1.5,'nonsec_economic_equity':2.,'nonsec_economic_required':1.8,'nonsec_accumulated_economic_earnings':.8,'sec_risk':7.70456409331,'tax_loss_sec':0.,'tax_loss_parent':0.,'financial_principal':.39849091709,'nonsec_original_principal':.2}
BASE={'sec_profit':10.8,'other_profit':3.4,'growth':.04,'mature_growth':.03,'cash_yield':.015,'release_start':6,'release_fraction':.12,'tax_reset':True,'funding_spread':0.,'capital_multiplier':1.,'profit_multiplier':1.,'upstream_delay':0,'parent_extra_payment':0.,'zero_dividend':False,'collection_delay':0.,'principal_year':6,'upstream_capacity':1.,'nonsec_haircut':0.,'principal_recovery':1.,'old_pseudo_pool':False,'negative_parent_year':0}
HISTORY=[
[2021,13.09432064824,8.55292769606,8.44030376619,8.97425918175,44.04023656654,185.02025399391,.2211],
[2022,12.48557644196,8.50946123333,8.20446156837,1.27746589539,65.16466322324,211.88073016465,.1440],
[2023,11.08143928237,8.19346927799,7.86159896625,-3.13772469098,71.96286055982,239.57832055216,.1194],
[2024,11.60434309016,9.61012074364,9.25322890681,44.58787289143,80.72709052263,306.36935734730,.1264],
[2025,16.06774103951,12.08459494722,11.65388675489,-10.22224564514,91.87547095531,392.93374497620,.1403]]
def legal_reserve(profit,opening_retained,rate,cap_remaining=float('inf')):
    return min(max(0.,cap_remaining),max(0.,profit+min(0.,opening_retained))*rate)

def statutory(profit,retained,registered,reserve):
    # Paid-in capital is not the statutory ceiling. Registration changes no cash.
    return legal_reserve(profit,retained,.1,registered*.5-reserve)

def taxed(pretax,loss,rate):
    taxable=max(0.,pretax-max(0.,loss)); tax=taxable*rate
    closing=max(0.,loss- max(0.,pretax))+max(0.,-pretax)
    return pretax-tax,closing,tax

def collect_old(cash,retained,receivable,amount):
    received=min(max(0.,amount),max(0.,receivable))
    return cash+received,retained,receivable-received,received

def liquidation(assets,tax_basis,debt,cost,loss=0.,rate=.25,ownership=1.):
    # Proposed settlement waterfall, not evidence of executed bankruptcy payments.
    # Costs, taxes and full debt must all settle before common cash/cancellation.
    assert assets>=0 and debt>=0 and cost>=0 and 0<=ownership<=1
    tax=max(0.,assets-tax_basis-cost-loss)*rate
    residual=assets-debt-cost-tax
    cost_paid=min(assets,cost)
    tax_paid=min(max(0.,assets-cost_paid),tax)
    debt_paid=min(max(0.,assets-cost_paid-tax_paid),debt)
    feasible=residual>=0
    return dict(realized_assets=assets,asset_tax_basis=tax_basis,
                external_debt_paid=debt_paid,exit_cost=cost,tax=tax,
                feasible=feasible,ordinary_proceeds=max(0.,residual)*ownership,
                exit_cost_paid=cost_paid,exit_cost_unpaid=cost-cost_paid,
                tax_paid=tax_paid,tax_unpaid=tax-tax_paid,
                external_debt_unpaid=debt-debt_paid,
                settlement_complete=feasible,
                cash_after_senior_claims=max(0.,residual))

def capital_return(cash,shares,amount,cancel_fraction):
    assert 0<=cancel_fraction<=1 and amount<=cash and shares>0
    return {'cash_after':cash-amount,'shares_after':shares*(1-cancel_fraction),'distribution_per_original_share':amount/shares,'cancelled':shares*cancel_fraction}

def investment_exit(proceeds,dividend_component,cost,taxrate=.25):
    div=min(max(0.,dividend_component),proceeds)
    principal=proceeds-div
    gain=principal-cost
    return dict(dividend_income=div,investment_principal=principal,investment_tax_basis=cost,capital_gain=gain,tax=max(0.,gain)*taxrate,net_cash=proceeds-max(0.,gain)*taxrate)

def payment(want,cash,profit):
    return max(0.,min(want,cash,profit))
def step(st,t,cfg,sec_oper,other_oper):
    s=deepcopy(st); old=deepcopy(st)
    growth=cfg['growth'] if t<=5 else cfg['mature_growth']
    ks=s['sec_required']*(1+growth)*(cfg['capital_multiplier'] if t==1 else 1)
    ko=s['other_required']*(1+growth)
    sec_interest=max(0,s['sec_equity']-s['sec_required'])*cfg['cash_yield']
    oth_interest=max(0,s['other_equity']-s['other_required'])*cfg['cash_yield']
    activity_scale=ks/(80*cfg['capital_multiplier'])
    gross_assets=250*activity_scale
    funded_debt=gross_assets-ks
    baseline_debt=170*activity_scale
    funding=(funded_debt*(.018+cfg['funding_spread'])-baseline_debt*.018)*(.75 if cfg['tax_reset'] and t>=5 else .83)
    rate=.25 if cfg['tax_reset'] and t>=5 else .17
    ns,s['tax_loss_sec'],sec_tax=taxed((sec_oper+sec_interest-funding)/(1-rate),s['tax_loss_sec'],rate)
    # Three economic contributions; never offset one entity's tax loss against another.
    sub_oper=other_oper*(.3/3.4)
    sub_interest=max(0,s['nonsec_economic_equity']-s['nonsec_economic_required'])*cfg['cash_yield']
    sub_np=sub_oper+sub_interest
    own_pretax=(other_oper-sub_oper+oth_interest-sub_interest)/.83
    if cfg['negative_parent_year']==t: own_pretax=-5.
    own_np,s['tax_loss_parent'],parent_tax=taxed(own_pretax,s['tax_loss_parent'],.17)
    sub_np=sub_np if sub_np>=0 else sub_np/.83 # no instantaneous group tax refund
    no=own_np+sub_np
    stat_add=statutory(ns,s['sec_up'],12.7,s['sec_stat'])
    risk_add=legal_reserve(ns,s['sec_up'],.2)
    sec_reserve=risk_add+stat_add;s['sec_stat']+=stat_add;s['sec_risk']+=risk_add
    s['sec_up']+=ns-sec_reserve
    cash_sec=s['sec_equity']+ns-ks
    desired=.2*max(0,ns) if t<cfg['release_start'] else max(0,ns-(ks-s['sec_required']))+cfg['release_fraction']*max(0,s['sec_equity']-s['sec_required'])
    phase=min(1.,max(0.,(t-cfg['release_start']+1)/10.))
    if t>=cfg['release_start']: desired=.2*max(0,ns)+phase*(desired-.2*max(0,ns))
    if cfg['upstream_delay']>=t: desired=0
    up=payment(desired,cash_sec,s['sec_up'])
    sec_short=max(0,-cash_sec)
    s['sec_equity']+=ns-up;s['sec_up']-=up
    # Parent/nonsecurities operating profit is after all subsidiary technical charges;
    # intercompany dividend changes legal parent profit only, never group earnings.
    # NONSEC is an economic upstream budget, NOT a legal entity / reserve pool.
    # There is no invented registered capital, statutory reserve or pooled tax loss.
    sub_k=s['nonsec_economic_required']*(1+growth)
    sub_dk=sub_k-s['nonsec_economic_required']
    sub_excess=max(0,s['nonsec_economic_equity']-s['nonsec_economic_required'])
    principal_released=sub_excess if t>=cfg['principal_year'] else 0.
    eligible=max(0,sub_np-sub_dk)+principal_released
    sub_up=payment(eligible*cfg['upstream_capacity'],s['nonsec_economic_equity']+sub_np-sub_k,float('inf'))
    # Economic legal-capacity haircut retains cash and corresponding earnings until
    # later capacity permits payment; it is never labelled statutory retained profit.
    sub_up*=1-cfg['nonsec_haircut']
    sub_old_release=min(s['nonsec_original_principal'],max(0.,sub_up-max(0.,sub_np-sub_dk)))
    s['nonsec_original_principal']-=sub_old_release
    s['nonsec_accumulated_economic_earnings']+=sub_np-sub_up # economic accumulated earnings only
    s['nonsec_economic_equity']+=sub_np-sub_up
    s['nonsec_economic_required']=sub_k
    sub_reserve=0.
    parent_profit=own_np+sub_up+up
    # Registration at share capital + prospective option shares is conditional;
    # observed parent registration15.804037675 is separately stress-tested.
    pstat=statutory(parent_profit,s['parent_up'],SHARES+(DILUTION if t>=1 else 0),s['parent_stat'])
    s['parent_stat']+=pstat;s['parent_up']+=parent_profit-pstat
    exercise=DILUTION*EXERCISE if t==1 else 0
    rec=0.; portfolio_sale=0.
    if t>=cfg['principal_year']:
        _,_,s['parent_receivable'],rec=collect_old(0.,s['parent_up'],s['parent_receivable'],s['parent_receivable']*cfg['principal_recovery'])
        portfolio_sale=s['financial_principal']*cfg['principal_recovery'];s['financial_principal']-=portfolio_sale
    # Receivable and investment recovered at carrying amount: cash only, no new profit.
    # Securities refinances the loan with external borrowing; total funding unchanged.

    parent_cash=s['parent_cash']+own_np+sub_up+up-(ko-s['other_required']-sub_dk)+rec+portfolio_sale+exercise-(cfg['parent_extra_payment'] if t==1 else 0)
    desired_ext=([1.8,2.2,2.7,3.2,3.8][t-1] if t<=5 else max(0,no+up-(ko-s['other_required']))+cfg['release_fraction']*max(0,s['other_equity']-s['other_required']))
    if t>5: desired_ext=(3.8/16.311799145839785)*(ns+no)+phase*(desired_ext-(3.8/16.311799145839785)*(ns+no))
    realized_old_principal=rec+portfolio_sale+sub_old_release
    desired_ext+=realized_old_principal
    if cfg['zero_dividend']:desired_ext=0
    parent_cash-=cfg['collection_delay'] if t==1 else 0
    ext=payment(desired_ext,parent_cash-1.,s['parent_up'])
    s['parent_receivable']+=cfg['collection_delay'] if t==1 else 0
    s['parent_cash']=parent_cash-ext;s['parent_up']-=ext
    s['other_equity']+=no+up+exercise-ext-(cfg['parent_extra_payment'] if t==1 else 0)
    s['sec_required']=ks;s['other_required']=ko
    haircut=3.44114525163*activity_scale;core=s['sec_equity']-haircut
    risk=14*(ks/80); exposure=gross_assets
    deficit=max(sec_short,1-s['parent_cash'],2*risk-core,.16*exposure-core,0)
    expected=old['sec_equity']+old['other_equity']+ns+no+exercise-ext-(cfg['parent_extra_payment'] if t==1 else 0)
    assert abs(s['sec_equity']+s['other_equity']-expected)<1e-8
    assert up<=max(0,old['sec_up']+ns-sec_reserve)+1e-8
    row={'year':2026+t,'sec_operating_profit':sec_oper,'other_operating_profit':other_oper,'sec_surplus_income':sec_interest,'other_surplus_income':oth_interest,'incremental_financing_cost_after_tax':funding,'group_profit':ns+no,'sec_reserve_add':sec_reserve,'parent_stat_add':pstat,'sec_upstream_dividend':up,'nonsec_economic_profit':sub_np,'nonsec_reserve_NOT_APPLICABLE':sub_reserve,'nonsec_economic_payment':sub_up,'parent_direct_profit':own_np,'parent_legal_profit':parent_profit,'ordinary_dividend':ext,'distribution_per_share':ext/(SHARES+DILUTION),'exercise_cash':exercise,'receivable_collection':rec,'financial_principal_sale':portfolio_sale,'realized_old_principal':realized_old_principal,'sec_tax':sec_tax,'parent_tax':parent_tax,'sec_risk_add':risk_add,'nonsec_economic_upstream':sub_up,'nonsec_legal_capacity_assumption':cfg['upstream_capacity']*(1-cfg['nonsec_haircut']), 'sec_external_funding':funded_debt-s['parent_receivable'],'sec_external_and_internal_funding':funded_debt,'sec_operating_gross_assets':gross_assets,'sec_surplus_assets':s['sec_equity']-ks,'sec_base_funding_cost':funded_debt*.018,'capital_funding_gap':deficit,'core_net_capital':core,'risk_capital_requirement':risk,'risk_coverage':core/risk,'capital_leverage':core/exposure,**s}
    return s,row

def path(overrides=None,years=40):
    c=BASE| (overrides or {});s=deepcopy(INITIAL);rows=[];sec=c['sec_profit'];oth=c['other_profit']
    for t in range(1,years+1):
        if t>1:
            growth=c['growth'] if t<=5 else c['mature_growth'];sec*=1+growth;oth*=1+growth
        sp=sec;op=oth
        if c['tax_reset'] and t>=5:sp*=.75/.83
        sp*=c['profit_multiplier'];op*=c['profit_multiplier']
        if c.get('cyclical') and t<=2:sp*=.65;op*=.75
        if c.get('cyclical') and t==3:sp*=.85;op*=.9
        if c.get('structural'):
            sp*=.97**min(t-1,5);op*=.98**min(t-1,5)
        s,row=step(s,t,c,sp,op);rows.append(row)
        if row['capital_funding_gap']>1e-8:return {'feasible':False,'failure_year':2026+t,'rows':rows,'terminal':None}
    # Continue the identical legal/funding state; no liquidation of required capital
    # or independently chosen payout ratio is introduced at a horizon boundary.
    return {'feasible':True,'rows':rows,'terminal_state':s}

def value(p,r,g=.03):
    if not p['feasible']:return None
    rows=p['rows'];n=len(rows)
    # Finite-horizon Gordon approximation, not an exact finite-year growth claim.
    # Full 120/160/200 recurrences below check value and mature-state convergence.
    last=rows[-1]; terminal_distribution=last['ordinary_dividend']*(1+g)
    tv=terminal_distribution/(r-g)/(SHARES+DILUTION)
    dividends=[x['distribution_per_share'] for x in rows]
    pv=sum(d/(1+r)**(i+1) for i,d in enumerate(dividends))+tv/(1+r)**n
    tv5=sum(dividends[i]/(1+r)**(i-4) for i in range(5,n))+tv/(1+r)**(n-5)
    assert abs(pv-(sum(dividends[i]/(1+r)**(i+1) for i in range(5))+tv5/(1+r)**5))<1e-8
    return {'discount_rate':r,'current_value':pv,'year5_value':tv5,'year5_terminal_pv_share':tv5/(1+r)**5/pv,'tail_year':n,'tail_value':tv,'tail_pv_share':tv/(1+r)**n/pv}



def close_path(p,exit_year=20,asset_haircut=.02,investment_basis=40.51227686503,
               securities_exit_cost=1.,other_exit_cost=None,extra_external_debt=0.):
    """Economic exit only: not a forecast corporate resolution. Debt fully senior.
    Detailed offshore proceeds unknown: extra 0.15 of nonsec economic equity
    retained as realizability friction, NOT an invented foreign tax rate.
    """
    if not p['feasible']:return p
    rows=deepcopy(p['rows'][:exit_year]);s=rows[-1]
    debt=s['sec_external_and_internal_funding'];equity=s['sec_equity']
    # Customer cash and equal claims excluded on both sides; no net benefit.
    assets=debt+equity;tax_basis=assets
    sold=max(0.,assets-asset_haircut*s['sec_operating_gross_assets'])
    security=liquidation(sold,tax_basis,debt+extra_external_debt,securities_exit_cost,rate=.25)
    # Group owns 100% through 99.95% direct + 0.05% wholly owned intermediary.
    # 43.995 is parent BOOK cost, not verified tax basis: conditional 40.512 budget.
    other_debt_budget=48.97028465007*s['other_required']/13.
    nonsec_assets=s['other_equity']+other_debt_budget
    other_cost=1.+.15*s['nonsec_economic_equity'] if other_exit_cost is None else other_exit_cost
    other=liquidation(nonsec_assets,nonsec_assets,other_debt_budget,other_cost,rate=.25)
    if not security['feasible'] or not other['feasible']:
        # Atomic proposed exit is REJECTED. No sale/settlement has been executed;
        # preserve every annual cash/receivable/equity balance and original share.
        # Trial waterfall shortfalls are reported, never converted to forgiveness.
        retained=deepcopy(s)
        retained.update(shares=SHARES+DILUTION,
                        securities_total_debt=debt+extra_external_debt,
                        securities_external_debt=max(0.,debt-s['parent_receivable'])+extra_external_debt,
                        other_external_debt_budget=other_debt_budget)
        return {'feasible':False,'failure_year':s['year'],
                'failure_reason':'exit_senior_claims_or_costs_unpaid',
                'rows':rows,'terminal_state':retained,'finite_exit':False,
                'exit_attempt':{'executed':False,'securities':security,
                    'other_economic_net_assets':other,'shares_cancelled':0.,
                    'post_exit_shares':SHARES+DILUTION,'shareholder_cash':0.,
                    'retained_state':retained}}
    parent=investment_exit(security['ordinary_proceeds'],max(0,s['sec_up'])+s['sec_stat'],investment_basis)
    # Parent loans already included in other equity; repayment is cash conversion,
    # not an extra distribution. Securities repayment to parent is in total debt.
    proceeds=parent['net_cash']+other['ordinary_proceeds']
    share_exit=capital_return(proceeds,SHARES+DILUTION,proceeds,1.)
    s['exit']={'share_cancellation':share_exit,'securities':security,'parent_investment':parent,'other_economic_net_assets':other,'shareholder_cash':proceeds,'shares_cancelled':SHARES+DILUTION,'post_exit_shares':0,'capital_repayment_not_profit':True,'tax_basis_is_budget':True,'other_debt_is_economic_budget':True,'post_exit_state':{'securities_equity':0.,'other_equity':0.,'external_debt':0.,'shares':0.}}
    s['balance_basis']='annual balances before exit; exit.post_exit_state is after final distribution'
    s['ordinary_dividend']+=proceeds;s['distribution_per_share']=s['ordinary_dividend']/(SHARES+DILUTION)
    return {'feasible':security['feasible'] and other['feasible'],'rows':rows,'terminal_state':None,'finite_exit':True}

def valued(p,r,g=.03):
    if not p['feasible']:return None
    if not p.get('finite_exit'):return value(p,r,g)
    ds=[x['distribution_per_share'] for x in p['rows']]
    pv=sum(d/(1+r)**(i+1) for i,d in enumerate(ds));tv=sum(ds[i]/(1+r)**(i-4) for i in range(5,len(ds)))
    return {'discount_rate':r,'current_value':pv,'year5_value':tv,'year5_terminal_pv_share':tv/(1+r)**5/pv,'tail_year':len(ds),'tail_value':0.,'tail_pv_share':0.}

def cohort_audit(p):
    """FIFO ATTRIBUTION of economic surplus, not fabricated legal accounts.
    Every added financial-cash vintage remains in trace or is consumed/released.
    Necessary operating capital and parent buffer excluded from the surplus.
    """
    result={}
    for name,initial in [('securities',4.),('other',4.39849091709)]:
        batches=[{'origin':2026,'added':initial,'left':initial,'consumed':0.}];trace=[];prev=initial
        for row in p['rows']:
            if name=='securities': flow=row['group_profit']-row['parent_direct_profit']-row['nonsec_economic_profit']; dividend=row['sec_upstream_dividend']; ending=max(0,row['sec_equity']-row['sec_required'])
            else: dividend=row['ordinary_dividend'];ending=max(0,row['other_equity']-row['other_required']-1.)
            if 'exit' in row: ending=0.
            # Known balance transition separates contributions vs uses. Principal
            # collections within this economic bucket do NOT create new wealth.
            contribution=ending-prev+dividend
            if contribution>0:batches.append({'origin':row['year'],'added':contribution,'left':contribution,'consumed':0.})
            use=dividend+max(0,-contribution)
            for b in batches:
                q=min(use,b['left']);b['left']-=q;b['consumed']+=q;use-=q
                if use<1e-10:break
            assert use<1e-6
            assert abs(sum(b['left'] for b in batches)-ending)<1e-6
            trace.append({'year':row['year'],'financial_contribution':max(0,contribution),'use':dividend+max(0,-contribution),'closing':ending})
            prev=ending
        for b in batches:assert abs(b['added']-b['left']-b['consumed'])<1e-6
        result[name]={'vintages':batches,'trace':trace,'residual':prev}
    return result

SCENARIOS={
'base':{},
'cyclical_2027_2029':{'cyclical':True},
'structural_2027_on':{'structural':True,'profit_multiplier':.8,'growth':.01,'mature_growth':.01,'capital_multiplier':1.08,'funding_spread':.005,'exit_year':20},
'optimistic_2027_on':{'profit_multiplier':1.12,'growth':.06,'mature_growth':.03},
'capital_10pct_2027':{'capital_multiplier':1.10},
'funding_plus100bp_2027_on':{'funding_spread':.01},
'upstream_delayed_two_years':{'upstream_delay':2},
'maturity_release_delayed_to2037':{'release_start':11},
'no_tax_expiry_after2030':{'tax_reset':False},
'nonsec_capacity_50pct':{'upstream_capacity':.5},
'nonsec_capacity_zero_until_exit':{'upstream_capacity':0.,'exit_year':20},
'principal_recovery_delayed_10years':{'principal_year':11},
'principal_recovery_half_then_balance':{'principal_recovery':.5},
'parent_negative_2027':{'negative_parent_year':1},
'liquidity_failure':{'zero_dividend':True,'upstream_delay':2,'parent_extra_payment':3.314,'collection_delay':3.4}}

def scenario(c,n=200):
    p=path(c,n)
    return close_path(p,c['exit_year']) if c.get('exit_year') else p

def tests():
    # All call actual functions used to generate the official model.
    assert statutory(10,0,20,5)==1 # registered20, paid10 irrelevant
    assert statutory(10,-12,20,5)==0
    assert statutory(10,-6,20,5)==.4
    assert statutory(10,0,20,10)==0
    assert statutory(10,0,24,10)==1 # registered conversion; no invented cash
    assert collect_old(2,3,4,1)==(3,3,3,1)
    assert taxed(-5,0,.25)==(-5,5,0)
    assert taxed(3,5,.25)==(3,2,0)
    assert taxed(4,2,.25)==(3.5,0,.5)
    q=liquidation(30,30,20,2,ownership=.4)
    assert q['ordinary_proceeds']==3.2 and q['external_debt_paid']==20
    assert investment_exit(8,0,8)['capital_gain']==0
    assert capital_return(10,10,2,.2)=={'cash_after':8,'shares_after':8.,'distribution_per_original_share':.2,'cancelled':2.}
    assert capital_return(10,10,10,1)['shares_after']==0
    assert investment_exit(12,2,8)['tax']==.5
    assert liquidation(15,15,20,1)['ordinary_proceeds']==0
    p=path({'zero_dividend':True,'upstream_delay':2,'parent_extra_payment':3.314,'collection_delay':3.4})
    assert not p['feasible'] and p['rows'][0]['ordinary_dividend']==0
    x=path(years=40)
    assert x['rows'][5]['receivable_collection']==1.5
    assert x['rows'][5]['realized_old_principal']>2.09
    assert all(r['nonsec_reserve_NOT_APPLICABLE']==0 for r in x['rows'])
    assert abs(x['rows'][5]['parent_legal_profit']-(x['rows'][5]['parent_direct_profit']+x['rows'][5]['nonsec_economic_payment']+x['rows'][5]['sec_upstream_dividend']))<1e-9
    # Independent hand values: zero cash cannot pay one cost or twenty debt;
    # assets15/cost1/debt20 pays14 debt and leaves6; assets3/cost5 leaves2 cost.
    boundary={}
    for label,args,expected in [
        ('zero_realization',(0,30,20,1),(0,1,0,20,False)),
        ('debt_shortfall',(15,15,20,1),(1,0,14,6,False)),
        ('cost_shortfall',(3,3,20,5),(3,2,0,20,False)),
        ('positive_exit',(30,30,20,2),(2,0,20,0,True))]:
        q=liquidation(*args)
        actual=tuple(q[k] for k in ('exit_cost_paid','exit_cost_unpaid','external_debt_paid','external_debt_unpaid','settlement_complete'))
        assert actual==expected,(label,actual,expected)
        assert q['ordinary_proceeds']==(8 if label=='positive_exit' else 0)
        boundary[label]=q
    y=path(years=20);before=deepcopy(y);last=y['rows'][-1]
    shocks={'zero_asset_recovery':{'asset_haircut':10.},
            'unfunded_external_debt':{'extra_external_debt':10000.},
            'securities_cost_unpayable':{'securities_exit_cost':10000.},
            'other_cost_unpayable':{'other_exit_cost':10000.}}
    for label,params in shocks.items():
        q=close_path(y,20,**params)
        assert not q['feasible'] and not q['finite_exit'] and valued(q,.105) is None
        assert q['rows']==y['rows'] and 'exit' not in q['rows'][-1]
        assert q['exit_attempt']['executed'] is False
        assert q['exit_attempt']['shares_cancelled']==0
        assert q['exit_attempt']['post_exit_shares']==SHARES+DILUTION
        assert 'parent_investment' not in q['exit_attempt']
        for k,v in last.items():assert q['terminal_state'][k]==v
        assert q['terminal_state']['securities_total_debt']==last['sec_external_and_internal_funding']+params.get('extra_external_debt',0.)
        boundary[label]={'feasible':q['feasible'],'value':valued(q,.105),'attempt':q['exit_attempt']}
    good=close_path(y,20)
    assert good['feasible'] and good['finite_exit'] and valued(good,.105) is not None
    assert good['rows'][-1]['exit']['post_exit_shares']==0
    assert all(good['rows'][-1]['exit'][k]['settlement_complete'] for k in ('securities','other_economic_net_assets'))
    assert y==before # all calls are non-mutating, including failed proposals
    boundary['positive_full_path']={'value':valued(good,.105),'exit':good['rows'][-1]['exit']}
    return {'legacy_actual_function_cases':15,'status':'PASS',
            'zero_dividend_failure_year':p['failure_year'],'exit_boundary_cases':boundary}


def runoff(r,life=15,erosion=.04):
    # Independent economic method: no new client acquisition, progressively repay
    # financing before releasing operating equity. No terminal after closure.
    eq=102.39849091709-2.94609332017+DILUTION*EXERCISE
    req=70.;surplus=eq-req;cash=surplus;rows=[];v=0.;loss=0.
    # Exit legal entity uncertainty expressed as economic 3% friction, not tax.
    for t in range(1,life+1):
        debt0=217.47028465007*(1-(t-1)/life);debt1=217.47028465007*(1-t/life)
        k0=70*(1-(t-1)/life);k1=70*(1-t/life)
        rev=16.2*(1-erosion)**(t-1);cost=5.69*(1-erosion*.5)**(t-1)
        profit,loss,tax=taxed(rev-cost,loss,.17 if t<5 else .25)
        # Loan/investment liquidation is at book tax basis; repayment of external
        # financing happens IN FULL before residual capital reaches shareholders.
        gross_recovery=(debt0-debt1)+(k0-k1)
        waterfall=liquidation(gross_recovery,gross_recovery,debt0-debt1,0.)
        return_cap=waterfall['ordinary_proceeds']
        old_release=surplus/3 if t<=3 else 0
        capital_income=.025*k0;surplus_income=.015*cash;cash-=old_release
        closing_cost=2. if t==life else 0
        # Investors receive net proceeds only; friction includes approval, taxes
        # on unreconciled bases and intermediate shareholder costs, not income tax refunds.
        capital_friction=.03*(return_cap+old_release)
        d=profit+capital_income+surplus_income+return_cap+old_release-closing_cost-capital_friction
        v+=d/(1+r)**t
        rows.append(dict(year=2026+t,revenue=rev,cost=cost,pretax=rev-cost,tax=tax,loss_cf=loss,client_profit=profit,capital_income=capital_income,surplus_income=surplus_income,asset_recovery=gross_recovery,asset_tax_basis=gross_recovery,external_debt_repaid=debt0-debt1,capital_return=return_cap,old_surplus_release=old_release,closing_cost=closing_cost,realization_friction=capital_friction,shareholder_cash=d,remaining_external_debt=debt1,remaining_required_equity=k1,remaining_surplus=cash))
    assert abs(rows[-1]['remaining_external_debt'])<1e-9 and abs(rows[-1]['remaining_required_equity'])<1e-9
    return dict(value_per_share=v/(SHARES+DILUTION),rows=rows,equity_start=eq,shares=SHARES+DILUTION,assumption='economic realizability benchmark, not legal dividends per individual entity')
