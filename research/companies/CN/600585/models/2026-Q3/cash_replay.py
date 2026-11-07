#!/usr/bin/env python3
"""当前资本现金与权益计算核；经营输入由同次实际计算生成。"""
import sys

import json, math, copy
REGISTERED_SHARES=5277060044
OLD_SHARES=(REGISTERED_SHARES-36879800-17306500)/1e9
SHARES=(REGISTERED_SHARES-36879800-17556500)/1e9
REPURCHASE_HKD=4235600
HISTORICAL_FX_PROXY=.8686  # 2026 H1 report p202; NOT 2026-10-29 spot/settlement rate.
def repurchase_bridge(cash, enabled=True, fx=HISTORICAL_FX_PROXY, fee_rate=0., settled=False):
    cost=REPURCHASE_HKD*fx/1e9 if enabled else 0.
    fee=cost*fee_rate
    gross_cash=cash-(cost+fee if settled else 0.)
    payable=0. if settled else cost+fee
    result=dict(cash_before=cash,gross_cash_at_cutoff=gross_cash,settlement_payable=payable,
      available_cash_after_reservation=gross_cash-payable,treasury_stock_cost_add=cost,
      apic_change=-fee,registered_share_change=0,registered_shares=REGISTERED_SHARES,
      profit_change=0,tax_change=0,nci_change=0,retained_earnings_change=0,
      total_equity_change=-cost-fee,consideration_hkd=REPURCHASE_HKD if enabled else 0,
      fx_cny_per_hkd=fx,fx_is_historical_proxy=True,fee_rate_budget=fee_rate,
      cancelled_shares=0,treasury_h_shares_add=250000 if enabled else 0,
      shares_bn=SHARES if enabled else OLD_SHARES,holder_distribution=0)
    assert abs((gross_cash-cash)-payable-result['total_equity_change'])<1e-12
    return result
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
CASES['legacy_base']=dict(CASES['base'],repurchase=False,legacy_loss_payout=True)
CASES['corrected_no_repurchase']=dict(CASES['base'],repurchase=False)
CASES['fx_minus_10pct']=dict(CASES['base'],fx=.78174)
CASES['fx_plus_10pct']=dict(CASES['base'],fx=.95546)
CASES['fees_1pct_bound']=dict(CASES['base'],repurchase_fee=.01)
CASES['settled_at_cutoff']=dict(CASES['base'],settled=True)
def legal(up,res,cap,profit):
    # Negative UP must first be repaired; never cross-offset separate cohorts.
    after=up+profit
    provision=min(max(0,cap*.5-res),.10*max(0,after-max(0,up)))
    return after-provision,res+provision,provision

def unit(name,cash,debt,up,res,cap,owner,floor):
    return dict(name=name,cash=cash,debt=debt,up=up,res=res,cap=cap,owner=owner,floor=floor)

def cash_step(u,ebit,da,capex,dwc,external_income=0,repay=0,required=False,noncash_loss=0):
    opening=u['cash']; finance=opening*.015
    interest=u['debt']*.026
    pretax=ebit+finance-interest+external_income
    # No group tax consolidation. No unsupported tax-loss asset cash benefit.
    tax=.25*max(0,pretax); profit=pretax-tax-noncash_loss
    u['up'],u['res'],reserve=legal(u['up'],u['res'],u['cap'],profit)
    before=opening+profit+noncash_loss+da-capex-dwc
    maturity=u['debt']/3
    paid=min(repay,u['debt']) if required else min(repay,u['debt'],max(0,before-u['floor']))
    refinancing=max(0,maturity-paid)
    u['debt']-=paid; u['cash']=before-paid
    assert abs(u['cash']-(opening+profit+noncash_loss+da-capex-dwc-paid))<1e-8
    return dict(open_cash=opening,ebit=ebit,da=da,capex=capex,dwc=dwc,financial_income=finance,other_cash_income=external_income,interest=interest,tax=tax,profit=profit,noncash_disposal_loss=noncash_loss,reserve_add=reserve,debt_repaid=paid,scheduled_maturity=maturity,refinancing=refinancing,cash_before_distribution=u['cash'])

def distribute(u,desired):
    d=min(max(0,desired),max(0,u['up']),max(0,u['cash']-u['floor']))
    u['cash']-=d;u['up']-=d
    assert u['cash']>=u['floor']-1e-8 or d==0
    return d

def economics(*args, **kwargs):
    raise TechnicalFailure('Operating forecasts are frozen; this draft cannot recompute economics.')

def run(name,method='unit_economics',horizon=400,*,frozen_path=None,event_condition=None,diagnostic_sink=None,diagnostic_context=None):
    stage='admission';t=None;rows=[];current_iteration_completed=False
    try:
        if frozen_path is None:
            raise TechnicalFailure('A complete pinned frozen operating path is required')
        if (frozen_path['case'],frozen_path['method']) != (name,method):
            raise TechnicalFailure('Frozen path key mismatch')
        if event_condition is not None and name not in CURRENT_CASES:
            raise TechnicalFailure('Unselected historical diagnostic cannot become a current path')
        stage='initialize_accounts'
        scenario=CASES[name];c=CASES['base'] if scenario.get('conditional') else scenario;pc=c.get('parent_cash',60);p=unit('listed_parent',pc,10.6,141.970464865,2.64965129,5.277060044,1,4)
        w=unit('residual_profitable_budget_pool',c['finance']-pc-5.8,10.6,c.get('legal_opening',0),1.5,c.get('reserve_cap',6),c.get('residual_owner',.94),5)
        l=unit('residual_loss_budget_pool',2,0,-1.0,.1,1,.94,.8)
        y=unit('Yingde_75pct',2.5,.2,c.get('yingde_up',3.0),.1,.4,.75,.4)
        e=unit('Environmental_budget_pool',1.3,4.1,-.5,.2,1.2,.2121*c.get('env_lower',.69),.5)
        stage='reserve_old_and_new_transactions'
        bridge=repurchase_bridge(p['cash'],c.get('repurchase',True),c.get('fx',HISTORICAL_FX_PROXY),c.get('repurchase_fee',0.),c.get('settled',False))
        if event_condition is not None:
            bridge=append_new_event(bridge,event_condition)
        p['cash']=bridge['available_cash_after_reservation']; shares=bridge['shares_bn']
        us=[p,w,l,y,e]; loan=44.088345981;poolpay=17.164153814
        # Gross intercompany principal never creates group earnings or cash.
        portfolio=9.376410426-.03599034*(1-.2121*.69);initial_portfolio=portfolio;fund_calls=1.93;receivable=.041608258;pending=0;pending_by_sub=[0.0]*5
        cumulative_common_equity_change=bridge['total_equity_change']; cumulative_nci_equity_change=0.; cumulative_physical_asset_change=0.; cumulative_working_capital_change=0.
        rows=[]; stopped=None; support_loans=[0.0]*5;acquisition_cost=0.;checkpoint=None
        for t in range(1,horizon+1):
            if t==6 and scenario.get('conditional'): c=scenario  # SAME live accounts; no reinitialization
            current_iteration_completed=False
            op=None;st=[]
            stage='frozen_operations_and_opening_balances'
            op=frozen_operations(frozen_path,t);start_cash=sum(u['cash'] for u in us); start_debt=sum(u['debt'] for u in us)
            stage='settle_dividends_and_old_receivable'
            receipts=pending; p['cash']+=receipts;pending=0
            for i in range(1,5): us[i]['cash']-=pending_by_sub[i]
            pending_by_sub=[0.0]*5
            # Existing receivable collected once, never booked again as profit.
            rc=receivable if t==1 and c.get('old_dividend','internal')!='zero' else 0
            p['cash']+=rc;receivable-=rc
            rc_external=rc if c.get('old_dividend','internal')=='external' else 0
            if rc and not rc_external:w['cash']-=rc  # uncertain debtor: conservative internal transfer
            # Assets held through ordinary portfolio maturity/recycling, not immediate liquidation.
            stage='portfolio_and_pool_transfers'
            call=min(fund_calls,.5) if t<=4 else 0
            fund_calls-=call;portfolio+=call;p['cash']-=call
            sale=min(portfolio,(initial_portfolio+1.93)/10) if c.get('portfolio_start',6)<=t<c.get('portfolio_start',6)+10 else 0
            recovery=c.get('recovery',.85)
            portfolio-=sale;p['cash']+=sale*recovery
            # 15% haircut is recognized, coupon scales with outstanding principal.
            income=portfolio*c.get('portfolio_income',.025)
            disposal_loss=sale*(1-recovery)  # recognize once in earnings, add back in CFO; sale proceeds already booked
            payable=min(poolpay,17.164153814/5);poolpay-=payable
            p['cash']-=payable;w['cash']+=payable
            stage='entity_cash_steps'
            st=[];internal_interest=loan*.02
            for i,u in enumerate(us):
                dep=op['da']*[.02,.83,.05,.025,.075][i]
                cap=op['capex']*[.02,.83,.05,.025,.075][i]
                if i==4 and t==1:
                    acquisition_cost=c.get('acquisition',.307);cap+=acquisition_cost
                dwc=(.3 if t==1 else -.1 if t<=5 else 0)*[.01,.87,.04,.03,.05][i]
                st.append(cash_step(u,op['components'][i],dep,cap,dwc,income+internal_interest if i==0 else -internal_interest if i==1 else 0,u['debt']/3 if c.get('no_refinancing') else u['debt']/max(1,11-t) if t<=10 else u['debt'],c.get('no_refinancing',False),disposal_loss if i==0 else 0))
            # Acquisition earnings are excluded from base pending approvals/integration.
            # Wide boundary: 40m pretax incremental project earnings, taxed separately,
            # all environmental ownership raised to .99 (not merely new project).
            # Actual environmental legal reserves/cash/debt gate every distribution.
            stage='medical_boundary'
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
            stage='recover_internal_principal_and_fund_deficits'
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
            stage='support_recovery'
            support_recovery=0
            for i in (1,2,3,4):
                sr=min(support_loans[i],max(0,us[i]['cash']-us[i]['floor']))
                us[i]['cash']-=sr;p['cash']+=sr;support_loans[i]-=sr;support_recovery+=sr
                if i==2:p['up']+=sr  # reverse allowance only on actual recovery
            stage='subsidiary_dividend_declarations'
            d_sub=0;nci=0;declared=0
            for i,u in enumerate(us[1:],1):
                target=max(0,st[i]['profit'])+min(1,max(0,(t-5)/10))*.15*max(0,u['cash']-u['floor'])
                d=distribute(u,target)
                d_sub+=d;owned=d*u['owner'];nci+=d-owned;declared+=owned
                pending_by_sub[i]=.25*owned;u['cash']+=.25*owned
            # Declaration creates parent income; 25% actually received next year.
            stage='parent_receipts_and_legal_capacity'
            paid_now=.75*declared;p['cash']+=paid_now;pending=.25*declared
            p['up'],p['res'],reserve_on_div=legal(p['up'],p['res'],p['cap'],declared)
            st[0]['reserve_add']+=reserve_on_div
            # Common holder payout budget moves 45% to full distributable cash as
            # domestic expansion ends; excess opening liquidity returned gradually.
            stage='common_holder_distribution'
            ramp=min(1,max(0,(t-5)/(c['release']-5)))
            ownerprofit=st[0]['profit']+declared
            common_profit=st[0]['profit']+sum(st[i]['profit']*us[i]['owner'] for i in range(1,len(us)))
            payout_profit=common_profit+(disposal_loss if c.get('legacy_loss_payout') else 0.)
            desired=max(0,payout_profit)*(.45+.55*ramp)+ramp*.15*max(0,p['cash']-p['floor'])
            if t<=2 and c.get('floor_plan',True) and common_profit>0: desired=max(desired,.90*shares)
            d=distribute(p,desired)
            end_cash=sum(u['cash'] for u in us)
            # Consolidated cash conservation excludes internal payments, preserves
            # dividend transit receivable and actual minority distributions.
            stage='group_cash_and_equity_conservation'
            operating=sum(z['profit']+z['noncash_disposal_loss']+z['da']-z['capex']-z['dwc']-z['debt_repaid'] for z in st)
            expected=start_cash+rc_external+sale*recovery-call+operating-nci-d
            assert abs(end_cash-expected)<1e-7,(t,end_cash,expected)
            physical_change=sum(z['capex']-z['da'] for z in st)
            wc_change=sum(z['dwc'] for z in st)
            debt_change=sum(u['debt'] for u in us)-start_debt
            balance_sheet_equity_change=end_cash-start_cash+physical_change+wc_change+call-sale-rc_external-debt_change
            nci_profit=sum(st[i]['profit']*(1-us[i]['owner']) for i in range(1,5))
            common_equity_change=common_profit-d
            nci_equity_change=nci_profit-nci
            assert abs(balance_sheet_equity_change-common_equity_change-nci_equity_change)<1e-7
            cumulative_common_equity_change+=common_equity_change
            cumulative_nci_equity_change+=nci_equity_change
            cumulative_physical_asset_change+=physical_change
            cumulative_working_capital_change+=wc_change
            equity_ledger=dict(common_profit=common_profit,nci_profit=nci_profit,group_profit=sum(z['profit'] for z in st),
              common_equity_change=common_equity_change,nci_equity_change=nci_equity_change,
              balance_sheet_equity_change=balance_sheet_equity_change,cumulative_common_equity_change=cumulative_common_equity_change,
              cumulative_nci_equity_change=cumulative_nci_equity_change,cumulative_physical_asset_change=cumulative_physical_asset_change,
              cumulative_working_capital_change=cumulative_working_capital_change,registered_capital=REGISTERED_SHARES/1e9,
              treasury_stock_increment=bridge['treasury_stock_cost_add'],apic_change=bridge['apic_change'])
            stage='assemble_complete_row'
            row=dict(equity_ledger=equity_ledger,payout_profit=payout_profit,old_receivable=receivable,old_receivable_collection=rc,old_receivable_external_cash=rc_external,portfolio_cost_sold=sale,portfolio_cash_recovery=sale*recovery,portfolio_cash_income=income,portfolio_disposal_loss=sale*(1-recovery),acquisition_cost=acquisition_cost,new_medical_full_cash=medical_cash,new_medical_attributable_profit_before_payout=medical_common,year=t,method=method,case=name,operations=op,entities={u['name']:dict(**u,**st[i]) for i,u in enumerate(us)},loan=loan,internal_interest=internal_interest,pool_payable=poolpay,portfolio=portfolio,fund_call=call,common_attributable_profit=common_profit,parent_dividend_receivable=pending,declared_to_parent=declared,received_by_parent=paid_now+receipts,loan_recovery=lr,gross_pool_payment=payable,parent_support=support,support_loan_balances=list(support_loans),support_recovery=support_recovery,nci_cash_distribution=nci,common_distribution=d,distribution_per_share=d/shares,total_cash=end_cash,total_debt=sum(u['debt'] for u in us),total_reserve=sum(u['res'] for u in us),pv=discount_cash(d/shares,scenario['r'],t))
            rows.append(row)
            current_iteration_completed=True
            if t==5:
                checkpoint=copy.deepcopy(dict(entities=us,loan=loan,poolpay=poolpay,portfolio=portfolio,initial_portfolio=initial_portfolio,fund_calls=fund_calls,old_receivable=receivable,pending=pending,pending_by_sub=pending_by_sub,support_loans=support_loans,acquisition_cost=acquisition_cost))
        failure_iteration_stage=stage if stopped else None
        stage='final_path_valuation'
        pv=sum(r['pv'] for r in rows)
        tv5=sum(discount_cash(r['distribution_per_share'],scenario['r'],r['year']-5) for r in rows if r['year']>5)
        result=dict(case=name,method=method,year5_state=checkpoint,parameters=scenario,shared_base_first5=bool(scenario.get('conditional')),repurchase_bridge=bridge,shares_bn=shares,status='infeasible' if stopped else 'feasible',stop=stopped,value=pv if not stopped else None,partial_distributions_pv=pv,terminal_year5=tv5 if not stopped else None,first5=[r['distribution_per_share'] for r in rows[:5]],terminal_pv_fraction=(tv5/(1+scenario['r'])**5/pv if pv and not stopped else None),rows=rows)

        if diagnostic_sink is not None:
            diagnostic_sink(runtime_snapshot(locals(),'economic_infeasible' if stopped else 'completed'))
        return result
    except Exception as exc:
        payload=runtime_snapshot(locals(),'technical_failure',exc)
        raise PathTechnicalFailure(payload) from exc


# Event facts and explicit research conditions. This code is a static draft.
from fractions import Fraction
from pathlib import Path
import argparse, hashlib, os, sys, platform, traceback
CURRENT_REGISTERED_SHARES = 5277060044
CURRENT_A_TREASURY = 36879800  # Unchanged existing assumption, not newly confirmed.
CURRENT_H_TREASURY = 18026500
CURRENT_PARTICIPATING_SHARES = 5222153744
NEW_TRANSACTIONS = (
    {'trade_date': '2026-10-30', 'shares': 270000, 'hkd': 4598800, 'reference_fx': '0.85594', 'source_id': '1225648833'},
    {'trade_date': '2026-11-02', 'shares': 200000, 'hkd': 3437440, 'reference_fx': '0.85595', 'source_id': '1225653297'},
)
CONDITIONS = {
    'reference_no_fee': {'fx_multiplier': '1', 'fee_rate': '0'},
    'reference_fee_20bp': {'fx_multiplier': '1', 'fee_rate': '0.002'},
    'adverse_fx_50bp_fee_20bp': {'fx_multiplier': '1.005', 'fee_rate': '0.002'},
}
CURRENT_CASES = ('core_low', 'base', 'core_high', 'conditional_low_after_base5', 'conditional_high_after_base5')
METHODS = ('unit_economics', 'replacement_asset_budget')
OLD_GATE_CASES = CURRENT_CASES + ('persistent_demand_loss',)
RAW_SHA = '4bdf238153515395d1b36fd73457496f9f16f3f267c56626b91b935786ccec1b'
RAW_BYTES = 105803292

class TechnicalFailure(RuntimeError):
    """Missing inputs, identity/schema mismatch or failed exact replay, never economic failure."""


def event_cost_exact(condition):
    """Actual production function; exact CNY-bn price/fee reservation before float cash ledger."""
    c = CONDITIONS[condition]
    costs = [Fraction(t['hkd']) * Fraction(t['reference_fx']) * Fraction(c['fx_multiplier']) / 10**9 for t in NEW_TRANSACTIONS]
    fees = [v * Fraction(c['fee_rate']) for v in costs]
    return sum(costs, Fraction(0)), sum(fees, Fraction(0))


def append_new_event(old_bridge, condition, settled=False):
    """Append new obligation once, retaining the original October 29 bridge unchanged."""
    cost_q, fee_q = event_cost_exact(condition)
    cost, fee = float(cost_q), float(fee_q)
    reserved = cost + fee
    b = copy.deepcopy(old_bridge)
    b.update(
        gross_cash_at_cutoff=old_bridge['gross_cash_at_cutoff'] - (reserved if settled else 0.),
        settlement_payable=old_bridge['settlement_payable'] + (0. if settled else reserved),
        available_cash_after_reservation=old_bridge['available_cash_after_reservation'] - reserved,
        treasury_stock_cost_add=old_bridge['treasury_stock_cost_add'] + cost,
        apic_change=old_bridge['apic_change'] - fee,
        total_equity_change=old_bridge['total_equity_change'] - reserved,
        consideration_hkd=old_bridge['consideration_hkd'] + sum(t['hkd'] for t in NEW_TRANSACTIONS),
        treasury_h_shares_add=old_bridge['treasury_h_shares_add'] + sum(t['shares'] for t in NEW_TRANSACTIONS),
        shares_bn=CURRENT_PARTICIPATING_SHARES / 1e9,
        fx_cny_per_hkd=None,
        fx_is_historical_proxy=False,
        fee_rate_budget=None,
        fx_basis='Mixed: unchanged October 29 historical proxy; new date-specific reference assumptions, not actual settlement.',
        old_bridge_preserved=copy.deepcopy(old_bridge),
        incremental_event=dict(condition=condition, assumptions=copy.deepcopy(CONDITIONS[condition]),
            transactions=copy.deepcopy(NEW_TRANSACTIONS), condition_metadata=copy.deepcopy(CONDITION_METADATA[condition]),
            fx_evidence=FX_EVIDENCE_DESCRIPTION, cost_cny_bn=cost, fee_cny_bn=fee,
            cost_cny_bn_exact=str(cost_q), fee_cny_bn_exact=str(fee_q),
            settled_presentation=settled, actual_settlement_verified=False,
            participating_shares_before=5222623744, participating_shares_after=CURRENT_PARTICIPATING_SHARES,
            a_treasury_unchanged_is_assumption=True),
    )
    assert b['registered_shares'] == CURRENT_REGISTERED_SHARES
    assert b['cancelled_shares'] == b['registered_share_change'] == 0
    assert all(b[k] == 0 for k in ('profit_change', 'tax_change', 'nci_change', 'retained_earnings_change', 'holder_distribution'))
    assert abs(b['gross_cash_at_cutoff'] - b['settlement_payable'] - b['available_cash_after_reservation']) < 1e-12
    assert abs(b['available_cash_after_reservation'] - b['cash_before'] - b['total_equity_change']) < 1e-12
    return b


def frozen_operations(saved, year):
    """Read the complete saved operating row. No economic forecast regeneration or extrapolation."""
    rows = saved['rows']
    if year <= len(rows):
        if rows[year-1]['year'] != year:
            raise TechnicalFailure('Non-contiguous frozen operating rows')
        return copy.deepcopy(rows[year-1]['operations'])
    stop = saved.get('stop')
    if stop and stop.get('year') == year and 'operations' in stop:
        return copy.deepcopy(stop['operations'])
    raise TechnicalFailure('Missing frozen operation at year %s for %s/%s; no broad operating rerun allowed' % (year, saved['method'], saved['case']))


def discount_cash(distribution_per_share, rate, periods):
    return distribution_per_share / (1 + rate) ** periods












def holder_contract(paths, as_of):
    p = paths[('unit_economics', 'base')]
    lo = paths[('unit_economics', 'conditional_low_after_base5')]
    hi = paths[('unit_economics', 'conditional_high_after_base5')]
    if any(x['status'] != 'feasible' for x in (p,lo,hi)):
        return {'status':'economic_infeasible', 'return_model':None,
                'reason':'A complete current holder path is infeasible; no terminal value is fabricated.'}
    return {'schema_version':1, 'method':'annual_common_equity_irr_v1', 'currency':'CNY', 'model_as_of':as_of,
        'base_case_distributions_per_share':p['first5'],
        'base_case_terminal_equity_value_range_per_share':{'year_5':{'low':lo['terminal_year5'], 'high':hi['terminal_year5']}}}










PRIMARY_CONDITION = 'reference_no_fee'
CONDITION_METADATA = {
    'reference_no_fee': {'primary': True, 'label': '参考汇率下已披露对价、未计未知费用',
        'purpose': 'Disclosed consideration translated at saved official-domain historical-table reference rates; unknown fees excluded.'},
    'reference_fee_20bp': {'primary': False, 'label': '20bp费用诊断假设',
        'purpose': 'Analyst diagnostic only. No tariff or execution evidence supports this precise magnitude.'},
    'adverse_fx_50bp_fee_20bp': {'primary': False, 'label': '50bp汇率和20bp费用诊断假设',
        'purpose': 'Analyst diagnostic only. Actual cost may fall outside all listed conditions.'},
}
FX_EVIDENCE_DESCRIPTION = ('Saved search response from the official-domain historical table, with dated HKD/CNY rows; '
    'the dated announcement opens failed. This is not independent full-text verification of either dated FX announcement '
    'and does not establish actual settlement.')




class PathTechnicalFailure(TechnicalFailure):
    def __init__(self, payload):
        self.payload = payload
        super().__init__('A technical path failure occurred; complete available runtime state is attached.')


class ExactReplayMismatch(TechnicalFailure):
    def __init__(self, payload):
        self.payload = payload
        super().__init__('Exact replay mismatch at ' + payload['first_difference']['pointer'])


def typed_diagnostic(value, active=None):
    """Preserve unsupported JSON values explicitly; never silently replace them with null or drop them."""
    if value is None or isinstance(value,(str,bool,int)):
        return value
    if isinstance(value,float):
        return value if math.isfinite(value) else {'diagnostic_type':'nonfinite_float','representation':repr(value)}
    if isinstance(value,Fraction):
        return {'diagnostic_type':'Fraction','numerator':value.numerator,'denominator':value.denominator}
    if isinstance(value,Path):
        return {'diagnostic_type':'Path','value':str(value)}
    active=set() if active is None else active
    if id(value) in active:
        return {'diagnostic_type':'cyclic_reference','python_type':type(value).__qualname__}
    active.add(id(value))
    try:
        if isinstance(value,dict):
            if all(isinstance(k,str) for k in value):
                return {k:typed_diagnostic(v,active) for k,v in value.items()}
            return {'diagnostic_type':'non_string_key_mapping','items':[[typed_diagnostic(k,active),typed_diagnostic(v,active)] for k,v in value.items()]}
        if isinstance(value,list): return [typed_diagnostic(v,active) for v in value]
        if isinstance(value,tuple): return {'diagnostic_type':'tuple','items':[typed_diagnostic(v,active) for v in value]}
        return {'diagnostic_type':'unsupported_json_value','python_type':type(value).__module__+'.'+type(value).__qualname__,
                'representation':repr(value),'lossless_object_reconstruction_claimed':False}
    finally:
        active.remove(id(value))


def runtime_snapshot(frame, outcome, exception=None):
    keys=('name','method','horizon','event_condition','scenario','c','pc','t','stage','current_iteration_completed',
        'failure_iteration_stage','i','u','dep','cap','dwc','medical_cash','medical_common','op','st','p','w','l','y','e','us','bridge','shares','loan','poolpay','portfolio','initial_portfolio',
        'fund_calls','receivable','pending','pending_by_sub','support_loans','acquisition_cost',
        'cumulative_common_equity_change','cumulative_nci_equity_change','cumulative_physical_asset_change',
        'cumulative_working_capital_change','checkpoint','stopped','start_cash','start_debt',
        'receipts','rc','rc_external','call','sale','recovery','income','disposal_loss','payable','internal_interest',
        'lr','support','support_recovery','declared','paid_now','nci','d','end_cash','operating','expected',
        'physical_change','wc_change','debt_change','balance_sheet_equity_change','common_profit',
        'common_equity_change','nci_profit','nci_equity_change','equity_ledger','pv','tv5')
    present={k:frame[k] for k in keys if k in frame}
    missing=[k for k in keys if k not in frame]
    rows=frame.get('rows',[])
    frozen=frame.get('frozen_path')
    payload={'schema':'conch_runtime_snapshot_v2','outcome':outcome,
        'runtime_state':present,'not_yet_initialized_fields':missing,
        'completed_rows':rows,'complete_result_if_available':frame.get('result'),
        'last_completed_year':rows[-1]['year'] if rows else None,
        'current_iteration_is_completed':frame.get('current_iteration_completed',False),
        'current_iteration_row':frame.get('row') if frame.get('current_iteration_completed',False) else None,
        'frozen_input_reference':frame.get('diagnostic_context'),
        'frozen_parameters':frozen.get('parameters') if isinstance(frozen,dict) else None,
        'current_condition_assumptions':CONDITIONS.get(frame.get('event_condition')),
        'current_condition_metadata':CONDITION_METADATA.get(frame.get('event_condition')),
        'python_flags':str(sys.flags),'optimize':sys.flags.optimize}
    if exception is not None:
        frames=[];tb=exception.__traceback__
        while tb is not None:
            # Preserve the failing production helper's local values as well as run's outer state.
            if tb.tb_frame.f_code.co_name in ('cash_step','legal','distribute','repurchase_bridge','append_new_event','frozen_operations'):
                frames.append({'function':tb.tb_frame.f_code.co_name,'line':tb.tb_lineno,'locals':dict(tb.tb_frame.f_locals)})
            tb=tb.tb_next
        payload['exception']={'type':type(exception).__module__+'.'+type(exception).__qualname__,
            'message':str(exception),'traceback':traceback.format_exc(),'production_helper_frames':frames}
    return payload













PORTABLE_INPUT_MANIFEST_SHA = 'facee8a6c7ae37a428c2734f3ce23986010330746a59a42d5bd39434f1b3f55c'
