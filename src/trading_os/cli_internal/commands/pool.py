from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from ...paths import repo_root


def _pool_path() -> Path:
    return repo_root() / "artifacts" / "watchlist" / "pool.json"


def _stock_names_path() -> Path:
    return repo_root() / "data" / "stock_names.json"


def _empty_pool() -> dict:
    return {
        "last_updated": "",
        "pools": {
            "canslim": {"candidates": [], "watchlist": [], "ready": []},
            "elder": {"candidates": [], "watchlist": [], "ready": []},
            "value": {"candidates": [], "watchlist": [], "ready": []},
        },
        "exited": [],
    }


def _load_pool(path: Path | None = None) -> dict:
    import json

    p = path or _pool_path()
    if not p.exists():
        return _empty_pool()
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"pool.json 解析失败: {e}", file=sys.stderr)
        print(f"请检查文件: {p}", file=sys.stderr)
        raise SystemExit(1)


def _save_pool(data: dict, path: Path | None = None) -> None:
    import json

    p = path or _pool_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _tracking_path(symbol: str, tracking_dir) -> Path:
    prefix = symbol.replace(":", "_")
    for p in tracking_dir.glob(f"{prefix}*.md"):
        return p
    data = _load_pool()
    name = ""
    for sys_pools in data.get("pools", {}).values():
        for tier_items in sys_pools.values():
            for item in tier_items:
                if item.get("symbol") == symbol:
                    name = item.get("name") or ""
                    break
    if not name:
        for item in data.get("exited", []):
            if item.get("symbol") == symbol:
                name = item.get("name") or ""
                break
    fname = f"{prefix}_{name}.md" if name else f"{prefix}.md"
    return tracking_dir / fname


def _append_tracking(symbol: str, note: str) -> None:
    tracking_dir = repo_root() / "artifacts" / "watchlist" / "tracking"
    tracking_dir.mkdir(parents=True, exist_ok=True)
    fpath = _tracking_path(symbol, tracking_dir)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entry = f"\n### {today}\n{note}\n"
    with open(fpath, "a", encoding="utf-8") as f:
        f.write(entry)


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _scan_candidate_to_pool_entry(
    item: dict,
    *,
    effective_date: str | None,
    signal_date: str | None,
    scan_job_id: str | None,
    scan_file: str | None,
    existing: dict | None = None,
) -> dict:
    score = item.get("score")
    rank = item.get("rank")
    reason_bits = ["scan candidate"]
    if score is not None:
        reason_bits.append(f"score={score}")
    if rank is not None:
        reason_bits.append(f"rank={rank}")
    entry = {
        "symbol": item["symbol"],
        "name": item.get("name", ""),
        "entered_at": (existing or {}).get("entered_at", _today_utc()),
        "entry_reason": " | ".join(reason_bits),
        "trigger_price": (existing or {}).get("trigger_price", item.get("trigger_price")),
        "notes": (existing or {}).get("notes", ""),
        "score": score,
        "scan_effective_date": effective_date,
        "scan_signal_date": signal_date,
        "scan_job_id": scan_job_id,
        "scan_file": scan_file,
    }
    if existing:
        for key in ("research_file",):
            if key in existing:
                entry[key] = existing[key]
    return entry


def sync_candidates_from_scan(
    *,
    system: str,
    scan_data: dict,
    apply: bool = False,
    scan_file: str | None = None,
    scan_job_id: str | None = None,
    pool_path: Path | None = None,
) -> dict:
    data = _load_pool(pool_path)
    effective_date = scan_data.get("effective_date")
    signal_date = scan_data.get("signal_date") or scan_data.get("scan_date")
    pool_system = data["pools"].setdefault(system, {"candidates": [], "watchlist": [], "ready": []})
    active_non_candidates = {
        item["symbol"]
        for tier in ("watchlist", "ready")
        for item in pool_system.get(tier, [])
    }
    exited_symbols = {
        item["symbol"]
        for item in data.get("exited", [])
        if item.get("system") == system
    }
    old_candidates = {item["symbol"]: item for item in pool_system.get("candidates", [])}
    scan_candidates = {item["symbol"]: item for item in scan_data.get("candidates", [])}

    retained_symbols = []
    blocked_reentry = []
    for symbol in scan_candidates:
        if symbol in active_non_candidates:
            retained_symbols.append(symbol)
        elif symbol in exited_symbols:
            blocked_reentry.append(symbol)

    next_candidates = []
    for symbol, item in scan_candidates.items():
        if symbol in active_non_candidates or symbol in exited_symbols:
            continue
        next_candidates.append(
            _scan_candidate_to_pool_entry(
                item,
                effective_date=effective_date,
                signal_date=signal_date,
                scan_job_id=scan_job_id,
                scan_file=scan_file,
                existing=old_candidates.get(symbol),
            )
        )
    next_candidates.sort(key=lambda x: (-float(x.get("score") or 0), x["symbol"]))

    summary = {
        "effective_date": effective_date,
        "signal_date": signal_date,
        "scan_candidates": len(scan_candidates),
        "scan_candidates_total": int(scan_data.get("candidates_total") or len(scan_candidates)),
        "previous_candidates": len(old_candidates),
        "next_candidates": len(next_candidates),
        "eligible_after_policy_filter": len(next_candidates) + len(retained_symbols),
        "actually_written": len(next_candidates),
        "added": sorted([sym for sym in scan_candidates if sym not in old_candidates and sym not in active_non_candidates and sym not in exited_symbols]),
        "dropped": sorted([sym for sym in old_candidates if sym not in scan_candidates]),
        "retained": sorted([sym for sym in scan_candidates if sym in old_candidates]),
        "already_active": sorted(retained_symbols),
        "blocked_reentry": sorted(blocked_reentry),
        "updated": False,
    }
    if apply:
        pool_system["candidates"] = next_candidates
        data["last_updated"] = _today_utc()
        _save_pool(data, pool_path)
        summary["updated"] = True
    return summary


def _cmd_pool(ns: argparse.Namespace) -> int:
    sub = ns.pool_cmd
    if sub == "list":
        return _pool_list(ns)
    if sub == "status":
        return _pool_status(ns)
    if sub == "add":
        return _pool_add(ns)
    if sub == "remove":
        return _pool_remove(ns)
    if sub == "promote":
        return _pool_promote(ns)
    if sub == "update":
        return _pool_update(ns)
    if sub == "sync-from-scan":
        return _pool_sync_from_scan(ns)
    print(f"未知 pool 子命令: {sub}", file=sys.stderr)
    return 1


def _pool_list(ns: argparse.Namespace) -> int:
    data = _load_pool()
    systems = [ns.system] if getattr(ns, "system", None) else ["canslim", "elder", "value"]
    tiers = [ns.tier] if getattr(ns, "tier", None) else ["candidates", "watchlist", "ready"]
    total = 0
    for sys_name in systems:
        pool = data["pools"].get(sys_name, {})
        for tier in tiers:
            items = pool.get(tier, [])
            if not items:
                continue
            print(f"\n【{sys_name.upper()} / {tier}】({len(items)} 只)")
            for item in items:
                status = item.get("status", "—")
                trigger = item.get("trigger_price")
                trigger_str = f"  触发价:{trigger}" if trigger else ""
                name = item.get("name") or ""
                print(f"  {item['symbol']:<18} {name:<10} [{status}]{trigger_str}")
                if getattr(ns, "verbose", False) and item.get("notes"):
                    print(f"    └ {item['notes']}")
            total += len(items)
    print(f"\n合计: {total} 只在池")
    return 0


def _pool_status(ns: argparse.Namespace) -> int:
    import io

    buf = io.StringIO()
    data = _load_pool()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def w(line: str = "") -> None:
        buf.write(line + "\n")

    w(f"# 自选池状态报告 — {today}")
    w()
    total_watching = 0
    for sys_name in ["canslim", "elder", "value"]:
        pool = data["pools"].get(sys_name, {})
        n = sum(len(pool.get(t, [])) for t in ["candidates", "watchlist", "ready"])
        total_watching += n
    w(f"**在池标的：{total_watching} 只 | 已移出：{len(data.get('exited', []))} 只**")
    w()

    ready_items = []
    for sys_name in ["canslim", "elder", "value"]:
        for item in data["pools"].get(sys_name, {}).get("ready", []):
            ready_items.append((sys_name, item))
    if ready_items:
        w("## ⚡ 需要立即处理（已进入 ready 层）")
        for sys_name, item in ready_items:
            w(f"- **{item['symbol']} {item['name']}** [{sys_name.upper()}]")
            w(f"  触发价:{item.get('trigger_price')}  止损:{item.get('stop_loss')}  目标仓位:{item.get('target_position_pct')}%")
        w()

    for sys_name in ["canslim", "elder", "value"]:
        pool = data["pools"].get(sys_name, {})
        items_wl = pool.get("watchlist", [])
        items_cd = pool.get("candidates", [])
        if not items_wl and not items_cd:
            continue
        w(f"## {sys_name.upper()} 体系")
        if items_wl:
            w(f"### 观察池（{len(items_wl)} 只）")
            for item in items_wl:
                w(f"- **{item['symbol']} {item['name']}** [{item.get('status', '—')}]")
                w(f"  触发价:{item.get('trigger_price')}  目标仓位:{item.get('target_position_pct')}%")
                if item.get("notes"):
                    w(f"  _{item['notes']}_")
        if items_cd:
            w(f"### 候选池（{len(items_cd)} 只，待深度研究）")
            for item in items_cd:
                w(f"- {item['symbol']} {item['name']}  触发价:{item.get('trigger_price')}")
        w()

    exited = data.get("exited", [])
    if exited:
        w(f"## 已移出（{len(exited)} 只）")
        for item in exited[-5:]:
            w(f"- {item['symbol']} {item['name']} — {item.get('exit_reason', '')[:60]}")
        w()

    report = buf.getvalue()
    output_path = getattr(ns, "output", None)
    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report, encoding="utf-8")
        print(f"报告已写入: {output_path}")
    else:
        print(report)
    return 0


def _pool_add(ns: argparse.Namespace) -> int:
    import json as _json

    data = _load_pool()
    system = ns.system
    tier = getattr(ns, "tier", "candidates")
    symbol = ns.symbol
    today = _today_utc()
    pool = data["pools"].setdefault(system, {"candidates": [], "watchlist": [], "ready": []})
    for t in ["candidates", "watchlist", "ready"]:
        for item in pool.get(t, []):
            if item["symbol"] == symbol:
                print(f"{symbol} 已在 {system}/{t} 中", file=sys.stderr)
                return 1

    explicit_name = getattr(ns, "name", None)
    if explicit_name is not None:
        name = explicit_name
    else:
        names_path = _stock_names_path()
        if names_path.exists():
            name_map = _json.loads(names_path.read_text(encoding="utf-8"))
            name = name_map.get(symbol, "")
        else:
            name = ""

    entry: dict = {
        "symbol": symbol,
        "name": name,
        "entered_at": today,
        "entry_reason": getattr(ns, "reason", ""),
        "trigger_price": getattr(ns, "trigger", None),
        "notes": getattr(ns, "notes", ""),
    }
    if tier in ("watchlist", "ready"):
        entry.update({
            "research_file": getattr(ns, "research", None),
            "stop_loss": getattr(ns, "stop_loss", None),
            "target_position_pct": getattr(ns, "position_pct", None),
            "status": "waiting_market",
            "last_checked": today,
        })
    else:
        entry["score"] = getattr(ns, "score", None)

    pool.setdefault(tier, []).append(entry)
    data["last_updated"] = today
    _save_pool(data)
    if tier in ("watchlist", "ready"):
        _append_tracking(symbol, f"入池：{system}/{tier}\n- 原因：{entry['entry_reason']}\n- 触发价：{entry['trigger_price']}")
    print(f"已添加 {symbol} → {system}/{tier}")
    return 0


def _pool_remove(ns: argparse.Namespace) -> int:
    data = _load_pool()
    symbol = ns.symbol
    system = getattr(ns, "system", None)
    today = _today_utc()
    reason = getattr(ns, "reason", "")
    removed = []
    removed_tiers: list[str] = []
    systems_to_check = [system] if system else list(data["pools"].keys())
    for sys_name in systems_to_check:
        pool = data["pools"].get(sys_name, {})
        for tier in ["candidates", "watchlist", "ready"]:
            before = pool.get(tier, [])
            after = [x for x in before if x["symbol"] != symbol]
            if len(after) < len(before):
                removed_item = next(x for x in before if x["symbol"] == symbol)
                pool[tier] = after
                data["exited"].append({
                    "symbol": symbol,
                    "name": removed_item.get("name", symbol),
                    "system": sys_name,
                    "exited_at": today,
                    "exit_reason": reason,
                    "duration_days": (
                        datetime.now(timezone.utc).date() -
                        datetime.fromisoformat(removed_item.get("entered_at", today)).date()
                    ).days,
                })
                removed.append(f"{sys_name}/{tier}")
                removed_tiers.append(tier)
    if not removed:
        print(f"{symbol} 不在池中", file=sys.stderr)
        return 1
    data["last_updated"] = today
    _save_pool(data)
    if any(tier in ("watchlist", "ready") for tier in removed_tiers):
        _append_tracking(symbol, f"移出池：{', '.join(removed)}\n- 原因：{reason}")
    print(f"已移出 {symbol}（来自 {', '.join(removed)}）")
    return 0


def _pool_promote(ns: argparse.Namespace) -> int:
    data = _load_pool()
    symbol = ns.symbol
    system = ns.system
    to_tier = ns.to
    today = _today_utc()
    tier_order = ["candidates", "watchlist", "ready"]
    if to_tier not in tier_order:
        print(f"无效 tier: {to_tier}", file=sys.stderr)
        return 1

    pool = data["pools"].get(system, {})
    from_tier = None
    item = None
    for t in tier_order:
        for x in pool.get(t, []):
            if x["symbol"] == symbol:
                from_tier = t
                item = x
                break
        if item:
            break
    if not item:
        print(f"{symbol} 不在 {system} 池中", file=sys.stderr)
        return 1

    pool[from_tier] = [x for x in pool[from_tier] if x["symbol"] != symbol]
    item["last_checked"] = today
    if to_tier in ("watchlist", "ready") and "status" not in item:
        item["status"] = "waiting_market"
    if to_tier == "ready":
        item["confirmed_at"] = today
        if getattr(ns, "research", None):
            item["research_file"] = ns.research

    pool.setdefault(to_tier, []).append(item)
    data["last_updated"] = today
    _save_pool(data)
    _append_tracking(symbol, f"层级提升：{system}/{from_tier} → {system}/{to_tier}")
    print(f"已提升 {symbol}：{system}/{from_tier} → {system}/{to_tier}")
    return 0


def _pool_update(ns: argparse.Namespace) -> int:
    data = _load_pool()
    symbol = ns.symbol
    system = getattr(ns, "system", None)
    today = _today_utc()
    updated = False
    touched_tracking_tier = False
    systems_to_check = [system] if system else list(data["pools"].keys())
    for sys_name in systems_to_check:
        pool = data["pools"].get(sys_name, {})
        for tier in ["candidates", "watchlist", "ready"]:
            for item in pool.get(tier, []):
                if item["symbol"] == symbol:
                    if getattr(ns, "status", None):
                        item["status"] = ns.status
                    if getattr(ns, "trigger", None) is not None:
                        item["trigger_price"] = ns.trigger
                    if getattr(ns, "stop_loss", None) is not None:
                        item["stop_loss"] = ns.stop_loss
                    if getattr(ns, "notes", None):
                        prior = item.get("notes", "")
                        item["notes"] = f"{prior}；{ns.notes}" if prior else ns.notes
                    item["last_checked"] = today
                    updated = True
                    touched_tracking_tier = touched_tracking_tier or tier in ("watchlist", "ready")
    if not updated:
        print(f"{symbol} 不在池中", file=sys.stderr)
        return 1
    data["last_updated"] = today
    _save_pool(data)
    notes = getattr(ns, "notes", "")
    status = getattr(ns, "status", "")
    if touched_tracking_tier:
        _append_tracking(symbol, f"更新：status={status}\n{notes}")
    print(f"已更新 {symbol}")
    return 0


def _pool_sync_from_scan(ns: argparse.Namespace) -> int:
    import json

    scan_path = ns.scan
    system = ns.system
    if not Path(scan_path).exists():
        print(f"扫描文件不存在: {scan_path}", file=sys.stderr)
        return 1

    scan_data = json.loads(Path(scan_path).read_text(encoding="utf-8"))
    pool_data = _load_pool()
    pool_system = pool_data["pools"].get(system, {})
    active_tiers: dict[str, str] = {}
    for tier in ["candidates", "watchlist", "ready"]:
        for item in pool_system.get(tier, []):
            active_tiers[item["symbol"]] = tier
    summary = sync_candidates_from_scan(
        system=system,
        scan_data=scan_data,
        apply=getattr(ns, "apply", False),
        scan_file=str(Path(scan_path)),
    )

    print(
        f"\n【pool sync-from-scan】{system.upper()} | "
        f"effective_date: {summary.get('effective_date') or '?'} | "
        f"signal_date: {summary.get('signal_date') or '?'}"
    )
    print(
        f"扫描命中总数: {summary['scan_candidates_total']} 只 | "
        f"输出候选: {summary['scan_candidates']} 只 | "
        f"策略可入池: {summary['eligible_after_policy_filter']} 只 | "
        f"旧 candidates: {summary['previous_candidates']} 只 | "
        f"新 candidates: {summary['next_candidates']} 只\n"
    )

    scan_symbols = {item["symbol"]: item for item in scan_data.get("candidates", [])}
    if summary["added"]:
        print("✅ 建议入候选池（新出现，未在池中）:")
        for sym in summary["added"]:
            item = scan_symbols[sym]
            print(f"  {sym:<20} {item.get('name', ''):<10} 得分:{item.get('score', '?')}")
    else:
        print("✅ 无新候选需要入池")

    active_symbols = sorted(set(summary["retained"]) | set(summary["already_active"]))
    if active_symbols:
        print(f"\n📋 已在池中或已高层跟踪（{len(active_symbols)} 只）:")
        for sym in active_symbols:
            item = scan_symbols[sym]
            tier = active_tiers.get(sym, "active")
            print(f"  {sym:<20} {item.get('name', ''):<10} [{tier}] 得分:{item.get('score', '?')}")

    if summary["blocked_reentry"]:
        print(f"\n⛔ 已移出标的不自动回池（{len(summary['blocked_reentry'])} 只）:")
        for sym in summary["blocked_reentry"]:
            item = scan_symbols[sym]
            print(f"  {sym:<20} {item.get('name', ''):<10}")

    if summary["dropped"]:
        print("\n⚠️  旧 candidates 未出现在本次扫描中:")
        for sym in summary["dropped"]:
            print(f"  {sym:<20} [candidates] — 本次扫描未命中")
    else:
        print("\n✅ 旧 candidates 全部仍在本次扫描结果中")

    if summary["updated"]:
        print("\n已应用：仅重建 candidates，watchlist/ready 未自动改动。")
    else:
        print("\n（默认 dry-run；如需重建 candidates，请加 --apply）")
    return 0
