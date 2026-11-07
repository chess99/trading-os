import baseline
import cash_replay as cash

def calculate(inputs):
    base = cash.replay(baseline.run(baseline.assumptions()))
    lo = cash.replay(baseline.run(baseline.assumptions(rate=.115, price=.97)))
    hi = cash.replay(baseline.run(baseline.assumptions(rate=.095, price=1.03)))
    holder_low = cash.replay(baseline.run(baseline.assumptions()), rate=.115)
    holder_high = cash.replay(baseline.run(baseline.assumptions()), rate=.095)
    cases = {"base": base, "low": lo, "high": hi, "holder_low": holder_low, "holder_high": holder_high}
    value = {"low": lo["value"], "high": hi["value"], "currency": "CNY"}
    d, low, high = base["dps5"], holder_low["terminal5"], holder_high["terminal5"]
    holder = {"base_case_distributions_per_share": d, "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": low, "high": high}}}
    return value, holder, cases
