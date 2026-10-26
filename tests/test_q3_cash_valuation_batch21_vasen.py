#!/usr/bin/env python3
"""Independent reconstruction from frozen source-budget only; no production imports or inspection.
First finishes separate arithmetic, only then opens delivered output for comparison.
Units billion CNY. Row 0 parent, rows 1..4 disclosed core subsidiaries.
"""
import json,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]/'research/companies/CN/002372/models'
B={'unit': 'CNY billion', 'shares': 1.571867988, 'registered_shares': 1.592037988, 'parent_cash': 1.45, 'parent_retained': 0.75, 'parent_reserve': 0.796038994, 'core_cash': [0.25, 0.1, 0.12, 0.08], 'core_capital': [0.32, 0.1, 0.08, 0.06], 'core_retained': [0.45, 0.18, 0.2, 0.1], 'core_profit_weights': [0.46, 0.19, 0.23, 0.12], 'core_initial_fixed': [0.9, 0.28, 0.32, 0.2], 'core_initial_nwc': [0.16, 0.07, 0.08, 0.04], 'revenue_year0': 4.95, 'revenue_year1': 4.9, 'margin_year1': 0.147, 'parent_cost_year1': 0.12, 'core_tax': 0.15, 'interest_yield': 0.012, 'parent_tax': 0.25, 'growth_2_to_5': [0.02, 0.03, 0.03, 0.025], 'margin_2_to_5': [0.148, 0.149, 0.15, 0.15], 'terminal_growth': 0.015, 'terminal_margin': 0.14, 'core_nwc_ratio': 0.07142857142857142, 'growth_fixed_ratio': 0.6, 'maintenance_ratio': 0.04081632653061224, 'committed_build': [0.1, 0.05], 'parent_settlement': [0.3, 0.2], 'parent_minimum_cash': 0.25, 'sub_minimum_cash': 0.3, 'jointventure_book': 0.36784975989, 'jointventure_proceeds': 0.3, 'jointventure_year': 5, 'other_investment_book': 0.555418655, 'other_investment_proceeds': 0.35, 'other_investment_year': 8, 'old_receivable_recovery': 0.03, 'old_receivable_year': 6, 'minority_cash_and_other_working_cash_excluded': 0.1308818324, 'ordinary_payout': 0.8, 'special_release_fraction': 0.2, 'discount_rates': [0.1, 0.085], 'forecast_start': '2026-10-26', 'notes': 'Independent literal research budget frozen BEFORE either valuation implementation. Not imported by production; independent verifier may read only this budget plus its own literal algorithms.', 'capital_release_year': 12, 'minimum_parent_capital': 0.5, 'shares_repurchased_pro_rata_at_par': 1.0, 'acquisition_payable': 0.00304348433}

def recompute(margin_adjustment=0):
    cash=[B['parent_cash']]+B['core_cash'][:]
    undistributed=[B['parent_retained']]+B['core_retained'][:]
    registered=[B['registered_shares']]+B['core_capital'][:]
    reserve=[B['parent_reserve']]+[x/2 for x in registered[1:]]
    nwc=[.16,.07,.08,.04]
    weights=B['core_profit_weights'];revenue=B['revenue_year0'];prior=revenue
    holder_cash=[];summaries=[];taxloss=[];group_earnings_pool=2.32064890364
    for period in range(1,241):
        if period==1:revenue=B['revenue_year1'];net_margin=B['margin_year1']
        elif period<6:
            revenue*=1+B['growth_2_to_5'][period-2];net_margin=B['margin_2_to_5'][period-2]
        else:
            fade=min(1.,(period-5)/5.)
            growth=B['growth_2_to_5'][-1]*(1-fade)+B['terminal_growth']*fade
            revenue*=1+growth
            net_margin=B['margin_2_to_5'][-1]*(1-fade)+B['terminal_margin']*fade
        net_margin+=margin_adjustment
        ratio=revenue/4.9
        settling=B['parent_settlement'][period-1] if period<3 else 0.
        cash[0]-=settling
        own=-B['parent_cost_year1']*ratio+cash[0]*B['interest_yield']
        taxloss=[(expiry,amount) for expiry,amount in taxloss if expiry>=period and amount>1e-12]
        if own<0:taxloss.append((period+5,-own));parent_tax=0.
        else:
            balance=own;remaining=[]
            for expiry,amount in taxloss:
                offset=min(balance,amount);balance-=offset;remaining.append((expiry,amount-offset))
            taxloss=remaining;parent_tax=balance*B['parent_tax']
        own-=parent_tax;cash[0]+=own
        group_profit=own;parent_profit=own;reserve_total=0.;subs_paid=[]
        for j,w in enumerate(weights,1):
            cash[j]+=settling*w
            taxed_profit=revenue*net_margin*w/(1-B['core_tax'])+cash[j]*B['interest_yield']
            profit=taxed_profit*(1-B['core_tax'])
            group_profit+=profit
            retained_before=undistributed[j]
            eligible=max(0.,profit-max(0.,-retained_before))
            allocate=min(.1*eligible,max(0.,registered[j]/2-reserve[j]))
            reserve[j]+=allocate;reserve_total+=allocate;undistributed[j]+=profit-allocate
            next_nwc=revenue*B['core_nwc_ratio']*w
            fixed_add=max(revenue-prior,0.)*B['growth_fixed_ratio']*w
            construction=B['committed_build'][period-1]*w if period<3 else 0.
            # Maintenance exactly offsets depreciation, therefore cancelled here rather than copied as FCF terms.
            cash[j]+=profit-fixed_add-construction-(next_nwc-nwc[j-1]);nwc[j-1]=next_nwc
            floor=B['sub_minimum_cash']*ratio*w
            paid=min(max(0.,undistributed[j]),max(0.,cash[j]-floor))
            cash[j]-=paid;undistributed[j]-=paid;cash[0]+=paid;parent_profit+=paid;subs_paid.append(paid)
        asset_profit=0.
        if period==1:cash[0]-=B['acquisition_payable']
        for original,proceeds,year in [(B['jointventure_book'],B['jointventure_proceeds'],B['jointventure_year']),
                                       (B['other_investment_book'],B['other_investment_proceeds'],B['other_investment_year'])]:
            if period==year:
                # Both are loss realisations under baseline and one-factor margin diagnostic.
                assert proceeds<=original
                cash[0]+=proceeds;asset_profit+=proceeds-original
        if period==B['old_receivable_year']:cash[0]+=B['old_receivable_recovery']
        parent_profit+=asset_profit
        eligible=max(0.,parent_profit-max(0.,-undistributed[0]))
        allocate=min(.1*eligible,max(0.,registered[0]/2-reserve[0]))
        reserve[0]+=allocate;undistributed[0]+=parent_profit-allocate
        group_earnings_pool+=group_profit+asset_profit-reserve_total-allocate
        floor=B['parent_minimum_cash']*ratio
        legal=min(max(0.,undistributed[0]),max(0.,group_earnings_pool))
        if period<6:
            ordinary=min(B['ordinary_payout']*max(0.,group_profit),legal,max(0.,cash[0]-floor))
            cash[0]-=ordinary;undistributed[0]-=ordinary;group_earnings_pool-=ordinary
            legal=min(max(0.,undistributed[0]),max(0.,group_earnings_pool))
            special=min(B['special_release_fraction']*max(0.,cash[0]-floor),legal)
            cash[0]-=special;undistributed[0]-=special;group_earnings_pool-=special
            payment=ordinary+special
        else:
            payment=min(legal,max(0.,cash[0]-floor))
            cash[0]-=payment;undistributed[0]-=payment;group_earnings_pool-=payment
        reduction=0.
        if period>=B['capital_release_year'] and undistributed[0]>=-1e-12:
            reduction=min(max(0.,cash[0]-floor),max(0.,registered[0]-B['minimum_parent_capital']))
            cash[0]-=reduction;registered[0]-=reduction
        payment+=reduction
        assert min(cash)>=0
        holder_cash.append(payment/B['shares'])
        summaries.append(dict(year=period,dps=payment/B['shares'],cash=sum(cash),parent_retained=undistributed[0],
                              parent_cash=cash[0],upstream=sum(subs_paid),capital_return=reduction))
        prior=revenue
    valuation=[]
    for discount in B['discount_rates']:
        today=0.;terminal=0.;first5=0.
        for t,payment in enumerate(holder_cash,1):
            today+=payment*pow(1+discount,-t)
            if t<=5:first5+=payment*pow(1+discount,-t)
            else:terminal+=payment*pow(1+discount,5-t)
        valuation.append(dict(pv=today,tv5=terminal,pv_first5=first5,r=discount))
    return dict(valuation=valuation,annual=summaries)


def test_vasen_independent_literal_cash_legal_and_margin():
 independent={'base':recompute(),'margin_minus_1pp':recompute(-.01)}
 # All estimates now completed. Output is read only as comparison oracle, never used to calculate.
 production=json.loads((ROOT/'2026-Q3-output.json').read_text())
 checks=[]
 for name,out in independent.items():
     delivered=production['scenarios'][name]
     for i in range(2):
         for key in ['pv','tv5','pv_first5']:
             error=out['valuation'][i][key]-delivered['valuation'][i][key]
             assert abs(error)<1e-9,(name,i,key,error)
             checks.append(dict(case=name,endpoint=i,metric=key,independent=out['valuation'][i][key],error=error))
     for a,b in zip(out['annual'],delivered['annual']):
         assert abs(a['dps']-b['dps'])<1e-9
         assert abs(a['cash']-b['cash'])<1e-8
         assert abs(a['parent_retained']-b['parent']['retained'])<1e-8

def test_vasen_actual_functions_registration_capital_and_original_holder():
 import runpy,copy
 m=runpy.run_path(str(ROOT/'2026-Q3.py'));m['tests']();d=m['boundary_diagnostics']()
 for z in d.values():assert z['status']=='infeasible' and z['pv'] is None and z['tv5'] is None
 assert d['positive_cash_floor']['opening_cash']>0
 rows=m['path'](m['BUDGET']);old=rows[10];new=rows[11]
 assert new['capital_return']>.8
 assert abs(old['parent']['capital']-new['parent']['capital']-new['capital_return'])<1e-9
 assert abs(new['current_outstanding_shares']/1.571867988-new['shares_per_initial_share'])<1e-10
 assert abs(new['distribution']/1.571867988-new['dps'])<1e-10
 assert abs(new['parent']['reserve']-.796038994)<1e-10
 for row in rows:
  for e,cap in zip(row['subsidiaries'],[.32,.10,.08,.06]):
   assert e['reserve']<=cap*.5+1e-9
   assert e['cash']-e['payable']>=.30*(row['revenue']/4.9)*[.46,.19,.23,.12][row['subsidiaries'].index(e)]-1e-7
 extended=m['path'](m['BUDGET'],300)
 assert extended[:240]==rows
 for r in [.10,.085]:
  for k in ['pv','tv5']:assert abs(m['value'](extended,r)[k]-m['value'](rows,r)[k])<1e-6

def test_vasen_registered_not_paid_in_and_unknown_opening_budget():
 import runpy,copy
 m=runpy.run_path(str(ROOT/'2026-Q3.py'))
 e=dict(re=0.,reserve=5.,registered_capital=20.,paid_capital=10.)
 assert m['accrue_legal'](e,10.)==1. and e['re']==9.
 b=copy.deepcopy(m['BUDGET']);b['subs_paid_ratio']=[.5]*4
 assert [r['dps'] for r in m['path'](b)]==[r['dps'] for r in m['path'](m['BUDGET'])]
 b=copy.deepcopy(m['BUDGET']);b.update(opening_reserve_full=False,subs_legal_opening=[0.]*4)
 z=m['value'](m['path'](b),.10)
 assert round(z['pv'],5)==4.76975  # Published diagnostic at five-decimal display precision, not independent proof.
 assert m['path'](b)[0]['dps']<m['path'](m['BUDGET'])[0]['dps']
