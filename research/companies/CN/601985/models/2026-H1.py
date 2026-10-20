"""中国核电普通股模型。标准库、离线；亿元/GW/亿股。参数均为研究预算。"""
import json, copy
from pathlib import Path
S=205.680
B0=1184.23
M0=1133.13
DEBT0=4916.10
D0=[.15,.16,.18,.19,.21]
PAID_OLD_DIVIDEND=32.8223837072
GROUP_CASH_AFTER_OLD_DIV=184.32-PAID_OLD_DIVIDEND
PARENT_CASH_AFTER_OLD_DIV=76.34-PAID_OLD_DIVIDEND
# first: 首个50%年度的相对周年，随后一个年度达到100%。容量是校准至披露总量的组合估计。
PROJECTS=[
 dict(name='田湾7、8',budget=466.7883,spent=397.9091,gw=2.53,own=.50,first=1,vat=True),
 dict(name='徐大堡3、4',budget=482.6090,spent=378.3657,gw=2.55,own=.54,first=2,vat=True),
 dict(name='三门3、4',budget=461.7521,spent=317.7687,gw=2.50,own=.56,first=2,vat=True),
 dict(name='徐大堡1、2',budget=389.3578,spent=245.3087,gw=2.50,own=.54,first=3,vat=True),
 dict(name='漳州3、4',budget=360.9005,spent=149.7120,gw=2.42,own=.51,first=4,vat=True),
 dict(name='金七门1、2',budget=414.4716,spent=158.8516,gw=2.46,own=.51,first=5,vat=True),
 dict(name='徐圩一期',budget=678.7293,spent=127.1264,gw=3.09,own=.46,first=6,vat=True),
 dict(name='三门5、6',budget=405.1699,spent=63.0218,gw=2.50,own=.56,first=6,vat=True),
 # 无法分拆的其他在建与新核准组合：全部旧账面纳入资本，不反复扣旧投入。
 dict(name='其他在建/海南小堆及新核准组合',budget=1410.5079,spent=510.5079,gw=5.085,own=.51,first=8,vat=False),
 dict(name='在建风光',budget=400.,spent=206.0095,gw=9.2406,own=.6271,first=2,vat=False,renew=True),
]
BASE=dict(k=.086,g=.0075,price=.333,cash_unit=.135,hours=7300,new_rate=.024,existing_price_change=-.0025,recovery=5.,overrun=1.,delay=0,renew_price=.30,renew_hours=1900,renew_cash=.07,pool_remaining=900.,parent_loan_annual=60.,upstream_ratio=.9,other_initial_capi=10.)
LOW={**BASE,'k':.092,'g':.005,'price':.325,'cash_unit':.14,'hours':7100,'new_rate':.026,'existing_price_change':-.005,'recovery':0.,'overrun':1.04,'renew_price':.29,'renew_hours':1800,'other_initial_capi':15.}
HIGH={**BASE,'k':.08,'g':.01,'price':.34,'cash_unit':.13,'hours':7500,'new_rate':.022,'existing_price_change':0.,'recovery':10.,'overrun':1.,'renew_price':.31,'renew_hours':2000,'other_initial_capi':5.}
def model(par):
    projects=copy.deepcopy(PROJECTS)
    for p in projects:
        if p['name'].startswith('其他'):p['budget']=p['spent']+par['pool_remaining']
        p['budget']=p['spent']+(p['budget']-p['spent'])*par['overrun']
        p['first']+=par['delay']
        p['remaining']=p['budget']-p['spent']
    b,m,debt=B0,M0,DEBT0
    parent_debt=186.53
    parent_loans=0.
    rows=[]
    cumulative_extra_capitalized=0.
    original_cip=sum(p['spent'] for p in projects)
    # 历史总利息=费用化67.5731+八大项目资本化35.3932。
    gross0=67.573143183+35.393165244+par['other_initial_capi']
    cap0=35.393165244+par['other_initial_capi']
    old_da=2*(107.850361536+2.461898966+2.874038899+.985422893)
    old_common=2*36.4115373488
    old_group=2*71.0890777095
    old_share=old_common/old_group
    for t in range(1,21):
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
            # VAT退税按收入3%的保守净现金近似，仅旧核准核电前10年，免所得税。
            refund=volume*price*.03 if p['vat'] and t-first<10 else 0.
            op_new+=ebit;common_op_new+=ebit*p['own'];da_new+=da
            vat+=refund;common_vat+=refund*p['own']
            maint_new+=da*min(1,.5+max(0,t-first)*.05)
            contributions.append(dict(name=p['name'],operating_fraction=f,revenue=volume*price,ebit=ebit,depreciation=da,vat_refund=refund,capex=spend,owned_operating_profit=ebit*p['own']))
        # 原有VAT与其他补助24.63亿元：十年退出，终态不永续；新项目另算且到期退出。
        old_change=1832.18*par['existing_price_change']+par['recovery']*min(1,t/3)-24.6306468274*min(1,t/10)
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
        wc=10. if t<=10 else 0.
        cash_rebuild=PAID_OLD_DIVIDEND if t==1 else 0.
        if t==1:
            assert abs(GROUP_CASH_AFTER_OLD_DIV+cash_rebuild-184.32)<1e-10
            assert abs(PARENT_CASH_AFTER_OLD_DIV+(50-PARENT_CASH_AFTER_OLD_DIV)-50)<1e-10
        # Mother statutory cash: 子公司净收益90%上划，前五年合计50亿元既有储备释放。
        # Parent incremental interest from borrowing is charged 100% to common, not project ownership.
        net_parent_loan=par['parent_loan_annual'] if t<=5 else (-par['parent_loan_annual'] if t<=10 else 0.)
        avg_parent_loans=parent_loans+net_parent_loan/2
        newdebt=debt;newparent=parent_debt
        for _ in range(100):
            avg_debt=(debt+newdebt)/2
            gross=gross0+(avg_debt-DEBT0)*par['new_rate']+(par['new_rate']-.024)*DEBT0*min(t/5,1)
            interest=max(0,gross-cap_interest)
            interest_delta=interest-67.573143183
            parent_interest_delta=par['new_rate']*((parent_debt+newparent)/2-186.53-avg_parent_loans)
            old_refund_exit=24.6306468274*min(1,t/10)
            net=old_group+.75*(old_change+op_new-interest_delta)+vat-.25*old_refund_exit
            common=old_common+.75*(old_change*old_share+common_op_new-interest_delta*.53-parent_interest_delta*.47)+common_vat-ordinary_coupon-.25*old_refund_exit*old_share
            minority=net-common-ordinary_coupon
            d=D0[t-1]*S if t<=5 else max(0,common)*(.45 if t<=10 else .60)
            md=max(0,minority)*(.50 if t<=10 else .60)
            upstream=par['upstream_ratio']*max(0,common+5+parent_interest_delta)+(10 if t<=5 else 0)
            p_expense=5+parent_interest_delta
            release=PARENT_CASH_AFTER_OLD_DIV-50. if t==1 else 0.
            upstream=min(upstream,parent_debt+parent_inject+net_parent_loan+d+p_expense-release)
            np=parent_debt+parent_inject+net_parent_loan+d+p_expense-upstream-release
            nd=debt+capex+d+md+ordinary_coupon-net-da+wc+cash_rebuild-minor_in
            if abs(nd-newdebt)+abs(np-newparent)<1e-10:break
            newdebt,newparent=nd,np
        assert newparent>=-1e-7 and newdebt>0
        bnext=b+common-d
        mnext=m+minority-md+minor_in
        # 现金守恒，资本化利息已经含在建设预算，不从净利润第二次扣。
        assert abs((net+da-wc+minor_in+newdebt-debt-cash_rebuild)-(capex+d+md+ordinary_coupon))<1e-7
        assert abs(parent_debt+parent_inject+net_parent_loan+d+p_expense-upstream-release-newparent)<1e-7
        # 总资本守恒（普通及少数权益+债务）；永续固定，不重复扣本金。
        assert abs((bnext-b)+(mnext-m)+(newdebt-debt)-(capex-da+wc+cash_rebuild))<1e-7
        rows.append(dict(year=t,common_earnings=common,group_earnings=net,minority_earnings=minority,dividend=d,dividend_per_share=d/S,common_equity_start=b,common_equity_end=bnext,minority_equity_end=mnext,debt_end=newdebt,parent_debt_end=newparent,parent_upstream=upstream,parent_injection=parent_inject,parent_net_loan=net_parent_loan,parent_loan_balance=parent_loans+net_parent_loan,parent_net_expense=p_expense,interest_expensed=interest,interest_capitalized=cap_interest,gross_interest=gross,capex=capex,growth_capex=growth_cap,maintenance_capex=maintenance,depreciation=da,working_capital=wc,cash_reserve_rebuild=cash_rebuild,group_cash_end=184.32,parent_cash_end=50.,minority_new_capital=minor_in,minority_distribution=md,projects=contributions))
        b,m,debt,parent_debt=bnext,mnext,newdebt,newparent
        parent_loans+=net_parent_loan
    # 第21年正常经营：已无新项目税收优惠。权益以g增长，需留存g*B，不独立指定ROE/分红。
    e21=rows[-1]['common_earnings']*(1+par['g'])
    d21=e21-par['g']*b
    tv20=d21/(par['k']-par['g'])
    pv_d=sum(r['dividend']/(1+par['k'])**r['year'] for r in rows)
    value=(pv_d+tv20/(1+par['k'])**20)/S
    tv5=(sum(r['dividend']/(1+par['k'])**(r['year']-5) for r in rows[5:])+tv20/(1+par['k'])**15)/S
    ri=sum((r['common_earnings']-par['k']*r['common_equity_start'])/(1+par['k'])**r['year'] for r in rows)
    terminal_ri=(e21-par['k']*b)/(par['k']-par['g'])
    ri_value=(B0+ri+terminal_ri/(1+par['k'])**20)/S
    assert abs(value-ri_value)<1e-9
    assert abs(value-(sum(D0[i]/(1+par['k'])**(i+1) for i in range(5))+tv5/(1+par['k'])**5))<1e-9
    # 稳态资本：净经营资金=债务+普通权益+少数权益；增长投资匹配各资金来源。
    terminal_assets=b+m+debt+10
    terminal_capex=da+par['g']*terminal_assets
    return dict(parameters=par,projects=projects,rows=rows,value=value,ri_value=ri_value,terminal_year5=tv5,terminal_year20_total=tv20,terminal_profit_year21=e21,terminal_dividend_year21=d21,terminal_roe=e21/b,terminal_payout=d21/e21,terminal_capex=terminal_capex,terminal_present_share=tv20/(1+par['k'])**20/S/value,first5_terminal_present_share=tv5/(1+par['k'])**5/value,pv_dividends=pv_d/S,ri_explicit_pv=ri,ri_terminal_pv=terminal_ri/(1+par['k'])**20)
def main():
    out={key:model(p) for key,p in [('low',LOW),('base',BASE),('high',HIGH)]}
    out['sensitivities']={}
    variants={
      'price_minus_one_cent':{**BASE,'price':BASE['price']-.01,'existing_price_change':BASE['existing_price_change']-.01},
      'interest_plus_100bp':{**BASE,'new_rate':BASE['new_rate']+.01},
      'completion_delay_two_years':{**BASE,'delay':2},
      'remaining_construction_plus_20pct':{**BASE,'overrun':1.2},
      'other_pool_extra_300':{**BASE,'pool_remaining':1200.},
      'parent_upstream_70pct':{**BASE,'upstream_ratio':.7},
      'parent_extra_net_loans_60':{**BASE,'parent_loan_annual':120.},
      'structural_weak':{**LOW,'price':.30,'cash_unit':.145,'hours':6800,'existing_price_change':-.02,'overrun':1.2,'delay':2},
    }
    for name,p in variants.items():
        r=model(p);out['sensitivities'][name]={'value':r['value'],'change_from_base':r['value']-out['base']['value'],'terminal_year5':r['terminal_year5'],'common_earnings_y5':r['rows'][4]['common_earnings'],'debt_y5':r['rows'][4]['debt_end'],'parent_debt_peak':max(z['parent_debt_end'] for z in r['rows'])}
    # 普通股账面与未来收益的已知特例：ROE=k、全部分红时公允价值=账面。
    assert abs((100*.08)/.08-100)<1e-10
    Path(__file__).with_name('2026-H1-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    for k in ['low','base','high']:
        x=out[k];print(k, {z:round(x[z],5) for z in ['value','terminal_year5','terminal_roe','terminal_payout','terminal_capex','terminal_present_share']})
        for t in [1,3,5,10,20]:
            r=x['rows'][t-1];print(t,{z:round(r[z],2) for z in ['common_earnings','dividend_per_share','debt_end','parent_debt_end','interest_expensed','interest_capitalized','growth_capex','capex','parent_upstream','parent_injection']})
    print(out['sensitivities'])
if __name__=='__main__':main()
