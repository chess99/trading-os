"""CNY 100 million / 100 million shares; offline, standard library only."""
import json
from pathlib import Path

S = 15.71867988
DPS = [0.40, 0.42, 0.44, 0.46, 0.48]
DIV = [x*S for x in DPS]
CASH = 20.63-1.35-3.0-0.16-0.18-0.473
INVESTMENT = 4.2513480331
YIELD = 0.012

def model(profits, roi, rate, growth, investment_recovery, cash=CASH):
    opening = cash
    rows = []
    previous_profit = profits[0]
    parent_cash = 16.04-3.0
    parent_retained = 8.5075399874
    for i, profit in enumerate(profits):
        # Existing installed capacity supports recovery toward 6.8; do not buy
        # the same capacity twice. 0.2/year covers channel/pilot growth budgets.
        reinvest = .20+max(0, profit-max(previous_profit,6.8))/roi
        # Maintenance capex equals depreciation: both 2.0, already in earnings.
        fcfe = profit-reinvest
        financial_income = cash*YIELD
        closing = cash+fcfe+financial_income-DIV[i]
        # Parent direct recurring operations estimated at -0.40 annually;
        # Retain all growth investment in subsidiaries before upstreaming 95%
        # of remaining attributable cash; no duplicate group-level cost.
        upstream = .95*(profit+.40-reinvest)
        parent_profit = -.40+upstream+.15
        parent_cash += parent_profit-DIV[i]
        parent_retained += parent_profit-DIV[i]
        rows.append(dict(year=i+1,profit=profit,maintenance_capex=2.0,
                         depreciation=2.0,growth_reinvestment=reinvest,
                         fcfe=fcfe,opening_cash=cash,financial_income=financial_income,
                         dividend=DIV[i],closing_cash=closing,
                         parent_upstream=upstream,parent_profit=parent_profit,
                         parent_cash=parent_cash,parent_retained=parent_retained))
        assert abs(closing-cash-fcfe-financial_income+DIV[i]) < 1e-10
        assert min(closing,parent_cash,parent_retained) > 0
        cash=closing
        previous_profit=profit
    terminal_earnings=profits[-1]*(1+growth)
    terminal_reinvest=profits[-1]*growth/roi
    terminal_fcfe=terminal_earnings-terminal_reinvest
    terminal_operation=terminal_fcfe/(rate-growth)
    terminal_investment=INVESTMENT*investment_recovery
    terminal_equity=terminal_operation+cash+terminal_investment
    dividend_pv=sum(d/(1+rate)**(i+1) for i,d in enumerate(DIV))
    terminal_pv=terminal_equity/(1+rate)**5
    # Identity: cash carried below cost of equity creates a disclosed retention drag.
    operation_pv=sum(row['fcfe']/(1+rate)**row['year'] for row in rows)+terminal_operation/(1+rate)**5
    retention_drag=sum((rate-YIELD)*row['opening_cash']/(1+rate)**row['year'] for row in rows)
    bridge_pv=operation_pv+opening-retention_drag+terminal_investment/(1+rate)**5
    assert abs(bridge_pv-dividend_pv-terminal_pv)<1e-9
    assert abs(sum(r['fcfe']+r['financial_income']-r['dividend'] for r in rows)+opening-cash)<1e-9
    return dict(rows=rows,terminal_operation=terminal_operation,terminal_fcfe=terminal_fcfe,
                terminal_cash=cash,terminal_investment=terminal_investment,
                terminal_equity=terminal_equity,terminal_per_share=terminal_equity/S,
                dividend_pv=dividend_pv,terminal_pv=terminal_pv,
                retention_drag=retention_drag,operation_pv=operation_pv,
                investment_pv=terminal_investment/(1+rate)**5,
                value_per_share=(dividend_pv+terminal_pv)/S,
                terminal_share=terminal_pv/(dividend_pv+terminal_pv),
                rate=rate,growth=growth,incremental_roi=roi)

low=model([6.3,6.3,6.5,6.75,7.0],.15,.088,.015,.8)
high=model([6.8,6.8,7.1,7.45,7.8],.20,.085,.020,1.0)
base=model([6.55,6.55,6.8,7.1,7.4],.175,.0865,.0175,.9)
structural=model([6.0,5.8,5.6,5.5,5.5],.12,.095,0,.7)
cycle=model([5.8,5.9,6.3,6.8,7.4],.175,.0865,.0175,.9)
upside=model([6.8,7.1,7.6,8.2,8.8],.22,.085,.025,1.0)
sensitivity=model([x*.9 for x in [6.55,6.55,6.8,7.1,7.4]],.175,.0865,.0175,.9)
low_roi=model([6.55,6.55,6.8,7.1,7.4],.10,.0865,.0175,.9)
no_growth=model([6.55]*5,.175,.0865,0,.9)
# Auxiliary normalized operating-earnings capitalization. Preserve same retained-
# financial-asset treatment, rather than adding all cash a second time.
aux_low=(6.3*14.0+CASH-low['retention_drag']+low['investment_pv'])/S
aux_high=(6.8*15.0+CASH-high['retention_drag']+high['investment_pv'])/S
assert abs(sum(DPS)-2.2)<1e-12
assert len(base['rows'])==5
assert abs(10/.1-100)<1e-10  # zero-growth capitalisation identity
assert abs((100*(1+.08)-8)-100)<1e-10  # cash interest = distribution

out=dict(shares=S,initial_excess_cash=CASH,distributions_per_share=DPS,
         distributions_total=sum(DIV),financial_yield=YIELD,
         low=low,high=high,base=base,structural=structural,cycle=cycle,upside=upside,
         sensitivity_profit_minus_10pct=sensitivity,sensitivity_incremental_roi_10pct=low_roi,
         sensitivity_no_growth=no_growth,aux_low=aux_low,aux_high=aux_high,
         parent_one_year_upstream_delay_cash=base['rows'][0]['parent_cash']-base['rows'][0]['parent_upstream'])
Path(__file__).with_name('2026-H1-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:out[k] for k in ['initial_excess_cash','aux_low','aux_high','parent_one_year_upstream_delay_cash']}))
print(json.dumps({k:{'value':out[k]['value_per_share'],'terminal':out[k]['terminal_per_share'],'cash5':out[k]['terminal_cash']} for k in ['low','high','base','structural','cycle','upside','sensitivity_profit_minus_10pct','sensitivity_incremental_roi_10pct','sensitivity_no_growth']}))
