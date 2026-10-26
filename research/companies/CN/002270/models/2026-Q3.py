#!/usr/bin/env python3
"""CN:002270; CNY billion except per share. Deterministic legal/cash annual model.
Run from any cwd; writes next to this file. No external input/dependencies.
"""
import json, math, pathlib, copy, gzip, base64, hashlib, argparse
SHARES=.896225431
# Legal-subject budgets: actual ownership/capital, estimated standalone allocation.
LEGACY_SPECS=[('Guizhou',.20,.060,1.,'Shanghai'),('Zunyi',.06,.050,1.,'Shanghai'),('Russia',.02,.00113862286,.65,'Shanghai'),('Turkey',.02,.017401925,.9832,'Shanghai'),('CNC',0.,.092,1.,'Parent'),('SolarLeaf',0.,.133,1.,'SolarHolding'),('SolarHolding',0.,.387,1.,'Parent'),('ShanghaiHV',.15,.050,1.,'Shanghai'),('Shanghai',.55,.100,1.,'Parent')]

def legacy_legal_step(ur,reserve,capital,profit,rate=.1,cap_fraction=.5):
    recovery=min(max(-ur,0.),max(profit,0.))
    addition=min(max(capital*cap_fraction-reserve,0.),max(profit-recovery,0.)*rate)
    return ur+profit-addition,reserve+addition,addition

def legacy_payout(legal,cash,floor,target):
    return min(max(legal,0.),max(cash-floor,0.),max(target,0.))

def legacy_run(mode='base',discount=.10,years=600,margin_shift=0.,roic=.25,lag=.0,legal_zero=False,extra_payment=0.,issue=0.,debt_limit=.95,shanghai_weight=.55,parent_cash=.06,old_ar_delay=0):
    specs=[(n,(shanghai_weight if n=='Shanghai' else .15+.55-shanghai_weight if n=='ShanghaiHV' else w),cap,own,par) for n,w,cap,own,par in LEGACY_SPECS]
    cash0=.99942404399-.23301861206-.024998103-.00927546078
    nodes={}
    for name,w,cap,own,par in specs:
        nodes[name]=dict(cash=(cash0-parent_cash)*({'Shanghai':.78,'ShanghaiHV':.02,'CNC':.02,'SolarLeaf':.04,'SolarHolding':.02,'Guizhou':.04,'Zunyi':.02,'Russia':.04,'Turkey':.02}[name]),ur=0. if legal_zero else (.30 if name=='Shanghai' else .03),reserve=0.,capital=cap,debt=.23858193369 if name=='Shanghai' else (.55 if name=='SolarLeaf' else 0.),payable=.39698138794 if name=='Shanghai' else 0.,owner=own,parent=par,operating_capital=2.3*w if w else (.7*.45 if name=='CNC' else .7*.55 if name=='SolarLeaf' else 0.))
    nodes['Parent']=dict(cash=parent_cash,ur=.44478031239-.23301861206,reserve=.36530171861,capital=SHARES,debt=0.,payable=0.,owner=1.,parent=None)
    ar={n:0. for n in nodes};ar['Parent']=.39698138794
    rev=2.36;other=.34; shares=SHARES; rows=[]; feasible=True; fail=None; debt_cap=debt_limit; sponsor_used=0.; maturity={n:{} for n in nodes}
    for t in range(1,years+1):
        growth=[.09,.09,.08,.07,.06,.05,.04,.03,.025,.02][min(t-1,9)]
        if mode=='cyclical' and t<=3:growth=[-.15,.0,.18][t-1]
        if mode=='structural':growth=[-.22,-.08,0.,0.,.01][min(t-1,4)]
        if mode=='upside':growth=[.13,.12,.10,.09,.07,.06,.05,.04,.03,.02][min(t-1,9)]
        oldrev=rev; rev*=1+growth; oldother=other;other*=1+(.03 if t<6 else .02)
        margin=.34-.02*min(t,10)/10+margin_shift
        if mode=='cyclical' and t<=3:margin-=[.05,.03,.01][t-1]
        if mode=='structural':margin=.23+margin_shift
        if mode=='upside':margin+=.012
        ep=rev*margin; op=other*.055; hq=.02*((1.01 if mode=='structural' else 1.02)**(t-1))
        inc=max(rev-oldrev,0)*margin/(roic if t<=5 else min(roic,.18))
        if mode=='structural':inc+=rev*.015 # stranded capital, no immediate liquidation credit
        oinc=max(other-oldother,0)*.055/.12
        beginning={n:copy.deepcopy(s) for n,s in nodes.items()}; start_ar=ar.copy(); receipts={n:0. for n in nodes}; declarations={n:0. for n in nodes}; netprofit={n:0. for n in nodes}; detail={}; minor=0.; ext=0.; equity=0.
        if t==1 and issue:
            nodes['Parent']['cash']+=issue;nodes['Parent']['capital']+=issue/10; shares+=issue/10;equity=issue
        for name,w,cap,own,par in specs:
            s=nodes[name]; old=beginning[name]
            oper=ep*w if w else (op*.45 if name=='CNC' else op*.55 if name=='SolarLeaf' else 0.)
            investment=inc*w if w else (oinc*.45 if name=='CNC' else oinc*.55 if name=='SolarLeaf' else 0.)
            interest=s['cash']*.015-s['debt']*.045
            profit=oper+interest+declarations[name]
            # Subsidiary declaration income is not consolidated new earnings.
            s['cash']+=oper+interest-investment+receipts[name]
            s['operating_capital']+=investment
            s['ur'],s['reserve'],reserve_add=legacy_legal_step(s['ur'],s['reserve'],s['capital'],profit, .05 if name=='Turkey' else .1, .2 if name=='Turkey' else .5)
            principal=min(s['debt'],((.23858193369 if name=='Shanghai' else .55 if name=='SolarLeaf' else 0.)/8 if t<=8 else 0.)+maturity[name].pop(t,0.))
            s['cash']-=principal;s['debt']-=principal
            floor=rev*.085*w if w else other*.085*({'CNC':.45,'SolarLeaf':.55,'SolarHolding':0.}[name])
            old_paid=min(s['payable'], max(s['cash']-floor,0.)) if not (name=='Shanghai' and t<=old_ar_delay) else 0.
            s['payable']-=old_paid;s['cash']-=old_paid
            old_tax=old_paid*own*(.10 if name in ['Russia','Turkey'] else 0.)
            receipts[par]+=old_paid*own-old_tax;ar[par]-=old_paid*own-old_tax;minor+=old_paid*(1-own)
            if name=='CNC':
                receipts['Parent']-=old_paid*.1304;receipts['Shanghai']+=old_paid*.1304
                ar['Parent']+=old_paid*.1304;ar['Shanghai']-=old_paid*.1304
            # Ordinary and release dividends share ONE legal and cash cap.
            desired=max(oper*.78,0.)+max(s['cash']-floor-oper*.78,0.)*.20
            legal=max(s['ur'],0.)
            if name=='Turkey':legal=min(legal,(legal+.005*s['capital'])/1.1)
            declared=legacy_payout(legal,s['cash'],floor,desired)
            second=max(declared-.05*s['capital'],0.)*.1 if name=='Turkey' else 0.
            s['ur']-=second;s['second_reserve']=s.get('second_reserve',0.)+second
            paid=declared*(1-lag);s['ur']-=declared;s['cash']-=paid;s['payable']+=declared-paid
            tax=.10 if name in ['Russia','Turkey'] else 0.
            declarations[par]+=declared*own*(1-tax);receipts[par]+=paid*own*(1-tax);ar[par]+=(declared-paid)*own*(1-tax);minor+=paid*(1-own)
            foreign_tax=paid*own*tax+old_tax
            # CNC indirect 13.04% is routed through Shanghai, still 100% group-owned.
            if name=='CNC':
                for ledger,amount in [(declarations,declared),(receipts,paid)]:
                    ledger['Parent']-=amount*.1304;ledger['Shanghai']+=amount*.1304
                ar['Parent']-=(declared-paid)*.1304;ar['Shanghai']+=(declared-paid)*.1304
            detail_floor=floor
            netprofit[name]=oper+interest-foreign_tax
            detail[name]=dict(floor=floor,begin=old,operating_profit=oper,financial_income_net=interest,declared_income=declarations[name],profit=profit,reinvestment=investment,maintenance=rev*.04*w if w else other*.04*({'CNC':.45,'SolarLeaf':.55,'SolarHolding':0.}[name]),dep=rev*.04*w if w else other*.04*({'CNC':.45,'SolarLeaf':.55,'SolarHolding':0.}[name]),reserve_add=reserve_add,second_reserve_add=second,withholding_paid=foreign_tax,old_dividend_paid=old_paid,declared=declared,paid=paid,received=receipts[name],debt_repaid=principal,end=copy.deepcopy(s))
        p=nodes['Parent'];profit=declarations['Parent']-hq+p['cash']*.015-p['debt']*.045
        netprofit['Parent']=-hq+p['cash']*.015-p['debt']*.045
        parent_principal=min(p['debt'],maturity['Parent'].pop(t,0.))
        p['debt']-=parent_principal
        p['cash']+=receipts['Parent']+netprofit['Parent']-parent_principal
        # Sponsor solar debt amortization through the actual holding chain before dividends.
        need=max(detail['SolarLeaf']['floor']-nodes['SolarLeaf']['cash'],0.)
        injection=min(need,max(p['cash']-.03,0.),max(.70-sponsor_used,0.))
        p['cash']-=injection;nodes['SolarLeaf']['cash']+=injection
        nodes['SolarLeaf']['capital']+=injection;nodes['SolarHolding']['capital']+=injection
        sponsor_used+=injection
        detail['SolarLeaf']['capital_cash_in']=injection;detail['SolarHolding']['parent_equity_in_and_project_equity_out']=injection
        for name,w,cap,own,par in specs:
            ss=nodes[name]; floor=detail[name]['floor']
            borrowing=min(max(floor-ss['cash'],0.),max(debt_cap-sum(z['debt'] for z in nodes.values()),0.))
            if borrowing<1e-12*max(1.,floor):borrowing=0.
            ss['cash']+=borrowing;ss['debt']+=borrowing;ext+=borrowing
            if borrowing:
                for due in [t+1,t+2]:maturity[name][due]=maturity[name].get(due,0.)+borrowing/2
            detail[name]['borrowed']=borrowing;detail[name]['end']=copy.deepcopy(ss)
            if ss['cash']<floor-1e-10*max(1.,floor):feasible=False;fail={'year':t,'entity':name,'cash':ss['cash'],'required_cash':floor,'zero_D_failed':True}

        recovery=.07 if t==2 else (.04 if t==3 else 0.)
        p['cash']+=recovery
        buyback=.125001897 if t==1 else 0.
        payment=extra_payment if t==1 else (-extra_payment if t==3 else 0.)
        p['cash']-=buyback+payment
        p['ur'],p['reserve'],ra=legacy_legal_step(p['ur'],p['reserve'],p['capital'],profit)
        group_profit=sum(netprofit.values()); parent_floor=.03*(1.01 if mode=='structural' else 1.02)**(t-1)
        # No issue proceeds are automatically dividend profit.
        target=max(group_profit,0.)*.70 if t<=5 else max(p['cash']-parent_floor,0.)
        D=legacy_payout(p['ur'],p['cash'],parent_floor,target)
        p['ur']-=D;p['cash']-=D
        borrow=min(max(parent_floor-p['cash'],0.),max(debt_cap-sum(s['debt'] for s in nodes.values()),0.))
        if borrow<1e-12*max(1.,parent_floor):borrow=0.
        p['cash']+=borrow;p['debt']+=borrow;ext+=borrow
        if borrow:
            for due in [t+1,t+2]:maturity['Parent'][due]=maturity['Parent'].get(due,0.)+borrow/2
        if p['cash']<parent_floor-1e-10*max(1.,parent_floor):feasible=False;fail={'year':t,'entity':'Parent','cash':p['cash'],'required_cash':parent_floor,'zero_D_failed':True}
        detail['Parent']=dict(floor=parent_floor,debt_repaid=parent_principal,begin=beginning['Parent'],profit=profit,operating_profit=-hq,declared_income=declarations['Parent'],received=receipts['Parent'],reserve_add=ra,dividend=D,nonoperating_asset_recovery=recovery,solar_equity_out=injection,sponsor_used=sponsor_used,buyback=buyback,extra_settlement=payment,borrowed=borrow,equity_raised=equity,end=copy.deepcopy(p))
        b=sum(v['cash'] for v in beginning.values());e=sum(v['cash'] for v in nodes.values());rep=sum(d.get('debt_repaid',0) for d in detail.values())
        residual=e-(b+group_profit-inc-oinc-rep+ext+equity+recovery-D-minor-buyback-payment)
        assert abs(residual)<1e-6*max(1,e), (t,residual)
        assert all(s['reserve']<=s['capital']*.5+1e-9 and s['reserve']>=0 for s in nodes.values())
        assert all(s['cash']>=-1e-8 for s in nodes.values()) or not feasible
        for n,s in nodes.items():
            if n!='Parent': assert s['ur']>=-1e-9 or detail[n]['declared']==0
        rows.append(dict(year=t,electric_revenue=rev,other_revenue=other,margin=margin,group_profit=group_profit,reinvestment=inc+oinc,dividend=D,dps=D/shares,shares=shares,minority_paid=minor,financing=ext,equity=equity,ar_end=ar.copy(),new_debt_maturities=copy.deepcopy(maturity),cash_residual=residual,subjects=detail))
        if not feasible:break
    pv=sum(x['dps']/(1+discount)**x['year'] for x in rows) if feasible else None
    tv=sum(x['dps']/(1+discount)**(x['year']-5) for x in rows if x['year']>5) if feasible else None
    return dict(mode=mode,discount=discount,years=years,feasible=feasible,failure=fail,pv=pv,tv5=tv,first5=[x['dps'] for x in rows[:5]],tail_share=(sum(x['dps']/(1+discount)**x['year'] for x in rows if x['year']>10)/pv if feasible else None),rows=rows)


# Corrected model: only Parent is a statutory ledger. Budget is NOT a legal entity.
def reserve_step(retained,statutory,registered,profit,paid_in=None):
    recovered=min(max(-retained,0),max(profit,0))
    addition=min(max(registered*.5-statutory,0),max(profit-recovered,0)*.1)
    return retained+profit-addition,statutory+addition,addition

def capital_return(cash,registered,shares,requested,fee_rate=.02,ownership=1.,basis=None,creditor_hold=0.):
    """Conditional pro-rata cancellation at par; not dividend profit. No operating liquidation."""
    gross=min(max(cash-creditor_hold,0)/(1+fee_rate),registered*.49,max(requested,0))
    fee=gross*fee_rate
    cancelled=shares*gross/registered if registered else 0
    # Ordinary domestic holder tax basis is not forecast; company-level no income on own reduction.
    return dict(cash=cash-gross-fee,registered=registered-gross,shares=shares-cancelled,
                paid=gross*ownership,minority=gross*(1-ownership),fees=fee,profit=0.,cancelled=cancelled)

def asset_exit(proceeds,basis,fee,tax,ownership):
    taxable=max(proceeds-fee-basis,0)
    return dict(cash=(proceeds-fee-taxable*tax)*ownership,profit=(proceeds-fee-basis-taxable*tax)*ownership,
                tax=taxable*tax,minority=(proceeds-fee-taxable*tax)*(1-ownership))

def run(mode='base',discount=.0975,years=600,margin_shift=0.,roic=.25,upstream_scale=1.,lag=0.,reserve_credit=0.,extra_payment=0.,debt_limit=.95,parent_cash=.06,old_ar_delay=0,issue=0.,redemption_year=12,redemption=.40,tax_fail=False,small_minor=.0025,finite_solar=True,economic_revision=True,release_rate=.20,release_start=6,annual_sweep=True,sweep_start=13,capital_fee=.02,creditor_hold=0.,principal_recovery_year=0,principal_recovery_amount=0.,capital_shock_year=0,capital_shock_amount=0.,capitalisation_budget=1.,principal_recovery_schedule=()):
    # cash and receivable locations are conditional budgets anchored in H1, not Q3 legal facts.
    cash0=.73213186815; pc=parent_cash; bc=cash0-pc; ur=.21176170033; reserve=reserve_credit
    reg=.896225431; shares=.896225431; original_shares=shares; holder_fraction=1.
    old_ar=.39698138794; new_ar=0.; debt=.78858193369; pdebt=0.; maturities={}; pmaturities={}
    rev=2.36;other=.34; cnc=.34*.45;solar=.34*.55; capital=3.;solar_basis=.385
    rows=[];feasible=True;failure=None; issue_premium=0.; probe_basis=principal_recovery_amount+sum(a for _,a in principal_recovery_schedule); probe_capital=0.; opening_surplus=2.89118017991; conversion_budget=min(max(capitalisation_budget,0),opening_surplus)
    for t in range(1,years+1):
        start=dict(parent_cash=pc,budget_cash=bc,retained=ur,statutory=reserve,registered=reg,shares=shares,old_ar=old_ar,new_ar=new_ar,debt=debt,parent_debt=pdebt,operating_capital=capital,solar_basis=solar_basis,issue_premium=issue_premium,probe_basis=probe_basis,probe_capital=probe_capital,opening_capital_surplus=opening_surplus,conversion_budget=conversion_budget)
        growth=[.09,.09,.08,.07,.06,.05,.04,.03,.025,.02][min(t-1,9)]
        if mode=='cyclical' and t<=3:growth=[-.15,0.,.18][t-1]
        if mode=='structural':growth=[-.22,-.08,0.,0.,.01][min(t-1,4)]
        if mode=='upside':growth=[.13,.12,.10,.09,.07,.06,.05,.04,.03,.02][min(t-1,9)]
        oldrev=rev;rev*=1+growth;oldother=other;other*=1+(.03 if t<6 else .02)
        oldcnc=cnc;cnc*=1+(.03 if t<6 else .02)
        margin=.34-.02*min(t,10)/10+margin_shift
        if mode=='cyclical' and t<=3:margin-=[.05,.03,.01][t-1]
        if mode=='structural':margin=.23+margin_shift
        if mode=='upside':margin+=.012
        ep=rev*margin
        # Existing 15% tax is embedded in normalized post-tax margin. Explicit renewal loss.
        tax_drag=ep/.85*.10*((.70 if t>=2 else .15)+(.20 if t>=5 else 0)) if tax_fail else 0.
        ep-=tax_drag
        inc=max(rev-oldrev,0)*max(margin,0)/(roic if t<=5 else min(roic,.18))
        stranded=rev*.015 if mode=='structural' else 0.;inc+=stranded
        if finite_solar and economic_revision:
            solar_rev=solar if t<=20 else 0.;sp=solar_rev*.055
            depreciation=.385/20 if t<=20 else 0.;maintenance=solar_rev*.025
            solar_basis=max(0,solar_basis-depreciation)
            op=cnc*.055+sp;oinc=max(cnc-oldcnc,0)*.055/.12
            solar_cash_adjust=depreciation-maintenance
            other_sales=cnc+solar_rev
        else:
            op=other*.055;oinc=max(other-oldother,0)*.055/.12;solar_cash_adjust=0.;other_sales=other;depreciation=maintenance=0.
        minority_electric=ep*(.02*.35+.02*.0168+(small_minor if economic_revision else 0))
        minority_cnc=cnc*.055*.10*.30 if economic_revision else 0.
        minority=max(minority_electric+minority_cnc,0.) # cash budget; no assumed change of equity percentages
        crossborder=max(ep,0.)*.04*.10 # conditional aggregate remittance friction, not treaty assertion
        fin=bc*.015-debt*.045;hq=.02*((1.01 if mode=='structural' else 1.02)**(t-1))
        pfin=pc*.015-pdebt*.045
        probe_profit=probe_capital*.18
        probe_investment=capital_shock_amount if t==capital_shock_year else 0.
        probe_capital+=probe_investment;inc+=probe_investment
        common_profit=ep+op+fin-minority-crossborder+probe_profit
        bc+=common_profit+solar_cash_adjust-inc-oinc
        capital+=inc+oinc-stranded-(depreciation-maintenance)
        rep=min(debt,(.78858193369/8 if t<=8 else 0)+maturities.pop(t,0));debt-=rep;bc-=rep
        prep=min(pdebt,pmaturities.pop(t,0));pdebt-=prep;pc-=prep
        floor=.085*(rev+other_sales);pfloor=.03*((1.01 if mode=='structural' else 1.02)**(t-1))
        equity=issue if t==1 else 0.
        if equity:
            pc+=equity;reg+=equity/10;shares+=equity/10;holder_fraction*=start['shares']/shares;issue_premium+=equity*.9
        # Old declared Shanghai dividend: only cash/receivable, never new statutory earnings.
        old_paid=min(old_ar,max(bc-floor,0.)) if t>old_ar_delay else 0.;old_ar-=old_paid;bc-=old_paid;pc+=old_paid
        arrears_paid=min(new_ar,max(bc-floor,0.));new_ar-=arrears_paid;bc-=arrears_paid;pc+=arrears_paid
        # Aggregate achievable NEW declaration budget, no pooled losses/fictional legal reserves.
        # Historical 2025 declaration/equipment-group profit ~59%; H1 ~79%.
        capacity_ratio=(.65 if t<=5 else min(.95,.65+.06*(t-5)))*upstream_scale
        capacity=max(common_profit,0.)*capacity_ratio
        financial_release_budget=max(bc-floor-capacity-new_ar-old_ar,0)*release_rate*upstream_scale if t>=release_start else 0.
        declaration=min(capacity+financial_release_budget,max(bc-floor,0.))
        paid=declaration*(1-lag);new_ar+=declaration-paid;bc-=paid;pc+=paid
        # Explicit limited realization of identified parent assets; basis cannot be dividend profit.
        recovery=.07 if t==2 else 0.;disposal_profit=0.;exit_tax=0.
        if t==3:
            ex=asset_exit(.022,.02695481108,.002,.25,1.) if economic_revision else asset_exit(.045,.08107,.005,.25,1.);recovery+=ex['cash'];disposal_profit+=ex['profit'];exit_tax+=ex['tax']
        solar_exit=0.
        if t==20 and finite_solar and economic_revision:
            ex=asset_exit(.03,solar_basis,.005,.25,1.);solar_exit=ex['cash'];bc+=solar_exit;exit_tax+=ex['tax']
            # subsidiary disposal gain raises future economic budget only via this year's new declaration
            extra_decl=min(max(ex['profit'],0.)*upstream_scale,max(bc-floor,0.))
            declaration+=extra_decl;paid+=extra_decl*(1-lag);new_ar+=extra_decl*lag;bc-=extra_decl*(1-lag);pc+=extra_decl*(1-lag)
        probe_recovery=(principal_recovery_amount if t==principal_recovery_year else 0.)+sum(a for y,a in principal_recovery_schedule if y==t)
        probe_basis-=probe_recovery;recovery+=probe_recovery
        pc+=recovery+pfin-hq
        profit=declaration+pfin-hq+disposal_profit
        ur,reserve,ra=reserve_step(ur,reserve,reg,profit)
        buyback=.125001897 if t==1 else 0.;payment=extra_payment if t==1 else (-extra_payment if t==3 else 0.)
        pc-=buyback+payment
        # Bounded group support is actual transfer, not legal capital change or fresh group income.
        support=min(max(floor-bc,0.),max(pc-pfloor,0.));bc+=support;pc-=support
        finance=min(max(floor-bc,0.),max(debt_limit-debt-pdebt,0.));bc+=finance;debt+=finance
        if finance>1e-12:
            for due in [t+1,t+2]:maturities[due]=maturities.get(due,0)+finance/2
        target=max(common_profit+pfin-hq,0)*.70 if t<=5 else max(pc-pfloor,0)
        D=min(max(ur,0),max(pc-pfloor,0),target);pc-=D;ur-=D
        refund=fees=cancelled=capitalised=bonus_shares=converted_opening=0.
        sweep_eligible=annual_sweep and t>=max(sweep_start,redemption_year+1) and redemption>0
        # Conditional issuer approvals: capitalise ONLY the identified premium from modeled new issue.
        # No initial unidentified reserve is reclassified; conversion creates no cash or profit.
        if sweep_eligible and issue_premium>0:
            capitalised=issue_premium;bonus_shares=shares*capitalised/reg
            shares+=bonus_shares;reg+=capitalised;issue_premium=0.
        # Further registered headroom can come only from explicit, bounded opening surplus conversion.
        # 1bn eligibility is a conditional governance budget within disclosed 2.89118bn account,
        # not evidence that every component of that accounting reserve is legally convertible.
        if sweep_eligible:
            required=max(max(pc-pfloor-creditor_hold,0)/(1+capital_fee)+.1-reg,0)
            converted_opening=min(required,conversion_budget,opening_surplus)
            if converted_opening<1e-10:converted_opening=0.
            if converted_opening:
                bonus=shares*converted_opening/reg;shares+=bonus;bonus_shares+=bonus
                reg+=converted_opening;opening_surplus-=converted_opening;conversion_budget-=converted_opening
        if (t==redemption_year or sweep_eligible) and redemption:
            request=redemption if t==redemption_year else max(pc-pfloor,0)/(1+capital_fee)
            cr=capital_return(max(pc-pfloor,0),reg,shares,request,fee_rate=capital_fee,creditor_hold=creditor_hold)
            refund=cr['paid'];fees=cr['fees'];cancelled=cr['cancelled'];pc-=refund+fees
            reg=cr['registered'];shares=cr['shares'];ur-=fees
        pborrow=min(max(pfloor-pc,0.),max(debt_limit-debt-pdebt,0.));pc+=pborrow;pdebt+=pborrow
        if pborrow>1e-12:
            for due in [t+1,t+2]:pmaturities[due]=pmaturities.get(due,0)+pborrow/2
        if min(bc-floor,pc-pfloor)<-1e-9*max(1,rev):
            feasible=False;failure=dict(year=t,budget_cash=bc,parent_cash=pc,budget_floor=floor,parent_floor=pfloor,dividend=D)
        # For pro-rata cancellation ongoing original holder owns constant fraction of remaining issuer.
        # For issue, original holders diluted; issue price only cash input, no current market quote.
        dps=(D+refund)/original_shares*holder_fraction
        group_profit=common_profit+pfin-hq
        residual=pc+bc-(start['parent_cash']+start['budget_cash']+group_profit+solar_cash_adjust-inc-oinc-rep-prep+finance+pborrow+equity+recovery+solar_exit-D-refund-fees-buyback-payment)
        assert abs(residual)<1e-7*max(1,abs(pc)+abs(bc)),(t,residual)
        rows.append(dict(year=t,electric_revenue=rev,other_revenue=other_sales,margin=margin,probe_recovery=probe_recovery,probe_profit=probe_profit,probe_investment=probe_investment,capitalised_issue_premium=capitalised,capitalised_opening_surplus=converted_opening,bonus_shares=bonus_shares,tax_drag=tax_drag,group_common_profit=group_profit,minority_paid=minority,withholding_friction=crossborder,financing=finance+pborrow,debt_repaid=rep+prep,reinvestment=inc+oinc,maintenance_electric_cnc=.04*(rev+cnc),depreciation_electric_cnc=.04*(rev+cnc),solar_depreciation=depreciation,solar_maintenance=maintenance,solar_exit=solar_exit,solar_cash_adjust=solar_cash_adjust,exit_tax=exit_tax,upstream_capacity=capacity,financial_release_budget=financial_release_budget,upstream_declared=declaration,upstream_paid=paid,old_receivable_cash=old_paid,new_receivable_cash=arrears_paid,support=support,parent_profit=profit,parent_statutory_add=ra,dividend=D,capital_return=refund,cancellation=cancelled,fees=fees,dps=dps,buyback=buyback,extra_settlement=payment,asset_recovery=recovery,asset_disposal_profit=disposal_profit,equity=equity,cash_residual=residual,budget_floor=floor,parent_floor=pfloor,begin=start,end=dict(parent_cash=pc,budget_cash=bc,retained=ur,statutory=reserve,registered=reg,shares=shares,old_ar=old_ar,new_ar=new_ar,debt=debt,parent_debt=pdebt,operating_capital=capital,solar_basis=solar_basis,issue_premium=issue_premium,probe_basis=probe_basis,probe_capital=probe_capital,opening_capital_surplus=opening_surplus,conversion_budget=conversion_budget)))
        if not feasible:break
    pv=sum(x['dps']/(1+discount)**x['year'] for x in rows) if feasible else None
    tv=sum(x['dps']/(1+discount)**(x['year']-5) for x in rows if x['year']>5) if feasible else None
    return dict(mode=mode,discount=discount,feasible=feasible,failure=failure,pv=pv,tv5=tv,first5=[x['dps'] for x in rows[:5]],tail_share=sum(x['dps']/(1+discount)**x['year'] for x in rows if x['year']>10)/pv if feasible else None,rows=rows)

def tests():
    assert reserve_step(0,5,20,10,paid_in=10)==(9,6,1)
    assert reserve_step(-3,0,20,2)==(-1,0,0)
    assert reserve_step(-3,0,20,5)==(1.8,.2,.2)
    assert reserve_step(0,10,20,10)==(10,10,0)
    assert reserve_step(0,10,22,10)==(9,11,1)
    cr=capital_return(10,20,20,4,.05,.65)
    assert cr['profit']==0 and cr['registered']==16 and cr['shares']==16 and cr['cash']==5.8 and cr['paid']==2.6
    ex=asset_exit(10,10,1,.25,.65);assert ex['cash']==5.8500000000000005 and ex['profit']==-.65
    r=run(years=3);assert r['rows'][0]['old_receivable_cash']>0
    assert abs(r['rows'][0]['parent_profit']-(r['rows'][0]['upstream_declared']+.06*.015-.02))<1e-12
    z=run(years=1,extra_payment=10,debt_limit=0);assert not z['feasible'] and z['rows'][0]['dividend']==0
    crpath=run(years=20);z=crpath['rows'][11];assert z['capital_return']>0 and z['end']['shares']<z['begin']['shares']
    assert abs(z['dps']-(z['dividend']+z['capital_return'])/.896225431)<1e-12
    return dict(registered_not_paid_in='pass',loss_first='pass',full_reserve='pass',conversion_registered='pass',old_receivable_not_profit='pass',no_unlimited_finance='pass',capital_return_not_profit='pass',minority_fees_and_cancellation='pass',real_production_redemption=z['capital_return'])

def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def expand_output(packed):
    x=copy.deepcopy(packed);blob=x.pop('annual_data');rows=json.loads(gzip.decompress(base64.b64decode(blob['payload_base64'])))
    for k,v in rows.items():x['paths'][k]['rows']=v
    assert hashlib.sha256(canonical(x)).hexdigest()==blob['expanded_sha256']
    return x

def main():
    paths={}
    cfg=[('base_low',dict(discount=.105)),('base_high',dict(discount=.09)),('base',{}),('bridge_reserve0',dict(economic_revision=False,finite_solar=False,small_minor=0,redemption=0)),('bridge_minor_asset',dict(finite_solar=False,redemption=0)),('bridge_finite_solar',dict(redemption=0)),('cyclical',dict(mode='cyclical')),('structural',dict(mode='structural')),('upside',dict(mode='upside')),('margin_minus3',dict(margin_shift=-.03)),('roic15',dict(roic=.15)),('upstream_80pct',dict(upstream_scale=.8)),('upstream80_release_slow',dict(upstream_scale=.8,release_rate=.10,release_start=10)),('release_slow',dict(release_rate=.10,release_start=10)),('receipt_half',dict(lag=.5)),('reserve_upper',dict(reserve_credit=.36530171861)),('no_reduction',dict(redemption=0)),('reduction_year20',dict(redemption_year=20,sweep_start=21)),('residual_sweep_year20',dict(sweep_start=20)),('capital_fee_5pct',dict(capital_fee=.05)),('capital_fee_10pct',dict(capital_fee=.10)),('single_reduction_oldpolicy',dict(annual_sweep=False)),('productive_capital_probe',dict(capital_shock_year=20,capital_shock_amount=.05)),('par_only_diagnostic',dict(capitalisation_budget=0)),('principal_1bn_probe',dict(principal_recovery_year=20,principal_recovery_amount=1.)),('tax_renewal_fails',dict(tax_fail=True)),('small_minority_triple',dict(small_minor=.0075)),('parent_cash_low',dict(parent_cash=.02)),('old_receipt_year2',dict(old_ar_delay=1)),('parent_payment',dict(extra_payment=.078)),('issue',dict(issue=.5))]
    for n,kw in cfg:paths[n]=run(**kw)
    # Explicit SAME OPERATING BUDGET bridge. Not a purported legal-only theorem: replacement
    # of invented statutory pools necessarily changes the timing/routing budget. No growth/margin/ROIC change.
    for mode in ['base','cyclical','structural','upside']:
        paths['old_'+mode]=legacy_run(mode=mode,discount=.0975)
        paths['same_budget_'+mode]=run(mode=mode,economic_revision=False,small_minor=0,finite_solar=False,redemption=0,reserve_credit=.36530171861)
    conv={str(n):{str(r):{k:v for k,v in run(years=n,discount=r).items() if k!='rows'} for r in [.09,.105]} for n in [300,600,900]}
    epv=[]
    for r,m,d in [(.105,.30,.75),(.09,.33,.85)]:
        mature=(2.5*m*(1-.009836)+.144*.04-.025-.035)/r
        solar_value=sum(.02189/(1+r)**t for t in range(1,21))+.01875/(1+r)**20
        franchise=sum(.04*(1-d**t)/(1-d)*(1-.03/.20)/(1+r)**t for t in range(1,9))
        bridge=.73213186815-.78858193369-.24-.125001897+.07/(1+r)**2+.02/(1+r)**3
        epv.append((mature+solar_value+franchise+bridge)/SHARES)
    output=dict(symbol='CN:002270',units='十亿元；股数十亿股；每股元',source_cutoff='2026-10-26T11:31:00Z',paths=paths,convergence=conv,tests=tests(),method2_epv=epv)
    raw=copy.deepcopy(output);rows={k:v.pop('rows') for k,v in output['paths'].items()}
    output['annual_data']=dict(encoding='gzip-base64 ordinary full JSON rows',schema='paths[name].rows; begin/end literal fields; economic budget is NOT legal entity',expanded_sha256=hashlib.sha256(canonical(raw)).hexdigest(),payload_base64=base64.b64encode(gzip.compress(canonical(rows),mtime=0)).decode())
    assert expand_output(output)==raw
    p=pathlib.Path(__file__).parent;p.joinpath('2026-Q3-output.json').write_bytes(canonical(output))
    p.joinpath('summary.json').write_text(json.dumps({k:{a:v[a] for a in ['pv','tv5','first5','feasible']} for k,v in output['paths'].items()},ensure_ascii=False,indent=2))
    print(p.joinpath('summary.json').read_text())
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--expand');a=parser.parse_args()
    if a.expand:
        o=json.loads(pathlib.Path(__file__).with_name('2026-Q3-output.json').read_text());pathlib.Path(a.expand).write_bytes(canonical(expand_output(o)))
    else:main()
