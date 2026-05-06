# Daily Workflow Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重新设计每日工作流，实现：全量数据更新 → 全量扫描决定候选池进出 → 池中标的深度分析（首次入池做研究，已在池每日验证假设） → 生成日报。

**Architecture:**
- `fetch-ak-bulk` 修复 ETF/指数 fallback 卡死问题（新浪对 ETF 失败后不再等 BaoStock 超时）
- `daily-workflow` skill 重写，反映完整的五步工作流
- `pool` CLI 新增 `pool sync-from-scan` 子命令，自动比对扫描结果与现有池，输出进出池建议

**Tech Stack:** Python, akshare, trading_os CLI, CANSLIM/Elder skill 体系

---

## 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/trading_os/data/sources/akshare_source.py` | Modify | `_fetch_with_fallback`：ETF 代码跳过 BaoStock fallback |
| `src/trading_os/cli.py` | Modify | `pool` 新增 `sync-from-scan` 子命令 |
| `.claude/skills/daily-workflow/SKILL.md` | Rewrite | 完整五步工作流 |
| `tests/test_fetch_etf_filter.py` | Create | ETF 过滤的单元测试 |

---

## Task 1：修复 `_fetch_with_fallback` 对 ETF 的无效 BaoStock fallback

**背景：** 当 `fetch-ak-bulk` 使用新浪接口时，遇到 ETF（如 515880）会失败，随后走 BaoStock fallback，但 BaoStock 也不通，导致每只 ETF 都超时 10 秒以上，卡死全量更新进程。

**Files:**
- Modify: `src/trading_os/data/sources/akshare_source.py`（`_fetch_with_fallback` 函数）
- Create: `tests/test_fetch_etf_filter.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_fetch_etf_filter.py` 写：

```python
"""测试 ETF 代码在 _fetch_with_fallback 中不会走 BaoStock fallback。"""
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from trading_os.data.sources.akshare_source import _fetch_with_fallback, _SOURCE_AVAILABILITY
from trading_os.data.schema import Exchange


def _make_empty_df():
    return pd.DataFrame()


def _make_valid_df():
    return pd.DataFrame({
        "日期": ["2026-01-02"],
        "开盘": [1.0], "收盘": [1.0], "最高": [1.0], "最低": [1.0], "成交量": [100],
    })


def test_etf_skips_baostock_when_sina_fails():
    """ETF 代码（51xxxx）在新浪失败后，不应尝试 BaoStock——因为 BaoStock 不通时会超时卡死。"""
    import trading_os.data.sources.akshare_source as mod
    # 重置会话缓存
    mod._SOURCE_AVAILABILITY.update({"eastmoney": False, "sina": False, "baostock": None})

    mock_ak = MagicMock()
    mock_ak.stock_zh_a_hist.side_effect = Exception("eastmoney fail")
    mock_ak.stock_zh_a_daily.side_effect = Exception("sina fail: No value to decode")

    baostock_called = []
    def fake_bs_fetch(*args, **kwargs):
        baostock_called.append(True)
        return _make_valid_df()

    with patch("trading_os.data.sources.akshare_source._BAOSTOCK_LOCK"):
        with patch("trading_os.data.sources.baostock_source.fetch_daily_bars", fake_bs_fetch):
            df, src = _fetch_with_fallback(
                mock_ak, "515880", Exchange.SSE, "20260101", "20260401", "qfq"
            )

    assert not baostock_called, "ETF 代码不应触发 BaoStock fallback"
    assert df.empty


def test_normal_stock_still_uses_baostock_fallback():
    """普通股票（600000）在新浪失败后，仍应尝试 BaoStock。"""
    import trading_os.data.sources.akshare_source as mod
    mod._SOURCE_AVAILABILITY.update({"eastmoney": False, "sina": False, "baostock": None})

    mock_ak = MagicMock()
    mock_ak.stock_zh_a_hist.side_effect = Exception("eastmoney fail")
    mock_ak.stock_zh_a_daily.side_effect = Exception("sina fail")

    baostock_called = []
    def fake_bs_fetch(*args, **kwargs):
        baostock_called.append(True)
        return _make_valid_df()

    with patch("trading_os.data.sources.akshare_source._BAOSTOCK_LOCK"):
        with patch("trading_os.data.sources.baostock_source.fetch_daily_bars", fake_bs_fetch):
            df, src = _fetch_with_fallback(
                mock_ak, "600000", Exchange.SSE, "20260101", "20260401", "qfq"
            )

    assert baostock_called, "普通股票应尝试 BaoStock fallback"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/zcs/code2/trading-os
python -m pytest tests/test_fetch_etf_filter.py -v 2>&1 | head -30
```

预期：`test_etf_skips_baostock_when_sina_fails` FAIL（当前代码 ETF 会走 BaoStock）

- [ ] **Step 3: 实现修复**

在 `src/trading_os/data/sources/akshare_source.py` 中，在 `_fetch_with_fallback` 函数里，在 "Fallback 2: BaoStock" 块的开头加入 ETF 检测：

找到这段代码：
```python
    # Fallback 2：BaoStock（若会话级探测已确认不可用则跳过）
    # BaoStock login/logout 是全局状态，并发时必须串行化
    if _SOURCE_AVAILABILITY["baostock"] is False:
        return pd.DataFrame(), "none"
    try:
```

替换为：
```python
    # Fallback 2：BaoStock（若会话级探测已确认不可用则跳过）
    # ETF/LOF 代码（51xxxx/56xxxx for SSE, 15xxxx/16xxxx for SZSE）新浪失败是预期行为，
    # 不走 BaoStock fallback——BaoStock 不通时会超时卡死全量更新。
    _is_etf = (
        (exchange.value == "SSE" and (symbol_str.startswith("51") or symbol_str.startswith("56")))
        or (exchange.value == "SZSE" and (symbol_str.startswith("15") or symbol_str.startswith("16")))
    )
    if _is_etf:
        return pd.DataFrame(), "none"
    # BaoStock login/logout 是全局状态，并发时必须串行化
    if _SOURCE_AVAILABILITY["baostock"] is False:
        return pd.DataFrame(), "none"
    try:
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_fetch_etf_filter.py -v
```

预期：2 tests PASSED

- [ ] **Step 5: 全量回归测试**

```bash
python -m pytest tests/ -v --tb=short -q 2>&1 | tail -20
```

预期：无新增失败

- [ ] **Step 6: Commit**

```bash
git add src/trading_os/data/sources/akshare_source.py tests/test_fetch_etf_filter.py
git commit -m "fix: ETF代码跳过BaoStock fallback，避免全量更新卡死"
```

---

## Task 2：`pool` CLI 新增 `sync-from-scan` 子命令

**背景：** 当前 `pool` 没有办法自动把扫描结果（`artifacts/scan/canslim-YYYYMMDD.json`）与现有池比对，输出"谁应该入候选池、谁应该移出"的建议，只能手动判断。

**Files:**
- Modify: `src/trading_os/cli.py`（`_cmd_pool` 和 argparse 注册）

- [ ] **Step 1: 写失败测试**

在 `tests/test_pool_sync.py`：

```python
"""测试 pool sync-from-scan 子命令。"""
import json, tempfile, os, sys
from pathlib import Path
from unittest.mock import patch
import pytest


def _run_pool(args, pool_path):
    """辅助：以 pool_path 为池文件运行 pool 子命令。"""
    from trading_os.cli import main
    with patch("trading_os.cli._pool_path", return_value=Path(pool_path)):
        return main(["pool"] + args)


def _make_pool(tmp_path):
    pool = {
        "last_updated": "2026-05-06",
        "pools": {
            "canslim": {
                "candidates": [
                    {"symbol": "SSE:601138", "name": "工业富联", "entered_at": "2026-05-01",
                     "entry_reason": "test", "score": 5}
                ],
                "watchlist": [], "ready": []
            },
            "elder": {"candidates": [], "watchlist": [], "ready": []},
            "value": {"candidates": [], "watchlist": [], "ready": []}
        },
        "exited": []
    }
    p = tmp_path / "pool.json"
    p.write_text(json.dumps(pool))
    return str(p)


def _make_scan(tmp_path, candidates):
    scan = {
        "scan_date": "2026-05-06",
        "system": "canslim",
        "total_scanned": 5517,
        "candidates": candidates,
        "filtered_out": 0,
    }
    p = tmp_path / "canslim-20260506.json"
    p.write_text(json.dumps(scan))
    return str(p)


def test_sync_shows_new_candidate(tmp_path, capsys):
    """扫描中出现的高分新标的，且不在池中，应提示'建议入候选池'。"""
    pool_path = _make_pool(tmp_path)
    scan_path = _make_scan(tmp_path, [
        {"symbol": "SZSE:300750", "name": "宁德时代", "rank": 1, "score": 6.0,
         "signals": {"eps_growth_yoy": 0.42, "roe": 0.247, "relative_strength_top20pct": True},
         "next_step": ""}
    ])
    _run_pool(["sync-from-scan", "--scan", scan_path, "--system", "canslim"], pool_path)
    out = capsys.readouterr().out
    assert "SZSE:300750" in out
    assert "宁德时代" in out
    assert "建议入候选" in out or "new" in out.lower()


def test_sync_shows_already_in_pool(tmp_path, capsys):
    """扫描中出现的标的已经在池中，应显示'已在池中'而不是重复建议。"""
    pool_path = _make_pool(tmp_path)
    scan_path = _make_scan(tmp_path, [
        {"symbol": "SSE:601138", "name": "工业富联", "rank": 1, "score": 5.0,
         "signals": {}, "next_step": ""}
    ])
    _run_pool(["sync-from-scan", "--scan", scan_path, "--system", "canslim"], pool_path)
    out = capsys.readouterr().out
    assert "SSE:601138" in out
    assert "已在池" in out or "already" in out.lower()


def test_sync_shows_dropped_from_scan(tmp_path, capsys):
    """池中标的本次扫描未出现（得分不足），应提示'需关注是否移出'。"""
    pool_path = _make_pool(tmp_path)
    scan_path = _make_scan(tmp_path, [])  # 扫描结果为空，601138 消失
    _run_pool(["sync-from-scan", "--scan", scan_path, "--system", "canslim"], pool_path)
    out = capsys.readouterr().out
    assert "SSE:601138" in out
    assert "未出现" in out or "dropped" in out.lower() or "不在" in out
```

- [ ] **Step 2: 运行确认失败**

```bash
python -m pytest tests/test_pool_sync.py -v 2>&1 | head -20
```

预期：3 tests ERROR（sync-from-scan 子命令不存在）

- [ ] **Step 3: 实现 `_pool_sync_from_scan`**

在 `src/trading_os/cli.py` 中，在 `_pool_update` 函数之后、`# --------------- Main ---------------` 之前，添加：

```python
def _pool_sync_from_scan(ns: argparse.Namespace) -> int:
    """比对扫描结果与现有池，输出进出池建议（不自动修改池）。"""
    import json
    from pathlib import Path

    scan_path = ns.scan
    system = ns.system

    if not Path(scan_path).exists():
        print(f"扫描文件不存在: {scan_path}", file=sys.stderr)
        return 1

    scan_data = json.loads(Path(scan_path).read_text(encoding="utf-8"))
    pool_data = _load_pool()

    scan_symbols = {item["symbol"]: item for item in scan_data.get("candidates", [])}
    pool_system = pool_data["pools"].get(system, {})
    pool_in_symbols: dict[str, str] = {}  # symbol -> tier
    for tier in ["candidates", "watchlist", "ready"]:
        for item in pool_system.get(tier, []):
            pool_in_symbols[item["symbol"]] = tier

    print(f"\n【pool sync-from-scan】{system.upper()} | 扫描日期: {scan_data.get('scan_date', '?')}")
    print(f"扫描候选: {len(scan_symbols)} 只 | 当前池: {len(pool_in_symbols)} 只\n")

    # 新出现：在扫描中，不在池中
    new_entries = {s: v for s, v in scan_symbols.items() if s not in pool_in_symbols}
    if new_entries:
        print("✅ 建议入候选池（新出现，未在池中）:")
        for sym, item in sorted(new_entries.items(), key=lambda x: -x[1].get("score", 0)):
            print(f"  {sym:<20} {item.get('name',''):<10} 得分:{item.get('score','?')}")
            print(f"    → pool add --symbol {sym} --system {system} --tier candidates "
                  f"--reason \"scan得分{item.get('score','?')}\" "
                  f"--score {item.get('score','?')}")
    else:
        print("✅ 无新候选需要入池")

    # 已在池
    already = {s: v for s, v in scan_symbols.items() if s in pool_in_symbols}
    if already:
        print(f"\n📋 已在池中（{len(already)} 只）:")
        for sym, item in already.items():
            tier = pool_in_symbols[sym]
            print(f"  {sym:<20} {item.get('name',''):<10} [{tier}] 得分:{item.get('score','?')}")

    # 池中但本次扫描未出现
    dropped = {s: t for s, t in pool_in_symbols.items() if s not in scan_symbols}
    if dropped:
        print(f"\n⚠️  池中标的未出现在本次扫描（需关注是否移出）:")
        for sym, tier in dropped.items():
            print(f"  {sym:<20} [{tier}] — 本次扫描得分不足，请确认是否移出")
    else:
        print("\n✅ 所有池中标的均在本次扫描中出现")

    print(f"\n（此命令只输出建议，不修改 pool.json。如需操作请手动执行上方命令）")
    return 0
```

- [ ] **Step 4: 在 `_cmd_pool` dispatch 中加入分支**

找到 `_cmd_pool` 函数中的 dispatch：

```python
def _cmd_pool(ns: argparse.Namespace) -> int:
    sub = ns.pool_cmd
    if sub == "list":
        return _pool_list(ns)
    elif sub == "status":
        return _pool_status(ns)
    elif sub == "add":
        return _pool_add(ns)
    elif sub == "remove":
        return _pool_remove(ns)
    elif sub == "promote":
        return _pool_promote(ns)
    elif sub == "update":
        return _pool_update(ns)
    else:
        print(f"未知 pool 子命令: {sub}", file=sys.stderr)
        return 1
```

在 `elif sub == "update":` 行后加：

```python
    elif sub == "sync-from-scan":
        return _pool_sync_from_scan(ns)
```

- [ ] **Step 5: 在 argparse 注册 `sync-from-scan`**

找到 pool argparse 注册区段末尾（`p.set_defaults(func=_cmd_pool)` 附近），在最后一个 `pool_sub.add_parser` 后加：

```python
    p = pool_sub.add_parser("sync-from-scan", help="比对扫描结果与现有池，输出进出池建议（不修改池）")
    p.add_argument("--scan", required=True, help="扫描 JSON 路径，如 artifacts/scan/canslim-20260506.json")
    p.add_argument("--system", required=True, choices=["canslim", "elder", "value"])
```

- [ ] **Step 6: 运行测试确认通过**

```bash
python -m pytest tests/test_pool_sync.py -v
```

预期：3 tests PASSED

- [ ] **Step 7: 手动验证**

```bash
python -m trading_os pool sync-from-scan \
  --scan artifacts/scan/canslim-20260429.json \
  --system canslim
```

预期：输出已在池/新候选/已消失三个区块

- [ ] **Step 8: Commit**

```bash
git add src/trading_os/cli.py tests/test_pool_sync.py
git commit -m "feat: pool sync-from-scan — 自动比对扫描结果与现有池"
```

---

## Task 3：重写 `daily-workflow` skill

**背景：** 当前 skill 工作流错误（Step 1 只拉自选池标的而非全量、无全量扫描、无每日假设验证）。需要反映完整的五步工作流。

**Files:**
- Rewrite: `.claude/skills/daily-workflow/SKILL.md`

- [ ] **Step 1: 重写 SKILL.md**

完整替换 `.claude/skills/daily-workflow/SKILL.md` 内容为：

```markdown
---
name: daily-workflow
description: |
  每日自选池工作流。五步完整流程：全量数据更新 → 大盘状态 → 全量扫描决定候选池进出
  → 池中标的深度分析（首次入池做研究，已在池每日验证假设是否还成立）→ 生成日报。
  触发词："跑日常工作流"、"更新自选池"、"日常分析"、"今天市场怎样"、"日报"。
  输出：大盘状态 + 扫描进出池建议 + 每只标的假设验证 + 需要立即处理事项 + 日报文件。
  重要：数据更新完成后才开始分析，不提前宣布完成。
---

# Daily Workflow — 每日自选池工作流

**触发词**：「跑日常工作流」「更新自选池」「日常分析」「今天市场怎样」「日报」

**重要原则**：五步必须按顺序完成，Step 1 数据拉取完成后才进行分析。不得在数据未就绪时提前生成日报。

---

## Step 1：全量数据更新

更新全量 A 股 K 线数据（2800+ 只），同时更新大盘指数：

```bash
# 全量更新（后台运行，等完成后再继续）
python -m trading_os fetch-ak-bulk --start {LAST_TRADING_DAY} --end {TODAY} --adjustment qfq
# 同时更新上证指数（market-breadth 需要）
python -m trading_os fetch-bars --exchange SSE --ticker 000001 --start {LAST_TRADING_DAY}
```

- `LAST_TRADING_DAY`：上次运行日期（或昨日）
- 必须等 fetch-ak-bulk **完成**后才进行后续步骤
- 如果完全失败（网络问题），用本地已有数据继续，但在日报中注明数据截止日期
- ETF（51xxxx/56xxxx/15xxxx/16xxxx）已自动过滤，不会卡死

---

## Step 2：大盘状态检查

```bash
python -m trading_os market-breadth --index SSE:000001
```

判断标准：
- 换筹日 ≥ 5：**熊市**，不建新仓，所有 waiting_market 标的继续等待
- 换筹日 3-4：**震荡**，谨慎，减小仓位
- 换筹日 ≤ 2：**健康**，正常操作
- **跟进日（Follow-Through Day）**：反弹第4-7日，主要指数放量涨 ≥1.5% → 大盘转势信号

---

## Step 3：全量扫描 → 候选池进出决策

每周一跑完整扫描，其余日期跑快速比对：

### 周一（完整扫描）

```bash
python -m trading_os scan-canslim --date {TODAY} --top 50 \
  --output artifacts/scan/canslim-{TODAY}.json

python -m trading_os scan-elder --date {TODAY} \
  --output artifacts/scan/elder-{TODAY}.json
```

### 每日（比对现有池与最新扫描）

```bash
# 用最近一次扫描结果比对
python -m trading_os pool sync-from-scan \
  --scan artifacts/scan/canslim-{LATEST_SCAN_DATE}.json \
  --system canslim
```

**决策规则：**

| 情况 | 建议动作 |
|------|---------|
| 扫描新出现，得分 ≥4/7 | `pool add --tier candidates` 入候选池 |
| 候选池标的得分持续 <3/7 两周 | `pool remove` 移出 |
| 观察池标的从扫描消失（连续3次） | 标记预警，人工确认是否移出 |
| 观察池标的得分大幅下降（≥2分） | 日报中标注，触发下方 Step 4 重新验证 |

---

## Step 4：池中标的逐只分析

这是工作流最重要的步骤。对每只标的根据其状态执行不同深度的分析：

### 4A：首次入池（tier 从无到 candidates）

运行完整深度研究：

- CANSLIM 体系：使用 `canslim-fundamental-research` skill
- Value 体系：使用 `value-fundamental-research` skill
- Elder 体系：使用 `elder-screen` skill

研究完成后：
```bash
python -m trading_os pool promote --symbol {SYMBOL} --system {SYSTEM} --to watchlist \
  --research artifacts/research/{RESEARCH_FILE}
```

并在 `artifacts/watchlist/tracking/{SYMBOL}.md` 创建追踪文件，记录：
- 入池原因与核心假设
- 触发价与止损价
- 主要风险点

### 4B：已在观察池（watchlist/ready）— 每日假设验证

对每只已在池标的，回答以下问题：

**技术面（每日）：**
```bash
python -m trading_os 52week --symbols {SYMBOL}
```
- 当前价 vs 触发价：距离是否在压缩/扩大？
- 是否触达触发价（需立即处理）？
- 是否跌破止损（需立即处理）？
- 距52周高点是否超过 -20%（标记预警）？

**假设验证（每日简述，每周深度）：**

每日问：
1. 入池时的**核心催化剂**（如 AI 算力需求、关税政策、基本面增速）今天有没有新信息？
2. 入池时预判的**时间窗口**（如等大盘跟进日、等季报确认）是否还合理？
3. 有没有出现入池时没有预料到的**新风险**？

每周问（周一跑扫描时一起）：
- 基本面有没有新季报、公告、研报？
- CANSLIM 体系：最新季度 EPS 增速是否维持加速趋势？
- Value 体系：估值逻辑（DCF 参数、护城河）有没有变化？
- 综合判断：维持在池 / 升层 / 移出

**更新追踪文件：**
在 `artifacts/watchlist/tracking/{SYMBOL}.md` 末尾追加一条：
```
### {TODAY}
- 当前价：{PRICE}，距触发价：{PCT}%
- 大盘状态：{换筹日数量}个换筹日
- 假设验证：[催化剂/时间窗口/风险的简短更新]
- 状态：{维持/升层/预警/移出}
```

### 4C：候选池（candidates）— 每周深度检查

不每日检查，每周一跑扫描时一并确认：
- 是否可以升至 watchlist（完成深度研究）？
- 还是从候选池移出（基本面变差）？

---

## Step 5：生成日报

```bash
python -m trading_os pool status --output artifacts/daily/{TODAY}.md
```

日报结构（在 pool status 输出基础上补充）：

```markdown
# 每日工作流报告 — {TODAY}

## 数据状态
- K线数据截至：{DATE}（是/否为今日）

## 大盘状态
- 换筹日：{N} 个 → {熊市/震荡/健康}
- 跟进日：{是/否}
- 操作指引：{停止建仓/谨慎/正常}

## ⚡ 需要立即处理
- [触达触发价/止损价的标的]

## 扫描变化（Step 3 结果）
- 新候选：[列出]
- 已消失：[列出]

## 标的假设验证摘要（Step 4 结果）
- [每只的一行简述：状态 + 关键变化]

## 建议下一步行动（优先级排序）
1. [最紧急]
2. ...
```

---

## 进出池规则速查

| 体系 | 入 candidates | 入 watchlist | 入 ready | 出池 |
|------|--------------|-------------|---------|------|
| CANSLIM | scan ≥4/7，且 C/A/L 至少2个通过 | 深度研究完成+人工确认 | 大盘跟进日+技术面确认 | 假设失效/连续3次扫描消失/人工 |
| Elder | 三重滤网第一滤网通过 | 二三滤网确认 | 第三滤网入场信号 | 止损/趋势反转 |
| Value | DCF 折价 ≥25% | 深度研究+安全边际≥30% | 大盘转势+回落至目标价 | 逻辑失效/估值修复 |
```

- [ ] **Step 2: 验证 skill 语法正确（YAML frontmatter）**

```bash
python -c "
import re
content = open('.claude/skills/daily-workflow/SKILL.md').read()
fm = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
assert fm, 'frontmatter 缺失'
import yaml
meta = yaml.safe_load(fm.group(1))
assert 'name' in meta, 'name 字段缺失'
assert 'description' in meta, 'description 字段缺失'
print('SKILL.md 格式正确')
print('name:', meta['name'])
print('description 长度:', len(meta['description']))
"
```

预期：`SKILL.md 格式正确`

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/daily-workflow/SKILL.md
git commit -m "refactor: daily-workflow skill 重写——完整五步工作流含每日假设验证"
```

---

## Task 4：用干净上下文 Agent 验证 skill 效果

**目标：** 用完全不了解本次改动历史的 Agent，实际触发 `daily-workflow` skill 并验证它按预期工作流执行。

- [ ] **Step 1: 准备验证场景**

确保以下文件存在且可用：
```bash
ls artifacts/watchlist/pool.json     # 7只在池标的
ls artifacts/scan/canslim-20260429.json  # 最近一次扫描结果
python -m trading_os pool list       # 确认CLI正常
```

- [ ] **Step 2: 启动干净上下文 Agent 验证**

用 Agent tool（subagent_type=general-purpose）验证，给 Agent 完全干净的上下文，只告诉它项目目录和要做什么，验证它能否正确触发并执行 daily-workflow skill：

```
验证任务：
工作目录：/Users/zcs/code2/trading-os

请触发 daily-workflow skill，执行每日工作流。
注意：你对这个项目的历史没有任何背景知识，完全基于 skill 文件的指引执行。

验证以下几点：
1. skill 是否被正确触发（应通过 Skill tool）？
2. Step 1 是否尝试全量数据更新（fetch-ak-bulk），而不是只拉自选池标的？
3. Step 3 是否运行了 pool sync-from-scan 来比对扫描结果？
4. Step 4 对已在池标的是否逐只验证假设（而不只是看价格）？
5. Step 5 日报是否在数据就绪后才生成？

请记录每一步的实际行为，最后给出验证报告：哪些符合预期，哪些不符合。
```

- [ ] **Step 3: 根据验证结果修正 skill**

如果 Agent 报告有步骤不符合预期（如跳过了扫描、日报提前生成、假设验证不够深入），直接修改 `SKILL.md` 对应段落，重跑验证。

- [ ] **Step 4: 最终 Commit**

```bash
git add .claude/skills/daily-workflow/SKILL.md
git commit -m "fix: daily-workflow skill 根据验证结果调整"
```

---

## 验收标准

1. `fetch-ak-bulk` 运行时，ETF 代码（515880 等）不再卡死，直接跳过
2. `python -m trading_os pool sync-from-scan --scan artifacts/scan/canslim-20260429.json --system canslim` 输出新候选/已在池/已消失三个区块
3. 干净上下文 Agent 触发 daily-workflow，能正确按五步执行，第四步对每只标的验证假设而不只是看价格
4. 所有单元测试通过：`python -m pytest tests/ -q`
