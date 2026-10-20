import json
from pathlib import Path
S=16.82828214
D=[.20,.22,.24,.26,.28]

def model(growth=.08,roi=.13,r=.095,g=.023,profit0=11.0):
    capital=80.94; cash=0.; profit=profit0; rows=[]; pvdiv=0.; residual=0.; initial=capital
    for t,d in enumerate(D,1):
        prior=profit
        profit=profit0*(1+growth)**t
        invest=(profit-prior)/roi
        interest=cash*.015
        fcfe=profit-invest
        dividend=d*S
        opening=capital
        capital+=invest
        cash+=fcfe+interest-dividend
        residual+=(profit-r*opening)/(1+r)**t
        pvdiv+=dividend/(1+r)**t
        assert abs((capital+cash)-(opening+(cash-fcfe-interest+dividend)+profit+interest-dividend))<1e-8
        rows.append(dict(year=t,revenue=70.9*(1+growth)**t,profit=profit,investment=invest,fcfe=fcfe,interest=interest,dividend=dividend,capital=capital,excess_cash=cash))
    terminal_fcfe=profit*(1+g)*(1-g/roi)
    franchise=terminal_fcfe/(r-g)
    terminal=franchise+cash
    value=(pvdiv+terminal/(1+r)**5)/S
    mature_roe=.125 if growth<=.08 else .14
    ri_terminal=(mature_roe-r)*capital/(r-g)
    ri_operating=(initial+residual+ri_terminal/(1+r)**5)
    # operating RI equals distributable FCFE PV + terminal operating franchise.
    ri_terminal_equity=capital+ri_terminal
    ri=(sum(x['fcfe']/(1+r)**x['year'] for x in rows)+ri_terminal_equity/(1+r)**5)/S
    # FCFE assumed paid immediately for auxiliary; main uses actual dividend timing and 1.5% cash accumulation.
    assert all(x['excess_cash']>=0 for x in rows)
    assert abs(ri*S-ri_operating)<1e-8
    ri += (pvdiv+cash/(1+r)**5-sum(x['fcfe']/(1+r)**x['year'] for x in rows))/S
    return dict(parameters=dict(growth=growth,roi=roi,r=r,g=g,profit0=profit0),rows=rows,terminal_fcfe=terminal_fcfe,franchise=franchise,terminal=terminal,terminal_per_share=terminal/S,value=value,terminal_pv_share=(terminal/(1+r)**5)/(value*S),auxiliary_ri=ri,mature_roe=mature_roe)

out={'shares':S,'dividends':D,'low':model(),'high':model(.09,.15,.088,.025),'sensitivity_roi_11':model(roi=.11),'sensitivity_r_plus_1pct':model(r=.105),'structural':model(.03,.10,.105,.015,9.5),'upside':model(.11,.16,.088,.025)}
out['cyclical_value']=out['low']['value']-(.5*1.015**4+.5*1.015**3)/1.095**5/S
# No growth/no investment special case: perpetual FCFE equals earnings.
p=11.; r=.1
assert abs(sum(p/(1+r)**t for t in range(1,6))+p/r/(1+r)**5-p/r)<1e-8
for c in out.values():
    if not isinstance(c,dict) or 'rows' not in c: continue
    assert abs(c['rows'][-1]['excess_cash']-sum(x['fcfe']+x['interest']-x['dividend'] for x in c['rows']))<1e-8
Path(__file__).with_name('2026-H1-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(json.dumps({k:{x:round(v[x],4) for x in ['value','terminal_per_share','auxiliary_ri']} for k,v in out.items() if isinstance(v,dict)},ensure_ascii=False))
