from __future__ import annotations

import json
import os
import re
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Sequence

POOL_PATH = Path("screening/cn-a/value-quality/pool.json")
CURRENT_PATH = Path("screening/cn-a/value-quality/current.md")
DEFAULT_METHODOLOGY_PATH = "prompts/screening/cn-a-value-quality.md"

TIERS = ("core_moat", "quality_research")
TIER_TITLES = {
    "core_moat": "A：核心护城河池",
    "quality_research": "B：质量研究池",
}
GROUPS = (
    "consumer_brand_network",
    "healthcare_platform",
    "technology_industrial",
    "infrastructure_finance_resource",
)
GROUP_TITLES = {
    "consumer_brand_network": "消费、品牌与网络",
    "healthcare_platform": "医疗平台、产品与牌照",
    "technology_industrial": "科技与工业制造",
    "infrastructure_finance_resource": "基础设施、金融与资源",
}

_SYMBOL_RE = re.compile(r"CN:\d{6}")
_POOL_FIELDS = {
    "schema_version",
    "as_of",
    "universe_count",
    "methodology",
    "philosophy",
    "companies",
}
_COMPANY_FIELDS = {"symbol", "name", "industry", "tier", "group"}
_COUPLING_FIELDS = {
    "candidate_since",
    "current_price",
    "information_cutoff",
    "report_path",
    "research_status",
    "return_model",
    "status",
    "task_id",
    "valuation",
    "value_range",
}


class QualityPoolError(ValueError):
    """Raised when the independent value-quality pool is invalid."""


def _nonblank(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise QualityPoolError(f"{label} 必须是非空字符串")
    return value.strip()


def _markdown(value: str) -> str:
    return value.replace("|", "／").replace("\r", " ").replace("\n", " ")


@dataclass(frozen=True)
class QualityPoolCompany:
    symbol: str
    name: str
    industry: str
    tier: str
    group: str
    note: str | None = None


@dataclass(frozen=True)
class QualityPool:
    schema_version: int
    as_of: str
    universe_count: int
    methodology: str
    philosophy: str
    companies: tuple[QualityPoolCompany, ...]

    def payload(self) -> dict[str, Any]:
        companies: list[dict[str, Any]] = []
        for company in self.companies:
            item = asdict(company)
            if item["note"] is None:
                item.pop("note")
            companies.append(item)
        return {
            "schema_version": self.schema_version,
            "as_of": self.as_of,
            "universe_count": self.universe_count,
            "methodology": self.methodology,
            "philosophy": self.philosophy,
            "companies": companies,
        }

    def status(self) -> dict[str, Any]:
        tier_counts = Counter(company.tier for company in self.companies)
        group_counts = Counter(company.group for company in self.companies)
        return {
            "as_of": self.as_of,
            "universe_count": self.universe_count,
            "pool_count": len(self.companies),
            "tier_counts": {tier: tier_counts[tier] for tier in TIERS},
            "group_counts": {group: group_counts[group] for group in GROUPS},
        }


def parse_quality_pool(payload: object) -> QualityPool:
    if not isinstance(payload, Mapping):
        raise QualityPoolError("价值质量池必须是 JSON 对象")
    if set(payload) != _POOL_FIELDS:
        missing = sorted(_POOL_FIELDS.difference(payload))
        unexpected = sorted(set(payload).difference(_POOL_FIELDS))
        detail = []
        if missing:
            detail.append("缺少 " + ", ".join(missing))
        if unexpected:
            detail.append("多出 " + ", ".join(unexpected))
        raise QualityPoolError("价值质量池字段不符合 version 1 合同：" + "；".join(detail))
    if isinstance(payload["schema_version"], bool) or payload["schema_version"] != 1:
        raise QualityPoolError("仅支持 schema_version=1")

    as_of = _nonblank(payload["as_of"], "as_of")
    try:
        parsed_date = date.fromisoformat(as_of)
    except ValueError as exc:
        raise QualityPoolError("as_of 必须是 YYYY-MM-DD 日期") from exc
    if parsed_date.isoformat() != as_of:
        raise QualityPoolError("as_of 必须是规范的 YYYY-MM-DD 日期")

    universe_count = payload["universe_count"]
    if isinstance(universe_count, bool) or not isinstance(universe_count, int):
        raise QualityPoolError("universe_count 必须是正整数")
    if universe_count <= 0:
        raise QualityPoolError("universe_count 必须是正整数")

    methodology = _nonblank(payload["methodology"], "methodology")
    philosophy = _nonblank(payload["philosophy"], "philosophy")
    raw_companies = payload["companies"]
    if not isinstance(raw_companies, Sequence) or isinstance(raw_companies, (str, bytes)):
        raise QualityPoolError("companies 必须是对象数组")
    if not raw_companies:
        raise QualityPoolError("companies 不能为空")
    if len(raw_companies) > universe_count:
        raise QualityPoolError("公司池数量不能超过 universe_count")

    companies: list[QualityPoolCompany] = []
    symbols: set[str] = set()
    seen_quality_tier = False
    for index, raw_company in enumerate(raw_companies, start=1):
        if not isinstance(raw_company, Mapping):
            raise QualityPoolError(f"companies[{index}] 必须是对象")
        present_coupling = sorted(_COUPLING_FIELDS.intersection(raw_company))
        if present_coupling:
            raise QualityPoolError(
                "价值质量池不得耦合单公司研究、行情或估值字段："
                + ", ".join(present_coupling)
            )
        allowed_fields = _COMPANY_FIELDS | {"note"}
        missing = sorted(_COMPANY_FIELDS.difference(raw_company))
        unexpected = sorted(set(raw_company).difference(allowed_fields))
        if missing or unexpected:
            detail = []
            if missing:
                detail.append("缺少 " + ", ".join(missing))
            if unexpected:
                detail.append("多出 " + ", ".join(unexpected))
            raise QualityPoolError(f"companies[{index}] 字段错误：" + "；".join(detail))

        symbol = _nonblank(raw_company["symbol"], f"companies[{index}].symbol")
        if not _SYMBOL_RE.fullmatch(symbol):
            raise QualityPoolError(f"companies[{index}].symbol 必须形如 CN:600000")
        if symbol in symbols:
            raise QualityPoolError(f"公司池存在重复证券：{symbol}")
        symbols.add(symbol)

        tier = _nonblank(raw_company["tier"], f"companies[{index}].tier")
        if tier not in TIERS:
            raise QualityPoolError(f"companies[{index}].tier 必须是 {' / '.join(TIERS)}")
        if tier == "quality_research":
            seen_quality_tier = True
        elif seen_quality_tier:
            raise QualityPoolError("core_moat 必须整体排在 quality_research 之前")

        group = _nonblank(raw_company["group"], f"companies[{index}].group")
        if group not in GROUPS:
            raise QualityPoolError(f"companies[{index}].group 不在允许范围内")
        raw_note = raw_company.get("note")
        note = None if raw_note is None else _nonblank(raw_note, f"companies[{index}].note")
        companies.append(
            QualityPoolCompany(
                symbol=symbol,
                name=_nonblank(raw_company["name"], f"companies[{index}].name"),
                industry=_nonblank(
                    raw_company["industry"], f"companies[{index}].industry"
                ),
                tier=tier,
                group=group,
                note=note,
            )
        )

    return QualityPool(
        schema_version=1,
        as_of=as_of,
        universe_count=universe_count,
        methodology=methodology,
        philosophy=philosophy,
        companies=tuple(companies),
    )


def render_current_pool(pool: QualityPool) -> str:
    status = pool.status()
    lines = [
        "# 全 A 股价值质量池",
        "",
        f"信息截止：{pool.as_of}。方法规范：`{pool.methodology}`。",
        "",
        pool.philosophy,
        "",
        (
            f"当前共 **{status['pool_count']} 家**，其中核心护城河池 "
            f"**{status['tier_counts']['core_moat']} 家**，质量研究池 "
            f"**{status['tier_counts']['quality_research']} 家**。"
        ),
        "",
        "本池只表达商业质量与持续研究价值，不表达买入、仓位、当前估值或单公司研究状态。",
        "",
    ]
    for tier in TIERS:
        tier_companies = [company for company in pool.companies if company.tier == tier]
        lines.extend([f"## {TIER_TITLES[tier]}（{len(tier_companies)} 家）", ""])
        for group in GROUPS:
            subset = [company for company in tier_companies if company.group == group]
            if not subset:
                continue
            lines.extend([f"### {GROUP_TITLES[group]}（{len(subset)} 家）", ""])
            if any(company.note for company in subset):
                lines.extend(
                    [
                        "| 代码 | 公司 | 行业 | 筛选备注 |",
                        "|---|---|---|---|",
                    ]
                )
                for company in subset:
                    lines.append(
                        f"| {company.symbol.removeprefix('CN:')} | {_markdown(company.name)} | "
                        f"{_markdown(company.industry)} | {_markdown(company.note or '—')} |"
                    )
            else:
                lines.extend(["| 代码 | 公司 | 行业 |", "|---|---|---|"])
                for company in subset:
                    lines.append(
                        f"| {company.symbol.removeprefix('CN:')} | {_markdown(company.name)} | "
                        f"{_markdown(company.industry)} |"
                    )
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(text, encoding="utf-8", newline="\n")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class QualityPoolStore:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.pool_path = self.root / POOL_PATH
        self.current_path = self.root / CURRENT_PATH

    def _validate_methodology(self, pool: QualityPool) -> None:
        methodology = (self.root / pool.methodology).resolve()
        try:
            methodology.relative_to(self.root)
        except ValueError as exc:
            raise QualityPoolError("methodology 必须位于仓库内") from exc
        if not methodology.is_file():
            raise QualityPoolError(f"methodology 文件不存在：{pool.methodology}")

    def read(self) -> QualityPool:
        if not self.pool_path.is_file():
            raise QualityPoolError(f"价值质量池不存在：{POOL_PATH.as_posix()}")
        try:
            payload = json.loads(self.pool_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise QualityPoolError("pool.json 不是有效 JSON") from exc
        return parse_quality_pool(payload)

    def replace(self, payload: object) -> QualityPool:
        pool = parse_quality_pool(payload)
        self._validate_methodology(pool)
        normalized = json.dumps(pool.payload(), ensure_ascii=False, indent=2) + "\n"
        current = render_current_pool(pool)
        _atomic_write_text(self.pool_path, normalized)
        _atomic_write_text(self.current_path, current)
        return pool

    def validate(self) -> QualityPool:
        pool = self.read()
        self._validate_methodology(pool)
        expected = render_current_pool(pool)
        if not self.current_path.is_file():
            raise QualityPoolError(f"可读投影不存在：{CURRENT_PATH.as_posix()}")
        if self.current_path.read_text(encoding="utf-8") != expected:
            raise QualityPoolError("current.md 不是 pool.json 的确定性投影；请重新 replace")
        return pool


__all__ = [
    "CURRENT_PATH",
    "DEFAULT_METHODOLOGY_PATH",
    "GROUPS",
    "POOL_PATH",
    "QualityPool",
    "QualityPoolCompany",
    "QualityPoolError",
    "QualityPoolStore",
    "TIERS",
    "parse_quality_pool",
    "render_current_pool",
]
