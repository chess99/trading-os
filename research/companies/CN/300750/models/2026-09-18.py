"""CATL 2026-09-18 research model; money in CNY 100m, shares in 100m.

Run: python research/companies/CN/300750/models/2026-09-18.py
No quotes, IRR, trading thresholds, or network calls.
The companion report distinguishes facts from research assumptions.
"""
from dataclasses import dataclass, replace
import json
import math


@dataclass(frozen=True)
class Case:
    first_profit: float = 850.0
    tenth_profit: float = 1800.0
    incremental_equity_return: float = 0.20
    terminal_growth: float = 0.03
    terminal_equity_return: float = 0.15
    excess_cash: float = 1000.0
    diluted_shares: float = 46.5

    def path(self):
        if not all(math.isfinite(x) for x in vars(self).values()):
            raise ValueError("All inputs must be finite.")
        if min(self.first_profit, self.tenth_profit,
               self.incremental_equity_return,
               self.terminal_equity_return, self.diluted_shares) <= 0:
            raise ValueError("Earnings, returns and shares must be positive.")
        if not 0 <= self.terminal_growth < self.terminal_equity_return:
            raise ValueError("Terminal growth must leave positive distributable cash.")
        if self.excess_cash < 0:
            raise ValueError("Excess debt cannot silently be treated as cash.")
        growth = (self.tenth_profit / self.first_profit) ** (1 / 9) - 1
        earnings = [self.first_profit * (1 + growth) ** t for t in range(10)]
        # End-of-year investment supports the following year's earnings.
        invested = [(earnings[t + 1] - earnings[t]) /
                    self.incremental_equity_return for t in range(9)]
        invested += [earnings[-1] * self.terminal_growth /
                     self.terminal_equity_return]
        cash = [e - i for e, i in zip(earnings, invested)]
        return growth, earnings, invested, cash


def valuation(case, cost, cash_overrides=None):
    if not math.isfinite(cost) or cost <= case.terminal_growth:
        raise ValueError("Discount rate must exceed terminal growth.")
    growth, earnings, invested, cash = case.path()
    if cash_overrides is not None:
        cash = list(cash_overrides)
        if len(cash) != 10 or not all(math.isfinite(x) for x in cash):
            raise ValueError("Ten finite annual cash flows are required.")
    terminal = (earnings[-1] * (1 + case.terminal_growth) *
                (1 - case.terminal_growth / case.terminal_equity_return) /
                (cost - case.terminal_growth))
    pv_cash = sum(f / (1 + cost) ** (t + 1) for t, f in enumerate(cash))
    pv_terminal = terminal / (1 + cost) ** 10
    return {
        "cost": cost, "profit_growth_y1_to_y10": growth,
        "value_per_share": (pv_cash + pv_terminal + case.excess_cash) /
                           case.diluted_shares,
        "terminal_share_of_operating_pv": pv_terminal / (pv_cash + pv_terminal),
        "terminal_at_year10": terminal,
    }


def holder_model(case, costs=(0.10, 0.095, 0.09)):
    _, earnings, invested, economic_cash = case.path()
    dividends = [round(e * 0.5 / case.diluted_shares, 2) for e in earnings[:5]]
    balance = case.excess_cash
    cash_interest = []
    for f, d in zip(economic_cash[:5], dividends):
        interest = balance * 0.02
        cash_interest.append(interest)
        balance += interest + f - d * case.diluted_shares
    outputs = []
    for cost in costs:
        tv10 = valuation(case, cost)["terminal_at_year10"]
        operating5 = (sum(economic_cash[t] / (1 + cost) ** (t - 4)
                          for t in range(5, 10)) + tv10 / (1 + cost) ** 5)
        tv5 = (operating5 + balance) / case.diluted_shares
        holder_pv = sum(d / (1 + cost) ** (t + 1) for t, d in enumerate(dividends))
        holder_pv += tv5 / (1 + cost) ** 5
        outputs.append({"cost": cost, "terminal_equity_per_share_year5": tv5,
                        "pv_with_five_year_actual_distribution_timing": holder_pv})
    # June equity calibrated for distributions and disclosed repurchases;
    # this is not an audited September balance sheet.
    equity0 = 3793.54 - 64.88 - 11.47
    operating_equity0 = equity0 - case.excess_cash
    equity5 = operating_equity0 + sum(invested[:5]) + balance
    bridge5 = (equity0 + sum(earnings[:5]) + sum(cash_interest) -
               sum(dividends) * case.diluted_shares)
    assert abs(equity5 - bridge5) < 1e-8, "Equity bridge must reconcile."
    return {
        "annual_distributions_per_share": dividends,
        "year5_excess_cash": balance,
        "five_year_net_reinvestment": sum(invested[:5]),
        "calibrated_initial_common_equity": equity0,
        "calibrated_year5_common_equity": equity5,
        "terminal_scenarios": outputs,
    }


def results():
    base = Case()
    growth, earnings, invested, cash = base.path()
    structural = Case(750, 1000, 0.12, 0.02, 0.10, 500)
    optimistic = Case(950, 2400, 0.25, 0.03, 0.18, 1200)
    cyclical_cash = cash.copy()
    for t in (0, 1):
        cyclical_cash[t] -= earnings[t] * 0.15  # No fictitious capex saving.
    holder = holder_model(base)
    assert holder["annual_distributions_per_share"] == [9.14, 9.93, 10.8, 11.74, 12.76]
    assert 289 < valuation(base, 0.10)["value_per_share"] < 291
    assert 342 < valuation(base, 0.09)["value_per_share"] < 345
    return {
        "units": "money CNY 100m; shares 100m; per-share figures CNY",
        "base_inputs": vars(base),
        "base_path": [{"year": t + 1, "profit": earnings[t],
                       "net_reinvestment": invested[t],
                       "economic_cash": cash[t]} for t in range(10)],
        "base": [valuation(base, r) for r in (0.10, 0.095, 0.09)],
        "cyclical": [valuation(base, r, cyclical_cash) for r in (0.10, 0.09)],
        "structural": [valuation(structural, r) for r in (0.11, 0.10)],
        "optimistic": [valuation(optimistic, r) for r in (0.10, 0.09)],
        "capital_return_sensitivity": [
            {"incremental_equity_return": q,
             "value_per_share": valuation(replace(base, incremental_equity_return=q),
                                           0.095)["value_per_share"]}
            for q in (0.12, 0.15, 0.20, 0.25)],
        "excess_cash_sensitivity": [
            {"excess_cash": c,
             "value_per_share": valuation(replace(base, excess_cash=c),
                                           0.095)["value_per_share"]}
            for c in (0, 500, 1000, 1500)],
        "secondary_pe": {"earnings_including_cash_income": 870,
                         "multiples": [16, 18],
                         "values": [870 / 46.5 * p for p in (16, 18)]},
        "holder": holder,
    }


if __name__ == "__main__":
    print(json.dumps(results(), ensure_ascii=False, indent=2, allow_nan=False))
