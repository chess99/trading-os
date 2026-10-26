"""华润江中2026Q3. 单位百万元；预算非承诺。Python标准库单文件。"""
import json, math
from pathlib import Path
S=635.588289
# Q3其他非流动资产无附注：以H1预付资本款52.410570不变作估计；±100检验。
FIN=283.2669359+422.54048033+(935.17586633-5.82521356)+(1283.83120596-52.4105701)
INVEST=94.77226667
BASE=dict(name='base', effective_year=1, growth=[0,.025,.03,.03,.025],p_profit=580.,n_profit=240., p_capex=[120,120,110,105,105],n_capex=[150,140,125,115,115],p_da=90.,n_da=75.,wc=[15,15,16,17,17],div=[.95,1,1.05,1.1,1.15],financial_release=3,margin=1.,extra_wc=0.,fund_call=24., terminal_growth=.0175,terminal_roic=.16)
SCENARIOS={
 'base':BASE,
 'cyclical':dict(BASE,name='cyclical',growth=[-.12,0,.08,.06,.03],margin=.95,extra_wc=80,div=[.70,.80,.95,1.05,1.10],effective_year=1),
 'structural':dict(BASE,name='structural',growth=[-.15,-.07,-.03,0,0],margin=.8,extra_wc=120,div=[.5,.5,.55,.6,.6],terminal_growth=0.,terminal_roic=.095,effective_year=1),
 'upside':dict(BASE,name='upside',growth=[.03,.05,.05,.04,.035],margin=1.04,extra_wc=10,div=[1,1.1,1.2,1.3,1.4],terminal_growth=.0225,terminal_roic=.18,effective_year=1)}
def pv(distributions,terminal,r):
 return sum(x/(1+r)**(i+1) for i,x in enumerate(distributions))+terminal/(1+r)**len(distributions)

def legal(profit,retained,loss,reserve,cap):
 # Statutory losses mean negative accumulated distributable retained earnings,
 # not the sum of loss-making individual years when accumulated RE remains positive.
 opening_loss=max(0.,-retained)
 available_profit=max(0.,profit-opening_loss)
 allocation=min(max(0.,cap*.5-reserve),available_profit*.1)
 new_retained=retained+profit-allocation
 return new_retained,max(0.,-new_retained),reserve+allocation,allocation

def release_bridge(last,r,g,roi,wait=1,hand=False,investment=118.77226667,fund_year=3):
 """Actual post-Y5 legal release. J cash and debt cannot be settled by other N.
 Operational terminal already includes .51*J operating FCF; debt service from that
 FCF contributes only the incremental .49 to shareholders, avoiding double count.
 """
 pfree=max(0.,last['p_cash']-(0. if hand else 300.))
 jfree=max(0.,last['jcash']-(0. if hand else 20.))
 ofree=max(0.,last['other_n_cash']-(0. if hand else 130.))
 debt=last['internal_loan']; plegal=last['p_legal']; jlegal=last['jlegal']; olegal=last['n_legal']-jlegal
 pres=last['p_reserve']; jres=last['jreserve']; ores=last['n_reserve']-jres
 opj=0. if hand else 20.*last['n_profit']/240.
 opp=last['p_profit']; opo=last['n_profit']-opj
 pv_fin=0.; records=[]; uncredited_j_operating=0.
 yield_rate=0. if hand else .015
 for t in range(1,81):
  # Interest accrues on actual segregated financial balances; no artificial capitalized loan asset.
  opening_financial_cash=pfree+jfree+ofree
  pi=pfree*yield_rate; ji=jfree*yield_rate; oi=ofree*yield_rate
  pfree+=pi; jfree+=ji; ofree+=oi
  opp*=1+g; opo*=1+g; opj*=1+g
  jint=debt*.03
  jfcf=opj*(1-g/roi)
  # J operational CF remains in operational perpetuity; only debt-driven redistribution is overlaid.
  operating_service=min(max(jfcf,0.),debt+jint)
  paid_int=min(jint,operating_service); amort=max(0.,operating_service-paid_int)
  if paid_int<jint-1e-8: return dict(feasible=False,reason='J terminal FCF cannot service internal interest')
  debt-=amort
  uncredited_j_operating+=operating_service
  pfree+=operating_service
  jlegal,_,jres,_=legal(opj-jint+ji,jlegal,0,jres,122.45)
  olegal,_,ores,_=legal(opo+oi,olegal,0,ores,277.55)
  plegal,_,pres,_=legal(opp+pi+paid_int,plegal,0,pres,S)
  # Operating terminal assumes these normal operating cash distributions actually occur.
  # Consume the same entities' legal capacity BEFORE releasing financial principal.
  p_normal=opp*(1-g/roi)
  o_normal=opo*(1-g/roi)
  j_normal=max(0.,jfcf-operating_service)
  if min(plegal-p_normal,olegal-o_normal,jlegal-j_normal)<-1e-8:
   return dict(feasible=False,reason='normal operating terminal distribution exceeds legal capacity',year_after_five=t)
  plegal-=p_normal;olegal-=o_normal;jlegal-=j_normal
  normal_sub_receipt=.51*(o_normal+j_normal)
  # Domestic subsidiary declaration recognized by P and received/paid through in the same year.
  plegal+=normal_sub_receipt
  plegal-=normal_sub_receipt
  assert min(plegal,olegal,jlegal)>=-1e-8
  # Existing J financial surplus may repay only its own debt, never an assumed group cash offset.
  j_existing=0.; odiv=0.; jdiv=0.
  if t>=wait:
   j_existing=min(jfree,debt);jfree-=j_existing;debt-=j_existing;pfree+=j_existing
   odiv=max(0.,min(ofree,olegal));ofree-=odiv;olegal-=odiv
   # Any J surplus left after debt is zero is dividend-limited by J's own retained earnings.
   jdiv=max(0.,min(jfree,jlegal)) if debt<1e-8 else 0.
   jfree-=jdiv;jlegal-=jdiv
   pfree+=.51*(odiv+jdiv);plegal+=.51*(odiv+jdiv)
  fund=investment if t==max(fund_year,wait) else 0.
  # Original fund principal is recovered as cash; no invented gain or additional retained earnings.
  pfree+=fund
  ordinary=max(0.,min(pfree,plegal)) if t>=wait else 0.
  pfree-=ordinary;plegal-=ordinary
  # The .51 J operating cash was already valued at its generation date in the
  # operating DCF, so debit that date even when the financial release is deferred.
  # uncredited_j_operating only tracks settlement, not the economic discount date.
  baseline_debit=min(uncredited_j_operating,ordinary)
  uncredited_j_operating-=baseline_debit
  increment=ordinary-.51*operating_service
  pv_fin+=increment/(1+r)**t
  assert min(pfree,jfree,ofree,debt)>=-1e-7
  assert abs((pfree+jfree+ofree)-(opening_financial_cash+pi+ji+oi+operating_service+fund-ordinary-.49*(odiv+jdiv)))<1e-7
  records.append(dict(year_after_five=t,p_normal_operating_distribution=p_normal,other_n_normal_operating_dividend=o_normal,j_normal_operating_dividend=j_normal,parent_normal_subsidiary_receipt=normal_sub_receipt,parent_normal_subsidiary_passthrough=normal_sub_receipt,p_normal_and_financial_ordinary_cash=p_normal+normal_sub_receipt+ordinary,p_financial_cash=pfree,j_financial_cash=jfree,other_n_financial_cash=ofree,j_internal_debt=debt,p_legal=plegal,j_legal=jlegal,other_n_legal=olegal,j_operating_cash=jfcf,j_operating_debt_service=operating_service,j_existing_principal_repayment=j_existing,sub_dividend=odiv+jdiv,other_n_financial_dividend=odiv,j_financial_dividend=jdiv,parent_received_dividend=.51*(odiv+jdiv),parent_received_interest=paid_int,ordinary_cash=ordinary,operating_cash_already_valued=.51*operating_service,incremental_financial_cash=increment,fund_recovery=fund))
  if t>=max(wait,fund_year) and debt<1e-8 and pfree+jfree+ofree+uncredited_j_operating<1e-7:
   # Beyond the explicit release tail, normal FCF <= profit. Remaining legal
   # reserves can be funded from retained earnings without restricting normal cash.
   if min(plegal-max(0.,S*.5-pres),olegal-max(0.,(0. if hand else 277.55*.5)-ores),jlegal-max(0.,(0. if hand else 122.45*.5)-jres)) < -1e-8:
    return dict(feasible=False,reason='steady normal distribution lacks statutory reserve capacity')
   break
 else:return dict(feasible=False,reason='post-terminal release remains unresolved',records=records)
 return dict(feasible=True,value=pv_fin,records=records,completed_after_years=t)

def model(c,r=.095,g=None,roic=None,delay=None,fin_adjust=0.,internal=400.,n_start=70.,force_profit=None):
 g=c['terminal_growth'] if g is None else g; roic=c['terminal_roic'] if roic is None else roic
 delay=c['financial_release'] if delay is None else delay
 hand=c.get('hand',False); initial=1000. if hand else FIN+fin_adjust
 if hand:n_start=0.;internal=0.
 shares=S; p=initial-n_start; n=n_start; rec=0. if hand else 163.214080; payable=internal
 # P includes wholly-owned cash; mother reserve600 prevents treating ordinary intercompany payables as free.
 p_legal=2000. if hand else 2200.; n_legal=0. if hand else 650.; p_loss=n_loss=0.; p_reserve=356.393488; n_reserve=100.
 debt=0. if hand else 50+7.78537867+2.26369971; external_minor=0. if hand else 156.785920
 pminimum=0. if hand else 900.; jminimum=0. if hand else 20.
 olegal=0. if hand else 550.; ores=0. if hand else 80.; oloss=0.
 loan=0.; jcash=0. if hand else 20.; jloss=0.; jlegal=0. if hand else 100.; jreserve=0. if hand else 20.; pp=c['p_profit']; np=c['n_profit']; rows=[]; dps=[]; mdiv=0.; extra=c['extra_wc']
 for i in range(5):
  y=i+1; pp*=1+c['growth'][i]; np*=1+c['growth'][i]
  op_p=pp*c['margin']; op_n=np*c['margin']
  if force_profit is not None: op_p,op_n=force_profit
  # Internal balance settlement; N borrower receives a ring-fenced 300 loan from P, repays old163.214.
  p0,n0=p,n
  settlement=payable if y==1 else 0.; old=rec if y==1 else 0.; new=300. if y==1 and not hand else 0.
  p+=-settlement+old-new; n+=settlement-old+new; payable-=settlement; rec-=old; loan+=new
  internal_interest=loan*.03
  # separately earned financial interest; principal excluded from operating terminal.
  ip=max(p,0)*(0. if hand else .015); inn=max(n,0)*(0. if hand else .015)
  extpay=(debt-50+external_minor) if y==1 else (50. if y==2 else 0.); extint=debt*.03 if y==1 else (1.5 if y==2 else 0.)
  if hand:extpay=extint=0.
  np_net=op_n+inn-internal_interest-extint; pp_net=op_p+ip+internal_interest
  p_legal,p_loss,p_reserve,pr=legal(pp_net,p_legal,p_loss,p_reserve,S)
  extra_now=extra if y==1 else (-extra/2 if y in [3,4] and c['name']!='structural' else 0.)
  fcp=op_p+c['p_da']-c['p_capex'][i]-.6*c['wc'][i]-.6*extra_now
  fcn=op_n+c['n_da']-c['n_capex'][i]-.4*c['wc'][i]-.4*extra_now
  p+=fcp+ip+internal_interest-(c['fund_call'] if y==1 else 0.)
  n+=fcn+inn-internal_interest-extint-extpay
  # Jisheng is separately ring-fenced: no cash from other minority subsidiaries is assumed accessible.
  jprofit=0. if hand else 20.*(op_n/240.)
  jfcf=jprofit +40.-[40,35,30,25,20][i] - (50. if c.get('j_capex_stress') and y==1 else 0.)
  if hand:jfcf=0.
  jcash+=new-old-(external_minor if y==1 else 0)+jfcf-internal_interest
  jlegal,jloss,jreserve,jalloc=legal(jprofit-internal_interest,jlegal,jloss,jreserve,122.45)
  olegal,oloss,ores,oalloc=legal(np_net-(jprofit-internal_interest),olegal,oloss,ores,277.55)
  n_legal=jlegal+olegal;n_loss=jloss+oloss;n_reserve=jreserve+ores
  topup=max(0,jminimum-jcash)
  if topup:
   if loan+topup>450 or p-topup<pminimum: return dict(feasible=False,failed_year=y,reason='Jisheng ring-fenced cash funding unavailable',zero_dividend_does_not_fix=True)
   p-=topup; n+=topup; jcash+=topup; loan+=topup
  assert jcash>=-1e-8
  # N consolidated fcf contains J capex stress; the subset cannot generate extra group income.
  if c.get('j_capex_stress') and y==1:
   n-=50.; fcn-=50.
  assert n-jcash>=-1e-8, 'Other N cash cannot fund J implicitly'
  # N dividends are genuine declaration and same-year receipt budget after all external/legacy payment.
  nd=0 if y<delay else max(0,min(.65*max(np_net,0),n-jcash-150.,n_legal-jlegal))
  n-=nd; olegal-=nd;n_legal=jlegal+olegal; p+=.51*nd; p_legal+=.51*nd; mdiv+=.49*nd
  refund=92.6531 if c.get('refund') and y==2 else 0.
  if refund: p-=refund; shares-=6.763
  target=c['div'][i]*shares; paid=max(0,min(target,p-pminimum,p_legal))
  p-=paid; p_legal-=paid
  feasible=p>=pminimum-1e-8 and n>=0 and n-jcash>=-1e-8 and n_legal>=jlegal-1e-8
  if not feasible: return dict(feasible=False,failed_year=y,p=p,n=n,zero_dividend_does_not_fix=(n<0 or p+paid<pminimum))
  assert n-jcash>=-1e-8 and n_legal-jlegal>=-1e-8
  # consolidation money identity: internal principal, interest, parent portion of dividends cancel.
  expected=p0+n0+fcp+fcn+ip+inn-extint-extpay-(c['fund_call'] if y==1 else 0)-paid-.49*nd-refund
  assert abs(p+n-expected)<1e-7
  dps.append(paid/shares)
  rows.append(dict(year=y,p_profit=op_p,n_profit=op_n,p_cash=p,n_cash=n,p_legal=p_legal,n_legal=n_legal,p_loss=p_loss,n_loss=n_loss,p_reserve=p_reserve,n_reserve=n_reserve,p_fcf=fcp,n_fcf=fcn,internal_loan=loan,jcash=jcash,other_n_cash=n-jcash,jlegal=jlegal,jloss=jloss,jreserve=jreserve,j_topup=topup,internal_interest=internal_interest,sub_declared=nd,parent_receipt=.51*nd,distribution=paid,distribution_per_share=paid/shares,shares=shares,refund=refund,financial_interest=ip+inn,minority_dividend=.49*nd))
 # The same base fifth-year cash and earnings are used for low/high terminal endpoints.
 common_op=rows[-1]['p_profit']+.51*rows[-1]['n_profit']
 op_terminal=common_op*(1+g)*(1-g/roic)/(r-g)
 # Actual legal and creditor release schedule, same Y5 base state for both endpoints.
 bridge=release_bridge(rows[-1],r,g,roic,wait=1+max(0,delay-5),hand=hand,investment=0. if hand else INVEST+c['fund_call'])
 if not bridge['feasible']:return dict(feasible=False,reason=bridge['reason'],release_bridge=bridge)
 fin_terminal=bridge['value']
 financial_common=p-300.+.51*(n-150.)+.49*loan
 terminal=(op_terminal+fin_terminal)/shares
 value=pv(dps,terminal,r)
 return dict(feasible=True,rows=rows,distributions_per_share=dps,terminal_per_share=terminal,value=value,terminal_pv_fraction=(terminal/(1+r)**5)/value,terminal_operating=op_terminal,terminal_financial=fin_terminal,common_operating_profit=common_op,financial_common_before_delay=financial_common,initial_financial=initial,release_bridge=bridge,assumptions=c,r=r,g=g,roic=roic,delay=delay)
def main():
 low=model(BASE,.10,.015,.14); high=model(BASE,.09,.02,.18); mid=model(BASE)
 # Same live valuation chain hand examples, no standalone tautology.
 assert abs(pv([1]*5,10,0)-15)<1e-12
 assert abs(pv([0,0,0,0,0],32,1)-1)<1e-12
 assert abs(pv([1,0,0,0,0],0,.1)-1/1.1)<1e-12
 # Positive retained profits do not become accumulated losses just because one year loses money.
 ret,loss,res,alloc=legal(-100,200,0,0,400)
 assert ret==100 and loss==0
 ret,loss,res,alloc=legal(40,ret,loss,res,400)
 assert ret==136 and loss==0 and alloc==4
 # A genuine negative retained balance must first be repaired before reserve allocation.
 ret,loss,res,alloc=legal(-100,0,0,0,400)
 ret,loss,res,alloc=legal(40,ret,loss,res,400)
 assert ret==-60 and loss==60 and alloc==0
 ret,loss,res,alloc=legal(100,ret,loss,res,400)
 assert ret==36 and loss==0 and alloc==4
 # Hand-calculable input enters the actual operating/capital/cash/legal/release model.
 hand=dict(BASE,hand=True,p_profit=100.,n_profit=0.,growth=[0]*5,p_da=0.,n_da=0.,p_capex=[0]*5,n_capex=[0]*5,wc=[0]*5,div=[.1]*5,fund_call=0.,terminal_growth=0.)
 h=model(hand,.1,g=0.,roic=.1)
 end=1000+5*(100-.1*S)
 expected_terminal=(100/.1+end/1.1)/S
 expected_value=sum(.1/1.1**t for t in range(1,6))+expected_terminal/1.1**5
 assert abs(h['rows'][-1]['p_cash']-end)<1e-9
 assert abs(h['rows'][-1]['p_legal']-(2000+500-.5*S))<1e-9
 assert abs(h['terminal_per_share']-expected_terminal)<1e-9 and abs(h['value']-expected_value)<1e-9
 # Profit losses survive and no payout is allowed when all liquidity buffers fail.
 failure=model(BASE,force_profit=(-2000,-2000)); assert not failure['feasible']
 blocked=release_bridge(dict(mid['rows'][-1],p_legal=-1000.),.095,.0175,.16)
 assert not blocked['feasible'] and 'normal operating' in blocked['reason']
 # Auxiliary normalized earnings capitalization explicitly derives multiple from reinvestment/risk.
 # Removes financial income; same starting common financial rights less operating reserve and obligations.
 # Auxiliary uses current assets after pro-forma settlement, not the five-year cash balance.
 # External obligations are conservatively paid immediately here; operations immediately normalize.
 aux_start=dict(p_cash=FIN-70-400+163.214080-309-24,
  n_cash=70+400-163.214080+309-(50+7.78537867+2.26369971+156.785920),
  jcash=20+309-163.214080-156.785920,
  p_legal=2200.,n_legal=650.,jlegal=100.,p_reserve=356.393488,jreserve=20.,n_reserve=100.,
  internal_loan=309.,p_profit=580.,n_profit=240.)
 aux_start['other_n_cash']=aux_start['n_cash']-aux_start['jcash']
 earnings0=580+.51*240
 auxiliary={};aux_bridges={}
 for ar,ag,ari in [(.10,.015,.14),(.09,.02,.18)]:
  ab=release_bridge(aux_start,ar,ag,ari,investment=INVEST+24,fund_year=8)
  assert ab['feasible']
  auxiliary[str(ar)]=(earnings0*(1+ag)*(1-ag/ari)/(ar-ag)+ab['value'])/S
  aux_bridges[str(ar)]=ab
 out=dict(unit='CNY million except per share',share_count_million=S,core_low=low,core_high=high,base=mid,auxiliary=auxiliary,auxiliary_financial_start=aux_start,auxiliary_bridges=aux_bridges,scenarios={k:model(v) for k,v in SCENARIOS.items()},release_tests={str(d):model(BASE,delay=d) for d in [3,5,8,10]},sensitivity={
 'r_105':model(BASE,.105),'terminal_roic_10':model(BASE,roic=.10), 'financial_minus100':model(BASE,fin_adjust=-100),'minority_internal_plus300':model(BASE,internal=700),'all_internal_minority_1000':model(BASE,internal=1000),'n_cash_plus100':model(BASE,n_start=170),'j_capex_stress':model(dict(BASE,j_capex_stress=True)),'refund_cancel':model(dict(BASE,refund=True))},hand_tests={'zero_discount':15,'terminal_only':1,'one_period':1/1.1,'funding_failure':failure,'normal_operating_legal_constraint':blocked,'statutory_examples':{'positive_RE_200_loss100_then_profit40':{'closing_RE':136,'reserve':4,'accumulated_loss':0},'negative_RE_loss100_then40_then100':{'closing_RE':36,'reserve':4,'accumulated_loss':0}},'full_model_example':dict(expected_cash=end,expected_terminal=expected_terminal,expected_value=expected_value,actual=h)},
 jis_liquidity_test={'opening':20,'new_loan':300,'old_parent_repayment':163.214080,'external_minor_repayment':156.785920,'minimum_fcf':0,'closing_before_interest':0.,'interest_budget':9.,'required_operating_fcf':9.,'comment':'requires>=9m annual Jisheng free cash; H1CFO34.41m; additional liquidity100m P earmark within900m reserve; stress capex50m causes50m extra loan, with creditor and cash carried forward'})
 data=json.dumps(out,ensure_ascii=False,indent=2)
 Path(__file__).with_name('2026-Q3-output.json').write_text(data)
 print(data)
if __name__=='__main__':main()
