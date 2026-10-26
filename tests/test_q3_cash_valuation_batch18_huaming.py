#!/usr/bin/env python3
"""Independent literal-parameter cash book. Does not import/read production code or parameters.
Only at the end reads delivered result for comparison. CNY billions.
"""
import json,pathlib

def recompute(rate,marginloss=0.,capital_return=.25,delay=0.,localshare=.55,parent_cash=.06,old_delay=0):
    # GZ, ZY, RU, TR, CNC, photovoltaic projects, holding, HV, Shanghai, parent
    capitals=[.060,.050,.00113862286,.017401925,.092,.133,.387,.050,.100,.896225431]
    own=[1.,1.,.65,.9832,1.,1.,1.,1.,1.]
    parent=[8,8,8,8,9,6,9,8,9]
    allocation=[.20,.06,.02,.02,0,0,0,.70-localshare,localshare]
    cash=[(.99942404399-.23301861206-.024998103-.00927546078-parent_cash)*v for v in [.04,.02,.04,.02,.02,.04,.02,.02,.78]]+[parent_cash]
    earnings=[.03]*8+[.30,.44478031239-.23301861206]
    reserves=[0.]*9+[.36530171861]
    loans=[0.]*10;loans[5]=.55;loans[8]=.23858193369
    owed=[0.]*10;owed[8]=.39698138794
    sales=2.36;secondary=.34;sponsored=0.; ds=[]; pv=0.;terminal=0.
    for yr in range(1,601):
        rs=sales;os=secondary
        sales*=1+[.09,.09,.08,.07,.06,.05,.04,.03,.025,.02][min(yr-1,9)]
        secondary*=1+(.03 if yr<6 else .02)
        nm=.34-.02*min(yr,10)/10+marginloss
        growth_capital=(sales-rs)*nm/(capital_return if yr<=5 else min(capital_return,.18))
        extra_capital=(secondary-os)*.055/.12
        rec=[0.]*10;decl=[0.]*10;economic=[0.]*10;floors=[0.]*10
        for i in range(9):
            op=sales*nm*allocation[i] if allocation[i] else secondary*.055*(.45 if i==4 else .55 if i==5 else 0)
            invest=growth_capital*allocation[i] if allocation[i] else extra_capital*(.45 if i==4 else .55 if i==5 else 0)
            fin=.015*cash[i]-.045*loans[i]
            law_profit=op+fin+decl[i]
            cash[i]+=op+fin-invest+rec[i]
            recover=min(max(-earnings[i],0),max(law_profit,0))
            reserve=min(max(capitals[i]*(.2 if i==3 else .5)-reserves[i],0),max(law_profit-recover,0)*(.05 if i==3 else .1))
            earnings[i]+=law_profit-reserve;reserves[i]+=reserve
            principal=min(loans[i],(.23858193369 if i==8 else .55 if i==5 else 0)/8) if yr<=8 else 0
            loans[i]-=principal;cash[i]-=principal
            floor=sales*.085*allocation[i] if allocation[i] else secondary*.085*(.45 if i==4 else .55 if i==5 else 0)
            floors[i]=floor
            oldpay=min(owed[i],max(cash[i]-floor,0)) if not (i==8 and yr<=old_delay) else 0; owed[i]-=oldpay;cash[i]-=oldpay;rec[parent[i]]+=oldpay*own[i]*(.9 if i in [2,3] else 1.)
            if i==4:rec[9]-=oldpay*.1304;rec[8]+=oldpay*.1304
            want=max(op*.78,0)+max(cash[i]-floor-op*.78,0)*.20
            capacity=max(earnings[i],0)
            if i==3:capacity=min(capacity,(capacity+.005*capitals[i])/1.1)
            div=min(capacity,max(cash[i]-floor,0),max(want,0))
            earnings[i]-=max(div-.05*capitals[i],0)*.1 if i==3 else 0
            paid=div*(1-delay);earnings[i]-=div;cash[i]-=paid;owed[i]+=div-paid
            tax=.1 if i in [2,3] else 0
            decl[parent[i]]+=div*own[i]*(1-tax);rec[parent[i]]+=paid*own[i]*(1-tax)
            if i==4:
                decl[9]-=div*.1304;decl[8]+=div*.1304;rec[9]-=paid*.1304;rec[8]+=paid*.1304
            economic[i]=op+fin-(paid+oldpay)*own[i]*tax
        ownprofit=-.02*1.02**(yr-1)+.015*cash[9]-.045*loans[9]
        law_profit=decl[9]+ownprofit;economic[9]=ownprofit;cash[9]+=rec[9]+ownprofit
        inject=min(max(floors[5]-cash[5],0),max(cash[9]-.03,0),max(.70-sponsored,0))
        cash[9]-=inject;cash[5]+=inject;capitals[5]+=inject;capitals[6]+=inject;sponsored+=inject
        for i in range(9):
            borrowed=min(max(floors[i]-cash[i],0),max(.95-sum(loans),0));cash[i]+=borrowed;loans[i]+=borrowed
            assert cash[i]>-1e-9
        cash[9]+=.07 if yr==2 else .04 if yr==3 else 0
        if yr==1:cash[9]-=.125001897
        recover=min(max(-earnings[9],0),max(law_profit,0))
        reserve=min(max(capitals[9]/2-reserves[9],0),max(law_profit-recover,0)/10)
        earnings[9]+=law_profit-reserve;reserves[9]+=reserve
        floor=.03*1.02**(yr-1)
        want=max(sum(economic),0)*.7 if yr<=5 else max(cash[9]-floor,0)
        dividend=min(max(earnings[9],0),max(cash[9]-floor,0),max(want,0))
        earnings[9]-=dividend;cash[9]-=dividend
        borrowed=min(max(floor-cash[9],0),max(.95-sum(loans),0));cash[9]+=borrowed;loans[9]+=borrowed
        d=dividend/.896225431
        if yr<=5:ds.append(d)
        pv+=d/(1+rate)**yr
        if yr>5:terminal+=d/(1+rate)**(yr-5)
    return {'pv':pv,'tv5':terminal,'first5':ds}

ROOT=pathlib.Path(__file__).resolve().parents[1]/'research/companies/CN/002270/models'
def test_huaming_literal_multilevel_distribution_and_sensitivity():
 cases={'base_low':recompute(.105),'base_high':recompute(.09),'base':recompute(.0975),'margin_minus3':recompute(.0975,-.03),'roic15':recompute(.0975,capital_return=.15),'receipt_half':recompute(.0975,delay=.5),'upstream_manufacturing':recompute(.0975,localshare=.30),'parent_cash_low':recompute(.0975,parent_cash=.02),'old_receipt_year2':recompute(.0975,old_delay=1)}
 out=json.loads((ROOT/'2026-Q3-output.json').read_text())
 for name,value in cases.items():
  for k in ['pv','tv5']:assert abs(value[k]-out['paths'][name][k])<1e-9
  assert max(abs(a-b) for a,b in zip(value['first5'],out['paths'][name]['first5']))<1e-9

def test_huaming_actual_funding_and_complete_lossless_package():
 import runpy,hashlib,base64,gzip
 m=runpy.run_path(str(ROOT/'2026-Q3.py'));t=m['tests']()
 f=t['positive_cash_fixture'];assert 0<f['cash']<f['required_cash']
 d=t['new_debt_fixture'];assert abs(d[0]['borrowing']-.05)<1e-9
 assert abs(d[1]['parent_principal']-.025)<1e-9 and abs(d[2]['parent_principal']-.025)<1e-9
 packed=json.loads((ROOT/'2026-Q3-output.json').read_text());full=m['expand_output'](packed)
 assert hashlib.sha256(m['canonical_json'](full)).hexdigest()==packed['annual_data']['expanded_canonical_sha256']
 assert int.from_bytes(base64.b64decode(packed['annual_data']['payload_base64'])[4:8],'little')==0
 for name,p in full['paths'].items():
  assert len(p['rows'])==600 and p['feasible']
  for r in p['rows']:
   for n,v in r['subjects'].items():
    assert v['end']['cash']>=v['floor']-1e-7*max(1,v['floor'])
    assert v['end']['reserve']<=v['end']['capital']*.5+1e-8
  if name in ['base_low','base_high']:assert p['rows']==full['paths']['base']['rows']
 for side in ['low','high']:
  for k in ['pv','tv5']:assert abs(full['convergence']['300'][side][k]-full['convergence']['900'][side][k])<1e-6
