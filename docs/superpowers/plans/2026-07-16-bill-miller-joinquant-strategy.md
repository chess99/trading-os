# Bill Miller JoinQuant Strategy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a single-file JoinQuant strategy that ranks all historical A-shares with three Miller-inspired fundamental models, constructs a concentrated constrained portfolio, and can be locally tested without a JoinQuant runtime.

**Architecture:** Keep all production logic in one platform-copyable file, but isolate pandas/numpy-only calculations from JoinQuant API boundary functions. The platform layer fetches point-in-time universe, annual fundamentals, valuation, industry, and price data; pure functions convert those inputs into features, scores, selections, and target weights; the execution layer submits monthly target-value orders.

**Tech Stack:** Python 3, pandas, numpy, JoinQuant strategy APIs, pytest, Ruff.

## Global Constraints

- Production strategy path is exactly `strategies/joinquant/bill_miller_quant.py`.
- Local tests must not require the `jqdata` package or network access.
- The JoinQuant script must remain standalone and must not import `trading_os`.
- All point-in-time queries use the previous trading day and `date`/`watch_date`, never a future report `statDate`.
- Initial portfolio uses the top 20; later entries come only from the top 15; existing holdings survive through rank 40 unless vetoed.
- Single-stock weight is 2%-8%; industry weight is at most 25%; financial weight is at most 30%; loss-making growth weight is at most 20%.
- No price stop-loss, intraday timing signal, external data, LLM call, or generic local backtest engine.
- Existing user and agent changes outside the files listed in this plan must remain untouched and unstaged.

---

## File Map

- Create `strategies/joinquant/bill_miller_quant.py`: standalone JoinQuant lifecycle, point-in-time data adapter, pure feature/scoring/portfolio functions, and order execution.
- Create `tests/test_bill_miller_joinquant_strategy.py`: local behavioral tests for all pure functions plus import/compile smoke coverage.
- Create `docs/superpowers/plans/2026-07-16-bill-miller-joinquant-strategy.md`: this execution plan.

---

### Task 1: Numerical primitives and company feature construction

**Files:**
- Create: `strategies/joinquant/bill_miller_quant.py`
- Create: `tests/test_bill_miller_joinquant_strategy.py`

**Interfaces:**
- Produces: `safe_divide(numerator, denominator) -> float`
- Produces: `simple_growth(latest, previous) -> float`
- Produces: `compound_growth(latest, oldest, periods) -> float`
- Produces: `winsorize_series(series, lower=0.05, upper=0.95) -> pandas.Series`
- Produces: `percentile_score(series, higher_is_better=True, min_count=20) -> pandas.Series`
- Produces: `build_company_features(history_rows, valuation_row, price_row, industry, is_financial, latest_row=None) -> dict | None`
- Consumes: Annual rows using official JoinQuant field names from `balance`, `cash_flow`, `income`, and `indicator`.

- [ ] **Step 1: Write failing tests for safe numerical behavior**

Create the test loader and assertions:

```python
from __future__ import annotations

import importlib.util
import datetime as dt
import math
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_PATH = ROOT / "strategies" / "joinquant" / "bill_miller_quant.py"


def load_strategy():
    spec = importlib.util.spec_from_file_location("bill_miller_quant", STRATEGY_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_safe_ratios_and_growth_reject_economically_invalid_denominators():
    strategy = load_strategy()

    assert strategy.safe_divide(10.0, 2.0) == 5.0
    assert math.isnan(strategy.safe_divide(10.0, 0.0))
    assert math.isnan(strategy.safe_divide(10.0, np.nan))
    assert strategy.simple_growth(120.0, 100.0) == 0.2
    assert math.isnan(strategy.simple_growth(120.0, -100.0))
    assert round(strategy.compound_growth(121.0, 100.0, 2), 6) == 0.1


def test_percentile_score_handles_outliers_ties_and_small_samples():
    strategy = load_strategy()
    values = pd.Series([1.0, 2.0, 3.0, 1000.0, np.nan], index=list("abcde"))

    clipped = strategy.winsorize_series(values, lower=0.0, upper=0.75)
    assert clipped.loc["d"] == 3.0
    scores = strategy.percentile_score(clipped, min_count=3)
    assert scores.loc["c"] == scores.loc["d"]
    assert scores.loc["a"] < scores.loc["b"] < scores.loc["c"]
    assert math.isnan(scores.loc["e"])
    assert strategy.percentile_score(pd.Series([1.0, 2.0]), min_count=3).isna().all()
```

- [ ] **Step 2: Run the numerical tests and confirm the RED state**

Run:

```bash
pytest tests/test_bill_miller_joinquant_strategy.py -q
```

Expected: FAIL because `strategies/joinquant/bill_miller_quant.py` or the requested functions do not exist.

- [ ] **Step 3: Implement the minimal numerical primitives**

Create the strategy file with a Chinese module docstring, `numpy`/`pandas` imports, model constants, and these behaviors:

```python
from __future__ import annotations

import datetime as dt
import math

import numpy as np
import pandas as pd


MODEL_GENERAL = "general"
MODEL_FINANCIAL = "financial"
MODEL_GROWTH = "growth"


def _finite_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return np.nan
    return number if np.isfinite(number) else np.nan


def safe_divide(numerator, denominator):
    numerator = _finite_number(numerator)
    denominator = _finite_number(denominator)
    if not np.isfinite(numerator) or not np.isfinite(denominator) or abs(denominator) < 1e-12:
        return np.nan
    return numerator / denominator


def simple_growth(latest, previous):
    previous = _finite_number(previous)
    if not np.isfinite(previous) or previous <= 0:
        return np.nan
    return safe_divide(_finite_number(latest) - previous, previous)


def compound_growth(latest, oldest, periods):
    latest = _finite_number(latest)
    oldest = _finite_number(oldest)
    if not np.isfinite(latest) or not np.isfinite(oldest) or latest <= 0 or oldest <= 0 or periods <= 0:
        return np.nan
    return (latest / oldest) ** (1.0 / periods) - 1.0


def winsorize_series(series, lower=0.05, upper=0.95):
    clean = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)
    valid = clean.dropna()
    if valid.empty:
        return clean
    return clean.clip(valid.quantile(lower), valid.quantile(upper))


def percentile_score(series, higher_is_better=True, min_count=20):
    clean = winsorize_series(series)
    if clean.notna().sum() < min_count:
        return pd.Series(np.nan, index=clean.index, dtype=float)
    scores = clean.rank(method="average", pct=True) * 100.0
    return scores if higher_is_better else 100.0 - scores
```

- [ ] **Step 4: Run the numerical tests and confirm GREEN**

Run:

```bash
pytest tests/test_bill_miller_joinquant_strategy.py -q
```

Expected: all numerical primitive tests PASS.

- [ ] **Step 5: Write the failing company-feature test**

Append a three-year annual fixture using verified JoinQuant columns and assert the economic outputs:

```python
def test_build_company_features_derives_cash_flow_returns_and_balance_sheet_risk():
    strategy = load_strategy()
    history = pd.DataFrame(
        [
            {
                "statDate": "2022-12-31",
                "cash_equivalents": 20.0,
                "total_assets": 200.0,
                "total_liability": 100.0,
                "total_owner_equities": 100.0,
                "paidin_capital": 10.0,
                "account_receivable": 20.0,
                "inventories": 10.0,
                "shortterm_loan": 20.0,
                "longterm_loan": 20.0,
                "bonds_payable": 0.0,
                "good_will": 4.0,
                "net_operate_cash_flow": 16.0,
                "fix_intan_other_asset_acqui_cash": 6.0,
                "total_operating_revenue": 100.0,
                "operating_profit": 12.0,
                "np_parent_company_owners": 10.0,
                "adjusted_profit": 9.0,
                "roe": 10.0,
                "roa": 5.0,
                "gross_profit_margin": 30.0,
            },
            {
                "statDate": "2023-12-31",
                "cash_equivalents": 23.0,
                "total_assets": 220.0,
                "total_liability": 108.0,
                "total_owner_equities": 112.0,
                "paidin_capital": 10.0,
                "account_receivable": 21.0,
                "inventories": 10.5,
                "shortterm_loan": 18.0,
                "longterm_loan": 18.0,
                "bonds_payable": 0.0,
                "good_will": 4.0,
                "net_operate_cash_flow": 18.0,
                "fix_intan_other_asset_acqui_cash": 6.0,
                "total_operating_revenue": 110.0,
                "operating_profit": 14.0,
                "np_parent_company_owners": 11.0,
                "adjusted_profit": 10.5,
                "roe": 10.4,
                "roa": 5.1,
                "gross_profit_margin": 31.0,
            },
            {
                "statDate": "2024-12-31",
                "cash_equivalents": 28.0,
                "total_assets": 245.0,
                "total_liability": 115.0,
                "total_owner_equities": 130.0,
                "paidin_capital": 10.0,
                "account_receivable": 22.0,
                "inventories": 11.0,
                "shortterm_loan": 16.0,
                "longterm_loan": 16.0,
                "bonds_payable": 0.0,
                "good_will": 4.0,
                "net_operate_cash_flow": 22.0,
                "fix_intan_other_asset_acqui_cash": 7.0,
                "total_operating_revenue": 121.0,
                "operating_profit": 17.0,
                "np_parent_company_owners": 13.0,
                "adjusted_profit": 12.5,
                "roe": 11.0,
                "roa": 5.5,
                "gross_profit_margin": 32.0,
            },
        ]
    )
    features = strategy.build_company_features(
        history,
        {"code": "000001.XSHE", "market_cap": 150.0, "pe_ratio": 12.0, "pb_ratio": 1.2, "ps_ratio": 1.0, "pcf_ratio": 8.0},
        {"return_12m": -0.2, "volatility_12m": 0.25, "max_drawdown_12m": -0.35, "average_money_20d": 5e7},
        industry="制造业",
        is_financial=False,
    )

    assert features is not None
    assert features["code"] == "000001.XSHE"
    assert features["latest_fcf"] == 15.0
    assert round(features["fcf_yield"], 4) == 0.1
    assert round(features["revenue_cagr"], 4) == 0.1
    assert features["fcf_positive_ratio"] == 1.0
    assert round(features["net_debt_ratio"], 4) == round((32.0 - 28.0) / 130.0, 4)
    assert features["contrarian_signal"] > 0
```

- [ ] **Step 6: Run the company-feature test and confirm RED**

Run:

```bash
pytest tests/test_bill_miller_joinquant_strategy.py::test_build_company_features_derives_cash_flow_returns_and_balance_sheet_risk -q
```

Expected: FAIL because `build_company_features` does not exist.

- [ ] **Step 7: Implement company feature construction**

Implement `build_company_features` so it sorts annual rows by `statDate`, requires at least two periods, computes annual FCF, revenue/profit/cash-flow trends, invested-capital and leverage proxies, valuation yields, accounting gaps, growth-company cash runway, and price risk. It must return keys consumed by later tasks:

```python
{
    "code", "industry", "is_financial", "latest_revenue", "latest_profit",
    "latest_cfo", "latest_fcf", "fcf_yield", "cash_conversion",
    "fcf_positive_ratio", "cfo_positive_ratio",
    "revenue_cagr", "profit_growth", "profit_stability", "gross_margin",
    "gross_margin_change", "roic_proxy", "incremental_return", "roe", "roa",
    "asset_turnover", "net_debt_ratio", "liability_ratio", "share_capital_growth",
    "ar_growth_gap",
    "inventory_growth_gap", "adjusted_profit_ratio", "goodwill_ratio",
    "cash_runway_years", "cash_burn_improvement", "earnings_yield", "book_yield",
    "sales_yield", "roe_to_pb", "return_12m", "volatility_12m",
    "max_drawdown_12m", "average_money_20d", "contrarian_signal",
    "total_assets", "total_liability", "deterioration_count",
    "accounting_gap_streak", "feature_coverage"
}
```

Use `market_cap * 1e8` because JoinQuant returns market capitalization in 100 million yuan. Treat invalid denominators as missing instead of rewarding extreme ratios. Define invested capital as owner equity plus short/long/bond debt minus cash, and use `operating_profit * 0.75` as the transparent ROIC numerator proxy.
When `latest_row` is present, use its published quarterly revenue growth, gross margin, and operating cash-flow direction only to compute `deterioration_count`; continue to derive FCF yield, ROIC, and multi-year trends from completed annual rows. Compute `share_capital_growth` from `paidin_capital` and include it in `feature_coverage`.

- [ ] **Step 8: Run all Task 1 tests and commit**

Run:

```bash
pytest tests/test_bill_miller_joinquant_strategy.py -q
ruff check strategies/joinquant/bill_miller_quant.py tests/test_bill_miller_joinquant_strategy.py
```

Expected: PASS with no Ruff errors.

Stage only the two Task 1 files, inspect `git diff --staged`, and commit:

```bash
git add strategies/joinquant/bill_miller_quant.py tests/test_bill_miller_joinquant_strategy.py
git diff --staged --check
git diff --staged --name-status
git commit -m "feat: add Miller strategy feature engine"
```

---

### Task 2: Three-model scoring and risk vetoes

**Files:**
- Modify: `strategies/joinquant/bill_miller_quant.py`
- Modify: `tests/test_bill_miller_joinquant_strategy.py`

**Interfaces:**
- Consumes: The feature dictionary produced by `build_company_features`.
- Produces: `classify_model(row) -> str | None`
- Produces: `risk_veto_reasons(row) -> list[str]`
- Produces: `score_candidates(features, min_group_size=20) -> pandas.DataFrame`
- Output columns: `code`, `model`, `industry`, five component scores, `score`, `veto_reasons`, `eligible`.

- [ ] **Step 1: Write failing tests for classification and veto rules**

Add tests proving financial precedence, ordinary-company classification, eligible loss-making growth classification, and cash-runway/liability vetoes:

```python
def test_classification_and_vetoes_distinguish_three_company_models():
    strategy = load_strategy()
    base = {
        "latest_revenue": 100.0,
        "latest_profit": 10.0,
        "latest_fcf": 8.0,
        "revenue_cagr": 0.1,
        "gross_margin": 30.0,
        "gross_margin_change": 1.0,
        "cash_runway_years": np.inf,
        "liability_ratio": 0.45,
        "fcf_positive_ratio": 1.0,
        "latest_cfo": 12.0,
        "cfo_positive_ratio": 1.0,
        "deterioration_count": 0,
        "accounting_gap_streak": 0,
        "feature_coverage": 1.0,
    }

    assert strategy.classify_model({**base, "is_financial": True}) == strategy.MODEL_FINANCIAL
    assert strategy.classify_model({**base, "is_financial": False}) == strategy.MODEL_GENERAL
    growth = {**base, "is_financial": False, "latest_profit": -5.0, "latest_fcf": -6.0, "cash_runway_years": 2.0}
    assert strategy.classify_model(growth) == strategy.MODEL_GROWTH
    assert strategy.risk_veto_reasons(growth) == []
    assert "cash_runway" in strategy.risk_veto_reasons({**growth, "cash_runway_years": 1.0})
    assert "insolvent" in strategy.risk_veto_reasons({**base, "total_assets": 100.0, "total_liability": 101.0})
```

- [ ] **Step 2: Run classification tests and confirm RED**

Run the named test. Expected: FAIL because classification and veto functions do not exist.

- [ ] **Step 3: Implement deterministic classification and vetoes**

Implement financial-first classification. A non-financial company with both positive latest profit and latest FCF is `general`; otherwise it is `growth` only when revenue CAGR and gross margin are positive, margin decline is no worse than 10 percentage points, cash runway is at least 1.5 years, and liability ratio is below 70%. Return `None` for companies that fit no model. Implement veto reason codes exactly as asserted and add reason codes for three-year negative CFO without growth, two-of-three fundamental deterioration, repeated receivable/inventory gaps, and insufficient feature coverage.

- [ ] **Step 4: Run classification tests and confirm GREEN**

Run the named test. Expected: PASS.

- [ ] **Step 5: Write failing tests for cross-sectional scoring**

Add an explicit six-company fixture and assertions:

```python
def make_scoring_fixture():
    base = {
        "industry": "制造业",
        "is_financial": False,
        "latest_revenue": 100.0,
        "latest_profit": 10.0,
        "latest_fcf": 8.0,
        "latest_cfo": 12.0,
        "revenue_cagr": 0.10,
        "profit_growth": 0.10,
        "profit_stability": 1.0,
        "gross_margin": 30.0,
        "gross_margin_change": 1.0,
        "cash_conversion": 1.2,
        "fcf_positive_ratio": 1.0,
        "cfo_positive_ratio": 1.0,
        "roic_proxy": 0.12,
        "incremental_return": 0.15,
        "roe": 12.0,
        "roa": 6.0,
        "asset_turnover": 0.8,
        "share_capital_growth": 0.0,
        "net_debt_ratio": 0.1,
        "liability_ratio": 0.45,
        "ar_growth_gap": 0.0,
        "inventory_growth_gap": 0.0,
        "adjusted_profit_ratio": 0.95,
        "goodwill_ratio": 0.02,
        "cash_runway_years": 5.0,
        "cash_burn_improvement": 0.02,
        "earnings_yield": 0.08,
        "book_yield": 0.80,
        "sales_yield": 1.0,
        "roe_to_pb": 10.0,
        "contrarian_signal": 0.20,
        "total_assets": 200.0,
        "total_liability": 90.0,
        "deterioration_count": 0,
        "accounting_gap_streak": 0,
        "feature_coverage": 1.0,
    }

    def row(code, **changes):
        return {**base, "code": code, **changes}

    return pd.DataFrame(
        [
            row("GENERAL_GOOD", fcf_yield=0.10, roic_proxy=0.18, contrarian_signal=0.35),
            row("GENERAL_WEAK", fcf_yield=0.02, roic_proxy=0.06, net_debt_ratio=0.8),
            row("FINANCIAL_GOOD", is_financial=True, industry="银行I", roe_to_pb=14.0, roe=14.0),
            row("FINANCIAL_WEAK", is_financial=True, industry="银行I", roe_to_pb=5.0, roe=6.0),
            row(
                "GROWTH_GOOD",
                latest_profit=-3.0,
                latest_fcf=-4.0,
                revenue_cagr=0.30,
                gross_margin=55.0,
                cash_runway_years=3.0,
                sales_yield=0.8,
            ),
            row(
                "GROWTH_WEAK",
                latest_profit=-5.0,
                latest_fcf=-7.0,
                revenue_cagr=0.05,
                gross_margin=20.0,
                cash_runway_years=1.6,
                sales_yield=0.2,
            ),
        ]
    )


def test_score_candidates_rewards_expectation_gap_without_making_low_pe_a_hard_filter():
    strategy = load_strategy()
    frame = make_scoring_fixture()
    ranked = strategy.score_candidates(frame, min_group_size=2)

    assert set(ranked["model"]) == {strategy.MODEL_GENERAL, strategy.MODEL_FINANCIAL, strategy.MODEL_GROWTH}
    assert ranked.loc[ranked["code"] == "GENERAL_GOOD", "score"].iloc[0] > ranked.loc[ranked["code"] == "GENERAL_WEAK", "score"].iloc[0]
    assert ranked.loc[ranked["code"] == "GROWTH_GOOD", "eligible"].iloc[0]
    assert ranked["score"].dropna().between(0.0, 100.0).all()
```

The fixture includes every raw feature used by the component specifications and uses no mocks.

- [ ] **Step 6: Run scoring tests and confirm RED**

Run the scoring test. Expected: FAIL because `score_candidates` does not exist.

- [ ] **Step 7: Implement component scoring**

Define explicit feature/direction maps for each model:

- General expectations: `fcf_yield`, `earnings_yield`, `book_yield`, `sales_yield`, `roe_to_pb` high.
- General quality: `cash_conversion`, `fcf_positive_ratio`, `revenue_cagr`, `gross_margin`, `profit_stability` high.
- General capital return: `roic_proxy`, `incremental_return`, `roe`, `roa` high.
- General accounting: `adjusted_profit_ratio` high; `net_debt_ratio`, `ar_growth_gap`, `inventory_growth_gap`, `goodwill_ratio` low.
- Financial expectations: `roe_to_pb`, `book_yield`, `earnings_yield` high.
- Financial quality/capital/accounting: `profit_stability`, `profit_growth`, `adjusted_profit_ratio`, `roe`, `roa` high; compare only inside the financial sub-industry.
- Growth expectations: `sales_yield`, `revenue_cagr`, `cash_burn_improvement` high.
- Growth quality/capital/accounting: `gross_margin`, `gross_margin_change`, `asset_turnover`, `cash_runway_years` high; `liability_ratio` and `share_capital_growth` low.
- All models' contrarian component: `contrarian_signal` high.

For each feature, median-fill only after verifying the candidate has at least half of that component's inputs. Convert valid features to percentile scores inside the relevant model group, average each component, and combine 35/25/15/15/10. Attach veto reasons and sort descending by score with code as a stable tie breaker.

- [ ] **Step 8: Run Task 2 tests, lint, inspect, and commit**

Run full targeted pytest and Ruff. Stage only the strategy and targeted test, inspect the staged diff, and commit:

```bash
git commit -m "feat: add Miller three-model ranking"
```

---

### Task 3: Holding buffer and constrained portfolio weights

**Files:**
- Modify: `strategies/joinquant/bill_miller_quant.py`
- Modify: `tests/test_bill_miller_joinquant_strategy.py`

**Interfaces:**
- Consumes: Descending eligible output from `score_candidates`.
- Produces: `select_portfolio(ranked, current_codes, target_count=20, entry_rank=15, hold_rank=40) -> list[str]`
- Produces: `allocate_weights(selected, max_single=0.08, min_single=0.02, max_industry=0.25, max_financial=0.30, max_growth=0.20) -> dict[str, float]`

- [ ] **Step 1: Write failing holding-buffer tests**

Create a 50-name ranked frame and assert:

```python
def make_ranked_fixture(count):
    return pd.DataFrame(
        {
            "code": [f"S{rank:03d}" for rank in range(1, count + 1)],
            "score": np.linspace(100.0, 50.0, count),
            "eligible": [True] * count,
            "veto_reasons": [[] for _ in range(count)],
        }
    )


def test_select_portfolio_uses_initial_top_twenty_and_later_rank_buffers():
    strategy = load_strategy()
    ranked = make_ranked_fixture(50)

    assert strategy.select_portfolio(ranked, []) == list(ranked["code"].head(20))
    selected = strategy.select_portfolio(ranked, ["S035", "S045"])
    assert "S035" in selected
    assert "S045" not in selected
    assert len(selected) <= 20
    new_codes = set(selected) - {"S035", "S045"}
    assert new_codes <= set(ranked["code"].head(15))
```

- [ ] **Step 2: Run selection test and confirm RED**

Expected: FAIL because `select_portfolio` does not exist.

- [ ] **Step 3: Implement selection with stable ranking**

Filter out ineligible/vetoed rows first. On an empty current portfolio select up to the first 20. Otherwise retain current holdings through rank 40, sorted by current rank, then fill remaining slots only from entry ranks 1-15. Never exceed the target count and never force a cash position to be filled by a rank 16+ newcomer.

- [ ] **Step 4: Run selection test and confirm GREEN**

Expected: PASS.

- [ ] **Step 5: Write failing allocation constraint tests**

Build a selected frame containing multiple industries, financial names, and growth names with unequal scores and downside risks. Assert every weight is 2%-8%, total weight is at most 100%, each industry is at most 25%, financial total is at most 30%, growth total is at most 20%, and lower downside risk receives more weight when scores are equal. Add a five-name concentrated fixture proving that unallocatable capital remains cash rather than violating the 8% single-name cap.

- [ ] **Step 6: Run allocation tests and confirm RED**

Expected: FAIL because `allocate_weights` does not exist.

- [ ] **Step 7: Implement transparent capped allocation**

Compute raw conviction as `max(score - 50, 1) / max(downside_risk, 0.05)`, normalize, and redistribute in bounded iterations to names below 8%. Scale down industry/model groups that breach their caps, drop resulting weights below 2%, and do not re-expand a capped group. Return rounded weights with total no greater than 1.0; residual is intentional cash.

- [ ] **Step 8: Run Task 3 tests, lint, inspect, and commit**

Run targeted pytest and Ruff. Stage only the two implementation files, inspect staged names/diff, and commit:

```bash
git commit -m "feat: add Miller portfolio construction"
```

---

### Task 4: JoinQuant point-in-time adapter and monthly execution

**Files:**
- Modify: `strategies/joinquant/bill_miller_quant.py`
- Modify: `tests/test_bill_miller_joinquant_strategy.py`

**Interfaces:**
- Produces JoinQuant lifecycle: `initialize(context)` and `monthly_rebalance(context)`.
- Produces boundary helpers: `_chunked`, `_previous_trade_day`, `_fetch_universe`, `_fetch_annual_fundamentals`, `_fetch_latest_fundamentals`, `_fetch_valuations`, `_fetch_industries`, `_fetch_price_stats`, `_build_feature_frame`, `_is_buyable`, `_is_sellable`, `_execute_targets`.
- Consumes official fields: `balance.cash_equivalents`, `balance.total_assets`, `balance.total_liability`, `balance.total_owner_equities`, `balance.paidin_capital`, `balance.account_receivable`, `balance.inventories`, `balance.shortterm_loan`, `balance.longterm_loan`, `balance.bonds_payable`, `balance.good_will`, `cash_flow.net_operate_cash_flow`, `cash_flow.fix_intan_other_asset_acqui_cash`, `income.total_operating_revenue`, `income.operating_profit`, `income.np_parent_company_owners`, `indicator.adjusted_profit`, `indicator.roe`, `indicator.roa`, `indicator.gross_profit_margin`, `indicator.inc_total_revenue_year_on_year`, and valuation fields.

- [ ] **Step 1: Write failing boundary smoke tests**

Add concrete tests that import the file without `jqdata`, validate batching and observation-date behavior, normalize a representative `get_price(..., panel=False)` long-form DataFrame, and inspect the source boundary:

```python
def test_joinquant_boundary_helpers_are_point_in_time_and_locally_importable():
    strategy = load_strategy()
    codes = [f"S{i:04d}" for i in range(1005)]
    chunks = list(strategy._chunked(codes, 400))
    assert [len(chunk) for chunk in chunks] == [400, 400, 205]
    assert [code for chunk in chunks for code in chunk] == codes

    calls = []

    def fake_trade_days(**kwargs):
        calls.append(kwargs)
        return np.array([dt.date(2026, 7, 15), dt.date(2026, 7, 16)])

    strategy.get_trade_days = fake_trade_days
    assert strategy._previous_trade_day(dt.date(2026, 7, 16)) == dt.date(2026, 7, 15)
    assert calls == [{"end_date": dt.date(2026, 7, 16), "count": 2}]


def test_price_normalizer_accepts_joinquant_long_form_and_source_has_no_repo_import():
    strategy = load_strategy()
    raw = pd.DataFrame(
        {
            "time": pd.to_datetime(["2026-07-14", "2026-07-15"]),
            "code": ["000001.XSHE", "000001.XSHE"],
            "close": [10.0, 11.0],
            "money": [3e7, 4e7],
        }
    )
    normalized = strategy._normalize_price_frame(raw)
    assert list(normalized.columns) == ["time", "code", "close", "money"]
    assert normalized.iloc[-1]["close"] == 11.0
    assert "import trading_os" not in STRATEGY_PATH.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run boundary tests and confirm RED**

Expected: FAIL because boundary helpers and lifecycle functions are not complete.

- [ ] **Step 3: Implement JoinQuant initialization**

Add a guarded wildcard import so local import succeeds while JoinQuant receives its APIs:

```python
try:
    from jqdata import *  # noqa: F403
except ImportError:
    pass
```

Configure `000985.XSHG`, real prices, future-data protection, fixed slippage, A-share costs, and `run_monthly(monthly_rebalance, 1, time="10:00")`. Put JoinQuant-name Ruff suppressions at file scope only for F403/F405; do not suppress unrelated lint rules.

- [ ] **Step 4: Implement point-in-time data fetching**

Implement these exact data-flow rules:

1. Observation date is the previous result from `get_trade_days(end_date=context.current_dt.date(), count=2)`.
2. Universe is `get_all_securities(['stock'], date=observation_date)`, filtered to 500 natural days of listing history.
3. Current-day `get_current_data()` removes ST, names containing `退`, and paused securities before queries.
4. Twenty-day average money uses `get_price` batches of 400 and filters below 20 million yuan.
5. Annual history uses `get_history_fundamentals` batches small enough to stay under 5,000 returned rows, with `watch_date=observation_date`, `count=3`, `interval='1y'`, and `stat_by_year=True`.
6. Latest visible quarterly fundamentals use `get_fundamentals(query(...), date=observation_date)` and feed only deterioration/coverage checks; annual FCF and return ratios are never synthesized from one quarter.
7. Valuation uses `get_fundamentals(query(...).filter(valuation.code.in_(batch)), date=observation_date)`.
8. Industry uses `get_industry(batch, date=observation_date)` and `sw_l1`; names containing 银行、非银金融、证券、保险 or 多元金融 set `is_financial=True`.
9. Twelve-month return, annualized volatility, and max drawdown use 252 previous daily closes. Fetch full price history only after liquidity filtering and in batches.
10. A failed batch logs a warning and removes that batch from the current candidate set; it never substitutes current/future data.

- [ ] **Step 5: Implement monthly ranking and order execution**

`monthly_rebalance` must fetch data, build one feature row per security, call `score_candidates`, `select_portfolio`, and `allocate_weights`, then:

1. Sell positions absent from target weights when `_is_sellable` confirms not paused and not at the lower limit.
2. Adjust retained/buy positions with `order_target_value(code, portfolio.total_value * weight)` when buyable; do not buy paused/upper-limit names.
3. Skip target values below one board lot at the latest price.
4. Log observation date, universe/liquid/scored/eligible counts, selected codes, target weights, veto counts, and retained cash.
5. Catch errors per symbol/batch, but allow an unexpected top-level data failure to leave the existing portfolio unchanged.

- [ ] **Step 6: Run boundary tests and confirm GREEN**

Run the targeted boundary tests. Expected: PASS without a local `jqdata` installation.

- [ ] **Step 7: Run fresh complete verification**

Run:

```bash
pytest tests/test_bill_miller_joinquant_strategy.py -q
ruff check strategies/joinquant/bill_miller_quant.py tests/test_bill_miller_joinquant_strategy.py
python -m py_compile strategies/joinquant/bill_miller_quant.py
pytest -q
```

Expected: all targeted and repository tests pass, Ruff reports no errors, and compilation exits 0.

- [ ] **Step 8: Inspect only the intended final diff and commit**

Run:

```bash
git status --short
git diff --check -- strategies/joinquant/bill_miller_quant.py tests/test_bill_miller_joinquant_strategy.py
git add strategies/joinquant/bill_miller_quant.py tests/test_bill_miller_joinquant_strategy.py
git diff --staged --check
git diff --staged --name-status
git diff --staged
git commit -m "feat: add JoinQuant Miller strategy"
```

The staged name list must contain only the strategy and its test. Do not stage generated research indexes, coverage queues, temporary files, PDFs, or any pre-existing dirty-worktree changes.

---

## Plan Self-Review Checklist

- Every design requirement maps to a task: numerical safety (Task 1), three company models and vetoes (Task 2), concentrated buffered portfolio (Task 3), and point-in-time JoinQuant execution (Task 4).
- All production interfaces consumed by later tasks are named in the preceding task.
- All JoinQuant financial fields were checked against the official Stock data documentation on 2026-07-16.
- The plan contains no dependency on the removed local backtest/strategy framework.
- Local verification does not claim to replace an actual JoinQuant platform backtest; platform performance validation remains a user-run acceptance step after upload.
