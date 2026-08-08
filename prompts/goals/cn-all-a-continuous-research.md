# 全 A 股持续研究 Goal

> 在新的 Codex 任务中引用本文件。状态与执行细节以根 `AGENTS.md`、`playbooks/simple-research.md` 和 `prompts/company/standard-deep-research.md` 为准。

持续维护全 A 股研究系统。只有没有有效基线时才跑全市场；基线完成后只处理新增公司、每日收盘价格、财报、重大公告和人工事件。

## 状态模型

证券范围使用 `active / inactive`。公司研究状态使用：

- `unseen`：尚未初筛；
- `ignore`：当前不值得正式研究或研究后不值得持续监控；
- `candidate`：主 Agent 已选中，等待或正在正式研究；
- `covered`：已有当前有效正式报告，进入价格或事件监控；
- `stale`：重大变化使旧报告失效，暂停价格监控并等待更新。

初筛动作只允许 `ignore / research_now`；`research_now` 写入 `candidate` 并创建任务。价格触发只能来自 active `covered` 公司。

## 全市场基线

主 Agent 分批浏览冻结范围内全部 active unseen 公司。程序只准备压缩事实，主 Agent 逐项决定是否值得占用一次正式研究资源。

- 明显缺乏业务质量、现金收益、治理可信度、错价可能性或可解关键问题：`ignore`；
- 值得完成一次正式研究：`research_now`。

初筛不估值、不设置买点、不生成公司报告。不要按数量目标填队列，也不要把未研究公司放入价格监控。

## 单公司任务

不同公司可以独立并行，一家公司始终由一个 Agent 端到端完成。每个任务必须使用 `prompts/company/standard-deep-research.md`，没有研究等级、分钟预算、复核 Agent、承保或中间交流。

最终结果只有 `covered / ignore`，两者都保留 `current.md`。`covered` 必须有价格或事件触发；`ignore` 不激活价格线。

## 增量运行

每日收盘只扫描 active covered 的有效价格线。命中后主 Agent 复看；仅当原报告失效时转为 stale 并更新研究。

公告扫描覆盖全部 active 公司：

- ignore 出现实质变化：转 candidate；
- covered 原逻辑仍有效：保持 covered；
- covered 报告或估值失效：转 stale；
- stale 更新完成：转 covered 或 ignore。

## 恢复与写入

启动时读取 Git 状态、`coverage/cn-a/research_state.jsonl`、`coverage/cn-a/research_queue.jsonl`、`research/watchlist.jsonl` 和当前报告。保留用户及其他并行修改，不重做已完成公司。

单公司 Agent不直接写共享 JSONL。协调器串行接收最终结果、原子写状态、重建自选池并运行 `python -m trading_os validate`。每完成一个完整迭代，只提交本轮修改。

## 每轮报告

向用户报告：运行模式、信息截止时间、active/inactive 数、unseen/ignore/candidate/covered/stale 数、研究队列、完成公司、自选池变化、价格命中、重大事件、验证与提交。不要汇报多余流程层级或 Agent 往返。
