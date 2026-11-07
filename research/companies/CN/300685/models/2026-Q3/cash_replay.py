import hashlib,copy
from pathlib import Path
# NEW_RECONSTRUCTION: cached operating inputs; current cash recursion.
# No original main/build or full-company scenario generator is included.
CACHE_ROWS = None
TAIL_ROWS = None
EVENT_DELTA_CASH = 0.0
TREASURY_SHARES = .003566367

import copy,json,math,gzip,hashlib,argparse,base64,zlib

from pathlib import Path

SHARES=380.985869

INPUT=dict(revenue0=[870.,350.],growth=[.06,.09],margin=[.35,.25],tax=.15,wc_ratio=.50,
 capex_ratio=.045,da_ratio=.025,payout=.50,deposit_yield=.018,debt_rate=.03,
 opening_cash=[1038.798788,100.,120.],term_deposit=[764.908373,0.,0.],
 opening_debt=[150.242611,5.,5.],parent_retained=1189.40749267,parent_reserve=195.0525845,
 parent_registered=390.105169,parent_paid=390.105169,voluntary_reserve_rate=0.,
 profit_weights=[.92,.04,.04],cash_weights=[.90,.05,.05],cash_floor=[180.,30.,30.],
 term_maturity=1,release_year=99,release_target=600.,extra_capex=[0]*5,legal_profit_adjust=[0]*5,
 old_receivable=[8.15444172,.17277681],internal_interest=0.,external_limit=0.,subs_upstream_start=99,
 access_cost=[0.,.02,.10],financial_release_delay=3,parent_cost_basis_return=[0.,0.,0.],
 equity_asset=53.,equity_book=53.,equity_tax_basis=50.,equity_sale_fee=.01,
 tail_g=.025,tail_margin=.30,tail_ic=.80,tail_growth0=.065,horizon=200,
 minimum_cash_interest=True,redemption=[0.]*5,external_shares=380.985869,share_par=1.)

def legal_update(retained,reserve,registered,profit,voluntary=0.):
    # paid capital and investment cost are deliberately NOT the cap input.
    eligible=max(profit+min(retained,0.),0.)
    mandatory=min(.1*eligible,max(.5*registered-reserve,0.))
    discretionary=max(eligible-mandatory,0)*voluntary
    return retained+profit-mandatory-discretionary,reserve+mandatory,mandatory,discretionary

def realize(gross,book,tax_basis,tax_rate,fee,ownership=1.,required_exit=0.,external_debt=0.,shares=None):
    costs=gross*fee+required_exit
    if gross+1e-10<costs+external_debt: raise ValueError('exit costs/external debt unfunded; no liquidation or share cancellation')
    taxable=max(gross-costs-tax_basis,0.)
    tax=taxable*tax_rate
    if gross-costs-tax+1e-10<external_debt:raise ValueError('exit tax leaves external debt unpaid; shares preserved')
    return dict(feasible=True,external_debt_paid=external_debt,unpaid_external_debt=0.,shares_after=shares,net=(gross-costs-tax-external_debt)*ownership,profit=(gross-costs-book-tax)*ownership,
                tax=tax*ownership,cost=costs*ownership,principal=min(gross-costs,tax_basis)*ownership,
                minority=(gross-costs-tax-external_debt)*(1-ownership))

def capital_return(cash,amount,basis,registered,shares,fee=0.,ownership=1.,par_value=None,external_debt_due=0.):
    # Explicit conditional paid reduction: a real entity input only, never used to create a synthetic legal pool.
    if amount>min(cash,basis,registered)+1e-10: raise ValueError('capital return lacks cash/basis/registered capital')
    if cash-amount+1e-10<external_debt_due:raise ValueError('redemption leaves external debt unfunded; original shares preserved')
    par_value=registered/shares if par_value is None else par_value
    if amount/par_value>shares+1e-10:raise ValueError('redeemed external shares exceed outstanding shares')
    net=amount*(1-fee)*ownership
    return dict(feasible=True,unpaid_external_debt=external_debt_due,net=net,profit=0.,cash=cash-amount,basis=basis-amount,registered=registered-amount,
                shares=shares-amount/par_value,minority=amount*(1-fee)*(1-ownership),cost=amount*fee)

def move(c,s,t,a):
    if a< -1e-8 or a>c[s]+1e-8: raise ValueError('unfunded transfer')
    c[s]-=a;c[t]+=a

def net_interest(gross_interest, aftertax_operating_profit, tax_rate):
    """Current cash shield cannot exceed this source's positive operating tax budget."""
    capacity=max(0.,aftertax_operating_profit)/(1-tax_rate)
    if capacity>=gross_interest:return gross_interest*(1-tax_rate)
    return gross_interest-capacity*tax_rate

def simulate(p):
    p=copy.deepcopy(p);cash=[a-b for a,b in zip(p['opening_cash'],p['term_deposit'])];term=p['term_deposit'][:]
    debt=p['opening_debt'][:];rec=p['old_receivable'][:];ret=p['parent_retained'];reserve=p['parent_reserve'];rev=p['revenue0'][:]
    wc=p.get('opening_wc',sum(rev)*.5);rows=[];pending=p['release_target'];registered=p['parent_registered'];paid=p['parent_paid'];shares=p['external_shares']
    for y in range(1,6):
        opening=sum(cash)+sum(term); saved=CACHE_ROWS[y-1]
        rev=saved['revenue'][:];sales=sum(rev);ebit=saved['ebit'];tax=saved['tax'];nop=saved['nopat']
        nwc=saved['wc'];da=saved['da'];capex=saved['capex'];fcf=saved['fcf'];wc=nwc
        fin=[(cash[i]+term[i])*p['deposit_yield']*(1-p['tax']) for i in range(3)]
        # tax shield only with positive modeled profit; losses never give instant cash refund.
        interest=[net_interest(debt[i]*p['debt_rate'],nop*p['profit_weights'][i],p['tax']) for i in range(3)]
        internal=[x*p['internal_interest'] for x in rec]
        profit=[nop*w+fin[i]-interest[i] for i,w in enumerate(p['profit_weights'])]
        profit[0]+=sum(internal)+p['legal_profit_adjust'][y-1]
        for i in (1,2):profit[i]-=internal[i-1]
        for i in range(3):
            cash[i]+=fcf*p['cash_weights'][i]+fin[i]-interest[i]
            if y>=p['term_maturity']:cash[i]+=term[i];term[i]=0.
        for i in (1,2):
            if cash[i]<internal[i-1]:raise ValueError('operations/internal interest unfunded before any distribution')
            move(cash,i,0,internal[i-1])
        principal=[min(debt[i],p['opening_debt'][i]*[.10,.45,.45,0,0][y-1]) for i in range(3)]
        funding=[0.,0.]
        for i in (1,2):
            need=max(p['cash_floor'][i]+principal[i]-cash[i],0);a=min(need,max(cash[0]-principal[0]-p['cash_floor'][0],0))
            move(cash,0,i,a);rec[i-1]+=a;funding[i-1]=a
        for i in range(3):
            if cash[i]+1e-8<principal[i]:raise ValueError('zero distribution still cannot fund debt/operations')
            cash[i]-=principal[i];debt[i]-=principal[i]
        receipts=[0.,0.];up=[0.,0.];cost=0.
        for i in (1,2):
            a=min(max(cash[i]-p['cash_floor'][i],0),rec[i-1]);move(cash,i,0,a);rec[i-1]-=a;receipts[i-1]=a
            if y>=p['subs_upstream_start']:
                gross=max(cash[i]-p['cash_floor'][i],0);c=gross*p['access_cost'][i];cash[i]-=c;cost+=c
                move(cash,i,0,gross-c);up[i-1]=gross-c
        ret,reserve,alloc,vol=legal_update(ret,reserve,registered,profit[0]+sum(up),p['voluntary_reserve_rate'])
        ordinary=min(max(sum(profit)-cost,0)*p['payout'],max(ret,0),max(cash[0]-p['cash_floor'][0],0))
        cash[0]-=ordinary;ret-=ordinary
        special=min(pending,max(ret,0),max(cash[0]-p['cash_floor'][0],0)) if y>=p['release_year'] else 0.
        cash[0]-=special;ret-=special;pending-=special
        redemption=p['redemption'][y-1]
        if redemption:
            reduced=capital_return(cash[0],redemption,paid,registered,shares,par_value=p['share_par'],external_debt_due=debt[0])
            cash[0]=reduced['cash'];paid=reduced['basis'];registered=reduced['registered'];shares=reduced['shares']
        err=sum(cash)+sum(term)-(opening+fcf+sum(fin)-sum(interest)-sum(principal)-ordinary-special-cost-redemption)
        assert abs(err)<1e-7 and min(cash+term+debt)>-1e-7
        rows.append(dict(year=y,revenue=rev[:],ebit=ebit,tax=tax,nopat=nop,fcf=fcf,da=da,capex=capex,wc=wc,
          net_profit=sum(profit)-cost,cash=cash[:],term=term[:],debt=debt[:],principal=principal,
          parent_legal=ret,parent_reserve=reserve,parent_profit=profit[0]+sum(up),statutory_allocation=alloc,voluntary_allocation=vol,
          economic_residual_profit=profit[1:],deposit_income=sum(fin),interest=sum(interest),
          old_receivable=rec[:],principal_receipts=receipts,internal_support=funding,internal_interest=internal,
          economic_upstream=up,access_cost=cost,ordinary=ordinary,special=special,capital_redemption=redemption,registered=registered,shares=shares,holder_share_fraction=shares/p['external_shares'],distribution=ordinary+special+redemption,cash_identity_error=err))
    return rows

def value(rows,p,r=.09,g=None,end_margin=None,ic_ratio=None,pe=20,terminal_growth0=None,horizon=None):
    g=p['tail_g'] if g is None else g;end_margin=p['tail_margin'] if end_margin is None else end_margin
    ic=p['tail_ic'] if ic_ratio is None else ic_ratio;g0=p['tail_growth0'] if terminal_growth0 is None else terminal_growth0
    H=p['horizon'] if horizon is None else horizon
    if H<20 or r<=g:raise ValueError('tail requires convergent positive spread')
    s=rows[-1];p=copy.deepcopy(p);p['parent_registered']=s['registered'];rev=sum(s['revenue']);margin=s['ebit']/rev;ret=s['parent_legal'];reserve=s['parent_reserve']
    cash=[s['cash'][i]+s['term'][i]-p['cash_floor'][i] for i in range(3)]
    if min(cash)<-1e-8:raise ValueError('necessary operating liquidity unfunded at Y5')
    for i in range(3):
        if cash[i]+1e-8<s['debt'][i]:raise ValueError('terminal debt unfunded')
        cash[i]-=s['debt'][i]
    equity=realize(p['equity_asset'],p['equity_book'],p['equity_tax_basis'],p['tax'],p['equity_sale_fee'])
    cash[0]+=equity['net'];ret,reserve,_,_=legal_update(ret,reserve,p['parent_registered'],equity['profit'],p['voluntary_reserve_rate'])
    receiv=s['old_receivable'][:]
    for i in (1,2):
        a=min(cash[i],receiv[i-1]);move(cash,i,0,a);receiv[i-1]-=a
    # P's own existing retained earnings can support immediate financial release at Y5.
    now=min(cash[0],max(ret,0));cash[0]-=now;ret-=now
    financial=now;operating=0.;tails=[];minmargin=ret;basis=p['parent_cost_basis_return'][:]
    original_excess=cash[:];totalcost=equity['cost']+equity['tax']
    for k in range(1,H+1):
        old=sum(cash); saved=TAIL_ROWS[k-1]
        newrev=saved['revenue'];m=saved['margin'];nop=saved['nopat']
        reinvest=saved['reinvestment'];fcf=saved['operating_cash']
        minimum_income=[x*p['deposit_yield']*(1-p['tax']) if p['minimum_cash_interest'] else 0. for x in p['cash_floor']]
        fin=[x*p['deposit_yield']*(1-p['tax']) for x in cash]
        op=[fcf*w+minimum_income[i] for i,w in enumerate(p['profit_weights'])]
        if min(op)<0:raise ValueError('negative tail requires explicit recovery or exit path')
        cost=sum(op[i]*p['access_cost'][i] for i in (1,2));netop=sum(op)-cost
        parentprofit=nop*p['profit_weights'][0]+minimum_income[0]+fin[0]+sum(op[i]*(1-p['access_cost'][i]) for i in (1,2))
        for i in range(3):cash[i]+=fin[i]
        ret,reserve,alloc,vol=legal_update(ret,reserve,p['parent_registered'],parentprofit,p['voluntary_reserve_rate'])
        # Operating payments are cash of this year, not a second use of old principal.
        if ret+1e-7<netop:raise ValueError('parent legal profits cannot support tail operating payout at year '+str(k+5))
        ret-=netop;principal_receipt=[0.,0.];capital=[0.,0.];up=[0.,0.];friction=0.
        if k>=p['financial_release_delay']:
            for i in (1,2):
                # No synthetic local statutory earnings: a finite economic realization budget.
                gross=cash[i];fee=gross*p['access_cost'][i];net=gross-fee;cash[i]=0.;cash[0]+=net;friction+=fee
                capital[i-1]=min(net,basis[i]);basis[i]-=capital[i-1]
                up[i-1]=net-capital[i-1]
            ret,reserve,a,v=legal_update(ret,reserve,p['parent_registered'],sum(up),p['voluntary_reserve_rate']);alloc+=a;vol+=v
        paid=min(cash[0],max(ret,0));cash[0]-=paid;ret-=paid
        financial+=paid/(1+r)**k;operating+=netop/(1+r)**k;totalcost+=friction
        err=sum(cash)-(old+sum(fin)-friction-paid)
        assert abs(err)<1e-6
        minmargin=min(minmargin,ret)
        tails.append(dict(year=5+k,revenue=newrev,margin=m,nopat=nop,reinvestment=reinvest,
          operating_cash=fcf,necessary_cash=p['cash_floor'],necessary_cash_income=sum(minimum_income),
          economic_upstream_operation=[op[i]*(1-p['access_cost'][i]) for i in (1,2)],
          operating_access_cost=cost,operating_distribution=netop,financial_interest=sum(fin),
          economic_capital_return=capital,economic_dividend_receipts=up,financial_access_cost=friction,
          financial_distribution=paid,distribution=netop+paid,parent_legal=ret,parent_reserve=reserve,
          statutory_allocation=alloc,voluntary_allocation=vol,unreleased_financial=cash[:],cash_identity_error=err))
        rev=newrev
    # Beyond H, same economics exactly: growing business cash and fixed minimum-cash interest.
    access=sum(w*(1-c) for w,c in zip(p['profit_weights'],p['access_cost']))
    grow_cash=fcf*access
    fixed_income=sum(x*(1-c) for x,c in zip(minimum_income,p['access_cost']))
    continuation=grow_cash*(1+g)/(r-g)+fixed_income/r
    operating+=continuation/(1+r)**H
    if sum(cash)>1e-7 or sum(receiv)>1e-7:raise ValueError('unrealized principal remains; no zeroing at horizon')
    tv=operating+financial;dpv=sum(x['distribution']/(1+r)**x['year'] for x in rows)
    # PE uses pure operation NOPAT adjusted for access; min-cash income separately capitalized, not all cash added twice.
    method2=(dpv+(s['nopat']*access*pe+fixed_income/r+financial)/(1+r)**5)/SHARES
    return dict(per_share=(dpv+tv/(1+r)**5)/SHARES,method2=method2,terminal_per_share=tv/SHARES,
      distribution_pv=dpv,terminal_operating=operating,terminal_financial=financial,terminal_pv_share=(tv/(1+r)**5)/(dpv+tv/(1+r)**5),
      tail= tails,continuation_at_horizon=continuation,continuation_pv_at_y5=continuation/(1+r)**H,
      parent_min_legal_after_distribution=minmargin,realization=equity,initial_financial_distribution=now,
      initial_remaining_financial=original_excess,financial_cost_total=totalcost,tail_access_factor=access)


import importlib.util,sys,stat,os
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent
CODE='300685'
CHECKER_NAME='2026-Q3-capital-20261102-check.py'
CHECKER_SHA='4a1361122f0f7719e3a072d025a99a94adf7e48473cc46c50ea99689493ba57d'
EVENT={'deduction': 'Full parent and group cash, one external payment; no registered cancellation', 'external_shares_after': '379434869', 'external_shares_before': '380985869', 'fees': 'Source excludes transaction fees', 'paid_transaction_oct31': '199896151.37', 'paid_transaction_q3': '171127899.17', 'post_q3_cash': '28768252.20', 'registered_shares_unchanged': '390105169', 'source_ids': ['1225598652', '1225652740'], 'treasury_increment': '1551000'}
OUTPUT_META={'classification': 'NEW_RECONSTRUCTION_NOT_OLD189_BYTE_RECOVERY', 'event': {'deduction': 'Full parent and group cash, one external payment; no registered cancellation', 'external_shares_after': '379434869', 'external_shares_before': '380985869', 'fees': 'Source excludes transaction fees', 'paid_transaction_oct31': '199896151.37', 'paid_transaction_q3': '171127899.17', 'post_q3_cash': '28768252.20', 'registered_shares_unchanged': '390105169', 'source_ids': ['1225598652', '1225652740'], 'treasury_increment': '1551000'}, 'event_asof': '2026-11-02', 'event_input_sha256': '1dcfa6e215877e9489f8ffdea8cdaffbf4d524e7898af3964298b84f5576e57b', 'historical_field_roles': {'/results/base/actual_first_changed_year': 'historical original diagnostic label, not current event-change evidence', '/results/base/changed': 'historical original diagnostic metadata, not current economic changes', '/results/base/classification': 'full_operating_path describes the original stored operating scenario, not a freshly generated forecast'}, 'old_diagnostics_are_historical_not_updated': True, 'operating_forecast_recomputed': False, 'original_baseline_sha256': 'f65ad246edefcf19232cb35202725a82ebc989c47b0e2c7c404933b3a04bf8aa', 'period': '2026-Q3', 'scope': 'base5 cash +base/low/high200-tail cash; other16 and 50/100/500 convergence historical', 'scope_note': 'Original full company forecast dispatcher not executed; operating rows reused. Original finite terminal/NOPAT and normalized earning-power formulas are evaluated where required for selected cash valuation, not called new researched forecasts.', 'symbol': 'CN:300685', 'public_delivery_note': 'New reconstruction of selected current cash from exact published operating budgets. Old unselected diagnostics remain historical. This is not recovery of the lost original189 bytes.'}

def selected_cash(old,event,changed):
    m=sys.modules[__name__]
    saved = old['scenarios']['base']
    spec = copy.deepcopy(saved['inputs'])
    if changed:
        spec['opening_cash'][0] -= float(event['post_q3_cash'])/1e6
        spec['external_shares'] = float(event['external_shares_after'])/1e6
        m.SHARES = spec['external_shares']
    m.CACHE_ROWS = saved['rows']
    rows = m.simulate(spec)
    valuations = {}
    for key, args in [('valuation', ()), ('low', (.095,.02,.29,.85,18)), ('high', (.085,.025,.31,.75,22))]:
        m.TAIL_ROWS = saved[key]['tail']
        assert len(m.TAIL_ROWS) == 200
        valuations[key] = m.value(rows, spec, *args)
    base = copy.deepcopy(saved)
    base.update(inputs=spec, rows=rows, **valuations)
    # The original field describes original diagnostics relative to original base.
    # Do not silently turn that historical label into a newly compared diagnostic.
    result = {'base': base}
    oracle = {'base': saved}
    projection = result
    scope = 'base5 cash +base/low/high200-tail cash; other16 and 50/100/500 convergence historical'

    return result,projection,oracle,scope
