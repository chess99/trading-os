"""Anhui Heli ordinary-equity cash model. All money CNY billion; no inputs/files/network.
Units M=listed legal parent, S=mature subsidiaries consolidated proxy, Y=Yufeng.
S minority 25% is weighted-budget parameter, not each subsidiary ownership.
Internal support is parent loan and never consolidated income.
"""
import json, math
SHARES=.890692761

def statutory_transfer(retained, income, paid_capital, statutory):
    return min(max(0,.5*paid_capital-statutory),.1*max(0,income+min(retained,0)))

def exit_waterfall(net,loan,equity_cost,ownership):
    recovery=min(loan,max(0,net)); residual=max(0,net-loan)
    parent_cash=recovery+ownership*residual+min(0,net)
    minority_cash=(1-ownership)*residual
    loss=equity_cost-ownership*residual+loan-recovery+max(0,-net)
    assert abs(parent_cash+minority_cash-net)<1e-8
    return dict(parent_cash=parent_cash,minority_cash=minority_cash,loan_recovery=recovery,equity_recovery=ownership*residual,parent_legal_loss=loss)

def step(cash, retained, debt, nopat, reinvest, reserve, principal, payout, interest_rate=.035, yield_rate=.02, extra=0, receipt=0, support=0,paid_capital=0,statutory=0):
    interest=debt*interest_rate
    income=nopat-interest+cash*yield_rate
    available=cash+income-reinvest-principal+receipt-support
    allocation=statutory_transfer(retained,income+receipt,paid_capital,statutory)
    legal=max(0,retained+income+receipt-allocation)
    ordinary=max(0,income+receipt)*payout
    distribution=max(0,min(ordinary+extra,legal,available-reserve))
    end=available-distribution
    assert end>=reserve*(1-1e-10)-1e-8
    assert math.isclose(end+distribution,cash+income-reinvest-principal+receipt-support,rel_tol=1e-10,abs_tol=1e-8)
    return dict(paid_capital=paid_capital,statutory_start=statutory,statutory_allocation=allocation,statutory_end=statutory+allocation,cash_start=cash,retained_start=retained,debt_start=debt,nopat=nopat,interest=interest,financial_income=cash*yield_rate,net_income=income,reinvestment=reinvest,principal=principal,receipt=receipt,support=support,reserve=reserve,distribution=distribution,cash_end=end,retained_end=retained+income+receipt-allocation-distribution,debt_end=debt-principal)

CASES={
'base':dict(dom=[12,12.5,13,13.4,13.8],over=[10.3,11.1,11.9,12.7,13.5],dm=[.05,.052,.054,.055,.055],om=[.105,.108,.11,.11,.11],yr=[.8,.88,.98,1.1,1.22],ye=[-.12,-.08,-.03,.02,.05],cap=[.90,.95,.90,.85,.80],wc=.20,delay=0),
'cyclical':dict(dom=[10.8,11.3,12.2,13.1,13.8],over=[9.1,9.7,10.9,12.1,13.2],dm=[.035,.04,.048,.052,.055],om=[.08,.087,.10,.105,.11],yr=[.65,.7,.8,.95,1.1],ye=[-.17,-.13,-.07,-.01,.025],cap=[.80,.80,.85,.85,.8],wc=.23,delay=.35),
'structural':dict(dom=[10.8,10.4,10.2,10.2,10.3],over=[9.2,9.1,9.0,9.1,9.2],dm=[.035,.03,.028,.028,.028],om=[.075,.07,.065,.065,.065],yr=[.6,.5,.45,.45,.45],ye=[-.16,-.10,-.04,0,.009],cap=[.80,.70,.60,.55,.50],wc=.25,delay=.5),
'optimistic':dict(dom=[12.5,13.3,14.1,14.8,15.5],over=[11,12.3,13.7,15,16.3],dm=[.055,.058,.06,.06,.06],om=[.11,.115,.12,.12,.12],yr=[.9,1.05,1.25,1.5,1.75],ye=[-.08,-.02,.04,.08,.12],cap=[1.05,1.10,1.10,1.05,1.0],wc=.20,delay=0)}

def forecast(case='base',margin_shift=0,nci_s=.25,horizon=1000,convert=False,legal_case='base'):
    p=CASES[case]; M=dict(cash=4.4,retained=5.7,debt=1.035);S=dict(cash=1.2,retained=2.0,debt=.50);Y=dict(cash=.06,retained=-.12,debt=.245)
    oldr=21.5; oldyr=.8; loan=0.; rows=[]; K=9.; yK=.4802694
    book_invest=.705
    shares=SHARES; ms=1.13178883522; ss=.60; ys=.01; ycap=.116800964; mcap=SHARES
    scap=3.
    if legal_case=='low_headroom':scap=4.;ss=.2;ys=0;S['retained']=.5
    if legal_case=='high_headroom':scap=2.;ss=.8;ys=.05;S['retained']=3.
    group_equity=5.66+K+yK+book_invest-1.78
    for t in range(1,horizon+1):
        conversion=0
        if convert and t==3:
            conversion=.23371
            M['debt']-=conversion
            shares+=conversion/12.55
            mcap+=conversion/12.55
        if t<=5:
            d,o=p['dom'][t-1],p['over'][t-1]; dm,om=p['dm'][t-1],p['om'][t-1];yr=p['yr'][t-1];ye=p['ye'][t-1];cap=p['cap'][t-1];da=.42+.03*t
        else:
            growth=p.get('g',(.04 if case=='optimistic' else .03 if case=='base' else .025 if case=='cyclical' else .01) if t<=10 else (.02 if case!='structural' else .01))
            d*=1+growth;o*=1+growth;yr*=1+growth
            # Mature margin fades after year ten; no permanent peak extrapolation.
            dm+=((.05 if case!='structural' else .028)-dm)*(.2 if t>10 and not case.startswith('secondary') else 0)
            om+=((.10 if case!='structural' else .065)-om)*(.2 if t>10 and not case.startswith('secondary') else 0)
            ye=yr*(.04 if case in ('base','cyclical') or case.startswith('secondary') else .06 if case=='optimistic' else .02)
            da=.02*(d+o);cap=da+.25*((d+o)-oldr)
        if case=='structural' and t>3:
            yr=0;ye=0
        r=d+o; ebit=d*(dm+margin_shift)+o*(om+margin_shift);nopat=ebit*.82
        # Delayed receipts stress is absorbed in WC permanently, not presumed recovered.
        wc=p['wc']*(r-oldr)+(p['wc']-.20)*oldr*(t==1)+p['delay']*(t==1)
        reinv=cap-da+wc;K+=reinv
        yreinv=(.03 if t<=2 else .02)-.02+.20*(yr-oldyr)
        if case=='structural' and t>3: yreinv=0
        yK+=yreinv
        yp=min(Y['debt'],[.135,.06,.05,0,0][t-1] if t<=5 else 0); yinterest=Y['debt']*.055
        yn=ye*(.82 if ye>0 else 1)-yinterest
        yc0=Y['cash']; yavailable=yc0+yn-yreinv-yp; yreserve=.1*yr
        funding=max(0,yreserve-yavailable);loan+=funding;yavailable+=funding
        repayment=min(loan,max(0,yavailable-yreserve));loan-=repayment;yavailable-=repayment
        ya=statutory_transfer(Y['retained'],yn,ycap,ys)
        ys0=ys;ys+=ya
        ylegal=max(0,Y['retained']+yn-ya)
        ydiv=min(ylegal,max(0,yavailable-yreserve))
        Y=dict(cash=yavailable-ydiv,retained=Y['retained']+yn-ya-ydiv,debt=Y['debt']-yp)
        assert math.isclose(Y['cash']+ydiv+repayment,yc0+yn-yreinv-yp+funding,rel_tol=1e-10,abs_tol=1e-8)
        exit_cash=0; exit_legal_loss=0; exit_detail=None
        if case=='structural' and t==3:
            gross_non_cash=1.256552+(yK-.4802694)
            recover=gross_non_cash*.70
            trade_claims=.7762826
            closure=.08
            net=recover+Y['cash']-trade_claims-Y['debt']-closure
            oldloan=loan
            waterfall=exit_waterfall(net,oldloan,.452605166,.7342)
            exit_cash=waterfall['parent_cash']
            exit_legal_loss=waterfall['parent_legal_loss']
            exit_detail=dict(**waterfall,statutory_before_exit=ys,paid_capital_before_exit=ycap,assets_after_exit=0,liabilities_after_exit=0,paid_capital_after_exit=0,parent_investment_after_exit=0,gross_non_cash=gross_non_cash,recovery=recover,trade_claims=trade_claims,external_principal=Y['debt'],closure=closure,net=net,parent_equity_cost=.452605166,parent_loan_cost=oldloan)
            loan=0;ys=0;ycap=0;Y=dict(cash=0,retained=0,debt=0)
        sp=min(S['debt'],[.25,.15,.10,0,0][t-1] if t<=5 else 0)
        sx=max(0,S['cash']-.03*r)*(.15 if t<=5 else 1)
        sr=step(**S,paid_capital=scap,statutory=ss,nopat=nopat*.45,reinvest=reinv*.45,reserve=.03*r,principal=sp,payout=.55 if t<=5 else 1,extra=sx)
        ss=sr['statutory_end']
        S=dict(cash=sr['cash_end'],retained=sr['retained_end'],debt=sr['debt_end'])
        receipt=(1-nci_s)*sr['distribution']+.7342*ydiv
        mp=min(M['debt'],([.60,.20,0,.00129,0] if convert else [.60,.20,.15,.085,0])[t-1] if t<=5 else 0)
        # Actual subsidiary dividend recognition and cash receipt coincide in budget;
        # loan repayment is not dividend income, implemented separately in opening cash.
        M['cash']+=repayment+exit_cash
        M['retained']-=exit_legal_loss
        investment_sale=.50 if t==15 else 0
        if t==15:
            M['cash']+=investment_sale
            M['retained']-=.205  # loss against .705 carrying value, no second cash deduction
        mx=max(0,M['cash']-.06*r)*(.05 if t<=5 else 1)
        mr=step(**M,paid_capital=mcap,statutory=ms,nopat=nopat*.55+(.022 if t<15 else 0),reinvest=reinv*.55,reserve=.06*r,principal=mp,payout=.50 if t<=5 else 1,extra=mx,receipt=receipt,support=funding)
        ms=mr['statutory_end']
        M=dict(cash=mr['cash_end'],retained=mr['retained_end'],debt=mr['debt_end'])
        consolidated_cash=M['cash']+S['cash']+Y['cash'];nci=nci_s*sr['distribution']+.2658*ydiv+(exit_detail['minority_cash'] if exit_detail else 0)
        startcash=mr['cash_start']-repayment-investment_sale-exit_cash+sr['cash_start']+yc0
        totalincome=mr['net_income']+sr['net_income']+yn
        liquidation_external=(exit_detail['recovery']-exit_detail['trade_claims']-exit_detail['external_principal']-exit_detail['closure']) if exit_detail else 0
        assert math.isclose(consolidated_cash+mr['distribution']+nci,startcash+totalincome-reinv-yreinv-mp-sp-yp+investment_sale+liquidation_external,rel_tol=1e-10,abs_tol=1e-7)
        old_equity=group_equity
        book_loss=.205 if t==15 else 0
        if t==15: book_invest=0
        exit_loss=0
        if exit_detail:
            exit_loss=yK+exit_detail['trade_claims']-exit_detail['recovery']+exit_detail['closure']
            yK=0
        group_equity=consolidated_cash+K+yK+book_invest-M['debt']-S['debt']-Y['debt']
        assert math.isclose(group_equity,old_equity+totalincome-mr['distribution']-nci-book_loss-exit_loss+conversion,rel_tol=1e-10,abs_tol=1e-6)
        rows.append(dict(shares=shares,conversion=conversion,parent_investment_Y=0 if case=='structural' and t>=3 else .452605166,group_equity=group_equity,group_equity_start=old_equity,noncore_book_loss=book_loss,exit_asset_loss=exit_loss,year=t,domestic=d,overseas=o,yufeng_revenue=yr,mature_ebit=ebit,yufeng_ebit=ye,capex=cap,DA=da,WC_change=wc,noncash_operating_capital=K,yufeng_capital=yK,parent=mr,subs=sr,yufeng=dict(paid_capital=ycap,statutory_start=ys0,statutory_allocation=ya,statutory_end=ys,cash_start=yc0,net_income=yn,interest=yinterest,principal=yp,reinvestment=yreinv,support=funding,loan_repayment=repayment,loan_end=loan,cash_end=Y['cash'],retained_end=Y['retained'],debt_end=Y['debt'],distribution=ydiv),investment_sale=investment_sale,yufeng_exit=exit_detail,nci_distribution=nci,common_distribution=mr['distribution'],common_eps_distribution=mr['distribution']/shares,consolidated_cash=consolidated_cash,common_earnings=mr['net_income']+(1-nci_s)*sr['net_income']+.7342*yn))
        oldr=r;oldyr=yr
    return rows

def valuation(rows,r,g):
    n=len(rows)
    ds=[z.get('common_eps_distribution',z['common_distribution']/SHARES) for z in rows]
    observed=ds[-1]/ds[-2]-1
    assert abs(observed-g)<1e-5,(observed,g)
    terminal=ds[-1]*(1+observed)/(r-observed)
    pv=sum(d/(1+r)**(i+1) for i,d in enumerate(ds))+terminal/(1+r)**n
    fifth=sum(d/(1+r)**(i+1-5) for i,d in enumerate(ds) if i>=5)+terminal/(1+r)**(n-5)
    return dict(current_per_share=pv,year5_per_share=fifth,terminal_pv_share=terminal/(1+r)**n/pv,observed_terminal_distribution_growth=observed)

def add_secondary():
    for key,dm,om,pm,g in [('secondary_low',.045,.095,.07,.015),('secondary_high',.055,.11,.08,.02)]:
        d,o=10.06,11.31
        CASES[key]=dict(dom=[d*(1+g)**i for i in range(5)],over=[o*(1+g)**i for i in range(5)],dm=[(8.06*dm+2*pm)/d]*5,om=[(9.31*om+2*pm)/o]*5,yr=[.8,.88,.98,1.1,1.22],ye=[-.12,-.08,-.03,.02,.05],cap=[.9,.95,.9,.85,.8],wc=.20,delay=0,g=g)

def convergence(a,b):
    def normalized(z):
        revenue=z['domestic']+z['overseas']+z['yufeng_revenue']
        items={'K':z['noncash_operating_capital'],'YK':z['yufeng_capital'],'E':z['group_equity'],'D':z['common_distribution'],'shares':z['shares']}
        for unit in ['parent','subs','yufeng']:
            for f in ['cash_end','retained_end','debt_end','statutory_end','paid_capital']:
                items[unit+'_'+f]=z[unit][f]
        items['loan']=z['yufeng']['loan_end']
        return {k:(v if k=='shares' or any(q in k for q in ['statutory','paid_capital','debt_end','loan']) else v/revenue) for k,v in items.items()}
    x,y=normalized(a[-1]),normalized(b[-1]);d={k:abs(x[k]-y[k]) for k in x}
    relative={k:d[k]/max(abs(x[k]),abs(y[k]),1e-12) for k in x}
    assert max(d.values())<1e-4 and max(relative.values())<1e-4,(d,relative)
    assert b[-1]['yufeng']['loan_end']==0
    return dict(horizons=[len(a),len(b)],normalized_state_a=x,normalized_state_b=y,absolute_differences=d,max_difference=max(d.values()),relative_differences=relative,max_relative_difference=max(relative.values()),absolute_tolerance=1e-4,relative_tolerance=1e-4,scale='growing cash/capital/RE/equity/distribution divided by total external revenue; fixed statutory/paid capital/shares and zero debt/loan unscaled',distribution_growth=[a[-1]['common_distribution']/a[-2]['common_distribution']-1,b[-1]['common_distribution']/b[-2]['common_distribution']-1])

def test():
    a=step(cash=10,retained=20,debt=2,nopat=4,reinvest=1,reserve=5,principal=1,payout=.5,interest_rate=.5,yield_rate=0)
    assert a['net_income']==3 and a['distribution']==1.5 and a['cash_end']==9.5 and a['debt_end']==1 and a['retained_end']==21.5
    b=step(cash=10,retained=0,debt=0,nopat=2,reinvest=0,reserve=11,principal=0,payout=1,yield_rate=0)
    assert b['distribution']==1 and b['cash_end']==11
    c=step(cash=20,retained=-2,debt=0,nopat=5,reinvest=0,reserve=0,principal=0,payout=1,yield_rate=0,paid_capital=10,statutory=4.8)
    assert abs(c['statutory_allocation']-.2)<1e-10 and abs(c['distribution']-2.8)<1e-10
    e=exit_waterfall(10,2,3,.75)
    assert e['parent_cash']==8 and e['minority_cash']==2 and e['parent_legal_loss']==-3
    v=valuation([dict(year=t,common_distribution=1) for t in range(1,121)],.10,0)
    assert abs(v['current_per_share']-10/SHARES)<1e-10
    assert abs(v['year5_per_share']-10/SHARES)<1e-10

def main():
    add_secondary();test();out={'units':'CNY billion, shares billion','shares':SHARES,'annual':{},'valuations':{},'convergence':{},'tests':'production statutory, exit, cash, equity and perpetuity hand cases passed'}
    for c in CASES:
        z=forecast(c);ext=forecast(c,horizon=1200);out['annual'][c]=z;out['convergence'][c]=convergence(z,ext)
        g=CASES[c].get('g',.01 if c=='structural' else .02)
        rs=[.115,.105] if c=='structural' else [.105,.095]
        out['valuations'][c]=[valuation(z,r,g) for r in rs]
        out['convergence'][c]['extended_values']=[valuation(ext,r,g) for r in rs]
    out['secondary']=[out['valuations']['secondary_low'][0],out['valuations']['secondary_high'][1]]
    out['sensitivity_margin_minus_1pp']=[valuation(forecast('base',-.01),r,.02) for r in [.105,.095]]
    out['sensitivity_mature_minority']={str(n):[valuation(forecast('base',0,n),r,.02) for r in [.105,.095]] for n in [.20,.30]}
    out['legal_range']={}
    for legal in ['low_headroom','high_headroom']:
        zz=forecast(legal_case=legal);out['annual'][legal]=zz;out['convergence'][legal]=convergence(zz,forecast(legal_case=legal,horizon=1200))
        out['legal_range'][legal]=[valuation(zz,r,.02) for r in [.105,.095]]
    cz=forecast(convert=True);out['annual']['conversion']=cz;out['convergence']['conversion']=convergence(cz,forecast(convert=True,horizon=1200))
    out['conversion']=[valuation(cz,r,.02) for r in [.105,.095]]
    print(json.dumps(out,ensure_ascii=False,separators=(',',':'),sort_keys=True))
if __name__=='__main__':main()
