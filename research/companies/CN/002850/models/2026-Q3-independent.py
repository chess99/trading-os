"""独立复算：直接预算与二分求融资利息，现金向量逐项折现；不导入正式预算函数。"""
import json
import math
import runpy
from pathlib import Path

P = Path(__file__).resolve().parent
WORK = P.parent / ".work"
WORK.mkdir(parents=True, exist_ok=True)
import sys
sys.stdout.reconfigure(encoding="utf-8")
a = json.loads((P / "2026-Q3-inputs.json").read_text(encoding="utf-8"))
# The comparison target is generated now; independent arithmetic below uses only inputs.
import subprocess, sys
current = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(P/'2026-Q3.py'), '--details'], cwd=P, capture_output=True, text=True, encoding='utf-8', check=True)
expected = json.loads(current.stdout)
f, c = a["facts"], a["base"]
shares = f["q3_issued_shares"] + f["contingent_registered_shares_upper"]
total_cash = sum([f["q3_cash_equivalents"], f["q3_financial_assets"], f["matched_option_proceeds_upper"], -f["buyback_increment_paid_october"], -f["minority_cash_reserve_budget"]])
pcash = f["parent_h1_cash_and_financial_assets"] - f["buyback_increment_paid_october"] + f["matched_option_proceeds_upper"]
debt = f["q3_debt_and_leases"]
project = c["earmarked_project_cash_start"]
rev = c["revenue_start"]
divs, cash_rows = [], []
for n in range(5):
    delta = rev * c["growth"][n]
    rev += delta
    p = rev * c["after_tax_common_operating_margin"][n]
    cap = delta * (c["incremental_fixed_capital_per_revenue"] + c["incremental_working_capital_per_revenue"]) - c["paid_prebuilt_capacity_credit"][n] + c["opening_capital_credit_settlement"][n] + c["additional_overseas_robot_common_capital"][n]
    project = max(0, project - c["project_cash_release_limit"][n])
    floor = c["operating_cash_floor"] + project
    yield_cash = max(0, total_cash - c["operating_cash_floor"]) * c["cash_yield_after_tax"]
    repurchase = f["buyback_future_budget"] if n == 0 else 0
    declared = p * c["huizhou_jiangsu_profit_share"] * c["subsidiary_payout_fraction"]
    assert declared <= p * c["huizhou_jiangsu_profit_share"] * 0.9
    # Baseline cash and legal limits select parent's available-cash branch in every year.
    d0 = pcash + p * c["parent_own_profit_share"] + declared - c["parent_capital_share"] * cap - repurchase - c["parent_cash_floor"]
    def at_interest(i):
        d = min(shares * c["dividend_target_per_share"][n], max(0, d0 - c["parent_interest_share"] * i))
        before = total_cash + p + yield_cash - cap - repurchase - d - i
        new_borrow = max(0, floor - before)
        return d, before, new_borrow
    lo, hi = 0.0, 1.0
    for _ in range(70):
        i = (lo + hi) / 2
        draw = at_interest(i)[2]
        if i < debt * c["debt_interest"] + draw * c["debt_interest"] / 2:
            lo = i
        else:
            hi = i
    interest = (lo + hi) / 2
    dividend, before, draw = at_interest(interest)
    repay = min(debt + draw, max(0, before + draw - floor))
    newcash = before + draw - repay
    pcash += p*c["parent_own_profit_share"] + declared - cap*c["parent_capital_share"] - interest*c["parent_interest_share"] - repurchase - dividend
    debt += draw - repay
    assert abs(total_cash + p + yield_cash - cap - interest - dividend - repurchase + draw - repay - newcash) < 1e-10
    assert debt < c["debt_limit"] and pcash >= c["parent_cash_floor"] - 1e-10
    total_cash = newcash
    divs.append(dividend / shares)
    cash_rows.append({"year":n+1,"cash":total_cash,"debt":debt,"parent_cash":pcash,"dividend_per_share":divs[-1]})


def independent_endpoint(rate, roic, g):
    years = len(c["tail_profit_growth"])
    profits = [p * math.prod(1 + x for x in c["tail_profit_growth"][:t]) for t in range(1, years+1)]
    prev = [p] + profits[:-1]
    cashflows = [new - (new-old)/roic for new,old in zip(profits,prev)]
    annuity = sum(cf/(1+rate)**t for t,cf in enumerate(cashflows,1))
    tv12 = (profits[-1]*(1+g)-profits[-1]*g/roic)/(rate-g)
    tailpv = tv12/(1+rate)**years
    eq5 = annuity + tailpv + total_cash - c["operating_cash_floor"] - project - debt
    tv5 = eq5/shares
    present_divs = sum(x/(1+rate)**t for t,x in enumerate(divs,1))
    return {"current":present_divs+tv5/(1+rate)**5,"year5":tv5,"tail_explicit_pv":annuity,"tail_perpetuity_pv":tailpv}


checks = {}
for name,e in a["endpoints"].items():
    calc = independent_endpoint(e["equity_cost"],e["incremental_return"],e["terminal_growth"])
    ref = expected["details"]["base"]["endpoints"][name]
    assert abs(calc["current"]-ref["current"]) < 1e-9
    assert abs(calc["year5"]-ref["year5"]) < 1e-9
    checks[name] = calc
assert max(abs(x-y) for x,y in zip(divs,expected["return_model"]["base_case_distributions_per_share"])) < 1e-9
assert abs(debt-expected["details"]["base"]["budget"]["debt_5"]) < 1e-9
low = a["endpoints"]["low"]
changed = independent_endpoint(low["equity_cost"],0.10,low["terminal_growth"])
# Use the adopted tail function solely as the comparison implementation.
formal = runpy.run_path(str(P/"2026-Q3.py"))
formal_tail = formal["operating_value"](p,c["tail_profit_growth"],0.10,low["equity_cost"],low["terminal_growth"])
formal_current = sum(x/(1+low["equity_cost"])**t for t,x in enumerate(divs,1)) + (formal_tail["value"] + total_cash-c["operating_cash_floor"]-project-debt)/shares/(1+low["equity_cost"])**5
assert abs(changed["current"]-formal_current) < 1e-9
summary={"status":"passed","scope":"基准五年资金、母公司现金、普通股分配、两个核心端点；支配性尾期增量回报12%降至10%的独立复算。其他情景完成正式函数预算，未声称独立逐一复算。",
         "endpoints":checks,"dominant_parameter":{"tail_incremental_return_from":0.12,"to":0.10,"current_before":checks["low"]["current"],"current_after":changed["current"],"change":changed["current"]-checks["low"]["current"]},
         "five_year_budget":cash_rows,"same_function_hand_examples":formal["tests"](),"max_allowed_numeric_error":1e-9}
# Independent source arithmetic for the newly material capital bridge.
asset_delta = sum(f["long_term_operating_assets_q3"][k]-f["long_term_operating_assets_h1"][k] for k in f["long_term_operating_assets_q3"])
lo_credit = f["equipment_construction_payables_h1"] + asset_delta + 0.22 - f["q3_capex_cash"] - 0.15
hi_credit = f["equipment_construction_payables_h1"] + asset_delta + 0.28 + 0.04 - f["q3_capex_cash"] + 0.15
capacity = f["long_term_operating_assets_q3"]["cip"]+f["long_term_operating_assets_q3"]["prepaid_long_term"]-f["headquarters_full_project_budget"]-f["capital_credit_q3_budget"]
assert abs(asset_delta-expected["details"]["capital_bridge"]["long_term_asset_net_increase_q3"]) < 1e-12
assert abs(lo_credit-expected["details"]["capital_bridge"]["capital_credit_q3_bridge_range"][0]) < 1e-12
assert abs(hi_credit-expected["details"]["capital_bridge"]["capital_credit_q3_bridge_range"][1]) < 1e-12
assert sum(c["paid_prebuilt_capacity_credit"]) <= capacity
summary["capital_bridge_independent"]={"asset_delta":asset_delta,"closing_credit_range":[lo_credit,hi_credit],"paid_capacity_bound":capacity,"adopted_prebuilt_credit":sum(c["paid_prebuilt_capacity_credit"])}
(WORK/"2026-Q3-verification.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(summary,ensure_ascii=False,indent=2))
