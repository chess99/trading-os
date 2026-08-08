from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .research_flow import (
    PriceLevel,
    ResearchFlow,
    ResearchFlowError,
    ResearchResult,
    ScreenDecision,
    ValidationError,
    ValueRange,
)

LEGACY_TAG = "pre-simplification-20260808"

_REPORT_PATH_RE = re.compile(
    r"^research/companies/CN/(?P<ticker>\d{6})/reports/(?P<filename>[^/]+\.md)$"
)
_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-")
_URL_RE = re.compile(r'https?://[^\s)>\]}"\']+')
_SPACE_RE = re.compile(r"\s+")
_CN_SYMBOL_RE = re.compile(
    r"(?:CN\s*[:：]\s*(\d{6})|(?<!\d)(\d{6})\s*\.(?:SZ|SH|BJ)\b)",
    re.IGNORECASE,
)


class LegacySalvageError(ResearchFlowError):
    """Raised when the fixed legacy snapshot cannot be read or safely migrated."""


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
class LegacySalvageResult:
    tag: str
    commit: str
    batch_id: str
    migrated: tuple[dict[str, Any], ...]
    skipped: tuple[dict[str, Any], ...]


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LegacySalvageError(f"{label} must be a non-blank string")
    return value.strip()


def _kind(filename: str) -> str:
    lowered = filename.lower()
    if "failed" in lowered:
        return "failed"
    if "superseded" in lowered or "archived" in lowered:
        return "superseded"
    if "investment-committee" in lowered or "committee-review" in lowered:
        return "investment_committee"
    if "chatgpt" in lowered:
        return "chatgpt_deep_research"
    if "deep-review" in lowered:
        return "deep_review"
    if "followup" in lowered:
        return "followup"
    if any(word in lowered for word in ("refresh", "update", "supplement", "monitoring")):
        return "update"
    if "initial-research" in lowered:
        return "modern_initial_research"
    if "rapid-triage" in lowered:
        return "rapid_triage"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}-initial\.md", lowered):
        return "bulk_initial"
    return "other"


_KIND_SCORE = {
    "investment_committee": 100,
    "chatgpt_deep_research": 95,
    "deep_review": 90,
    "followup": 80,
    "update": 70,
    "modern_initial_research": 65,
    "other": 40,
    "rapid_triage": 25,
    "bulk_initial": 5,
    "superseded": -100,
    "failed": -100,
}


def _score(kind: str, body: str, byte_size: int) -> tuple[int, tuple[str, ...]]:
    signals = [f"kind:{kind}", f"length:{byte_size}"]
    score = _KIND_SCORE[kind]
    score += min(15, byte_size // 4_000)

    url_count = len(_URL_RE.findall(body))
    if url_count:
        score += min(5, url_count)
        signals.append(f"urls:{url_count}")

    markers = (
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
    excerpt = " ".join(paragraphs)
    return title, excerpt[:420]


def _body_identity(body: str, expected_symbol: str) -> tuple[str, tuple[str, ...]]:
    """Check only the title/header area, avoiding peer codes deep in a report."""

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
    """Read one frozen Git tag and migrate only explicitly reviewed condensations.

    Candidate discovery is one local, batched Git read. It never creates company
    research tasks. Applying decisions deliberately goes through the current
    :class:`ResearchFlow` contract; no legacy state, queue or report tree is
    restored into the working tree.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    def _git(self, *args: str, input_bytes: bytes | None = None) -> bytes:
        command = [
            "git",
            "-c",
            f"safe.directory={self.root.as_posix()}",
            *args,
        ]
        try:
            completed = subprocess.run(
                command,
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
        raw = self._git(
            "ls-tree",
            "-r",
            "-z",
            "-l",
            commit,
            "--",
            "research/companies/CN",
        )
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

    def _current_symbols(self) -> set[str]:
        base = self.root / "research" / "companies" / "CN"
        if not base.is_dir():
            return set()
        return {
            f"CN:{path.parent.name}"
            for path in base.glob("*/current.md")
            if re.fullmatch(r"\d{6}", path.parent.name) and path.is_file()
        }

    def _meta_identities(
        self,
        entries: Sequence[_TreeEntry],
        blobs: Mapping[str, bytes],
        symbols: set[str],
    ) -> dict[str, tuple[str | None, str | None]]:
        meta_by_symbol: dict[str, _TreeEntry] = {}
        for entry in entries:
            match = re.fullmatch(
                r"research/companies/CN/(\d{6})/meta\.json", entry.path
            )
            if match and f"CN:{match.group(1)}" in symbols:
                meta_by_symbol[f"CN:{match.group(1)}"] = entry
        identities: dict[str, tuple[str | None, str | None]] = {}
        for symbol, entry in meta_by_symbol.items():
            try:
                payload = json.loads(blobs[entry.object_id].decode("utf-8"))
            except (KeyError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            identity = payload.get("identity") if isinstance(payload, dict) else None
            name = identity.get("name") if isinstance(identity, dict) else None
            declared_symbol = identity.get("symbol") if isinstance(identity, dict) else None
            if not name and isinstance(payload, dict):
                name = payload.get("company_name") or payload.get("name")
            normalized_name = name.strip() if isinstance(name, str) and name.strip() else None
            normalized_symbol = (
                declared_symbol.strip().upper()
                if isinstance(declared_symbol, str) and declared_symbol.strip()
                else None
            )
            identities[symbol] = (normalized_name, normalized_symbol)
        return identities

    def list_candidates(
        self,
        *,
        limit: int = 200,
        min_score: int = 40,
    ) -> LegacyCandidateScan:
        """Rank old Markdown reports without consulting or mutating old workflow state."""

        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise ValidationError("limit must be a positive integer")
        if isinstance(min_score, bool) or not isinstance(min_score, int):
            raise ValidationError("min_score must be an integer")

        commit = self._commit()
        entries = self._tree(commit)
        reports = self._report_entries(entries)
        current_symbols = self._current_symbols()
        eligible_entries: list[_TreeEntry] = []
        excluded = 0
        for entry in reports:
            match = _REPORT_PATH_RE.fullmatch(entry.path)
            assert match is not None
            if f"CN:{match.group('ticker')}" in current_symbols:
                excluded += 1
            else:
                eligible_entries.append(entry)

        report_blobs = self._blobs([entry.object_id for entry in eligible_entries])
        reports_by_symbol: dict[str, list[_TreeEntry]] = {}
        for entry in eligible_entries:
            match = _REPORT_PATH_RE.fullmatch(entry.path)
            assert match is not None
            reports_by_symbol.setdefault(f"CN:{match.group('ticker')}", []).append(entry)

        ranked: list[
            tuple[
                _TreeEntry,
                str,
                str,
                int,
                tuple[str, ...],
                str,
                tuple[str, ...],
                tuple[str, ...],
                str | None,
                str,
            ]
        ] = []
        identity_mismatches: list[dict[str, Any]] = []
        for entry in eligible_entries:
            match = _REPORT_PATH_RE.fullmatch(entry.path)
            assert match is not None
            body = report_blobs[entry.object_id].decode("utf-8", errors="replace")
            kind = _kind(match.group("filename"))
            score, signals = _score(kind, body, entry.size)
            symbol = f"CN:{match.group('ticker')}"
            identity_status, detected_symbols = _body_identity(body, symbol)
            if identity_status == "mismatch":
                identity_mismatches.append(
                    {
                        "symbol": symbol,
                        "legacy_path": entry.path,
                        "detected_symbols": detected_symbols,
                        "reason": "identity_mismatch",
                    }
                )
                continue
            if score < min_score:
                continue
            title, excerpt = _title_and_excerpt(body)
            report_date_match = _DATE_RE.match(match.group("filename"))
            report_date = report_date_match.group(1) if report_date_match else None
            newer_paths: list[str] = []
            if report_date:
                for related in reports_by_symbol[symbol]:
                    related_match = _DATE_RE.match(Path(related.path).name)
                    if (
                        related_match
                        and related_match.group(1) > report_date
                        and _kind(Path(related.path).name) not in {"failed", "superseded"}
                    ):
                        newer_paths.append(related.path)
            newer_paths.sort()
            if newer_paths:
                signals = (*signals, f"newer_reports:{len(newer_paths)}")
            ranked.append(
                (
                    entry,
                    symbol,
                    kind,
                    score,
                    signals,
                    identity_status,
                    detected_symbols,
                    tuple(newer_paths),
                    title,
                    excerpt,
                )
            )
        ranked.sort(key=lambda item: (-item[3], item[1], item[0].path))
        selected = ranked[:limit]

        selected_symbols = {item[1] for item in selected}
        meta_entries = [
            entry
            for entry in entries
            if re.fullmatch(r"research/companies/CN/\d{6}/meta\.json", entry.path)
            and f"CN:{entry.path.split('/')[3]}" in selected_symbols
        ]
        meta_blobs = self._blobs([entry.object_id for entry in meta_entries])
        identities = self._meta_identities(meta_entries, meta_blobs, selected_symbols)

        candidates: list[LegacyReportCandidate] = []
        for (
            entry,
            symbol,
            kind,
            score,
            signals,
            identity_status,
            detected_symbols,
            newer_paths,
            title,
            excerpt,
        ) in selected:
            name, declared_symbol = identities.get(symbol, (None, None))
            if declared_symbol is not None and declared_symbol != symbol:
                identity_mismatches.append(
                    {
                        "symbol": symbol,
                        "legacy_path": entry.path,
                        "detected_symbols": (declared_symbol,),
                        "reason": "metadata_identity_mismatch",
                    }
                )
                continue
            if identity_status == "unverified" and declared_symbol == symbol:
                identity_status = "metadata_match"
            date_match = _DATE_RE.match(Path(entry.path).name)
            candidates.append(
                LegacyReportCandidate(
                    candidate_id=_candidate_id(commit, entry),
                    symbol=symbol,
                    name=name,
                    legacy_path=entry.path,
                    legacy_blob_oid=entry.object_id,
                    report_date=date_match.group(1) if date_match else None,
                    report_kind=kind,
                    byte_size=entry.size,
                    score=score,
                    signals=signals,
                    identity_status=identity_status,
                    detected_symbols=detected_symbols,
                    newer_report_paths=newer_paths,
                    title=title,
                    excerpt=excerpt,
                )
            )
        return LegacyCandidateScan(
            tag=LEGACY_TAG,
            commit=commit,
            reports_scanned=len(reports),
            reports_excluded_for_current=excluded,
            identity_mismatches=tuple(
                sorted(identity_mismatches, key=lambda item: item["legacy_path"])
            ),
            eligible_reports=len(ranked),
            candidates=tuple(candidates),
        )

    @staticmethod
    def _result(payload: Mapping[str, Any]) -> ResearchResult:
        raw_range = payload.get("value_range")
        if not isinstance(raw_range, Mapping):
            raise LegacySalvageError("migrate result requires value_range")
        raw_levels = payload.get("price_levels") or []
        if not isinstance(raw_levels, list) or not all(
            isinstance(item, Mapping) for item in raw_levels
        ):
            raise LegacySalvageError("result.price_levels must be an array of objects")
        return ResearchResult(
            symbol=payload["symbol"],
            name=payload.get("name"),
            outcome=payload["outcome"],
            summary=payload["summary"],
            key_logic=payload.get("key_logic") or (),
            risks=payload.get("risks") or (),
            value_range=ValueRange(
                low=raw_range["low"],
                high=raw_range["high"],
                currency=raw_range.get("currency", "CNY"),
            ),
            price_levels=tuple(
                PriceLevel(
                    id=item["id"],
                    label=item["label"],
                    threshold=item["threshold"],
                    rearm_above=item.get("rearm_above"),
                )
                for item in raw_levels
            ),
            buy_below=payload.get("buy_below"),
            rearm_above=payload.get("rearm_above"),
            event_triggers=payload.get("event_triggers") or (),
            source_urls=payload.get("source_urls") or (),
            report_markdown=payload.get("report_markdown"),
        )

    def apply_decisions(
        self,
        payload: Mapping[str, Any],
        *,
        at: str | None = None,
    ) -> LegacySalvageResult:
        """Write only explicitly selected, newly condensed modern research results."""

        if not isinstance(payload, Mapping):
            raise LegacySalvageError("legacy salvage input must be a JSON object")
        batch_id = _text(payload.get("batch_id"), "batch_id")
        raw_decisions = payload.get("decisions")
        if not isinstance(raw_decisions, list) or not raw_decisions:
            raise LegacySalvageError("decisions must be a non-empty array")
        if not all(isinstance(item, Mapping) for item in raw_decisions):
            raise LegacySalvageError("each salvage decision must be an object")

        commit = self._commit()
        entries = self._tree(commit)
        reports = self._report_entries(entries)
        by_path = {entry.path: entry for entry in reports}
        reports_by_symbol: dict[str, list[_TreeEntry]] = {}
        meta_by_symbol: dict[str, _TreeEntry] = {}
        for entry in reports:
            match = _REPORT_PATH_RE.fullmatch(entry.path)
            assert match is not None
            reports_by_symbol.setdefault(f"CN:{match.group('ticker')}", []).append(entry)
        for entry in entries:
            meta_match = re.fullmatch(
                r"research/companies/CN/(\d{6})/meta\.json", entry.path
            )
            if meta_match:
                meta_by_symbol[f"CN:{meta_match.group(1)}"] = entry
        current_symbols = self._current_symbols()
        selected: list[tuple[Mapping[str, Any], _TreeEntry, ResearchResult]] = []
        skipped: list[dict[str, Any]] = []
        seen_candidates: set[str] = set()
        seen_symbols: set[str] = set()
        selected_blob_ids: list[str] = []

        for decision in raw_decisions:
            candidate_id = _text(decision.get("candidate_id"), "candidate_id")
            symbol = _text(decision.get("symbol"), "symbol").upper()
            legacy_path = _text(decision.get("legacy_path"), "legacy_path")
            legacy_blob_oid = _text(decision.get("legacy_blob_oid"), "legacy_blob_oid")
            action = _text(decision.get("action"), "action")
            if candidate_id in seen_candidates:
                raise LegacySalvageError(f"duplicate candidate decision: {candidate_id}")
            if symbol in seen_symbols:
                raise LegacySalvageError(f"only one salvage decision is allowed for {symbol}")
            seen_candidates.add(candidate_id)
            seen_symbols.add(symbol)

            entry = by_path.get(legacy_path)
            match = _REPORT_PATH_RE.fullmatch(legacy_path)
            if entry is None or match is None:
                raise LegacySalvageError(f"legacy report is not in {LEGACY_TAG}: {legacy_path}")
            expected_symbol = f"CN:{match.group('ticker')}"
            expected_candidate = _candidate_id(commit, entry)
            if symbol != expected_symbol:
                raise LegacySalvageError("decision symbol does not match legacy report path")
            if legacy_blob_oid != entry.object_id or candidate_id != expected_candidate:
                raise LegacySalvageError(f"legacy candidate identity changed: {legacy_path}")
            if action == "skip":
                reason = _text(decision.get("reason"), "skip reason")
                skipped.append(
                    {
                        "candidate_id": candidate_id,
                        "symbol": symbol,
                        "legacy_path": legacy_path,
                        "reason": reason,
                    }
                )
                continue
            if action != "migrate":
                raise LegacySalvageError("action must be migrate or skip")
            if symbol in current_symbols:
                raise LegacySalvageError(f"current.md already exists for {symbol}")
            reason = _text(decision.get("reason"), "migrate reason")
            selected_date_match = _DATE_RE.match(Path(entry.path).name)
            required_review_paths = {entry.path}
            if selected_date_match:
                selected_date = selected_date_match.group(1)
                required_review_paths.update(
                    related.path
                    for related in reports_by_symbol[symbol]
                    if (related_date := _DATE_RE.match(Path(related.path).name))
                    and related_date.group(1) > selected_date
                    and _kind(Path(related.path).name) not in {"failed", "superseded"}
                )
            raw_reviewed_paths = decision.get("reviewed_legacy_paths")
            if not isinstance(raw_reviewed_paths, list) or not all(
                isinstance(item, str) and item.strip() for item in raw_reviewed_paths
            ):
                raise LegacySalvageError(
                    "migrate decision requires reviewed_legacy_paths"
                )
            reviewed_paths = {item.strip() for item in raw_reviewed_paths}
            missing_reviews = sorted(required_review_paths - reviewed_paths)
            if missing_reviews:
                raise LegacySalvageError(
                    "migrate decision has not reviewed the selected or newer reports: "
                    + ", ".join(missing_reviews)
                )
            unknown_reviews = sorted(reviewed_paths - set(by_path))
            if unknown_reviews:
                raise LegacySalvageError(
                    "reviewed_legacy_paths contains paths outside the frozen report tree: "
                    + ", ".join(unknown_reviews)
                )
            foreign_reviews = sorted(
                path
                for path in reviewed_paths
                if (review_match := _REPORT_PATH_RE.fullmatch(path))
                and f"CN:{review_match.group('ticker')}" != symbol
            )
            if foreign_reviews:
                raise LegacySalvageError(
                    "reviewed_legacy_paths contains another company's reports: "
                    + ", ".join(foreign_reviews)
                )
            result_payload = decision.get("result")
            if not isinstance(result_payload, Mapping):
                raise LegacySalvageError("migrate decision requires a result object")
            try:
                result = self._result(result_payload)
                normalized = ResearchFlow._normalized_result(result)
            except (KeyError, TypeError, ValueError) as exc:
                raise LegacySalvageError(f"invalid migrate result for {symbol}: {exc}") from exc
            if normalized["symbol"] != symbol:
                raise LegacySalvageError("result symbol does not match selected candidate")
            if normalized["outcome"] != "researched":
                raise LegacySalvageError("legacy salvage only accepts researched results")
            selected.append((dict(decision, reason=reason), entry, result))
            selected_blob_ids.append(entry.object_id)

        if not selected:
            return LegacySalvageResult(
                tag=LEGACY_TAG,
                commit=commit,
                batch_id=batch_id,
                migrated=(),
                skipped=tuple(skipped),
            )

        selected_meta_entries = [
            meta_by_symbol[result.symbol]
            for _decision, _entry, result in selected
            if result.symbol in meta_by_symbol
        ]
        old_blobs = self._blobs(
            [*selected_blob_ids, *(entry.object_id for entry in selected_meta_entries)]
        )
        for _decision, entry, result in selected:
            old_body = old_blobs[entry.object_id].decode("utf-8", errors="replace")
            identity_status, detected_symbols = _body_identity(old_body, result.symbol)
            if identity_status == "mismatch":
                raise LegacySalvageError(
                    f"identity_mismatch for {entry.path}: " + ", ".join(detected_symbols)
                )
            identity_verified = identity_status == "match"
            meta_entry = meta_by_symbol.get(result.symbol)
            if meta_entry is not None:
                identities = self._meta_identities(
                    [meta_entry], old_blobs, {result.symbol}
                )
                _name, declared_symbol = identities.get(result.symbol, (None, None))
                if declared_symbol is not None and declared_symbol != result.symbol:
                    raise LegacySalvageError(
                        f"metadata_identity_mismatch for {entry.path}: {declared_symbol}"
                    )
                identity_verified = identity_verified or declared_symbol == result.symbol
            if not identity_verified:
                raise LegacySalvageError(
                    f"identity_unverified for {entry.path}; title/header or metadata "
                    "must identify the path symbol"
                )
            new_body = (result.report_markdown or "").replace("\r\n", "\n").strip()
            if new_body == old_body.replace("\r\n", "\n").strip():
                raise LegacySalvageError(
                    f"raw legacy report cannot be restored as current.md: {entry.path}"
                )

        flow = ResearchFlow(self.root)
        flow.validate()
        if flow.list_tasks():
            raise LegacySalvageError(
                "legacy salvage requires an empty research queue; "
                "finish or requeue current work first"
            )
        trigger_key = f"screen:legacy-salvage:{batch_id}"
        selected_symbols = {result.symbol for _decision, _entry, result in selected}
        already_processed = sorted(
            state["symbol"]
            for state in flow.read_states()
            if state["symbol"] in selected_symbols
            and trigger_key in set(state.get("processed_triggers") or [])
        )
        if already_processed:
            raise LegacySalvageError(
                "salvage batch was already processed for: " + ", ".join(already_processed)
            )

        timestamp = at or payload.get("at")
        screening = flow.apply_screening(
            [
                ScreenDecision(
                    symbol=result.symbol,
                    name=result.name,
                    route="research_now",
                    reason=(
                        f"旧研报打捞 {entry.path}@{entry.object_id}: "
                        f"{decision['reason']}"
                    ),
                )
                for decision, entry, result in selected
            ],
            screen_id=f"legacy-salvage:{batch_id}",
            mode="event",
            at=timestamp,
        )
        if screening.deduplicated or len(screening.enqueued_tasks) != len(selected):
            raise LegacySalvageError("one or more salvage candidates were already processed")
        dispatched = flow.dispatch_tasks(limit=len(selected), at=timestamp)
        tasks_by_symbol = {task.symbol: task for task in dispatched}
        if set(tasks_by_symbol) != {result.symbol for _, _, result in selected}:
            raise LegacySalvageError("could not exclusively dispatch the salvage batch")

        migrated: list[dict[str, Any]] = []
        for _decision, entry, result in selected:
            state = flow.apply_result(
                result,
                task_id=tasks_by_symbol[result.symbol].task_id,
                at=timestamp,
            )
            migrated.append(
                {
                    "candidate_id": _candidate_id(commit, entry),
                    "symbol": result.symbol,
                    "legacy_path": entry.path,
                    "legacy_blob_oid": entry.object_id,
                    "report_path": state["report_path"],
                }
            )
        flow.validate()
        return LegacySalvageResult(
            tag=LEGACY_TAG,
            commit=commit,
            batch_id=batch_id,
            migrated=tuple(migrated),
            skipped=tuple(skipped),
        )


__all__ = [
    "LEGACY_TAG",
    "LegacyCandidateScan",
    "LegacyReportCandidate",
    "LegacyReportSalvager",
    "LegacySalvageError",
    "LegacySalvageResult",
]
