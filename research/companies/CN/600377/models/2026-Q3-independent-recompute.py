#!/usr/bin/env python3
# No import of production functions. Independently transcribed source literals and closed-form annuities.
import json,math,subprocess,tempfile,shutil,hashlib
from pathlib import Path
from datetime import date
R=Path(__file__).resolve().parent;j=json.loads((R/'2026-Q3-output.json').read_text())
data=[(2700960892.79,855384836.49,376232401.42,15243,1,'2032-06-26'),(551384766.22,229251711.79,143144566.80,3165,1,'2032-09-30'),(339931743.92,93479074.20,36773614.54,2056,.85,'2029-09-30'),(377616267.35*1858/2177,188861393.97*1858/2177,126583291.60*1858/2177,1858,.85,'2028-09-30'),(377616267.35*319/2177,188861393.97*319/2177,126583291.60*319/2177,319,.85,'2031-10-31'),(39653824.14,34582194.95,20282275.62,228,.7,'2043-09-30'),(89311059.34,72304177.54,56011564.34,513,.51,'2045-12-31'),(58540602.78,60125927.34,28439892.61,336,.51,'2046-01-31'),(684218099.66,228282743.83,199538751.14,3827,.645,'2046-06-30')]
ans=[]
for factor,extension in [(1,0),(.9,0),(1,10)]:
 v=0
 for r,c,a,d,o,e in data:
  w=r/4869625851.68;da=a/5e8+.35906*w
  cash=(d*.000365*factor-(c/5e8-da)*(.8+.2*factor)-da-.24*w)*.75+da-.45*w
  n=(date.fromisoformat(e)-date(2026,10,27)).days/365.25+extension;whole=math.floor(n)
  v+=o*cash*((1-1.08**-whole)/.08+(n-whole)/1.08**n)
 ans.append(v)
for v,k in zip(ans,['finite_low','minus10pct','free_extension10']):assert abs(v-j[k]['asset_pv'])<1e-8
# Old appraisal FULL endpoint, explicit midpoint discount weights and source FCFF series.
cfs=[.9709698,.6308389,.7779357,.994198,1.2292371,1.2773332,1.198143,1.2515281,1.3054863,1.357729,1.0725373,1.4959654,1.5505666,1.5884043,1.6256304,1.650056,1.6752745,1.6987506,1.7216783,1.7310729,1.7303958]
app=[]
for k in [.0703,.0803]:app.append(sum(c*math.exp(-math.log1p(k)*(i+.5)) for i,c in enumerate(cfs))+.0267511/(1+k)**21-.1713209-6.3292886)
assert abs(app[0]-j['old_appraisal']['equity'])<1e-8
assert abs(app[1]-j['appraisal_rate_plus100bp']['equity'])<1e-8
# Independent first parent cash/debt endpoint: approved interim payment included.
debt=.400234444+.94572297939+3.850732815+5.96143121398+7.74408818339
pre=1.16232544068+1.75+2.1+.2+.40336137865-3.2-.075-4.95815175-2.468496275-debt*.025*.5
draw=(.4+.25*5.0377475-pre)/(1-.025*.25)
assert abs(draw-j['parent']['conditional']['rows'][0]['new_debt'])<1e-8
# Full independent TARGET conditional lifetime with literal source operating vector.
rr=[.8347178,.9865573,1.3182117,1.6284611,1.7220946,1.6203144,1.6892767,1.7578899,1.8240535,1.8835016,2.0191427,2.0720048,2.1232165,2.1746221,2.2082863,2.2461267,2.2808593,2.3158514,2.3321400,2.3360742]
cc=[.5167555,.5721463,.6912377,.8030196,.7556197,.7154970,.7497565,.7826553,.8149913,1.3029967,.8962447,.9198894,.9431964,.9649563,.9847617,1.0042013,1.0227908,1.0396023,1.0544290,1.0677206]
aa=[.3999634,.4511798,.5646252,.6708385,.6194498,.5767522,.6070248,.6358412,.6640125,.6881443,.7361373,.7553986,.7742214,.7913789,.8065986,.8212966,.8350414,.8468751,.8567337,.8650137]
ret=-.67964151799+.1743513;res=.00006495307;cash=.05;debt=5.903825;dist=[]
losses={2027:.25501091221-(.1743513-.09188183074),2028:.21484021663,2029:.18955235984}
for i,(rev,cost,amort) in enumerate(zip(rr,cc,aa)):
 ebt=rev-cost-.0035-.025*debt
 offset=0
 for deadline in sorted(losses):
  if deadline>=2027+i:
   use=min(losses[deadline],max(0,ebt-offset));losses[deadline]-=use;offset+=use
 net=ebt-.25*max(0,ebt-offset)
 for deadline in losses:
  if deadline<=2027+i:losses[deadline]=0
 legal_add=min(max(0,7.9562/2-res),max(0,net-max(0,-ret))/10)
 res+=legal_add;ret+=net-legal_add
 principal=debt/(20-i);cash+=net+amort-.0480065*1.03**i-principal;debt-=principal
 dividend=min(max(0,ret),max(0,cash-.05));ret-=dividend;cash-=dividend
 assert cash>=.05-1e-9
 dist.append(dividend)
 v=j['targets']['conditional']['rows'][i]
 assert abs(dividend-v['dividend'])<2e-8 and abs(ret-v['retained'])<2e-8
release=cash-debt-.05
full_target=sum(d/1.08**(i+1) for i,d in enumerate(dist))+release/1.08**21
full_target5=sum(d/1.08**(i-4) for i,d in enumerate(dist) if i>=5)+release/1.08**16
assert abs(full_target-j['targets']['conditional']['equity_pv_2026end'])<2e-8
assert abs(full_target5-j['targets']['conditional']['residual_equity_2031end'])<2e-8

# All legal entities and all periods: cash, signed retained capacity, reserve, ownership, debt, failure stop.
for k,sc in j['parent'].items():
 for r in sc['rows']:
  cash=r['begin_cash']+r['cfo']+r['new_receipts']+r['old_receivable_receipt']+r['compensation_cash']+r['new_debt']-r['investment']-r['maintenance']-r['acquisition_payment']-r['interest']-r['old_dividend_payment']-r['new_dividend']-r['debt_repayment']-r['onlend_cash_drag']
  assert abs(cash-r['end_cash'])<2e-8
  assert abs(r['begin_retained']+r['legal_profit']-r['reserve_added']-r['new_dividend']-r['retained'])<2e-8
  assert abs(r['begin_debt']+r['new_debt']-r['debt_repayment']-r['end_debt'])<2e-8
  assert r['new_dividend']<=max(0,r['signed_legal_capacity'])+1e-8
  if r['period']=='2026H2':assert abs(r['dps']-.25)<1e-9
alltargets={**j['targets'],**{k+'_no_shield':v for k,v in j['target_no_tax_shield'].items()},'onlend':j['target_onlend']}
for k,sc in alltargets.items():
 reserve=.00006495307
 vintages={2027:.25501091221,2028:.21484021663,2029:.18955235984}
 if sc['shield']:vintages[2027]-=.1743513-.09188183074
 for r in sc['rows']:
  ebt=r['ebit']-r['interest'];offset=0
  if sc['shield']:
   for expiry in sorted(vintages):
    if expiry>=r['year']:
     amount=min(max(0,ebt-offset),vintages[expiry]);vintages[expiry]-=amount;offset+=amount
  tax=max(0,ebt-offset)*.25;profit=ebt-tax
  assert abs(tax-r['tax'])<2e-8
  for expiry in vintages:
   if expiry<=r['year']:vintages[expiry]=0
  addition=min(max(0,7.9562*.5-reserve),max(0,profit-max(0,-r['begin_retained']))*.1)
  reserve+=addition
  assert abs(reserve-r['reserve'])<2e-8
  assert abs(profit-r['profit'])<2e-8
  assert abs(r['begin_retained']+profit-addition-r['signed_legal_capacity'])<2e-8
  assert abs(r['signed_legal_capacity']-r['dividend']-r['retained'])<2e-8
  assert abs(r['begin_cash']+r['profit']+r['da']-r['maintenance_capex']-r['principal_repayment']+r['new_debt']-r['dividend']-r['end_cash'])<2e-8
  assert abs(r['begin_debt']+r['new_debt']-r['principal_repayment']-r['end_debt'])<2e-8
  assert r['dividend']<=max(0,r['signed_legal_capacity'])+1e-8
 assert len(sc['rows'])==20
 assert abs(sc['liquidation_2047']-max(0,sc['rows'][-1]['end_cash']-sc['rows'][-1]['end_debt']-.05))<2e-8
# Contract compensation linked to each freshly modelled tax/profit path, never added to target retained earnings.
for sc in alltargets.values():
 total=.1743513+sum(r['profit'] for r in sc['rows'][:2])
 comp=min(7.34541,.592571-total) if total<.95*.592571 else 0
 assert abs(sc['compensation_diagnostic']['gross']-comp)<2e-8
assert j['targets']['conditional']['compensation_diagnostic']['gross']==0
assert j['target_no_tax_shield']['conditional']['compensation_diagnostic']['gross']>0
# Dividends accrue into separate NEW receivables, old opening receivables cannot fund a second receipt.
for sc in j['parent'].values():
 for r in sc['rows']:
  assert abs(r['new_dividend_receivable_begin']+r['declared_profit']-r['new_receipts']-r['new_dividend_receivable_end'])<2e-8
  assert abs(r['old_dividend_receivable_begin']-r['old_receivable_receipt']-r['old_dividend_receivable_end'])<2e-8
  assert r['new_dividend_receivable_end']>=-1e-8 and r['old_dividend_receivable_end']>=-1e-8
# Independently reconstruct all 20 years onloan claim/external debt/interest, not 12bn added twice.
for label,bridge in j['onlend_bridges'].items():
 assert bridge['initial']['parent_external_draw']==5.903825
 assert bridge['initial']['target_bank_repaid']==5.903825
 assert bridge['initial']['group_net_new_debt']==0 and bridge['initial']['group_net_new_cash']==0
 assert bridge['initial']['transient_balance_recognised']==0
 balance=5.903825;ar=0
 for i,r in enumerate(bridge['rows']):
  interest=balance*.021;payment=0 if bridge['delay'] and i==1 else interest+ar
  ar+=interest-payment;principal=5.903825/20;balance-=principal
  assert abs(r['end_onloan']-balance)<2e-8
  assert abs(r['parent_interest_received']-payment)<2e-8
  assert abs(r['parent_cash_drag']-(interest-payment))<2e-8
  assert abs(r['end_interest_receivable']-ar)<2e-8
  assert abs(r['target_end_total_cash']-r['target_end_free_cash']-ar)<2e-8
  assert abs(r['parent_external_principal_repaid']-principal)<2e-8
  assert r['parent_legal_profit_net']==0
 for r in j['parent']['onlend_'+label]['rows']:
  b=r['onlend_bridge']
  if b:
   assert abs(r['gross_external_debt_including_onlend']-r['end_debt']-b['end_onloan'])<2e-8
   assert abs(r['onlend_receivable']-b['end_onloan'])<2e-8
assert len(j['parent']['financing_failure']['rows'])==1 and not j['parent']['financing_failure']['feasible']
signed=-679641517.99+592571000
assert signed<0 and abs(signed/1e9-j['signed_commitment_capacity'])<1e-9
with tempfile.TemporaryDirectory(dir=R) as t:
 p=Path(t)/'only_model.py';shutil.copyfile(R/'2026-Q3.py',p)
 b=subprocess.check_output(['python',str(p)],cwd='/tmp');assert b==(R/'2026-Q3-output.json').read_bytes()
 print(json.dumps(dict(finite_lower_literal=ans[0],revenue_minus10_literal=ans[1],dominant_free_extension_delta=ans[2]-ans[0],appraisal_literal=app[0],appraisal_discount100bp=app[1],parent_first_draw=draw,target_full_lifetime_literal=full_target,target_independent_year5_literal=full_target5,signed_commitment_capacity_yuan=signed,all_periods_cash_debt_signed_legal='passed',single_file_arbitrary_cwd_all_bytes=True,output_sha256=hashlib.sha256(b).hexdigest(),r1_onlend_and_r3_receivables='passed',tax_shield_and_no_shield_all_years='passed',status='passed'),ensure_ascii=False,indent=2))
