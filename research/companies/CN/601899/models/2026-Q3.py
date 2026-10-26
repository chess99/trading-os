#!/usr/bin/env python3
"""Zijin 2026-Q3. CNY billion; copper/lithium kt, gold tonnes.
Finite, recoverable reserve constrained operating model + two-level financing.
No security quotation is an input. All assumptions are in this file.
"""
import json, math, copy
from pathlib import Path
CUTOFF='2026-10-26T06:30:00Z'
# name, metal, look-through equity, 2027..31 saleable output (100% project),
# recoverable inventory at start 2027, maximum years, full accounting unit cost,
# depreciation/unit, sustaining/unit, five-year development capital (100% project, bn)
# Reserve caps are research budgets, not new company reserve certifications.
MINES=[
 ('巨龙','cu',.5816,[300,330,350,350,350],17000,40,31000,5000,6000,[1.2,.8,.6,.4,.4]),
 ('塞紫金上带','cu',1,[180,190,200,200,195],2300,14,24000,4500,6000,[1,1,1,.6,.5]),
 ('塞紫铜','cu',.63,[125,135,145,150,150],5000,24,39000,6000,7500,[1,1,1,.8,.5]),
 ('科卢韦齐','cu',.67,[115,110,100,85,70],500,6,34000,4000,5000,[.2,.2,.1,.1,0]),
 ('多宝山铜山','cu',1,[108,115,120,125,125],2500,30,30000,5000,6000,[1,1.2,1,.8,.5]),
 ('紫金山','cu',1,[85,80,70,60,50],450,8,29000,4000,5000,[.1,.1,.1,0,0]),
 ('朱诺','cu',.5359,[38,65,76,76,76],1800,25,33000,5000,6500,[1,.3,.2,.2,.2]),
 ('其他控股铜矿','cu',.76,[80,85,90,90,90],1300,18,34000,5000,6500,[.7,.8,.8,.6,.4]),
 # Only direct Kamoa equity. Indirect Ivanhoe holding remains a separate financial asset.
 ('卡莫阿直接','cu',.396,[350,420,480,500,500],14500,35,44000,9000,10000,[6,4,3,2,2]),
 ('阿瑞那二期','cu',1,[0,0,0,20,70],2300,30,36000,6000,7000,[2,2.5,2.5,1.5,.5]),
 ('武里蒂卡','au',.5897,[8.8,9,9,9,9],130,15,265,35,55,[.2,.2,.2,.2,.2]),
 ('阿基姆','au',.85,[8,9,10,10,10],177,22,400,50,80,[.6,.7,.7,.4,.3]),
 ('罗斯贝尔','au',.8075,[8,8.5,9,9,9],145,22,350,45,70,[.5,.7,.7,.4,.3]),
 ('诺顿','au',.85,[8,8,8,8,8],94,14,430,55,80,[.3,.3,.3,.3,.3]),
 ('瑞果多','au',.85,[7,8,9,10,10],76,16,310,40,65,[.5,.6,.6,.3,.2]),
 ('泽拉夫尚','au',.595,[6,6,6,6,6],62,12,280,35,60,[.2,.3,.3,.2,.1]),
 ('奥罗拉','au',.85,[5,5.5,6,6,6],75,20,320,50,75,[.4,.4,.4,.3,.2]),
 # Domestic/associated gold basket covers Longnan, Shanxi, Serbia associated gold and other assets.
 # 0.836 is H1 residual attributable output / residual gross output, recomputed in notes.
 ('其他金矿及伴生金','au',.8388361627233438,[46,47,49,50,50],780,22,290,40,65,[2,2.5,2.5,2,1.5]),
 # Chifeng 25.85% ownership * 82.28% underlying mine economics; no full-consolidation windfall.
 ('赤峰矿山','au',.2585*.8228,[15,16,17,18,18],210,18,400,45,75,[.8,.9,.9,.7,.5]),
 ('拉果措','li',.63,[25,30,35,40,40],1800,30,55000,7000,9000,[.5,.5,.4,.3,.2]),
 ('3Q','li',1,[25,30,35,40,40],1500,30,50000,7000,9000,[.5,.5,.4,.3,.2]),
 ('湘源','li',1,[40,45,50,50,50],1000,25,60000,6000,9000,[.4,.4,.3,.3,.2]),
 ('马诺诺','li',.549,[30,55,75,90,100],2800,30,55000,7000,10000,[2,1.5,1,.5,.4]),
 ('藏格锂','li',.262,[14,15,15,15,15],400,25,30000,3000,5000,[.1,.1,.1,.1,.1]),
]
BASE={'gold':850.,'copper':80000.,'lithium':90000.,'inflation':.015,'tax':.24,
      'royalty':.055,'cost_real_growth':.003,'upstream_fraction':.65,
      'equity_rate':.095,'ordinary_debt_rate':.033,'deposit_rate':.015,
      'payout_first5':.35,'payout_later':.70,'scenario':'base', 'price_shift':1.,
      'cost_shift':1.,'volume_shift':1.,'growth_shift':1.,'reserve_shift':1.,
      'subcash_factor':.78,'subdebt_factor':.75,'assets_factor':1.,'acquisition_prepaid':0.,'convert_2029':False}
SHARES=26.590798241+.0262 # Employee treasury shares re-enter circulation; options included.
EMPLOYEE_CASH=.077474592*18.56+.0262*10.70
# Parent debt + fully owned offshore CB liability plus residual project debt share.
PARENT_DEBT=10.326890067+22.075727251+20.929911054+43.254379669
GROUP_BOOK_DEBT=35.207599259+27.941847860+41.904209712+64.633685387+.222222739
CB_BOOK=12.9+8.6 # Q3 does not disaggregate; bounded by H1 liability and Q3 equity components.
CB_REDEMPTION=1.9996*7.0+1.5*7.0
# Kamoa Holding owns 80% of operating mine; balance-sheet ownership is 49.5%,
# not the 39.6% mine output interest. Shareholder loans are deducted then Zijin receivable added.
# H1 official USD bn facilities; USD/CNY budget 7.0. Holding shareholder loan credit uses Zijin H1 note.
JV_NET_DEBT=(.907076+.916897+.315435+.075532+.066728-.129481+2.744807)*.495*7-9.284632475
# Existing fair-value financial assets (not operating investments), plus non-modelled associates.
NONOPERATING_ASSOCIATES=3.242001754+1.175240077+(4.741664751+.440994803)*.262+.388460245+.288414821+.141983058
# Broad 80% common-equity realization budget, not false full ownership of consolidated assets.
FINANCIAL_ASSETS=(13.141995727+15.006467342+2.694675079)*.8+NONOPERATING_ASSOCIATES-.7-(3.333987700-1.425577447)
ACQUISITION_CASH=10.006048855+.310902731*29.82*.88
CHIFENG_NET_CASH=(6.033056952-.251781916-.535727062-.152391571)*.2585+.310902731*29.82*.88*.2585

def discount(flows,rate,start=0):
    return sum(x/(1+rate)**(i+1-start) for i,x in enumerate(flows) if i+1>start)

def operations(p):
    remaining={m[0]:m[4]*p['reserve_shift']*(.85 if m[1]=='li' else 1) for m in MINES}
    result=[]
    for t in range(1,41):
        inflation=(1+p['inflation'])**(t-1)
        shift=p['price_shift']; volume=p['volume_shift']; costshift=p['cost_shift']; capshift=p['growth_shift']
        if p['scenario']=='cyclical':
            shift*= [0.80,.85,.95][t-1] if t<=3 else 1
            volume*=.90 if t<=2 else (0.95 if t==3 else 1)
            capshift*=1.15 if t<=3 else 1
        if p['scenario']=='structural' and t>=2:
            # Overseas water/power/royalty/permit costs worsen permanently; no mean reversion.
            shift*=.85; costshift*=1.20; volume*=.85; capshift*=1.25
        if p['scenario']=='upside':
            shift*=1.12; volume*=1.06 if t>=3 else 1; capshift*=1.12
        sums={'profit':0.,'fcf':0.,'revenue':0.,'da':0.,'sustain':0.,'growth':0.,'nwc':0.,'cu':0.,'au':0.,'li':0.}
        detail=[]
        for name,metal,own,qs,reserve,life,cost,da,sustain,cap in MINES:
            qplan=(qs[t-1] if t<=5 else qs[-1]*(.995**(t-5))) if t<=life else 0
            q=min(remaining[name],qplan*volume)
            remaining[name]-=q
            # Capacity commissioning may lag but sunk/committed construction is not cancelled.
            development=cap[t-1]*capshift if t<=5 else 0
            unit=p[{'cu':'copper','au':'gold','li':'lithium'}[metal]]*inflation*shift
            denom=1000 if metal=='au' else 1e6
            revenue=q*unit/denom
            account_cost=q*cost*inflation*(1+p['cost_real_growth'])**(t-1)*costshift/denom
            depreciation=q*da*inflation/denom
            maintenance=q*sustain*inflation*costshift/denom
            tax=p['tax']+(.06 if p['scenario']=='structural' and t>=2 else 0)
            ebit=revenue-account_cost-revenue*p['royalty']
            profit=ebit*(1-tax) if ebit>0 else ebit # no fictitious immediate loss-tax refund
            wc=(.015*revenue if t<=5 else 0)
            fcf=profit+depreciation-maintenance-development-wc
            for key,val in [('profit',profit),('fcf',fcf),('revenue',revenue),('da',depreciation),('sustain',maintenance),('growth',development),('nwc',wc),(metal,q)]: sums[key]+=val*own
            detail.append({'mine':name,'gross_output':q,'ownership':own,'attributable_profit':profit*own,'attributable_fcf':fcf*own,'remaining_recoverable':remaining[name]})
        # Silver/molybdenum/zinc/potash/refining/Longking; excludes any income on separately valued securities.
        # Q3 sulphur-price windfall excluded. Projects fade; no perpetual commodity franchise.
        other_scale=1 if t<=5 else max(0,(26-t)/21)
        otherprofit=(8.0+min(t-1,4)*.5)*inflation*other_scale
        othercap=(1.8 if t<=5 else .6)*inflation*other_scale
        overhead=7.5*inflation*(1 if t<=5 else max(.15,(41-t)/36))
        sums['profit']+=otherprofit-overhead
        sums['fcf']+=otherprofit-othercap-overhead
        sums['growth']+=othercap
        sums['year']=2026+t;sums['details']=detail
        result.append(sums)
    return result

def finance(ops,p, opening=None):
    """Same function handles formal model and hand-verifiable test cases.
    Subs are economic attributable aggregate, with separate cash/RE; no claim legal offsets exist.
    Parent dividends cannot exceed retained legal profits or authorized funding capacity.
    """
    o=opening or {}
    parent_cash=o.get('parent_cash',6.119465016)
    sub_cash=o.get('sub_cash',(76.776449446-6.119465016)*p['subcash_factor']-ACQUISITION_CASH+p['acquisition_prepaid']+CHIFENG_NET_CASH)
    pd=o.get('parent_debt',PARENT_DEBT)
    sd=o.get('sub_debt',(GROUP_BOOK_DEBT-PARENT_DEBT-CB_BOOK)*p['subdebt_factor']+CB_REDEMPTION+JV_NET_DEBT)
    parent_re=o.get('parent_re',14.622428427)
    sub_re=o.get('sub_re',40.) # budget only; no reliance on entire consolidated retained profit
    shares=o.get('shares',SHARES)
    assets=o.get('assets',FINANCIAL_ASSETS*p['assets_factor'])
    cb=o.get('cb',CB_REDEMPTION)
    reserve=o.get('min_cash',3.)
    rows=[]
    for i,op in enumerate(ops):
        t=i+1; n=len(ops)
        pc0,sc0,pd0,sd0=parent_cash,sub_cash,pd,sd
        # Existing CB coupons are separated from normal project/parent financing.
        coupon=.139972 if cb>10.5 and not o else 0
        parent_interest=pd*p['ordinary_debt_rate']
        sub_interest=max(0,sd-cb)*p['ordinary_debt_rate']+coupon
        interest=parent_interest+sub_interest
        deposit=(parent_cash+sub_cash)*p['deposit_rate']
        totalprofit=op['profit']-interest+deposit
        fcf=op['fcf']-interest+deposit
        # Parent's own operations are included in op; this only locates the cash, not adds new profits.
        direct=min(2.,max(0,op['profit']*.06)) if not o else o.get('direct',0)
        subprofit=op['profit']-direct-sub_interest+sub_cash*p['deposit_rate']
        sub_re+=subprofit
        sub_cash+=op['fcf']-direct-sub_interest+sc0*p['deposit_rate']
        parent_cash+=direct-parent_interest+pc0*p['deposit_rate']
        source_budget=max(0,subprofit)*p['upstream_fraction']
        # All upstream is current declared income; receipts from old receivables are NOT presumed profits.
        upstream=min(source_budget,max(0,sub_re),max(0,sub_cash-(15. if not o else reserve)))
        sub_re-=upstream;sub_cash-=upstream;parent_cash+=upstream
        parent_re+=direct-parent_interest+pc0*p['deposit_rate']+upstream
        # Registered capital reserve top-up after options/employee shares: budget 0.02bn once.
        if t==1 and not o: parent_re-=.02; parent_cash+=EMPLOYEE_CASH
        conversion=0; repayment=0
        if t==3 and not o:
            amount=1.9996*7
            if p['convert_2029']:
                sd-=amount;cb-=amount;shares+=.836031904;conversion=amount
            else:
                sd-=amount;cb-=amount;pd+=amount # fully owned financing subsidiary refinanced by treasury, no phantom cash gain
        if t==5 and not o:
            sd-=10.5;cb-=10.5;pd+=10.5
        payout=(p['payout_first5'] if t<=5 else p['payout_later'])
        if p['scenario']=='structural' and t>=2:
            payout=.10 if t<=5 else (.40 if pd+sd-parent_cash-sub_cash<30 else 0.)
        desired=max(0,totalprofit)*payout
        legal_cap=max(0,parent_re-(0 if o else 2.))
        # The 10bn annual NET borrowing budget and 190bn TOTAL debt ceiling apply
        # to both parent and subsidiaries together, including unavoidable operating deficits.
        # Refinancing CB into ordinary debt above is a debt transfer, not new consolidated debt.
        sub_min=(15. if not o else reserve)
        borrowing_cap=min(10.,max(0,190-pd-sd)) if not o else o.get('borrowing_cap',0.)
        parent_mandatory=max(0,reserve-parent_cash)
        sub_mandatory=max(0,sub_min-sub_cash)
        mandatory=parent_mandatory+sub_mandatory
        if mandatory>borrowing_cap+1e-8:
            raise AssertionError('Zero-dividend funding shortfall: mandatory liquidity exceeds annual/total debt capacity')
        pd+=parent_mandatory;parent_cash+=parent_mandatory
        sd+=sub_mandatory;sub_cash+=sub_mandatory
        available=max(0,parent_cash-reserve)+(borrowing_cap-mandatory)
        dividend=min(desired,legal_cap,available)
        discretionary_borrow=max(0,dividend+reserve-parent_cash)
        pd+=discretionary_borrow;parent_cash+=discretionary_borrow-dividend;parent_re-=dividend
        borrowing=mandatory+discretionary_borrow
        assert borrowing<=borrowing_cap+1e-8
        repay_sub=min(max(0,sd-cb),max(0,sub_cash-sub_min))
        sd-=repay_sub;sub_cash-=repay_sub
        repay_parent=min(pd,max(0,parent_cash-reserve))
        pd-=repay_parent;parent_cash-=repay_parent
        assert pd+sd<=190+1e-6, 'Funding ceiling breached; path infeasible'
        # Cash conservation including changes in debt and non-cash conversion.
        external=(pd+sd)-(pd0+sd0)+conversion
        equity_cash=EMPLOYEE_CASH if t==1 and not o else 0
        assert abs((parent_cash+sub_cash)-(pc0+sc0)-(fcf+external+equity_cash-dividend))<1e-7
        assert dividend<=legal_cap+1e-8 and upstream<=max(0,sub_re+upstream)+1e-8, 'Illegal payment'  # accumulated operating losses can be negative; distribution remains constrained
        rows.append({'year':op['year'],'shares':shares,'profit':totalprofit,'fcf':fcf,'upstream':upstream,
          'dividend':dividend,'dps':dividend/shares,'desired_dividend':desired,'legal_cap':legal_cap,
          'parent_cash':parent_cash,'sub_cash':sub_cash,'parent_debt':pd,'sub_debt':sd,
          'parent_re':parent_re,'sub_re':sub_re,'interest':interest,'deposit':deposit,'new_borrowing':borrowing,
          'net_claim':pd+sd-parent_cash-sub_cash,'assets':assets,'conversion':conversion})
    return rows

def nav_value(fcfs,rate,closure,liquidity,net_claim,assets,shares,equity_proceeds=0):
    n=len(fcfs)
    project=discount(fcfs,rate)-(closure-liquidity)/(1+rate)**n-liquidity
    value=(project-net_claim+assets+equity_proceeds/(1+rate))/shares
    return value,project

def values(ops,rows,p):
    r=p['equity_rate'];n=len(rows)
    # Provision is not deducted initially and again at closure: one cash settlement only.
    closure=8.*(1+p['inflation'])**(n-1)
    residual=rows[-1]['assets']-rows[-1]['net_claim']-closure
    dps=[x['dps'] for x in rows]
    dps[-1]+=residual/rows[-1]['shares']
    first5=discount(dps[:5],r)
    wacc=r-.01
    initial_claim=PARENT_DEBT+(GROUP_BOOK_DEBT-PARENT_DEBT-CB_BOOK)*p['subdebt_factor']+CB_REDEMPTION+JV_NET_DEBT-6.119465016-((76.776449446-6.119465016)*p['subcash_factor']-ACQUISITION_CASH+p['acquisition_prepaid']+CHIFENG_NET_CASH)
    nav,project_pv=nav_value([x['fcf'] for x in ops],wacc,closure,18.,initial_claim,FINANCIAL_ASSETS*p['assets_factor'],SHARES,EMPLOYEE_CASH)
    # Remaining NAV at year 5 is revalued from remaining mine reserves, not copied from today.
    future_operating=discount([x['fcf'] for x in ops],wacc,start=5)-closure/(1+wacc)**(n-5)-18.+18./(1+wacc)**(n-5)
    tv5=(future_operating+rows[4]['assets']-rows[4]['net_claim'])/rows[4]['shares']
    ddm=first5+tv5/(1+r)**5
    return {'current':nav,'terminal_year5':tv5,'first5_dividend_pv':first5,
            'terminal_pv_fraction':(ddm-first5)/ddm,'auxiliary_ddm':ddm,
            'project_pv':project_pv,'initial_net_claim':initial_claim,
            'future_operating_nav_at_year5':future_operating,
            'liquidation_residual':residual}

def run(p):
    ops=operations(p);rows=finance(ops,p);v=values(ops,rows,p)
    return {'parameters':p,'values':v,'operations':ops,'financing':rows,'five_year_dps':[round(x['dps'],6) for x in rows[:5]]}

def tests():
    # One operating year, profit=FCF=10, all distributed upstream and to holder, no debt/tax/capital.
    p=dict(BASE,ordinary_debt_rate=0,deposit_rate=0,upstream_fraction=1,payout_first5=1)
    op=[{'profit':10.,'fcf':10.,'year':2027}]
    opening={'parent_cash':0.,'sub_cash':0.,'parent_debt':0.,'sub_debt':0.,'parent_re':0.,'sub_re':0.,'shares':2.,'assets':0.,'cb':0.,'min_cash':0.}
    row=finance(op,p,opening)[0]
    assert abs(row['dps']-5)<1e-12 and row['net_claim']==0
    assert abs(discount([row['dps']],.1)-50/11)<1e-12
    # Same formal function, dividend demand 10 but only 6 cash: payment cut to 6, retained legal profit 4.
    op=[{'profit':10.,'fcf':6.,'year':2027}]
    row2=finance(op,p,opening)[0]
    assert row2['dividend']==6 and row2['sub_re']==4 and row2['parent_re']==0
    # Zero dividend cannot cure a 15 cash operating deficit when funding is capped at 10.
    impossible=dict(opening,borrowing_cap=10.)
    caught=False
    try: finance([{'profit':-15.,'fcf':-15.,'year':2027}],p,impossible)
    except AssertionError as error: caught='Zero-dividend funding shortfall' in str(error)
    assert caught
    assert abs(nav_value([10.],.10,0,0,0,0,2)[0]-50/11)<1e-12
    return {'zero_dividend_funding_infeasible_case_passed':caught,'formal_nav_hand_case_50_over_11':50/11,'formal_finance_hand_case_1_dps':row['dps'],'formal_finance_hand_case_2_payment':row2['dividend'],'pv_hand_case_50_over_11':50/11,'passed':True}

if __name__=='__main__':
    cases={'base':BASE,'base_terminal_low':dict(BASE,equity_rate=.10),'base_terminal_high':dict(BASE,equity_rate=.09),'core_low':dict(BASE,gold=810,copper=77000,lithium=85000,equity_rate=.10,subcash_factor=.74,subdebt_factor=.79,assets_factor=.95),
           'core_high':dict(BASE,gold=890,copper=83000,lithium=95000,equity_rate=.09,subcash_factor=.82,subdebt_factor=.71,assets_factor=1.05),
           'cyclical':dict(BASE,scenario='cyclical'),
           'structural':dict(BASE,scenario='structural',upstream_fraction=.50,equity_rate=.105),
           'upside':dict(BASE,scenario='upside',equity_rate=.09),
           'gold_minus_100':dict(BASE,gold=750),
           'copper_minus_10000':dict(BASE,copper=70000),
           'upstream_minus20pct':dict(BASE,upstream_fraction=.52),
           'acquisition_A_prepaid':dict(BASE,acquisition_prepaid=10.006048855),
           'conversion_2029':dict(BASE,convert_2029=True)}
    out={'cutoff':CUTOFF,'units':'CNY billion; au tonnes; cu/li thousand tonnes','tests':tests(),'cases':{}}
    for name,p in cases.items():
        try:out['cases'][name]=run(p)
        except AssertionError as e: out['cases'][name]={'infeasible':str(e)}
    Path(__file__).with_name('2026-Q3-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
    print(json.dumps({k:v.get('values',v) for k,v in out['cases'].items()},ensure_ascii=False,indent=2))
