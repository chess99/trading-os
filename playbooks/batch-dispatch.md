# 批量独立复核调度 Playbook

## 运行模型

- 一家公司一个独立 agent；公司之间并行，公司内阶段串行。
- 候选集合先冻结；新增公司必须创建新批次。
- runner 只负责执行 JSON 任务，不拥有承保结论权。
- 每个任务使用带超时的租约。失败公司单独重试，已封存结果不得重写。
- 盲评、揭示、challenger、仲裁和组合综合使用不同提示词与最小可读范围。
- v2 旧产物只保留为历史；新生产批次只接受 schema v3，不猜测迁移。

## 生产顺序

1. 只有完成深研、结构化主张和证据封存的公司才能进入候选批次。
2. 程序冻结候选并从旧主张生成不含评级、合理价和仓位的脱敏包。
3. 独立 agent 提交 v3 盲评：只含事实、会计处理、风险、估值、证据账本和可复算回报模型，不得提交承保状态、排名或预期回报结论。
4. 程序验证证据账本并执行会计、正常化盈利、估值、安全边际和风险升级规则；揭示 agent 只记录与旧研究的差异。
5. 程序做一次临时跨公司排序，把当前可能进入前五大仓位的候选与其他规则触发项送入完全独立 challenger。
6. 仲裁 agent 只重建最终事实和假设。程序再次执行全部规则；无可靠共识时不通过。
7. 程序生成单公司候选；单公司 agent 不得提供 `portfolio_eligible`、`rank_score`、`expected_annual_return` 或操作。
8. 公司全部终态后封存最新行情。程序根据未来逐年每股现金分配和终值，按每一个最新价格重算 IRR、距12%门槛差值和12%激活价，再构建组合。
9. 严格验证批次、公司资产、coverage 和派生文件后才发布结果。

```bash
python -m trading_os review create <run-id> --scope-type custom --market CN --description "批次" --candidates <candidates.json>
python -m trading_os review prepare <run-id>
python automation/scripts/review_dispatch.py <run-id> --runner <agent-runner> --concurrency 4
python -m trading_os review validate <run-id> --strict
python -m trading_os review synthesize <run-id> --quotes <quotes.json>
python -m trading_os review report <run-id>
```
