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
# 全量更新（等完成后再继续）
python -m trading_os fetch-ak-bulk --start {LAST_TRADING_DAY} --end {TODAY} --adjustment qfq
# 同时更新上证指数（market-breadth 需要；必须加 --asset-type index 才能拉到真实点位）
python -m trading_os fetch-bars --exchange SSE --ticker 000001 --asset-type index --start {LAST_TRADING_DAY}
```

- `LAST_TRADING_DAY`：上次运行日期（或昨日）
- **必须等 fetch-ak-bulk 完成，且输出中"数据截止"= 今日或最近交易日，才进入 Step 2**
  - 输出会显示 `数据截止: 2026-05-15  [✓ 今日数据已就绪]` 或 `[⚠️  落后 N 天]`
  - 若显示落后 >1 个交易日：**停止工作流**，在日报中注明"数据未就绪，本次分析价格数据不可信"，不得生成任何价格结论
- 如果命令完全失败（网络问题）：同上，注明数据截止，不做价格分析
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
- **跟进日（Follow-Through Day）**：反弹第4-7日，主要指数放量涨 ≥1.5% → 大盘转势信号，所有 waiting_market 标的立即进入技术面确认流程

---

## Step 3：全量扫描 → 候选池进出决策

每周一跑完整扫描，其余日期用最新扫描结果比对：

### 周一（完整扫描）

```bash
python -m trading_os scan-canslim --date {TODAY} --top 50 \
  --output artifacts/scan/canslim-{TODAY}.json

python -m trading_os scan-elder --date {TODAY} \
  --output artifacts/scan/elder-{TODAY}.json
```

### 每日（比对现有池与最新扫描）

```bash
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
| 观察池标的得分大幅下降（≥2分） | 日报中标注，触发 Step 4 重新验证 |

---

## Step 4：池中标的逐只分析

这是工作流最重要的步骤。对每只标的根据其状态执行不同深度的分析。

### 4A：首次入池（candidates 层，深度研究尚未做）

运行完整深度研究：
- CANSLIM 体系：使用 `canslim-fundamental-research` skill
- Value 体系：使用 `value-fundamental-research` skill
- Elder 体系：使用 `elder-screen` skill

研究完成后升层并创建追踪文件：

```bash
python -m trading_os pool promote --symbol {SYMBOL} --system {SYSTEM} --to watchlist \
  --research artifacts/research/{RESEARCH_FILE}
```

在 `artifacts/watchlist/tracking/{EXCHANGE}_{TICKER}.md` 记录：
- 入池原因与核心假设（催化剂、估值逻辑、技术形态）
- 触发价与止损价
- 主要风险点（1-3个）
- 预期时间窗口（如"等大盘跟进日"、"等Q2季报确认"）

### 4B：已在观察池（watchlist/ready）— 每日假设验证

对每只已在池标的，完成以下两部分：

**技术面更新（每日必做）：**

```bash
python -m trading_os 52week --symbols {SYMBOL}
```

检查：
- 当前价 vs 触发价：距离压缩还是扩大？
- 是否触达触发价（🚨 需立即处理）？
- 是否跌破止损（🚨 需立即处理）？
- 距52周高点是否超过 -20%（⚠️ 标记预警）？

**假设验证（每日简问，每周深问）：**

每日回答（简短，1-2句每个）：
1. 入池时的**核心催化剂**（AI算力需求、关税政策、EPS加速等）今天有没有新信息改变判断？
2. 入池时预判的**时间窗口**（等大盘跟进日、等季报确认等）是否还合理？
3. 有没有出现入池时没有预料到的**新风险**？

每周深问（周一和扫描一起做）：
- 基本面：有没有新季报/公告/研报改变基本面判断？
- CANSLIM：最新季度 EPS 增速是否维持加速趋势？
- Value：DCF 参数、护城河假设有没有根本性变化？
- 综合判断：维持观察 / 升层 / 移出，并说明理由

**更新追踪文件：**

在 `artifacts/watchlist/tracking/{EXCHANGE}_{TICKER}.md` 末尾追加：

```markdown
### {TODAY}
- 当前价：{PRICE}，距触发价：{PCT}%，距52周高点：{PCT2}%
- 大盘：{N}个换筹日（{熊市/震荡/健康}）
- 催化剂：[今日新信息或"无变化"]
- 时间窗口：[是否还合理]
- 新风险：[有/无，说明]
- 结论：维持观察 / 升层（说明条件）/ 预警（说明原因）/ 移出（说明原因）
```

### 4C：候选池（candidates）— 每周深度检查

候选池不每日检查，每周一扫描时一并处理：
- 已有深度研究但尚未升层 → 确认是否升至 watchlist
- 尚未做深度研究 → 安排研究（4A 流程）
- 基本面变差（扫描得分下降） → 考虑移出

---

## Step 5：生成日报

Step 1-4 全部完成后，生成日报：

```bash
mkdir -p artifacts/daily
python -m trading_os pool status --output artifacts/daily/{TODAY}.md
```

在文件开头补充以下内容（pool status 输出基础上追加）：

```markdown
# 每日工作流报告 — {TODAY}

## 数据状态
- K线数据截至：{DATE}（{是/否}为今日最新数据）

## 大盘状态
- 换筹日：{N} 个 → {熊市/震荡/健康}
- 跟进日：{是/否}
- 操作指引：{停止建仓 / 谨慎 / 正常}

## ⚡ 需要立即处理
- {触达触发价/跌破止损的标的，或"无"}

## 扫描变化（Step 3）
- 新建议入池：{列出 symbol 和得分，或"无"}
- 已消失预警：{列出 symbol，或"无"}

## 标的假设验证摘要（Step 4）
| 标的 | 价格 | 距触发 | 假设状态 | 结论 |
|------|------|--------|---------|------|
| {SYMBOL} | {PRICE} | {PCT}% | {简述} | 维持/预警/移出 |

## 近期市场动态

```python
from trading_os.news import get_market_news, format_news_for_prompt
items = get_market_news(limit=15)
news_section = format_news_for_prompt(items)
```

在日报末尾追加此栏（如 `news_section` 非空）：

---
{news_section}
---

此栏为背景参考，不影响个股分析结论。

## 建议下一步行动（优先级排序）
1. {最紧急的行动}
2. ...
```

---

## 进出池规则速查

| 体系 | 入 candidates | 入 watchlist | 入 ready | 出池 |
|------|--------------|-------------|---------|------|
| CANSLIM | scan ≥4/7，且 C/A/L 至少2个通过 | 深度研究完成+人工确认 | 大盘跟进日+技术面确认 | 假设失效/连续3次扫描消失/人工 |
| Elder | 三重滤网第一滤网通过 | 二三滤网确认 | 第三滤网入场信号 | 止损/趋势反转 |
| Value | DCF 折价 ≥25% | 深度研究+安全边际≥30% | 大盘转势+回落至目标价 | 逻辑失效/估值修复 |

---

## 常用命令快速参考

```bash
# 查看池状态
python -m trading_os pool list
python -m trading_os pool list -v

# 扫描比对
python -m trading_os pool sync-from-scan \
  --scan artifacts/scan/canslim-{DATE}.json --system canslim

# 入池
python -m trading_os pool add --symbol SZSE:300750 --system canslim \
  --tier candidates --reason "scan得分6/7" --score 6

# 升层
python -m trading_os pool promote --symbol SZSE:300750 \
  --system canslim --to watchlist

# 更新状态
python -m trading_os pool update --symbol SZSE:300750 \
  --system canslim --status ready --notes "换筹日降至2，跟进日出现"

# 移出
python -m trading_os pool remove --symbol SSE:600221 \
  --system canslim --reason "基本面假设失效"

# 生成日报
python -m trading_os pool status --output artifacts/daily/$(date +%Y%m%d).md
```
