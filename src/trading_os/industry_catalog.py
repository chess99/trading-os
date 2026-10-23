"""Read-only navigation over industry Markdown; never changes company state."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .research_assets.research_flow import ValidationError


def industry_catalog(root: Path, *, require_complete: bool = False) -> dict[str, Any]:
    root = root.resolve()
    directory = root / "research/industries/sectors"
    topics: list[dict[str, Any]] = []
    routes: dict[str, str] = {}
    for path in sorted(directory.glob("*.md")):
        if path.is_symlink() or path.resolve().parent != directory.resolve():
            raise ValidationError(f"industry document must be local: {path}")
        body = path.read_text(encoding="utf-8")
        title = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        line = re.search(r"^适用二级行业：\s*(.+)$", body, re.MULTILINE)
        if not title or not line:
            raise ValidationError(f"industry document lacks title or routing line: {path}")
        names = [name.strip().rstrip("。") for name in line[1].split("、")]
        if not all(names) or len(set(names)) != len(names):
            raise ValidationError(f"invalid industry routing line: {path}")
        for name in names:
            if name in routes:
                raise ValidationError(f"duplicate industry route: {name}")
            routes[name] = path.stem
        topics.append(
            {
                "id": path.stem,
                "title": title[1],
                "industries": names,
                "path": path.relative_to(root).as_posix(),
            }
        )
    alias_path = root / "research/industries/market-routes.json"
    if alias_path.exists():
        aliases = json.loads(alias_path.read_text(encoding="utf-8"))
        topic_ids = {topic["id"] for topic in topics}
        for name, topic in aliases.items():
            if topic not in topic_ids or (name in routes and routes[name] != topic):
                raise ValidationError(f"invalid cross-market industry route: {name}")
            routes[name] = topic
    states = []
    for market in ("cn-a", "hk", "us"):
        path = root / f"coverage/{market}/research_state.jsonl"
        if path.exists():
            states.extend(
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            )
        pool_path = root / f"screening/{market}/value-quality/pool.json"
        if market != "cn-a" and pool_path.exists():
            states.extend(json.loads(pool_path.read_text(encoding="utf-8"))["companies"])
    combined = {}
    for row in states:
        combined[row["symbol"]] = {**combined.get(row["symbol"], {}), **row}
    states = list(combined.values())
    named = {row["industry"] for row in states if row.get("industry")}
    missing = sorted(named - routes.keys())
    if require_complete and missing:
        raise ValidationError("industries without a research framework: " + ", ".join(missing))
    if require_complete and not topics:
        raise ValidationError("industry catalog is empty")
    return {
        "topics": topics,
        "routes": routes,
        "unmapped_industries": missing,
        "named_industry_count": len(named),
        "unclassified_companies": [
            {"symbol": row["symbol"], "name": row.get("name")}
            for row in states
            if not row.get("industry")
        ],
        "scope": "经营框架覆盖与原证抽样深度不同；逐篇参阅资料和局限。",
    }
