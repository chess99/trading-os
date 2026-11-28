"""运行 python 2026-H1.py，在同目录重建截至2026年11月27日的美元船队现金及港元每股结果。"""
from pathlib import Path
import json
from math import isclose

directory = Path(__file__).resolve().parent
inputs = json.loads((directory / "2026-H1-input.json").read_text())
reported = inputs["reported"]
estimate = inputs["cutoff_estimates"]
fx = inputs["hkd_per_usd"]
shares = inputs["million_shares"]
special = reported["future_special_hkd"]
special_usd = shares * special / fx
opening_surplus = (
    reported["cash_and_deposits"] + reported["funds"] * estimate["fund_recovery"]
    - reported["bank_debt"] - reported["minority_equity"]
    + estimate["volume_since_june"] * (estimate["freight_since_june"] - estimate["net_cash_cost_since_june"])
    - estimate["capex_since_june"] - shares * reported["paid_interim_hkd"] / fx
    - estimate["operating_cash_floor"] - special_usd
)
commitments = inputs["commitment_payments"]
assert isclose(sum(commitments) + estimate["of_which_commitments_paid"],
               reported["committed_vessels"] + reported["committed_depots"])

def cash_available(volume, freight, net_cost, capex, working):
    return volume * (freight - net_cost) - capex - working

def pv(amount, t, rate):
    return amount / (1 + rate) ** t

assert cash_available(2, 100, 70, 20, 5) == 35
assert isclose(pv(110, 1, 0.1), 100)

def run(case):
    p = inputs["base"] | case
    reserve, diluted = opening_surplus, shares
    cash_dividends, free_cash = [], []
    for year, payment in enumerate(commitments):
        diluted *= 1 + inputs["annual_share_dilution"]
        cash = cash_available(p["vol"][year], p["freight"][year], p["cost"][year],
                              payment + p["other_capex"][year], p["growth_working_capital"][year])
        dividend = max(0, cash * p["payout"])
        previous = reserve
        reserve += cash - dividend
        assert isclose(previous + cash, reserve + dividend) and reserve >= 0
        free_cash.append(cash)
        cash_dividends.append(dividend * fx / diluted)
    # 全周期稳态箱量不再扩张，留存现金不计利息，既有船队持续支付替换开支。
    normalized = cash_available(p["vol"][-1], p["steady_rate"], p["steady_cost"], p["steady_capex"], 0)
    long_run_cost = (1 + p["discount"]) * (1 + inputs["annual_share_dilution"]) - 1
    terminal = (normalized / long_run_cost + reserve) * fx / diluted
    special_pv = pv(special, reported["special_days"] / 365, p["discount"])
    terminal_pv = pv(terminal, 5, p["discount"])
    value = special_pv + sum(pv(c, y, p["discount"]) for y, c in enumerate(cash_dividends, 1)) + terminal_pv
    cash_dividends[0] += special
    return dict(value=round(value, 2), terminal=round(terminal, 4), terminal_share=round(terminal_pv/value, 3),
                distributions=[round(c, 4) for c in cash_dividends], free_cash=[round(c, 2) for c in free_cash],
                retained_usd=round(reserve, 2), steady_owner_cash=round(normalized, 2))

cases = {name:run(case) for name, case in inputs["cases"].items()}
assert [v["value"] for v in cases.values()] == sorted(v["value"] for v in cases.values())
low, high = cases["base_low"], cases["base_high"]
assert low["distributions"] == high["distributions"]
book_equity = reported["parent_equity"] + estimate["net_income_since_june"] - shares * (special + reported["paid_interim_hkd"]) / fx
book = inputs["book_check"]
book_prices = []
for unit_profit, rate in zip(book["net_income_per_teu"], book["equity_cost"]):
    roe = unit_profit * book["volume"] / book_equity
    justified_pb = roe / ((1 + rate) * (1 + inputs["annual_share_dilution"]) - 1)
    book_prices.append(round(justified_pb * book_equity * fx / shares + pv(special, reported["special_days"]/365, rate), 2))
observed_cost = reported["h1_freight"] - (
    reported["h1_cash_from_operations"] - reported["h1_interest_received"] + reported["h1_bank_interest_paid"]
    - reported["h1_lease_principal"] + reported["h1_jv_dividend"] - reported["h1_jv_tax"] - reported["h1_minority_profit"]
) / reported["h1_volume"]
stress = run(inputs["cases"]["base_low"] | {"steady_rate":inputs["cases"]["base_low"]["steady_rate"] - 25})
output = dict(symbol=inputs["symbol"], report_period=inputs["report_period"],
              value_range=dict(low=low["value"], high=high["value"], currency="HKD"),
              return_model=dict(schema_version=1, method="annual_common_equity_irr_v1", currency="HKD", model_as_of=inputs["as_of"],
                                base_case_distributions_per_share=low["distributions"],
                                base_case_terminal_equity_value_range_per_share={"year_5":{"low":low["terminal"],"high":high["terminal"]}}),
              cases=cases, opening_surplus_after_special_usd=round(opening_surplus, 2), adjusted_book_usd=round(book_equity,2),
              secondary_pb_range_hkd=book_prices, h1_net_cash_cost=round(observed_cost, 2),
              steady_freight_minus_25_low_hkd=stress["value"])
(directory / "2026-H1-output.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
