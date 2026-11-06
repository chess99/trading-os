#!/usr/bin/env python3
"""Anjoy Q3 2026, CNY billion, no price input. Python stdlib; deterministic stdout.
Entity budgets are estimates, not undisclosed statutory accounts. No cash is added to PV:
only actual outside common distributions enter PV. Numerical truncation excludes
liquidation; complete hypothetical liquidation is retained ONLY as a boundary diagnostic.
"""
import json, copy, math
ASOF='2026-10-29T00:49:13+00:00'
SHARES=.332128032
FX=6.758 # transaction contractual conversion, not a live quote
IFC_COST=.03047396550*FX
JV_CAP=.07425*FX


def earnings_basis():
    # Original FY2025 consolidated statements, FY2024 comparatives; CNY billions.
    # Strip net interest, subsidy, investment/FV and disposal; retain FX/fees and impairments.
    group24=1.95440939618+.00154046126-.07387302358-.04487738229-.03079371732-.06223276025-(-.00347485928)
    group25=1.79760849066+.01744934699-.05712632673-.05711729731-.05581166406-.00802118739-(-.00145572769)
    parent24=1.20795040881+.00003102162-.01253109747-.01003398284-.98162227918-.05254528930-(-.00004280460)
    parent25=3.73153034136+.00009308262-.04257850794-.00650355658-3.54594033000-.00560244140-(-.00004388889)
    # DWT was only consolidated July onward in 2025 and absent in FY2024.
    dwt_full=.08203093088/.75
    dwt_in_two_year_mean=.5*.03762628840/.75
    maintenance=.51330473986+.00685349229+.05847552991+.02154172341+.00071154688
    return dict(group24=group24,group25=group25,parent24=parent24,parent25=parent25,
                dwt_full_pretax_proxy=dwt_full,dwt_partial_removed=dwt_in_two_year_mean,
                total_existing_normalized=(group24+group25)/2-dwt_in_two_year_mean+dwt_full,
                parent_normalized=(parent24+parent25)/2,maintenance_DA=maintenance,
                domestic_commitment=1.05341430,domestic_nopat_yield=.06,
                group_source='FY2025 physical p103 / printed102',parent_source='FY2025 physical p105 / printed104',maintenance_source='FY2025 physical p204-205 / printed203-204')
EARNINGS=earnings_basis()
EARNINGS['latest_evidence_check']={'nine_month_2026':1.49760963922+.01357718577-.07240371533-.03911829829-.05015099110-.02122644157+.00112780183,'nine_month_2025':1.21415883565+.01817689843-.03417905438-.03819372507-.03581379099-.00191904854+.00110178287,'H1_2026':1.08521643978+.00938491133-.04699513629-.03035857502-.03563024422-.01568847780-.00014699394,'H1_2025':.85314146526+.00540295361-.01187772269-.02640001172-.02485654887-.01199822444+.00009902128}


def entity(name,own,cash,re,capital,reserve,ppe,wc,debt,loan,cost,rev,margin):
    return dict(name=name,own=own,cash=cash,re=re,capital=capital,reserve=reserve,ppe=ppe,wc=wc,debt=debt,loan=loan,cost=cost,rev=rev,margin=margin,payable=0.,pending_ownership=own,capital_premium=0.,lower_tier_nci_book=(.00386751577 if name=='Dingweitai' else .011114106 if name=='IFC' else 0.),equity_other=cash+ppe+wc-debt-loan-re-capital-reserve)

def opening(re_scale=1.):
    # Initial financial liquidity = Q3 cash equivalents + trading financial assets;
    # restricted .08436538631 tracked separately, released after one year, never lost.
    subs=[entity('mature_wholly_owned',1,4.09501137029,1.8,6.70,.65,4.27,1.06,0,0,7.11379885688,12.89,.125),
          entity('Xinhongye',.9,.30,.35,.08,.04,.34,.42,.20,0,.909,1.80,.035),
          entity('Xinliuwu',.744915,.20,.04,.26,.06,.55,.24,.20,.20,.69111536061,1.45,-.025),
          entity('Dingweitai',.7,.15,.06,.0578486,.0289243,.30,.12,0,0,.4445,.70,.15),
          entity('Honghu_Anjoy',.9,.08,.04,.52,.02,.60,.10,.09531241249,0,.468,.60,.06),
          entity('Oriental_Food',.699859,.03,.01,.01,.005,.03,.04,0,0,.04737992419,.16,.025)]
    for s in subs:s['re']*=re_scale;s['equity_other']=s['cash']+s['ppe']+s['wc']-s['debt']-s['loan']-s['re']-s['capital']-s['reserve']
    subs[0]['payable']=.02106
    for q in subs:
        q['trade_payable']=.6992614221 if q['name']=='mature_wholly_owned' else 0.
        q['equity_other']-=q['trade_payable']+q['payable']
    p=dict(cash=3.26-.069017992,re=3.34696287911,reserve=.166644466,capital=10.53425748998,registered_capital=.333288932,capital_premium=10.20096855798,treasury=.10859303382,treasury_shares=.0011609,dividend_shares=SHARES,
                ppe=.205,wc=.10,trade_receivable=.6992614221,loan=.2,investment_cost=9.67379414168,receivable=.02106,
                # .069017992 is already declared H-share liability, not a new A distribution.
                dividend_payable=0.,restricted=.08436538631,external_debt=.02556617843,
                forward_dwt=.11622299074,other_net=-.11077337718,subs=subs)
    p['other_equity']=parent_net_assets(p)-p['capital']-p['reserve']-p['re']+p['treasury']
    return p

def parent_net_assets(p):
    # Group DWT put is not a second standalone mother liability.
    return sum(p[k] for k in ['cash','ppe','wc','trade_receivable','loan','investment_cost','receivable','restricted','other_net'])-p['external_debt']-p['dividend_payable']

def entity_balance(s):
    return s['cash']+s['ppe']+s['wc']-s['debt']-s['loan']-s['payable']-s.get('trade_payable',0.)-s['capital']-s['reserve']-s['re']-s['equity_other']

def law(re, reserve, capital, profit):
    """Losses offset first; capital premium never restores RE. 10% reserve until 50% paid capital."""
    old=re; re+=profit
    transfer=min(max(0.,capital*.5-reserve),max(0.,profit+min(0.,old))*.1)
    return re-transfer,reserve+transfer,transfer

def step_entity(s,rev,margin,wcr,pper,lag,policy,extra_capex=0.,injection=0.,repay_loan=0.,loan_rate=.03,deposit=.015,repayment_fraction=.20,lower_rate_override=None,operating_ebit_override=None,depreciation_rate=.09,wc_override=None):
    b=copy.deepcopy(s); s['cash']+=injection;s['capital']+=injection
    # Settling last year's declaration changes cash/payable only, not earnings or RE.
    settle=s['payable'];s['cash']-=settle;s['payable']=0.
    interest=s['debt']*.035+s['loan']*loan_rate
    cash_interest=max(0.,b['cash'])*deposit
    operating_ebit=rev*margin if operating_ebit_override is None else operating_ebit_override
    pretax=operating_ebit+cash_interest-interest
    tax=max(0.,pretax)*.25 # no instantaneous cash refund or unverified loss carryforward asset
    profit=pretax-tax
    lower_rate=.12115 if s['name']=='IFC' else .01085 if s['name']=='Dingweitai' else 0.
    if lower_rate_override is not None:lower_rate=lower_rate_override
    lower_nci=max(0.,profit)*lower_rate
    profit-=lower_nci
    da=b['ppe']*depreciation_rate
    target=max(0.,rev*pper)
    capex=max(da,target-b['ppe']+da)+extra_capex
    newppe=b['ppe']+capex-da
    wc=rev*wcr if wc_override is None else wc_override; dwc=wc-b['wc']
    fcf=profit+da-capex-dwc
    s['cash']+=fcf
    tradepay=min(s.get('trade_payable',0.),.14,max(0.,s['cash']-rev*.04));s['trade_payable']=s.get('trade_payable',0.)-tradepay;s['cash']-=tradepay
    s['ppe']=newppe;s['wc']=wc;s['rev']=rev
    # Debt is seasonal working funding, roll annually at 3.5%, repay if excess; no free cancellation.
    repayment=min(s['debt'],max(0.,s['cash']-rev*.04)*repayment_fraction)
    s['debt']-=repayment;s['cash']-=repayment
    loanpay=min(s['loan'],repay_loan,max(0.,s['cash']-rev*.04));s['loan']-=loanpay;s['cash']-=loanpay
    financing=max(0.,rev*.04-s['cash'])
    capacity=.80*(s['ppe']+s['wc']) # explicit budget ceiling, not a confirmed credit facility
    assert s['debt']+financing<=capacity+1e-8,(s['name'],'unfunded bank capacity',s['debt']+financing,capacity)
    s['debt']+=financing;s['cash']+=financing
    if s['name'] in ('IFC','Oriental_Food'):
        reserveadd=0.;s['re']+=profit # profit/solvency budget, not Chinese statutory reserve
    elif s['name']=='Indonesia':
        reserveadd=min(max(0.,s['capital']*.20-s['reserve']),max(0.,profit+min(0.,s['re']))*.10)
        s['re']+=profit-reserveadd;s['reserve']+=reserveadd # 10% annual allocation is budget, 20% target statutory
    else:s['re'],s['reserve'],reserveadd=law(s['re'],s['reserve'],s['capital'],profit)
    # Distribution cap applied to full declaration; liquidity retained to meet delayed payment too.
    available=max(0.,s['cash']-rev*.04)
    targetdiv=policy*max(0.,profit)+(.12*max(0.,s['re']-profit) if policy>=.95 else 0.)
    declared=min(max(0.,s['re']),available,targetdiv)
    paid=declared*(1-lag);s['cash']-=paid;s['payable']=declared*lag;s['re']-=declared;s['pending_ownership']=s['own']
    s['cash_check']=s['cash']-(b['cash']+injection-settle+fcf-tradepay-repayment-loanpay+financing-paid)
    assert abs(s['cash_check'])<1e-8 and s['cash']>=-1e-8
    assert declared<=max(0.,s['re']+declared)+1e-9
    # Opening fixture payables must themselves be equity-reconciled.
    assert abs(entity_balance(s))<1e-8,(s['name'],entity_balance(s))
    return dict(name=s['name'],opening=b,closing=copy.deepcopy(s),revenue=rev,margin=margin,operating_ebit=operating_ebit,operating_profit_entry=('historical_normalized_earnings_or_capital_return' if operating_ebit_override is not None else 'sales_times_margin'),pretax_profit=pretax,cash_tax=tax,lower_tier_nci_cash=lower_nci,profit=profit,da=da,capex=capex,dwc=dwc,fcf=fcf,external_interest=b['debt']*.035,intercompany_interest=b['loan']*loan_rate,
                trade_settlement=tradepay,equity_injection=injection,reserve_addition=reserveadd,declared=declared,paid=paid+settle,parent_gross_paid=paid*s['own']+settle*b['pending_ownership'],nci_gross_paid=paid*(1-s['own'])+settle*(1-b['pending_ownership']),new_paid=paid,settled_old=settle,loan_repaid=loanpay,debt_repaid=repayment,debt_drawn=financing,bank_capacity_budget=capacity,bank_repayment_fraction=repayment_fraction)

def liquidate(state,lastrev):
    """Complete wind-down numerical boundary, not a current control-value shortcut."""
    p=copy.deepcopy(state);rows=[];parent_proceeds=0.;loans=0.;nci=0.;realised=0.
    for s in p['subs']:
        # NWC is net of operating liabilities; cash includes outstanding dividend payables.
        gross=s['cash']+.90*s['wc']+.50*s['ppe']
        cost=.03*s['rev']; external=s['debt']+s['payable']
        shortfall=max(0.,cost+external-gross)
        assert shortfall<1e-8,'hypothetical exit has unpaid senior obligations; cannot erase balances'
        trade_recovery=min(s.get('trade_payable',0.),max(0.,gross-cost-external));external+=trade_recovery
        after=max(0.,gross-cost-external)
        loan_recovery=min(s['loan'],after);after-=loan_recovery
        lower_nci_exit=after*(.1814 if s['name']=='IFC' else .01085 if s['name']=='Dingweitai' else 0.)
        eq=after-lower_nci_exit;pp=eq*s['own'];nn=eq*(1-s['own'])+lower_nci_exit
        # Previously declared amounts paid separately to owners, preserving prior RE recognition.
        paidparent=s['payable']*s['own'];paidnci=s['payable']*(1-s['own'])
        parent_proceeds+=pp+paidparent+trade_recovery;loans+=loan_recovery;nci+=nn+paidnci
        realised+=pp-s['cost']
        rows.append(dict(name=s['name'],cash=s['cash'],wc_recovery=.90*s['wc'],ppe_recovery=.50*s['ppe'],exit_expense=cost,exit_expense_paid=cost,external_debt_paid=s['debt'],declared_payables_paid=s['payable'],unpaid_senior_obligations=shortfall,trade_payable=s.get('trade_payable',0.),trade_recovery=trade_recovery,external_debt=s['debt'],declared_payables=s['payable'],loan_due=s['loan'],loan_recovered=loan_recovery,loan_loss=s['loan']-loan_recovery,lower_tier_nci_proceeds=lower_nci_exit,equity_residual=eq,parent_equity_proceeds=pp,nci_equity_proceeds=nn,parent_historical_and_added_cost=s['cost'],parent_realised_gain=pp-s['cost'],ending_cash=0.,ending_ppe=0.,ending_wc=0.,ending_loan=0.,ending_capital=0.,ending_re=0.,ending_nci=0.))
    loan_loss=p['loan']-loans
    mother_exit_cost=.01*lastrev
    mother_disposal=.90*p['wc']+.50*p['ppe']+p['other_net']
    parent_gain=realised-loan_loss+mother_disposal-p['wc']-p['ppe']-p['other_net']-mother_exit_cost
    # No shareholder tax forecast; disposal losses have no assumed tax cash refund.
    tax=max(0.,parent_gain)*.25
    gross=p['cash']+parent_proceeds+loans+mother_disposal+p['restricted']
    payout=max(0.,gross-p['external_debt']-p['dividend_payable']-mother_exit_cost-tax)
    return dict(entities=rows,parent_cash=p['cash'],parent_investment_cost=p['investment_cost'],investment_cost_sum=sum(x['cost'] for x in p['subs']),parent_loan_book=p['loan'],parent_loan_recovery=loans,parent_loan_loss=loan_loss,parent_sub_equity_proceeds=parent_proceeds,parent_realised_gain=parent_gain,parent_re_before=p['re'],parent_re_after_disposal=p['re']+parent_gain-tax,parent_paid_capital_and_premium=p['capital'],parent_reserve=p['reserve'],parent_treasury=p['treasury'],parent_other_net=p['other_net'],parent_disposal_recovery=mother_disposal,parent_exit_expense=mother_exit_cost,tax=tax,parent_debt=p['external_debt'],already_declared_external_payable=p['dividend_payable'],common_final_liquidation_cash=payout,nci_final_cash=nci,all_ending_balances_zero=True)

def retire(s):
    gross=s['cash']+.9*s['wc']+.5*s['ppe'];fee=.03*s['rev']
    unpaid=s['debt']+s['payable'];surplus=gross-fee-unpaid
    guarantee=max(0.,-surplus);available=max(0.,surplus)
    lr=min(s['loan'],available);available-=lr
    parent_eq=available*s['own'];nci=available*(1-s['own'])
    parentcash=parent_eq+lr+s['payable']*s['own']-guarantee
    gain=parent_eq-s['cost']-(s['loan']-lr)-guarantee
    return dict(name=s['name'],opening=copy.deepcopy(s),gross_recovery=gross,exit_cost=fee,external_debt_paid=s['debt'],dividend_payables_settled=s['payable'],parent_guarantee_cash=guarantee,parent_loan_recovery=lr,parent_loan_loss=s['loan']-lr,parent_equity_proceeds=parent_eq,nci_proceeds=nci,parent_investment_cost=s['cost'],parent_realised_gain=gain,parent_cash=parentcash,ending_cash=0.,ending_re=0.,ending_capital=0.,ending_loans=0.,ending_debt=0.,ending_nci=0.)

def economic_book(p):
    return p['cash']+p['ppe']+p['wc']+p['trade_receivable']+p['loan']+p['receivable']+p['other_net']+p['restricted']-p['external_debt']-p['dividend_payable']-p['forward_dwt']+sum(s['own']*(s['cash']+s['ppe']+s['wc']-s['debt']-s['loan']-s['payable']-s.get('trade_payable',0.)-s.get('lower_tier_nci_book',0.)) for s in p['subs'])

def run(case='base',method='main',discount=.09,years=160,re_scale=1.,lag=.15,parent_re_shift=0.,cost_shock=0.,nci_shift=0.,cash_shift=0.,jv_own=.505,sbc_scale=1.,employee_cash_fraction=0.,refinance_refusal=False,treasury_cancel=False,lower_nci_high=False,lower_nci_low=False,dwt_nci_high=False,earnings_anchor=0.):
    p=opening(re_scale);p['re']+=parent_re_shift;p['other_equity']-=parent_re_shift;p['cash']+=cash_shift;p['other_equity']+=cash_shift;p['subs'][0]['cash']-=cash_shift;p['subs'][0]['equity_other']-=cash_shift
    for s in p['subs']:
        if s['own']<1:s['own']=max(0.,s['own']-nci_shift)
    hist=[];pv=0.;revprev=17.6;ifc_observations=[]
    # Core excludes acquisitive IFC and JV; legal cohorts sum external revenue only (no interco duplication).
    for y in range(1,years+1):
        beg=copy.deepcopy(p); inflow=outflow=0.;declaration=0.;nci_cash=0.;subprofit=0.;rows=[];transactions=[];exitgain=0.;earlyexitcash=0.
        if (case=='structural' or refinance_refusal or method=='earnings') and y==4:
            keep=[]
            for sub in p['subs']:
                if sub['name'] in (['Xinliuwu','Xinhongye','Oriental_Food'] if case=='structural' else ['Xinliuwu']):
                    z=retire(sub);transactions.append(dict(type='permanent_water_products_exit',bridge=z));z['mother_cash_before_exit']=p['cash'];p['cash']+=z['parent_cash'];z['mother_cash_after_exit']=p['cash'];assert p['cash']>=0.,'exit requires unfunded parent rescue';earlyexitcash+=z['parent_cash'];exitgain+=z['parent_realised_gain'];nci_cash+=z['nci_proceeds'];p['loan']-=sub['loan'];p['investment_cost']-=sub['cost']
                else:keep.append(sub)
            p['subs']=keep
        if y==1:
            s=entity('IFC',.600005,0.025,0.018,.03274,.003,.115,.085,.1614,0,IFC_COST,.52,.06)
            # IFRS acquisition fair-value/goodwill NOT a second cash asset; historical cost only at mother.
            p['subs'].append(s);p['cash']-=IFC_COST;p['investment_cost']+=IFC_COST;outflow+=IFC_COST
            transactions.append(dict(type='conditional_IFC_close_budget',cash_cost=IFC_COST,own=.600005,assumed_close='Y1',double_counted_fair_value=0.))
            p['subs'].append(entity('Indonesia',jv_own,0,0,0,0,0,0,0,0,0,0,0))
        # Common first five years across core endpoints; auxiliary derives separate operating and capital inputs.
        growth=([.07,.06,.055,.05,.045][y-1] if y<=5 else max(0.,.045*(15-y)/10))
        if method=='aux':growth=([.05,.045,.04,.035,.03][y-1] if y<=5 else max(0.,.03*(12-y)/7))
        if case=='cyclical' and y<=2:growth-=.07
        if case=='structural':growth=min(growth,.01)
        if case=='upside' and y<=7:growth+=.025
        core=16.19261303359 if method=='earnings' else revprev*(1+growth);revprev=core
        for s in p['subs']:
            name=s['name'];inj=0.;extra=0.
            if name=='Dingweitai' and y==2:
                norm26,norm27=(.065,.066) if case=='structural' else ((.08203093088,.08203093088) if method=='earnings' else (.08,.085) if method=='aux' else (.09,.096))
                price=((.08203093088+norm26+norm27)/3*12+.075)*.2
                s['own']+=.2;s['cost']+=price;p['cash']-=price;p['investment_cost']+=price;outflow+=price;p['forward_dwt']=0.
                transactions.append(dict(type='Dingweitai_conditional_20pct',cash_cost=price,new_ownership=s['own'],recognised_forward_cleared=.11622299074))
            if name=='Indonesia':
                inj=JV_CAP/5 if y<=5 else 0.;motherinj=inj*.505;minorinj=inj*.495
                # Funding follows contracted HK path 50.5%; final lower-tier 1% registration remains uncertain.
                direct=0. # p4 prose/diagram 1% conflict: effective midpoint .505, no invented additional cash
                p['cash']-=motherinj;p['investment_cost']+=motherinj;s['cost']+=motherinj;outflow+=motherinj
                rev=[0,.025,.08,.16,.25][y-1] if y<=5 else min(.55,s['rev']*(1.12 if y<=10 else 1.02 if y<=15 else 1))
                margin=[-.03,-.04,.01,.04,.06][y-1] if y<=5 else .07
                wcr=.16;pper=.80;extra=JV_CAP/5*.65 if y<=5 else 0.
                transactions.append(dict(type='JV_five_tranches_budget',total_equity=inj,parent_cash=motherinj,nci_cash=minorinj))
            elif name=='IFC':
                rev=s['rev']*(1.04 if y<=8 else 1.01 if y<=15 else 1.);margin=.06;wcr=.14;pper=.23
                if case=='upside':margin=.075
                # Calendar proxy is separate from rolling valuation years: actual Jan-Jul
                # 2026 plus five months of Y1 run rate; 2027=Y1, 2028=Y2.
                # Profit belongs to IFC shareholders AFTER its lower-tier NCI, BEFORE Anjoy own.
                if y==4:
                    np=[.002473843+ifc_observations[0][0]/5.2805*5/12,ifc_observations[0][0]/5.2805,ifc_observations[1][0]/5.2805]
                    sales=[.055985031+ifc_observations[0][1]/5.2805*5/12,ifc_observations[0][1]/5.2805,ifc_observations[1][1]/5.2805]
                    tests=dict(cumulative_profit=sum(np)>=.01801032585,each_year_profit=all(x>=.005136837 for x in np),each_year_revenue=all(x>=.098629244 for x in sales))
                    gate=all(tests.values())
                    transactions.append(dict(type='IFC_contract_performance_budget',calendar_years=[2026,2027,2028],profit_SGD_bn=np,revenue_SGD_bn=sales,tests=tests,performance_pass=gate,normal_business_CAS_special_audit_confirmed=False,other_ownership_valuation_ODI_conditions_confirmed=False,compensation_shortfall_SGD_bn=max(0.,.01801032585-sum(np)),compensation_receivable_recognised=0.,compensation_cash_received=0.,additional_purchase_budgeted=False))
                    # No automatic purchase without all conditions. In these paths performance
                    # itself fails; if it ever passes, separate audit/approval and bonus budget
                    # must be supplied rather than silently exercising the future agreement.
                    assert not gate,'IFC success requires separately modelled audit, bonus and future agreement'
            else:
                weight={'mature_wholly_owned':12.89/17.6,'Xinhongye':1.8/17.6,'Xinliuwu':1.45/17.6,'Dingweitai':.70/17.6,'Honghu_Anjoy':.60/17.6,'Oriental_Food':.16/17.6}[name]
                rev=core*weight; margin=s['margin']
                if name=='Xinliuwu':margin=min(.025,-.025+.01*y)
                if name=='mature_wholly_owned' and y>5:margin=max(.105,.125-.002*(y-5))
                wcr=.12 if name=='mature_wholly_owned' else .22;pper=.34 if name=='mature_wholly_owned' else .32
                if method=='aux':margin-=.0075;wcr+=.015;pper+=.025
            if case=='cyclical' and y<=3:margin-=.015;wcr+=.025
            if case=='structural':margin-=.03;wcr+=.03;pper+=.05
            if case=='upside':margin+=.006;wcr-=.005
            margin-=cost_shock
            operating_override=None;wc_override=None;dep_rate=.09
            if method=='earnings':
                dep_rate=EARNINGS['maintenance_DA']/6.295
                parent_anchor=EARNINGS['parent_normalized']
                xhy=(.0313389+.0272236*2)/2
                xlw=(-.0155873-.0441429*2)/2
                dwt=EARNINGS['dwt_full_pretax_proxy'];honghu=.0051935*2/.75;ofe=.07*.08
                total=EARNINGS['total_existing_normalized']+earnings_anchor
                mature=total-parent_anchor-xhy-xlw-dwt-honghu-ofe
                fade=1.-.10*min(1.,max(0.,y-5)/10)
                if name=='IFC':
                    rev=.098629244*5.2805
                    normal_np=(.005500431+.003002871*12/7)/2*5.2805
                    operating_override=(normal_np/.75+.1614*.035-.025*.015)*fade
                    extra=0.;wc_override=s['wc'];pper=s['ppe']/rev
                elif name=='Indonesia':
                    # Independent capital deployment, not the main sales/asset ratios.
                    extra=JV_CAP/5*.65 if y<=5 else 0.
                    wc_override=s['wc']+(JV_CAP/5*.30 if y<=5 else 0.)
                    pper=s['ppe']/rev if rev else 0.
                    operating_override=-.005 if y<=2 else (s['ppe']+s['wc'])*(.02 if y==3 else .04 if y==4 else .06)/.75
                else:
                    operating_override={'mature_wholly_owned':mature,'Xinhongye':xhy,'Xinliuwu':xlw,'Dingweitai':dwt,'Honghu_Anjoy':honghu,'Oriental_Food':ofe}[name]*fade
                    wc_override=s['wc'];pper=s['ppe']/rev
                    extra=([.40,.35,.30341430][y-1] if y<=3 else 0.) if name=='mature_wholly_owned' else 0.
                    if name=='mature_wholly_owned':
                        earning_capital=sum([.40,.35,.30341430][:max(0,min(3,y-2))])
                        operating_override+=earning_capital*.06/.75
                margin=operating_override/rev if rev else 0.
            row=step_entity(s,rev,margin,wcr,pper,lag,.75 if y<=5 else 1.,extra,inj,repay_loan=.04 if y>=4 else 0,repayment_fraction=.20 if y<=5 else .50 if y<=10 else 1.,lower_rate_override=(.1762 if lower_nci_high else .0661 if lower_nci_low else None) if name=='IFC' else .035839 if name=='Dingweitai' and dwt_nci_high else None,operating_ebit_override=operating_override,depreciation_rate=dep_rate,wc_override=wc_override)
            if name=='IFC':ifc_observations.append((row['profit'],row['revenue']))
            leak=.05 if name in ('IFC','Indonesia','Oriental_Food') else 0. # budget all-layer cross-border tax/fees, not asserted treaty rate
            row['upstream_leakage_rate']=leak;row['upstream_cash_leakage']=row['parent_gross_paid']*leak
            rows.append(row);inflow+=(row['parent_gross_paid']*(1-leak)+row['trade_settlement']+row['loan_repaid']+row['intercompany_interest']*.75)
            declaration+=row['declared']*s['own']*(1-leak);nci_cash+=row['nci_gross_paid']+row['lower_tier_nci_cash'];subprofit+=(row['profit']-row['declared']*leak)*s['own']
            p['loan']-=row['loan_repaid'];p['trade_receivable']-=row['trade_settlement']
        # Parent own manufacturing/corporate expense: net after-tax operating profit .10bn,
        # income and cash from financial assets shown separately. No subsidiary dividend double count in group earnings.
        parentop=EARNINGS['parent_normalized']*.75*(1.-.10*min(1.,max(0.,y-5)/10)) if method=='earnings' else .10*(core/18.832)
        pfinancial=max(0.,beg['cash'])*.015*.75
        loaninterest=sum(x['intercompany_interest'] for x in rows)
        # Existing repurchased shares were designated for employee incentives, not cancellation.
        # Budget all delivered Y1 with zero subscription in base; noncash SBC uses historical
        # carrying amount as a service-value proxy, not a quoted stock price.
        sbc=0.;employee_cash=0.
        if y==1 and treasury_cancel:
            original_treasury=p['treasury'];cancelled=p['treasury_shares']
            p['registered_capital']-=cancelled;p['capital_premium']-=original_treasury-cancelled
            p['capital']=p['registered_capital']+p['capital_premium'];p['treasury']=0.;p['treasury_shares']=0.
            transactions.append(dict(type='conditional_36month_unused_treasury_cancellation',treasury_carrying_released=original_treasury,registered_capital_reduced=cancelled,cash_paid=0.))
        elif y==1:
            original_treasury=p['treasury'];sbc=original_treasury*sbc_scale
            employee_cash=original_treasury*employee_cash_fraction
            p['capital_premium']+=sbc+employee_cash-original_treasury
            p['capital']=p['registered_capital']+p['capital_premium']
            p['treasury']=0.;p['treasury_shares']=0.;p['dividend_shares']=.333288932
            p['cash']+=employee_cash
            transactions.append(dict(type='budget_existing_treasury_employee_delivery',sbc_expense=sbc,subscription_cash=employee_cash,treasury_carrying_released=original_treasury,shares_delivered=.0011609,registered_capital_change=0.))
        parentprofit=parentop+pfinancial+declaration+loaninterest*.75+exitgain-sbc
        cashop=parentop+pfinancial+inflow
        p['cash']+=cashop
        if y==1:p['cash']+=p['restricted'];p['restricted']=0.;p['cash']-=p['dividend_payable'];p['dividend_payable']=0.
        p['receivable']=sum(s['payable']*s['own']*(.95 if s['name'] in ('IFC','Indonesia','Oriental_Food') else 1.) for s in p['subs'])
        otherpayment=min(max(0.,-p['other_net']),.022154675436);p['cash']-=otherpayment;p['other_net']+=otherpayment
        p['re'],p['reserve'],reserveadd=law(p['re'],p['reserve'],p['registered_capital'],parentprofit)
        # no repeated deduction of dividends paid before Q3 opening. Forecast outside A/H cash only.
        commonprofit=parentop+pfinancial+subprofit+loaninterest*.75-sbc
        desired=.70*max(0.,commonprofit) if y<=5 else max(0.,parentprofit)+.10*max(0.,p['re']-parentprofit)
        cashfloor=.6 # payments, collateral, seasonal procurement and treasury settlement buffer
        distribution=min(max(0.,p['re']),max(0.,p['cash']-cashfloor),desired)
        p['cash']-=distribution;p['re']-=distribution
        # External lease-like debt amortized 5 years; financed only if necessary before distribution.
        debtrepay=min(p['external_debt'],.006,p['cash']);p['external_debt']-=debtrepay;p['cash']-=debtrepay
        expected=beg['cash']+earlyexitcash-outflow+cashop+employee_cash+(beg['restricted']-beg['dividend_payable'] if y==1 else 0)-distribution-debtrepay-otherpayment
        assert abs(p['cash']-expected)<1e-8 and p['cash']>=-1e-8
        assert abs(p['loan']-sum(s['loan'] for s in p['subs']))<1e-8
        balance=parent_net_assets(p)-(p['capital']+p['reserve']+p['re']-p['treasury']+p['other_equity'])
        assert abs(balance)<1e-8,(case,method,y,balance)
        pv+=distribution*SHARES/p['dividend_shares']/(1+discount)**y
        hist.append(dict(year=y,parent_opening=beg,noncash_sbc=sbc,employee_subscription_cash=employee_cash,ordinary_shares_eligible=p['dividend_shares'],early_exit_cash=earlyexitcash,early_exit_realised_gain=exitgain,parent_profit=parentprofit,parent_maintenance_capex=(.205*EARNINGS['maintenance_DA']/6.295 if method=='earnings' else .01845),parent_da=(.205*EARNINGS['maintenance_DA']/6.295 if method=='earnings' else .01845),parent_own_aftertax=parentop,parent_financial_income=pfinancial,parent_declared_investment_income=declaration,parent_actual_receipts=inflow,parent_cashflow_before_dividend=cashop,other_obligation_cash_paid=otherpayment,parent_external_equity_investment=outflow,parent_reserve_addition=reserveadd,common_economic_profit=commonprofit,common_paid=distribution,common_per_share=distribution/p['dividend_shares'],nci_paid=nci_cash,transactions=transactions,entities=rows,parent_closing=copy.deepcopy(p),parent_asset_equity_residual=balance,cash_conservation_residual=p['cash']-expected))
    exit=liquidate(p,core);epv=exit['common_final_liquidation_cash']*SHARES/p['dividend_shares']/(1+discount)**years # excluded from going-concern PV
    first5=sum(r['common_per_share']*SHARES/(1+discount)**r['year'] for r in hist[:5])
    tv5=(pv-first5)*(1+discount)**5
    b0=economic_book(hist[0]['parent_opening']);ri=b0;rirows=[]
    for row in hist:
        b=economic_book(row['parent_opening'])*SHARES/row['parent_opening']['dividend_shares'];e=economic_book(row['parent_closing'])*SHARES/row['parent_closing']['dividend_shares'];earn=e-b+row['common_per_share']*SHARES;res=earn-discount*b
        ri+=res/(1+discount)**row['year'];rirows.append(dict(year=row['year'],opening_adjusted_book=b,closing_adjusted_book=e,economic_profit=earn,capital_charge=discount*b,residual_income=res))
    ri-=economic_book(p)*SHARES/p['dividend_shares']/(1+discount)**years # boundary book, no forced liquidation proceeds
    assert abs(ri-pv)<1e-8
    return dict(input_parameters=dict(case=case,method=method,discount=discount,years=years,re_scale=re_scale,lag=lag,parent_re_shift=parent_re_shift,cost_shock=cost_shock,nci_shift=nci_shift,cash_shift=cash_shift,jv_own=jv_own,sbc_scale=sbc_scale,employee_cash_fraction=employee_cash_fraction,refinance_refusal=refinance_refusal,treasury_cancel=treasury_cancel,lower_nci_high=lower_nci_high,lower_nci_low=lower_nci_low,dwt_nci_high=dwt_nci_high,earnings_anchor=earnings_anchor),residual_income_value_per_share=ri/SHARES,residual_income_annual=rirows,case=case,method=method,discount=discount,years=years,value_per_share=pv/SHARES,first5_distributions_per_share=[r['common_per_share'] for r in hist[:5]],tv5_per_share=tv5/SHARES,tv5_pv_fraction=(pv-first5)/pv,hypothetical_exit_pv_per_share=epv/SHARES,exit_included_in_value=False,annual=hist,exit=exit)

def tests():
    assert law(-2.,0.,10.,1.)==(-1.,0.,0.)
    assert law(-2.,0.,10.,4.)==(1.8,.2,.2)
    # same production entity function, literal manual cash: opening10 + profit.075 - old payable.2 - new dividend.075 =9.8
    s=entity('toy',.6,10,2,0,0,0,0,0,0,0,1,.1);s['payable']=.2;s['equity_other']-=.2
    r=step_entity(s,1,.1,0,0,0,1,deposit=0)
    # policy also releases 12% accumulated RE: .075+.24=.315 => cash9.56, RE1.76
    assert abs(r['declared']-.315)<1e-10 and abs(s['cash']-9.56)<1e-10
    # mother cash cannot be replaced by sub cash: declaration delayed remains receivable.
    s=entity('lag',.6,1,1,0,0,0,0,0,0,0,1,.1)
    r=step_entity(s,1,.1,0,0,1,.7,deposit=0)
    assert r['paid']==0 and abs(s['payable']-.0525)<1e-10
    # cost basis changes disposal statutory gain, never cash proceeds twice.
    a=opening();x=liquidate(a,18);a['subs'][0]['cost']+=.1;a['investment_cost']+=.1;z=liquidate(a,18)
    assert abs(z['parent_realised_gain']-x['parent_realised_gain']+.1)<1e-10
    # NCI shares liquidation residual; debt and parent loan paid before equity.
    s=x['entities'][2];assert abs(s['parent_equity_proceeds']-s['equity_residual']*.744915)<1e-10
    assert s['loan_recovered']<=.2 and s['external_debt']==.2
    assert law(1.,.166644466,.333288932,1.)==(2.,.166644466,0.)
    s=entity('IFC',.6,1,1,.1,0,0,0,0,0,0,1,-.1)
    r=step_entity(s,1,-.1,0,0,0,1,deposit=0)
    assert r['profit']==-.1 and r['cash_tax']==0 and r['reserve_addition']==0
    s=entity('Indonesia',.505,1,1,1,.19,0,0,0,0,0,1,.4)
    r=step_entity(s,1,.4,0,0,0,1,deposit=0)
    assert abs(s['reserve']-.2)<1e-10 and abs(r['reserve_addition']-.01)<1e-10
    s=entity('old_rights',.6,1,1,0,0,0,0,0,0,0,1,.1);s['payable']=.2;s['equity_other']-=.2;s['own']=.9
    r=step_entity(s,1,.1,0,0,0,1,deposit=0)
    assert abs(r['parent_gross_paid']-.2955)<1e-10 and abs(r['nci_gross_paid']-.0995)<1e-10
    s=entity('earnings_override',1.,1,1,0,0,0,0,0,0,0,1,.9)
    r=step_entity(s,1,.9,0,0,0,1,deposit=0,operating_ebit_override=.2)
    assert abs(r['profit']-.15)<1e-10 and abs(s['cash']-.88)<1e-10
    return dict(independent_earnings_entry_override=True,prior_declared_dividend_rights=True,parent_registered_not_premium=True,foreign_reserve=True,no_loss_cash_tax_refund=True,loss_offset=True,reserve=True,same_chain_literal=True,declared_vs_cash=True,historical_cost=True,nci_and_loans=True)

def main():
    configs={
      'base':dict(), 'core_low':dict(discount=.10),'core_high':dict(discount=.08),
      'auxiliary':dict(method='earnings'),'weaker_operating':dict(method='aux'),'cyclical':dict(case='cyclical'),
      'structural':dict(case='structural'),'upside':dict(case='upside')}
    stressconfigs={
      'raw_material_margin_minus_1pct':dict(cost_shock=.01),
      'subs_RE_half':dict(re_scale=.5), 'parent_RE_minus_0_5bn':dict(parent_re_shift=-.5),
      'remittance_lag_50pct':dict(lag=.5), 'minority_ownership_plus_5pct':dict(nci_shift=.05),
      'parent_cash_minus_0_8bn':dict(cash_shift=-.8),
      'JV_effective_own_low':dict(jv_own=.49995),'JV_effective_own_high':dict(jv_own=.50995),
      'employee_subscription_half_cost':dict(employee_cash_fraction=.5),
      'employee_SBC_150pct':dict(sbc_scale=1.5),
      'Xinliuwu_refinance_refusal_Y4':dict(refinance_refusal=True),
      'unused_treasury_cancellation':dict(treasury_cancel=True),
      'lower_tier_NCI_high_cash_share':dict(lower_nci_high=True),
      'lower_tier_NCI_low_cash_share':dict(lower_nci_low=True),
      'Dingweitai_lower_tier_NCI_high_cash_share':dict(dwt_nci_high=True),
      'earnings_anchor_FY2024':dict(method='earnings',earnings_anchor=(EARNINGS['group24']-EARNINGS['group25'])/2+EARNINGS['dwt_partial_removed']),
      'earnings_anchor_FY2025':dict(method='earnings',earnings_anchor=(EARNINGS['group25']-EARNINGS['group24'])/2-EARNINGS['dwt_partial_removed'])}
    cases={k:run(**v) for k,v in configs.items()}
    sensitivities={k:run(**v) for k,v in stressconfigs.items()}
    convergence_all={k:[run(years=n,**v) for n in ([60,100,200,400,600] if v.get('method')=='earnings' else [60,100,200])] for k,v in dict(configs,**stressconfigs).items()}
    # base alias retained for readable table building; full rows are present for every path above.
    convergence=convergence_all['base']
    print(json.dumps(dict(schema='anjoy_entity_owner_cash_v1',as_of=ASOF,units='CNY billion except per-share CNY',independent_earnings_basis=EARNINGS,shares_billion=SHARES,tests=tests(),cases=cases,sensitivities=sensitivities,convergence=convergence,convergence_all=convergence_all),ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False))
if __name__=='__main__':main()
