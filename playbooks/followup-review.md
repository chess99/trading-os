# 单公司监控更新 Playbook

## 边界

一个 agent 只更新一家公司。先读 `meta.json` 和 `reports.latest`，不得覆盖此前报告。

## 过程

1. 提取上一轮关键假设、证据截止和触发器。
2. 收集截止时间后的财报、公告、行业数据和公司事件。
3. 将每条主张标为 confirmed、weakened、disproven 或 untested。
4. 判断新信息是否只影响短期情绪，还是改变自由现金流、资本回报、治理或永久资本损失风险。
5. 按 `monitoring_update` 新增中文报告，更新证据和触发器；不在公司状态写组合仓位。
6. 如果原承保结论已失效，启动新的独立承保批次，不能在监控更新中直接恢复买入资格。

## 验证

```bash
python -m trading_os assets validate
python -m trading_os index rebuild
python -m trading_os schedule build
python -m trading_os alerts build
```
