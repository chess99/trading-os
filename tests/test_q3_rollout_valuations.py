"""独立复算新一批Q3核心端点和支配性敏感性，不导入正式模型。"""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "research/companies/CN"


def result(ticker):
    return json.loads((ROOT / ticker / "models/2026-Q3-output.json").read_text())


@pytest.mark.parametrize("margin,rate,key", [(0, .10, "core"), (.01, .095, "margin")])
def test_hikvision_independent_cash_and_value(margin, rate, key):
    actual = result("002415")
    main, innovation = 70., 33.
    cash = 36.60138445169 - 4.
    debt = 3.11165646664 + 1.09053677814 + .86492007394 + .31397661151
    dividends = []
    for year in range(1, 11):
        previous = main + innovation
        main *= 1 + (.04 if year <= 5 else .03)
        innovation *= 1 + (.12 if year <= 5 else [.08, .07, .06, .05, .04][year - 6])
        revenue = main + innovation
        profit = main * (.175 + margin) + innovation * (.14 + margin)
        capex = [2.2, 1.6, 1.][year - 1] if year <= 3 else .007 * revenue
        investment = .5 * (revenue - previous) + capex - (1.5 if year <= 2 else 0)
        financial = max(cash - 10 * previous / 103, 0) * .015 - debt * .03
        dividend = .65 * (profit + financial)
        repayment = min(debt, 2.)
        debt -= repayment
        cash += profit - investment + financial - dividend - repayment
        dividends.append(dividend)
    terminal = profit * 1.02 * (1 - .02 / .15) / (rate - .02)
    terminal += cash - debt - 10 * revenue / 103 + (1.56698632401 + .67280655052) * .9
    value = (sum(d / (1 + rate) ** t for t, d in enumerate(dividends, 1))
             + terminal / (1 + rate) ** 10) / 9.16487155
    expected = (actual["cases"]["base"]["low"]["value_per_share"] if key == "core"
                else actual["margin_sensitivity"]["0.01"])
    assert value == pytest.approx(expected, abs=1e-9)


@pytest.mark.parametrize("margin,rate,key", [(.18, .10, "core_low"), (.17, .095, "margin_minus_100bp")])
def test_fuyao_independent_cash_and_value(margin, rate, key):
    actual = result("600660")[key]
    cash = 21.487115845 + 1.009542675 - .689662926
    debt = sum([9.848754943, 3.709805867, 5.081237775, 1.499759929,
                .297915057, .041716237, 2.083572932])
    previous = 46.5
    dividends = []
    for revenue, capex, depreciation in zip(
        [47, 50, 53, 56, 58.8], [6.3, 6, 5.7, 5.3, 5], [3, 3.3, 3.5, 3.7, 3.9], strict=True,
    ):
        profit = revenue * margin + (cash * .02 - debt * .03) * .8
        free_cash = profit + depreciation - capex - .12 * (revenue - previous)
        dividend = min(.6 * profit, free_cash)
        dividends.append(dividend)
        cash += free_cash - dividend
        previous = revenue
    nopat, operating_value = 58.8 * margin, 0.
    for year, growth in enumerate([.04, .035, .03, .0275, .025], 1):
        nopat *= 1 + growth
        operating_value += nopat * (1 - growth / .15) / (1 + rate) ** year
    operating_value += nopat * 1.025 * (1 - .025 / .15) / (rate - .025) / (1 + rate) ** 5
    terminal = (operating_value + cash - debt - .08 * 58.8) / 2.609743532
    value = sum(d / (1 + rate) ** t for t, d in enumerate(dividends, 1)) / 2.609743532
    value += terminal / (1 + rate) ** 5
    assert value == pytest.approx(actual["current_value"], abs=1e-9)
    assert terminal == pytest.approx(actual["terminal_per_share"], abs=1e-9)
