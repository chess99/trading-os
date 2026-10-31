#!/usr/bin/env python3
"""Standalone common-equity cash/state model. Amounts CNY bn; no files read."""
import json, math
ASOF='2026-10-29T11:19:00+00:00'
SHARES=1.471901463
C0=22.50258359789
DEBT0=3.00175833334+2.22686673016+0.72780189151+0.01463845030
EQ0=47.05370980849
MIN0=.16178127204
I0=2.99299421195+.35816458841
W0=.62088824436
CLAIM0=.01111000899
R0=.44109823048
OP0=EQ0+MIN0+DEBT0-C0-I0-W0-CLAIM0

def law(re,res,cap,profit):
    # Losses first absorbed by retained earnings; 10% only after accumulated losses filled.
    eligible=max(0.,re+profit)-max(0.,re)
    add=min(max(0.,cap*.5-res),max(0.,eligible)*.10)
    return re+profit-add,res+add,add

def step(s,p):
    """Same production transition used by formal scenarios and hand cases."""
    q=s.copy(); old=s.copy();y=p['year'];r=p['rate'];nop=p['nopat'];netinv=p['capex']-p['da']+p['dnwc']
    # Current restricted accrued interest is already an asset, not new income.
    ry=(s['restricted']-s['accrued'])*p['cash_yield'];release=0.
    if y==2:release+=s['accrued'];q['accrued']=0.
    if y==4:release+=s['restricted']-s['accrued']+ry
    q['restricted']+=ry-release
    py=s['pcash']*p['cash_yield']+ry*.9;sy=s['scash']*p['cash_yield'];my=s['mcash']*p['cash_yield']+ry*.1
    cashyield=py+sy+my
    wy=s['wealth']*p['cash_yield'];wr=s['wealth'] if y==1 else 0.;q['wealth']-=wr
    invprofit=s['invest']*p['investment_roe'];invdiv=invprofit*.4
    q['invest']+=invprofit-invdiv
    proceeds=exitloss=0.
    if y==p['exit_year']:
        gross=q['invest']*p['exit_recovery'];fee=.01*gross;tax=.25*max(0.,gross-fee-s['invest_cost']);proceeds=gross-fee-tax
        exitloss=proceeds-q['invest'];q['invest']=0.
    recovery=claimloss=0.
    if y==4:
        recovery=s['claim']*.925;claimloss=recovery-s['claim'];q['claim']=0.;q['claim_face']-=s['claim'];q['claim_debtor_obligation']-=s['claim']
        # Allowance is accounting impairment, not legal extinguishment. Residual face remains fully provided.
    repayment=min(s['debt'],p['repay']);interest=s['debt_face']*p['debt_rate']*.75;q['debt']-=repayment
    paid_accrued=min(s['debt_accrued'],repayment);q['debt_accrued']-=paid_accrued;q['debt_face']-=repayment-paid_accrued
    minority_profit=max(0.,nop)*p['minority_share'];minority_div=.8*minority_profit;q['minority']+=minority_profit-minority_div
    commonprofit=nop+cashyield+wy+invprofit+exitloss+claimloss-interest-minority_profit
    # All finance assets held in the paying parent. Producer/residual bucket includes small NCI activities.
    pp=nop*.10+py+wy+invprofit+exitloss+claimloss-interest
    sp=nop*.75+sy;mp=nop*.15+my-minority_profit
    q['pcash']+=nop*.10-netinv*.20+py-ry*.9+wy+invdiv+proceeds+recovery+release*.9+wr-interest-repayment
    q['scash']+=sp
    q['mcash']+=nop*.15+my-ry*.1-netinv*.80-minority_div+release*.1
    # Normal scheduled gross internal settlements; never set off legal balances.
    pay=min(q['internal_payable'],p['internal_pay'],max(0.,q['pcash']-p['parent_floor']))
    q['pcash']-=pay;q['scash']+=pay;q['internal_payable']-=pay
    repay_internal=min(q['internal_receivable'],p['internal_collect'],max(0.,q['mcash']-p['producer_floor']-q['producer_div_payable']))
    q['mcash']-=repay_internal;q['pcash']+=repay_internal;q['internal_receivable']-=repay_internal
    advance=max(0.,p['producer_floor']-q['mcash'])
    if advance>max(0.,q['pcash']-p['parent_floor']):raise ValueError('infeasible producer funding')
    q['pcash']-=advance;q['mcash']+=advance;q['internal_receivable']+=advance
    q['sales_re'],q['sales_reserve'],sa=law(q['sales_re'],q['sales_reserve'],.1,sp)
    q['producer_re'],q['producer_reserve'],ma=law(q['producer_re'],q['producer_reserve'],.487582236,mp)
    # Declaration is recognized once; cash follows only to extent declared payable.
    sd=min(max(0.,q['sales_re']),max(0.,sp)*p['upstream']+max(0.,q['scash']-p['sales_floor']-sp)*.20,max(0.,q['scash']-p['sales_floor']-q['sales_div_payable']))
    md=min(max(0.,q['producer_re']),max(0.,mp)*p['upstream'],max(0.,q['mcash']-p['producer_floor']-q['producer_div_payable']))
    q['sales_re']-=sd;q['producer_re']-=md
    q['div_receivable']+=sd+md
    actual_s=min(q['sales_div_payable']+sd*p['receipt_fraction'],max(0.,q['scash']-p['sales_floor']))
    actual_m=min(q['producer_div_payable']+md*p['receipt_fraction'],max(0.,q['mcash']-p['producer_floor']))
    q['sales_div_payable']+=sd-actual_s;q['producer_div_payable']+=md-actual_m
    q['scash']-=actual_s;q['mcash']-=actual_m;q['pcash']+=actual_s+actual_m;q['div_receivable']-=actual_s+actual_m
    q['parent_re'],q['parent_reserve'],pa=law(q['parent_re'],q['parent_reserve'],SHARES,pp+sd+md)
    desired=p['fixed_div'] if p['fixed_div'] is not None else max(0.,commonprofit)*p['payout']+max(0.,s['pcash']-p['excess_floor'])*.10
    dividend=min(desired,max(0.,q['parent_re']),max(0.,q['pcash']-p['parent_floor']))
    q['pcash']-=dividend;q['parent_re']-=dividend
    q['opcapital']+=netinv
    q['equity']+=commonprofit-dividend
    groupcash=q['pcash']+q['scash']+q['mcash']+q['restricted']
    assets=q['opcapital']+groupcash+q['invest']+q['wealth']+q['claim']
    assert abs(assets-q['debt']-q['minority']-q['equity'])<1e-7*max(1,abs(assets))
    expcash=sum(s[k] for k in ['pcash','scash','mcash','restricted'])+nop-netinv+cashyield+wy+invdiv+proceeds+recovery+wr-interest-repayment-minority_div-dividend
    assert abs(groupcash-expcash)<1e-8*max(1,abs(expcash))
    assert min(q['pcash'],q['scash'],q['mcash'],q['restricted'],q['invest'],q['wealth'],q['debt'])>=-1e-8
    assert abs(q['div_receivable']-q['sales_div_payable']-q['producer_div_payable'])<1e-8
    assert dividend<=max(0.,old['parent_re']+pp+sd+md-pa)+1e-8
    flows=dict(nopat=nop,netinvestment=netinv,common_profit=commonprofit,dividend=dividend,desired_dividend=desired,dividend_per_share=dividend/SHARES,cash_yield=cashyield,restricted_income_net=ry,restricted_income_gross=ry/.75,restricted_income_tax=ry/.75*.25,claim_gross_collection=s['claim'] if y==4 else 0.,wealth_income=wy,wealth_redemption=wr,investment_profit=invprofit,investment_dividend=invdiv,investment_sale=proceeds,investment_exit_gain=exitloss,claim_recovery=recovery,claim_gain=claimloss,restricted_release=release,interest=interest,debt_repayment=repayment,minority_profit=minority_profit,minority_dividend=minority_div,subsidiary_declaration=sd+md,subsidiary_receipt=actual_s+actual_m,internal_payment=pay,internal_collection=repay_internal,producer_advance=advance,parent_profit=pp+sd+md,parent_reserve_add=pa,sales_reserve_add=sa,producer_reserve_add=ma,cash_residual=groupcash-expcash,equity_residual=assets-q['debt']-q['minority']-q['equity'])
    return q,flows

def initial(parent_cash=19.5,legal_sales=4.,parent_re=23.4):
    return dict(pcash=parent_cash,scash=1.8,mcash=C0-R0-parent_cash-1.8,restricted=R0,accrued=.42982209448,wealth=W0,invest=I0,invest_cost=2.9,claim=CLAIM0,claim_face=.09111000899,claim_debtor_obligation=.09111000899,claim_allowance=.08,debt=DEBT0,debt_face=DEBT0-.005,debt_accrued=.005,minority=MIN0,equity=EQ0,opcapital=OP0,parent_re=parent_re,parent_reserve=1.471941963,sales_re=legal_sales,sales_reserve=.05,producer_re=0.,producer_reserve=0.,internal_receivable=13.47855455085,internal_payable=5.8,div_receivable=0.,sales_div_payable=0.,producer_div_payable=0.)

def run(name='base',rate=.095,horizon=240,overrides=None):
    o=overrides or {};s=initial(o.get('parent_cash',19.5),o.get('sales_re',4.),o.get('parent_re',23.4));s['invest_cost']=o.get('invest_cost',2.9);start=s.copy();rows=[];pv=0.;ri=0.;rev0=18.5
    highs=[16.2,16.5,17.2,18.,18.9];lows=[2.3,2.35,2.4,2.5,2.6];sales=[.17,.17,.165,.16,.155];taxes=[.175,.175,.17,.17,.17]
    caps=[2.9,2.8,2.3,1.7,1.3];das=[.8,.85,.9,.95,1.];nwcs=[.2,.15,.1,.1,.1]
    if name=='earnings_check':highs=[16.4]*5;lows=[2.4]*5;sales=[.165]*5;taxes=[.175]*5
    if name=='cyclical':highs=[14.8,14.8,15.8,17.,18.4];sales=[.185,.185,.18,.17,.16]
    if name=='structural':highs=[14.8,14.2,13.7,13.2,12.8];lows=[2.3,2.3,2.3,2.3,2.3];sales=[.20]*5;taxes=[.185]*5
    if name=='upside':highs=[17.,18.,19.2,20.5,21.7];sales=[.165,.16,.155,.15,.15]
    for y in range(1,horizon+1):
        old=s.copy()
        if y<=5:
            high=highs[y-1];low=lows[y-1];rev=high+low
            gm=(high*(.865 if name=='structural' else .895)+low*.43)/rev
            margin=gm-sales[y-1]-taxes[y-1]-.05
            cap,da,dn=caps[y-1],das[y-1],nwcs[y-1]
        else:
            growth=(0. if name=='earnings_check' else -.01 if name=='structural' else (.015 if name=='upside' else .01)) if y<=30 else (-.01 if name=='structural' else .005)
            if name=='earnings_check':growth=0.
            rev=rev0*(1+growth)
            m5=(highs[-1]*(.865 if name=='structural' else .895)+lows[-1]*.43)/(highs[-1]+lows[-1])-sales[-1]-taxes[-1]-.05
            target=.25 if name=='structural' else .35
            margin=m5+(target-m5)*min(1.,max(0.,(y-15)/35))
            da=rev*.04;dn=0.
            # Maintenance replaces depreciation; contraction keeps idle operating assets, no free liquidation.
            cap=da+max(0.,growth)*s['opcapital']
        rev*=o.get('revenue_factor',1.);margin+=o.get('margin_delta',0.);nop=rev*margin*.75
        if y<=5:cap+=o.get('extra_capex',0.)
        p=dict(year=y,rate=rate,nopat=nop,capex=cap,da=da,dnwc=dn,cash_yield=.015,debt_rate=o.get('debt_rate',.025),minority_share=.008,investment_roe=.05,exit_year=o.get('exit_year',15),exit_recovery=o.get('exit_recovery',.85),repay=(5.2286250635 if y==1 else DEBT0-5.2286250635 if y==2 else 0.),parent_floor=2.,sales_floor=.5,producer_floor=.5,internal_pay=1. if y<=6 else 0.,internal_collect=.8,upstream=o.get('upstream',.90),receipt_fraction=o.get('receipt_fraction',1.),fixed_div=8.5 if y==1 else None,payout=.75 if y<=5 else .90,excess_floor=3.)
        if o.get('finite_recovery') and y>=30 and y%10==0:p.update(upstream=1e6,receipt_fraction=1.)
        if o.get('hand_params'):p.update(o['hand_params'])
        s,f=step(s,p);pv+=f['dividend']/(1+rate)**y;ri+=(f['common_profit']-rate*old['equity'])/(1+rate)**y
        rows.append(dict(year=y,revenue=rev,ebit_margin=margin,parameters=p,opening=old,flows=f,closing=s.copy(),pv_dividend=f['dividend']/(1+rate)**y));rev0=rev/o.get('revenue_factor',1.)
    book_tail=s['equity']/(1+rate)**horizon
    value=pv+book_tail
    # Clean surplus residual income is an alternative capital-charge computation, not independent commercial evidence.
    rim=start['equity']+ri
    assert abs(value-rim)<1e-7*max(1,abs(value))
    v5=sum(row['flows']['dividend']/(1+rate)**(row['year']-5) for row in rows[5:])+s['equity']/(1+rate)**(horizon-5)
    return dict(name=name,discount_rate=rate,horizon=horizon,initial=start,years=rows,value_bn=value,value_per_share=value/SHARES,residual_income_value_bn=rim,residual_income_value_per_share=rim/SHARES,year5_terminal_per_share=v5/SHARES,year5_terminal_pv_share=v5/((1+rate)**5)/value,tail_book_pv_bn=book_tail,first5_distributions=[z['flows']['dividend_per_share'] for z in rows[:5]])

def main():
    cases={}
    for name,rate,o in [('base',.095,{}),('earnings_check',.095,{}),('core_low',.10,{}),('core_high',.09,{}),('cyclical',.095,{}),('structural',.105,{}),('upside',.09,{}),('margin_down',.095,{'margin_delta':-.05}),('upstream_delay',.095,{'upstream':.65,'receipt_fraction':.5,'parent_cash':17.,'sales_re':1.,'parent_re':20.}),('extra_capital',.095,{'extra_capex':.5}),('investment_late',.095,{'exit_year':25,'exit_recovery':.65}),('investment_cost_zero',.095,{'invest_cost':0.}),('tail_160',.095,{}),('tail_320',.095,{})]:
        economic=name if name in ('cyclical','structural','upside','earnings_check') else 'base'
        cases[name]=run(economic,rate,160 if name=='tail_160' else 320 if name=='tail_320' else 240,o)
    # Genuine continuation under identical policies, including every annual economic state.
    extended=[('base','base',.095,{}),('core_low','base',.10,{}),('core_high','base',.09,{}),('earnings_check','earnings_check',.095,{}),('structural','structural',.105,{}),('upstream_delay','base',.095,{'upstream':.65,'receipt_fraction':.5,'parent_cash':17.,'sales_re':1.,'parent_re':20.})]
    for tag,economic,rate,opts in extended:
        for horizon in (480,960):cases[f'extension_{tag}_{horizon}']=run(economic,rate,horizon,opts)
        if tag in ('base','earnings_check','structural','upstream_delay'):
            cases[f'finite_recovery_{tag}']=run(economic,rate,480,dict(opts,finite_recovery=True))
    print(json.dumps(dict(information_cutoff=ASOF,currency='CNY',amount_unit='CNY billion except per-share',shares_bn=SHARES,cases=cases),ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False))
if __name__=='__main__':main()
