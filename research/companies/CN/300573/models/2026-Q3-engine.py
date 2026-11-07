#!/usr/bin/env python3
"""300573, CNY million; standalone stdlib, deterministic stdout JSON.
All forecast splits are research budgets, not undisclosed issuer product data.
No price input. Annual payments are to a continuing ordinary shareholder.
"""
import json, math, copy
SHARES=356.553846
FACTS={'group_cash_equivalents':530.53624182,'restricted_cash':7.28406852,'bank_debt':88.0,'lease_debt':17.57890698,'shares_issued':354.917774,'options_shares':1.636072,'option_price':11.28,'parent_H1_cash':416.39526720,'parent_H1_retained':808.14042688,'parent_H1_reserve':167.03158376,'parent_H1_profit':438.16820264,'group_H1_profit':430.40429336,'group_Q3_profit':274.70156362,'H1_dividend_paid_in_Q3':106.47533220}
BASE={'name':'base','r':.10,'atropine_mix':.45,'parent_revenue0':2800.,'parent_cash0':485.53624182,'sub_cash0':45.,'parent_retained0':976.3666583,'reserve0':167.03158376,'capital':SHARES,'engineering_payable0':218.59069682,'nwc0':250.,'fixed0':1580.,'unit_shift':0.,'price_shift':0.,'gross_shift':0.,'selling_shift':0.,'tax':.15,'capex_extra':0.,'wc_extra':0.,'cash_release':.25,'cash_yield':.01,'payout':.55,'sub_delay':0,'shock':False,'structural':False,'optimistic':False,'years':240,'capital_return_year':30,'capital_return_amount':100.,'capital_return_cost':.05}

def reserve_and_distributable(retained,reserve,profit,capital):
    # A positive year's earnings first cover accumulated legal loss.
    replenished=max(profit-max(-retained,0.),0.)
    appropriation=min(.1*replenished,max(.5*capital-reserve,0.))
    return retained+profit-appropriation,reserve+appropriation,appropriation

def operations(p):
    a=p['parent_revenue0']*p['atropine_mix']; o=p['parent_revenue0']-a
    prev=p['nwc0']; fixed=p['fixed0']; rows=[]
    for y in range(1,p['years']+1):
        if y>15:
            z=dict(rows[-1],year=y,dnwc=0.,new_capex=rows[-1]['da'],unit_growth=0.,net_price_change=0.)
            rows.append(z);continue
        au=[.15,.18,.13,.10,.08][y-1] if y<=5 else (.05 if y<=10 else .02)
        ap=-.03 if y==1 else (-.05 if y<=5 else (-.04 if y<=10 else -.02))
        ou=.05 if y<=5 else .03 if y<=10 else .02
        op=-.01 if y==1 else -.02 if y<=10 else -.01
        au+=p['unit_shift']; ap+=p['price_shift']
        if p['shock'] and y<=2: au-=.20;ou-=.12
        if p['shock'] and y==3: au+=.25;ou+=.15
        if p['structural']:
            ap-=.12 if y<=3 else .02
            ou-=.03
        if p['optimistic']: au+=.04 if y<=5 else 0.
        a*=1+au; a*=1+ap; o*=1+ou; o*=1+op
        rev=a+o
        if p.get('recall_recovery') and y<=2:rev*=.30 if y==1 else .65
        gross=.84-.003*min(y-1,14)+p['gross_shift']
        sell=.285+p['selling_shift']
        if p['structural']:gross-=.06;sell+=.045
        if p['shock'] and y<=2: gross-=.035;sell+=.02
        rd=max(310.,.105*rev); admin=max(150.,.055*rev);other=.022*rev
        ebit=rev*(gross-sell)-rd-admin-other
        if p.get('recall_recovery') and y<=2:
            gross-=.10 if y==1 else .05
            ebit=rev*gross-max(rev*sell,350.)-rd-admin-other
        da=130.+min(y-1,3)*15.
        # New capital includes sustaining equipment and outstanding centre work;
        # old engineer payable is settled separately, never capitalized again.
        capex=[340.,330.,200.,190.,190.][y-1] if y<=5 else da+max(rev-(rows[-1]['revenue'] if rows else 2800),0)*.18
        capex+=p['capex_extra'] if y<=3 else 0.
        if p.get('recall_recovery') and y<=3:capex+=[-160.,-100.,260.][y-1]
        nwc=rev*(.09+p['wc_extra']); dnw=nwc-prev;prev=nwc
        fixed+=capex-da
        rows.append(dict(year=y,atropine_budget_revenue=a,other_pharma_revenue=o,revenue=rev,gross_margin=gross,sales_ratio=sell,rd=rd,admin=admin,other=other,ebit=ebit,da=da,new_capex=capex,nwc=nwc,dnwc=dnw,fixed=fixed,unit_growth=au,net_price_change=ap))
    if p.get('auxiliary'):
        rows=[];previous=p['nwc0'];fixed=p['fixed0']
        for y in range(1,p['years']+1):
            revenue=3300.;nwc=revenue*.09;da=175.
            # Independent normalized franchise; 30 annual equipment renewal is expensed,
            # not perpetual capex accumulation. Extra centre completion 230 over 3 years.
            capex=da+([100.,80.,50.][y-1] if y<=3 else 0.)
            ebit=revenue*(.815-.29)-350.-190.-75.-30.
            fixed+=capex-da
            rows.append(dict(year=y,revenue=revenue,ebit=ebit,da=da,new_capex=capex,dnwc=nwc-previous,nwc=nwc,fixed=fixed,gross_margin=.815,rd=350.,admin=190.,other=105.))
            previous=nwc
    return rows

def simulate(p):
    rows=operations(p);pc=p['parent_cash0'];sc=p['sub_cash0'];pr=p['parent_retained0'];sr=-30.;res=p['reserve0'];sres=0.;debt=105.57890698;engineering=p['engineering_payable0'];taxloss=0.;sloss=30.;out=[];infeasible=False;group_equity=2231.51635954;subcapital=120.;investment_basis=120.
    for z in rows:
        y=z['year'];pc0=pc;sc0=sc;debt0=debt;pr0=pr;res0=res
        interest=debt*.03; pretax=z['ebit']-interest
        taxable=max(pretax-taxloss,0);taxloss=max(taxloss-pretax,0)
        tax=taxable*p['tax'];ni=pretax-tax
        # Subsidiaries are 100%-owned hospital/research entities; pooled BUDGET,
        # not an invented separate legal audited hospital income statement.
        sub_revenue=[70.,80.,90.,100.,108.][y-1] if y<=5 else min(108.+4*(y-5),140.)
        sub_variable_cost=.5*sub_revenue;sub_fixed_cost=50.
        sp=sub_revenue-sub_variable_cost-sub_fixed_cost
        if p['structural']:sp-=12.
        if y<=p['sub_delay']:sp-=10.
        if p.get('auxiliary'):sp=([-20.,-15.,-10.][y-1] if y<=3 else 0.)
        stax=max(sp-sloss,0)*.25;sloss=max(sloss-sp,0);sni=sp-stax
        sda=15.;scap=20. if y<=3 else 15.;sc+=sni+sda-scap
        fund=max(20.-sc,0);sc+=fund
        sr,sres,sapp=reserve_and_distributable(sr,sres,sni,subcapital)
        upstream=min(max(sr,0),max(sc-20.,0),max(sni,0)*.5 if y<=5 else max(sni,0)+p['cash_release']*max(sc-20.-max(sni,0),0))
        sr-=upstream;sc-=upstream
        # Conditional budget: lawful paid-in capital reduction after creditor process.
        # Not profit or a dividend; never release statutory reserve automatically.
        capital_return=min(p.get('capital_return_amount',0.),max(sc-20.,0.),max(subcapital-20.,0.)) if y==p.get('capital_return_year') else 0.
        sc-=capital_return;subcapital-=capital_return
        investment_basis+=fund-capital_return
        return_cost=capital_return*p.get('capital_return_cost',0.)
        assert investment_basis>=-1e-8
        settle=min(engineering,120. if y==1 else 98.59069682 if y==2 else engineering);engineering-=settle
        repay=min(debt,105.57890698/3) if y<=3 else 0.;debt-=repay
        receipt=FACTS['options_shares']*FACTS['option_price'] if y==1 else 0.
        mincash=.075*z['revenue']
        treasury=max(pc-.075*(2800. if y==1 else rows[y-2]['revenue']),0)*p['cash_yield']
        asset_recovery=(11.66666667+3.64671848)*.60 if y==8 else 0.
        asset_loss=(11.66666667+3.64671848)*.40 if y==8 else 0.
        restricted_release=7.28406852 if y==3 else 0.
        parent_profit=ni+treasury+upstream-asset_loss-return_cost
        pr,res,app=reserve_and_distributable(pr,res,parent_profit,p['capital'])
        prediv=pc+ni+treasury+z['da']-z['new_capex']-z['dnwc']-settle-repay-fund+upstream+receipt+asset_recovery+restricted_release+capital_return-return_cost
        desired=max(parent_profit,0)*p['payout']
        if y<=5 and p.get('first5_dividends'):desired=p['first5_dividends'][y-1]
        if y>=6:desired+=p['cash_release']*max(prediv-mincash-desired,0)
        dividend=max(0.,min(desired,max(pr,0),max(prediv-mincash,0)))
        pc=prediv-dividend;pr-=dividend
        funding_gap=max(-pc,0)
        if funding_gap>1e-8:infeasible=True
        if y<=5 and p.get('first5_dividends'):
            assert abs(dividend-desired)<1e-7, 'Frozen first-five distribution not cash/legal feasible'
        # No assumed bank approval, no invented bailout, no payouts from borrowing.
        assert abs(pc-(pc0+ni+treasury+z['da']-z['new_capex']-z['dnwc']-settle-repay-fund+upstream+receipt+asset_recovery+restricted_release+capital_return-return_cost-dividend))<1e-7
        assert abs(sc-(sc0+sni+sda-scap+fund-upstream-capital_return))<1e-7
        assert abs(pr-(pr0+parent_profit-app-dividend))<1e-7
        assert res<=p['capital']*.5+1e-8
        group_equity+=ni+treasury+sni-asset_loss+receipt-dividend-return_cost
        out.append(dict(z,group_equity=group_equity,asset_recovery=asset_recovery,asset_impairment=asset_loss,restricted_release=restricted_release,interest=interest,tax=tax,operating_net_profit=ni,parent_profit=parent_profit,parent_retained=pr,parent_reserve=res,reserve_addition=app,parent_cash=pc,min_parent_cash=mincash,parent_cash_start=pc0,subsidiary_revenue_budget=sub_revenue,subsidiary_variable_cost=sub_variable_cost,subsidiary_fixed_cost=sub_fixed_cost+(12. if p['structural'] else 0)+(10. if y<=p['sub_delay'] else 0),subsidiary_profit_budget=sni,subsidiary_cash=sc,subsidiary_retained=sr,subsidiary_reserve=sres,subsidiary_upstream=upstream,subsidiary_capital_return=capital_return,capital_return_transaction_cost=return_cost,parent_sub_investment_basis=investment_basis,subsidiary_paid_in_capital=subcapital,parent_equity_support=fund,engineering_paid=settle,engineering_remaining=engineering,debt_paid=repay,debt_remaining=debt,option_receipt=receipt,treasury_income=treasury,dividend=dividend,dps=dividend/SHARES,external_funding_gap=funding_gap))
        if infeasible:break # Insolvency stops forecast; no fictional later negative-cash dividends.
    r=p['r'];last=out[-1]
    pv=sum(t['dividend']/(1+r)**t['year'] for t in out)
    terminal5=sum(t['dividend']/(1+r)**(t['year']-5) for t in out if t['year']>5)
    convergence={str(n):sum(t['dividend']/(1+r)**t['year'] for t in out if t['year']<=n)/SHARES for n in (160,200,240)} if len(out)>=240 and not infeasible else {}
    steady={}
    if convergence:
        assert abs(convergence['240']-convergence['200'])<1e-5
        assert abs(convergence['200']-convergence['160'])<1e-4
        prev=out[-2]
        for k in ('dividend','parent_cash','parent_reserve','subsidiary_cash','subsidiary_reserve','subsidiary_upstream'):
            assert abs(last[k]-prev[k])<1e-6,(p['name'],k,last[k]-prev[k])
        assert abs(last['new_capex']-last['da'])<1e-9
        assert last['dnwc']==0 and abs(last['debt_remaining'])<1e-8 and abs(last['engineering_remaining'])<1e-8
        steady={k:last[k] for k in ('dividend','parent_cash','min_parent_cash','parent_reserve','parent_retained','subsidiary_cash','subsidiary_reserve','subsidiary_retained','subsidiary_upstream','treasury_income')}
        steady['unvalued_after_240_upper_bound_per_share']=last['dividend']*(1.000001)/r/(1+r)**240/SHARES
        assert steady['unvalued_after_240_upper_bound_per_share']<1e-6
    return {'inputs':p,'rows':out,'feasible':not infeasible,'forecast_status':'truncated_at_funding_gap' if infeasible else 'finite_actual_holder_distributions_no_terminal_addition','value_per_share':None if infeasible else pv/SHARES,'year5_terminal_per_share':None if infeasible else terminal5/SHARES,'five_year_dps':[t['dps'] for t in out[:5]],'convergence_values_per_share':convergence,'steady_holder_state':steady,'year5_onward_PV_fraction':None if infeasible or not pv else terminal5/(1+r)**5/pv,'future_incremental_roic_1to5':None if len(out)<5 else (out[4]['ebit']-out[0]['ebit'])*(1-p['tax'])/((out[4]['fixed']+out[4]['nwc'])-(out[0]['fixed']+out[0]['nwc']))}

def auxiliary(r=.10):
    # Independently normalized economics, SAME actual minority-holder payment bridge.
    return simulate(dict(BASE,name='auxiliary',r=r,auxiliary=True))

def tests():
    # Production reserve logic must pass loss recovery and legal cap literal tests.
    a,b,c=reserve_and_distributable(-40.,49.,30.,100.);assert (a,b,c)==(-10.,49.,0.)
    a,b,c=reserve_and_distributable(a,b,30.,100.);assert (a,b,c)==(19.,50.,1.)
    a,b,c=reserve_and_distributable(a,b,10.,100.);assert (a,b,c)==(29.,50.,0.)
    # Actual production simulator receives a loss/recovery operating override.
    global operations
    saved=operations
    def fixture(p):
        out=[]
        for i,e in enumerate([-40.,30.,40.],1):out.append(dict(year=i,revenue=100.,ebit=e,da=0.,new_capex=0.,dnwc=0.,fixed=100.,nwc=0.))
        return out
    operations=fixture
    q=dict(BASE,years=3,parent_cash0=500.,parent_retained0=-10.,reserve0=177.,engineering_payable0=0.,tax=0.,cash_yield=0.,payout=1.)
    f=simulate(q); operations=saved
    # Independent literals: 3% interest on 105.57890698 then declining debt;
    # loss balance must be carried until year 3 and no dividend before recovery.
    assert f['rows'][0]['dps']==0 and f['rows'][1]['dps']==0
    assert f['rows'][0]['parent_retained']<0 and f['rows'][2]['parent_retained']>=-1e-8
    assert abs(f['rows'][0]['parent_retained']-(-53.1673672094))<1e-7
    assert abs(f['rows'][1]['parent_retained']-(-25.278945349))<1e-7
    expected_d3=38.9442109302-25.278945349-(356.553846/2-177.)
    assert abs(f['rows'][2]['dividend']-expected_d3)<1e-7
    # Constraint test: genuine liquidity shortfall is flagged, not funded by fiat.
    q=dict(BASE,parent_cash0=0.,capex_extra=1200.)
    constrained=simulate(q);assert not constrained['feasible'] and constrained['rows'][0]['dividend']==0
    return {'reserve_loss_recovery_literal_pass':True,'reserve_cap_literal_pass':True,'production_loss_then_profit_pass':True,'production_loss_rows':f['rows'],'production_insolvency_not_hidden':True,'production_insolvency_rows':constrained['rows'],'production_insolvency_value':constrained['value_per_share']}

def main():
    params=[BASE,dict(BASE,name='core_low',r=.105,price_shift=-.01,gross_shift=-.01),dict(BASE,name='core_high',r=.095,unit_shift=.02,gross_shift=.005),dict(BASE,name='cyclical',shock=True),dict(BASE,name='structural',structural=True,tax=.20),dict(BASE,name='optimistic',optimistic=True),dict(BASE,name='price_minus_1pct',price_shift=-.01),dict(BASE,name='release_slow',cash_release=.10),dict(BASE,name='release_fast',cash_release=.50),dict(BASE,name='receivables_delay',wc_extra=.04),dict(BASE,name='capex_overrun',capex_extra=100.),dict(BASE,name='subsidiary_delayed',sub_delay=5),dict(BASE,name='mix_35pct',atropine_mix=.35),dict(BASE,name='mix_55pct',atropine_mix=.55),dict(BASE,name='recall_recovery',recall_recovery=True),dict(BASE,name='no_capital_return',capital_return_year=0),dict(BASE,name='capital_return_20',capital_return_year=20),dict(BASE,name='capital_return_40',capital_return_year=40),dict(BASE,name='capital_return_partial',capital_return_amount=50.),dict(BASE,name='capital_return_cost10',capital_return_cost=.10)]
    base_schedule=[z['dividend'] for z in simulate(BASE)['rows'][:5]]
    for p in params:
        if p['name'] in ('core_low','core_high'):p['first5_dividends']=base_schedule
    scenarios={p['name']:simulate(p) for p in params}
    result={'company':'CN:300573','period':'2026-Q3','model_as_of':'2026-10-28T11:00:00+00:00','units':'CNY million except per-share and ratios','opening_facts':FACTS,'share_count_fully_diluted_m':SHARES,'fact_budget_boundary':'Q3 consolidated and H1 parent facts; October issuance receipt, Q3 parent cash/profit allocation, engineering split and all future operations/distributions are budgets. No clinical-stage product sales.', 'scenarios':scenarios,'auxiliary':[auxiliary(.105),auxiliary(.10),auxiliary(.095)],'tests':tests()}
    print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True,allow_nan=False))
if __name__=='__main__':main()
