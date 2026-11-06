"""600085 source-first operating-FCFE value plus owned financial claims; dated payout diagnostic. Standard library; no work on import.
All monetary values RMB million; no quote/market-price input or IRR.
Selected boundary: parent own + A*tech(core + tech*CM) + A_direct*CM + A-owned residual.
"""
from copy import deepcopy
from datetime import date
import math

NODES = ("parent", "tech", "cm", "residual")

class PolicyBufferBreach(Exception):
    """A positive-cash proxy/policy buffer breach; not demonstrated cash insolvency."""
    def __init__(self, message, partial):
        super().__init__(message)
        self.partial = partial


class EconomicInfeasible(Exception):
    """A genuine operating/funding constraint, not a programming-error bucket."""
    def __init__(self, message, partial):
        super().__init__(message)
        self.partial = partial


def require(condition, message):
    if not condition:
        raise ValueError(message)


def close(a, b, label, tol=1e-7):
    if not math.isclose(a, b, rel_tol=tol, abs_tol=tol):
        raise ArithmeticError(f"{label}: {a!r} != {b!r}")


def validate(data):
    def finite_tree(value):
        if isinstance(value,float): require(math.isfinite(value), "nonfinite input")
        elif isinstance(value,dict):
            for item in value.values(): finite_tree(item)
        elif isinstance(value,list):
            for item in value: finite_tree(item)
    finite_tree(data)
    require(data["schema"] == "tongrentang-source-first-v2", "unsupported input schema")
    if "deterministic_fixture" in data:
        require(data["symbol"]=="FIXTURE", "fixture initialization is not permitted for a company input")
    a = data["assumptions"]
    require(a["months"] == 120, "this version requires 120 monthly periods")
    require(data["cutoff"] == "2026-10-31", "unsupported cutoff; do not silently shift periods")
    require(0 <= a["terminal_growth"] < min(a["discount_rates"]), "invalid tail growth/discount")
    require(a["terminal_incremental_roic"] > a["terminal_growth"], "invalid reinvestment ROIC")
    for weights in (a["q3_cash_delta_allocation"], a["restricted_cash_allocation"], a["ap_allocation"]):
        close(sum(weights.values()), 1.0, "allocation weights")
    for key in NODES:
        node = a["nodes"][key]
        require(len(node["growth_years"]) == 10, f"{key}: growth vector must cover ten years")
        require(all(-0.8 < x < 0.5 for x in node["growth_years"]), "invalid growth")
        require(0 <= node["tax_rate"] < 1, "invalid tax")
    require(len({s["id"] for s in data["scenarios"]}) == len(data["scenarios"]), "duplicate scenario")
    return True


def scenario_assumptions(data, scenario):
    a = deepcopy(data["assumptions"])
    override = scenario["overrides"]
    for key, val in override.items():
        if key in a:
            a[key] = deepcopy(val)
        elif key not in ("growth_shift", "gross_margin_shift", "inventory_target_multiplier", "domestic_tax_rate", "residual_target_gross_margin", "residual_fixed_cost_inflation"):
            raise ValueError(f"unknown scenario key: {key}")
    for name, n in a["nodes"].items():
        n["growth_years"] = [x + override.get("growth_shift", 0) * max(0, (6-i)/6)
                             for i, x in enumerate(n["growth_years"])]
        n["target_gross_margin"] += override.get("gross_margin_shift", 0)
        n["inventory_target_cogs_years"] *= override.get("inventory_target_multiplier", 1)
        if name in ("parent", "tech") and "domestic_tax_rate" in override:
            n["tax_rate"] = override["domestic_tax_rate"]
        if name=="residual":
            n["target_gross_margin"]=override.get("residual_target_gross_margin",n["target_gross_margin"])
            n["fixed_cost_inflation"]=override.get("residual_fixed_cost_inflation",n["fixed_cost_inflation"])
    for key in ("h1_transit_settled_by_q3", "q3_current_loan_fraction", "cm_legacy_remaining_at_cutoff",
                "project_q3_capex_fraction", "tech_commitment_overlap_fraction"):
        require(0 <= a[key] <= 1, f"{key} outside [0,1]")
    require(all(0 <= f <= 1 for f in a["cm_legacy_recovery_fraction"]), "invalid legacy recoveries")
    require(all(0 < f <= 1 for f in a["owner_cash_fraction"].values()), "invalid cash attribution")
    return a


def month_date(t):
    """t=1 is November 2026; t=60 is October 2031. No implicit Q4 replay."""
    serial = 2026 * 12 + 10 + (t - 1)
    return serial // 12, serial % 12 + 1


def normalize_anchors(data, a):
    r = data["raw"]
    own = r["ownership"]
    fx = r["fx"]["cm_owner_ni_rmb_m"] / r["fx"]["cm_owner_ni_hkd_m"]
    cm = r["cm"]
    parent = r["parent"]
    tech = r["tech"]
    # These NI anchors are already attributable to the respective share class.
    ni = {
        "parent": parent["h1_ni"] - parent["h1_sub_dividend_income"],
        "tech": tech["h1_owner_ni"] - own["tech_cm"] * r["fx"]["cm_owner_ni_rmb_m"],
        "cm": r["fx"]["cm_owner_ni_rmb_m"],
    }
    ni["residual"] = r["h1_group"]["parent_ni"] - ni["parent"] - own["a_tech"] * tech["h1_owner_ni"] - own["a_cm_direct"] * ni["cm"]
    close(ni["parent"] + own["a_tech"] * (ni["tech"] + own["tech_cm"] * ni["cm"])
          + own["a_cm_direct"] * ni["cm"] + ni["residual"], r["h1_group"]["parent_ni"], "H1 owner NI bridge")
    observed_cm_owner_fraction = cm["h1_owner_ni_hkd_m"] / cm["h1_group_ni_hkd_m"]
    fin_income = {
        "parent": parent["h1_interest_income"] + parent["h1_financial_gain"],
        "tech": tech["h1_core_interest_income"] * a["tech_cost_exposure_fraction"],
        "cm": cm["h1_interest_income_hkd_m"] * fx * observed_cm_owner_fraction,
        "residual": max(0.0, r["h1_group"]["interest_income"] - parent["h1_interest_income"]
                         - (tech["h1_core_interest_income"] + tech["h1_cm_interest_income"])) * a["owner_cash_fraction"]["residual"],
    }
    interest = {"parent": parent["h1_interest_expense"],
                "tech": tech["h1_core_interest_expense"] * a["tech_cost_exposure_fraction"],
                "cm": cm["h1_lease_interest_hkd_m"] * fx * observed_cm_owner_fraction,
                "residual": a["residual_h1_interest_expense_proxy"]}
    credit_gain = {"parent":-parent["h1_credit_loss"],
                   "tech":tech["h1_core_net_credit_gain"]*a["tech_cost_exposure_fraction"],
                   "cm":0.0,
                   "residual":-(r["h1_group"]["credit_loss"]-parent["h1_credit_loss"]+tech["h1_group_net_credit_gain"])*a["owner_cash_fraction"]["residual"]}
    credit_gain["cm"] = cm["h1_net_credit_reversal_hkd_m"] * fx * observed_cm_owner_fraction
    revenue = {"parent": parent["h1_revenue"] * 2,
               "tech": (tech["h1_revenue"] - tech["h1_cm_segment_revenue"]) * 2,
               "cm": cm["h1_revenue_hkd_m"] * fx * 2,
               "residual": r["commercial"]["h1_revenue"] * 2 * r["commercial"]["a_direct_ownership"] * a["commercial_store_owner_fraction"]}
    scale = {"parent": 1.0, "tech": a["tech_cost_exposure_fraction"],
             "cm": a["cm_cost_exposure_fraction"], "residual": 1.0}
    gm = {"parent": 1 - parent["h1_cogs"] / parent["h1_revenue"],
          "tech": (tech["h1_gross_profit"] - cm["h1_gross_profit_hkd_m"] * fx) /
                   (tech["h1_revenue"] - tech["h1_cm_segment_revenue"]),
          "cm": cm["h1_gross_profit_hkd_m"] / cm["h1_revenue_hkd_m"], "residual": r["commercial"]["h1_industry_gross_margin"]}
    anchors = {}
    for k in NODES:
        n = a["nodes"][k]
        # Reconstruct an owner-level EBIT proxy, explicitly replacing ROU + lease-interest
        # with cash lease cost. Historical component tax uses base tax, not scenario tax.
        base_tax = data["assumptions"]["nodes"][k]["tax_rate"]
        norm_ni = ni[k] - (fin_income[k] + credit_gain[k]) * (1 - base_tax)
        ebit = norm_ni * 2 / (1 - base_tax) + interest[k] * 2 + n["lease_rou_da_annual"] - n["lease_cash_annual"]
        nonrent_cost = revenue[k] * gm[k] * scale[k] - ebit - n["lease_cash_annual"]
        require(nonrent_cost >= 0, f"{k}: negative implied non-rent cost")
        anchors[k] = {"h1_owner_ni": ni[k], "removed_h1_financial_income": fin_income[k],
                      "removed_h1_credit_reversal": credit_gain[k], "normalized_h1_owner_ni": norm_ni,
                      "reference_annual_revenue": revenue[k], "reference_gross_margin": gm[k],
                      "cost_scale": scale[k], "reference_nonrent_cost": nonrent_cost,
                      "reference_postrent_ebit": ebit}
    return anchors


def opening_state(data, a):
    r = data["raw"]; h = r["h1_group"]; q = r["q3_group"]
    p = r["parent"]; tech = r["tech"]; cm = r["cm"]; own = r["ownership"]
    fx = r["fx"]["h1_closing_rmb_per_hkd"]
    f = {"parent": 1.0, **a["owner_cash_fraction"]}
    cm_cash = cm["cash_hkd_m"] * fx
    raw_h1 = {"parent": p["cash"] + p["financial_assets"],
              "tech": tech["cash_equivalents"] + tech["term_deposit"] - cm_cash,
              "cm": cm_cash}
    raw_h1["residual"] = h["cash"] + h["financial_assets"] - sum(raw_h1.values())
    require(min(raw_h1.values()) >= 0, "negative raw financial residual")
    cash = {k: raw_h1[k] * f[k] for k in NODES}
    paid = tech["fy25_dividend_paid_aug2026"]
    settled = a["h1_transit_settled_by_q3"]
    # Fully owner-level declared dividends: do not multiply these by a cash-proxy fraction.
    known_moves = {"parent": paid * own["a_tech"] + settled * p["transit_dividend"],
                   "tech": -paid + settled * tech["transit_dividend"], "cm": 0.0, "residual": 0.0}
    observed_delta = q["cash"] + q["financial_assets"] - h["cash"] - h["financial_assets"]
    unexplained = observed_delta - sum(known_moves.values())
    for k in NODES:
        cash[k] += known_moves[k] + unexplained * a["q3_cash_delta_allocation"].get(k, 0) * f[k]
        cash[k] += a["unobserved_october_cash_change"] * a["q3_cash_delta_allocation"].get(k, 0) * f[k]
    close(sum(raw_h1.values()) + sum(known_moves.values()) + unexplained,
          q["cash"] + q["financial_assets"], "September gross financial control")
    restricted = {k: h["restricted_cash"] * a["restricted_cash_allocation"][k] * f[k] for k in NODES}
    # Current non-current liability includes leases. Source does not provide Sept split.
    q3_debt = q["short_debt"] + q["long_debt"] + q["current_noncurrent_total"] * a["q3_current_loan_fraction"] + h["minority_loans"]
    h1_debt = h["short_debt"] + h["long_debt_total"] + h["minority_loans"]
    cm_debt = cm["debt_hkd_m"] * fx
    residual_debt = h1_debt - p["debt"] - tech["debt"]
    require(residual_debt >= 0, "negative debt residual")
    debt = {"parent": p["debt"], "tech": (tech["debt"] - cm_debt) * f["tech"],
            "cm": cm_debt * f["cm"], "residual": residual_debt * f["residual"]}
    for k in ("tech", "residual"):
        debt[k] += (q3_debt - h1_debt) * (0.90 if k == "tech" else 0.10) * f[k]
    require(min(debt.values()) >= 0, "debt bridge produced negative principal")
    raw_inv = {"parent": p["inventory"], "cm": cm["inventory_hkd_m"] * fx,
               "tech": tech["inventory"] - cm["inventory_hkd_m"] * fx}
    raw_inv["residual"] = h["inventory"] - sum(raw_inv.values())
    for k in NODES:
        raw_inv[k] += (q["inventory"] - h["inventory"]) * a["q3_cash_delta_allocation"].get(k, 0)
    close(sum(raw_inv.values()), q["inventory"], "September inventory control")
    legacy_net_raw = cm["ar_net_hkd_m"] * fx * a["cm_legacy_remaining_at_cutoff"]
    other_ar = q["ar"] - p["ar"] - legacy_net_raw
    require(other_ar >= 0, "CM legacy allocation exceeds consolidated AR")
    raw_ar = {"parent": p["ar"], "cm": 0.0,
              "tech": other_ar * a["other_ar_allocation_tech"],
              "residual": other_ar * (1-a["other_ar_allocation_tech"])}
    close(sum(raw_ar.values()) + legacy_net_raw, q["ar"], "September AR allocation control")
    states = {}
    for k in NODES:
        states[k] = {"cash": cash[k], "debt": debt[k], "debt_initial": debt[k],
                     "restricted": restricted[k], "inventory": raw_inv[k] * f[k],
                     "ordinary_ar": raw_ar[k] * f[k],
                     "ap": q["ap"] * a["ap_allocation"][k] * f[k],
                     "payable_dividend": 0.0, "receivable_dividend": 0.0,
                     "initial_inventory": raw_inv[k] * f[k], "initial_ar": raw_ar[k] * f[k],
                     "initial_ap": q["ap"] * a["ap_allocation"][k] * f[k],
                     "legacy_net": legacy_net_raw * f[k] if k == "cm" else 0.0,
                     "re": p["re"] + a["unobserved_october_re_change"] if k == "parent" else 0.0,
                     "statutory_reserve": p["statutory_reserve"] if k == "parent" else 0.0,
                     "legal_credit": 0.0, "cost_index":1.0, "normal_annual": {}, "profit_year": {}}
    # Any uncollected H1 declared dividends are explicit receivables, not new profit.
    initial_events = []
    for k, amount in (("parent", p["transit_dividend"]), ("tech", tech["transit_dividend"])):
        left = amount * (1-settled)
        if left:
            states[k]["receivable_dividend"] += left
            initial_events.append({"type":"receipt", "at":3, "node":k,"amount":left,"source":"H1 transit; already recognized"})
    legacy = []
    for i, gross in enumerate(cm["ar_aging_hkd_m"]):
        gross_rmb = gross * fx * a["cm_legacy_remaining_at_cutoff"] * f["cm"]
        book_net = gross_rmb * (1-cm["ar_allowance_hkd_m"]/cm["ar_gross_hkd_m"])
        expected = gross_rmb * a["cm_legacy_recovery_fraction"][i]
        legacy.append({"cohort":i,"gross":gross_rmb,"opening_net":book_net,"expected_cash":expected,
                       "remaining_expected":expected,"collection_months":a["cm_legacy_collection_months"][i],
                       "delay":a["cm_legacy_extra_delay_months"],"net_adjustment":expected-book_net})
    controls = {"h1_financial_gross":sum(raw_h1.values()), "known_h1_to_q3_cash_moves":known_moves,
                "q3_financial_gross_observed":q["cash"]+q["financial_assets"],
                "unallocated_h1_to_q3_cash_change_before_proxy_allocation":unexplained,
                "unobserved_october_cash_proxy":a["unobserved_october_cash_change"],
                "q3_gross_debt_proxy":q3_debt,"q3_current_loan_fraction_proxy":a["q3_current_loan_fraction"],
                "q3_inventory_gross_control":sum(raw_inv.values()),
                "q3_ar_gross_control":sum(raw_ar.values())+legacy_net_raw,
                "owner_cash_fractions_are_proxies_not_profit_ratios":f,
                "cm_legacy_expected_cash":sum(x["expected_cash"] for x in legacy),
                "cm_legacy_opening_net":sum(x["opening_net"] for x in legacy),
                "cm_legacy_new_net_loss_or_release":sum(x["net_adjustment"] for x in legacy),
                "October_is_not_in_future_stub":True}
    return states, legacy, initial_events, controls


def project_plan(data, a):
    rows = []
    total_h1_remaining=sum(p["budget"]*(1-p["cumulative_spend_fraction"]) for p in data["raw"]["projects"])
    already_spent_proxy=(data["raw"]["q3_group"]["capex_ytd"]-data["raw"]["h1_group"]["capex"])*a["project_q3_capex_fraction"]+a["project_october_spend_proxy"]
    require(0 <= already_spent_proxy <= total_h1_remaining, "invalid pre-cutoff project spend proxy")
    for p in data["raw"]["projects"]:
        # Latest budget less cumulative spend; Q3 cash already observed is not paid twice.
        h1_remaining=p["budget"]*(1-p["cumulative_spend_fraction"])
        pre_cutoff_spend=already_spent_proxy*h1_remaining/total_h1_remaining
        remaining = h1_remaining-pre_cutoff_spend
        rows.append({**p, "remaining_at_h1":p["budget"]*(1-p["cumulative_spend_fraction"]),
                     "pre_cutoff_additional_spend_proxy":pre_cutoff_spend, "cash_remaining_proxy_at_cutoff":remaining*p["future_owner_share"]})
    signed = data["raw"]["tech"]["capital_commitment"]
    overlap = a["tech_commitment_overlap_fraction"] * signed
    lab_remaining = next(x["cash_remaining_proxy_at_cutoff"] for x in rows if x["id"]=="tech_lab")
    require(overlap <= lab_remaining + 1e-8, "assumed overlap exceeds remaining tech lab budget")
    incremental = signed-overlap
    rows.append({"id":"tech_signed_incremental_only","node":"tech","months":24,
                 "cash_remaining_proxy_at_cutoff":incremental,"signed_total":signed,"overlap_with_lab":overlap})
    return rows


def smooth_weight(fraction):
    x=min(1.0,max(0.0,fraction))
    return x*x*(3-2*x)


def budget_month(k, st, anchor, n, a, t, last_sales, legacy):
    year = min(9, (t-1)//12)
    growth = n["growth_years"][year]
    sales_annual = last_sales * (1+growth)**(1/12)
    ratio = sales_annual/anchor["reference_annual_revenue"]
    gm = anchor["reference_gross_margin"] + (n["target_gross_margin"]-anchor["reference_gross_margin"])*min(1,t/60)
    scale = anchor["cost_scale"]
    sales = sales_annual/12
    cogs_annual = sales_annual*(1-gm)*scale
    gross = sales*gm*scale
    var = anchor["reference_nonrent_cost"]*n["variable_opex_share"]*ratio/12
    fade=min(1.0,max(0.0,(t-60)/60))
    inflation=n["fixed_cost_inflation"]*(1-fade)+a["terminal_growth"]*fade
    st["cost_index"] *= (1+inflation)**(1/12)
    fixed = anchor["reference_nonrent_cost"]*(1-n["variable_opex_share"])*st["cost_index"]/12
    rent_annual = n["lease_cash_annual"]*st["cost_index"]
    closure_cost=a["structural_retail_exit_cost"]/24 if k=="residual" and t<=24 else 0.0
    ebit = gross-var-fixed-rent_annual/12-closure_cost
    # Continuous normal credit cost distinct from the opening legacy book.
    credit_cost = sales*scale*(a["normal_credit_cost_fraction_cm"] if k=="cm" else a["normal_credit_cost_fraction_other"])
    ebit -= credit_cost
    if "fixture_ebit_by_month" in n:
        ebit=n["fixture_ebit_by_month"].get(str(t),0.0)
    debt_interest = st["debt"]*a["loan_rate"]/12
    tax = max(0.0, (ebit-debt_interest)*n["tax_rate"])
    core_ni = ebit-debt_interest-tax
    nonlease_da = n["nonlease_da_annual"]*max(a["nonlease_da_sales_floor"],ratio)/12
    maintenance = n["maintenance_annual"]*st["cost_index"]/12
    fixed_growth_capex = max(0.0, sales_annual-last_sales)*n["growth_fixed_capital_per_sales"]*scale
    # No one-off release at year 5. Targets transition continuously from opening stocks.
    target_inv = cogs_annual*n["inventory_target_cogs_years"]
    w = smooth_weight(t/n["inventory_transition_months"])
    inventory = st["initial_inventory"]*(1-w)+target_inv*w
    finished = None
    if k=="cm":
        # Explicit raw/WIP and finished-goods cohorts; total-decline != finished sell-through.
        initial_fg = a["_cm_initial_finished_owner"]
        target_fg = cogs_annual*n["finished_goods_target_cogs_years"]
        wf = smooth_weight(t/a["cm_finished_goods_months_to_target"])
        finished = initial_fg*(1-wf)+target_fg*wf
        initial_other = st["initial_inventory"]-initial_fg
        other_target = max(0.0,target_inv-target_fg)
        inventory = initial_other*(1-w)+other_target*w+finished
    target_ar = sales_annual*scale*n["ar_days"]/365
    ar_weight = smooth_weight(t/12)
    ordinary_ar = st["initial_ar"]*(1-ar_weight)+target_ar*ar_weight
    target_ap = cogs_annual*n["payable_cogs_years"]
    ap = st["initial_ap"]*(1-ar_weight)+target_ap*ar_weight
    delta_nwc = inventory-st["inventory"] + ordinary_ar-st["ordinary_ar"] - (ap-st["ap"])
    legacy_receipts = 0.0
    legacy_non_cash_adjustment = 0.0
    if k=="cm":
        if t==1:
            legacy_non_cash_adjustment = sum(c["net_adjustment"] for c in legacy)
            st["legacy_net"] += legacy_non_cash_adjustment
        for c in legacy:
            if c["delay"] < t <= c["delay"]+c["collection_months"]:
                receipt = min(c["remaining_expected"],c["expected_cash"]/c["collection_months"])
                c["remaining_expected"] -= receipt
                legacy_receipts += receipt
        st["legacy_net"] -= legacy_receipts
        require(st["legacy_net"] > -1e-6, "legacy book below zero")
    # Unrecoverable legacy loss reduces reported NI but not cash again: book was net of allowance.
    # New noncash estimate is recognized once. Cash receipts themselves release old NWC.
    fcf_before_financing = core_ni+nonlease_da-maintenance-fixed_growth_capex-delta_nwc+legacy_receipts
    ni = core_ni+legacy_non_cash_adjustment
    minimum_cash = sales_annual*scale*n["minimum_cash_sales_fraction"]
    delta_minimum_cash=minimum_cash-st["minimum_cash"]
    st["minimum_cash"]=minimum_cash
    interest_on_cash = max(0,st["cash"]-st["restricted"]-minimum_cash-st["payable_dividend"])*a["cash_yield"]/12*(1-n["tax_rate"])
    st["inventory"]=inventory; st["ordinary_ar"]=ordinary_ar; st["ap"]=ap
    st["normal_annual"]={"sales":sales_annual,"ebit":ebit*12,"nopat":(ebit-max(0,ebit*n["tax_rate"]))*12,
                         "nonlease_da":nonlease_da*12,"maintenance":maintenance*12,
                         "inventory":inventory,"ordinary_ar":ordinary_ar,"ap":ap,
                         "growth_fixed_capital_per_sales":n["growth_fixed_capital_per_sales"]*scale,
                         "minimum_cash":minimum_cash,"rent":rent_annual,"credit_cost":credit_cost*12}
    return {"sales":sales*scale,"sales_driver_annual":sales_annual,"gross_margin":gm,"ebit":ebit,
            "core_ni":core_ni,"reported_ni":ni+interest_on_cash,"closure_cost":closure_cost,"debt_interest":debt_interest,
            "cash_income":interest_on_cash,"cash_rent":rent_annual/12,"nonlease_da":nonlease_da,
            "recurring_owner_cash_before_growth":core_ni+nonlease_da-maintenance,
            "maintenance":maintenance,"growth_capex":fixed_growth_capex,"delta_nwc":delta_nwc,
            "legacy_collection":legacy_receipts,"legacy_non_cash_adjustment":legacy_non_cash_adjustment,
            "finished_goods":finished,"fcfe_pre_principal_projects":fcf_before_financing+interest_on_cash,
            "minimum_cash":minimum_cash,"delta_minimum_cash":delta_minimum_cash}, sales_annual


def debt_payment(st, k, t, a):
    # Research funding policy: principal paid in FCFE; never deducted again at t0.
    fraction=a["debt_repayment_schedule"][k].get(str(t),0.0)
    return min(st["debt"],st["debt_initial"]*fraction)


def apply_operating_budget(k,st,anchor,n,a,t,last_sales,legacy,projects):
    """Single operating/capital/debt cash engine, also used on copies for payout headroom."""
    row,next_sales=budget_month(k,st,anchor,n,a,t,last_sales,legacy)
    capex=sum(p["cash_remaining_proxy_at_cutoff"]/p["months"] for p in projects if p["node"]==k and t<=p["months"])
    growth_overlap=min(row["growth_capex"],capex*a["project_growth_capex_overlap_fraction"])
    row["growth_capex"]-=growth_overlap
    row["fcfe_pre_principal_projects"]+=growth_overlap
    row["project_growth_capex_overlap_credit"]=growth_overlap
    principal=debt_payment(st,k,t,a)
    st["debt"]-=principal
    st["cash"]+=row["fcfe_pre_principal_projects"]-capex-principal
    row["project_capex"]=capex; row["principal_paid"]=principal
    row["fcfe_after_projects_principal"]=row["fcfe_pre_principal_projects"]-capex-principal
    row["operating_fcfe_for_value"]=row["fcfe_after_projects_principal"]-row["cash_income"]-row["delta_minimum_cash"]
    return row,next_sales


def residual_operating_cash_guard(states,anchor,a,t,last_sales,projects,current,monthly,target,policy):
    """Discretionary upstream dividend only; no new funds or changed operating obligations.
    Observe current/quarter recurring cash, then reserve same-engine next-12-month
    capital/debt/working-cash needs. Projection excludes treasury income, so payout
    affordability never relies on interest earned on money it is about to distribute.
    """
    st=states["residual"]
    trailing=[m["nodes"]["residual"]["recurring_owner_cash_before_growth"] for m in monthly[-(policy["trailing_months"]-1):]]
    trailing.append(current["recurring_owner_cash_before_growth"])
    projected=deepcopy(st)
    # Already-declared payments are earmarked once at the start; no new dividends/support.
    projected["cash"]-=projected["payable_dividend"]
    projected["payable_dividend"]=0.0
    headroom=projected["cash"]-projected["restricted"]-projected["minimum_cash"]
    minimum_headroom=headroom; minimum_at=t; future=[]; sales=last_sales
    for step in range(1,policy["forward_months"]+1):
        at=t+step
        row,sales=apply_operating_budget("residual",projected,anchor,a["nodes"]["residual"],a,at,sales,[],projects)
        projected["cash"]-=row["cash_income"]
        available=projected["cash"]-projected["restricted"]-projected["minimum_cash"]
        if available<minimum_headroom:
            minimum_headroom=available;minimum_at=at
        future.append({"t":at,"recurring_owner_cash_before_growth":row["recurring_owner_cash_before_growth"],
            "cash_flow_excluding_treasury_income":row["fcfe_after_projects_principal"]-row["cash_income"],
            "project_capex":row["project_capex"],"principal_paid":row["principal_paid"],
            "minimum_cash":row["minimum_cash"],"headroom_before_new_distribution":available})
    future_recurring=sum(x["recurring_owner_cash_before_growth"] for x in future)
    reasons=[]
    if current["recurring_owner_cash_before_growth"]<=0:reasons.append("current_recurring_cash_nonpositive")
    if sum(trailing)<=0:reasons.append("trailing_quarter_recurring_cash_nonpositive")
    if future_recurring<=0:reasons.append("forward_year_recurring_cash_nonpositive")
    if minimum_headroom<=0:reasons.append("forward_committed_budget_has_no_distribution_headroom")
    amount=0.0 if reasons else min(max(0.0,target),max(0.0,minimum_headroom))
    return amount,{"rule":policy["rule"],"declaration_t":t,"target_from_prior_profit":target,
        "current_recurring_cash":current["recurring_owner_cash_before_growth"],
        "trailing_recurring_cash":trailing,"forward_recurring_cash_sum":future_recurring,
        "current_headroom":headroom,"minimum_forward_headroom":minimum_headroom,"minimum_headroom_at":minimum_at,
        "distribution_allowed":amount,"blocked_reasons":reasons,"forward_budget":future,
        "is_announced_company_policy":False,"treasury_income_counted_in_capacity":False,
        "new_borrowing_or_parent_support_assumed":False}


def declare(node, amount, states, events, t, pay_delay, own):
    st=states[node]
    amount=max(0.0,amount)
    if amount == 0:
        return
    st["payable_dividend"] += amount
    receivers = []
    if node=="cm": receivers=[("parent",own["a_cm_direct"]),("tech",own["tech_cm"])]
    elif node=="tech": receivers=[("parent",own["a_tech"])]
    elif node=="residual": receivers=[("parent",1.0)]
    for receiver, fraction in receivers:
        received=amount*fraction
        states[receiver]["receivable_dividend"] += received
        if receiver=="parent": states[receiver]["legal_credit"] += received
    events.append({"type":"payment","node":node,"at":t+pay_delay,"amount":amount,"receivers":receivers})


def settle_events(states, events, t, a, flows, dividends):
    remaining=[]
    for event in events:
        if event["at"] != t:
            remaining.append(event); continue
        st=states[event["node"]]
        amount=event["amount"]
        if event["type"]=="receipt":
            st["cash"] += amount
            st["receivable_dividend"] -= amount
            flows[event["node"]]["dividend_receipts"] += amount
        else:
            st["cash"] -= amount
            st["payable_dividend"] -= amount
            flows[event["node"]]["dividend_payments"] += amount
            if event["node"]=="parent":
                dividends[t]=dividends.get(t,0.0)+amount
            for receiver, fraction in event["receivers"]:
                lag=a["cm_receipt_lag_months"] if event["node"]=="cm" else 1
                remaining.append({"type":"receipt","node":receiver,"at":t+lag,"amount":amount*fraction,
                                  "source":event["node"]})
    return remaining


def owner_weights(data):
    o=data["raw"]["ownership"]
    return {"parent":1.0,"tech":o["a_tech"],"cm":o["a_cm_direct"]+o["a_tech"]*o["tech_cm"],"residual":1.0}


def financial_claim_value(states,data):
    """Owned financial claims net of restricted/operating cash and dividend claims.
    Financial debt is NOT subtracted here: scheduled principal and interest are in FCFE.
    """
    weights=owner_weights(data)
    detail={k:st["cash"]-st["restricted"]-st["minimum_cash"]+st["receivable_dividend"]-st["payable_dividend"] for k,st in states.items()}
    return sum(weights[k]*v for k,v in detail.items()),detail


def terminal_operating_value(states, data, a, rate):
    # Only continuing operations. NO accumulated cash is restored because a horizon ended.
    g=a["terminal_growth"]; detail={}; warnings=[]
    weights=owner_weights(data)
    for k,st in states.items():
        require(abs(st["debt"])<1e-6,"terminal principal not zero; specify an FCFE debt extension")
        n=st["normal_annual"]
        operating_nwc_growth=max(0,n["inventory"]+n["ordinary_ar"]-n["ap"])*g
        minimum_cash_growth=n["minimum_cash"]*g
        fixed_growth=n["sales"]*n["growth_fixed_capital_per_sales"]*g
        intensity_growth=operating_nwc_growth+minimum_cash_growth+fixed_growth
        # With nonpositive NOPAT, a positive ROIC rule is not meaningful; physical capital
        # requirements remain. The signed contribution survives rather than causing bankruptcy.
        roic_growth=max(0,n["nopat"])*(1+g)*g/a["terminal_incremental_roic"]
        reinvestment=max(intensity_growth,roic_growth)
        owner_earnings=n["nopat"]*(1+g)+n["nonlease_da"]*(1+g)-n["maintenance"]*(1+g)-reinvestment
        require(math.isfinite(owner_earnings),"nonfinite terminal operating cash")
        core=owner_earnings/(rate-g)
        state="positive_operating_contribution" if owner_earnings>0 else ("zero_operating_contribution" if owner_earnings==0 else "negative_operating_contribution")
        if owner_earnings<0:
            warnings.append({"node":k,"status":state,"meaning":"Signed continuing burden retained. Does not itself prove cash insolvency; continuation/funding/exit merits review."})
        detail[k]={"core_value":core,"operating_status":state,"next_owner_earnings":owner_earnings,
            "required_growth_reinvestment":reinvestment,"operating_nwc_growth":operating_nwc_growth,
            "minimum_operating_cash_growth":minimum_cash_growth,"fixed_growth":fixed_growth,
            "intensity_growth":intensity_growth,"roic_growth":roic_growth,
            "minimum_operating_cash_stock_not_released":n["minimum_cash"],"debt":st["debt"]}
    total=sum(weights[k]*v["core_value"] for k,v in detail.items())
    o=data["raw"]["ownership"]
    equivalent=detail["parent"]["core_value"]+o["a_tech"]*(detail["tech"]["core_value"]+o["tech_cm"]*detail["cm"]["core_value"])+o["a_cm_direct"]*detail["cm"]["core_value"]+detail["residual"]["core_value"]
    close(total,equivalent,"non-overlap signed terminal contribution")
    return total,detail,warnings


def apply_parent_reserve(parent,legal_profit,year,rate):
    # Budget accrual with a calendar-year cumulative target. Negative months reverse
    # only THIS year's provisional accrual; old statutory reserve is not distributed.
    profits=parent.setdefault("legal_profit_calendar_year",{})
    transfers=parent.setdefault("reserve_calendar_year",{})
    profits[year]=profits.get(year,0.0)+legal_profit
    target=rate*max(0.0,profits[year])
    delta=target-transfers.get(year,0.0)
    transfers[year]=target
    parent["statutory_reserve"]+=delta
    parent["re"]+=legal_profit-delta
    return delta,profits[year],target


def fixture_initialization(data,a):
    """Deterministic initial CONDITIONS only; same budget/payments/valuation chain follows.
    Does not run a second financial core and never applies to CN:600085 inputs.
    """
    f=data["deterministic_fixture"]; anchors={}; states={}
    for k in NODES:
        anchors[k]={"h1_owner_ni":0.0,"removed_h1_financial_income":0.0,"removed_h1_credit_reversal":0.0,
            "normalized_h1_owner_ni":0.0,"reference_annual_revenue":100.0,"reference_gross_margin":0.0,
            "cost_scale":1.0,"reference_nonrent_cost":0.0,"reference_postrent_ebit":0.0}
        states[k]={"cash":f.get("cash",{}).get(k,0.0),"debt":f.get("debt",{}).get(k,0.0),"debt_initial":f.get("debt",{}).get(k,0.0),"restricted":0.0,
            "inventory":0.0,"ordinary_ar":0.0,"ap":0.0,"payable_dividend":0.0,"receivable_dividend":0.0,
            "initial_inventory":0.0,"initial_ar":0.0,"initial_ap":0.0,"legacy_net":0.0,
            "re":f.get("parent_re",1000000.0) if k=="parent" else 0.0,"statutory_reserve":0.0,"legal_credit":0.0,
            "cost_index":1.0,"normal_annual":{},"profit_year":{}}
    legacy=[]
    for i,c in enumerate(f.get("legacy_claims",[])):
        net=c["gross"]-c["original_allowance"]
        expected=c["known_collection"]
        legacy.append({"cohort":i,"gross":c["gross"],"opening_net":net,"expected_cash":expected,
            "remaining_expected":expected,"collection_months":1,"delay":c["collection_month"]-1,
            "net_adjustment":expected-net})
        states["cm"]["legacy_net"]+=net
    controls={"initialization":"DETERMINISTIC_FIXTURE_NOT_COMPANY_FORECAST",
              "cm_legacy_expected_cash":sum(c["expected_cash"] for c in legacy),
              "cm_legacy_opening_net":sum(c["opening_net"] for c in legacy)}
    return anchors,states,legacy,[],controls,deepcopy(f.get("projects",[]))


def simulate(data, scenario):
    validate(data)
    a=scenario_assumptions(data,scenario)
    fixture=data.get("deterministic_fixture")
    policy=data["targeted_residual_policy"]
    require(policy["rule"]=="residual_operating_cash_guard_v1","unsupported discretionary policy rule")
    require(policy["trailing_months"]==3 and policy["forward_months"]==12,"frozen policy windows changed")
    require(scenario["id"]==policy["target_scenario"] or data["symbol"]=="FIXTURE","targeted implementation permits only slow_demand or deterministic fixtures")
    if fixture is not None:
        anchors,states,legacy,events,controls,projects=fixture_initialization(data,a)
    else:
        anchors=normalize_anchors(data,a)
        states,legacy,events,controls=opening_state(data,a)
        projects=project_plan(data,a)
    own=data["raw"]["ownership"]
    a["_cm_initial_finished_owner"]=0.0 if fixture is not None else data["raw"]["cm"]["finished_goods_hkd_m"]*data["raw"]["fx"]["h1_closing_rmb_per_hkd"]*a["owner_cash_fraction"]["cm"]
    sales={k:anchors[k]["reference_annual_revenue"]*a["nodes"][k]["sales_factor_from_h1_annual"] for k in NODES}
    for k in NODES:
        states[k]["minimum_cash"]=sales[k]*anchors[k]["cost_scale"]*a["nodes"][k]["minimum_cash_sales_fraction"]
    opening_states=deepcopy(states)
    opening_financial,opening_financial_detail=financial_claim_value(opening_states,data)
    weights=owner_weights(data)
    economic_profit_by_year={2026:0.0}
    for k in NODES:
        # Clearly labelled 10-month proxy. Used only to seed 2027 payout policy, not to create cash.
        states[k]["profit_year"][2026]=anchors[k]["normalized_h1_owner_ni"]*2*a["nodes"][k]["sales_factor_from_h1_annual"]*10/12
    october_profit_proxy=(anchors["parent"]["normalized_h1_owner_ni"]*2*a["nodes"]["parent"]["sales_factor_from_h1_annual"]
        +own["a_tech"]*anchors["tech"]["normalized_h1_owner_ni"]*2*a["nodes"]["tech"]["sales_factor_from_h1_annual"]
        +(own["a_cm_direct"]+own["a_tech"]*own["tech_cm"])*anchors["cm"]["normalized_h1_owner_ni"]*2*a["nodes"]["cm"]["sales_factor_from_h1_annual"]
        +anchors["residual"]["normalized_h1_owner_ni"]*2*a["nodes"]["residual"]["sales_factor_from_h1_annual"])/12
    economic_profit_by_year[2026]=data["raw"]["q3_group"]["parent_ni_ytd"]+october_profit_proxy
    controls["known_9m_parent_ni_for_2027_dividend_policy"]=data["raw"]["q3_group"]["parent_ni_ytd"]
    controls["October_NI_proxy_only_for_2027_dividend_policy_not_cash"]=october_profit_proxy
    legal_seed_2026=data["raw"]["parent"]["h1_ni"]+anchors["parent"]["normalized_h1_owner_ni"]*2*4/12
    if fixture is not None:
        economic_profit_by_year[2026]=0.0
        legal_seed_2026=0.0
        for k in NODES: states[k]["profit_year"][2026]=0.0
    states["parent"]["legal_profit_calendar_year"]={2026:legal_seed_2026}
    states["parent"]["reserve_calendar_year"]={2026:0.0}
    controls["2026_pre_cutoff_legal_profit_seed_for_annual_reserve_only"]=legal_seed_2026
    controls["2026_reserve_prior_to_future_budget"]=0.0
    monthly=[]; dividend_map={}; snapshots={}; cash_audit_max=0.0
    for t in range(1,a["months"]+1):
        y,m=month_date(t)
        flows={k:{"opening_cash":states[k]["cash"],"dividend_receipts":0.0,"dividend_payments":0.0} for k in NODES}
        events=settle_events(states,events,t,a,flows,dividend_map)
        node_month={}
        for k in NODES:
            st=states[k]
            row,sales[k]=apply_operating_budget(k,st,anchors[k],a["nodes"][k],a,t,sales[k],legacy,projects)
            st["profit_year"][y]=st["profit_year"].get(y,0)+row["reported_ni"]
            node_month[k]=row
        # Tech owner profit includes its CM interest. Parent consolidated earnings never add internal dividends.
        cm_ni=node_month["cm"]["reported_ni"]
        group_ni=(node_month["parent"]["reported_ni"]+own["a_tech"]*(node_month["tech"]["reported_ni"]+own["tech_cm"]*cm_ni)
                  +own["a_cm_direct"]*cm_ni+node_month["residual"]["reported_ni"])
        economic_profit_by_year[y]=economic_profit_by_year.get(y,0)+group_ni
        # Declare sub dividends in March/April, pay CM June, Tech August, residual May.
        for k, declaration_month, pay_delay in (("cm",3,3),("tech",3,5),("residual",4,1)):
            if m==declaration_month:
                prior=states[k]["profit_year"].get(y-1,0)
                if k=="tech": prior+=own["tech_cm"]*states["cm"]["profit_year"].get(y-1,0)
                target=max(0,prior)*a["subsidiary_payout"][k]
                if k=="residual":
                    amount,decision=residual_operating_cash_guard(states,anchors[k],a,t,sales[k],projects,node_month[k],monthly,target,policy)
                    node_month[k]["discretionary_upstream_decision"]=decision
                else:
                    available=states[k]["cash"]-states[k]["restricted"]-node_month[k]["minimum_cash"]-states[k]["payable_dividend"]
                    due_capex=sum(p["cash_remaining_proxy_at_cutoff"]/p["months"]*max(0,min(12,p["months"]-t)) for p in projects if p["node"]==k)
                    due_principal=sum(debt_payment(states[k],k,j,a) for j in range(t+1,min(120,t+12)+1))
                    available-=due_capex+due_principal
                    amount=min(target,max(0,available))
                declare(k,amount,states,events,t,pay_delay,own)
        parent=states["parent"]
        legal_profit=node_month["parent"]["reported_ni"]+parent["legal_credit"]
        parent["legal_credit"]=0.0
        reserve,legal_ytd,reserve_ytd=apply_parent_reserve(parent,legal_profit,y,a["parent_statutory_rate"])
        if m==12:
            close(reserve_ytd,a["parent_statutory_rate"]*max(0,legal_ytd),"annual statutory reserve calibration")
        a_div_declared=0.0
        if m==5:
            target=max(0,economic_profit_by_year.get(y-1,0))*a["parent_payout"]
            cash_capacity=parent["cash"]-parent["restricted"]-node_month["parent"]["minimum_cash"]-parent["payable_dividend"]
            due_parent_principal=sum(debt_payment(parent,"parent",j,a) for j in range(t+1,min(120,t+12)+1))
            cash_capacity-=due_parent_principal
            a_div_declared=min(target,max(0,parent["re"]),max(0,cash_capacity))
            parent["re"]-=a_div_declared
            declare("parent",a_div_declared,states,events,t,2,own)
        if fixture is not None:
            for payment in fixture.get("known_parent_payments",[]):
                if t==payment["declaration_month"]:
                    amount=payment["amount"]
                    require(parent["re"]>=amount,"fixture declared payment exceeds RE")
                    parent["re"]-=amount
                    a_div_declared+=amount
                    declare("parent",amount,states,events,t,payment["payment_month"]-t,own)
        # Technical identities must raise errors, not become economic nulls.
        for k in NODES:
            st=states[k]; row=node_month[k]; flow=flows[k]
            expected=flow["opening_cash"]+flow["dividend_receipts"]-flow["dividend_payments"]+row["fcfe_after_projects_principal"]
            cash_audit_max=max(cash_audit_max,abs(expected-st["cash"]))
            close(expected,st["cash"],f"cash roll {k} {t}")
            free=st["cash"]-st["restricted"]-st["payable_dividend"]
            if free < row["minimum_cash"]-1e-7:
                unrestricted=st["cash"]-st["restricted"]
                hard_shortfall=unrestricted < -1e-7
                kind="current_unrestricted_cash_shortfall" if hard_shortfall else "policy_buffer_breach_unresolved"
                evidence={"kind":kind,"boundary":"A_attributable_aggregate_not_a_legal_entity" if k=="residual" else "specified_research_cash_boundary",
                    "cash":st["cash"],"restricted":st["restricted"],"unrestricted_cash":unrestricted,
                    "dividend_payable":st["payable_dividend"],"minimum_cash":row["minimum_cash"],
                    "minimum_buffer_shortfall":row["minimum_cash"]-free,
                    "current_ebit":row["ebit"],"current_operating_cash_after_projects_principal":row["fcfe_after_projects_principal"],
                    "current_project_budget_payment":row["project_capex"],"current_research_schedule_principal":row["principal_paid"],
                    "current_dividend_payment":flow["dividend_payments"],
                    "cumulative_node_distributions":sum(mo["nodes"][k]["dividend_payments"] for mo in monthly)+flow["dividend_payments"],
                    "debt_schedule_is_unchanged_research_policy":True,"new_funding_assumed":False,
                    "whole_company_insolvency_claim":False}
                partial={"month":t,"node":k,"cash":st["cash"],"minimum_cash":row["minimum_cash"],
                    "dividend_payable":st["payable_dividend"],"monthly_so_far":monthly,"current_month_budget":node_month,
                    "states_at_failure":states,"controls":controls,"project_plan":projects,"failure_evidence":evidence}
                message=f"{scenario['id']} {k} month {t}: {kind}; specified budget only, no funding plug or whole-company insolvency inference"
                if hard_shortfall:raise EconomicInfeasible(message,partial)
                raise PolicyBufferBreach(message,partial)
            row.update({"closing_cash":st["cash"],"debt":st["debt"],"inventory":st["inventory"],"ordinary_ar":st["ordinary_ar"],
                        "legacy_net_ar":st["legacy_net"],"ap":st["ap"],"receivable_dividend":st["receivable_dividend"],
                        "payable_dividend":st["payable_dividend"],"dividend_receipts":flow["dividend_receipts"],"dividend_payments":flow["dividend_payments"]})
        monthly.append({"t":t,"year":y,"month":m,"a_attributable_economic_ni":group_ni,"a_dividend_paid":dividend_map.get(t,0),
                        "a_dividend_declared":a_div_declared,"parent_legal_profit":legal_profit,"parent_statutory_transfer":reserve,
                        "parent_re":parent["re"],"parent_statutory_reserve":parent["statutory_reserve"],
                        "parent_legal_profit_calendar_ytd":legal_ytd,"parent_reserve_calendar_ytd":reserve_ytd,
                        "a_operating_fcfe_for_value":sum(weights[k]*node_month[k]["operating_fcfe_for_value"] for k in NODES),"nodes":node_month})
        if t in (2,12,24,36,48,60,72,120): snapshots[str(t)]=deepcopy(states)
    valuation=[]
    financial_y5,financial_y5_detail=financial_claim_value(snapshots["60"],data)
    for rate in a["discount_rates"]:
        tail,taildetail,terminal_warnings=terminal_operating_value(states,data,a,rate)
        operating_pv=sum(row["a_operating_fcfe_for_value"]/(1+rate)**(row["t"]/12) for row in monthly)
        current=opening_financial+operating_pv+tail/(1+rate)**10
        operating_after5=sum(row["a_operating_fcfe_for_value"]/(1+rate)**((row["t"]-60)/12) for row in monthly if row["t"]>60)
        y5=financial_y5+operating_after5+tail/(1+rate)**5
        actual_pv5=sum(d/(1+rate)**(t/12) for t,d in dividend_map.items() if t<=60)
        holder_implied=actual_pv5+y5/(1+rate)**5
        operating_pv5=sum(row["a_operating_fcfe_for_value"]/(1+rate)**(row["t"]/12) for row in monthly if row["t"]<=60)
        timing_bridge=actual_pv5+financial_y5/(1+rate)**5-opening_financial-operating_pv5
        close(holder_implied-current,timing_bridge,"asset-value versus dated-distribution bridge")
        shares=data["raw"]["shares_m"]
        valuation.append({"discount_rate":rate,"current_value_per_share":current/shares,
            "year5_value_per_share":y5/shares,"pv_first5_dividends_per_share":actual_pv5/shares,
            "opening_owned_financial_claims":opening_financial,"opening_financial_by_node":opening_financial_detail,
            "operating_fcfe_pv":operating_pv,"year10_operating_value":tail,"year10_detail":taildetail,
            "terminal_warnings":terminal_warnings,"year5_owned_financial_claims":financial_y5,"year5_financial_by_node":financial_y5_detail,
            "holder_D_plus_Y5_implied_current_per_share":holder_implied/shares,
            "capital_access_timing_gap_per_share":timing_bridge/shares,
            "method_boundary":"Main=operating FCFE PV plus owned available financial claims NOW; dated D and Y5 are same-state holder/capital-access diagnostics. No Y10 recovery of retained principal."})
    annual=[]
    sums=("sales","ebit","core_ni","reported_ni","cash_rent","nonlease_da","maintenance","growth_capex","project_capex","project_growth_capex_overlap_credit","closure_cost","delta_nwc","legacy_collection","legacy_non_cash_adjustment","principal_paid","cash_income","delta_minimum_cash","operating_fcfe_for_value","fcfe_after_projects_principal")
    for yr in range(1,11):
        block=monthly[(yr-1)*12:yr*12]
        row={"holding_year":yr,"end_date":f"{2026+yr}-10-31","a_cash_dividend":sum(x["a_dividend_paid"] for x in block),
             "a_economic_ni":sum(x["a_attributable_economic_ni"] for x in block),"parent_re":block[-1]["parent_re"],"nodes":{}}
        for k in NODES:
            row["nodes"][k]={field:sum(x["nodes"][k][field] for x in block) for field in sums}
            row["nodes"][k].update({field:block[-1]["nodes"][k][field] for field in ("closing_cash","inventory","ordinary_ar","legacy_net_ar","ap","debt","receivable_dividend","payable_dividend","minimum_cash")})
        annual.append(row)
    require(max((abs(c["remaining_expected"]) for c in legacy),default=0.0)<1e-6,"uncollected legacy beyond horizon must not disappear")
    result={"scenario":scenario["id"],"status":"computed_not_independently_validated","description":scenario["description"],
            "targeted_residual_policy":deepcopy(policy),"source_cutoff":data["cutoff"],"method":"operating FCFE value plus same-boundary current financial claims; dated payouts are separate capital-access diagnostics",
            "anchors":anchors,"opening_controls":controls,"project_plan":projects,"legacy_cohorts":legacy,
            "cash_roll_max_abs_error":cash_audit_max,"annual":annual,"monthly":monthly,
            "stub_nov_dec_2026":monthly[:2],"capital_transition_years":[annual[i-1] for i in (4,5,6,10)],
            "dividends_per_share_year1_to5":[x["a_cash_dividend"]/data["raw"]["shares_m"] for x in annual[:5]],
            "valuation_by_rate":valuation,"snapshots":snapshots,"economic_warnings":valuation[0]["terminal_warnings"],
            "limitations":["cash and debt residual ownership are explicit ranges, not precise legal-entity September accounts",
                "dynamic NWC covers inventory/trade AR/AP; other operating balances held constant, not a full statutory cashflow reconstruction",
                "October cash and RE are unobserved proxies; October never appears as future operating income",
                "invoice age is not past-due status; legacy recovery and delay are separate",
                "parent RE uses conservative unchanged H1 proxy plus explicit October adjustment; no undisclosed July-October profit credit",
                "maintenance and lease budgets are owner-level research assumptions, not source-certified legal entity schedules",
                "main financial claims are valued at the current snapshot; no horizon-triggered release; actual-distribution timing effect separately shown",
                "nonpositive terminal node contributions remain signed warnings, not automatic cash insolvency; auxiliary range has its own status"]}

    try:
        result["auxiliary_method"]=normalized_earnings_check(data,a,opening_states,anchors,valuation)
    except Exception as exc:
        # Genuine malformed auxiliary inputs still fail nonzero, but preserve finished main work.
        exc.partial_model=result
        raise
    return result


def normalized_earnings_check(data,a,opening,anchors,valuation):
    """Independent historical normalization input, not reverse solved from main DCF."""
    own=data["raw"]["ownership"]
    weights={"parent":1.0,"tech":own["a_tech"],"cm":own["a_cm_direct"]+own["a_tech"]*own["tech_cm"],"residual":1.0}
    cash=0.0; debt=0.0
    for k in NODES:
        minimum=anchors[k]["reference_annual_revenue"]*a["nodes"][k]["sales_factor_from_h1_annual"]*anchors[k]["cost_scale"]*a["nodes"][k]["minimum_cash_sales_fraction"]
        cash+=weights[k]*(opening[k]["cash"]-opening[k]["restricted"]-minimum+opening[k]["receivable_dividend"]-opening[k]["payable_dividend"])
        debt+=weights[k]*opening[k]["debt"]
    x=data["auxiliary"]
    for key in ("reported_owner_ni_range","aftertax_financial_income_range","owner_nonlease_da_range","owner_maintenance_range","normal_growth_reinvestment_range"):
        bounds=x[key]
        require(len(bounds)==2 and all(math.isfinite(v) for v in bounds) and bounds[0]<=bounds[1],f"invalid auxiliary input interval: {key}")
    aftertax_debt_interest=debt*a["loan_rate"]*(1-x["debt_interest_tax_proxy"])
    low=(x["reported_owner_ni_range"][0]-x["aftertax_financial_income_range"][1]+aftertax_debt_interest
         +x["owner_nonlease_da_range"][0]-x["owner_maintenance_range"][1]-x["normal_growth_reinvestment_range"][1])
    high=(x["reported_owner_ni_range"][1]-x["aftertax_financial_income_range"][0]+aftertax_debt_interest
          +x["owner_nonlease_da_range"][1]-x["owner_maintenance_range"][0]-x["normal_growth_reinvestment_range"][0])
    require(math.isfinite(low) and math.isfinite(high) and high>=low,"nonfinite or reversed auxiliary owner earnings range")
    shares=data["raw"]["shares_m"]
    require(all(rate>0 and math.isfinite(rate) for rate in x["capitalization_rates"]),"invalid auxiliary capitalization rate")
    corners=[(earn/rate+cash-debt)/shares for earn in (low,high) for rate in x["capitalization_rates"]]
    values=[min(corners),max(corners)]
    auxiliary_status="positive_normalization_range" if low>0 else ("nonpositive_normalization_range" if high<=0 else "normalization_range_crosses_zero")
    center=sum(values)/2
    main=next(v["current_value_per_share"] for v in valuation if v["discount_rate"]==a["primary_discount_rate"])
    gap=abs(main-center)/abs(center) if center else None
    return {"status":auxiliary_status,"method":x["method"],"basis":x["basis"],"owner_earnings_range":[low,high],
            "attributable_opening_excess_financial_assets":cash,"attributable_debt":debt,
            "capitalization_rates":x["capitalization_rates"],"current_value_range_per_share":values,
            "center_gap_from_main":gap,"requires_explanation_if_over_25pct":gap is None or gap>0.25,
            "not_averaged_into_core":True,
            "invested_capital_proxy":data["raw"]["q3_group"]["parent_equity"]-cash+debt,
            "timing_difference":"aux assumes immediate normalized earnings and subtracts debt once; main phases operating FCFE and pays principal in budget. Both add same-boundary owned financial claims at the valuation date."}
