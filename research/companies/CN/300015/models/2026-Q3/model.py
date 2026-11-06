#!/usr/bin/env python3
"""Stdlib, standalone economic budgets in CNY billion. Legal entity forecasts, not certifications."""
import copy,json,sys
ASOF='2026-10-29T21:57:17+00:00';SHARES=9.268201556
# UK carved out of Europe; direct ownership routes UK to CB, not directly to listed parent.
DATA={
'domestic_mature':[18.4,.29,.06,.23,.95,2.1,.30,5.,1.,4.,6.,3.6],
'domestic_ramp':[1.,-.07,.07,.25,.85,.20,0.,-.80,.10,2.,1.,.50],
'uk':[.170768,-.20,.06,.25,.84,.03,0.,-.092,0.,.124,.10,.05],
'europe':[2.479232,.27,.06,.27,.7323,.37,.10,.52,.09,.30,1.,.60],
'isec':[.44,.23,.07,.22,.5961,.12,.04,.20,.03,.20,.20,.16],
'brazil':[1.1,.14,.05,.34,.5006,.25,.21736641496,-.10,.02,.70,.40,.25],
'other':[.15,-.03,.04,.21,.85,.01239644963,0.,-.05,0.,.10,.10,.05]}
SCENARIOS={
'base':dict(r=.10,g=.05,margin=0.,maint=0.,put=.65,wht=.05,fund_return=.02,uncalled=.05,finance=True),
'core_low':dict(r=.105,g=.045,margin=-.005,maint=.002,put=.8,wht=.07,fund_return=0.,uncalled=.1,finance=True),
'core_high':dict(r=.095,g=.055,margin=.005,maint=-.001,put=.5,wht=.03,fund_return=.04,uncalled=0.,finance=True),
'cyclical':dict(r=.10,g=.05,margin=0.,maint=0.,put=.65,wht=.05,fund_return=.02,uncalled=.05,finance=True,cycle=True),
'structural':dict(r=.11,g=.01,margin=-.07,maint=.015,put=.85,wht=.10,fund_return=-.02,uncalled=.2,finance=True,structural=True),
'upside':dict(r=.095,g=.07,margin=.01,maint=0.,put=.9,wht=.03,fund_return=.04,uncalled=0.,finance=True),
'margin_minus_2pp':dict(r=.10,g=.05,margin=-.02,maint=0.,put=.65,wht=.05,fund_return=.02,uncalled=.05,finance=True),
'cash_delay':dict(r=.10,g=.05,margin=0.,maint=0.,put=.65,wht=.10,fund_return=0.,uncalled=.20,finance=True,delay=True),
'financing_failure':dict(r=.11,g=.01,margin=-.20,maint=.02,put=1.2,wht=.10,fund_return=-.03,uncalled=.20,finance=False,structural=True),
 'terminal_low':dict(r=.105,g=.045,margin=-.005,maint=.002,put=.8,wht=.07,fund_return=0.,uncalled=.1,finance=True,fork_after5=True),
 'terminal_high':dict(r=.095,g=.055,margin=.005,maint=-.001,put=.5,wht=.03,fund_return=.04,uncalled=0.,finance=True,fork_after5=True)}
def legal_profit(re,res,capital,profit):
 z=min(max(0.,profit+min(re,0.))*.1,max(0.,capital*.5-res));return re+profit-z,res+z,z

def operating(k,y,previous,p,method):
 a=DATA[k];g=p['g']+(.02 if k in ('europe','uk') else 0.)
 if y>5:g=.015+(g-.015)*max(0.,(15-y)/10)
 if p.get('structural'):g=0. if y<=4 else .01
 if p.get('cycle') and y<=2:g=-.04 if y==1 else 0.
 if p.get('cycle') and y in (3,4):g=.08
 if k=='other':g=.015
 if k=='uk' and y<=5 and not p.get('structural'):g=p.get('uk_growth',.16)
 margin=a[1];rev=previous*(1+g)
 if method=='patient':
  visits,fee,var,fixed={'domestic_mature':(16.7,1.1,.60,.114),'domestic_ramp':(1.2,.9,.75,.32),'europe':(.93,2.666916129,.60,.13),'uk':(.0683,2.5,.75,.45),'isec':(.35,1.257,.62,.15),'brazil':(1.2,.917,.70,.16),'other':(.15,1.,.75,.28)}[k]
  rev=visits*fee*(1+g-.002) if y==1 else previous*(1+g-.002 if y<=10 else 1+g);margin=1-var-fixed
 if k=='domestic_ramp':margin=-.07+min(y,6)*.035
 if k=='uk':margin=-.20+min(y,5)*p.get('uk_recovery',.07)
 margin+=p['margin']
 if p.get('cycle') and y<=2:margin-=.025
 if k=='brazil' and p.get('structural'):margin=0.
 margin-=.02*min(1.,max(0.,y-5)/15)
 rent=rev*(.06 if 'domestic' in k else .055);da=rev*a[2]
 return dict(revenue=rev,after_rent_ebitda=rev*margin,cash_rent=rent,cash_cost=rev*(1-margin)-rent,ordinary_depreciation=da,maintenance=rev*(a[2]+p['maint']),growth_capex=max(0.,rev-previous)*(.7 if 'domestic' in k else .6),working_capital_increase=max(0.,rev-previous)*(.20 if k=='brazil' else .08),tax_rate=a[3])

def simulate(label,method='segment',horizon=320,override=None,initial=None):
 target=copy.deepcopy(SCENARIOS[label]);target.update(override or {});p=target
 ent={};leases=sum(a[11] for a in DATA.values());old_ppa=.01260595866
 brazil_ppa=p.get('brazil_ppa',.10);other_q3=.31163322375-.12228371502-brazil_ppa
 assert 0<=brazil_ppa<=.18934950873
 for k,a in DATA.items():
  share=a[11]/leases
  ent[k]=dict(revenue=a[0],cash=a[5],debt=a[6],re=a[7],reserve=a[8],capital=a[9],assets=a[10],lease=a[11],ownership=a[4],owner='europe' if k=='uk' else 'brazil_hold' if k=='brazil' else 'parent',support_loan=0.,investment_cost=0.,loans_to_subs=0.,financial_principal=.21937604148 if k=='europe' else 0.,ppa_dtl=(.008 if k=='europe' else old_ppa-.008 if k=='domestic_mature' else brazil_ppa if k=='brazil' else 0.),lease_dtl=.85429357362*share,lease_dta=.95275508543*share,fixed_dtl=.05952990350*share,fixed_dta=.04821029164*share,other_dta=(1.41000418210-.95275508543-.04821029164+.70874866194-.60585846134)*share,other_dtl=other_q3 if k=='brazil' else 0.,goodwill={'domestic_mature':6.5,'domestic_ramp':1.,'uk':.10,'europe':1.4,'isec':.46117710399,'brazil':.13662761445,'other':.1}[k])
 for e in ent.values():
  fraction=e['lease']/leases;e['loss_dta']=.21104457767*fraction;e['timing_dta']=e['other_dta']-e['loss_dta']
 ent['brazil'].update(saude_fraction=.3260,doctor_fraction=.1734)
 ent['europe'].update(optimax_liability=.07947292982*3.750/10.702,uk_put_liability=.07947292982*6.952/10.702,uk_investment_cost=.10)
 parent=dict(cash=2.,debt=1.8,re=9.68582686464,reserve=1.87807934279,capital=9.281000213,subsidiary_cost=23.11939371476,investment_allowance=1.31341476948,loan_face=4.09701206974,loan_allowance=0.,owed_to_subs=4.5,dividend_receivable=1.920938,finance=1.51139710968,restricted=.02031151021,project_cash=.1047418,tax_payable=.60440155413,bank_capacity=1.5,share_count=SHARES)
 holding=dict(cash=.10,re=-.18943446205,reserve=0.,capital=.225,loan_face=.7491298515,closed=False,support_capacity=p.get('holding_credit',.2),cost_allowance=0.)
 brazil_hold=dict(cash=0.,re=0.,reserve=0.,capital=.696,loan_face=0.,investment_cost=.696,put_liability=(.36888986072-.07947292982)*p.get('brazil_obligation_share',.8),other_acquisition_liability=(.36888986072-.07947292982)*(1-p.get('brazil_obligation_share',.8)),loans_to_hospitals=0.)
 if initial:
  parent.update(initial.get('parent',{}));holding.update(initial.get('holding',{}))
 # Old medical/financial/foreign categories; carrying NAV is not tax cost proof.
 medical=.46283218798;foreign=.05395087476;old_financial=.96110065459-.2-medical-foreign
 funds=[dict(name='legacy_medical',holder='holding',nav=medical,cost=medical,tax_basis=medical,age=0,exit=7),dict(name='legacy_financial_holding',holder='holding',nav=.68469538945-medical,cost=.68469538945-medical,tax_basis=.68469538945-medical,age=0,exit=5),dict(name='legacy_financial_parent',holder='parent',nav=.07640526514-foreign,cost=.07640526514-foreign,tax_basis=.07640526514-foreign,age=0,exit=5),dict(name='foreign_equity_budget',holder='parent',nav=foreign,cost=foreign,tax_basis=foreign,age=0,exit=5),dict(name='new_special',holder='parent',nav=.2,cost=.2,tax_basis=.2,age=0,exit=5)]
 funds.append(dict(name='strategic_associates',holder='parent',nav=.101552624,cost=.101552624,tax_basis=.101552624,age=0,exit=8))
 funds.append(dict(name='strategic_fvoci',holder='parent',nav=.0365711,cost=.0365711,tax_basis=.0365711,age=0,exit=8))
 # Allocation to holding is an economic bound, not a claim all H1 funds' legal holders are disclosed.
 unpaid=SCENARIOS['base']['uncalled'] if target.get('fork_after5') else p['uncalled'];assert 0<=unpaid<=.2
 for key in ('nav','cost','tax_basis'):funds[4][key]-=unpaid;funds[2][key]+=unpaid
 parent['oci']=0.;holding['oci']=0.
 for f in funds:
  f['tax_basis']*=p.get('fund_tax_basis_factor',1.);f['book']=f['nav'];f['oci']=0.;f['class']='equity_method' if f['name']=='strategic_associates' else 'FVOCI' if f['name']=='strategic_fvoci' else 'FVTPL'
  tr=p.get('holding_tax',.09) if f['holder']=='holding' else .25
  f['dtl']=max(0.,f['book']-f['tax_basis'])*tr;f['commitment']=.2 if f['name']=='new_special' else 0.;f['unpaid']=unpaid if f['name']=='new_special' else 0.
  owner=holding if f['holder']=='holding' else parent
  if f['class']=='FVOCI':f['oci']=-f['dtl'];owner['oci']-=f['dtl']
  else:owner['re']-=f['dtl']
 assert abs(sum(f['book'] for f in funds if f['class']=='FVTPL')-.96110065459)<1e-10
 oldface=4.09701206974-.7491298515;uk_ebitda=[];uk_profit=[];rows=[];pv=0.;term=0.;d5=[]
 def cash_total():return parent['cash']+holding['cash']+brazil_hold['cash']+sum(e['cash'] for e in ent.values())
 for y in range(1,horizon+1):
  p=copy.deepcopy(SCENARIOS['base']) if target.get('fork_after5') and y<=5 else target.copy();p['r']=target['r']
  opening=copy.deepcopy(parent);ho=copy.deepcopy(holding);bo=copy.deepcopy(brazil_hold);eo=copy.deepcopy(ent);c0=cash_total();outside=0.;parent_profit=0.;subincome={k:0. for k in ent};logs={};fundlogs=[];holding_profit=0.;brazil_hold_profit=0.;parent_equity_change=0.
  def fail(entity,gap):
   return dict(case=label,method=method,horizon=horizon,parameters=target,feasible=False,failure_year=y,failure_entity=entity,funding_gap=gap,value_per_share=None,years=rows,failed_states={'parent':copy.deepcopy(parent),'holding':copy.deepcopy(holding),'brazil_hold':copy.deepcopy(brazil_hold),'entities':copy.deepcopy(ent),'funds':copy.deepcopy(funds)})
  # Known old declared distributions and bilateral loan faces: principal only.
  schedule=4 if p.get('delay') else 2
  olddiv=min(parent['dividend_receivable'],1.920938/schedule) if y<=schedule else 0.
  parent['dividend_receivable']-=olddiv;parent['cash']+=olddiv;ent['domestic_mature']['cash']-=olddiv
  dur=10 if p.get('delay') else 5;oldloan=min(parent['loan_face'],oldface/dur) if y<=dur else 0.
  parent['loan_face']-=oldloan;parent['cash']+=oldloan;ent['domestic_mature']['cash']-=oldloan
  payable=min(parent['owed_to_subs'],.9) if y<=5 else 0.;parent['owed_to_subs']-=payable;parent['cash']-=payable;ent['domestic_mature']['cash']+=payable
  # Funds: net-NAV return for old portfolio; new contractual investment-period fee only.
  call=funds[4]['unpaid'] if y==1 else 0.;parent['cash']-=call;outside-=call
  for key in ('nav','book','cost','tax_basis'):funds[4][key]+=call
  funds[4]['unpaid']-=call;assert funds[4]['cost']<=funds[4]['commitment']+1e-12
  fund_oci_transfer=0.
  for f in funds:
   f0=copy.deepcopy(f);owner=holding if f['holder']=='holding' else parent;taxrate=p.get('holding_tax',.09) if f['holder']=='holding' else .25
   rate=p['fund_return'] if f['name'] in ('legacy_medical','new_special') else p['fund_return']*.5
   if f['name']=='strategic_associates':rate=p.get('associate_return',-.01)
   if f['name']=='strategic_fvoci':rate=p.get('fvoci_return',-.01)
   yieldrate=max(0.,min(rate,.01)) if f['name']=='legacy_medical' and y>=3 else max(0.,min(rate,.005)) if 'financial' in f['name'] else p.get('associate_yield',0.) if f['class']=='equity_method' else 0.
   income=f['nav']*yieldrate;f['nav']*=1+rate-yieldrate
   fee=f['cost']*p.get('fund_fee',.01) if f['name']=='new_special' and y<=3 else 0.
   fee_paid=min(fee,f['nav']);f['nav']-=fee_paid
   # NAV-to-book mapping is an explicit forecast, not a claim of observed fair value.
   book_target=f['nav'] if f['class']!='FVOCI' or p.get('fvoci_remeasure',True) else f0['book']
   change=book_target-f0['book'];f['book']=book_target
   dtl_before_sale=max(0.,f['book']-f['tax_basis'])*taxrate;deferred=dtl_before_sale-f0['dtl'];f['dtl']=dtl_before_sale
   f['age']+=1;exit_year=p.get('special_exit',5) if f['name']=='new_special' else f['exit']
   if p.get('no_fund_exit'):exit_year=100000
   exiting=y==exit_year;sale=f['nav'] if exiting else 0.;expense=sale*p.get('fund_exit_fee',.02);book=f['book'] if exiting else 0.;taxbasis=f['tax_basis'] if exiting else 0.
   cash_tax=income*taxrate+max(0.,sale-expense-taxbasis)*taxrate
   disposal=sale-expense-book if exiting else 0.;tax= cash_tax
   oci_change=0.;transfer=0.
   if f['class']=='FVOCI':
    oci_change=change-deferred+disposal-(cash_tax-income*taxrate)+(f['dtl'] if exiting else 0.)
    profit=income*(1-taxrate);f['oci']+=oci_change
    if exiting:transfer=f['oci'];f['oci']=0.;owner['re']+=transfer;fund_oci_transfer+=transfer
    owner['oci']+=oci_change-transfer
   else:
    profit=income+change+disposal-cash_tax-deferred+(f['dtl'] if exiting else 0.)
   cash=income+sale-expense-cash_tax;owner['cash']+=cash;outside+=cash
   if f['holder']=='holding':holding_profit+=profit
   else:parent_profit+=profit
   if exiting:f.update(nav=0.,book=0.,cost=0.,tax_basis=0.,dtl=0.)
   fundlogs.append(dict(name=f['name'],opening=f0,closing=copy.deepcopy(f),net_return=rate,realized_income=income,fee_inside_nav=fee_paid,sale=sale,exit_expense=expense,carrying_value_derecognized=book,capital_cost_derecognized=f0['cost'] if exiting else 0.,tax=tax,profit=profit,cash=cash,book_change=change,disposal_profit=disposal if f['class']!='FVOCI' else 0.,deferred_tax_change=deferred-(dtl_before_sale if exiting else 0.),oci_change=oci_change,oci_to_re=transfer))
  # Lhasa actual payment guard; support is an interest-bearing shareholder loan, never free cash.
  hcost=(p.get('holding_admin',.001) if not holding['closed'] else 0.)
  hi=holding['loan_face']*p.get('holding_interest_rate',.035) if not holding['closed'] else 0.
  htax=max(0.,holding_profit-hcost-hi)*p.get('holding_tax',.09) # fund-level cash tax already paid: no second tax
  htax=0. # fundlogs compute entity tax by realized components; deductions conservatively not monetized
  holding_profit-=hcost+hi;holding['cash']-=hcost+hi;outside-=hcost+hi*.25;parent['cash']+=hi*.75;parent_profit+=hi*.75
  hsupport=max(0.,.01-holding['cash']) if not holding['closed'] else 0.
  if hsupport:
   hsupport=min(hsupport,holding['support_capacity']) if p['finance'] else 0.
   parent['cash']-=hsupport;holding['cash']+=hsupport;holding['loan_face']+=hsupport;parent['loan_face']+=hsupport;holding['support_capacity']-=hsupport
  if holding['cash'] < -1e-9:return fail('holding',-holding['cash'])
  hrepay=min(max(0.,holding['cash']-.01),holding['loan_face']);holding['cash']-=hrepay;parent['cash']+=hrepay;holding['loan_face']-=hrepay;parent['loan_face']-=hrepay
  holding['re'],holding['reserve'],hreserve=legal_profit(holding['re'],holding['reserve'],holding['capital'],holding_profit)
  hwrite=0.;hcostloss=0.;hexitcash=0.;hliqfee=0.;hliqdistribution=0.;hwaivertax=0.;hwaiverprofit=0.
  # Definite exited assets cannot support a phantom receivable; allowance does not extinguish face.
  if not holding['closed'] and not any(f['nav']>1e-12 for f in funds if f['holder']=='holding'):
   required=max(0.,holding['loan_face']-max(0.,holding['cash']-.002));change=required-parent['loan_allowance'];parent['loan_allowance']=required;parent_profit-=change
   required_cost=max(0.,.225-max(0.,holding['cash']-holding['loan_face']-.002));hcostloss=required_cost-holding['cost_allowance'];holding['cost_allowance']=required_cost;parent['investment_allowance']+=hcostloss;parent_profit-=hcostloss
  # Explicit terminal liquidation budget only once assets have actually exited; separate no-waiver path.
  if y>=10 and not holding['closed'] and not any(f['nav']>1e-12 for f in funds if f['holder']=='holding') and not p.get('no_waiver'):
   hliqfee=.002;holding['cash']-=hliqfee;holding['re']-=hliqfee;outside-=hliqfee
   hexitcash=min(holding['cash'],holding['loan_face']);holding['cash']-=hexitcash;holding['loan_face']-=hexitcash;parent['cash']+=hexitcash;parent['loan_face']-=hexitcash
   hwrite=holding['loan_face'];parent['loan_face']-=hwrite;holding['loan_face']=0.;hwaiverprofit=hwrite
   written_allowance=min(parent['loan_allowance'],hwrite);parent['loan_allowance']-=written_allowance;parent_profit-=hwrite-written_allowance
   hwaivertax=max(0.,holding['re']+hwrite)*p.get('holding_tax',.09);holding['cash']-=hwaivertax;outside-=hwaivertax;holding['re']+=hwrite-hwaivertax
   if holding['cash']<0:return fail('holding_liquidation',-holding['cash'])
   hliqdistribution=holding['cash'];holding['cash']=0.;parent['cash']+=hliqdistribution;cost_adjustment=.225-hliqdistribution-holding['cost_allowance'];hcostloss+=cost_adjustment;parent_profit-=cost_adjustment;parent['investment_allowance']-=holding['cost_allowance'];holding['cost_allowance']=0.;parent['subsidiary_cost']-=.225
   holding.update(closed=True,re=0.,capital=0.,reserve=0.)
  # Operating hospitals: UK first, then its European parent, preserving direct and ultimate rights.
  support_total=0.;minority_support=0.;minority_cash=0.;up=0.;uptax=0.;uk_payment=0.;uk_put=0.;uk_adjustment=0.
  for k,e in ent.items():
   o=operating(k,y,e['revenue'],p,method);rev=o['revenue'];taxrate=o['tax_rate'];direct=e['ownership'];ultimate=direct*(ent['europe']['ownership'] if k=='uk' else 1.)
   debtinterest=e['debt']*(.12 if k=='brazil' else .04);supportinterest=e['support_loan']*.035
   owner=ent['europe'] if k=='uk' else brazil_hold if k=='brazil' else parent
   finance_interest=e['financial_principal']*.025;cashinterest=e['cash']*.008
   financial_income=finance_interest+cashinterest
   # Gross lease DTL/DTA tracked. Old excess book depreciation consumes genuine timing differences.
   lease_net=e['lease_dtl']-e['lease_dta'];lease_rev=lease_net/(6-y) if y<=5 else 0.;fixed_net=e['fixed_dtl']-e['fixed_dta'];fixed_rev=fixed_net/(6-y) if y<=5 else 0.
   extra_book_depreciation=(lease_rev+fixed_rev)/taxrate
   ppa=min(e['ppa_dtl']/taxrate,.008 if k=='europe' else .004 if k=='domestic_mature' else .025 if k=='brazil' else 0.);ppa_rev=ppa*taxrate;e['ppa_dtl']-=ppa_rev
   if y<=5:e['fixed_dtl']*=max(0.,(5-y)/(6-y));e['fixed_dta']*=max(0.,(5-y)/(6-y))
   other_paid=e['other_dtl']/(16-y) if 6<=y<=15 else 0.;e['other_dtl']-=other_paid
   taxable=o['after_rent_ebitda']-o['ordinary_depreciation']-debtinterest-supportinterest+financial_income
   ordinary_tax=max(0.,taxable)*taxrate
   loss_used=min(e['loss_dta'],ordinary_tax*p.get('dta_use_cap',.15)) if y<=5 else 0.
   timing_used=min(e['timing_dta'],max(0.,ordinary_tax-loss_used)*p.get('dta_use_cap',.15)/3) if y<=10 else 0.
   e['loss_dta']-=loss_used;e['timing_dta']-=timing_used;dta_used=loss_used+timing_used
   loss_writeoff=e['loss_dta'] if y==6 else 0.;timing_writeoff=e['timing_dta'] if y==10 else 0.;dta_writeoff=loss_writeoff+timing_writeoff
   e['loss_dta']-=loss_writeoff;e['timing_dta']-=timing_writeoff;e['other_dta']=e['loss_dta']+e['timing_dta']
   cash_tax=ordinary_tax-dta_used+other_paid
   book_ebit=o['after_rent_ebitda']-o['ordinary_depreciation']-extra_book_depreciation-ppa
   impairment=e['goodwill']*.30 if p.get('structural') and y==1 else 0.;e['goodwill']-=impairment
   profit=book_ebit-debtinterest-supportinterest+financial_income-cash_tax+lease_rev+fixed_rev+ppa_rev+other_paid-dta_used-dta_writeoff-impairment+subincome[k]
   # Real European buyer pays Optimax and CB UK contracts, not listed parent by fiction.
   remeasurement=0.;equity_adjustment=0.
   if k=='uk':uk_ebitda.append(o['after_rent_ebitda']+o['cash_rent']*p.get('uk_lease_ebitda',1.));uk_profit.append(max(0.,profit))
   if k=='europe':
    choice=p.get('optimax_choice',5);execution=choice-2 # 2024 Jul acquisition => third/fourth/fifth calendar anniversary in y1/2/3
    if y==execution:
     sample=uk_ebitda[:execution];average=sum(sample)/len(sample)
     # GBP conversion for both EBITDA and contractual 10m GBP at same budget FX.
     fx=p.get('gbp_fx',9.4);uk_payment=max(0.,5.5*(average/fx)-.010)*fx/2
     remeasurement=uk_payment-e['optimax_liability'];e['optimax_liability']=0.;e['cash']-=uk_payment;outside-=uk_payment;e['uk_investment_cost']+=uk_payment;profit-=remeasurement
    if y==p.get('uk_put_year',5):
     uk_put=max(0.,uk_profit[-1])*16*(1-ent['uk']['ownership']);equity_adjustment=uk_put-e['uk_put_liability'];e['uk_put_liability']=0.;e['cash']-=uk_put;outside-=uk_put;e['uk_investment_cost']+=uk_put;ent['uk']['ownership']=1.
   e['re'],e['reserve'],reserve=legal_profit(e['re'],e['reserve'],e['capital'],profit);e['re']-=equity_adjustment
   debtprincipal=min(e['debt'],DATA[k][6]/5);e['debt']-=debtprincipal
   finprincipal=min(e['financial_principal'],.21937604148/3) if k=='europe' else 0.;e['financial_principal']-=finprincipal
   cashop=taxable-cash_tax-o['maintenance']-o['growth_capex']-o['working_capital_increase']+o['ordinary_depreciation']
   # taxable contains interest owed to owner, which is internal rather than outside group.
   e['cash']+=cashop-debtprincipal+finprincipal;outside+=cashop+supportinterest-debtprincipal+finprincipal
   if supportinterest:
    recipient_tax=supportinterest*(.27 if k=='uk' else .34 if k=='brazil' else .25);owner['cash']+=supportinterest-recipient_tax;outside-=recipient_tax
    if k=='uk':subincome['europe']+=supportinterest-recipient_tax
    elif k=='brazil':brazil_hold_profit+=supportinterest-recipient_tax
    else:parent_profit+=supportinterest-recipient_tax
   e['assets']+=o['maintenance']+o['growth_capex']-o['ordinary_depreciation']-fixed_rev/taxrate
   lease_retire=min(e['lease'],o['cash_rent']);lease_add=max(0.,o['cash_rent']*5-e['lease']+lease_retire);e['lease']+=lease_add-lease_retire
   # New ROU/liability tax bases generate equal gross DTL/DTA, not a fictitious PPA windfall.
   e['lease_dta']=e['lease']*taxrate+max(0.,-(lease_net-lease_rev));e['lease_dtl']=e['lease']*taxrate+max(0.,lease_net-lease_rev);e['rou_book_asset']=e['lease_dtl']/taxrate
   floor=rev*.06;need=max(0.,floor-e['cash']);minority_in=0.;owner_in=0.;support_kind=p.get('support_kind','pro_rata')
   if need:
    if support_kind=='loan':
     owner_in=need;owner['cash']-=need;e['cash']+=need;e['support_loan']+=need
     if k=='uk':owner['loans_to_subs']+=need
     elif k=='brazil':owner['loans_to_hospitals']+=need
     else:parent['loan_face']+=need
    elif support_kind=='dilute':
     oldcap=e['capital'];owner_in=need;owner['cash']-=need;e['cash']+=need;e['capital']+=need;e['ownership']=(oldcap*direct+need)/(oldcap+need)
     if k=='uk':owner['uk_investment_cost']+=need
     elif k=='brazil':
      owner['investment_cost']+=need;e['saude_fraction']*=oldcap/(oldcap+need);e['doctor_fraction']*=oldcap/(oldcap+need)
     else:parent['subsidiary_cost']+=need
    else:
     owner_in=need*direct;minority_in=need-owner_in;owner['cash']-=owner_in;e['cash']+=need;e['capital']+=need;outside+=minority_in
     if k=='uk':owner['uk_investment_cost']+=owner_in
     elif k=='brazil':owner['investment_cost']+=owner_in
     else:parent['subsidiary_cost']+=owner_in
    support_total+=owner_in;minority_support+=minority_in
   # Shareholder loan principal is paid before distributions, not transformed into profits.
   loan_repay=min(e['support_loan'],max(0.,e['cash']-floor)*.5);e['support_loan']-=loan_repay;e['cash']-=loan_repay;owner['cash']+=loan_repay
   if k=='uk':owner['loans_to_subs']-=loan_repay
   elif k=='brazil':owner['loans_to_hospitals']-=loan_repay
   else:parent['loan_face']-=loan_repay
   available=min(max(0.,e['re']),max(0.,e['cash']-floor));declaration=available*min(p.get('sub_payout_max',.9),p.get('sub_payout_start',.7)+.02*max(0,y-5))
   if p.get('delay') and y<=3:declaration*=.5
   # A year-end UK purchase affects subsequent year dividends, not already paid current dividends.
   direct=e['ownership'];owned=declaration*direct;friction=owned*p['wht'] if k in ('europe','isec','other') else 0.
   e['cash']-=declaration;e['re']-=declaration;owner['cash']+=owned-friction;outside-=declaration-owned+friction;minority_cash+=declaration-owned
   if k=='uk':subincome['europe']+=owned
   elif k=='brazil':brazil_hold_profit+=owned
   else:parent_profit+=owned-friction;up+=owned;uptax+=friction
   e['revenue']=rev
   logs[k]={**o,'opening_state':eo[k],'book_ebit':book_ebit,'extra_book_depreciation':extra_book_depreciation,'ppa_amortization':ppa,'ppa_dtl_reversal':ppa_rev,'lease_dtl_net_reversal':lease_rev,'fixed_dtl_reversal':fixed_rev,'other_dtl_cash_settlement':other_paid,'cash_tax':cash_tax,'other_dta_utilized':dta_used,'recognized_loss_dta_used':loss_used,'other_timing_dta_used':timing_used,'other_dta_writeoff':dta_writeoff,'cash_interest_income':cashinterest,'debt_interest':debtinterest,'shareholder_loan_interest':supportinterest,'financial_interest':finance_interest,'financial_principal_returned':finprincipal,'profit':profit,'reserve_added':reserve,'equity_adjustment':equity_adjustment,'contingent_remeasurement':remeasurement,'debt_principal_paid':debtprincipal,'operating_cash_after_investment':cashop,'capital_support':need,'owner_support':owner_in,'minority_support':minority_in,'support_kind':support_kind,'shareholder_loan_repaid':loan_repay,'declared_and_paid':declaration,'direct_owner_fraction_at_distribution':direct,'ultimate_owner_fraction_at_distribution':direct*(ent['europe']['ownership'] if k=='uk' else 1.),'ordinary_parent_receipt_gross':owned,'remittance_friction_tax':friction,'minority_cash':declaration-owned,'lease_additions':lease_add,'lease_retired':lease_retire,'closing_state':copy.deepcopy(e)}
  # Brazil rights remain at the local holding. Parent funds only through a recorded loan.
  bpay=0.;bremeasure=0.;other_acquisition_paid=brazil_hold['other_acquisition_liability'] if y==3 else 0.;brazil_hold['other_acquisition_liability']-=other_acquisition_paid;brazil_hold['cash']-=other_acquisition_paid;outside-=other_acquisition_paid
  if y==p.get('put_year',4):
   brazil_contract_scale=max(.6,min(1.4,logs['brazil']['after_rent_ebitda']/.1871889625))
   bpay=p['put']*brazil_contract_scale;bremeasure=bpay-brazil_hold['put_liability'];brazil_hold['put_liability']=0.;brazil_hold['cash']-=bpay;outside-=bpay;brazil_hold['investment_cost']+=bpay;brazil_hold_profit-=bremeasure;ent['brazil']['ownership']+=ent['brazil']['saude_fraction'];ent['brazil']['saude_fraction']=0.
  bi=brazil_hold['loan_face']*.035;brazil_hold['cash']-=bi;parent['cash']+=bi*.75;outside-=bi*.25;parent_profit+=bi*.75;brazil_hold_profit-=bi
  bsupport=max(0.,-brazil_hold['cash'])
  if bsupport:
   if not p['finance']:return fail('brazil_hold',bsupport)
   parent['cash']-=bsupport;brazil_hold['cash']+=bsupport;brazil_hold['loan_face']+=bsupport;parent['loan_face']+=bsupport
  brepay=min(brazil_hold['loan_face'],max(0.,brazil_hold['cash'])*.6);brazil_hold['cash']-=brepay;parent['cash']+=brepay;brazil_hold['loan_face']-=brepay;parent['loan_face']-=brepay
  brazil_hold['re'],brazil_hold['reserve'],bres=legal_profit(brazil_hold['re'],brazil_hold['reserve'],brazil_hold['capital'],brazil_hold_profit)
  bd=min(max(0.,brazil_hold['cash']),max(0.,brazil_hold['re']))*.9;brazil_hold['cash']-=bd;brazil_hold['re']-=bd;bt=bd*p['wht'];parent['cash']+=bd-bt;parent_profit+=bd-bt;outside-=bt;up+=bd;uptax+=bt
  # Parent direct service, HQ, financial income, real tax and debt cash.
  long_hq_growth=1.01 if p.get('structural') else 1.015
  prevenue=.60*1.025**min(y,15)*long_hq_growth**max(0,y-15);pebit=prevenue*.12-.18*1.02**min(y,15)*long_hq_growth**max(0,y-15)
  interest=parent['debt']*.035;fy=parent['finance']*.018+parent['cash']*.008;ftax=max(0.,pebit-interest+fy)*.25
  freturn=min(parent['finance'],1.51139710968/3);parent['finance']-=freturn;debtpay=min(parent['debt'],.36);parent['debt']-=debtpay
  if y==1:parent['project_cash']=0. # designated cash applied within, not in addition to, existing hospital capital budget
  oldtax=parent['tax_payable'] if y==1 else 0.;parent['tax_payable']-=oldtax
  ri=parent['restricted']*p.get('restricted_yield',.01);ritax=ri*p.get('restricted_tax_rate',.25);ftax+=ritax;parent['restricted']+=ri;release=parent['restricted'] if y==3 else 0.;parent['restricted']-=release
  parent_profit+=pebit-interest+fy-ftax+ri
  directcash=pebit-interest+fy-ftax+freturn-debtpay-oldtax+release;parent['cash']+=directcash;outside+=directcash
  impairment=3. if p.get('structural') and y==1 else 0.;parent_profit-=impairment;parent['investment_allowance']+=impairment
  parent['re'],parent['reserve'],reserve=legal_profit(parent['re'],parent['reserve'],parent['capital'],parent_profit)
  loan=0.
  if parent['cash']<.3 and p['finance']:
   loan=min(parent['bank_capacity'],.3-parent['cash']);parent['cash']+=loan;parent['debt']+=loan;parent['bank_capacity']-=loan;outside+=loan
  for name,state in [('parent',parent),('holding',holding),('brazil_hold',brazil_hold)]+list(ent.items()):
   if state['cash'] < -1e-9:return fail(name,-state['cash'])
  requested=(.18+.015*(y-1))*SHARES if y<=5 else max(rows[-1]['distribution']*p.get('payout_growth',1.06),max(0.,parent['cash']-.5)*p.get('payout_excess_fraction',.25))
  fund_locked_profit=sum(max(0.,f['book']-f['cost']-f['dtl']) for f in funds if f['holder']=='parent' and f['class']!='FVOCI');distribution=min(requested,max(0.,parent['re']-fund_locked_profit),max(0.,parent['cash']-.5));parent['cash']-=distribution;parent['re']-=distribution;outside-=distribution
  residual=cash_total()-c0-outside;assert abs(residual)<1e-8,(label,y,residual)
  assert min(holding['cash'],brazil_hold['cash'],parent['cash'],*[e['cash'] for e in ent.values()])>=-1e-9
  assert parent['loan_face']>=-1e-8
  d=distribution/SHARES;pv+=d/(1+p['r'])**y
  if y<=5:d5.append(d)
  else:term+=d/(1+p['r'])**(y-5)
  # Actual closing rights after purchase differ only from explicitly timestamped distribution rights.
  for k in logs:logs[k]['closing_state']=copy.deepcopy(ent[k])
  rows.append(dict(year=y,parent_open=opening,parent_close=copy.deepcopy(parent),holding_open=ho,holding_close=copy.deepcopy(holding),brazil_hold_open=bo,brazil_hold_close=copy.deepcopy(brazil_hold),entities=logs,funds=fundlogs,old_dividend_collection=olddiv,old_loan_face_collection=oldloan,old_internal_payable_settlement=payable,holding_admin=hcost,holding_interest=hi,holding_support_loan=hsupport,holding_loan_cash_repaid=hrepay+hexitcash,holding_legal_extinguishment=hwrite,holding_cost_loss=hcostloss,holding_liquidation_fee=hliqfee,holding_liquidation_distribution=hliqdistribution,holding_waiver_profit=hwaiverprofit,holding_waiver_tax=hwaivertax,holding_profit=holding_profit,holding_reserve=hreserve,brazil_put_cash=bpay,other_acquisition_liability_paid=other_acquisition_paid,brazil_put_remeasurement=bremeasure,brazil_holding_support_loan=bsupport,brazil_holding_interest=bi,brazil_holding_loan_repaid=brepay,brazil_holding_profit=brazil_hold_profit,brazil_holding_reserve=bres,brazil_holding_dividend=bd,optimax_cash=uk_payment,uk_management_put_cash=uk_put,subsidiary_support=support_total,minority_support=minority_support,minority_paid=minority_cash,subsidiary_gross_current_dividends=up,subsidiary_remittance_friction=uptax,parent_direct_revenue=prevenue,parent_direct_ebit=pebit,parent_physical_depreciation=prevenue*.04,parent_maintenance=prevenue*.04,parent_financial_income=fy,parent_financial_principal_return=freturn,parent_interest=interest,parent_cash_tax=ftax,parent_debt_principal=debtpay,parent_new_borrowing=loan,fund_call=call,old_tax_paid=oldtax,restricted_interest_retained=ri,restricted_interest_cash_tax=ritax,fund_oci_to_re=fund_oci_transfer,fund_unrealized_distribution_lock=fund_locked_profit,restricted_principal_return=release,parent_current_profit=parent_profit,parent_reserve_allocation=reserve,distribution=distribution,distribution_per_share=d,group_cash=cash_total(),cash_conservation_residual=residual,cumulative_pv_per_share=pv))
 return dict(case=label,method=method,horizon=horizon,parameters=target,feasible=True,value_per_share=pv,distributions=d5,terminal5=term,parent_y5=rows[4]['parent_close'] if len(rows)>=5 else None,years=rows,tail_state=copy.deepcopy(parent),tail_group_states=copy.deepcopy(ent),tail_holding=copy.deepcopy(holding),tail_brazil_holding=copy.deepcopy(brazil_hold),tail_funds=copy.deepcopy(funds),tail_cash_pv=cash_total()/(1+p['r'])**horizon/SHARES,terminal_share=term/(1+p['r'])**5/pv if pv else None)
