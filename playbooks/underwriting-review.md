# 独立承保复核 Playbook

## 目标

把初始研究当作待验证主张，而不是答案。agent负责核验事实与重建假设，程序负责执行规则并生成状态；公司层不得给最终组合操作与仓位。

## 半盲两阶段

1. 程序从封存的结构化主张生成脱敏包，移除旧评级、合理价、买入区和结论。
2. 独立 agent 只接收脱敏包、允许来源与冻结政策，从零重建盈利质量、现金流、正常化盈利、三情景价值、反方证据和回报模型。
3. 盲评必须提交标准证据账本和股本桥。关键财务来源、行情时间、行业及周期数据新鲜度由程序验证。
4. `blind-assessment.json` 先做 SHA-256 封存；揭示阶段只记录它与旧研究的差异，不得改写盲评或自报状态。
5. 程序执行确定性规则，并根据重大分歧、治理疑点、周期位置、永久损失风险和潜在前五大仓位决定 challenger。
6. challenger 完全独立重建同一份 v3 契约；按调度契约，challenger 不能读取此前研究和第一份评估。仲裁完成后程序再次执行规则，两份估值仍无可靠共识时不通过。

## 硬门槛

- 关键财务数字必须来自 S1；必需的一手来源不能由 agent 自行删减。
- 必须完成盈利质量桥、现金流桥和正常化盈利桥。
- 禁止单季度简单年化、周期峰值利润外推、遗漏一次性项目、净债务、少数股东权益或稀释。
- 至少两种估值方法、悲观/基准/乐观三情景、敏感性、市场隐含预期和三条反方证据。
- 治理重大疑点或周期位置不明至少使用 elevated 安全边际；永久损失风险必须使用 severe。
- 同一风险不得无说明地同时在正常化盈利、情景、折现率和安全边际中重复收费。
- 证据缺失改变的是承保状态，不能靠更低价格治愈。

## 回报模型

agent只能提交基准情景未来逐年每股现金分配、持有期末每股经济价值和模型日期。程序用最新价格求 IRR，并用组合政策的12%门槛折现同一组现金流得到激活价。

当前内在价值区间不是未来终值；分红、注销式回购和终值不得重复计算。12%是组合机会成本门槛，不应先塞进业务情景再重复折价。

```bash
python -m trading_os review create <run-id> --scope-type industry --market CN --description "行业" --candidates <candidates.json>
python -m trading_os review prepare <run-id>
python automation/scripts/review_dispatch.py <run-id> --runner <agent-runner>
python -m trading_os review status <run-id>
python -m trading_os review validate <run-id> --strict
```
