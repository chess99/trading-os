"""Luxshare: pure standard-library financial functions. Import performs no model work.
Amounts CNY bn; shares bn; all paths supplied by CLI. No network, market prices or hidden files.
"""
import copy
import math

EPS = 1e-8


class EconomicInfeasible(Exception):
    def __init__(self, reason, details=None):
        super().__init__(reason)
        self.reason = reason
        self.details = details or {}


def near(a, b, label, tol=1e-7):
    if not math.isfinite(a) or not math.isfinite(b) or abs(a-b) > tol * max(1.0, abs(a), abs(b)):
        raise ArithmeticError(f"identity failed: {label}: {a!r} != {b!r}")


def dividend_payable_bridge(september_payable, october_paid, other_payables, common_fraction, likai_fraction):
    if october_paid > september_payable+EPS or not 0 <= common_fraction <= 1 or not 0 <= likai_fraction <= 1:
        raise ValueError("invalid legacy dividend classification")
    remaining = september_payable-october_paid
    common = remaining*common_fraction
    nci = remaining-common
    return {"september_payable": september_payable, "october_paid": october_paid,
            "cutoff_remaining": remaining, "operating_other_payables": other_payables-september_payable,
            "legacy_common": common, "legacy_likai": nci*likai_fraction,
            "legacy_other_nci": nci*(1-likai_fraction), "new_cutoff_holder_right": 0.0}


def nci_boundary(assets, assigned_debt, recourse_fraction):
    """Valuation boundary, not a cash-default test or legal guarantee assertion."""
    if not 0 <= recourse_fraction <= 1:
        raise ValueError("recourse fraction outside0-1")
    raw = assets-assigned_debt
    deficiency = min(assigned_debt, max(0.0, -raw))
    continuing_negative_asset_burden = max(0.0, -assets)
    parent_obligation = deficiency*recourse_fraction
    creditor_recovery_loss = deficiency-parent_obligation
    nci_debt_recoverable_from_own_assets = assigned_debt-deficiency
    equity = max(0.0, assets-nci_debt_recoverable_from_own_assets)
    near(assigned_debt, nci_debt_recoverable_from_own_assets+parent_obligation+creditor_recovery_loss,
         "NCI paired creditor/recourse scope")
    return {"raw_equity": raw, "nci_equity_after_boundary": equity,
            "nci_debt_recoverable_from_assigned_assets": nci_debt_recoverable_from_own_assets,
            "common_group_recourse_obligation": parent_obligation,
            "external_creditor_recovery_loss": creditor_recovery_loss,
            "negative_operating_asset_burden_retained_in_group_EV": continuing_negative_asset_burden,
            "status": "NEGATIVE_RAW_NCI_BOUNDARY_APPLIED" if raw < -EPS else "RAW_NCI_NONNEGATIVE",
            "cash_default_proven": False, "cash_face_obligations_not_written_off": True}


def capacity_investment(sales, maintained_capacity, marginal_turnover):
    if marginal_turnover <= 0:
        raise ValueError("nonpositive marginal capital turnover")
    needed_sales_capacity = max(0.0, sales-maintained_capacity)
    growth_capital = needed_sales_capacity/marginal_turnover
    return {"growth_capital": growth_capital, "capacity_sales_end": maintained_capacity+needed_sales_capacity,
            "idle_capacity_sales_end": max(0.0, maintained_capacity-sales),
            "marginal_turnover": marginal_turnover}


def fade(start, end, year, last_year):
    return start + (end-start) * min(max(year / last_year, 0.0), 1.0)


def cohort_rate(entry_rate, cost, age, years):
    return cost + (entry_rate-cost) * max(0.0, 1.0-age/years)


def entrant_rate(old_rate_at_entry, cap, cost):
    # The mature cap itself converges with the entry-year old return.
    return min(cap, old_rate_at_entry) if old_rate_at_entry > cost else old_rate_at_entry


def capital_cash(delivered, noncash_lease, prepaid_begin, new_prepay, payable_begin, payable_end):
    cash_delivery = delivered - noncash_lease
    if min(delivered, noncash_lease, prepaid_begin, new_prepay, payable_begin, payable_end) < -EPS or cash_delivery < -EPS:
        raise ValueError("invalid capital delivery/lease/prepayment")
    used = min(prepaid_begin, max(0.0, cash_delivery))
    result = {
        "delivered_capital": delivered, "noncash_lease_addition": noncash_lease,
        "prepaid_begin": prepaid_begin, "prepaid_used_on_delivery": used,
        "new_capital_prepayment": new_prepay,
        "prepaid_end": prepaid_begin-used+new_prepay,
        "capital_payable_begin": payable_begin, "capital_payable_end": payable_end,
        "actual_capital_cash": cash_delivery-used+new_prepay+payable_begin-payable_end,
    }
    result["financing_neutral_investment"] = result["actual_capital_cash"] + noncash_lease
    near(result["actual_capital_cash"], delivered-noncash_lease+result["prepaid_end"]-prepaid_begin+payable_begin-payable_end, "capital/prepay/payable")
    return result


def cash_bridge(fcff, minimum_cash_increment, financing_interest, interest_shield,
                tax_timing, financial_income_net, associate_cash_net,
                noncash_lease_addition=0.0, financial_redemption=0.0,
                financial_purchase=0.0, debt_new_cash=0.0, debt_repayment_cash=0.0,
                external_equity_cash=0.0, nci_capital_cash=0.0, nci_distribution=0.0,
                outside_investment_cash=0.0, unfunded_commitment_cash=0.0,
                common_distribution=0.0, financial_liability_settlement=0.0,
                legacy_dividend_settlement=0.0, group_internal_support=0.0):
    # fcff is financing-neutral, including noncash leased capital and delta minimum cash.
    items = {
        "fcff": fcff, "minimum_cash_increment_restored": minimum_cash_increment,
        "financing_interest_paid": -financing_interest, "usable_interest_tax_shield": interest_shield,
        "extra_operating_cash_tax": -tax_timing, "financial_income_net": financial_income_net,
        "associate_actual_cash_net": associate_cash_net,
        "noncash_lease_investment_restored": noncash_lease_addition,
        "financial_principal_redeemed": financial_redemption, "financial_principal_purchased": -financial_purchase,
        "debt_cash_borrowed": debt_new_cash, "debt_cash_repaid": -debt_repayment_cash,
        "external_equity_cash": external_equity_cash, "nci_cash_injected": nci_capital_cash,
        "nci_cash_distributed": -nci_distribution, "outside_investment_cash": -outside_investment_cash,
        "unfunded_commitment_cash": -unfunded_commitment_cash, "common_cash_distributed": -common_distribution,
        "financial_liability_cash_settlement": -financial_liability_settlement,
        "legacy_dividend_paid_to_old_right_holders": -legacy_dividend_settlement,
        "group_internal_support_transfer": group_internal_support,
    }
    return {"components": items, "change_in_cash": sum(items.values())}


def fund_pool(cash_begin, minimum_cash, restricted_cash, free_deposits, desired_distribution,
              mandatory_distribution, raw_change, ordinary_debt, paired_debt_floor):
    """No net new borrowing. Redeem available principal, trim optional D, repay unpaired debt.
    Does not move another ownership pool's cash. Used by formal path and closed-form fixtures.
    """
    if min(cash_begin, minimum_cash, restricted_cash, free_deposits, desired_distribution,
           mandatory_distribution, ordinary_debt, paired_debt_floor) < -EPS:
        raise ValueError("negative opening cash/funding input")
    required = minimum_cash + restricted_cash
    c = cash_begin + raw_change
    redemption = min(free_deposits, max(0.0, required+mandatory_distribution-c))
    c += redemption
    deposits = free_deposits-redemption
    if c+EPS < required+mandatory_distribution:
        raise EconomicInfeasible("cash_shortfall_even_with_optional_D_zero", {
            "cash_before_D": c, "minimum_and_restricted": required,
            "mandatory_D": mandatory_distribution, "remaining_free_deposits": deposits,
            "gap": required+mandatory_distribution-c})
    # Do not liquidate deposits solely to fund discretionary dividends.
    optional_paid = min(max(0.0, desired_distribution-mandatory_distribution), max(0.0, c-required-mandatory_distribution))
    paid = mandatory_distribution+optional_paid
    c -= paid
    repay = min(max(ordinary_debt-paired_debt_floor, 0.0), max(c-required, 0.0))
    c -= repay
    debt_end = ordinary_debt-repay
    purchase = max(0.0, c-required)
    c -= purchase
    deposits += purchase
    near(c, cash_begin+raw_change+redemption-paid-repay-purchase, "pool cash conservation")
    near(free_deposits+purchase-redemption, deposits, "deposit principal conservation")
    if c+EPS < required:
        raise ArithmeticError("post-allocation liquidity floor violated")
    return {"cash_end": c, "free_deposits_end": deposits, "ordinary_debt_end": debt_end,
            "financial_redemption": redemption, "financial_purchase": purchase,
            "ordinary_voluntary_repayment": repay, "distribution_paid": paid,
            "optional_distribution_cut": max(0.0, desired_distribution-paid),
            "required_cash": required}


def associate_schedule(cfg, initial_book, g, horizon, earnings_factor=1.0):
    if cfg["cash_withholding_rate"] != 0.0 or cfg["external_capital_calls"] != 0.0:
        raise ValueError("nonzero associate withholding/capital calls require explicit extended treatment")
    ke = cfg["equity_cost"]
    if not 0 <= g < ke:
        raise ValueError("associate stable growth must be below equity cost")
    old_rate0 = cfg["normal_old_earnings"]*earnings_factor/initial_book
    cohorts = []
    book = initial_book
    ar = cfg["opening_receivable"]
    result = [{"year": 0, "book_end": book, "receivable_end": ar, "ri": 0.0,
               "earnings": 0.0, "dividend_declared": 0.0, "cash_received": 0.0,
               "new_cohort": 0.0, "cohorts": []}]
    for year in range(1, horizon+1):
        old_rate = fade(old_rate0, ke, year, cfg["old_fade_years"])
        cohort_income = []
        for item in cohorts:
            rate = cohort_rate(item["entry_rate"], ke, year-item["entry_year"], cfg["cohort_fade_years"])
            cohort_income.append({**item, "rate_this_year": rate, "income": item["capital"]*rate})
        earnings = initial_book*old_rate + sum(x["income"] for x in cohort_income)
        stable_payout = 1.0-g/ke
        if year <= cfg["payout_hold_years"]:
            payout = cfg["payout_initial"]
        else:
            payout = fade(cfg["payout_initial"], stable_payout,
                          year-cfg["payout_hold_years"], cfg["payout_mature_year"]-cfg["payout_hold_years"])
        declared = max(earnings, 0.0)*payout
        actual = ar + declared*(1-cfg["collection_lag_fraction"])
        ar_end = declared*cfg["collection_lag_fraction"]
        retained = earnings-declared
        if retained < -EPS:
            raise EconomicInfeasible("associate_retention_negative_requires_capital_reduction", {"year": year})
        entry = entrant_rate(old_rate, cfg["new_entry_return_cap"], ke)
        near(book, initial_book+sum(x["capital"] for x in cohorts), "associate capital cohorts")
        new_book = book+retained
        ri = earnings-ke*book
        row = {"year": year, "book_begin": book, "book_end": new_book,
               "old_capital": initial_book, "old_return": old_rate, "old_earnings": initial_book*old_rate,
               "cohort_earnings": sum(x["income"] for x in cohort_income), "earnings": earnings,
               "payout": payout, "dividend_declared": declared,
               "receivable_begin": ar, "cash_received": actual, "receivable_end": ar_end,
               "retained": retained, "new_cohort": retained, "entry_return": entry,
               "ri": ri, "cohorts": cohort_income}
        near(ar+declared-actual, ar_end, "associate declared/receivable/cash")
        near(book+earnings-declared, new_book, "associate clean surplus")
        result.append(row)
        if retained > EPS:
            cohorts.append({"entry_year": year, "entry_rate": entry, "capital": retained})
        book, ar = new_book, ar_end
    if abs(result[-1]["ri"]) > 1e-7:
        raise ArithmeticError("associate RI tail not exhausted: extend horizon, do not force terminal zero")
    return result


def associate_value(rows, at, ke, g=0.0, lag_fraction=0.0, wait_rate=0.0):
    # Production RI prices dividends at declaration. Explicitly bridge their collection wait.
    if abs(rows[-1]["ri"]) > 1e-7:
        raise ArithmeticError("nonzero associate production terminal RI")
    if not (0 <= lag_fraction <= 1 and 0 <= wait_rate and g < ke):
        raise ValueError("invalid associate collection valuation inputs")
    tail = sum(row["ri"]/(1+ke)**(row["year"]-at) for row in rows if row["year"] > at)
    ar_face = rows[at].get("receivable_end", 0.0)
    ar_value = ar_face/(1+wait_rate)
    future_declared_pv = sum(row.get("dividend_declared", 0.0)/(1+ke)**(row["year"]-at)
                             for row in rows if row["year"] > at)
    # Production capital has ke return in steady state, so declaration = (ke-g)*B.
    # Collection waiting remains even after production excess returns have ended.
    terminal_next_declared = rows[-1]["book_end"]*(ke-g)
    terminal_declaration_pv = terminal_next_declared/(ke-g)/(1+ke)**(rows[-1]["year"]-at)
    wait_unit_cost = lag_fraction*(1.0-1.0/(1+wait_rate))
    explicit_wait = future_declared_pv*wait_unit_cost
    perpetual_wait_tail = terminal_declaration_pv*wait_unit_cost
    return {"book": rows[at]["book_end"], "receivable_face": ar_face,
            "receivable_value": ar_value, "production_residual_income_pv": tail,
            "future_explicit_collection_wait_cost": explicit_wait,
            "perpetual_collection_wait_tail_cost": perpetual_wait_tail,
            "wait_discount_rate": wait_rate, "lag_fraction": lag_fraction,
            "timing_convention": "declaration-year75%/next-annual-bucket25%; short waiting discounted at frozen financial rate, not operatingWACC",
            "value": rows[at]["book_end"]+ar_value+tail-explicit_wait-perpetual_wait_tail}


def enterprise_value(fcffs, terminal_next_fcff, g, wacc, at=0):
    if wacc <= g:
        raise ValueError("WACC must exceed g")
    n = len(fcffs)
    explicit = sum(fcffs[j-1]/(1+wacc)**(j-at) for j in range(at+1, n+1))
    terminal_at_n = terminal_next_fcff/(wacc-g)
    terminal_pv = terminal_at_n/(1+wacc)**(n-at)
    return {"explicit_pv": explicit, "terminal_pv": terminal_pv, "value": explicit+terminal_pv,
            "terminal_pv_fraction": terminal_pv/(explicit+terminal_pv) if explicit+terminal_pv else None}


def equity_bridge(operating_ev, financial_assets, associate_assets, debt, nci_value,
                  ordinary_dividend_payable=0.0, holder_distribution_right=0.0,
                  unissued_employee_claim=0.0):
    company_equity = operating_ev+financial_assets+associate_assets-debt-nci_value-ordinary_dividend_payable
    return {"operating_ev": operating_ev, "financial_assets": financial_assets,
            "associate_assets": associate_assets, "debt": debt, "full_nci_value": nci_value,
            "ordinary_dividend_payable": ordinary_dividend_payable,
            "company_equity_ex_dividend_right": company_equity,
            "cutoff_holder_distribution_right": holder_distribution_right,
            "unissued_employee_claim": unissued_employee_claim,
            "ordinary_holder_equity": company_equity+holder_distribution_right-unissued_employee_claim}


def option_step(lots, year, dividend_per_share, intrinsic_after_year, october_exercised=0.0):
    updated = copy.deepcopy(lots)
    total_n = total_cash = 0.0
    records = []
    for lot in updated:
        lot["strike_current"] = max(0.01, lot.get("strike_current", lot["strike"])-dividend_per_share)
        n0 = lot.get("initial_remaining", lot["remaining"])
        lot["initial_remaining"] = n0
        vest = n0*lot["vesting_weights"][year-1] if year <= len(lot["vesting_weights"]) else 0.0
        lot["available"] = lot.get("available", 0.0)+vest
        exercised = lot["available"] if year <= lot["expiry_year"] and intrinsic_after_year > lot["strike_current"] else 0.0
        lot["available"] -= exercised
        lot["remaining"] -= exercised
        expired = 0.0
        if year >= lot["expiry_year"]:
            expired = lot["remaining"]
            lot["remaining"] = 0.0
            lot["available"] = 0.0
        paid = exercised*lot["strike_current"]
        total_n += exercised
        total_cash += paid
        records.append({"name": lot["name"], "vested_this_year": vest, "strike": lot["strike_current"],
                        "exercised": exercised, "exercise_cash": paid, "expired": expired,
                        "remaining": lot["remaining"]})
    return updated, {"shares_issued": total_n, "cash_received": total_cash, "lots": records}


def ownership_weights(inputs, patch):
    factor = patch.get("nci_claims_factor", 1.0)
    result = {}
    for name in ("likai", "other_nci"):
        result[name] = {k: (v*factor if k.endswith("_share") else v) for k, v in inputs["ownership"][name].items()}
    result["common"] = {k: 1.0-sum(result[n][k] for n in ("likai", "other_nci"))
                        for k in ("operating_share", "financial_share", "ordinary_debt_share", "associate_share")}
    result["common"]["nci_payout"] = 0.0
    for name, item in result.items():
        if any(not 0 <= item[k] <= 1 for k in item if k.endswith("_share")):
            raise ValueError(f"ownership claim outside0-1: {name}")
    for key in ("operating_share", "financial_share", "ordinary_debt_share", "associate_share"):
        near(sum(x[key] for x in result.values()), 1.0, "ownership sum "+key)
    return result


def initial_state(inputs, patch):
    f, e, b = inputs["facts"], inputs["opening_estimates"], inputs["business"]
    issued = f["oct29_issued_shares"]
    oct_cb_shares = issued-f["sept_registered_shares"]-e["october_options_exercised"]
    if oct_cb_shares < -EPS:
        raise ValueError("October share bridge inconsistent")
    cb_face = f["cb_sept_face"]-max(oct_cb_shares, 0.0)*f["cb_conversion_price"]
    cb_value = cb_face*f["cb_redemption_factor"]
    legacy = dividend_payable_bridge(f["q3_dividends_payable"], f["known_h1_dividend_total"], f["q3_other_payables"],
                                     e["legacy_dividend_common_fraction"], e["legacy_dividend_nci_likai_fraction"])
    cash = f["q3_cash"]-f["known_h1_dividend_total"]+e["october_options_exercised"]*e["october_option_price"]+e["october_unknown_net_operating_cash"]
    restricted_cash = f["q3_cash"]-f["q3_cash_equivalents"]
    transfer_nwc = patch.get("financial_to_nwc", 0.0)
    transfer_cap = patch.get("financial_to_capital_prepay", 0.0)
    deposits = (f["q3_trading"]+f["q3_term_due"]+f["q3_other_current_assets"]-e["other_current_nonfinancial"]
                +f["q3_other_noncurrent_assets"]-e["capital_prepaid"]-e["acquisition_prepaid_to_productive_capital"]-e["other_noncurrent_nonfinancial"]
                -transfer_nwc-transfer_cap)
    pledged = e["restricted_deposits"]+patch.get("extra_restricted_deposits", 0.0)
    if deposits < pledged:
        raise ValueError("restricted deposits exceed financial deposits")
    other_fin = (f["q3_other_equity"]+f["q3_other_noncurrent_financial_asset"]+f["q3_investment_property"])*e["other_asset_realization_factor"]
    financial_liability = f["q3_trading_financial_liability"]+f["q3_derivative_financial_liability"]
    ordinary = f["q3_short_debt"]+f["q3_long_debt"]+f["q3_bonds"]+f["q3_current_noncurrent_debt"]+e["short_notes"]-e["current_lease"]-e["cb_carrying_in_current"]
    lease = f["q3_long_lease"]+e["current_lease"]
    nonlease_book = f["q3_fixed"]+f["q3_cip"]+f["q3_intangible"]+f["q3_deferred_cost"]
    lease_book = f["q3_rou"]
    sales = {x["name"]: x["normal_cutoff_sales"] for x in b["segments"]}
    total_sales = sum(sales.values())
    da = nonlease_book*b["nonlease_da_rate"]+lease_book*b["lease_da_rate"]
    gross = sum(x["normal_cutoff_sales"]*x["margin_start"] for x in b["segments"])
    ebit = gross-total_sales*b["cash_opex_ratio_start"]
    cash_expenses = total_sales-ebit-da+max(ebit, 0.0)*b["tax_rate"]
    cmin = cash_expenses*b["minimum_cash_days"]/365.0
    op_current_other_liability = f["q3_other_current_liabilities"]-e["short_notes"]
    nwc = (f["q3_receivables"]+f["q3_inventory"]+f["q3_operating_prepay"]+f["q3_notes_receivable"]
           +f["q3_receivable_finance"]+f["q3_contract_asset"]+f["q3_other_receivables"]+e["other_current_nonfinancial"]
           -f["q3_payables"]-f["q3_notes_payable"]-f["q3_contract_liability"]-f["q3_payroll_payable"]
           -f["q3_tax_payable"]-legacy["operating_other_payables"]-op_current_other_liability+transfer_nwc)
    weights = ownership_weights(inputs, patch)
    pools = {}
    for name, w in weights.items():
        pools[name] = {"cash": f["q3_cash"]*w["financial_share"]+e["october_unknown_net_operating_cash"]*w["operating_share"]
                       +(e["october_options_exercised"]*e["october_option_price"]-f["known_h1_dividend_total"] if name == "common" else 0.0), "restricted_cash": restricted_cash*w["financial_share"],
                       "free_deposits": (deposits-pledged)*w["financial_share"], "pledged_deposits": pledged*w["financial_share"],
                       "other_financial": other_fin*w["financial_share"],
                       "financial_receivable": f["q3_derivative_asset"]*w["financial_share"],
                       "financial_settlement_liability": financial_liability*w["financial_share"],
                       "legacy_dividend_payable": legacy["legacy_"+name],
                       "ordinary_debt": ordinary*w["ordinary_debt_share"],
                       "lease_debt": lease*w["operating_share"], "cb_economic_debt": cb_value if name == "common" else 0.0,
                       "minimum_cash": cmin*w["operating_share"]}
    near(sum(x["cash"] for x in pools.values()), cash, "September to October cash total")
    lots = copy.deepcopy(inputs["securities"]["options"])
    for lot in lots:
        if lot["name"] == "2025":
            lot["remaining"] -= e["october_options_exercised"]
    parent = {"cash": e["parent_oct_cash_before_q3_payment"],
              "retained_earnings": f["parent_q3_re_before_q3_declaration"]-f["q3_declared_dividend"],
              "statutory_reserve": f["parent_statutory_reserve"],
              "dividend_receivable": f["parent_h1_dividend_receivable"],
              "ordinary_dividend_payable": f["q3_declared_dividend"]}
    return {"year": 0, "sales": sales, "total_sales": total_sales, "ebit": ebit,
            "nopat": ebit*(1-b["tax_rate"]), "da": da, "cash_like_nopat": ebit*(1-b["tax_rate"]),
            "book_nonlease": nonlease_book, "book_lease": lease_book, "economic_capital": nonlease_book+lease_book, "capacity_sales": total_sales,
            "cash_opex": total_sales*b["cash_opex_ratio_start"],
            "cash_research_and_development": total_sales*b["rd_cash_ratio_in_total_opex"],
            "capital_turnover": total_sales/(nonlease_book+lease_book),
            "capital_prepaid": e["capital_prepaid"]+e["acquisition_prepaid_to_productive_capital"]+transfer_cap,
            "capital_payable": e["capital_payable"], "nwc": nwc, "minimum_cash": cmin,
            "nwc_days": nwc/total_sales*365.0, "pools": pools, "parent": parent, "weights": weights,
            "issued": issued, "treasury": f["treasury_shares"], "outstanding": issued-f["treasury_shares"],
            "lots": lots, "cb_face": cb_face, "cb_conversion_price": f["cb_conversion_price"],
            "cb_mode": patch.get("cb_mode", inputs["finance"]["cb_base"]),
            "normal_cutoff_sales": total_sales, "normal_cutoff_nopat": ebit*(1-b["tax_rate"]),
            "initial_nwc_days": nwc/total_sales*365.0,
            "opening_bridge": {"legacy_distribution_bridge": legacy, "financial_liability_to_settle": financial_liability,
                               "reported_q3_cash": f["q3_cash"], "h1_paid_by_cutoff_budget": f["known_h1_dividend_total"],
                               "oct_option_cash": e["october_options_exercised"]*e["october_option_price"],
                               "oct_other_cash_budget": e["october_unknown_net_operating_cash"],
                               "oct_cb_shares_budget": oct_cb_shares, "cb_carrying_removed_from_current": e["cb_carrying_in_current"],
                               "cb_economic_redemption_claim": cb_value,
                               "financial_reclassified_to_nwc": transfer_nwc, "financial_reclassified_to_capital_prepay": transfer_cap}}


def operation_step(inputs, previous, year, growth_scale, patch, terminal=False):
    b = inputs["business"]
    g = b["terminal_growth"]
    path = inputs.get("business_paths", {}).get(patch.get("business_path"), {})
    segments, sales, gross = [], {}, 0.0
    for seg in b["segments"]:
        if year <= 3:
            planned_growth = seg["growth_first3"][year-1]
        else:
            planned_growth = fade(seg["growth_first3"][-1], g, year-3, b["growth_mature_year"]-3)
        overrides = path.get("growth_overrides", {}).get(seg["name"], [])
        if year <= len(overrides):
            planned_growth = overrides[year-1]
        realized_growth = planned_growth*growth_scale if planned_growth > 0 else planned_growth
        revenue = previous["sales"][seg["name"]]*(1+realized_growth)
        margin = fade(seg["margin_start"], seg["margin_mature"], year, b["growth_mature_year"])
        margin += path.get("permanent_margin_deltas", {}).get(seg["name"], 0.0)
        temporary = path.get("temporary_margin_deltas", {}).get(seg["name"], [])
        if year <= len(temporary):
            margin += temporary[year-1]
        sales[seg["name"]] = revenue
        gross += revenue*margin
        segments.append({"name": seg["name"], "sales": revenue, "gross_margin": margin,
                         "planned_growth": planned_growth, "actual_growth": realized_growth})
    total = sum(sales.values())
    opex_ratio = fade(b["cash_opex_ratio_start"], b["cash_opex_ratio_mature"], year, b["growth_mature_year"])
    opex_ratio += path.get("cash_opex_ratio_delta", 0.0)
    cash_opex = total*opex_ratio
    fixed_floors = path.get("opex_floor_to_previous_by_year", [])
    if year <= len(fixed_floors):
        cash_opex = max(cash_opex, previous["cash_opex"]*fixed_floors[year-1])
    rd_ratio = path.get("rd_cash_ratio_override") or b["rd_cash_ratio_in_total_opex"]
    cash_rd = total*rd_ratio
    rd_floors = path.get("rd_floor_to_previous_by_year", [])
    if year <= len(rd_floors):
        cash_rd = max(cash_rd, previous["cash_research_and_development"]*rd_floors[year-1])
    cash_opex = max(cash_opex, cash_rd)
    sbc = b["existing_sbc_expense"][year-1] if year <= len(b["existing_sbc_expense"]) else 0.0
    treasury_service = inputs["facts"]["treasury_cost"] if year == inputs["securities"]["treasury_release_year"] and previous["treasury"] > EPS else 0.0
    sbc += treasury_service
    ebit = gross-cash_opex-sbc
    tax = max(ebit, 0.0)*b["tax_rate"]
    nopat = ebit-tax
    da_nonlease = previous["book_nonlease"]*b["nonlease_da_rate"]
    da_lease = previous["book_lease"]*b["lease_da_rate"]
    da = da_nonlease+da_lease
    maintenance = da*b["maintenance_factor"]
    capacity = capacity_investment(total, previous["capacity_sales"],
                                   previous["capital_turnover"]*path.get("marginal_capital_turnover_factor", 1.0))
    growth_capital = capacity["growth_capital"]
    delivered = maintenance+growth_capital
    new_lease = delivered*b["new_capital_lease_share"]
    new_prepay = (delivered-new_lease)*b["new_capital_prepay_ratio"]
    cap = capital_cash(delivered, new_lease, previous["capital_prepaid"], new_prepay, previous["capital_payable"], 0.0)
    days = b["normal_nwc_days"] + (previous["initial_nwc_days"]-b["normal_nwc_days"])*max(0.0, 1.0-year/b["nwc_transition_years"])
    days += patch.get("nwc_extra_days", 0.0)+path.get("nwc_permanent_extra_days", 0.0)
    temp_days = path.get("nwc_extra_days_by_year", [])
    if year <= len(temp_days):
        days += temp_days[year-1]
    nwc = total*days/365.0
    cash_cost = total-ebit-da-sbc+tax
    if cash_cost < -EPS:
        raise ValueError("negative cash operating cost")
    cmin = cash_cost*b["minimum_cash_days"]/365.0
    fcff = nopat+da+sbc-cap["financing_neutral_investment"]-(nwc-previous["nwc"])-(cmin-previous["minimum_cash"])
    book_nonlease = previous["book_nonlease"]+delivered-new_lease-da_nonlease
    book_lease = previous["book_lease"]+new_lease-da_lease
    economic = previous["economic_capital"]+delivered-maintenance
    near(economic, previous["economic_capital"]+growth_capital, "economic productive capital")
    return {"year": year, "sales": sales, "segments": segments, "total_sales": total, "gross_profit": gross,
            "cash_opex_ratio": cash_opex/total, "cash_opex": cash_opex,
            "cash_research_and_development": cash_rd,
            "cash_other_operating_expenses": cash_opex-cash_rd,
            "sbc_noncash": sbc, "treasury_service_expense": treasury_service,
            "ebit": ebit, "unlevered_operating_cash_tax": tax, "nopat": nopat,
            "cash_like_nopat": nopat+sbc, "da": da, "nonlease_da": da_nonlease, "lease_da": da_lease,
            "maintenance_capital": maintenance, "growth_capital": growth_capital, "capital": cap,
            "book_nonlease": book_nonlease, "book_lease": book_lease, "economic_capital": economic,
            "capital_turnover": previous["capital_turnover"], "capacity_sales": capacity["capacity_sales_end"],
            "capacity_investment": capacity, "capacity_utilization": total/capacity["capacity_sales_end"],
            "business_path": patch.get("business_path", "base"), "capital_prepaid": cap["prepaid_end"], "capital_payable": 0.0,
            "nwc": nwc, "nwc_days": days, "nwc_increment": nwc-previous["nwc"],
            "minimum_cash": cmin, "minimum_cash_increment": cmin-previous["minimum_cash"],
            "cash_operating_cost_including_tax": cash_cost, "fcff": fcff,
            "growth_scale": growth_scale, "terminal": terminal,
            "initial_nwc_days": previous["initial_nwc_days"],
            "normal_cutoff_sales": previous["normal_cutoff_sales"], "normal_cutoff_nopat": previous["normal_cutoff_nopat"]}


def parent_budget(inputs, previous_parent, common_profit, group_available_cash, operating_index, year, patch, legacy_payment=0.0):
    p = inputs["parent"]
    declared = min(max(0.0, p["annual_sub_dividend_anchor"]*operating_index),
                   max(0.0, common_profit)*p["declared_cap_fraction_common_profit"], max(group_available_cash, 0.0))
    lag = patch.get("parent_lag", p["collection_lag_fraction"])
    received_desired = previous_parent["dividend_receivable"]+declared*(1-lag)
    received = min(received_desired, max(group_available_cash, 0.0))
    receivable_end = previous_parent["dividend_receivable"]+declared-received
    own_cash = p["own_cash_after_finance_tax"]*operating_index+p["net_internal_working_funding"]
    cash_before_D = previous_parent["cash"]+received+own_cash-legacy_payment
    ni = declared+p["own_net_profit"]*operating_index
    reserve = max(0.0, ni)*p["reserve_rate"]
    # Actual continue-extraction policy; no automatic can-stop threshold switch.
    re_before_new_D = previous_parent["retained_earnings"]+ni-reserve
    mother_min = p["minimum_cash"]*operating_index
    payable = previous_parent["ordinary_dividend_payable"]
    if cash_before_D+EPS < mother_min+payable:
        raise EconomicInfeasible("mother_cash_cannot_meet_known_dividend_and_buffer", {
            "year": year, "cash_before_D": cash_before_D, "minimum": mother_min, "known_payable": payable,
            "upstream_received": received, "receivable_end": receivable_end})
    target_optional = max(0.0, common_profit)*p["common_payout_ratio"]
    optional = min(target_optional, max(re_before_new_D, 0.0), max(cash_before_D-mother_min-payable, 0.0))
    return {"cash_before_D": cash_before_D, "minimum_cash": mother_min, "upstream_declared": declared,
            "upstream_actual_cash": received, "dividend_receivable_end": receivable_end,
            "own_cash_net": own_cash, "legacy_payment_to_old_rights": legacy_payment, "net_profit": ni, "statutory_extraction": reserve,
            "statutory_reserve_end": previous_parent["statutory_reserve"]+reserve,
            "retained_earnings_before_new_D": re_before_new_D,
            "known_dividend_payable": payable, "target_optional_D": target_optional,
            "optional_after_mother_constraints": optional,
            "desired_total_D": payable+optional}


def funding_step(inputs, previous, operation, assoc_row, year, patch):
    finance = inputs["finance"]
    w = previous["weights"]
    pools, pool_records = {}, {}
    pre = {}
    for name, old in previous["pools"].items():
        share = w[name]["operating_share"]
        min_cash = operation["minimum_cash"]*share
        interest = old["ordinary_debt"]*finance["ordinary_interest_rate"]+old["lease_debt"]*finance["lease_interest_rate"]
        usable_shield = min(interest*finance["interest_shield_rate"], max(operation["unlevered_operating_cash_tax"]*share, 0.0))
        fin_base = max(0.0, old["cash"]-old["restricted_cash"]-old["minimum_cash"])+old["free_deposits"]+old["pledged_deposits"]
        fin_gross = fin_base*finance["financial_cash_yield"]
        fin_net = fin_gross*(1-finance["financial_tax_rate"])
        lease_repay = min(old["lease_debt"], old["lease_debt"]*finance["lease_principal_rate"])
        lease_add = operation["capital"]["noncash_lease_addition"]*share
        cb_cash = old["cb_economic_debt"] if year == 1 and previous["cb_mode"] == "cash" and name == "common" else 0.0
        cb_non_cash = old["cb_economic_debt"] if year == 1 and previous["cb_mode"] == "convert" and name == "common" else 0.0
        financial_asset_cash = old.get("financial_receivable", 0.0)
        financial_liability_cash = old.get("financial_settlement_liability", 0.0)
        legacy_dividend_cash = old.get("legacy_dividend_payable", 0.0)
        gross_maturity = old["ordinary_debt"]*finance["ordinary_maturity_fraction_per_year"]
        rolled = gross_maturity  # Only still-outstanding principal; never resurrect prior repayment.
        baseline = cash_bridge(operation["fcff"]*share, operation["minimum_cash_increment"]*share,
                               interest, usable_shield, finance["cash_tax_timing_increment"]*share,
                               fin_net, assoc_row["cash_received"]*w[name]["associate_share"],
                               noncash_lease_addition=lease_add, debt_new_cash=rolled,
                               debt_repayment_cash=gross_maturity+lease_repay+cb_cash,
                               financial_redemption=financial_asset_cash,
                               financial_liability_settlement=financial_liability_cash,
                               legacy_dividend_settlement=legacy_dividend_cash)
        profit = (operation["nopat"]*share-interest+usable_shield+fin_net+assoc_row["earnings"]*w[name]["associate_share"])
        pre[name] = {"old": old, "raw_bridge": baseline, "raw_change": baseline["change_in_cash"],
                     "profit": profit, "interest": interest, "shield": usable_shield,
                     "financial_income_gross": fin_gross, "financial_income_net": fin_net,
                     "lease_repaid": lease_repay, "lease_added_noncash": lease_add,
                     "lease_debt_end": old["lease_debt"]+lease_add-lease_repay,
                     "cb_cash_paid": cb_cash, "cb_noncash_equity_conversion": cb_non_cash,
                     "cb_debt_end": old["cb_economic_debt"]-cb_cash-cb_non_cash,
                     "ordinary_maturities": gross_maturity, "ordinary_rollovers": rolled,
                     "financial_receivable_cash_settled": financial_asset_cash,
                     "financial_liability_cash_settled": financial_liability_cash,
                     "legacy_dividend_cash_settled": legacy_dividend_cash, "internal_support_cash": 0.0,
                     "minimum_cash": min_cash}
    common = pre["common"]
    support_cap = patch.get("cash_support_cap", inputs["ownership"]["annual_common_cash_support_cap"])
    common_spare = max(0.0, common["old"]["cash"]+common["raw_change"]+common["old"]["free_deposits"]
                       -common["minimum_cash"]-common["old"]["restricted_cash"]-previous["parent"]["ordinary_dividend_payable"])
    remaining_support = min(support_cap, common_spare)
    for name in ("likai", "other_nci"):
        item = pre[name]
        gap = max(0.0, item["minimum_cash"]+item["old"]["restricted_cash"]
                  -item["old"]["cash"]-item["raw_change"]-item["old"]["free_deposits"])
        support = min(gap, remaining_support)
        item["raw_change"] += support
        item["raw_bridge"]["components"]["group_internal_support_transfer"] += support
        item["raw_bridge"]["change_in_cash"] += support
        item["internal_support_cash"] = support
        common["raw_change"] -= support
        common["raw_bridge"]["components"]["group_internal_support_transfer"] -= support
        common["raw_bridge"]["change_in_cash"] -= support
        common["internal_support_cash"] -= support
        remaining_support -= support
        if gap > support+EPS:
            raise EconomicInfeasible("ownership_pool_liquidity_failure_under_frozen_cash_access_bound", {
                "year": year, "pool": name, "unfunded_gap": gap-support,
                "annual_support_cap": support_cap, "available_common_liquidity_before_support": common_spare,
                "scope": "this assumed funds-access budget, not proof whole company is intrinsically unfinanceable"})
    available = (common["old"]["cash"]+common["raw_change"]+common["old"]["free_deposits"]
                 -common["minimum_cash"]-common["old"]["restricted_cash"])
    pbudget = parent_budget(inputs, previous["parent"], common["profit"], available,
                            max(0.0, operation["cash_like_nopat"]/previous["normal_cutoff_nopat"]), year, patch,
                            legacy_payment=common["legacy_dividend_cash_settled"])
    for name, data in pre.items():
        old = data["old"]
        if name == "common":
            desired, mandatory = pbudget["desired_total_D"], pbudget["known_dividend_payable"]
        else:
            desired, mandatory = max(0.0, data["profit"])*w[name]["nci_payout"], 0.0
        allocation = fund_pool(old["cash"], data["minimum_cash"], old["restricted_cash"], old["free_deposits"],
                               desired, mandatory, data["raw_change"], old["ordinary_debt"], min(old["ordinary_debt"], old["pledged_deposits"]))
        pools[name] = {"cash": allocation["cash_end"], "restricted_cash": old["restricted_cash"],
                       "free_deposits": allocation["free_deposits_end"], "pledged_deposits": old["pledged_deposits"],
                       "other_financial": old["other_financial"], "financial_receivable": 0.0,
                       "financial_settlement_liability": 0.0, "legacy_dividend_payable": 0.0,
                       "ordinary_debt": allocation["ordinary_debt_end"],
                       "lease_debt": data["lease_debt_end"], "cb_economic_debt": data["cb_debt_end"],
                       "minimum_cash": data["minimum_cash"]}
        bridge = copy.deepcopy(data["raw_bridge"])
        c = bridge["components"]
        c["financial_principal_redeemed"] += allocation["financial_redemption"]
        c["financial_principal_purchased"] -= allocation["financial_purchase"]
        c["debt_cash_repaid"] -= allocation["ordinary_voluntary_repayment"]
        c["common_cash_distributed" if name == "common" else "nci_cash_distributed"] -= allocation["distribution_paid"]
        bridge["change_in_cash"] = sum(c.values())
        near(old["cash"]+bridge["change_in_cash"], pools[name]["cash"], name+" final cash")
        near(old["ordinary_debt"]-allocation["ordinary_voluntary_repayment"], pools[name]["ordinary_debt"], name+" ordinary debt")
        near(old["lease_debt"]+data["lease_added_noncash"]-data["lease_repaid"], pools[name]["lease_debt"], name+" lease debt")
        near(old.get("financial_receivable", 0.0), data["financial_receivable_cash_settled"]+pools[name]["financial_receivable"], name+" financial asset settlement")
        near(old.get("financial_settlement_liability", 0.0), data["financial_liability_cash_settled"]+pools[name]["financial_settlement_liability"], name+" financial liability settlement")
        near(old.get("legacy_dividend_payable", 0.0), data["legacy_dividend_cash_settled"]+pools[name]["legacy_dividend_payable"], name+" legacy dividend liability")
        pool_records[name] = {**{k: v for k, v in data.items() if k not in ("old", "raw_bridge")},
                              "cash_begin": old["cash"], "debt_begin": old["ordinary_debt"]+old["lease_debt"]+old["cb_economic_debt"],
                              "allocation": allocation, "cash_bridge": bridge, "end": copy.deepcopy(pools[name])}
    paid = pool_records["common"]["allocation"]["distribution_paid"]
    optional_paid = paid-pbudget["known_dividend_payable"]
    mother_cash = pbudget["cash_before_D"]-paid
    # Excess mother funds may move within common-owned pool; this is not group expense/income.
    legal_parent_cash_cap = pbudget["minimum_cash"] + max(0.0, pools["common"]["cash"]-pools["common"]["restricted_cash"]-pools["common"]["minimum_cash"])
    downstream = max(0.0, mother_cash-legal_parent_cash_cap)
    mother_cash -= downstream
    if mother_cash > pools["common"]["cash"]-pools["common"]["restricted_cash"]+EPS:
        raise EconomicInfeasible("mother_cash_location_exceeds_common_available_cash", {"year": year})
    parent = {"cash": mother_cash, "retained_earnings": pbudget["retained_earnings_before_new_D"]-optional_paid,
              "statutory_reserve": pbudget["statutory_reserve_end"], "dividend_receivable": pbudget["dividend_receivable_end"],
              "ordinary_dividend_payable": 0.0}
    near(previous["parent"]["retained_earnings"]+pbudget["net_profit"]-pbudget["statutory_extraction"]-optional_paid,
         parent["retained_earnings"], "mother RE known dividend already declared")
    pbudget.update(statutory_threshold_reference=previous["issued"]*inputs["parent"]["reserve_cap_fraction"],
                   continued_extraction_is_budget_not_post_threshold_legal_requirement=True,
                   actual_total_D=paid, actual_optional_D=optional_paid, cash_end=mother_cash,
                   downstream_internal_transfer=downstream, retained_earnings_end=parent["retained_earnings"],
                   ordinary_dividend_payable_end=0.0)
    group = {"cash_begin": sum(x["cash"] for x in previous["pools"].values()),
             "cash_end_before_employee_cash": sum(x["cash"] for x in pools.values()),
             "ordinary_debt_end": sum(x["ordinary_debt"] for x in pools.values()),
             "lease_debt_end": sum(x["lease_debt"] for x in pools.values()),
             "cb_debt_end": sum(x["cb_economic_debt"] for x in pools.values()),
             "nci_dividends": sum(pool_records[n]["allocation"]["distribution_paid"] for n in ("likai", "other_nci")),
             "common_dividend": paid, "parent_upstream_is_group_internal": True,
             "nci_external_capital_injection": 0.0, "outside_new_acquisitions": 0.0,
             "group_internal_support_net": sum(x["internal_support_cash"] for x in pre.values()),
             "legacy_dividends_to_old_rights": sum(x["legacy_dividend_cash_settled"] for x in pre.values()),
             "financial_liabilities_settled": sum(x["financial_liability_cash_settled"] for x in pre.values()),
             "cash_change_before_employee_cash": sum(x["cash_bridge"]["change_in_cash"] for x in pool_records.values())}
    near(group["group_internal_support_net"], 0.0, "internal support no new group cash")
    near(group["cash_begin"]+group["cash_change_before_employee_cash"], group["cash_end_before_employee_cash"], "all pools group cash")
    return pools, parent, pool_records, pbudget, group


def economic_path(inputs, patch, hints, assoc, progress=None):
    start = initial_state(inputs, patch)
    rows = [start]
    replan_log = []
    for year in range(1, inputs["horizon"]+1):
        previous = rows[-1]
        feasible = None
        failures = []
        for scale in inputs["business"]["growth_replan_scales"]:
            op = operation_step(inputs, previous, year, scale, patch)
            try:
                funding = funding_step(inputs, previous, op, assoc[year], year, patch)
                feasible = (op, funding)
                break
            except EconomicInfeasible as exc:
                failures.append({"growth_scale": scale, "reason": exc.reason, "details": exc.details})
        if feasible is None:
            raise EconomicInfeasible("operating_or_funding_path_infeasible_after_optional_D_and_cancellable_growth_replan", {
                "year": year, "attempted_growth_scales": failures,
                "last_feasible_year": year-1, "partial_years": rows})
        op, (pools, parent, pool_records, pbudget, group) = feasible
        if failures:
            replan_log.append({"year": year, "rejected_plans": failures, "accepted_scale": op["growth_scale"],
                               "effect": "this year sales/capital reduced; all subsequent states restart from reduced capacity/sales"})
        issued, treasury = previous["issued"], previous["treasury"]
        cb_shares = 0.0
        if year == 1 and previous["cb_mode"] == "convert":
            cb_shares = previous["cb_face"]/previous["cb_conversion_price"]
            issued += cb_shares
        eligible_shares = issued-treasury
        dividend_per_share = group["common_dividend"]/eligible_shares
        lots, opt = option_step(previous["lots"], year, dividend_per_share, hints[year])
        released = treasury if year == inputs["securities"]["treasury_release_year"] else 0.0
        treasury -= released
        issued += opt["shares_issued"]
        pools["common"]["cash"] += opt["cash_received"]
        parent["cash"] += opt["cash_received"]
        group["employee_exercise_cash"] = opt["cash_received"]
        group["cash_end"] = sum(p["cash"] for p in pools.values())
        near(group["cash_begin"]+group["cash_change_before_employee_cash"]+opt["cash_received"], group["cash_end"], "group cash after employee cash")
        row = {**op, "pools": pools, "parent": parent, "pool_cash_records": pool_records,
               "parent_cash_record": pbudget, "group_cash_record": group, "weights": previous["weights"],
               "issued": issued, "treasury": treasury, "outstanding": issued-treasury,
               "dividend_eligible_shares": eligible_shares, "common_distribution_per_share": dividend_per_share,
               "employee_options": opt, "treasury_released": released, "cb_shares_issued": cb_shares,
               "lots": lots, "cb_face": previous["cb_face"], "cb_conversion_price": previous["cb_conversion_price"],
               "cb_mode": previous["cb_mode"], "associate": assoc[year]}
        near(row["outstanding"], previous["outstanding"]+cb_shares+opt["shares_issued"]+released, "ordinary share bridge")
        rows.append(row)
        if progress:
            progress({"phase": "year_budget", "year": year, "sales": row["total_sales"], "fcff": row["fcff"],
                      "cash_end": group["cash_end"], "debt_end": group["ordinary_debt_end"]+group["lease_debt_end"]+group["cb_debt_end"],
                      "D": group["common_dividend"], "growth_scale": row["growth_scale"], "state": row})
    terminal = operation_step(inputs, rows[-1], inputs["horizon"]+1, 1.0, patch, terminal=True)
    if terminal["growth_capital"] <= 0 or terminal["nwc_increment"] < -EPS or terminal["minimum_cash_increment"] < -EPS:
        raise ArithmeticError("positive terminal growth without corresponding capital")
    last_assoc = assoc[-1]
    ke, g = inputs["associates"]["equity_cost"], inputs["business"]["terminal_growth"]
    next_earnings = last_assoc["book_end"]*ke
    next_declared = next_earnings*(1-g/ke)
    next_assoc = {"earnings": next_earnings,
                  "cash_received": last_assoc["receivable_end"]+next_declared*(1-inputs["associates"]["collection_lag_fraction"])}
    _, _, terminal_pools, terminal_parent, terminal_group = funding_step(inputs, rows[-1], terminal, next_assoc,
                                                                       inputs["horizon"]+1, patch)
    terminal["positive_growth_funding_preview"] = {"group": terminal_group, "parent": terminal_parent,
                                                   "pools": terminal_pools}
    return rows, terminal, replan_log


def pool_financial_value(pool):
    return pool["cash"]-pool["minimum_cash"]+pool["free_deposits"]+pool["pledged_deposits"]+pool["other_financial"]+pool.get("financial_receivable", 0.0)


def pool_debt_value(pool, remove_cb=False):
    return (pool["ordinary_debt"]+pool["lease_debt"]+(0.0 if remove_cb else pool["cb_economic_debt"])
            +pool.get("financial_settlement_liability", 0.0)+pool.get("legacy_dividend_payable", 0.0))


def valuation_path(inputs, rows, terminal, assoc, wacc, auxiliary=False, patch=None):
    patch = patch or {}
    n, g = inputs["horizon"], inputs["business"]["terminal_growth"]
    ke = inputs["associates"]["equity_cost"]
    fcffs = [r["fcff"] for r in rows[1:]]
    raw = []
    for at, state in enumerate(rows):
        if auxiliary:
            capital = state["economic_capital"]+state["nwc"]+state["minimum_cash"]+state["capital_prepaid"]
            normal = state["cash_like_nopat"]
            roic = normal/capital if capital > 0 else 0.0
            # Unlike PE, this is before interest and NCI; ongoing growth needs capital.
            reinvestment = g*capital
            normal_fcff = normal*(1+g)-reinvestment
            ev = {"value": normal_fcff/(wacc-g), "normal_cash_like_nopat": normal,
                  "normalized_capital": capital, "normal_return_on_capital": roic,
                  "steady_growth_reinvestment": reinvestment, "normal_fcff": normal_fcff,
                  "terminal_pv_fraction": 1.0}
        else:
            ev = enterprise_value(fcffs, terminal["fcff"], g, wacc, at)
        av = associate_value(assoc, at, ke, g, inputs["associates"]["collection_lag_fraction"],
                             inputs["associates"]["receivable_wait_discount_rate"])
        fin = sum(pool_financial_value(p) for p in state["pools"].values())
        remove_cb = at == 0 and state["cb_mode"] == "convert"
        debt = sum(pool_debt_value(p, remove_cb=(remove_cb and name == "common")) for name, p in state["pools"].items())
        nci = {}
        for name in ("likai", "other_nci"):
            w = state["weights"][name]
            p = state["pools"][name]
            nci[name] = {"operating_ev": ev["value"]*w["operating_share"],
                         "financial_assets": pool_financial_value(p), "associate_value": av["value"]*w["associate_share"],
                         "debt": pool_debt_value(p)}
            boundary = nci_boundary(nci[name]["operating_ev"]+nci[name]["financial_assets"]+nci[name]["associate_value"],
                                    nci[name]["debt"], patch.get("nci_recourse_fraction", inputs["ownership"]["nci_recourse_fraction"]))
            nci[name]["boundary"] = boundary
            nci[name]["equity_value"] = boundary["nci_equity_after_boundary"]
        creditor_loss = sum(x["boundary"]["external_creditor_recovery_loss"] for x in nci.values())
        common_recourse = sum(x["boundary"]["common_group_recourse_obligation"] for x in nci.values())
        debt_before_boundary = debt
        debt -= creditor_loss
        payable = state["parent"]["ordinary_dividend_payable"]
        bridge = equity_bridge(ev["value"], fin, av["value"], debt, sum(x["equity_value"] for x in nci.values()), payable, payable)
        denominator = state["outstanding"]
        if remove_cb:
            denominator += state["cb_face"]/state["cb_conversion_price"]
        raw.append({"year": at, "operating": ev, "associate": av, "nci": nci,
                    "bridge": bridge, "debt_before_recourse_boundary": debt_before_boundary,
                    "creditor_recovery_loss_bound": creditor_loss, "common_group_recourse_obligation_bound": common_recourse,
                    "valuation_diagnostic_status": "NCI_SCOPE_BOUNDARY_USED" if any(x["boundary"]["status"] != "RAW_NCI_NONNEGATIVE" for x in nci.values()) else "NO_NCI_BOUNDARY_NEEDED",
                    "shares_for_current_holders_and_committed_cb": denominator})
    # Price the unissued employee claim only for awards still unissued at each valuation time.
    # Current denominator does NOT simultaneously include those future shares. After issuance,
    # no old claim is deducted again; Y5 uses actual issued shares and only any remaining awards.
    out = [None]*(n+1)
    for at in range(n, -1, -1):
        option_claim = treasury_claim = 0.0
        for future in range(at+1, n+1):
            price = out[future]["per_share"]
            for lot in rows[future]["employee_options"]["lots"]:
                option_claim += lot["exercised"]*max(0.0, price-lot["strike"])/(1+ke)**(future-at)
            treasury_claim += rows[future]["treasury_released"]*max(0.0, price)/(1+ke)**(future-at)
        item = raw[at]
        item["bridge"]["unissued_employee_claim"] = option_claim+treasury_claim
        item["bridge"]["ordinary_holder_equity"] -= option_claim+treasury_claim
        item["unissued_option_claim"] = option_claim
        item["unissued_treasury_employee_claim"] = treasury_claim
        item["per_share"] = item["bridge"]["ordinary_holder_equity"]/item["shares_for_current_holders_and_committed_cb"]
        out[at] = item
    return out


def validate_inputs(inputs):
    if inputs["amount_unit"] != "CNY billion" or inputs["share_unit"] != "billion shares":
        raise ValueError("unit contract mismatch")
    if inputs["horizon"] < inputs["associates"]["old_fade_years"]+inputs["associates"]["cohort_fade_years"]+1:
        raise ValueError("horizon truncates associate cohort tails")
    if inputs["horizon"] > 20:
        raise ValueError("unplanned excessive horizon")
    g = inputs["business"]["terminal_growth"]
    if not 0 < g < min(inputs["valuation"]["wacc_low"], inputs["associates"]["equity_cost"]):
        raise ValueError("invalid growth/cost relation")
    if inputs["finance"]["financial_asset_credit_loss"] != 0:
        raise ValueError("nonzero credit loss needs explicit asset/income/writeoff path")
    path_keys = {"mechanism", "source_anchor", "growth_overrides", "temporary_margin_deltas",
                 "permanent_margin_deltas", "nwc_extra_days_by_year", "nwc_permanent_extra_days",
                 "opex_floor_to_previous_by_year", "rd_floor_to_previous_by_year",
                 "marginal_capital_turnover_factor", "cash_opex_ratio_delta", "rd_cash_ratio_override"}
    names = {x["name"] for x in inputs["business"]["segments"]}
    for name, path in inputs.get("business_paths", {}).items():
        unknown_path_keys = set(path)-path_keys
        if unknown_path_keys:
            raise ValueError("unknown operating path parameters: "+name+repr(sorted(unknown_path_keys)))
        for field in ("growth_overrides", "temporary_margin_deltas", "permanent_margin_deltas"):
            if set(path.get(field, {}))-names:
                raise ValueError("unknown operating segment in "+name)
    for opt in inputs["securities"]["options"]:
        near(sum(opt["vesting_weights"]), 1.0, "option vesting weights")
        if opt["expiry_year"] < len(opt["vesting_weights"]):
            raise ValueError("vesting after expiry")
    for scale in inputs["business"]["growth_replan_scales"]:
        if not 0 <= scale <= 1:
            raise ValueError("invalid growth replan")
    if inputs["business"]["growth_replan_scales"][-1] != 0:
        raise ValueError("must identify zero-cancellable-growth funding limit")


def compute_case(inputs, case, progress=None):
    validate_inputs(inputs)
    patch = case["patch"]
    allowed = {"nwc_extra_days", "financial_to_nwc", "financial_to_capital_prepay", "extra_restricted_deposits",
               "associate_earnings_factor", "nci_claims_factor", "parent_lag", "cb_mode", "business_path",
               "nci_recourse_fraction", "cash_support_cap"}
    unknown = set(patch)-allowed
    if unknown:
        raise ValueError("unknown case patch keys: "+repr(sorted(unknown)))
    if "business_path" in patch and patch["business_path"] not in inputs.get("business_paths", {}):
        raise ValueError("unknown operating path")
    assoc = associate_schedule(inputs["associates"], inputs["facts"]["q3_associate_book"],
                               inputs["business"]["terminal_growth"], inputs["horizon"], patch.get("associate_earnings_factor", 1.0))
    hints = [0.0]*(inputs["horizon"]+1)
    old_signature = None
    iterations = []
    stable = None
    for iteration in range(1, inputs["securities"]["max_option_iterations"]+1):
        if progress:
            progress({"phase": "option_iteration_start", "iteration": iteration})
        rows, terminal, replans = economic_path(inputs, patch, hints, assoc, progress)
        midpoint = valuation_path(inputs, rows, terminal, assoc, inputs["valuation"]["wacc_mid"], patch=patch)
        signature = tuple(tuple((lot["name"], round(lot["exercised"], 12)) for lot in row["employee_options"]["lots"]) for row in rows[1:])
        iterations.append({"iteration": iteration, "exercise_plan_by_year_and_lot": list(signature),
                           "midpoint_current_per_share": midpoint[0]["per_share"]})
        if signature == old_signature:
            stable = (rows, terminal, replans, midpoint)
            break
        old_signature = signature
        hints = [x["per_share"] for x in midpoint]
    if stable is None:
        raise RuntimeError("option intrinsic/funding fixed point did not converge; numerical failure, not economic null")
    rows, terminal, replans, midpoint = stable
    lower = valuation_path(inputs, rows, terminal, assoc, inputs["valuation"]["wacc_high"], patch=patch)
    upper = valuation_path(inputs, rows, terminal, assoc, inputs["valuation"]["wacc_low"], patch=patch)
    auxiliary = valuation_path(inputs, rows, terminal, assoc, inputs["valuation"]["wacc_mid"], auxiliary=True, patch=patch)
    for at in (0, 5):
        if lower[at]["per_share"] > upper[at]["per_share"]+EPS:
            raise ArithmeticError("core WACC endpoints inverted")
    disparity = auxiliary[0]["per_share"]/midpoint[0]["per_share"]-1 if midpoint[0]["per_share"] else None
    return_model = {"schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "CNY",
                    "model_as_of": inputs["information_cutoff"],
                    "base_case_distributions_per_share": [row["common_distribution_per_share"] for row in rows[1:6]],
                    "base_case_terminal_equity_value_range_per_share": {"year_5": [lower[5]["per_share"], upper[5]["per_share"]]}}
    result = {"case_id": case["id"], "kind": case["kind"], "status": "FEASIBLE",
              "patch": patch, "unit": "CNY billion, shares billion, per-share CNY",
              "current_value_range_per_share": [lower[0]["per_share"], upper[0]["per_share"]],
              "range_scope": "SAME_PATH_COST_RANGE_ONLY_PENDING_ECONOMIC_CORE_ASSESSMENT",
              "method_status": {"main": "VALUATION_COMPUTED_ON_FEASIBLE_CASH_PATH", "auxiliary": "DIAGNOSTIC_ONLY_DOES_NOT_NULL_MAIN"},
              "current_midpoint_per_share": midpoint[0]["per_share"],
              "auxiliary_current_per_share": auxiliary[0]["per_share"],
              "auxiliary_point_interpretation": "SIGNED_RESIDUAL_ONLY_NOT_COMMON_SHARE_PRICE" if auxiliary[0]["per_share"] < 0 else "POSITIVE_NORMALIZED_EQUITY_POINT",
              "auxiliary_relative_gap": disparity,
              "auxiliary_gap_requires_explanation": disparity is not None and abs(disparity) > 0.25,
              "auxiliary_mechanism": "mature steady return/reinvestment capitalization omits explicit transition growth; shared capital bridge not independent authentication; never averaged into core",
              "return_model": return_model,
              "return_model_note": "Same operating/funding/ownership/option path; knownQ3 D in first window, H1 excluded; year5 remaining14yr operating/cohort tails plus financial/associate assets less debt/fullNCI and only still-unissuedemployeeclaims; no marketprice/IRR.",
              "option_iterations": iterations, "growth_replans": replans,
              "year_states": rows, "terminal_operating_state": terminal, "associate_states": assoc,
              "valuations": {"core_low": lower, "core_mid": midpoint, "core_high": upper, "auxiliary_mid": auxiliary}}
    return result
