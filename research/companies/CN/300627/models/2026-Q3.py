"""CN:300627 Huace Navigation, CNY million. Stdlib only.
Rolling years from 2026-10-26. Long years are numerical integration, not forecasts.
Actual securities and opening legal capital documented; future entity attribution is a budget.
"""
import copy,json,math
from pathlib import Path
P={
 'sales':[3600,4000,4400,4800,5200], 'margin':[.13,.15,.16,.165,.17],
 'terminal_growth':.02,'terminal_margin':.145,'fade_end':15,
 'wc_ratio':.39,'fixed_ratio':.20,'opening_wc':1430.,'opening_fixed':686.,
 'tax':.15,'cash_yield':.018,'debt_rate':.035,'payout':.50,
 'opening_cash':[1800.,200.,200.], 'opening_debt':[105.006481,17.225,17.225],
 'opening_legal':[1700.,0.,0.], 'opening_reserve':[370.058427,0.,0.],
 'capital':[793.970662,50.,200.], 'weights':[.85,.075,.075],
 'cash_weights':[.85,.075,.075], 'floor_weights':[.75,.10,.15], 'floor_ratio':.12,
 'new_shares':[.60312,0.,0.,0.,0.], 'exercise_prices':[16.8,26.63,26.63,0,0],
 'sbc_addback':[0.,0.,0.,0.,0.], 'sbc_expense':[0.,0.,0.,0.,0.],
 'opening_shares':793.970662,'opening_equity':4445.085799,
 'opening_intercompany':[137.30797819,354.63494228], 'debt_limit':[200.,50.,50.],
 'upstream_start':2,'special_start':10,'fund_call':62.5,'locked_deposits':[450.,0.,0.],'extra_wc':0.,'extra_wc_start':1,
 'entity_names':['上海华测导航技术股份有限公司','上海双微导航技术有限公司','武汉华测卫星技术有限公司'],
 'nonmodelled_assets':134.035546,'nonmodelled_asset_return':0.,
 'annual_minority':.002,'opening_ringfenced_minorities':12.22431,
}
def legal_add(balance,reserve,capital,profit):
    """Losses carried forward; only profit above prior loss can fund reserve."""
    gain=max(profit-max(-balance,0),0)
    allocation=min(.1*gain,max(.5*capital-reserve,0))
    return balance+profit-allocation,reserve+allocation,allocation

def simulate(p,n=350):
    p=copy.deepcopy(p); cash=p['opening_cash'][:]; debt=p['opening_debt'][:]
    legal=p['opening_legal'][:]; reserve=p['opening_reserve'][:]; capital=p['capital'][:]
    loans=p['opening_intercompany'][:]; shares=p['opening_shares'];equity=p['opening_equity']
    wc=p['opening_wc'];fixed=p['opening_fixed'];sales=p['sales'][0];rows=[]
    for y in range(1,n+1):
        locked=p['locked_deposits'][:] if y==1 else [0.,0.,0.]
        prior_cash=cash[:];prior_legal=legal[:];prior_equity=equity;prior_shares=shares
        if y<=5: sales=p['sales'][y-1];margin=p['margin'][y-1]
        else:
            fade=min((y-5)/(p['fade_end']-5),1.)
            growth=(p['sales'][4]/p['sales'][3]-1)*(1-fade)+p['terminal_growth']*fade
            sales*=1+growth;margin=p['margin'][4]*(1-fade)+p['terminal_margin']*fade
        new_wc=sales*p['wc_ratio']+(p['extra_wc'] if y>=p['extra_wc_start'] else 0.)
        new_fixed=sales*p['fixed_ratio']; da=fixed*.12;capex=da+new_fixed-fixed
        if capex<0: capex=0.;new_fixed=fixed-da
        dwc=new_wc-wc; net_reinvestment=capex-da+dwc
        cash_ebit=sales*margin; sbc=(p['sbc_expense'][y-1] if y<=5 else 0.)
        accounting_ebit=cash_ebit-sbc
        nopat=accounting_ebit*(1-p['tax'])
        addback=p['sbc_addback'][y-1] if y<=5 else 0.
        # Tax benefit is not assumed for share awards. SBC addback therefore net of no tax shield.
        operating_cf=cash_ebit*(1-p['tax'])-net_reinvestment
        financial=[c*p['cash_yield']*(1-p['tax']) for c in cash]
        interest=[d*p['debt_rate']*(1-p['tax']) for d in debt]
        minority=max(cash_ebit*(1-p['tax']),0)*p['annual_minority']
        profits=[nopat*w+financial[i]-interest[i] for i,w in enumerate(p['weights'])]
        profits[0]-=minority+sbc*p['tax'] # no tax shield for SBC
        ni=sum(profits)
        for i in range(3):
            cash_weight=p['cash_weights'][i] if y<=5 else p['weights'][i]
            cash[i]+=operating_cf*cash_weight+financial[i]-interest[i]
        fund_call=p['fund_call'] if y==1 else 0.
        cash[0]-=minority+fund_call
        issued=p['new_shares'][y-1] if y<=5 else 0.;proceeds=issued*(p['exercise_prices'][y-1] if y<=5 else 0)
        shares+=issued;capital[0]+=issued;cash[0]+=proceeds
        allocations=[]
        for i in range(3):
            legal[i],reserve[i],a=legal_add(legal[i],reserve[i],capital[i],profits[i]);allocations.append(a)
        floor=[sales*p['floor_ratio']*w+locked[i] for i,w in enumerate(p['floor_weights'])]
        principal=[min(d,p['opening_debt'][i]/3) if y<=3 else 0 for i,d in enumerate(debt)]
        newloans=[0.,0.];newborrow=[0.,0.,0.]
        # No shareholder cash injection with unidentified ownership: internal funding is a recorded loan.
        for i in (1,2):
            need=max(floor[i]+principal[i]-cash[i],0)
            give=min(need,max(cash[0]-floor[0]-principal[0],0))
            cash[0]-=give;cash[i]+=give;loans[i-1]+=give;newloans[i-1]=give
        for i in range(3):
            need=max(floor[i]+principal[i]-cash[i],0)
            borrow=min(need,max(p['debt_limit'][i]-debt[i],0));cash[i]+=borrow;debt[i]+=borrow;newborrow[i]=borrow
            if cash[i]+1e-8<principal[i]: raise ValueError('Zero dividend still cannot pay debt/operations: year %d entity %d'%(y,i))
            cash[i]-=principal[i];debt[i]-=principal[i]
            if cash[i]+1e-7<floor[i]:raise ValueError('Zero dividend cannot fund minimum operating liquidity')
        repay=[];declared=[];received=[]
        for i in (1,2):
            pay=min(loans[i-1],max(cash[i]-floor[i],0));loans[i-1]-=pay;cash[i]-=pay;cash[0]+=pay;repay.append(pay)
            # New dividends declared and paid in same annual budget. Opening dividend receivables = zero.
            div=min(max(legal[i],0),max(cash[i]-floor[i],0)) if y>=p['upstream_start'] else 0.
            legal[i]-=div;cash[i]-=div;cash[0]+=div
            legal[0],reserve[0],a=legal_add(legal[0],reserve[0],capital[0],div);allocations[0]+=a
            declared.append(div);received.append(div)
        target=max(ni,0)*p['payout'] if y<=5 else max(ni+max(addback,0)-max(net_reinvestment,0),0)
        ordinary=min(target,max(cash[0]-floor[0],0),max(legal[0],0))
        cash[0]-=ordinary;legal[0]-=ordinary
        # Additional retained financial principal is released only AFTER ordinary dividends consume legal profit.
        special=min(max(cash[0]-floor[0],0),max(legal[0],0)) if y>=p['special_start'] else 0.
        cash[0]-=special;legal[0]-=special;dist=ordinary+special
        equity+=ni+addback+proceeds-dist # equity-settled charge credit also increases capital reserve
        expected=sum(prior_cash)+operating_cf+sum(financial)-sum(interest)-minority-fund_call+proceeds+sum(newborrow)-sum(principal)-dist
        assert abs(sum(cash)-expected)<max(1e-6,abs(expected)*1e-12)
        assert min(cash+debt+loans)>=-1e-7
        assert all(reserve[i]<=capital[i]*.5+1e-7 for i in range(3))
        bps=equity/shares;prior_bps=prior_equity/prior_shares
        # Shareholder clean-surplus earnings include stock issue dilution, not whole-group profit alone.
        owner_earnings=(ni+addback+proceeds-prior_bps*issued)/shares
        assert abs(bps-prior_bps-owner_earnings+dist/shares)<1e-8
        rows.append(dict(year=y,sales=sales,margin=margin,cash_ebit=cash_ebit,accounting_ebit=accounting_ebit,
          net_profit=ni,sbc_expense=sbc,sbc_addback=addback,minority_cash=minority,da=da,capex=capex,
          working_capital=new_wc,fixed_assets=new_fixed,net_reinvestment=net_reinvestment,operating_cf=operating_cf,
          shares=shares,issued_shares=issued,issue_proceeds=proceeds,equity=equity,bps=bps,prior_bps=prior_bps,
          owner_earnings=owner_earnings,cash=cash[:],debt=debt[:],legal=legal[:],reserve=reserve[:],capital=capital[:],
          legal_profit_operating_financial=profits,legal_profit_upstream=[sum(declared),0.,0.],
          reserve_allocation=allocations,financial_income=financial,debt_interest=interest,principal=principal,
          new_borrowing=newborrow,intercompany_new_loans=newloans,intercompany_loans=loans[:],
          intercompany_principal_repaid=repay,subs_declared=declared,subs_received=received,old_dividend_receipts=0.,
          locked_deposits=locked,fund_call=fund_call,fund_parent_equity_injection_to_ningbo= fund_call,fund_ningbo_cash_paid_to_partnership=fund_call,fund_vehicle_capital_budget=100.+p['fund_call'],nonmodelled_investment_assets=p['nonmodelled_assets']+p['fund_call'],cash_floor=floor,ordinary=ordinary,special=special,distribution=dist,dps=dist/shares))
        wc=new_wc;fixed=new_fixed
    return rows

def value(rows,r,start=0):
    return sum(z['dps']/(1+r)**(z['year']-start) for z in rows if z['year']>start)
def residual_income(rows,r,start=0):
    b=rows[start]['prior_bps']
    return b+sum((z['owner_earnings']-r*z['prior_bps'])/(1+r)**(z['year']-start) for z in rows if z['year']>start)-rows[-1]['bps']/(1+r)**(len(rows)-start)
def case(p,n=350):
    rows=simulate(p,n);v={}
    for r in (.105,.10,.095):
        k=str(r);v[k]={'value':value(rows,r),'tv5':value(rows,r,5),'residual_income':residual_income(rows,r),
          'tv5_share_pv':value(rows,r,5)/(1+r)**5/value(rows,r)}
        assert abs(v[k]['value']-v[k]['residual_income'])<1e-7
    return {'parameters':p,'valuations':v,'rows':rows}
def test():
    q=copy.deepcopy(P);q.update(sales=[100]*5,margin=[.2]*5,wc_ratio=0.,fixed_ratio=0.,opening_wc=0.,opening_fixed=0.,tax=0.,cash_yield=0.,debt_rate=0.,
      opening_cash=[0.,0.,0.],opening_debt=[0.,0.,0.],opening_legal=[0.,0.,0.],opening_reserve=[0.,0.,0.],capital=[0.,0.,0.],weights=[1.,0.,0.],cash_weights=[1.,0.,0.],floor_ratio=0.,new_shares=[0.]*5,sbc_expense=[0.]*5,sbc_addback=[0.]*5,opening_shares=10.,opening_equity=0.,opening_intercompany=[0.,0.],annual_minority=0.,payout=1.,fund_call=0.,locked_deposits=[0.,0.,0.])
    rows=simulate(q,5)
    manual=2*sum(1/1.1**i for i in range(1,6))
    assert all(abs(z['dps']-2)<1e-10 for z in rows)
    assert abs(value(rows,.1)-manual)<1e-10
    assert legal_add(-20,0,100,10)==(-10,0,0)
    assert legal_add(-10,0,100,30)==(18,2,2)
    bad=copy.deepcopy(q);bad['margin']=[-1]*5;bad['debt_limit']=[0.,0.,0.]
    try:simulate(bad,5)
    except ValueError:failed=True
    else:failed=False
    assert failed
    return {'same_function_manual_annuity':manual,'persistent_loss_tests':True,'zero_dividend_insolvency_rejected':True}
def main():
    out={'unit':'CNY million unless per share','period':'2026-Q3','manual_tests':test(),'cases':{}}
    params={'base':copy.deepcopy(P)}
    q=copy.deepcopy(P);q.update(sales=[3100,3300,3900,4500,5000],margin=[.07,.10,.14,.16,.17],extra_wc=200.);params['cyclical']=q
    q=copy.deepcopy(P);q.update(sales=[3400,3500,3600,3700,3800],margin=[.08,.085,.09,.09,.09],terminal_margin=.08,terminal_growth=.01,wc_ratio=.48,fixed_ratio=.24,new_shares=[.60312,0.,0.,0.,0.],exercise_prices=[16.8,0.,0.,0.,0.],sbc_expense=[0.,0.,0.,0.,0.],sbc_addback=[0.,0.,0.,0.,0.]);params['structural']=q
    q=copy.deepcopy(P);q.update(sales=[3800,4400,5100,5800,6500],margin=[.145,.17,.18,.19,.19],terminal_margin=.16,wc_ratio=.37,fixed_ratio=.21);params['upside']=q
    q=copy.deepcopy(P);q.update(sales=[3600,4000,4400,4488,4577.76],margin=[.13,.15,.16,.16,.16],terminal_growth=.02,terminal_margin=.16);params['normalized_earnings_power_year3']=q
    q=copy.deepcopy(P);q['terminal_margin']=.125;params['terminal_margin_minus2pt_from_year6']=q
    q=copy.deepcopy(P);q['extra_wc']=300.;q['extra_wc_start']=1;params['receivable_delay_300_from_year1']=q
    q=copy.deepcopy(P);q['upstream_start']=6;q['weights']=[.65,.175,.175];q['cash_weights']=[.60,.20,.20];params['parent_cash_upstream_delay']=q
    q=copy.deepcopy(P);q['special_start']=15;params['retained_principal_release_year15']=q
    q=copy.deepcopy(P);q.update(new_shares=[12.0,7.0,6.67055,0.,0.],exercise_prices=[16.5,25.5,24.9,0,0]);params['all_rights_exercise_conditional_diagnostic']=q
    for name,p in params.items():out['cases'][name]=case(p)
    base=out['cases']['base'];long=simulate(P,450)
    for key in ['sales','net_profit','cash','debt','legal','reserve','shares','working_capital','fixed_assets','capital']:
        assert base['rows'][4][key]==out['cases']['retained_principal_release_year15']['rows'][4][key],key
    out['year5_endpoint_state_identical']=True
    earnings=4400*.16*.85*(1-P['annual_minority']);capital_need=4400*(.39+.20);minimum_cash=4400*.12
    cash_flow=(earnings-capital_need*.02-minimum_cash*.02+minimum_cash*.018*.85)*1.02
    out['earnings_power_check']={'normalized_year':3,'operating_profit_after_tax_and_minority':earnings,'operating_capital':capital_need,'minimum_cash':minimum_cash,'next_year_normalized_distributable':cash_flow,'capitalized_value_at_year3_before_extra_retained_financial_principal':{str(r):cash_flow/(r-.02) for r in [.105,.1,.095]},'actual_legal_budget_case':'normalized_earnings_power_year3','extra_principal_treatment':'Only actual legally distributed cash in the associated full budget, no additional mechanical cash asset addback.'}
    out['integration_check']={str(r):{'n350':value(base['rows'],r),'n450':value(long,r),'difference':value(long,r)-value(base['rows'],r),
       'remaining_cash_350':base['rows'][-1]['cash'],'remaining_legal_350':base['rows'][-1]['legal']} for r in (.105,.095)}
    out['long_integration_rows']=long
    out['core']={'low':round(out['cases']['retained_principal_release_year15']['valuations']['0.105']['value'],2),'high':round(base['valuations']['0.095']['value'],2),
      'dps':[round(z['dps'],6) for z in base['rows'][:5]],'tv5_low':round(out['cases']['retained_principal_release_year15']['valuations']['0.105']['tv5'],2),'tv5_high':round(base['valuations']['0.095']['tv5'],2)}
    Path(__file__).with_name('2026-Q3-output.json').write_text(json.dumps(out,ensure_ascii=False,separators=(',',':'))+'\n')
    print(json.dumps(out['core'],ensure_ascii=False,indent=2))
if __name__=='__main__':main()
