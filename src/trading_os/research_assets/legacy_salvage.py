from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .research_flow import ResearchFlowError, ValidationError, _atomic_write_text

LEGACY_TAG = "pre-simplification-20260808"

_REPORT_PATH_RE = re.compile(
    r"^research/companies/CN/(?P<ticker>\d{6})/reports/(?P<filename>[^/]+\.md)$"
)
_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:-|\.md$)")
_URL_RE = re.compile(r'https?://[^\s)>\]}"\']+')
_SPACE_RE = re.compile(r"\s+")
_CN_SYMBOL_RE = re.compile(
    r"(?:CN\s*[:：]\s*(\d{6})|(?<!\d)(\d{6})\s*\.(?:SZ|SH|BJ)\b)",
    re.IGNORECASE,
)


class LegacySalvageError(ResearchFlowError):
    """Raised when the frozen legacy snapshot cannot be archived safely."""


@dataclass(frozen=True)
class _TreeEntry:
    path: str
    object_id: str
    size: int


@dataclass(frozen=True)
class LegacyReportCandidate:
    candidate_id: str
    symbol: str
    name: str | None
    legacy_path: str
    legacy_blob_oid: str
    report_date: str | None
    report_kind: str
    byte_size: int
    score: int
    signals: tuple[str, ...]
    identity_status: str
    detected_symbols: tuple[str, ...]
    newer_report_paths: tuple[str, ...]
    title: str | None
    excerpt: str


@dataclass(frozen=True)
class LegacyCandidateScan:
    tag: str
    commit: str
    reports_scanned: int
    reports_excluded_for_current: int
    identity_mismatches: tuple[dict[str, Any], ...]
    eligible_reports: int
    candidates: tuple[LegacyReportCandidate, ...]


@dataclass(frozen=True)
class LegacyArchiveResult:
    tag: str
    commit: str
    reports_scanned: int
    companies_seen: int
    companies_archived: int
    already_archived: int
    companies_skipped: int
    skipped: tuple[dict[str, Any], ...]


def _kind(filename: str) -> str:
    lowered = filename.lower()
    if any(word in lowered for word in ("failed", "superseded", "archived", "draft")):
        return "excluded"
    if "investment-committee" in lowered or "committee-review" in lowered:
        return "process_review"
    if "chatgpt" in lowered:
        return "chatgpt_deep_research"
    if "initial-research" in lowered:
        return "modern_initial_research"
    if "followup" in lowered:
        return "followup"
    if any(word in lowered for word in ("refresh", "update", "supplement", "monitoring")):
        return "update"
    if "deep-review" in lowered:
        return "deep_review"
    if "rapid-triage" in lowered:
        return "rapid_triage"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}-initial\.md", lowered):
        return "bulk_initial"
    return "other"


_KIND_SCORE = {
    "chatgpt_deep_research": 95,
    "modern_initial_research": 90,
    "followup": 80,
    "update": 70,
    "deep_review": 65,
    "other": 40,
    "rapid_triage": 25,
    "bulk_initial": 5,
    "process_review": -100,
    "excluded": -100,
}


def _score(kind: str, body: str, byte_size: int) -> tuple[int, tuple[str, ...]]:
    signals = [f"kind:{kind}", f"length:{byte_size}"]
    score = _KIND_SCORE[kind] + min(15, byte_size // 4_000)
    url_count = len(_URL_RE.findall(body))
    if url_count:
        score += min(5, url_count)
        signals.append(f"urls:{url_count}")
    markers = (
        ("business", ("商业模式", "业务模式", "竞争优势"), 4),
        ("valuation", ("估值", "合理价值", "价值区间", "买入区"), 5),
        ("risk", ("风险", "证伪"), 4),
        ("trigger", ("触发", "催化", "复核条件"), 4),
        ("financials", ("现金流", "毛利率", "资产负债表"), 3),
        ("sources", ("来源", "参考资料", "原始披露"), 2),
    )
    for label, words, points in markers:
        if any(word in body for word in words):
            score += points
            signals.append(label)
    if "|" in body and "---" in body:
        score += 2
        signals.append("table")
    replacement_count = body.count("\ufffd")
    mojibake_count = sum(body.count(token) for token in ("锛", "銆", "鐨勫", "鍏徃"))
    if replacement_count:
        score -= 50
        signals.append(f"replacement_chars:{replacement_count}")
    if mojibake_count >= 3:
        score -= 20
        signals.append("possible_mojibake")
    return score, tuple(signals)


def _title_and_excerpt(body: str) -> tuple[str | None, str]:
    title: str | None = None
    paragraphs: list[str] = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("<!--"):
            continue
        if title is None and line.startswith("# "):
            title = line[2:].strip() or None
            continue
        if line.startswith("#") or line.startswith("|") or line.startswith("```"):
            continue
        normalized = _SPACE_RE.sub(" ", line).strip(" -*>")
        if normalized:
            paragraphs.append(normalized)
        if sum(len(item) for item in paragraphs) >= 420:
            break
    return title, " ".join(paragraphs)[:420]


def _body_identity(body: str, expected_symbol: str) -> tuple[str, tuple[str, ...]]:
    header_lines: list[str] = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        header_lines.append(line)
        if len(header_lines) >= 12 or sum(len(item) for item in header_lines) >= 1_500:
            break
    detected = sorted(
        {
            f"CN:{first or second}"
            for first, second in _CN_SYMBOL_RE.findall("\n".join(header_lines))
        }
    )
    if not detected:
        return "unverified", ()
    if expected_symbol not in detected:
        return "mismatch", tuple(detected)
    return "match", tuple(detected)


def _candidate_id(commit: str, entry: _TreeEntry) -> str:
    material = f"{commit}\0{entry.path}\0{entry.object_id}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:24]


class LegacyReportSalvager:
    """Read one frozen Git tag and copy one best historical report per company.

    The archive is deliberately outside the current-state workflow. It does not
    read or write company status, tasks, valuation, triggers, or the watchlist.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    def _git(self, *args: str, input_bytes: bytes | None = None) -> bytes:
        try:
            completed = subprocess.run(
                ["git", "-c", f"safe.directory={self.root.as_posix()}", *args],
                cwd=self.root,
                input=input_bytes,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        except OSError as exc:
            raise LegacySalvageError(f"cannot run git: {exc}") from exc
        if completed.returncode:
            message = completed.stderr.decode("utf-8", errors="replace").strip()
            raise LegacySalvageError(message or f"git exited with {completed.returncode}")
        return completed.stdout

    def _commit(self) -> str:
        raw = self._git("rev-parse", "--verify", f"refs/tags/{LEGACY_TAG}^{{commit}}")
        commit = raw.decode("ascii", errors="strict").strip()
        if not re.fullmatch(r"[0-9a-f]{40,64}", commit):
            raise LegacySalvageError(f"{LEGACY_TAG} did not resolve to a commit")
        return commit

    def _tree(self, commit: str) -> tuple[_TreeEntry, ...]:
        raw = self._git("ls-tree", "-r", "-z", "-l", commit, "--", "research/companies/CN")
        entries: list[_TreeEntry] = []
        for record in raw.split(b"\0"):
            if not record:
                continue
            try:
                header, raw_path = record.split(b"\t", 1)
                _mode, object_type, object_id, raw_size = header.split()
                path = raw_path.decode("utf-8")
                size = int(raw_size)
            except (ValueError, UnicodeDecodeError) as exc:
                raise LegacySalvageError("cannot parse the frozen legacy Git tree") from exc
            if object_type == b"blob":
                entries.append(_TreeEntry(path, object_id.decode("ascii"), size))
        return tuple(entries)

    def _blobs(self, object_ids: Sequence[str]) -> dict[str, bytes]:
        unique_ids = tuple(dict.fromkeys(object_ids))
        if not unique_ids:
            return {}
        request = "".join(f"{object_id}\n" for object_id in unique_ids).encode("ascii")
        raw = self._git("cat-file", "--batch", input_bytes=request)
        position = 0
        blobs: dict[str, bytes] = {}
        for requested_id in unique_ids:
            header_end = raw.find(b"\n", position)
            if header_end < 0:
                raise LegacySalvageError("truncated response from git cat-file")
            header = raw[position:header_end].split()
            position = header_end + 1
            if len(header) != 3 or header[1] != b"blob":
                raise LegacySalvageError(f"legacy blob is unavailable: {requested_id}")
            try:
                size = int(header[2])
            except ValueError as exc:
                raise LegacySalvageError("invalid blob size from git cat-file") from exc
            content_end = position + size
            if content_end >= len(raw) or raw[content_end : content_end + 1] != b"\n":
                raise LegacySalvageError("truncated legacy blob content")
            blobs[requested_id] = raw[position:content_end]
            position = content_end + 1
        return blobs

    @staticmethod
    def _report_entries(entries: Sequence[_TreeEntry]) -> tuple[_TreeEntry, ...]:
        return tuple(entry for entry in entries if _REPORT_PATH_RE.fullmatch(entry.path))

    @staticmethod
    def _meta_entries(entries: Sequence[_TreeEntry]) -> dict[str, _TreeEntry]:
        result: dict[str, _TreeEntry] = {}
        for entry in entries:
            match = re.fullmatch(r"research/companies/CN/(\d{6})/meta\.json", entry.path)
            if match:
                result[f"CN:{match.group(1)}"] = entry
        return result

    @staticmethod
    def _meta_identity(
        symbol: str, entry: _TreeEntry | None, blobs: Mapping[str, bytes]
    ) -> tuple[str | None, str | None]:
        if entry is None:
            return None, None
        try:
            payload = json.loads(blobs[entry.object_id].decode("utf-8"))
        except (KeyError, UnicodeDecodeError, json.JSONDecodeError):
            return None, None
        identity = payload.get("identity") if isinstance(payload, dict) else None
        name = identity.get("name") if isinstance(identity, dict) else None
        declared = identity.get("symbol") if isinstance(identity, dict) else None
        if not name and isinstance(payload, dict):
            name = payload.get("company_name") or payload.get("name")
        normalized_name = name.strip() if isinstance(name, str) and name.strip() else None
        normalized_symbol = declared.strip().upper() if isinstance(declared, str) else None
        if normalized_symbol == symbol:
            return normalized_name, normalized_symbol
        return normalized_name, normalized_symbol

    def _catalog(
        self,
    ) -> tuple[str, tuple[_TreeEntry, ...], dict[str, bytes], dict[str, _TreeEntry]]:
        commit = self._commit()
        entries = self._tree(commit)
        reports = self._report_entries(entries)
        meta_entries = self._meta_entries(entries)
        blobs = self._blobs(
            [
                *(entry.object_id for entry in reports),
                *(entry.object_id for entry in meta_entries.values()),
            ]
        )
        return commit, reports, blobs, meta_entries

    def _eligible_candidates(
        self,
    ) -> tuple[
        str,
        tuple[_TreeEntry, ...],
        dict[str, bytes],
        list[LegacyReportCandidate],
        list[dict[str, Any]],
    ]:
        commit, reports, blobs, meta_entries = self._catalog()
        reports_by_symbol: dict[str, list[_TreeEntry]] = {}
        for entry in reports:
            match = _REPORT_PATH_RE.fullmatch(entry.path)
            assert match is not None
            reports_by_symbol.setdefault(f"CN:{match.group('ticker')}", []).append(entry)

        candidates: list[LegacyReportCandidate] = []
        skipped: list[dict[str, Any]] = []
        for entry in reports:
            match = _REPORT_PATH_RE.fullmatch(entry.path)
            assert match is not None
            symbol = f"CN:{match.group('ticker')}"
            filename = match.group("filename")
            body = blobs[entry.object_id].decode("utf-8", errors="replace")
            kind = _kind(filename)
            if kind in {"excluded", "process_review"}:
                continue
            body_status, detected_symbols = _body_identity(body, symbol)
            name, declared_symbol = self._meta_identity(symbol, meta_entries.get(symbol), blobs)
            if body_status == "mismatch" or (
                declared_symbol is not None and declared_symbol != symbol
            ):
                skipped.append(
                    {
                        "symbol": symbol,
                        "legacy_path": entry.path,
                        "reason": "identity_mismatch",
                        "detected_symbols": detected_symbols
                        or ((declared_symbol,) if declared_symbol else ()),
                    }
                )
                continue
            if body_status != "match" and declared_symbol != symbol:
                skipped.append(
                    {
                        "symbol": symbol,
                        "legacy_path": entry.path,
                        "reason": "identity_unverified",
                        "detected_symbols": detected_symbols,
                    }
                )
                continue
            score, signals = _score(kind, body, entry.size)
            date_match = _DATE_RE.match(filename)
            report_date = date_match.group(1) if date_match else None
            newer_paths = tuple(
                sorted(
                    related.path
                    for related in reports_by_symbol[symbol]
                    if (related_match := _DATE_RE.match(Path(related.path).name))
                    and report_date is not None
                    and related_match.group(1) > report_date
                    and _kind(Path(related.path).name) not in {"excluded", "process_review"}
                )
            )
            title, excerpt = _title_and_excerpt(body)
            candidates.append(
                LegacyReportCandidate(
                    candidate_id=_candidate_id(commit, entry),
                    symbol=symbol,
                    name=name,
                    legacy_path=entry.path,
                    legacy_blob_oid=entry.object_id,
                    report_date=report_date,
                    report_kind=kind,
                    byte_size=entry.size,
                    score=score,
                    signals=signals,
                    identity_status=("match" if body_status == "match" else "metadata_match"),
                    detected_symbols=detected_symbols,
                    newer_report_paths=newer_paths,
                    title=title,
                    excerpt=excerpt,
                )
            )
        return commit, reports, blobs, candidates, skipped

    def list_candidates(self, *, limit: int = 200, min_score: int = 0) -> LegacyCandidateScan:
        """Rank eligible old reports without changing current research facts."""

        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise ValidationError("limit must be a positive integer")
        if isinstance(min_score, bool) or not isinstance(min_score, int):
            raise ValidationError("min_score must be an integer")
        commit, reports, _blobs, candidates, skipped = self._eligible_candidates()
        eligible = [candidate for candidate in candidates if candidate.score >= min_score]
        eligible.sort(
            key=lambda item: (
                -item.score,
                item.symbol,
                -(int((item.report_date or "0000-00-00").replace("-", ""))),
                item.legacy_path,
            )
        )
        return LegacyCandidateScan(
            tag=LEGACY_TAG,
            commit=commit,
            reports_scanned=len(reports),
            reports_excluded_for_current=0,
            identity_mismatches=tuple(sorted(skipped, key=lambda item: item["legacy_path"])),
            eligible_reports=len(eligible),
            candidates=tuple(eligible[:limit]),
        )

    def archive_best(self) -> LegacyArchiveResult:
        """Archive exactly one highest-quality legacy report for each verified company."""

        commit, reports, blobs, candidates, skipped_reports = self._eligible_candidates()
        by_symbol: dict[str, list[LegacyReportCandidate]] = {}
        for candidate in candidates:
            by_symbol.setdefault(candidate.symbol, []).append(candidate)
        selected = {
            symbol: max(
                company_candidates,
                key=lambda item: (
                    item.score,
                    item.report_date or "0000-00-00",
                    item.byte_size,
                    item.legacy_path,
                ),
            )
            for symbol, company_candidates in by_symbol.items()
        }

        planned: list[tuple[Path, str]] = []
        already_archived = 0
        for symbol, candidate in sorted(selected.items()):
            ticker = symbol.split(":", 1)[1]
            filename = f"{candidate.report_date}.md" if candidate.report_date else "undated.md"
            destination = self.root / "research" / "companies" / "CN" / ticker / "legacy" / filename
            raw_body = (
                blobs[candidate.legacy_blob_oid]
                .decode("utf-8", errors="replace")
                .replace("\r\n", "\n")
                .strip()
            )
            content = (
                "> **历史资料**\n"
                "> 仅供历史参考，不代表当前公司状态、估值或价格结论；"
                "系统不会用本文件生成研究状态、研究任务或价格监控。\n"
                f"> 来源：`{LEGACY_TAG}` / `{candidate.legacy_path}` / "
                f"`{candidate.legacy_blob_oid}`\n\n"
                f"{raw_body}\n"
            )
            existing = list(destination.parent.glob("*.md")) if destination.parent.is_dir() else []
            if existing:
                if len(existing) == 1 and existing[0] == destination:
                    if destination.read_text(encoding="utf-8") == content:
                        already_archived += 1
                        continue
                raise LegacySalvageError(
                    f"legacy archive already contains a different report for {symbol}"
                )
            planned.append((destination, content))

        for destination, content in planned:
            _atomic_write_text(destination, content)

        companies_seen = len(
            {
                f"CN:{match.group('ticker')}"
                for entry in reports
                if (match := _REPORT_PATH_RE.fullmatch(entry.path))
            }
        )
        skipped_by_symbol: dict[str, dict[str, Any]] = {}
        for item in skipped_reports:
            skipped_by_symbol.setdefault(item["symbol"], item)
        skipped_companies = tuple(
            skipped_by_symbol[symbol]
            for symbol in sorted(skipped_by_symbol.keys() - selected.keys())
        )
        return LegacyArchiveResult(
            tag=LEGACY_TAG,
            commit=commit,
            reports_scanned=len(reports),
            companies_seen=companies_seen,
            companies_archived=len(planned),
            already_archived=already_archived,
            companies_skipped=companies_seen - len(selected),
            skipped=skipped_companies,
        )


__all__ = [
    "LEGACY_TAG",
    "LegacyArchiveResult",
    "LegacyCandidateScan",
    "LegacyReportCandidate",
    "LegacyReportSalvager",
    "LegacySalvageError",
]
