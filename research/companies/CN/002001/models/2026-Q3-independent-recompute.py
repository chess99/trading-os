#!/usr/bin/env python3
"""Independent recursion: loads output, never imports production functions."""
import json, pathlib, math
root=pathlib.Path(__file__).resolve().parent
o=json.loads((root/'2026-Q3-output.json').read_text()); checked=0; biggest=0

def close(a,b):
 global checked,biggest
 checked+=1;biggest=max(biggest,abs(a-b));assert abs(a-b)<1e-8,(a,b)
def audit(z):
 s=z['inputs'];f=z['common_allocation'];n=30.7342168
 pc=10.7417255915;sc=(88.8501376416+29.9034945546)*f-pc
 pr=58.2620187972;sr=s['sub_retained0'];ps=15.45453678;ss=s['sub_reserve0'];recv=0
 pd=52*f;sd=(80.3851060175-52)*f;revenues=s['revenues'][:];divs=[]
 for t in range(1,11):
  i=t-1
  if t>1:
   revenues=[revenues[j]*(1+(s['growth'][j] if t<=5 else min(.025,s['growth'][j]))) for j in range(4)]
  gross=sum(revenues[j]*(s['margins'][j]-(s['permanent_margin_cut'] if j==0 else 0)) for j in range(4))
  op=(gross-sum(revenues)*s['expense'])*.85*f*s['early_profit_multipliers'][i]
  pp=op*.08-pd*s['debt_rate']*.85+max(pc,0)*s['fin_yield']
  sp=op*.92-sd*s['debt_rate']*.85+max(sc,0)*s['fin_yield']
  sadd=min(max(0,sp+min(0,sr))*.1,max(0,11/2-ss))
  sr+=sp-sadd;ss+=sadd
  pf=pp-.8-s['parent_extra_payment'];sf=sp-(s['net_invest'][i]*f-.8)+s['assoc_dividend']*f
  pm=3*f*1.02**i+pd*max(0,t-5)/5;sm=12*f*1.02**i+sd*max(0,t-5)/5
  want=(27+2*i)*s['early_profit_multipliers'][i] if t<=5 else (35*1.02**(t-5) if s['slow_capital_return'] else max(0,sf)+.18*max(0,sc-sm))
  decl=min(max(0,sr),max(0,sc+sf-sm-recv),max(0,want))
  arrived=recv+decl*(1-s['cash_lag']);recv=decl*s['cash_lag'];sc+=sf-arrived;sr-=decl
  padd=min(max(0,pp+decl+min(0,pr))*.1,max(0,30.7342168/2-ps))
  pr+=pp+decl-padd;ps+=padd
  wantdiv=s['payout_per_share'][i]*n if t<=5 else (1.15*n*1.02**(t-5) if s['slow_capital_return'] else max(0,pf+arrived)+.18*max(0,pc-pm))
  div=min(max(0,wantdiv),max(0,pr),max(0,pc+pf+arrived-pm-s['repurchase'][i]))
  pc+=pf+arrived-div-s['repurchase'][i];pr-=div;divs.append(div)
  expected={'nopat_common':op,'parent_profit_ex_upstream':pp,'subs_profit':sp,'parent_reserve_add':padd,'subs_reserve_add':sadd,'parent_retained':pr,'subs_retained':sr,'parent_cash':pc,'subs_cash':sc,'ordinary_dividend':div,'declared_upstream':decl,'received_upstream':arrived,'dividend_receivable':recv,'parent_flow':pf,'subs_flow':sf}
  for k,v in expected.items():close(v,z['years'][i][k])
 principal=pc+sc-15*f*1.02**9-pd-sd+12.1871039662*f*s['assoc_recovery']
 released=min(pr+sr,principal) if s['terminal_asset_release'] else 0
 tail=op*(1+s['g'])*(1-s['g']/s['terminal_roic'])/(s['r']-s['g'])
 terminal=tail+released+(principal-released)*(1+s['fin_yield'])**5/(1+s['r'])**5
 v=(sum(d/(1+s['r'])**(i+1) for i,d in enumerate(divs))+terminal/(1+s['r'])**10)/n
 y5=(sum(divs[i]/(1+s['r'])**(i-4) for i in range(5,10))+terminal/(1+s['r'])**5)/n
 close(v,z['value_per_share']);close(y5,z['terminal_y5_per_share']);close(principal,z['financial_assets_after_debt_y10']);close(terminal,z['terminal_y10'])
 return {'value_per_share':v,'year5':y5,'years_checked':10}
results={k:audit(v) for k,v in {**o['cases'],**o['sensitivities']}.items()}
close((90*.45+80*.38)/170,o['nutrition_aggregation']['base_margin'])
close(10+4-3,11);close(sum(10/1.1**i for i in range(1,11))+100/1.1**10,100)
close(10.5542211475+22.0480270428+32.737022807+10+5+.0458350202,80.3851060175)
# Literal legal counterexamples independent of the production helper.
for opening,profit,reserve,capital,want_ret,want_add in [(-3,5,0,10,1.8,.2),(-5,3,0,10,-2,0),(-5,5,0,10,0,0),(0,10,4.9,10,9.9,.1)]:
 available=max(0,profit-max(0,-opening));addition=min(available/10,max(0,capital/2-reserve))
 close(opening+profit-addition,want_ret);close(addition,want_add)
for name,profit,retained,payout,reserve in [('production_parent_loss_carry','parent_profit_ex_upstream','parent_retained','ordinary_dividend','parent_reserve_add'),('production_subs_loss_carry','subs_profit','subs_retained','declared_upstream','subs_reserve_add')]:
 case=o['tests'][name];amount=case[profit]+(case['declared_upstream'] if 'parent' in name else 0)
 close(case[retained],-100+amount);close(case[payout],0);close(case[reserve],0);assert case[retained]<0
counter=o['tests']['production_parent_declaration_legal_counterexample']
close(min(max(0,counter['own_profit']+counter['declared']-3)/10,5),counter['actual_reserve_add'])
print(json.dumps({'status':'passed','comparison_count':checked,'max_absolute_difference':biggest,'cases':results,'source_arithmetic':{'Q3_CFO':52.2761469817-36.4014428294,'nutrition_GP':90*.45+80*.38}},ensure_ascii=False,sort_keys=True,indent=2))
