#!/usr/bin/env python3
"""CNY billion; shares billion. Economic budgets, not legal opinions. stdlib only."""
import json,math,copy
ASOF='2026-10-29T00:00:00+00:00'
SHARES=.824157988
PARAMS={
 'base':{'rev':[17.8,20.,22.2,24.3,26.2],'margin':[.125,.133,.14,.146,.15],'capex':[2.4,2.3,2.2,2.1,2.1],'da':[.85,1.,1.15,1.3,1.4],'wc':[.7,.75,.8,.8,.8]},
 'cycle':{'rev':[15.3,16.5,19.2,22.,24.7],'margin':[.105,.115,.133,.144,.15],'capex':[2.25,2.15,2.1,2.05,2.1],'da':[.85,1.,1.15,1.3,1.4],'wc':[1.1,.9,.55,.65,.7]},
 'structural':{'rev':[16.4,17.2,18.,18.6,19.2],'margin':[.10,.095,.09,.085,.085],'capex':[2.2,2.,1.8,1.7,1.6],'da':[.85,1.,1.15,1.3,1.4],'wc':[.9,.8,.75,.6,.55],'long_margin':.085,'g':.01,'parent_profit_share':.75},
 'upside':{'rev':[18.5,21.5,24.8,28.,31.],'margin':[.135,.145,.155,.16,.165],'capex':[2.6,2.5,2.4,2.3,2.3],'da':[.85,1.,1.15,1.3,1.4],'wc':[.75,.85,.9,1.,1.],'long_margin':.155},
 'upstream_delay':{'inherit':'base','upstream_start':8,'parent_profit_share':.7},
 'working_capital_delay':{'inherit':'base','wc_extra':1.5},
 'asset_operating':{'inherit':'base','asset_is_operating':True},
 'asset_5y':{'inherit':'base','deposit_year':5},
 'asset_haircut':{'inherit':'base','asset_haircut':.5},
 'slow_cash_return':{'inherit':'base','cash_sweep':.03},
 'cost_100bp':{'inherit':'base','margin_cut':.01},
 'independent_normalized':{'aux':True},
}
OPEN={'cash':6.10961708001,'deposit':4.09795518432,'debt':3.09845651511,'operating_capital':14.95499544012,'parent_RE':9.05370385443,'parent_reserve':.412078994,'registered_capital':.824157988,'sub_loan':.72036370997,'sub_investment_cost':7.3988185798,'unknown_assets':3.66316371985,'NCI':-.01698236336}

# Historical grant-date quotes below are disclosed fair-value inputs, NOT current quotes.
from datetime import date
GRANTS=[
 ('2025_first','2025-08-25',4471300,135.85,94.92,[.392303,.360581,.344127],[.013608,.014194,.015022],228015400,94.48,[0,1311210,1748280]),
 ('2025_reserve','2025-10-14',528700,147.80,94.92,[.329213,.359978,.339089],[.014091,.014940,.015102],32204200,94.48,[105870,158610,211480]),
 ('2026_first','2026-06-22',4501200,104.19,86.,[.320349,.361587,.346223],[.011667,.012462,.012938],135671900,85.69,[1350360,1350360,1800480]),
 ('2026_reserve','2026-10-26',998800,116.49,85.69,[.302514,.326159,.335203],[.011797,.012452,.012624],39281100,85.69,[299640,299640,399520])]

def award_budget(p):
 """Remaining service costs, service/assessment/registration dates; budget, not audited allocation."""
 cutoff=date(2026,10,29);balance=date(2026,9,30);end=[date(2026+y,10,28) for y in range(1,6)]
 ledger=[];annual=[{'expense':0.,'vest':0.,'subscription':0.,'settled_capital':0.,'details':[]} for _ in end]
 opening_cost=0.;opening_bridge=0.
 for name,ds,original,stock,strike,vol,rate,total,pay,quantities in GRANTS:
  start=date.fromisoformat(ds);fv=[]
  for j in range(3):
   T=j+1;z=(math.log(stock/strike)+(rate[j]+vol[j]**2/2)*T)/(vol[j]*math.sqrt(T))
   cdf=lambda x:(1+math.erf(x/math.sqrt(2)))/2
   fv.append(stock*cdf(z)-strike*math.exp(-rate[j]*T)*cdf(z-vol[j]*math.sqrt(T)))
  scale=total/(original*sum(a*b for a,b in zip([.3,.3,.4],fv)))
  for j,q in enumerate(quantities):
   if q==0:continue
   service=date(start.year+j+1,start.month,start.day)
   assessment=date(start.year+j+1,4,30)
   if name=='2025_first':registration=date(service.year,9,15)
   elif name=='2026_first':registration=date(service.year,7,15)
   else:registration=date(service.year,11,15)
   performance_year=start.year+j
   baseline=10.30010438697 if start.year==2025 else 13.80025166395
   revenue=13.80025166395 if performance_year==2025 else (16.3 if performance_year==2026 else p.get('rev',[1.9403242333405575*1.06/.12,1.9403242333405575*1.06**2/.12])[performance_year-2027])
   target=baseline*[1.2,1.44,1.728][j];trigger=baseline*[1.16,1.3456,1.5609][j]
   factor=1. if revenue>=target else (round(revenue/target,4) if revenue>=trigger else 0.)
   if name=='2025_reserve' and j==0:factor=1.
   fair=q*fv[j]*scale/1e9
   def accrued(day):
    elapsed=max(0.,min(1.,(day-start).days/(service-start).days))
    return fair*elapsed*(factor if day>=assessment else 1.)
   # Only Oct1-Oct28 is incremental to Q3 actual book; no repeat of prior recognised cost.
   before=accrued(cutoff);opening_cost+=before;opening_bridge+=before-accrued(balance)
   for y,stop in enumerate(end):
    after=accrued(stop);expense=after-before;before=after
    lo=cutoff if y==0 else end[y-1]
    vested=math.floor(q*factor)/1e9 if lo<registration<=stop else 0.
    settled=fair*factor if vested else 0.
    annual[y]['expense']+=expense;annual[y]['vest']+=vested;annual[y]['subscription']+=vested*pay;annual[y]['settled_capital']+=settled
    annual[y]['details'].append({'batch':name,'window':j+1,'service_end':service.isoformat(),'assessment_budget':assessment.isoformat(),'registration_budget':registration.isoformat(),'performance_year':performance_year,'revenue_budget':revenue,'target':target,'trigger':trigger,'factor':factor,'remaining_rights':q,'full_cost_budget':fair,'cost_recognition':expense,'registered_shares':vested,'subscription_cash':vested*pay})
   ledger.append({'batch':name,'window':j+1,'rights':q,'factor':factor,'grant_fair_value_per_share_budget':fv[j]*scale,'opening_accrued_budget':accrued(cutoff),'performance_year':performance_year})
 return {'annual':annual,'opening_accrued':opening_cost,'opening_post_q3_cost':opening_bridge,'tranches':ledger}


def configuration(name):
 p=copy.deepcopy(PARAMS[name]);ref=p.pop('inherit',None)
 if ref: p={**copy.deepcopy(PARAMS[ref]),**p}
 return p

def run(p,N=400,seed=None,constant=None):
 s=copy.deepcopy(seed or {'pcash':4.,'scash':OPEN['cash']-4.,'pdep':OPEN['deposit']*.75,'sdep':OPEN['deposit']*.25,'pdebt':OPEN['debt'],'sdebt':0.,'pop':OPEN['operating_capital']*.6,'sop':OPEN['operating_capital']*.4,'pre':OPEN['parent_RE'],'sre':0.,'reserve':0.,'loan':OPEN['sub_loan'],'parent_investment_cost':OPEN['sub_investment_cost'],'nci_equity':OPEN['NCI'],'parent_equity':22.0810935527,'default_arrears':0.})
 if p.get('asset_is_operating'):
  amount=OPEN['unknown_assets'];s['pdep']-=amount*.75;s['sdep']-=amount*.25;s['pop']+=amount*.75;s['sop']+=amount*.25
 s['parent_statutory_reserve']=.412078994 if seed is None else 0.
 s['registered_capital']=.824157988 if seed is None else 0.
 aw=award_budget(p) if constant is None else {'annual':[],'opening_accrued':0.,'opening_post_q3_cost':0.,'tranches':[]}
 s.update({'treasury_shares':.005543468 if constant is None else 0.,'treasury_cost':.73314842463*(5543468/6758348) if constant is None else 0.,'share_premium_movement':0.,'sbc_capital_parent':aw['opening_accrued']*.75,'sbc_capital_sub':aw['opening_accrued']*.25,'cumulative_future_sbc':0.,'remaining_award_rights':sum(a['rights'] for a in aw['tranches'])/1e9})
 s['pre']-=aw['opening_post_q3_cost']*.75;s['sre']-=aw['opening_post_q3_cost']*.25
 rows=[];rev=16.3;lastprofit=1.9403242333405575
 for t in range(1,N+1):
  prior=copy.deepcopy(s)
  award=aw['annual'][t-1] if t<=5 and constant is None else {'expense':0.,'vest':0.,'subscription':0.,'settled_capital':0.,'details':[]}
  vest=award['vest'];subscription=award['subscription'];sbc=award['expense']
  s['sbc_capital_parent']+=sbc*.75-award['settled_capital']*.75
  s['sbc_capital_sub']+=sbc*.25-award['settled_capital']*.25
  s['cumulative_future_sbc']+=sbc
  treasury_used=min(vest,s['treasury_shares'])
  treasury_cost_used=s['treasury_cost']*treasury_used/s['treasury_shares'] if s['treasury_shares'] else 0.
  s['treasury_shares']-=treasury_used;s['treasury_cost']-=treasury_cost_used
  new_registered=vest-treasury_used;s['registered_capital']+=new_registered
  s['share_premium_movement']+=subscription+award['settled_capital']-treasury_cost_used-new_registered
  if t<=5 and constant is None:
   closed=sum(x['remaining_rights']/1e9 for x in award['details'] if int(x['registration_budget'][:4])==2026+t or (t==1 and x['registration_budget']<'2027-10-29'))
   # Remaining contractual rights close at their budget registration date, even if performance fails.
   s['remaining_award_rights']=sum(x['remaining_rights']/1e9 for x in award['details'] if x['registration_budget']>str(2026+t)+'-10-28')
  shares=s['registered_capital']-s['treasury_shares'] if constant is None else SHARES
  s['pcash']+=subscription;s['parent_equity']+=subscription
  g=p.get('g',.02);loss=0.;dep_return=0.
  if constant is not None: rev=constant['revenue'];opprofit=constant['profit'];da=constant.get('da',0.);capex=constant.get('capex',0.);wc=constant.get('wc',0.)
  elif p.get('aux'):
   # Independent economic entry: normalized historical earnings; no main revenue/margin arrays.
   growth=.06 if t<=10 else max(g,.06-(t-10)*.004)
   opprofit=lastprofit*(1+growth);netinvestment=(opprofit-lastprofit)/.12
   rev=opprofit/.12;da=rev*.055;capex=da+netinvestment*.65;wc=netinvestment*.35;lastprofit=opprofit
  elif t<=5:
   rev=p['rev'][t-1];opprofit=rev*(p['margin'][t-1]-p.get('margin_cut',0.))*.85
   da=p['da'][t-1];capex=p['capex'][t-1];wc=p['wc'][t-1]
  else:
   growth=max(g,.08-(t-6)*.006);oldrev=rev;rev*=1+growth
   margin=p['margin'][-1]+(p.get('long_margin',.14)-p['margin'][-1])*min(1,(t-5)/10)
   opprofit=rev*(margin-p.get('margin_cut',0.))*.85
   da=.055*rev;capex=da+.45*(rev-oldrev);wc=.35*(rev-oldrev)
  if p.get('wc_extra'):
   if t==1:wc+=p['wc_extra']
   if t in (3,4,5):wc-=p['wc_extra']/3
  if t==1 and p.get('asset_haircut'):
   loss=OPEN['unknown_assets']*p['asset_haircut'];s['pdep']-=loss*.75;s['sdep']-=loss*.25
  if t==p.get('deposit_year',3):
   dep_return=s['pdep']+s['sdep'];s['pcash']+=s['pdep'];s['scash']+=s['sdep'];s['pdep']=s['sdep']=0.
  # Financial return on opening balances. Taxes included in 1.5% after-tax financial yield.
  pf=(max(prior['pcash'],0)+max(prior['pdep']-loss*.75,0))*.015
  sf=(max(prior['scash'],0)+max(prior['sdep']-loss*.25,0))*.015
  interest=prior['pdebt']*.035;sintr=prior['sdebt']*.045
  share=p.get('parent_profit_share',1.05-.03*min(t,10))
  parent_operating_profit=opprofit*share
  if constant is None and t<=5 and not p.get('aux') and 'parent_profit_share' not in p:
   parent_sales=[19.,21.3,23.5,25.5,27.3][t-1]
   parent_margin=[.108,.109,.11,.11,.11][t-1]
   # A separate parent sales/profit budget anchored to its H1 actual operating business.
   if p.get('rev',[17.8])[0]==15.3: parent_sales*=[.86,.90,.95,.98,1.][t-1];parent_margin-=[.02,.015,.007,0,0][t-1]
   if p.get('rev',[17.8])[0]==18.5: parent_sales*=1.04;parent_margin+=.006
   parent_operating_profit=parent_sales*(parent_margin-p.get('margin_cut',0.)*.85)
  pn=parent_operating_profit+pf-interest-loss*.75
  sn=opprofit-parent_operating_profit+sf-sintr-loss*.25
  # NCI economic cost budget (not treating negative historical NCI as a common-share windfall).
  nci=0. if constant is not None else max(0.,opprofit)*.008
  sn-=nci;s['nci_equity']+=nci-nci
  ni=capex-da+wc;s['pop']+=ni*.6;s['sop']+=ni*.4
  s['pcash']+=pn+loss*.75-ni*.6;s['scash']+=sn+loss*.25-ni*.4
  s['pre']+=pn-sbc*.75;s['sre']+=sn-sbc*.25
  if constant is None:
   parent_reserve_add=min(max(0.,min(pn-sbc*.75,s['pre']))*.1,max(0,s['registered_capital']*.5-s['parent_statutory_reserve']))
   s['parent_statutory_reserve']+=parent_reserve_add;s['pre']-=parent_reserve_add
  reserve=min(max(0.,min(sn-sbc*.25,s['sre']))*.06,max(0.,1.36-s['reserve']))
  s['reserve']+=reserve;s['sre']-=reserve
  # Debt collection and financing are real cash transfers, never consolidated profit.
  minp=0. if constant is not None else rev*.05;mins=0. if constant is not None else rev*.025
  repay=min(s['loan'],max(0,s['scash']-mins));s['loan']-=repay;s['scash']-=repay;s['pcash']+=repay
  credit_capacity=p.get('credit_capacity',max(OPEN['debt'],rev*.20))
  available_credit=max(0.,credit_capacity-s['pdebt'])
  support=min(max(0.,mins-s['scash']),max(0.,s['pcash'])+available_credit)
  s['loan']+=support;s['scash']+=support;s['pcash']-=support
  # Denied finance leaves an actual unpaid operating creditor, not fictitious cash or forgiven debt.
  arrears_created=max(0.,-s['scash']);s['scash']+=arrears_created;s['default_arrears']+=arrears_created

  up=0.
  if t>=p.get('upstream_start',1):up=min(max(0.,s['sre']),max(0.,s['scash']-mins))
  tax=up*(0. if constant is not None else .02);s['sre']-=up;s['scash']-=up;s['pre']+=up-tax;s['pcash']+=up-tax
  borrow=min(max(0.,minp-s['pcash']),max(0.,credit_capacity-s['pdebt']));s['pdebt']+=borrow;s['pcash']+=borrow
  parent_unpaid=max(0.,-s['pcash']);s['pcash']+=parent_unpaid;s['default_arrears']+=parent_unpaid;arrears_created+=parent_unpaid
  arrears_paid=min(s['default_arrears'],max(0.,s['pcash']-minp));s['pcash']-=arrears_paid;s['default_arrears']-=arrears_paid

  # No principal forgiveness. Excess pays bank before common distributions.
  debtpay=min(s['pdebt'],max(0.,s['pcash']-minp));s['pdebt']-=debtpay;s['pcash']-=debtpay
  target=(.20 if t<=5 else min(1.,.2+(t-5)*.08))*max(0.,pn-sbc*.75+up-tax)
  target+=p.get('cash_sweep',.10)*max(0.,s['pcash']-minp-target)
  planned_buyback=.01669088805 if t==1 and constant is None else 0.
  div=min(target,max(0.,s['pre']),max(0.,s['pcash']-minp-planned_buyback)) if s['default_arrears']<1e-12 else 0.
  s['pcash']-=div;s['pre']-=div
  # Already-paid treasury cost is never charged again as economic cash expense.
  buyback=planned_buyback
  buyback_credit=min(max(0.,minp+buyback-s['pcash']),max(0.,credit_capacity-s['pdebt']))
  s['pcash']+=buyback_credit;s['pdebt']+=buyback_credit;borrow+=buyback_credit
  buyback=min(buyback,max(0.,s['pcash']));s['pcash']-=buyback
  if constant is None:
   s['treasury_shares']+=buyback/108;s['treasury_cost']+=buyback
   shares=s['registered_capital']-s['treasury_shares']
  s['parent_equity']+=pn+sn-tax-div-buyback
  cashbefore=prior['pcash']+prior['scash'];cashafter=s['pcash']+s['scash']
  expected=cashbefore+subscription+pn+sn+loss-ni+dep_return-tax+borrow-debtpay-div-buyback+arrears_created-arrears_paid
  assert abs(cashafter-expected)<1e-8*max(1,abs(cashafter))
  assert min(s['pcash'],s['scash'],s['loan'],s['pdebt'],s['reserve'])>=-1e-8
  assert abs((s['pop']+s['sop'])-(prior['pop']+prior['sop']+ni))<1e-8*max(1,s['pop']+s['sop'])
  # Explicit economic equity movement includes financing principal and financial asset impairment once.
  economic_equity=s['pop']+s['sop']+s['pcash']+s['scash']+s['pdep']+s['sdep']-s['pdebt']-s['sdebt']-s['default_arrears']
  assert abs(economic_equity-s['parent_equity']-s['nci_equity'])<1e-7*max(1,abs(economic_equity))
  capital_fields=['pre','sre','reserve','parent_statutory_reserve','sbc_capital_parent','sbc_capital_sub','share_premium_movement','registered_capital']
  capital_change=sum(s[k]-prior[k] for k in capital_fields)-(s['treasury_cost']-prior['treasury_cost'])
  assert abs(capital_change-(pn+sn-tax-div+subscription-buyback))<1e-7*max(1,abs(capital_change))
  if prior['sre']+sn-sbc*.25<=0:assert reserve==0
  row={'year':t,'revenue':rev,'SBC_expense':sbc,'parent_SBC_expense':sbc*.75,'sub_SBC_expense':sbc*.25,'award_detail':award['details'],'treasury_shares_delivered':treasury_used,'treasury_cost_delivered':treasury_cost_used,'capital_component_change':capital_change,'new_registered_shares':new_registered,'capital_settlement':award['settled_capital'],'credit_capacity_budget':credit_capacity,'new_unpaid_creditor_claim':arrears_created,'unpaid_creditor_repayment':arrears_paid,'after_tax_operating_profit':opprofit,'depreciation':da,'capex':capex,'working_capital_increase':wc,'net_investment':ni,'parent_after_tax_operating_profit':parent_operating_profit,'parent_profit':pn-sbc*.75,'sub_profit_after_NCI':sn-sbc*.25,'parent_cash_profit_before_SBC':pn,'sub_cash_profit_before_SBC':sn,'NCI_profit':nci,'NCI_cash_distribution':nci,'NCI_equity':s['nci_equity'],'parent_financial_income':pf,'sub_financial_income':sf,'external_interest':interest+sintr,'asset_impairment':loss,'deposit_redemption':dep_return,'sub_reserve_transfer':reserve,'loan_repayment':repay,'new_parent_loan_to_sub':support,'sub_dividend_declared_and_received':up,'upstream_tax':tax,'new_external_borrowing':borrow,'external_principal_repayment':debtpay,'common_distribution':div,'future_dividend_shares':shares,'vested_awards':vest,'subscription_cash':subscription,'distribution_per_share':div/shares,'buyback_cash':buyback,'state':copy.deepcopy(s)}
  rows.append(row)
 return rows

def summarize(rows,r):
 pv=sum(x['distribution_per_share']/(1+r)**x['year'] for x in rows)
 first=sum(x['distribution_per_share']/(1+r)**x['year'] for x in rows[:5]);y5=(pv-first)*(1+r)**5
 return {'discount_rate':r,'present_value_per_share':pv,'year5_value_per_share':y5,'year5_onward_PV_share':(pv-first)/pv if pv else 0.,'five_distributions':[x['distribution_per_share'] for x in rows[:5]]}

def hand_tests():
 seed={'pcash':10.,'scash':0.,'pdep':0.,'sdep':0.,'pdebt':0.,'sdebt':0.,'pop':0.,'sop':0.,'pre':10.,'sre':0.,'reserve':0.,'loan':0.,'parent_investment_cost':0.,'nci_equity':0.,'parent_equity':10.,'default_arrears':0.}
 out=run({'parent_profit_share':1.},1,seed,{'revenue':0.,'profit':1.})[0]
 # Opening 10 earns .15 + operating 1; 20% profit dividend .23 plus 10% surplus 1.092; closing9.828.
 assert abs(out['common_distribution']-1.322)<1e-12 and abs(out['state']['pcash']-9.828)<1e-12
 seed['pre']=0.;out2=run({'parent_profit_share':1.},1,seed,{'revenue':0.,'profit':-2.})[0]
 assert out2['common_distribution']==0 and out2['state']['pre']<0
 # Sub losses receive an actual loan; no disappearance of creditor claim.
 seed['pcash']=0.;seed['pre']=0.;seed['parent_equity']=0.;out3=run({'parent_profit_share':0.,'credit_capacity':1.},1,seed,{'revenue':0.,'profit':-2.})[0]
 assert abs(out3['state']['loan']-1.)<1e-12 and abs(out3['state']['pdebt']-1.)<1e-12 and abs(out3['state']['default_arrears']-1.)<1e-12 and out3['common_distribution']==0
 refusal_extension=run({'parent_profit_share':0.,'credit_capacity':1.},3,seed,{'revenue':0.,'profit':-2.})
 assert all(r['state']['pdebt']<=1. and r['common_distribution']==0 for r in refusal_extension)
 assert refusal_extension[-1]['state']['default_arrears']>=5.
 reserve_seed=copy.deepcopy(seed);reserve_seed.update(pcash=0.,scash=10.,sre=-2.,parent_equity=10.)
 reserve_case=run({'parent_profit_share':0.},1,reserve_seed,{'revenue':0.,'profit':1.})[0]
 assert reserve_case['sub_reserve_transfer']==0 and reserve_case['state']['sre']<0
 return {'cash_and_profit_case':out,'loss_no_distribution_case':out2,'credit_refusal_creditor_survival_case':out3,'credit_refusal_extension':refusal_extension,'prior_loss_before_reserve_case':reserve_case}

def main():
 paths={};convergence={}
 for name in PARAMS:
  p=configuration(name);rows=run(p,1600);paths[name]={'award_budget':award_budget(p),'parameters':p,'years':rows,'values':[summarize(rows,r) for r in (.095,.10,.105)]}
  convergence[name]=[{'years':n,'value':summarize(run(p,n),.10),'end_state':run(p,n)[-1]['state']} for n in (100,200,400,800,1600)]
  for c in convergence[name]:
   terminal=rows[c['years']-1];sales=terminal['revenue']
   c['normalized_state']={k:v/sales for k,v in terminal['state'].items()}
   c['normalized_state']['registered_share_count']=terminal['state']['registered_capital']
   c['normalized_state']['treasury_share_count']=terminal['state']['treasury_shares']
   c['normalized_state']['common_dividend_to_sales']=terminal['common_distribution']/sales
   c['normalized_state']['operating_profit_to_sales']=terminal['after_tax_operating_profit']/sales
  differences={k:abs(convergence[name][-1]['normalized_state'][k]-convergence[name][-2]['normalized_state'][k]) for k in convergence[name][-1]['normalized_state']}
  convergence[name][-1]['normalized_full_state_differences_800_1600']=differences
  assert max(differences.values())<.0001
  assert abs(convergence[name][-1]['value']['present_value_per_share']-convergence[name][-2]['value']['present_value_per_share'])<1e-7
 print(json.dumps({'as_of':ASOF,'units':'CNY billion, shares billion','shares':SHARES,'opening':OPEN,'paths':paths,'convergence':convergence,'production_hand_tests':hand_tests()},ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False))
if __name__=='__main__':main()
