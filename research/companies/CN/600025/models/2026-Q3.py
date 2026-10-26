#!/usr/bin/env python3
"""600025 full ordinary-equity project DCF and legal holder cash forecast.
Cutoff2026-10-26T14:00:00+08:00; CNY bn, bn shares and bn kWh.
Research assumptions distinguished from source facts in report. No price/IRR input.
"""
import json, math
from pathlib import Path
S=18.631094257
D=12.86153548252+7.60206886607+89.92829278035+5.03432504108+10.02803032770+1.04987728601
PD=.5445591529+3.76709300772+50.03871641483+5.03432504108+10.02803032770
PERP=16.217
FACT={"shares":S,"financial_debt_including_lease_and_accruals":D,"parent_debt":PD,
"cash_equivalents":3.72253673088,"cash_funds":4.73352182637,"parent_cce":.38992885011,
"ordinary_book_equity":89.26155561263-PERP,"nci_book":6.56759097069,
"financial_investments":3.40228742690+1.44209053814+.57035715058,
"parent_retained":23.90057410048,"parent_reserve":5.39638671312,
"q3_revenue":7.95814429781,"q3_np":3.17752803387,
"q3_cfo":15.66983217184-9.08736770639,
"q3_capex":11.15169156613-7.25137652878,
"ytd_fcf_before_finance":15.66983217184-11.15169156613,
"q3_gross_margin_ytd":1-8.68826681539/21.10552486504}
PROJECTS={"RM":{"budget":58.3815079,"cip":8.28299014527,"first_power":2033,"GW":2.6},
"GS":{"budget":50.40133460819,"cip":4.42357346965,"first_power":None,"GW_historical_plan":2.2},
"BDa":{"budget":23.4922659,"cip":3.44129553187,"first_power":None,"GW_historical_plan":1.5},
"GX_preparatory_scope":{"budget":3.38219,"cip":2.27377883062,"first_power":None,"GW_historical_plan":2.1}}
for p in PROJECTS.values():p['budget_less_cip']=p['budget']-p['cip']

# FY2025 pp97-102, consistent balance and operating-capital proxy; CNY bn.
D25=sum([11.40924837254,13.36558519994,7.0294920445,89.90696883939,3.01694575343,.87318375252])
D24=sum([14.25864183125,12.09108859132,5.02008013699,89.66633714127,2.,.49410830399])
C25=88.1147747291+D25-3.9426238849-3.35683954573-1.43219328755-.52407461678
C24=79.16849207242+D24-3.09311429674-3.2738657337-1.38959566006-.50212403955
EB25=10.82631114676+2.62526646359-.31135451079-.02195057723
EB24=10.38746541627+2.67467698169-.32528603306-.01006393738
FACT['capital_proxy_2024']=C24;FACT['capital_proxy_2025']=C25
FACT['operating_ebit_proxy_2024']=EB24;FACT['operating_ebit_proxy_2025']=EB25
FACT['roic_proxy_2025']=EB25*.85/((C25+C24)/2)
FACT['incremental_roic_proxy_2024_to_2025']=(EB25-EB24)*.85/(C25-C24)

def pv(cash,rate):return sum(v/(1+rate)**(i+1) for i,v in enumerate(cash))
def annuity(cash,rate,years):return cash*(1-(1+rate)**(-years))/rate if rate else cash*years

def mature(rate=.055,life=50,price=1.,water=1.,maintenance=4.,tax_after=.25):
    # 2027 annual proxy. No unbuilt station revenue; full current debt NOT allocated away.
    rows=[]
    for i in range(1,life+1):
        infl=1.005**(i-1)
        # Existing domestic/foreign assets together for 15y, foreign concessions then run off.
        runoff=max(0.,min(1.,(25-i)/10)) if i>15 else 1.
        revenue=(25.6*price*water+1.6*runoff)*infl
        cash_cost=(6.2*(.75+.25*water))*infl
        da=7.5*infl
        tax=.15 if i<=4 else tax_after
        ebit=revenue-cash_cost-da
        maintenance_cash=maintenance*infl
        fcf=ebit*(1-tax)+da-maintenance_cash
        # extra large replacement, not annual D&A simply labelled free cash
        if i in (20,40):fcf-=8*infl
        rows.append(dict(year=2026+i,revenue=revenue,ebit=ebit,nopat=ebit*(1-tax),da=da,maintenance=maintenance_cash,fcff=fcf))
    ev=pv([x['fcff'] for x in rows],rate)
    # non-operating earnings absent from EBIT; investments added only once.
    # NCI shown at finite-life cash value, not their book equity.
    nci=annuity(.8,.075,30)
    capital_creditor_ceiling=7.64707985906-.26956263829+.23835321232+.06437698640
    common_residual=ev-D-PERP+nci*0+(FACT['cash_equivalents']-2.0296755)+FACT['financial_investments']-nci-capital_creditor_ceiling
    return dict(ev=ev,conditional_common_residual=common_residual,conditional_residual_per_share=common_residual/S,
        nci_value=nci,capital_creditor_ceiling=capital_creditor_ceiling,
        after_year5_pv_share=pv([x['fcff'] for x in rows[5:]],rate)/(1+rate)**5/ev,rows=rows)

def funding_step(cash,profit,da,capex,distribution,target_cash,credit_limit):
    """Production waterfall: financing capped; distributions cut before uncovered gap."""
    available=cash+profit+da-capex-target_cash
    if available < -credit_limit-1e-10:
        raise ValueError(f"融资不可行：零股利资金缺口 {-available:.6f} 超过新增融资上限 {credit_limit:.6f}")
    actual=min(distribution,max(0,available+credit_limit))
    borrowing=max(-available+actual,0)
    repayment=max(available-actual,0)
    end=cash+profit+da-capex-actual+borrowing-repayment
    assert abs(end-target_cash)<1e-8
    return actual,borrowing-repayment,end


import copy
P=Path(__file__).resolve().parent
old={k:globals()[k] for k in ['S','D','PD','PERP','FACT','annuity','mature','funding_step']}
# Full-project engineering cost before FUTURE finance, net of capitalized H1 interest.
# RM engineering disclosed, other dynamic budgets require finance-share estimates.
FACTS={
 'RM':dict(dynamic=58.3815079,engineering=44.6*1.10,cip=8.28299014527,old_interest=.39785046984,gen=11.281,gw=2.6,owner='upper_sub'),
 'GS':dict(dynamic=50.40133460819,cip=4.42357346965,old_interest=.07648238126,gen=None,gw=2.2,owner='parent_direct'),
 'BDa':dict(dynamic=23.4922659,cip=3.44129553187,old_interest=.11422327861,gen=6.149,gw=1.5,owner='upper_sub'),
 'GX':dict(dynamic=31.7,cip=2.27377883062,old_interest=.12294163552,gen=9.036,gw=2.1,owner='upper_sub'),
 'BDuo':dict(dynamic=15.85,cip=.44507355036,old_interest=0.,gen=3.096,gw=.72,owner='upper_sub'),
 'GLB':dict(dynamic=4.95,cip=.82378837876,old_interest=0.,gen=1.162,gw=.195,owner='parent_direct'),
 'PV_completion':dict(dynamic=8.75,engineering=8.75,cip=6.25152322764,old_interest=0.,gen=3.5,gw=2.5,owner='newenergy_sub',solar=True)}
# Q3 net CIP increased2.56456; 2.4 non-finance paid forecast allocated pro-rata to H1 CIP.
for f in FACTS.values():f['q3_engineering_paid']=2.4*f['cip']/28.59711873621
SC={
 'engineering_low':dict(rate=.06,loan=.032,finance_share=.10,cost=1.1,life=40,first=[2035,2035,2034,2035],gen=[11.281,8.,6.149,8.89],price=[.40,.27,.30,.30],water=.95,upstream_equity=1.),
 'central':dict(rate=.055,loan=.028,finance_share=.15,cost=1.,life=45,first=[2033,2033,2032,2033],gen=[11.281,9.46,6.149,9.036],price=[.425,.30,.33,.33],water=1.,upstream_equity=1.),
 'engineering_high':dict(rate=.05,loan=.024,finance_share=.20,cost=.95,life=50,first=[2033,2031,2031,2032],gen=[11.281,11.,6.149,9.4],price=[.45,.33,.36,.36],water=1.,upstream_equity=1.)}

for key,c in SC.items():
 c['first'] += [2038,2033,2029] if key=='engineering_low' else ([2036,2031,2028] if key=='central' else [2035,2029,2028])
 c['gen'] += [2.8,1.05,3.25] if key=='engineering_low' else ([3.096,1.162,3.5] if key=='central' else [3.6,1.22,4.0])
 c['price'] += [.30,.24,.25] if key=='engineering_low' else ([.33,.26,.29] if key=='central' else [.36,.28,.34])
# Core endpoints are LOCAL variations around central operating path, not all stress endpoints.
SC['core_low']=copy.deepcopy(SC['central']);SC['core_low'].update(rate=.06,loan=.03,cost=1.03,life=45,solar_cost_factor=1.2)
SC['core_high']=copy.deepcopy(SC['central']);SC['core_high'].update(rate=.05,loan=.026,cost=.97,life=45,solar_cost_factor=.92)
SC['core_low']['gen'][1]=8.8;SC['core_high']['gen'][1]=10.2
SC['core_low']['price']=[.40,.28,.31,.31,.31,.25,.27]
SC['core_high']['price']=[.45,.32,.35,.35,.35,.27,.31]

SC['cyclical']=copy.deepcopy(SC['central']);SC['cyclical'].update(mature_water=[.85,.9,.96,1,1],mature_price=1.01,loan=.03,parent_credit=9.)
SC['structural']=copy.deepcopy(SC['central']);SC['structural'].update(mature_water=[.9,.85,.85,.85,.85],mature_price=.92,mature_cost=1.1,water=.85,loan=.035,parent_credit=5.)
SC['upside']=copy.deepcopy(SC['central']);SC['upside'].update(mature_water=[1.04]*5,mature_price=1.03,water=1.04,loan=.024)

def legal_reserve_appropriation(profit,retained,reserve,paid_capital):
 return min(max(0,profit+min(0,retained))*.1,max(0,.5*paid_capital-reserve))

def construction_finance(opening_debt,engineering_cash,rate,equity_share=.3):
 # debt financed fraction of interest is drawn evenly through period; algebraic closure
 interest=rate*(opening_debt+.5*(1-equity_share)*engineering_cash)/(1-.5*(1-equity_share)*rate)
 draw=(1-equity_share)*(engineering_cash+interest)
 equity=equity_share*(engineering_cash+interest)
 assert abs(equity+draw-engineering_cash-interest)<1e-9
 return dict(interest=interest,draw=draw,equity=equity,debt=opening_debt+draw)

def build(name,params,idx,water_override=None,delay=0):
 f=FACTS[name];c=params;first=c['first'][idx]+delay;life=25 if f.get('solar') or f.get('wind') else c['life'];deplife=20 if f.get('solar') or f.get('wind') else 45
 # H1 base: Q3 project cash attribution not provided. No subtraction invented.
 engineering=f.get('engineering',f['dynamic']*(1-c['finance_share']))*c['cost']*c.get('solar_cost_factor',1.) if f.get('solar') else f.get('engineering',f['dynamic']*(1-c['finance_share']))*c['cost']
 sunk=f['cip']-f['old_interest']+f.get('q3_engineering_paid',0.);remain=max(0,engineering-sunk)
 debt=0.;capint=0.;retained=0.;reserve=0.;paidcapital=sunk;cash=0.;rows=[]
 # Opening project debt is ZERO incremental; all historical debt stays in old group bridge.
 # 70% of NEW total cash is project financed, not 70% of sunk cost borrowed twice.
 for y in range(2027,first+life):
  cap=remain/max(1,first-2027) if y<first else (remain if first==2027 and y==2027 else 0.)
  ramp=0 if y<first else (.5 if y==first else 1.)
  volume=c['gen'][idx]*c['water']*(water_override or 1)*ramp*(.997**max(0,y-first) if f.get('wind') else (.995**max(0,y-first) if f.get('solar') else 1.))
  revenue=volume*.992*c['price'][idx]/1.13
  # Explicit operating resources, not constant investment-return assumption.
  operating=f['gw']*(.08 if f.get('wind') else (.05 if f.get('solar') else .20))*ramp # CNY 200/kW annual including cash resource/environment cost proxy
  maintenance=f['gw']*(.05 if f.get('wind') else (.035 if f.get('solar') else .12))*ramp
  debt_begin=debt; cash_begin=cash;ret_begin=retained
  if cap:
   fin=construction_finance(debt,cap,c['loan']);interest=fin['interest'];draw=fin['draw'];equity=fin['equity'];debt=fin['debt'];capint+=interest;paidcapital+=equity
   da=tax=profit=div=repay=0.;stat_interest=0.;fcff=-cap
  else:
   interest=debt*c['loan'];stat_interest=interest;draw=equity=0.
   da=(engineering+f['old_interest']+capint)/deplife if y-first<deplife else 0.
   ebit=revenue-operating-da
   tax=max(0,ebit-interest)*.25 # no uncertain construction tax holiday assumed
   profit=ebit-interest-tax
   unlevered_da=(engineering+f['old_interest'])/deplife if y-first<deplife else 0.
   fcff=revenue-operating-max(0,revenue-operating-unlevered_da)*.25-maintenance
   appropr=0. if f.get('branch') else min(max(0,profit+min(retained,0))*.1,max(0,.5*paidcapital-reserve));reserve+=appropr;retained+=profit-appropr
   available=cash+profit+da-maintenance
   if available<0:
    # Extra capital call cannot disappear merely because production commenced.
    equity=-available;paidcapital+=equity;available=0.
   repay=min(debt,available*.7);debt-=repay;available-=repay
   div=available if f.get('branch') else min(max(0,retained),available);retained-=div;cash=available-div
  assert debt>=-1e-9 and cash>=-1e-9
  assert abs(cash_begin+revenue-operating-tax-cap-maintenance-interest+draw+equity-repay-div-cash)<1e-8
  rows.append(dict(year=y,engineering_cash=cap,capitalized_interest=interest if cap else 0,interest_expense=stat_interest,equity_call=equity,borrowing=draw,repayment=repay,debt=debt,revenue=revenue,da=da,tax=tax,statutory_profit=profit,dividend=div,cash=cash,retained=retained,legal_reserve=reserve,fcff=fcff))
 # Finite life: terminal cash is allowed only against legal retained+paid capital on liquidation.
 # No value for plant scrap assumed; still outstanding debt remains a creditor claim.
 final_residual=cash-debt
 equity_pv=sum((x['dividend']-x['equity_call'])/(1+c['rate']+.02)**(x['year']-2026) for x in rows)+final_residual/(1+c['rate']+.02)**(rows[-1]['year']-2026)
 enterprise_pv=sum(x['fcff']/(1+c['rate'])**(x['year']-2026) for x in rows)
 return dict(engineering=engineering,remaining_engineering=remain,first_power=first,full_power=first+1,generation=c['gen'][idx],tariff_including_vat=c['price'][idx],loan_rate=c['loan'],incremental_equity_pv=equity_pv,fcff_npv=enterprise_pv,future_capitalized_interest=capint,rows=rows)

def bundle(name):
 c=SC[name];projects={n:build(n,c,i) for i,n in enumerate(FACTS)}
 # Additional RM downstream 54e8 kWh deliberately held separate: joint design volumes
 # may already contain RM-regulated output at GS/GX. Never add all 54 on top blindly.
 # These are sensitivity endpoints, not an adopted compensation split.
 comp=sum(5.4*.22*.75/(1+c['rate'])**(y-2026) for y in range(max(c['first'])+1,max(c['first'])+1+c['life']))
 total=sum(x['fcff_npv'] for x in projects.values())
 maturity=old['mature'](c['rate'],40 if name=='engineering_low' else (60 if name in ('engineering_high','core_high') else 50),maintenance=4.5 if name in ('engineering_low','core_low') else (3.5 if name in ('engineering_high','core_high') else 4.))
 if name in ('cyclical','structural','upside'):
  for row in maturity['rows']:
   age=row['year']-2027;infl=1.005**age;w=c.get('mature_water',[1]*5)[min(age,4)];pf=c.get('mature_price',1);cf=c.get('mature_cost',1)
   rev=row['revenue']*w*pf;cost=6.2*infl*cf;ebit=rev-cost-row['da'];tax=.15 if age<4 else .25
   row.update(revenue=rev,ebit=ebit,nopat=ebit*(1-tax),fcff=ebit*(1-tax)+row['da']-row['maintenance']-(8*infl if age+1 in (20,40) else 0))
  newev=sum(x['fcff']/(1+c['rate'])**(x['year']-2026) for x in maturity['rows'])
  maturity['conditional_common_residual']+=newev-maturity['ev'];maturity['ev']=newev
 rows=[]
 for year in range(2027,2032):
  pr={n:next(x for x in v['rows'] if x['year']==year) for n,v in projects.items()}
  rows.append(dict(year=year,engineering_cash=sum(x['engineering_cash'] for x in pr.values()),capitalized_interest=sum(x['capitalized_interest'] for x in pr.values()),parent_direct_GS_equity=pr['GS']['equity_call'],parent_upper_sub_equity=sum(v['equity_call'] for k,v in pr.items() if k!='GS'),project_borrowing=sum(x['borrowing'] for x in pr.values()),project_dividends=sum(x['dividend'] for x in pr.values()),project_statutory_profit=sum(x['statutory_profit'] for x in pr.values())))
 return dict(projects=projects,mature=maturity,fcff_npv_before_additional_compensation=total,compensation_max_sensitivity=comp,
 conditional_common_before_other_projects_per_share=(maturity['conditional_common_residual']+total)/S,
 conditional_common_full_compensation_before_other_projects_per_share=(maturity['conditional_common_residual']+total+comp)/S,
 five_year_project_funding=rows)

# Announced 2026-054; forecast closing 2027, not a completed ownership fact.
ACQ=dict(price=8.7012044,old_debt=.44109644445+.69873486464+6.8483+.10548456367,
 cash=.04648791615,legal_retained=-1.56786683744,capital=9.79241652163,
 old_capital_payable=.17722204944+.04125958114+.00036734884)

def acquisition(params):
 c=copy.deepcopy(params);c['first']=[2028,2028,2028];c['gen']=[2.7,.26,.338];c['price']=[.35,.34,.34];c['life']=45
 if params.get('acq_delay'):c['first']=[x+params['acq_delay'] for x in c['first']]
 # Appraisal pp9-10: JXF/X and QSF/W2 are BRANCHES; ND/N is a wholly owned wind SUBSIDIARY.
 newfacts={'X':dict(dynamic=18.617,cip=3.91921463674,old_interest=.11426267834,gw=.6,branch=True),
 'W2':dict(dynamic=.810,engineering=.810*.95,wind=True,branch=True,cip=.01261966514,old_interest=0.,gw=.1),
 'N':dict(dynamic=.5331218,engineering=.5331218*.95,wind=True,cip=.33226816921,old_interest=.00358063057,gw=.13)}
 projects={}
 for i,(n,f) in enumerate(newfacts.items()):
  FACTS[n]=f;projects[n]=build(n,c,i);del FACTS[n]
 debt=ACQ['old_debt'];cash=.9*ACQ['cash'];subcash=.1*ACQ['cash'];retained=ACQ['legal_retained'];reserve=0.
 subretained=subreserve=subreceivable=nreceivable=0.;rows=[];last_project_cash=last_project_debt=0.
 for year in range(2027,2072):
  age=year-2027;infl=1.005**age;factor=.7+(.3*.995**age if age<25 else 0.)
  w=c.get('mature_water',[1]*5)[min(age,4)];pf=c.get('mature_price',1.)
  rev=1.15*factor*infl*w*pf;op=.28*factor*infl;da=.4*factor*infl;maint=.14*factor*infl
  intr=debt*(.016 if age<3 else .02);pp=rev-op-da-intr;taxrate=.15 if year<=2030 else .25
  profit=pp-max(0,pp)*taxrate
  active={n:next((x for x in z['rows'] if x['year']==year),None) for n,z in projects.items()};active={n:x for n,x in active.items() if x is not None}
  projectprofit=sum(x['statutory_profit'] for x in active.values())
  # 2025 mother NP .31284 vs consolidated .33890 supports90% direct /10% existing sub profit budget.
  subprofit=.1*profit;suballoc=max(0,subprofit+min(0,subretained))*.1
  subreserve+=suballoc;subretained+=subprofit-suballoc
  subdeclared=min(max(0,subprofit*.3),max(0,subretained));subretained-=subdeclared
  subreceived=subreceivable+.8*subdeclared;subreceivable=.2*subdeclared
  subbefore=subcash;subcash+=subprofit+.1*da-.1*maint-subreceived
  if subcash<0:raise ValueError('target existing operating subsidiaries cash infeasible')
  nd=active.get('N',{}).get('dividend',0.);nreceived=nreceivable+.8*nd;nreceivable=.2*nd
  branchprofit=sum(active[n]['statutory_profit'] for n in ('X','W2') if n in active)
  branchcash=sum(active[n]['dividend'] for n in ('X','W2') if n in active)
  liquidation=sum(z['rows'][-1]['cash']-z['rows'][-1]['debt'] for z in projects.values() if z['rows'][-1]['year']==year-1)
  calls=sum(x['equity_call'] for x in active.values())
  statutory=.9*profit+subdeclared+branchprofit+nd
  appropr=legal_reserve_appropriation(statutory,retained,reserve,ACQ['capital']);reserve+=appropr;retained+=statutory-appropr
  before=cash;opening=debt;oldpay=ACQ['old_capital_payable']/2 if age<2 else 0.
  available=cash+.9*(profit+da-maint)+subreceived+branchcash+nreceived+liquidation-calls-oldpay
  parent_call=max(0,.1-available);available+=parent_call
  repay=min(debt,max(0,available-.1)*.7);debt-=repay;available-=repay
  dividend=min(max(0,retained),max(0,available-.1));retained-=dividend;cash=available-dividend
  fcff=rev-op-max(0,rev-op-da)*taxrate-maint
  opcash=profit+da+sum(x['statutory_profit']+x['da'] for x in active.values())
  projectcash=sum(x['cash'] for x in active.values())+nreceivable;projectdebt=sum(x['debt'] for x in active.values())
  projectmaintenance=sum(newfacts[n]['gw']*(.05 if n in ('W2','N') else .12)*(.5 if year==projects[n]['first_power'] else (1. if year>projects[n]['first_power'] else 0.)) for n in active)
  totalcap=maint+projectmaintenance+sum(x['engineering_cash']+x['capitalized_interest'] for x in active.values())+oldpay
  netborrow=debt-opening+projectdebt-last_project_debt
  assert abs(before+subbefore+last_project_cash+opcash-totalcap+netborrow+parent_call-dividend-cash-subcash-projectcash)<1e-8,(year,'target consolidated conservation')
  last_project_cash=projectcash;last_project_debt=projectdebt
  rows.append(dict(year=year,operating_cash=opcash,capex_and_old_payment=totalcap,net_borrowing=netborrow,existing_fcff=fcff,existing_profit=profit,consolidated_profit=profit+projectprofit,statutory_profit=statutory,retained=retained,reserve=reserve,existing_sub_retained=subretained,existing_sub_cash=subcash,existing_sub_declared=subdeclared,existing_sub_received=subreceived,N_declared=nd,N_received=nreceived,N_receivable=nreceivable,parent_call=parent_call,dividend=dividend,general_debt=debt,project_debt=projectdebt,cash=cash+subcash+projectcash,old_capital_payable_payment=oldpay))
 return dict(projects=projects,rows=rows)

def acquisition_value(params,asof=2026,actual=None):
 a=acquisition(SC['central'] if asof!=2026 and params in [SC['core_low'],SC['core_high']] else params);r=params['rate'];rows=a['rows']
 ev=sum(x['existing_fcff']/(1+r)**(x['year']-asof) for x in rows if x['year']>asof)
 ev+=sum(x['fcff']/(1+r)**(x['year']-asof) for z in a['projects'].values() for x in z['rows'] if x['year']>asof)
 if asof==2026:
  equity=ev-ACQ['old_debt']+ACQ['cash']-.1-ACQ['old_capital_payable']-ACQ['price']/(1+r)
 else:
  row=actual[-1] if actual else next(x for x in rows if x['year']==asof)
  equity=ev-row['general_debt']-row['project_debt']+row['cash']-.1
 return dict(net_increment=equity,enterprise=ev,rows=rows,projects=a['projects'])

def holder_cash_diagnostic(scenario='central', renewable_cash=0., investor_share=0., acquire=True, years=5):
 c=SC[scenario];b=bundle(scenario);pdebt=old['PD'];sdebt=old['D']-pdebt
 pcash=old['FACT']['parent_cce'];scash=old['FACT']['cash_equivalents']-pcash;last_project_cash=0.;last_project_debt=0.
 retained=old['FACT']['parent_retained'];reserve=old['FACT']['parent_reserve'];receivable=.45110034756;rows=[]
 target=acquisition(c) if acquire else None
 mature_sub_retained=0.;mature_sub_reserve=0.
 for t in range(years):
  year=2027+t;infl=1.005**t;tax=.15 if year<=2030 else .25
  ar=target['rows'][t] if acquire else dict(parent_call=0.,dividend=0.,statutory_profit=0.,consolidated_profit=0.,general_debt=0.,project_debt=0.,cash=0.)
  acq_payment=ACQ['price'] if acquire and t==0 else 0.
  acq_loan=.8*acq_payment
  w=c.get('mature_water',[1]*5)[min(t,4)];pf=c.get('mature_price',1);cf=c.get('mature_cost',1)
  pp=(19.3*w*pf-4.9*cf-5.3)*infl-pdebt*c['loan'];pp-=max(0,pp)*tax
  sp=(7.9*w*pf-1.3*cf-2.2)*infl-sdebt*c['loan'];sp-=max(0,sp)*tax
  project={n:next(x for x in z['rows'] if x['year']==year) for n,z in b['projects'].items()}
  gs={k:project['GS'][k]+project['GLB'][k] for k in ['equity_call','dividend','statutory_profit','da']};subprojects=[x for n,x in project.items() if n not in ('GS','GLB')]
  required_sub_capital=sum(x['equity_call'] for x in subprojects)
  gx_minority_call=.11*project['GX']['equity_call'];gx_minority_div=.11*project['GX']['dividend'];gx_minority_profit=.11*project['GX']['statutory_profit']
  upper_names=('RM','BDa','GX','BDuo')
  upper_calls=sum(project[n]['equity_call'] for n in upper_names)-gx_minority_call
  upper_div=sum(project[n]['dividend'] for n in upper_names)-gx_minority_div
  upper_profit=sum(project[n]['statutory_profit'] for n in upper_names)-gx_minority_profit
  # Explicit incremental capital raise at book pre-money, not claimed transaction pricing.
  upfront=(2.9064947*investor_share/(1-investor_share)) if investor_share and t==0 else 0.
  assert upfront<=upper_calls+1e-9
  external_capital=gx_minority_call+investor_share*upper_calls+(1-investor_share)*upfront
  support=required_sub_capital-external_capital
  new_sub_declared=sum(x['dividend'] for x in subprojects)-gx_minority_div-investor_share*upper_div
  suballoc=max(0,sp+min(0,mature_sub_retained))*.1;mature_sub_reserve+=suballoc
  mature_sub_retained+=sp-suballoc
  mature_declared=min(max(0,.3*.72*sp),max(0,.72*mature_sub_retained))
  nci_paid=min(max(0,.28*sp*.5),max(0,.28*mature_sub_retained))
  mature_sub_retained-=mature_declared+nci_paid
  assert mature_sub_retained>=-1e-9
  declared=mature_declared+new_sub_declared
  mature_received=receivable+.8*mature_declared
  received=mature_received+new_sub_declared;receivable=.2*mature_declared
  project_gs_cash=gs['statutory_profit']+gs['da']-old['FACT'].get('unused',0)
  # direct project cash is revenue - opex - cash interest - taxes - engineering - maintenance + loans - repayments.
  # Using project equity call/dividend/end cash change is exactly its external residual.
  direct_net=gs['dividend']-gs['equity_call']
  # Project retained cash stays at project; not also placed in parent cash.
  statutory=pp+gs['statutory_profit']+declared+.3+ar['dividend']
  alloc=legal_reserve_appropriation(statutory,retained,reserve,S);reserve+=alloc
  legal=max(0,retained+statutory-alloc-old['PERP']*.025)
  common=pp+.72*sp+gs['statutory_profit']+sum(x['statutory_profit'] for x in subprojects)-gx_minority_profit-investor_share*upper_profit+.3-old['PERP']*.025+ar['consolidated_profit']
  intended=min((.205*S if t==0 else max(0,rows[-1]['common_earnings']*.45)),legal)
  p_before=pcash;s_before=scash;pold=pdebt;sold=sdebt
  pcash+=received+.3-old['PERP']*.025-support+direct_net+ar['dividend']-ar['parent_call']-acq_payment+acq_loan
  paid,pnet,pcash=old['funding_step'](pcash,pp,5.3*infl,2.8*infl+(2./3+old['mature']()['capital_creditor_ceiling']*.4/3 if t<3 else 0),intended,.6,c.get('parent_credit',7.))
  # New subsidiary distributions originate at project, so only mature received is paid here.
  _,snet,scash=old['funding_step'](scash,sp,2.2*infl,1.2*infl+renewable_cash+(old['mature']()['capital_creditor_ceiling']*.6/3 if t<3 else 0),mature_received+nci_paid,2.5,15.)
  pdebt+=pnet+acq_loan;sdebt+=snet;retained+=statutory-alloc-old['PERP']*.025-paid
  newdebt=sum(x['debt'] for x in project.values())
  project_cash=sum(x['cash'] for x in project.values())
  # Central five-year horizon has no project commissioning; exact consolidated conservation.
  project_profit=sum(x['statutory_profit'] for x in project.values());project_da=sum(x['da'] for x in project.values())
  project_maintenance=sum(FACTS[n]['gw']*(.035 if FACTS[n].get('solar') else .12)*(0 if year<b['projects'][n]['first_power'] else (.5 if year==b['projects'][n]['first_power'] else 1.)) for n in project)
  extra=(2./3+old['mature']()['capital_creditor_ceiling']/3) if t<3 else 0.
  predicted=p_before+s_before+last_project_cash+pp+sp+project_profit+.3-old['PERP']*.025+7.5*infl+project_da-4*infl-project_maintenance-renewable_cash-extra-sum(x['engineering_cash']+x['capitalized_interest'] for x in project.values())-paid-nci_paid+pnet+snet+(newdebt-last_project_debt)+external_capital-investor_share*upper_div-gx_minority_div
  assert abs(predicted+ar['dividend']-ar['parent_call']-acq_payment+acq_loan-pcash-scash-project_cash)<1e-8
  last_project_cash=project_cash;last_project_debt=newdebt
  rows.append(dict(year=year,common_earnings=common,parent_statutory_profit=statutory,parent_legal_reserve=alloc,parent_retained=retained,parent_capital_call=support+gs['equity_call'],upper_sub_capital_call=support,external_project_capital=external_capital,GS_direct_capital_call=gs['equity_call'],ordinary_distribution=paid,distribution_per_share=paid/S,parent_new_general_debt=pnet,mature_sub_new_debt=snet,project_debt=newdebt,group_debt=pdebt+sdebt+newdebt,target_general_debt=ar['general_debt'],target_project_debt=ar['project_debt'],target_cash=ar['cash'],target_parent_support=ar['parent_call'],target_dividend=ar['dividend'],acquisition_payment=acq_payment,acquisition_loan=acq_loan,parent_cash=pcash,mature_sub_cash=scash,mature_sub_retained=mature_sub_retained,mature_sub_reserve=mature_sub_reserve,mature_sub_declared=mature_declared,mature_sub_received=mature_received,project_cash=project_cash,engineering_cash=sum(x['engineering_cash'] for x in project.values()),capitalized_interest=sum(x['capitalized_interest'] for x in project.values()),other_newenergy_cash=renewable_cash,maintenance=4*infl))
 return rows

def valuation(name,asof_year=2026,financing_rows=None,acquire=True,upper_share=0.,upper_old_external_debt=0.):
 c=SC[name];b=bundle(name);r=c['rate'];m=b['mature'];shift=asof_year-2026
 operating=sum(x['fcff']/(1+r)**(x['year']-asof_year) for x in m['rows'] if x['year']>asof_year)
 forward_projects=bundle('central')['projects'] if shift and name in ('core_low','core_high') else b['projects']
 projects=sum(x['fcff']/(1+r)**(x['year']-asof_year) for z in forward_projects.values() for x in z['rows'] if x['year']>asof_year)
 # 27e8 kWh existing downstream increment only. Do not count new GS/GX/BDuo compensation twice.
 comp=sum(2.7*.22*.75/(1+r)**(y-asof_year) for y in range(2035,2078) if y>asof_year)
 legacy=sum((2./3)/(1+r)**(y-asof_year) for y in range(2027,2030) if y>asof_year)
 if shift==0:
  debt=old['D'];cash=old['FACT']['cash_equivalents'];old_creditor=m['capital_creditor_ceiling'];nci=m['nci_value']
 else:
  row=next(x for x in financing_rows if x['year']==asof_year);debt=row['group_debt'];cash=row['parent_cash']+row['mature_sub_cash']+row['project_cash'];old_creditor=0.;nci=old['annuity'](.8,.075,25)
 acq=acquisition_value(c,asof_year)['net_increment'] if acquire else 0.
 gx=forward_projects['GX'];ke=r+.02
 gx_claim=.11*(sum((x['dividend']-x['equity_call'])/(1+ke)**(x['year']-asof_year) for x in gx['rows'] if x['year']>asof_year)+(gx['rows'][-1]['cash']-gx['rows'][-1]['debt'])/(1+ke)**(gx['rows'][-1]['year']-asof_year))
 upper_claim=0.;raise_value=0.
 if upper_share:
  for n in ('RM','BDa','GX','BDuo'):
   z=forward_projects[n];ownership=.89 if n=='GX' else 1.
   claim=sum((x['dividend']-x['equity_call'])/(1+ke)**(x['year']-asof_year) for x in z['rows'] if x['year']>asof_year)+(z['rows'][-1]['cash']-z['rows'][-1]['debt'])/(1+ke)**(z['rows'][-1]['year']-asof_year)
   upper_claim+=upper_share*ownership*claim
  upper_claim-=upper_share*upper_old_external_debt
  if not shift:raise_value=(1-upper_share)*(2.9064947*upper_share/(1-upper_share))/(1+r)
 equity=operating+projects+comp+acq-gx_claim-upper_claim+raise_value-legacy-debt-old['PERP']-nci-old_creditor+cash-2.0296755+old['FACT']['financial_investments']
 return dict(per_share=equity/S,ordinary_equity=equity,acquisition_net_increment=acq,gx_minority_future_claim=gx_claim,upper_new_minority_claim=upper_claim,upper_raise_parent_value=raise_value,operating_ev=operating,project_npv=projects,existing_downstream_increment=comp,legacy_completion_reserve_pv=legacy,debt=debt,perpetual=old['PERP'],nci=nci,old_capital_creditor=old_creditor,cash=cash,necessary_cash=2.0296755,nonoperating_financial_assets=old['FACT']['financial_investments'])

def economic_scenarios():
 out={}
 for n in ['central','cyclical','structural','upside']:
  try:
   rows=holder_cash_diagnostic(n);out[n]=dict(feasible=True,rows=rows,current_value=valuation(n),terminal_equity=valuation(n,2031,rows))
  except ValueError as e:out[n]=dict(feasible=False,reason=str(e),terminal_equity=None)
 return out

def tests():
 # Formal finance function: zero opening debt, engineering100, r0 => 70 debt/30 equity.
 assert construction_finance(0,100,0)==dict(interest=0.,draw=70.,equity=30.,debt=70.)
 # Opening100, engineering0, r10%: interest=10/.965; equity=30% interest.
 t=construction_finance(100,0,.1)
 assert abs(t['interest']-10/.965)<1e-10
 assert abs(t['draw']-.7*10/.965)<1e-10
 # Central GS directproject first-year cap is explicit, not subsidiary mixed %.
 b=bundle('central');assert b['five_year_project_funding'][0]['parent_direct_GS_equity']>0
 FACTS['hand']=dict(engineering=0.,dynamic=0.,cip=0.,old_interest=0.,gw=0.)
 hand=build('hand',dict(first=[2027],life=1,finance_share=0.,cost=1.,gen=[1.],water=1.,price=[1.13],loan=0.,rate=0.),0)
 del FACTS['hand']
 assert abs(hand['fcff_npv']-.372)<1e-10 # .5 ramp*.992 sellable * (1-.25 tax)
 assert abs(hand['rows'][0]['statutory_profit']-.372)<1e-10
 assert old['funding_step'](1,3,2,6,4,0,2)==(2,2,0)
 try:old['funding_step'](1,3,2,9,0,0,2)
 except ValueError:pass
 else:raise AssertionError('zero-dividend infeasible case did not fail')
 assert len(holder_cash_diagnostic())==5
 assert abs(legal_reserve_appropriation(10,-8,0,100)-.2)<1e-12
 assert legal_reserve_appropriation(10,-12,0,100)==0.
 return 'passed: formal construction and funding hand cases; every project and target/year cash and debt invariants'

def auxiliary_earnings(name):
 v=valuation(name);k=.08 if name=='core_low' else .07
 normal=(13.5-old['D']*.026)*.75-old['PERP']*.025-.8+.3
 value=(normal/k-v['old_capital_creditor']+v['project_npv']+v['existing_downstream_increment']+v['acquisition_net_increment']-v['gx_minority_future_claim']-v['legacy_completion_reserve_pv'])/S
 return dict(normal_common_earnings=normal,equity_cost=k,per_share=value)

def sensitivities():
 out={}
 saved=FACTS['GLB']['dynamic'];FACTS['GLB']['dynamic']=6.4
 out['GLB_64bn_yuan_budget_sensitivity']=valuation('central')['per_share']
 FACTS['GLB']['dynamic']=saved
 for volume in (8.,11.):
  SC['gs_test']=copy.deepcopy(SC['central']);SC['gs_test']['gen'][1]=volume
  out['GS_generation_'+str(volume)]=valuation('gs_test')['per_share']
 del SC['gs_test']
 b=bundle('central')
 out['changdu_unassigned_max_11pct_project_claim_per_share']=max(abs(.11*b['projects'][n]['incremental_equity_pv']/S) for n in ('RM','BDa','BDuo'))
 out['target_grant_50pct_remaining_engineering_ceiling_per_share']=sum(z['remaining_engineering'] for z in acquisition(SC['central'])['projects'].values())*.5/1.055/S
 out['q3_capital_allocation_zero_to_full_cash_ceiling_per_share']=3.90031503735/S
 out['all_old_capital_creditors_operating_ceiling_per_share']=old['mature']()['capital_creditor_ceiling']/S
 out['mature_domestic_tariff_minus5pct_per_share']=(old['mature'](price=.95)['ev']-old['mature']()['ev'])/S
 upper_rows=holder_cash_diagnostic(investor_share=.35)
 out['upper35_book_raise_case']=dict(raise_cash=2.9064947*.35/.65,rows=upper_rows,current=valuation('central',upper_share=.35),year5=valuation('central',2031,upper_rows,upper_share=.35),old_external_debt_max_additional_value_per_share=.35*(19.2192021-2.9064947)/S)
 return out

if __name__=='__main__':
 base=holder_cash_diagnostic()
 out=dict(complete_valuation={n:valuation(n) for n in ['core_low','central','core_high']},terminal_year5={n:valuation(n,2031,base) for n in ['core_low','core_high']},cutoff='2026-10-26T14:00:00+08:00',unit='CNY billion; billion kWh',facts=FACTS,scenarios={n:bundle(n) for n in SC},economic_scenarios=economic_scenarios(),holder_diagnostic=holder_cash_diagnostic(),construction_funding_through_2041=holder_cash_diagnostic(years=15),construction_funding_cases={n:holder_cash_diagnostic(n,years=15) for n in ['core_low','core_high','cyclical','upside']},acquisition=acquisition_value(SC['central']),sensitivity=sensitivities(),auxiliary={n:auxiliary_earnings(n) for n in ['core_low','core_high']},acquisition_failure=dict(value=valuation('central',acquire=False),rows=holder_cash_diagnostic(acquire=False)),tests=tests())
 out['value_range']=dict(low=round(out['complete_valuation']['core_low']['per_share'],2),high=round(out['complete_valuation']['core_high']['per_share'],2),currency='CNY')
 out['return_model']=dict(schema_version=1,method='annual_common_equity_irr_v1',currency='CNY',model_as_of=out['cutoff'],base_case_distributions_per_share=[round(x['distribution_per_share'],4) for x in base],base_case_terminal_equity_value_range_per_share=dict(year_5=dict(low=round(out['terminal_year5']['core_low']['per_share'],2),high=round(out['terminal_year5']['core_high']['per_share'],2))))
 (P/'2026-Q3-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
 for n,b in out['scenarios'].items():print(n,b['fcff_npv_before_additional_compensation'],b['compensation_max_sensitivity'],b['conditional_common_before_other_projects_per_share'],b['conditional_common_full_compensation_before_other_projects_per_share'],b['five_year_project_funding'][0])
