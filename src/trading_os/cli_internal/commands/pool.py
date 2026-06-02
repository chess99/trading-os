from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from ...paths import repo_root

POOL_SYSTEM_CHOICES = ["canslim", "elder", "value"]
POOL_TIER_CHOICES = ["candidates", "watchlist", "ready"]


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
        raise SystemExit(1) from e


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
            w(
                f"  触发价:{item.get('trigger_price')}  止损:{item.get('stop_loss')}  "
                f"目标仓位:{item.get('target_position_pct')}%"
            )
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
                w(
                    f"  触发价:{item.get('trigger_price')}  "
                    f"目标仓位:{item.get('target_position_pct')}%"
                )
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
        _append_tracking(
            symbol,
            f"入池：{system}/{tier}\n"
            f"- 原因：{entry['entry_reason']}\n"
            f"- 触发价：{entry['trigger_price']}",
        )
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


def register_pool_commands(sub: argparse._SubParsersAction) -> None:
    pool_p = sub.add_parser("pool", help="自选池管理（查看/添加/移出/升层/更新）")
    pool_sub = pool_p.add_subparsers(dest="pool_cmd", required=True)
    pool_p.set_defaults(func=_cmd_pool)

    p = pool_sub.add_parser("list", help="列出池中标的")
    p.add_argument("--system", choices=POOL_SYSTEM_CHOICES, default=None)
    p.add_argument("--tier", choices=POOL_TIER_CHOICES, default=None)
    p.add_argument("-v", "--verbose", action="store_true", help="显示备注")

    p = pool_sub.add_parser("status", help="生成池状态摘要报告")
    p.add_argument("--output", default=None, help="输出 Markdown 路径（默认 stdout）")

    p = pool_sub.add_parser("add", help="添加标的到池")
    p.add_argument("--symbol", required=True, help="如 SZSE:300750")
    p.add_argument("--system", required=True, choices=POOL_SYSTEM_CHOICES)
    p.add_argument("--tier", choices=POOL_TIER_CHOICES, default="candidates")
    p.add_argument("--name", default=None)
    p.add_argument("--reason", default="")
    p.add_argument("--trigger", type=float, default=None, help="触发入场价")
    p.add_argument("--stop-loss", type=float, default=None, dest="stop_loss")
    p.add_argument("--position-pct", type=float, default=None, dest="position_pct")
    p.add_argument("--research", default=None, help="研究报告路径")
    p.add_argument("--score", type=float, default=None)
    p.add_argument("--notes", default="")

    p = pool_sub.add_parser("remove", help="移出标的（记录原因）")
    p.add_argument("--symbol", required=True)
    p.add_argument("--system", choices=POOL_SYSTEM_CHOICES, default=None)
    p.add_argument("--reason", default="")

    p = pool_sub.add_parser("promote", help="升层（candidates→watchlist→ready）")
    p.add_argument("--symbol", required=True)
    p.add_argument("--system", required=True, choices=POOL_SYSTEM_CHOICES)
    p.add_argument("--to", required=True, choices=["watchlist", "ready"], dest="to")
    p.add_argument("--research", default=None)

    p = pool_sub.add_parser("update", help="更新标的状态/触发价/备注")
    p.add_argument("--symbol", required=True)
    p.add_argument("--system", choices=POOL_SYSTEM_CHOICES, default=None)
    p.add_argument(
        "--status",
        default=None,
        choices=["waiting_market", "waiting_catalyst", "ready", "entered"],
    )
    p.add_argument("--trigger", type=float, default=None)
    p.add_argument("--stop-loss", type=float, default=None, dest="stop_loss")
    p.add_argument("--notes", default=None)
