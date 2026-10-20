"""山东高速普通股经济模型。金额亿元、股数亿股。标准库，无网络。"""
import json, math, datetime, pathlib
P=pathlib.Path(__file__).parent
SHARES=48.34570825
ASOF=datetime.date(2026,9,12)
# 京台未分段披露收入，三段各1/3为中性配置；最早/最晚期限另作敏感性。
ROADS=[('济青',30.23,'2044-12-31'),('京台德齐',17.41/3,'2046-07-15'),('京台齐济',17.41/3,'2050-12-25'),('京台济泰',17.41/3,'2047-12-29'),('黄河二桥',4.9,'2050-12-25'),('济莱',5.42,'2034-10-21'),('威乳',1.47,'2032-12-19')]
ROAD_REVENUE=sum(x[1] for x in ROADS)
FIXED=468.1283581421
ROAD_TAX_BASIS=FIXED-24.08-17.5
CASH=15.2532406574; TRADING=5.1227889886; DEBT=403.02; PERP=164; OLD_PAY=13.6799624598
OTHER_ASSETS=960.8780236361-FIXED-CASH-TRADING-326.5031383149-131.550210474
OTHER_LIABS=558.4373395814-DEBT-OLD_PAY
OLD_CONSTRUCTION_PAYABLE=36.5891530529
REQUIRED_CASH=3.
# NAV已扣该主体全部负债，包括对子公司的母内部借款；重要子公司再扣实际少数权益。
EQUITY=[
 ('武荆',27.7512390391,.90,1.05,2.804749932),
 ('轨道交通',32.6783133978,.75,.90,1.6169377106),
 ('信息集团',17.6350060697,.55,.75,.7),
 ('毅康',14.3906953348,.30,.50,0),
 ('投资发展',40,1.00,1.20,.80),
 ('其他直接子股',225.1214476879-14.818249429-23.1386099262-13.8688570315-20.9989439328-40,.85,1.00,None),
 ('联营合营',101.381690627,.80,.95,4.2060557218),
]
# 其他子股主要成熟道路、基金和东深；按成本基数5%正常化收益，NAV不叠加合并母权益差。
EQUITY=[(n,b,l,h,b*.05 if e is None else e) for n,b,l,h,e in EQUITY]
# 应收股利只作为期初应收回收，不重复计利润；其余借款本金含对大邑的独立债权。
DIV_RECEIVABLE=1.7718098104
LOANS=[('大邑',25.4323177074,.025,10),('其他内部及应收',131.550210474-DIV_RECEIVABLE-25.4323177074,.03,8)]
PROJECT_REV=[60264,65932,72304,74270,76290,78364,80494,82876,76398,78251,89055,91215,93642,95714,97831,99996,102208,104706,96026,97973,110927,113035,115296,116336,97951]
PROJECT_CF=[42795,46845,51423,28669,53924,55227,54866,53572,1675,8293,57028,58236,59622,33181,61909,63090,64295,65690,2316,8582,68942,70031,71217,37608,30168]
# 可研经营现金已扣税和周期大修；财务测算的建设期利息不得再混入企业现金。
# 最新预算余44.26包含融资利息；模型分开纯建设与母融资表实际利息。
BUDGET_CAPEX=[24,20.26,0,0,0]
# 可研总投资68.7546与纯建设65.7151之差3.0395为建期息；按比例剔除未来预算中的建期息，母融资表另付实际利息。
CAPEX=[x*(1-3.0395/68.7546) for x in BUDGET_CAPEX]
DIVS=[.40,.40,.39,.39,.38]

def pv(flows,rate,start=0): return sum(x['amount']/(1+rate)**(x['t']-start) for x in flows if x['t']>start)
def loan_value(principal,coupon,years,rate):
 return principal*(coupon*sum((1+rate)**(-i) for i in range(1,years+1))+(1+rate)**(-years))
def run(side='low', road_cash_scale=1., project_volume=None, project_delay=0, equity_scale=1., investment_extra=0.):
 hi=side=='high'; rate=.058 if hi else .064; growth=.008 if hi else 0.;maint=8 if hi else 8.5
 loan_rate=.045 if hi else .055; volume=(.95 if hi else .90) if project_volume is None else project_volume
 routeflows=[];byroute=[];book_remaining=[]
 for name,rev,expiry in ROADS:
  years=(datetime.date.fromisoformat(expiry)-ASOF).days/365.25
  basis=ROAD_TAX_BASIS*rev/ROAD_REVENUE
  depreciation=basis/years
  f=[]
  for t in range(1,30):
   fraction=max(0,min(1,years-(t-1)))
   if not fraction: continue
   sales=rev*(1+growth)**(t-1)*fraction
   costs=(7.8594*1.03+.723*1.025+maint+1.5+.5)*rev/97.1737*1.025**(t-1)*fraction
   dep=depreciation*fraction
   tax=max(0,sales-costs-dep)*.25
   f.append({'t':t,'amount':(sales-costs-tax)*road_cash_scale,'sales':sales,'costs':costs,'depreciation':dep,'tax':tax})
  byroute.append({'name':name,'tax_basis':basis,'expiry':expiry,'flows':f,'value':pv(f,rate),'year5_value':pv(f,rate,5)})
 for t in range(1,30):
  rows=[x for route in byroute for x in route['flows'] if x['t']==t]
  if rows:routeflows.append({'t':t,'amount':sum(x['amount'] for x in rows)})
 project=[]
 for i,(cf,rev) in enumerate(zip(PROJECT_CF,PROJECT_REV)):
  # 每少1元含税收费，按9%VAT及25%所得税近似少0.75/1.09元经营现金。
  # 可研大修成本保持不变，低端不把车少等同维护少。
  project.append({'t':3+i+project_delay,'amount':cf/10000-(1-volume)*rev/10000*.75/1.09})
 project_all=project+[{'t':1,'amount':-CAPEX[0]},{'t':2,'amount':-CAPEX[1]}]
 eq=[]
 for name,b,l,h,earn in EQUITY:
  multiple=h if hi else l
  eq.append({'name':name,'book_basis':b,'multiple':multiple*equity_scale,'value':b*multiple*equity_scale,'normal_earnings':earn})
 eqvalue=sum(x['value'] for x in eq)
 loans=[{'name':n,'principal':b,'coupon':c,'years':y,'value':loan_value(b,c,y,loan_rate)} for n,b,c,y in LOANS]
 loanvalue=sum(x['value'] for x in loans)
 other=OTHER_ASSETS*(.9 if hi else .75)
 fixedother=20 if hi else 15
 roads=pv(routeflows,rate);proj=pv(project_all,rate)
 equity=roads+proj+eqvalue+loanvalue+DIV_RECEIVABLE+other+fixedother+CASH-REQUIRED_CASH+TRADING-OTHER_LIABS-DEBT-PERP-OLD_PAY
 # 母公司五年资金与组合资本；对子支持和新增股权本金同时增加资产，不视为损耗。
 fund=[];bdebt=DEBT;cash=CASH-OLD_PAY;portfolio_book=[x['book_basis'] for x in eq]
 retained=133.60290748;newloan=0;new_equity=0
 for t in range(1,6):
  roadrow=[x for ro in byroute for x in ro['flows'] if x['t']==t]
  roadcash=sum(x['amount'] for x in roadrow)
  dep=sum(x['depreciation'] for x in roadrow)
  projectcash=sum(x['amount'] for x in project if x['t']==t)
  interest=bdebt*.027
  loan_interest=sum(x['principal']*x['coupon'] for x in loans)+newloan*.03
  # 股权当年盈利保持初始各项可持续利润，新增股权回报5%；不以NAV倍数创造会计盈利。
  earnings=[x['normal_earnings'] for x in eq]
  equity_earn=sum(earnings)+new_equity*.05
  upstream=3.5 if t<=2 else (3.8 if t==3 else 4.)
  # 首年3.5含已确认应收1.7718的到账，只有新增部分减少本期股权净值。
  current_upstream=upstream-(DIV_RECEIVABLE if t==1 else 0)
  principal_support=[4,4,3,3,2][t-1]+investment_extra
  eq_invest=1.
  # 母直接运营和贷款利息均税后；债务利息税盾单列；永续无税盾。
  operating=roadcash+projectcash+loan_interest*.75+interest*.25
  dividend=DIVS[t-1]*SHARES
  old_construction_payment=OLD_CONSTRUCTION_PAYABLE/2 if t<=2 else 0
  uses=interest+6.232+CAPEX[t-1]+old_construction_payment+3+principal_support+eq_invest+dividend
  net_borrow=3-cash-operating-upstream+uses
  close=bdebt+net_borrow
  # 子权益已经扣内部贷款；增加内部贷款不再增加子股权益。
  totalearn=sum(earnings)
  for j in range(len(portfolio_book)):
   portfolio_book[j]+=earnings[j]-current_upstream*(earnings[j]/totalearn)
  new_equity+=eq_invest+(new_equity*.05)
  newloan+=principal_support
  # 母法定利润仅包含普通经营及可识别投资确认，未将全部子留存入母利润。
  mother_profit=roadcash-dep+projectcash-max(0,68.34/25 if t>=3 else 0)-interest*.75+loan_interest*.75+6.1
  retained+=mother_profit*.9-dividend-6.232
  assert abs(cash+operating+upstream+net_borrow-uses-3)<1e-8
  fund.append(dict(year=t,road_cash=roadcash,project_cash=projectcash,ordinary_interest=interest,interest_tax_shield=interest*.25,loan_interest=loan_interest,upstream=upstream,current_year_upstream=current_upstream,perpetual_interest=6.232,project_capex=CAPEX[t-1],old_construction_payment=old_construction_payment,other_capex=3,internal_support=principal_support,new_equity=eq_invest,dividend=dividend,net_borrow=net_borrow,closing_debt=close,closing_cash=3,mother_profit_proxy=mother_profit,mother_retained_profit=retained,portfolio_equity_book=sum(portfolio_book)+new_equity,internal_loan_principal=sum(x['principal'] for x in loans)+newloan))
  bdebt=close;cash=3
 # Other capex3/year replaces consumed nonroad fixed assets3/year, no free asset accumulation.
 eq5=sum(v*x['multiple'] for v,x in zip(portfolio_book,eq))+new_equity*(.85 if not hi else 1.)
 loan5=sum(loan_value(x['principal'],x['coupon'],x['years']-5,loan_rate) for x in loans)+loan_value(newloan,.03,8,loan_rate)
 road5=pv(routeflows,rate,5);proj5=pv(project,rate,5)
 terminal=road5+proj5+eq5+loan5+other+fixedother+3-REQUIRED_CASH+TRADING-(OTHER_LIABS-OLD_CONSTRUCTION_PAYABLE)-bdebt-PERP
 return {'side':side,'parameters':dict(rate=rate,growth=growth,maintenance=maint,loan_rate=loan_rate,project_volume=volume),'roads':byroute,'road_flows':routeflows,'road_value':roads,'project_flows':project_all,'project_value':proj,'equity_portfolio':eq,'equity_portfolio_value':eqvalue,'loans':loans,'loan_value':loanvalue,'other_assets':other,'other_liabilities':OTHER_LIABS,'current_equity':equity,'current_per_share':equity/SHARES,'funding':fund,'year5_bridge':dict(roads=road5,project=proj5,equity_portfolio=eq5,loans=loan5,other_assets=other,other_fixed=fixedother,cash=0,required_operating_cash=3,trading=TRADING,other_liabilities=OTHER_LIABS-OLD_CONSTRUCTION_PAYABLE,ordinary_debt=bdebt,perpetual=PERP),'terminal_equity':terminal,'terminal_per_share':terminal/SHARES}
low=run('low');high=run('high')
# 辅助法使用已实现普通EPS作独立历史锚，不把道路税盾的直线代理当会计盈利事实。
# H1机械年化仅是弱边界，FY2025为历史全年参考；两者不预设新项目全部兑现。
aux_profit_low=.263*2*SHARES
aux_profit_high=.545*SHARES
auxiliary={'eps_2026_h1':.263,'eps_2025_fy':.545,
 'ordinary_profit_low':aux_profit_low,'ordinary_profit_high':aux_profit_high,
 'payout_low':.75,'payout_high':.80,'equity_cost_low':.11,'equity_cost_high':.10,'growth_low':-.01,'growth_high':0.,
 'low_per_share':aux_profit_low/SHARES*.75*.99/(.11+.01),
 'high_per_share':aux_profit_high/SHARES*.80/.10}
out={'units':'亿元、亿股、元/股','shares':SHARES,'low':low,'high':high,'sensitivity':{'road_cash_minus10':run('low',road_cash_scale=.9),'equity_recovery_minus10':run('low',equity_scale=.9),'project_volume_75':run('low',project_volume=.75),'project_delay_2':run('low',project_delay=2),'extra_support_3_per_year':run('low',investment_extra=3)},'distributions':DIVS,'auxiliary':auxiliary}
# 算术与守恒特例，不依赖估值范围。
assert abs(pv([{'t':1,'amount':11}],.1)-10)<1e-10
assert abs(loan_value(100,.05,8,.05)-100)<1e-9
assert len(PROJECT_CF)==len(PROJECT_REV)==25
assert all(x['mother_retained_profit']>0 for x in low['funding']+high['funding'])
for scen in [low,high]:
 assert abs(scen['project_value']-pv(scen['project_flows'],scen['parameters']['rate']))<1e-8
 assert not any(x['amount'] for r in scen['roads'] for x in r['flows'] if x['t']>math.ceil((datetime.date.fromisoformat(r['expiry'])-ASOF).days/365.25))
 # 五年前后同一项目和道路现金严格分解。
 r=scen['parameters']['rate']
 assert abs(scen['road_value']-sum(x['amount']/(1+r)**x['t'] for x in scen['road_flows'] if x['t']<=5)-scen['year5_bridge']['roads']/(1+r)**5)<1e-8
(P/'2026-H1-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'current':[low['current_per_share'],high['current_per_share']],'terminal':[low['terminal_per_share'],high['terminal_per_share']],'road':[low['road_value'],high['road_value']],'project':[low['project_value'],high['project_value']],'equity_portfolio':[low['equity_portfolio_value'],high['equity_portfolio_value']],'loans':[low['loan_value'],high['loan_value']],'debt5':[low['funding'][-1]['closing_debt'],high['funding'][-1]['closing_debt']],'sens':{k:[v['current_per_share'],v['terminal_per_share']] for k,v in out['sensitivity'].items()}},ensure_ascii=False,indent=2))
