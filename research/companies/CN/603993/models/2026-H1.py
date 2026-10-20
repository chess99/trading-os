"""CMOC: finite resource cash model; CNY 100m, tonnes, USD; no network."""
import json, copy
from pathlib import Path
S=213.94310176
D=[.32,.36,.40,.44,.48]
FX=7.1
OPEN_CASH=425.2284107039-20.8739127184+3.0005547945+10.0398352569+35.8574112474-150-25
BANK=358.6097022123+16.0853797653+5.98+2.6713968952
PARAMS={'low':dict(cu=10000,co=35000,gold=3300,k=.108,tfm_life=23), 'high':dict(cu=11000,co=40000,gold=3600,k=.098,tfm_life=25)}
def calc(p, copper_shift=0, capital_mult=1, quota_delay=False, tfm_life=None, uplink_delay=False, convert=False, permanent_quota=False, bank_share=1, minority_cash=25, cobalt_attribution=None):
    p=copy.deepcopy(p); p['cu']+=copper_shift
    life=tfm_life or p['tfm_life']; k=p['k']; shares=217.34 if convert else S; rows=[]; pool=OPEN_CASH+25-minority_cash; inventory=168397.; bank=BANK*bank_share
    for y in range(1,26):
        # Current installed copper and measured KFM addition; KFM physical resource envelope.
        tfm=540000 if y<=life else 0
        kfm=([260000,300000,330000]+[340000]*7+[220000,100000])[y-1] if y<=12 else 0
        q=tfm+kfm; owned_q=tfm*.8+kfm*.7125
        ow=owned_q/q if q else .8
        cu_revenue=q*p['cu']*FX/1e8
        cu_royalty=cu_revenue*.035
        tfm_cost_factor=1+min(.20,max(0,y-5)*.02)
        cu_cost=(tfm*3900*tfm_cost_factor+kfm*3900)*FX/1e8
        cu_sustain=q*700*FX/1e8
        # Depreciation ~ sustaining replacement, a cash-tax proxy; no second addback.
        cu_cash=(tfm*(p['cu']*.965-3900*tfm_cost_factor-700)*.8+kfm*(p['cu']*.965-3900-700)*.7125)*FX/1e8*.70
        production=q*.15
        if y<=5:
            sell=min(production,[30000,45000,60000,75000,90000][y-1])
            if quota_delay: sell*=.65
        elif y<=10: sell=min(production+max(0,inventory-100000),[100000,110000,120000,130000,132000][y-6])
        else: sell=min(production+30000,production+max(0,inventory-100000)) if q else inventory
        if permanent_quota: sell=min(sell,60000)
        if y==25 and not permanent_quota: sell=production+inventory
        # Price normalization and sold-metal unit cash include joint allocation; incremental stock absorbs 6000 USD/t.
        co_ow=ow if cobalt_attribution is None else cobalt_attribution
        co_cash=(sell*(p['co']*.9-13000)*FX/1e8)*.70*co_ow
        delta_inventory=production-sell
        inv_cash=-delta_inventory*6000*FX/1e8*co_ow
        inventory+=delta_inventory
        # Chinese and Brazilian mature segments, normal prices vs H1 and full sustaining.
        china=(13500*(500000-310000)/1e8*.85-4 if y<=20 else 0)+(6000*(650000-300000)/1e8*.85-1.5 if y<=15 else 0)
        brazil=((10500*(270000-170000)+1150000*(3700-3100))/1e8*.66-2.5) if y<=25 else 0
        gold=(7e6/31.1035*(p['gold']-2400)*FX/1e8*.66) if y<=18 else 0
        # Reserve conversion and mine-life extension are incremental to replacement.
        reserve_cap=(6 if y<=5 else 12 if y<=15 else 6) * capital_mult if tfm else 0
        other_extension=3*capital_mult if y<=20 else 0
        kfm_cap=[16,4.14,0,0,0][y-1] if y<=5 else 0 # USD 398m remaining * FX *.7125 =20.14 CNY100m
        gold_integration=[3,3,2,0,0][y-1] if y<=5 else 0
        odin_work=1 if y<=5 else 0
        old_engineering=[12,9.264,0,0,0][y-1] if y<=5 else 0
        growth=reserve_cap+other_extension+kfm_cap+gold_integration+odin_work+old_engineering
        # Existing prepayments cause sales recognized without fresh cash. No double debt deduction.
        prepay=105.4027040612*.7125/5 if y<=5 else 0
        stream=65.6391466892/18 if y<=18 else 0
        rights=([7.44419126,9.4972231973,0][y-1])*.8 if y<=3 else 0
        # IXM net trading profit before group financing 15, common overhead/compliance 18.
        operating_other=-3 if y<=life else -1
        interest=bank*.05*.75
        amort=BANK*bank_share/20 if y>=6 else 0
        bank-=amort
        cb=85 if y==1 and not convert else 0
        wc=[8,6,4,3,3][y-1] if y<=5 else 0
        # No assumed unrestricted sale of all minority cash; 25 reserved in opening bridge.
        # Odin existing paid asset option is explicitly valued net of uncertain development, no mine output invented.
        asset_recovery=20+7.94 if y==5 else 0
        if y==25: asset_recovery+=150+20.8739127184-50 # release operating/reserved cash net closure cash budget
        cash=cu_cash+co_cash+inv_cash+china+brazil+gold+operating_other-interest-growth-prepay-stream-rights-wc-amort-cb+asset_recovery
        dividend=(D[y-1]*shares if y<=5 else cash)
        if uplink_delay and y in [1,2]: dividend-=20
        if uplink_delay and y in [3,4]: dividend+=20
        pool_income=pool*.015 if y<=5 else 0
        if y<=5: pool=pool+cash+pool_income-dividend
        rows.append(dict(year=y,tfm_copper=tfm,kfm_copper=kfm,copper=cu_cash,cobalt=co_cash,cobalt_inventory_cash=inv_cash,cobalt_inventory_t=inventory,china=china,brazil=brazil,gold=gold,growth=growth,interest=interest,amortization=amort,convertible_repayment=cb,prepaid_delivery=prepay,stream=stream,rights=rights,wc=wc,asset_recovery=asset_recovery,cash=cash,dividend=dividend,pool_income=pool_income,pool=pool if y<=5 else None,bank=bank))
    residual=sum(r['cash']/(1+k)**(r['year']-5) for r in rows[5:])
    tv=(pool+residual)/shares
    value=sum(r['dividend']/shares/(1+k)**r['year'] for r in rows[:5])+tv/(1+k)**5
    assert abs(bank)<1e-8
    assert min(r['pool'] for r in rows[:5])>0
    assert abs(pool-(OPEN_CASH+25-minority_cash)-sum(r['cash']+r['pool_income']-r['dividend'] for r in rows[:5]))<1e-7
    assert abs(sum(r['amortization'] for r in rows)-BANK*bank_share)<1e-7
    assert sum(r['kfm_copper'] for r in rows)<=4008000*.90
    assert sum(r['tfm_copper'] for r in rows)<=29573000*.85
    assert permanent_quota or abs(inventory)<1e-7
    return dict(parameters=p,rows=rows,terminal_operating=residual,terminal_cash=pool,terminal_per_share=tv,value_per_share=value,terminal_pv_fraction=(tv/(1+k)**5)/value)

results={key:calc(p) for key,p in PARAMS.items()}
results['sensitivities']={key:{'copper_minus_1000':calc(p,copper_shift=-1000)['value_per_share'],'reserve_capital_double':calc(p,capital_mult=2)['value_per_share'],'quota_delay_first5':calc(p,quota_delay=True)['value_per_share'],'tfm_life_15':calc(p,tfm_life=15)['value_per_share'],'upstream_delay_40':calc(p,uplink_delay=True)['value_per_share'],'conversion':calc(p,convert=True)['value_per_share'],'permanent_60kt_cobalt_quota':calc(p,permanent_quota=True)['value_per_share'],'bank_77pct_attribution':calc(p,bank_share=.77)['value_per_share'],'minority_cash_68':calc(p,minority_cash=68)['value_per_share'],'cobalt_fixed_7125pct':calc(p,cobalt_attribution=.7125)['value_per_share'],'cobalt_fixed_80pct':calc(p,cobalt_attribution=.8)['value_per_share']} for key,p in PARAMS.items()}
# Auxiliary normalized run-off capitalization: mature Y5 underlying cash excluding financing principal,
# finite 15-year duration at same k, no perpetual growth, plus starting net liquid equity.
# This diagnostic omits explicit timing advantages of the primary path; independent economics check.
for key,p in PARAMS.items():
    r=results[key]['rows'][4]; mature=r['cash']-r['asset_recovery']+r['prepaid_delivery']+r['rights']+r['wc']-r['cobalt_inventory_cash']+r['interest']+r['stream']
    asset_rate=.097 if key=='low' else .088
    factor=(1-(1+asset_rate)**-15)/asset_rate
    net=OPEN_CASH-BANK-85-105.4027040612*.7125-65.6391466892-(7.44419126+9.4972231973)*.8+20+7.94
    results[key]['auxiliary']={'mature_cash':mature,'asset_rate':asset_rate,'factor':factor,'net_adjustment':net,'per_share':(mature*factor+net)/S}
results['independent_sensitivity_rows']={key:calc(p,copper_shift=-1000)['rows'] for key,p in PARAMS.items()}
results['opening_bridge']={'gross_cash':425.2284107039,'restricted_excluded_until_closure':20.8739127184,'cash_like_products':48.8978012988,'operating_cash_retained':150,'minority_cash_buffer':25,'opening_cash_pool':OPEN_CASH,'bank_principal':BANK,'convertible_y1':85,'trade_receivables_not_cash':101.3908765303,'other_financial_asset_recovery_y5':7.94}
results['distributions_per_share']=D
parent_cash=38.4550060684; legal=33.9861064717; legal_stress=legal; parent=[]
for i,(div_up,extra) in enumerate(zip([35,45,55,65,75],[15,15,2,0,0])):
    paid=D[i]*S
    legal+=35+div_up-paid
    legal_stress+=(35+div_up)*.9-paid
    assert legal_stress>=0
    parent_cash+=32+div_up+(18.0234153341 if i==0 else 0)-extra-paid
    assert parent_cash>=0 and legal>=0
    parent.append(dict(year=i+1,own_profit=35,new_dividend_declared_and_received=div_up,old_dividend_receivable_collected=18.0234153341 if i==0 else 0,own_cash_after_capital=32,net_intercompany_and_extra_funding=extra,common_dividend=paid,ending_legal_profit=legal,ending_legal_profit_after_10pct_reserve=legal_stress,ending_cash=parent_cash))
results['parent_budget']=parent
assert abs(sum([100/1.1,100/1.21])-100*(1-1.1**-2)/.1)<1e-9
assert 6000*15<=103000*.90
assert 7*18<=156*.85
results['self_checks']={'cash_conservation':True,'bank_principal_once':True,'physical_resource_ceiling':True,'no_perpetuity':True,'known_case':sum([100/1.1,100/1.21])}
Path(__file__).with_name('2026-H1-output.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({key:{x:v for x,v in r.items() if x!='rows'} for key,r in results.items() if key in PARAMS},ensure_ascii=False,indent=2))
print(json.dumps(results['sensitivities'],ensure_ascii=False,indent=2))
