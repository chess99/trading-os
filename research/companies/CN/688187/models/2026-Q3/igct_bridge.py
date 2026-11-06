from fractions import Fraction

def check(raw, budget):
    principal = Fraction(192070000)
    own = Fraction(7786, 10000)
    common = float(principal * own / 10**9)
    nci = float(principal * (1 - own) / 10**9)
    paths = [("base/main", raw["paths"]["base"]["main"]), ("base/aux", raw["paths"]["base"]["aux"])]
    paths += [("sensitivity/" + x["name"], x["result"]) for x in raw["isolated_sensitivities"]]
    checked = []
    for label, path in paths:
        years, opening = path["annual"], path["opening"]
        state = [(opening["parent_finance"], opening["subs_finance"], opening["finance_nci"], opening["parent_re"], opening["subs_re"], years[0]["financial_target"] * (1 - budget["parent_financial_share"]))]
        for row in years:
            b = row["parent_sub_bridge"]
            state.append((b["parent_finance_closing"], b["subs_finance_closing"], row["financial_closing_nci"], b["parent_re_closing"], b["subs_re_closing"], row["financial_target"] * (1 - budget["parent_financial_share"])))
        margins = [(p - budget["parent_cash_floor_bn"], s - floor - common, n - nci, pr, sr) for p,s,n,pr,sr,floor in state]
        if not all(min(x) >= -1e-9 for x in margins): raise ValueError((label, "IGCT同基准资金约束未满足"))
        checked.append({"path": label, "minimum_subs_margin_bn": min(x[1] for x in margins), "minimum_nci_margin_bn": min(x[2] for x in margins), "D1_D5": path["D1_D5"]})
    return {"total_principal_cny": int(principal), "common_principal_cny": float(principal * own), "NCI_principal_cny": float(principal * (1 - own)), "all_paths_supported_without_changing_D": True, "paths": checked}
