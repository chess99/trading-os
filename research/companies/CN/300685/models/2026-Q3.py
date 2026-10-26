"""CN300685 2026Q3; monetary unit CNY million; annual rolling years after cutoff.
Standalone deterministic owner cash model. No current price, weights or IRR.
"""
import json,copy,math
from pathlib import Path
SHARES=380.985869
INPUT={'revenue0':[870.,350.], 'growth':[.06,.09], 'margin':[.35,.25], 'tax':.15,
       'wc_ratio':.50,'capex_ratio':.045,'da_ratio':.025,'payout':.50,'deposit_yield':.018,
       'debt_rate':.03,'release_year':99,'term_maturity':1,'release_target':600.,
       'opening_cash':[1038.798788,100.,120.], 'term_deposit':[764.908373,0.,0.],
       'opening_debt':[150.242611,5.,5.], 'opening_legal':[1189.407493,0.,0.],
       'opening_reserve':[195.0525845,0.,0.], 'reserve_caps':[195.0525845,20.,10.],
       'profit_weights':[.92,.04,.04], 'cash_weights':[.90,.05,.05],
       'cash_floor':[180.,30.,30.], 'subs_upstream_start':99,'internal_interest':.03,
       'external_limit':0.,'equity_asset':53.,'old_intercompany':8.327219, 'terminal_release_delay':3,
       'extra_capex':[0,0,0,0,0], 'legal_profit_adjust':[0,0,0,0,0]}
def transfer(cash,source,target,amount):
    assert amount>=-1e-8 and cash[source]+1e-8>=amount
    cash[source]-=amount;cash[target]+=amount

def simulate(p):
    p=copy.deepcopy(p);cash=p['opening_cash'][:];term=p['term_deposit'][:];debt=p['opening_debt'][:]
    liquid=[c-t for c,t in zip(cash,term)]; legal=p['opening_legal'][:]; reserve=p['opening_reserve'][:]
    rev=p['revenue0'][:]; wc=p.get('opening_wc',sum(rev)*.50); rows=[]; loans=[p['old_intercompany']/2]*2
    outstanding_release=p['release_target'];
    for y in range(1,6):
        old_total=sum(liquid)+sum(term); old_loans=sum(loans)
        prev_rev=sum(rev)
        growth=p.get('growth_path',[p['growth']]*5)[y-1];margin=p.get('margin_path',[p['margin']]*5)[y-1]
        rev=[r*(1+g) for r,g in zip(rev,growth)]; sales=sum(rev)
        ebit=sum(r*m for r,m in zip(rev,margin));nopat=ebit*(1-p['tax'])
        new_wc=sales*p.get('wc_path',[p['wc_ratio']]*5)[y-1]
        da=sales*p['da_ratio'];capex=sales*p['capex_ratio']+p['extra_capex'][y-1]
        fcf=nopat+da-capex-(new_wc-wc);wc=new_wc
        fin=[(liquid[i]+term[i])*p['deposit_yield']*(1-p['tax']) for i in range(3)]
        interest=[d*p['debt_rate']*(1-p['tax']) for d in debt]
        profits=[nopat*w+fin[i]-interest[i] for i,w in enumerate(p['profit_weights'])]
        profits[0]+=p['legal_profit_adjust'][y-1]
        internal_interest=[l*p['internal_interest'] for l in loans]
        profits[0]+=sum(internal_interest)
        for i in (1,2): profits[i]-=internal_interest[i-1]
        assert abs(sum(profits)-(nopat+sum(fin)-sum(interest)+p['legal_profit_adjust'][y-1]))<1e-8
        for i in range(3):
            liquid[i]+=fcf*p['cash_weights'][i]+fin[i]-interest[i]
            # Losses remain in cumulative distributable balance; reserve only after loss absorbed.
            pre=legal[i];legal[i]+=profits[i]
            alloc=min(max(legal[i]-max(pre,0),0)*.10,max(p['reserve_caps'][i]-reserve[i],0))
            legal[i]-=alloc;reserve[i]+=alloc
            if y>=p['term_maturity']: liquid[i]+=term[i];term[i]=0
        for i in (1,2):
            pay=min(max(liquid[i],0),internal_interest[i-1]);transfer(liquid,i,0,pay)
            # Unpaid intercompany interest is retained as internal loan (cancel on consolidation).
            loans[i-1]+=internal_interest[i-1]-pay
        # Scheduled principal amortization: all old debt repaid over first three years.
        principal=[min(debt[i],p['opening_debt'][i]*([.10,.45,.45,0,0][y-1])) for i in range(3)]
        funding=0.;newloans=[0.,0.]
        for i in (1,2):
            need=max(principal[i]+p['cash_floor'][i]-liquid[i],0)
            available=max(liquid[0]-principal[0]-p['cash_floor'][0],0)
            lend=min(need,available);transfer(liquid,0,i,lend);loans[i-1]+=lend;newloans[i-1]=lend
        for i in range(3):
            need=max(principal[i]-liquid[i],0)
            borrow=min(need,p['external_limit']-funding)
            if borrow>0: debt[i]+=borrow;liquid[i]+=borrow;funding+=borrow
            if liquid[i]+1e-8<principal[i]: raise ValueError('Unfunded entity debt repayment, even with zero dividends')
            liquid[i]-=principal[i];debt[i]-=principal[i]
            if liquid[i]<-1e-8: raise ValueError('Unfunded entity operating deficit')
        upstream=[0.,0.];loan_repay=[0.,0.]
        for i in (1,2):
            repay=min(max(liquid[i]-p['cash_floor'][i],0),loans[i-1]);transfer(liquid,i,0,repay);loans[i-1]-=repay;loan_repay[i-1]=repay
            if y>=p['subs_upstream_start']:
                up=min(max(liquid[i]-p['cash_floor'][i],0),max(legal[i],0))
                transfer(liquid,i,0,up);legal[i]-=up;legal[0]+=up;upstream[i-1]=up
        # Dividend receipts only count once: new upstream profits above, old loan receipts have no legal profit.
        ordinary_target=max(sum(profits),0)*p['payout']
        ordinary=min(ordinary_target,max(legal[0],0),max(liquid[0]-p['cash_floor'][0],0))
        liquid[0]-=ordinary;legal[0]-=ordinary
        special=0.
        if y>=p['release_year']:
            special=min(outstanding_release,max(legal[0],0),max(liquid[0]-p['cash_floor'][0],0))
            liquid[0]-=special;legal[0]-=special;outstanding_release-=special
        expected=old_total+fcf+sum(fin)-sum(interest)+funding-sum(principal)-ordinary-special
        assert abs(sum(liquid)+sum(term)-expected)<1e-7
        assert min(liquid+term+debt)>=-1e-7
        rows.append(dict(year=y,revenue=rev[:],ebit=ebit,nopat=nopat,net_profit=sum(profits),fcf=fcf,
          da=da,capex=capex,wc=wc,cash=liquid[:],term=term[:],legal=legal[:],reserve=reserve[:],debt=debt[:],
          deposit_income=sum(fin),interest=sum(interest),principal=principal,external_funding=funding,
          internal_loans=loans[:],internal_interest=internal_interest,internal_new_funding=newloans,
          loan_repayment=loan_repay,subs_declared_and_paid=upstream,old_dividend_receipts=0.,
          ordinary=ordinary,special=special,distribution=ordinary+special,
          pending_release=outstanding_release,terminal_release_delay=p['terminal_release_delay'],cash_identity_error=sum(liquid)+sum(term)-expected))
    return rows

def operating_terminal(state,r,g=.025,fade_years=10,end_margin=.30,ic_ratio=.80):
    """At end of Y5, fade revenue growth and margin from actual Y5 state; no current cash.
    Reinvestment=(sales increase)*ic_ratio; includes working capital and net fixed capital.
    """
    rev=sum(state['revenue']);margin=state['ebit']/rev;growth0=state.get('terminal_growth0',.065)
    total=0.;flows=[];profits=[]
    for k in range(1,fade_years+1):
        growth=growth0+(g-growth0)*k/fade_years;newrev=rev*(1+growth)
        m=margin+(end_margin-margin)*k/fade_years;nop=newrev*m*.85
        reinvest=(newrev-rev)*ic_ratio;fcf=nop-reinvest
        total+=fcf/(1+r)**k;flows.append(fcf);profits.append(nop);rev=newrev
    stable_roic=end_margin*.85/ic_ratio
    perpetuity=nop*(1+g)*(1-g/stable_roic)/(r-g)
    return {'value':total+perpetuity/(1+r)**fade_years,'flows':flows,'profits':profits,'g':g,'stable_roic':stable_roic,
            'perpetuity_pv':perpetuity/(1+r)**fade_years}

def value(rows,r,g=.025,end_margin=.30,ic_ratio=.80,pe=20,equity_asset=53,terminal_growth0=.065):
    state=copy.deepcopy(rows[-1]);state['terminal_growth0']=terminal_growth0
    operating=operating_terminal(state,r,g,end_margin=end_margin,ic_ratio=ic_ratio)
    # Sub reserves are non-distributable; retain operating minimum, no automatic extra-cash access.
    excess=[max(state['cash'][i]+state['term'][i]-[180,30,30][i],0) for i in range(3)]
    cash=excess[:];legal=state['legal'][:];reserve=state['reserve'][:]
    caps=[195.0525845,20.,10.];loans=state['internal_loans'][:]
    # Strategic asset realization is parent cash, not a second operating earning.
    cash[0]+=equity_asset
    for i in range(3):
        if cash[i]+1e-8<state['debt'][i]:raise ValueError('Unfunded terminal debt')
        cash[i]-=state['debt'][i]
    release_schedule=[];financial=0.;immediate=[0.,0.,0.]
    def move_sub(i,amount):
        transfer(cash,i,0,amount);legal[i]-=amount;legal[0]+=amount
    # Existing internal principal repayment never creates parent distributable profit.
    for i in (1,2):
        repay=min(cash[i],loans[i-1]);transfer(cash,i,0,repay);loans[i-1]-=repay
        up=min(cash[i],max(legal[i],0));move_sub(i,up);immediate[i]=up
    paid=min(cash[0],max(legal[0],0));cash[0]-=paid;legal[0]-=paid
    financial+=paid;immediate[0]=paid-sum(immediate[1:])
    release_schedule.append({'years_after_y5':0,'paid':paid,'parent_legal_after':legal[0],
                             'subs_actual_dividend':immediate[1:],'cash_remaining':cash[:]})
    # Tail future FCF is already in operating value. Pay it once, then separately trace
    # delayed old financial principal and its interest through each legal entity.
    for k in range(1,1001):
        if sum(cash)<1e-8 and sum(loans)<1e-8:break
        before=sum(cash);fin=[x*.0153 for x in cash]
        n=len(operating['flows']);scale=(1+operating['g'])**max(k-n,0)
        flow=operating['flows'][min(k-1,n-1)]*scale
        profit=operating['profits'][min(k-1,n-1)]*scale
        weights=[.92,.04,.04];inter=[x*.03 for x in loans]
        for i in range(3):
            np=profit*weights[i]+fin[i]+(sum(inter) if i==0 else -inter[i-1])
            old=legal[i];legal[i]+=np
            provision=min(max(legal[i]-max(old,0),0)*.10,max(caps[i]-reserve[i],0))
            reserve[i]+=provision;legal[i]-=provision
            cash[i]+=flow*weights[i]+fin[i]
        for i in (1,2):
            if cash[i]+1e-8<inter[i-1]:raise ValueError('Unfunded terminal internal interest')
            transfer(cash,i,0,inter[i-1])
            repay=min(max(cash[i]-flow*weights[i],0),loans[i-1]);transfer(cash,i,0,repay);loans[i-1]-=repay
            # Ordinary operating dividend must really be legal; do not silently overvalue it.
            normal=flow*weights[i]
            if min(cash[i],max(legal[i],0))+1e-8<normal:raise ValueError('Tail operating dividend legally constrained')
            move_sub(i,normal)
        if min(cash[0],max(legal[0],0))+1e-8<flow:raise ValueError('Parent tail operating dividend constrained')
        cash[0]-=flow;legal[0]-=flow
        up=[0.,0.]
        if k>=state['terminal_release_delay']:
            for i in (1,2):
                amount=min(cash[i],max(legal[i],0));move_sub(i,amount);up[i-1]=amount
            special=min(cash[0],max(legal[0],0));cash[0]-=special;legal[0]-=special
        else:special=0.
        assert min(cash)>=-1e-7 and abs(sum(cash)-(before+sum(fin)-special))<1e-6
        financial+=special/(1+r)**k
        release_schedule.append({'years_after_y5':k,'paid':special,'subs_actual_dividend':up,
          'parent_legal_after':legal[0],'cash_remaining':cash[:],'legal':legal[:],'reserve':reserve[:]})
    if sum(cash)>1e-7 or sum(loans)>1e-7:raise ValueError('Terminal principal not legally released; no arbitrary residual value')
    legal_now=immediate
    tv=operating['value']+financial
    dpv=sum(x['distribution']/(1+r)**x['year'] for x in rows)
    current=(dpv+tv/(1+r)**5)/SHARES
    second=(dpv+(state['nopat']*pe+financial)/(1+r)**5)/SHARES
    return dict(per_share=current,method2=second,terminal_per_share=tv/SHARES,distribution_pv=dpv,
                terminal_operating=operating,terminal_financial=financial,terminal_excess_by_entity=excess,terminal_immediate_legal_release=legal_now,terminal_deferred_release=release_schedule,
                terminal_pv_share=(tv/(1+r)**5)/(dpv+tv/(1+r)**5))

def scenarios():
    d={}; base=simulate(INPUT)
    d['base']={'inputs':INPUT,'rows':base,'low':value(base,.095,.02,.29,.85,18),
      'high':value(base,.085,.025,.31,.75,22), 'mid':value(base,.09)}
    for name,updates in {
       'cyclical':{'growth_path':[[-.06,0],[.02,.04],[.10,.12],[.08,.10],[.06,.09]],'margin_path':[[.31,.21],[.33,.23],[.35,.25],[.35,.25],[.35,.25]],'wc_path':[.60,.57,.54,.52,.50]},
       'structural':{'growth':[.0,.04],'margin':[.25,.20],'wc_ratio':.60,'capex_ratio':.055},
       'upside':{'growth':[.09,.13],'margin':[.36,.28],'wc_ratio':.48,'capex_ratio':.05},
       'release_year3':{'release_year':3},'release_year5':{'release_year':5},'term_lock3':{'term_maturity':3},'term_lock5':{'term_maturity':5},
       'upstream_year3':{'subs_upstream_start':3},'terminal_release5':{'terminal_release_delay':5},'parent_cash_minus150':{'opening_cash':[888.798788,175.,195.]},
       'margin_minus2pp':{'margin':[.33,.23]}}.items():
        p=copy.deepcopy(INPUT);p.update(updates)
        try:
            rows=simulate(p)
            kw={'g':.015,'end_margin':.23,'ic_ratio':1.,'terminal_growth0':.025} if name=='structural' else ({'g':.025,'end_margin':.32,'terminal_growth0':.09} if name=='upside' else ({'end_margin':.28} if name=='margin_minus2pp' else {}))
            d[name]={'changed':updates,'effective_year':{'release_year3':3,'release_year5':5,'upstream_year3':3,'term_lock3':3,'term_lock5':5,'terminal_release5':10}.get(name,1),
                     'timing_note':('Earliest deferred financial principal release is year 5 + 5; base is year 5 + 3' if name=='terminal_release5' else 'margin_minus2pp changes years1-5 and the entire post-year5 margin fade/steady state' if name=='margin_minus2pp' else 'Deposit-lock scenarios change availability from year1; stated effective year is actual maturity' if name.startswith('term_lock') else 'Explicit release/start year; remaining assumptions unchanged'),
                     'frozen':'All remaining inputs in base; market growth versus legal entity profit allocation separate',
                     'rows':rows,'valuation':value(rows,.09,**kw)}
        except ValueError as e:d[name]={'changed':updates,'infeasible':str(e)}
    return d

def tests():
    # Formal cash chain with hand-computable zero-growth debt-free entity.
    p=copy.deepcopy(INPUT);p.update(revenue0=[100,0],growth=[0,0],margin=[.2,0],tax=0,
      wc_ratio=0,capex_ratio=0,da_ratio=0,payout=.5,deposit_yield=0,opening_cash=[100,0,0],
      term_deposit=[0,0,0],opening_debt=[0,0,0],opening_legal=[100,0,0],opening_reserve=[50,0,0],
      reserve_caps=[50,0,0],profit_weights=[1,0,0],cash_weights=[1,0,0],cash_floor=[0,0,0],
      old_intercompany=0,release_target=0,opening_wc=0)
    r=simulate(p)
    assert [x['distribution'] for x in r]==[10]*5 and r[-1]['cash']==[150,0,0] and r[-1]['legal'][0]==150
    # Formal terminal chain constant perpetual profit 17, zero growth -> 170 at 10%.
    s={'revenue':[100,0],'ebit':20,'terminal_growth0':0}
    t=operating_terminal(s,.1,0,end_margin=.2)
    assert abs(t['value']-170)<1e-8
    # Accumulated statutory losses remain and prevent premature dividends.
    q=copy.deepcopy(p);q['opening_legal']=[-30,0,0];z=simulate(q)
    assert [x['distribution'] for x in z][:2]==[0,10]
    # Insufficient cash fails even with zero distributions and zero financing.
    q=copy.deepcopy(p);q['opening_cash']=[0,0,0];q['extra_capex']=[200]*5;q['payout']=0
    try:simulate(q)
    except (ValueError,AssertionError):pass
    else:raise AssertionError('unfunded must fail')
    return {'formal_cash_hand_case':True,'formal_terminal_hand_case':True,'loss_carryforward':True,'unfunded_zero_dividend':True}
if __name__=='__main__':
    out={'units':'CNY million except per share','shares':SHARES,'tests':tests(),'scenarios':scenarios()}
    payload=json.dumps(out,ensure_ascii=False,indent=2)
    Path(__file__).with_name('2026-Q3-output.json').write_text(payload+'\n')
    print(payload)
