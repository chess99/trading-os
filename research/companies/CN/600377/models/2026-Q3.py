#!/usr/bin/env python3
"""Fresh 600377 Q3 snapshot. CNY billion throughout. Standard library, no external inputs.
Finite assets and conditional legal-entity budgets, NOT completed whole-company equity value.
"""
import json,copy
from datetime import date
ASOF=date(2026,10,27)
S=5.0377475

def finite(c,n,k):
    z=int(n);return sum(c/(1+k)**t for t in range(1,z+1))+(n-z)*c/(1+k)**n

def legal(retained,reserve,capital,profit):
    # Signed distributable capacity is retained+profit minus appropriation, NOT clipped.
    provision=min(max(0,capital*.5-reserve),.1*max(0,profit-max(0,-retained)))
    return retained+profit-provision,reserve+provision,provision

RAW=[('沪宁',2700960892.79,855384836.49,376232401.42,15243,1,'2032-06-26'),
('宁常镇溧',551384766.22,229251711.79,143144566.80,3165,1,'2032-09-30'),
('广靖锡澄',339931743.92,93479074.20,36773614.54,2056,.85,'2029-09-30'),
('锡宜',377616267.35*1858/2177,188861393.97*1858/2177,126583291.60*1858/2177,1858,.85,'2028-09-30'),
('环太湖',377616267.35*319/2177,188861393.97*319/2177,126583291.60*319/2177,319,.85,'2031-10-31'),
('镇丹',39653824.14,34582194.95,20282275.62,228,.7,'2043-09-30'),
('常宜',89311059.34,72304177.54,56011564.34,513,.51,'2045-12-31'),
('宜长',58540602.78,60125927.34,28439892.61,336,.51,'2046-01-31'),
('五峰山',684218099.66,228282743.83,199538751.14,3827,.645,'2046-06-30')]

def roads(k=.08,revfactor=1,extra_years=0):
    rows=[]
    for name,r,c,a,d,own,end in RAW:
        w=r/4869625851.68;da=2*a/1e9+.35906*w
        revenue=d*365/1e6*revfactor;cost=(2*c/1e9-da)*(.8+.2*revfactor)
        profit=(revenue-cost-da-.24*w)*.75;fcff=profit+da-.45*w
        n=(date.fromisoformat(end)-ASOF).days/365.25+extra_years
        rows.append(dict(name=name,ownership=own,revenue=revenue,cash_cost=cost,da=da,
         hq=.24*w,maintenance=.45*w,nopat=profit,fcff=fcff,years=n,end=end,
         asset_pv=finite(fcff,n,k)*own,earnings_capacity=finite(profit,n,k)*own))
    return dict(k=k,rows=rows,asset_pv=sum(r['asset_pv'] for r in rows),earnings_capacity=sum(r['earnings_capacity'] for r in rows))

REV=[.8359040,.8347178,.9865573,1.3182117,1.6284611,1.7220946,1.6203144,1.6892767,1.7578899,1.8240535,1.8835016,2.0191427,2.0720048,2.1232165,2.1746221,2.2082863,2.2461267,2.2808593,2.3158514,2.3321400,2.3360742]
COST=[.5046278,.5167555,.5721463,.6912377,.8030196,.7556197,.7154970,.7497565,.7826553,.8149913,1.3029967,.8962447,.9198894,.9431964,.9649563,.9847617,1.0042013,1.0227908,1.0396023,1.0544290,1.0677206]
DA=[.3911386,.3999634,.4511798,.5646252,.6708385,.6194498,.5767522,.6070248,.6358412,.6640125,.6881443,.7361373,.7553986,.7742214,.7913789,.8065986,.8212966,.8350414,.8468751,.8567337,.8650137]
FCFF=[.9709698,.6308389,.7779357,.9941980,1.2292371,1.2773332,1.1981430,1.2515281,1.3054863,1.3577290,1.0725373,1.4959654,1.5505666,1.5884043,1.6256304,1.6500560,1.6752745,1.6987506,1.7216783,1.7310729,1.7303958]

def appraisal(k=.0703):
    rows=[dict(year=2026+i,fcff=c,discount_time=i+.5,pv=c/(1+k)**(i+.5)) for i,c in enumerate(FCFF)]
    terminal=.0267511/(1+k)**21
    enterprise=sum(x['pv'] for x in rows)+terminal-.1713209
    return dict(rows=rows,k=k,as_of='2025-12-31',equity=enterprise-6.3292886,enterprise=enterprise,
     terminal_pv=terminal,terminal_share=terminal/(enterprise+.1713209),debt=6.3292886,nonoperating=-.1713209,
     caveat='Old sent-for-review appraisal reconstructed, not final filed table or adopted investment value')

FINAL_2026_PROFIT=.1743513
FINAL_PROFITS=[.1743513,.1607533,.2574664]
JULY_TAX_LOSSES={2027:.25501091221,2028:.21484021663,2029:.18955235984}

def tax_calc(ebt,losses,year,enabled=True):
    left=dict(losses);used=0
    if enabled:
        for expiry in sorted(left):
            if expiry>=year:
                take=min(left[expiry],max(0,ebt-used));left[expiry]-=take;used+=take
    return .25*max(0,ebt-used),used,left

def target(name,factors,rate=.025,credit=.5,shield=True):
    retained=-.67964151799+FINAL_2026_PROFIT;reserve=.00006495307;debt=5.903825;cash=.05;rows=[]
    # Book pretax proxy for Aug-Dec26; FINAL forecast is net profit while tax-loss utilisation assumes no current tax.
    losses=dict(JULY_TAX_LOSSES)
    _,used2026,losses=tax_calc(FINAL_2026_PROFIT-.09188183074,losses,2026,shield)
    opening_losses=dict(losses)
    for i in range(20):
        year=2027+i;j=i+1;f=factors[i];begin_cash=cash;begin_debt=debt;begin_retained=retained;oldreserve=reserve
        rev=REV[j]*f;cashcost=(COST[j]-DA[j])*(.8+.2*f);ebit=rev-cashcost-DA[j]-.0035
        principal=debt/(20-i);capex=.0480065*1.03**i;draw=0
        for _ in range(100):
            interest=debt*rate+draw*rate*.5;ebt=ebit-interest
            tax,used,left=tax_calc(ebt,losses,year,shield);profit=ebt-tax
            before=begin_cash+profit+DA[j]-capex-principal
            nd=min(credit,max(0,.05-before))
            if abs(nd-draw)<1e-13:break
            draw=nd
        signed,reserve,provision=legal(begin_retained,oldreserve,7.9562,profit)
        expired=sum(v for y,v in left.items() if y<=year)
        losses={y:v for y,v in left.items() if y>year}
        available=before+draw;div=min(max(0,signed),max(0,available-.05))
        cash=available-div;retained=signed-div;debt=begin_debt-principal+draw
        assert abs(cash-(begin_cash+profit+DA[j]-capex-principal+draw-div))<1e-8
        assert div<=max(0,signed)+1e-8 and reserve<=7.9562*.5+1e-8
        rows.append(dict(year=year,revenue=rev,volume_factor=f,cash_cost=cashcost,da=DA[j],ebit=ebit,
         begin_cash=begin_cash,begin_debt=begin_debt,begin_retained=begin_retained,interest=interest,pretax=ebt,
         tax=tax,known_tax_loss_used=used,known_tax_loss_expired=expired,remaining_tax_losses=losses.copy(),
         profit=profit,cfo=profit+DA[j],maintenance_capex=capex,principal_repayment=principal,new_debt=draw,
         reserve_added=provision,reserve=reserve,signed_legal_capacity=signed,retained=retained,
         dividend=div,end_cash=cash,end_debt=debt,feasible=cash>=.05-1e-8))
        if cash<.05-1e-8: break
    feasible=len(rows)==20 and all(r['feasible'] for r in rows)
    release=max(0,cash-debt-.05) if feasible else None
    pv=sum(r['dividend']/1.08**(r['year']-2026) for r in rows)
    tv5=sum(r['dividend']/1.08**(r['year']-2031) for r in rows if r['year']>2031)
    if feasible:pv+=release/1.08**21;tv5+=release/1.08**16
    return dict(name=name,rows=rows,feasible=feasible,liquidation_2047=release,equity_pv_2026end=pv if feasible else None,
     residual_equity_2031end=tv5 if feasible else None,liquidation_pv_fraction=release/1.08**21/pv if feasible and pv else None,
     shield=shield,final_2026_net_profit=FINAL_2026_PROFIT,final_2026_28_forecast=FINAL_PROFITS,
     july_tax_loss_vintages=JULY_TAX_LOSSES,aug_dec26_tax_loss_consumed=used2026,opening_tax_loss_vintages=opening_losses,
     caveat='Tax base approximates accounting pretax; use only disclosed loss vintages, no newly generated losses. Opening free cash50m is a forecast, not July actual194.233m. Not legal approval.')

def onlend_bridge(target_result,rate=.021,delay=False):
    # Conditional Jan2027 replacement after closing. Approved balance ceiling CNY6bn; CNY12bn transient settlement is NOT added.
    balance=5.903825;interest_receivable=0;rows=[]
    initial=dict(parent_external_draw=balance,parent_loan_to_target=balance,target_new_parent_debt=balance,
      target_bank_repaid=balance,group_net_new_debt=0,group_net_new_cash=0,approved_balance_ceiling=6,
      transient_settlement_ceiling=12,transient_balance_recognised=0,executed_fact=False)
    for r in target_result['rows']:
        begin=balance;principal=r['principal_repayment']*begin/r['begin_debt']
        accrual=begin*rate;begin_ar=interest_receivable
        paid=0 if delay and r['year']==2028 else accrual+begin_ar
        interest_receivable=begin_ar+accrual-paid;balance-=principal
        rows.append(dict(year=r['year'],begin_onloan=begin,end_onloan=balance,principal_from_target=principal,
         parent_external_principal_repaid=principal,parent_finance_interest=accrual,
         parent_interest_income_accrual=accrual,target_interest_payment=paid,parent_interest_received=paid,
         begin_interest_receivable=begin_ar,end_interest_receivable=interest_receivable,
         target_interest_payable=interest_receivable,target_restricted_cash_for_due_interest=interest_receivable,
         parent_cash_drag=accrual-paid,parent_legal_profit_net=0,
         target_end_free_cash=r['end_cash'],target_end_total_cash=r['end_cash']+interest_receivable,
         group_external_debt_replaced=balance,group_intercompany_asset_liability_eliminated=balance,
         target_remaining_bank_debt=max(0,r['end_debt']-balance)))
        assert balance<=6+1e-8 and abs(principal-rows[-1]['parent_external_principal_repaid'])<1e-9
    return dict(initial=initial,rows=rows,rate=rate,delay=delay,
       boundary='Approval != drawing. Conditional issuance/rollover; after three-year authorisation future approvals not assumed factual. Pass through all financing costs at par, no tax arbitrage. Delayed interest held restricted by target, not distributed.')

PARENT=dict(cash=1.16232544068+1.75,retained=12.75005843361,reserve=2.51887375,capital=S,
 debt=.400234444+.94572297939+3.850732815+5.96143121398+7.74408818339,interest_free=2.60764)

def parent(name,cfo,ownprofit,receipts,declarations,invest,capacities,rate=.025,acquire=False,targetdiv=None,late=False,compensation=0,onlend=None):
    p=copy.deepcopy(PARENT);rows=[];new_ar=0;old_ar=.40336137865;desired=[.25,.49,.49,.5,.5,.5];targetdiv=targetdiv or [0]*5
    for i,year in enumerate(['2026H2',2027,2028,2029,2030,2031]):
        dt=.5 if i==0 else 1;start=copy.deepcopy(p)
        new_ar_begin=new_ar;old_ar_begin=old_ar
        new_ar+=declarations[i]-receipts[i]
        assert new_ar>=-1e-10
        loan=onlend['rows'][i-1] if onlend and i else None
        loan_drag=loan['parent_cash_drag'] if loan else 0
        oldreceipt=.40336137865 if i==(1 if late else 0) else 0
        old_ar-=oldreceipt
        oldpay=2.468496275 if i==0 else 0;extra=targetdiv[i-1] if i else 0
        compensation_cash=compensation*.75 if i==3 else 0 # 2029 receipt, 25% tax/settlement reserve; not parent distributable income
        acquisition=(4.95815175 if i==0 else 2.38725825*(1+.03) if i==1 else 0) if acquire else 0
        maintenance=.15*dt;base_interest=p['debt']*rate*dt
        before=p['cash']+cfo[i]+receipts[i]+extra+oldreceipt+compensation_cash-invest[i]-maintenance-acquisition-oldpay-base_interest-loan_drag
        request=desired[i]*S
        # New financing pays half-period interest; budget explicitly conditional on named parent's credit.
        draw=min(capacities[i],max(0,(.4+request-before)/(1-rate*dt*.5)))
        interest=base_interest+draw*rate*dt*.5
        profit=ownprofit[i]+declarations[i]+extra-interest
        signed,reserve,appropriation=legal(p['retained'],p['reserve'],S,profit)
        available=before+draw-draw*rate*dt*.5
        dividend=request if i==0 else min(request,max(0,signed),max(0,available-.4)) # approved 2026 interim cannot simply be cut
        cash=available-dividend;debt=p['debt']+draw
        paydown=min(debt,max(0,cash-.8));cash-=paydown;debt-=paydown
        p.update(cash=cash,debt=debt,retained=signed-dividend,reserve=reserve)
        assert abs(cash-(start['cash']+cfo[i]+receipts[i]+extra+oldreceipt+compensation_cash+draw-invest[i]-maintenance-acquisition-oldpay-interest-dividend-paydown-loan_drag))<1e-8
        assert dividend<=max(0,signed)+1e-8
        rows.append(dict(period=year,begin_cash=start['cash'],begin_debt=start['debt'],begin_retained=start['retained'],
         onlend_cash_drag=loan_drag,onlend_bridge=loan,new_dividend_receivable_begin=new_ar_begin,new_dividend_receivable_end=new_ar,old_dividend_receivable_begin=old_ar_begin,old_dividend_receivable_end=old_ar,compensation_cash=compensation_cash,cfo=cfo[i],new_receipts=receipts[i]+extra,target_receipts=extra,old_receivable_receipt=oldreceipt,
         own_profit_before_finance=ownprofit[i],declared_profit=declarations[i]+extra,legal_profit=profit,
         signed_legal_capacity=signed,reserve_added=appropriation,reserve=reserve,retained=p['retained'],
         investment=invest[i],maintenance=maintenance,acquisition_payment=acquisition,interest=interest,
         old_dividend_payment=oldpay,new_dividend=dividend,dps=dividend/S,requested_dps=desired[i],
         new_debt=draw,new_debt_capacity=capacities[i],hypothetical_maturity=5.2 if i==0 else 5,
         hypothetical_rollover=5.2 if i==0 else 5,debt_repayment=paydown,end_debt=debt,end_cash=cash,
         gross_external_debt_including_onlend=debt+(loan['end_onloan'] if loan else 0),onlend_receivable=loan['end_onloan'] if loan else 0,interest_free=2.60764,feasible=cash>=.4-1e-8,borrower='上市母公司'))
        if cash<.4-1e-8:break
    return dict(name=name,rows=rows,feasible=all(r['feasible'] for r in rows),terminal_equity=None,
      caveat='Calendar budgets not rolling five-year holder outputs; credit and rollover are assumptions, not commitments')

def renew(c,n,cap,k=.08):
    incoming=finite(c,n,k)/((1+k)**6)
    cost=sum(cap*w/(1+k)**t for t,w in [(2,.2),(3,.3),(4,.3),(5,.2)])
    return dict(cash=c,years=n,capex=cap,inflow_pv=incoming,capex_pv=cost,npv=incoming-cost,per_share=(incoming-cost)/S)

def main():
    assert abs(finite(100,2,.1)-(100/1.1+100/1.21))<1e-10
    assert finite(100,1.5,0)==150
    assert legal(-8,0,100,10)==(1.8,.2,.2)
    assert legal(5,50,100,10)==(15,50,0)
    assert legal(-8,0,100,5)==(-3,0,0)
    assert tax_calc(10,{2027:4},2027)==(1.5,4,{2027:0})
    assert tax_calc(-2,{2027:4},2027)==(0,0,{2027:4})
    assert tax_calc(10,{2026:4},2027)==(2.5,0,{2026:4})
    hb=onlend_bridge({'rows':[dict(year=2027,principal_repayment=5.903825/20,begin_debt=5.903825,end_debt=5.903825*19/20,end_cash=.05)]})
    assert hb['initial']['group_net_new_debt']==0
    assert abs(hb['rows'][0]['parent_finance_interest']-5.903825*.021)<1e-12 and abs(hb['rows'][0]['end_onloan']-5.903825*19/20)<1e-12
    targets={k:target(k,f,rate,credit) for k,f,rate,credit in [('conditional',[1]*20,.025,.5),('cyclical',[.85,.9,.95]+[1]*17,.03,.5),('structural',[.7]*20,.035,.3),('upside',[1.1]*20,.022,.5)]}
    noshield={k:target(k+'_no_tax_shield',f,rate,credit,False) for k,f,rate,credit in [('conditional',[1]*20,.025,.5),('cyclical',[.85,.9,.95]+[1]*17,.03,.5),('structural',[.7]*20,.035,.3),('upside',[1.1]*20,.022,.5)]}
    refinance=target('conditional_onlend_2.1pct',[1]*20,.021,.5,True)
    bridges={'synchronous':onlend_bridge(refinance),'interest_one_year_delayed':onlend_bridge(refinance,delay=True)}
    base=dict(cfo=[2.1,4.2,4.2,4.1,4,3.9],ownprofit=[1.55,3.1,3.1,3,2.9,2.8],receipts=[.2,.8,.8,.9,.9,1],declarations=[.2,.8,.8,.9,.9,1],invest=[3.2,2.5,2.2,1.2,.8,.5],capacities=[8,4,3,2,2,2])
    budgets={'no_acquisition':parent('不交割',**base)}
    limited=copy.deepcopy(base);limited['capacities']=[5,4,3,2,2,2]
    budgets['financing_failure']=parent('新增融资仅50亿元，失败即停',**limited,acquire=True)
    for k in targets:
        a=copy.deepcopy(base)
        if k=='cyclical':a.update(cfo=[1.8,3.6,3.8,4,4,3.9],ownprofit=[1.3,2.5,2.7,2.9,2.9,2.8],receipts=[.15,.6,.65,.8,.9,1],declarations=[.2,.7,.7,.8,.9,1],rate=.03,late=True)
        if k=='structural':a.update(cfo=[1.7,3.5,3.4,3.3,3.2,3.1],ownprofit=[1.2,2.4,2.3,2.2,2.1,2],receipts=[.1,.5,.5,.5,.5,.5],declarations=[.1,.5,.5,.5,.5,.5],invest=[3.5,2.75,2.42,1.32,.88,.55],capacities=[8,3,2,1,1,1],rate=.035)
        if k=='upside':a.update(cfo=[2.2,4.4,4.5,4.6,4.7,4.8],ownprofit=[1.65,3.2,3.3,3.4,3.5,3.6],receipts=[.3,.9,1,1.1,1.2,1.3],declarations=[.3,.9,1,1.1,1.2,1.3],rate=.022)
        actual=FINAL_2026_PROFIT+sum(r['profit'] for r in targets[k]['rows'][:2])
        compensation=min(7.34541,.592571-actual) if actual<.95*.592571 else 0
        targets[k]['compensation_diagnostic']=dict(profit_2026_28=actual,gross=compensation,net_receipt_2029=compensation*.75,caveat='Conditional audit-adjusted profit proxy, no target earnings uplift; 25% reserve not asserted tax law')
        budgets[k]=parent(k,**a,acquire=True,targetdiv=[r['dividend'] for r in targets[k]['rows'][:5]],compensation=compensation)
        if compensation:budgets[k+'_compensation_unreceived']=parent(k+'补偿未到账',**a,acquire=True,targetdiv=[r['dividend'] for r in targets[k]['rows'][:5]],compensation=0)
        ns=noshield[k];nactual=FINAL_2026_PROFIT+sum(r['profit'] for r in ns['rows'][:2]);ncomp=min(7.34541,.592571-nactual) if nactual<.95*.592571 else 0
        ns['compensation_diagnostic']=dict(profit_2026_28=nactual,gross=ncomp,net_receipt_2029=ncomp*.75)
        budgets[k+'_no_tax_shield']=parent(k+'_no_tax_shield',**a,acquire=True,targetdiv=[r['dividend'] for r in ns['rows'][:5]],compensation=ncomp)

    ra=FINAL_2026_PROFIT+sum(r['profit'] for r in refinance['rows'][:2]);rc=max(0,.592571-ra) if ra<.95*.592571 else 0
    refinance['compensation_diagnostic']=dict(profit_2026_28=ra,gross=rc,net_receipt_2029=rc*.75)
    for key,bridge in bridges.items():
        budgets['onlend_'+key]=parent('onlend_'+key,**base,acquire=True,targetdiv=[r['dividend'] for r in refinance['rows'][:5]],compensation=rc,onlend=bridge)
    lo=roads();hi=roads(.07);extension=roads(extra_years=10)
    return dict(schema='600377_Q3_fresh_recovery_v3',asof=str(ASOF),unit='CNY billion',shares=S,value_range=None,return_model=None,
      finite_low=lo,finite_high=hi,minus10pct=roads(revfactor=.9),free_extension10=extension,
      spurious_extension_value=extension['asset_pv']-lo['asset_pv'],renewal_grid=[renew(c,n,cap) for c in [2.4,3.2,4] for n in [10,15,20] for cap in [15,25,35]],
      old_appraisal=appraisal(),appraisal_rate_plus100bp=appraisal(.0803),targets=targets,target_no_tax_shield=noshield,target_onlend=refinance,onlend_bridges=bridges,parent_open=PARENT,parent=budgets,
      signed_commitment_capacity=-.67964151799+.592571,commitment_distributable=0,
      bank_principal=dict(book=8.439347224,tax_basis=4.62953082744,immediate=8.439347224-.25*3.80981639656,
        hold10_low=finite(.386,10,.08)+(.8*8.439347224-.25*(.8*8.439347224-4.62953082744))/1.08**10,
        hold10_high=finite(.44161741828,10,.07)+(8.439347224-.25*3.80981639656)/1.07**10,
        caveat='Group bank stake only, parent/minority split unresolved; alternative realisation not additive'),
      q3_facts=dict(revenue=15.39644036079,construction=6.091928,profit=3.85338673131,adjusted=3.80959611652,
        cfo=5.61460846266,capex=5.87097234972,cfo_less_capex=5.61460846266-5.87097234972,cash=.69590685590,
        book_common=44.22764206457,minority=14.15668664410,financial=4.11985229942,associates=14.47970489593,
        other_equity=13.07524373216,other_financial=1.50740265217,
        financing_components=[.91130092022,1.78226096663,2.33982122964,23.28260289154,9.24279916105,2.81418,.03001286604,.06615481308]),
      tests=dict(production_hand_cases=10,cash_conservation='passed'),
      unresolved=['旧权接续资本和收费期限','新路全生命周期交通与全部资本','法律实体融资与资本应付款归属','金融本金税后实现与少数归属','全公司2031后剩余普通股权益'])

def clean(x):
    if isinstance(x,float):return round(x,10)
    if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
    if isinstance(x,list):return [clean(v) for v in x]
    return x
if __name__=='__main__':print(json.dumps(clean(main()),ensure_ascii=False,sort_keys=True,indent=2))
