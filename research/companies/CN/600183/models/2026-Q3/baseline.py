#!/usr/bin/env python3
"""600183 independent conditional economic budgets. Stdlib, no input files.
Units CNY billion, shares billion. Legal budgets are NOT certified legal accounts.
Full annual state emitted, no terminal sale or market multiple. Revision 1 draft.
"""
import json, math, sys, copy
ASOF='2026-10-30T07:41:00Z'
SHARES=2.429003670
E_SHARES=.860261067
E_OWN=.514142157/E_SHARES
FACE=2-.009340018*96.84

def close(a,b):
    assert abs(a-b)<1e-7*max(1,abs(a),abs(b)),(a,b)

def initial():
    # Individual legal parent observations; W is a consolidated economic budget.
    p_eq=16.74415596132-9.90020676771
    x_eq=28.13283934617-9.83852725721
    w_eq=x_eq-p_eq
    nci=4.08615932122-(1-E_OWN)*9.83852725721
    entries=[('P',1.80238444867,3.58418560077,.00351469445,.16754047412,FACE,p_eq,6.77530085961,2.55405354960,2.429003670,.86622042977),
             ('W',.78145640530,.43442228620,.01285056823,1.67626283112,0,w_eq,1.5,2.,7.,0),
             ('E',2.47839140265,.2779,.00188823083,2.88106548309,0,9.83852725721,3.07899876088,.35227694504,.860261067,.05167824917)]
    out={}
    for name,c,f,r,d,b,e,re,sr,cap,asset in entries:
        ic=e+d+b-c-f-r-asset
        wc={'P':1.2,'W':6.7,'E':2.8}[name]
        out[name]=dict(cash=c,financial=f,restricted=r,bank=d,bond=b,equity=e,re=re,reserve=sr,paid_capital=cap,investments=asset,investment_cost=asset,working=wc,fixed=ic-wc,losses=[],dividend_receivable=0.,internal_face=0.,internal_allowance=0.)
    out['P']['internal_face']=.80699973563
    out['W']['internal_payable']=.80699973563
    return out,nci/w_eq

def tax_charge(profit,losses,year,rate=.15):
    losses=[x[:] for x in losses if x[0]>=year]
    taxable=max(0.,profit)
    for x in losses:
        used=min(x[1],taxable); x[1]-=used; taxable-=used
    if profit<0: losses.append([year+5,-profit])
    return taxable*rate,losses

def flow(s, year, revenue, ebit, capex, new_wc, minimum, bank_ceiling,
         repayment=0.,extra_cash=0.,extra_profit=0.,equity_change=0.,buyback=0.,
         invest_release=0.,financial_tax=0.,reserve_policy=True,noncash_comp=0.,duration=1.,tax_exempt_income=0.,tax_rate=.15,defer_financing=False):
    """The real production cash/earnings chain, also used by hand cases."""
    o=copy.deepcopy(s)
    da=o['fixed']*.07*duration
    fi=(o['cash']*.015+o['financial']*.02+o['restricted']*.02)*duration
    interest=(o['bank']*.035+o['bond']*.0001)*duration
    redemption=o['financial'] if year==1 else 0.
    financial_tax=financial_tax if redemption else 0.
    ebit-=noncash_comp
    pretax=ebit-interest+fi+extra_profit
    tax,losses=tax_charge(pretax+noncash_comp-tax_exempt_income,o['losses'],year,tax_rate)  # No unverified tax deduction for treasury grants
    ni=pretax-tax-financial_tax
    dwc=new_wc-o['working']
    release=o['restricted'] if year==6 else 0.
    raw=release+o['cash']+ni+noncash_comp+da-capex-dwc+redemption+extra_cash-extra_profit+invest_release-repayment-buyback
    # Financial liquidation levy is included once in NI; cash includes that NI.
    borrow=0. if defer_financing else min(max(0.,minimum-raw),max(0.,bank_ceiling-o['bank']))
    cash=raw+borrow
    # Do not continue an insolvent year as though value remained available.
    failed=False if defer_financing else cash < -1e-10
    fixed=o['fixed']+capex-da
    reserve_add=0.
    if reserve_policy:
        reserve_add=min(.1*max(0.,ni+min(0.,o['re'])),max(0.,.5*o['paid_capital']-o['reserve']))
    re=o['re']+ni-reserve_add
    ns=dict(o,cash=cash,financial=o['financial']-redemption,restricted=o['restricted']-release,
            bank=o['bank']+borrow,bond=o['bond']-repayment,equity=o['equity']+ni+noncash_comp+equity_change-buyback,
            re=re,reserve=o['reserve']+reserve_add,fixed=fixed,working=new_wc,losses=losses,
            investments=o['investments']-invest_release,investment_cost=o['investment_cost']-invest_release)
    row=dict(year=year,duration=duration,opening=o,revenue=revenue,ebit=ebit,total_operating_cost=revenue-ebit,da=da,capex=capex,maintenance_capex_budget=da,net_fixed_investment=capex-da,working_change=dwc,
             finance_income=fi,interest=interest,pretax=pretax,cash_tax=tax,liquidation_tax=financial_tax,net_income=ni,
             cash_before_financing=raw,cash_before_upstream=raw,upstream_cash=0.,financing_deferred=defer_financing,borrow=borrow,bank_ceiling=bank_ceiling,minimum_cash=minimum,
             bond_repayment=repayment,extra_cash=extra_cash,extra_profit=extra_profit,investment_principal_released=invest_release,
             financial_redemption=redemption,restricted_release=release,buyback=buyback,equity_change=equity_change,
             reserve_addition=reserve_add,tax_rate=tax_rate,tax_exempt_income=tax_exempt_income,noncash_comp=noncash_comp,distribution=0.,failed=failed,closing=copy.deepcopy(ns))
    close(cash,o['cash']+ni+noncash_comp+da-capex-dwc+redemption+extra_cash-extra_profit+invest_release-repayment-buyback+borrow+release)
    return ns,row

def finance_after_upstream(s,row,upstream_cash):
    """Annual ordering: legally receivable current dividends arrive before parent liquidity test."""
    assert row['financing_deferred'] and row['borrow']==0.
    row['upstream_cash']=upstream_cash
    row['cash_before_financing']=s['cash']
    draw=min(max(0.,row['minimum_cash']-s['cash']),max(0.,row['bank_ceiling']-s['bank']))
    s['cash']+=draw;s['bank']+=draw
    row['borrow']=draw;row['failed']=s['cash'] < -1e-10;row['financing_deferred']=False
    row['closing']=copy.deepcopy(s)
    close(s['cash'],row['cash_before_upstream']+upstream_cash+draw)

def distribute(s,row,desired,cash_gate=1.):
    amount=min(max(0.,desired),max(0.,s['re']),max(0.,s['cash']-row['minimum_cash'])*cash_gate)
    s['cash']-=amount;s['re']-=amount;s['equity']-=amount
    row['distribution']=amount;row['closing']=copy.deepcopy(s)
    return amount

def scenario(name,method='A',margin_shift=0.,k=.103,cyclic=False,structural=False,upside=False,
             cash_delay=False,exchange=False,credit_failure=False,high_tax=False,years=400,shift_start=1):
    states,wminor=initial(); rows=[]; own=E_OWN; shares=SHARES
    # Unreported 30-day operating bridge is explicitly a budget, not an observed October result.
    bridge={}
    for tag,rev,earn,cap,dwc in [('P',2.08357509534,.66,.16,.15),('W',1.38905006356,.44,.14,.15),('E',1.25468232117,.30,.25,.10)]:
        states[tag],bridge[tag]=flow(states[tag],0,rev,earn,cap,states[tag]['working']+dwc,.05,10.,duration=30/365.,reserve_policy=tag!='P')
    before_known_capital=copy.deepcopy(states)
    # Known post-quarter repurchases: cash cost and treasury stock, never shareholder distribution.
    states['P']['cash']-=.059927076;states['P']['equity']-=.059927076
    states['E']['cash']-=.02499978436;states['E']['equity']-=.02499978436
    known_capital=dict(opening=before_known_capital,cash_spent={'P':.059927076,'W':0.,'E':.02499978436},closing=copy.deepcopy(states))
    stock=.0006063; estock=.000285426
    plegal=16.74415596132-.059927076+bridge['P']['net_income']
    pq=0.; eq=0.; area=185.; earea=2.1; price=175.; eprice=6600.
    totalpv=0.; laterpv=0.; dist=[]; failed=False
    for t in range(1,years+1):
        annual_opening=copy.deepcopy(states)
        ox=states['P']['fixed']+states['P']['working']+states['W']['fixed']+states['W']['working']
        oe=states['E']['fixed']+states['E']['working']
        if t>1:
            g=([.10,.08,.07,.06,.05][t-2] if t<=6 else max(.02,.05-(t-6)*.006))
            eg=([.12,.10,.08,.06,.05][t-2] if t<=6 else max(.02,.05-(t-6)*.006))
            if t<=15: area*=1+g;earea*=1+eg
            else: price*=1.02;eprice*=1.02
            if t<=5: price*=1.02;eprice*=1.02
        fade=min(1.,(t-1)/14.)
        effective_shift=margin_shift if t>=shift_start else 0.
        if method=='A':
            rx=area*price/1000.+1.*(1.02**(t-1)); er=earea*eprice/1000.
            mx=.22-.04*fade+effective_shift; me=.22-.05*fade+effective_shift
            ex=rx*mx; ee=er*me
        else:
            rx=ox*(2.30-.90*fade);er=oe*(1.40-.30*fade)
            ex=ox*(.45-.25*fade+effective_shift);ee=oe*(.30-.12*fade+effective_shift)
        if cyclic and t<=3:
            rx*=.85;er*=.82;ex=ex*.6;ee=ee*.55
        if structural and t>=2:
            rx*=.80;er*=.78;ex=rx*.09;ee=er*.085
        if upside:
            rx*=1.08;er*=1.10;ex*=1.18;ee*=1.20
        if credit_failure and t==1: ex-=20.;ee-=12.
        # Committed and plausible expansion funding remains in all stress scenarios.
        capx=([3.1,3.0,2.5,2.2,1.8][t-1] if t<=5 else .07*(states['P']['fixed']+states['W']['fixed'])+.025*rx)
        cape=([3.2,2.8,2.3,1.8,1.4][t-1] if t<=5 else .07*states['E']['fixed']+.025*er)
        if structural: capx*=1.1;cape*=1.1
        # Main five-year CCL fixed-capital envelope includes remaining Songshanhu, not already spent Jiangxi costs.
        pcap=capx*(.65 if t<=5 else .35);wcap=capx-pcap
        if method=='A':
            xwc=rx*(.245 if not cash_delay else .275);ewc=er*(.22 if not cash_delay else .28)
        else:
            xwc=rx*.25;ewc=er*.23
        internal=.80699973563 if t<8 else 0.
        if cash_delay and t<=2: internal+=.8
        if method=='B' and t>5:
            capital_growth=max(.02,.06-.004*(t-6))
            dxwc=xwc-states['P']['working']-states['W']['working']
            dewc=ewc-states['E']['working']
            capx=max(0.,.07*(states['P']['fixed']+states['W']['fixed'])+capital_growth*ox-dxwc)
            cape=max(0.,.07*states['E']['fixed']+capital_growth*oe-dewc)
            pcap=capx*.35;wcap=capx-pcap
        pwork=xwc*.30+internal;wwork=xwc*.70-internal
        prior_face=states['P']['internal_face']
        states['P']['internal_face']=internal
        states['W']['internal_payable']=internal
        oldpq=pq;oldeq=eq;old_epay=states['E'].get('dividend_payable',0.);pq=eq=0.
        # Settle all last-year declared subsidiary dividends, including minority payables.
        if cash_delay and t>1:
            states['W']['cash']-=oldpq/(1-wminor)
            states['E']['cash']-=old_epay
        for tag in ('W','E'): states[tag]['dividend_payable']=0.
        # Associate earnings are cash dividends; principal exits at carrying cost in year10 (budget, no exit multiple).
        assoc_profit=.085 if t<=10 else 0.
        principal=states['P']['investments'] if t==10 else 0.
        ep=states['E']['investments'] if t==10 else 0.
        repay=states['P']['bond'] if t==3 and not exchange else 0.
        exchanged=0.;exchange_gain=0.;exchange_tax=0.
        if t==3 and exchange:
            exchanged=states['P']['bond']/96.84/E_SHARES
            # H1 parent actual cost .98044781525B / .523482175B shares, used as tax-basis budget.
            cost=exchanged*E_SHARES*(.98044781525/.523482175)
            exchange_gain=states['P']['bond']-cost
            exchange_tax=max(0.,exchange_gain)*.15
            own-=exchanged;states['P']['bond']=0.
            states['P']['equity']+=FACE-exchange_tax
            states['P']['re']+=exchange_gain-exchange_tax
        # Actual future program uses treasury shares, fully regranted at t3; no free shrink in terminal denominator.
        pb=.190072924 if t==1 else 0.; eb=.12500021564 if t==1 else 0.
        if t==1: stock+=.0019;estock+=.00125
        if t==3: stock=0.;estock=0.
        # Employee cost included in EBIT; extra repurchase is paid once, no assumed grant proceeds.
        pre_flow=copy.deepcopy(states)
        erows={}
        for tag,r,e,c,w,extra,prof,pr,b,ft in [
            ('W',rx*.4,ex*.4,wcap,wwork,0.,0.,0.,0.,.005),
            ('E',er,ee,cape,ewc,.003 if t<=10 else 0.,.003 if t<=10 else 0.,ep,eb,.001),
            ('P',rx*.6,ex*.6,pcap,pwork,oldpq+oldeq+assoc_profit-exchange_tax,assoc_profit,principal,pb,.05)]:
            ceiling=0. if credit_failure else {'P':4.,'W':4.,'E':6.}[tag]*(1.02**(t-1))
            states[tag],erows[tag]=flow(states[tag],t,r,e,c,w,r*.035,ceiling,
                repayment=repay if tag=='P' else 0.,extra_cash=extra,extra_profit=prof,
                invest_release=pr,buyback=b,financial_tax=ft,reserve_policy=tag!='P',
                noncash_comp=({'P':.25,'W':0.,'E':.15}[tag] if t==3 else 0.),
                tax_exempt_income=assoc_profit if tag=='P' else 0.,tax_rate=.25 if high_tax and t>=4 else .15,defer_financing=tag=='P')
        # Cash distributions upstream are constrained by actual retained earnings budget and cash.
        wd=distribute(states['W'],erows['W'],max(0.,states['W']['cash']-erows['W']['minimum_cash'])*(.65 if t<=5 else min(1.,.65+.1*(t-5))))
        ed=distribute(states['E'],erows['E'],max(0.,states['E']['cash']-erows['E']['minimum_cash'])*(.45 if t<=5 else min(1.,.45+.1*(t-5))),.90)
        cash_own=own*E_SHARES/(E_SHARES-estock)
        wp=wd*(1-wminor);en=ed*cash_own;minor=(oldpq*wminor/(1-wminor)+old_epay-oldeq) if cash_delay else wd*wminor+ed*(1-cash_own)
        # Dividend confirmation and receipt separated; collection next year does not create second income.
        states['P']['re']+=wp+en;states['P']['equity']+=wp+en
        if cash_delay: pq=wp;eq=en
        else: states['P']['cash']+=wp+en
        states['P']['dividend_receivable']=pq+eq
        for tag,recv in [('W',pq),('E',eq)]:
            # A declared but unpaid dividend remains payer cash and payable, not already cash spent.
            if cash_delay:
                states[tag]['cash']+=recv/(1-wminor if tag=='W' else cash_own)
                states[tag]['dividend_payable']=recv/(1-wminor if tag=='W' else cash_own)
        finance_after_upstream(states['P'],erows['P'],0. if cash_delay else wp+en)
        failed=any(r['failed'] for r in erows.values())
        proposed=(.60 if t==1 else 0.)*(shares-stock)
        desired=max(proposed,.38*max(0.,erows['P']['net_income']+wp+en)) if t<=5 else max(0.,states['P']['cash']-erows['P']['minimum_cash'])*min(1.,.40+.1*(t-5))
        pd=0. if failed else distribute(states['P'],erows['P'],desired)
        close(states['P']['cash'],erows['P']['cash_before_financing']+erows['P']['borrow']-pd)
        per=pd/(shares-stock)
        # Parent legal net-income budget includes subsidiary declarations, not principal recovery.
        plni=erows['P']['net_income']+wp+en+exchange_gain-exchange_tax
        plegal+=plni-pd-pb+erows['P']['noncash_comp']
        for tag in states:
            ss=states[tag]
            assets=sum(ss[x] for x in ('cash','financial','restricted','investments','fixed','working','dividend_receivable'))
            liabilities=ss['bank']+ss['bond']+ss.get('dividend_payable',0.)
            close(assets-liabilities,ss['equity'])
            erows[tag]['balance_residual']=assets-liabilities-ss['equity']
            erows[tag]['closing']=copy.deepcopy(ss)
        yearly=dict(year=t,state_bridge=dict(opening=annual_opening,pre_flow=pre_flow,events=dict(internal_face_change=internal-prior_face,previous_w_dividend_paid=oldpq/(1-wminor) if cash_delay and t>1 else 0.,previous_e_dividend_paid=old_epay if cash_delay and t>1 else 0.,exchange_face_extinguished=FACE if exchanged else 0.,exchange_equity_adjustment=FACE-exchange_tax if exchanged else 0.,exchange_RE_adjustment=exchange_gain-exchange_tax if exchanged else 0.)),anniversary=2026+t,ccl_volume_million_m2=area if method=='A' else None,ccl_basket_unit_revenue=price if method=='A' else None,pcb_volume_million_m2=earea if method=='A' else None,pcb_basket_unit_revenue=eprice if method=='A' else None,entities=erows,economic_ownership_e=own,dividend_ownership_e=cash_own,minority_cash=minor,
            parent_legal_equity_budget=plegal,parent_legal_net_income_budget=plni,declared_w=wp,declared_e=en,
            collected_previous_dividends=oldpq+oldeq,dividend_receivable=pq+eq,exchange_stake=exchanged,
            exchange_gain_budget=exchange_gain,exchange_tax_cash=exchange_tax,issued_shares=shares,treasury_shares=stock,
            electronic_treasury_shares=estock,fully_diluted_shares=shares,holder_cash=pd,holder_per_share=per,
            consolidated_equity_budget=sum(states[x]['equity'] for x in states),minority_equity_budget=wminor*states['W']['equity']+(1-own)*states['E']['equity'],common_equity_budget=states['P']['equity']+(1-wminor)*states['W']['equity']+own*states['E']['equity'],internal_trade_face=internal,internal_principal_collected=prior_face-internal,internal_principal_profit=0.,discount_factor=(1+k)**(-t),pv=per/(1+k)**t,failed=failed)
        rows.append(yearly)
        if t<=5:dist.append(per)
        totalpv+=yearly['pv']
        if t>5:laterpv+=yearly['pv']
        if failed:break
    return dict(name=name,method=method,asof=ASOF,parameters=dict(margin_shift=margin_shift,k=k,cyclic=cyclic,structural=structural,upside=upside,cash_delay=cash_delay,exchange=exchange,credit_failure=credit_failure,high_tax=high_tax,years=years,shift_start=shift_start),
        opening_operating_bridge=bridge,known_capital_bridge=known_capital,status='financing_failed' if failed else 'conditional_budget',value_per_share=None if failed else totalpv,
        distributions=dist,year5_continuation=None if failed else laterpv*(1+k)**5,
        terminal_pv_fraction=None if failed or not totalpv else laterpv/totalpv,
        rows=rows,last_year_pv=rows[-1]['pv'],tail_pv_ratio=(rows[-1]['pv']/rows[-2]['pv'] if len(rows)>1 and rows[-2]['pv'] else None))
