"""当前资本现金与权益计算核；经营输入由同次实际计算生成。"""
import json,sys,math,copy
ASOF='2026-10-29T21:15:00+00:00'
SHARES=5.843973444-.027324744
F0=13.90215239402+15.77000341971+(5.95814823145-.02454325436)+.01998252411+.0001
DEBT0=3.00438546269+.21468472+.010+.05293536636+.05222398542+.01044617439
NCI0=.5099672518
WC0=.43867552020+2.52250752191+.05630438348+.1002517778+.26562064336-1.442545254-.97654385991-.55554026115-.42749868676-.98506281977-.11535148725
E0=39.35885125153
P_RE=6.60775754879+.1
DIV_AR=1.575
LOAN=1.09519183722
INV_GROSS=1.80523117295
INV_ALLOW=.10749138451
PRODUCT_R=[15.3,4.85,3.05,5.4,1.55]
SCENARIOS={
 'base':dict(r=.085,g=.015,dm=0.,dg=0.,wc=0.,delay=0.,up=.90),
 'core_low':dict(r=.09,g=.0125,dm=-.005,dg=-.003,wc=0.,delay=0.,up=.90),
 'core_high':dict(r=.08,g=.0175,dm=.005,dg=.003,wc=0.,delay=0.,up=.90),
 'cycle':dict(r=.085,g=.015,dm=0.,dg=0.,wc=0.,delay=.30,up=.85),
 'structural':dict(r=.095,g=.005,dm=-.045,dg=-.015,wc=.045,delay=.50,up=.70),
 'upside':dict(r=.08,g=.02,dm=.015,dg=.015,wc=0.,delay=0.,up=.95),
 'payer_delay':dict(r=.085,g=.015,dm=0.,dg=0.,wc=0.,delay=.75,up=.90),
 'margin_counter':dict(r=.085,g=.015,dm=-.02,dg=0.,wc=0.,delay=0.,up=.90),
 'tax25':dict(r=.085,g=.015,dm=0.,dg=0.,wc=0.,delay=0.,up=.90,tax=.25),
 'terminal_low':dict(r=.09,g=.0125,dm=-.005,dg=-.003,wc=0.,delay=0.,up=.90,terminal_only=True),
 'terminal_high':dict(r=.08,g=.0175,dm=.005,dg=.003,wc=0.,delay=0.,up=.90,terminal_only=True),
 'finance_failure':dict(r=.085,g=.015,dm=-2.,dg=0.,wc=.1,delay=1.,up=0.,zero_cash=True)
}
def legal(re,profit,reserve,capital):
    # Current losses first offset accumulated RE; positive profit first cures old losses.
    taxable_for_reserve=max(0.,profit-max(0.,-re))
    add=min(.1*taxable_for_reserve,max(0.,.5*capital-reserve))
    return re+profit-add,reserve+add,add

def payout(cash,re,minimum,desired):
    return max(0.,min(max(0.,cash-minimum),max(0.,re),max(0.,desired)))

def run(method,name,saved,event=None,n=360,override=None):
    event=event or {}
    cash_delta=(event.get("paid_increment_CNY",0.)+event.get("incremental_fee_CNY",0.)+event.get("h_increment_cash_RMB_condition",0.))/1e9
    a_stock=event.get("bought_increment_shares",0)/1e9
    h_held=event.get("h_issuer_held_excluded_shares",0)/1e9
    cfg=dict(SCENARIOS[name]); cfg.update(override or {})
    # Keep scenario identity out of operating dispatch; cycle applied below.
    p=cfg.get('parent_financial_assets',24.); s=F0-NCI0-p; minorcash=NCI0
    if cfg.get('zero_cash'): p=s=0.
    p-=cash_delta
    pre=P_RE; sre=22.50900180541-P_RE+DIV_AR
    pres=2.925912472; sres=.50; scap=2.; pcap=5.843973444
    ar=DIV_AR; loan=LOAN; investment=INV_GROSS-INV_ALLOW
    wc=WC0; debt=DEBT0; stock=SHARES-a_stock-h_held; treasury=.027324744+a_stock
    equity=E0-cash_delta; mc=NCI0; lag_np=6.7; revprev=sum(PRODUCT_R)
    opassets=E0+DEBT0-(F0-NCI0); fixed=6.31265528895+1.10784971645+1.19170973694+.08617827247+.06901037302; pv=0.; rows=[]; failure=None
    configured=cfg
    for z in saved["years"]:
        y=z["year"];rev=z["revenue"];ebit=z["ebit"];components=copy.deepcopy(z["components"])
        cfg=SCENARIOS['base'] if configured.get('terminal_only') and y<=5 else configured
        scale=rev/sum(PRODUCT_R);tax=cfg.get('tax',.18)
        nopat=z['nopat']
        minor_np=z['minority_profit']
        ownop=z['own_operating_profit']
        ar_trade=z['receivable']
        inventory=z['inventory']
        prepaid=z['prepayment']
        other_receivable=z['other_receivable']
        other_current=z['other_current']
        payable=z['payable']
        contract=z['contract_liability']
        salary=z['salary_payable']
        tax_payable=z['tax_payable']
        otherpay=z['other_payable']
        vat=z['vat_payable']
        wcnew=z['nwc']
        dwc=z['delta_nwc']
        fixed_open=z['depreciable_assets_open']
        da=z['depreciation']
        maintenance=z['maintenance']
        growth=z['growth_capex']
        capex=z['capex']
        fixed=z['depreciable_assets_close']
        fcff=z['fcff']
        oldp,olds,olddebt,oldpre,oldsre,oldar,oldloan=p,s,debt,pre,sre,ar,loan
        target_debt=(2.2 if y==1 else 1.5*scale)+.21468472*scale+.010+.01044617439
        p_locked=4.41697068687*max(0.,1-y/3.)
        s_locked=(5.95814823145-.02454325436-4.41697068687)*max(0.,1-y/3.)
        restricted=.01384926355*target_debt/DEBT0
        pmin=1.5*scale+p_locked+restricted*.70
        smin=1.5*scale+s_locked+restricted*.30
        # First two years repay current + existing lease obligations; replacements in capex.
        debtflow=target_debt-debt
        interest=(debt+target_debt)/2*.023*(1-tax)
        # 1.8% is a blended AFTER-income-tax financial-return budget; see r2 evidence note.
        # Restricted cash remains earning; gross principal is not separately added to value.
        p_fin=p*.018; s_fin=s*.018
        minor_fin=minorcash*.018
        ni_p=ownop*.06+p_fin-interest*.85
        ni_s=ownop*.94+s_fin-interest*.15
        # Financing-note proceeds stay in financing, never operating receipts.
        p_cf=ownop*.06+(da-capex)*.05-dwc*.72+p_fin-interest*.85+debtflow*.85
        s_cf=ownop*.94+(da-capex)*.95-dwc*.28+s_fin-interest*.15+debtflow*.15
        old_tax_paid=.15323081763/5 if y<=5 else 0.
        p_cf-=old_tax_paid*.7; s_cf-=old_tax_paid*.3
        p+=p_cf; s+=s_cf
        # Old declared receivable collection changes cash, NOT profit.
        collection=min(ar,max(0.,s-smin))*(1-cfg['delay'] if y==1 else 1.)
        p+=collection; s-=collection; ar-=collection
        repayment=min(loan,LOAN/5,max(0.,s-smin))
        p+=repayment; s-=repayment; loan-=repayment
        sre,sres,sadd=legal(sre,ni_s,sres,scap)
        # Subsidiary economic pool includes Gaoming direct70%/indirect30%.
        # H1 p86: Xingzhao is a PRC tax-resident enterprise; domestic dividends
        # are exempt. Do not tax 30% indirect domestic ownership as foreign remittance.
        # Overseas/unverified remittance leakage is a separate sensitivity, not a fact.
        want=cfg['up']*max(ni_s,0.)+.10*max(0.,s-3.*scale)
        declared=payout(s,sre,smin,want)
        newpaid=declared*(1-cfg['delay'] if y<=2 else 1.)
        sre-=declared; s-=newpaid
        withholding=newpaid*cfg.get('uplink_tax',.005)
        p+=newpaid-withholding; ar+=declared-newpaid
        pprofit=ni_p+declared-withholding
        pre,pres,padd=legal(pre,pprofit,pres,pcap)
        # Base models the remaining minimum A repurchase budget, at a budget cost
        # of CNY40/share (not a quotation); 70% cancellation, 30% employee transfer Y2.
        buy=.24530655464-event.get("paid_increment_CNY",0.)/1e9 if y==1 else 0.
        bought=buy/40.; stock-=bought; treasury+=bought; p-=buy
        cancelled=.7*(.022035253+a_stock+bought) if y==1 else 0.
        pcap-=cancelled; treasury-=cancelled
        employee_transfer=treasury if y==2 else 0.
        stock+=employee_transfer; treasury-=employee_transfer
        # Employee transfers assumed for service, no sale proceeds; operating margins
        # include compensation budget. Existing own-share acquisition is not expensed twice.
        # Gross financial assets include term deposits; maturities only reclassify.
        p_locked=4.41697068687*max(0.,1-y/3.)
        s_locked=(5.95814823145-.02454325436-4.41697068687)*max(0.,1-y/3.)
        restricted=.01384926355*target_debt/DEBT0
        need=1.5*scale+p_locked+restricted*.70
        if p<pmin-1e-8 or s<smin-1e-8:
            # Authorized no new equity/no unlimited rescue: liquidity support from the
            # parent is a legally booked loan, not a fictional subsidiary profit.
            support=max(0.,smin-s)
            if support<=max(0.,p-pmin) and p>=pmin:
                p-=support; s+=support; loan+=support
            else:
                failure={'year':y,'parent_cash':p,'sub_cash':s,'required_each':need,'reason':'operating liquidity cannot be financed within modeled authority'}
                break
        else: support=0.
        desired=.80*max(0.,lag_np)+.05*max(0.,p-need)
        d=payout(p,pre,need,desired)
        p-=d; pre-=d
        group_np=ownop+p_fin+s_fin-interest-withholding
        equity+=group_np-d-buy
        opassets+=capex-da+dwc+old_tax_paid
        # Full consolidated ordinary equity closure; treasury transfer is equity-neutral.
        expected=p+s+opassets-target_debt
        assert abs(expected-equity)<1e-7*max(1.,abs(equity)),(name,y,expected,equity)
        assert min(p,s,ar,loan,treasury)>=-1e-8
        assert abs((p+s)-(oldp+olds+fcff+p_fin+s_fin-interest+debtflow-withholding-d-buy-old_tax_paid))<1e-7*max(1.,abs(p+s))
        assert abs(pre-(oldpre+pprofit-padd-d))<1e-7*max(1.,abs(pre))
        assert abs(sre-(oldsre+ni_s-sadd-declared))<1e-7*max(1.,abs(sre))
        minor_d=.8*max(0.,minor_np+minor_fin)
        minorcash+=minor_np+minor_fin-minor_d; mc+=minor_np+minor_fin-minor_d
        dps=d/stock; disc=(1+configured['r'])**y; pv+=dps/disc
        row=dict(year=y,revenue=rev,components=components,ebit=ebit,nopat=nopat,minority_profit=minor_np,own_operating_profit=ownop,
          receivable=ar_trade,inventory=inventory,prepayment=prepaid,other_receivable=other_receivable,other_current=other_current,payable=payable,contract_liability=contract,salary_payable=salary,tax_payable=tax_payable,other_payable=otherpay,vat_payable=vat,nwc=wcnew,delta_nwc=dwc,
          depreciable_assets_open=fixed_open,depreciable_assets_close=fixed,
          depreciation=da,maintenance=maintenance,growth_capex=growth,capex=capex,fcff=fcff,
          opening_deferred_tax_paid=old_tax_paid,opening_deferred_tax_remaining=max(0.,.15323081763*(1-y/5)),
          debt_open=debt,debt_close=target_debt,debt_flow=debtflow,after_tax_interest=interest,
          parent_locked_deposits=p_locked,sub_locked_deposits=s_locked,restricted_financial_cash=restricted,parent_liquid_assets=p-p_locked-restricted*.70,sub_liquid_assets=s-s_locked-restricted*.30,
          parent_cash_open=oldp,sub_cash_open=olds,parent_cash=p,sub_cash=s,parent_financial_income=p_fin,sub_financial_income=s_fin,
          parent_direct_profit=ni_p,sub_profit=ni_s,parent_direct_cf=p_cf,sub_direct_cf=s_cf,
          dividend_ar_open=oldar,old_dividend_collected=collection,new_sub_declared=declared,new_sub_paid=newpaid,withholding=withholding,dividend_ar=ar,
          loan_open=oldloan,loan_repaid=repayment,new_loan=support,loan_face=loan,loan_allowance=0.,loan_carrying=loan,
          parent_re_open=oldpre,parent_profit=pprofit,parent_reserve_added=padd,parent_re=pre,parent_reserve=pres,parent_paid_capital=pcap,
          sub_re_open=oldsre,sub_reserve_added=sadd,sub_re=sre,sub_reserve=sres,sub_paid_capital=scap,
          investment_gross=INV_GROSS,investment_allowance=INV_ALLOW,investment_net=investment,
          ordinary_distribution=d,ordinary_distribution_per_share=dps,repurchase_cash=buy,shares_bought=bought,shares_cancelled=cancelled,employee_shares=employee_transfer,economic_shares=stock,treasury_shares=treasury,
          own_net_profit=group_np,ordinary_book_equity=equity,net_operating_assets=opassets,nci_equity=mc,nci_distribution=minor_d,nci_cash=minorcash,
          cash_conservation_error=(p+s)-(oldp+olds+fcff+p_fin+s_fin-interest+debtflow-withholding-d-buy-old_tax_paid),equity_identity_error=expected-equity,pv_distribution=dps/disc,pv_cumulative=pv)
        rows.append(row)
        debt=target_debt; wc=wcnew; revprev=rev; lag_np=group_np
    if failure:
        return dict(method=method,scenario=name,assumptions=cfg,feasible=False,failure=failure,value_per_share=None,terminal_year5=None,years=rows)
    cfg=configured
    tv=sum(x['ordinary_distribution_per_share']/(1+cfg['r'])**(x['year']-5) for x in rows[5:])
    tvshare=tv/(1+cfg['r'])**5/pv
    return dict(method=method,scenario=name,assumptions=cfg,feasible=True,value_per_share=pv,terminal_year5=tv,terminal_pv_share=tvshare,distributions=[x['ordinary_distribution_per_share'] for x in rows[:5]],years=rows)
