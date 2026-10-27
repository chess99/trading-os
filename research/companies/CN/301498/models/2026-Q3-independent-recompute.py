#!/usr/bin/env python3
"""Independent literal re-derivation. Does not import production model.
Hardcoded assumptions are separately transcribed; JSON read solely for comparisons.
"""
import json,math
from pathlib import Path
P=Path(__file__).resolve().parent
observed=json.loads((P/'2026-Q3-output.json').read_text())['scenarios']
results={}
for case,discount,delta in [('base_low',.115,0),('margin_minus_1pp',.105,-.01)]:
    g=20.64194808;p=11.;debt=12.5004688889;pd=7.5505157778;long=.340825
    retained=2.6796800999; reserve=.9290301779; lastrev=71.5612458114; ds=[]; states=[]
    R=[72,78,84.5,91,96.5];M=[.07,.08,.09,.095,.1];G=[6,5.5,4.5,3,1];K=[2.5,2.7,3,3.3,3.5];A=[2.3,2.5,2.8,3.1,3.3];PC=[2.3,2.5,1.8,1,.7];rates=[.2,.25,.3,.3,.35]
    for t in range(5):
        go=g;po=p;do=debt;pdo=pd
        earnings=R[t]*(M[t]+delta)*.75
        ni=earnings+.75*(go*.015-(do+long)*.038)
        w=max(0,R[t]-lastrev)*.1
        cashflow=ni+A[t]-w
        parentprofit=.45*earnings+.75*(.015*po-.038*pdo)
        parentflow=parentprofit+.45*A[t]-.4*w
        loss=max(0,-retained); taxable_for_reserve=max(0,parentprofit-loss)
        allocation=min(max(0,4.01133/2-reserve),taxable_for_reserve*.1)
        legal=retained+parentprofit-allocation;reserve+=allocation
        acq=.65 if t==1 else 0.;bb=.6636085757 if t==0 else 0.
        pre=go+cashflow-G[t]-K[t]-acq-bb;ppre=po+parentflow-PC[t]-acq-bb
        net=0. if t<2 else min(do,2.,max(0,pre-7.))
        netp=net*pdo/do if do else 0.
        bankpay=do;banknew=do-net;parentpay=pdo;parentnew=pdo-netp
        debt=do-net;pd=pdo-netp;pre-=net;ppre-=netp
        down=max(0,ppre-(pre-3));ppre-=down
        d=max(0,min(max(0,ni)*rates[t],pre-5,ppre-1,max(0,legal)))
        g=pre-d;p=ppre-d;retained=legal-d
        subsidiary=(go-po)+(cashflow-parentflow)-(G[t]+K[t]-PC[t])-(bankpay-parentpay)+(banknew-parentnew)+down
        assert abs(subsidiary-(g-p))<1e-10
        ds.append(d/4.01133);lastrev=R[t]
        state=dict(cash_close=g,parent_cash_close=p,parent_retained_close=retained,parent_reserve=reserve,parent_short_close=pd,bank_debt_close=debt+long,dps=ds[-1],subsidiary_cash_close=subsidiary)
        ref=observed['base' if case=='base_low' else case]['rows'][t]
        for k,x in state.items():assert abs(x-ref[k])<1e-9,(case,t,k,x,ref[k])
        states.append(state)
    future=earnings; explicit=0.;fs=[]
    for j,rate in enumerate([.06,.055,.045,.035,.03],1):
        increment=future*rate;future+=increment;fcf=future-increment/.15-.2
        fs.append(fcf);explicit+=fcf/(1+discount)**j
    finalcash=future*1.02*(1-.02/.12)-.2
    ev=explicit+finalcash/(discount-.02)/(1+discount)**5
    terminal=(ev+g-debt-long)/4.01133
    current=sum(x/(1+discount)**(i+1) for i,x in enumerate(ds))+terminal/(1+discount)**5
    target=observed['base']['low'] if case=='base_low' else observed[case]['valuation']
    assert abs(current-target['value_per_share'])<1e-9
    assert abs(terminal-target['terminal_per_share'])<1e-9
    results[case]=dict(value=current,terminal=terminal,states=states,fcff6_10=fs)
(P/'independent-check.json').write_text(json.dumps({'status':'PASS_FRESH_RECONSTRUCTION','independence':'No model import; separately literal cash, legal, debt and value recursion; output JSON comparison only','checks':results},ensure_ascii=False,indent=2)+'\n')
print('PASS independent base low and margin minus 1pp complete equity value and entity cash')
