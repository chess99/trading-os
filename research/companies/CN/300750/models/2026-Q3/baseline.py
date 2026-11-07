#!/usr/bin/env python3
"""Standalone CATL 2026Q3 ordinary-owner model, CNY bn / bn shares.
Each source pool is an economic attribution budget, NOT a synthetic legal entity.
No market prices. Forecast cancellation and share transfers are not legal facts.
"""
import json,math,datetime,sys
ASOF='2026-10-29T19:40:29+08:00'
REGISTERED=4.627249686
EMPLOYEE=.028319044
OPTIONS=.000519738
SEPT_QTY=.010945162
SEPT_PAID=3.30315513838
TRADES=[(8,.000697833,.19997683436),(15,.0006895,.19237993188),(16,.000222,.061019185),(19,.0001867,.0499936164),(21,.003488624,.7999985385),(22,.002271,.4999467487),(28,.0008713,.19998299442),(29,.0002338,.053672625)]
DEBT=39.897579+16.871100+76.354823+52.737747+4.064886
FIN=369.813786+62.779978+.629346-1.646355-DEBT-90-15-1.632147
INVEST_COST=13.148849+11.824729

def law(re,res,reg,profit,optional=0):
    eligible=max(0.,profit+min(0.,re))
    statutory=min(eligible*.1,max(0.,reg*.5-res))
    extra=eligible*optional
    return re+profit-statutory-extra,res+statutory,statutory,extra

def sale(cost,recovery,fee,taxrate=.25):
    gross=cost*recovery;expense=gross*fee;gain=gross-cost-expense
    tax=max(0.,gain)*taxrate
    return gross-expense-tax,gain-tax,expense,tax

def operations(method,scale,extra,cycle,n,g,previous):
    if method=='volume':
        p=[1100*.065+6.5,1270*.063+7,1440*.062+7.5,1600*.061+9,1760*.060+9.5]
        inv=[42,44,45,46,47]
        if n<=5:earn=p[n-1]*scale;capital=inv[n-1]*scale
        elif n<=10:
            growth=[.06,.05,.04,.03,.03][n-6];roic=[.16,.15,.14,.13,.12][n-6]
            earn=previous*(1+growth);capital=(earn-previous)/roic
        else:earn=previous*(1+g);capital=earn*g/.12
    else:
        # Independently chosen earnings/reinvestment entry: fixed 10% expansion
        # years2-5 with 20% incremental return, then 3% / 12% after year5.
        earn=78*scale if n==1 else previous*(1+(.10 if n<=5 else .03 if n<=10 else g))
        capital=earn*(.10/.20 if n<=5 else (.03 if n<=10 else g)/.12)
    if n<=5:capital+=extra
    shock=20 if cycle and n==1 else 15 if cycle and n==2 else 0
    return earn,earn-shock,capital,shock

def run(method='volume',r=.095,g=.025,scale=1.,extra=0.,cycle=False,upstream=.75,parent_start=100.,parent_earn=.55,friction=.02,voluntary=0.,n_years=480,cutday=29,trade_through=29,fee_rate=.001,cancel_year=1,loan_repay=.50,loan_allowance=0.,recovery=.80,buyback=0.,buy_price=None,refinance=1.,source_profit_access=1.,reg_override=None,employee_transfer=True,exercise=True,fund_end=11,fund_recovery=.8,matched_locked=0.,matched_unlock_year=6,matched_recovery=1.,matched_fee=0.,first_maturity=None,**unused):
    assert n_years>=12 and 0<=refinance<=1 and 0<=loan_repay<=1
    assert 0<=matched_locked<=1 and 0<=matched_recovery and 0<=matched_fee<=1
    purchases=[x for x in TRADES if x[0]<=min(cutday,trade_through)]
    paid=sum(x[2] for x in purchases);qty=SEPT_QTY+sum(x[1] for x in purchases)
    # Q3 cash already includes September purchases and September fees. October
    # fee is a 10bp economic budget; exact commission/tax is not disclosed.
    fees=paid*fee_rate
    foregone=sum(x[2]*(cutday-x[0])/365*.02 for x in purchases)
    carry=FIN*.02*cutday/365-foregone
    pc=parent_start+parent_start*.02*cutday/365-paid-fees-foregone
    sc=FIN-parent_start+(FIN-parent_start)*.02*cutday/365
    re=145.440692-4.598335875*1.411 # buyback costs belong to treasury cost, not operating RE
    reserve=2.313325;reg=REGISTERED if reg_override is None else reg_override
    cp=166.987461;treasury_cost=SEPT_PAID+paid+fees
    issued=REGISTERED;employee=EMPLOYEE;option_rights=OPTIONS;employee_cost=6.932212
    div_ar=.008228;loan=132.661171;allowance=loan_allowance;re-=allowance
    source_re=0.;source_restricted=0.;optional_reserve=0.;parent_cost=8.490108;source_cost=INVEST_COST-parent_cost
    subcost=105.393005;subimp=6.669403
    debt=DEBT;matched=DEBT
    group_equity=386.880990-paid-fees+carry
    common_operating_capital=386.880990-FIN-INVEST_COST
    fund_cost=0.;fund_uncalled=.4
    nci_equity=36.335776;nci_cash=15.;nci_capital=nci_equity-nci_cash
    rows=[];previous=0.;failure=None;failure_state=None;pv=0.;pv5=0.;distributions=[]
    for n in range(1,n_years+1):
        op_pc,op_sc,op_re,op_source_re,op_loan,op_eq=pc,sc,re,source_re,loan,group_equity
        op_reg,op_cp,op_res=reg,cp,reserve
        normal,profit,capital,shock=operations(method,scale,extra,cycle,n,g,previous);previous=normal
        owner=profit-capital
        # Gross NCI business and investments remain outside common attribution.
        nci_profit=profit*.07/.93;nci_invest=(capital-(min(fund_uncalled,max(0.,capital),.4) if n==1 else 0.))*.07/.93
        nci_interest=nci_cash*.02;nci_distribution=max(0.,nci_profit-nci_invest+nci_interest)
        nci_cash+=nci_profit-nci_invest+nci_interest-nci_distribution
        nci_equity+=nci_profit+nci_interest-nci_distribution;nci_capital+=nci_invest
        # Matching assets are costs/tax bases, not automatic debt cancellation.
        debt_open=debt;matched_open=matched
        maturity=min(debt, (56.768679 if first_maturity is None else first_maturity) if n==1 else DEBT*.10)
        new_debt=maturity*refinance;due=maturity-new_debt
        locked=min(matched,DEBT*matched_locked) if n<matched_unlock_year else 0.
        matched_basis=min(max(0.,matched-locked),max(0.,matched-(debt-due)))
        matched_net,matched_gain,matched_expense,matched_tax=sale(matched_basis,matched_recovery,matched_fee)
        matched-=matched_basis
        interest_debt=debt_open*.025;interest_matched=matched_open*.025
        matched_interest_net=(interest_matched-interest_debt)-max(0.,interest_matched-interest_debt)*.20
        p_interest=(pc-(buyback*.25 if n==1 else 0.))*.025;s_interest=sc*.025
        p_tax=max(0.,p_interest)*.20;s_tax=max(0.,s_interest)*.20
        pi=p_interest-p_tax;si=s_interest-s_tax
        pc+=pi+owner*.55;sc+=si+owner*.45
        fund_call=min(fund_uncalled,max(0.,capital),.4) if n==1 else 0.
        fund_uncalled-=fund_call;fund_cost+=fund_call
        pc-=fund_call*.45;sc+=fund_call*.45
        common_operating_capital+=capital-fund_call
        fund_net=fund_gain=fund_fee=fund_tax=fund_basis=0.
        if n==fund_end:
            fund_basis=fund_cost;fund_net,fund_gain,fund_fee,fund_tax=sale(fund_cost,fund_recovery,friction)
            fund_cost=0.;pc+=fund_net
        # Non-parent budgets are after common ownership/tax. Access fraction
        # is a capacity assumption, not invented individual statutory reserves.
        source_re+=profit*.45+si
        soldp=solds=salecost=saletax=salegainp=salegains=0.
        if 6<=n<=10:
            soldp=parent_cost/(11-n);solds=source_cost/(11-n)
            netp,salegainp,fee_p,tax_p=sale(soldp,recovery,friction)
            nets,salegains,fee_s,tax_s=sale(solds,recovery,friction)
            parent_cost-=soldp;source_cost-=solds;pc+=netp;sc+=nets
            source_re+=salegains;salecost=fee_p+fee_s;saletax=tax_p+tax_s
        # Economic attribution: 55% parent /45% non-parent matching assets
        # and debt. No NCI liquidity/necessary cash is available for this debt.
        pc+=(matched_net+matched_interest_net)*.55;sc+=(matched_net+matched_interest_net)*.45
        source_re+=(matched_gain+matched_interest_net)*.45
        p_due=due*.55;s_due=due*.45
        p_paid=min(p_due,max(0.,pc));s_paid=min(s_due,max(0.,sc))
        pc-=p_paid;sc-=s_paid;debt-=p_paid+s_paid
        unpaid=due-p_paid-s_paid
        if unpaid>1e-7:
            failure='debt maturity cannot be paid from authorised attributed resources'
            fp=parent_earn*profit+pi+salegainp+fund_gain+(matched_gain+matched_interest_net)*.55
            fr,fs,fstat,fopt=law(re,reserve,reg,fp,voluntary)
            failure_state=dict(year=n,operating_profit=profit,reinvestment=capital,opening_debt_face=debt_open,scheduled_maturity=maturity,new_borrowing=new_debt,net_debt_due=due,actual_parent_principal_paid=p_paid,actual_source_principal_paid=s_paid,unpaid_principal=unpaid,debt_face=debt,parent_cash=pc,source_cash=sc,matched_remaining_cost=matched,matched_remaining_tax_basis=matched,matched_restricted_cost=locked,matched_disposed_basis=matched_basis,matched_gross_proceeds=matched_basis*matched_recovery,matched_realisation_expense=matched_expense,matched_realisation_tax=matched_tax,matched_realised_gain_after_tax=matched_gain,matched_interest_net=matched_interest_net,parent_legal_profit=fp,parent_retained=fr,parent_statutory_reserve=fs,parent_optional_reserve=optional_reserve+fopt,source_budget_retained=source_re,internal_loan_face=loan,internal_loan_allowance=allowance,dividend_receivable=div_ar,remaining_parent_financial_cost=parent_cost,remaining_source_financial_cost=source_cost,fund_cost=fund_cost,common_operating_capital=common_operating_capital,common_equity=group_equity+profit+pi+si+salegainp+salegains+fund_gain+matched_gain+matched_interest_net,nci_cash=nci_cash,nci_equity=nci_equity,dividend=0.,necessary_operating_liquidity=90.)
            break
        # Repay finite internal principal first after year5, subject to actual
        # source cash. Reclassification never creates consolidated profit/cash.
        principal=min(loan,max(0.,sc-div_ar)*loan_repay) if n>=6 else 0.
        loan-=principal;sc-=principal;pc+=principal
        reversal=min(allowance,principal);allowance-=reversal
        desired_decl=max(0.,profit*.22 if n<=5 else sc-div_ar)
        declaration=min(desired_decl,max(0.,source_re)*source_profit_access,max(0.,sc-div_ar))
        source_re-=declaration;div_ar+=declaration
        receipt=min(max(0.,sc),div_ar*(upstream if n<=5 else 1.))
        sc-=receipt;pc+=receipt;div_ar-=receipt
        legal_profit=parent_earn*profit+pi+declaration+salegainp+reversal+fund_gain+(matched_gain+matched_interest_net)*.55
        re,reserve,stat,opt=law(re,reserve,reg,legal_profit,voluntary)
        optional_reserve+=opt
        # Legal cancellation consumes equity premium, not another cash payment.
        cancelled=0.;bbpaid=0.;bbfee=0.;bought=0.;cancellation_re_charge=0.
        if n==1 and buyback:
            if buy_price is None or buy_price<=0:raise ValueError('priced conditional purchase required')
            bbpaid=buyback;bbfee=buyback*fee_rate;bought=buyback/buy_price
            if pc<bbpaid+bbfee:failure='unfunded conditional repurchase';break
            pc-=bbpaid+bbfee;qty+=bought;treasury_cost+=bbpaid+bbfee
        if n==cancel_year:
            cancelled=qty;issued-=cancelled;reg-=cancelled
            premium=max(0.,treasury_cost-cancelled);cp_used=min(cp,premium);cp-=cp_used;cancellation_re_charge=premium-cp_used;re-=cancellation_re_charge
            qty=0.;treasury_cost=0.
        # Forecast transfers are separate from actual legal balances. Year1
        # 8.081586m uses the disclosed second employee plan; remaining legacy
        # treasury is budgeted over years2-5. Price158.42 is plan consideration,
        # not a security quote. No buyback quantity is inferred from it.
        transfer_qty=0.;employee_receipt=0.;employee_basis=0.;option_issue=0.;option_receipt=0.
        if employee_transfer and n<=5:
            transfer_qty=min(employee,.008081586 if n==1 else employee/(6-n))
            employee_basis=employee_cost*transfer_qty/employee if employee else 0.
            employee_receipt=transfer_qty*158.42
            employee-=transfer_qty;employee_cost-=employee_basis
            pc+=employee_receipt;cp+=employee_receipt-employee_basis
        if exercise and n==1:
            option_issue=option_rights;option_rights=0.
            # Prior-month exercise consideration for these same two plans is
            # an economic receipt proxy, not verified future contract cash.
            option_receipt=option_issue*(15854459.09/56437)
            pc+=option_receipt;issued+=option_issue;reg+=option_issue;cp+=option_receipt-option_issue
        economic_shares=issued-qty+option_rights
        effective_shares=issued-qty-employee
        wanted=([8.5,9.5,10.5,12,13][n-1]*effective_shares if n<=5 else max(0.,owner+pi+si)+max(0.,op_pc+op_sc)/5)
        dividend=min(max(0.,wanted),max(0.,pc),max(0.,re))
        pc-=dividend;re-=dividend;dps=dividend/effective_shares
        group_equity+=profit+pi+si+salegainp+salegains+fund_gain+matched_gain+matched_interest_net-dividend-bbpaid-bbfee+employee_receipt+option_receipt
        residual=pc+sc-(op_pc+op_sc+owner+pi+si+(soldp+solds)*recovery-salecost-saletax+fund_net+matched_net+matched_interest_net-p_paid-s_paid-dividend-bbpaid-bbfee+employee_receipt+option_receipt)
        assert abs(residual)<1e-6*max(1.,abs(pc+sc))
        assert abs(loan-(op_loan-principal))<1e-8
        equity_residual=group_equity-(pc+sc+parent_cost+source_cost+fund_cost+common_operating_capital+matched-debt)
        assert abs(equity_residual)<1e-6*max(1.,abs(group_equity))
        assert abs(re-(op_re+legal_profit-stat-opt-dividend-cancellation_re_charge))<1e-6*max(1.,abs(re))
        if min(pc,sc,nci_cash)<-1e-7: failure='negative cash without authorised financing';break
        disc=(1+r)**n;pv+=dps/disc
        if n>5:pv5+=dps/(1+r)**(n-5)
        if n<=5:distributions.append(dps)
        row=dict(year=n,normal_operating_profit=normal,operating_profit=profit,reinvestment=capital,cycle_loss=shock,common_owner_cash=owner,
          opening_parent_cash=op_pc,opening_source_cash=op_sc,parent_interest_gross=p_interest,source_interest_gross=s_interest,financial_income_tax=p_tax+s_tax,
          parent_own_cash=owner*.55-fund_call*.45,source_own_cash=owner*.45+fund_call*.45,source_profit=profit*.45,source_budget_retained=source_re,source_restricted_budget=source_restricted,
          opening_parent_retained=op_re,parent_legal_profit=legal_profit,new_dividend_declaration=declaration,dividend_receipt=receipt,dividend_receivable=div_ar,
          statutory_addition=stat,voluntary_addition=opt,parent_statutory_reserve=reserve,parent_optional_reserve=optional_reserve,parent_retained=re,
          loan_face=loan,loan_allowance=allowance,loan_carrying=loan-allowance,loan_repayment=principal,loan_allowance_reversal=reversal,internal_debt=loan,
          parent_subsidiary_cost=subcost,parent_subsidiary_impairment=subimp,parent_subsidiary_carrying=subcost-subimp,
          financial_cost_sold=soldp+solds,financial_gross_proceeds=(soldp+solds)*recovery,financial_gain=salegainp+salegains,financial_sale_tax=saletax,financial_sale_cost=salecost,
          fund_call=fund_call,fund_uncalled=fund_uncalled,fund_remaining_cost=fund_cost,fund_sale_basis=fund_basis,fund_net_receipt=fund_net,fund_sale_gain=fund_gain,fund_sale_fee=fund_fee,fund_sale_tax=fund_tax,remaining_parent_financial_cost=parent_cost,remaining_source_financial_cost=source_cost,
          registered=reg,issued=issued,employee_transfer_quantity=transfer_qty,employee_transfer_receipt=employee_receipt,employee_transfer_cost=employee_basis,remaining_employee_treasury_cost=employee_cost,option_issue=option_issue,option_exercise_receipt=option_receipt,repurchased_uncancelled=qty,employee_treasury_legal=employee,option_claims=option_rights,effective_dividend_budget_shares=effective_shares,
          diluted_economic_shares=economic_shares,cancelled=cancelled,repurchase_cash=bbpaid,repurchase_fee=bbfee,parent_capital_reserve=cp,cancellation_retained_charge=cancellation_re_charge,
          dividend=dividend,dps=dps,desired_dividend=wanted,dividend_shortfall=max(0.,wanted-dividend),parent_cash=pc,source_cash=sc,common_financial_cash=pc+sc,
          matched_opening_cost=matched_open,matched_remaining_tax_basis=matched,matched_restricted_cost=locked,matched_disposed_basis=matched_basis,matched_gross_proceeds=matched_basis*matched_recovery,matched_realisation_expense=matched_expense,matched_realisation_tax=matched_tax,matched_realised_gain_after_tax=matched_gain,matched_interest_net=matched_interest_net,parent_debt_face=debt*.55,source_debt_face=debt*.45,parent_matched_cost=matched*.55,source_matched_cost=matched*.45,actual_parent_principal_paid=p_paid,actual_source_principal_paid=s_paid,net_debt_due=due,unpaid_principal=unpaid,debt_face=debt,debt_repayment=maturity,new_borrowing=new_debt,matched_financial_asset=matched,debt_interest=interest_debt,matched_asset_income=interest_matched,
          necessary_operating_liquidity=90.,capital_payable=1.632147,capital_payable_matched_cash=1.632147,
          nci_profit=nci_profit,nci_reinvestment=nci_invest,nci_distribution=nci_distribution,nci_cash=nci_cash,nci_equity=nci_equity,nci_operating_capital=nci_capital,
          common_operating_capital=common_operating_capital,common_equity=group_equity,cash_residual=residual,equity_residual=equity_residual,group_gross_liquidity=pc+sc+matched+90+15+1.632147,
          pv_distribution=dps/disc)
        rows.append(row)
    # No terminal balance reset. The explicit series is extended to480 years.
    # Tail PV bound includes all liquid wealth plus a gross-profit perpetuity;
    # no equity value is awarded to unpaid/unrealised nominal ledger balances.
    economic_shares=issued-qty+option_rights
    tail_bound=(max(0.,normal)*(1+g)/(r-g)+max(0.,pc+sc)+parent_cost+source_cost+fund_cost+max(0.,matched-debt))/max(1e-9,economic_shares)/(1+r)**len(rows)
    feasible=failure is None
    return dict(method=method,parameters=dict(r=r,g=g,scale=scale,extra=extra,cycle=cycle,upstream=upstream,parent_start=parent_start,parent_earn=parent_earn,friction=friction,voluntary=voluntary,n_years=n_years,cutday=cutday,trade_through=trade_through,fee_rate=fee_rate,cancel_year=cancel_year,loan_repay=loan_repay,loan_allowance=loan_allowance,recovery=recovery,buyback=buyback,buy_price=buy_price,refinance=refinance,source_profit_access=source_profit_access,employee_transfer=employee_transfer,exercise=exercise,fund_end=fund_end,fund_recovery=fund_recovery,matched_locked=matched_locked,matched_unlock_year=matched_unlock_year,matched_recovery=matched_recovery,matched_fee=matched_fee,first_maturity=first_maturity),
      capital_bridge=dict(paid_october=paid,cumulative_paid=SEPT_PAID+paid,fees_budget=fees,finance_carry=carry,foregone_income=foregone,repurchased_quantity=SEPT_QTY+sum(x[1] for x in purchases),remaining_minimum_budget=20-SEPT_PAID-paid,registered_at_cutoff=REGISTERED,actual_effective_shares=REGISTERED-EMPLOYEE-SEPT_QTY-sum(x[1] for x in purchases)),
      PV=pv if feasible else None,TV5=pv5 if feasible else None,D=distributions,feasible=feasible,failure=failure,failure_state=failure_state,rows=rows,tail_PV_upper_bound=tail_bound if feasible else None,
      TV_fraction=pv5/(1+r)**5/pv if feasible and pv else None)

SPECS={'financing_distribution_cut':{'refinance':0.,'matched_locked':.8,'matched_unlock_year':6,'matched_recovery':.8,'matched_fee':.02,'first_maturity':130.},'financing_delay':{'refinance':0.,'matched_locked':.8,'matched_unlock_year':6,'matched_recovery':.8,'matched_fee':.02},'financing_failure':{'refinance':0.,'matched_locked':1.,'matched_unlock_year':6,'first_maturity':DEBT},'base':{},'core_low':{'r':.10,'g':.02},'core_high':{'r':.09,'g':.03},'cycle':{'cycle':True},'structural':{'r':.105,'g':.015,'scale':.70,'extra':10},'optimistic':{'r':.09,'g':.03,'scale':1.15},'capital_plus10':{'extra':10},'upstream_stress':{'parent_start':40,'upstream':.25,'source_profit_access':.5},'loan_slow':{'loan_repay':.10},'loan_not_repaid':{'loan_repay':0.},'loan_allowance':{'loan_allowance':.473575},'fees_30bp':{'fee_rate':.003},'no_refinancing':{'refinance':0},'reserve_10pct':{'voluntary':.10},'sale_recovery60':{'recovery':.60},'fund_delay_loss':{'fund_end':14,'fund_recovery':0.},'cancellation_delayed':{'cancel_year':3},'no_future_incentive_settlement':{'employee_transfer':False,'exercise':False},'pre_last_trade':{'trade_through':28},'old_fact_same_date':{'trade_through':0},'september_cutoff':{'cutday':0}}
