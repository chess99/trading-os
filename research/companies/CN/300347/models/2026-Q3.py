#!/usr/bin/env python3
"""泰格医药2026-Q3：原表勾稽、经营估值和资本边界诊断。

运行: python 2026-Q3.py [--output PATH]
金额单位CNY十亿元，股数十亿股。只用同目录输入及Python标准库。
正式总权益价值与持有人接口留空；诊断数值不得当作已采纳的总估值。
"""
import argparse
import copy
import json
from pathlib import Path


def operating_path(a):
    """服务经营路径；不含金融本金、投资收益、基金管理收益及融资。"""
    old_revenue = a['opening_revenue']
    capital = a['opening_operating_capital']
    out = []
    for t in range(1, 11):
        growth = a['growth'][t - 1]
        revenue = old_revenue * (1 + growth)
        margin = a['margins'][t - 1]
        ebit = revenue * margin
        nopat = ebit * (1 - a['tax'])
        da = revenue * a['da_ratio']
        growth_ppe = max(revenue - old_revenue, 0) * a['growth_ppe_ratio']
        capex = da + growth_ppe
        delta_wc = (revenue - old_revenue) * a['working_capital_ratio']
        reinvestment = capex - da + delta_wc
        fcf = nopat - reinvestment
        old_capital = capital
        capital += reinvestment
        assert abs(capital - old_capital - reinvestment) < 1e-10
        assert abs(fcf + capex + delta_wc - nopat - da) < 1e-10
        out.append(dict(year=t, revenue=revenue, ebit=ebit, nopat=nopat,
                        da=da, capex=capex, delta_wc=delta_wc, fcf=fcf,
                        operating_capital=capital,
                        roic_without_goodwill=nopat / ((old_capital + capital) / 2)))
        old_revenue = revenue
    return out


def discounted_business(rows, rate, terminal_growth, terminal_roic):
    """同一经营企业价值函数同时用于正式诊断及手算特例。"""
    assert rate > terminal_growth and terminal_roic > terminal_growth
    final_nopat = rows[-1]['nopat']
    next_nopat = final_nopat * (1 + terminal_growth)
    terminal_fcf = next_nopat * (1 - terminal_growth / terminal_roic)
    terminal = terminal_fcf / (rate - terminal_growth)
    annual_pv = sum(x['fcf'] / (1 + rate) ** x['year'] for x in rows)
    terminal_pv = terminal / (1 + rate) ** rows[-1]['year']
    return dict(business_enterprise_value=annual_pv + terminal_pv,
                annual_fcf_pv=annual_pv, terminal_pv=terminal_pv,
                terminal_pv_fraction=terminal_pv / (annual_pv + terminal_pv),
                terminal_fcf=terminal_fcf, rate=rate,
                terminal_growth=terminal_growth, terminal_roic=terminal_roic)


def normalized_business(rows, multiple, rate, anchor_year=3):
    """在第3年将经营EBIT资本化，折现并加之前的经营现金。"""
    anchor = rows[anchor_year - 1]
    early = sum(x['fcf'] / (1 + rate) ** x['year']
                for x in rows if x['year'] <= anchor_year)
    return dict(business_enterprise_value=early + anchor['ebit'] * multiple /
                (1 + rate) ** anchor_year, anchor_year=anchor_year,
                anchor_ebit=anchor['ebit'], enterprise_ebit_multiple=multiple,
                rate=rate)


def funding_boundary(rows, opening_cash, call_schedule, other_payment,
                     deposit_release, early_exits, late_exits,
                     award_cash, reserve=1.0, rate=0.045):
    """集团合并最宽资金测试：call年初、经营及晚退出年末。

    这不是母/子公司提款或可分配利润认证。已存债假设正常续作，另付
    年息0.086；新循环融资由本函数计算利息及偿还。股利设零仅用于找
    最大资金边界，不构成未来零股利预测。
    """
    cash = opening_cash
    debt = peak = 0.0
    records = []
    for i, call in enumerate(call_schedule):
        opening, debt_open = cash, debt
        cash += deposit_release[i] + early_exits[i]
        cash -= call + other_payment[i]
        draw = max(reserve - cash, 0)
        debt += draw
        cash += draw
        peak = max(peak, debt)
        interest = debt * rate + 0.086
        cash += rows[i]['fcf'] + late_exits[i] + award_cash[i] - interest
        repay = min(debt, max(cash - reserve, 0))
        cash -= repay
        debt -= repay
        # Any interest-period shortfall is financed and retained, not silently ignored.
        end_draw = max(reserve - cash, 0)
        cash += end_draw
        debt += end_draw
        peak = max(peak, debt)
        expected = (opening + deposit_release[i] + early_exits[i] - call -
                    other_payment[i] + draw + rows[i]['fcf'] + late_exits[i] +
                    award_cash[i] - interest - repay + end_draw)
        assert abs(cash - expected) < 1e-10
        assert abs(debt - (debt_open + draw + end_draw - repay)) < 1e-10
        records.append(dict(year=i+1, call=call, deposit_release=deposit_release[i],
                            exits=early_exits[i] + late_exits[i],
                            operation_fcf=rows[i]['fcf'], award_cash=award_cash[i],
                            new_draw=draw + end_draw, repay=repay,
                            financing_interest=interest, closing_cash=cash,
                            closing_new_debt=debt))
    return dict(peak_additional_revolving_credit=peak,
                ending_additional_debt=debt, rows=records)


def future_commitment_npv(calls, exit_year, recovery_multiple, rate):
    # New assets are acquired as cash is paid. Exit receipts include all principal
    # and profit; there is no second addition of their cost or book value.
    outflow = sum(v / (1 + rate) ** (i + 1) for i, v in enumerate(calls))
    receipt = sum(calls) * recovery_multiple
    asset_pv = receipt / (1 + rate) ** exit_year
    return dict(cash_call_pv=outflow, acquired_right_receipt=receipt,
                acquired_right_pv=asset_pv, net_present_effect=asset_pv-outflow,
                exit_year=exit_year, gross_recovery_multiple=recovery_multiple)


def self_tests():
    # A constant, fully distributable 100-unit perpetuity is worth 100/10%=1000.
    # This passes the hand case through the SAME function used for the diagnostics.
    rows = [dict(year=i, fcf=100., nopat=100.) for i in range(1, 11)]
    actual = discounted_business(rows, .1, 0., .2)
    assert abs(actual['business_enterprise_value'] - 1000.) < 1e-9
    # One principal outflow followed by an identical one-year-later cash return
    # loses precisely the time value, not the whole contribution.
    c = future_commitment_npv([1.], 2, 1., .1)
    assert abs(c['net_present_effect'] - (1/1.1**2 - 1/1.1)) < 1e-12
    # Cancelling existing treasury shares changes registered and treasury counts
    # equally; it never reduces outside-holder shares a second time.
    registered, treasury, cancel = .861026050, .026847258, .005883780
    assert abs((registered-treasury) -
               ((registered-cancel)-(treasury-cancel))) < 1e-12


def compute(data):
    self_tests()
    f = data['facts']
    q3 = {k: f['nine_months'][k]-f['half_year'][k]
          for k in ['revenue','common_profit','common_adjusted_profit','operating_cf','cost']}
    q3['gross_margin'] = 1-q3['cost']/q3['revenue']
    nine = f['nine_months']
    operating_ebit = nine['revenue'] - sum(nine[k] for k in
                        ['cost','tax_and_surcharge','selling','administrative','research'])
    registered = f['registered_q3'] - sum(f['completed_cancellations'])
    treasury = f['treasury_q3'] - sum(f['completed_cancellations'])
    outside = registered - treasury
    fully_diluted = outside + f['awards_granted']
    share_bridge = dict(registered_after_cancellations=registered,
                       treasury_after_cancellations=treasury,
                       outside_current=outside, fully_diluted_if_awards_vest=fully_diluted,
                       conditional_employee_cash=f['awards_granted']*f['award_price'])
    rows = operating_path(data['operating_assumptions'])
    rate = data['operating_assumptions']['rate']
    dcf = {name: discounted_business(rows, r, .025, .16)
           for name, r in [('low',.115),('reference',rate),('high',.095)]}
    auxiliary = {str(m): normalized_business(rows, m, rate) for m in [12,14,16]}
    lower_margin = copy.deepcopy(data['operating_assumptions'])
    lower_margin['margins'] = [v-.01 for v in lower_margin['margins']]
    margin_effect = (discounted_business(operating_path(lower_margin),rate,.025,.16)
                     ['business_enterprise_value']-dcf['reference']['business_enterprise_value'])
    funding = {}
    calls = [2.,2.,2.]
    other = [f['other_investment_commitment']+f['acquisition_tail'],0,0]
    awards = [0,0,0]  # The boundary does not depend on conditional award subscriptions.
    for name, cds, early, late in [
        ('no_deposit_or_exit',[0,0,0],[0,0,0],[0,0,0]),
        ('deposit_upper_bound',[f['other_noncurrent_assets_q3'],0,0],[0,0,0],[0,0,0]),
        ('deposits_and_late_exits',[f['other_noncurrent_assets_q3'],0,0],[0,0,0],[.5,.5,.5]),
        ('deposits_and_early_exits',[f['other_noncurrent_assets_q3'],0,0],[.5,.5,.5],[0,0,0])]:
        funding[name] = funding_boundary(rows,f['cash_equivalents_q3'],calls,other,
                                          cds,early,late,awards)
    book = f['long_term_equity_q3']+f['other_noncurrent_financial_q3']+f['other_equity_q3']
    # A net-book allocation EXAMPLE, not a strict ownership bound: NCI is net
    # equity and cannot cap its gross claim on any individual asset category.
    asset_bound = dict(gross_book=book,
                      example_net_book_if_all_nci_deducted_here=book-f['nci_equity_q3'],
                      gross_book_before_nci_allocation=book,
                      q3_company_total_common_equity=f['common_equity_q3'],
                      level3_fraction_h1=f['level3_financial_h1']/f['financial_h1'])
    investment_diagnostics = {}
    for y in [3,6,10]:
        for h in [.6,1.0]:
            investment_diagnostics[f'recovery_{h}_year_{y}'] = {
                'pv_before_nci_tax_and_fees':book*h/(1+rate)**y,
                'gross_recovery_fraction':h,'year':y}
    commitment = {str(m):future_commitment_npv(calls,6,m,rate) for m in [.5,1.,1.4]}
    first,last = rows[0],rows[4]
    public_result = (dict(symbol='CN:300347',report_period='2026-Q3',
                information_cutoff=data['information_cutoff'],value_range=None,return_model=None,
                publication_reason=data['publication_reason'],
                quarter_reconciliation=q3,nine_month_operating_ebit=operating_ebit,
                nine_month_operating_ebit_margin=operating_ebit/nine['revenue'],
                reported_operating_cf_less_capex=nine['operating_cf']-f['capex_nine_months'],
                parent_h1_cash_after_declared_distribution_proforma=f['parent_cash_h1']-f['parent_dividend_payable_h1'],
                parent_h1_dividend_cash_implied_by_balance_bridge=f['parent_dividends_receivable_open']+f['parent_cost_method_dividend_h1']-f['parent_dividends_receivable_h1'],
                share_bridge=share_bridge,
                operating_diagnostic=dict(first_five=rows[:5],year10=rows[-1],
                    discounted_business=dcf,normalized_business=auxiliary,
                    year1_roic_including_goodwill=first['nopat']/((data['operating_assumptions']['opening_operating_capital']+first['operating_capital'])/2+f['goodwill_q3']),
                    year5_roic_including_goodwill=last['nopat']/((rows[3]['operating_capital']+last['operating_capital'])/2+f['goodwill_q3']),
                    year1_to_year5_profit_over_capital_increase=(last['nopat']-first['nopat'])/(last['operating_capital']-first['operating_capital']),
                    one_percentage_point_margin_effect=margin_effect),
                financial_net_book_allocation_example=asset_bound,
                financial_recovery_diagnostics=investment_diagnostics,
                commitment_rights_diagnostics=commitment,
                consolidated_funding_boundaries=funding,
                tests='constant perpetuity, delayed principal, treasury cancellation, operating capital and cash/debt conservation passed'))
    public_result.update({'information_cutoff': '2026-11-06T23:59:59+08:00', 'valuation_note': '总普通股核心价值暂不估计。服务经营主法为十年DCF：渐进恢复、10.5%资本成本，9.5%—11.5%边界、长期增长2.5%及终端增量资本回报16%，得到合并经营企业价值92.1—120.5亿元；辅助第三年12—16倍EBIT得132.6—171.8亿元，其中枢较高约46%，来自更长高回报资本化，未平均。金融本金143.30亿元、少数净权益36.24亿元及新增认缴60亿元对全公司价值有决定性影响；公开披露不能充分约束新权利经济性、主要退出资金归属与期限，未用任意折扣或主体上划比例填成核心区间。融资量级检验支持若干正常路径，不等于集团现金危机。', 'return_model_note': '五年实际现金分配与第五年普通股终值暂留空。集团经营现金、母公司法定利润及可用现金、投资平台回收与call安排需要相容预算，主要资本来源和新增项目权利仍未充分约束。已实施0.126元分配不直接年金化；Q3现金不重复扣7月分红。最新登记855142270股、库存20963478股，外部普通股834178792股；9174770股条件全部归属后843353562股并带来条件缴款3.608亿元。没有将经营自由现金、回购或金融本金直接当作持有人分配，也未将当前经营诊断复制为第五年终值。'}, schema='trading_os_research_result_v1')
    return public_result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output')
    a = p.parse_args()
    data=json.loads(Path(__file__).with_name('2026-Q3-inputs.json').read_text(encoding='utf-8'))
    result=compute(data)
    s=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    if a.output: Path(a.output).write_text(s,encoding='utf-8')
    else: print(s,end='')


if __name__=='__main__':main()
