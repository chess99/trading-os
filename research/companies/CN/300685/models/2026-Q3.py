"""艾德生物2026Q3统一六根修正候选。金额百万元；无现价、IRR、交易阈值。
P是真实母公司；D/F是经济能力预算，绝非法人，不设注册资本或法储。
运行产生全部年度结果；--expand 将无损gzip展开；--out DIR选择输出目录。
"""
import copy,json,math,gzip,hashlib,argparse,base64,zlib
from pathlib import Path
OLD_SOURCE='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'
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
        opening=sum(cash)+sum(term);g=p.get('growth_path',[p['growth']]*5)[y-1];m=p.get('margin_path',[p['margin']]*5)[y-1]
        rev=[a*(1+b) for a,b in zip(rev,g)];sales=sum(rev);ebit=sum(a*b for a,b in zip(rev,m))
        tax=max(ebit,0)*p.get('tax_path',[p['tax']]*5)[y-1];nop=ebit-tax
        nwc=sales*p.get('wc_path',[p['wc_ratio']]*5)[y-1];da=sales*p['da_ratio'];capex=sales*p['capex_ratio']+p['extra_capex'][y-1]
        fcf=nop+da-capex-(nwc-wc);wc=nwc
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
        old=sum(cash);gr=g0+(g-g0)*min(k,10)/10;newrev=rev*(1+gr)
        m=margin+(end_margin-margin)*min(k,10)/10;nop=newrev*m-max(newrev*m,0)*p['tax']
        reinvest=(newrev-rev)*ic;fcf=nop-reinvest
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

CHANGES={
 'cyclical':dict(growth_path=[[-.06,0],[.02,.04],[.10,.12],[.08,.10],[.06,.09]],margin_path=[[.31,.21],[.33,.23],[.35,.25],[.35,.25],[.35,.25]],wc_path=[.60,.57,.54,.52,.50]),
 'structural':dict(growth=[0.,.04],margin=[.25,.20],wc_ratio=.60,capex_ratio=.055,tail_g=.015,tail_margin=.23,tail_ic=1.,tail_growth0=.025),
 'upside':dict(growth=[.09,.13],margin=[.36,.28],wc_ratio=.48,capex_ratio=.05,tail_margin=.32,tail_growth0=.09),
 'margin_minus2pp':dict(margin=[.33,.23],tail_margin=.28),
 'release_year3':dict(release_year=3),'release_year5':dict(release_year=5),
 'term_lock3':dict(term_maturity=3),'term_lock5':dict(term_maturity=5),
 'upstream_year3':dict(subs_upstream_start=3),'terminal_release5':dict(financial_release_delay=5),
 'parent_cash_minus150':dict(opening_cash=[888.798788,175.,195.]),
 'tax_incentive_lapse':dict(tax=.25),
 'access_worse':dict(access_cost=[0.,.10,.30],financial_release_delay=5),
 'paid_capital_return':dict(redemption=[0.,0.,10.,0.,0.]),
 'voluntary10_after_cap':dict(voluntary_reserve_rate=.10),
 'zero_dividend_unfunded':dict(opening_cash=[0.,0.,0.],term_deposit=[0.,0.,0.],payout=0.,extra_capex=[2000]*5)}

def cases():
    out={}
    for name,updates in {'base':{},**CHANGES}.items():
        p=copy.deepcopy(INPUT);p.update(updates);rows=[]
        try:
            rows=simulate(p);v=value(rows,p)
            out[name]=dict(inputs=p,changed=updates,rows=rows,valuation=v,
              effective_year=(3 if name in ['release_year3','upstream_year3'] else 5 if name=='release_year5' else 6 if name in ['access_worse','terminal_release5'] else 1),
              classification='full_operating_path' if name in ['base','cyclical','structural','upside'] else 'isolated_diagnostic',feasible=True)
            if name=='base':
                out[name]['low']=value(rows,p,.095,.02,.29,.85,18)
                out[name]['high']=value(rows,p,.085,.025,.31,.75,22)
        except ValueError as e:out[name]=dict(inputs=p,changed=updates,rows=rows,feasible=False,failure=str(e))
    baseline=out['base']
    for name,case in out.items():
        first=None
        for a,b in zip(case.get('rows',[]),baseline['rows']):
            if any(abs(a[k]-b[k])>1e-7 for k in ['distribution','fcf','parent_legal']) or any(abs(x-y)>1e-7 for x,y in zip(a['cash']+a['term'],b['cash']+b['term'])):
                first=a['year'];break
        if first is None and case['feasible']:
            for a,b in zip(case['valuation']['tail'],baseline['valuation']['tail']):
                if any(abs(a[k]-b[k])>1e-7 for k in ['operating_distribution','financial_distribution','parent_legal']):first=a['year'];break
        case['actual_first_changed_year']=first
    return out

def tests():
    assert legal_update(0,5,20,10)[2]==1 # registered20 paid10 is NOT cap5
    assert legal_update(-12,0,20,10)[0]==-2 and legal_update(-12,0,20,10)[2]==0
    assert legal_update(0,10,20,10)[2]==0
    assert legal_update(0,10,40,10)[2]==1 # registered conversion actually effective
    assert legal_update(-5,0,20,10)[2]==.5
    assert legal_update(0,10,20,10,.1)[3]==1
    q=copy.deepcopy(INPUT);q.update(revenue0=[100.,0.],growth=[0.,0.],margin=[.2,0.],tax=0.,wc_ratio=0.,opening_wc=0.,capex_ratio=0.,da_ratio=0.,opening_cash=[100.,0.,0.],term_deposit=[0.]*3,opening_debt=[0.]*3,parent_retained=100.,parent_reserve=10.,parent_registered=20.,profit_weights=[1.,0.,0.],cash_weights=[1.,0.,0.],cash_floor=[0.]*3,deposit_yield=0.,old_receivable=[0.,0.])
    z=simulate(q);assert [x['distribution'] for x in z]==[10.]*5 and z[-1]['cash']==[150.,0.,0.]
    qc=copy.deepcopy(q);qc.update(revenue0=[50.,0.],parent_registered=20.,parent_paid=10.,parent_reserve=5.,parent_retained=0.)
    assert simulate(qc)[0]['statutory_allocation']==1.
    q2=copy.deepcopy(q);q2.update(parent_retained=-30.)
    assert [x['distribution'] for x in simulate(q2)][:2]==[0.,10.]
    q3=copy.deepcopy(q);q3.update(opening_cash=[0.,100.,0.],old_receivable=[10.,0.],payout=0.)
    zz=simulate(q3)[0];assert zz['parent_profit']==20 and zz['principal_receipts'][0]==10
    qloss=copy.deepcopy(q);qloss.update(margin=[-.1,0.],tax=.25,payout=0.)
    assert simulate(qloss)[0]['tax']==0 and simulate(qloss)[0]['nopat']==-10
    q4=copy.deepcopy(q);q4.update(opening_cash=[0.]*3,extra_capex=[1000]*5,payout=0.)
    try:simulate(q4)
    except ValueError:pass
    else:raise AssertionError('unfunded must fail')
    qr=copy.deepcopy(q);qr.update(parent_paid=20.,redemption=[5.,0.,0.,0.,0.],external_shares=100.,share_par=.2)
    zr=simulate(qr);assert zr[0]['shares']==75 and zr[0]['registered']==15 and zr[0]['distribution']==15
    cr=capital_return(10,6,8,20,100,fee=.1,ownership=.7)
    assert abs(cr['net']-3.78)<1e-9 and cr['shares']==70 and cr['profit']==0 and cr['registered']==14
    ex=realize(100,90,80,.2,.1,.7,required_exit=5)
    assert ex['net']==58.8 and ex['tax']==.7 and ex['minority']>0
    try:realize(1,1,1,.2,0.,required_exit=2)
    except ValueError:pass
    else:raise AssertionError('exit insufficiency must fail')
    before=(100.,120.,50.)
    try:realize(before[0],90.,80.,.2,.01,external_debt=before[1],shares=before[2])
    except ValueError:assert before==(100.,120.,50.)
    else:raise AssertionError('external debt shortfall cannot extinguish shares')
    try:capital_return(10,6,8,20,100,external_debt_due=5)
    except ValueError:pass
    else:raise AssertionError('redemption cannot strand external debt')
    # Necessity cash earns; excluding income changes value, not arbitrary release of principal.
    q.update(equity_asset=0.,equity_book=0.,equity_tax_basis=0.)
    v=value(z,q,r=.1,g=0,end_margin=.2,terminal_growth0=0)
    assert abs(v['terminal_operating']-200)<1e-7
    return dict(registered_not_paid=True,loss_before_reserve=True,cap_and_conversion=True,voluntary_distinct=True,
      old_receivable_no_profit=True,no_immediate_loss_tax_refund=True,zero_dividend_failure=True,capital_return_shares_and_basis=True,
      minority_and_exit_cost=True,unfunded_exit_failure=True,external_debt_exit_failure_preserves_shares=True,redemption_external_debt_failure=True,actual_cash_function_hand_case=True,actual_tail_hand_case=True)

def bridge():
    ns={'__name__':'frozen_old'};exec(zlib.decompress(base64.b64decode(OLD_SOURCE)).decode(),ns)
    olds=ns['scenarios']();out={}
    for name,old in olds.items():
        if 'rows' not in old:continue
        p=copy.deepcopy(INPUT)
        if name in CHANGES:p.update(CHANGES[name])
        # Keep old economic budget, including old assumed internal interest/loan split,
        # zero realization friction and no incremental minimum-cash income; isolate legal method.
        p.update(old_receivable=[8.327219/2]*2,internal_interest=.03,access_cost=[0.,0.,0.],
          equity_tax_basis=53.,equity_book=53.,equity_sale_fee=0.,minimum_cash_interest=False)
        rows=simulate(p);v=value(rows,p);ov=old.get('mid',old.get('valuation'))
        out[name]=dict(old_per_share=ov['per_share'],new_same_budget_per_share=v['per_share'],delta=v['per_share']-ov['per_share'],
          old_terminal=ov['terminal_per_share'],new_terminal=v['terminal_per_share'],old_D=[x['distribution'] for x in old['rows']],new_D=[x['distribution'] for x in rows],
          old_years=old['rows'],new_years=rows,new_tail=v['tail'],
          legal_method_only='No fictitious statutory subsidiary pools; finite economic residual realization. Identical sales/cost/tax/capex/debt/share budget; timing method changes explicitly.',
          old_last_financial_release=max(x['years_after_y5'] for x in ov['terminal_deferred_release']))
    p=copy.deepcopy(INPUT);p.update(old_receivable=[8.327219/2]*2,internal_interest=.03,access_cost=[0.,0.,0.],equity_tax_basis=53.,equity_book=53.,equity_sale_fee=0.,minimum_cash_interest=False)
    rr=simulate(p)
    for label,args in [('low',(.095,.02,.29,.85,18)),('high',(.085,.025,.31,.75,22))]:
        nv=value(rr,p,*args);ov=olds['base'][label]
        out['base_'+label]=dict(old_per_share=ov['per_share'],new_same_budget_per_share=nv['per_share'],delta=nv['per_share']-ov['per_share'],old_terminal=ov['terminal_per_share'],new_terminal=nv['terminal_per_share'],old_D=[x['distribution'] for x in olds['base']['rows']],new_D=[x['distribution'] for x in rr],old_years=olds['base']['rows'],new_years=rr,new_tail=nv['tail'],old_last_financial_release=max(x['years_after_y5'] for x in ov['terminal_deferred_release']))
    return out

def run():
    result=dict(schema='300685-unified-root-v1',units='CNY million except per-share',shares=SHARES,
      method='Real parent legal constraint plus expressly conditional economic residual access; no synthetic subsidiaries',tests=tests(),scenarios=cases(),same_budget_bridge=bridge())
    base=result['scenarios']['base'];v=base['valuation'];p=base['inputs'];rows=base['rows']
    result['convergence']={str(h):value(rows,p,horizon=h)['per_share'] for h in [50,100,200,500]}
    assert max(result['convergence'].values())-min(result['convergence'].values())<1e-8
    result['economic_assumption_bridge']=[]
    steps=[dict(old_receivable=[8.327219/2]*2,internal_interest=.03,access_cost=[0.,0.,0.],equity_tax_basis=53.,equity_book=53.,equity_sale_fee=0.,minimum_cash_interest=False),
      dict(old_receivable=INPUT['old_receivable'],internal_interest=0.),dict(access_cost=INPUT['access_cost']),
      dict(equity_tax_basis=50.,equity_sale_fee=.01),dict(minimum_cash_interest=True)]
    pp=copy.deepcopy(INPUT);last=None
    for n,step in enumerate(steps):
        pp.update(step);rr=simulate(pp);vv=value(rr,pp)
        result['economic_assumption_bridge'].append(dict(step=n,changes=step,value=vv['per_share'],delta=None if last is None else vv['per_share']-last,rows=rr))
        last=vv['per_share']
    assert abs(last-v['per_share'])<1e-9
    return result

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--out',default=str(Path(__file__).parent));a.add_argument('--expand',action='store_true');args=a.parse_args()
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    data=(json.dumps(run(),ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
    compressed=gzip.compress(data,mtime=0);(out/'2026-Q3-output.json.gz').write_bytes(compressed)
    if args.expand:(out/'2026-Q3-output.json').write_bytes(data)
    summary=dict(schema='300685-unified-root-v1',uncompressed_bytes=len(data),compressed_bytes=len(compressed),sha256_uncompressed=hashlib.sha256(data).hexdigest(),sha256_gzip=hashlib.sha256(compressed).hexdigest())
    (out/'output-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
