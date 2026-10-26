#!/usr/bin/env python3
"""600415 owner cash valuation. CNY billion, shares billion. stdlib only.
Annual steps end 2027-10-26 ... 2036-10-26; no quoted price/IRR.
All forecast numbers are research budgets, not management commitments.
"""
import json, math, copy
from pathlib import Path
S=5.483559226
P={
 'shares':S,'sub_reserve_cap':3.0,'service_reserve_share':1/3,'spv_opening_legal':0.,'initial_parent_operating_capital':21.528,'initial_sub_operating_capital':2.50,'land_amortization_base':.29875,'land_cohorts':[[2.0,20,2.0],[2.0,25,1.5],[4.75,40,3.5]],'renewed_land_life':40,'mature_last_year':240,'parent_cash':2.62860596978,'sub_cash':0.31908907089,
 'old_dividend_payable':1.60,'parent_legal':10.91945666804,'reserve':2.41770218353,
 'parent_cash_floor':0.8,'sub_cash_floor':0.2,'debt':3.16491319407,
 'debt_limit':8.0,'debt_rate':0.03,'payout':0.55,
 'market_revenue':3.10,'market_margin':0.45,'market_tax':0.25,
 'market_growth':[.025]*10,
 'digital_profit':.14,'digital_growth':[.10]*5+[.08,.06,.05,.04,.03],
 'pay_profit':.025,'pay_growth':[.20]*5+[.15,.10,.08,.05,.03],
 'trade_profit':.03,'trade_capital':2.0,'trade_growth':.03,
 'other_profit':.03,'market_da':.75,'market_maintenance':.45,
 'market_incremental_roic':.40,'digital_incremental_roic':.40,
 'project_capex':[2.45,2.05,1.33,.3,.1,0,0,0,0,0],
 'legacy_completion':[1.0,.5,.1,0,0,0,0,0,0,0],
 'legacy_net_sales_cash':[.3,.5,.2,0,0,0,0,0,0,0],
 'legacy_sales_profit':[.08,.10,.04,0,0,0,0,0,0,0],
 'project_profit':[0,0,0,.04,.10,.14,.16,.17,.17,.17],
 'project_da':[0,0,0,.02,.05,.07,.08,.08,.08,.08],
 'project_maintenance':[0,0,0,.02,.05,.07,.08,.08,.08,.08],
 'parent_wc_extra':[.30,.20,-.25,-.25,0,0,0,0,0,0],
 'sub_wc_extra':[.15,.05,0,0,0,0,0,0,0,0],
 'parent_other_net_payments':[.15,.10,0,0,0,0,0,0,0,0],
 'parent_financial':1.17544289071,'sub_financial':1.62111182267,
 'property_rights':3.61962308727,'parent_other_rights':.335,'sub_other_rights':1.37111541374,
 'leasing_book':.69151935555,'hotel_book':.51990495872,'logistics_book':.14850607920,
 'leasing_roe':.18,'leasing_growth':.05,'hotel_roe':.10,'hotel_growth':.02,
 'deposit_principal':.45,'deposit_release_year':2,'cd_principal':.50,
 'financial_release':[.40,.25,.15,.05,.025,.025,.025,.025,.025,.025],
 'property_release':[0,0,.10,.10,.10,.15,.15,.15,.15,.10],
 'fund_release':[0,0,0,.10,.10,.15,.15,.15,.15,.20],
 'portfolio_yield':.02,'sub_upstream_ratio':.75,'upstream_lag':0,
 'frozen_loss_fraction':0,'property_loss':0,'project_scale':1,'capex_scale':1,'rent_scale':1,'digital_scale':1,
 'loan_call':0,'terminal_g':.02,'terminal_roic':.12,'terminal_leasing_roe':.15,
 'extra_commitment':0,'extra_loss':0,'minority_profit':.012,'construction_debt_share':.35,
 'prepaid_fee_revenue':[1.5,1.0,.5,0,0,0,0,0,0,0],'project_net_sale_cash':[0,0,.8,1.7,1.0,0,0,0,0,0],'project_sale_profit':[0,0,.1,.25,.15,0,0,0,0,0],
 'land_renewal_base':2.0,'land_inflation':.02,
 'frozen_financial':.66436108531,'frozen_fund':.102918559,'realization_tax':.060,'cash_release_lag':1,
}

def present_value(distributions,terminal,r):
    if r<=-1: raise ValueError('discount rate')
    return sum(c/(1+r)**(i+1) for i,c in enumerate(distributions))+terminal/(1+r)**len(distributions)

def reserve_profit(legal,reserve,profit,cap):
    # loss must first be recovered; statutory reserve only from profit after recovery
    post=legal+profit
    alloc=min(max(cap-reserve,0),max(0,profit+min(legal,0))*.1)
    return post-alloc,reserve+alloc,alloc

def settle_cash(cash,legal,target,floor,debt,limit):
    # NO debt to support dividends: borrow only to preserve mandatory liquidity.
    draw=max(0,floor-cash)
    if debt+draw>limit+1e-9: raise ValueError('mandatory funding deficit even with zero dividend')
    cash+=draw; debt+=draw
    paid=min(max(0,target),max(0,legal),max(0,cash-floor))
    return cash-paid,legal-paid,paid,debt,draw

def simulate(p):
    cashp=p['parent_cash']-p['old_dividend_payable']; cashs=p['sub_cash']
    legalp=p['parent_legal']; legals=0.; reservep=p['reserve']; reserves=0.
    service_cash=p['sub_cash_floor'];spv_cash=p['sub_cash']-service_cash
    service_legal=service_reserve=spv_reserve=service_recv=spv_recv=0.;spv_legal=p['spv_opening_legal']
    debt=p['debt']; m=p['market_revenue']*p['market_margin']*(1-p['market_tax'])*p['rent_scale']
    digital=p['digital_profit']*p['digital_scale']; pay=p['pay_profit']; trade=p['trade_profit']; wc=p['trade_capital']
    lease=p['leasing_book']; hotel=p['hotel_book']; receivable=0.; rows=[]
    finp=p['parent_financial']; fins=p['sub_financial']; prop=p['property_rights']; fp=p['parent_other_rights']; fs=p['sub_other_rights']
    accum_cap=0.; capitalp=p['initial_parent_operating_capital']; capitals=p['initial_sub_operating_capital']; protected_payment_capital=0.; minority=p['minority_profit']
    for i in range(10):
        y=i+1; openingp=cashp; openings=cashs; openingdebt=debt; openingreceivable=receivable; opening_service_cash=service_cash;opening_spv_cash=spv_cash;opening_service_recv=service_recv;opening_spv_recv=spv_recv; opening_legalp=legalp; opening_reservep=reservep
        mg=p['market_growth'][i]; dg=p['digital_growth'][i]; pg=p['pay_growth'][i]
        if i: m*=1+mg; digital*=1+dg; pay*=1+pg; trade*=1+p['trade_growth']
        market_reinvest=m*mg/p['market_incremental_roic']
        digital_reinvest=digital*dg/p['digital_incremental_roic']
        pay_reinvest=max(0,pay*.25); protected_payment_capital+=pay_reinvest # own risk/technology capital; NEVER customer balances
        trade_wc=wc*p['trade_growth']; wc+=trade_wc
        project=p['project_profit'][i]*p['project_scale']; project_da=p['project_da'][i]
        maintain=p['market_maintenance']*(1.02**i)+p['project_maintenance'][i]
        da=p['market_da']*(1.02**i)+project_da
        capex=(p['project_capex'][i]+p['legacy_completion'][i])*p['capex_scale']
        accum_cap+=capex+market_reinvest+digital_reinvest+pay_reinvest
        capitalp+=capex+market_reinvest+maintain-da
        capitals+=digital_reinvest+pay_reinvest+trade_wc
        assert min(capitalp,capitals)>0
        # Existing non-operating holdings: principal returned at finite dates, income removed on redemption.
        fr=p['financial_release'][i]; pr=p['property_release'][i]; ur=p['fund_release'][i]
        fin_income_p=finp*p['portfolio_yield']; fin_income_s=max(0,fins-p['frozen_financial']*(1-(p['frozen_loss_fraction'] if y>1 else 0)))*p['portfolio_yield']; fund_income_p=fp*.02; fund_income_s=max(0,fs-p['frozen_fund']*(1-(p['frozen_loss_fraction'] if y>1 else 0)))*.02
        finrelp=p['parent_financial']*fr; finrels=(p['sub_financial']-p['frozen_financial'])*fr+(p['frozen_financial']*(1-p['frozen_loss_fraction']) if y==10 else 0)
        proploss=p['property_loss'] if y==1 else 0.
        proprel=p['property_rights']*pr*(1-p['property_loss']/p['property_rights'])
        frelp=p['parent_other_rights']*ur; frels=(p['sub_other_rights']-p['frozen_fund'])*ur+(p['frozen_fund']*(1-p['frozen_loss_fraction']) if y==10 else 0)
        frozenloss=(p['frozen_financial']+p['frozen_fund'])*p['frozen_loss_fraction'] if y==1 else 0.
        if y==1: fins-=p['frozen_financial']*p['frozen_loss_fraction']; fs-=p['frozen_fund']*p['frozen_loss_fraction']
        finp-=finrelp; fins-=finrels; prop-=proprel+proploss; fp-=frelp; fs-=frels
        lp=lease*p['leasing_roe']; ld=lp-lease*p['leasing_growth']; lease+=lp-ld
        hp=hotel*p['hotel_roe']; hd=hp-hotel*p['hotel_growth']; hotel+=hp-hd
        deposit=p['deposit_principal'] if y==p['deposit_release_year'] else 0.
        cd=p['cd_principal'] if y==3 else 0.
        # Associate new declarations: no repeat recognition of previous dividend receivables.
        parent_equity_income=lp+hp; parent_assoc_cash=ld+hd
        planned_draw=min(capex*p['construction_debt_share'],max(0,p['debt_limit']-debt))
        interest=(debt+planned_draw*.5)*p['debt_rate']*.75
        debt+=planned_draw;cashp+=planned_draw
        parent_profit=m+project+p['prepaid_fee_revenue'][i]*.75+p['project_sale_profit'][i]+p['other_profit']+p['legacy_sales_profit'][i]+parent_equity_income+fin_income_p+fund_income_p-interest-proploss-(p['extra_loss'] if y==1 else 0)
        service_profit=digital+pay+trade-minority
        spv_profit=fin_income_s+fund_income_s-frozenloss
        subsidiary_profit=service_profit+spv_profit
        service_legal,service_reserve,_=reserve_profit(service_legal,service_reserve,service_profit,p['sub_reserve_cap']*p['service_reserve_share'])
        spv_legal,spv_reserve,_=reserve_profit(spv_legal,spv_reserve,spv_profit,p['sub_reserve_cap']*(1-p['service_reserve_share']))
        service_free=service_profit-digital_reinvest-pay_reinvest-trade_wc-p['sub_wc_extra'][i]
        spv_free=fin_income_s+fund_income_s+finrels+frels
        service_cash+=service_free;spv_cash+=spv_free
        service_new=min(max(service_legal-protected_payment_capital,0),max(service_cash-p['sub_cash_floor']-service_recv,0),max(service_profit*p['sub_upstream_ratio'],0))
        spv_new=min(max(spv_legal,0),max(spv_cash-spv_recv,0),max(spv_profit*p['sub_upstream_ratio'],0))
        if y==10:
            service_new=min(max(service_legal-protected_payment_capital,0),max(service_cash-p['sub_cash_floor']-service_recv,0))
            spv_new=min(max(spv_legal,0),max(spv_cash-spv_recv,0))
        service_legal-=service_new;spv_legal-=spv_new
        service_got=service_recv if p['upstream_lag'] else service_new
        spv_got=spv_recv if p['upstream_lag'] else spv_new
        service_recv=service_new if p['upstream_lag'] else 0.
        spv_recv=spv_new if p['upstream_lag'] else 0.
        service_cash-=service_got;spv_cash-=spv_got
        # Only parent capital, not SPV cash or legal profits, may fund operating subsidiary shortfalls.
        inject=max(p['sub_cash_floor']-service_cash,0);service_cash+=inject
        new_decl=service_new+spv_new;received=service_got+spv_got;receivable=service_recv+spv_recv
        sub_free=service_free+spv_free;cashs=service_cash+spv_cash
        legals=service_legal+spv_legal;reserves=service_reserve+spv_reserve
        assert abs(service_cash-opening_service_cash-service_free+service_got-inject)<1e-8
        assert abs(spv_cash-opening_spv_cash-spv_free+spv_got)<1e-8
        assert abs(service_recv-opening_service_recv-service_new+service_got)<1e-8
        assert abs(spv_recv-opening_spv_recv-spv_new+spv_got)<1e-8
        assert service_cash>=p['sub_cash_floor']-1e-8 and spv_cash>=-1e-8
        if service_legal<0:assert service_new==0
        if spv_legal<0:assert spv_new==0
        parent_profit+=new_decl
        legalp,reservep,preserve=reserve_profit(legalp,reservep,parent_profit,p['shares']*.5)
        pfree=m+project-p['prepaid_fee_revenue'][i]*.25+p['project_net_sale_cash'][i]+p['other_profit']+da-maintain-market_reinvest-capex+p['legacy_net_sales_cash'][i]-p['parent_wc_extra'][i]-p['parent_other_net_payments'][i]+parent_assoc_cash+fin_income_p+fund_income_p+finrelp+proprel+frelp+deposit+cd-interest-inject-(p['realization_tax'] if y==2 else 0)-(p['extra_commitment'] if y==1 else 0)
        cashp+=pfree+received
        if y==3 and p['loan_call']:
            repayment=min(p['loan_call'],debt); debt-=repayment; cashp-=repayment
        else: repayment=0.
        common_profit=(parent_profit-new_decl-parent_equity_income)+subsidiary_profit+lp+hp
        target=max(0,common_profit*p['payout'])
        final_repayment=debt if y==10 else 0.
        cashp-=final_repayment;debt-=final_repayment
        if y==10: target=max(0,cashp-p['parent_cash_floor'])
        short=max(0,p['parent_cash_floor']-cashp)
        extra_interest=short/(1-.5*p['debt_rate']*.75)*.5*p['debt_rate']*.75
        if extra_interest:
            cashp-=extra_interest;pfree-=extra_interest;interest+=extra_interest;parent_profit-=extra_interest;common_profit-=extra_interest
            legalp,reservep,preserve=reserve_profit(opening_legalp,opening_reservep,parent_profit,p['shares']*.5)
            target=0.0
        cashp,legalp,div,debt,draw=settle_cash(cashp,legalp,target,p['parent_cash_floor'],debt,p['debt_limit'])
        # Surplus first deleverages after construction; no permanent cash trap.
        repay_extra=min(max(0,cashp-p['parent_cash_floor']),max(0,debt-p['debt'])) if y>=5 else 0.
        cashp-=repay_extra; debt-=repay_extra
        assert abs(cashp-(openingp+pfree+received-repayment+draw+planned_draw-div-repay_extra-final_repayment))<1e-8
        assert abs(cashs-(openings+sub_free-received+inject))<1e-8
        assert abs((receivable-openingreceivable)-(new_decl-received))<1e-8
        assert min(cashp,cashs)>=-1e-8
        rows.append(dict(year=y,market_nopat=m,digital_nopat=digital,payment_nopat=pay,trade_nopat=trade,project_nopat=project,
          common_profit=common_profit,parent_operating_capital=capitalp,sub_operating_capital=capitals,da=da,maintenance=maintain,project_and_completion_capex=capex,
          organic_market_reinvestment=market_reinvest,digital_reinvestment=digital_reinvest,payment_own_capital=pay_reinvest,trade_wc_addition=trade_wc,
          service_profit=service_profit,spv_profit=spv_profit,service_cash=service_cash,spv_cash=spv_cash,service_legal=service_legal,spv_legal=spv_legal,service_reserve=service_reserve,spv_reserve=spv_reserve,service_receivable=service_recv,spv_receivable=spv_recv,service_new_declaration=service_new,spv_new_declaration=spv_new,parent_capital_injection=inject,subsidiary_profit=subsidiary_profit,sub_legal=legals,sub_statutory_reserve=reserves,payment_retained_capital=.20+protected_payment_capital,sub_cash=cashs,new_sub_declaration=new_decl,sub_cash_received=received,dividend_receivable=receivable,
          parent_profit=parent_profit,parent_legal=legalp,parent_statutory_reserve=reservep,parent_cash=cashp,
          parent_free_cash_before_upstream=pfree,subsidiary_free_cash=sub_free,parent_dividend=div,dps=div/p['shares'],debt=debt,borrowing=draw+planned_draw,debt_repaid=repayment+repay_extra+final_repayment,
          prepaid_fee_revenue=p['prepaid_fee_revenue'][i],project_sale_cash=p['project_net_sale_cash'][i],net_interest=interest,leasing_book=lease,hotel_book=hotel,portfolio_principal=finp+fins+prop+fp+fs,
          portfolio_cash_return=finrelp+finrels+proprel+frelp+frels,portfolio_income=fin_income_p+fin_income_s+fund_income_p+fund_income_s,
          associate_cash_dividends=parent_assoc_cash,cumulative_new_investment=accum_cap))
    assert abs(rows[-1]['portfolio_principal'])<1e-8, 'unresolved property or financial principal omitted'
    return rows

MATURE_COLUMNS=['year','operating_nopat','da','physical_maintenance','growth_investment','land_amortization','land_cash','parent_cash','sub_cash','parent_legal','sub_legal','parent_reserve','sub_reserve','payment_capital','parent_operating_capital','sub_operating_capital','debt','debt_limit','borrowing','debt_repaid','new_sub_declaration','sub_cash_received','dividend_receivable','spv_capital_return','ordinary_dividend','special_dividend','dps','leasing_book','hotel_book','service_cash','spv_cash','service_legal','spv_legal','service_reserve','spv_reserve','service_receivable','spv_receivable','parent_capital_injection']

def terminal(rows,p,r,g):
    # No Gordon or residual NAV shortcut. Explicit legal/cash/capital recursion to Y240.
    a=rows[-1];pc=a['parent_cash'];sc=a['sub_cash'];pl=a['parent_legal'];sl=a['sub_legal']
    pres=a['parent_statutory_reserve'];sres=a['sub_statutory_reserve'];debt=a['debt'];recv=a['dividend_receivable']
    service_cash=a['service_cash'];spv_cash=a['spv_cash'];service_legal=a['service_legal'];spv_legal=a['spv_legal'];service_reserve=a['service_reserve'];spv_reserve=a['spv_reserve'];service_recv=a['service_receivable'];spv_recv=a['spv_receivable']
    cp=a['parent_operating_capital'];cs=a['sub_operating_capital'];paycap=a['payment_retained_capital'];protected=paycap-.20
    lease=a['leasing_book'];hotel=a['hotel_book'];pending=0.;pv=0.;audit=[]
    spv_remaining=max(0,spv_cash-spv_recv)
    owned_spv_netassets=p['sub_cash']-p['sub_cash_floor']+p['sub_financial']+p['sub_other_rights']+sum(z['spv_profit']-z['spv_new_declaration'] for z in rows)
    assert abs(spv_remaining-owned_spv_netassets)<1e-8, 'SPV cash does not reconcile to its own invested capital and retained earnings'
    landstates=[[book*(life-10)/life,life-10,book/life,newcost] for book,life,newcost in p['land_cohorts']]
    gap=max(0,a['da']-p['land_amortization_base']-a['maintenance'])
    last_gross=0.
    for y in range(11,p['mature_last_year']+1):
        n=y-10;factor=(1+g)**n
        pc0,sc0=pc,sc;debt0=debt;recv0=recv;service_cash0=service_cash;spv_cash0=spv_cash
        pfloor=p['parent_cash_floor']*factor;sfloor=p['sub_cash_floor']*factor
        limit=p['debt_limit']*factor
        parent_nopat=(a['market_nopat']+a['project_nopat']+p['other_profit'])*factor
        sub_profit=(a['digital_nopat']+a['payment_nopat']+a['trade_nopat']-p['minority_profit'])*factor
        normalized_nopat=parent_nopat+sub_profit
        landam=0.;landcash=0.
        for ls in landstates:
            if ls[1]==0:
                cost=ls[3]*(p['land_renewal_base']/2.0)*(1+p['land_inflation'])**y
                ls[0]=cost;ls[1]=p['renewed_land_life'];ls[2]=cost/p['renewed_land_life'];landcash+=cost
            amort=min(ls[0],ls[2]);ls[0]-=amort;ls[1]-=1;landam+=amort
        physical_da=(a['da']-p['land_amortization_base'])*factor
        da=physical_da+landam
        parent_nopat+=(p['land_amortization_base']*factor-landam)*.75
        nopat=parent_nopat+sub_profit
        # Historic land amortization ends; actual renewal creates a new finite amortization schedule.
        maintenance=physical_da-gap*max(0,(3-n)/3)
        assert maintenance>=0
        sub_growth=a['digital_nopat']*factor*g/p['digital_incremental_roic']+paycap*g+p['trade_capital']*(1+p['trade_growth'])**10*(1+g)**(n-1)*g
        parent_min=a['market_nopat']*factor*g/p['market_incremental_roic']+a['project_nopat']*factor*g/.05+p['other_profit']*factor*g/.12
        growth=normalized_nopat*g/p['terminal_roic'];parent_growth=growth-sub_growth
        assert parent_growth>=parent_min-1e-9, 'growth capital insufficient for operating units'
        payadd=paycap*g;paycap+=payadd;protected+=payadd
        cp+=maintenance+parent_growth+landcash-da;cs+=sub_growth
        assert min(cp,cs)>0, ('operating capital exhausted',y,cp,cs,p['rent_scale'],p['project_scale'],g)
        lp=lease*p['terminal_leasing_roe'];hp=hotel*p['hotel_roe']
        ld=lp-lease*g;hd=hp-hotel*g;lease+=lease*g;hotel+=hotel*g
        assert ld<=lp*.9+1e-9 and hd<=hp*.9+1e-9
        service_legal,service_reserve,_=reserve_profit(service_legal,service_reserve,sub_profit,p['sub_reserve_cap']*p['service_reserve_share'])
        subcf=sub_profit-sub_growth;service_cash+=subcf
        new=min(max(service_legal-protected,0),max(service_cash-sfloor-service_recv,0))
        service_legal-=new
        service_got=service_recv if p['upstream_lag'] else new
        service_recv=new if p['upstream_lag'] else 0.
        spv_got=spv_recv;spv_recv=0. # old investment dividends, never new legal income
        service_cash-=service_got;spv_cash-=spv_got
        got=service_got+spv_got;recv=service_recv+spv_recv
        inject=max(sfloor-service_cash,0);service_cash+=inject
        sc=service_cash+spv_cash;sl=service_legal+spv_legal;sres=service_reserve+spv_reserve
        interest=debt*p['debt_rate']*.75
        parentcf=parent_nopat+da-maintenance-parent_growth-landcash+ld+hd+got-interest-inject
        pc+=parentcf
        short=max(pfloor-pc,0);draw=short/(1-.5*p['debt_rate']*.75)
        extra_interest=draw*.5*p['debt_rate']*.75;pc-=extra_interest;interest+=extra_interest
        if debt+draw>limit+1e-8:raise ValueError('mature mandatory financing deficit with zero dividends')
        pc+=draw;debt+=draw
        repay=min(max(pc-pfloor,0),debt);pc-=repay;debt-=repay
        parent_profit=parent_nopat+lp+hp+new-interest
        pl,pres,_=reserve_profit(pl,pres,parent_profit,p['shares']*.5)
        pending=min(pending,max(pc-pfloor,0))
        ordinary=0. if p.get('test_zero_mature_dividends',False) else min(max(pl,0),max(pc-pfloor-pending,0));pl-=ordinary;pc-=ordinary
        # Only already-liquidated investment SPV capital can be reduced; old declared dividends reserved.
        capreturn=0.
        if n>=p['cash_release_lag']:
            capreturn=min(spv_remaining,max(spv_cash-spv_recv,0));spv_remaining-=capreturn;spv_cash-=capreturn;sc-=capreturn;pc+=capreturn;pending+=capreturn
        if spv_remaining<1e-9 and spv_cash<1e-9 and spv_recv<1e-9:
            spv_legal=spv_reserve=0. # completed liquidation retires its books, no transfer to service legal pool
        sl=service_legal+spv_legal;sres=service_reserve+spv_reserve
        assert abs(service_cash-service_cash0-subcf+service_got-inject)<1e-6
        assert abs(spv_cash-spv_cash0+spv_got+capreturn)<1e-6
        logistics=p['logistics_book'] if y==15 else 0.
        pc+=logistics;pending+=logistics
        special=0. if p.get('test_zero_mature_dividends',False) else min(pending,max(pl,0),max(pc-pfloor,0));pending-=special;pl-=special;pc-=special
        assert abs(pc-(pc0+parentcf-extra_interest+draw-repay-ordinary+capreturn+logistics-special))<1e-6
        assert abs(sc-(sc0+subcf-got+inject-capreturn))<1e-6
        assert abs(recv-recv0-new+got)<1e-6
        assert pc>=pfloor-1e-7 and sc>=sfloor-1e-7 and debt<=limit+1e-7
        if service_legal<0:assert new==0
        assert service_cash>=sfloor-1e-7 and spv_cash>=-1e-7
        if pl<0:assert ordinary+special==0
        dividend=ordinary+special;pv+=dividend/(1+r)**n
        land_upper=sum(z[2] for z in p['land_cohorts'])*(p['land_renewal_base']/2.0)*(1+p['land_inflation'])**y/p['renewed_land_life']
        last_gross=normalized_nopat+physical_da+.75*p['land_amortization_base']*factor+.25*max(landam,land_upper)+lp+hp
        audit.append([y,nopat,da,maintenance,growth,landam,landcash,pc,sc,pl,sl,pres,sres,paycap,cp,cs,debt,limit,draw,repay,new,got,recv,capreturn,ordinary,special,dividend/p['shares'],lease,hotel,service_cash,spv_cash,service_legal,spv_legal,service_reserve,spv_reserve,service_recv,spv_recv,inject])
    # Upper bound within THIS continuing policy: ignore every future expense and distribute all cash.
    # All remaining positive recurring gross inflows grow no faster than g; land inflation <= g.
    assert spv_remaining<1e-8, 'SPV principal left without release or operating use'
    tail_bound=(pc+sc+last_gross*(1+g)/(r-g))/(1+r)**(p['mature_last_year']-10)
    assert tail_bound/(1+r)**10/p['shares']<p.get('tail_error_tolerance',.0001), 'truncation material'
    return dict(equity=pv,annual=audit,last_year=p['mature_last_year'],tail_error_bound_at_year10=tail_bound,
      tail_error_bound_per_share_today=tail_bound/(1+r)**10/p['shares'],remaining_spv_capital=spv_remaining,
      min_parent_operating_capital=min(z[14] for z in audit),min_sub_operating_capital=min(z[15] for z in audit))

def value(rows,p,r,g):
    t=terminal(rows,p,r,g); d=[a['parent_dividend'] for a in rows]
    tv5=present_value(d[5:],t['equity'],r)
    pv=present_value(d[:5],tv5,r)
    return dict(pv=pv/p['shares'],tv5=tv5/p['shares'],tv10=t['equity']/p['shares'],terminal_detail=t,
     pv_terminal_fraction=(tv5/(1+r)**5)/pv,r=r,g=g)

def auxiliary(p):
    # A separately normalized no-growth earnings-power plus dated net-asset realization view.
    # NOT projected base path or the DCF terminal identity. Cap rates refer to after-tax, maintained cash.
    out=[]
    for rentcash,caprate,service,pe,propertyloss,leasepb,projectnpv in [(1.20,.085,.13,12,.565,1.2,-2.1),(1.50,.075,.20,15,0,1.5,-1.2)]:
        liquid=(2.79655471338-.66436108531-.060)/1.09
        property_nav=(3.61962308727-propertyloss)/1.09**6
        funds=(1.70611541374-.102918559)/1.09**7
        frozen=(.66436108531+.102918559)/1.09**10
        lease=.69151935555*leasepb; hotel=.51990495872; logistics=.1485060792/1.09**10
        deposits=.45/1.09**2+.50/1.09**3
        assetrec=liquid+property_nav+funds+frozen+lease+hotel+logistics+deposits
        market=rentcash/caprate; services=service*pe
        equity=market+services+assetrec+projectnpv +p['parent_cash']+p['sub_cash']-p['old_dividend_payable']-p['debt']-1.0
        out.append(dict(rent_cash=rentcash,capitalization_rate=caprate,market_value=market,service_profit=service,service_multiple=pe,service_value=services,
          asset_components=dict(liquid=liquid,property=property_nav,funds=funds,frozen=frozen,leasing=lease,hotel=hotel,logistics=logistics,deposits=deposits),
          net_investment_rights_value=assetrec,unfinished_projects_net_value=projectnpv,value=equity/p['shares']))
    return out

def self_tests():
    assert abs(present_value([10]*5,100,.1)-100)<1e-10
    c,l,d,b,draw=settle_cash(30,50,10,5,0,0)
    assert (c,l,d,b,draw)==(20,40,10,0,0)
    assert reserve_profit(-5,0,3,10)==(-2,0,0)
    assert all(abs(a-b)<1e-12 for a,b in zip(reserve_profit(-2,0,5,10),(2.7,.3,.3)))
    try: settle_cash(-10,100,0,1,0,5)
    except ValueError: pass
    else: raise AssertionError('zero-dividend failure test missing')
    # Formal simulator must fail, not merely a separate liquidity identity.
    q=copy.deepcopy(P);q.update(payout=0,debt_limit=3.2,extra_commitment=1)
    try:simulate(q)
    except ValueError:pass
    else:raise AssertionError('formal zero dividend model incorrectly rescued')
    constant=copy.deepcopy(P);constant.update(shares=1.,other_profit=0.,minority_profit=0.,trade_capital=0.,land_cohorts=[],land_amortization_base=0.,logistics_book=0.,debt_limit=0.,sub_financial=0.,sub_other_rights=0.,sub_cash=.2)
    row=dict(spv_profit=0.,spv_new_declaration=0.,service_cash=.2,spv_cash=0.,service_legal=0.,spv_legal=0.,service_reserve=1.,spv_reserve=0.,service_receivable=0.,spv_receivable=0.,parent_cash=.8,sub_cash=.2,parent_legal=100.,sub_legal=0.,parent_statutory_reserve=.5,sub_statutory_reserve=1.,debt=0.,dividend_receivable=0.,parent_operating_capital=20.,sub_operating_capital=2.,payment_retained_capital=.2,leasing_book=0.,hotel_book=0.,da=0.,maintenance=0.,market_nopat=1.,digital_nopat=0.,payment_nopat=0.,trade_nopat=0.,project_nopat=0.)
    exact=terminal([row],constant,.10,0.)
    assert abs(exact['equity']-10*(1-1.1**-230))<1e-10
    # Actual mature engine: zero ordinary AND special dividends do not conjure renewal financing.
    failure=copy.deepcopy(constant);failure.update(land_cohorts=[[0.,11,100.]],test_zero_mature_dividends=True)
    try:terminal([row],failure,.10,0.)
    except ValueError:pass
    else:raise AssertionError('mature zero-dividend renewal deficit incorrectly rescued')
    return {'formal_pv_hand_case':'pass','formal_cash_hand_case':'pass','loss_and_reserve_case':'pass','formal_zero_dividend_insolvency':'pass','formal_mature_cash_annuity_hand_case':'pass','formal_mature_zero_dividend_insolvency':'pass'}

def main():
    scenarios={'base':{},'cyclical':{'rent_scale':.90,'digital_scale':.80,'market_growth':[0,.04,.04,.03,.025,.025,.025,.025,.025,.025],'project_profit':[0,0,0,0,.04,.10,.14,.16,.17,.17],'parent_wc_extra':[.6,.3,-.3,-.3,0,0,0,0,0,0],'upstream_lag':1},
      'structural':{'rent_scale':.82,'digital_scale':.65,'market_growth':[0,.01,.01,.01,.01,.01,.01,.01,.01,.01],'digital_growth':[.03]*10,'pay_growth':[.08]*10,'project_scale':.55,'capex_scale':1.2,'property_loss':1.13,'portfolio_yield':.01,'payout':.4,'debt_rate':.045},
      'upside':{'market_growth':[.07]*5+[.05,.04,.03,.025,.02],'digital_growth':[.15]*5+[.10,.08,.06,.04,.03],'pay_growth':[.30]*5+[.15,.10,.08,.05,.03],'project_scale':1.15},
      'rent_growth_minus_2pp_y2_on':{'market_growth':[.025]+[.005]*9},
      'capex_overrun_20pct_y1_y5':{'capex_scale':1.2},
      'no_new_admission_fee_y1_on':{'market_revenue':2.95},'new_admission_fee_double_y1_on':{'market_revenue':3.25},'spv_opening_legal_loss_1_5bn':{'spv_opening_legal':-1.5},'sub_reserve_cap_1bn':{'sub_reserve_cap':1.0},'sub_reserve_cap_0_5bn':{'sub_reserve_cap':.5},'sub_reserve_cap_2bn':{'sub_reserve_cap':2.0},'sub_reserve_never_stops':{'sub_reserve_cap':1000000.0},'upstream_delay_1y':{'upstream_lag':1},'payment_profit_minus_25pct_y1_on':{'pay_profit':.01875},'frozen_asset_half_loss_y1':{'frozen_loss_fraction':.5},'logistics_zero_recovery':{'logistics_book':0},'land_renewal_double':{'land_renewal_base':4.0},'sub_capital_return_delayed_5y':{'cash_release_lag':5},
      'extra_net_payment_1bn_y1':{'extra_commitment':1},
      'refinancing_reduction_1bn_y3':{'loan_call':1.,'debt_limit':7.0},
      'property_asset_loss_10pct_y1':{'property_loss':1.13},
      'project_profit_minus_30pct_y4_on':{'project_scale':.7}}
    output={'units':'CNY billion; shares billion; per share CNY','as_of':'2026-10-26','inputs':P,'tests':self_tests(),'mature_columns':MATURE_COLUMNS,'scenarios':{}}
    for name,change in scenarios.items():
        p=copy.deepcopy(P);p.update(change)
        try:
            rows=simulate(p)
            output['scenarios'][name]={'changes':change,'annual':rows,'low':value(rows,p,.095,.02),'high':value(rows,p,.085,.025)}
        except ValueError as e:output['scenarios'][name]={'changes':change,'feasible':False,'reason':str(e)}
    output['auxiliary']=auxiliary(P)
    base=output['scenarios']['base']; output['core']={'low':round(base['low']['pv'],2),'high':round(base['high']['pv'],2),
        'distributions':[round(a['dps'],6) for a in base['annual'][:5]],'tv5_low':round(base['low']['tv5'],2),'tv5_high':round(base['high']['tv5'],2)}
    Path(__file__).with_name('2026-Q3-output.json').write_text(json.dumps(output,ensure_ascii=False,separators=(',',':'),sort_keys=True)+'\n')
    print(json.dumps(output['core'],ensure_ascii=False));print('tests',output['tests'])
if __name__=='__main__':main()
