"""Independent scalar reconstruction: literal inputs, no production imports.
Production JSON is read only AFTER independent paths/values are calculated.
"""
import json,gzip,base64,hashlib
from pathlib import Path
S=15.824105875
CASES={
'base':{},'cyclical_2027_2029':{'cycle':1},
'structural_2027_on':{'structural':1,'mult':.8,'g':.01,'g2':.01,'capital':1.08,'spread':.005,'exit':20},
'optimistic_2027_on':{'mult':1.12,'g':.06},'capital_10pct_2027':{'capital':1.1},
'funding_plus100bp_2027_on':{'spread':.01},'upstream_delayed_two_years':{'delay':2},
'maturity_release_delayed_to2037':{'start':11},'no_tax_expiry_after2030':{'taxreset':False},
'nonsec_capacity_50pct':{'capacity':.5},'nonsec_capacity_zero_until_exit':{'capacity':0.,'exit':20},
'principal_recovery_delayed_10years':{'realize':11},'principal_recovery_half_then_balance':{'recovery':.5},
'parent_negative_2027':{'negative':1},
'liquidity_failure':{'zero':1,'delay':2,'payment':3.314,'collection':3.4}}

def independent(c,N):
    g=c.get('g',.04);g2=c.get('g2',.03);mx=c.get('mult',1);km=c.get('capital',1);spread=c.get('spread',0);start=c.get('start',6)
    a,b,ka,kb,ua,ub,ra,rb,cash=84.,18.39849091709,80.,13.,31.,15.18415647965,3.81206356153,2.24775334314,3.3
    se,sk,su,principal,loan,portfolio=2.,1.8,.8,.2,1.5,.39849091709
    taxlossA=taxlossB=0.;risk=7.70456409331;opA=10.8;opB=3.4;rows=[]
    for y in range(1,N+1):
        gy=g if y<=5 else g2
        if y>1:opA*=1+gy;opB*=1+gy
        ta=.25 if c.get('taxreset',True) and y>=5 else .17
        opa=opA*(.75/.83 if ta==.25 else 1)*mx;opb=opB*mx
        if c.get('cycle'):
            if y<=2:opa*=.65;opb*=.75
            elif y==3:opa*=.85;opb*=.9
        if c.get('structural'):opa*=.97**min(y-1,5);opb*=.98**min(y-1,5)
        na=ka*(1+gy)*(km if y==1 else 1);nb=kb*(1+gy)
        scale=na/(80*km);debt=250*scale-na
        finance=(debt*(.018+spread)-170*scale*.018)*(1-ta)
        interestA=max(0,a-ka)*.015;interestB=max(0,b-kb)*.015
        pretax=(opa+interestA-finance)/(1-ta)
        taxA=max(0,pretax-taxlossA)*ta;taxlossA=max(0,taxlossA-max(0,pretax))+max(0,-pretax)
        pa=pretax-taxA
        subop=opb*.3/3.4;si=max(0,se-sk)*.015;subp=subop+si
        preB=(opb-subop+max(0,b-kb)*.015-si)/.83
        if c.get('negative')==y:preB=-5
        taxB=max(0,preB-taxlossB)*.17;taxlossB=max(0,taxlossB-max(0,preB))+max(0,-preB)
        own=preB-taxB
        if subp<0:subp/=.83
        pb=own+subp
        available=max(0,pa+min(0,ua));dr=min(max(0,6.35-ra),.1*available);ra+=dr;risk+=.2*available;ua+=pa-.2*available-dr
        ramp=min(1,max(0,(y-start+1)/10))
        want=.2*max(0,pa)
        if y>=start:want+=ramp*(max(0,pa-na+ka)+.12*max(0,a-ka)-want)
        if y<=c.get('delay',0):want=0
        up=max(0,min(want,a+pa-na,ua));gap=max(0,na-a-pa);a+=pa-up;ua-=up
        nsk=sk*(1+gy);dsk=nsk-sk
        eligible=max(0,subp-dsk)+(max(0,se-sk) if y>=c.get('realize',6) else 0)
        subpay=max(0,min(eligible*c.get('capacity',1),se+subp-nsk))
        subold=min(principal,max(0,subpay-max(0,subp-dsk)));principal-=subold
        su+=subp-subpay;se+=subp-subpay;sk=nsk
        parent=own+up+subpay
        dpr=min(max(0,S*.5-rb),.1*max(0,parent+min(0,ub)));rb+=dpr;ub+=parent-dpr
        rec=port=0
        if y>=c.get('realize',6):rec=loan*c.get('recovery',1);loan-=rec;port=portfolio*c.get('recovery',1);portfolio-=port
        ex=.001906*23.63 if y==1 else 0
        cash+=parent-(nb-kb-dsk)+rec+port+ex-(c.get('payment',0) if y==1 else 0)
        if y<=5:want=[1.8,2.2,2.7,3.2,3.8][y-1]
        else:
            early=3.8/16.311799145839785*(pa+pb)
            mature=max(0,pb+up-(nb-kb))+.12*max(0,b-kb)
            want=early+ramp*(mature-early)
        want+=rec+port+subold
        if c.get('zero'):want=0
        if y==1:cash-=c.get('collection',0);loan+=c.get('collection',0)
        d=max(0,min(want,cash-1,ub));cash-=d;ub-=d
        b+=pb+up+ex-d-(c.get('payment',0) if y==1 else 0)
        ka=na;kb=nb
        core=a-3.44114525163*scale
        fail=max(gap,1-cash,2*14*ka/80-core,.16*250*scale-core,0)
        rows.append(dict(sec_equity=a,other_equity=b,sec_up=ua,parent_up=ub,parent_cash=cash,sec_required=ka,other_required=kb,nonsec_economic_equity=se,nonsec_economic_required=sk,ordinary_dividend=d,distribution_per_share=d/S,sec_tax=taxA,parent_tax=taxB,sec_risk=risk,sec_upstream_dividend=up,parent_legal_profit=parent,receivable_collection=rec,financial_principal_sale=port,group_profit=pa+pb,sec_stat=ra,parent_stat=rb,nonsec_accumulated_economic_earnings=su,debt=debt,gross=250*scale))
        rows[-1].update(year=2026+y,sec_operating_profit=opa,other_operating_profit=opb,
            sec_surplus_income=interestA,other_surplus_income=interestB,
            incremental_financing_cost_after_tax=finance,sec_reserve_add=dr+.2*available,
            parent_stat_add=dpr,nonsec_economic_profit=subp,nonsec_reserve_NOT_APPLICABLE=0.,
            nonsec_economic_payment=subpay,parent_direct_profit=own,exercise_cash=ex,
            realized_old_principal=rec+port+subold,sec_risk_add=.2*available,
            nonsec_economic_upstream=subpay,nonsec_legal_capacity_assumption=c.get('capacity',1),
            sec_external_funding=debt-loan,sec_external_and_internal_funding=debt,
            sec_operating_gross_assets=250*scale,sec_surplus_assets=a-ka,
            sec_base_funding_cost=debt*.018,capital_funding_gap=fail,core_net_capital=core,
            risk_capital_requirement=14*ka/80,risk_coverage=core/(14*ka/80),
            capital_leverage=core/(250*scale),parent_receivable=loan,
            tax_loss_sec=taxlossA,tax_loss_parent=taxlossB,financial_principal=portfolio,
            nonsec_original_principal=principal)
        if fail>1e-8:return dict(feasible=False,rows=rows)
        if c.get('exit')==y:
            # Two-level net realization, full external AND internal loan settlement
            sec_realized=debt+a-.02*250*scale
            sec_remaining=max(0,sec_realized-debt-1)
            dividend=min(max(0,ua)+ra,sec_remaining)
            capital_tax=max(0,sec_remaining-dividend-40.51227686503)*.25
            other=max(0,b-1-.15*se)
            proceeds=sec_remaining-capital_tax+other
            rows[-1]['ordinary_dividend']+=proceeds;rows[-1]['distribution_per_share']+=proceeds/S
            return dict(feasible=True,finite=True,rows=rows)
    return dict(feasible=True,rows=rows)

def price(p,rate,g=.03):
    if not p['feasible']:return None
    ds=[r['distribution_per_share'] for r in p['rows']];n=len(ds)
    terminal=0 if p.get('finite') else ds[-1]*(1+g)/(rate-g)
    pv=sum(d/(1+rate)**(i+1) for i,d in enumerate(ds))+terminal/(1+rate)**n
    tv=sum(ds[i]/(1+rate)**(i-4) for i in range(5,n))+terminal/(1+rate)**(n-5)
    return pv,tv

calc={name:independent(c,200) for name,c in CASES.items()}
convergence={n:{name:price(independent(c,n),.105,c.get('g2',.03)) for name,c in CASES.items()} for n in [120,160,200,260]}
endpoints={name:price(calc['base'],r) for name,r in [('low',.115),('high',.10)]}
envelope=json.loads(Path(__file__).with_name('2026-Q3-output.json').read_text())
canonical=gzip.decompress(base64.b64decode(envelope['payload_base64'],validate=True))
assert len(canonical)==envelope['full_output_bytes'] and hashlib.sha256(canonical).hexdigest()==envelope['full_output_sha256']
a=json.loads(canonical)
checks={};max_error=0
for name,p in calc.items():
    target=a['scenarios'][name]['path'];assert p['feasible']==target['feasible'],name
    assert len(p['rows'])==len(target['rows']),name
    err=0
    for l,r in zip(p['rows'],target['rows']):
        assert set(r)-set(l)<= {'exit','balance_basis'},(name,set(r)-set(l))
        for k,v in l.items():
            if k not in r:continue
            delta=abs(v-r[k]);err=max(err,delta)
            assert delta<1e-7,(name,k,delta,l,r)
    val=price(p,.105,CASES[name].get('g2',.03))
    if val:
        assert abs(val[0]-a['scenarios'][name]['value']['current_value'])<1e-9
        assert abs(val[1]-a['scenarios'][name]['value']['year5_value'])<1e-9
    max_error=max(max_error,err);checks[name]={'annual_max_absolute_difference_bn':err,'pv_tv':val,'rows':len(p['rows'])}
for name,v in endpoints.items():
    assert abs(v[0]-a['core_endpoints'][name]['current_value'])<1e-9
    assert abs(v[1]-a['core_endpoints'][name]['year5_value'])<1e-9
for n,ss in convergence.items():
    for name,v in ss.items():
        target=a['convergence'][str(n)][name]['value']
        assert (v is None)==(target is None)
        if v:assert abs(v[0]-target['current_value'])<1e-9
result=dict(status='PASS independent literal all scenarios and all 54 annual scalar fields; exit metadata covered by separate hand-value tests',checks=checks,endpoints=endpoints,convergence=convergence,max_absolute_annual_error_bn=max_error)
Path(__file__).with_name('independent-output.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
# Auxiliary independently typed, including gross recovery/full liability priority.
def alternative(rate,N,decay):
    e=102.39849091709-2.94609332017+.001906*23.63
    liquid=e-70;opening=liquid;value=0;loss=0
    for k in range(N):
        rev=16.2*(1-decay)**k;cost=5.69*(1-decay/2)**k
        pre=rev-cost;tax=max(0,pre-loss)*(.17 if k<4 else .25)
        loss=max(0,loss-max(0,pre))+max(0,-pre)
        debt_repaid=217.47028465007/N
        gross=debt_repaid+70/N
        returned=gross-debt_repaid
        old=opening/3 if k<3 else 0
        cash=pre-tax+.025*70*(1-k/N)+liquid*.015+returned+old-(2 if k==N-1 else 0)-.03*(returned+old)
        liquid-=old;value+=cash/(1+rate)**(k+1)
    return value/15.824105875
aux={k:alternative(r,n,d) for k,r,n,d in [('low',.115,12,.06),('high',.10,18,.03)]}
for k,v in aux.items():assert abs(v-a['auxiliary'][k]['value_per_share'])<1e-10
# Every future cash vintage rebuilt from the INDEPENDENT state trajectory.
cohort_checks={}
for name,p in calc.items():
    if not p['feasible']:continue
    for bucket,initial in [('securities',4.),('other',4.39849091709)]:
        lots=[[2026,initial,initial,0.]];previous=initial
        for k,row in enumerate(p['rows'],1):
            end=max(0,row['sec_equity']-row['sec_required']) if bucket=='securities' else max(0,row['other_equity']-row['other_required']-1)
            if p.get('finite') and k==len(p['rows']):end=0
            paid=row['sec_upstream_dividend'] if bucket=='securities' else row['ordinary_dividend']
            change=end-previous+paid
            if change>0:lots.append([2026+k,change,change,0.])
            consumed=paid-min(0,change)
            for lot in lots:
                amount=min(lot[2],consumed);lot[2]-=amount;lot[3]+=amount;consumed-=amount
                if consumed<1e-10:break
            assert consumed<1e-6
            previous=end
        expected=a['scenarios'][name]['cohorts'][bucket]['vintages'];assert len(expected)==len(lots),(name,bucket)
        error=0
        for lot,v in zip(lots,expected):
            assert lot[0]==v['origin']
            for ix,key in [(1,'added'),(2,'left'),(3,'consumed')]:error=max(error,abs(lot[ix]-v[key]))
        assert error<1e-6,(name,bucket,error)
        cohort_checks[name+'/'+bucket]={'batch_count':len(lots),'max_absolute_difference_bn':error}
result['auxiliary']=aux;result['all_future_vintage_rebuild']=cohort_checks
Path(__file__).with_name('independent-output.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print('Auxiliary and all future financial-cash vintages: PASS')
