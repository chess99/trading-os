"""科达利：标准库模型。python 2026-Q3.py [--details | --test]。金额为十亿元。"""
import argparse
import copy
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def capital_bridge(inp):
    """Use balance-sheet changes to bound net capital settlement credit, without tracking old invoice batches."""
    f = inp["facts"]
    delta = sum(f["long_term_operating_assets_q3"].values()) - sum(f["long_term_operating_assets_h1"].values())
    dlow, dhigh = f["q3_depreciation_amortization_budget_range"]
    llow, lhigh = f["q3_capital_disposal_loss_budget_range"]
    tolerance = f["capital_classification_noncash_tolerance"]
    implicit_low = f["equipment_construction_payables_h1"] + delta + dlow + llow - f["q3_capex_cash"] - tolerance
    implicit_high = f["equipment_construction_payables_h1"] + delta + dhigh + lhigh - f["q3_capex_cash"] + tolerance
    prepaid_cip = f["long_term_operating_assets_q3"]["cip"] + f["long_term_operating_assets_q3"]["prepaid_long_term"]
    paid_capacity_bound = max(0, prepaid_cip - f["headquarters_full_project_budget"] - f["capital_credit_q3_budget"])
    h1_delta = sum(f["long_term_operating_assets_h1"].values()) - sum(f["long_term_operating_assets_fy25"].values())
    h1_residual = h1_delta + f["h1_depreciation_amortization_excluding_rou"] - f["h1_capex_cash"] - (f["equipment_construction_payables_h1"] - f["equipment_construction_payables_fy25"])
    return {"long_term_asset_net_increase_q3":delta,"q3_capex_cash":f["q3_capex_cash"],
            "h1_bridge_residual_before_disposals_fx_classification":h1_residual,
            "capital_credit_q3_bridge_range":[implicit_low,implicit_high],
            "capital_credit_q3_adopted_range":f["capital_credit_q3_budget_range"],
            "capital_credit_q3_adopted":f["capital_credit_q3_budget"],
            "cip_and_prepay_q3":prepaid_cip,"headquarters_budget_reserved":f["headquarters_full_project_budget"],
            "paid_capacity_bound_central":paid_capacity_bound,
            "paid_capacity_credit_adopted":sum(inp["base"]["paid_prebuilt_capacity_credit"])}


def operating_value(profit, growths, roic, discount, terminal_growth):
    """未来经营现金：税后经营利润-取得新增利润所需资本；最后一期后采用Gordon。"""
    pv = 0.0
    for t, growth in enumerate(growths, 1):
        next_profit = profit * (1 + growth)
        investment = (next_profit - profit) / roic
        pv += (next_profit - investment) / (1 + discount) ** t
        profit = next_profit
    terminal_cash = profit * (1 + terminal_growth) - profit * terminal_growth / roic
    terminal = terminal_cash / (discount - terminal_growth)
    tail_pv = terminal / (1 + discount) ** len(growths)
    return {"value": pv + tail_pv, "explicit_cash_pv": pv, "perpetuity_pv": tail_pv,
            "terminal_year_profit": profit, "terminal_next_cash": terminal_cash}


def simulate(inp, cfg):
    f = inp["facts"]
    shares = f["q3_issued_shares"] + f["contingent_registered_shares_upper"]
    cash = f["q3_cash_equivalents"] + f["q3_financial_assets"] - f["buyback_increment_paid_october"] + f["matched_option_proceeds_upper"] - f["minority_cash_reserve_budget"]
    project = cfg["earmarked_project_cash_start"]
    debt = f["q3_debt_and_leases"]
    parent_cash = f["parent_h1_cash_and_financial_assets"] - f["buyback_increment_paid_october"] + f["matched_option_proceeds_upper"]
    parent_re = f["parent_h1_retained_profit"]
    parent_reserve = f["parent_h1_statutory_reserve_budget"]
    sub_re = [-x for x in cfg["subsidiary_initial_loss_budget"]]
    sub_reserve = [0.0, 0.0]
    sub_reserve_caps = [0.25, 0.50]
    receivable = 0.0
    prev_declared = 0.0
    parent_bridge = 0.0
    revenue = cfg["revenue_start"]
    rows = []
    for i in range(5):
        opening_cash, opening_debt, opening_parent = cash, debt, parent_cash
        delta_revenue = revenue * cfg["growth"][i]
        revenue += delta_revenue
        profit = revenue * cfg["after_tax_common_operating_margin"][i]
        fixed = delta_revenue * cfg["incremental_fixed_capital_per_revenue"] - cfg["paid_prebuilt_capacity_credit"][i]
        working = delta_revenue * cfg["incremental_working_capital_per_revenue"]
        old_pay = cfg["opening_capital_credit_settlement"][i]
        extra = cfg["additional_overseas_robot_common_capital"][i] + cfg["committed_extra_cash"][i]
        investment = fixed + working + old_pay + extra
        released = min(project, cfg["project_cash_release_limit"][i], max(0, fixed + old_pay + extra))
        project -= released
        # Income on excess/project financial assets. Operating minimum cash earns no separately valued income.
        financial_income = max(0, opening_cash - cfg["operating_cash_floor"]) * cfg["cash_yield_after_tax"]
        own_profit = cfg["parent_own_profit_share"] * profit
        declared = 0.0
        for j, share in enumerate([cfg["huizhou_fraction_of_pair"], 1 - cfg["huizhou_fraction_of_pair"]]):
            sub_profit = profit * cfg["huizhou_jiangsu_profit_share"] * share
            restored = max(0.0, sub_profit + min(0.0, sub_re[j]))
            reserve = min(max(0.0, sub_reserve_caps[j] - sub_reserve[j]), restored * 0.10)
            sub_reserve[j] += reserve
            sub_re[j] += sub_profit - reserve
            payment = min(max(0.0, sub_re[j]), cfg["subsidiary_payout_fraction"] * sub_profit)
            sub_re[j] -= payment
            declared += payment
        received = declared if not cfg["upstream_lag_years"] else prev_declared
        prev_declared = declared
        receivable += declared - received
        # Parent trade receipts and supplier settlements are normalized, rather than annualizing H1 CFO.
        parent_capital = investment * cfg["parent_capital_share"]
        repurchase = f["buyback_future_budget"] if i == 0 else 0.0
        interest = opening_debt * cfg["debt_interest"]
        dividend = 0.0
        # Dividend is cash/profit constrained; new borrowing pays operating/project capital, not a fixed dividend promise.
        for _ in range(30):
            parent_interest = max(interest * cfg["parent_interest_share"], parent_bridge * cfg["debt_interest"])
            parent_net = own_profit - parent_interest + declared
            parent_res = min(max(0.0, cfg["parent_reserve_cap"] - parent_reserve), max(0.0, parent_net) * 0.10)
            parent_capacity = max(0.0, parent_re + parent_net - parent_res)
            parent_before_div = opening_parent + own_profit - parent_interest - parent_capital + received - repurchase
            parent_draw = max(0.0, cfg["parent_cash_floor"] - parent_before_div)
            if parent_bridge + parent_draw > cfg["parent_bridge_limit"] + 1e-9:
                raise ValueError(f"Y{i+1}: parent bridge limit exceeded")
            parent_repay = min(parent_bridge, max(0.0, parent_before_div - cfg["parent_cash_floor"]))
            parent_before_div += parent_draw - parent_repay
            dividend = min(cfg["dividend_target_per_share"][i] * shares, parent_capacity,
                           max(0.0, parent_before_div - cfg["parent_cash_floor"]))
            floor = cfg["operating_cash_floor"] + project
            max_draw = cfg["debt_limit"] - opening_debt
            group_affordable_dividend = max(0.0, opening_cash + profit + financial_income - investment - interest - repurchase + max_draw - floor)
            dividend = min(dividend, group_affordable_dividend)
            cash_before_finance = opening_cash + profit + financial_income - investment - interest - dividend - repurchase
            draw = max(parent_draw, max(0.0, floor - cash_before_finance))
            new_interest = opening_debt * cfg["debt_interest"] + draw * cfg["debt_interest"] * 0.5
            if abs(new_interest - interest) < 1e-13:
                break
            interest = new_interest
        required_debt = opening_debt + draw
        if required_debt > cfg["debt_limit"] + 1e-9:
            raise ValueError(f"Y{i+1}: required debt {required_debt:.6f} exceeds limit {cfg['debt_limit']}")
        parent_interest = max(interest * cfg["parent_interest_share"], parent_bridge * cfg["debt_interest"])
        parent_net = own_profit - parent_interest + declared
        parent_res = min(max(0.0, cfg["parent_reserve_cap"] - parent_reserve), max(0.0, parent_net) * 0.10)
        parent_reserve += parent_res
        parent_re += parent_net - parent_res - dividend
        parent_cash = opening_parent + own_profit - parent_interest - parent_capital + received - repurchase + parent_draw - parent_repay - dividend
        parent_bridge += parent_draw - parent_repay
        if parent_cash < cfg["parent_cash_floor"] - 1e-9:
            raise ValueError(f"Y{i+1}: parent operating capital cannot be funded")
        repayment = min(max(0.0, required_debt - parent_bridge), max(0.0, cash_before_finance + draw - floor))
        debt = required_debt - repayment
        cash = cash_before_finance + draw - repayment
        residual = opening_cash + profit + financial_income - investment - interest - dividend - repurchase + draw - repayment - cash
        assert abs(residual) < 1e-9
        assert parent_re >= -1e-9 and min(sub_re) >= -sum(cfg["subsidiary_initial_loss_budget"]) - 1e-9
        assert cash >= floor - 1e-9
        rows.append(dict(year=i+1, revenue=revenue, operating_profit=profit, investment=investment,
                         fixed_growth=fixed, working_growth=working, opening_capital_credit_paid=old_pay, paid_prebuilt_credit=cfg["paid_prebuilt_capacity_credit"][i], extra_capital=extra,
                         cash_income=financial_income, interest=interest, group_profit=profit+financial_income-interest,
                         ordinary_distribution=dividend, distribution_per_share=dividend/shares,
                         cash=cash, earmarked_project_cash=project, debt=debt,
                         draw=draw, repayment=repayment, parent_cash=parent_cash, parent_retained_profit=parent_re,
                         upstream_declared=declared, upstream_received=received, dividend_receivable=receivable,
                         parent_capital=parent_capital, sub_retained_profit=list(sub_re), sub_reserve=list(sub_reserve),
                         parent_bridge=parent_bridge, parent_bridge_draw=parent_draw, parent_bridge_repay=parent_repay,
                         cash_conservation_residual=residual))
    return {"shares": shares, "rows": rows, "cash_5": cash, "debt_5": debt,
            "excess_net_cash_5": cash - cfg["operating_cash_floor"] - project - debt,
            "peak_debt": max(r["debt"] for r in rows)}


def value_budget(inp, cfg, endpoints):
    budget = simulate(inp, cfg)
    distributions = [r["distribution_per_share"] for r in budget["rows"]]
    values = {}
    for name, e in endpoints.items():
        tail = operating_value(budget["rows"][-1]["operating_profit"], cfg["tail_profit_growth"],
                               e["incremental_return"], e["equity_cost"], e["terminal_growth"])
        terminal_equity = tail["value"] + budget["excess_net_cash_5"]
        tvps = terminal_equity / budget["shares"]
        distributions_pv = sum(d/(1+e["equity_cost"])**t for t, d in enumerate(distributions, 1))
        terminal_pv = tvps / (1+e["equity_cost"])**5
        values[name] = dict(current=distributions_pv+terminal_pv, year5=tvps,
                            distributions_pv=distributions_pv, terminal_pv=terminal_pv,
                            terminal_pv_fraction=terminal_pv/(terminal_pv+distributions_pv), tail=tail)
    return {"budget": budget, "distributions": distributions, "endpoints": values}


def build(inp):
    cfg = inp["base"]
    base = value_budget(inp, cfg, inp["endpoints"])
    v = {"low": round(base["endpoints"]["low"]["current"], 1), "high": round(base["endpoints"]["high"]["current"], 1), "currency": "CNY"}
    tv = {name: round(base["endpoints"][name]["year5"], 2) for name in ["low", "high"]}
    # Auxiliary immediate steady-state capitalization, sharing economics, omitting the finite high-growth phase.
    f = inp["facts"]
    cash0 = f["q3_cash_equivalents"] + f["q3_financial_assets"] - f["buyback_increment_paid_october"] + f["matched_option_proceeds_upper"] - f["minority_cash_reserve_budget"]
    bridge = cash0 - cfg["operating_cash_floor"] - f["q3_debt_and_leases"] - f["buyback_future_budget"] - sum(cfg["opening_capital_credit_settlement"])
    auxiliary = {}
    for name, e in inp["endpoints"].items():
        mature = operating_value(base["budget"]["rows"][0]["operating_profit"], [], e["incremental_return"], e["equity_cost"], e["terminal_growth"])
        auxiliary[name] = (mature["value"] + bridge) / base["budget"]["shares"]
    scenarios = {}
    variants = {
      "cyclical": {"growth":[0.02,0.08,0.18,0.14,0.10], "after_tax_common_operating_margin":[0.075,0.08,0.095,0.10,0.10], "committed_extra_cash":[0.8,0.4,0,0,0], "dividend_target_per_share":[1.2,1.4,2.1,2.8,3.3]},
      "structural": {"growth":[0.08,0.04,0.02,0.01,0], "after_tax_common_operating_margin":[0.08,0.075,0.07,0.065,0.06], "incremental_fixed_capital_per_revenue":0.80, "committed_extra_cash":[0.4,0.3,0.2,0.1,0.1], "dividend_target_per_share":[1.8,1.7,1.5,1.3,1.2], "tail_profit_growth":[0,0,0,0,0,0,0]},
      "optimistic": {"growth":[0.24,0.20,0.16,0.13,0.10], "after_tax_common_operating_margin":[0.104,0.108,0.11,0.11,0.11], "incremental_fixed_capital_per_revenue":0.45, "dividend_target_per_share":[2.5,3.0,3.5,4.0,4.5], "tail_profit_growth":[0.09,0.08,0.07,0.06,0.05,0.04,0.03]},
      "capital_plus_020": {"incremental_fixed_capital_per_revenue":0.80},
      "capital_plus_020_growth_rescheduled": {"incremental_fixed_capital_per_revenue":0.80,"growth":[0.14,0.12,0.10,0.08,0.07]},
      "upstream_delayed_one_year": {"upstream_lag_years":1},
      "subs_old_losses_05_each": {"subsidiary_initial_loss_budget":[0.5,0.5]},
      "parent_capital_share_030": {"parent_capital_share":0.30},
      "capital_credit_low_08": {"opening_capital_credit_settlement":[0.4,0.4,0,0,0]},
      "capital_credit_high_12": {"opening_capital_credit_settlement":[0.6,0.6,0,0,0]},
      "capital_credit_low_paired_prebuilt": {"opening_capital_credit_settlement":[0.4,0.4,0,0,0],"paid_prebuilt_capacity_credit":[0.2,0.1,0,0,0]},
      "capital_credit_high_paired_prebuilt": {"opening_capital_credit_settlement":[0.6,0.6,0,0,0],"paid_prebuilt_capacity_credit":[0,0,0,0,0]},
      "zero_opening_capital_credit_diagnostic": {"opening_capital_credit_settlement":[0,0,0,0,0]},
      "no_prebuilt_capacity_credit": {"paid_prebuilt_capacity_credit":[0,0,0,0,0]}
    }
    for name, changes in variants.items():
        new = copy.deepcopy(cfg); new.update(changes)
        ends = copy.deepcopy(inp["endpoints"])
        if name == "structural":
            ends = {"low":{"equity_cost":0.115,"terminal_growth":0.01,"incremental_return":0.08}, "high":{"equity_cost":0.105,"terminal_growth":0.01,"incremental_return":0.09}}
        if name == "capital_plus_020_growth_rescheduled":
            ends["low"]["incremental_return"]=0.10
            ends["high"]["incremental_return"]=0.13
        try:
            s = value_budget(inp,new,ends)
            scenarios[name] = {"changes":changes,"current":{k:v["current"] for k,v in s["endpoints"].items()},
                               "distributions":s["distributions"],"peak_debt":s["budget"]["peak_debt"],
                               "cash_5":s["budget"]["cash_5"],"debt_5":s["budget"]["debt_5"],"feasible":True}
        except ValueError as e:
            scenarios[name] = {"changes":changes,"feasible":False,"reason":str(e)}
    valuation_note = "核心为五年实际可付分配加Y5独立经营价值；Y5后7年利润增长从7%递减到2.5%，新增利润以12%—15%回报支付资本，再进入2%—2.5%稳态，股权成本10.5%/9.5%。首五年收入18%/15%/12%/10%/8%增长、税后普通股经营率9.8%—10.1%，增收资本率80%，首两年抵扣1.5亿元已付款预建能力；Q3资本性结算余额预算10亿元（范围8—12亿元）分两年偿付，另支付海外机器人投入。辅助为立即稳态利润资本化，单列资金并清偿Q3存量资本信用。基准不依赖机器人规模成功。"
    return_note = "五项为母公司现金与法定利润约束后实际预算现金，非集团FCF；惠州/江苏未来利润依法提储后最多45%宣派到账，母公司自身利润及直接资本同步预算。Y5价值来自Y5经营状态后的七年衰减及稳态现金，扣期末借款，仅加已扣五年分配后的额外金融资金；运营备用金及保证金归经营资本，不再全额加回。完全稀释股数286448468股，对截止前可能行权未单列登记60126股与6337881.66元认款配对；激励回购不缩分母，不计持有人分配。"
    return {"schema":"trading_os_research_result_v1","symbol":inp["symbol"],"report_period":inp["report_period"],
            "information_cutoff":inp["information_cutoff"],"value_range":v,"valuation_note":valuation_note,
            "return_model":{"schema_version":1,"method":"annual_common_equity_irr_v1","currency":"CNY",
                            "model_as_of":inp["information_cutoff"],"base_case_distributions_per_share":base["distributions"],
                            "base_case_terminal_equity_value_range_per_share":{"year_5":tv}},
            "return_model_note":return_note,"details":{"base":base,"auxiliary":auxiliary,"scenarios":scenarios,"capital_bridge":capital_bridge(inp)}}


def tests():
    # The exact operating valuation function used in the adopted tail: 100 cash forever at 10%.
    z = operating_value(100, [0,0], 0.20, 0.10, 0)
    assert abs(z["value"] - 1000) < 1e-9
    # 5% growth, 20% incremental ROIC: cash 105-5/.2=80; subsequent growth perpetuity is 1600.
    z = operating_value(100, [], 0.20, 0.10, 0.05)
    assert abs(z["value"] - 1600) < 1e-9
    inp = json.loads((HERE/"2026-Q3-inputs.json").read_text(encoding="utf-8"))
    out = build(inp)
    b = out["details"]["base"]["budget"]
    assert len(b["rows"]) == 5
    assert all(abs(r["cash_conservation_residual"]) < 1e-9 for r in b["rows"])
    assert all(r["parent_cash"] >= inp["base"]["parent_cash_floor"] - 1e-9 for r in b["rows"])
    assert out["return_model"]["base_case_terminal_equity_value_range_per_share"]["year_5"]["low"] != out["value_range"]["low"]
    bridge=capital_bridge(inp)
    assert sum(inp["base"]["opening_capital_credit_settlement"]) == inp["facts"]["capital_credit_q3_budget"]
    assert bridge["paid_capacity_credit_adopted"] <= bridge["paid_capacity_bound_central"]
    assert bridge["capital_credit_q3_bridge_range"][0] < bridge["capital_credit_q3_adopted"] < bridge["capital_credit_q3_bridge_range"][1]
    return {"tests_passed":["same_function_zero_growth_1000","same_function_growth_reinvestment_1600","five_periods","group_cash_conservation","parent_cash_profit_constraints","separate_current_and_Y5","capital_credit_bridge","paid_prebuilt_credit_bound"]}


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    parser=argparse.ArgumentParser();parser.add_argument("--details",action="store_true");parser.add_argument("--test",action="store_true")
    args=parser.parse_args()
    inp=json.loads((HERE/"2026-Q3-inputs.json").read_text(encoding="utf-8"))
    out=tests() if args.test else build(inp)
    if not args.test: out.update({'information_cutoff': '2026-11-06T23:59:59+08:00', 'valuation_note': '核心为五年实际可付分配加Y5独立经营价值；Y5后7年利润增长从7%递减到2.5%，新增利润以12%—15%回报支付资本，再进入2%—2.5%稳态，股权成本10.5%/9.5%。首五年收入18%/15%/12%/10%/8%增长、税后普通股经营率9.8%—10.1%，增收资本率80%，首两年抵扣1.5亿元已付款预建能力；Q3资本性结算余额预算10亿元（范围8—12亿元）分两年偿付，另支付海外机器人投入。辅助为立即稳态利润资本化，单列资金并清偿Q3存量资本信用。基准不依赖机器人规模成功。', 'return_model_note': '五项为母公司现金与法定利润约束后实际预算现金，非集团FCF；惠州/江苏未来利润依法提储后最多45%宣派到账，母公司自身利润及直接资本同步预算。Y5价值来自Y5经营状态后的七年衰减及稳态现金，扣期末借款，仅加已扣五年分配后的额外金融资金；运营备用金及保证金归经营资本，不再全额加回。完全稀释股数286448468股，对截止前可能行权未单列登记60126股与6337881.66元认款配对；激励回购不缩分母，不计持有人分配。'})
    if not args.test and not args.details: out.pop("details")
    print(json.dumps(out,ensure_ascii=False,indent=2))
