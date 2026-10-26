"""百亚股份；金额百万元，股数百万；仅标准库。运行写同目录output。"""
import json, pathlib, copy
SHARES=429.647790
PARAMS={'base': {'revenue':[3550,3760,4020,4260,4470,4649,4812,4956,5105,5258], 'ebit_margin':[.070,.080,.088,.094,.096,.096,.095,.094,.093,.092], 'capex':[140,145,150,155,160,164,168,172,177,182], 'wc_ratio':.10,'g':.02},
'cyclical':{'revenue':[3300,3510,3900,4170,4400,4576,4736,4878,5024,5175],'ebit_margin':[.025,.055,.080,.090,.096,.096,.095,.094,.093,.092],'capex':[125,130,145,150,158,162,166,170,175,180],'wc_ratio':.14,'g':.02},
'structural':{'revenue':[3200,3040,2950,2950,2970,2990,3010,3030,3050,3070],'ebit_margin':[-.025,-.01,.015,.025,.03,.03,.03,.03,.03,.03],'capex':[120]*10,'wc_ratio':.18,'g':0},
'optimistic':{'revenue':[3700,4070,4477,4870,5210,5523,5799,6031,6212,6398],'ebit_margin':[.085,.10,.112,.12,.122,.12,.118,.116,.114,.112],'capex':[155,165,180,195,205,215,225,230,235,240],'wc_ratio':.10,'g':.02}}
def discounted(flows,r,terminal=0):
 return sum(v/(1+r)**(i+1) for i,v in enumerate(flows))+terminal/(1+r)**len(flows)
def project(p, opening_cash=418.753180, parent_cash=376.877862, legal=500, reserve=171.647242, limit=100, parent_fraction=.90):
 sublegal=0.; subreserve=0.; interloan=0.
 cash=opening_cash; pcash=parent_cash; prev_rev=3559.134314; debt=0.; rows=[]; feasible=True
 prev_wc=prev_rev*.10; minimum=150
 for i,(rev,m,capex) in enumerate(zip(p['revenue'],p['ebit_margin'],p['capex'])):
  tax=.16 if i<4 else (.23 if i==4 else .25)
  op=rev*m; nopat=op-max(op,0)*tax # losses do not create immediate cash tax refund
  da=100+2*i; wc=rev*p['wc_ratio']; dwc=wc-prev_wc; buf=150*rev/3559.134314; dbuf=buf-minimum
  interest=debt*.05; fcf=nopat+da-capex-dwc-dbuf-interest
  # Cash balances below exclude committed minimum operating buffer.
  if i==0: cash-=150;pcash-=150*parent_fraction
  cash+=fcf; pcash+=parent_fraction*(fcf+interest)-interest
  internal_interest=interloan*.05
  pcash+=internal_interest # subsidiary pays; consolidated cash unchanged
  subcash=cash-pcash
  support=max(0,-subcash);pcash-=support;interloan+=support
  repayment=min(max(cash-pcash,0),interloan);pcash+=repayment;interloan-=repayment
  compensation=50/3 if i<3 else 0
  parent_profit=parent_fraction*(nopat-compensation)-interest+internal_interest
  subprofit=(1-parent_fraction)*(nopat-compensation)-internal_interest
  sr=min(max(subprofit+min(sublegal,0),0)*.1,max(20-subreserve,0))
  sublegal+=subprofit-sr;subreserve+=sr
  reserve_add=min(max(parent_profit+min(legal,0),0)*.1,max(SHARES*.5-reserve,0))
  legal+=parent_profit-reserve_add # negative balance retained, never clipped away
  reserve+=reserve_add
  need=max(0,-cash,-pcash)
  if need:
   available=max(0,limit-debt); borrowed=min(need,available); debt+=borrowed;cash+=borrowed;pcash+=borrowed
   if borrowed+1e-8<need: feasible=False
  target=max(0,.60*(nopat-compensation-interest))
  div=max(0,min(target,legal,cash,pcash)) if feasible else 0
  pre=cash;ppre=pcash; cash-=div;pcash-=div;legal-=div
  assert abs(pre-div-cash)<1e-8 and abs(ppre-div-pcash)<1e-8
  if feasible: assert min(cash,pcash,cash-pcash)>=-1e-8
  rows.append(dict(year=i+1,revenue=rev,ebit=op,tax_rate=tax,nopat=nopat,da=da,capex=capex,delta_wc=dwc,delta_buffer=dbuf,fcfe=fcf,external_interest=interest,parent_profit=parent_profit,reserve_add=reserve_add,legal_retained=legal,sub_legal_retained=sublegal,sub_reserve=subreserve,parent_reserve=reserve,parent_surplus_cash=pcash,subsidiary_surplus_cash=cash-pcash,intercompany_loan=interloan,intercompany_interest=internal_interest,intercompany_support=support,intercompany_repayment=repayment,group_surplus_cash=cash,debt=debt,dividend=div,dps=div/SHARES,feasible=feasible))
  prev_rev=rev;prev_wc=wc;minimum=buf
 return rows

def release_cash(last, r, g, annual_ni, annual_fcf, years=3):
 # All amounts are actual entity cash; internal dividends/loans cancel on consolidation.
 pcash=last['parent_surplus_cash']-last['debt']+30
 scash=last['group_surplus_cash']-last['parent_surplus_cash']
 loan=last.get('intercompany_loan',0)
 repay=min(scash,loan);scash-=repay;pcash+=repay;loan-=repay
 lp=last['legal_retained']-(37.112891-30);ls=last['sub_legal_retained'];rp=last['parent_reserve'];rs=last['sub_reserve']
 ptarget=max(pcash,0)/years;starget=max(scash,0)/years;adjustment_pv=0.;schedule=[]
 assert pcash>=-1e-8 and scash>=-1e-8
 for t in range(1,501):
  opening=pcash+scash
  ni=annual_ni*(1+g)**(t-1);regular=annual_fcf*(1+g)**(t-1)
  pcash+=.9*regular;scash+=.1*regular
  internal_interest=loan*.05;pcash+=internal_interest;scash-=internal_interest
  support=max(0,-scash);pcash-=support;scash+=support;loan+=support
  repayment=min(scash,loan);scash-=repayment;pcash+=repayment;loan-=repayment
  sp=.1*ni-internal_interest; sr=min(max(sp+min(ls,0),0)*.1,max(20-rs,0));rs+=sr;ls+=sp-sr
  # Deferred ordinary dividends remain in subsidiary cash; the same distribution
  # capacity later releases them, rather than treating delay as permanent loss.
  sub_div=min(scash,max(ls,0),.1*regular+max(starget,max(scash-.1*regular,0)/years))
  scash-=sub_div;ls-=sub_div;pcash+=sub_div
  parent_profit=.9*ni+internal_interest+sub_div
  pr=min(max(parent_profit+min(lp,0),0)*.1,max(SHARES*.5-rp,0));rp+=pr;lp+=parent_profit-pr
  holder_div=min(pcash,max(lp,0),.9*regular+sub_div+max(ptarget,max(pcash-(.9*regular+sub_div),0)/years))
  pcash-=holder_div;lp-=holder_div
  adjustment_pv+=(holder_div-regular)/(1+r)**t
  assert min(pcash,scash)>=-1e-8
  assert abs(opening+regular-holder_div-pcash-scash)<1e-7
  schedule.append(dict(year_after_10=t,opening_group_cash=opening,operating_fcfe=regular,subsidiary_new_declaration=sub_div,parent_holder_payment=holder_div,increment_vs_gordon_payment=holder_div-regular,parent_legal=lp,subsidiary_legal=ls,parent_cash=pcash,subsidiary_cash=scash,unreleased_cash=pcash+scash,intercompany_loan=loan))
  sub_next_reserve=min(max(.1*ni*(1+g)+min(ls,0),0)*.1,max(20-rs,0))
  if pcash+scash<1e-8 and .1*ni*(1+g)-sub_next_reserve+ls>=.1*regular*(1+g)-1e-8:break
 assert pcash+scash<1e-7, (pcash,scash,lp,ls)
 return adjustment_pv,schedule

def value(p,r,release_years=3):
 rows=project(p)
 if not all(x['feasible'] for x in rows): return {'feasible':False,'rows':rows}
 g=p['g']; last=rows[-1]; rev=last['revenue']*(1+g)
 # Unlevered steady cash: debt settled at year ten from cash, no perpetual interest double count.
 terminal_ni=rev*p['ebit_margin'][-1]*.75
 terminal_fcf=terminal_ni+last['da']*(1+g)-p['capex'][-1]*(1+g)-last['revenue']*p['wc_ratio']*g-150*last['revenue']/3559.134314*g
 cash_pv,schedule=release_cash(last,r,g,terminal_ni,terminal_fcf,release_years)
 tv10=terminal_fcf/(r-g)+cash_pv
 equity5=discounted([x['dividend'] for x in rows[5:]],r,tv10)
 value0=discounted([x['dividend'] for x in rows[:5]],r,equity5)/SHARES
 return dict(feasible=True,current_value=value0,year5_terminal=equity5/SHARES,terminal_pv_share=(equity5/(1+r)**5/SHARES)/value0,tail_gordon_pv_share=(terminal_fcf/(r-g))/(1+r)**10/SHARES/value0,steady_fcfe=terminal_fcf,release_schedule=schedule,year10_release_pv=cash_pv,rows=rows)
def run():
 out={'units':'CNY million; shares million','shares':SHARES,'parameters':PARAMS,'scenarios':{}}
 for name,p in PARAMS.items(): out['scenarios'][name]={str(r):value(p,r) for r in [.10,.11]}
 base=out['scenarios']['base'];out['value_range']={'low':round(base['0.11']['current_value'],2),'high':round(base['0.1']['current_value'],2)}
 out['dps']=[round(x['dps'],4) for x in base['0.1']['rows'][:5]]
 out['year5']={'low':round(base['0.11']['year5_terminal'],2),'high':round(base['0.1']['year5_terminal'],2)}
 # earnings-capitalization, normalized 25% taxation, same opening equity bridge
 out['method2']={'low':(3760*.08*.75*14+298.75318)/SHARES,'high':(4020*.088*.75*17+298.75318)/SHARES}
 s=copy.deepcopy(PARAMS['base']);s['ebit_margin']=[x-.01 for x in s['ebit_margin']];out['margin_minus_1pp']=value(s,.10)
 out['release_5years']=value(PARAMS['base'],.10,5)
 out['release_1year']=value(PARAMS['base'],.10,1)
 out['parent_fraction_70pct']=project(PARAMS['base'],parent_cash=418.753180*.7,parent_fraction=.7)
 # Same formal valuation function: constant no-reinvestment operating cash, zero cash bridge.
 assert abs(discounted([10]*5,.1,100)-100)<1e-9
 z={'revenue':[3559.134314]*10,'ebit_margin':[0]*10,'capex':[100+2*i for i in range(10)],'wc_ratio':.1,'g':0}
 zr=project(z,opening_cash=150,parent_cash=135,legal=500,limit=0)
 assert all(abs(x['fcfe'])<1e-9 and x['dividend']==0 and abs(x['group_surplus_cash'])<1e-9 for x in zr)
 p={'revenue':[100]*10,'ebit_margin':[.1]*10,'capex':[100+2*i for i in range(10)],'wc_ratio':.1,'g':0}
 rr=project(p,opening_cash=150,parent_cash=135,legal=-1000,limit=0)
 assert rr[0]['dividend']==0 and rr[0]['legal_retained'] < -1000
 assert all(x['dividend']==0 for x in project(PARAMS['structural'],opening_cash=0,parent_cash=0,legal=0,limit=0))
 assert not project(PARAMS['structural'],opening_cash=0,parent_cash=0,legal=0,limit=0)[0]['feasible']
 # Formal cash-release hand case: zero operations and 60 cash (30 parent plus
 # 30 modeled investment recovery), one-year release => PV 60/1.1.
 h={'parent_surplus_cash':30,'group_surplus_cash':30,'debt':0,'legal_retained':100,'sub_legal_retained':0,'parent_reserve':SHARES*.5,'sub_reserve':20}
 hp,hr=release_cash(h,.1,0,0,0,1)
 assert abs(hp-60/1.1)<1e-9 and abs(hr[-1]['unreleased_cash'])<1e-9
 h2=dict(h,parent_surplus_cash=0,group_surplus_cash=0,sub_legal_retained=-5)
 _,delayed=release_cash(h2,.1,0,20,10,1)
 assert abs(delayed[0]['subsidiary_cash']-1)<1e-9
 assert abs(delayed[0]['parent_holder_payment']-39)<1e-9
 assert delayed[-1]['unreleased_cash']<1e-8
 # Actual structural branch must fund subsidiary deficits via parent loans.
 assert out['scenarios']['structural']['0.1']['rows'][0]['intercompany_support']>0
 out['checks']=['formal discounted chain: five 10 cashflows plus 100 at 10%=100','negative statutory retained earnings carried','zero dividend does not cure unavailable financing','annual group parent subsidiary cash conservation', 'structural parent-to-subsidiary loan and interest tracked', 'formal release: 60 one-year cash at 10%=54.5454545', 'formal delayed legal dividend: subsidiary retains 1 in year1 then repays later']
 pathlib.Path(__file__).with_name('2026-Q3-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
 return out
if __name__=='__main__':
 o=run();print(json.dumps({k:o[k] for k in ['value_range','dps','year5','method2']},ensure_ascii=False,indent=2))
