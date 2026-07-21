# 模型组合综合 Playbook

## 两级决策

单公司只能承保通过或不通过。只有全部公司进入终态、严格验证通过且最新行情快照封存后，组合层才能给 `buy_now`、其他操作和仓位。

## 五个买入条件

1. 承保通过；
2. 证据和行情未过期；
3. 现价进入承保买入区；
4. 横向比较入选；
5. 单股、行业、经济风险簇和损失预算允许。

缺一项就不能 `buy_now`。候选不足时保留现金，不为满仓降低标准。

## 输出

组合必须完整展示所有候选的当前价、悲观价值、合理价值、买入区、承保状态、最终操作、仓位和结构化理由。所有落选公司写入排除记录，避免幸存者偏差。

```bash
python -m trading_os review synthesize <run-id> --quotes <quote-snapshot.json>
python -m trading_os review report <run-id>
```
