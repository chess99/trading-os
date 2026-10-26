#!/usr/bin/env python3
"""CNY billion, shares billion. Standalone deterministic shareholder cash model."""
import json, math
from pathlib import Path
from copy import deepcopy
SHARES=15.822199875
DILUTION=.001906
EXERCISE=23.63
INITIAL={'sec_equity':84.0,'other_equity':18.39849091709,'sec_required':80.,'other_required':13.,'sec_up':31.,'parent_up':15.18415647965,'sec_stat':3.81206356153,'parent_stat':2.24775334314,'parent_cash':3.3,'parent_receivable':1.5,'other_sub_equity':2.,'other_sub_required':1.8,'other_sub_up':.8,'other_sub_paid_capital':.4,'other_sub_stat':.15}
BASE={'sec_profit':10.8,'other_profit':3.4,'growth':.04,'mature_growth':.03,'cash_yield':.015,'release_start':6,'release_fraction':.12,'tax_reset':True,'funding_spread':0.,'capital_multiplier':1.,'profit_multiplier':1.,'upstream_delay':0,'parent_extra_payment':0.,'zero_dividend':False,'collection_delay':0.}
HISTORY=[
[2021,13.09432064824,8.55292769606,8.44030376619,8.97425918175,44.04023656654,185.02025399391,.2211],
[2022,12.48557644196,8.50946123333,8.20446156837,1.27746589539,65.16466322324,211.88073016465,.1440],
[2023,11.08143928237,8.19346927799,7.86159896625,-3.13772469098,71.96286055982,239.57832055216,.1194],
[2024,11.60434309016,9.61012074364,9.25322890681,44.58787289143,80.72709052263,306.36935734730,.1264],
[2025,16.06774103951,12.08459494722,11.65388675489,-10.22224564514,91.87547095531,392.93374497620,.1403]]
def legal_reserve(profit,opening_retained,rate,cap_remaining=float('inf')):
    return min(max(0.,cap_remaining),max(0.,profit+min(0.,opening_retained))*rate)

def payment(want,cash,profit):
    return max(0.,min(want,cash,profit))
def step(st,t,cfg,sec_oper,other_oper):
    s=deepcopy(st); old=deepcopy(st)
    growth=cfg['growth'] if t<=5 else cfg['mature_growth']
    ks=s['sec_required']*(1+growth)*(cfg['capital_multiplier'] if t==1 else 1)
    ko=s['other_required']*(1+growth)
    sec_interest=max(0,s['sec_equity']-s['sec_required'])*cfg['cash_yield']
    oth_interest=max(0,s['other_equity']-s['other_required'])*cfg['cash_yield']
    activity_scale=ks/(80*cfg['capital_multiplier'])
    gross_assets=250*activity_scale
    funded_debt=gross_assets-ks
    baseline_debt=170*activity_scale
    funding=(funded_debt*(.018+cfg['funding_spread'])-baseline_debt*.018)*(.75 if cfg['tax_reset'] and t>=5 else .83)
    ns=sec_oper+sec_interest-funding; no=other_oper+oth_interest
    statutory=legal_reserve(ns,s['sec_up'],.1,6.35-s['sec_stat'])
    sec_reserve=legal_reserve(ns,s['sec_up'],.2)+statutory;s['sec_stat']+=statutory
    s['sec_up']+=ns-sec_reserve
    cash_sec=s['sec_equity']+ns-ks
    desired=.2*max(0,ns) if t<cfg['release_start'] else max(0,ns-(ks-s['sec_required']))+cfg['release_fraction']*max(0,s['sec_equity']-s['sec_required'])
    phase=min(1.,max(0.,(t-cfg['release_start']+1)/10.))
    if t>=cfg['release_start']: desired=.2*max(0,ns)+phase*(desired-.2*max(0,ns))
    if cfg['upstream_delay']>=t: desired=0
    up=payment(desired,cash_sec,s['sec_up'])
    sec_short=max(0,-cash_sec)
    s['sec_equity']+=ns-up;s['sec_up']-=up
    # Parent/nonsecurities operating profit is after all subsidiary technical charges;
    # intercompany dividend changes legal parent profit only, never group earnings.
    sub_np=other_oper*(.3/3.4)
    own_np=no-sub_np
    sub_k=s['other_sub_required']*(1+growth)
    sub_reserve=legal_reserve(sub_np,s['other_sub_up'],.1,.5*s['other_sub_paid_capital']-s['other_sub_stat'])
    s['other_sub_stat']+=sub_reserve
    s['other_sub_up']+=sub_np-sub_reserve
    sub_up=payment(max(0,sub_np-(sub_k-s['other_sub_required'])),s['other_sub_equity']+sub_np-sub_k,s['other_sub_up'])
    s['other_sub_up']-=sub_up;s['other_sub_equity']+=sub_np-sub_up
    sub_dk=sub_k-s['other_sub_required'];s['other_sub_required']=sub_k
    parent_profit=own_np+sub_up+up
    pstat=legal_reserve(parent_profit,s['parent_up'],.1,(SHARES+(DILUTION if t>=1 else 0))*.5-s['parent_stat'])
    s['parent_stat']+=pstat;s['parent_up']+=parent_profit-pstat
    exercise=DILUTION*EXERCISE if t==1 else 0
    rec=0. # Existing intercompany loan remains invested; no assumed principal receipt
    s['parent_receivable']-=rec
    parent_cash=s['parent_cash']+own_np+sub_up+up-(ko-s['other_required']-sub_dk)+rec+exercise-(cfg['parent_extra_payment'] if t==1 else 0)
    desired_ext=([1.8,2.2,2.7,3.2,3.8][t-1] if t<=5 else max(0,no+up-(ko-s['other_required']))+cfg['release_fraction']*max(0,s['other_equity']-s['other_required']))
    if t>5: desired_ext=(3.8/16.311799145839785)*(ns+no)+phase*(desired_ext-(3.8/16.311799145839785)*(ns+no))
    if cfg['zero_dividend']:desired_ext=0
    parent_cash-=cfg['collection_delay'] if t==1 else 0
    ext=payment(desired_ext,parent_cash-1.,s['parent_up'])
    s['parent_receivable']+=cfg['collection_delay'] if t==1 else 0
    s['parent_cash']=parent_cash-ext;s['parent_up']-=ext
    s['other_equity']+=no+up+exercise-ext-(cfg['parent_extra_payment'] if t==1 else 0)
    s['sec_required']=ks;s['other_required']=ko
    haircut=3.44114525163*activity_scale;core=s['sec_equity']-haircut
    risk=14*(ks/80); exposure=gross_assets
    deficit=max(sec_short,1-s['parent_cash'],2*risk-core,.16*exposure-core,0)
    expected=old['sec_equity']+old['other_equity']+ns+no+exercise-ext-(cfg['parent_extra_payment'] if t==1 else 0)
    assert abs(s['sec_equity']+s['other_equity']-expected)<1e-8
    assert up<=max(0,old['sec_up']+ns-sec_reserve)+1e-8
    row={'year':2026+t,'sec_operating_profit':sec_oper,'other_operating_profit':other_oper,'sec_surplus_income':sec_interest,'other_surplus_income':oth_interest,'incremental_financing_cost_after_tax':funding,'group_profit':ns+no,'sec_reserve_add':sec_reserve,'parent_stat_add':pstat,'sec_upstream_dividend':up,'other_sub_profit':sub_np,'other_sub_reserve_add':sub_reserve,'other_sub_upstream_dividend':sub_up,'parent_direct_profit':own_np,'parent_legal_profit':parent_profit,'ordinary_dividend':ext,'distribution_per_share':ext/(SHARES+DILUTION),'exercise_cash':exercise,'receivable_collection':rec,'sec_external_and_internal_funding':funded_debt,'sec_operating_gross_assets':gross_assets,'sec_surplus_assets':s['sec_equity']-ks,'sec_base_funding_cost':funded_debt*.018,'capital_funding_gap':deficit,'core_net_capital':core,'risk_capital_requirement':risk,'risk_coverage':core/risk,'capital_leverage':core/exposure,**s}
    return s,row

def path(overrides=None,years=40):
    c=BASE| (overrides or {});s=deepcopy(INITIAL);rows=[];sec=c['sec_profit'];oth=c['other_profit']
    for k in ('other_sub_paid_capital','other_sub_stat'):
        if k in c:s[k]=c[k]
    for t in range(1,years+1):
        if t>1:
            growth=c['growth'] if t<=5 else c['mature_growth'];sec*=1+growth;oth*=1+growth
        sp=sec;op=oth
        if c['tax_reset'] and t>=5:sp*=.75/.83
        sp*=c['profit_multiplier'];op*=c['profit_multiplier']
        if c.get('cyclical') and t<=2:sp*=.65;op*=.75
        if c.get('cyclical') and t==3:sp*=.85;op*=.9
        if c.get('structural'):
            sp*=.97**min(t-1,5);op*=.98**min(t-1,5)
        s,row=step(s,t,c,sp,op);rows.append(row)
        if row['capital_funding_gap']>1e-8:return {'feasible':False,'failure_year':2026+t,'rows':rows,'terminal':None}
    # Continue the identical legal/funding state; no liquidation of required capital
    # or independently chosen payout ratio is introduced at a horizon boundary.
    return {'feasible':True,'rows':rows,'terminal_state':s}

def value(p,r,g=.03):
    if not p['feasible']:return None
    rows=p['rows'];n=len(rows)
    # Finite-horizon Gordon approximation, not an exact finite-year growth claim.
    # Full 120/160/200 recurrences below check value and mature-state convergence.
    last=rows[-1]; terminal_distribution=last['ordinary_dividend']*(1+g)
    tv=terminal_distribution/(r-g)/(SHARES+DILUTION)
    dividends=[x['distribution_per_share'] for x in rows]
    pv=sum(d/(1+r)**(i+1) for i,d in enumerate(dividends))+tv/(1+r)**n
    tv5=sum(dividends[i]/(1+r)**(i-4) for i in range(5,n))+tv/(1+r)**(n-5)
    assert abs(pv-(sum(dividends[i]/(1+r)**(i+1) for i in range(5))+tv5/(1+r)**5))<1e-8
    return {'discount_rate':r,'current_value':pv,'year5_value':tv5,'year5_terminal_pv_share':tv5/(1+r)**5/pv,'tail_year':n,'tail_value':tv,'tail_pv_share':tv/(1+r)**n/pv}

def runoff(r,franchise_life=15,erosion=.04):
    # Economically distinct zero-new-acquisition, run-off business: shrinking clients,
    # 60bn securities capital +10bn other capital and 29.4524bn realizable excess.
    # All balance sheet investment income is excluded from franchise earnings.
    equity=102.39849091709-2.94609332017+DILUTION*EXERCISE
    required=70.;excess=equity-required;franchise=8.7
    rows=[];v=0.;liquid=excess
    for t in range(1,franchise_life+1):
        k0=required;required=70.*(1-t/franchise_life)
        client_revenue=16.2*(1-erosion)**(t-1)
        maintenance_cost=5.69*(1-erosion*.5)**(t-1)
        client_profit=(client_revenue-maintenance_cost)*(.83 if t<5 else .75)
        profit=client_profit+.025*k0
        excess_release=excess/3 if t<=3 else 0.
        excess_income=liquid*.015
        exit_cost=2. if t==franchise_life else 0.
        distribution=profit+k0-required+excess_release+excess_income-exit_cost
        liquid-=excess_release
        v+=distribution/(1+r)**t
        rows.append({'year':t,'client_revenue':client_revenue,'maintenance_cost':maintenance_cost,'client_earnings':client_profit,'capital_income':.025*k0,'released_net_capital':k0-required,'ending_required_capital':required,'excess_release':excess_release,'excess_income':excess_income,'exit_cost':exit_cost,'economic_cash':distribution})
    return {'value_per_share':v/(SHARES+DILUTION),'realizable_net_assets':equity,'initial_excess':excess,'client_revenue0':16.2,'operating_cost0':5.69,'client_tax_rate_first4':.17,'client_tax_rate_year5_on':.25,'asset_capital_yield_after_tax':.025,'surplus_yield_after_tax':.015,'closing_cost':2.,'rows':rows,'note':'Alternative orderly run-off economic benchmark; not proposed or committed shareholder distributions. Debt/client money already netted in book equity; goodwill removed; no continuing terminal or duplicated capital income.'}

def tests():
    assert payment(3,2,4)==2 and payment(3,4,1)==1 and payment(3,-1,4)==0
    s={'sec_equity':10.,'other_equity':10.,'sec_required':10.,'other_required':10.,'sec_up':10.,'parent_up':10.,'sec_stat':6.35,'parent_stat':8.,'parent_cash':5.,'parent_receivable':0.,'other_sub_equity':2.,'other_sub_required':1.8,'other_sub_up':.8,'other_sub_paid_capital':.4,'other_sub_stat':.15}
    c=BASE|{'growth':0.,'mature_growth':0.,'cash_yield':0.,'release_start':6,'tax_reset':False}
    out,row=step(s,2,c,2.,1.)
    # sec reserve .4; up .4; parent profit1.4; dividend2.2 => Etotal20.8, cash4.2
    assert abs(row['sec_upstream_dividend']-.4)<1e-12
    assert abs(out['sec_equity']-11.6)<1e-12
    assert abs(out['other_equity']-9.2)<1e-12
    assert abs(out['parent_cash']-4.2)<1e-12
    assert abs(out['sec_up']-11.2)<1e-12
    assert abs(out['parent_up']-9.2)<1e-12
    neg=deepcopy(s);neg['sec_up']=-3;neg['sec_stat']=0;neg['parent_up']=-3;neg['parent_stat']=0;neg['other_sub_up']=-2
    z,zr=step(neg,2,c,2.,1.)
    assert zr['sec_reserve_add']==0 # all three reserves follow issuer loss-repair policy
    assert z['sec_stat']==0 and zr['parent_stat_add']==0 and zr['other_sub_reserve_add']==0
    assert zr['sec_upstream_dividend']==0 and zr['other_sub_upstream_dividend']==0 and zr['ordinary_dividend']==0
    zz,zzr=step(neg,2,c,5.,1.)
    assert abs(zz['sec_stat']-.2)<1e-12 and abs(zzr['sec_reserve_add']-.6)<1e-12
    capped=deepcopy(s);capped['other_sub_stat']=.195
    co,cr=step(capped,2,c,2.,1.)
    assert abs(cr['other_sub_reserve_add']-.005)<1e-12 and abs(co['other_sub_stat']-.2)<1e-12
    co2,cr2=step(co,3,c,2.,1.)
    assert cr2['other_sub_reserve_add']==0
    # legally unpayable earnings, zero dividend cannot cure prepayment liquidity shock
    fail=path({'zero_dividend':True,'upstream_delay':2,'parent_extra_payment':3.314,'collection_delay':3.4})
    assert not fail['feasible'] and fail['rows'][0]['ordinary_dividend']==0
    return {'formal_step_hand_case':'pass','negative_retained_profit_hand_case':'pass','other_sub_statutory_cap_hand_case':'pass','zero_distribution_funding_failure':fail}

def main():
    p=path(years=120)
    scenarios={
    'cyclical_2027_2029':{'cyclical':True},
    'structural_2027_on':{'structural':True,'profit_multiplier':.8,'growth':.01,'mature_growth':.01,'capital_multiplier':1.08,'funding_spread':.005},
    'optimistic_2027_on':{'profit_multiplier':1.12,'growth':.06,'mature_growth':.03},
    'capital_10pct_2027':{'capital_multiplier':1.10},
    'funding_plus100bp_2027_on':{'funding_spread':.01},
    'upstream_delayed_two_years':{'upstream_delay':2},
    'maturity_release_delayed_to2037':{'release_start':11},
    'no_tax_expiry_after2030':{'tax_reset':False},
    'other_sub_stat_already_full_2027':{'other_sub_paid_capital':.338,'other_sub_stat':.169},
    'other_sub_stat_large_unfunded_2027':{'other_sub_paid_capital':.8,'other_sub_stat':0.}}
    ss={}
    for name,changes in scenarios.items():
        q=path(changes,120);ss[name]={'changes':changes,'feasible':q['feasible'],'rows':q['rows'],'valuation':value(q,.105,changes.get('mature_growth',.03)),'failure_year':q.get('failure_year')}
    convergence={}
    for n in (120,160,200):
        q=path(years=n);last=q['rows'][-1];prev=q['rows'][-2]
        rates={k:last[k]/prev[k]-1 for k in ('ordinary_dividend','group_profit','sec_required','other_required','sec_equity','other_equity')}
        convergence[str(n)]={'path':q,'endpoints':{'low':value(q,.115),'high':value(q,.10)},'last_year_growth':rates,'max_growth_gap':max(abs(v-.03) for v in rates.values())}
    assert convergence['200']['max_growth_gap']<2e-5
    assert abs(convergence['200']['last_year_growth']['ordinary_dividend']-.03)<4e-7
    assert convergence['200']['max_growth_gap']<convergence['160']['max_growth_gap']<convergence['120']['max_growth_gap']
    for side in ('low','high'):
        assert abs(convergence['120']['endpoints'][side]['current_value']-convergence['200']['endpoints'][side]['current_value'])<1e-5
    output={'convergence':convergence,'unit':'CNY billion; shares billion; per share CNY','as_of':'2026-10-26','historical_columns':['year','revenue','parent_net_income','adjusted_net_income','operating_cashflow','parent_equity','assets','roe'],'historical':HISTORY,'normalization_bridge':{'brokerage_net_fee':8.4,'other_security_fee':3.2,'net_interest_after_baseline_funding':4.2,'trading_investment_net_income':2.4,'fund_platform_revenue':4.1,'data_other_revenue':.5,'all_operating_and_credit_cost':5.69,'effective_tax':.17,'rounded_net_operating_profit':14.2,'sec_profit_after_internal_service_charge':10.8,'other_group_profit':3.4},'initial':INITIAL,'assumptions':BASE,'shares':{'issued':SHARES,'remaining_awards_assumed_vested':DILUTION,'fully_diluted':SHARES+DILUTION,'subscription_price':EXERCISE},'base':p,'core_endpoints':{'low':value(p,.115),'high':value(p,.10)},'central':value(p,.105),'auxiliary_runoff':{'low':runoff(.115,12,.06),'high':runoff(.10,18,.03)},'scenarios':ss,'tests':tests()}
    Path(__file__).with_name('2026-Q3-output.json').write_text(json.dumps(output,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')
    print(json.dumps({'core':output['core_endpoints'],'first5':[(x['year'],x['distribution_per_share'],x['group_profit']) for x in p['rows'][:5]],'aux':[output['auxiliary_runoff'][k]['value_per_share'] for k in ('low','high')],'scenarios':{k:v['valuation'] for k,v in ss.items()}},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
