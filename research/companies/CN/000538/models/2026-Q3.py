#!/usr/bin/env python3
"""Self-contained production model; CNY bn, annual anniversaries after cutoff.
No files or inputs read. Legal balances are disclosed/budget as documented in report.
No market prices. All cases use same ordinary shares, cash/debt and timing.
"""
import json, math
SHARES=1.784262603
CUTOFF='2026-10-29T11:13:00+00:00'
NAMES=('P','H','R','D','O')
COMMON0=40.26965006088
MINORITY0=.05548673386
LIQUID0=7.06762709152+5.51925892909
NONCORE0=.28548012754+.071745+.50053279018
ASSOC0=13.81476199125-.50053279018
RESTRICTED0=7.62908754676-7.06762709152
BANK0=.1322
LEASE0=.05009695922+.15520310425+.0021+.12894015094-BANK0
EMPLOYEE0=.52308490010
OWN={'P':1.,'H':1.,'R':1.,'D':1.,'O':1.}
INITIAL={
 'cash':[10.,.3,.3,1.9,LIQUID0-12.5],
 're':[1.45,0.,0.,0.,-.24447494195], # O is economic repair budget, not statutory retained earnings
 'reserve':[2.52929761808,0.,0.,0.,0.],
 'capital':[1.784262603,.0845,.0164,1.,0.],
 'loan_receivable_face':[0.,.8,2.,4.21326076649,0.],
 'loan_allowance':[0.,.8/7.01326076649*.14597466954,2./7.01326076649*.14597466954,4.21326076649/7.01326076649*.14597466954,0.],
 'parent_payable':[0.,4.,3.,4.,0.],
 'parent_investment_allowance':[0.,0.,0.,0.,.24447494195],
 'parent_investment_cost':[0.,.16829766103,.13089451814,.76553364730,1.53846962445]
}
CASES={
 'base':dict(k=.09,dg=.035,hg=.025,dm=.30,hm=.35,distm=.035,assocroe=.07),
 'core_low':dict(k=.095,dg=.03,hg=.015,dm=.295,hm=.345,distm=.034,assocroe=.065),
 'core_high':dict(k=.085,dg=.04,hg=.03,dm=.305,hm=.355,distm=.036,assocroe=.075),
 'cycle':dict(k=.09,dg=.035,hg=.025,dm=.30,hm=.35,distm=.035,assocroe=.07,cycle=True),
 'structural':dict(k=.10,dg=-.01,hg=-.02,dm=.22,hm=.25,distm=.025,assocroe=.05,structural=True),
 'upside':dict(k=.085,dg=.05,hg=.045,dm=.32,hm=.37,distm=.037,assocroe=.08),
 'cash_delay':dict(k=.09,dg=.035,hg=.025,dm=.30,hm=.35,distm=.035,assocroe=.07,cash_delay=True),
 'working_capital_heavy':dict(k=.09,dg=.035,hg=.025,dm=.30,hm=.35,distm=.035,assocroe=.07,working_capital_heavy=True),
 'tax_fade_diagnostic':dict(k=.09,dg=.035,hg=.025,dm=.30,hm=.35,distm=.035,assocroe=.07,tax_fade=True),
 'tax_expiry':dict(k=.09,dg=.035,hg=.025,dm=.30,hm=.35,distm=.035,assocroe=.07,tax_expiry=True),
 'other_deficit':dict(k=.09,dg=.035,hg=.025,dm=.30,hm=.35,distm=.035,assocroe=.07,other_deficit=True),
 'parent_bridge_low':dict(k=.09,dg=.035,hg=.025,dm=.30,hm=.35,distm=.035,assocroe=.07,parent_bridge_low=True),
 'cash_failure':dict(k=.09,dg=.035,hg=.025,dm=.30,hm=.35,distm=.035,assocroe=.07,cash_failure=True),
 'holder_low':dict(k=.095,dg=.03,hg=.015,dm=.295,hm=.345,distm=.034,assocroe=.065,firstfive_base=True),
 'holder_high':dict(k=.085,dg=.04,hg=.03,dm=.305,hm=.355,distm=.036,assocroe=.075,firstfive_base=True),
 'margin_minus_2pp':dict(k=.09,dg=.035,hg=.025,dm=.28,hm=.33,distm=.035,assocroe=.07),
}
def distribute(re, reserve, capital, profit, cash, floor, desired):
    # Current loss first offsets retained earnings; only profit exceeding opening deficit is reservable.
    deficit=max(-re,0.)
    appropriation=min(max(capital*.5-reserve,0.), max(profit-deficit,0.)*.1)
    available=re+profit-appropriation
    payment=max(0.,min(desired,available,cash-floor))
    return available-payment,reserve+appropriation,payment,appropriation

def run(cfg,method='A',years=600):
    parameters=cfg.copy(); k=cfg['k']
    cash=dict(zip(NAMES,INITIAL['cash'])); re=dict(zip(NAMES,INITIAL['re'])); reserve=dict(zip(NAMES,INITIAL['reserve'])); cap=dict(zip(NAMES,INITIAL['capital']))
    loan=dict(zip(NAMES,INITIAL['loan_receivable_face'])); allowance=dict(zip(NAMES,INITIAL['loan_allowance'])); payable=dict(zip(NAMES,INITIAL['parent_payable'])); invcost=dict(zip(NAMES,INITIAL['parent_investment_cost']))
    other_re=-.32 if cfg.get('other_deficit') else -.02; hk_re=-.22447494195 # capital-repair budget, NOT legal retained earnings
    re['O']=other_re+hk_re; reserve['O']=0.; cap['O']=0.
    hk_nci=-.03327008812; rest_nci=MINORITY0-hk_nci # Q3 allocation budget anchored to H1, not Q3 reported split
    if cfg.get('parent_bridge_low'):cash['P']-=.622;cash['D']+=.622;re['P']=.84657
    revenue=[8.8,7.,1.5,26.]; prev_revenue=revenue[:]
    ratio=[.08,.08,.40,.23] if method=='A' else [.10,.10,.40,.25]
    nwc=[a*b for a,b in zip(revenue,ratio)]
    fixed=[1.6,1.2,.7,1.8,.15]
    assoc=ASSOC0; noncore=NONCORE0; restricted=RESTRICTED0; emp=EMPLOYEE0; bank=BANK0; lease=LEASE0; rou=.21556719552
    eq=COMMON0; nci=MINORITY0; other_operating_net_assets=eq+nci-(sum(cash.values())+sum(nwc)+sum(fixed)+assoc+noncore+restricted+rou-bank-lease-emp); rows=[]; pv=0.; ri=COMMON0; bridge_discount=1. # Unreported interim operating flows not fabricated
    for t in range(1,years+1):
        cfg={**parameters,**CASES['base']} if parameters.get('firstfive_base') and t<=5 else parameters
        oldcash=cash.copy(); oldeq=eq; oldnci=nci; oldassoc=assoc; oldnoncore=noncore; oldrestricted=restricted; oldemp=emp; oldbank=bank; oldlease=lease; oldrou=rou
        structural=cfg.get('structural',False)
        terminal_g=.005 if structural else .02
        growth=[cfg['dg'],cfg['hg'],.02,.03]
        if t>5:growth=[g+(terminal_g-g)*min((t-5)/10,1) for g in growth]
        if structural:growth[2:]=[.005,.01] if t<=5 else [terminal_g,terminal_g]
        revenue=[r*(1+g) for r,g in zip(prev_revenue,growth)] if t>1 else prev_revenue[:]
        if cfg.get('cycle'):
            # Observable temporary channel reduction: sales level relative to undisturbed trend .94/.97/1.00.
            previous=.94 if t==2 else .97 if t==3 else 1.
            current=.94 if t==1 else .97 if t==2 else 1.
            revenue=[r*current/previous for r in revenue]
        scale=sum(revenue)/43.3
        tf=.85 # core conditional renewal, eligible western industrial mix retained
        if cfg.get('tax_fade'):tf=1-(.15+.10*min(max(t-4,0)/6,1))
        if cfg.get('tax_expiry'):tf=.85 if t<=4 else 1-(.15*64/365+.25*301/365) if t==5 else .75
        if method=='A':
            drug=revenue[0]*cfg['dm']; health=revenue[1]*cfg['hm']; resource=revenue[2]*.08; dist=revenue[3]*cfg['distm']; central=.85*scale
            if cfg.get('cycle') and t<=2:central+=.15*scale
            brand=1.2*revenue[1]/7.
            rprofit=.5*revenue[2]/1.5
            # Internal resource transfer margin is deducted from P; internal brand fee shifts H->P.
            pprofit=(drug+brand-central)*tf-(rprofit-resource*tf)
            operating={'P':pprofit,'H':(health-brand)*tf,'R':rprofit,'D':dist*.75,'O':.015*scale}
            op_detail=dict(drug_ebit=drug,health_ebit_before_brand=health,resource_external_ebit=resource,distribution_ebit=dist,central_expense=central,brand_fee=brand,resource_internal_profit=rprofit-resource*tf)
        else:
            industrial=revenue[0]+revenue[1]+1.*revenue[2]/1.5
            commercial=sum(revenue)-industrial
            gross=industrial*.65+commercial*.064
            sell=industrial*.315+commercial*.017
            admin=industrial*.048+commercial*.0065
            research=industrial*.028
            credit=industrial*.008+commercial*.003
            indprofit=(industrial*(.65-.315-.048-.028-.008))*tf
            dprofit=commercial*(.064-.017-.0065-.003)*.75
            hp=revenue[1]*.16;rp=.5*revenue[2]/1.5;op=.015*scale
            operating={'P':indprofit-hp-rp-op,'H':hp,'R':rp,'D':dprofit,'O':op}
            op_detail=dict(industrial_sales=industrial,commercial_sales=commercial,gross_profit=gross,selling=sell,admin=admin,research=research,credit_cost=credit,industrial_aftertax=indprofit,distribution_aftertax=dprofit)
        # Full lease accounting: depreciation and interest in income, principal paid, new ROU noncash.
        lease_dep=.08*scale;lease_int=oldlease*.04
        lease_principal=min(oldlease,.08*scale)
        lease_new=max(0.,oldlease*(1+(growth[0] if t>1 else 0))-oldlease+lease_principal)
        lease=oldlease+lease_new-lease_principal;rou=oldrou+lease_new-lease_dep
        operating['P']-=lease_int*tf
        bank_int=oldbank*.035;bank_repay=oldbank if t==1 else 0.;bank-=bank_repay
        operating['D']-=bank_int*.75
        # Trading+cash return taxed separately, not duplicated in operating earnings.
        fin={n:oldcash[n]*.018*(.75 if n=='D' else (.6*.75+.4*.835) if n=='O' else tf) for n in NAMES}
        aro=cfg['assocroe'];ap=oldassoc*aro
        apayout=.35 if t<=5 else .35+(max(0.,1-terminal_g/aro)-.35)*min((t-5)/10,1)
        ad=ap*apayout;assoc=oldassoc+ap-ad
        # Other investments: explicit yield, cost, disposal expenses and gain tax. No capital repayment as profit.
        ni=oldnoncore*.025;disposal=0.;disposal_pnl=0.;disposal_tax=0.;disposal_fee=0.
        if t==10 and oldnoncore:
            grosssale=oldnoncore*.95;disposal_fee=grosssale*.01;disposal_tax=max(grosssale-disposal_fee-.65,0.)*.25
            disposal=grosssale-disposal_fee-disposal_tax;disposal_pnl=disposal-oldnoncore;noncore=0.
        # Paired employee account earns return and pays the matching pre-existing obligation.
        rinterest=oldrestricted*.018*tf;restricted=oldrestricted+rinterest
        employee_pay=min(oldemp,.04);emp-=employee_pay;restricted-=employee_pay
        release=max(0.,restricted-.035) if emp<=1e-12 else 0.;restricted-=release
        # Restricted .035 guarantee/maintenance base remains an asset earning returns; no forced loss.
        np={n:operating[n]+fin[n] for n in NAMES}
        np['P']+=ap+ni+disposal_pnl+rinterest
        change_nwc=[];capex={};dep={};fcf={}
        for i,n in enumerate(NAMES):
            if n=='O':delta=0.
            else:
                j={'P':0,'H':1,'R':2,'D':3}[n]
                rat=ratio[j]+(.07 if (structural or cfg.get('working_capital_heavy')) and j==3 else 0.)
                target=revenue[j]*rat
                delta=target-nwc[j];nwc[j]=target
            change_nwc.append(delta)
            dep[n]=fixed[i]*.08
            growth_cap=max(revenue[min(i,3)]-prev_revenue[min(i,3)],0.)*([.18,.16,.30,.07,0.][i]) if n!='O' else 0.
            finish=.04 if t<=3 and n in ('P','R') else 0.
            capex[n]=dep[n]+growth_cap+finish
            fixed[i]+=capex[n]-dep[n]
            fcf[n]=operating[n]+fin[n]+dep[n]-capex[n]-delta
            if n=='P':fcf[n]+=ad+ni+disposal+release+lease_dep-lease_principal
            if n=='D':fcf[n]-=bank_repay
            cash[n]+=fcf[n]
        # Contractual claims persist as face and allowance. Gross cash settlements; no legal set-off presumed.
        settlements={};allowance_release=0.;injections={};upstream={};subreserve={};minoritydiv=0.
        if cfg.get('cash_failure') and t==1:cash['P']-=20. # hypothetical new cash commitment, not extinguishment of an old claim
        for n in NAMES[1:]:
            pay=payable[n]*(.20 if cfg.get('cash_delay') and t<=3 else .05)
            collect=0. if cfg.get('cash_delay') and t<=3 else loan[n]*.05
            pay=min(pay,payable[n])
            al=allowance[n]*(collect/loan[n]) if loan[n] else 0.
            loan[n]-=collect;allowance[n]-=al;payable[n]-=pay
            allowance_release+=al;cash[n]+=pay-collect;cash['P']+=collect-pay
            settlements[n]=dict(parent_payment=pay,parent_collection=collect,face_end=loan[n],allowance_end=allowance[n],parent_payable_end=payable[n])
        floors={'P':2.*scale,'H':.2*scale,'R':.3*scale,'D':1.5*scale,'O':.05*scale}
        other_details={}
        for n in NAMES[1:]:
            injection=max(0.,floors[n]-cash[n]);injections[n]=injection
            if injection:
                cash[n]+=injection;cash['P']-=injection;invcost[n]+=injection
            desired=max(0.,np[n]*.85)+max(0.,cash[n]-floors[n])* .08
            if cfg.get('cash_delay') and t<=3:desired=0.
            if n=='O':
                # Two economic subledgers, not a fictitious legal company. HK earnings net of local taxes.
                hk_profit=.004572833*scale+oldcash[n]*.4*.018*.835
                other_profit=np[n]-hk_profit
                hk_open=hk_re;other_open=other_re
                hk_re+=hk_profit;other_re+=other_profit
                available_cash=max(0.,cash[n]-floors[n])
                other_div=max(0.,min(other_re,available_cash,other_profit*.85+available_cash*.048))
                hk_div=max(0.,min(hk_re,available_cash-other_div,hk_profit*.85))
                if cfg.get('cash_delay') and t<=3:other_div=0.;hk_div=0.
                hk_re-=hk_div;other_re-=other_div
                div=other_div+hk_div;appropr=0.;re[n]=hk_re+other_re;reserve[n]=0.
                minority_cash=hk_div*.2694;minority_income=hk_profit*.2694
                hk_nci+=minority_income-minority_cash
                other_details=dict(hk_profit=hk_profit,other_profit=other_profit,hk_recovery_begin=hk_open,hk_recovery_end=hk_re,other_budget_begin=other_open,other_budget_end=other_re,hk_distribution=hk_div,other_distribution=other_div,hk_minority_equity=hk_nci,other_minority_equity=rest_nci,hk_minority_profit=minority_income,hk_minority_dividend=minority_cash)
            else:
                re[n],reserve[n],div,appropr=distribute(re[n],reserve[n],cap[n],np[n],cash[n],floors[n],desired)
                minority_cash=0.
            cash[n]-=div;cash['P']+=div-minority_cash
            minoritydiv+=minority_cash;upstream[n]=div-minority_cash;subreserve[n]=appropr
        group_profit=sum(np.values());minority_profit=minority_income;common_profit=group_profit-minority_profit
        plegal=np['P']+sum(upstream.values())+allowance_release # associate equity profit legally recognized, cash separately ad
        desired_common=max(0.,common_profit*.90)+max(0.,cash['P']-floors['P']-2*scale)*.05
        re['P'],reserve['P'],div,pappropr=distribute(re['P'],reserve['P'],cap['P'],plegal,cash['P'],floors['P'],desired_common)
        cash['P']-=div
        if min(cash.values()) < -1e-9:
            return dict(feasible=False,failure_year=t,reason='No authorized financing; parent cannot meet gross cash obligations',cash=cash,rows=rows)
        nci+=minority_profit-minoritydiv;eq+=common_profit-div
        discount=(1+k)**t
        d_pv=div/discount;ri_pv=(common_profit-k*oldeq)/discount
        pv+=d_pv;ri+=ri_pv
        # Consolidated conservation: internal principal/upstream/injections eliminated.
        balance_common=sum(cash.values())+sum(nwc)+sum(fixed)+assoc+noncore+restricted+rou-bank-lease-emp+other_operating_net_assets-nci
        assert abs(balance_common-eq)<1e-7*max(1,abs(eq)),(t,balance_common,eq)
        expected=sum(oldcash.values())+sum(fcf.values())-minoritydiv-div
        cash_error=sum(cash.values())-expected
        assert abs(cash_error)<1e-7*max(1,abs(expected)),(t,cash_error)
        assert all(v>=-1e-8 for v in [restricted,emp,bank,lease]+list(loan.values())+list(allowance.values())+list(payable.values())) or cfg.get('cash_failure')
        row=dict(other_economic_subledgers=other_details,industrial_tax_factor=tf,year=t,revenue=revenue[:],operating_detail=op_detail,operating_profit=operating,financial_income=fin,entity_profit=np,common_profit=common_profit,minority_profit=minority_profit,
          nwc=nwc[:],delta_nwc=change_nwc,fixed_assets=fixed[:],capex=capex,depreciation=dep,entity_fcf_before_internal=fcf,cash_begin=oldcash,cash_end=cash.copy(),cash_conservation_error=cash_error,
          internal_settlements=settlements,parent_sub_investment_cost=invcost.copy(),parent_sub_investment_allowance=dict(zip(NAMES,INITIAL['parent_investment_allowance'])),parent_sub_investment_net={n:invcost[n]-INITIAL['parent_investment_allowance'][i] for i,n in enumerate(NAMES)},capital_injections=injections,sub_upstream_cash=upstream,minority_dividend=minoritydiv,
          parent_legal_profit=plegal,retained_earnings=re.copy(),statutory_reserve=reserve.copy(),reserve_addition=dict(subreserve,P=pappropr),
          associate_begin=oldassoc,associate_profit=ap,associate_cash_dividend=ad,associate_end=assoc,associate_payout=apayout,
          noncore_begin=oldnoncore,noncore_income=ni,noncore_sale=disposal,noncore_disposal_profit=disposal_pnl,noncore_sale_tax=disposal_tax,noncore_sale_fee=disposal_fee,noncore_end=noncore,
          restricted_begin=oldrestricted,restricted_interest=rinterest,employee_liability_begin=oldemp,employee_payment=employee_pay,employee_liability_end=emp,restricted_release=release,restricted_end=restricted,
          bank_begin=oldbank,bank_interest=bank_int,bank_principal=bank_repay,bank_end=bank,lease_begin=oldlease,lease_addition=lease_new,lease_depreciation=lease_dep,lease_principal=lease_principal,lease_interest=lease_int,lease_end=lease,rou_end=rou,
          other_operating_net_assets=other_operating_net_assets,balance_sheet_common_equity=balance_common,common_equity_begin=oldeq,common_equity_end=eq,minority_equity_begin=oldnci,minority_equity_end=nci,common_dividend=div,dividend_per_share=div/SHARES,pv_dividend=d_pv,pv_residual_income=ri_pv)
        rows.append(row);prev_revenue=revenue[:]
    # Every value is a full continuation of the same state path; no horizon cash sweep or multiplier.
    y5=sum(r['common_dividend']/(1+k)**(r['year']-5) for r in rows[5:])/SHARES
    tail={str(h):dict(dividend_pv=sum(r['pv_dividend'] for r in rows[:h])/SHARES,book_pv=rows[h-1]['common_equity_end']/(1+k)**h/SHARES,nominal_cash=sum(rows[h-1]['cash_end'].values()),nominal_associate=rows[h-1]['associate_end'],nominal_internal_face=sum(x['face_end'] for x in rows[h-1]['internal_settlements'].values())) for h in (60,120,300,600) if h<=years}
    return dict(feasible=True,method=method,assumptions=parameters,shares=SHARES,unit='CNY billion',rows=rows,value_at_balance_date=pv/SHARES,value_per_share=pv/SHARES*bridge_discount,
       residual_income_value_per_share=ri/SHARES*bridge_discount,year5_terminal_per_share=y5,year5_terminal_pv_share=y5*SHARES/(1+k)**5/pv,tail=tail,
       residual_identity_error=ri-pv-eq/(1+k)**years)

def main():
    result={'as_of':CUTOFF,'shares':SHARES,'opening_common_equity':COMMON0,'initial':INITIAL,'other_opening_economic_budgets':{'hk_repair':-.22447494195,'other_repair':-.02,'hk_nci_budget':-.03327008812,'other_nci_budget':.08875682198,'hk_cash_allocation':.4,'other_cash_allocation':.6,'note':'O has no statutory capital/reserve; allocations are economic budgets not legal capacity certificates'},'timing':'Annual anniversaries from 2026-10-29; Latest observed Q3 balances start anniversary forecast at cutoff; unreported October flows held at zero, sensitivity in source notes','cases':{}}
    for name,cfg in CASES.items(): result['cases'][name]=run(cfg)
    result['crosscheck']=run(CASES['base'],'B')
    print(json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False))
if __name__=='__main__':main()
