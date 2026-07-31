# 模型组合综合 Playbook

## 两级决策

单公司只能承保通过或不通过，状态由程序生成，不能给买卖动作或仓位。全部公司进入终态、严格验证通过且最新行情快照封存后，组合层才能给 `buy_now`、其他操作和仓位。

portfolio synthesis 是独立预算阶段，必须由主 Agent 对同一 manager-screen run 显式批准；underwriting 或 challenger approval 都不自动授权组合综合。批准需要绑定本次纳入的 underwriting 终态、policy 和 run 级容量账本；相应 sealed approval contract 尚未就绪时不得运行 synthesize。

## 买入条件

1. 确定性承保通过；
2. 证据和行情未过期；最新报价完整覆盖候选、带来源与时区时间，并经过与 synthesize 时间一致的新鲜度校验；
3. 最新价格不高于独立承保的安全边际买入区；
4. 同一组封存未来现金流按最新价格计算的预期年化回报不低于12%；
5. 如果可能进入前五大仓位，完全独立 challenger 已完成；
6. 单股、行业、经济风险簇、前五大集中度和悲观损失预算允许。

缺一项就不能 `buy_now`。候选不足时保留现金，不为满仓降低标准。

## 最新价格重算

公司候选不得保存 agent 自报的预期回报。候选只保存：

- 模型日期与币种；
- 未来第1年至第H年的每股现金分配；
- 第H年末基准情景每股经济价值。

组合程序对每次最新报价计算：

```text
现价 = Σ[第t年现金分配 / (1+r)^t] + 期末价值 / (1+r)^H
```

求得 `r` 为最新预期年化回报。把 `r` 固定为12%得到 `minimum_return_activation_price`。实际可买价格上限为：

```text
min(安全边际买入区上限, 12%回报激活价)
```

10%—12%为高优先级近门槛观察，不给仓位；价格到达实际可买上限时只触发重新运行组合与证据检查，不自动下单。

行情快照不可原地覆盖。过期行情只能追加新的 sealed quote snapshot；若引用 manager-screen 行情，则使用绑定基础 snapshot 路径与 SHA-256 的 sealed quote amendment。不能靠修改 `fresh` 标志或复用盘中无时区价格绕过校验。任何价格触发只请求重新批准与重算，不自动扩容、合成或下单。

## 输出

组合必须展示所有候选的：

- 最新价格及时间；
- 预期年化回报、12%门槛差值；
- 12%激活价和实际可买价格上限；
- 悲观价值、合理价值、安全边际买入区；
- 承保状态、最终操作、仓位和结构化理由；
- 单公司候选 SHA-256 与完整回报模型。

所有落选公司写入排除记录，避免幸存者偏差。

```bash
python -m trading_os review synthesize <run-id> --quotes <quote-snapshot.json>
python -m trading_os review report <run-id>
```
