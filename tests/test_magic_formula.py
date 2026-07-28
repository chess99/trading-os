from __future__ import annotations

import datetime as dt

import pytest

CUTOFF = dt.datetime(2026, 7, 28, 12, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))


def _company(ticker: str, *, industry: str = "消费电子") -> dict[str, object]:
    return {
        "symbol": f"CN:{ticker}",
        "ticker": ticker,
        "name": f"公司{ticker}",
        "industry": industry,
        "market_cap_cny": 1000.0,
        "as_of": "2026-07-22",
    }


def _income(ticker: str, year: int, **changes: object) -> dict[str, object]:
    value: dict[str, object] = {
        "SECURITY_CODE": ticker,
        "NOTICE_DATE": f"{year + 1}-03-31T00:00:00+08:00",
        "UPDATE_DATE": f"{year + 1}-03-31T00:00:00+08:00",
        "OPERATE_PROFIT": 120.0,
        "FE_INTEREST_EXPENSE": 10.0,
        "FINANCE_EXPENSE": 99.0,
        "INVEST_INCOME": 10.0,
        "FAIRVALUE_CHANGE_INCOME": 5.0,
        "ASSET_DISPOSAL_INCOME": 2.0,
        "OTHER_INCOME": 3.0,
    }
    value.update(changes)
    return value


def _balance(ticker: str, year: int, **changes: object) -> dict[str, object]:
    value: dict[str, object] = {
        "SECURITY_CODE": ticker,
        "NOTICE_DATE": f"{year + 1}-03-31T00:00:00+08:00",
        "UPDATE_DATE": f"{year + 1}-03-31T00:00:00+08:00",
        "TOTAL_CURRENT_ASSETS": 200.0,
        "TOTAL_CURRENT_LIAB": 100.0,
        "FIXED_ASSET": 100.0,
        "CIP": 10.0,
        "MONETARYFUNDS": 20.0,
        "SHORT_LOAN": 10.0,
        "SHORT_BOND_PAYABLE": 0.0,
        "NONCURRENT_LIAB_1YEAR": 0.0,
        "LONG_LOAN": 50.0,
        "BOND_PAYABLE": 0.0,
        "LEASE_LIAB": 5.0,
        "PERPETUAL_BOND_PAYBALE": 99.0,
        "MINORITY_EQUITY": 20.0,
        "OTHER_EQUITY_TOOL": 30.0,
        "PREFERRED_SHARES": 7.0,
    }
    value.update(changes)
    return value


def _build(companies: list[dict[str, object]], *, latest=None):
    from trading_os.research_assets.magic_formula import build_magic_formula_snapshot

    years = (2023, 2024, 2025)
    return build_magic_formula_snapshot(
        companies=companies,
        income_records_by_year={
            year: [_income(str(company["ticker"]), year) for company in companies]
            for year in years
        },
        balance_records_by_year={
            year: [_balance(str(company["ticker"]), year) for company in companies]
            for year in years
        },
        latest_balance_records=latest,
        latest_balance_date="2026-03-31" if latest is not None else None,
        generated_at=CUTOFF,
        market_snapshot_sha256="a" * 64,
        source="test",
    )


def test_normalized_formula_removes_nonoperating_income_and_builds_ev_without_double_count():
    latest = [_balance("000001", 2025, MONETARYFUNDS=40.0)]
    result = _build([_company("000001")], latest=latest)

    item = result["items"][0]
    assert item["normalized_ebit_cny"] == pytest.approx(110.0)
    assert item["enterprise_value_cny"] == pytest.approx(1075.0)
    assert item["earnings_yield"] == pytest.approx(110.0 / 1075.0)
    assert item["return_on_tangible_capital"] == pytest.approx(110.0 / 200.0)
    assert item["classic_combined_rank"] == 1
    assert "cash_deduction_requires_company_level_restriction_check" in item["reason_codes"]


def test_financials_are_excluded_and_cyclicals_are_routed_to_specialist():
    result = _build(
        [
            _company("000001", industry="银行Ⅱ"),
            _company("000002", industry="煤炭开采"),
        ]
    )

    assert result["items"][0]["symbol"] == "CN:000002"
    assert result["items"][0]["eligible_for_nonfinancial_lens"] is False
    assert result["excluded"] == [
        {
            "symbol": "CN:000001",
            "reason_code": "magic_formula_incompatible_business_model",
            "detail": "银行",
        }
    ]


def test_nonpositive_operating_capital_is_structurally_excluded():
    company = _company("000001")
    years = (2023, 2024, 2025)
    from trading_os.research_assets.magic_formula import build_magic_formula_snapshot

    result = build_magic_formula_snapshot(
        companies=[company],
        income_records_by_year={year: [_income("000001", year)] for year in years},
        balance_records_by_year={
            year: [
                _balance(
                    "000001",
                    year,
                    TOTAL_CURRENT_ASSETS=10.0,
                    TOTAL_CURRENT_LIAB=500.0,
                    FIXED_ASSET=1.0,
                    CIP=0.0,
                )
            ]
            for year in years
        },
        generated_at=CUTOFF,
        market_snapshot_sha256="b" * 64,
        source="test",
    )

    assert result["items"] == []
    assert result["excluded"][0]["reason_code"] == "insufficient_positive_normalized_history"


def test_future_restatement_is_not_used_and_symbol_breaks_ties_stably():
    companies = [_company("000002"), _company("000001")]
    years = (2023, 2024, 2025)
    incomes = {
        year: [
            row
            for company in companies
            for row in (
                _income(str(company["ticker"]), year),
                _income(
                    str(company["ticker"]),
                    year,
                    UPDATE_DATE="2026-08-01T00:00:00+08:00",
                    OPERATE_PROFIT=9999.0,
                ),
            )
        ]
        for year in years
    }
    from trading_os.research_assets.magic_formula import build_magic_formula_snapshot

    result = build_magic_formula_snapshot(
        companies=companies,
        income_records_by_year=incomes,
        balance_records_by_year={
            year: [_balance(str(company["ticker"]), year) for company in companies]
            for year in years
        },
        generated_at=CUTOFF,
        market_snapshot_sha256="c" * 64,
        source="test",
    )

    assert [item["symbol"] for item in result["items"]] == ["CN:000001", "CN:000002"]
    assert all(item["normalized_ebit_cny"] == pytest.approx(110.0) for item in result["items"])


def test_unknown_exchange_uses_a_share_ticker_prefix_without_silent_drop():
    from automation.scripts.build_magic_formula_snapshot import _secucode

    assert _secucode({"ticker": "302132", "exchange": "UNKNOWN"}) == "302132.SZ"


def test_near_zero_capital_is_routed_to_quality_lens_and_roc_is_winsorized():
    company = _company("000001")
    years = (2023, 2024, 2025)
    from trading_os.research_assets.magic_formula import build_magic_formula_snapshot

    tiny_capital = {
        year: [
            _balance(
                "000001",
                year,
                TOTAL_CURRENT_ASSETS=100.5,
                MONETARYFUNDS=20.0,
                TOTAL_CURRENT_LIAB=100.0,
                SHORT_LOAN=10.0,
                FIXED_ASSET=9.6,
                CIP=0.0,
            )
        ]
        for year in years
    }
    result = build_magic_formula_snapshot(
        companies=[company],
        income_records_by_year={year: [_income("000001", year)] for year in years},
        balance_records_by_year=tiny_capital,
        generated_at=CUTOFF,
        market_snapshot_sha256="d" * 64,
        source="test",
    )

    item = result["items"][0]
    assert item["return_on_tangible_capital"] > 10
    assert item["ranking_return_on_tangible_capital"] == 2.0
    assert item["eligible_for_nonfinancial_lens"] is False
    assert "near_zero_operating_capital_requires_quality_lens" in item["reason_codes"]
