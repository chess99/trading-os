# Trading OS Agent Guide

除非用户主动要求切分支，否则直接在当前分支开发。文档默认使用中文。完成一个完整迭代后，只提交本次修改的文件；提交前检查暂存区，禁止带入用户或其他 Agent 的无关修改。

## 唯一事实源

- 全市场状态：`coverage/cn-a/research_state.jsonl`。
- 当前研究队列：`coverage/cn-a/research_queue.jsonl`。
- 自选池：`research/watchlist.jsonl`，必须可由全市场状态确定性重建。
- 单公司完整研究：`research/companies/CN/{ticker}/current.md`，每家公司最多一份，更新历史交给 Git。
- 收盘价触发的去重与重新武装状态直接保存在公司当前状态行中。
- 财报与重大公告扫描只用 `coverage/cn-a/event_scan_state.json` 保存最后成功时间和近期公告 ID；不得扩张为永久事件账本。

旧 manager-screen、quick/targeted/scoped/deep 阶段预算、claim/seal、calibration、独立承保、challenger、仲裁和组合审批均已退役，不得重新引入。

## 角色与并行

- 主 Agent 批量浏览全市场压缩事实，逐项判断 `ignore / watch / research_now`。
- 不设置必须深入研究的公司数量。是否值得派发，取决于主 Agent 对信息价值、业务质量、错价可能性和关键问题可解性的判断。
- 只有 `research_now` 派单公司 Agent；明显不值得研究的公司不得为了形式完整而派发。
- 不同公司允许并行，常见并行度为 3—6，具体由调用者配置；一家公司只允许一个 Agent 端到端完成。
- 单公司 Agent 收到一次完整任务，最终返回一次结构化结果。没有复核 Agent、经理审批或中间角色交流。
- 同一个 Agent 先快速浏览；若没有价值就结束，若有价值就在同一上下文继续。研究深度由 Agent 自适应决定，不设置分钟数或阶段预算。

## 结果要求

结果状态为 `discard / watch / researched`：

- `discard` 只需简短定性结论；若存在明确的公司特定重看条件再记录，否则由全市场财报与重大事件扫描负责重新发现；
- `watch` 需说明为什么值得跟踪，并给出财报、事件或价格触发条件；
- `researched` 需给出关键逻辑、关键风险、合理价值区间、买入触发价、后续触发条件与来源 URL。只有这种结果写 `current.md`。

不要求仓位建议、`buy_now`、精确年化回报、独立承保结论或组合动作。数字应能在给出的来源中复核，但不建立 evidence ledger、SHA 权限链或多角色复核链。

## 初筛与日常触发

- 首轮全市场初筛只需要完整走一次。之后以价格、财报、公告、日期或人工事件驱动局部更新。
- 自选池只包含当前值得持续关注的 `watch` 和 `researched` 公司，不得把整个长尾市场塞入自选池。
- 价格只做每日收盘扫描。首次越过触发价时生成复看提示；价格离开触发区后重新武装，避免每天重复提醒。价格命中本身不创建研究任务。
- 公告扫描必须覆盖全市场当前证券身份；任一目录、分页、URL 或判断结果不完整时不得推进检查点。
- 池内公司遇到财报或重大事件可直接进入快速复核。
- 池外公司先进入批量变化筛选，主 Agent认为出现实质变化后才转为 `research_now`。
- 价格变化本身只触发估值和结论复核，不要求重做全部基本面研究。

## 写入纪律

- worker 不直接修改共享 JSONL；由协调器校验并原子写入。
- 同一公司、同一触发事件只能存在一个活动任务。
- 报告只保留公开来源的标题、URL 和日期；可重新下载的 PDF、网页、行情快照不进入 Git。
- 修改共享状态后重建自选池并运行 `python -m trading_os validate`。

## 开始工作

先读：

1. `playbooks/simple-research.md`
2. `prompts/goals/cn-all-a-continuous-research.md`

常用命令见 `README.md`。
