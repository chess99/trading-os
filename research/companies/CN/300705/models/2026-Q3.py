#!/usr/bin/env python3
"""Conditional economics, NOT a published reliable value/holder forecast. CNY million.
Pure stdlib. stdout is full deterministic JSON; independent of cwd and external files.
"""
import json, math, copy
FACTS={'revenue9m':2048.72312008,'profit9m':239.90538981,'deducted9m':229.83217755,'cfo9m':480.30929773,'capex9m':228.20013282,'cash_equivalent':529.20261284,'financial_assets':180.34807948,'deposit':70.0,'shares':500.294904,'treasury':6.1808,'bond_face':205.2212,'bond_conversion_price':14.55,'minority_equity':147.44477136,'parent_cash_H1':192.07320280,'parent_financial_H1':20.002,'parent_deposit_H1':70.0,'parent_retained_H1':1178.32342544,'parent_statutory_H1':200.82707075}
ENTITIES={'parent':{'own':1.,'capital':500.294904,'reserve':200.82707075,'retained':1178.32342544,'cash':282.0752028},'hongyang':{'own':1.,'capital':233.7295,'reserve':60.,'retained':230.,'cash':220.},'yiyao':{'own':1.,'capital':50.,'reserve':15.,'retained':35.,'cash':100.},'pudao':{'own':1.,'capital':50.,'reserve':15.,'retained':30.,'cash':30.},'nuona':{'own':.7,'capital':50.,'reserve':0.,'retained':-20.,'cash':100.},'shannuo':{'own':.50,'capital':100.,'reserve':0.,'retained':-2.,'cash':47.47548952}}
# Shannuo direct 50% only: indirect 12% is retained solely within investment recovery, never twice.
# Parent opening legal figures are observed H1. All subsidiary legal balances/cash allocations
# above are explicitly CONDITIONAL budgets, NOT reported balances. This gap prevents publication.
CONFIGS={
'base':{'rev':[1100.,1050.,650.],'growth':[.06,.05,.06],'gm':[.68,.72,.34],'sell':.32,'admin':.072,'rd':.08,'capex':240.,'wc':.23,'rate':.105,'g':.015,'roi':.12,'nona':[ -25.,-15.,-5.,5.,10.],'buyback':150.,'recover':.75},
'cyclical':{'rev':[950.,1000.,610.],'growth':[.09,.06,.06],'gm':[.64,.70,.33],'sell':.33,'admin':.08,'rd':.085,'capex':230.,'wc':.28,'rate':.115,'g':.01,'roi':.10,'nona':[-35.,-25.,-10.,0.,6.],'buyback':155.,'recover':.65},
'structural':{'rev':[820.,940.,590.],'growth':[.01,.02,.02],'gm':[.59,.67,.31],'sell':.32,'admin':.085,'rd':.09,'capex':210.,'wc':.28,'rate':.12,'g':0.,'roi':.08,'nona':[-35.,-30.,-25.,-20.,-20.],'buyback':160.,'recover':.5},
'upside':{'rev':[1250.,1150.,700.],'growth':[.08,.07,.07],'gm':[.71,.73,.35],'sell':.315,'admin':.068,'rd':.08,'capex':270.,'wc':.23,'rate':.10,'g':.02,'roi':.14,'nona':[-15.,-5.,5.,15.,25.],'buyback':0.,'recover':.85}}

def legal_step(state,profit,fcf,requested,buffer,debt_payment=0.,financing=0.):
    """Production legal-and-cash gate: losses replenished before 10% reserve, cap 50%."""
    opening=copy.deepcopy(state)
    eligible=max(0.,profit+min(0.,state['retained']))
    reserve=min(max(0.,.5*state['capital']-state['reserve']),.1*eligible)
    state['reserve']+=reserve
    state['retained']+=profit-reserve
    pre=state['cash']+fcf-debt_payment+financing
    paid=min(max(0.,requested),max(0.,state['retained']),max(0.,pre-buffer))
    state['cash']=pre-paid;state['retained']-=paid
    assert abs(state['cash']-(opening['cash']+fcf-debt_payment+financing-paid))<1e-7
    return {'profit':profit,'fcf':fcf,'reserve_added':reserve,'paid':paid,'cash':state['cash'],'retained':state['retained'],'debt_payment':debt_payment,'financing':financing,'liquidity_shortfall':max(0.,buffer-state['cash'])}

def economic(c,y,method):
    # Five-year fade, then 1.5%/scenario terminal growth; no automatic restoration to peak margin.
    rev=[v*(1+g)**min(y-1,4)*(1+c['g'])**max(y-5,0) for v,g in zip(c['rev'],c['growth'])]
    if method=='normalised_segments':
        # Independent unit economics: segment cash operating margins AFTER all recurrent selling,
        # administration, tax and innovation replacement costs; not copied from primary DPS/earnings.
        margins={'base':[.105,.115,.11],'cyclical':[.075,.10,.09], 'structural':[.025,.075,.065],'upside':[.13,.13,.12]}[c['name']]
        nopat=sum(a*b for a,b in zip(rev,margins))
    else:
        gross=sum(a*b for a,b in zip(rev,c['gm']))
        nopat=(gross-sum(rev)*(c['sell']+c['admin']+c['rd']+.012))*.82
    # tangible and intangible maintenance includes replacement innovation; R&D expense above separate.
    da=170.*(1+c['g'])**(y-1)
    prev=sum(c['rev']) if y==1 else sum(economic_revenue(c,y-1))
    dwc=max(0.,sum(rev)-prev)*c['wc']
    capex=c['capex']*(1+c['g'])**(y-1) if y<=5 else da+max(0.,nopat)*c['g']/c['roi']-dwc
    capex=max(da,capex) if y>5 else capex
    return {'revenue':rev,'nopat':nopat,'da':da,'capex':capex,'dwc':dwc,'fcff':nopat+da-capex-dwc}
def economic_revenue(c,y):return [v*(1+g)**min(y-1,4)*(1+c['g'])**max(y-5,0) for v,g in zip(c['rev'],c['growth'])]

def run(config,method='operating_dcf',conversion=False,release_start=6,horizon=240):
    c=copy.deepcopy(config);s=copy.deepcopy(ENTITIES);rows=[];shares=FACTS['shares']-FACTS['treasury']
    # H1 observed parent bank: 85.5m credit + .98624m short borrowing.
    # H1 Hongyang: 171.71508m mortgage + 112.5m guaranteed loans.
    # Q3 aggregate 567.32141165m includes current portions. Remaining 196.62009165m
    # borrower not identified in Q3: CONDITIONALLY assigned parent treasury, not reported legal debt.
    initial_bank={'parent':283.10633165,'hongyang':284.21508}
    banks=copy.deepcopy(initial_bank);extra_debt=0.;repay_extra=0.;failed=False
    for y in range(1,horizon+1):
        opening_group_cash=sum(v['cash'] for v in s.values())
        eco=economic(c,y,method);nona=c['nona'][min(y-1,4)]*(1+c['g'])**max(y-5,0);shannuo=-12.*(1+c['g'])**(y-1)
        bank_interest={k:v*.035 for k,v in banks.items()};extra_interest=extra_debt*.06
        bond_coupon=FACTS['bond_face']*([.015,.025,0.][min(y-1,2)]) if not conversion else 0.
        bond_payment=FACTS['bond_face']*1.13 if y==3 and not conversion else 0.
        bond_premium=FACTS['bond_face']*.13 if bond_payment else 0.
        if conversion and y==1:shares+=FACTS['bond_face']/FACTS['bond_conversion_price']
        buyback=c['buyback'] if y==3 else 0.
        if buyback:s['nuona']['own']=1.
        # Normal renewal years 1-10. Actual cash amortization years 11-15, not a terminal bridge.
        if y==11:repay_extra=extra_debt/5
        bank_principal={k:min(v,initial_bank[k]/5) if 11<=y<=15 else 0. for k,v in banks.items()}
        extra_principal=min(extra_debt,repay_extra) if 11<=y<=15 else 0.
        profits={'hongyang':eco['revenue'][2]*.18,'yiyao':sum(eco['revenue'][:2])*.06,'pudao':35.*(1+c['g'])**(y-1),'nuona':nona,'shannuo':shannuo}
        profits['parent']=eco['nopat']-sum(profits.values())-bank_interest['parent']-extra_interest-bond_coupon-bond_premium
        profits['hongyang']-=bank_interest['hongyang']
        interest=sum(bank_interest.values())+extra_interest+bond_coupon
        netinvest=eco['capex']-eco['da']+eco['dwc'];alloc={'parent':.45,'hongyang':.40,'yiyao':.05,'pudao':.03,'nuona':.05,'shannuo':.02}
        sub={};up=0.;nci=0.;internal_injections=0.;internal_dividends=0.
        for k in ['hongyang','yiyao','pudao','nuona','shannuo']:
            buffer={'hongyang':60.,'yiyao':40.,'pudao':10.,'nuona':20.,'shannuo':15.}[k]*(1+c['g'])**(y-1)
            fcf=profits[k]-netinvest*alloc[k];payment=bank_principal.get(k,0.)
            need=max(0.,buffer-s[k]['cash']-fcf+payment)
            requested=max(0.,profits[k])*(.5 if y<release_start else 1.)
            if y>=release_start:requested+=max(0.,s[k]['cash']-buffer)/max(1,release_start+4-y)
            sub[k]=legal_step(s[k],profits[k],fcf,requested,buffer,debt_payment=payment,financing=need)
            up+=sub[k]['paid']*s[k]['own']-need
            internal_injections+=need;internal_dividends+=sub[k]['paid']*s[k]['own']
            nci+=sub[k]['paid']*(1-s[k]['own'])
        recovery=(158.45492372+98.86831149)*c['recover'] if y==8 else 0.
        # Premium reduces legal income, but full 113% cash is booked ONCE below.
        fcf=profits['parent']+bond_premium-netinvest*alloc['parent']+up+recovery
        legalprofit=profits['parent']+internal_dividends
        common=eco['nopat']-interest-bond_premium-nona*(1-s['nuona']['own'])-shannuo*(1-s['shannuo']['own'])
        buffer=100.*(1+c['g'])**(y-1)
        requested=max(0.,common)*(.4 if y<release_start else 1.)
        if y>=release_start:requested+=max(0.,s['parent']['cash']-buffer)/max(1,release_start+4-y)
        payment=bank_principal['parent']+extra_principal+bond_payment+buyback
        needed=max(0.,buffer-s['parent']['cash']-fcf+payment)
        draw=min(needed,max(0.,150.-extra_debt)) if y<=10 else 0.
        extra_debt+=draw-extra_principal
        for k in banks:banks[k]-=bank_principal[k]
        par=legal_step(s['parent'],legalprofit,fcf,requested,buffer,payment,draw)
        if par['liquidity_shortfall']>1e-6:failed=True
        closing_group_cash=sum(v['cash'] for v in s.values())
        expected=opening_group_cash+eco['fcff']-interest+recovery+draw-sum(bank_principal.values())-extra_principal-bond_payment-buyback-par['paid']-nci
        residual=closing_group_cash-expected
        assert abs(residual)<1e-7*max(1.,closing_group_cash)
        assert abs(sum(profits.values())-(eco['nopat']-interest-bond_premium))<1e-7*max(1.,abs(eco['nopat']))
        rows.append({'year':y,'economic':eco,'common_profit':common,'subsidiaries':sub,'parent':par,'bank_debt_by_budget_entity':copy.deepcopy(banks),'bank_interest_by_budget_entity':bank_interest,'bank_principal_by_budget_entity':bank_principal,'additional_debt':extra_debt,'additional_principal':extra_principal,'external_new_financing':draw,'bond_payment':bond_payment,'bond_premium_legal_expense':bond_premium,'minority_buyback':buyback,'investment_recovery':recovery,'minority_distribution':nci,'internal_injections':internal_injections,'internal_dividends':internal_dividends,'group_cash_open':opening_group_cash,'group_cash_close':closing_group_cash,'group_cash_expected':expected,'group_cash_conservation_residual':residual,'shares':shares,'dps':par['paid']/shares,'entity_state':copy.deepcopy(s)})
        if y==15 and not failed:assert sum(banks.values())+extra_debt<1e-7
        if failed:break
    rate=c['rate'];g=c['g']
    pv=sum(r['dps']/(1+rate)**r['year'] for r in rows)
    terminal5=sum(r['dps']/(1+rate)**(r['year']-5) for r in rows if r['year']>5)
    checks={}
    if not failed:
        assert sum(banks.values())+extra_debt<1e-7
        # Loss-maker Shannuo remains funded in every year; never disappears at a horizon boundary.
        assert rows[-1]['subsidiaries']['shannuo']['profit']<0 and rows[-1]['internal_injections']>0
        for key in ['dps']:
            assert abs(rows[-1][key]/rows[-2][key]-(1+g))<1e-8
        for k in s:
            for key in ['cash','profit']:
                latest=rows[-1]['parent' if k=='parent' else 'subsidiaries']
                prior=rows[-2]['parent' if k=='parent' else 'subsidiaries']
                if k!='parent':latest=latest[k];prior=prior[k]
                assert abs(latest[key]/prior[key]-(1+g))<1e-7
            assert s[k]['reserve']<=s[k]['capital']/2+1e-7
        checks={'debt_fully_paid_year15':True,'all_entity_cash_and_legal_profit_growth_match':True,'persistent_loss_funding_included':True,'holder_dividend_growth_matches':True,'no_terminal_shortcut':True}
    tail_bound=(rows[-1]['dps']/(1+rate)**horizon)*((1+g)/(1+rate))/(1-(1+g)/(1+rate)) if not failed else None
    return {'tail_truncation_bound_under_verified_steady_recurrence':tail_bound,'status':'infeasible' if failed else 'conditional_feasible','method':method,'assumptions':c,'conversion':conversion,'release_start':release_start,'numerical_horizon':horizon,'rows':rows,'current_value':None if failed else pv,'terminal_year5':None if failed else terminal5,'infeasibility':{'year':rows[-1]['year'],'parent_cash_shortfall':rows[-1]['parent']['liquidity_shortfall'],'additional_financing_unsecured':True} if failed else None,'first5_dps':None if failed else [r['dps'] for r in rows[:5]],'year5_tail_pv_share':terminal5/(1+rate)**5/pv if pv and not failed else None,'steady_state_checks':checks}

def tests():
    # Same production legal_step, independent hand answers.
    s={'cash':100.,'retained':-20.,'reserve':48.,'capital':100.}
    a=legal_step(s,10.,10.,99.,0.) # old losses remain: no reserve, no distribution
    assert a['paid']==0 and s['retained']==-10 and s['cash']==110
    b=legal_step(s,40.,40.,99.,0.) # first cover 10 loss, reserve min(3,2)=2; 28 paid
    assert b['reserve_added']==2 and b['paid']==28 and s['cash']==122 and s['retained']==0
    s={'cash':20.,'retained':100.,'reserve':50.,'capital':100.}
    c=legal_step(s,10.,10.,50.,5.,debt_payment=24.,financing=4.)
    assert c['paid']==5 and s['cash']==5 and s['retained']==105
    return {'loss_to_profit_reserve_cap':{'first':a,'second':b},'debt_and_funding':c}

def main():
    runs={}
    for name,c in CONFIGS.items():
        c=dict(c,name=name)
        runs[name]=run(c);runs[name+'_normalised']=run(c,'normalised_segments')
    b=dict(CONFIGS['base'],name='base')
    sensitivities={}
    for key,val in [('gm',[.63,.72,.34]),('rd',.10),('recover',.5),('rate',.12)]:
        p=copy.deepcopy(b);p[key]=val;sensitivities[key]=run(p)
    sensitivities['release_y10']=run(b,release_start=10)
    sensitivities['all_bond_converted']=run(b,conversion=True)
    convergence={}
    for key,full in {**runs,**sensitivities}.items():
        if full['status']=='conditional_feasible':
            short=[run(full['assumptions'],full['method'],full['conversion'],full['release_start'],h) for h in (160,200)]
            vals=[v['current_value'] for v in short]+[full['current_value']]
            assert abs(vals[-1]-vals[0])/vals[-1]<1e-5
            convergence[key]={'horizons':[160,200,240],'values':vals,'year5_values':[v['terminal_year5'] for v in short]+[full['terminal_year5']],'max_relative_gap':abs(vals[-1]-vals[0])/vals[-1]}
    out={'convergence':convergence,'units':'CNY million except shares million and per-share CNY','purpose':'conditional diagnostics only; value_range and return_model null because normalised net-price/channel cost and legal cash attribution are not constrained','facts':FACTS,'opening_entity_budget':ENTITIES,'runs':runs,'sensitivities':sensitivities,'production_hand_cases':tests()}
    print(json.dumps(out,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False))
if __name__=='__main__':main()
