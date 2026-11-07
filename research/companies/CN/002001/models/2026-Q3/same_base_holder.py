"""Same-base future rights, with every rate-dependent term repriced. UNEXECUTED.
No new operating scenario. Original float order is an exact source interface gate;
Fraction forward/reverse is a separate mathematical identity, not independent valuation.
"""
from fractions import Fraction

def source_components(base,rate,shares):
    s=base['inputs']
    operating=base['tail_cash_y11']/(rate-s['g'])
    deferred=base['trapped_principal_y10']*((1+s['fin_yield'])/(1+rate))**5
    terminal10=operating+base['principal_release_y10']+deferred
    pv_div=sum(z['ordinary_dividend']/(1+rate)**z['year'] for z in base['years'])
    pv_terminal=terminal10/(1+rate)**10
    value=(sum(v/(1+rate)**(i+1) for i,v in enumerate([z['ordinary_dividend'] for z in base['years']]))+terminal10/(1+rate)**len(base['years']))/shares
    terminal5=(sum(z['ordinary_dividend']/(1+rate)**(z['year']-5) for z in base['years'][5:])+terminal10/(1+rate)**5)/shares
    return {'terminal_operating_y10':operating,'deferred_principal_pv_y10':deferred,
            'terminal_y10':terminal10,'terminal_y5_per_share':terminal5,'value_per_share':value,
            'pv_distributions':pv_div,'pv_terminal':pv_terminal,'terminal_pv_share':pv_terminal/(pv_div+pv_terminal)}

def source_order(base,rate,shares):return source_components(base,rate,shares)['terminal_y5_per_share']
def q(v):return Fraction(str(v))
def rational_terminal(base,r):
    return q(base['tail_cash_y11'])/(r-q(base['inputs']['g']))+q(base['principal_release_y10'])+q(base['trapped_principal_y10'])*((1+q(base['inputs']['fin_yield']))/(1+r))**5

def rational_direct(base,rate,shares):
    r=q(rate)
    return (sum((q(z['ordinary_dividend'])/(1+r)**(z['year']-5) for z in base['years'][5:]),Fraction(0))+rational_terminal(base,r)/(1+r)**5)/q(shares)

def rational_reverse(base,rate,shares):
    r=q(rate);x=rational_terminal(base,r)
    for row in reversed(base['years'][5:]):x=(x+q(row['ordinary_dividend']))/(1+r)
    return x/q(shares)

def exact_anchor(base,shares):
    if len(base['years'])!=10 or [z['year'] for z in base['years']]!=list(range(1,11)):raise ValueError('Incomplete base history')
    computed=source_components(base,base['inputs']['r'],shares)
    for key,value in computed.items():
        if type(value)!=type(base[key]) or value!=base[key]:raise AssertionError(('original_order_anchor',key,value,base[key]))
    return computed

def formal_checks(base,shares):
    exact_anchor(base,shares)
    rates={}
    for r in ('0.10','0.095','0.09'):
        a=rational_direct(base,r,shares);b=rational_reverse(base,r,shares)
        assert a==b
        rates[r]={'float_source_order':source_components(base,float(r),shares),'fraction_tv5':str(a)}
    return {'post_dividend_Y5_complete_state':base['years'][4], 'future_rows':base['years'][5:],
            'terminal_primitives':{k:base[k] for k in ('tail_cash_y11','principal_release_y10','trapped_principal_y10')},
            'inputs':base['inputs'],'rates':rates,'scope':'same base rights, NOT core operating risk range'}
