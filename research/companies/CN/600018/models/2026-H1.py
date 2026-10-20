"""上港2026H1：亿元、亿股；仅标准库，无网络。"""
import json, math
from pathlib import Path
S=232.79960504
D=[.20,.20,.21,.22,.23]
# Cash-rent convention: exclude both current/noncurrent lease liability from net debt.
NET_DEBT=3.3586832993+65.7030347299+309.2145130335+142.6909728816+.0306082192-409.7515109716
LOANS=16.6788761111
BOOK=[362.5005851308,222.1748446316,93.2207240058,36.7454486832,209.2301386873]
MARKET=[173.2695057113,105.6705033216,63.4512722422,24.8966823420]
FIN=50.1966527278
NCI_BOOK=167.8969604219
PROJECT_PAID=131.30  # 121.30 reported plus 10 cutoff-stub construction budget
# Project equity-funded allocation; attributable debt sensitivity separately disclosed.
LEGACY_NCI_BASE=NCI_BOOK-.2*121.30
PAID_JULY=.145*S
PARAMS={
 'low':dict(ebit=118,multiple=9,growth=.02,roic=.10,project_rate=.075,unit_cash=310,util=.80,other_q=.65,financial_q=.8,nci_q=1.10,required_cash=60),
 'base':dict(ebit=121,multiple=9.5,growth=.025,roic=.10,project_rate=.0725,unit_cash=325,util=.825,other_q=.75,financial_q=.9,nci_q=1.05,required_cash=50),
 'high':dict(ebit=124,multiple=10,growth=.03,roic=.10,project_rate=.07,unit_cash=340,util=.85,other_q=.85,financial_q=1,nci_q=1.0,required_cash=40)}

def pv(cash,rate,offset=0): return sum(x/(1+rate)**(i+1-offset) for i,x in enumerate(cash) if i+1>offset)

def project(c,extra_capital=0,delay=0):
 # Eight-year phased remaining construction; 35 years cash, no residual sale value.
 build=[35,55,60,60,55,45,40,31.58]
 build=[x*(1+extra_capital/381.58) for x in build]
 # Existing assets produce from first phase. No claim these volumes are announced guidance.
 vol=[v*c['util']/.825 for v in [1,2,3.2,4.5,5.8,7,8.2]]+[11.6*c['util']]*28
 if delay: vol=[0]*delay+vol[:-delay]
 rows=[]; placed=PROJECT_PAID; cumdep=0
 for t in range(1,36):
  cap=build[t-1] if t<=8 else 0
  placed+=cap
  # 30-year composite life, depreciation bounded by paid/depreciable capital.
  commissioned=(512.88+extra_capital)*vol[t-1]/(11.6*c['util'])
  assert commissioned <= placed+1e-8
  dep=min(commissioned/30,max(0,placed-cumdep)); cumdep+=dep
  ebitda=vol[t-1]*c['unit_cash']/100
  ebit=ebitda-dep
  tax=max(0,ebit)*.25  # do not cash-credit project startup losses
  maintenance=8*(vol[t-1]/(11.6*c['util']))
  wc=(vol[t-1]-(vol[t-2] if t>1 else 0))*.25
  cf=ebitda-tax-maintenance-wc-cap
  rows.append(dict(year=t,volume_million_teu=vol[t-1],ebitda=ebitda,depreciation=dep,ebit=ebit,tax=tax,maintenance=maintenance,working_capital=wc,construction=cap,fcff=cf))
 return rows

def investments(c,years=5):
 b=BOOK[:]; q=[MARKET[i]/BOOK[i] for i in range(4)]+[c['other_q']]
 roe=[.08,.09,.07,.06,.06]; payout=[.35,.35,.60,.45,.40]
 value0=sum(x*y for x,y in zip(b,q))+FIN*c['financial_q']
 rows=[]
 for t in range(1,years+1):
  earnings=[x*y for x,y in zip(b,roe)]
  div=[x*y for x,y in zip(earnings,payout)]
  b=[x+y-z for x,y,z in zip(b,earnings,div)]
  rows.append({'year':t,'earnings':sum(earnings),'dividends':sum(div),'books':b[:],'value':sum(x*y for x,y in zip(b,q))+FIN*c['financial_q']})
 return value0,rows

def run(c,extra_capital=0,delay=0,invest_freeze=False):
 proj=project(c,extra_capital,delay); pc=[x['fcff'] for x in proj]
 proj0=pv(pc,c['project_rate']); proj5=pv(pc,c['project_rate'],5)
 inv0,inv=investments(c)
 legacy_nci0=LEGACY_NCI_BASE*c['nci_q']
 reserve0=c['required_cash']
 # Reported bank cash409.7515 excludes restricted cash. Debt variable thereafter
 # means bank debt minus SURPLUS cash: required operating cash belongs to operating EV.
 gross0=NET_DEBT+409.7515109716
 stub=86/365
 normalfcf=c['ebit']*.75*(1-c['growth']/c['roic'])
 stub_finance=(gross0*.02-409.7515109716*.01)*.75
 debt0=NET_DEBT+reserve0+PAID_JULY+10*.8-stub*(normalfcf+inv[0]['dividends']+LOANS*.018*.75-stub_finance-10)
 cash0=gross0-(debt0-reserve0)
 value0=(c['ebit']*c['multiple']+inv0+LOANS-debt0-legacy_nci0+.8*proj0)/S
 debt=debt0; cash=cash0; gross=gross0; rows=[]; nci_book=LEGACY_NCI_BASE
 # Parent bank debt420 is a budget allocation of group bank debt521.0, not a new
 # external fact. Consolidated subsidiaries hold remaining101.0; refinance at par.
 parent_gross=420.0; parent_cash=181.1658315785-PAID_JULY
 parent_undistributed=513.6720831249; parent_rows=[]
 for t in range(1,6):
  ebit=c['ebit']*(1+c['growth'])**t
  nopat=.75*ebit
  reinvest=nopat*c['growth']/c['roic']
  maturefcf=nopat-reinvest
  reserve=reserve0*(1+c['growth'])**t
  previous_reserve=reserve0*(1+c['growth'])**(t-1)
  assert reinvest >= reserve-previous_reserve
  nciprofit=18*(1+c['growth'])**t; ncidiv=.6*nciprofit
  nci_book+=nciprofit-ncidiv
  shareholder=D[t-1]*S; projcash=pc[t-1]
  minor_project_contribution=max(-projcash,0)*.2
  minor_project_distribution=max(projcash,0)*.2
  invcash=inv[t-1]['dividends']
  # Parent cash and funding determines actual new group gross borrowing.
  own=18*(1.02)**(t-1); remittance=48*(1.02)**(t-1)
  project_fund=.8*max(-projcash,0)
  additional_investment=.25*reinvest
  noninterest_need=8+project_fund+additional_investment+5+shareholder
  parent_preborrow=parent_cash+own+remittance-noninterest_need-.02*parent_gross
  borrowing=max(0,(100-parent_preborrow)/(1-.02/2))
  parent_interest=.02*(parent_gross+.5*borrowing)
  parent_cash=parent_cash+own+remittance-noninterest_need-parent_interest+borrowing
  parent_gross+=borrowing
  parent_undistributed+=70*(1.02)**(t-1)*.9-shareholder
  parent_rows.append(dict(year=t,own_cash=own,investment_cash=remittance,project_funding=project_fund,other_capital=8+additional_investment,finance_cash=parent_interest,net_other_settlement=5,ordinary_dividend=shareholder,net_new_external_debt=borrowing,bank_debt_end=parent_gross,cash_end=parent_cash,legal_retained_profit=parent_undistributed))
  assert parent_undistributed>0
  # Cash reserve growth is part of net reinvestment; it is not an external cash
  # payment. Actual group cash therefore adds reserve back to adjusted net debt.
  available_pre_finance=maturefcf+invcash+LOANS*.018*.75+projcash+minor_project_contribution-minor_project_distribution-ncidiv
  gross_end=gross+borrowing
  interest_expense=.02*(gross+.5*borrowing)
  cash_end_before_finance=gross_end-debt-shareholder+available_pre_finance+reserve
  netfinance=.75*(interest_expense-.01*.5*(cash+cash_end_before_finance))/(1-.75*.01/2)
  nextdebt=debt+shareholder-available_pre_finance+netfinance
  cash_end=gross_end-nextdebt+reserve
  interest_income=.01*(cash+cash_end)/2
  assert abs(netfinance-.75*(interest_expense-interest_income))<1e-8
  assert abs((gross_end-cash_end)-(nextdebt-reserve))<1e-8
  sub_cash=cash_end-parent_cash
  assert sub_cash>reserve-15*(1+c['growth'])**t
  rows.append(dict(year=t,ebit=ebit,nopat=nopat,maintenance=40*(1+c['growth'])**t,depreciation=40*(1+c['growth'])**t,growth_and_wc_investment=reinvest,required_cash_growth=reserve-previous_reserve,required_operating_cash=reserve,mature_fcff=maturefcf,investment_dividend=invcash,investment_value=inv[t-1]['value'],project_fcff=projcash,project_external_minority_contribution=minor_project_contribution,project_external_minority_distribution=minor_project_distribution,minority_legacy_profit=nciprofit,minority_legacy_dividend=ncidiv,finance_after_tax=netfinance,bank_interest_expense=interest_expense,deposit_interest_income=interest_income,ordinary_dividend=shareholder,net_debt_start=debt,net_debt_end=nextdebt,actual_bank_net_debt=nextdebt-reserve,bank_debt_start=gross,bank_debt_end=gross_end,bank_cash_start=cash,bank_cash_end=cash_end,subsidiary_cash_end=sub_cash,retained_nci_book=nci_book))
  assert abs(nextdebt-debt-shareholder+available_pre_finance-netfinance)<1e-9
  debt=nextdebt;cash=cash_end;gross=gross_end
 nci5=nci_book*c['nci_q']
 inv5=inv0 if invest_freeze else inv[-1]['value']
 tv5=(rows[-1]['ebit']*c['multiple']+inv5+LOANS-debt-nci5+.8*proj5)/S
 wacc=.075 if c['multiple']==9 else (.07 if c['multiple']==10 else .0725)
 mature_t5=rows[-1]['nopat']*1.015*(1-.015/.08)/(wacc-.015)
 mature_dcf=pv([y['mature_fcff'] for y in rows],wacc)+mature_t5/(1+wacc)**5
 auxiliary=(mature_dcf+inv0+LOANS-debt0-legacy_nci0+.8*proj0)/S
 return dict(current_value=value0,investment_current=inv0,project_value_current=proj0,legacy_nci_current=legacy_nci0,cutoff_net_debt=debt0,cutoff_actual_bank_net_debt=debt0-reserve0,cutoff_required_operating_cash=reserve0,cutoff_bank_debt=gross0,cutoff_bank_cash=cash0,cutoff_parent_cash=181.1658315785-PAID_JULY,project_terminal_value=proj5,investment_terminal_value=inv5,legacy_nci_terminal=nci5,terminal_net_debt=debt,terminal_actual_bank_net_debt=debt-rows[-1]['required_operating_cash'],terminal_value=tv5,auxiliary_value=auxiliary,mature_dcf=mature_dcf,dividends=D,annual=rows,parent=parent_rows,project=proj,investments=inv)

results={k:run(c) for k,c in PARAMS.items()}
base=results['base']; sens={}
# Cyclic two-year earnings loss, with long-run network intact.
sens['cyclical_two_years']={'current_value':base['current_value']-(15*.75/1.08+8*.75/1.08**2)/S,'description':'前两年经营EBIT分别少15/8亿元，税后损失折现，不改变长期终值倍数。'}
for name,kwargs in [('project_extra100',{'extra_capital':100}),('project_delay3',{'delay':3}),('investment_no_growth',{'invest_freeze':True})]:
 x=run(PARAMS['base'],**kwargs); sens[name]={k:x[k] for k in ['current_value','terminal_value','project_value_current','terminal_net_debt']}
c=dict(PARAMS['base'],ebit=111)
x=run(c); sens['mature_ebit_minus10']={k:x[k] for k in ['current_value','terminal_value','cutoff_net_debt']}
# Independent single-input structural alternatives, explicitly not core endpoints.
c=dict(PARAMS['base'],ebit=100,multiple=8,growth=.005,unit_cash=300,util=.65)
x=run(c); sens['structural']={k:x[k] for k in ['current_value','terminal_value','project_value_current']}
c=dict(PARAMS['base'],ebit=128,multiple=10.5,growth=.035,unit_cash=430,util=.9)
x=run(c); sens['upside']={k:x[k] for k in ['current_value','terminal_value','project_value_current']}
# Cash and ownership identities, zero discount hand-check, bank book retention.
assert abs(pv([10,20],0)-30)<1e-12
assert abs(sum(x['construction'] for x in base['project'])-381.58)<1e-9
for x in results.values():
 assert len(x['annual'])==5
 for y in x['annual']:
  assert abs(y['nopat']-y['growth_and_wc_investment']-y['mature_fcff'])<1e-9
  assert abs(.8*y['project_fcff']-(y['project_fcff']+y['project_external_minority_contribution']-y['project_external_minority_distribution']))<1e-9
 for i,y in enumerate(x['investments']):
  prev=sum(BOOK) if i==0 else sum(x['investments'][i-1]['books'])
  assert abs(sum(y['books'])-prev-y['earnings']+y['dividends'])<1e-9
out=dict(units='亿元、亿股；每股元',params=PARAMS,starting_bank_net_debt=NET_DEBT,results=results,sensitivities=sens)
Path(__file__).with_name('2026-H1-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:{a:v[a] for a in ['current_value','terminal_value','auxiliary_value','project_value_current','project_terminal_value','investment_current','investment_terminal_value','cutoff_net_debt','terminal_net_debt','legacy_nci_current','legacy_nci_terminal']} for k,v in results.items()},indent=2))
print(json.dumps(sens,indent=2))
