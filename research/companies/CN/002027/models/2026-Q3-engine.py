#!/usr/bin/env python3
"""分众传媒2026Q3；标准库、十亿元/十亿股。所有未来数是经济预算。
运行 python 2026-Q3.py；--expand输出完整年度行（默认文件已完整保存）。
"""
import json, math, pathlib, argparse
SHARES=14.442199726
NEW_SHARES=1.534540509
PARAMS=dict(revenue=12.2,margin=.43,tax=.20,growth=[.03,.03,.03,.02],g=.015,capex_net=.12,wc=.22,required=3.,yield_net=.015,release=.10,deal=True,full=False,delay=0,shock=0.,structural=False,upstream=.98,minority_reserve=.89487837921,normalized=False,asset_scale=1.)
# Initial financial amounts: liquid excludes restricted cash. All minority book equity
# is reserved from assets as a conservative allocation, not added again to operating value.
BRIDGE=dict(cash=3.37005689245,wealth=5.41729629228,deposit=.53050980819,other_deposit=.04,
 debt=.40,minority_asset_reserve=.89487837921,tax_realisation=.10,required=3.,
 risk_assets=(.08255321142+.68052811304+2.04129594824)*.80,disposal_receivable=.1842210)

def pv(cash,r):
    return sum(x/(1+r)**(i+1) for i,x in enumerate(cash))

def target_distribution(opening_budget, profit, available_cash, desired, capital_injection=0.):
    """Signed economic legal-profit budget. Capital is cash, never distributable profit.
    Positive profit first covers deficits; 10% of remaining profit retained as a budget,
    not a claim about each target entity's statutory reserve balance.
    """
    after_loss=opening_budget+profit
    reserve=.10*max(0.,min(profit,after_loss))
    before_payout=after_loss-reserve
    paid=min(max(0.,available_cash+capital_injection),max(0.,desired),max(0.,before_payout))
    return before_payout-paid,paid,reserve

def run(p=None,years=240):
    p=dict(PARAMS,**(p or {})); b=BRIDGE
    pool=b['cash']+b['wealth']+b['deposit']+b['other_deposit']-b['debt']-p['minority_reserve']-b['tax_realisation']-p['required']
    pool-=.09
    locked=(b['risk_assets']+b['disposal_receivable']+.09)*p['asset_scale'];pool*=p['asset_scale']; legal=7.99474198783
    # H1 statutory profit less Sept dividend, not asserted as an observed Q3 balance.
    old_claim=6.9; parent_cash=0.; shares=SHARES; required=p['required']; revenue=p['revenue']
    rows=[]; target_locked=0.; target_claim=.10804049573*(1. if p['full'] else .90022); target_pool=0.; statutory_reserve=4.44559442201;fund=0.
    for y in range(1,years+1):
        start=pool+locked+target_pool+target_locked+parent_cash+fund
        transaction=0.; acquired=0.; dilution=0.
        if y==2 and p['deal']:
            shares+=NEW_SHARES; dilution=NEW_SHARES
            own=1. if p['full'] else .90022
            transaction=.535225 if p['full'] else .0296495
            acquired=(1.87656154744-.5-.00052961208)*own*p['asset_scale']
            target_locked+=acquired
        prev=revenue
        if y>1:
            growth=p['growth'][y-2] if y<=5 else p['g']
            if p['normalized'] and y>=4:growth=p['g']
            revenue*=1+growth
        # Demand loss is temporary with explicit recovery or permanent with lower margin/growth.
        factor=1.
        if p['shock']:
            factor=1-p['shock']*(1 if p['structural'] else {1:1.,2:.7,3:.35}.get(y,0))
        effective=revenue*factor
        previous_effective=rows[-1]['revenue'] if rows else effective
        margin=p['margin']-(.04 if p['structural'] else (.035*(1-factor)/max(p['shock'],.0001) if p['shock'] else 0))
        # Cash rent, sales/admin/R&D, normal bad debts all included in margin.
        profit=effective*margin*(1-p['tax'])-.04
        growth_capital=p['wc']*max(0,effective-previous_effective)
        req_new=p['required']*(effective/p['revenue'])
        req_change=req_new-required;required=req_new
        reinvest=p['capex_net']*(effective/p['revenue'])+growth_capital+req_change
        legacy_cf=profit-reinvest
        own=1. if p['full'] else .90022
        target_profit=0.;target_cf=0.
        if p['deal'] and y>=2:
            # Modest operating integration, no price-rise synergy; excluded financial yield.
            target_profit=(.06*1.10**min(y-2,4)*(1+p['g'])**max(y-6,0))*own
            if p['normalized'] and y>=4:target_profit=.066*(1+p['g'])**(y-3)*own
            if p['structural']:target_profit=-.04*own*(1+p['g'])**(y-2)
            elif p['shock']:target_profit*=factor
            target_cf=target_profit-.02*own*(1+p['g'])**max(y-2,0)
        legacy_interest=pool*p['yield_net'];target_interest=target_pool*p['yield_net']
        interest=legacy_interest+target_interest
        locked_income=locked*.01+target_locked*.01+fund*.01
        locked*=1.01;target_locked*=1.01;fund*=1.01
        # Assets mature over ten years, not immediate mother-company cash.
        conversion=0.
        if y>=6:
            conversion=locked*.20;locked-=conversion
        target_conversion=0.
        if y>=10:
            target_conversion=target_locked*.20;target_locked-=target_conversion
        fund_purchase=.20 if y==1 else 0.
        pool+=legacy_cf+legacy_interest+conversion-transaction-fund_purchase
        fund+=fund_purchase
        fund_release=fund*.2 if y>=11 else 0.
        fund-=fund_release;pool+=fund_release
        target_pool+=target_cf+target_interest+target_conversion
        target_support=max(0.,-target_pool)
        if target_pool<0:pool+=target_pool;target_pool=0.
        # Target cash can only migrate with profit/reserve support; retained cash remains valued.
        target_claim,target_up,target_reserve=target_distribution(target_claim,target_profit+target_interest,target_pool,max(0,target_cf+target_interest)+(target_pool*.10 if y>=10 else 0))
        target_pool-=target_up;pool+=target_up
        declaration=max(profit+legacy_interest,0)*p['upstream']+target_up
        reserve_add=min(declaration*.10,max(0,.50*shares-statutory_reserve))
        statutory_reserve+=reserve_add
        legal_add=declaration-reserve_add # parent statutory budget, future declarations conditional
        legal+=legal_add
        old_claim+=declaration
        desired=.80*max(legacy_cf+target_cf,0) if y<=5 else max(legacy_cf+target_cf,0)+pool*p['release']
        # Delay test: upstream capacity disrupted, never assumes group cash equals parent cash.
        upstream_cap=max(0,legacy_cf+target_up)+max(0,pool)*p['release']
        if y<=p['delay']:upstream_cap=0.
        receipt=min(max(pool,0),old_claim,upstream_cap,max(0,desired-parent_cash))
        pool-=receipt;parent_cash+=receipt;old_claim-=receipt
        dividend=min(max(desired,0),parent_cash,max(legal,0))
        parent_cash-=dividend;legal-=dividend
        if pool < -1e-8:raise AssertionError('unfunded scenario: adjust dividends/capital')
        end=pool+locked+target_pool+target_locked+parent_cash+fund
        assert abs(end-(start+legacy_cf+target_cf+interest+locked_income+acquired-transaction-dividend))<1e-7*max(1,end)
        rows.append(dict(year=y,revenue=effective,margin=margin,profit=profit,target_profit=target_profit,
          target_profit_budget=target_claim,target_reserve_budget=target_reserve,target_capital_support=target_support,target_upstream=target_up,reinvestment=reinvest,required_operating_cash=required,legacy_cf=legacy_cf,target_cf=target_cf,
          financial_income=interest+locked_income,acquired_financial=acquired,transaction_cash=transaction,
          shares=shares,new_shares=dilution,dividend=dividend,dps=dividend/shares,
          ending_free_pool=pool,ending_locked=locked+target_locked+fund,ending_target_pool=target_pool,
          parent_cash=parent_cash,fund_purchase=fund_purchase,legal_budget=legal,old_claim_budget=old_claim,actual_upstream_budget=receipt,
          opening_financial=start,ending_financial=end))
    def val(r,from_year=0):
        # Explicit 240-year convergence; tail economic claims are retained, not discarded.
        c=[z['dps'] for z in rows[from_year:]]
        last=rows[-1];tail=(last['legacy_cf']+last['target_cf'])*(1+p['g'])/(r-p['g'])/shares+last['ending_financial']/shares
        return pv(c,r)+tail/(1+r)**len(c)
    return dict(parameters=p,years=rows,value_low=val(.10),value_high=val(.09),terminal_y5_low=val(.10,5),terminal_y5_high=val(.09,5),
                distributions=[r['dps'] for r in rows[:5]],terminal_pv_share_low=val(.10,5)/(1.10**5)/val(.10))

def tests():
    # Production discount function: exact five coupons and terminal known hand result.
    assert abs(pv([10,10,10,10,110],.1)-100)<1e-10
    # Production complete waterfall: one-year no growth, no acquisition, literal expected cash and dividend.
    t=run({'deal':False,'growth':[0]*4,'g':0},1)['years'][0]
    cf=12.2*.43*.8-.04-.12
    assert abs(t['legacy_cf']-cf)<1e-12
    assert abs(t['dividend']-.8*cf)<1e-12
    initial=3.37005689245+5.41729629228+.53050980819+.04-.4-.89487837921-.1-3-.09
    locked=(.08255321142+.68052811304+2.04129594824)*.8+.184221+.09
    expected=initial+locked+cf+initial*.015+locked*.01-.8*cf
    assert abs(t['ending_financial']-expected)<1e-12
    # Same target-distribution function: nonzero cash capital cannot repair accounting loss.
    q,paid,retained=target_distribution(.10,-.30,.20,1.,capital_injection=.50)
    assert abs(q+.20)<1e-12 and paid==0 and retained==0
    q,paid,retained=target_distribution(q,.15,.70,1.)
    assert abs(q+.05)<1e-12 and paid==0 and retained==0
    q,paid,retained=target_distribution(q,.10,.80,1.)
    assert abs(q)<1e-12 and abs(paid-.045)<1e-12 and abs(retained-.005)<1e-12
    return {'loss_capital_recovery_case':{'opening_profit_budget':.1,'loss':-.3,'capital_cash':.5,'after_loss_budget':-.2,'first_profit':.15,'first_dividend':0,'second_profit':.1,'second_reserve':.005,'second_dividend':.045},'production_pv_hand_case':100,'production_waterfall_hand_cf':cf,'production_waterfall_hand_distribution':.8*cf,'production_waterfall_hand_financial':expected,'cash_conservation':'every year every scenario asserted'}

def main():
    scenarios={'base':{},'cyclical':{'shock':.15,'delay':1},'structural':{'shock':.25,'structural':True,'g':0.,'capex_net':.20,'upstream':.9},'optimistic':{'revenue':12.6,'margin':.45,'growth':[.04]*4,'g':.02},'no_deal':{'deal':False},'full_deal':{'full':True},'upstream_delay_2y':{'delay':2},'margin_minus_2pp':{'margin':.41},'fund_release_half':{'release':.05},'minority_asset_allocation':{'minority_reserve':.55}}
    out={'units':'CNY billion and billion shares, per share CNY','bridge':BRIDGE,'tests':tests(),'scenarios':{k:run(v) for k,v in scenarios.items()}}
    # Second method: normalize at Y3; derive a capitalization multiple from cash conversion,
    # g and risk, then explicitly reconcile actual minority-holder payout/asset recovery.
    normal=run({'normalized':True});zero_assets=run({'normalized':True,'asset_scale':0.})
    n=normal['years'][2]['profit']+normal['years'][2]['target_profit']
    share=normal['years'][2]['shares'];f4=normal['years'][3]['legacy_cf']+normal['years'][3]['target_cf']
    secondary={}
    for name,r in [('low',.10),('high',.09)]:
        # Growing operating CF except fixed .04 minority operating earnings deduction.
        cap=(f4+.04)/(r-.015)-.04/r
        pure=pv([(x['legacy_cf']+x['target_cf'])/x['shares'] for x in normal['years'][:3]],r)+cap/share/(1+r)**3
        constrained=zero_assets['value_'+name]
        actual=normal['value_'+name]
        secondary[name]={'cost_of_equity':r,'g':.015,'profit_y3':n,'cash_y4':f4,
          'derived_PE':cap/n,'capitalized_operating_value':pure,
          'payout_and_reinvestment_timing_adjustment':constrained-pure,
          'same_waterfall_financial_asset_contribution':actual-constrained,'value':actual}
    out['secondary']={'method':'normalized earning-power capitalization reconciled to actual common-holder cash constraints',
       'normalized_parameters':normal['parameters'],'low':secondary['low']['value'],'high':secondary['high']['value'],
       'endpoints':secondary,'years':normal['years'],'no_initial_surplus_years':zero_assets['years'],
       'note':'No 12-14x prior and no five-year lump-sum asset release. Y3 earnings normalize from Y4 at 1.5%; financial receipts use identical ownership/tax/liquidity/loss and parent constraints. The counterfactual removes only opening and acquired financial surplus, not operational required capital. Both methods share the waterfall and do not independently certify it.'}
    out['summary']={k:{a:v[a] for a in ['value_low','value_high','terminal_y5_low','terminal_y5_high','distributions']} for k,v in out['scenarios'].items()}
    data=json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+'\n'
    path=pathlib.Path(__file__).resolve().with_name('2026-Q3-output.json');path.write_text(data,encoding='utf-8')
    parser=argparse.ArgumentParser();parser.add_argument('--expand',action='store_true');args=parser.parse_args()
    print(data if args.expand else json.dumps({'summary':out['summary'],'secondary':out['secondary'],'tests':out['tests']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
