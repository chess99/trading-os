#!/usr/bin/env python3
"""Gree CN:000651 2026-Q3; stdlib only; CNY billion, billion shares.
python 2026-Q3.py --output result.json [--expand full.json]
Economic subsidiary budget is NOT a fictional legal entity. Only parent retained earnings
are a known legal account; all subsidiary remittances are conditional budget estimates.
"""
import argparse, copy, json, math, gzip, base64, hashlib
from pathlib import Path
ASOF='2026-10-26T21:05:30+00:00'
FACTS={'cash':117.51612395099,'trading':36.90545281127,'current_noncurrent':15.90953100220,
       'debt_investment':35.47025242991,'noncurrent_other':44.81056870791,
       'nonfinancial_other_excluded':.23228220806,'current_finance_estimate_h1':13.48029639344,
       'equity_investments':1.56955343919+.0927089847+2.66664326204,
       'external_loans':.72771478356,'external_debt':83.44040109325,'external_deposits':.16118650506,
       'common_book_equity':150.48538383222,'nci':3.90329889331,'finance_equity_fy2025':7.36682,'parent_retained':91.56066899799,
       'parent_reserve':2.8007028705,'paid_share_capital':5.601405741,'shares':5.601405741,
       'already_bought':.0283198,'already_cost':1.08337963314,'buyback_minimum':5.,'buyback_cap':54.55}
GROSS=sum(FACTS[k] for k in ['cash','trading','current_noncurrent','debt_investment','noncurrent_other','current_finance_estimate_h1','equity_investments','external_loans'])-FACTS['nonfinancial_other_excluded']
# Recoverability budget, not an observed write-down; charged once against opening principal.
HAIRCUT=(GROSS-FACTS['cash']-FACTS['equity_investments'])*.02+FACTS['equity_investments']*.25
NET=GROSS-HAIRCUT-FACTS['external_debt']-FACTS['external_deposits']-FACTS['nci']-FACTS['finance_equity_fy2025']
DEFAULT={'name':'base','r':.095,'g_terminal':.01,'years':60,'revenue':160.,'fixed':43.,'nwc':150.48538383222-(NET+HAIRCUT+7.36682)-43.,
 'net_treasury':NET,'parent_fraction':.85,'parent_liquid':15.,'sub_liquid':10.67166431875,
 'parent_retained':FACTS['parent_retained'],'parent_paid':FACTS['paid_share_capital'],
 'parent_reserve':FACTS['parent_reserve'],'parent_premium':1.5,
 'finance_equity':FACTS['finance_equity_fy2025'],'finance_profit':.20508,'finance_exit':20,
 'finance_exit_fee':.03,'finance_sale_tax':.15,'parent_floor':20.,'sub_floor':10.,
 'total_liquidity':65.,'yield':.017,'payout':.70,'upstream':.70,'upstream_delay':1,
 'parent_profit_fraction':.80,'sub_reserve_budget':.10,'sub_safety_buffer':1.,'credit_limit':15.,'borrow_rate':.06,
 'maturity_rate':.20,'margin_shift':0.,'shift_start':1,'funding_shock':0.,'exit_year':60,
 'buyback':True,'buyback_cash':5.-1.08337963314,'buyback_price':54.55,'cash_shock':0.,
 'exit_fixed_recovery':.45,'exit_nwc_recovery':1.,'exit_cost':8.,'exit_tax':.15,'escrow_spread':0.,'early_extra':4.,'all_sub_upstream_stop_until':0,'all_sub_upstream_scale':1.}

def legal_profit(retained, reserve, paid, profit):
    eligible=max(0.,min(profit,retained+profit))
    appropriation=min(.1*eligible,max(0.,.5*paid-reserve))
    return retained+profit-appropriation,reserve+appropriation,appropriation

def settle(cash, debt, need, limit):
    """Only executed borrowing is cash; unfunded deficit stays outstanding."""
    borrowed=min(max(0.,need-cash),max(0.,limit-debt))
    cash+=borrowed;debt+=borrowed
    if cash<0:return 0.,debt,borrowed,need-cash
    paid=min(max(0.,cash),need);cash-=paid
    return cash,debt,borrowed,need-paid

def liquidation(cash, fixed, nwc, debt, costs, recovery=.45, tax=.15):
    proceeds=fixed*recovery
    disposal_tax=max(0.,proceeds-fixed)*tax
    # Negative NWC means suppliers/rebates/contracts must be settled, not recovered.
    available=cash+proceeds+max(0.,nwc)-disposal_tax
    obligations=debt+costs+max(0.,-nwc)
    residual=max(0.,available-obligations);unpaid=max(0.,obligations-available)
    return {'proceeds':proceeds,'tax':disposal_tax,'obligations':obligations,'distribution':residual,
            'unpaid_claims':unpaid,'feasible':unpaid<1e-9}

def operating(t,p):
    g=([.01,.025,.025,.02,.02][t-1] if t<=5 else .015 if t<=10 else .01)
    m=([.115,.12,.123,.125,.125][t-1] if t<=5 else .125-.001*min(t-5,15))
    nwc=-.40;cap=.27
    if p['name']=='cyclical':
        if t<=5:g=[-.10,-.03,.08,.05,.03][t-1];m=[.085,.095,.11,.12,.125][t-1]
        nwc=-.35 if t<=2 else -.40
    if p['name']=='structural':
        g=-.04 if t<=5 else -.015;m=max(.055,.10-.003*t);nwc=-.29;cap=.30
    if p['name']=='optimistic':
        g=[.04,.04,.04,.035,.03][t-1] if t<=5 else .025 if t<=10 else .015
        m=.13 if t<=5 else max(.115,.13-.001*(t-5));nwc=-.41
    if t>30 and p['name']!='structural':
        g=-.01;m=max(.08,m-.001*(t-30))
    if 'manual' in p:return p['manual']['growth'],p['manual']['margin'],p['manual'].get('nwc_ratio',0.),p['manual'].get('fixed_ratio',0.)
    return g,m+(p['margin_shift'] if t>=p['shift_start'] else 0.),nwc,cap

def run(overrides=None):
    p=copy.deepcopy(DEFAULT);p.update(overrides or {})
    shares=FACTS['shares'];paid=p['parent_paid'];premium=p['parent_premium'];ret=p['parent_retained'];reserve=p['parent_reserve']
    total=p['net_treasury'];parent_total=total*p['parent_fraction'];sub_total=total-parent_total
    pc=p['parent_liquid'];sc=p['sub_liquid'];pi=parent_total-pc;si=sub_total-sc
    # Parent/sub allocations are economic budget, not reported Q3 legal cash balances.
    opening_pi=pi;opening_si=si;rev=p['revenue'];fixed=p['fixed'];nwc=p['nwc'];debt=0.;bank=p['finance_equity'];bank_cost=bank
    bank_accumulated=0.;pending=0.;sub_loss=0.;sub_retained_budget=0.;sub_buffer=0.;rows=[];feasible=True;unpaid=0.;external=FACTS['external_debt'];escrow=external
    for t in range(1,p['years']+1):
        open_unpaid=unpaid
        open_pc,open_sc,open_pi,open_si,open_bank,open_debt,open_pending=pc,sc,pi,si,bank,debt,pending
        open_rev=rev;old_fixed=fixed;old_nwc=nwc
        g,margin,nr,fr=operating(t,p);rev*=1+g
        core=rev*margin
        if t==1:core-=p.get('initial_loss',0.)
        da=old_fixed*.11
        maintenance=old_fixed*.10
        growthcap=max(0.,fr*(rev-open_rev))
        capex=maintenance+growthcap
        fixed=old_fixed+capex-da
        # Keep productive assets adequate: replacement shortfall is capital spending.
        capex+=max(0.,fr*rev-fixed);fixed=max(fixed,fr*rev)
        nwc=nr*rev;delta_nwc=nwc-old_nwc
        capneed=capex-da+delta_nwc
        escrow_spread_income=external*p['escrow_spread']
        financial=(pc+sc+pi+si)*p['yield']+escrow_spread_income;interest=debt*p['borrow_rate']
        common_profit=core+financial-interest
        cf=common_profit-capneed
        parent_op=core*p['parent_profit_fraction'];sub_op=core-parent_op
        parent_fin=(pc+pi)*p['yield']+escrow_spread_income;sub_fin=financial-parent_fin
        parent_cf=parent_op+parent_fin-interest-capneed*p['parent_fraction']
        sub_cf=sub_op+sub_fin-capneed*(1-p['parent_fraction'])
        matured_p=min(pi,max(0.,opening_pi*p['maturity_rate']));matured_s=min(si,max(0.,opening_si*p['maturity_rate']))
        pc+=matured_p+parent_cf+pending;pi-=matured_p
        sc+=matured_s+sub_cf;si-=matured_s;received=pending;pending=0.
        sub_support=min(max(0.,pc),max(0.,-sc));pc-=sub_support;sc+=sub_support
        if sc<0:unpaid-=sc;sc=0.
        # Finance company: capital and customer funds are not free parent cash.
        bank_profit=0.;bank_div=0.;bank_sale=0.;bank_gain=0.;bank_fee=0.;bank_tax=0.
        if bank>0:
            bank_profit=p['finance_profit']*(1.01**(t-1));bank+=bank_profit;bank_accumulated+=bank_profit
            bank_div=max(0.,bank_profit*.7);bank-=bank_div;bank_accumulated-=bank_div
            if t==p['finance_exit'] or t==p['exit_year']:
                bank_fee=bank*p['finance_exit_fee'];bank_gain=max(0.,bank-bank_fee-bank_cost);bank_tax=bank_gain*p['finance_sale_tax']
                bank_sale=max(0.,bank-bank_fee-bank_tax);bank=0.
            # Sale requires regulatory permission and settled deposits/claims; capital return is not dividend profit.
        pc+=bank_div+bank_sale
        parent_profit=parent_op+parent_fin-interest+bank_div+bank_gain-bank_tax
        employee_charge=(.3*(FACTS['already_cost']+p['buyback_cash']) if t==1 and p['buyback'] else 0.)
        parent_profit-=employee_charge # noncash compensation; fully diluted shares already include employee rights
        ret,reserve,legal_reserve=legal_profit(ret,reserve,paid,parent_profit)
        # Subsidiaries only remit positive cash backed by this year's profit after accumulated modeled losses.
        subprofit=sub_op+sub_fin
        eligible=max(0.,min(subprofit,sub_loss+subprofit));sub_loss=min(0.,sub_loss+subprofit)
        sub_reserved=min(eligible*p['sub_reserve_budget'],max(0.,p['sub_safety_buffer']-sub_buffer))
        sub_buffer+=sub_reserved
        sub_retained_budget+=subprofit-sub_reserved
        normal_up=max(0.,eligible-sub_reserved)*p['upstream']
        extra_up=max(0.,sub_retained_budget-normal_up)*(.25 if t>=10 else 0.)
        upstream_gate=0. if t<=p['all_sub_upstream_stop_until'] else p['all_sub_upstream_scale']
        declared=min(max(0.,sc-p['sub_floor']),max(0.,sub_retained_budget),(normal_up+extra_up)*upstream_gate)
        sub_retained_budget-=declared
        sc-=declared
        ret+=declared # Parent investment income on declaration; collection next year is not profit twice.
        if p['upstream_delay']:
            pending+=declared
        else:pc+=declared;received+=declared
        buy=0.;cancel_shares=0.;cancel_retained=0.
        if t==1 and p['buyback']:
            buy=p['buyback_cash'];cancel_shares=.7*(FACTS['already_bought']+buy/p['buyback_price'])
            cost=.7*(FACTS['already_cost']+buy);par=cancel_shares
            premium_used=min(premium,max(0.,cost-par));premium-=premium_used
            cancel_retained=max(0.,cost-par-premium_used);ret-=cancel_retained;paid-=par;shares-=cancel_shares
            # All non-cancelled shares treated as fully diluted employee entitlements; no imaginary issue proceeds.
        shock=(p['cash_shock'] if t==1 else 0.)+(p['funding_shock'] if t==p.get('funding_shock_year',3) else 0.)
        pc,debt,borrowing,miss=settle(pc,debt,buy+shock,p['credit_limit']);unpaid+=miss
        # incremental debt repaid from available liquidity before dividends.
        repay=min(debt,max(0.,pc-p['parent_floor']));pc-=repay;debt-=repay
        liquid_excess=max(0.,pc-p['parent_floor'])
        required_liquidity=p['total_liquidity']*rev/p['revenue']
        economic_excess=max(0.,pc+sc+pi+si+pending-required_liquidity)
        ordinary=max(0.,common_profit+bank_profit)*p['payout']
        # Release surplus principal at a measured pace; no everlasting idle-capital prison.
        release=(p['early_extra'] if t<=10 else max(0.,economic_excess)/max(1,21-t)) if t<=20 else economic_excess
        requested=ordinary+release
        # A missed obligation invalidates the going-concern contract immediately.
        funding_unpaid_before_exit=unpaid
        feasible=feasible and unpaid<1e-8
        dist=min(requested,max(0.,ret),liquid_excess,economic_excess) if feasible else 0.
        pc-=dist;ret-=dist
        escrow_payment=min(external,FACTS['external_debt']/5.) if t<=5 else 0.
        escrow-=escrow_payment;external-=escrow_payment
        exit_info=None
        if p['exit_year']==t:
            # Maturity/capital disposal modeled at exit; unsettled subsidiary claims remain real.
            exit_info=liquidation(pc+sc+pi+si+pending+bank,fixed,nwc,debt+unpaid,p['exit_cost'],p['exit_fixed_recovery'],p['exit_tax'])
            if not exit_info['feasible'] and dist>0:
                # Same-period proposed dividend cannot leapfrog known exit creditors.
                pc+=dist;ret+=dist;dist=0.
                exit_info=liquidation(pc+sc+pi+si+pending+bank,fixed,nwc,debt+unpaid,p['exit_cost'],p['exit_fixed_recovery'],p['exit_tax'])
            # Legal reduction/liquidation allows return of contributed capital after all claims, not profit-only distribution.
            withheld=exit_info['distribution'] if not feasible else 0.
            if withheld:
                exit_info['withheld_equity_residual']=withheld
                exit_info['distribution']=0. # Funding-default path has no assumed restructuring permission.
            dist+=exit_info['distribution'];unpaid=exit_info['unpaid_claims'];pc=withheld;sc=pi=si=pending=bank=0.;debt=0. # remaining total claims are preserved in unpaid, not double-counted as debt
        feasible=feasible and unpaid<1e-8
        if exit_info is not None and feasible:
            before_exit_net=open_pc+open_sc+open_pi+open_si+open_pending+open_bank-open_debt-open_unpaid+cf+bank_profit-bank_fee-bank_tax-buy-shock
            assert abs(before_exit_net+exit_info['proceeds']+nwc-p['exit_cost']-exit_info['tax']-dist)<1e-7
        if exit_info is None:
            # Common cash+financial assets including accrued upstream claim.
            lhs=pc+sc+pi+si+pending+bank-debt-unpaid
            rhs=open_pc+open_sc+open_pi+open_si+open_pending+open_bank-open_debt-open_unpaid+cf+bank_profit-bank_fee-bank_tax-buy-shock-dist
            assert abs(lhs-rhs)<1e-7,(t,lhs,rhs)
        assert abs(escrow-external)<1e-8
        rows.append({'year':t,'calendar_label':2026+t,'revenue':rev,'growth':g,'net_operating_margin':margin,'common_operating_profit':core,
          'financial_income_ex_financeco':financial,'financing_interest':interest,'financeco_profit':bank_profit,'profit_total':common_profit+bank_profit,
          'depreciation':da,'maintenance':maintenance,'growth_capex':growthcap,'capex':capex,'fixed_end':fixed,'nwc_end':nwc,'delta_nwc':delta_nwc,
          'capital_need':capneed,'common_fcf':cf+bank_profit,'parent_profit_before_upstream':parent_profit,'new_employee_share_compensation':employee_charge,'sub_economic_profit':subprofit,
          'sub_prior_loss_end':sub_loss,'sub_retained_economic_budget_end':sub_retained_budget,'sub_buffer_end':sub_buffer,'sub_reserve_economic_budget':sub_reserved,'upstream_declared':declared,'upstream_received':received,'pending_end':pending,
          'parent_retained_end':ret,'parent_statutory_reserve_end':reserve,'legal_reserve_added':legal_reserve,'parent_paid_capital_end':paid,
          'parent_cash_end':pc,'sub_cash_end':sc,'parent_investments_end':pi,'sub_investments_end':si,'parent_maturities':matured_p,'sub_maturities':matured_s,
          'financeco_equity_end':bank,'financeco_dividend':bank_div,'financeco_principal_and_gain_recovered':bank_sale,'financeco_exit_fee':bank_fee,'financeco_exit_tax':bank_tax,
          'internal_sub_support_actually_paid':sub_support,'borrowed_received':borrowing,'debt_repaid':repay,'incremental_debt_end':debt,'unpaid_claims':unpaid,'funding_shock_paid':shock-miss,
          'buyback_cash':buy,'cancelled_shares':cancel_shares,'cancellation_retained_charge':cancel_retained,'shares_end':shares,
          'external_escrow_assets_end':escrow,'external_escrow_debt_end':external,'external_debt_net_paid':escrow_payment,'external_gross_principal_paid':external+escrow_payment,'external_refinancing_received':external,'escrow_net_spread_income':escrow_spread_income,
          'required_economic_liquidity':required_liquidity,'ordinary_budget':ordinary,'extra_release_budget':release,'requested_distribution':requested,'distribution':dist,'dps':dist/shares,'exit':exit_info,'feasible':feasible})
        if not feasible:
            rows[-1]['funding_unpaid_before_exit']=funding_unpaid_before_exit
            break # Preserve the failed ledger; no unapproved refinancing/restructuring or later dividends.
        if exit_info:break
    r=p['r'];gg=p['g_terminal']
    # Forward steady operation includes necessary liquidity income; no second principal addition.
    last=rows[-1]
    steady_rev=rev*(1+gg);steady_core=steady_rev*last['net_operating_margin']
    steady_required=p['total_liquidity']*rev/p['revenue']
    steady_capital=(fixed+nwc+steady_required)*gg
    steady_income=steady_required*p['yield']
    steady_fcfe=steady_core+steady_income-steady_capital
    # Distribute all mature recurring cash after retained-earnings constraint. Parent/core + regular upstream supports this budget.
    terminal=0. if p['exit_year'] else max(0.,steady_fcfe)/(r-gg)
    # Cash above required liquidity remains a common asset, only once at end; debt always deducted.
    surplus=max(0.,pc+sc+pi+si+pending-steady_required)
    # Parent reduced paid capital is the only known residual non-profit return budget.
    # Excess above that remains earning capital, not presumed immediately distributable.
    capital_return=min(surplus,max(0.,paid))*.97/(1+r)
    permanent_extra=max(0.,surplus-max(0.,paid))
    # Remaining non-distributable capital supports operating liquidity and earns yield;
    # its release is tested under the whole-business orderly exit scenario, not invented legal pools.
    surplus=capital_return+permanent_extra*p['yield']/(r-gg)
    finance_residual=(p['finance_profit']*(1.01**p['years'])/(r-.01) if bank>0 else 0.)
    residual_assets=surplus+finance_residual-debt if not p['exit_year'] else 0.
    terminal+=residual_assets
    value=sum(x['dps']/(1+r)**x['year'] for x in rows)+terminal/shares/(1+r)**len(rows)
    year5=sum(x['dps']/(1+r)**(x['year']-5) for x in rows if x['year']>5)+terminal/shares/(1+r)**(len(rows)-5)
    result={'parameters':p,'opening_bridge':{'gross':GROSS,'recoverability_budget':HAIRCUT,'net_treasury':total,'financeco_capital_separate':p['finance_equity'],'external_debt_reserved':FACTS['external_debt'],'nci_removed':FACTS['nci'],'opening_net_operating_liabilities':p['nwc'],'opening_fixed':p['fixed'],'common_equity_after_recovery_loss':total+p['finance_equity']+p['fixed']+p['nwc']},
      'annual':rows,'value_per_share':value,'year5_terminal_per_share':year5,'first5_dps':[x['dps'] for x in rows[:5]],
      'terminal_value':terminal,'terminal_pv_share':terminal/shares/(1+r)**len(rows)/value if value else 0.,'steady_fcfe':steady_fcfe,'residual_assets_at_terminal':residual_assets,'feasible':feasible}
    if not feasible:
        # Received distributions are historical cash, NOT a valuation of unresolved equity.
        result.update(value_per_share=None,year5_terminal_per_share=None,terminal_value=None,
                      terminal_pv_share=None,residual_assets_at_terminal=None,
                      failure_year=rows[-1]['year'],failure_unpaid_claims=unpaid,
                      distributions_received_before_failure=[{'year':x['year'],'dps':x['dps']} for x in rows if x['year']<rows[-1]['year']],
                      received_distributions_pv_per_share=sum(x['dps']/(1+r)**x['year'] for x in rows if x['year']<rows[-1]['year']))
    return result

def cases():
    s={'base':{},'core_low':{'r':.10,'margin_shift':-.005,'years':50,'exit_year':50},'core_high':{'r':.09,'margin_shift':.005,'years':70,'exit_year':70},
       'cyclical':{'name':'cyclical'},'structural':{'name':'structural','exit_year':30,'cash_shock':6.,'total_liquidity':75.,'payout':.50,'upstream':.50},
       'optimistic':{'name':'optimistic'},'cash_delay':{'maturity_rate':.10,'upstream':.40,'funding_shock':12.,'funding_shock_year':3},
       'finance_keep':{'finance_exit':60},'buyback_max':{'buyback_cash':10.-FACTS['already_cost']},
       'margin_from_6':{'margin_shift':-.01,'shift_start':6},'margin_from_11':{'margin_shift':-.01,'shift_start':11},
       'yield_low':{'yield':.01},'funding_spread':{'escrow_spread':-.01},'all_sub_upstream_stop_10':{'all_sub_upstream_stop_until':10},'all_sub_upstream_40pct':{'all_sub_upstream_scale':.4},'liquidity_95':{'total_liquidity':95.},'no_early_extra':{'early_extra':0.},'life_40':{'years':40,'exit_year':40},'life_80':{'years':80,'exit_year':80},'liquidity_high':{'total_liquidity':80.,'parent_floor':25.,'sub_floor':15.}}
    return {k:run(v) for k,v in s.items()}

def tests():
    assert legal_profit(-5.,0.,10.,3.)==(-2.,0.,0.)
    assert legal_profit(-5.,0.,10.,8.)==(2.7,.30000000000000004,.30000000000000004)
    a=settle(2.,0.,9.,4.);assert a==(0.,4.,4.,3.)
    e=liquidation(3.,10.,-8.,5.,2.,.5,.15);assert e['distribution']==0 and e['unpaid_claims']==7 and not e['feasible']
    e=liquidation(20.,10.,-8.,5.,2.,.5,.15);assert e['distribution']==10 and e['unpaid_claims']==0
    # Real production run: negative profits reduce parent legal retained, funded cash not invented.
    neg=run({'initial_loss':200.,'credit_limit':0.,'buyback':False,'years':1})
    assert neg['annual'][0]['parent_retained_end']<0 and neg['annual'][0]['distribution']==0
    catastrophic=run({'initial_loss':1000.,'credit_limit':0.,'buyback':False,'years':1,'exit_year':1})
    assert not catastrophic['feasible'] and catastrophic['annual'][0]['unpaid_claims']>0
    no_exit=run({'initial_loss':1000.,'credit_limit':0.,'buyback':False,'years':5,'exit_year':None})
    late_failure=run({'funding_shock':1000.,'funding_shock_year':3,'credit_limit':0.,'buyback':False,'years':8,'exit_year':None})
    exit_only=run({'exit_cost':1000.,'years':1,'exit_year':1,'buyback':False})
    for failed in (catastrophic,no_exit,late_failure,exit_only):
        assert not failed['feasible']
        assert all(failed[k] is None for k in ('value_per_share','year5_terminal_per_share','terminal_value','terminal_pv_share','residual_assets_at_terminal'))
        assert failed['annual'][-1]['unpaid_claims']>0
        assert len(failed['annual'])==failed['failure_year']
    assert exit_only['annual'][-1]['distribution']==0
    assert no_exit['annual'][-1]['distribution']==0
    assert late_failure['failure_year']==3 and late_failure['annual'][-1]['distribution']==0
    assert len(late_failure['distributions_received_before_failure'])==2
    assert late_failure['received_distributions_pv_per_share']>0
    blocked=run({'all_sub_upstream_stop_until':10})
    assert all(x['upstream_declared']==0 for x in blocked['annual'][:10])
    assert blocked['annual'][10]['upstream_declared']>0
    persistent=run({'all_sub_upstream_scale':.4})
    x=persistent['annual'][19]
    ordinary_up=(x['sub_economic_profit']-x['sub_reserve_economic_budget'])*.7
    retained_before=x['sub_retained_economic_budget_end']+x['upstream_declared']
    accumulated_up=max(0.,retained_before-ordinary_up)*.25
    expected=min(x['sub_cash_end']+x['upstream_declared']-10.,retained_before,(ordinary_up+accumulated_up)*.4)
    assert abs(x['upstream_declared']-expected)<1e-10
    base=run();late=run({'margin_shift':-.01,'shift_start':6})
    assert base['first5_dps']==late['first5_dps'] and late['value_per_share']<base['value_per_share']
    # Same production chain simple one-year flat firm: 10 profit; no capital need, no yield, payout100%.
    simple=run({'years':1,'exit_year':None,'manual':{'growth':0.,'margin':.1},'revenue':100.,'fixed':0.,'nwc':0.,'net_treasury':0.,'parent_fraction':1.,'parent_liquid':0.,'sub_liquid':0.,'finance_equity':0.,'finance_profit':0.,'parent_profit_fraction':1.,'yield':0.,'buyback':False,'parent_floor':0.,'sub_floor':0.,'total_liquidity':0.,'payout':1.,'r':.1,'g_terminal':0.})
    assert abs(simple['annual'][0]['distribution']-10.)<1e-10
    assert abs(simple['value_per_share']-100./FACTS['shares'])<1e-10
    return {'failed_full_run_pv_tv_null_and_no_postdefault_dividends':'pass','legal_loss_tests':'pass','financing_shortfall':'pass','exit_shortfall_and_capital_return':'pass','production_negative_profit':'pass','future_effective_year':'pass','all_sub_upstream_gate_including_accumulated_release':'pass','production_literal_flat_company':'pass'}

def secondary():
    shares=FACTS['shares']-.7*(FACTS['already_bought']+DEFAULT['buyback_cash']/FACTS['buyback_cap'])
    extra=NET-65.;adjustment=-64.-DEFAULT['nwc'];values=[]
    for r,core in [(.10,19.),(.09,21.)]:
        operating=(core+65.*.017-(43.-64.+65.)*.01)/(r-.01)
        recovery=sum((extra/10.+extra*(11-t)/10.*.017)/(1+r)**t for t in range(1,11))
        finance=sum(.20508*1.01**(t-1)/(1+r)**t for t in range(1,21))+7.36682*.97/(1+r)**20
        result=(operating+recovery+finance-(DEFAULT['buyback_cash']+adjustment)/(1+r))/shares
        values.append({'r':r,'operating_profit':core,'operating_value':operating,'excess_financial_recovery_pv':recovery,'financeco_value':finance,'opening_settlement':adjustment,'per_share':result})
    return values

def output():
    allcases=cases();test=tests()
    summary={k:{a:v[a] for a in ['value_per_share','year5_terminal_per_share','first5_dps','terminal_pv_share','feasible']} for k,v in allcases.items()}
    raw=json.dumps({'facts':FACTS,'scenarios':allcases},ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    return {'company':'CN:000651','period':'2026-Q3','as_of':ASOF,'units':'CNY billion; shares billion; per share CNY','summary':summary,'secondary_valuation':secondary(),'tests':test,
      'full_paths':{'encoding':'gzip+base64','decoded_sha256':hashlib.sha256(raw).hexdigest(),'data':base64.b64encode(gzip.compress(raw,mtime=0)).decode()}}
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--output');ap.add_argument('--expand');a=ap.parse_args();o=output()
    data=json.dumps(o,ensure_ascii=False,sort_keys=True,indent=2)+'\n'
    if a.output:Path(a.output).write_text(data,encoding='utf-8')
    else:print(data,end='')
    if a.expand:Path(a.expand).write_bytes(gzip.decompress(base64.b64decode(o['full_paths']['data'])))
