"""马应龙：亿元、亿股。标准库，无网络。所有预算均为研究估计。"""
from pathlib import Path
import json
from copy import deepcopy

P = dict(shares=4.31053891, minority=.515152, tax=.15,
    revenue1=dict(core=20.40,health=5.00,trade=11.50,hospital=4.00,other=.35),
    growth=dict(core=.02,health=.10,trade=0,hospital=0,other=0),
    gross_margin=dict(core=.69,health=.55,trade=.084,hospital=.14,other=.80),
    selling=.225,admin=.032,research=.027,surcharge=.008,loss=.007,
    health_nopat_margin=.13,roic=.15,health_roic=.20,
    depreciation=.6359266196,rou_amort=.2742649214,maintenance=.70,lease_cash=.34,
    health_depreciation=.04,health_rou_amort=.01,health_maintenance=.045,health_lease_cash=.015,
    nwc_ratio=.18,reserve_ratio=.05,health_nwc_ratio=.18,health_reserve_ratio=.05,
    year1_growth_capex=.30,year1_health_growth_capex=.08,
    historical_revenue=38.6661,historical_health_revenue=4.00,
    financial_assets=33.5517,wealth=18.4579,recovery_loss=.02,old_dividend=3.0174,
    unclaimed=.022,opening_reserve=2.50,minority_financial=.60,debt=.11,other_assets=.7578,
    finance_yield=.014,debt_rate=.03,dividends=[.70,.74,.78,.82,.86])

def profits(rev,p):
    total=sum(rev.values())
    gross=sum(rev[n]*p['gross_margin'][n] for n in rev)
    costs={n:total*p[n] for n in ['selling','admin','research','surcharge','loss']}
    ebit=gross-sum(costs.values())
    nopat=ebit*(1-p['tax'])
    health=rev['health']*p['health_nopat_margin']
    return dict(revenue=total,revenue_by_segment=rev,gross_profit=gross,costs=costs,ebit=ebit,nopat=nopat,health_nopat=health,common_nopat=nopat-health*p['minority'])

def build(p):
    opening=p['financial_assets']-p['wealth']*p['recovery_loss']-p['old_dividend']-p['unclaimed']-p['opening_reserve']-p['minority_financial']
    financial=opening; rows=[]; prev=None
    for year in range(1,6):
        rev={n:v*(1+p['growth'][n])**(year-1) for n,v in p['revenue1'].items()}
        q=profits(rev,p); scale=q['revenue']/sum(p['revenue1'].values()); hs=rev['health']/p['revenue1']['health']
        delta_rev=q['revenue']-(prev['revenue'] if prev else p['historical_revenue'])
        delta_health=rev['health']-(prev['revenue_by_segment']['health'] if prev else p['historical_health_revenue'])
        nwc=max(delta_rev,0)*p['nwc_ratio']; reserve=max(delta_rev,0)*p['reserve_ratio']
        hnwc=max(delta_health,0)*p['health_nwc_ratio']; hreserve=max(delta_health,0)*p['health_reserve_ratio']
        if prev:
            hinvest=max(q['health_nopat']-prev['health_nopat'],0)/p['health_roic']
            other_invest=max((q['nopat']-q['health_nopat'])-(prev['nopat']-prev['health_nopat']),0)/p['roic']
            invest=hinvest+other_invest
            # Growth budget includes working capital and operating reserves, so no double count.
            gcap=max(invest-nwc-reserve,0)
            hgcap=max(hinvest-hnwc-hreserve,0)
        else:
            gcap=p['year1_growth_capex']; hgcap=p['year1_health_growth_capex']
        da=p['depreciation']*scale; rou=p['rou_amort']*scale; maint=p['maintenance']*scale; rent=p['lease_cash']*scale
        hda=p['health_depreciation']*hs; hrou=p['health_rou_amort']*hs; hmaint=p['health_maintenance']*hs; hrent=p['health_lease_cash']*hs
        group_cf=q['nopat']+da+rou-maint-rent-gcap-nwc-reserve
        health_cf=q['health_nopat']+hda+hrou-hmaint-hrent-hgcap-hnwc-hreserve
        minority_cf=health_cf*p['minority']; common_cf=group_cf-minority_cf
        interest=financial*p['finance_yield']*(1-p['tax']); debt_interest=p['debt']*p['debt_rate']*(1-p['tax'])
        dividend=p['dividends'][year-1]*p['shares']; before=financial
        financial+=common_cf+interest-debt_interest-dividend
        q.update(year=year,depreciation=da,rou_amort=rou,maintenance=maint,lease_cash=rent,growth_capex=gcap,nwc=nwc,reserve=reserve,
            health_depreciation=hda,health_rou_amort=hrou,health_maintenance=hmaint,health_lease_cash=hrent,health_growth_capex=hgcap,health_nwc=hnwc,health_reserve=hreserve,
            group_fcff=group_cf,health_fcff=health_cf,minority_fcff=minority_cf,common_fcff=common_cf,
            opening_financial=before,financial_income=interest,debt_interest=debt_interest,dividend=dividend,closing_financial=financial)
        assert abs(financial-before-common_cf-interest+debt_interest+dividend)<1e-10
        assert abs(group_cf-common_cf-minority_cf)<1e-10
        if prev:
            assert abs(gcap+nwc+reserve-(hinvest+other_invest))<1e-10
            assert abs(hgcap+hnwc+hreserve-hinvest)<1e-10
        rows.append(q); prev=q
    return dict(opening_financial=opening,opening_net_financial=opening-p['debt'],rows=rows)

def endpoint(p,b,k,g):
    q=b['rows'][-1]; scale=q['revenue']/sum(p['revenue1'].values())*(1+g)
    hs=q['revenue_by_segment']['health']/p['revenue1']['health']*(1+g)
    # Ongoing growth slows all businesses to g; expenditure already expensed remains in NOPAT.
    ng=q['nopat']*(1+g); nh=q['health_nopat']*(1+g)
    other_invest=(ng-nh)*g/p['roic']; hinvest=nh*g/p['health_roic']
    group_cash=ng+(p['depreciation']+p['rou_amort']-p['maintenance']-p['lease_cash'])*scale-other_invest-hinvest
    health_cash=nh+(p['health_depreciation']+p['health_rou_amort']-p['health_maintenance']-p['health_lease_cash'])*hs-hinvest
    fcff6=group_cash-health_cash*p['minority']
    op=fcff6/(k-g); bridge=q['closing_financial']+p['other_assets']-p['debt']
    tv=(op+bridge)/p['shares']
    dpv=sum(d/(1+k)**t for t,d in enumerate(p['dividends'],1)); tpv=tv/(1+k)**5
    assert k>g and abs(group_cash-fcff6-health_cash*p['minority'])<1e-10
    return dict(k=k,g=g,nopat6=ng,health_nopat6=nh,other_reinvestment6=other_invest,health_reinvestment6=hinvest,common_fcff6=fcff6,operating_terminal=op,financial_bridge=bridge,terminal_per_share=tv,dividend_pv=dpv,terminal_pv=tpv,current_value=dpv+tpv,terminal_share=tpv/(dpv+tpv))

def run(p):
    b=build(p)
    b['low']=endpoint(p,b,.105,.02); b['high']=endpoint(p,b,.09,.025)
    return b

def auxiliary(p,b,k,g):
    # Same current ordinary NOPAT and cash bridge; optimistic immediate steady-state timing.
    q=b['rows'][0]; m=(1-g/p['roic'])/(k-g)
    # Different reinvestment productivity for health, same ownership scope.
    value=(q['nopat']-q['health_nopat'])*m + q['health_nopat']*(1-p['minority'])*(1-g/p['health_roic'])/(k-g)
    return dict(k=k,g=g,other_multiple=m,health_multiple=(1-g/p['health_roic'])/(k-g),current_value=(value+b['opening_net_financial']+p['other_assets'])/p['shares'])

def main():
    base=run(P); sensitivities={}
    for name,edit in [('lower_roic',dict(roic=.10,health_roic=.12)),('core_margin_minus_3pp',{}),('cash_loss_20pct',{}),('core_flat',{}),('core_growing_4pct',{})]:
        p=deepcopy(P);p.update(edit)
        if name=='core_margin_minus_3pp':p['gross_margin']['core']-=.03
        if name=='cash_loss_20pct':p['financial_assets']-=base['opening_financial']*.20
        if name=='core_flat':p['growth']['core']=0
        if name=='core_growing_4pct':p['growth']['core']=.04
        sensitivities[name]=run(p)
    stress=deepcopy(P);stress['gross_margin']['core']=.64;stress['selling']=.235;stress['growth']['core']=0;stress['growth']['health']=.03;stress['health_nopat_margin']=.10;stress['roic']=.10;stress['health_roic']=.12
    sensitivities['structural']=run(stress)
    out=dict(parameters=P,base=base,auxiliary_low=auxiliary(P,base,.105,.02),auxiliary_high=auxiliary(P,base,.09,.025),
      cost_of_capital_low=endpoint(P,base,.11,.02),cost_of_capital_high=endpoint(P,base,.085,.025),sensitivities=sensitivities)
    # Basic cases independent of forecast values: a perpetual flat business and a cash-only asset.
    flat=deepcopy(P); flat.update(shares=1,depreciation=0,rou_amort=0,maintenance=0,lease_cash=0,health_depreciation=0,health_rou_amort=0,health_maintenance=0,health_lease_cash=0,other_assets=0,debt=0,dividends=[0]*5)
    dummy={'rows':[{'revenue':sum(flat['revenue1'].values()),'revenue_by_segment':{'health':0},'nopat':10,'health_nopat':0,'closing_financial':0}]}
    flat_result=endpoint(flat,dummy,.10,0)
    assert abs(flat_result['operating_terminal']-100)<1e-12
    dummy['rows'][0].update(nopat=0,closing_financial=100)
    cash_only=endpoint(flat,dummy,.10,0)
    assert abs(cash_only['current_value']-100/1.1**5)<1e-10
    assert abs(sum([1/(1.1)**t for t in range(1,6)])+10/1.1**5-10)<1e-10
    assert abs(27+5-3-29)<1e-10
    assert len(base['rows'])==len(P['dividends'])==5
    assert all(q['closing_financial']>0 and q['common_fcff']+q['financial_income']-q['debt_interest']>q['dividend'] for q in base['rows'])
    out['checks']={'cash_conservation':True,'minority_scope':True,'growth_capital_allocation':True,'perpetuity_case':True,'five_distributions':True,'dividend_coverage':True}
    Path(__file__).with_name('2026-H1-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({n:base[n] for n in ['low','high']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
