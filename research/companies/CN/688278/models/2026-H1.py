"""特宝生物；金额亿元、股数亿股。标准库，无网络。"""
import json
from pathlib import Path
D=[.65,.72,.80,.88,.96]
SHARES=4.0818948-.10753+.04544
CONVERT_SHARES=SHARES+15.33266/58.56
BOND=15.33266
COUPONS=[BOND*x for x in [.001,.003,.006,.01,.015]]
REDEMPTION=BOND*1.08  # 第六年108%包含末期2%息，不能另扣一次
INITIAL_NET_FINANCIAL=2.05+15.18
SUBSCRIPTION=1.78
YIELD=.015
BANK_DEBT=7.43
BANK_COST=.03  # 税后融资成本；银行本金在初始净金融桥扣除，正常续作
CASES={
 'low':{'r':.112,'pg':[35,36,36,35.5,35],'gh':[3,4.5,7,9.5,12],'other':[3,3.5,4,4,4], 'nopat':[8.4,8.8,9.1,9.4,9.6], 'da':[1.3,1.6,1.9,2.1,2.2], 'capex':[5,4.5,3.4,2.7,2.4], 'wc':[1.3,1.1,1,.8,.6], 'later':[9.2,9.6,10,10.3,10.5], 'tail_cash':[6.5,3.4,.6], 'tail_g':[-.04,0,-.02]},
 'high':{'r':.10,'pg':[36,38,40,41.5,42],'gh':[4,6.5,10,14.5,20],'other':[3,3.5,4,4,4], 'nopat':[9.2,10.2,11.4,12.7,13.7], 'da':[1.3,1.6,1.9,2.1,2.2], 'capex':[4.8,4.3,3.6,3.2,3], 'wc':[1.1,1,.9,.9,.6], 'later':[10.8,11.6,12.4,13,13.5], 'tail_cash':[8,4.8,.7], 'tail_g':[-.02,0,0]}}
def pv(vals,r,start=1):return sum(v/(1+r)**t for t,v in enumerate(vals,start))
def calc(case,convert=False,tail_shift=0,gh_factor=1,delay=False,treasury=False,profit_haircut=0):
 c=CASES[case];r=c['r'];s=CONVERT_SHARES if convert else SHARES
 if treasury:s+=.10753
 # 敏感性中的GH现金损失：税后贡献率15%/20%，不自动返还已承诺资本。
 margin=.15 if case=='low' else .20
 fc=[n+d-k-w for n,d,k,w in zip(c['nopat'],c['da'],c['capex'],c['wc'])]
 fc=[f-g*margin*(1-gh_factor)-n*profit_haircut for f,g,n in zip(fc,c['gh'],c['nopat'])]
 later=[(v-c['tail_cash'][1]*(1-gh_factor))*(1-profit_haircut) for v in c['later']]
 if delay:
  fc=[fc[0]*.65,fc[1]*.75,fc[2]*.9]+fc[3:]
 cash=INITIAL_NET_FINANCIAL
 rows=[]
 for i,f in enumerate(fc):
  sub=SUBSCRIPTION if i==0 else 0
  interest=(cash+BANK_DEBT)*YIELD-BANK_DEBT*BANK_COST
  coupon=0 if convert else COUPONS[i]
  div=D[i]*s
  end=cash+interest+sub+f-div-coupon
  assert abs(end-cash-interest-sub-f+div+coupon)<1e-10
  rows.append({'year':i+1,'revenue':c['pg'][i]+c['gh'][i]+c['other'][i],'nopat':c['nopat'][i],'da':c['da'][i],'capex':c['capex'][i],'working_capital_addition':c['wc'][i],'operating_cash':f,'opening_net_financial':cash,'net_interest':interest,'subscription':sub,'coupon':coupon,'distribution_total':div,'closing_net_financial':end})
  cash=end
 tail=[a*(1-profit_haircut)*(1+(g+tail_shift))/(r-(g+tail_shift)) for a,g in zip([c['tail_cash'][0],c['tail_cash'][1]*gh_factor,c['tail_cash'][2]],c['tail_g'])]
 op=pv(later,r)+sum(tail)/(1+r)**5
 # Y5现金中的到期准备按债务2%折现一年；经营风险不用于打折固定债务。
 debt=0 if convert else REDEMPTION/1.02
 tv=(op+cash-debt)/s
 value=pv(D,r)+tv/(1+r)**5
 # 独立辅助：第五年维持现有规模的现金收益资本化；WC不再增长，资本化研发和维护不删除。
 ep_cash=c['nopat'][-1]+c['da'][-1]-c['capex'][-1]
 ep_tv=(ep_cash/r+cash-debt)/s
 ep_value=pv(D,r)+ep_tv/(1+r)**5
 return {'shares':s,'rows':rows,'cash_y5':cash,'debt_y5':debt,'operating_value_y5':op,'tail_value_y10':sum(tail),'tail_components':tail,'tv5':tv,'value':value,'terminal_fraction':(tv/(1+r)**5)/value,'tail_fraction':sum(tail)/(1+r)**10/s/value,'ep_cash':ep_cash,'ep_value':ep_value,'ep_tv5':ep_tv,'later_cash':later,'post_redemption_net_financial':cash+(cash+BANK_DEBT)*YIELD-BANK_DEBT*BANK_COST+later[0]-(0 if convert else REDEMPTION)}
def main():
 assert abs(pv([11],.1)-10)<1e-10
 assert abs(pv([1,1],0)-2)<1e-10
 assert abs(sum(COUPONS)+REDEMPTION-BOND*1.115)<1e-10
 assert all(abs(sum(c['tail_cash'])-c['later'][-1])<1e-10 for c in CASES.values())
 out={k:calc(k) for k in CASES}
 out['scenarios']={k:{'cyclical':calc(k,delay=True),'structural':calc(k,gh_factor=.7,profit_haircut=.25,tail_shift=-.02),'optimistic':calc(k,gh_factor=1.2,tail_shift=.01)} for k in CASES}
 out['sensitivities']={k:{'convert':calc(k,convert=True),'gh_30pct_lower':calc(k,gh_factor=.7),'tail_2pp_faster_decay':calc(k,tail_shift=-.02),'two_year_delay':calc(k,delay=True),'treasury_release_no_proceeds':calc(k,treasury=True)} for k in CASES}
 # 永续公式检验：十万期显式现金和闭式尾部一致。
 for k,c in CASES.items():
  for a,g in zip(c['tail_cash'],c['tail_g']):
   explicit=sum(a*(1+g)**t/(1+c['r'])**t for t in range(1,1000))
   assert abs(explicit-a*(1+g)/(c['r']-g))<1e-8
 Path(__file__).with_name('2026-H1-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:{x:out[k][x] for x in ['shares','cash_y5','debt_y5','operating_value_y5','tv5','value','ep_value','tail_fraction','post_redemption_net_financial']} for k in CASES},indent=2))
 print(json.dumps({k:{x:round(y['value'],4) for x,y in out['sensitivities'][k].items()} for k in CASES},indent=2))
if __name__=='__main__':main()
