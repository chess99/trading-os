#!/usr/bin/env python3
"""Yifeng, CNY billion, billions of shares. Independent inputs in source; no I/O inputs.
Conditional pro-rata capital returns track surviving investor units; value/RI are per original held share.
Projected annual anniversary periods 2026-10-29 to 2027-10-29 etc.
2026-09-30 balances rolled to cutoff ONLY for disclosed 10.346m treasury purchase;
unreported October operations assumed net zero, with explicit alternative bridge.
"""
import json, math, sys
from decimal import Decimal, ROUND_HALF_UP

def cents(value):
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

def issue_adjust(price, old_shares, added_shares, issue_price):
    old=Decimal(str(old_shares)); new=Decimal(str(added_shares))
    return cents((Decimal(str(price))*old+Decimal(str(issue_price))*new)/(old+new))

def dividend_adjust(price, cash, total_shares):
    return cents(Decimal(str(price))-Decimal(str(cash))/Decimal(str(total_shares)))
ASOF='2026-10-29T12:00:00+00:00'

def appropriation(re, reserve, profit, ceiling):
    # Losses consume retained earnings before reserve; never create reserve on deficit repair.
    positive_after_loss=max(0.0, profit+min(0.0,re))
    add=min(max(0.0,ceiling-reserve),0.1*positive_after_loss)
    return re+profit-add, reserve+add, add

def cash_waterfall(cash, floor, retained, requested):
    paid=max(0.0,min(requested,cash-floor,retained))
    return cash-paid,retained-paid,paid

def simulate(p, years=320, hand=False):
    if hand:
        # The same legal appropriation and payment functions used in every forecast year.
        re,rs,add=appropriation(-2.,1.,12.,5.)
        cash,re,d=cash_waterfall(20.,3.,re,20.)
        return {'cash':cash,'retained':re,'reserve':rs,'dividend':d,'reserve_added':add}
    original=dict(p)
    r=p.get('discount',.095); kind=p.get('kind','stores'); nm=p.get('name','base')
    # Actual combined monetary/trading/debt/other-financial assets; October disclosed repurchase.
    liquid=4.30827464718+5.24037359208+.17309747146+.002564-.010346
    parent=5.539654+p.get('parent_bridge_shift',0); minority=p.get('nci_initial_cash',.5); subs=liquid-parent-minority
    face=1.797232; bond=1.68434541821; option=.16187669421
    accrued_coupon=.01042 # Sep current coupon budget, H1 disclosed .00593289866, rolled 3 months
    lease=1.36402558072+1.03130705921-accrued_coupon
    rou=2.65054355145; fixed=1.55781106283+.07927902011+.45302989690+.03454856242+.32366032629
    goodwill=4.77930767981
    common_eq=12.02020226778-option-.010346; nci_eq=.83238487296
    # Initial operating net assets inferred from audited balance identity, not a cash plug each year.
    # Other net nonfinancial assets include inventories/receivables less supplier, payroll,tax and deferred balances.
    nwc=common_eq+option+nci_eq+bond+lease+accrued_coupon-liquid-fixed-goodwill-rou
    start_nwc=nwc
    unpaid_issue_fee=.0001 # H1 special report outstanding 0.10m, conservative cutoff carry; no new expense.
    parent_re=.44045346379-(1.208135186*.30)+.06
    parent_res=.41383962117; sub_re=6.67795436160-parent_re
    sub_res=.8; nci_re=.30; nci_res=.08
    divrec=.85640940830; intercompany=2.162387228
    investment_cost=2.650765330
    shares=1.212392486; treasury=.0046573
    # Parent H1 paid-in capital + capital premium, net actual cutoff treasury cost.
    # Excludes statutory reserves, retained profit and the separate CB equity component.
    parent_contributed=1.212392486+3.64854574959-.10676769626
    holder_units=1.
    treasury_cost=.10676769626 # Sept IFRS cost + Oct disclosed purchase, fee difference retained
    retailstores=10761.; franchise=4691.; cohorts=[]
    unit=0.00208; funit=.000545; other=.73; prevrev=24.6
    parent_trade_nwc=1.10-3.10-1.50
    parent_bills=3.10; parent_payables=1.50 # Sep bridge budget, not disclosed parent Q3 figures
    total_bills=5.30076380226; total_payables=2.50415992804
    collateral=1.243496184; proceeds_principal=1.2639947
    # H1 official special report: cumulative interest11.8416m less bank fees0.0025m and digital-project interest used0.4033m.
    # Already included in opening financial assets/equity: restrict, never add again.
    proceeds_income=p.get('opening_restricted_income',.0114358)
    qualified_budget=1.1274906+.1365041
    qualified_completion_year=0
    proceeds=proceeds_principal+proceeds_income
    grant_shares=.0102011; grant_strike=11.34; convprice=31.14
    common_pv=0.; rows=[]; last_div=0.; feasible=True; breach=None
    initial_book=common_eq/(shares-treasury); previous_book=initial_book; residual_pv=initial_book; accumulated_dps=0.
    allerr=0.; largest_eqerr=0.; first_common_eq=common_eq
    # Forecast explicit retail economics independent of earnings entry.
    for y in range(1,years+1):
        p={} if original.get('base_first_five') and y<=5 else original
        opening_holder_units=holder_units;opening_parent_contributed=parent_contributed
        opening_conversion_price=convprice
        opening_restricted_principal=proceeds_principal;opening_restricted_income=proceeds_income
        opening_qualified_budget=qualified_budget
        opening={'parent_cash':parent,'subsidiary_common_cash':subs,'nci_cash':minority,
                 'ordinary_equity':common_eq,'nci_equity':nci_eq,'bond':bond,'lease':lease,
                 'rou':rou,'fixed':fixed,'nwc':nwc,'goodwill':goodwill,'option_equity':option,
                 'accrued_coupon':accrued_coupon,'shares':shares,'treasury':treasury,'parent_re':parent_re,'sub_re':sub_re}
        grow=max(0.,1-(y-1)/15.)
        inflation=1.015**(y-1)
        # Store maturation: first year 30%, second 75%, then mature; closed stores lose all sales.
        opened=p.get('opens',380)*min(1.,2*grow)
        closed=160*grow
        acquired=36 if y==1 else 0
        retailstores-=closed
        cohorts=[(n,age+1) for n,age in cohorts]
        cohorts.append((opened+acquired,0))
        mature_eq=retailstores+sum(n*.95*([.30,.75,1.][min(age,2)]) for n,age in cohorts)
        physical=retailstores+sum(n for n,age in cohorts)
        if y>1: unit*=1.015+p.get('same_store_extra',.005)*grow
        franchise*=1+.065*grow
        funit*=1.015 if y>1 else 1
        other*=1.015 if y>1 else 1
        retail=mature_eq*unit; franch=franchise*funit
        gm=p.get('retail_margin',.409)-.014*min((y-1)/15.,1.)+p.get('margin_shock',0)*(1 if (y>=2 and (not p.get('cyclical') or y<=3)) else 0)
        fg=.12
        staff=(physical+.05*sum(n for n,age in cohorts))*.000357*inflation*(1+.004*min(y-1,15))
        rent=physical*.000126*inflation
        othercost=(retail+franch)*.054 +other*.40
        new_retail=sum(n*.95*([.30,.75,1.][min(age,2)]) for n,age in cohorts)*unit
        gross=retail*gm-new_retail*.01+franch*fg+other*.70
        if kind=='earnings':
            # Independent entry: normalized sales and post-rent/pre-depreciation margin,
            # no store revenue, gross-margin or payroll output used to set profit.
            revenue=25.10*(1+p.get('sales_growth',.04))**min(y-1,5)
            if y>6: revenue*=1.015**(y-6)
            ebitda=revenue*(p.get('earnings_cash_margin',.125)-.009*min((y-1)/15.,1.))
            ebitda+=revenue*p.get('margin_shock',0)*(1 if (y>=2 and (not p.get('cyclical') or y<=3)) else 0)
            rent=revenue*.054
            # Same approved capital programme, independent sales/margin outcome; no sales inferred from store count.
            physical=retailstores+sum(n for n,age in cohorts)
            retail=franch=staff=othercost=gross=None
        else:
            revenue=retail+franch+other; ebitda=gross-staff-othercost-rent
        # Permanent maintenance covers both replacement of short-life fit-outs and acquired intangibles.
        maintenance=revenue*p.get('maintenance_ratio',.012)
        expansion=opened*.00032943*inflation
        build_commissioned=expansion
        warehouse=min(.1365041, .1365041 if y==1 else 0.)
        if p.get('accelerate') and y==1:
            # Pay remaining promised construction, but assets mature only as stores open in later years.
            expansion=1.1274906
        elif p.get('accelerate') and y>1:
            use=min(prepaid_build,expansion); prepaid_build-=use; expansion-=use
        if y==1: prepaid_build=max(0,expansion-opened*.00032943*inflation)
        capex=maintenance+expansion+warehouse
        depreciation=fixed/7.5
        # ROU / lease renewals continue in every tail year. Cash rent includes principal, interest, property and uncapitalized occupancy items (not asserted short-lease disclosure).
        principal=lease/2.
        lease_interest=.04*lease
        short_rent=max(0.,rent-principal-lease_interest)
        rent_cash=principal+lease_interest+short_rent
        rou_da=rou/2.
        lease_add=max(0.,1.75*rent-(lease-principal))
        lease=lease-principal+lease_add; rou=rou-rou_da+lease_add
        ebit=ebitda+rent-rent_cash+principal+lease_interest-rou_da-depreciation
        # Closing cash operating WC scales with gross operating size; excess payer days and supplier contraction explicit.
        # Remove the separately identified old issue-fee payable from scalable operating NWC.
        # Its payment is an existing-liability settlement, not earnings or investment yield.
        issue_fee_paid=unpaid_issue_fee;unpaid_issue_fee=0.
        target_nwc=(start_nwc+.0001)*revenue/24.6
        target_nwc+=sum(n*(1. if age==0 else .5 if age==1 else 0.) for n,age in cohorts)*.00014931*inflation
        if p.get('payer_days',0) and (not p.get('cyclical') or y<=3): target_nwc+=revenue*p['payer_days']/365.*.60
        if p.get('supplier_cut',0) and (not p.get('cyclical') or y<=3): target_nwc+=p['supplier_cut']*inflation
        dnw=target_nwc-nwc; nwc=target_nwc
        fixed+=maintenance+build_commissioned+warehouse-depreciation
        acquisition=.01765 if y==1 else 0.
        goodwill+=acquisition
        fee=(.0005 if y==1 else 0.)+closed*.00002*inflation
        supplier_reduction=p.get('supplier_cut',0)*inflation if (not p.get('cyclical') or y<=3) else 0.
        bill_fee=.003*max(0.,5.30076380226*revenue/24.6-supplier_reduction)
        # All financial principal earns a conservative yield; no added net cash valuation outside this waterfall.
        fin_parent=max(0,parent)*.015; fin_sub=max(0,subs)*.015; fin_nci=max(0,minority)*.015
        restricted_gross_income=proceeds*.015
        restricted_income_tax=restricted_gross_income*.25
        # Tax paid within total parent tax/cash calculation; retain the NET yield, not a second profit.
        proceeds_income+=restricted_gross_income-restricted_income_tax
        coupon=face*([.01,.015,.018,0.][y-1]) if y<=4 else 0.
        debt_accretion=(face*1.10-1.68434541821)/4 if y<=4 else 0.
        old_accrued=accrued_coupon;accrued_coupon=0.
        interest=coupon-old_accrued+debt_accretion
        bond+=debt_accretion
        sbc=[.0590192166667,.0246917,.0030111833333,0.][min(y-1,3)] # total after-tax disclosure .0867221; use pretax equivalent below
        if y==3 and not p.get('full_vest'): sbc-=.04336105 # reversal of second 50% service award on nonmarket performance failure
        sbc_pretax=sbc/.75
        # Operating NCI ratio from 9M NP excludes financing borne by listed parent.
        op_aftertax=(ebit-lease_interest-fee)*.75
        nci_np=op_aftertax*.105+fin_nci*.75
        parent_own_np=op_aftertax*.06+(fin_parent-interest-bill_fee)*.75-sbc
        sub_np=op_aftertax*.835+fin_sub*.75
        common_np=parent_own_np+sub_np
        total_np=common_np+nci_np
        noncash=depreciation+rou_da
        operating_cf=op_aftertax+noncash-principal-capex-dnw-acquisition
        # Parent pays 6% operating cash needs, common subs 83.5%, NCI 10.5%.
        parent_cf=operating_cf*.06+(fin_parent-coupon-bill_fee)*.75+debt_accretion*.25-old_accrued*.25
        sub_cf=operating_cf*.835+fin_sub*.75
        nci_cf=operating_cf*.105+fin_nci*.75
        # The NWC release includes fee payment; issuer parent, not NCI, bears its whole cash.
        parent_cf-=.94*issue_fee_paid;sub_cf+=.835*issue_fee_paid;nci_cf+=.105*issue_fee_paid
        parent+=parent_cf;subs+=sub_cf;minority+=nci_cf
        # Expensed share compensation credits capital reserve; grant receipts, repurchase and dilution separate.
        repurchase=grant_cash=grant_refund=0.;newshares=cancelled_shares=0.
        if y==1:
            repurchase=.2-.1067571
            bought=repurchase/30.56 # disclosed authorization cap, not a spot-price forecast
            treasury+=bought; treasury_cost+=repurchase;parent-=repurchase
            if p.get('all_new_grant'): newshares=grant_shares
            else:
                used=min(treasury,grant_shares); treasury-=used;newshares=grant_shares-used
                treasury_cost=0. if treasury==0 else treasury_cost*treasury/(treasury+used)
            convprice=issue_adjust(convprice,shares,newshares,grant_strike)
            shares+=newshares; grant_cash=grant_shares*grant_strike;parent+=grant_cash
        conversion_price_after_issue=convprice
        if y==3 and not p.get('full_vest'):
            cancelled_shares=grant_shares*.5
            grant_refund=cancelled_shares*(grant_strike*(1+.015*2)-accumulated_dps)
            shares-=cancelled_shares;parent-=grant_refund
            # Prospectus p25/body24 gives fair-holder-protection principle, NO inverse formula.
            # Unchanged price is a CONDITIONAL future-announcement assumption, not a legal rule.
            # Additional downward protective adjustment is a separate explicit sensitivity.
            convprice=cents(convprice*(1-p.get('cancellation_price_haircut',0)))
        conversion_price_after_cancellation=convprice
        conversion_price_used=convprice if y==4 and p.get('convert') else 0.
        redeemed=converted=0.;option_transfer=0.
        if y==4:
            if p.get('convert'):
                converted=face/convprice;shares+=converted
                option_transfer=option;option=0.;bond_transfer=bond;bond=0.
            else:
                redeemed=face*1.10;parent-=redeemed;bond-=redeemed
                option_transfer=option;option=0.;bond_transfer=0.
        else: bond_transfer=0.
        # Only actual cash construction WITHIN remaining disclosed project envelope qualifies.
        # No approval to enlarge the build envelope is presumed. Conditional closeout below is explicit.
        eligible_project_spend=min(qualified_budget,expansion+warehouse)
        qualified_budget=max(0.,qualified_budget-eligible_project_spend)
        spent_principal=min(proceeds_principal,eligible_project_spend)
        spent_income=min(proceeds_income,max(0.,eligible_project_spend-spent_principal))
        proceeds_principal-=spent_principal;proceeds_income-=spent_income
        spent_proceeds=spent_principal+spent_income
        if not qualified_completion_year and qualified_budget<=1e-12: qualified_completion_year=y
        released_principal=released_income=0.
        # Forecast CONDITION: after completion, two full annual periods for compliant closeout,
        # required approval and special-account settlement. NOT evidence of current approval.
        # Actual no-approval and longer-delay countercases retain funds and all income each year.
        if qualified_completion_year and y>=qualified_completion_year+p.get('closeout_delay',2) and not p.get('no_closeout'):
            released_principal=proceeds_principal;released_income=proceeds_income
            proceeds_principal=proceeds_income=0.
        proceeds=proceeds_principal+proceeds_income
        total_bills=max(0.,5.30076380226*revenue/24.6-supplier_reduction)
        total_payables=2.50415992804*revenue/24.6
        collateral=total_bills*(1.243496184/5.30076380226)
        parent_bills=3.10*revenue/24.6-.65*supplier_reduction;parent_payables=1.50*revenue/24.6
        # Parent central procurement settles external suppliers; excess funding advanced to common subsidiaries.
        new_parent_trade_nwc=(1.10-3.10-1.50)*revenue/24.6
        if p.get('payer_days',0) and (not p.get('cyclical') or y<=3): new_parent_trade_nwc+=.06*revenue*p['payer_days']/365.*.60
        if p.get('supplier_cut',0) and (not p.get('cyclical') or y<=3): new_parent_trade_nwc+=.65*supplier_reduction
        parent_trade_change=new_parent_trade_nwc-parent_trade_nwc;parent_trade_nwc=new_parent_trade_nwc
        funding_source=.06*dnw-parent_trade_change
        cashpool_advance=max(-intercompany,funding_source)
        intercompany+=cashpool_advance
        parent+=funding_source-cashpool_advance;subs-=funding_source-cashpool_advance
        # Parent RE and subsidiary RE use separate profits; internal declarations are NOT consolidated income.
        # Parent appropriation waits for declared subsidiary profit below.
        sub_re,sub_res,sradd=appropriation(sub_re,sub_res,sub_np,1.5)
        nci_re,nci_res,nradd=appropriation(nci_re,nci_res,nci_np,.20)
        operating_floor=revenue*.04
        parent_floor=operating_floor*.35+collateral*.65+proceeds
        sub_floor=operating_floor*.545+collateral*.30
        nci_floor=operating_floor*.105+collateral*.05
        # Collection of legacy receivables repays balance only. Separate two-year dividend receivable lag and cashpool amortisation.
        delay=p.get('upstream_delay',0)
        collected=min(divrec,max(0.,subs-sub_floor),.45*inflation) if y>delay else 0.
        divrec-=collected;subs-=collected;parent+=collected
        current_repayment=min(intercompany,max(0.,subs-sub_floor),.20*inflation) if y>delay else 0.
        intercompany-=current_repayment;subs-=current_repayment;parent+=current_repayment
        # Declaration budget: recurring profits + finite accumulated distributable reserves; no perpetual legacy draw.
        request=max(0,sub_np)*(.60 if y<=5 else .95)+min((.10 if y<=5 else .20)*inflation,max(0,sub_re-max(0,sub_np)))
        declaration=min(max(0,sub_re),request,max(0.,subs-sub_floor))
        if y<=delay: declaration=0.
        sub_re-=declaration;divrec+=declaration
        # OPTIONAL conditional proportional paid-capital return, not an announced programme.
        # Requires valid shareholder/creditor/registration procedures; no automatic right to distribute reserves.
        capital_return=capital_return_cost=reduction_shares=capital_return_original_dps=0.
        capital_available=parent_contributed-repurchase+grant_cash-grant_refund+sbc+option_transfer+bond_transfer
        if y==p.get('capital_return_year',-1) and p.get('capital_return_fraction',0)>0 and treasury==0 and abs(bond)<1e-12:
            buffer=1.5*inflation;fixed_cost=.001*inflation
            capacity=max(0.,(parent-parent_floor-buffer-fixed_cost)/1.005)
            capital_return=min(capital_available*p['capital_return_fraction'],capacity)
            if capital_return>0:
                q=capital_return/capital_available
                capital_return_original_dps=holder_units*capital_return/(shares-treasury)
                reduction_shares=shares*q;shares-=reduction_shares;holder_units*=1-q
                capital_return_cost=capital_return*.005+fixed_cost
                parent-=capital_return+capital_return_cost
                parent_own_np-=capital_return_cost;common_np-=capital_return_cost;total_np-=capital_return_cost
                parent_cf-=capital_return_cost # Issuer cash expense, no assumed tax credit.
        parent_re,parent_res,pradd=appropriation(parent_re,parent_res,parent_own_np+declaration,.5*shares)
        sameyear=min(divrec,max(0.,subs-sub_floor),declaration*.85)
        divrec-=sameyear;subs-=sameyear;parent+=sameyear
        # Once current profit is declared, pay an ordinary target plus legal/cash-constrained special distribution.
        target=max(0,common_np)*(.62 if y<=5 else .85)
        special=max(0,parent-parent_floor-1.5*inflation)*.30 if y>5 else 0.
        parent,parent_re,dividend=cash_waterfall(parent,parent_floor,parent_re,target+special)
        minority,nci_re,nci_div=cash_waterfall(minority,nci_floor,nci_re,max(0,nci_np)*(.60 if y<=5 else .90)+max(0,minority-nci_floor-.3*inflation)*.30)
        eligible=shares-treasury
        dps=dividend/eligible
        conversion_dividend_per_total_share=dividend/shares if y<4 else 0.
        convprice=dividend_adjust(convprice,dividend,shares) if y<4 else convprice
        holder_ordinary_dps=holder_units*dps
        holder_cash_distribution=holder_ordinary_dps+capital_return_original_dps
        pv=holder_cash_distribution/(1+r)**y;common_pv+=pv;accumulated_dps+=dps
        # Capital roll-forwards include noncash compensation credit and derivative-equity transfer.
        common_eq+=common_np-dividend-repurchase+grant_cash-grant_refund+sbc+option_transfer+bond_transfer-capital_return
        parent_contributed=capital_available-capital_return
        parent_ordinary_equity=parent_contributed+parent_re+parent_res
        # Diagnostic attribution identity, NOT an annual cash plug or valuation input.
        parent_net_other_external_liabilities=parent+investment_cost+divrec+intercompany-bond-option-parent_ordinary_equity
        nci_eq+=nci_np-nci_div
        endingliq=parent+subs+minority
        cash_expected=(opening['parent_cash']+opening['subsidiary_common_cash']+opening['nci_cash']+
                       parent_cf+sub_cf+nci_cf-repurchase+grant_cash-grant_refund-redeemed-dividend-nci_div-capital_return)
        cash_err=endingliq-cash_expected
        assets_net=fixed+prepaid_build+goodwill+rou+nwc+endingliq
        eq_err=assets_net-bond-lease-accrued_coupon-common_eq-option-nci_eq
        allerr=max(allerr,abs(cash_err));largest_eqerr=max(largest_eqerr,abs(eq_err))
        failed=min(parent-parent_floor,subs-sub_floor,minority-nci_floor)<-1e-8
        if failed and feasible:
            feasible=False;breach={'year':y,'parent_shortfall':min(0,parent-parent_floor),'subs_shortfall':min(0,subs-sub_floor),'nci_shortfall':min(0,minority-nci_floor)}
        book=common_eq/eligible*holder_units
        residual_income_per_share=book-previous_book+holder_cash_distribution-r*previous_book
        residual_pv+=residual_income_per_share/(1+r)**y
        previous_book=book
        row={'parent_contributed_capital_net':parent_contributed,'parent_paid_in_capital':shares,
             'parent_capital_reserve_net_treasury':parent_contributed-shares,'parent_ordinary_book_equity':parent_ordinary_equity,
             'parent_other_net_external_liabilities':parent_net_other_external_liabilities,
             'parent_other_operating_net_assets':parent_bills+parent_payables-parent_net_other_external_liabilities,
             'holder_units_opening':opening_holder_units,'holder_units_remaining':holder_units,
             'capital_return_cash':capital_return,'capital_return_cost':capital_return_cost,'capital_reduction_shares':reduction_shares,
             'capital_return_per_original_share':capital_return_original_dps,'ordinary_dividend_per_original_share':holder_ordinary_dps,
             'holder_distribution_per_original_share':holder_cash_distribution,'book_value_per_share':book,'residual_income_per_share':residual_income_per_share,'year':y,'ending_date':str(2026+y)+'-10-29','revenue':revenue,'owned_store_equivalents':mature_eq,
             'owned_physical_stores':physical,'franchise_stores':franchise,'new_stores':opened,'closed_stores':closed,
             'retail_revenue':retail,'franchise_revenue':franch,'retail_gross_margin':gm if kind=='stores' else None,
             'staff_cash':staff,'cash_rent':rent_cash,'ebitda_after_rent':ebitda,'ebit':ebit,'financial_income':fin_parent+fin_sub+fin_nci,
             'common_net_profit':common_np,'minority_net_profit':nci_np,'depreciation':depreciation,'rou_depreciation':rou_da,
             'maintenance_capex':maintenance,'growth_capex':expansion,'warehouse_capex':warehouse,'acquisition':acquisition,
             'prepaid_construction_asset':prepaid_build,'commissioned_growth_build':build_commissioned,'fixed_net_assets':fixed,'goodwill':goodwill,'net_working_capital':nwc,'working_capital_investment':dnw,
             'lease_interest':lease_interest,'lease_principal_paid':principal,'lease_renewal_additions':lease_add,'lease_liability':lease,'rou_asset':rou,
             'accrued_bond_coupon':accrued_coupon,'bond_face':face if y<4 else 0.,'bond_carrying':bond,'bond_coupon':coupon,'bond_accretion':debt_accretion,
             'supplier_bill_finance_fee':bill_fee,'closure_and_acquisition_cost':fee,'bond_redemption':redeemed,'bond_converted_new_shares':converted,'conversion_price':convprice,'bond_equity_component':option,
             'financial_liquid_total':endingliq,'collateral_restricted':collateral,'unspent_restricted_proceeds':proceeds,
             'restricted_opening_principal':opening_restricted_principal,'restricted_opening_income':opening_restricted_income,
             'restricted_gross_income':restricted_gross_income,'restricted_income_tax':restricted_income_tax,
             'restricted_principal_spent':spent_principal,'restricted_income_spent':spent_income,
             'restricted_principal_balance':proceeds_principal,'restricted_income_balance':proceeds_income,
             'qualified_project_budget_opening':opening_qualified_budget,'qualified_project_cash_spend':eligible_project_spend,
             'qualified_project_budget_remaining':qualified_budget,'restricted_total_cash_used':spent_proceeds,
             'project_completion_year':qualified_completion_year,'restricted_principal_released':released_principal,'restricted_income_released':released_income,
             'issue_fee_liability_paid':issue_fee_paid,'unpaid_issue_fee_liability':unpaid_issue_fee,
             'conversion_price_opening':opening_conversion_price,'conversion_price_after_issue':conversion_price_after_issue,
             'conversion_price_after_cancellation':conversion_price_after_cancellation,'conversion_dividend_per_total_share':conversion_dividend_per_total_share,
             'conversion_price_used':conversion_price_used,'new_issued_grant_shares':newshares,
             'total_supplier_bills':total_bills,'total_supplier_payables':total_payables,
             'parent_cash':parent,'common_subs_cash':subs,'minority_cash':minority,'parent_floor':parent_floor,'subs_floor':sub_floor,'nci_floor':nci_floor,
             'parent_bills_budget':parent_bills,'parent_supplier_payables_budget':parent_payables,
             'parent_own_profit':parent_own_np,'sub_common_profit':sub_np,'parent_retained':parent_re,'parent_reserve':parent_res,
             'subs_retained':sub_re,'subs_reserve':sub_res,'nci_retained':nci_re,'nci_reserve':nci_res,
             'parent_dividend_receivable':divrec,'legacy_and_prior_dividend_collected':collected,'new_dividend_declared':declaration,'new_dividend_cash_received':sameyear,
             'parent_trade_net_working_capital':parent_trade_nwc,'new_cashpool_advance':cashpool_advance,'parent_external_procurement_cash_adjustment':funding_source,'intercompany_receivable':intercompany,'intercompany_cash_repayment':current_repayment,'parent_investment_cost':investment_cost,
             'investment_exit_proceeds':0.,'investment_exit_tax':0.,'investment_exit_cost':0.,
             'ordinary_book_equity':common_eq,'minority_book_equity':nci_eq,'repurchase_cash':repurchase,'grant_cash':grant_cash,
             'grant_failure_refund':grant_refund,'cancelled_grant_shares':cancelled_shares,'sbc_net_expense':sbc,'issued_shares':shares,'treasury_shares':treasury,'treasury_cost':treasury_cost,'eligible_shares':eligible,
             'ordinary_cash_dividend':dividend,'nci_cash_dividend':nci_div,'dividend_per_share':dps,'present_value_per_share':pv,
             'parent_operating_and_financing_cf':parent_cf,'subs_operating_cf':sub_cf,'minority_operating_cf':nci_cf,
             'cash_conservation_error':cash_err,'equity_conservation_error':eq_err,'financing_feasible_this_year':not failed}
        rows.append(row);lastphysical=physical;prevrev=revenue;last_div=dps
        if failed: break # No negative-cash continuation or valuation beyond a financing failure.
    y5=sum(x['holder_distribution_per_original_share']/(1+r)**(x['year']-5) for x in rows[5:])
    return {'name':nm,'kind':kind,'parameters':original,'years':years,'value_per_share':common_pv if feasible else None,
            'unfunded_path_has_no_value':not feasible,'year5_continuation_per_share':y5 if feasible else None,
            'five_dividends_per_share':[x['dividend_per_share'] for x in rows[:5]],'year5plus_pv_share':y5/(1+r)**5/common_pv if common_pv else None,
            'residual_income_value_per_share':residual_pv if feasible else None,'book_terminal_present_value':book/(1+r)**len(rows),'last_20_years_pv':sum(x['present_value_per_share'] for x in rows[-20:]),'financing_feasible':feasible,'first_financing_breach':breach,
            'max_cash_error':allerr,'max_equity_error':largest_eqerr,'annual_states':rows}

def main():
    cases=[{'name':'core_low','retail_margin':.405,'same_store_extra':.002,'opens':320,'discount':.10},
           {'name':'base'},
           {'name':'core_high','retail_margin':.413,'same_store_extra':.008,'opens':440,'discount':.09},
           {'name':'earnings_low','kind':'earnings','earnings_cash_margin':.120,'sales_growth':.03,'discount':.10},
           {'name':'earnings_high','kind':'earnings','earnings_cash_margin':.130,'sales_growth':.05,'discount':.09},
           {'name':'q3_margin_persists','retail_margin':.399},
           {'name':'permanent_margin_loss','margin_shock':-.025},
           {'name':'payer_delay_supplier_cut','payer_days':60,'supplier_cut':1.0},
           {'name':'upstream_three_year_delay','upstream_delay':3},
           {'name':'accelerated_promised_build','accelerate':True},
           {'name':'closeout_delay_five_years','closeout_delay':5},
           {'name':'no_approved_closeout','no_closeout':True},
           {'name':'capital_return_10pct_y12','capital_return_fraction':.10,'capital_return_year':12},
           {'name':'capital_return_20pct_y12','capital_return_fraction':.20,'capital_return_year':12},
           {'name':'capital_return_20pct_y20','capital_return_fraction':.20,'capital_return_year':20},
           {'name':'conditional_conversion','convert':True},
           {'name':'conversion_protective_cut','convert':True,'cancellation_price_haircut':.02},
           {'name':'all_new_conditional_conversion','convert':True,'all_new_grant':True},
           {'name':'all_new_grant','all_new_grant':True},
           {'name':'maintenance_1_8pct','maintenance_ratio':.018},
           {'name':'cyclical_recovery','cyclical':True,'margin_shock':-.015,'payer_days':45},
           {'name':'full_vest_conditional','full_vest':True},
           {'name':'holder_y5_low','base_first_five':True,'retail_margin':.405,'same_store_extra':.002,'opens':320,'discount':.10},
           {'name':'holder_y5_high','base_first_five':True,'retail_margin':.413,'same_store_extra':.008,'opens':440,'discount':.09},
           {'name':'parent_cash_bridge_low','parent_bridge_shift':-.70},
           {'name':'parent_cash_bridge_high','parent_bridge_shift':.70},
           {'name':'nci_cash_low','nci_initial_cash':.3},
           {'name':'nci_cash_high','nci_initial_cash':.7},
           {'name':'financing_failure_120days','payer_days':120,'supplier_cut':3.0}]
    out={'as_of':ASOF,'currency':'CNY','units':'billion CNY, billion shares; per-share CNY','hand_case':simulate({},hand=True),
         'results':[simulate(p) for p in cases], 'long_tail_extension':simulate({'name':'base_extension'},years=640),
         'tail_extensions':[simulate(dict(params,name=label+'_extension_'+str(h)),years=h)
             for label,params,hs in [('base',{},[960]),('structural',{'margin_shock':-.025},[640,960]),('upstream',{'upstream_delay':3},[640,960]),('restricted',{'no_closeout':True},[640,960]),('capital',{'capital_return_fraction':.20,'capital_return_year':12},[640,960])] for h in hs]}
    json.dump(out,sys.stdout,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False);sys.stdout.write('\n')
if __name__=='__main__': main()
