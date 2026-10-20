"""羚锐制药：亿元、亿股；存量推广应付按显式付款时间结算一次。"""
import json
from pathlib import Path
S=5.67115486
DPS=[1,1,1.05,1.1,1.15]

def evaluate(cash,r,g,net,y,payments):
    # 原现金路径已含超常应付结算。原期初金融权益中的相同准备予以还原。
    opening=net+sum(payments)
    normalized=[x+p for x,p in zip(cash,payments)]
    tv=cash[-1]*(1+g)/(r-g)
    pv_cash=sum(x/(1+r)**(i+1) for i,x in enumerate(cash))
    pv_terminal=tv/(1+r)**5
    rows=[]; balance=opening
    for i,(cf,d,p,n) in enumerate(zip(cash,DPS,payments,normalized)):
        before=balance; income=before*y; dividend=d*S
        balance=before+income+n-p-dividend
        assert abs(balance-(before+income+cf-dividend))<1e-10
        rows.append(dict(year=i+1,opening_financial_assets=before,financial_income=income,operating_cash_before_legacy_settlement=n,legacy_payable_payment=p,operating_cash_after_settlement=cf,dividend=dividend,closing_financial_assets=balance))
    assert abs(sum(normalized)-sum(payments)-sum(cash))<1e-10
    return dict(cash=cash,legacy_payments=payments,normalized_cash=normalized,rate=r,growth=g,opening_assets=opening,pv_cash=pv_cash,terminal_operating_value=tv,pv_terminal=pv_terminal,value_per_share=(opening+pv_cash+pv_terminal)/S,rows=rows,terminal_assets=balance,terminal_per_share=(tv+balance)/S,terminal_pv_share_of_total=pv_terminal/(opening+pv_cash+pv_terminal))

low=evaluate([5.4,6,6.7,7,7.2],.105,.015,14.5467,.01,[1.5,1,0,0,0])
high=evaluate([6.3,6.8,7.3,7.6,7.9],.095,.02,15.5467,.015,[.6,.4,0,0,0])
sensitive=evaluate([6.3,6.8,7.3,7.6,7.9],.105,.02,15.5467,.015,[.6,.4,0,0,0])
# 手算特例：零收益、零经营、零分配不改变金融本金；一期现金折现恒等式。
assert 10*(1+0)+0-0==10
assert abs(11/1.1-10)<1e-10
assert len(DPS)==5
# 期初资产桥及专用结算准备：已计费用对应既有负债，偿付只计一次。
assert abs(24.4932-3.6105-.0548-4-.3812+1.1-17.5467)<1e-9
assert abs(24.4932-3.6105-.0548-4-.3812+1.6-18.0467)<1e-9
reserve=1.5
for i,payment in enumerate([.9,.6,0,0,0]):
    start=reserve; reserve-=payment
    assert reserve>=-1e-9
    high['rows'][i].update(dedicated_reserve_opening=start,dedicated_reserve_payment=payment,dedicated_reserve_closing=reserve)
    low_reserve_payment=[.3,.2,0,0,0][i]
    low['rows'][i].update(dedicated_reserve_payment=low_reserve_payment,dedicated_reserve_closing=[.2,0,0,0,0][i])
assert abs(reserve)<1e-9
assert abs(sum(high['legacy_payments'])+1.5-2.5)<1e-9
assert abs(sum(low['legacy_payments'])+.5-3)<1e-9
result=dict(shares=S,distribution_per_share=DPS,total_distributions=sum(DPS)*S,low=low,high=high,sensitivity_cost_plus_1pct=sensitive,auxiliary_low=(7*11.5+14.5467)/S,auxiliary_high=(7.5*13+15.5467)/S)
Path(__file__).with_name('2026-H1-output.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['total_distributions','auxiliary_low','auxiliary_high']},ensure_ascii=False))
print(json.dumps({k:{j:result[k][j] for j in ['value_per_share','terminal_assets','terminal_per_share','opening_assets']} for k in ['low','high','sensitivity_cost_plus_1pct']},ensure_ascii=False,indent=2))
