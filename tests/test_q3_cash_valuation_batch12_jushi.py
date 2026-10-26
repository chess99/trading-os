import copy,json,math,runpy,pytest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/'research/companies/CN/600176/models'
def independently_rebuild(s,years=240):
    # Independently re-entered reported/budget inputs, no initial()/NODES use.
    raw=[('JJ','G',1.,.16,.16,.2,.6,.85,1.291,.383241303),
         ('CD','G',1.,.1,.13,.15,.8,2.,1.5,0.),
         ('HA','G',1.,.2,.34,.25,2.3,5.3,1.99988347,1.204223357),
         ('EG','G',.7501,.08,.07,.25,.8,1.,.21,0.),
         ('US','P',.7,.04,.04,.1,.15,.3,1.4,0.),
         ('W','Z',.8,.01,.01,.059480663,.128548324,.228548324,.3,.361010719),
         ('L','Z',1.,0.,0.,.03,0.,1.5,.3,0.),
         ('Z','P',1.,0.,0.,0.,0.,.05,.6,0.),
         ('G','P',1.,.4,.25,.42,3.15,4.,5.255313048,1.317516638),
         ('P',None,1.,.01,0.,.8,6.9,8.1,4.003136728,0.)]
    state={n:dict(dividend_receivable=.65 if n=='P' else 0.,cash=c,debt=d,limit=l,capital=k,reserve=1.475234311 if n=='P' else 0.,retained=.00385265745 if n=='P' else 0.,loan=loan,payable=.65 if n=='G' else 0.) for n,up,own,w,cw,c,d,l,k,loan in raw}
    records=[]; prev=24.; vals=[]
    for t in range(1,years+1):
        # Independent reconstruction of original operating assumptions, not reading official outputs.
        if t<6:
            rr=(24.81,24.565,25.67,27.05,28.40)[t-1]; mm=(.29,.26,.25,.25,.25)[t-1]
            dd=2.8+.15*(t-1); cc=(7.5,6.5,5.0,4.2,4.3)[t-1]
        else:
            factors=(1.04,1.035,1.03,1.025,1.02)
            rr=28.4*math.prod(factors[:min(t-5,5)])*1.015**max(t-10,0)
            mm=.25-.004*min(t-5,5); dd=3.4*rr/28.4
            lastfactor=factors[t-6] if t<=10 else 1.015
            cc=dd+1.6*rr*(1-1/lastfactor)
        if t>=s['start']:
            rr*=s['rev_factor']; mm+=s['margin_shift']; cc*=s['capex_factor']
            if t>5: rr*=s['growth_factor']**min((t-5)/5,1)
        if False and t<=3:
            rr*=(.88,.92,.96)[t-1]; mm-=(.09,.07,.04)[t-1]
        if False and t==1: cc+=20
        op=dict(revenue=rr,ebit=rr*mm,depreciation=dd,capex=cc)
        rev=op['revenue']; netwc=(rev-prev)/5+(1. if t==1 else -.4 if t==2 else -.3 if t==3 else 0.)
        shock=s['wc_shock']*((t==s['start'])-(t==s['start']+2)); dc={n[0]:[0.,0.] for n in raw}
        ir=sum(z['loan'] for z in state.values())*.025; principal=0.; earn=0.; out=0.
        rec={}
        for name,up,own,w,cw,_,_,_,_,_ in raw:
            z=state[name]; rw=.41 if name=='G' else 0. if name=='P' else w
            floor=(.45 if name=='P' else .02 if name in ('Z','L') else 1.35*rw)*rev/24
            cash_grids={1:[.6,1.2,3.,.3,.2,.1,.9,0.,1.2,0.],2:[.55,1.,2.4,.3,.2,.1,.82449,0.,1.12551,0.],3:[.55,.8,1.65,.3,.2,.1,.1,0.,1.3,0.]}
            idx=[n[0] for n in raw].index(name)
            capnode=cash_grids[t][idx]*op['capex']/(7.5,6.5,5.)[t-1] if t<=3 else op['capex']*(.025 if name=='L' else cw-(.025 if name=='G' else 0))
            lp=(.02,.12,.22,.24,.25)[t-1] if t<=5 else .25*rev/28.4
            ld=(.01,.05,.09,.10,.10)[t-1] if t<=5 else .10*rev/28.4
            depnode=op['depreciation']*cw+(ld if name=='L' else -ld if name=='G' else 0)
            equity=.3 if t==1 else .2 if t==2 else 0
            ei=equity if name in ('L','Z') else 0; eo=equity if name in ('P','Z') else 0
            wa=.13*rev/24-op['ebit']*.01
            operating=op['ebit']*w+(wa if name=='W' else -wa if name=='G' else 0)+(lp if name=='L' else -lp if name=='G' else 0); interest=z['cash']*.012; cost=z['debt']*(s['rate'] if t>=s['start'] else .03)+z['loan']*.025
            pretax=operating+interest-cost+(ir if name=='P' else 0.)
            ownprofit=pretax-.18*max(pretax,0)+(.1*rev/24 if name=='P' else 0)
            legal=ownprofit+dc[name][0]
            replenish=min(max(.5*(z['capital']+ei)-z['reserve'],0),.1*max(legal+min(z['retained'],0),0))
            room=z['retained']+legal-replenish
            cash=ei-eo+z['cash']+ownprofit+depnode-capnode-netwc*rw-(shock if name=='P' else 0)+dc[name][1]+(principal if name=='P' else 0)-z['payable']
            newdebt=min(max(floor-cash,0),max(z['limit']-z['debt'],0)); cash+=newdebt
            if cash<floor-1e-10: return {'feasible':False,'year':t,'node':name}
            interpay=min(z['loan'],.1*max(cash-floor,0)); cash-=interpay
            redeem=min(z['debt']+newdebt,.25*max(cash-floor,0)); cash-=redeem
            want=max(earn,0)*(.45 if t<=5 else .7 if t<=10 else 1) if name=='P' else 1e9
            regular=min(max(room,0),max(cash-floor,0),max(want,0))
            extra=min(max(room-regular,0),max(cash-floor-regular,0)) if t>=6 else 0
            declared=regular+extra; lag=0 if name=='P' else (s['lag'] if t>=s['start'] else .15); paid=declared*(1-lag)
            transfer=z['payable']+paid; cash-=paid
            state[name]={'dividend_receivable':z.get('dividend_receivable',0)+dc[name][0]-dc[name][1],'cash':cash,'debt':z['debt']+newdebt-redeem,'limit':z['limit'],'capital':z['capital']+ei,'reserve':z['reserve']+replenish,'retained':room-declared,'loan':z['loan']-interpay,'payable':declared-paid}
            earn+=ownprofit*own; principal+=interpay
            if up:
                factor=own*(.95 if name in ('EG','US') else 1)
                dc[up][0]+=declared*factor; dc[up][1]+=transfer*factor
            else: out=transfer/4.003136728
            rec[name]=copy.deepcopy(state[name])
        records.append({'year':t,'states':rec,'owner_profit':earn,'distribution_per_share':out}); vals.append(out); prev=rev
    return dict(feasible=True,trace=records,distributions=vals,valuation={'low':sum(v*(1.1025)**(-i-1) for i,v in enumerate(vals)),'high':sum(v*(1.09)**(-i-1) for i,v in enumerate(vals)),'terminal_low':sum(v*(1.1025)**(-i-1) for i,v in enumerate(vals[5:])),'terminal_high':sum(v*(1.09)**(-i-1) for i,v in enumerate(vals[5:]))})

def decode(p):
 table=[]
 for row in p['objects']:
  vals=[table[v[0]] if isinstance(v,list) else v for v in row[1:]]
  table.append(vals if row[0]==0 else dict(zip(p['schemas'][-row[0]-1],vals)))
 return table[p['root'][0]]
@pytest.mark.parametrize('name,start,shock',[('base',1,0.),('margin_minus_2pp',2,-.02)])
def test_jushi_literal_original_inputs(name,start,shock):
 o=decode(json.loads((ROOT/'2026-Q3-output.json').read_text()))
 x=independently_rebuild(dict(start=start,rev_factor=1.,margin_shift=shock,growth_factor=1.,capex_factor=1.,rate=.03,lag=.15,wc_shock=0.));z=o['scenarios'][name]
 assert x['feasible'] and z['feasible']
 for u,v in zip(x['trace'],z['trace']):
  assert u['distribution_per_share']==pytest.approx(v['distribution_per_share'],abs=1e-8)
  for n in u['states']:
   for key,val in u['states'][n].items(): assert val==pytest.approx(v['nodes'][n]['end'][key],rel=1e-8,abs=1e-7)
 for a,b in [('low','value_low'),('high','value_high'),('terminal_low','terminal_y5_low'),('terminal_high','terminal_y5_high')]: assert x['valuation'][a]==pytest.approx(z['valuation'][b],abs=1e-8)
def test_jushi_real_functions_same_year5_and_economic_crosscheck():
 m=runpy.run_path(str(ROOT/'2026-Q3.py'));m['tests']()
 packed=json.loads((ROOT/'2026-Q3-output.json').read_text());o=decode(packed)
 assert o==m['expand_output'](packed)
 assert o['same_year5_state_terminal_restart']['verified']
 assert not o['scenarios']['unfundable']['feasible']
 assert o['auxiliary_normalized_PE']['complete_budget']['trace'][:5]==o['scenarios']['base']['trace'][:5]
 assert o['auxiliary_normalized_PE']['high']<o['summary']['value_high']
