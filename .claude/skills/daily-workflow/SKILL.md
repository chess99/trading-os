---
name: daily-workflow
description: |
  每日自选池工作流。更新 A 股数据、检查大盘状态、逐只更新追踪文件、生成日报。
  触发词："跑日常工作流"、"更新自选池"、"日常分析"、"今天市场怎样"、"更新追踪"。
  输出：大盘状态 + 池中标的价格/信号更新 + 需要立即处理的事项 + 日报文件。
---

# Daily Workflow — 每日自选池工作流

**触发词**：「跑日常工作流」「更新自选池」「日常分析」「今天市场怎样」「更新追踪」

---

## 执行流程

### Step 1：更新 K 线数据

```bash
# 获取昨日或最近未更新的数据（--skip-existing 跳过已有）
python -m trading_os fetch-ak-bulk --start {LAST_TRADING_DAY} --adjustment qfq
```

- `LAST_TRADING_DAY` = 上次运行日期（或昨日）
- 如果网络问题，继续后续步骤（用本地已有数据）

### Step 2：大盘状态检查

```bash
python -m trading_os market-breadth --index SSE:000001
```

输出解读：
- 换筹日 ≥ 5：熊市，停止建仓
- 换筹日 3-4：震荡，谨慎
- 换筹日 ≤ 2：中性/偏多
- **跟进日（Follow-Through Day）**：反弹第4-7日，主要指数放量涨 ≥1.5% → 大盘转势信号，立即进入入场流程

### Step 3：池中标的逐一更新

读取 `artifacts/watchlist/pool.json`，对所有 watchlist + ready 层的标的执行：

```bash
# 获取52周高低点和最新价
python -m trading_os 52week --symbols {SYMBOL}
```

**自动检查项**（每只）：
1. 当前价 vs 触发价：是否到达入场点？
2. 当前价 vs 止损价：是否触及止损（仅 ready 层有效）？
3. 当前价 vs 52周高点：是否回调超过 20%（标记 alert）？
4. 如果 status = waiting_market，检查大盘是否出现跟进日

**候选池**（candidates 层）每周检查一次基本面变化（不每日）。

### Step 4：每周全 A 扫描（周一执行）

```bash
python -m trading_os scan-canslim --date {TODAY} --top 30 \
  --output artifacts/scan/canslim-{TODAY}.json

python -m trading_os scan-elder --date {TODAY} \
  --output artifacts/scan/elder-{TODAY}.json
```

比较新扫描结果与现有池：
- 新出现的高分标的 → 候选是否已在池中？若未在，提示加入
- 已在池中的标的信号是否有变化（评分上升/下降）？

### Step 5：生成日报

```bash
python -m trading_os pool status --output artifacts/daily/{TODAY}.md
```

在报告开头手动追加大盘状态和当日摘要（步骤2/3/4的结果）。

**日报结构**：
```markdown
# 每日工作流报告 — YYYY-MM-DD

## 大盘状态
- 换筹日：N 个（熊市/震荡/中性）
- 跟进日：是/否

## ⚡ 需要立即处理
- [如有触发价/止损触达，列在这里]

## 池中标的更新
[每只的价格变化、是否接近触发价]

## 本周扫描新候选
[如有周扫描，列出新发现]

## 建议下一步
[优先级排序的行动清单]
```

---

## 进出池触发规则（工作流中自动检查）

### 入场触发（waiting_market → ready）

条件：大盘出现跟进日 AND 标的价格突破触发价 AND 成交量 > 50日均量 × 1.4

动作：
```bash
python -m trading_os pool update --symbol {SYMBOL} --system {SYSTEM} --status ready
python -m trading_os pool promote --symbol {SYMBOL} --system {SYSTEM} --to ready
```

### 止损触发（只在 ready/entered 层检查）

条件：当前价 < stop_loss

动作：立即在日报中标注 🚨，人工确认后执行：
```bash
python -m trading_os pool remove --symbol {SYMBOL} --reason "触及止损 {PRICE}"
```

### 回调预警

条件：当前价 < 52周高点 × 80%（回调超20%）

动作：在日报中标注 ⚠️，不自动移出，等人工判断：
- 有新催化剂支撑 → 继续持有
- 无新催化剂 → 降回 candidates 或移出

### 基本面恶化（候选/观察层，每季报后检查）

条件：EPS 连续2季同比增速下滑超原增速2/3

动作：日报中标注 🔴，人工确认后移出：
```bash
python -m trading_os pool remove --symbol {SYMBOL} --reason "EPS增速连续下滑"
```

---

## 进出池规则速查

| 体系 | 入 candidates | 入 watchlist | 入 ready | 出池 |
|------|--------------|-------------|---------|------|
| CANSLIM | scan ≥4/7，C/A/L至少2个通过 | 深度研究完成+人工确认 | 大盘跟进日+技术面确认 | 基本面恶化/回调>20%无催化/人工 |
| Elder | 三重滤网第一滤网通过 | 二三滤网确认 | 触及第三滤网入场信号 | 止损/趋势反转 |
| Value | DCF折价≥25% | 深度研究完成+安全边际≥30% | 大盘转势+价格回落至目标价 | 逻辑失效/估值修复至合理价 |

---

## 文件路径

```
artifacts/watchlist/pool.json        # 池状态（唯一机器状态权威）
artifacts/watchlist/tracking/*.md    # 每只标的追踪日志（只追加，不机器回读）
artifacts/daily/YYYYMMDD.md          # 每日报告
artifacts/scan/canslim-YYYYMMDD.json # 每周全 A 扫描结果
```

---

## 快速命令参考

```bash
# 查看池状态
python -m trading_os pool list
python -m trading_os pool list --system canslim --tier watchlist -v

# 生成日报
python -m trading_os pool status
python -m trading_os pool status --output artifacts/daily/$(date +%Y%m%d).md

# 添加新标的
python -m trading_os pool add \
  --symbol SZSE:300750 --system canslim --tier candidates \
  --name "宁德时代" --reason "CANSLIM 6/7" --trigger 453.0

# 升层（深度研究完成后）
python -m trading_os pool promote \
  --symbol SZSE:300750 --system canslim --to watchlist \
  --research artifacts/research/deep-research-20260501.md

# 更新状态
python -m trading_os pool update \
  --symbol SZSE:300750 --system canslim \
  --status ready --notes "换筹日降至2，出现跟进日"

# 移出
python -m trading_os pool remove \
  --symbol SSE:600221 --system canslim \
  --reason "基本面核查不通过"
```
