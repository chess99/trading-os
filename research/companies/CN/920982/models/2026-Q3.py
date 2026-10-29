#!/usr/bin/env python3
"""Jinbo 2026Q3; CNY million/shares million. Self-contained economic budgets, not legal forecasts."""
import json, math, copy
ASOF='2026-10-29T02:25:00Z'
ACTUAL={'parent_cash':1021.52693950,'group_cash':1053.15732744,'parent_re':1852.44893504,'parent_reserve':57.53267,'registered':115.06534,'new_shares':3.607243,'issue_net':989.39366333,'treasury_shares':.5,'treasury_cost':81.71584687,'parent_investment_cost':157.747801,'fast_paid':115.,'fast_net':105.26178155,'fast_assets':189.19236455,'fast_old_loan':76.93957696,'fast_new_capital':85.,'fast_new_loan':904.39366333,'fast_total_budget':1260.295,'fast_preinvest':83.93917572,'old_policy_cash_bound':96.03116601,'parent_bank':286.14129167,'parent_lease':99.89559999,'old_rent':57.73191436,'external_fund_cost':30.,'external_commitment':71.25,'wuling_re':-37.402593,'wuling_capital':10.,'wuling_trade':55.60762207,'wuling_loan':.01191335,'dingzheng_re':-39.144091,'dingzheng_capital':5.8824,'dingzheng_loan':68.31757502,'dingzheng_assets':38.021385,'dingzheng_external':2.96550002}
# Opening cash allocations below are stated ECONOMIC BUDGETS within the observable group/mother difference.
# They are not invented individual Sep-30 bank balances; alternatives are fully projected.
BUDGET={'fast_cash':10.,'wuling_cash':15.,'dingzheng_cash':2.,'other_cash':4.63038794,'post_sep_project_cash':15.,'other_project':100.,'parent_wc':350.,'parent_ppe':831.52809608,'fast_wc':10.,'cash_floor':160.,'tax_parent':.15,'tax_sub':.25,'deposit_rate':.01,'bank_rate':.035}

def reserve_allocation(re_before,profit,reserve,capital):
    # Only positive current profit remaining AFTER historical loss absorption.
    eligible=max(0.,min(profit,re_before+profit))
    transfer=min(.1*eligible,max(0.,.5*capital-reserve))
    return re_before+profit-transfer,reserve+transfer,transfer

def distribute(s,profit,floor,payout=1.):
    old=s['re'];s['re'],s['reserve'],res=reserve_allocation(old,profit,s['reserve'],s['capital'])
    available=max(0.,s['cash']-floor)
    pay=min(max(0.,s['re']),available)*payout
    s['cash']-=pay;s['re']-=pay
    return pay,res

def entity(cash,re,capital,reserve=0.,loan=0.,ppe=0.,wc=0.,ext=0.):
    return dict(cash=cash,re=re,capital=capital,reserve=reserve,loan=loan,loan_allowance=0.,ppe=ppe,wc=wc,external_debt=ext,restricted=0.,investment_cost=0.,investment_allowance=0.)


def option_contract(calendar_year,group_nonrec_np_ex_sbc,personal_ratio=1.,elect=True):
    """Real award terms; metric is calendar audited consolidated attributable adjusted NP, NOT mother profit.
    Input here can be an explicit forecast, never relabelled as an audited future result.
    Shares in millions. Original windows35/35/30; remaining35:30 after first35 cancellation.
    """
    assert calendar_year in (2026,2027) and 0.<=personal_ratio<=1.
    tranche={2026:.289380,2027:.248040}[calendar_year]
    threshold={2026:1400.,2027:1800.}[calendar_year]
    new=tranche*personal_ratio if group_nonrec_np_ex_sbc>=threshold and elect else 0.
    return dict(calendar_year=calendar_year,performance_metric=group_nonrec_np_ex_sbc,threshold=threshold,tranche=tranche,new_shares=new,cash=new*209.27,capital_premium=new*(209.27-1.))

def configuration(name='base'):
    c=dict(name=name,method='products',r=.11,rev=1150.,single_margin=.87,skin_margin=.64,growth=.035,tail_growth=.01,fast_fee_markup=.05,fast_completion=3,fast_cost_factor=1.,fast_services=True,permanent_price=.0,cyclical=False,bank_refinance=False,cash_release=.65,treasury_recovery=1.,fund_recovery=1.,fund_exit=10,loan_recovery=.4,policy_cash=96.03116601,extra_project=100.,parent_cash_adjust=0.,sub_cash_shift=0.,wc_ratio=.30,credit_loss=.006,selling_rate=.27,fixed_cash_opex=245.,aux_roic=.225,other_capital_return=10,other_share=.90,ding_support_years=10000,fast_restricted_net_yield=0.,calendar_sbc_adjustment=0.,fail_credit=False)
    changes={
      'core_low':dict(r=.115,rev=1100.,single_margin=.86,growth=.03,selling_rate=.28),
      'core_high':dict(r=.105,rev=1200.,single_margin=.88,growth=.04,selling_rate=.26),
      'aux_low':dict(method='capital_return',aux_roic=.20,r=.115,growth=.02),
      'aux_high':dict(method='capital_return',aux_roic=.25,r=.105,growth=.02),
      'cyclical':dict(cyclical=True,wc_ratio=.36),
      'structural':dict(rev=1035.,single_margin=.78,skin_margin=.58,growth=0.,tail_growth=0.,permanent_price=.015,fast_cost_factor=1.2,credit_loss=.02,selling_rate=.30),
      'optimistic':dict(rev=1265.,single_margin=.90,growth=.06,tail_growth=.015,credit_loss=.004,selling_rate=.25),
      'r_plus_1pp':dict(r=.12),
      'slow_distribution':dict(cash_release=.3),
      'faster_distribution':dict(cash_release=1.),
      'no_fast_service_margin':dict(fast_fee_markup=0.),
      'fast_delay':dict(fast_completion=5,fast_cost_factor=1.2),
      'fund_half_recovery':dict(fund_recovery=.5,fund_exit=15),
      'treasury_cancel':dict(treasury_recovery=0.),
      'loan_zero_recovery':dict(loan_recovery=0.),
      'loan_full_asset_recovery':dict(loan_recovery=1.),
      'policy_restriction_zero':dict(policy_cash=0.),
      'project_overrun':dict(extra_project=150.,parent_cash_adjust=-15.),
      'cash_redistribution':dict(sub_cash_shift=10.),
      'other_capital_delayed':dict(other_capital_return=20),
      'other_minority_high':dict(other_share=.65),
      'other_wholly_owned':dict(other_share=1.),
      'issuance_settlement_release':dict(parent_cash_adjust=1.3),
      'ding_support_stops_y10':dict(ding_support_years=10),
      'restricted_net_yield_1pct':dict(fast_restricted_net_yield=.01),
      'calendar_option_sbc_plus100':dict(calendar_sbc_adjustment=100.),
      'unfunded_project':dict(parent_cash_adjust=-900.,fast_cost_factor=2.,fail_credit=True),
    }
    c.update(changes.get(name,{}));return c

def opening(c):
    a=ACTUAL;b=BUDGET
    p=entity(a['parent_cash']-b['post_sep_project_cash']+c['parent_cash_adjust'],a['parent_re'],a['registered'],a['parent_reserve'],ppe=b['parent_ppe'],wc=b['parent_wc'],ext=a['parent_bank'])
    p.update(lease=a['parent_lease'],rou=95.30699725,investment_cost=a['parent_investment_cost'],investment_allowance=0.,restricted=c['policy_cash'],fund_cost=33.681117,fund_allowance=0.,capital_premium=287.02600874+a['issue_net']-a['new_shares'],treasury_cost=a['treasury_cost'],treasury_shares=.5,old_rent=a['old_rent'])
    p['cash']-=c['policy_cash'];p['restricted']+=a['issue_net']
    f=entity(b['fast_cash']+c['sub_cash_shift'],a['fast_net']-115.,115.,loan=a['fast_old_loan']+b['post_sep_project_cash'],ppe=a['fast_assets']-b['fast_cash']-b['fast_wc']+b['post_sep_project_cash'],wc=b['fast_wc'],ext=a['fast_assets']-a['fast_net']-a['fast_old_loan'])
    w=entity(b['wuling_cash']-c['sub_cash_shift'],a['wuling_re'],10.,loan=a['wuling_trade']+a['wuling_loan'],ppe=1.196,wc=31.426695,ext=19.40575958)
    d=entity(b['dingzheng_cash'],a['dingzheng_re'],a['dingzheng_capital'],loan=a['dingzheng_loan'],ppe=a['dingzheng_assets']-b['dingzheng_cash'],ext=a['dingzheng_external'])
    o=entity(b['other_cash'],-15.,35.2,loan=8.76657843,ppe=20.,wc=5.,ext=5.)
    return dict(parent=p,fast=f,wuling=w,dingzheng=d,other=o,registered=p['capital'],committed_new_shares=a['new_shares'],option_remaining=.53742,common_shares=p['capital']-.5,fast_capex_remaining=(a['fast_total_budget']-a['fast_preinvest'])*c['fast_cost_factor'],parent_loans={'fast':f['loan'],'wuling':w['loan'],'dingzheng':d['loan'],'other':o['loan']},parent_allowances={'fast':0.,'wuling':0.,'dingzheng':0.,'other':0.},nci_equity={'wuling':-9.0267,'dingzheng':-.4837,'other':2.8589917},other_cost=30.2,last_group_adjusted_np=0.,status='feasible',unpaid_external=0.)

def operate(s,profit,da,capex,new_wc,interest=0.,principal=0.,cash_other=0.):
    delta_wc=new_wc-s['wc'];s['ppe']+=capex-da;s['wc']=new_wc
    s['cash']+=profit+da-capex-delta_wc-principal+cash_other
    s['external_debt']-=principal
    return dict(profit=profit,da=da,capex=capex,delta_wc=delta_wc,interest=interest,external_principal=principal,cash_other=cash_other)

def step(s,c,t):
    p=s['parent'];f=s['fast'];w=s['wuling'];d=s['dingzheng'];o=s['other'];a=ACTUAL;b=BUDGET
    prev=copy.deepcopy(s);flows={};parent_other=0.;parent_invest_profit=0.;group_external_capex=0.
    other_subscription=46.95/3. if t<=3 else 0.
    o['cash']+=other_subscription;o['capital']+=other_subscription
    # 10m Ding-tian subscribed cost was already in mother investment; settle that payable, do not book investment twice.
    new_other_cost=other_subscription-(10./3. if t<=3 else 0.)
    p['investment_cost']+=new_other_cost;s['other_cost']+=new_other_cost
    # Issue cash and shares are both in opening bridge; planned 85m paid capital +904.394m loan transferred together.
    if t==1:
        p['capital']+=s['committed_new_shares'];s['registered']+=s['committed_new_shares'];s['committed_new_shares']=0.
        p['restricted']-=a['issue_net'];f['restricted']+=a['issue_net'];f['capital']+=85.;p['investment_cost']+=85.;f['loan']+=a['fast_new_loan'];s['parent_loans']['fast']+=a['fast_new_loan']
        # H1 explicitly restricts policy financing to FAST, not the mother's other factory.
        policy=c['policy_cash'];p['restricted']-=policy;f['restricted']+=policy;f['loan']+=policy;s['parent_loans']['fast']+=policy
        # Approved pre-investment replacement reclassifies cash, not profit or new group funding.
        f['restricted']-=a['fast_preinvest'];f['cash']+=a['fast_preinvest']
    # Existing bank debt and leases are finite; no implicit unlimited refinancing.
    bank_pr=min(p['external_debt'],[87.01204167,70.,70.,59.12925][t-1] if t<=4 else p['external_debt'])
    bank_interest=p['external_debt']*b['bank_rate']
    lease_interest=p['lease']*.03
    lease_payment=min(p['lease']+lease_interest,28.)
    lease_pr=min(p['lease'],max(0.,lease_payment-lease_interest));p['lease']-=lease_pr
    rou_da=min(p['rou'],95.30699725/4.);p['rou']-=rou_da
    short_rent=28.-lease_payment # replacement short-term workspace rental budget, not a disappearing operating cost.
    old_rent=min(p['old_rent'],a['old_rent']/2.);p['old_rent']-=old_rent
    # External committed fund and small associate investments: cost remains until real modeled realization.
    invest= (a['external_commitment']/3. if t<=3 else 0.)
    p['fund_cost']+=invest
    fund_cash=0.;fund_profit=0.
    if t==c['fund_exit']:
        gross=p['fund_cost']*c['fund_recovery'];fee=.02*gross;tax=.25*max(0.,gross-fee-p['fund_cost']);fund_cash=gross-fee-tax;fund_profit=fund_cash-p['fund_cost'];p['fund_cost']=0.;p['fund_allowance']=0.
    # Treasury is already paid. A resale is not a dividend; cancellation does not repay historic cash twice.
    treasury_cash=0.
    if t==2 and p['treasury_shares']>0 and c['treasury_recovery']>0:
        treasury_cash=a['treasury_cost']*c['treasury_recovery'];p['capital_premium']+=treasury_cash-p['treasury_cost'];p['treasury_cost']=0.;p['treasury_shares']=0.
    if t==3 and p['treasury_shares']>0:
        p['capital']-=p['treasury_shares'];s['registered']-=p['treasury_shares'];p['capital_premium']-=p['treasury_cost']-p['treasury_shares'];p['treasury_cost']=0.;p['treasury_shares']=0.
    # Finished platform provides internal research service at budgeted full cost plus markup. No invented external drug revenue.
    completion=c['fast_completion'];build=min(s['fast_capex_remaining'],(a['fast_total_budget']-a['fast_preinvest'])*c['fast_cost_factor']/completion) if t<=completion else 0.
    s['fast_capex_remaining']-=build
    f_wc_add=build*(36.6175/(a['fast_total_budget']-a['fast_preinvest']))
    fast_da=f['ppe']/20. if t>completion else 0.
    fast_maint=fast_da if t>completion else 0.
    fast_running=(24. if t>completion else 4.)*((1+c['tail_growth'])**max(0,t-completion-1))
    fee=(fast_da+fast_running)*(1+c['fast_fee_markup']) if t>completion else fast_running
    f_interest=f['external_debt']*.035;f_pr=min(f['external_debt'],a['fast_assets']-a['fast_net']-a['fast_old_loan']) if t==2 else 0.
    f_profit=(fee-fast_running-fast_da-f_interest)*(1-.25) # no fictitious tax refund on a loss
    if fee-fast_running-fast_da-f_interest<0:f_profit=fee-fast_running-fast_da-f_interest
    f_capex=build-f_wc_add+fast_maint
    restricted_income=max(0.,f['restricted']-min(f['restricted'],build)/2.)*c['fast_restricted_net_yield']
    f['restricted']+=restricted_income;f_profit+=restricted_income
    restricted_spend=min(f['restricted'],build);f['restricted']-=restricted_spend;f['cash']+=restricted_spend
    flows['fast']=operate(f,f_profit,fast_da,f_capex,f['wc']+f_wc_add,interest=f_interest,principal=f_pr,cash_other=-restricted_income)
    flows['fast']['restricted_net_income']=restricted_income
    # Wuling: real 65% holding, historical trade balance collected only out of its actual surplus.
    growth=(1+c['growth'])**min(t-1,9)*(1+c['tail_growth'])**max(0,t-10)
    w_rev=110.*growth*(.8 if c['cyclical'] and t<=2 else 1.)
    w_operating=(.04 if c['permanent_price']==0 else .01)*w_rev
    w_np=w_operating*(1-.25);w_da=.12*growth;w_cap=w_da;w_pr=min(w['external_debt'],19.40575958/4.) if t<=4 else 0.
    flows['wuling']=operate(w,w_np,w_da,w_cap,31.426695*growth,principal=w_pr)
    # Dingzheng is an explicit conditional IP runoff, not a legal termination. Unpaid face survives with allowance.
    d_np=-.1;d_cash_other=0.;d_pr=0.
    if t==3:
        gross=d['ppe']*c['loan_recovery'];fees=1.+.05*gross;tax=.25*max(0.,gross-fees-d['ppe']);net=max(0.,gross-fees-tax);d_np+=net-d['ppe'];d['ppe']=0.;d_cash_other=net;d_pr=min(d['external_debt'],max(0.,d['cash']+net-.1))
    flows['dingzheng']=operate(d,d_np,0.,0.,0.,principal=d_pr,cash_other=d_cash_other-(d_np+.1 if t==3 else 0.))
    # The disposal loss is noncash: above cash_other reverses it, leaving net proceeds and administration expense.
    # Other named controlled R&D/marketing entities grouped solely for economic budget; not represented as one legal entity.
    o_np=(-2. if t<=3 else .5*growth)+max(0.,prev['other']['cash'])*.01*.75;o_da=.5;o_cap=.5;o_pr=min(o['external_debt'],1.)
    flows['other']=operate(o,o_np,o_da,o_cap,5.*growth,principal=o_pr)
    other_return=0.;other_return_profit=0.;other_nci_return=0.
    if t==c['other_capital_return']:
        # Conditional individual-company capital reduction budgets, not a documented authorization or one fictitious legal issuer.
        total=min(max(0.,o['cash']-8.),max(0.,o['capital']-25.))
        basis=s['other_cost']*total/o['capital'];gross=total*c['other_share'];fees=.01*gross;tax=.25*max(0.,gross-fees-basis)
        other_return=gross-fees-tax;other_return_profit=other_return-basis;other_nci_return=total*(1-c['other_share'])
        o['cash']-=total;o['capital']-=total;s['other_cost']-=basis;p['investment_cost']-=basis
    # Mother-funded deficits create real intercompany claims, never free equity or negative cash.
    support_total=0.;repayment_total=0.;dividend_total=0.;nci_dividend=0.;impairment=0.
    for key,child,floor,share in [('fast',f,10.,1.),('wuling',w,10.,.65),('dingzheng',d,.1,.85),('other',o,4.,c['other_share'])]:
        support=max(0.,floor-child['cash'])
        if key=='dingzheng' and t>c['ding_support_years']:
            support=0.
            # Refusing another parent loan does not cancel the subsidiary's administration bill or existing debt.
            unpaid=max(0.,-child['cash'])
            if unpaid:
                child['external_debt']+=unpaid;child['cash']+=unpaid;s['unpaid_external']+=unpaid
                flows[key]['cash_other']+=unpaid;flows[key]['unpaid_administration']=unpaid
        if support:child['cash']+=support;child['loan']+=support;s['parent_loans'][key]+=support;support_total+=support
        repayment=min(child['loan'],max(0.,child['cash']-floor)*(.5 if key=='fast' else .7))
        child['cash']-=repayment;child['loan']-=repayment;s['parent_loans'][key]-=repayment;repayment_total+=repayment
        profit=flows[key]['profit'];dv,rs=distribute(child,profit,floor,.7)
        dividend_total+=dv*share;nci_dividend+=dv*(1-share)
        # Explicit recognition of creditor shortfall, no deletion of debt/claim face and no rebooking recovered principal as earnings.
        target=child['loan'] if key=='dingzheng' and t>=3 else 0.
        delta=target-s['parent_allowances'][key];s['parent_allowances'][key]=target;child['loan_allowance']=target;impairment+=delta
        if key in s['nci_equity']:s['nci_equity'][key]+=profit*(1-share)-dv*(1-share)-(other_nci_return if key=='other' else 0.)
        flows[key].update(parent_support=support,principal_to_parent=repayment,dividend=dv,parent_dividend=dv*share,nci_dividend=dv*(1-share),reserve_transfer=rs,credit_allowance=target)
    # A failed subsidiary investment is impaired separately from its debt. This is a mother legal-profit item, not a second group cash cost.
    investment_loss=5. if t==3 else 0.;p['investment_allowance']+=investment_loss
    # Products vs independent capital-return forecast entry. Shared ownership bridge does not make independent operating hypotheses identical.
    phase_growth=(1+c['growth'])**min(t-1,9)*(1+c['tail_growth'])**max(0,t-10)
    cyc_factor=([.80,.88,.97][t-1] if c['cyclical'] and t<=3 else 1.)
    rev=c['rev']*phase_growth*cyc_factor*((1-c['permanent_price'])**min(t-1,15))
    da=p['ppe']*.10
    desired_wc=c['wc_ratio']*rev
    growth_capex=max(0.,rev-prev.get('last_revenue',c['rev']))*.35
    ordinary_build=(c['extra_project']/2. if t<=2 else 0.)
    # Existing policy-restricted cash can only fund qualifying construction, not dividends.
    release=min(p['restricted'],ordinary_build);p['restricted']-=release;p['cash']+=release
    # Any unused old policy cash remains earmarked then discharges its associated bank debt, never silently made dividend cash.
    if t==4 and p['restricted']>0:
        release_debt=min(p['restricted'],bank_pr);p['restricted']-=release_debt;p['cash']+=release_debt
    p_capex=da+growth_capex+ordinary_build
    if c['method']=='products':
        # Segment margins are accounting gross margins (already include manufacturing DA). Reconstruct cash gross before subtracting DA once.
        gross=rev*((820/1150)*c['single_margin']+(60/1150)*.62+(230/1150)*c['skin_margin']+(40/1150)*.70)+da
        cash_opex=rev*(c['selling_rate']+.018+c['credit_loss'])+c['fixed_cash_opex']*phase_growth
        ebit=gross-cash_opex-da-rou_da-short_rent-fee
    else:
        # Independent sustainable earnings on physical + working productive capital, not a multiple of method-one earnings.
        productive=831.52809608+350.
        preplatform_nopat=productive*c['aux_roic']*phase_growth
        ebit=preplatform_nopat/(1-b['tax_parent'])-fee-rou_da-short_rent
        gross=None;cash_opex=None
    financial_income=max(0.,prev['parent']['cash'])*b['deposit_rate']
    operating_pre_tax=ebit-bank_interest-lease_interest+financial_income
    tax=max(0.,operating_pre_tax)*b['tax_parent'];own_np=operating_pre_tax-tax
    parent_np=own_np+dividend_total+fund_profit+other_return_profit-impairment-investment_loss
    parent_other=repayment_total-support_total+dividend_total+fund_cash-invest+treasury_cash-old_rent-other_subscription+other_return
    # Parent NP already includes dividends and disposal earnings; remove them before cash bridge then add actual receipt/cost.
    parent_other-=dividend_total+fund_profit+other_return_profit-impairment-investment_loss
    flows['parent']=operate(p,parent_np,da,p_capex,desired_wc,interest=bank_interest+lease_interest,principal=bank_pr,cash_other=parent_other-lease_pr+rou_da)
    # Fund/cash principal is not an extra terminal asset: only actual cash receipts and future dividends are valued.
    if p['cash'] < -1e-7 or s['unpaid_external']>1e-9:
        s['status']='infeasible';s['unpaid_external']=max(s['unpaid_external'],-p['cash']);return s,dict(year=t,status='infeasible',unpaid_cash_obligation=s['unpaid_external'],states=copy.deepcopy(s),flows=flows)
    floor=b['cash_floor']*phase_growth
    payout=c['cash_release'] if t>3 else min(c['cash_release'],.15)
    parent_div,res=distribute(p,parent_np,floor,payout)
    # Calendar-company performance bridge, separate from rolling mother profit. Forecast only; audit and personal eligibility remain conditions.
    group_adjusted_np=own_np+sum(flows[k]['profit']*share for k,share in [('fast',1.),('wuling',.65),('dingzheng',.85),('other',c['other_share'])])
    option_cash=0.;option_new=0.;assessment=None
    if t in (1,2):
        calendar_year=2025+t
        if t==1:
            # Known 2026 9M consolidated attributable non-recurring-adjusted income plus a separately budgeted Q4.
            q4_budget=55.*(c['rev']/1150.)*(c['single_margin']/.87)
            performance=322.34745027+q4_budget+c['calendar_sbc_adjustment']
        else:
            # 2027 Jan1-Oct29 =301 days of rolling year1, Oct29-Jan1=64 days of rolling year2.
            # Uniform intrayear earning is a calendar conversion BUDGET, not actual calendar results.
            performance=prev['last_group_adjusted_np']*(301./365.)+group_adjusted_np*(64./365.)+c['calendar_sbc_adjustment']
        performance=c.get('option_metric_override',{}).get(calendar_year,performance)
        assessment=option_contract(calendar_year,performance,c.get('option_personal_ratio',1.),c.get('option_elect',True))
        option_new=assessment['new_shares'];option_cash=assessment['cash']
        p['cash']+=option_cash;p['capital']+=option_new;p['capital_premium']+=assessment['capital_premium'];s['registered']+=option_new
        s['option_remaining']=max(0.,s['option_remaining']-assessment['tranche'])
    s['last_group_adjusted_np']=group_adjusted_np
    s['common_shares']=s['registered']-p['treasury_shares'];s['last_revenue']=rev
    flows['parent'].update(rou_depreciation=rou_da,revenue=rev,gross_profit=gross,cash_opex=cash_opex,ebit=ebit,own_np=own_np,tax=tax,financial_income=financial_income,service_fee=fee,dividend=parent_div,reserve_transfer=res,loan_repayment=repayment_total,loan_support=support_total,child_dividends=dividend_total,credit_impairment=impairment,investment_impairment=investment_loss,fund_cash=fund_cash,fund_profit=fund_profit,fund_subscription=invest,treasury_cash=treasury_cash,lease_principal=lease_pr,lease_cash=lease_payment,old_rent_paid=old_rent,option_cash=option_cash,option_new=option_new,other_subscription=other_subscription,other_capital_return=other_return,other_return_profit=other_return_profit,other_nci_capital_return=other_nci_return,group_adjusted_np_budget=group_adjusted_np,option_assessment=assessment)
    # Legal child dividends reduce child RE before the mother's investment income is booked; shared source has no second group profit.
    return s,dict(year=t,status='feasible',states=copy.deepcopy(s),flows=flows,dividend_per_share=parent_div/s['common_shares'],nci_dividend=nci_dividend)

def project(c,years=240):
    s=opening(c);rows=[]
    for t in range(1,years+1):
        s,row=step(s,c,t);rows.append(row)
        if s['status']!='feasible':break
    if s['status']!='feasible':return dict(config=c,status='infeasible',years=rows,value=None,holder=None)
    value=sum(x['dividend_per_share']/(1+c['r'])**x['year'] for x in rows)
    term=sum(x['dividend_per_share']/(1+c['r'])**(x['year']-5) for x in rows if x['year']>5)
    return dict(config=c,status='feasible',years=rows,value=value,holder=dict(distributions=[x['dividend_per_share'] for x in rows[:5]],terminal_y5=term),remaining_discounted_tail_bound=rows[-1]['dividend_per_share']*(1+c['tail_growth'])/(c['r']-c['tail_growth'])/(1+c['r'])**years)

def selftest():
    # Same production reserve/distribution function, explicit arithmetic: -5 +8 leaves3, reserve .3, cash20, distribution2.7.
    z=entity(20.,-5.,100.);pay,rs=distribute(z,8.,0.);assert abs(pay-2.7)<1e-10 and abs(rs-.3)<1e-10 and abs(z['cash']-17.3)<1e-10
    z=entity(1.,10.,100.);pay,rs=distribute(z,10.,.5);assert pay==.5 and rs==1.
    # Same cash-operation function:10+profit4+DA2-capex3-WC1-principal2=10.
    z=entity(10.,0.,10.,ppe=20.,wc=5.,ext=8.);operate(z,4.,2.,3.,6.,principal=2.);assert z['cash']==10 and z['external_debt']==6 and z['ppe']==21
    bad=project(configuration('unfunded_project'),10);assert bad['status']=='infeasible' and bad['value'] is None and bad['holder'] is None
    a=option_contract(2026,1400.);b=option_contract(2027,1800.);z=option_contract(2026,1399.99)
    assert a['new_shares']==.28938 and b['new_shares']==.24804 and z['new_shares']==0.
    assert option_contract(2027,1800.,personal_ratio=0.)['new_shares']==0.
    return {'production_handexamples':3,'real_calendar_option_contract_boundaries':4,'refused_financing_fail_closed':True}

def main():
    names=['base','core_low','core_high','aux_low','aux_high','cyclical','structural','optimistic','r_plus_1pp','slow_distribution','faster_distribution','no_fast_service_margin','fast_delay','fund_half_recovery','treasury_cancel','loan_zero_recovery','loan_full_asset_recovery','policy_restriction_zero','project_overrun','cash_redistribution','other_capital_delayed','other_minority_high','other_wholly_owned','issuance_settlement_release','ding_support_stops_y10','restricted_net_yield_1pct','calendar_option_sbc_plus100','unfunded_project']
    cases={n:project(configuration(n)) for n in names}
    # Terminal interval varies valuation discount cost on the SAME baseline operating/cash/ownership history.
    base=cases['base'];terminal=[]
    for r in (.115,.105):terminal.append(sum(x['dividend_per_share']/(1+r)**(x['year']-5) for x in base['years'] if x['year']>5))
    holder={'schema_version':1,'method':'annual_common_equity_irr_v1','currency':'CNY','model_as_of':ASOF,'base_case_distributions_per_share':base['holder']['distributions'] if base['holder'] else None,'base_case_terminal_equity_value_range_per_share':{'year_5':{'low':min(terminal),'high':max(terminal)}}}
    out={'company':'锦波生物','symbol':'CN:920982','information_cutoff':ASOF,'units':'CNY million; million shares; CNY/share','actual':ACTUAL,'economic_budgets':BUDGET,'cases':cases,'value_range':{'low':cases['core_low']['value'],'high':cases['core_high']['value'],'currency':'CNY'},'return_model':holder,'convergence':{str(n):project(configuration('base'),n)['value'] for n in (120,180,240,360)},'extended_base_360':project(configuration('base'),360),'tests':selftest()}
    print(json.dumps(out,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False))
if __name__=='__main__':main()
