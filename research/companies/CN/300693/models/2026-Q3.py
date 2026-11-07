"""Sinexcel 2026-Q3. Python standard library; CNY million / million shares.
Run: python 2026-Q3.py [--check]. Reads adjacent inputs; writes concise output.
No market price, IRR, encoded archive, historical Git object or private dependency.
"""
from pathlib import Path
from copy import deepcopy
import json, math, sys

HERE=Path(__file__).resolve().parent
INPUT=json.loads((HERE/'2026-Q3-inputs.json').read_text(encoding='utf8'))

def interpolate(a,b,t):return a+(b-a)*t

def operating_step(p,y,rev,wc,fixed,floor):
    if y<=5:
        growth=p['growth5'][y-1];gm=p['gross5'][y-1];expense=p['opex5'][y-1]
        parent_share=p['parent_op_share5'][y-1]
        subs_positive_share=p['subs_positive_profit_share5'][y-1]
    else:
        t=min(1.,(y-5)/(p['fade_year']-5))
        growth=[interpolate(g,p['long_growth'],t) for g in p['growth5'][-1]]
        gm=[interpolate(g,m,t) for g,m in zip(p['gross5'][-1],p['gross_mature'])]
        expense=interpolate(p['opex5'][-1],p['opex_mature'],t)
        parent_share=interpolate(p['parent_op_share5'][-1],p['parent_op_share_mature'],t)
        subs_positive_share=interpolate(p['subs_positive_profit_share5'][-1],p['subs_positive_profit_share_mature'],t)
    shock=p.get('margin_shock',0.) if y>=p.get('shock_year',1) else 0.
    gm=[m+shock for m in gm]
    newrev=[v*(1+g) for v,g in zip(rev,growth)];sales=sum(newrev)
    gross=sum(v*m for v,m in zip(newrev,gm));ebit=gross-sales*expense
    parent_ebit=ebit*parent_share;subs_ebit=ebit-parent_ebit
    parent_tax=p['parent_tax'] if y<p.get('tax_lost_year',999) else .25
    # Positive and loss-making subsidiaries do not offset each other's taxable income.
    subs_positive=max(subs_ebit,ebit*subs_positive_share,0.)
    tax=max(parent_ebit,0.)*parent_tax+subs_positive*p['subs_tax']
    minority=max(ebit,0.)*(1-p['subs_tax'])*p['other_minority_profit_fraction']
    # Pending subsidiary scheme applies only to this subsidiary's budget profit.
    scheme_nci=0.
    if p.get('subscheme_implemented_year') and y>=p['subscheme_implemented_year']:
        subprofit=p['subscheme_netprofit5'][min(y,5)-1]
        if y>5:subprofit*=sales/p['year5_sales']
        scheme_nci=subprofit*p['subscheme_minority_fraction']
        # A higher same-group subsidiary profit cannot hide taxable profit behind losses.
        required_positive=max(subprofit,0.)/(1-p['subs_tax'])
        extra_tax=max(required_positive-subs_positive,0.)*p['subs_tax']
        tax+=extra_tax
    cash_nopat=ebit-tax-minority-scheme_nci
    parent_cash_nopat=parent_ebit-max(parent_ebit,0.)*parent_tax
    target_wc=sales*p['wc_ratio']
    if y<=p.get('late_collection_years',0):target_wc+=sales*p.get('late_collection_extra_ratio',0.)
    delta_wc=target_wc-wc;da=sales*p['da_ratio']
    if y<=5:capex=sales*p['capex_ratio']+p['committed_capex'][y-1]
    else:capex=da+max(sales-sum(rev),0.)*p['mature_fixed_ratio']
    newfloor=sales*p['cash_floor_ratio'];delta_floor=newfloor-floor
    fcf=cash_nopat+da-capex-delta_wc
    parent_fcf=(parent_cash_nopat+da*p['parent_da_share']
                -capex*p['parent_capex_share']-delta_wc*p['parent_wc_share'])
    return dict(year=y,revenue=sales,segments=newrev,gross_margin=gross/sales,
      ebit=ebit,tax=tax,cash_nopat=cash_nopat,parent_cash_nopat=parent_cash_nopat,
      minority=minority,scheme_nci=scheme_nci,wc=target_wc,delta_wc=delta_wc,
      da=da,capex=capex,fixed=fixed+capex-da,cash_floor=newfloor,
      delta_cash_floor=delta_floor,fcf=fcf,parent_fcf=parent_fcf,
      distributable_operating_cash=fcf-delta_floor)

def payment_gate(cash,retained,target,floor):
    """The actual gate used in the forecast and the hand-calculated test."""
    amount=min(max(target,0.),max(cash-floor,0.),max(retained,0.))
    return amount,cash-amount,retained-amount

def vest_ratio(profit,target,trigger):
    return 1. if profit>=target else (.6 if profit>=trigger else 0.)

def simulate(overrides=None):
    f=deepcopy(INPUT['facts']);p=deepcopy(INPUT['assumptions']);p.update(overrides or {})
    wc_parts=f['wc_components']
    wc=sum(v for k,v in wc_parts.items() if k not in ['accounts_payable','bills_payable','contract_liability'])-sum(wc_parts[k] for k in ['accounts_payable','bills_payable','contract_liability'])
    fixed=f['fixed_operating_q3'];rev=p['revenue0'][:];floor=sum(rev)*p['cash_floor_ratio']
    cash=f['cce_q3']-f['first_repurchase_cash']-f['minority_book_q3']
    parent_cash=f['cce_q3']*f['parent_cce_h1']/f['group_cce_h1']-f['first_repurchase_cash']+p.get('parent_cash_shift',0.)
    parent_cash=min(max(parent_cash,0.),cash)
    term=f['term_deposit_h1'];parent_term=min(p['parent_term_budget'],term)
    group_re=f['common_re_q3'];parent_re=f['parent_re_h1']-f['h1_paid_in_september']
    parent_reserve=f['parent_reserve_h1'];loan_support=0.
    # The 2026 calendar-year proxy is derived from this cycle's independent revenue budget.
    gp0=sum(r*m for r,m in zip(rev,[.61,.375,.30,.31,.35]))
    eligible2026=(gp0-sum(rev)*.24)*(1-p['parent_tax'])
    goals=[561.62,673.94,808.73];triggers=[514.82,566.30,622.93]
    previous_eligible=eligible2026;vesting=[];payments=[];rows=[]
    shares=f['issued_shares']-f['treasury_at_cutoff'];cum_dps=0.
    # Estimate total earned award cost from the same operating path. Costs already booked
    # are not charged again; failure can reverse earlier estimates without creating cash.
    rv=rev[:];ww=wc;ff=fixed;fl=floor;proxies=[eligible2026]
    for yy in [1,2]:
        bb=operating_step(p,yy,rv,ww,ff,fl)
        proxies.append(bb['cash_nopat']+cash*p['cash_yield_aftertax']+term*p['term_yield_aftertax'])
        rv=bb['segments'];ww=bb['wc'];ff=bb['fixed'];fl=bb['cash_floor']
    expected_ratios=[vest_ratio(a,t,n) for a,t,n in zip(proxies,goals,triggers)]
    expected_cost=f['grant_full_fair_value']*sum(a*b for a,b in zip([.3,.3,.4],expected_ratios))
    remaining_cost=expected_cost-f['sbc_recognised_q3']
    weights=p['sbc_future_full_weights'];total_weight=sum(weights)
    fees=([remaining_cost,0.,0.,0.,0.] if remaining_cost<0. else [remaining_cost*w/total_weight for w in weights])
    if p.get('reserve_vests'):
        reserve_cost=f['grant_full_fair_value']/f['first_grant_shares']*f['ungranted_reserve_shares']
        fees[1]+=reserve_cost*.5;fees[2]+=reserve_cost*.5
    treasury_reissued=f['treasury_at_cutoff']
    for y in range(1,p['fade_year']+2):
        if y==6:
            p['year5_sales']=sum(rev);p['mature_fixed_ratio']=fixed/sum(rev)
        b=operating_step(p,y,rev,wc,fixed,floor)
        if y>5:
            # Beyond the five-year payment budget, model the operating economic value.
            # Surplus cash is available for ordinary owners after required capital;
            # do not silently perpetuate a 45% payout and an ever-growing cash hoard.
            rows.append(b)
            rev=b['segments'];wc=b['wc'];fixed=b['fixed'];floor=b['cash_floor']
            continue
        if y<=3:
            ratio=vest_ratio(previous_eligible,goals[y-1],triggers[y-1])
            if p.get('no_exercise'):ratio=0.
            vest=f['first_grant_shares']*[.3,.3,.4][y-1]*ratio
        else:vest=0.;ratio=0.
        # Reserve is ungranted as of cutoff. Optional sensitivity assumes later grant/settlement.
        if p.get('reserve_vests') and y in [2,3]:vest+=f['ungranted_reserve_shares']*.5
        price=max(0.,f['grant_price_less_paid_dividends']-cum_dps)
        subscription=vest*price;shares+=vest
        # Repurchases for employee plans return to outstanding shares, never assume cancellation.
        repurchase=(p['new_repurchase_budget_total']-f['first_repurchase_cash']) if y==1 else 0.
        if repurchase:
            bought=repurchase/p['new_repurchase_average_price_budget']
            shares-=bought;treasury_reissued+=bought
        if y==p['new_repurchase_treasury_reissue_year']:shares+=treasury_reissued
        sbc=fees[y-1] if y<=5 else 0.
        netinterest=cash*p['cash_yield_aftertax']+term*p['term_yield_aftertax']
        parent_interest=parent_cash*p['cash_yield_aftertax']+parent_term*p['term_yield_aftertax']
        debt=f['debt_and_lease_q3'] if y==1 else 0.
        parent_debt=f['parent_bank_debt_h1'] if y==1 else 0.
        interest_cost=debt*.04*(1-p['parent_tax'])
        parent_interest_cost=parent_debt*.04*(1-p['parent_tax'])
        scheme_cash=p['subscheme_cash'] if p.get('subscheme_implemented_year')==y else 0.
        # New minority capital is not parent profit. Only parent's post-transaction economic share.
        scheme_parent_cash=scheme_cash*(1-p['subscheme_minority_fraction'])
        matured=term if y==p['term_maturity_year'] else 0.
        parent_matured=parent_term if matured else 0.
        start_cash=cash;start_term=term
        early=0.;early_fee=0.
        if y==p.get('early_term_year',0):
            early=min(p.get('early_term_cash',0.),term)
            early_fee=early*p.get('early_term_fee',.005)
            # Break a parent-held term deposit; budget conditional on bank withdrawal terms.
            term-=early;parent_term-=min(early,parent_term)
            cash+=early-early_fee;parent_cash+=early-early_fee
        investment_cash=0.;investment_loss=0.
        if y==p['investment_realisation_year']:
            gross=f['non_operating_investment_book_q3']*p['investment_recovery']*(1-p['investment_fee'])
            investment_cash=gross*(1-p['investment_gross_tax_reserve'])
            investment_loss=investment_cash-f['non_operating_investment_book_q3']
        cash+=b['fcf']+netinterest-interest_cost+subscription+scheme_parent_cash+matured-debt-repurchase+investment_cash
        parent_cash+=b['parent_fcf']+parent_interest-parent_interest_cost+subscription+parent_matured-parent_debt-repurchase+investment_cash
        term-=matured;parent_term-=parent_matured
        # Other entities meet their operating floor with existing cash; parent supports a shortfall.
        child_floor=b['cash_floor']*(1-p['parent_cash_floor_share'])
        child_cash=cash-parent_cash
        support=max(child_floor-child_cash,0.)
        parent_cash-=support;loan_support+=support
        netprofit=b['cash_nopat']-sbc+netinterest-interest_cost+investment_loss-early_fee
        parent_profit=b['parent_cash_nopat']-sbc+parent_interest-parent_interest_cost+investment_loss-early_fee
        group_re+=netprofit;parent_re+=parent_profit
        appropriation=max(parent_profit,0.)*p['voluntary_parent_reserve_fraction']
        parent_re-=appropriation;parent_reserve+=appropriation
        target=max(netprofit,0.)*p['distribution_fraction']
        group_target=min(target,max(cash-b['cash_floor'],0.),max(group_re,0.))
        paid,new_parent_cash,new_parent_re=payment_gate(parent_cash,parent_re,group_target,b['cash_floor']*p['parent_cash_floor_share'])
        feasible=cash>=b['cash_floor']-1e-8 and parent_cash>=b['cash_floor']*p['parent_cash_floor_share']-1e-8
        if not feasible:
            return {'feasible':False,'year':y,'group_cash':cash,'parent_cash':parent_cash,'cash_floor':b['cash_floor'],'reason':'Operating capital and normal payment obligations cannot be funded without new financing or lower investment.'}
        parent_cash=new_parent_cash;parent_re=new_parent_re;cash-=paid;group_re-=paid
        dps=paid/shares;cum_dps+=dps
        # Cash conservation includes maturity as transfer, not income.
        expected=(b['fcf']+netinterest-interest_cost+subscription+scheme_parent_cash-debt-repurchase-paid+investment_cash-early_fee)
        assert math.isclose(cash+term-start_cash-start_term,expected,abs_tol=1e-7)
        assert parent_cash<=cash+1e-7
        assert group_re>=-1e-8 and parent_re>=-1e-8
        b.update(cash=cash,term=term,parent_cash=parent_cash,parent_term=parent_term,
          parent_re=parent_re,parent_reserve=parent_reserve,common_re=group_re,
          netprofit=netprofit,parent_profit=parent_profit,sbc=sbc,
          dividend=paid,dps=dps,shares=shares,vested=vest,vest_ratio=ratio,
          subscription=subscription,grant_price=price,repurchase=repurchase,
          early_term_unlocked=early,early_term_fee=early_fee,investment_cash=investment_cash,
          intercompany_support=support,cumulative_support=loan_support,
          financing=0.,scheme_cash_common=scheme_parent_cash)
        rows.append(b);payments.append(dps);vesting.append(vest)
        previous_eligible=b['cash_nopat']+netinterest-interest_cost
        rev=b['segments'];wc=b['wc'];fixed=b['fixed'];floor=b['cash_floor']
    return dict(feasible=True,rows=rows,eligible2026=eligible2026,inputs=p)

def tail_value(rows,r,g,at=5):
    """Business PV only; excludes financial interest and all existing excess cash."""
    final=rows[-1]
    # At fade+1 all rates/intensities are mature. This period is the first perpetuity cash.
    tv=final['distributable_operating_cash']/(r-g)
    explicit=sum(b['distributable_operating_cash']/(1+r)**(b['year']-at)
                 for b in rows if at<b['year']<final['year'])
    return explicit+tv/(1+r)**(final['year']-1-at)

def value(sim):
    if not sim['feasible']:return sim
    rows=sim['rows'];p=sim['inputs'];five=rows[4];ends=[];aux=[];term=[];contributions=[]
    # Following year-5 operating value requires remaining capital; floor is excluded from cash.
    financial=five['cash']+five['term']-five['cash_floor']
    parent_extra=max(0.,five['parent_cash']+five['parent_term']-five['cash_floor']*p['parent_cash_floor_share'])
    child_extra=max(0.,financial-parent_extra)
    for r,pe in zip(p['discount_rates'],p['auxiliary_operating_pe']):
        business=tail_value(rows,r,p['long_growth'])
        finvalue=(parent_extra+child_extra*p['child_extra_recovery'])*(1-p['terminal_financial_friction'])*((1+p['cash_yield_aftertax'])/(1+r))**p['terminal_financial_realisation_lag']
        terminal=(business+finvalue)/five['shares']
        pvdiv=sum(b['dps']/(1+r)**b['year'] for b in rows[:5])
        current=pvdiv+terminal/(1+r)**5
        # Separate earnings capitalisation, excluding interest and cash already distributed.
        earnings=five['cash_nopat']-five['sbc']
        aux_terminal=(earnings*pe+finvalue)/five['shares']
        ends.append(current);term.append(terminal)
        aux.append(pvdiv+aux_terminal/(1+r)**5)
        contributions.append((terminal/(1+r)**5)/current)
    return dict(value_range={'low':ends[0],'high':ends[1],'currency':'CNY'},
      return_model={'schema_version':1,'method':'annual_common_equity_irr_v1','currency':'CNY',
       'model_as_of':INPUT['information_cutoff'],
       'base_case_distributions_per_share':[b['dps'] for b in rows[:5]],
       'base_case_terminal_equity_value_range_per_share':{'year_5':{'low':term[0],'high':term[1]}}},
      auxiliary_value_range=aux,terminal_pv_fraction=contributions,
      financial_bridge_y5={'cash':five['cash'],'term':five['term'],'cash_floor':five['cash_floor'],'extra':financial,
       'parent_extra':parent_extra,'child_extra':child_extra,'child_recovery':p['child_extra_recovery'],
       'legal_realisation_lag_years':p['terminal_financial_realisation_lag']},
      forecast5=[{k:v for k,v in b.items() if k not in ['segments']} for b in rows[:5]],
      fade={'year':rows[-2]['year'],'revenue':rows[-2]['revenue'],'cash_nopat':rows[-2]['cash_nopat'],
       'annual_cash':rows[-1]['distributable_operating_cash'],'growth':p['long_growth']},
      eligible2026=sim['eligible2026'])

def run():
    base=simulate();out=value(base)
    scenarios={
      'temporary_delay':{'growth5':[[0.,.03,.02,0.,0.],[.12,.15,.07,.03,.02]]+INPUT['assumptions']['growth5'][2:],
        'late_collection_years':2,'late_collection_extra_ratio':.04},
      'structural_competition':{'growth5':[[.08,.08,.03,0.,0.]]*5,
        'gross5':[[.53,.29,.25,.28,.30]]*5,'gross_mature':[.48,.25,.23,.27,.28],
        'opex5':[.245,.24,.235,.23,.225], 'opex_mature':.22,'wc_ratio':.18,'long_growth':.01,
        'early_term_year':1,'early_term_cash':200.,'early_term_fee':.005},
      'stronger_execution':{'growth5':[[.27,.28,.15,.07,.06],[.22,.23,.13,.06,.05]]+INPUT['assumptions']['growth5'][2:],
         'committed_capex':[110,60,0,0,0]},
      'gross_margin_minus_2pt':{'margin_shock':-.02,'shock_year':2},
      'mature_margin_minus_2pt_from_year6':{'margin_shock':-.02,'shock_year':6},
      'wc_plus_5pt':{'wc_ratio':.19,'early_term_year':1,'early_term_cash':80.,'early_term_fee':.005},
      'parent_tax25_from_year1':{'tax_lost_year':1},
      'parent_cash_minus100':{'parent_cash_shift':-100},
      'parent_cash_plus100':{'parent_cash_shift':100},
      'term_matures_year5':{'term_maturity_year':5},
      'no_grant_exercise':{'no_exercise':True},
      'ungranted_reserve_full_vests':{'reserve_vests':True},
      'pending_sub_scheme_completed_year1':{'subscheme_implemented_year':1},
      'pending_sub_scheme_high_profit':{'subscheme_implemented_year':1,'subscheme_netprofit5':[-10,20,40,60,80]},
      'permanent_zero_growth':{'long_growth':0.},
      'child_extra_no_recovery':{'child_extra_recovery':0.},
      'investment_total_loss':{'investment_recovery':0.},
    }
    out['scenarios']={}
    for name,changes in scenarios.items():
        s=simulate(changes)
        if s['feasible']:
            v=value(s);out['scenarios'][name]={'value_range':v['value_range'],
              'distributions_per_share':v['return_model']['base_case_distributions_per_share'],
              'year5_terminal':v['return_model']['base_case_terminal_equity_value_range_per_share']['year_5'],
              'min_parent_cash':min(b['parent_cash'] for b in s['rows'][:5]),
              'max_intercompany_support':max(b['cumulative_support'] for b in s['rows'][:5]),
              'changed_inputs':changes}
        else:out['scenarios'][name]=s|{'changed_inputs':changes}
    out={'symbol':INPUT['symbol'],'report_period':INPUT['report_period'],**out}
    return out

def check():
    # Send a hand-checkable flat business through the SAME official operating function.
    p=deepcopy(INPUT['assumptions']);p.update(growth5=[[0.]*5]*5,gross5=[[.4]*5]*5,
      opex5=[.2]*5,parent_op_share5=[1.]*5,parent_tax=.25,subs_tax=.25,
      subs_positive_profit_share5=[0.]*5,
      other_minority_profit_fraction=0.,wc_ratio=.1,da_ratio=.02,capex_ratio=.02,
      committed_capex=[0.]*5,cash_floor_ratio=.05)
    b=operating_step(p,1,[100.,0.,0.,0.,0.],10.,20.,5.)
    # Revenue100, GP40, expense20, tax5, profit/FCF15; DA2 exactly funds capex2.
    assert math.isclose(b['fcf'],15.,abs_tol=1e-12)
    assert math.isclose(b['distributable_operating_cash'],15.,abs_tol=1e-12)
    paid,cash,re=payment_gate(12.,20.,10.,5.)
    assert (paid,cash,re)==(7.,5.,13.)
    # Flat 15 perpetuity, r10%, g0, at year5: 150. Official tail function.
    r=[dict(year=y,distributable_operating_cash=15.) for y in range(1,17)]
    assert math.isclose(tail_value(r,.10,0.),150.,abs_tol=1e-10)
    sim=simulate();v=value(sim)
    assert len(v['return_model']['base_case_distributions_per_share'])==5
    assert all(row['repurchase']>=0. for row in sim['rows'][:5])
    assert sim['rows'][3]['shares']>=INPUT['facts']['issued_shares']
    assert sim['rows'][2]['term']==0.
    assert sim['rows'][0]['financing']==0.
    print('Checks passed: official operating function hand case, payment gate, perpetuity, cash conservation, maturity, treasury reissue and five-year contract.')


METADATA = {'information_cutoff': '2026-11-06T23:59:59+08:00', 'valuation_note': '主法为前五年实际分配加第五年剩余普通股经济价值折现，经营继续推至第十五年、增速向2%和分部毛利52/29/25/29/30%衰减；股权成本11%/10%。第五年额外金融本金约15.649亿元，单独按两年实现、1%摩擦和1%净息估值，子额外资金采用75%回收。辅助第五年经营盈利11—12倍资本化为23.72—26.47元，未取平均。暂时延迟19.20—22.04元、结构性竞争12.27—13.91元，情景端点不混入核心。', 'return_model_note': '五次每股现金分配按归母利润45%预算并经母法定利润、母现金和集团资金门槛，首年受约束降额；无特别分派存单承诺。第五年经营价值独立由第6—15年经营现金及2%成熟尾值形成，金融本金已扣五次分配、回购、投入与还债；终值34.166286—38.215444元，当前价值独立折现。基准第五年完全稀释有权股数3.14493103亿股，含预计60%公司比例归属的限制股和全部库存重新流通；未来认款与股份同步，回购不列持有人现金。不提供三年终值。'}

if __name__=='__main__':
    import argparse
    sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path)
    p.add_argument('--check',action='store_true')
    args=p.parse_args()
    if args.check:check()
    result=run();result.update(METADATA,schema='trading_os_research_result_v1')
    text=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if args.output:args.output.write_text(text,encoding='utf-8')
    else:print(text,end='')
