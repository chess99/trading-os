"""宇通客车2026-H1；金额亿元、股数亿股。仅标准库，无网络。"""
import json
from pathlib import Path
from math import isclose
S=22.13939223
CASH=125.82
MINORITY_ASSET=2.4095452897
RISK_ASSETS=7.5007720746+14.3736552545+5.9
DIV=[1.60,1.65,1.70,1.75,1.80]
PARAMS={
 'low':dict(domestic=150,export=210,other=49,dm=.19,em=.28,om=.15,opex=.12,reserve=65,reinvest=3.5,growth=.02,rate=.10,asset_factor=.7),
 'base':dict(domestic=154,export=220,other=49,dm=.19,em=.285,om=.15,opex=.119,reserve=60,reinvest=3.5,growth=.03,rate=.095,asset_factor=.8),
 'high':dict(domestic=155,export=225,other=49,dm=.195,em=.29,om=.15,opex=.118,reserve=55,reinvest=4,growth=.035,rate=.09,asset_factor=.9)}
def compute(p):
 dividends=p.get('dividends',DIV)
 rev=p['domestic']+p['export']+p['other']
 gross=p['domestic']*p['dm']+p['export']*p['em']+p['other']*p['om']
 profit=(gross-rev*p['opex']-1)*.85-.4
 fcf=profit-p['reinvest']
 flows=[fcf*(1+p['growth'])**i for i in range(5)]
 terminal=flows[-1]*1.02/(p['rate']-.02)
 excess=CASH-MINORITY_ASSET-p['reserve']
 risk=RISK_ASSETS*p['asset_factor']
 adjustment=excess+risk
 tvpv=terminal/(1+p['rate'])**5
 op_pv=sum(x/(1+p['rate'])**(i+1) for i,x in enumerate(flows))+tvpv
 balances=[];bal=excess
 for i,x in enumerate(flows):
  old=bal;bal=old*1.015+x-dividends[i]*S
  assert isclose(bal,old+old*.015+x-dividends[i]*S)
  balances.append(bal)
 terminal_low=(flows[-1]*1.02/(.10-.02)+bal+risk)/S
 terminal_high=(flows[-1]*1.02/(.09-.02)+bal+risk)/S
 return dict(parameters=p,reinvestment_schedule=[p['reinvest']*(1+p['growth'])**i for i in range(5)],profit_schedule=[profit*(1+p['growth'])**i for i in range(5)],reserve_schedule=[p['reserve']*(1+p['growth'])**i for i in range(6)],incremental_return=(profit*((1+p['growth'])**4-1))/sum(p['reinvest']*(1+p['growth'])**i for i in range(1,5)),revenue=rev,gross_profit=gross,operating_common_profit=profit,fcfe_first=fcf,fcfe=flows,excess_cash=excess,risk_asset_value=risk,net_adjustment=adjustment,operating_pv=op_pv,value_per_share=(sum(dividends[i]*S/(1+p['rate'])**(i+1) for i in range(5))+(terminal+bal+risk)/(1+p['rate'])**5)/S,terminal_operating_value=terminal,terminal_pv_share=tvpv/op_pv,annual_cash_balances=balances,year5_terminal_range=[terminal_low,terminal_high],aux_cash_cap_range=[(fcf*13+adjustment)/S,(fcf*15+adjustment)/S])
def pv_recipe(p,label):
 z=compute(p)
 return dict(label=label,type='pv',cashflows=[dict(t=i+1,amount=x*S) for i,x in enumerate(DIV)],terminal=dict(t=5,amount=z['terminal_operating_value']+z['annual_cash_balances'][-1]+z['risk_asset_value']),rate=p['rate'],net_adjustment=0,shares=S,expected_per_share=z['value_per_share'])
def run():
 core={k:compute(v) for k,v in PARAMS.items()}
 base=PARAMS['base'];dividends=DIV;sens={}
 for key,patch in {'export_margin_minus_3pp':{'em':base['em']-.03},'cost_of_equity_plus_1pp':{'rate':base['rate']+.01},'cash_reserve_plus_10':{'reserve':70},'net_reinvestment_plus_2':{'reinvest':5.5}}.items():
  v=compute(dict(base,**patch));sens[key]=dict(value=v['value_per_share'],delta=v['value_per_share']-core['base']['value_per_share'])
 # 额外损失不改变已冻结股息时，先减少现金池，随后体现在终值。
 for key,shocks in {'extra_warranty':{1:5,2:5},'arbitration_20':{1:20},'finance_deposit_20pct':{1:28.22*.2},'risk_assets_zero':{5:core['base']['risk_asset_value']}}.items():
  loss=sum(amount*1.015**(5-t) for t,amount in shocks.items())/1.095**5/S
  sens[key]=dict(value=core['base']['value_per_share']-loss,delta=-loss)
 # 完整经济路径：弱周期两年现金下滑后恢复；永久结构压力改变收入、毛利、费用和再投资。
 b=core['base'];weak_cf=[b['fcfe'][0]*.70,b['fcfe'][1]*.85,*b['fcfe'][2:]]
 weak_bal=b['excess_cash']
 for i,x in enumerate(weak_cf):weak_bal=weak_bal*1.015+x-dividends[i]*S
 weak=(sum(dividends[i]*S/1.095**(i+1) for i in range(5))+(b['terminal_operating_value']+weak_bal+b['risk_asset_value'])/1.095**5)/S
 structure=compute(dict(base,domestic=145,export=190,em=.25,opex=.125,reinvest=5,growth=0,rate=.105,reserve=70,asset_factor=.6,dividends=[1.0]*5))
 upside=compute(dict(base,export=245,em=.30,opex=.117,reinvest=4,growth=.04,rate=.09))
 zero={'cashflows':sum(10/1.1**i for i in range(1,6))+100/1.1**5,'expected':100}
 assert isclose(zero['cashflows'],zero['expected'])
 assert all(isclose(z['profit_schedule'][i]-z['reinvestment_schedule'][i],z['fcfe'][i]) for z in core.values() for i in range(5))
 assert len(DIV)==5 and all(min(z['annual_cash_balances'])>0 for z in core.values())
 # 原模型的低现金桥可独立复现。
 assert isclose(25+sum(42*1.04**i for i in range(5))-S*10.5,20.021929105)
 out=dict(units='亿元、亿股、元/股',shares=S,distributions=DIV,core=core,sensitivities=sens,scenarios=dict(cyclical_weak=weak,structural=structure,upside=upside),special_case=zero,asset_bridge=dict(cash_like=CASH,minority_reservation=MINORITY_ASSET,risk_assets_book=RISK_ASSETS,lease_treatment='所有租赁按经营费用及正常现金支付，不另扣本金',warranty_treatment='正常质保支付包含在经营利润现金转换中；不另扣52.07亿元准备，不给准备增长融资收益',risk_asset_scope='其他权益工具+其他非流动金融资产+九鼎租赁减值后5.90；合营与其余经营投资包含经营路径'),independent_recipes=[pv_recipe(PARAMS['low'],'核心下端'),pv_recipe(dict(base,em=.255),'海外毛利下降3个百分点')])
 Path(__file__).with_name('2026-H1-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:dict(value=v['value_per_share'],profit=v['operating_common_profit'],fcf=v['fcfe_first'],cash=v['excess_cash'],asset=v['risk_asset_value'],terminal=v['year5_terminal_range']) for k,v in core.items()},ensure_ascii=False,indent=2));print(json.dumps(sens,indent=2));print('scenarios',weak,structure['value_per_share'],upside['value_per_share'])
if __name__=='__main__':run()
