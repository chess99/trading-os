#!/usr/bin/env python3
"""特宝生物2026-Q3；stdlib only；CNY million except per-share; no market-price inputs.
Y1-Y5 consecutive forecast years ending approximately Oct 2027-31.
Three economic/legal cash blocks: listed operating parent P, wholly-owned patent B,
wholly-owned research R. Opening entity allocations are estimates (see report).
"""
import json, math, copy
from pathlib import Path
SHARES=(408189480-10821089+4334528)/1e6
OPEN={'P':2005.2855085,'B':195.0,'R':40.0}
# 884.43647815 cash equivalents +1355.84903035 liquid financial assets.
BASE={
 'hbv':[3250,3350,3350,3300,3200,3100,3000,2900,2800,2700],
 'gh':[800,1050,1300,1500,1650,1800,1930,2050,2150,2220],
 'other':[320,350,380,400,420,440,455,465,470,470],
 'new':[0,0,0,100,300,450,600,700,750,780],
 'rd':[500,540,580,620,650,680,700,710,710,710],
 'milestones':[80,100,160,150,120,100,80,60,50,50],
 'capex':[520,470,400,330,300,300,300,300,300,300],
 'da':[145,165,185,210,235,255,275,290,300,300],
 'gross':[.887,.883,.878,.873,.868,.863,.858,.853,.85,.85],
 'sell':[.355,.35,.345,.34,.335,.335,.335,.335,.335,.335],
 'admin':[.085]*10, 'donation':[.018]*10,
 'research_sub':[90,100,110,120,130,135,140,140,140,140],
 'nwc_ratio':.34,'nwc_open':1471.73526582,'tail_decay':-.02,
 'bank_limit':1100.,'bank_rate':.035,'yield':.012,
 'payout':.30,'b_payout':.60,'old_settlement_years':4,
 'initial_cash':OPEN,'initial_retained':{'P':1950.,'B':600.,'R':-100.},
 'delay':1,'fund_recovery_year':8,'fund_recovery':161.65239399,
 'convert':False, 'zero_dividend':False,'revenue_multiplier':1.,'gh_multiplier':1.,
 'shift_parent_to_sub':0.,'reserve_extra':0.,
}

def legal_profit(retained,reserve,capital,profit):
    """Cumulative losses persist. Statutory 10% only after prior losses recovered;
    contribution stops at half paid-up capital, never treats capital injection as profit."""
    taxable_profit=max(0.,profit+min(0.,retained))
    add=min(max(0.,.5*capital-reserve),.1*taxable_profit)
    return retained+profit-add,reserve+add,add

def simulate(cfg):
    c=copy.deepcopy(cfg); cash=dict(c['initial_cash']);cash['P']-=c['shift_parent_to_sub'];cash['B']+=c['shift_parent_to_sub']
    retained=dict(c['initial_retained']);reserve={'P':205.43661109,'B':21.,'R':0.}
    capital={'P':408.18948,'B':42.,'R':700.}
    debt=39.78476663+711.29327388+17.73298847+26.93038998
    bond=1533.266; receivable=320.; payable=320.;pending=[]
    shares=SHARES; issue=4.334528*38.57
    prev_nwc=c['nwc_open']; earmarked=1400.; rows=[]; failure=None
    for y in range(1,c.get('horizon',250)+1):
        i=min(y-1,9); fade=(1+c['tail_decay'])**max(0,y-10)
        seg={k:c[k][i]*fade*c['revenue_multiplier']*(c['gh_multiplier'] if k=='gh' else 1.) for k in ('hbv','gh','other','new')}
        rev=sum(seg.values()); rd=c['rd'][i]*fade; milestone=c['milestones'][i]*fade
        capex=c['capex'][i]*fade; da=c['da'][i]*fade
        # Revenue-linked royalty paid to external licensor on new HBV drugs; milestones expensed once.
        group_ebit=rev*(c['gross'][i]-c['sell'][i]-c['admin'][i]-c['donation'][i])-rd-milestone-.08*seg['new']
        research=c['research_sub'][i]*fade
        internal_rate=.06 if y==1 else (.045 if y==2 else .03)
        b_rev=(seg['hbv']+seg['gh'])*internal_rate
        b_ebit=.8*b_rev
        p_ebit=group_ebit-b_ebit+research
        r_ebit=-research
        nwc=rev*c['nwc_ratio']; delta_nwc=nwc-prev_nwc;prev_nwc=nwc
        retained_open=dict(retained)
        begin=dict(cash);begin_debt=debt; external_issue=issue if y==1 else 0.
        cash['P']+=external_issue
        if y==1:capital['P']+=4.334528
        interest={k:max(0.,begin[k])*c['yield'] for k in cash}
        bank_interest=debt*c['bank_rate']
        bond_coupon=(bond*[.001,.003,.006,.01,.015][y-1]) if y<=5 else 0.
        conversion=0.
        if c['convert'] and y==1:
            conversion=bond/58.56;shares+=conversion;bond=0.;bond_coupon=0.
        # Year 6 redemption 108% includes final coupon; only 8% premium affects P&L,
        # principal does not; coupon not separately charged in year 6.
        redemption=bond*1.08 if y==6 else 0.
        premium=bond*.08 if y==6 else 0.
        pretax={'P':p_ebit+interest['P']-bank_interest-bond_coupon-premium,'B':b_ebit+interest['B'],'R':r_ebit+interest['R']}
        tax={k:max(0.,pretax[k])*(.15 if k!='R' else .25) for k in cash}
        profit={k:pretax[k]-tax[k] for k in cash}
        cf={'P':profit['P']+.9*da-.9*capex-delta_nwc+premium,
            'B':profit['B']+.05*da-.05*capex,
            'R':profit['R']+.05*da-.05*capex}
        for k in cash:cash[k]+=cf[k]
        repayment=min(debt,150.) if 2<=y<=7 else 0.
        cash['P']-=repayment+redemption
        debt-=repayment
        if redemption:bond=0.
        other_obligation=31.49177387 if y==2 else 0.;cash['P']-=other_obligation
        fund_recovery=c['fund_recovery'] if y==c['fund_recovery_year'] else 0.
        cash['P']+=fund_recovery
        # Recovery is asset principal, not new profit; only losses/profits beyond book enter earnings.
        if fund_recovery:
            profit['P']+=fund_recovery-161.65239399
        settlement=min(receivable,320./c['old_settlement_years'])
        cash['P']-=settlement;cash['B']+=settlement;receivable-=settlement;payable-=settlement
        upstream=sum(v for due,v in pending if due==y)
        cash['B']-=upstream;cash['P']+=upstream
        pending=[(d,v) for d,v in pending if d>y]
        # Parent tops up research cash, capital increase not P&L and not R retained profit.
        r_floor=20.*fade
        support=max(0.,r_floor-cash['R']);cash['P']-=support;cash['R']+=support;capital['R']+=support
        earmarked=max(0.,earmarked-min(earmarked,.65*capex+.2*rd))
        floor_runoff=(1+c['tail_decay'])**max(0,y-20)
        p_floor=max(250.*floor_runoff,.10*rev)+earmarked+c['reserve_extra']*floor_runoff;b_floor=30.*fade
        # finite bridge financing only for necessary operations, never dividend.
        draw=max(0.,p_floor-cash['P']); permitted=max(0.,c['bank_limit']-debt)
        if draw>permitted+1e-7:
            failure={'year':y,'required_draw':draw,'available_draw':permitted,'cash_before_draw':cash['P']};break
        cash['P']+=draw;debt+=draw
        # Conservative new debt accrues half-year interest immediately, with no assumed tax shield.
        new_interest=draw*c['bank_rate']*.5;cash['P']-=new_interest;profit['P']-=new_interest
        if cash['P']<0:failure={'year':y,'reason':'negative parent cash after interest'};break
        adds={}
        for k in cash:retained[k],reserve[k],adds[k]=legal_profit(retained[k],reserve[k],capital[k],profit[k])
        # Declare only funded amounts. Pay with one-year lag; reserve the declared cash at B.
        reserved=sum(v for _,v in pending)
        target_b=c['b_payout']*max(0.,profit['B'])
        if 5<y<=20:target_b+=.25*max(0.,cash['B']-b_floor-reserved)
        if y>=25:target_b=max(0.,cash['B']-b_floor-reserved)
        bdiv=min(max(0.,retained['B']),max(0.,cash['B']-b_floor-reserved),target_b)
        retained['B']-=bdiv
        # New declarations enter P's earnings, not twice on receipt.
        retained['P'],reserve['P'],padd=legal_profit(retained['P'],reserve['P'],capital['P'],bdiv);adds['P']+=padd
        pending.append((y+c['delay'],bdiv))
        group_profit=sum(profit.values())
        target_p=c['payout']*max(0.,group_profit) if y<=5 else .7*max(0.,group_profit)+.25*max(0.,cash['P']-p_floor)
        if 20<y<23:target_p=.7*max(0.,group_profit)
        if y>=23:target_p=max(0.,cash['P']-p_floor)
        if c['zero_dividend']:target_p=0.
        pdiv=min(target_p,max(0.,cash['P']-p_floor),max(0.,retained['P']))
        cash['P']-=pdiv;retained['P']-=pdiv
        assert abs(retained['P']-(retained_open['P']+profit['P']+bdiv-adds['P']-pdiv))<1e-6
        assert abs(retained['B']-(retained_open['B']+profit['B']-adds['B']-bdiv))<1e-6
        assert abs(retained['R']-(retained_open['R']+profit['R']-adds['R']))<1e-6
        # Independent external cash identity eliminates all internal settlement/support/dividend flows.
        expected=sum(begin.values())+sum(cf.values())+external_issue+draw-repayment-redemption-other_obligation+fund_recovery-pdiv-new_interest
        error=sum(cash.values())-expected
        assert abs(error)<1e-6,(y,error)
        assert min(cash.values())>=-1e-7
        assert abs(payable-receivable)<1e-9
        assert cash['B']+1e-7>=sum(v for _,v in pending)
        # recurring sustainable FCFE excludes financing income, debt flows, asset recovery.
        sustainable=sum(v-max(0.,v)*(.25 if k=='R' else .15) for k,v in {'P':p_ebit,'B':b_ebit,'R':r_ebit}.items())+da-capex-delta_nwc
        rows.append({'year':y,'segments':seg,'revenue':rev,'group_ebit':group_ebit,'rd':rd,'milestones':milestone,'capex':capex,'da':da,'nwc':nwc,'delta_nwc':delta_nwc,'profit':profit,'group_profit':group_profit,'operating_capital_cash':cf,'cash_open':begin,'cash_close':dict(cash),'retained':dict(retained),'reserve':dict(reserve),'statutory_add':adds,'debt':debt,'bond_face':bond,'bank_interest':bank_interest+new_interest,'bond_coupon':bond_coupon,'bond_redemption':redemption,'borrow':draw,'repay':repayment,'research_support':support,'internal_old_settlement':settlement,'internal_old_remaining':receivable,'sub_declared':bdiv,'sub_received':upstream,'sub_dividend_receivable':sum(v for _,v in pending),'common_dividend':pdiv,'dps':pdiv/shares,'shares':shares,'equity_issue_cash':external_issue,'fund_recovery':fund_recovery,'earmarked_cash':earmarked,'parent_cash_floor':p_floor,'sustainable_fcfe':sustainable,'cash_conservation_error':error,'paid_capital':dict(capital),'pending_dividends':list(pending),'research_accumulated_loss':min(0.,retained['R'])})
    return {'feasible':failure is None,'failure':failure,'rows':rows,'shares':shares,'tail_decay':c['tail_decay'],'fund_recovery_year':c['fund_recovery_year']}

def valuation(run,r,g=None):
    if not run['feasible']:return {'feasible':False,'value':None,'failure':run['failure']}
    rows=run['rows'];g=run['tail_decay'] if g is None else g
    # Actual legal dividends only, including 230 post-Y20 years. No FCFE terminal plus
    # separately capitalised financial principal; all cash earns, pays, or remains trapped.
    value=sum(x['dps']/(1+r)**x['year'] for x in rows)
    tv5=sum(x['dps']/(1+r)**(x['year']-5) for x in rows if x['year']>5)
    tail=sum(x['common_dividend']/(1+r)**(x['year']-20) for x in rows if x['year']>20)
    d5=sum(x['dps']/(1+r)**x['year'] for x in rows[:5])
    assert abs(value-d5-tv5/(1+r)**5)<1e-8
    last=rows[-1]
    return {'feasible':True,'discount_rate':r,'g':g,'value':value,'tv5':tv5,'dps':[x['dps'] for x in rows[:5]],'tv5_pv_fraction':tv5/(1+r)**5/value,'tail20_pv_fraction':tail/run['shares']/(1+r)**20/value,'terminal20_total':tail,'tail_method':'actual legal distributions Y21-Y250; no residual capital repayment credited','year250_uncredited_cash':last['cash_close'],'year250_retained':last['retained'],'year250_pending':last['pending_dividends'],'year250_cash_pv_per_share':sum(last['cash_close'].values())/run['shares']/(1+r)**250}

def variants():
    out={'base':copy.deepcopy(BASE)}
    cyc=copy.deepcopy(BASE)
    for k in ['hbv','gh','other']:
        cyc[k]=[v*m for v,m in zip(cyc[k],[.85,.9,.95,1,1,1,1,1,1,1])]
    cyc['nwc_ratio']=.39;cyc['capex']=[520,450,420,330,300,300,300,300,300,300];out['cyclical']=cyc
    bad=copy.deepcopy(BASE)
    bad['hbv']=[3000,2700,2400,2100,1850,1650,1500,1370,1250,1150]
    bad['gh']=[650,780,850,900,920,930,930,920,900,880];bad['new']=[0]*10
    bad['gross']=[.87,.85,.83,.81,.80,.80,.80,.80,.80,.80]
    bad['sell']=[.37]*10;bad['rd']=[500,520,470,420,370,330,300,290,280,270]
    bad['milestones']=[80,100,80,0,0,0,0,0,0,0]
    bad['capex']=[520,470,360,220,180,160,150,150,150,150]
    bad['research_sub']=[90,100,80,60,40,30,25,25,25,25]
    bad['nwc_ratio']=.40;bad['tail_decay']=-.05;bad['fund_recovery']=113.156675793
    out['structural']=bad
    good=copy.deepcopy(BASE);good['hbv']=[3400,3650,3850,4000,4100,4150,4150,4100,4050,4000]
    good['gh']=[900,1250,1600,1950,2200,2400,2550,2650,2700,2700]
    good['new']=[0,0,0,200,550,900,1200,1400,1500,1550]
    good['rd']=[550,620,680,740,800,840,880,900,920,940]
    good['milestones']=[100,140,220,250,300,250,220,180,150,150]
    good['capex']=[550,520,450,400,380,360,340,330,330,330];good['tail_decay']=-.01
    out['optimistic']=good
    return out

def checks():
    # Hand-computable one-year P/B/R operation fed to the FORMAL simulator, not separate identity.
    x=copy.deepcopy(BASE)
    for k in ['hbv','gh','other','new','rd','milestones','capex','da','research_sub']:x[k]=[0.]*10
    x.update(initial_cash={'P':5000.,'B':100.,'R':20.},initial_retained={'P':1000.,'B':100.,'R':-100.},bank_rate=0.,**{'yield':0.},payout=0.,b_payout=0.,nwc_ratio=0.,nwc_open=0.)
    x['hbv']=[100.]*10;x['gross']=[.8]*10;x['sell']=[.2]*10;x['admin']=[.1]*10;x['donation']=[0.]*10
    a=simulate(x)['rows'][0]
    # EBIT=50, B EBIT=4.8, P EBIT=45.2, bond coupon=1.533266;
    # tax P=.15*(45.2-1.533266); B=.72; net=41.1967239.
    hand_p=(45.2-1.533266)*.85;hand_b=4.8*.85
    assert abs(a['profit']['P']-hand_p)<1e-8
    assert abs(a['profit']['B']-hand_b)<1e-8
    expected_p=5000+4.334528*38.57+hand_p-80
    assert abs(a['cash_close']['P']-expected_p)<1e-8
    assert abs(a['cash_close']['B']-(100+hand_b+80))<1e-8
    assert legal_profit(-100.,0.,100.,40.)[0]==-60.
    assert legal_profit(-60.,0.,100.,80.)[:2]==(18.,2.)
    # Zero dividend and impossible operating deficit -> explicit financing failure, not fictitious zero cash.
    z=copy.deepcopy(BASE);z['zero_dividend']=True;z['initial_cash']={'P':1.,'B':0.,'R':0.};z['bank_limit']=800.;z['rd']=[3000.]*10
    failed=simulate(z);assert not failed['feasible']
    return {'formal_hand_case':{'parent_profit':hand_p,'sub_profit':hand_b,'parent_cash':expected_p,'pass':True},'loss_carryforward_pass':True,'zero_dividend_financing_failure':failed['failure']}

def main():
    runs={k:simulate(v) for k,v in variants().items()}
    vals={k:{'low':valuation(v,.115),'high':valuation(v,.10)} for k,v in runs.items()}
    sensitivities={}
    for label,change in [('gh_minus20',{'gh_multiplier':.8}),('collection_extra10points',{'nwc_ratio':.44}),('cash_trapped_200',{'shift_parent_to_sub':200.,'old_settlement_years':8,'delay':2}),('all_convert',{'convert':True}),('rd_plus150',{'rd':[v+150 for v in BASE['rd']]}),('capital_overrun20',{'capex':[v*1.2 for v in BASE['capex']]}),('no_new_pipeline',{'new':[0.]*10})]:
        c=copy.deepcopy(BASE);c.update(change);rr=simulate(c);sensitivities[label]={'model':rr,'value':valuation(rr,.1075)}
    # Secondary method: normalised year-5 NOPAT capitalization (9-11x), strip investment
    # income; deduct remaining bank debt + year6 bond payment PV, add only liquid excess
    # released over 3y (not all opening principal), non-liquid asset recovery at year8.
    row=runs['base']['rows'][4];nopat=row['group_ebit']*.85-.15*BASE['research_sub'][4]
    excess=sum(row['cash_close'].values())-row['parent_cash_floor']-50
    aux=[]
    for r,m in [(.115,9),(.10,11)]:
        net=excess/(1+r)**3-row['debt']-1533.266*1.08/(1+.025)+161.65239399/(1+r)**3
        tv=(nopat*m+net)/SHARES
        v=sum(a['dps']/(1+r)**a['year'] for a in runs['base']['rows'][:5])+tv/(1+r)**5
        aux.append({'r':r,'multiple':m,'year5_nopat':nopat,'year5_net_financial':net,'tv5':tv,'value':v})
    convergence={}
    for name,cfg in variants().items():
        extended=copy.deepcopy(cfg);extended['horizon']=350
        extended_run=simulate(extended)
        delta=valuation(extended_run,.10)['value']-vals[name]['high']['value']
        assert abs(delta)<1e-8
        convergence[name]={'extra_Y251_350_pv_per_share':delta,'uncredited_residual_no_capital_return':True}
    result={'tail_convergence':convergence,'unit':'CNY million; shares million; per_share CNY','as_of':'2026-10-26T00:00:00+08:00','inputs':BASE,'runs':runs,'valuations':vals,'auxiliary':aux,'sensitivities':sensitivities,'tests':checks()}
    Path(__file__).with_name('2026-Q3-output.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'values':vals,'auxiliary':aux,'tests':result['tests']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
