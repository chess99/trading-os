"""Independent raw-literal reconstruction; no production function used for estimates."""
import json, math, copy, runpy
from pathlib import Path
import pytest
def reconstruct(q,years=300):
    a=[dict(cash=c,earn=u,res=s,cap=k,loan=0.,debt=0.,owed=0.) for c,u,s,k in zip(q['cash'],q['retained'],q['reserve'],q['capital'])]
    rev0=7.8;k0=q['initial_fixed'];wc0=q['initial_working'];dep0=3.09069063185;hist=[]
    for yr in range(1,years+1):
        if yr<6: rev=q['revenue'][yr-1];margin=q['margin'][yr-1]
        else:
            theta=min(1,(yr-5)/10)
            rev=rev0*(1+q['g_after5']+(q['g_long']-q['g_after5'])*theta)
            margin=q['margin'][-1]+(q['margin_long']-q['margin'][-1])*theta
        earn=rev*margin*(1-q['tax']);cost=q['parent_cost']*rev/7.8
        li=sum(e['loan'] for e in a)*q['loan_rate']
        profit=[-cost-q['parent_extra_cost']+a[0]['cash']*q['cash_yield']-a[0]['debt']*q['external_rate']+li]
        for idx,e in enumerate(a[1:],1):
            profit.append((earn+cost)*q['weights'][idx]+e['cash']*q['cash_yield']-e['loan']*q['loan_rate']-e['debt']*q['external_rate'])
        k=max(.6,q['initial_fixed']+q['capital_ratio']*(rev-7.8)+sum(q['construction'][:min(yr,5)]))
        dk=k-k0
        if rev*.02+dk<0:dk=-rev*.02;k=k0+dk
        wc=rev*q['working_ratio'];deposits=rev*q['contract_ratio']
        for i,e in enumerate(a):
            e['cash']+=profit[i] if i==0 else profit[i]+q['weights'][i]*(-dk-(wc-wc0)+deposits-dep0)
        for i,e in enumerate(a[1:],1):
            a[q['receiver'][i]]['cash']+=e['owed'];e['cash']-=e['owed'];e['owed']=0.
        floors=[.3]+[q['weights'][i]*(rev*q['liquidity_ratio']+deposits) for i in range(1,len(a))]
        for i,e in enumerate(a[1:],1):
            lend=min(max(floors[i]-e['cash'],0),max(a[0]['cash']-.3,0))
            a[0]['cash']-=lend;e['cash']+=lend;e['loan']+=lend
        for i,e in enumerate(a[1:],1):
            new=min(max(floors[i]-e['cash'],0),max(q['external_limit']-sum(z['debt'] for z in a),0))
            e['cash']+=new;e['debt']+=new
            if e['cash']<floors[i]-1e-8:raise ValueError('infeasible subsidiary')
        for i,e in enumerate(a):
            repay=min(max(e['cash']-floors[i],0),e['debt']);e['cash']-=repay;e['debt']-=repay
        for i,e in enumerate(a[1:],1):
            repay=min(max(e['cash']-floors[i],0),e['loan']);e['cash']-=repay;e['loan']-=repay;a[0]['cash']+=repay
        statutory=profit[:]
        for i in q['upstream_order']:
            e=a[i]
            eligible=max(0,statutory[i]+min(e['earn'],0));reserve=min(eligible/10,max(e['cap']/2-e['res'],0))
            e['earn']+=statutory[i]-reserve;e['res']+=reserve
            normal=min(max(statutory[i],0)*q['upstream_payout'],max(e['earn'],0),max(e['cash']-floors[i],0))
            extra=min(max(e['earn']-normal,0),max(e['cash']-floors[i]-normal,0)*q['release_fraction']) if yr>=q['release_start'] else 0.
            pay=normal+extra;e['earn']-=pay;statutory[q['receiver'][i]]+=pay
            if q['upstream_lag']:e['owed']=pay
            else:e['cash']-=pay;a[q['receiver'][i]]['cash']+=pay
        parent=a[0];borrow=min(max(.3-parent['cash'],0),max(q['external_limit']-sum(z['debt'] for z in a),0));parent['cash']+=borrow;parent['debt']+=borrow
        if parent['cash']<.3-1e-8:raise ValueError('infeasible parent')
        income=statutory[0];reserve=min(max(income+min(parent['earn'],0),0)/10,max(parent['cap']/2-parent['res'],0))
        parent['earn']+=income-reserve;parent['res']+=reserve
        regular=min(max(sum(profit),0)*q['normal_payout'],max(parent['earn'],0),max(parent['cash']-.3,0))
        additional=min(max(parent['earn']-regular,0),max(parent['cash']-.3-regular,0)*q['release_fraction']) if yr>=q['release_start'] else 0
        div=regular+additional;parent['cash']-=div;parent['earn']-=div
        hist.append({'year':yr,'revenue':rev,'profit':sum(profit),'dividend':div,'cash':[z['cash'] for z in a],'retained':[z['earn'] for z in a],'reserve':[z['res'] for z in a],'external':[z['debt'] for z in a],'loans':[z['loan'] for z in a],'payable':[z['owed'] for z in a],'fixed':k,'working':wc,'contract':deposits})
        rev0=rev;k0=k;wc0=wc;dep0=deposits
    r=q['discount'];divs=[h['dividend']/.75264 for h in hist]
    return {'value':q.get('opening_distribution',0.)/.75264+sum(d/(1+r)**(i+1) for i,d in enumerate(divs)),'tv5':sum(d/(1+r)**(i-4) for i,d in enumerate(divs) if i>=5),'rows':hist}
literal_base={
    'cash':[2.4,0.325,1.45,0.30,2.4,2.36567701089,0.918,0.325],
    'retained':[2.7,0.35,0.9,0.2,1.2,1.1,0.5,0.35],
    'reserve':[0.36081535125,0.015,0.15,0.005,0.10383,0.0275,0.2003902,0.0],
    'capital':[0.75264,0.03,0.30,0.01,0.20766,0.055,0.4007804,0.01],
    'revenue':[7.8,8.346,8.84676,9.3775656,9.84644388],
    'margin':[0.48,0.48,0.48,0.48,0.48],
    'weights':[0.0,0.115,0.27,0.22,0.16,0.12,0.0,0.115],
    'receiver':[None,0,0,0,0,0,0,1],
    'upstream_order':[7,1,2,3,4,5,6],
    'initial_fixed':1.70810491672,'initial_working':0.078,
    'construction':[0.18,0.11,0.06,0.0,0.0],
    'capital_ratio':0.20,'working_ratio':0.01,
    'liquidity_ratio':0.12,'contract_ratio':3.09069063185/7.8,
    'parent_cost':0.16,'parent_extra_cost':0.0,
    'cash_yield':0.012,'loan_rate':0.03,'external_rate':0.05,'external_limit':0.5,
    'normal_payout':0.80,'upstream_payout':0.80,
    'release_fraction':0.20,'release_start':6,'upstream_lag':0,
    'tax':0.15,'discount':0.10,'g_after5':0.04,'g_long':0.02,'margin_long':0.42,
    'opening_distribution':0.0
}
literal_sets={
    'core_low':dict(literal_base,discount=0.105,g_after5=0.03,g_long=0.015,margin_long=0.40),
    'core_high':dict(literal_base,discount=0.095,g_after5=0.045,g_long=0.025,margin_long=0.44),
    'margin_minus5pp_fromY1':dict(literal_base,margin=[0.43,0.43,0.43,0.43,0.43],margin_long=0.37)
}

ROOT=Path(__file__).resolve().parents[1]/'research/companies/CN/300033/models'
def read_full():
 data=json.loads((ROOT/'2026-Q3-output.json').read_text())
 for c in data['cases'].values():
  t=c['annual_rows'];assert len(t['columns'])==len(set(t['columns']))
  c['annual_rows']=[dict(zip(t['columns'],v)) for v in t['values']]
 return data
@pytest.mark.parametrize('label',list(literal_sets))
def test_ths_literal_raw_chain(label):
 fresh=reconstruct(copy.deepcopy(literal_sets[label]));formal=read_full()['cases'][label]
 assert fresh['value']==pytest.approx(formal['valuation']['value'],abs=1e-8)
 assert fresh['tv5']==pytest.approx(formal['valuation']['tv5'],abs=1e-8)
 assert len(fresh['rows'])==len(formal['annual_rows'])==300
 for a,b in zip(fresh['rows'],formal['annual_rows']):
  assert a['dividend']==pytest.approx(b['dividend'],rel=1e-10,abs=1e-9)
  for key in ('cash','retained','reserve','external','loans','payable'):
   for u,v in zip(a[key],b['state'][key]):assert u==pytest.approx(v,rel=1e-10,abs=1e-8)
def test_ths_production_nested_dividends_and_lossless_encoding():
 m=runpy.run_path(str(ROOT/'2026-Q3.py'));m['tests']()
 data=json.loads((ROOT/'2026-Q3-output.json').read_text());full=m['expand_output'](data)
 assert m['pack_output'](full)==data
 assert full==read_full()
 for c in full['cases'].values():assert [r['year'] for r in c['annual_rows']]==list(range(1,301))
 assert full['cases']['core_low']['annual_rows'][4]['state']==full['cases']['core_high']['annual_rows'][4]['state']
