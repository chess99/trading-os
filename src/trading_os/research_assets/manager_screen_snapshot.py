from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .coverage_store import COMPANIES_FILE, read_jsonl, write_jsonl

DEFAULT_ENDPOINT = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

PROFILE_REPORT = "RPT_F10_BASIC_ORGINFO"
REPORTS = {
    "income": {
        "name": "RPT_F10_FINANCE_GINCOME",
        "columns": [
            "SECUCODE",
            "SECURITY_CODE",
            "ORG_TYPE",
            "REPORT_DATE",
            "REPORT_TYPE",
            "NOTICE_DATE",
            "UPDATE_DATE",
            "TOTAL_OPERATE_INCOME",
            "OPERATE_PROFIT",
            "PARENT_NETPROFIT",
            "DEDUCT_PARENT_NETPROFIT",
            "BASIC_EPS",
            "OPINION_TYPE",
        ],
    },
    "balance": {
        "name": "RPT_F10_FINANCE_GBALANCE",
        "columns": [
            "SECUCODE",
            "SECURITY_CODE",
            "ORG_TYPE",
            "REPORT_DATE",
            "REPORT_TYPE",
            "NOTICE_DATE",
            "UPDATE_DATE",
            "MONETARYFUNDS",
            "SHORT_LOAN",
            "SHORT_BOND_PAYABLE",
            "NONCURRENT_LIAB_1YEAR",
            "LONG_LOAN",
            "BOND_PAYABLE",
            "LEASE_LIAB",
            "TOTAL_ASSETS",
            "TOTAL_LIABILITIES",
            "TOTAL_PARENT_EQUITY",
            "GOODWILL",
            "ACCOUNTS_RECE",
            "NOTE_ACCOUNTS_RECE",
            "INVENTORY",
            "CONTRACT_ASSET",
            "OPINION_TYPE",
        ],
    },
    "cashflow": {
        "name": "RPT_F10_FINANCE_GCASHFLOW",
        "columns": [
            "SECUCODE",
            "SECURITY_CODE",
            "ORG_TYPE",
            "REPORT_DATE",
            "REPORT_TYPE",
            "NOTICE_DATE",
            "UPDATE_DATE",
            "NETCASH_OPERATE",
            "CONSTRUCT_LONG_ASSET",
            "ASSIGN_DIVIDEND_PORFIT",
            "OPINION_TYPE",
        ],
    },
}
PROFILE_COLUMNS = ["ALL"]

FetchRecords = Callable[..., list[dict[str, Any]]]


class ManagerScreenSnapshotError(ValueError):
    """Raised when the compact manager-screen source snapshot cannot be built."""


def prepare_manager_screen_snapshot(
    *,
    root: str | Path,
    run_id: str,
    information_cutoff: dt.datetime,
    fetched_at: dt.datetime,
    output_path: str | Path | None = None,
    endpoint: str = DEFAULT_ENDPOINT,
    page_size: int = 500,
    fetch_records: FetchRecords | None = None,
) -> dict[str, Any]:
    """Build one compact, fact-only company snapshot for a manager-screen run."""

    base = Path(root)
    repository_root = base.parent.parent
    run = _identifier(run_id)
    cutoff = _aware(information_cutoff, "information_cutoff")
    fetched = _aware(fetched_at, "fetched_at")
    if fetched < cutoff:
        raise ManagerScreenSnapshotError("fetched_at cannot be before information_cutoff")
    if isinstance(page_size, bool) or not isinstance(page_size, int) or not 1 <= page_size <= 500:
        raise ManagerScreenSnapshotError("page_size must be between 1 and 500")

    target = (
        Path(output_path)
        if output_path is not None
        else base / "snapshots" / run / "companies.jsonl"
    )
    if not target.is_absolute():
        target = repository_root / target
    target = target.resolve()
    try:
        target.relative_to(repository_root.resolve())
    except ValueError as exc:
        raise ManagerScreenSnapshotError(
            "manager-screen snapshot must be stored inside the repository"
        ) from exc

    if target.exists():
        return _existing_summary(
            target=target,
            repository_root=repository_root,
            run_id=run,
            information_cutoff=cutoff,
        )

    companies_path = base / COMPANIES_FILE
    companies = read_jsonl(companies_path)
    if not companies:
        raise ManagerScreenSnapshotError("coverage company snapshot is empty")
    symbols = {_symbol(item.get("symbol")) for item in companies}
    secucodes = {_secucode(item) for item in companies}
    fetch = fetch_records or _fetch_report_records

    profiles = fetch(
        endpoint=endpoint,
        report_name=PROFILE_REPORT,
        columns=PROFILE_COLUMNS,
        report_date=None,
        page_size=page_size,
        secucodes=secucodes,
    )
    report_dates = _report_dates(cutoff.date())
    raw_by_kind: dict[str, list[dict[str, Any]]] = {}
    source_counts: dict[str, int] = {"profile": len(profiles)}
    for kind, contract in REPORTS.items():
        rows = []
        for report_date in report_dates:
            fetched_rows = fetch(
                endpoint=endpoint,
                report_name=contract["name"],
                columns=contract["columns"],
                report_date=report_date,
                page_size=page_size,
                secucodes=secucodes,
            )
            source_counts[f"{kind}:{report_date}"] = len(fetched_rows)
            rows.extend(fetched_rows)
        raw_by_kind[kind] = rows

    profile_by_ticker = _latest_profiles(profiles, cutoff=cutoff, symbols=symbols)
    reports_by_kind = {
        kind: _latest_reports(rows, cutoff=cutoff, symbols=symbols)
        for kind, rows in raw_by_kind.items()
    }
    enriched = []
    for company in companies:
        symbol = _symbol(company.get("symbol"))
        ticker = symbol.split(":", 1)[1]
        periods = []
        available_dates = sorted(
            {
                report_date
                for kind_records in reports_by_kind.values()
                for report_ticker, report_date in kind_records
                if report_ticker == ticker
            }
        )
        for report_date in available_dates:
            periods.append(
                _compact_period(
                    report_date=report_date,
                    income=reports_by_kind["income"].get((ticker, report_date)),
                    balance=reports_by_kind["balance"].get((ticker, report_date)),
                    cashflow=reports_by_kind["cashflow"].get((ticker, report_date)),
                )
            )
        annuals = [item for item in periods if item["report_date"].endswith("-12-31")]
        interims = [item for item in periods if not item["report_date"].endswith("-12-31")]
        profile = profile_by_ticker.get(ticker)
        data_gaps = []
        if profile is None:
            data_gaps.append("business_profile_missing")
        if len(annuals) < 3:
            data_gaps.append("three_year_annual_history_incomplete")
        if not periods or all(item["operating_cash_flow_cny"] is None for item in periods):
            data_gaps.append("operating_cash_flow_missing")
        if not periods or all(item["balance_sheet"] is None for item in periods):
            data_gaps.append("balance_sheet_missing")
        updated = dict(company)
        updated["manager_screen_facts"] = {
            "schema_version": 1,
            "run_id": run,
            "information_cutoff": cutoff.isoformat(),
            "fetched_at": fetched.isoformat(),
            "source": endpoint,
            "business": _compact_profile(profile),
            "annuals": annuals,
            "latest_interim": interims[-1] if interims else None,
            "data_gaps": data_gaps,
        }
        enriched.append(updated)

    if {item["symbol"] for item in enriched} != symbols:
        raise ManagerScreenSnapshotError("manager-screen snapshot lost company identities")
    write_jsonl(target, enriched)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    return {
        "schema_version": 1,
        "run_id": run,
        "information_cutoff": cutoff.isoformat(),
        "fetched_at": fetched.isoformat(),
        "path": _relative(target, repository_root),
        "sha256": digest,
        "record_count": len(enriched),
        "source_counts": dict(sorted(source_counts.items())),
        "data_gap_counts": _data_gap_counts(enriched),
        "portfolio_action": None,
    }


def _fetch_report_records(
    *,
    endpoint: str,
    report_name: str,
    columns: Sequence[str],
    report_date: str | None,
    page_size: int,
    secucodes: set[str],
) -> list[dict[str, Any]]:
    rows = []
    page_number = 1
    pages = 1
    while page_number <= pages:
        payload = _request_page(
            endpoint=endpoint,
            report_name=report_name,
            columns=columns,
            report_date=report_date,
            page_size=page_size,
            page_number=page_number,
        )
        pages = _positive_int(payload.get("pages") or 1, "source page count")
        for row in payload["data"]:
            if isinstance(row, Mapping) and row.get("SECUCODE") in secucodes:
                rows.append(dict(row))
        page_number += 1
    return rows


def _request_page(
    *,
    endpoint: str,
    report_name: str,
    columns: Sequence[str],
    report_date: str | None,
    page_size: int,
    page_number: int,
) -> dict[str, Any]:
    filters = ['(SECURITY_TYPE_CODE="058001001")']
    if report_date is not None:
        filters.insert(0, f"(REPORT_DATE='{report_date}')")
    query = urllib.parse.urlencode(
        {
            "reportName": report_name,
            "columns": ",".join(columns),
            "filter": "".join(filters),
            "pageNumber": page_number,
            "pageSize": page_size,
            "sortTypes": "1" if report_name == PROFILE_REPORT else "1,1",
            "sortColumns": (
                "SECURITY_CODE"
                if report_name == PROFILE_REPORT
                else "SECURITY_CODE,UPDATE_DATE"
            ),
        }
    )
    url = f"{endpoint}?{query}"
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "Trading-OS manager-screen snapshot/1.0"},
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
            result = payload.get("result")
            if not payload.get("success") or not isinstance(result, Mapping):
                raise RuntimeError(payload.get("message") or "public API returned failure")
            data = result.get("data")
            if not isinstance(data, list):
                raise RuntimeError("public API result.data is not an array")
            return {"pages": result.get("pages") or 1, "data": data}
        except Exception as exc:  # noqa: BLE001 - bounded public-data retry boundary
            last_error = exc
            if attempt < 3:
                time.sleep(1.5 * (attempt + 1))
    raise ManagerScreenSnapshotError(
        f"failed to fetch {report_name} page {page_number}: {last_error}"
    )


def _report_dates(cutoff: dt.date) -> list[str]:
    dates = [f"{year}-12-31" for year in range(cutoff.year - 3, cutoff.year)]
    if cutoff.month >= 4:
        dates.append(f"{cutoff.year}-03-31")
    if cutoff.month >= 7:
        dates.append(f"{cutoff.year}-06-30")
    if cutoff.month >= 10:
        dates.append(f"{cutoff.year}-09-30")
    return dates


def _latest_profiles(
    rows: Sequence[Mapping[str, Any]],
    *,
    cutoff: dt.datetime,
    symbols: set[str],
) -> dict[str, dict[str, Any]]:
    result = {}
    for row in rows:
        ticker = row.get("SECURITY_CODE")
        if not isinstance(ticker, str) or f"CN:{ticker}" not in symbols:
            continue
        result[ticker] = dict(row)
    return result


def _latest_reports(
    rows: Sequence[Mapping[str, Any]],
    *,
    cutoff: dt.datetime,
    symbols: set[str],
) -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        ticker = row.get("SECURITY_CODE")
        report_date = _date_text(row.get("REPORT_DATE"))
        if (
            not isinstance(ticker, str)
            or f"CN:{ticker}" not in symbols
            or report_date is None
            or not _available_at_cutoff(row, cutoff)
        ):
            continue
        key = (ticker, report_date)
        existing = result.get(key)
        if existing is None or _source_sort_key(row) > _source_sort_key(existing):
            result[key] = dict(row)
    return result


def _available_at_cutoff(row: Mapping[str, Any], cutoff: dt.datetime) -> bool:
    for field in ("NOTICE_DATE", "UPDATE_DATE"):
        value = _date_text(row.get(field))
        if value is not None and dt.date.fromisoformat(value) > cutoff.date():
            return False
    return True


def _source_sort_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return str(row.get("UPDATE_DATE") or ""), str(row.get("NOTICE_DATE") or "")


def _compact_profile(row: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "org_type": row.get("ORG_TYPE"),
        "industry_csrc": row.get("INDUSTRYCSRC1"),
        "industry_board": row.get("BOARD_NAME_LEVEL"),
        "main_business": _compact_text(row.get("MAIN_BUSINESS"), limit=800),
        "actual_controller": _compact_text(row.get("ACTUAL_HOLDER"), limit=200),
        "auditor": _compact_text(row.get("ACCOUNTFIRM_NAME"), limit=200),
        "listing_date": _date_text(row.get("LISTING_DATE")),
    }


def _compact_period(
    *,
    report_date: str,
    income: Mapping[str, Any] | None,
    balance: Mapping[str, Any] | None,
    cashflow: Mapping[str, Any] | None,
) -> dict[str, Any]:
    debt = (
        _sum_values(
            balance,
            (
                "SHORT_LOAN",
                "SHORT_BOND_PAYABLE",
                "NONCURRENT_LIAB_1YEAR",
                "LONG_LOAN",
                "BOND_PAYABLE",
                "LEASE_LIAB",
            ),
        )
        if balance is not None
        else None
    )
    notice_dates = [
        value
        for row in (income, balance, cashflow)
        if row is not None
        if (value := _date_text(row.get("NOTICE_DATE"))) is not None
    ]
    opinion = next(
        (
            row.get("OPINION_TYPE")
            for row in (income, balance, cashflow)
            if row is not None and row.get("OPINION_TYPE")
        ),
        None,
    )
    return {
        "report_date": report_date,
        "notice_date": max(notice_dates) if notice_dates else None,
        "report_type": next(
            (
                row.get("REPORT_TYPE")
                for row in (income, balance, cashflow)
                if row is not None and row.get("REPORT_TYPE")
            ),
            None,
        ),
        "revenue_cny": _number(income, "TOTAL_OPERATE_INCOME"),
        "operating_profit_cny": _number(income, "OPERATE_PROFIT"),
        "parent_net_profit_cny": _number(income, "PARENT_NETPROFIT"),
        "deducted_parent_net_profit_cny": _number(
            income,
            "DEDUCT_PARENT_NETPROFIT",
        ),
        "operating_cash_flow_cny": _number(cashflow, "NETCASH_OPERATE"),
        "capital_expenditure_cny": _number(cashflow, "CONSTRUCT_LONG_ASSET"),
        "cash_dividends_paid_cny": _number(cashflow, "ASSIGN_DIVIDEND_PORFIT"),
        "balance_sheet": (
            {
                "cash_cny": _number(balance, "MONETARYFUNDS"),
                "interest_bearing_debt_cny": debt,
                "total_assets_cny": _number(balance, "TOTAL_ASSETS"),
                "total_liabilities_cny": _number(balance, "TOTAL_LIABILITIES"),
                "parent_equity_cny": _number(balance, "TOTAL_PARENT_EQUITY"),
                "goodwill_cny": _number(balance, "GOODWILL"),
                "accounts_receivable_cny": _number(balance, "ACCOUNTS_RECE"),
                "notes_and_accounts_receivable_cny": _number(
                    balance,
                    "NOTE_ACCOUNTS_RECE",
                ),
                "inventory_cny": _number(balance, "INVENTORY"),
                "contract_assets_cny": _number(balance, "CONTRACT_ASSET"),
            }
            if balance is not None
            else None
        ),
        "audit_opinion": opinion,
        "source_completeness": {
            "income": income is not None,
            "balance": balance is not None,
            "cashflow": cashflow is not None,
        },
    }


def _number(row: Mapping[str, Any] | None, field: str) -> float | int | None:
    if row is None:
        return None
    value = row.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def _sum_values(row: Mapping[str, Any], fields: Sequence[str]) -> float | int | None:
    values = [_number(row, field) for field in fields]
    present = [value for value in values if value is not None]
    return sum(present) if present else None


def _date_text(value: Any) -> str | None:
    if not isinstance(value, str) or len(value) < 10:
        return None
    candidate = value[:10]
    try:
        return dt.date.fromisoformat(candidate).isoformat()
    except ValueError:
        return None


def _compact_text(value: Any, *, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    compact = " ".join(value.split())
    if not compact:
        return None
    return compact[:limit]


def _data_gap_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        facts = row.get("manager_screen_facts")
        if not isinstance(facts, Mapping):
            continue
        for gap in facts.get("data_gaps") or []:
            if isinstance(gap, str):
                counts[gap] = counts.get(gap, 0) + 1
    return dict(sorted(counts.items()))


def _existing_summary(
    *,
    target: Path,
    repository_root: Path,
    run_id: str,
    information_cutoff: dt.datetime,
) -> dict[str, Any]:
    rows = read_jsonl(target)
    if not rows:
        raise ManagerScreenSnapshotError("existing manager-screen snapshot is empty")
    for row in rows:
        facts = row.get("manager_screen_facts")
        if (
            not isinstance(facts, Mapping)
            or facts.get("run_id") != run_id
            or facts.get("information_cutoff") != information_cutoff.isoformat()
        ):
            raise ManagerScreenSnapshotError(
                "existing manager-screen snapshot conflicts with requested run or cutoff"
            )
    return {
        "schema_version": 1,
        "run_id": run_id,
        "information_cutoff": information_cutoff.isoformat(),
        "fetched_at": rows[0]["manager_screen_facts"].get("fetched_at"),
        "path": _relative(target, repository_root),
        "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "record_count": len(rows),
        "source_counts": None,
        "data_gap_counts": _data_gap_counts(rows),
        "portfolio_action": None,
    }


def _secucode(company: Mapping[str, Any]) -> str:
    ticker = str(company.get("ticker") or str(company["symbol"]).split(":", 1)[-1])
    suffix = {"SSE": "SH", "SZSE": "SZ", "BSE": "BJ"}.get(str(company.get("exchange")))
    if suffix is None:
        raise ManagerScreenSnapshotError(
            f"unsupported exchange for {ticker}: {company.get('exchange')}"
        )
    return f"{ticker}.{suffix}"


def _symbol(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"CN:[0-9]{6}", value):
        raise ManagerScreenSnapshotError(f"invalid CN symbol: {value}")
    return value


def _identifier(value: Any) -> str:
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise ManagerScreenSnapshotError("run_id is invalid")
    return value


def _positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ManagerScreenSnapshotError(f"{label} must be a positive integer")
    return value


def _aware(value: dt.datetime, label: str) -> dt.datetime:
    if not isinstance(value, dt.datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ManagerScreenSnapshotError(f"{label} must include timezone information")
    return value


def _relative(path: Path, repository_root: Path) -> str:
    try:
        return path.resolve().relative_to(repository_root.resolve()).as_posix()
    except ValueError as exc:
        raise ManagerScreenSnapshotError(f"path is outside repository: {path}") from exc
