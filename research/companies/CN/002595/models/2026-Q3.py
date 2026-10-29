#!/usr/bin/env python3
"""Himile 2026Q3; CNY billions except per share. Pure stdlib, standalone.
Run: python model.py > output.json. Rolling years after 2026-10-28.
The valuation chain is dividends + 10y continuation; all cash stays on balance sheet
until actually distributed; financing is never raised to pay discretionary dividends.
"""
import json,copy,math
SHARES=1.16
OPEN={'cash_parent':.57976271516,'cash_sub':1.04693782226-.57976271516,
      'parent_re':9.98198718724,'reserve':.4,'sub_re':1.0,'debt':.23938569609,
      'loan':.43,'associate':.07485824473,'minority':.00964602093,'wc':6.05,'capital':12.35}

def business(s='base',gm_shift=0,wc_shift=0):
    rev=[6.5,4.3,.8,.9]; out=[]; oldwc=OPEN['wc']; capital=OPEN['capital']; lastnop=None
    gr=[[.08,.08,.07,.06,.05],[.12,.12,.10,.08,.06],[.15,.15,.12,.10,.08],[.10,.10,.08,.06,.05]]
    for t in range(1,11):
        if t<=5:
            growth=[gr[i][t-1] for i in range(4)]
            gm=[.365+min(t-1,2)*.005,.20+min(t-1,3)*.01,.30,.33]
            capex=[1.6,1.6,1.5,1.3,1.2][t-1]; dep=[.45,.52,.60,.68,.75][t-1]
        else:
            growth=[{6:.05,7:.045,8:.04,9:.035,10:.03}[t]]*4
            gm=[.375,.23,.30,.33]; dep=.75*(1.04**(t-5)); capex=0
        ratio=.49+wc_shift; fee=.098; cashratio=.064
        if s=='cycle':
            if t<=2:growth=[-.10,-.12,-.20,-.12] if t==1 else [0,0,0,0];gm=[.33,.16,.24,.27];ratio=.55
            elif t<=5:growth=[.10,.14,.15,.12];gm=[.35+.008*(t-3),.19+.015*(t-3),.28,.31];ratio=.53-.01*(t-3)
            capex=([1.45,1.15,1.30,1.45,1.4][t-1] if t<=5 else capex); cashratio=.075
        elif s=='structural':
            growth=([-.15,-.20,-.25,-.15] if t==1 else ([-.03]*4 if t==2 else [.02]*4));gm=[.29,.14,.22,.25];fee=.105;ratio=.57;cashratio=.08
            capex=([1.4,1.15,1.0,.9,.9][t-1] if t<=5 else capex)
        elif s=='upside':
            if t<=5:growth=[x+.035 for x in growth];gm=[.39,.25,.34,.36];ratio=.46
            else:gm=[.39,.25,.34,.36];ratio=.46
            capex=(capex+.20 if t<=5 else capex)
        rev=[v*(1+g) for v,g in zip(rev,growth)];total=sum(rev)
        gross=sum(v*(m+gm_shift) for v,m in zip(rev,gm));ebit=gross-fee*total
        nopat=ebit*.85;wc=total*ratio
        # Structural losses: 0.30bn of old receivables cannot release cash. Only once.
        impairment=.30 if s=='structural' and t==1 else 0
        dwc=wc-oldwc+impairment
        needcash=total*cashratio
        oldneed=(12.5*.064 if t==1 else out[-1]['min_cash'])
        dcash=needcash-oldneed
        if t>5:
            roic=.16 if s=='base' else {'cycle':.14,'structural':.08,'upside':.19}[s]
            # Actual revenue-led growth includes profit structure, stable after year 5.
            netinvestment=max(0,(nopat-lastnop)/roic)
            capex=max(dep*1.05,dep+netinvestment-dwc-dcash)
        fcf=nopat+dep-capex-dwc
        capital+=capex-dep+dwc+dcash-impairment
        out.append(dict(year=t,segments=rev[:],revenue=total,gross_profit=gross,ebit=ebit,nopat=nopat,
                        dep=dep,capex=capex,maintenance_capex=dep*1.05,growth_capex=capex-dep*1.05,
                        wc=wc,delta_wc_cash=dwc,impairment=impairment,min_cash=needcash,
                        free_cash_before_interest=fcf,fcff=fcf-dcash,capital=capital,roic=nopat/capital))
        oldwc=wc;lastnop=nopat
    return out

def simulate(rows,opening,scenario='base',payout=.35,cash_yield=.01,parent_share=.80,sub_capex_share=.55,loan_recovery_year=1,loan_haircut=0,upstream_allowed=True):
    p=opening['cash_parent'];s=opening['cash_sub'];re=opening['parent_re'];reserve=opening['reserve'];sre=opening['sub_re'];debt=opening['debt'];loan=opening['loan'];out=[]
    for r in rows:
        t=r['year'];start=p+s;startdebt=debt;ps=p;ss=s
        minp=.625*r['min_cash'];mins=.375*r['min_cash']
        finp=max(0,p-minp)*cash_yield;fins=max(0,s-mins)*cash_yield
        loaninterest=loan*.063*.85*(.8 if t==1 else 1) if loan>0 else 0
        interest=debt*.04*.85
        principal=loan*(1-loan_haircut) if t==loan_recovery_year else 0
        loanloss=loan*loan_haircut if t==loan_recovery_year else 0
        if t==loan_recovery_year:loan=0
        # Cash-generating profits and cash accounting exclude noncash impairment tax credits.
        pc=(r['nopat']+r['dep']-r['delta_wc_cash'])*parent_share-r['capex']*(1-sub_capex_share)
        sc=r['free_cash_before_interest']-pc
        p+=pc+finp+loaninterest+principal-interest;s+=sc+fins
        pn=r['nopat']*parent_share+finp+loaninterest-interest-r['impairment']*.85-loanloss
        sn=r['nopat']*(1-parent_share)+fins
        loss_to_cover=max(0,-re)
        provision=min(max(0,.58-reserve),max(0,pn-loss_to_cover)*.10);reserve+=provision;re+=pn-provision;sre+=sn-max(0,sn)*.10
        injection=0;upstream=0;newdebt=0;repay=0
        # Parent capital injection/normal intercompany lending finances required sub investment.
        if s<mins:injection=mins-s;p-=injection;s+=injection
        # Only surplus cash backed by accumulated lawful profit can be upstreamed.
        upstream=min(max(0,s-mins),max(0,sre),max(0,minp-p)) if (upstream_allowed or t>5) else 0
        s-=upstream;p+=upstream;sre-=upstream;re+=upstream
        if p<minp:newdebt=minp-p;p+=newdebt;debt+=newdebt
        # Normal repayment follows cash generation, not forced acceleration.
        repay=min(debt,max(0,p-minp));p-=repay;debt-=repay
        common_profit=r['nopat']+finp+fins+loaninterest-interest-r['impairment']*.85-loanloss
        desired=max(0,common_profit)*payout
        if t>=6:desired=max(desired,max(0,r['free_cash_before_interest']-interest)*.8)+.2*max(0,start-r['min_cash'])
        needed=max(0,desired-(p-minp))
        extra=min(needed,max(0,s-mins),max(0,sre)) if (upstream_allowed or t>5) else 0;s-=extra;p+=extra;sre-=extra;re+=extra;upstream+=extra
        dividend=min(desired,max(0,p-minp),max(0,re));p-=dividend;re-=dividend
        assert p>=minp-1e-9 and s>=mins-1e-9 and sre>=-1e-9
        residual=(p+s)-(start+r['free_cash_before_interest']+finp+fins+loaninterest+principal-interest+newdebt-repay-dividend)
        assert abs(residual)<1e-8
        out.append(dict(**r,cash_start=start,cash_parent=p,cash_sub=s,cash_end=p+s,financial_income=finp+fins+loaninterest,
            interest=interest,loan_recovery=principal,loan_loss=loanloss,loan_end=loan,new_debt=newdebt,debt_repaid=repay,debt_end=debt,
            parent_operating_cash=pc,subs_operating_cash=sc,injection=injection,upstream=upstream,parent_profit=pn,
            parent_reserve=reserve,parent_re=re,subs_re=sre,desired_dividend=desired,dividend=dividend,dps=dividend/SHARES,
            cash_conservation_residual=residual))
    return out

def value(rows,r,g,terminal_roic,associate,minority,release_years=0):
    z=rows[-1];n=len(rows)
    # Steady-state capital maintenance plus growth fully funded, including working cash.
    steady=z['nopat']*(1+g)*(1-g/terminal_roic)
    operating=steady/(r-g)
    excess=max(0,z['cash_end']-z['min_cash'])
    # Parent and sub retained profits must each support the final cash release.
    assert z['parent_re']>=max(0,z['cash_parent']-.625*z['min_cash'])-1e-9
    assert z['subs_re']>=max(0,z['cash_sub']-.375*z['min_cash'])-1e-9
    # All modeled continuations are debt-free: FCFE equals operating FCFF.
    assert abs(z['debt_end'])<1e-9
    if release_years:
        cashvalue=sum((excess/release_years+(excess-excess*i/release_years)*.01)/(1+r)**(i+1) for i in range(release_years))
    else:cashvalue=excess
    bridge=cashvalue+z['loan_end']+associate-minority-z['debt_end']
    terminal=operating+bridge
    pvdiv=sum(x['dividend']/(1+r)**x['year'] for x in rows)
    pvt=terminal/(1+r)**n
    # Independently future year-5 equity includes years 6-10 distributions + year-10 state.
    y5=(sum(x['dividend']/(1+r)**(x['year']-5) for x in rows if x['year']>5)+terminal/(1+r)**(n-5))/SHARES
    return dict(value_per_share=(pvdiv+pvt)/SHARES,terminal_year5_per_share=y5,terminal_year10=terminal,
        terminal_operating_value=operating,terminal_cash_bridge=bridge,steady_fcfe=steady,pv_distributions=pvdiv,
        terminal_pv_share=pvt/(pvdiv+pvt),discount=r,growth=g,terminal_roic=terminal_roic)

def run():
    result={'units':'CNY billion, shares billion; per-share CNY','opening':OPEN,'cases':{}}
    specs={'base':(.10,.025,.16),'cycle':(.105,.025,.14),'structural':(.115,.01,.08),'upside':(.095,.03,.19)}
    for name,(r,g,roic) in specs.items():
        rows=simulate(business(name),OPEN,scenario=name,loan_haircut=.5 if name=='structural' else 0)
        result['cases'][name]={'rows':rows,'valuation':value(rows,r,g,roic,OPEN['associate']*(.5 if name=='structural' else 1),OPEN['minority'])}
    base=result['cases']['base']['rows']
    result['core']={str(r):value(base,r,.025,.16,OPEN['associate'],OPEN['minority']) for r in [.095,.105]}
    # Secondary normalised owner-earnings multiple on year-5 earning capacity; same cash bridge.
    z=base[4];fn=z['nopat']*1.025*(1-.025/.16)
    bridge=z['cash_end']-z['min_cash']+OPEN['associate']-OPEN['minority']-z['debt_end']+z['loan_end']
    result['secondary']={str(mult):(sum(x['dividend']/(1.10)**x['year'] for x in base[:5])+(fn*mult+bridge)/1.10**5)/SHARES for mult in [13,16]}
    result['sensitivity']={}
    for name,kw in [('gross_margin_minus_1pp',{'gm_shift':-.01}),('wc_ratio_plus_5pp',{'wc_shift':.05})]:
        rows=simulate(business(**kw),OPEN)
        result['sensitivity'][name]={'rows':rows,'valuation':value(rows,.10,.025,.16,OPEN['associate'],OPEN['minority'])}
    for name,kw in [('loan_renewal_to_year3',{'loan_recovery_year':3}),('parent_profit_share_65pct',{'parent_share':.65}),('cash_yield_zero',{'cash_yield':0}),('upstream_delayed_5years_parent_share_65pct',{'parent_share':.65,'upstream_allowed':False})]:
        rows=simulate(business(),OPEN,**kw);result['sensitivity'][name]={'rows':rows,'valuation':value(rows,.10,.025,.16,OPEN['associate'],OPEN['minority'])}
    zero_sub=copy.deepcopy(OPEN);zero_sub['sub_re']=0
    zero_rows=simulate(business(),zero_sub)
    result['sensitivity']['zero_opening_sub_distributable_profit']={'rows':zero_rows,'valuation':value(zero_rows,.10,.025,.16,OPEN['associate'],OPEN['minority'])}
    result['slow_cash_release_5years']=value(base,.10,.025,.16,OPEN['associate'],OPEN['minority'],release_years=5)
    # Hand-computable fixture uses the SAME simulate and value functions as formal paths.
    fixture=[dict(year=t,nopat=1.,dep=.2,capex=.2,delta_wc_cash=0.,impairment=0.,min_cash=0.,free_cash_before_interest=1.) for t in range(1,11)]
    op=dict(cash_parent=0.,cash_sub=0.,parent_re=100.,reserve=.58,sub_re=0.,debt=0.,loan=0.)
    check=simulate(fixture,op,payout=1.,cash_yield=0,parent_share=1.,sub_capex_share=0)
    v=value(check,.10,0,.10,0,0)
    assert all(abs(x['dividend']-1)<1e-10 and abs(x['cash_end'])<1e-10 for x in check)
    assert abs(v['value_per_share']-10/SHARES)<1e-10
    lossop=dict(op,parent_re=-2.,reserve=.4)
    losscase=simulate(fixture,lossop,payout=1.,cash_yield=0,parent_share=1.,sub_capex_share=0)
    assert abs(losscase[0]['parent_re']+1)<1e-10 and losscase[0]['parent_reserve']==.4 and losscase[0]['dividend']==0
    assert abs(losscase[1]['parent_re'])<1e-10 and losscase[1]['parent_reserve']==.4 and losscase[1]['dividend']==0
    assert abs(losscase[2]['parent_reserve']-.5)<1e-10 and abs(losscase[2]['dividend']-.9)<1e-10
    result['loss_cover_formal_chain_case']=losscase[:3]
    result['formal_chain_hand_case']={'annual_dividend':1,'cash_end':0,'perpetuity_total_equity':10,'expected_per_share':10/SHARES,'actual':v}
    return result
if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False,indent=2))
