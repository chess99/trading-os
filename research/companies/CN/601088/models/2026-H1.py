"""中国神华有限资源普通股现金模型；单位亿元、亿股，标准库、无网络。"""
import json
from pathlib import Path
S=216.89434304
# 已扣利息、税及少数。资本现金含矿权及旧付款；安全费用不加回。
def path(capital=400,first_capital=480,rate=.08,life=35,profit=560,net_liability=435):
    rows=[]; retained=0.0; accumulated=0.0
    for t in range(1,life+1):
        scale=1 if t<=life-10 else 1-.10*(t-(life-10))
        np=profit*scale-(max(-retained,0)*.025 if t<=6 else 0)
        da=280*scale
        cap=first_capital if t<=5 else min(120,240*scale)+(capital-120)*scale
        cash=np+da-cap
        # 先五年65%普通股分配；缺口/盈余在第六年清偿/释放。
        dividend=profit*.65 if t<=5 else cash
        financing=0.0
        if t<=5:
            financing=dividend-cash
            retained-=financing
        elif t==6:
            dividend+=retained
            retained=0.0
        # 收缩前五年预留本金；十年内同比例释放存款、金融本金并偿债。
        reserve=net_liability/5 if life-10<t<=life-5 else 0.0
        dividend-=reserve
        principal_settlement=net_liability/10 if t>life-10 else 0.0
        accumulated+=reserve-principal_settlement
        assert abs(cash+financing-dividend-reserve-(0 if t!=6 else -rows[4]['retained']))<1e-7
        rows.append({'year':t,'scale':scale,'parent_profit':np,'da':da,'capital_cash':cap,'owner_cash':cash,'dividend':dividend,'net_financing':financing,'retained':retained,'debt_reserve':accumulated,'principal_settlement':principal_settlement})
    assert abs(accumulated)<1e-7
    assert abs(sum(x['principal_settlement'] for x in rows)-net_liability)<1e-7
    assert all(x['dividend']>=0 for x in rows)
    value=sum(x['dividend']/(1+rate)**x['year'] for x in rows)/S
    terminal=sum(x['dividend']/(1+rate)**(x['year']-5) for x in rows if x['year']>5)/S
    return {'value':value,'year5_terminal':terminal,'rows':rows,'rate':rate,'life':life,'net_liability':net_liability,'year5_onward_pv_share':terminal/(1+rate)**5/value}
base=path()
low=path(capital=420,first_capital=500,rate=.085,net_liability=452)
high=path(capital=380,first_capital=460,rate=.075,net_liability=417)
sens={
 'capital_plus50':path(capital=450),
 'coal_price_minus20_before_resource_tax':path(profit=560-76*.79*.81),
 'life25':path(life=25),
 'life40':path(life=40),
 'rate9':path(rate=.09),
 'net_liability_plus143':path(net_liability=578),
 'cycle3years':None,
}
# 周期性盈利头三年-20%，之后回到既定路径；不以融资维持原分配。
cy=sum((x['dividend']-(112 if x['year']<=3 else 0))/(1.08**x['year']) for x in base['rows'])/S
# 结构性损伤：永久利润400，必要资本340，先期400；25年寿命。
struct=path(capital=340,first_capital=400,profit=400,life=25)
optimistic=path(capital=380,first_capital=460,profit=600,rate=.075,life=40)
# 正常母公司融资预算不是集团新增收益；上划延迟及往来额外支付压力。
parent={'opening_cash_after_paid_final':390.05-223.4011733312,'own_cfo':250,'cash_capex':175,'interest_and_lease':15,'upstream':250,'subsidiary_loan_repayments':60,'dividends':364,'annual_net_cash':250-175-15+250+60-364,'five_year_cash_before_refinancing':390.05-223.4011733312+5*(250-175-15+250+60-364),'two_year_upstream_delay100_plus_net_settlement100_financing_need':max(0,2*100+100-(390.05-223.4011733312+5*(250-175-15+250+60-364)))}
# 仅利息按2.5%计，已有资金余额及正常续作不等于零。
assert abs(sum([540,110,150,30,6,30,8])*.79*.81-559.2726)<1e-8
assert abs(sum([1/1.08**t for t in range(1,2)])-1/1.08)<1e-12
assert abs(base['value']-(sum(x['dividend']/1.08**x['year'] for x in base['rows'][:5])/S+base['year5_terminal']/1.08**5))<1e-9
out={'units':'亿元、亿股','shares':S,'base':base,'low':low,'high':high,'sensitivity':sens,'cycle_value':cy,'structural':struct,'optimistic':optimistic,'parent_budget':parent,'return_model':{'schema_version':1,'method':'annual_common_equity_irr_v1','currency':'CNY','model_as_of':'2026-09-06T00:00:00+08:00','base_case_distributions_per_share':[round(x['dividend']/S,6) for x in base['rows'][:5]],'base_case_terminal_equity_value_range_per_share':{'year_5':{'low':round(low['year5_terminal'],2),'high':round(high['year5_terminal'],2)}}}}
# 交叉法将第6年后的自由现金资本化为有限年金，扣衰减和净融资本金。
flat=sum(440/1.08**t for t in range(1,36))/S
out['cross_check']={'flat_owner_cash':440,'finite_annuity_factor':sum(1/1.08**t for t in range(1,36)),'flat_value':flat,'early_capital_and_distribution_timing_adjustment':sum((base['rows'][i-1]['dividend']-440)/1.08**i for i in range(1,7))/S,'late_decline_and_debt_adjustment':sum((base['rows'][i-1]['dividend']-440)/1.08**i for i in range(26,36))/S}
assert abs(flat+out['cross_check']['early_capital_and_distribution_timing_adjustment']+out['cross_check']['late_decline_and_debt_adjustment']-base['value'])<1e-8
out['method2']={'cash':440,'multiples':[10,12],'early_adjustment':out['cross_check']['early_capital_and_distribution_timing_adjustment'],'net_principal_pv_per_share':sum(435/5/1.08**t for t in range(26,31))/S}
out['method2']['values']=[440*m/S+out['method2']['early_adjustment']-out['method2']['net_principal_pv_per_share'] for m in [10,12]]
Path(__file__).with_name('2026-H1-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:out[k] for k in ['parent_budget','return_model','cross_check','cycle_value']},ensure_ascii=False,indent=2))
print('VALUES', {k:round(out[k]['value'],4) for k in ['low','base','high','structural','optimistic']})
print('SENS', {k:round(v['value'],4) for k,v in sens.items() if v})
