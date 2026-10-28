import json, math, pathlib
def independent_literal(data):
 """不调用production，重新literal递推全部正式经营路径。"""
 checks=[]
 paths=list(data['inputs'].items())
 altered=dict(data['inputs']['base']);altered['unit']=[x-500 for x in altered['unit']]
 paths.append(('unit_minus_500',altered))
 for name,c in paths:
  a=16.17;b=12.98;pc=4.92685;lr=4.30024;ar=1.104697;reserve=1.831906632;pb=5.104;pv=0
  for n in range(5):
   e=c['vol'][n]*c['unit'][n]*.001*.75+c['slaughter'][n]*(.85 if c['slaughter'][n]>=0 else 1)+c['other'][n]-.0385
   profit=e+(a-2)*.015-b*c['rate']*.75
   free=profit+c['da'][n]-c['capex'][n]-c['wc'][n]-.04
   declare=max(0,profit)*c['up'];recv=ar+declare*(1-c['delay']);ar=declare*c['delay']
   pcost=pb*c['rate']*.75;direct=.25*c['vol'][n]/1.4+pc*.0142-pcost
   prep=min(pb,c['redemption'][n]*.4)
   income=declare+direct
   levy=min(max(0,3.464661213*.5-reserve),max(0,income+min(lr,0))*.1)
   reserve+=levy;lr+=income-levy
   pc+=recv+direct-.3-c['settle'][n]-prep
   a+=free-c['redemption'][n];b-=c['redemption'][n];pb-=prep
   paid=max(0,min(max(0,profit)*c['payout'],lr,pc-1.5,a-2.65))
   pc-=paid;lr-=paid;a-=paid;pv+=paid/(1+c['r'])**(n+1)
   reference=data['sensitivities'][name] if name=='unit_minus_500' else data['outputs'][name]
   ref=reference['rows'][n]
   for key,val in [('common_profit',profit),('fcfe',free),('assets',a),('debt',b),('parent_cash',pc),('parent_legal',lr),('dividend',paid),('dividend_receivable',ar),('parent_statutory_reserve',reserve),('parent_reserve_transfer',levy),('parent_debt',pb),('parent_debt_repaid',prep),('parent_interest',pcost)]:
    assert math.isclose(val,ref[key],rel_tol=1e-12,abs_tol=1e-11),(name,n,key)
  r=c['r'];g=c['g'];gap=c.get('terminal_maintenance_gap',.05)
  op=(e*(1+g)*(1-g/c['roic'])-gap-.04)/(r-g)
  reg=.65/(1+r)**10+.00975*(1-(1+r)**-10)/r
  tv=(op+a-b-2.65+reg)/3.464661213;value=pv/3.464661213+tv/(1+r)**5
  assert abs(tv-reference['terminal_value'])<1e-10
  assert abs(value-reference['current_value'])<1e-10
  checks.append(dict(case=name,value=value,terminal=tv,status='passed'))
 assert abs(data['outputs']['base']['rows'][0]['common_profit']-data['sensitivities']['unit_minus_500']['rows'][0]['common_profit']-.525)<1e-10
 return dict(method='independent literal, no production call',cases=checks,dominant_parameter='吨利-500元首年利润-5.25亿元 passed')

p=pathlib.Path(__file__).resolve().parent
r=independent_literal(json.loads((p/'2026-Q3-output.json').read_text()))
(p/'independent_check.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(r,ensure_ascii=False,indent=2))
