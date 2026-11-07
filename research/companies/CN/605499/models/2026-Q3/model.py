"""Planned compact economic producer. NOT executed during static preparation.
Units: CNY billion and shares billion. Only stdlib json/sys; no project imports.
All business assumptions are in model_inputs.json. Cash ownership != payout ceiling.
"""
import json
import sys
from datetime import date


class FundingGap(ValueError):
    def __init__(self, message, partial=None):
        super().__init__(message)
        self.partial = partial or {}


def clone(value):
    return json.loads(json.dumps(value))


def close(actual, expected, tolerance=1e-8):
    if abs(actual - expected) > tolerance * max(1.0, abs(expected)):
        raise AssertionError((actual, expected))


def operating_metrics(item):
    revenues = item["product_revenue"]
    margins = item["gross_margin"]
    if len(revenues) != len(margins) or not revenues:
        raise ValueError("product dimensions")
    if any(x < 0 for x in revenues) or any(not -1 < x < 1 for x in margins):
        raise ValueError("product economics")
    revenue = sum(revenues)
    if revenue <= 0:
        raise ValueError("positive revenue required")
    gross = sum(r * m for r, m in zip(revenues, margins))
    expenses = sum(item[k] for k in ("sales_ratio", "admin_ratio", "rd_ratio", "surcharge_ratio", "ordinary_loss_ratio")) * revenue
    ebit = gross - expenses - item["lease_extra_cash_charge"]
    tax = max(ebit, 0.0) * item["tax"]  # no immediate refund on unproven losses
    nopat = ebit - tax
    fcff = nopat + item["da_nonlease"] - item["capex_cash"] - item["delta_wc"]
    result = dict(item)
    result.update(revenue=revenue, gross_profit=gross, ebit=ebit,
                  ebit_margin=ebit / revenue, nopat=nopat, fcff=fcff)
    if item["capex_cash"] < 0 or item["da_nonlease"] < 0:
        raise ValueError("capital inputs")
    if item.get("legacy_capex_payment", 0.0) > item["capex_cash"] + 1e-10:
        raise ValueError("legacy cash cannot exceed total capex")
    close(fcff, nopat + item["da_nonlease"] - item["capex_cash"] - item["delta_wc"])
    return result


def scale_period(row, fraction):
    """Scale flows only; tax/margin/rates remain unchanged."""
    item = dict(row)
    item["product_revenue"] = [v * fraction for v in row["product_revenue"]]
    for key in ("lease_extra_cash_charge", "da_nonlease", "capex_cash", "delta_wc", "legacy_capex_payment"):
        item[key] = row.get(key, 0.0) * fraction
    return operating_metrics(item)


def after_tax_interest(row, context, duration):
    gross = context["debt"] * context["debt_cost"] * duration
    # Do not grant an immediate tax shield where the operating base has losses.
    return gross - min(max(row["ebit"], 0.0), gross) * row["tax"]


def cash_step(opening, row, context, duration, dividend):
    interest = after_tax_interest(row, context, duration)
    yield_cash = opening * context["cash_yield"] * duration
    minority_cash = max(row["nopat"], 0.0) * context["nci_fraction"]
    closing = opening + row["fcff"] + yield_cash - interest - minority_cash - dividend
    close(closing - opening, row["fcff"] + yield_cash - interest - minority_cash - dividend)
    if closing < -1e-9:
        raise FundingGap("liquid portfolio exhausted; explicit financing/exit redesign needed", {"stage":"cash_step","cash_opening":opening,"cash_closing_raw":closing,"fcff":row["fcff"],"interest":interest,"yield":yield_cash,"dividend":dividend})
    return closing, interest, yield_cash, minority_cash


def day(value):
    return date.fromisoformat(value)


def anniversary(origin, years):
    return date(origin.year + years, origin.month, origin.day)


def years_between(origin, target):
    """Actual/actual anniversary fractions: exact anniversaries equal integers."""
    if target < origin:
        return -years_between(target, origin)
    whole = target.year - origin.year
    if anniversary(origin, whole) > target:
        whole -= 1
    left = anniversary(origin, whole)
    right = anniversary(origin, whole + 1)
    return whole + (target-left).days/(right-left).days


def reserve_amount(income, gap, context, full_year_active):
    proposed = max(income, 0.0)*context["appropriation_rate"]
    mode = context["appropriation_mode"]
    if mode == "cap_at_threshold":
        return min(gap, proposed)
    if mode == "full_year_until_threshold":
        return proposed if full_year_active else 0.0
    if mode == "continue_10pct":
        return proposed
    raise ValueError("unknown appropriation mode")


def mother_calendar(year, cash, retained, gap, upstream, target, context):
    """Only a few dated corporate events, not a monthly/individual-entity model.
    Profit recognition and cash arrival are distinct. Old available cash carries.
    """
    events = []
    for index, plan in enumerate(context["upstream_schedule"]):
        if plan["recognition_md"] > plan["cash_md"]:
            raise ValueError("upstream recognition must precede receipt in this budget")
        amount = upstream*plan["weight"]
        for kind, key, priority in (("upstream_recognition","recognition_md",0),("upstream_cash","cash_md",1)):
            events.append({"date":f"{year}-{plan[key]}","kind":kind,"amount":amount,"priority":priority,"ref":f"U{year}-{index}"})
    for index, plan in enumerate(context["payment_plan"]):
        declaration=f"{year}-{plan['declaration_month_day']}"
        entitlement=f"{year}-{plan['entitlement_month_day']}"
        payment=f"{year}-{plan['payment_month_day']}"
        if not declaration <= entitlement <= payment:
            raise ValueError("declaration <= entitlement <= payment")
        ref=f"D{year}-{index}"
        common={"planned_amount":target*plan["weight"],"ref":ref,"payment_date":payment,"entitlement_date":entitlement,"declaration_date":declaration}
        events.append(dict(common,date=declaration,kind="dividend_declaration",priority=2))
        events.append(dict(common,date=payment,kind="dividend_payment",priority=3))
    events.sort(key=lambda e:(e["date"],e["priority"],e["ref"]))
    all_events=clone(events)
    declarations={}
    records=[]
    full_year_active=gap>1e-10
    total_reserve=0.0
    for event in events:
        kind=event["kind"]
        amount=event.get("amount",0.0)
        reserve=0.0
        mother_cash_delta=0.0
        subsidiary_cash_delta=0.0
        if kind == "upstream_recognition":
            reserve=reserve_amount(amount,gap,context,full_year_active)
            gap=max(0.0,gap-reserve)
            retained += amount-reserve
            total_reserve += reserve
        elif kind == "upstream_cash":
            cash += amount
            mother_cash_delta=amount
            subsidiary_cash_delta=-amount
        elif kind == "dividend_declaration":
            # Forecast receipts by the planned payment may support declaration;
            # existing legal profits are still required at declaration.
            arrivals=sum(e["amount"] for e in all_events if e["kind"]=="upstream_cash" and event["date"]<e["date"]<=event["payment_date"])
            prior_unpaid=sum(e["amount"] for e in declarations.values() if not e["paid"] and e["payment_date"]<=event["payment_date"])
            amount=min(event["planned_amount"],max(retained,0.0),max(cash+arrivals-prior_unpaid,0.0))
            retained -= amount
            declarations[event["ref"]]={"amount":amount,"paid":False,"payment_date":event["payment_date"]}
        elif kind == "dividend_payment":
            amount=declarations[event["ref"]]["amount"]
            cash -= amount
            mother_cash_delta=-amount
            declarations[event["ref"]]["paid"]=True
            if cash < -1e-9:
                raise FundingGap("mother cash unavailable on a declared payment date",{"year":year,"event":event,"cash_raw":cash,"mother_events_completed":records})
        else:
            raise ValueError(kind)
        if retained < -1e-9:
            raise AssertionError("mother legal retained deficit")
        records.append(dict(event,amount=amount,mother_cash_after=cash,mother_retained_after=retained,
            reserve_transfer=reserve,mother_cash_delta=mother_cash_delta,subsidiary_cash_delta=subsidiary_cash_delta,
            consolidated_cash_delta=-amount if kind=="dividend_payment" else 0.0))
    return {"cash":cash,"retained":retained,"gap":gap,"events":records,"reserve_transfer":total_reserve,
            "dividends":sum(e["amount"] for e in records if e["kind"]=="dividend_payment")}


def holder_adapter(records, context, endpoint, terminal_ev):
    """Exact five anniversary buckets and October-31 equity from calendar state."""
    asof=day(context["valuation_date"])
    horizon=day(context["holder_horizon_date"])
    if horizon != anniversary(asof,5):
        raise ValueError("year5 must be the genuine fifth anniversary")
    buckets=[0.0]*5
    payments=[e for row in records for e in row["mother_events"] if e["kind"]=="dividend_payment"]
    declarations=[e for row in records for e in row["mother_events"] if e["kind"]=="dividend_declaration"]
    for event in payments:
        when=day(event["date"])
        if asof < when <= horizon:
            for bucket in range(5):
                if anniversary(asof,bucket) < when <= anniversary(asof,bucket+1):
                    buckets[bucket] += event["amount"]/context["shares"]
                    break
    last=records[-1]
    end=day(last["calendar_end"])
    beginning=date(end.year-1,12,31)
    if not beginning < horizon <= end:
        raise ValueError("horizon must fall in last calendar budget")
    fraction=(horizon-beginning).days/(end-beginning).days
    remainder=1-fraction
    after=sum(e["amount"] for e in payments if horizon < day(e["date"]) <= end)
    before=sum(e["amount"] for e in last["mother_events"] if e["kind"]=="dividend_payment" and day(e["date"])<=horizon)
    cash_h=last["cash_end"]-remainder*last["cash_flow_before_common"]+after
    close(cash_h,last["cash_start"]+fraction*last["cash_flow_before_common"]-before)
    remaining_fcff=last["fcff"]*remainder
    gap_years=years_between(horizon,end)
    ev_h=(terminal_ev+remaining_fcff)/(1+endpoint["discount_rate"])**gap_years
    pending=[e for e in declarations if day(e["date"])<=horizon<day(e["payment_date"])]
    pending_nominal=sum(e["amount"] for e in pending)
    entitled_pv=0.0
    embedded_pv=0.0
    for event in pending:
        claim=event["amount"]/(1+context["cash_yield"])**years_between(horizon,day(event["payment_date"]))
        if day(event["entitlement_date"]) <= horizon:
            entitled_pv += claim
        else:
            embedded_pv += claim
    nci=max(context["nci_book"],context["nci_fraction"]*ev_h)
    stock_equity=ev_h+cash_h+context["illiquid_finance"]-context["debt"]-nci-pending_nominal+embedded_pv
    holder_equity=stock_equity+entitled_pv
    return {"valuation_date":asof.isoformat(),"horizon_date":horizon.isoformat(),"bucket_end_dates":[anniversary(asof,i).isoformat() for i in range(1,6)],
        "distributions_per_share":buckets,"horizon_fraction_in_last_calendar_year":fraction,
        "calendar_year5_ev":terminal_ev,"remaining_calendar_fcff":remaining_fcff,"remaining_time_years":gap_years,
        "operating_ev_at_anniversary":ev_h,"financial_cash_at_anniversary":cash_h,
        "post_horizon_payments_to_calendar_end":after,"declared_unpaid_nominal":pending_nominal,
        "held_dividend_receivable_pv":entitled_pv,"embedded_cum_dividend_claim_pv":embedded_pv,
        "ex_rights_stock_equity":stock_equity,"terminal_holder_equity":holder_equity,
        "terminal_equity_per_share":holder_equity/context["shares"],
        "physical_capital_at_anniversary":last["physical_capital_start"]+fraction*(last["physical_capital_end"]-last["physical_capital_start"]),
        "invested_capital_at_anniversary":last["invested_capital_start"]+fraction*(last["invested_capital_end"]-last["invested_capital_start"]),
        "pending_claims":pending,"payment_events":payments}


def evaluate_path(rows, context, endpoint, stub=None):
    if len(rows)!=5:
        raise ValueError("exactly five complete calendar budgets")
    r,g,roic=endpoint["discount_rate"],endpoint["growth"],endpoint["incremental_roic"]
    if not (r>g>=0 and roic>g and context["shares"]>0):
        raise ValueError("terminal/ownership conditions")
    asof=day(context["valuation_date"])
    cash=context["liquid_finance"]
    initial_cash=cash
    mother_cash=context["mother_available_cash"]
    retained=context["mother_retained"]
    reserve_gap=context["reserve_gap"]
    invested=context["invested_capital"]
    physical=context["physical_capital"]
    initial_invested=invested
    pv_fcff=0.0
    annual_records=[]
    stub_record=None
    if stub is not None:
        if not asof < day(context["stub_upstream_recognition_date"]) <= day(context["stub_upstream_cash_date"]) <= date(asof.year,12,31):
            raise ValueError("stub recognition/receipt dates outside the stub")
        try:
            cash,interest,yield_cash,minority_cash=cash_step(cash,stub,context,context["stub_years"],0.0)
        except FundingGap as exc:
            exc.partial.update({"stage":"stub","completed_annual":[],"stub_input":stub})
            raise
        invested += stub["capex_cash"]-stub["da_nonlease"]+stub["delta_wc"]
        physical += stub["capex_cash"]-stub.get("legacy_capex_payment",0)-stub["da_nonlease"]
        pv_fcff += stub["fcff"]/(1+r)**context["stub_years"]
        amount=context["stub_upstream_budget"]
        provision=reserve_amount(amount,reserve_gap,context,reserve_gap>1e-10)
        reserve_gap=max(0,reserve_gap-provision)
        retained += amount-provision
        mother_cash += amount
        stub_record=dict(stub,cash_end=cash,interest=interest,finance_yield=yield_cash,nci_cash=minority_cash,
            upstream_profit_recognition_date=context["stub_upstream_recognition_date"],upstream_cash_date=context["stub_upstream_cash_date"],
            upstream_budget=amount,mother_cash_delta=amount,subsidiary_cash_delta=-amount,consolidated_upstream_cash_delta=0.0,
            mother_cash_end=mother_cash,mother_retained_end=retained,mother_reserve_transfer=provision)
    for i,row in enumerate(rows):
        mother=None
        try:
            parent_np=row["nopat"]*(1-context["nci_fraction"])
            interest=after_tax_interest(row,context,1.0)
            minority_cash=max(row["nopat"],0)*context["nci_fraction"]
            direct=min(max(parent_np,0),context["direct_parent_cash_profit"])
            # Base direct parent contribution is zero. Fixtures can use it;
            # it joins the same recognition/receipt budget, not consolidated income twice.
            upstream=min(max(parent_np-direct,0)*context["upstream_profit_cap"],
                         max(row["fcff"]-interest-minority_cash-direct,0)*context["upstream_cash_cap"])
            target=max(parent_np*context["payout_target"],0)
            mother_start=mother_cash
            mother=mother_calendar(row["year"],mother_cash,retained,reserve_gap,upstream+direct,target,context)
            mother_cash,retained,reserve_gap=mother["cash"],mother["retained"],mother["gap"]
            dividend=mother["dividends"]
            previous_cash,previous_invested,previous_physical=cash,invested,physical
            cash,interest,yield_cash,minority_cash=cash_step(cash,row,context,1.0,dividend)
            bflow=row["fcff"]+yield_cash-interest-minority_cash
            cal_end=day(context["calendar_year_end_dates"][i])
            if cal_end.year != row["year"]:
                raise ValueError("calendar end does not match operating budget year")
            cal_start=date(cal_end.year-1,12,31)
            paid=0.0
            for event in mother["events"]:
                if event["kind"]=="dividend_payment":
                    paid += event["amount"]
                    fraction=(day(event["date"])-cal_start).days/(cal_end-cal_start).days
                    raw_at_date=previous_cash+bflow*fraction-paid
                    if raw_at_date < -1e-9:
                        raise FundingGap("group liquid funding negative at dated shareholder payment",{"year":row["year"],"date":event["date"],"raw_cash":raw_at_date,"event":event})
            invested += row["capex_cash"]-row["da_nonlease"]+row["delta_wc"]
            physical += row["capex_cash"]-row.get("legacy_capex_payment",0)-row["da_nonlease"]
            time=years_between(asof,cal_end)
            pv_fcff += row["fcff"]/(1+r)**time
            average_capital=(previous_invested+invested)/2
            annual_records.append(dict(row,time_years=time,calendar_end=cal_end.isoformat(),cash_start=previous_cash,cash_end=cash,
                cash_flow_before_common=bflow,bank_interest_after_tax=interest,financial_yield=yield_cash,nci_cash=minority_cash,
                net_finance_end=cash+context["illiquid_finance"]-context["debt"],upstream_budget=upstream,mother_income=upstream+direct,
                mother_cash_start=mother_start,mother_cash_end=mother_cash,mother_reserve_transfer=mother["reserve_transfer"],
                mother_legal_retained=retained,mother_events=mother["events"],actual_common_dividend=dividend,
                distribution_per_share=dividend/context["shares"],invested_capital_start=previous_invested,invested_capital_end=invested,
                physical_capital_start=previous_physical,physical_capital_end=physical,
                net_roic=row["nopat"]/average_capital if average_capital>0 else None))
        except FundingGap as exc:
            exc.partial.update({"completed_annual":annual_records,"stub":stub_record,"failed_year":row["year"],"failed_row":row,
                "mother_available_cash":mother_cash,"mother_legal_retained":retained,
                "failed_mother_events":mother["events"] if mother is not None else [],"no_automatic_financing":True})
            raise
    last=rows[-1]
    margin6=last["ebit_margin"]-endpoint["margin_fade"]
    revenue6=last["revenue"]*(1+g)
    ebit6=revenue6*margin6
    nopat6=ebit6-max(ebit6,0)*last["tax"]
    reinvest=max(nopat6,0)*g/roic
    gap=endpoint["maintenance_gap"]
    fcff6=nopat6-reinvest-gap
    terminal_ev=fcff6/(r-g)
    pv_terminal=terminal_ev/(1+r)**annual_records[-1]["time_years"]
    operating_ev=pv_fcff+pv_terminal
    nci_now=max(context["nci_book"],context["nci_fraction"]*operating_ev)
    nci_terminal=max(context["nci_book"],context["nci_fraction"]*terminal_ev)
    nfa0=initial_cash+context["illiquid_finance"]-context["debt"]
    equity_now=operating_ev+nfa0-nci_now
    calendar_terminal=terminal_ev+cash+context["illiquid_finance"]-context["debt"]-nci_terminal
    dwc6=context["terminal_wc_ratio"]*(revenue6-last["revenue"])
    da6=last["da_nonlease"]*(1+g)
    capex6=da6+reinvest+gap-dwc6
    close(fcff6,nopat6+da6-capex6-dwc6)
    holder=holder_adapter(annual_records,context,endpoint,terminal_ev)
    owner_pv=sum(e["amount"]/(1+r)**years_between(asof,day(e["date"])) for e in holder["payment_events"] if day(e["date"])<=day(context["holder_horizon_date"]))
    owner_pv += holder["terminal_holder_equity"]/(1+r)**5
    capital_change=annual_records[-1]["invested_capital_end"]-annual_records[0]["invested_capital_end"]
    return {"status":"feasible","endpoint":endpoint,"stub":stub_record,"annual":annual_records,
        "net_finance_at_valuation":nfa0,"operating_ev":operating_ev,"pv_fcff":pv_fcff,"pv_terminal":pv_terminal,
        "terminal_share_of_operating_ev":pv_terminal/operating_ev if operating_ev else None,
        "equity_value":equity_now,"value_per_share":equity_now/context["shares"],
        "calendar_terminal_equity":calendar_terminal,"calendar_terminal_equity_per_share":calendar_terminal/context["shares"],
        "terminal_equity_per_share":holder["terminal_equity_per_share"],"holder_adapter":holder,
        "retained_cash_timing_pv_diagnostic_per_share":owner_pv/context["shares"],
        "year6":{"revenue":revenue6,"ebit_margin":margin6,"nopat":nopat6,"growth_reinvestment":reinvest,"maintenance_gap":gap,"delta_wc":dwc6,"da":da6,"capex":capex6,"fcff":fcff6,"ev":terminal_ev,
                 "maintenance_floor_diagnostic":last.get("maintenance_cash",last["da_nonlease"])*(1+g)},
        "cash_conservation_change":cash-initial_cash,"initial_invested_capital":initial_invested,
        "incremental_roic_year1_to_year5":(annual_records[-1]["nopat"]-annual_records[0]["nopat"])/capital_change if abs(capital_change)>1e-9 else None}


def company_path(name, rows, context, endpoint, stub):
    try:
        result=evaluate_path(rows,context,endpoint,stub)
        result["path_name"]=name
        return result
    except FundingGap as exc:
        return {"status":"economically_infeasible","path_name":name,"reason":str(exc),"raw_partial":exc.partial,
                "value_per_share":None,"terminal_equity_per_share":None,"no_fabricated_financing_or_zero_floor":True}

def make_context(data):
    b = data["balance"]
    annual_2026_revenue = data["nine_month_revenue"] + sum(data["q4_estimate"]["product_revenue"])
    op_cash = annual_2026_revenue * data["operating_cash_ratio"]
    total_finance = b["cash"] + b["trading"] + b["current_maturing_finance"] + b["other_current_cd_included"] + b["illiquid_finance"]
    liquid = total_finance - b["illiquid_finance"] - op_cash - b["restricted_guarantee"] - b["declared_dividend_payable"]
    m = data["mother"]
    context = {
        "liquid_finance":liquid, "illiquid_finance":b["illiquid_finance"], "debt":b["bank_debt"],
        "debt_cost":data["bank_debt_pretax_cost"], "cash_yield":data["liquid_after_tax_yield"],
        "shares":data["share_count"], "nci_fraction":data["nci_profit_fraction"], "nci_book":b["nci_book"],
        "mother_retained":m["retained_h1"] - m["h1_dividend_declared_after_h1"],
        "reserve_gap":max(m["statutory_reserve_target"] - m["statutory_reserve"],0),
        "appropriation_rate":m["appropriation_rate"], "appropriation_mode":m["appropriation_mode"],
        "upstream_profit_cap":m["upstream_profit_cap"], "upstream_cash_cap":m["upstream_cash_cap"],
        "payout_target":m["common_payout_target"], "direct_parent_cash_profit":m["direct_parent_cash_profit_assumed"],
        "stub_years":years_between(day(data["valuation_date"]),day(data["calendar_stub_date"])),
        "valuation_date":data["valuation_date"], "holder_horizon_date":data["holder_horizon_date"],
        "calendar_year_end_dates":data["calendar_year_end_dates"],
        "mother_available_cash":m["opening_available_cash_budget"],
        "stub_upstream_budget":m["stub_upstream_budget"],
        "stub_upstream_recognition_date":m["stub_upstream_recognition_date"], "stub_upstream_cash_date":m["stub_upstream_cash_date"],
        "payment_plan":m["payment_plan"], "upstream_schedule":m["upstream_schedule"],
        "terminal_wc_ratio":data["operating_cash_ratio"]+data["incremental_other_wc_ratio"],
        "invested_capital":b["equity_total"] + b["bank_debt"] + b["lease_liability_total"] + b["declared_dividend_payable"]
            - total_finance - b["rou_asset"] + op_cash + b["restricted_guarantee"],
        "physical_capital":b["physical_assets"]
    }
    october = scale_period(data["q4_estimate"], 1.0/3)
    context["liquid_finance"], interest, yield_cash, minority_cash = cash_step(liquid, october, context, years_between(day(data["financial_date"]),day(data["valuation_date"])), 0)
    context["invested_capital"] += october["capex_cash"] - october["da_nonlease"] + october["delta_wc"]
    context["physical_capital"] += october["capex_cash"] - october["legacy_capex_payment"] - october["da_nonlease"]
    return context, dict(october, interest=interest, financial_yield=yield_cash, nci_cash=minority_cash,
                         liquid_before=liquid, liquid_after=context["liquid_finance"], op_cash_reserve=op_cash), annual_2026_revenue


def build_rows(data, scenario=None, gross_shift_all=0.0):
    base = data["base"]
    last_revenue = data["nine_month_revenue"] + sum(data["q4_estimate"]["product_revenue"])
    rows = []
    cumulative_capex_difference = 0.0
    for i, year in enumerate(base["years"]):
        revenues = list(base["product_revenue"][i])
        margins = [v + gross_shift_all for v in base["gross_margin"][i]]
        if scenario:
            revenues = [a*b for a,b in zip(revenues,scenario["product_revenue_factors"][i])]
            margins = [v+scenario["gross_margin_shift"][i] for v in margins]
        item = {k:base[k][i] for k in ("sales_ratio","admin_ratio","rd_ratio","surcharge_ratio","ordinary_loss_ratio",
            "lease_extra_cash_charge","tax","da_nonlease","maintenance_cash","capex_cash","legacy_capex_payment")}
        settlement = base["channel_settlement_cash"][i]
        if scenario:
            item["sales_ratio"] += scenario["sales_ratio_shift"][i]
            item["capex_cash"] = scenario["capex_cash"][i]
            capital_difference = item["capex_cash"] - base["capex_cash"][i]
            # 8% blended incremental depreciation, half-year convention;
            # scenario margins are already after this depreciation burden.
            item["da_nonlease"] += 0.08 * (cumulative_capex_difference + 0.5 * capital_difference)
            item["maintenance_cash"] *= item["da_nonlease"] / base["da_nonlease"][i]
            cumulative_capex_difference += capital_difference
            settlement = scenario["channel_settlement_cash"][i]
            if "tax" in scenario:
                item["tax"] = scenario["tax"][i]
        item.update(year=year,product_revenue=revenues,gross_margin=margins,channel_settlement_cash=settlement)
        item["delta_wc"] = (data["operating_cash_ratio"] + data["incremental_other_wc_ratio"]) * (sum(revenues)-last_revenue) + settlement
        rows.append(operating_metrics(item))
        last_revenue = sum(revenues)
    return rows


def endpoint_from(data, key):
    base = data["base"]
    return dict(base[key], growth=base["terminal_growth"],margin_fade=base["terminal_margin_fade"],maintenance_gap=base["terminal_maintenance_gap"])


def historical_diagnostic(data):
    records = {}
    for year, item in data["history"].items():
        fa = sum(item["financial_assets"])
        op_cash = item["revenue"] * data["operating_cash_ratio"]
        net_capital = item["equity"] + item["bank_debt"] + item["lease"] - fa - item["rou"] + op_cash
        gross_assets = item["assets"] - fa - item["rou"] + op_cash
        ebit = item["revenue"] - sum(item[k] for k in ("cogs","surcharge","sales","admin","rd")) - 0.03
        records[year] = {"net_operating_capital":net_capital,"gross_operating_assets":gross_assets,"normalized_nopat":ebit*0.78}
    avgnet = (records["2024"]["net_operating_capital"]+records["2025"]["net_operating_capital"])/2
    avggross = (records["2024"]["gross_operating_assets"]+records["2025"]["gross_operating_assets"])/2
    records["2025_comparable_return"] = {"normalized_tax":0.22,"rent_adjustment_research_estimate":0.03,
        "net_roic":records["2025"]["normalized_nopat"]/avgnet if avgnet>0 else None,
        "gross_asset_return":records["2025"]["normalized_nopat"]/avggross,
        "warning":"net invested capital small due channel/other operating float; not a sustainable incremental project return"}
    return records


def hand_cases():
    """Expected values independently derived in hand-cases-v3.md; not pre-run proof."""
    fixture={"product_revenue":[100.0],"gross_margin":[0.4],"sales_ratio":0.1,"admin_ratio":0.05,"rd_ratio":0.02,
             "surcharge_ratio":0.01,"ordinary_loss_ratio":0.0,"lease_extra_cash_charge":0.0,"tax":0.25,
             "da_nonlease":3.0,"capex_cash":5.0,"delta_wc":1.0,"legacy_capex_payment":0.0}
    rows=[operating_metrics(dict(fixture,year=2027+i)) for i in range(5)]
    c={"liquid_finance":20.0,"illiquid_finance":0.0,"debt":10.0,"debt_cost":0.1,"cash_yield":0.02,
       "shares":10.0,"nci_fraction":0.0,"nci_book":0.0,"mother_retained":1.0,"reserve_gap":0.5,
       "appropriation_rate":0.1,"appropriation_mode":"cap_at_threshold","upstream_profit_cap":0.75,"upstream_cash_cap":0.9,
       "payout_target":0.6,"direct_parent_cash_profit":1.0,"stub_years":0.0,"terminal_wc_ratio":0.0,
       "invested_capital":30.0,"physical_capital":50.0,"mother_available_cash":0.0,
       "valuation_date":"2026-12-31","holder_horizon_date":"2031-12-31",
       "calendar_year_end_dates":[f"{year}-12-31" for year in range(2027,2032)],
       "stub_upstream_budget":0.0,"stub_upstream_recognition_date":"2026-12-01","stub_upstream_cash_date":"2026-12-15",
       "upstream_schedule":[{"recognition_md":"12-10","cash_md":"12-15","weight":1.0}],
       "payment_plan":[{"declaration_month_day":"12-20","entitlement_month_day":"12-30","payment_month_day":"12-31","weight":1.0}]}
    e={"discount_rate":0.1,"growth":0.0,"incremental_roic":0.2,"margin_fade":0.0,"maintenance_gap":0.0}
    base=evaluate_path(rows,c,e)
    for key,value in (("ebit",22.0),("nopat",16.5),("fcff",13.5),("upstream_budget",10.575),
                      ("mother_reserve_transfer",0.5),("actual_common_dividend",9.9),("cash_end",23.25)):
        close(base["annual"][0][key],value)
    close(base["annual"][-1]["cash_end"],36.91313052)
    close(base["year6"]["ev"],165.0)
    close(base["value_per_share"],16.3627639682)
    close(base["terminal_equity_per_share"],19.191313052)
    if base["holder_adapter"]["distributions_per_share"] != [0.99]*5:
        for value in base["holder_adapter"]["distributions_per_share"]: close(value,0.99)
    # Old, lawful cash can support payout above same-year FCFF/new remittance.
    lower_cash_rows=[operating_metrics(dict(fixture,year=2027+i,capex_cash=10.0)) for i in range(5)]
    old_cash=evaluate_path(lower_cash_rows,dict(c,mother_available_cash=20.0,mother_retained=20.0),e)
    close(old_cash["annual"][0]["fcff"],8.5)
    close(old_cash["annual"][0]["actual_common_dividend"],9.9)
    close(old_cash["annual"][0]["mother_cash_end"],17.175)
    close(old_cash["annual"][0]["cash_end"],18.25)
    # Negative net financial assets are never floored.
    negative=evaluate_path(rows,dict(c,liquid_finance=5.0,debt=50.0),e)
    close(negative["net_finance_at_valuation"],-45.0)
    close(negative["value_per_share"],10.8627639682)
    close(negative["annual"][0]["actual_common_dividend"],8.875)
    # Positive growth + maintenance + NCI + illiquid asset principal.
    growth=evaluate_path(rows,dict(c,illiquid_finance=3,nci_fraction=0.01,nci_book=2,terminal_wc_ratio=0.1),
                         dict(e,discount_rate=0.2,growth=0.1,incremental_roic=0.5,maintenance_gap=0.15))
    close(growth["year6"]["nopat"],18.15)
    close(growth["year6"]["capex"],6.08)
    close(growth["year6"]["fcff"],14.37)
    close(growth["calendar_terminal_equity_per_share"],17.126966386944)
    # Exact anniversary adapter: same nonzero five-year operating chain,
    # zero additional pre-2027 stub flows solely in this closed-form date fixture.
    dated=dict(c,valuation_date="2026-10-31",holder_horizon_date="2031-10-31",mother_available_cash=20.0,mother_retained=20.0,
        payment_plan=[{"declaration_month_day":"10-15","entitlement_month_day":"10-20","payment_month_day":"11-30","weight":1.0}])
    crossing=evaluate_path(rows,dated,e)
    h=crossing["holder_adapter"]
    for actual,expected in zip(h["distributions_per_share"],[0.0,0.99,0.99,0.99,0.99]): close(actual,expected)
    close(h["financial_cash_at_anniversary"],44.5706862029589)
    close(h["declared_unpaid_nominal"],9.9)
    claim=9.9/(1.02)**(30/366)
    expected_ev=(165+13.5*61/365)/(1.1)**(61/366)
    close(h["held_dividend_receivable_pv"],claim)
    close(h["terminal_equity_per_share"],(expected_ev+44.5706862029589-10-9.9+claim)/10)
    if h["horizon_date"]!="2031-10-31": raise AssertionError("not fifth anniversary")
    # Across the same boundary, undeclared future dividend stays in stock cash,
    # whereas declared/entitled future cash is a receivable, not a cash bucket.
    undeclared=evaluate_path(rows,dict(dated,payment_plan=c["payment_plan"]),e)["holder_adapter"]
    close(undeclared["declared_unpaid_nominal"],0.0)
    close(undeclared["financial_cash_at_anniversary"],44.5706862029589)
    # Economic failure preserves three complete periods + raw negative fourth;
    # another completed path remains usable. Assertion/type bugs are not caught.
    loss=dict(fixture,product_revenue=[10],gross_margin=[0.2],sales_ratio=0.2,admin_ratio=0.1,rd_ratio=0,
              surcharge_ratio=0,da_nonlease=0.2,capex_cash=1,delta_wc=0)
    mixed=rows[:2]+[operating_metrics(dict(loss,year=2029+i)) for i in range(3)]
    failed=company_path("hand_funding_gap",mixed,dict(c,liquid_finance=5,debt=50),e,None)
    if failed["status"]!="economically_infeasible" or len(failed["raw_partial"]["completed_annual"])!=3:
        raise AssertionError("partial economic path not retained")
    close(failed["raw_partial"]["cash_closing_raw"],-6.4849322)
    if company_path("hand_other_path",rows,c,e,None)["status"]!="feasible":
        raise AssertionError("other path discarded")
    return {"same_chain_nonzero":"passed","old_mother_cash_above_current_fcff":"passed","negative_net_assets":"passed",
            "positive_growth_nci_principal":"passed","exact_anniversary_crossing_claim":"passed","partial_funding_gap":"passed"}


def produce(data):
    if len(data["calendar_year_end_dates"])!=5:
        raise ValueError("five calendar ends")
    close(data["share_count"]+data["treasury_shares"],data["issued_share_count"])
    close(sum(p["weight"] for p in data["mother"]["upstream_schedule"]),1.0)
    close(sum(p["weight"] for p in data["mother"]["payment_plan"]),1.0)
    close(1-data["mother"]["subsidiary_statutory_profit_holdback"]-data["mother"]["subsidiary_other_profit_holdback"],data["mother"]["upstream_profit_cap"])
    try:
        context,october,annual2026=make_context(data)
    except FundingGap as exc:
        return {"status":"COMMON_INITIAL_BRIDGE_ECONOMICALLY_INFEASIBLE","raw_partial":exc.partial,
                "raw_inputs":data,"return_model":None,"reason":str(exc)}
    stub=scale_period(data["q4_estimate"],2/3)
    rows=build_rows(data)
    low=company_path("core_low",rows,context,endpoint_from(data,"core_low"),stub)
    high=company_path("core_high",rows,context,endpoint_from(data,"core_high"),stub)
    outcomes={}
    for name,assumptions in data["scenarios"].items():
        endpoint={"discount_rate":assumptions["discount_rate"],"growth":assumptions["terminal_growth"],
            "incremental_roic":assumptions["incremental_roic"],"margin_fade":assumptions["terminal_margin_fade"],
            "maintenance_gap":data["base"]["terminal_maintenance_gap"]}
        outcomes[name]=company_path(name,build_rows(data,assumptions),context,endpoint,stub)
    diagnostics={
        "gross_margin_minus_1pp":company_path("gross_margin_minus_1pp",build_rows(data,gross_shift_all=-0.01),context,endpoint_from(data,"core_low"),stub),
        "mother_continues_10pct_reserve":company_path("mother_continues_10pct_reserve",rows,dict(context,appropriation_mode="continue_10pct"),endpoint_from(data,"core_low"),stub),
        "mother_full_first_year_10pct":company_path("mother_full_first_year_10pct",rows,dict(context,appropriation_mode="full_year_until_threshold"),endpoint_from(data,"core_low"),stub),
        "all_issued_shares_no_extra_proceeds":company_path("all_issued_shares",rows,dict(context,shares=data["issued_share_count"]),endpoint_from(data,"core_low"),stub),
        "delayed_upstream_and_no_open_mother_cash":company_path("delayed_upstream",rows,
            dict(context,mother_available_cash=0.0,stub_upstream_budget=1.0,
                 upstream_schedule=[{"recognition_md":"11-30","cash_md":"12-15","weight":1.0}]),endpoint_from(data,"core_low"),stub),
        "other_current_cd_max_per_share":data["balance"]["other_current_cd_upper_sensitivity"]/data["share_count"],
        "october_cash_bridge_plusminus_025_per_share":0.25/data["share_count"]}
    normalized=sum(rows[i]["nopat"] for i in data["base"]["auxiliary_normalized_nopat_years"])/len(data["base"]["auxiliary_normalized_nopat_years"])
    nfa=context["liquid_finance"]+context["illiquid_finance"]-context["debt"]
    auxiliary=[]
    for multiple in data["base"]["auxiliary_multiples"]:
        ev=normalized*multiple
        auxiliary.append((ev+nfa-max(context["nci_book"],ev*context["nci_fraction"]))/context["shares"])
    core_ok=low["status"]==high["status"]=="feasible"
    return_model=None
    if core_ok:
        if low["value_per_share"]>high["value_per_share"]: raise AssertionError("core endpoints reversed")
        return_model={"schema_version":1,"method":"annual_common_equity_irr_v1","currency":"CNY","model_as_of":data["information_cutoff"],
            "base_case_distributions_per_share":low["holder_adapter"]["distributions_per_share"],
            "base_case_terminal_equity_value_range_per_share":{"year_5":{"low":low["terminal_equity_per_share"],"high":high["terminal_equity_per_share"]}}}
    return {"status":"EXECUTED_NOT_CANONICAL_ACCEPTED","task_id":data["task_id"],"information_cutoff":data["information_cutoff"],
        "units":data["unit"],"context":context,"october_estimate_bridge":october,"annual2026_revenue_anchor":annual2026,
        "core_low":low,"core_high":high,"scenarios":outcomes,"diagnostics":diagnostics,
        "historical_return_diagnostic":historical_diagnostic(data),
        "auxiliary":{"normalized_operating_nopat":normalized,"multiples":data["base"]["auxiliary_multiples"],"value_per_share_range":auxiliary},
        "return_model":return_model,"return_model_availability_note":"available" if core_ok else "Core economic funding gap retained; see raw_partial, not a swallowed assertion.",
        "dates_note":"Actual future payment-budget dates feed five anniversary buckets ending2031-10-31. Calendar2031-12-31 EV/cash is bridged back using remaining annual-proxy flows, financial yield/interest, payments and dividend rights. Dates are forecasts, not announced facts; no monthly business model.",
        "cash_note":"Mother can use source-bounded existing cash and retained upstream receipts. Recognition and receipt dates differ. Internal upstream is mother-plus/sub-minus/group-zero. Existing IPO principal remains in equity; existing unpaid dividend deducted once."}
