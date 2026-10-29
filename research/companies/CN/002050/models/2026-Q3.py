#!/usr/bin/env python3
"""Sanhua 2026Q3. Python stdlib only. All monetary quantities CNY billion;
shares billion. No prices, network, local inputs, or cwd dependencies."""
import json, copy, math
S=4.207365435 # includes treasury stock assumed reissued for compensation; no fictitious cancellation
MIN=69575380.74/3136869701.89
START=dict(cash=13.62726641447+.94976587324+.917995-(.057184368+.0073784+.03068077627+.01815410725+.02156603859+.14066+.0071335)-.010146686,
 debt=1.54691094311+.99896272274+1.23492+.15251487221,
 mother_cash=6.5,mother_profit=.78460581691-.50329943904,
 reserve=1.17290878487,minor_cash=.16,need=3.3)
BASE=dict(revenue=[34.3,36.7,39.3,41.8,44.2], margin=[.151,.153,.155,.155,.154],
 da=[1.6,1.75,1.9,2.05,2.2],capex=[3.6,3.5,3.3,3.1,3.1],wc=[.50,.55,.60,.60,.60],
 tax=.16,need_ratio=.10,cash_yield=.015,debt_rate=.03,payout=.40,
 upstream_fraction=.38,mother_np_fraction=.14,mother_fcf_fraction=.12,mother_injection=.45,
 grant=[.244,.244,.2430296258,0,0],mother_need=1.2, mother_debt_fraction=.60, repays=[1.2,1.2,1.2,.33330853806,0],
 buybacks=[.19204866216,0,0,0,0], repay_extra=[0]*5,
 release_years=10,growth6=.04,roic6=.16,g=.025,roic=.14,rates=[.10,.09],multiple=[14,16],
 minority=MIN,shares=S,initial=START, label='base')

def continuation(nopat,growth,roic,g,steady_roic,r):
    """Same chain used by production and hand special-case; excludes financial income/assets."""
    vals=[]
    for i in range(1,6):
        nopat*=1+growth
        vals.append(nopat*(1-growth/roic))
    tv=nopat*(1+g)*(1-g/steady_roic)/(r-g)
    ev=sum(v/(1+r)**(i+1) for i,v in enumerate(vals))+tv/(1+r)**5
    return ev,vals,tv

def run(p):
    z=p['initial'];cash=z['cash'];debt=z['debt'];mc=z['mother_cash'];mp=z['mother_profit'];res=z['reserve'];mi=z['minor_cash'];need=z['need'];rows=[]
    for i in range(5):
        rev=p['revenue'][i]; nop=rev*p['margin'][i]*(1-p['tax']);fcf=nop+p['da'][i]-p['capex'][i]-p['wc'][i]
        ni=nop-p['debt_rate']*debt*(1-p['tax'])+max(cash-need,0)*p['cash_yield']; common_ni=ni*(1-p['minority'])-p['grant'][i]
        interest=debt*p['debt_rate']*(1-p['tax']);fin=max(cash-need,0)*p['cash_yield'];need1=rev*p['need_ratio']
        # Minority owns operating cash and its own financial subaccount; no parent profits from internal dividends.
        mfin=max(mi,0)*p['cash_yield'];mflow=fcf*p['minority']+mfin;md=max(nop*p['minority']*.15,0);mi1=mi+mflow-md
        principal=min(debt,max(p['repays'][i]+p['repay_extra'][i],0)); buy=p['buybacks'][i]
        pre=cash+fcf+fin-interest-principal-buy-md
        mown=nop*p['mother_np_fraction'];subprofit=max(nop*(1-p['minority'])-mown,0)
        # Fresh declarations budgeted from current profits, not old receivable collections or new capital.
        proposed_up=subprofit*p['upstream_fraction'];injection=p['mother_injection']
        moper=fcf*p['mother_fcf_fraction'];mfincome=max(mc-p['mother_need'],0)*p['cash_yield'];mint=interest*p['mother_debt_fraction'];mpr=principal*p['mother_debt_fraction']
        parent_pre=mc+moper+mfincome-mint-mpr-buy-injection
        sub_pre=pre-parent_pre
        sub_min=max(need1-p['mother_need'],0)+max(mi1,0)
        up=min(proposed_up,max(sub_pre-sub_min,0))
        parent_pre+=up;sub_pre-=up
        mp_income=mown+up+mfincome-mint-p['grant'][i]
        sr=min(max(mp_income,0)*.1,max(p['shares']*.5-res,0));res+=sr
        available=max(mp+mp_income-sr,0)
        intended=max(common_ni*p['payout'],0)
        div=min(intended,available,max(parent_pre-p['mother_need'],0),max(pre-need1-mi1,0))
        mc1=parent_pre-div;cash1=pre-div;mp1=mp+mp_income-sr-div
        assert mc1>=p['mother_need']-1e-8 and cash1-mc1>=sub_min-1e-8,(p['label'],i,'liquidity')
        assert mp1>=-1e-8 and abs(cash1-(cash+fcf+fin-interest-principal-buy-md-div))<1e-9
        assert abs((cash1-mc1)+mc1-cash1)<1e-10
        rows.append(dict(year=i+1,revenue=rev,nopat=nop,fcf=fcf,net_income=ni,common_income=common_ni,da=p['da'][i],capex=p['capex'][i],new_wc=p['wc'][i],need_cash=need1,increment_need=need1-need,
         finance_income=fin,interest=interest,principal=principal,debt_end=debt-principal,buyback=buy,minor_div=md,minor_financial_end=mi1,dividend=div,dps=div/p['shares'],dividend_requested=intended,cash_end=cash1,
         mother_own_np=mown,subsidiary_profit=subprofit,upstream=up,upstream_requested=proposed_up,mother_injection=injection,mother_cash_end=mc1,subs_cash_end=cash1-mc1,mother_reserve_end=res,mother_retained_end=mp1,mother_np=mp_income,grant_expense=p['grant'][i],grant_capital_reserve_credit=p['grant'][i]))
        cash,debt,mc,mp,mi,need=cash1,debt-principal,mc1,mp1,mi1,need1
    vals=[]
    for r,mult in zip(p['rates'],p['multiple']):
        op,cfs,tv=continuation(rows[-1]['nopat'],p['growth6'],p['roic6'],p['g'],p['roic'],r)
        excess=cash-need-mi
        # Extra principal is distributed gradually, not magically at par in year 5.
        release=p.get('release_years',10)
        while True:
            legal_ok=True
            asset_schedule=[excess/release+(excess-excess*j/release)*p['cash_yield'] for j in range(release)]
            asset_value=sum(v/(1+r)**(j+1) for j,v in enumerate(asset_schedule))
            bridge=asset_value-debt # no second book minority subtraction
            # Legal capacity test: source only fresh projected subsidiary profits retained after declarations;
            # no credit for undisclosed historical reserves, old receivable or mother capital injections.
            # Separate source buckets. Paid-in-capital caps are actual H1 CNY amounts for
            # the three major wholly owned PRC entities; other entities use a separately stress-tested liquidity/earnings buffer, not an asserted legal cap.
            # Zero opening reserve/retained is deliberately a forecast lower-bound, not their reported legal balance.
            buckets=[dict(name=n,weight=w,cap=c,stat=0.,retained=0.) for n,w,c in
                     [('auto',.55,2.16*.5),('commercial',.18,1.65529*.5),('microchannel',.12,.36*.5),('other',.15,p.get('other_reserve_cap',1.2))]]
            for z in rows:
                for bk in buckets:
                    profit=z['subsidiary_profit']*bk['weight']
                    st=min(max(profit,0)*.1,max(bk['cap']-bk['stat'],0));bk['stat']+=st
                    bk['retained']+=profit-st-z['upstream']*bk['weight']
            mother_excess=min(max(mc-p['mother_need'],0),excess)
            for bk in buckets: bk['cash']=(excess-mother_excess)*bk['weight']
            parent_res=mp;parent_stat=res;remaining=excess;lastnop=rows[-1]['nopat'];tail_legal=[]
            for j in range(release):
                growth=p['growth6'] if j<5 else p['g'];ret=p['roic6'] if j<5 else p['roic']
                lastnop*=1+growth;common_np=lastnop*(1-p['minority']);common_fcf=common_np*(1-growth/ret)
                pay=common_fcf+remaining*p['cash_yield']+excess/release
                own_np=lastnop*p['mother_np_fraction'];own_cf=common_fcf*p['mother_fcf_fraction']
                mother_excess=min(max(mc-p['mother_need'],0),excess)
                mother_release=mother_excess/release
                mother_fin=remaining*p['cash_yield']*(mother_excess/excess if excess else 0)
                child_fin=remaining*p['cash_yield']-mother_fin
                up_needed=pay-own_cf-mother_fin-mother_release
                # Child total cash includes the release reserve; this transfer is internal.
                child_profit=common_np-own_np
                caps=[]
                for bk in buckets:
                    finance=bk['cash']*p['cash_yield']
                    profit=child_profit*bk['weight']+finance
                    st=min(max(profit,0)*.1,max(bk['cap']-bk['stat'],0));bk['stat']+=st
                    bk['retained']+=profit-st
                    bk['cash']+=(common_fcf-own_cf)*bk['weight']+finance
                    caps.append(max(min(bk['retained'],bk['cash']),0))
                # Pay first from the intended sources, then legally redistribute declarations among
                # funded profitable sources. No loss entity is assumed able to pay merely because group cash exists.
                paid=[min(up_needed*bk['weight'],c) for bk,c in zip(buckets,caps)]
                shortage=max(up_needed-sum(paid),0)
                for k in range(len(buckets)):
                    extra=min(shortage,caps[k]-paid[k]);paid[k]+=extra;shortage-=extra
                legal_ok=legal_ok and shortage<1e-8
                for bk,amount in zip(buckets,paid):
                    bk['cash']-=amount;bk['retained']-=amount
                    legal_ok=legal_ok and bk['cash']>=-1e-8 and bk['retained']>=-1e-8
                assert abs(sum(bk['cash'] for bk in buckets)-(remaining-excess/release)*(1-mother_excess/excess))<1e-7 or not legal_ok
                parent_profit=own_np+up_needed+mother_fin
                parent_st=min(max(parent_profit,0)*.1,max(p['shares']*.5-parent_stat,0))
                parent_stat+=parent_st
                parent_res+=parent_profit-parent_st-pay
                legal_ok=legal_ok and parent_res>=-1e-8
                tail_legal.append(dict(year=j+6,payout=pay,upstream=up_needed,subsidiary_legal_retained=sum(q['retained'] for q in buckets),
                    source_buckets=[{**q,'cap':q['cap'] if math.isfinite(q['cap']) else None} for q in buckets],
                    mother_legal_retained=parent_res,mother_statutory=parent_stat,mother_finance_income=mother_fin,subsidiary_finance_income=child_fin,excess_end=remaining-excess/release))
                remaining-=excess/release
            assert abs(remaining)<1e-8
            if legal_ok: break
            release+=5
            if release>100: raise ValueError('Unconstrained payment path: '+p['label'])
        terminal=((1-p['minority'])*op+bridge)/p['shares']
        d_pv=sum(x['dps']/(1+r)**x['year'] for x in rows)
        present=d_pv+terminal/(1+r)**5
        aux_tv=((1-p['minority'])*rows[-1]['nopat']*mult+bridge)/p['shares']
        vals.append(dict(rate=r,value=present,terminal=terminal,op_value5=op,bridge5=bridge,terminal_pv_share=(terminal/(1+r)**5)/present,
          asset_release_years=release,extra_assets5=excess,extra_assets_value5=asset_value,asset_runoff=asset_schedule,tail_legal=tail_legal,distributions_pv=d_pv,aux_value=d_pv+aux_tv/(1+r)**5,aux_terminal=aux_tv,future6_10_fcff=cfs,year10_terminal=tv))
    return dict(label=p['label'],inputs=p,rows=rows,valuation=vals)

def scenario(label,**kw):
 p=copy.deepcopy(BASE);p.update(kw);p['label']=label;return p

def all_results():
 scenarios=[BASE,
 scenario('cyclical',revenue=[31,32,35,38,41],margin=[.125,.13,.145,.15,.152],capex=[3.2,2.8,2.9,3,3.1],wc=[.6,.2,.45,.5,.55],payout=.30,upstream_fraction=.30,growth6=.035,roic6=.14,g=.02,roic=.12,rates=[.105,.095],multiple=[12,14]),
 scenario('structural',revenue=[31,30,30,30.5,31],margin=[.12,.105,.10,.10,.10],capex=[3.2,2.8,2.6,2.5,2.5],da=[1.6,1.75,1.85,1.9,1.9],wc=[.8,.4,.2,.15,.15],payout=.20,upstream_fraction=.22,mother_injection=.2,growth6=.01,roic6=.085,g=.01,roic=.085,rates=[.115,.105],multiple=[9,11]),
 scenario('optimistic',revenue=[36,40,44.5,49,53.5],margin=[.16,.163,.165,.165,.163],capex=[4,4,3.9,3.8,3.7],da=[1.65,1.85,2.05,2.3,2.55],wc=[.65,.7,.75,.8,.8],payout=.4,upstream_fraction=.40,mother_injection=.6,growth6=.05,roic6=.19,g=.03,roic=.17,rates=[.095,.085],multiple=[16,18]),
 scenario('upstream_delay',upstream_fraction=.12),
 scenario('extra_capital',capex=[4.6,4.5,4.3,4.1,4.1]),
 scenario('structural_capital_failure',revenue=[31,30,30,30.5,31],margin=[.12,.105,.10,.10,.10],capex=[3.8,3.5,3.2,3,2.8],da=[1.6,1.75,1.85,1.9,1.9],wc=[.8,.4,.2,.15,.15],payout=.10,upstream_fraction=.18,mother_injection=.2,repays=[.6,.6,.6,.6,.6],growth6=.01,roic6=.075,g=.01,roic=.075,rates=[.12,.11],multiple=[8,10]),
 scenario('margin_minus_1pct',margin=[x-.01 for x in BASE['margin']]),
 scenario('terminal_roic_10pct',roic=.10,roic6=.10),
 scenario('financial_asset_uncertainty',initial={**START,'cash':START['cash']-.917995}),
 scenario('mother_cash_low',initial={**START,'mother_cash':5.0}),
 scenario('asset_release_5years',release_years=5),
 scenario('asset_release_15years',release_years=15),
 scenario('minor_financial_zero',initial={**START,'minor_cash':0}),
 scenario('minor_financial_all_book_equity',initial={**START,'minor_cash':.35504825852}),
 scenario('minor_profit_3pct',minority=.03),
 scenario('other_reserve_budget_high',other_reserve_cap=2.4),
 scenario('other_reserve_budget_low',other_reserve_cap=.6),
 scenario('grant_budget_high',grant=[.4,.4,.4,0,0]),
 scenario('grant_budget_low',grant=[.15,.15,.15,0,0]),
 scenario('mother_cash_high',initial={**START,'mother_cash':8.0}),
 scenario('cash_reserve_low',need_ratio=.075),
 scenario('cash_reserve_high',need_ratio=.12)]
 return {p['label']:run(p) for p in scenarios}

def test():
 # A perpetuity of 1, zero growth: five explicit years plus terminal all use exact production chain.
 ev,cfs,tv=continuation(1,0,.2,0,.2,.1)
 assert abs(ev-10)<1e-12 and cfs==[1]*5 and tv==10
 # No operating growth, reinvestment or finance; initial cash10, dividend .4 of earnings1;
 # mother earns1 and pays .4, group retains .6 each year. Final op=10, cash13: total23.
 p=scenario('hand',grant=[0]*5,revenue=[10]*5,margin=[.1]*5,tax=0,da=[0]*5,capex=[0]*5,wc=[0]*5,need_ratio=0,cash_yield=0,debt_rate=0,payout=.4,mother_np_fraction=1,mother_fcf_fraction=1,upstream_fraction=0,mother_injection=0,mother_need=0,repays=[0]*5,buybacks=[0]*5,growth6=0,g=0,rates=[.1,.1],minority=0,shares=1,release_years=1,initial=dict(cash=10,debt=0,mother_cash=10,mother_profit=10,reserve=.5,minor_cash=0,need=0))
 x=run(p);assert abs(x['rows'][-1]['cash_end']-13)<1e-12
 expected=sum(.4/1.1**i for i in range(1,6))+(10+13/1.1)/1.1**5
 assert abs(x['valuation'][0]['value']-expected)<1e-12
 return dict(perpetuity=ev,cash13_terminal21_818_value=expected,passed=True)
if __name__=='__main__':
 print(json.dumps(dict(units='CNY billion; shares billion',test=test(),scenarios=all_results()),ensure_ascii=False,indent=2))
