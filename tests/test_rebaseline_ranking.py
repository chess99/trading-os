from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

import pytest

from tests.test_company_assets import write_company

NOW = dt.datetime.fromisoformat("2026-07-22T18:00:00+08:00")


def _company_dir(tmp_path: Path, ticker: str, name: str) -> Path:
    seed = write_company(tmp_path / f"seed-{ticker}")
    target = tmp_path / "research" / "companies" / "CN" / ticker
    target.parent.mkdir(parents=True, exist_ok=True)
    seed.rename(target)
    report_path = target / "reports" / "2026-07-21-initial-research.md"
    report = report_path.read_text(encoding="utf-8").replace(
        '"symbol": "CN:600519"', f'"symbol": "CN:{ticker}"'
    ).replace(
        "# 公司研究：贵州茅台（CN:600519）",
        f"# 公司研究：{name}（CN:{ticker}）",
    )
    report_path.write_text(report, encoding="utf-8")
    meta_path = target / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["identity"].update(
        {"symbol": f"CN:{ticker}", "ticker": ticker, "name": name}
    )
    meta["research"].update(
        {"coverage_status": "requires_rebaseline", "rebaseline_required": True}
    )
    meta["reports"]["history"][0]["sha256"] = hashlib.sha256(
        report_path.read_bytes()
    ).hexdigest()
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return target


def _inputs(tmp_path: Path, records: list[dict]) -> tuple[Path, Path, Path]:
    from trading_os.research_assets.coverage_store import write_jsonl

    companies_path = tmp_path / "coverage" / "cn-a" / "companies.jsonl"
    queue_path = tmp_path / "coverage" / "cn-a" / "research_queue.jsonl"
    queue = []
    for record in records:
        ticker = record["symbol"].split(":", 1)[1]
        company_dir = _company_dir(tmp_path, ticker, record["name"])
        queue.append(
            {
                "symbol": record["symbol"],
                "name": record["name"],
                "status": "requires_rebaseline",
                "target_company_dir": str(company_dir),
            }
        )
    write_jsonl(companies_path, records)
    write_jsonl(queue_path, queue)
    return companies_path, queue_path, tmp_path / "research"


def _record(symbol: str = "CN:600519", name: str = "样本公司", **changes) -> dict:
    value = {
        "symbol": symbol,
        "name": name,
        "as_of": "2026-07-22",
        "security_type": "common_stock",
        "listing_status": "listed",
        "industry": "食品饮料",
        "price": 20.0,
        "market_cap_cny": 100_000_000_000,
        "pe_ttm": 12.0,
        "pb": 1.5,
        "roe": 16.0,
        "revenue_growth_pct": 8.0,
        "profit_growth_pct": 10.0,
        "dividend_yield_pct": 3.5,
        "debt_to_asset_pct": 35.0,
        "latest_filing_date": "2026-04-30",
        "source": "public fixture",
    }
    value.update(changes)
    return value


def _build(tmp_path: Path, records: list[dict], **kwargs):
    from trading_os.research_assets.rebaseline_ranking import build_rebaseline_ranking

    companies, queue, research = _inputs(tmp_path, records)
    return build_rebaseline_ranking(
        companies_path=companies,
        queue_path=queue,
        research_root=research,
        generated_at=NOW,
        **kwargs,
    )


def test_ranking_is_stable_and_ties_break_by_symbol(tmp_path: Path):
    from trading_os.research_assets.rebaseline_ranking import build_rebaseline_ranking

    records = [
        _record("CN:600002", "乙公司"),
        _record("CN:000001", "甲公司"),
    ]
    companies, queue, research = _inputs(tmp_path, records)
    kwargs = {
        "companies_path": companies,
        "queue_path": queue,
        "research_root": research,
        "generated_at": NOW,
    }
    first = build_rebaseline_ranking(**kwargs)
    second = build_rebaseline_ranking(**kwargs)

    assert [item["symbol"] for item in first["items"]] == [
        "CN:000001",
        "CN:600002",
    ]
    assert first == second


def test_missing_data_is_recorded_and_not_silently_scored_as_zero(tmp_path: Path):
    record = _record(roe=None, debt_to_asset_pct=None, latest_filing_date=None)

    item = _build(tmp_path, [record])["items"][0]

    assert {"roe", "debt_to_asset_pct", "latest_filing_date"} <= set(
        item["missing_fields"]
    )
    assert item["dimensions"]["operating_capital_quality"] > 0
    assert item["score_confidence"] in {"medium", "low"}


def test_financial_company_uses_pb_and_specialized_balance_sheet_review(tmp_path: Path):
    item = _build(
        tmp_path,
        [_record(industry="股份制银行", pe_ttm=4.0, pb=0.55, debt_to_asset_pct=92.0)],
    )["items"][0]

    assert "financial_sector_pb_valuation" in item["reason_codes"]
    assert "financial_balance_sheet_requires_specialized_review" in item["reason_codes"]
    assert item["dimensions"]["value_dislocation"] == 23.5


def test_negative_pe_requires_normalization_instead_of_cheapness_bonus(tmp_path: Path):
    negative = _build(tmp_path, [_record(pe_ttm=-3.0)])["items"][0]

    assert "negative_pe_requires_normalization" in negative["reason_codes"]
    assert negative["dimensions"]["value_dislocation"] < 15


def test_cyclical_industry_is_routed_to_normalization_without_blanket_penalty(
    tmp_path: Path,
):
    item = _build(tmp_path, [_record(industry="煤炭开采")])["items"][0]

    assert {penalty["code"] for penalty in item["penalties"]} == {
        "cyclical_normalization_required"
    }
    assert sum(penalty["points"] for penalty in item["penalties"]) == 0
    assert item["economic_risk_cluster"] == "commodity_cycle"


def test_single_period_outliers_trigger_verification_instead_of_maximum_scores(
    tmp_path: Path,
):
    item = _build(
        tmp_path,
        [_record(pe_ttm=0.9, roe=80.0, profit_growth_pct=2600.0)],
    )["items"][0]

    assert {
        "extreme_low_pe_requires_one_off_verification",
        "single_period_roe_outlier_requires_verification",
        "single_period_growth_outlier_requires_verification",
    } <= set(item["reason_codes"])
    assert item["dimensions"]["value_dislocation"] < 20
    assert item["dimensions"]["operating_capital_quality"] < 19
    assert item["dimensions"]["verifiable_catalyst_odds"] == 4


@pytest.mark.parametrize(
    ("industry", "cluster"),
    [("化学制药", "healthcare_policy"), ("白酒Ⅱ", "consumer_demand")],
)
def test_industry_aliases_map_to_stable_risk_clusters(
    tmp_path: Path, industry: str, cluster: str
):
    item = _build(tmp_path, [_record(industry=industry)])["items"][0]

    assert item["economic_risk_cluster"] == cluster


def test_delisting_security_is_hard_excluded_with_reason(tmp_path: Path):
    payload = _build(tmp_path, [_record(name="样本退")])

    assert payload["ranked_count"] == 0
    assert payload["excluded"] == [
        {"symbol": "CN:600519", "reason_code": "delisting_name_signal"}
    ]


def test_private_fields_are_rejected_before_ranking(tmp_path: Path):
    from trading_os.research_assets.rebaseline_ranking import RebaselineRankingError

    with pytest.raises(RebaselineRankingError, match="private field"):
        _build(tmp_path, [_record(cost_basis=18.0)])


def test_stale_market_snapshot_is_rejected(tmp_path: Path):
    from trading_os.research_assets.rebaseline_ranking import RebaselineRankingError

    with pytest.raises(RebaselineRankingError, match="stale"):
        _build(tmp_path, [_record(as_of="2026-07-01")])


@pytest.mark.parametrize("bad", [True, "12", float("inf")])
def test_invalid_public_numeric_values_fail_closed(tmp_path: Path, bad):
    from trading_os.research_assets.rebaseline_ranking import RebaselineRankingError

    with pytest.raises(RebaselineRankingError, match="numeric|finite"):
        _build(tmp_path, [_record(pe_ttm=bad)])
