#!/usr/bin/env python3
"""BNBM 2026Q3; stdlib, deterministic. Money=CNY billion, shares=billion.
Forecast dates are successive 12-month anniversaries of 2026-10-26.
The legal parent/Taishan budget is deliberately separate from economic segments.
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

def simulation(sc,years=10,steady_g=None):
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
            forfeiture=(p['restricted_refund'][y] if y<10 else 0);cp-=forfeiture;shares-=(p['restricted_cancel'][y] if y<10 else 0)
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

def economic_terminal(sim,r,g,roic,financial_lag=0):
    """Value at Y5. Operations after Y5 distribute all economic free cash; cash principal
    at Y5 is a claim retained in valuation, not falsely reported as an actual cash dividend.
    Y6+ operating cash excludes financial-asset yields to avoid principal/interest double count.
    Debt interest excluded from operating NOPAT; closing debt deducted in the Y5 bridge.
    """
    rows=sim['rows']; pv=0; cashflows=[]
    for a in rows[5:]:
        # common-owned operating cash including recurring headquarters cost; no financial income
        f=a['common_operating_profit']+INPUT['parent_own_operating_profit']-a['common_reinvestment']
        cashflows.append(f);pv+=f/(1+r)**(a['year']-5)
    final_op=rows[-1]['common_operating_profit']+INPUT['parent_own_operating_profit']
    terminal_np=final_op*(1+g);reinvest=terminal_np*g/roic
    terminal_fcf=terminal_np-reinvest;tv10=terminal_fcf/(r-g)
    tv10pv5=tv10/(1+r)**5;operation=pv+tv10pv5
    y5=rows[4]; liquidity=INPUT['parent_cash_floor']+INPUT['sub_cash_floor']
    nonop=INPUT['nonoperating_assets']['financial_assets']+INPUT['nonoperating_assets']['associates_book']*INPUT['nonoperating_assets']['associates_recovery_factor']
    bridge=y5['common_net_financial_assets']-liquidity-y5['acquisition_payable']+nonop
    financial_claim_before_lag=bridge
    bridge*=((1.018)/(1+r))**financial_lag
    tv5=operation+bridge
    distributions=[a['dps'] for a in rows[:5]]
    pv_d=sum(distributions[i]/(1+r)**(i+1) for i in range(5))
    current=pv_d+tv5/y5['shares']/(1+r)**5
    return {'r':r,'g':g,'terminal_roic':roic,'year6_10_operating_fcfe':cashflows,'y10_sustainable_common_operating_np':final_op,'y11_np':terminal_np,'y11_reinvestment':reinvest,'y11_fcfe':terminal_fcf,'tv10':tv10,'tv10_pv_at_y5':tv10pv5,'operating_value_y5':operation,'y5_cash_parent':y5['parent_cash'],'y5_cash_sub_common':y5['sub_common_cash'],'y5_external_debt':y5['parent_debt']+y5['sub_common_debt'],'y5_nonoperating_assets':nonop,'y5_remaining_acquisition_payable':y5['acquisition_payable'],'y5_required_liquidity':liquidity,'y5_financial_claim_before_lag':financial_claim_before_lag,'financial_claim_release_lag':financial_lag,'y5_excess_net_financial_assets':bridge,'tv5':tv5,'tv5_per_share':tv5/y5['shares'],'pv_first5_dividends_per_share':pv_d,'current_value_per_share':current,'terminal5_pv_fraction':(current-pv_d)/current,'ultimate_tv10_pv_fraction':tv10/(1+r)**10/y5['shares']/current}

def actual_terminal(sc,r,g,years=400):
    sim=simulation(sc,years,g)
    if not sim['feasible']:return {'feasible':False,'failure':sim}
    rows=sim['rows'];pv=sum(a['dps']/(1+r)**a['year'] for a in rows)
    first5=sum(a['dps']/(1+r)**a['year'] for a in rows[:5])
    tv5=(pv-first5)*(1+r)**5
    last=rows[-1]
    return {'feasible':True,'r':r,'g':g,'integration_years':years,'current_value_per_share':pv,'tv5_per_share':tv5,'tv5':tv5*rows[4]['shares'],'pv_first5_dividends_per_share':first5,'last_year_dividend':last['total_dividend'],'last_parent_cash':last['parent_cash'],'last_sub_cash':last['sub_common_cash'],'last_debt':last['parent_debt']+last['sub_common_debt'],'last_unpaid_historical_pool':last['pool_parent_payable'],'first_debt_free_year':next((a['year'] for a in rows if a['parent_debt']+a['sub_common_debt']<1e-9),None),'first_cash_at_operating_floor_year':next((a['year'] for a in rows[5:] if a['parent_cash']+a['sub_common_cash']<1.100000001),None),'omitted_cash_dividend_tail_upper_bound_per_share':(last['total_dividend']*(1+g)+1)/(r-g)/last['shares']/(1+r)**years,'tail_cash_pv_bound':(last['parent_cash']+last['sub_common_cash'])/last['shares']/(1+r)**years,'trajectory':pack(sim)}

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

def tests():
    # Formal distribution chain: loss first, then reserve only remaining profit; ceiling tested.
    a=legal(-2,.49,1,5,10,100);assert abs(a['levy']-.01)<1e-12 and abs(a['dividend']-2.99)<1e-12
    b=legal(-3,0,1,2,10,100);assert b['dividend']==0 and b['retained']==-1 and b['levy']==0
    c=legal(1,.5,1,2,10,.4);assert c['dividend']==.4 and abs(c['retained']-2.6)<1e-12
    # Formal operating chain: sales100->110 EBIT22 tax4.4; DA11 maint11 growthfixed5 WC2 = invest7, FCF10.6.
    s={'growth':[.1],'margin':[.2],'tax':.2,'da_rate':.1,'maintenance_over_da':1,'fixed_growth_capital_per_sales':.5,'working_capital_per_sales':.2,'acquisition':[0],'common_fraction':1}
    o=operate(100,50,s,0,{'growth_delta':[0],'margin_delta':[0]});assert abs(o['nopat']-17.6)<1e-10 and abs(o['net_reinvestment']-7)<1e-10 and abs(o['economic_common_fcfe_unlevered']-10.6)<1e-10
    # Interest recipient taxable while parent paying interest has losses: check simulation's separate tax function.
    z=simulation(INPUT['scenarios']['base']);assert z['rows'][0]['parent_finance_tax']==0 and z['rows'][0]['sub_finance_tax']>0
    q=copy.deepcopy(INPUT['scenarios']['base']);q['old_dividend_collection_year']=3
    z2=simulation(q);assert abs(z['rows'][0]['parent_legal']['pre_distribution_legal_profit']-z2['rows'][0]['parent_legal']['pre_distribution_legal_profit'])<1e-10
    # A failed funding budget must not become a priced successful scenario.
    q=copy.deepcopy(INPUT['scenarios']['base']);q['pool_repayment']=10;q['loan_collection']=0
    fail=simulation(q);assert not fail['feasible']
    return {'formal_legal_loss_cover_reserve_ceiling':'pass','formal_operating_hand_case':'pass','separate_internal_interest_tax':'pass','finite_funding_failure':'pass','cash_conservation':'pass'}

def pack(sim):
    if not sim['feasible']:return sim
    rows=sim['rows'];cols=[k for k in rows[0] if k not in ('segments','taishan_legal','parent_legal','source_legal_other')]
    out={'feasible':True,'annual_columns':cols,'annual_values':[[a[k] for k in cols] for a in rows],'segments':{},'legal':{},'source_legal_other':{}}
    for name in INPUT['segments']:
        sc=list(rows[0]['segments'][name]);out['segments'][name]={'columns':sc,'values':[[a['segments'][name][k] for k in sc] for a in rows]}
    for name in ['taishan_legal','parent_legal']:
        lc=list(rows[0][name]);out['legal'][name]={'columns':lc,'values':[[a[name][k] for k in lc] for a in rows]}
    for name in rows[0]['source_legal_other']:
        lc=list(rows[0]['source_legal_other'][name]);out['source_legal_other'][name]={'columns':lc,'values':[[a['source_legal_other'][name][k] for k in lc] for a in rows]}
    # lossless expansion test of compact representation, no discarded years or fields.
    rebuilt=[]
    for i,vals in enumerate(out['annual_values']):
        a=dict(zip(cols,vals));a['segments']={n:dict(zip(v['columns'],v['values'][i])) for n,v in out['segments'].items()}
        for n,v in out['legal'].items():a[n]=dict(zip(v['columns'],v['values'][i]))
        a['source_legal_other']={n:dict(zip(v['columns'],v['values'][i])) for n,v in out['source_legal_other'].items()}
        rebuilt.append(a)
    assert rebuilt==rows
    return out

def main():
    output={'inputs':INPUT,'tests':tests(),'scenarios':{},'auxiliary':auxiliary()}
    for name,sc in INPUT['scenarios'].items():
        sim=simulation(sc);v=pack(sim)
        if sim['feasible']:
            v['economic_low']=economic_terminal(sim,INPUT['discount_low_value'],sc.get('terminal_g',INPUT['terminal_g_low']),sc.get('terminal_roic',INPUT['terminal_incremental_roic']))
            v['economic_high']=economic_terminal(sim,INPUT['discount_high_value'],sc.get('terminal_g',INPUT['terminal_g_high']),sc.get('terminal_roic',INPUT['terminal_incremental_roic']))
            for endpoint,r,g in [('low',pval:=INPUT['discount_low_value'],sc.get('terminal_g',INPUT['terminal_g_low'])),('high',INPUT['discount_high_value'],sc.get('terminal_g',INPUT['terminal_g_high']))]:
                v[endpoint]=actual_terminal(sc,r,g)
                full=simulation(sc,400,g);assert full['rows'][:10]==sim['rows']
                v[endpoint]['trajectory']={'prefix_ref':'scenarios.'+name,'prefix_years':10,'continuation':pack({'feasible':True,'rows':full['rows'][10:]})}
                assert len(sim['rows'])+len(v[endpoint]['trajectory']['continuation']['annual_values'])==400
            v['dps_first5']=[a['dps'] for a in sim['rows'][:5]]
            v['matched_incremental_return_y1_y5']=(sim['rows'][4]['common_operating_profit']-sim['rows'][0]['common_operating_profit'])/sum(sum(a['segments'][k]['common_reinvestment'] for k in INPUT['segments'])+a['wc_stress_change']+a['committed_project_extra_capex'] for a in sim['rows'][1:5])
        output['scenarios'][name]=v
    b=output['scenarios']['base'];base_sim=simulation(INPUT['scenarios']['base'])
    output['legacy_economic_claim_delay_only_not_core']={n:economic_terminal(base_sim,r,g,INPUT['terminal_incremental_roic'],5) for n,r,g in [('low',.10,.005),('high',.09,.01)]}
    output['convergence']={}
    for ep,r,g in [('low',.10,.005),('high',.09,.01)]:
        vals={str(n):actual_terminal(INPUT['scenarios']['base'],r,g,n)['current_value_per_share'] for n in [150,250,400]}
        assert abs(vals['400']-vals['250'])<1e-6
        output['convergence'][ep]=vals
    output['historical_legal_retained_sensitivity']={}
    for retained in [0,6]:
        prior=INPUT['taishan_start_retained'];INPUT['taishan_start_retained']=retained
        output['historical_legal_retained_sensitivity'][str(retained)]={ep:actual_terminal(INPUT['scenarios']['base'],r,g)['current_value_per_share'] for ep,r,g in [('low',.10,.005),('high',.09,.01)]}
        INPUT['taishan_start_retained']=prior
    output['reserve_capital_sensitivity']={}
    for multiplier in [0,2]:
        prior=copy.deepcopy(INPUT['other_legal_capital_common']);INPUT['other_legal_capital_common']={k:v*multiplier for k,v in prior.items()}
        output['reserve_capital_sensitivity'][str(multiplier)]={ep:actual_terminal(INPUT['scenarios']['base'],r,g)['current_value_per_share'] for ep,r,g in [('low',.10,.005),('high',.09,.01)]}
        INPUT['other_legal_capital_common']=prior
    output['value_range']={'low':round(b['low']['current_value_per_share'],2),'high':round(b['high']['current_value_per_share'],2),'currency':'CNY'}
    output['return_model']={'schema_version':1,'method':'annual_common_equity_irr_v1','currency':'CNY','model_as_of':INPUT['asof'],'base_case_distributions_per_share':[round(x,6) for x in b['dps_first5']],'base_case_terminal_equity_value_range_per_share':{'year_5':{'low':round(b['low']['tv5_per_share'],6),'high':round(b['high']['tv5_per_share'],6)}}}
    Path(__file__).with_name('2026-Q3-output.json').write_text(json.dumps(output,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')
    print(json.dumps({'value':output['value_range'],'holder':output['return_model'],'auxiliary':output['auxiliary']['per_share'],'scenario_values':{k:([v['low']['current_value_per_share'],v['high']['current_value_per_share']] if v['feasible'] else 'FAILED') for k,v in output['scenarios'].items()}},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
