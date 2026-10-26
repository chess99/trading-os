"""Supor; CNY billion and billion shares; no market price input. Python standard library."""
import json, copy, math
from pathlib import Path
CUTOFF='2026-10-26T06:00:00+00:00'
# Fully diluted forecast uses outstanding option notices; see source-assumptions.md.
BASE=dict(dom=[16*(1.025)**i for i in range(5)],exp=[7*(1.02)**i for i in range(5)],dm=[.095]*5,em=[.047]*5,capex=[.24]*5,da=[.16]*5,wc=[.06]*5,payout=.85,upstream=.90,receipt=.90,settlement=[.15]*5,opening_excess=1.60142209873-.01786188461+.0004462727,opening_parent=.50,parent_ur=1.093300754,parent_reserve=.330789524,sub_reserve_rate=.10,parent_np_ratio=.022,finance_yield=.02,debt_rate=.05,shares=.796964626,issuance=[.00102317,.0010115,.0010345,.0005215,0],issue_cash=[(.000480780*36.49+.000542390*37.89),(.000498500*37.89+.000513000*38.82),(.000513000*38.82+.000521500*31.21),(.000521500*31.21),0],options=True,terminal_roic=.25)
# Options are conditional budget, never assumed completed as of cutoff.
def forecast(a):
    p=a['opening_parent'];s=a['opening_excess']-p;ur=a['parent_ur'];res=a['parent_reserve'];ic=2.451173958;rec=0.;subur=0.;debt=0.;equity=5.459076363+.0004462727;shares=a['shares'];rows=[]
    for i in range(5):
        start=p+s;olddebt=debt; oldrec=rec
        op=a['dom'][i]*a['dm'][i]+a['exp'][i]*a['em'][i]
        finance=start*a['finance_yield']-debt*a['debt_rate']+a.get('restricted_interest',0.)
        profit=op+finance
        retain=a['capex'][i]-a['da'][i]+a['wc'][i]
        fcf=profit-retain
        parent_profit=op*a['parent_np_ratio']+p*a['finance_yield']
        sub_profit=profit-parent_profit
        # Statutory reserves not presumed distributable. Subs declare only current earned reserves.
        sub_available=max(0,sub_profit)*(1-a['sub_reserve_rate'])
        declaration=sub_available*a['upstream']
        subur+=sub_available-declaration
        cash_receipt=oldrec+declaration*a['receipt'];rec=declaration*(1-a['receipt'])
        parent_cf=parent_profit-retain*a['parent_np_ratio']
        sub_cf=fcf-parent_cf
        issue=a['issuance'][i] if a['options'] else 0.;proceeds=a['issue_cash'][i] if a['options'] else 0.;shares+=issue
        # Parent pays subsidiaries genuine intercompany obligations; group cash unchanged.
        settle=min(ic,a['settlement'][i]);ic-=settle
        p+=parent_cf+cash_receipt+proceeds-settle;s+=sub_cf-cash_receipt+settle
        legalprofit=parent_profit+declaration
        reserve=min(max(0,legalprofit)*.10,max(0,shares*.5-res));res+=reserve
        ur+=legalprofit-reserve
        # No debt-financed dividends. If operating cash itself fails, borrow and pay financing cost next year.
        borrow=max(0,-(p+s));debt+=borrow;s+=borrow
        div=max(0,min(profit*a['payout'],ur,p,p+s))
        p-=div;ur-=div;equity+=profit+proceeds-div
        assert p>=-1e-9 and s>=-1e-9 and ur>=-1e-9
        assert abs((p+s)-(start+fcf+proceeds-div+borrow))<1e-8
        assert abs(cash_receipt+rec-oldrec-declaration)<1e-8
        rows.append(dict(year=i+1,dom=a['dom'][i],export=a['exp'][i],operating_profit=op,financial_profit=finance,common_profit=profit,da=a['da'][i],capex=a['capex'][i],wc=a['wc'][i],fcf=fcf,subs_profit=sub_profit,subs_declaration=declaration,subs_legal_retention=subur,parent_own_profit=parent_profit,parent_profit=legalprofit,parent_reserve=res,parent_ur=ur,dividend=div,dps=div/shares,parent_cash=p,subs_cash=s,upstream_receipt=cash_receipt,dividend_receivable=rec,intercompany_payable=ic,settlement=settle,issuance=issue,issue_cash=proceeds,shares=shares,debt=debt,common_equity=equity,excess_cash=p+s))
    return rows

def valuation(rows,k,g,roic):
    r=rows[-1]; # terminal capital retention explicitly g/ROIC; no financial interest capitalization
    steady_fcf=r['operating_profit']*(1+g)*(1-g/roic)
    business=steady_fcf/(k-g)
    terminal=(business+r['excess_cash']-r['debt'])/r['shares']
    divpv=sum(x['dps']/(1+k)**x['year'] for x in rows)
    tvpv=terminal/(1+k)**5
    return dict(k=k,g=g,roic=roic,terminal_business=business,terminal_fcf=steady_fcf,terminal_per_share=terminal,current_per_share=divpv+tvpv,terminal_pv_ratio=tvpv/(divpv+tvpv))

def run():
    cases={'base':BASE}
    cyc=copy.deepcopy(BASE);cyc.update(dom=[14.8,15.5]+BASE['dom'][2:],exp=[6.2,6.5]+BASE['exp'][2:],dm=[.088,.092]+[.095]*3,em=[.035,.04]+[.047]*3,wc=[.30,.15,-.15,.06,.06],receipt=.65,settlement=[.40,.15,.15,.15,.15]);cases['cycle']=cyc
    bear=copy.deepcopy(BASE);bear.update(dom=[14.5*(.99)**i for i in range(5)],exp=[5.8*(.97)**i for i in range(5)],dm=[.07]*5,em=[.025]*5,capex=[.28]*5,wc=[.2,.15,.10,.1,.1],receipt=.60,upstream=.65,settlement=[.6,.3,.3,.3,.3],options=False,terminal_roic=.15);cases['structural']=bear
    bull=copy.deepcopy(BASE);bull.update(dom=[16.2*(1.04)**i for i in range(5)],exp=[7.3*(1.04)**i for i in range(5)],dm=[.10]*5,em=[.06]*5,capex=[.30]*5,wc=[.10]*5,receipt=.95);cases['upside']=bull
    result={'information_cutoff':CUTOFF,'units':'CNY billion; billion shares; per-share CNY','cases':{}}
    for name,a in cases.items():
        rows=forecast(a);params=[(.095,.015),(.085,.02)] if name!='structural' else [(.105,0),(.095,.005)]
        vals=[valuation(rows,k,g,a['terminal_roic']) for k,g in params]
        result['cases'][name]={'assumptions':a,'rows':rows,'valuations':vals}
    r=result['cases']['base']['rows'];first=r[0]
    # auxiliary normalized cash earnings multiple: includes reinvestment, removes financial income.
    result['auxiliary']={'method':'normalized operating owner-cash multiple plus opening surplus','low':((first['operating_profit']-.14)*13+BASE['opening_excess'])/.800555296,'high':((first['operating_profit']-.14)*16+BASE['opening_excess'])/.800555296}
    sens=copy.deepcopy(BASE);sens['dm']=[x-.01 for x in BASE['dm']];rr=forecast(sens)
    result['sensitivity_domestic_margin_minus_1pp']=[valuation(rr,k,g,.25) for k,g in [(.095,.015),(.085,.02)]]
    no=copy.deepcopy(BASE);no['options']=False;rr=forecast(no);result['no_option_exercise']=[valuation(rr,k,g,.25) for k,g in [(.095,.015),(.085,.02)]]
    result['terminal_cash_realization_delay_3years']=[dict(k=k,g=g,current_per_share=valuation(r,k,g,.25)['current_per_share'] - r[-1]['excess_cash']/r[-1]['shares']*(1-(1.02/(1+k))**3)/(1+k)**5) for k,g in [(.095,.015),(.085,.02)]]
    tmp=copy.deepcopy(BASE);tmp['opening_parent']=0.;zr=forecast(tmp)
    result['parent_opening_extra_cash_zero']={'rows':zr,'valuations':[valuation(zr,k,g,.25) for k,g in [(.095,.015),(.085,.02)]]}
    # Existing procurement-settlement diagnostic: pay Q3 operating acceptances and
    # release only collateral independently identified in H1. Discount borrowing is separate.
    switch=copy.deepcopy(BASE);switch['wc'][2]+=1.5776-(.770+.09891+.256443)
    sw=forecast(switch)
    result['existing_acceptance_settlement_switch_year3']={'net_extra_cash_need':1.5776-(.770+.09891+.256443),'rows':sw,'valuations':[valuation(sw,k,g,.25) for k,g in [(.095,.015),(.085,.02)]]}
    ri=copy.deepcopy(BASE);ri['restricted_interest']=.770*.02;rr=forecast(ri)
    result['restricted_CD_interest_2pct']={'annual_net_interest':.770*.02,'rows':rr,'valuations':[valuation(rr,k,g,.25) for k,g in [(.095,.015),(.085,.02)]]}
    result['terminal_roic_15pct']=[valuation(r,k,g,.15) for k,g in [(.095,.015),(.085,.02)]]
    return result

def tests():
    # Hand-calculable same official forecast + valuation chain: op=1, no reinvestment,
    # no subs cash, no interest, no issuance; each year div=1, end cash=0, k=.1 g=0 => V=10.
    a=copy.deepcopy(BASE);a.update(dom=[1]*5,exp=[0]*5,dm=[1]*5,em=[0]*5,capex=[0]*5,da=[0]*5,wc=[0]*5,payout=1,upstream=1,receipt=1,settlement=[0]*5,opening_excess=0,opening_parent=0,parent_ur=100,parent_reserve=.5,sub_reserve_rate=0,parent_np_ratio=1,finance_yield=0,shares=1,options=False)
    rr=forecast(a);v=valuation(rr,.1,0,.25)
    assert all(abs(x['dps']-1)<1e-12 for x in rr)
    assert abs(v['current_per_share']-10)<1e-10
    assert all(x['excess_cash']==0 for x in rr)
    # Same chain legal cash constraint: no subsidiary receipts first period => payout limited by parent.
    a['parent_np_ratio']=0;a['receipt']=0;a['parent_ur']=0
    rr=forecast(a);assert rr[0]['dps']==0 and abs(rr[1]['dps']-1)<1e-12
    return {'hand_case_value':v['current_per_share'],'hand_expected':10,'cash_and_legal_delay_test':'passed'}
if __name__=='__main__':
    o=run();o['tests']=tests();Path(__file__).with_name('2026-Q3-output.json').write_text(json.dumps(o,ensure_ascii=False,indent=2));print(json.dumps({n:[v['current_per_share'] for v in c['valuations']] for n,c in o['cases'].items()}));print(o['auxiliary'])
