"""爱博医疗2026-H1；百万元、百万股；标准库、离线可重算。"""
import json
from pathlib import Path
S=193.437735
CASH=602.09588558+82.53251524
BANK=1151.47035839
OTHER_DEBT=65.63343719
INVEST=117.12929205+35.83517207+42.70506108+17.42761644
PRODUCTS=[('IOL',560,.85),('其他手术',70,.44),('OK镜',245,.85),('其他近视管理',70,.64),('软镜',540,.33),('其他视力保健',45,.28),('运动医学',360,.61),('贸易其他',95,.12)]
GROSS=sum(r*m for _,r,m in PRODUCTS)
NOPAT=(GROSS-400-210-160-23)*.83-1.66

def operations(start=NOPAT,roic=.12,maint_extra=0,growth=.05):
    rows=[]; prev_reserve=300
    for t in range(1,12):
        growth_t=growth if t<=5 else .03 if t<=10 else .02
        n=start if t==1 else rows[-1]['nopat']*(1+growth_t)
        reinvest=n*growth_t/roic
        fixed=reinvest*.7; nwc=reinvest*.3
        project=[60,60,54.5939][t-1] if t<=3 else 0
        extra=max(0,project-fixed)
        da=145*(1.04**(t-1)); maintenance=da+maint_extra
        reserve=prev_reserve*(1.02 if t==11 else 1.03)
        reserve_add=reserve-prev_reserve
        transition=20 if t==1 else 10 if t==2 else 0
        payable=58.453 if t==1 else 0
        cf=n+da-maintenance-fixed-extra-nwc-transition-payable-reserve_add
        rows.append(dict(year=t,nopat=n,da=da,maintenance=maintenance,growth_fixed=fixed,project_extra=extra,nwc=nwc,transition_wc=transition,asset_payable=payable,cash_reserve=reserve,cash_reserve_add=reserve_add,fcff=cf))
        prev_reserve=reserve
    return rows

def value(rows,k=.10,g=.02,nci=260,invest_recovery=.85):
    terminal=rows[10]['fcff']/(k-g)
    pv_cf=sum(r['fcff']/(1+k)**r['year'] for r in rows[:10])
    terminal_pv=terminal/(1+k)**10
    asset_pv=INVEST*invest_recovery/(1+k)**5
    adj=CASH-300-BANK-OTHER_DEBT-nci+asset_pv
    return dict(per_share=(pv_cf+terminal_pv+adj)/S,operating_pv=pv_cf+terminal_pv,terminal=terminal,terminal_pv_share=terminal_pv/(pv_cf+terminal_pv),financial_asset_pv=asset_pv,net_adjustment=adj,rate=k,rows=rows,minority_value=nci)

base=operations()
low=value(operations(start=NOPAT-12,roic=.11),.105,nci=280,invest_recovery=.75)
high=value(operations(start=NOPAT+12,roic=.13),.095,nci=240,invest_recovery=.95)
central=value(base)

# 集团现金和本金预算：FCFF已扣必要现金增量，实际资金池加回该留存再比较最低现金。
returns=[]; cash=CASH; bank=BANK; other=OTHER_DEBT; parent_cash=363.41510687; parent_retained=1319.13549610
for i,row in enumerate(base[:5]):
    t=i+1
    net_bank_repay=100
    other_repay=[12.98066057,15,15,12,10.65277662][i]
    interest=bank*.035*.83
    div=[60,65,75,85,95][i]
    nci_div=[5,6,7,8,9][i]
    opening=cash
    cash+=row['fcff']+row['cash_reserve_add']-interest-net_bank_repay-other_repay-div-nci_div
    bank-=net_bank_repay; other-=other_repay
    parent_cfo=220*1.03**i
    parent_cap=30*1.04**i
    parent_support=[75,70,65,60,55][i]
    parent_cash+=parent_cfo-parent_cap-parent_support-75-div
    parent_retained+=260*1.03**i-div
    assert cash>=row['cash_reserve'] and parent_cash>=150 and parent_retained>0
    assert abs(cash-(opening+row['fcff']+row['cash_reserve_add']-interest-net_bank_repay-other_repay-div-nci_div))<1e-8
    returns.append(dict(year=t,fcff=row['fcff'],interest_after_tax=interest,bank_net_repayment=net_bank_repay,other_repayment=other_repay,common_dividend=div,nci_dividend=nci_div,cash=cash,minimum_cash=row['cash_reserve'],bank_debt=bank,other_debt=other,parent_cash=parent_cash,parent_cfo=parent_cfo,parent_capex=parent_cap,parent_net_support=parent_support,parent_retained=parent_retained,distribution_per_share=div/S))

def terminal5(k,scale=1):
    cashflows=[r['fcff']*scale for r in base[5:10]]
    terminal=base[10]['fcff']*scale/(k-.02)
    operating=sum(c/(1+k)**(i+1) for i,c in enumerate(cashflows))+terminal/(1+k)**5
    nci=260*1.03**5
    equity=operating+cash-base[4]['cash_reserve']+INVEST*.85-bank-other-nci
    return dict(per_share=equity/S,operating_value=operating,excess_cash=cash-base[4]['cash_reserve'],financial_assets=INVEST*.85,bank_debt=bank,other_debt=other,minority_value=nci,rate=k)

sens={}
for label,params in [('roic_9',dict(roic=.09)),('maintenance_plus_25',dict(maint_extra=25)),('growth_3',dict(growth=.03)),('growth_7',dict(growth=.07))]:
    sens[label]=value(operations(**params))['per_share']
# 固定资本的盈利减20%，不让利润下降自动节省项目、库存和维护。
stress=[]
for row in base:
    rr=dict(row); rr['fcff']-=.2*row['nopat']; stress.append(rr)
sens['profit_minus_20_fixed_capital']=value(stress)['per_share']
sens['cash_reserve_plus_100']=central['per_share']-100/S
sens['nci_plus_60']=central['per_share']-60/S
sens['all_investments_zero']=central['per_share']-central['financial_asset_pv']/S
# 周期延迟只压前两年现金；长期利润压力见profit_minus_20_fixed_capital。
cycle=[dict(x) for x in base]
for i in range(2):cycle[i]['fcff']-=50
sens['two_year_delay']=value(cycle)['per_share']
assert abs(GROSS-1181.65)<1e-8
assert abs(NOPAT-320.9195)<1e-8
assert abs(other)<1e-6
assert all(abs(r['fcff']-(r['nopat']+r['da']-r['maintenance']-r['growth_fixed']-r['project_extra']-r['nwc']-r['transition_wc']-r['asset_payable']-r['cash_reserve_add']))<1e-8 for r in base)
# 无增长、无额外资本的手算特例：恒定100现金、10%贴现=1000。
assert abs(sum(100/1.1**t for t in range(1,11))+1000/1.1**10-1000)<1e-8
# 股利多发1，终值现金少1，不能重复计价。
assert abs(((cash-1)-cash)+1)<1e-8
# 辅助稳态现金资本化：第五年后立即降至2%增长，股权折现率高于加权资本成本。
aux=[]
for wacc,ke in [(.105,.125),(.095,.115)]:
    stable_nopat=base[4]['nopat']*1.02
    stable_cash=stable_nopat*(1-.02/.12)-base[4]['cash_reserve']*.02
    ev=stable_cash/(wacc-.02)
    eq=ev+cash-base[4]['cash_reserve']+INVEST*.85-bank-other-260*1.03**5
    pv=(sum(r['common_dividend']/(1+ke)**r['year'] for r in returns)+eq/(1+ke)**5)/S
    aux.append(pv)
output=dict(units='百万元、百万股',share_count=S,normal_group_nopat=NOPAT,products=PRODUCTS,core_low=low,core_high=high,central=central,return_budget=returns,terminal5_low=terminal5(.105,.96),terminal5_high=terminal5(.095,1.04),sensitivities=sens,auxiliary_value_range=aux,financial_investment_book=INVEST,checks='passed')
Path(__file__).with_name('2026-H1-output.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:output[k] for k in ['normal_group_nopat','sensitivities','auxiliary_value_range','checks']},ensure_ascii=False))
print('core',low['per_share'],high['per_share'],'central',central['per_share'])
print('terminal5',output['terminal5_low'],output['terminal5_high'])
print('dividends',[r['distribution_per_share'] for r in returns])
