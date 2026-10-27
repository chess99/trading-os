#!/usr/bin/env python3
# Independent literal-input implementation: no production import or production balances used.
import json,pathlib
ROOT=pathlib.Path(__file__).resolve().parent

def check(kind):
 params={'base':(.10,.0139,.0135,.005,.0002,.0005,.29,.16,.028),
 'core_low':(.105,.0137,.0133,.0055,.0003,.0006,.295,.17,.030),
 'core_high':(.095,.0141,.0137,.0045,.0001,.0004,.285,.15,.026),
 'cost_plus_100bp':(.11,.0139,.0135,.005,.0002,.0005,.29,.16,.028)}
 k,start,end,lc,nc,cc,ci,tax,rate=params[kind]
 equity=144.102147; bank=138.667354; risk=1504.078374; retained=58.880589
 ds=[]; records=[]
 for yr in range(1,121):
  growth=([.08,.08,.07,.065,.06][yr-1] if yr<=5 else max(.04,.06-.002*(yr-5)))
  n=risk*(1+growth); avg=risk*(1+growth/2)
  margin=start+(end-start)*min(yr-1,14)/14
  pretax=avg*((1.5*margin+.003+.0031)*(1-ci)-.78*lc-.72*nc-.3*cc-.00025)
  surplus=max(equity-(.096+.320167/1504.078374)*risk,0)
  gross=pretax*(1-tax)+.02*surplus
  earnings=gross-avg*30/1504.078374*rate
  parentearn=.962*gross-avg*30/1504.078374*rate
  subearn=earnings-parentearn
  upstream=0
  if yr>5:
   upstream=max(0,min(equity-bank+subearn-.004*n,subearn-.004*(n-risk)+.2*max(0,equity-bank-.004*risk)))
  reserve=.1*max(parentearn,0)+.015*.78*(n-risk)
  group_room=equity+earnings-(.096+.320167/1504.078374)*n
  parent_room=bank+parentearn+upstream-(.092*.993603962+1.298238/1504.078374)*n
  assert min(group_room,parent_room)>0
  if yr<=5: wish=earnings*[.30,.30,.32,.35,.38][yr-1]
  else: wish=max(0,earnings-(.096+.320167/1504.078374)*(n-risk)+.2*surplus)
  payout=min(wish,group_room,parent_room,retained+parentearn+upstream-reserve,.05*470.061919/1504.078374*risk)
  oldequity=equity
  equity+=earnings-payout;bank+=parentearn+upstream-payout;retained+=parentearn+upstream-reserve-payout
  assets0=2530.394819*risk/1504.078374; assets1=2530.394819*n/1504.078374
  depdelta=1543.748157*(n-risk)/1504.078374;otherdelta=23*(n-risk)/1504.078374;atdelta=30*(n-risk)/1504.078374
  debt0=assets0-oldequity-(30+1543.748157+23)*risk/1504.078374
  debt1=assets1-equity-(30+1543.748157+23)*n/1504.078374
  cashdelta=159.486803*(n-risk)/1504.078374
  net=earnings+depdelta+otherdelta+atdelta+debt1-debt0-payout-(assets1-assets0-cashdelta)
  assert abs(net-cashdelta)<1e-7
  records.append([equity,bank,n,retained,payout,earnings]); ds.append(payout);risk=n
 tail=ds[-1]*1.04/(k-.04)
 v=(sum(d/(1+k)**j for j,d in enumerate(ds,1))+tail/(1+k)**120)/7.249002548
 return {'value':v,'year1':[round(z,9) for z in records[0]],'year5':[round(z,9) for z in records[4]],'cash_conservation_all_years':True}
results={n:check(n) for n in ['base','core_low','core_high','cost_plus_100bp']}
# Only after all independent projections are computed is the published file opened for comparison.
published=json.loads((ROOT/'2026-Q3-output.json').read_text())
for n in results:
 assert abs(results[n]['value']-published[n]['value'])<1e-8
 for i in [0,4]:
  expected=results[n]['year'+str(i+1)]
  actual=published[n]['rows'][i]
  for z,key in zip(expected,['book_end','parent_book_end','rwa_end','parent_undistributed_end','common_dividend','common_profit']):assert abs(z-actual[key])<1e-8
results['sensitivity_change']=results['cost_plus_100bp']['value']-results['base']['value']
(ROOT/'independent-check.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(results,indent=2))
