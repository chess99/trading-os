from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re
import time
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .coverage_store import (
    COMPANIES_FILE,
    read_jsonl,
    serialized_coverage_write,
    write_jsonl,
)
from .manager_screen_terminal_governance import (
    ManagerScreenTerminalGovernanceError,
    require_manager_screen_terminal_governance_open,
)
from .sealing import SealingError, seal_json, verify_sealed

DEFAULT_ENDPOINT = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
DEFAULT_QUOTE_ENDPOINT = "https://push2.eastmoney.com/api/qt/ulist.np/get"
DEFAULT_TENCENT_QUOTE_ENDPOINT = "https://qt.gtimg.cn/q="
DEFAULT_QUOTE_MAX_AGE = dt.timedelta(days=3)
QUOTE_FUTURE_TOLERANCE = dt.timedelta(minutes=5)
DATE_ONLY_QUOTE_TIME = dt.time(hour=15)
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
QUOTE_FIELDS = (
    "as_of",
    "price",
    "currency",
    "market_cap_cny",
    "float_market_cap_cny",
    "pe_ttm",
    "pb",
    "roe",
    "revenue_growth_pct",
    "profit_growth_pct",
    "debt_to_asset_pct",
    "dividend_yield_pct",
    "turnover_cny",
    "turnover_rate_pct",
    "source",
    "fetched_at",
)

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
FetchQuotePayload = Callable[[str], Mapping[str, Any]]
FetchQuoteText = Callable[[str], bytes | str]


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
    quote_snapshot: Sequence[Mapping[str, Any]] | None = None,
    quote_max_age: dt.timedelta = DEFAULT_QUOTE_MAX_AGE,
) -> dict[str, Any]:
    """Build one compact, fact-only company snapshot for a manager-screen run."""

    base = Path(root)
    repository_root = base.parent.parent
    run = _identifier(run_id)
    cutoff = _aware(information_cutoff, "information_cutoff")
    fetched = _aware(fetched_at, "fetched_at")
    if fetched < cutoff:
        raise ManagerScreenSnapshotError("fetched_at cannot be before information_cutoff")
    quote_max_age_seconds = _quote_max_age_seconds(quote_max_age)
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
        if quote_snapshot is not None:
            raise ManagerScreenSnapshotError(
                "existing companies.jsonl is immutable; create a sealed quote amendment "
                "instead of injecting refreshed quotes into it"
            )
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
    companies = _apply_quote_snapshot(
        companies,
        quote_snapshot=quote_snapshot,
        fetched_at=fetched,
    )
    symbols = {_symbol(item.get("symbol")) for item in companies}
    quote_freshness_by_symbol = {
        _symbol(company.get("symbol")): _validate_quote_freshness(
            company,
            evaluated_at=cutoff,
            max_age_seconds=quote_max_age_seconds,
        )
        for company in companies
    }
    secucodes = {secucode for item in companies if (secucode := _secucode(item)) is not None}
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
        quote_freshness = quote_freshness_by_symbol[symbol]
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
        if _secucode(company) is None:
            data_gaps.append("unsupported_exchange_identity")
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
            "quote_freshness": quote_freshness,
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
        "quote_freshness_policy": {
            "max_age_seconds": quote_max_age_seconds,
            "future_tolerance_seconds": int(QUOTE_FUTURE_TOLERANCE.total_seconds()),
        },
        "portfolio_action": None,
    }


@serialized_coverage_write
def prepare_manager_screen_quote_amendment(
    *,
    root: str | Path,
    run_id: str,
    amendment_id: str,
    effective_at: dt.datetime,
    quote_snapshot: Sequence[Mapping[str, Any]],
    quote_max_age: dt.timedelta = DEFAULT_QUOTE_MAX_AGE,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Seal a full-universe quote overlay without mutating companies.jsonl."""

    base = Path(root)
    repository_root = base.parent.parent
    run = _identifier(run_id)
    amendment = _identifier(amendment_id)
    effective = _aware(effective_at, "effective_at")
    max_age_seconds = _quote_max_age_seconds(quote_max_age)
    base_snapshot = (base / "snapshots" / run / "companies.jsonl").resolve()
    try:
        base_snapshot.relative_to(repository_root.resolve())
    except ValueError as exc:
        raise ManagerScreenSnapshotError(
            "manager-screen base snapshot must be inside the repository"
        ) from exc
    rows = read_jsonl(base_snapshot)
    if not rows:
        raise ManagerScreenSnapshotError(f"manager-screen base snapshot is missing or empty: {run}")
    refreshed = _apply_quote_snapshot(
        rows,
        quote_snapshot=quote_snapshot,
        fetched_at=effective,
    )
    quotes = []
    for company in refreshed:
        freshness = _validate_quote_freshness(
            company,
            evaluated_at=effective,
            max_age_seconds=max_age_seconds,
        )
        quote = {"symbol": _symbol(company.get("symbol"))}
        quote.update({field: company.get(field) for field in QUOTE_FIELDS})
        quote["as_of"] = freshness["quote_as_of"]
        quote["quote_freshness"] = freshness
        quotes.append(quote)
    quotes.sort(key=lambda item: item["symbol"])
    target = (
        Path(output_path)
        if output_path is not None
        else base / "snapshots" / run / "quote-amendments" / f"{amendment}.json"
    )
    if not target.is_absolute():
        target = repository_root / target
    target = target.resolve()
    try:
        target.relative_to(repository_root.resolve())
    except ValueError as exc:
        raise ManagerScreenSnapshotError(
            "manager-screen quote amendment must be stored inside the repository"
        ) from exc
    target_seal = target.with_name(f"{target.name}.seal.json")
    if not target.exists() and not target_seal.exists():
        _require_full_market_allocation_open(
            base=base,
            run_id=run,
        )
    payload = {
        "schema_version": 1,
        "run_id": run,
        "amendment_id": amendment,
        "effective_at": effective.isoformat(),
        "base_snapshot_path": _relative(base_snapshot, repository_root),
        "base_snapshot_sha256": hashlib.sha256(base_snapshot.read_bytes()).hexdigest(),
        "quote_freshness_policy": {
            "max_age_seconds": max_age_seconds,
            "future_tolerance_seconds": int(QUOTE_FUTURE_TOLERANCE.total_seconds()),
        },
        "quote_count": len(quotes),
        "quotes": quotes,
        "portfolio_action": None,
    }
    if target.exists():
        try:
            seal = verify_sealed(target)
            existing = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, SealingError) as exc:
            raise ManagerScreenSnapshotError(
                f"existing quote amendment is not validly sealed: {target}"
            ) from exc
        if seal.artifact_type != "manager_screen_quote_amendment" or existing != payload:
            raise ManagerScreenSnapshotError(
                f"sealed quote amendment conflicts with request: {amendment}"
            )
    else:
        seal = seal_json(
            target,
            payload,
            artifact_type="manager_screen_quote_amendment",
            sealed_at=effective,
        )
    return {
        "schema_version": 1,
        "run_id": run,
        "amendment_id": amendment,
        "effective_at": effective.isoformat(),
        "path": _relative(target, repository_root),
        "sha256": seal.sha256,
        "quote_count": len(quotes),
        "base_snapshot_sha256": payload["base_snapshot_sha256"],
        "quote_freshness_policy": payload["quote_freshness_policy"],
        "portfolio_action": None,
    }


def _require_full_market_allocation_open(*, base: Path, run_id: str) -> None:
    """Forbid a new quote amendment after the allocation singleton is frozen."""

    try:
        require_manager_screen_terminal_governance_open(
            root=base,
            run_id=run_id,
            operation="new quote amendment",
        )
    except ManagerScreenTerminalGovernanceError as exc:
        raise ManagerScreenSnapshotError(str(exc)) from exc


def fetch_eastmoney_previous_close_quotes(
    *,
    root: str | Path,
    run_id: str,
    quote_date: dt.date,
    fetched_at: dt.datetime,
    endpoint: str = DEFAULT_QUOTE_ENDPOINT,
    chunk_size: int = 80,
    fetch_payload: FetchQuotePayload | None = None,
) -> list[dict[str, Any]]:
    """Fetch an exact-universe previous-close snapshot from Eastmoney.

    The endpoint's ``f18`` field is the previous trading close. The caller must
    provide that trading date explicitly; this prevents a live intraday price
    from being mislabeled as a completed close.
    """

    base = Path(root)
    run = _identifier(run_id)
    fetched = _aware(fetched_at, "fetched_at")
    if not isinstance(quote_date, dt.date) or isinstance(quote_date, dt.datetime):
        raise ManagerScreenSnapshotError("quote_date must be a date")
    if quote_date >= fetched.date():
        raise ManagerScreenSnapshotError("previous-close quote_date must precede fetched_at date")
    if (
        isinstance(chunk_size, bool)
        or not isinstance(chunk_size, int)
        or not 1 <= chunk_size <= 100
    ):
        raise ManagerScreenSnapshotError("quote chunk_size must be between 1 and 100")
    snapshot_path = base / "snapshots" / run / "companies.jsonl"
    companies = read_jsonl(snapshot_path)
    if not companies:
        raise ManagerScreenSnapshotError(f"manager-screen base snapshot is missing or empty: {run}")
    expected = {
        _symbol(row.get("symbol")): {
            "name": row.get("name"),
            "price": row.get("price"),
            "market_cap_cny": row.get("market_cap_cny"),
            "float_market_cap_cny": row.get("float_market_cap_cny"),
            "pe_ttm": row.get("pe_ttm"),
            "pb": row.get("pb"),
        }
        for row in companies
    }
    if len(expected) != len(companies):
        raise ManagerScreenSnapshotError("manager-screen base snapshot contains duplicate symbols")
    secid_to_symbol = {_eastmoney_secid(symbol): symbol for symbol in expected}
    fetch = fetch_payload or _fetch_quote_payload
    observed: dict[str, Mapping[str, Any]] = {}
    secids = sorted(secid_to_symbol)
    fields = "f2,f9,f12,f14,f18,f20,f21,f23,f124"
    for offset in range(0, len(secids), chunk_size):
        chunk = secids[offset : offset + chunk_size]
        query = urllib.parse.urlencode(
            {
                "fltt": 2,
                "invt": 2,
                "fields": fields,
                "secids": ",".join(chunk),
            }
        )
        payload = fetch(f"{endpoint}?{query}")
        if not isinstance(payload, Mapping):
            raise ManagerScreenSnapshotError("Eastmoney quote response must be an object")
        response_code = payload.get("rc")
        if (
            isinstance(response_code, bool)
            or not isinstance(response_code, int)
            or response_code != 0
        ):
            raise ManagerScreenSnapshotError(
                f"Eastmoney quote response returned failure rc={response_code!r}"
            )
        data = payload.get("data") if isinstance(payload, Mapping) else None
        rows = data.get("diff") if isinstance(data, Mapping) else None
        if not isinstance(rows, list):
            raise ManagerScreenSnapshotError("Eastmoney quote response does not contain data.diff")
        total = data.get("total")
        if isinstance(total, bool) or not isinstance(total, int):
            raise ManagerScreenSnapshotError(
                "Eastmoney quote response data.total must be an integer"
            )
        if total != len(rows) or total != len(chunk):
            raise ManagerScreenSnapshotError(
                "Eastmoney quote response count does not match the requested chunk: "
                f"requested={len(chunk)}, total={total}, rows={len(rows)}"
            )
        requested_symbols = {secid_to_symbol[secid] for secid in chunk}
        chunk_symbols: set[str] = set()
        for raw in rows:
            if not isinstance(raw, Mapping):
                raise ManagerScreenSnapshotError("Eastmoney quote row must be an object")
            ticker = raw.get("f12")
            if not isinstance(ticker, str) or not re.fullmatch(r"[0-9]{6}", ticker):
                raise ManagerScreenSnapshotError("Eastmoney quote ticker is invalid")
            symbol = f"CN:{ticker}"
            if symbol not in expected:
                raise ManagerScreenSnapshotError(
                    f"Eastmoney returned a symbol outside the frozen universe: {symbol}"
                )
            if symbol in observed:
                raise ManagerScreenSnapshotError(f"Eastmoney returned a duplicate quote: {symbol}")
            if symbol not in requested_symbols:
                raise ManagerScreenSnapshotError(
                    f"Eastmoney returned a symbol outside the requested quote chunk: {symbol}"
                )
            _eastmoney_quote_update_datetime(
                raw.get("f124"),
                symbol=symbol,
                quote_date=quote_date,
                fetched_at=fetched,
            )
            observed[symbol] = raw
            chunk_symbols.add(symbol)
        if chunk_symbols != requested_symbols:
            missing = sorted(requested_symbols - chunk_symbols)
            unexpected = sorted(chunk_symbols - requested_symbols)
            raise ManagerScreenSnapshotError(
                "Eastmoney quote response does not exactly cover the requested chunk; "
                f"missing={missing}, unexpected={unexpected}"
            )
    expected_symbols = set(expected)
    observed_symbols = set(observed)
    if len(observed) != len(expected) or observed_symbols != expected_symbols:
        missing = sorted(expected_symbols - observed_symbols)
        unexpected = sorted(observed_symbols - expected_symbols)
        raise ManagerScreenSnapshotError(
            "Eastmoney previous-close response does not cover the frozen universe; "
            f"missing={missing[:10]}, unexpected={unexpected[:10]}"
        )

    source = (
        "Eastmoney push2 ulist.np/get f18 previous trading close; "
        f"explicit close date {quote_date.isoformat()}"
    )
    result = []
    for symbol in sorted(expected):
        raw = observed[symbol]
        previous_close = _positive_quote_number(raw.get("f18"), f"{symbol}.f18")
        current_price = _optional_quote_number(raw.get("f2"))
        base_quote = expected[symbol]
        total_market_cap = _scaled_quote_value(
            current_value=raw.get("f20"),
            current_price=current_price,
            base_value=base_quote.get("market_cap_cny"),
            base_price=base_quote.get("price"),
            target_price=previous_close,
        )
        float_market_cap = _scaled_quote_value(
            current_value=raw.get("f21"),
            current_price=current_price,
            base_value=base_quote.get("float_market_cap_cny"),
            base_price=base_quote.get("price"),
            target_price=previous_close,
        )
        result.append(
            {
                "symbol": symbol,
                "price": previous_close,
                "as_of": quote_date.isoformat(),
                "currency": "CNY",
                "market_cap_cny": total_market_cap,
                "float_market_cap_cny": float_market_cap,
                "pe_ttm": _scaled_multiple(
                    current_multiple=raw.get("f9"),
                    current_price=current_price,
                    base_multiple=base_quote.get("pe_ttm"),
                    base_price=base_quote.get("price"),
                    target_price=previous_close,
                ),
                "pb": _scaled_multiple(
                    current_multiple=raw.get("f23"),
                    current_price=current_price,
                    base_multiple=base_quote.get("pb"),
                    base_price=base_quote.get("price"),
                    target_price=previous_close,
                ),
                "turnover_cny": None,
                "turnover_rate_pct": None,
                "source": source,
                "fetched_at": fetched.isoformat(),
            }
        )
    return result


def fetch_tencent_previous_close_quotes(
    *,
    root: str | Path,
    run_id: str,
    quote_date: dt.date,
    fetched_at: dt.datetime,
    endpoint: str = DEFAULT_TENCENT_QUOTE_ENDPOINT,
    chunk_size: int = 80,
    fetch_text: FetchQuoteText | None = None,
) -> list[dict[str, Any]]:
    """Fetch an exact-universe previous-close snapshot from Tencent quotes."""

    base = Path(root)
    run = _identifier(run_id)
    fetched = _aware(fetched_at, "fetched_at")
    if not isinstance(quote_date, dt.date) or isinstance(quote_date, dt.datetime):
        raise ManagerScreenSnapshotError("quote_date must be a date")
    if quote_date >= fetched.date():
        raise ManagerScreenSnapshotError("previous-close quote_date must precede fetched_at date")
    if (
        isinstance(chunk_size, bool)
        or not isinstance(chunk_size, int)
        or not 1 <= chunk_size <= 100
    ):
        raise ManagerScreenSnapshotError("Tencent quote chunk_size must be between 1 and 100")
    snapshot_path = base / "snapshots" / run / "companies.jsonl"
    companies = read_jsonl(snapshot_path)
    if not companies:
        raise ManagerScreenSnapshotError(f"manager-screen base snapshot is missing or empty: {run}")

    expected: dict[str, dict[str, Any]] = {}
    symbols: set[str] = set()
    for company in companies:
        symbol = _symbol(company.get("symbol"))
        if symbol in symbols:
            raise ManagerScreenSnapshotError(
                "manager-screen base snapshot contains duplicate symbols"
            )
        symbols.add(symbol)
        code = _tencent_quote_code(company)
        if code in expected:
            raise ManagerScreenSnapshotError(
                f"manager-screen base snapshot contains duplicate Tencent code: {code}"
            )
        expected[code] = {
            "symbol": symbol,
            "price": company.get("price"),
            "market_cap_cny": company.get("market_cap_cny"),
            "float_market_cap_cny": company.get("float_market_cap_cny"),
            "pe_ttm": company.get("pe_ttm"),
            "pb": company.get("pb"),
        }

    fetch = fetch_text or _fetch_tencent_quote_text
    observed: dict[str, list[str]] = {}
    codes = sorted(expected)
    for offset in range(0, len(codes), chunk_size):
        chunk = codes[offset : offset + chunk_size]
        response = fetch(f"{endpoint}{','.join(chunk)}")
        text = _decode_tencent_quote_text(response)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if len(lines) != len(chunk):
            raise ManagerScreenSnapshotError(
                "Tencent quote response count does not match the requested chunk: "
                f"requested={len(chunk)}, rows={len(lines)}"
            )
        chunk_codes: set[str] = set()
        for line in lines:
            match = re.fullmatch(
                r'v_((?:sh|sz|bj)[0-9]{6})="([^"\r\n]*)";',
                line,
            )
            if match is None:
                raise ManagerScreenSnapshotError("Tencent quote response row is malformed")
            code, value = match.groups()
            if code not in expected:
                raise ManagerScreenSnapshotError(
                    f"Tencent returned a code outside the frozen universe: {code}"
                )
            if code in observed or code in chunk_codes:
                raise ManagerScreenSnapshotError(f"Tencent returned a duplicate quote: {code}")
            if code not in chunk:
                raise ManagerScreenSnapshotError(
                    f"Tencent returned a code outside the requested quote chunk: {code}"
                )
            fields = value.split("~")
            if len(fields) <= 53:
                raise ManagerScreenSnapshotError(
                    f"Tencent quote row does not contain required fields: {code}"
                )
            ticker = fields[2]
            if ticker != code[2:]:
                raise ManagerScreenSnapshotError(
                    f"Tencent quote ticker does not match requested code: {code}"
                )
            _tencent_quote_update_datetime(
                fields[30],
                code=code,
                quote_date=quote_date,
                fetched_at=fetched,
            )
            observed[code] = fields
            chunk_codes.add(code)
        requested_codes = set(chunk)
        if chunk_codes != requested_codes:
            missing = sorted(requested_codes - chunk_codes)
            unexpected = sorted(chunk_codes - requested_codes)
            raise ManagerScreenSnapshotError(
                "Tencent quote response does not exactly cover the requested chunk; "
                f"missing={missing}, unexpected={unexpected}"
            )

    observed_codes = set(observed)
    expected_codes = set(expected)
    if len(observed) != len(expected) or observed_codes != expected_codes:
        missing = sorted(expected_codes - observed_codes)
        unexpected = sorted(observed_codes - expected_codes)
        raise ManagerScreenSnapshotError(
            "Tencent previous-close response does not cover the frozen universe; "
            f"missing={missing[:10]}, unexpected={unexpected[:10]}"
        )

    source = (
        "Tencent qt.gtimg.cn fields 4 previous close, 44/45 market cap, "
        "46 PB and 53 PE TTM; "
        f"explicit close date {quote_date.isoformat()}"
    )
    result = []
    for code, base_quote in sorted(
        expected.items(),
        key=lambda item: item[1]["symbol"],
    ):
        fields = observed[code]
        symbol = base_quote["symbol"]
        previous_close = _positive_tencent_number(
            fields[4],
            f"{symbol}.field4",
        )
        current_price = _optional_tencent_number(fields[3])
        total_market_cap = _scaled_quote_value(
            current_value=_scaled_tencent_cny(fields[45]),
            current_price=current_price,
            base_value=base_quote.get("market_cap_cny"),
            base_price=base_quote.get("price"),
            target_price=previous_close,
        )
        float_market_cap = _scaled_quote_value(
            current_value=_scaled_tencent_cny(fields[44]),
            current_price=current_price,
            base_value=base_quote.get("float_market_cap_cny"),
            base_price=base_quote.get("price"),
            target_price=previous_close,
        )
        result.append(
            {
                "symbol": symbol,
                "price": previous_close,
                "as_of": quote_date.isoformat(),
                "currency": "CNY",
                "market_cap_cny": total_market_cap,
                "float_market_cap_cny": float_market_cap,
                "pe_ttm": _scaled_multiple(
                    current_multiple=_optional_tencent_number(fields[53]),
                    current_price=current_price,
                    base_multiple=base_quote.get("pe_ttm"),
                    base_price=base_quote.get("price"),
                    target_price=previous_close,
                ),
                "pb": _scaled_multiple(
                    current_multiple=_optional_tencent_number(fields[46]),
                    current_price=current_price,
                    base_multiple=base_quote.get("pb"),
                    base_price=base_quote.get("price"),
                    target_price=previous_close,
                ),
                "turnover_cny": None,
                "turnover_rate_pct": None,
                "source": source,
                "fetched_at": fetched.isoformat(),
            }
        )
    return result


def _apply_quote_snapshot(
    companies: Sequence[Mapping[str, Any]],
    *,
    quote_snapshot: Sequence[Mapping[str, Any]] | None,
    fetched_at: dt.datetime,
) -> list[dict[str, Any]]:
    normalized = [dict(company) for company in companies]
    if quote_snapshot is None:
        return normalized
    by_symbol: dict[str, dict[str, Any]] = {}
    universe = {_symbol(company.get("symbol")) for company in companies}
    for index, raw in enumerate(quote_snapshot):
        if not isinstance(raw, Mapping):
            raise ManagerScreenSnapshotError(f"quote_snapshot[{index}] must be an object")
        symbol = _symbol(raw.get("symbol"))
        if symbol not in universe:
            raise ManagerScreenSnapshotError(
                f"quote snapshot contains a symbol outside the company universe: {symbol}"
            )
        if symbol in by_symbol:
            raise ManagerScreenSnapshotError(f"duplicate quote symbol: {symbol}")
        price = raw.get("price")
        if (
            isinstance(price, bool)
            or not isinstance(price, (int, float))
            or not math.isfinite(float(price))
            or price <= 0
        ):
            raise ManagerScreenSnapshotError(f"invalid quote price for {symbol}")
        quote = {field: raw.get(field) for field in QUOTE_FIELDS}
        quote["price"] = price
        quote["as_of"] = raw.get("as_of")
        quote["source"] = raw.get("source")
        quote["fetched_at"] = raw.get("fetched_at") or fetched_at.isoformat()
        by_symbol[symbol] = quote
    missing = sorted(universe - set(by_symbol))
    if missing:
        raise ManagerScreenSnapshotError(
            "injected quote snapshot must cover the full company universe; "
            f"missing: {', '.join(missing[:10])}"
        )
    for company in normalized:
        company.update(by_symbol[_symbol(company.get("symbol"))])
    return normalized


def _validate_quote_freshness(
    company: Mapping[str, Any],
    *,
    evaluated_at: dt.datetime,
    max_age_seconds: int,
) -> dict[str, Any]:
    symbol = _symbol(company.get("symbol"))
    price = company.get("price")
    if (
        isinstance(price, bool)
        or not isinstance(price, (int, float))
        or not math.isfinite(float(price))
        or price <= 0
    ):
        raise ManagerScreenSnapshotError(f"current quote price is missing or invalid: {symbol}")
    quote_as_of = _quote_datetime(
        company.get("as_of"),
        timezone=evaluated_at.tzinfo,
        field=f"{symbol}.as_of",
    )
    age = evaluated_at - quote_as_of
    if age > dt.timedelta(seconds=max_age_seconds):
        raise ManagerScreenSnapshotError(
            f"stale quote for {symbol}: {quote_as_of.isoformat()} exceeds "
            f"max age {max_age_seconds}s"
        )
    if -age > QUOTE_FUTURE_TOLERANCE:
        raise ManagerScreenSnapshotError(
            f"quote is after the information cutoff for {symbol}: {quote_as_of.isoformat()}"
        )
    source = company.get("source")
    if not isinstance(source, str) or not source.strip():
        raise ManagerScreenSnapshotError(f"quote source is missing: {symbol}")
    return {
        "schema_version": 1,
        "status": "fresh",
        "quote_as_of": quote_as_of.isoformat(),
        "evaluated_at": evaluated_at.isoformat(),
        "age_seconds": max(0.0, age.total_seconds()),
        "max_age_seconds": max_age_seconds,
        "future_tolerance_seconds": int(QUOTE_FUTURE_TOLERANCE.total_seconds()),
        "source": source.strip(),
    }


def _quote_max_age_seconds(value: dt.timedelta) -> int:
    if not isinstance(value, dt.timedelta):
        raise ManagerScreenSnapshotError("quote_max_age must be a timedelta")
    seconds = value.total_seconds()
    if not math.isfinite(seconds) or seconds <= 0:
        raise ManagerScreenSnapshotError("quote_max_age must be positive")
    return int(seconds)


def _quote_datetime(
    value: Any,
    *,
    timezone: dt.tzinfo | None,
    field: str,
) -> dt.datetime:
    if not isinstance(value, str) or not value.strip():
        raise ManagerScreenSnapshotError(f"{field} must be an ISO date or datetime")
    candidate = value.strip()
    if "T" not in candidate:
        try:
            return dt.datetime.combine(
                dt.date.fromisoformat(candidate),
                DATE_ONLY_QUOTE_TIME,
                tzinfo=timezone,
            )
        except ValueError as exc:
            raise ManagerScreenSnapshotError(f"{field} must be an ISO date or datetime") from exc
    try:
        parsed = dt.datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ManagerScreenSnapshotError(f"{field} must be an ISO date or datetime") from exc
    if parsed.tzinfo is None:
        raise ManagerScreenSnapshotError(f"{field} datetime must include UTC offset")
    return parsed


def _eastmoney_secid(symbol: str) -> str:
    ticker = _symbol(symbol).split(":", 1)[1]
    market = "1" if ticker.startswith("6") else "0"
    return f"{market}.{ticker}"


def _tencent_quote_code(company: Mapping[str, Any]) -> str:
    symbol = _symbol(company.get("symbol"))
    ticker = symbol.split(":", 1)[1]
    frozen_ticker = company.get("ticker")
    if frozen_ticker is not None and frozen_ticker != ticker:
        raise ManagerScreenSnapshotError(f"manager-screen ticker does not match symbol: {symbol}")
    exchange = company.get("exchange")
    prefix = {
        "SSE": "sh",
        "SZSE": "sz",
        "BSE": "bj",
    }.get(exchange)
    # The frozen universe contains one post-restructuring Shenzhen security
    # (CN:302132) whose upstream snapshot predates exchange normalization.
    # A 0/2/3-leading A-share ticker is unambiguously Shenzhen for this quote
    # provider, so retain exact symbol/ticker checks while allowing that
    # narrowly inferable identity. Other unknown exchanges still fail closed.
    if prefix is None and exchange == "UNKNOWN" and ticker.startswith(("0", "2", "3")):
        prefix = "sz"
    if prefix is None:
        raise ManagerScreenSnapshotError(
            f"unsupported exchange for Tencent quote identity: {symbol}"
        )
    return f"{prefix}{ticker}"


def _fetch_quote_payload(url: str) -> Mapping[str, Any]:
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Trading-OS manager-screen quotes/1.0",
                    "Referer": "https://quote.eastmoney.com/",
                },
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, Mapping) or payload.get("rc") not in {0, None}:
                raise RuntimeError("Eastmoney quote API returned failure")
            return payload
        except (OSError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
            last_error = exc
            if attempt == 3:
                break
            time.sleep(0.5 * (attempt + 1))
    raise ManagerScreenSnapshotError(f"failed to fetch Eastmoney quote payload: {last_error}")


def _fetch_tencent_quote_text(url: str) -> bytes:
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Trading-OS manager-screen quotes/1.0",
                    "Referer": "https://gu.qq.com/",
                    "Accept-Charset": "gb18030",
                },
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        except (OSError, TimeoutError) as exc:
            last_error = exc
            if attempt == 3:
                break
            time.sleep(0.5 * (attempt + 1))
    raise ManagerScreenSnapshotError(f"failed to fetch Tencent quote text: {last_error}")


def _decode_tencent_quote_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, bytes):
        raise ManagerScreenSnapshotError("Tencent quote response must be GB18030 bytes or text")
    try:
        return value.decode("gb18030")
    except UnicodeDecodeError as exc:
        raise ManagerScreenSnapshotError("Tencent quote response is not valid GB18030") from exc


def _eastmoney_quote_update_datetime(
    value: Any,
    *,
    symbol: str,
    quote_date: dt.date,
    fetched_at: dt.datetime,
) -> dt.datetime:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) <= 0
        or not float(value).is_integer()
    ):
        raise ManagerScreenSnapshotError(
            f"Eastmoney quote update timestamp is invalid: {symbol}.f124"
        )
    try:
        updated_at = dt.datetime.fromtimestamp(int(value), tz=fetched_at.tzinfo)
    except (OverflowError, OSError, ValueError) as exc:
        raise ManagerScreenSnapshotError(
            f"Eastmoney quote update timestamp is invalid: {symbol}.f124"
        ) from exc
    if updated_at.date() < quote_date:
        raise ManagerScreenSnapshotError(
            "Eastmoney quote update predates the declared previous-close date: "
            f"{symbol} updated_at={updated_at.isoformat()}, "
            f"quote_date={quote_date.isoformat()}"
        )
    if updated_at > fetched_at + QUOTE_FUTURE_TOLERANCE:
        raise ManagerScreenSnapshotError(
            "Eastmoney quote update is after fetched_at: "
            f"{symbol} updated_at={updated_at.isoformat()}"
        )
    return updated_at


def _tencent_quote_update_datetime(
    value: Any,
    *,
    code: str,
    quote_date: dt.date,
    fetched_at: dt.datetime,
) -> dt.datetime:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{14}", value):
        raise ManagerScreenSnapshotError(
            f"Tencent quote update timestamp is invalid: {code}.field30"
        )
    try:
        updated_at = dt.datetime.strptime(value, "%Y%m%d%H%M%S").replace(tzinfo=fetched_at.tzinfo)
    except ValueError as exc:
        raise ManagerScreenSnapshotError(
            f"Tencent quote update timestamp is invalid: {code}.field30"
        ) from exc
    if updated_at.date() < quote_date:
        raise ManagerScreenSnapshotError(
            "Tencent quote update predates the declared previous-close date: "
            f"{code} updated_at={updated_at.isoformat()}, "
            f"quote_date={quote_date.isoformat()}"
        )
    if updated_at > fetched_at + QUOTE_FUTURE_TOLERANCE:
        raise ManagerScreenSnapshotError(
            f"Tencent quote update is after fetched_at: {code} updated_at={updated_at.isoformat()}"
        )
    return updated_at


def _positive_tencent_number(value: Any, field: str) -> float:
    result = _optional_tencent_number(value)
    if result is None or result <= 0:
        raise ManagerScreenSnapshotError(f"{field} must be a positive number")
    return result


def _optional_tencent_number(value: Any) -> float | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        result = float(value)
    except ValueError:
        return None
    return result if math.isfinite(result) else None


def _scaled_tencent_cny(value: Any) -> float | None:
    result = _optional_tencent_number(value)
    return None if result is None else result * 100_000_000


def _positive_quote_number(value: Any, field: str) -> float:
    result = _optional_quote_number(value)
    if result is None or result <= 0:
        raise ManagerScreenSnapshotError(f"{field} must be a positive number")
    return result


def _optional_quote_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def _scaled_quote_value(
    *,
    current_value: Any,
    current_price: float | None,
    base_value: Any,
    base_price: Any,
    target_price: float,
) -> int | None:
    current = _optional_quote_number(current_value)
    if current is not None and current > 0 and current_price is not None and current_price > 0:
        return int(round(current * target_price / current_price))
    base = _optional_quote_number(base_value)
    anchor = _optional_quote_number(base_price)
    if base is not None and base > 0 and anchor is not None and anchor > 0:
        return int(round(base * target_price / anchor))
    return None


def _scaled_multiple(
    *,
    current_multiple: Any,
    current_price: float | None,
    base_multiple: Any,
    base_price: Any,
    target_price: float,
) -> float | None:
    current = _optional_quote_number(current_multiple)
    if current is not None and current_price is not None and current_price > 0:
        return round(current * target_price / current_price, 4)
    base = _optional_quote_number(base_multiple)
    anchor = _optional_quote_number(base_price)
    if base is not None and anchor is not None and anchor > 0:
        return round(base * target_price / anchor, 4)
    return None


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
                "SECURITY_CODE" if report_name == PROFILE_REPORT else "SECURITY_CODE,UPDATE_DATE"
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
    freshness = rows[0]["manager_screen_facts"].get("quote_freshness")
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
        "quote_freshness_policy": (
            {
                "max_age_seconds": freshness.get("max_age_seconds"),
                "future_tolerance_seconds": freshness.get("future_tolerance_seconds"),
            }
            if isinstance(freshness, Mapping)
            else None
        ),
        "portfolio_action": None,
    }


def _secucode(company: Mapping[str, Any]) -> str | None:
    ticker = str(company.get("ticker") or str(company["symbol"]).split(":", 1)[-1])
    suffix = {"SSE": "SH", "SZSE": "SZ", "BSE": "BJ"}.get(str(company.get("exchange")))
    if suffix is None:
        return None
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
