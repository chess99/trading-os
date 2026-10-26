#!/usr/bin/env python3
"""600025, CNY bn, shares bn. Conditional diagnostics, NOT a complete equity valuation.
Public data cutoff 2026-10-26T14:00:00+08:00. No live price, IRR or trade rule.
Unresolved project net values X_0 and X_5 deliberately remain null.
"""
import json, math
from pathlib import Path
S=18.631094257
D=12.86153548252+7.60206886607+89.92829278035+5.03432504108+10.02803032770+1.04987728601
PD=.5445591529+3.76709300772+50.03871641483+5.03432504108+10.02803032770
PERP=16.217
FACT={"shares":S,"financial_debt_including_lease_and_accruals":D,"parent_debt":PD,
"cash_equivalents":3.72253673088,"cash_funds":4.73352182637,"parent_cce":.38992885011,
"ordinary_book_equity":89.26155561263-PERP,"nci_book":6.56759097069,
"financial_investments":3.40228742690+1.44209053814+.57035715058,
"parent_retained":23.90057410048,"parent_reserve":5.39638671312,
"q3_revenue":7.95814429781,"q3_np":3.17752803387,
"q3_cfo":15.66983217184-9.08736770639,
"q3_capex":11.15169156613-7.25137652878,
"ytd_fcf_before_finance":15.66983217184-11.15169156613,
"q3_gross_margin_ytd":1-8.68826681539/21.10552486504}
PROJECTS={"RM":{"budget":58.3815079,"cip":8.28299014527,"first_power":2033,"GW":2.6},
"GS":{"budget":50.40133460819,"cip":4.42357346965,"first_power":None,"GW_historical_plan":2.2},
"BDa":{"budget":23.4922659,"cip":3.44129553187,"first_power":None,"GW_historical_plan":1.5},
"GX_preparatory_scope":{"budget":3.38219,"cip":2.27377883062,"first_power":None,"GW_historical_plan":2.1}}
for p in PROJECTS.values():p['budget_less_cip']=p['budget']-p['cip']

# FY2025 pp97-102, consistent balance and operating-capital proxy; CNY bn.
D25=sum([11.40924837254,13.36558519994,7.0294920445,89.90696883939,3.01694575343,.87318375252])
D24=sum([14.25864183125,12.09108859132,5.02008013699,89.66633714127,2.,.49410830399])
C25=88.1147747291+D25-3.9426238849-3.35683954573-1.43219328755-.52407461678
C24=79.16849207242+D24-3.09311429674-3.2738657337-1.38959566006-.50212403955
EB25=10.82631114676+2.62526646359-.31135451079-.02195057723
EB24=10.38746541627+2.67467698169-.32528603306-.01006393738
FACT['capital_proxy_2024']=C24;FACT['capital_proxy_2025']=C25
FACT['operating_ebit_proxy_2024']=EB24;FACT['operating_ebit_proxy_2025']=EB25
FACT['roic_proxy_2025']=EB25*.85/((C25+C24)/2)
FACT['incremental_roic_proxy_2024_to_2025']=(EB25-EB24)*.85/(C25-C24)

def pv(cash,rate):return sum(v/(1+rate)**(i+1) for i,v in enumerate(cash))
def annuity(cash,rate,years):return cash*(1-(1+rate)**(-years))/rate if rate else cash*years

def mature(rate=.055,life=50,price=1.,water=1.,maintenance=4.,tax_after=.25):
    # 2027 annual proxy. No unbuilt station revenue; full current debt NOT allocated away.
    rows=[]
    for i in range(1,life+1):
        infl=1.005**(i-1)
        # Existing domestic/foreign assets together for 15y, foreign concessions then run off.
        runoff=max(0.,min(1.,(25-i)/10)) if i>15 else 1.
        revenue=(25.6*price*water+1.6*runoff)*infl
        cash_cost=(6.2*(.75+.25*water))*infl
        da=7.5*infl
        tax=.15 if i<=4 else tax_after
        ebit=revenue-cash_cost-da
        maintenance_cash=maintenance*infl
        fcf=ebit*(1-tax)+da-maintenance_cash
        # extra large replacement, not annual D&A simply labelled free cash
        if i in (20,40):fcf-=8*infl
        rows.append(dict(year=2026+i,revenue=revenue,ebit=ebit,nopat=ebit*(1-tax),da=da,maintenance=maintenance_cash,fcff=fcf))
    ev=pv([x['fcff'] for x in rows],rate)
    # non-operating earnings absent from EBIT; investments added only once.
    # NCI shown at finite-life cash value, not their book equity.
    nci=annuity(.8,.075,30)
    capital_creditor_ceiling=7.64707985906-.26956263829+.23835321232+.06437698640
    common_residual=ev-D-PERP+nci*0+(FACT['cash_equivalents']-2.0296755)+FACT['financial_investments']-nci-capital_creditor_ceiling
    return dict(ev=ev,conditional_common_residual=common_residual,conditional_residual_per_share=common_residual/S,
        nci_value=nci,capital_creditor_ceiling=capital_creditor_ceiling,
        after_year5_pv_share=pv([x['fcff'] for x in rows[5:]],rate)/(1+rate)**5/ev,rows=rows)

def rm(rate=.055,price=.425,remaining=36.71485985473,delay=0,volume=1.,downstream=.5):
    # RM 30yr evaluation; downstream=.5 is phased availability, NOT ownership haircut.
    # Internal compensation is not added to consolidated revenue a second time.
    first_full=2034+delay
    rows=[]
    for year in range(2027,first_full+30):
        capex=remaining/(first_full-2027) if year<first_full else 0.
        revenue=(11.281*.992*price/1.13+5.4*.22*downstream)*volume if year>=first_full else 0.
        da=44.6/45 if revenue else 0.
        cashcost=.7 if revenue else 0.
        # No assumed post-2030 regional preference extension; 3+3 holiday only diagnostic.
        age=year-first_full
        tax=0 if 0<=age<3 else (.125 if 3<=age<6 else .25)
        profit=max(0,revenue-cashcost-da)*(1-tax)
        fcf=profit+da-(.4 if revenue else 0)-capex
        rows.append(dict(year=year,capex=capex,revenue=revenue,da=da,nopat=profit,fcff=fcf))
    return dict(npv=pv([x['fcff'] for x in rows],rate),rows=rows,remaining_nonfinance_or_total_budget_proxy=remaining)

SCENARIOS={
'base':dict(water=[1]*5,price=1,cost=1,rate=.026,capex=[19,20,20,19,18],support=[4,4.5,4.5,4,3.5],payout=.45),
'cyclical':dict(water=[.85,.9,.96,1,1],price=1.01,cost=1,rate=.030,capex=[19,20,20,19,18],support=[4,4.5,4.5,4,3.5],payout=.45),
'structural':dict(water=[.9,.85,.85,.85,.85],price=.92,cost=1.1,rate=.035,capex=[19,20,20,19,18],support=[4,4.5,4.5,4,3.5],payout=.45),
'upside':dict(water=[1.04]*5,price=1.03,cost=1,rate=.024,capex=[20,21,21,20,19],support=[4.5,5,5,4.5,4],payout=.45)}

def funding_step(cash,profit,da,capex,distribution,target_cash,credit_limit):
    """Production waterfall: financing capped; distributions cut before uncovered gap."""
    available=cash+profit+da-capex-target_cash
    if available < -credit_limit-1e-10:
        raise ValueError(f"融资不可行：零股利资金缺口 {-available:.6f} 超过新增融资上限 {credit_limit:.6f}")
    actual=min(distribution,max(0,available+credit_limit))
    borrowing=max(-available+actual,0)
    repayment=max(available-actual,0)
    end=cash+profit+da-capex-actual+borrowing-repayment
    assert abs(end-target_cash)<1e-8
    return actual,borrowing-repayment,end

def financing(name):
    c=SCENARIOS[name]; pdebt=PD;sdebt=D-PD;pcash=FACT['parent_cce'];scash=FACT['cash_equivalents']-pcash
    reserve=FACT['parent_reserve']; retained=FACT['parent_retained'];subre=0.;receivable=.45110034756
    rows=[]
    for t in range(5):
        y=2027+t;f=1.005**t;water=c['water'][t];tax=.15 if y<=2030 else .25
        # 2025 direct/sub revenue and Q3 parent operating CF anchor this split.
        prevp,prevs=pdebt,sdebt
        prevpc,prevsc=pcash,scash
        prevret,prevreserve=retained,reserve
        pebit=(19.3*water*c['price']-4.9*c['cost']-5.3)*f
        sebit=(7.9*water*c['price']-1.3*c['cost']-2.2)*f
        pp=max(pebit-pdebt*c['rate'],0)*(1-tax)
        sp=max(sebit-sdebt*c['rate'],0)*(1-tax)
        nci_profit=.28*sp # weighted earnings share, not asserted legal project ownership
        common_np=pp+sp-nci_profit+.3-PERP*.025
        # operating sub upstream dividend only 30% of attributable current earnings;
        # other retained earnings and borrowing are not automatically distributable.
        declared=max(0,.30*(sp-nci_profit))
        old_receivable=receivable
        received=old_receivable+.8*declared
        receivable=.2*declared
        nci_paid=min(.5,nci_profit)
        # Construction envelope includes maintenance+old settlement+RM+other projects.
        # Parent-to-sub support is an internal financing flow, eliminated group-wide.
        pcap=4.0*f;scap=c['capex'][t]-pcap;support=c['support'][t]
        scash+=support
        subdist=received+nci_paid
        actual_sub,snet,scash=funding_step(scash,sp,2.2*f,scap,subdist,2.5,15.)
        # If sub cash cannot pay intended dividend, revise received/declared, not silently borrow unlimited.
        assert snet<=15.+1e-9 and abs(actual_sub-subdist)<1e-9
        sdebt+=snet
        statutory=pp+declared+.3
        statutory_reserve=min(max(statutory,0)*.10,max(S*.5-reserve,0))
        reserve+=statutory_reserve
        statutory_common=statutory-statutory_reserve-PERP*.025
        legal=max(0,retained+statutory_common)
        intended=min(max(common_np*c['payout'],0),legal)
        # Collection of old receivable affects CASH, not statutory profit.
        pcash+=received+.3-PERP*.025-support
        actual,pnet,pcash=funding_step(pcash,pp,5.3*f,pcap,intended,.6,5.)
        pdebt+=pnet;retained+=statutory_common-actual
        subre+=sp-nci_profit-declared
        assert retained>=-1e-8 and subre>=-1e-8
        # Cash conservation including all intercompany transfer eliminations and uncollected dividends.
        total_start=prevpc+prevsc
        total_end=pcash+scash
        group_np=pp+sp+.3-PERP*.025
        expected=total_start+group_np+7.5*f-c['capex'][t]-actual-nci_paid+pnet+snet
        assert abs(expected-total_end)<1e-8
        rows.append(dict(year=y,parent_ebit=pebit,subs_ebit=sebit,parent_direct_np=pp,subs_np=sp,
            common_earnings=common_np,statutory_profit=statutory,legal_reserve=statutory_reserve,parent_retained=retained,
            sub_dividend_declared=declared,sub_dividend_received=received,dividend_receivable=receivable,
            capital_envelope=c['capex'][t],parent_capex=pcap,subs_capex=scap,parent_support=support,rm_construction_reference=[5,6,6.5,7,7][t],rm_capital_reference=.3*[5,6,6.5,7,7][t],other_support_reference=support-.3*[5,6,6.5,7,7][t],
            distribution=actual,distribution_per_share=actual/S,parent_net_borrowing=pnet,subs_net_borrowing=snet,
            parent_debt=pdebt,group_debt=pdebt+sdebt,parent_cash=pcash,subs_cash=scash,nci_paid=nci_paid,
            reduced_distribution=intended-actual,unresolved_project_equity_value=None))
    return rows

def unknown_project_scale():
    # Historical 5.8GW planning scale only; not an adopted engineering forecast.
    out=[]
    for hours,tariff,cost,start in [(3000,.22,95,2037),(5000,.35,67.136,2033)]:
        rev=5.8*hours/1000*tariff
        annual_cf=rev*.65 # dimension test, not observed project economics
        v=annuity(annual_cf,.06,40)/(1.06)**(start-2027)-pv([cost/8]*8,.06)
        out.append(dict(hours=hours,net_tariff=tariff,remaining_cost=cost,start=start,annual_cf=annual_cf,npv=v,per_share=v/S))
    return out

def tests():
    assert abs(pv([110],.1)-100)<1e-10
    assert abs(annuity(10,.1,2)-(10/1.1+10/1.21))<1e-10
    # Calls actual production waterfall: 1+3+2-4-1=1, no borrowing.
    assert funding_step(1,3,2,4,1,1,10)==(1,0,1)
    # Same chain, cash short: distribution must fall from 4 to 2 with max credit 2.
    assert funding_step(1,3,2,6,4,0,2)==(2,2,0)
    # Zero dividends cannot cure 3 of funding need against only 2 of credit.
    try:
        funding_step(1,3,2,9,0,0,2)
    except ValueError as exc:
        assert '融资不可行' in str(exc)
    else:
        raise AssertionError('unfunded investment must not manufacture excess credit')
    return 'passed: pv, annuity, three financing-waterfall hand cases including infeasibility, group cash and legal reserves' 

def main():
    low=mature(.06,40,maintenance=4.5);high=mature(.05,60,maintenance=3.5)
    # Independent method: normal EBIT capitalized on a declining earnings life (no peer multiple).
    # Capitalization factors are finite annuity values, with depreciation-replacement spread explicit.
    cross=[]
    for r,n,maint in [(.06,40,4.5),(.05,60,3.5)]:
        nopat=13.5*.75
        ev=annuity(nopat+7.5-maint,r,n)
        residual=(ev-D-PERP+(FACT['cash_equivalents']-2.0296755)+FACT['financial_investments']-low['nci_value']-low['capital_creditor_ceiling'])/S
        cross.append(dict(rate=r,years=n,normal_nopat=nopat,fcff=nopat+7.5-maint,enterprise_value=ev,conditional_residual_per_share=residual))
    normalized_common=(13.5-D*.026)*.75-PERP*.025-.8+.3
    earnings_capacity=[dict(equity_cost=k,normal_common_earnings=normalized_common,per_share=(normalized_common/k-low['capital_creditor_ceiling'])/S) for k in [.08,.07]]
    result=dict(earnings_capacity_diagnostic=earnings_capacity,cutoff='2026-10-26T14:00:00+08:00',unit='CNY billion',facts=FACT,projects=PROJECTS,
        value_range=None,return_model=None,reason='GS/BDa/GX scope, future capex and generation combination remain material unresolved X; diagnostics cannot establish whole common-equity value',
        mature_low=low,mature_high=high,normalized_cash_crosscheck=cross,
        rm_low=rm(.06,.40,50.09851775473,2,downstream=.5),rm_high=rm(.05,.45,36.71485985473,0,downstream=1.),
        unknown_project_scale=unknown_project_scale(),funding_diagnostics={k:financing(k) for k in SCENARIOS},
        sensitivity_price_minus5=mature(.055,50,price=.95)['conditional_residual_per_share'],
        sensitivity_base=mature()['conditional_residual_per_share'],tests=tests())
    Path(__file__).with_name('2026-Q3-output.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps({k:result[k] for k in ['facts','normalized_cash_crosscheck','unknown_project_scale','tests']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
