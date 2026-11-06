"""Dong-E-E-Jiao: CNY billion except per-share, anniversary cash periods.
All forward inputs are research budgets, not company guidance. Standard library only.
Cash is common-owner attributable financial assets, after reserved obligations.
Minority cash capital removed initially; incremental minority profits removed annually.
Lease cost is cash rent in operating margins; hence no separate lease debt deduction.
"""
from pathlib import Path
import json, copy

class FundingFailure(Exception):
    def __init__(self,state):
        self.state=state
        super().__init__(str(state))

def capital_realization(cash, proceeds, investment_cost, exit_cost, debt, shares, fraction=1., tax=.25):
    """Conditional disposal at actual owner fraction; principal is not profit.
    No sale/debt/share cancellation is completed if costs or creditors cannot be paid.
    """
    gain=(proceeds-investment_cost-exit_cost)*fraction
    tax_cash=max(0.,gain)*tax
    available=cash+(proceeds-exit_cost)*fraction-tax_cash
    gap=max(0.,debt-available)
    if gap>1e-12:
        return dict(feasible=False, funding_gap=gap, cash=cash, debt=debt, shares=shares, distribution=0., realized_profit=0., tax_cash=0.)
    return dict(feasible=True, funding_gap=0., cash=0., debt=0., shares=0., distribution=available-debt, realized_profit=gain-tax_cash, tax_cash=tax_cash)

SHARES=.639826824
CASH0=(3670798598.29+3611072057.36)/1e9-.020-.060541-.051-.09563224203
BASE=dict(revenues=[6.9,7.18,7.47,7.77,8.08,8.36,8.61,8.85,9.07,9.25],
 margins=[.295,.295,.297,.297,.297,.295,.293,.291,.289,.287],tax=.16,
 da=[.17,.19,.23,.25,.27,.28,.29,.30,.31,.32],
 maintenance=[.15,.17,.21,.24,.27,.28,.29,.30,.31,.32],
 project=[.60,.60,.17,0,0,0,0,0,0,0],
 other_growth=[.04,.04,.04,.04,.04,.04,.04,.04,.04,.04],
 nwc=[.12,.08,.07,.07,.07,.06,.06,.06,.06,.06],
 minority=[.003,.004,.005,.006,.007,.008,.009,.01,.011,.012],
 payout=.95,yield_net=.013,parent_share=.88,sub_payout=.8,
 parent_cash=CASH0-.4,sub_cash=.4,parent_re=8.0,source_retained_budget=0.,
 source_profit_buffer_rate=.10,tail_source_buffer_rate=0.,source_release_rate=.10,mother_release_rate=.10,parent_registered=.639802980,parent_paid=.639802980,shares=.639802980,capital_action_cash=.00076614393,
 parent_statutory=.46615687134,treasury_shares=.000385869,
 parent_floor=.9,sub_floor=.1,liquidity_revenue_anchor=9.25,review_years=5,realization_fee=.01,internal_repayment=0.,g=.02,roic=.15)

def project(p):
    pc,sc,pr,sr=p['parent_cash'],p['sub_cash'],p['parent_re'],p['source_retained_budget']
    reserve=p['parent_statutory']
    issued_shares=p.get('shares',SHARES)
    treasury_shares=p.get('treasury_shares',0.)
    shares=issued_shares-treasury_shares # treasury stock receives no dividends before cancellation
    action_cash=p.get('capital_action_cash',0.)
    debt=p.get("bank_debt",0.)
    if pc-action_cash<p["parent_floor"]-1e-12:
        raise FundingFailure(dict(year=0,reason="capital_action_unfunded",cash=pc,bank_debt=debt,shares=p.get("pre_action_shares",SHARES)-treasury_shares,issued_shares=p.get("pre_action_shares",SHARES),treasury_shares=treasury_shares,funding_gap=p["parent_floor"]-pc+action_cash))
    pc-=action_cash
    registered=p["parent_registered"];paid=p["parent_paid"]
    conversion=p.get("debt_conversion",0.)
    if conversion:
        if conversion>debt or p.get("conversion_price",0.)<=0:
            raise ValueError("invalid debt conversion")
        added=conversion/p["conversion_price"]
        shares+=added;issued_shares+=added;registered+=added;paid+=added;debt-=conversion
    old_receivable=p.get("old_dividend_receivable",0.)
    rows=[]
    held_parent=held_source=0.
    source_withheld_earnings=0.
    tail_start=p.get('_tail_start',len(p['revenues']))
    for i,rev in enumerate(p['revenues']):
        if i==tail_start:
            held_parent=max(0.,pc-p['parent_floor']);held_source=max(0.,sc-p['sub_floor'])
        locked=p.get('_release_delay',0)>0 and tail_start<=i<tail_start+p.get('_release_delay',0)
        scale=rev/p.get('liquidity_revenue_anchor',9.25) if i>=tail_start and p.get('scale_liquidity',True) else 1.
        mother_min=p['parent_floor']*scale;source_min=p['sub_floor']*scale
        mother_floor=mother_min+(held_parent if locked else 0.)
        source_floor=source_min+(held_source if locked else 0.)
        review=i>=tail_start and not locked and (i-tail_start+1-p.get('_release_delay',0))%p.get('review_years',5)==0
        ebit=rev*p['margins'][i]
        cash_tax=max(0.,ebit)*p['tax'] # no cash refund or unverified cross-entity loss offsets
        op=ebit-cash_tax-p['minority'][i]
        debt_service=p.get('debt_service',{}).get(i+1,0.)
        old_receipt=p.get('old_dividend_receipts',{}).get(i+1,0.)
        if old_receipt<0 or old_receipt>old_receivable+1e-12:
            raise ValueError('old dividend collection exceeds existing receivable')
        old_receivable-=old_receipt
        # Split owner-attributable profit/cash; subsidiaries are equity-weighted.
        pn,sn=op*p['parent_share'],op*(1-p['parent_share'])
        pi,si=pc*p['yield_net'],sc*p['yield_net']
        cap=p['maintenance'][i]+p['project'][i]+p['other_growth'][i]
        fcf=op+p['da'][i]-cap-p['nwc'][i]
        # Main park is legally funded by parent; other capital follows profit split.
        adj=p['da'][i]-p['maintenance'][i]-p['other_growth'][i]-p['nwc'][i]
        pfcf=pn+adj*p['parent_share']-p['project'][i]
        sfcf=sn+adj*(1-p['parent_share'])
        transfer=p['internal_repayment'] if i==0 else 0.
        sc_pre=sc+sfcf+si+transfer-old_receipt
        # Aggregate source budget, NOT a legal person or pooled statutory reserve.
        # 10% is a disclosure/appropriation buffer on recovered earnings, not PRC law.
        # Existing legal reserves are not guessed from net assets. Opening earnings
        # budget is zero; recurring 80% declarations need only current-year capacity.
        sub_profit=sn+si
        source_eligible=max(0.,min(sub_profit,sr+sub_profit))
        source_buffer=(p['source_profit_buffer_rate'] if i<tail_start else p['tail_source_buffer_rate'])*source_eligible
        source_budget=sr+sub_profit-source_buffer
        source_withheld_earnings+=source_buffer
        # Beyond the explicit forecast, release existing surplus gradually rather
        # than adding group cash to a terminal value. Zero routine profit payout does
        # not erase finite surplus principal: delayed recovery still needs earnings/cash capacity.
        release=(p['source_release_rate']*max(0.,sc-p['sub_floor'])
                 if i>=tail_start and not locked else 0.)
        upstream=max(0,min(p['sub_payout']*max(0.,sub_profit)+release,source_budget,sc_pre-source_floor))
        upstream=max(0.,upstream-p.get("retain_source",{}).get(i+1,0.))
        source_gross=upstream;source_principal=0.;realization_fee=0.;buffer_release=0.
        if review:
            # Conditional economic realization budget, NOT a synthetic subsidiary legal dividend.
            # Attributable financial assets are monetized at carrying value; no gain/tax refund.
            source_gross=max(0.,sc_pre-source_floor)
            earnings_receipt=min(source_gross,max(0.,source_budget))
            buffer_release=min(source_withheld_earnings,source_gross-earnings_receipt)
            source_withheld_earnings-=buffer_release
            source_principal=source_gross-earnings_receipt-buffer_release
            realization_fee=source_gross*p.get('realization_fee',.01)
            upstream=source_gross-realization_fee
        sr=source_budget-(source_gross-source_principal-buffer_release)
        sc_new=sc_pre-source_gross
        parent_profit=pn+pi+upstream-source_principal
        # Actual listed-company legal account; registered, not paid, is threshold.
        eligible=max(0.,min(parent_profit,pr+parent_profit))
        appropriation=min(.1*eligible,max(0.,.5*registered-reserve))
        reserve+=appropriation
        parent_legal=pr+parent_profit-appropriation
        pc_pre=pc+pfcf+pi+upstream-transfer+old_receipt-debt_service
        target=p['payout']*max(0,op+pi+si) + (p['mother_release_rate']*max(0.,pc-p['parent_floor']) if i>=tail_start and not locked else 0.)
        if review:target=max(0.,pc_pre-mother_floor) # finite five-year capital allocation, not perpetual 100% routine payout
        dividend=max(0,min(target,parent_legal,pc_pre-mother_floor))
        dividend=max(0.,dividend-p.get("retain_parent",{}).get(i+1,0.))
        pc_new=pc_pre-dividend;pr=parent_legal-dividend
        if min(pc_new-mother_min,sc_new-source_min) < -1e-9 or debt_service>debt+1e-12:
            raise FundingFailure(dict(year=i+1,reason='operating_or_creditor_gap',parent_cash_before_payment=pc_pre+debt_service,source_cash=sc_new,bank_debt=debt,shares=shares,issued_shares=issued_shares,treasury_shares=treasury_shares,dividend=0.,funding_gap=max(0.,p['parent_floor']-pc_pre,p['sub_floor']-sc_new),rows=rows))
        debt-=debt_service
        assert abs(pc_new+sc_new-(pc+sc+fcf+pi+si-dividend-debt_service-realization_fee))<1e-9
        rows.append(dict(year=i+1,revenue=rev,ebit=ebit,cash_tax=cash_tax,old_dividend_receipt=old_receipt,debt_service=debt_service,operating_profit_common=op,parent_own_profit=pn,
            subsidiary_profit=sn,financial_income=pi+si,parent_legal_profit=parent_profit,
            subsidiary_upstream=upstream,source_gross_realization=source_gross,source_principal_return=source_principal,source_buffer_release=buffer_release,source_withheld_earnings=source_withheld_earnings,realization_fee=realization_fee,parent_necessary_cash=mother_min,source_necessary_cash=source_min,realization_review=int(review),capex=cap,da=p['da'][i],nwc=p['nwc'][i],fcf=fcf,
            dividend=dividend,dps=dividend/shares,parent_cash=pc_new,subsidiary_cash=sc_new,
            cash=pc_new+sc_new,parent_retained=pr,source_earnings_budget=sr,source_profit_buffer=source_buffer,
            parent_reserve_appropriation=appropriation,parent_statutory_reserve=reserve,
            parent_registered=registered,parent_paid=paid,
            bank_debt=debt,new_financing=0.,shares=shares,issued_shares=issued_shares,treasury_shares=treasury_shares,internal_repayment=transfer,capital_action_cash=action_cash if i==0 else 0.,parent_locked_cash=held_parent if locked else 0.,source_locked_cash=held_source if locked else 0.))
        pc,sc=pc_new,sc_new
    return rows

def operating_terminal(last,p,r):
    # Incremental investment funds steady growth; maintenance equals depreciation.
    next_profit=last['operating_profit_common']*(1+p['g'])
    return next_profit*(1-p['g']/p['roic'])/(r-p['g'])

def extend_forecast(p,horizon=320,release_delay=0):
    """Same operating steady growth/ROIC, but actual owner receipts continue.
    No new legal entities or group cash sweep. Minorities stay excluded.
    """
    q=copy.deepcopy(p);n=len(p['revenues']);q['_tail_start']=n;q['_release_delay']=release_delay
    last_ebit=p['revenues'][-1]*p['margins'][-1]
    lastprofit=last_ebit-max(0.,last_ebit)*p['tax']-p['minority'][-1]
    for year in range(n+1,horizon+1):
        factor=(1+p['g'])**(year-n)
        op=lastprofit*factor
        q['revenues'].append(p['revenues'][-1]*factor)
        q['margins'].append(p['margins'][-1]);q['minority'].append(p['minority'][-1]*factor)
        q['da'].append(p['da'][-1]*factor);q['maintenance'].append(p['da'][-1]*factor)
        q['project'].append(0.);q['other_growth'].append(op*p['g']/p['roic']);q['nwc'].append(0.)
    return q

def initial_cash_recovery(p,rows):
    """FIFO attribution of existing SURPLUS cash through actual upstream and D.
    Cash is fungible: this diagnostic adds no cash or separate legal capital claim.
    Operating minimum cash is excluded, not treated as a finite liquidation asset.
    """
    mother=max(0.,p['parent_cash']-p.get('capital_action_cash',0.)-p['parent_floor'])
    source=max(0.,p['sub_cash']-p['sub_floor'])
    pending={'mother_initial_surplus':mother,'source_initial_surplus':0.}
    result={k:dict(initial=v,paid=0.,first_year=None,last_year=None,pv=0.) for k,v in [('mother_initial_surplus',mother),('source_initial_surplus',source)]}
    for x in rows:
        transfer=min(source,x['subsidiary_upstream']);source-=transfer
        pending['source_initial_surplus']+=transfer
        cash=x['dividend']
        for k in pending:
            take=min(cash,pending[k]);pending[k]-=take;cash-=take
            if take>1e-12:
                z=result[k];z['paid']+=take;z['first_year']=z['first_year'] or x['year'];z['last_year']=x['year'];z['pv']+=take/(1.09)**x['year']
    for k in result:result[k]['unpaid']=result[k]['initial']-result[k]['paid']
    return result

def valuation(p,r,start=0,cash_release_delay=0):
    n=len(p['revenues'])
    try:
        future=project(extend_forecast(p,p.get('horizon',320),cash_release_delay))
    except FundingFailure as exc:
        return dict(feasible=False,value=None,terminal_equity=None,failure=exc.state)
    if future[-1]['bank_debt']>1e-12:
        return dict(feasible=False,value=None,terminal_equity=None,failure=dict(reason='unsettled_external_debt',bank_debt=future[-1]['bank_debt'],shares=future[-1]['shares']))
    rows=future[:n];tail=future[n:]
    terminal=sum(z['dividend']/(1+r)**(z['year']-n) for z in tail)
    pv_d=sum(x['dividend']/(1+r)**(x['year']-start) for x in rows[start:])
    pv_t=terminal/(1+r)**(n-start)
    # No credit for end-horizon cash. Check extending the horizon for convergence.
    return dict(feasible=True,value=(pv_d+pv_t)/future[0]['shares'],terminal_pv_fraction=pv_t/(pv_d+pv_t),
        terminal_equity=terminal,pv_dividends=pv_d,pv_terminal=pv_t,rows=rows,tail_rows=tail,
        initial_cash_recovery=initial_cash_recovery(p,future),tail_ending_cash_uncredited=future[-1]['cash'],terminal_method='actual mother dividends; revenue-scaled liquidity; 5-year finite economic surplus review; no group cash addback')

def scenario(name):
    p=copy.deepcopy(BASE)
    if name=='cyclical':
        p.update(revenues=[6.2,6.3,6.8,7.3,7.75,8.1,8.4,8.65,8.85,9.02],
          margins=[.255,.26,.28,.29,.295,.293,.291,.289,.287,.285],
          nwc=[.4,.2,-.12,-.08,.07,.06,.06,.06,.06,.06],payout=.8)
    elif name=='structural':
        p.update(revenues=[6.2,5.9,5.65,5.5,5.4,5.3,5.2,5.1,5.,4.9],
          margins=[.24,.21,.19,.18,.18,.18,.18,.18,.18,.18],tax=.20,
          nwc=[.35,.25,.15,.1,.1,.08,.08,.08,.08,.08],payout=.65,g=0.,roic=.10)
    elif name=='optimistic':
        p.update(revenues=[7.1,7.6,8.15,8.7,9.25,9.7,10.1,10.5,10.85,11.17],
          margins=[.30,.305,.31,.31,.31,.308,.306,.304,.302,.30],
          nwc=[.14,.14,.14,.14,.14,.12,.12,.1,.1,.1],g=.025,roic=.18)
    elif name=='loss_year1':p['margins'][0]=-.10
    elif name=='margin_minus_2pp':p['margins']=[x-.02 for x in p['margins']]
    elif name=='credit_delay':p['nwc'][0]+=.6;p['nwc'][2]-=.6
    elif name=='park_overrun':p['project']=[x*1.3 for x in p['project']]
    elif name=='internal_settlement':p['internal_repayment']=.6
    elif name=='no_upstream':p['sub_payout']=0.
    elif name=='source_buffer_zero':p['source_profit_buffer_rate']=0.
    elif name=='source_buffer_20pct':p['source_profit_buffer_rate']=.20
    elif name=='source_prior_budget_035':p['source_retained_budget']=.35
    elif name=='mother_legal_zero_boundary':p['parent_re']=0.
    elif name=='pending_cancellations_complete':
        p.update(shares=.639417111,treasury_shares=0.,parent_registered=.639417111,parent_paid=.639417111,
            capital_action_cash=.00076614393)
    elif name=='registered_old_charter_timing':p['parent_registered']=.643976824
    elif name=='source_release_slow':p.update(source_release_rate=.05,mother_release_rate=.05)
    elif name=='source_release_fast':p.update(source_release_rate=.20,mother_release_rate=.20)
    elif name=='source_payout_half':p['sub_payout']=.40
    elif name=='horizon_400':p['horizon']=400
    elif name=='tail_source_buffer_10pct':p['tail_source_buffer_rate']=.10
    elif name=='review_3years':p['review_years']=3
    elif name=='review_10years':p['review_years']=10
    elif name=='realization_fee_3pct':p['realization_fee']=.03
    elif name=='realization_fee_zero':p['realization_fee']=0.
    elif name=='liquidity_150pct':p['parent_floor']*=1.5;p['sub_floor']*=1.5
    return p

def checks():
    # Actual projection + valuation functions: no growth, one period, all profit paid.
    p=copy.deepcopy(BASE)
    p.update(revenues=[1.],margins=[1.],tax=0.,da=[0.],maintenance=[0.],project=[0.],
      other_growth=[0.],nwc=[0.],minority=[0.],payout=1.,yield_net=0.,parent_share=1.,
      sub_payout=0.,parent_cash=0.,sub_cash=0.,parent_re=0.,source_retained_budget=0.,
      parent_floor=0.,sub_floor=0.,g=0.,roic=.2,shares=SHARES,treasury_shares=0.,capital_action_cash=0.)
    v=valuation(p,.1)
    assert abs(v['value']-10/SHARES)<1e-10 # (1 + 1/.1)/1.1
    assert v['rows'][0]['cash']==0
    # Forced parent cash constraint reduces dividends, never borrows for distribution.
    p['project']=[.75]
    v=valuation(p,.1)
    assert abs(v['rows'][0]['dividend']-.25)<1e-10
    # Losses must remain signed: .5 loss then .3 recovery leaves .2 deficit.
    p.update(revenues=[1.,1.,1.],margins=[-.5,.3,.3],da=[0.]*3,maintenance=[0.]*3,
      project=[0.]*3,other_growth=[0.]*3,nwc=[0.]*3,minority=[0.]*3,parent_cash=1.)
    a=project(p)
    assert [round(z['dividend'],8) for z in a]==[0.,0.,.1]
    assert [round(z['parent_retained'],8) for z in a]==[-.5,-.2,0.]
    # Source-budget loss recovery: buffer only recovered earnings, not unrecovered losses.
    p.update(parent_share=0.,sub_cash=1.,parent_cash=0.,sub_payout=1.)
    b=project(p)
    assert [round(z['subsidiary_upstream'],8) for z in b]==[0.,0.,.09]
    assert [round(z['source_earnings_budget'],8) for z in b]==[-.5,-.2,0.]
    # Same published engine: registered20/paid10/reserve5/profit10 must add1.
    p.update(revenues=[10.],margins=[1.],parent_share=1.,parent_cash=0.,sub_cash=0.,
      parent_re=0.,source_retained_budget=0.,parent_registered=20.,parent_paid=10.,
      parent_statutory=5.,da=[0.],maintenance=[0.],project=[0.],other_growth=[0.],
      nwc=[0.],minority=[0.],payout=1.)
    counter=project(p)[0]
    assert counter['parent_reserve_appropriation']==1. and counter['dividend']==9.
    p['parent_paid']=1.
    assert project(p)[0]['parent_reserve_appropriation']==1.
    return {'registered20_paid10_reserve5_profit10':counter,'actual_chain_hand_case' :10/SHARES,'cash_constraint_dividend':.25,
      'parent_loss_recovery_dividends':[z['dividend'] for z in a],
      'subsidiary_loss_recovery_upstream':[z['subsidiary_upstream'] for z in b]}

def main():
    out={'units':'CNY billion, shares billion, per-share CNY','assumptions':BASE,'initial_common_cash':CASH0,'initial_common_cash_after_capital_action':CASH0-BASE['capital_action_cash'],
      'base_low':valuation(BASE,.095),'base_high':valuation(BASE,.085),
      'year5_low':valuation(BASE,.095,5),'year5_high':valuation(BASE,.085,5),
      'checks':checks(),'scenarios':{},'capital_action_note':'As-of issued shares .639826824bn. 24 Oct approved 23844 restricted-share repurchase budget: year1 opening cash .00076614393bn and future shares/registered/paid .639802980bn; not as-of completion. 385869 already-paid treasury shares are excluded from participating shares before cancellation; cancellation pending shareholders changes registered/issued shares only, no extra cash or second EPS benefit. Repurchase is not cash dividend to continuing holders.',
      'source_budget_note':'Opening source earnings budget 0; 10% recovered-profit buffer and 80% declaration target are governance estimates, not aggregate legal reserve. Registered/paid/actual reserve functions apply to listed mother only.'}
    for name in ['cyclical','structural','optimistic','loss_year1','margin_minus_2pp','credit_delay','park_overrun','internal_settlement','no_upstream','source_buffer_zero','source_buffer_20pct','source_prior_budget_035','mother_legal_zero_boundary','pending_cancellations_complete','registered_old_charter_timing','source_release_slow','source_release_fast','source_payout_half','horizon_400','tail_source_buffer_10pct','review_3years','review_10years','realization_fee_3pct','realization_fee_zero','liquidity_150pct']:
        out['scenarios'][name]=valuation(scenario(name),.09)
    out['scenarios']['terminal_cash_delay_3']=valuation(BASE,.09,cash_release_delay=3)
    out['scenarios']['terminal_cash_delay_5']=valuation(BASE,.09,cash_release_delay=5)
    # Forward 3-year operating earnings multiple with the same equity cash bridge.
    rows=project(BASE)
    out['tail_source_buffer_scenarios']={}
    for label in ['base','cyclical','structural','optimistic']:
        q=scenario(label);q['tail_source_buffer_rate']=.10
        out['tail_source_buffer_scenarios'][label]=valuation(q,.09)
    out['method2']={str(m):(sum(x['dividend']/1.09**x['year'] for x in rows[:3])+
      (rows[2]['operating_profit_common']*m+rows[2]['cash']-1)/1.09**3)/(BASE['shares']-BASE['treasury_shares']) for m in [16,19]}
    out['sensitivity_metadata']={'effective':'year 1 (2026-10-26 onward), consolidated business and listed parent',
      'margin_minus_2pp':'all years operating margin -2pp; revenue, tax, capex, NWC, payout policy, discount fixed',
      'credit_delay':'additional .6 year1 NWC, returns year3; all operating inputs fixed; financing/dividends recomputed',
      'park_overrun':'parent park capex +30%, no additional sales; all other inputs fixed',
      'internal_settlement':'parent transfers .6 to subsidiaries year1, no group cash cost; profits unchanged',
      'no_upstream':'routine source payout zero; tail five-year economic realization with earnings/principal distinction, fee and mother legal cap',
      'terminal_cash_delay':'existing surplus held 3/5 years; first five-year realization review also delayed; financial income and mother legal/cash caps remain',
      'structural':'permanent demand decline, margin compression, credit costs and tax; committed park still paid; no automatic recovery',
      'cyclical':'two years weak sales/margin, working capital release year3-4; park commitments retained',
      'optimistic':'new products scale with higher margins and NWC, same park, higher mature ROIC'}
    Path(__file__).with_name('2026-Q3-output.json').write_text(json.dumps(out,ensure_ascii=False,separators=(',',':'))+'\n')
if __name__=='__main__':main()
