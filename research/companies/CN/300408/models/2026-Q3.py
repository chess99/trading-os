#!/usr/bin/env python3
"""300408 owner cash model. Python standard library only; units CNY billion.
All entity allocations/prospective figures are budgets, NOT disclosed legal statements.
Run from any cwd: python /absolute/path/2026-Q3.py [--output path]
"""
import json, math, argparse, tempfile, subprocess, sys, hashlib
from pathlib import Path
SHARES=1.996718571
FACTS={'revenue_9m':11.50279609524,'profit_9m':3.865199634,'revenue_q3':5.07946433904,'profit_q3':1.93308139329,'cash':11.57188087185,'liquid_investments':3.06164445722,'other_noncurrent':5.54262411258,'long_deposit_budget':5.30,'debt_and_lease':1.66953126187,'post_balance_buyback_budget':.50,'minority_equity':.00419001671,'parent_retained_H1':6.76403078395,'parent_reserve_H1':1.13113825124,'issued_shares_bn':SHARES}
OPEN_CASH=FACTS['cash']+FACTS['liquid_investments']+FACTS['long_deposit_budget']-FACTS['debt_and_lease']-FACTS['post_balance_buyback_budget']-FACTS['minority_equity']
NAMES=['潮州三环母公司','南充三环','德阳三环','其他正留存预算组（香港/深圳/苏州等）','境外未弥亏预算组（具体法人未披露；境外实际主体含Frontier/Vermes/Glory）']
OP=[.45,.25,.20,.08,.02]; CAP=[.22,.35,.33,.08,.02]
N=len(OP); FLOOR=[.5,.225,.175,.08,.02]
# Legal capital/reserve of other group is a conservative budget, not one legal entity.
CAPITAL=[SHARES,.06,.20,.90,.10]; RESERVE=[1.13113825124,.03,.10,.05,0.]
RETAINED=[6.76403078395,4.,3.,1.,-.08387549836]
INITIAL=[OPEN_CASH-5.2,2.2,1.7,1.1,.2]
LOANS=[0.,1.4,.9,.205,.05]
BASE={'rate':.10,'margin_shift':0.,'revenue_scale':1.,'capex_scale':1.,'legal_scale':1.,'cash_delay':0,'repatriation_haircut':.10,'foreign_delay':2,'interest_net':.015,'special_cap':2.,'terminal_margin':.24,'operating_tax':.15}

def legal_step(retained,reserve,capital,profit,cash_available,wanted,reserve_rate=.10):
    """Same production chain in every entity, including hand-calculable tests."""
    healed=max(0.,profit+min(retained,0.))
    appropriation=min(reserve_rate*healed,max(0.,.5*capital-reserve))
    legal=max(0.,retained+profit-appropriation)
    dividend=min(max(0.,wanted),max(0.,cash_available),legal)
    return {'retained':retained+profit-appropriation-dividend,'reserve':reserve+appropriation,'reserve_add':appropriation,'legal_capacity':legal,'dividend':dividend}

def forecast(cfg,years=240):
    """Economic inputs: revenue -> after-tax operating profit -> capital -> entity cash."""
    out=[]; rev0=16.8*cfg['revenue_scale']; rev=rev0
    for t in range(1,years+1):
        if 'flat_earnings' in cfg:
            out.append({'year':t,'revenue':19.5,'margin':cfg['flat_earnings']/19.5,'operating_profit':cfg['flat_earnings'],'depreciation':1.2,'capex':1.2+(1.8683195 if t==1 else 0.),'delta_wc':(19.5-rev)*.20})
            rev=19.5
            continue
        growth=[None,.12,.09,.06,.04,.04,.035,.03,.025,.02][t-1] if t<=10 else .02
        nr=19.5*cfg['revenue_scale'] if t==1 else rev*(1+growth)
        m=([.28,.275,.265,.255,.25,.248,.246,.244,.242,.24][t-1] if t<=10 else cfg['terminal_margin'])+cfg['margin_shift']
        m=m*(1-cfg['operating_tax'])/.85 if m>0 else m/.85
        da=([.95,1.15,1.35,1.5,1.6][t-1] if t<=5 else nr*.06)
        cap=([3.,3.,2.6,2.3,2.0][t-1] if t<=5 else da+(nr-rev)*.55)*cfg['capex_scale']
        wc=(nr-rev)*.20
        # Profits include operating tax (15% base, through normalized after-tax margin).
        # No financial income, subsidies or unrealized investment gains in operating profit.
        out.append({'year':t,'revenue':nr,'margin':m,'operating_profit':nr*m,'depreciation':da,'capex':cap,'delta_wc':wc})
        rev=nr
    return out

def model(cfg,years=240):
    rows=[]; cash=INITIAL[:]; cash[0]+=cfg.get('opening_cash_delta',0.); ret=[x*cfg['legal_scale'] if x>=0 else x for x in RETAINED]; reserve=RESERVE[:]; loans=LOANS[:]
    retained_cash_release_year=None
    book_ppe=8.166
    for econ in forecast(cfg,years):
        t=econ['year']; book_ppe+=econ['capex']-econ['depreciation']; opening=sum(cash); fin=[c*cfg['interest_net'] for c in cash]
        profits=[econ['operating_profit']*w+fin[i] for i,w in enumerate(OP)]
        minimum=[econ['revenue']*.10*w for w in FLOOR]
        flows=[profits[i]+econ['depreciation']*CAP[i]-econ['capex']*CAP[i]-econ['delta_wc']*OP[i] for i in range(N)]
        # Known overseas loss bucket is separate; withholding occurs only on actual remittance.
        foreign_tax=0.
        for i in range(N): cash[i]+=flows[i]
        # Parent equity injections as needed; no fictitious external funding.
        injections=[0.]*N
        for i in range(1,N):
            if cash[i]<minimum[i]:
                injections[i]=minimum[i]-cash[i]; cash[0]-=injections[i]; cash[i]+=injections[i]
        assert cash[0]>=-1e-8,'Unfunded capital plan'
        # Real intercompany loan repayments budget, does NOT create parent legal earnings.
        repayments=[0.]*N
        if 6<=t<=10:
            for i in range(1,N):
                repayments[i]=min(loans[i],LOANS[i]/5,max(0.,cash[i]-minimum[i]))
                loans[i]-=repayments[i]; cash[i]-=repayments[i]; cash[0]+=repayments[i]
        dividends=[]; entity=[]; up=0.
        for i in range(1,N):
            wanted=0. if t<=max(cfg['cash_delay'],cfg['foreign_delay'] if i==4 else 0) else max(0.,cash[i]-minimum[i])
            # Capital-use funds: no excess distribution during first five construction years;
            # only current realized earnings/cash conversion can be remitted.
            if t<=5: wanted=min(wanted,max(0.,profits[i])*.70)
            st=legal_step(ret[i],reserve[i],CAPITAL[i],profits[i],cash[i]-minimum[i],wanted,reserve_rate=0. if i==4 else .10)
            ret[i]=st['retained']; reserve[i]=st['reserve']; cash[i]-=st['dividend']; tax=st['dividend']*cfg['repatriation_haircut'] if i==4 else 0.; foreign_tax+=tax;up+=st['dividend']-tax
            entity.append(dict(name=NAMES[i],profit=profits[i],cashflow=flows[i],loan_repayment=repayments[i],injection=injections[i],minimum_cash=minimum[i],closing_cash=cash[i],withholding_tax=tax,**st))
        cash[0]+=up
        parent_profit=profits[0]+up # dividend declaration and receipt same year budget.
        # Actual known opening HK dividend receivable excluded from incremental profit and cash;
        # immaterial 0.008826bn, no duplicate gain.
        payout=[.25,.30,.35,.40,.45][t-1] if t<=5 else 1.
        wanted=max(0.,econ['operating_profit'])*payout
        if t>=6: wanted+=max(0.,sum(fin)-foreign_tax)+cfg['special_cap']
        st=legal_step(ret[0],reserve[0],CAPITAL[0],parent_profit,cash[0]-minimum[0],wanted)
        ret[0]=st['retained']; reserve[0]=st['reserve']; cash[0]-=st['dividend']
        entity.insert(0,dict(name=NAMES[0],profit=parent_profit,own_profit=profits[0],upstream_dividend=up,cashflow=flows[0],minimum_cash=minimum[0],closing_cash=cash[0],**st))
        closing=sum(cash); div=st['dividend']; totalflow=sum(flows)-foreign_tax
        liquidation=0.
        if t in [cfg.get('capital_return_year'),cfg.get('foreign_capital_return_year')]:
            # Explicit conditional legal-entity capital return, NOT approved policy.
            # Parent budget limited to 60% of disclosed 13.0169bn capital reserve;
            # the register/creditor/tax process must separately permit a proportional
            # return. Reference ownership units unchanged, nominal shares may shrink.
            # Overseas unidentified-loss bucket: only allocated .2bn initial financial
            # resources as an economic ceiling, subject to EACH relevant local entity's
            # solvency/capital tests. No inference that PRC rules authorize foreign return.
            indices=([0] if t==cfg.get('capital_return_year') else [])+([4] if t==cfg.get('foreign_capital_return_year') else [])
            for i in indices:
                ceiling=13.01691792502*.60 if i==0 else .2
                gross=min(max(0.,cash[i]-minimum[i]),ceiling)
                cost=min(gross,.02*gross+.2) if i==0 else min(gross,.10*gross+.02)
                if i==4:
                    # Two legs: foreign capital proceeds to parent, then separately
                    # approved supplementary parent proportional capital return.
                    cost+=min(gross-cost,.02*(gross-cost)+.02)
                    entity[0]['supplementary_capital_return_from_foreign']=gross-cost
                payment=gross-cost
                cash[i]-=gross; div+=payment;liquidation+=payment;totalflow-=cost
                entity[i]['conditional_capital_return_gross']=gross
                entity[i]['conditional_capital_return_ceiling']=ceiling
                entity[i]['conditional_capital_return_cost']=cost
                entity[i]['conditional_capital_return']=payment
                entity[i]['closing_cash']=cash[i]
            closing=sum(cash)
        assert abs(opening+totalflow-div-closing)<1e-8*max(1.,closing)
        assert all(c>=-1e-9 for c in cash)
        if retained_cash_release_year is None and t>5 and closing<=sum(minimum)+.001: retained_cash_release_year=t
        rows.append(dict(**econ,opening_cash=opening,financial_income=sum(fin),foreign_tax=foreign_tax,group_cashflow=totalflow,dividend=div,dps=div/SHARES,closing_cash=closing,minimum_cash=sum(minimum),book_ppe=book_ppe,liquidation_distribution=liquidation,entities=entity))
    r=cfg['rate']; pv=sum(z['dps']/(1+r)**z['year'] for z in rows)
    # Mature cash is necessary working liquidity, no excess financial principal stranded.
    # 240-year omitted PV is immaterial; explicit truncation convergence reported below.
    term=sum(z['dps']/(1+r)**(z['year']-5) for z in rows[5:])
    return {'config':cfg,'value':pv,'year5_terminal':term,'terminal_pv_fraction':term/(1+r)**5/pv,'dps':[z['dps'] for z in rows[:5]],'excess_cash_exhausted_year':retained_cash_release_year,'rows':rows}

def literal(cfg,years=240):
    """Independent literal implementation, NOT calling forecast/model/legal_step.
    Re-derives sales, profits, all entity capital/cash/legal budgets and dividends.
    Used to independently test the low endpoint and dominant margin sensitivity.
    """
    c=list(INITIAL); u=[v*cfg['legal_scale'] if v>=0 else v for v in RETAINED]; s=list(RESERVE); debt=list(LOANS)
    revenue=16.8*cfg['revenue_scale']; value=0.; values=[]
    for y in range(1,years+1):
        old=revenue
        if y==1: revenue=19.5*cfg['revenue_scale']
        else: revenue*=1+([0,.12,.09,.06,.04,.04,.035,.03,.025,.02][y-1] if y<=10 else .02)
        margin=([.28,.275,.265,.255,.25,.248,.246,.244,.242,.24][y-1] if y<=10 else cfg['terminal_margin'])+cfg['margin_shift']
        margin=margin*(1-cfg['operating_tax'])/.85 if margin>0 else margin/.85
        operating=revenue*margin
        depreciation=[.95,1.15,1.35,1.5,1.6][y-1] if y<=5 else .06*revenue
        investment=([3.,3.,2.6,2.3,2.0][y-1] if y<=5 else depreciation+.55*(revenue-old))*cfg['capex_scale']
        working=.2*(revenue-old); interest=[x*cfg['interest_net'] for x in c]
        earnings=[operating*OP[i]+interest[i] for i in range(N)]
        tax=0.
        floors=[revenue*.1*x for x in FLOOR]
        for i in range(N): c[i]+=earnings[i]+(depreciation-investment)*CAP[i]-working*OP[i]
        for i in range(1,N):
            if c[i]<floors[i]: c[0]-=floors[i]-c[i]; c[i]=floors[i]
        if 6<=y<=10:
            for i in range(1,N):
                pay=min(debt[i],LOANS[i]/5,max(0,c[i]-floors[i])); c[i]-=pay;c[0]+=pay;debt[i]-=pay
        up=0
        for i in list(range(1,N))+[0]:
            profit=earnings[i]+(up if i==0 else 0)
            reserve=min(max(0,CAPITAL[i]/2-s[i]),max(0,profit+min(u[i],0))*(0. if i==4 else .1))
            available=max(0,u[i]+profit-reserve)
            if i:
                desired=0 if y<=max(cfg['cash_delay'],cfg['foreign_delay'] if i==4 else 0) else max(0,c[i]-floors[i])
                if y<=5: desired=min(desired,max(0,profit)*.7)
            else:
                c[0]+=up
                desired=max(0,operating)*([.25,.30,.35,.40,.45][y-1] if y<=5 else 1.)
                if y>=6: desired+=max(0,sum(interest)-tax)+cfg['special_cap']
            payment=max(0,min(desired,c[i]-floors[i],available))
            u[i]+=profit-reserve-payment;s[i]+=reserve;c[i]-=payment
            if i:
                withheld=payment*cfg['repatriation_haircut'] if i==4 else 0.;tax+=withheld;up+=payment-withheld
            else: value+=payment/SHARES/(1+cfg['rate'])**y; values.append(payment/SHARES)
    return {'value':value,'dps':values[:5]}

def hand_tests():
    # Loss -2 then +1 then +3: loss carried forward; zero first two distributions.
    u=0.;s=0.; results=[]
    for p in [-2.,1.,3.]:
        x=legal_step(u,s,10.,p,100.,100.);u=x['retained'];s=x['reserve'];results.append(x)
    assert [x['dividend'] for x in results]==[0.,0.,1.8]
    assert abs(results[-1]['reserve']-.2)<1e-12
    # cap remaining .05, profit 1: reserve .05, dividend .95.
    x=legal_step(0.,.45,1.,1.,10.,10.);assert abs(x['dividend']-.95)<1e-12 and x['reserve']==.5
    # Cash-bound .3 despite legal capacity .9.
    z=legal_step(0.,0.,10.,1.,.3,10.);assert abs(z['dividend']-.3)<1e-12
    return {'loss_then_profit':results,'reserve_cap':x,'cash_cap':z}

def crosscheck():
    # Independent economic premise: no expansion/no real growth; mature operating
    # earnings 4.3--4.9bn; existing MLCC
    # unfinished obligation 1.8683195bn paid in year 1 with no credited extra earnings.
    # Same holders and legal/cash waterfall; not a valuation identity or market multiple.
    values=[]
    for earnings,r in [(4.3,.105),(4.9,.095)]:
        cfg=dict(BASE,flat_earnings=earnings,rate=r,capital_return_year=20,foreign_capital_return_year=30)
        v=model(cfg)
        values.append({'normalized_operating_earnings':earnings,'rate':r,'value':v['value'],'year5_terminal':v['year5_terminal'],'excess_cash_exhausted_year':v['excess_cash_exhausted_year'],'config':cfg,'release_sensitivity':{str(y):model(dict(cfg,capital_return_year=y))['value'] for y in [15,20,30,40]},'final_excess_principal_bn':max(0.,v['rows'][-1]['closing_cash']-v['rows'][-1]['minimum_cash']),'foreign_return_year40_value':model(dict(cfg,foreign_capital_return_year=40))['value'],'rows':v['rows']})
    return values

def main():
    specs={'base':{},'core_low':{'rate':.105,'margin_shift':-.015},'core_high':{'rate':.095,'margin_shift':.015},'margin_minus_3pp':{'margin_shift':-.03},'lower_demand':{'revenue_scale':.85,'margin_shift':-.02,'cash_delay':2},'structural':{'revenue_scale':.80,'margin_shift':-.07,'capex_scale':1.15,'special_cap':1.},'legal_delay':{'legal_scale':0.,'cash_delay':5,'special_cap':1.},'capital_plus_25pct':{'capex_scale':1.25},'slower_return':{'special_cap':.5},'deposit_minus_500m':{'opening_cash_delta':-.5},'profit_tax_plus_3pp':{'operating_tax':.18},'blocked_foreign_5years':{'cash_delay':5}}
    cases={k:model(dict(BASE,**v)) for k,v in specs.items()}
    independently={}
    for k in ['core_low','margin_minus_3pp']:
        independently[k]=literal(cases[k]['config']);assert abs(independently[k]['value']-cases[k]['value'])<1e-10
    b=cases['base']; conv={n:model(BASE,n)['value'] for n in [100,160,240]}
    assert abs(conv[240]-conv[160])<.001
    assert b['excess_cash_exhausted_year'] is not None
    tail_audit={}
    for name,v in cases.items():
        last=v['rows'][-1]; excess=max(0.,last['closing_cash']-last['minimum_cash'])
        tail_audit[name]={'year240_excess_principal_bn':excess,'year240_necessary_cash_bn':last['minimum_cash'],'value_240_minus_160':v['value']-model(v['config'],160)['value'],'excess_exhausted_year':v['excess_cash_exhausted_year']}
        assert excess<1e-6 and abs(tail_audit[name]['value_240_minus_160'])<.002
    result={'company':'CN:300408','period':'2026-Q3','units':'CNY billion except per-share CNY','facts':FACTS,'opening_cash_bridge':OPEN_CASH,'budget_entity_openings':[dict(name=NAMES[i],cash=INITIAL[i],retained=RETAINED[i],reserve=RESERVE[i],capital=CAPITAL[i],parent_loan=LOANS[i],operating_profit_weight=OP[i],capital_weight=CAP[i]) for i in range(N)],'cases':cases,'independent_literal':independently,'production_hand_tests':hand_tests(),'convergence':conv,'all_scenarios_tail_audit':tail_audit,'auxiliary_earnings_power':crosscheck()}
    ap=argparse.ArgumentParser();ap.add_argument('--output');ap.add_argument('--verify-repro',action='store_true');args=ap.parse_args()
    if args.verify_repro:
        source=Path(__file__).resolve(); expected=source.with_name('2026-Q3-output.json').read_bytes()
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            blobs=[]
            for directory in [a,b]:
                target=Path(directory)/'out.json'
                subprocess.run([sys.executable,str(source),'--output',str(target)],cwd=directory,check=True,capture_output=True)
                blobs.append(target.read_bytes())
            assert blobs[0]==blobs[1]==expected
            print(json.dumps({'byte_identical':True,'sha256':hashlib.sha256(expected).hexdigest(),'independent_cwds':2}))
        return
    p=Path(args.output) if args.output else Path(__file__).with_name('2026-Q3-output.json')
    p.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(p),'cases':{k:{q:v[q] for q in ['value','year5_terminal','dps','excess_cash_exhausted_year']} for k,v in cases.items()},'auxiliary':[{k:v for k,v in z.items() if k!='rows'} for z in result['auxiliary_earnings_power']],'convergence':conv},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
