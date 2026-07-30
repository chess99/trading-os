# 已停止的全 A 股 rapid-triage Cycle 003 校准档案

本目录只保留 2026-07-30 至 2026-07-31 期间已停止、未闭环的 Cycle 003 中可用于机制复盘的最小信息。它不是正式 coverage、不是当前公司结论，也不得被下游 workflow 当成可操作事实源。

## 为什么停止

旧流程要求一家公司一个 Agent，再由半盲 reviewer 对停止路由抽检。reviewer 与原 Agent 的观点差异被机械解释为路由错误，随后生成 correction cohort；correction 自身又进入同一质量门，最终出现三层嵌套 correction。瓶颈从“判断公司”转移成“证明每次判断与另一名 reviewer 一致”。

## 保留了什么

- `calibration.jsonl`：25 家公司的逐轮路由、研究价值、估值信号、决定性问题、Agent provenance 和来源 ID；每家公司一行。
- 本 README：记录停止原因、规模和新机制应避免的故障模式。
- `manifest.json`：记录原始产物规模、清理范围和校准文件摘要。

原始 Markdown 报告、source manifest、quality packet、seal 和未闭环 queue/meta 写入均已移除。其信息高度重复，而且未通过旧机制自己的闭环条件；保留它们反而会让下游误把草稿当作正式结论。

## 量化复盘

- 初始 cohort：25 家、25 个单公司 package。
- correction-001：10 家被重复判断；其中 6 家的派生路由改变。
- nested correction：2 家被第三次判断；随后又为 1 家创建了第四层空 correction cohort。
- 共 37 个单公司 package、226 个 coverage 文件、798,616 字节；产物时间窗约 6 小时 51 分钟。
- 初始判断约 2 小时完成，随后超过 5 小时耗在抽检、扩样、重做和 resolution 上，仍未闭环。

## 新机制必须守住的边界

1. 初筛由同一投资经理 Agent 批量判断，保证尺度一致；不再一家公司启动一个 Agent。
2. 路由分歧是校准信号，不等于事实错误；只有身份错误、可核验事实错误、重大风险遗漏或 contract 违规才算 material error。
3. 初筛结果一次封存。发现 material error 时只允许一次显式 adjudication，不允许 correction 套 correction。
4. 只有少数 `send_to_analyst` 候选购买单公司研究员预算；独立承保和 challenger 留到深研之后。
