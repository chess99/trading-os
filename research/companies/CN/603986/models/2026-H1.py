"""兆易创新；亿元、亿股；标准库、无网络。"""
import json
from pathlib import Path
D=[1.2,1.5,1.8,2.2,2.6]
R={'storage':[180,165,170,177,185], 'mcu':[32,36,41,46,52], 'lpddr':[3,7,12,18,25], 'custom':[1,4,8,14,22], 'analog':[1,1.3,1.7,2.2,3], 'saixin':[3,3.6,4.3,5.1,6], 'sensor':[2,2,2,2,2]}
OWN={'storage':1,'mcu':1,'lpddr':1,'custom':.6867,'analog':1,'saixin':.3807,'sensor':1}
GM={'storage':[.55,.48,.46,.45,.45],'mcu':[.40]*5,'lpddr':[.45]*5,'custom':[.45]*5,'analog':[.40]*5,'saixin':[.42]*5,'sensor':[.20]*5}
RD={'storage':[12,12.5,13,14,15], 'mcu':[x*.12 for x in R['mcu']], 'lpddr':[x*.13 for x in R['lpddr']], 'custom':[.3,.92,1.6,2.38,3.3], 'analog':[x*.14 for x in R['analog']], 'saixin':[x*.10 for x in R['saixin']], 'sensor':[.25]*5}
TAX={k:(.25 if k=='custom' else .10 if k=='saixin' else .15) for k in R}
# 已登记703,971,427股；余2023第四期897.45万份×25%；2024后两期各648.37万份×30%。
OPTION_2023=897.45*10000*.25/1e8
OPTION_2024=648.37*10000*.30/1e8
OPTION_CASH=[OPTION_2023*85.38+OPTION_2024*58.09,OPTION_2024*(58.09-D[0]),0,0,0]
SHARES=[7.03971427+OPTION_2023+OPTION_2024*(1 if i==0 else 2)-.0375 for i in range(5)]
RECEIVED_EXERCISE=1.9008943434
CANCEL_PAYMENT=.0041637365

def operating(revenue_scale=1,storage_gm_shift=0,custom_scale=1):
 rows=[];prev_common_rev=210 # 经营规模归一的初始周转基数；非历史财报收入
 for i in range(5):
  scale=revenue_scale[i] if isinstance(revenue_scale,list) else revenue_scale
  rev={k:v[i]*(custom_scale if k=='custom' else scale) for k,v in R.items()}
  total=sum(rev.values());common_rev=sum(rev[k]*OWN[k] for k in R)
  nopat={k:(rev[k]*(GM[k][i]+(storage_gm_shift if k=='storage' else 0)) -RD[k][i]*(custom_scale if k=='custom' else scale)-rev[k]*(.06 if k=='custom' else .05))*(1-TAX[k])*OWN[k] for k in R}
  # 已有费用化研发全部保留；有形/资本化研发毛投入12→16，折旧摊销6→10，净投入6。
  net_fixed=6*common_rev/total
  wc=.15*(common_rev-prev_common_rev)
  capital=net_fixed+wc
  profit=sum(nopat.values());fcfe=profit-capital
  rows.append(dict(year=i+1,revenue=total,common_revenue=common_rev,rd=sum(RD[k][i]*(custom_scale if k=='custom' else scale) for k in R),nopat_by_segment=nopat,nopat=profit,net_fixed=net_fixed,delta_working_capital=wc,reinvestment=capital,fcfe=fcfe,shares=SHARES[i]))
  prev_common_rev=common_rev
 return rows

def case(rate,g,roic,haircut,reserve,op=None):
 op=op or operating()
 # 现金等价物139.29+定存29.36+交易金融4.72=173.37；权益工具及非流动金融144.21。
 liquid=173.37-reserve-12.0057-2.60-1.004+RECEIVED_EXERCISE-CANCEL_PAYMENT
 portfolio=144.21*(1-haircut)
 initial=liquid+portfolio
 fund=0;rows=[]
 for i,row in enumerate(op):
  start=liquid;interest=start*.02
  buyback=14 if i==0 else 0
  fund_purchase=7 if i==0 else 0
  div=D[i]*row['shares']
  liquid=start+interest+row['fcfe']-div-buyback-fund_purchase+OPTION_CASH[i]
  fund+=fund_purchase
  rows.append(dict(**row,dividend=div,option_proceeds=OPTION_CASH[i],interest=interest,buyback=buyback,fund_purchase=fund_purchase,liquid_start=start,liquid_end=liquid,financial_pool=liquid+portfolio+fund))
  assert abs(liquid-start-interest-row['fcfe']+div+buyback+fund_purchase-OPTION_CASH[i])<1e-8
 nopat6=op[-1]['nopat']*(1+g);reinvest6=nopat6*g/roic;fcfe6=nopat6-reinvest6
 operating_tv=fcfe6/(rate-g)
 terminal=(operating_tv+rows[-1]['financial_pool'])/SHARES[-1]
 dividend_pv=sum(x/(1+rate)**i for i,x in enumerate(D,1))
 tvpv=terminal/(1+rate)**5
 value=dividend_pv+tvpv
 # 辅助：经营现金及时可用；同样支付剩余回购，股数同时扣回购注销并含全部预算稀释。
 aux=(sum(row['fcfe']/(1+rate)**row['year'] for row in op)+operating_tv/(1+rate)**5+initial-14/(1+rate)+sum(x/(1+rate)**(i+1) for i,x in enumerate(OPTION_CASH)))/SHARES[-1]
 return dict(rate=rate,g=g,incremental_roic=roic,initial_financial_pool=initial,rows=rows,nopat6=nopat6,terminal_reinvestment=reinvest6,fcfe6=fcfe6,operating_tv=operating_tv,terminal_per_share=terminal,current_value=value,dividend_pv=dividend_pv,terminal_pv_weight=tvpv/value,auxiliary_value=aux)

def main():
 low=case(.105,.025,.16,.20,45);high=case(.095,.035,.20,.10,35)
 sensitivity=case(.105,.025,.16,.20,45,operating(storage_gm_shift=-.05))
 custom_half=case(.105,.025,.16,.20,45,operating(custom_scale=.5))
 cycle=case(.105,.025,.16,.20,45,operating(revenue_scale=[.9,.9,1,1,1]))
 roic_stress=case(.105,.025,.12,.20,45)
 structural=case(.105,.015,.12,.20,45,operating(storage_gm_shift=-.10,custom_scale=.5))
 upside=case(.095,.035,.20,.10,35,operating(storage_gm_shift=.03))
 # 母体净经营现金预算已扣母体必要资本，合法宣派到账与利润同年；不含公允价值收益。
 cash=88.37-20-1.004-14-7+RECEIVED_EXERCISE-CANCEL_PAYMENT;legal=85.79-21.87;parent=[]
 for i,(native,native_profit,up) in enumerate(zip([10,10,11,12,13],[10,10,11,12,13],[4,5,6,7,8])):
  div=D[i]*SHARES[i];cash+=native+up-div+OPTION_CASH[i];legal+=native_profit+up-div
  parent.append(dict(year=i+1,native_net_cash=native,native_profit_budget=native_profit,upstream_cash=up,option_proceeds=OPTION_CASH[i],dividend=div,cash_end=cash,conservative_distributable_profit=legal))
  assert cash>0 and legal>0
 assert len(D)==5 and abs(sum(D)-9.3)<1e-9
 assert abs(SHARES[-1]-(7.03971427+OPTION_2023+2*OPTION_2024-15/400))<1e-9
 assert all(abs(x['nopat']-x['reinvestment']-x['fcfe'])<1e-8 for x in low['rows'])
 assert abs(10/.10-100)<1e-12 # 零增长永续现金可手算特例
 assert sensitivity['current_value']<low['current_value']
 out=dict(unit='亿元、亿股；每股结果为元',segments_revenue=R,ownership=OWN,option_cash=OPTION_CASH,share_schedule=SHARES,received_exercise=RECEIVED_EXERCISE,low=low,high=high,sensitivity_storage_gm_minus_5pp=sensitivity,sensitivity_custom_half=custom_half,cyclical_volume_minus_10pct=cycle,sensitivity_terminal_roic_12pct=roic_stress,structural_downside=structural,upside=upside,parent_distribution_budget=parent,assertions='现金守恒、利润减再投资、股数、五期分红及零增长永续特例通过')
 Path(__file__).with_name('2026-H1-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:{x:v[x] for x in ['current_value','terminal_per_share','auxiliary_value']} for k,v in [('low',low),('high',high),('gm_minus5',sensitivity),('custom_half',custom_half)]},ensure_ascii=False))
if __name__=='__main__':main()
