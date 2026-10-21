import json, math
# All company cash/profits in CNY billions, shares in billions.
ISSUED=(20793122579+902767867)/1e9
OPTIONS=(68013597+352207727)/1e9
N=ISSUED+OPTIONS
PROCEEDS=(68013597*55+352207727*51.6)*0.8686/1e9
GROSS_FIN=sum([196.293,132.237,248.473,6.934,19.043,29.500])
# H1 detailed financial assets carried forward; Q3 detailed liabilities estimated.
F0=GROSS_FIN+26.966+9.014-(85.542-(73.910-55.797))-9.240-100-4.476+PROCEEDS
NP=[100,103,106,108,110]
DA=[190,192,194,196,198]
CAPEX=[145,147,149,151,153]
LEASE_PRINCIPAL=[35,35,36,37,37]
WC=[20,17,13,10,8]
CF=[p+d-c-l-w for p,d,c,l,w in zip(NP,DA,CAPEX,LEASE_PRINCIPAL,WC)]
DPS=[4.66,4.80,4.97,5.11,5.29]
ASSOC_CASH=[6,6.2,6.4,6.6,6.8]

def calculate(r=.085,g=.0075,roi=.10,profit=NP,cf=CF,dps=DPS,f0=F0,assoc_terminal=205,yield_rate=.02,terminal_cf_override=None):
    f=f0; rows=[]
    for i,(p,c,d,a) in enumerate(zip(profit,cf,dps,ASSOC_CASH),1):
        opening=f; yield_cash=opening*yield_rate; dividends=d*N
        f=opening+c+a+yield_cash-dividends
        assert abs((f-opening)-(c+a+yield_cash-dividends))<1e-9
        rows.append(dict(year=i,operating_profit=p,operating_cash=c,dividend=dividends,dps=d,financial_income=yield_cash,associate_dividend=a,ending_financial_assets=f))
    terminal_cash=profit[-1]*(1+g)*(1-g/roi) if terminal_cf_override is None else terminal_cf_override
    operations_terminal=terminal_cash/(r-g)
    terminal=operations_terminal+f+assoc_terminal
    pv_div=sum(d*N/(1+r)**i for i,d in enumerate(dps,1))
    pv_terminal=terminal/(1+r)**5
    return dict(value=(pv_div+pv_terminal)/N,terminal_per_share=terminal/N,operations_terminal=operations_terminal,terminal_cash=terminal_cash,terminal_pv_fraction=pv_terminal/(pv_div+pv_terminal),ending_financial_assets=f,rows=rows)

def output():
    lower=calculate(r=.09,g=.005,assoc_terminal=190)
    upper=calculate(r=.08,g=.01,assoc_terminal=220)
    base=calculate()
    weak=calculate(profit=[90,95,101,106,110],cf=[65,80,95,104,110],dps=[4.30,4.50,4.80,5.00,5.29])
    # Structural: permanent pricing erosion + reinvestment drag, not mean reversion.
    structural=calculate(r=.095,g=0,roi=.08,profit=[95,90,85,82,80],cf=[80,70,65,60,60],dps=[4.0,3.8,3.5,3.3,3.2],assoc_terminal=165,terminal_cf_override=60)
    upside=calculate(r=.08,g=.015,roi=.12,profit=[110,116,122,128,135],cf=[110,116,122,128,135],dps=[4.8,5.1,5.4,5.7,6.0],assoc_terminal=225)
    bridge_low=sum((d*N-c)/(1.09)**i for i,(d,c) in enumerate(zip(DPS,CF),1))+(lower["ending_financial_assets"]+190)/1.09**5
    bridge_high=sum((d*N-c)/(1.08)**i for i,(d,c) in enumerate(zip(DPS,CF),1))+(upper["ending_financial_assets"]+220)/1.08**5
    pe_derived=[sum(.9*1.02**i/(1+r)**i for i in range(1,6))+1.02**5*(1+g)*(1-g/.10)/(r-g)/(1+r)**5 for r,g in [(.09,.005),(.08,.01)]]
    assoc_bridge=[109*1.01**5*9+42*1.02**5*16+150*1.01**5,109*1.02**5*10+42*1.03**5*18+150*1.02**5]
    book_equity=1395.990+PROCEEDS; book_rows=[]
    for i,row in enumerate(base["rows"]):
        book_equity+=row["operating_profit"]+row["financial_income"]+14+i*.25-row["dividend"]
        book_rows.append(book_equity)
    pe_low=(100*11.5+bridge_low)/N
    pe_high=(100*13.5+bridge_high)/N
    assert len(DPS)==5 and abs(sum(CF)-504)<1e-9
    assert abs(calculate(r=.1,g=0,profit=[10]*5,cf=[10]*5,dps=[0]*5,f0=0,assoc_terminal=0,yield_rate=0)['operations_terminal']-100)<1e-9
    return dict(auxiliary_derived_pe=pe_derived,associate_terminal_bridge_cny_100m=assoc_bridge,book_common_equity_bridge=book_rows,issued_shares=ISSUED,options=OPTIONS,fully_diluted_shares=N,exercise_cash=PROCEEDS,initial_surplus_financial_assets=F0,gross_identified_q3_financial_assets=GROSS_FIN,base=base,lower=lower,upper=upper,auxiliary_pe=[pe_low,pe_high],financial_bridge=[bridge_low,bridge_high],cyclical=weak,structural=structural,upside=upside,sensitivity_r_plus_1pp=calculate(r=.095),sensitivity_operating_profit_minus_10pct=calculate(profit=[p*.9 for p in NP],cf=[c-0.1*p for c,p in zip(CF,NP)]),sensitivity_f0_minus_20=calculate(f0=F0-20))
if __name__=='__main__': print(json.dumps(output(),ensure_ascii=False,indent=2))
