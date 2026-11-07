#!/usr/bin/env python3
"""Wuliangye 2026-Q3, standalone, stdlib only. All money = CNY bn.
Run from any cwd: python /path/2026-Q3.py [--out DIR]. Default output beside script.
Forecast/legal budgets are research estimates, NOT legal distributability certificates.
"""
from pathlib import Path
from copy import deepcopy
import argparse,json,gzip,base64,hashlib
SHARES=(3881608005-21753438)/1e9
FACTS={'shares_issued':3881608005,'treasury_shares':21753438,
 'post_q3_buyback_cash':0.40001113095,'buyback_paid_q3':1.20071904153,
 'buyback_paid_snapshot':1.60073017248,'post_q3_other_cash_budget':0.,
 'cash_equivalents':108.63124653495,'monetary':111.72980995956,
 'old_dividends_payable':2.12458530952,'nci_book':2.51980609250,
 'other_current_liability':23.76726500238,'reg_goods_latest_H1':4.50692216770,
 'parent_cash_H1':56.97642199697,'parent_retained_H1':40.95815603573,
 'parent_reserve':20.271654476,'parent_registered_capital':3.881608005,
 'parent_receivable_dividend_H1':0.53424809295,'sales_registered_capital':0.2,
 'sales_ownership':0.95,'sales_profit_H1':5.00338154234}

def reserve_step(retained,reserve,registered,profit):
    """Losses consume retained profits; 10% current profit after loss recovery,
    capped at 50% registered capital. Existing reserve is never invented."""
    recovery=min(max(-retained,0),max(profit,0))
    allocation=min(max(registered*.5-reserve,0),max(profit-recovery,0)*.1)
    return retained+profit-allocation,reserve+allocation,allocation

def terminal_value(state,p,constant_nopat=None):
    """Explicit payer continuation to year 400, not a frozen payout multiplier.
    Other-entity upstream budget is conditional economics, NOT certified legal profit.
    No terminal liquidation. Omitted infinite cashflows have a disclosed upper bound.
    """
    st=deepcopy(state); r=p['r']; rows=[]; pv=0.
    if constant_nopat is not None: st['nopat']=constant_nopat
    scale=1.; horizon=400
    for year in range(6,horizon+1):
        k=year-6
        growth=(p['g6']+(p['g']-p['g6'])*min(k,4)/4) if constant_nopat is None else 0.
        oldnopat=st['nopat']; oldrequired=st['required']; oldcash=st['cash']; oldpc=st['pc']
        st['nopat']*=1+growth; scale*=1+growth
        st['required']*=1+growth
        # Total growth capital includes necessary cash. Non-cash investment is
        # separately paid; increased necessary cash remains in the cash ledger.
        noncash_reinvestment=(st['nopat']-oldnopat)/p['roic']-(st['required']-oldrequired)
        interest=st['cash']*p['cash_yield']; ai=st['assoc']*p['associate_yield']
        sold=st['assoc']*p['release']; sale_friction=sold*p['transfer_friction']
        st['assoc']-=sold
        reg=min(st['legacy'],state['legacy']/3) if k<3 else 0.; st['legacy']-=reg
        taxrelease=min(st['dta'],p['dta_release_budget'][-1],max(st['nopat'],0)*p['tax']/(1-p['tax']) if p['tax']<1 else 0.)
        st['dta']-=taxrelease
        lease=p['lease_cash'][-1]*p['common_share']*scale if constant_nopat is None else 0.
        cf=st['nopat']+interest+ai-noncash_reinvestment-reg+taxrelease+sold-sale_friction-lease
        st['cash']+=cf
        parent_direct=st['pc']*p['cash_yield']-p['parent_admin']*scale
        old_sret=st['sret']; sales_profit=st['nopat']*p['sales_profit_fraction']/FACTS['sales_ownership']
        st['sret'],st['sres'],salloc=reserve_step(st['sret'],st['sres'],FACTS['sales_registered_capital'],sales_profit)
        # No invented registered capital or statutory reserve for the rest of the group.
        # This explicitly conditional economic earnings budget must first become
        # legally available, assumed in this experiment and NOT asserted as fact.
        other_profit=st['nopat']*(1-p['sales_profit_fraction'])+max(interest-st['pc']*p['cash_yield'],0)+ai-sale_friction
        old_oret=st['oret'];st['oret']+=other_profit
        sales_wanted=min(max(st['sret'],0),max(sales_profit-salloc,0)*p['upstream_fraction']+max(old_sret,0)*p['release'])*FACTS['sales_ownership']
        other_wanted=min(max(st['oret'],0),max(other_profit,0)*p['other_upstream_fraction']+max(old_oret,0)*p['release']) if year>=p['other_access_start_year'] else 0.
        lag=p['upstream_lag']; outstanding=sum(st['declarations'][max(0,len(st['declarations'])-lag):]) if lag else 0.
        subsidiary_cash_capacity=max(st['cash']-st['pc']-max(st['required']-p['parent_floor']*scale,0)-outstanding,0)
        allocation=min(1.,subsidiary_cash_capacity/max(sales_wanted+other_wanted,1e-20))
        sd=sales_wanted*allocation;od=other_wanted*allocation; declaration=sd+od
        st['sret']-=sd/FACTS['sales_ownership'];st['oret']-=od;st['declarations'].append(declaration)
        receipt=st['declarations'][year-1-lag] if year-1>=lag else 0.
        fee=receipt*p['transfer_friction'];st['cash']-=fee
        parent_profit=parent_direct+declaration-fee
        st['pret'],st['pres'],palloc=reserve_step(st['pret'],st['pres'],FACTS['parent_registered_capital'],parent_profit)
        st['pc']+=parent_direct+receipt-fee
        group_available=max(st['cash']-st['required'],0)
        target=max(st['nopat']+interest+ai-sale_friction-fee,0)*p['payout'][-1]+max(oldcash-oldrequired,0)*p['release']
        legal=max(st['pret'],0);pcap=max(st['pc']-p['parent_floor']*scale,0)
        dividend=min(target,group_available,pcap,legal)
        st['cash']-=dividend;st['pc']-=dividend;st['pret']-=dividend
        pv+=dividend/(1+r)**(year-5)
        assert min(st['cash'],st['pc'])>=-1e-8
        assert st['pc']<=st['cash']+1e-8
        rows.append(dict(year=year,nopat=st['nopat'],growth=growth,noncash_reinvestment=noncash_reinvestment,
          cash_start=oldcash,cash_end=st['cash'],required_cash=st['required'],lease_cash=lease,economic_fcf_before_upstream_friction=cf,
          parent_cash_start=oldpc,parent_cash_end=st['pc'],parent_direct=parent_direct,parent_profit=parent_profit,
          parent_retained=st['pret'],parent_reserve=st['pres'],parent_reserve_added=palloc,
          sales_reserve=st['sres'],sales_retained=st['sret'],other_economic_retained=st['oret'],
          declaration=declaration,receipt=receipt,upstream_friction=fee,subsidiary_cash_capacity=subsidiary_cash_capacity,
          dividend=dividend,dividend_target=target,parent_cash_capacity=pcap,parent_profit_capacity=legal,
          associate_principal_remaining=st['assoc'],associate_principal_sold=sold,asset_sale_friction=sale_friction,
          tax_asset_remaining=st['dta'],tax_asset_release=taxrelease,legacy_remaining=st['legacy']))
    # Generous bound permits immediate payment of all remaining capital plus an
    # unconstrained perpetual gross cash stream. It is NOT added as a liquidation.
    h=max(p['g'],p['g6'],p['cash_yield'],0.) if constant_nopat is None else max(p['cash_yield'],0.)
    assert r>h
    future_stream=max(st['nopat'],0)*(1+h)*(1+abs(h/p['roic']))+max(st['cash'],0)*p['cash_yield']+st['assoc']*p['associate_yield']
    bound=(max(st['cash'],0)+st['assoc']+st['dta']+future_stream/(r-h))/(1+r)**(horizon-5)
    return {'total':pv,'rows':rows,'residual_pv_upper_bound':bound,'horizon':horizon,
            'method':'explicit annual operating, upstream, payer cash/profit and capital-release budgets; no liquidation',
            'conditional_other_entity_legal_availability':True}

BASE={
 'volume':[23000,24300,25600,26700,27500], # core product, tonnes
 'realization':[1.40,1.40,1.41,1.42,1.42], # CNY million/tonne
 'other_wine':[7.,7.2,7.4,7.7,7.9], 'non_wine':[3.,3.,3.05,3.10,3.10],
 'gm_core':[.865,.865,.87,.87,.87], 'gm_other':[.59,.60,.60,.61,.61],
 'gm_non':.10,'selling':[.205,.200,.195,.190,.185],
 'admin':[.055,.054,.053,.052,.052],'rd':.008,'excise':.148,'tax':.25,
 'common_share':.974,'capex':[2.4,2.4,2.3,2.2,2.0], 'da':[1.10,1.15,1.20,1.25,1.30],
 'nwc':[4.7,4.9,5.1,5.3,5.5], 'opening_nwc':4.5,
 'required_cash':[15.,15.3,15.6,15.9,16.2], 'opening_required_cash':15.,
 'reg_unwind':[.12,.20,.25,.23,.20], 'reg_asset_haircut':0.,
 'payout':[.75]*5,'minimum_dividend':[20.,0.,0.,0.,0.],
 'buyback_cash':[8.-1.60073017248,0.,0.,0.,0.],
 'buyback_retired':[(8.-1.60073017248)/151.01,0.,0.,0.,0.], # official ceiling, not quote/value anchor
 'sales_profit_fraction':.56,'upstream_fraction':.65,'upstream_lag':1,
 'parent_open_cash':45.,'parent_open_retained':40.5,'parent_floor':5.,
 'sales_reserve_budget_start':0., # undisclosed: conservative *budget*, not fact
 'parent_internal_funding':[.6]*5,'parent_extra_loss':[0.]*5,
 'parent_admin':.30,'lease_cash':[.32]*5,'opening_net_dta':(7.51454158486-.04654052890)*.974,'dta_release_budget':[1.2]*5,
 'cash_loss':[0.]*5, 'extra_group_capex':[0.]*5,
 'parent_dividend_receivable_open':.53424809295,
 'minority_cash_budget':2.5,'associate_open':2.25,'cash_yield':.012,'associate_yield':.04,
 'term_asset_maturity_year':3,'r':.09,'g':.015,'g6':.03,'roic':.18,'release':.125,
 'other_access_start_year':6,'other_upstream_fraction':.65,'transfer_friction':.02,'equity_issuance':0.,'new_debt':0.,'financial_loss_parent_share':.5,
}

def run_model(p):
    p=deepcopy(p)
    assert p['equity_issuance']==0 and p['new_debt']==0
    common=p['common_share']
    # Q3 cash already includes Q3 repurchases; bridge only subsequent paid increment.
    cash=FACTS['cash_equivalents']-FACTS['old_dividends_payable']-p['minority_cash_budget']-FACTS['post_q3_buyback_cash']
    term=(FACTS['monetary']-FACTS['cash_equivalents'])*common
    assoc=p['associate_open']; required=p['opening_required_cash']; nwc=p['opening_nwc']
    legacy=(FACTS['other_current_liability']-FACTS['reg_goods_latest_H1']*(1-p['reg_asset_haircut']))*common
    opening_legacy=legacy; dta=p['opening_net_dta']
    # Parent cash inputs remain the original Q3-proxy budgets (including stresses).
    pc=p['parent_open_cash']-FACTS['post_q3_buyback_cash']; pret=p['parent_open_retained']; pres=FACTS['parent_reserve']
    sret=0.; sres=p['sales_reserve_budget_start']; declarations=[]; rows=[]; shares=SHARES; oret=0.
    for i in range(5):
        core=p['volume'][i]*p['realization'][i]/1000
        revenue=core+p['other_wine'][i]+p['non_wine'][i]
        gross=core*p['gm_core'][i]+p['other_wine'][i]*p['gm_other'][i]+p['non_wine'][i]*p['gm_non']
        ebit=gross-revenue*(p['selling'][i]+p['admin'][i]+p['rd']+p['excise'])
        # Losses receive no immediate tax refund: conservatism, no fictitious DTA cash.
        nopat=(ebit-max(ebit,0)*p['tax'])*common
        interest=(cash+term)*p['cash_yield']; assoc_income=assoc*p['associate_yield']
        profit=nopat+interest+assoc_income-p['cash_loss'][i]
        reg_out=min(legacy,opening_legacy*p['reg_unwind'][i]); legacy-=reg_out
        maturation=term if i+1==p['term_asset_maturity_year'] else 0.
        if maturation:term=0.
        capex=(p['capex'][i]+p['extra_group_capex'][i])*common
        reinvest=(capex-p['da'][i]*common)+(p['nwc'][i]-nwc)*common+p['lease_cash'][i]*common
        tax_release=min(dta,p['dta_release_budget'][i],max(ebit,0)*p['tax']*common);dta-=tax_release
        economic_fcf=tax_release+nopat+interest+assoc_income-reinvest-reg_out-p['cash_loss'][i]
        cash_before=cash; cash+=economic_fcf+maturation-p['buyback_cash'][i]; shares-=p['buyback_retired'][i]
        assert shares>0
        # Separate legal payer: new subsidiary declaration creates parent income;
        # receipt of past receivable creates cash only. No group income from upstream.
        sales_profit=nopat*p['sales_profit_fraction']/FACTS['sales_ownership']
        sret,sres,salloc=reserve_step(sret,sres,FACTS['sales_registered_capital'],sales_profit)
        sales_declaration=min(max(sret,0),max(sales_profit-salloc,0)*p['upstream_fraction'])
        sret-=sales_declaration
        common_declaration=sales_declaration*FACTS['sales_ownership']
        lag=p['upstream_lag']
        outstanding=sum(declarations[max(0,len(declarations)-lag):]) if lag else 0.
        capacity=max(cash-pc-max(p['required_cash'][i]-p['parent_floor'],0)-outstanding,0)
        if common_declaration>capacity:
            sret+=(common_declaration-capacity)/FACTS['sales_ownership'];common_declaration=capacity
        declarations.append(common_declaration)
        oret+=nopat*(1-p['sales_profit_fraction'])+max(interest-pc*p['cash_yield'],0)+assoc_income-p['cash_loss'][i]*(1-p['financial_loss_parent_share'])
        lag=p['upstream_lag']
        receipt=declarations[i-lag] if i>=lag else 0.
        old_receipt=p['parent_dividend_receivable_open'] if i==0 else 0.
        parent_direct=pc*p['cash_yield']-p['parent_admin']
        ploss=p['parent_extra_loss'][i]+p['cash_loss'][i]*p['financial_loss_parent_share']
        fee=receipt*p['transfer_friction'];cash-=fee;economic_fcf-=fee
        parent_profit=parent_direct+common_declaration-ploss-fee
        pret,pres,palloc=reserve_step(pret,pres,FACTS['parent_registered_capital'],parent_profit)
        parent_cash_before=pc
        parent_external_cash_loss=p['cash_loss'][i]*p['financial_loss_parent_share']
        pc+=parent_direct+receipt+old_receipt-p['parent_internal_funding'][i]-parent_external_cash_loss-fee
        pc-=p['buyback_cash'][i]
        target=max(max(profit,0)*p['payout'][i],p['minimum_dividend'][i])
        group_limit=max(cash-p['required_cash'][i],0)
        parent_cash_limit=max(pc-p['parent_floor'],0)
        legal_limit=max(pret,0)
        dividend=min(target,group_limit,parent_cash_limit,legal_limit)
        cash-=dividend;pc-=dividend;pret-=dividend
        assert cash>=-1e-9 and pc>=-1e-9
        assert abs(cash-(cash_before+economic_fcf+maturation-p['buyback_cash'][i]-dividend))<1e-8
        assert abs(pc-(parent_cash_before+parent_direct+receipt+old_receipt-p['parent_internal_funding'][i]-parent_external_cash_loss-fee-p['buyback_cash'][i]-dividend))<1e-8
        assert dividend<=max(pret+dividend,0)+1e-8
        required=p['required_cash'][i]; nwc=p['nwc'][i]
        rows.append(dict(year=i+1,revenue=revenue,core_revenue=core,ebit=ebit,common_operating_nopat=nopat,
           cash_interest=interest,associate_income=assoc_income,common_profit_budget=profit,
           capex=capex,net_reinvestment=reinvest,regulatory_net_cash_out=reg_out,
           economic_fcf=economic_fcf,tax_asset_release=tax_release,tax_asset_remaining=dta,term_matured=maturation,dividend=dividend,dps=dividend/shares,shares_end=shares,buyback_cash=p['buyback_cash'][i],buyback_retired=p['buyback_retired'][i],
           cash_start=cash_before,cash_end=cash,required_cash=required,excess_cash=cash-required,
           parent_cash_start=parent_cash_before,parent_cash_end=pc,parent_profit=parent_profit,parent_non_cash_impairment=p['parent_extra_loss'][i],parent_external_cash_loss=parent_external_cash_loss,
           parent_retained_end=pret,parent_reserve_end=pres,parent_reserve_added=palloc,
           sales_profit=sales_profit,sales_reserve_added=salloc,sales_reserve_end=sres,
           sales_retained_budget=sret,parent_declaration_income=common_declaration,
           parent_current_dividend_receipt=receipt,upstream_friction=fee,subsidiary_cash_capacity=capacity,other_economic_retained=oret,parent_old_receivable_received=old_receipt,
           parent_receivable_end=sum(declarations[max(0,i-lag+1):]),
           target_dividend=target,actual_constraints={'group':group_limit,'parent_cash':parent_cash_limit,'parent_profit':legal_limit},
           legacy_remaining=legacy))
    state=dict(nopat=rows[-1]['common_operating_nopat'],cash=cash,required=required,assoc=assoc,
        legacy=legacy,dta=dta,pc=pc,pret=pret,pres=pres,sret=sret,sres=sres,oret=oret,declarations=declarations)
    tv=terminal_value(state,p)
    pv_div=sum(x['dps']/(1+p['r'])**x['year'] for x in rows)
    pv_tv=tv['total']/shares/(1+p['r'])**5
    # Auxiliary no-growth year-3 owner earnings continuation. Same year-5 funds,
    # same actual first-five distributions, separate operating normalization.
    normalized=rows[2]['common_operating_nopat']-(p['capex'][2]-p['da'][2]+p['lease_cash'][2])*common
    aux=terminal_value(state,p,constant_nopat=normalized)
    epv=pv_div+aux['total']/shares/(1+p['r'])**5
    return {'parameters':p,'rows':rows,'terminal_components':tv,'current_value_per_share':pv_div+pv_tv,
            'terminal_value_per_share':tv['total']/shares,'dividends_per_share':[x['dps'] for x in rows],
            'pv_dividends':pv_div,'pv_terminal':pv_tv,'terminal_share':pv_tv/(pv_div+pv_tv),
            'auxiliary_epv_per_share':epv,'auxiliary_components':{'normalized_owner_earnings':normalized,'continuation':aux},
            'shares_bn':shares,'opening_shares_bn':SHARES,'opening_legacy_net':opening_legacy,'no_new_financing':True}

def scenarios():
    base=deepcopy(BASE);lo=deepcopy(base);hi=deepcopy(base)
    lo.update(volume=[22500,23500,24500,25100,25500],realization=[1.38]*5,r=.095,g=.01,g6=.02,roic=.15,release=.10)
    hi.update(volume=[23500,25000,26500,27900,29000],realization=[1.42,1.42,1.43,1.44,1.45],r=.085,g=.02,g6=.04,roic=.20,release=.15)
    cyc=deepcopy(base);cyc.update(volume=[18500,19500,22500,25000,27000],realization=[1.32,1.32,1.37,1.40,1.42],
       selling=[.24,.235,.215,.20,.19],other_wine=[5.8,6.,6.5,7.,7.5],nwc=[7.,8.,7.,6.,5.5],
       payout=[.6,.6,.7,.75,.75],reg_unwind=[.05,.10,.20,.25,.25],upstream_lag=2,
       parent_internal_funding=[2.,1.,.6,.6,.6],r=.095,g=.01,g6=.03,release=.1)
    bad=deepcopy(base);bad.update(volume=[18000,16000,15000,14500,14000],realization=[1.25,1.20,1.17,1.15,1.13],
       gm_core=[.84,.82,.80,.79,.78],gm_other=[.5]*5,other_wine=[5.5,5.,4.7,4.5,4.4],
       selling=[.25,.26,.27,.27,.27],admin=[.07,.075,.08,.08,.08],excise=.16,
       capex=[2.0,1.6,1.3,1.1,1.0],nwc=[7.,7.,6.,5.,4.],required_cash=[15,14,13,12,11],
       payout=[.50]*5,reg_unwind=[.40,.30,.20,.10,0],reg_asset_haircut=.35,
       parent_extra_loss=[3.,0,0,0,0],parent_internal_funding=[3,2,1,.5,.5],
       r=.105,g=-.01,g6=-.02,roic=.10,release=.08,upstream_fraction=.20,upstream_lag=2)
    bull=deepcopy(base);bull.update(volume=[25000,28000,31000,33500,35000],realization=[1.45,1.47,1.50,1.52,1.54],
       selling=[.19,.185,.18,.175,.17],other_wine=[8.,8.6,9.2,9.8,10.4],
       capex=[2.7,3.,3.,2.8,2.5],nwc=[5,5.5,6.,6.5,7.],required_cash=[15.5,16,17,18,19],
       r=.085,g=.025,g6=.05,roic=.22,release=.15,upstream_fraction=.65)
    gov=deepcopy(base);gov.update(cash_loss=[45.36217853685*.2,0,0,0,0],
          parent_open_cash=30.,parent_open_retained=25.,upstream_lag=3,release=.05)
    return {'repair_case':base,'conditional_lower':lo,'conditional_upper':hi,'cyclical_weak':cyc,'structural_adverse':bad,'optimistic':bull,'finance_governance_stress':gov}

def make_outputs():
    results={k:run_model(v) for k,v in scenarios().items()}
    sens={}
    for label,changes in {'r_minus_1pp':{'r':.08},'r_plus_1pp':{'r':.10},
        'core_realization_minus_10pct':{'realization':[x*.9 for x in BASE['realization']]},
        'cash_release_5pct':{'release':.05},'cash_release_25pct':{'release':.25},
        'no_new_upstream_sales':{'upstream_fraction':0},
        'other_upstream_deferred_to_year16':{'other_access_start_year':16},
        'repurchased_shares_double_ceiling_min':{'buyback_retired':[BASE['buyback_retired'][0]*2,0,0,0,0]},
        'extra_5bn_construction':{'extra_group_capex':[1]*5},
        'minority_cash_1_5':{'minority_cash_budget':1.5},'minority_cash_3_5':{'minority_cash_budget':3.5},
        'parent_cash_down_10bn':{'parent_open_cash':35.},
        'working_capital_plus_5bn':{'nwc':[x+5 for x in BASE['nwc']]}}.items():
        p=deepcopy(BASE);p.update(changes);sens[label]=run_model(p)
    return {'facts':FACTS,'scenarios':results,'sensitivities':sens,'units':'CNY bn except per-share, tonnes, realization million/tonne','source_cutoff':'2026-10-29T00:00:00Z','historical_research_cutoff':'2026-10-27T11:26:04Z'}

def pack_output(output):
    raw=json.dumps(output,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    return {'format':'gzip+base64-json-v1','units':output['units'],
      'summary':{k:{'conditional_value_per_share':v['current_value_per_share'],
        'conditional_terminal_per_share':v['terminal_value_per_share'],
        'conditional_distributions_per_share':v['dividends_per_share'],
        'auxiliary_value_per_share':v['auxiliary_epv_per_share'],
        'terminal_pv_fraction':v['terminal_share']} for k,v in output['scenarios'].items()},
      'uncompressed_bytes':len(raw),
      'uncompressed_sha256':hashlib.sha256(raw).hexdigest(),
      'description':'Lossless complete facts, parameters, 7 scenarios, 13 sensitivities and all annual rows. Use --expand for ordinary JSON.',
      'data':base64.b64encode(gzip.compress(raw,mtime=0)).decode('ascii')}

def main():
    a=argparse.ArgumentParser();a.add_argument('--out',type=Path,default=Path(__file__).resolve().parent)
    a.add_argument('--expand',action='store_true',help='also write complete uncompressed JSON next to packed output')
    args=a.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    out=make_outputs();(args.out/'2026-Q3-output.json').write_text(json.dumps(pack_output(out),ensure_ascii=False,indent=2)+'\n')
    if args.expand:(args.out/'2026-Q3-output.expanded.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:{'value':v['current_value_per_share'],'terminal':v['terminal_value_per_share'],'dps':v['dividends_per_share'],'epv':v['auxiliary_epv_per_share'],'terminal_share':v['terminal_share']} for k,v in out['scenarios'].items()},indent=2))
if __name__=='__main__':main()
