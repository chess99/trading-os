"""卫星化学2026-H1：金额亿元、股数亿股；经营租赁口径，标准库无网络。"""
import json
from pathlib import Path
SHARES=34.0
CASH0=126.305+8.1072+.7+7.9-25
DEBT=51.13+32.69+30.626
INV=23.4
MINORITY=.21
DIV=[.55,.6,.65,.7,.75]
PROJECT=[25,22,14.29,0,0] # 高端材料42.48+研发中心18.81；舍入61.29
BASE={
 'low':dict(existing=68,growth=.015,project_profit=[0,1.5,3.5,5.5,7.5],extra_capex=[3,4,5,7,9],wc=[3]*5,dep=[30,31,32,33,34],rent=[28,29,30,31,32],ke=.108,wacc=.10,g=.015,roic=.10),
 'high':dict(existing=80,growth=.02,project_profit=[0,2,5,8,10],extra_capex=[5,7,9,12,15],wc=[4,5,6,6,6],dep=[30,32,34,36,38],rent=[28,30,32,34,36],ke=.098,wacc=.092,g=.02,roic=.12)
}
def model(p, profit_scale=1, capex_extra=0, rent_extra=0):
 cash=CASH0; rows=[]
 for i in range(5):
  # NOPAT含所有经营费用与当期完整租金。租前利润仅为口径核对，不独立估值。
  nopat=(p['existing']*(1+p['growth'])**i+p['project_profit'][i])*profit_scale-rent_extra*.85
  rent=p['rent'][i]+rent_extra
  fcff=nopat+p['dep'][i]-p['dep'][i]-PROJECT[i]-p['extra_capex'][i]-p['wc'][i]-capex_extra
  cash_interest=cash*.01; debt_interest=DEBT*.03*.85
  owner_cash=fcff+cash_interest-debt_interest
  distribution=DIV[i]*SHARES
  cash_end=cash+owner_cash-distribution
  rows.append(dict(year=i+1,nopat_after_full_rent=nopat,full_rent=rent,nopat_before_full_rent=nopat+rent*.85,nonlease_depreciation=p['dep'][i],maintenance=p['dep'][i],remaining_project_capex=PROJECT[i],other_growth_capex=p['extra_capex'][i]+capex_extra,incremental_working_capital=p['wc'][i],fcff=fcff,cash_start=cash,cash_yield_net_tax=cash_interest,nonlease_interest_net_tax=debt_interest,owner_cash=owner_cash,common_distribution=distribution,cash_end=cash_end,nonlease_debt=DEBT))
  assert abs(cash_end-cash-owner_cash+distribution)<1e-9
  assert abs(fcff-(nopat-PROJECT[i]-p['extra_capex'][i]-p['wc'][i]-capex_extra))<1e-9
  cash=cash_end
 terminal_operating=rows[-1]['nopat_after_full_rent']*(1+p['g'])*(1-p['g']/p['roic'])/(p['wacc']-p['g'])
 terminal_equity=terminal_operating+cash-DEBT+INV-MINORITY
 pv_div=sum(x/(1+p['ke'])**(i+1) for i,x in enumerate(DIV))
 pv_terminal=terminal_equity/SHARES/(1+p['ke'])**5
 auxiliary=(sum(r['fcff']/(1+p['wacc'])**r['year'] for r in rows)+terminal_operating/(1+p['wacc'])**5+CASH0-DEBT+INV-MINORITY)/SHARES
 return dict(inputs=p,rows=rows,terminal_operating_value=terminal_operating,terminal_cash=cash,terminal_equity_value=terminal_equity,terminal_per_share=terminal_equity/SHARES,current_value=pv_div+pv_terminal,distribution_pv=pv_div,terminal_pv=pv_terminal,terminal_contribution=pv_terminal/(pv_div+pv_terminal),auxiliary_fcff_value=auxiliary)
def checks():
 assert abs(sum(PROJECT)-61.29)<1e-9
 assert abs(sum(DIV)*SHARES-110.5)<1e-9
 # 零增长资本化、零净现金且立即足额分配的手算特例。
 assert abs(10/.1-100)<1e-9
 assert abs(sum(10/1.1**t for t in range(1,6))+100/1.1**5-100)<1e-9
 # 多付一元分红必少留一元现金；租金永久增量通过经营利润且不另减租赁本金。
 assert abs((100+20-5)-(100+20-6)-1)<1e-9
 assert 'lease_debt' not in BASE['low']
checks()
output={'units':'亿元、亿股、元/股','scope':'完整租金在经营利润和FCFF内；净金融桥不含租赁负债及使用权资产；银行、外部票据、白银本金仍计债务','starting_cash_after_operating_buffer':CASH0,'nonlease_debt':DEBT,'investment_value':INV,'shares':SHARES,'distributions':DIV,'base':{k:model(v) for k,v in BASE.items()},'sensitivities':{}}
output['sensitivities']['all_nopat_minus20pct']={k:model(v,profit_scale=.8) for k,v in BASE.items()}
output['sensitivities']['annual_rent_plus5']={k:model(v,rent_extra=5) for k,v in BASE.items()}
output['sensitivities']['five_year_capex_plus25']={k:model(v,capex_extra=5) for k,v in BASE.items()}
# 完整替代经营路径：前三年周期弱后恢复，和永久成本受损并低回报继续扩张。
for name,scale,extra,rx in [('structural',.65,5,5),('optimistic',1.15,0,0)]:
 output['sensitivities'][name]={k:model(v,profit_scale=scale,capex_extra=extra,rent_extra=rx) for k,v in BASE.items()}
# 周期弱：旧装置盈利前三年弱，项目同步延后但期末恢复；资本计划不减免。
cycle={}
for k,v in BASE.items():
 p=dict(v); p['project_profit']=[v['project_profit'][i]-v['existing']*(1+v['growth'])**i*.2 if i<3 else v['project_profit'][i] for i in range(5)]
 cycle[k]=model(p)
output['sensitivities']['cyclical_three_years']=cycle
Path(__file__).with_name('2026-H1-output.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':
 for k,v in output['base'].items(): print(k,round(v['current_value'],4),round(v['terminal_per_share'],4),round(v['auxiliary_fcff_value'],4))
 for k,v in output['sensitivities'].items(): print(k,[round(x['current_value'],3) for x in v.values()])
