#!/usr/bin/env python3
"""688278: CNY million; conditional economic remittance budget, not fabricated subsidiary legal accounts.
P is the PRC listed parent; B is Bosai plus budgeted support to its actual subsidiaries.
R is ONLY an economic R&D cash budget. No jurisdiction, registered capital or statutory reserve is assigned to R.
All forecasts are estimates; real entities and accounting cost evidence are in sources.md.
"""
import json,copy,math,hashlib,gzip,base64
from pathlib import Path
OLD_SOURCE='#!/usr/bin/env python3\n"""特宝生物2026-Q3；stdlib only；CNY million except per-share; no market-price inputs.\nY1-Y5 consecutive forecast years ending approximately Oct 2027-31.\nThree economic/legal cash blocks: listed operating parent P, wholly-owned patent B,\nwholly-owned research R. Opening entity allocations are estimates (see report).\n"""\nimport json, math, copy\nfrom pathlib import Path\nSHARES=(408189480-10821089+4334528)/1e6\nOPEN={\'P\':2005.2855085,\'B\':195.0,\'R\':40.0}\n# 884.43647815 cash equivalents +1355.84903035 liquid financial assets.\nBASE={\n \'hbv\':[3250,3350,3350,3300,3200,3100,3000,2900,2800,2700],\n \'gh\':[800,1050,1300,1500,1650,1800,1930,2050,2150,2220],\n \'other\':[320,350,380,400,420,440,455,465,470,470],\n \'new\':[0,0,0,100,300,450,600,700,750,780],\n \'rd\':[500,540,580,620,650,680,700,710,710,710],\n \'milestones\':[80,100,160,150,120,100,80,60,50,50],\n \'capex\':[520,470,400,330,300,300,300,300,300,300],\n \'da\':[145,165,185,210,235,255,275,290,300,300],\n \'gross\':[.887,.883,.878,.873,.868,.863,.858,.853,.85,.85],\n \'sell\':[.355,.35,.345,.34,.335,.335,.335,.335,.335,.335],\n \'admin\':[.085]*10, \'donation\':[.018]*10,\n \'research_sub\':[90,100,110,120,130,135,140,140,140,140],\n \'nwc_ratio\':.34,\'nwc_open\':1471.73526582,\'tail_decay\':-.02,\n \'bank_limit\':1100.,\'bank_rate\':.035,\'yield\':.012,\n \'payout\':.30,\'b_payout\':.60,\'old_settlement_years\':4,\n \'initial_cash\':OPEN,\'initial_retained\':{\'P\':1950.,\'B\':600.,\'R\':-100.},\n \'delay\':1,\'fund_recovery_year\':8,\'fund_recovery\':161.65239399,\n \'convert\':False, \'zero_dividend\':False,\'revenue_multiplier\':1.,\'gh_multiplier\':1.,\n \'shift_parent_to_sub\':0.,\'reserve_extra\':0.,\n}\n\ndef legal_profit(retained,reserve,capital,profit):\n    """Cumulative losses persist. Statutory 10% only after prior losses recovered;\n    contribution stops at half paid-up capital, never treats capital injection as profit."""\n    taxable_profit=max(0.,profit+min(0.,retained))\n    add=min(max(0.,.5*capital-reserve),.1*taxable_profit)\n    return retained+profit-add,reserve+add,add\n\ndef simulate(cfg):\n    c=copy.deepcopy(cfg); cash=dict(c[\'initial_cash\']);cash[\'P\']-=c[\'shift_parent_to_sub\'];cash[\'B\']+=c[\'shift_parent_to_sub\']\n    retained=dict(c[\'initial_retained\']);reserve={\'P\':205.43661109,\'B\':21.,\'R\':0.}\n    capital={\'P\':408.18948,\'B\':42.,\'R\':700.}\n    debt=39.78476663+711.29327388+17.73298847+26.93038998\n    bond=1533.266; receivable=320.; payable=320.;pending=[]\n    shares=SHARES; issue=4.334528*38.57\n    prev_nwc=c[\'nwc_open\']; earmarked=1400.; rows=[]; failure=None\n    for y in range(1,c.get(\'horizon\',250)+1):\n        i=min(y-1,9); fade=(1+c[\'tail_decay\'])**max(0,y-10)\n        seg={k:c[k][i]*fade*c[\'revenue_multiplier\']*(c[\'gh_multiplier\'] if k==\'gh\' else 1.) for k in (\'hbv\',\'gh\',\'other\',\'new\')}\n        rev=sum(seg.values()); rd=c[\'rd\'][i]*fade; milestone=c[\'milestones\'][i]*fade\n        capex=c[\'capex\'][i]*fade; da=c[\'da\'][i]*fade\n        # Revenue-linked royalty paid to external licensor on new HBV drugs; milestones expensed once.\n        group_ebit=rev*(c[\'gross\'][i]-c[\'sell\'][i]-c[\'admin\'][i]-c[\'donation\'][i])-rd-milestone-.08*seg[\'new\']\n        research=c[\'research_sub\'][i]*fade\n        internal_rate=.06 if y==1 else (.045 if y==2 else .03)\n        b_rev=(seg[\'hbv\']+seg[\'gh\'])*internal_rate\n        b_ebit=.8*b_rev\n        p_ebit=group_ebit-b_ebit+research\n        r_ebit=-research\n        nwc=rev*c[\'nwc_ratio\']; delta_nwc=nwc-prev_nwc;prev_nwc=nwc\n        retained_open=dict(retained)\n        begin=dict(cash);begin_debt=debt; external_issue=issue if y==1 else 0.\n        cash[\'P\']+=external_issue\n        if y==1:capital[\'P\']+=4.334528\n        interest={k:max(0.,begin[k])*c[\'yield\'] for k in cash}\n        bank_interest=debt*c[\'bank_rate\']\n        bond_coupon=(bond*[.001,.003,.006,.01,.015][y-1]) if y<=5 else 0.\n        conversion=0.\n        if c[\'convert\'] and y==1:\n            conversion=bond/58.56;shares+=conversion;bond=0.;bond_coupon=0.\n        # Year 6 redemption 108% includes final coupon; only 8% premium affects P&L,\n        # principal does not; coupon not separately charged in year 6.\n        redemption=bond*1.08 if y==6 else 0.\n        premium=bond*.08 if y==6 else 0.\n        pretax={\'P\':p_ebit+interest[\'P\']-bank_interest-bond_coupon-premium,\'B\':b_ebit+interest[\'B\'],\'R\':r_ebit+interest[\'R\']}\n        tax={k:max(0.,pretax[k])*(.15 if k!=\'R\' else .25) for k in cash}\n        profit={k:pretax[k]-tax[k] for k in cash}\n        cf={\'P\':profit[\'P\']+.9*da-.9*capex-delta_nwc+premium,\n            \'B\':profit[\'B\']+.05*da-.05*capex,\n            \'R\':profit[\'R\']+.05*da-.05*capex}\n        for k in cash:cash[k]+=cf[k]\n        repayment=min(debt,150.) if 2<=y<=7 else 0.\n        cash[\'P\']-=repayment+redemption\n        debt-=repayment\n        if redemption:bond=0.\n        other_obligation=31.49177387 if y==2 else 0.;cash[\'P\']-=other_obligation\n        fund_recovery=c[\'fund_recovery\'] if y==c[\'fund_recovery_year\'] else 0.\n        cash[\'P\']+=fund_recovery\n        # Recovery is asset principal, not new profit; only losses/profits beyond book enter earnings.\n        if fund_recovery:\n            profit[\'P\']+=fund_recovery-161.65239399\n        settlement=min(receivable,320./c[\'old_settlement_years\'])\n        cash[\'P\']-=settlement;cash[\'B\']+=settlement;receivable-=settlement;payable-=settlement\n        upstream=sum(v for due,v in pending if due==y)\n        cash[\'B\']-=upstream;cash[\'P\']+=upstream\n        pending=[(d,v) for d,v in pending if d>y]\n        # Parent tops up research cash, capital increase not P&L and not R retained profit.\n        r_floor=20.*fade\n        support=max(0.,r_floor-cash[\'R\']);cash[\'P\']-=support;cash[\'R\']+=support;capital[\'R\']+=support\n        earmarked=max(0.,earmarked-min(earmarked,.65*capex+.2*rd))\n        floor_runoff=(1+c[\'tail_decay\'])**max(0,y-20)\n        p_floor=max(250.*floor_runoff,.10*rev)+earmarked+c[\'reserve_extra\']*floor_runoff;b_floor=30.*fade\n        # finite bridge financing only for necessary operations, never dividend.\n        draw=max(0.,p_floor-cash[\'P\']); permitted=max(0.,c[\'bank_limit\']-debt)\n        if draw>permitted+1e-7:\n            failure={\'year\':y,\'required_draw\':draw,\'available_draw\':permitted,\'cash_before_draw\':cash[\'P\']};break\n        cash[\'P\']+=draw;debt+=draw\n        # Conservative new debt accrues half-year interest immediately, with no assumed tax shield.\n        new_interest=draw*c[\'bank_rate\']*.5;cash[\'P\']-=new_interest;profit[\'P\']-=new_interest\n        if cash[\'P\']<0:failure={\'year\':y,\'reason\':\'negative parent cash after interest\'};break\n        adds={}\n        for k in cash:retained[k],reserve[k],adds[k]=legal_profit(retained[k],reserve[k],capital[k],profit[k])\n        # Declare only funded amounts. Pay with one-year lag; reserve the declared cash at B.\n        reserved=sum(v for _,v in pending)\n        target_b=c[\'b_payout\']*max(0.,profit[\'B\'])\n        if 5<y<=20:target_b+=.25*max(0.,cash[\'B\']-b_floor-reserved)\n        if y>=25:target_b=max(0.,cash[\'B\']-b_floor-reserved)\n        bdiv=min(max(0.,retained[\'B\']),max(0.,cash[\'B\']-b_floor-reserved),target_b)\n        retained[\'B\']-=bdiv\n        # New declarations enter P\'s earnings, not twice on receipt.\n        retained[\'P\'],reserve[\'P\'],padd=legal_profit(retained[\'P\'],reserve[\'P\'],capital[\'P\'],bdiv);adds[\'P\']+=padd\n        pending.append((y+c[\'delay\'],bdiv))\n        group_profit=sum(profit.values())\n        target_p=c[\'payout\']*max(0.,group_profit) if y<=5 else .7*max(0.,group_profit)+.25*max(0.,cash[\'P\']-p_floor)\n        if 20<y<23:target_p=.7*max(0.,group_profit)\n        if y>=23:target_p=max(0.,cash[\'P\']-p_floor)\n        if c[\'zero_dividend\']:target_p=0.\n        pdiv=min(target_p,max(0.,cash[\'P\']-p_floor),max(0.,retained[\'P\']))\n        cash[\'P\']-=pdiv;retained[\'P\']-=pdiv\n        assert abs(retained[\'P\']-(retained_open[\'P\']+profit[\'P\']+bdiv-adds[\'P\']-pdiv))<1e-6\n        assert abs(retained[\'B\']-(retained_open[\'B\']+profit[\'B\']-adds[\'B\']-bdiv))<1e-6\n        assert abs(retained[\'R\']-(retained_open[\'R\']+profit[\'R\']-adds[\'R\']))<1e-6\n        # Independent external cash identity eliminates all internal settlement/support/dividend flows.\n        expected=sum(begin.values())+sum(cf.values())+external_issue+draw-repayment-redemption-other_obligation+fund_recovery-pdiv-new_interest\n        error=sum(cash.values())-expected\n        assert abs(error)<1e-6,(y,error)\n        assert min(cash.values())>=-1e-7\n        assert abs(payable-receivable)<1e-9\n        assert cash[\'B\']+1e-7>=sum(v for _,v in pending)\n        # recurring sustainable FCFE excludes financing income, debt flows, asset recovery.\n        sustainable=sum(v-max(0.,v)*(.25 if k==\'R\' else .15) for k,v in {\'P\':p_ebit,\'B\':b_ebit,\'R\':r_ebit}.items())+da-capex-delta_nwc\n        rows.append({\'year\':y,\'segments\':seg,\'revenue\':rev,\'group_ebit\':group_ebit,\'rd\':rd,\'milestones\':milestone,\'capex\':capex,\'da\':da,\'nwc\':nwc,\'delta_nwc\':delta_nwc,\'profit\':profit,\'group_profit\':group_profit,\'operating_capital_cash\':cf,\'cash_open\':begin,\'cash_close\':dict(cash),\'retained\':dict(retained),\'reserve\':dict(reserve),\'statutory_add\':adds,\'debt\':debt,\'bond_face\':bond,\'bank_interest\':bank_interest+new_interest,\'bond_coupon\':bond_coupon,\'bond_redemption\':redemption,\'borrow\':draw,\'repay\':repayment,\'research_support\':support,\'internal_old_settlement\':settlement,\'internal_old_remaining\':receivable,\'sub_declared\':bdiv,\'sub_received\':upstream,\'sub_dividend_receivable\':sum(v for _,v in pending),\'common_dividend\':pdiv,\'dps\':pdiv/shares,\'shares\':shares,\'equity_issue_cash\':external_issue,\'fund_recovery\':fund_recovery,\'earmarked_cash\':earmarked,\'parent_cash_floor\':p_floor,\'sustainable_fcfe\':sustainable,\'cash_conservation_error\':error,\'paid_capital\':dict(capital),\'pending_dividends\':list(pending),\'research_accumulated_loss\':min(0.,retained[\'R\'])})\n    return {\'feasible\':failure is None,\'failure\':failure,\'rows\':rows,\'shares\':shares,\'tail_decay\':c[\'tail_decay\'],\'fund_recovery_year\':c[\'fund_recovery_year\']}\n\ndef valuation(run,r,g=None):\n    if not run[\'feasible\']:return {\'feasible\':False,\'value\':None,\'failure\':run[\'failure\']}\n    rows=run[\'rows\'];g=run[\'tail_decay\'] if g is None else g\n    # Actual legal dividends only, including 230 post-Y20 years. No FCFE terminal plus\n    # separately capitalised financial principal; all cash earns, pays, or remains trapped.\n    value=sum(x[\'dps\']/(1+r)**x[\'year\'] for x in rows)\n    tv5=sum(x[\'dps\']/(1+r)**(x[\'year\']-5) for x in rows if x[\'year\']>5)\n    tail=sum(x[\'common_dividend\']/(1+r)**(x[\'year\']-20) for x in rows if x[\'year\']>20)\n    d5=sum(x[\'dps\']/(1+r)**x[\'year\'] for x in rows[:5])\n    assert abs(value-d5-tv5/(1+r)**5)<1e-8\n    last=rows[-1]\n    return {\'feasible\':True,\'discount_rate\':r,\'g\':g,\'value\':value,\'tv5\':tv5,\'dps\':[x[\'dps\'] for x in rows[:5]],\'tv5_pv_fraction\':tv5/(1+r)**5/value,\'tail20_pv_fraction\':tail/run[\'shares\']/(1+r)**20/value,\'terminal20_total\':tail,\'tail_method\':\'actual legal distributions Y21-Y250; no residual capital repayment credited\',\'year250_uncredited_cash\':last[\'cash_close\'],\'year250_retained\':last[\'retained\'],\'year250_pending\':last[\'pending_dividends\'],\'year250_cash_pv_per_share\':sum(last[\'cash_close\'].values())/run[\'shares\']/(1+r)**250}\n\ndef variants():\n    out={\'base\':copy.deepcopy(BASE)}\n    cyc=copy.deepcopy(BASE)\n    for k in [\'hbv\',\'gh\',\'other\']:\n        cyc[k]=[v*m for v,m in zip(cyc[k],[.85,.9,.95,1,1,1,1,1,1,1])]\n    cyc[\'nwc_ratio\']=.39;cyc[\'capex\']=[520,450,420,330,300,300,300,300,300,300];out[\'cyclical\']=cyc\n    bad=copy.deepcopy(BASE)\n    bad[\'hbv\']=[3000,2700,2400,2100,1850,1650,1500,1370,1250,1150]\n    bad[\'gh\']=[650,780,850,900,920,930,930,920,900,880];bad[\'new\']=[0]*10\n    bad[\'gross\']=[.87,.85,.83,.81,.80,.80,.80,.80,.80,.80]\n    bad[\'sell\']=[.37]*10;bad[\'rd\']=[500,520,470,420,370,330,300,290,280,270]\n    bad[\'milestones\']=[80,100,80,0,0,0,0,0,0,0]\n    bad[\'capex\']=[520,470,360,220,180,160,150,150,150,150]\n    bad[\'research_sub\']=[90,100,80,60,40,30,25,25,25,25]\n    bad[\'nwc_ratio\']=.40;bad[\'tail_decay\']=-.05;bad[\'fund_recovery\']=113.156675793\n    out[\'structural\']=bad\n    good=copy.deepcopy(BASE);good[\'hbv\']=[3400,3650,3850,4000,4100,4150,4150,4100,4050,4000]\n    good[\'gh\']=[900,1250,1600,1950,2200,2400,2550,2650,2700,2700]\n    good[\'new\']=[0,0,0,200,550,900,1200,1400,1500,1550]\n    good[\'rd\']=[550,620,680,740,800,840,880,900,920,940]\n    good[\'milestones\']=[100,140,220,250,300,250,220,180,150,150]\n    good[\'capex\']=[550,520,450,400,380,360,340,330,330,330];good[\'tail_decay\']=-.01\n    out[\'optimistic\']=good\n    return out\n\ndef checks():\n    # Hand-computable one-year P/B/R operation fed to the FORMAL simulator, not separate identity.\n    x=copy.deepcopy(BASE)\n    for k in [\'hbv\',\'gh\',\'other\',\'new\',\'rd\',\'milestones\',\'capex\',\'da\',\'research_sub\']:x[k]=[0.]*10\n    x.update(initial_cash={\'P\':5000.,\'B\':100.,\'R\':20.},initial_retained={\'P\':1000.,\'B\':100.,\'R\':-100.},bank_rate=0.,**{\'yield\':0.},payout=0.,b_payout=0.,nwc_ratio=0.,nwc_open=0.)\n    x[\'hbv\']=[100.]*10;x[\'gross\']=[.8]*10;x[\'sell\']=[.2]*10;x[\'admin\']=[.1]*10;x[\'donation\']=[0.]*10\n    a=simulate(x)[\'rows\'][0]\n    # EBIT=50, B EBIT=4.8, P EBIT=45.2, bond coupon=1.533266;\n    # tax P=.15*(45.2-1.533266); B=.72; net=41.1967239.\n    hand_p=(45.2-1.533266)*.85;hand_b=4.8*.85\n    assert abs(a[\'profit\'][\'P\']-hand_p)<1e-8\n    assert abs(a[\'profit\'][\'B\']-hand_b)<1e-8\n    expected_p=5000+4.334528*38.57+hand_p-80\n    assert abs(a[\'cash_close\'][\'P\']-expected_p)<1e-8\n    assert abs(a[\'cash_close\'][\'B\']-(100+hand_b+80))<1e-8\n    assert legal_profit(-100.,0.,100.,40.)[0]==-60.\n    assert legal_profit(-60.,0.,100.,80.)[:2]==(18.,2.)\n    # Zero dividend and impossible operating deficit -> explicit financing failure, not fictitious zero cash.\n    z=copy.deepcopy(BASE);z[\'zero_dividend\']=True;z[\'initial_cash\']={\'P\':1.,\'B\':0.,\'R\':0.};z[\'bank_limit\']=800.;z[\'rd\']=[3000.]*10\n    failed=simulate(z);assert not failed[\'feasible\']\n    return {\'formal_hand_case\':{\'parent_profit\':hand_p,\'sub_profit\':hand_b,\'parent_cash\':expected_p,\'pass\':True},\'loss_carryforward_pass\':True,\'zero_dividend_financing_failure\':failed[\'failure\']}\n\ndef main():\n    runs={k:simulate(v) for k,v in variants().items()}\n    vals={k:{\'low\':valuation(v,.115),\'high\':valuation(v,.10)} for k,v in runs.items()}\n    sensitivities={}\n    for label,change in [(\'gh_minus20\',{\'gh_multiplier\':.8}),(\'collection_extra10points\',{\'nwc_ratio\':.44}),(\'cash_trapped_200\',{\'shift_parent_to_sub\':200.,\'old_settlement_years\':8,\'delay\':2}),(\'all_convert\',{\'convert\':True}),(\'rd_plus150\',{\'rd\':[v+150 for v in BASE[\'rd\']]}),(\'capital_overrun20\',{\'capex\':[v*1.2 for v in BASE[\'capex\']]}),(\'no_new_pipeline\',{\'new\':[0.]*10})]:\n        c=copy.deepcopy(BASE);c.update(change);rr=simulate(c);sensitivities[label]={\'model\':rr,\'value\':valuation(rr,.1075)}\n    # Secondary method: normalised year-5 NOPAT capitalization (9-11x), strip investment\n    # income; deduct remaining bank debt + year6 bond payment PV, add only liquid excess\n    # released over 3y (not all opening principal), non-liquid asset recovery at year8.\n    row=runs[\'base\'][\'rows\'][4];nopat=row[\'group_ebit\']*.85-.15*BASE[\'research_sub\'][4]\n    excess=sum(row[\'cash_close\'].values())-row[\'parent_cash_floor\']-50\n    aux=[]\n    for r,m in [(.115,9),(.10,11)]:\n        net=excess/(1+r)**3-row[\'debt\']-1533.266*1.08/(1+.025)+161.65239399/(1+r)**3\n        tv=(nopat*m+net)/SHARES\n        v=sum(a[\'dps\']/(1+r)**a[\'year\'] for a in runs[\'base\'][\'rows\'][:5])+tv/(1+r)**5\n        aux.append({\'r\':r,\'multiple\':m,\'year5_nopat\':nopat,\'year5_net_financial\':net,\'tv5\':tv,\'value\':v})\n    convergence={}\n    for name,cfg in variants().items():\n        extended=copy.deepcopy(cfg);extended[\'horizon\']=350\n        extended_run=simulate(extended)\n        delta=valuation(extended_run,.10)[\'value\']-vals[name][\'high\'][\'value\']\n        assert abs(delta)<1e-8\n        convergence[name]={\'extra_Y251_350_pv_per_share\':delta,\'uncredited_residual_no_capital_return\':True}\n    result={\'tail_convergence\':convergence,\'unit\':\'CNY million; shares million; per_share CNY\',\'as_of\':\'2026-10-26T00:00:00+08:00\',\'inputs\':BASE,\'runs\':runs,\'valuations\':vals,\'auxiliary\':aux,\'sensitivities\':sensitivities,\'tests\':checks()}\n    Path(__file__).with_name(\'2026-Q3-output.json\').write_text(json.dumps(result,ensure_ascii=False,indent=2)+\'\\n\')\n    print(json.dumps({\'values\':vals,\'auxiliary\':aux,\'tests\':result[\'tests\']},ensure_ascii=False,indent=2))\nif __name__==\'__main__\':main()\n'
OLD={"__name__":"frozen_old"};exec(OLD_SOURCE,OLD)
BASE={'hbv': [3250, 3350, 3350, 3300, 3200, 3100, 3000, 2900, 2800, 2700], 'gh': [800, 1050, 1300, 1500, 1650, 1800, 1930, 2050, 2150, 2220], 'other': [320, 350, 380, 400, 420, 440, 455, 465, 470, 470], 'new': [0, 0, 0, 100, 300, 450, 600, 700, 750, 780], 'rd': [500, 540, 580, 620, 650, 680, 700, 710, 710, 710], 'milestones': [80, 100, 160, 150, 120, 100, 80, 60, 50, 50], 'capex': [520, 470, 400, 330, 300, 300, 300, 300, 300, 300], 'da': [145, 165, 185, 210, 235, 255, 275, 290, 300, 300], 'gross': [0.887, 0.883, 0.878, 0.873, 0.868, 0.863, 0.858, 0.853, 0.85, 0.85], 'sell': [0.355, 0.35, 0.345, 0.34, 0.335, 0.335, 0.335, 0.335, 0.335, 0.335], 'admin': [0.085, 0.085, 0.085, 0.085, 0.085, 0.085, 0.085, 0.085, 0.085, 0.085], 'donation': [0.018, 0.018, 0.018, 0.018, 0.018, 0.018, 0.018, 0.018, 0.018, 0.018], 'research_sub': [90, 100, 110, 120, 130, 135, 140, 140, 140, 140], 'nwc_ratio': 0.34, 'nwc_open': 1471.73526582, 'tail_decay': -0.02, 'bank_limit': 1100.0, 'bank_rate': 0.035, 'yield': 0.012, 'payout': 0.3, 'b_payout': 0.6, 'old_settlement_years': 4, 'initial_cash': {'P': 2005.2855085, 'B': 195.0, 'R': 40.0}, 'initial_retained': {'P': 1950.0, 'B': 600.0, 'R': -100.0}, 'delay': 1, 'fund_recovery_year': 8, 'fund_recovery': 161.65239399, 'convert': False, 'zero_dividend': False, 'revenue_multiplier': 1.0, 'gh_multiplier': 1.0, 'shift_parent_to_sub': 0.0, 'reserve_extra': 0.0}
VARIANTS={'base': {'hbv': [3250, 3350, 3350, 3300, 3200, 3100, 3000, 2900, 2800, 2700], 'gh': [800, 1050, 1300, 1500, 1650, 1800, 1930, 2050, 2150, 2220], 'other': [320, 350, 380, 400, 420, 440, 455, 465, 470, 470], 'new': [0, 0, 0, 100, 300, 450, 600, 700, 750, 780], 'rd': [500, 540, 580, 620, 650, 680, 700, 710, 710, 710], 'milestones': [80, 100, 160, 150, 120, 100, 80, 60, 50, 50], 'capex': [520, 470, 400, 330, 300, 300, 300, 300, 300, 300], 'da': [145, 165, 185, 210, 235, 255, 275, 290, 300, 300], 'gross': [0.887, 0.883, 0.878, 0.873, 0.868, 0.863, 0.858, 0.853, 0.85, 0.85], 'sell': [0.355, 0.35, 0.345, 0.34, 0.335, 0.335, 0.335, 0.335, 0.335, 0.335], 'admin': [0.085, 0.085, 0.085, 0.085, 0.085, 0.085, 0.085, 0.085, 0.085, 0.085], 'donation': [0.018, 0.018, 0.018, 0.018, 0.018, 0.018, 0.018, 0.018, 0.018, 0.018], 'research_sub': [90, 100, 110, 120, 130, 135, 140, 140, 140, 140], 'nwc_ratio': 0.34, 'nwc_open': 1471.73526582, 'tail_decay': -0.02, 'bank_limit': 1100.0, 'bank_rate': 0.035, 'yield': 0.012, 'payout': 0.3, 'b_payout': 0.6, 'old_settlement_years': 4, 'initial_cash': {'P': 2005.2855085, 'B': 195.0, 'R': 40.0}, 'initial_retained': {'P': 1950.0, 'B': 600.0, 'R': -100.0}, 'delay': 1, 'fund_recovery_year': 8, 'fund_recovery': 161.65239399, 'convert': False, 'zero_dividend': False, 'revenue_multiplier': 1.0, 'gh_multiplier': 1.0, 'shift_parent_to_sub': 0.0, 'reserve_extra': 0.0}, 'cyclical': {'hbv': [2762.5, 3015.0, 3182.5, 3300, 3200, 3100, 3000, 2900, 2800, 2700], 'gh': [680.0, 945.0, 1235.0, 1500, 1650, 1800, 1930, 2050, 2150, 2220], 'other': [272.0, 315.0, 361.0, 400, 420, 440, 455, 465, 470, 470], 'new': [0, 0, 0, 100, 300, 450, 600, 700, 750, 780], 'rd': [500, 540, 580, 620, 650, 680, 700, 710, 710, 710], 'milestones': [80, 100, 160, 150, 120, 100, 80, 60, 50, 50], 'capex': [520, 450, 420, 330, 300, 300, 300, 300, 300, 300], 'da': [145, 165, 185, 210, 235, 255, 275, 290, 300, 300], 'gross': [0.887, 0.883, 0.878, 0.873, 0.868, 0.863, 0.858, 0.853, 0.85, 0.85], 'sell': [0.355, 0.35, 0.345, 0.34, 0.335, 0.335, 0.335, 0.335, 0.335, 0.335], 'admin': [0.085, 0.085, 0.085, 0.085, 0.085, 0.085, 0.085, 0.085, 0.085, 0.085], 'donation': [0.018, 0.018, 0.018, 0.018, 0.018, 0.018, 0.018, 0.018, 0.018, 0.018], 'research_sub': [90, 100, 110, 120, 130, 135, 140, 140, 140, 140], 'nwc_ratio': 0.39, 'nwc_open': 1471.73526582, 'tail_decay': -0.02, 'bank_limit': 1100.0, 'bank_rate': 0.035, 'yield': 0.012, 'payout': 0.3, 'b_payout': 0.6, 'old_settlement_years': 4, 'initial_cash': {'P': 2005.2855085, 'B': 195.0, 'R': 40.0}, 'initial_retained': {'P': 1950.0, 'B': 600.0, 'R': -100.0}, 'delay': 1, 'fund_recovery_year': 8, 'fund_recovery': 161.65239399, 'convert': False, 'zero_dividend': False, 'revenue_multiplier': 1.0, 'gh_multiplier': 1.0, 'shift_parent_to_sub': 0.0, 'reserve_extra': 0.0}, 'structural': {'hbv': [3000, 2700, 2400, 2100, 1850, 1650, 1500, 1370, 1250, 1150], 'gh': [650, 780, 850, 900, 920, 930, 930, 920, 900, 880], 'other': [320, 350, 380, 400, 420, 440, 455, 465, 470, 470], 'new': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0], 'rd': [500, 520, 470, 420, 370, 330, 300, 290, 280, 270], 'milestones': [80, 100, 80, 0, 0, 0, 0, 0, 0, 0], 'capex': [520, 470, 360, 220, 180, 160, 150, 150, 150, 150], 'da': [145, 165, 185, 210, 235, 255, 275, 290, 300, 300], 'gross': [0.87, 0.85, 0.83, 0.81, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8], 'sell': [0.37, 0.37, 0.37, 0.37, 0.37, 0.37, 0.37, 0.37, 0.37, 0.37], 'admin': [0.085, 0.085, 0.085, 0.085, 0.085, 0.085, 0.085, 0.085, 0.085, 0.085], 'donation': [0.018, 0.018, 0.018, 0.018, 0.018, 0.018, 0.018, 0.018, 0.018, 0.018], 'research_sub': [90, 100, 80, 60, 40, 30, 25, 25, 25, 25], 'nwc_ratio': 0.4, 'nwc_open': 1471.73526582, 'tail_decay': -0.05, 'bank_limit': 1100.0, 'bank_rate': 0.035, 'yield': 0.012, 'payout': 0.3, 'b_payout': 0.6, 'old_settlement_years': 4, 'initial_cash': {'P': 2005.2855085, 'B': 195.0, 'R': 40.0}, 'initial_retained': {'P': 1950.0, 'B': 600.0, 'R': -100.0}, 'delay': 1, 'fund_recovery_year': 8, 'fund_recovery': 113.156675793, 'convert': False, 'zero_dividend': False, 'revenue_multiplier': 1.0, 'gh_multiplier': 1.0, 'shift_parent_to_sub': 0.0, 'reserve_extra': 0.0}, 'optimistic': {'hbv': [3400, 3650, 3850, 4000, 4100, 4150, 4150, 4100, 4050, 4000], 'gh': [900, 1250, 1600, 1950, 2200, 2400, 2550, 2650, 2700, 2700], 'other': [320, 350, 380, 400, 420, 440, 455, 465, 470, 470], 'new': [0, 0, 0, 200, 550, 900, 1200, 1400, 1500, 1550], 'rd': [550, 620, 680, 740, 800, 840, 880, 900, 920, 940], 'milestones': [100, 140, 220, 250, 300, 250, 220, 180, 150, 150], 'capex': [550, 520, 450, 400, 380, 360, 340, 330, 330, 330], 'da': [145, 165, 185, 210, 235, 255, 275, 290, 300, 300], 'gross': [0.887, 0.883, 0.878, 0.873, 0.868, 0.863, 0.858, 0.853, 0.85, 0.85], 'sell': [0.355, 0.35, 0.345, 0.34, 0.335, 0.335, 0.335, 0.335, 0.335, 0.335], 'admin': [0.085, 0.085, 0.085, 0.085, 0.085, 0.085, 0.085, 0.085, 0.085, 0.085], 'donation': [0.018, 0.018, 0.018, 0.018, 0.018, 0.018, 0.018, 0.018, 0.018, 0.018], 'research_sub': [90, 100, 110, 120, 130, 135, 140, 140, 140, 140], 'nwc_ratio': 0.34, 'nwc_open': 1471.73526582, 'tail_decay': -0.01, 'bank_limit': 1100.0, 'bank_rate': 0.035, 'yield': 0.012, 'payout': 0.3, 'b_payout': 0.6, 'old_settlement_years': 4, 'initial_cash': {'P': 2005.2855085, 'B': 195.0, 'R': 40.0}, 'initial_retained': {'P': 1950.0, 'B': 600.0, 'R': -100.0}, 'delay': 1, 'fund_recovery_year': 8, 'fund_recovery': 161.65239399, 'convert': False, 'zero_dividend': False, 'revenue_multiplier': 1.0, 'gh_multiplier': 1.0, 'shift_parent_to_sub': 0.0, 'reserve_extra': 0.0}}
SHARES=(408189480-10821089+4334528)/1e6

def legal_profit(retained,reserve,registered,profit,paid=None):
    # paid is deliberately irrelevant to the 50% threshold. No cash generated by registration.
    add=min(max(0.,registered*.5-reserve),.1*max(0.,profit+min(0.,retained)))
    return retained+profit-add,reserve+add,add

def liquidation(cash,gross_noncash,recovery,external_debt,parent_loan,ownership,cost,new_cost=0,fees=0,tax_rate=.25):
    # Gross assets are impaired BEFORE debt settlement. Parent loan precedes equity, not haircut.
    gross=cash+gross_noncash*recovery
    fees_paid=min(max(0.,gross),fees); fees_shortfall=fees-fees_paid
    external_paid=min(external_debt,max(0.,gross-fees_paid)); remain=max(0.,gross-fees_paid-external_paid)
    feasible=fees_shortfall<1e-8 and external_debt-external_paid<1e-8
    parent_paid=min(parent_loan,remain); remain-=parent_paid
    equity=remain*ownership; basis=cost+new_cost
    gain=equity-basis; tax=max(0.,gain)*tax_rate # no immediate cash refund for a loss
    return dict(gross_realized=gross,fees=fees,external_paid=external_paid,
                external_shortfall=external_debt-external_paid,parent_loan_paid=parent_paid,
                parent_loan_loss=parent_loan-parent_paid,minority_equity=remain*(1-ownership),
                parent_equity=equity,investment_basis=basis,investment_gain=gain,tax=tax,
                parent_cash=parent_paid+equity-tax,shares_cancelled_fraction=1. if feasible else 0.,
                feasible=feasible,fees_paid=fees_paid,fees_shortfall=fees_shortfall)

def reduce_capital(cash,registered,shares,holder_units,amount,min_registered):
    paid=min(max(0.,cash),max(0.,registered-min_registered),max(0.,amount))
    fraction=paid/registered if registered else 0
    return dict(cash=cash-paid,registered=registered-paid,shares=shares*(1-fraction),
                holder_units=holder_units*(1-fraction),cash_paid=paid,
                cancellation_fraction=fraction,profit_recognized=0.)

def simulate(cfg,method_only=False):
    c=copy.deepcopy(cfg); horizon=c.get('horizon',250)
    cash=dict(c['initial_cash']);cash['P']-=c['shift_parent_to_sub'];cash['B']+=c['shift_parent_to_sub']
    # These are capacity BUDGETS, not claimed Q3 legal retained balances for subsidiary groups.
    capacity={'P':c['initial_retained']['P'],'B':c.get('b_capacity',c['initial_retained']['B'] if method_only else 500.)}
    reserve={'P':204.09474000,'B':c.get('b_reserve',0.)}
    registered={'P':408.18948,'B':42.}
    debt=795.74141896;bond=1533.266;pending=[];receivable=320.
    economic_shares=SHARES; holder_units=1.; legal_shares=SHARES
    equity_basis={'P_to_B':47.56511718,'P_to_Hangzhou':62.33956437,'B_to_Skyline':155.30765844}
    total_new={k:0. for k in equity_basis};total_consumed={k:0. for k in equity_basis}
    prev_nwc=c['nwc_open']; earmarked=1400.;rows=[];failure=None
    fixed=817.81733761+219.41470488+314.66550899+45.04624653
    alloc=c.get('research_via_b',.75) # 50%-100% tested, anchored Shanghai actual loss; not a legal ratio.
    exit_year=c.get('exit_year'); impairment=c.get('recognize_research_cost',True)
    for y in range(1,horizon+1):
        i=min(y-1,9);fade=(1+c['tail_decay'])**max(0,y-10)
        seg={k:c[k][i]*fade*c['revenue_multiplier']*(c['gh_multiplier'] if k=='gh' else 1.) for k in ('hbv','gh','other','new')}
        rev=sum(seg.values()); rd=c['rd'][i]*fade; milestone=c['milestones'][i]*fade
        capex=c['capex'][i]*fade;da=c['da'][i]*fade
        planned_da=da
        retired=min(fixed,max(0.,-c['tail_decay'])*fixed) if y>10 and c.get('retire_idle_assets',False) else 0.
        salvage=retired*c.get('asset_salvage',.35)
        da=min(da,max(0.,fixed+capex-retired)) if c.get('retire_idle_assets',False) else da
        group_ebit=rev*(c['gross'][i]-c['sell'][i]-c['admin'][i]-c['donation'][i])-rd-milestone-.08*seg['new']+planned_da-da
        research=c['research_sub'][i]*fade
        b_ebit=(seg['hbv']+seg['gh'])*(.06 if y==1 else .045 if y==2 else .03)*.8
        p_ebit=group_ebit-b_ebit+research
        nwc=rev*c['nwc_ratio'];dnwc=nwc-prev_nwc;prev_nwc=nwc
        begin=dict(cash); opening_capacity=dict(capacity);opening_debt=debt
        issue=4.334528*38.57 if y==1 else 0.;cash['P']+=issue
        if y==1:registered['P']+=4.334528
        converted=0.
        if c['convert'] and y==1:
            converted=bond/58.56;economic_shares+=converted;legal_shares+=converted;registered['P']+=converted;bond=0.
        interest={k:max(0.,begin[k])*c['yield'] for k in cash}
        bi=debt*c['bank_rate'];coupon=bond*[.001,.003,.006,.01,.015][y-1] if y<=5 else 0.
        redemption=bond*1.08 if y==6 else 0.;premium=bond*.08 if y==6 else 0.
        pre={'P':p_ebit+interest['P']-bi-coupon-premium,'B':b_ebit+interest['B'],'R':-research+interest['R']}
        tax={k:max(0.,pre[k])*(.25 if k=='R' else .15) for k in cash}
        profit={k:pre[k]-tax[k] for k in cash}
        # Disposal loss has no immediate tax refund; operating tax computed before loss.
        for k,weight in [('P',.9),('B',.05),('R',.05)]:profit[k]-=weight*(retired-salvage)
        cf={'P':profit['P']+.9*(da-capex)-dnwc+premium,'B':profit['B']+.05*(da-capex),'R':profit['R']+.05*(da-capex)}
        for k,weight in [('P',.9),('B',.05),('R',.05)]:cf[k]+=weight*retired
        for k in cash:cash[k]+=cf[k]
        fixed=max(0.,fixed+capex-da-retired) # active operating assets, not extra financial principal
        repayment=min(debt,150.) if 2<=y<=7 else 0.;debt-=repayment
        cash['P']-=repayment+redemption
        if redemption:bond=0.
        obligation=31.49177387 if y==2 else 0.;cash['B']-=obligation # Skyline contingent payment is in Bosai chain
        fund=c['fund_recovery'] if y==c['fund_recovery_year'] else 0.;cash['P']+=fund
        fund_gain=fund-161.65239399 if fund else 0.
        settle=min(receivable,320./c['old_settlement_years']);receivable-=settle
        cash['P']-=settle;cash['B']+=settle
        received=sum(v for due,v in pending if due==y);cash['B']-=received;cash['P']+=received
        pending=[(d,v) for d,v in pending if d>y]
        r_floor=20.*fade;support=max(0.,r_floor-cash['R'])
        cash['R']+=support;cash['B']-=support*alloc;cash['P']-=support*(1-alloc)
        total_new['B_to_Skyline']+=support*alloc;total_new['P_to_Hangzhou']+=support*(1-alloc)
        # Research consumption, not a second cash deduction or an immediate tax credit.
        consumed=max(0.,-profit['R'])
        total_consumed['B_to_Skyline']+=consumed*alloc;total_consumed['P_to_Hangzhou']+=consumed*(1-alloc)
        b_floor=30.*fade
        reserved=sum(v for _,v in pending)
        b_topup=max(0.,b_floor+reserved-cash['B']);cash['P']-=b_topup;cash['B']+=b_topup
        total_new['P_to_B']+=b_topup
        earmarked=max(0.,earmarked-min(earmarked,.65*capex+.2*rd))
        floor_runoff=(1+c['tail_decay'])**max(0,y-20)
        p_floor=max(250.*floor_runoff,.10*rev)+earmarked+c['reserve_extra']*floor_runoff
        draw=max(0.,p_floor-cash['P']);allowed=max(0.,c['bank_limit']-debt)
        if draw>allowed+1e-7:
            failure={'year':y,'required_draw':draw,'available_draw':allowed,'cash_before_draw':cash['P']};break
        cash['P']+=draw;debt+=draw;extra_interest=draw*c['bank_rate']*.5
        cash['P']-=extra_interest;profit['P']-=extra_interest
        if cash['P']<0:failure={'year':y,'reason':'negative cash after funded interest'};break
        # Economic payout budget charges downstream R&D consumption. No asserted offshore PRC reserves.
        p_charge=((1-alloc)*consumed+b_topup) if impairment else 0.
        b_charge=alloc*consumed if impairment else 0.
        capacity['B'],reserve['B'],badd=legal_profit(capacity['B'],reserve['B'],registered['B'],profit['B']-b_charge)
        target_b=c['b_payout']*max(0.,profit['B']-b_charge)
        if 5<y<=20:target_b+=.25*max(0.,cash['B']-b_floor-reserved)
        if y>=c.get('b_release_year',25):target_b=max(0.,cash['B']-b_floor-reserved)
        declared=min(max(0.,capacity['B']),max(0.,cash['B']-b_floor-reserved),target_b)
        capacity['B']-=declared;pending.append((y+c['delay'],declared))
        capacity['P'],reserve['P'],padd=legal_profit(capacity['P'],reserve['P'],registered['P'],profit['P']+declared+fund_gain-p_charge)
        group_profit=sum(profit.values())+fund_gain
        target=c['payout']*max(0.,group_profit) if y<=5 else .7*max(0.,group_profit)+.25*max(0.,cash['P']-p_floor)
        if 20<y<23:target=.7*max(0.,group_profit)
        if y>=c.get('p_release_year',23):target=max(0.,cash['P']-p_floor)
        if c['zero_dividend']:target=0.
        dividend=min(target,max(0.,cash['P']-p_floor),max(0.,capacity['P']))
        cash['P']-=dividend;capacity['P']-=dividend
        capital_return=0.;reduction=None
        if c.get('capital_release',False) and y>=15 and not c['zero_dividend']:
            excess=max(0.,cash['P']-p_floor)
            if excess>0 and capacity['P']<1e-6:
                reduction=reduce_capital(cash['P'],registered['P'],legal_shares,holder_units,excess,100.)
                cash['P']=reduction['cash'];registered['P']=reduction['registered'];legal_shares=reduction['shares'];holder_units=reduction['holder_units'];capital_return=reduction['cash_paid']
        expected=sum(begin.values())+sum(cf.values())+issue+draw-repayment-redemption-obligation+fund-dividend-capital_return-extra_interest
        err=sum(cash.values())-expected
        assert abs(err)<1e-6,(y,err)
        assert min(cash.values())>=-1e-7 and cash['B']+1e-7>=sum(v for _,v in pending)
        exit_bridge=None;exit_distribution=0.
        if exit_year==y:
            # All operating assets are sold; no franchise or project value remains after sale.
            # Working liabilities are reconstructed separately: never haircut net working assets.
            working_liabilities=.11*rev;gross_working=nwc+working_liabilities
            operating_realization=gross_working*c.get('working_recovery',.85)+fixed*c.get('fixed_recovery',.50)
            # Internal old payable and dividend obligations cancel ONLY after both actual sides settle.
            pending_amount=sum(v for _,v in pending); internal_remaining=receivable
            gross=sum(cash.values())+operating_realization
            fees=.03*operating_realization+25.
            obligations=debt+bond*1.08+working_liabilities
            sale_gain=operating_realization-(gross_working+fixed)
            exit_tax=max(0.,sale_gain)*.25
            before_layer=gross-fees-obligations-exit_tax
            if before_layer<0:
                # Infeasible orderly exit: creditors/expenses remain unpaid. Never clear
                # liabilities or cancel shares merely because equity residual is negative.
                failure={'year':y,'reason':'exit funding shortage before equity allocation',
                    'exit_shortfall':-before_layer,'gross_realized_assets':gross,
                    'exit_fees':fees,'external_creditor_obligations':obligations,
                    'exit_cash_tax':exit_tax,'cash_unliquidated':dict(cash),
                    'bank_debt_outstanding':debt,'bond_face_outstanding':bond,
                    'working_liabilities_outstanding':working_liabilities,
                    'pending_internal_dividends':list(pending),
                    'remaining_legal_shares':legal_shares,'holder_units':holder_units,
                    'dividend_before_failed_exit':dividend,'capital_return_before_failed_exit':capital_return,
                    'exit_distribution':0.,'liabilities_cleared':False,'shares_cancelled_by_exit':False}
                break
            # Economic allocation of already debt-cleared proceeds, NOT fictitious subsidiary balance sheets.
            # Cross-layer tax on positive cost-basis gains is separate from operating-asset losses.
            b_cash_settled=cash['B']-pending_amount+internal_remaining
            p_cash_settled=cash['P']+pending_amount-internal_remaining
            assert min(b_cash_settled,p_cash_settled)>=-1e-7
            b_equity=min(before_layer,max(0.,b_cash_settled+alloc*cash['R']+(.05+.05*alloc)*fixed*c.get('fixed_recovery',.5)))
            h_equity=min(before_layer-b_equity,max(0.,(1-alloc)*cash['R']+(.05*(1-alloc))*fixed*c.get('fixed_recovery',.5)))
            b_disposal=liquidation(b_equity,0,1,0,0,1,equity_basis['P_to_B'],total_new['P_to_B'],0,.25)
            h_disposal=liquidation(h_equity,0,1,0,0,1,equity_basis['P_to_Hangzhou'],total_new['P_to_Hangzhou'],0,.25)
            investment_gain_tax=b_disposal['tax']+h_disposal['tax']
            layer_tax_budget=c.get('layer_exit_friction',.05)*max(0.,before_layer-investment_gain_tax)
            net=before_layer-investment_gain_tax-layer_tax_budget
            if net<0:failure={'year':y,'exit_shortfall':-net};break
            exit_distribution=net;exit_bridge=dict(cash=sum(cash.values()),gross_working_assets=gross_working,working_liabilities=working_liabilities,
                fixed_operating_assets=fixed,operating_realization=operating_realization,fees=fees,external_debt=debt,bond_redemption=bond*1.08,
                corporate_cash_tax=exit_tax,parent_subsidiary_disposal_tax=investment_gain_tax,parent_B_disposal=b_disposal,parent_Hangzhou_disposal=h_disposal,additional_cross_layer_tax_friction_budget=layer_tax_budget,negative_sale_gain_no_refund=min(0.,sale_gain),ordinary_equity_cash=net,minority=0.,
                internal_receivables_paid_and_cancelled=internal_remaining,internal_dividend_paid_and_cancelled=pending_amount,
                parent_cash_after_internal_settlement=p_cash_settled,b_cash_after_internal_settlement=b_cash_settled,
                parent_original_investment_costs=equity_basis,parent_future_support=total_new.copy(),
                research_economic_costs_consumed=total_consumed.copy(),equity_cancellation_fraction=1.,
                scope='conditional group orderly exit; not asserted legal entity liquidation balance sheet')
            cash={k:0. for k in cash};debt=0.;bond=0.;pending=[];legal_shares=0.;holder_units=0.
        total_payment=dividend+capital_return+exit_distribution
        row=dict(year=y,segments=seg,revenue=rev,group_ebit=group_ebit,rd=rd,milestones=milestone,capex=capex,da=da,
            nwc=nwc,delta_nwc=dnwc,fixed_operating_assets=fixed,planned_da=planned_da,retired_asset_book=retired,asset_sale_cash=salvage,profit=profit,tax=tax,group_profit=group_profit,
            cash_open=begin,cash_close=dict(cash),operating_capital_cash=cf,capacity_budget=dict(capacity),
            reserve_budget=dict(reserve),registered_real_P_B=dict(registered),parent_discretionary_reserve=1.34187109,investment_book_value_B=39.69332303,investment_impairment_B=7.87179415,statutory_or_budget_add={'P':padd,'B':badd},
            research_support=support,research_support_via_B=support*alloc,research_support_via_parent_H=support*(1-alloc),
            parent_equity_topup_B=b_topup,investment_cost_start=equity_basis.copy(),future_investment_cost=total_new.copy(),
            research_cost_consumed=total_consumed.copy(),parent_economic_capacity_charge=p_charge,b_economic_capacity_charge=b_charge,
            debt=debt,bond_face=bond,bank_interest=bi+extra_interest,bond_coupon=coupon,bond_redemption=redemption,borrow=draw,repay=repayment,
            internal_old_settlement=settle,internal_old_remaining=receivable,sub_declared=declared,sub_received=received,pending_dividends=list(pending),
            common_dividend=dividend,capital_return=capital_return,exit_distribution=exit_distribution,dps=total_payment/economic_shares,
            economic_original_shares= economic_shares,remaining_legal_shares=legal_shares,holder_units=holder_units,capital_reduction=reduction,
            equity_issue_cash=issue,fund_recovery=fund,earmarked_cash=earmarked,parent_cash_floor=p_floor,b_cash_floor=b_floor,r_necessary_cash=r_floor,
            cash_conservation_error=err,exit_bridge=exit_bridge)
        rows.append(row)
        if exit_bridge:break
    return {'feasible':failure is None,'failure':failure,'rows':rows,'shares':economic_shares,'tail_decay':c['tail_decay'],
            'classification':'P legal facts + conditional capacity; B economic upstream budget; R economic cost/funding only'}

def value(run,r):
    if not run['feasible']:return {'feasible':False,'value':None,'failure':run['failure']}
    rows=run['rows'];pv=sum(z['dps']/(1+r)**z['year'] for z in rows)
    tv=sum(z['dps']/(1+r)**(z['year']-5) for z in rows if z['year']>5)
    return {'feasible':True,'value':pv,'tv5':tv,'dps':[z['dps'] for z in rows[:5]],'r':r,
        'tv5_pv_fraction':tv/(1+r)**5/pv,'final_cash':rows[-1]['cash_close'],
        'capital_return_pv':sum((z['capital_return']+z['exit_distribution'])/run['shares']/(1+r)**z['year'] for z in rows)}

def checks():
    assert legal_profit(0,5,20,10,paid=10)==(9.,6.,1.)
    assert legal_profit(-10,0,20,6)==(-4,0.,0.)
    assert legal_profit(-4,0,20,14)==(9.,1.,1.)
    assert legal_profit(0,10,20,10)==(10.,10.,0.)
    assert legal_profit(0,10,24,10)==(9.,11.,1.)
    # Production waterfall: gross 20 cash+100*.5=70; costs5, external30, parentloan10,
    # residual25; 80% equity20; original+new basis30 => loss10, cash30, zero refund.
    q=liquidation(20,100,.5,30,10,.8,20,10,5)
    assert q['parent_cash']==30 and q['investment_gain']==-10 and abs(q['minority_equity']-5)<1e-9 and q['tax']==0
    q2=liquidation(0,100,.5,60,10,1,20,0,0)
    assert q2['external_shortfall']==10 and q2['parent_cash']==0
    assert not q2['feasible'] and q2['shares_cancelled_fraction']==0
    fee_failure=liquidation(0,0,0,0,0,1,0,fees=5)
    assert not fee_failure['feasible'] and fee_failure['fees_shortfall']==5 and fee_failure['shares_cancelled_fraction']==0
    cr=reduce_capital(50,100,10,1,30,20)
    assert cr['cash']==20 and cr['shares']==7 and cr['holder_units']==.7 and cr['profit_recognized']==0
    # Actual simulator one-year literal case; R&D=0, no legal proxy pooling offshore.
    c=copy.deepcopy(BASE)
    for k in ['hbv','gh','other','new','rd','milestones','capex','da','research_sub']:c[k]=[0.]*10
    c.update(horizon=1,initial_cash={'P':5000.,'B':100.,'R':20.},initial_retained={'P':1000.,'B':100.,'R':-100.},bank_rate=0.,**{'yield':0.},payout=0.,b_payout=0.,nwc_ratio=0.,nwc_open=0.)
    c['hbv']=[100.]*10;c['gross']=[.8]*10;c['sell']=[.2]*10;c['admin']=[.1]*10;c['donation']=[0.]*10
    z=simulate(c)['rows'][0]
    assert abs(z['profit']['P']-37.1167239)<1e-8
    assert abs(z['cash_close']['P']-5124.29946886)<1e-8
    assert abs(z['cash_close']['B']-184.08)<1e-8
    # Collected old internal balance moved cash by 80; no investment earnings recognition.
    assert z['internal_old_settlement']==80 and z['sub_received']==0 and z['sub_declared']==0
    assert abs(z['capacity_budget']['P']-1034.9494599)<1e-8 # reserve already full in toy? new capital deficit .82539291
    bad=copy.deepcopy(BASE);bad.update(zero_dividend=True,initial_cash={'P':1.,'B':0.,'R':0.},bank_limit=800.);bad['rd']=[3000.]*10
    f=simulate(bad);assert not f['feasible']
    exit_failures={}
    for name,expected in [('base',31.38216653677449),('cyclical',31.38216653677449),('optimistic',29.1935731096377)]:
        c=copy.deepcopy(VARIANTS[name]);c.update(p_release_year=12,b_release_year=15,
            capital_release=True,retire_idle_assets=True,exit_year=40,
            working_recovery=0.,fixed_recovery=0.)
        stress=simulate(c);ef=stress['failure']
        assert not stress['feasible'] and ef['year']==40
        assert abs(ef['exit_shortfall']-expected)<1e-7,(name,ef)
        assert abs(ef['exit_shortfall']-(ef['exit_fees']+ef['external_creditor_obligations']+ef['exit_cash_tax']-ef['gross_realized_assets']))<1e-9
        assert ef['working_liabilities_outstanding']>0 and ef['remaining_legal_shares']>0
        assert not ef['liabilities_cleared'] and not ef['shares_cancelled_by_exit']
        assert ef['exit_distribution']==0 and value(stress,.1075)['value'] is None
        exit_failures[name]=ef
    return {'exit_funding_shortage_production_cases':exit_failures,'registered_not_paid':True,'loss_first':True,'reserve_full':True,'registered_conversion':True,
            'literal_production_exit':q,'insolvent_exit':q2,'proportional_cancellation':cr,'literal_one_year':z,
            'zero_dividend_financing_failure':f['failure']}

def produce():
    method={};runs={};vals={};old={};bridges={}
    for name,original in VARIANTS.items():
        oldrun=OLD['simulate'](original)
        old[name]={'low':OLD['valuation'](oldrun,.115),'high':OLD['valuation'](oldrun,.10)}
        method[name]=simulate(original,True)
        cfg=copy.deepcopy(original)
        # Allocation-policy change separately priced: do not wait 23/25 years for excess cash.
        cfg.update(p_release_year=12,b_release_year=15,capital_release=True,retire_idle_assets=True,exit_year=40)
        if name=='structural':cfg['exit_year']=35
        runs[name]=simulate(cfg)
        vals[name]={k:value(runs[name],r) for k,r in [('low',.115),('high',.10)]}
        bridges[name]={'old_same_economic_budget':old[name],
          'method_only_same_dates':{k:value(method[name],r) for k,r in [('low',.115),('high',.10)]},
          'new_policy':vals[name],
          'economic_parameter_change':{'B_opening_capacity_budget':[600,500],'p_excess_release': [23,12],'b_excess_release':[25,15],'franchise_exit_year':35 if name=='structural' else 40,'idle_fixed_capital_retirement_after_Y10':'annual demand decay rate, 35% gross recovery, 0 immediate loss tax refund'},
          'annual_method_changes':[{'year':a['year'],'old_cash':a['cash_close'],'new_cash':b['cash_close'],
            'old_dps':a['dps'],'new_dps':b['dps'],'new_b_support':b['research_support_via_B'],
            'old_parent_retained':a['retained']['P'],'new_parent_capacity':b['capacity_budget']['P']}
            for a,b in zip(oldrun['rows'],method[name]['rows'])]}
    sens={}
    choices=[('GH_minus20',{'gh_multiplier':.8}),('collection44',{'nwc_ratio':.44}),
      ('cash_shift200_delay2',{'shift_parent_to_sub':200.,'old_settlement_years':8,'delay':2}),('all_convert',{'convert':True}),
      ('RD_plus150',{'rd':[v+150 for v in BASE['rd']]}),('capital_overrun20',{'capex':[v*1.2 for v in BASE['capex']]}),
      ('no_new_pipeline',{'new':[0.]*10}),('R_via_B_50pct',{'research_via_b':.5}),('R_via_B_100pct',{'research_via_b':1.}),
      ('B_full_reserve',{'b_reserve':21.}),('B_capacity_zero',{'b_capacity':0.}),
      ('P_capacity1000',{'initial_retained':{'P':1000.,'B':600.,'R':-100.}}),
      ('cash_distribution_delay5',{'delay':5,'p_release_year':17,'b_release_year':20}),
      ('franchise_exit30',{'exit_year':30}),('franchise_exit50',{'exit_year':50}),('exit_layer_friction20',{'layer_exit_friction':.20}),('exit_layer_friction_zero',{'layer_exit_friction':0.}),('asset_salvage_zero',{'asset_salvage':0.}),('asset_salvage70',{'asset_salvage':.70}),('structural_exit25',{'__structural':True,'exit_year':25}),('structural_exit45',{'__structural':True,'exit_year':45}),
      ('structural_assets_half',{'__structural':True,'exit_year':35,'working_recovery':.65,'fixed_recovery':.25,'layer_exit_friction':.10})]
    for name,ch in choices:
        cc=copy.deepcopy(VARIANTS['structural'] if ch.get('__structural') else BASE)
        cc.update(p_release_year=12,b_release_year=15,capital_release=True,retire_idle_assets=True,exit_year=40);cc.update(ch)
        rr=simulate(cc);sens[name]={'change':ch,'run':rr,'value':value(rr,.1075)}
    convergence={}
    for name,c in VARIANTS.items():
        cc=copy.deepcopy(c);cc.update(p_release_year=12,b_release_year=15,capital_release=True,retire_idle_assets=True,exit_year=40,horizon=350)
        if name=='structural':cc['exit_year']=35
        rr=simulate(cc)
        convergence[name]={'250_to_350_value_change':value(rr,.10)['value']-vals[name]['high']['value'],
          'max_group_cash_error':max(abs(z['cash_conservation_error']) for z in rr['rows']),
          'first_cash_or_funding_failure':rr['failure'],
          'economic_principal_use':'R cash is an explicit operating buffer; research support consumed as costs. B/P surplus released 12/15, structural remaining assets sold Y35; continued operating fixed/NWC capital supports recurring earnings, not separately added.'}
    b=runs['base']['rows'][4];nopat=b['group_ebit']*.85-.15*BASE['research_sub'][4]
    excess=sum(b['cash_close'].values())-b['parent_cash_floor']-b['b_cash_floor']-b['r_necessary_cash']
    aux=[]
    for r,m in [(.115,9),(.10,11)]:
        net=excess/(1+r)**3-b['debt']-1533.266*1.08/(1+.025)+161.65239399/(1+r)**3
        tv=(nopat*m+net)/SHARES
        aux.append({'value':sum(z['dps']/(1+r)**z['year'] for z in runs['base']['rows'][:5])+tv/(1+r)**5,'tv5':tv,'nopat':nopat,'multiple':m,'financial_bridge':net})
    return {'schema':'688278-root-repair-v1','unit':'CNY million, shares million, per-share CNY',
      'as_of':'2026-10-26T00:00:00+08:00','inputs':VARIANTS,'runs':runs,'method_only_runs':method,
      'valuations':vals,'bridges':bridges,'sensitivities':sens,'auxiliary':aux,'tests':checks(),'convergence':convergence}

def main():
    out=produce();raw=json.dumps(out,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    target=Path(__file__).with_name('2026-Q3-output.json')
    if len(raw)>16*1024*1024:
        wrapped={'schema':'lossless-gzip-base64-v1','decoded_schema':out['schema'],'sha256':hashlib.sha256(raw).hexdigest(),
            'decoded_bytes':len(raw),'summary':out['valuations'],'encoding':'gzip-mtime-0/base64',
            'expand_command':"python -c \"import json,gzip,base64; p=json.load(open('2026-Q3-output.json'));open('expanded.json','wb').write(gzip.decompress(base64.b64decode(p['payload'])))\"",
            'payload':base64.b64encode(gzip.compress(raw,mtime=0)).decode()}
        target.write_text(json.dumps(wrapped,ensure_ascii=False,indent=2)+'\n')
        assert json.loads(gzip.decompress(base64.b64decode(wrapped['payload'])))==out
    else:target.write_bytes(raw+b'\n')
    print(json.dumps({'valuations':out['valuations'],'auxiliary':out['auxiliary'],'convergence':out['convergence']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
