#!/usr/bin/env python3
"""Independent recovery snapshot: deterministic stdlib-only, CNY100m and shares100m.
Economic budgets are not legal certifications. No file/network/price input.
"""
import json,copy
ASOF='2026-10-27T22:00:00+00:00'
F=dict(shares=2.13998399,bank=54.358898861,parent_bank=6.7471555747,parent_cash=.5659278207,parent_retained=.3730465658,parent_reserve=1.1256183235,parent_capital=2.13998399,cb_face=13.89697,cb_book=13.963662443,nci=2.5072208398,legacy=1.480273,cash=13.2745958424,wc=36.9287744237,capital=84.6131157283)
# 10/22 cancellation completed, 10/23 announcement:214026399-28000.
# Sept face retained conservatively despite +772 October shares; <30000 yuan extra obligation.
R=[[27.5,31,17,8,8.5,16,2],[29,37,17.5,8.2,9.5,18,2.1],[30.5,42,18,8.4,10.5,20,2.2],[32,46,18.2,8.6,11.5,21.5,2.3],[33.5,49,18.3,8.8,12.5,23,2.4]]
M=[[.235,.175,.27,.41,.18,.06,.12],[.235,.185,.265,.405,.19,.075,.12],[.235,.195,.26,.4,.20,.085,.12],[.23,.20,.25,.395,.205,.095,.12],[.23,.20,.24,.39,.21,.10,.12]]
P=dict(revenue=R,margin=M,opex=[.147,.144,.141,.138,.136],capex=[8,7.8,7.3,6.8,6.4],da=[4.2,4.6,5,5.3,5.6],wc=[39,42,44.5,46.5,48],old_capital_payment=[.8957315724,0,0,0,0],quality=[.6,.1,0,0,0],tax=.25,bank_rate=.03,parent_rate=.032,interest_tax_shield=.2,financial_income=.135,portfolio=6.5,friction=.08,dill=[3.6,3.8,4,4.2,4.4],hk=[1.6,1.7,1.8,1.9,2],overseas_payout=.5,domestic=[.25,.35,.45,.55,.65],intermediate_cost=[.35]*5,intermediate_opening=0,parent_cost=[1,1.02,1.04,1.06,1.08],parent_capex=[.25]*5,parent_invest=[.6,.5,.4,.3,.2],old_div_collection=[.4039015,0,0,0,0],working_settlement=[.5,.4,.3,.2,.1],dps=[.2,.2,.25,.3,.35],nci_profit=[.43,.46,.49,.52,.55],nci_other_div=[.02,.02,.03,.03,.04],delay=0,extra_parent_payment=0,group_limit=82.77,parent_limit=30,parent_floor=.5,locked=[0]*5,locked_recovery=1,rollover=1,purpose_recovery=1,project_obligation=4.540956,project_spend=[1.8,1.5,1.240956,0,0])
# Full project cash budget. Self-funded payments are NOT disclosed; estimates are conditional.
PROJECT=dict(total=15.22,fund_budget=10.35,fund_paid=5.809044,self_budget=4.87,
 subprojects=[dict(total=8.153,fund=6.8,paid=3.277976),dict(total=6.,fund=2.75,paid=1.731),dict(total=1.067,fund=.8,paid=.800068)])
SELF_REMAIN=sum((t['total']-t['fund'])*max(0,1-t['paid']/t['fund']) for t in PROJECT['subprojects'])
P.update(project_self_remaining=SELF_REMAIN,project_fund_remaining=4.540956,project_old_overlap=0,
 project_obligation=4.540956+SELF_REMAIN,project_spend=[2.8+SELF_REMAIN*.6,1.4+SELF_REMAIN*.3,.340956+SELF_REMAIN*.1,0,0],
 project_fund_spend=[2.8,1.4,.340956,0,0],project_self_spend=[SELF_REMAIN*.6,SELF_REMAIN*.3,SELF_REMAIN*.1,0,0],temporary_draw=0)
# Construction budget delayed, not an assertion the issuer revised its Dec-2026 target.
for i in range(5):
 P['capex'][i]+=[.6,.3,.1,0,0][i]*SELF_REMAIN
 P['revenue'][i][1]=[29,34,40,46,49][i]
P['da']=[4.1,4.4,4.9,5.3,5.6]

def temporary_ledger(draw):
 # Separate purpose account: actual draw not disclosed; budget 0, stress 1.8.
 # Any drawn amount MUST be returned before project payments; no automatic netting.
 opening=1.950955
 assert 0<=draw<=min(1.8,opening)
 stages=[dict(event='opening',dedicated=opening,operating_transfer=0,outstanding=0),
 dict(event='draw',dedicated=opening-draw,operating_transfer=draw,outstanding=draw),
 dict(event='return_before_2027-10-27',dedicated=opening,operating_transfer=0,outstanding=0)]
 for a in stages:assert abs(a['dedicated']+a['operating_transfer']-opening)<1e-9
 return dict(stages=stages,mandatory_return=draw,group_cash_created=0,extra_distributable_profit=0)

def effective(face,book):
 if face==0:return 0
 lo,hi=0.,.2
 for _ in range(100):
  y=(lo+hi)/2;pv=sum(face*c/(1+y)**t for c,t in zip([.003,.006,.01,.015,1.1],[6/365,371/365,736/365,1101/365,1466/365]))
  if pv>book:lo=y
  else:hi=y
 return (lo+hi)/2

def run(p,f=F,convert=False):
 b=f['bank'];pb=f['parent_bank'];cash=f['cash'];pc=f['parent_cash'];ret=f['parent_retained'];nci=f['nci'];k=f['capital'];wc=f['wc'];cb=f['cb_book'];shares=f['shares'];mid=p['intermediate_opening'];reserve=0.;pending=0.;locked=0.;project_remaining=p['project_obligation'];dedicated=min(1.950955,max(0,f['cash']));rows=[];er=effective(f['cb_face'],cb);feasible=True
 for i in range(5):
  ob,opb,oc,opc,oret,onci,ok=b,pb,cash,pc,ret,nci,k
  project_open=project_remaining
  project_paid=min(project_remaining,p['project_spend'][i],max(0,p['capex'][i]-p['da'][i]-p['old_capital_payment'][i]));project_remaining-=project_paid
  fund_paid=min(project_paid,p.get('project_fund_spend',[0]*5)[i]);self_paid=project_paid-fund_paid
  dedicated_open=dedicated;dedicated_topup=max(0,fund_paid-dedicated);dedicated+=dedicated_topup-fund_paid
  assert abs(dedicated_open+dedicated_topup-fund_paid-dedicated)<1e-9
  rev=sum(p['revenue'][i]);gross=sum(a*m for a,m in zip(p['revenue'][i],p['margin'][i]));ebit=gross-rev*p['opex'][i];nopat=ebit-max(ebit,0)*p['tax'];dwc=p['wc'][i]-wc;wc=p['wc'][i];investment=p['capex'][i]-p['old_capital_payment'][i]-p['da'][i]+dwc;k+=investment;fcff=nopat-investment-p['old_capital_payment'][i]-p['quality'][i]
  dd=max(0,p['dill'][i])*p['overseas_payout'];hd=max(0,p['hk'][i])*p['overseas_payout'];fg=dd*.9+hd;friction=fg*p['friction'];foreign=fg-friction
  mp=foreign-p['intermediate_cost'][i];available=max(0,mid+mp);rs=min(min(max(0,mp),available)*.1,max(0,1.505-reserve));reserve+=rs;md=max(0,available-rs);mid+=mp-rs-md
  declare=md+p['domestic'][i];delayed=declare*p['delay'];received=declare-delayed+pending;pending=delayed
  payment=f['cb_face']*[.003,.006,.01,.015,1.1][i];redemption=payment if i==4 else 0
  cb_expense=(cb*(1+er)-payment*(1+er)**(1-6/365))-cb+payment if i<4 else payment-cb
  if i==4 and convert:
   shares+=f['cb_face']/(38.78-sum(x['dps'] for x in rows));payment=redemption=cb_expense=0
  interest=(ob+redemption)*p['bank_rate'];pinterest=(opb+redemption)*p['parent_rate'];profit=declare-p['parent_cost'][i]-pinterest-cb_expense;ret+=profit
  # No new parent reserve required: opening reserve already >=50% registered capital.
  parent_pre=pc+received+p['old_div_collection'][i]+p['working_settlement'][i]-p['parent_cost'][i]-pinterest-payment-p['parent_capex'][i]-p['parent_invest'][i]-(p['extra_parent_payment'] if i==0 else 0)
  nd=dd*.1+p['nci_other_div'][i];nci+=p['nci_profit'][i]-nd
  # External taxes/FX/fees are real consolidated cash outflow, not intra-group cancellation.
  group_pre=cash+fcff-(interest-p['financial_income'])*(1-p['interest_tax_shield'])-payment-nd-friction
  sub_pre=group_pre-parent_pre;locked+=p['locked'][i]
  pm=min(opb,3.7714124162 if i==0 else opb*.6);gm=min(ob,48.1334362877 if i==0 else ob*.75);sm=max(0,gm-pm)
  def finance(div):
   pd=max(-opb,p['parent_floor']-(parent_pre-div));sd=max(-(ob-opb),f['cash']-p['parent_floor']+locked-sub_pre)
   pr=max(pm,-pd);sr=max(sm,-sd);pn=pr+pd;sn=sr+sd
   short=max(0,ob+pd+sd-p['group_limit'],opb+pd-p['parent_limit'],pn+sn-(gm*p['rollover']+max(0,p['group_limit']-ob)))
   return pd,sd,pr,sr,pn,sn,short
  div=min(shares*p['dps'][i],max(0,ret-.1));fund=finance(div)
  if fund[-1]>1e-9:div=0;fund=finance(div)
  pd,sd,pr,sr,pn,sn,short=fund
  if short>1e-9:
   rows.append(dict(year=i+1,feasible=False,dps=0,required_group_bank=ob+pd+sd,required_parent_bank=opb+pd,unfunded=short,ebit=ebit,fcff=fcff,parent_pre=parent_pre,subsidiary_pre=sub_pre,foreign_friction=friction));feasible=False;break
  pb=opb+pd;b=ob+pd+sd;pc=parent_pre-div+pd;sc=sub_pre+sd;cash=pc+sc;ret-=div;cb=0 if i==4 else cb+cb_expense-payment
  assert abs(oc+fcff-(interest-p['financial_income'])*(1-p['interest_tax_shield'])-payment-nd-friction-div+(b-ob)-cash)<1e-8
  assert abs(parent_pre-div+pn-pr-pc)<1e-8 and abs(sub_pre+sn-sr-sc)<1e-8
  assert abs(oret+profit-div-ret)<1e-8 and abs(onci+p['nci_profit'][i]-nd-nci)<1e-8
  assert abs(k-ok+fcff-(nopat-p['old_capital_payment'][i]-p['quality'][i]))<1e-8
  rows.append(dict(dedicated_opening=dedicated_open,dedicated_topup_from_existing_group_pool=dedicated_topup,dedicated_fund_payment=fund_paid,dedicated_ending=dedicated,project_self_payment=self_paid,project_opening=project_open,project_fund_plan=p.get('project_fund_spend',[0]*5)[i],project_self_plan=p.get('project_self_spend',[0]*5)[i],other_growth_capex=p['capex'][i]-p['da'][i]-p['old_capital_payment'][i]-project_paid,project_spend_included_in_capex=project_paid,project_remaining=project_remaining,temporary_fund_authorized=1.8 if i==0 else 0,temporary_fund_draw_budget=p.get('temporary_draw',0) if i==0 else 0,temporary_fund_mandatory_return=p.get('temporary_draw',0) if i==0 else 0,year=i+1,feasible=True,revenue=rev,gross=gross,ebit=ebit,nopat=nopat,capex=p['capex'][i],da=p['da'][i],wc=wc,dwc=dwc,investment=investment,capital=k,roic=nopat/((ok+k)/2),fcff=fcff,foreign_gross=fg,foreign_friction=friction,foreign_net=foreign,intermediate_profit=mp,intermediate_retained=mid,intermediate_reserve=reserve,parent_declare=declare,parent_received=received,old_dividend_collection=p['old_div_collection'][i],parent_profit=profit,parent_retained=ret,parent_pre=parent_pre,subsidiary_pre=sub_pre,parent_cash=pc,subsidiary_cash=sc,cash=cash,parent_bank=pb,subsidiary_bank=b-pb,bank=b,parent_scheduled_maturity=pm,subsidiary_scheduled_maturity=sm,parent_gross_repayment=pr,subsidiary_gross_repayment=sr,parent_gross_borrowing=pn,subsidiary_gross_borrowing=sn,bank_interest=interest,parent_interest=pinterest,cb_cash=payment,cb_expense=cb_expense,cb_book=cb,nci_profit=p['nci_profit'][i],nci_dividend=nd,nci_equity=nci,locked=locked,distribution=div,dps=div/shares,shares=shares))
 return dict(feasible=feasible,rows=rows,convert=convert,cb_effective_rate=er)
def terminal(z,p,f,w,g,roi,ke,operating_value=None):
 if not z['feasible']:return None
 r=z['rows'][-1];np6=r['nopat']*(1+g);eb6=r['ebit']*(1+g);reinvest=np6*g/roi;ev=(np6-reinvest)/(w-g) if operating_value is None else operating_value
 nc=r['nci_equity']+(p['nci_profit'][-1]*(1+g)-ke*r['nci_equity'])/(ke-g)
 leakage=r['foreign_friction']*(1+g)/(ke-g);lockloss=r['locked']*(1-p['locked_recovery'])+4.540956*(1-p['purpose_recovery'])
 equity=ev+r['cash']+p['portfolio']-r['bank']-nc-f['legacy']-leakage-lockloss-r['project_remaining'];tv=max(0,equity)/r['shares'];pd=sum(t['dps']/(1+ke)**t['year'] for t in z['rows']);pt=tv/(1+ke)**5
 return dict(unpaid_project=r['project_remaining'],ev=ev,nopat6=np6,reinvestment6=reinvest,bank=r['bank'],financial_principal=r['cash']+p['portfolio'],nci=nc,legacy=f['legacy'],friction_value=leakage,locked_loss=lockloss,equity=equity,terminal_per_share=tv,current=pd+pt,pv_distribution=pd,terminal_pv_weight=pt/(pd+pt) if pd+pt else 0,parameters=dict(wacc=w,growth=g,roi=roi,ke=ke,operating_value_override=operating_value))
def auxiliary(z,p,f,w,ke,years,repair=True):
 if not z['feasible']:return None
 r=z['rows'][-1];capital=r['capital'];start_return=r['nopat']/capital;growth=.01;epv=0.;fcfpv=0.;schedule=[]
 for j in range(1,years+1):
  roc=start_return+(w-start_return)*(j-1)/years if repair else start_return
  profit=capital*roc;investment=capital*growth;cf=profit-investment;ep=profit-w*capital
  epv+=ep/(1+w)**j;fcfpv+=cf/(1+w)**j
  schedule.append(dict(year_after_5=j,opening_capital=capital,roic=roc,nopat=profit,reinvestment=investment,fcff=cf,economic_profit=ep))
  capital+=investment
 # After equipment/product renewal, normal competition gives ROIC=cost, no perpetual excess spread.
 # Continuing EV equals operating capital because NOPAT=w*K, reinvest=g*K. Not liquidation proceeds.
 terminal_roic=w if repair else start_return
 terminal_ep=(terminal_roic-w)*capital/(w-growth)/(1+w)**years
 ev=r['capital']+epv+terminal_ep;discounted_continuing=capital*(terminal_roic-growth)/(w-growth)/(1+w)**years
 assert abs(ev-fcfpv-discounted_continuing)<1e-8
 t=terminal(z,p,f,w,growth,w,ke,ev)
 # Auxiliary operating value uses the explicit finite schedule, not the main perpetuity diagnostics.
 t['nopat6']=schedule[0]['nopat'];t['reinvestment6']=schedule[0]['reinvestment']
 t['parameters'].pop('roi',None)
 t['parameters'].update(method='finite_economic_profit_with_direct_fcff_bridge',initial_roic=start_return,terminal_roic=terminal_roic,fade_years=years,repair=repair)
 t['economic_profit_bridge']=dict(opening_capital=r['capital'],initial_roic=start_return,repair=repair,terminal_roic=terminal_roic,terminal_economic_profit_pv=terminal_ep,fade_years=years,growth=growth,ep_present_value=epv,fcff_present_value=fcfpv,continuing_capital=capital,discounted_continuing_value=discounted_continuing,schedule=schedule)
 return t
def evaluate(p,f=F):
 a=run(p,f);c=run(p,f,True);ends=[]
 for w,g,k in [(.095,.015,.14),(.085,.02,.12)]:
  x=terminal(a,p,f,w,g,.11,k);y=terminal(c,p,f,w,g,.11,k)
  # A failed repayment route is not rescued by assuming voluntary conversion occurs.
  selected=min([x,y],key=lambda t:t['current']) if x is not None and y is not None else None
  ends.append(dict(repay=x,convert=y,selected=selected))
 return dict(inputs=p,repay=a,convert=c,endpoints=ends,auxiliary=[auxiliary(a,p,f,w,k,n) for w,k,n in [(.095,.14,10),(.085,.12,5)]],auxiliary_no_return_repair=[auxiliary(a,p,f,w,k,10,False) for w,k in [(.095,.14),(.085,.12)]],temporary_funds=temporary_ledger(p.get('temporary_draw',0)))
def scenarios():
 d={'base':copy.deepcopy(P)}
 q=copy.deepcopy(P)
 for i in range(5):
  factor=[.9,.93,.98,1,1][i];q['revenue'][i]=[v*factor for v in q['revenue'][i]];q['margin'][i]=[v-[.015,.01,.003,0,0][i] for v in q['margin'][i]];q['wc'][i]+=3 if i<2 else 0;q['dill'][i]*=factor;q['hk'][i]*=factor;q['domestic'][i]*=factor;q['quality'][i]+=[.3,.1,0,0,0][i]
 q.update(bank_rate=.035,delay=.25,extra_parent_payment=.5);d['cyclical']=q
 q=copy.deepcopy(P)
 for i in range(5):
  q['revenue'][i]=[v*[.92,.88,.84,.82,.8][i] for v in q['revenue'][i]];q['margin'][i]=[v-.04 for v in q['margin'][i]];q['capex'][i]=[7,6,5.5,5.2,5][i];q['dill'][i]*=.7;q['hk'][i]*=.6;q['domestic'][i]=0;q['quality'][i]+=[.7,.4,.2,.1,0][i];q['nci_profit'][i]*=.7;q['wc'][i]+=5 if i<2 else 0
 q.update(bank_rate=.045,parent_rate=.05,overseas_payout=.35,delay=.5,extra_parent_payment=1,group_limit=70);d['structural']=q
 q=copy.deepcopy(P)
 for i in range(5):
  q['revenue'][i]=[v*[1.04,1.07,1.1,1.12,1.15][i] for v in q['revenue'][i]];q['margin'][i][1]+=.02;q['margin'][i][5]+=.02;q['capex'][i]+=1;q['wc'][i]+=(i+1)*.5;q['dill'][i]*=1.1;q['hk'][i]*=1.1;q['domestic'][i]*=1.2
 d['upside']=q
 q=copy.deepcopy(P)
 for i in range(5):q['margin'][i][1]-=.01;q['domestic'][i]*=.85;q['parent_invest'][i]+=.15
 d['suspension_margin_pressure']=q
 q=copy.deepcopy(P);q.update(delay=.5,extra_parent_payment=1);d['upstream_delay']=q
 q=copy.deepcopy(q);q['intermediate_opening']=-1;d['legal_loss_rebuild']=q
 q=copy.deepcopy(P);q.update(delay=1,extra_parent_payment=1,parent_limit=10,locked=[1]*5,locked_recovery=.5,rollover=.75);d['cash_locked']=q
 q=copy.deepcopy(P);q['portfolio']-=3;d['financial_principal_loss']=q
 q=copy.deepcopy(P);q['purpose_recovery']=0;d['purpose_asset_unreleased']=q
 for name,remaining,air,da in [('project_self_paid',0,[31,37,42,46,49],[4.2,4.6,5,5.3,5.6]),('project_self_unpaid',4.87,[27,31,38,45,49],[4,4.3,4.8,5.2,5.6])]:
  q=copy.deepcopy(P);q['project_self_remaining']=remaining;q['project_obligation']=4.540956+remaining
  for i,weight in enumerate([.6,.3,.1,0,0]):
   q['capex'][i]+=(remaining-SELF_REMAIN)*weight;q['project_self_spend'][i]=remaining*weight;q['project_spend'][i]=q['project_fund_spend'][i]+remaining*weight;q['revenue'][i][1]=air[i];q['da'][i]=da[i]
  d[name]=q
 q=copy.deepcopy(P);overlap=min(.8957315724,SELF_REMAIN);q['project_old_overlap']=overlap;q['project_obligation']-=overlap;q['project_self_remaining']-=overlap
 # Existing payable already counted in old_capital_payment. No additional asset or cash charge.
 for i,weight in enumerate([.6,.3,.1,0,0]):
  q['capex'][i]-=overlap*weight;q['project_spend'][i]-=overlap*weight;q['project_self_spend'][i]-=overlap*weight
 d['project_payable_overlap']=q
 q=copy.deepcopy(P);q['temporary_draw']=1.8;d['temporary_draw_and_return']=q
 return d

def self_test():
 p=copy.deepcopy(P);f=copy.deepcopy(F)
 f.update(bank=0,parent_bank=0,parent_cash=0,parent_retained=0,cb_face=0,cb_book=0,nci=0,legacy=0,cash=0,wc=0,capital=100)
 for key in ['capex','da','wc','old_capital_payment','quality','dill','hk','domestic','intermediate_cost','parent_cost','parent_capex','parent_invest','old_div_collection','working_settlement','dps','nci_profit','nci_other_div','project_spend']:p[key]=[0]*5
 p.update(revenue=[[100]+[0]*6 for _ in range(5)],margin=[[.1]+[0]*6 for _ in range(5)],opex=[0]*5,tax=0,bank_rate=0,parent_rate=0,financial_income=0,portfolio=0,parent_floor=0,project_obligation=0)
 z=run(p,f);t=terminal(z,p,f,.1,0,.1,.1)
 assert z['rows'][-1]['cash']==50 and z['rows'][-1]['bank']==0 and t['equity']==150
 # Independent hand cases through production project + auxiliary functions.
 a=auxiliary(z,p,f,.1,.1,5);assert abs(a['ev']-100)<1e-8
 project=copy.deepcopy(p);project.update(project_obligation=6,project_spend=[6,0,0,0,0],project_fund_spend=[4,0,0,0,0],project_self_spend=[2,0,0,0,0],capex=[6,0,0,0,0])
 pz=run(project,f);pt=terminal(pz,project,f,.1,0,.1,.1)
 assert abs(pz['rows'][-1]['cash']-44)<1e-8 and pz['rows'][-1]['project_remaining']==0 and abs(pt['equity']-144)<1e-8
 assert temporary_ledger(1.8)['mandatory_return']==1.8
 p['hk']=[2]*5
 z2=run(p,f);t2=terminal(z2,p,f,.1,0,.1,.1)
 assert abs(z2['rows'][-1]['cash']-49.6)<1e-8 and abs(t2['friction_value']-.8)<1e-8 and abs(t2['equity']-148.8)<1e-8
 return dict(case='Production chain:5x10 cash+100 EV=150;second case annual HK dividend1 and8%real friction:cash49.6+EV100-terminal leakage0.8=148.8',actual_equity=t['equity'],nonzero_friction_equity=t2['equity'],nonzero_project_equity=pt['equity'],zero_spread_auxiliary_ev=a['ev'],temporary_draw_return=temporary_ledger(1.8))
if __name__=='__main__':print(json.dumps(dict(company='CN:603197',period='2026-Q3',information_cutoff=ASOF,unit='CNY 100m; shares 100m',facts=F,project_facts=PROJECT,project_self_remaining_estimate=SELF_REMAIN,self_test=self_test(),scenarios={n:evaluate(p) for n,p in scenarios().items()}),ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False))
