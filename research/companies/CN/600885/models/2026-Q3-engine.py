#!/usr/bin/env python3
"""Hongfa conditional economic budget. CNY millions; no external inputs or market prices.
Opening 2026Q3 consolidated facts; parent H1 legal balances carried with explicit
unobserved-Q3 budget, never represented as Q3 legal financial statements.
"""
import json, math, copy
ASOF='2026-10-30T10:36:00Z'
SHARES=1547.594313

def initial(p=None):
    old_face=77.12 if p is None else p['gongkong_opening_face']
    g_cash=383.9017*(.05 if p is None else p['gongkong_cash_ratio'])
    p_cash=.28620116; p_liab=.60350084; loan=770.25196668; olddiv=462.04128696
    total=17723.72169015; common=13863.64127742
    e_eq=total-p_cash+p_liab-loan-olddiv
    own=(common-p_cash+p_liab-loan-olddiv)/.8
    debt=761.10694607+204.43647101+52.91925576+62.90281556
    restricted=.01020053; accrued=2.90169682
    dep=2639.52623523-1363.07223155-restricted-accrued
    cash=1363.07223155-p_cash; funds=512.96538307; payable=181.03960682
    capital=e_eq+debt+loan+olddiv+payable-cash-dep-funds-restricted-accrued
    return dict(year=0,revenue=23000.,wc=7600.,fixed=capital-7600.,cash=cash,deposit=dep,funds=funds,restricted=restricted,
        debt=debt,parent_loan=loan,parent_dividend_payable=olddiv,minority_dividend_payable=payable,
        op_equity=own,lower_equity=e_eq-own,op_re=0.,op_reserve=0.,op_paid_capital=962.906843,
        parent_cash=p_cash,parent_liability=p_liab,parent_re=8.44394080,parent_reserve=419.91693518,
        parent_cost=4898.67364591,parent_capital=1547.594313,loan_allowance=0.,
        loan_accrued=0.,deposit_accrued=accrued,tax_losses=0.,shares=SHARES,
        internal_other_face=4647.3991,pool_cash=100.,pool_assets=4647.3991,pool_equity=100.,pool_re=0.,pool_reserve=0.,pool_arrears=0.,gongkong_old_face=old_face,gongkong_cash=g_cash,gongkong_assets=27.5129+old_face-g_cash,gongkong_equity=27.5129,gongkong_re=0.,gongkong_reserve=0.,gongkong_arrears=0.,internal_gongkong_limit=81.,internal_gongkong_draw=0.,lower_re=0.,lower_reserve=0.,lower_capital=1404.328164,internal_accrued=0.,
        parent_equity=4898.67364591+loan+olddiv+p_cash-p_liab)

def parameters(name):
    p=dict(name=name,method='sales',growth=[.14,.12,.10,.08,.06],margin=.165,longmargin=.15,wc=.32,fc=.36,
      tax=.16,rate=.09,lower=.05,paydelay=0,deposit_release=2,loan_repay=5,upstream=.50,
      internal_draw=0.,gongkong_use=.75,gongkong_growth=1.,gongkong_reference_net=4.6422,gongkong_opening_face=77.12,gongkong_cash_ratio=.05,gongkong_refinance=True,gongkong_repay_year=1,pool_roll=.90,pool_hold=0,pool_min_cash=100.,pool_profit_factor=1.,pool_base_cash=100.,pool_loss=12.8126,parent_tax=.25,recovery=.95,finance_rate=.018,capshock=0.)
    if name=='core_low': p.update(margin=.16,longmargin=.145,rate=.095,wc=.33,fc=.37)
    if name=='core_high': p.update(margin=.17,longmargin=.155,rate=.085,wc=.31,fc=.35)
    if name=='capital': p.update(method='capital',growth=[.12,.10,.09,.07,.05],roc=.18,rate=.09)
    if name=='cyclical': p.update(growth=[.02,.05,.16,.12,.08],margin=.145,capshock=.05)
    if name=='structural': p.update(growth=[.08,.06,.04,.03,.02],margin=.135,longmargin=.11,wc=.38,fc=.40,lower=.065)
    if name=='upside': p.update(growth=[.18,.16,.13,.10,.08],margin=.18,longmargin=.165,wc=.30,fc=.34)
    if name=='margin_minus_1pp': p.update(margin=.155,longmargin=.14)
    if name=='collection_20days': p.update(wc=.32+20/365)
    if name=='upstream_delay': p.update(paydelay=2,upstream=.35,deposit_release=3,loan_repay=7,internal_draw=81.)
    if name=='tax25': p.update(tax=.25)
    if name=='lower_minority7': p.update(lower=.07)
    if name=='gongkong_draw': p.update(internal_draw=81.)
    if name=='gongkong_delayed': p.update(internal_draw=81.,gongkong_repay_year=3)
    if name=='gongkong_illiquid': p.update(internal_draw=81.,gongkong_use=1.,gongkong_growth=.1)
    if name=='pool_no_roll': p.update(pool_roll=0.,pool_hold=3,pool_min_cash=500.)
    if name=='pool_weak': p.update(pool_profit_factor=.5,pool_min_cash=500.,pool_hold=3)
    if name=='gongkong_no_old': p.update(internal_draw=81.,gongkong_opening_face=0.)
    if name=='gongkong_additive': p.update(internal_draw=81.,gongkong_refinance=False)
    if name=='gongkong_cash10': p.update(gongkong_cash_ratio=.10)
    return p

def reserve(re, profit, sr, cap):
    # Cover existing loss before statutory allocation, never 10% of raw profit after a loss.
    taxable_positive=max(0.,profit-max(0.,-re))
    add=min(max(0.,.5*cap-sr),.10*taxable_positive)
    return re+profit-add,sr+add,add

def step(prev,p,t,override=None):
    s=copy.deepcopy(prev); start=copy.deepcopy(prev)
    g=p['growth'][t-1] if t<=5 else (.06-(t-5)*.004 if t<=15 else .02)
    g=max(.02,g) if t>5 else g
    rev=s['revenue']*(1+g)
    margin=p['margin'] if t<=5 else p['margin']+(p['longmargin']-p['margin'])*min(1.,(t-5)/10)
    if p['name']=='cyclical' and t>2: margin=.165 if t<=5 else .165+(.15-.165)*min(1.,(t-5)/10)
    wc=rev*p['wc']; fixed=rev*p['fc']; depreciation=.14*s['fixed']
    capex=depreciation+fixed-s['fixed']; delta_wc=wc-s['wc']
    if p['method']=='capital':
        # Independent operating entry: incumbent NOPAT and independently budgeted
        # return on new productive capital; no sales-margin-derived earnings.
        old_nopat=prev.get('capital_nopat',3150.)
        old_k=s['wc']+s['fixed']
        new_k=old_k*(1+g)
        inc=new_k-old_k
        roc=p['roc'] if t<=5 else p['roc']+(.105-p['roc'])*min(1.,(t-5)/10)
        fade=.002*min(t,15)/15
        nopat=old_nopat*(1-fade)+inc*roc
        wc=new_k*.47;fixed=new_k*.53;delta_wc=wc-s['wc'];capex=depreciation+fixed-s['fixed']
        rev=new_k/.68; ebit=nopat/(1-p['tax'])
        s['capital_nopat']=nopat
    else: ebit=rev*margin
    if override is not None:
        rev=override['rev'];wc=override['wc'];fixed=override['fixed'];depreciation=override['da'];capex=override['capex'];delta_wc=wc-s['wc'];ebit=override['ebit']
    financial_income=(s['deposit']+s['funds']+s['restricted'])*p['finance_rate']+s['cash']*.005
    ext_interest=s['debt']*.035
    int_interest=s['parent_loan']*.021
    taxable=ebit+financial_income-ext_interest-int_interest
    # No cross-entity loss offset: aggregate positive taxable budget, losses not recognized as an asset.
    tax=max(0.,taxable)*p['tax']
    baseline_net=taxable-tax
    # Named entity sub-ledger is an ALLOCATION within consolidated assets/profits,
    # not a second business added to the sales or capital entry.
    draw=p['internal_draw'] if t==1 else 0.
    face0=s['internal_gongkong_draw'];face=face0+draw
    old_face=s['gongkong_old_face']
    refinanced=min(old_face,draw) if p['gongkong_refinance'] else 0.
    old_face-=refinanced
    gc0=s['gongkong_cash'];ge0=s['gongkong_equity'];ga0=s['gongkong_assets']
    g_base_ebit=(p['gongkong_reference_net']/.85+p['gongkong_opening_face']*.033)*rev/17202.48068691
    g_ebit=g_base_ebit*p['gongkong_growth']
    g_interest=(face+old_face)*.033
    baseline_g_interest=p['gongkong_opening_face']*.033
    interest_change=g_interest-baseline_g_interest
    g_tax=max(0.,g_ebit-g_interest)*.15
    g_base_tax=max(0.,g_base_ebit-baseline_g_interest)*.15
    # Lender is electroacoustic (25%); no cross-entity loss tax credit.
    lender_increment_tax=(max(0.,taxable-g_base_ebit+interest_change)-max(0.,taxable-g_base_ebit))*.25
    g_net=g_ebit-g_interest-g_tax
    g_delta_net=g_net-(g_base_ebit-baseline_g_interest-g_base_tax)
    adjustment=g_ebit-g_base_ebit-(g_tax-g_base_tax)-lender_increment_tax
    tax+=g_tax-g_base_tax+lender_increment_tax
    net=baseline_net+adjustment
    lower_profit=baseline_net*p['lower']+g_delta_net*.25
    own_profit=net-lower_profit
    # Borrower spends part of the new draw on operating capital, an explicit
    # additional investment beyond unchanged operating plan; no false group inflow.
    draw_use=(draw-refinanced)*p['gongkong_use']
    g_invest=.8*max(0.,g_net)+draw_use
    delta_wc+=draw_use;wc+=draw_use
    s['gongkong_assets']+=g_invest
    s['gongkong_cash']+=draw-refinanced+g_net-g_invest
    s['gongkong_equity']+=g_net
    s['gongkong_re'],s['gongkong_reserve'],g_reserve_add=reserve(s['gongkong_re'],g_net,s['gongkong_reserve'],20.)
    g_floor=383.9017*p['gongkong_cash_ratio']
    g_due=face if t>=p['gongkong_repay_year'] else 0.
    repayment_internal=min(g_due,max(0.,s['gongkong_cash']-g_floor))
    s['gongkong_cash']-=repayment_internal;face-=repayment_internal
    s['internal_gongkong_draw']=face;s['gongkong_arrears']=face if t>=p['gongkong_repay_year'] else 0.
    old_due=old_face*.20 if t>5 else 0.
    old_repaid=min(old_due,max(0.,s['gongkong_cash']-g_floor))
    s['gongkong_cash']-=old_repaid;s['gongkong_old_face']=old_face-old_repaid
    s['gongkong_arrears']+=old_due-old_repaid
    g_dividend=min(max(0.,g_net)*.5,max(0.,s['gongkong_re']),max(0.,s['gongkong_cash']-g_floor)) if face==0. else 0.
    s['gongkong_cash']-=g_dividend;s['gongkong_equity']-=g_dividend;s['gongkong_re']-=g_dividend
    # Remaining announced internal aid: pooled economic budget, not invented
    # individual contracts. 20% maturities/year; 90% normally renewed. Existing
    # physical assets already reside in consolidated capital. No forced writeoff.
    pf=s['internal_other_face'];pool_interest=pf*.033
    pool_baseline_profit=pf*.03*.75-p['pool_loss']*max(0.,1-(t-1)/3) # known FY Jindu loss fades only conditionally
    pool_profit=pool_baseline_profit*(p['pool_profit_factor'] if t<=3 else 1.)
    pool_delta=pool_profit-pool_baseline_profit
    net+=pool_delta;own_profit+=pool_delta;tax+=pool_delta/3;ebit+=pool_delta/.75 # 25% incremental positive tax base, no loss asset
    pool_cash0=s['pool_cash'];pool_eq0=s['pool_equity']
    s['pool_cash']+=pool_profit;s['pool_equity']+=pool_profit;s['pool_re']+=pool_profit
    pool_due=min(pf,pf*.20*(1-p['pool_roll'])+s['pool_arrears'])
    pool_paid=min(pool_due,max(0.,s['pool_cash']-(p['pool_min_cash'] if t<=3 else p['pool_base_cash'])))
    s['pool_cash']-=pool_paid;s['internal_other_face']-=pool_paid;s['pool_arrears']=pool_due-pool_paid
    pool_dividend=min(max(0.,s['pool_re']),max(0.,s['pool_cash']-(p['pool_min_cash'] if t<=3 else p['pool_base_cash']))) if t>p['pool_hold'] and s['pool_arrears']==0 else 0.
    s['pool_cash']-=pool_dividend;s['pool_equity']-=pool_dividend;s['pool_re']-=pool_dividend
    cash_before=s['cash'];s['cash']+=net+depreciation-capex-delta_wc
    s['wc']=wc;s['fixed']=fixed;s['revenue']=rev
    s['lower_equity']+=lower_profit;s['op_equity']+=own_profit
    lender_distributable_profit=own_profit-.75*g_net-pool_profit+.75*g_dividend+pool_dividend
    s['op_re'],s['op_reserve'],op_reserve_add=reserve(s['op_re'],lender_distributable_profit,s['op_reserve'],s['op_paid_capital'])
    # Deposits are not legal restricted cash: contractual maturity budget rather than immediate sweep.
    dep_redeem=s['deposit'] if t==p['deposit_release'] else 0.
    funds_redeem=s['funds'] if t==1 else 0.
    accrued_redeem=s['deposit_accrued'] if t==p['deposit_release'] else 0.
    s['deposit_accrued']-=accrued_redeem
    s['deposit']-=dep_redeem;s['funds']-=funds_redeem;s['cash']+=dep_redeem+funds_redeem+accrued_redeem
    buffer=rev*.05
    # Only cash outside named borrower and residual borrower pool can service
    # platform distributions. These balances are SUBSETS, not additional assets.
    ring_cash=s['gongkong_cash']+s['pool_cash']
    buffer=ring_cash+max(0.,buffer-g_floor-p['pool_base_cash'])
    # Normal external debt rolls unchanged at 3.5%; any new borrowing is visible
    # and limited by 15% sales. Never let an insolvent negative cash state run on.
    borrow=max(0.,buffer-s['cash']);s['cash']+=borrow;s['debt']+=borrow
    if s['debt']>rev*.15: raise ValueError('financing capacity exhausted')
    oldpay=min(s['parent_dividend_payable'],max(0.,s['cash']-buffer)) if t>p['paydelay'] else 0.
    s['parent_dividend_payable']-=oldpay;s['cash']-=oldpay;s['parent_cash']+=oldpay
    minority_old=min(s['minority_dividend_payable'],max(0.,s['cash']-buffer))
    s['minority_dividend_payable']-=minority_old;s['cash']-=minority_old
    loanpay=min(s['parent_loan'],start['parent_loan']/max(1,p['loan_repay']-t+1),max(0.,s['cash']-buffer)) if t<=p['loan_repay'] else min(s['parent_loan'],max(0.,s['cash']-buffer))
    s['parent_loan']-=loanpay;s['cash']-=loanpay;s['parent_cash']+=loanpay
    # Parent loan interest included above as E expense, is paid, then separately taxed at parent.
    s['parent_cash']+=int_interest
    # Parent loan is E's funding: net income already deducted interest, no second cash deduction.
    s['lower_re'],s['lower_reserve'],lower_reserve_add=reserve(s['lower_re'],lower_profit,s['lower_reserve'],s['lower_capital'])
    other_lower_profit=lower_profit-g_net*.25
    other_lower_dist=min(max(0.,s['lower_re']-g_dividend*.25),max(0.,other_lower_profit),max(0.,s['cash']-buffer)*p['lower'])
    lower_dist=other_lower_dist+g_dividend*.25
    s['lower_re']-=lower_dist
    s['cash']-=lower_dist;s['lower_equity']-=lower_dist
    payout=p['upstream'] if t<=5 else (.75 if t<=10 else 1.)
    desired=max(0.,own_profit)*payout
    if t>10: desired=max(desired,s['cash']-buffer)
    declaration=min(desired,max(0.,s['op_re']),max(0.,s['cash']-buffer)) if t>p['paydelay'] else 0.
    s['op_re']-=declaration;s['op_equity']-=declaration;s['cash']-=declaration
    upper_minor=declaration*.2;parent_new=declaration*.8;s['parent_cash']+=parent_new
    overhead=3.*(1.02**(t-1))
    parent_bank_income=start['parent_cash']*.005
    s['parent_cash']+=parent_bank_income
    p_tax=max(0.,int_interest+parent_bank_income-overhead)*p['parent_tax']
    parent_profit=parent_new+int_interest+parent_bank_income-overhead-p_tax
    s['parent_cash']-=overhead+p_tax
    # The original receivable principal payments do not create parent net profit.
    s['parent_re'],s['parent_reserve'],p_reserve_add=reserve(s['parent_re'],parent_profit,s['parent_reserve'],s['parent_capital'])
    s['parent_equity']+=parent_profit
    clear_p_liab=min(s['parent_liability'],max(0.,s['parent_cash']))
    s['parent_liability']-=clear_p_liab;s['parent_cash']-=clear_p_liab
    desired_holder=max(0.,own_profit*.8)*(.30 if t<=5 else .6 if t<=10 else 1.)
    if t>10: desired_holder=max(desired_holder,s['parent_cash']-1.)
    distribution=min(desired_holder,max(0.,s['parent_re']),max(0.,s['parent_cash']-1.))
    s['parent_cash']-=distribution;s['parent_re']-=distribution;s['parent_equity']-=distribution
    if s['parent_cash']<-.00001: raise ValueError('parent payment funding exhausted')
    g_balance=s['gongkong_cash']+s['gongkong_assets']-s['internal_gongkong_draw']-s['gongkong_old_face']-s['gongkong_equity']
    pool_balance=s['pool_cash']+s['pool_assets']-s['internal_other_face']-s['pool_equity']
    # Lender/residual platform owns 75% of named borrower and all budgeted
    # residual pool. Its loans are assets, not group assets added a second time.
    lender_cash=s['cash']-s['gongkong_cash']-s['pool_cash']
    lender_assets=s['wc']+s['fixed']-s['gongkong_assets']-s['pool_assets']+lender_cash+s['deposit']+s['funds']+s['restricted']+s['deposit_accrued']+s['internal_gongkong_draw']+s['gongkong_old_face']+s['internal_other_face']+.75*s['gongkong_equity']+s['pool_equity']
    lender_liabilities=s['debt']+s['parent_loan']+s['parent_dividend_payable']+s['minority_dividend_payable']
    lender_equity=s['op_equity']+s['lower_equity']-.25*s['gongkong_equity']
    lender_balance=lender_assets-lender_liabilities-lender_equity
    if max(abs(g_balance),abs(pool_balance),abs(lender_balance))>1e-5*max(1,s['op_equity']): raise AssertionError(('entity balance',t,g_balance,pool_balance,lender_balance))
    if min(s['gongkong_cash'],s['pool_cash'],lender_cash)<-1e-6: raise ValueError('entity cash insufficient')
    # Economic balance identities (lower minority capital and upper minority capital separate).
    assets=s['wc']+s['fixed']+s['cash']+s['deposit']+s['funds']+s['restricted']+s['deposit_accrued']
    liabilities=s['debt']+s['parent_loan']+s['parent_dividend_payable']+s['minority_dividend_payable']
    e_res=assets-liabilities-s['op_equity']-s['lower_equity']
    p_assets=s['parent_cost']+s['parent_loan']+s['parent_dividend_payable']+s['parent_cash']
    p_res=p_assets-s['parent_liability']-s['parent_equity']
    # Initial parent H1 audited figures form self-contained opening budget.
    if abs(e_res)>1e-5*max(1,assets) or abs(p_res)>1e-5*max(1,p_assets): raise AssertionError(('balance',t,e_res,p_res))
    s.update(year=t)
    flow=dict(growth=g,ebit=ebit,op_tax=tax,net_income=net,financial_income=financial_income,interest=ext_interest,
      internal_interest=int_interest,depreciation=depreciation,capex=capex,delta_wc=delta_wc,
      op_cfo=net+depreciation-delta_wc,fcfe=net+depreciation-capex-delta_wc,
      deposit_redemption=dep_redeem,deposit_accrued_receipt=accrued_redeem,fund_redemption=funds_redeem,new_debt=borrow,
      old_dividend_received=oldpay,loan_principal_repaid=loanpay,minority_old_paid=minority_old,
      lower_profit=lower_profit,own_profit=own_profit,lower_dividend=lower_dist,upper_dividend=upper_minor,
      new_parent_dividend=parent_new,parent_profit=parent_profit,parent_bank_income=parent_bank_income,parent_tax=p_tax,parent_overhead=overhead,
      op_reserve_add=op_reserve_add,lower_reserve_add=lower_reserve_add,parent_reserve_add=p_reserve_add,holder_distribution=distribution,
      internal_draw=draw,internal_repayment=repayment_internal,internal_face_rollover=pf*.20*p['pool_roll'],internal_interest_gross=pool_interest+g_interest,internal_interest_eliminated=pool_interest+g_interest,
      lender_distributable_profit=lender_distributable_profit,gongkong_old_repaid=old_repaid,gongkong_refinanced=refinanced,gongkong_old_due=old_due,gongkong_interest_change=interest_change,gongkong_baseline_interest=baseline_g_interest,gongkong_interest=g_interest,gongkong_tax=g_tax,gongkong_net=g_net,gongkong_profit_delta=g_delta_net,lender_increment_tax=lender_increment_tax,group_net_adjustment=adjustment,
      gongkong_investment=g_invest,gongkong_dividend=g_dividend,gongkong_reserve_add=g_reserve_add,gongkong_due=g_due,gongkong_equity_residual=g_balance,pool_equity_residual=pool_balance,lender_equity_residual=lender_balance,lender_cash=lender_cash,
      pool_baseline_profit=pool_baseline_profit,pool_profit_delta=pool_delta,pool_interest=pool_interest,pool_profit=pool_profit,pool_due=pool_due,pool_repayment=pool_paid,pool_dividend=pool_dividend,ring_cash=ring_cash,equity_residual=e_res,parent_equity_residual=p_res)
    return s,flow

def exit_value(s,p):
    # A distant liquidation closure tests whole-state conservation, not a magic cash unlock.
    recover=(s['wc']+s['fixed'])*p['recovery'];cost=(s['wc']+s['fixed'])*.01
    cash=recover-cost+s['cash']+s['deposit']+s['funds']+s['restricted']+s['deposit_accrued']
    tax=max(0.,recover-cost-s['wc']-s['fixed'])*p['tax'];cash-=tax
    cash-=s['debt']+s['parent_loan']+s['parent_dividend_payable']+s['minority_dividend_payable']
    if cash<0: raise ValueError('exit insolvency')
    eq=s['op_equity']+s['lower_equity']
    g_recovery=s['gongkong_assets']*(p['recovery']-.01)+s['gongkong_cash']
    g_face=s['gongkong_old_face']+s['internal_gongkong_draw']
    g_loan_received=min(g_face,max(0.,g_recovery))
    g_surplus=max(0.,g_recovery-g_face)
    remainder=cash-g_recovery+g_loan_received
    other_lower=(s['lower_equity']-.25*s['gongkong_equity'])/max(1e-9,eq-s['gongkong_equity'])*remainder
    lower=other_lower+.25*g_surplus
    op_own=remainder-other_lower+.75*g_surplus;upper=op_own*.2;parent_proceeds=op_own*.8
    pool_recovery=s['pool_assets']*(p['recovery']-.01)+s['pool_cash']
    pool_face_received=min(s['internal_other_face'],max(0.,pool_recovery))
    # Parent investment exit costs and gain taxes use historical cost, no fictional step-up.
    fee=parent_proceeds*.005;gain=parent_proceeds-fee-s['parent_cost'];p_tax=max(0.,gain)*.25
    holder=parent_proceeds-fee-p_tax+s['parent_loan']+s['parent_dividend_payable']+s['parent_cash']-s['parent_liability']
    return dict(gongkong_loan_face=g_face,gongkong_loan_received=g_loan_received,gongkong_credit_loss=g_face-g_loan_received,gongkong_minority=.25*g_surplus,pool_face=s['internal_other_face'],pool_face_received=pool_face_received,pool_credit_loss=s['internal_other_face']-pool_face_received,holder=holder,op_recovery=recover,op_exit_cost=cost,op_exit_tax=tax,lower_minority=lower,upper_minority=upper,parent_proceeds=parent_proceeds,parent_cost=s['parent_cost'],parent_gain=gain,parent_fee=fee,parent_tax=p_tax,loan_face_repaid=s['parent_loan'],old_dividend_repaid=s['parent_dividend_payable'],residual=0.)

def run(p,n=160,start=None,first=1):
    s=copy.deepcopy(initial(p) if start is None else start);rows=[];pv=0.
    for t in range(first,n+1):
        s,f=step(s,p,t);pv+=f['holder_distribution']/(1+p['rate'])**(t-first+1)
        rows.append(dict(state=copy.deepcopy(s),flow=f))
    close=exit_value(s,p);pv+=close['holder']/(1+p['rate'])**(n-first+1)
    return dict(parameters=p,horizon=n,start_state=initial(p) if start is None else start,rows=rows,exit=close,value=pv/SHARES)

def main():
    names=['base','core_low','core_high','capital','cyclical','structural','upside','margin_minus_1pp','collection_20days','upstream_delay','tax25','lower_minority7','gongkong_draw','gongkong_delayed','gongkong_illiquid','pool_no_roll','gongkong_no_old','gongkong_additive','gongkong_cash10','pool_weak']
    cases={n:run(parameters(n)) for n in names}
    base=cases['base'];y5=base['rows'][4]['state']
    continued={n:run(parameters(n),160,start=y5,first=6) for n in ['core_low','base','core_high']}
    extended={n:run(parameters(n),240) for n in ['base','core_low','core_high','structural','capital','gongkong_illiquid','gongkong_additive','pool_weak']}
    summary={n:dict(value=c['value'],first5=[r['flow']['holder_distribution']/SHARES for r in c['rows'][:5]],minimum_parent_cash=min(r['state']['parent_cash'] for r in c['rows']),minimum_op_cash=min(r['state']['cash'] for r in c['rows'])) for n,c in cases.items()}
    json.dump(dict(asof=ASOF,unit='CNY million',shares=SHARES,opening=initial(),cases=cases,y5_same_history=continued,extended=extended,summary=summary),__import__('sys').stdout,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False);print()
if __name__=='__main__':main()
