#!/usr/bin/env python3
"""002372 ordinary-equity cash valuation. Standalone stdlib; CNY bn except per share.
No live price, no external files as inputs. Rounded display is not calculation precision.
"""
import json, math, copy, pathlib, sys
SHARES=1.571867988
NAMES=['临海新材','上海新材','天津新材','重庆新材']
WEIGHTS=[.46,.19,.23,.12]
CAP=[.32,.10,.08,.06]  # Registered capital disclosed; reserve cap uses REGISTERED capital (Company Law art.210).
# Fully paid assumed for cash-capital budget only, not a separate paid-in disclosure; no extra funding.
BUDGET=dict(revenue0=4.95,revenue1=4.90,margin1=.147,parent_cost=.12,
 growth=[.02,.03,.03,.025],margins=[.148,.149,.15,.15],terminal_growth=.015,
 terminal_margin=.14,nwc_ratio=.35/4.9,fixed_growth_ratio=.6,maintenance_ratio=.2/4.9,
 commitments=[.10,.05],settlement=[.30,.20],yield_rate=.012,sub_tax=.15,
 parent_tax=.25,payout=.80,special=.20,upstream_lag=0,opening_reserve_full=True,
 jv_book=.36784975989,jv_cash=.30,jv_year=5,other_book=.555418655,
 other_cash=.35,other_year=8,receivable=.03,receivable_year=6,
 parent_cash=1.45,parent_retained=.75,core_cash=[.25,.10,.12,.08],
 parent_floor=.25,subs_floor=.30,margin_shift=0.0,receivable_shock=0.0,capital_release_year=12,minimum_parent_capital=.50)

def initial(b):
    p=dict(name='上市母公司',cash=b['parent_cash'],re=b['parent_retained'],reserve=.796038994,capital=1.592037988,
      fixed=.15,nwc=.10,debt=0.,losses=[],div_receivable=0.,loan_receivable=0.)
    s=[]
    for i in range(4):
        s.append(dict(name=NAMES[i],cash=b['core_cash'][i],re=[.45,.18,.20,.10][i],
          reserve=CAP[i]*.5 if b['opening_reserve_full'] else 0.,capital=CAP[i],
          fixed=[.90,.28,.32,.20][i],nwc=[.16,.07,.08,.04][i],debt=0.,losses=[],div_payable=0.))
    return p,s

def tax(e,taxable,rate,year):
    # Expiring tax losses never become cash tax credits; dividends are exempt.
    e['losses']=[list(x) for x in e['losses'] if x[0]>=year and x[1]>1e-12]
    if taxable<0:
        e['losses'].append([year+5,-taxable]);return 0.
    residual=taxable
    for lot in e['losses']:
        used=min(lot[1],residual);lot[1]-=used;residual-=used
    return max(0.,residual)*rate

def accrue_legal(e,net_profit):
    before=e['re'];e['re']+=net_profit
    # First absorb losses, then reserve 10% of remaining current profit, capped at 50% REGISTERED capital.
    eligible=max(0.,net_profit-max(0.,-before))
    reserve=min(.1*eligible,max(0.,.5*e['capital']-e['reserve']))
    e['reserve']+=reserve;e['re']-=reserve
    return reserve

def payment(e,wanted,floor):
    paid=max(0.,min(wanted,e['re'],e['cash']-floor))
    e['cash']-=paid;e['re']-=paid
    return paid

def financing(e,floor,limit):
    # External, finite facilities: no shareholder issuance and no internal-interest tax shields.
    draw=max(0.,floor-e['cash'])
    if draw>0:
        if e['debt']+draw>limit+1e-9:raise ValueError('finite funding exceeded '+e['name'])
        e['cash']+=draw;e['debt']+=draw
    repay=min(e['debt'],max(0.,e['cash']-floor))
    e['cash']-=repay;e['debt']-=repay
    return draw-repay

def capital_payment(e,floor,minimum):
    # Paid-in assumed equal to registered: actual cash return reduces both and outstanding shares.
    if e['re']< -1e-12 or e['debt']>0:return 0.
    paid=min(max(0.,e['cash']-floor),max(0.,e['capital']-minimum))
    e['cash']-=paid;e['capital']-=paid
    return paid

def collect_old_dividend(e):
    collected=e['div_receivable'];e['cash']+=collected;e['div_receivable']=0.
    return collected  # Never modifies legal earnings or recognises new income.

def path(b,years=240):
    p,subs=initial(b);out=[];rev=b['revenue0'];prevrev=rev;consolidated_re=2.32064890364
    for y in range(1,years+1):
        if y==1: rev=b['revenue1'];margin=b['margin1']
        elif y<=5:rev*=1+b['growth'][y-2];margin=b['margins'][y-2]
        elif y<=10:
            rev*=1+(b['growth'][-1]+(b['terminal_growth']-b['growth'][-1])*(y-5)/5)
            margin=b['margins'][-1]+(b['terminal_margin']-b['margins'][-1])*(y-5)/5
        else:rev*=1+b['terminal_growth'];margin=b['terminal_margin']
        margin+=b['margin_shift'];scale=rev/4.9
        opening_cash=p['cash']+sum(e['cash'] for e in subs)
        opening_debt=p['debt']+sum(e['debt'] for e in subs)
        settlement=b['settlement'][y-1] if y<=len(b['settlement']) else 0.
        p['cash']-=settlement
        parent_interest=p['cash']*b['yield_rate']-p['debt']*.045
        parent_op=-b['parent_cost']*scale
        # Small subsidiary turnaround/carry costs included in parent cost budget; no pooled dividends claimed.
        parent_tax=tax(p,parent_op+parent_interest,b['parent_tax'],y)
        parent_np=parent_op+parent_interest-parent_tax
        p['cash']+=parent_np
        parent_old_received=collect_old_dividend(p)
        group_np=parent_np;group_cash=parent_np;gross_upstream=0.;cash_upstream=0.;subrows=[];netfund=0.;allcapex=0.;allwc=0.;reserves=0.
        total_np_target=rev*margin
        for i,e in enumerate(subs):
            w=WEIGHTS[i];start=e.copy();startcash=e['cash'];oldpaid=e['div_payable'];e['cash']-=oldpaid;e['div_payable']=0.
            e['cash']+=settlement*w
            # Four disclosed profitable wholly owned production entities; net operating profit budget.
            op=total_np_target*w/(1-b['sub_tax'])
            interest=(e['cash'])*b['yield_rate']-e['debt']*.045
            cash_tax=tax(e,op+interest,b['sub_tax'],y);np=op+interest-cash_tax
            reserve=accrue_legal(e,np);reserves+=reserve
            da=b['maintenance_ratio']*rev*w
            committed=(b['commitments'][y-1] if y<=len(b['commitments']) else 0)*w
            growth=max(0.,rev-prevrev)*b['fixed_growth_ratio']*w
            capex=da+growth+committed;e['fixed']+=capex-da
            target_nwc=rev*b['nwc_ratio']*w
            if b['receivable_shock'] and y<=2:target_nwc+=b['receivable_shock']*w
            wc=target_nwc-e['nwc'];e['nwc']=target_nwc
            fcf=np+da-capex-wc;e['cash']+=fcf
            floor=b['subs_floor']*scale*w
            fund=financing(e,floor,.20*w);netfund+=fund
            # Declared dividends immediately consume legal pool. Lag stores payable/receivable, never a second profit.
            declared=max(0.,min(e['re'],e['cash']-floor-e['div_payable']))
            e['re']-=declared
            if b['upstream_lag']:
                e['div_payable']=declared;p['div_receivable']+=declared;received=0.
            else:e['cash']-=declared;p['cash']+=declared;received=declared
            gross_upstream+=declared;cash_upstream+=received
            group_np+=np;group_cash+=fcf;allcapex+=capex;allwc+=wc
            assert abs(e['cash']-(startcash-oldpaid+settlement*w+fcf+fund-received))<1e-7
            assert e['cash']>=-1e-9 and e['re']>=-1e-9 and e['reserve']<=.5*e['capital']+1e-9
            subrows.append(dict(name=e['name'],opening_cash=startcash,operating_pretax=op,interest=interest,tax=cash_tax,np=np,
              reserve_add=reserve,legal_retained=e['re'],reserve=e['reserve'],paid_capital=e['capital'],cash=e['cash'],debt=e['debt'],
              depreciation=da,capex=capex,nwc=e['nwc'],delta_nwc=wc,fcf=fcf,settlement=settlement*w,declared=declared,
              paid=received+oldpaid,payable=e['div_payable'],net_borrowing=fund,fixed=e['fixed']))
        # Parent recognizes declaration, not collection, as new exempt investment income.
        parent_np+=gross_upstream
        nonop_cash=-.00304348433 if y==1 else 0.;nonop_profit=0.;asset_recovery={}
        for label,book,cash,when in [('jointventure',b['jv_book'],b['jv_cash'],b['jv_year']),('other_equity',b['other_book'],b['other_cash'],b['other_year'])]:
            if y==when:
                gain=cash-book;extra_tax=tax(p,max(0.,gain),b['parent_tax'],y) if gain>0 else 0.
                # Asset disposal losses don't create immediate tax refunds; no future credit assumed absent substantiation.
                nonop_cash+=cash-extra_tax;nonop_profit+=gain-extra_tax;asset_recovery[label]=dict(book=book,cash=cash,gain=gain,tax=extra_tax)
        if y==b['receivable_year']:
            nonop_cash+=b['receivable'];asset_recovery['old_receivable']=dict(cash=b['receivable'],profit=0.)
        p['cash']+=nonop_cash;parent_np+=nonop_profit;pres=accrue_legal(p,parent_np)
        consolidated_re+=group_np+nonop_profit-reserves-pres
        pfloor=b['parent_floor']*scale
        pfund=financing(p,pfloor,.30);netfund+=pfund
        cash_capacity=max(0.,p['cash']-pfloor)
        ordinary_target=b['payout']*max(0.,group_np)
        if y<=5:
            ordinary=payment(p,min(ordinary_target,max(0.,consolidated_re)),pfloor);consolidated_re-=ordinary
            extra=payment(p,min(b['special']*max(0.,p['cash']-pfloor),max(0.,consolidated_re)),pfloor);consolidated_re-=extra
        else:
            ordinary=payment(p,min(cash_capacity,max(0.,consolidated_re)),pfloor);extra=0.;consolidated_re-=ordinary
        capital_return=0.
        if y>=b['capital_release_year'] and p['re']>=-1e-12 and p['debt']==0:
            capital_return=capital_payment(p,pfloor,b['minimum_parent_capital'])
        distribution=ordinary+extra+capital_return;endcash=p['cash']+sum(e['cash'] for e in subs)
        assert abs(endcash-(opening_cash+group_cash+nonop_cash+netfund-distribution))<1e-7
        assert p['cash']>=-1e-9
        assert ordinary+extra<=max(0.,p['re']+ordinary+extra)+1e-8
        out.append(dict(year=y,revenue=rev,core_net_margin=margin,group_net_profit=group_np,
          capex=allcapex,delta_nwc=allwc,economic_fcf=group_cash,nonop_cash=nonop_cash,nonop_profit=nonop_profit,
          ordinary=ordinary,special=extra,capital_return=capital_return,distribution=distribution,dps=distribution/SHARES,
          current_outstanding_shares=p['capital']-.02017,shares_per_initial_share=(p['capital']-.02017)/SHARES,
          cash=endcash,debt=p['debt']+sum(e['debt'] for e in subs),net_borrowing=netfund,
          parent=dict(cash=p['cash'],retained=p['re'],reserve=p['reserve'],capital=p['capital'],net_profit=parent_np,
             tax=parent_tax,interest=parent_interest,own_operating=parent_op,declared_upstream=gross_upstream,
             received_upstream=cash_upstream+parent_old_received,div_receivable=p['div_receivable'],settlement=settlement,
             ordinary=ordinary,special=extra,capital_return=capital_return,debt=p['debt'],tax_losses=copy.deepcopy(p['losses'])),
          subsidiaries=subrows,asset_recovery=asset_recovery,consolidated_retained=consolidated_re))
        prevrev=rev
    return out

def value(rows,r):
    pv=sum(x['dps']/(1+r)**x['year'] for x in rows)
    first=sum(x['dps']/(1+r)**x['year'] for x in rows[:5])
    tv=sum(x['dps']/(1+r)**(x['year']-5) for x in rows[5:])
    assert abs(pv-(first+tv/(1+r)**5))<1e-10
    return dict(pv=pv,tv5=tv,pv_first5=first,tv_pv_share=(pv-first)/pv,r=r)

def scenarios():
    cases={'base':copy.deepcopy(BUDGET)}
    b=copy.deepcopy(BUDGET);b.update(revenue1=4.45,growth=[-.03,.05,.06,.035],margin1=.125,margins=[.122,.138,.147,.15],receivable_shock=.15,jv_year=7,other_year=10);cases['cyclical']=b
    b=copy.deepcopy(BUDGET);b.update(revenue1=4.65,growth=[-.03,-.02,0.,.01],margin1=.13,margins=[.12,.115,.115,.115],terminal_growth=.005,terminal_margin=.10,parent_cost=.125,fixed_growth_ratio=.9,nwc_ratio=.10,jv_cash=.22,other_cash=.20);cases['structural']=b
    b=copy.deepcopy(BUDGET);b.update(revenue1=5.10,growth=[.05,.055,.05,.04],margin1=.152,margins=[.157,.16,.162,.162],terminal_growth=.02,terminal_margin=.15,fixed_growth_ratio=.8,jv_cash=.36,other_cash=.45);cases['upside']=b
    b=copy.deepcopy(BUDGET);b['margin_shift']=-.01;cases['margin_minus_1pp']=b
    b=copy.deepcopy(BUDGET);b.update(upstream_lag=1,opening_reserve_full=False,settlement=[.50,.20],parent_cash=1.25,core_cash=[.342,.138,.166,.104],receivable_shock=.20,other_year=15);cases['cash_legal_delay']=b
    b=copy.deepcopy(BUDGET);b['capital_release_year']=25;cases['capital_release_delayed']=b
    return cases

def auxiliary():
    # Independent economic capitalization: stable replacement cash earnings, no future recovery growth.
    # Product-level normalised 5.0bn sales; net owner earnings 0.58-0.68bn excluding all investment income.
    # No-growth earnings power at 9.5%-8.5% capital cost; independently normalized earnings; asset recoveries timed.
    rows=[]
    for earnings,multiple,r in [(.58,1/.095,.10),(.68,1/.085,.085)]:
        # excess liquid financial assets net minorities and 0.75bn liquidity/settlement execution cushion;
        # commitments and obligations are the SAME 0.15bn construction and 0.003bn acquisition amount.
        extra=(2.1308818324-.05-.75-.15-.00304348433)
        jv=.30/(1+r)**5;other=.35/(1+r)**8;receivable=.03/(1+r)**6
        rows.append(dict(earnings=earnings,multiple=multiple,operations=earnings*multiple,
          liquid_bridge=extra,jv_pv=jv,other_pv=other,receivable_pv=receivable,
          per_share=(earnings*multiple+extra+jv+other+receivable)/SHARES))
    return rows

def boundary_diagnostics():
    # Exercise the actual full production path with all first-year shareholder cash disabled.
    # An impossible required investment must fail; no residual/terminal value is manufactured.
    b=copy.deepcopy(BUDGET)
    b.update(payout=0.,special=0.,capital_release_year=10000,commitments=[20.,0.])
    try:
        path(b,1)
    except ValueError as err:
        assert str(err).startswith('finite funding exceeded')
        failed=dict(status='infeasible',reason=str(err),pv=None,tv5=None,
          zero_ordinary_target=True,zero_special=True,capital_return_disabled=True,
          required_first_year_construction=20.,tested_function='path',years_attempted=1)
    else:
        raise AssertionError('full path accepted infeasible required investment at zero distributions')
    # Strictly positive cash is still insufficient if a binding operating floor cannot be funded.
    try:
        financing(dict(name='positive_cash_below_floor',cash=.03,debt=0.),.10,.05)
    except ValueError as err:
        assert str(err).startswith('finite funding exceeded')
        positive=dict(status='infeasible',reason=str(err),pv=None,tv5=None,
          opening_cash=.03,required_floor=.10,finite_facility=.05,tested_function='financing')
    else:
        raise AssertionError('positive cash below floor incorrectly accepted')
    return dict(zero_distribution_required_investment=failed,positive_cash_floor=positive)

def tests():
    e=dict(cash=10.,re=-2.,reserve=0.,capital=10.,losses=[])
    assert abs(accrue_legal(e,5.)-.3)<1e-12 and abs(e['re']-2.7)<1e-12
    assert payment(e,10.,0.)==2.7 and abs(e['cash']-7.3)<1e-12
    e=dict(cash=10.,re=0.,reserve=4.9,capital=10.,losses=[])
    assert abs(accrue_legal(e,4.)-.1)<1e-12 and abs(e['re']-3.9)<1e-12
    assert payment(e,2.,9.)==1.;assert payment(e,8.,9.)==0.
    e=dict(losses=[]);assert tax(e,-2.,.25,1)==0.;assert tax(e,1.,.25,2)==0.;assert abs(tax(e,3.,.25,3)-.5)<1e-12
    e=dict(losses=[]);tax(e,-2.,.25,1);assert tax(e,1.,.25,7)==.25
    v=value([dict(year=i,dps=1.) for i in range(1,7)],0.)
    assert v['pv']==6. and v['tv5']==1.
    # finite funding actual production function, not separate identity
    e=dict(name='test',cash=-.1,debt=0.);assert abs(financing(e,.1,.25)-.2)<1e-12
    try:financing(dict(name='test',cash=-1.,debt=0.),.1,.25);raise AssertionError('unlimited borrowing')
    except ValueError:pass
    e=dict(cash=3.,re=0.,reserve=1.,capital=2.,debt=0.,div_receivable=.4)
    assert collect_old_dividend(e)==.4 and e['re']==0. and e['cash']==3.4
    assert capital_payment(e,2.,1.)==1. and e['capital']==1. and e['re']==0.
    assert capital_payment(dict(cash=3.,re=-1.,capital=2.,debt=0.),0.,0.)==0.
    return 'passed: old receivable no earnings, pro-rata capital reduction, loss-before-reserve, cap, shared distribution pool, cash floor, loss expiry, PV/TV, finite finance'

def main():
    result=dict(symbol='CN:002372',unit='CNY billion; DPS CNY',shares=SHARES,budget=BUDGET,tests=tests(),scenarios={})
    for name,b in scenarios().items():
        rows=path(b);vals=[value(rows,r) for r in [.10,.085]]
        # Complete annual outputs, compact JSON; numerical horizon not commercial evidence.
        result['scenarios'][name]=dict(inputs=b,annual=rows,valuation=vals)
    result['auxiliary']=auxiliary()
    result['boundary_diagnostics']=boundary_diagnostics()
    longer=path(BUDGET,300)
    result['convergence_240_vs_300']=[value(longer,r)['pv']-result['scenarios']['base']['valuation'][i]['pv'] for i,r in enumerate([.10,.085])]
    dest=pathlib.Path(__file__).with_name('2026-Q3-output.json')
    dest.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n')
    print(json.dumps({k:v['valuation'] for k,v in result['scenarios'].items()},ensure_ascii=False,indent=2))
    print('base DPS', [x['dps'] for x in result['scenarios']['base']['annual'][:5]],'aux',result['auxiliary'])
if __name__=='__main__':main()
