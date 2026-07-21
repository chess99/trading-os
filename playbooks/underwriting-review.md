# 独立承保复核 Playbook

## 目标

把初始研究当作待验证主张，而不是答案。每家公司由一个独立 agent 重新承保；公司级结果只判断证据和价值是否通过，不能给最终组合操作。

## 半盲两阶段

1. 程序从封存的结构化主张生成脱敏包，删除此前结论性答案。
2. 独立 agent 只接收脱敏包、允许来源和政策，从零重建三张桥、三情景价值和反方证据。
3. `blind-assessment.json` 先做 SHA-256 封存；封存验证通过后才能揭示此前研究并逐条差异审计。
4. 重大分歧、治理疑点、周期位置不明或潜在前五大仓位触发完全独立的 challenger。
5. challenger 不能读取此前研究和第一份评估；两份结果封存后由第三名 agent 仲裁。

## 硬闸门

- 关键财务数字必须有 S1 来源，行业关键驱动按政策满足新鲜度。
- 必须完成盈利质量桥、现金流桥和正常化盈利桥。
- 禁止单季利润简单年化、周期峰值利润外推、未处理一次性项目和净债务。
- 至少两种估值方法、三情景、敏感性、市场隐含预期和三条反方证据。
- 没有可靠共识时不通过。

## 命令

```bash
python -m trading_os review create <run-id> --scope-type industry --market CN --description "行业" --candidates <candidates.json>
python -m trading_os review prepare <run-id>
python automation/scripts/review_dispatch.py <run-id> --runner <agent-runner>
python -m trading_os review status <run-id>
python -m trading_os review validate <run-id> --strict
```
