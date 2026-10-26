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


OLD_SOURCE='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'

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

def main():
    old={};exec(zlib.decompress(base64.b64decode(OLD_SOURCE)),old)
    output={'as_of':'2026-10-26T11:15:00+00:00','unit':'CNY billion; shares billion','initial':INITIAL,'assumptions':BASE,'scenarios':{},'tests':tests(),'convergence':{},'old_new_same_economics':{},'auxiliary':{'low':runoff(.115,12,.06),'high':runoff(.10,18,.03)}}
    for name,c in SCENARIOS.items():
        p=scenario(c,200);output['scenarios'][name]={'changes':c,'path':p,'value':valued(p,.105,c.get('mature_growth',.03)),'cohorts':cohort_audit(p) if p['feasible'] else None}
        # Isolate implementation effects before separately adding economic exit.
        op=old['path'](c,200);np=path(c,200)
        legal_only=path(c|{'principal_year':10000},200)
        output['old_new_same_economics'][name]={'comparison_valid_for_original_parameters':not any(k in c for k in ('upstream_capacity','principal_year','principal_recovery','negative_parent_year')),'new_policy_parameters_are_not_pure_legal_corrections':[k for k in c if k in ('upstream_capacity','principal_year','principal_recovery','negative_parent_year','exit_year')],'old':old['value'](op,.105,c.get('mature_growth',.03)),'legal_only_no_new_recovery_policy':valued(legal_only,.105,c.get('mature_growth',.03)),'legal_only_rows':legal_only['rows'],'new_without_exit_parameter':valued(np,.105,c.get('mature_growth',.03)),'old_rows':op['rows'],'new_rows':np['rows'],'economic_exit_delta':None if not p['feasible'] else valued(p,.105,c.get('mature_growth',.03))['current_value']-valued(np,.105,c.get('mature_growth',.03))['current_value']}
    for n in (120,160,200,260):
        output['convergence'][str(n)]={name:{'value':valued(scenario(c,n),.105,c.get('mature_growth',.03)),'last':scenario(c,n)['rows'][-1]} for name,c in SCENARIOS.items()}
    p=scenario({});old_core=old['path']({},200);law_core=path({'principal_year':10000},200)
    output['core_method_bridge']={k:{'old':old['value'](old_core,r),'legal_only_same_economics':valued(law_core,r),'new_with_realization_policy':valued(p,r),'old_first5_D':[z['distribution_per_share'] for z in old_core['rows'][:5]],'legal_first5_D':[z['distribution_per_share'] for z in law_core['rows'][:5]],'new_first5_D':[z['distribution_per_share'] for z in p['rows'][:5]]} for k,r in [('low',.115),('high',.10)]}
    output['core_endpoints']={k:valued(p,r) for k,r in [('low',.115),('high',.10)]}
    output['core_distributions']=[r['distribution_per_share'] for r in p['rows'][:5]]
    # 20/30/40 exits only as cross-checks, not the continuing-business core.
    output['exit_life_sensitivity']={str(n):valued(close_path(path(years=n),n),.105) for n in (20,30,40)}
    output['exit_tax_basis_sensitivity']={str(b):valued(close_path(path(years=20),20,investment_basis=b),.105) for b in (38.,40.51227686503,44.)}
    output['exit_asset_haircut_sensitivity']={str(h):valued(close_path(path(years=20),20,asset_haircut=h),.105) for h in (0.,.02,.05)}
    raw=json.dumps(output,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()+b'\n'
    dest=Path(__file__).with_name('2026-Q3-output.json.gz');dest.write_bytes(gzip.compress(raw,mtime=0))
    summary={k:output[k] for k in ['as_of','core_endpoints','core_distributions','tests','exit_life_sensitivity']}
    summary.update(scenarios={k:v['value'] for k,v in output['scenarios'].items()},auxiliary={k:v['value_per_share'] for k,v in output['auxiliary'].items()},output_sha256=hashlib.sha256(raw).hexdigest(),compressed_sha256=hashlib.sha256(dest.read_bytes()).hexdigest())
    Path(__file__).with_name('summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    write_transport(raw,dest.read_bytes(),summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2))
def write_transport(raw,compressed,summary):
    """UTF-8 publication envelope only; canonical full output is unchanged."""
    envelope={
        'schema':'cn-equity-model-output-gzip-base64-v1',
        'symbol':'CN:300059','report_period':'2026-Q3',
        'packaging_status':'transport_only_not_publication_closed',
        'encoding':'base64+gzip','gzip_mtime':0,
        'full_output_bytes':len(raw),'full_output_sha256':hashlib.sha256(raw).hexdigest(),
        'compressed_bytes':len(compressed),'compressed_sha256':hashlib.sha256(compressed).hexdigest(),
        'summary':summary,
        'expand_command':'python 2026-Q3.py --expand [target.json]',
        'payload_base64':base64.b64encode(compressed).decode('ascii')}
    Path(__file__).with_name('2026-Q3-output.json').write_text(json.dumps(envelope,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def expand_transport(target=None):
    envelope=json.loads(Path(__file__).with_name('2026-Q3-output.json').read_text(encoding='utf-8'))
    assert envelope['schema']=='cn-equity-model-output-gzip-base64-v1'
    compressed=base64.b64decode(envelope['payload_base64'],validate=True)
    assert len(compressed)==envelope['compressed_bytes']
    assert hashlib.sha256(compressed).hexdigest()==envelope['compressed_sha256']
    raw=gzip.decompress(compressed)
    assert len(raw)==envelope['full_output_bytes']
    assert hashlib.sha256(raw).hexdigest()==envelope['full_output_sha256']
    json.loads(raw) # ensure full canonical output is valid JSON before writing
    dest=Path(target) if target else Path(__file__).with_name('2026-Q3-output.expanded.json')
    if dest.resolve() in (Path(__file__).resolve(),Path(__file__).with_name('2026-Q3-output.json').resolve()):
        raise ValueError('Expansion target must not overwrite model or envelope')
    dest.write_bytes(raw)
    print(str(dest))

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description='Generate deterministic full model output and UTF-8 transport envelope, or expand envelope.')
    parser.add_argument('--expand',nargs='?',const='',metavar='TARGET',help='Decode full canonical JSON; default: 2026-Q3-output.expanded.json')
    args=parser.parse_args()
    if args.expand is not None:expand_transport(args.expand or None)
    else:main()

