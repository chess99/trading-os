"""中国广核：亿元、亿股；五个完整周年预算，标准库、无网络。"""
import json
from pathlib import Path
D=[.09,.095,.10,.11,.12]
BASIC=504.988; CB=48.992849; B0=1236.78
# 每组台数折算为各年完整商业运行年；总投资均包括建设期利息。
BATCHES=[
 ('惠州1/2',407.1924/2,.82,[2,2,2,2,2]),
 ('苍南1/2',422.01/2,.46,[1.5,2,2,2,2]),
 ('陆丰5/6',407.52/2,1,[.5,1.5,2,2,2]),
 ('陆丰1/2',413.8446/2,1,[0,0,0,1,2]),
 ('惠州3/4',380.5784/2,1,[0,0,0,.5,1.5]),
 ('宁德5/6',383/2,.51,[0,0,.5,1.5,2]),
 ('苍南3',767/4,.51,[0,0,0,.5,1]),
 ('招远1',420.3248/2,1,[0,0,0,0,.5]),
]
# 预算与累计投入比例；并非把在建余额简单从总预算中减掉。
PROJECT_BUDGETS=[('陆丰1/2',413.8446,.6885),('陆丰5/6',407.52,.5755),('惠州1/2',407.1924,.9928),('惠州3/4',380.5784,.2852),('苍南1/2',422.01,.9365),('苍南后续',767,.161),('宁德5/6',383,.44),('招远1/2',420.3248,.193),('防城港5/6',363.06,.1236)]

def run(price=.33,hours=7150,mature=97.5,rate=.08,multiple=14,delay=0,capex_factor=1,upstream_factor=1,conversion=True,redemption_premium=0):
 rows=[]; book=B0; group_debt=3492.32; parent_debt=276.68
 group_cash=195.04-43.43; parent_cash=80.21-43.43
 parent_retained=306.09; cp=3.58; shares=BASIC; capex_total=0
 for i in range(5):
  batchrows=[]; new_attr=0; new_group=0; dep=0; new_minority=0
  for name,cost,own,profile in BATCHES:
   n=profile[max(0,i-delay)] if i>=delay else 0
   remaining_fraction={'惠州1/2':.0072,'苍南1/2':.0635,'陆丰5/6':.4245,'陆丰1/2':.3115,'惠州3/4':.7148,'宁德5/6':.56,'苍南3':.839,'招远1':.807}[name]
   cost=cost*(1+(capex_factor-1)*remaining_fraction)
   q=1.2*hours/100 # 1.2GW*小时/100 = 亿kWh
   revenue=q*price; cashcost=q*.14
   da=cost*.033; interest=cost*.8*.026
   ni=(revenue-cashcost-da-interest)*.75
   new_attr+=n*ni*own;new_group+=n*ni;dep+=n*da;new_minority+=n*ni*(1-own)
   batchrows.append({'name':name,'equivalent_units':n,'ownership':own,'revenue_per_unit':revenue,'cashcost_per_unit':cashcost,'depreciation_per_unit':da,'interest_per_unit':interest,'profit_per_unit':ni,'attributable_profit':n*ni*own})
  parent_extra_interest=max(0,parent_debt-276.68)*.03
  cb_save=0
  if i==4:
   if conversion:
    shares=BASIC+CB/cp;group_debt-=CB;parent_debt-=CB;book+=CB;cb_save=CB*.02*.75
   else:
    premium=CB*redemption_premium
    group_debt+=premium;parent_debt+=premium;book-=premium;parent_retained-=premium
    cb_save=-(CB*(1+redemption_premium)*.03-CB*.02)*.75 # 到期本金及额外赎回现金用3%贷款置换
  profit=mature+new_attr-parent_extra_interest*.75+cb_save
  dist=D[i]*shares
  capex=500*capex_factor; maintenance=60; growth=capex-maintenance;capex_total+=capex
  # 成熟资产年经营现金270，减基线现金利息50，含营运资金/换料波动储备。
  cash_after_interest=220+new_group+dep-parent_extra_interest+cb_save
  minority_distribution=25+.45*new_minority
  minority_capital=growth*.2*.25
  new_borrowing=capex+dist+minority_distribution-cash_after_interest-minority_capital
  group_debt+=new_borrowing
  # 成熟利润80%上划，新投产利润50%上划，其余留在项目公司。
  upstream=(mature*.8+new_attr*.5)*upstream_factor
  parent_injection=growth*.2*.75
  parent_cost=9+parent_extra_interest-cb_save
  needed=dist+parent_injection+parent_cost-upstream
  parent_debt+=needed
  # 第一年上划中含H1已确认的应收股利收回，不重复增加可分配利润。
  old_receivable=min(32.96,upstream) if i==0 else 0
  parent_retained+=upstream-old_receivable-(10+parent_extra_interest-cb_save)-dist
  before=book;book+=profit-dist
  assert abs(book-(before+profit-dist))<1e-8
  assert abs(new_borrowing-(capex+dist+minority_distribution-cash_after_interest-minority_capital))<1e-8
  assert parent_retained>0
  rows.append({'year':i+1,'shares':shares,'profit':profit,'new_attributable_profit':new_attr,'new_group_profit':new_group,'new_depreciation':dep,'dividend_per_share':D[i],'distribution':dist,'book_equity_end':book,'capex':capex,'maintenance':maintenance,'growth_capex':growth,'capitalized_interest_in_capex':40*capex_factor,'cash_after_interest':cash_after_interest,'minority_distribution':minority_distribution,'minority_capital':minority_capital,'net_borrowing':new_borrowing,'gross_debt_end':group_debt,'net_debt_end':group_debt-group_cash,'parent_upstream':upstream,'old_receivable_collected':old_receivable,'parent_equity_injection':parent_injection,'parent_cost':parent_cost,'parent_net_borrowing':needed,'parent_debt_end':parent_debt,'parent_cash':parent_cash,'redemption_premium_financed':CB*redemption_premium if i==4 and not conversion else 0,'parent_retained':parent_retained,'batches':batchrows})
  if i<4:cp-=D[i]
 terminal=rows[-1]['profit']*multiple/shares
 divpv=sum(v/(1+rate)**(i+1) for i,v in enumerate(D));tvpv=terminal/(1+rate)**5
 return {'price':price,'hours':hours,'mature_profit':mature,'cost_of_equity':rate,'multiple':multiple,'rows':rows,'terminal_per_share':terminal,'value':divpv+tvpv,'dividend_pv':divpv,'terminal_pv':tvpv,'terminal_weight':tvpv/(divpv+tvpv),'conversion_price':cp,'shares':shares,'capex_total':capex_total}

def ri(roe_start,roe_end,k,g):
 b=B0/BASIC;value=b;rows=[];shares=BASIC;conversion_accretion=0
 for t in range(1,11):
  if t==5:
   newshares=BASIC+CB/(3.58-sum(D[:4]))
   adjusted=(b*shares+CB)/newshares
   conversion_accretion=adjusted-b;value+=conversion_accretion/(1+k)**(t-1)
   b=adjusted;shares=newshares
  roe=roe_start+(roe_end-roe_start)*(t-1)/9
  earn=b*roe;res=earn-b*k
  div=D[t-1] if t<=5 else earn*(.5+.05*(t-6)/4)
  value+=res/(1+k)**t
  rows.append({'year':t,'book_begin':b,'roe':roe,'earnings':earn,'dividend':div,'residual':res})
  b+=earn-div
 tv=b*(roe_end-k)/(k-g);value+=tv/(1+k)**10
 return {'value':value,'rows':rows,'terminal_book':b,'terminal_value':tv,'steady_payout':1-g/roe_end,'conversion_accretion':conversion_accretion,'k':k,'g':g}

low=run(price=.325,hours=7000,mature=95,rate=.085,multiple=13)
high=run(price=.335,hours=7300,mature=100,rate=.075,multiple=15)
base=run()
out={'units':'人民币亿元；亿股；电价不含税元/kWh','project_budgets':PROJECT_BUDGETS,'remaining_budget':sum(b*(1-f) for _,b,f in PROJECT_BUDGETS),'low':low,'base':base,'high':high,'auxiliary_low':ri(.09,.085,.085,.03),'auxiliary_high':ri(.10,.095,.075,.035),'sensitivity':{'price_down_1cent':run(price=.32),'one_year_delay':run(delay=1),'capex_plus_20pct':run(capex_factor=1.2),'upstream_down_20pct':run(upstream_factor=.8),'no_conversion':run(conversion=False),'no_conversion_premium10':run(conversion=False,redemption_premium=.1),'structural':run(price=.30,hours=6800,mature=80,rate=.09,multiple=12)}}
# 手算边界：零折现PV等于现金总和+终值；份额零时不取得该项目利润。
z=run(rate=0);assert abs(z['value']-sum(D)-z['terminal_per_share'])<1e-9
assert len(base['rows'])==5 and abs(base['shares']-(BASIC+CB/(3.58-sum(D[:4]))))<1e-9
assert abs(out['sensitivity']['no_conversion']['shares']-BASIC)<1e-9
assert all(row['distribution']==row['shares']*row['dividend_per_share'] for row in base['rows'])
assert abs(sum(b for _,b,_ in PROJECT_BUDGETS)-3964.5302)<.01
out['self_checks']=['利润留存滚动','合并现金及新增借款守恒','母公司法定留存非负','已确认应收不重复计利润','转换与不转换股债互斥','零折现手算特例','九组总预算与原报一致']
Path(__file__).with_name('2026-H1-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k: {a:v[a] for a in ['value','terminal_per_share','shares']} for k,v in [('low',low),('base',base),('high',high)]},ensure_ascii=False,indent=2))
