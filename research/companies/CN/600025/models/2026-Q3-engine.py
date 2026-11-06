#!/usr/bin/env python3
"""600025 entity-aware research model. Units CNY bn / bn shares / bn kWh.
Economic units NEVER have registered capital or statutory reserves.
Actual entity opening estimates are explicitly budgets, not reported balances.
No quote input; deterministic stdlib output; no repository dependencies.
"""
import json,copy,math,gzip,base64,hashlib,sys
from pathlib import Path
P=Path(__file__).resolve().parent
A={'S': 18.631094257,
 'D': 126.50412978373,
 'PD': 69.41272394423,
 'PERP': 16.217,
 'FACT': {'shares': 18.631094257,
          'financial_debt_including_lease_and_accruals': 126.50412978373,
          'parent_debt': 69.41272394423,
          'cash_equivalents': 3.72253673088,
          'cash_funds': 4.73352182637,
          'parent_cce': 0.38992885011,
          'ordinary_book_equity': 73.04455561263,
          'nci_book': 6.56759097069,
          'financial_investments': 5.414735115619999,
          'parent_retained': 23.90057410048,
          'parent_reserve': 5.39638671312,
          'q3_revenue': 7.95814429781,
          'q3_np': 3.17752803387,
          'q3_cfo': 6.58246446545,
          'q3_capex': 3.9003150373499995,
          'ytd_fcf_before_finance': 4.51814060571,
          'q3_gross_margin_ytd': 0.588341589657333,
          'capital_proxy_2024': 194.44004834719,
          'capital_proxy_2025': 204.46046735646,
          'operating_ebit_proxy_2024': 12.726792427520001,
          'operating_ebit_proxy_2025': 13.11827252233,
          'roic_proxy_2025': 0.05590632854565885,
          'incremental_roic_proxy_2024_to_2025': 0.03320800061161727},
 'FACTS': {'RM': {'dynamic': 58.3815079,
                  'engineering': 49.06,
                  'cip': 8.28299014527,
                  'old_interest': 0.39785046984,
                  'gen': 11.281,
                  'gw': 2.6,
                  'owner': 'upper',
                  'q3_engineering_paid': 0.6951461275529397},
           'GS': {'dynamic': 50.40133460819,
                  'cip': 4.42357346965,
                  'old_interest': 0.07648238126,
                  'gen': None,
                  'gw': 2.2,
                  'owner': 'parent_direct',
                  'q3_engineering_paid': 0.37124636314207304},
           'BDa': {'dynamic': 23.4922659,
                   'cip': 3.44129553187,
                   'old_interest': 0.11422327861,
                   'gen': 6.149,
                   'gw': 1.5,
                   'owner': 'changdu',
                   'q3_engineering_paid': 0.2888091402729402},
           'GX': {'dynamic': 31.7,
                  'cip': 2.27377883062,
                  'old_interest': 0.12294163552,
                  'gen': 9.036,
                  'gw': 2.1,
                  'owner': 'guxue',
                  'q3_engineering_paid': 0.1908258396178282},
           'BDuo': {'dynamic': 15.85,
                    'cip': 0.44507355036,
                    'old_interest': 0.0,
                    'gen': 3.096,
                    'gw': 0.72,
                    'owner': 'upper',
                    'q3_engineering_paid': 0.03735259243132989},
           'GLB': {'dynamic': 4.95,
                   'cip': 0.82378837876,
                   'old_interest': 0.0,
                   'gen': 1.162,
                   'gw': 0.195,
                   'owner': 'parent_direct',
                   'q3_engineering_paid': 0.06913605972900282},
           'PV_completion': {'dynamic': 8.75,
                             'engineering': 8.75,
                             'cip': 6.25152322764,
                             'old_interest': 0.0,
                             'gen': 3.5,
                             'gw': 2.5,
                             'owner': 'economic_completion_budget',
                             'solar': True,
                             'q3_engineering_paid': 0.5246562034705335}},
 'SC': {'engineering_low': {'rate': 0.06,
                            'loan': 0.032,
                            'finance_share': 0.1,
                            'cost': 1.1,
                            'life': 40,
                            'first': [2035, 2035, 2034, 2035, 2038, 2033, 2029],
                            'gen': [11.281, 8.0, 6.149, 8.89, 2.8, 1.05, 3.25],
                            'price': [0.4, 0.27, 0.3, 0.3, 0.3, 0.24, 0.25],
                            'water': 0.95,
                            'upstream_equity': 1.0},
        'central': {'rate': 0.05,
                    'loan': 0.028,
                    'finance_share': 0.15,
                    'cost': 1.0,
                    'life': 45,
                    'first': [2033, 2033, 2032, 2033, 2036, 2031, 2028],
                    'gen': [11.281, 9.46, 6.149, 9.036, 3.096, 1.162, 3.5],
                    'price': [0.425, 0.3, 0.33, 0.33, 0.33, 0.26, 0.29],
                    'water': 1.0,
                    'upstream_equity': 1.0},
        'engineering_high': {'rate': 0.05,
                             'loan': 0.024,
                             'finance_share': 0.2,
                             'cost': 0.95,
                             'life': 50,
                             'first': [2033, 2031, 2031, 2032, 2035, 2029, 2028],
                             'gen': [11.281, 11.0, 6.149, 9.4, 3.6, 1.22, 4.0],
                             'price': [0.45, 0.33, 0.36, 0.36, 0.36, 0.28, 0.34],
                             'water': 1.0,
                             'upstream_equity': 1.0},
        'core_low': {'rate': 0.055,
                     'loan': 0.03,
                     'finance_share': 0.15,
                     'cost': 1.03,
                     'life': 45,
                     'first': [2033, 2033, 2032, 2033, 2036, 2031, 2028],
                     'gen': [11.281, 8.8, 6.149, 9.036, 3.096, 1.162, 3.5],
                     'price': [0.4, 0.28, 0.31, 0.31, 0.31, 0.25, 0.27],
                     'water': 1.0,
                     'upstream_equity': 1.0,
                     'solar_cost_factor': 1.2},
        'core_high': {'rate': 0.045,
                      'loan': 0.026,
                      'finance_share': 0.15,
                      'cost': 0.97,
                      'life': 45,
                      'first': [2033, 2033, 2032, 2033, 2036, 2031, 2028],
                      'gen': [11.281, 10.2, 6.149, 9.036, 3.096, 1.162, 3.5],
                      'price': [0.45, 0.32, 0.35, 0.35, 0.35, 0.27, 0.31],
                      'water': 1.0,
                      'upstream_equity': 1.0,
                      'solar_cost_factor': 0.92},
        'cyclical': {'rate': 0.05,
                     'loan': 0.03,
                     'finance_share': 0.15,
                     'cost': 1.0,
                     'life': 45,
                     'first': [2033, 2033, 2032, 2033, 2036, 2031, 2028],
                     'gen': [11.281, 9.46, 6.149, 9.036, 3.096, 1.162, 3.5],
                     'price': [0.425, 0.3, 0.33, 0.33, 0.33, 0.26, 0.29],
                     'water': 1.0,
                     'upstream_equity': 1.0,
                     'mature_water': [0.85, 0.9, 0.96, 1, 1],
                     'mature_price': 1.01,
                     'parent_credit': 9.0},
        'structural': {'rate': 0.05,
                       'loan': 0.035,
                       'finance_share': 0.15,
                       'cost': 1.0,
                       'life': 45,
                       'first': [2033, 2033, 2032, 2033, 2036, 2031, 2028],
                       'gen': [11.281, 9.46, 6.149, 9.036, 3.096, 1.162, 3.5],
                       'price': [0.425, 0.3, 0.33, 0.33, 0.33, 0.26, 0.29],
                       'water': 0.85,
                       'upstream_equity': 1.0,
                       'mature_water': [0.9, 0.85, 0.85, 0.85, 0.85],
                       'mature_price': 0.92,
                       'mature_cost': 1.1,
                       'parent_credit': 5.0},
        'upside': {'rate': 0.05,
                   'loan': 0.024,
                   'finance_share': 0.15,
                   'cost': 1.0,
                   'life': 45,
                   'first': [2033, 2033, 2032, 2033, 2036, 2031, 2028],
                   'gen': [11.281, 9.46, 6.149, 9.036, 3.096, 1.162, 3.5],
                   'price': [0.425, 0.3, 0.33, 0.33, 0.33, 0.26, 0.29],
                   'water': 1.04,
                   'upstream_equity': 1.0,
                   'mature_water': [1.04, 1.04, 1.04, 1.04, 1.04],
                   'mature_price': 1.03}},
 'ACQ': {'price': 8.7012044,
         'old_debt': 8.09361587276,
         'cash': 0.04648791615,
         'legal_retained': -1.56786683744,
         'old_capital_payable': 0.21884897942,
         'registered_capital_source': 9.7924165,
         'paid_capital_source': 9.79241652163},
 'capital_cost_method': {'method': 'APV',
                         'rate_semantics': 'nominal CNY unlevered operating cost, NOT tax-adjusted WACC',
                         'core_Ku': [0.045, 0.055],
                         'central_Ku': 0.05,
                         'reference_RF': 0.0181,
                         'reference_betaU': 0.5721,
                         'reference_ERP': 0.0657,
                         'specific_project_premium': 0,
                         'reference_date': '2025-03-31',
                         'reference_disclosed': '2025-12-31',
                         'reference_url': 'https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=11891305&stockid=000722',
                         'source_derived_Ku_without_rc': 0.05568697,
                         'shield_discount': 'same Ku; only tax actually saved by model financing and '
                                            'depreciation, no terminal leverage',
                         'perpetual_tax_shield': False,
                         'large_hydro_peer_betaU': [0.3107, 0.4923, 0.3616],
                         'adopted_betaU_equivalent': 0.4855403348554034,
                         'reason': 'Large-hydro evidence given greater weight than unweighted '
                                   'small-company-inclusive mean. 5% central, 4.5-5.5% range; no '
                                   'project-specific risk premium added.'},
 'VAT_budget': {'Q3_estimated_total': 3.66609092479,
                'parent_budget': 0.2,
                'subsidiary_NCI_share_budget': 0.1,
                'recovery_years': 4,
                'target_disclosed_May31_credit': 0.39221314626,
                'qualification': 'group Q3 tax credit is estimate from Q3 totals less H1 non-VAT components, '
                                 'parent allocation not disclosed; full and zero/delay tests provided',
                'future_capex': 'nominal engineering cost proxy before debt financing; recoverable VAT '
                                'treatment in disclosed total budget not fully reconciled, net-cost minus8% '
                                'full path is alternative not fact'},
 'NCI_budget': {'opening_minor_cash_bn': 0.4,
                'opening_bounds_bn': [0, 1.15],
                'basis': 'H1 p181-185 reported NCI profit by real entity; normalized annual0.8bn. Important '
                         'entities weighted current assets including nested Ruili ownership give '
                         'roughly1.15bn scale reference, NOT cash fact or complete upper bound. 0.4bn '
                         'central liquidity budget,0-1.15 sensitivities.',
                'economic_cash_entitlement': 'normal profit proxy after sustaining capital, '
                                             'multiplier0.8-1.2 alternatives; not statutory distributable '
                                             'profits',
                'payout': '50% current entitlement plus20% opening owned liquid reserve from2036; foreign '
                          'run-off shared with existing revenue model; residual capital returned on modeled '
                          'foreign exit',
                'discount': 'same Ku, finite foreign and continuing domestic; retained minority cash never '
                            'available to parent',
                'normalized_profit_by_entity_bn': {'云南联合电力': 0.3276975737,
                                                   '桑河二级水电': 0.22545125684,
                                                   '龙开口': 0.01508410178,
                                                   '清洁能源合伙': 0.10705748942,
                                                   '四川泸定': 0.02732937992,
                                                   '其他既有少数经济预算': 0.09738019834},
                'cash_sensitivities': {'fast': {'payout': 0.8, 'release_rate': 0.5, 'start': 2027},
                                       'slow': {'payout': 0.3, 'release_rate': 0.1, 'start': 2041}}},
 'target_branch_tax': 'X/W2 HNYL branches use9% through2027,15% through2030,25% later; pool current taxable '
                      'non-exempt branch profit/loss with90% existing HNYL operating budget. No inherited '
                      'tax-loss carryforward assumed.',
 'downstream_benefit': '2035 onwards 2.7bn kWh*0.22 CNY net revenue included parent mature earnings and '
                       'cash, no separate extra EV.',
 'PV_completion_ownership_budget': {'core_economic_ownership': 1.0,
                                    'condition': 'full final asset-to-entity mapping not disclosed; not a '
                                                 'factual 100% legal ownership assertion',
                                    'external_share_sensitivity': 0.2},
 'depreciation_budget': 'first half-year operation uses half annual original tax-basis depreciation; '
                        'remaining half at final year; HNYL N and W2 full-year starts use full-year fraction',
 'tax_pooling_budget': 'only current-year same-taxpayer branches at same applicable tax rate; direct parent '
                       'GS/GLB, upper RM/BDuo, target X/W2; no cross-entity offset',
 'capital_recovery_budget': 'PV after25 operating years plus5 realization buffer and PV-project debt '
                            'cleared, not after all unrelated mature-sub debt; proportionate cancellation of '
                            'nominal and paid capital separately'}
S=A['S'];D=A['D'];PD=A['PD'];PERP=A['PERP'];F=A['FACT'];PF=A['FACTS'];SC=A['SC'];ACQ=A['ACQ']
END=2101
CRED=7.64707985906-.26956263829+.23835321232+.06437698640
REGISTER={'parent':18.631094257,'upper':3.,'changdu':4.8,'guxue':5.6,'target':9.7924165,'ND':.1}
# H1 group nonstatutory total supplies an illustrative bound; exact parent split unknown.
PRES=5.39638671312-.016-.00353267441

def reserve(profit,retained,statutory,registered,paid=None):
    return min(.1*max(0.,profit+min(0.,retained)),max(0.,.5*registered-statutory))

def capital_action(cash,shares,registered,paid,amount,price,kind):
    """Real share/cash/registered-capital linkage; no forecast corporate action assumed."""
    n=amount/price
    if kind=='issue':return cash+amount,shares+n,registered+n,paid+n
    if kind=='reduction':
        if n>shares+1e-10 or amount>cash+1e-10:raise ValueError('capital reduction infeasible')
        fraction=n/shares if shares else 0.
        return cash-amount,shares-n,registered*(1-fraction),paid*(1-fraction)
    raise ValueError(kind)

def realized_capital(cash,removed_basis,tax=0.,fee=0.,ownership=1.):
    """Recipient cash and investment disposal gain are separate; external costs once."""
    return ownership*(cash-tax-fee),ownership*(cash-tax-fee-removed_basis)

def fund(cash,flow,wanted,buffer,debt,limit):
    avail=cash+flow-buffer
    if avail < -limit-1e-8:raise ValueError(f'zero-distribution funding gap {-avail:.6f} > credit {limit:.6f}')
    d=min(max(0,wanted),max(0,avail+limit));borrow=max(0,d-avail)
    repay=min(debt,max(0,avail-d));end=cash+flow-d+borrow-repay
    assert abs(end-(cash+flow-d+borrow-repay))<1e-8 and end>=buffer-1e-8
    return d,borrow-repay,end

def legal_step(state,profit,cashflow,registered,payout=1.,buffer=0.,old_receipt=0.,declaration=0.):
    """One real domestic entity; old receivable collection is cash only."""
    openingcash=state['cash'];openingretained=state['retained'];openingreserve=state['reserve']
    income=profit+declaration
    take=reserve(income,state['retained'],state['reserve'],registered)
    retained=state['retained']+income-take
    cash=state['cash']+cashflow+old_receipt
    support=max(0,buffer-cash);cash+=support
    div=min(max(0,retained),max(0,cash-buffer)*payout)
    state.update(retained=retained-div,reserve=state['reserve']+take,cash=cash-div)
    assert abs(state['cash']-(openingcash+cashflow+old_receipt+support-div))<1e-8
    assert abs(state['retained']+state['reserve']-(openingretained+openingreserve+income-div))<1e-8
    return dict(profit=income,appropriation=take,declared=div,support=support,**state)

def economic_step(state,profit,flow,payout=.3,buffer=0.):
    """Non-entity budget: no legal reserve or registered capital is invented.
    Early 85% cumulative-profit ceiling converges to a finite 1.5-year profit buffer; NOT a statutory account.
    Unpaid cash remains an identified financial asset; earning 1.5% where material.
    """
    state['profit_budget']+=profit
    cash=state['cash']+flow
    support=max(0,buffer-cash);cash+=support
    cushion=min(.15*max(0,state['profit_budget']),1.5*max(0,profit))
    room=max(0,state['profit_budget']-cushion-state['declared_total'])
    wanted=max(0,profit*payout)
    if payout>=.8:wanted+=max(0,cash-buffer)*.2
    paid=min(room,max(0,cash-buffer),wanted)
    state['declared_total']+=paid;state['cash']=cash-paid
    return dict(profit_budget=state['profit_budget'],declared=paid,support=support,cash=state['cash'],ceiling_room=room)

def pooled_tax_saving(taxable_items,rate):
    """Only departments/branches of ONE taxpayer at the same rate, no cross-company loss offset."""
    return sum(max(0.,v)*rate for v in taxable_items)-max(0.,sum(taxable_items))*rate

def depreciation_fraction(age,years,first_fraction):
    if age<0:return 0.
    if age==0:return first_fraction
    if age<years:return 1.
    if age==years:return 1-first_fraction
    return 0.

def engineering(f,c,i,first=None,end=END,legacy=False):
    first=first or c['first'][i];renew=f.get('solar') or f.get('wind');life=25 if renew else (c['life'] if legacy else end-first+1)
    cost=f.get('engineering',f['dynamic']*(1-c['finance_share']))*c['cost']*(c.get('solar_cost_factor',1.) if f.get('solar') else 1.)
    sunk=f['cip']-f['old_interest']+f.get('q3_engineering_paid',0);remain=max(0,cost-sunk)
    debt=capint=0.;rows=[]
    for y in range(2027,end+1):
        operating=y>=first and y<first+life;ramp=f.get('first_ramp',.5) if y==first else (1. if operating else 0.)
        cap=remain/(first-2027) if y<first else (remain if first<=2027 and y==2027 else 0.)
        vol=c['gen'][i]*c['water']*ramp*(.997**max(0,y-first) if f.get('wind') else (.995**max(0,y-first) if f.get('solar') else 1.))
        if not renew:vol*=c.get('hydro_retention',1.)**max(0,y-first-20)
        rev=vol*.992*c['price'][i]/1.13
        op=f['gw']*(.08 if f.get('wind') else (.05 if f.get('solar') else .20))*ramp
        maint=f['gw']*(.05 if f.get('wind') else (.035 if f.get('solar') else .12))*ramp
        # Incremental major-refurbishment reserve, real cash reinvestment not trapped legal capital.
        if not renew and not legacy:maint+=.004*cost*ramp
        begin=debt
        build_interest=c['loan']*(debt+.35*cap)/(1-.35*c['loan']) if cap else 0.
        # Same-year completion and revenue: allocate the forecast year's total finance cost once.
        capitalized=build_interest*(1-ramp if operating else 1.)
        operating_interest=build_interest-capitalized if cap else debt*c['loan']
        draw=.7*(cap+capitalized);equity=.3*(cap+capitalized)
        debt+=draw;capint+=capitalized
        df=depreciation_fraction(y-first,20 if renew else 45,f.get('first_ramp',.5)) if operating else 0.
        replacement_da=(f['gw']*.12+.004*cost)*ramp if not renew and not legacy and operating and y-first>=45 else 0.
        da=(cost+f['old_interest']+capint)/(20 if renew else 45)*df+replacement_da
        ordinary_rate=(.09 if y<=2027 else .15 if y<=2030 else .25) if f.get('target_tax') else .25
        taxrate=(0. if y<first+3 else .125 if y<first+6 else ordinary_rate) if (f.get('tax_holiday') or c.get('new_project_holiday',False)) else ordinary_rate
        pretax=rev-op-da-operating_interest
        tax=max(0,pretax)*taxrate;profit=pretax-tax
        available=profit+da-maint
        equity+=max(0,-available);available=max(0,available)
        repay=min(debt,.7*available);debt-=repay;netcash=available-repay
        uda=(cost+f['old_interest'])/(20 if renew else 45)*df+replacement_da
        fcff=rev-op-max(0,rev-op-uda)*taxrate-maint-cap
        interest=capitalized+operating_interest
        assert abs(rev-op-tax-cap-maint-interest+draw+equity-repay-netcash)<1e-8
        rows.append(dict(year=y,taxrate=taxrate,pretax=pretax,unlevered_taxable=rev-op-uda,unlevered_da=uda,revenue=rev,operating=op,tax=tax,da=da,profit=profit,engineering=cap,maintenance=maint,interest=interest,capitalized_interest=capitalized,borrowing=draw,repayment=repay,debt=debt,equity_call=equity,economic_cash=netcash,fcff=fcff,tax_shield=max(0,rev-op-uda)*taxrate-tax))
    tail=0 if renew or legacy else rows[-1]['fcff']/c['rate']
    return dict(first=first,engineering_cost=cost,remaining=remain,tail_enterprise=tail,rows=rows)

def mature(c,year,legacy=False):
    age=year-2027;infl=1.005**age
    w=c.get('mature_water',[1]*5)[min(age,4)];pf=c.get('mature_price',1);cf=c.get('mature_cost',1)
    runoff=max(0,min(1,(24-age)/10)) if age>=15 else 1.
    rev=(25.6*c.get('hydro_retention',1.)**max(0,age-20)+1.6*runoff)*infl*w*pf
    rev+=2.7*.22 if year>=2035 else 0.
    cost=6.2*infl*cf;transition=max(0.,min(1.,(age-19)/20)) if not legacy else 0.
    da=(7.5*(1-transition)+(c.get('maintenance',4.)+.4)*transition)*infl;tax=.15 if year<=2030 else .25
    maint=c.get('maintenance',4.)*infl+(8*infl if (age+1)%20==0 else 0)
    if legacy and year>2026+c.get('mature_life',50):rev=cost=da=maint=0
    fcff=(rev-cost-da)*(1-tax)+da-maint if rev-cost-da>=0 else rev-cost-maint
    return dict(year=year,revenue=rev,cost=cost,da=da,maintenance=maint,taxrate=tax,fcff=fcff,ebit=rev-cost-da)

def target(c,end=END,legacy=False):
    tc=copy.deepcopy(c);tc.update(first=[2027+c.get('acq_delay',0),2028+c.get('acq_delay',0),2026+c.get('acq_delay',0)],gen=[2.7,.26,.338],price=[v*c.get('target_tariff',1.) for v in [.35,.34,.34]])
    fs={'X':dict(dynamic=18.617,cip=3.91921463674,old_interest=.11426267834,gw=.6,target_tax=True),'W2':dict(dynamic=.810,engineering=.810*.95,cip=.01261966514,old_interest=0,gw=.1,wind=True,first_ramp=1.,target_tax=True),'N':dict(dynamic=.5331218,engineering=.5331218*.95,cip=.33226816921,old_interest=.00358063057,gw=.13,wind=True,tax_holiday=True,first_ramp=1.)}
    ps={n:engineering(f,tc,i,end=end,legacy=legacy) for i,(n,f) in enumerate(fs.items())}
    st=dict(retained=-1.56786683744,reserve=0.,cash=.9*ACQ['cash']);nd=dict(retained=0.,reserve=0.,cash=0.)
    sub=dict(profit_budget=0.,declared_total=0.,cash=.1*ACQ['cash']);debt=ACQ['old_debt'];recv=0;ndpay=subpay=0.;ndbasis=.05179;ndclosed=False;target_registered=REGISTER['target'];rows=[]
    for t,y in enumerate(range(2027,end+1)):
        vat_recovery=c.get('vat_scale',1.)*(.36794333648+.02426980978)/c.get('vat_years',4) if t<c.get('vat_years',4) else 0.
        infl=1.005**t;factor=.7+(.3*.995**t if t<25 else 0.)
        w=c.get('mature_water',[1]*5)[min(t,4)];pf=c.get('mature_price',1)
        rev=1.15*factor*infl*w*pf*c.get('target_tariff',1.);op=.28*factor*infl;da=(.4*(1-max(0.,min(1.,(t-19)/20)))+.14*max(0.,min(1.,(t-19)/20)))*factor*infl if not legacy else .4*factor*infl;maint=.14*factor*infl
        if legacy and y>2071:rev=op=da=maint=0
        interest=debt*(.016 if t<3 else c['loan']);pretax=rev-op-da-interest;profit=pretax-max(0,pretax)*(.09 if y==2027 else .15 if y<=2030 else .25)
        pr={n:p['rows'][t] for n,p in ps.items()}
        tr=.09 if y<=2027 else .15 if y<=2030 else .25
        taxable_branches=[n for n in ('X','W2') if abs(pr[n]['taxrate']-tr)<1e-12]
        parent_pre=.9*pretax+sum(pr[n]['pretax'] for n in taxable_branches)
        target_tax_saving=pooled_tax_saving([.9*pretax]+[pr[n]['pretax'] for n in taxable_branches],tr)
        parent_unlev=.9*(rev-op-da)+sum(pr[n]['unlevered_taxable'] for n in taxable_branches)
        target_unlev_tax_saving=pooled_tax_saving([.9*(rev-op-da)]+[pr[n]['unlevered_taxable'] for n in taxable_branches],tr)
        nd['cash']-=ndpay;sub['cash']-=subpay
        ns=legal_step(nd,pr['N']['profit'],pr['N']['economic_cash']-pr['N']['equity_call'],.1)
        bs=economic_step(sub,.1*profit,.1*(profit+da-maint),.3 if t<9 else .8)
        ndbasis+=ns['support']
        liquidation_cash=liquidation_gain=liquidation_tax=0.
        if y>=ps['N']['first']+25+c.get('capital_return_delay',0) and not ndclosed:
            # Returns known/forecast paid investment first; excess taxed conservatively once.
            liquidation_tax=max(0,nd['cash']-ndbasis)*.25
            liquidation_cash=max(0,nd['cash'])
            # Tax is at HNYL recipient on gain over investment basis, not ND cash minus a fictitious asset tax basis.
            _,liquidation_gain=realized_capital(liquidation_cash,ndbasis,tax=liquidation_tax)
            if liquidation_cash>0:capital_action(liquidation_cash,.1,.1,min(.1,ndbasis),liquidation_cash,liquidation_cash/.1,'reduction')
            nd.update(cash=0.,retained=0.,reserve=0.);ndclosed=True
        declared=ns['declared']+bs['declared'];received=recv+c.get('receipt',.8)*declared;recv=(1-c.get('receipt',.8))*declared
        ndpay=(1-c.get('receipt',.8))*ns['declared'];subpay=(1-c.get('receipt',.8))*bs['declared'];nd['cash']+=ndpay;sub['cash']+=subpay
        oldpay=ACQ['old_capital_payable']/2 if t<2 else 0
        grant=c.get('target_grant',0.) if t==0 else 0.
        flow=target_tax_saving+vat_recovery+grant+liquidation_cash-liquidation_tax+.9*(profit+da-maint)+received+sum(pr[n]['economic_cash']-pr[n]['equity_call'] for n in ('X','W2'))-ns['support']-bs['support']-oldpay
        repay=min(debt,max(0,st['cash']+flow-.1)*.7);debt-=repay
        lr=legal_step(st,target_tax_saving+.9*profit+sum(pr[n]['profit'] for n in ('X','W2'))+liquidation_gain,flow-repay,target_registered,declaration=declared,buffer=.1)
        capital_return=0.;reduction_fraction=0.
        if y>=2053+c.get('capital_return_delay',0) and debt<1e-8 and sum(x['debt'] for x in pr.values())<1e-8:
            capital_return=min(max(0,st['cash']-.1)*.2,max(0,target_registered-1.))
            reduction_fraction=capital_return/target_registered if target_registered else 0.
            if capital_return:
                _,_,target_registered,_=capital_action(st['cash'],target_registered,target_registered,target_registered,capital_return,1.,'reduction')
                st['cash']-=capital_return
        rows.append(dict(year=y,target_branch_cash_tax_saving=target_tax_saving,target_branch_unlevered_tax_saving=target_unlev_tax_saving,profit=target_tax_saving+profit+sum(v['profit'] for v in pr.values())-liquidation_tax,ND_liquidation_cash=liquidation_cash,ND_liquidation_tax=liquidation_tax,ND_liquidation_taxpayer='HNYL_recipient_conservative_gain_tax_budget',ND_upstream_net_cash=liquidation_cash-liquidation_tax,ND_liquidation_gain=liquidation_gain,ND_investment_basis=ndbasis,ND_closed=ndclosed,depreciation=da+sum(v['da'] for v in pr.values()),vat_recovery=vat_recovery,capital_cash=maint+oldpay+sum(v['engineering']+v['capitalized_interest']+v['maintenance'] for v in pr.values())-grant-vat_recovery,statutory_profit=lr['profit'],registered=target_registered,capital_return=capital_return,capital_reduction_fraction=reduction_fraction,reserve=st['reserve'],retained=st['retained'],cash=st['cash']+sub['cash']+nd['cash'],general_debt=debt,project_debt=sum(x['debt'] for x in pr.values()),dividend=lr['declared'],support=lr['support'],receivable=recv,ND=dict(ns,ending_cash=nd['cash'],ending_registered=0. if ndclosed else .1,ending_shares=0. if ndclosed else .1),subsidiary_budget=bs,fcff=target_unlev_tax_saving+rev-op-max(0,rev-op-da)*(.09 if y==2027 else .15 if y<=2030 else .25)-maint-oldpay+grant+vat_recovery-liquidation_tax,tax_shield=target_tax_saving-target_unlev_tax_saving+max(0,rev-op-da)*(.09 if y==2027 else .15 if y<=2030 else .25)-(pretax-profit)))
    tail=0 if legacy else rows[-1]['fcff']/c['rate']
    return dict(rows=rows,projects=ps,tail_enterprise=tail)


NCI_BASE=A['NCI_budget']['normalized_profit_by_entity_bn']
def minority_step(states,c,year):
    age=year-2027;infl=1.005**age
    w=c.get('mature_water',[1]*5)[min(age,4)];pf=c.get('mature_price',1);cf=c.get('mature_cost',1)
    factor=max(0.,(w*pf-.3*cf)/.7)*c.get('nci_cash_multiplier',1.)
    runoff=max(0.,min(1.,(24-age)/10)) if age>=15 else 1.
    rows={}
    for name,base in NCI_BASE.items():
        foreign=name in ('云南联合电力','桑河二级水电')
        opening=states[name];profit=base*infl*factor*(runoff if foreign else c.get('hydro_retention',1.)**max(0,age-20))
        # Economic cash entitlement after sustaining capital equals normal profit in this explicit budget.
        # Cash not paid remains owned by those outside holders; no statutory reserve is invented.
        release=c.get('nci_release_rate',.2) if year>=c.get('nci_release_start',2036) else 0.
        payment=c.get('nci_payout',.5)*profit+opening*release
        if foreign and runoff==0:payment+=opening*(1-release)
        closing=opening+profit-payment;states[name]=closing
        rows[name]={'opening_restricted_cash':opening,'economic_profit_cash_budget':profit,'gross_cash_payment':payment,'closing_restricted_cash':closing,'foreign_budget':foreign}
    return rows

def run(name='central',overrides=None,end=END,legacy=False):
    c=copy.deepcopy(SC[name]);c.update(overrides or {})
    if name=='core_low':c.setdefault('maintenance',4.5)
    if name=='core_high':c.setdefault('maintenance',3.5)
    if legacy:c['mature_life']=60 if name=='core_high' else (40 if name=='engineering_low' else 50)
    projects={n:engineering(f,c,i,end=end,legacy=legacy) for i,(n,f) in enumerate(PF.items())}
    ta=target(c,end,legacy) if c.get('acquire',True) else None
    ncistates={n:c.get('nci_opening_cash',.4)*v/.8 for n,v in NCI_BASE.items()}
    pdebt=PD;sdebt=D-PD;pcash=F['parent_cce'];scash=F['cash_equivalents']-pcash
    retained=F['parent_retained'];stat=c.get('parent_reserve',PRES);receivable=.45110034756
    est={n:dict(retained=(-.15 if n=='upper' else 0.)+c.get('entity_opening_loss',0),reserve=0.,cash=0.) for n in ('upper','changdu','guxue')}
    pvbudget=dict(profit_budget=0.,declared_total=0.,cash=0.)
    maturebudget=dict(profit_budget=0.,declared_total=0.,cash=scash)
    target_investment_basis=ACQ['price'] if c.get('acquire',True) else 0.
    capital_recovery_basis={'newenergy':10.01558753253,'sichuan':5.81029529217};capital_recovery_registered={'newenergy':8.04587,'sichuan':1.4698}
    upreceivable=0.;newreceivable=0.;payables={n:0. for n in ('changdu','guxue','upper','pv')};rows=[];upper_pct=c.get('upper_share',0);raised=False
    for t,y in enumerate(range(2027,end+1)):
        mr=mature(c,y,False);infl=1.005**t;tax=mr['taxrate']
        # Q3 estimated VAT credit: latest gross lines less H1 identified non-VAT items.
        vat_total=(.60770786908-.00091764444+3.10183439590-.04253369575)*c.get('vat_scale',1.)
        vat_recovery=vat_total/c.get('vat_years',4) if t<c.get('vat_years',4) else 0.
        vat_parent=min(.2*c.get('vat_scale',1.),vat_total)/c.get('vat_years',4) if t<c.get('vat_years',4) else 0.
        vat_sub=vat_recovery-vat_parent;vat_nci=vat_sub*c.get('vat_nci',.1)
        w=c.get('mature_water',[1]*5)[min(t,4)];pf=c.get('mature_price',1);cf=c.get('mature_cost',1)
        # Direct parent and mature subsidiaries reconcile to the same group operating unit.
        parent_da=mr['da']*(5.3/7.5)
        parent_ebit=(19.3*w*pf*c.get('hydro_retention',1.)**max(0,t-20)-4.9*cf)*infl+(2.7*.22 if y>=2035 else 0.)-parent_da
        ppretax=parent_ebit-pdebt*c['loan'];pp=ppretax-max(0,ppretax)*tax
        spre=mr['ebit']-parent_ebit-sdebt*c['loan'];sp=spre-max(0,spre)*tax
        ncidetail=minority_step(ncistates,c,y);nciprofit=sum(z['economic_profit_cash_budget'] for z in ncidetail.values());ncipaid=sum(z['gross_cash_payment'] for z in ncidetail.values())+vat_nci
        nci_cash=sum(ncistates.values())
        pr={n:p['rows'][t] for n,p in projects.items()}
        direct_taxable=[n for n in ('GS','GLB') if abs(pr[n]['taxrate']-tax)<1e-12]
        direct_tax_saving=pooled_tax_saving([ppretax]+[pr[n]['pretax'] for n in direct_taxable],tax)
        direct_unlevered_saving=pooled_tax_saving([parent_ebit]+[pr[n]['unlevered_taxable'] for n in direct_taxable],tax)
        pp+=direct_tax_saving
        upper_taxable=[n for n in ('RM','BDuo') if abs(pr[n]['taxrate']-.25)<1e-12]
        upper_tax_saving=pooled_tax_saving([pr[n]['pretax'] for n in upper_taxable],.25)
        upper_unlevered_saving=pooled_tax_saving([pr[n]['unlevered_taxable'] for n in upper_taxable],.25)
        oldpayables=copy.deepcopy(payables)
        for en in ('changdu','guxue','upper'):est[en]['cash']-=payables[en]
        pvbudget['cash']-=payables['pv']
        cd=legal_step(est['changdu'],pr['BDa']['profit'],pr['BDa']['economic_cash']-pr['BDa']['equity_call'],4.8,payout=c.get('new_payout',.9))
        gx=legal_step(est['guxue'],pr['GX']['profit'],pr['GX']['economic_cash']-pr['GX']['equity_call'],5.6,payout=c.get('new_payout',.9))
        for en,rr in [('changdu',cd),('guxue',gx)]:
            payables[en]=(1-c.get('receipt',.8))*rr['declared'];est[en]['cash']+=payables[en]
        updecl=.89*(cd['declared']+gx['declared']);upreceived=upreceivable+c.get('receipt',.8)*updecl;upreceivable=(1-c.get('receipt',.8))*updecl
        upflow=upper_tax_saving+sum(pr[n]['economic_cash']-pr[n]['equity_call'] for n in ('RM','BDuo'))+upreceived-.89*(cd['support']+gx['support'])
        # 35% conditional branch: independent negotiated pre-money value, not CIP or equity-cost proxy.
        raise_cash=0.
        if upper_pct and t==c.get('raise_year',0):
            raise_cash=c.get('raise_cash',3.*.35/.65);est['upper']['cash']+=raise_cash;raised=True
        currentpct=upper_pct if raised else 0.
        registered=3/(1-currentpct) if raised else 3.
        up=legal_step(est['upper'],upper_tax_saving+sum(pr[n]['profit'] for n in ('RM','BDuo')),upflow,registered,payout=c.get('new_payout',.9),declaration=updecl)
        # PV_completion is explicitly an economic combination of新能源/Sichuan, not a made-up entity.
        pv_pct=c.get('pv_external_share',0.)
        pv=economic_step(pvbudget,pr['PV_completion']['profit'],pr['PV_completion']['economic_cash']-pr['PV_completion']['equity_call'],.5 if t<9 else .8)
        # Post-retirement capital recovery: real domestic entities, not a PV legal reserve pool.
        # Conditional pro-rata nominal reduction budget, after debt-free funding and retirement.
        # Future support increases actual parent investment-cost budget, not registered capital.
        totalreg=sum(capital_recovery_registered.values())
        for en in capital_recovery_basis:capital_recovery_basis[en]+=(1-pv_pct)*pv['support']*capital_recovery_registered[en]/totalreg if totalreg else 0.
        recovery={n:0. for n in capital_recovery_basis};recovery_cost=0.;pv_external_recovery=0.
        if y>=projects['PV_completion']['first']+30+c.get('capital_return_delay',0) and pr['PV_completion']['debt']<1e-8:
            grossamount=min(pvbudget['cash']*.2,sum(capital_recovery_registered.values())/max(1e-9,1-pv_pct),sum(capital_recovery_basis.values())/max(1e-9,1-pv_pct))
            amount=grossamount*(1-pv_pct);pv_external_recovery=grossamount*pv_pct
            totalreg=sum(capital_recovery_registered.values())
            for en in recovery:
                a=amount*capital_recovery_registered[en]/totalreg if totalreg else 0.
                a=min(a,capital_recovery_registered[en]);recovery[en]=a
                cost_removed=capital_recovery_basis[en]*a/capital_recovery_registered[en] if capital_recovery_registered[en] else 0.
                recovery_cost+=cost_removed
                # Nominal capital/share reduction at par; parent listed shares unchanged.
                _,_,reg,_=capital_action(a,capital_recovery_registered[en],capital_recovery_registered[en],capital_recovery_registered[en],a,1.,'reduction')
                capital_recovery_registered[en]=reg;capital_recovery_basis[en]-=cost_removed
            pvbudget['cash']-=sum(recovery.values())+pv_external_recovery
        capital_recovery=sum(recovery.values());capital_recovery_gain=realized_capital(capital_recovery,recovery_cost)[1]
        payables['upper']=(1-c.get('receipt',.8))*up['declared'];est['upper']['cash']+=payables['upper']
        payables['pv']=(1-c.get('receipt',.8))*pv['declared'];pvbudget['cash']+=payables['pv']
        decl=(1-currentpct)*up['declared']+(1-pv_pct)*pv['declared']
        receive=newreceivable+c.get('receipt',.8)*decl;newreceivable=(1-c.get('receipt',.8))*decl
        support=(1-currentpct)*up['support']+(1-pv_pct)*pv['support']
        ar=ta['rows'][t] if ta else dict(capital_return=0,capital_reduction_fraction=0,dividend=0,support=0,profit=0,depreciation=0,capital_cash=0,general_debt=0,project_debt=0,cash=0)
        target_investment_basis+=ar['support']
        target_cost_removed=target_investment_basis*ar['capital_reduction_fraction']
        target_investment_basis-=target_cost_removed
        target_capital_gain=realized_capital(ar['capital_return'],target_cost_removed)[1]
        payment=ACQ['price'] if ta and t==0 else 0;acqloan=.8*payment
        # Subsidiary economic remittance budget, no fictitious aggregated statutory reserve.
        subprofit=sp-nciprofit
        base_declaration=max(0,c.get('mature_payout',.3 if t<9 else .8)*subprofit)+(max(0,scash-2.5-nci_cash)*.2 if t>=9 else 0)
        maturebudget['profit_budget']+=subprofit
        budget_cushion=min(.15*max(0,maturebudget['profit_budget']),1.5*max(0,subprofit))
        declare=min(base_declaration,max(0,maturebudget['profit_budget']-budget_cushion-maturebudget['declared_total']))
        received=receivable+c.get('receipt',.8)*declare;receivable=(1-c.get('receipt',.8))*declare
        subsmaint=.3*mr['maintenance'];parentmaint=.7*mr['maintenance']
        extra=(2/3+CRED*c.get('old_capital_payable_scale',1.)/3) if t<3 else 0
        subflow=vat_sub+sp+(mr['da']-parent_da)-subsmaint-.6*extra+(2/3*.6 if t<3 else 0)
        sd,snet,scash=fund(scash,subflow,received+ncipaid,2.5+nci_cash,sdebt,15.)
        # If budget cannot pay, adjust declarations and cash receipts together rather than fictitious transfer.
        if sd+1e-8<received+ncipaid:raise ValueError('subsidiary remittance budget not financeable')
        sdebt+=snet;maturebudget['declared_total']+=declare;maturebudget['cash']=scash
        directprofit=pr['GS']['profit']+pr['GLB']['profit'];directflow=sum(pr[n]['economic_cash']-pr[n]['equity_call'] for n in ('GS','GLB'))
        cashinterest=max(0,pcash-.6)*.015
        statutory=pp+directprofit+declare+decl+.3+ar['dividend']+cashinterest+capital_recovery_gain+target_capital_gain
        appropr=reserve(statutory,retained,stat,c.get('parent_registered',S));stat+=appropr
        legal=max(0,retained+statutory-appropr-PERP*.025)
        common=pp+subprofit+directprofit+upper_tax_saving+sum(pr[n]['profit'] for n in ('RM','BDuo','PV_completion'))+.89*(pr['BDa']['profit']+pr['GX']['profit'])+.3-PERP*.025+ar['profit']
        common-=pv_pct*pr['PV_completion']['profit']
        common-=currentpct*(upper_tax_saving+sum(pr[n]['profit'] for n in ('RM','BDuo'))+.89*(pr['BDa']['profit']+pr['GX']['profit']))
        intended=min(.205*S if t==0 else max(0,rows[-1]['common_profit']*.45)+(max(0,pcash-.6)*.2 if t>=15 and pdebt<5 else 0),legal)
        cashinterest=max(0,pcash-.6)*.015
        flow=vat_parent+pp+parent_da-parentmaint-.4*extra-(2/3*.6 if t<3 else 0)+received+receive+directflow+.3-PERP*.025-support+ar['dividend']-ar['support']-payment+acqloan+cashinterest+capital_recovery+ar['capital_return']
        paid,pnet,pcash=fund(pcash,flow,intended,.6,pdebt,c.get('parent_credit',7.))
        pdebt+=pnet+acqloan;retained+=statutory-appropr-PERP*.025-paid
        assert min(pdebt,sdebt,pcash,scash)>=-1e-8
        rows.append(dict(year=y,direct_tax_saving=direct_tax_saving,direct_unlevered_saving=direct_unlevered_saving,upper_tax_saving=upper_tax_saving,upper_unlevered_saving=upper_unlevered_saving,mature_nci_detail=ncidetail,mature_nci_profit=nciprofit,mature_nci_restricted_cash=nci_cash,vat_recovery=vat_recovery,vat_parent=vat_parent,vat_sub=vat_sub,vat_nci=vat_nci,common_profit=common,mature_profit=pp+sp,parent_cash_interest=cashinterest,mature_nci_paid=ncipaid,parent_statutory_profit=statutory,parent_registered=c.get('parent_registered',S),parent_statutory_reserve=stat,parent_appropriation=appropr,parent_retained=retained,parent_cash=pcash,intercompany_payables=copy.deepcopy(payables),parent_debt=pdebt,parent_net_borrowing=pnet,parent_flow=flow,subsidiary_capital_recovery=capital_recovery,subsidiary_recovered_cost=recovery_cost,subsidiary_capital_recovery_gain=capital_recovery_gain,target_investment_basis=target_investment_basis,target_cost_removed=target_cost_removed,target_capital_gain=target_capital_gain,capital_recovery_by_entity=recovery,capital_recovery_registered=copy.deepcopy(capital_recovery_registered),capital_recovery_basis=copy.deepcopy(capital_recovery_basis),parent_distribution=paid,dps=paid/S,mature_sub_debt=sdebt,mature_sub_cash=scash,mature_sub_declared=declare,mature_sub_received=received,mature_budget_profit=maturebudget['profit_budget'],new_sub_declared=decl,new_sub_received=receive,new_sub_support=support,old_receivable=receivable,upper=dict(up,cash=est['upper']['cash']),changdu=dict(cd,cash=est['changdu']['cash']),guxue=dict(gx,cash=est['guxue']['cash']),pv_budget=dict(pv,cash=pvbudget['cash']),upper_registered=registered,upper_external_ownership=currentpct,upper_raise_cash=raise_cash,pv_external_share=pv_pct,pv_external_recovery=pv_external_recovery,external_capital=pv_pct*pv['support']+.11*(cd['support']+gx['support'])+currentpct*up['support']+raise_cash,external_dividend=pv_external_recovery+pv_pct*(oldpayables['pv']+c.get('receipt',.8)*pv['declared'])+.11*(oldpayables['changdu']+oldpayables['guxue']+c.get('receipt',.8)*(cd['declared']+gx['declared']))+currentpct*(oldpayables['upper']+c.get('receipt',.8)*up['declared']),project_debt=sum(x['debt'] for x in pr.values()),project_cash=sum(s['cash'] for s in est.values())+pvbudget['cash'],target=ar,acquisition_payment=payment,acquisition_loan=acqloan,engineering_cash=sum(x['engineering'] for x in pr.values()),project_profit=upper_tax_saving+sum(x['profit'] for x in pr.values()),project_da=sum(x['da'] for x in pr.values()),project_capital_cash=sum(x['engineering']+x['capitalized_interest']+x['maintenance'] for x in pr.values()),legacy_capital_cash=extra,mature=mr,mature_tax_shield=direct_tax_saving-direct_unlevered_saving+max(0,mr['ebit'])*tax-(max(0,ppretax)*tax+max(0,spre)*tax)))
    # Full consolidated conservation, including target acquired cash/debt and delayed internal payments.
    priorcash=F['cash_equivalents'];priordebt=D
    for rr in rows:
        totalcash=rr['parent_cash']+rr['mature_sub_cash']+rr['project_cash']+rr['target']['cash']
        totaldebt=rr['parent_debt']+rr['mature_sub_debt']+rr['project_debt']+rr['target']['general_debt']+rr['target']['project_debt']
        opening_acq=(ta is not None and rr['year']==2027)
        predicted=priorcash+rr['vat_recovery']+rr['mature_profit']+rr['project_profit']+rr['target']['profit']+.3+rr['parent_cash_interest']-PERP*.025+rr['mature']['da']+rr['project_da']+rr['target']['depreciation']-rr['mature']['maintenance']-rr['project_capital_cash']-rr['target']['capital_cash']-rr['legacy_capital_cash']-rr['parent_distribution']-rr['mature_nci_paid']-rr['external_dividend']+totaldebt-priordebt+rr['external_capital']-rr['acquisition_payment']+(ACQ['cash']-ACQ['old_debt'] if opening_acq else 0)
        rr['consolidated_cash_check']=predicted-totalcash
        assert abs(predicted-totalcash)<1e-7,(name,rr['year'],predicted-totalcash)
        priorcash=totalcash;priordebt=totaldebt
    result=dict(name=name,params=c,projects=projects,target=ta,rows=rows,feasible=True,end=end)
    result['current']=value(result,2026,legacy);result['year5']=value(result,2031,legacy)
    result['distributions']=[round(x['dps'],4) for x in rows[:5]]
    result['peak_debt']=max(x['parent_debt']+x['mature_sub_debt']+x['project_debt']+x['target']['general_debt']+x['target']['project_debt'] for x in rows)
    return result

def value(b,asof=2026,legacy=False):
    c=b['params'];r=c['rate'];end=b['end'];rows=b['rows'];shift=asof-2026
    discount=lambda seq:sum(v/(1+r)**(y-asof) for y,v in seq if y>asof)
    maturepv=discount((x['year'],mature(c,x['year'],legacy)['fcff']) for x in rows)
    last=rows[-1]['mature'];infl=1.005**(end-2027)
    normalized=last['fcff']+(8*infl if (end-2026)%20==0 else 0)-.4*infl
    compannual=2.7*.22*.75 if end>=2035 else 0.
    tail=0 if legacy else (normalized-compannual)/(r-.005)+compannual/r
    maturepv+=tail/(1+r)**(end-asof)+discount((x['year'],x['direct_unlevered_saving']) for x in rows)
    projectpvs={n:discount((x['year'],x['fcff']) for x in p['rows'])+(0 if legacy or p['tail_enterprise']==0 else p['rows'][-1]['fcff']/r)/(1+r)**(end-asof) for n,p in b['projects'].items()}
    # Share both full engineering obligations and operating receipts, never profit-only ownership.
    projectpvs['RM']+=discount((x['year'],x['upper_unlevered_saving']) for x in rows)
    claim=.11*(projectpvs['BDa']+projectpvs['GX'])+c.get('pv_external_share',0.)*projectpvs['PV_completion']
    upperbase=projectpvs['RM']+projectpvs['BDuo']+.89*(projectpvs['BDa']+projectpvs['GX'])
    if asof>2026:
        rr=next(x for x in rows if x['year']==asof);at={n:next(x for x in p['rows'] if x['year']==asof) for n,p in b['projects'].items()}
        claim+=c.get('pv_external_share',0.)*(-at['PV_completion']['debt']+rr['pv_budget']['cash'])
        claim+=.11*(-at['BDa']['debt']-at['GX']['debt']+rr['changdu']['cash']+rr['guxue']['cash'])
        upperbase+=-at['RM']['debt']-at['BDuo']['debt']+.89*(-at['BDa']['debt']-at['GX']['debt']+rr['changdu']['cash']+rr['guxue']['cash'])+rr['upper']['cash']
    upperclaim=c.get('upper_share',0)*upperbase
    raisepv=c.get('upper_share',0) and ((1-c['upper_share'])*c.get('raise_cash',3*.35/.65)/(1+r)**(2027+c.get('raise_year',0)-asof) if asof<2027+c.get('raise_year',0) else 0.)
    comp=0. # Downstream benefit already enters mature operating revenue, cash and tax.
    legacycap=discount((y,2/3) for y in (2027,2028,2029))
    if asof==2026:debt=D;cash=F['cash_equivalents'];credit=CRED*c.get('old_capital_payable_scale',1.);nci=0.
    else:
        row=next(x for x in rows if x['year']==asof);debt=row['parent_debt']+row['mature_sub_debt']+row['project_debt'];cash=row['parent_cash']+row['mature_sub_cash']+row['project_cash'];credit=0;nci=0.
    nci=discount((x['year'],x['mature_nci_paid']-x['vat_nci']) for x in rows)
    nlast=rows[-1];g=1.005*c.get('hydro_retention',1.)-1;balance=nlast['mature_nci_restricted_cash'];annual=nlast['mature_nci_profit']
    # 50% next-year profit paid immediately; retained half released geometrically at 20%.
    rel=c.get('nci_release_rate',.2);pay=c.get('nci_payout',.5)
    nci_tail=(balance*rel/(r+rel)+annual*(1+g)/(r-g)*(pay+(1-pay)*rel/(r+rel)))
    nci+=nci_tail/(1+r)**(end-asof)
    acq=0
    if b['target']:
        t=b['target'];acq=discount((x['year'],x['fcff']) for x in t['rows'])+(0 if legacy else t['rows'][-1]['fcff']/r)/(1+r)**(end-asof)
        acq+=sum(discount((x['year'],x['fcff']) for x in p['rows'])+(0 if legacy or p['tail_enterprise']==0 else p['rows'][-1]['fcff']/r)/(1+r)**(end-asof) for p in t['projects'].values())
        if asof==2026:acq+=ACQ['cash']-.1-ACQ['old_debt']-ACQ['price']/(1+r)
        else:
            ar=next(x for x in t['rows'] if x['year']==asof);acq+=ar['cash']-.1-ar['general_debt']-ar['project_debt']
    # APV: rate denotes unlevered operating cost; finite actual cash-tax shields only.
    # Shield risky future tax capacity discounted at Ku, no perpetual leverage or new financing policy.
    tax_shield_mature=discount((x['year'],x['mature_tax_shield']) for x in rows)
    tax_shield_projects={n:discount((x['year'],x['tax_shield']) for x in p['rows']) for n,p in b['projects'].items()}
    tax_shield_projects['RM']+=discount((x['year'],x['upper_tax_saving']-x['upper_unlevered_saving']) for x in rows)
    tax_shield_target=0.
    if b['target']:
        tax_shield_target=discount((x['year'],x['tax_shield']) for x in b['target']['rows'])+sum(discount((x['year'],x['tax_shield']) for x in p['rows']) for p in b['target']['projects'].values())
    shield_claim=c.get('pv_external_share',0.)*tax_shield_projects['PV_completion']+.11*(tax_shield_projects['BDa']+tax_shield_projects['GX'])
    shield_upper=c.get('upper_share',0)*(tax_shield_projects['RM']+tax_shield_projects['BDuo']+.89*(tax_shield_projects['BDa']+tax_shield_projects['GX']))
    shield=tax_shield_mature+sum(tax_shield_projects.values())+tax_shield_target-shield_claim-shield_upper
    fiscal_pv=discount((x['year'],x['vat_recovery']-x['vat_nci']) for x in rows)
    eq=fiscal_pv+shield+maturepv+sum(projectpvs.values())-claim-upperclaim+raisepv+comp-legacycap-debt-PERP-nci-credit+cash-2.0296755+F['financial_investments']+acq
    return dict(per_share=eq/S,equity=eq,fiscal_asset_recovery_pv=fiscal_pv,tax_shield=shield,tax_shield_mature=tax_shield_mature,tax_shield_projects=tax_shield_projects,tax_shield_target=tax_shield_target,tax_shield_minority=shield_claim+shield_upper,mature_ev=maturepv,projects=projectpvs,project_sum=sum(projectpvs.values()),project_minority_claim=claim,upper_claim=upperclaim,raise_value=raisepv,compensation=comp,legacy_completion=legacycap,debt=debt,perpetual=PERP,nci=nci,nci_tail_pv=nci_tail/(1+r)**(end-asof),capital_payables=credit,cash=cash,necessary_cash=2.0296755,financial_assets=F['financial_investments'],acquisition_increment=acq,terminal_mature_pv=tail/(1+r)**(end-asof))

def tests():
    assert reserve(10,0,5,20,paid=10)==1
    assert reserve(10,-8,0,20)==.2
    assert reserve(10,-12,0,20)==0
    assert reserve(10,0,10,20)==0
    assert reserve(10,0,10,22)==1
    st=dict(cash=0.,retained=0.,reserve=0.)
    v=legal_step(st,0,0,20,old_receipt=4)
    assert v['profit']==0 and v['declared']==0 and v['cash']==4
    try:fund(1,-5,0,0,10,2)
    except ValueError:pass
    else:raise AssertionError('zero dividend gap concealed')
    assert capital_action(20,10,10,10,4,2,'reduction')==(16,8,8,8)
    assert capital_action(20,10,10,5,4,2,'reduction')==(16,8,8,4)
    assert capital_action(20,10,10,10,4,2,'issue')==(24,12,12,12)
    cash,gain=realized_capital(10,12,fee=1,ownership=.65)
    assert abs(cash-5.85)<1e-12 and abs(gain+1.95)<1e-12
    st=dict(cash=0.,retained=0.,reserve=0.)
    v=legal_step(st,gain,cash,20)
    assert v['declared']==0 and v['cash']==cash and v['retained']==gain
    assert realized_capital(10,10)==(10,0)
    q=copy.deepcopy(SC['central']);q['mature_price']=0
    assert abs(mature(q,2027)['fcff']+10.2)<1e-12
    return {'negative_ebit_no_instant_tax_refund':True,'principal_not_profit_cost_fee_minority':True,'registered_vs_paid':True,'loss_first':True,'full_reserve':True,'capital_conversion':True,'old_receivable':True,'zero_dividend_failure':True,'capital_cash_share_link':True}

def make():
    out={'unit':'CNY billion','cutoff':'2026-10-26T14:00:00+08:00','tests':tests(),'cases':{}}
    specs=[(n,n,{}) for n in ('core_low','central','core_high','cyclical','structural','upside','engineering_low','engineering_high')]
    specs += [('no_acquisition','central',{'acquire':False}),('raise35_par','central',{'upper_share':.35,'raise_cash':3*.35/.65}),('raise35_premium','central',{'upper_share':.35,'raise_cash':3.0}),('remit_slow','central',{'receipt':.5,'new_payout':.6,'mature_payout':.2,'entity_opening_loss':-.5}),('remit_fast','central',{'receipt':1.,'new_payout':1.,'mature_payout':.5}),('tariff_minus5','central',{'mature_price':.95}),('delay2','central',{'first':[x+2 for x in SC['central']['first']],'acq_delay':2}),('cost_plus10','central',{'cost':1.1,'parent_credit':9.}),('target_grant_70','central',{'target_grant':7.}),('target_tariff_plus40','central',{'target_tariff':1.4}),('sediment_loss','central',{'hydro_retention':.998}),('capital_recovery_delay10','central',{'capital_return_delay':10}),('parent_old_registration','central',{'parent_registered':18.}),('parent_reserve_zero','central',{'parent_reserve':0.}),('parent_reserve_all_stat','central',{'parent_reserve':5.39638671312}),('vat_none','central',{'vat_scale':0}),('vat_slow10','central',{'vat_years':10}),('vat_nci30','central',{'vat_nci':.3}),('target_plan_delay1','central',{'acq_delay':1}),('net_capex_minus8','central',{'cost':.92}),('holiday_all_conditional','central',{'new_project_holiday':True}),('maintenance_equal_DA_credit9','central',{'maintenance':7.5,'parent_credit':9.}),('ku_large_peer','central',{'rate':.0181+(.3107+.4923+.3616)/3*.0657}),('ku425','central',{'rate':.0425}),('ku6','central',{'rate':.06}),('nci_fast_release','central',{'nci_payout':.8,'nci_release_rate':.5,'nci_release_start':2027}),('nci_slow_release','central',{'nci_payout':.3,'nci_release_rate':.1,'nci_release_start':2041}),('old_payables_not_capital','central',{'old_capital_payable_scale':0.}),('pv_nci20','central',{'pv_external_share':.2}),('nci_cash_low','central',{'nci_cash_multiplier':.8,'nci_opening_cash':0.}),('nci_cash_high','central',{'nci_cash_multiplier':1.2,'nci_opening_cash':1.15})]
    for label,n,ov in specs:
        try:out['cases'][label]=run(n,ov)
        except ValueError as e:out['cases'][label]={'feasible':False,'reason':str(e),'params':dict(SC[n],**ov)}
    out['value_range']={k:round(out['cases'][n]['current']['per_share'],2) for k,n in [('low','core_low'),('high','core_high')]};out['value_range']['currency']='CNY'
    out['terminal_base_rate_range']={}
    for tag,rate in [('low',.055),('high',.045)]:
        bb=copy.deepcopy(out['cases']['central']);bb['params']['rate']=rate;out['terminal_base_rate_range'][tag]=value(bb,2031)
    out['return_model']=dict(schema_version=1,method='annual_common_equity_irr_v1',currency='CNY',model_as_of=out['cutoff'],base_case_distributions_per_share=[x['dps'] for x in out['cases']['central']['rows'][:5]],base_case_terminal_equity_value_range_per_share={'year_5':{k:out['terminal_base_rate_range'][k]['per_share'] for k in ('low','high')}})
    out['parameters']=copy.deepcopy(A)
    out['documentation']=DOCUMENTATION
    return out

DOCUMENTATION={'2026-Q3-entity-sources.md': '# 主体、资本和证据边界（金额：亿元）\n\n资料截至2026-10-26；本表把财报事实、登记报道和研究预算分开。未知单体资料不以工程投资、母公司投资成本或合并余额替代。\n\n|对象|真实法律路径/法域|注册资本|实缴|法定/任意公积、亏损|原证/处理|\n|---|---|---:|---|---|---|\n|华能澜沧江水电股份有限公司|上市付款母；中国|186.31094257（发行后章程变更及已发行股本；本次未获工商换照原件）|现已发行股本186.31094257；不是全部权益|Q3母盈余合计53.9638671312，未分配239.0057410048；母法定/任意未单独拆分|S1母表；S2合并法定59.9751930914、任意0.16、其他0.0353267441，不能替代母表。基准母法定53.7685403871为上限扣集团非一般储备的预算，不称事实；另将母法定从0到全额53.963867重跑，全期D不变，法定容量不binding|\n|华能澜沧江上游水电有限公司|上市母100%；中国；35%尚未交割|30|未取得本次单体实缴表|H1净资产29.064947、净利0.036520；单体留存/法定/任意未披露|S2第15、172页；RM实施主体S26、股东会S30；RM和BDuo共同归上游工程预算，不能各建资本池。起始累计亏损预算1.5、储备0，不宣称由净资产减资本精确导出；额外5亿元各主体亏损为敏感|\n|华能澜沧江（昌都）水电有限公司|上游控制，上市体系间接89%；中国|48|未知；认缴不加现金|2026新设，初始留存、公积预算0，另测亏损|S2第171及184页间接89%；10月21采购HNFZ2026-10-2-01190明确BDa。工程管理归属原公告转载，可支持预算映射，未取得全部资产划转清单|\n|华能澜沧江古学（芒康）水电有限公司|上游89%、宁德时代11%；中国|56|认缴49.84/6.16，不等于已实缴|新设公司初始留存、公积预算0|S25国家企业信用信息公示系统调查报道；GX归古学为名称与项目开发映射，出资进度仍属预算；11%同时承担现金与取得收益|\n|华能澜沧江新能源有限公司|上市母100%；中国|80.4587|未知|H1净资产134.712361、净利1.634340；单体储备未得|S2第15、172页；PV_completion同时包括四川及其他新能源，严格仅为工程组合。以85%早期累计盈利、后期最多1.5年利润缓冲建立有限经济上划预算，不建立该组合“法定公积”|\n|华能四川能源开发有限公司|上市母100%；中国|14.698|未知|H1净资产92.229656、净利5.254948；单体储备未得|S2第15、子公司表；与新能源/龙开口/国际共同约束既有运营上划预算，不能合并亏损互抵|\n|华能龙开口水电有限公司|上市母100%；中国|26.7213|未知|H1净资产35.430761、净利1.508410|S2第15；不把注册资本等同水电站资产成本|\n|华能澜沧江国际能源有限公司及境外子公司|国内国际公司—柬埔寨、缅甸经营主体|国内5.6178|未知|H1净资产54.841174、净利5.165714；境外留存未知|S2第15及税注。只设经济可汇回预算，考虑特许权有限及到账时差；不对境外套中国10%/50%。全期上划慢/快情景是付款能力预算而非当地法务意见|\n|HNYL公司（公开匿名名称）|拟由华能集团100%转至上市母；中国|97.924165（评估万元四舍五入）|97.9241652163（审计），本期资本公积转实收12.6，不是新增现金|母未分配-15.6786683744；母盈余空栏/0|S22母表及实收附注；S23 **PDF第9页/印刷第7页**分别列明注册及分公司。不得猜完整公司名。模型注册取评估97.924165、母留存取审计，资本金支持不自动增加注册|\n|JXF/X水电、QSF/W2风电|HNYL分公司，中国|不适用|不适用|利润直接进HNYL，不造法人储备|S23印刷7—10页；X后续工程支出与运营收益一致在100%目标体系计入|\n|ND/N风电|HNYL100%子公司，中国|1|评估实缴0.5179；S22印刷64页母公司期末长期股权投资0.5179；印刷58页企业概况表另列投资额0.1579，不以该概况表替代期末母成本|未取得单体留存，预算0、公积0|S23印刷48页注册/实缴专表；注册1决定0.5上限，不使用工程成本5.33亿元。实际宣派才进目标母利润，现金80%当期到账|\n|QS光伏|目标法律86%，按实缴现金分配；中国|3.31|目标2.32、YT0|单体留存未知|S23印刷48—49页：章程按实缴，外方拟退出待批，经济现金100%预算不称法律已100%。若条款变化须重跑目标经济归属|\n\n## 35%方案的真实事实与条件预算\n\n2026-031和6月股东会资料明确4月24日在上海联合产权交易所挂牌、拟引入35%，8月资金报告仍称进行中。可读取材料未披露截止日前成交价、溢价、验资或注册变更结果。基准仍100%，现金0。\n\n条件分支假设2027年一次交割，原注册30亿元不减，新增名义注册=30×35/65=16.153846亿元，总注册46.153846亿元。平价示例实收16.153846，溢价0；另一个示例实收30亿元、资本溢价13.846154亿元，新增注册仍16.153846。二者都是条件估计，不是挂牌底价或已成交事实。股权、实际到账、后续资本分担和分红从同一年联动，溢价不进入法定利润；仅发生在上游，不稀释上市186.31亿股。募集资金转为借款的原文保留，其未实际放款额不凭空加内部利息或债权价值。\n\n## 来源入口\n\nS1 https://static.cninfo.com.cn/finalpage/2026-10-26/1225621880.PDF\n\nS2 https://static.cninfo.com.cn/finalpage/2026-08-26/1225504979.PDF\n\nS22 https://file.finance.sina.com.cn/211.154.219.97:9494/MRGG/CNSESH_STOCK/2026/2026-10/2026-10-26/12658801.PDF\n\nS23 https://file.finance.sina.com.cn/211.154.219.97:9494/MRGG/CNSESH_STOCK/2026/2026-10/2026-10-26/12658811.PDF\n\nS25 https://www.jjckb.cn/20260928/b8eb31546cfa4744805c3d6c107d5550/c.html\n\nS26 https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=12322932&stockid=600025\n\nS30 https://static.cninfo.com.cn/finalpage/2026-06-03/1225346259.PDF\n\nBDa采购原公告转载 https://www.bidcenter.com.cn/zhaobiao/zbkeyw-30619-540000-1.html （采购号HNFZ2026-10-2-01190，2026-10-21；非交易所资产划转证明）\n\nRM/BDuo建管局采购公告索引 https://www.bidcenter.com.cn/newssearchyz-362738094-4.html （招标号HNZB2026-06-3-034；与发行人RM实施主体原文交叉，不以招标索引替代注册资料）\n\n境内法定提取规则 https://www.samr.gov.cn/xyjgs/flfg/art/2024/art_d4e84936a8a744f8928ac7aec7594345.html 第210条；先补亏，注册50%门槛，实缴与注册分开。\n\n上市母注册补充：发行人2025-076章程变更公告明确由180亿元改为186.31094257亿元，2026年度股东会资料继续审议相关条款；本次未取得工商换照原件，另以旧注册180亿元重跑完整分配路径，普通股D不变。原文分发：https://paper.cnstock.com/html/2025-10/31/content_2139814.htm 。股本、认缴变更与登记完成不混同。\n\n\n### 本轮本金回收成本原证与预算\nH1母长期股权投资明细印刷222页：新能源10.01558753253、四川5.81029529217十亿元是母投资账面成本，不是注册或实缴。注册分别8.04587/1.4698十亿元；组合未来支持/部分减资按注册权重配置是研究预算，不是披露项目归属。HNYL母投资成本起点为收购价8.7012044十亿元，未来实际支持增加；按注销比例结转成本，损失进入母法定利润。ND评估印刷48页实缴0.05179十亿元，与注册0.1不同；清算接收方税为保守预测。实际法域、原证URL见上表。\n\n## 既有少数及嵌套路径（本轮直接核H1原文）\n\nH1印刷172—179页集团构成及181—185页非全资附注，不以合并控制替代经济持股：\n\n|主体|归属|本期已披露少数损益（亿元）|资金与期限预算|\n|---|---|---:|---|\n|云南联合电力开发有限公司|体系间接51%；该体系瑞丽江一级水电80%，存在第二层少数|1.6384878685|采用原表最终少数损益，不再乘49%；境外经营逐步退出，积累现金随后回收|\n|桑河二级水电有限公司|间接51%；柬埔寨|1.1272562842|境外适用法域与许可仍为条件，不套境内公积规则|\n|华能龙开口水电有限公司|上市母95%|0.0754205089|国内持续经营现金权利不按30年终止|\n|云南澜沧江清洁能源合伙企业（有限合伙）|新能源33.20%，以表决机制控制；外部66.80%|0.5352874471|不是全资，保留最终少数经济索取；不向合伙体机械套公司法法定公积|\n|四川华能泸定水电有限公司|外部20%|0.1366468996|由四川体系持有，国内持续经营预算|\n\n上述五项H1少数利润合计3.513099亿元，宣派合计1.516181亿元。年度正常化总少数经济现金8亿元，其中上述各项按两倍H1构成约束、剩余0.973802亿元明确为其他既有少数预算。这里的利润与现金等量是维持必要资本后的估计，不是已审计FCFE。已有少数期初可归属流动现金4亿元是预算：五项期末流动资产按所列经济份额约11.5亿元仅给量级参照，不能证明全公司少数现金上界；当前资产不自动等于现金。0—11.5亿元与现金权益80%—120%、快慢支付完整重算。所有保留款只归真实少数，不计为母公司可用现金。\n\n华能澜沧江（普洱）新能源有限公司97.99%在H1印刷174页列明；未取得完整基地法人资产映射，不能仅凭地址把189万千瓦全分配给该公司。未来250万千瓦完工组合100%经济权益为条件预算，额外20%外部参与分支同步分担投入、利润、债务及本金，不与既有合伙少数重复。\n\n华能四川能源开发有限公司H1印刷178—179页列直接100%，注册146,980万元；该母层100%不意味着其下泸定等项目全资。新能源与四川部分减资的投资成本源于H1母表印刷222页，仍需审批及债权保护。PV本金回收约束现绑定该项目债务，不再绑定其他成熟子公司的全部合并债务。\n\n实缴与注册在减资函数按各自注销比例下降；部分实缴公司不能按注销名义股数直接减掉同额实缴。ND股权全注销时，模型用已知/后续支持约束实缴预算，不以工程额替代注册。\n\nND成本最终核验：S22 PDF65/印刷64页，母长期股权投资明细的2025年末及2026年5月31日ND均为51,790,000元；生产起始投资成本0.05179十亿元据此成立，不是仅因S23实缴相等而互换概念。S22印刷58页概况表15,790,000元与当期母明细不同；采用明确时点及原表用途的母明细。\n\n资料边界补充：BDa采购仅公开索引核得主体和编号，完整转载页有人机验证；GX56亿元登记为报道引国家公示系统，89%/11%股权是报道引天眼查，并非直接取得工商股权原表。成熟经营负EBIT不生成即时退税；现有39情景数值不因此改变。\n', '2026-Q3-economic-sanity-review.md': '# 华能水电：普通股现金归属与估值分歧\n\n金额为亿元，除每股；资料截止2026-10-26。本说明与完整报告和39条模型路径一起阅读。\n\n## 核心判断\n\n持续梯级经营有经济价值，但资本成本、未来更新和新增工程资本效率决定其范围。核心4.23—11.45元、中心7.4659元；辅助正常利润资本化3.00元明显较低，因其把折旧近似为持续更新，不以平均掩盖该分歧。维护提高至75亿元、母融资额度提高至90亿元的完整条件值3.86元。\n\nKu5%及4.5%—5.5%为采用的经营风险范围；大型水电可比机制值4.36%是有力替代，完整结果10.90元。固定WACC不能同时解释前期高债务及远期全部去杠杆，所以使用全额无杠杆FCFF和有限现金税盾。不能用股价或卖方值倒推资本成本，也不把现金场景里的施工、枯水风险再加为特定溢价。\n\n## 注册、股权价和企业价值不是一回事\n\nHNYL注册97.924165亿元；审计实收97.9241652163亿元；其中12.6亿元为资本公积转股，不是新现金。拟议100%股权价87.012044亿元。旧模型的77.8620亿元是旧税、工期及资本成本假设下，将其未来经营流机械折回2026年5月31日的企业价值，既不是注册也不是股权。\n\n|一致5月31日桥|亿元|\n|---|---:|\n|对价/评估100%股权|87.0120|\n|融资债|80.9362|\n|现金|0.4649|\n|必要现金预算|1.0000|\n|对价隐含经营EV，未分离所有非经营项|168.4833|\n|当前模型年底经营APV，含已识别税信用|117.4614|\n|同一未来流机械折回5月31日|114.1655|\n|同净债/必要现金下股权|32.6942|\n|对价减模型权益|54.3178|\n\n本模型没有六月至十二月真实施工与经营结算，日历折回不能冒充完整交割桥。以前77.86亿元到当前114.17亿元的差异来自资本成本、有限融资税盾、项目计划、9%税惠与信用回收等方法/经营变化，不是注册资本核实本身创造价值。上轮APV候选约113.84亿元与本轮114.17亿元的差异较小，亦不能掩盖少数与税链上的原错误。\n\n分歧的经济原因依次是：X186.17亿元总预算、既有CIP39.19亿元后的高剩余工程负担；27亿度及0.35元含税价只属采用的经营预测；工程财政资金有来源文字却无完整金额；真实含税净概算、期后付款及资本化利息拆分不充分；卖方与本模型的资本成本、税惠和长寿命更新路径未能逐年对齐。当前X经营现值94.80亿元、未来建设114.47亿元、有限项目税盾5.23亿元；同法人合税收益另归HNYL整体。低净值是条件判断，不是已发生减值。\n\n较低Ku4.36%/4.25%将目标权益提高到62.90/69.01亿元，差额降至24.12/18.01亿元。全部目标电价高40%、一次净补助70亿元、净工程成本低8%的集团条件值分别8.13/7.80/8.04元。它们表示未知的量级，不是已获合同或补助；没有把这些有利条件倒塞进核心去贴近交易价。\n\n## 真实所有权与合法资金的边界\n\nHNYL是匿名拟购全资目标，不能称云南联合电力；QS法定86%而现章程按实缴给目标100%经济分红，尚未完成的14%退出不当事实。现有云南联合、桑河、龙开口、清洁能源合伙、泸定少数来自H1附注；嵌套最终少数损益直接使用，不再重复乘外部比例。受托控制33.2%合伙份额不变成100%经济所有。\n\n现金归属预算采用正常少数8亿元，其中逐实体构成由H1披露约束；必要资本后现金近似利润仍是估计，0.8—1.2倍及期初归属现金0—11.5亿元完整重算，值约7.58—7.34元（低现金索取对应较高普通股值）。少数未付现金在资金账中隔离；国内持续权利不30年归零，境外退出后积累本金有释放路径。快/慢释放各7.38/7.58元。境外实际许可与当地资本维护约束未假称全部完成，条件经济范围优先于虚构法定池。\n\n新能源完工组合是经营预算，缺完整项目法人表；已知普洱97.99%不能凭名称映射所有基地，核心全额经济权益为条件，20%外部参与的完整路径为7.41元。真实新能源/四川母层均100%，不意味着其所有下属项目全资。部分资本回收须批准、债权保护、实际现金及对应成本注销；不拿其他成熟子公司的全部债务做无限冻结门槛。基准PV金融本金2058起回收，而不是等待2078其他成熟债务全部清偿；两者当前FCFF和前五年分配不变，后期付款与母法定损益真实不同。\n\n## 税与建设现金\n\n目标9%至2027；之后15%至2030、25%为预算。X/W2为同一HNYL法人分公司，适用普通税率与当期税基合算；GS/GLB归本部、RM/BDuo归上游，各自合算，不跨法人抵亏。ND独立税惠依据首笔生产经营收入年度，计划投产不是完成证据。JD/QJ/QS/SN的已披露优惠可能降低既有业务实际税，尚缺详细构成，未写成精确税率事实。\n\n同年可施工、借款、资本化与费用化利息并发电。半年的运行预算只使用半额原税基年度折旧，期末补足剩余半额；原成本不因此多扣。已有VAT回收只加现金不加利润；未来概算含税净税不明时以完整成本替代路径表示，而不把全部成本机械退13%。财政补助与已付税信用不同。\n\n## 末端与投资判断\n\n显式期末2101之后的净经营与少数索取尾部，折现到当前约130.59亿元，占中心普通股价值约9.4%；其中成熟经营尾部占其自身EV约3.3%。改用2086/2126/2151显式末年，中心约7.445/7.462/7.465元；数值收敛不证明许可永续。\n\n母后期多余现金按20%释放，法定利润、注册及投资成本仍贯通；ND退出接收方保守税为预测，不是已确定税单。所有39路径逐年保留资金、税、利润、权益和股份字段，其中38可行；结构性不利首年零股利仍需约90.88亿元一般资金而额度50亿元，明确不可行。价值可以有用但仍是附明确资本、税务、归属和回收条件的范围，不能由内部算术闭合宣称所有外部条件已经证实。\n\n资料边界补充：BDa采购仅公开索引核得主体和编号，完整转载页有人机验证；GX56亿元登记为报道引国家公示系统，89%/11%股权是报道引天眼查，并非直接取得工商股权原表。成熟经营负EBIT不生成即时退税；现有39情景数值不因此改变。\n'}

def canonical_bytes(o):
 return json.dumps(o,ensure_ascii=False,separators=(',',':')).encode('utf-8')

def pack_output(o):
 def summary(x):
  if isinstance(x,dict):return {k:summary(v) for k,v in x.items() if k not in ('rows','tail_rows')}
  if isinstance(x,list):return [summary(v) for v in x]
  return x
 raw=canonical_bytes(o);p=summary(o)
 p['_complete_output']={'encoding':'gzip-mtime0-base64-json-utf8','expanded_bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'schema':'Complete object: all 39 scenarios and all annual rows, project/entity financing, APV bridges, embedded literal parameters and source/economic notes. Readable outer fields omit annual rows; complete detail is losslessly encoded. Units CNY billion, billion shares and per-share CNY where indicated. Numerical terminal horizon is not forecast evidence.','expand_command':'python 2026-Q3.py --expand 2026-Q3-output.json expanded.json','data':base64.b64encode(gzip.compress(raw,compresslevel=9,mtime=0)).decode('ascii')}
 assert expand_output(p)==o
 return p

def expand_output(o):
 a=o['_complete_output'];raw=gzip.decompress(base64.b64decode(a['data']))
 assert len(raw)==a['expanded_bytes'] and hashlib.sha256(raw).hexdigest()==a['sha256']
 return json.loads(raw)

if __name__=='__main__':
 if len(sys.argv)==4 and sys.argv[1]=='--expand':
  src=json.loads(Path(sys.argv[2]).read_text());Path(sys.argv[3]).write_bytes(canonical_bytes(expand_output(src)))
 else:
  o=make();Path(__file__).with_name('2026-Q3-output.json').write_bytes(canonical_bytes(pack_output(o)));print(o['value_range'])
