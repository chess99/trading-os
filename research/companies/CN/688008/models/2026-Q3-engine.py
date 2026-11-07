#!/usr/bin/env python3
"""CN688008: standalone, RMB bn. All future entity allocations are economic budgets, not statutory certification."""
import copy,json,sys,math
ASOF='2026-10-30T12:00:00Z'
ACTUAL={'cash':15.798925948,'trading':3.06852248221,'equity_investment':.34461107437,'oci_equities':.02680362539,'other_financial':.40476230098,'paid_oct_dividend':.2416873318,'oct_new_buyback':.1002381,'bank_and_lease':.13630174904,'registered_shares':1.220538021,'treasury_shares':.012721362,'mother_re_h1':.40536755315,'mother_reserve':.35195873425,'internal_face':2.23240648736,'mother_h1_external_other':.000215297,'hq_external_paid_ytd':.27975,'hq_parent_new_budget':.24975}
NAMES=['P','K','M','C','SH','PROP','VC','FUND','HQ','U']
# Entity financial pools are constrained allocations of group external assets, not assertions of Q3 separate cash balances.
BASE={'r':.10,'old':7.2,'new':1.65,'hq':.18,'cpu':.35,'gm':.66,'newgm':.64,'rd':.13,'sga':.075,'growth_old':.17,'growth_new':.35,'growth_hq':.55,'terminal_g':.02,'upstream':.8,'release_start':7,'release_rate':.15,'hqtax':.25,'hq_share':7550/16570,'parent_tax':.10,'kunshan_tax':.10,'offshore_leak':.05,'finyield':.018,'fin_loss':.04,'recovery_fee':.015,'wc_ratio':.16,'fixed_ratio':.10,'cash_ratio':.10,'parent_re':.45,'internal_delay':3,'hq_fail':0,'cycle':False,'structural':False,'aux':False,'capital_allowed':False,'vest':True,'hq_backstop':.25,'pool_shift':0.0,'cayman_child_basis_scale':1.0,'payout_scale':1.0,'hq_debt_rate':.0251,'hq_loan_budget':.10,'main_failure_year':0,'aux_margin':.41,'aux_revenue':9.5,'aux_fade_margin':.32,'capital_commitment':.06392201834,'investment_commitment':.1421,'cancel_treasury':False,'parent_operating_share':.20,'kunshan_year1_tax':.10,'illiquid_yield':.02,'hq_asset_recovery':.5,'hq_fixed_recovery':.4,'hq_preference_paid':True,'opening_cash_stress':0.,'initial_taxloss_scale':1.,'guarantee_cap':.023275550134,'conditional_capital_return':True,'capital_return_start':10,'capital_return_fraction':.20,'capital_return_price':100.,'surplus_distribution_start':7,'hq_founder_current':True,'capital_return_limit':1.,'future_buyback_cash':.1997619,'future_buyback_price':280.,'future_buyback_disposition':'award','future_buyback_fees':.001,'hq_shortfall_basis':'current','investment_sale_year':0,'investment_sale_factor':1.}
SCENARIOS={
 'base':{},'hq_subscription_shortfall':{'hq_shortfall_basis':'subscription','hq_fail':1},'investment_sale_y10':{'investment_sale_year':10},'investment_sale_y20':{'investment_sale_year':20},'investment_sale_y20_haircut':{'investment_sale_year':20,'investment_sale_factor':.75},'new_plan_not_executed':{'future_buyback_cash':0.},'new_plan_upper_budget':{'future_buyback_cash':.3997619},'new_plan_cancel_unused':{'future_buyback_disposition':'cancel'},'new_plan_price100':{'future_buyback_price':100.},'core_low':{'r':.105,'growth_old':.14,'growth_new':.30,'gm':.65,'newgm':.62},
 'core_high':{'r':.095,'growth_old':.20,'growth_new':.40,'gm':.67,'newgm':.65},
 'cycle':{'cycle':True},'structural':{'structural':True,'growth_old':.06,'growth_new':.15,'gm':.59,'newgm':.56,'hq_fail':4},
 'new_product_success':{'growth_new':.50,'growth_hq':.70},'discount_plus_1pp':{'r':.11},
 'gross_minus_3pp':{'gm':.63,'newgm':.61},'upstream_slow':{'upstream':.35,'internal_delay':10,'release_start':12,'release_rate':.08},
 'no_capital_return':{'capital_allowed':False,'conditional_capital_return':False},'unchanged_cash_policy':{'conditional_capital_return':False,'surplus_distribution_start':0},'capital_return_delayed':{'capital_return_start':15,'capital_return_fraction':.1},'capital_return_half':{'capital_return_limit':.5},'zero_financial_yield':{'finyield':0,'illiquid_yield':0},'cancel_treasury':{'cancel_treasury':True},'no_vesting':{'vest':False},'hq_no_parent_loan':{'hq_loan_budget':0.},'hq_interest5':{'hq_debt_rate':.05},'hq_zero_recovery':{'hq_fail':1,'hq_asset_recovery':0.,'hq_fixed_recovery':0.,'opening_cash_stress':.34},'royalty_low':{'parent_operating_share':.1},'royalty_high':{'parent_operating_share':.3},'kunshan_exempt_first_year':{'kunshan_year1_tax':0.},'no_opening_taxloss':{'initial_taxloss_scale':0.},'capital_commitment_double':{'capital_commitment':.12784403668,'investment_commitment':.2842},'dividend_slow':{'payout_scale':.5},
 'tax25':{'parent_tax':.25,'kunshan_tax':.25,'offshore_leak':.13},'financial_impairment':{'fin_loss':.25},
 'hq_funding_failure':{'hq_fail':3,'hq_backstop':0},'hq_financed':{'hq_backstop':.85},'hq_early_stop':{'hq_fail':1,'hq_backstop':0},'hq_old_share':{'hq_share':.4488,'hq_backstop':.85},
 'parent_capacity_low':{'parent_re':0,'pool_shift':2},'foreign_pool_shift':{'pool_shift':2},
 'working_capital_stress':{'wc_ratio':.23,'fixed_ratio':.14},'hq_original_founder_layer':{'hq_founder_current':False,'hq_fail':1},'maximum_legal_dividends':{'surplus_distribution_start':7,'conditional_capital_return':False},'conditional_capital_return':{'conditional_capital_return':True,'surplus_distribution_start':0},'conditional_capital_return_price50':{'conditional_capital_return':True,'capital_return_price':50.,'surplus_distribution_start':0},'conditional_capital_return_price200':{'conditional_capital_return':True,'capital_return_price':200.,'surplus_distribution_start':0},'maximum_legal_plus_capital_return':{'surplus_distribution_start':7,'conditional_capital_return':True},'auxiliary':{'aux':True},'aux_low':{'aux':True,'aux_revenue':9.,'aux_margin':.38,'aux_fade_margin':.30,'r':.105},'aux_high':{'aux':True,'aux_revenue':10.,'aux_margin':.44,'aux_fade_margin':.34,'r':.095}}
def params(name):
 p=BASE.copy();p.update(SCENARIOS[name]);return p

def taxprofit(pre,loss,rate):
 use=min(max(pre,0),loss);tax=max(pre-use,0)*rate
 return pre-tax,loss-use+max(-pre,0),tax

def entity_tax(v,pre,rate,year):
 # Separate taxable losses, with five-budget-year expiry; legal RE is not itself a tax asset.
 left=max(pre,0);use=0.
 for lot in v['loss_lots']:
  x=min(left,lot['amount']);lot['amount']-=x;left-=x;use+=x
 v['loss_lots']=[x for x in v['loss_lots'] if x['amount']>1e-14]
 if pre<0:v['loss_lots'].append({'expires':year+5,'amount':-pre})
 v['taxloss']=sum(x['amount'] for x in v['loss_lots'])
 tax=left*rate
 return pre-tax,tax

def reserve_charge(re_before,profit,reserve,reg):
 # Prior deficits absorbed BEFORE annual statutory appropriation.
 return min(max(reg*.5-reserve,0),.1*min(max(profit,0),max(re_before+profit,0)))

def capped_allocation(amount,caps,weights):
 # Iterative weighted shortfall allocation, never exceeding each investor's stage-specific paid amount.
 result=[0.]*len(caps);left=min(max(amount,0),sum(caps));active=list(range(len(caps)))
 while left>1e-14 and active:
  total=sum(weights[i] for i in active)
  over=[i for i in active if left*weights[i]/total>=caps[i]-result[i]-1e-14]
  if not over:
   for i in active:result[i]+=left*weights[i]/total
   left=0.;break
  for i in over:
   x=caps[i]-result[i];result[i]+=x;left-=x;active.remove(i)
 return result

def hq_waterfall(net,share,current=True,basis='current'):
 # Contract says shortfalls use then-current holdings; stage principal entitlements remain capped.
 # Alternative subscription-class interpretation is retained as a full boundary, not treated as legal certification.
 left=max(net,0);parent=0.;stages=[]
 founder=([.0755,.02149,.00665,.00665,.02421],[7550,2149,665,665,2421]) if current else ([.051,.02149,.00665,.00665,.01421],[5100,2149,665,665,1421])
 layers=[([.24975,.05175,.198],[7550,230,880]),([.0402,.0603,.030],[7550,2010,2421]),founder]
 for caps,weights in layers:
  paid=min(left,sum(caps));allocation=capped_allocation(paid,caps,weights if basis=='current' else caps)
  parent+=allocation[0];left-=paid;stages.append({'total':paid,'parent':allocation[0],'individual_payments':allocation,'individual_caps':caps,'shortfall_basis':basis})
 parent+=left*share
 return parent,max(net,0)-parent,stages

def initial(p):
 pool=sum(ACTUAL[k] for k in ['cash','trading','equity_investment','oci_equities','other_financial'])-ACTUAL['paid_oct_dividend']-ACTUAL['oct_new_buyback']
 pools=[8.1-p['pool_shift'],3.5,5.9+p['pool_shift'],.41625,.1,.15,.1,.08375,0,.6]
 pools[8]=pool-sum(pools)
 illiquid=ACTUAL['equity_investment']+ACTUAL['oci_equities']+ACTUAL['other_financial']
 pools[2]-=illiquid
 pools[8]-=p['opening_cash_stress'];pools[0]+=p['opening_cash_stress']
 res=[ACTUAL['mother_reserve'],.25,0,0,.10,.03,0,0,0,0]
 regs=[ACTUAL['registered_shares'],.5,.0005,.00000035,.85,.815,.5,.08375,.1657,.01]
 retained=[p['parent_re'],3.,2.4,1.9,-.05,-.05,.05,0.,-.40,0.]
 cost=[0,.5,0,1.88146869632,.4165,0,.5,0.,.34103,.01]
 states={n:dict(cash=pools[i],re=retained[i],reserve=res[i],reg=regs[i],cost=cost[i],taxloss=max(-retained[i],0)*p['initial_taxloss_scale'],wc=0.,fixed=0.,face=0.,external_debt=0.,alive=True,capital=max(pools[i]-max(retained[i],0),0),wc_assets=0.,wc_payables=0.,investments=illiquid if n=='M' else 0.,loan_impairment=0.) for i,n in enumerate(NAMES)}
 # Full parent gross face; each corresponding debtor face never erased by accounting write-down.
 faces={'PROP':.91440423912,'SH':.53126669867,'K':.13815705329,'VC':.05303464220,'HQ':p['hq_loan_budget']+.00116534246,'U':.59437851162-p['hq_loan_budget']}
 assert abs(sum(faces.values())-ACTUAL['internal_face'])<1e-10
 for n,x in faces.items():states[n]['face']=x
 for v in states.values():v['loss_lots']=[{'expires':5,'amount':v['taxloss']}] if v['taxloss'] else []
 states['P']['other_obligation']=.08100773010+.01530432854
 states['HQ']['external_debt']=.11282987518
 states['P']['external_debt']=ACTUAL['bank_and_lease']-.11282987518
 for n in NAMES:states[n]['costs']={}
 for n in ['K','C','SH','VC','HQ','U']:states[n]['costs']['P']=states[n]['cost']
 for n,x in {'M':1.2,'SH':.4335,'PROP':.8,'FUND':.058625}.items():states[n]['costs']['C']=x*p['cayman_child_basis_scale']
 return states

def run(p=None,years=240,switch_after5=None):
 p=copy.deepcopy(p or BASE);assert not p['capital_allowed'], 'No modeled lawful capital-return route';p0=copy.deepcopy(p);s=initial(p);registered=ACTUAL['registered_shares'];treasury=ACTUAL['treasury_shares'];treasury_cost=.98772587259+.1002381;parent_premium=13.13096305643;shares=ACTUAL['registered_shares']-ACTUAL['treasury_shares'];shares0=shares
 holder_units=1.;capital_return_cumulative=0.;capital_return_original_budget=None;future_inventory=0.
 revenues=[p['old'],p['new'],p['hq'],p['cpu']];rows=[];hq_funded=0.;cum_d=0.;pvop=0.;pvdiv=0.;pvcapital=0.;pvfinancial=0.;pv_nci=0.
 def move(src,dst,x):
  if x< -1e-10 or x>s[src]['cash']+1e-8:raise AssertionError(('transfer',src,dst,x,s[src]['cash']))
  s[src]['cash']-=x;s[dst]['cash']+=x
 for t in range(1,years+1):
  if t==6 and switch_after5:p.update(switch_after5)
  for v in s.values():
   v['loss_lots']=[x for x in v['loss_lots'] if x['expires']>=t];v['taxloss']=sum(x['amount'] for x in v['loss_lots'])
  before=copy.deepcopy(s);group_begin=sum(v['cash'] for v in s.values());receipts={n:0. for n in NAMES};profits={n:0. for n in NAMES};charges={n:0. for n in NAMES};taxes={n:0. for n in NAMES};finprofits={n:0. for n in NAMES};fincash={n:0. for n in NAMES};opcash={n:0. for n in NAMES};divs={n:0. for n in NAMES};caps={n:0. for n in NAMES};intpaid={n:0. for n in NAMES};exits=[];external_nci=0.;cross_tax=0.;return_tax=0.;fees=0.;external_in=0.;bankpaid=0.;trade_exit_paid=0.;fcff=0.;interest_paid=0.;hq_claim_loss=0.;unfunded_hq=0.;commitment_paid=0.;investment_paid=0.;buyback_cash=0.;buyback_fees=0.;future_award_sbc=0.;future_award_shares=0.;future_cancel_shares=0.;future_cost_removed=0.;investment_sales={}
  if t==1 and p['future_buyback_cash']:
   buyback_cash=p['future_buyback_cash'];buyback_fees=buyback_cash*p['future_buyback_fees'];future_inventory=buyback_cash/p['future_buyback_price']
   s['P']['cash']-=buyback_cash+buyback_fees;shares-=future_inventory;treasury+=future_inventory;treasury_cost+=buyback_cash+buyback_fees
  if t==3 and future_inventory:
   future_cost_removed=treasury_cost*future_inventory/treasury;treasury_cost-=future_cost_removed;treasury-=future_inventory
   if p['future_buyback_disposition']=='award':
    future_award_shares=future_inventory;shares+=future_inventory;future_award_sbc=p['future_buyback_cash'];parent_premium+=future_award_sbc-future_cost_removed
   else:
    future_cancel_shares=future_inventory;registered-=future_inventory;parent_premium+=future_inventory-future_cost_removed;s['P']['reg']=registered
   future_inventory=0.
  if t>1:
   for i,g0 in enumerate([p['growth_old'],p['growth_new'],p['growth_hq'],.03]):
    g=p['terminal_g']+(g0-p['terminal_g'])*max(0,1-(t-2)/10)
    if p['structural'] and t>=4:g=-.05 if i==0 else (0 if i in [1,2] else -.02)
    revenues[i]*=1+g
  rev=revenues[:]
  if p['cycle'] and t<=3:rev=[x*[.72,.85,.95][t-1] for x in rev]
  if not s['HQ']['alive']:rev[2]=0.
  gm=p['gm']+(.60-p['gm'])*min((t-1)/12,1);ngm=p['newgm']+(.58-p['newgm'])*min((t-1)/12,1)
  if p['structural']:gm=min(gm,.52);ngm=min(ngm,.50)
  mainrev=rev[0]+rev[1]+rev[3];main_ebit=rev[0]*gm+rev[1]*ngm+rev[3]*.20-mainrev*(p['rd']+p['sga']+.035*min((t-1)/12,1))
  if p['aux']:
   # Independent normalized earning-power entrance: orders-constrained aggregate sales, no product-growth inheritance.
   mainrev=p['aux_revenue']*(1.02**(t-1));margin=p['aux_margin']+(p['aux_fade_margin']-p['aux_margin'])*min((t-1)/10,1)
   main_ebit=mainrev*margin;rev=[mainrev,0.,rev[2],0.]
  # No financial interest/FV within operating EBIT. Cash replacement of future compensation remains expense.
  ps=p['parent_operating_share'];allocation={'P':ps,'K':(1-ps)*.4375,'M':(1-ps)*.5,'SH':(1-ps)*.0625}
  rental=min(.06*(1+p['terminal_g'])**(t-1),.025*mainrev)
  for n,w in allocation.items():profits[n]=(main_ebit-rental)*w
  profits['PROP']=rental
  hqexpense=.28*(1.10**min(t-1,5))*(1+p['terminal_g'])**max(t-6,0)
  profits['HQ']=rev[2]*.60-hqexpense if s['HQ']['alive'] else 0.
  h=s['HQ'];hq_stop=bool(p['hq_fail'] and t>=p['hq_fail'])
  if h['alive']:
   opening_wc=.03 if t==1 else h['wc'];opening_fixed=.25 if t==1 else h['fixed']
   debt_due=min(h['external_debt'],.11282987518/5) if t<=5 else 0.
   pre=profits['HQ']-h['external_debt']*p['hq_debt_rate']-h['face']*.025
   anticipated=taxprofit(pre,h['taxloss'],p['hqtax'])[0]
   growth_fixed=max(rev[2]-(p['hq'] if t==1 else rows[-1]['revenue'][2]),0)*.15
   commitment=p['capital_commitment']/2 if t<=2 else 0.
   ending=h['cash']+anticipated+h['cash']*p['finyield']-(rev[2]*.22-opening_wc)-growth_fixed-commitment-debt_due
   needed=max(.08-ending,0)
   capacity=min(max(p['hq_backstop']-hq_funded,0),max(s['P']['cash']-.2,0))
   if needed>capacity+1e-10:hq_stop=True
   if not hq_stop and needed:
    move('P','HQ',needed);h['face']+=needed;hq_funded+=needed
   if hq_stop:
    # Stop the unaffordable whole-year budget before incurring it; no refund of fictional negative cash.
    rev[2]=0.;profits['HQ']=0.;h['wc']=opening_wc;h['fixed']=opening_fixed
    if t==1:h['wc_assets']=.05;h['wc_payables']=.02
  # Debt is owed by Hengqin, not the property pool. Both external and internal interest are cash paid.
  if s['HQ']['alive'] and not hq_stop:
   extinterest=s['HQ']['external_debt']*p['hq_debt_rate'];intinterest=s['HQ']['face']*.025
   profits['HQ']-=extinterest+intinterest;profits['P']+=intinterest;interest_paid=extinterest
  if p['structural'] and s['HQ']['alive'] and not hq_stop:profits['HQ']-=.08
  lease_interest=s['P']['external_debt']*.03;profits['P']-=lease_interest;interest_paid+=lease_interest
  # Property operating occupancy cost is embedded in margin; rent is internal, not additional group profit.
  operating_pretax=profits.copy()
  for n,v in s.items():
   if not v['alive'] or (n=='HQ' and hq_stop):continue
   rate=p['parent_tax'] if n=='P' else (p['kunshan_year1_tax'] if n=='K' and t==1 else p['kunshan_tax'] if n=='K' else .12 if n=='M' else p['hqtax'] if n=='HQ' else .15 if n in ['SH','VC'] else .25 if n=='PROP' else 0.)
   operating_profit,tx=entity_tax(v,profits[n],rate,t);taxes[n]+=tx
   # All principal yields; liquidity/capital-budget cash is not presumed worthless.
   finincome=max(v['cash'],0)*p['finyield']+v['investments']*p['illiquid_yield'];financial_profit,ftx=entity_tax(v,finincome,rate,t);taxes[n]+=ftx;finprofits[n]=financial_profit
   impairment= (p['fin_loss']*(.34461107437+.02680362539+.40476230098) if n=='M' and t==1 else 0.)
   v['investments']-=impairment;fincash[n]=financial_profit;finprofits[n]-=impairment
   wn=mainrev*p['wc_ratio']*allocation.get(n,0)+(rev[2]*.22 if n=='HQ' else 0)
   fw={'P':.15,'K':.20,'M':.20,'PROP':.45}.get(n,0)
   oldrev=(p['old']+p['new']+p['cpu']) if t==1 else rows[-1]['revenue'][0]+rows[-1]['revenue'][1]+rows[-1]['revenue'][3]
   initial_fixed=(2.27206572549-.25)*fw+(.25 if n=='HQ' else 0)
   fn=(initial_fixed if t==1 else v['fixed'])+max(mainrev-oldrev,0)*p['fixed_ratio']*({'P':.30,'K':.30,'M':.35,'SH':.05}.get(n,0))+(initial_fixed*p['terminal_g'] if n=='PROP' and t>1 else 0)+(max(rev[2]-(p['hq'] if t==1 else rows[-1]['revenue'][2]),0)*.15 if n=='HQ' else 0)
   # Opening operating assets already exist: only incremental required capital, never charge whole capacity again.
   if t==1:
    v['wc']=(.81249959698-.03)*allocation.get(n,0)+(.03 if n=='HQ' else 0)
    v['fixed']=initial_fixed
    before[n]['wc']=v['wc'];before[n]['fixed']=v['fixed']
   v['wc_assets']=wn+(mainrev*.11*allocation.get(n,0)+(rev[2]*.10 if n=='HQ' else 0));v['wc_payables']=v['wc_assets']-wn
   d_wc=wn-v['wc'];d_fixed=fn-v['fixed'];v['wc']=wn;v['fixed']=fn
   capex_net=d_fixed
   if t<=2 and n=='HQ':
    extra=p['capital_commitment']/2;capex_net+=extra;v['fixed']+=extra;commitment_paid+=extra
   opcash[n]=operating_profit-d_wc-capex_net
   v['cash']+=opcash[n]+fincash[n];profits[n]=operating_profit+finprofits[n]
   # Noncash expense on pre-existing grants: cash earnings do not disappear, but legal RE does.
   known_sbc=(.08 if t==1 else .04 if t==2 else 0) if n=='P' and p['vest'] else 0
   profits[n]-=known_sbc+(future_award_sbc if n=='P' else 0.)
   if n=='P':parent_premium+=known_sbc
   charge=reserve_charge(v['re'],profits[n],v['reserve'],v['reg']) if n in ['K','SH','HQ','PROP','VC'] else 0
   v['re']+=profits[n]-charge;v['reserve']+=charge;charges[n]=charge
   fcff+=opcash[n]*(p['hq_share'] if n=='HQ' else 1.)
  # Existing awards conditional vesting; A shares come out of treasury, H award new shares.
  vestcash=0.;newshares=0.
  if p['vest'] and t<=2:
   anew=.001274563 if t==1 else 0.;hnew=.0002555
   newshares=anew+hnew;vestcash=(.000127928*18.22+.001146635*25.42 if t==1 else 0.)+hnew*59*.86535
   shares+=newshares;registered+=hnew;treasury-=anew
   removed_cost=treasury_cost*(anew/(treasury+anew)) if anew else 0.;treasury_cost-=removed_cost
   parent_premium+=vestcash-hnew-removed_cost;s['P']['reg']=registered
   s['P']['cash']+=vestcash;s['P']['capital']+=vestcash;external_in+=vestcash
  if p['cancel_treasury'] and t==3:
   cancelled=min(.00676,treasury);removed_cost=treasury_cost*cancelled/treasury;treasury_cost-=removed_cost;treasury-=cancelled;registered-=cancelled;parent_premium+=cancelled-removed_cost;s['P']['reg']=registered
  if t<=2:
   investment_paid=p['investment_commitment']/2;s['C']['cash']-=investment_paid;s['C']['investments']+=investment_paid
  # Conditional disposal of illiquid investments; principal becomes cash, only loss/fees reduce profit and RE.
  if t==p['investment_sale_year']:
   for n in ['M','C']:
    basis=s[n]['investments'];gross=basis*p['investment_sale_factor'];fee=gross*p['recovery_fee'];net=gross-fee;loss=basis-net
    s[n]['investments']=0.;s[n]['cash']+=net;s[n]['re']-=loss;profits[n]-=loss;finprofits[n]-=loss;external_in+=net;fees+=fee
    investment_sales[n]={'book_basis':basis,'gross':gross,'fee':fee,'net_cash':net,'accounting_loss':loss,'tax_refund':0.}
  if t<=5:
   for debtor in ['HQ','P']:
    initial_debt=.11282987518 if debtor=='HQ' else ACTUAL['bank_and_lease']-.11282987518
    pay=min(s[debtor]['external_debt'],initial_debt/5,max(s[debtor]['cash'],0)) if s[debtor]['alive'] and not(debtor=='HQ' and hq_stop) else 0
    s[debtor]['cash']-=pay;s[debtor]['external_debt']-=pay;bankpaid+=pay
   fcff-=bankpaid
  # Any finite parent support was funded before admitting the year's Hengqin budget.
  h=s['HQ'];doexit=h['alive'] and hq_stop
  if doexit:
   # Exit real assets, pay external exit fees; keep any unpaid parent face and its matching impairment.
   gross=h['cash']+p['hq_asset_recovery']*h['wc_assets']+p['hq_fixed_recovery']*h['fixed'];cost=min(gross,.04+.02*(h['wc']+h['fixed']));net=max(gross-cost,0);fees+=cost
   extface=h['external_debt']+h['wc_payables'];paid=min(net,extface);net-=paid
   extpay=paid*h['external_debt']/extface if extface else 0.;tradepay=paid-extpay
   h['external_debt']-=extpay;h['wc_payables']-=tradepay;bankpaid+=extpay;trade_exit_paid+=tradepay
   debtpay=min(net,h['face']);net-=debtpay;h['face']-=debtpay;s['P']['cash']+=debtpay
   guarantee_paid=min(max(h['wc_payables'],0),p['guarantee_cap'],max(s['P']['cash']-.2,0))
   s['P']['cash']-=guarantee_paid;h['wc_payables']-=guarantee_paid;trade_exit_paid+=guarantee_paid
   # Subrogation remains a gross parent claim; subsequent impairment does not erase debtor face.
   h['face']+=guarantee_paid
   hq_claim_loss=h['face'];s['P']['re']-=hq_claim_loss;h['loan_impairment']=hq_claim_loss
   pp,minor,water=hq_waterfall(net,p['hq_share'],p['hq_founder_current'],p['hq_shortfall_basis']);tax=max(pp-h['cost'],0)*p['parent_tax'];return_tax+=tax;s['P']['cash']+=pp-tax;s['P']['re']+=pp-h['cost']-tax;external_nci+=minor
   # Cash conservation includes actual realizations, not accounting book net assets.
   exit_asset_recovery=p['hq_asset_recovery']*h['wc_assets']+p['hq_fixed_recovery']*h['fixed'];external_in+=exit_asset_recovery
   asset_loss=h['wc_assets']+h['fixed']-exit_asset_recovery+cost;h['re']-=asset_loss
   exits.append({'subsidiary_asset_loss':asset_loss,'entity':'HQ','gross':gross,'cost':cost,'guarantee_paid':guarantee_paid,'trade_paid':tradepay,'trade_unpaid':h['wc_payables'],'external_debt_paid':extpay,'external_debt_unpaid':h['external_debt'],'parent_debt_paid':debtpay,'unpaid_face':h['face'],'parent_equity_recovery':pp,'minority_recovery':minor,'parent_basis':h['cost'],'parent_tax':tax,'waterfall':water,'unfunded_operations_stopped':max(-h['cash'],0)})
   h.update(cash=0.,wc=0.,wc_assets=0.,fixed=0.,alive=False);h['cost']=0.
  # Legal loans first, retaining gross debts when capacity is insufficient. No group profit from principal.
  for n in ['PROP','SH','K','VC','C','HQ','U']:
   v=s[n]
   if not v['alive']:continue
   target=v['face']/max(p['internal_delay']-(t-1),1) if t>=1 else 0
   paid=min(v['face'],target,max(v['cash']-.08,0));move(n,'P',paid);v['face']-=paid;intpaid[n]=paid
  # Bottom-up distributions. Subsidiary receipts recognized only once; no old declared dividend treated as new profit.
  for n,destinations in [('M',[('C',1.)]),('SH',[('P',.49),('C',.51)]),('PROP',[('C',1.)]),('VC',[('P',1.)]),('FUND',[('C',.70)]),('HQ',[('P',p['hq_share'])]),('K',[('P',1.)]),('U',[('P',1.)]),('C',[('P',1.)])]:
   v=s[n]
   if not v['alive']:continue
   floor=max(.08 if v['face']>1e-9 else .02,(mainrev*p['cash_ratio']*allocation.get(n,0)+rev[2]*.12*(n=='HQ')))
   current=max(profits[n]+receipts[n],0)
   target=p['upstream']*current+(.10*max(v['re']-current,0) if t>=3 else 0.)
   if p['surplus_distribution_start'] and t>=p['surplus_distribution_start']:target=max(v['re'],0)
   dividend=min(max(v['re'],0),target,max(v['cash']-floor,0));v['cash']-=dividend;v['re']-=dividend;divs[n]=dividend
   cap=0.;caps[n]=0.
   weight=sum(w for _,w in destinations);external_nci+=(dividend+cap)*(1-weight)
   for dest,w in destinations:
    d=dividend*w;c=cap*w;leak=d*p['offshore_leak'] if n=='C' else d*.10 if n=='FUND' else 0.;cross_tax+=leak
    # Taxable disposal spread versus remaining parent tax basis; basis usage cannot create earnings twice.
    basis=min(s[n]['costs'].get(dest,0),c);s[n]['costs'][dest]=s[n]['costs'].get(dest,0)-basis
    if dest=='P':s[n]['cost']=s[n]['costs'][dest]
    ctax=max(c-basis,0)*p['parent_tax'] if dest=='P' else 0.;return_tax+=ctax
    s[dest]['cash']+=d-leak+c-ctax
    addition=d-leak+max(c-basis,0)-ctax
    app=0. # Parent annual appropriation is calculated once after all profit and loss components.
    s[dest]['re']+=addition-app;s[dest]['reserve']+=app;charges[dest]+=app;receipts[dest]+=d-leak
  pstate=s['P'];annual_profit=profits['P']+receipts['P']-hq_claim_loss+sum(e['parent_equity_recovery']-e['parent_basis']-e['parent_tax'] for e in exits)
  parent_charge=reserve_charge(before['P']['re'],annual_profit,pstate['reserve'],pstate['reg']);pstate['re']-=parent_charge;pstate['reserve']+=parent_charge;charges['P']+=parent_charge
  floor=max(.20,mainrev*p['cash_ratio']*.22)+pstate['other_obligation']
  payout=([.20,.25,.35,.50,.60][t-1] if t<=5 else .85)*p['payout_scale']
  current=max(profits['P']+receipts['P'],0)
  target=payout*current+(.10*max(pstate['re']-current,0) if t>=6 else 0.)
  if p['surplus_distribution_start'] and t>=p['surplus_distribution_start']:target=max(pstate['re'],0)
  dividend=min(max(pstate['re'],0),target,max(pstate['cash']-floor,0));pstate['cash']-=dividend;pstate['re']-=dividend
  # Explicit conditional pro-rata reduction, never a claimed announced action. Registered shares and the original holder's units fall together.
  distribution_shares=shares;units_before=holder_units;cancelled_for_return=0.;treasury_return_cancel=0.;treasury_return_cost=0.;cap=0.;fee=0.
  if p['conditional_capital_return'] and t>=p['capital_return_start']:
   if capital_return_original_budget is None:capital_return_original_budget=pstate['capital']
   cap=min(max(capital_return_original_budget*p['capital_return_limit']-capital_return_cumulative,0),max(pstate['cash']-floor,0),max(pstate['capital'],0)*p['capital_return_fraction'],max(parent_premium,0))
   fee=cap*p['recovery_fee'];cancelled_for_return=cap/p['capital_return_price']
   assert cancelled_for_return<shares and cancelled_for_return<registered
   factor=(shares-cancelled_for_return)/shares
   treasury_return_cancel=treasury*(1-factor);treasury_return_cost=treasury_cost*(1-factor)
   treasury-=treasury_return_cancel;treasury_cost-=treasury_return_cost
   pstate['cash']-=cap;pstate['capital']-=cap;capital_return_cumulative+=cap;parent_premium-=cap+treasury_return_cost-cancelled_for_return-treasury_return_cancel
   holder_units*=factor;shares-=cancelled_for_return;registered-=cancelled_for_return+treasury_return_cancel;pstate['reg']=registered;fees+=fee
  holder_ordinary=units_before*dividend/distribution_shares;holder_capital=units_before*(cap-fee)/distribution_shares
  per=holder_ordinary+holder_capital;cum_d+=per
  cash_end=sum(v['cash'] for v in s.values());expected=group_begin+sum(opcash.values())+sum(fincash.values())+external_in-bankpaid-trade_exit_paid-investment_paid-buyback_cash-buyback_fees-external_nci-cross_tax-return_tax-dividend-cap
  # HQ liquidation costs included in external cash; parent capital realization fee belongs to holder net proceeds.
  expected-=sum(e['cost'] for e in exits)
  assert abs(cash_end-expected)<1e-6*(1+abs(cash_end)),('cash',t,cash_end,expected)
  assert all(v['cash']>=-1e-7 and v['face']>=-1e-9 for v in s.values()),('negative',t)
  df=((1+p0['r'])**min(t,5)*(1+p['r'])**max(t-5,0)) if switch_after5 else (1+p['r'])**t;pvop+=fcff/df;pvdiv+=holder_ordinary/df;pvcapital+=holder_capital/df;pvfinancial+=sum(finprofits.values())/df;pv_nci+=external_nci/df
  rows.append({'year':t,'calendar_budget':2026+t,'revenue':rev,'main_ebit':main_ebit,'operating_pretax':operating_pretax,'opening_states':before if t==1 else None,'hq_cash_rd_sga':hqexpense if h['alive'] else 0,'tax':taxes,'profit':profits,'finance_profit':finprofits,'finance_cash':fincash,'opcash':opcash,'statutory_appropriation':charges,'upstream_dividend':divs,'conditional_subcapital_realization':caps,'received_dividend':receipts,'internal_principal_paid':intpaid,'exits':exits,'trade_exit_paid':trade_exit_paid,'bank_paid':bankpaid,'crossborder_tax':cross_tax,'capital_gain_tax':return_tax,'realization_fees':fees,'nci_external_cash':external_nci,'award_proceeds':vestcash,'new_participating_shares':newshares,'shares':shares,'ordinary_dividend':dividend,'conditional_capital_realization':cap,'holder_cash_per_share':per,'group_begin_cash':group_begin,'group_end_cash':cash_end,'investment_sales':investment_sales,'forecast_buyback_cash':buyback_cash,'forecast_buyback_fees':buyback_fees,'future_award_shares':future_award_shares,'future_award_sbc':future_award_sbc,'future_cancel_shares':future_cancel_shares,'future_treasury_cost_removed':future_cost_removed,'capital_return_cumulative':capital_return_cumulative,'capital_return_original_budget':capital_return_original_budget,'holder_units_begin':units_before,'holder_units_end':holder_units,'distribution_participating_shares':distribution_shares,'capital_return_treasury_cancel':treasury_return_cancel,'capital_return_treasury_cost_removed':treasury_return_cost,'capital_return_cancelled_shares':cancelled_for_return,'holder_ordinary_cash':holder_ordinary,'holder_capital_cash':holder_capital,'registered_shares':registered,'treasury_shares':treasury,'treasury_cost':treasury_cost,'parent_capital_premium':parent_premium,'interest_external_paid':interest_paid,'investment_commitment_paid':investment_paid,'capital_commitment_paid':commitment_paid,'hq_unpaid_claim_impairment':hq_claim_loss,'group_external_in':external_in,'parent_gross_internal_claim':sum(v['face'] for n,v in s.items() if n!='P'),'parent_net_internal_claim':sum(v['face']-v['loan_impairment'] for n,v in s.items() if n!='P'),'parent_hq_support_cumulative':hq_funded,'states':copy.deepcopy(s),'operating_fcff_parent':fcff,'discount_factor':df})
 # Residual assets/claims are disclosed and NOT silently discarded at horizon. Values are full summed cash-policy PV, no magic terminal release.
 residual=sum(v['cash']+v['wc']+v['fixed']+v['investments']-v['external_debt']-v.get('other_obligation',0.)- (v['wc_payables'] if not v['alive'] else 0.) for v in s.values());remaining_face=sum(v['face'] for n,v in s.items() if n!='P')
 value=pvdiv+pvcapital
 y5=(sum(x['holder_cash_per_share']/((1+p['r'])**(x['year']-5)) for x in rows[5:]))
 return {'value':value,'pv_ordinary':pvdiv,'pv_conditional_capital':pvcapital,'operating_fcff_pv_bn':pvop,'finance_income_pv_bn':pvfinancial,'nci_external_pv_bn':pv_nci,'year5_value':y5,'first5':[x['holder_cash_per_share'] for x in rows[:5]],'residual_asset_book_bn':residual,'discount_convention':'chained initial discount through year5 and continuation discount after year5' if switch_after5 else 'constant scenario discount from initial date','residual_discounted_asset_bn':residual/(((1+p0['r'])**min(years,5)*(1+p['r'])**max(years-5,0)) if switch_after5 else (1+p['r'])**years),'unpaid_internal_face_bn':remaining_face,'initial_participating_shares':shares0,'final_participating_shares':shares,'params':p0,'continuation_switch':switch_after5,'years':rows}

def generate():
 results={name:run(params(name),240) for name in SCENARIOS}
 convergence={str(h):{n:run(params(n),h)['value'] for n in ['base','core_low','core_high','hq_financed','no_capital_return','hq_funding_failure','structural']} for h in [120,360,480]}
 continuations={n:run(BASE,240,SCENARIOS[n]) for n in ['core_low','core_high']}
 y5={n:x['year5_value'] for n,x in continuations.items()}
 return {'continuations':continuations,'same_base_first5_continuations':y5,'schema':'montage_entity_policy_v6','information_cutoff':ASOF,'units':'CNY billion; shares billion; per-share CNY','actual':ACTUAL,'assumption_type':'entity cash/RE allocations and future payout are economic budgets; central policy distributes lawful surplus from year 7 and conditionally returns a bounded parent capital pool from year 10 only after approvals and creditor procedures; no-approval and unchanged-policy boundaries included','results':results,'convergence':convergence}
if __name__=='__main__':json.dump(generate(),sys.stdout,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False);sys.stdout.write('\n')
