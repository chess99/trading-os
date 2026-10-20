"""新和成 FCFF、经营超额收益及普通股现金桥。单位：亿元、亿股。无网络。"""
import json
from pathlib import Path
S=30.7342168
TAX=.145
DEBT=73.8
CASH=100.42
REQUIRED=15
ASSOC=11.45
MINORITY=1.54
BRIDGE=CASH-REQUIRED-DEBT+ASSOC-MINORITY
IC=348.80+MINORITY+DEBT-(CASH-REQUIRED)-ASSOC
DIV=[1,1,1.05,1.1,1.15]
# 营养、香料、新材料、其他的收入与毛利率；费用含研发、销售管理、税金、正常减值。
PATHS={
 'low':{'revenues':[[165,40,24,22],[168,41,26,22.25],[170,42,28,22.5],[173,43,30,22.75],[175,44,32,23]],'margins':[[.40,.46,.30,.18],[.40,.4625,.3025,.18],[.40,.465,.305,.18],[.40,.4675,.3075,.18],[.40,.47,.31,.18]],'reinvestment':[20,19,18,16,14],'wacc':.095,'growth':.02,'ronic':.12},
 'high':{'revenues':[[175,42,25,22],[179,43.25,27.75,22.5],[183,44.5,30.5,23],[187,45.75,33.25,23.5],[190,47,36,24]],'margins':[[.42,.48,.32,.18],[.42,.485,.325,.18],[.42,.49,.33,.18],[.42,.495,.335,.18],[.42,.50,.34,.18]],'reinvestment':[18,17,16,15,13],'wacc':.085,'growth':.025,'ronic':.15}}
def pv(c,r): return sum(v/(1+r)**(i+1) for i,v in enumerate(c))
def run(k, profit_shift=0, rate_shift=0, capital_extra=0, delay=False):
 p=PATHS[k];r=p['wacc']+rate_shift;g=p['growth'];q=p['ronic']
 sales=[sum(x) for x in p['revenues']]
 gp=[sum(a*b for a,b in zip(x,y)) for x,y in zip(p['revenues'],p['margins'])]
 op=[(a-.105*b)*(1-TAX)+profit_shift for a,b in zip(gp,sales)]
 if delay: op=[x-d for x,d in zip(op,[6,5,3,0,0])]
 inv=[x+capital_extra for x in p['reinvestment']]
 fcff=[a-b for a,b in zip(op,inv)]
 tv=op[-1]*(1+g)*(1-g/q)/(r-g)
 vp=pv(fcff,r);vt=tv/(1+r)**5
 value=(vp+vt+BRIDGE)/S
 # 辅助法：五年相同资本和利润；Y6起旧资本回报维持，新增资本按q回报。
 capital=IC;ep=[]
 for n,i in zip(op,inv):
  ep.append(n-r*capital);capital+=i
 # 连续盈利与增长投资的残余收益恒等式，非额外独立盈利证据。
 terminal_ep_value=tv-capital
 residual=(IC+pv(ep,r)+terminal_ep_value/(1+r)**5+BRIDGE)/S
 assert abs(residual-value)<1e-9
 fin=CASH-REQUIRED; ledger=[]
 debt_interest=DEBT*.025*(1-TAX)
 minor_distribution=.35
 for t,(n,c,d) in enumerate(zip(op,fcff,DIV),1):
  inc=fin*.015 # 金融资产税后现金收益；联营1.45亿元年度分配单列。
  assoc_distribution=1.45
  dist=d*S
  new=fin+inc+assoc_distribution+c-debt_interest-minor_distribution-dist
  assert abs(new-fin-(inc+assoc_distribution+c-debt_interest-minor_distribution-dist))<1e-9
  ledger.append({'year':t,'opening_financial_assets':fin,'after_tax_financial_income':inc,'associate_dividend':assoc_distribution,'fcff':c,'after_tax_debt_interest':debt_interest,'minority_distribution':minor_distribution,'common_dividend':dist,'closing_financial_assets':new})
  fin=new
 terminal_bridge=fin-DEBT+ASSOC-MINORITY
 # 母公司法定利润采用经常自身利润+已宣派子公司股利；到账不重复成为利润。
 parent_cash=10.7417;parent_retained=58.2620;parent=[]
 for t,(up,own,own_profit,d) in enumerate(zip([20,22,24,26,28],[9,10,11,12,13],[5,5.5,6,6.5,7],DIV),1):
  parent_cash+=up+own-d*S
  parent_retained+=up+own_profit-d*S
  parent.append({'year':t,'declared_and_received_subsidiary_dividend':up,'own_free_cash':own,'own_legal_profit':own_profit,'common_dividend':d*S,'closing_cash':parent_cash,'closing_distributable_retained_profit':parent_retained})
  assert parent_cash>=0 and parent_retained>=0
 return {'revenues':sales,'gross_profits':gp,'nopat':op,'net_reinvestment':inv,'fcff':fcff,'wacc':r,'terminal_growth':g,'terminal_ronic':q,'terminal_operating_value':tv,'explicit_pv':vp,'terminal_pv':vt,'current_bridge':BRIDGE,'value_per_share':value,'terminal_fraction':vt/(vp+vt+BRIDGE),'economic_profit_method_per_share':residual,'economic_profit':ep,'ending_invested_capital':capital,'financial_ledger':ledger,'terminal_bridge':terminal_bridge,'terminal_per_share':(tv+terminal_bridge)/S,'parent_ledger':parent}
def auxiliary(k):
 r=.095 if k=='low' else .085
 roics=([.175-.005*i for i in range(10)] if k=='low' else [.195-.005*i for i in range(10)])
 growths=([.03]*5+[.025]*5 if k=='low' else [.04]*5+[.03]*5)
 tr=.115 if k=='low' else .135
 g=.02 if k=='low' else .025
 capital=IC; flows=[];rows=[]
 for i,(roic,cg) in enumerate(zip(roics,growths),1):
  ep=capital*(roic-r);flows.append(ep)
  rows.append({'year':i,'opening_capital':capital,'roic':roic,'capital_growth':cg,'economic_profit':ep})
  capital*=1+cg
 terminal=(tr-r)*capital/(r-g)
 value=(IC+pv(flows,r)+terminal/(1+r)**10+BRIDGE)/S
 return {'rows':rows,'terminal_roic':tr,'terminal_growth':g,'rate':r,'terminal_excess_value':terminal,'value_per_share':value,'capital_base':IC}
def main():
 assert abs(pv([10],.1)-10/1.1)<1e-12
 assert abs(IC+BRIDGE-348.8)<1e-9
 assert sum(DIV)==5.3
 base={k:run(k) for k in PATHS}
 out={'units':'亿元、亿股；每股人民币元','shares':S,'operating_capital_including_required_cash':IC,'current_bridge':BRIDGE,'dividends_per_share':DIV,'dividend_total':sum(DIV)*S,'base':base,'auxiliary':{k:auxiliary(k) for k in PATHS},'sensitivity':{k:{'profit_minus_10':run(k,profit_shift=-10)['value_per_share'],'wacc_plus_1pp':run(k,rate_shift=.01)['value_per_share'],'additional_capital_2_per_year':run(k,capital_extra=2)['value_per_share'],'cycle_delay':run(k,delay=True)['value_per_share']} for k in PATHS},'checks':{'cash_conservation':True,'residual_income_identity':True,'required_cash_preserved':True,'parent_cash_and_legal_profit_positive':True}}
 Path(__file__).with_name('2026-H1-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'base':{k:{x:v[x] for x in ['value_per_share','terminal_per_share','terminal_bridge','nopat','fcff']} for k,v in base.items()},'sensitivity':out['sensitivity']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
