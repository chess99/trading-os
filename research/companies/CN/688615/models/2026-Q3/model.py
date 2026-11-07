"""NEW_RECONSTRUCTION. Own full company engine; NOT recovered old bytes.
No I/O or execution at import. CLI authorization belongs to run_attempt.py.
Money/shares in millions; legal known award pools retained as integer inputs.
"""
from copy import deepcopy
from datetime import datetime, timedelta
from math import isfinite


class ModelError(RuntimeError):
    pass


class EconomicInfeasible(ModelError):
    pass


def dt(s):
    return datetime.fromisoformat(s)


def iso(d):
    return d.isoformat()


def add_years(d, n):
    return d.replace(year=d.year + n)


def year_start(y, tz):
    return datetime(y, 1, 1, tzinfo=tz)


def elapsed(a, b, policy="actual_365"):
    if policy == "actual_365":
        return (b - a).total_seconds() / (365 * 86400)
    if policy == "equal_fiscal_year":
        def coord(d):
            s = year_start(d.year, d.tzinfo)
            e = year_start(d.year + 1, d.tzinfo)
            q = (d.month-1) // 3
            qs = datetime(d.year, 3*q+1, 1, tzinfo=d.tzinfo)
            qe = datetime(d.year, 3*q+4, 1, tzinfo=d.tzinfo) if q<3 else e
            return d.year + q/4 + (d-qs).total_seconds()/(qe-qs).total_seconds()/4
        return coord(b) - coord(a)
    raise ModelError("unknown day count")


def discount(a, b, r, p):
    if r <= 0 or b < a:
        raise ModelError("invalid discount request")
    return (1 + r) ** (-elapsed(a, b, p["new_mapping"]["day_count"]))


def near(a, b, tol=1e-7):
    if not isfinite(a) or not isfinite(b) or abs(a-b) > tol * max(1, abs(a), abs(b)):
        raise ModelError(f"identity failure: {a!r} vs {b!r}")


def emit(log, kind, **data):
    if log is not None:
        log(kind, deepcopy(data))


def interpolate(anchors, index):
    if index <= anchors[0][0]:
        return anchors[0][1]
    for (x, y), (xx, yy) in zip(anchors, anchors[1:]):
        if index <= xx:
            return y + (yy-y) * (index-x) / (xx-x)
    return anchors[-1][1]


def factor(revenue, base, target, trigger):
    growth = revenue / base - 1
    return 1.0 if growth >= target else (0.8 if growth >= trigger else 0.0)


def fiscal_budgets(p, method):
    if method not in ("dcf", "epv"):
        raise ModelError("unknown method")
    y0 = p["fy_start"]
    result = {}
    prior = {k: s["fy2026_revenue"] for k, s in p["segments"].items()}
    base_rev = sum(prior.values())
    for y in range(y0, y0 + p["horizon"] + 3):
        i = y-y0
        revenues = {}
        for k, s in p["segments"].items():
            g = s["growth"][min(i-1, len(s["growth"])-1)] if i else 0
            revenues[k] = s["fy2026_revenue"] if method == "epv" or i == 0 else prior[k]*(1+g)
        rev = sum(revenues.values())
        cost_i = 0 if method == "epv" else i
        direct = sum(revenues[k] * interpolate(p["segments"][k]["cash_cost_anchors"], cost_i) for k in revenues)
        ratios = {k: interpolate(a, cost_i) for k, a in p["cost_anchors"].items()}
        # EPV keeps current operating efficiency but not a permanent holiday from future pay refresh.
        ratios["normal_share_compensation"] = interpolate(p["cost_anchors"]["normal_share_compensation"], i)
        expense_keys = ("sales_cash", "rd_cash", "admin_cash", "rent_cash", "normal_share_compensation")
        expenses = {k: ratios[k]*rev for k in expense_keys}
        da = ratios["non_ROU_DA"]*rev
        pretax_before_known_sbc = rev-direct-sum(expenses.values())-da
        tax = max(pretax_before_known_sbc, 0)*p["tax_rate"]
        np_before_known_sbc = pretax_before_known_sbc-tax
        maint = p["maintenance_cash_ratio"]*rev
        growth_cap = 0 if method == "epv" or i == 0 else p["growth_capital_per_revenue_increment"]*max(rev-sum(prior.values()), 0)
        nw = p["operating_nwc"]
        op_cash = p["opening_source"]["required_operating_cash_budget"]*rev/base_rev
        nwc = op_cash+rev*(nw["ar_ratio"]+nw["contract_asset_ratio"]+nw["other_asset_ratio"]-nw["ap_ratio"]-nw["salary_accrual_ratio"])-nw["consumer_contract_liability_ratio"]*sum(revenues[k] for k in nw["consumer_segments"])
        result[y] = dict(year=y, revenues=revenues, revenue=rev, direct_cash_cost=direct,
                         expenses=expenses, da=da, cash_tax=tax, pretax_before_known_sbc=pretax_before_known_sbc,
                         np_before_known_sbc=np_before_known_sbc, maintenance=maint, growth_capital=growth_cap,
                         operating_cash=op_cash, operating_nwc=nwc, cost_ratios=ratios)
        prior = revenues
    return result


def overlap_fraction(a, b, s, e):
    left, right = max(a, s), min(b, e)
    return max((right-left).total_seconds(), 0)/(e-s).total_seconds()


def revenue_fraction(p, fy, a, b, fiscal):
    tz = a.tzinfo
    if fy == p["fy_start"]:
        q4 = datetime(fy, 10, 1, tzinfo=tz)
        end = year_start(fy+1, tz)
        if a < q4:
            # Used only by formal-chain fixtures whose known opening is Jan 1.
            if not p.get("fixture_mode"):
                raise ModelError("no pre-Q4 historical operating forecast allowed")
        else:
            remaining = fiscal[fy]["revenue"]-p["opening_source"]["q3_reported_revenue"]
            if remaining < 0:
                raise EconomicInfeasible("FY26 forecast below already reported 9M revenue")
            return remaining/fiscal[fy]["revenue"]*overlap_fraction(a,b,q4,end)
    q4w = p["fy2026_Q4_revenue_fraction"]
    starts = [datetime(fy, m, 1, tzinfo=tz) for m in (1,4,7,10)] + [year_start(fy+1,tz)]
    weights = [(1-q4w)/3]*3+[q4w]
    return sum(w*overlap_fraction(a,b,s,e) for w,s,e in zip(weights,starts,starts[1:]))


def known_sbc(p, fiscal, a, b):
    if p.get("fixture_mode"):
        return 0.0
    m = p["new_mapping"]
    cut = dt(p["information_cutoff"])
    q4 = datetime(p["fy_start"],10,1,tzinfo=cut.tzinfo)
    fyend = year_start(p["fy_start"]+1,cut.tzinfo)
    # Unknown earlier accounting reversal is not fabricated or applied to reported 9M NP.
    old_pre = m["old_pre_cutoff_Q4_cost_reference"]*overlap_fraction(a,b,q4,fyend) if b <= cut else 0.0
    end = dt(m["old_second_service_end"])
    old_gate = factor(fiscal[p["fy_start"]]["revenue"],m["old_revenue_base"],m["old_second_target"],m["old_second_trigger"])
    remaining_cost = (m["old_future_second_cost_reference"]*m["old_second_remaining_integer"]/
                      m["old_future_reference_batch_integer"]*p["awards"]["personal_retention_budget"]*old_gate)
    old_future = remaining_cost*overlap_fraction(a,b,cut,end)
    # Published prospective schedule is a budget of future service, not a new cash payment.
    new = 0.0
    base = sum(p["awards"]["new_revenue_base_source"])/3
    for ys, amount in p["known_SBC_budget"]["new_plan_by_year"].items():
        y = int(ys)
        s = datetime(y,9,29,tzinfo=cut.tzinfo) if y == p["fy_start"] else year_start(y,cut.tzinfo)
        e = year_start(y+1,cut.tzinfo)
        index = min(max(y-p["fy_start"],0),5)
        gate = factor(fiscal[y]["revenue"],base,p["awards"]["new_target"][index],p["awards"]["new_trigger"][index])
        new += amount*gate*overlap_fraction(a,b,s,e)
    return old_pre+old_future+new


def flow(p, fiscal, a, b):
    if b <= a or (b.year != a.year and b != year_start(a.year+1,a.tzinfo)):
        raise ModelError("flow requires positive within-fiscal-year interval")
    y = a.year
    f = fiscal[y]
    w = revenue_fraction(p,y,a,b,fiscal)
    sbc = known_sbc(p,fiscal,a,b)
    np = f["np_before_known_sbc"]*w-sbc
    da = f["da"]*w
    if y == p["fy_start"] and not p.get("fixture_mode"):
        start = datetime(y,10,1,tzinfo=a.tzinfo)
        end = year_start(y+1,a.tzinfo)
        frac = overlap_fraction(a,b,start,end)
        capex = (p["fy2026_cash_capital_budget"]-p["opening_source"]["q3_reported_cash_capital_spend"])*frac
        o = p["opening_source"]
        initial_nwc = (o["required_operating_cash_budget"]+o["q3_AR"]+o["q3_contract_assets"]+
                       o["other_operating_current_assets_budget"]-o["q3_AP"]-o["q3_salary_accrual"]-o["q3_contract_liabilities"])
        dnw = (f["operating_nwc"]-initial_nwc)*frac
        maintenance = p["maintenance_cash_ratio"]*f["revenue"]*w
        growth = capex-maintenance  # classification residual; total cash capex is binding FY26 budget.
    else:
        frac = overlap_fraction(a,b,year_start(y,a.tzinfo),year_start(y+1,a.tzinfo))
        prev = fiscal[y-1]["operating_nwc"] if y-1 in fiscal else p.get("fixture_opening_nwc",f["operating_nwc"])
        dnw = (f["operating_nwc"]-prev)*frac
        maintenance, growth = f["maintenance"]*w, f["growth_capital"]*w
        capex = maintenance+growth
    fcf = np+sbc+da-capex-dnw
    near(fcf, f["np_before_known_sbc"]*w+da-capex-dnw)
    return dict(a=iso(a),b=iso(b),fiscal_year=y,revenue=f["revenue"]*w,
                np=np,known_sbc=sbc,da=da,cash_tax=f["cash_tax"]*w,
                maintenance=maintenance,growth_capital=growth,capex=capex,dnwc=dnw,fcf=fcf)


def make_awards(p, fiscal):
    if p.get("fixture_awards") is not None:
        return deepcopy(p["fixture_awards"])
    if not p["awards"]["enabled"]:
        return []
    m, aw = p["new_mapping"],p["awards"]
    early = p["early_settlement"]
    result = []
    gate2 = factor(fiscal[p["fy_start"]]["revenue"],m["old_revenue_base"],m["old_second_target"],m["old_second_trigger"])
    for i,q,gate in ((1,m["old_first_qualified_integer"]/1e6,1.0),
                     (2,m["old_second_remaining_integer"]/1e6*gate2*aw["personal_retention_budget"],gate2)):
        key = ("old_first_early_future_date" if i==1 else "old_second_early_date") if early else ("old_first_late_date" if i==1 else "old_second_late_date")
        result.append(dict(id=f"OLD{i}",date=m[key],q=q,strike=m["old_official_strike"],
                           company_gate=gate,eligibility_confirmed=(i==1),specified_date_only=True))
    base = sum(aw["new_revenue_base_source"])/3
    start = dt(m["new_first_early_date"] if early else m["new_first_late_date"])
    for label,total,parts in (("A",aw["new_group_a_quantity"],aw["group_a_tranches"]),
                              ("B",aw["new_group_b_quantity"],aw["group_b_tranches"])):
        for i,part in enumerate(parts):
            year = p["fy_start"]+i
            gate = factor(fiscal[year]["revenue"],base,aw["new_target"][i],aw["new_trigger"][i])
            result.append(dict(id=f"{label}{i+1}",date=iso(add_years(start,i)),
                               q=total*part*gate*aw["personal_retention_budget"],strike=aw["new_strike"],
                               company_gate=gate,eligibility_confirmed=False,specified_date_only=True))
    if p["include_reserved_award"]:
        gate = factor(fiscal[p["fy_start"]]["revenue"],base,aw["new_target"][0],aw["new_trigger"][0])
        result.append(dict(id="RESERVED_BUDGET_ONLY",date=iso(start),q=aw["new_reserved_quantity_not_granted"]*gate*aw["personal_retention_budget"],strike=aw["new_strike"],company_gate=gate,eligibility_confirmed=False,specified_date_only=True))
    return sorted(result,key=lambda x:(x["date"],x["id"]))


def event_schedule(p, awards, start, end):
    tz = start.tzinfo
    cut = dt(p["information_cutoff"])
    events = []
    def add(date,kind,payload=None,priority=10):
        if start < date <= end:
            events.append(dict(date=iso(date),kind=kind,payload=payload,priority=priority))
    for y in range(start.year,end.year+1):
        for month in (1,4,7,10):
            add(datetime(y,month,1,tzinfo=tz),"quarter",priority=0)
        add(year_start(y,tz),"fiscal_close",y-1,priority=1)
        m=p["new_mapping"]
        add(datetime(y,m["payout_month"],m["payout_day"],m["payout_hour"],tzinfo=tz),"dividend",y-1,priority=3)
    for i in range(p["horizon"]):
        y = cut.year+i+1
        date = datetime(y,4,1,12,tzinfo=tz)
        for field,kind,priority in (("private_fund_calls","private_call",4),
                                    ("parent_internal_support","support",5),
                                    ("parent_internal_receipts","internal_receipt",6)):
            amt = p[field][i] if i<len(p[field]) else 0
            if amt:
                add(date,kind,amt,priority)
        for field,kind,month in (("subsidiary_dividends_recognized","sub_declared",6),
                                 ("subsidiary_dividends_received","sub_received",9)):
            amt = p[field][i] if i<len(p[field]) else 0
            if amt:
                add(datetime(y,month,30,12,tzinfo=tz),kind,amt,7)
    for aw in awards:
        add(dt(aw["date"]),"award",aw["id"],8)
    cancel=p["new_mapping"].get("treasury_cancellation_date")
    if cancel:
        add(dt(cancel),"cancel_treasury",None,9)
    for n in range(1,p["horizon"]+1):
        add(add_years(cut,n),"anniversary",n,20)
    add(end,"end",None,30)
    return sorted(events,key=lambda x:(x["date"],x["priority"],str(x["payload"])))


def build_context(p, method):
    cut=dt(p["information_cutoff"])
    end=add_years(cut,p["horizon"])
    fiscal=fiscal_budgets(p,method)
    awards=make_awards(p,fiscal)
    if len({a["id"] for a in awards})!=len(awards):
        raise ModelError("duplicate award id")
    if any(not cut < dt(a["date"]) <= end for a in awards):
        raise ModelError("award event outside forward horizon")
    events=event_schedule(p,awards,cut,end)
    boundaries=sorted(set([cut,end]+[dt(x["date"]) for x in events]))
    pieces=[flow(p,fiscal,a,b) for a,b in zip(boundaries,boundaries[1:])]
    return dict(method=method,cut=cut,end=end,fiscal=fiscal,awards=awards,events=events,pieces=pieces)


def state_base(p, awards):
    o=p["opening_source"]
    return dict(date=p["information_cutoff"],L=o["q3_cash"]+o["q3_trading_financial_assets"]-o["required_operating_cash_budget"],
                J=o["q3_other_financial_assets"]+o["q3_equity_instruments"],P=p["initial_parent_liquid_excess_budget"],
                RE=p["initial_parent_RE_budget"],eligible_RE=p["initial_parent_RE_budget"],
                statutory=p["initial_statutory_reserve_budget"],discretionary=p["initial_discretionary_reserve_budget"],
                registered=p["initial_registered_shares"],treasury=p["initial_treasury_shares"],
                dividend_receivable=p["initial_dividend_receivable"],
                group_np={str(p["fy_start"]):o["q3_reported_parent_attributable_NP"]},parent_np={},
                dividends=[],executions=[],processed_awards=[],strike={a["id"]:a["strike"] for a in awards},
                cumulative_fcf=0.0,cumulative_capex=0.0,cumulative_dnwc=0.0,cumulative_da=0.0)


def balance_check(s):
    for k in ("L","P","J","treasury","registered"):
        if not isfinite(s[k]):
            raise ModelError("nonfinite state "+k)
    if s["L"] < -1e-7 or s["P"] < -1e-7:
        raise EconomicInfeasible("cash exhausted without authorized financing")
    if s["treasury"] < -1e-7 or s["registered"] <= s["treasury"]:
        raise ModelError("invalid share balance")
    if s["P"] > s["L"]+1e-6:
        raise ModelError("parent excess cash cannot exceed group excess cash")


def apply_flow(p,s,f,parent_on=True):
    a,b=dt(f["a"]),dt(f["b"])
    t=elapsed(a,b,p["new_mapping"]["day_count"])
    yield_g=s["L"]*p["financial_cash_yield_after_tax"]*t
    yield_p=s["P"]*p["financial_cash_yield_after_tax"]*t if parent_on else 0
    before=deepcopy(s)
    s["L"]+=f["fcf"]+yield_g
    year=str(f["fiscal_year"])
    s["group_np"][year]=s["group_np"].get(year,0)+f["np"]+yield_g
    pnp=0.0
    if parent_on:
        # Net FCF share already includes cash tax/rent/capex/NWC; none is deducted again.
        s["P"]+=p["parent_profit_cash_share"]*f["fcf"]+yield_p
        pnp=p["parent_profit_cash_share"]*f["np"]+yield_p
        s["RE"]+=pnp
        s["parent_np"][year]=s["parent_np"].get(year,0)+pnp
    s["date"]=f["b"]
    for key,fkey in (("cumulative_fcf","fcf"),("cumulative_capex","capex"),("cumulative_dnwc","dnwc"),("cumulative_da","da")):
        s[key]+=f[fkey]
    near(s["L"]-before["L"],f["fcf"]+yield_g)
    if parent_on:
        near(s["P"]-before["P"],p["parent_profit_cash_share"]*f["fcf"]+yield_p)
    return dict(flow=f,financial_group=yield_g,financial_parent=yield_p,parent_np=pnp,
                parent_cash_basis="NET_FCF",before=before,after=deepcopy(s))


def opening_state(p,c,log):
    s=state_base(p,c["awards"])
    if p.get("fixture_mode"):
        balance_check(s)
        return s,[]
    cut=c["cut"]
    start=dt(p["new_mapping"]["asset_date"])
    pref=dt(p["new_mapping"]["parent_budget_reference"])
    buy=datetime(p["fy_start"],10,27,12,tzinfo=cut.tzinfo)
    points=sorted(set([start,cut,pref,buy]+[year_start(y,cut.tzinfo) for y in range(start.year+1,cut.year+1)]))
    points=[x for x in points if start<=x<=cut]
    bridge=[]
    for a,b in zip(points,points[1:]):
        f=flow(p,c["fiscal"],a,b)
        item=apply_flow(p,s,f,parent_on=a>=pref)
        # Before pref, P/RE are held at independently budgeted pref values, not Q3 facts.
        if b==buy:
            amount=p["opening_source"]["actual_october_buyback_cash_excluding_fees"]
            s["L"]-=amount
            item["buyback_cash"] = amount
            # P budget at Nov1 is already after the disclosed Oct buyback.
        bridge.append(item)
        emit(log,"opening_bridge_interval",**item,state_after=deepcopy(s))
    s["date"]=iso(cut)
    s["eligible_RE"]=s["RE"]
    # Cumulative investment diagnostics start at cutoff, not 9/30.
    for k in ("cumulative_fcf","cumulative_capex","cumulative_dnwc","cumulative_da"):
        s[k]=0.0
    balance_check(s)
    return s,bridge


def lock_amount(p,key,when):
    cut=dt(p["information_cutoff"])
    i=0
    while i+1<len(p[key]) and add_years(cut,i+1)<when:
        i+=1
    return p[key][min(i,len(p[key])-1)] if p[key] else 0


def run_path(p,c,initial,active,log,tag):
    s=deepcopy(initial)
    start=dt(s["date"])
    events=[e for e in c["events"] if dt(e["date"])>start]
    awards={x["id"]:x for x in c["awards"]}
    nodes=[]
    previous=start
    for ev in events:
        now=dt(ev["date"])
        if now>previous:
            f=flow(p,c["fiscal"],previous,now)
            item=apply_flow(p,s,f)
            emit(log,"flow",tag=tag,**item)
            previous=now
            balance_check(s)
        before=deepcopy(s)
        kind,payload=ev["kind"],ev["payload"]
        detail={}
        if kind=="fiscal_close":
            profit=s["parent_np"].get(str(payload),0)
            opening_re=s["RE"]-profit
            taxable_for_reserve=max(profit-max(-opening_re,0),0)
            reserve=min(p["reserve_rate"]*taxable_for_reserve,max(p["reserve_cap_fraction"]*p["nominal_value_per_share"]*s["registered"]-s["statutory"],0))
            s["statutory"]+=reserve
            s["RE"]-=reserve
            s["eligible_RE"]=s["RE"]
            detail=dict(parent_fiscal_profit=profit,reserve_transfer=reserve)
        elif kind=="dividend":
            total_np=s["group_np"].get(str(payload))
            if total_np is None:
                raise ModelError("missing fiscal profit for dividend")
            target=max(total_np,0)*p["payout_ratio"]
            constraints=dict(target=target,parent_RE=max(s["eligible_RE"],0),
                parent_cash=max(s["P"]-lock_amount(p,"parent_locked",now),0),
                group_cash=max(s["L"]-lock_amount(p,"group_locked",now),0))
            amount=min(constraints.values())
            n=s["registered"]-s["treasury"]
            d=amount/n
            s["L"]-=amount;s["P"]-=amount;s["RE"]-=amount;s["eligible_RE"]-=amount
            detail=dict(date=iso(now),total=amount,per_share=d,participating_shares=n,
                        fiscal_profit=total_np,constraints=constraints,binding=[k for k,v in constraints.items() if abs(v-amount)<1e-8])
            s["dividends"].append(detail)
            for key in s["strike"]:
                if key not in s["processed_awards"]:
                    s["strike"][key]=max(s["strike"][key]-d,p["awards"]["minimum_strike"])
        elif kind=="award":
            a=awards[payload]
            q=a["q"]
            executed=bool(active[payload]) and q>0
            k=s["strike"][payload]
            used=min(q,s["treasury"]) if executed else 0
            issued=q-used if executed else 0
            cash=q*k if executed else 0
            s["registered"]+=issued;s["treasury"]-=used;s["L"]+=cash;s["P"]+=cash
            detail=dict(id=payload,date=iso(now),q=q,strike=k,active=executed,eligible_confirmed=a.get("eligibility_confirmed",False),
                        participating_before=before["registered"]-before["treasury"],treasury_delivered=used,new_registered=issued,employee_cash=cash)
            s["executions"].append(detail);s["processed_awards"].append(payload)
            near((s["registered"]-s["treasury"])-(before["registered"]-before["treasury"]),q if executed else 0)
        elif kind=="private_call":
            s["L"]-=payload;s["J"]+=payload
            s["P"]-=payload*p["new_mapping"]["parent_private_call_share"]
            near(s["L"]+s["J"],before["L"]+before["J"])
        elif kind=="support":
            s["P"]-=payload  # Intragroup; no second deduction from group L.
        elif kind=="internal_receipt":
            s["P"]+=payload
        elif kind=="sub_declared":
            s["dividend_receivable"]+=payload;s["RE"]+=payload
            y=str(now.year);s["parent_np"][y]=s["parent_np"].get(y,0)+payload
        elif kind=="sub_received":
            if payload>s["dividend_receivable"]+1e-8:
                raise ModelError("receipt exceeds previously recognized dividend receivable")
            s["P"]+=payload;s["dividend_receivable"]-=payload
        elif kind=="cancel_treasury":
            s["registered"]-=s["treasury"];s["treasury"]=0.0
            near(s["registered"]-s["treasury"],before["registered"]-before["treasury"])
        elif kind not in ("quarter","anniversary","end"):
            raise ModelError("unknown event "+kind)
        s["date"]=iso(now)
        balance_check(s)
        node=dict(event=ev,before=before,after=deepcopy(s),detail=detail)
        nodes.append(node)
        emit(log,"event",tag=tag,**node)
    return dict(initial=deepcopy(initial),final=deepcopy(s),nodes=nodes)


def operating_value(p,c,when,r,g):
    if not r>g:
        raise ModelError("nonpositive terminal discount spread")
    explicit=0.0
    for f in c["pieces"]:
        a,b=dt(f["a"]),dt(f["b"])
        if b<=when:
            continue
        relevant=f if a>=when else flow(p,c["fiscal"],when,b)
        explicit+=relevant["fcf"]*discount(when,b,r,p)
    last=c["fiscal"][c["end"].year]
    terminal_g=0.0 if c["method"]=="epv" else g
    # Known grants expire before this horizon. Ongoing refresh remains in ordinary expense.
    np=last["np_before_known_sbc"]*(1+terminal_g)
    da=last["da"]*(1+terminal_g)
    maint=last["maintenance"]*(1+terminal_g)
    growth=np*terminal_g/p["terminal_incremental_roic"]
    terminal_cash=np+da-maint-growth
    terminal_value=terminal_cash/(r-terminal_g)
    tvpv=terminal_value*discount(when,c["end"],r,p)
    return dict(explicit=explicit,terminal_pv=tvpv,total=explicit+tvpv,
                terminal_cash=terminal_cash,terminal_reinvestment=growth,
                terminal_nopat=np,terminal_g=terminal_g,terminal_date=iso(c["end"]))


def financial_value(p,s):
    return s["L"]+p["private_asset_value_fraction"]*s["J"]-p["financial_value_haircut"]-p["minority_equity_claim_budget"]


def price_path(p,c,path,r,g):
    costs=[]
    rows=[]
    for node in reversed(path["nodes"]):
        if node["event"]["kind"]!="award":
            continue
        row=deepcopy(node["detail"])
        s=node["before"]
        when=dt(row["date"])
        o=operating_value(p,c,when,r,g)
        later=sum(x["signed_cost"]*discount(when,dt(x["date"]),r,p) for x in costs)
        e=o["total"]+financial_value(p,s)-later
        n,q,k=row["participating_before"],row["q"],row["strike"]
        signed=q*(e-n*k)/(n+q) if q else 0.0
        wanted=q>0 and e>n*k
        actual_cost=signed if row["active"] else 0.0
        row.update(operating=o,financial=financial_value(p,s),later_claims_pv=later,
                   equity_before_this_claim=e,signed_if_executed=signed,signed_cost=actual_cost,
                   wanted=wanted,compatible=(row["active"]==wanted),
                   executed_value_per_share=(e+q*k)/(n+q) if q else e/n)
        if not row["active"]:
            near(row["employee_cash"],0);near(actual_cost,0)
        else:
            near(actual_cost,q*(row["executed_value_per_share"]-k))
        costs.append(row);rows.append(row)
    return list(reversed(rows))


def solve(p,c,initial,r,g,log,tag,seed=None,forced=False):
    ids=[a["id"] for a in c["awards"] if dt(a["date"])>dt(initial["date"])]
    active={i:(bool(seed[i]) if seed is not None and i in seed else False) for i in ids}
    if forced:
        active={a["id"]:a["q"]>0 for a in c["awards"] if a["id"] in ids}
    seen=set()
    for iteration in range(p["new_mapping"]["max_branch_iterations"]):
        key=tuple(active[i] for i in ids)
        if key in seen:
            raise ModelError("exercise fixed-point cycle; no economic null substitution")
        seen.add(key)
        emit(log,"branch_iteration_start",tag=tag,iteration=iteration,active=active)
        path=run_path(p,c,initial,active,log,f"{tag}/iteration-{iteration}")
        claims=price_path(p,c,path,r,g)
        wanted={row["id"]:row["wanted"] for row in claims}
        emit(log,"branch_iteration_evaluation",tag=tag,iteration=iteration,claims=claims,wanted=wanted)
        if forced or wanted==active:
            return dict(path=path,claims=claims,active=active,iterations=iteration+1,
                        all_compatible=all(x["compatible"] for x in claims),forced=forced)
        active=wanted
    raise ModelError("exercise fixed-point iteration cap reached")


def value_at(p,c,state,claims,r,g):
    when=dt(state["date"])
    o=operating_value(p,c,when,r,g)
    future=[x for x in claims if dt(x["date"])>when]
    claim_pv=sum(x["signed_cost"]*discount(when,dt(x["date"]),r,p) for x in future)
    finance=financial_value(p,state)
    n=state["registered"]-state["treasury"]
    common=o["total"]+finance-claim_pv
    return dict(date=state["date"],operating=o,financial=finance,rights_pv=claim_pv,
                common_equity=common,participating_shares=n,per_share=common/n,
                financial_components=dict(L=state["L"],J=state["J"],private_value_fraction=p["private_asset_value_fraction"],
                                          haircut=p["financial_value_haircut"],minority_claim=p["minority_equity_claim_budget"]),
                future_claims=future)


def checkpoint(path,n):
    found=[x["after"] for x in path["nodes"] if x["event"]["kind"]=="anniversary" and x["event"]["payload"]==n]
    if len(found)!=1:
        raise ModelError("missing/duplicate anniversary checkpoint")
    return deepcopy(found[0])


def endpoint(p,c,base,r,g,log,tag):
    cp=checkpoint(base["path"],5)
    original_claims=price_path(p,c,base["path"],r,g)
    tail_rows=[x for x in original_claims if dt(x["date"])>dt(cp["date"])]
    replay=not all(x["compatible"] for x in tail_rows)
    if replay:
        tail=solve(p,c,cp,r,g,log,tag,seed=base["active"],forced=p["force_all_exercise"])
        prefix=[x for x in base["path"]["nodes"] if dt(x["event"]["date"])<=dt(cp["date"])]
        path=dict(initial=base["path"]["initial"],final=tail["path"]["final"],nodes=deepcopy(prefix)+tail["path"]["nodes"])
        claims=price_path(p,c,path,r,g)
        iterations=tail["iterations"]
    else:
        path=deepcopy(base["path"]);claims=original_claims;iterations=0
    if checkpoint(path,5)!=cp:
        raise ModelError("endpoint changed frozen five-year state")
    prefix_claims=[x for x in claims if dt(x["date"])<=dt(cp["date"])]
    tail_claims=[x for x in claims if dt(x["date"])>dt(cp["date"])]
    result=dict(r=r,g=g,tail_replayed=replay,tail_iterations=iterations,
                prefix_locked=True,prefix_claims=prefix_claims,tail_claims=tail_claims,
                current_unconditional_eligible=all(x["compatible"] for x in claims),
                tail_compatible=all(x["compatible"] for x in tail_claims),
                current=value_at(p,c,path["initial"],claims,r,g),
                year5=value_at(p,c,cp,claims,r,g),checkpoint=cp,path=path)
    if not result["tail_compatible"] and not p["force_all_exercise"]:
        raise ModelError("endpoint tail failed internal consistency")
    emit(log,"endpoint_complete",tag=tag,result=result)
    return result


def run_case(p,method="dcf",log=None):
    c=build_context(p,method)
    emit(log,"fiscal_budgets",method=method,budgets=c["fiscal"],awards=c["awards"])
    initial,bridge=opening_state(p,c,log)
    r=p["discount_rate"];g=0.0 if method=="epv" else p["terminal_growth"]
    base=solve(p,c,initial,r,g,log,"base",forced=p["force_all_exercise"])
    cp=checkpoint(base["path"],5)
    current=value_at(p,c,initial,base["claims"],r,g)
    y5=value_at(p,c,cp,base["claims"],r,g)
    distributions=[]
    for i in range(1,6):
        a,b=add_years(c["cut"],i-1),add_years(c["cut"],i)
        distributions.append(sum(x["per_share"] for x in cp["dividends"] if a<dt(x["date"])<=b))
    endpoints=[]
    for i,(rr,gg) in enumerate(p["endpoint_pairs"]):
        endpoints.append(endpoint(p,c,base,rr,0.0 if method=="epv" else gg,log,f"endpoint-{i}"))
    first=checkpoint(base["path"],1)
    delta_np=c["fiscal"][dt(cp["date"]).year]["np_before_known_sbc"]-c["fiscal"][dt(first["date"]).year]["np_before_known_sbc"]
    investment=(cp["cumulative_capex"]-first["cumulative_capex"])-(cp["cumulative_da"]-first["cumulative_da"])+(cp["cumulative_dnwc"]-first["cumulative_dnwc"])
    result=dict(status="NEW_EXECUTION_RESULT_NOT_OLD_PASS",method=method,information_cutoff=p["information_cutoff"],
                current=current,year5=y5,checkpoint=cp,distributions=distributions,dividend_records=cp["dividends"],
                current_unconditional_eligible=base["all_compatible"],base=base,endpoints=endpoints,
                opening_bridge=bridge,fiscal_budgets=c["fiscal"],awards=c["awards"],
                current_effective_company_factor={a["id"]:a["company_gate"] for a in c["awards"]},
                incremental_capital_diagnostic=dict(start=first["date"],end=cp["date"],profit_delta=delta_np,
                    net_investment=investment,ratio=delta_np/investment if investment>0 else None,
                    status="MEANINGFUL_BUDGET_RATIO" if investment>0 else "NONPOSITIVE_DENOMINATOR_NOT_EVIDENCE_OF_INFINITE_ROIC"),
                limitations=["specified-date deterministic exercise; not full optimal waiting option",
                    "fractional quantities are conditional expected economic shares, not legal registration",
                    "parent cash/net profit share and Q3-to-cutoff flows are budgets",
                    "financial principal not double-capitalized with financial income",
                    "endpoint false denotes action-policy inconsistency, not zero business value"])
    emit(log,"case_complete",result=result)
    return result
