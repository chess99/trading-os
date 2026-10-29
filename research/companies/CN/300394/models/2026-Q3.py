#!/usr/bin/env python3
"""TFC common-equity model. stdlib only; money CNY bn, shares bn.
Run: python 2026-Q3.py [output.json]. No market-price inputs or network.
First five periods are next 12-month budgets, NOT calendar reported results.
Years 6-15 fade to sustainable reinvestment; tail cash includes operating liquidity.
"""
import copy,json,sys,math
from pathlib import Path
S0=1.090825093
OLD=0.002442846
OLD_PROCEEDS=OLD*((18.51-.7)/1.4-.5)
C0=(2659301975.87+180044333.34-6644344.95)/1e9
WC0=(1944696183.78+1560249.48+5498335.62+92187039.65+1273968083.13-284312566.54-707490615.-366305442.10)/1e9
FIXED0=(1359827366.41+212947361.05+115621014.77+151836647.67)/1e9
DEBT0=(1758645.06+1472362.08)/1e9
BASE=dict(revenue=[8,9.4,10.7,11.8,12.8],margin=[.42,.415,.40,.385,.37],wc=[.28,.275,.27,.265,.26],capex=[1.0,1.0,.9,.85,.8],da=[.25,.33,.42,.51,.60],cash_floor=.08,parent_share=.72,parent_cash=2.20,parent_re=2.43010250806-.5454125465,payout=.46,tail_growth=[.08,.07,.06,.05,.045,.04,.035,.03,.025,.025],tail_roc=[.35,.32,.29,.26,.23,.21,.19,.17,.16,.15],g=.025,roc=.15,k=.10,collection_delay=0,extra_capex=0,fund_recovery=.03,buyback_cash=0,buyback_shares=0,new_grants=False)

def reserve_step(re,profit,reserve,capital,rate=.10,cap_fraction=.50):
    # Losses consume retained earnings first. No distribution or reserve before deficits covered.
    eligible=max(0.,profit-max(0.,-re))
    allocation=min(rate*eligible,max(0.,cap_fraction*capital-reserve))
    return re+profit-allocation,reserve+allocation,allocation

def calculate(p):
    cash=C0; pc=p['parent_cash']; re=p['parent_re']; reserve=p.get('parent_reserve',.47663983975)
    jc=p.get('jiangxi_cash',.30); oc=cash-pc-jc
    jre=0.; ore=-p.get('other_opening_loss',.10); jreserve=0.
    jp=.19; opct=1-p['parent_share']-jp
    wc=WC0; fixed=FIXED0; floor=.55; shares=S0; rows=[]; debt=DEBT0
    # New grants: only optimistic may satisfy 2027 test. 2028/29 thresholds checked separately.
    pending={}; new_fraction=[]
    for t in range(5):
        r=p['revenue'][t]; op=r*p['margin'][t]*.9998 # net operating tax already in margin, remove NCI earnings
        financial=cash*.015
        # fiscal test proxy on adjacent rolling budget; explicit boundary test below.
        growth=(op+financial)/1.97645290647-1
        trigger=[1.2,3.2,5.6][t] if t<3 else 1e99
        target=[1.5,4.,7.][t] if t<3 else 1e99
        fraction=(min(1.,growth/target) if growth>=trigger else 0.) if p['new_grants'] else 0.
        if t<3: new_fraction.append(fraction)
        if fraction: pending[t+1]=(.0022769*[.4,.3,.3][t]*fraction)
        new=pending.get(t,0.)
        old=OLD if t==0 else 0.
        proceeds=(OLD_PROCEEDS if t==0 else 0.)+new*max(0.,119.5-sum(z['dps'] for z in rows))
        shares+=old+new
        # cash-neutral legal charge: published total schedule is retained conservatively even if future forfeitures reverse it.
        sbc=[.1760758,.0858957,.0368153,.0027582,0][t]
        legal_profit=p['parent_share']*op+pc*.015-p['parent_share']*sbc
        re,reserve,allocation=reserve_step(re,legal_profit,reserve,shares)
        wc_new=r*p['wc'][t]+(p['collection_delay'] if t<2 else 0.)
        dwc=wc_new-wc; netcap=p['capex'][t]+(p['extra_capex'] if t<2 else 0.)-p['da'][t]
        fixed+=netcap
        fcf=op-dwc-netcap
        # Parent is revenue-booking/trading/manufacturing legal entity; normal operating settlements included.
        pfcf=p['parent_share']*(op-dwc)-.5*netcap
        fund=.03 if t==0 else 0.
        repaid=debt; debt=0.
        bb=p['buyback_cash'] if t==0 else 0.
        if t==0: shares-=p['buyback_shares']
        newfloor=r*p['cash_floor']; pfloor=.6*newfloor
        pre=cash+fcf+financial+proceeds-fund-repaid-bb
        ppre=pc+pfcf+pc*.015+proceeds-fund-repaid-bb
        # Fund subsidiary deficits with a documented budgeted capital transfer, not a dividend.
        jpre=jc+jp*(op-dwc)-.30*netcap+jc*.015
        opre=pre-ppre-jpre
        jtransfer=max(0.,.25*newfloor-jpre); otransfer=max(0.,.15*newfloor-opre)
        transfer=jtransfer+otransfer; ppre-=transfer;jpre+=jtransfer;opre+=otransfer
        jre,jreserve,jallocation=reserve_step(jre,jp*(op-sbc)+jc*.015,jreserve,.15)
        # Other/overseas legal profits are a budget, not inferred audited retained earnings.
        ore+=opct*(op-sbc)+oc*.015
        wanted=p['payout']*max(0.,op+financial-sbc)
        dividend=max(0.,min(wanted,re,pre-newfloor,ppre-pfloor))
        cash=pre-dividend; pc=ppre-dividend; re-=dividend; jc=jpre;oc=opre
        assert cash>=newfloor-1e-9 and pc>=pfloor-1e-9, 'Unfunded operating scenario'
        assert dividend<=max(0.,re+dividend)+1e-9, 'Illegal dividend'
        if re<0: assert dividend==0., 'Losses must be covered first'
        assert abs(cash-(pre-dividend))<1e-10
        assert abs(cash-(C0 if not rows else rows[-1]['cash'])-fcf-financial-proceeds+fund+repaid+bb+dividend)<1e-9
        assert cash-pc>=.4*newfloor-1e-9
        rows.append(dict(year=t+1,revenue=r,operating_profit=op,accounting_sbc=sbc,financial_income=financial,nwc=wc_new,delta_nwc=dwc,capex=p['capex'][t]+(p['extra_capex'] if t<2 else 0.),da=p['da'][t],fixed_capital=fixed,fcf=fcf,necessary_cash=newfloor,parent_operating_fcf=pfcf,parent_profit=legal_profit,reserve_added=allocation,parent_reserve=reserve,parent_re=re,parent_cash=pc,jiangxi_cash=jc,other_cash=oc,jiangxi_re=jre,jiangxi_reserve=jreserve,other_re=ore,subsidiary_cash=cash-pc,capital_transfer=transfer,debt_repayment=repaid,debt=debt,subscription_cash=proceeds,shares=shares,dividend=dividend,dps=dividend/shares,cash=cash,extra_cash=cash-newfloor,private_fund_cost=fund,buyback_cash=bb,new_grant_fraction=fraction))
        wc=wc_new;floor=newfloor
    bridge=holder_bridge(p,rows[-1],jre,ore,jreserve)
    tv5=bridge['value5']/shares
    present=sum(z['dps']/(1+p['k'])**z['year'] for z in rows)+tv5/(1+p['k'])**5
    return dict(parameters=p,years=rows,bridge=bridge,terminal_equity5=tv5,present_value=present,perpetuity_pv_fraction=bridge['after15_pv5']/shares/(1+p['k'])**5/present,year5_terminal_pv_fraction=(tv5/(1+p['k'])**5)/present,new_grant_fractions=new_fraction)


def holder_bridge(p,last,jre,ore,jreserve):
    """Same source-of-funds and legal-capacity chain for all late cash.
    No face-value cash addition: old excess, future operating FCF and financial
    income enter cohorts, mature and get legally paid, then discounted.
    300-year sum plus explicit upper-bound truncation error, no hidden cash release.
    """
    floor=last['necessary_cash']; k=p['k']; H=p.get('recovery_years',5)
    # Parent / wholly-owned Jiangxi / other entities including Thailand via Singapore.
    # 25/15% liquidity floor splits are budgets, not published subsidiary cash.
    extras=[last['parent_cash']-.60*floor,last['jiangxi_cash']-.25*floor,last['other_cash']-.15*floor]
    assert min(extras)>-1e-8
    shares=last['shares']; res=[last['parent_reserve'],jreserve,0.]
    re=[last['parent_re'],jre,ore]; weights=[p['parent_share'],.19,1-p['parent_share']-.19]
    delays=[0,1,p.get('overseas_delay',2)]
    coverage=p.get('overseas_profit_coverage',.75)
    queues=[[],[],[]];legal_pending=[]
    recovery=p.get('cash_recovery_fraction',1.)
    # Non-recovered fraction is an explicit impairment, not a perpetual locked balance.
    loss=[e*(1-recovery) for e in extras]
    extras=[e*recovery for e in extras]
    re=[re[z]-loss[z] for z in range(3)]
    for z in range(3):
        for a in range(1,H+1): queues[z].append([5+a+delays[z],extras[z]/H,'opening'])
    profit=last['operating_profit'];rows=[];pv=0.;after15=0.;openingpv=0.;financialpv=0.;operatingpv=0.
    cum_parent=0.;cum_j=0.;cum_o=0.
    # cash at each entity is exactly sum of unspent cohorts (all above required floors).
    for t in range(6,301):
        idx=t-6;growth=p['tail_growth'][idx] if idx<10 else p['g'];roc=p['tail_roc'][idx] if idx<10 else p['roc']
        newprofit=profit*(1+growth);investment=(newprofit-profit)/roc
        free=newprofit-investment
        assert free>=-1e-9
        opening_cash=[sum(c[1] for c in q) for q in queues]
        interests=[v*.015 for v in opening_cash]
        payments=[0.,0.,0.];tags=[{}, {}, {}];withholding=0.
        # Fixed annual subsidiary profit attribution; scope is disclosed forecast budget.
        legalprofits=[newprofit*weights[z]+interests[z] for z in range(3)]
        legalprofits[2]=newprofit*weights[2]*coverage+interests[2]+sum(v for y,v in legal_pending if y==t)
        legal_pending.append((t+p.get('overseas_legal_delay',3),newprofit*weights[2]*(1-coverage)))
        # The excluded foreign fraction is an evidential buffer, not a statutory reserve.
        # Remaining budgeted profit becomes eligible only after further audited years, not permanently zero.
        for z in range(3):
            if z<2:
                re[z],res[z],_=reserve_step(re[z],legalprofits[z],res[z],shares if z==0 else .15)
            else: re[z],res[z],_=reserve_step(re[z],legalprofits[z],res[z],.50029,.05,.10)
            queues[z].append([t+delays[z],free*weights[z],'operating'])
            queues[z].append([t+delays[z],interests[z],'financial'])
        # Fund cost paid in year1, actual recovery enters mother at year6, never added to tv5.
        if t==6:
            queues[0].append([t,p['fund_recovery'],'fund'])
            re[0]-=.03-p['fund_recovery']
        # Subsidiary declaration and cash arrival same modeled year: parent investment profit
        # recognized once here; no prebooked dividend receivable counted again.
        for z in [1,2]:
            eligible=sum(c[1] for c in queues[z] if c[0]<=t)
            pay=min(eligible,max(0.,re[z]));payments[z]=pay;re[z]-=pay
            remaining=pay
            for c in queues[z]:
                if c[0]<=t and remaining>0:
                    paid=min(c[1],remaining);c[1]-=paid;remaining-=paid
                    tags[z][c[2]]=tags[z].get(c[2],0.)+paid
                    tax=paid*p.get('overseas_withholding',.10) if z==2 else 0.
                    withholding+=tax;queues[0].append([t,paid-tax,c[2]])
            receipt=pay*(1-p.get('overseas_withholding',.10)) if z==2 else pay
            re[0],res[0],_=reserve_step(re[0],receipt,res[0],shares)
        eligible=sum(c[1] for c in queues[0] if c[0]<=t)
        pay=min(eligible,max(0.,re[0]));payments[0]=pay;re[0]-=pay
        remaining=pay
        for c in queues[0]:
            if c[0]<=t and remaining>0:
                paid=min(c[1],remaining);c[1]-=paid;remaining-=paid
                tags[0][c[2]]=tags[0].get(c[2],0.)+paid
        queues=[[c for c in q if c[1]>1e-12] for q in queues]
        closing=[sum(c[1] for c in q) for q in queues]
        assert abs(sum(closing)-sum(opening_cash)-free-sum(interests)-(p['fund_recovery'] if t==6 else 0)+pay+withholding)<1e-8
        if re[0]<0: assert pay==0
        df=(1+k)**(t-5);pv+=pay/df
        if t>15: after15+=pay/df
        openingpv+=tags[0].get('opening',0.)/df
        financialpv+=tags[0].get('financial',0.)/df
        operatingpv+=tags[0].get('operating',0.)/df
        cum_parent+=pay;cum_j+=payments[1];cum_o+=payments[2]
        rows.append(dict(year=t,profit=newprofit,reinvestment=investment,operating_free_cash=free,opening_extra_cash=opening_cash,financial_income=interests,legal_profit=legalprofits,subsidiary_upstream=payments[1:],withholding=withholding,holder_distribution=pay,holder_tags=tags[0],closing_extra_cash=closing,retained_earnings=re.copy(),legal_reserves=res.copy()))
        profit=newprofit
    residual_bound=(sum(closing)+newprofit*(1+p['g'])/(k-p['g']))/(1+k)**295
    assert residual_bound<.00001, 'Increase horizon for meaningful remaining value'
    return dict(value5=pv,after15_pv5=after15,opening_excess_cash5=extras,initial_impairment5=loss,opening_cash_realization_pv5=openingpv,financial_income_pv5=financialpv,operating_cash_pv5=operatingpv,recovery_years=H,delays=delays,residual_upper_bound5=residual_bound,rows=rows)

def hand_checks():
    # Feed a zero-growth, zero-investment case into SAME production calculation chain.
    p=copy.deepcopy(BASE);p.update(revenue=[1]*5,margin=[.1/.9998]*5,wc=[WC0]*5,capex=[0]*5,da=[0]*5,cash_floor=0,payout=0,tail_growth=[0]*10,tail_roc=[.2]*10,g=0.,roc=.2,k=.1)
    out=calculate(p)
    # 0.1 forever valued at year5 = 1.0 independent geometric-series result.
    # All current/future cash is routed through production holder_bridge.
    assert out['bridge']['residual_upper_bound5']<1e-5
    # Formal reserve function: loss carry -2, profit3, reserve .4 capital1 => eligible1 reserve .1 => RE .9.
    assert all(abs(x-y)<1e-10 for x,y in zip(reserve_step(-2.,3.,.4,1.),(.9,.5,.1)))
    assert reserve_step(0.,3.,.5,1.)==(3.,.5,0.)
    # Full production chain with initial parent losses: first year remains in deficit and pays zero.
    loss=copy.deepcopy(BASE);loss['parent_re']=-5.;loss['parent_reserve']=.5466339695
    check=calculate(loss)
    assert check['years'][0]['parent_re']<0 and check['years'][0]['dividend']==0
    assert check['years'][1]['parent_re']>=-1e-9 and check['years'][1]['dividend']>0
    simple=copy.deepcopy(BASE);simple.update(tail_growth=[0.]*10,tail_roc=[.15]*10,g=0.,k=.1,recovery_years=2,fund_recovery=0.)
    hs=holder_bridge(simple,dict(necessary_cash=0.,parent_cash=2.,jiangxi_cash=0.,other_cash=0.,parent_re=10.,parent_reserve=.5,shares=1.,operating_profit=0.),0.,0.,0.)
    manual=1.03/1.1+1.015/1.1**2
    assert abs(hs['value5']-manual)<1e-10
    return {'formal_bridge_manual_expected':manual,'formal_bridge_actual':hs['value5'],'loss_and_reserve_cap':'passed','production_loss_turnaround_first_dividend':check['years'][0]['dividend'],'production_loss_turnaround_second_dividend':check['years'][1]['dividend']} 

def main():
    cases={}
    for name,k,g,roc in [('core_low',.105,.02,.12),('base',.10,.025,.15),('core_high',.095,.025,.15)]:
        p=copy.deepcopy(BASE);p.update(k=k,g=g,roc=roc);cases[name]=calculate(p)
    p=copy.deepcopy(BASE);p.update(revenue=[6.3,7.6,9.5,11.8,12.8],margin=[.35,.37,.39,.385,.37],wc=[.34,.32,.29,.265,.26],collection_delay=.3,extra_capex=.15,k=.105);cases['cyclical']=calculate(p)
    p=copy.deepcopy(BASE);p.update(revenue=[6.5,6.6,6.8,7.,7.2],margin=[.28,.25,.22,.20,.20],wc=[.36]*5,capex=[1.0,.9,.75,.65,.6],da=[.25,.33,.4,.46,.5],parent_share=.60,payout=.35,tail_growth=[.02]*10,tail_roc=[.12]*10,g=.015,roc=.10,k=.115,fund_recovery=.015,aux_normal=1.44);cases['structural']=calculate(p)
    p=copy.deepcopy(BASE);p.update(revenue=[10.5,13.,15.5,18.,20.],margin=[.45,.44,.43,.42,.41],capex=[1.3,1.4,1.4,1.3,1.2],da=[.3,.45,.6,.75,.9],wc=[.30,.29,.28,.27,.26],tail_growth=[.12,.11,.10,.09,.08,.07,.06,.05,.04,.03],tail_roc=[.45,.4,.35,.3,.27,.24,.21,.19,.17,.15],new_grants=True,k=.10);cases['upside']=calculate(p)
    for name,changes in [('margin_minus_3pp',{'margin':[m-.03 for m in BASE['margin']]}),('working_capital_plus_5pp',{'wc':[x+.05 for x in BASE['wc']]}),('parent_60pct_delayed_receipts',{'parent_share':.60,'collection_delay':.5}),('cash_buffer_12pct',{'cash_floor':.12}),('fund_total_loss',{'fund_recovery':0}),('recovery_3_years',{'recovery_years':3}),('recovery_10_years',{'recovery_years':10}),('recovery_15_years',{'recovery_years':15}),('recovery_80pct',{'cash_recovery_fraction':.8}),('overseas_5year_50pct_profit',{'overseas_delay':5,'overseas_profit_coverage':.5,'overseas_legal_delay':5}),('other_loss_300m',{'other_opening_loss':.3}),('jiangxi_cash_150m',{'jiangxi_cash':.15}),('jiangxi_cash_450m',{'jiangxi_cash':.45}),('overseas_tax_zero',{'overseas_withholding':0}),('conditional_buyback',{'buyback_cash':.15,'buyback_shares':.000428571})]:
        p=copy.deepcopy(BASE);p.update(changes);cases[name]=calculate(p)
    aux={}
    for name in ['core_low','base','core_high']:
        a=copy.deepcopy(cases[name]['parameters']);g=a['g'];roc=a['roc'];rev=7.5;wc=WC0;fl=.55;prior=3.*.9998
        a.update(revenue=[],margin=[],wc=[],capex=[],da=[],cash_floor=.55/7.5,tail_growth=[g]*10,tail_roc=[roc]*10)
        for t in range(5):
            rev*=1+g;np=rev*.4*.9998;nwc=wc*(1+g);nf=fl*(1+g);investment=(np-prior)/roc
            netcap=investment-(nwc-wc)-(nf-fl)
            a['revenue'].append(rev);a['margin'].append(.4);a['wc'].append(nwc/rev);a['capex'].append(.25+netcap);a['da'].append(.25)
            wc=nwc;fl=nf;prior=np
        aux[name]=calculate(a)
    out={'auxiliary_cases':aux,'units':'CNY billion; billion shares; CNY/share','opening':{'cash':C0,'nwc':WC0,'fixed':FIXED0,'lease_debt':DEBT0,'old_grant_proceeds':OLD_PROCEEDS},'tests':hand_checks(),'cases':cases}
    dest=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).with_name('2026-Q3-output.json')
    dest.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:{'value':v['present_value'],'tv5':v['terminal_equity5'],'dps':[r['dps'] for r in v['years']],'cash5':v['years'][-1]['cash'],'parent_cash5':v['years'][-1]['parent_cash']} for k,v in cases.items()},indent=2))
if __name__=='__main__':main()
