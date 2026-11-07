"""当前资本现金与权益计算核；经营输入由同次实际计算生成。"""
import copy
from common import EconomicRefusal

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

def bridge(saved, facts, event=None, checkpoint=None):
    """Replays only cash/capital steps. No operating() function exists in this module."""
    checkpoint=checkpoint or (lambda state:None)
    input_parameters=copy.deepcopy(saved['parameters'])
    p=copy.deepcopy(input_parameters); FACTS=copy.deepcopy(facts)
    checkpoint({'phase':'input','parameters':input_parameters,'facts':facts,'event':event})
    GROSS=saved['opening_bridge']['gross']; HAIRCUT=saved['opening_bridge']['recoverability_budget']
    event=event or {}; post_cutoff_cash=event.get('post_cutoff_cash',0.)
    if event:
        total_plan=FACTS['already_cost']+p['buyback_cash']
        p['buyback_cash']=total_plan-event['cumulative_cost']
        if p['buyback_cash']<0: raise EconomicRefusal('actual_buyback_exceeds_selected_plan',{'failure_row':{'year':0,'total_plan':total_plan,'actual_paid':event['cumulative_cost'],'event':event},'rows_before_failure':[]})
        FACTS['already_cost']=event['cumulative_cost']; FACTS['already_bought']=event['cumulative_shares']
        p['buyback_price']=event.get('future_price',p['buyback_price'])
        if p['buyback_price']<=0: raise ValueError('future price must be positive')
    shares=FACTS['shares'];paid=p['parent_paid'];premium=p['parent_premium'];ret=p['parent_retained'];reserve=p['parent_reserve']
    total=p['net_treasury'];parent_total=total*p['parent_fraction'];sub_total=total-parent_total
    pc=p['parent_liquid'];sc=p['sub_liquid'];pi=parent_total-pc;si=sub_total-sc
    # Parent/sub allocations are economic budget, not reported Q3 legal cash balances.
    opening_pi=pi;opening_si=si
    # October paid from parent's existing cash; no cancellation has yet occurred.
    pc-=post_cutoff_cash; total-=post_cutoff_cash
    if pc<0: raise EconomicRefusal('opening_parent_cash_insufficient_for_known_payment',{'failure_row':{'year':0,'cash':pc,'unpaid_obligation':-pc,'parent_investments':pi,'sub_cash':sc,'sub_investments':si,'debt':0.,'event':event},'rows_before_failure':[]})
    opening_parameters={**copy.deepcopy(p),'net_treasury':total,'parent_liquid':pc}
    rev=p['revenue'];fixed=p['fixed'];nwc=p['nwc'];debt=0.;bank=p['finance_equity'];bank_cost=bank
    bank_accumulated=0.;pending=0.;sub_loss=0.;sub_retained_budget=0.;sub_buffer=0.;rows=[];feasible=True;unpaid=0.;external=FACTS['external_debt'];escrow=external
    opening_state={'parent_cash':pc,'sub_cash':sc,'parent_investments':pi,'sub_investments':si,'debt':debt,'bank':bank,'retained':ret,'reserve':reserve,'paid_capital':paid,'premium':premium,'shares':shares}
    for t in range(1,p['years']+1):
        checkpoint({'phase':'year_open','year':t,'cash':pc,'sub_cash':sc,'parent_investments':pi,'sub_investments':si,'bank':bank,'debt':debt,'unpaid':unpaid,'pending':pending,'paid_capital':paid,'premium':premium,'retained':ret,'reserve':reserve,'completed_rows':len(rows)})
        open_unpaid=unpaid
        open_pc,open_sc,open_pi,open_si,open_bank,open_debt,open_pending=pc,sc,pi,si,bank,debt,pending
        frozen=saved['annual'][t-1]
        if frozen['year']!=t: raise ValueError('noncontiguous saved operating path')
        rev=frozen['revenue'];g=frozen['growth'];margin=frozen['net_operating_margin']
        core=frozen['common_operating_profit'];da=frozen['depreciation'];maintenance=frozen['maintenance']
        growthcap=frozen['growth_capex'];capex=frozen['capex'];fixed=frozen['fixed_end']
        nwc=frozen['nwc_end'];delta_nwc=frozen['delta_nwc'];capneed=frozen['capital_need']
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
            bank_profit=frozen['financeco_profit'];bank+=bank_profit;bank_accumulated+=bank_profit
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
        checkpoint({'phase':'year_close','year':t,'row':rows[-1],'premium':premium})
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
    result['input_parameters']=input_parameters
    result['opening_parameters']=opening_parameters
    result['source_event']=copy.deepcopy(event)
    result['opening_state']=opening_state
    result['recurrence_allocation_parameters']=copy.deepcopy(p)
    if event:result['parameters']=copy.deepcopy(opening_parameters)
    result['parameters_role']='Opening effective post-event parameters. Historical allocation basis is separately retained in recurrence_allocation_parameters; exact cash/investment splits are in opening_state. This is not a new old-source input.'
    if not feasible:result['status']='ECONOMIC_REFUSAL'
    result['event_bridge']={'post_cutoff_cash':post_cutoff_cash,'factual_registered_shares':facts['shares'],
      'factual_completed_cancellation':0.,'remaining_future_cash':p['buyback_cash'],
      'future_price_assumption':p['buyback_price'],'purpose_cancel_fraction':.7,
      'employee_fully_diluted_fraction':.3,'parent_premium_end':premium}
    return result


def secondary(saved,facts,event=None):
    """Old independent normalisation; cash reallocated from future budget, not added twice."""
    p=saved['parameters'];event=event or {};spent=event.get('post_cutoff_cash',0.)
    already=event.get('cumulative_cost',facts['already_cost']);bought=event.get('cumulative_shares',facts['already_bought'])
    future=(facts['already_cost']+p['buyback_cash']-already) if event else p['buyback_cash']
    price=event.get('future_price',p['buyback_price'])
    if future<0:raise EconomicRefusal('actual_exceeds_auxiliary_selected_plan')
    shares=facts['shares']-.7*(bought+future/price)
    extra=p['net_treasury']-spent-65.;adjustment=-64.-p['nwc'];values=[]
    for r,core in [(.10,19.),(.09,21.)]:
        operating=(core+65.*.017-(43.-64.+65.)*.01)/(r-.01)
        recovery=sum((extra/10.+extra*(11-t)/10.*.017)/(1+r)**t for t in range(1,11))
        finance=sum(.20508*1.01**(t-1)/(1+r)**t for t in range(1,21))+7.36682*.97/(1+r)**20
        result=(operating+recovery+finance-(future+adjustment)/(1+r))/shares
        values.append({'r':r,'operating_profit':core,'operating_value':operating,
          'excess_financial_recovery_pv':recovery,'financeco_value':finance,'opening_settlement':adjustment,'per_share':result})
    return values
