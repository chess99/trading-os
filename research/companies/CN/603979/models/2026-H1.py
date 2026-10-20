"""金诚信：亿元、万吨、美元/吨；标准库；预算而非公司指引。"""
import json
from pathlib import Path
N=19
SHARES=6.23793+4.95824/11.12 # 旧债转股、新债现金偿还
FX=7.0
Q={
 'Dikulushi':[1.2,.9,.15],
 'Lonshi西':[4,3.8,3.4,2.5,1.5,1,.5],
 'Lonshi东':[0,0,0,1.8,4,6,8,8,8,8,8,8,7,5,3],
 'Lubambe':[2.6,3,3.25,3.25,3.25,3.25,1.8],
 'Alacran':[0,0,1,2,2.5,2.5,2.5,2.5,2.5,2.5,2.5,2.5,2.5,2.5,2.5]}
COST={'Dikulushi':4500,'Lonshi西':3600,'Lonshi东':4200,'Lubambe':6500,'Alacran':4900}
TAX={'Dikulushi':.30,'Lonshi西':.30,'Lonshi东':.30,'Lubambe':.30,'Alacran':.35}
MAINT={'Dikulushi':400,'Lonshi西':400,'Lonshi东':500,'Lubambe':650,'Alacran':450}
# 成本内不含折旧；税盾按经济折耗估算，固定资产折旧不重复计现金支出
DEPR={'Dikulushi':350,'Lonshi西':450,'Lonshi东':800,'Lubambe':600,'Alacran':700}
CAP={'Dikulushi':[0]*3+[.5], 'Lonshi西':[0]*7+[.8],
 'Lonshi东':[12,13,12,7.419877]+[0]*11+[1.2],
 'Lubambe':[1.48995]+[0]*6+[.6], 'Alacran':[14,15.428]+[0]*13+[.8]}
DPS=[.4,.4,.5,.6,.7]
INIT_CASH=57.1914+8-4.117
INIT_DEBT=64.4393-4.9441437702+(19.9978-19.5413171043)
# 10亿元经营现金独立保留；当期投资收益不计入矿服经营利润
INIT_BRIDGE=INIT_CASH-INIT_DEBT-10-1.1128

def pv(cf,r,start=1): return sum(v/(1+r)**t for t,v in enumerate(cf,start))
def run(price=8750,r=.105,service_margin=.2475,cost_mult=1,cap_mult=1,delay=0,cycle_drop=0,minority_funding=True):
 rows=[]; parts={};details={}
 for name,q0 in Q.items():
  q=([0]*delay+q0 if name in ['Lonshi东','Alacran'] else q0)[:N]
  q=q+[0]*(N-len(q)); ca=CAP[name]+[0]*(N-len(CAP[name]));
  if delay and name in ['Lonshi东','Alacran']:
   closeidx=15; ca[closeidx+delay]=ca[closeidx]; ca[closeidx]=0
  cf=[];detail=[]
  for i,qty in enumerate(q):
   rev=qty*(price-(cycle_drop if i<3 else 0))*FX/10000
   operating=qty*COST[name]*cost_mult*FX/10000
   depreciation=qty*DEPR[name]*FX/10000
   tax=max(0,rev-operating-depreciation)*TAX[name]
   maintain=qty*MAINT[name]*FX/10000
   cash=rev-operating-tax-maintain-ca[i]*cap_mult
   cf.append(cash);detail.append(dict(qty=qty,revenue=rev,cost=operating,tax=tax,maintenance=maintain,development_and_closure=ca[i]*cap_mult,fcff=cash))
  if name=='Alacran': cf=[v*.975 for v in cf]
  if name in ['Dikulushi','Lonshi西','Lonshi东']:
   ownership=.9 if name=='Dikulushi' else .95
   cf=[(d['revenue']-d['cost']-d['tax']-d['maintenance'])*ownership-d['development_and_closure']*(ownership if minority_funding else 1) for d in detail]
  parts[name]=cf;details[name]=detail
 service=[];service_rows=[]
 for i in range(N):
  revenue=69*(1.04**min(i,4))*(1.02**max(0,i-4))
  gross=revenue*service_margin; overhead=revenue*.075; ebit=gross-overhead
  tax=ebit*.25; depreciation=revenue*.065
  capex=revenue*.075+(1.6 if i<5 else 0)
  wc=(revenue-(66.13 if i==0 else service_rows[-1]['revenue']))*.30
  cf=ebit-tax+depreciation-capex-wc
  service.append(cf);service_rows.append(dict(revenue=revenue,gross=gross,overhead=overhead,tax=tax,depreciation=depreciation,capex=capex,wc=wc,fcff=cf))
 parts['矿服']=service
 # 归属普通股南区净现金0.5，北区前两年资本合计3、Y3起净增0.6；泰睿支持/退出Y1-2共2.5；有限磷矿期15年
 other=[-.5,-2,.8,1.1,1.1]+[1.1]*10+[0,-.3]+[0]*(N-17)
 parts['磷矿及泰睿']=other
 total=[sum(v[i] for v in parts.values()) for i in range(N)]
 # 矿服Y6起成熟2%增长；所有矿山显性到退出，不用矿业永续
 stv=service[5]/(r-.02)
 enterprise=pv(total[:5],r)+stv/(1+r)**5+sum(pv(v[5:],r,start=6) for k,v in parts.items() if k!='矿服')
 # 外部债权已包含在INIT_DEBT；少数残余扣20% Lub项目正值上界，不再扣同一外部贷款第二次
 minority=.20*max(0,pv(parts['Lubambe'],r)-7.0627-2.7584)
 redemption_premium=2.3997/(1+r)**5
 value=(enterprise+INIT_BRIDGE-minority-redemption_premium)/SHARES
 tv=stv+sum(pv(v[5:],r) for k,v in parts.items() if k!='矿服')
 # 集团现金守恒：必要现金10，剩余现金利息2%，债务利率5%，税盾25%；缺口正常项目借款补足
 cash=INIT_CASH;debt=INIT_DEBT;fund=[];parent_cash=17.0785-4.117;parent_profit=26.4545-4.117;parent_rows=[]
 for i in range(5):
  income=max(0,cash-10)*.02*.75;interest=(max(0,debt-19.9978)*.055+19.9978*[.003,.006,.01,.015,0][i])*.75
  # 外部少数现金按正现金20%/2.5%预算，避免集团FCFF全部归母
  minority_paid=0 # 已有股东贷款优先，前五年不预算少数股权派息
  distribution=SHARES*DPS[i]
  before=cash;olddebt=debt
  cash+=total[i]+income-interest-minority_paid-distribution
  borrowed=max(0,10-cash);cash+=borrowed;debt+=borrowed
  redeemed=0
  if i==4:
   redeemed=19.9978;cash-=22.3975;debt-=redeemed
   extra=max(0,10-cash);cash+=extra;debt+=extra;borrowed+=extra
  assert abs(cash-before-total[i]-income+interest+minority_paid+distribution-borrowed+(22.3975 if i==4 else 0))<1e-8
  # 母公司：净矿服及管理现金2亿元，新上划2/2/3/4/5亿；第一年应收股息2.3054仅收现不计新利润
  upstream=[2,2,4,6,8][i]; receivable=2.3054 if i==0 else 0; support=[3,3,1,0,0][i]
  parent_cash+=-1+upstream+receivable-distribution-support
  parent_profit+=-1+upstream-distribution
  parent_rows.append(dict(year=i+1,new_upstream=upstream,net_own_cash=-1,project_support=support,old_receivable_collection=receivable,distribution=distribution,cash=parent_cash,distributable_profit=parent_profit))
  fund.append(dict(year=i+1,opening_cash=before,opening_debt=olddebt,fcff=total[i],financial_income=income,after_tax_interest=interest,minority_paid=minority_paid,dividend=distribution,new_debt=borrowed,redeemed_principal=redeemed,cash=cash,debt=debt))
 minority5=minority*(1+r)**5 # 未付少数权利随时间承接，不将其默认为消失
 endbridge=cash-debt-10-1.1128-minority5
 tv_equity=(tv+endbridge)/SHARES
 # 辅助法：独立按普通股12%资本成本折现实际分红及未来残余经营/金融权益
 auxiliary=pv(DPS,.12)+tv_equity/(1.12**5)
 assert sum(Q['Dikulushi'])<=2.7
 assert sum(Q['Lonshi东'])<=2504.56*.0358*.9
 assert all(x['cash']>=10-1e-8 for x in fund)
 assert all(x['cash']>=0 and x['distributable_profit']>=0 for x in parent_rows)
 return dict(price=price,rate=r,shares=SHARES,initial_bridge=INIT_BRIDGE,enterprise_value=enterprise,minority=minority,premium_pv=redemption_premium,value_per_share=value,terminal_ev=tv,terminal_equity_per_share=tv_equity,end_bridge=endbridge,auxiliary_value=auxiliary,fcff=total,parts=parts,mine_details=details,service_details=service_rows,financing=fund,parent=parent_rows,terminal_contribution=tv/(1+r)**5/enterprise)

assert abs(pv([110],.1)-100)<1e-10
assert abs(pv([0,121],.1)-100)<1e-10
low=run(8500,.11,.24);high=run(9000,.10,.255);base=run()
scenarios={'minority_no_funding_no_recovery':run(minority_funding=False), 'cycle_three_years':run(cycle_drop=1500), 'optimistic_copper':run(price=9500), 'copper_minus_1000':run(7750), 'operating_cost_plus_10pct':run(cost_mult=1.1), 'development_plus_20pct':run(cap_mult=1.2), 'two_year_delay':run(delay=2)}
out=dict(units='亿元、亿股、万吨；USD/t铜净实现',base=base,low=low,high=high,sensitivities={k:dict(value_per_share=v['value_per_share'],delta=v['value_per_share']-base['value_per_share'],minimum_parent_cash=min(x['cash'] for x in v['parent'])) for k,v in scenarios.items()},assumptions=dict(Q=Q,COST=COST,TAX=TAX,MAINT=MAINT,DEPR=DEPR,CAP=CAP,DPS=DPS))
Path(__file__).with_name('2026-H1-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(json.dumps({k:{x:out[k][x] for x in ['value_per_share','terminal_equity_per_share','auxiliary_value','fcff','end_bridge','terminal_contribution']} for k in ['low','base','high']},ensure_ascii=False,indent=2));print(out['sensitivities'])
