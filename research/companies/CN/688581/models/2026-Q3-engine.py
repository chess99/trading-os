#!/usr/bin/env python3
"""Self-contained stdlib entity-cash model. CNY million; no prices or trading.
Legal face, impairment allowance and actual collections are distinct stocks.
"""
import json,copy
ASOF='2026-10-29T00:55:00+00:00';S=80.740656;OWN=.958333

def initial():
 hcap=91.12670946*.7;ocap=91.12670946*.3
 return dict(p_cash=2165.,p_re=825.,p_reserve=66.90921161,p_cp=1705.4505081,p_cap=220.,p_wc=3.87676024,treasury=1.06970481,shares=S,ar_h=0.,ar_o=0.,mature_sales_last=510.,overseas_last=340.,equipment_last=8.,
 h=dict(remittance_escrow=0.,dividend_payable_parent=0.,cash=20.,cap=hcap,wc=0.,external_debt=10.,loan_face=55.,loan_allowance=0.,investment_cost=116.04268019,investment_allowance=0.,investment_cost_retired=0.,re=20+hcap-55-10-120,paid_capital=120.,capital_premium=0.,reserve=0.,tax_lots=[[i,24.]for i in range(1,6)],closed=False,loss_run=0,minority=.4668126),
 o=dict(remittance_escrow=0.,dividend_payable_parent=0.,cash=131.12500845,cap=ocap,wc=0.,external_debt=43.12236991,loan_face=30.,loan_allowance=0.,investment_cost=101.33387138,investment_allowance=0.,investment_cost_retired=0.,re=5.,paid_capital=5.,capital_premium=131.12500845+ocap-43.12236991-30-5-5,reserve=0.,tax_lots=[[i,4.]for i in range(1,6)],closed=False,loss_run=0,minority=0.))

def business(t,c):
 d=[170,175,180,185,190][min(t,5)-1];o=[340,355,370,385,400][min(t,5)-1];e=[8,20,40,65,90][min(t,5)-1]
 if t>5:
  for y in range(6,t+1):
   g={'low':.025,'mid':.04,'high':.055}[c.get('tail','mid')]*max(0,(20-y)/14)
   d*=1+.45*g;o*=1+g;e*=1+.8*g
 dm=.58;om=.73;kind=c.get('kind','base')
 if kind=='cycle':d*={1:.85,2:.90,3:.96}.get(t,1);o*={1:.85,2:.90,3:.96}.get(t,1)
 if kind=='structural':d*=.8;o*=.82;e*=.55;dm=.49;om=.63
 if kind=='upside':d*=1.05;o*=1.12;e*=2.5
 mature=d+o;transfer=.04*o if t>=3 else 0
 p_ebit=d*dm+o*om-.27*mature-transfer
 h_ebitda=.30*e-32+5.32+(min(6,(t-5)*.6)if t>5 else 0)
 if kind=='structural':h_ebitda-=8
 if c.get('method')=='history':
  p_ebit={'low':195.,'mid':210.,'high':225.}[c.get('tail','mid')]*(1-.18*min(t,15)/15)-transfer
  h_ebitda=-26+3*min(t,10)+5.32
 return dict(domestic=d,overseas=o,equipment=e,mature=mature,parent_ebit=p_ebit,h_ebitda=h_ebitda,o_ebitda=transfer-4+2.28,internal_manufacturing_profit=transfer)

def tax(entity,t,income):
 lots=[[y,a]for y,a in entity['tax_lots']if y>=t];taxable=max(0,income)
 for z in lots:
  used=min(z[1],taxable);z[1]-=used;taxable-=used
 lots=[z for z in lots if z[1]>1e-10]
 if income<0:lots.append([t+5,-income])
 entity['tax_lots']=lots
 return .2*taxable

def exit_waterfall(h,t,c):
 """Uses this entity's assets only. Shortfall is an allowance, never debt waiver.
 Closed-but-unsettled entity keeps legal debt face and parent cost/allowance.
 """
 assert abs(h['remittance_escrow'])<1e-9 and abs(h['dividend_payable_parent'])<1e-9
 before=copy.deepcopy(h);book=h['cap']+h['wc']
 sale=h['cap']*c.get('exit_recovery',.6)+h['wc']*c.get('exit_wc_recovery',.9)
 closure=c.get('exit_cost',15.)
 taxable_result=sale-book-closure;taxpaid=tax(h,t,taxable_result)
 # Budgeted parent advance only funds unavoidable closure costs, not a gift to equity.
 support=max(0,closure+taxpaid-h['cash']-sale);h['loan_face']+=support
 gross_resources=h['cash']+sale+support
 after_priority=gross_resources-closure-taxpaid
 external_paid=min(h['external_debt'],after_priority);h['external_debt']-=external_paid;after_priority-=external_paid
 loan_collected=min(h['loan_face'],after_priority);h['loan_face']-=loan_collected;after_priority-=loan_collected
 surplus=after_priority
 parent_equity=surplus*OWN;minority_cash=surplus*(1-OWN)
 loan_impairment=max(0,h['loan_face']-h['loan_allowance']);h['loan_allowance']+=loan_impairment
 carrying=h['investment_cost']-h['investment_allowance']
 # Recovery after debt priority is equity proceeds; unrecovered investment is separately charged.
 investment_result=parent_equity-carrying
 if surplus>0:
  h['investment_cost_retired']+=h['investment_cost'];h['investment_cost']=0.;h['investment_allowance']=0.
 else:h['investment_allowance']=h['investment_cost']
 profit=taxable_result-taxpaid;h['re']+=profit;h['minority']+=profit*(1-OWN)
 h['cash']=0.;h['cap']=0.;h['wc']=0.;h['closed']=True
 if surplus>0:h['re']=0.;h['paid_capital']=0.;h['reserve']=0.;h['capital_premium']=0.;h['minority']=0.
 assert abs(gross_resources-closure-taxpaid-external_paid-loan_collected-parent_equity-minority_cash)<1e-8
 return dict(before=before,asset_book=book,asset_proceeds=sale,closure_cost=closure,tax=taxpaid,parent_closure_advance=support,external_paid=external_paid,loan_collected=loan_collected,loan_face_uncollected=h['loan_face'],loan_allowance=h['loan_allowance'],loan_impairment=loan_impairment,equity_surplus=surplus,parent_equity_receipt=parent_equity,minority_cash=minority_cash,parent_investment_cost_before=before['investment_cost'],parent_investment_allowance_before=before['investment_allowance'],parent_investment_result=investment_result,parent_investment_cost_after=h['investment_cost'],parent_investment_allowance_after=h['investment_allowance'],legal_debt_waiver=0.,profit=profit)

def operate(entity,key,t,a,c):
 """One separate company budget: own cash -> own debt -> own dividends."""
 z=entity;old=copy.deepcopy(z)
 if z['closed']:
  tax(z,t,0.)
  return dict(profit=0.,tax=0.,finance=0.,interest=0.,depreciation=0.,capex=0.,wc_change=0.,funding=0.,loan_collected=0.,external_paid=0.,reserve=0.,dividend=0.,parent_dividend=0.,minority_dividend=0.,remittance_tax=0.,capital_return=0.,capital_return_cost=0.,parent_capital_receipt=0.,parent_capital_profit=0.)
 dep=.08*z['cap'];fin=z['cash']*c.get('yield',.017)/.8;interest=z['external_debt']*.035
 earnings=a[key+'_ebitda']-dep+fin-interest;paidtax=tax(z,t,earnings);np=earnings-paidtax
 if t<=5:
  total=[200,170,90,25,20][t-1]*c.get('capex_multiplier',1.)
  if c.get('kind')=='cycle'and t<=2:total*=1.1
  if c.get('kind')=='structural'and t==3:total+=40
  capex=total*(.7 if key=='h'else .3)
 else:
  g=max(0,(a['equipment']/a['equipment_last']-1))if key=='h'else max(0,a['overseas']/a['overseas_last']-1)
  capex=dep+(a['equipment']*.6*g if key=='h'else a['overseas']*.15*g)
 wc=.1*a['equipment']if key=='h'else 0.;dwc=wc-z['wc']
 term=c.get('h_debt_term',3)if key=='h'else 3
 initialdebt=10. if key=='h'else 43.12236991
 debtpay=min(z['external_debt'],initialdebt/term)if t<=term else 0.
 z['external_debt']-=debtpay;z['cash']+=np+dep-capex-dwc-debtpay
 z['cap']+=capex-dep;z['wc']=wc;z['re']+=np
 reserve=min(.1*max(0,min(np,z['re'])),max(0,.5*z['paid_capital']-z['reserve']));z['reserve']+=reserve;z['re']-=reserve
 floor=10.;fund=max(0,floor-z['cash']);z['cash']+=fund;z['loan_face']+=fund
 collect=min(z['loan_face'],max(0,z['cash']-floor));z['loan_face']-=collect;z['cash']-=collect
 div=.9*min(max(0,z['re']),max(0,z['cash']-floor))
 if c.get('kind')=='delay'and key=='o'and 10<=t<=20:div=0.
 z['cash']-=div;z['re']-=div
 ownership=OWN if key=='h'else 1.;minor=div*(1-ownership);withholding=div*c.get('remit_tax',.05)if key=='o'else 0.
 parentdiv=div*ownership-withholding
 # Actual cash is reserved in the paying entity's settlement account; AR is not cash.
 z['remittance_escrow']+=parentdiv;z['dividend_payable_parent']+=parentdiv
 z['minority']+=np*(1-ownership)-minor
 z['loss_run']=z['loss_run']+1 if np<0 else 0
 # Conditional return of other-subsidiary contributed premium follows same long-run policy.
 cr=0.;fee=0.;crprofit=0.;receipt=0.
 if key=='o'and t>=c.get('return_start',15):
  cr=min(max(0,z['cash']-floor),max(0,z['capital_premium'])*c.get('return_rate',.06))
  fee=.005*cr;z['cash']-=cr+fee;z['capital_premium']-=cr;z['re']-=fee;receipt=cr
  cost_recovered=min(z['investment_cost'],cr);z['investment_cost']-=cost_recovered;z['investment_cost_retired']+=cost_recovered;crprofit=cr-cost_recovered
 return dict(profit=np,tax=paidtax,finance=fin,interest=interest,depreciation=dep,capex=capex,wc_change=dwc,funding=fund,loan_collected=collect,external_paid=debtpay,reserve=reserve,dividend=div,parent_dividend=parentdiv,minority_dividend=minor,remittance_tax=withholding,capital_return=cr,capital_return_cost=fee,parent_capital_receipt=receipt,parent_capital_profit=crprofit)

def liquid_cash(s):return s['p_cash']+s['h']['cash']+s['o']['cash']+s['h']['remittance_escrow']+s['o']['remittance_escrow']

def step(st,t,c):
 x=copy.deepcopy(st);old=copy.deepcopy(st);a=business(t,c)
 # Settlement is actual cash movement; no parent yield is assumed on funds still
 # in clearing at the prior year-end. Internal AR and payable eliminate in group.
 prior_ar=0.
 for key in ['h','o']:
  z=x[key];paid=z['dividend_payable_parent']
  assert abs(x['ar_'+key]-paid)<1e-9 and z['remittance_escrow']+1e-9>=paid
  z['remittance_escrow']-=paid;z['dividend_payable_parent']-=paid
  x['ar_'+key]-=paid;x['p_cash']+=paid;prior_ar+=paid
 a.update(equipment_last=x['equipment_last'],overseas_last=x['overseas_last'])
 exitinfo=None
 if t==c.get('exit_year',8)and x['h']['loss_run']>=3 and not x['h']['closed']:
  exitinfo=exit_waterfall(x['h'],t,c)
 if x['h']['closed']:a['equipment']=0.
 pdep=.07*x['p_cap'];maturegrowth=max(0,a['mature']/x['mature_sales_last']-1)
 pc=[24,25,27,29,30][t-1]if t<=5 else pdep+a['mature']*.3*maturegrowth
 newwc=.1*a['mature'];dwc=newwc-x['p_wc'];x['p_wc']=newwc;x['p_cap']+=pc-pdep
 sbc=17.5 if t<=3 else 0.;pfin=old['p_cash']*c.get('yield',.017)
 operating_np=(a['parent_ebit']-(pdep-16.8))*.85+pfin-sbc
 x['p_cash']+=operating_np+sbc+pdep-pc-dwc
 p_np=operating_np
 flows={}
 for key in ['h','o']:
  f=operate(x[key],key,t,a,c);flows[key]=f
  x['p_cash']+=f['loan_collected']-f['funding']+f['parent_capital_receipt']
  x['ar_'+key]=f['parent_dividend'];p_np+=f['parent_dividend']+f['parent_capital_profit']
 parent_exit_tax=0.
 if exitinfo:
  f=exitinfo;x['p_cash']+=f['loan_collected']+f['parent_equity_receipt']-f['parent_closure_advance']
  parent_exit_tax=.15*max(0,f['parent_investment_result']);x['p_cash']-=parent_exit_tax
  p_np+=f['parent_investment_result']-f['loan_impairment']-parent_exit_tax
 x['p_re']+=p_np
 buy=c.get('buy',52.5)if t==1 else 0.;derivative=.56400492 if t==1 else 0.
 x['p_cash']-=buy+derivative;x['p_cp']+=sbc;x['treasury']+=buy
 if t==3:x['p_cp']-=x['treasury'];x['treasury']=0.
 sales=a['mature']+a['equipment'];floor=100+.05*sales;locked=max(0,101.72124749*(1-t/3))
 available=max(0,x['p_cash']-floor-locked)
 payout=.4 if t<=5 else (.7 if t<=10 else 1.)
 # Group economic profit excludes parent impairment of intra-group financial assets;
 # legal dividend ceiling independently includes these parent impairments.
 group_np=operating_np+flows['h']['profit']*OWN+flows['o']['profit']
 if exitinfo:group_np+=exitinfo['profit']*OWN-parent_exit_tax
 ordinary=max(0,group_np)*payout
 special=0 if t<=5 else min(max(0,x['p_re']-ordinary),available*.1)
 div=min(ordinary+special,max(0,x['p_re']),available);x['p_cash']-=div;x['p_re']-=div
 cr=min(max(0,x['p_cash']-floor),max(0,x['p_cp'])*c.get('return_rate',.06))if t>=c.get('return_start',15)else 0.
 fee=.005*cr;x['p_cash']-=cr+fee;x['p_cp']-=cr;x['p_re']-=fee
 x['mature_sales_last']=a['mature'];x['overseas_last']=a['overseas'];x['equipment_last']=max(a['equipment'],1e-9)
 expected=operating_np+sbc+pdep-pc-dwc-buy-derivative-div-cr-fee-parent_exit_tax
 for f in flows.values():expected+=f['profit']+f['depreciation']-f['capex']-f['wc_change']-f['external_paid']-f['minority_dividend']-f['remittance_tax']-f['capital_return_cost']
 if exitinfo:expected+=exitinfo['profit']+exitinfo['asset_book']-exitinfo['external_paid']-exitinfo['minority_cash']
 err=liquid_cash(x)-liquid_cash(old)-expected
 assert abs(err)<1e-7,(t,err)
 assert min(x['p_cash'],x['h']['cash'],x['o']['cash'])>=-1e-8
 for key in ['h','o']:
  assert x[key]['loan_face']+1e-8>=x[key]['loan_allowance']>=0
  assert abs(x['ar_'+key]-x[key]['dividend_payable_parent'])<1e-9
  assert abs(x[key]['remittance_escrow']-x[key]['dividend_payable_parent'])<1e-9
 return x,dict(year=t,state=x,business=a,parent_operating_np=operating_np,parent_operating_tax=(a['parent_ebit']-(pdep-16.8))*.15,parent_financial_income_gross=pfin/.8,parent_financial_tax=pfin/.8-pfin,parent_statutory_reserve_transfer=0.,parent_legal_np=p_np,parent_finance=pfin,parent_depreciation=pdep,parent_capex=pc,parent_wc_change=dwc,parent_prior_receivable_collected=prior_ar,parent_exit_tax=parent_exit_tax,sbc=sbc,buyback=buy,derivative_settlement=derivative,entities=flows,exit=exitinfo,ordinary_special_dividend=div,capital_return=cr,capital_return_cost=fee,holder_cash=div+cr,holder_per_share=(div+cr)/S,cash_conservation_error=err)

def run(c,n=240,st=None,start=1):
 s=copy.deepcopy(st or initial());rows=[]
 for t in range(start,n+1):s,row=step(s,t,c);rows.append(row)
 r=c.get('r',.10);pv=sum(z['holder_cash']/(1+r)**(z['year']-start+1)for z in rows);tail=rows[-1]['holder_cash']/r/(1+r)**(n-start+1)
 return dict(config=c,start=start,n=n,rows=rows,value=(pv+tail)/S,pv_explicit=pv/S,pv_residual=tail/S)

def cases():
 return {
 'base':dict(r=.10,tail='mid',return_start=15,return_rate=.06),
 'core_low':dict(r=.105,tail='low',return_start=20,return_rate=.05),
 'core_high':dict(r=.095,tail='high',return_start=12,return_rate=.08),
 'history_low':dict(r=.105,tail='low',method='history',return_start=20,return_rate=.05),
 'history_high':dict(r=.095,tail='high',method='history',return_start=12,return_rate=.08),
 'cycle':dict(r=.10,tail='mid',kind='cycle',return_start=18,return_rate=.06),
 'structural':dict(r=.11,tail='low',kind='structural',return_start=20,return_rate=.05),
 'upside':dict(r=.095,tail='high',kind='upside',return_start=12,return_rate=.08),
 'release_delay':dict(r=.10,tail='mid',return_start=30,return_rate=.03),
 'no_capital_return_condition':dict(r=.10,tail='mid',return_start=9999,return_rate=0),
 'sub_remittance_delay':dict(r=.10,tail='mid',kind='delay',return_start=15,return_rate=.06),
 'buy70':dict(r=.10,tail='mid',buy=70,return_start=15,return_rate=.06),
 'remittance_tax10':dict(r=.10,tail='mid',remit_tax=.10,return_start=15,return_rate=.06),
 'exit_recovery40':dict(r=.10,tail='mid',exit_recovery=.4,return_start=15,return_rate=.06),
 'exit_recovery80':dict(r=.10,tail='mid',exit_recovery=.8,return_start=15,return_rate=.06),
 'exit_zero_recovery':dict(r=.10,tail='mid',exit_recovery=0.,exit_wc_recovery=0.,return_start=15,return_rate=.06),
 'exit_external_debt_late':dict(r=.10,tail='mid',h_debt_term=12,return_start=15,return_rate=.06),
 'project_overrun':dict(r=.10,tail='mid',capex_multiplier=1.2,return_start=15,return_rate=.06),
 'core_low_buy70':dict(r=.105,tail='low',buy=70,return_start=20,return_rate=.05),
 'parent_cash_split_low':dict(r=.10,tail='mid',return_start=15,return_rate=.06)}

def tests():
 # The same production waterfall used by step, with hand-computable counterexamples.
 h=copy.deepcopy(initial()['h']);h.update(cash=10.,cap=100.,wc=0.,external_debt=20.,loan_face=80.,loan_allowance=0.,investment_cost=50.,investment_allowance=0.,tax_lots=[])
 f=exit_waterfall(h,8,dict(exit_recovery=.6,exit_cost=10.))
 # 10+60 -10closure -20external =40loan collection; remaining face40 + allowance40; equity0.
 assert f['loan_collected']==40 and f['loan_face_uncollected']==40 and f['loan_allowance']==40 and f['minority_cash']==0 and f['legal_debt_waiver']==0
 h2=copy.deepcopy(initial()['h']);h2.update(cash=10.,cap=100.,wc=0.,external_debt=20.,loan_face=10.,loan_allowance=0.,investment_cost=50.,investment_allowance=0.,tax_lots=[])
 f2=exit_waterfall(h2,8,dict(exit_recovery=.6,exit_cost=10.))
 assert f2['equity_surplus']==30 and abs(f2['parent_equity_receipt']-28.74999)<1e-8 and abs(f2['minority_cash']-1.25001)<1e-8
 # Actual operating function: prior legal loss9, NP10 => eligible profit1, reserve0.1.
 z=copy.deepcopy(initial()['h']);z.update(cash=10.,cap=0.,wc=0.,external_debt=0.,loan_face=0.,re=-9.,reserve=0.,tax_lots=[[100,100.]])
 aa=dict(h_ebitda=10.-10.*.017/.8,equipment=0.,equipment_last=1.,overseas=0.,overseas_last=1.)
 rf=operate(z,'h',6,aa,{})
 assert abs(rf['profit']-10.)<1e-9 and abs(rf['reserve']-.1)<1e-9
 assert abs(z['remittance_escrow']-z['dividend_payable_parent'])<1e-9
 ss=initial();ss['h']=copy.deepcopy(z);ss['h']['closed']=True;ss['ar_h']=z['remittance_escrow']
 settled,srow=step(ss,7,dict(r=.10,tail='mid',return_start=15,return_rate=.06))
 assert abs(srow['parent_prior_receivable_collected']-.77624973)<1e-9
 assert settled['h']['remittance_escrow']==0. and settled['h']['dividend_payable_parent']==0. and settled['ar_h']==0.
 return dict(insolvent_priority_counterexample=f,solvent_equity_counterexample=f2,loss_offset_reserve_counterexample=dict(prior_re=-9.,flow=rf,state=z,expected_reserve=.1),actual_clearing_step_counterexample=srow)

def stock_gap(a,b,path=''):
 if isinstance(a,dict):
  result=[]
  for k in a:result+=stock_gap(a[k],b[k],path+'.'+k)
  return result
 if isinstance(a,list):
  if len(a)!=len(b):return [dict(path=path,before=a,after=b,gap=None)]
  result=[]
  for i,(x,y) in enumerate(zip(a,b)):result+=stock_gap(x,y,path+'['+str(i)+']')
  return result
 if type(a)in(int,float):return [dict(path=path,before=a,after=b,gap=abs(a-b))]
 assert a==b
 return []

def main():
 cs=cases();res={};conv={};checks={}
 for name,c in cs.items():
  st=initial()
  if name=='parent_cash_split_low':st['p_cash']-=100;st['o']['cash']+=100;st['p_re']=750
  res[name]=run(c,240,st);conv[name]={str(n):run(c,n,st)for n in [120,360,720,1440]}
  gaps=stock_gap(conv[name]['720']['rows'][-1]['state'],conv[name]['1440']['rows'][-1]['state'])
  checks[name]=dict(full_state_720_1440=gaps,max_gap=max(x['gap'] for x in gaps if x['gap'] is not None),value_240_1440_gap=abs(res[name]['value']-conv[name]['1440']['value']))
  if checks[name]['max_gap']>=.001:
   conv[name]['2880']=run(c,2880,st)
   gaps=stock_gap(conv[name]['1440']['rows'][-1]['state'],conv[name]['2880']['rows'][-1]['state'])
   checks[name]['full_state_1440_2880']=gaps;checks[name]['max_gap']=max(x['gap'] for x in gaps if x['gap'] is not None)
  # A micro-yuan scale is not claimed. 0.001m = RMB1000 on multi-billion assets.
  assert checks[name]['max_gap']<.001,(name,checks[name]['max_gap'])
 s5=res['base']['rows'][4]['state'];term={k:run(cs[k],1440,s5,6)for k in ['core_low','core_high']}
 print(json.dumps(dict(asof=ASOF,units='CNY million / million current ownership units',initial=initial(),tests=tests(),results=res,terminal_same_base_y5=term,convergence=conv,convergence_checks=checks),ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False))
if __name__=='__main__':main()
