"""法拉电子，金额亿元、股数亿股。标准库离线模型。"""
import json
from pathlib import Path
SHARES=2.25
REVENUE=[58,62.06,66.4042,70.388452,73.9078746]
CAPEX=[5.5,5.65,5.8,6.0,6.2]
DA=[3,3.15,3.3,3.5,3.7]
WC=[.8,.85,.85,.85,.85]
RESERVE_ADD=[.3,.4,.4,.4,.4]
DPS=[2.4,2.5,2.7,2.9,3.1]
def pv(cash,terminal,r):
    return sum(x/(1+r)**t for t,x in enumerate(cash,1))+terminal/(1+r)**len(cash)
def run(margin=.23,yield_rate=.01,roic=.18,g=.025,extra_wc=0,revenue=None,dps=None,capex=None,da=None,wc=None,other=2.6,initial=21,reserve_add=None,terminal_maintenance_gap=0):
    rev=revenue or REVENUE; ds=dps or DPS; cap=capex or CAPEX; dep=da or DA; working=wc or WC
    cash=initial; reserve=5.5; rows=[]
    for i,sales in enumerate(rev):
        nopat=sales*margin*.86
        reinvest=cap[i]-dep[i]+working[i]+extra_wc
        fcf=nopat-reinvest
        interest=cash*yield_rate
        dividend=ds[i]*SHARES
        end=cash+fcf+interest-dividend
        reserve+=(RESERVE_ADD if reserve_add is None else reserve_add)[i]
        assert abs(end-cash-fcf-interest+dividend)<1e-9
        assert abs(nopat-fcf-reinvest)<1e-9
        assert end >= 0
        assert (RESERVE_ADD if reserve_add is None else reserve_add)[i] <= working[i]+extra_wc+1e-9
        rows.append(dict(year=i+1,revenue=sales,nopat=nopat,da=dep[i],capex=cap[i],wc=working[i]+extra_wc,reinvestment=reinvest,fcff=fcf,cash_open=cash,financial_net_cash_income=interest,dividend=dividend,dps=ds[i],cash_close=end,operating_cash=reserve))
        cash=end
    term_fcf=rows[-1]['nopat']*(1+g)*(1-g/roic)-terminal_maintenance_gap
    ends={}
    for label,r in [('low',.10),('high',.085)]:
        op=term_fcf/(r-g)
        terminal=(op+cash+other)/SHARES
        value=pv(ds,terminal,r)
        ends[label]=dict(rate=r,terminal_operating_value=op,terminal_per_share=terminal,current_per_share=value,terminal_pv_share=terminal/(1+r)**5/value)
    assert abs(cash-initial-sum(x['fcff']+x['financial_net_cash_income']-x['dividend'] for x in rows))<1e-9
    return dict(rows=rows,terminal_fcff=term_fcf,terminal_roic=roic,terminal_growth=g,financial_yield=yield_rate,terminal_other_assets=other,endpoints=ends)
def main():
    base=run()
    sensitivity={'margin_21pct':run(margin=.21),'terminal_roic_12pct':run(roic=.12),'extra_wc_1_each_year':run(extra_wc=1),'zero_financial_yield':run(yield_rate=0)}
    # 周期弱：原有客户资格保存，前两年去库存，第三年起恢复；取消短期扩张节省现金。
    cycle=run(revenue=[52,56,62,68,73.9078746],margin=.23,capex=[4.3,4.7,5.8,6,6.2],wc=[.3,.4,.85,.85,.85],dps=[2,2.1,2.4,2.8,3.1],reserve_add=[.1,.2,.4,.4,.4])
    # 永久损伤：利润率与周转同时恶化，经营现金7亿元永久耗损，固定规模不自动恢复。
    structural=run(revenue=[48]*5,margin=.16,capex=[3.5]*5,da=[3]*5,wc=[0]*5,dps=[1.5]*5,roic=.10,g=0,initial=14,other=1,reserve_add=[0]*5,terminal_maintenance_gap=.5)
    optimistic=run(revenue=[60,66,73,80,87],margin=.24,capex=[6,6.5,7,7.5,8],wc=[1]*5,dps=[2.6,2.9,3.2,3.6,4],roic=.22)
    normal_low=57*.23*.86; normal_high=61*.24*.86
    method2={'low':(normal_low*14+23.6)/SHARES,'high':(normal_high*17+23.6)/SHARES,'nopat_low':normal_low,'nopat_high':normal_high}
    # 特例：零利率总和；无增长永续现金；现金无分配时余额自然累积。
    assert pv([1,2],3,0)==6
    assert abs(10*(1-0/.18)/.1-100)<1e-12
    assert abs((21+8-5)-24)<1e-12
    assert run(roic=.12)['endpoints']['low']['current_per_share']<base['endpoints']['low']['current_per_share']
    out={'units':'亿元/亿股，折现到2026-09-06，滚动年度末','shares':SHARES,'base':base,'method2':method2,'sensitivity':sensitivity,'scenarios':{'cycle':cycle,'structural':structural,'optimistic':optimistic},'checks':'cash conservation, equity bridge, no-growth, zero-rate and sensitivity passed'}
    Path(__file__).with_name('2026-H1-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'base':base['endpoints'],'method2':method2,'sensitivity':{k:v['endpoints'] for k,v in sensitivity.items()},'scenarios':{k:v['endpoints'] for k,v in out['scenarios'].items()}},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
