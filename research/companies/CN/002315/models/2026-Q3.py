#!/usr/bin/env python3
"""CN002315 owner cash model. CNY million / million shares. stdlib only.
Entity allocations are explicit budget assumptions, not unpublished subsidiary accounts.
No quotation or IRR. Year 1 is next twelve months after 2026-10-26.
"""
import json, math, copy
from pathlib import Path
ASOF='2026-10-26T16:45:00+08:00'
N0=413.375586
# Financial asset bridge: CA is not cash. Reserve cash includes customer settlement excluded at outset.
BRIDGE={'cash_equivalents':727.782733,'customer_money_excluded':223.0,'noncash_deposits':713.668442,'cd_after_CA':1561.298925,'trading_assets':192.062255,'treasury':50.045760,'equities':792.818599,'other_financial':4.000974,'loans':31.117926,'associates':57.237025,'restricted_excluded':12.325576,'existing_tax_and_legacy_obligations_excluded':55.0}
# Accountable allocation budget: all group financial resources allocated, no unsupported cash upstream.
TOTAL=sum(BRIDGE[k] for k in ('cash_equivalents','noncash_deposits','cd_after_CA','trading_assets','treasury','equities','other_financial','loans','associates'))-223-12.325576-55
P_DEP=2100.; P_EQ=620.; L_DEP=220.; S_EQ=172.818599+57.237025+4.000974
S_DEP=TOTAL-500.-4.782733-P_DEP-P_EQ-L_DEP-S_EQ
SCENARIOS={
 'base':dict(mic=[1990,2150,2320,2490,2640],ai=[105,130,155,178,200],other=[230,235,240,245,250],margin=[.313,.319,.324,.328,.330],cl=[.68,.68,.68,.67,.66],subs=[-25,-18,-10,-5,0],tax=.15,cap=.018,after_growth=.06,stable=.025,exercise=True),
 'cyclical':dict(mic=[1800,1810,1950,2130,2300],ai=[90,100,115,135,155],other=[210,210,220,230,240],margin=[.275,.270,.295,.310,.320],cl=[.64,.62,.64,.65,.65],subs=[-40,-35,-20,-10,-5],tax=.17,cap=.018,after_growth=.05,stable=.02,exercise=False),
 'structural':dict(mic=[1750,1550,1400,1280,1200],ai=[80,65,55,50,45],other=[200,180,165,150,140],margin=[.23,.18,.14,.12,.10],cl=[.58,.50,.44,.40,.38],subs=[-50,-45,-35,-25,-15],tax=.20,cap=.022,after_growth=-.02,stable=0.,exercise=False),
 'optimistic':dict(mic=[2070,2340,2630,2920,3210],ai=[120,165,220,285,350],other=[240,255,270,285,300],margin=[.32,.335,.345,.355,.36],cl=[.70,.71,.71,.70,.69],subs=[-20,-10,0,8,15],tax=.15,cap=.021,after_growth=.07,stable=.03,exercise=True)}

def legal_profit(old,profit,reserve,capital):
    # Loss carryforward never reset. Reserve only on profit after fully covering old losses.
    eligible=max(0.,profit+min(old,0.))
    provision=min(.10*eligible,max(0.,.5*capital-reserve))
    return old+profit-provision,reserve+provision,provision

def cash_year(st,revenue,margin,tax,capex,da,wc,minimum,financial_interest=0.,mature=0.,sale=0.,sale_book=0.,borrow_limit=0.,desired=0.,receipt=0.,declared_income=0.,support=0.,new_equity=0.,capital_increase=0.,financial_cash=None,noncash_charge=0.):
    """Same formal earnings->capital->cash->legal distribution chain used by every case."""
    o=copy.deepcopy(st); oldcash=st['cash']; olddebt=st['debt']
    interest_cost=olddebt*.05
    operating_ebit=revenue*margin
    pretax=operating_ebit+financial_interest-interest_cost
    tax_paid=max(0.,pretax)*tax+max(0.,sale-sale_book)*.25
    # Realized investment gain/loss counted once; receipt of old dividend not new earnings.
    profit=pretax-tax_paid+(sale-sale_book)+declared_income-noncash_charge
    re,reserve,provision=legal_profit(st['re'],profit,st['reserve'],st['capital']+capital_increase)
    financial_cash=financial_interest if financial_cash is None else financial_cash
    operating_cash=operating_ebit+financial_cash-interest_cost-tax_paid+da-capex-(wc-st['wc'])
    available=oldcash+operating_cash+mature+sale+receipt+new_equity-support
    debt_draw=min(max(0.,minimum-available),max(0.,borrow_limit-olddebt))
    available+=debt_draw
    if available < minimum-1e-7: raise ValueError('financing infeasible even with zero dividend')
    repay=min(max(0.,available-minimum),olddebt+debt_draw)
    available-=repay
    payout=max(0.,min(desired,re,available-minimum))
    o.update(cash=available-payout,debt=olddebt+debt_draw-repay,re=re-payout,reserve=reserve,wc=wc,capital=st['capital']+capital_increase)
    assert o['cash']>=-1e-7 and o['re']>=min(re,0.)-1e-7
    cash_error=o['cash']-(oldcash+operating_cash+mature+sale+receipt+new_equity-support+debt_draw-repay-payout)
    assert abs(cash_error)<1e-7
    return o,dict(ebit=operating_ebit,profit=profit,tax=tax_paid,interest_cost=interest_cost,financial_interest=financial_interest,financial_cash=financial_cash,ocf_after_capex=operating_cash,delta_wc=wc-st['wc'],minimum=minimum,maturity=mature,sale=sale,receipt=receipt,declared_income=declared_income,support=support,equity_cash=new_equity,debt_draw=debt_draw,repayment=repay,distribution=payout,cash=o['cash'],debt=o['debt'],retained=o['re'],statutory=o['reserve'],reserve_charge=provision,cash_error=cash_error)

def initial():
    return dict(P=dict(cash=500.,debt=1.5,re=1300.,reserve=203.642853,capital=N0,wc=-(1229.590007+258.957197)+.07*2134.324686-.025*2134.324686),
      S=dict(cash=4.782733,debt=0.,re=-650.,reserve=0.,capital=400.,wc=0.),
      L=dict(cash=0.,debt=0.,re=35.,reserve=5.,capital=200.,wc=0.))

def run(name='base',stable=None,delay=0,margin_shift=0.,parent_cash_shift=0.,sub_upstream=False,sub_loss=-650.,deposit_shift=0.,opening_re=1300.,max_year=80,impairment_fraction=1.):
    c=copy.deepcopy(SCENARIOS[name]); stable=c['stable'] if stable is None else stable
    states=initial();states['S']['re']=sub_loss;states['P']['re']=opening_re;states['P']['cash']+=parent_cash_shift;states['S']['cash']-=parent_cash_shift
    if min(v['cash'] for v in states.values())<0:raise ValueError('invalid allocation')
    deposits={'P':P_DEP+deposit_shift,'S':S_DEP-deposit_shift,'L':L_DEP}; eq={'P':P_EQ,'S':S_EQ};accrued={'P':0.,'S':0.,'L':0.};N=N0;cum_dps=0.;rows=[];receivable=0.;s_receivable=0.;loan_receivable=0.; cumulative_subscription=0.; incremental_investment_book=0.
    for y in range(1,max_year+1):
      if y<=5:mic=c['mic'][y-1];ai=c['ai'][y-1];other=c['other'][y-1];m=c['margin'][y-1]+margin_shift;cl=c['cl'][y-1];subprofit=c['subs'][y-1]
      else:
        gy=stable+(c['after_growth']-stable)*max(0.,(10-y)/5)
        mic*=1+gy;ai*=1+gy;other*=1+gy
        # Post-year5 cash budgets retain each scenario's competitive economics.
        subprofit=(c['subs'][-1] if name=='structural' else max(c['subs'][-1],4.))*((1+stable)**(y-5))
      rev=mic+ai+other; prevN=N
      # Existing awards only; conditions modeled, new annual talent cost already in operating margin.
      ex=0.
      if c['exercise']:
        ex=10.329613 if y==1 else (8.156226 if y==2 else 0.)
      strike=max(0.,20.84-cum_dps);eqcash=ex*strike;N+=ex
      parent_rev=rev-other
      wc=-cl*parent_rev+.07*parent_rev-.025*parent_rev
      minimum=.30*cl*parent_rev+.12*parent_rev
      capex=c['cap']*parent_rev;da=.017*parent_rev
      # Contract source fees and recurring stock-equivalent compensation embedded in margin.
      maturityP=600. if y==1+delay else (500. if y in (2+delay,3+delay,4+delay) else 0.)
      maturityP=min(deposits['P'],maturityP)
      maturityS=deposits['S'] if y==1+delay else 0.
      maturityL=deposits['L'] if y==1 else 0.
      # Interest accrued on beginning deposits; paid only pro rata as principal matures.
      p_interest=.018*(states['P']['cash']+deposits['P'])+(.025*eq['P'])
      s_interest=.015*(states['S']['cash']+deposits['S'])
      l_interest=.018*(states['L']['cash']+deposits['L'])
      interest_cash={}
      for ent,rate,mat in [('P',.018,maturityP),('S',.015,maturityS),('L',.018,maturityL)]:
        accrued[ent]+=rate*deposits[ent]
        paid=accrued[ent]*mat/deposits[ent] if deposits[ent] else 0.
        accrued[ent]-=paid
        interest_cash[ent]=rate*states[ent]['cash']+paid
      interest_cash['P']+=.025*eq['P']
      psale=.90*eq['P'] if y==8+delay else 0.;pbook=eq['P'] if psale else 0.
      ssale=.65*eq['S'] if y==10+delay else 0.;sbook=eq['S'] if ssale else 0.
      # S is a segregated non-financial subsidiary budget envelope, NOT published entity accounts.
      # Segregated loss-repair equity subscription budget, not an intercompany loan.
      # Parent alone subscribes at par; S capital and parent's modeled ownership rise.
      # Newly funded operating losses are budgeted as unrecoverable incremental cost-method
      # investment impairment, no tax credit. This is NOT a disclosed statutory charge.
      # Zero impairment is tested; existing investment carrying cost not written off again.
      smin=20.;s_cash_pre=states['S']['cash']+subprofit+interest_cash['S']-max(0.,subprofit+s_interest)*.20+maturityS+ssale
      support=max(0.,-subprofit,smin-s_cash_pre)
      if support>60.:raise ValueError('subsidiary support budget infeasible')
      cumulative_subscription+=support
      incremental_investment_book+=support
      impairment=impairment_fraction*min(support,max(0.,-subprofit))
      incremental_investment_book-=impairment
      s_ownership=(328.+cumulative_subscription)/(400.+cumulative_subscription)
      states['S'],sr=cash_year(states['S'],1.,subprofit,.20,0.,0.,0.,smin,s_interest,maturityS,ssale,sbook,borrow_limit=0.,desired=max(0.,s_cash_pre+support-smin) if y>=10+delay and sub_upstream else 0.,new_equity=support,capital_increase=support,financial_cash=interest_cash['S'])
      # Small-loan subsidiary: 99.87% parent ownership; real capital retained, dividends from earned profit.
      # No assumption of regulatory-capital cancellation or return of original principal.
      lmin=220.;lpre=max(0.,l_interest*.75)
      ldesired=.8*lpre
      states['L'],lr=cash_year(states['L'],0.,0.,.25,0.,0.,0.,lmin,l_interest,maturityL,borrow_limit=0.,desired=ldesired,financial_cash=interest_cash['L'])
      declared=lr['distribution']*.9987+sr['distribution']*s_ownership
      received=receivable;receivable=declared
      # Parent recognizes declaration now, actual cash is received one year later.
      owner_profit_est=max(0.,parent_rev*m*(1-c['tax'])+p_interest*(1-c['tax'])+subprofit+declared)
      ordinary=.80*owner_profit_est
      # Financial principal is NOT swept into TV. Additional distributions begin year6, capped
      # at 20% of annual sales and constrained by parent accumulated statutory profit and cash.
      special_cap=.20*parent_rev if y>=6+delay else 0.
      desired=ordinary+special_cap
      states['P'],pr=cash_year(states['P'],parent_rev,m,c['tax'],capex,da,wc,minimum,p_interest,maturityP,psale,pbook,borrow_limit=100.,desired=desired,receipt=received,declared_income=declared,support=support,new_equity=eqcash,capital_increase=ex,financial_cash=interest_cash['P'],noncash_charge=impairment)
      deposits['P']-=maturityP;deposits['S']-=maturityS;deposits['L']-=maturityL
      if psale:eq['P']=0.
      if ssale:eq['S']=0.
      pr['ordinary_actual']=min(ordinary,pr['distribution'])
      pr['extra_actual']=pr['distribution']-pr['ordinary_actual']
      assert pr['extra_actual']<=max(0.,pr['retained']+pr['distribution']-pr['ordinary_actual'])+1e-8
      dps=pr['distribution']/N;cum_dps+=dps
      # Entity-level conservation; parent support and subsidiary receipt cancel exactly.
      assert abs(sr['equity_cash']-pr['support'])<1e-8
      assert abs(pr['receipt']-(rows[-1]['dividend_receivable'] if rows else 0.))<1e-8
      rows.append(dict(year=y,revenue=rev,mic=mic,ai=ai,other=other,parent_revenue=parent_rev,margin=m,cl=cl,capex=capex,da=da,shares=N,exercise=ex,exercise_price=strike,dps=dps,subsidiary_support_legal_form='parent_only_paid_in_equity',S_parent_ownership=s_ownership,cumulative_S_subscription=cumulative_subscription,P_incremental_S_investment_book=incremental_investment_book,P_budget_investment_impairment=impairment,ordinary_budget=ordinary,special_cap=special_cap,P=pr,S=sr,L=lr,deposit_remaining=copy.deepcopy(deposits),equity_remaining=copy.deepcopy(eq),dividend_receivable=receivable,deposit_interest_receivable=copy.deepcopy(accrued),states=copy.deepcopy(states)))
    return rows

def pv(rows,r,g,start=0):
    # First five-year distributions identical at both core endpoints. Future terminal at y5
    # is computed from the same fifth-year balances, with growth only changed after that date.
    cash=sum(x['dps']/(1+r)**(x['year']-start) for x in rows if x['year']>start)
    tail=rows[-1]['dps']*(1+g)/(r-g)/(1+r)**(rows[-1]['year']-start)
    return dict(value=cash+tail,tail=tail,cash=cash)

def tests():
    st=dict(cash=10.,debt=0.,re=-2.,reserve=0.,capital=100.,wc=0.)
    # Hand result: EBIT20 tax4, NI16, loss cover2, reserve1.4, legal12.6;
    # cash =10+16+2-3-1=24; min5; desired20 -> D12.6; cash11.4.
    s,x=cash_year(st,100.,.2,.2,3.,2.,1.,5.,desired=20.)
    assert abs(x['distribution']-12.6)<1e-9 and abs(s['cash']-11.4)<1e-9
    # Prior dividend receipt is cash only: no new income or statutory capacity.
    s,x=cash_year(dict(st,cash=5.,re=-20.),0.,0.,.2,0.,0.,0.,0.,receipt=7.,desired=7.)
    assert s['re']==-20 and s['cash']==12 and x['distribution']==0
    # Finite financing failure even with dividend zero.
    try:cash_year(dict(st,cash=1.),100.,-1.,.2,0.,0.,0.,0.,borrow_limit=20.)
    except ValueError:pass
    else:raise AssertionError('must fail insolvent path')
    # Interest enters earnings/cash exactly once.
    s,x=cash_year(dict(st,re=0.),0.,0.,.25,0.,0.,0.,0.,financial_interest=4.,desired=0.)
    assert abs(s['cash']-13.)<1e-9 and abs(x['profit']-3.)<1e-9
    s,x=cash_year(dict(st,re=0.),0.,0.,.25,0.,0.,0.,0.,financial_interest=4.,financial_cash=0.,desired=0.)
    assert abs(s['cash']-9.)<1e-9 and abs(x['profit']-3.)<1e-9
    s,x=cash_year(s,0.,0.,.25,0.,0.,0.,0.,financial_interest=0.,financial_cash=4.,desired=0.)
    assert abs(s['cash']-13.)<1e-9 and x['profit']==0.
    # Equity subscription must raise capital/reserve ceiling, not earnings.
    ss,xx=cash_year(dict(st,cash=100.,re=0.,reserve=50.),100.,1.,0.,0.,0.,0.,0.,new_equity=100.,capital_increase=100.)
    assert ss['capital']==200. and ss['reserve']==60. and xx['profit']==100. and ss['cash']==300.
    return ['equity_subscription_changes_reserve_ceiling','deferred_interest_not_double_profit','formal_chain_hand_example','old_dividend_no_new_profit','finite_financing_failure','interest_once','all_entity_cash_conservation']

def independent_verify(rows,r,g,claimed,start=0):
    # Independent direct loop on frozen scalar output; does not call run/pv/cash_year.
    z=0.
    for row in rows:
      if row['year']>start:z+=row['P']['distribution']/row['shares']*math.exp(-(row['year']-start)*math.log(1+r))
    z+=rows[-1]['P']['distribution']/rows[-1]['shares']*(1+g)/(r-g)*math.exp(-(len(rows)-start)*math.log(1+r))
    assert abs(z-claimed)<1e-8
    # Independently reconstruct all first-year main parameters and payment constraints.
    q=rows[0];rev=1990+105;ebit=rev*.313;fin=.018*(500+2100)+.025*620;tax=(ebit+fin-.075)*.15
    ni=ebit+fin-.075-tax+q['L']['distribution']*.9987-25
    rsv=min(.1*ni,.5*q['shares']-203.642853)
    re=1300+ni-rsv
    cash=500+ebit+(.018*500+.025*620+.018*600)-.075-tax+.017*rev-.018*rev-(q['P']['delta_wc'])+600+10.329613*20.84-q['P']['support']
    repay=min(cash-q['P']['minimum'],1.5)
    d=min(q['ordinary_budget'],re,cash-repay-q['P']['minimum'])
    assert abs(d-q['P']['distribution'])<1e-7
    return z

def independently_rebuild(r,g):
    """Second implementation from literal source/budget inputs; no formal model calls or rows.
    Rebuild P/S/L earnings, accrual/receipt, capital, borrowing, legal profit, dilution, all 80 years.
    This is deliberately verbose and uses scalar accounts to expose cross-entity mistakes.
    """
    pc,sc,lc=500.,4.782733,0.; pd,sd,ld=2100.,160.867732,220.
    pe,se=620.,234.056598; pa=sa=la=0.; debt=1.5
    pre,pres=1300.,203.642853; sre,sres=-650.,0.; s_capital=400.; lre,lres=35.,5.
    shares=413.375586; old_wc=-1488.547204+.045*2134.324686
    outstanding_dividend=0.; accumulated_dps=0.; payments=[]; rebuilt=[]
    for year in range(1,81):
      if year<=5:
        mic=[1990.,2150.,2320.,2490.,2640.][year-1]
        ai=[105.,130.,155.,178.,200.][year-1]
        other=[230.,235.,240.,245.,250.][year-1]
        margin=[.313,.319,.324,.328,.330][year-1]
        prepaid=[.68,.68,.68,.67,.66][year-1]
        subsidiary_profit=[-25.,-18.,-10.,-5.,0.][year-1]
      else:
        growth=g+(.06-g)*max(0.,(10-year)/5)
        mic=mic*(1+growth);ai=ai*(1+growth);other=other*(1+growth)
        subsidiary_profit=4.*(1+g)**(year-5)
      turnover=mic+ai
      issued=(10.329613 if year==1 else 8.156226 if year==2 else 0.)
      subscription=issued*max(0.,20.84-accumulated_dps);shares+=issued
      pm=min(pd,600. if year==1 else 500. if year in (2,3,4) else 0.)
      sm=sd if year==1 else 0.;lm=ld if year==1 else 0.
      p_fin=pc*.018+pd*.018+pe*.025;s_fin=sc*.015+sd*.015;l_fin=lc*.018+ld*.018
      pa+=pd*.018;sa+=sd*.015;la+=ld*.018
      p_coupon=pa*pm/pd if pd else 0.;s_coupon=sa*sm/sd if sd else 0.;l_coupon=la*lm/ld if ld else 0.
      pa-=p_coupon;sa-=s_coupon;la-=l_coupon
      p_fin_cash=pc*.018+pe*.025+p_coupon;s_fin_cash=sc*.015+s_coupon;l_fin_cash=lc*.018+l_coupon
      pp=pe*.90 if year==8 else 0.;pb=pe if year==8 else 0.
      sp=se*.65 if year==10 else 0.;sb=se if year==10 else 0.
      s_tax=max(0.,subsidiary_profit+s_fin)*.20+max(0.,sp-sb)*.25
      s_income=subsidiary_profit+s_fin-s_tax+sp-sb
      s_potential=sc+subsidiary_profit+s_fin_cash-s_tax+sm+sp
      parent_support=max(0.,-subsidiary_profit,20.-s_potential)
      assert parent_support<=60.
      sc=s_potential+parent_support
      s_capital+=parent_support
      s_reserve=min(.1*max(0.,s_income+min(sre,0.)),max(0.,.5*s_capital-sres))
      sre+=s_income-s_reserve;sres+=s_reserve
      # No S upstream; no positive/negative sub income can be pooled into P statutory balance.
      l_tax=l_fin*.25;l_income=l_fin-l_tax
      l_reserve=min(.1*max(0.,l_income+min(lre,0.)),max(0.,100.-lres))
      lre+=l_income-l_reserve;lres+=l_reserve
      l_before=lc+l_fin_cash-l_tax+lm
      ld_cash=min(.8*l_income,max(0.,lre),max(0.,l_before-220.))
      lc=l_before-ld_cash;lre-=ld_cash
      declaration=ld_cash*.9987
      ebit=turnover*margin;debt_interest=debt*.05
      income_tax=max(0.,ebit+p_fin-debt_interest)*.15+max(0.,pp-pb)*.25
      p_income=ebit+p_fin-debt_interest-income_tax+(pp-pb)+declaration-max(0.,-subsidiary_profit)
      p_reserve=min(.1*max(0.,p_income+min(pre,0.)),max(0.,.5*shares-pres))
      pre+=p_income-p_reserve;pres+=p_reserve
      new_wc=(-prepaid+.045)*turnover
      required=(.3*prepaid+.12)*turnover
      available=pc+ebit+p_fin_cash-debt_interest-income_tax+.017*turnover-.018*turnover-new_wc+old_wc+pm+pp+outstanding_dividend+subscription-parent_support
      draw=min(max(0.,required-available),max(0.,100.-debt));available+=draw
      assert available>=required-1e-7
      repaid=min(max(0.,available-required),debt+draw);available-=repaid;debt+=draw-repaid
      normal=.8*max(0.,ebit*.85+p_fin*.85+subsidiary_profit+declaration)
      extra=.2*turnover if year>=6 else 0.
      distribution=max(0.,min(normal+extra,pre,available-required))
      pre-=distribution;pc=available-distribution
      per_share=distribution/shares;payments.append(per_share);accumulated_dps+=per_share
      outstanding_dividend=declaration;old_wc=new_wc
      pd-=pm;sd-=sm;ld-=lm
      if year==8:pe=0.
      if year==10:se=0.
      rebuilt.append(dict(year=year,P_cash=pc,S_cash=sc,L_cash=lc,P_retained=pre,S_retained=sre,S_capital=s_capital,S_reserve=sres,L_retained=lre,shares=shares,dividend=per_share))
    current=sum(payment*math.pow(1+r,-i) for i,payment in enumerate(payments,1))
    current+=payments[-1]*(1+g)/(r-g)*math.pow(1+r,-80)
    future=sum(payments[i-1]*math.pow(1+r,-(i-5)) for i in range(6,81))
    future+=payments[-1]*(1+g)/(r-g)*math.pow(1+r,-75)
    return {'current':current,'TV5':future,'first5':rebuilt[:5],'last':rebuilt[-1],'annual_trace':rebuilt}

def main():
    out={'asof':ASOF,'units':'CNY million; shares million','financial_bridge':BRIDGE,'net_financial_assets_budget':TOTAL,'sub_deposits_budget':S_DEP,'tests':tests(),'scenarios':{}}
    for name,c in SCENARIOS.items():
      if name=='base': endpoints=[(.105,.02),(.095,.03)]
      elif name=='structural':endpoints=[(.13,0.),(.115,0.)]
      elif name=='cyclical':endpoints=[(.115,.015),(.105,.025)]
      else:endpoints=[(.10,.025),(.09,.035)]
      vals=[]
      # The first five years do not depend on long-run g.
      for r,g in endpoints:
        rows=run(name,stable=g);v=pv(rows,r,g);tv=pv(rows,r,g,5)
        if name=='base': independent_verify(rows,r,g,v['value'])
        vals.append(dict(r=r,g=g,current=v['value'],year5=tv['value'],year5_pv_share=tv['value']/(1+r)**5/v['value'],year80_tail=v['tail'],first5=rows[:5],release_years=rows[5:16],last=rows[-1],annual_trace=rows))
      assert [x['dps'] for x in vals[0]['first5']]==[x['dps'] for x in vals[1]['first5']]
      out['scenarios'][name]=vals
    b=out['scenarios']['base'];out['core_value']={'low':round(b[0]['current'],2),'high':round(b[1]['current'],2)}
    out['return_model']={'schema_version':1,'method':'annual_common_equity_irr_v1','currency':'CNY','model_as_of':ASOF,'base_case_distributions_per_share':[round(x['dps'],6) for x in b[0]['first5']],'base_case_terminal_equity_value_range_per_share':{'year_5':{'low':round(b[0]['year5'],2),'high':round(b[1]['year5'],2)}}}
    # Auxiliary: exact non-overlapping decomposition of holder cash. Capitalize only
    # recurring OPERATING ordinary distribution; price all other actual cash through
    # the same entity/legal bridge. No extra face-value asset add-on or arbitrary delay.
    rr=run('base',stable=.025)
    ordinary_operating=[]; residual=[]
    for row in rr:
      y=row['year']; sub=[-25,-18,-10,-5,0][y-1] if y<=5 else 4*1.025**(y-5)
      op=.8*max(0.,row['P']['ebit']*.85+sub)/row['shares']
      ordinary_operating.append(op);residual.append(row['dps']-op)
    residual_pv=sum(v/1.10**i for i,v in enumerate(residual,1))+residual[-1]*1.025/.075/1.10**80
    operating_pv=sum(v/1.10**i for i,v in enumerate(ordinary_operating,1))+ordinary_operating[-1]*1.025/.075/1.10**80
    assert abs(residual_pv+operating_pv-pv(rr,.10,.025)['value'])<1e-8
    normal_op_distribution=.8*(2095*.313*.85-25)
    out['auxiliary']={'normal_operating_distribution':normal_op_distribution,'other_actual_distribution_pv':residual_pv,'operating_distribution_pv':operating_pv,'low':normal_op_distribution*18/431.861425+residual_pv,'high':normal_op_distribution*22/431.861425+residual_pv,'note':'18-22x only operating ordinary dividend; all remaining actual payments valued through legal bridge, no independent excess-cash addition'}
    out['independent_full_rebuild']=[]
    for rate,growth in [(.105,.02),(.095,.03),(.11,.025)]:
      independent=independently_rebuild(rate,growth)
      formal=run('base',stable=growth)
      assert abs(independent['current']-pv(formal,rate,growth)['value'])<1e-7
      assert abs(independent['TV5']-pv(formal,rate,growth,5)['value'])<1e-7
      for i in range(5):
        assert abs(independent['first5'][i]['P_cash']-formal[i]['P']['cash'])<1e-7
        assert abs(independent['first5'][i]['P_retained']-formal[i]['P']['retained'])<1e-7
        assert abs(independent['first5'][i]['S_capital']-formal[i]['states']['S']['capital'])<1e-7
        assert abs(independent['first5'][i]['S_reserve']-formal[i]['S']['statutory'])<1e-7
        assert abs(independent['first5'][i]['dividend']-formal[i]['dps'])<1e-8
      for a,z in zip(independent['annual_trace'],formal):
        for label,entity,field in [('P_cash','P','cash'),('S_cash','S','cash'),('L_cash','L','cash'),('P_retained','P','retained'),('S_retained','S','retained'),('L_retained','L','retained'),('S_reserve','S','statutory')]:
          assert abs(a[label]-z[entity][field])<1e-7
        assert abs(a['S_capital']-z['states']['S']['capital'])<1e-7
        assert abs(a['dividend']-z['dps'])<1e-8
      out['independent_full_rebuild'].append({'r':rate,'g':growth,**independent})
    out['sensitivity']={}
    for label,kw in [('no_budget_investment_impairment',{'impairment_fraction':0.}),('release_delay_3',{'delay':3}),('release_delay_5',{'delay':5}),('margin_minus_1pt',{'margin_shift':-.01}),('no_S_upstream',{'sub_upstream':False}),('S_upstream_after_legal_recovery',{'sub_upstream':True}),('S_loss_zero',{'sub_loss':0.,'sub_upstream':True}),('parent_principal_minus_300',{'deposit_shift':-300.}),('parent_retained_minus_300',{'opening_re':1000.})]:
      try:
        rr=run('base',stable=.025,**kw);v=pv(rr,.10,.025);out['sensitivity'][label]={'value':v['value'],'D':[round(z['dps'],6) for z in rr[:5]],'TV5':pv(rr,.10,.025,5)['value'],'annual_trace':rr}
      except ValueError as e:out['sensitivity'][label]={'infeasible':str(e)}
    out['base_annual_trace']=run('base',stable=.025)
    # Dominant discount-rate sensitivity independently reconstructed from unchanged cash path.
    rr=run('base',stable=.025);v=pv(rr,.11,.025);independent_verify(rr,.11,.025,v['value']);out['sensitivity']['discount_11pct']={**v,'annual_trace':rr}
    out['tail_convergence']=[]
    for r,g in [(.105,.02),(.095,.03),(.10,.025)]:
      for horizon in (80,120,160):
        path=run('base',stable=g,max_year=horizon); val=pv(path,r,g)
        out['tail_convergence'].append(dict(r=r,g=g,horizon=horizon,value=val['value'],tail_pv=val['tail'],last_dps_growth=path[-1]['dps']/path[-2]['dps']-1,last_parent_retained=path[-1]['P']['retained'],annual_trace=path))
    out['unpaid_subsidiary_financial_assets_ceiling']=[]
    for year in (5,10,80):
      z=out['base_annual_trace'][year-1]
      ss=z['S']['cash']+z['deposit_remaining']['S']+z['equity_remaining']['S']+z['deposit_interest_receivable']['S']-z['S']['debt']
      ll=z['L']['cash']+z['deposit_remaining']['L']+z['deposit_interest_receivable']['L']-z['L']['debt']
      ceiling=(ss*z['S_parent_ownership']+ll*.9987)/z['shares']
      out['unpaid_subsidiary_financial_assets_ceiling'].append(dict(year=year,S_financial_assets=ss,L_financial_assets=ll,S_retained=z['S']['retained'],S_capital=z['states']['S']['capital'],S_parent_ownership=z['S_parent_ownership'],gross_owner_assets_per_share=ceiling,discounted_gross_assets_ceiling=ceiling/1.10**year,note='Inventory ceiling only, NOT incremental valuation: before operating liabilities, tax, liquidation costs, approvals and legal loss cover; L earnings already valued, liquidation would remove future earnings. S envelope does not authorize cross-entity pooling.'))
    Path(__file__).with_name('2026-Q3-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'core':out['core_value'],'return_model':out['return_model'],'auxiliary':out['auxiliary'],'sensitivities':out['sensitivity']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
