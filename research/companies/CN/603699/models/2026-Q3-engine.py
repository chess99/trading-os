#!/usr/bin/env python3
"""Neway conditional owner-cash model. Units CNY bn, shares bn; no security quotes.
Annual budgets from disclosure-pro-forma opening, not reconstructed Q3 entity accounts.
Full rows are the production output; no summary replaces them.
"""
import copy, json, sys
from math import isfinite

OPEN={
 'cash':(881006429.03-327375399.54)/1e9,'restricted_cash':(904079572.91-881006429.03)/1e9,
 'financial':1654581808.30/1e9,'debt':1783002436.38/1e9,'lease':11160260.26/1e9,
 'award':266966602.32/1e9,'shares':779465237/1e9,'reserve':387798463.50/1e9,
 'retained':2453524821.26/1e9,'nci':21258467.46/1e9,'equity':4755054919.04/1e9,
 'ppe':(1149204317.36+193635197.59+190465786.22+10964967.63+4272162.62)/1e9,
 'other':(171859286.98+10032887.74+31370284.96+904079572.91-881006429.03)/1e9,
 'parent_cash_share':(566837712.29+1732740742.94)/(1038181446.32+1737749689.13),
 'parent_retained':(1990418969.95+381054126.63*(563660964.40/733375734.30)-327375399.54)/1e9,
 'internal_ar':741254510.14/1e9,'internal_loan':404528980.44/1e9,
 'internal_note_proxy':(2154193247.56-957954945.14)/1e9,
 'unrealized_profit':45558552.44/1e9,'elimination_dta':9478230.98/1e9,
 'cancel_shares':87072/1e9,'cancel_cash':(74572*14.32+12500*3.68)/1e9,
}
# Net operating current assets, with award obligation reclassified out of operating accruals.
OPEN['nwc']=(67274591.45+2973282650.55+41302784.25+67493538.94+24329824.09+2896829827.22+124152288.04+88801534.70-833041317.64-1505110104.17-250269433.13-185466557.92-103954303.26-(1049562312.76-327375399.54-266966602.32)-83018299.68-44293367.31)/1e9
BASE={'name':'base','years':180,'discount':.09,'post5_discount':None,'core_revenue':8.10,'growth':.04,'terminal_growth':.015,'cash_ebit_margin':.24,'replacement_comp':.01,'sbc_schedule':[.110,.070,.025],'tax':.18,'credit_loss_rate':.006,'debt_rate':.035,'fx_cost_rate':.005,'liquid_yield':.018,'nci_share':.005,'parent_profit_share':.77,'parent_cash_share':.75,'payout':.80,'payout_pause_years':0,'excess_release':.15,'release_start':6,'min_cash_rate':.07,'parent_min_fraction':.55,'nwc_rate':None,'maintenance_rate':.025,'core_growth_capital_rate':.10,'project_high_capex':.73044,'project_fluid_capex':.50,'project_high_sales':1.5,'project_fluid_sales':.60,'project_margin':.20,'project_wc_rate':.187824,'project_delay':0,'project_replacement_fraction':0.,'extra_commitment':0.,'project_overrun':1.,'financial_haircut':0.,'financial_lock_years':0,'internal_ar_delay':0.,'internal_ar_recover':3,'internal_note_pay':0.,'parent_opening_shift':0.,'loan_recovery_start':999,'loan_recovery_rate':.1,'liquid_sweep':.80,'subs_reserve_always':False,'parent_reserve_always':False,'subs_reserve_cap':.75,'chongqing':False,'chongqing_ownership':.60,'cyclical':False,'structural':False,'severe':False,'no_refinance':False,'cancel':True,'award_fail':False}
BASE['nwc_rate']=OPEN['nwc']/8.10

def config(name='base',**kw):
 c=copy.deepcopy(BASE);c.update(kw);c['name']=name;return c

def growth_rate(c,y):
 return c['growth'] if y<=5 else c['growth']+(c['terminal_growth']-c['growth'])*min((y-5)/10,1)

def project(c,y,kind):
 delay=c['project_delay']; k=y-delay
 sales=c['project_'+kind+'_sales']
 ramp=[.10,.35,.65,.85,1.0] if kind=='high' else [0,.15,.50,.80,1.0]
 rev=0 if k<=0 else sales*ramp[min(k-1,4)]*((1+c['terminal_growth'])**max(k-5,0))
 capex=c['project_'+kind+'_capex']*c['project_overrun']*([.65,.35][k-1] if 1<=k<=2 else 0)
 return rev,capex

def legal_profit(retained,reserve,profit,cap,always=False):
 # Losses are offset before reserve transfers; retained can be negative.
 post=retained+profit; reserve_add=min(max(post,0),max(profit-max(-retained,0),0)*.1)
 if not always: reserve_add=min(reserve_add,max(cap-reserve,0))
 return post-reserve_add,reserve+reserve_add,reserve_add

def distribution(retained,cash,min_cash,requested):
 return min(max(retained,0),max(cash-min_cash,0),max(requested,0))

def validate_inputs(c):
 # Narrow domain checks; loss-making margins, high costs and severe contractions remain valid.
 if not isinstance(c,dict):raise ValueError('config must be a dict')
 if set(c)!=set(BASE):raise ValueError('config keys must match BASE')
 boolean_keys={k for k,v in BASE.items()if isinstance(v,bool)}
 integer_min={'years':1,'payout_pause_years':0,'release_start':1,'project_delay':0,'financial_lock_years':0,'internal_ar_recover':1,'loan_recovery_start':1}
 fractions={'tax','nci_share','parent_profit_share','parent_cash_share','excess_release','parent_min_fraction','project_replacement_fraction','financial_haircut','loan_recovery_rate','liquid_sweep','chongqing_ownership'}
 def finite_number(v,label):
  if isinstance(v,bool)or not isinstance(v,(int,float))or not isfinite(v):raise ValueError(label+' must be a finite number')
 for k,v in c.items():
  if k=='name':
   if not isinstance(v,str)or not v:raise ValueError('name must be a nonempty string')
  elif k in boolean_keys:
   if not isinstance(v,bool):raise ValueError(k+' must be boolean')
  elif k in integer_min:
   if isinstance(v,bool)or not isinstance(v,int)or v<integer_min[k]:raise ValueError(k+' must be an integer >= '+str(integer_min[k]))
  elif k=='sbc_schedule':
   if not isinstance(v,(list,tuple)):raise ValueError('sbc_schedule must be a numeric sequence')
   for i,x in enumerate(v):finite_number(x,'sbc_schedule['+str(i)+']')
  elif k=='post5_discount'and v is None:continue
  else:finite_number(v,k)
  if k in fractions and not 0<=v<=1:raise ValueError(k+' must be within [0,1]')
  if k in {'discount','post5_discount'}and v is not None and v<=-1:raise ValueError(k+' must exceed -1')
  if k in {'growth','terminal_growth'}and v<-1:raise ValueError(k+' cannot imply negative revenue by falling below -100%')
 for k in ['core_revenue','project_high_capex','project_fluid_capex','project_high_sales','project_fluid_sales','project_overrun','extra_commitment','payout','min_cash_rate','internal_ar_delay','internal_note_pay','subs_reserve_cap']:
  if c[k]<0:raise ValueError(k+' must be nonnegative')
 for k,v in OPEN.items():finite_number(v,'OPEN.'+k)
 if OPEN['shares']<=0:raise ValueError('OPEN.shares must be positive')
 if not 0<=OPEN['parent_cash_share']<=1:raise ValueError('OPEN.parent_cash_share must be within [0,1]')

def run(c):
 validate_inputs(c)
 o=OPEN; cash=o['cash'];fin=o['financial'];debt=o['debt'];lease=o['lease'];award=o['award'];shares=o['shares'];nwc=o['nwc'];ppe=o['ppe'];other=o['other'];nci=o['nci'];gre=o['retained'];
 pc=(cash+fin)*o['parent_cash_share']+c['parent_opening_shift'];sc=cash+fin-pc
 # Cash+financial budgets: financial redemption is separately tracked, not new earnings.
 p_re=o['parent_retained'];s_re=gre-p_re+o['unrealized_profit']-o['elimination_dta'];p_res=o['reserve'];s_res=.10
 p_loan=o['internal_loan'];iar=o['internal_ar'];inote=o['internal_note_proxy'];
 eq=o['equity']; core=c['core_revenue'];proj_prev=0.;oldrev=8.10; df=1.;pv=0.;rows=[];failed=None;arrears=0.;initial_award=award
 opening_identity=cash+fin+nwc+ppe+other-debt-lease-award-eq
 assert abs(opening_identity)<1e-7,opening_identity
 for y in range(1,c['years']+1):
  start={'cash':cash,'financial':fin,'debt':debt,'lease':lease,'award':award,'shares':shares,'nwc':nwc,'ppe':ppe,'other':other,'equity':eq,'nci':nci,'parent_cash':pc,'subs_cash':sc,'parent_retained':p_re,'subs_retained':s_re,'parent_reserve':p_res,'subs_reserve':s_res,'internal_ar':iar,'internal_loan':p_loan,'internal_note':inote,'group_retained':gre}
  if y>1:core*=1+growth_rate(c,y)
  rh,ch=project(c,y,'high');rf,cf=project(c,y,'fluid');cq=0.;rq=0.;nci_project=0.
  if c['chongqing']:
   cq=[.08,.08,.06,.04,.032986][y-1]if y<=5 else 0
   rq=[0,.025,.07,.13,.176][min(y-1,4)]*(1+c['terminal_growth'])**max(y-5,0)
  multiplier=([.88,.92,.98,1.,1.][min(y-1,4)] if c['cyclical'] else 1.)
  if c['structural']:multiplier*=.85*(.985**max(y-3,0)); rh*=.5;rf*=.5;rq*=.5
  if c['severe']:multiplier*=.45;rh*=.2;rf*=.2
  replacement_sales=(rh+rf)*c['project_replacement_fraction']
  effective_core=max(core*multiplier-replacement_sales,0)
  revenue=effective_core+rh+rf+rq
  margin=c['cash_ebit_margin']-(.035 if c['cyclical'] and y<=2 else 0)-(.07 if c['structural'] else 0)-(.40 if c['severe'] else 0)
  replacement=revenue*c['replacement_comp'] if y>=4 else 0.
  ebit_cash=effective_core*margin+(rh+rf)*c['project_margin']+rq*.20-replacement
  # Cash operating margin is after depreciation; known grants are separate noncash expense.
  sbc=c['sbc_schedule'][y-1]if y<=len(c['sbc_schedule']) else 0.
  credit_loss=revenue*c['credit_loss_rate']; ebit=ebit_cash-credit_loss-sbc
  interest=debt*c['debt_rate']+lease*c['debt_rate'];liq_income=(cash+fin)*c['liquid_yield'];
  fx_cost=revenue*c['fx_cost_rate'];pretax=ebit-interest+liq_income-fx_cost;tax=max(pretax,0)*c['tax'];net=pretax-tax
  nci_profit=net*c['nci_share']
  if c['chongqing']:nci_project=rq*.20*(1-c['tax'])*(1-c['chongqing_ownership']);nci_profit+=nci_project
  owner_profit=net-nci_profit;nci+=nci_profit
  nci_div=min(max(nci,0),max(nci_profit,0)*.50);nci-=nci_div
  # Current assets and operating trade liabilities scale jointly. Loss is separately expensed;
  # NWC is net of recurring allowance, with replenishment of receivables/inventory in operating cost.
  required_nwc=effective_core*c['nwc_rate']+(rh+rf)*c['project_wc_rate']+rq*.22
  if c['cyclical'] and y<=2:required_nwc+=.25
  if c['structural']:required_nwc+=.35
  dnwc=required_nwc-nwc;nwc=required_nwc
  maintenance=effective_core*c['maintenance_rate']+(rh+rf+rq)*.025
  core_growth=max(effective_core-(oldrev-proj_prev),0)*c['core_growth_capital_rate'];
  capex=maintenance+core_growth+ch+cf+cq+(c['extra_commitment']if y==1 else 0)
  depreciation=min(ppe,.08*ppe);ppe+=capex-depreciation
  cash_operating=net+sbc+depreciation-dnwc
  operating_to_parent=(cash_operating-nci_div)*c['parent_cash_share']
  parent_capex=maintenance*.30+core_growth*.30+ch+(c['extra_commitment']if y==1 else 0)
  pc+=operating_to_parent-parent_capex;sc+=(cash_operating-nci_div)-operating_to_parent-(capex-parent_capex)
  cash+=cash_operating-capex-nci_div
  # Actual financial principal becomes cash, with explicit haircut; no duplicate asset addition.
  redeem=fin if y>c['financial_lock_years'] else 0.
  loss=redeem*c['financial_haircut'];cash+=redeem-loss;fin-=redeem
  pc-=loss*o['parent_cash_share'];sc-=loss*(1-o['parent_cash_share']);owner_profit-=loss;net-=loss
  # Legal entity budgets, not identified debtor allocation or fabricated statutory accounts.
  p_own=owner_profit*c['parent_profit_share'];s_own=owner_profit-p_own
  s_re,s_res,s_transfer=legal_profit(s_re,s_res,s_own,c['subs_reserve_cap'],c['subs_reserve_always'])
  # Reserve transfers reclassify legal capital; not group expense/cash loss.
  refund=0.;cancelled=0.;vest=0.
  if y==1 and c['cancel']:
   refund=o['cancel_cash'];cancelled=o['cancel_shares'];shares-=cancelled;award-=refund;cash-=refund;pc-=refund
  failed_grant_cash=0.
  if c['award_fail'] and y==1:
   # Source-identified 2026 grant only; no invented conversion price for legacy awards.
   failed_grant_cash=113006889.97/1e9; failed_grant_shares=4182338/1e9
   refund+=failed_grant_cash;cancelled+=failed_grant_shares;shares-=failed_grant_shares
   cash-=failed_grant_cash;pc-=failed_grant_cash;award-=failed_grant_cash
  vest_base=initial_award-(113006889.97/1e9 if c['award_fail'] else 0.)
  vest=min(award,vest_base*[.45,.35,.20][y-1])if y<=3 else 0.;award-=vest
  # External lease principal actual amortization; no omitted debt in owner cash.
  lease_paid=min(lease,o['lease']/3);lease-=lease_paid;cash-=lease_paid;pc-=lease_paid*.5;sc-=lease_paid*.5
  # Material internal timing test preserves consolidated cash; identity remains unknown.
  trade_shift=c['internal_ar_delay']if y==1 else (-c['internal_ar_delay']if y==c['internal_ar_recover']else 0.)
  if trade_shift<0:trade_shift=-min(-trade_shift,max(sc,0))
  pc-=trade_shift;sc+=trade_shift;iar+=trade_shift
  notes_paid=min(inote,c['internal_note_pay'])if y==1 else 0.;pc-=notes_paid;sc+=notes_paid;inote-=notes_paid
  minimum=revenue*c['min_cash_rate'];pmin=minimum*c['parent_min_fraction'];smin=minimum-pmin
  # Locked investment cannot satisfy payment-floor tests until redemption.
  locked_parent=fin*o['parent_cash_share'];locked_sub=fin*(1-o['parent_cash_share'])
  down=min(max(smin-(sc-locked_sub),0),max(pc-locked_parent-pmin,0));pc-=down;sc+=down;p_loan+=down
  loan_repay=min(p_loan*c['loan_recovery_rate'],max(sc-locked_sub-smin,0))if y>=c['loan_recovery_start']else 0.;pc+=loan_repay;sc-=loan_repay;p_loan-=loan_repay
  s_request=max(s_own,0)*.70+(max(sc-locked_sub-smin,0)*c['excess_release']if y>=c['release_start']else 0)
  sub_div=distribution(s_re,sc-locked_sub,smin,s_request);s_re-=sub_div;sc-=sub_div;pc+=sub_div
  # Current-year newly declared subsidiary distribution is new parent investment income.
  # Apply one annual loss-offset/reserve calculation to own profit + new investment income.
  # Collection of a dividend receivable already recognized in a prior year is NOT included;
  # the disclosed old dividend receivable was collected by H1 and is absent from this opening.
  parent_annual_profit=p_own+sub_div
  p_re,p_res,p_transfer=legal_profit(start['parent_retained'],start['parent_reserve'],parent_annual_profit,start['shares']*.5,c['parent_reserve_always'])
  gre+=owner_profit-p_transfer-s_transfer
  # Debts finance operating shortage only, never the requested dividend.
  capacity=(0 if c['no_refinance'] else max(o['debt'],revenue*.25))
  mandatory=max(debt-capacity,0)
  # Creditor priority uses actual cash in each legal pool; no proportional overdraft.
  repayp=min(mandatory,max(pc-locked_parent-pmin,0))
  repays=min(mandatory-repayp,max(sc-locked_sub-smin,0))
  repayment=repayp+repays;cash-=repayment;debt-=repayment;pc-=repayp;sc-=repays
  shortage=max(pmin-(pc-locked_parent),0)+max(smin-(sc-locked_sub),0)
  draw=min(shortage,max(capacity-debt,0));debt+=draw;cash+=draw
  pdraw=min(draw,max(pmin-(pc-locked_parent),0));pc+=pdraw;sc+=draw-pdraw
  # Optional cash sweep repays debt with genuine surplus before shareholder payments.
  sweep=min(debt,max(cash-minimum-(.4 if y<=2 else 0),0)*c['liquid_sweep'])if not c['no_refinance']else 0
  payp=min(sweep,max(pc-locked_parent-pmin,0));pays=min(sweep-payp,max(sc-locked_sub-smin,0));sweep=payp+pays
  cash-=sweep;debt-=sweep;pc-=payp;sc-=pays;repayment+=sweep
  request=max(owner_profit,0)*c['payout']+(max(pc-locked_parent-pmin,0)*c['excess_release']if y>=c['release_start']else 0)
  constraint_gap=max(pmin-(pc-locked_parent),0)+max(smin-(sc-locked_sub),0)
  unresolved_maturity=max(mandatory-repayment,0)
  blocked=constraint_gap>1e-9 or unresolved_maturity>1e-9
  div=0. if blocked or y<=c['payout_pause_years'] or draw>repayment+1e-9 else distribution(p_re,pc-locked_parent,pmin,request);pc-=div;cash-=div;p_re-=div;gre-=div
  eq+=net-nci_div-div+sbc+vest
  # An unresolved funding path is not assumed bankruptcy. Stop valuation, retain all claims.
  # Negative cash expenditure denotes unpaid operating amounts, represented as creditor arrears.
  # No shareholder receives cash on a path that fails required maturity or operating floors.
  if blocked:
   failed=y
   parent_unpaid=max(locked_parent-pc,0);subs_unpaid=max(locked_sub-sc,0)
   arrears=parent_unpaid+subs_unpaid;pc+=parent_unpaid;sc+=subs_unpaid;cash+=arrears
  rate=c['post5_discount']if y>5 and c['post5_discount']is not None else c['discount'];df*=1+rate;dps=div/shares;pv+=dps/df
  row={'year':y,'start':start,'core_revenue':effective_core,'replacement_sales':replacement_sales,'high_project_revenue':rh,'fluid_project_revenue':rf,'chongqing_revenue':rq,'revenue':revenue,'cash_ebit':ebit_cash,'credit_loss':credit_loss,'sbc':sbc,'ebit':ebit,'interest':interest,'liquid_income':liq_income,'fx_cost':fx_cost,'tax':tax,'net_income':net,'owner_profit':owner_profit,'nci_profit':nci_profit,'nci_dividend':nci_div,'nwc_change':dnwc,'nwc':nwc,'maintenance':maintenance,'core_growth_capex':core_growth,'high_capex':ch,'fluid_capex':cf,'chongqing_capex':cq,'capex':capex,'depreciation':depreciation,'ppe':ppe,'other':other,'cash_operating':cash_operating,'parent_external_operating_cash':operating_to_parent,'parent_capex':parent_capex,'financial_redeemed':redeem,'financial_loss':loss,'financial':fin,'parent_own_profit':p_own,'parent_new_investment_income':sub_div,'parent_annual_statutory_profit':parent_annual_profit,'subs_own_profit':s_own,'parent_reserve_transfer':p_transfer,'subs_reserve_transfer':s_transfer,'parent_reserve':p_res,'subs_reserve':s_res,'parent_retained':p_re,'subs_retained':s_re,'group_retained':gre,'refund_cash':refund,'cancelled_shares':cancelled,'vest_release':vest,'award':award,'shares':shares,'lease_paid':lease_paid,'lease':lease,'internal_ar_shift':trade_shift,'internal_ar':iar,'internal_notes_paid':notes_paid,'internal_note':inote,'downstream_loan':down,'loan_repayment':loan_repay,'internal_loan':p_loan,'subs_dividend':sub_div,'debt_capacity':capacity,'mandatory_repayment':mandatory,'borrowed':draw,'repaid':repayment,'debt':debt,'min_cash':minimum,'parent_min_cash':pmin,'subs_min_cash':smin,'parent_cash_financial':pc,'subs_cash_financial':sc,'cash':cash,'equity':eq,'nci_equity':nci,'dividend':div,'dps':dps,'discount_factor':df,'pv_dividend':dps/df,'arrears':arrears,'unresolved':bool(failed),'unresolved_maturity':unresolved_maturity,'operating_floor_shortfall':constraint_gap}
  row['group_balance_residual']=cash+fin+nwc+ppe+other-debt-lease-award-arrears-eq
  row['cash_pool_residual']=pc+sc-cash-fin
  row['retained_elimination_residual']=p_re+s_re-gre-(o['unrealized_profit']-o['elimination_dta'])
  rows.append(row);oldrev=revenue;proj_prev=rh+rf+rq
  if failed:break
 value=None if failed else pv
 first5=[x['dps']for x in rows[:5]]
 df5=rows[4]['discount_factor']if len(rows)>=5 else None
 continuation=None if failed or df5 is None else sum(x['pv_dividend']for x in rows[5:])*df5
 return {'config':c,'opening':o,'rows':rows,'value':value,'distributions_first5':first5,'continuation_year5':continuation,'failure_year':failed,'first5_pv':sum(x['pv_dividend']for x in rows[:5]),'post5_pv_fraction':None if value is None or value==0 else (value-sum(x['pv_dividend']for x in rows[:5]))/value,'remaining_book_equity_at_horizon':eq,'tail_not_automatically_liquidated':True}

CASES=[config(),config('attribution_flat_existing',growth=0,terminal_growth=0,project_high_sales=0,project_fluid_sales=0,project_high_capex=0,project_fluid_capex=0,excess_release=0),config('attribution_existing_growth',project_high_sales=0,project_fluid_sales=0,project_high_capex=0,project_fluid_capex=0,excess_release=0),config('attribution_growth_projects',excess_release=0),config('already_paid_boundary',project_high_capex=.65,project_fluid_capex=.45),config('project_replacement20',project_replacement_fraction=.20),config('conditional_early_redemption_remedy',no_refinance=True,financial_haircut=.10,project_delay=2,extra_commitment=.35098004535,payout_pause_years=2),config('no_refinance_remediation',no_refinance=True,financial_lock_years=3,project_delay=2,extra_commitment=.35098004535,payout_pause_years=2),config('core_low',growth=.03,cash_ebit_margin=.23,project_high_sales=1.3,project_fluid_sales=.5,discount=.095,tax=.19),config('core_high',growth=.05,cash_ebit_margin=.25,project_high_sales=1.7,project_fluid_sales=.7,discount=.085,tax=.17),config('cycle',cyclical=True,project_delay=1),config('structural',structural=True,growth=.01,terminal_growth=0,project_delay=2),config('strong_execution',growth=.06,cash_ebit_margin=.26,project_high_sales=2.,project_fluid_sales=.8),config('persistent_fx2pct',fx_cost_rate=.02),config('margin_minus2pp',cash_ebit_margin=.22),config('working_capital_plus10pp',nwc_rate=BASE['nwc_rate']+.10),config('unallocated_commitments_additional',extra_commitment=.35098004535),config('projects_delay2',project_delay=2),config('projects_overrun25',project_overrun=1.25),config('financial_lock3_haircut5',financial_lock_years=3,financial_haircut=.05),config('internal_ar_delay_full',internal_ar_delay=OPEN['internal_ar']),config('internal_note_settlement',internal_note_pay=OPEN['internal_note_proxy']),config('parent_opening_cash_minus0_5',parent_opening_shift=-.5),config('no_refinance',no_refinance=True),config('no_refinance_locked',no_refinance=True,financial_lock_years=3),config('unresolved_severe',severe=True,no_refinance=True),config('unapproved_chongqing60',chongqing=True,chongqing_ownership=.60),config('unapproved_chongqing100',chongqing=True,chongqing_ownership=1.),config('payout60_noextra',payout=.60,excess_release=0),config('subs_reserve_continues',subs_reserve_always=True),config('parent_reserve_continues',parent_reserve_always=True),config('grant_failure',award_fail=True),config('cancel_not_executed',cancel=False),config('parent_profit_share60',parent_profit_share=.60),config('liyang_repayment_after5',loan_recovery_start=5),config('holder_cont_low',post5_discount=.095),config('holder_cont_high',post5_discount=.085)]

def auxiliary():
 # Independent no-growth earnings-power: historical normalized operating profit ranges;
 # full remaining project spend charged, separate mature returns ramped, not main future EBITDA.
 cases=[]
 for label,ebit,tax,r,capex,project_profit in [('low',1.55,.20,.10,1.70000,.17),('base',1.75,.18,.095,1.70000,.22),('high',1.95,.17,.09,1.70000,.27)]:
  maintenance_extra=.05; normalized=(ebit*(1-tax)-maintenance_extra)*(1-.005)
  # Financial principal at face (after known dividend), all debt/lease and award refund-reserve;
  # no financial interest capitalized in operating earnings.
  liquid=OPEN['cash']+OPEN['financial'];operating_cash=.07*8.1
  netbridge=liquid-operating_cash-OPEN['debt']-OPEN['lease']-OPEN['award']+OPEN['award']/(1+r)**3
  # Full remaining two-project fixed budgets1.23044bn plus high-project full WC0.46956bn.
  # No unexplained prior-paid credit; fluid WC scope remains separately uncertain.
  # Award cash reserve released only after3years, not a permanent expense with diluted shares.
  total=normalized/r+netbridge-capex+project_profit/r/(1+r)**3
  cases.append({'name':label,'normalized_ebit':ebit,'tax':tax,'discount':r,'maint_above_DA':maintenance_extra,'normal_owner_cash':normalized,'net_bridge':netbridge,'remaining_project_net_investment':capex,'mature_incremental_owner_profit':project_profit,'project_delay_years':3,'equity_value':total,'value_per_share':total/OPEN['shares']})
 return cases

def main():
 print(json.dumps({'schema':'neway_full_annual_owner_cash_v2','information_cutoff':'2026-10-30T11:00:00Z','units':'CNY bn; shares bn; per-share CNY','cases':[run(c)for c in CASES],'auxiliary':auxiliary()},ensure_ascii=False,separators=(',',':'),allow_nan=False))
if __name__=='__main__':main()
