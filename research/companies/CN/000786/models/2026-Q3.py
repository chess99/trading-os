#!/usr/bin/env python3
"""BNBM 2026Q3; stdlib, deterministic. Money=CNY billion, shares=billion.
Forecast dates are successive 12-month anniversaries of 2026-10-26.
Only the real parent has a statutory ledger. Subsidiary transfers are explicitly
conditional economic budgets. legacy_simulation is comparison-only and contains
the rejected synthetic statutory source pools; it is never the current model.
"""
import json, math, copy
from pathlib import Path
INPUT={'asof': '2026-10-26T00:00:00+08:00',
 'shares': 1.697823974,
 'liquid_consolidated': 4.13972111738,
 'minority_liquid': 0.1,
 'debt_components': {'short': 0.41266416026,
                     'long': 0.15804510242,
                     'current_noncurrent': 0.08298035033,
                     'lease': 0.13135629318,
                     'commercial_paper': 1.0,
                     'related_loan': 0.15035},
 'minority_debt': 0.03,
 'parent_cash': 2.8,
 'parent_debt': 1.0,
 'parent_retained': 2.5585150299,
 'parent_reserve': 0.8704664345,
 'parent_capital': 1.697823974,
 'parent_own_operating_profit': -0.1,
 'pool_parent_payable': 10.0,
 'pool_parent_receivable': 2.8,
 'old_dividend_receivable': 0.159,
 'pool_interest': 0.02,
 'pool_repayment': 0.5,
 'loan_collection': 0.3,
 'old_dividend_collection_year': 1,
 'parent_cash_yield': 0.02,
 'sub_cash_yield': 0.02,
 'sub_tax': 0.1,
 'parent_tax': 0.25,
 'debt_rate': 0.03,
 'new_debt_rate': 0.035,
 'parent_cash_floor': 0.3,
 'sub_cash_floor': 0.8,
 'parent_new_debt_limit': 2.5,
 'sub_new_debt_limit': 1.0,
 'taishan_light_profit_fraction': 0.85,
 'taishan_legal_profit_conversion': 0.7,
 'taishan_capital': 0.155625,
 'taishan_start_reserve': 0.0,
 'taishan_start_retained': 3.0,
 'other_legal_capital_common': {'light':2.0,'waterproof':1.0,'coatings':1.0},
 'other_legal_start_reserve': 0.0,
 'mature_upstream_ramp': [.2,.4,.6,.8,1.0],
 'historical_retained_budget': '3bn common-owned source, budget not reported individual statutory balance;0/6bn sensitivity',
 'taishan_cash_share': 0.8,
 'unpaid_acquisition': 0.81699029771,
 'acquisition_settlement': [0.4, 0.41699029771, 0, 0, 0, 0, 0, 0, 0, 0],
 'nonoperating_assets': {'financial_assets': 0.06725058679, 'associates_book': 0.14303061780, 'associates_recovery_factor': 1.0},
 'committed_growth_capex_common': [0.55, 0.5, 0.25, 0, 0, 0, 0, 0, 0, 0],
 'restricted_refund': [0.071114680725, 0.071114680725, 0, 0, 0, 0, 0, 0, 0, 0],
 'restricted_cancel': [0.004158066, 0.004158066, 0, 0, 0, 0, 0, 0, 0, 0],
 'payout': 0.4,
 'first_year_cash_dividend': 0.9,
 'terminal_g_low': 0.005,
 'terminal_g_high': 0.01,
 'terminal_incremental_roic': 0.1,
 'discount_low_value': 0.1,
 'discount_high_value': 0.09,
 'segments': {'light': {'opening_revenue': 15.0,
                        'growth': [0, 0.01, 0.02, 0.02, 0.02, 0.02, 0.02, 0.015, 0.015, 0.01],
                        'margin': [0.145, 0.15, 0.155, 0.16, 0.16, 0.16, 0.1575, 0.155, 0.1525, 0.15],
                        'tax': 0.1,
                        'common_fraction': 0.995,
                        'opening_capital': 18.5,
                        'da_rate': 0.06,
                        'maintenance_over_da': 1.0,
                        'fixed_growth_capital_per_sales': 0.35,
                        'working_capital_per_sales': 0.12,
                        'acquisition': [0.05, 0.05, 0.05, 0, 0, 0, 0, 0, 0, 0]},
              'waterproof': {'opening_revenue': 5.3,
                             'growth': [0.04, 0.04, 0.04, 0.03, 0.03, 0.025, 0.025, 0.02, 0.015, 0.01],
                             'margin': [0.08, 0.082, 0.085, 0.085, 0.085, 0.085, 0.083, 0.082, 0.081, 0.08],
                             'tax': 0.15,
                             'common_fraction': 0.95,
                             'opening_capital': 3.6,
                             'da_rate': 0.022,
                             'maintenance_over_da': 1.05,
                             'fixed_growth_capital_per_sales': 0.35,
                             'working_capital_per_sales': 0.45,
                             'acquisition': [0.1, 0.1, 0.05, 0.05, 0, 0, 0, 0, 0, 0]},
              'coatings': {'opening_revenue': 4.5,
                           'growth': [0.05, 0.05, 0.04, 0.04, 0.03, 0.03, 0.025, 0.02, 0.015, 0.01],
                           'margin': [0.08, 0.085, 0.09, 0.095, 0.095, 0.095, 0.0925, 0.09, 0.0875, 0.085],
                           'tax': 0.15,
                           'common_fraction': 0.8,
                           'opening_capital': 4.2,
                           'da_rate': 0.04,
                           'maintenance_over_da': 1.0,
                           'fixed_growth_capital_per_sales': 0.4,
                           'working_capital_per_sales': 0.25,
                           'acquisition': [0.1, 0.1, 0.05, 0.05, 0, 0, 0, 0, 0, 0]}},
 'scenarios': {'base': {'growth_delta': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                        'margin_delta': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                        'wc_extra': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                        'description': '缓慢修复，三业务全部自Y1生效；母子资金池正常净结算；不纳入额外大并购'},
               'cyclical_weak': {'growth_delta': [-0.08, -0.03, 0.04, 0.03, 0.01, 0, 0, 0, 0, 0],
                                 'margin_delta': [-0.025, -0.015, -0.005, 0, 0, 0, 0, 0, 0, 0],
                                 'wc_extra': [0.8, 0.3, -0.5, -0.3, -0.3, 0, 0, 0, 0, 0],
                                 'description': 'Y1-2需求/回款低迷；Y3-5部分恢复，资本开支仍维护；母子金融与法定链逐年重算'},
               'structural_adverse': {'growth_delta': [-0.06, -0.05, -0.04, -0.03, -0.02, -0.02, -0.02, -0.015, -0.015, -0.01],
                                      'margin_delta': [-0.04, -0.04, -0.04, -0.04, -0.04, -0.04, -0.04, -0.04, -0.04, -0.04],
                                      'wc_extra': [0.5, 0.3, 0.2, 0, 0, 0, 0, 0, 0, 0],
                                      'terminal_g': 0,
                                      'terminal_roic': 0.07,
                                      'description': '自Y1价格和渠道信用永久恶化，十年收入不回峰值，长期零增长；无自动利润率修复'},
               'optimistic': {'growth_delta': [0.02, 0.02, 0.02, 0.02, 0.02, 0.01, 0.01, 0.01, 0.01, 0.01],
                              'margin_delta': [0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01],
                              'wc_extra': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                              'description': '自Y1存量装修/海外兑现，售价企稳与利用率提升；增长资本同步增加'},
               'light_margin_minus_2pp': {'growth_delta': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                                          'margin_delta': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                                          'wc_extra': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                                          'light_margin_extra': -0.02,
                                          'description': '单因素诊断：仅轻质经营利润率永久减2个百分点；仍重算法定与现金，不是独立全经济路径'},
               'pool_cash_stress': {'growth_delta': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                                    'margin_delta': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                                    'wc_extra': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                                    'pool_repayment': 1.5,
                                    'loan_collection': 0.1,
                                    'old_dividend_collection_year': 3,
                                    'description': 'Y1-5母每年净多付资金池1.4，对比基准.2；旧应收股利延至Y3；D先调低再有限借款'},
               'full_dilution_diagnostic': {'growth_delta': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                                            'margin_delta': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                                            'wc_extra': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                                            'no_forfeit': True,
                                            'description': '互斥资本结构诊断：假设所有限制股保留且退款义务解除，不是符合当前业绩门槛的经营路径'}},
 'historical': {'columns': ['year', 'revenue', 'parent_profit', 'recurring_parent_profit', 'CFO', 'capex', 'ROE_pct', 'parent_equity'],
                'values': [[2021, 21.32494302757, 3.52158694711, 3.45813826519, 3.8639765244, None, 19.89, 19.05315962369],
                           [2022, 20.15470105891, 3.14441978848, 2.65270065706, 3.67681728644, 1.45296009882, 15.83, 21.07196888089],
                           [2023, 22.42589563699, 3.52400119359, 3.49505625046, 4.7343874898, 1.16230839989, 16.0, 23.36521292463],
                           [2024, 25.82112441948, 3.6469424704, 3.55801164429, 5.13446551562, 1.19403887099, 15.01, 25.67293720831],
                           [2025, 25.28026191822, 2.90638029166, 2.78027838168, 4.20394568237, 1.19247618632, 11.11, 27.16514588783]],
                'note': '2021/22利润收入/CFO采用2023年报追溯口径；2021capex尚不混入未经追溯原值'},
 'quarter': {'revenue_ytd': 19.07628175397,
             'parent_profit_ytd': 1.90480706702,
             'recurring_ytd': 1.86294771481,
             'cfo_ytd': 0.77652477099,
             'capex_ytd': 0.62034059533,
             'revenue_q3': 6.44491984626,
             'parent_profit_q3': 0.52936674093,
             'recurring_q3': 0.5451570393,
             'cfo_h1': 0.6849080178,
             'ar': 6.14265910128,
             'ar_prior_q3': 6.38435884979,
             'inventory': 2.60006909812,
             'inventory_prior_q3': 2.4528158349,
             'cost_ytd': 13.77597632501,
             'operating_profit_ytd': 2.1554659285,
             'minority_equity': 1.30477766109,
             'parent_equity': 27.88796073911},
 'auxiliary': {'method': 'earnings_power_no_growth',
               'segment_margin': [0.15, 0.08, 0.085],
               'discounts': [0.1, 0.11, 0.11],
               'debt_deduction': True,
               'note': '当前规模在充分维护下的无增长盈利能力；不加入增长/并购期权，和主要DCF有实质经济差异'}}

def legal(retained,reserve,capital,profit,desired,cash_available):
    """No capital-reserve loss offset assumed. Current profits first cover accumulated loss."""
    available=retained+profit
    levy=min(max(capital*.5-reserve,0),max(min(profit,available),0)*.1)
    available-=levy
    dividend=max(0,min(desired,available,cash_available))
    return {'retained':available-dividend,'reserve':reserve+levy,'levy':levy,'dividend':dividend,'pre_distribution_legal_profit':available}

def operate(prior_revenue,capital,s,y,sc):
    growth=s['growth'][y]+sc['growth_delta'][y]
    revenue=prior_revenue*(1+growth)
    margin=s['margin'][y]+sc['margin_delta'][y]+sc.get('segment_margin_extra',0)
    ebit=revenue*margin
    tax=max(0,ebit)*s['tax']
    nopat=ebit-tax
    da=revenue*s['da_rate']
    maintenance=da*s['maintenance_over_da']
    # A shrinking installed asset base is NOT assumed to be sold at book value.
    growth_fixed=max(0,revenue-prior_revenue)*s['fixed_growth_capital_per_sales']
    d_wc=(revenue-prior_revenue)*s['working_capital_per_sales']
    acquisition=s['acquisition'][y]
    invest=maintenance+growth_fixed+acquisition-da+d_wc
    return {'revenue':revenue,'growth':growth,'margin':margin,'ebit':ebit,'cash_tax':tax,'nopat':nopat,'da':da,'maintenance_capex':maintenance,'growth_capex':growth_fixed,'acquisition':acquisition,'working_capital_change':d_wc,'net_reinvestment':invest,'closing_operating_capital':capital+invest,'economic_common_profit':nopat*s['common_fraction'],'common_reinvestment':invest*s['common_fraction'],'economic_common_fcfe_unlevered':(nopat-invest)*s['common_fraction'],'common_fraction':s['common_fraction']}


def realize_asset(book,tax_basis,gross,cost,tax_rate):
    """Principal is cash; only proceeds minus accounting cost is profit. Loss gives no cash rebate."""
    gain=gross-cost-book;tax=max(0,gross-cost-tax_basis)*tax_rate
    return {'net_cash':gross-cost-tax,'accounting_gain':gain,'tax':tax,'book_removed':book,'tax_basis_removed':tax_basis}

def exit_waterfall(cash,noncash_assets,haircut,external_debt,exit_cost,tax_basis,ownership):
    r=realize_asset(noncash_assets,tax_basis,noncash_assets*(1-haircut),exit_cost,.25)
    assets=max(0,cash+r['net_cash']);paid=min(assets,external_debt)
    return dict(r,feasible=cash+r['net_cash']>=external_debt,unfunded_cost=max(0,-cash-r['net_cash']),external_debt_paid=paid,external_debt_shortfall=external_debt-paid,common_cash=max(0,assets-paid)*ownership)

def equity_issue(registered,pre_equity_value,ownership,new_parent,new_minority,price_to_book=1):
    """Pro-rata money at stated actual equity value; registered capital is not a valuation proxy."""
    new_equity=new_parent+new_minority
    return {'parent_fraction':(pre_equity_value*ownership+new_parent/price_to_book)/(pre_equity_value+new_equity/price_to_book),'cash_in':new_equity,'registered':registered*(1+new_equity/price_to_book/pre_equity_value)}

def capital_refund(shares,cash,refund,cancel):
    # Accounting booking inside annual settlement; simulation checks funded closure
    # after upstream collections and capped financing. This is not an authorization.
    assert 0<=cancel<=shares and refund>=0
    return {'shares':shares-cancel,'cash':cash-refund,'profit':0}

def cohort_audit(rows):
    # Every positive annual net cash generation creates a distinct cohort, even if
    # wholly paid out the SAME year. FIFO is an audit attribution, not a legal setoff.
    opening=INPUT['liquid_consolidated']-INPUT['minority_liquid']
    queue=[{'origin':0,'created':opening,'remaining':opening,'uses':[]}]
    for row in rows:
        generation=(row['common_net_profit']-row['common_reinvestment']-row['acquisition_payment']-row['forfeiture_cash']+row['new_parent_debt']+row['new_sub_debt']+row['nonoperating_realization']-row.get('asset_accounting_gain',0)+row.get('asset_sale_tax',0))
        if generation>0:queue.append({'origin':row['year'],'created':generation,'remaining':generation,'uses':[]})
        uses=[('operations_capital_obligations_net',max(0,-generation)),('external_debt_first',row['external_debt_repayment']),('ordinary_and_special_distribution',row['total_dividend'])]
        for label,use in uses:
            for q in queue:
                x=min(q['remaining'],use)
                if x>0:q['uses'].append({'year':row['year'],'amount':x,'purpose':label});q['remaining']-=x;use-=x
                if use<1e-10:break
            assert use<1e-7
        assert abs(sum(q['remaining'] for q in queue)-row['parent_cash']-row['sub_common_cash'])<1e-7
    return queue

def priced(sc,r,g,years=400,old=False):
    sim=(legacy_simulation if old else simulation)(sc,years,g)
    if not sim['feasible']:return sim
    rows=sim['rows'];pv=sum(a['dps']/(1+r)**a['year'] for a in rows)
    d5=sum(a['dps']/(1+r)**a['year'] for a in rows[:5]);tv=(pv-d5)*(1+r)**5
    return dict(feasible=True,pv=pv,tv5=tv,d5=d5,r=r,g=g,years=years,terminal_share=(pv-d5)/pv,after10_share=sum(a['dps']/(1+r)**a['year'] for a in rows[10:])/pv,tail_bound=(rows[-1]['total_dividend']*(1+g)+1)/(r-g)/rows[-1]['shares']/(1+r)**years,rows=rows,financial_cohorts=cohort_audit(rows))
def legacy_simulation(sc,years=10,steady_g=None):
    p=INPUT; segs=copy.deepcopy(p['segments']); rev={k:v['opening_revenue'] for k,v in segs.items()}; capital={k:v['opening_capital'] for k,v in segs.items()}
    cp=p['parent_cash']; cs=p['liquid_consolidated']-p['minority_liquid']-cp
    dp=p['parent_debt']; ds=sum(p['debt_components'].values())-p['minority_debt']-dp
    lp=p['pool_parent_payable']; lr=p['pool_parent_receivable']; old=p['old_dividend_receivable']; acquisition_payable=p['unpaid_acquisition']
    pr=p['parent_retained']; pres=p['parent_reserve']; tr=p['taishan_start_retained']; tres=p['taishan_start_reserve']; shares=p['shares']; prev_profit=0; rows=[]; accumulated_extra_capital=0
    other={k:{'retained':0.0,'reserve':p['other_legal_start_reserve']} for k in segs}
    equity=p['quarter']['parent_equity']
    nonop_remaining=p['nonoperating_assets']['financial_assets']+p['nonoperating_assets']['associates_book']*p['nonoperating_assets']['associates_recovery_factor']
    book_residual=equity-(sum(capital[k]*segs[k]['common_fraction'] for k in segs)+cp+cs-dp-ds-acquisition_payable+nonop_remaining)
    legal_equity_gap=equity-(pr+pres+tr+tres+sum(v['retained']+v['reserve'] for v in other.values()))
    for y in range(years):
        sr={}
        for k,s in segs.items():
            local=dict(sc); local['segment_margin_extra']=sc.get('light_margin_extra',0) if k=='light' else 0
            if y<10:
                sr[k]=operate(rev[k],capital[k],s,y,local)
            else:
                g=steady_g if steady_g is not None else sc.get('terminal_g',p['terminal_g_low']);roic=sc.get('terminal_roic',p['terminal_incremental_roic'])
                last=rows[-1]['segments'][k]; revenue=last['revenue']*(1+g);ebit=last['ebit']*(1+g);nopat=ebit-max(ebit,0)*s['tax'];da=revenue*s['da_rate'];growth_invest=nopat*g/roic;maintenance_extra=da*(s['maintenance_over_da']-1);investment=growth_invest+maintenance_extra
                sr[k]={'revenue':revenue,'growth':g,'margin':ebit/revenue,'ebit':ebit,'cash_tax':ebit-nopat,'nopat':nopat,'da':da,'maintenance_capex':da*s['maintenance_over_da'],'growth_capex':growth_invest*.6,'acquisition':0,'working_capital_change':growth_invest*.4,'net_reinvestment':investment,'closing_operating_capital':capital[k]+investment,'economic_common_profit':nopat*s['common_fraction'],'common_reinvestment':investment*s['common_fraction'],'economic_common_fcfe_unlevered':(nopat-investment)*s['common_fraction'],'common_fraction':s['common_fraction']}
            rev[k]=sr[k]['revenue'];capital[k]=sr[k]['closing_operating_capital']
        op=sum(v['economic_common_profit'] for v in sr.values()); invest=sum(v['common_reinvestment'] for v in sr.values())+(sc['wc_extra'][y] if y<10 else 0)
        generic_growth_capex=sum(v['growth_capex']*v['common_fraction'] for v in sr.values())
        committed_extra=max(0,(p['committed_growth_capex_common'][y] if y<10 else 0)-generic_growth_capex)
        invest+=committed_extra
        accumulated_extra_capital+=committed_extra+(sc['wc_extra'][y] if y<10 else 0)
        open_cp,open_cs,open_dp,open_ds=cp,cs,dp,ds
        pool_interest=lp*p['pool_interest']; lend_interest=lr*p['pool_interest']
        ip=cp*p['parent_cash_yield']; ist=cs*p['sub_cash_yield']; debt_ip=min(dp,p['parent_debt'])*p['debt_rate']+max(0,dp-p['parent_debt'])*p['new_debt_rate']; base_ds=sum(p['debt_components'].values())-p['minority_debt']-p['parent_debt']; debt_is=min(ds,base_ds)*p['debt_rate']+max(0,ds-base_ds)*p['new_debt_rate']
        p_pretax=p['parent_own_operating_profit']+ip+lend_interest-pool_interest-debt_ip
        taxp=max(0,p_pretax)*p['parent_tax'] # dividend is exempt; a loss gives NO immediate shield
        finance_sub=ist+pool_interest-lend_interest-debt_is
        taxs=(max(0,sr['light']['ebit']+finance_sub)-max(0,sr['light']['ebit']))*p['sub_tax'] # treasury assigned to profitable light taxpayer; loss itself gives no cash credit
        p_own_np=p_pretax-taxp; s_np=op+finance_sub-taxs
        common_np=p_own_np+s_np
        cp+=p_own_np; cs+=s_np-invest
        repay=min(lp,sc.get('pool_repayment',p['pool_repayment'])) 
        collect=min(lr,sc.get('loan_collection',p['loan_collection'])) 
        old_collect=old if y+1==sc.get('old_dividend_collection_year',p['old_dividend_collection_year']) else 0
        cp+=collect-repay+old_collect;cs+=repay-collect-old_collect;lp-=repay;lr-=collect;old-=old_collect
        acquisition_payment=min(acquisition_payable,(p['acquisition_settlement'][y] if y<10 else 0));acquisition_payable-=acquisition_payment;cp-=acquisition_payment
        forfeiture=0
        if not sc.get('no_forfeit'):
            forfeiture=(p['restricted_refund'][y] if y<10 else 0)
            action=capital_refund(shares,cp,forfeiture,(p['restricted_cancel'][y] if y<10 else 0));cp=action['cash'];shares=action['shares']
        # Surplus release begins only after committed projects/acquisition payments finish;
        # a five-year ramp models routing newly consolidated wings, not an instant legal waiver.
        ramp=0 if y<5 else p['mature_upstream_ramp'][min(y-5,4)]
        debt_pay_s=min(ds,max(0,cs-p['sub_cash_floor'])*ramp);cs-=debt_pay_s;ds-=debt_pay_s
        tprofit=sr['light']['nopat']*p['taishan_light_profit_fraction']*p['taishan_legal_profit_conversion']
        cash_available=max(0,cs-p['sub_cash_floor'])*p['taishan_cash_share']
        desired_t=tprofit+max(0,tr)*ramp
        upstream=legal(tr,tres,p['taishan_capital'],tprofit,desired_t,cash_available)
        tr,tres=upstream['retained'],upstream['reserve']; u=upstream['dividend'];cp+=u;cs-=u
        other_states={};other_upstream=0
        for k in segs:
            source_profit=sr[k]['economic_common_profit']
            if k=='light':source_profit+=finance_sub-taxs-tprofit
            a=other[k]
            desired_o=max(0,a['retained']+source_profit)*ramp
            ol=legal(a['retained'],a['reserve'],p['other_legal_capital_common'][k],source_profit,desired_o,max(0,cs-p['sub_cash_floor']))
            other[k]={'retained':ol['retained'],'reserve':ol['reserve']}; other_states[k]=dict(ol,profit=source_profit,capital=p['other_legal_capital_common'][k])
            cs-=ol['dividend'];cp+=ol['dividend'];other_upstream+=ol['dividend']
        u+=other_upstream
        asset_realization=0
        if y==9:
            asset_realization=p['nonoperating_assets']['financial_assets']+p['nonoperating_assets']['associates_book']*p['nonoperating_assets']['associates_recovery_factor'];cp+=asset_realization
        debt_pay_p=min(dp,max(0,cp-p['parent_cash_floor'])*ramp);cp-=debt_pay_p;dp-=debt_pay_p
        desired=p['first_year_cash_dividend'] if y==0 else max(0,prev_profit*p['payout'])
        # First reduce ordinary D, then use finite external financing ONLY to restore operating liquidity.
        available=max(0,min(cp-p['parent_cash_floor'],cp+cs-p['parent_cash_floor']-p['sub_cash_floor']))
        pl=legal(pr,pres,shares,p_own_np+u,desired,available);d=pl['dividend'];pr,pres=pl['retained'],pl['reserve'];cp-=d
        special=0
        if ramp:
            # Ordinary D has already consumed THIS retained-profit ledger. No principal unlock twice.
            special=max(0,min(pr,max(0,cp-p['parent_cash_floor'])))*ramp
            pr-=special;cp-=special
            pl['retained']=pr
        total_d=d+special
        newp=max(0,p['parent_cash_floor']-cp);news=max(0,p['sub_cash_floor']-cs)
        if dp+newp-p['parent_debt']>p['parent_new_debt_limit']+1e-9 or ds+news-(sum(p['debt_components'].values())-p['minority_debt']-p['parent_debt'])>p['sub_new_debt_limit']+1e-9:
            return {'feasible':False,'failed_year':y+1,'failure':'zero/capped dividend still insufficient with finite financing','rows':rows,'cash_before_unfunded':[cp,cs],'additional_debt_needed':[newp,news]}
        cp+=newp;cs+=news;dp+=newp;ds+=news
        # No new shareholder equity, no imaginary increase in legal reserve ceiling.
        error=(cp+cs-open_cp-open_cs)-(common_np-invest-total_d-forfeiture-acquisition_payment+newp+news-debt_pay_p-debt_pay_s+asset_realization)
        assert abs(error)<1e-8
        assert cp>=p['parent_cash_floor']-1e-9 and cs>=p['sub_cash_floor']-1e-9
        rows.append({'year':y+1,'segments':sr,'common_operating_profit':op,'common_operating_capital_end':sum(capital[k]*segs[k]['common_fraction'] for k in segs)+accumulated_extra_capital,'common_reinvestment':invest,'wc_stress_change':(sc['wc_extra'][y] if y<10 else 0),'committed_project_extra_capex':committed_extra,'acquisition_payment':acquisition_payment,'acquisition_payable':acquisition_payable, 'parent_own_net_profit':p_own_np,'sub_economic_net_profit':s_np,'common_net_profit':common_np,'parent_finance_tax':taxp,'sub_finance_tax':taxs,'parent_external_interest':debt_ip,'sub_external_interest':debt_is,'parent_pool_interest_paid':pool_interest,'parent_loan_interest_received':lend_interest,'parent_financial_income':ip,'sub_financial_income':ist,'taishan_legal_profit_budget':tprofit,'taishan_legal':upstream,'upstream_cash':u,'old_dividend_collection':old_collect,'old_dividend_balance':old,'pool_repayment':repay,'loan_collection':collect,'pool_parent_payable':lp,'pool_parent_receivable':lr,'parent_legal':pl,'requested_dividend':desired,'ordinary_dividend':d,'special_dividend':special,'total_dividend':total_d,'dps':total_d/shares,'source_legal_other':other_states,'source_upstream_other':other_upstream,'release_ramp':ramp,'external_debt_repayment':debt_pay_p+debt_pay_s,'nonoperating_realization':asset_realization,'forfeiture_cash':forfeiture,'shares':shares,'parent_legal_capital':shares,'parent_cash':cp,'sub_common_cash':cs,'parent_debt':dp,'sub_common_debt':ds,'new_parent_debt':newp,'new_sub_debt':news,'common_net_financial_assets':cp+cs-dp-ds,'cash_conservation_error':error})
        equity+=common_np-total_d-forfeiture
        nonop_remaining-=asset_realization
        asset_bridge=sum(capital[k]*segs[k]['common_fraction'] for k in segs)+accumulated_extra_capital+cp+cs-dp-ds-acquisition_payable+nonop_remaining+book_residual
        assert abs(equity-asset_bridge)<1e-7
        rows[-1]['common_asset_equity_bridge']=asset_bridge
        rows[-1]['unmodeled_book_net_assets_constant']=book_residual
        rows[-1]['unrealized_nonoperating_assets']=nonop_remaining
        legal_equity_gap-=forfeiture
        legal_sum=pr+pres+tr+tres+sum(a['retained']+a['reserve'] for a in other.values())
        assert abs(equity-legal_sum-legal_equity_gap)<1e-7
        rows[-1]['equity_outside_distributable_and_statutory_reserves']=legal_equity_gap
        rows[-1]['common_equity_rollforward']=equity
        rows[-1]['legal_source_retained_total']=tr+sum(a['retained'] for a in other.values())
        rows[-1]['legal_source_reserve_total']=tres+sum(a['reserve'] for a in other.values())
        prev_profit=common_np
    return {'feasible':True,'rows':rows}

def simulation(sc,years=10,steady_g=None):
    p=INPUT; segs=copy.deepcopy(p['segments']); rev={k:v['opening_revenue'] for k,v in segs.items()}; capital={k:v['opening_capital'] for k,v in segs.items()}
    cp=p['parent_cash']; cs=p['liquid_consolidated']-p['minority_liquid']-cp
    dp=p['parent_debt']; ds=sum(p['debt_components'].values())-p['minority_debt']-dp
    lp=p['pool_parent_payable']; lr=p['pool_parent_receivable']; old=p['old_dividend_receivable']; acquisition_payable=p['unpaid_acquisition']
    pr=p['parent_retained']; pres=p['parent_reserve']; shares=p['shares']; prev_profit=0; rows=[]; accumulated_extra_capital=0
    budget_balance=sc.get('opening_upstream_budget',3.0) # economic routing budget, NEVER a statutory account
    batches=[]; allocations=[]
    equity=p['quarter']['parent_equity']
    nonop_remaining=p['nonoperating_assets']['financial_assets']+p['nonoperating_assets']['associates_book']*p['nonoperating_assets']['associates_recovery_factor']
    book_residual=equity-(sum(capital[k]*segs[k]['common_fraction'] for k in segs)+cp+cs-dp-ds-acquisition_payable+nonop_remaining)

    for y in range(years):
        sr={}
        for k,s in segs.items():
            local=dict(sc); local['segment_margin_extra']=sc.get('light_margin_extra',0) if k=='light' else 0
            if y<10:
                sr[k]=operate(rev[k],capital[k],s,y,local)
            else:
                g=steady_g if steady_g is not None else sc.get('terminal_g',p['terminal_g_low']);roic=sc.get('terminal_roic',p['terminal_incremental_roic'])
                last=rows[-1]['segments'][k]; revenue=last['revenue']*(1+g);ebit=last['ebit']*(1+g);nopat=ebit-max(ebit,0)*s['tax'];da=revenue*s['da_rate'];growth_invest=nopat*g/roic;maintenance_extra=da*(s['maintenance_over_da']-1);investment=growth_invest+maintenance_extra
                sr[k]={'revenue':revenue,'growth':g,'margin':ebit/revenue,'ebit':ebit,'cash_tax':ebit-nopat,'nopat':nopat,'da':da,'maintenance_capex':da*s['maintenance_over_da'],'growth_capex':growth_invest*.6,'acquisition':0,'working_capital_change':growth_invest*.4,'net_reinvestment':investment,'closing_operating_capital':capital[k]+investment,'economic_common_profit':nopat*s['common_fraction'],'common_reinvestment':investment*s['common_fraction'],'economic_common_fcfe_unlevered':(nopat-investment)*s['common_fraction'],'common_fraction':s['common_fraction']}
            rev[k]=sr[k]['revenue'];capital[k]=sr[k]['closing_operating_capital']
        op=sum(v['economic_common_profit'] for v in sr.values()); invest=sum(v['common_reinvestment'] for v in sr.values())+(sc['wc_extra'][y] if y<10 else 0)
        generic_growth_capex=sum(v['growth_capex']*v['common_fraction'] for v in sr.values())
        committed_extra=max(0,(p['committed_growth_capex_common'][y] if y<10 else 0)-generic_growth_capex)
        invest+=committed_extra
        accumulated_extra_capital+=committed_extra+(sc['wc_extra'][y] if y<10 else 0)
        open_cp,open_cs,open_dp,open_ds=cp,cs,dp,ds
        pool_interest=lp*p['pool_interest']; lend_interest=lr*p['pool_interest']*sc.get('interest_bearing_receivable_fraction',p.get('interest_bearing_receivable_fraction',1.0))
        ip=cp*p['parent_cash_yield']; ist=cs*p['sub_cash_yield']; debt_ip=min(dp,p['parent_debt'])*p['debt_rate']+max(0,dp-p['parent_debt'])*p['new_debt_rate']; base_ds=sum(p['debt_components'].values())-p['minority_debt']-p['parent_debt']; debt_is=min(ds,base_ds)*p['debt_rate']+max(0,ds-base_ds)*p['new_debt_rate']
        p_pretax=p['parent_own_operating_profit']+ip+lend_interest-pool_interest-debt_ip
        taxp=max(0,p_pretax)*sc.get('parent_tax',p['parent_tax']) # dividend is exempt; a loss gives NO immediate shield
        finance_sub=ist+pool_interest-lend_interest-debt_is
        taxs=(max(0,sr['light']['ebit']+finance_sub)-max(0,sr['light']['ebit']))*p['sub_tax'] if sc.get('matched_old_tax',False) else max(finance_sub,0)*sc.get('treasury_tax',.15) # treasury assigned to profitable light taxpayer; loss itself gives no cash credit
        p_own_np=p_pretax-taxp; s_np=op+finance_sub-taxs
        common_np=p_own_np+s_np
        cp+=p_own_np; cs+=s_np-invest
        repay=min(lp,sc.get('pool_repayment',p['pool_repayment'])) 
        collect=min(lr,sc.get('loan_collection',p['loan_collection'])) 
        old_collect=old if y+1==sc.get('old_dividend_collection_year',p['old_dividend_collection_year']) else 0
        cp+=collect-repay+old_collect;cs+=repay-collect-old_collect;lp-=repay;lr-=collect;old-=old_collect
        acquisition_payment=min(acquisition_payable,(p['acquisition_settlement'][y] if y<10 else 0));acquisition_payable-=acquisition_payment;cp-=acquisition_payment
        forfeiture=0
        if not sc.get('no_forfeit'):
            forfeiture=(p['restricted_refund'][y] if y<10 else 0)
            action=capital_refund(shares,cp,forfeiture,(p['restricted_cancel'][y] if y<10 else 0));cp=action['cash'];shares=action['shares']
        # Surplus release begins only after committed projects/acquisition payments finish;
        # a five-year ramp models routing newly consolidated wings, not an instant legal waiver.
        ramp=0 if y<5+sc.get('routing_delay',0) else p['mature_upstream_ramp'][min(y-5-sc.get('routing_delay',0),4)]
        debt_pay_s=min(ds,max(0,cs-p['sub_cash_floor'])*ramp);cs-=debt_pay_s;ds-=debt_pay_s
        # No segment or synthetic source is a legal person. This ceiling is a
        # conditional economic transfer budget constrained by observed dividend history.
        budget_balance+=s_np
        early=max(0,sr['light']['nopat']*.85*.70)*sc.get('early_upstream_scale',1.0)
        desired_u=early if y<5+sc.get('routing_delay',0) else max(0,budget_balance)*ramp*sc.get('routing_fraction',1.0)
        u=max(0,min(desired_u,budget_balance,max(0,cs-p['sub_cash_floor'])))
        # Conditional routing friction is a real cash cost, not a phantom reserve.
        friction=u*sc.get('routing_friction',0.0)
        received=u-friction;cs-=u;cp+=received;budget_balance-=u
        common_np-=friction
        asset_realization=0;realization_gain=0;realization_tax=0
        if y==9:
            basis=p['nonoperating_assets']['financial_assets']+p['nonoperating_assets']['associates_book']
            realized=realize_asset(basis,basis,basis*sc.get('asset_recovery',1.0),sc.get('asset_sale_cost',0),p['parent_tax'])
            asset_realization=realized['net_cash'];realization_gain=realized['accounting_gain'];realization_tax=realized['tax']
            cp+=asset_realization;common_np+=realization_gain-realization_tax
        # Financing-asset cohorts tag every year's excess formation, and later cash uses.
        opening_excess=max(0,open_cp+open_cs-p['parent_cash_floor']-p['sub_cash_floor'])
        debt_pay_p=min(dp,max(0,cp-p['parent_cash_floor'])*ramp);cp-=debt_pay_p;dp-=debt_pay_p
        desired=p['first_year_cash_dividend'] if y==0 else max(0,prev_profit*p['payout'])
        # First reduce ordinary D, then use finite external financing ONLY to restore operating liquidity.
        available=max(0,min(cp-p['parent_cash_floor'],cp+cs-p['parent_cash_floor']-p['sub_cash_floor']))
        pl=legal(pr,pres,shares,p_own_np+received+realization_gain-realization_tax,desired,available);d=pl['dividend'];pr,pres=pl['retained'],pl['reserve'];cp-=d
        special=0
        if ramp:
            # Ordinary D has already consumed THIS retained-profit ledger. No principal unlock twice.
            special=max(0,min(pr,max(0,cp-p['parent_cash_floor'])))*ramp
            pr-=special;cp-=special
            pl['retained']=pr
        total_d=d+special
        newp=max(0,p['parent_cash_floor']-cp);news=max(0,p['sub_cash_floor']-cs)
        if dp+newp-p['parent_debt']>p['parent_new_debt_limit']+1e-9 or ds+news-(sum(p['debt_components'].values())-p['minority_debt']-p['parent_debt'])>p['sub_new_debt_limit']+1e-9:
            return {'feasible':False,'failed_year':y+1,'failure':'zero/capped dividend still insufficient with finite financing','rows':rows,'cash_before_unfunded':[cp,cs],'additional_debt_needed':[newp,news]}
        cp+=newp;cs+=news;dp+=newp;ds+=news
        # No new shareholder equity, no imaginary increase in legal reserve ceiling.
        error=(cp+cs-open_cp-open_cs)-(common_np-invest-total_d-forfeiture-acquisition_payment+newp+news-debt_pay_p-debt_pay_s+asset_realization-realization_gain+realization_tax)
        assert abs(error)<1e-8
        assert cp>=p['parent_cash_floor']-1e-9 and cs>=p['sub_cash_floor']-1e-9
        rows.append({'year':y+1,'segments':sr,'common_operating_profit':op,'common_operating_capital_end':sum(capital[k]*segs[k]['common_fraction'] for k in segs)+accumulated_extra_capital,'common_reinvestment':invest,'wc_stress_change':(sc['wc_extra'][y] if y<10 else 0),'committed_project_extra_capex':committed_extra,'acquisition_payment':acquisition_payment,'acquisition_payable':acquisition_payable,'parent_own_net_profit':p_own_np,'sub_economic_net_profit':s_np,'common_net_profit':common_np,'parent_finance_tax':taxp,'sub_finance_tax':taxs,'parent_external_interest':debt_ip,'sub_external_interest':debt_is,'parent_pool_interest_paid':pool_interest,'parent_loan_interest_received':lend_interest,'parent_financial_income':ip,'sub_financial_income':ist,'upstream_economic_budget_balance':budget_balance,'upstream_requested':desired_u,'upstream_cash':received,'upstream_gross':u,'routing_cash_cost':friction,'old_dividend_collection':old_collect,'old_dividend_balance':old,'pool_repayment':repay,'loan_collection':collect,'pool_parent_payable':lp,'pool_parent_receivable':lr,'parent_legal':pl,'requested_dividend':desired,'ordinary_dividend':d,'special_dividend':special,'total_dividend':total_d,'dps':total_d/shares,'release_ramp':ramp,'external_debt_repayment':debt_pay_p+debt_pay_s,'nonoperating_realization':asset_realization,'asset_accounting_gain':realization_gain,'asset_sale_tax':realization_tax,'forfeiture_cash':forfeiture,'shares':shares,'parent_legal_capital':shares,'parent_cash':cp,'sub_common_cash':cs,'parent_debt':dp,'sub_common_debt':ds,'new_parent_debt':newp,'new_sub_debt':news,'common_net_financial_assets':cp+cs-dp-ds,'cash_conservation_error':error})
        equity+=common_np-total_d-forfeiture
        if y==9: nonop_remaining=0
        asset_bridge=sum(capital[k]*segs[k]['common_fraction'] for k in segs)+accumulated_extra_capital+cp+cs-dp-ds-acquisition_payable+nonop_remaining+book_residual
        assert abs(equity-asset_bridge)<1e-7
        rows[-1]['common_asset_equity_bridge']=asset_bridge
        rows[-1]['unmodeled_book_net_assets_constant']=book_residual
        rows[-1]['unrealized_nonoperating_assets']=nonop_remaining
        prev_profit=common_np
    return {'feasible':True,'rows':rows}

def auxiliary():
    p=INPUT; value=0; details={}
    for (k,s),m,r in zip(p['segments'].items(),p['auxiliary']['segment_margin'],p['auxiliary']['discounts']):
        e=s['opening_revenue']*m*(1-s['tax'])*s['common_fraction']
        maintenance_extra=s['opening_revenue']*s['da_rate']*(s['maintenance_over_da']-1)*s['common_fraction']
        v=(e-maintenance_extra)/r;details[k]={'revenue':s['opening_revenue'],'margin':m,'sustainable_common_profit':e,'maintenance_over_depreciation':maintenance_extra,'capitalization_rate':r,'value':v};value+=v
    value+=p['parent_own_operating_profit']/.10
    net=p['liquid_consolidated']-p['minority_liquid']-(sum(p['debt_components'].values())-p['minority_debt'])-p['parent_cash_floor']-p['sub_cash_floor']
    commitment_pv=sum(x/(1.10)**(i+1) for i,x in enumerate(p['committed_growth_capex_common']))
    net-=p['unpaid_acquisition']+sum(p['restricted_refund'])+commitment_pv
    net+=p['nonoperating_assets']['financial_assets']+p['nonoperating_assets']['associates_book']*p['nonoperating_assets']['associates_recovery_factor']
    diluted_final=p['shares']-sum(p['restricted_cancel'])
    return {'segments':details,'parent_overhead_value':p['parent_own_operating_profit']/.10,'current_excess_net_financial_assets':net,'equity_value':value+net,'no_growth_committed_project_pv_deduction':commitment_pv,'fully_settled_shares':diluted_final,'per_share':(value+net)/diluted_final}


def actual_tests():
    results={}
    def check(name,condition):
        assert condition,name
        results[name]='pass'
    check('registered20_paid10_reserve5_profit10_levy1',abs(legal(0,5,20,10,100,100)['levy']-1)<1e-12)
    check('loss_coverage_first',legal(-3,0,20,2,100,100)['dividend']==0)
    check('reserve_already_full',legal(0,10,20,10,100,100)['levy']==0)
    check('registered_conversion_updates_ceiling',legal(0,10,40,10,100,100)['levy']==1)
    a=realize_asset(10,8,9,1,.25)
    check('principal_not_profit_tax_basis_separate',a=={'net_cash':8.0,'accounting_gain':-2,'tax':0.0,'book_removed':10,'tax_basis_removed':8})
    x=exit_waterfall(2,10,.2,5,1,10,.6)
    check('finite_exit_debt_first_noncash_haircut',abs(x['common_cash']-2.4)<1e-12)
    check('exit_cost_unfunded_not_hidden',not exit_waterfall(0,1,.5,1,2,1,.8)['feasible'])
    check('minority_issue_register_not_valuation_proxy',abs(equity_issue(2,10,.8,0,2)['registered']-2.4)<1e-12)
    check('profit_constrained_capital_return',capital_refund(10,10,3,3)=={'shares':7,'cash':7,'profit':0})
    check('minority_capital_real_equity',abs(equity_issue(2,10,.8,0,2)['parent_fraction']-2/3)<1e-12)
    o=operate(100,50,dict(growth=[0],margin=[-.1],tax=.25,da_rate=.1,maintenance_over_da=1.05,fixed_growth_capital_per_sales=.5,working_capital_per_sales=.2,acquisition=[0],common_fraction=1),0,dict(growth_delta=[0],margin_delta=[0]))
    check('negative_EBIT_no_unconditional_refund',o['cash_tax']==0)
    check('g0_maintenance_survives',o['maintenance_capex']==10.5)
    b=copy.deepcopy(INPUT['scenarios']['base']);z=simulation(b);b['old_dividend_collection_year']=3;z2=simulation(b)
    check('old_receivable_not_new_profit',abs(z['rows'][0]['parent_legal']['pre_distribution_legal_profit']-z2['rows'][0]['parent_legal']['pre_distribution_legal_profit'])<1e-10)
    b['pool_repayment']=10;b['loan_collection']=0;check('finite_finance_fails',not simulation(b)['feasible'])
    check('actual_refunds_reduce_shares',abs(z['rows'][1]['shares']-1.689507842)<1e-12)
    check('mature_cash_not_frozen',all(sum(q['remaining'] for q in priced(INPUT['scenarios'][n],.1,0,400)['financial_cohorts'])<1.1000001 for n in ['base','structural_adverse']))
    return results

def main():
    import lzma,base64,hashlib,sys
    if len(sys.argv)>1 and sys.argv[1]=='--expand':
        source=Path(__file__).with_name('2026-Q3-output.json')
        o=json.loads(source.read_text())
        assert o['schema']=='deterministic-xz-json-envelope-v1'
        compressed=base64.b64decode(o['payload_xz_base64'],validate=True)
        assert len(compressed)==o['compressed_bytes']
        assert hashlib.sha256(compressed).hexdigest()==o['compressed_sha256']
        raw=lzma.decompress(compressed,format=lzma.FORMAT_XZ)
        assert len(raw)==o['uncompressed_bytes']
        assert hashlib.sha256(raw).hexdigest()==o['payload_sha256']
        target=Path(sys.argv[2]) if len(sys.argv)>2 else Path(__file__).with_name('expanded-output.json')
        if target.resolve() in {source.resolve(),Path(__file__).resolve()}:raise ValueError('Expansion target must not overwrite the model or packed output')
        target.write_bytes(raw);return
    output={'schema':'BNBM-entity-economic-budget-v2','units':'CNY billion; shares billion','inputs_original':copy.deepcopy(INPUT),'tests':{},'matched_budget':{},'scenarios':{},'sensitivities':{},'convergence':{}}
    endpoints=[('low',.10,.005),('high',.09,.01)]
    # First isolate removing fictitious legal pools. ALL economics and tax inputs identical.
    for n,s in INPUT['scenarios'].items():
        q=copy.deepcopy(s);q['matched_old_tax']=True
        output['matched_budget'][n]={}
        for ep,r,g in endpoints:
            gg=q.get('terminal_g',g)
            output['matched_budget'][n][ep]={'old':priced(q,r,gg,old=True),'new':priced(q,r,gg)}
    INPUT['interest_bearing_receivable_fraction']=1.7/2.8
    INPUT['pool_parent_payable']=9.4
    # Current statutory high-tech rate is 15%; forward use 25% expiry budget, not a false current-law fact.
    INPUT['routing_method']='Economic ability budget supported by actual historical parent dividends; not a subsidiary statutory ledger'
    output['inputs_current']=copy.deepcopy(INPUT)
    for n,s in INPUT['scenarios'].items():
        output['scenarios'][n]={ep:priced(s,r,s.get('terminal_g',g)) for ep,r,g in endpoints}
    for n,changes in {'routing_70pct':{'routing_fraction':.7},'routing_delay3':{'routing_delay':3},'routing_cost3pct':{'routing_friction':.03},'early_half':{'early_upstream_scale':.5},'historic_budget_zero':{'opening_upstream_budget':0},'parent_tax15':{'parent_tax':.15},'direct_assets_recovery70':{'asset_recovery':.7,'asset_sale_cost':.01},'foreign_routing_cost10pct':{'routing_friction':.003},'treasury_tax25':{'treasury_tax':.25}}.items():
        q=dict(INPUT['scenarios']['base'],**changes)
        output['sensitivities'][n]={'changed':changes,'endpoints':{ep:priced(q,r,g) for ep,r,g in endpoints}}
    output['tests']=actual_tests();output['auxiliary']=auxiliary()
    for ep,r,g in endpoints:output['convergence'][ep]={str(n):priced(INPUT['scenarios']['base'],r,g,n)['pv'] for n in [150,250,400,600]}
    b=output['scenarios']['base'];output['value_range']={'low':round(b['low']['pv'],2),'high':round(b['high']['pv'],2),'currency':'CNY'}
    output['return_model']={'schema_version':1,'method':'annual_common_equity_irr_v1','currency':'CNY','model_as_of':INPUT['asof'],'base_case_distributions_per_share':[round(a['dps'],6) for a in b['low']['rows'][:5]],'base_case_terminal_equity_value_range_per_share':{'year_5':{ep:round(b[ep]['tv5'],6) for ep,_,_ in endpoints}}}
    raw=json.dumps(output,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
    compressed=lzma.compress(raw,format=lzma.FORMAT_XZ,preset=6)
    wrapper={'schema':'deterministic-xz-json-envelope-v1','payload_schema':output['schema'],'payload_sha256':hashlib.sha256(raw).hexdigest(),'uncompressed_bytes':len(raw),'compression':{'format':'xz','preset':6,'library':'Python standard library lzma'},'compressed_bytes':len(compressed),'compressed_sha256':hashlib.sha256(compressed).hexdigest(),'expand':'python 2026-Q3.py --expand [target]; stdlib lzma.decompress(base64.b64decode(payload_xz_base64)); default expanded-output.json','value_range':output['value_range'],'return_model':output['return_model'],'tests':output['tests'],'payload_xz_base64':base64.b64encode(compressed).decode()}
    Path(__file__).with_name('2026-Q3-output.json').write_text(json.dumps(wrapper,ensure_ascii=False,separators=(',',':'))+'\n')
    Path(__file__).with_name('summary.json').write_text(json.dumps({k:v for k,v in wrapper.items() if k!='payload_xz_base64'},ensure_ascii=False,indent=2))
    print(json.dumps(output['value_range'],ensure_ascii=False));print(json.dumps(output['return_model'],ensure_ascii=False))
if __name__=='__main__':main()
