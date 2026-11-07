"""当前资本现金与权益计算核；经营输入由同次实际计算生成。"""
import copy
import hashlib
import json
import math
import os
from fractions import Fraction
from pathlib import Path


ASOF = "2026-10-29T20:00:00+00:00"
EVENT_EVIDENCE_DATE = "2026-11-03"
POLICY = {
    "rate": ".035", "cash_yield": ".01", "restricted_yield": ".015",
    "restricted_tax_rate": ".25", "portfolio_yield": ".025", "investment_yield": ".04",
    "restricted_total": "2.81784941523", "op_floor": "1.08434152701",
    "unresolved0": ".2", "resolve_rate": ".2", "cost_anchor": "9.70",
    "qty_anchor": "76.", "restricted_parent_numerator": "2.17157235279",
    "restricted_parent_denominator": "2.91744722625", "bank_anchor": "67.90205880025",
    "taxable_slaughter_allowance": ".15", "operating_tax_rate": ".25", "operating_cash_tax": ".15",
    "cb_face": "9.5429474", "cb_redemption_factor": "1.07", "cb_cash_premium": ".668006318",
    "first_maturity": "62.", "later_maturity_ratio": ".75", "finance_limit": "12.",
    "group_floor": "12.", "parent_floor": "3.", "sub_floor": "5.", "cycle_buffer": "18.",
    "repay_ratio": ".65", "hq_expense": ".5", "parent_portfolio": ".2",
    "steady_lease_principal": ".8", "minority_ratio": ".00021",
    "statutory_ratio": ".1", "sub_reserve_cap": "47.259422605025",
    "parent_reserve_fraction": ".5", "dividend_ratio": ".4", "upstream_parent_buffer": "6.",
    "gross_ic_limit": "2.", "investment_sale_fee": ".02",
    "balance_tolerance": "1e-7", "funding_tolerance": "1e-8",
}
OPERATING_FIELDS = (
    "year", "qty_million", "weight_kg", "pig_price", "cash_unit_cost", "slaughter_cash", "ebitda",
    "da_fixed", "da_bio", "da_rou", "capex_fixed", "maintenance_fixed", "expansion",
    "bio_gross", "bio_disposal_cash", "bio_net", "lease_new", "lease_principal", "delta_working",
    "portfolio_redemption", "investment_sale", "investment_sale_cost", "investment_sale_tax",
)


class TechnicalFailure(Exception):
    def __init__(self, code, detail=None):
        super().__init__(code)
        self.code = code
        self.detail = detail or {}


def number_factory(kind):
    if kind == "float":
        return float
    if kind == "fraction":
        return Fraction
    raise TechnicalFailure("NUMBER_KIND_NOT_SUPPORTED")


def context(kind="float", fixture_policy=None):
    n = number_factory(kind)
    values = dict(POLICY)
    if fixture_policy is not None:
        unknown = set(fixture_policy) - set(values)
        if unknown:
            raise TechnicalFailure("UNKNOWN_FIXTURE_POLICY", {"keys": sorted(unknown)})
        values.update(fixture_policy)
    out = {key: n(value) for key, value in values.items()}
    if kind == "fraction":
        out["balance_tolerance"] = Fraction(0)
        out["funding_tolerance"] = Fraction(0)
    return {"kind": kind, "n": n, "p": out, "fixture": fixture_policy is not None}


def numeric_tree(obj, n):
    if isinstance(obj, bool) or obj is None:
        return obj
    if isinstance(obj, dict):
        return {k: numeric_tree(v, n) for k, v in obj.items()}
    if isinstance(obj, list):
        return [numeric_tree(v, n) for v in obj]
    if isinstance(obj, str):
        try:
            value = n(obj)
        except (ValueError, ZeroDivisionError):
            return obj
        if isinstance(value, float) and not math.isfinite(value):
            raise TechnicalFailure("NONFINITE_INPUT")
        return value
    return obj


def condition(name, ctx, fixture_amounts=None):
    n = ctx["n"]
    if name not in ("ZERO", "A0", "A1O", "A2O"):
        raise TechnicalFailure("CONDITION_NOT_ADMITTED", {"condition": name})
    if fixture_amounts is not None and not ctx["fixture"]:
        raise TechnicalFailure("FIXTURE_AMOUNTS_IN_PRODUCTION")
    principal = n("0") if name == "ZERO" else n("0.3")
    coupon = n("0") if name == "ZERO" else n("0.00414986301")
    if fixture_amounts is not None:
        principal, coupon = map(n, fixture_amounts)
    if name == "ZERO" and (principal != 0 or coupon != 0):
        raise TechnicalFailure("NONZERO_AMOUNT_IN_ZERO_CONDITION")
    ag = coupon if name in ("A1O", "A2O") else n("0")
    ap = coupon if name == "A1O" else n("0")
    return {"name": name, "active": name != "ZERO", "principal": principal, "coupon": coupon,
            "group_accrual_other": ag, "parent_accrual_other": ap,
            "group_accrual_debt": n("0"), "parent_accrual_debt": n("0"),
            "funding": "F0", "cash_yield_exposure": n("1"),
            "actual_payment_text_cny": "304149863.01" if fixture_amounts is None and name != "ZERO" else None}


def check_close(left, right, ctx, code, trace):
    error = left - right
    if abs(error) > ctx["p"]["balance_tolerance"]:
        raise TechnicalFailure(code, {"error": error, "partial": copy.deepcopy(trace)})
    return error


def repayment_journal(opening, bridge, ctx):
    """Same formal event function for production and Fraction tests; no NCI split."""
    journal_phase = "prepare"
    completed_steps = []
    n = ctx["n"]
    s = copy.deepcopy(opening)
    if not bridge["active"]:
        return s, {"applied": False, "payment": n("0"), "u_group": n("0"),
                   "u_parent": n("0"), "anchor_gap": n("0")}, None
    journal_phase = "validate_event"
    p, i = bridge["principal"], bridge["coupon"]
    ag, ap = bridge["group_accrual_other"], bridge["parent_accrual_other"]
    if bridge["group_accrual_debt"] != 0 or bridge["parent_accrual_debt"] != 0:
        raise TechnicalFailure("DEBT_ACCRUAL_CLASS_NOT_ADMITTED")
    if p < 0 or i < 0 or not (0 <= ap <= ag <= i):
        raise TechnicalFailure("INVALID_ADMITTED_ACCRUAL_DOMAIN")
    if opening["bank"] < p or opening["parent_bank"] < p or opening["op_liab"] < ag:
        return s, {"applied": False, "known_payment": p + i,
                   "gaps": {"group_identified_principal": max(n("0"), p-opening["bank"]),
                            "parent_identified_principal": max(n("0"), p-opening["parent_bank"]),
                            "group_identified_other_accrual": max(n("0"), ag-opening["op_liab"])}}, "IDENTIFIED_POOL_INSUFFICIENT"
    ug, up, payment = i - ag, i - ap, p + i
    journal_phase = 'group_cash_payment'
    s["cash"] -= payment
    completed_steps.append('group_cash_payment')
    journal_phase = 'parent_cash_payment'
    s["parent_cash"] -= payment
    completed_steps.append('parent_cash_payment')
    journal_phase = 'group_principal_retirement'
    s["bank"] -= p
    completed_steps.append('group_principal_retirement')
    journal_phase = 'parent_principal_retirement'
    s["parent_bank"] -= p
    completed_steps.append('parent_principal_retirement')
    journal_phase = 'group_accrual_settlement'
    s["op_liab"] -= ag
    completed_steps.append('group_accrual_settlement')
    journal_phase = 'group_common_equity'
    s["common"] -= ug
    completed_steps.append('group_common_equity')
    journal_phase = 'group_retained_earnings'
    s["group_re"] -= ug
    completed_steps.append('group_retained_earnings')
    journal_phase = 'parent_retained_earnings'
    s["parent_re"] -= up
    completed_steps.append('parent_retained_earnings')
    journal_phase = "form_ledger"
    ledger = {"applied": True, "principal": p, "coupon": i, "payment": payment,
              "group_accrual_other_settlement": ag, "parent_accrual_other_settlement_memo": ap,
              "u_group": ug, "u_parent": up, "anchor_gap": up - ug,
              "group_cash_delta": -payment, "parent_cash_delta": -payment,
              "bank_delta": -p, "parent_bank_delta": -p, "op_liab_delta": -ag,
              "common_delta": -ug, "group_re_delta": -ug, "parent_re_delta": -up,
              "sub_cash_delta": n("0"), "sub_re_delta": n("0"), "minority_delta": n("0"),
              "new_tax_benefit": n("0"), "observed_replacement_receipt": n("0"),
              "cash_yield_exposure": bridge["cash_yield_exposure"]}
    completed_steps.append("form_ledger")
    journal_phase = "group_balance_check"
    check_close(-payment, -p - ag - ug, ctx, "JOURNAL_GROUP_IMBALANCE", ledger)
    completed_steps.append("group_balance_check")
    journal_phase = "parent_balance_check"
    check_close(-payment, -p - ap - up, ctx, "JOURNAL_PARENT_IMBALANCE", ledger)
    completed_steps.append("parent_balance_check")
    journal_phase = "event_cash_source_check"
    if s["cash"] < 0 or s["parent_cash"] < 0:
        ledger["gaps"] = {"group_event_cash_source": max(n("0"), -s["cash"]),
                          "parent_event_cash_source": max(n("0"), -s["parent_cash"])}
        return s, ledger, "ACTUAL_PAYMENT_BUDGET_SOURCE_GAP"
    return s, ledger, None


def economic_failure(y, phase, reason, opening, attempted, trace, gap=None, gaps=None):
    row = {"year": y, "feasible": False, "failure_type": "economic", "phase": phase,
           "reason": reason, "funding_gap": gap, "entity_gaps": copy.deepcopy(gaps or {}), "opening_state": copy.deepcopy(opening),
           "attempted_state": copy.deepcopy(attempted), "ending_state": copy.deepcopy(opening),
           "computed_fields": copy.deepcopy(trace)}
    return copy.deepcopy(opening), row, False


def stage_values(values):
    """Retain all evaluated intermediate amounts without recursive trace objects."""
    omit = {"n", "p", "ctx", "trace", "s", "o", "raw_o", "operating", "baseline", "bridge", "row"}
    return {key: copy.deepcopy(value) for key, value in values.items()
            if key not in omit and not callable(value)}


def validate_finite_input(value, path="input"):
    if isinstance(value, float) and not math.isfinite(value):
        raise TechnicalFailure("NONFINITE_STEP_INPUT", {"path": path})
    if isinstance(value, dict):
        for key, child in value.items():
            validate_finite_input(child, path + "." + str(key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            validate_finite_input(child, path + "[" + str(index) + "]")


def step_capital(s, y, case, operating, baseline, ctx, bridge):
    """Preserve the actual failing production-frame locals for any late error."""
    try:
        return _step_capital_impl(s, y, case, operating, baseline, ctx, bridge)
    except Exception as exc:
        frame_values = None
        journal_values = None
        journal_failure_line = None
        tb = exc.__traceback__
        while tb is not None:
            # Inspect only these two production functions, never unrelated frames.
            if tb.tb_frame.f_code is _step_capital_impl.__code__:
                frame_values = dict(tb.tb_frame.f_locals)
            elif tb.tb_frame.f_code is repayment_journal.__code__:
                journal_values = dict(tb.tb_frame.f_locals)
                journal_failure_line = tb.tb_lineno
            tb = tb.tb_next
        values = frame_values or {}
        partial = {"phase": values.get("phase", "input_validation"),
                   "raw_opening_state": copy.deepcopy(values.get("raw_o", s)),
                   "attempted_state": copy.deepcopy(values.get("s", s)),
                   "event": copy.deepcopy(values.get("event", {})),
                   "financial_intermediates": stage_values(values),
                   "frozen_operating": copy.deepcopy(operating)}
        if journal_values is not None:
            # A failed journal call has not assigned its local state/ledger back
            # to _step_capital_impl. Prefer the actual journal attempt, not its
            # caller's still-opening s. A formed ledger is not a completed check.
            jv = journal_values
            partial["phase"] = "event_journal"
            partial["attempted_state"] = copy.deepcopy(jv.get("s", jv.get("opening", s)))
            interrupted_event = copy.deepcopy(jv.get("ledger", {}))
            for public, local in (("principal", "p"), ("coupon", "i"),
                                  ("known_payment", "payment"), ("u_group", "ug"), ("u_parent", "up")):
                if local in jv:
                    interrupted_event[public] = copy.deepcopy(jv[local])
            interrupted_event["journal_completed"] = False
            interrupted_event["journal_status"] = "interrupted_technical"
            partial["event"] = interrupted_event
            completed = jv.get("completed_steps", [])
            partial["journal"] = {
                "phase": jv.get("journal_phase", "prepare"),
                "completed_steps": copy.deepcopy(completed),
                "failure_location": {"function": "repayment_journal", "line": journal_failure_line},
                "opening_state": copy.deepcopy(jv.get("opening", s)),
                "formed_ledger": copy.deepcopy(jv.get("ledger")),
                "accounting_checks_complete": "parent_balance_check" in completed,
                "return_completed": False,
                "intermediates": stage_values(jv),
            }
        if "row" in values:
            partial["completed_row_before_failure"] = copy.deepcopy(values["row"])
        if "trace" in values:
            partial["trace"] = copy.deepcopy(values["trace"])
        code = exc.code if isinstance(exc, TechnicalFailure) else type(exc).__name__
        detail = {"message": str(exc), "partial": partial}
        if isinstance(exc, TechnicalFailure):
            detail["original_detail"] = exc.detail
        raise TechnicalFailure(code, detail) from exc


def _step_capital_impl(s, y, case, operating, baseline, ctx, bridge):
    """Complete capital/distribution chain; frozen saved operating rows only.

    Arithmetic/order of the ZERO branch follows the original source. Extra event
    arithmetic is guarded. The caller later compares ALL old fields bit-exactly.
    """
    phase = "input_validation"
    n, p = ctx["n"], ctx["p"]
    validate_finite_input(s, "opening")
    validate_finite_input(operating, "operating")
    validate_finite_input(baseline, "baseline")
    if s["shares"] <= 0:
        raise TechnicalFailure("NONPOSITIVE_SHARES")
    if bridge["funding"] != "F0" or bridge["cash_yield_exposure"] != 1:
        raise TechnicalFailure("FUNDING_OR_TIMING_NOT_ADMITTED")
    if bridge["group_accrual_debt"] != 0 or bridge["parent_accrual_debt"] != 0:
        raise TechnicalFailure("DEBT_ACCRUAL_CLASS_NOT_ADMITTED")
    if case not in ("core_low", "base", "core_high") and not ctx["fixture"]:
        raise TechnicalFailure("OPERATING_CASE_NOT_ADMITTED", {"case": case})
    if operating["year"] != y:
        raise TechnicalFailure("OPERATING_YEAR_MISMATCH")
    absent = [k for k in OPERATING_FIELDS if k not in operating]
    if absent:
        raise TechnicalFailure("MISSING_OPERATING_FIELDS", {"fields": absent})
    raw_o = copy.deepcopy(s)
    trace = {"year": y, "case": case, "frozen_operating": copy.deepcopy(operating)}
    phase = "event_journal"
    if y == 1 and bridge["active"]:
        s, event, fail = repayment_journal(s, bridge, ctx)
        trace["event"] = event
        if fail:
            return economic_failure(y, "event", fail, raw_o, s, trace, gaps=event.get("gaps"))
    else:
        s = copy.deepcopy(s)
        event = {"applied": False, "payment": n("0"), "u_group": n("0"),
                 "u_parent": n("0"), "anchor_gap": n("0")}
    event_after_snapshot = copy.deepcopy(s) if event["applied"] else None
    o = copy.deepcopy(s)
    phase = "operating_and_financial"
    ug, up, h = event["u_group"], event["u_parent"], event["anchor_gap"]
    q, price, cost, sl, growth = (operating[k] for k in
        ("qty_million", "pig_price", "cash_unit_cost", "slaughter_cash", "expansion"))
    da_fixed, da_bio, da_rou = (operating[k] for k in ("da_fixed", "da_bio", "da_rou"))
    da = da_fixed + da_bio + da_rou
    ebitda = operating["ebitda"]
    cap_fixed = operating["capex_fixed"]
    bio_gross, bio_retire, bio_net = (operating[k] for k in
        ("bio_gross", "bio_disposal_cash", "bio_net"))
    dw = operating["delta_working"]
    s["working"] = operating["physical_ending_state"]["working"]
    s["fixed"] += cap_fixed - da_fixed
    s["bio"] += bio_net - da_bio
    lease_principal, lease_new = operating["lease_principal"], operating["lease_new"]
    s["rou"] += lease_new - da_rou
    s["lease"] += lease_new - lease_principal
    interest = o["bank"] * p["rate"] + o["lease"] * p["rate"]
    cb_pay = p["cb_face"] * p["cb_redemption_factor"] if y == 1 else n("0.")
    cb_charge = cb_pay - s["cb"] if y == 1 else n("0.")
    op_floor, unresolved0, resolve_rate = p["op_floor"], p["unresolved0"], p["resolve_rate"]
    if y == 1:
        o["restricted_operating"] = op_floor
        o["restricted_unresolved"] = unresolved0
        o["restricted_financing"] = p["restricted_total"] - op_floor - unresolved0
    target_op = op_floor * q / p["qty_anchor"] * cost / p["cost_anchor"]
    if bridge["active"]:
        collateral_denominator = p["bank_anchor"] - bridge["principal"]
        if collateral_denominator <= 0:
            raise TechnicalFailure("INVALID_COLLATERAL_DENOMINATOR", trace)
        target_fin = (p["restricted_total"] - op_floor - unresolved0) * o["bank"] / collateral_denominator
    else:
        collateral_denominator = p["bank_anchor"]
        target_fin = (p["restricted_total"] - op_floor - unresolved0) * o["bank"] / p["bank_anchor"]
    target_unresolved = o["restricted_unresolved"] * (n("1.") - resolve_rate if y >= 3 else n("1."))
    s["restricted_operating"], s["restricted_financing"], s["restricted_unresolved"] = target_op, target_fin, target_unresolved
    s["restricted"] = target_op + target_fin + target_unresolved
    restricted_release = o["restricted"] - s["restricted"]
    parent_restricted_ratio = p["restricted_parent_numerator"] / p["restricted_parent_denominator"]
    parent_restricted_release = restricted_release * parent_restricted_ratio
    s["parent_restricted"] = s["restricted"] * parent_restricted_ratio
    restricted_income = o["restricted"] * p["restricted_yield"]
    restricted_tax = restricted_income * p["restricted_tax_rate"]
    finance_income = (restricted_income + s["portfolio"] * p["portfolio_yield"]
                      + s["investment"] * p["investment_yield"] + s["cash"] * p["cash_yield"])
    tax = max(n("0."), sl - p["taxable_slaughter_allowance"]) * p["operating_tax_rate"] + p["operating_cash_tax"] + restricted_tax
    investment_sale = s["investment"] if y == 10 else n("0.")
    investment_sale_cost = investment_sale * p["investment_sale_fee"]
    ni = ebitda - da - interest - cb_charge + finance_income - tax - investment_sale_cost
    # Mother components are evaluated early without changing state or old order.
    parent_interest = o["parent_bank"] * p["rate"] + o["parent_lease"] * p["rate"]
    parent_fin_income = (o["parent_cash"] * p["cash_yield"] + o["parent_restricted"] * p["restricted_yield"]
                         + (p["parent_portfolio"] * p["portfolio_yield"] if y == 1 else n("0.")))
    parent_restricted_tax = o["parent_restricted"] * p["restricted_yield"] * p["restricted_tax_rate"]
    attribution = None
    if bridge["active"]:
        if baseline is None or any(k not in baseline for k in ("parent_interest", "parent_fin_income", "parent_restricted_tax")):
            raise TechnicalFailure("MISSING_PARENT_ATTRIBUTION_BASELINE", trace)
        ni -= ug
        delta_interest = baseline["parent_interest"] - parent_interest
        delta_cash_and_restricted_yield = parent_fin_income - baseline["parent_fin_income"]
        delta_restricted_tax = baseline["parent_restricted_tax"] - parent_restricted_tax
        delta_parent_only = delta_interest + delta_cash_and_restricted_yield + delta_restricted_tax - ug
        minority_income = (ni - delta_parent_only) * p["minority_ratio"]
        attribution = {"mother_interest_delta_in_group_NI": delta_interest,
                       "mother_cash_and_restricted_yield_delta_in_group_NI": delta_cash_and_restricted_yield,
                       "mother_restricted_cash_tax_delta_in_group_NI": delta_restricted_tax,
                       "group_coupon_expense_delta": -ug,
                       "parent_H1_coupon_expense_not_substituted": up,
                       "delta_parent_only_in_group_NI": delta_parent_only,
                       "minority_income_base": ni - delta_parent_only,
                       "baseline_parent_interest": baseline["parent_interest"],
                       "baseline_parent_fin_income": baseline["parent_fin_income"],
                       "baseline_parent_restricted_tax": baseline["parent_restricted_tax"]}
    else:
        minority_income = ni * p["minority_ratio"]
    common_income = ni - minority_income
    redeem = s["portfolio"] if y == 1 else n("0.")
    s["portfolio"] -= redeem
    fcfe = ni + da - cap_fixed - bio_net - lease_principal - dw
    if event["applied"]:
        fcfe += ug  # expense already paid in the separate full-C journal
    s["cash"] += fcfe + redeem + investment_sale - cb_pay + cb_charge + restricted_release
    s["investment"] -= investment_sale
    s["cb"] = n("0.") if y == 1 else s["cb"]
    maturity_cap = p["first_maturity"] - bridge["principal"] if bridge["active"] else p["first_maturity"]
    maturity = min(s["bank"], maturity_cap if y == 1 else s["bank"] * p["later_maturity_ratio"])
    rollover = maturity
    contractual_net = maturity - rollover
    s["bank"] -= contractual_net
    s["cash"] -= contractual_net
    if y == 1:
        s["other_equity"] = n("0.")
    phase = "group_funding"
    need = max(n("0."), p["group_floor"] - s["cash"])
    issue = min(need, max(n("0."), p["finance_limit"] - s["finance_used"]))
    s["finance_used"] += issue
    s["bank"] += issue
    s["cash"] += issue
    trace.update({"event": event, "attribution": attribution, "net_income": ni, "common_income": common_income,
                  "interest": interest, "finance_income": finance_income, "tax": tax, "fcfe_before_finance": fcfe,
                  "bank_maturity": maturity, "rollover": rollover, "new_finance": issue,
                  "restricted_release": restricted_release, "collateral_denominator": collateral_denominator})
    trace["financial_intermediates"] = stage_values(locals())
    if s["cash"] < p["group_floor"] - p["funding_tolerance"]:
        return economic_failure(y, "group_funding", "CASH_FLOOR_UNFUNDED_AFTER_BUDGET_FINANCING", raw_o, s, trace, p["group_floor"] - s["cash"],
                                {"group_cash_floor": p["group_floor"] - s["cash"]})
    phase = "discretionary_debt"
    repay = min(s["bank"], max(n("0."), s["cash"] - p["cycle_buffer"]) * (p["repay_ratio"] if y <= 10 else n("1.")))
    s["bank"] -= repay
    s["cash"] -= repay
    phase = "entity_cash_and_profit"
    parent_ratio = o["parent_bank"] / o["bank"] if o["bank"] else n("0.")
    parent_lease_ratio = o["parent_lease"] / o["lease"] if o["lease"] else n("0.")
    s["parent_lease"] += (lease_new - lease_principal) * parent_lease_ratio
    parent_expense = p["hq_expense"] + parent_interest + cb_charge - parent_fin_income + parent_restricted_tax
    if event["applied"]:
        parent_expense += up
    s["parent_bank"] = max(n("0."), o["parent_bank"] + (issue - repay - contractual_net) * parent_ratio)
    sub_income = common_income + parent_expense
    if event["applied"]:
        sub_income -= h  # anchor memo cannot become subsidiary profit
    sr0 = s["sub_re"]
    s["sub_re"] += sub_income
    statutory = min(max(n("0."), sub_income - max(n("0."), -sr0)) * p["statutory_ratio"],
                    max(n("0."), p["sub_reserve_cap"] - s["sub_reserve"]))
    s["sub_re"] -= statutory
    s["sub_reserve"] += statutory
    parent_financing = ((issue - repay - contractual_net) * parent_ratio - cb_pay + cb_charge
                        - (lease_principal - p["steady_lease_principal"]) * parent_lease_ratio)
    parent_portfolio_redemption = p["parent_portfolio"] if y == 1 else n("0.")
    pc = s["parent_cash"] - parent_expense + parent_financing + parent_portfolio_redemption + parent_restricted_release
    if event["applied"]:
        pc += up
    sub_cash = s["cash"] - pc
    desired = n("0.") if y == 1 else max(n("0."), common_income) * p["dividend_ratio"] if y <= 10 else max(n("0."), s["cash"] - p["cycle_buffer"])
    desired = min(desired, max(n("0."), s["cash"] - p["group_floor"]))
    upstream = min(max(n("0."), s["sub_re"]), max(n("0."), sub_cash - p["sub_floor"]),
                   max(n("0."), desired + p["upstream_parent_buffer"] - pc))
    s["sub_re"] -= upstream
    pc += upstream
    sub_cash -= upstream
    phase = "parent_re_and_reserve"
    parent_profit = upstream - parent_expense
    pr0 = raw_o["parent_re"] if event["applied"] else s["parent_re"]
    if event["applied"]:
        s["parent_re"] += parent_profit + up
    else:
        s["parent_re"] += parent_profit
    reserve = min(max(n("0."), parent_profit - max(n("0."), -pr0)) * p["statutory_ratio"],
                  max(n("0."), s["registered"] * p["parent_reserve_fraction"] - s["parent_reserve"]))
    s["parent_re"] -= reserve
    s["parent_reserve"] += reserve
    phase = "gross_internal_principal"
    gross_receive = min(p["gross_ic_limit"], s["ic_receivable"], max(n("0."), sub_cash - p["sub_floor"]))
    pc += gross_receive
    sub_cash -= gross_receive
    s["ic_receivable"] -= gross_receive
    gross_pay = min(p["gross_ic_limit"], s["ic_payable"], max(n("0."), pc - p["parent_floor"]))
    pc -= gross_pay
    sub_cash += gross_pay
    s["ic_payable"] -= gross_pay
    phase = "internal_support"
    support = n("0.")
    if pc < p["parent_floor"]:
        support = min(p["parent_floor"] - pc, max(n("0."), sub_cash - p["sub_floor"]))
        pc += support
        sub_cash -= support
        s["ic_payable"] += support
    elif sub_cash < p["sub_floor"]:
        support = -min(p["sub_floor"] - sub_cash, max(n("0."), pc - p["parent_floor"]))
        pc += support
        sub_cash -= support
        s["ic_receivable"] -= support
    collect = min(s["ic_receivable"], max(n("0."), sub_cash - p["sub_floor"]),
                  max(n("0."), desired + p["parent_floor"] - pc))
    s["ic_receivable"] -= collect
    pc += collect
    sub_cash -= collect
    phase = "dividend_and_minority"
    dividend = min(desired, max(n("0."), s["parent_re"]), max(n("0."), pc - p["parent_floor"]))
    pc -= dividend
    s["parent_re"] -= dividend
    s["cash"] -= dividend
    s["parent_cash"] = pc
    md = min(max(n("0."), minority_income), max(n("0."), s["cash"] - p["group_floor"]), max(n("0."), sub_cash - p["sub_floor"]))
    s["cash"] -= md
    sub_cash -= md
    if event["applied"]:
        s["common"] += common_income + ug - dividend
        s["group_re"] += common_income + ug - dividend
    else:
        s["common"] += common_income - dividend
        s["group_re"] += common_income - dividend
    s["minority"] += minority_income - md
    assets = sum(s[k] for k in ("cash", "restricted", "portfolio", "investment", "fixed", "bio", "rou", "working"))
    liabilities = s["bank"] + s["cb"] + s["lease"] + s["op_liab"]
    equity = s["common"] + s["minority"]
    cash_error = s["cash"] - (o["cash"] + fcfe + redeem + investment_sale + restricted_release
                   - (p["cb_face"] * p["cb_redemption_factor"] if y == 1 else n("0."))
                   + (p["cb_face"] * p["cb_redemption_factor"] - o["cb"] if y == 1 else n("0."))
                   - contractual_net + issue - repay - dividend - md + n("0."))
    row = dict(year=y, feasible=True, qty_million=q, weight_kg=operating["weight_kg"], pig_price=price, cash_unit_cost=cost, slaughter_cash=sl,
        ebitda=ebitda, da_fixed=da_fixed, da_bio=da_bio, da_rou=da_rou, ebit=ebitda-da, interest=interest, cb_charge=cb_charge,
        finance_income=finance_income, restricted_income=restricted_income, restricted_tax=restricted_tax, restricted_release=restricted_release,
        parent_restricted_release=parent_restricted_release, parent_restricted_tax=parent_restricted_tax, tax=tax, net_income=ni, common_income=common_income, capex_fixed=cap_fixed,
        maintenance_fixed=da_fixed, expansion=growth, bio_gross=bio_gross, bio_disposal_cash=bio_retire, bio_net=bio_net,
        lease_new=lease_new, lease_principal=lease_principal, delta_working=dw, fcfe_before_finance=fcfe,
        portfolio_redemption=redeem, investment_sale=investment_sale, investment_sale_cost=investment_sale_cost, investment_sale_tax=n("0."),
        cb_face=p["cb_face"] if y == 1 else n("0."), cb_cash_interest_premium=p["cb_cash_premium"] if y == 1 else n("0."),
        cb_repayment=cb_pay, bank_maturity=maturity, rollover=rollover, new_finance=issue, discretionary_bank_repayment=repay,
        parent_expense=parent_expense, parent_interest=parent_interest, parent_fin_income=parent_fin_income, parent_financing=parent_financing,
        sub_income=sub_income, sub_statutory=statutory, upstream_declared=upstream, upstream_paid=upstream, parent_profit=parent_profit, parent_statutory=reserve,
        gross_ic_principal_received=gross_receive, gross_ic_principal_paid=gross_pay, new_ic_support_to_parent=support, ic_principal_collected=collect,
        common_dividend=dividend, dps=dividend/s["shares"], minority_dividend=md, sub_cash=sub_cash,
        assets=assets, liabilities=liabilities, equity=equity, cash_error=cash_error, ending_state=s)
    trace["completed_row_before_validation"] = copy.deepcopy(row)
    trace["financial_intermediates"] = stage_values(locals())
    if bridge["active"]:
        row["bridge"] = {"condition": bridge["name"], "funding": "F0", "event": event, "attribution": attribution,
            "event_before_state": raw_o if event["applied"] else None,
            "event_after_state": event_after_snapshot,
            "already_posted_coupon_fcfe_addback": ug, "already_posted_parent_cash_addback": up,
            "already_posted_group_equity_addback": ug, "already_posted_parent_RE_addback": up,
            "parent_reserve_opening_RE": pr0, "nondistributable_anchor_gap_once": h,
            "collateral_eligible_opening_bank": o["bank"], "collateral_denominator": collateral_denominator,
            "known_principal_paid_once": bridge["principal"] if event["applied"] else n("0."),
            "remaining_maturity": maturity, "replacement_observed_receipt": n("0."),
            "desired_dividend_before_legal_and_cash_caps": desired,
            "minority_income": minority_income,
            "valuation_anchor": ASOF, "event_evidence_date": EVENT_EVIDENCE_DATE}
    phase = "final_validation"
    if ctx["fixture"] and ctx.get("fixture_fault_phase") == phase:
        raise RuntimeError("deliberate post-payment final-validation fixture fault")
    check_close(assets, liabilities + equity, ctx, "BALANCE_SHEET_FAILURE", trace)
    check_close(cash_error, n("0."), ctx, "CASH_ROLLFORWARD_FAILURE", trace)
    check_close(pc + sub_cash, s["cash"], ctx, "ENTITY_CASH_FAILURE", trace)
    check_close(s["bank"], o["bank"] - contractual_net + issue - repay, ctx, "BANK_ROLLFORWARD_FAILURE", trace)
    check_close(s["lease"], o["lease"] + lease_new - lease_principal, ctx, "LEASE_ROLLFORWARD_FAILURE", trace)
    check_close(s["parent_bank"], max(n("0."), o["parent_bank"] + (issue - repay - contractual_net) * parent_ratio), ctx, "PARENT_BANK_ROLLFORWARD_FAILURE", trace)
    check_close(s["shares"], raw_o["shares"], ctx, "SHARE_COUNT_CHANGED", trace)
    check_close(s["ic_payable"], o["ic_payable"] - gross_pay + max(n("0."), support), ctx, "IC_PAYABLE_FAILURE", trace)
    check_close(s["ic_receivable"], o["ic_receivable"] - gross_receive - collect - min(n("0."), support), ctx, "IC_RECEIVABLE_FAILURE", trace)
    check_close(s["working"], o["working"] + dw, ctx, "WORKING_CASH_BRIDGE_FAILURE", trace)
    check_close(cap_fixed, da_fixed + growth, ctx, "FIXED_CAPITAL_INPUT_FAILURE", trace)
    check_close(redeem, operating["portfolio_redemption"], ctx, "FROZEN_REDEMPTION_CHANGED", trace)
    check_close(investment_sale, operating["investment_sale"], ctx, "FROZEN_INVESTMENT_SALE_CHANGED", trace)
    check_close(investment_sale_cost, operating["investment_sale_cost"], ctx, "FROZEN_INVESTMENT_FEE_CHANGED", trace)
    for key in ("fixed", "bio", "rou", "working", "investment", "portfolio"):
        check_close(s[key], operating["physical_ending_state"][key], ctx, "FROZEN_OPERATING_STATE_CHANGED:" + key, trace)
    if min(s["cash"] - p["group_floor"], pc - p["parent_floor"], sub_cash - p["sub_floor"]) < -p["balance_tolerance"]:
        gaps = {"group_cash_floor": max(n("0"), p["group_floor"]-s["cash"]),
                "parent_cash_floor": max(n("0"), p["parent_floor"]-pc),
                "subsidiary_cash_floor": max(n("0"), p["sub_floor"]-sub_cash)}
        return economic_failure(y, "entity_distribution", "ENTITY_CASH_BUFFER_UNFUNDED", raw_o, s, trace, gaps=gaps)
    if dividend < 0 or dividend > desired or dividend > max(n("0."), s["parent_re"] + dividend) + p["balance_tolerance"]:
        raise TechnicalFailure("UNSUPPORTED_DIVIDEND_OR_LEGAL_RE", trace)
    return s, row, True


def summarize(rows, case, rate, final_state):
    """Same order as old simulate; Y5 discounts the SAME tail, no net-cash add-on."""
    pv = sum(r["dps"] / (1 + rate) ** r["year"] for r in rows)
    tv = sum(r["dps"] / (1 + rate) ** (r["year"] - 5) for r in rows if r["year"] > 5)
    return dict(case=case, entry="unit", feasible=True, rows=rows, current_value=pv, terminal_y5=tv, rate=rate,
                dps5=[r["dps"] for r in rows[:5]],
                pv_after5=sum(r["dps"] / (1 + rate) ** r["year"] for r in rows[5:]), final_state=final_state)


def simulate_saved(opening, operating_rows, baseline_rows, case, rate, ctx, bridge):
    s = copy.deepcopy(opening)
    rows = []
    for y, operating in enumerate(operating_rows, 1):
        baseline = baseline_rows[y-1] if baseline_rows is not None and y <= len(baseline_rows) else None
        try:
            s, row, ok = step_capital(s, y, case, operating, baseline, ctx, bridge)
        except TechnicalFailure as exc:
            rows.append({"year": y, "feasible": None, "failure_type": "implementation", "reason": exc.code,
                         "partial": exc.detail.get("partial", exc.detail), "exception_detail": exc.detail,
                         "last_completed_state": copy.deepcopy(s)})
            return dict(case=case, entry="unit", feasible=None, failure_type="implementation", rows=rows,
                        current_value=None, terminal_y5=None, dps5=None, rate=rate)
        except Exception as exc:
            rows.append({"year": y, "feasible": None, "failure_type": "implementation", "reason": type(exc).__name__,
                         "message": str(exc), "last_completed_state": copy.deepcopy(s), "frozen_operating": copy.deepcopy(operating),
                         "partial": {"phase": "simulate_boundary", "raw_opening_state": copy.deepcopy(s),
                                     "attempted_state": copy.deepcopy(s), "event": {}, "financial_intermediates": {}}})
            return dict(case=case, entry="unit", feasible=None, failure_type="implementation", rows=rows,
                        current_value=None, terminal_y5=None, dps5=None, rate=rate)
        rows.append(row)
        if not ok:
            return dict(case=case, entry="unit", feasible=False, failure_type="economic", rows=rows,
                        current_value=None, terminal_y5=None, dps5=None, rate=rate)
    try:
        return summarize(rows, case, rate, s)
    except Exception as exc:
        return dict(case=case, entry="unit", feasible=None, failure_type="implementation", rows=rows,
                    current_value=None, terminal_y5=None, dps5=None, rate=rate,
                    summary_failure={"phase": "valuation_summary", "reason": type(exc).__name__,
                                     "message": str(exc), "attempted_state": copy.deepcopy(s)})
