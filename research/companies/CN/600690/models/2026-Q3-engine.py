#!/usr/bin/env python3
"""Self-contained stdlib economic model. bn CNY/bn shares; no input-file dependency."""
import json,math
ASOF='2026-10-29T16:54:00+00:00'
NAMES=['海尔智家母公司','境内经营子公司现金预算池','Haier U.S. Appliance Solutions及美洲经营链','海尔股份香港及其他海外经营链']

def reserve_step(old_re,profit,reserve,capital,rate=.10):
    # This exact function is also used by production scenarios and hand cases.
    eligible=max(0.,profit+min(0.,old_re))
    transfer=min(eligible*rate,max(0.,capital*.5-reserve))
    return old_re+profit-transfer,reserve+transfer,transfer

def payout(cash,buffer,legal,wanted):
    return min(max(0.,wanted),max(0.,cash-buffer),max(0.,legal))

def finance_asset(book,basis,year,sell=True):
    income=book*.05;dividend=income*.70;book+=income-dividend
    net=tax=loss=0.
    if 8<=year<=12 and sell:
        sold=book/(13-year);basis_sold=basis/(13-year)
        net=sold*.95*.98;tax=max(0.,net-basis_sold)*.25
        loss=sold-net;book-=sold;basis-=basis_sold
    return book,basis,income,dividend,net,tax,loss

def operating(year,entry,shock,region_revenue):
    if entry=='region':
        growth={2:[.02,.02,.06],3:[.025,.02,.05],4:[.025,.02,.04],5:[.02,.02,.03]}.get(year,[.015,.015,.015])
        if year>1:region_revenue=[r*(1+g) for r,g in zip(region_revenue,growth)]
        revenues=region_revenue[:]
        margins=[.093+min(year-1,4)*.00075,.05+min(year-1,4)*.00125,.056+min(year-1,4)*.001]
    else:
        products=[174*(1.018**min(year-1,4))*(1.015**max(year-5,0)),89*(1.045**min(year-1,4))*(1.015**max(year-5,0)),34*(1.025**min(year-1,4))*(1.015**max(year-5,0))]
        profit=sum(x*y for x,y in zip(products,[.087,.092,.002]))
        total=sum(products);revenues=[total*.48,total*.25,total*.27];margins=[profit/total]*3
    if shock=='cycle':
        mult=[.92,.95,.975,1.,1.][min(year-1,4)];cut=[.015,.01,.005,0.,0.][min(year-1,4)]
        revenues=[revenues[0]*mult,revenues[1]*mult,revenues[2]];margins=[margins[0]-cut,margins[1]-cut,margins[2]]
    elif shock=='structural':revenues=[140.,72.,78.*1.005**(year-1)];margins=[.073,.035,.041]
    elif shock=='margin':margins=[m-.01 for m in margins]
    elif shock=='upside':margins=[m+.008 for m in margins]
    return revenues,margins,region_revenue

def finance_maturity(cash,floor,payable,opening_face,due,original_face,renewal_ratio):
    remaining=max(0.,opening_face-due)
    surplus=max(0.,cash-floor-payable)
    planned_amortization=min(original_face/10,opening_face)
    requested=max(0.,due-min(planned_amortization,surplus),due-(cash-floor))
    limit=min(renewal_ratio*due+(original_face*.1 if renewal_ratio else 0.),max(0.,original_face*1.1-remaining))
    draw=min(requested,limit)
    gap=max(0.,floor-(cash+draw-due))
    return draw,limit,gap

def capital_support(parent_cash_after_due,parent_floor,foreign_gap,limit=2.):
    principal=min(limit,max(0.,foreign_gap),max(0.,parent_cash_after_due-parent_floor)/1.005)
    return principal,principal*.005

def lease_budget(opening_face,revenue):
    interest=opening_face*.035
    principal=opening_face*.30
    end_face=6.12860249428*revenue/290.
    additions=end_face-opening_face+principal
    assert additions>=-1e-10
    return interest,principal,interest+principal,additions,end_face

def calculate(rate=.09,shock='base',entry='region',n=600):
    cash=[5.18618959424,14.,11.,9.46865483533]
    locked=[0.,1.,0.,.42897156333]
    deposit=[8.56449457885,12.5,2.85,4.77781753788];original_deposit=deposit[:]
    deposit_interest=[.25,.5,.15,.29010915928];original_deposit_interest=deposit_interest[:]
    trading=[1.14627895833,2.,0.,.36887246362]
    debt_interest=[.02069839355,.02,.02,.02077285645]
    short_principal=[2.,7.,7.,4.26349715838];current_long=[.92676277778,.1,.1,.07192221328]
    long_principal=[3.74,4.9,4.9,1.62411568061];bond=[3.5,0.,0.,0.];rolling_loans=[0.]*4
    injected_cost=0.
    allowance=.00438140981;pool_interest=.00318527778
    opening_paid_A=.020175398;cash[0]-=opening_paid_A
    pool_term={'pool5':5,'pool10':10,'pool40':40,'funding_failure':1}.get(shock,20)
    renewal=0. if shock in ('no_rollover','funding_failure','support_unavailable') else .5 if shock=='credit_tight' else 1.
    new_loan_rate=.05 if shock=='credit_tight' else .0375
    liquidity_defence=shock in ('no_rollover','credit_tight','funding_failure','operating_failure','support_unavailable')
    equity=[5.10398527402,14.,0.,7.58446117369];basis=equity[:]
    if shock=='short_deposit_zero':
        deposit[3]-=1.06295;original_deposit[3]-=1.06295;deposit_interest[3]-=.01238017479;original_deposit_interest[3]-=.01238017479
    debt=[10.16676277778,12.,12.,5.95953505227];original_debt=debt[:]
    retained=[3.81752658055,30.,20.,10.];reserves=[4.691456667,1.,0.,0.]
    capital=[9.298538164,10.,10.,10.]
    dividend_ar=5.77103628755;dividend_ap=[0.,3.,1.5,1.27103628755]
    pool_ar=61.89762275810;pool_ap=110.85428234403
    deferred_assets=[0.,.9,.7,.78766402332];deferred_liab=[.39389874339,.3,.8,.42790552278]
    previous_revenue=[140.,72.,78.];underlying_revenue=[140.,72.,78.]
    nci=[0.,4.5,0.,2.31620001535];lease=6.12860249428;shares=9.218280204;states=[];value=0.;max_cash_error=0.
    for year in range(1,n+1):
        cash_open=sum(cash);restricted_open=sum(locked);opening_pool_ar=pool_ar;opening_pool_ap=pool_ap
        revenues,margins,underlying_revenue=operating(year,entry,shock,underlying_revenue)
        if liquidity_defence:revenues=[140.,72.,78.]
        if shock=='operating_failure':margins=[-1.,-1.,-1.]
        delay=shock=='remittance' and year<=3
        receipt=0.;pool_in=pool_out=0.
        if not delay:
            for i in (1,2,3):
                actual=min(dividend_ap[i],max(0.,cash[i]));cash[i]-=actual;cash[0]+=actual;dividend_ap[i]-=actual;receipt+=actual
            dividend_ar-=receipt
            pool_in=min(max(0.,pool_ar-allowance),61.89324134829/pool_term);pool_out=min(pool_ap,110.85428234403/pool_term)
            cash[0]+=pool_in-pool_out;cash[1]+=pool_out-pool_in;pool_ar-=pool_in;pool_ap-=pool_out
        pool_gross_in=max(0.,pool_ar-allowance)+pool_in if not delay else 0.
        pool_gross_out=pool_ap+pool_out if not delay else 0.
        pool_new_advance=pool_gross_in-pool_in;pool_new_borrow=pool_gross_out-pool_out
        old_interest_receipt=pool_interest if year==1 else 0.;cash[0]+=old_interest_receipt;pool_interest-=old_interest_receipt
        collected_interest=[0.]*4;trading_sale=[0.]*4;paid_old_interest=[0.]*4
        buffers=[2.,revenues[0]*.04,revenues[1]*.04,revenues[2]*.04]
        arrays={k:[0.]*4 for k in ['income','fc','tax','interest_income','interest_cost','redeem','equity_div','exit_tax','impair','net_invest','dta_used','dtl_paid','sale_net']}
        for i in range(4):
            tax_rate=[.25,.18,.25,.24][i]
            interest_cost=(debt[i]-rolling_loans[i]-bond[i])*.035+rolling_loans[i]*new_loan_rate+bond[i]*(1.5*.0199+2*.0166)/3.5;interest_income=(cash[i]+locked[i]+deposit[i]+trading[i])*.022
            equity[i],basis[i],equity_income,equity_div,sale,sale_tax,loss=finance_asset(equity[i],basis[i],year,shock!='hold_equity')
            ratio=11.26802909443/28.69231211673
            redeem=original_deposit[i]*ratio if year==1 else min(deposit[i],original_deposit[i]*(1-ratio)/4) if year<=5 else 0.;deposit[i]-=redeem
            collected_interest[i]=original_deposit_interest[i]*(1.02055455027/1.19010915928) if year==1 else deposit_interest[i] if year==2 else 0.;deposit_interest[i]-=collected_interest[i]
            trading_sale[i]=trading[i] if year==1 else 0.;trading[i]-=trading_sale[i]
            paid_old_interest[i]=debt_interest[i] if year==1 else 0.;debt_interest[i]-=paid_old_interest[i]
            cash[i]+=redeem+sale-sale_tax+collected_interest[i]+trading_sale[i]-paid_old_interest[i]
            op=0.;net_invest=0.
            if i>0:
                j=i-1;op=revenues[j]*margins[j]
                if shock=='structural' and year==1:loss+=[1.,5.,2.][j]
                depreciation=revenues[j]*[.020,.022,.025][j]
                capex=revenues[j]*[.030,.058,.038][j] if year<=5 else depreciation+max(0.,op)*(1-tax_rate)*.015/[.20,.16,.18][j]
                if liquidity_defence and year>5:capex=depreciation
                wc=(revenues[j]-previous_revenue[j])*.05+(revenues[j]*.02 if shock=='structural' and year==1 else 0.)
                net_invest=capex-depreciation+wc
            taxable=max(0.,op+interest_income-interest_cost)
            normal_tax=taxable*tax_rate
            dta_used=min(deferred_assets[i],normal_tax*.1);deferred_assets[i]-=dta_used
            dtl_paid=deferred_liab[i]/(11-year) if year<=10 else 0.;deferred_liab[i]-=dtl_paid
            cash_tax=normal_tax-dta_used+dtl_paid
            income=op+interest_income+equity_income-interest_cost-loss-normal_tax-sale_tax
            cf=op+interest_income+equity_div-interest_cost-cash_tax-net_invest
            if i==0:income-=.25;cf-=.25
            cash[i]+=cf
            if year==5:cash[i]+=locked[i];locked[i]=0.
            vals=[income,cf,cash_tax,interest_income,interest_cost,redeem,equity_div,sale_tax,loss,net_invest,dta_used,dtl_paid,sale]
            for k,v in zip(arrays,vals):arrays[k][i]=v
        previous_revenue=revenues[:]
        buyback=1.18770973552+(0. if liquidity_defence else .68974745072) if year==1 else 0.;cash[0]-=buyback
        if year==1 and not liquidity_defence:arrays['income'][0]-=.68974745072
        minority=[0.]*4
        minority_profit=[0.,arrays['income'][1]*.05,0.,arrays['income'][3]*.03]
        repaid=[];new_borrow=[];maturities=[];borrow_limits=[];failures=[]
        for i in range(4):
            due=(short_principal[i]+current_long[i] if year==1 else long_principal[i]/4 if 2<=year<=5 else 0.)+(bond[i] if year==2 else 0.)+rolling_loans[i]
            draw,limit,gap=finance_maturity(cash[i],buffers[i],dividend_ap[i],debt[i],due,original_debt[i],renewal)
            if gap>1e-8:failures.append(dict(pool=i,required_floor=buffers[i],available_cash=cash[i],mandatory_due=due,new_borrow=draw,financing_gap=gap))
            repaid.append(due);new_borrow.append(draw);maturities.append(due);borrow_limits.append(limit)
        capital_help=0.;capital_fee=0.
        if liquidity_defence and shock!='support_unavailable':
            parent_available=cash[0]+new_borrow[0]-repaid[0]
            foreign_gap=max(0.,buffers[2]-cash[2]-new_borrow[2]+repaid[2])
            capital_help,capital_fee=capital_support(parent_available,buffers[0],foreign_gap)
            cash[0]-=capital_help+capital_fee;cash[2]+=capital_help
            arrays['income'][0]-=capital_fee;arrays['fc'][0]-=capital_fee;capital[2]+=capital_help;injected_cost+=capital_help
            failures=[]
            for i in range(4):
                gap=buffers[i]-(cash[i]+new_borrow[i]-repaid[i])
                if gap>1e-8:failures.append(dict(pool=i,required_floor=buffers[i],available_cash=cash[i],mandatory_due=maturities[i],new_borrow=new_borrow[i],financing_gap=gap))
        if failures:
            return dict(asof=ASOF,rate=rate,shock=shock,entry=entry,status='infeasible',value=None,year5=None,dividends=None,tail_pv_bound=None,states=states,failure=dict(year=year,reason='mandatory_maturity_or_operating_cash_floor',details=failures,proposed_cash_before_debt=cash[:],debt_face=debt[:],unsettled_opening_pool_receivable_face=opening_pool_ar,unsettled_opening_pool_payable_face=opening_pool_ap,discretionary_dividend=0.,expansion_capex_cut=liquidity_defence and year>5,discretionary_A_stopped=liquidity_defence))
        for i in range(4):
            cash[i]+=new_borrow[i]-repaid[i];debt[i]+=new_borrow[i]-repaid[i];rolling_loans[i]=new_borrow[i]
        if year==2:bond=[0.]*4
        reserve_added=[]
        for i in range(4):
            retained[i],reserves[i],transfer=reserve_step(retained[i],arrays['income'][i],reserves[i],capital[i]);reserve_added.append(transfer)
        declarations=[0.]*4;withholding=0.
        for i in (1,2,3):
            defence=(2*revenues[i-1]*[.01,.036,.013][i-1]+(long_principal[i]/4 if year<5 else 0.)+rolling_loans[i]) if liquidity_defence and year<=5 else 0.
            free=max(0.,cash[i]-buffers[i]-dividend_ap[i]-defence)
            available=min(free*.9,max(max(0.,arrays['income'][i])*.85,free*.25))
            gross=payout(cash[i],buffers[i]+dividend_ap[i],retained[i],available)
            minority[i]=gross*[0.,.05,0.,.03][i]
            gross_common=gross-minority[i];drag=gross_common*(.03 if i>1 else 0.);net=gross_common-drag
            cash[i]-=drag+minority[i];withholding+=drag;retained[i]-=gross;dividend_ap[i]+=net;dividend_ar+=net;declarations[i]=net
            nci[i]+=minority_profit[i]-minority[i]
        declared=sum(declarations);arrays['income'][0]+=declared;retained[0]+=declared
        common_income=sum(arrays['income'])-declared-sum(minority_profit)-withholding
        wished=max(0.,common_income)*(.60 if year<=5 else .80 if year<=10 else 1.)
        if liquidity_defence and year<=5:wished=0.
        if year>10:wished=max(wished,max(0.,cash[0]-buffers[0]))
        common_dividend=payout(cash[0],buffers[0],retained[0],wished);cash[0]-=common_dividend;retained[0]-=common_dividend
        eligible_shares=shares-.069981989*(max(0,3-year)/3)
        dps=common_dividend/eligible_shares;annual_pv=dps/(1+rate)**year;value+=annual_pv
        lease_open=lease
        lease_interest,lease_principal_paid,lease_cash,lease_new,lease=lease_budget(lease_open,sum(revenues))
        rent_by_region=[lease_cash*r/sum(revenues) for r in revenues]
        before_rent=[revenues[i]*margins[i]+rent_by_region[i] for i in range(3)]
        assert abs(lease-6.12860249428*sum(revenues)/290.)<1e-9*max(1.,lease)
        # Global cash conservation: transfers and dividends between group entities cancel, never add value.
        expected=cash_open+sum(arrays['fc'])+sum(arrays['redeem'])+sum(arrays['sale_net'])-sum(arrays['exit_tax'])+(restricted_open-sum(locked))-sum(minority)-sum(repaid)-buyback-withholding-common_dividend+sum(new_borrow)+sum(collected_interest)+sum(trading_sale)-sum(paid_old_interest)+old_interest_receipt
        error=sum(cash)-expected;max_cash_error=max(max_cash_error,abs(error))
        assert abs(error)<1e-8*max(1,abs(expected)),(year,error)
        assert all(cash[i]>=buffers[i]-1e-8 for i in range(4))
        assert min(cash)>-1e-8,(year,shock,cash)
        assert abs(dividend_ar-sum(dividend_ap))<1e-6*max(1,dividend_ar)
        assert all(v>=-1e-8 for v in debt+deposit+basis+locked)
        states.append(dict(year=year,revenue=revenues,operating_margin=margins,cash=cash[:],restricted=locked[:],deposit_principal_face=deposit[:],deposit_accrued_interest=deposit_interest[:],deposit_interest_collected=collected_interest,trading_asset_carrying=trading[:],trading_recovered=trading_sale,debt_accrued_interest=debt_interest[:],debt_old_interest_paid=paid_old_interest,bank_mandatory_due=maturities,bank_new_borrow=new_borrow,bank_borrow_cap=borrow_limits,bank_refinanced_one_year_face=rolling_loans[:],cash_floor=buffers,opening_paid_A_cash_bridge=opening_paid_A if year==1 else 0.,equity_carrying=equity[:],equity_tax_basis=basis[:],debt_face=debt[:],debt_paid=repaid,lease_face=lease,lease_open_face=lease_open,lease_principal_paid=lease_principal_paid,lease_cash_included_in_operating=rent_by_region,operating_profit_before_cash_rent=before_rent,lease_new=lease_new,lease_cash=lease_cash,lease_interest=lease_interest,net_income=arrays['income'],minority_paid=minority,minority_income=minority_profit,minority_equity=nci[:],tax_cash=arrays['tax'],dta=deferred_assets[:],dtl=deferred_liab[:],dta_used=arrays['dta_used'],dtl_paid=arrays['dtl_paid'],financial_income=arrays['interest_income'],interest=arrays['interest_cost'],equity_income_cash=arrays['equity_div'],equity_exit_tax=arrays['exit_tax'],asset_impairment=arrays['impair'],reinvestment=arrays['net_invest'],operating_financing_cash=arrays['fc'],deposit_recovered=arrays['redeem'],dividend_received=receipt,dividend_declared=declarations,dividend_receivable=dividend_ar,sub_dividend_payable=dividend_ap[:],pool_receivable_face=pool_ar,pool_allowance=allowance,pool_allowance_reversal=0.,pool_legal_writeoff=0.,pool_loss_tax_cash=0.,pool_receivable_net=pool_ar-allowance,pool_accrued_interest=pool_interest,pool_old_interest_received=old_interest_receipt,pool_gross_due_receivable=pool_gross_in,pool_gross_due_payable=pool_gross_out,pool_new_advance=pool_new_advance,pool_new_borrow=pool_new_borrow,pool_payable_face=pool_ap,pool_receipt=pool_in,pool_payment=pool_out,re=retained[:],reserve=reserves[:],reserve_add=reserve_added,parent_total_long_term_investment_carrying=76.33429375260+injected_cost,parent_US_capital_injection=capital_help,capital_transfer_cost=capital_fee,internal_paid_in_capital=capital[:],buyback_cash=buyback,withholding=withholding,common_income=common_income,common_dividend=common_dividend,shares=eligible_shares,full_diluted_shares=shares,dps=dps,pv=annual_pv,cumulative_value=value))
    residual=states[-1]['dps']*1.015/(rate-.015)/(1+rate)**n
    assert residual<1e-8
    return dict(asof=ASOF,rate=rate,shock=shock,entry=entry,status='feasible',value=value+residual,year5=sum(s['dps']/(1+rate)**(s['year']-5) for s in states[5:])+residual*(1+rate)**5,dividends=[s['dps'] for s in states[:5]],tail_pv_bound=residual,states=states)

def handtests():
    # Direct tests of precisely the production functions, with independent expected numbers.
    assert reserve_step(-4,10,0,100)==(5.4,.6000000000000001,.6000000000000001)
    assert reserve_step(-20,10,0,100)==(-10,0.,0.)
    assert reserve_step(5,10,49.8,100)[1]==50.
    assert payout(12,3,4,9)==4
    b,c,y,d,p,t,l=finance_asset(100,80,12)
    assert abs(y-5)<1e-12 and abs(d-3.5)<1e-12
    assert abs(p-94.4965)<1e-10 and abs(t-3.624125)<1e-10 and abs(l-7.0035)<1e-10
    assert abs(b)+abs(c)<1e-12
    return {'loss_before_reserve':True,'loss_blocks_distribution':True,'reserve_cap':True,'cash_and_RE_cap':True,'asset_principal_gain_fee_tax':True}
if __name__=='__main__':
    handtests()
    out={key:calculate(rate,shock,entry) for key,rate,shock,entry in [('low',.095,'base','region'),('base',.09,'base','region'),('high',.085,'base','region'),('product',.09,'base','product'),('cycle',.09,'cycle','region'),('structural',.10,'structural','region'),('upside',.09,'upside','region'),('margin',.09,'margin','region'),('remittance',.09,'remittance','region'),('hold_equity',.09,'hold_equity','region'),('short_deposit_zero',.09,'short_deposit_zero','region'),('pool5',.09,'pool5','region'),('pool10',.09,'pool10','region'),('pool40',.09,'pool40','region'),('no_rollover',.09,'no_rollover','region'),('credit_tight',.09,'credit_tight','region'),('funding_failure',.09,'funding_failure','region'),('operating_failure',.09,'operating_failure','region'),('support_unavailable',.09,'support_unavailable','region')]}
    print(json.dumps(out,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False))
