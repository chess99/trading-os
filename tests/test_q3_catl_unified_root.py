"""Current CATL complete independent recurrence and actual owner-payment capacity.

The accepted v7 supersedes the forecast-buyback ten-year synthetic terminal root.
No current producer/checker is changed. The helper is byte-for-byte the frozen
independent source/literal.py, not reconstructed from production formulas.
"""

import hashlib
import json
import lzma
import math
import runpy
from pathlib import Path

import pytest

P = Path(__file__).resolve().parents[1] / "research/companies/CN/300750/models"


@pytest.fixture(scope="module")
def production():
    descriptor = json.loads((P / "2026-Q3-output.json").read_text())
    assert descriptor["artifact_kind"] == "transport_manifest_not_model_result"
    assert descriptor["file"] == "2026-Q3-output.json.xz"
    compressed = (P / descriptor["file"]).read_bytes()
    assert len(compressed) == descriptor["compressed_bytes"]
    assert hashlib.sha256(compressed).hexdigest() == descriptor["compressed_sha256"]
    expanded = lzma.decompress(compressed)
    assert len(expanded) == descriptor["expanded_bytes"]
    assert hashlib.sha256(expanded).hexdigest() == descriptor["expanded_sha256"]
    result = json.loads(expanded)
    assert set(result["models"]) == {"volume", "earnings"}
    return result["models"]


def test_catl_literal_all_scenarios(production, tmp_path):
    helper = Path(__file__).with_name("catl_2026q3_literal.py")
    assert (
        hashlib.sha256(helper.read_bytes()).hexdigest()
        == "5fbea63363b159bde3f30fe9164bc98a96944bcbf959eb3e3ff59f9aa57ed3c7"
    )
    independent = runpy.run_path(str(helper))
    calculate, specs = independent["calculate"], independent["CASES"]
    assert len(specs) == 24
    leaves = rows = cases = 0

    def compare(expected, actual, path):
        nonlocal leaves
        if isinstance(expected, dict):
            assert set(expected) <= set(actual), path
            for key, value in expected.items():
                compare(value, actual[key], path + "/" + key)
        elif isinstance(expected, list):
            assert len(expected) == len(actual), path
            for index, (value, found) in enumerate(zip(expected, actual, strict=True)):
                compare(value, found, path + "/" + str(index))
        else:
            leaves += 1
            if isinstance(expected, (float, int)) and not isinstance(expected, bool):
                assert math.isclose(expected, actual, rel_tol=2e-10, abs_tol=2e-8), (
                    path,
                    expected,
                    actual,
                )
            else:
                assert expected == actual, (path, expected, actual)

    # Complete independently computed annual states are retained, not summarized.
    with lzma.open(tmp_path / "catl-independent-all-cases.json.xz", "wt") as output:
        output.write("{")
        for method_index, method in enumerate(("volume", "earnings")):
            actual = production[method]
            base = calculate(kind=method)
            reference = base["PV"] * 1.095 - base["D"][0]
            remaining = (
                20
                - 3.30315513838
                - sum(
                    [
                        0.19997683436,
                        0.19237993188,
                        0.061019185,
                        0.0499936164,
                        0.7999985385,
                        0.4999467487,
                        0.19998299442,
                        0.053672625,
                    ]
                )
            )
            full_specs = dict(specs)
            for ratio in (0.8, 1.0, 1.2):
                full_specs["conditional_repurchase_" + str(ratio)] = {
                    "buyback": remaining,
                    "buy_price": reference * ratio,
                }
            full_specs["tail240"] = {"n_years": 240}
            assert set(full_specs) == set(actual) and len(full_specs) == 28
            output.write(("," if method_index else "") + json.dumps(method) + ":{")
            for index, (name, kwargs) in enumerate(full_specs.items()):
                expected = base if name == "base" else calculate(kind=method, **kwargs)
                try:
                    compare(expected, actual[name], method + "/" + name)
                except BaseException:
                    with lzma.open(
                        tmp_path / (method + "-" + name + "-failed-literal.json.xz"), "wt"
                    ) as failed:
                        json.dump(expected, failed, allow_nan=False)
                    raise
                rows += len(expected["rows"])
                cases += 1
                output.write(("," if index else "") + json.dumps(name) + ":")
                json.dump(expected, output, ensure_ascii=False, allow_nan=False)
            output.write("}")
        output.write("}")
    assert cases == 56 and rows == 25440
    (tmp_path / "catl-literal-coverage.json").write_text(
        json.dumps({"cases": cases, "annual_rows": rows, "independent_leaves": leaves})
    )


def test_catl_finite_principal_and_actual_tail_capacity(production, tmp_path):
    # Exact frozen reviewer economic loop; only paths/output plumbing is adapted.
    d = {"models": production}
    errors = []
    count = 0

    def eq(a, b, label):
        nonlocal count
        count += 1
        if not math.isclose(a, b, rel_tol=2e-10, abs_tol=2e-7):
            errors.append([label, a, b])

    for method, cases in d["models"].items():
        for name, v in cases.items():
            pr = None
            rate = v["parameters"]["r"]
            if v["feasible"]:
                eq(v["PV"], sum(x["dps"] / (1 + rate) ** x["year"] for x in v["rows"]), name + "PV")
                eq(
                    v["PV"],
                    sum(x / (1 + rate) ** (i + 1) for i, x in enumerate(v["D"]))
                    + v["TV5"] / (1 + rate) ** 5,
                    name + "Y5",
                )
            else:
                assert v["PV"] is None and v["TV5"] is None and v["tail_PV_upper_bound"] is None
            for x in v["rows"]:
                tag = f"{method}/{name}/{x['year']}"
                debt0 = 189.926135 if pr is None else pr["debt_face"]
                eq(x["loan_face"], x["internal_debt"], tag + "internal debt")
                eq(x["loan_carrying"], x["loan_face"] - x["loan_allowance"], tag + "allowance")
                eq(
                    x["common_equity"],
                    x["parent_cash"]
                    + x["source_cash"]
                    + x["remaining_parent_financial_cost"]
                    + x["remaining_source_financial_cost"]
                    + x["fund_remaining_cost"]
                    + x["common_operating_capital"]
                    + x["matched_financial_asset"]
                    - x["debt_face"],
                    tag + "equity",
                )
                eq(
                    x["parent_retained"],
                    x["opening_parent_retained"]
                    + x["parent_legal_profit"]
                    - x["statutory_addition"]
                    - x["voluntary_addition"]
                    - x["dividend"]
                    - x["cancellation_retained_charge"],
                    tag + "RE",
                )
                eq(
                    x["dps"] * x["effective_dividend_budget_shares"],
                    x["dividend"],
                    tag + "distribution",
                )
                eq(x["nci_equity"], x["nci_cash"] + x["nci_operating_capital"], tag + "NCI")
                eq(
                    debt0 - x["actual_parent_principal_paid"] - x["actual_source_principal_paid"],
                    x["debt_face"],
                    tag + "actual repayment",
                )
                eq(
                    x["matched_opening_cost"] - x["matched_disposed_basis"],
                    x["matched_financial_asset"],
                    tag + "cost",
                )
                eq(x["matched_remaining_tax_basis"], x["matched_financial_asset"], tag + "taxbasis")
                eq(
                    x["matched_realised_gain_after_tax"],
                    x["matched_gross_proceeds"]
                    - x["matched_disposed_basis"]
                    - x["matched_realisation_expense"]
                    - x["matched_realisation_tax"],
                    tag + "gain",
                )
                eq(
                    x["matched_realisation_tax"],
                    max(
                        0,
                        x["matched_gross_proceeds"]
                        - x["matched_disposed_basis"]
                        - x["matched_realisation_expense"],
                    )
                    * 0.25,
                    tag + "tax",
                )
                eq(
                    x["net_debt_due"],
                    x["actual_parent_principal_paid"]
                    + x["actual_source_principal_paid"]
                    + x["unpaid_principal"],
                    tag + "due",
                )
                cash_in = (
                    x["opening_parent_cash"]
                    + x["opening_source_cash"]
                    + x["common_owner_cash"]
                    + x["parent_interest_gross"]
                    + x["source_interest_gross"]
                    - x["financial_income_tax"]
                    + x["financial_gross_proceeds"]
                    - x["financial_sale_cost"]
                    - x["financial_sale_tax"]
                    + x["fund_net_receipt"]
                    + x["matched_gross_proceeds"]
                    - x["matched_realisation_expense"]
                    - x["matched_realisation_tax"]
                    + x["matched_interest_net"]
                    - x["actual_parent_principal_paid"]
                    - x["actual_source_principal_paid"]
                    - x["dividend"]
                    - x["repurchase_cash"]
                    - x["repurchase_fee"]
                    + x["employee_transfer_receipt"]
                    + x["option_exercise_receipt"]
                )
                eq(cash_in, x["parent_cash"] + x["source_cash"], tag + "full cash")
                if pr:
                    eq(pr["loan_face"] - x["loan_repayment"], x["loan_face"], tag + "principal")
                assert min(x["parent_cash"], x["source_cash"], x["nci_cash"]) >= -1e-7
                pr = x
            if v["failure_state"]:
                f = v["failure_state"]
                assert min(f["parent_cash"], f["source_cash"]) >= 0
                eq(
                    f["common_equity"],
                    f["parent_cash"]
                    + f["source_cash"]
                    + f["remaining_parent_financial_cost"]
                    + f["remaining_source_financial_cost"]
                    + f["fund_cost"]
                    + f["common_operating_capital"]
                    + f["matched_remaining_cost"]
                    - f["debt_face"],
                    name + "failure equity",
                )
                eq(
                    f["opening_debt_face"]
                    - f["actual_parent_principal_paid"]
                    - f["actual_source_principal_paid"],
                    f["debt_face"],
                    name + "failure face",
                )
                eq(
                    f["net_debt_due"]
                    - f["actual_parent_principal_paid"]
                    - f["actual_source_principal_paid"],
                    f["unpaid_principal"],
                    name + "failure unpaid",
                )

    assert not errors, errors[:10]
    for _method, cases in production.items():
        assert len(cases) == 28
        for _name, case in cases.items():
            if case["feasible"]:
                assert len(case["rows"]) == case["parameters"]["n_years"]
                rate = case["parameters"]["r"]
                eq(
                    case["TV5"],
                    sum(
                        row["dps"] / (1 + rate) ** (row["year"] - 5)
                        for row in case["rows"]
                        if row["year"] > 5
                    ),
                    "actual tail only",
                )
                last = case["rows"][-1]
                eq(
                    sum(row["loan_repayment"] for row in case["rows"]) + last["loan_face"],
                    132.661171,
                    "finite principal",
                )
                for key in (
                    "remaining_parent_financial_cost",
                    "remaining_source_financial_cost",
                    "fund_remaining_cost",
                ):
                    eq(last[key], 0.0, "finite external realization")
            for row in case["rows"]:
                assert row["dividend"] <= max(0.0, row["desired_dividend"]) + 1e-7
                assert (
                    0
                    <= row["dividend"]
                    <= max(0.0, row["parent_retained"] + row["dividend"]) + 1e-7
                )
                assert row["dividend"] <= max(0.0, row["parent_cash"] + row["dividend"]) + 1e-7
                assert row["loan_repayment"] >= -1e-8
            if case["failure_state"]:
                assert not case["feasible"] and case["failure_state"]["unpaid_principal"] > 0
        eq(cases["loan_not_repaid"]["rows"][-1]["loan_face"], 132.661171, "no principal reset")
        eq(cases["loan_not_repaid"]["PV"], cases["base"]["PV"], "no internal face-value award")
        gap = cases["base"]["PV"] - cases["tail240"]["PV"]
        assert 0 <= gap <= cases["tail240"]["tail_PV_upper_bound"]
        assert cases["base"]["tail_PV_upper_bound"] < 1e-9
        assert any(
            a < b - 1e-8
            for a, b in zip(cases["upstream_stress"]["D"], cases["base"]["D"], strict=True)
        )
        assert any(
            a < b - 1e-8
            for a, b in zip(
                cases["financing_distribution_cut"]["D"], cases["base"]["D"], strict=True
            )
        )
        assert cases["structural"]["PV"] < cases["base"]["PV"]
    # The revised volume path need not breach the obsolete13yuan fifth-year
    # prediction. Earnings does; both retain every actual capacity check above.
    assert production["earnings"]["structural"]["D"][-1] < 13
    assert not errors, errors[:10]
    (tmp_path / "catl-economic-coverage.json").write_text(
        json.dumps({"checks": count, "errors": errors})
    )
