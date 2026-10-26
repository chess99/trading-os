"""Literal re-entry, no imports from main model, separate recurrence implementation."""
import json
from pathlib import Path
# Literal transcription from original Q3/H1 tables (CNY):
q3_revenue=15559791853.09;q3_profit=11907023170.67;q3_adjusted=11463112307.40
h1_revenue=10505339283.68;h1_profit=8064281453.11;h1_adjusted=7726695676.62
q1_revenue=5031027125.40;q1_profit=3737779855.92
q3_equity=102398490917.09;shares=15822199875
sec_h1_assets=426403159812.34;sec_h1_debt=345767521999.73
sec_h1_core=77194492560.98;sec_h1_riskadjustment=3441145251.63
assert abs(sec_h1_assets-sec_h1_debt-sec_h1_core-sec_h1_riskadjustment)<.0001
S=15.824105875

def independent(rate,extra_rate=0,capital=1,delay=0,start=6,tax=True,years=120,subcapital=.4,substat=.15):
    a=84.;b=18.39849091709;ka=80.;kb=13.;ua=31.;ub=15.18415647965;ra=3.81206356153;rb=2.24775334314;cash=3.3;sube=2.;subk=1.8;subu=.8
    dd=[];states=[]
    for year in range(1,years+1):
        multiplier=1.04**min(year-1,4)*1.03**max(0,year-5)
        operatinga=10.8*multiplier*(.75/.83 if tax and year>=5 else 1)
        operatingb=3.4*multiplier
        growth=.04 if year<=5 else .03
        nextka=ka*(1+growth)*(capital if year==1 else 1);nextkb=kb*(1+growth)
        scale=nextka/(80*capital);debt=250*scale-nextka
        delta_finance=(debt*(.018+extra_rate)-170*scale*.018)*(.75 if tax and year>=5 else .83)
        pa=operatinga+max(0,a-ka)*.015-delta_finance
        pb=operatingb+max(0,b-kb)*.015
        riska=.2*max(0,pa+min(0,ua));deltara=min(max(0,6.35-ra),.1*max(0,pa+min(0,ua)));ra+=deltara
        ua+=pa-riska-deltara
        ramp=min(1,max(0,(year-start+1)/10))
        target=.2*max(0,pa)
        if year>=start:target+=(max(0,pa-nextka+ka)+.12*max(0,a-ka)-target)*ramp
        if year<=delay:target=0
        upstream=max(0,min(target,a+pa-nextka,ua))
        ua-=upstream;a+=pa-upstream
        subp=operatingb*.3/3.4;subnext=subk*(1+growth);subreserve=min(max(0,subcapital*.5-substat),.1*max(0,subp+min(0,subu)));substat+=subreserve;subu+=subp-subreserve
        subpay=max(0,min(max(0,subp-subnext+subk),sube+subp-subnext,subu));subu-=subpay;sube+=subp-subpay
        pparent=pb-subp+subpay+upstream;drb=min(max(0,15.824105875*.5-rb),.1*max(0,pparent+min(0,ub)));rb+=drb;ub+=pparent-drb
        cash+=pparent-nextkb+kb+subnext-subk+(.001906*23.63 if year==1 else 0)
        if year<=5:wanted=[1.8,2.2,2.7,3.2,3.8][year-1]
        else:
            previous=.23296081417541978*(pa+pb) # overwritten by independently literal fraction below
            previous=3.8/16.311799145839785*(pa+pb)
            steady=max(0,pb+upstream-nextkb+kb)+.12*max(0,b-kb)
            wanted=previous+ramp*(steady-previous)
        dividend=max(0,min(wanted,cash-1,ub));ub-=dividend;cash-=dividend
        b+=pb+upstream+(.001906*23.63 if year==1 else 0)-dividend
        ka=nextka;kb=nextkb;subk=subnext
        dd.append(dividend/S);states.append((a,b,ua,ub,cash))
    residual=dd[-1]*1.03/(rate-.03)
    pv=sum(d/(1+rate)**(i+1) for i,d in enumerate(dd))+residual/(1+rate)**years
    v5=sum(dd[i]/(1+rate)**(i-4) for i in range(5,years))+residual/(1+rate)**(years-5)
    return {'pv':pv,'tv5':v5,'distributions':dd[:5],'year5_state':states[4],'all_states':states,'all_distributions':dd}

def run_off(rate,life,erosion):
    cash0=102.39849091709-2.94609332017+.001906*23.63-70
    total=0;liq=cash0
    for t in range(1,life+1):
        release=cash0/3 if t<=3 else 0
        total+=((16.2*(1-erosion)**(t-1)-5.69*(1-erosion*.5)**(t-1))*(.83 if t<5 else .75)+.025*70*(1-(t-1)/life)+70/life+release+liq*.015-(2 if t==life else 0))/(1+rate)**t
        liq-=release
    return total/S


ROOT=Path(__file__).resolve().parents[1]/'research/companies/CN/300059/models'

def test_eastmoney_literal_core_sensitivities_and_long_tail():
    a=json.loads((ROOT/'2026-Q3-output.json').read_text())
    for n in [120,160,200]:
        for label,r in [('low',.115),('high',.10)]:
            v=independent(r,years=n);q=a['convergence'][str(n)]
            assert abs(v['pv']-q['endpoints'][label]['current_value'])<1e-9
            assert abs(v['tv5']-q['endpoints'][label]['year5_value'])<1e-9
            for state,div,row in zip(v['all_states'],v['all_distributions'],q['path']['rows']):
                assert abs(div-row['distribution_per_share'])<1e-9
                for x,k in zip(state,['sec_equity','other_equity','sec_up','parent_up','parent_cash']):assert abs(x-row[k])<1e-7
    for name,args in [('funding_plus100bp_2027_on',{'extra_rate':.01}),('capital_10pct_2027',{'capital':1.1}),('upstream_delayed_two_years',{'delay':2}),('maturity_release_delayed_to2037',{'start':11}),('no_tax_expiry_after2030',{'tax':False}),('other_sub_stat_already_full_2027',{'subcapital':.338,'substat':.169}),('other_sub_stat_large_unfunded_2027',{'subcapital':.8,'substat':0})]:
        v=independent(.105,**args);q=a['scenarios'][name]['valuation']
        assert abs(v['pv']-q['current_value'])<1e-9 and abs(v['tv5']-q['year5_value'])<1e-9
    for label,r,n,e in [('low',.115,12,.06),('high',.10,18,.03)]:assert abs(run_off(r,n,e)-a['auxiliary_runoff'][label]['value_per_share'])<1e-9

def test_eastmoney_actual_legal_cash_functions():
    import runpy
    m=runpy.run_path(str(ROOT/'2026-Q3.py'));m['tests']()
    a=json.loads((ROOT/'2026-Q3-output.json').read_text())
    assert a['base']['rows'][1]['other_sub_stat']==.2
    assert a['base']['rows'][2]['other_sub_reserve_add']==0
    assert not a['tests']['zero_distribution_funding_failure']['feasible']
    assert a['convergence']['200']['max_growth_gap']<2e-5
    for label in ['low','high']:
        assert abs(a['convergence']['120']['endpoints'][label]['current_value']-a['convergence']['200']['endpoints'][label]['current_value'])<1e-6
