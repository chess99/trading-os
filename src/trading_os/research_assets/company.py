from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from .models import ReportType, UnderwritingStatus
from .sealing import verify_sealed


class AssetValidationError(ValueError):
    """Raised when a v2 company research asset is invalid."""


ALLOWED_MARKETS = {"CN", "HK", "US"}
ALLOWED_SECURITY_STATUSES = {"active", "inactive", "archived"}
ALLOWED_COVERAGE_STATUSES = {
    "covered",
    "researching",
    "requires_rebaseline",
    "inactive",
}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}
ALLOWED_TRIGGER_TYPES = {"date", "price", "filing", "event", "thesis"}
SYMBOL_RE = re.compile(r"^(CN|HK|US):[A-Z0-9.]+$")
REPORT_PATH_RE = re.compile(
    r"^reports/(?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})-"
    r"[a-z0-9][a-z0-9-]*\.md$"
)
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
REPORT_META_RE = re.compile(
    r"\A<!-- trading-os-report-meta\r?\n(?P<meta>.*?)\r?\n-->\r?\n",
    re.DOTALL,
)

META_KEYS = {
    "schema_version",
    "identity",
    "research",
    "reports",
    "underwriting",
    "valuation",
    "triggers",
    "updated_at",
}
IDENTITY_KEYS = {
    "symbol",
    "market",
    "ticker",
    "name",
    "currency",
    "security_status",
}
RESEARCH_REQUIRED_KEYS = {
    "coverage_status",
    "rebaseline_required",
    "information_cutoff",
}
RESEARCH_OPTIONAL_KEYS = {"refresh_due_at", "latest_rapid_triage"}
RESEARCH_KEYS = RESEARCH_REQUIRED_KEYS | RESEARCH_OPTIONAL_KEYS
REPORTS_KEYS = {"latest", "latest_by_type", "history", "historical_artifacts"}
REPORT_RECORD_KEYS = {"report_id", "path", "report_type", "as_of", "sha256"}
HISTORICAL_ARTIFACT_KEYS = {"path", "format", "sha256"}
UNDERWRITING_KEYS = {
    "status",
    "review_id",
    "confidence",
    "evidence_valid_until",
    "reason_codes",
}
VALUATION_KEYS = {
    "currency",
    "price_as_of",
    "bear_value",
    "fair_value_range",
    "buy_zone",
    "reduce_zone",
}
TRIGGER_KEYS = {"trigger_id", "type", "condition", "reason", "active"}
LATEST_RAPID_TRIAGE_KEYS = {
    "report_id",
    "report_path",
    "source_package_path",
    "source_package_sha256",
    "information_cutoff",
    "review_mode",
    "published_at",
}
RAPID_TRIAGE_SOURCE_MANIFEST_KEYS = {
    "schema_version",
    "artifact_type",
    "report_id",
    "symbol",
    "information_cutoff",
    "source_package",
    "sources",
}
RAPID_TRIAGE_SOURCE_PACKAGE_KEYS = {
    "repository_path",
    "seal_manifest_path",
    "artifact_type",
    "sha256",
    "sealed_at",
}
REPORT_FRONT_META_KEYS = {
    "schema_version",
    "report_id",
    "report_type",
    "symbol",
    "as_of",
    "information_cutoff",
    "price_snapshot_id",
    "policy_versions",
    "agent_id",
    "predecessor_reports",
    "sealed_artifacts",
    "source_manifest",
}

REPORT_SECTION_REQUIREMENTS = {
    ReportType.RAPID_TRIAGE.value: {
        "快速结论",
        "业务速览",
        "变化摘要",
        "正常化盈利粗判",
        "市场隐含预期",
        "反方证据",
        "重启触发器",
        "来源",
    },
    ReportType.INITIAL_RESEARCH.value: {
        "结论版",
        "业务理解",
        "行业与竞争格局",
        "公司质量",
        "财务质量",
        "结构化主张",
        "估值",
        "市场隐含预期",
        "情景与赔率",
        "关键假设",
        "跟踪触发器",
        "风险",
        "来源",
    },
    ReportType.MONITORING_UPDATE.value: {
        "上一轮判断复盘",
        "新信息",
        "判断变化",
        "证据更新",
        "跟踪触发器",
        "风险",
        "来源",
    },
    ReportType.UNDERWRITING_REVIEW.value: {
        "承保结论",
        "证据账本",
        "盈利质量桥",
        "现金流桥",
        "正常化盈利",
        "估值与敏感性",
        "市场隐含预期",
        "反方证据",
        "旧主张差异审计",
        "自动阻断检查",
        "失效条件",
        "来源",
    },
    ReportType.CHALLENGER_REVIEW.value: {
        "独立挑战结论",
        "证据账本",
        "盈利质量桥",
        "现金流桥",
        "正常化盈利",
        "估值与敏感性",
        "反方证据",
        "争议点",
        "失效条件",
        "来源",
    },
}


def validate_company_dir(
    company_dir: str | Path, *, strict: bool = True
) -> dict[str, Any]:
    del strict  # v2 validation is always strict.
    path = Path(company_dir)
    if not path.exists():
        raise AssetValidationError(f"company directory does not exist: {path}")
    if not path.is_dir():
        raise AssetValidationError(f"company path is not a directory: {path}")
    meta_path = path / "meta.json"
    if not meta_path.is_file():
        raise AssetValidationError(f"missing meta.json: {meta_path}")

    meta = _read_json_object(meta_path, "meta.json")
    if meta.get("schema_version") != 2:
        raise AssetValidationError(
            "company asset is not schema_version 2; run assets migrate before validation"
        )
    _require_exact_keys(meta, META_KEYS, "meta", unknown_label="unknown meta fields")

    identity = _require_object(meta, "identity", "meta")
    _validate_identity(path, identity)
    research = _require_object(meta, "research", "meta")
    _validate_research(research)
    reports = _require_object(meta, "reports", "meta")
    _validate_reports(path, identity, reports)
    _validate_rapid_triage_state(path, research, reports)
    underwriting = _require_object(meta, "underwriting", "meta")
    _validate_underwriting(underwriting)
    valuation = _require_object(meta, "valuation", "meta")
    _validate_valuation(valuation)
    _validate_triggers(meta.get("triggers"))
    _parse_datetime(meta.get("updated_at"), "updated_at")
    return meta


def validate_research_assets(research_root: str | Path) -> dict[str, Any]:
    root = Path(research_root)
    companies_root = root / "companies"
    company_dirs = _company_dirs(companies_root) if companies_root.exists() else []
    errors: list[dict[str, str]] = []
    valid_count = 0
    for company_dir in company_dirs:
        try:
            validate_company_dir(company_dir)
        except AssetValidationError as exc:
            errors.append({"company_dir": str(company_dir), "error": str(exc)})
        else:
            valid_count += 1
    return {
        "schema_version": 2,
        "company_count": len(company_dirs),
        "valid_count": valid_count,
        "invalid_count": len(errors),
        "errors": errors,
    }


def _validate_identity(company_dir: Path, identity: Mapping[str, Any]) -> None:
    _require_exact_keys(identity, IDENTITY_KEYS, "identity")
    symbol = _require_string(identity, "symbol", "identity")
    market = _require_string(identity, "market", "identity")
    ticker = _require_string(identity, "ticker", "identity")
    _require_string(identity, "name", "identity")
    _require_string(identity, "currency", "identity")
    security_status = _require_string(identity, "security_status", "identity")
    if not SYMBOL_RE.fullmatch(symbol):
        raise AssetValidationError(f"identity.symbol has invalid format: {symbol}")
    if market not in ALLOWED_MARKETS:
        raise AssetValidationError(f"identity.market must be one of {sorted(ALLOWED_MARKETS)}")
    if symbol != f"{market}:{ticker}":
        raise AssetValidationError("identity.symbol must match identity.market and ticker")
    if security_status not in ALLOWED_SECURITY_STATUSES:
        raise AssetValidationError(
            f"identity.security_status must be one of {sorted(ALLOWED_SECURITY_STATUSES)}"
        )
    if company_dir.name != ticker or company_dir.parent.name != market:
        raise AssetValidationError(
            "company directory must end with research/companies/{market}/{ticker}"
        )


def _validate_research(research: Mapping[str, Any]) -> None:
    unknown = sorted(set(research) - RESEARCH_KEYS)
    if unknown:
        raise AssetValidationError(f"unknown research fields: {unknown}")
    missing = sorted(RESEARCH_REQUIRED_KEYS - set(research))
    if missing:
        raise AssetValidationError(f"missing research fields: {missing}")
    coverage_status = _require_string(research, "coverage_status", "research")
    if coverage_status not in ALLOWED_COVERAGE_STATUSES:
        raise AssetValidationError(
            f"research.coverage_status must be one of {sorted(ALLOWED_COVERAGE_STATUSES)}"
        )
    if not isinstance(research.get("rebaseline_required"), bool):
        raise AssetValidationError("research.rebaseline_required must be boolean")
    information_cutoff = research.get("information_cutoff")
    if information_cutoff is not None:
        _parse_datetime(information_cutoff, "research.information_cutoff")
    refresh_due_at = research.get("refresh_due_at")
    if refresh_due_at is not None:
        _parse_datetime(refresh_due_at, "research.refresh_due_at")
    latest_triage = research.get("latest_rapid_triage")
    if latest_triage is not None:
        _validate_latest_rapid_triage(latest_triage)


def _validate_reports(
    company_dir: Path,
    identity: Mapping[str, Any],
    reports: Mapping[str, Any],
) -> None:
    _require_exact_keys(reports, REPORTS_KEYS, "reports")
    history = reports.get("history")
    historical = reports.get("historical_artifacts")
    latest_by_type = reports.get("latest_by_type")
    if not isinstance(history, list):
        raise AssetValidationError("reports.history must be an array")
    if not isinstance(historical, list):
        raise AssetValidationError("reports.historical_artifacts must be an array")
    if not isinstance(latest_by_type, dict):
        raise AssetValidationError("reports.latest_by_type must be an object")

    records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    dates: list[dt.date] = []
    for index, raw_record in enumerate(history):
        if not isinstance(raw_record, dict):
            raise AssetValidationError(f"reports.history[{index}] must be an object")
        record = raw_record
        _require_exact_keys(record, REPORT_RECORD_KEYS, f"reports.history[{index}]")
        report_id = _require_string(record, "report_id", f"reports.history[{index}]")
        report_path_text = _require_string(record, "path", f"reports.history[{index}]")
        report_type = _require_string(
            record, "report_type", f"reports.history[{index}]"
        )
        if report_type not in REPORT_SECTION_REQUIREMENTS:
            raise AssetValidationError(f"unsupported report_type: {report_type}")
        as_of = _parse_date(record.get("as_of"), f"reports.history[{index}].as_of")
        expected_hash = _require_sha256(
            record.get("sha256"), f"reports.history[{index}].sha256"
        )
        match = REPORT_PATH_RE.fullmatch(report_path_text)
        if not match:
            raise AssetValidationError(f"invalid report path: {report_path_text}")
        if match.group("date") != as_of.isoformat():
            raise AssetValidationError("report path date must match report record as_of")
        if report_id in seen_ids:
            raise AssetValidationError(f"duplicate report_id: {report_id}")
        if report_path_text in seen_paths:
            raise AssetValidationError(f"duplicate report path: {report_path_text}")
        seen_ids.add(report_id)
        seen_paths.add(report_path_text)
        dates.append(as_of)

        report_path = _safe_file(company_dir, report_path_text, "report path")
        _require_matching_hash(report_path, expected_hash, "report sha256")
        _validate_report_file(
            company_dir,
            report_path,
            identity=identity,
            record=record,
        )
        if report_type == ReportType.RAPID_TRIAGE.value:
            _validate_rapid_triage_report_linkage(
                company_dir,
                report_path,
                identity=identity,
                record=record,
            )
        records.append(record)

    if dates != sorted(dates):
        raise AssetValidationError("reports.history must be chronological")

    latest = reports.get("latest")
    if history:
        if not isinstance(latest, str) or not latest:
            raise AssetValidationError("reports.latest must reference the latest history item")
        if latest != records[-1]["path"]:
            raise AssetValidationError("reports.latest must equal the last history path")
    elif latest is not None:
        raise AssetValidationError("reports.latest must be null when history is empty")

    valid_types = set(REPORT_SECTION_REQUIREMENTS)
    if set(latest_by_type) - valid_types:
        raise AssetValidationError("reports.latest_by_type contains unsupported report type")
    expected_latest_by_type: dict[str, str] = {}
    for record in records:
        expected_latest_by_type[record["report_type"]] = record["path"]
    if latest_by_type != expected_latest_by_type:
        raise AssetValidationError(
            "reports.latest_by_type must point to the latest history record of each type"
        )

    historical_paths: set[str] = set()
    for index, raw_artifact in enumerate(historical):
        if not isinstance(raw_artifact, dict):
            raise AssetValidationError(
                f"reports.historical_artifacts[{index}] must be an object"
            )
        artifact = raw_artifact
        _require_exact_keys(
            artifact,
            HISTORICAL_ARTIFACT_KEYS,
            f"reports.historical_artifacts[{index}]",
        )
        artifact_path_text = _require_string(
            artifact, "path", f"reports.historical_artifacts[{index}]"
        )
        if artifact.get("format") != "legacy_v1":
            raise AssetValidationError("historical artifact format must be legacy_v1")
        expected_hash = _require_sha256(
            artifact.get("sha256"),
            f"reports.historical_artifacts[{index}].sha256",
        )
        if artifact_path_text in seen_paths or artifact_path_text in historical_paths:
            raise AssetValidationError(f"duplicate historical artifact path: {artifact_path_text}")
        artifact_path = _safe_file(company_dir, artifact_path_text, "historical artifact path")
        _require_matching_hash(artifact_path, expected_hash, "historical artifact sha256")
        historical_paths.add(artifact_path_text)


def _validate_latest_rapid_triage(value: Any) -> None:
    if not isinstance(value, Mapping):
        raise AssetValidationError("research.latest_rapid_triage must be an object")
    _require_exact_keys(value, LATEST_RAPID_TRIAGE_KEYS, "latest_rapid_triage")
    _require_string(value, "report_id", "latest_rapid_triage")
    report_path = _require_string(value, "report_path", "latest_rapid_triage")
    if not REPORT_PATH_RE.fullmatch(report_path):
        raise AssetValidationError("latest_rapid_triage.report_path is invalid")
    _require_string(value, "source_package_path", "latest_rapid_triage")
    _require_sha256(
        value.get("source_package_sha256"),
        "latest_rapid_triage.source_package_sha256",
    )
    _parse_datetime(
        value.get("information_cutoff"),
        "latest_rapid_triage.information_cutoff",
    )
    if value.get("review_mode") not in {"baseline_recheck", "triggered_update"}:
        raise AssetValidationError("latest_rapid_triage.review_mode is invalid")
    _parse_datetime(value.get("published_at"), "latest_rapid_triage.published_at")


def _validate_rapid_triage_state(
    company_dir: Path,
    research: Mapping[str, Any],
    reports: Mapping[str, Any],
) -> None:
    state = research.get("latest_rapid_triage")
    rapid_path = reports.get("latest_by_type", {}).get(ReportType.RAPID_TRIAGE.value)
    if state is None:
        if rapid_path is not None:
            raise AssetValidationError(
                "rapid_triage history requires research.latest_rapid_triage"
            )
        return
    if rapid_path != state["report_path"]:
        raise AssetValidationError(
            "latest_rapid_triage.report_path must match reports.latest_by_type"
        )
    matching = [
        item
        for item in reports["history"]
        if item["path"] == state["report_path"]
        and item["report_type"] == ReportType.RAPID_TRIAGE.value
    ]
    if len(matching) != 1 or matching[0]["report_id"] != state["report_id"]:
        raise AssetValidationError("latest_rapid_triage does not match report history")
    research_cutoff = research.get("information_cutoff")
    if research_cutoff is None or _parse_datetime(
        research_cutoff, "research.information_cutoff"
    ) < _parse_datetime(
        state["information_cutoff"],
        "latest_rapid_triage.information_cutoff",
    ):
        raise AssetValidationError(
            "research.information_cutoff cannot precede latest rapid triage"
        )
    package_path = _safe_repository_file(
        company_dir,
        state["source_package_path"],
        "latest rapid-triage source package",
    )
    try:
        sealed = verify_sealed(package_path)
    except ValueError as exc:
        raise AssetValidationError(
            f"invalid latest rapid-triage source package: {exc}"
        ) from exc
    if sealed.artifact_type != "rapid_triage_package":
        raise AssetValidationError("latest rapid-triage source artifact type is invalid")
    if sealed.sha256 != state["source_package_sha256"]:
        raise AssetValidationError("latest rapid-triage source sha256 does not match")


def _validate_rapid_triage_report_linkage(
    company_dir: Path,
    report_path: Path,
    *,
    identity: Mapping[str, Any],
    record: Mapping[str, Any],
) -> None:
    front = _read_report_front(report_path)
    manifest_path = _safe_file(
        company_dir, str(front["source_manifest"]), "source_manifest path"
    )
    try:
        manifest_seal = verify_sealed(manifest_path)
    except ValueError as exc:
        raise AssetValidationError(
            f"rapid-triage source manifest is not validly sealed: {exc}"
        ) from exc
    if manifest_seal.artifact_type != "rapid_triage_source_manifest":
        raise AssetValidationError("rapid-triage source manifest artifact type is invalid")
    manifest = _read_json_object(manifest_path, "rapid-triage source manifest")
    _require_exact_keys(
        manifest,
        RAPID_TRIAGE_SOURCE_MANIFEST_KEYS,
        "rapid-triage source manifest",
    )
    if manifest.get("schema_version") != 1:
        raise AssetValidationError("rapid-triage source manifest schema_version must be 1")
    if manifest.get("artifact_type") != "rapid_triage_source_manifest":
        raise AssetValidationError("rapid-triage source manifest type does not match")
    if manifest.get("report_id") != record["report_id"]:
        raise AssetValidationError("rapid-triage source manifest report_id does not match")
    if manifest.get("symbol") != identity["symbol"]:
        raise AssetValidationError("rapid-triage source manifest symbol does not match")
    if manifest.get("information_cutoff") != front["information_cutoff"]:
        raise AssetValidationError(
            "rapid-triage source manifest information_cutoff does not match"
        )
    if not isinstance(manifest.get("sources"), list):
        raise AssetValidationError("rapid-triage source manifest sources must be an array")
    package_ref = manifest.get("source_package")
    if not isinstance(package_ref, Mapping):
        raise AssetValidationError("rapid-triage source_package must be an object")
    _require_exact_keys(
        package_ref,
        RAPID_TRIAGE_SOURCE_PACKAGE_KEYS,
        "rapid-triage source_package",
    )
    package_path = _safe_repository_file(
        company_dir,
        _require_string(package_ref, "repository_path", "source_package"),
        "rapid-triage source package",
    )
    seal_path = _safe_repository_file(
        company_dir,
        _require_string(package_ref, "seal_manifest_path", "source_package"),
        "rapid-triage source seal manifest",
    )
    try:
        package_seal = verify_sealed(package_path)
    except ValueError as exc:
        raise AssetValidationError(
            f"rapid-triage source package seal is invalid: {exc}"
        ) from exc
    if seal_path != package_seal.manifest_path.resolve():
        raise AssetValidationError("rapid-triage source seal path does not match")
    if package_ref.get("artifact_type") != package_seal.artifact_type:
        raise AssetValidationError("rapid-triage source artifact type does not match")
    if package_seal.artifact_type != "rapid_triage_package":
        raise AssetValidationError("rapid-triage source artifact has wrong type")
    if package_ref.get("sha256") != package_seal.sha256:
        raise AssetValidationError("rapid-triage source sha256 does not match seal")
    if package_ref.get("sealed_at") != package_seal.sealed_at.isoformat():
        raise AssetValidationError("rapid-triage source sealed_at does not match seal")
    package = _read_json_object(package_path, "rapid-triage source package")
    if package.get("symbol") != identity["symbol"]:
        raise AssetValidationError("rapid-triage source package symbol does not match")
    if package.get("information_cutoff") != front["information_cutoff"]:
        raise AssetValidationError(
            "rapid-triage source package information_cutoff does not match"
        )


def _read_report_front(report_path: Path) -> dict[str, Any]:
    try:
        text = report_path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise AssetValidationError(f"could not read report file: {report_path}") from exc
    match = REPORT_META_RE.match(text)
    if not match:
        raise AssetValidationError("report must start with trading-os-report-meta front metadata")
    try:
        front = json.loads(match.group("meta"))
    except json.JSONDecodeError as exc:
        raise AssetValidationError(f"invalid report front metadata JSON: {exc}") from exc
    if not isinstance(front, dict):
        raise AssetValidationError("report front metadata must be an object")
    return front


def _validate_report_file(
    company_dir: Path,
    report_path: Path,
    *,
    identity: Mapping[str, Any],
    record: Mapping[str, Any],
) -> None:
    try:
        text = report_path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise AssetValidationError(f"could not read report file: {report_path}") from exc
    match = REPORT_META_RE.match(text)
    if not match:
        raise AssetValidationError("report must start with trading-os-report-meta front metadata")
    try:
        front = json.loads(match.group("meta"))
    except json.JSONDecodeError as exc:
        raise AssetValidationError(f"invalid report front metadata JSON: {exc}") from exc
    if not isinstance(front, dict):
        raise AssetValidationError("report front metadata must be an object")
    _require_exact_keys(front, REPORT_FRONT_META_KEYS, "report front metadata")
    if front.get("schema_version") != 2:
        raise AssetValidationError("report front metadata schema_version must be 2")
    for key in ("report_id", "report_type", "as_of"):
        if front.get(key) != record.get(key):
            raise AssetValidationError(f"report front metadata {key} must match history")
    if front.get("symbol") != identity.get("symbol"):
        raise AssetValidationError("report front metadata symbol must match company identity")
    _parse_date(front.get("as_of"), "report front metadata as_of")
    _parse_datetime(
        front.get("information_cutoff"), "report front metadata information_cutoff"
    )
    price_snapshot_id = front.get("price_snapshot_id")
    if price_snapshot_id is not None and (
        not isinstance(price_snapshot_id, str) or not price_snapshot_id.strip()
    ):
        raise AssetValidationError("price_snapshot_id must be null or a non-empty string")
    _require_string(front, "agent_id", "report front metadata")
    _require_string(front, "source_manifest", "report front metadata")
    policy_versions = front.get("policy_versions")
    if not isinstance(policy_versions, dict) or not policy_versions:
        raise AssetValidationError("report policy_versions must be a non-empty object")
    for policy_id, version in policy_versions.items():
        if not isinstance(policy_id, str) or not policy_id.strip():
            raise AssetValidationError("report policy_versions keys must be non-empty strings")
        if not isinstance(version, str) or not version.strip():
            raise AssetValidationError("report policy_versions values must be non-empty strings")
    _require_string_array(front.get("predecessor_reports"), "predecessor_reports")
    sealed_artifacts = _require_string_array(
        front.get("sealed_artifacts"), "sealed_artifacts"
    )
    for artifact in sealed_artifacts:
        _safe_file(company_dir, artifact, "sealed artifact path")
    _safe_file(company_dir, str(front["source_manifest"]), "source_manifest path")

    body = text[match.end() :]
    first_non_empty = next((line.strip() for line in body.splitlines() if line.strip()), "")
    expected_title = f"# 公司研究：{identity['name']}（{identity['symbol']}）"
    if first_non_empty != expected_title:
        raise AssetValidationError(f"report title must be '{expected_title}'")
    headings = {
        line.removeprefix("## ").strip()
        for line in body.splitlines()
        if line.startswith("## ")
    }
    report_type = str(record["report_type"])
    missing = sorted(REPORT_SECTION_REQUIREMENTS[report_type] - headings)
    if missing:
        raise AssetValidationError(
            f"report is missing required section(s) for {report_type}: {missing}"
        )


def _validate_underwriting(underwriting: Mapping[str, Any]) -> None:
    _require_exact_keys(underwriting, UNDERWRITING_KEYS, "underwriting")
    status = underwriting.get("status")
    allowed_statuses = {item.value for item in UnderwritingStatus}
    if status is not None and status not in allowed_statuses:
        raise AssetValidationError(f"unsupported underwriting.status: {status}")
    review_id = underwriting.get("review_id")
    if review_id is not None and (
        not isinstance(review_id, str) or not review_id.strip()
    ):
        raise AssetValidationError("underwriting.review_id must be null or a string")
    if status is not None and review_id is None:
        raise AssetValidationError("underwriting.review_id is required when status is set")
    confidence = underwriting.get("confidence")
    if confidence is not None and confidence not in ALLOWED_CONFIDENCE:
        raise AssetValidationError(
            f"underwriting.confidence must be one of {sorted(ALLOWED_CONFIDENCE)}"
        )
    valid_until = underwriting.get("evidence_valid_until")
    if valid_until is not None:
        _parse_datetime(valid_until, "underwriting.evidence_valid_until")
    reasons = _require_string_array(
        underwriting.get("reason_codes"), "underwriting.reason_codes"
    )
    if len(reasons) != len(set(reasons)):
        raise AssetValidationError("underwriting.reason_codes must be unique")


def _validate_valuation(valuation: Mapping[str, Any]) -> None:
    _require_exact_keys(valuation, VALUATION_KEYS, "valuation")
    currency = valuation.get("currency")
    if currency is not None and (not isinstance(currency, str) or not currency.strip()):
        raise AssetValidationError("valuation.currency must be null or a string")
    price_as_of = valuation.get("price_as_of")
    if price_as_of is not None:
        _parse_datetime(price_as_of, "valuation.price_as_of")
    bear_value = valuation.get("bear_value")
    if bear_value is not None:
        _require_number(bear_value, "valuation.bear_value")
    for field in ("fair_value_range", "buy_zone", "reduce_zone"):
        _validate_nullable_range(valuation.get(field), field)
    has_value = bear_value is not None or any(
        valuation.get(field) is not None
        for field in ("fair_value_range", "buy_zone", "reduce_zone")
    )
    if has_value and currency is None:
        raise AssetValidationError("valuation.currency is required when values are present")


def _validate_triggers(raw_triggers: Any) -> None:
    if not isinstance(raw_triggers, list):
        raise AssetValidationError("triggers must be an array")
    seen: set[str] = set()
    for index, raw_trigger in enumerate(raw_triggers):
        if not isinstance(raw_trigger, dict):
            raise AssetValidationError(f"triggers[{index}] must be an object")
        trigger = raw_trigger
        _require_exact_keys(trigger, TRIGGER_KEYS, f"triggers[{index}]")
        trigger_id = _require_string(trigger, "trigger_id", f"triggers[{index}]")
        if trigger_id in seen:
            raise AssetValidationError(f"duplicate trigger_id: {trigger_id}")
        seen.add(trigger_id)
        trigger_type = _require_string(trigger, "type", f"triggers[{index}]")
        if trigger_type not in ALLOWED_TRIGGER_TYPES:
            raise AssetValidationError(f"unsupported trigger type: {trigger_type}")
        if not isinstance(trigger.get("condition"), dict):
            raise AssetValidationError(f"triggers[{index}].condition must be an object")
        _require_string(trigger, "reason", f"triggers[{index}]")
        if not isinstance(trigger.get("active"), bool):
            raise AssetValidationError(f"triggers[{index}].active must be boolean")


def _validate_nullable_range(value: Any, field: str) -> None:
    if value is None:
        return
    if not isinstance(value, list) or len(value) != 2:
        raise AssetValidationError(f"valuation.{field} must be null or a two-number range")
    lower = _require_number(value[0], f"valuation.{field}[0]")
    upper = _require_number(value[1], f"valuation.{field}[1]")
    if lower > upper:
        raise AssetValidationError(f"valuation.{field} lower bound must be <= upper bound")


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise AssetValidationError(f"invalid JSON in {path}: {exc}") from exc
    except OSError as exc:
        raise AssetValidationError(f"could not read {label}: {path}") from exc
    if not isinstance(data, dict):
        raise AssetValidationError(f"{label} must contain an object")
    return data


def _require_exact_keys(
    value: Mapping[str, Any],
    expected: set[str],
    label: str,
    *,
    unknown_label: str | None = None,
) -> None:
    keys = set(value)
    unknown = sorted(keys - expected)
    if unknown:
        prefix = unknown_label or f"unknown {label} fields"
        raise AssetValidationError(f"{prefix}: {unknown}")
    missing = sorted(expected - keys)
    if missing:
        raise AssetValidationError(f"missing {label} fields: {missing}")


def _require_object(
    value: Mapping[str, Any], key: str, label: str
) -> dict[str, Any]:
    result = value.get(key)
    if not isinstance(result, dict):
        raise AssetValidationError(f"{label}.{key} must be an object")
    return result


def _require_string(value: Mapping[str, Any], key: str, label: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result.strip():
        raise AssetValidationError(f"{label}.{key} must be a non-empty string")
    return result.strip()


def _require_string_array(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        raise AssetValidationError(f"{label} must be an array")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise AssetValidationError(f"{label} items must be non-empty strings")
        result.append(item.strip())
    return result


def _require_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AssetValidationError(f"{label} must be numeric")
    return float(value)


def _require_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise AssetValidationError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _parse_date(value: Any, label: str) -> dt.date:
    if not isinstance(value, str):
        raise AssetValidationError(f"{label} must be an ISO date")
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise AssetValidationError(f"{label} must be a real ISO date") from exc


def _parse_datetime(value: Any, label: str) -> dt.datetime:
    if not isinstance(value, str):
        raise AssetValidationError(f"{label} must be an ISO 8601 datetime")
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise AssetValidationError(f"{label} must be an ISO 8601 datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AssetValidationError(f"{label} must include a UTC offset")
    return parsed


def _safe_file(company_dir: Path, relative_path: str, label: str) -> Path:
    candidate_text = relative_path.replace("\\", "/")
    if (
        not candidate_text
        or candidate_text.startswith("/")
        or re.match(r"^[A-Za-z]:", candidate_text)
        or any(part in {"", ".", ".."} for part in candidate_text.split("/"))
    ):
        raise AssetValidationError(f"invalid {label}: {relative_path}")
    company_root = company_dir.resolve()
    candidate = (company_dir / candidate_text).resolve()
    try:
        candidate.relative_to(company_root)
    except ValueError as exc:
        raise AssetValidationError(f"invalid {label}: {relative_path}") from exc
    if not candidate.is_file():
        raise AssetValidationError(f"missing file for {label}: {relative_path}")
    return candidate


def _safe_repository_file(company_dir: Path, relative_path: str, label: str) -> Path:
    candidate_text = relative_path.replace("\\", "/")
    if (
        not candidate_text
        or candidate_text.startswith("/")
        or re.match(r"^[A-Za-z]:", candidate_text)
        or any(part in {"", ".", ".."} for part in candidate_text.split("/"))
    ):
        raise AssetValidationError(f"invalid {label}: {relative_path}")
    repository_root = company_dir.resolve().parents[3]
    candidate = (repository_root / candidate_text).resolve()
    try:
        candidate.relative_to(repository_root)
    except ValueError as exc:
        raise AssetValidationError(f"invalid {label}: {relative_path}") from exc
    if not candidate.is_file():
        raise AssetValidationError(f"missing file for {label}: {relative_path}")
    return candidate


def _require_matching_hash(path: Path, expected: str, label: str) -> None:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise AssetValidationError(
            f"{label} mismatch for {path}: expected {expected}, got {actual}"
        )


def _company_dirs(companies_root: Path) -> list[Path]:
    paths: list[Path] = []
    for market_dir in sorted(path for path in companies_root.iterdir() if path.is_dir()):
        for company_dir in sorted(path for path in market_dir.iterdir() if path.is_dir()):
            if (company_dir / "meta.json").is_file():
                paths.append(company_dir)
    return paths
