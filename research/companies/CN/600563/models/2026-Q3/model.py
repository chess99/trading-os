#!/usr/bin/env python3
"""CN:600563 source-first owner-value model. Standard library only.
Ordinary offline computation; no external permission ticket.
Writes only a new --output directory. No network, subprocess, canonical writes,
source changes, archive, Library, candidate acceptance or price/IRR calculation.
Monetary calculations: CNY billion; source facts retain original CNY precision.
"""
from __future__ import annotations
import copy
import csv
import hashlib
import json
import math
import traceback
from pathlib import Path

BILLION = 1_000_000_000.0
TOL = 1e-8


def near(a, b, label, tol=TOL):
    if not math.isclose(a, b, rel_tol=tol, abs_tol=tol):
        raise AssertionError(f"{label}: {a!r} != {b!r}")


def b(value):
    return value / BILLION


def discount_operating(flows, terminal_next_flow, cost, growth, valuation_year=0):
    """The SAME finite + perpetual operating valuation used in all scenarios/tests.
    flows contain years 1..10, terminal_next_flow belongs to year 11.
    valuation_year=5 independently discounts years 6..10 and terminal at year 10.
    """
    if cost <= growth:
        raise ValueError("Capital cost must exceed stable nominal growth")
    n = len(flows)
    explicit = sum(cf / (1 + cost) ** (i + 1 - valuation_year)
                   for i, cf in enumerate(flows) if i + 1 > valuation_year)
    terminal = terminal_next_flow / (cost - growth) / (1 + cost) ** (n - valuation_year)
    return {"explicit_pv": explicit, "terminal_pv": terminal,
            "operating_value": explicit + terminal,
            "terminal_fraction": terminal / (explicit + terminal) if explicit + terminal else None}


def advance_cash(begin, prebuffer_cash, finance_income, interest, debt_repayment,
                 prior_financial_tax_paid, dividend):
    """Total interest-bearing financial PRINCIPAL, including operating cash.
    prebuffer_cash has NOT deducted the increase in necessary operating cash.
    Paying prior tax simultaneously reduces its liability outside this function.
    """
    return (begin + prebuffer_cash + finance_income - interest - debt_repayment
            - prior_financial_tax_paid - dividend)


def physical_maintenance(stock, a, fixed_other_maintenance):
    residual = 1 - a["residual"]
    return (stock[0] * residual / a["life_buildings"]
            + stock[1] * residual / a["life_machines"]
            + stock[2] * residual / a["life_other"] + fixed_other_maintenance)


def nwc_of(facts, capital_ap):
    return b(sum(facts["working_assets"].values())
             - sum(facts["working_liabilities"].values())) + capital_ap


def core_operating_ebit(facts, assumptions):
    """Source bridge excludes finance/investment/FV and neutralizes FX.
    Ordinary loss and operating grants normalized independently of annual gains.
    Normal source EBIT is not yet the forward economic-maintenance adjustment.
    """
    revenue = b(facts["revenue"])
    cost = b(sum(facts[k] for k in ("cogs", "surcharges", "selling", "admin", "rd")))
    raw_pre_other = revenue - cost
    observed_loss = b(facts["credit_impairment_signed"] + facts["asset_impairment_signed"])
    observed_other = b(facts["other_income"])
    return {
        "revenue": revenue,
        "operating_cost_ex_finance": cost,
        "ebit_before_other_and_impairment": raw_pre_other,
        "reported_other_income": observed_other,
        "reported_credit_and_asset_losses_signed": observed_loss,
        "reported_operating_ebit_ex_finance_investment_fv": raw_pre_other + observed_other + observed_loss,
        "normal_loss": revenue * assumptions["normal_loss_ratio"],
        "normal_operating_grants": revenue * assumptions["normal_recurring_grant_ratio"],
        "normal_ebit": raw_pre_other - revenue * assumptions["normal_loss_ratio"]
                       + revenue * assumptions["normal_recurring_grant_ratio"]
    }


def initial_state(data, a):
    f = data["facts_yuan"]
    q, h = f["nine_months_2026"], f["h1_2026"]
    revenue0 = b(f["fy2025"]["revenue"] + q["revenue"] - f["nine_months_2025"]["revenue"])
    net0 = b(f["fy2025"]["parent_net_income"] + q["parent_net_income"]
             - f["nine_months_2025"]["parent_net_income"])
    cd = b(h["long_cd_carrying"]) + a["long_cd_classification_delta"]
    equity_investments = b(h["trading_equity_assets"])
    capital_ap = b(h["capital_payables"]) + a["capital_ap_opening_delta"]
    # The Q3 residual is NOT claimed to be confirmed capital prepayment.
    op_noncurrent_residual = b(q["other_noncurrent_assets"]) - cd
    if min(cd, op_noncurrent_residual, capital_ap) < 0:
        raise ValueError("Impossible opening financial/capital classification")
    operating_long = b(sum(q["operating_long_assets"].values())) + op_noncurrent_residual
    nwc = nwc_of(q, capital_ap)
    debt_financial = b(q["cash"] + q["trading_financial"] + q["short_financial"]) + cd - equity_investments
    foreign_funds = b(h["group_cash"] - h["mother_cash"]
                      + h["group_short_financial"] - h["mother_short_financial"])
    financial_tax = b(h["financial_fv_dtl"] + h["cd_interest_dtl"])
    operating_tax_timing = b(q["net_dtl"]) - financial_tax
    gross = h["gross_fixed_assets"]
    stock = [b(gross[k]) for k in ("buildings", "machines", "other")]
    other_maintenance = (
        b(gross["vehicles"]) * (1 - a["residual"]) / a["life_vehicles"]
        + b(gross["solar"]) * (1 - a["residual"]) / a["life_solar"]
        + 2 * b(sum(h["other_half_year_amortization"]))
    )
    return {
        "revenue": revenue0, "ttm_parent_profit": net0, "nwc": nwc,
        "capital_ap": capital_ap, "operating_long_economic": operating_long,
        "operating_long_book_reference": operating_long,
        "operating_cash": a["operating_cash_initial"],
        "capital_funded": operating_long + nwc + a["operating_cash_initial"] - capital_ap,
        "capital_gross": operating_long + nwc + a["operating_cash_initial"],
        "debt_financial": debt_financial, "equity_financial_book": equity_investments,
        "affiliate": b(q["affiliate"]), "financial_debt": b(q["financial_debt"]),
        "foreign_financial": foreign_funds,
        "parent_financial": debt_financial - foreign_funds,
        "parent_retained_profit": b(h["mother_retained_earnings"]),
        "financial_tax_remaining": financial_tax, "operating_tax_timing": operating_tax_timing,
        "long_cd": cd, "short_financial": b(q["short_financial"]),
        "trading_debt_financial": b(q["trading_financial"]) - equity_investments,
        "physical_stock": stock, "other_maintenance": other_maintenance,
        "initial_maintenance": physical_maintenance(stock, a, other_maintenance),
        "classification_note": "Q3总额/H1分类延续；长期CD、权益投资、资本AP均非Q3分项事实",
        "unclassified_noncurrent_in_operating_capital": op_noncurrent_residual - b(h["capital_prepay"])
    }


def month_number(s):
    y, m = map(int, s.split("-"))
    return y * 12 + m - 1


def cd_release_weights(data, mode):
    """Banks disclose month RANGES, not monthly holdings. Uniform is a budget.
    Late mode uses each range's latest month. No long CD matures in year 1.
    Carrying-value interest is released with principal, not earned a second time.
    """
    h = data["facts_yuan"]["h1_2026"]
    amounts = [0.0] * 12
    total = sum(row["principal"] for row in h["cd_principal_maturities"])
    for row in h["cd_principal_maturities"]:
        first, last = month_number(row["first"]), month_number(row["last"])
        months = [last] if mode == "late" else list(range(first, last + 1))
        for month in months:
            # Year 1 covers month numbers Nov-2026 through Oct-2027.
            year = (month - month_number("2026-11")) // 12 + 1
            if not 1 <= year <= 11:
                raise ValueError("CD maturity outside documented modeled buckets")
            amounts[year] += row["principal"] / len(months) / total
    near(sum(amounts), 1, "CD principal weights")
    near(amounts[1], 0, "No long CD released in first model year")
    return amounts


def scenario_definitions(base):
    """Only the seven authorized targeted paths (five here plus two holder paths).
    No old-policy stress result is imported or reused as a current-policy result.
    """
    def scenario(name, description, updates):
        a = copy.deepcopy(base)
        a.update(updates)
        return {"name": name, "description": description, "assumptions": a}
    return [
        scenario("base", "核心中间；增销资金逐年足额，零未证实闲置设备/厂房信用", {}),
        scenario("core_low", "核心较低端：原增长/利润/寿命/a不变，仅适用足额资本政策", {
            "growth_first_ten": [.08,.07,.06,.05,.04,.04,.035,.03,.025,.025],
            "life_machines": 9, "life_other": 7, "sales_capital_coefficient": 1.15,
            "cost_of_capital": .10, "equity_investment_recovery": .70,
            "premaintenance_margin": [x-.005 for x in base["premaintenance_margin"]]}),
        scenario("core_high", "核心较高端：原增长/利润/寿命/a不变，仅适用足额资本政策", {
            "growth_first_ten": [.10,.09,.08,.07,.06,.05,.045,.04,.03,.025],
            "life_other": 9, "sales_capital_coefficient": 1.00,
            "cost_of_capital": .09, "equity_investment_recovery": 1.0,
            "premaintenance_margin": [x+.005 for x in base["premaintenance_margin"]]}),
        scenario("shorter_lives", "设备8年/其他6年；同修正后基准收入及新增物理能力，额外维护现金不挤出增能", {
            "life_machines": 8, "life_other": 6}),
        scenario("structural_weak", "原永久竞争侵蚀假设不变；同一足额资本约束，不保旧估值", {
            "growth_first_ten": [0,.01,.02,.02,.02,.02,.015,.015,.01,.01],
            "growth_terminal": .01,
            "premaintenance_margin": [.268,.258,.258,.258,.258,.258,.258,.258,.258,.258],
            "sales_capital_coefficient": 1.40, "life_machines": 8, "life_other": 6,
            "nwc_ratio": .27, "cash_capex_ratio_after2": .095,
            "overseas_capex_first_five": [.06,.08,.08,.02,0],
            "foreign_profit_share": [0,0,0,.02,.03,.03,.03,.03,.03,.03,.03],
            "payout": [.30]*11})
    ]


def solve_capital_connection(physical_m_begin, steady_maintenance, half_rate,
                             weight, planned_budget, target_long_cash, delta_ap,
                             scheduled_overseas, minimum_new_capacity=0.0):
    """Analytic max of funded-growth, planned-spending and physical constraints.
    M=B+k*N; C=M+N-dAP. Y1-5: C=max(planned budget, M+required long cash,
    M+overseas-dAP, M-dAP, M+fixed-minimum-N-dAP). Later only the former
    planned-spending branch fades; required sales capital NEVER fades with w.
    The old branch's unique N-root is retained, then max'd against full needs.
    No trial search, future margin-based capital cut, unproved capacity credit,
    duplicated overseas expenditure, or hidden external funding.
    """
    if not 0 <= weight <= 1 or half_rate < 0 or minimum_new_capacity < 0:
        raise ValueError("Invalid capital-connection inputs")
    constant_m = (1-weight)*physical_m_begin + weight*steady_maintenance
    slope_m = (1-weight)*half_rate
    planned_root = ((1-weight)*(planned_budget-constant_m)
                    + weight*target_long_cash + delta_ap) / (1+(1-weight)*slope_m)
    sales_required_physical = target_long_cash + delta_ap
    new_capacity = max(0.0, planned_root, sales_required_physical,
                       scheduled_overseas, minimum_new_capacity)
    maintenance = constant_m + slope_m*new_capacity
    capex = maintenance + new_capacity - delta_ap
    required_cash = maintenance + target_long_cash
    planned_branch_cash = (1-weight)*planned_budget + weight*required_cash
    binding = []
    for name, value in (("nonnegative_capacity", 0.0), ("planned_spending", planned_root),
                        ("sales_required", sales_required_physical),
                        ("scheduled_overseas", scheduled_overseas),
                        ("corrected_base_capacity", minimum_new_capacity)):
        if math.isclose(new_capacity, value, rel_tol=TOL, abs_tol=TOL):
            binding.append(name)
    return {"maintenance":maintenance, "cash_capex":capex,
            "new_capacity":new_capacity, "planned_branch_root_capacity":planned_root,
            "sales_required_physical_capacity":sales_required_physical,
            "required_cash_capex_for_sales":required_cash,
            "planned_branch_cash_at_actual_maintenance":planned_branch_cash,
            "cash_above_planned_branch":capex-planned_branch_cash,
            "minimum_same_sales_capacity_from_corrected_base":minimum_new_capacity,
            "binding_constraints":binding}


def simulate(data, definition, fixed_first_five_dividends=None, trace=None,
             fixed_minimum_new_capacity=None):
    trace = trace if trace is not None else {}
    trace.update({"case": definition["name"], "stage": "opening", "year": None})
    a = definition["assumptions"]
    if fixed_minimum_new_capacity is not None and len(fixed_minimum_new_capacity) != 11:
        raise ValueError("Same-capacity stress needs all eleven corrected-base years")
    s = initial_state(data, a)
    opening = copy.deepcopy(s)
    revenue = [s["revenue"]]
    for growth in a["growth_first_ten"] + [a["growth_terminal"], a["growth_terminal"]]:
        revenue.append(revenue[-1] * (1 + growth))
    cash_ratio = a["operating_cash_initial"] / revenue[0]
    g = a["growth_terminal"]
    # New CAPACITY includes equipment acquired on capital-AP credit.
    # This is a replacement-cost budget coefficient, not observed net book value.
    long_capacity_coefficient = (a["sales_capital_coefficient"]
        - (a["nwc_ratio"] + cash_ratio - a["capital_ap_ratio"]) / (1 + g))
    weighted_replacement_rate = sum(
        weight * (1 - a["residual"]) / life
        for weight, life in zip(a["new_capacity_mix"],
                               (a["life_buildings"], a["life_machines"], a["life_other"])))
    terminal_maintenance_ratio = long_capacity_coefficient * weighted_replacement_rate
    weights = cd_release_weights(data, a["cd_maturity_mode"])
    rows, warnings = [], []
    issues, distribution_adjustments, legal_deficits = [], [], []
    trace["completed_year_rows"] = rows
    prior_parent_profit_proxy = s["ttm_parent_profit"] * a["dividend1_profit_proxy_factor"]
    op_tax_remaining = s["operating_tax_timing"]
    cd_remaining = s["long_cd"]
    h = data["facts_yuan"]["h1_2026"]
    for t in range(1, 12):
        begin = copy.deepcopy(s)
        r = revenue[t]
        trace.update({"stage": "year_capital", "year": t, "revenue": r,
                      "opening_funded_capital": begin["capital_funded"],
                      "opening_parent_financial": begin["parent_financial"]})
        margin = a["premaintenance_margin"][min(t-1,9)] + a["ebit_margin_diagnostic_delta"]
        nwc = r * a["nwc_ratio"]
        cash = r * cash_ratio
        ap = r * a["capital_ap_ratio"]
        dnwc, dc, dap = nwc-begin["nwc"], cash-begin["operating_cash"], ap-begin["capital_ap"]
        physical_m_begin = physical_maintenance(begin["physical_stock"], a, begin["other_maintenance"])
        target_investment = a["sales_capital_coefficient"] * max(0, revenue[t+1]-r)
        target_long_cash = target_investment - dnwc - dc
        if t == 1:
            budget, w = a["cash_capex_year1"] + a["extra_capex_year1"], 0.0
        elif t == 2:
            budget, w = a["cash_capex_year2"], 0.0
        elif t <= 5:
            budget, w = r * a["cash_capex_ratio_after2"], 0.0
        elif t <= 10:
            budget, w = r * a["cash_capex_ratio_after2"], a["maintenance_transition_weights"][t-6]
        else:
            budget, w = r * a["cash_capex_ratio_after2"], 1.0
        overseas = a["overseas_capex_first_five"][t-1] if t <= 5 else 0.0
        minimum_capacity = fixed_minimum_new_capacity[t-1] if fixed_minimum_new_capacity is not None else 0.0
        half_rate = .5 * weighted_replacement_rate
        capital_connection = solve_capital_connection(
            physical_m_begin, terminal_maintenance_ratio*r, half_rate, w,
            budget, target_long_cash, dap, overseas, minimum_capacity)
        maintenance = capital_connection["maintenance"]
        capex = capital_connection["cash_capex"]
        new_capacity = capital_connection["new_capacity"]
        physical_m = physical_m_begin + half_rate*new_capacity
        trace.update({"cash_capex": capex, "maintenance": maintenance,
                      "new_physical_capacity": new_capacity, "delta_capital_ap": dap,
                      "maintenance_physical_path": physical_m,
                      "maintenance_steady_path": terminal_maintenance_ratio*r,
                      "transition_weight": w, "capital_connection":capital_connection,
                      "sales_driven_target_investment":target_investment})
        near(maintenance, (1-w)*physical_m + w*terminal_maintenance_ratio*r, f"M blend {t}")
        if capex < 0 or maintenance < 0 or new_capacity < -TOL:
            warnings.append(f"Y{t}: 预算/维护导致负新增能力，路径需经济重估，未隐式补融资或floor")
            issues.append({"case":definition["name"],"year":t,"code":"physical_capacity_not_closed",
                           "cash_capex":capex,"maintenance":maintenance,
                           "new_physical_capacity":new_capacity,"delta_capital_ap":dap,
                           "gap":max(0,-capex,-maintenance,-new_capacity),
                           "reason":"未建模收缩/处置或额外资金，不能据负新增能力维持既定收入"})
        domestic_new_capacity = new_capacity - overseas if t <= 5 else new_capacity
        if t <= 5 and domestic_new_capacity < -TOL:
            warnings.append(f"Y{t}: 已有总capex无法覆盖维护/海外/资本AP桥，不能称路径已通过")
            issues.append({"case":definition["name"],"year":t,"code":"scheduled_overseas_capital_unfunded",
                           "new_physical_capacity":new_capacity,"scheduled_overseas":overseas,
                           "cash_capex":capex,"maintenance":maintenance,
                           "capital_ap_begin":begin["capital_ap"],"capital_ap_end":ap,
                           "gap":-domestic_new_capacity,
                           "reason":"总预算未覆盖既定海外建设与国内能力；没有替代经营路径"})
        # Physical stock contains assets financed by both cash and capital AP.
        stock = [old + mix*new_capacity for old, mix in zip(begin["physical_stock"], a["new_capacity_mix"])]
        economic_ebit = margin*r-maintenance
        book_da = a["book_da_display_ratio"]*r
        book_ebit_reference = margin*r-book_da
        cash_tax = a["tax"] * max(book_ebit_reference if a["stricter_cash_tax"] else economic_ebit, 0)
        nopat = economic_ebit-cash_tax
        normal_statutory_profit_proxy = book_ebit_reference-a["tax"]*max(book_ebit_reference, 0)
        if a["operating_dtl_release_years"]:
            additional_tax = min(op_tax_remaining, opening["operating_tax_timing"]/a["operating_dtl_release_years"])
        else:
            additional_tax = 0.0
        op_tax_remaining -= additional_tax
        net_investment = capex-maintenance+dnwc+dc
        sales_capital_coverage = net_investment-target_investment
        if sales_capital_coverage < -TOL:
            issues.append({"case":definition["name"],"year":t,"code":"sales_capital_unfunded",
                           "target_investment":target_investment,"actual_net_investment":net_investment,
                           "gap":-sales_capital_coverage,
                           "reason":"未证明闲置能力，不得以维护过渡权重打折增销必需资金"})
        physical_required = max(0, target_long_cash+dap, overseas, minimum_capacity)
        if new_capacity < physical_required-TOL:
            issues.append({"case":definition["name"],"year":t,"code":"required_capacity_unfunded",
                           "physical_required":physical_required,"actual_capacity":new_capacity,
                           "gap":physical_required-new_capacity})
        near(capex, max(capital_connection["planned_branch_cash_at_actual_maintenance"],
                        maintenance+target_long_cash, maintenance+overseas-dap,
                        maintenance-dap, maintenance+minimum_capacity-dap),
             f"full capital-connection max {t}")
        fcff = nopat-net_investment-additional_tax
        prebuffer_cash = fcff+dc
        economic_long = begin["operating_long_economic"]+capex+dap-maintenance
        book_long = begin["operating_long_book_reference"]+capex+dap-book_da
        funded_capital = economic_long+nwc+cash-ap
        gross_capital = economic_long+nwc+cash
        trace.update({"stage":"year_economic_cash", "net_investment":net_investment,
                      "fcff":fcff,"prebuffer_cash":prebuffer_cash,"funded_capital":funded_capital,
                      "economic_long":economic_long,"book_long":book_long,
                      "delta_nwc":dnwc,"delta_operating_cash":dc})
        near(funded_capital-begin["capital_funded"], net_investment, f"economic funded capital {t}")
        # Economic consumption adjustment is explicit; no hidden impairment cash.
        near(book_long-economic_long,
             begin["operating_long_book_reference"]-begin["operating_long_economic"]+maintenance-book_da,
             f"book/economic bridge {t}")
        cd_release = opening["long_cd"]*weights[t]
        cd_remaining -= cd_release
        old_cd_tax_paid = b(h["cd_interest_dtl"])*weights[t]
        financial_tax_remaining = begin["financial_tax_remaining"]-old_cd_tax_paid
        financial_debt_repaid = begin["financial_debt"] if t == 1 else 0.0
        interest = begin["financial_debt"]*a["debt_interest_rate"]*(.5 if t == 1 else 1)
        foreign_profit = max(nopat, 0)*a["foreign_profit_share"][t-1]
        foreign_before_injection = begin["foreign_financial"]+foreign_profit-overseas
        injection = max(0, a["overseas_financial_minimum"]-foreign_before_injection)
        foreign_end = foreign_before_injection+injection
        payout = a["payout"][t-1]
        planned_dividend = payout*max(prior_parent_profit_proxy, 0)
        if fixed_first_five_dividends is not None and t <= 5:
            # Holder endpoints use the SAME five cash distributions as the
            # contract, rather than adding low/high cash under different D paths.
            planned_dividend = fixed_first_five_dividends[t-1]
        parent_prebuffer_before_finance = prebuffer_cash-foreign_profit+overseas-injection
        # Conservative balance rule: planned dividend stops earning immediately;
        # current operating inflow earns for half a year. If D is cut, no extra
        # same-year yield is invented; retained money earns from the next year.
        earning_base = max(0, begin["debt_financial"]-begin["operating_cash"]
                           -begin["foreign_financial"]-planned_dividend
                           +.5*parent_prebuffer_before_finance)
        finance_income = earning_base*a["finance_yield"]*(1-a["finance_tax"])
        parent_statutory = normal_statutory_profit_proxy-foreign_profit+finance_income-interest
        parent_economic = nopat-foreign_profit+finance_income-interest
        parent_legal_before = begin["parent_retained_profit"]+parent_statutory
        before_dividend = advance_cash(begin["debt_financial"], prebuffer_cash,
                                      finance_income, interest, financial_debt_repaid, old_cd_tax_paid, 0)
        locked_trading = opening["trading_debt_financial"]*a["locked_trading_fraction_year1"] if t == 1 else 0.0
        # Short financial assets are assumed released inside Y1, not before cutoff.
        # All long-CD liability buckets are removed from available parental cash.
        parent_cash_before = before_dividend-foreign_end
        parent_required_cash = max(0, cash-a["overseas_financial_minimum"])
        parent_payment_before = parent_cash_before-cd_remaining-locked_trading-financial_tax_remaining
        dividend_capacity = max(0, min(parent_legal_before, parent_payment_before-parent_required_cash))
        dividend = min(planned_dividend, dividend_capacity)
        if dividend < planned_dividend-TOL:
            warnings.append(f"Y{t}: 分红因母公司利润/流动资金约束从{planned_dividend:.6f}降至{dividend:.6f}")
            distribution_adjustments.append({"case":definition["name"],"year":t,
                                             "planned":planned_dividend,"actual":dividend,
                                             "parent_legal_before":parent_legal_before,
                                             "parent_payment_before":parent_payment_before,
                                             "parent_required_cash":parent_required_cash})
            if fixed_first_five_dividends is not None and t <= 5:
                issues.append({"case":definition["name"],"year":t,"code":"fixed_holder_distribution_unpayable",
                               "required_dividend":planned_dividend,"actual_dividend":dividend,
                               "gap":planned_dividend-dividend,
                               "reason":"同D端点付不出已指定的中间路径现金，不能另改D继续称同D"})
        debt_financial_end = advance_cash(begin["debt_financial"], prebuffer_cash, finance_income,
                                          interest, financial_debt_repaid, old_cd_tax_paid, dividend)
        parent_financial_end = debt_financial_end-foreign_end
        parent_retained = parent_legal_before-dividend
        parent_payment_end = parent_payment_before-dividend
        parent_independent_roll = (begin["parent_financial"]+parent_prebuffer_before_finance
                                  +finance_income-interest-financial_debt_repaid-old_cd_tax_paid-dividend)
        trace.update({"stage":"year_parent_cash", "parent_financial_end":parent_financial_end,
                      "parent_independent_roll":parent_independent_roll,
                      "parent_payment_end":parent_payment_end,"parent_required_cash":parent_required_cash,
                      "parent_legal_before":parent_legal_before,"parent_retained_end":parent_retained,
                      "dividend_planned":planned_dividend,"dividend_actual":dividend,
                      "foreign_financial_end":foreign_end,"parent_injection":injection,
                      "debt_financial_end":debt_financial_end})
        near(parent_independent_roll, parent_financial_end, f"parent/group/internal injection {t}")
        if parent_payment_end < parent_required_cash-TOL:
            warnings.append(f"Y{t}: 降低分配后母公司仍缺必要经营现金，资金路径未闭合")
            issues.append({"case":definition["name"],"year":t,"code":"parent_cash_gap_after_distribution_cut",
                           "parent_payment_cash_end":parent_payment_end,"required_cash":parent_required_cash,
                           "dividend_actual":dividend,"parent_financial_end":parent_financial_end,
                           "gap":parent_required_cash-parent_payment_end,
                           "reason":"实际付款资金缺口未有显式融资或经营收缩方案"})
        if dividend > max(parent_legal_before,0)+TOL:
            issues.append({"case":definition["name"],"year":t,"code":"dividend_exceeds_legal_profit_proxy",
                           "dividend":dividend,"parent_legal_before":parent_legal_before,
                           "gap":dividend-max(parent_legal_before,0)})
        if parent_retained < -TOL:
            # Retained loss alone is not bankruptcy: no dividend, later profits
            # can repair it. Cash shortage is tested independently above.
            legal_deficits.append({"case":definition["name"],"year":t,
                                   "retained_loss":-parent_retained,"dividend_actual":dividend,
                                   "reason":"累计法定利润代理为负，停止分红并结转弥补；单独不判资金破产"})
        s.update({"revenue": r, "nwc": nwc, "operating_cash": cash, "capital_ap": ap,
                  "operating_long_economic": economic_long, "operating_long_book_reference": book_long,
                  "capital_funded": funded_capital, "capital_gross": gross_capital,
                  "debt_financial": debt_financial_end, "foreign_financial": foreign_end,
                  "parent_financial": parent_financial_end, "parent_retained_profit": parent_retained,
                  "financial_tax_remaining": financial_tax_remaining,
                  "financial_debt": begin["financial_debt"]-financial_debt_repaid,
                  "physical_stock": stock})
        row = {
            "year": t, "revenue": r, "premaintenance_margin": margin, "maintenance": maintenance,
            "maintenance_physical_path": physical_m, "maintenance_steady_path": terminal_maintenance_ratio*r,
            "transition_weight": w, "economic_ebit": economic_ebit, "economic_ebit_margin": economic_ebit/r,
            "book_da_reference": book_da, "cash_tax": cash_tax, "nopat": nopat,
            "additional_operating_tax": additional_tax, "operating_tax_timing_remaining": op_tax_remaining,
            "cash_capex": capex, "capex_budget_before_transition": budget,
            "old_capital_ap_paid": begin["capital_ap"], "new_capital_ap_credit": ap,
            "delta_capital_ap": dap, "new_physical_capacity": new_capacity,
            "overseas_capex_inside_total": overseas, "domestic_new_capacity": domestic_new_capacity,
            "nwc": nwc, "delta_nwc": dnwc, "operating_cash": cash, "delta_operating_cash": dc,
            "sales_driven_target_investment": target_investment, "net_investment": net_investment,
            "sales_capital_coverage_excess": sales_capital_coverage,
            "required_new_physical_capacity": physical_required,
            "sales_required_physical_capacity": capital_connection["sales_required_physical_capacity"],
            "required_cash_capex_for_sales": capital_connection["required_cash_capex_for_sales"],
            "planned_branch_cash_at_actual_maintenance": capital_connection["planned_branch_cash_at_actual_maintenance"],
            "cash_above_planned_branch": capital_connection["cash_above_planned_branch"],
            "minimum_capacity_from_corrected_base": minimum_capacity,
            "capital_binding_constraints": capital_connection["binding_constraints"],
            "unproved_spare_machine_credit": 0.0, "domestic_building_reuse_credit": 0.0,
            "reinvestment_rate": net_investment/nopat if nopat else None,
            "capital_funded": funded_capital, "capital_gross": gross_capital,
            "operating_long_economic": economic_long, "operating_long_book_reference": book_long,
            "book_to_economic_consumption_difference": book_long-economic_long,
            "noncash_disposal_adjustment": 0.0,
            "mature_roic_funded": nopat/((begin["capital_funded"]+funded_capital)/2),
            "mature_roic_gross": nopat/((begin["capital_gross"]+gross_capital)/2),
            "fcff": fcff, "prebuffer_cash": prebuffer_cash, "finance_income": finance_income,
            "finance_earning_base": earning_base, "interest": interest,
            "financial_debt_repaid": financial_debt_repaid, "financial_debt_end": s["financial_debt"],
            "cd_release": cd_release, "cd_remaining": cd_remaining,
            "short_financial_released": opening["short_financial"] if t == 1 else 0.0,
            "locked_trading": locked_trading, "financial_tax_paid": old_cd_tax_paid,
            "financial_tax_remaining": financial_tax_remaining,
            "debt_financial_begin": begin["debt_financial"], "debt_financial_end": debt_financial_end,
            "foreign_financial_begin": begin["foreign_financial"], "foreign_profit_retained": foreign_profit,
            "parent_injection": injection, "foreign_financial_end": foreign_end,
            "parent_financial_begin": begin["parent_financial"], "parent_financial_end": parent_financial_end,
            "parent_cash_generation_before_finance": parent_prebuffer_before_finance,
            "parent_statutory_profit_proxy": parent_statutory, "parent_economic_profit_proxy": parent_economic,
            "parent_retained_profit_begin": begin["parent_retained_profit"], "parent_retained_profit_end": parent_retained,
            "statutory_reserve_accrual": 0.0, "discretionary_reserve_accrual": 0.0,
            "parent_payment_cash_end": parent_payment_end, "parent_required_cash": parent_required_cash,
            "dividend_planned": planned_dividend, "dividend": dividend,
            "dividend_per_share": dividend*BILLION/data["identity"]["shares"],
            "economic_parent_profit_for_next_dividend": max(0, min(parent_statutory,parent_economic)),
            "equity_investment_recovery": opening["equity_financial_book"]*a["equity_investment_recovery"]
        }
        rows.append(row)
        prior_parent_profit_proxy = row["economic_parent_profit_for_next_dividend"]
    for i, row in enumerate(rows):
        if i < len(rows)-1:
            next_row = rows[i+1]
            delta_profit = next_row["nopat"]-row["nopat"]
            row["forward_incremental_roic"] = delta_profit/row["net_investment"] if row["net_investment"] > TOL else None
            # Pure decomposition: new sales at next margin plus old-sales margin change.
            old_margin = row["nopat"]/row["revenue"]
            new_margin = next_row["nopat"]/next_row["revenue"]
            row["next_profit_from_new_sales"] = (next_row["revenue"]-row["revenue"])*new_margin
            row["next_profit_erosion_existing_sales"] = row["revenue"]*(new_margin-old_margin)
            trace.update({"stage":"profit_decomposition","year":row["year"],
                          "delta_profit":delta_profit,"new_sales_profit":row["next_profit_from_new_sales"],
                          "old_sales_profit_erosion":row["next_profit_erosion_existing_sales"]})
            near(delta_profit, row["next_profit_from_new_sales"]+row["next_profit_erosion_existing_sales"], "profit decomposition")
        if i:
            delta_k = row["capital_funded"]-rows[i-1]["capital_funded"]
            row["same_period_incremental_roic"] = (row["nopat"]-rows[i-1]["nopat"])/delta_k if delta_k > TOL else None
    terminal_roic = (rows[10]["nopat"]/rows[10]["revenue"])/a["sales_capital_coefficient"]
    trace.update({"stage":"terminal_and_valuation", "year":10,
                  "terminal_ronic":terminal_roic,"year10_investment":rows[9]["net_investment"],
                  "year11_investment":rows[10]["net_investment"],"terminal_fcff":rows[10]["fcff"]})
    near(rows[9]["net_investment"], a["sales_capital_coefficient"]*rows[9]["revenue"]*g, "Y10 stable investment")
    trace["year"] = 11
    near(rows[10]["net_investment"], a["sales_capital_coefficient"]*rows[10]["revenue"]*g, "Y11 stable investment")
    if rows[10]["nopat"] > 0:
        near(rows[10]["nopat"]*g/terminal_roic, rows[10]["net_investment"], "terminal RONIC identity is outcome")
    flows = [row["fcff"] for row in rows[:10]]
    current = discount_operating(flows, rows[10]["fcff"], a["cost_of_capital"], g)
    future5 = discount_operating(flows, rows[10]["fcff"], a["cost_of_capital"], g, 5)
    equity_value = opening["equity_financial_book"]*a["equity_investment_recovery"]
    initial_assets = (opening["debt_financial"]+equity_value+opening["affiliate"]
                      -opening["operating_cash"]-opening["financial_debt"]-opening["financial_tax_remaining"])
    row5 = rows[4]
    assets5 = (row5["debt_financial_end"]+equity_value+opening["affiliate"]
               -row5["operating_cash"]-row5["financial_debt_end"]-row5["financial_tax_remaining"])
    normal_ebit0 = revenue[0]*(a["premaintenance_margin"][0]+a["ebit_margin_diagnostic_delta"])-opening["initial_maintenance"]
    aux_profit = normal_ebit0-a["tax"]*max(normal_ebit0,0)
    aux_operating = aux_profit/a["cost_of_capital"]
    shares = data["identity"]["shares"]
    p = lambda value: value*BILLION/shares
    feasibility = {"admissible":not issues,
                   "status":"unclosed" if issues else ("feasible_with_dividend_cut" if distribution_adjustments else "feasible"),
                   "issues":issues,"distribution_adjustments":distribution_adjustments,
                   "nonfatal_retained_profit_deficits":legal_deficits,
                   "scope":"Y1-11 full sales-capital, planned payments, physical additions, parent cash and distributions; R0-to-Y1 installed-capacity assumption remains unproved; not independent acceptance"}
    return {
        "name": definition["name"], "description": definition["description"], "assumptions": a,
        "capital_policy":"full_funded_sales_required_max_planned_v4",
        "opening_production_scope":"R0-to-Y1 revenue requires already-installed production and demand; future capex only backs Y1-to-Y2 onward, not retrospective proof of Y1 capacity",
        "opening": opening, "rows": rows, "warnings": warnings,"feasibility":feasibility,
        "diagnostic_value_note":"以下为原始算术诊断；未闭合路径不得进入可采纳核心/五年合同",
        "cd_release_weights": weights, "long_capacity_funding_per_incremental_sales": long_capacity_coefficient,
        "terminal_maintenance_ratio": terminal_maintenance_ratio, "terminal_realized_ronic": terminal_roic,
        "diagnostic_valuation_current": {**current, "nonoperating_net_asset_bridge": initial_assets,
                              "common_equity_value": current["operating_value"]+initial_assets,
                              "per_share": p(current["operating_value"]+initial_assets)},
        "diagnostic_valuation_year5": {**future5, "post_distribution_net_asset_bridge": assets5,
                            "common_equity_value": future5["operating_value"]+assets5,
                            "per_share": p(future5["operating_value"]+assets5)},
        "diagnostic_auxiliary_no_growth": {"normal_economic_nopat": aux_profit, "operating_value": aux_operating,
                                "per_share": p(aux_operating+initial_assets),
                                "difference_from_primary_fraction": (aux_operating-current["operating_value"])/current["operating_value"]},
        "five_distributions_per_share": [row["dividend_per_share"] for row in rows[:5]],
        "transition_5_6": {key: [rows[4][key],rows[5][key]] for key in
                           ("revenue","maintenance","cash_capex","net_investment","fcff","dividend","operating_cash","debt_financial_end")},
        "transition_10_11": {key: [rows[9][key],rows[10][key]] for key in
                             ("revenue","maintenance","cash_capex","net_investment","fcff","economic_ebit_margin")},
        "y1_to_y5_incremental_roic": (rows[4]["nopat"]-rows[0]["nopat"])/(rows[4]["capital_funded"]-rows[0]["capital_funded"])
            if rows[4]["capital_funded"]-rows[0]["capital_funded"] > TOL else None
    }


def factual_outputs(data):
    facts, a = data["facts_yuan"], data["assumptions"]
    bridge = {}
    for key in ("fy2024","fy2025","nine_months_2025","nine_months_2026"):
        bridge[key] = core_operating_ebit(facts[key],a)
        if "depreciation_components" in facts[key]:
            bridge[key]["reported_da"] = b(sum(facts[key]["depreciation_components"]))
            bridge[key]["normalized_premaintenance_margin_from_source"] = (
                bridge[key]["normal_ebit"]+bridge[key]["reported_da"])/bridge[key]["revenue"]
    ttm = {key: facts["fy2025"][key]+facts["nine_months_2026"][key]-facts["nine_months_2025"][key]
           for key in ("revenue","cogs","surcharges","selling","admin","rd","other_income",
                       "credit_impairment_signed","asset_impairment_signed")}
    bridge["ttm"] = core_operating_ebit(ttm,a)
    k = {}
    r0 = bridge["ttm"]["revenue"]
    for key in ("fy2024","fy2025"):
        f = facts[key]
        ap = b(f["capital_payables"])
        nwc = nwc_of(f,ap)
        op_long = b(sum(f["operating_long_assets"].values()))
        cash = a["operating_cash_initial"]*b(f["revenue"])/r0
        k[key] = {"nwc": nwc, "operating_long": op_long, "capital_ap": ap,
                  "operating_cash_budget_for_comparability": cash,
                  "capital_gross": nwc+op_long+cash, "capital_funded": nwc+op_long+cash-ap}
    annual_nopat25 = bridge["fy2025"]["normal_ebit"]*(1-a["tax"])
    annual_nopat24 = bridge["fy2024"]["normal_ebit"]*(1-a["tax"])
    bridge["mature_roic_2025_reported_scope"] = annual_nopat25/((k["fy2024"]["capital_funded"]+k["fy2025"]["capital_funded"])/2)
    dk = k["fy2025"]["capital_funded"]-k["fy2024"]["capital_funded"]
    bridge["incremental_roic_2024_to_2025_reported_scope"] = (annual_nopat25-annual_nopat24)/dk if dk>TOL else None
    bridge["historical_scope_caveat"] = "2025-10上海美星出表；未完全统一范围，历史回报只作诊断，不认证新增项目回报"
    bridge["capital_reconstruction"] = k
    bridge["quarters_2026"] = {
        "q1_revenue": b(facts["q1_2026"]["revenue"]),
        "q2_revenue": b(facts["h1_2026"]["revenue"]-facts["q1_2026"]["revenue"]),
        "q3_revenue": b(facts["nine_months_2026"]["single_q3_revenue"]),
        "q1_net": b(facts["q1_2026"]["parent_net_income"]),
        "q2_net": b(facts["h1_2026"]["parent_net_income"]-facts["q1_2026"]["parent_net_income"]),
        "q3_net": b(facts["nine_months_2026"]["single_q3_net_income"])
    }
    return bridge


def same_function_tests():
    v = discount_operating([100.0]*10,100.0,.10,0)
    near(v["operating_value"],1000,"official valuation function: zero growth cash annuity")
    y5 = discount_operating([100.0]*10,100.0,.10,0,5)
    near(y5["operating_value"],1000,"official valuation function: independent year5")
    end = advance_cash(100,20,4,0,0,0,6)
    near(end,118,"official total cash roll, retained cash not zero or double distribution")
    return {"zero_growth_value": v["operating_value"], "year5_zero_growth_value": y5["operating_value"],
            "cash_100_plus20_plus4_minus6": end}


def synthetic_capital_connection_tests():
    """Four small solver checks; no company assumptions, no new company paths.
    Executed only within the coordinator's eventual exact once attempt.
    """
    specs = [
        ("sales_floor", .30, .40, .05, 0.0, .35, .40, .02, .08, 0.0),
        ("planned_budget_floor", .30, .40, .05, 0.0, .90, .20, .02, .08, 0.0),
        ("overseas_not_double_added", .30, .40, .05, .4, .35, .05, .01, .20, 0.0),
        ("corrected_base_capacity_floor", .45, .55, .07, .2, .50, .15, .01, .08, .40)]
    rows = []
    for label, mb, ms, h, w, budget, required, dap, overseas, fixed in specs:
        result = solve_capital_connection(mb,ms,h,w,budget,required,dap,overseas,fixed)
        m,c,n = result["maintenance"],result["cash_capex"],result["new_capacity"]
        near(m,(1-w)*(mb+h*n)+w*ms,"synthetic maintenance equation")
        near(c-m+dap,n,"synthetic AP physical equation")
        near(c,max((1-w)*budget+w*(m+required),m+required,m+overseas-dap,m-dap,m+fixed-dap),
             "synthetic max constraints")
        if n+TOL < max(0,required+dap,overseas,fixed):
            raise AssertionError("Synthetic capital floor violation: "+label)
        rows.append({"label":label,"scope":"synthetic solver case not company forecast",**result})
    return rows


def output_markdown(results, contract, facts):
    base = results["base"]
    lines = ["# 模型诊断输出（非正式候选）", "", "单位：人民币十亿元；每股项目为元。",
             "以下算术值可以来自未闭合路径；仅明确通过可行性门槛的必要路径才进入末尾临时合同。", "",
             "| 路径 | 可行性 | 算术当前每股值 | 算术第5年每股值 | 终态经营利润率 | 实际增量回报 | 终值现值占比 |",
             "|---|---|---:|---:|---:|---:|---:|"]
    for key, r in results.items():
        lines.append(f'| {key} | {r["feasibility"]["status"]} | {r["diagnostic_valuation_current"]["per_share"]:.4f} | {r["diagnostic_valuation_year5"]["per_share"]:.4f} | {r["rows"][10]["economic_ebit_margin"]:.2%} | {r["terminal_realized_ronic"]:.2%} | {r["diagnostic_valuation_current"]["terminal_fraction"]:.2%} |')
    lines += ["", "## 五年分配与资金", "", "| 年 | 收入 | 维护 | 总capex | 净增长资金 | FCFF | 实际D/股 | 母公司可付现金 | 常备要求 |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for row in base["rows"][:6]:
        lines.append(f'| {row["year"]} | {row["revenue"]:.5f} | {row["maintenance"]:.5f} | {row["cash_capex"]:.5f} | {row["net_investment"]:.5f} | {row["fcff"]:.5f} | {row["dividend_per_share"]:.5f} | {row["parent_payment_cash_end"]:.5f} | {row["parent_required_cash"]:.5f} |')
    lines += ["", "## 警示", ""]
    for key,r in results.items():
        for warning in r["warnings"]:
            lines.append(f"- {key}: {warning}")
    if not any(r["warnings"] for r in results.values()):
        lines.append("未触发脚本内预算/付款警示；不替代原表复核和独立复算。")
    lines += ["", "## 主辅方法", f'正常经营现金无增长辅助每股值：{base["diagnostic_auxiliary_no_growth"]["per_share"]:.5f}；主辅经营价值差：{base["diagnostic_auxiliary_no_growth"]["difference_from_primary_fraction"]:.2%}。',
              "", "## 五年合同（未写入正式研究）", "```json", json.dumps(contract,ensure_ascii=False,indent=2), "```", ""]
    return "\n".join(lines)


def write_json_once(path, value):
    with path.open("x", encoding="utf-8") as fh:
        json.dump(value, fh, ensure_ascii=False, indent=2, allow_nan=False)
        fh.write("\n")


def build_contract(data, results):
    """Economic failures gate only contracts that REQUIRE those paths.
    This deliberately does not require all non-core stresses to be feasible.
    Pure program failure never calls this function and retains a nonzero exit.
    """
    current_required = ("base","core_low","core_high")
    holder_required = ("base","holder_low","holder_high")
    current_failures = [{"case":name,"issues":results[name]["feasibility"]["issues"]}
                        for name in current_required if not results[name]["feasibility"]["admissible"]]
    holder_failures = [{"case":name,"issues":results[name]["feasibility"]["issues"]}
                       for name in holder_required if not results[name]["feasibility"]["admissible"]]
    low, high = results["core_low"],results["core_high"]
    hl, hh = results["holder_low"],results["holder_high"]
    low_value, high_value = low["diagnostic_valuation_current"]["per_share"],high["diagnostic_valuation_current"]["per_share"]
    low5, high5 = hl["diagnostic_valuation_year5"]["per_share"],hh["diagnostic_valuation_year5"]["per_share"]
    if low_value > high_value:
        current_failures.append({"code":"endpoint_order_unresolved","low":low_value,"high":high_value,
                                 "reason":"不静默排序以掩盖经济端点倒置"})
    if low5 > high5:
        holder_failures.append({"code":"holder_endpoint_order_unresolved","low":low5,"high":high5})
    distributions = results["base"]["five_distributions_per_share"]
    if len(distributions) != 5:
        raise AssertionError("Five-year distribution interface length")
    value_range = None if current_failures else {"low":low_value,"high":high_value,"currency":"CNY"}
    holder_contract = None if holder_failures else {
        "schema_version":1,"method":"annual_common_equity_irr_v1","currency":"CNY",
        "model_as_of":data["identity"]["information_cutoff"],
        "base_case_distributions_per_share":distributions,
        "base_case_terminal_equity_value_range_per_share":{"year_5":{"low":low5,"high":high5}}}
    return {
        "information_cutoff":data["identity"]["information_cutoff"],
        "value_range":value_range,"return_model":holder_contract,
        "valuation_note": "核心必要路径未闭合，数值核心区间不可用；详见失败原因。" if current_failures
            else "核心必要路径通过脚本经济可行性门槛；仍是待独立复算的工作底稿，非正式研究接收。",
        "return_model_note": "基准或同D终值必要路径未闭合，五年接口不可用；未改D或隐藏资金缺口。" if holder_failures
            else "五年D及两条同D端点重新滚动普通股资金，股份2.25亿；终值来自Y5之后经营与派息后资产，非当前价值复制。仍待独立复算。",
        "availability":{"current_required_cases":list(current_required),"holder_required_cases":list(holder_required),
                        "current_failures":current_failures,"holder_failures":holder_failures},
        "status":"provisional_contract_not_formal_candidate" if not current_failures and not holder_failures
                 else "contract_fields_unavailable_or_partial_see_reasons",
        "base_case_current_value_per_share":results["base"]["diagnostic_valuation_current"]["per_share"]
            if results["base"]["feasibility"]["admissible"] else None}


def synthetic_gate_tests(data):
    """Tiny counterfactual interface tests, NOT additional company scenarios.
    These exercise the exact contract gate and do not assert that any actual
    source-based path has failed or passed. Records preserve each injected issue.
    """
    names = ("base","core_low","core_high","holder_low","holder_high","noncore_stress")
    fixture = {}
    for name in names:
        value = 80 if name in ("core_low","holder_low") else 100
        fixture[name] = {"feasibility":{"admissible":True,"status":"feasible","issues":[]},
                         "diagnostic_valuation_current":{"per_share":value},
                         "diagnostic_valuation_year5":{"per_share":value+20},
                         "five_distributions_per_share":[1,1,1,1,1]}
    outcomes = []
    specifications = [
        ("noncore_failure_not_global_null","noncore_stress",False,True,True),
        ("base_funding_failure_blocks_both","base",False,False,False),
        ("holder_fixed_D_failure_only_blocks_holder","holder_low",False,True,False),
        ("legal_D_cut_and_negative_RE_alone_not_null","base",True,True,True)]
    for label,name,admissible,want_value,want_holder in specifications:
        cases = copy.deepcopy(fixture)
        cases[name]["feasibility"] = {
            "admissible":admissible,
            "status":"feasible_with_dividend_cut" if admissible else "unclosed",
            "issues":[] if admissible else [{"code":"synthetic_counterexample","case":name,"year":1,"gap":.1}],
            "nonfatal_retained_profit_deficits":[{"retained_loss":.1,"dividend_actual":0}] if admissible else []}
        contract = build_contract(data,cases)
        actual = (contract["value_range"] is not None,contract["return_model"] is not None)
        if actual != (want_value,want_holder):
            raise AssertionError(f"Contract gate counterexample {label}: {actual}")
        outcomes.append({"label":label,"injected_feasibility":cases[name]["feasibility"],
                         "value_available":actual[0],"holder_available":actual[1]})
    return outcomes
