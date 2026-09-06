from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from collections import Counter
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlsplit

POOL_PATH = Path("screening/cn-a/value-quality/pool.json")
CURRENT_PATH = POOL_PATH.with_name("current.md")
DEFAULT_METHODOLOGY_PATH = "prompts/screening/cn-a-value-quality.md"
TIERS = ("core_moat", "quality_research")
TIER_TITLES = {"core_moat": "A：核心护城河池", "quality_research": "B：质量研究池"}
GROUPS = (
    "consumer_brand_network",
    "healthcare_platform",
    "technology_industrial",
    "infrastructure_finance_resource",
)
GROUP_TITLES = dict(
    zip(
        GROUPS,
        (
            "消费、品牌与网络",
            "医疗平台、产品与牌照",
            "科技与工业制造",
            "基础设施、金融与资源",
        ),
        strict=True,
    )
)
_CARD_FIELDS = {"moat", "owner_cash", "risks", "tier_reason"}
_SYMBOL_RE = re.compile(r"CN:[0-9]{6}")
# Explicit contamination only; product prices and loan yields are operating facts.
_FORBIDDEN = re.compile(
    r"股价|现价|市值|估值|折价|目标价|买入价|关注价|安全边际|仓位|买入|卖出|加仓|减仓|"
    r"建仓|止损|止盈|价格触发|投资授权|收益率门槛|证券溢价|"
    r"(?<![a-zA-Z])(?:IRR|PE|PB|buy_now|armed|rearm|covered|stale|candidate)(?![a-zA-Z])|"
    r"report_path|return_model|research_status|task_id|research[/\\]companies",
    re.IGNORECASE,
)
_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()


class QualityPoolError(ValueError):
    """Invalid independent quality pool."""


def _text(value: object, label: str, *, screened: bool = True) -> str:
    if not isinstance(value, str) or not value.strip():
        raise QualityPoolError(f"{label} 必须是非空字符串")
    result = value.strip()
    if screened and _FORBIDDEN.search(result):
        raise QualityPoolError(f"{label} 含行情、交易或单公司研究耦合内容")
    return result


def _object(value: object, fields: set[str], label: str) -> dict:
    if not isinstance(value, dict) or set(value) != fields:
        raise QualityPoolError(f"{label} 字段必须为：{', '.join(sorted(fields))}")
    return value


def _date(value: object, label: str) -> str:
    value = _text(value, label)
    try:
        if date.fromisoformat(value).isoformat() == value:
            return value
    except ValueError:
        pass
    raise QualityPoolError(f"{label} 必须是 YYYY-MM-DD 日期")


def _symbol(value: object) -> str:
    if not isinstance(value, str) or not _SYMBOL_RE.fullmatch(value):
        raise QualityPoolError("证券代码必须形如 CN:600000")
    return value


def _array(value: object, label: str) -> list:
    if not isinstance(value, list):
        raise QualityPoolError(f"{label} 必须是数组")
    return value


def _sources(value: object) -> tuple[dict[str, str], ...]:
    values = _array(value, "sources")
    if not 1 <= len(values) <= 3:
        raise QualityPoolError("sources 必须有 1—3 个公开来源")
    result = []
    for raw in values:
        raw = _object(raw, {"title", "url"}, "source")
        title = _text(raw["title"], "source.title")
        url = _text(raw["url"], "source.url", screened=False)
        try:
            parsed = urlsplit(url)
            valid = parsed.scheme in ("https", "http") and parsed.hostname
        except ValueError:
            valid = False
        if not valid or any(c.isspace() for c in url):
            raise QualityPoolError("来源必须使用有效公开 HTTP(S) URL")
        result.append({"title": title, "url": url})
    if len({r["url"] for r in result}) != len(result):
        raise QualityPoolError("来源 URL 不得重复")
    return tuple(result)


@dataclass(frozen=True)
class QualityPoolCompany:
    symbol: str
    name: str
    industry: str
    tier: str
    group: str
    moat: str
    owner_cash: str
    risks: str
    tier_reason: str
    sources: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class QualityPool:
    schema_version: int
    as_of: str
    methodology: str
    philosophy: str
    universe: dict[str, Any]
    review: dict[str, Any]
    companies: tuple[QualityPoolCompany, ...]

    def payload(self) -> dict[str, Any]:
        return json.loads(json.dumps(asdict(self), ensure_ascii=False))

    def status(self) -> dict[str, Any]:
        tiers = Counter(c.tier for c in self.companies)
        groups = Counter(c.group for c in self.companies)
        return {
            "as_of": self.as_of,
            "universe_as_of": self.universe["as_of"],
            "universe_count": len(self.universe["securities"]),
            "pool_count": len(self.companies),
            "tier_counts": {t: tiers[t] for t in TIERS},
            "group_counts": {g: groups[g] for g in GROUPS},
            "reviewed_count": len(self.review["reviewed_symbols"]),
            "missing_baseline_count": len(self.review["missing_baseline_symbols"]),
        }


def parse_quality_pool(payload: object) -> QualityPool:
    p = _object(
        payload,
        {
            "schema_version",
            "as_of",
            "methodology",
            "philosophy",
            "universe",
            "review",
            "companies",
        },
        "价值质量池 v2",
    )
    if type(p["schema_version"]) is not int or p["schema_version"] != 2:
        raise QualityPoolError("仅支持 schema_version=2；旧池需补齐判断卡和独立证券清单")
    as_of = _date(p["as_of"], "as_of")
    u = _object(p["universe"], {"as_of", "sources", "securities"}, "universe")
    universe_date = _date(u["as_of"], "universe.as_of")
    if universe_date > as_of:
        raise QualityPoolError("证券清单日期不能晚于筛选日期")
    if not isinstance(u["securities"], dict) or not u["securities"]:
        raise QualityPoolError("universe.securities 必须是非空代码与标准简称映射")
    identities = {_symbol(k): _text(v, "证券简称") for k, v in u["securities"].items()}
    universe = {
        "as_of": universe_date,
        "sources": list(_sources(u["sources"])),
        "securities": dict(sorted(identities.items())),
    }
    r = _object(
        p["review"],
        {
            "baseline_as_of",
            "baseline_count",
            "missing_baseline_symbols",
            "reviewed_symbols",
            "scope_note",
            "omission_check",
            "admission_check",
        },
        "review",
    )
    baseline_date = _date(r["baseline_as_of"], "review.baseline_as_of")
    if baseline_date > as_of or type(r["baseline_count"]) is not int or r["baseline_count"] < 0:
        raise QualityPoolError("历史财务基线日期或数量不合法")
    review = {"baseline_as_of": baseline_date, "baseline_count": r["baseline_count"]}
    for field in ("missing_baseline_symbols", "reviewed_symbols"):
        symbols = [_symbol(s) for s in _array(r[field], field)]
        if len(set(symbols)) != len(symbols) or not set(symbols) <= identities.keys():
            raise QualityPoolError(f"{field} 必须为证券清单内的不重复代码")
        review[field] = sorted(symbols)
    for field in ("scope_note", "omission_check", "admission_check"):
        review[field] = _text(r[field], field)
    companies = []
    seen = set()
    for raw in _array(p["companies"], "companies"):
        c = _object(
            raw,
            {
                "symbol",
                "name",
                "industry",
                "tier",
                "group",
                "sources",
                *_CARD_FIELDS,
            },
            "company（不得耦合单公司研究、行情或交易字段）",
        )
        symbol = _symbol(c["symbol"])
        if symbol in seen:
            raise QualityPoolError(f"重复证券：{symbol}")
        seen.add(symbol)
        if symbol not in identities or c["name"] != identities[symbol]:
            raise QualityPoolError(f"{symbol} 代码或名称与独立证券清单不符")
        if c["tier"] not in TIERS or c["group"] not in GROUPS:
            raise QualityPoolError(f"{symbol} 分层或分组不合法")
        companies.append(
            QualityPoolCompany(
                symbol=symbol,
                name=identities[symbol],
                industry=_text(c["industry"], "industry"),
                tier=c["tier"],
                group=c["group"],
                sources=_sources(c["sources"]),
                **{f: _text(c[f], f"{symbol}.{f}") for f in _CARD_FIELDS},
            )
        )
    if not seen <= set(review["reviewed_symbols"]):
        raise QualityPoolError("入池公司必须包含在本轮 reviewed_symbols 中")
    companies.sort(key=lambda c: (TIERS.index(c.tier), GROUPS.index(c.group), c.symbol))
    return QualityPool(
        2,
        as_of,
        _text(p["methodology"], "methodology", screened=False),
        _text(p["philosophy"], "philosophy"),
        universe,
        review,
        tuple(companies),
    )


def _markdown(value: str) -> str:
    return value.replace("|", "／").replace("\r", " ").replace("\n", " ")


def render_current_pool(pool: QualityPool) -> str:
    s = pool.status()
    lines = [
        "# 全 A 股价值质量池",
        "",
        f"筛选复核日期：{pool.as_of}。方法：{pool.methodology}。",
        "",
        pool.philosophy,
        "",
        f"当前 **{s['pool_count']} 家**：核心 **{s['tier_counts']['core_moat']} 家**，"
        f"验证层 **{s['tier_counts']['quality_research']} 家**。",
        "",
        "本池只表达商业质量与持续研究价值，不表达买入、仓位、当前估值或单公司研究状态。",
        "",
        f"证券清单：{pool.universe['as_of']}，{s['universe_count']} 家。"
        f"本轮重点复核 {s['reviewed_count']} 家；"
        f"缺少旧财务基线 {s['missing_baseline_count']} 家。",
        "",
        pool.review["scope_note"],
        "",
        "遗漏检查：" + pool.review["omission_check"],
        "",
        "误入检查：" + pool.review["admission_check"],
        "",
    ]
    for tier in TIERS:
        lines.extend([f"## {TIER_TITLES[tier]}（{s['tier_counts'][tier]} 家）", ""])
        for group in GROUPS:
            subset = [c for c in pool.companies if c.tier == tier and c.group == group]
            if not subset:
                continue
            lines.extend([f"### {GROUP_TITLES[group]}（{len(subset)} 家）", ""])
            for c in subset:
                lines.extend(
                    [
                        f"#### {c.symbol[3:]} {_markdown(c.name)} · {_markdown(c.industry)}",
                        "",
                        "- 竞争优势：" + _markdown(c.moat),
                        "- 普通股现金：" + _markdown(c.owner_cash),
                        "- 主要反证：" + _markdown(c.risks),
                        "- 分层理由：" + _markdown(c.tier_reason),
                        "- 来源："
                        + "；".join(
                            f"[{_markdown(src['title'])}](<{src['url']}>)" for src in c.sources
                        ),
                        "",
                    ]
                )
    return "\n".join(lines).rstrip() + "\n"


@contextmanager
def _exclusive_lock(path: Path) -> Iterator[None]:
    with _LOCKS_GUARD:
        local = _LOCKS.setdefault(str(path.resolve()), threading.RLock())
    path.parent.mkdir(parents=True, exist_ok=True)
    with local, path.open("a+b") as handle:
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
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@dataclass(frozen=True)
class PoolWriteResult:
    pool: QualityPool
    projection_current: bool
    warning: str | None = None


class QualityPoolStore:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.pool_path = self.root / POOL_PATH
        self.current_path = self.root / CURRENT_PATH
        self.lock_path = self.pool_path.with_suffix(".json.lock")

    def _validate_methodology(self, pool: QualityPool) -> None:
        path = (self.root / pool.methodology).resolve()
        if not path.is_relative_to(self.root) or not path.is_file():
            raise QualityPoolError("methodology 必须指向仓库内存在的文件")

    def read(self) -> QualityPool:
        try:
            payload = json.loads(self.pool_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise QualityPoolError(f"无法读取有效价值质量池：{exc}") from exc
        pool = parse_quality_pool(payload)
        self._validate_methodology(pool)
        return pool

    def projection_current(self, pool: QualityPool) -> bool:
        try:
            return self.current_path.read_text(encoding="utf-8") == render_current_pool(pool)
        except (OSError, UnicodeError):
            return False

    def replace(self, payload: object) -> PoolWriteResult:
        pool = parse_quality_pool(payload)
        self._validate_methodology(pool)
        normalized = json.dumps(pool.payload(), ensure_ascii=False, indent=2) + "\n"
        current = render_current_pool(pool)
        with _exclusive_lock(self.lock_path):
            # JSON is the sole commit point; a failed projection cannot uncommit it.
            _atomic_write_text(self.pool_path, normalized)
            try:
                _atomic_write_text(self.current_path, current)
            except OSError as exc:
                return PoolWriteResult(
                    pool, False, f"名单已保存；投影更新失败，请运行 rebuild：{exc}"
                )
        return PoolWriteResult(pool, True)

    def rebuild(self) -> QualityPool:
        with _exclusive_lock(self.lock_path):
            pool = self.read()
            _atomic_write_text(self.current_path, render_current_pool(pool))
        return pool

    def validate(self) -> QualityPool:
        pool = self.read()
        if not self.projection_current(pool):
            raise QualityPoolError(
                "current.md 不是 pool.json 的确定性投影；请运行 quality-pool rebuild"
            )
        return pool
