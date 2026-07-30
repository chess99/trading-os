# 批量研究与独立复核调度 Playbook

## 两种批次

### Manager screen

- 一批 100—200 家，默认 150。
- 同一个主 Agent完整浏览 packet，不派发单公司 Agent。
- 一次提交全批 `pass/watch/send_to_analyst`。
- 批次只创建 batch、packet、result 及各自 seal。
- 不设半盲路由 reviewer，不创建 correction cohort。

### 单公司研究与承保

- 只有 `send_to_analyst` 后才一家公司一个研究员 Agent。
- 公司之间可并行，公司内阶段串行。
- 研究员只解决决定性问题并提交自己的 package，不写共享 coverage。
- 深研后的 blind review、reveal、challenger、仲裁和组合综合使用不同角色与最小可读范围。

## 调度顺序

1. 主 Agent冻结 scope 和 manager-screen batch。
2. 主 Agent亲自完成整批初筛并物化 coverage。
3. runner 只派发 `quick_profile,status=pending` 的少数候选。
4. 研究员失败只重试该公司；已封存结果不得重写。
5. 主 Agent比较同层结果，决定停止、补证或深研。
6. 深研完成后程序冻结承保候选并生成脱敏包。
7. 独立 reviewer 重建事实、会计、风险、估值和证据账本。
8. 重大分歧、高风险或潜在大仓位进入 challenger；无可靠共识不通过。
9. 公司承保终态后封存最新行情并进行组合综合。

## 租约与恢复

- 单公司任务使用带超时租约；只有确实失效后才释放。
- 同一 symbol 同时只能有一个可变任务所有者。
- result 已封存但 coverage 未写回时，主 Agent重放正式命令修复。
- runner 不拥有承保、晋级或组合结论权。

## 命令

```bash
python -m trading_os coverage manager-screen-freeze <run-id> <batch-id>
python -m trading_os coverage manager-screen-record <run-id> <batch-id> --input <decisions.json>
python -m trading_os coverage manager-screen-status <run-id>

python -m trading_os coverage profile-claim --agent <agent-id> [--symbol CN:000000]
python -m trading_os coverage profile-release --agent <agent-id> --symbol CN:000000 --failure-reason <reason>
python -m trading_os coverage profile-status <cycle-id>

python -m trading_os review create <review-id> --scope-type custom --market CN --description "批次" --candidates <candidates.json>
python -m trading_os review prepare <review-id>
python automation/scripts/review_dispatch.py <review-id> --runner <agent-runner> --concurrency 4
python -m trading_os review validate <review-id> --strict
python -m trading_os review synthesize <review-id> --quotes <quotes.json>
python -m trading_os review report <review-id>
```

旧 `triage-claim/record` 与 `quality-triage-*` 只读兼容，不用于新生产。
