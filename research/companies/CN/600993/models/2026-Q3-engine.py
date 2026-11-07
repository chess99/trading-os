#!/usr/bin/env python3
"""CN600993 conditional owner-cash model; RMB million, no external files."""
import copy,json,math,sys
SHARES=431.053891
ASOF='2026-10-30T10:30:00Z'
# cash, net operating capital, paid capital, statutory reserve, retained earnings,
# initial annual external revenue, EBIT margin, tax, parent, parent ownership, parent investment cost
DATA={
'P':[444.95731102,850,431.053891,295.29264633,3997.61373170,2050,.315,.15,None,1,0],
'DH':[25,77.08,66,10,54.4467,500,.125,.15,'P',32/66,32],
'DHLOW':[5,25.6717647059,15,1,9.6717647059,25,.11,.25,'DH',.575,14.7612647059],
'COMM':[40,265,237.25,20,43.38,1400,.009,.25,'P',1,264.99588451],
'MED':[12,110,176,10,-10,35,.008,.25,'P',.9577,220.89381560],
'BJ':[8,25,76.5,0,-49.0753,90,-.006,.25,'MED',.798144*.997622,61.058],
'GWK':[5,380,10,0,38.0999336,27,.70,.25,'P',1,10],
'POOL':[12,0,500,20,192,0,0,.25,'P',1,500],
'OTHER':[5.15094384,120,100,8,25,70,.045,.25,'P',.85,114.41100617],
}
# Parent cost exact total1142.30070628 is source-based allocated group budgets.
assert abs(sum(v[10] for k,v in DATA.items()if v[8]=='P')-1142.30070628)<1e-6
CASES={
'base':{},'historical_profit_no_special':{'payout':.50,'extra_rate':0},'baseline_profit_slow_release':{'extra_rate':.03},'slow_parent_distribution':{'payout':.30,'extra_rate':.03},'fast_parent_distribution':{'payout':.80,'extra_rate':.20},'core_low':{'p_margin':.30,'growth':.02,'dh_growth':.10,'r':.095},'core_high':{'p_margin':.33,'growth':.04,'dh_growth':.18,'r':.085},
'cycle':{'cycle':True},'structural':{'structural':True,'p_margin':.245,'growth':0,'dh_growth':.025},'optimistic':{'p_margin':.345,'growth':.05,'dh_growth':.22},
'aux_low':{'method':'capital','capital_return':.68,'r':.095},'aux_high':{'method':'capital','capital_return':.79,'r':.085},
'permanent_tax25':{'tax25':True},'upstream_delay3':{'upstream_delay':3},'pool550':{'pool_face':550},'pool850':{'pool_face':850},
'pool_material_minority_claim':{'pool_share':.85},'pool_full_ownership':{'pool_share':1},'pool_high_minority_assignment':{'pool_share':32/66},'financial_loss10pct':{'fin_loss':.10},'cd_delay5':{'cd_years':5},
'property_rent_half':{'rent_factor':.5},'pool_capital_return_delay15':{'cap_return_start':15},'lower_nci_21pct':{'lower_share':.7882},'lower_nci_60pct':{'lower_share':.40},'hospital_support_stop':{'hospital_stop':True},
'capital_intensity_plus50pct':{'capital_factor':1.5},'financing_failure':{'fin_loss':1,'p_margin':-.20,'growth':-.10,'support_limit':0,'debt_limit':0},
}
def initial(c):
 s={}
 for k,v in DATA.items():
  cash,capital,paid,reserve,re,rev,margin,tax,parent,ownership,cost=v
  s[k]=dict(cash=cash,capital=capital,paid=paid,reserve=reserve,re=re,revenue=rev,losses=[],parent=parent,ownership=ownership,cost=cost,treasury=0,cd=0,investments=0,external_debt=0,lease=({'P':15.94980257,'COMM':10,'MED':35,'BJ':10.34369997}.get(k,0)),loans={},investment_costs={})
 for k,a in s.items():
  if a['parent']:s[a['parent']]['investment_costs'][k]=a['cost']
 s['P']['treasury']=1835.95749066;s['P']['cd']=867.72933352;s['P']['investments']=126.87861857;s['OTHER']['investments']=9.56045856;s['OTHER']['treasury']=6
 s['P']['loans']={'GWK':336.90006640,'COMM':24,'OTHER':4.56975976};s['POOL']['loans']={'P':c.get('pool_face',700)}
 # Unallocated NCI opening budget calibrated to Q3 group NCI, NOT an identified legal owner.
 base_other_nci=(130.4467*(1-32/66)+25.6717647059*.425+(176+(27.4247*(.798144*.997622)-61.058))*.0423+27.4247*(1-.798144*.997622)+133*.15)
 pool_share=1-(130.94579336-base_other_nci)/712
 s['POOL']['ownership']=c.get('pool_share',pool_share)
 s['DHLOW']['ownership']=c.get('lower_share',.575)
 # Creditor assignment is uncertain, but never creates cash. Alternative face
 # reclassifies economic opening equity between parent and creditor, not money.
 delta=c.get('pool_face',700)-700;s['P']['re']-=delta;s['POOL']['re']+=delta
 for k,a in s.items():
  a['rou_asset']=a['lease'];a['historical_support_used']=0;a['loan_allowances']={};a['capital_reserve']=89.12046524 if k=='P' else 0;a['legacy_dividend_payable']=2.63057165 if k=='P' else 0
  owed=sum(x['loans'].get(k,0) for x in s.values())
  assets=a['cash']+a['capital']+a['treasury']+a['cd']+a['investments']+sum(a['loans'].values())-sum(a['loan_allowances'].values())+sum(a['investment_costs'].values())+a['rou_asset']
  a['other_net_book_assets']=a['paid']+a['reserve']+a['capital_reserve']+a['re']+owed+a['legacy_dividend_payable']+a['external_debt']+a['lease']-assets
  # This reconciliation is never added to valuation or magically liquidated.
 return s

def taxpay(ebt,losses,tax,year):
 losses=[[y,v]for y,v in losses if year-y<=5 and v>1e-10];used=0
 if ebt<0:losses.append([year,-ebt]);return 0,losses,used
 taxable=ebt
 for x in losses:
  take=min(taxable,x[1]);x[1]-=take;taxable-=take;used+=take
 return taxable*tax,losses,used

def reserve_profit(s,ni):
 old=s['re'];s['re']+=ni
 transferable=min(max(0,s['re']-max(old,0))*.10,max(0,.5*s['paid']-s['reserve']))
 s['re']-=transferable;s['reserve']+=transferable
 return transferable

def simulate(name,years=120,start=None,overrides=None):
 c=dict(CASES[name]);c.update(overrides or {});r=c.get('r',.09);s=initial(c) if start is None else copy.deepcopy(start['state']);first=1 if start is None else start['year']+1;rows=[];pv=0;pay5=[];state5=None;failure=None
 for year in range(first,years+1):
  opening=copy.deepcopy(s);flows={k:{'loan_interest_in':0.,'loan_interest_out':0.,'principal_in':0.,'principal_out':0.,'new_loan_in':0.,'new_loan_out':0.,'dividend_in':0.,'dividend_out':0.,'nci_dividend':0.,'capital_return_in':0.,'capital_return_out':0.,'nci_capital_return':0.,'realized_cost':0.,'capital_gain':0.,'capital_gain_tax':0.,'credit_loss':0.,'credit_recovery':0.,'legacy_dividend_payment':0.}for k in s}
  for lender,a in opening.items():
   for borrower,face in a['loans'].items():
    rate=0 if borrower in ['MED','BJ'] else .01 if borrower in ['GWK','P'] else .02
    interest=face*rate;flows[lender]['loan_interest_in']+=interest;flows[borrower]['loan_interest_out']+=interest
  legacy=s['P']['legacy_dividend_payable'];s['P']['cash']-=legacy;s['P']['legacy_dividend_payable']=0;flows['P']['legacy_dividend_payment']=legacy
  # All actual EBIT entries exclude treasury yield and intercompany interest.
  for k,a in s.items():
   f=flows[k];old=opening[k];base=DATA[k];tax=.25 if c.get('tax25')and k in ['P','DH'] else base[7]
   g=c.get('growth',.03) if k=='P' else c.get('dh_growth',.15) if k in ['DH','DHLOW'] else .02 if k in ['COMM','OTHER'] else .01
   if year>5:g=.01+(g-.01)*max(0,(10-year)/5)
   if c.get('structural')and year>2:g=0 if k!='GWK' else -.01
   if year==1:newrev=base[5]
   else:newrev=old['revenue']*(1+g)
   if c.get('cycle'):
    factor={1:.92,2:.95,3:1}.get(year,1);prev={1:1,2:.92,3:.95,4:1}.get(year,1);newrev*=factor/prev
   margin=c.get('p_margin',.315)if k=='P'else base[6]
   if k=='P' and year>5:margin-=min(.035,(year-5)*.0025)
   if k in ['DH','DHLOW']and year>5:margin=max(.075,margin-(year-5)*.001)
   if c.get('structural'):
    if k in ['DH','DHLOW']:margin=.06
    if k in ['COMM','MED','BJ']:margin=-.005 if year<=3 else .002
   if c.get('cycle') and year<=2:margin-=.025 if k in ['P','DH']else .002
   if k=='BJ' and year>3:margin=.012
   if k=='GWK':newrev=base[5]*(1.01**(year-1))*c.get('rent_factor',1)*(1 if year<=9 else .8)
   ebit=newrev*margin
   if c.get('hospital_stop') and k=='BJ' and year>=4:
    newrev=0;ebit=-12 if year==4 else 0
   growthcap=max(0,newrev-old['revenue'])*({'P':.20,'DH':.23,'DHLOW':.22,'COMM':.16,'MED':.30,'BJ':.30,'GWK':0,'OTHER':.25,'POOL':0}[k])
   research=25 if k=='P' and year<=5 else 12*(1.01**(year-6)) if k=='P' else 0
   growthcap=(growthcap+research)*c.get('capital_factor',1)
   # capital method: separately estimated mature productive asset return plus
   # lower incremental return on actual additional deployed capital.
   if c.get('method')=='capital':
    rr=c.get('capital_return',.735)if k=='P'else {'DH':.65,'DHLOW':.10,'COMM':.035,'MED':.008,'BJ':-.015,'GWK':.05,'POOL':0,'OTHER':.025}[k]
    ebit=base[1]*rr*(1.01**(year-1))+max(0,old['capital']-base[1])*(.25 if k=='P'else .12)
   maintenance=max(0,old['capital'])*(.045 if k=='P' else .04)
   # Mature replacement included: depreciation and maintenance cash both persist.
   lease_interest=old['lease']*.04;lease_principal=old['lease']*.20;lease_renewal=lease_principal*(newrev/old['revenue'] if old['revenue'] else 1)
   a['lease']=old['lease']-lease_principal+lease_renewal;lease_depreciation=lease_principal;a['rou_asset']=old['rou_asset']-lease_depreciation+lease_renewal
   treasury_yield=max(0,old['treasury'])*.02;cd_yield=old['cd']*.022;cash_yield=max(0,old['cash'])*.012
   treas_release=min(a['treasury'],1835.95749066/3 if k=='P' else max(0,a['treasury']))
   cd_release=min(a['cd'],867.72933352/c.get('cd_years',3))if k=='P'else 0
   finloss=(treas_release+cd_release)*c.get('fin_loss',0)
   a['treasury']-=treas_release;a['cd']-=cd_release
   inv_release=min(a['investments'],(126.87861857 if k=='P' else 9.56045856)/10) if year>=5 else 0
   inv_yield=old['investments']*.02; a['investments']-=inv_release
   # Sale at book is explicit conditional budget, not asserted market value;
   # separate downside recovery implemented through same realized P&L/cash bridge.
   inv_loss=inv_release*(.4 if c.get('structural') else 0)
   operating_ebt=ebit-lease_interest
   ebt=operating_ebt+treasury_yield+cd_yield+cash_yield+inv_yield+f['loan_interest_in']-f['loan_interest_out']-old['external_debt']*.05-finloss-inv_loss
   taxcash,a['losses'],lossused=taxpay(ebt,a['losses'],tax,year);ni=ebt-taxcash
   a['capital']+=growthcap
   # EBIT has lease depreciation; add it back and pay actual lease principal.
   cashflow=ni+maintenance+lease_depreciation-maintenance-growthcap-lease_principal+treas_release+cd_release+inv_release
   a['cash']+=cashflow;reserve=0;a['revenue']=newrev
   f.update(revenue=newrev,ebit=ebit,growth_capital=growthcap,research_capital=research,maintenance_capex=maintenance,depreciation=maintenance,lease_interest=lease_interest,lease_depreciation=lease_depreciation,lease_principal=lease_principal,lease_non_cash_renewal=lease_renewal,treasury_yield=treasury_yield,cd_yield=cd_yield,cash_yield=cash_yield,investment_yield=inv_yield,treasury_release=treas_release,cd_release=cd_release,investment_release=inv_release,financial_loss=finloss+inv_loss,ebt=ebt,tax=taxcash,net_income=ni,tax_loss_used=lossused,statutory_transfer=reserve,operating_cash_change=cashflow,tax_rate=tax)
  # Principal must actually leave payer, reach creditor, never create profit.
  for lender in ['POOL','P']:
   for borrower,face in list(s[lender]['loans'].items()):
    reserve=max(2,s[borrower]['revenue']*.04)
    scheduled=min(face,c.get('pool_face',700)/7)if borrower=='P'else min(face,10 if borrower=='GWK'else 5)
    actual=min(scheduled,max(0,s[borrower]['cash']-reserve))
    s[borrower]['cash']-=actual;s[lender]['cash']+=actual;s[lender]['loans'][borrower]-=actual
    flows[borrower]['principal_out']+=actual;flows[lender]['principal_in']+=actual
    allowance=s[lender]['loan_allowances'].get(borrower,0);reverse=min(actual,allowance)
    s[lender]['loan_allowances'][borrower]=allowance-reverse;flows[lender]['credit_recovery']+=reverse
  # Support is an actual new loan with a finite external funding envelope.
  for k in [x for x in s if x!='P']:
   need=max(0,2+s[k]['revenue']*.025-s[k]['cash'])
   if need:
    limit=c.get('support_limit',20)*(1.01**(year-1));already=sum(f['new_loan_in'] for f in flows.values())
    if c.get('hospital_stop') and k in ['MED','BJ'] and year>=4:limit=0
    if already+need>limit+1e-8:failure={'year':year,'entity':k,'reason':'subsidiary financing cap','unfunded':need};break
    s['P']['historical_support_used']+=need;s['P']['cash']-=need;s[k]['cash']+=need;s['P']['loans'][k]=s['P']['loans'].get(k,0)+need;flows[k]['new_loan_in']+=need;flows['P']['new_loan_out']+=need
    if k in ['MED','BJ']:
     s['P']['loan_allowances'][k]=s['P']['loan_allowances'].get(k,0)+need;flows['P']['credit_loss']+=need
  if failure:break
  if s['P']['cash']<0:
   need=-s['P']['cash'];cap=c.get('debt_limit',205)
   if s['P']['external_debt']+need>cap:failure={'year':year,'entity':'P','reason':'parent financing cap','unfunded':need};break
   s['P']['external_debt']+=need;s['P']['cash']+=need;flows['P']['external_draw']=need
  # Bottom-up real cash distributions; statutory profit and cash checked separately.
  for k in ['DHLOW','BJ','DH','COMM','MED','GWK','POOL','OTHER']:
   a=s[k];f=flows[k];parent=a['parent'];reserve=max(2,a['revenue']*.04)
   f['statutory_transfer']=reserve_profit(a,f['net_income']+f['dividend_in']-f['credit_loss']+f['credit_recovery'])
   dividend=min(max(0,a['re']),max(0,a['cash']-reserve),max(0,f['net_income'])*.85+max(0,a['cash']-reserve)*.12)
   if year<=c.get('upstream_delay',0):dividend=0
   a['cash']-=dividend;a['re']-=dividend;portion=dividend*a['ownership'];nci=dividend-portion
   s[parent]['cash']+=portion;flows[parent]['dividend_in']+=portion;f['dividend_out']=dividend;f['nci_dividend']=nci
   capreturn=0
   if k=='POOL'and year>=c.get('cap_return_start',5):
    capreturn=min(a['paid']*.15,max(0,a['cash']-reserve));oldpaid=a['paid'];a['paid']-=capreturn;a['cash']-=capreturn
    gross=capreturn*a['ownership'];cost=min(s[parent]['investment_costs'][k],s[parent]['investment_costs'][k]*capreturn/oldpaid)if oldpaid else 0;s[parent]['investment_costs'][k]-=cost
    gain=gross-cost;gtax=max(0,gain)*flows[parent]['tax_rate'];s[parent]['cash']+=gross-gtax;s[parent]['re']+=gain-gtax
    flows[parent]['capital_return_in']+=gross;flows[parent]['realized_cost']+=cost;flows[parent]['capital_gain']+=gain;flows[parent]['capital_gain_tax']+=gtax;f['capital_return_out']=capreturn;f['nci_capital_return']=capreturn-gross
  a=s['P'];f=flows['P'];f['statutory_transfer']=reserve_profit(a,f['net_income']+f['dividend_in']-f['credit_loss']+f['credit_recovery']);reserve=max(100,205*a['revenue']/2050)+min(sum(s['POOL']['loans'].values()),c.get('pool_face',700)/7)
  debt_repay=min(a['external_debt'],max(0,a['cash']-reserve));a['external_debt']-=debt_repay;a['cash']-=debt_repay;f['external_repay']=debt_repay
  normal=max(0,f['net_income']+f['dividend_in']-f['credit_loss']+f['credit_recovery'])*c.get('payout',(.50 if year<=5 else .65))
  extra=max(0,a['cash']-reserve-normal)*c.get('extra_rate',.12)
  div=min(max(0,a['re']),max(0,a['cash']-reserve),normal+extra);a['cash']-=div;a['re']-=div;f['dividend_out']=div
  for k,a in s.items():
   f=flows[k];o=opening[k]
   cash_expected=o['cash']+f['operating_cash_change']+f['principal_in']-f['principal_out']+f['new_loan_in']-f['new_loan_out']+f['dividend_in']-f['dividend_out']+f['capital_return_in']-f['capital_return_out']-f['capital_gain_tax']+f.get('external_draw',0)-f.get('external_repay',0)-f['legacy_dividend_payment']
   re_expected=o['re']+f['net_income']-f['statutory_transfer']+f['dividend_in']-f['dividend_out']+f['capital_gain']-f['capital_gain_tax']-f['credit_loss']+f['credit_recovery']
   assert abs(a['cash']-cash_expected)<1e-6 and abs(a['re']-re_expected)<1e-6,(year,k)
   owed=sum(x['loans'].get(k,0) for x in s.values())
   assets=a['cash']+a['capital']+a['treasury']+a['cd']+a['investments']+sum(a['loans'].values())-sum(a['loan_allowances'].values())+sum(a['investment_costs'].values())+a['rou_asset']+a['other_net_book_assets']
   assert abs(assets-owed-a['legacy_dividend_payable']-a['external_debt']-a['lease']-a['paid']-a['reserve']-a['capital_reserve']-a['re'])<1e-5,(year,k,'balance')
   assert a['cash']>=-1e-8 and a['paid']>=-1e-8 and f['dividend_out']<=max(0,o['re']+f['net_income']-f['statutory_transfer']+f['dividend_in'])+1e-6
  assert abs(sum(x['loan_interest_in']-x['loan_interest_out'] for x in flows.values()))<1e-8
  assert abs(sum(x['principal_in']-x['principal_out'] for x in flows.values()))<1e-8
  pv+=div/SHARES/(1+r)**(year-first+1)
  row={'year':year,'opening':opening,'flows':flows,'closing':copy.deepcopy(s),'ordinary_cash_per_share':div/SHARES,'cumulative_present_value':pv,'external_nci_cash':sum(f['nci_dividend']+f['nci_capital_return']for f in flows.values())};rows.append(row)
  if year<=5:pay5.append(div/SHARES)
  if year==5:state5={'year':5,'state':copy.deepcopy(s)}
 return {'case':name,'rate':r,'years':years,'first_year':first,'feasible':failure is None,'failure':failure,'value_per_share':pv if failure is None else None,'first5':pay5,'state5':state5,'closing_state':s,'annual':rows}

def result():
 runs={n:simulate(n,120)for n in CASES};base=runs['base'];tails={str(t):simulate('base',t)for t in [180,240]};holder={n:simulate(n,120,start=base['state5'])for n in ['core_low','core_high']}
 return {'schema':'cn600993_owner_cash_v1','information_cutoff':ASOF,'units':'CNY million except per share','shares_million':SHARES,'input_data':DATA,'cases':CASES,'runs':runs,'actual_tail_extensions':tails,'holder_continuations':holder,'value_range':{'low':math.floor(runs['core_low']['value_per_share']*10)/10,'high':math.ceil(runs['core_high']['value_per_share']*10)/10,'currency':'CNY'},'return_model':{'schema_version':1,'method':'annual_common_equity_irr_v1','currency':'CNY','model_as_of':ASOF,'base_case_distributions_per_share':base['first5'],'base_case_terminal_equity_value_range_per_share':{'year_5':{'low':holder['core_low']['value_per_share'],'high':holder['core_high']['value_per_share']}}}}
if __name__=='__main__':json.dump(result(),sys.stdout,ensure_ascii=False,separators=(',',':'),sort_keys=True);sys.stdout.write('\n')
