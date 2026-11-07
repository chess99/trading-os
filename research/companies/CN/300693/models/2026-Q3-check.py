"""Independent base endpoint/financial bridge recalculation. Does not import model.
Uses raw input JSON, different loop structure, then compares the official concise output.
"""
from pathlib import Path
import json,math
P=Path(__file__).resolve().parent
j=json.loads((P/'2026-Q3-inputs.json').read_text(encoding='utf8'))
f=j['facts'];a=j['assumptions'];official=json.loads((P/'2026-Q3-output.json').read_text(encoding='utf8'))
w=f['wc_components'];working=sum(w.values())-2*sum(w[k] for k in ['accounts_payable','bills_payable','contract_liability'])
revenue=a['revenue0'][:];fixed=f['fixed_operating_q3'];floor=sum(revenue)*a['cash_floor_ratio']
bank=f['cce_q3']-f['minority_book_q3']-f['first_repurchase_cash']
mother=f['cce_q3']*f['parent_cce_h1']/f['group_cce_h1']-f['first_repurchase_cash']
deposits=f['term_deposit_h1'];mdeposits=a['parent_term_budget']
legal=f['parent_re_h1']-f['h1_paid_in_september'];gre=f['common_re_q3']
n=f['issued_shares']-f['treasury_at_cutoff'];cumulative=0.;records=[];late_margin_delta={}
fees_left=f['grant_full_fair_value']*.6-f['sbc_recognised_q3']
fees=[fees_left*x/sum(a['sbc_future_full_weights']) for x in a['sbc_future_full_weights']]
for year in range(1,17):
    if year==6:fixed_intensity=fixed/sum(revenue)
    if year<=5:
        gr=a['growth5'][year-1];margins=a['gross5'][year-1];expense=a['opex5'][year-1]
        mother_share=a['parent_op_share5'][year-1];positive_share=a['subs_positive_profit_share5'][year-1]
    else:
        t=min((year-5)/10,1)
        gr=[x*(1-t)+a['long_growth']*t for x in a['growth5'][-1]]
        margins=[x*(1-t)+z*t for x,z in zip(a['gross5'][-1],a['gross_mature'])]
        expense=a['opex5'][-1]*(1-t)+a['opex_mature']*t
        mother_share=a['parent_op_share5'][-1]*(1-t)+a['parent_op_share_mature']*t
        positive_share=a['subs_positive_profit_share5'][-1]*(1-t)+a['subs_positive_profit_share_mature']*t
    previous_sales=sum(revenue);revenue=[x*(1+g) for x,g in zip(revenue,gr)];sales=sum(revenue)
    operating=sum(x*m for x,m in zip(revenue,margins))-sales*expense
    mother_nopat=operating*mother_share*(1-a['parent_tax'])
    tax=max(operating*mother_share,0)*a['parent_tax']+max(operating*(1-mother_share),operating*positive_share,0)*a['subs_tax']
    profit=operating-tax-max(operating,0)*(1-a['subs_tax'])*a['other_minority_profit_fraction']
    new_working=sales*a['wc_ratio'];change=new_working-working
    depreciation=sales*a['da_ratio']
    investment=sales*a['capex_ratio']+a['committed_capex'][year-1] if year<=5 else depreciation+(sales-previous_sales)*fixed_intensity
    fcf=profit+depreciation-investment-change
    new_floor=sales*a['cash_floor_ratio'];free=fcf-(new_floor-floor)
    fixed+=investment-depreciation;working=new_working;floor=new_floor
    if year<=5:
        allocated=f['first_grant_shares']*[.3,.3,.4][year-1]*.6 if year<=3 else 0
        price=f['grant_price_less_paid_dividends']-cumulative;proceeds=allocated*price;n+=allocated
        repurchase=a['new_repurchase_budget_total']-f['first_repurchase_cash'] if year==1 else 0
        if year==1:n-=repurchase/a['new_repurchase_average_price_budget']
        if year==4:n+=f['treasury_at_cutoff']+(a['new_repurchase_budget_total']-f['first_repurchase_cash'])/a['new_repurchase_average_price_budget']
        income=bank*a['cash_yield_aftertax']+deposits*a['term_yield_aftertax']
        mincome=mother*a['cash_yield_aftertax']+mdeposits*a['term_yield_aftertax']
        debt=f['debt_and_lease_q3'] if year==1 else 0;md=f['parent_bank_debt_h1'] if year==1 else 0
        intcost=debt*.04*(1-a['parent_tax']);mintcost=md*.04*(1-a['parent_tax'])
        recovery=f['non_operating_investment_book_q3']*a['investment_recovery']*(1-a['investment_fee'])*(1-a['investment_gross_tax_reserve']) if year==a['investment_realisation_year'] else 0
        disposal_profit=recovery-f['non_operating_investment_book_q3'] if recovery else 0
        matured=deposits if year==a['term_maturity_year'] else 0;mmatured=mdeposits if matured else 0
        bank+=fcf+income-intcost+proceeds+matured-debt-repurchase+recovery
        mother+=mother_nopat+depreciation*a['parent_da_share']-investment*a['parent_capex_share']-change*a['parent_wc_share']+mincome-mintcost+proceeds+mmatured-md-repurchase+recovery
        deposits-=matured;mdeposits-=mmatured
        mother-=max(floor*(1-a['parent_cash_floor_share'])-(bank-mother),0)
        np=profit-fees[year-1]+income-intcost+disposal_profit
        mp=mother_nopat-fees[year-1]+mincome-mintcost+disposal_profit
        legal+=mp-max(mp,0)*a['voluntary_parent_reserve_fraction'];gre+=np
        paid=max(min(np*a['distribution_fraction'],bank-floor,gre,mother-floor*a['parent_cash_floor_share'],legal),0)
        bank-=paid;mother-=paid;legal-=paid;gre-=paid
        dps=paid/n;cumulative+=dps
        for key,actual in [('dps',dps),('cash',bank),('parent_cash',mother),('parent_re',legal),('shares',n),('fcf',fcf)]:
            assert math.isclose(actual,official['forecast5'][year-1][key],abs_tol=1e-7),(year,key,actual,official['forecast5'][year-1][key])
        if year==5:
            fifth_n=n;extra=bank+deposits-floor;parent_extra=mother+mdeposits-floor*a['parent_cash_floor_share'];child_extra=extra-parent_extra
    records.append((year,free))
    if year>=6:
        # Independent analytical derivative, compared with an actual full model rerun.
        late_margin_delta[year]=.02*sales*(1-mother_share*a['parent_tax']-positive_share*a['subs_tax']-(1-a['subs_tax'])*a['other_minority_profit_fraction'])

results=[];variation=[]
for r in [.11,.10]:
    # Year16 is first stable payment, hence perpetuity stands at year15.
    residual=sum(c/(1+r)**(year-5) for year,c in records if 6<=year<=15)
    residual+=records[-1][1]/(r-a['long_growth'])/(1+r)**10
    financial=(parent_extra+child_extra*a['child_extra_recovery'])*(1-a['terminal_financial_friction'])*((1+a['cash_yield_aftertax'])/(1+r))**a['terminal_financial_realisation_lag']
    terminal=(residual+financial)/fifth_n
    total=sum(row['dps']/(1+r)**row['year'] for row in official['forecast5'])+terminal/(1+r)**5
    results.append(total)
    pv_loss=sum(late_margin_delta[y]/(1+r)**y for y in range(6,16))
    pv_loss+=late_margin_delta[16]/(r-a['long_growth'])/(1+r)**15
    variation.append(total-pv_loss/fifth_n)
assert math.isclose(results[0],official['value_range']['low'],abs_tol=1e-8)
assert math.isclose(results[1],official['value_range']['high'],abs_tol=1e-8)
changed=official['scenarios']['mature_margin_minus_2pt_from_year6']['value_range']
assert math.isclose(variation[0],changed['low'],abs_tol=1e-8)
assert math.isclose(variation[1],changed['high'],abs_tol=1e-8)
print(json.dumps({'independent_value_range':results,'independent_margin_variation':variation,'independent_y5_extra_cash':extra,'independent_y5_parent_extra':parent_extra,'checks':'Every annual base operating FCF, five payments, share count, group/parent cash and legal profit, both DCF endpoints and a dominant margin parameter change passed.'},indent=2))
