#!/usr/bin/env python3
"""002463 2026-Q3 owner-value research model. CNY billion except per-share.
No packages/network. Running from any directory writes beside this file.
Every scenario owns operating forecasts, capex, working capital, financing,
parent profit budget and parent cash budget. Budgets are NOT statutory audits.
"""
from pathlib import Path
from copy import deepcopy
import json, math
ROOT=Path(__file__).resolve().parent
INFORMATION_CUTOFF='2026-10-27T11:33:49+00:00'
ACTUAL={
 'cash':6.552840227, 'near_deposits':1.356233971,
 'long_deposits_estimate':0.8, 'minority_opening':0.015815715,
 'debt':4.177908575+4.725179250+0.522261872,
 'net_financial_equity':0.89,
 'fixed_and_prepaid':8.459661726+3.305495382+0.618454834+(3.398620908-0.8),
 'nwc':8.2, 'operating_cash':1.9,
 'legacy_capex_payable_estimate':2.2,
 'parent_cash_estimate':3.8,'parent_debt_estimate':5.2,
 'parent_retained_h1':10.146663766,
 'parent_statutory_reserve_budget_proxy':1.157990517,
 'shares':1.928555322, 'fully_diluted':1.953888787,
 'remaining_options':0.025333465,'first_tranche_remaining':0.010569965,'second_tranche':0.014763500,'exercise_price':19.22,
 'historical_dividend_2025_paid_2026':0.962181769,
}
BUSINESS_BUILD={
 'enterprise_data_pcb':[35.8,44.35,52.25,59.15,64.5],
 'automotive_pcb':[3.2,3.5,3.8,4.1,4.5],
 'industrial_other_pcb':[.55,.60,.65,.75,.80],
 'scrap_other':[1.95,2.05,2.30,2.50,3.20],
 'enterprise_gross_margin':[.44,.435,.42,.405,.39],
 'auto_gross_margin':[.20,.21,.22,.23,.24],
 'industrial_gross_margin':[.35]*5,'scrap_gross_margin':[.20]*5,
 'note':'Independent forward budget, NOT a Q3 segment disclosure. Enterprise/data includes network switching/router, AI/HPC and general servers; no assumed Nvidia/Arista customer identity.'
}
BASE={
 'name':'base',
 'revenue':[41.5,50.5,59,66.5,73,78.8,84.3,89.4,93.9,97.7],
 'ebit_margin':[.285,.285,.28,.27,.26,.25,.24,.235,.23,.225],
 'capex_first5':[7.8,7.2,6.3,5.7,5.3],
 'wc_ratio':[.25,.25,.245,.24,.24,.24,.24,.24,.24,.24],
 'cash_ratio':.05,'tail_fixed_ratio':.60,'depreciation_rate':.07,
 'dividend_budget':[2.2,2.7,3.2,4,5,6,7.5,9,11,13],
 'tax':.15,'common_operating_share':.998,'deposit_yield_net':.015,
 'outside_cash_recovery_budget':1.0,'cash_release_delay':3,'debt_rate':.04,'debt_limit':20,'debt_repay_cash_threshold':.16,
 'parent_profit_share':.60,'parent_wc_share':.65,'parent_capex_share':.50,
 'parent_cash_floor_share':.60,'parent_debt_share':.60,
 'extra_parent_payment':[0]*10,'cash_collection_delay':[0]*10,
 'upstream_dividend_budget':[0]*10,
 'terminal_growth':.025,'terminal_incremental_roic':.18,'discount':.105,
 'scenario_scope':'集团（母公司、黄石、沪利、泰国、胜伟策）高阶板升级与建设；前五年扩产、此后利润和增长渐降；无子公司股利上划依赖。',
 'changed':'独立基准','frozen':'税率/已持有股权资产/已建资本/初始债务和股数均为共同起点',
}
def project(p, actual=None):
 a=deepcopy(ACTUAL if actual is None else actual)
 cash=a['cash']+a['near_deposits']+a['long_deposits_estimate']-a['minority_opening']
 debt=a['debt']; pcash=a['parent_cash_estimate']; pdebt=a['parent_debt_estimate']
 fixed=a['fixed_and_prepaid']; wc=a['nwc']; op_cash=a['operating_cash']
 retained=a['parent_retained_h1']; reserve=a['parent_statutory_reserve_budget_proxy']
 shares=a['fully_diluted']; registered_capital=a['shares']; rows=[]; ever_failed=False
 for i,(rev,margin) in enumerate(zip(p['revenue'],p['ebit_margin'])):
  oldcash,olddebt,oldpcash,oldpdebt=cash,debt,pcash,pdebt
  oldfixed,oldwc,oldopc=fixed,wc,op_cash
  if i<5: capex=p['capex_first5'][i]
  else:
   # Solve closing fixed assets target with half-year depreciation on additions.
   start_ratio=rows[4]['fixed_capital']/rows[4]['revenue']
   gradual_ratio=start_ratio+(p['tail_fixed_ratio']-start_ratio)*(i-4)/5
   target=max(gradual_ratio*rev,oldfixed*(1-p['depreciation_rate']))
   capex=max(0,(target-oldfixed*(1-p['depreciation_rate']))/(1-.5*p['depreciation_rate']))
  dep=p['depreciation_rate']*oldfixed+.5*p['depreciation_rate']*capex
  fixed=oldfixed+capex-dep
  wc=rev*p['wc_ratio'][i]+p['cash_collection_delay'][i]
  dwc=wc-oldwc
  op_cash=rev*p['cash_ratio']; dopc=op_cash-oldopc
  ebit=rev*margin
  nopat=(ebit-max(ebit,0)*p['tax'])*p['common_operating_share']
  interest_tax=p['tax'] if ebit>0 else 0
  settle=a['legacy_capex_payable_estimate']/2 if i<2 else 0
  op_free=nopat+dep-capex-dwc-settle
  fcff=op_free-dopc
  interest=olddebt*p['debt_rate']*(1-interest_tax)
  financial_income=oldcash*p['deposit_yield_net']
  new_registered_shares=a['first_tranche_remaining'] if i==0 else a['second_tranche'] if i==1 else 0
  exercise=new_registered_shares*a['exercise_price']
  registered_capital+=new_registered_shares # registered legal capital budget, separate from fully diluted equity denominator
  # Payer legal-profit budget: parent's own recurring profit; no invented subsidiary reserves.
  pint=oldpdebt*p['debt_rate']*(1-interest_tax)
  pincome=oldpcash*p['deposit_yield_net']
  pprofit=nopat*p['parent_profit_share']-pint+pincome
  # Profit loss consumes the budget first. Statutory reserve stops at 50% registered capital.
  oldretained=retained
  retained+=pprofit
  profit_after_loss_repair=max(0,pprofit+min(oldretained,0))
  reserve_add=min(max(registered_capital*.5-reserve,0),profit_after_loss_repair*.10)
  retained-=reserve_add;reserve+=reserve_add
  parent_operating_cash=(nopat+dep)*p['parent_profit_share']-dwc*p['parent_wc_share']-capex*p['parent_capex_share']-settle*p['parent_capex_share']-pint+pincome-p['extra_parent_payment'][i]
  # Internal dividends zero baseline. Any scenario addition requires independent entity evidence.
  upstream=p['upstream_dividend_budget'][i]
  cash+=op_free-interest+financial_income+exercise
  pcash+=parent_operating_cash+exercise+upstream
  minimum=op_cash; pminimum=minimum*p['parent_cash_floor_share']
  wanted=max(0,p['dividend_budget'][i])
  legal=max(0,retained)
  # Only pay when both parent and group funding suffice within the modeled bank envelope.
  available_debt=max(0,p['debt_limit']-debt)
  payable=min(wanted,legal,max(0,cash-minimum+available_debt),max(0,pcash-pminimum+available_debt))
  need=max(0,minimum+payable-cash,pminimum+payable-pcash)
  draw=min(need,available_debt)
  # Parent-specific draw is allocated there, remaining normal group draw 60% to parent.
  parent_need=max(0,pminimum+payable-pcash)
  pdraw=min(draw,parent_need+max(0,draw-parent_need)*p['parent_debt_share'])
  debt+=draw;cash+=draw;pdebt+=pdraw;pcash+=pdraw
  feasible=not ever_failed and cash-payable>=minimum-1e-8 and pcash-payable>=pminimum-1e-8
  ever_failed=ever_failed or not feasible
  cash-=payable;pcash-=payable;retained-=payable
  # Debt pays down only from funds above a genuine operating + construction buffer.
  repay=min(debt,max(0,cash-max(minimum,rev*p['debt_repay_cash_threshold'])))
  prepay=min(pdebt,repay*p['parent_debt_share'],max(0,pcash-pminimum))
  other_available=max(0,(cash-pcash)-(minimum-pminimum))
  other_repay=min(repay-prepay,other_available,max(0,debt-pdebt))
  # A subsidiary cannot repay debt that only the parent legally owes.
  extra_parent=min(repay-prepay-other_repay,max(0,pdebt-prepay),max(0,pcash-pminimum-prepay))
  prepay+=extra_parent;repay=prepay+other_repay
  cash-=repay;debt-=repay;pcash-=prepay;pdebt-=prepay
  closing_ic=fixed+wc+op_cash
  rows.append(dict(year=i+1,revenue=rev,ebit_margin=margin,ebit=ebit,cash_operating_tax=max(ebit,0)*p['tax'],nopat=nopat,depreciation=dep,capex=capex,
   fixed_capital=fixed,nwc=wc,delta_nwc=dwc,operating_cash=op_cash,delta_operating_cash=dopc,
   legacy_capex_payable_settled=settle,fcff=fcff,op_free=op_free,
   interest_after_tax=interest,financial_income=financial_income,option_cash=exercise,
   debt_draw=draw,debt_repayment=repay,closing_cash=cash,closing_debt=debt,
   dividend=payable,requested_dividend=wanted,dps=payable/shares,shares=shares,registered_capital_budget=registered_capital,profit_after_loss_repair=profit_after_loss_repair,
   parent_profit_budget=pprofit,parent_retained_budget=retained,parent_reserve=reserve,reserve_addition=reserve_add,
   parent_operating_cash=parent_operating_cash,parent_cash=pcash,parent_debt=pdebt,
   parent_debt_draw=pdraw,parent_debt_repayment=prepay,parent_cash_floor=pminimum,
   invested_capital=closing_ic,feasible=feasible,
   cash_conservation_error=cash-(oldcash+op_free-interest+financial_income+exercise+draw-payable-repay),
   parent_cash_conservation_error=pcash-(oldpcash+parent_operating_cash+exercise+upstream+pdraw-payable-prepay),
   profit_budget_error=retained-(oldretained+pprofit-reserve_add-payable)))
  if not feasible: break # stop: subsequent cash flows require a new restructuring authorization
 return rows

def terminal_operating_value(last,p,r=None):
 r=p['discount'] if r is None else r;g=p['terminal_growth']
 # Mature installed capacity can retain a higher average return. Marginal greenfield
 # capital return is separately constrained by the 33bn-RMB project's 13.9% cash IRR / ~15% profit-to-total-investment.
 next_nopat=last['nopat']*(1+g)
 next_reinvestment=next_nopat*g/p['terminal_incremental_roic']
 return (next_nopat-next_reinvestment)/(r-g)

def discounted_value(cashflows, terminal, rate):
 """Production discount chain; unit tests feed hand-computable cases into THIS function."""
 return sum(c/(1+rate)**(i+1) for i,c in enumerate(cashflows))+terminal/(1+rate)**len(cashflows)

def cash_bridge_value(total,required,parent,p,r):
 # Payer-external financial surplus earns deposit yield and is recovered after a
 # separately modeled release delay. This is a valuation assumption, not legal approval.
 outside=max(0,total-parent-required*(1-p['parent_cash_floor_share']))
 release_factor=p['outside_cash_recovery_budget']*((1+p['deposit_yield_net'])/(1+r))**p['cash_release_delay']
 return total-required-outside*(1-release_factor),outside,outside*(1-release_factor)

def value(p,rows=None,r=None,actual=None):
 a=ACTUAL if actual is None else actual
 rows=project(p,a) if rows is None else rows;r=p['discount'] if r is None else r
 if not all(x['feasible'] for x in rows):return {'feasible':False,'reason':'Modeled group/parent funding envelope failed; no retained terminal.'}
 tv=terminal_operating_value(rows[-1],p,r)
 ev=discounted_value([x['fcff'] for x in rows],tv,r)
 cash0=a['cash']+a['near_deposits']+a['long_deposits_estimate']-a['minority_opening']
 liquid0,outside0,haircut0=cash_bridge_value(cash0,a['operating_cash'],a['parent_cash_estimate'],p,r)
 bridge=liquid0-a['debt']+a['net_financial_equity']
 # Options modeled as future fully diluted shares plus actual cash proceeds, not treasury-stock netting.
 optionpv=a['exercise_price']*(a['first_tranche_remaining']/(1+r)+a['second_tranche']/(1+r)**2)
 today=(ev+bridge+optionpv)/a['fully_diluted']
 ev5=discounted_value([x['fcff'] for x in rows[5:]],tv,r)
 x=rows[4];liquid5,outside5,haircut5=cash_bridge_value(x['closing_cash'],x['operating_cash'],x['parent_cash'],p,r)
 eq5=ev5+liquid5-x['closing_debt']+a['net_financial_equity']
 # Same operating path, actual dividend policy, financing and cash retention: useful reconciliation, not another business forecast.
 holdingpv=discounted_value([x['dividend'] for x in rows[:5]],eq5,r)/a['fully_diluted']
 ic1,ic5=rows[0]['invested_capital'],rows[4]['invested_capital']
 return dict(feasible=True,value_per_share=today,enterprise_value=ev,equity_bridge=bridge,option_proceeds_pv=optionpv,
  cash_release_delay=p['cash_release_delay'],initial_outside_parent_financial_cash=outside0,initial_cash_release_discount=haircut0,year5_outside_parent_financial_cash=outside5,year5_cash_release_discount=haircut5,terminal_operating_value_year10=tv,terminal_pv_share=(tv/(1+r)**10)/ev,
  terminal_equity_per_share_year5=eq5/a['fully_diluted'],terminal_ev_year5=ev5,
  policy_reconciled_pv_per_share=holdingpv,
  incremental_return_y1_y5=(rows[4]['nopat']-rows[0]['nopat'])/(ic5-ic1),
  terminal_forward_roic=rows[-1]['nopat']*(1+p['terminal_growth'])/rows[-1]['invested_capital'])

def cases():
 out={'base':deepcopy(BASE)}
 def add(n,**kwargs):
  p=deepcopy(BASE);p['name']=n;p.update(kwargs);out[n]=p
 add('core_low',revenue=[40,47,53.5,59,64,68.5,72.6,76.2,79.3,82],ebit_margin=[.275,.275,.265,.255,.245,.235,.225,.22,.215,.21],discount=.115,terminal_growth=.02,terminal_incremental_roic=.14,dividend_budget=[2.2,2.5,2.9,3.4,4,4.8,5.8,7,8.5,10],changed='高阶迁移较慢、毛利逐年回落更快，资本成本11.5%，永久增长2%；资本开支前五年仍兑现现有计划。')
 add('core_high',revenue=[43,54,65,74,82,89.4,96.6,103.3,109.5,115],ebit_margin=[.30,.30,.295,.285,.275,.265,.255,.25,.245,.24],capex_first5=[8.3,8.2,7.2,6.8,6.3],discount=.10,terminal_growth=.025,terminal_incremental_roic=.20,dividend_budget=[2.2,3,3.8,4.8,6.1,7.5,9,11,13,15],changed='海外量产和高层/HDI升级较顺，容量与营运资金同时增加；利润率仍衰减。')
 add('cyclical',revenue=[34,35,46,56,64,70,75,80,84,87],ebit_margin=[.20,.18,.24,.25,.25,.245,.24,.235,.23,.225],capex_first5=[7.8,6.5,4.8,5.8,5.6],wc_ratio=[.29,.30,.27,.25,.24,.24,.24,.24,.24,.24],dividend_budget=[1,1,2.2,3,4,5,6,7.5,9,10.5],changed='Y1-Y2客户消化库存/泰国爬坡转弱，已有工程照付，Y3换代恢复；母公司预算分红下调。')
 add('structural',revenue=[33,31,32,33,34,35,36,37,38,39],ebit_margin=[.18,.14,.14,.15,.16,.16,.16,.16,.16,.16],capex_first5=[7.8,5.5,2.2,2.1,2.1],wc_ratio=[.30,.32,.30,.28,.27,.27,.27,.27,.27,.27],dividend_budget=[.6,0,.4,.6,.8,1.1,1.5,1.8,2.2,2.5],debt_rate=.055,discount=.125,terminal_growth=.01,terminal_incremental_roic=.12,cash_release_delay=5,tail_fixed_ratio=.68,changed='Y1起竞争扩产压价、部分互连转向替代方案；低毛利与低周转永久化，完成约束性工程后缩减新投资，债务更贵，无旧终值。')
 add('upside',revenue=[47,62,78,94,108,120,131,141,150,158],ebit_margin=[.31,.315,.31,.30,.29,.28,.27,.265,.26,.255],capex_first5=[9,10,9.5,9,8],wc_ratio=[.26,.26,.25,.245,.24,.24,.24,.24,.24,.24],dividend_budget=[2.2,3.3,4.5,6,8,10,12,15,18,21],discount=.10,terminal_incremental_roic=.22,changed='Y1起1.6T/224Gbps放量、海外高阶复制兑现，新增产能和营运资本同步提高，不给未验证CoWoP单独溢价。')
 add('collection_delay',cash_collection_delay=[2.5,2.5,1.25,0,0,0,0,0,0,0],extra_parent_payment=[.8,0,0,0,0,0,0,0,0,0],changed='Y1-Y2集团约25亿元回款迟滞，母公司另外8亿元内部往来结算外流预算；Y3-Y4回收，不当作永损。')
 add('funding_squeeze',cash_collection_delay=[2.5,2.5,1.25,0,0,0,0,0,0,0],extra_parent_payment=[.8,0,0,0,0,0,0,0,0,0],debt_limit=9.5,debt_rate=.06,discount=.115,changed='与回款延迟同一冲击，但银行总债务不能超过95亿元、成本6%；现金股利按实际母公司和集团资金自动削减并重算终值。')
 add('platform_failure',revenue=[25,20,22,24,26,27,28,29,30,31],ebit_margin=[-.05,-.10,.05,.08,.10,.12,.12,.12,.12,.12],capex_first5=[7.8,5.5,2,1.5,1.5],wc_ratio=[.35,.38,.33,.30,.29,.29,.29,.29,.29,.29],dividend_budget=[0]*10,debt_limit=10,debt_rate=.065,discount=.14,terminal_growth=0,terminal_incremental_roic=.10,changed='核心平台认证丢失叠加信用冻结；初期亏损和已承诺工程不可回避。若资金失败，不沿用任何持续经营终值。')
 # Parent internal extra payment is cash transfer, not new consolidated cost; earns no second group charge.
 add('dividend_not_adopted',dividend_budget=[1,1.5,2,3,4,5,6,8,10,12],changed='22亿元提议未获采纳；无回购、少付现金留在集团存款并在终值保留本金。')
 return out

def tests():
 # Exact perpetuity with ten-year production discount chain: 10 every year at10%, TV100 ->100.
 assert abs(discounted_value([10]*10,100,.1)-100)<1e-9
 assert abs(discounted_value([-20,30],40,.1)-(-20/1.1+70/1.21))<1e-9
 # Test the same production operating terminal function with known capital reinvestment.
 last={'nopat':10,'invested_capital':50};p={'discount':.1,'terminal_growth':.02,'terminal_incremental_roic':.204}
 assert abs(terminal_operating_value(last,p)-(10.2-1)/.08)<1e-9
 # Exact legal budget: negative parent profit consumes reserve budget, not clipped to zero earnings.
 toy=deepcopy(BASE);toy['revenue']=[10];toy['ebit_margin']=[-.1];toy['capex_first5']=[0];toy['wc_ratio']=[.25];toy['dividend_budget']=[0]
 x=project(toy)[0];assert x['parent_profit_budget']<0 and x['parent_retained_budget']<ACTUAL['parent_retained_h1']
 # Reserve 50%, not 100% registered-capital test through actual production projection.
 toy2=deepcopy(BASE);a=deepcopy(ACTUAL);a['parent_statutory_reserve_budget_proxy']=(a['shares']+a['first_tranche_remaining'])*.5-.01
 x=project(toy2,a)[0];assert abs(x['reserve_addition']-.01)<1e-9
 # Positive profit cannot trigger reserve extraction while cumulative loss is unrepaired.
 aa=deepcopy(ACTUAL);aa['parent_retained_h1']=-5;aa['parent_statutory_reserve_budget_proxy']=0
 tt=deepcopy(toy);tt['ebit_margin']=[.1]
 xx=project(tt,aa)[0];assert 0<xx['parent_profit_budget']<5 and xx['reserve_addition']==0
 # Unregistered second-tranche dilution is NOT legal capital in first-year reserve limit.
 aa=deepcopy(ACTUAL);aa['parent_statutory_reserve_budget_proxy']=aa['shares']*.5
 xx=project(BASE,aa)[0]
 assert abs(xx['reserve_addition']-aa['first_tranche_remaining']*.5)<1e-9
 assert xx['registered_capital_budget']<xx['shares']
 result={}
 for name,p in cases().items():
  rows=project(p)
  assert len(rows)==10 or rows[-1]['feasible'] is False
  for x in rows:
   for k in ['cash_conservation_error','parent_cash_conservation_error','profit_budget_error']:assert abs(x[k])<1e-8,(name,k,x[k])
   assert x['dividend']<=max(0,x['parent_retained_budget']+x['dividend'])+1e-8
   if x['feasible']:
    assert x['parent_cash']<=x['closing_cash']+1e-8,(name,'parent cash exceeds group')
    assert x['parent_debt']<=x['closing_debt']+1e-8,(name,'parent debt exceeds group')
  result[name]={'funding_feasible':all(x['feasible'] for x in rows),'cash_conservation_max_error':max(abs(x['cash_conservation_error']) for x in rows),'max_debt':max(x['closing_debt'] for x in rows)}
 return result

def main():
 verification=tests();out={'production_hand_cases':['10-year perpetuity: exact PV100','negative then positive cashflow discount','terminal reinvestment exact','parent loss consumes retained profits','reserve cap equals 50 percent registered capital','positive profit first repairs accumulated loss','unregistered dilution excluded from legal reserve threshold'],'business_build':BUSINESS_BUILD,'units':'CNY billion except per share','information_cutoff':INFORMATION_CUTOFF,'actual':ACTUAL,'cases':{},'tests':verification}
 for i in range(5):
  total=sum(BUSINESS_BUILD[k][i] for k in ['enterprise_data_pcb','automotive_pcb','industrial_other_pcb','scrap_other'])
  assert abs(total-BASE['revenue'][i])<1e-8
 for n,p in cases().items():
  rows=project(p);v=value(p,rows);out['cases'][n]={'inputs':p,'annual':rows,'valuation':v}
 b=out['cases']['base'];rows=b['annual']
 out['sensitivity']={}
 for r in [.095,.105,.115,.125]:out['sensitivity'][str(r)]=value(BASE,rows,r)
 out['single_parameter_sensitivity']={}
 for delta in [-.03,.03]:
  q=deepcopy(BASE);q['ebit_margin']=[v+delta for v in q['ebit_margin']];q['name']='ebit_margin_'+str(delta)
  out['single_parameter_sensitivity'][q['name']]={'inputs':q,'annual':project(q),'valuation':value(q)}
 for roi in [.14,.22]:
  q=deepcopy(BASE);q['terminal_incremental_roic']=roi;q['name']='terminal_incremental_roic_'+str(roi)
  out['single_parameter_sensitivity'][q['name']]={'inputs':q,'annual':project(q),'valuation':value(q)}
 # Cash-location stress: not an economic loss, so use the same group capital and debt.
 aa=deepcopy(ACTUAL);aa['parent_cash_estimate']=2.5
 pr=project(BASE,aa)
 out['parent_cash_location_stress']={'opening_parent_cash':2.5,'annual':pr,'valuation':value(BASE,pr,actual=aa)}
 aa=deepcopy(ACTUAL);aa['parent_statutory_reserve_budget_proxy']=0
 out['parent_reserve_zero_stress']={'opening_parent_statutory_reserve_assumed':0,'annual':project(BASE,aa),'note':'Not an assertion that reported parent statutory reserve is zero; conservative alternate budget because parent standalone split is not separately presented.'}
 out['cash_release_delay_sensitivity']={}
 for delay in [0,5,8]:
  q=deepcopy(BASE);q['cash_release_delay']=delay
  out['cash_release_delay_sensitivity'][str(delay)]=value(q)
 out['unverified_cash_capacity_bounds']={}
 for fraction in [0,.5,1]:
  q=deepcopy(BASE);q['outside_cash_recovery_budget']=fraction
  out['unverified_cash_capacity_bounds'][str(fraction)]=dict(value(q),unrecognized_initial_economic_cash=(1-fraction)*value(q)['initial_outside_parent_financial_cash'],unrecognized_year5_economic_cash=(1-fraction)*value(q)['year5_outside_parent_financial_cash'])
 out['cash_capacity_note']='Unrecognized 0%/50% balances are still undistributed economic financial assets, not necessary operating capital and not physical writeoffs: annual cash balances and 1.5% yield are unchanged. Only realization value is withheld pending legal capacity evidence, a lower information bound rather than a going-concern forecast. Parent-external excess cash is a consolidated economic asset, not proved legal dividend capacity. Three-year full release is conditional budget, not certified. Bounds with 0%, 50%, 100% realization show the exact uncertainty; 0% is an information-bound valuation stress, not a prediction that cash disappears. No unverified upstream cash funds forecast parent dividends.'
 # Secondary operating-earnings capitalisation; distinct explicit normalisation of conversion/growth.
 y3=rows[2];bridge3=cash_bridge_value(y3['closing_cash'],y3['operating_cash'],y3['parent_cash'],BASE,BASE['discount'])[0]-y3['closing_debt']+ACTUAL['net_financial_equity']
 pars=[(.05,.60,.115,.02,.14),(.08,.70,.10,.025,.20)]
 multiples=[sum(conv*(1+growth)**t/(1+k)**t for t in range(1,6))+(1+growth)**5*(1+g)*(1-g/roic)/(k-g)/(1+k)**5 for growth,conv,k,g,roic in pars]
 vals=[(y3['nopat']*m+bridge3)/(1+k)**3/ACTUAL['fully_diluted']+sum(x['dividend']/(1+k)**x['year'] for x in rows[:3])/ACTUAL['fully_diluted'] for m,(_,_,k,_,_) in zip(multiples,pars)]
 out['secondary_earnings']={'year':3,'normalised_nopat':y3['nopat'],'parameters_growth_conversion_discount_g_roic':pars,'multiples':multiples,'future_bridge':bridge3,'current_values':vals}
 out['base_terminal_range_year5']=[value(BASE,rows,.115)['terminal_equity_per_share_year5'],value(BASE,rows,.095)['terminal_equity_per_share_year5']]
 (ROOT/'2026-Q3-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
 print(json.dumps({n:dict(v['valuation'],dps=[round(x['dps'],6) for x in v['annual'][:5]]) for n,v in out['cases'].items()},ensure_ascii=False,indent=2))
 print('secondary',out['secondary_earnings']);print('terminal range',out['base_terminal_range_year5']);print('tests',verification)
if __name__=='__main__':main()
