"""当前资本现金与权益计算核；经营输入由同次实际计算生成。"""
import copy
SEGMENTS = ("core", "colipu", "retail")
EPS = 1e-8
FUNDING_LABELS = {
    "PARENT_INTERNAL_SETTLEMENT_SHORTFALL":"母体内部结算资金不足",
    "PARENT_ASSUMED_BUFFER_SHORTFALL":"母体自定流动性缓冲不足",
    "GROUP_ASSUMED_BUFFER_SHORTFALL":"集团自定流动性缓冲不足",
    "GROUP_OPERATING_FINANCING_GAP":"经营投入存在实际融资缺口",
    "PARENT_OPERATING_OR_CAPITAL_ACTION_FUNDING_GAP":"母体经营或资本动作缺少已落实资金"
}
def series_value(values, year):
    return values[min(year - 1, len(values) - 1)]

def cash_ownership_bridge(inputs, config):
    """ONE asset classification for primary/auxiliary; no free-standing NCI haircut."""
    p = inputs["opening"]["segments"]["colipu"]
    common = p["ownership"]
    operating = p["revenue"] * p["cash_ratio"]
    seasonal_total = config["seasonal_cash_common"] / common
    excess = config["colipu_excess_cash"]
    gross = operating + seasonal_total + excess
    colipu_nci = gross * (1 - common)
    other_nci = config["other_nci_financial_assets"]
    group_assets = inputs["history"]["q3"]["cash"] + inputs["history"]["q3"]["trading_financial_assets"]
    assert excess >= 0 and other_nci >= 0
    assert gross + inputs["opening"]["parent_liquid_proxy"] <= group_assets + EPS
    assert abs(gross * common + colipu_nci - gross) < EPS
    assert abs(operating * common + config["seasonal_cash_common"] + excess * common - gross * common) < EPS
    return {"colipu_operating_cash_total": operating, "colipu_seasonal_cash_total": seasonal_total,
            "colipu_excess_cash_total": excess, "colipu_gross_financial_assets_total": gross,
            "colipu_common_financial_assets": gross * common,
            "colipu_nci_financial_assets": colipu_nci, "other_nci_financial_assets": other_nci,
            "group_nci_financial_assets": colipu_nci + other_nci,
            "remaining_group_assets_after_colipu_and_parent_proxy": group_assets - gross - inputs["opening"]["parent_liquid_proxy"],
            "classification": "Same gross cash, required operating/seasonal cash and excess cash in both methods; all seasonal buffer allocated to Colipu; other NCI rights nonnegative."}

def opening_bridge(inputs, config):
    h = inputs["history"]
    q = h["q3"]
    ownership = cash_ownership_bridge(inputs, config)
    group_assets = q["cash"] + q["trading_financial_assets"]
    known_after_q3_buyback = q["buyback_spend_oct15"] - q["buyback_spend_sep"]
    operating_cash = sum(p["revenue"] * p["cash_ratio"] * p["ownership"]
                         for p in inputs["opening"]["segments"].values())
    reserve = operating_cash + config["seasonal_cash_common"] + config["restricted_operating_cash"]
    free = group_assets - known_after_q3_buyback - ownership["group_nci_financial_assets"] - config["common_debt"] - reserve
    return {
        "group_financial_assets_q3": group_assets, "cash_ownership_classification": ownership,
        "known_post_q3_treasury_purchase": known_after_q3_buyback,
        "noncommon_financial_assets_estimate": ownership["group_nci_financial_assets"],
        "common_bank_debt_deducted": config["common_debt"],
        "operating_cash_already_capitalised": operating_cash,
        "seasonal_buffer_common": config["seasonal_cash_common"],
        "restricted_cash_in_operating_capital": config["restricted_operating_cash"],
        "total_required_common_cash": reserve,
        "group_buffer_mobilisation_upper_bound": reserve - config["restricted_operating_cash"],
        "opening_excess_net_financial_assets": free,
        "other_nonoperating_investments_value": q["other_investments_book"] * config["other_investments_recovery"],
        "lease_debt_deducted": 0.0,
        "lease_reason": "Full cash rent expensed in operating earnings every year, so no second lease principal deduction.",
        "remaining_employee_buyback": config["buyback_total_plan"] - q["buyback_spend_oct15"],
        "parent_free_liquidity_proxy": inputs["opening"]["parent_liquid_proxy"] - inputs["opening"]["parent_required_liquid"]
    }

def funding_state(parent_cash, group_cash, *, parent_buffer=0, group_buffer=0,
                  parent_before_internal_settlement=None):
    """Classify available EXTRA cash versus policy reserves; never create financing.
    Reserve amounts are an upper-bound diagnostic, not permission to spend them.
    Parent-only trouble does not prove consolidated operating EV is destroyed.
    """
    parent_before = parent_cash if parent_before_internal_settlement is None else parent_before_internal_settlement
    group_upper = group_cash + group_buffer
    parent_upper = parent_cash + parent_buffer
    issues = []
    if group_upper < -EPS:
        issues.append("GROUP_OPERATING_FINANCING_GAP")
    elif group_cash < -EPS:
        issues.append("GROUP_ASSUMED_BUFFER_SHORTFALL")
    if parent_cash < -EPS:
        if parent_before >= -EPS:
            issues.append("PARENT_INTERNAL_SETTLEMENT_SHORTFALL")
        elif parent_before + parent_buffer < -EPS:
            issues.append("PARENT_OPERATING_OR_CAPITAL_ACTION_FUNDING_GAP")
        else:
            issues.append("PARENT_ASSUMED_BUFFER_SHORTFALL")
    ready = not issues
    true_gap = any(x in issues for x in ("GROUP_OPERATING_FINANCING_GAP", "PARENT_OPERATING_OR_CAPITAL_ACTION_FUNDING_GAP"))
    if ready:
        operating_status = "SUPPORTED"
        reason = "普通分配前，经营投入、研究缓冲与计划结算均已具备资金。"
    elif true_gap:
        operating_status = "CONDITIONAL_UNFUNDED_OPERATING_OR_CAPITAL_ACTION_PATH"
        reason = "即使按可移动缓冲上界检验，现有经营投入或资本动作仍有资金缺口；融资或行动调整尚未落实，不假设免费资金。"
    elif "GROUP_ASSUMED_BUFFER_SHORTFALL" in issues:
        operating_status = "CONDITIONAL_ON_EXPLICIT_BUFFER_RELAXATION"
        reason = "未显示集团总资金必然不足，但既定运行及季节性缓冲未达到；需先明确缓冲调整与重建安排，不能把条件诊断直接当作已闭合价值。"
    else:
        operating_status = "GROUP_OPERATING_EV_NOT_INVALIDATED_BY_PARENT_LIQUIDITY"
        reason = "母体结算或自定流动性安排未具备资金。这本身不否定集团经营EV，但实际付款时点及可动用资产仍有条件。"
    return {"classification": issues[0] if issues else "FUNDED_BEFORE_D", "all_issues": issues,
            "payment_path_ready": ready, "true_operating_or_capital_action_financing_gap": true_gap,
            "operating_value_status": operating_status, "reason": reason,
            "group_extra_cash": group_cash, "group_cash_upper_bound_including_movable_buffer": group_upper,
            "group_gross_financing_shortfall": max(-group_upper,0),
            "group_policy_buffer_shortfall": max(-group_cash,0),
            "parent_extra_cash": parent_cash, "parent_cash_upper_bound_including_buffer": parent_upper,
            "parent_before_internal_settlement": parent_before,
            "parent_internal_settlement_shortfall": max(-parent_cash,0) if parent_before >= -EPS else 0,
            "buffer_draw_assumed": False, "new_financing_assumed": False}

def distribute(parent_cash, group_cash, retained, parent_profit, group_profit, payout,
               *, parent_buffer=0, group_buffer=0, parent_before_internal_settlement=None):
    """Formal payment gate. D limitation is distinct from an unresolved funding path."""
    requested = max(group_profit, 0) * payout
    legal = max(retained + parent_profit, 0)
    funding = funding_state(parent_cash, group_cash, parent_buffer=parent_buffer,
                            group_buffer=group_buffer, parent_before_internal_settlement=parent_before_internal_settlement)
    if not funding["payment_path_ready"]:
        return {"feasible": False, "requested": requested, "paid": None,
                "funding_state": funding, "reason": funding["reason"]}
    paid = min(requested, legal, max(parent_cash, 0), max(group_cash, 0))
    constrained = paid + EPS < requested
    return {"feasible": True, "requested": requested, "paid": paid,
            "classification": "ORDINARY_D_CONSTRAINED" if constrained else "ORDINARY_D_PAID_AS_BUDGETED",
            "funding_state": funding, "legal_capacity": legal, "parent_cash_capacity": parent_cash,
            "group_cash_capacity": group_cash, "constrained": constrained,
            "parent_cash_after": parent_cash - paid, "group_cash_after": group_cash - paid,
            "retained_after": retained + parent_profit - paid}

def valuation_acceptance(ledger, diagnostic_equity, future_equity, shares):
    """Formal contract != conditional business valuation. No parameter rescue or zero-cost finance."""
    supported = ledger["feasible"]
    issue = ledger.get("funding_state")
    return {"current_equity_contract_eligible": supported, "holder_contract_eligible": supported,
            "current_value_per_share": diagnostic_equity / shares if supported else None,
            "conditional_equity_diagnostic_per_share": diagnostic_equity / shares,
            "year5_equity_per_share": future_equity / shares if supported and future_equity is not None else None,
            "operating_value_status": "SUPPORTED" if supported else issue["operating_value_status"],
            "contract_status": "ACCEPTABLE_FUNDING_PATH" if supported else "CONDITIONAL_NOT_FORMAL_CONTRACT",
            "reason": "普通D下调已联动留存现金，不因此否定经营EV。" if supported else issue["reason"],
            "no_automatic_ev_writeoff": True}

def holder_ledger(inputs, config, rows, bridge):
    o = inputs["opening"]
    free = bridge["opening_excess_net_financial_assets"]
    parent_free = bridge["parent_free_liquidity_proxy"]
    retained = o["parent_retained_earnings_floor"]
    ledger = []
    initial = funding_state(parent_free, free, parent_buffer=o["parent_required_liquid"],
                            group_buffer=bridge["group_buffer_mobilisation_upper_bound"])
    if not initial["payment_path_ready"]:
        return {"feasible":False,"ledger":ledger,"funding_state":initial,"reason":initial["reason"],"failure_year":0}
    grant = config["buyback_total_plan"] / config["employee_grant_years"]
    for year in range(1, 6):
        row = rows[year - 1]
        core = row["segments"]["core"]
        group_interest = max(free, 0) * o["financial_yield_after_tax"]
        parent_interest = max(parent_free, 0) * o["financial_yield_after_tax"]
        pbt = core["ebit_after_rent"] * o["parent_core_pretax_fraction"]
        parent_tax = max(pbt, 0) * series_value(config["parent_tax"], year)
        parent_op_profit = pbt - parent_tax
        parent_investment = core["investment_cash_net_of_da"] * o["parent_capital_fraction"]
        parent_fcf = parent_op_profit - parent_investment
        buyback = bridge["remaining_employee_buyback"] if year == 1 else 0.0
        extra_transfer = series_value(config["parent_extra_internal_payment"], year)
        upstream = series_value(config["parent_sub_dividend_receipt"], year)
        assert upstream == 0, "No unverified future upstream dividend admitted in this version"
        parent_pre_d = parent_free + parent_fcf + parent_interest + upstream - buyback - extra_transfer
        group_pre_d = free + row["common_fcff"] + group_interest - buyback
        # Stock delivery is not new share issuance. Treasury cash is counted once;
        # budget noncash grant amortisation reduces parent legal/accounting profit and payout target only.
        parent_profit = parent_op_profit + parent_interest - grant
        common_profit = row["common_nopat"] + group_interest - grant
        charge = max(parent_profit, 0) * o["statutory_reserve_charge_rate"]
        gate = distribute(parent_pre_d, group_pre_d, retained, parent_profit - charge,
                          common_profit, o["ordinary_payout_budget"],
                          parent_buffer=o["parent_required_liquid"] + o["parent_capital_fraction"] * (core["operating_cash"] - o["segments"]["core"]["revenue"] * o["segments"]["core"]["cash_ratio"]),
                          group_buffer=sum(v["operating_cash"] * o["segments"][k]["ownership"] for k,v in row["segments"].items()) + config["seasonal_cash_common"],
                          parent_before_internal_settlement=parent_pre_d + extra_transfer)
        item = {"year": year, "opening_group_free": free, "opening_parent_free": parent_free,
                "parent_operating_profit": parent_op_profit, "parent_cash_fcf": parent_fcf,
                "parent_financial_yield": parent_interest, "group_financial_yield": group_interest,
                "common_accounting_profit_budget": common_profit,
                "noncash_employee_grant_expense_budget": grant, "buyback_cash": buyback,
                "employee_cash_proceeds": 0, "extra_parent_to_subsidiary_settlement": extra_transfer,
                "subsidiary_upstream_dividend_cash": upstream,
                "parent_legal_profit_budget": parent_profit, "reserve_charge": charge,
                "group_fcff": row["common_fcff"], "payment_gate": gate}
        ledger.append(item)
        if not gate["feasible"]:
            return {"feasible": False, "ledger": ledger, "reason": gate["reason"], "funding_state":gate["funding_state"], "failure_year":year}
        free, parent_free, retained = gate["group_cash_after"], gate["parent_cash_after"], gate["retained_after"]
        assert abs(free - (item["opening_group_free"] + row["common_fcff"] + group_interest - buyback - gate["paid"])) < EPS
        assert abs(parent_free - (item["opening_parent_free"] + parent_fcf + parent_interest - buyback - extra_transfer - gate["paid"])) < EPS
        assert parent_free <= free + EPS, "Mother liquidity cannot exceed total common discretionary pool"
    return {"feasible": True, "ledger": ledger, "end_group_free": free,
            "end_parent_free": parent_free, "end_parent_retained": retained,
            "distributions_per_share": [x["payment_gate"]["paid"] / inputs["shares"] for x in ledger]}

def operating_value_at(rows, config, year):
    """Independent state date: Y0 or Y5; Y5 is not current value rolled forward."""
    assert year in (0, 5)
    values = {}
    for s in SEGMENTS:
        r = config["discount"][s]
        g = config["terminal_growth"][s]
        assert r > g
        interim = sum(rows[t - 1]["segments"][s]["common_fcff"] / (1 + r) ** (t - year)
                      for t in range(year + 1, 11))
        terminal_row = rows[10]["segments"][s]
        flat_grant = terminal_row.get("common_grant_nopat", 0.0)
        terminal = (terminal_row["common_fcff"] - flat_grant) / (r - g) + flat_grant / r
        terminal_pv = terminal / (1 + r) ** (10 - year)
        values[s] = {"explicit_period_pv": interim, "terminal_pv": terminal_pv,
                     "terminal_value_at_year10": terminal, "value": interim + terminal_pv}
    return {"segments": values, "total": sum(x["value"] for x in values.values()),
            "terminal_pv_total": sum(x["terminal_pv"] for x in values.values())}

def run_case(inputs, name, saved, event=None):
    event = event or {}
    inputs = copy.deepcopy(inputs)
    # Compatibility key names stay historical; event metadata supplies the new source date.
    delta = event.get('paid_increment_CNY', 0.0) / 1e8
    fees = event.get('incremental_fee_CNY', 0.0) / 1e8
    inputs['history']['q3']['buyback_spend_oct15'] += delta
    inputs['opening']['parent_liquid_proxy'] -= delta + fees
    inputs['history']['q3']['cash'] -= fees
    config = copy.deepcopy(saved['config'])
    rows = copy.deepcopy(saved['operating_rows'])
    bridge = opening_bridge(inputs, config)
    ledger = holder_ledger(inputs, config, rows, bridge)
    current_op = operating_value_at(rows, config, 0)
    future_op = operating_value_at(rows, config, 5)
    # Repurchases are a real common-equity outflow; no share-count cancellation benefit.
    repurchase_pv = bridge["remaining_employee_buyback"] / (1 + config["discount"]["core"])
    equity = current_op["total"] + bridge["opening_excess_net_financial_assets"] + bridge["other_nonoperating_investments_value"] - repurchase_pv
    future = future_op["total"] + ledger["end_group_free"] + bridge["other_nonoperating_investments_value"] if ledger["feasible"] else None
    acceptance = valuation_acceptance(ledger, equity, future, inputs["shares"])
    capital_checks = {}
    for s in SEGMENTS:
        a, b = rows[0]["segments"][s], rows[4]["segments"][s]
        denominator = b["total_operating_capital"] - a["total_operating_capital"]
        capital_checks[s] = {"year1_revenue": a["revenue"], "year5_revenue": b["revenue"],
            "year1_nopat": a["nopat"], "year5_nopat": b["nopat"],
            "year1_capital": a["total_operating_capital"], "year5_capital": b["total_operating_capital"],
            "year1_to_year5_incremental_return": ((b["nopat"] - a["nopat"]) / denominator) if abs(denominator) > EPS else None,
            "five_year_maintenance": sum(x["segments"][s]["maintenance_capex"] for x in rows[:5]),
            "five_year_growth_and_upgrade": sum(x["segments"][s]["growth_fixed_capex"] + x["segments"][s]["upgrade_capex"] for x in rows[:5]),
            "five_year_cash_rent": sum(x["segments"][s]["cash_rent"] for x in rows[:5]),
            "five_year_research": sum(x["segments"][s]["research_expense_cash"] for x in rows[:5]),
            "capital_caveat": "Forecast not observed ROIC. Colipu needs additional common seasonal reserve outside segment table; fixed capital is not assumed liquid on decline."}
    return {"name": name, "scenario_definition": inputs["cases"][name], "config": config,
            "opening_bridge": bridge, "operating_rows": rows, "capital_checks": capital_checks,
            "current_operating_value": current_op, "current_equity": equity if acceptance["current_equity_contract_eligible"] else None,
            "diagnostic_equity_before_funding_acceptance": equity,
            "current_value_per_share": acceptance["current_value_per_share"],
            "conditional_equity_diagnostic_per_share": equity / inputs["shares"], "valuation_acceptance":acceptance,
            "future_operating_value_year5": future_op,
            "holder_ledger": ledger, "year5_equity": future,
            "year5_equity_per_share": future / inputs["shares"] if future is not None else None,
            "current_terminal_pv_fraction": current_op["terminal_pv_total"] / equity,
            "remaining_buyback_pv": repurchase_pv}

def auxiliary_from_saved(saved_aux, old_cases, new_cases, shares):
    """Unchanged earnings/ROE inputs; only the exact shared cash bridge changes."""
    out = copy.deepcopy(saved_aux)
    for side in ('low','high'):
        name = 'core_' + side
        old, new = old_cases[name], new_cases[name]
        a, b = old['opening_bridge'], new['opening_bridge']
        delta = (b['opening_excess_net_financial_assets'] - a['opening_excess_net_financial_assets']) - (new['remaining_buyback_pv'] - old['remaining_buyback_pv'])
        out[side]['cash_ownership_classification'] = b['cash_ownership_classification']
        if delta:
            out[side]['equity'] += delta
            out[side]['per_share'] = out[side]['equity'] / shares
    return out

def holder_endpoints(saved_endpoint, old_base, new_cases, shares):
    """Saved endpoint operating value is fixed; replay base cash and original PV formula."""
    out = copy.deepcopy(saved_endpoint)
    new_base = new_cases['base']
    ledger = new_base['holder_ledger']
    current_ready = all(new_cases[n]['valuation_acceptance']['current_equity_contract_eligible']
                        for n in ('core_low','base','core_high'))
    holder_ready = (new_base['valuation_acceptance']['holder_contract_eligible']
                    and ledger['feasible'] and len(ledger['ledger']) == 5
                    and len(ledger.get('distributions_per_share', [])) == 5)
    out['current_contract_eligible'] = current_ready
    out['holder_contract_eligible'] = holder_ready
    out['terminal_same_base_state'] = holder_ready
    if not holder_ready:
        out['year5_low'] = out['year5_high'] = None
        out['five_year_cash_realisation_pv'] = {side:None for side in ('low','high')}
        out['unavailable_reason'] = ledger.get('reason', 'Incomplete five-year holder payment path')
        return out
    delta = ledger['end_group_free'] - old_base['holder_ledger']['end_group_free']
    for key in ('year5_low','year5_high'):
        if delta: out[key] += delta / shares
    holder_pv = {}
    for side, terminal, rate in (
        ('low',out['year5_low'],new_cases['core_low']['config']['discount']['core']),
        ('high',out['year5_high'],new_cases['core_high']['config']['discount']['core'])):
        # Exact numerical ordering from original render_candidate lines553-559.
        holder_pv[side] = sum(x / (1 + rate) ** year for year,x in enumerate(ledger['distributions_per_share'],1)) + terminal / (1 + rate) ** 5
    out['five_year_cash_realisation_pv'] = holder_pv
    return out
