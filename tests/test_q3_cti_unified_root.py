"""Independent literal CTI ledger and real production boundaries after six-root rebuild."""
import json, importlib.util
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'research/companies/CN/300012/models'
def literal(rate=.09,g=.03,ret=.15,multiple=1,costmult=1,up=1,delay=.1,fee=.005,weak=False):
    n=1.682828214
    c=.61314537045+.36761189194+.28+.01011858241-.45-.03-.067-.06524846766
    p=.15;s=c-p;r=2.96728214377-.084141411;reserve=.48845025728
    ar=.21451912125;past=0;flows=[];records=[];profit=0;release=0
    for y in range(1,401):
        if y<6:
            profit=[1.30,1.43,1.54,1.65,1.75][y-1]*multiple
            investment=[.76,.77,.76,.70,.68][y-1]*costmult
        else:
            growth=([.02]*5 if weak else [.05,.045,.04,.035,.03])[y-6] if y<11 else g
            investment=profit*growth/ret;profit=profit*(1+growth)
            if y>10:investment=profit*g/ret
        free=profit-investment
        old=p+s;ip=p*.015;isub=s*.015;p+=ip;s+=isub
        pp=(.4+.04*(y-1))*multiple if y<6 else .32*profit
        own=([.20,.22,.24,.26,.28][y-1]*multiple-[.04,.03,.03,.03,.03][y-1]*costmult) if y<6 else free*.25
        p+=own;s+=free-own
        sep=profit-pp
        if y<6:
            declaration=min([.30,.32,.36,.40,.44][y-1]*multiple*up,.85*sep)
            request=[.23,.25,.28,.31,.34][y-1]*up
        else:
            request=s*(1-delay)
            declaration=min(.85*sep*up+isub+past/5,request)
        past+=sep+isub-declaration
        ar+=declaration
        transfer=max(0,min(request,s,ar));ar-=transfer;s-=transfer
        tax=transfer*fee if y>5 else 0
        p+=transfer-tax
        legal_profit=pp+declaration+ip-tax
        reserve_add=.1*max(0,legal_profit+min(0,r)) if reserve<.5*n else 0.
        reserve+=reserve_add;r+=legal_profit-reserve_add
        if y==6:release=old
        if y<6:target=[.23,.26,.29,.32,.35][y-1]*n
        else:
            target=free*min(1,.5+.1*(y-5))+(release/5 if y<11 else 0)
            if y>=11:target=max(target,p)
        distribution=max(0,min(target,r,p));p-=distribution;r-=distribution
        flows.append(distribution/n);records.append((p+s,r,reserve))
    pv=sum(d/(1+rate)**(i+1) for i,d in enumerate(flows))
    tv=sum(d/(1+rate)**(i+1-5) for i,d in enumerate(flows) if i>=5)
    return {'pv':pv,'tv5':tv,'dps':flows[:5],'cash_y5':records[4][0],'minimum_retained':min(x[1] for x in records),'records':records}

def test_cti_independent_full_tail():
    expected={'base':literal(),'core_low':literal(rate=.095,g=.025,ret=.14),'core_high':literal(rate=.085,ret=.16),'sensitivity_roi12':literal(ret=.12),'structural_weak':literal(rate=.10,g=.015,ret=.10,multiple=.8,costmult=1.15,up=.75,delay=.25,fee=.02,weak=True)}
    production=json.loads((P/'2026-Q3-output.json').read_text())
    for key,e in expected.items():
        o=production['cases'][key]
        assert e['pv']==pytest.approx(o['value_per_share'],abs=1e-10)
        assert e['tv5']==pytest.approx(o['terminal_share_y5'],abs=1e-10)
        assert e['dps']==pytest.approx(o['dps'],abs=1e-10)
        for independent,actual in zip(e['records'],o['annual']):
            assert independent==pytest.approx((actual['group_extra_cash_end'],actual['parent_retained_end'],actual['statutory_reserve_end']),abs=1e-7)

def test_cti_all_scenario_future_cash_realization():
    production=json.loads((P/'2026-Q3-output.json').read_text())
    for key,c in production['cases'].items():
        assert c['feasible']
        for row in c['annual'][20:]:
            assert row['parent_cash_end']==pytest.approx(0,abs=1e-8)
            # Source residual is an actively rotating settlement buffer, not profits trapped forever.
            assert row['subsidiary_economic_cash_end'] <= row['earnings']*.41
        r=c['parameters']['k']
        assert c['value_per_share']==pytest.approx(sum(d/(1+r)**(i+1) for i,d in enumerate(c['dps']))+c['terminal_share_y5']/(1+r)**5)

def test_cti_actual_model_function_boundaries():
    spec=importlib.util.spec_from_file_location("cti_final",P/"2026-Q3.py")
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    checks={}
    def check(name,condition,detail):
     assert condition,(name,detail)
     checks[name]=detail
    r=m.owner_cash_step(0,5,20,10,100,100,paid_capital=10)
    check('registered_not_paid_threshold',r['reserve_add']==1 and r['paid']==9,r)
    r=m.owner_cash_step(-8,0,20,10,100,100);check('loss_first',abs(r['reserve_add']-.2)<1e-10 and abs(r['paid']-1.8)<1e-10,r)
    r=m.owner_cash_step(0,10,20,10,100,100);check('full_can_stop',r['reserve_add']==0,r)
    r=m.owner_cash_step(0,10,20,10,100,100,True);check('full_may_continue',r['reserve_add']==1,r)
    r=m.owner_cash_step(0,10,24,10,100,100);check('registered_conversion_changes_threshold',r['reserve_add']==1,r)
    # Already declared receivable increases cash only; same production payer function.
    r=m.owner_cash_step(0,0,20,0,10,10);check('old_receivable_cash_not_profit',r['paid']==0 and r['available_profit']==0,r)
    r=m.owner_cash_step(0,0,20,0,0,-1);check('no_invented_financing',r['cash']==-1,r)
    # Finite asset realizes principal without imaginary earnings; costs and ownership are explicit.
    r=m.owner_cash_step(0,10,20,0,0,0,sale={'asset_proceeds':10,'basis':10,'cost':1,'tax_rate':.25,'ownership':.6},capital_return=5.4,paid_capital=20,shares=20,capital_authorized=True)
    check('finite_asset_principal_cost_minority_no_double_count',abs(r['capital_paid']-5.4)<1e-10 and abs(r['cash'])<1e-10 and abs(r['sale']['profit']+.6)<1e-10 and abs(r['ending_shares']-14.6)<1e-10,r)
    r=m.owner_cash_step(0,10,20,0,100,0,sale={'asset_proceeds':14,'basis':10,'cost':2,'tax_rate':.25,'ownership':.5},capital_return=5,paid_capital=20,shares=20,capital_authorized=True)
    check('gain_tax_principal_separated',abs(r['paid']-.75)<1e-10 and abs(r['capital_paid']-5)<1e-10 and r['cash']==0 and r['sale']['tax']==.25,r)
    r=m.owner_cash_step(0,10,20,0,0,5,capital_return=5,capital_authorized=False);check('capital_authorization_required',r['capital_paid']==0 and r['cash']==5,r)
    b=m.calc(); a=m.calc(roi=.12)
    check('roi_effective_year6',b['annual'][:5]==a['annual'][:5] and b['annual'][5]['investment']!=a['annual'][5]['investment'],{'base_year6':b['annual'][5]['investment'],'roi12_year6':a['annual'][5]['investment']})
    # Actual valuation-chain tests: no legal constraints binding is a measured result, not assumed.
    for n,args in [('base',{}),('structural',dict(k=.10,terminal_g=.015,roi=.10,e_scale=.8,investment_scale=1.15,tail_g=(.02,)*5,upstream_scale=.75,cash_delay=.25,friction=.02))]:
     c=m.calc(**args); d=m.calc(legal=False,**args)
     check('full_tail_'+n,c['feasible'] and all(x['parent_retained_end']>=0 for x in c['annual']),{'minimum_parent_retained':min(x['parent_retained_end'] for x in c['annual']),'law_delta':c['value_per_share']-d['value_per_share'],'last_cash':c['annual'][-1]['group_extra_cash_end']})
     check('D_TV_identity_'+n,abs(sum(x/(1+args.get('k',.09))**(i+1) for i,x in enumerate(c['dps']))+c['terminal_share_y5']/(1+args.get('k',.09))**5-c['value_per_share'])<1e-9,c['value_per_share'])
    z=m.calc(e_scale=.05,investment_scale=2)
    check('actual_calc_zero_payout_cannot_repair_insolvency',not z['feasible'] and any(x['distribution']==0 and x['group_extra_cash_end']<0 for x in z['annual']),{'feasible':z['feasible'],'first_year_cash':z['annual'][0]['group_extra_cash_end']})
