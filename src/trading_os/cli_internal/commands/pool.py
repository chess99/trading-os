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


def _load_pool() -> dict:
    import json

    p = _pool_path()
    if not p.exists():
        return _empty_pool()
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"pool.json 解析失败: {e}", file=sys.stderr)
        print(f"请检查文件: {p}", file=sys.stderr)
        raise SystemExit(1)


def _save_pool(data: dict) -> None:
    import json

    p = _pool_path()
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
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
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
    _append_tracking(symbol, f"入池：{system}/{tier}\n- 原因：{entry['entry_reason']}\n- 触发价：{entry['trigger_price']}")
    print(f"已添加 {symbol} → {system}/{tier}")
    return 0


def _pool_remove(ns: argparse.Namespace) -> int:
    data = _load_pool()
    symbol = ns.symbol
    system = getattr(ns, "system", None)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    reason = getattr(ns, "reason", "")
    removed = []
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
    if not removed:
        print(f"{symbol} 不在池中", file=sys.stderr)
        return 1
    data["last_updated"] = today
    _save_pool(data)
    _append_tracking(symbol, f"移出池：{', '.join(removed)}\n- 原因：{reason}")
    print(f"已移出 {symbol}（来自 {', '.join(removed)}）")
    return 0


def _pool_promote(ns: argparse.Namespace) -> int:
    data = _load_pool()
    symbol = ns.symbol
    system = ns.system
    to_tier = ns.to
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
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
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    updated = False
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
    if not updated:
        print(f"{symbol} 不在池中", file=sys.stderr)
        return 1
    data["last_updated"] = today
    _save_pool(data)
    notes = getattr(ns, "notes", "")
    status = getattr(ns, "status", "")
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
    scan_symbols = {item["symbol"]: item for item in scan_data.get("candidates", [])}
    pool_system = pool_data["pools"].get(system, {})
    pool_in_symbols: dict[str, str] = {}
    for tier in ["candidates", "watchlist", "ready"]:
        for item in pool_system.get(tier, []):
            pool_in_symbols[item["symbol"]] = tier

    print(f"\n【pool sync-from-scan】{system.upper()} | 扫描日期: {scan_data.get('scan_date', '?')}")
    print(f"扫描候选: {len(scan_symbols)} 只 | 当前池: {len(pool_in_symbols)} 只\n")

    new_entries = {s: v for s, v in scan_symbols.items() if s not in pool_in_symbols}
    if new_entries:
        print("✅ 建议入候选池（新出现，未在池中）:")
        for sym, item in sorted(new_entries.items(), key=lambda x: -x[1].get("score", 0)):
            print(f"  {sym:<20} {item.get('name',''):<10} 得分:{item.get('score','?')}")
            print(f"    → pool add --symbol {sym} --system {system} --tier candidates --reason \"scan得分{item.get('score','?')}\" --score {item.get('score','?')}")
    else:
        print("✅ 无新候选需要入池")

    already = {s: v for s, v in scan_symbols.items() if s in pool_in_symbols}
    if already:
        print(f"\n📋 已在池中（{len(already)} 只）:")
        for sym, item in already.items():
            tier = pool_in_symbols[sym]
            print(f"  {sym:<20} {item.get('name',''):<10} [{tier}] 得分:{item.get('score','?')}")

    dropped = {s: t for s, t in pool_in_symbols.items() if s not in scan_symbols}
    if dropped:
        print("\n⚠️  池中标的未出现在本次扫描（需关注是否移出）:")
        for sym, tier in dropped.items():
            print(f"  {sym:<20} [{tier}] — 本次扫描得分不足，请确认是否移出")
    else:
        print("\n✅ 所有池中标的均在本次扫描中出现")

    print("\n（此命令只输出建议，不修改 pool.json。如需操作请手动执行上方命令）")
    return 0
