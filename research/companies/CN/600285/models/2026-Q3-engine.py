#!/usr/bin/env python3
"""Standalone stdlib model. CNY million. Conditional budgets, not legal opinions."""
import json, math, sys
ASOF='2026-10-30T09:15:56+00:00'
SHARES=567.115486

def reserve_step(re, reserve, capital, profit):
    # Profit first offsets accumulated losses; only residual positive profit funds reserve.
    topup=min(max(0.0,capital*.5-reserve),.1*max(0.0,profit+min(0.0,re)))
    return re+profit-topup,reserve+topup,topup

def operating(t, method, scenario, previous):
    fade=max(0.0,(20-t)/15) if t>5 else 1.0
    weak=scenario=='cyclical'; structural=scenario=='structural'; good=scenario=='optimistic'
    dg={'low':-.005,'high':.005,'optimistic':.015}.get(scenario,0)
    dm={'low':-.004,'high':.006,'optimistic':.012,'structural':-.05}.get(scenario,0)
    if method=='main':
        growth=(.04+dg)*fade
        sales=4050.0 if t==1 else previous['sales']*(1+growth)
        if weak and t==1: sales*=.9
        if weak and t in (2,3): sales*=1.05
        if structural and t<=3: sales*=.95
        ebitmargin=.22+.014*fade+dm
        if weak and t<=2: ebitmargin-=.03
        ebit=sales*ebitmargin
        return dict(sales=sales,ebit=ebit,ebitmargin=ebitmargin,growth=growth,paste_volume=None,paste_price=None,other_sales=None)
    volume=1750.0 if t==1 else previous['paste_volume']*(1+.02*fade)
    price=1.28 if t==1 else previous['paste_price']*(1+.01*fade)
    other=1700.0 if t==1 else previous['other_sales']*(1+.05*fade)
    sales=volume*price+other
    ebit=volume*price*(.30+.01*fade)+other*(.24+.01*fade)-sales*.088
    return dict(sales=sales,ebit=ebit,ebitmargin=ebit/sales,growth=sales/previous['sales']-1 if t>1 else 0,paste_volume=volume,paste_price=price,other_sales=other)

def fund_path(years, mode='normal', opening_book=50., prior_pref=7.2):
    """LP-attributable project ledger. Gross project returns, fees and carry separately."""
    call_years=(1,3) if mode=='delayed' else (1,2)
    end_invest=3 if mode=='delayed' else 2
    exits={6:50.,8:100.,10:50.} if mode=='delayed' else ({4:50.,6:100.,8:50.} if mode=='loss' else {4:50.,5:100.,6:50.})
    multiple=.65 if mode=='loss' else (2.20 if mode=='upside' else 1.60)
    project=40.; liquid=opening_book-40.; nav=opening_book; taxbasis=50.
    paid=50.; returned=0.; pref_due=prior_pref; pref_paid=0.; catch_paid=0.; gp_paid=0.; tax_paid=0.; cumulative_tax_income=0.; cum_lp=0.; rows=[]
    def waterfall(amount, outstanding, pref_due, pref_paid, catch_paid):
        principal=min(amount,max(0.,outstanding)); amount-=principal
        preferred=min(amount,max(0.,pref_due)); amount-=preferred
        catch=min(amount,max(0.,(pref_paid+preferred)*.25-catch_paid)); amount-=catch
        lp=principal+preferred+amount*.8; gp=catch+amount*.2
        return lp,gp,principal,preferred,catch,amount*.8
    final=max(exits)
    for t in range(1,years+1):
        old_nav=nav; old_liquid=liquid; old_project=project; old_basis=taxbasis
        call=100. if t in call_years else 0.
        paid+=call; project+=call*.8; liquid+=call*.2
        temporary_income=liquid*.01 if t<=final else 0.
        liquid+=temporary_income
        if t<=final: pref_due+=max(0.,paid-returned)*.08
        fee=(250.*.02 if t<=end_invest else project*.02) if t<=final else 0.
        liquid-=fee
        cost=exits.get(t,0.); gross=cost*multiple
        project-=cost; liquid+=gross
        assert liquid>=-1e-8,('fund cash failure',t,liquid)
        amount=(max(0.,liquid-(0. if t==final else 8.)) if cost else 0.)
        lp,gp,principal,preferred,catch,sharing=waterfall(amount,paid-returned,pref_due,pref_paid,catch_paid)
        liquid-=lp+gp; returned+=principal; pref_due-=preferred; pref_paid+=preferred; catch_paid+=catch; gp_paid+=gp; cum_lp+=lp
        # GP's existing claim against retained realizations is not owned by LP.
        _,carry_reserve,_,_,_,_=waterfall(project+liquid,paid-returned,pref_due,pref_paid,catch_paid)
        nav=project+liquid-carry_reserve
        income=nav-old_nav+lp-call
        taxable_income=gross-cost-fee-gp+temporary_income+(opening_book-50. if t==final else 0.)
        cumulative_tax_income+=taxable_income
        cash_tax=max(0.,max(0.,cumulative_tax_income)*.25-tax_paid); tax_paid+=cash_tax
        taxbasis+=call+taxable_income-lp
        assert abs(old_liquid+call*.2+temporary_income-fee+gross-lp-gp-liquid)<1e-7
        assert abs(old_project+call*.8-cost-project)<1e-7
        assert abs(income+old_nav+call-lp-nav)<1e-7
        rows.append(dict(year=t,mode=mode,company_commitment=250.,fund_total_disclosed_commitment=950.,company_lp_fraction=250./950.,opening_nav=old_nav,opening_tax_basis=old_basis,call=call,unfunded=250.-paid,
            project_cost=project,fund_cash=liquid,fee=fee,temporary_income=temporary_income,project_exit_cost=cost,project_gross_proceeds=gross,project_multiple=multiple,
            lp_distribution=lp,return_capital=principal,preferred_paid=preferred,lp_residual_profit=sharing,gp_paid=gp,
            gp_catchup_paid=catch,cumulative_gp=gp_paid,carry_reserve=carry_reserve,capital_paid=paid,capital_returned=returned,
            preferred_unpaid=pref_due,preferred_cumulative_paid=pref_paid,closing_nav=nav,book_profit=income,taxable_income=taxable_income,
            cumulative_taxable_income=cumulative_tax_income,cash_tax=cash_tax,cumulative_tax_paid=tax_paid,closing_tax_basis=taxbasis,
            cumulative_lp_distribution=cum_lp,cash_distribution_minus_current_profit=lp-income,opening_embedded_book_gain=opening_book-50.,closed=t>=final))
    return rows

def simulate(method='main', scenario='base', years=240, rate=.0975, upstream_delay=0, extra_marketing=0.0, fund_mode='normal', maintenance_extra=0., fund_opening=50., prior_pref=7.2):
    cash=[597.56652869,109.46010010,54.73005005]
    deposits=[1688.144704,0.,0.]; liquid=[234.983493819,17.4061847273,8.7030923637]
    strategic=[197.5321833+50.-fund_opening,6.9309538,3.4654769]; fund=[fund_opening,0.,0.]
    fund_rows=fund_path(years,fund_mode,fund_opening,prior_pref)
    debt=[340.0,21.18874206,10.59437103]; lease=[1.23790336,2.30631632,1.15315816]
    # Q3 debt face proxies sum to317.63636661+54.14674648, lease total4.69737784.
    reps=[5.6,0.,0.]
    re=[1953.75159678,0.,0.]; reserve=[286.10526155,0.,0.]; capital=[567.115486,200.,82.]
    equity=3497.78828339-extra_marketing*.85; minority=40.01588552-extra_marketing*.85*.006
    re[0]-=extra_marketing*.85*.8
    marketing=1350.+extra_marketing
    taxpay=225.96201421; grosswc=1375.516363
    ordinarypay=644.13498011
    wc=grosswc-marketing-taxpay-ordinarypay
    initialfinancial=sum(cash+deposits+liquid+strategic+fund)
    netoperating=equity-initialfinancial+sum(debt+lease+reps)
    first_netoperating=netoperating
    previous={'sales':3951.98354105}
    rows=[]; pv=0.; pv5=0.; pvafter5=0.
    for t in range(1,years+1):
        o=operating(t,method,scenario,previous); sales=o['sales']; ratio=sales/4050
        old_cash=cash[:]; old_equity=equity; old_minority=minority; old_re=re[:]; old_reserve=reserve[:]
        old_fin=sum(deposits+liquid+strategic+fund); old_debt=sum(debt+lease+reps)
        old_wc=wc
        # Three-year transition to normal settlement days; legal claims remain until paid.
        adjustment=min(1.,t/3.)
        new_marketing=(1350.+extra_marketing)*(1-adjustment)+sales*.25*adjustment
        new_taxpay=225.96201421*(1-adjustment)+sales*.02*adjustment
        new_gross=1375.516363*(1-adjustment)+sales*.30*adjustment
        new_ordinary=644.13498011*sales/3951.98354105
        wc=new_gross-new_marketing-new_taxpay-new_ordinary
        delta_wc=wc-old_wc
        # DTA associated with opening excess marketing: no double recognition of expense.
        tax_release=max(0.,marketing-new_marketing)*.15 if t<=3 else 0.
        marketing,taxpay,grosswc,ordinarypay=new_marketing,new_taxpay,new_gross,new_ordinary
        da=100*ratio; capex=(100+maintenance_extra)*ratio+.30*max(0.,sales-previous['sales'])
        # Tax at15% on operating profit; losses kept economically, no immediate tax refund.
        operating_tax=max(0.,o['ebit'])*.15
        opnet=o['ebit']-operating_tax
        profits=[]; cfs=[]; redemptions=[]; principals=[]; interests=[]; taxes=[]; contributions=[]
        weights=[.8,.14,.06]
        for i,w in enumerate(weights):
            depositinterest=deposits[i]*(1620./1688.144704)*.02
            cashinterest=cash[i]*.01
            liquidinterest=liquid[i]*.018
            fr=fund_rows[t-1]
            fundinterest=fr['book_profit'] if i==0 else 0.
            interest=debt[i]*.025+lease[i]*.03
            fintax=(depositinterest+cashinterest+liquidinterest)*.15+(fr['cash_tax'] if i==0 else 0.)
            netfin=depositinterest+cashinterest+liquidinterest+fundinterest-fintax-interest*.85
            depred=deposits[i]/(4-t) if t<=3 else 0.
            liqred=liquid[i] if t==1 else 0.
            eqred=strategic[i]/(6-t) if t<=5 else 0.
            saletax=eqred*(57.928614/207.928614)*.15
            contribution=fr['call'] if i==0 else 0.
            principal=(debt[i]+lease[i])/(4-t) if t<=3 else 0.
            olddeb=debt[i]; oldlease=lease[i]
            if t<=3: debt[i]-=olddeb/(4-t); lease[i]-=oldlease/(4-t)
            deposits[i]-=depred; liquid[i]-=liqred; strategic[i]-=eqred; fund[i]=fr['closing_nav'] if i==0 else 0.
            profit=opnet*w+netfin-saletax
            cf=profit+(da-capex-delta_wc+tax_release)*w+depred+liqred+eqred-principal-contribution
            if i==0: cf+=fr['lp_distribution']-fr['book_profit']
            cash[i]+=cf
            re[i],reserve[i],topup=reserve_step(re[i],reserve[i],capital[i],profit)
            profits.append(profit); cfs.append(cf); redemptions.append(depred+liqred+eqred); principals.append(principal)
            interests.append(interest); taxes.append(operating_tax*w+fintax+saletax-interest*.15); contributions.append(contribution)
        # Minority belongs to silver operating vehicle; no minority haircut to all parent cash.
        subsidiary_div=[]; upstream=0.; minority_div=0.
        payout=.8+.2*min(1.,max(0.,t-5)/15)
        for i in [1,2]:
            floor=sales*.075*weights[i]
            desired=max(0.,profits[i])*payout
            desired+=.10*max(0.,cash[i]-floor-desired)
            if t<=upstream_delay: desired=0.
            div=min(max(0.,re[i]),max(0.,cash[i]-floor),desired)
            re[i]-=div; cash[i]-=div
            ownership=1. if i==1 else .9
            received=div*ownership
            cash[0]+=received; re[0]+=received
            upstream+=received; minority_div+=div*(1-ownership); subsidiary_div.append(div)
        commonprofit=sum(profits)-.1*profits[2]
        desired=max(0.,commonprofit)*payout
        desired+=.10*max(0.,cash[0]-sales*.075*.8-desired)
        commondiv=min(desired,max(0.,re[0]),max(0.,cash[0]-sales*.075*.8))
        cash[0]-=commondiv; re[0]-=commondiv
        vested=5.6 if t==2 else 0.
        if t==2: reps[0]=0.
        equity+=sum(profits)-commondiv-minority_div+vested
        minority+=profits[2]*.1-minority_div
        netoperating+=capex-da+delta_wc-tax_release
        cash_residual=sum(cash)-sum(old_cash)-sum(cfs)+commondiv+minority_div
        equity_residual=equity-old_equity-sum(profits)+commondiv+minority_div-vested
        balance_residual=sum(cash+deposits+liquid+strategic+fund)+netoperating-sum(debt+lease+reps)-equity
        assert min(cash)>-1e-8, ('financing failure',t,cash)
        assert max(abs(cash_residual),abs(equity_residual),abs(balance_residual))<1e-6
        commonpv=commondiv/(1+rate)**t; pv+=commonpv
        if t<=5: pv5+=commonpv
        else: pvafter5+=commondiv/(1+rate)**(t-5)
        rows.append(dict(year=t,calendar_year=2026+t,operating=o,operating_tax=operating_tax,operating_net=opnet,da=da,capex=capex,
            opening_cash=old_cash,closing_cash=cash[:],profits=profits,cash_before_distributions_increments=cfs,
            cash_interest_tax_included=True,financial_redemptions=redemptions,debt_principal_paid=principals,interest_expense=interests,
            tax_expense=taxes,fund_contributions=contributions,fund_contract=fr,deposits=deposits[:],deposit_face=[d*1620./1688.144704 for d in deposits],deposit_accrued=[d*(1-1620./1688.144704) for d in deposits],liquid=liquid[:],strategic=strategic[:],fund=fund[:],
            debt=debt[:],lease=lease[:],repurchase_obligation=reps[:],gross_working_assets=grosswc,marketing_payable=marketing,
            tax_payable=taxpay,ordinary_payables=ordinarypay,net_working_capital=wc,delta_wc=delta_wc,dta_cash_release=tax_release,
            net_operating_book_assets=netoperating,opening_retained_earnings=old_re,closing_retained_earnings=re[:],opening_reserve=old_reserve,
            closing_reserve=reserve[:],subsidiary_dividends=subsidiary_div,parent_upstream_cash_and_income=upstream,
            common_profit=commonprofit,common_distribution=commondiv,common_dps=commondiv/SHARES,minority_distribution=minority_div,
            total_equity=equity,minority_equity=minority,common_equity=equity-minority,common_distribution_pv=commonpv,
            cash_residual=cash_residual,equity_residual=equity_residual,balance_residual=balance_residual))
        previous=o
    return dict(method=method,scenario=scenario,rate=rate,years=years,upstream_delay=upstream_delay,extra_marketing=extra_marketing,fund_mode=fund_mode,maintenance_extra=maintenance_extra,fund_opening=fund_opening,prior_pref=prior_pref,
        initial_net_operating_book_assets=first_netoperating,initial_financial_assets=initialfinancial,value_per_share=pv/SHARES,
        terminal5_per_share=pvafter5/SHARES,first5_dps=[r['common_dps'] for r in rows[:5]],
        terminal_pv_fraction=(pv-pv5)/pv,remaining_nominal_fund=sum(fund),remaining_nominal_obligations=marketing+taxpay+ordinarypay+sum(debt+lease+reps),rows=rows)

def build(years=240):
    cases=[simulate('main','base',years,r) for r in [.10,.095]]
    cases += [simulate('main',s,years,.0975) for s in ['low','high','cyclical','structural','optimistic']]
    cases += [simulate('aux','base',years,.0975),simulate('main','base',years,.0975,2),simulate('main','base',years,.0975,0,300.)]
    cases += [simulate(m,'base',years,.0975,fund_mode=f) for m in ['main','aux'] for f in ['delayed','loss']]
    cases += [simulate('main','base',years,.0975,fund_mode='upside'),simulate('main','base',years,.0975,maintenance_extra=50.)]
    cases += [simulate('main','base',years,.0975,fund_opening=v) for v in [45.,55.]]
    cases += [simulate('main','base',years,.0975,prior_pref=v) for v in [3.2,11.2]]
    return dict(asof=ASOF,shares=SHARES,units='CNY million except per share',cases=cases)

if __name__=='__main__':
    n=int(sys.argv[1]) if len(sys.argv)>1 else 240
    print(json.dumps(build(n),ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False))
