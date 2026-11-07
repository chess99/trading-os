"""华明装备2026-Q3可读模型；金额百万元。python 2026-Q3.py，stdout仅轻量正式结果。"""
from pathlib import Path
import json,copy,math
P=Path(__file__).resolve().parent
WORK = P.parent / '.work'
WORK.mkdir(parents=True, exist_ok=True)

def holder_value(distributions,terminal,rate):
    """同一持有人计算链：年末分配，最后一期分配后经济价值。"""
    return sum(c/(1+rate)**(i+1) for i,c in enumerate(distributions))+terminal/(1+rate)**len(distributions)

def annuity(cash,years,rate,recovery=0):
    return sum(cash/(1+rate)**t for t in range(1,years+1))+recovery/(1+rate)**years

def forecast(x):
    cash=x['cash_20260930']-x['paid_oct_dividend']-x['repurchase_paid_oct']
    debt=x['short_bank_debt']+x['long_bank_debt']+x['current_long_bank_debt']
    parent=x['parent_cash_budget']; retained=x['parent_retained_start']; reserve=x['parent_statutory_reserve_credit']
    old=x['parent_old_dividend_receivable']; new_receivable=0
    rev=copy.deepcopy(x['base_revenue_2026']); rows=[]
    for i in range(10):
        start_cash=cash;start_debt=debt;start_parent=parent;start_old=old;prev_mfg=rev['domestic_electric']+rev['export_electric']+rev['cnc']
        for k,g in [('domestic_electric','domestic'),('export_electric','export'),('cnc','cnc')]:rev[k]*=1+x['growth'][g][i]
        electric=rev['domestic_electric']+rev['export_electric']; mfg=electric+rev['cnc']
        hq=x['hq_cash_cost_2026']*(1+x['hq_growth'])**(i+1)
        charge=x['annual_incentive_charge']*(1 if i<5 else (1+x['hq_growth'])**(i-4))
        electric_nopat=electric*x['electric_nopat_margin'][i]-charge
        mfg_nopat=electric_nopat+rev['cnc']*x['cnc_nopat_margin']-hq
        solar_nopat=rev['solar_other']*x['solar_other_nopat_margin']; nopat=mfg_nopat+solar_nopat
        maintenance=mfg*x['manufacturing_maintenance_rate']
        growth_capital=max(0,mfg-prev_mfg)*x['growth_capital_per_incremental_sales']
        # 利润已经扣除维护相当的制造折旧，维护与折旧相抵；增长资本另扣。
        solar_noncash=x['solar_annual_depreciation']; solar_maintenance=rev['solar_other']*x['solar_maintenance_rate']
        incentive_addback=charge if i<x['prepaid_incentive_years'] else 0
        repayment=min(debt,x['bank_repayment'][i]);debt-=repayment
        interest=(start_debt+debt)/2*x['bank_interest']*(1-x['cash_tax'])
        cash_income=max(0,start_cash-x['minimum_group_cash']*(1+x['cash_floor_growth'])**i)*x['cash_yield']*(1-x['cash_tax'])
        common_profit=nopat-interest+cash_income
        completion=x['solar_completion_capex'] if i==0 else 0
        repurchase=(x['repurchase_total_budget']-x['repurchase_paid_oct']+x['repurchase_fees']) if i==0 else 0
        government=x['government_receivable_collection'][i];financial_recovery=x['equity_asset_collection'][i]
        settlement=x['parent_net_other_settlement'][i]
        fcf=nopat+incentive_addback+solar_noncash-solar_maintenance-growth_capital-completion-interest+cash_income-repayment
        cash_pre=start_cash+fcf-repurchase+government+financial_recovery-settlement
        floor=x['minimum_group_cash']*(1+x['cash_floor_growth'])**(i+1)
        # 仅就母公司主来源上海华明作量级预算，不建立虚构法人或跨法人抵销。
        declared=max(0,electric_nopat)*(x['upstream_ratio_first5'] if i<5 else x['upstream_ratio_next5'])
        parent_profit=declared-hq
        legal_add=min(max(0,parent_profit)*.10,max(0,x['parent_share_capital']*.5-reserve))
        reserve+=legal_add
        legal_capacity=max(0,retained+parent_profit-legal_add)
        parent_pre_internal=start_parent-hq-repurchase-settlement+government
        sub_cash_pre=cash_pre-parent_pre_internal
        internal_capacity=max(0,sub_cash_pre-(floor-x['parent_cash_floor']))
        old_received=min(old,x['old_dividend_collection'][i],internal_capacity)
        old-=old_received;internal_capacity-=old_received
        received=min(declared*x['upstream_received_fraction'],internal_capacity)
        new_receivable+=declared-received
        parent_pre=parent_pre_internal+old_received+received
        desired=max(0,common_profit)*(x['payout_first5'] if i<5 else x['payout_next5'])
        dividend=max(0,min(desired,cash_pre-floor,parent_pre-x['parent_cash_floor'],legal_capacity))
        cash=cash_pre-dividend;parent=parent_pre-dividend;retained+=parent_profit-legal_add-dividend
        if cash < floor-1e-7 or parent < x['parent_cash_floor']-1e-7:
            raise ValueError(f'year {i+1} funding floor failed: {cash},{parent}')
        assert abs(cash-(start_cash+fcf-repurchase+government+financial_recovery-settlement-dividend))<1e-7
        assert abs(parent-(start_parent-hq-repurchase-settlement+government+old_received+received-dividend))<1e-7
        assert abs(old-(start_old-old_received))<1e-7
        assert retained>=-1e-7 and parent<=cash+1e-7
        rows.append(dict(year=i+1,domestic_electric=rev['domestic_electric'],export_electric=rev['export_electric'],cnc=rev['cnc'],revenue=mfg+rev['solar_other'],electric_nopat=electric_nopat,mfg_nopat=mfg_nopat,nopat=nopat,common_profit=common_profit,maintenance=maintenance,growth_capital=growth_capital,solar_noncash=solar_noncash,solar_maintenance=solar_maintenance,incentive_addback=incentive_addback,completion=completion,interest=interest,cash_income=cash_income,debt_repaid=repayment,debt_end=debt,repurchase=repurchase,fcf=fcf,dividend=dividend,dividend_per_share=dividend/x['shares'],desired_dividend=desired,cash_end=cash,cash_floor=floor,parent_declared=declared,parent_received=received,old_dividend_received=old_received,old_dividend_receivable=old,new_dividend_receivable=new_receivable,parent_cash_end=parent,parent_legal_profit=parent_profit,parent_retained=retained,parent_reserve=reserve,government_recovery=government,financial_recovery=financial_recovery,net_settlement=settlement))
    assert debt<1e-7
    return rows

def value(x,rows,rate):
    last=rows[-1];g=x['stable_growth'];roic=x['stable_incremental_roic']
    # 十年后制造业务增速2%，新增资本回报18%；必要资本留存g/ROIC。
    stable_mfg_fcf=last['mfg_nopat']*(1+g)*(1-g/roic)
    operation_terminal=stable_mfg_fcf/(rate-g)
    solar_cf=x['base_revenue_2026']['solar_other']*(x['solar_other_nopat_margin']-x['solar_maintenance_rate'])+x['solar_annual_depreciation']
    solar_terminal=annuity(solar_cf,x['solar_remaining_years']-10,rate,x['solar_final_recovery'])
    surplus=max(0,last['cash_end']-last['cash_floor'])
    # 成熟期上划利润并由母公司回投增长资本，内部双向资金不增集团现金。
    legal_after=last['parent_retained']; release_delay=None
    for t in range(1,51):
        mfg_profit=last['mfg_nopat']*(1+g)**t
        active_solar=t<=x['solar_remaining_years']-10
        solar_profit=x['base_revenue_2026']['solar_other']*x['solar_other_nopat_margin'] if active_solar else 0
        normal_cash=mfg_profit*(1-g/roic)+(solar_cf if active_solar else 0)
        legal_after+=mfg_profit+solar_profit-normal_cash
        if t>=x['cash_release_delay'] and legal_after>=surplus:
            release_delay=t;break
    if release_delay is None:raise ValueError('surplus realization timing not bounded within diagnostic horizon')
    legal_cash_release_capacity=max(0,legal_after)
    cash_terminal=surplus/(1+rate)**release_delay
    terminal=operation_terminal+solar_terminal+cash_terminal
    dividends=[r['dividend'] for r in rows]
    current=holder_value(dividends,terminal,rate)
    terminal5=holder_value(dividends[5:],terminal,rate)
    assert abs(current-holder_value(dividends[:5],terminal5,rate))<1e-7
    return dict(current_per_share=current/x['shares'],terminal_year5_per_share=terminal5/x['shares'],terminal_year10=terminal,stable_mfg_fcf=stable_mfg_fcf,operation_terminal=operation_terminal,solar_terminal=solar_terminal,surplus_cash_terminal=cash_terminal,legal_cash_release_capacity=legal_cash_release_capacity,cash_release_delay=release_delay,terminal_pv_fraction=(terminal/(1+rate)**10)/current)

def auxiliary_value(x,rows):
    """辅助EV/税后经营收益；同一普通股义务，有限光伏和预付激励另桥。"""
    rate=x['discount_base'];mfg_nopat=rows[0]['mfg_nopat']
    solar_cf=x['base_revenue_2026']['solar_other']*(x['solar_other_nopat_margin']-x['solar_maintenance_rate'])+x['solar_annual_depreciation']
    solar=annuity(solar_cf,x['solar_remaining_years'],rate,x['solar_final_recovery'])
    financial=x['cash_20260930']-x['paid_oct_dividend']-x['repurchase_paid_oct']-x['minimum_group_cash']-(x['short_bank_debt']+x['long_bank_debt']+x['current_long_bank_debt'])
    prepaid=sum(x['annual_incentive_charge']/(1+rate)**t for t in range(1,6))-(x['repurchase_total_budget']-x['repurchase_paid_oct'])/(1+rate)
    recovery=sum((x['government_receivable_collection'][t]+x['equity_asset_collection'][t])/(1+rate)**(t+1) for t in range(10))
    bridge=financial+solar+prepaid+recovery
    return dict(mfg_nopat=mfg_nopat,multiples=[13,16],finite_solar=solar,financial_bridge_before_solar=financial,prepaid_incentive_timing=prepaid,asset_recoveries_pv=recovery,total_bridge=bridge,per_share=[(mfg_nopat*k+bridge)/x['shares'] for k in [13,16]])

def scenarios(x):
    z={}
    for label in ['base','core_low','core_high','cycle','structural','upside','margin_down_1pp','slower_upstream','parent_cash_20','extra_settlement_78','capital_intensity_1_5','repurchase_250','solar_low','cash_minus100','bank_plus25','no_short_refinancing']:
        a=copy.deepcopy(x)
        if label=='core_low':a['electric_nopat_margin']=[v-.01 for v in a['electric_nopat_margin']];a['growth_capital_per_incremental_sales']=1.25
        if label=='core_high':a['electric_nopat_margin']=[v+.005 for v in a['electric_nopat_margin']];a['growth_capital_per_incremental_sales']=1.0
        if label=='margin_down_1pp':a['electric_nopat_margin']=[v-.01 for v in a['electric_nopat_margin']]
        if label=='cycle':
            a['growth']['domestic'][:3]=[-.10,0,.12];a['growth']['export'][:3]=[-.05,.08,.25]
            a['electric_nopat_margin'][:3]=[.275,.295,.315];a['parent_net_other_settlement']=[78,-39,-39,0,0,0,0,0,0,0]
        if label=='structural':
            a['growth']['domestic']=[-.15,-.05]+[.01]*8;a['growth']['export']=[-.20,-.05]+[.02]*8
            a['electric_nopat_margin']=[.23]*10;a['growth_capital_per_incremental_sales']=1.5;a['stable_growth']=.01;a['stable_incremental_roic']=.12
            a['bank_repayment']=[100,100,100,150,134.99458888,100,0,0,0,0]
        if label=='upside':
            a['growth']['export'][:5]=[.28,.25,.20,.16,.12];a['electric_nopat_margin']=[v+.015 for v in a['electric_nopat_margin']];a['growth_capital_per_incremental_sales']=1.0
        if label=='slower_upstream':a['upstream_received_fraction']=.8
        if label=='parent_cash_20':a['parent_cash_budget']=20
        if label=='extra_settlement_78':a['parent_net_other_settlement']=[78,-78,0,0,0,0,0,0,0,0]
        if label=='capital_intensity_1_5':a['growth_capital_per_incremental_sales']=1.5
        if label=='repurchase_250':
            a['repurchase_total_budget']=250;a['annual_incentive_charge']=50
        if label=='solar_low':a['base_revenue_2026']['solar_other']=50;a['solar_other_nopat_margin']=.10;a['solar_remaining_years']=15
        if label=='cash_minus100':a['cash_20260930']-=100
        if label=='bank_plus25':
            a['current_long_bank_debt']+=25;a['bank_repayment'][4]+=25
        if label=='no_short_refinancing':a['bank_repayment']=[414,150,120.99458888,0,0,0,0,0,0,0]
        try:
            rows=forecast(a);rate=.105 if label=='core_low' else .09 if label=='core_high' else a['discount_base']
            z[label]={'adopted_discount':rate,'value':value(a,rows,rate),'first5_distributions':[r['dividend_per_share'] for r in rows[:5]],'cash_minimum':min(r['cash_end'] for r in rows),'parent_cash_minimum':min(r['parent_cash_end'] for r in rows),'rows':rows,'inputs':a}
        except ValueError as e:z[label]={'infeasible':str(e)}
    return z

def run():
    x=json.loads((P/'2026-Q3-inputs.json').read_text(encoding='utf-8-sig'));s=scenarios(x);b=s['base'];r=b['rows']
    # 已知可手算特例进入正式持有人折现函数：每年1、第五年价值10、折现10%，现值恰10。
    assert math.isclose(holder_value([1]*5,10,.1),10,abs_tol=1e-12)
    assert holder_value([1]*5,10,0)==15
    low=s['core_low']['value']['current_per_share'];high=s['core_high']['value']['current_per_share']
    rm={'schema_version':1,'method':'annual_common_equity_irr_v1','currency':'CNY','model_as_of':x['information_cutoff'],'base_case_distributions_per_share':[round(v,8) for v in b['first5_distributions']],'base_case_terminal_equity_value_range_per_share':{'year_5':{'low':round(value(x,r,.105)['terminal_year5_per_share'],8),'high':round(value(x,r,.09)['terminal_year5_per_share'],8)}}}
    output={'schema':'trading_os_research_result_v1','symbol':'CN:002270','report_period':'2026-Q3','information_cutoff':x['information_cutoff'],'value_range':{'low':round(low,2),'high':round(high,2),'currency':'CNY'},'return_model':rm,'notes':['金额CNY，每股以896225431股完全稀释口径。主法为十年持有人实际分配及分配后持续经营价值折现。','股份支付/回购仅承担一次现金；已付0.26元分红退出未来现金，库存股最终重新授予。','子股息应收回收不增加母利润；集团现金、母现金、法定留存及内部划款约束分别执行。','终值制造2%增长/18%新增资本回报；光伏有限20年，额外现金在第十年后基准六年释放；未计H股资金。']}
    output.update({'valuation_note': '核心为十年实际分配及后续经济价值折现，资本成本9%—10.5%；下端设备经营率低1个百分点/新增资本1.25元每元收入，上端高0.5个百分点/资本1.0元。制造十年后2%增长/18%新增资本回报，光伏有限20年，额外本金按可约束时点释放。辅助正常制造收益13—16倍加同义务净桥为11.86—14.53元；不取平均，结构失败和乐观路径不并入核心区间。', 'return_model_note': '未来五年每股分配0.53406716/0.58961512/0.64958746/0.70583446/0.75441111元，为母法定利润、到账与集团资金约束后的预算。第五年末13.90084365—17.00136981元由同一基准第五年后的分红、持续制造及有限光伏现金、分配后留存本金推导，按9%—10.5%资本成本；完全稀释896225431股。已付0.26元退出未来现金，回购股份用于激励、现金与补偿只承担一次，不预计H股募集资金；经营租赁留在现金经营成本，银行本金五年内清偿。'})
    (P/'2026-Q3-output.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    compact={k:{a:v for a,v in v.items() if a not in ['inputs','rows']} for k,v in s.items()}
    diagnostics={'auxiliary':auxiliary_value(x,r),'base_rows':r,'scenarios':compact,'base_value':b['value'],'cash_bridge':{'starting_group_cash':x['cash_20260930']-x['paid_oct_dividend']-x['repurchase_paid_oct'],'bank_debt':x['short_bank_debt']+x['long_bank_debt']+x['current_long_bank_debt'],'operating_lease_excluded_from_bank_debt':x['operating_lease_liability']},'hand_case':{'distributions':[1]*5,'terminal':10,'discount':.1,'result':holder_value([1]*5,10,.1),'independent_hand_result':10}}
    (WORK / '2026-Q3-diagnostics.json').write_text(json.dumps(diagnostics,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(output,ensure_ascii=False))
if __name__=='__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    run()
