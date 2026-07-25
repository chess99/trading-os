# 批量独立复核调度 Playbook

## 运行模型

- 一家公司一个独立 agent；公司之间并行，公司内阶段串行。
- 候选集合先冻结，新增公司必须创建新批次。
- runner 是供应商无关适配器；领域层不绑定某个模型厂商 CLI。
- 每个任务使用带超时的租约。失败公司单独重试，已封存结果不会重复执行。
- 盲审、揭示、挑战、仲裁和组合综合使用不同提示词和最小可读路径。
- 报告验证通过前不得更新公司状态。

## 主 agent 步骤

1. 只从完整深研已封存、达到承保参考门槛且相对全市场仍具竞争力的公司生成候选 JSON/JSONL；机器排名、快速画像和范围研究不能直接进入承保。
2. 创建批次并冻结候选，随后生成脱敏主张包。
3. 按公司派发独立盲审；不得把此前结论传给盲审 agent。
4. 封存验证通过后派发揭示审计；满足升级条件时派发 challenger 和仲裁。
5. 所有公司终态后，封存最新行情并构建受约束模型组合。
6. 严格验证公司资产、批次、coverage 和生成件，只提交本批次文件。

```bash
python -m trading_os review create <run-id> --scope-type custom --market CN --description "批次" --candidates <candidates.json>
python -m trading_os review prepare <run-id>
python automation/scripts/review_dispatch.py <run-id> --runner <agent-runner> --concurrency 4
python -m trading_os review validate <run-id> --strict
python -m trading_os review synthesize <run-id> --quotes <quotes.json>
python -m trading_os review report <run-id>
```
