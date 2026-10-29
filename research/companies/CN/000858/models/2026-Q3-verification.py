#!/usr/bin/env python3
"""Independent recalculation plus actual production-function hand cases; stdlib only."""
import importlib.util,copy,json,math,tempfile,subprocess,sys,gzip,base64,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('valuation',P/'2026-Q3.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

INDEPENDENT_FACTS={'shares_issued': 3881608005, 'treasury_shares': 21753438, 'post_q3_buyback_cash': 0.40001113095, 'cash_equivalents': 108.63124653495, 'monetary': 111.72980995956, 'old_dividends_payable': 2.12458530952, 'nci_book': 2.5198060925, 'other_current_liability': 23.76726500238, 'reg_goods_latest_H1': 4.5069221677, 'parent_cash_H1': 56.97642199697, 'parent_retained_H1': 40.95815603573, 'parent_reserve': 20.271654476, 'parent_registered_capital': 3.881608005, 'parent_receivable_dividend_H1': 0.53424809295, 'sales_registered_capital': 0.2, 'sales_ownership': 0.95, 'sales_profit_H1': 5.00338154234}
INDEPENDENT_PARAMETERS={'volume': [23000, 24300, 25600, 26700, 27500], 'realization': [1.4, 1.4, 1.41, 1.42, 1.42], 'other_wine': [7.0, 7.2, 7.4, 7.7, 7.9], 'non_wine': [3.0, 3.0, 3.05, 3.1, 3.1], 'gm_core': [0.865, 0.865, 0.87, 0.87, 0.87], 'gm_other': [0.59, 0.6, 0.6, 0.61, 0.61], 'gm_non': 0.1, 'selling': [0.205, 0.2, 0.195, 0.19, 0.185], 'admin': [0.055, 0.054, 0.053, 0.052, 0.052], 'rd': 0.008, 'excise': 0.148, 'tax': 0.25, 'common_share': 0.974, 'capex': [2.4, 2.4, 2.3, 2.2, 2.0], 'da': [1.1, 1.15, 1.2, 1.25, 1.3], 'nwc': [4.7, 4.9, 5.1, 5.3, 5.5], 'opening_nwc': 4.5, 'required_cash': [15.0, 15.3, 15.6, 15.9, 16.2], 'opening_required_cash': 15.0, 'reg_unwind': [0.12, 0.2, 0.25, 0.23, 0.2], 'reg_asset_haircut': 0.0, 'payout': [0.75, 0.75, 0.75, 0.75, 0.75], 'minimum_dividend': [20.0, 0.0, 0.0, 0.0, 0.0], 'buyback_cash': [6.39926982752, 0.0, 0.0, 0.0, 0.0], 'buyback_retired': [0.042376463992583276, 0.0, 0.0, 0.0, 0.0], 'sales_profit_fraction': 0.56, 'upstream_fraction': 0.65, 'upstream_lag': 1, 'parent_open_cash': 45.0, 'parent_open_retained': 40.5, 'parent_floor': 5.0, 'sales_reserve_budget_start': 0.0, 'parent_internal_funding': [0.6, 0.6, 0.6, 0.6, 0.6], 'parent_extra_loss': [0.0, 0.0, 0.0, 0.0, 0.0], 'parent_admin': 0.3, 'lease_cash': [0.32, 0.32, 0.32, 0.32, 0.32], 'opening_net_dta': 7.27383302850504, 'dta_release_budget': [1.2, 1.2, 1.2, 1.2, 1.2], 'cash_loss': [0.0, 0.0, 0.0, 0.0, 0.0], 'extra_group_capex': [0.0, 0.0, 0.0, 0.0, 0.0], 'parent_dividend_receivable_open': 0.53424809295, 'minority_cash_budget': 2.5, 'associate_open': 2.25, 'cash_yield': 0.012, 'associate_yield': 0.04, 'term_asset_maturity_year': 3, 'r': 0.09, 'g': 0.015, 'g6': 0.03, 'roic': 0.18, 'release': 0.125, 'other_access_start_year': 6, 'other_upstream_fraction': 0.65, 'transfer_friction': 0.02, 'equity_issuance': 0.0, 'new_debt': 0.0, 'financial_loss_parent_share': 0.5}

def close(a,b):assert math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-9),(a,b)
def independently_recalculate(p):
    # Separate implementation from parameters, not from official output rows.
    f=INDEPENDENT_FACTS;c=p['common_share'];n=(3881608005-21753438)/1e9; C=f['cash_equivalents']-f['old_dividends_payable']-p['minority_cash_budget']-f['post_q3_buyback_cash']
    T=(f['monetary']-f['cash_equivalents'])*c;A=p['associate_open'];N=p['opening_nwc']
    L=(f['other_current_liability']-f['reg_goods_latest_H1']*(1-p['reg_asset_haircut']))*c;L0=L
    taxasset=p['opening_net_dta'];PC=p['parent_open_cash']-f['post_q3_buyback_cash'];R=p['parent_open_retained'];SR=0.;SF=p['sales_reserve_budget_start'];Q=[]; ds=[];last=None; O=0.
    for i in range(5):
        cr=p['volume'][i]/1000*p['realization'][i];rev=cr+p['other_wine'][i]+p['non_wine'][i]
        eb=cr*p['gm_core'][i]+p['other_wine'][i]*p['gm_other'][i]+p['non_wine'][i]*p['gm_non']-rev*(p['selling'][i]+p['admin'][i]+p['rd']+p['excise'])
        op=(eb-max(eb,0)*p['tax'])*c;interest=(C+T)*p['cash_yield'];earn=op+interest+A*p['associate_yield']-p['cash_loss'][i]
        out=min(L,L0*p['reg_unwind'][i]);L-=out
        taxrel=min(taxasset,p['dta_release_budget'][i],max(eb,0)*p['tax']*c);taxasset-=taxrel
        cf=op+interest+A*p['associate_yield']-((p['capex'][i]+p['extra_group_capex'][i]-p['da'][i]+p['nwc'][i]-N+p['lease_cash'][i])*c)-out-p['cash_loss'][i]+taxrel
        C+=cf-p['buyback_cash'][i]
        if i+1==p['term_asset_maturity_year']:C+=T;T=0
        n-=p['buyback_retired'][i]
        sp=op*p['sales_profit_fraction']/f['sales_ownership']
        available=max(0,sp-max(0,-SR));alloc=min(max(0,.5*f['sales_registered_capital']-SF),available*.1);SF+=alloc;SR+=sp-alloc
        declare=min(max(SR,0),max(sp-alloc,0)*p['upstream_fraction'])*f['sales_ownership']
        lag=p['upstream_lag'];pending=sum(Q[max(0,len(Q)-lag):]) if lag else 0.
        declare=min(declare,max(0,C-PC-max(p['required_cash'][i]-p['parent_floor'],0)-pending))
        SR-=declare/f['sales_ownership'];Q.append(declare)
        O+=op*(1-p['sales_profit_fraction'])+max(interest-PC*p['cash_yield'],0)+A*p['associate_yield']-p['cash_loss'][i]*(1-p['financial_loss_parent_share'])
        recv=Q[i-p['upstream_lag']] if i>=p['upstream_lag'] else 0
        own=PC*p['cash_yield']-p['parent_admin'];loss=p['cash_loss'][i]*p['financial_loss_parent_share']
        fee=recv*p['transfer_friction'];C-=fee
        R+=own+Q[-1]-p['parent_extra_loss'][i]-loss-fee # parent's actual disclosed reserve above threshold
        PC+=own+recv+(p['parent_dividend_receivable_open'] if i==0 else 0)-p['parent_internal_funding'][i]-loss-fee-p['buyback_cash'][i]
        div=max(0,min(max(max(earn,0)*p['payout'][i],p['minimum_dividend'][i]),max(0,C-p['required_cash'][i]),max(0,PC-p['parent_floor']),max(0,R)))
        C-=div;PC-=div;R-=div;ds.append(div/n);N=p['nwc'][i];last=(op,earn,div,eb)
    r=p['r'];op,earn,div,eb=last; req=p['required_cash'][-1];Llast=L;tailpv=0.;scale=1.
    for y in range(6,401):
        grow=p['g6']+(p['g']-p['g6'])*min(y-6,4)/4
        oldop=op;oldreq=req;oldcash=C;oldpc=PC;op*=1+grow;req*=1+grow;scale*=1+grow
        invest=(op-oldop)/p['roic']-(req-oldreq)
        interest=C*p['cash_yield'];ai=A*p['associate_yield'];sold=A*p['release'];cost=sold*p['transfer_friction'];A-=sold
        runoff=min(L,Llast/3) if y<=8 else 0.;L-=runoff
        tr=min(taxasset,p['dta_release_budget'][-1],max(op,0)*p['tax']/(1-p['tax']));taxasset-=tr
        C+=op+interest+ai-invest-runoff+tr+sold-cost-p['lease_cash'][-1]*p['common_share']*scale
        own=PC*p['cash_yield']-p['parent_admin']*scale
        sp=op*p['sales_profit_fraction']/f['sales_ownership'];oldSR=SR
        alloc=min(max(0,.5*f['sales_registered_capital']-SF),max(sp-max(-SR,0),0)*.1);SF+=alloc;SR+=sp-alloc
        oldO=O;other=op*(1-p['sales_profit_fraction'])+max(interest-PC*p['cash_yield'],0)+ai-cost;O+=other
        wantS=min(max(SR,0),max(sp-alloc,0)*p['upstream_fraction']+max(oldSR,0)*p['release'])*f['sales_ownership']
        wantO=min(max(O,0),max(other,0)*p['other_upstream_fraction']+max(oldO,0)*p['release']) if y>=p['other_access_start_year'] else 0.
        lag=p['upstream_lag'];pending=sum(Q[max(0,len(Q)-lag):]) if lag else 0
        cap=max(C-PC-max(req-p['parent_floor']*scale,0)-pending,0)
        fraction=min(1,cap/max(wantS+wantO,1e-20));dS=wantS*fraction;dO=wantO*fraction
        SR-=dS/f['sales_ownership'];O-=dO;Q.append(dS+dO)
        recv=Q[y-1-lag] if y-1>=lag else 0.;fee=recv*p['transfer_friction'];C-=fee
        R+=own+Q[-1]-fee;PC+=own+recv-fee
        target=max(op+interest+ai-cost-fee,0)*p['payout'][-1]+max(oldcash-oldreq,0)*p['release']
        div=min(target,max(C-req,0),max(PC-p['parent_floor']*scale,0),max(R,0))
        C-=div;PC-=div;R-=div;tailpv+=div/(1+r)**(y-5)
    return sum(d/(1+r)**(i+1) for i,d in enumerate(ds))+tailpv/n/(1+r)**5,ds,tailpv/n

def hand_cases():
    oldfacts=copy.deepcopy(m.FACTS);oldshares=m.SHARES
    try:
        m.SHARES=1.;m.FACTS.update(post_q3_buyback_cash=0.,cash_equivalents=0.,monetary=0.,old_dividends_payable=0.,other_current_liability=0.,reg_goods_latest_H1=0.,parent_registered_capital=0.,parent_reserve=0.,sales_registered_capital=0.,sales_ownership=1.)
        p=copy.deepcopy(m.BASE)
        p.update(volume=[10000]*5,realization=[1.]*5,other_wine=[0.]*5,non_wine=[0.]*5,
          gm_core=[1.]*5,gm_other=[0.]*5,gm_non=0.,selling=[0.]*5,admin=[0.]*5,rd=0.,excise=0.,tax=0.,
          common_share=1.,capex=[0.]*5,da=[0.]*5,nwc=[0.]*5,opening_nwc=0.,required_cash=[0.]*5,opening_required_cash=0.,
          payout=[1.]*5,minimum_dividend=[0.]*5,buyback_cash=[0.]*5,buyback_retired=[0.]*5,
          sales_profit_fraction=1.,upstream_fraction=1.,upstream_lag=0,parent_open_cash=0.,parent_open_retained=0.,parent_floor=0.,
          parent_internal_funding=[0.]*5,parent_dividend_receivable_open=0.,minority_cash_budget=0.,associate_open=0.,cash_yield=0.,associate_yield=0.,
          transfer_friction=0.,parent_admin=0.,lease_cash=[0.]*5,opening_net_dta=0.,dta_release_budget=[0.]*5,r=.1,g=0.,g6=0.,roic=.2)
        x=m.run_model(p);close(x['current_value_per_share'],100);assert x['dividends_per_share']==[10.]*5;close(x['terminal_value_per_share'],100)
        # Cash principal isn't discarded when distributions are zero; earns 2% and
        # requests 10%/year after year 5, with sufficient parent retained profits.
        # Cash earns 2%, so outstanding falls 8%; exact geometric sum.
        m.FACTS.update(cash_equivalents=100.,monetary=100.)
        p.update(volume=[0.]*5,payout=[0.]*5,parent_open_cash=100.,parent_open_retained=100.,cash_yield=.02,release=.1)
        x=m.run_model(p);close(x['current_value_per_share'],100*(1.02/1.1)**5*.10/(.1+.1-.02))
        return {'perpetuity_value':100,'cash_principal_case':x['current_value_per_share']}
    finally:m.FACTS.clear();m.FACTS.update(oldfacts);m.SHARES=oldshares

def main():
    close(60945321083.57-30307593428.60,30637727654.97)
    close(21511276550.29-15036724758.11,6474551792.18)
    close(28416674541.77+4441799422.57,32858473964.34)
    close(8752942991.31+957704479.72,9710647471.03)
    close(124114690633.67+46684115.79-629696415.76-14900431798.75,108631246534.95)
    manual=hand_cases();p=copy.deepcopy(INDEPENDENT_PARAMETERS);p.update(volume=[22500,23500,24500,25100,25500],realization=[1.38]*5,r=.095,g=.01,g6=.02,roic=.15,release=.10);a=m.run_model(p);b=independently_recalculate(p);close(a['current_value_per_share'],b[0]);close(a['terminal_value_per_share'],b[2])
    q=copy.deepcopy(INDEPENDENT_PARAMETERS);q['r']+=.01;c=m.run_model(q);d=independently_recalculate(q);close(c['current_value_per_share'],d[0])
    q2=copy.deepcopy(INDEPENDENT_PARAMETERS);q2['realization']=[x*.9 for x in q2['realization']];close(m.run_model(q2)['current_value_per_share'],independently_recalculate(q2)[0])
    ret,res,add=m.reserve_step(-3,0,10,2);assert (ret,res,add)==(-1,0,0)
    ret,res,add=m.reserve_step(ret,res,10,5);close(ret,3.6);close(add,.4)
    ret,res,add=m.reserve_step(0,4.9,10,100);close(add,.1);close(res,5.)
    output=m.make_outputs()
    independent_all={}
    for label,v in {**output['scenarios'],**output['sensitivities']}.items():
        independent_value,independent_dps,independent_terminal=independently_recalculate(v['parameters'])
        close(v['current_value_per_share'],independent_value);close(v['terminal_value_per_share'],independent_terminal)
        for actual,expected in zip(v['dividends_per_share'],independent_dps):close(actual,expected)
        independent_all[label]={'value':independent_value,'terminal':independent_terminal,'dps':independent_dps}
    for v in list(output['scenarios'].values())+list(output['sensitivities'].values()):
        assert len(v['rows'])==5
        previous_shares=v['opening_shares_bn']
        for row in v['rows']:
            close(row['shares_end'],previous_shares-row['buyback_retired']);previous_shares=row['shares_end']
            assert row['dividend']<=row['actual_constraints']['parent_profit']+1e-8
            assert row['dividend']<=row['actual_constraints']['parent_cash']+1e-8
            close(row['cash_end'],row['cash_start']+row['economic_fcf']+row['term_matured']-row['dividend']-row['buyback_cash'])
            assert row['sales_reserve_end']<=.1+1e-8
        for tail in [v['terminal_components'],v['auxiliary_components']['continuation']]:
            assert tail['residual_pv_upper_bound']/v['shares_bn']<1e-6
            assert len(tail['rows'])==395
            for z in tail['rows']:
                close(z['cash_end'],z['cash_start']+z['economic_fcf_before_upstream_friction']-z['upstream_friction']-z['dividend'])
                close(z['parent_cash_end'],z['parent_cash_start']+z['parent_direct']+z['receipt']-z['upstream_friction']-z['dividend'])
                assert z['parent_cash_end']<=z['cash_end']+1e-8
                assert z['dividend']<=min(z['parent_cash_capacity'],z['parent_profit_capacity'])+1e-8
                assert z['declaration']<=z['subsidiary_cash_capacity']+1e-8
        if v['rows'][0]['parent_old_receivable_received']:

            close(v['rows'][0]['parent_old_receivable_received'],.53424809295)
    gov=output['scenarios']['finance_governance_stress'];assert gov['rows'][0]['dividend']<20
    assert gov['terminal_value_per_share']<output['scenarios']['repair_case']['terminal_value_per_share']
    assert output['scenarios']['structural_adverse']['terminal_value_per_share']<gov['terminal_value_per_share']
    with tempfile.TemporaryDirectory() as td:
        td=Path(td);(td/'2026-Q3.py').write_bytes((P/'2026-Q3.py').read_bytes());other=td/'other';other.mkdir()
        subprocess.run([sys.executable,str(td/'2026-Q3.py')],cwd=other,check=True,stdout=subprocess.DEVNULL)
        packed=json.loads((td/'2026-Q3-output.json').read_text());raw=gzip.decompress(base64.b64decode(packed['data']))
        assert hashlib.sha256(raw).hexdigest()==packed['uncompressed_sha256'];assert len(raw)==packed['uncompressed_bytes']
        standalone=json.loads(raw);assert standalone==output
        expected=(json.dumps(m.pack_output(output),ensure_ascii=False,indent=2)+'\n').encode()
        assert (td/'2026-Q3-output.json').read_bytes()==expected
        assert not (other/'2026-Q3-output.json').exists()
        subprocess.run([sys.executable,str(td/'2026-Q3.py'),'--expand'],cwd=other,check=True,stdout=subprocess.DEVNULL)
        assert json.loads((td/'2026-Q3-output.expanded.json').read_text())==output
    result={'status':'fresh_local_checks_passed_not_independent_acceptance','manual_production_chain_cases':manual,'independent_conditional_lower':b[0],
      'independent_r_plus_1pp':d[0],'independent_realization_minus_10pct':independently_recalculate(q2)[0],
      'independent_all':independent_all,'scenario_count':len(output['scenarios']),'sensitivity_count':len(output['sensitivities']),
      'checks':['source arithmetic','50% statutory threshold','loss consumes legal profit','receivable cash vs income separation','cash conservation','buyback cash and share count','payer constraint lowers dividends and terminal','400-year cash/upstream/retained-profit continuation','terminal residual per-share bound below 0.000001 CNY','standalone copied-script different-cwd reproduction']}
    (P/'test-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
