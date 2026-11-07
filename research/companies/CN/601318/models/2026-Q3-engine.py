#!/usr/bin/env python3
"""Ping An ordinary-owner model. stdlib only; CNY billion, shares billion.
No prices. Each period is one prospective year from information cutoff.
Life EV/NBV are alternative appraisal diagnostics, never added to cash DDM.
"""
import json, math, copy
from pathlib import Path
SH=18.107641995
OWN_L=.945 # group-attributable OP / total life OP rounded from Q3
OWN_P=.9955
OWN_B=.5796
BASE=dict(new_csm=46.,new_growth=.035,csm_release=.086,csm_interest=.029,
          life_inv=23.,life_other=17.,life_tax=.10,life_min_growth=.03,
          pc_cor=.96,pc_growth=.035,pc_invest=7.,bank_roe=.105,bank_rwa_growth=.03,
          other_roe=.055,other_growth=.02,cost=.105,g=.02,convert=True,
          haircut=0.,shock=0.,structural=False,delay=0.,strategic=[10.,8.,6.,4.,4.],
          remission=.42,release=.20,liquid_buffer=20.)

def present(cash,r,terminal=0.):
    return sum(x/(1+r)**(i+1) for i,x in enumerate(cash))+terminal/(1+r)**len(cash)

def projection(p):
    # Q3 CSM not disclosed: H1 balance 737.775 plus Q3 estimated new 7.4,
    # interest 5.3, release 16.4 -> 734.1. No favourable assumption revision.
    own_l=p.get('life_claim_ratio',OWN_L)
    csm=734.1; lc=803.36; la=1094.210; lm=583.271
    pc=120.219; pa=159.161; pm=73.369
    bb=476.701; bc=466.076; rwa=4851.049
    ob=137.178 # H1 asset management + empowerment attributable net assets
    cash=(78.338-7.29862537376)-p.get('liquidity_haircut',0.); legal=112.050; shares=SH; equity=1044.366
    retained_l=0.; retained_p=0.; parent_debt=26.985; new_debt=0.; receivable=0.
    legal_l=legal_p=legal_b=legal_o=0.; reserve_l=reserve_p=reserve_b=reserve_o=0.; indirect_bank_cash=0.; ev_cohorts=[]; rows=[]
    for t in range(1,p.get('horizon',80)+1):
        opening_cash=cash; opening_legal=legal; opening_eq=equity
        cy=(t<=3 and p['shock']>0)
        factor=(1-p['shock']*[1,.65,.25][t-1]) if cy else 1.
        # Structural hypothesis permanently weaker product economics, no recovery.
        grow=p['new_growth'] if t<=10 else p['g']
        new=p['new_csm']*(1+grow)**(min(t,10)-1)
        if t>10:new=p['new_csm']*(1+p['new_growth'])**9*(1+p['g'])**(t-10)
        new*=factor
        release=(csm*(1+p['csm_interest'])+new)*p['csm_release']
        csm=csm*(1+p['csm_interest'])+new-release
        # Historical baseline investment income includes all original invested capital;
        # only cumulative NEW retained capital earns additional 2.5% here.
        scale=(1+p['g'])**max(0,t-10)
        lp=(release+p['life_other']*scale+p['life_inv']*scale+.025*retained_l)*(1-p['life_tax'])
        loss=p['haircut'] if t==1 else 0.
        if p.get('ev_emergence'):
            # Independent actuarial income emergence, not calibrated to CSM/DDM.
            # Attributable VIF is converted to level economic earnings at the
            # disclosed 8.5% actuarial discount rate over 30 years. New NBV
            # creates 15-year earnings cohorts, not immediate cash income.
            inv_drop=(.04-(.035 if p['life_inv']<23 else .0375))/.005
            rate=.085; old_vif=541.854-10.-150.712*inv_drop
            old_years=p.get('ev_old_years',30); new_years=p.get('ev_new_years',15)
            old_income=(old_vif*rate/(1-(1+rate)**-old_years) if t<=old_years else 0.)
            nbv=34.*(1-.16844*inv_drop)*(1+p['new_growth'])**min(t,10)*max(0.,(20-t)/10 if t>10 else 1.)
            ev_cohorts.append((t,nbv*rate/(1-(1+rate)**-new_years)))
            new_income=sum(v for born,v in ev_cohorts if 0<=t-born<new_years)
            nav_income=(428.985-476.701*.084)*(.035 if p['life_inv']<23 else .0375)*scale
            lp=(old_income+new_income+nav_income)/own_l+.025*retained_l
        lp=lp*factor-loss
        lg=p['life_min_growth'] if t<=10 else p['g']; lm*=1+lg
        capreq=max(1.35*lm-lc,1.80*lm-la,0.)
        inj=max(0.,capreq-lp)
        # Parent injects on solvency shortfall; economic effect not an extra loss.
        lc+=lp+inj; la+=lp+inj; appropr_l=min(.10*max(0.,lp+min(legal_l,0.)),max(0.,18.0013215855-reserve_l));reserve_l+=appropr_l;legal_l+=lp-appropr_l
        extra=max(0.,min(lc-1.35*lm,la-1.80*lm)-44.322*scale)
        target=p['remission']+min(max(t-5,0),5)*.055
        lr=min(max(0.,target*lp+(p['release']*extra if t>5 else 0.)),
               max(0.,lc-1.35*lm),max(0.,la-1.80*lm),max(0.,legal_l))
        lc-=lr;la-=lr;legal_l-=lr;retained_l+=lp+inj-lr
        prem=350.7*(1+p['pc_growth'])**min(t,10)*(1+p['g'])**max(0,t-10)
        cor=p['pc_cor']+.025*(1-factor)
        pp=(prem*(1-cor)+p['pc_invest']*scale-3.0*scale+.025*retained_p)*.80
        if cy:pp-=p['shock']*10
        pm*=1+(p['pc_growth'] if t<=10 else p['g'])
        pi=max(0.,max(1.5*pm-pc,2.*pm-pa)-pp)
        pc+=pp+pi;pa+=pp+pi;appropr_p=min(.10*max(0.,pp+min(legal_p,0.)),max(0.,10.5-reserve_p));reserve_p+=appropr_p;legal_p+=pp-appropr_p
        pe=max(0.,min(pc-1.5*pm,pa-2*pm)-10.22*scale)
        pr=min(max(0.,(.35+min(max(t-5,0),5)*.07)*pp+(p['release']*pe if t>5 else 0.)),max(0.,pc-1.5*pm),max(0.,pa-2*pm),max(0.,legal_p))
        pc-=pr;pa-=pr;legal_p-=pr;retained_p+=pp+pi-pr
        roe=p['bank_roe']-(.035*(1-factor))
        operating_bank_equity=min(bb,rwa*(476.701/4851.049))
        bp=operating_bank_equity*roe+max(0.,bb-operating_bank_equity)*.025 # surplus earns cash yield, not banking ROE
        rwa*=1+(p['bank_rwa_growth'] if t<=10 else p['g'])
        bi=max(0.,.095*rwa-(bc+bp));bb+=bp+bi;bc+=bp+bi;appropr_b=min(.10*max(0.,bp+min(legal_b,0.)),max(0.,9.702959099-reserve_b));reserve_b+=appropr_b;legal_b+=bp-appropr_b
        br=min(max(0.,(.30+min(max(t-5,0),5)*.07)*bp+(p['release']*max(0.,bc-.095*rwa-5.) if t>5 else 0.)),max(0.,bc-.095*rwa),max(0.,legal_b))
        bb-=br;bc-=br;legal_b-=br
        op=ob*p['other_roe']*factor
        oi=p['strategic'][t-1] if t<=5 else 2.*(1+p['g'])**(t-6)
        # Strategic capex/capital injections buy yielding assets; not discarded or released at TV.
        appropr_o=min(.10*max(0.,op+min(legal_o,0.)),max(0.,10.-reserve_o));reserve_o+=appropr_o;legal_o+=op-appropr_o
        ore=min(max(0.,legal_o),max(0.,op-ob*p['other_growth'])); ob+=op+oi-ore;legal_o-=ore
        # Bank 49.56% is direct mother holding. The indirect group interest must pass
        # through life legal entities; no second booking of bank profit.
        # Receipt is statutory income at the intermediary, but NOT group income
        # or fresh solvency capital: the bank investment becomes cash. No bank
        # retained earnings are credited to life capital (conservative double-
        # gearing exclusion). Both payout routes share the SAME capital ceiling.
        indirect_received=br*(OWN_B-.4956)
        holder_income=indirect_received/.9954
        holder_appropr=min(.10*max(0.,holder_income+min(legal_l,0.)),max(0.,18.0013215855-reserve_l))
        reserve_l+=holder_appropr; legal_l+=holder_income-holder_appropr
        indirect_bank_cash+=indirect_received
        # Re-open the provisional insurance payout and allocate the common
        # legal/capital budget pro rata across both routes, not insurance-first.
        # This prevents lawful transit cash from being permanently subordinated.
        lc+=lr;la+=lr;legal_l+=lr;retained_l+=lr
        desired_indirect=indirect_bank_cash*p.get('indirect_up_rate',.8)/.9954
        total_desired=lr+desired_indirect
        joint_paid=min(total_desired,max(0.,lc-1.35*lm),max(0.,la-1.8*lm),max(0.,legal_l))
        weight=joint_paid/total_desired if total_desired else 0.
        lr*=weight;gross_indirect=desired_indirect*weight
        indirect_up=gross_indirect*.9954
        indirect_bank_cash-=indirect_up
        lc-=lr+gross_indirect;la-=lr+gross_indirect;legal_l-=lr+gross_indirect
        retained_l-=lr+gross_indirect
        declared=lr*own_l+pr*OWN_P+br*.4956+indirect_up+ore
        injections=inj*own_l+pi*OWN_P+bi*OWN_B+oi
        delayed=declared*p['delay'] if t<=2 else 0.
        received=declared-delayed+receivable;receivable=delayed
        redemption=0.; conversion_equity=0.; settlement_gain=0.
        if p['convert']:
            if t==1:
                shares+=1.05 # 0.938633367 contractual now + future antidilution budget
                conversion_equity=41.244 # Q3 bonds + derivative removed; no new cash
        else:
            if t==1:redemption=p.get('cash_settlement',25.2)
            if t==2 and not p.get('cash_settlement'):redemption=10.824
            if redemption:
                carrying=41.244 if p.get('cash_settlement') else 41.244*redemption/36.024
                settlement_gain=carrying-redemption
        parent_income=.025*cash-2.3*scale-.035*(parent_debt+new_debt)
        loan_runoff=min(parent_debt,26.985/5) if p.get('loan_runoff') and t<=5 else 0.
        parent_debt-=loan_runoff
        cash+=received+parent_income-injections-redemption-loan_runoff
        # Legal net income follows declared dividends, not collection of old receivable.
        legal+=declared+parent_income+settlement_gain
        desired=(2.70*(1.02)**(t-1)*shares if t<=5 else max(0.,received+parent_income-injections)+p['release']*max(0.,cash-p['liquid_buffer']*scale))
        finance=max(0.,p['liquid_buffer']*scale-cash)
        # Recoverable financing uses parent bonds/loans, not invented equity. Subsequent
        # surplus first repays debt before discretionary shareholder distribution.
        cash+=finance;new_debt+=finance
        repay=min(new_debt,max(0.,cash-p['liquid_buffer']*scale-(desired if t<=5 else 0.)))
        cash-=repay;new_debt-=repay
        div=min(max(0.,desired),max(0.,cash-p['liquid_buffer']*scale),max(0.,legal))
        cash-=div;legal-=div
        profit=lp*own_l+pp*OWN_P+bp*OWN_B+op+parent_income+settlement_gain
        equity+=profit-div+conversion_equity
        assert abs(cash-(opening_cash+received+parent_income-injections-redemption-loan_runoff+finance-repay-div))<1e-7
        assert abs(legal-(opening_legal+declared+parent_income+settlement_gain-div))<1e-7
        assert abs(equity-(opening_eq+profit-div+conversion_equity))<1e-7
        assert min(lc/lm-1.35,la/lm-1.8,pc/pm-1.5,pa/pm-2.,bc/rwa-.095)>-1e-9
        assert min(cash,legal,div)>-1e-9
        assert new_debt<30. # stressed refinancing budget capped at CNY30bn
        rows.append(dict(year=t,csm=csm,new_csm=new,csm_release=release,life_profit=lp,
           life_min=lm,life_core=lc,life_actual=la,life_remit=lr,pc_profit=pp,pc_min=pm,pc_core=pc,pc_remit=pr,
           life_legal=legal_l,pc_legal=legal_p,bank_legal=legal_b,life_reserve=reserve_l,pc_reserve=reserve_p,bank_reserve=reserve_b,indirect_bank_cash=indirect_bank_cash,indirect_bank_up=indirect_up,indirect_bank_received=indirect_received,indirect_holder_statutory_income=holder_income,indirect_holder_reserve=holder_appropr,bank_profit=bp,bank_common_equity=bb,bank_rwa=rwa,bank_cet1=bc,bank_remit=br,
           other_equity=ob,other_profit=op,other_remit=ore,strategic_investment=oi,
           group_profit=profit,parent_declared=declared,parent_received=received,parent_receivable=receivable,
           capital_injections=injections,parent_income=parent_income,parent_cash=cash,parent_legal=legal,
           normal_loan_repaid=loan_runoff,normal_parent_debt=parent_debt,redemption=redemption,settlement_gain=settlement_gain,new_borrowing=finance,debt_repaid=repay,extra_debt=new_debt,
           conversion_equity=conversion_equity,shares=shares,dividend=div,dps=div/shares,equity=equity))
    d=[x['dps'] for x in rows]; tail=d[-1]*(1+p['g'])/(p['cost']-p['g'])
    value=present(d,p['cost'],tail);tv5=present(d[5:],p['cost'],tail)
    # Same ordinary-holder realizability bridge in residual-income form.
    # Opening book and conversion are not additive windfalls: use fully
    # converted opening book, then clean-surplus earnings and terminal book
    # subtraction. Terminal value is ONLY continuation of permitted dividends.
    initial_book=1044.366+(41.244 if p['convert'] else 0.)
    old=initial_book; residual=[]
    for row in rows:
        clean_earnings=row['equity']-old+row['dividend']
        residual.append((clean_earnings-p['cost']*old)/row['shares'])
        old=row['equity']
    residual_value=initial_book/rows[0]['shares']+present(residual,p['cost'],tail-old/rows[-1]['shares'])
    assert abs(residual_value-value)<1e-7
    return dict(realizable_residual_value=residual_value,residual_terminal_book_deduction=old/rows[-1]['shares'],value=value,tv5=tv5,distributions=d[:5],tail80_pv=tail/(1+p['cost'])**len(rows),
                tv5_pv_share=tv5/(1+p['cost'])**5/value,rows=rows,params=p)

def appraisal(p):
    # Independent actuarial appraisal, Q3 group common book replaces H1 book.
    # Life EV adjustment = 970.839 - 428.985; other EV adjustment -2.138.
    # Q3 estimated run-off of VIF adjustment 10 bn; varied separately.
    investment_drop=(.04-(.035 if p['life_inv']<23 else .0375))/.005
    ev=1044.366+(970.839-428.985)-2.138-10.-150.712*investment_drop
    # 10-year new-business franchise followed by 10-year linear decay, not infinite NBV.
    nbv=34.*(1-.16844*investment_drop)
    franchise=sum(nbv*(1+p['new_growth'])**min(i,10)*max(0.,(20-i)/10 if i>10 else 1)/(1+p['cost'])**i for i in range(1,21))
    # Ordinary bank NAV already included, replace at justified PB.
    banknav=476.701*OWN_B
    bank_adj=banknav*((p['bank_roe']-p['g'])/(p['cost']-p['g'])-1)
    # Other low-return capital gets a finite 10-year excess-return correction, not written off.
    other_adj=sum(137.178*(p['other_roe']-p['cost'])/(1+p['cost'])**i for i in range(1,11))
    if p['convert']:ev+=41.244
    return dict(value=(ev+franchise+bank_adj+other_adj)/(SH+(1.05 if p['convert'] else 0)),adjusted_ev=ev,franchise=franchise,bank_adjustment=bank_adj,other_adjustment=other_adj)

def main():
    cases={}
    variants={'base':{},'core_low':dict(new_csm=42.,new_growth=.02,life_inv=18.,bank_roe=.10,pc_cor=.965,cost=.11),
      'core_high':dict(new_csm=50.,new_growth=.045,life_inv=26.,bank_roe=.11,pc_cor=.955,cost=.10),
      'cyclical':dict(shock=.30,haircut=35.,delay=.20),
      'structural':dict(new_csm=32.,new_growth=-.015,life_inv=8.,life_other=14.,bank_roe=.08,pc_cor=.985,other_roe=.025,life_min_growth=.035,bank_rwa_growth=.035,cost=.115,g=.01,haircut=80.,structural=True,strategic=[8.,6.,4.,2.,2.]),
      'optimistic':dict(new_csm=58.,new_growth=.06,life_inv=30.,bank_roe=.115,pc_cor=.95,other_roe=.07,cost=.10),
      'ev_bridge_base':dict(ev_emergence=True),'ev_bridge_low':dict(ev_emergence=True,new_csm=42.,new_growth=.02,life_inv=18.,bank_roe=.10,pc_cor=.965,cost=.11),'ev_bridge_high':dict(ev_emergence=True,new_csm=50.,new_growth=.045,life_inv=26.,bank_roe=.11,pc_cor=.955,cost=.10),'ev_bridge_slow':dict(ev_emergence=True,release=.10,indirect_up_rate=.5),'ev_bridge_long':dict(ev_emergence=True,ev_old_years=40,ev_new_years=20),'ev_bridge_short':dict(ev_emergence=True,ev_old_years=20,ev_new_years=10),'base_120_years':dict(horizon=120),'base_180_years':dict(horizon=180),'low_180_years':dict(new_csm=42.,new_growth=.02,life_inv=18.,bank_roe=.10,pc_cor=.965,cost=.11,horizon=180),'high_180_years':dict(new_csm=50.,new_growth=.045,life_inv=26.,bank_roe=.11,pc_cor=.955,cost=.10,horizon=180),'life_claims92pct':dict(life_claim_ratio=.92),'life_claims97pct':dict(life_claim_ratio=.97),'normal_loan_runoff':dict(loan_runoff=True),'cash_settlement80':dict(convert=False,cash_settlement=80.),'cash_settlement120':dict(convert=False,cash_settlement=120.),'cash_redemption':dict(convert=False),'higher_capital':dict(life_min_growth=.05,bank_rwa_growth=.05),
      'slow_release':dict(release=.10),'delayed_remit':dict(delay=.50),'higher_reinvestment':dict(strategic=[20.,20.,15.,12.,10.]),'liquidity_unavailable20':dict(liquidity_haircut=20.,convert=False),'indirect_bank_slow':dict(indirect_up_rate=.5),
      'sensitivity_investment_minus5':dict(life_inv=18.),'sensitivity_cost_plus1':dict(cost=.115)}
    for name,v in variants.items():
        p=BASE|v;cases[name]=projection(p);cases[name]['appraisal']=appraisal(p) if name in ('base','core_low','core_high') else None
    # Hand-computable cases call the exact valuation chain used above.
    assert abs(present([10.]*5,.1,100.)-100.)<1e-10
    assert abs(present([0.,121.],.1)-100.)<1e-10
    for q in cases.values():
        assert abs(present(q['distributions'],q['params']['cost'],q['tv5'])-q['value'])<1e-8
    # Hand-computable perturbations use the FULL formal projection chain, not
    # a second discounting identity: same declaration, collection only delayed.
    hand_base=projection(BASE)
    hand_delay=projection(BASE|{'delay':.5})
    hand_injection=projection(BASE|{'strategic':[20.,8.,6.,4.,4.]})
    a=hand_base['rows'][0];d=hand_delay['rows'][0];j=hand_injection['rows'][0]
    assert abs(a['parent_cash']-d['parent_cash']-.5*a['parent_declared'])<1e-8
    assert abs(a['parent_legal']-d['parent_legal'])<1e-8
    assert abs(d['parent_receivable']-.5*a['parent_declared'])<1e-8
    assert abs(a['parent_cash']-j['parent_cash']-10.)<1e-8
    assert abs(a['parent_legal']-j['parent_legal'])<1e-8
    assert abs(j['other_equity']-a['other_equity']-10.)<1e-8
    assert abs(j['group_profit']-a['group_profit'])<1e-8
    assert abs(j['equity']-a['equity'])<1e-8
    # Contractual bank ordinary capital and source-unit arithmetic.
    assert 556.701-80.==476.701
    tests={'delay50pct_cash_delta':a['parent_cash']-d['parent_cash'],
      'delay50pct_independent_expected':.5*a['parent_declared'],
      'delay50pct_legal_delta':a['parent_legal']-d['parent_legal'],
      'extra10_injection_cash_delta':a['parent_cash']-j['parent_cash'],
      'extra10_injection_profit_delta':j['group_profit']-a['group_profit'],
      'extra10_injection_group_equity_delta':j['equity']-a['equity']}
    out=dict(projection_hand_tests=tests,units='CNY billion; shares billion; per share CNY',cases=cases,hand_tests={'level_10_per_year_terminal100_at10pct':present([10.]*5,.1,100.),'121_in_year2_at10pct':present([0.,121.],.1)})
    print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
