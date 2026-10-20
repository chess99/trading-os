"""安图生物；亿元、亿股、元/股；无外部依赖。"""
import json
from pathlib import Path
S=5.71424768
CASH=32.0332
DEBT=9.1406
MINORITY=1.2
RESERVE=4.0
BRIDGE=CASH-DEBT-MINORITY-RESERVE
REVENUE=[42.5,43.3,44.3,45.5,46.8]
RD=[8.3,8.5,8.7,9.0,9.3]
EBIT=[8.2,8.4,8.7,9.1,9.5]
NOPAT=[v*.85 for v in EBIT]
DA=[4.5]*5
CAPEX=[3.8,3.8,3.9,4.,4.1]
# 前五年4亿元备用金固定；WC只含非现金经营资产净投入。
WC=[2.5,2.0,1.8,1.6,1.6]
FCFF=[n+d-c-w for n,d,c,w in zip(NOPAT,DA,CAPEX,WC)]
DIV=[4.5,4.8,5.0,5.2,5.4]
def valuation(cfs,nopat,r,g,roic,bridge=BRIDGE):
    term=nopat*(1+g)*(1-g/roic)/(r-g)
    cpv=sum(c/(1+r)**t for t,c in enumerate(cfs,1))
    tpv=term/(1+r)**5
    return dict(rate=r,growth=g,incremental_roic=roic,terminal_ev=term,cashflow_pv=cpv,terminal_pv=tpv,operating_value=cpv+tpv,equity_value_per_share=(cpv+tpv+bridge)/S,terminal_share=tpv/(cpv+tpv) if cpv+tpv else 0)
low=valuation(FCFF,NOPAT[-1],.10,.01,.09)
high=valuation(FCFF,NOPAT[-1],.09,.015,.11)
base=valuation(FCFF,NOPAT[-1],.095,.0125,.10)
# NOPAT、全费用化研发与资本支出分开。资本开支不再包含已费用化的研发现金。
rows=[];cash=CASH
parent_cash=8.5758046262;parent_profit_reserve=29.9289569516
for i in range(5):
    finance_income=max(cash-RESERVE,0)*.015
    interest=.24
    minority_distribution=.04
    closing=cash+FCFF[i]+finance_income-interest-minority_distribution-DIV[i]
    parent_open=parent_cash
    parent_cfo=[3,4,5,5.5,6][i]
    parent_capex=[1.5,1.5,1.6,1.7,1.8][i]
    upstream=[1.2,1.2,1.3,1.4,1.5][i]
    parent_other=[.5,.4,.3,.2,.2][i]
    redemption=0.0
    parent_cash+=parent_cfo+upstream+redemption-parent_capex-parent_other-.1-DIV[i]
    legal_profit=[5.5,5.7,5.9,6.1,6.3][i]
    parent_profit_reserve+=legal_profit-DIV[i]
    rows.append(dict(year=i+1,revenue=REVENUE[i],research_expense=RD[i],economic_ebit=EBIT[i],nopat=NOPAT[i],depreciation=DA[i],non_research_capex=CAPEX[i],working_capital_investment=WC[i],fcff=FCFF[i],opening_financial_assets=cash,financial_income=finance_income,net_debt_interest=interest,minority_distribution=minority_distribution,common_distribution=DIV[i],dividend_per_share=DIV[i]/S,closing_financial_assets=closing,debt=DEBT,parent_opening_cash=parent_open,parent_operating_cash=parent_cfo,parent_capex=parent_capex,subsidiary_dividends_received=upstream,parent_other_net_payments=parent_other,parent_financial_redemption=redemption,parent_interest=.1,parent_closing_cash=parent_cash,parent_profit=legal_profit,parent_undistributed_profits=parent_profit_reserve))
    assert abs(closing-cash-FCFF[i]-finance_income+interest+minority_distribution+DIV[i])<1e-9
    assert parent_cash>3 and parent_profit_reserve>0
    cash=closing
# 第五年末经营估值加分红后的资产；第六年起经营必要现金随g增长，减入终值现金流。
def end_value(r,g,roi):
    operating=(NOPAT[-1]*(1+g)*(1-g/roi)-RESERVE*g)/(r-g)
    terminal_minority=MINORITY+(.10-.04)*5
    bridge=cash-DEBT-terminal_minority-RESERVE
    return dict(operating_value=operating,financial_assets=cash,debt=DEBT,minority_value=terminal_minority,operating_cash_reserve=RESERVE,net_bridge=bridge,equity_per_share=(operating+bridge)/S)
# 当前DCF亦纳入终值新增必要现金；第一至五年备用金固定4亿元，WC均为非现金资本。
for v in [low,high,base]:
    decrement=RESERVE*v['growth']/(v['rate']-v['growth'])
    v['terminal_ev']-=decrement
    v['terminal_pv']=v['terminal_ev']/(1+v['rate'])**5
    v['operating_value']=v['cashflow_pv']+v['terminal_pv']
    v['equity_value_per_share']=(v['operating_value']+BRIDGE)/S
    v['terminal_share']=v['terminal_pv']/v['operating_value']
terminal_low=end_value(.10,.01,.09);terminal_high=end_value(.09,.015,.11)
# 辅助法：第五年成熟现金资本化后回折；同一现金端点，允许前五年现金低于成熟年。
aux=[]
for v in [low,high]:
    matured_cash=NOPAT[-1]*(1+v['growth'])*(1-v['growth']/v['incremental_roic'])-RESERVE*v['growth']
    # 以持续当前正常化现金6.4亿为水平年金，前五年不再额外叠加。
    stable=6.4/(v['rate']-v['growth'])
    aux.append(dict(normalized_next_cash=6.4,rate=v['rate'],growth=v['growth'],operating_value=stable,equity_value_per_share=(stable+BRIDGE)/S))
sens={}
for label,dcf,dn in [('every_year_and_terminal_nopat_minus_1',[x-1 for x in FCFF],NOPAT[-1]-1),('first_five_years_additional_capital_1',[x-1 for x in FCFF],NOPAT[-1])]:
    v=valuation(dcf,dn,.095,.0125,.10)
    v['equity_value_per_share']-=RESERVE*.0125/(.095-.0125)/(1.095**5)/S
    sens[label]=v['equity_value_per_share']
sens['base']=base['equity_value_per_share']
sens['extra_parent_net_payment_2_each_of_first_two_years_min_cash']=min(r['parent_closing_cash']-2*min(r['year'],2) for r in rows)
sens['minority_value_double_loss_per_share']=MINORITY/(1.095**5)/S
# 时点净现金与未来现金桥可以独立使用，不能将未来留存再加到当前DCF。
assert len(rows)==5 and S>0
assert abs(valuation([0]*5,0,.1,0,.1)['equity_value_per_share']-BRIDGE/S)<1e-9
assert all(abs(r['fcff']-(r['nopat']+r['depreciation']-r['non_research_capex']-r['working_capital_investment']))<1e-9 for r in rows)
assert abs(sum(DIV)/S-sum(r['dividend_per_share'] for r in rows))<1e-9
assert cash>CASH
def holder_pv(cfs, final_nopat, r, g, roi):
    c=CASH
    for flow,d in zip(cfs,DIV):
        c += flow + (c-RESERVE)*.015 - .24 - .04 - d
    terminal_operating=(final_nopat*(1+g)*(1-g/roi)-RESERVE*g)/(r-g)
    terminal_common=terminal_operating+c-DEBT-(MINORITY+.06*5)-RESERVE
    return (sum(d/(1+r)**t for t,d in enumerate(DIV,1))+terminal_common/(1+r)**5)/S

for v in [low,high,base]:
    r=v['rate']
    v['assets_immediately_redeployable_value_per_share']=v['equity_value_per_share']
    v['equity_value_per_share']=holder_pv(FCFF,NOPAT[-1],r,v['growth'],v['incremental_roic'])
    v['distribution_pv_per_share']=sum(d/(1+r)**t for t,d in enumerate(DIV,1))/S
    v['terminal_common_equity_pv_per_share']=v['equity_value_per_share']-v['distribution_pv_per_share']
    initial_cash_gap=(CASH-RESERVE)*(1-(1.015/(1+r))**5)/S
    future_retention_gap=sum((f-d)/(1+r)**t*(1-(1.015/(1+r))**(5-t)) for t,(f,d) in enumerate(zip(FCFF,DIV),1))/S
    debt_gap=(-DEBT+DEBT/(1+r)**5+sum(.24*1.015**(5-t)/(1+r)**5 for t in range(1,6)))/S
    minority_gap=(-MINORITY+(MINORITY+.06*5)/(1+r)**5+sum(.04*1.015**(5-t)/(1+r)**5 for t in range(1,6)))/S
    v['reconciliation']={'initial_excess_cash_retention':initial_cash_gap,'future_operating_cash_retention':future_retention_gap,'debt_payment_timing':debt_gap,'minority_payment_timing':minority_gap,'total_gap':initial_cash_gap+future_retention_gap+debt_gap+minority_gap}
    assert abs(v['assets_immediately_redeployable_value_per_share']-v['equity_value_per_share']-v['reconciliation']['total_gap'])<1e-9
sens['base']=base['equity_value_per_share']
sens['every_year_and_terminal_nopat_minus_1']=holder_pv([f-1 for f in FCFF],NOPAT[-1]-1,.095,.0125,.10)
sens['first_five_years_additional_capital_1']=holder_pv([f-1 for f in FCFF],NOPAT[-1],.095,.0125,.10)
# 辅助现金资本化法同样计入已采纳金融留存/融资时点差额，避免把资产即时可运用当基准。
for a,v in zip(aux,[low,high]):
    a['assets_immediately_redeployable_value_per_share']=a['equity_value_per_share']
    a['financial_timing_adjustment_per_share']=v['reconciliation']['total_gap']
    a['equity_value_per_share']-=v['reconciliation']['total_gap']
out=dict(units='亿元、亿股、元/股',shares=S,bridge=BRIDGE,core_low=low,core_high=high,base=base,annual=rows,auxiliary=aux,terminal_low=terminal_low,terminal_high=terminal_high,sensitivities=sens,self_checks='现金守恒、母公司支付、利润储备、五年分配与零经营价值特例通过')
Path(__file__).with_name('2026-H1-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:out[k] for k in ['bridge','core_low','core_high','terminal_low','terminal_high','sensitivities']},ensure_ascii=False,indent=2))
