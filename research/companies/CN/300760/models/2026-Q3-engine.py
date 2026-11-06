#!/usr/bin/env python3
"""Mindray independent 2026-Q3 research. Stdlib, CNY billion, anniversary years.
No input files, prices, network or third-party modules. Budgets are not legal certifications.
Full annual states through real extended tails; no terminal liquidation or perpetual shortcut.
"""
import json,sys,copy,math
ASOF='2026-10-29T11:00:00+00:00'
SHARES=1.211799431
# TTM product estimates in billions; rounding residual allocated to ex-HT emerging.
SEG=[('ivd_ex_ds',12.404,0.310,0.085,0.48),('life',9.743,0.295,0.045,0.40),('imaging',5.434,0.265,0.045,0.42),('emerging_ex_ht',3.191567,0.240,0.145,0.55),('ht',3.073502,0.350,0.18,0.45),('ds',0.700,0.060,0.07,0.65)]
# Legal entities and bounded budget pools; deepcontrol aggregates Deepcontrol and Tongsheng holding routes.
# Tongsheng LP99.88/GP0.12 capital shares do NOT prove contractual profit allocation.
# Financial portfolio placement at parent/ht is a consolidated-property collection budget, not verified legal title.
# PPA does not alter subsidiary legal profit.
HT_HELD=39541125; HT_EXTERNAL=139227286
INIT={
 'parent':dict(cash=14.060307433-1.61169324323-.47250208809-.00025,re=32.970496611-1.61169324323, reserve=.607845633,cap=1.211799431,loan=0.),
 'software':dict(cash=.30,re=.362836027,reserve=.02,cap=.04,loan=0.),
 'other_wholly_owned':dict(cash=19.304992064-14.060307433+1.61169324323-.30-1.27282871066-.20-.10,re=0.,reserve=0.,cap=3.,loan=.430130208),
 'ht':dict(cash=.11939129412,re=.05558810726,reserve=.05322155367,cap=.141529162,loan=0.),
 'ht_ops':dict(cash=1.27282871066+.497759370-.11939129412-.03-.005-.005,re=2.,reserve=0.,cap=.06,loan=0.),
 'yi':dict(cash=.03,re=-.01,reserve=0.,cap=.040135370,loan=0.),
 'hao':dict(cash=.005,re=-.024831,reserve=0.,cap=.0021,loan=0.),
 'fund':dict(cash=.005,re=0.,reserve=0.,cap=.084,loan=0.),
 'deepcontrol':dict(cash=.10,re=0.,reserve=0.,cap=1.475,loan=.08),
 'ds':dict(cash=.20,re=-.10,reserve=0.,cap=.10,loan=0.)}
# Q3 full cash not available for free distribution: restricted separate, with real returns.
RESTRICTED=.054518106; FOREIGN=.131555845
CASES={
 'core_low':dict(r=.10,margin=-.005,capmult=1.05,put=.75,mode='sales'),
 'base':dict(r=.095,margin=0.,capmult=1.,put=.65,mode='sales'),
 'core_high':dict(r=.09,margin=.005,capmult=.95,put=.55,mode='sales'),
 'capital_method':dict(r=.095,margin=0.,capmult=1.,put=.65,mode='capital'),
 'cyclical':dict(r=.095,margin=0.,capmult=1.,put=.65,mode='sales',cycle=True),
 'structural':dict(r=.105,margin=-.055,capmult=1.50,put=.90,mode='sales',structural=True),
 'upside':dict(r=.09,margin=.012,capmult=.90,put=.65,mode='sales',upside=True),
 'cash_delay':dict(r=.095,margin=0.,capmult=1.,put=.65,mode='sales',delay=True),
 'ds_high_payment':dict(r=.095,margin=0.,capmult=1.,put=1.5,mode='sales'),
 'unit_profit_down':dict(r=.095,margin=-.02,capmult=1.,put=.65,mode='sales'),
}
CASES['capital_intensity_only']=dict(CASES['base'],capmult=1.5)
CASES['ht_upstream_delay']=dict(CASES['base'],ht_delay=True)
CASES['fund_priority_high']=dict(CASES['base'],fund_rate=.08)
CASES['fund_priority_low']=dict(CASES['base'],fund_rate=.02)
for _name in ['core_low','base','core_high','capital_method','cash_delay','ds_high_payment','capital_intensity_only','ht_upstream_delay','fund_priority_high','fund_priority_low']:
    CASES[_name]['fixed_5y_cash_budget']=True

def legal_step(re,reserve,cap,profit):
    """Loss repair precedes reserve. Negative RE is never erased."""
    repaired=min(max(profit,0),max(-re,0))
    eligible=max(profit-repaired,0)
    added=min(.10*eligible,max(.5*cap-reserve,0))
    return re+profit-added,reserve+added,repaired,added

def operating(c,n):
    rev=[x[1] for x in SEG]; K=[x[1]*x[4] for x in SEG]
    oldprofit=8.4; lastinvestment=1.6; built=0.; independent_capital=K[:4]
    for y in range(1,n+1):
      rows=[]
      for i,(name,start,m,g,k) in enumerate(SEG):
        # Growth fade from year 6 to 15, then 2%. Core margin fade after year 10.
        growth=g if y<=5 else g+(.02-g)*min((y-5)/10,1)
        if c.get('structural'): growth=(.005 if i<3 else .035) if y<=10 else .01
        if c.get('upside') and y<=5:growth+=.025
        prev=rev[i];rev[i]*=1+growth
        margin=m+c['margin']-(.025*min(max(y-10,0)/10,1) if i<4 else 0)
        demand=1.
        if c.get('cycle') and y<=3:demand=[.88,.93,.97][y-1]
        rr=rev[i]*demand
        ebit=rr*margin
        tax=max(ebit,0)*(.15 if i!=5 else .25)
        nopat=ebit-tax
        target=rr*k*c['capmult']+(built if i==0 else 0.)
        investment=target-K[i]
        da=rr*(.035 if i!=4 else .025)
        capex=da+max(investment,0)*.75
        wc=max(investment,0)*.25+min(investment,0)
        # Base committed build-out: additional 0.6/0.5/0.3bn, then depreciated and
        # maintained within future capital budget, no end-year miraculous release.
        extra=([.6,.5,.3][y-1] if y<=3 and i==0 else 0.)
        investment+=extra;capex+=extra;K[i]=target+extra
        if i==0:built+=extra
        rows.append(dict(name=name,revenue=rr,ebit=ebit,tax=tax,nopat=nopat,capital=K[i],depreciation=da,capex=capex,delta_wc=wc,net_investment=investment,fcf=nopat-investment))
      if c['mode']=='capital':
        # Independent existing earnings + lagged new-capital return, not a renamed DCF.
        incremental_roic=.25-.10*min(max(y-5,0)/10,1)
        if y<=15:
          coreprofit=oldprofit*1.015+lastinvestment*incremental_roic
          invest=1.6*1.05**(y-1)
        else:coreprofit=oldprofit*1.02;invest=(coreprofit-oldprofit)/.15
        oldprofit=coreprofit;lastinvestment=invest
        totalrev=sum(z['revenue'] for z in rows[:4])
        for ci,z in enumerate(rows[:4]):
          w=z['revenue']/totalrev;z['nopat']=coreprofit*w;z['tax']=z['nopat']*.15/.85;z['ebit']=z['nopat']+z['tax'];z['net_investment']=invest*w;z['capex']=z['depreciation']+.75*invest*w;z['delta_wc']=.25*invest*w;z['fcf']=z['nopat']-z['net_investment'];independent_capital[ci]+=z['net_investment'];z['capital']=independent_capital[ci]
      yield rows

def run(c,n=180):
  E=copy.deepcopy(INIT); restricted=RESTRICTED; foreign=FOREIGN
  restricted_split={'parent':RESTRICTED-.01844325524,'ht':.01844325524}
  leases=.300534930
  # Foreign cash remains in WOS cash but unavailable; it earns the same bank yield once.
  pending={k:0. for k in E}; loanface=.510130208; loanallowance=0.
  debt=.000170545; bonus=.970140639; old_cap_pay=.443090988
  dsput=.391842888; htden=HT_EXTERNAL; htheld=HT_HELD
  investments={'parent':.202798230-.168781974+.195765215-.04846995103,'ht':.13578977205+.04846995103}
  costs=copy.deepcopy(investments); invcost=20.922508412+.47250208809+.00025
  years=[]; pv=0.; terminal=0.; shares=SHARES; cumulative_ht_dps=0.
  ht_internal=.8; support_face={'yi':0.,'hao':0.}; hao_external=.030
  fund_lp=.049; fund_priority_due=0.; fund_mother_cost=.035
  target_parent={'software':'parent','other_wholly_owned':'parent','ds':'parent','ht_ops':'ht','ht':'deepcontrol','deepcontrol':'parent','fund':'ht'}
  floors0={'parent':3.,'software':.1,'other_wholly_owned':1.5,'ht':.08,'ht_ops':.34,'yi':.02,'hao':.005,'fund':.005,'deepcontrol':.02,'ds':.15}
  scale0=sum(z[1] for z in SEG);htscale0=SEG[4][1]
  previous_floor={k:v for k,v in floors0.items()}

  for y,B in enumerate(operating(c,n),1):
    begin={k:copy.deepcopy(v) for k,v in E.items()}; startcash=sum(v['cash'] for v in E.values())+restricted
    ownht=htheld/htden; ownds=.75 if y<=6 else 1.
    corep=sum(z['nopat'] for z in B[:4]); corecf=sum(z['fcf'] for z in B[:4])
    coreinv=sum(z['net_investment'] for z in B[:4])
    # Liquidity policy scales with actual operating size; no 2% minimum growing above 1% stress business.
    global_scale=sum(z['revenue'] for z in B)/scale0
    ht_scale=B[4]['revenue']/htscale0
    floors={k:v*(ht_scale if k in ['ht','ht_ops','yi','hao','fund','deepcontrol'] else global_scale) for k,v in floors0.items()}
    yp=(-.010*(1-(y-1)/10) if y<=10 else .002*(B[4]['revenue']/htscale0))
    hp=(-.020*(1-(y-1)/10) if y<=10 else .003*(B[4]['revenue']/htscale0))
    htp=c.get('ht_parent_profit_fixture',B[4]['nopat']*.08)
    op_pool=B[4]['nopat']-htp-yp-hp
    htinv=B[4]['net_investment']

    # H1 parent ex-investment income and Shenzhen software support 50/20/30 allocation.
    ops={'parent':(corep*.50,corecf*.50),'software':(corep*.20,corecf*.20),'other_wholly_owned':(corep*.30,corecf*.30),'ht':(htp,htp-htinv*.08),'ht_ops':(op_pool,op_pool-htinv*.87),'yi':(yp,yp-htinv*.02),'hao':(hp,hp-htinv*.03),'fund':(0.,0.),'deepcontrol':(-.001*global_scale,-.001*global_scale),'ds':(B[5]['nopat'],B[5]['fcf'])}
    interests={}; legalprofits={}; cashflows={}; repair={}; reserveadd={}; sales={}; salesgain={}; taxsale={}
    ext_add=0.;ext_sub=0.; received=0.; declared=0.;minority=0.;settlements={}
    # Contractual old bonus/capital payable paid without creating or deducting fresh income.
    bonuspay=min(bonus,.5) if y<=2 else bonus;bonus-=bonuspay
    cap_pay=min(old_cap_pay,.25);old_cap_pay-=cap_pay
    debtpay=debt if y==1 else 0.;debtinterest=debt*.0583;debt-=debtpay
    # Loan remains at FACE until collected. No group profit on principal collection.
    loanrepay=min(loanface,.17) if not c.get('delay') or y>3 else 0.
    loanface-=loanrepay
    dc_repay=min(E['deepcontrol']['loan'],loanrepay)
    E['deepcontrol']['loan']-=dc_repay;E['deepcontrol']['cash']-=dc_repay
    E['other_wholly_owned']['loan']-=loanrepay-dc_repay
    E['other_wholly_owned']['cash']-=loanrepay-dc_repay;E['parent']['cash']+=loanrepay
    hao_interest=hao_external*.028;hao_repaid=hao_external if y==1 else 0.;hao_external-=hao_repaid
    E['hao']['cash']-=hao_repaid+hao_interest;ext_sub+=hao_repaid+hao_interest

    # Repay legacy obligations split between actual parent and subsidiaries by observed H1 ratio.
    for name,w in [('parent',.73),('other_wholly_owned',.27)]:E[name]['cash']-=(bonuspay+cap_pay)*w
    E['ds']['cash']-=debtpay+debtinterest
    ext_sub+=bonuspay+cap_pay+debtpay+debtinterest
    legacy_misc=(.039071059+.013883531) if y==1 else 0.
    E['parent']['cash']-=.039071059 if y==1 else 0.
    E['ht']['cash']-=.013883531 if y==1 else 0.
    ext_sub+=legacy_misc
    # Treasury awards: 2.2m total budget released in years 2-5; no new issue if treasury sufficient.
    grant=.55e6 if 2<=y<=5 else 0.;grantprice=max(240.-cumulative_ht_dps,0.)
    grantcash=grant*grantprice/1e9;htden+=grant
    E['ht']['cash']+=grantcash;ext_add+=grantcash
    ownht=htheld/htden
    # Restriction rotates gradually. Replenishment tied to operating scale, not loss of value.
    release=restricted*.25; newrestricted=sum(z['revenue'] for z in B)*.0003
    rincome=restricted*.02*.85
    r_incomes={}
    for rn,rv in list(restricted_split.items()):
      rr=rv*.25;ra=newrestricted*(.34 if rn=='ht' else .66);ri=rv*.02*.85
      r_incomes[rn]=ri;restricted_split[rn]=rv+ri-rr+ra;E[rn]['cash']+=rr-ra
    restricted=sum(restricted_split.values());ext_add+=rincome
    lease_begin=leases;lease_cash=sum(z['revenue'] for z in B)*.0067
    lease_interest=lease_begin*.05;lease_principal=min(max(lease_cash-lease_interest,0),lease_begin)
    lease_new=.300534930*global_scale-(lease_begin-lease_principal);leases=lease_begin-lease_principal+lease_new
    if not c.get('delay') or y>10:foreign*=.75
    for name,(profit,fcf) in ops.items():
      x=E[name]; rate=.02;interest=max(begin[name]['cash'],0)*rate*.85
      interests[name]=interest
      sale=0.;gain=0.;stax=0.
      if y==3 and name in investments:
        gross=investments[name];fee=gross*.02;gain=gross-fee-costs[name];stax=max(gain,0)*.25;sale=gross-fee-stax;investments[name]=0.
      sales[name]=sale;salesgain[name]=gain;taxsale[name]=stax
      profit+=interest+gain-stax
      if name=='ds':profit-=debtinterest
      if name=='hao':profit-=hao_interest
      profit+=r_incomes.get(name,0.)
      legalprofits[name]=profit
      x['cash']+=fcf+interest+sale
      ext_add+=fcf+interest+sale
      cashflows[name]=fcf
    # Deferred owned dividends follow the disclosed-entity / explicitly aggregated budget routes; no fresh recipient income.
    for name in E:
      if name=='parent':continue
      due=pending[name]
      if isinstance(due,dict):
        for dest,amount in due.items():
          E[name]['cash']-=amount;E[dest]['cash']+=amount
          if dest=='parent':received+=amount
      else:
        dest=target_parent.get(name,'ht');E[name]['cash']-=due;E[dest]['cash']+=due
        if dest=='parent':received+=due
      pending[name]=0.
    putpayment=c['put'] if y==6 else 0.
    if y<=6:dsput=(c['put']/(1.05**(6-y))) if y<6 else 0.
    if putpayment:E['parent']['cash']-=putpayment;ext_sub+=putpayment;invcost+=putpayment
    # HT mother owes operating pool: repayment only if funded, face is retained otherwise.
    ht_internal_paid=min(ht_internal,.16,max(E['ht']['cash']-floors['ht'],0))
    ht_internal-=ht_internal_paid;E['ht']['cash']-=ht_internal_paid;E['ht_ops']['cash']+=ht_internal_paid
    transfers=[];support_repaid={};fund_priority_paid=0.;fund_principal_paid=0.
    # Topological declaration order. Profits flow on declarations, cash follows separately.
    for name in ['yi','hao','ht_ops','fund','ht','deepcontrol','software','other_wholly_owned','ds']:
      x=E[name]
      if name in support_face:
        repay=min(support_face[name],max(x['cash']-floors[name],0))
        support_face[name]-=repay;x['cash']-=repay;E['ht']['cash']+=repay;support_repaid[name]=repay
      if name=='fund':
        accrual=fund_lp*c.get('fund_rate',.05);fund_priority_due+=accrual;legalprofits[name]-=accrual
        fund_priority_paid=min(fund_priority_due,max(x['cash']-floors[name],0))
        fund_priority_due-=fund_priority_paid;x['cash']-=fund_priority_paid;minority+=fund_priority_paid
        if y>=10:
          fund_principal_paid=min(fund_lp,max(x['cash']-floors[name],0))
          fund_lp-=fund_principal_paid;x['cash']-=fund_principal_paid;minority+=fund_principal_paid
        x['re']+=legalprofits[name];repair[name]=min(max(legalprofits[name],0),max(-begin[name]['re'],0));reserveadd[name]=0.
      else:x['re'],x['reserve'],repair[name],reserveadd[name]=legal_step(x['re'],x['reserve'],x['cap'],legalprofits[name])
      floor=floors[name];unavailable=foreign if name=='other_wholly_owned' else 0.
      available=max(x['cash']-floor-unavailable,0.)
      payout=(.25 if name=='ht' else .65) if y<=5 else .90
      target=payout*max(legalprofits[name],0)+(.10*available if y>5 else 0.)
      if c.get('ht_delay') and y<=3 and name in ['ht_ops','yi','hao','fund']:target=0.
      if name=='fund' and (fund_lp>1e-12 or fund_priority_due>1e-12):target=0.
      dividend=min(max(x['re'],0),available,target)
      if name=='yi':routes={'ht':.533859,'fund':.192207}
      elif name=='hao':routes={'ht':.119048,'fund':.515774}
      else:routes={target_parent[name]:(ownht if name=='ht' else ownds if name=='ds' else 1.)}
      fraction=sum(routes.values());minordiv=dividend*(1-fraction);minority+=minordiv
      x['cash']-=minordiv;x['re']-=dividend;paid_now=0.;owed={}
      for dest,fraction_to in routes.items():
        owner=dividend*fraction_to
        rate=.2 if c.get('delay') and y<=3 else .9
        if c.get('ht_delay') and name in ['ht_ops','yi','hao','fund']:rate=.5
        immediate=rate*owner;x['cash']-=immediate;E[dest]['cash']+=immediate
        legalprofits[dest]+=owner;owed[dest]=owner-immediate;paid_now+=immediate
        transfers.append(dict(source=name,recipient=dest,declared=owner,paid=immediate,pending=owner-immediate))
        if dest=='parent':received+=immediate;declared+=owner
      pending[name]=owed
      settlements[name]=dict(dividend=dividend,ownership=fraction,paid_to_parent=paid_now,payable_to_parent=sum(owed.values()),paid_minorities=minordiv,unavailable=unavailable,floor=floor)
    ext_sub+=minority
    # Parent law: subsidiary DECLARATION, not collection, is income.
    # Parent declaration income has already arrived exactly once via topological routing.
    x=E['parent'];x['re'],x['reserve'],repair['parent'],reserveadd['parent']=legal_step(x['re'],x['reserve'],x['cap'],legalprofits['parent'])
    commonop=corep+(htp+op_pool+yp*.533859+hp*.119048)*ownht+B[5]['nopat']*ownds-.001*global_scale
    floor=floors['parent']
    requested=(.65 if y<=5 else .90)*commonop + (.10*max(x['cash']-floor,0) if y>5 else 0.)
    if y<=5 and c.get('fixed_5y_cash_budget'):requested=[4.5,4.9,5.3,5.7,6.1][y-1]*SHARES
    distribution=min(max(x['re'],0),max(x['cash']-floor,0),requested)
    # No dividend promise survives insolvency. Parent support only for wholly owned operating pools.
    support={}
    for name in ['software','other_wholly_owned','ds']:
      need=max(-E[name]['cash'],0.)
      if need and x['cash']-floor>=need:
        x['cash']-=need;E[name]['cash']+=need;support[name]=need;invcost+=need
      elif need: return dict(feasible=False,failed_year=y,reason='No finance at required entity; valuation stopped',years=years)
    # HT mother can fund minority operations only with an explicit priority loan claim.
    ht_support={}
    for name in ['yi','hao']:
      need=max(-E[name]['cash'],0.)
      if need:
        if E['ht']['cash']<need:
          bridge=need-E['ht']['cash']
          if E['ht_ops']['cash']-floors['ht_ops']<bridge:return dict(feasible=False,failed_year=y,reason='HT internal funding unavailable',years=years)
          E['ht_ops']['cash']-=bridge;E['ht']['cash']+=bridge;ht_internal+=bridge
        E['ht']['cash']-=need;E[name]['cash']+=need;support_face[name]+=need;ht_support[name]=need
    for name in ['ht','deepcontrol']:
      need=max(-E[name]['cash'],0.)
      if need:
        src='ht_ops' if name=='ht' else 'parent'
        if E[src]['cash']-floors[src]<need:return dict(feasible=False,failed_year=y,reason='Holding cash unavailable',years=years)
        E[src]['cash']-=need;E[name]['cash']+=need
        if name=='ht':ht_internal+=need
        else:E[name]['loan']+=need;loanface+=need
    if E['ht_ops']['cash']<0:return dict(feasible=False,failed_year=y,reason='HT operating pool unfunded',years=years)

    distribution=min(max(x['re'],0),max(x['cash']-floor,0),requested)
    x['cash']-=distribution;x['re']-=distribution;ext_sub+=distribution
    cumulative_ht_dps+=settlements['ht']['dividend']*1e9/htden
    endcash=sum(v['cash'] for v in E.values())+restricted
    residual=endcash-(startcash+ext_add-ext_sub)
    assert abs(residual)<1e-7*max(1,endcash),(y,residual)
    assert all(z['cash']>=-1e-9 for z in E.values())
    dps=distribution/shares; discounted=dps/(1+c['r'])**y;pv+=discounted
    if y>5:terminal+=dps/(1+c['r'])**(y-5)
    # Finite PPA schedule: no value is added; simply reconciliation to group accounting.
    ppa=max(0,min(.39,3.12-.39*(y-1)))
    years.append(dict(year=y,period_end=f'{2026+y}-10-29',businesses=B,entities=copy.deepcopy(E),entity_begin=begin,legal_profit=legalprofits,loss_repair=repair,reserve_added=reserveadd,interest_after_tax=interests,operating_cash=cashflows,financial_sale_proceeds=sales,financial_sale_gains=salesgain,financial_sale_tax=taxsale,settlements=settlements,declared_to_parent=declared,received_by_parent=received,dividend_receivable=sum(sum(v.values()) if isinstance(v,dict) else v for v in pending.values()),dividend_routes=transfers,pending_dividends=copy.deepcopy(pending),cash_floors=floors,ht_internal_loan_face=ht_internal,internal_claims={'ht_ops_to_ht':{'receivable':ht_internal,'payable':ht_internal},'ht_to_yi':{'receivable':support_face['yi'],'payable':support_face['yi']},'ht_to_hao':{'receivable':support_face['hao'],'payable':support_face['hao']},'parent_to_deepcontrol':{'receivable':E['deepcontrol']['loan'],'payable':E['deepcontrol']['loan']},'parent_to_other_wholly_owned':{'receivable':E['other_wholly_owned']['loan'],'payable':E['other_wholly_owned']['loan']}},ht_internal_loan_repaid=ht_internal_paid,ht_support_loan_face=copy.deepcopy(support_face),ht_support_paid=ht_support,ht_support_repaid=support_repaid,hao_external_loan_face=hao_external,hao_external_loan_paid=hao_repaid,hao_external_interest=hao_interest,fund_other_lp_face=fund_lp,fund_priority_due=fund_priority_due,fund_priority_paid=fund_priority_paid,fund_principal_paid=fund_principal_paid,fund_mother_cost=fund_mother_cost,ht_subsidiary_investment_costs={'ht_ops':1.42649005292, 'yi':.07997147962,'hao':.015,'fund':.035},deepcontrol_HT_accounting_cost_observation=7.667336744+.700038+.47250208809+.00025,fund_investment_costs={'yi':.020,'hao':.064},intercompany_loan_face=loanface,intercompany_loan_allowance=loanallowance,loan_repaid=loanrepay,bank_debt_face=debt,bank_debt_repaid=debtpay,bank_interest=debtinterest,old_bonus_remaining=bonus,old_bonus_paid=bonuspay,old_capital_payable_remaining=old_cap_pay,old_capital_payable_paid=cap_pay,restricted_cash=restricted,restricted_cash_by_entity=copy.deepcopy(restricted_split),restricted_income=rincome,lease_balance=leases,lease_new_obligations=lease_new,lease_cash_in_operating_cost=lease_cash,lease_principal_in_cost=lease_principal,lease_interest_in_cost=lease_interest,legacy_misc_paid=legacy_misc,restricted_release=release,restricted_addition=newrestricted,foreign_cash_pending_approval=foreign,ds_put_liability=dsput,ds_put_paid=putpayment,ds_ownership=ownds,ht_ownership=ownht,ht_external_shares=htden,ht_award_cash=grantcash,parent_investment_cost=invcost,parent_capital_return=0.,parent_disposal_gain=0.,parent_exit_tax=0.,support=support,common_operating_profit=commonop,common_accounting_profit_proxy=commonop-ppa*.85*ownht,ppa_amortisation=ppa,group_cash_start=startcash,external_cash_add=ext_add,external_cash_sub=ext_sub,group_cash_end=endcash,cash_residual=residual,minority_dividends=minority,requested_common_distribution=requested,common_distribution=distribution,shares=shares,distribution_per_share=dps,pv_distribution_per_share=discounted,retained_financial_assets=sum(investments.values())))
  return dict(feasible=True,parameters=c,tail_years=n,current_value=pv,year5_value=terminal,first5=[z['distribution_per_share'] for z in years[:5]],terminal_pv_fraction=terminal/(1+c['r'])**5/pv,remaining_cash_pv_per_share=years[-1]['group_cash_end']/SHARES/(1+c['r'])**n,years=years)

def tests():
  assert legal_step(-2.,0.,10.,3.)==(0.9,.1,2.,.1)
  assert legal_step(1.,5.,10.,2.)==(3.,5.,0.,0.)
  global SEG
  save_segments=SEG
  try:
    SEG=[('ivd_ex_ds',10.,.20,0.,0.)]+[(name,0.,0.,0.,0.) for name in ['life','imaging','emerging_ex_ht','ht','ds']]
    hand=list(operating(dict(CASES['base'],margin=0.),2))
    assert abs(hand[0][0]['nopat']-1.7)<1e-12
    assert abs(hand[0][0]['fcf']-1.1)<1e-12
    assert abs(hand[0][0]['capex']-.95)<1e-12
    assert abs(hand[1][0]['fcf']-1.2)<1e-12
  finally:SEG=save_segments
  z=run(CASES['base'],3);a=z['years'][0]
  # Real input counterexample: 2-point margin loss travels through earnings, tax and distributions.
  weak=run(CASES['unit_profit_down'],3)
  assert weak['years'][0]['common_operating_profit']<a['common_operating_profit']
  assert weak['first5'][0]<z['first5'][0]
  # Actual-source mother capacity, no upstream declarations: group cash cannot create legal RE.
  actual=run(dict(CASES['base'],ht_delay=True,ht_parent_profit_fixture=.08756240546),1)['years'][0]
  expected_profit=.08756240546+.11939129412*.017+.01844325524*.017
  expected_re=legal_step(.05558810726,.05322155367,.141529162,expected_profit)[0]
  assert abs(actual['legal_profit']['ht']-expected_profit)<1e-12
  assert actual['settlements']['ht']['dividend']<=expected_re+1e-12
  assert actual['settlements']['ht']['dividend']<.277341602452575
  assert not any(t['declared']>0 for t in actual['dividend_routes'] if t['recipient']=='ht')
  delayed=run(CASES['ht_upstream_delay'],6)
  assert delayed['years'][3]['settlements']['ht_ops']['dividend']>0
  captest=run(CASES['capital_intensity_only'],180)
  assert captest['current_value']<run(CASES['base'],180)['current_value']
  # Calls exact production chain with zero demand / no cash: returns infeasible not a valued negative cash.
  old=copy.deepcopy(INIT)
  try:
    for v in INIT.values():v['cash']=0
    bad=run(dict(CASES['structural'],margin=-1.),3)
    assert not bad['feasible']
  finally:INIT.clear();INIT.update(old)
  return dict(production_operating_handcase=True,loss_repair_hand_case=True,reserve_cap_hand_case=True,real_margin_counterexample=True,financing_failure_stops=True,actual_HT_parent_no_upstream_capacity=True,HT_temporary_delay_resumes=True,isolated_capital_intensity_counterexample=True)

def main():
  data={'as_of':ASOF,'currency':'CNY','unit':'billion except per-share and explicit shares','tests':tests(),'initial':INIT,'cases':{}}
  for name,c in CASES.items(): data['cases'][name]=run(c,180)
  data['extended_tail']={name:run(CASES[name],720) for name in ['core_low','base','core_high','capital_method','structural']}
  data['tail_comparison']={name:{'delta_current':data['extended_tail'][name]['current_value']-data['cases'][name]['current_value'],'delta_year5':data['extended_tail'][name]['year5_value']-data['cases'][name]['year5_value']} for name in data['extended_tail'] if data['extended_tail'][name]['feasible']}
  json.dump(data,sys.stdout,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False);print()
if __name__=='__main__':main()
