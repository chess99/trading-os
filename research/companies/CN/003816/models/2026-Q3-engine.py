#!/usr/bin/env python3
"""CN003816 2026Q3. stdlib-only, no network/files/input dependency.
All monetary inputs billions CNY; economic-share budgets != legal-entity statements.
Run python /path/2026-Q3.py > output.json. Forecast annual steps 2027..2106.
"""
import json, math, copy
SHARES=50.498824311
# Names, COD year, total project cost per unit bn (including IDC), real economic share,
# fraction of full construction cost remaining at cutoff; last 7 CODs are research budgets.
PROJECTS=[
 ('惠州1',2026,20.35962,.82,.01),('惠州2',2026,20.35962,.82,.02),
 ('苍南1',2026,21.1005,.46,.02),('苍南2',2027,21.1005,.46,.10),
 ('陆丰5',2027,20.376,1,.32),('陆丰6',2028,20.376,1,.48),
 ('陆丰1',2030,20.69223,1,.30),('陆丰2',2030,20.69223,1,.30),
 ('惠州3',2030,19.02892,1,.68),('惠州4',2031,19.02892,1,.74),
 ('宁德5',2029,19.15,.51,.50),('宁德6',2030,19.15,.51,.58),
 ('苍南3',2030,19.175,.51,.82),('苍南4',2033,19.175,.51,.90),
 ('招远1',2031,21.01624,1,.76),('招远2',2032,21.01624,1,.84),
 ('防城港5',2033,18.153,.61,.86),('防城港6',2034,18.153,.61,.90),
 ('台山3',2034,20,1,.95),('台山4',2035,20,1,.98),
 ('惠州5',2034,20,1,.98),('惠州6',2035,20,1,.99)]
BASE=dict(r=.08,tariff=.335,hours=7150,cash_cost=.14,tax=.25,
 mature_nopat=12.7,mature_da=8.0,mature_maintenance=4.0,
 debt=225.,construction_debt=70.,rate=.027,capex_factor=1.,delay=0,
 upstream=.75,receipt_delay=0,price_shift=0.,mature_multiplier=1.,
 parent_open_cash=3.678,sub_open_cash=7.0,receivable=3.295550588,
 parent_retained=30.609456005,parent_reserve=8.191772221,
 parent_capital=50.498824311,sub_retained_budget=30.,
 convertible=False,weak_years=0,weak_factor=1.,early_payout=.42,mature_plateau=10,mature_end=40,decomm_factor=1.,taishan_deficit=4.355)

def legal_step(retained,reserve,capital,profit,cash,requested):
    # Losses must be covered first; allocation only to net post-loss current profits.
    opening=retained
    retained+=profit
    eligible=max(0.,profit-max(0.,-opening))
    appropriation=min(max(0.,capital*.5-reserve),eligible*.10)
    reserve+=appropriation;retained-=appropriation
    paid=min(max(0.,requested),max(0.,retained),max(0.,cash))
    retained-=paid;cash-=paid
    return retained,reserve,cash,paid,appropriation

def cash_step(cash,operating,capex,interest,draw,principal,distribution):
    end=cash+operating-capex-interest+draw-principal-distribution
    assert abs(end-(cash+operating-capex-interest+draw-principal-distribution))<1e-8
    return end

def retirement_schedule(p,proj):
    obligations=[]
    # 4bn attributed mature liability PV is an estimate anchored to published group provision.
    for t in range(p['mature_plateau']+1,p['mature_end']+1):
        cost=4./(p['mature_end']-p['mature_plateau'])*1.055**t*p['decomm_factor']
        obligations.append(dict(name='mature-'+str(t),exit=t,cost=cost,start=1,half=False))
    for a in proj:
        end=a['cod']+60-2026;start=max(1,a['cod']-2026)
        cost=a['full']*.10*1.02**end*p['decomm_factor']
        obligations.append(dict(name=a['name'],exit=end,cost=cost,start=start,half=a['cod']>=2027))
    for a in obligations:
        weights=[(.5 if k==a['start'] and a['half'] else 1.) for k in range(a['start'],a['exit']+1)]
        a['annual']=a['cost']/sum(w*1.02**(a['exit']-k) for k,w in zip(range(a['start'],a['exit']+1),weights))
    return obligations

def simulate(p):
    p={**BASE,**p}; years=80
    face=4.8992182
    debt=p['debt']; parent_cash=p['parent_open_cash']; sub_cash=p['sub_open_cash']
    retained=p['parent_retained']; reserve=p['parent_reserve']; subret=p['sub_retained_budget']
    subreserve=0.; receivable=p['receivable']; shares=SHARES
    rows=[]; loans=[dict(balance=debt-face-25.,annual=(debt-face-25.)/30,start=1),dict(balance=face,annual=0.,start=1),dict(balance=25.,annual=25./30,start=1,owner='taishan')]
    # Opening cash excludes receivable; its eventual collection transfers existing subsidiary cash.
    proj=[]
    for name,cod,cost,own,remaining in PROJECTS:
        cod+=p['delay'] if cod>=2027 else 0
        full=cost*own*p['capex_factor']; rem=cost*own*remaining*p['capex_factor']
        # Outstanding contractual settlements for already operating units remain payable in year 1.
        start=max(2027,cod-5)
        span=max(1,cod-start+1)
        proj.append(dict(name=name,cod=cod,full=full,rem=rem,span=span,start=start,own=own))
    obligations=retirement_schedule(p,proj)
    decomm=0.; bridge=0.; total_ext_equity=0.
    ts_cash=.5;sub_cash-=ts_cash;ts_ret=-p['taishan_deficit']*.51;ts_res=0.
    mid_cash=0.;mid_res=0.
    for t in range(1,years+1):
        yr=2026+t; d0=debt; s0=sub_cash; pc0=parent_cash;ts0=ts_cash;mid0=mid_cash;fund0=decomm;opening_mid_res=mid_res
        ts_debt_open=sum(l['balance'] for l in loans if l.get('owner')=='taishan')
        # Mature fleet has no indefinite growth: orderly 2036-2066 runoff (no extension value).
        mature=1. if t<=p['mature_plateau'] else max(0.,(p['mature_end']-t)/(p['mature_end']-p['mature_plateau']))
        shock=p['weak_factor'] if t<=p['weak_years'] else 1.
        nopat=(p['mature_nopat']-.40)*mature*p['mature_multiplier']*shock
        finance_income=(.09 if t<=3 else 0.)+(.31 if t<=15 else 0.)
        finance_principal=(4.7 if t==3 else 0.)+(6.5 if t==15 else 0.)
        nopat+=finance_income
        # Pooled existing VAT-refund tail declines; new projects receive no modeled VAT windfall.
        nopat-=.60*min(1.,max(0.,(t-1)/8))*mature
        da=p['mature_da']*mature; maint=p['mature_maintenance']*mature
        capex=0.; added_nopat=0.; new_da=0.; capacity=0.; project_rows=[]
        for a in proj:
            spending=a['rem']/a['span'] if a['start']<=yr<=max(2027,a['cod']) else 0.
            capex+=spending
            age=yr-a['cod']; run=(.5 if age==0 else 1.) if 0<=age<60 else 0.
            if age<0: run=0.
            if t<=p['weak_years']:run*=shock
            gw=1.2*a['own']*run; capacity+=gw
            revenue=gw*p['hours']/1000*(p['tariff']+p['price_shift'])
            opex=gw*p['hours']/1000*p['cash_cost']
            dep=a['full']*.033*run if age<30 else a['full']*.012*run
            profit=(revenue-opex-dep)*(1-p['tax'])
            added_nopat+=profit;new_da+=dep
            maint+=a['full']*.012*run
            if t<=12:project_rows.append(dict(name=a['name'],capex=spending,nopat=profit,da=dep,owned_gw=gw))
        nopat+=added_nopat;da+=new_da
        ts_scale=mature*p['mature_multiplier']*shock
        # Profit budgets .4/.8/1.2bn at REFERENCE debt/interest; reconstruct NOPAT first.
        ts_nopat=(([.4,.8][t-1] if t<=2 else 1.2)*.51+25*.027*.75)*ts_scale
        # 1.11825bn normal TS NOPAT is already INSIDE mature 12.7bn, never added twice.
        nopat+=ts_nopat-(.612+25*.027*.75)*ts_scale
        # Cash decommission sinking-fund budget (not a second deduction of accounting provision).
        funding=sum(a['annual']*(.5 if t==a['start'] and a['half'] else 1.) for a in obligations if a['start']<=t<=a['exit'])
        retirement_payment=sum(a['cost'] for a in obligations if t==a['exit'])
        ts_retirement_deposit=sum(a['annual'] for a in obligations if a['name'].startswith('mature-') and t<=a['exit'])*1.785/17.1103056
        fund_income=decomm*.02
        decomm+=fund_income+funding-retirement_payment
        assert decomm>=-1e-6
        assert abs(decomm-(fund0+fund_income+funding-retirement_payment))<1e-6
        draw=.80*capex
        if draw>0:loans.append(dict(balance=draw,annual=draw/30,start=t+1))
        principal=0.;ts_principal=0.
        for l in loans:
            if t>=l['start']:
                v=min(l['balance'],l['annual']);l['balance']-=v;principal+=v
                if l.get('owner')=='taishan':ts_principal+=v
        # Construction interest already in full cost/capex: separate current expense from IDC.
        construction=p['construction_debt']*max(0.,1-t/10)
        interest=max(0.,d0-construction)*p['rate']
        bond_refinance=0.;bond_redemption=0.
        if t<=5:
            interest+=face*([.008,.012,.016,.020,.020][t-1]-p['rate'])
        if t==5 and not p['convertible']:
            # 106% including last 2% coupon: 4% premium is incremental to interest above.
            bond_refinance=face*1.04;bond_redemption=face*1.04
            loans[1]['balance']=0.
            loans.append(dict(balance=bond_refinance,annual=bond_refinance/20,start=6))
        debt=d0+draw-principal+(bond_refinance-face if bond_refinance else 0.)
        # Op cash calculated after tax; interest tax shield only at earning operating subsidiaries.
        parent_existing_interest=27.5*max(0.,1-(t-1)/30)*p['rate']
        # Existing parent financing, like the incremental bridge, has no presumed current tax shield.
        ts_interest_gross=ts_debt_open*p['rate']
        ts_interest_tax_shield=min(ts_interest_gross*p['tax'],max(0.,ts_nopat)/(1-p['tax'])*p['tax'])
        ts_interest=ts_interest_gross-ts_interest_tax_shield
        # No immediate shield on TS interest beyond its own positive operating tax base.
        ts_unavailable_shield=ts_interest-ts_interest_gross*(1-p['tax'])
        interest_after_tax=interest*(1-p['tax'])+min(interest,parent_existing_interest)*p['tax']+ts_unavailable_shield
        other_interest=interest_after_tax-ts_interest
        ts_profit=ts_nopat-ts_interest-ts_retirement_deposit
        net_profit=nopat-interest_after_tax-funding-(face*.04 if bond_refinance else 0.)
        operating=nopat+da-maint-funding+finance_principal
        # Group common-share cash net of project loans; parent equity injection is an internal transfer.
        injection=capex-draw
        ts_flow=ts_profit+(1.5-.51)*mature-ts_principal
        # Taishan attributable debt service is allocated within, not added to, group debt.
        ts_cash+=ts_flow
        ts_short=max(0.,-ts_cash)
        if ts_short:
            ts_cash+=ts_short;debt+=ts_short;loans.append(dict(balance=ts_short,annual=ts_short/15,start=t+1,owner='taishan'))
        other_operating=operating-(ts_nopat+(1.5-.51)*mature-ts_retirement_deposit)
        raw_sub=cash_step(sub_cash,other_operating,0,other_interest,0,principal-ts_principal,0)
        ts_ret,ts_res,ts_cash,ts_decl,ts_alloc=legal_step(ts_ret,ts_res,28.6*.51,ts_profit,ts_cash,max(0.,ts_profit)*p['upstream'])
        if t>=12:
            ts_ret,ts_res,ts_cash,ts_extra,_=legal_step(ts_ret,ts_res,28.6*.51,0.,ts_cash,max(0.,ts_cash-.2)/max(1,22-t))
            ts_decl+=ts_extra
        # 12.5/51 direct; 38.5/51 indirect. Intermediate cash takes one additional year.
        mid_receipt=mid_cash;mid_cash=0.
        via_mid=ts_decl*38.5/51
        mid_alloc=min(max(0.,.009-mid_res),ts_decl*28.5/51*.1)
        mid_res+=mid_alloc;mid_cash+=via_mid-mid_alloc
        # Capped intermediate reserve remains a cash asset, returned on capital exit.
        ts_receipt=ts_decl*12.5/51+mid_receipt
        ts_capital_return=0.;ts_exit_call=0.;ts_exit_repayment=0.;ts_midreserve_return=0.
        if t==p['mature_end']:
            # Exit capital pays ALL Taishan residual obligations first. Parent bears any deficit.
            ts_exit_repayment=sum(l['balance'] for l in loans if l.get('owner')=='taishan')
            ts_exit_call=max(0.,ts_exit_repayment-ts_cash)
            ts_cash+=ts_exit_call-ts_exit_repayment
            parent_cash-=ts_exit_call
            debt-=ts_exit_repayment;principal+=ts_exit_repayment;ts_principal+=ts_exit_repayment
            for l in loans:
                if l.get('owner')=='taishan':l['balance']=0.
            ts_midreserve_return=mid_res
            ts_capital_return=ts_cash+mid_res
            ts_receipt+=ts_capital_return;ts_cash=0.;mid_res=0.
        # Existing receivable collection only uses cash; never credited to current profit.
        old_receipt=min(receivable,max(0.,raw_sub-2.0)) if t>p['receipt_delay'] else 0.
        receivable-=old_receipt;raw_sub-=old_receipt
        declaration=max(0.,net_profit-ts_profit)*p['upstream']
        # Consolidated common-share distributable buffer is a research budget, not a legal statement.
        subret,subreserve,sub_cash,declared,sub_alloc=legal_step(subret,subreserve,70.,net_profit-ts_profit,raw_sub,declaration)
        receipt=declared if t>p['receipt_delay'] else 0.
        if not receipt:receivable+=declared;sub_cash+=declared
        # Cash retained in intermediate/operating companies released over 10 years after building phase,
        # subject to available legal profit budget. This is not a year-5 mark-to-par release.
        extra=0.
        if t>=12:
            request=max(0.,sub_cash-2.)/max(1,22-t)
            subret,subreserve,sub_cash,extra,extra_alloc=legal_step(subret,subreserve,70.,0.,sub_cash,request)
        receipt+=extra
        receipt+=ts_receipt
        # If cash shortage: operating company shortfall loan, included in all common-share debt.
        short=max(0.,2.-sub_cash) if mature+capacity>0 else max(0.,-sub_cash)
        if short:
            sub_cash+=short;debt+=short;loans.append(dict(balance=short,annual=short/15,start=t+1))
        holding_cost=.55 if mature+capacity>0 else 0.
        bridge_interest=bridge*p['rate'] # only incremental parent bridge; not in original debt.
        parent_profit=declared+extra+ts_receipt-ts_capital_return-ts_exit_call-holding_cost-bridge_interest
        parent_cash+=receipt+old_receipt-injection-holding_cost-bridge_interest
        # Shareholder payout request follows earnings, limited by legal profit and cash.
        target=max(0.,net_profit-holding_cost-bridge_interest)*(p['early_payout'] if t<=10 else .70)
        if t>12:target+=max(0.,parent_cash-2.)/max(1,22-t)
        # No borrowing to maintain arbitrary dividends; bridge funds committed equity capex only.
        deficit=max(0.,-parent_cash)
        if deficit:bridge+=deficit;parent_cash+=deficit
        bridge_repay=min(bridge,max(0.,parent_cash-2.))
        bridge-=bridge_repay;parent_cash-=bridge_repay
        retained,reserve,parent_cash,paid,alloc=legal_step(retained,reserve,p['parent_capital'],parent_profit,parent_cash,min(target,max(0.,parent_cash-1.)))
        # Retirement liquidation of residual cash and legally returnable capital; no asset resale premium.
        liquidation=0.
        if t==years:
            # All plant lives ended by 2095. Decommission funds consumed, not paid to shareholders.
            assert mature+capacity==0.
            assert debt+bridge<1e-7,(debt,bridge)
            assert abs(decomm)<1e-5
            liquidation=parent_cash+sub_cash+ts_cash+mid_cash+mid_res
            paid+=liquidation;parent_cash=0.;sub_cash=0.;ts_cash=0.;mid_cash=0.;mid_res=0.
        if p['convertible'] and t==5:
            # Alternative full conversion at adjusted price; no conversion assumed in core.
            conversion_price=max(.1,3.58-sum(x['dps'] for x in rows))
            face=4.8992182;shares+=face/conversion_price
            # Conversion reduces initial-loan principal, avoiding debt AND dilution counted together.
            loans[1]['balance']=0.;debt-=face
        assert parent_cash>=-1e-7 and sub_cash>=-1e-7 and ts_cash>=-1e-7
        assert abs(debt-sum(l['balance'] for l in loans))<1e-6
        # All cash movements are reconciled including declared-but-unreceived internal transfers.
        total_expected=s0+pc0+ts0+mid0+opening_mid_res+operating-interest_after_tax-principal-injection-holding_cost-bridge_interest+short+ts_short+deficit-bridge_repay-paid
        assert abs(sub_cash+parent_cash+ts_cash+mid_cash+mid_res-total_expected)<1e-6,(yr,total_expected,sub_cash+parent_cash+ts_cash+mid_cash+mid_res)
        assert abs(sub_cash+parent_cash+ts_cash+mid_cash+mid_res+decomm-(total_expected+fund0+funding+fund_income-retirement_payment))<1e-6
        ts_operating_cash=ts_nopat+(1.5-.51)*mature-ts_retirement_deposit-ts_interest
        assert abs(ts_cash-(ts0+ts_operating_cash-ts_principal+ts_short-ts_decl+ts_exit_call-ts_capital_return+ts_midreserve_return))<1e-6
        assert abs(interest_after_tax-ts_interest-other_interest)<1e-8
        if t>=p['mature_end']:assert sum(l['balance'] for l in loans if l.get('owner')=='taishan')<1e-7
        rows.append(dict(year=yr,nopat=nopat,profit=net_profit,da=da,maintenance=maint,
            capex=capex,equity_injection=injection,project_draw=draw,principal=principal,
            interest=interest_after_tax,bond_refinance=bond_refinance,bond_redemption=bond_redemption,financial_principal_received=finance_principal,debt=debt,parent_bridge=bridge,shortfall_draw=short,
            sub_cash=sub_cash,declared=declared,receipt=receipt,old_receipt=old_receipt,
            receivable=receivable,parent_profit=parent_profit,parent_cash=parent_cash,
            parent_retained=retained,parent_reserve=reserve,sub_retained_budget=subret,
            payout=paid,dps=paid/shares,shares=shares,
            decommission_opening=fund0,decommission_funding=funding,decommission_fund=decomm,decommission_payment=retirement_payment,decommission_income=fund_income,taishan_nopat=ts_nopat,taishan_debt_opening=ts_debt_open,taishan_debt_closing=sum(l['balance'] for l in loans if l.get('owner')=='taishan'),taishan_principal=ts_principal,taishan_interest_gross=ts_interest_gross,taishan_interest_tax_shield=ts_interest_tax_shield,taishan_interest_after_tax=ts_interest,other_interest_after_tax=other_interest,other_operating_cash=other_operating,taishan_operating_cash=ts_nopat+(1.5-.51)*mature-ts_retirement_deposit-ts_interest,taishan_exit_call=ts_exit_call,taishan_exit_debt_repayment=ts_exit_repayment,taishan_retirement_deposit=ts_retirement_deposit,taishan_capital_return=ts_capital_return,taishan_shortfall_draw=ts_short,taishan_profit=ts_profit,taishan_cash=ts_cash,taishan_retained=ts_ret,taishan_declared=ts_decl,intermediate_cash=mid_cash,intermediate_reserve=mid_res,projects=project_rows))
    pv=sum(x['dps']/(1+p['r'])**(i+1) for i,x in enumerate(rows))
    tv5=sum(x['dps']/(1+p['r'])**(i-4) for i,x in enumerate(rows) if i>=5)
    return dict(value=pv,terminal_year5=tv5,terminal_share=tv5/(1+p['r'])**5/pv,
                dps=[x['dps'] for x in rows[:5]],rows=rows,parameters=p,retirement_obligations=obligations)

def independent_unit_check(p):
    # Alternative economic normalization; identical ordinary-holder funding/payment bridge.
    stations=[(2.052,.75),(1.980,1),(2.172,.9388),(6.516,.6172),(3.5,.51),
              (4.548,.366),(4.356,.3376),(6.714,.3888)]
    gw=sum(cap*own for cap,own in stations) # excludes ALL 2026 new units
    da=gw*.46;maintenance=gw*.29
    nopat=(gw*7.0*(.342-.145)-da)*.75+.40
    q={**p,'mature_nopat':nopat,'mature_da':da,'mature_maintenance':maintenance,
       'hours':7000,'tariff':.342,'cash_cost':.145}
    z=simulate(q)
    return dict(normal_owned_gw=gw,normal_earnings=nopat,mature_nopat=nopat,
                mature_da=da,mature_maintenance=maintenance,value=z['value'],
                dps=z['dps'],terminal_year5=z['terminal_year5'],full_holder_model=z,
                note='独立机组产能及成本正常化，通过完全相同普通持有人现金、法律储备预算、负债和退役桥；非控制者资产出售价值。')

def tests():
    # Production legal function: losses recovered before allocating statutory reserve.
    r,s,c,d,a=legal_step(-4.,0.,20.,-2.,10.,5.);assert (r,s,c,d,a)==(-6.,0.,10.,0.,0.)
    r,s,c,d,a=legal_step(r,s,20.,10.,c,10.);assert all(abs(x-y)<1e-10 for x,y in zip((r,s,c,d,a),(0.,.4,6.4,3.6,.4)))
    # Production legal function: reserve cap precisely binds, no perpetual 10% deduction.
    r,s,c,d,a=legal_step(0.,9.8,20.,5.,8.,9.);assert abs(a-.2)<1e-10 and abs(d-4.8)<1e-10
    assert cash_step(2.,8.,10.,1.,5.,2.,1.)==1.
    assert legal_step(-4.,0.,28.6,.4,10.,1.)[3]==0.
    assert legal_step(30.,0.,70.,100.,100.,75.)[3]==75.
    return ['loss_then_profit: -4-2+10 => 0.4 reserve,3.6 payment',
            'reserve_cap:9.8->10.0;5 profit->4.8 payment','cash/debt:2+8-10-1+5-2-1=1']

def main():
    checks=tests()
    variants={'base':{},'core_low':dict(r=.085,tariff=.330,mature_nopat=12.4),
              'core_high':dict(r=.075,tariff=.340,mature_nopat=13.0),
              'cyclical':dict(delay=1,weak_years=2,weak_factor=.90,receipt_delay=1),
              'structural':dict(tariff=.300,mature_multiplier=.82,rate=.035,capex_factor=1.15,early_payout=.30),
              'optimistic':dict(tariff=.345,hours=7400,capex_factor=.95),
              'tariff_minus_001':dict(tariff=.325),
              'upstream_delay_2y':dict(receipt_delay=2),
              'upstream_60pct':dict(upstream=.60),
              'debt_plus_20':dict(debt=245.),
              'debt_minus_20':dict(debt=205.),
              'maintenance_plus_1':dict(mature_maintenance=5.),
              'shorter_mature_life':dict(mature_plateau=6,mature_end=32),
              'parent_open_cash_minus_2':dict(parent_open_cash=1.678),
              'remaining_cost_plus20pct':dict(capex_factor=1.2),
              'no_open_sub_retained':dict(sub_retained_budget=0.),
              'decommission_cost_150pct':dict(decomm_factor=1.5),'decommission_cost_200pct':dict(decomm_factor=2.),'taishan_deficit_1':dict(taishan_deficit=1.),'taishan_deficit_6':dict(taishan_deficit=6.),'feasibility_net_hours':dict(hours=6449.1),'convertible_full':dict(convertible=True)}
    results={k:simulate(v) for k,v in variants.items()}
    out=dict(schema_version=1,company='CN:003816',unit='CNY billion, shares billion',
        cutoff='2026-10-28T11:00:00+00:00',hand_checks=checks,
        assumptions_not_facts=['经济归属债务225（含建设70）及可用现金10.678为预算；并非逐主体债务事实',
        '项目权益和预算来源H1；剩余支付比例及未公布COD的七台投产年为预测',
        '法定子公司汇总储备30只是资金桥预算；不代表子公司可自由合并抵销'],
        results=results,independent_unit_method={k:independent_unit_check({**BASE,**variants[k]}) for k in ['core_low','base','core_high']})
    print(json.dumps(out,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False))
if __name__=='__main__':main()
