from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence
from urllib.parse import urlsplit

STATE_PATH = Path("coverage/cn-a/research_state.jsonl")
QUEUE_PATH = Path("coverage/cn-a/research_queue.jsonl")
STANDARDS_REGISTRY_PATH = Path("research/standards/registry.json")

_SYMBOL_RE = re.compile(r"^(?:CN:[0-9]{6}|HK:[0-9]{5}|US:[A-Z]{1,5}(?:[.-][A-Z])?)$")
MARKETS = {"cn-a": "CN", "hk": "HK", "us": "US"}
_STANDARD_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_SPEC_REVISION_RE = re.compile(r"^[a-f0-9]{40}$")
_DATED_MARKDOWN_RE = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})(?:-(?P<sequence>\d{2}))?\.md$")
_REPORT_PERIOD_RE = re.compile(r"^(?P<year>20\d{2})-(?P<period>FY|Q1|H1|Q3)$")
_FORMAL_REPORT_RE = re.compile(r"^(?P<year>20\d{2})-(?P<period>FY|Q1|H1|Q3)\.md$")
_REPORT_DEFERRAL_RE = re.compile(
    r"本次裁决不重复发明|完整业务分析可沿时间线回看|"
    r"(?:详见|参见|请回看).{0,20}(?:前序|上一版|历史|原)报告|"
    r"本报告不再重复.{0,20}(?:前序|上一版|历史|原)报告|"
    r"(?:前序|上一版|历史|原)报告.{0,30}(?:继续有效|共同部分)"
)
_REPORT_SECURITY_PRICE_LINE_RE = re.compile(
    r"关注价(?:格)?|买入价|重新武装|安全边际价格|价值区间下沿|"
    r"重新复核价|研究买入观察区|观察区|触发区|"
    r"price_levels|price_monitor|deep_review|rearm_above"
)
_REPORT_STITCHING_RE = re.compile(
    r"鉴于当前价值区间使用跨周期正常化经营而非单期利润直接年化|"
    r"(?:主要会计数据表|合并利润表主要数据).{0,30}可复核摘录如下"
)
# Only high-confidence delivery/process leaks are mechanical failures. Ordinary
# contrasts, customer/user analysis and model assumptions require editorial review.
_REPORT_PROCESS_LEAK_RE = re.compile(
    r"(?:按|按照|根据|回应|针对)(?:你|您)的(?:要求|建议|问题|反馈)|"
    r"你(?:提到|指出|希望我们)|(?:本次|本轮|上次|上轮)(?:的)?(?:对话|聊天)|"
    r"仓库统一的(?:三|五|十)年接口|协调器验收|research complete|"
    r"(?:任务ID|任务编号|task_id)\s*[:：=]",
    re.IGNORECASE,
)
_REPORT_INFORMATION_CUTOFF_RE = re.compile(
    r"信息截止(?:时间|时点|日)?\s*[：:=为]?\s*"
    r"(?P<year>20\d{2})[-年/](?P<month>\d{1,2})[-月/](?P<day>\d{1,2})日?"
)
_REPORT_ONE_SENTENCE_HEADING_RE = re.compile(
    r"^#{1,6}\s+(?:\d+(?:\.\d+)*[.、]?\s*)?一句话结论\s*$", re.MULTILINE
)
_REPORT_CORE_VALUE_RANGE_RE = re.compile(
    r"核心合理价值区间(?:为|是|\s|[：:])*"
    r"(?P<low>\d+(?:,\d{3})*(?:\.\d+)?)\s*"
    r"(?:—|–|-|至|~|～)\s*"
    r"(?P<high>\d+(?:,\d{3})*(?:\.\d+)?)"
)
_REPORT_PRIMARY_VALUATION_METHOD_RE = re.compile(
    r"主方法|核心方法|(?:PE|P/B|PB|DCF|现金流|分部估值|资产价值).{0,20}为核心|"
    r"以.{0,30}为核心"
)
_REPORT_METHOD_ONE_RE = re.compile(r"方法一")
_REPORT_METHOD_TWO_RE = re.compile(r"方法二")
_RETURN_MODEL_SCHEMA_VERSION = 1
_RETURN_MODEL_METHOD = "annual_common_equity_irr_v1"
_RETURN_MODEL_FIELDS = {
    "schema_version",
    "method",
    "currency",
    "model_as_of",
    "base_case_distributions_per_share",
    "base_case_terminal_equity_value_range_per_share",
}
_RETURN_MODEL_TERMINAL_HORIZONS = {"year_3", "year_5"}
_RETIRED_DYNAMIC_RETURN_FIELDS = frozenset(
    {
        "expected_annual_return",
        "expected_irr",
        "current_irr",
        "irr",
        "year_3_irr",
        "year_5_irr",
    }
)
_REFRESH_COMPARISON_FIELDS = ("前次假设", "本期实际", "判断变化", "估值影响")
_REQUIRED_REPORT_HEADINGS = {
    "一句话结论": re.compile(r"一句话结论"),
    "财务质量": re.compile(r"财务质量"),
    "估值": re.compile(r"估值|核心合理价值区间"),
    "基准持有人回报模型输入": re.compile(r"基准持有人回报模型输入"),
    "风险": re.compile(r"风险"),
    "来源": re.compile(r"来源"),
}
_THREAD_LOCKS: dict[str, threading.RLock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


def _has_refresh_comparison_table(report_markdown: str) -> bool:
    lines = report_markdown.splitlines()
    for index, line in enumerate(lines):
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if tuple(cells) != _REFRESH_COMPARISON_FIELDS:
            continue
        if index + 2 >= len(lines):
            return False
        separator = [cell.strip() for cell in lines[index + 1].strip().strip("|").split("|")]
        if len(separator) != len(_REFRESH_COMPARISON_FIELDS) or not all(
            re.fullmatch(r":?-{3,}:?", cell) for cell in separator
        ):
            return False
        values = [cell.strip() for cell in lines[index + 2].strip().strip("|").split("|")]
        return len(values) == len(_REFRESH_COMPARISON_FIELDS) and all(values)
    return False


class ResearchFlowError(RuntimeError):
    """Base error for the compact research workflow."""


class ValidationError(ResearchFlowError, ValueError):
    """Raised before an invalid workflow mutation is written."""


class StateCorruptionError(ResearchFlowError):
    """Raised when a persisted JSONL file is malformed or internally inconsistent."""


STATE_SCHEMA_VERSION = 6


class UniverseStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class CompanyStatus(str, Enum):
    UNSEEN = "unseen"
    IGNORE = "ignore"
    COVERED = "covered"


class ResearchOutcome(str, Enum):
    IGNORE = "ignore"
    COVERED = "covered"


class TaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"


PERIODIC_TRIGGER = "periodic"
MANUAL_REWRITE_TRIGGER = "manual_rewrite"


@dataclass(frozen=True)
class CompanyRef:
    symbol: str
    name: str | None = None


@dataclass(frozen=True)
class ValueRange:
    low: float
    high: float
    currency: str = "CNY"


@dataclass(frozen=True)
class ReturnModel:
    schema_version: int
    method: str
    currency: str
    model_as_of: str
    base_case_distributions_per_share: Sequence[float]
    base_case_terminal_equity_value_range_per_share: Mapping[str, Mapping[str, float]]


@dataclass(frozen=True)
class ResearchResult:
    symbol: str
    outcome: ResearchOutcome | str
    summary: str
    key_logic: Sequence[str]
    risks: Sequence[str]
    value_range: ValueRange | None
    source_urls: Sequence[str]
    information_cutoff: str
    report_period: str
    name: str | None = None
    report_markdown: str | None = None
    valuation_note: str | None = None
    return_model: ReturnModel | None = None
    return_model_note: str | None = None
    financial_basis: Mapping[str, str] | None = None
    security_basis: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class ResearchTask:
    task_id: str
    symbol: str
    trigger_kind: str
    trigger_id: str
    reason: str
    enqueued_at: str
    status: TaskStatus
    report_period: str
    name: str | None = None
    started_at: str | None = None
    financial_basis: Mapping[str, str] | None = None

    @property
    def trigger_key(self) -> str:
        return f"{self.trigger_kind}:{self.report_period}:{self.trigger_id}"


@dataclass(frozen=True)
class ResearchRequest:
    symbol: str
    reason: str
    name: str | None = None
    financial_basis: Mapping[str, str] | None = None


@dataclass(frozen=True)
class ResearchBatchUpdate:
    total: int
    enqueued_tasks: tuple[ResearchTask, ...]
    deduplicated: int


@dataclass(frozen=True)
class UniverseSyncUpdate:
    total: int
    added: int
    reactivated: int
    inactivated: int
    renamed: int


@dataclass(frozen=True)
class ResearchFlowStatus:
    companies: int
    active: int
    inactive: int
    unseen: int
    ignored: int
    covered: int
    queued: int
    running: int


def _thread_lock(path: Path) -> threading.RLock:
    key = str(path.resolve())
    with _THREAD_LOCKS_GUARD:
        return _THREAD_LOCKS.setdefault(key, threading.RLock())


@contextmanager
def _exclusive_lock(path: Path) -> Iterator[None]:
    """Serialize writers in this process and across local coordinator processes."""

    path.parent.mkdir(parents=True, exist_ok=True)
    local_lock = _thread_lock(path)
    with local_lock:
        handle = path.open("a+b")
        acquired = False
        try:
            if os.name == "nt":
                import msvcrt

                handle.seek(0, os.SEEK_END)
                if handle.tell() == 0:
                    handle.write(b"\0")
                    handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            acquired = True
            yield
        finally:
            try:
                if acquired:
                    handle.seek(0)
                    if os.name == "nt":
                        import msvcrt

                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()


def _replace_file(source: Path, target: Path) -> None:
    """Keep atomic replacement while tolerating brief Windows reader locks."""
    for attempt in range(7):
        try:
            os.replace(source, target)
            return
        except PermissionError as error:
            if getattr(error, "winerror", None) not in {5, 32, 33} or attempt == 6:
                raise
            time.sleep(0.025 * (2**attempt))


def _atomic_write_jsonl(path: Path, records: Iterable[Mapping[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for record in records
    ]
    content = (("\n".join(lines) + "\n") if lines else "").encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        _replace_file(temporary_path, path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    return path


def _atomic_write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        _replace_file(temporary_path, path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    return path


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw_line.strip():
            continue
        try:
            item = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise StateCorruptionError(f"{path}:{line_number}: invalid JSON: {exc.msg}") from exc
        if not isinstance(item, dict):
            raise StateCorruptionError(f"{path}:{line_number}: each JSONL row must be an object")
        records.append(item)
    return records


def _standards_registry(root: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    path = root / STANDARDS_REGISTRY_PATH
    try:
        registry = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError("research standards registry is missing") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError("research standards registry is not valid JSON") from exc
    if not isinstance(registry, dict) or registry.get("schema_version") != 1:
        raise ValidationError("unsupported research standards registry schema")
    raw_standards = registry.get("standards")
    if not isinstance(raw_standards, list) or not raw_standards:
        raise ValidationError("research standards registry has no standards")
    standards: dict[str, dict[str, Any]] = {}
    for item in raw_standards:
        if not isinstance(item, dict):
            raise ValidationError("research standard must be an object")
        standard_id = item.get("id")
        if (
            not isinstance(standard_id, str)
            or not _STANDARD_ID_RE.fullmatch(standard_id)
            or standard_id in standards
        ):
            raise ValidationError("research standard ID is missing, invalid, or duplicated")
        if item.get("status") not in {"draft", "released", "retired"}:
            raise ValidationError(f"research standard has invalid status: {standard_id}")
        if not _SPEC_REVISION_RE.fullmatch(str(item.get("spec_revision", ""))):
            raise ValidationError(
                f"research standard must bind a full spec revision: {standard_id}"
            )
        standards[standard_id] = item
    active = standards.get(registry.get("active_standard"))
    if active is None or active.get("status") != "released":
        raise ValidationError("active research standard must be released")
    return active, standards


def _enum_value(value: Enum | str, enum_type: type[Enum], label: str) -> str:
    raw = value.value if isinstance(value, Enum) else value
    try:
        return str(enum_type(raw).value)
    except (TypeError, ValueError) as exc:
        allowed = ", ".join(item.value for item in enum_type)
        raise ValidationError(f"{label} must be one of: {allowed}") from exc


def _symbol(value: str) -> str:
    normalized = str(value).strip().upper()
    if not _SYMBOL_RE.fullmatch(normalized):
        raise ValidationError("symbol must use CN:000000, HK:00000, or US:TICKER")
    return normalized


def _nonblank(value: str, label: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValidationError(f"{label} must not be blank")
    return normalized


def _optional_name(value: str | None) -> str | None:
    if value is None:
        return None
    return _nonblank(value, "name")


def _number(value: float | int, label: str) -> float:
    if isinstance(value, bool):
        raise ValidationError(f"{label} must be a finite non-negative number")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError(f"{label} must be a finite non-negative number") from exc
    if not math.isfinite(result) or result < 0:
        raise ValidationError(f"{label} must be a finite non-negative number")
    return result


def _strings(values: Sequence[str], label: str) -> list[str]:
    if isinstance(values, (str, bytes)):
        raise ValidationError(f"{label} must be a sequence of strings")
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _nonblank(value, label)
        if normalized not in seen:
            seen.add(normalized)
            output.append(normalized)
    return output


def _urls(values: Sequence[str]) -> list[str]:
    output = _strings(values, "source URL")
    for value in output:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValidationError(f"source URL must be an absolute http(s) URL: {value}")
    return output


def _timestamp(value: str | datetime | None) -> str:
    if value is None:
        parsed = datetime.now(timezone.utc)
    elif isinstance(value, datetime):
        parsed = value
    else:
        raw = _nonblank(value, "timestamp")
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValidationError(f"invalid ISO timestamp: {value}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValidationError("timestamp must include a timezone")
    return parsed.isoformat()


def _financial_basis(value: object, *, cutoff: str | None = None) -> dict[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping) or set(value) != {"period_end", "published_on", "source_url"}:
        raise ValidationError("financial_basis requires period_end, published_on, source_url")
    for key in ("period_end", "published_on"):
        try:
            if date.fromisoformat(value[key]).isoformat() != value[key]:
                raise ValueError()
        except (TypeError, ValueError):
            raise ValidationError(f"invalid financial_basis.{key}") from None
    if value["period_end"] > value["published_on"]:
        raise ValidationError("financial period ends after publication")
    if cutoff and value["published_on"] > cutoff[:10]:
        raise ValidationError("financial disclosure is not yet published at cutoff")
    _urls([value["source_url"]])
    return dict(value)


def _security_basis(value: object, symbol: str) -> dict[str, Any] | None:
    if value is None:
        if not symbol.startswith("CN:"):
            raise ValidationError("foreign research requires security_basis")
        return None
    if not isinstance(value, Mapping) or set(value) != {
        "currency",
        "unit",
        "ordinary_shares_per_unit",
        "source_url",
    }:
        raise ValidationError("security_basis fields are incomplete")
    currency = {"CN": "CNY", "HK": "HKD", "US": "USD"}[symbol[:2]]
    if value["currency"] != currency:
        raise ValidationError("security_basis currency must match the listed security")
    if value["unit"] not in {"ordinary_share", "ADS", "share_class"}:
        raise ValidationError("unknown listed security unit")
    ratio = _return_model_number(value["ordinary_shares_per_unit"], "ordinary_shares_per_unit")
    if ratio <= 0:
        raise ValidationError("ordinary_shares_per_unit must be positive")
    _urls([value["source_url"]])
    return dict(value)


def _report_period(value: object, *, information_cutoff: str | None = None) -> str:
    """Normalize a financial reporting period such as ``2026-H1``.

    The period names the latest periodic financial basis of a full report. A
    rewrite within the same period replaces that period's file; the factual
    cutoff remains a separate timestamp in the report and state.
    """

    normalized = _nonblank(value, "report_period") if isinstance(value, str) else ""
    match = _REPORT_PERIOD_RE.fullmatch(normalized)
    if match is None:
        raise ValidationError("report_period must be YYYY-FY, YYYY-Q1, YYYY-H1, or YYYY-Q3")
    if information_cutoff is not None:
        year = int(match.group("year"))
        month_day = {"Q1": (3, 31), "H1": (6, 30), "Q3": (9, 30), "FY": (12, 31)}[
            match.group("period")
        ]
        cutoff = datetime.fromisoformat(information_cutoff)
        period_end = datetime(year, *month_day, tzinfo=cutoff.tzinfo)
        if period_end > cutoff:
            raise ValidationError("report_period ends after information_cutoff")
    return normalized


def _report_period_key(value: str) -> tuple[int, int]:
    match = _REPORT_PERIOD_RE.fullmatch(value)
    if match is None:
        raise ValidationError(f"invalid report period: {value}")
    order = {"Q1": 1, "H1": 2, "Q3": 3, "FY": 4}
    return int(match.group("year")), order[match.group("period")]


def _value_range(value: ValueRange | None) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, ValueRange):
        raise ValidationError("value_range must be a ValueRange or None")
    low = _number(value.low, "value_range.low")
    high = _number(value.high, "value_range.high")
    if low > high:
        raise ValidationError("value_range.low must not exceed value_range.high")
    return {"low": low, "high": high, "currency": _nonblank(value.currency, "currency")}


def _return_model_number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{label} must be a finite non-negative number")
    return _number(value, label)


def _return_model_text(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{label} must be a non-empty string")
    return _nonblank(value, label)


def _return_model_range(value: object, label: str) -> dict[str, float]:
    if not isinstance(value, Mapping) or set(value) != {"low", "high"}:
        raise ValidationError(f"{label} must contain exactly low and high")
    low = _return_model_number(value["low"], f"{label}.low")
    high = _return_model_number(value["high"], f"{label}.high")
    if low > high:
        raise ValidationError(f"{label}.low must not exceed {label}.high")
    return {"low": low, "high": high}


def _normalized_return_model_payload(
    value: Mapping[str, Any],
    *,
    information_cutoff: str,
    value_range: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if set(value) != _RETURN_MODEL_FIELDS:
        raise ValidationError("return_model fields do not match the version 1 contract")
    schema_version = value["schema_version"]
    if (
        isinstance(schema_version, bool)
        or not isinstance(schema_version, int)
        or schema_version != _RETURN_MODEL_SCHEMA_VERSION
    ):
        raise ValidationError("return_model.schema_version must be 1")
    method = _return_model_text(value["method"], "return_model.method")
    if method != _RETURN_MODEL_METHOD:
        raise ValidationError(f"return_model.method must be {_RETURN_MODEL_METHOD}")
    currency = _return_model_text(value["currency"], "return_model.currency")
    if currency not in {"CNY", "HKD", "USD"}:
        raise ValidationError("return_model.currency must be CNY, HKD or USD")
    if value_range is not None and currency != value_range.get("currency"):
        raise ValidationError("return_model.currency must match value_range.currency")
    model_as_of = _timestamp(_return_model_text(value["model_as_of"], "return_model.model_as_of"))
    if model_as_of != information_cutoff:
        raise ValidationError("return_model.model_as_of must match information_cutoff")

    raw_distributions = value["base_case_distributions_per_share"]
    if (
        isinstance(raw_distributions, (str, bytes))
        or not isinstance(raw_distributions, Sequence)
        or len(raw_distributions) != 5
    ):
        raise ValidationError(
            "return_model.base_case_distributions_per_share must contain exactly 5 values"
        )
    distributions = [
        _return_model_number(
            item,
            f"return_model.base_case_distributions_per_share[{index}]",
        )
        for index, item in enumerate(raw_distributions)
    ]

    raw_terminal = value["base_case_terminal_equity_value_range_per_share"]
    if not isinstance(raw_terminal, Mapping):
        raise ValidationError(
            "return_model.base_case_terminal_equity_value_range_per_share must be an object"
        )
    horizons = set(raw_terminal)
    if "year_5" not in horizons or not horizons.issubset(_RETURN_MODEL_TERMINAL_HORIZONS):
        raise ValidationError(
            "return_model terminal ranges require year_5 and may only include year_3"
        )
    terminal: dict[str, dict[str, float]] = {}
    if "year_3" in raw_terminal:
        terminal["year_3"] = _return_model_range(
            raw_terminal["year_3"],
            "return_model.base_case_terminal_equity_value_range_per_share.year_3",
        )
        if sum(distributions[:3]) + terminal["year_3"]["high"] <= 0:
            raise ValidationError("return_model year_3 total future payoff must be positive")
    terminal["year_5"] = _return_model_range(
        raw_terminal["year_5"],
        "return_model.base_case_terminal_equity_value_range_per_share.year_5",
    )
    if sum(distributions) + terminal["year_5"]["high"] <= 0:
        raise ValidationError("return_model year_5 total future payoff must be positive")

    return {
        "schema_version": _RETURN_MODEL_SCHEMA_VERSION,
        "method": method,
        "currency": currency,
        "model_as_of": model_as_of,
        "base_case_distributions_per_share": distributions,
        "base_case_terminal_equity_value_range_per_share": terminal,
    }


def _return_model(
    value: ReturnModel | None,
    *,
    information_cutoff: str,
    value_range: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, ReturnModel):
        raise ValidationError("return_model must be a ReturnModel or None")
    return _normalized_return_model_payload(
        {
            "schema_version": value.schema_version,
            "method": value.method,
            "currency": value.currency,
            "model_as_of": value.model_as_of,
            "base_case_distributions_per_share": value.base_case_distributions_per_share,
            "base_case_terminal_equity_value_range_per_share": (
                value.base_case_terminal_equity_value_range_per_share
            ),
        },
        information_cutoff=information_cutoff,
        value_range=value_range,
    )


def _stored_return_model(
    value: object,
    *,
    information_cutoff: str,
    value_range: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError("persisted return_model must be an object")
    return _normalized_return_model_payload(
        value,
        information_cutoff=information_cutoff,
        value_range=value_range,
    )


def _task_id(symbol: str, trigger_key: str) -> str:
    digest = hashlib.sha256(f"{symbol}\0{trigger_key}".encode()).hexdigest()
    return digest[:24]


def _empty_state(symbol: str, name: str | None, at: str) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "symbol": symbol,
        "name": name,
        "universe_status": UniverseStatus.ACTIVE.value,
        "status": CompanyStatus.UNSEEN.value,
        "updated_at": at,
        "summary": None,
        "key_logic": [],
        "risks": [],
        "value_range": None,
        "source_urls": [],
        "last_research_at": None,
        "information_cutoff": None,
        "report_period": None,
        "basis_report_path": None,
        "valuation_note": None,
        "return_model": None,
        "return_model_note": None,
        "standard_id": None,
        "spec_revision": None,
        "accepted_at": None,
    }


def _task_from_row(row: Mapping[str, Any]) -> ResearchTask:
    try:
        task = ResearchTask(
            task_id=_nonblank(row["task_id"], "task_id"),
            symbol=_symbol(row["symbol"]),
            trigger_kind=_nonblank(row["trigger_kind"], "trigger_kind"),
            trigger_id=_nonblank(row["trigger_id"], "trigger_id"),
            reason=_nonblank(row["reason"], "reason"),
            enqueued_at=_timestamp(row["enqueued_at"]),
            status=TaskStatus(_enum_value(row["status"], TaskStatus, "task status")),
            report_period=_report_period(row["report_period"]),
            name=_optional_name(row.get("name")),
            started_at=(_timestamp(row["started_at"]) if row.get("started_at") else None),
            financial_basis=_financial_basis(row.get("financial_basis"), cutoff=row["enqueued_at"]),
        )
    except KeyError as exc:
        raise StateCorruptionError(f"queue row is missing {exc.args[0]}") from exc
    if task.trigger_kind not in {PERIODIC_TRIGGER, MANUAL_REWRITE_TRIGGER}:
        raise StateCorruptionError(f"unsupported research trigger: {task.trigger_kind}")
    return task


def _task_row(task: ResearchTask) -> dict[str, Any]:
    row = {
        "schema_version": STATE_SCHEMA_VERSION,
        "task_id": task.task_id,
        "symbol": task.symbol,
        "name": task.name,
        "trigger_kind": task.trigger_kind,
        "trigger_id": task.trigger_id,
        "reason": task.reason,
        "enqueued_at": task.enqueued_at,
        "status": task.status.value,
        "report_period": task.report_period,
        "started_at": task.started_at,
        **({"financial_basis": task.financial_basis} if task.financial_basis else {}),
    }
    return row


class ResearchFlow:
    """Small, single-writer coordinator for screening and company research.

    Worker agents receive :class:`ResearchTask` objects and return one
    :class:`ResearchResult`. They do not need to mutate any shared file. The
    caller decides how many tasks to dispatch concurrently.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        state_path: str | Path | None = None,
        queue_path: str | Path | None = None,
        market: str = "cn-a",
    ) -> None:
        if market not in MARKETS:
            raise ValidationError("unknown research market")
        self.market = market
        self.root = Path(root)
        self.state_path = self._resolve(state_path or f"coverage/{market}/research_state.jsonl")
        self.queue_path = self._resolve(queue_path or f"coverage/{market}/research_queue.jsonl")
        self.lock_path = self.state_path.with_suffix(self.state_path.suffix + ".lock")

    def _market_symbol(self, value: str) -> str:
        symbol = _symbol(value)
        if symbol.split(":")[0] != MARKETS[self.market]:
            raise ValidationError("security belongs to another research market")
        return symbol

    def _resolve(self, value: str | Path) -> Path:
        path = Path(value)
        return path if path.is_absolute() else self.root / path

    def _states(self) -> dict[str, dict[str, Any]]:
        rows = _read_jsonl(self.state_path)
        states: dict[str, dict[str, Any]] = {}
        for row in rows:
            try:
                symbol = self._market_symbol(row["symbol"])
                _enum_value(row["universe_status"], UniverseStatus, "universe status")
                _enum_value(row["status"], CompanyStatus, "company status")
            except KeyError as exc:
                raise StateCorruptionError(f"state row is missing {exc.args[0]}") from exc
            if symbol in states:
                raise StateCorruptionError(f"duplicate state row for {symbol}")
            states[symbol] = dict(row)
        return states

    def _tasks(self) -> list[ResearchTask]:
        tasks = [_task_from_row(row) for row in _read_jsonl(self.queue_path)]
        seen: set[str] = set()
        for task in tasks:
            self._market_symbol(task.symbol)
            if self.market != "cn-a" and task.financial_basis is None:
                raise StateCorruptionError("foreign task is missing financial_basis")
            expected_id = _task_id(task.symbol, task.trigger_key)
            if task.task_id != expected_id:
                raise StateCorruptionError(
                    f"task ID does not match symbol and trigger: {task.task_id}"
                )
            if task.task_id in seen:
                raise StateCorruptionError(f"duplicate queue task: {task.task_id}")
            seen.add(task.task_id)
        return tasks

    def _write_tasks(self, tasks: Sequence[ResearchTask]) -> None:
        ordered = sorted(tasks, key=lambda task: (task.enqueued_at, task.task_id))
        _atomic_write_jsonl(self.queue_path, (_task_row(task) for task in ordered))

    def _write_states(self, states: Mapping[str, Mapping[str, Any]]) -> None:
        _atomic_write_jsonl(self.state_path, (states[symbol] for symbol in sorted(states)))

    @staticmethod
    def _enqueue(
        tasks: list[ResearchTask],
        *,
        symbol: str,
        name: str | None,
        trigger_kind: str,
        trigger_id: str,
        report_period: str,
        reason: str,
        at: str,
        financial_basis: Mapping[str, str] | None = None,
    ) -> ResearchTask | None:
        kind = _nonblank(trigger_kind, "trigger_kind")
        if kind not in {PERIODIC_TRIGGER, MANUAL_REWRITE_TRIGGER}:
            raise ValidationError(f"unsupported research trigger: {kind}")
        identifier = _nonblank(trigger_id, "trigger_id")
        period = _report_period(report_period)
        trigger_key = f"{kind}:{period}:{identifier}"
        identifier_hash = _task_id(symbol, trigger_key)
        if any(task.task_id == identifier_hash for task in tasks) or any(
            task.symbol == symbol for task in tasks
        ):
            return None
        task = ResearchTask(
            task_id=identifier_hash,
            symbol=symbol,
            name=name,
            trigger_kind=kind,
            trigger_id=identifier,
            reason=_nonblank(reason, "reason"),
            enqueued_at=at,
            status=TaskStatus.QUEUED,
            report_period=period,
            financial_basis=financial_basis,
        )
        tasks.append(task)
        return task

    def register_universe(
        self, companies: Iterable[CompanyRef], *, at: str | datetime | None = None
    ) -> int:
        """Add previously unseen companies without changing existing decisions."""

        timestamp = _timestamp(at)
        normalized: list[tuple[str, str | None]] = []
        seen: set[str] = set()
        for company in companies:
            symbol = self._market_symbol(company.symbol)
            if symbol in seen:
                raise ValidationError(f"duplicate company in input: {symbol}")
            seen.add(symbol)
            normalized.append((symbol, _optional_name(company.name)))
        with _exclusive_lock(self.lock_path):
            states = self._states()
            added = 0
            for symbol, name in normalized:
                if symbol not in states:
                    states[symbol] = _empty_state(symbol, name, timestamp)
                    added += 1
                elif name and not states[symbol].get("name"):
                    states[symbol]["name"] = name
                    states[symbol]["updated_at"] = timestamp
            self._write_states(states)
        return added

    def sync_universe(
        self, companies: Iterable[CompanyRef], *, at: str | datetime | None = None
    ) -> UniverseSyncUpdate:
        """Synchronize a complete active-security snapshot without losing research history."""

        timestamp = _timestamp(at)
        snapshot: dict[str, str | None] = {}
        for company in companies:
            symbol = self._market_symbol(company.symbol)
            if symbol in snapshot:
                raise ValidationError(f"duplicate company in input: {symbol}")
            snapshot[symbol] = _optional_name(company.name)

        with _exclusive_lock(self.lock_path):
            states = self._states()
            tasks = self._tasks()
            added = 0
            reactivated = 0
            inactivated = 0
            renamed = 0

            for symbol, state in states.items():
                if (
                    symbol not in snapshot
                    and state.get("universe_status") == UniverseStatus.ACTIVE.value
                ):
                    state["universe_status"] = UniverseStatus.INACTIVE.value
                    state["updated_at"] = timestamp
                    tasks = [task for task in tasks if task.symbol != symbol]
                    inactivated += 1

            for symbol, name in snapshot.items():
                state = states.get(symbol)
                if state is None:
                    states[symbol] = _empty_state(symbol, name, timestamp)
                    added += 1
                    continue
                changed = False
                if name and name != state.get("name"):
                    state["name"] = name
                    renamed += 1
                    changed = True
                if state.get("universe_status") == UniverseStatus.INACTIVE.value:
                    state["universe_status"] = UniverseStatus.ACTIVE.value
                    reactivated += 1
                    changed = True
                if changed:
                    state["updated_at"] = timestamp

            self._write_tasks(tasks)
            self._write_states(states)
        return UniverseSyncUpdate(
            total=len(snapshot),
            added=added,
            reactivated=reactivated,
            inactivated=inactivated,
            renamed=renamed,
        )

    def enqueue_research(
        self,
        requests: Iterable[ResearchRequest],
        *,
        report_period: str,
        trigger_kind: str,
        batch_id: str | None = None,
        at: str | datetime | None = None,
    ) -> ResearchBatchUpdate:
        """Queue one financial-period study or an explicit same-period rewrite."""

        timestamp = _timestamp(at)
        period = _report_period(report_period)
        kind = _nonblank(trigger_kind, "trigger_kind")
        if kind not in {PERIODIC_TRIGGER, MANUAL_REWRITE_TRIGGER}:
            raise ValidationError(f"unsupported research trigger: {kind}")
        identifier = period if kind == PERIODIC_TRIGGER else _nonblank(batch_id, "batch_id")
        normalized: list[dict[str, Any]] = []
        seen: set[str] = set()
        for request in requests:
            symbol = self._market_symbol(request.symbol)
            if symbol in seen:
                raise ValidationError(f"duplicate research request for {symbol}")
            seen.add(symbol)
            normalized.append(
                {
                    "symbol": symbol,
                    "name": _optional_name(request.name),
                    "reason": _nonblank(request.reason, "reason"),
                    "financial_basis": _financial_basis(request.financial_basis, cutoff=timestamp),
                }
            )

        with (
            _exclusive_lock(self.root / "coverage/.research-schedule.lock"),
            _exclusive_lock(self.lock_path),
        ):
            states = self._states()
            tasks = self._tasks()
            issuers = {}
            for market in MARKETS:
                pool_path = self.root / f"screening/{market}/value-quality/pool.json"
                if pool_path.exists():
                    for company in json.loads(pool_path.read_text(encoding="utf-8"))["companies"]:
                        issuers[company["symbol"]] = company.get("issuer", company["symbol"])
            other_issuers = set()
            for market in MARKETS:
                if market != self.market:
                    for row in _read_jsonl(self.root / f"coverage/{market}/research_queue.jsonl"):
                        other_issuers.add(issuers.get(row["symbol"], row["symbol"]))
            for item in normalized:
                if issuers.get(item["symbol"], item["symbol"]) in other_issuers:
                    raise ValidationError("issuer already has an active task in another market")
                if self.market != "cn-a" and not item["financial_basis"]:
                    if kind == MANUAL_REWRITE_TRIGGER:
                        item["financial_basis"] = (states.get(item["symbol"]) or {}).get(
                            "financial_basis"
                        )
                    if not item["financial_basis"]:
                        raise ValidationError(
                            "foreign scheduling requires published financial_basis"
                        )
            invalid: list[str] = []
            conflicts: list[str] = []
            for item in normalized:
                state = states.get(item["symbol"])
                if state is None or state.get("universe_status") != UniverseStatus.ACTIVE.value:
                    invalid.append(item["symbol"])
                    continue
                target = self._report_path(item["symbol"], period)
                if kind == PERIODIC_TRIGGER and target.exists():
                    continue
                if kind == MANUAL_REWRITE_TRIGGER and not target.exists():
                    invalid.append(item["symbol"])
                    continue
                if any(task.symbol == item["symbol"] for task in tasks):
                    conflicts.append(item["symbol"])
            if invalid:
                raise ValidationError(
                    "research request is inactive or has no matching period slot: "
                    + ", ".join(invalid)
                )
            if conflicts:
                raise ValidationError(
                    "research company already has an active task: " + ", ".join(conflicts)
                )

            enqueued: list[ResearchTask] = []
            deduplicated = 0
            for item in normalized:
                target = self._report_path(item["symbol"], period)
                if kind == PERIODIC_TRIGGER and target.exists():
                    deduplicated += 1
                    continue
                state = states[item["symbol"]]
                task = self._enqueue(
                    tasks,
                    symbol=item["symbol"],
                    name=item["name"] or state.get("name"),
                    trigger_kind=kind,
                    trigger_id=identifier,
                    report_period=period,
                    reason=item["reason"],
                    at=timestamp,
                    financial_basis=item["financial_basis"],
                )
                if task is None:
                    deduplicated += 1
                else:
                    enqueued.append(task)
            if enqueued:
                self._write_tasks(tasks)

        return ResearchBatchUpdate(
            total=len(normalized),
            enqueued_tasks=tuple(enqueued),
            deduplicated=deduplicated,
        )

    def list_tasks(self, *, status: TaskStatus | str | None = None) -> tuple[ResearchTask, ...]:
        wanted = None if status is None else _enum_value(status, TaskStatus, "task status")
        with _exclusive_lock(self.lock_path):
            tasks = self._tasks()
        return tuple(task for task in tasks if wanted is None or task.status.value == wanted)

    def dispatch_tasks(
        self,
        *,
        limit: int,
        at: str | datetime | None = None,
        from_end: bool = False,
        trigger_kind: str | None = None,
    ) -> tuple[ResearchTask, ...]:
        """Dispatch at most ``limit`` companies; the caller owns the concurrency policy."""

        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise ValidationError("limit must be a positive integer")
        timestamp = _timestamp(at)
        wanted_trigger = (
            _nonblank(trigger_kind, "trigger_kind") if trigger_kind is not None else None
        )
        with _exclusive_lock(self.lock_path):
            tasks = self._tasks()
            active_symbols = {task.symbol for task in tasks if task.status is TaskStatus.RUNNING}
            selected_ids: set[str] = set()
            candidates = reversed(tasks) if from_end else iter(tasks)
            for task in candidates:
                if len(selected_ids) >= limit:
                    break
                if (
                    task.status is not TaskStatus.QUEUED
                    or task.symbol in active_symbols
                    or (wanted_trigger is not None and task.trigger_kind != wanted_trigger)
                ):
                    continue
                selected_ids.add(task.task_id)
                active_symbols.add(task.symbol)
            updated: list[ResearchTask] = []
            running: list[ResearchTask] = []
            for task in tasks:
                if task.task_id in selected_ids:
                    task = ResearchTask(
                        task_id=task.task_id,
                        symbol=task.symbol,
                        name=task.name,
                        trigger_kind=task.trigger_kind,
                        trigger_id=task.trigger_id,
                        reason=task.reason,
                        enqueued_at=task.enqueued_at,
                        status=TaskStatus.RUNNING,
                        report_period=task.report_period,
                        financial_basis=task.financial_basis,
                        started_at=timestamp,
                    )
                    running.append(task)
                updated.append(task)
            if running:
                self._write_tasks(updated)
        return tuple(running)

    def requeue_task(self, task_id: str) -> ResearchTask:
        """Explicitly return an interrupted running task to the queue."""

        wanted = _nonblank(task_id, "task_id")
        with _exclusive_lock(self.lock_path):
            tasks = self._tasks()
            current = next((task for task in tasks if task.task_id == wanted), None)
            if current is None:
                raise ValidationError(f"task is not current: {wanted}")
            if current.status is TaskStatus.QUEUED:
                return current
            restored = ResearchTask(
                task_id=current.task_id,
                symbol=current.symbol,
                name=current.name,
                trigger_kind=current.trigger_kind,
                trigger_id=current.trigger_id,
                reason=current.reason,
                enqueued_at=current.enqueued_at,
                status=TaskStatus.QUEUED,
                report_period=current.report_period,
                financial_basis=current.financial_basis,
                started_at=None,
            )
            self._write_tasks([restored if task.task_id == wanted else task for task in tasks])
            return restored

    def start_task(
        self,
        task_id: str,
        *,
        at: str | datetime | None = None,
    ) -> ResearchTask:
        """Atomically claim one exact queued task without consuming its neighbors."""

        wanted = _nonblank(task_id, "task_id")
        timestamp = _timestamp(at)
        with _exclusive_lock(self.lock_path):
            tasks = self._tasks()
            current = next((task for task in tasks if task.task_id == wanted), None)
            if current is None:
                raise ValidationError(f"task is not current: {wanted}")
            if current.status is TaskStatus.RUNNING:
                return current
            if any(
                task.symbol == current.symbol
                and task.status is TaskStatus.RUNNING
                and task.task_id != current.task_id
                for task in tasks
            ):
                raise ValidationError(f"company already has a running task: {current.symbol}")
            started = ResearchTask(
                task_id=current.task_id,
                symbol=current.symbol,
                name=current.name,
                trigger_kind=current.trigger_kind,
                trigger_id=current.trigger_id,
                reason=current.reason,
                enqueued_at=current.enqueued_at,
                status=TaskStatus.RUNNING,
                report_period=current.report_period,
                financial_basis=current.financial_basis,
                started_at=timestamp,
            )
            self._write_tasks([started if task.task_id == wanted else task for task in tasks])
            return started

    @staticmethod
    def _normalized_result(result: ResearchResult) -> dict[str, Any]:
        symbol = _symbol(result.symbol)
        outcome = _enum_value(result.outcome, ResearchOutcome, "research outcome")
        summary = _nonblank(result.summary, "summary")
        key_logic = _strings(result.key_logic, "key logic")
        risks = _strings(result.risks, "risk")
        value_range = _value_range(result.value_range)
        source_urls = _urls(result.source_urls)
        information_cutoff = _timestamp(result.information_cutoff)
        financial_basis = _financial_basis(result.financial_basis, cutoff=information_cutoff)
        security_basis = _security_basis(result.security_basis, symbol)
        if not symbol.startswith("CN:") and not financial_basis:
            raise ValidationError("foreign result requires financial_basis")
        expected_currency = {"CN": "CNY", "HK": "HKD", "US": "USD"}[symbol[:2]]
        if value_range and value_range["currency"] != expected_currency:
            raise ValidationError("value_range currency must match listed security")
        if result.return_model and result.return_model.currency != expected_currency:
            raise ValidationError("return_model currency must match listed security")
        report_period = _report_period(
            result.report_period,
            information_cutoff=information_cutoff if symbol.startswith("CN:") else None,
        )
        valuation_note = (
            _nonblank(result.valuation_note, "valuation_note")
            if result.valuation_note is not None
            else None
        )
        return_model = _return_model(
            result.return_model,
            information_cutoff=information_cutoff,
            value_range=value_range,
        )
        return_model_note = (
            _return_model_text(result.return_model_note, "return_model_note")
            if result.return_model_note is not None
            else None
        )
        report_markdown = (
            _nonblank(result.report_markdown, "report_markdown")
            if result.report_markdown is not None
            else None
        )
        if not key_logic:
            raise ValidationError("research result requires at least one key logic item")
        if not risks:
            raise ValidationError("research result requires at least one risk")
        if not source_urls:
            raise ValidationError("research result requires at least one source URL")
        if report_markdown is None:
            raise ValidationError("research result requires report_markdown")
        if not symbol.startswith("CN:"):
            for label, key in (("财务期末", "period_end"), ("财报披露", "published_on")):
                matches = re.findall(label + r"[：:]\s*(\d{4}-\d{2}-\d{2})", report_markdown)
                if matches != [financial_basis[key]]:
                    raise ValidationError(
                        "foreign report financial dates must match financial_basis"
                    )
        reader_text = "\n".join(
            (
                report_markdown,
                summary,
                *key_logic,
                *risks,
                valuation_note or "",
                return_model_note or "",
            )
        )
        if _REPORT_PROCESS_LEAK_RE.search(reader_text):
            raise ValidationError(
                "reader-facing research must not include user conversation or workflow notes; "
                "keep them in working papers"
            )
        if _REPORT_DEFERRAL_RE.search(report_markdown):
            raise ValidationError(
                "formal report must be self-contained and must not defer core analysis "
                "to prior reports"
            )
        if _REPORT_SECURITY_PRICE_LINE_RE.search(report_markdown):
            raise ValidationError(
                "formal report must not define a security-price trigger or review line"
            )
        if _REPORT_STITCHING_RE.search(report_markdown):
            raise ValidationError(
                "formal report must not stitch a financial-report excerpt onto prior analysis"
            )

        report_headings = tuple(
            line for line in report_markdown.splitlines() if re.match(r"^#{1,6}\s+", line)
        )
        missing_headings = [
            label
            for label, pattern in _REQUIRED_REPORT_HEADINGS.items()
            if not any(pattern.search(heading) for heading in report_headings)
        ]
        if missing_headings:
            raise ValidationError(
                "formal report is missing required headings: " + ", ".join(missing_headings)
            )
        if len(_REPORT_ONE_SENTENCE_HEADING_RE.findall(report_markdown)) != 1:
            raise ValidationError(
                "formal report requires exactly one one-sentence conclusion heading"
            )

        cutoff_matches = tuple(_REPORT_INFORMATION_CUTOFF_RE.finditer(report_markdown))
        if len(cutoff_matches) != 1:
            raise ValidationError(
                "formal report requires exactly one information cutoff declaration"
            )
        cutoff_match = cutoff_matches[0]
        declared_cutoff = (
            f"{cutoff_match.group('year')}-"
            f"{int(cutoff_match.group('month')):02d}-"
            f"{int(cutoff_match.group('day')):02d}"
        )
        if declared_cutoff != information_cutoff[:10]:
            raise ValidationError(
                "formal report information cutoff must match the structured result"
            )

        if value_range is not None:
            if not (
                _REPORT_METHOD_ONE_RE.search(report_markdown)
                and _REPORT_METHOD_TWO_RE.search(report_markdown)
                and _REPORT_PRIMARY_VALUATION_METHOD_RE.search(report_markdown)
            ):
                raise ValidationError(
                    "formal report with value_range must identify method one, method two, "
                    "and the primary valuation method"
                )
            range_match = _REPORT_CORE_VALUE_RANGE_RE.search(report_markdown)
            if range_match is None:
                raise ValidationError(
                    "formal report must state the structured value_range as its "
                    "core reasonable value range"
                )
            report_low = float(range_match.group("low").replace(",", ""))
            report_high = float(range_match.group("high").replace(",", ""))
            if not (
                math.isclose(report_low, value_range["low"], rel_tol=1e-9, abs_tol=0.01)
                and math.isclose(
                    report_high,
                    value_range["high"],
                    rel_tol=1e-9,
                    abs_tol=0.01,
                )
            ):
                raise ValidationError(
                    "formal report core reasonable value range must match value_range"
                )
        if value_range is None and valuation_note is None:
            raise ValidationError("research result requires value_range or valuation_note")
        if return_model_note is None:
            raise ValidationError("research result requires return_model_note")
        return {
            "symbol": symbol,
            "name": _optional_name(result.name),
            "outcome": outcome,
            "summary": summary,
            "key_logic": key_logic,
            "risks": risks,
            "value_range": value_range,
            "source_urls": source_urls,
            "information_cutoff": information_cutoff,
            "report_period": report_period,
            "financial_basis": financial_basis,
            "security_basis": security_basis,
            "report_markdown": report_markdown,
            "valuation_note": valuation_note,
            "return_model": return_model,
            "return_model_note": return_model_note,
        }

    def _company_directory(self, symbol: str) -> Path:
        market, ticker = self._market_symbol(symbol).split(":", 1)
        return self.root / "research" / "companies" / market / ticker

    def _formal_reports(self, symbol: str) -> tuple[Path, ...]:
        reports_directory = self._company_directory(symbol) / "reports"
        if not reports_directory.is_dir():
            return ()

        def order(path: Path) -> tuple[int, int]:
            match = _FORMAL_REPORT_RE.fullmatch(path.name)
            assert match is not None
            return _report_period_key(f"{match.group('year')}-{match.group('period')}")

        reports = [
            path
            for path in reports_directory.iterdir()
            if path.is_file() and _FORMAL_REPORT_RE.fullmatch(path.name)
        ]
        return tuple(sorted(reports, key=order))

    def _report_path(self, symbol: str, report_period: str) -> Path:
        normalized_period = _report_period(report_period)
        reports = self._formal_reports(symbol)
        if reports:
            newest_match = _FORMAL_REPORT_RE.fullmatch(reports[-1].name)
            assert newest_match is not None
            newest_period = f"{newest_match.group('year')}-{newest_match.group('period')}"
            if _report_period_key(normalized_period) < _report_period_key(newest_period):
                raise ValidationError(
                    f"research period for {symbol} predates its newest report period"
                )
        reports_directory = self._company_directory(symbol) / "reports"
        return reports_directory / f"{normalized_period}.md"

    def apply_result(
        self,
        result: ResearchResult,
        *,
        task_id: str,
        at: str | datetime | None = None,
    ) -> dict[str, Any]:
        """Apply the worker's single final answer and remove its current task."""

        normalized = self._normalized_result(result)
        self._market_symbol(normalized["symbol"])
        wanted = _nonblank(task_id, "task_id")
        timestamp = _timestamp(at)
        with _exclusive_lock(self.lock_path):
            active_standard, _ = _standards_registry(self.root)
            states = self._states()
            tasks = self._tasks()
            task = next((item for item in tasks if item.task_id == wanted), None)
            if task is None:
                raise ValidationError(f"task is not current: {wanted}")
            if task.status is not TaskStatus.RUNNING:
                raise ValidationError("research task must be running before completion")
            if task.symbol != normalized["symbol"]:
                raise ValidationError("research result symbol does not match task symbol")
            if task.report_period != normalized["report_period"]:
                raise ValidationError("research result period does not match task period")
            if task.financial_basis and normalized["financial_basis"] != task.financial_basis:
                raise ValidationError("result financial_basis does not match scheduled disclosure")
            current_state = states.get(normalized["symbol"])
            if (
                current_state
                and normalized["financial_basis"]
                and current_state.get("financial_basis")
            ):
                old_end = current_state["financial_basis"]["period_end"]
                new_end = normalized["financial_basis"]["period_end"]
                if new_end < old_end or (
                    normalized["report_period"] != current_state["report_period"]
                    and new_end <= old_end
                ):
                    raise ValidationError("new report period must advance the financial period end")
            needs_comparison = isinstance((current_state or {}).get("basis_report_path"), str)
            if needs_comparison and not _has_refresh_comparison_table(
                normalized["report_markdown"]
            ):
                raise ValidationError(
                    "updated formal report must contain a populated comparison table for "
                    "prior assumptions, current actuals, judgment changes, and valuation impact"
                )
            state = states.setdefault(
                normalized["symbol"],
                _empty_state(normalized["symbol"], normalized["name"], timestamp),
            )
            status = {
                ResearchOutcome.IGNORE.value: CompanyStatus.IGNORE.value,
                ResearchOutcome.COVERED.value: CompanyStatus.COVERED.value,
            }[normalized["outcome"]]
            report_path = self._report_path(normalized["symbol"], normalized["report_period"])
            report_relative = report_path.relative_to(self.root).as_posix()
            report_content = normalized["report_markdown"].rstrip() + "\n"
            _atomic_write_text(report_path, report_content)
            state.update(
                {
                    "schema_version": STATE_SCHEMA_VERSION,
                    "symbol": normalized["symbol"],
                    "name": normalized["name"] or state.get("name"),
                    "universe_status": UniverseStatus.ACTIVE.value,
                    "status": status,
                    "updated_at": timestamp,
                    "summary": normalized["summary"],
                    "key_logic": normalized["key_logic"],
                    "risks": normalized["risks"],
                    "value_range": normalized["value_range"],
                    "source_urls": normalized["source_urls"],
                    "last_research_at": timestamp,
                    "information_cutoff": normalized["information_cutoff"],
                    "report_period": normalized["report_period"],
                    **(
                        {
                            "financial_basis": normalized["financial_basis"],
                            "security_basis": normalized["security_basis"],
                        }
                        if normalized["financial_basis"]
                        else {}
                    ),
                    "basis_report_path": report_relative,
                    "valuation_note": normalized["valuation_note"],
                    "return_model": normalized["return_model"],
                    "return_model_note": normalized["return_model_note"],
                    "standard_id": active_standard["id"],
                    "spec_revision": active_standard["spec_revision"],
                    "accepted_at": timestamp,
                }
            )
            tasks = [item for item in tasks if item.task_id != task.task_id]
            self._write_states(states)
            self._write_tasks(tasks)
            return dict(state)

    def validate(self) -> ResearchFlowStatus:
        """Validate periodic research state and its current task queue."""

        with _thread_lock(self.lock_path):
            states = self._states()
            tasks = self._tasks()
            standards: dict[str, dict[str, Any]] | None = None
            counts = {status.value: 0 for status in CompanyStatus}
            universe_counts = {status.value: 0 for status in UniverseStatus}
            try:
                for symbol, state in states.items():
                    if state.get("schema_version") != STATE_SCHEMA_VERSION:
                        raise StateCorruptionError(f"state for {symbol} has unsupported schema")
                    universe_status = _enum_value(
                        state.get("universe_status"), UniverseStatus, "universe status"
                    )
                    status = _enum_value(state.get("status"), CompanyStatus, "company status")
                    universe_counts[universe_status] += 1
                    counts[status] += 1
                    _timestamp(state.get("updated_at"))
                    _strings(state.get("key_logic") or [], "key logic")
                    _strings(state.get("risks") or [], "risk")
                    _urls(state.get("source_urls") or [])
                    removed_fields = {
                        "event_triggers",
                        "last_screening",
                        "candidate_since",
                        "invalidation",
                        "last_update",
                        "processed_triggers",
                    }.intersection(state)
                    if removed_fields:
                        raise StateCorruptionError(
                            f"retired event fields remain for {symbol}: "
                            + ", ".join(sorted(removed_fields))
                        )
                    retired_return_fields = sorted(
                        _RETIRED_DYNAMIC_RETURN_FIELDS.intersection(state)
                    )
                    if retired_return_fields or "price_levels" in state or "price_monitor" in state:
                        raise StateCorruptionError(f"retired dynamic fields remain for {symbol}")

                    report_path = state.get("basis_report_path")
                    report_period = state.get("report_period")
                    standard_stamp = (
                        state.get("standard_id"),
                        state.get("spec_revision"),
                        state.get("accepted_at"),
                    )
                    if any(value is not None for value in standard_stamp) and not all(
                        value is not None for value in standard_stamp
                    ):
                        raise StateCorruptionError(
                            f"research standard stamp is incomplete for {symbol}"
                        )
                    if all(value is not None for value in standard_stamp):
                        if report_path is None:
                            raise StateCorruptionError(
                                f"research standard stamp has no report for {symbol}"
                            )
                        if standards is None:
                            try:
                                _, standards = _standards_registry(self.root)
                            except ValidationError as exc:
                                raise StateCorruptionError(str(exc)) from exc
                        standard = standards.get(state["standard_id"])
                        if standard is None or standard.get("status") == "draft":
                            raise StateCorruptionError(
                                f"research standard is unknown or draft for {symbol}"
                            )
                        if state["spec_revision"] != standard["spec_revision"]:
                            raise StateCorruptionError(
                                f"research standard revision mismatch for {symbol}"
                            )
                        accepted_at = _timestamp(state["accepted_at"])
                        information_cutoff_value = state.get("information_cutoff")
                        if information_cutoff_value is not None and datetime.fromisoformat(
                            accepted_at.replace("Z", "+00:00")
                        ) < datetime.fromisoformat(
                            _timestamp(information_cutoff_value).replace("Z", "+00:00")
                        ):
                            raise StateCorruptionError(
                                f"research acceptance predates information cutoff for {symbol}"
                            )
                    if report_path is not None:
                        expected_prefix = (self._company_directory(symbol) / "reports").relative_to(
                            self.root
                        ).as_posix() + "/"
                        if not isinstance(report_path, str) or not report_path.startswith(
                            expected_prefix
                        ):
                            raise StateCorruptionError(f"basis_report_path mismatch for {symbol}")
                        match = _FORMAL_REPORT_RE.fullmatch(
                            report_path.removeprefix(expected_prefix)
                        )
                        if match is None:
                            raise StateCorruptionError(
                                f"basis_report_path is not a period report for {symbol}"
                            )
                        expected_period = f"{match.group('year')}-{match.group('period')}"
                        if report_period != expected_period:
                            raise StateCorruptionError(
                                f"report_period does not match basis_report_path for {symbol}"
                            )
                        information_cutoff = _timestamp(state.get("information_cutoff"))
                        _report_period(
                            report_period,
                            information_cutoff=(
                                information_cutoff if self.market == "cn-a" else None
                            ),
                        )
                        if self.market != "cn-a":
                            if not _financial_basis(
                                state.get("financial_basis"), cutoff=information_cutoff
                            ):
                                raise StateCorruptionError("foreign report lacks financial_basis")
                            _security_basis(state.get("security_basis"), symbol)
                        _timestamp(state.get("last_research_at"))
                        expected_report = self.root / report_path
                        if (
                            not expected_report.is_file()
                            or not expected_report.read_text(encoding="utf-8").strip()
                        ):
                            raise StateCorruptionError(
                                f"basis report is missing or blank for {symbol}"
                            )
                        if _REPORT_DEFERRAL_RE.search(expected_report.read_text(encoding="utf-8")):
                            raise StateCorruptionError(
                                f"basis report defers core analysis for {symbol}"
                            )
                        reports = self._formal_reports(symbol)
                        if not reports or expected_report != reports[-1]:
                            raise StateCorruptionError(
                                f"basis_report_path is not the latest report period for {symbol}"
                            )
                        if not state.get("key_logic") or not state.get("risks"):
                            raise StateCorruptionError(
                                f"researched company lacks logic or risks: {symbol}"
                            )
                        if not state.get("source_urls"):
                            raise StateCorruptionError(
                                f"researched company lacks sources: {symbol}"
                            )
                        note = state.get("return_model_note")
                        if note is not None:
                            _return_model_text(note, "return_model_note")
                        if state.get("return_model") is not None:
                            if note is None:
                                raise StateCorruptionError(
                                    f"return_model lacks return_model_note: {symbol}"
                                )
                            raw_value_range = state.get("value_range")
                            _stored_return_model(
                                state["return_model"],
                                information_cutoff=information_cutoff,
                                value_range=raw_value_range,
                            )
                    elif report_period is not None:
                        raise StateCorruptionError(
                            f"report_period requires basis_report_path for {symbol}"
                        )

                    if status == CompanyStatus.COVERED.value:
                        if report_path is None:
                            raise StateCorruptionError(f"covered company has no report: {symbol}")
                        if state.get("value_range") is None and not state.get("valuation_note"):
                            raise StateCorruptionError(f"covered company lacks valuation: {symbol}")
                    elif status == CompanyStatus.UNSEEN.value and report_path is not None:
                        raise StateCorruptionError(f"unseen company already has a report: {symbol}")
            except (KeyError, TypeError, ValidationError) as exc:
                if isinstance(exc, StateCorruptionError):
                    raise
                raise StateCorruptionError(f"invalid research state: {exc}") from exc

            queued_symbols: set[str] = set()
            for task in tasks:
                company = states.get(task.symbol)
                if company is None:
                    raise StateCorruptionError(f"queue task has no company state: {task.symbol}")
                if company.get("universe_status") != UniverseStatus.ACTIVE.value:
                    raise StateCorruptionError(f"inactive company has a task: {task.symbol}")
                if task.symbol in queued_symbols:
                    raise StateCorruptionError(
                        f"company has more than one current task: {task.symbol}"
                    )
                queued_symbols.add(task.symbol)
                if task.status is TaskStatus.RUNNING and task.started_at is None:
                    raise StateCorruptionError(f"running task has no started_at: {task.task_id}")
                if task.status is TaskStatus.QUEUED and task.started_at is not None:
                    raise StateCorruptionError(
                        f"queued task unexpectedly has started_at: {task.task_id}"
                    )

            return ResearchFlowStatus(
                companies=len(states),
                active=universe_counts[UniverseStatus.ACTIVE.value],
                inactive=universe_counts[UniverseStatus.INACTIVE.value],
                unseen=counts[CompanyStatus.UNSEEN.value],
                ignored=counts[CompanyStatus.IGNORE.value],
                covered=counts[CompanyStatus.COVERED.value],
                queued=sum(task.status is TaskStatus.QUEUED for task in tasks),
                running=sum(task.status is TaskStatus.RUNNING for task in tasks),
            )

    def status(self) -> ResearchFlowStatus:
        """Return validated compact counts for CLI/status consumers."""

        return self.validate()

    def read_states(self) -> tuple[dict[str, Any], ...]:
        with _exclusive_lock(self.lock_path):
            states = self._states()
        return tuple(dict(states[symbol]) for symbol in sorted(states))


__all__ = [
    "CompanyRef",
    "CompanyStatus",
    "QUEUE_PATH",
    "ResearchFlow",
    "ResearchFlowError",
    "ResearchFlowStatus",
    "ResearchOutcome",
    "ResearchBatchUpdate",
    "ResearchRequest",
    "ResearchResult",
    "ReturnModel",
    "ResearchTask",
    "STATE_PATH",
    "STANDARDS_REGISTRY_PATH",
    "MANUAL_REWRITE_TRIGGER",
    "PERIODIC_TRIGGER",
    "StateCorruptionError",
    "TaskStatus",
    "UniverseStatus",
    "ValidationError",
    "ValueRange",
]
