"""中国核电普通股模型。标准库、离线；亿元/GW/亿股。参数均为研究预算。"""
import json, copy
from pathlib import Path
S=205.68002074
B0=1205.2045634206
M0=1164.9038483641
DEBT0=4980.52
D0=[.16,.18,.20,.22,.24]
PAID_OLD_DIVIDEND=4.1027979634
GROUP_CASH_AFTER_OLD_DIV=157.8272986299-PAID_OLD_DIVIDEND
PARENT_CASH_AFTER_OLD_DIV=44.1200110951-PAID_OLD_DIVIDEND
# first: 首个50%年度的相对周年，随后一个年度达到100%。容量为披露总量约束的组合估计。
PROJECTS=[
 dict(name='田湾7、8',budget=466.7883,spent=397.9091,gw=2.53,own=.46,first=1,vat=True),
 dict(name='徐大堡3、4',budget=482.6090,spent=378.3657,gw=2.55,own=.54,first=2,vat=True),
 dict(name='三门3、4',budget=461.7521,spent=317.7687,gw=2.50,own=.56,first=2,vat=True),
 dict(name='徐大堡1、2',budget=389.3578,spent=245.3087,gw=2.50,own=.54,first=3,vat=True),
 dict(name='漳州3、4',budget=360.9005,spent=149.7120,gw=2.42,own=.51,first=4,vat=True),
 dict(name='金七门1、2',budget=414.4716,spent=158.8516,gw=2.46,own=.51,first=5,vat=True),
 dict(name='徐圩一期',budget=678.7293,spent=127.1264,gw=3.09,own=.46,first=6,vat=True),
 dict(name='三门5、6',budget=405.1699,spent=63.0218,gw=2.50,own=.56,first=6,vat=True),
 dict(name='其他在建/海南小堆及新核准组合',budget=1410.5079,spent=510.5079,gw=5.085,own=.51,first=8,vat=False),
 dict(name='在建风光',budget=400.,spent=206.0095,gw=9.2406,own=.50,first=2,vat=False,renew=True),
]
BASE=dict(k=.086,g=.0075,price=.333,cash_unit=.135,hours=7300,new_rate=.024,existing_price_change=-.0025,recovery=5.,overrun=1.,delay=0,renew_price=.30,renew_hours=1900,renew_cash=.07,pool_remaining=900.,parent_loan_annual=40.,upstream_ratio=.85,other_initial_capi=10.,q3_growth_paid=140.,payment_extra=0.,upstream_delay=0.,weak_years=0,structural_loss=0.,renew_ownership=.50)
LOW={**BASE,'k':.092,'g':.005,'price':.325,'cash_unit':.14,'hours':7100,'new_rate':.026,'existing_price_change':-.005,'recovery':0.,'overrun':1.04,'renew_price':.29,'renew_hours':1800,'other_initial_capi':15.}
HIGH={**BASE,'k':.08,'g':.01,'price':.34,'cash_unit':.13,'hours':7500,'new_rate':.022,'existing_price_change':0.,'recovery':10.,'overrun':1.,'renew_price':.31,'renew_hours':2000,'other_initial_capi':5.}
def valuation(book, earnings, distributions, k, g, shares):
    b=book; ri=0.; pvd=0.; n=len(earnings)
    for t,(e,d) in enumerate(zip(earnings,distributions),1):
        ri+=(e-k*b)/(1+k)**t; pvd+=d/(1+k)**t; b+=e-d
    enext=earnings[-1]*(1+g); dnext=enext-g*b
    terminal=dnext/(k-g); tr=(enext-k*b)/(k-g)
    value=(pvd+terminal/(1+k)**n)/shares
    riv=(book+ri+tr/(1+k)**n)/shares
    assert abs(value-riv)<1e-8
    tv5=(sum(d/(1+k)**(i+1-5) for i,d in enumerate(distributions) if i>=5)+terminal/(1+k)**(n-5))/shares
    return dict(next_dividend=dnext,terminal_total=terminal,pv_distributions=pvd,value=value,terminal5=tv5,ri_value=riv,ri_explicit=ri,ri_terminal=tr)

def model(par, years=20):
    projects=copy.deepcopy(PROJECTS)
    for p in projects:
        if p['name'].startswith('其他'):p['budget']=p['spent']+par['pool_remaining']
        p['budget']=p['spent']+(p['budget']-p['spent'])*par['overrun']
        p['first']+=par['delay']
        p['remaining']=p['budget']-p['spent']
    remaining_total=sum(p['remaining'] for p in projects)
    # 已付建设款从未来现金剔除，分项分配为估计；不改变完整折旧成本。
    for p in projects:
        paid=par['q3_growth_paid']*p['remaining']/remaining_total
        p['spent']+=paid; p['remaining']-=paid
        if p.get('renew'): p['own']=par['renew_ownership']
    b,m,debt=B0,M0,DEBT0
    parent_debt=204.590962185
    parent_loans=0.
    parent_reserve=313.3491770382
    parent_statutory=63.368595982
    statutory_cap=S*.5
    deferred_upstream=0.
    rows=[]
    cumulative_extra_capitalized=0.
    original_cip=sum(p['spent'] for p in projects)
    # 费用化利息Q3累计年化；主要工程资本化以H1年化为锚。
    gross0=66.6217166852+35.393165244+par['other_initial_capi']
    cap0=35.393165244+par['other_initial_capi']
    old_da=2*(107.850361536+2.461898966+2.874038899+.985422893)
    old_common=60.660476185*4/3
    old_group=120.4824133592*4/3
    old_share=old_common/old_group
    for t in range(1,years+1):
        if t>20:
            # 稳态经济资本预算：不创造未计价闲置金融资产，不代表法定承诺。
            z=copy.deepcopy(rows[-1]); growth=par['g']; scale=1+growth
            common=z['common_earnings']*scale; minority=z['minority_earnings']*scale
            da=z['depreciation']*scale
            d=common-growth*b; md=minority-growth*m
            cp=da+growth*(b+m+debt)
            nd=debt*scale; bn=b*scale; mn=m*scale
            net=common+minority+.3
            assert abs(net+da+nd-debt-cp-d-md-.3)<1e-7
            assert abs(bn+mn+nd-(b+m+debt)-(cp-da))<1e-7
            pexpense=z['parent_net_expense']*scale
            pl=parent_loans*growth
            upstream=d+pexpense+pl-parent_debt*growth
            legalprofit=upstream-pexpense
            stat_add=min(max(0,legalprofit)*.1,max(0,statutory_cap-parent_statutory))
            parent_statutory+=stat_add
            parent_reserve+=legalprofit-stat_add-d
            assert parent_reserve>=-1e-7
            parent_debt*=scale;parent_loans*=scale
            z.update(year=t,common_earnings=common,group_earnings=net,minority_earnings=minority,
              dividend=d,dividend_per_share=d/S,common_equity_start=b,common_equity_end=bn,
              minority_equity_end=mn,debt_end=nd,capex=cp,growth_capex=growth*(b+m+debt),
              maintenance_capex=da,depreciation=da,working_capital=0.,cash_reserve_rebuild=0.,
              minority_new_capital=0.,minority_distribution=md,interest_expensed=z['interest_expensed']*scale,
              gross_interest=z['gross_interest']*scale,interest_capitalized=0.,parent_debt_end=parent_debt,
              parent_loan_balance=parent_loans,parent_net_loan=pl,parent_upstream=upstream,parent_injection=0.,
              parent_net_expense=pexpense,parent_legal_profit_budget=legalprofit,
              parent_legal_retention_budget=stat_add,parent_reserve_budget=parent_reserve,
              parent_deferred_dividend=0.,accelerated_payable_settlement=0.,projects=[],regime='steady_operating_capital')
            rows.append(z);b,m,debt=bn,mn,nd
            continue
        growth_cap=cap_interest=op_new=common_op_new=da_new=vat=common_vat=minor_in=parent_inject=maint_new=0.
        contributions=[]
        for p in projects:
            first=p['first']; full=first+1
            f=min(1,max(0,(t-first+1)/2))
            oldf=min(1,max(0,(t-first)/2))
            spend=p['remaining']/full if t<=full else 0.
            paid_before=p['remaining']*min(t-1,full)/full
            unop=1-(f+oldf)/2
            cap_interest+=(cap0*p['spent']/original_cip+.024*.8*(paid_before+spend/2))*unop
            growth_cap+=spend
            minor_in+=.2*spend*(1-p['own'])
            parent_inject+=.2*spend*p['own']
            renewable=p.get('renew',False)
            volume=p['gw']*(par['renew_hours'] if renewable else par['hours'])/100*f
            price=par['renew_price'] if renewable else par['price']
            cashcost=par['renew_cash'] if renewable else par['cash_unit']
            da=p['budget']/(20 if renewable else 40)*f
            ebit=volume*(price-cashcost)-da
            refund=volume*price*.03 if p['vat'] and t-first<10 else 0.
            op_new+=ebit;common_op_new+=ebit*p['own'];da_new+=da
            vat+=refund;common_vat+=refund*p['own']
            maint_new+=da*min(1,.5+max(0,t-first)*.05)
            contributions.append(dict(name=p['name'],operating_fraction=f,revenue=volume*price,ebit=ebit,depreciation=da,vat_refund=refund,capex=spend,owned_operating_profit=ebit*p['own']))
        old_change=1910.16*par['existing_price_change']+par['recovery']*min(1,t/3)-26.5566913547*min(1,t/10)-par['structural_loss']-(12 if t<=par['weak_years'] else 0)
        extra_capitalized=cap_interest*(par['new_rate']/.024-1)
        cap_interest+=extra_capitalized
        extra_da=cumulative_extra_capitalized/40
        cumulative_extra_capitalized+=extra_capitalized
        growth_cap+=extra_capitalized
        parent_inject+=extra_capitalized*.2*.53
        minor_in+=extra_capitalized*.2*.47
        da_new+=extra_da
        op_new-=extra_da
        common_op_new-=extra_da*.53
        ordinary_coupon=.3
        da=old_da+da_new
        maintenance=old_da*min(1,.5+t*.05)+maint_new
        capex=growth_cap+maintenance
        extra_payment=par['payment_extra'] if t==1 else 0.
        wc=10. if t<=10 else 0.
        cash_rebuild=160.-GROUP_CASH_AFTER_OLD_DIV if t==1 else 0.
        # 经济上划预算，不虚构各子公司法定余额；本金回收不新增利润。
        net_parent_loan=par['parent_loan_annual'] if t<=5 else -min(parent_loans,max(0,rows[-1]['group_earnings']+rows[-1]['depreciation']-rows[-1]['capex']-rows[-1]['dividend']-rows[-1]['minority_distribution'])*.3)
        avg_parent_loans=parent_loans+net_parent_loan/2
        newdebt=debt;newparent=parent_debt
        for _ in range(100):
            avg_debt=(debt+newdebt)/2
            gross=gross0+(avg_debt-DEBT0)*par['new_rate']+(par['new_rate']-.024)*DEBT0*min(t/5,1)
            interest=max(0,gross-cap_interest)
            interest_delta=interest-66.6217166852
            parent_interest_delta=par['new_rate']*((parent_debt+newparent)/2-204.590962185-avg_parent_loans)
            old_refund_exit=26.5566913547*min(1,t/10)
            net=old_group+.75*(old_change+op_new-interest_delta)+vat-.25*old_refund_exit
            common=old_common+.75*(old_change*old_share+common_op_new-interest_delta*.53-parent_interest_delta*.47)+common_vat-ordinary_coupon-.25*old_refund_exit*old_share
            minority=net-common-ordinary_coupon
            d=min(D0[t-1]*S,max(0,common)*.50) if t<=5 else max(0,common)*(.45 if t<=10 else .60)
            md=max(0,minority)*(.50 if t<=10 else .60)
            declared=par['upstream_ratio']*max(0,common+5+parent_interest_delta)
            upstream=declared*(1-par['upstream_delay'])+deferred_upstream
            next_deferred=declared*par['upstream_delay']
            p_expense=5+parent_interest_delta
            release=PARENT_CASH_AFTER_OLD_DIV-40. if t==1 else 0.
            upstream=max(0,min(upstream,parent_debt+parent_inject+net_parent_loan+d+p_expense-release))
            declared=min(declared,upstream+next_deferred-deferred_upstream)
            np=parent_debt+parent_inject+net_parent_loan+d+p_expense-upstream-release
            nd=debt+capex+d+md+ordinary_coupon-net-da+wc+cash_rebuild-minor_in+extra_payment
            if abs(nd-newdebt)+abs(np-newparent)<1e-10:break
            newdebt,newparent=nd,np
        assert newparent>=-1e-7 and newdebt>0
        assert newparent<800 and newdebt<7500, '融资预算超出可约束区间，须重新安排投入或分配'
        legal_profit_budget=declared-p_expense
        legal_retention=min(max(0,legal_profit_budget)*.10,max(0,statutory_cap-parent_statutory))
        parent_statutory+=legal_retention
        legal_available=parent_reserve+legal_profit_budget-legal_retention
        assert d<=legal_available+1e-7
        parent_reserve=legal_available-d
        deferred_upstream=next_deferred
        bnext=b+common-d
        mnext=m+minority-md+minor_in
        assert abs((net+da-wc+minor_in+newdebt-debt-cash_rebuild)-(capex+d+md+ordinary_coupon+extra_payment))<1e-7
        assert abs(parent_debt+parent_inject+net_parent_loan+d+p_expense-upstream-release-newparent)<1e-7
        assert abs((bnext-b)+(mnext-m)+(newdebt-debt)-(capex-da+wc+cash_rebuild+extra_payment))<1e-7
        rows.append(dict(year=t,common_earnings=common,group_earnings=net,minority_earnings=minority,dividend=d,dividend_per_share=d/S,common_equity_start=b,common_equity_end=bnext,minority_equity_end=mnext,debt_end=newdebt,parent_debt_end=newparent,parent_upstream=upstream,parent_injection=parent_inject,parent_net_loan=net_parent_loan,parent_loan_balance=parent_loans+net_parent_loan,parent_net_expense=p_expense,interest_expensed=interest,interest_capitalized=cap_interest,gross_interest=gross,capex=capex,growth_capex=growth_cap,maintenance_capex=maintenance,depreciation=da,working_capital=wc,cash_reserve_rebuild=cash_rebuild,group_cash_end=160.,parent_cash_end=40.,parent_legal_profit_budget=legal_profit_budget,parent_legal_retention_budget=legal_retention,parent_reserve_budget=parent_reserve,parent_deferred_dividend=deferred_upstream,accelerated_payable_settlement=extra_payment,operating_payables_end=354.979140761-sum(r.get('accelerated_payable_settlement',0) for r in rows)-extra_payment,minority_new_capital=minor_in,minority_distribution=md,projects=contributions))
        b,m,debt,parent_debt=bnext,mnext,newdebt,newparent
        parent_loans+=net_parent_loan
    e21=rows[-1]['common_earnings']*(1+par['g'])
    val=valuation(B0,[r['common_earnings'] for r in rows],[r['dividend'] for r in rows],par['k'],par['g'],S)
    d21,tv20,pv_d,value,tv5,ri_value,ri,terminal_ri=[val[z] for z in ('next_dividend','terminal_total','pv_distributions','value','terminal5','ri_value','ri_explicit','ri_terminal')]
    terminal_assets=b+m+debt
    terminal_capex=da*(1+par['g'])+par['g']*terminal_assets
    return dict(parameters=par,projects=projects,rows=rows,value=value,ri_value=ri_value,terminal_year5=tv5,terminal_year20_total=tv20,terminal_profit_year21=e21,terminal_dividend_year21=d21,terminal_roe=e21/b,terminal_payout=d21/e21,terminal_capex=terminal_capex,terminal_present_share=tv20/(1+par['k'])**years/S/value,first5_terminal_present_share=tv5/(1+par['k'])**5/value,pv_dividends=pv_d/S,ri_explicit_pv=ri,ri_terminal_pv=terminal_ri/(1+par['k'])**years)

def main():
    scenarios={'low':LOW,'base':BASE,'high':HIGH,
      'cyclical':{**BASE,'weak_years':2,'delay':1,'overrun':1.06,'new_rate':.027,'upstream_ratio':.7,'upstream_delay':.25},
      'structural':{**LOW,'price':.30,'hours':6800,'cash_unit':.145,'existing_price_change':-.02,'overrun':1.20,'delay':2,'renew_price':.27,'renew_hours':1700,'renew_ownership':.40,'upstream_ratio':.65,'new_rate':.033,'structural_loss':5.},
      'upside':{**HIGH,'price':.345,'hours':7600,'renew_price':.32,'renew_hours':2100,'renew_ownership':.6271,'upstream_ratio':.9},
      'price_minus_cent':{**BASE,'price':.323,'existing_price_change':-.0125},
      'rate_plus_100bp':{**BASE,'new_rate':.034},
      'parent_cash_pressure':{**BASE,'parent_loan_annual':80.,'upstream_ratio':.65,'upstream_delay':.25},
      'accelerated_payables':{**BASE,'payment_extra':50.},
      'q3_paid_110':{**BASE,'q3_growth_paid':110.},
      'q3_paid_170':{**BASE,'q3_growth_paid':170.}}
    out={name:model(p) for name,p in scenarios.items()}
    a=valuation(100,[8]*20,[8]*20,.08,0,1)
    assert abs(a['value']-100)<1e-9 and abs(a['terminal5']-100)<1e-9
    c=valuation(100,[10]*20,[8]*20,.10,0,1)
    hand=sum(8/1.1**t for t in range(1,21))+100/1.1**20
    assert abs(c['value']-hand)<1e-9
    out['tests']={'same_function_book_equals_value':a['value'],'retained_capital_case_value':c['value'],'retained_case_independent_hand':hand}
    out['source_inputs']={'shares':S,'common_equity':B0,'minority_equity':M0,'debt_proxy':DEBT0,'q3_profit_common':60.660476185,'q3_profit_group':120.4824133592,'cash_post_paid_dividend':GROUP_CASH_AFTER_OLD_DIV,'parent_cash_post_paid_dividend':PARENT_CASH_AFTER_OLD_DIV}
    out['convergence']={str(n):model(BASE,n)['value'] for n in (20,30,40)}
    out['summary']={name:{k:v[k] for k in ('value','terminal_year5','terminal_roe','terminal_payout','terminal_capex','terminal_present_share')} for name,v in out.items() if isinstance(v,dict) and 'value' in v}
    out['summary']['distributions']=[r['dividend_per_share'] for r in out['base']['rows'][:5]]
    Path(__file__).with_name('2026-Q3-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
    print(json.dumps(out['summary'],ensure_ascii=False,indent=2))
if __name__=='__main__':main()
