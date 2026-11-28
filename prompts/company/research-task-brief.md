# 单公司研究任务简报

本文件供协调器派发单公司研究任务使用。核心研究与验收要求见[统一深研提示词](standard-deep-research.md)、[核验附录](research-verification.md)和[写作规范](../research-writing.md)；文件体积预算见[交付规范](../../docs/research-artifacts.md)。

## 上下文与派发纪律

- 每家公司以不继承协调对话的独立研究上下文启动，单人端到端完成取证、建模、写作与返工，完成后不接手下一家公司。
- 协调器只传递任务身份、资料边界、规范路径、原始来源线索、行业主题及独占工作目录；不传递期待结论、对话记录、其他公司示范估值或旧估值中枢。
- 研究者先独立形成商业判断和初步模型，再阅读前次报告完成假设复盘；若为 A/H 双重上市发行人，优先参照 [ah-southbound-bridge.json](../../research/markets/ah-southbound-bridge.json) 保持发行人经营判断合一，避免重复造轮子。

## 可直接填写的派发简报

```text
研究任务：{symbol} {name}（筛选轨道：{compounder / inflection_growth}）
财报周期：{report_period}
关联行业主题：{industry_topic}
任务ID：{task_id}
任务类型：{periodic / manual_rewrite}
资料边界：{明确的信息截止日期；报告期与截止日分别说明}
工作目录：{该公司独占的临时目录}
仓库根目录：{repo_root}

必读规范：
AGENTS.md、playbooks/simple-research.md、
prompts/company/standard-deep-research.md、
prompts/company/research-verification.md、
prompts/research-writing.md（港股及A/H另读 prompts/company/cross-market.md）。

可选参考：
- 对应中国行业最新报告及 research/industries/topic-routes.json
- 全球对标标杆：research/benchmarks/global-leaders.json
- A/H 与港股通税率桥：research/markets/ah-southbound-bridge.json

执行要求：
1. 独立调查 2—3 个决定长期价值的商业矛盾，按重要性和四类原生估值框架（dividend_dcf_v1 / buyback_total_yield / growth_terminal_matrix / cyclical_cost_curve）完成取证与估值。
2. 守住重要性门槛与 Q1/Q3 附注继承纪律：季报缺单体/分部/工程附注时显式承接上一份完整 H1/FY 底稿，不编造多位小数细拆，不遗留未更新的历史情景。
3. 诚实作出 covered 或 ignore 结论；无长期拥有依据或价值被资本消耗吞噬时直接给 ignore。
4. 只研究本公司，不修改共享 JSONL、正式报告、规范与 Git；交付 candidate.json（须含 report_markdown、decision_profile、scenarios、capital_return_profile 与结构化结果）、可读 Python 模型、必要输入及简明结果。
5. 严格遵守写作文体要求：结论先行、平实准确、无过程旁白、不向正文和 decision_profile/scenarios 注入股价买点或交易指令。
```

## 协调复核与入库

协调器按核验附录五关完成实质验收（商业判断、重要性与季报继承、模型复算与四情景单调联动、慢变量结构化完整性、独立读者表达）。发现具体问题时指出原句、缺口与通过条件交回同一研究者修订；全部通过后调用 `research complete` 原子入库。
