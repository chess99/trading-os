#!/usr/bin/env python3
"""SANY 2026Q3, CNY billions unless per-share. Standalone conditional owner cash model."""
import json,sys,math
ASOF='2026-10-29T23:13:00+00:00'
REGISTERED=9.195004437
ELIGIBLE=REGISTERED-.038619413
FINANCE_NET_REFERENCE=(.303516-.088133)/78.109737
FINANCE_CUSTOMER_ASSETS=11.388048+12.610509+.381893+.098330
FINANCE_ASSET_TO_TTM=FINANCE_CUSTOMER_ASSETS/101.599746
FINANCE_GROSS_YIELD=(.303516*4/3)/FINANCE_CUSTOMER_ASSETS
A={
 'revenue_ttm':101.599746,'group_cash_equivalent':6.276610,'mother_cash_equivalent':2.022074,
 'group_interbank_asset':.085501,'group_money':27.127140,'mother_money':17.148465,'group_trading':24.708955,'mother_trading':4.813952,
 'short_debt_assets_budget':9.7,'mother_short_debt_assets_budget':9.0,
 'private_financial':1.053283,'mother_private_financial':.953063,
 'associate':2.694248,'mother_associate':.961836,
 'group_equity':95.365547,'mother_equity':33.253593,'nci':1.116505,
 'group_re':64.805501,'mother_re':.731274,'mother_reserve':4.277186,
 'mother_sub_cost':27.602836,'mother_other_payable':27.222078,'group_other_payable':8.473649,
 'working_capital':26.388667,'physical_capital':26.602902,
 'group_debt':23.372973,'mother_debt':2.036520,'unpaid_capex':.823474,
 'restricted_money_budget':.713882,'restricted_bonds_budget':1.733086,
 'old_parent_div_receivable':.001,'outside_guarantee_h1':10.555,
}
BASE={'customer_finance_yield_multiplier':1.,'external_debt_rate':.035,'portfolio_years':5,'rate':.09,'growth_domestic':.05,'growth_overseas':.11,'margin':.148,'wc':.26,'fixed':.25,
 'sub_release':.06,'mother_release':.06,'sub_payout':.65,'common_payout':.40,'internal_face':25.0,
 'internal_years':5,'internal_rate':0.,'capacity_fraction':.70,'deposit_years':3,'portfolio_haircut':0.,
 'cash_yield':.018,'deposit_yield':.023,'portfolio_yield':.026,'private_yield':.04,'sub_tax':.20,
 'mother_tax':.25,'div_tax':.006,'associate_roe':.065,'associate_payout':.30,'associate_exit':0,
 'minority_profit_share':.01,'refinance':.65,'extra_guarantee':0.,'wc_shock':0.,'delay_sub':0,
 'cycle':False,'structural':False,'upside':False,'method':'regional','cash_shock':0.,'foreign_translation_loss':0.,
 'extra_incentive_cash':0.,'remove_principal':False,'net_settlement':False}
def reserve(re,stat,np,cap):
 before=re;re+=np;alloc=min(max(cap-stat,0.),max(np-max(-before,0.),0.)*.10);return re-alloc,stat+alloc,alloc

def initial(p):
 m=A['mother_cash_equivalent'];s=A['group_cash_equivalent']-m
 ml=A['mother_money']-m;sl=A['group_money']+A['group_interbank_asset']-A['mother_money']-s
 mp=A['mother_trading']+A['mother_short_debt_assets_budget'];sp=A['group_trading']-A['mother_trading']+A['short_debt_assets_budget']-A['mother_short_debt_assets_budget']
 if p['remove_principal']:mp=sp=0.
 return {'m_cash':m,'s_cash':s,'m_deposit':ml,'s_deposit':sl,'m_portfolio':mp,'s_portfolio':sp,
  'm_private':A['mother_private_financial'],'s_private':A['private_financial']-A['mother_private_financial'],
  'm_associate':A['mother_associate'],'s_associate':A['associate']-A['mother_associate'],
  'm_associate_cost':A['mother_associate'],'s_associate_cost':A['associate']-A['mother_associate'],
  'm_associate_unremitted':0.,'s_associate_unremitted':0.,
  'm_re':A['mother_re'],'s_re':A['group_re']-A['mother_re'],'m_stat':A['mother_reserve'],'s_stat':4.,
  'm_equity':A['mother_equity'],'s_equity':A['group_equity']-A['mother_equity']+A['mother_sub_cost'],
  'nci':A['nci'],'sub_cost':A['mother_sub_cost'],'internal_face':p['internal_face'],'internal_allowance':0.,
  'm_debt':A['mother_debt'],'s_debt':A['group_debt']-A['mother_debt'],
  'wc':A['working_capital'],'fixed':A['physical_capital'],'unpaid_capex':A['unpaid_capex'],
  'm_taxloss':0.,'s_taxloss':0.,'shares':ELIGIBLE,'domestic':39.,'overseas':67.,'revenue':106.,
  'restricted':A['restricted_money_budget']+A['restricted_bonds_budget'],'year':0}
def tax(profit,loss,rate):
 taxable=max(profit-loss,0.);newloss=max(loss-profit,0.);return taxable*rate,newloss

def business(st,t,p):
 gd=p['growth_domestic'] if t<=5 else (.03 if t<=10 else .02)
 go=p['growth_overseas'] if t<=5 else (.05 if t<=10 else (.03 if t<=20 else .02))
 if t<=5:gd-=.005*(t-1);go-=.01*(t-1)
 if p['cycle']:
  if t==1:gd=-.22;go=-.15
  elif t==2:gd=-.05;go=0.
  elif t in (3,4):gd=.10;go=.12
 if p['structural']:gd=.00;go=.01
 if p['upside'] and t<=8:gd+=.02;go+=.025
 d=st['domestic']*(1+gd);o=st['overseas']*(1+go);r=d+o
 if p['method']=='product':
  # Independent product mix endpoint: excavator42%, concrete17%, crane16%, other25%.
  # Own price/volume trajectories are not a regional revenue scaling.
  old=st.get('products',[42.6,18.0,16.8,28.6]);rates=[.085,.065,.055,.070] if t<=5 else ([.035,.025,.03,.03] if t<=15 else [.02]*4)
  if p['structural']:rates=[.01,0.,0.,.01]
  new=[a*(1+g) for a,g in zip(old,rates)];r=sum(new);d=r*.37;o=r*.63
 else:new=[]
 margin=p['margin']-(.0004*max(0,min(t-5,15)))
 if p['method']=='product':margin=sum(w*m for w,m in zip([.42,.17,.16,.25],[.197,.119,.155,.101])) # EBITDA by product after operating cost and credit loss
 if p['cycle'] and t<=3:margin-= [.035,.025,.01][t-1]
 if p['structural']:margin=.105
 if p['upside']:margin+=.008
 return d,o,r,margin,new

def liquidate(st,who,need,p):
 # Sell only an existing financial portfolio, not operations or undisclosed subsidiary capital.
 gross=min(st[who+'_portfolio'],max(need-st[who+'_cash'],0.)/(1-p['portfolio_haircut']))
 loss=gross*p['portfolio_haircut'];st[who+'_portfolio']-=gross;st[who+'_cash']+=gross-loss
 # No assumed immediate tax relief on investment capital loss.
 st[who+'_re']-=loss;st[who+'_equity']-=loss
 return gross,loss

def project(parameters=None,years=240):
 p=dict(BASE);p.update(parameters or {});st=initial(p);rows=[];feasible=True
 initial_portfolio=(st['m_portfolio'],st['s_portfolio']);initial_deposit=(st['m_deposit'],st['s_deposit']);initialface=st['internal_face']
 for t in range(1,years+1):
  before=dict(st);d,o,r,margin,products=business(st,t,p);st.update(year=t,domestic=d,overseas=o,revenue=r)
  if products:st['products']=products
  dep=before['fixed']*.13;targetfixed=r*(p['fixed']-.001*min(t,10));fixed=max(before['fixed']-dep,targetfixed);capex=fixed-before['fixed']+dep
  wc=r*(p['wc']+(.06 if p['structural'] else 0.))
  if p['cycle'] and t<=2:wc+=r*.045
  if t<=3:wc+=p['wc_shock']*(4-t)/3
  delta_wc=wc-before['wc'];delta_fixed=fixed-before['fixed'];st['wc']=wc;st['fixed']=fixed
  industrial_margin=margin-FINANCE_NET_REFERENCE
  customer_finance_assets=r*FINANCE_ASSET_TO_TTM
  customer_finance_gross_interest=customer_finance_assets*FINANCE_GROSS_YIELD*p['customer_finance_yield_multiplier']
  industrial_ebitda=r*industrial_margin
  ebitda=industrial_ebitda+customer_finance_gross_interest;ebit=ebitda-dep;mother_ebit=-.55*r/114.;sub_ebit=ebit-mother_ebit
  # Cash-equivalent compensation including ongoing incentive cost is already in EBITDA;
  # existing transferred treasury proceeds and paid buybacks are not counted again.
  parent_extra=p['extra_incentive_cash'] if t==1 else 0.
  parent_ir=before['m_debt']*p['external_debt_rate'];sub_ir=before['s_debt']*p['external_debt_rate'];inter_ir=before['internal_face']*p['internal_rate']
  mf=before['m_cash']*p['cash_yield']+before['m_deposit']*p['deposit_yield']+before['m_portfolio']*p['portfolio_yield']+before['m_private']*p['private_yield']
  sf=before['s_cash']*p['cash_yield']+before['s_deposit']*p['deposit_yield']+before['s_portfolio']*p['portfolio_yield']+before['s_private']*p['private_yield']
  ma=before['m_associate']*p['associate_roe'];sa=before['s_associate']*p['associate_roe'];mad=ma*p['associate_payout'];sad=sa*p['associate_payout']
  st['m_associate']+=ma-mad;st['s_associate']+=sa-sad;st['m_associate_unremitted']+=ma-mad;st['s_associate_unremitted']+=sa-sad
  guarantee=p['extra_guarantee'] if t==1 else 0.;fx=p['foreign_translation_loss'] if t==1 else 0.
  mt,st['m_taxloss']=tax(mother_ebit+mf-parent_ir-inter_ir-parent_extra,st['m_taxloss'],p['mother_tax'])
  sth,st['s_taxloss']=tax(sub_ebit+sf-sub_ir+inter_ir-guarantee-fx,st['s_taxloss'],p['sub_tax'])
  mnp=mother_ebit+mf-parent_ir-inter_ir+ma-mt-parent_extra
  snp=sub_ebit+sf-sub_ir+inter_ir+sa-sth-guarantee-fx
  # Mother direct operating capital remains 5% of group delta; remaining manufacture/finance clients in subsidiaries.
  mcf=mother_ebit+mf-parent_ir-inter_ir-mt-parent_extra+mad-.05*(delta_wc+delta_fixed)
  scf=sub_ebit+sf-sub_ir+inter_ir-sth-guarantee-fx+sad-.95*(delta_wc+delta_fixed)
  st['m_cash']+=mcf;st['s_cash']+=scf
  st['m_re'],st['m_stat'],mrs=reserve(st['m_re'],st['m_stat'],mnp,REGISTERED*.5)
  st['s_re'],st['s_stat'],srs=reserve(st['s_re'],st['s_stat'],snp,6.)
  st['m_equity']+=mnp;st['s_equity']+=snp
  ncprofit=snp*p['minority_profit_share'];st['nci']+=ncprofit
  relm=min(st['m_deposit'],initial_deposit[0]/p['deposit_years']) if t<=p['deposit_years'] else 0.
  rels=min(st['s_deposit'],initial_deposit[1]/p['deposit_years']) if t<=p['deposit_years'] else 0.
  st['m_deposit']-=relm;st['s_deposit']-=rels;st['m_cash']+=relm;st['s_cash']+=rels
  # Repayment of principal is neither profit nor a second company cost.
  repayface=min(st['internal_face'],initialface/p['internal_years']) if t<=p['internal_years'] else 0.
  if t<=3: mdue=before['m_debt']/(4-t);sdue=before['s_debt']/(4-t)
  else:mdue=before['m_debt']*.15;sdue=before['s_debt']*.15
  mnew=mdue*p['refinance'];snew=sdue*p['refinance'];mprincipal=mdue-mnew;sprincipal=sdue-snew
  st['m_debt']-=mprincipal;st['s_debt']-=sprincipal
  engineering=min(st['unpaid_capex'],A['unpaid_capex']/2);st['unpaid_capex']-=engineering
  st['m_cash']-=mprincipal;st['s_cash']-=sprincipal+engineering
  if t==1:st['m_cash']-=p['cash_shock'];st['m_re']-=p['cash_shock'];st['m_equity']-=p['cash_shock']
  mmin=r*.008;smin=r*.035;restricted=A['restricted_money_budget']*r/106.+A['restricted_bonds_budget']*st['s_debt']/(A['group_debt']-A['mother_debt']);st['restricted']=restricted
  # Existing guarantees/collateral remain part of subsidiary pool; yield on them is retained.
  net_gross=net_common=net_nci=net_tax=net_reserve=0.
  if p['net_settlement'] and repayface>0:
   # Conditional same-counterparty declaration and legal setoff, not assumed core permission.
   net_gross=min(repayface/(1-p['minority_profit_share']),max(st['s_re']-st['s_associate_unremitted'],0.)*p['capacity_fraction'])
   net_common=net_gross*(1-p['minority_profit_share']);net_nci=net_gross-net_common;net_tax=net_common*p['div_tax']
   st['internal_face']-=net_common;repayface-=net_common
   st['s_re']-=net_gross;st['s_equity']-=net_gross;st['s_cash']-=net_nci;st['nci']-=net_nci
   st['m_cash']-=net_tax
   st['m_re'],st['m_stat'],net_reserve=reserve(st['m_re'],st['m_stat'],net_common-net_tax,REGISTERED*.5)
   st['m_equity']+=net_common-net_tax
  # Contract dates not fully public: orderly five-year redemption is an economic budget, tested at ten.
  mplanned,mlplanned=liquidate(st,'m',st['m_cash']+(initial_portfolio[0]/p['portfolio_years'] if t<=p['portfolio_years'] else 0.)*(1-p['portfolio_haircut']),p)
  mgross,mloss=liquidate(st,'m',repayface+mmin,p);mgross+=mplanned;mloss+=mlplanned
  if st['m_cash']+1e-9<repayface:feasible=False
  actualrepay=min(max(st['m_cash']-mmin,0.),repayface)
  # Schedule failure is explicit, not quietly forgiven or moved beyond tail.
  if actualrepay+1e-8<repayface:feasible=False
  st['m_cash']-=actualrepay;st['s_cash']+=actualrepay;st['internal_face']-=actualrepay
  splanned,slplanned=liquidate(st,'s',st['s_cash']+(initial_portfolio[1]/p['portfolio_years'] if t<=p['portfolio_years'] else 0.)*(1-p['portfolio_haircut']),p)
  sgross,sloss=liquidate(st,'s',smin+restricted,p);sgross+=splanned;sloss+=slplanned
  if st['s_cash']+1e-8<smin+restricted or st['m_cash']+1e-8<mmin:feasible=False
  sfinancial=max(st['s_cash']+st['s_portfolio']-smin-restricted-st['s_debt']-st['unpaid_capex'],0.)
  divtarget=max(snp,0.)*p['sub_payout']+sfinancial*p['sub_release']
  if t<=p['delay_sub']:divtarget=0.
  legal=max(st['s_re']-st['s_associate_unremitted'],0.)*p['capacity_fraction']
  divtarget=min(divtarget,legal)
  sg2,sl2=liquidate(st,'s',divtarget+smin+restricted,p);sloss+=sl2;sgross+=sg2
  legal=max(st['s_re']-st['s_associate_unremitted'],0.)*p['capacity_fraction']
  sd=min(divtarget,legal,max(st['s_cash']-smin-restricted,0.));ncd=sd*p['minority_profit_share'];parent_declared=sd-ncd;withhold=parent_declared*p['div_tax'];parent_received=parent_declared-withhold
  st['s_cash']-=sd;st['s_re']-=sd;st['s_equity']-=sd;st['nci']-=ncd
  st['m_cash']+=parent_received
  st['m_re'],st['m_stat'],divreserve=reserve(st['m_re'],st['m_stat'],parent_received,REGISTERED*.5)
  st['m_equity']+=parent_received
  # Associate exit is a separately conditioned actual sale, net fee/tax/cost, never a terminal plug.
  exit_cash=exit_gain=exit_tax=0.
  if p['associate_exit'] and t==p['associate_exit']:
   for who in ('m','s'):
    book=st[who+'_associate'];cost=st[who+'_associate_cost'];proceeds=book*.90;fees=proceeds*.02;et=max(proceeds-fees-cost,0.)*.25;gain=proceeds-fees-book-et
    st[who+'_cash']+=proceeds-fees-et;st[who+'_associate']=0.;st[who+'_associate_cost']=0.;st[who+'_associate_unremitted']=0.;st[who+'_re']+=gain;st[who+'_equity']+=gain
    exit_cash+=proceeds-fees-et;exit_gain+=gain;exit_tax+=et
    if who=='s':st['nci']+=gain*p['minority_profit_share'];ncprofit+=gain*p['minority_profit_share']
  mfree=max(st['m_cash']+st['m_portfolio']-mmin-st['m_debt']-st['internal_face'],0.)
  # Distribution rises with ordinary operating earnings, not total financial marks.
  nc_sale_loss=sloss*p['minority_profit_share'];st['nci']-=nc_sale_loss;ncprofit-=nc_sale_loss
  commonprofit=mnp+snp+exit_gain-ncprofit-withhold-net_tax-mloss-sloss
  payout=p['common_payout']*max(commonprofit,0.)+p['mother_release']*mfree
  mg2,ml2=liquidate(st,'m',payout+mmin,p);mgross+=mg2;mloss+=ml2;commonprofit-=ml2
  pay=min(payout,max(st['m_re']-st['m_associate_unremitted'],0.),max(st['m_cash']-mmin,0.))
  st['m_cash']-=pay;st['m_re']-=pay;st['m_equity']-=pay
  # Existing incentive treasury is assumed transferred over three years; no new registered shares or external cash.
  st['shares']=ELIGIBLE+(REGISTERED-ELIGIBLE)*min(t/3,1.)
  per=pay/st['shares']
  row={**{k:v for k,v in st.items() if k!='products'},'products':st.get('products',[]),'industrial_ebitda':industrial_ebitda,'industrial_ebitda_margin':industrial_margin,'customer_finance_assets':customer_finance_assets,'customer_finance_gross_interest':customer_finance_gross_interest,'ebitda':ebitda,'depreciation':dep,'ebit':ebit,'mother_ebit':mother_ebit,'sub_ebit':sub_ebit,'capex':capex,'delta_wc':delta_wc,'delta_fixed':delta_fixed,
   'm_financial_income':mf,'s_financial_income':sf,'m_associate_earnings':ma,'s_associate_earnings':sa,'m_associate_dividend':mad,'s_associate_dividend':sad,'m_tax':mt,'s_tax':sth,'m_interest':parent_ir,'s_interest':sub_ir,'inter_interest':inter_ir,
   'm_profit':mnp,'s_profit':snp,'nci_profit':ncprofit,'m_ordinary_cash_flow':mcf,'s_ordinary_cash_flow':scf,'m_reserve_add':mrs+divreserve+net_reserve,'s_reserve_add':srs,
   'm_deposit_release':relm,'s_deposit_release':rels,'internal_repaid':actualrepay,'internal_dividend_setoff':net_common,'setoff_gross_dividend':net_gross,'setoff_nci_cash':net_nci,'setoff_withholding':net_tax,'m_debt_due':mdue,'s_debt_due':sdue,'m_new_debt':mnew,'s_new_debt':snew,'engineering_payment':engineering,
   's_dividend':sd,'mother_declared_dividend':parent_declared,'mother_received_dividend':parent_received,'dividend_withholding':withhold,'nci_distribution':ncd,
   'm_portfolio_sold':mgross,'s_portfolio_sold':sgross,'m_sale_loss':mloss,'s_sale_loss':sloss,'m_minimum_cash':mmin,'s_minimum_cash':smin,
   'group_common_profit':commonprofit,'common_distribution':pay,'distribution_per_share':per,'associate_exit_cash':exit_cash,'associate_exit_gain':exit_gain,'associate_exit_tax':exit_tax,
   'group_equity_after':st['m_equity']+st['s_equity']-st['sub_cost'],'feasible_to_date':feasible}
  # Explicit cash, RE and debt assertions in the production chain.
  assert abs((before['m_debt']+before['s_debt'])-(st['m_debt']+st['s_debt'])-(mprincipal+sprincipal))<1e-7*max(1.,r)
  assert abs(st['internal_face']-(before['internal_face']-actualrepay-net_common))<1e-7
  assert st['m_deposit']>=-1e-8 and st['s_deposit']>=-1e-8
  assert st['m_portfolio']>=-1e-8 and st['s_portfolio']>=-1e-8
  rows.append(row)
  if not feasible:break
 value=sum(x['distribution_per_share']/(1+p['rate'])**x['year'] for x in rows) if feasible else None
 terminal={str(k):sum(x['distribution_per_share']/(1+k)**(x['year']-5) for x in rows[5:]) if feasible else None for k in (.085,.095)}
 return {'parameters':p,'initial_state':initial(p),'feasible':feasible,'value_per_share':value,'five_year_distributions':[x['distribution_per_share'] for x in rows[:5]] if feasible else None,'year5_remaining_value':terminal,'years':rows,'pv_after_year5':sum(x['distribution_per_share']/(1+p['rate'])**x['year'] for x in rows[5:]) if feasible else None}
SCENARIOS={'customer_finance_gross_low':{'customer_finance_yield_multiplier':.8},'customer_finance_gross_high':{'customer_finance_yield_multiplier':1.2},
 'portfolio_maturity10':{'portfolio_years':10},'minority_low':{'minority_profit_share':.005},'minority_high':{'minority_profit_share':.015},
 'common_payout20':{'common_payout':.20},'indonesia_penalty':{'extra_guarantee':.1668},'base':{},'core_low':{'margin':.145,'rate':.095},'core_high':{'margin':.151,'rate':.085},'product_crosscheck':{'method':'product'},
 'cycle':{'cycle':True,'wc_shock':3.,'extra_guarantee':.5},'structural':{'structural':True,'wc':.28,'extra_guarantee':1.5,'capacity_fraction':.50},'upside':{'upside':True},
 'return_slow':{'sub_release':.03,'mother_release':.03},'return_fast':{'sub_release':.10,'mother_release':.10},'sub_dividend_delay3':{'delay_sub':3},
 'internal_low':{'internal_face':18.748429},'internal_high':{'internal_face':27.222078},'internal_callable':{'internal_years':1},'internal_interest2':{'internal_rate':.02},'internal_callable_approved_netting':{'internal_years':1,'net_settlement':True},
 'deposit_delayed5':{'deposit_years':5},'financial_yield_zero':{'cash_yield':0.,'deposit_yield':0.,'portfolio_yield':0.,'private_yield':0.},'financial_principal_removed':{'remove_principal':True},
 'portfolio_haircut10':{'portfolio_haircut':.10},'sub_capacity30':{'capacity_fraction':.30},'no_refinance':{'refinance':0.},'credit_guarantee_stress':{'extra_guarantee':3.,'wc_shock':8.,'cycle':True,'refinance':0.},
 'associate_exit12':{'associate_exit':12},'private_capital_policy_extra':{'extra_incentive_cash':.4670198},'funding_failure':{'cash_shock':80.},'discount_plus100bp':{'rate':.10},'margin_minus100bp':{'margin':.138}}
def main():
 if '--base-only' in sys.argv:out=project()
 else:out={'company':'CN:600031','information_cutoff':ASOF,'units':'CNY billion; per-share CNY','facts_and_budgets':A,'scenarios':{k:project(v) for k,v in SCENARIOS.items()},'convergence':{str(n):project({},n) for n in (160,300,420)},'tail_scenarios':{k:project(v,420) for k,v in SCENARIOS.items()}}
 json.dump(out,sys.stdout,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False);sys.stdout.write('\n')
if __name__=='__main__':main()
