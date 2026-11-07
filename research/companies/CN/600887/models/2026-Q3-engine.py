#!/usr/bin/env python3
"""Yili common-equity cash budget, self-contained standard library only.
Money CNY billion. Not an audit of future statutory entity distributions.
"""
import json,math,sys,copy
SHARES=6.323560467
CASES=[('base',0,.0825,63.4,'base',1,False),('low',-.003,.085,62.5,'base',1,False),('high',.003,.08,64.,'base',1,False),('aux',0,.0825,63.4,'base',2,False),('cycle',0,.0825,63.4,'cycle',1,False),('structural',0,.095,62.5,'structural',1,False),('optimistic',0,.08,64.,'optimistic',1,False),('margin_minus_1pct',-.01,.0825,63.4,'base',1,False),('upstream_delay',0,.0825,63.4,'upstream_delay',1,False),('slow_treasury',0,.0825,63.4,'slow_treasury',1,False),('holder_low',-.003,.085,63.4,'base',1,True),('holder_high',.003,.08,63.4,'base',1,True)]

CASES += [(k,0,.0825,63.4,k,1,False) for k in ['wc_tight','wc_loose','wc_5yr','wc_10yr','contract_outflow','contract_loss','channel_credit_stress','legacy_positive_wc']+['put_'+str(a)+'_'+str(b) for a in [0,50,100] for b in [0,1]]]

def distribution(re,profit,reserve,ceiling,cash,floor,ratio=1.):
    # Retained earnings first absorb the old loss; reserve only new unabsorbed profit.
    restored=max(profit-max(-re,0.),0.)
    transfer=min(restored*.1,max(ceiling-reserve,0.))
    legal=re+profit-transfer
    dividend=max(0.,min(max(legal,0.),max(cash-floor,0.)*ratio))
    return legal-dividend,reserve+transfer,dividend,transfer

def debt_run(balance,annual_reduction,not_due=0.):
    maturity=max(0.,balance-not_due)
    redemption=min(balance,annual_reduction,maturity)
    refinancing=maturity-redemption
    return balance-redemption,redemption,maturity,refinancing

def tax_cycle(earnings,rate,dta,annual_use,dtl,annual_release,expire=False):
    current=max(earnings,0.)*rate
    shield=min(dta,annual_use,current)
    after=dta-shield
    expiry=after if expire else 0.
    after-=expiry
    release=min(dtl,annual_release)
    cash=current-shield
    expense=cash+shield+expiry-release
    return after,dtl-release,cash,expense,shield,release,expiry

def dispose(book,basis,fee,taxrate):
    gross=book;cost=gross*fee;receipt=gross-cost
    taxable_gain=max(receipt-basis,0.)
    cash_tax=taxable_gain*taxrate
    return receipt,cash_tax,receipt-book,cost,taxable_gain

def operation(revenue,volume,year,delta,kind,method):
    fade=min(1.,max(0.,(year-5)/15.))
    rates=[.115-.015*fade+delta,.155-.025*fade+delta,.15-.03*fade+delta,.02-.01*fade+delta]
    total=sum(revenue)
    if method==1:profit=sum(x*y for x,y in zip(revenue,rates))
    else:profit=sum(x*y for x,y in zip(volume,[1.35,15.,2.7]))-6.5*total/120.-.015*total*fade+delta*total
    if kind=='structural':profit=total*.065
    if kind=='cycle' and year<=3:profit-=total*(.025,.02,.01)[year-1]
    if kind=='optimistic':profit+=total*.01
    return profit,rates

def capital_budget(revenue,previous,year,kind):
    depreciation=.035*revenue
    growth=max(revenue-previous,0.)*(.3 if year<=5 else .6)
    extra=revenue*(.006 if kind=='structural' else .002)
    old=.77607085129 if year==1 else 0.
    return depreciation,growth,extra,old,depreciation+growth+extra+old

def working_cycle(initial,previous,revenue,year,period,target,other_initial,other_previous,shock=False):
    weight=min(year/period,1.)
    rates=[.08,.03,.015,.001,.126-.05-target,.05]
    if shock=='contract_outflow' and year<=3:rates[5]=[.02,0.,.02][year-1]
    if shock=='contract_loss':rates[5]=0.
    if shock=='channel_credit_stress':rates[1]=.06;rates[4]=.10;rates[5]=0.
    # Actual opening amounts are smoothly replaced by normal turnover ratios.
    closing=[revenue*((1-weight)*v/120.+weight*r) for v,r in zip(initial,rates)]
    other=other_initial*revenue/120.
    delta=sum(closing[:4])-sum(closing[4:])+other-(sum(previous[:4])-sum(previous[4:])+other_previous)
    purchases=.64*revenue+closing[0]-previous[0]
    supplier_cash=purchases+closing[2]-previous[2]+previous[4]-closing[4]
    receipts=revenue-(closing[1]+closing[3]-previous[1]-previous[3])+closing[5]-previous[5]
    return closing,other,delta,purchases,supplier_cash,receipts

def tax_settlement(assessed,opening,lag):
    closing=assessed*lag
    return closing,assessed+opening-closing

def external_funding(balance,opening,period):
    interest=balance*.0125
    paid=min(balance,opening/period)
    return balance-paid,interest,paid

def put_event(kind,year,cost):
    if not kind.startswith('put_'):return 0.,0.,0.,0.,cost,0.
    fraction=int(kind.split('_')[1])/100
    purchase=.062*7.5068 if year==10 else 0.
    if purchase:cost=purchase
    gross=.062*7.5068*fraction if year==15 else 0.
    fee=.02*gross;cash=gross-fee
    gain=cash-cost if year==15 else 0.
    if year==15:cost=0.
    return purchase,cash,fee,gain,cost,max(gain,0.)*.25

def forecast(spec,years=600):
    name,delta,discount,deposit,kind,method,future=spec
    cash=[15.02080895391,1.79353445993,.822946]
    RE=[33.53168094531,10.,-2.2164052];reserve=[3.200065459,2.,0.]
    tax_assets=[.41800809029,1.02846755746,.57098877798]
    tax_liabs=[.0274889456,.27242348129,.56469646491]
    debt=[11.117669,53.3277371];deposits=[deposit-3.4,3.4]
    locked=3.09489854216;loan=6.4;badface=.11934545017
    investment=4.64094265052;taxbasis=4.;associate=5.39054815052;assoc_earn=.36
    ic_pay=61.52646965108;ic_deposit=6.;shares=SHARES;capital=40.
    member_opening=1.6 if name=='low' else (1.1 if name=='high' else 1.34234840366)
    member=member_opening;guarantee=.16964679105+.01188925065
    opening_trade=[8.67620448080,3.69636998901,2.13311223009,.01680943356+.07849023523,7.61427873599+12.57064091712-.77607085129,5.10778864867]
    trade=opening_trade.copy()
    nonfinancial_other_payable=3.24257716739-.34737245346-member_opening
    other_opening=.19113862870-3.33452771693-.02263072084-(1.14004926010-.65731800305)-nonfinancial_other_payable-(.80515080354-.16964679105)
    other_wc=other_opening
    tax_due=[.65731800305*x for x in [.66,.31,.03]]
    wc_target=-.05 if name=='low' else (-.07 if name=='high' else -.06)
    if kind=='wc_tight':wc_target=-.04
    if kind=='wc_loose':wc_target=-.08
    if kind=='legacy_positive_wc':wc_target=.04
    transition=5 if kind=='wc_5yr' else (10 if kind=='wc_10yr' else 3)
    wc=sum(trade[:4])-sum(trade[4:])+other_wc
    put_overlap=int(kind.split('_')[2]) if kind.startswith('put_') else 0
    stake_cost=0.
    other_asset_residual=18.56801937603+5.21263921535+46.99953469174-deposit-loan
    capital=32.44154226350+1.04739166950+1.73315364951+.85477197738+4.56540197523+.69974882933+.17293304296+other_asset_residual-2.36644651992
    opening_capital=capital
    assert other_asset_residual>=.32117568356
    assert math.isclose(nonfinancial_other_payable+member+.34737245346,3.24257716739,abs_tol=1e-12)
    assert math.isclose(sum(trade[:4])-sum(trade[4:]),-9.91565108180,abs_tol=1e-11)
    revenues=[74.,33.,10.5,2.5];volumes=[9.,.49,.69]
    output=[]
    for year in range(1,years+1):
        previous_revenue=sum(revenues)
        if year>1:
            growth=([.02,.05,.04,.03] if year<=5 else ([.02]*4 if year<=15 else [.015]*4))
            if kind=='structural':growth=[-.01 if year<=5 else .005]*4
            if kind=='optimistic' and year<=10:growth=[i+.02 for i in growth]
            revenues=[v*(1+g) for v,g in zip(revenues,growth)]
            vg=.025 if year<=5 else (.02 if year<=15 else .015)
            if kind=='structural':vg=-.01 if year<=5 else .005
            if kind=='optimistic' and year<=10:vg+=.02
            volumes=[i*(1+vg) for i in volumes]
        total=sum(revenues)
        localdelta=0. if future and year<=5 else delta
        operating_profit,rates=operation(revenues,volumes,year,localdelta,kind,method)
        depreciation,growth_capex,maintenance_extra,old_construction,capex=capital_budget(total,previous_revenue,year,kind)
        old_trade=trade.copy();old_other=other_wc
        trade,other_wc,working_delta,purchases,supplier_cash,customer_cash=working_cycle(opening_trade,trade,total,year,transition,wc_target,other_opening,other_wc,kind)
        wc+=working_delta
        assert math.isclose(wc,sum(trade[:4])-sum(trade[4:])+other_wc,abs_tol=1e-7)
        assert supplier_cash>=old_trade[4] and customer_cash>=0
        assert math.isclose(old_trade[4]+purchases+trade[2]-old_trade[2]-supplier_cash,trade[4],abs_tol=1e-7)
        capital+=capex-depreciation-old_construction
        restricted_earned=locked*.015
        interest=sum(deposits)*.018+restricted_earned+max(loan,0.)*.035+(cash[0]+cash[1])*.01
        member_interest=member*.0125
        interest_expense=sum(debt)*(.035 if kind=='structural' else .022)+member_interest
        prePPA=operating_profit+interest-interest_expense
        ppa=min(.19720387666,max(0.,2.36644651992-(year-1)*.19720387666))
        actor_earn=[(prePPA+member_interest)*.66,(prePPA+member_interest)*.31-member_interest,(prePPA+member_interest)*.03]
        taxcash=[];taxexpense=[];taxdetail=[]
        for j in range(3):
            z=tax_cycle(actor_earn[j],[.15,.20,.25][j],tax_assets[j],[.041800809029,.102846755746,.114197755596][j],tax_liabs[j],[.00274889456,.027242348129,.0470580387425][j],j==2 and year==5)
            tax_assets[j],tax_liabs[j]=z[:2];taxcash.append(z[2]);taxexpense.append(z[3]);taxdetail.append(z)
        tax_assessed=taxcash.copy();opening_tax_due=tax_due.copy()
        settled=[tax_settlement(x,old,.2) for x,old in zip(tax_assessed,opening_tax_due)]
        tax_due=[z[0] for z in settled];taxcash=[z[1] for z in settled]
        assert all(x>=0 for x in taxcash)
        group_profit=prePPA-ppa-sum(taxexpense)
        netprofit=group_profit-(actor_earn[2]-ppa-taxexpense[2])*.3982
        term=30 if kind=='slow_treasury' else 10
        member,member_interest_check,member_paid=external_funding(member,member_opening,term)
        assert math.isclose(member_interest_check,member_interest,abs_tol=1e-12)
        guarantee_paid=min(guarantee,(.16964679105+.01188925065)/term);guarantee-=guarantee_paid
        matured_deposits=[min(deposits[0],(deposit-3.4)/term) if year<=term else 0.,min(deposits[1],3.4/term) if year<=term else 0.]
        deposits=[a-b for a,b in zip(deposits,matured_deposits)]
        debt_details=[debt_run(debt[j],[11.117669/term,53.3277371/term][j],3.5 if j==0 and year==1 else 0.) for j in range(2)]
        if kind=='funding_failure' and year==1:debt_details=[debt_run(debt[j],debt[j],3.5 if j==0 else 0.) for j in range(2)]
        debt=[x[0] for x in debt_details];repay=[x[1] for x in debt_details]
        loan_repaid=min(loan,.64);loan-=loan_repaid
        released=min(locked,.309489854216) if year<=10 else 0.
        locked-=released
        sale=saletax=sale_book_gain=fees=taxable_exit_gain=0.
        if year==10:
            sale,saletax,sale_book_gain,fees,taxable_exit_gain=dispose(investment,taxbasis,.02,.25)
            investment=0.
        assoc_div=.8*assoc_earn;assoc_profit=assoc_earn
        associate+=assoc_earn-assoc_div;assoc_earn*=1.02 if year<15 else 1.015
        put_purchase,put_receipt,put_fee,put_gain,stake_cost,put_tax=put_event(kind,year,stake_cost)
        profit=[actor_earn[0]-taxexpense[0],actor_earn[1]-taxexpense[1]+assoc_div+sale_book_gain-saletax,actor_earn[2]-ppa-taxexpense[2]+put_gain-put_tax]
        openingcash=sum(cash)
        groupcf=prePPA-sum(taxcash)+depreciation-capex-working_delta
        operating_cash=[actor_earn[j]-taxcash[j]+(depreciation-capex-working_delta)*[.66,.31,.03][j] for j in range(3)]
        cash=[a+b for a,b in zip(cash,operating_cash)]
        cash[0]+=matured_deposits[0]-repay[0]
        cash[1]+=matured_deposits[1]-repay[1]+loan_repaid+released+sale-saletax+assoc_div
        old_dividends=[.34632423249,.00104822097] if year==1 else [0.,0.]
        derivative_settlement=.10622327175-.00066455139-.10622327175*put_overlap if year==1 else 0.
        cash[0]-=old_dividends[0];cash[1]-=old_dividends[1]+derivative_settlement+member_paid+guarantee_paid
        cash[2]+=put_receipt-put_purchase-put_tax
        settlement=max(0.,min(ic_pay-6.,(61.52646965108-6.)/10.)) if year<=10 else (ic_pay if year==11 else 0.)
        cash[0]-=settlement;cash[1]+=settlement;ic_pay-=settlement
        internaldeposit_return=ic_deposit if year==11 else 0.
        cash[1]-=internaldeposit_return;cash[0]+=internaldeposit_return;ic_deposit-=internaldeposit_return
        # overseas, then domestic sub holding layer, then listed payer; no group cash pooling fiction
        RE[2],reserve[2],od,oreserve=distribution(RE[2],profit[2],reserve[2],.5,cash[2],.8,.8)
        cash[2]-=od;minority=od*(1-.6018);to_sub=od*.6018;withholding=to_sub*.05
        cash[1]+=to_sub-withholding
        ratio=.8 if year<=5 else 1.
        if kind=='upstream_delay' and year<=3:ratio=0.
        RE[1],reserve[1],upstream,sreserve=distribution(RE[1],profit[1]+to_sub-withholding,reserve[1],10.,cash[1],1.5*total/120.,ratio)
        cash[1]-=upstream;cash[0]+=upstream
        buyback=.950004992 if year==1 else 0.
        if year==1:shares-=buyback/39.53
        cash[0]-=buyback
        RE[0]+=profit[0]+upstream
        floor=6.*total/120.;target=max(netprofit*.75,0.)
        if year>5:target=max(target,cash[0]-floor)
        div=max(0.,min(target,max(RE[0],0.),max(cash[0]-floor,0.)))
        cash[0]-=div;RE[0]-=div
        actual=sum(cash)
        expected=openingcash+groupcf+sum(matured_deposits)-sum(repay)+loan_repaid+released+sale-saletax+assoc_div-minority-withholding-buyback-div-sum(old_dividends)-derivative_settlement-member_paid-guarantee_paid+put_receipt-put_purchase-put_tax
        assert math.isclose(actual,expected,abs_tol=1e-6,rel_tol=1e-12),(name,year,actual,expected)
        assert min(cash)>-1e-8,(name,year,cash)
        assert min(deposits+debt+tax_assets+tax_liabs)>-1e-8
        assert div<=max(RE[0]+div,0)+1e-8
        assert math.isclose(ic_pay,61.52646965108-sum(z['detail']['internal_settlement'] for z in output)-settlement,abs_tol=1e-8)
        disc=.0825 if future and year<=5 else discount
        row=dict(member_deposits=member,member_interest=member_interest,finance_guarantee_claims=guarantee,corporate_tax_payable=sum(tax_due),acquired_stake_cost=stake_cost,year=year,revenue=total,ebit=operating_profit,net_profit=netprofit,tax_cash=sum(taxcash),tax_expense=sum(taxexpense),ppa=ppa,dta=sum(tax_assets),dtl=sum(tax_liabs),capex=capex,depreciation=depreciation,working_capital=wc,capital=capital,interest=interest,debt_interest=interest_expense,bank_debt=sum(debt),deposits=sum(deposits),restricted=locked,loan_net=loan,unextinguished_bad_face=badface,investment=investment,associate=associate,parent_cash=cash[0],subs_cash=cash[1],overseas_cash=cash[2],parent_RE=RE[0],subs_RE=RE[1],overseas_RE=RE[2],parent_reserve=reserve[0],subs_reserve=reserve[1],overseas_reserve=reserve[2],ic_payable=ic_pay,ic_claim=ic_deposit,subs_dividend=upstream,overseas_dividend=od,minority_cash=minority,buyback=buyback,shares=shares,dividend=div,dps=div/shares,PV=div/(1+disc)**year)
        row['detail']=dict(trade_opening=old_trade,trade_closing=trade,trade_WC=sum(trade[:4])-sum(trade[4:]),other_operating_WC=other_wc,opening_other_operating_WC=old_other,working_cash_investment=working_delta,supplier_purchase_accrual=purchases,supplier_gross_cash_paid=supplier_cash,prior_supplier_face_paid=old_trade[4],new_supplier_face=trade[4],customer_gross_cash_received=customer_cash,prior_contract_fulfilled=old_trade[5],new_contract_advance=trade[5],payroll_liability=(3.33452771693+.02263072084)*total/120.,non_CIT_tax_liability=(1.14004926010-.65731800305)*total/120.,other_operating_payable=nonfinancial_other_payable*total/120.,operating_other_current_liability=(.80515080354-.16964679105)*total/120.,other_operating_receivable=.19113862870*total/120.,income_tax_assessed_after_shields=tax_assessed,income_tax_opening_payable=opening_tax_due,income_tax_closing_payable=tax_due,actual_income_tax_paid=taxcash,external_member_principal_paid=member_paid,external_member_interest=member_interest,external_finance_other_paid=guarantee_paid,external_finance_total_face=sum(debt)+member+guarantee,opening_financial_asset_category_total=70.78019328312,opening_other_asset_residual=other_asset_residual,opening_operating_capital=opening_capital,put_purchase=put_purchase,put_receipt=put_receipt,put_exit_fee=put_fee,put_cash_tax=put_tax,put_entity_gain=put_gain,put_recognised_overlap=.10622327175*put_overlap,put_recognised_liability_carried=.10622327175*put_overlap if year<10 else 0.,group_profit=group_profit,minority_profit=group_profit-netprofit,prior_declared_dividend_settlement=old_dividends,derivative_settlement=derivative_settlement,revenue_by_product=revenues.copy(),margin_by_product=rates,volume_million_tons=volumes.copy(),actor_pretax=actor_earn,actor_profit=profit,actor_cash_flow=operating_cash,tax_ledger=taxdetail,parent_sub_payable_face=ic_pay,sub_parent_receivable_face=ic_pay,parent_finance_deposit_face=ic_deposit,finance_sub_payable_face=ic_deposit,loan_gross_face=loan+badface,loan_loss_allowance=badface,loan_principal_collected=loan_repaid,restricted_interest=restricted_earned,deposit_redemptions=matured_deposits,debt_rollover=debt_details,internal_settlement=settlement,internal_deposit_repayment=internaldeposit_return,withholding_tax=withholding,associate_profit=assoc_profit,associate_dividend=assoc_div,financial_sale_receipt=sale,financial_sale_tax=saletax,financial_sale_gain=sale_book_gain,financial_sale_fee=fees,financial_exit_taxable_gain=taxable_exit_gain,financial_taxbasis=taxbasis if investment else 0.,growth_capex=growth_capex,maintenance_capex=depreciation+maintenance_extra,settlement_opening_construction=old_construction,inventory_budget=trade[0],receivable_budget=trade[1]+trade[3],net_operating_payables_budget=trade[4]+trade[5],retained_ppa_book=max(0.,2.36644651992-year*.19720387666),goodwill_book=.63252020993,subs_reserve_transfer=sreserve,overseas_reserve_transfer=oreserve,group_cash_identity_error=actual-expected)
        output.append(row)
    value=sum(x['dps']/(1+(.0825 if future and x['year']<=5 else discount))**x['year'] for x in output)
    terminal=sum(x['dps']/(1+discount)**(x['year']-5) for x in output[5:])
    tail_bound=abs(output[-1]['dps'])*(1.02)/(discount-.02)/(1+discount)**years
    return dict(name=name,value=value,terminal5=terminal,first5=[x['dps'] for x in output[:5]],states=output,tail_bound=tail_bound,terminal_PV_share=sum(x['dps']/(1+discount)**x['year'] for x in output[5:])/value)

def put_bridge(cases):
    base=next(x for x in cases if x['name']=='base')
    # The full states and actual share/ownership route are in the referenced forecast case.
    return [dict(case=x['name'],incremental_value_per_share=x['value']-base['value'],
                 same_cash_chain=True,states_location='cases/'+x['name']+'/states')
            for x in cases if x['name'].startswith('put_')]

def tests():
    # Real production functions, independently hand-computable fixtures.
    assert distribution(-2.,1.,0.,1.,10.,0.)==(-1.,0.,0.,0.)
    assert distribution(-1.,3.,0.,1.,10.,0.)==(0.,.2,1.8,.2)
    z=tax_cycle(10.,.2,.5,.5,.2,.1)
    assert all(math.isclose(a,b,abs_tol=1e-12) for a,b in zip(z,[0.,.1,1.5,1.9,.5,.1,0.]))
    assert debt_run(10.,3.)==(7.,3.,10.,7.)
    assert debt_run(10.,3.,9.)==(9.,1.,1.,0.)
    # Return principal is not profit: book10, basis8, fee1 => cash9, bookloss1, taxablegain1.
    assert dispose(10.,8.,.1,.25)==(9.,.25,-1.,1.,1.)
    p,_=operation([100.,0.,0.,0.],[0.,0.,0.],1,0,'base',1)
    assert math.isclose(p,11.5)
    # cash-limited subsidiary dividend and loss-before-reserve
    assert distribution(0.,10.,0.,100.,2.,1.)==(8.,1.,1.,1.)
    try:forecast(('funding_failure',0,.0825,63.4,'funding_failure',1,False),1)
    except AssertionError as e:failure=str(e)
    else:raise AssertionError('funding failure must not produce a valuation')
    z=capital_budget(100.,90.,2,'base')
    assert all(math.isclose(x,y) for x,y in zip(z,[3.5,3.,.2,0.,6.7]))
    assert tax_cycle(-2.,.25,.5,.1,0.,0.)==(.5,0.,0.,0.,0.,0.,0.)
    t=[9.6,3.6,1.8,.12,16.32,6.]
    z=working_cycle(t,t,120.,1,1,-.06,-6.,-6.)
    assert math.isclose(z[2],0.,abs_tol=1e-12) and math.isclose(z[4],76.8) and math.isclose(z[5],120.)
    actual=[8.67620448080,3.69636998901,2.13311223009,.09529966879,19.40884880182,5.10778864867]
    z=working_cycle(actual,actual,120.,1,3,-.06,-6.,-6.)
    assert math.isclose(z[2],.9052170272666667,abs_tol=1e-11)
    assert math.isclose(z[4],78.0265106969767,abs_tol=1e-11)
    assert math.isclose(z[5],120.32129366971,abs_tol=1e-11)
    assert external_funding(10.,10.,5)==(8.,.125,2.)
    assert tax_settlement(10.,3.,.2)==(2.,11.)
    z=put_event('put_50_1',10,0.)
    assert math.isclose(z[0],.4654216) and math.isclose(z[4],.4654216) and z[1]==0.
    z=put_event('put_50_1',15,.4654216)
    assert math.isclose(z[1],.228056584) and math.isclose(z[3],-.237365016) and z[5]==0.
    return {'production_handcases':18,'funding_failure_counterexample':failure,'passed':True}

def main():
    if '--tests' in sys.argv:print(json.dumps(tests(),sort_keys=True));return
    tests();cases=[forecast(x) for x in CASES];print(json.dumps({'schema':2,'as_of':'2026-10-29T17:52:00+00:00','unit':'CNY billion, shares billion','cases':cases,'conditional_put_bridges':put_bridge(cases),'tests':tests()},sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False))
if __name__=='__main__':main()
