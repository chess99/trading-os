"""600900 independent model. Units: CNY billion, kWh billion, shares billion.
Python standard library only. No network, old-model imports or hidden paths.
Cash construction budgets exclude financing interest; interest paid once below FCFF.
"""
import copy, gzip, json, math, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

def pv(cash, rate, offset=0):
    if not isinstance(cash, (list, tuple)) or not cash or not math.isfinite(rate) or rate < 0:
        raise ValueError('finite nonempty cash and nonnegative discount rate required')
    if any(not math.isfinite(x) for x in cash): raise ValueError('nonfinite cash')
    return sum(x/(1+rate)**(i+1+offset) for i,x in enumerate(cash))

def legal_payment(requested, opening_retained, legal_profit, opening_cash, cash_before_payment, min_cash, debt_capacity):
    """Separate legal distributable capacity from signed retained earnings.

    A cash floor is an operating-budget requirement, not by itself a legal default.
    If it cannot be funded within the credit limit, ending_cash is only the
    conditional cash arithmetic (possibly negative), never a feasible bank balance.
    The caller must stop the normal funded forecast when budget_feasible is False.
    """
    vals=[requested,opening_cash,min_cash,debt_capacity]
    signed=[opening_retained,legal_profit,cash_before_payment]
    if any(not math.isfinite(v) or v<0 for v in vals) or any(not math.isfinite(v) for v in signed):
        raise ValueError('invalid legal/cash domain')
    retained_before_payment=opening_retained+legal_profit
    if not math.isfinite(retained_before_payment):raise ValueError('retained earnings arithmetic overflow')
    legal=max(0,retained_before_payment)
    capacity=max(0,opening_cash+cash_before_payment-min_cash+debt_capacity)
    paid=min(requested,legal,capacity)
    required_financing=max(0,min_cash-opening_cash-cash_before_payment+paid)
    financing=min(required_financing,debt_capacity)
    ending_cash=opening_cash+cash_before_payment+financing-paid
    funding_gap=max(0,min_cash-ending_cash)
    cash_shortfall=max(0,-ending_cash)
    tol=1e-10*max(1,opening_cash,abs(cash_before_payment),min_cash,debt_capacity)
    budget_feasible=funding_gap<=tol
    status='feasible' if budget_feasible else ('unfunded_scheduled_payments' if cash_shortfall>tol else 'below_operating_cash_buffer')
    return dict(requested=requested,legal_capacity=legal,cash_capacity=capacity,paid=paid,
                financing=financing,ending_cash=ending_cash,ending_retained=retained_before_payment-paid,
                retained_before_payment=retained_before_payment,required_financing=required_financing,
                credit_limit=debt_capacity,funding_gap=funding_gap,cash_shortfall=cash_shortfall,
                budget_feasible=budget_feasible,status=status)

def validate(p):
    for k in ['generation','tariff','shares','discount','life','maintenance','interest','old_payables','nav_remaining','pump_remaining','pump_total','opening_debt','opening_cash','cash_floor','mother_cash','mother_cash_floor','mother_borrow_capacity','mother_debt']:
        if not math.isfinite(p[k]) or p[k]<0: raise ValueError(k)
    if p['generation']<=0 or p['tariff']<=0 or p['shares']<=0 or p['life']<10 or int(p['life'])!=p['life']: raise ValueError('positive volume/price/shares/integer life>=10')
    for k in ['sale_ratio','payout','pump_owned','sub_declare','sub_receive','terminal_tax','near_tax']:
        if not 0<=p[k]<=1: raise ValueError(k)
    if p['pump_remaining']>p['pump_total']: raise ValueError('project remaining budget exceeds total')
    # Starting below the desired cash floor is a genuine stress state, not an
    # invalid input. It must flow into the funding constraint instead of vanishing.
    if not math.isfinite(p['mother_retained']):raise ValueError('nonfinite parent retained earnings')
    for k in ['pump_schedule','nav_schedule','old_ap_schedule']:
        if abs(sum(p[k])-1)>1e-10 or any(v<0 for v in p[k]): raise ValueError(k)
    if len(p['generation_shock'])<5: raise ValueError('five years required')
    if p.get('depreciation_mode')=='cohort':
        if p['maintenance_life']<=0 or p['navigation_life']<=0:raise ValueError('asset lives')
        if any(c[1]<0 or c[2]<0 for c in p['old_asset_cohorts']):raise ValueError('asset cohort')

def operations(p):
    validate(p); rows=[];asset_remaining=[c[1] for c in p.get('old_asset_cohorts',[])];old_initial=sum(asset_remaining)
    for t in range(1,int(p['life'])+1):
        j=t-1; generation=p['generation']*(p['generation_shock'][j] if j<len(p['generation_shock']) else 1)
        if t>=p.get('nav_da_start',8):generation+=p.get('navigation_extra_generation',0)
        tariff=p['tariff']-(p['tariff_shock'][j] if j<len(p['tariff_shock']) else 0)
        if tariff<=0: raise ValueError('nonpositive realized tariff')
        revenue=generation*p['sale_ratio']*tariff
        # Mostly fixed operations; 20% of domestic cash production cost varies with volume.
        hydro_cash_cost=p['hydro_cash_cost']*(.8+.2*generation/p['generation'])
        hydro_ebitda=revenue-hydro_cash_cost-p['hydro_overhead']
        other_ebitda=p['other_ebitda']
        maintenance=p['maintenance']
        # Existing asset cohorts capped by their remaining carrying-value proxy.
        # New maintenance is capitalized then amortized over 20 years (half-year convention).
        # This is a normalized tax-basis proxy, not a claim about exact future tax returns.
        if p.get('depreciation_mode')=='cohort':
            old_da=0
            for k,c in enumerate(p['old_asset_cohorts']):
                charge=min(asset_remaining[k],c[2]);old_da+=charge;asset_remaining[k]-=charge
            renewal_da=maintenance/p['maintenance_life']*min(t-.5,p['maintenance_life'])
            legacy_da=old_da+renewal_da
            nav_da=(p['nav_remaining']+p['nav_incurred'])/p['navigation_life'] if p['nav_da_start']<=t<p['nav_da_start']+p['navigation_life'] else 0
        else:
            old_da=p['legacy_da'] if t<=10 else 0;renewal_da=0 if t<=10 else maintenance
            legacy_da=old_da+renewal_da;nav_da=0
        hydro_da=legacy_da*p['hydro_da_share']+nav_da; other_da=legacy_da*(1-p['hydro_da_share'])
        tax=p['near_tax'] if t<=4 else p['terminal_tax']
        hydro_nopat=(hydro_ebitda-hydro_da)*(1-tax)
        other_nopat=(other_ebitda-other_da)*(1-p['other_tax'])
        commissioned=p['pump_commission'][j] if j<len(p['pump_commission']) else 1
        # Project NOPAT after tax, net of 2% annual maintenance/depreciation; no fuel-free cash illusion.
        pump_nopat=p['pump_total']*commissioned*p['pump_roic']
        pump_da=p['pump_total']*commissioned*.02
        pump_capex=(p['pump_remaining']*p['pump_schedule'][j] if j<len(p['pump_schedule']) else 0)
        nav_capex=(p['nav_remaining']*p['nav_schedule'][j] if j<len(p['nav_schedule']) else 0)
        old_ap=(p['old_payables']*p['old_ap_schedule'][j] if j<len(p['old_ap_schedule']) else 0)
        nci_capital=pump_capex*(1-p['pump_owned'])*p['nci_funding_fraction']
        nci_pump_profit=pump_nopat*(1-p['pump_owned'])
        # Matching NCI cash calls: no claim that CYPC owns 100% of mixed-ownership pumps.
        nci_pump_cash=nci_pump_profit
        wc=p['wc_first'] if t==1 else (p['wc_next'] if t<=5 else 0)
        nopat=hydro_nopat+other_nopat+pump_nopat
        da=legacy_da+nav_da+pump_da
        capex=maintenance+pump_da+pump_capex+nav_capex+old_ap
        fcff=nopat+da-capex-wc
        rows.append(dict(year=t,generation=generation,tariff=tariff,hydro_revenue=revenue,
          hydro_cash_cost=hydro_cash_cost,hydro_ebitda=hydro_ebitda,other_ebitda=other_ebitda,
          hydro_da=hydro_da,other_da=other_da,tax=tax,hydro_nopat=hydro_nopat,other_nopat=other_nopat,
          pump_commissioned=commissioned,pump_nopat=pump_nopat,pump_da=pump_da,nopat=nopat,da=da,
          old_asset_da=old_da,old_asset_remaining=sum(asset_remaining),old_asset_initial=old_initial,
          maintenance_da=renewal_da,navigation_da=nav_da,
          maintenance=maintenance,pump_capex=pump_capex,nav_capex=nav_capex,old_payables_paid=old_ap,
          capex=capex,wc=wc,fcff=fcff,nci_capital=nci_capital,nci_pump_profit=nci_pump_profit,
          nci_pump_cash=nci_pump_cash,owned_unlevered_cash=fcff+nci_capital-nci_pump_cash))
    return rows

def financing(p, rows):
    debt=p['opening_debt'];cash=p['opening_cash'];retained=p['mother_retained'];mcash=p['mother_cash'];
    divrec=p['mother_div_receivable'];oldrec=divrec;mdebt=p['mother_debt'];nci_retained=0; result=[]
    last_np=p['estimated_2026_common_profit']
    for row in rows[:10]:
        r=dict(row);t=r['year'];interest=debt*p['interest'];shield=interest*(p['interest_shield'] if t<=4 else p['terminal_tax'])
        assoc_profit=p['associate_profit']*(1+p['associate_growth'])**(t-1)
        assoc_cash=p['associate_cash']*(1+p['associate_growth'])**(t-1)
        nci_profit=p['existing_nci_profit']+r['nci_pump_profit']
        nci_cash=p['existing_nci_cash']+r['nci_pump_cash']
        common_np=r['nopat']-interest+shield+assoc_profit+p['other_financial_cash']-nci_profit
        parent_interest=mdebt*p['interest']
        # Parent direct plants share of domestic economic cash; 100%-owned subsidiary earnings residual.
        parent_da=(r['hydro_da']-r['navigation_da'])*p['parent_hydro_fraction']+r['navigation_da']
        parent_direct_nopat=(r['hydro_ebitda']*p['parent_hydro_fraction']-parent_da)*.75
        parent_direct_np=parent_direct_nopat-parent_interest*.75
        subsidiary_profit=max(0,common_np-assoc_profit-p['other_financial_cash']-parent_direct_np)
        declared=subsidiary_profit*p['sub_declare']
        new_receipts=declared*p['sub_receive']
        old_receipts=min(oldrec,p['old_div_collection'][t-1] if t<=len(p['old_div_collection']) else 0)
        oldrec-=old_receipts;divrec+=declared-new_receipts-old_receipts
        mother_legal_profit=parent_direct_np+assoc_profit+p['other_financial_cash']+declared
        parent_capex=r['maintenance']*p['parent_hydro_fraction']+r['nav_capex']+r['old_payables_paid']*.25
        subsidiary_capital=r['pump_capex']*p['pump_owned']*.3
        mother_cash_before=parent_direct_nopat+parent_da-parent_interest*.75+assoc_cash+p['other_financial_cash']+new_receipts+old_receipts-parent_capex-subsidiary_capital
        requested=max(0,last_np*p['payout'])
        if t>5:requested=max(0,common_np*p['payout'])
        pay=legal_payment(requested,retained,mother_legal_profit,mcash,mother_cash_before,p['mother_cash_floor'],p['mother_borrow_capacity'])
        if not pay['budget_feasible']:
            # Do not use hypothetical group borrowing or intercompany transfers to
            # rescue a parent cash budget for which no financing authority exists.
            # Keep real losses and the approved financing amount, but stop before
            # inventing funded closing cash, five-year distributions or terminal value.
            r.update(payment_feasibility='infeasible',infeasibility_reason=pay['status'],
                opening_debt=debt,opening_cash=cash,common_profit=common_np,
                dividend_requested=requested,dividend_paid=pay['paid'],
                distribution_per_share=pay['paid']/p['shares'],
                parent_legal_profit=mother_legal_profit,parent_retained=pay['ending_retained'],
                parent_legal_capacity=pay['legal_capacity'],parent_cash_capacity=pay['cash_capacity'],
                parent_cash_before=mother_cash_before,parent_new_borrow=pay['financing'],
                parent_credit_limit=pay['credit_limit'],parent_required_financing=pay['required_financing'],
                parent_funding_gap=pay['funding_gap'],parent_cash_shortfall=pay['cash_shortfall'],
                parent_cash_after_all_scheduled_payments=pay['ending_cash'],
                parent_ending_cash=None,parent_ending_debt=None,
                parent_debt_after_authorized_draw=mdebt+pay['financing'],
                parent_dividend_receivable=divrec,new_borrowing=None,ending_debt=None,ending_cash=None)
            result.append(r)
            return result
        actual=pay['paid'];mother_surplus=max(0,pay['ending_cash']-p['mother_cash_floor'])
        mother_repay=min(mdebt,mother_surplus);mdebt+=pay['financing']-mother_repay
        mcash=pay['ending_cash']-mother_repay;retained=pay['ending_retained']
        legacy_dividend_paid=p.get('legacy_dividend_payable',0) if t==1 else 0
        group_before=r['fcff']-interest+shield+assoc_cash+p['other_financial_cash']-nci_cash+r['nci_capital']-legacy_dividend_paid
        surplus=group_before-actual;repay=min(debt,max(0,surplus+cash-p['cash_floor']))
        new_borrow=max(0,p['cash_floor']-cash-surplus);debt_end=debt+new_borrow-repay
        cash_end=cash+surplus+new_borrow-repay
        # Cash in a subsidiary is not automatically available to repay parent debt.
        # Retain it as group cash instead of creating an impossible debt allocation.
        if debt_end<mdebt:
            debt_end=mdebt
            new_borrow=max(0,debt_end-debt);repay=max(0,debt-debt_end)
            cash_end=cash+surplus+new_borrow-repay
        nci_retained+=p['existing_nci_profit']-p['existing_nci_cash']
        parent_unlevered_cash=parent_direct_nopat+parent_da-parent_capex
        subsidiary_unlevered_cash=r['fcff']-parent_unlevered_cash
        subsidiary_after_internal=subsidiary_unlevered_cash-(interest-shield-parent_interest*.75)-nci_cash+r['nci_capital']+subsidiary_capital-new_receipts-old_receipts-legacy_dividend_paid
        r.update(opening_debt=debt,opening_cash=cash,interest=interest,interest_shield=shield,
          associate_profit=assoc_profit,associate_cash=assoc_cash,common_profit=common_np,
          minority_profit=nci_profit,minority_cash=nci_cash,nci_retained=nci_retained,
          legacy_dividend_paid=legacy_dividend_paid,
          group_cash_before_common=group_before,dividend_requested=requested,dividend_paid=actual,distribution_per_share=actual/p['shares'],
          new_borrowing=new_borrow,debt_repayment=repay,ending_debt=debt_end,ending_cash=cash_end,
          parent_direct_profit=parent_direct_np,subsidiary_profit=subsidiary_profit,
          subsidiary_dividend_declared=declared,subsidiary_new_dividend_received=new_receipts,
          subsidiary_old_dividend_received=old_receipts,parent_legal_profit=mother_legal_profit,
          parent_retained=retained,parent_dividend_receivable=divrec,parent_cash_before=mother_cash_before,
          parent_legal_capacity=pay['legal_capacity'],parent_cash_capacity=pay['cash_capacity'],
          parent_capex=parent_capex,parent_sub_capital=subsidiary_capital,parent_new_borrow=pay['financing'],
          parent_repayment=mother_repay,parent_ending_debt=mdebt,parent_ending_cash=mcash,
          parent_unlevered_cash=parent_unlevered_cash,subsidiary_unlevered_cash=subsidiary_unlevered_cash,
          subsidiary_cash_after_internal=subsidiary_after_internal,
          subsidiary_ending_debt=debt_end-mdebt,subsidiary_ending_cash=cash_end-mcash,
          parent_sub_financing_transfer=mdebt-debt_end*p['mother_debt']/p['opening_debt'])
        # Parent transfer is not a second external group debt; group total controls.
        if mdebt>debt_end+1e-8:raise ValueError('parent debt exceeds group debt; funding allocation infeasible')
        result.append(r);debt=debt_end;cash=cash_end;last_np=common_np
    return result

def valuation(p,rows,finance,from_year=0):
    if any(x.get('payment_feasibility')=='infeasible' for x in finance):
        raise ValueError('unfunded parent cash budget: no funded common-equity valuation or holder terminal')
    future=rows[from_year:];rate=p['discount']
    enterprise=pv([r['fcff'] for r in future],rate)
    nci_calls=pv([r['nci_capital'] for r in future],rate)
    nci_pumps=pv([r['nci_pump_cash'] for r in future],rate)
    existing_nci=pv([p['existing_nci_profit']] * len(future),p['nci_discount'])
    retained_nci=finance[from_year-1]['nci_retained'] if from_year else 0
    assoc_earn=p['associate_profit']*(1+p['associate_growth'])**from_year
    assoc=assoc_earn*p['associate_multiple'];finasset=p['other_financial_value']
    debt=finance[from_year-1]['ending_debt'] if from_year else p['opening_debt']
    cash=finance[from_year-1]['ending_cash'] if from_year else p['opening_cash']
    excess_cash=max(0,cash-p['cash_floor'])
    legacy_claim=p.get('legacy_dividend_payable',0) if not from_year else 0
    total=enterprise+nci_calls-nci_pumps-existing_nci-retained_nci+assoc+finasset-debt+excess_cash-legacy_claim
    return dict(from_year=from_year,remaining_years=len(future),enterprise=enterprise,nci_capital_pv=nci_calls,nci_pump_value=nci_pumps,
      existing_nci_value=existing_nci,retained_nci=retained_nci,associate_earnings=assoc_earn,
      associate_value=assoc,other_financial_value=finasset,debt=debt,cash=cash,required_operating_cash=p['cash_floor'],excess_cash=excess_cash,legacy_dividend_claim=legacy_claim,equity=total,per_share=total/p['shares'])

def owner_earnings_capitalization(p, ke):
    """Cross-check: mature maintenance-adjusted equity earnings, fixed debt policy.
    Financial holdings added once; all interest paid; balloon principal deducted.
    Different financing policy and equity discount rate from the main enterprise DCF.
    """
    if ke<=0 or not math.isfinite(ke):raise ValueError('positive equity capitalization cost')
    o=operations(p);m=o[-1]
    mature_cash=m['hydro_nopat']+m['other_nopat']+m['da']-m['pump_da']-m['maintenance']
    owner_earn=mature_cash-p['opening_debt']*p['interest']*(1-p['terminal_tax'])-p['existing_nci_profit']
    factor=(1-(1+ke)**(-p['life']))/ke
    franchise=owner_earn*factor
    # Preserve real first-ten-year tax shields and WC, not perpetual depreciation.
    transition=pv([r['hydro_nopat']+r['other_nopat']+r['da']-r['pump_da']-r['maintenance']-r['wc']-mature_cash-(p['opening_debt']*p['interest']*(p['terminal_tax']-p['interest_shield']) if r['year']<=4 else 0) for r in o],ke)
    mandatory=-pv([r['nav_capex']+r['old_payables_paid'] for r in o],ke)
    pump=pv([r['pump_nopat']-r['pump_capex']+r['nci_capital']-r['nci_pump_cash'] for r in o],ke)
    principal=-p['opening_debt']/(1+ke)**p['life']
    financial=p['associate_profit']*p['associate_multiple']+p['other_financial_value']
    excess=max(0,p['opening_cash']-p['cash_floor'])
    legacy_claim=p.get('legacy_dividend_payable',0)
    equity=franchise+transition+mandatory+pump+principal+financial+excess-legacy_claim
    return dict(owner_earnings=owner_earn,equity_capitalization_rate=ke,factor=factor,franchise=franchise,transition=transition,mandatory=mandatory,pump=pump,terminal_principal=principal,financial_assets=financial,excess_cash=excess,legacy_dividend_claim=legacy_claim,equity=equity,per_share=equity/p['shares'])

def run(p):
    o=operations(p);f=financing(p,o)
    if f and f[-1].get('payment_feasibility')=='infeasible':
        return dict(parameters=p,operations=o,financing=f,status='funding_infeasible',
            infeasibility=dict(year=f[-1]['year'],reason=f[-1]['infeasibility_reason'],
                parent_funding_gap=f[-1]['parent_funding_gap'],parent_cash_shortfall=f[-1]['parent_cash_shortfall'],
                next_step='revise an evidenced payment, funding or investment assumption; no automatic rescue'),
            current=None,year_5=None)
    return dict(parameters=p,operations=o,financing=f,current=valuation(p,o,f),year_5=valuation(p,o,f,5))
