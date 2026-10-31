#!/usr/bin/env python3
"""Standalone deterministic economic budget; stdlib only, no input files.
Not purported undisclosed legal accounts. Unit billion CNY and billion shares.
Full annual balance sheets, allocations and all requested paths are output.
"""
import json,copy,math
CUT='2026-10-29T11:00:00+00:00'
A=98.68203736429; L=49.74992139575; CASH=19.21190767011
DEBT=.24487449584+1.06777927482+11.58608254076+.17478168994
FIN=.52552460511+.15129656104+.53344107178
INV=33.89908952192; AR=66.45610178359-CASH-INV
FIXED=7.52119374903+.48338811408+.21843773676+.04990739253+.22038872999+.08900811380
TECH=9.90127101975+8.82947832103
AP=18.01900096249+3.58651654426; CONTRACT=5.30124093394; GRANT=6.41100794633
LEGACY_DIV=.22155319142
DTA_NET=1.31709840187; DTL_NET=.45396645739; TAX_OFFSET=.09715811236
DTA_GROSS=DTA_NET+TAX_OFFSET; DTL_GROSS=DTL_NET+TAX_OFFSET
OTHERL=L-DEBT-AP-CONTRACT-GRANT-LEGACY_DIV-DTL_NET; OTHERA=0.; GW=2.38550176393
PCASH=7.40568491089-.553; PDEBT=9.0809613011
LOAN=2.08666303101; ICOST=19.27118668501; ACQ=.4045607
SHARES=.727953799
NCI=6.13892128961
POOL=(CASH-PCASH)+(A-CASH-FIN)-(L-DEBT-LEGACY_DIV)-(DEBT-PDEBT)
KING_EQ=9.35183578135-3.84326285462
HC_EQ=2.38651611476
WK=KING_EQ/POOL; WH=HC_EQ/POOL; WO=5./POOL; WM=1-WK-WH-WO
OTHER_OWN=1-(NCI-KING_EQ*.8216-HC_EQ*.2884)/5.

def close(a,b,label):
    if abs(a-b)>2e-7*max(1,abs(a),abs(b)):raise AssertionError((label,a,b))

def equity(u):
    return sum(u[k] for k in ('cash','ar','inventory','fixed','tech','other_asset','goodwill','deferred_tax_asset'))-sum(u[k] for k in ('ap','contract','other_liabilities','grant','debt','loan','dividend_payable','deferred_tax_liability'))

# H1 gross groups and their underlying differences, independently copied from
# S2 pp114-115. Q3 group allocation and utilization horizons are economic budgets.
DTA_GROUPS=[('impairment',.14523663829,.94679099950,5),('internal_profit',.11878030289,.91296030060,3),('loss',.33340513661,2.14635703301,5),('share_awards',.62187034373,4.02530874379,4),('grant',.01190287188,.07869565762,15),('lease',.09570856947,.59556031303,8),('other',.08481867063,.55696698948,5)]
DTL_OTHER=[('depreciation',.00407045778,.02739445308),('lease',.08852422941,.48331820669),('other',.00001389135,.00008339030)]
def tax_opening(weight,ppa_dtl,tech,purchased):
    groups=[]
    for name,credit,diff,horizon in DTA_GROUPS:
        value=DTA_GROSS*weight*credit/1.41172253350
        difference=value*diff/credit
        groups.append(dict(name=name,original_difference=difference,remaining_difference=difference,eligible_difference=0.,unrecognized_difference=0.,balance=value,horizon=horizon,expiry_year_budget=10 if name=='loss' else None))
    liabilities=[]
    for name,credit,diff in DTL_OTHER:
        value=DTL_GROSS*weight*credit/.55583215452
        difference=value*diff/credit
        liabilities.append(dict(name=name,original_difference=difference,remaining_difference=difference,balance=value))
    difference=ppa_dtl/.15
    return dict(deductible=groups,taxable=liabilities,ppa_book=difference,ppa_tax_basis=0.,ppa_dtl=ppa_dtl,ordinary_technology_tax_basis=tech-difference,rd_additional_basis=max(0,tech-purchased)*.5,unrecognized_losses=[])

def tax_bridge(u,old,t,case,pretax,impair,sbc,caprd,rdcash,am):
    ledger=u['tax_ledger']; previous_dta=old['deferred_tax_asset'];previous_dtl=old['deferred_tax_liability']
    rate=.25 if case=='tax_stress' else .15
    ppa_rate=.15 if case=='ppa_short_life' else .09
    ppa_am=old['tax_ledger']['ppa_book']*ppa_rate
    ordinary_tax_am=old['tax_ledger']['ordinary_technology_tax_basis']*.09
    other_reversal=0.
    for b in ledger['taxable']:
        reversal=min(b['remaining_difference'],b['original_difference']/8)
        b['remaining_difference']-=reversal;b['balance']=b['remaining_difference']*rate
        other_reversal+=reversal
    ppa_impair=old['tax_ledger']['ppa_book']*.20 if impair else 0.
    ledger['ppa_book']-=ppa_am+ppa_impair;ledger['ppa_dtl']=(ledger['ppa_book']-ledger['ppa_tax_basis'])*rate
    ledger['ordinary_technology_tax_basis']+=caprd-ordinary_tax_am
    eligibility=0. if case=='rd_tax_none' else 1. if case=='rd_tax_full' else .5
    # Extra R&D deduction is cash tax relief, not a second R&D cash payment.
    # The opening pool is always half the non-purchased technology; scenario
    # eligibility scales its amortization as well as prospective additions.
    extra_am=old['tax_ledger']['rd_additional_basis']*.09
    extra_deduction=eligibility*(rdcash-caprd)+extra_am*(eligibility/.5)
    ledger['rd_additional_basis']+=caprd*.5-extra_am
    # Book impairment and SBC do not create a tax deduction by assumption.
    # Book amortization is replaced with ordinary tax-basis amortization;
    # PPA book amortization has no tax basis and is not silently deductible.
    taxable_before_rights=pretax+impair+sbc+am-ordinary_tax_am+other_reversal-extra_deduction
    capacity=max(0.,taxable_before_rights);used=written_off=recognized_loss_expired=0.
    for b in ledger['deductible']:
        expiry=5 if case=='loss_expiry_short' and b['name']=='loss' else b['expiry_year_budget']
        if expiry is not None and t>expiry:
            recognized_loss_expired+=b['remaining_difference'];written_off+=b['balance']
            b['remaining_difference']=b['eligible_difference']=b['unrecognized_difference']=b['balance']=0.
            continue
        horizon=b['horizon']*(2 if case=='tax_asset_delay' else 1)
        b['eligible_difference']=min(b['remaining_difference'],b['eligible_difference']+b['original_difference']/horizon)
        if case=='tax_asset_unusable':
            written_off+=b['balance'];b['remaining_difference']=b['eligible_difference']=b['unrecognized_difference']=0.;b['balance']=0.
            continue
        take=min(capacity,b['eligible_difference']);capacity-=take;used+=take
        b['eligible_difference']-=take;b['remaining_difference']-=take
        # After finite forecast review, remaining rights are not presumed to vanish:
        # unrecognized memorandum rights can still offset future positive income.
        review=30 if case=='tax_asset_delay' else 15
        if t>=review:
            b['unrecognized_difference']=b['remaining_difference'];b['balance']=0.
        else:b['balance']=b['remaining_difference']*rate
    expired_losses=loss_used=0.;new_losses=[]
    for vintage in ledger['unrecognized_losses']:
        if t>vintage['expiry_year']:
            expired_losses+=vintage['difference'];continue
        use=min(capacity,vintage['difference']);capacity-=use;loss_used+=use
        vintage['difference']-=use
        if vintage['difference']>1e-14:new_losses.append(vintage)
    if taxable_before_rights<0:new_losses.append(dict(origin_year=t,expiry_year=t+(5 if case=='loss_expiry_short' else 10),difference=-taxable_before_rights))
    ledger['unrecognized_losses']=new_losses
    cash_tax=capacity*rate
    u['deferred_tax_asset']=sum(b['balance'] for b in ledger['deductible'])
    u['deferred_tax_liability']=ledger['ppa_dtl']+sum(b['balance'] for b in ledger['taxable'])
    deferred=previous_dta-u['deferred_tax_asset']+u['deferred_tax_liability']-previous_dtl
    expense=cash_tax+deferred
    close(expense-cash_tax,previous_dta-u['deferred_tax_asset']+u['deferred_tax_liability']-previous_dtl,'deferred_tax_bridge')
    close(ledger['ppa_dtl'],(ledger['ppa_book']-ledger['ppa_tax_basis'])*rate,'PPA_tax_base')
    close(taxable_before_rights,pretax+impair+sbc+am-ordinary_tax_am+other_reversal-extra_deduction,'book_to_tax')
    close(cash_tax,rate*max(0.,taxable_before_rights-used-loss_used),'cash_tax_capacity')
    return dict(cash_tax=cash_tax,current_tax_expense=cash_tax,deferred_tax_expense=deferred,income_tax_expense=expense,ordinary_technology_tax_amortization=ordinary_tax_am,ppa_book_amortization=ppa_am,ppa_tax_amortization=0.,ppa_book_impairment=ppa_impair,other_taxable_difference_reversal=other_reversal,rd_additional_deduction=extra_deduction,taxable_before_existing_rights=taxable_before_rights,existing_deductible_difference_used=used,unrecognized_loss_used=loss_used,unrecognized_loss_expired=expired_losses,tax_asset_disallowed=written_off,recognized_loss_difference_expired=recognized_loss_expired,forecast_tax_rate=rate)

def initial():
    units=[]
    for name,w,own,rev,mar in [('micro',WM,1.,38.,.17),('kingsemi',WK,.1784,2.,.12),('huacheng',WH,.7116,1.5,.13),('other',WO,OTHER_OWN,3.5,.08)]:
        u=dict(name=name,weight=w,ownership=own,revenue=rev,margin=mar,cash=(CASH-PCASH)*w,ar=AR*w,inventory=INV*w,fixed=FIXED*w,tech=TECH*w,other_asset=OTHERA*w,deferred_tax_asset=DTA_GROSS*w,deferred_tax_liability=DTL_GROSS*w,goodwill=GW*w,ap=AP*w,contract=CONTRACT*w,other_liabilities=OTHERL*w,grant=GRANT*w,debt=(DEBT-PDEBT)*w,loan=LOAN if name=='micro' else 0.,dividend_payable=0.)
        u['restricted_cash']=1.1963546 if name=='micro' else 0.
        u['reserve_capital']={'micro':1.14153708311,'kingsemi':.201766496,'huacheng':.020905844,'other':.5}[name]
        u['initial_debt']=u['debt'];u['initial_revenue']=rev
        u['opening_ratios']={k:u[k]/rev for k in ('ar','inventory','ap','contract','other_liabilities')}
        u['initial_grant']=u['grant'];u['initial_other_asset']=u['other_asset']
        u['retained']=equity(u)*.35;u['reserve']=0.;u['paid_capital']=equity(u)-u['retained']
        units.append(u)
    # Chinese purchase accounting uses parent-attributable goodwill. Keep it wholly
    # in the owned investment chain, never allocate it to 82.16% minority holders.
    for j in (1,2,3):
        g=units[j]['goodwill'];units[j]['goodwill']=0.;units[0]['goodwill']+=g
        units[j]['cash']+=g;units[0]['cash']-=g
    # Economic PPA budget: Kingsemi technology 4bn implies .36bn annual amortization,
    # near H1 purchase-accounting vs native profit difference, not disclosed Q3 detail.
    shift=4.-units[1]['tech']
    units[1]['tech']+=shift;units[1]['inventory']-=shift
    units[0]['tech']-=shift;units[0]['inventory']+=shift
    ppa_total=DTL_GROSS*(.46322357598/.55583215452)
    for u in units:
        target=ppa_total if u['name']=='kingsemi' else 0.
        move=target-ppa_total*u['weight']
        u['deferred_tax_liability']+=move;u['cash']+=move
        u['tax_ledger']=tax_opening(u['weight'],target,u['tech'],4. if u['name']=='kingsemi' else 0.)
        u['opening_ratios']={k:u[k]/u['revenue'] for k in ('ar','inventory','ap','contract','other_liabilities')}
        close(equity(u),u['retained']+u['paid_capital'],'allocation_preserves_equity')
    # Newly acquired assets cost+goodwill, paid by buyer through parent economic pool.
    u=dict(name='bonding',weight=0.,ownership=1.,revenue=0.,margin=0.,cash=.02,ar=.0142776,inventory=.025,fixed=.020,tech=.225,other_asset=.0072393,deferred_tax_asset=0.,deferred_tax_liability=0.,goodwill=ACQ-.3107059,ap=.000811,contract=0.,other_liabilities=0.,grant=0.,debt=0.,loan=0.,dividend_payable=0.)
    # The asset mix is an economic allocation, sum equals published net assets + cost premium.
    close(equity(u),ACQ,'acquisition_net_assets')
    u.update(restricted_cash=0.,reserve_capital=.35,initial_debt=0.,initial_revenue=0.,opening_ratios=dict(ar=.25,inventory=.6,ap=.3,contract=.1,other_liabilities=.05),initial_grant=0.,initial_other_asset=.0072393,retained=-.0392941,reserve=0.,paid_capital=ACQ+.0392941)
    u['tax_ledger']=tax_opening(0.,0.,u['tech'],u['tech'])
    units.append(u)
    p=dict(legacy_external_dividend_payable=LEGACY_DIV,cash=PCASH,debt=PDEBT,loan_face=LOAN,loan_allowance=0.,investment_cost=ICOST+ACQ,acquisition_payable=ACQ,dividend_receivable=0.,financial_other=FIN-.25,fund_nav=.25,fund_cost=.25,fund_unpaid=.26,retained=.01688247406-.06,reserve=.25601352096,shares=SHARES,paid_capital=0.)
    p['paid_capital']=pequity(p)-p['retained']-p['reserve']
    return units,p

def pequity(p):
    return p['cash']+p['loan_face']-p['loan_allowance']+p['investment_cost']+p['dividend_receivable']+p['financial_other']+p['fund_nav']-p['debt']-p['acquisition_payable']-p['legacy_external_dividend_payable']

def reserve_profit(retained,reserve,profit,cap):
    repaired=max(0,profit+min(retained,0))
    add=min(max(0,.5*cap-reserve),.1*repaired)
    return retained+profit-add,reserve+add,add

def growth(name,t,case):
    starts={'micro':[.14,.13,.11,.09,.07],'kingsemi':[.18,.20,.18,.16,.12],'huacheng':[.12,.12,.10,.08,.06],'other':[.06,.06,.05,.04,.04]}
    g=starts[name][t-1] if t<=5 else (.06-(t-6)*.008 if t<=10 else .02)
    if case=='structural':g=max(.0,g-.04) if t<=10 else .01
    if case=='cycle':g= -.05 if t==1 else (0. if t==2 else (.20 if t==3 else g))
    if case=='upside' and t<=8:g+=.025
    return g

def exercise(t,case,prior_dividends=0.):
    # End-Q3 to 10/23 actual issue: cash receipt estimated at 116.23, separately disclosed.
    # Future 2022 remaining balance estimated after observed shares; 2024 actual remaining grant.
    # 2025 high-strike grants: no automatic exercise; paired exercise sensitivity separately.
    n22=[.004,.002787992,0,0][t-1] if t<=4 else 0
    n24=[.002952170,.002960702,.002960702,.002960502][t-1] if t<=4 else 0
    n25=.010403050/4 if 2<=t<=5 and case=='all_options' else 0.
    q=n22+n24+n25
    # Official 2026-07-22 adjustment: P1=P0-V. Do not invent a zero-price floor.
    # All studied exercised awards remain >100 CNY; reject out-of-domain floor cases.
    def receipts(n,strike):
        if not n:return 0.
        adjusted=strike-prior_dividends
        if adjusted<=1:raise ValueError('Plan-specific floor requires separate verification')
        return n*adjusted
    proceeds=receipts(n22,115.5)+receipts(n24,139.63)+receipts(n25,234.98)
    return q,proceeds

def run(case='base',method='revenue',years=80,rate=.10):
    units,p=initial(); rows=[]; cumulative_dividends=0.; pv=0.; minority_pv=0.; failure=None
    # Actual post-Q3 share count already incorporated. Cash estimate only for actually issued increment.
    post_cash=.000168707*116.23;p['cash']+=post_cash;p['paid_capital']+=post_cash
    if case=='fund_full_call':
        # Unknown previously paid amount is reclassified from other financial assets, not destroyed.
        p['financial_other']+=p['fund_nav'];p['fund_nav']=0.;p['fund_cost']=0.;p['fund_unpaid']=.51
    if case=='fund_delay':exit_year=9
    else:exit_year=6
    fund_vintages=[(.25, -2)] if case!='fund_full_call' else []
    opening=dict(units=copy.deepcopy(units),parent=copy.deepcopy(p))
    for t in range(1,years+2):
        before=copy.deepcopy(p);aggregate={k:0. for k in ('declared','received','minority_declared','minority_paid','loan_repaid','sub_sbc','sub_ni','external_debt_repayment','operating_cash_generation')};out=[]
        for u in units:
            old=copy.deepcopy(u);n=u['name'];w=u['weight'];own=u['ownership']
            if n=='bonding':
                rev=[.05,.10,.18,.25,.35][t-1] if t<=5 else u['revenue']*(1.08 if t<=10 else .02+1)
                mar=[-.15,-.05,.05,.10,.14][t-1] if t<=5 else .16
                if case=='structural':rev*=.7;mar-=.04
            else:
                rev=u['revenue']*(1+growth(n,t,case))
                if method=='capital':
                    cg=[.10,.09,.08,.07,.06][t-1] if t<=5 else (.045 if t<=10 else .02)
                    rev=u['revenue']*(1+cg)
                mar=u['margin']+min(t,5)*(.001 if n!='kingsemi' else .005)
            if case=='structural' and n!='bonding':mar-=.025
            if case=='cycle' and t<=2:mar-=.015
            if case=='upside':mar+=.01
            if case=='margin_down':mar-=.02
            if case=='rd_failure' and t>=3:mar-=.02
            fraction=min(t/5,1.)
            targets=dict(ar=.24,inventory=.66,ap=.38,contract=.115,other_liabilities=.07)
            for key in targets:
                ratio=(1-fraction)*u['opening_ratios'][key]+fraction*targets[key]
                if key=='inventory' and (case=='structural' or (case=='cycle' and t<=2)):ratio+=.10
                if key=='ap' and case=='supplier_payment':ratio-=.10
                u[key]=rev*ratio
            oldwc=old['ar']+old['inventory']-old['ap']-old['contract']-old['other_liabilities']
            wc=u['ar']+u['inventory']-u['ap']-u['contract']-u['other_liabilities'];dwc=wc-oldwc
            caprd=rev*.065;rdcash=rev*(.165 if n=='micro' else .18)
            dep=old['fixed']*.065;ppa_rate=.15 if case=='ppa_short_life' else .09
            am=(old['tech']-old['tax_ledger']['ppa_book'])*.09+old['tax_ledger']['ppa_book']*ppa_rate;capex=rev*.025
            impair=old['tech']*.20 if case=='rd_failure' and t==3 else 0.
            otheram=min(old['other_asset'],u['initial_other_asset']/10)
            grel=min(old['grant'],u['initial_grant']/15)
            sbc=.02*w if t<=4 else 0.
            cash_ebitda=rev*mar
            # Independent capital entry: sustainable operating return on beginning capital,
            # not a restatement of primary revenue margins. Growth follows retained capital budgets.
            if method=='capital':
                oldic=oldwc+old['fixed']+old['tech']+old['other_asset']+old['goodwill']
                roic={'micro':.17,'kingsemi':.10,'huacheng':.125,'other':.09,'bonding':.02}[n]
                if n=='bonding':roic=min(.14,.02+.02*(t-1))
                if t>10:roic=max(.10,roic-(min(t-10,10))*.004)
                if case=='structural':roic-=.035
                # cash EBITDA reconstructed from independently chosen capital earnings.
                cash_ebitda=oldic*roic/.85+dep+am+otheram-caprd-grel+sbc
            int_rate=.055 if case=='rate_stress' else .035
            interest=old['debt']*int_rate;cashyield=old['cash']*.004
            pretax=cash_ebitda+caprd-dep-am-otheram+grel-sbc-interest+cashyield-impair
            taxflows=tax_bridge(u,old,t,case,pretax,impair,sbc,caprd,rdcash,am)
            tax=taxflows['cash_tax'];ni=pretax-taxflows['income_tax_expense']
            fcf=cash_ebitda-tax-interest+cashyield-capex-dwc
            u['cash']+=fcf
            injection=max(0,rev*.05-u['cash']) if own==1. else 0.
            if injection:
                u['cash']+=injection;u['paid_capital']+=injection;p['cash']-=injection;p['investment_cost']+=injection
            u['fixed']+=capex-dep;u['tech']+=caprd-am-impair;u['other_asset']-=otheram;u['grant']-=grel
            u['tax_ledger']['ordinary_technology_book']=u['tech']-u['tax_ledger']['ppa_book']
            u['tax_ledger']['ordinary_technology_unrecognized_deductible_difference']=u['tax_ledger']['ordinary_technology_tax_basis']-u['tax_ledger']['ordinary_technology_book']
            u['revenue']=rev
            u['paid_capital']+=sbc
            u['retained'],u['reserve'],radd=reserve_profit(u['retained'],u['reserve'],ni,u['reserve_capital'])
            # Previously declared dividend is an existing payable, never a new expense.
            paid_old=u['dividend_payable'];u['cash']-=paid_old;u['dividend_payable']=0.
            restricted_use=min(u['restricted_cash'],1.1963546/4,capex)
            u['restricted_cash']-=restricted_use
            floor=rev*.05+u['restricted_cash']
            repayment=min(u['debt'],u['initial_debt']/8,max(0,u['cash']-floor))
            u['cash']-=repayment;u['debt']-=repayment
            loanrep=min(u['loan'],LOAN/5,max(0,u['cash']-floor)) if n=='micro' else 0.
            u['cash']-=loanrep;u['loan']-=loanrep
            surplus=max(0,u['cash']-floor)
            dividend_budget=max(0,ni)*(.35 if t<=5 else .60 if t<=10 else 1.)
            if t>10:dividend_budget=max(dividend_budget,surplus*.20)
            declare=min(max(0,u['retained']),surplus,dividend_budget)
            if case=='upstream_delay' and t<=3:declare*=.5
            paid_new=.8*declare
            u['cash']-=paid_new;u['dividend_payable']=declare-paid_new;u['retained']-=declare
            if u['cash'] < -1e-8:
                failure=dict(year=t,entity=n,negative_cash=u['cash']);break
            close(equity(u),u['paid_capital']+u['reserve']+u['retained'],'unit_bs '+n)
            close(u['cash'],old['cash']+fcf+injection-paid_old-repayment-loanrep-paid_new,'unit_cash '+n)
            close(u['retained']+u['reserve'],old['retained']+old['reserve']+ni-declare,'unit_profit '+n)
            aggregate['declared']+=declare*own;aggregate['received']+=(paid_new+paid_old)*own
            aggregate['minority_declared']+=declare*(1-own);aggregate['minority_paid']+=(paid_new+paid_old)*(1-own)
            aggregate['loan_repaid']+=loanrep;aggregate['sub_sbc']+=sbc;aggregate['sub_ni']+=ni;aggregate['external_debt_repayment']+=repayment;aggregate['operating_cash_generation']+=fcf
            flows=dict(restricted_cash_used_for_included_capex=restricted_use,technology_impairment=impair,equity_injection=injection,revenue=rev,rd_cash_budget=rdcash,rd_capitalized=caprd,rd_cash_expensed=rdcash-caprd,depreciation=dep,technology_amortization=am,other_asset_amortization=otheram,old_grant_release=grel,share_expense=sbc,cash_ebitda=cash_ebitda,interest=interest,cash_interest=cashyield,tax=tax,net_income=ni,working_capital=wc,delta_working_capital=dwc,physical_capex=capex,pre_financing_cash_generation=fcf,external_principal_paid=repayment,scheduled_principal_rolled=max(0,min(old['debt'],u['initial_debt']/8)-repayment),intercompany_principal_paid=loanrep,reserve_addition=radd,dividend_declared=declare,dividend_paid=paid_old+paid_new,minority_dividend=(paid_old+paid_new)*(1-own),parent_dividend=(paid_old+paid_new)*own)
            flows.update(taxflows);flows['pretax_income']=pretax
            out.append(dict(balance=copy.deepcopy(u),flows=flows))
        if failure:break
        p['dividend_receivable']+=aggregate['declared']-aggregate['received']
        p['loan_face']-=aggregate['loan_repaid']
        p['cash']+=aggregate['received']+aggregate['loan_repaid']
        call=min(p['fund_unpaid'],(.51 if case=='fund_full_call' else .26)/2) if t<=2 else 0.
        p['fund_unpaid']-=call;p['fund_nav']+=call;p['fund_cost']+=call;p['cash']-=call
        if call:fund_vintages.append((call,t))
        fgain=p['fund_nav']*.06 if t<=exit_year else 0.
        fee=p['fund_cost']*.02 if t<=exit_year else 0.
        p['fund_nav']+=fgain-fee
        fproceeds=fgross=carry=exitcost=ftax=realized=principal=0.
        if t==exit_year:
            fgross=p['fund_nav'];exitcost=.02*fgross
            prof=max(0,fgross-exitcost-p['fund_cost'])
            hurdle=sum(v*.08*max(0,t-b) for v,b in fund_vintages)
            # Exact 20/80 catchup after LP's simple hurdle, capped at 20% total profit.
            carry=fund_carry(prof,hurdle)
            fproceeds=fgross-exitcost-carry
            realized=fproceeds-p['fund_cost'];ftax=max(0,realized)*.25
            principal=p['fund_cost'];p['cash']+=fproceeds-ftax;p['fund_nav']=0.;p['fund_cost']=0.
        fy=p['financial_other']*.03;fy_tax=fy*.25;p['cash']+=fy-fy_tax
        othercost=p['financial_other'] if t==8 else 0.
        othergross=othercost*(.70 if case=='investment_haircut' else 1.)
        otherexitfee=.02*othergross
        otherprincipal=othergross-otherexitfee
        otherexitprofit=otherprincipal-othercost
        otherexittax=max(0,otherexitprofit)*.25
        p['cash']+=otherprincipal-otherexittax;p['financial_other']-=othercost
        cashyield=before['cash']*.004;ir=.055 if case=='rate_stress' else .035
        interest=before['debt']*ir;admin=.08*1.02**(t-1)
        p['cash']+=cashyield-interest-admin
        # NAV return already accrued in past profit; exit reverses opening NAV and records sale proceeds.
        fin_profit=fgain-fee
        if t==exit_year:fin_profit+=fproceeds-fgross-ftax
        ni=aggregate['declared']+cashyield-interest-admin+fy-fy_tax+fin_profit+otherexitprofit-otherexittax
        p['retained'],p['reserve'],radd=reserve_profit(p['retained'],p['reserve'],ni,p['shares'])
        acqpay=ACQ*(.95 if t==1 else .05 if t==2 else 0)
        p['acquisition_payable']-=acqpay;p['cash']-=acqpay
        legacy_paid=p['legacy_external_dividend_payable'];p['cash']-=legacy_paid;p['legacy_external_dividend_payable']=0.
        debtpay=min(p['debt'],PDEBT/10,max(0,p['cash']-.5))
        p['debt']-=debtpay;p['cash']-=debtpay
        dq,proceeds=exercise(t,case,cumulative_dividends);p['shares']+=dq;p['cash']+=proceeds;p['paid_capital']+=proceeds
        policy=.25 if t<=5 else .6 if t<=10 else 1.
        desired=max(0,ni)*policy if t<=10 else max(0,p['cash']-.5)
        div=min(desired,max(0,p['retained']),max(0,p['cash']-.5))
        p['cash']-=div;p['retained']-=div
        if p['cash'] < -1e-8:
            failure=dict(year=t,entity='parent_economic_pool',negative_cash=p['cash']);break
        close(pequity(p),p['retained']+p['reserve']+p['paid_capital'],'parent_bs')
        close(p['dividend_receivable'],sum(u['dividend_payable']*u['ownership'] for u in units),'dividend_receivable')
        close(p['loan_face'],sum(u['loan'] for u in units),'intercompany_face')
        close(p['retained']+p['reserve'],before['retained']+before['reserve']+ni-div,'parent_profit')
        minority=sum(equity(u)*(1-u['ownership']) for u in units)
        own_equity=pequity(p)+sum(equity(u)*u['ownership'] for u in units)-p['investment_cost']
        total_equity=own_equity+minority
        dps=div/p['shares'];cumulative_dividends+=dps
        row=dict(year=t,units=out,parent=dict(balance=copy.deepcopy(p),flows=dict(legacy_external_dividend_paid=legacy_paid,net_income=ni,dividend_declared_from_subs=aggregate['declared'],dividend_cash_from_subs=aggregate['received'],intercompany_principal_received=aggregate['loan_repaid'],fund_call=call,fund_gross_return=fgain,fund_fee=fee,fund_sale_gross=fgross,fund_sale_cost=exitcost,fund_carry=carry,fund_exit_tax=ftax,fund_sale_proceeds=fproceeds,fund_principal_return=principal,fund_realized_profit=realized,other_financial_income=fy,other_financial_tax=fy_tax,other_financial_cost_released=othercost,other_financial_sale_gross=othergross,other_financial_exit_fee=otherexitfee,other_financial_exit_gain=otherexitprofit,other_financial_exit_tax=otherexittax,other_financial_principal=otherprincipal,cash_interest=cashyield,debt_interest=interest,administration=admin,acquisition_payment=acqpay,debt_principal=debtpay,scheduled_debt_rolled=max(0,min(before['debt'],PDEBT/10)-debtpay),option_new_shares=dq,option_proceeds=proceeds,reserve_addition=radd,ordinary_dividend=div,dividend_per_share=dps)),consolidation=dict(common_equity=own_equity,minority_equity=minority,total_equity=total_equity,minority_dividends=aggregate['minority_paid'],cash=sum(u['cash'] for u in units)+p['cash'],external_debt=sum(u['debt'] for u in units)+p['debt'],external_loan_face=0.,intercompany_eliminated_face=p['loan_face'],dividend_elimination=p['dividend_receivable']))
        if rows:
            prev=rows[-1]['consolidation'];previous_minority=prev['minority_equity']
        else:
            previous_minority=sum(equity(u)*(1-u['ownership']) for u in opening['units'])
        minority_ni=sum(x['flows']['net_income']*(1-x['balance']['ownership']) for x in out)
        minority_sbc=sum(x['flows']['share_expense']*(1-x['balance']['ownership']) for x in out)
        close(minority,previous_minority+minority_ni+minority_sbc-aggregate['minority_declared'],'minority_equity_roll')
        group_ni=ni+aggregate['sub_ni']-aggregate['declared']
        if rows:previous_total=rows[-1]['consolidation']['total_equity']
        else:previous_total=pequity(opening['parent'])+sum(equity(u) for u in opening['units'])-opening['parent']['investment_cost']
        close(total_equity,previous_total+group_ni+aggregate['sub_sbc']+proceeds-div-aggregate['minority_declared'],'consolidated_equity_roll')
        row['consolidation']['net_income']=group_ni
        gdta=sum(u['deferred_tax_asset'] for u in units);gdtl=sum(u['deferred_tax_liability'] for u in units);offset=min(TAX_OFFSET,gdta,gdtl)
        row['consolidation'].update(deferred_tax_assets_gross=gdta,deferred_tax_liabilities_gross=gdtl,tax_presentation_offset_budget=offset,deferred_tax_assets_net=gdta-offset,deferred_tax_liabilities_net=gdtl-offset,cash_operating_income_tax=sum(x['flows']['cash_tax'] for x in out),deferred_operating_income_tax=sum(x['flows']['deferred_tax_expense'] for x in out))
        rows.append(row)
        if t<=years:pv+=dps/(1+rate)**t;minority_pv+=aggregate['minority_paid']/(1+rate)**t
    if failure:return dict(case=case,method=method,rate=rate,years=years,feasible=False,failure=failure,opening=opening,annual_states=rows,value_per_share=None)
    # Continuing business, not liquidation. Required capital, supplier payables and R&D
    # keep growing; terminal economic equity is the PV of actual future distributions.
    g=.01 if case=='structural' else .02
    continuation=rows[-1]['parent']['flows']['dividend_per_share']/(rate-g)
    terminal_pv=continuation/(1+rate)**years
    value=cash_present_value([x['parent']['flows']['dividend_per_share'] for x in rows[:years]],continuation,rate)
    close(value,pv+terminal_pv,'valuation_chain')
    y5=sum(x['parent']['flows']['dividend_per_share']/(1+rate)**(x['year']-5) for x in rows if 5<x['year']<=years)+continuation/(1+rate)**(years-5)
    return dict(case=case,method=method,rate=rate,years=years,feasible=True,opening=opening,annual_states=rows,explicit_dividend_pv=pv,continuation_at_horizon=continuation,continuation_pv=terminal_pv,value_per_share=value,year5_value_per_share=y5,first5_distributions=[x['parent']['flows']['dividend_per_share'] for x in rows[:5]],minority_dividend_pv=minority_pv,continuation_growth=g)

def fund_carry(profit,hurdle):
    return min(.2*max(0,profit),max(0,profit-hurdle))

def cash_present_value(ds, terminal, rate):
    return sum(d/(1+rate)**(i+1) for i,d in enumerate(ds))+terminal/(1+rate)**len(ds)

def main():
    jobs=[('base','revenue',80,r) for r in (.095,.10,.105)]+[('base','capital',80,.10)]+[(c,'revenue',80,.10) for c in ('cycle','structural','upside','supplier_payment','upstream_delay','rate_stress','all_options','fund_full_call','fund_delay','rd_failure','margin_down','tax_stress','investment_haircut','tax_asset_delay','tax_asset_unusable','ppa_short_life','rd_tax_none','rd_tax_full','loss_expiry_short')]+[('base','revenue',120,r) for r in (.095,.10,.105)]
    results=[run(*a) for a in jobs]
    out=dict(schema_version=1,information_cutoff=CUT,units='billion_CNY_and_billion_shares',accounting_scope='economic consolidated and parent/operating-unit budgets, not undisclosed legal accounts',sources=dict(total_assets=A,total_liabilities=L,consolidated_cash=CASH,debt_including_leases=DEBT,financial_assets=FIN,operating_capital=A-CASH-FIN-DTA_NET-(L-DEBT-DTL_NET),deferred_tax_asset_net=DTA_NET,deferred_tax_liability_net=DTL_NET,deferred_tax_offset_budget=TAX_OFFSET,ar_other_operating_current=AR,fixed_operating_assets=FIXED,technology_assets=TECH,other_operating_liabilities=OTHERL),runs=results)
    print(json.dumps(out,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False))
if __name__=='__main__':main()
